// AgriCol - ESP32 Gateway Wi-Fi ↔ RS485
// Pont entre le bus RS485 filaire (capteurs Arduino) et le réseau Wi-Fi MQTT
//
// Ce nœud est le chef d'orchestre du bus RS485 :
// - Interroge chaque nœud Modbus à tour de rôle
// - Publie les données consolidées en MQTT
// - Relaie les commandes MQTT vers les vannes Modbus

#include <WiFi.h>
#include <PubSubClient.h>
#include <ModbusRTUMaster.h>
#include "../modbus_common.h"

// --- Wi-Fi / MQTT ---
const char *WIFI_SSID     = "AgriCol-IoT";
const char *WIFI_PASSWORD = "agricol2026";
const char *MQTT_BROKER   = "10.0.100.1";
const int   MQTT_PORT     = 1883;

WiFiClient wifi_client;
PubSubClient mqtt(wifi_client);

// --- RS485 ---
#define RS485_DE_RE  4
#define RS485_RX     16
#define RS485_TX     17
HardwareSerial rs485(2);  // UART2
ModbusRTUMaster modbus;

// --- Topologie des nœuds ---
typedef struct {
    uint8_t  addr;
    char     nom[20];
    int      type;    // 0=sol, 1=vanne, 2=météo, 3=débit, 4=PIR
    uint16_t last_regs[6];
    unsigned long last_seen;
    bool     online;
} Node;

static Node nodes[] = {
    { ADDR_SOL_SERRE,    "sol_serre",    0, {0},{0},false },
    { ADDR_SOL_CHAMP,    "sol_champ",    0, {0},{0},false },
    { ADDR_SOL_VERGER,   "sol_verger",   0, {0},{0},false },
    { ADDR_VANNE_SERRE,  "vanne_serre",  1, {0},{0},false },
    { ADDR_VANNE_CHAMP,  "vanne_champ",  1, {0},{0},false },
    { ADDR_VANNE_VERGER, "vanne_verger", 1, {0},{0},false },
    { ADDR_METEO,        "meteo",        2, {0},{0},false },
    { ADDR_DEBIT_SERRE,  "debit_serre",  3, {0},{0},false },
};
static const int NB_NODES = sizeof(nodes) / sizeof(nodes[0]);

static int current_node = 0;
static unsigned long last_scan = 0;
static const int SCAN_INTERVAL = 2000;  // 2s entre chaque nœud

// ========================================
//  MQTT - Réception des commandes
// ========================================
void mqttCallback(char *topic, byte *payload, unsigned int len) {
    char cmd[len + 1];
    memcpy(cmd, payload, len);
    cmd[len] = '\0';

    Serial.printf("[MQTT] Topic: %s, Payload: %s\n", topic, cmd);

    // agricol/commande/vanne/<nom_zone>
    char zone[32];
    if (sscanf(topic, "agricol/commande/vanne/%s", zone) == 1) {
        for (int i = 0; i < NB_NODES; i++) {
            if (nodes[i].type == 1 && strcmp(nodes[i].nom, zone) == 0) {
                bool etat = (strcmp(cmd, "OUVRIR") == 0 || strcmp(cmd, "1") == 0);
                modbus.writeSingleCoil(rs485, nodes[i].addr, 0, etat ? 0xFF00 : 0x0000);
                Serial.printf("[CMD] Vanne %s -> %s\n", zone, etat ? "OUVRIR" : "FERMER");
                return;
            }
        }
    }

    // agriculture/commande/pompe ON/OFF
    if (strcmp(topic, "agricol/commande/pompe") == 0) {
        bool on = (strcmp(cmd, "ON") == 0);
        // La pompe est connectée au nœud vanne principal
        modbus.writeSingleCoil(rs485, ADDR_VANNE_SERRE, 1, on ? 0xFF00 : 0x0000);
        Serial.printf("[CMD] Pompe -> %s\n", on ? "ON" : "OFF");
    }
}

