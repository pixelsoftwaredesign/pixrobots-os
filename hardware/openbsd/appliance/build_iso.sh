#!/bin/sh
# ============================================================
# PixelOS Appliance Builder
# Multi-architecture: Apple Silicon (arm64), Intel (amd64), RPi (arm64)
# Usage: sh build_iso.sh [version] [arch]
#   arch: amd64 (Intel Mac/PC), arm64 (Apple Silicon M1-M4, RPi)
# ============================================================
set -e

VERSION="${1:-75}"
ARCH="${2:-amd64}"            # amd64 ou arm64 (Apple Silicon / RPi)
MIRROR="https://cdn.openbsd.org/pub/OpenBSD"
WORKDIR="/tmp/pixelos-build"

# Config par architecture
case "${ARCH}" in
    amd64)
        PKG_ARCH="amd64"
        BOOT_SECTOR="cdbr"
        ISO="install${VERSION}.iso"
        IMG="install${VERSION}.img"   # Mini-root pour Apple Silicon
        ;;
    arm64)
        PKG_ARCH="aarch64"
        BOOT_SECTOR=""
        ISO="install${VERSION}.img"   # OpenBSD arm64 utilise .img (pas ISO)
        ;;
    *)
        echo "❌ Architecture non supportée: ${ARCH} (amd64 ou arm64)"
        exit 1
esac

CUSTOM_IMAGE="pixelos-${VERSION}-${ARCH}.img"
SITE_TGZ="site${VERSION}.tgz"

echo "╔════════════════════════════════════════════╗"
echo "║     PixelOS Appliance Builder             ║"
echo "║     Version ${VERSION}  Architecture: ${ARCH}   ║"
echo "╚════════════════════════════════════════════╝"
echo "Sortie: ${CUSTOM_IMAGE}"
rm -rf "${WORKDIR}"
mkdir -p "${WORKDIR}/src" "${WORKDIR}/mnt" "${WORKDIR}/custom"

# --- 1. Télécharger l'image OpenBSD ---
echo "[1] Téléchargement de OpenBSD ${VERSION} (${ARCH})..."
cd "${WORKDIR}"
if [ "${ARCH}" = "arm64" ]; then
    # Pour Apple Silicon: miniroot + firmware
    if [ ! -f "${IMG}" ]; then
        ftp "${MIRROR}/${VERSION}/${ARCH}/miniroot${VERSION}.img"
    fi
    # Firmware Apple Silicon (obligatoire pour boot sur M1/M2/M3/M4)
    mkdir -p firmware
    cd firmware
    ftp "${MIRROR}/${VERSION}/${ARCH}/BOOT${ARCH}.EFI" 2>/dev/null || true
    ftp "${MIRROR}/${VERSION}/${ARCH}/bootaa64.efi" 2>/dev/null || true
    cd "${WORKDIR}"
else
    if [ ! -f "${ISO}" ]; then
        ftp "${MIRROR}/${VERSION}/${ARCH}/${ISO}"
    fi
fi

# --- 2. Monter et extraire ---
echo "[2] Extraction de l'image système..."
if [ "${ARCH}" = "arm64" ]; then
    # miniroot.img est une image disque, on la copie directement
    cp "${IMG}" "${CUSTOM_IMAGE}"
    # Monter pour ajouter les fichiers
    doas vnconfig vnd0 "${CUSTOM_IMAGE}"
    doas mount /dev/vnd0a "${WORKDIR}/mnt"
else
    doas vnconfig vnd0 "${ISO}"
    doas mount -t cd9660 /dev/vnd0a "${WORKDIR}/mnt"
    cp -r "${WORKDIR}/mnt" "${WORKDIR}/src"
    doas umount /dev/vnd0a
    doas vnconfig -u vnd0
fi

# --- 3. Ajouter siteXX.tgz (configuration PixelOS) ---
echo "[3] Création du site tgz..."
cd "${WORKDIR}/custom"

# install.site — exécuté après installation de base
cat > install.site << 'EOF'
#!/bin/sh
# PixelOS — Post-install automation (architecture auto-détectée)
echo "=== PixelOS Appliance — Configuration initiale ==="
ARCH=$(machine)
echo "Architecture détectée: ${ARCH}"

# Ajouter les dépôts
echo "https://cdn.openbsd.org/pub/OpenBSD" > /etc/installurl

# Afficher la Charte de Souveraineté
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     CHARTE DE SOUVERAINETÉ PixelOS                  ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Vous êtes seul responsable de votre nœud.          ║"
echo "║  La communauté PixelOS n'a aucun accès à vos        ║"
echo "║  données, clés privées ou infrastructure.           ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
printf "Accepter la Charte ? (oui/non) : "
read ACCEPT
if [ "${ACCEPT}" != "oui" ]; then
    echo "❌ Vous devez accepter la Charte pour installer PixelOS."
    echo "   Consultez: https://pixelos.org/legal"
    exit 1
