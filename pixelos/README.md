# PixelOS - Système de Gestion Agricole Connecté

PixelOS est le système d'exploitation de gestion complet pour l'infrastructure AgriCol.
Il fédère l'ensemble des composants : serveur OpenBSD, backend Spring Boot, agents edge
Raspberry Pi, nœuds ESP32/Arduino, dashboard Streamlit, broker MQTT, bases de données.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     PIXELOS MANAGEMENT LAYER                    │
│                                                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ pixelos  │  │ pixelos  │  │ pixelos  │  │ pixelos-web   │  │
│  │ -cli     │  │ -agent   │  │ -monitor │  │ (Web UI :9999)│  │
│  │ (term.)  │  │ (daemon) │  │ (health) │  └───────────────┘  │
│  └──────────┘  └──────────┘  └──────────┘                     │
│       │              │              │                          │
│       └──────────────┴──────────────┘                          │
│                        │                                       │
│             ┌──────────┴──────────┐                            │
│             │   pixelos-core      │                            │
│             │  (MQTT, SSH, DB,    │                            │
│             │   OTA, config)      │                            │
│             └──────────┬──────────┘                            │
└────────────────────────┼───────────────────────────────────────┘
                         │
     ┌───────────────────┼────────────────────┐
     │                   │                    │
  ┌──┴──┐           ┌────┴────┐         ┌────┴────┐
  │Plan │           │Ferme    │         │Cloud    │
  │OpenBSD│          │RPi/Edge │         │Backend  │
  │serveur│          │agent    │         │Spring   │
  └──────┘           └─────────┘         └─────────┘
```

## Commandes CLI

```bash
# État du système
pixelos status                    # État global de tous les composants
pixelos status --node serre       # État d'un nœud spécifique
pixelos status --mqtt             # Santé du broker MQTT

# Gestion des nœuds
pixelos node list                 # Lister tous les nœuds
pixelos node add --addr 13 --type sol --nom jardin
pixelos node remove 13
pixelos node config 10 --hum-seuil 35 --hysteresis 5

# Irrigation
pixelos irrigate status           # État irrigation toutes zones
pixelos irrigate open serre       # Ouvrir vanne manuellement
pixelos irrigate close serre      # Fermer vanne
pixelos irrigate schedule         # Voir planning
pixelos irrigate schedule --zone serre --heure 06:00 --duree 30

# Firmware (OTA)
pixelos firmware list             # Versions firmware des nœuds
pixelos firmware build sensor     # Compiler firmware capteur
pixelos firmware flash --all      # Mettre à jour tous les nœuds
pixelos firmware flash 10         # Mettre à jour le nœud 10

# Monitoring
pixelos monitor health            # Santé complète du système
pixelos monitor logs --tail 50    # Logs centralisés
pixelos monitor alerts            # Alertes actives
pixelos monitor metrics           # Métriques en direct
pixelos monitor dashboard         # Ouvrir le dashboard web

# Maintenance
pixelos backup                    # Backup complet (config + DB)
pixelos backup --list             # Lister les backups
pixelos restore latest            # Restaurer dernier backup
pixelos update                    # Mettre à jour PixelOS
pixelos update --check            # Vérifier mises à jour disponibles

# Configuration
pixelos config show               # Afficher configuration
pixelos config set mqtt.port 1883 # Modifier un paramètre
pixelos config sync               # Synchroniser config vers tous les nœuds
```

## Installation

```bash
# Sur OpenBSD (serveur principal)
curl -sS https://pixelos.agricol.local/install.sh | doas sh

# Ou depuis les sources
git clone https://github.com/agricol/pixelos
cd pixelos
doas pip install -e .
doas pixelos setup
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| pixelos-web | 9999 | Interface d'administration web |
| pixelos-agent | - | Agent node (chaque machine) |
| pixelos-mqtt | 1883 | Broker MQTT (via Mosquitto) |
| pixelos-api | 8080 | API REST Spring Boot |
| pixelos-db | 3306/27017 | MySQL + MongoDB |
