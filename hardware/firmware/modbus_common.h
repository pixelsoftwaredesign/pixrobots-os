// AgriCol - Définitions Modbus communes à tous les nœuds
//
// Map registres (chaque nœud expose les registres suivants) :
//   R0  : Humidité sol x10 (0-1000 => 0.0%-100.0%)
//   R1  : Température x10 (-300-800 => -30.0°C-80.0°C)
//   R2  : Statut / alarmes (bits)
//          bit0: vanne ouverte
//          bit1: défaut capteur humidité
//          bit2: défaut capteur température
//          bit3: batterie faible
//   R3  : pH sol x100 (0-1400 => 0.00-14.00)
//   R4  : Conductivité électrique µS/cm (lecture directe)
//   R5  : Réservé

// Coils (sorties) :
//   C0  : Vanne ON/OFF (1=ouvrir, 0=fermer)
//   C1  : RESET nœud (1=reset)

#ifndef MODBUS_COMMON_H
#define MODBUS_COMMON_H

// --- Adresses Modbus ---
#define ADDR_NONE           0
#define ADDR_SOL_SERRE      10
#define ADDR_SOL_CHAMP      11
#define ADDR_SOL_VERGER     12
#define ADDR_SOL_JARDIN     13
#define ADDR_METEO          20
#define ADDR_ANEMOMETRE     21
#define ADDR_VANNE_SERRE    30
#define ADDR_VANNE_CHAMP    31
#define ADDR_VANNE_VERGER   32
#define ADDR_VANNE_JARDIN   33
#define ADDR_DEBIT_SERRE    40
#define ADDR_DEBIT_CHAMP    41
#define ADDR_PIR_SERRE      50
#define ADDR_PIR_CHAMP      51

// --- Registres ---
#define REG_HUMIDITE        0
#define REG_TEMPERATURE     1
#define REG_STATUT          2
#define REG_PH              3
#define REG_CONDUCTIVITE    4
#define REG_RESERVE1        5

// --- Bits statut ---
#define STATUT_VANNE_OPEN   (1 << 0)
#define STATUT_ERR_HUM      (1 << 1)
#define STATUT_ERR_TEMP     (1 << 2)
#define STATUT_BATTERIE_LOW (1 << 3)

// --- Coils ---
#define COIL_VANNE          0
#define COIL_RESET          1

// --- Config capteurs ---
#define HUM_MIN             0
#define HUM_MAX             1000      // 100.0%
#define TEMP_MIN            -300
#define TEMP_MAX            800
#define TEMP_SOL_THRESHOLD  400       // 40.0°C alerte

// --- Timing ---
#define MODBUS_SLAVE_TIMEOUT  50      // ms
#define SENSOR_READ_INTERVAL  5000    // ms
#define MQTT_PUBLISH_INTERVAL 30000   // ms

// --- Pins standard pour nœud capteur Arduino ---
#define PIN_HUMIDITE        A0        // Capteur humidité sol capacitif
#define PIN_PH              A1        // Module pH
#define PIN_CONDUCTIVITE    A2        // Module TDS/EC
#define PIN_TEMP_SOL        A3        // DS18B20 (OneWire sur pin digitale)
#define PIN_BATTERIE        A7        // Diviseur tension batterie

#define PIN_DHT22           2         // DHT22 température/humidité air
#define PIN_PLUVIOMETRE     3         // Pluviomètre à augets (interruption)
#define PIN_ANEMOMETRE      4         // Anémomètre (interruption)
#define PIN_LUMINOSITE      A6        // Photorésistance LDR

#define PIN_VANNE           9         // Relais vanne micro-irrigation
#define PIN_POMPE           10        // Relais pompe
#define PIN_PIR             11        // Détecteur mouvement PIR

#endif // MODBUS_COMMON_H
