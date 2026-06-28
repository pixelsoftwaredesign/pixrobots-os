/*
 * AgriCol - Serial↔MQTT Gateway Daemon for OpenBSD
 * Lit les données Modbus RTU sur RS485, publie en MQTT.
 * Reçoit les commandes MQTT, écrit en Modbus.
 *
 * Compilation: cc -o serial_gateway serial_gateway.c -lpaho-mqtt3c
 * Installation: /usr/local/libexec/agricol/serial_gateway
 */

#include <sys/types.h>
#include <sys/ioctl.h>
#include <sys/param.h>
#include <sys/watchdog.h>

#include <err.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <unistd.h>

#include <mqtt.h>  /* paho-mqtt */

#define MAX_NODES         32
#define SERIAL_BUF        256
#define MQTT_TOPIC_LEN    128
#define MQTT_PAYLOAD_LEN  512

/* === Configuration === */
static const char *SERIAL_DEV = "/dev/ttyU0";
static const int   SERIAL_BAUD = B9600;
static const char *MQTT_BROKER = "tcp://localhost:1883";
static const char *MQTT_CLIENT_ID = "agricol-gateway";
static const char *TOPIC_PREFIX = "agricol/rs485/";
static const int   WATCHDOG_TIMEOUT = 30; /* secondes */
static const int   POLL_INTERVAL_MS = 100;

/* === État global === */
static volatile sig_atomic_t running = 1;

/* === Structure nœud Modbus === */
typedef struct {
    uint8_t  addr;       /* Adresse Modbus (1-247) */
    char     nom[32];    /* Nom lisible */
    int      type;       /* 0=capteur sol, 1=vanne, 2=météo */
    uint16_t last_hum;   /* Dernière humidité (x10) */
    uint16_t last_temp;  /* Dernière température (x10) */
    time_t   last_seen;  /* Timestamp dernière communication */
    int      valve_state;/* 0=fermée, 1=ouverte */
} ModbusNode;

static ModbusNode nodes[MAX_NODES];
static int nb_nodes = 0;
static int serial_fd = -1;
static int watchdog_fd = -1;
static mqtt_client_t *mqtt_client = NULL;

/* === Prototypes === */
static void signal_handler(int);
static int  open_serial(const char *, int);
static int  serial_read(uint8_t *, size_t);
static int  serial_write(uint8_t *, size_t);
static int  modbus_read_registers(uint8_t addr, uint16_t reg, uint16_t count, uint16_t *dest);
static int  modbus_write_coil(uint8_t addr, uint16_t coil, int value);
static void mqtt_message_cb(void *, struct mqtt_response *);
static void process_sensor_data(uint8_t addr, uint16_t *regs, int count);
static void watchdog_pet(void);
static void init_nodes(void);
static void poll_nodes(void);

/* === Signal handler : arrêt propre === */
static void signal_handler(int sig) {
    (void)sig;
    running = 0;
}

/* === Watchdog : "pet" toutes les 10s, timeout 30s === */
static void watchdog_pet(void) {
    if (watchdog_fd < 0) {
        watchdog_fd = open("/dev/watchdog", O_RDWR);
        if (watchdog_fd < 0) return;
    }
    int timeout = WATCHDOG_TIMEOUT;
    ioctl(watchdog_fd, WDIOCSETTIMEOUT, &timeout);
    ioctl(watchdog_fd, WDIOCPETSOT, NULL);
}

/* === Ouverture port série === */
static int open_serial(const char *dev, int baud) {
    int fd = open(dev, O_RDWR | O_NOCTTY | O_NDELAY);
    if (fd < 0) return -1;

    struct termios tio;
    memset(&tio, 0, sizeof(tio));
    cfsetispeed(&tio, baud);
    cfsetospeed(&tio, baud);
    tio.c_cflag = CS8 | CLOCAL | CREAD | PARENB; /* 8N1 avec parité paire */
    tio.c_iflag = IGNPAR;
    tio.c_oflag = 0;
    tio.c_lflag = 0;
    tio.c_cc[VMIN]  = 1;
    tio.c_cc[VTIME] = 10; /* 1 seconde timeout */

    tcflush(fd, TCIFLUSH);
    tcsetattr(fd, TCSANOW, &tio);
    return fd;
}

/* === Tramme Modbus RTU : CRC16 === */
static uint16_t modbus_crc(uint8_t *buf, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= buf[i];
        for (int j = 0; j < 8; j++) {
            if (crc & 0x0001) crc = (crc >> 1) ^ 0xA001;
            else              crc >>= 1;
        }
    }
    return crc;
}

