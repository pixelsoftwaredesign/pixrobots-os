// AgriCol - Nœud capteur de sol (humidity/temp/pH/EC)
// Compatible Arduino Mega 2560 + RS485 shield
//
// Communication: Modbus RTU sur RS485 via SoftwareSerial ou Serial1
// Alimentation: Batterie Li-ion avec recharge solaire
// Watchdog: interne Arduino (réveil périodique)
//
// Connexions:
//   A0  - Capteur humidité capacitif (0-3.3V)
//   A1  - Module pH (0-5V)
//   A2  - Module TDS/conductivité
//   7   - DS18B20 température sol (OneWire)
//   A7  - Diviseur batterie (mesure tension)
//   RS485 - Serial1 (TX1=18, RX1=19, DE/RE=6)

#include <ModbusRTUSlave.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <avr/wdt.h>
#include <avr/sleep.h>

#include "../modbus_common.h"

// --- Configuration ---
// Choisir l'adresse en décommentant :
//#define NODE_ADDR ADDR_SOL_SERRE
#define NODE_ADDR ADDR_SOL_CHAMP
//#define NODE_ADDR ADDR_SOL_VERGER

#define RS485_DE_RE_PIN   6
#define ONE_WIRE_BUS      7
#define PIN_BATTERY       A7
#define VREF              5.0
#define VBAT_DIVIDER_RATIO 2.0    // Résistance diviseur

// --- Registres internes ---
static uint16_t regs[8] = {0};
static const int NB_REGS = 6;

// --- Capteurs ---
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature ds18b20(&oneWire);
ModbusRTUSlave modbus;

// --- Variables capteurs ---
static float humidity = 0;
static float temperature = 0;
static float pH = 7.0;
static float ec = 0;
static float battery = 0;
static unsigned long last_read = 0;

// ========================================
//  Fonctions capteurs
// ========================================

// Lecture humidité sol (capteur capacitif)
float readHumidity() {
    int raw = analogRead(PIN_HUMIDITE);
    // Capteur capacitif: valeurs inverses (sec=650+ / humide=250-)
    // Mapper à 0-100%
    float pct = map(raw, 700, 200, 0, 10000) / 100.0;
    return constrain(pct, 0.0, 100.0);
}

// Lecture pH
float readPH() {
    int raw = analogRead(PIN_PH);
    float voltage = raw * (VREF / 1024.0);
    // Courbe de calibration du module pH
    // pH = 7.0 + (2.5 - voltage) / 0.18
    return 7.0 + (2.5 - voltage) / 0.18;
}

// Lecture conductivité (TDS meter)
float readEC() {
    int raw = analogRead(PIN_CONDUCTIVITE);
    float voltage = raw * (VREF / 1024.0);
    // TDS = (voltage / VREF) * 1000 * facteur_calibration
    return (voltage / VREF) * 1000.0 * 0.5;
}

// Lecture batterie
float readBattery() {
    int raw = analogRead(PIN_BATTERIE);
    float voltage = raw * (VREF / 1024.0);
    return voltage * VBAT_DIVIDER_RATIO;
}

// ========================================
//  Modbus callbacks
// ========================================

// Lecture registres
uint16_t cbReadRegisters(uint16_t address, uint16_t count, uint16_t *buffer) {
    if (address + count > NB_REGS) return 0;
    for (uint16_t i = 0; i < count; i++) {
        buffer[i] = regs[address + i];
    }
    return count;
}

// Écriture coil (vanne sur ce nœud)
uint16_t cbWriteCoil(uint16_t address, uint16_t value) {
    if (address == COIL_VANNE) {
        if (value) {
            regs[REG_STATUT] |= STATUT_VANNE_OPEN;
        } else {
            regs[REG_STATUT] &= ~STATUT_VANNE_OPEN;
        }
        return 1;
    }
    if (address == COIL_RESET) {
        wdt_enable(WDTO_15MS);
        while (1); // reset
    }
    return 0;
}

// ========================================
//  Mise à jour registres
// ========================================

void updateRegisters() {
    // R0: Humidité x10
    regs[REG_HUMIDITE] = (uint16_t)(humidity * 10);
    // R1: Température x10
    regs[REG_TEMPERATURE] = (uint16_t)(temperature * 10 + 0.5);
    // R2: Statut
    uint16_t status = regs[REG_STATUT] & ~(STATUT_ERR_HUM | STATUT_ERR_TEMP | STATUT_BATTERIE_LOW);
    if (isnan(humidity))      status |= STATUT_ERR_HUM;
    if (isnan(temperature))   status |= STATUT_ERR_TEMP;
    if (battery < 3.3)        status |= STATUT_BATTERIE_LOW;
    regs[REG_STATUT] = status;
    // R3: pH x100
    regs[REG_PH] = (uint16_t)(pH * 100 + 0.5);
    // R4: Conductivité
    regs[REG_CONDUCTIVITE] = (uint16_t)ec;
}

// ========================================
//  Setup
// ========================================

void setup() {
    // Watchdog 8 secondes
    wdt_enable(WDTO_8S);

    // Série debug
    Serial.begin(115200);
    Serial.println(F("[AgriCol] Nœud capteur sol démarré"));

    // Capteurs
    ds18b20.begin();

    // RS485
    pinMode(RS485_DE_RE_PIN, OUTPUT);
    digitalWrite(RS485_DE_RE_PIN, LOW);  // Réception

    // Modbus
    modbus.configure(NODE_ADDR);
    modbus.registerReadHoldingRegistersCallback(cbReadRegisters);
    modbus.registerWriteSingleCoilCallback(cbWriteCoil);
    modbus.begin(Serial1, 9600, RS485_DE_RE_PIN, RS485_DE_RE_PIN);
    // Serial1: TX=18, RX=19 sur Arduino Mega

    Serial.print(F("Adresse Modbus: "));
    Serial.println(NODE_ADDR);

    // Initialisation registres
    regs[REG_HUMIDITE] = 0;
    regs[REG_TEMPERATURE] = 0;
    regs[REG_STATUT] = 0;
    regs[REG_PH] = 700;   // 7.00
    regs[REG_CONDUCTIVITE] = 0;

    last_read = millis();
}

// ========================================
//  Loop
// ========================================

void loop() {
    wdt_reset();  // Reset watchdog

    // Traitement Modbus (non-bloquant)
    modbus.poll();

    // Lecture capteurs toutes les 5 secondes
    unsigned long now = millis();
    if (now - last_read >= SENSOR_READ_INTERVAL) {
        // Humidité sol
        humidity = readHumidity();
        Serial.print(F("Humidité: ")); Serial.print(humidity); Serial.println(F("%"));

        // Température sol
        ds18b20.requestTemperatures();
        temperature = ds18b20.getTempCByIndex(0);
        Serial.print(F("Température sol: ")); Serial.print(temperature); Serial.println(F("°C"));

        // pH
        // pH = readPH();
        // Serial.print(F("pH: ")); Serial.println(pH);

        // Batterie
        battery = readBattery();
        Serial.print(F("Batterie: ")); Serial.print(battery); Serial.println(F("V"));

        // Mise à jour registres
        updateRegisters();

        last_read = now;
    }
}
