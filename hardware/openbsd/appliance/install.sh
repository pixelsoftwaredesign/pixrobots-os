#!/bin/ksh
# ============================================================
# Installation PixelOS pour la communauté
# Usage: ftp -o - https://pixelos.org/install.sh | sh
# ============================================================
set -e

VERSION="2.0"
RELEASE_URL="https://github.com/pixelsoftwaredesign/pixelos-agricol/releases"

echo "╔════════════════════════════════════════════╗"
echo "║     PixelOS ${VERSION} — Installation Communauté   ║"
echo "║     Réseau Mondial de Protection Agricole  ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# --- Vérification OS ---
if [ "$(uname -s)" != "OpenBSD" ]; then
    echo "⚠️  Ce script est conçu pour OpenBSD."
    echo "   Vous pouvez aussi utiliser l'ISO PixelOS Appliance."
    echo "   Téléchargement: ${RELEASE_URL}"
    exit 1
fi

# --- Vérification root ---
if [ "$(id -u)" -ne 0 ]; then
    echo "❌ Ce script doit être exécuté en root."
    echo "   sudo sh install.sh"
    exit 1
fi

echo "[1] Configuration du système..."
# Ajouter les dépôts
echo "https://cdn.openbsd.org/pub/OpenBSD" > /etc/installurl

echo "[2] Installation des paquets..."
pkg_add -u 2>/dev/null || true
pkg_add python git mosquitto py3-pip py3-serial py3-paho-mqtt 2>/dev/null || true

echo "[3] Installation de PixelOS..."
pip3 install pixelos 2>/dev/null || {
    echo "   Installation depuis GitHub..."
    cd /tmp
    ftp -o pixelos.tar.gz "${RELEASE_URL}/download/v${VERSION}/pixelos-${VERSION}.tar.gz"
    pip3 install pixelos.tar.gz
    rm pixelos.tar.gz
}

echo "[4] Configuration initiale..."
# Créer les répertoires
mkdir -p /var/db/pixelos /etc/pixelos

# Générer l'identité
pixelos federation status 2>/dev/null || true

echo "[5] Configuration du réseau fédéré..."
# Enregistrer le nœud
read -p "Entrez votre surnom (ex: FermeBioMaroc): " NICKNAME
read -p "Entrez votre pays (code ISO, ex: MA): " COUNTRY

pixelos portal register-seed --nickname "${NICKNAME}" --country "${COUNTRY}"
pixelos federation gov-register --name "${NICKNAME}" --country "${COUNTRY}"

echo "[6] Démarrage des services..."
pixelos ipfs init 2>/dev/null || true
pixelos ipfs start 2>/dev/null || true

# Activer le service web
echo "python3 -m pixelos.web" >> /etc/rc.local

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║     PixelOS — Installation terminée !     ║"
echo "╠════════════════════════════════════════════╣"
echo "║ Console : http://$(ifconfig vio0 | grep inet | awk '{print $2}'):9999"
echo "║ SSH     : ssh root@$(hostname)"
echo "║ Rejoindre: pixelos federation discover"
echo "║ Aide    : pixelos --help"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "🌱 Bienvenue dans la communauté internationale PixelOS !"