/* === Lecture registres Modbus === */
static int modbus_read_registers(uint8_t addr, uint16_t reg, uint16_t count, uint16_t *dest) {
    uint8_t req[8] = {
        addr,           /* Adresse esclave */
        0x03,           /* Fonction: lire registres */
        (reg >> 8) & 0xFF, reg & 0xFF,  /* Adresse registre */
        (count >> 8) & 0xFF, count & 0xFF, /* Nombre registres */
        0, 0            /* CRC (calculé après) */
    };
    uint16_t crc = modbus_crc(req, 6);
    req[6] = crc & 0xFF;
    req[7] = (crc >> 8) & 0xFF;

    serial_write(req, 8);
    usleep(50000); /* Attente réponse esclave */

    uint8_t resp[64];
    int len = serial_read(resp, sizeof(resp));
    if (len < 5 || resp[0] != addr || resp[1] != 0x03) return -1;

    int byte_count = resp[2];
    for (int i = 0; i < byte_count / 2 && i < (int)count; i++) {
        dest[i] = (resp[3 + i*2] << 8) | resp[4 + i*2];
    }
    return byte_count / 2;
}

/* === Écriture coil Modbus === */
static int modbus_write_coil(uint8_t addr, uint16_t coil, int value) {
    uint8_t req[8] = {
        addr,
        0x05,           /* Fonction: écrire coil unique */
        (coil >> 8) & 0xFF, coil & 0xFF,
        value ? 0xFF : 0x00, 0x00,  /* ON=0xFF00, OFF=0x0000 */
        0, 0
    };
    uint16_t crc = modbus_crc(req, 6);
    req[6] = crc & 0xFF;
    req[7] = (crc >> 8) & 0xFF;

    serial_write(req, 8);
    usleep(30000);
    return 0;
}

/* === Callback MQTT : commande reçue === */
static void mqtt_message_cb(void *unused, struct mqtt_response *resp) {
    (void)unused;
    if (!resp) return;

    char topic[MQTT_TOPIC_LEN];
    char payload[MQTT_PAYLOAD_LEN];
    int tlen = resp->topic_name_size < MQTT_TOPIC_LEN ? resp->topic_name_size : MQTT_TOPIC_LEN - 1;
    int plen = resp->application_message_size < MQTT_PAYLOAD_LEN ? resp->application_message_size : MQTT_PAYLOAD_LEN - 1;
    memcpy(topic, resp->topic_name, tlen); topic[tlen] = '\0';
    memcpy(payload, resp->application_message, plen); payload[plen] = '\0';

    /* Topic: agricol/commande/vanne/<addr> */
    int addr;
    if (sscanf(topic, "agricol/commande/vanne/%d", &addr) == 1 && addr > 0 && addr < 248) {
        int ouvrir = (strcmp(payload, "OUVRIR") == 0 || strcmp(payload, "1") == 0);
        modbus_write_coil((uint8_t)addr, 0, ouvrir);
        syslog(LOG_INFO, "Commande vanne %d: %s", addr, ouvrir ? "OUVRIR" : "FERMER");

        /* Mettre à jour état local */
        for (int i = 0; i < nb_nodes; i++) {
            if (nodes[i].addr == addr) {
                nodes[i].valve_state = ouvrir;
                break;
            }
        }
    }
}

/* === Publication MQTT === */
static void mqtt_publish(const char *topic, const char *fmt, ...) {
    if (!mqtt_client) return;
    char buf[MQTT_PAYLOAD_LEN];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);

    mqtt_publish_response_t presp;
    mqtt_publish(mqtt_client, topic, buf, strlen(buf), &presp, MQTT_PUBLISH_QOS_1);
}

/* === Boucle de scrutation des nœuds === */
static void poll_nodes(void) {
    uint16_t regs[16];

    for (int i = 0; i < nb_nodes; i++) {
        ModbusNode *n = &nodes[i];

        if (n->type == 0 || n->type == 2) {
            /* Capteur sol/météo : lire registres 0-5 */
            int nreg = modbus_read_registers(n->addr, 0, 5, regs);
            if (nreg > 0) {
                n->last_hum = regs[0];      /* Humidité x10 */
                n->last_temp = regs[1];     /* Température x10 */
                n->last_seen = time(NULL);

                char topic[64];
                snprintf(topic, sizeof(topic), "agricol/capteur/%s", n->nom);
                mqtt_publish(topic,
                    "{\"id\":\"%s\",\"addr\":%d,\"hum\":%.1f,\"temp\":%.1f}",
                    n->nom, n->addr,
                    (float)n->last_hum / 10.0,
                    (float)n->last_temp / 10.0);
            }
        }
    }
}

