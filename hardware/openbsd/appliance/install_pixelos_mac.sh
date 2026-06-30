#!/bin/bash
# ============================================================
# PixelOS — Installateur macOS
# Crée une clé USB bootable PixelOS pour Mac Intel & Apple Silicon
#
# Usage:
#   chmod +x install_pixelos_mac.sh
#   sudo ./install_pixelos_mac.sh
# ============================================================
set -e

VERSION="2.0"
ARCH=$(uname -m)  # x86_64 (Intel) ou arm64 (Apple Silicon)
PIXELOS_REPO="https://github.com/pixelsoftwaredesign/pixelos-agricol"
PIXELOS_DL="https://dl.pixelos.org/iso"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║     PixelOS Installateur macOS            ║"
echo "║     Réseau Mondial de Protection Agricole  ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# --- Vérification macOS ---
if [ "$(uname -s)" != "Darwin" ]; then
    echo -e "${RED}❌ Ce script est conçu pour macOS${NC}"
    echo "   Exécutez-le sur un Mac (Intel ou Apple Silicon)"
    exit 1
fi

# --- Vérification root ---
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Ce script doit être exécuté en root pour écrire sur le disque${NC}"
    echo "   sudo ./install_pixelos_mac.sh"
    exit 1
fi

echo -e "${GREEN}✅ macOS détecté: $(sw_vers -productVersion)${NC}"
echo -e "${GREEN}✅ Architecture: ${ARCH}${NC}"
echo ""

# --- Choix architecture cible ---
if [ "${ARCH}" = "arm64" ]; then
    echo "🍏 Apple Silicon détecté (M1/M2/M3/M4)"
    echo "   Vous pouvez installer:"
    echo "   1) PixelOS natif ARM64 (recommandé, via UTM ou Asahi)"
    echo "   2) PixelOS Intel via Rosetta 2 (VM UTM)"
    read -p "Choix [1/2] (défaut: 1): " TARGET_ARCH
    TARGET_ARCH="${TARGET_ARCH:-1}"
    if [ "${TARGET_ARCH}" = "1" ]; then
        IMG_ARCH="arm64"
        IMG_NAME="pixelos-latest-arm64.img"
    else
        IMG_ARCH="amd64"
        IMG_NAME="pixelos-latest-amd64.iso"
    fi
else
    IMG_ARCH="amd64"
    IMG_NAME="pixelos-latest-amd64.iso"
fi

echo ""
echo "=== Architecture cible: ${IMG_ARCH} ==="
echo ""

# --- Détection des disques ---
echo "💾 Disques disponibles:"
diskutil list internal physical | grep -E "^/dev/disk" || true
diskutil list external physical | grep -E "^/dev/disk" || true
echo ""
echo -e "${YELLOW}⚠️  ATTENTION: Le disque sélectionné sera EFFACÉ complètement${NC}"
echo ""
read -p "Entrez le numéro du disque (ex: 2 pour /dev/disk2): " DISK_NUM

DISK="/dev/disk${DISK_NUM}"
if [ ! -e "${DISK}" ]; then
    echo -e "${RED}❌ Disque ${DISK} introuvable${NC}"
    exit 1
fi

echo ""
echo -e "${RED}⚠️  Vous allez effacer ${DISK} pour installer PixelOS${NC}"
diskutil info "${DISK}" | grep -E "Device / Media Name|Disk Size|Volume Name"
echo ""
read -p "Confirmer? (tapez OUI en majuscules): " CONFIRM
if [ "${CONFIRM}" != "OUI" ]; then
    echo "Installation annulée."
    exit 0
fi

# --- Téléchargement de l'image ---
echo ""
echo "📥 Téléchargement de PixelOS ${VERSION} (${IMG_ARCH})..."
TMP_DIR=$(mktemp -d)
cd "${TMP_DIR}"

# Essayer plusieurs sources
DOWNLOADED=false

# Source 1: DL officiel
echo "   Source: ${PIXELOS_DL}/${IMG_NAME}"
curl -L -o "${IMG_NAME}" "${PIXELOS_DL}/${IMG_NAME}" --progress-bar && DOWNLOADED=true || true