fi
mkdir -p /var/db/pixelos
echo "{\"accepted\":true,\"accepted_at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
    > /var/db/pixelos/charter_accepted

# Installer les paquets essentiels
pkg_add -u
pkg_add python git mosquitto py3-pip py3-serial py3-paho-mqtt

# Installer PixelOS
pip3 install pixelos

# Générer l'identité du nœud
pixelos federation status 2>/dev/null || true

# Démarrer les services
rcctl enable mosquitto nsd
rcctl start mosquitto 2>/dev/null || true

# Auto-provisioning
if [ -f /etc/auto_provision.sh ]; then
    sh /etc/auto_provision.sh
fi

echo "=== PixelOS prêt ! ==="
echo "Console: http://<ip>:9999"
echo "Charte:  http://<ip>:9999/legal"
echo "Rejoindre: pixelos federation discover"
EOF
chmod +x install.site

# Auto-install config
cat > install.conf << 'CFG'
System hostname = pixelos
Which network interface = vio0
IPv4 address for vio0 = dhcp
IPv6 address for vio0 = none
Password for root = pixelos2024
Public ssh key for root =
Start sshd(8) by default = yes
Allow root ssh login = no
What timezone = UTC
Use disk geometry = whole
Set name(s) = +*
Location of sets = cd0
CFG

# Copier l'auto-provision dans l'image
cp "C:/Users/laa7a/Desktop/agricol/hardware/openbsd/appliance/auto_provision.sh" . 2>/dev/null || true

# Créer le siteXX.tgz
mkdir -p etc
cp install.site etc/
cp install.conf etc/
cp auto_provision.sh etc/ 2>/dev/null || true
tar czf "${SITE_TGZ}" etc/

# Copier dans la source
if [ "${ARCH}" = "arm64" ]; then
    doas cp "${SITE_TGZ}" "${WORKDIR}/mnt/${VERSION}/${ARCH}/"
else
    cp "${SITE_TGZ}" "${WORKDIR}/src/${VERSION}/${ARCH}/"
fi

# --- 4. Ajouter les fichiers PixelOS ---
echo "[4] Ajout des fichiers PixelOS..."
if [ "${ARCH}" = "arm64" ]; then
    # Sur l'image montée
    doas mkdir -p "${WORKDIR}/mnt/etc/pixelos"
    doas cp -r /etc/pixelos/* "${WORKDIR}/mnt/etc/pixelos/" 2>/dev/null || true
    doas umount "${WORKDIR}/mnt"
    doas vnconfig -u vnd0
else
    cp -r /etc/pixelos "${WORKDIR}/src/etc/" 2>/dev/null || true
    cp -r /var/nsd/zones "${WORKDIR}/src/var/nsd/" 2>/dev/null || true
fi

# --- 5. Reconstruire l'image ---
echo "[5] Création de l'image finale..."

if [ "${ARCH}" = "arm64" ]; then
    # L'image est déjà prête (miniroot modifiée)
    echo "Image Apple Silicon: ${WORKDIR}/${CUSTOM_IMAGE}"
else
    cd "${WORKDIR}/src"
    mkisofs -l -R -o "${WORKDIR}/${CUSTOM_IMAGE}" \
        -b ${VERSION}/${ARCH}/cdbr \
        -c boot.catalog \
        -no-emul-boot -boot-load-size 4 .
fi

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║     Image PixelOS prête !                 ║"
echo "╠════════════════════════════════════════════╣"
echo "║ Fichier : ${WORKDIR}/${CUSTOM_IMAGE}"
echo "║ Arch    : ${ARCH}"
echo "║ Taille  : $(du -h ${WORKDIR}/${CUSTOM_IMAGE} | cut -f1)"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "=== Instructions ==="
echo ""
if [ "${ARCH}" = "arm64" ]; then
    echo "🍏 Apple Silicon (M1/M2/M3/M4):"
    echo "  1. Copier sur une clé USB:"
    echo "     dd if=${CUSTOM_IMAGE} of=/dev/rdisk2 bs=1m"
    echo "  2. Démarrage: touche 'Option' au boot, choisir 'EFI Boot'"
    echo "  3. Ou Asahi Linux:"
    echo "     curl -sL https://alx.sh | sh"
    echo "     puis installer PixelOS dans la partition"
else
    echo "🖥️  Intel Mac / PC:"
    echo "  1. Copier sur une clé USB:"
    echo "     doas dd if=${CUSTOM_IMAGE} of=/dev/rsd0c bs=1M"
    echo "  2. Boot: touche 'Option' (Mac) ou F12 (PC)"
fi
echo ""
echo "  3. Connexion: ssh root@<ip>  (mot de passe: pixelos2024)"
echo "  4. Lancer:  pixelos federation discover"
echo "  5. Web:     http://<ip>:9999"
echo ""