// ========================================
//  Scrutation d'un nœud Modbus
// ========================================
bool pollNode(Node *n) {
    uint16_t regs[6];
    int nb = modbus.readHoldingRegisters(rs485, n->addr, 0, 5, regs);
    if (nb > 0) {
        memcpy(n->last_regs, regs, sizeof(uint16_t) * 6);
        n->last_seen = millis();
        n->online = true;
        return true;
    }
    if (n->online) {
        Serial.printf("[OFFLINE] Nœud %s (adr %d)\n", n->nom, n->addr);
    }
    n->online = false;
    return false;
}

// ========================================
//  Publication des données
// ========================================
void publishData(Node *n) {
    if (!n->online) return;

    char topic[64];
    char payload[256];

    switch (n->type) {
    case 0:  // Capteur sol
        snprintf(topic, sizeof(topic), "agricol/capteur/%s", n->nom);
        snprintf(payload, sizeof(payload),
            "{\"hum\":%.1f,\"temp\":%.1f,\"ph\":%.2f,\"ec\":%d,\"batt\":%s}",
            n->last_regs[REG_HUMIDITE] / 10.0,
            n->last_regs[REG_TEMPERATURE] / 10.0,
            n->last_regs[REG_PH] / 100.0,
            n->last_regs[REG_CONDUCTIVITE],
            (n->last_regs[REG_STATUT] & STATUT_BATTERIE_LOW) ? "FAIBLE" : "OK");
        mqtt.publish(topic, payload);
        break;

    case 1:  // Vanne
        snprintf(topic, sizeof(topic), "agricol/etat/vanne/%s", n->nom);
        mqtt.publish(topic,
            (n->last_regs[REG_STATUT] & STATUT_VANNE_OPEN) ? "OUVERT" : "FERME");
        break;

    case 2:  // Météo
        snprintf(topic, sizeof(topic), "agricol/capteur/%s", n->nom);
        snprintf(payload, sizeof(payload),
            "{\"temp\":%.1f,\"hum\":%.1f,\"pression\":%d}",
            n->last_regs[REG_TEMPERATURE] / 10.0,
            n->last_regs[REG_HUMIDITE] / 10.0,
            n->last_regs[REG_PH]);  // Pression stockée dans pH reg
        mqtt.publish(topic, payload);
        break;

    case 3:  // Débitmètre
        snprintf(topic, sizeof(topic), "agricol/etat/debit/%s", n->nom);
        snprintf(payload, sizeof(payload),
            "{\"debit\":%d,\"total\":%d}",
            n->last_regs[REG_HUMIDITE],
            n->last_regs[REG_TEMPERATURE]);
        mqtt.publish(topic, payload);
        break;
    }
}

// ========================================
//  Setup
// ========================================
void setup() {
    Serial.begin(115200);
    Serial.println("\n[AgriCol] Gateway RS485 ↔ MQTT");

    // RS485 sur UART2
    rs485.begin(9600, SERIAL_8E1, RS485_RX, RS485_TX);
    pinMode(RS485_DE_RE, OUTPUT);
    digitalWrite(RS485_DE_RE, LOW);  // Réception par défaut

    modbus.setTimeout(100);  // 100ms timeout par nœud

    // Wi-Fi
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) {
        delay(500);
        Serial.print(".");
    }
    Serial.printf("\n[WiFi] Connecté: %s\n", WiFi.localIP().toString().c_str());

    // MQTT
    mqtt.setServer(MQTT_BROKER, MQTT_PORT);
    mqtt.setCallback(mqttCallback);
    while (!mqtt.connected()) {
        if (mqtt.connect("agricol-gateway")) {
            mqtt.subscribe("agricol/commande/#");
            Serial.println("[MQTT] Connecté");
        } else {
            delay(5000);
        }
    }
}

// ========================================
//  Loop
// ========================================
void loop() {
    mqtt.loop();

    unsigned long now = millis();
    if (now - last_scan < SCAN_INTERVAL) {
        delay(10);
        return;
    }
    last_scan = now;

    // Scrutation round-robin
    Node *n = &nodes[current_node];
    bool ok = pollNode(n);
    if (ok) publishData(n);

    current_node = (current_node + 1) % NB_NODES;

    // Rapport périodique (tous les tours complets)
    if (current_node == 0) {
        int online = 0;
        for (int i = 0; i < NB_NODES; i++)
            if (nodes[i].online) online++;
        Serial.printf("[STATUS] %d/%d nœuds en ligne\n", online, NB_NODES);
    }
}
