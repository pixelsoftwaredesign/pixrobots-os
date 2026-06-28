# AgriCol - Architecture Hardware & Embarqué

Système de contrôle d'irrigation agricole avec OpenBSD, ESP32, Arduino, RS485 et MQTT.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   OpenBSD Mini PC                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Mosquitto │  │Node-RED  │  │ C Gateway Daemon  │  │
│  │ (MQTT)   │  │(logique) │  │(RS485→MQTT)       │  │
│  │ :1883    │  │ :1880    │  │                    │  │
│  └─────┬────┘  └────┬─────┘  └─────────┬──────────┘  │
│        │            │                  │              │
│        └────────────┼──────────────────┘              │
│                     │                                 │
│         PF Firewall │ (blocage IoT → Internet)        │
│          Watchdog   │ (reset automatique 30s)         │
└─────────────────────┼─────────────────────────────────┘
                      │
          ┌───────────┼────────────┐
          │ RS485     │ Wi-Fi      │
          │ (filailre)│ (ESP32)    │
    ┌─────┴─────┐ ┌───┴────┐ ┌───┴────┐
    │Capteurs   │ │Vannes  │ │Station │
    │sol #10-13 │ │#30-33  │ │météo   │
    │Arduino    │ │ESP32   │ │ESP32   │
    │RS485      │ │RS485   │ │Wi-Fi   │
    └───────────┘ └────────┘ └────────┘
```

## Structure du dossier

```
hardware/
├── openbsd/                 # Configuration serveur OpenBSD
│   ├── install.sh           # Script installation automatique
│   ├── pf.conf              # Packet Filter (firewall)
│   ├── sysctl.conf          # Optimisations noyau
│   ├── dhcpd.conf           # DHCP pour réseau IoT
│   ├── serial_gateway.c     # Daemon C RS485 ↔ MQTT
│   ├── Makefile             # Build du daemon
│   └── nodes.conf           # Déclaration des nœuds Modbus
├── firmware/                # Code embarqué
│   ├── modbus_common.h      # Définitions partagées Modbus
│   ├── sensor_node/         # Nœud capteur sol (Arduino Mega)
│   ├── valve_node/          # Nœud vanne (ESP32)
│   ├── weather_station/     # Station météo (ESP32)
│   └── gateway/             # Pont RS485 ↔ Wi-Fi (ESP32)
├── nodered/                 # Flows Node-RED
│   └── flows.json           # Logique irrigation auto
└── network/                 # Plans réseau et câblage
    ├── topology.txt         # Topologie complète
    └── cabling.md           # Câblage détaillé
```

## Flux de données

### Chaîne normale (capteur → dashboard)
```
Capteur sol (RS485)
  → Gateway ESP32 RS485→Wi-Fi
    → Mosquitto MQTT
      → Node-RED (décision irrigation)
        → Mosquitto MQTT
          → Vanne ESP32 (commande)
      → Backend Spring Boot (stockage)
        → Dashboard Streamlit (affichage)
```

### Chaîne de secours (sans ESP32 gateway)
```
Capteur sol (RS485)
  → OpenBSD (USB-RS485, daemon C)
    → Mosquitto MQTT
      → ...
```

## Sécurité

| Couche | Mécanisme |
|--------|-----------|
| Réseau IoT | PF bloque tout accès Internet pour les capteurs |
| MQTT | Réseau dédié, pas d'authentification (confiance physique) |
| RS485 | Pas de sécurité, bus filaire isolé physiquement |
| Watchdog | Reset auto du serveur si gel (matériel + softdog) |
| Fail-safe | Vannes fermées par défaut, timeout 2 min sans commande |
| Batterie | Deep sleep ESP32 si < 3.5V |

## Déploiement rapide

### 1. OpenBSD
```sh
doas sh openbsd/install.sh
```

### 2. Daemon C RS485
```sh
cd openbsd && make && doas make install
doas rcctl start serial_gateway
```

### 3. Firmware ESP32/Arduino
Ouvrir les fichiers `.ino` dans Arduino IDE, configurer l'adresse Modbus,
et flasher via USB/UART.

### 4. Node-RED
Importer `nodered/flows.json` dans Node-RED (Admin UI → Import).

## Maintenance

```sh
# Voir les logs de la gateway
tail -f /var/log/daemon

# Statut des nœuds
mosquitto_sub -h localhost -t "agricol/#" -v

# Watchdog
sysctl hw.watchdog
```
