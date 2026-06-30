# PixelOS Installer - Clé USB bootable OFFLINE

## Principe

La clé USB contient **TOUT** le nécessaire : OpenBSD + PixelOS + toutes les
dépendances. **Aucune connexion internet** n'est nécessaire sur le mini PC.

## Construction (1ère étape : sur une machine connectée)

```sh
# 1. Cloner le dépôt
git clone https://github.com/pixelsoftwaredesign/pixelos-agricol.git
cd pixelos-agricol/hardware/installer

# 2. Installer les prérequis (sur OpenBSD)
doas pkg_add rsync-- curl

# 3. TOUT pré-télécharger : sets + paquets + pip ~15 min
make prepare

# 4. Graver la clé USB offline
#    (VÉRIFIER d'abord que USB_DEV n'est PAS sd0 !)
dmesg | grep sd
doas make offline-usb USB_DEV=sd2
```

La clé est prête. Elle contient :

```
/ (racine)
├── install.conf           # Réponses auto-install
├── 76/
│   ├── SHA256.sig
│   ├── base76.tgz         # OpenBSD base system
│   ├── comp76.tgz         # Compilateur
│   ├── man76.tgz          # Manuels
│   └── site76.tgz         # PixelOS (sources + scripts + configs)
├── packages/              # Tous les .tgz OpenBSD
├── pip_packages/          # Tous les .whl Python
└── requirements.txt
```

## Installation sur le mini PC (2ème étape : sans internet)

1. Brancher la clé USB sur le mini PC
2. Booter sur la clé (F12/F2 pour le boot menu)
3. À l'invite `boot>`, taper :

```
boot> install -a -f install.conf
```

**Tout est automatique** : partitionnement, extraction des sets, installation
des paquets, compilation du daemon série, copie des sources PixelOS,
configuration du firewall, activation des services.

## Après installation

```sh
# Connexion SSH
ssh root@agricol-server

# État du système
pixelos status

# Web UI
http://agricol-server:9999

# Node-RED
http://agricol-server:1880

# MQTT
mosquitto_sub -h agricol-server -t "pixelos/#" -v
```

## Structure du projet

```
hardware/installer/
├── Makefile                # make prepare / make offline-usb / make clean
├── install.conf            # Réponses automatiques pour l'installeur OpenBSD
├── install.sh              # Script de provisioning (s'exécute après install)
├── requirements.txt        # Dépendances Python
├── packages-list.txt       # Liste des paquets OpenBSD requis
├── configs/                # Fichiers de configuration
│   ├── pf.conf             # Firewall (bloque IoT, autorise admin)
│   ├── dhcpd.conf          # DHCP pour réseau IoT (10.0.100.0/24)
│   ├── nodes.conf          # 18 nœuds Modbus (capteurs + vannes)
│   ├── sysctl.conf         # Optimisations réseau
│   ├── pixelos.yaml        # Configuration PixelOS
│   └── rc.conf.local       # Services au démarrage
├── src/
│   ├── serial_gateway.c    # Daemon C RS485 ↔ MQTT (348 lignes)
│   ├── Makefile.serial     # Build du daemon
│   └── rc.d/               # Services OpenBSD
│       ├── serial_gateway
│       ├── pixelos_agent
│       └── pixelos_web
└── README-installer.md
```
