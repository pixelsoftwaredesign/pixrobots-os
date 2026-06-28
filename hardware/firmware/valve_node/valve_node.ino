// AgriCol - Nœud micro-vanne irrigation
// ESP32 avec Wi-Fi + MQTT ou Arduino + RS485
//
// Version ESP32 (défaut) : Wi-Fi + MQTT direct
// Version Arduino : Modbus RTU sur RS485
//
// Micro-vannes proportionnelles (PWM) ou ON/OFF
// Ajouter une micro-pompe 12V avec retour Hall pour mesure débit réel
//
// Connexions ESP32 :
//   GPIO16 - Vanne 1 (relais ou MOSFET)
//   GPIO17 - Vanne 2
//   GPIO18 - Vanne 3
//   GPIO19 - Pompe
//   GPIO34 - Capteur débit YF-S201 (impulsions)
//   GPIO35 - Sonde courant vanne (ACS712)
//   GPIO32 - Bouton test local

// #define USE_WIFI
#define USE_RS485

#include "../modbus_common.h"

#ifdef USE_WIFI
#include <WiFi.h>
#include <PubSubClient.h>

const char *WIFI_SSID     = "AgriCol-IoT";
const char *WIFI_PASSWORD = "agricol2026";
const char *MQTT_BROKER   = "10.0.100.1";
const int   MQTT_PORT     = 1883;

WiFiClient wifi_client;
PubSubClient mqtt(wifi_client);
#endif

#ifdef USE_RS485
#include <ModbusRTUSlave.h>
ModbusRTUSlave modbus;
#endif

// --- Pins ESP32 ---
#define PIN_VANNE1      16
#define PIN_VANNE2      17
#define PIN_VANNE3      18
#define PIN_POMPE       19
#define PIN_DEBIT       34      // YF-S201 (entrée impulsion)
#define PIN_COURANT     35      // ACS712
#define PIN_BP_TEST     32

// --- Paramètres vannes ---
#define NB_VANNES       3
#define DEBIT_PULSES_PER_LITER 450  // YF-S201
#define PWM_FREQ        1000
#define PWM_RES         8

// --- État ---
static struct {
    int pin;
    bool etat;      // true = ouverte
    uint8_t ouverture; // 0-255 (PWM)
    unsigned long derniere_commande;
} vannes[NB_VANNES] = {
    { PIN_VANNE1, false, 0, 0 },
    { PIN_VANNE2, false, 0, 0 },
    { PIN_VANNE3, false, 0, 0 },
};

static bool pompe_active = false;
static volatile unsigned long pulse_count = 0;
static unsigned long dernier_debit = 0;
static float debit_l_min = 0;
static float consommation_totale = 0;  // Litres

// ========================================
//  Interruption débitmètre
// ========================================
void IRAM_ATTR debitISR() {
    pulse_count++;
}

// ========================================
//  Commande vanne
// ========================================
void commandeVanne(int idx, bool ouvrir, uint8_t niveau) {
    if (idx < 0 || idx >= NB_VANNES) return;

    if (ouvrir) {
        if (niveau == 0) niveau = 255;  // Pleine ouverture par défaut
        ledcWrite(idx, niveau);          // PWM
        digitalWrite(vannes[idx].pin, HIGH);
        vannes[idx].etat = true;
        vannes[idx].ouverture = niveau;
    } else {
        ledcWrite(idx, 0);
        digitalWrite(vannes[idx].pin, LOW);
        vannes[idx].etat = false;
        vannes[idx].ouverture = 0;
    }
    vannes[idx].derniere_commande = millis();
}

// ========================================
//  Commande pompe
// ========================================
void commandePompe(bool on) {
    if (on) {
        digitalWrite(PIN_POMPE, HIGH);
        pompe_active = true;
    } else {
        digitalWrite(PIN_POMPE, LOW);
        pompe_active = false;
    }
}

// ========================================
//  Fail-safe : fermeture si perte communication
// ========================================
void checkFailSafe() {
    unsigned long now = millis();
    unsigned long timeout = 120000; // 2 minutes sans commande

    for (int i = 0; i < NB_VANNES; i++) {
        if (vannes[i].etat && (now - vannes[i].derniere_commande > timeout)) {
            commandeVanne(i, false, 0);
            Serial.printf("[SAFE] Vanne %d fermée (timeout)\n", i);
        }
    }

    if (pompe_active && (now - dernier_debit > timeout)) {
        // Vérifier qu'aucune vanne n'est ouverte
        bool any_open = false;
        for (int i = 0; i < NB_VANNES; i++) {
            if (vannes[i].etat) { any_open = true; break; }
        }
        if (!any_open) {
            commandePompe(false);
            Serial.println("[SAFE] Pompe arrêtée (aucune vanne ouverte)");
        }
    }
}

// ========================================
//  Mesure débit
// ========================================
void mesureDebit() {
    unsigned long now = millis();
    if (now - dernier_debit < 2000) return;  // Toutes les 2s

    noInterrupts();
    unsigned long pulses = pulse_count;
    pulse_count = 0;
    interrupts();

    unsigned long dt = now - dernier_debit;
    debit_l_min = (float)pulses / DEBIT_PULSES_PER_LITER / (dt / 60000.0);
    consommation_totale += (float)pulses / DEBIT_PULSES_PER_LITER;
    dernier_debit = now;
}