/* === Initialisation des nœuds === */
static void init_nodes(void) {
    /* Surcharger avec fichier de config /etc/agricol/nodes.conf */
    FILE *f = fopen("/etc/agricol/nodes.conf", "r");
    if (f) {
        while (fscanf(f, "%hhu %31s %d\n", &nodes[nb_nodes].addr,
                      nodes[nb_nodes].nom, &nodes[nb_nodes].type) == 3) {
            nodes[nb_nodes].last_hum = 0;
            nodes[nb_nodes].last_temp = 0;
            nodes[nb_nodes].last_seen = 0;
            nodes[nb_nodes].valve_state = 0;
            nb_nodes++;
            if (nb_nodes >= MAX_NODES) break;
        }
        fclose(f);
        syslog(LOG_INFO, "Chargé %d nœuds depuis /etc/agricol/nodes.conf", nb_nodes);
        return;
    }

    /* Configuration par défaut */
    const ModbusNode def[] = {
        { 10, "serre_nord_sol",   0, 0, 0, 0, 0 },
        { 11, "champ_ouest_sol",  0, 0, 0, 0, 0 },
        { 12, "verger_est_sol",   0, 0, 0, 0, 0 },
        { 20, "station_meteo",    2, 0, 0, 0, 0 },
        { 30, "vanne_serre",      1, 0, 0, 0, 0 },
        { 31, "vanne_champ",      1, 0, 0, 0, 0 },
        { 32, "vanne_verger",     1, 0, 0, 0, 0 },
    };
    nb_nodes = sizeof(def) / sizeof(def[0]);
    memcpy(nodes, def, sizeof(def));
    syslog(LOG_INFO, "Configuration par défaut: %d nœuds", nb_nodes);
}

/* === Point d'entrée === */
int main(int argc, char **argv) {
    openlog("agricol-gw", LOG_PID | LOG_CONS, LOG_DAEMON);

    /* Option: device série */
    if (argc > 1) SERIAL_DEV = argv[1];

    /* Signaux */
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    signal(SIGPIPE, SIG_IGN);

    /* Initialisation nœuds */
    init_nodes();

    /* Ouverture port série */
    serial_fd = open_serial(SERIAL_DEV, SERIAL_BAUD);
    if (serial_fd < 0) {
        syslog(LOG_ERR, "Impossible d'ouvrir %s: %m", SERIAL_DEV);
        return 1;
    }
    syslog(LOG_INFO, "Port série %s ouvert (9600 8E1)", SERIAL_DEV);

    /* Connexion MQTT */
    mqtt_client = mqtt_connect(MQTT_BROKER, MQTT_CLIENT_ID);
    if (!mqtt_client) {
        syslog(LOG_ERR, "Impossible de connecter MQTT à %s", MQTT_BROKER);
        return 1;
    }

    /* Souscription aux commandes vannes */
    mqtt_subscribe(mqtt_client, "agricol/commande/vanne/+", 0);
    mqtt_set_callback(mqtt_client, mqtt_message_cb, NULL);

    syslog(LOG_INFO, "Gateway AgriCol démarrée");

    /* Boucle principale */
    time_t last_poll = 0;
    time_t last_watchdog = 0;

    while (running) {
        time_t now = time(NULL);

        /* Scrutation des capteurs toutes les 5 secondes */
        if (now - last_poll >= 5) {
            poll_nodes();
            last_poll = now;
        }

        /* Watchdog toutes les 10 secondes */
        if (now - last_watchdog >= 10) {
            watchdog_pet();
            last_watchdog = now;
        }

        /* Traitement MQTT */
        mqtt_sync(mqtt_client, 100);

        usleep(POLL_INTERVAL_MS * 1000);
    }

    /* Arrêt propre : fermer toutes les vannes */
    syslog(LOG_WARNING, "Arrêt : fermeture de toutes les vannes !");
    for (int i = 0; i < nb_nodes; i++) {
        if (nodes[i].type == 1) {
            modbus_write_coil(nodes[i].addr, 0, 0);
            syslog(LOG_INFO, "Vanne %s fermée (sécurité)", nodes[i].nom);
        }
    }

    mqtt_disconnect(mqtt_client);
    close(serial_fd);
    if (watchdog_fd >= 0) close(watchdog_fd);
    closelog();
    return 0;
}