# Source 2: GitHub releases
if [ "${DOWNLOADED}" = false ]; then
    echo "   Source: GitHub Releases"
    curl -L -o "${IMG_NAME}" \
        "${PIXELOS_REPO}/releases/download/v${VERSION}/${IMG_NAME}" \
        --progress-bar && DOWNLOADED=true || true
fi

# Source 3: Build depuis les sources (pixelos install)
if [ "${DOWNLOADED}" = false ]; then
    echo "   Build depuis les sources..."
    pip3 install pixelos 2>/dev/null || pip3 install git+${PIXELOS_REPO}.git
    echo "   Image à construire manuellement sur OpenBSD via build_iso.sh"
    echo "   Ou utiliser directement: pixelos install"
    pixelos install --target-dir "${TMP_DIR}" 2>/dev/null || true
    if [ -f "${TMP_DIR}/${IMG_NAME}" ]; then
        DOWNLOADED=true
    fi
fi

if [ "${DOWNLOADED}" = false ]; then
    echo -e "${RED}❌ Impossible de télécharger l'image PixelOS${NC}"
    echo "   Téléchargez-la manuellement depuis: ${PIXELOS_REPO}/releases"
    rm -rf "${TMP_DIR}"
    exit 1
fi

echo -e "${GREEN}✅ Image téléchargée: $(ls -lh ${IMG_NAME} | awk '{print $5}')${NC}"

# --- Écriture sur le disque ---
echo ""
echo "💿 Écriture de PixelOS sur ${DISK}..."
echo -e "${YELLOW}   Cela peut prendre plusieurs minutes...${NC}"

# Démonter le disque
diskutil unmountDisk "${DISK}" 2>/dev/null || true

# Écrire l'image
if [[ "${IMG_NAME}" == *.img ]]; then
    # Image Apple Silicon (miniroot)
    dd if="${IMG_NAME}" of="${DISK}" bs=1m status=progress
else
    # ISO Intel (convertir en image disque d'abord)
    dd if="${IMG_NAME}" of="${DISK}" bs=1m status=progress
fi

# Forcer l'écriture disque
sync
sleep 2

# Vérifier
diskutil eject "${DISK}" 2>/dev/null || true

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     ✅ Clé USB PixelOS prête !           ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo "=== Instructions de démarrage ==="
echo ""

if [ "${IMG_ARCH}" = "arm64" ]; then
    echo "🍏 Apple Silicon (M1/M2/M3/M4):"
    echo "  1. Insérer la clé USB dans le Mac"
    echo "  2. Éteindre le Mac"
    echo "  3. Maintenir le bouton POWER enfoncé jusqu'au menu 'Options de démarrage'"
    echo "  4. Choisir 'EFI Boot' (la clé USB PixelOS)"
    echo ""
    echo "   Alternative avec Asahi Linux:"
    echo "   https://asahilinux.org/ (pour dual-boot macOS + PixelOS)"
    echo ""
    echo "   Alternative avec UTM (VM):"
    echo "   https://mac.getutm.app/"
    echo "   Nouvelle VM → OpenBSD → Choisir l'image PixelOS"
else
    echo "🖥️  Intel Mac:"
    echo "  1. Insérer la clé USB"
    echo "  2. Redémarrer en maintenant la touche 'Option' (⌥)"
    echo "  3. Choisir la clé USB dans le menu de démarrage"
    echo ""
    echo "   Alternative avec VirtualBox:"
    echo "   Nouvelle VM → OpenBSD 64-bit → Choisir l'ISO PixelOS"
fi

echo ""
echo "=== Première connexion ==="
echo "  Une fois démarré:"
echo "  pixelos federation discover"
echo "  pixelos portal join --nickname \"Mon Mac\" --country \"FR\""
echo "  http://<ip>:9999 (interface web)"
echo ""

# Nettoyage
rm -rf "${TMP_DIR}"

echo "🌱 Bienvenue dans la communauté internationale PixelOS !"