// ========================================
//  Publication MQTT (ESP32)
// ========================================
#ifdef USE_WIFI
void mqttCallback(char *topic, byte *payload, unsigned int len) {
    char cmd[len + 1];
    memcpy(cmd, payload, len);
    cmd[len] = '\0';

    // agricol/commande/vanne/<idx>  OUVRIR/FERMER
    // agricol/commande/pompe        ON/OFF
    if (strstr(topic, "pompe")) {
        commandePompe(strcmp(cmd, "ON") == 0 || strcmp(cmd, "1") == 0);
        return;
    }

    int idx = -1;
    sscanf(topic, "agricol/commande/vanne/%d", &idx);
    if (idx >= 0 && idx < NB_VANNES) {
        bool ouvrir = (strcmp(cmd, "OUVRIR") == 0 || strcmp(cmd, "1") == 0);
        commandeVanne(idx, ouvrir, 255);
    }
}

void mqttPublishState() {
    char buf[128];

    for (int i = 0; i < NB_VANNES; i++) {
        snprintf(buf, sizeof(buf), "agricol/etat/vanne/%d", i + NODE_ADDR);
        mqtt.publish(buf, vannes[i].etat ? "OUVERT" : "FERME");
    }

    snprintf(buf, sizeof(buf), "agricol/etat/pompe/%d", NODE_ADDR);
    mqtt.publish(buf, pompe_active ? "ON" : "OFF");

    snprintf(buf, sizeof(buf), "agricol/etat/debit/%d", NODE_ADDR);
    snprintf(buf + 30, 30, "%.2f", debit_l_min);
    mqtt.publish(buf, buf + 30);
}

void reconnectMQTT() {
    while (!mqtt.connected()) {
        if (mqtt.connect("agricol-valve-node")) {
            mqtt.subscribe("agricol/commande/vanne/#");
            mqtt.subscribe("agricol/commande/pompe");
            Serial.println("[MQTT] Connecté");
        } else {
            delay(5000);
        }
    }
}
#endif

// ========================================
//  Modbus RS485 (Arduino)
// ========================================
#ifdef USE_RS485
uint16_t cbReadRegisters(uint16_t address, uint16_t count, uint16_t *buffer) {
    if (address + count > 8) return 0;
    for (uint16_t i = 0; i < count; i++) buffer[i] = 0;

    if (address == REG_HUMIDITE) {
        buffer[0] = vannes[0].etat ? 1000 : 0;
        if (vannes[1].etat) buffer[0] |= 0x00FF;
    }
    if (address == REG_STATUT) {
        for (int i = 0; i < NB_VANNES; i++)
            if (vannes[i].etat) buffer[0] |= (1 << i);
        if (pompe_active) buffer[0] |= (1 << 4);
    }
    return count;
}

uint16_t cbWriteCoil(uint16_t address, uint16_t value) {
    if (address == COIL_VANNE) {
        // Commandes toutes les vannes sur ce nœud
        for (int i = 0; i < NB_VANNES; i++)
            commandeVanne(i, value != 0, 255);
        return 1;
    }
    if (address == COIL_RESET) {
        ESP.restart();
    }
    return 0;
}
#endif

// ========================================
//  Setup
// ========================================

void setup() {
    Serial.begin(115200);
    Serial.printf("\n[AgriCol] Nœud vanne %d démarré\n", NODE_ADDR);

    // PWM pour les vannes
    ledcAttachPin(PIN_VANNE1, 0);
    ledcAttachPin(PIN_VANNE2, 1);
    ledcAttachPin(PIN_VANNE3, 2);
    ledcSetup(0, PWM_FREQ, PWM_RES);
    ledcSetup(1, PWM_FREQ, PWM_RES);
    ledcSetup(2, PWM_FREQ, PWM_RES);

    pinMode(PIN_VANNE1, OUTPUT);
    pinMode(PIN_VANNE2, OUTPUT);
    pinMode(PIN_VANNE3, OUTPUT);
    pinMode(PIN_POMPE, OUTPUT);
    pinMode(PIN_BP_TEST, INPUT_PULLUP);

    // Tout fermé par défaut (FAIL-SAFE)
    commandeVanne(0, false, 0);
    commandeVanne(1, false, 0);
    commandeVanne(2, false, 0);
    commandePompe(false);
    Serial.println("[SAFE] Toutes vannes fermées au démarrage");

    // Débitmètre
    pinMode(PIN_DEBIT, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_DEBIT), debitISR, RISING);

#ifdef USE_WIFI
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    mqtt.setServer(MQTT_BROKER, MQTT_PORT);
    mqtt.setCallback(mqttCallback);
#endif

#ifdef USE_RS485
    modbus.configure(NODE_ADDR);
    modbus.registerReadHoldingRegistersCallback(cbReadRegisters);
    modbus.registerWriteSingleCoilCallback(cbWriteCoil);
    modbus.begin(Serial1, 9600, /*DE=*/4, /*RE=*/4);
#endif
}

// ========================================
//  Loop
// ========================================

void loop() {
    static unsigned long last_mqtt = 0;

    // Bouton test local : ouvrir/fermer vanne 0
    if (digitalRead(PIN_BP_TEST) == LOW) {
        delay(50);  // Debounce
        while (digitalRead(PIN_BP_TEST) == LOW);
        commandeVanne(0, !vannes[0].etat, 255);
    }

    // Mesure débit
    mesureDebit();

    // Fail-safe
    checkFailSafe();

#ifdef USE_WIFI
    if (!mqtt.connected()) reconnectMQTT();
    mqtt.loop();

    if (millis() - last_mqtt > 10000) {
        mqttPublishState();
        last_mqtt = millis();
    }
#endif

#ifdef USE_RS485
    modbus.poll();
#endif
}
