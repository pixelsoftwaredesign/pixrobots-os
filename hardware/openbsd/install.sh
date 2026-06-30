#!/bin/sh
# AgriCol - Installation du serveur agricole OpenBSD
# À exécuter en root après installation minimale d'OpenBSD

set -e

echo "=== AgriCol - Installation serveur agricole OpenBSD ==="

# --- Paquets ---
echo "[+] Installation des paquets..."
pkg_add -u
pkg_add mosquitto node-red python py3-pip py3-serial py3-paho-mqtt
pkg_add sqlite3 influxdb chronograf
pkg_add relayd

# --- Services au démarrage ---
echo "[+] Activation des services..."
rcctl enable mosquitto
rcctl enable node_red
rcctl enable relayd
rcctl enable httpd

# --- Watchdog matériel (si disponible) ---
if sysctl -n hw.watchdog 2>/dev/null; then
    echo "watchdog_timeout=30" >> /etc/rc.conf.local
    echo "[+] Watchdog matériel activé (30s)"
else
    echo "[-] Pas de watchdog matériel détecté, utilisation de softdog"
    pkg_add softdog
    rcctl enable softdog
fi

# --- Création des utilisateurs ---
echo "[+] Création des utilisateurs système..."
useradd -m -s /sbin/nologin agricol_gw
useradd -m -s /sbin/nologin agricol_dash

# --- FTP sécurisé (transfert logs, photos drones) ---
echo "[+] Configuration FTP zones agricoles..."
sh ftp_setup.sh
cp ftpd.conf /etc/
# Ajouter FTP dans pf.conf
grep -q "ftp_port" /etc/pf.conf || cat >> /etc/pf.conf << 'PFE'
# FTP zone (ajouté par install.sh)
pass in on egress proto tcp from $local_net to ($ext_if) port 21 keep state
pass in on egress proto tcp from $local_net to ($ext_if) port >49151 keep state
PFE
pfctl -f /etc/pf.conf

# --- Python gateway daemon ---
echo "[+] Installation de la passerelle série->MQTT..."
mkdir -p /usr/local/libexec/agricol
cp serial_gateway.py /usr/local/libexec/agricol/
chmod +x /usr/local/libexec/agricol/serial_gateway.py
cp serial_gateway /etc/rc.d/
chmod +x /etc/rc.d/serial_gateway
rcctl enable serial_gateway

# --- Répertoires de données ---
echo "[+] Création des répertoires de données..."
mkdir -p /var/db/pixelos /var/db/agricol
chown _pixelos:_pixelos /var/db/pixelos
chown agricol_gw:agricol_gw /var/db/agricol

# --- httpd chroot + assets statiques ---
echo "[+] Configuration httpd reverse proxy..."
mkdir -p /var/www/htdocs/pixelos/static
cp -r /usr/local/lib/pixelos/web/templates /var/www/htdocs/pixelos/
cp -r /usr/local/lib/pixelos/web/static /var/www/htdocs/pixelos/
chown -R _pixelos:_pixelos /var/www/htdocs/pixelos
cp httpd.conf /etc/
cp relayd.conf /etc/
rcctl set httpd flags ""
rcctl set relayd flags "-f /etc/relayd.conf"

# --- Sécurité PF ---
echo "[+] Configuration du pare-feu..."
cp pf.conf /etc/pf.conf
pfctl -f /etc/pf.conf
pfctl -e
rcctl enable pf

# --- Redémarrage des services ---
echo "[+] Démarrage des services..."
rcctl start mosquitto
rcctl start serial_gateway
rcctl start node_red

echo "=== Installation terminée ==="
echo "Accès Node-RED: http://$(hostname):1880"
echo "Broker MQTT: tcp://$(hostname):1883"
echo "Watchdog: `sysctl -n hw.watchdog` secondes"
