// AgriCol - Station météo agricole
// ESP32 avec DHT22, BMP280, anémomètre, pluviomètre, LUX
//
// Communication: MQTT via Wi-Fi + Modbus RS485 (redondant)
// Alimentation: Panneau solaire + batterie Li-ion 18650
//
// Connexions ESP32 :
//   GPIO2  - DHT22
//   GPIO21 - BMP280 SDA (I2C)
//   GPIO22 - BMP280 SCL (I2C)
//   GPIO3  - Pluviomètre (interruption RISING)
//   GPIO4  - Anémomètre (interruption RISING)
//   GPIO36 - Luminosité LDR
//   GPIO39 - Tension panneau solaire

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <Adafruit_BMP280.h>
#include <esp_sleep.h>

#include "../modbus_common.h"

// --- Wi-Fi / MQTT ---
const char *WIFI_SSID     = "AgriCol-IoT";
const char *WIFI_PASSWORD = "agricol2026";
const char *MQTT_BROKER   = "10.0.100.1";
const int   MQTT_PORT     = 1883;
const char *MQTT_TOPIC    = "agricol/meteo";

WiFiClient wifi_client;
PubSubClient mqtt(wifi_client);

// --- Capteurs ---
#define PIN_DHT     2
#define PIN_BMP_SDA 21
#define PIN_BMP_SCL 22
#define PIN_PLUIE   3
#define PIN_ANEMO   4
#define PIN_LUX     36
#define PIN_SOLAR   39

DHT dht(PIN_DHT, DHT22);
Adafruit_BMP280 bmp;

// --- Variables météo ---
static float temperature = 0;
static float humidite_air = 0;
static float pression = 1013.25;
static float pluie_mm_h = 0;
static float vent_km_h = 0;
static float luminosite_lux = 0;
static float tension_solaire = 0;

// --- Interruptions ---
static volatile unsigned long pluie_pulses = 0;
static volatile unsigned long vent_pulses = 0;
static unsigned long last_meteo = 0;
static unsigned long last_mqtt = 0;

// Pluviomètre: 1 pulse = 0.2mm d'eau
#define PLUIE_MM_PER_PULSE 0.2
// Anémomètre: 1 pulse/s = 2.4 km/h (facteur à calibrer)
#define VENT_FACTOR 2.4

void IRAM_ATTR pluieISR() {
    pluie_pulses++;
}

void IRAM_ATTR ventISR() {
    vent_pulses++;
}

// ========================================
//  WiFi + MQTT
// ========================================
void reconnectMQTT() {
    if (WiFi.status() != WL_CONNECTED) {
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        for (int i = 0; i < 30 && WiFi.status() != WL_CONNECTED; i++) delay(500);
    }

    while (!mqtt.connected()) {
        if (mqtt.connect("agricol-meteo")) break;
        delay(5000);
    }
}

void publishMeteo() {
    char buf[256];
    snprintf(buf, sizeof(buf),
        "{"
        "\"temp\":%.1f,"
        "\"hum\":%.1f,"
        "\"pression\":%.1f,"
        "\"pluie\":%.2f,"
        "\"vent\":%.1f,"
        "\"lux\":%.0f,"
        "\"solaire\":%.2f"
        "}",
        temperature, humidite_air, pression,
        pluie_mm_h, vent_km_h,
        luminosite_lux, tension_solaire);

    mqtt.publish(MQTT_TOPIC, buf);
    Serial.print("[MQTT] Publié: ");
    Serial.println(buf);
}

// ========================================
//  Mesures
// ========================================
void lireCapteurs() {
    unsigned long now = millis();
    if (now - last_meteo < 5000) return;  // Toutes les 5s

    // DHT22
    temperature = dht.readTemperature();
    humidite_air = dht.readHumidity();
    if (isnan(temperature)) temperature = 0;
    if (isnan(humidite_air)) humidite_air = 0;

    // BMP280
    pression = bmp.readPressure() / 100.0;  // hPa
    if (isnan(pression)) pression = 1013.25;

    // Luminosité
    int ldr_raw = analogRead(PIN_LUX);
    luminosite_lux = map(ldr_raw, 0, 4095, 0, 100000);

    // Tension panneau solaire
    int sol_raw = analogRead(PIN_SOLAR);
    tension_solaire = (sol_raw / 4095.0) * 3.3 * 2;  // Diviseur x2

    // Pluie (cumul sur 5 min)
    noInterrupts();
    unsigned long pluie_p = pluie_pulses;
    unsigned long vent_p = vent_pulses;
    pluie_pulses = 0;
    vent_pulses = 0;
    interrupts();

    pluie_mm_h = (pluie_p * PLUIE_MM_PER_PULSE) / (5.0 / 60.0);  // mm/h
    if (pluie_mm_h > 200) pluie_mm_h = 0;  // Anti-rebond

    vent_km_h = vent_p * VENT_FACTOR;
    if (vent_km_h > 200) vent_km_h = 0;

    last_meteo = now;
}

// ========================================
//  Alarme irrigation (éviter arrosage sous pluie / vent fort)
// ========================================
void checkIrrigationBlock() {
    if (pluie_mm_h > 2.0) {
        mqtt.publish("agricol/alerte/meteo", "PLUIE_FORTE");
        mqtt.publish("agricol/commande/pompe", "OFF");  // Forcer arrêt
        Serial.println("[ALERTE] Pluie détectée - irrigation bloquée");
    }
    if (vent_km_h > 60.0) {
        mqtt.publish("agricol/alerte/meteo", "VENT_FORT");
        Serial.println("[ALERTE] Vent fort détecté");
    }
}

// ========================================
//  Setup
// ========================================
void setup() {
    Serial.begin(115200);
    Serial.println("\n[AgriCol] Station météo démarrée");

    // Capteurs
    dht.begin();
    Wire.begin(PIN_BMP_SDA, PIN_BMP_SCL);
    if (!bmp.begin(0x76)) {
        Serial.println("[ERR] BMP280 non trouvé");
    }
    bmp.setSampling(Adafruit_BMP280::MODE_NORMAL,
                    Adafruit_BMP280::SAMPLING_X2,
                    Adafruit_BMP280::SAMPLING_X16,
                    Adafruit_BMP280::FILTER_X16,
                    Adafruit_BMP280::STANDBY_MS_500);

    // Interruptions
    pinMode(PIN_PLUIE, INPUT_PULLUP);
    pinMode(PIN_ANEMO, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_PLUIE), pluieISR, RISING);
    attachInterrupt(digitalPinToInterrupt(PIN_ANEMO), ventISR, RISING);

    // Wi-Fi et MQTT
    reconnectMQTT();

    // Deep sleep si batterie faible
    esp_sleep_enable_timer_wakeup(30 * 1000000);  // 30 secondes
}

// ========================================
//  Loop
// ========================================
void loop() {
    reconnectMQTT();
    mqtt.loop();

    lireCapteurs();

    if (millis() - last_mqtt > 10000) {
        publishMeteo();
        checkIrrigationBlock();
        last_mqtt = millis();
    }

    delay(500);

    // Mode économie si batterie < 3.5V
    if (tension_solaire < 3.5 && tension_solaire > 0.1) {
        Serial.println("[SLEEP] Batterie faible - deep sleep 30s");
        esp_deep_sleep_start();
    }
}
