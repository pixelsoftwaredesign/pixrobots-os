#!/bin/sh
# PixelOS - Deploy static web assets into httpd chroot
# Synchronise les templates et statics Flask dans /var/www/htdocs/pixelos/
#
# Usage:
#   doas sh deploy-static.sh              # Sync depuis l'install standard
#   doas sh deploy-static.sh /mnt/usb     # Sync depuis un chemin personnalisé
#
# À exécuter après chaque mise à jour de PixelOS pour que httpd
# serve les dernières versions des assets statiques.

set -e

PIXELOS_SRC="${1:-/usr/local/lib/pixelos}"
CHROOT_HTDOCS="/var/www/htdocs/pixelos"
HTTPD_USER="_pixelos"

echo "=== PixelOS - Déploiement assets statiques ==="
echo "Source: ${PIXELOS_SRC}/web/"
echo "Cible:  ${CHROOT_HTDOCS}/"

if [ ! -d "${PIXELOS_SRC}/web" ]; then
    echo "[ERREUR] Source introuvable: ${PIXELOS_SRC}/web/"
    exit 1
fi

# Création des répertoires
mkdir -p "${CHROOT_HTDOCS}/static" "${CHROOT_HTDOCS}/templates"

# Synchronisation des templates
echo "[+] Templates..."
cp -r "${PIXELOS_SRC}/web/templates/" "${CHROOT_HTDOCS}/"
find "${CHROOT_HTDOCS}/templates" -type f -name '*.html' -exec chmod 644 {} \;

# Synchronisation des statics (CSS, JS, images)
if [ -d "${PIXELOS_SRC}/web/static" ]; then
    echo "[+] Static assets..."
    cp -r "${PIXELOS_SRC}/web/static/" "${CHROOT_HTDOCS}/"
fi

# Créer un favicon par défaut si absent
if [ ! -f "${CHROOT_HTDOCS}/favicon.ico" ]; then
    echo "[+] Favicon par défaut..."
    # Générer un SVG minimal
    cat > "${CHROOT_HTDOCS}/favicon.ico" << 'FAVICON'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="4" fill="#2e7d32"/>
  <text x="16" y="22" font-size="18" text-anchor="middle" fill="white" font-family="sans-serif">P</text>
</svg>
FAVICON
fi

# Permissions
chown -R "${HTTPD_USER}:${HTTPD_USER}" "${CHROOT_HTDOCS}/"
chmod -R 755 "${CHROOT_HTDOCS}/"

# Recharger httpd
if rcctl check httpd 2>/dev/null; then
    echo "[+] Rechargement httpd..."
    rcctl reload httpd
fi

echo "=== Déploiement terminé ==="
echo "Statiques: ${CHROOT_HTDOCS}/"
ls -la "${CHROOT_HTDOCS}/"
