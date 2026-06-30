#!/bin/sh
# PixelOS - Provisioning complet du serveur agricole OpenBSD
# Version OFFLINE : tous les paquets sont lus depuis le support d'installation.
#
# Ce script s'exécute automatiquement via siteXX.tgz après installation
# minimale d'OpenBSD, OU manuellement :
#   doas sh /mnt/pixelos/install.sh

set -e

VERBOSE=${VERBOSE:-1}
log() { [ "$VERBOSE" = "1" ] && echo "$@"; }

# Détection automatique du point de montage du support d'install
if [ -d /mnt/76 ] && [ -f /mnt/install.conf ]; then
    MEDIA="/mnt"
elif [ -d /mnt/pixelos ] && [ -f /mnt/install.sh ]; then
    MEDIA="/mnt"
elif [ -d /media/76 ]; then
    MEDIA="/media"
elif [ -d /tmp/install ]; then
    MEDIA="/tmp/install"
else
    MEDIA="/mnt"
fi

log "=== Support d'installation détecté: ${MEDIA} ==="

PACKAGES_DIR="${MEDIA}/packages"
PIP_DIR="${MEDIA}/pip_packages"
REQUIREMENTS="${MEDIA}/requirements.txt"
CONFIGS="${MEDIA}/configs"
SERIAL_SRC="${MEDIA}/src"
PIXELOS_SRC="${MEDIA}/pixelos"
ROOT_SRC="${MEDIA}/pixelos"
SYSUSER="_pixelos"
GWUSER="_pixelos_gw"

# ── 1. Paquets OpenBSD ────────────────────────────────────
log "=== [1/10] Installation des paquets OpenBSD (offline) ==="
if [ -d "${PACKAGES_DIR}" ]; then
    pkg_add -D local "${PACKAGES_DIR}"/*.tgz 2>&1 || \
    for pkg in "${PACKAGES_DIR}"/*.tgz; do
        pkg_add -D local "$pkg" 2>/dev/null || log "  Déjà installé: $(basename $pkg)"
    done
else
    log "  [AVERTISSEMENT] Dossier paquets introuvable: ${PACKAGES_DIR}"
    log "  Tentative installation depuis miroir (nécessite internet)..."
    pkg_add mosquitto node-red python py3-pip py3-serial py3-paho-mqtt
    pkg_add influxdb rsync-- git--
fi

# ── 2. Paquets Python ─────────────────────────────────────
log "=== [2/10] Installation des paquets Python (offline) ==="
if [ -d "${PIP_DIR}" ] && [ -f "${REQUIREMENTS}" ]; then
    pip3 install --no-index --find-links "${PIP_DIR}" \
        -r "${REQUIREMENTS}" 2>&1 || \
    log "  [AVERTISSEMENT] Certains paquets Python n'ont pas pu être installés"
elif [ -d "${PIP_DIR}" ]; then
    pip3 install --no-index --find-links "${PIP_DIR}" \
        structlog paho-mqtt pyyaml numpy scikit-learn scipy \
        onnx onnxruntime skl2onnx flask opencv-python-headless \
        psutil biopython h5py mysql-connector-python pymongo \
        psycopg2-binary pandas plotly streamlit requests 2>&1 || true
else
    log "  [AVERTISSEMENT] Dossier pip introuvable, installation via réseau..."
    pip3 install structlog paho-mqtt pyyaml numpy scikit-learn scipy \
        onnx onnxruntime skl2onnx flask opencv-python-headless \
        psutil biopython h5py mysql-connector-python pymongo \
        psycopg2-binary pandas plotly streamlit requests 2>&1 || true
fi

# ── 3. Utilisateurs système ────────────────────────────────
log "=== [3/10] Création utilisateurs ==="
if ! getent passwd ${SYSUSER} >/dev/null 2>&1; then
    useradd -m -s /sbin/nologin ${SYSUSER}
fi
if ! getent passwd ${GWUSER} >/dev/null 2>&1; then
    useradd -m -s /sbin/nologin ${GWUSER}
fi

# ── 4. Répertoires PixelOS ─────────────────────────────────
log "=== [4/10] Installation des sources PixelOS ==="
mkdir -p /usr/local/libexec/pixelos
mkdir -p /etc/pixelos
mkdir -p /var/db/pixelos/data
mkdir -p /var/log/pixelos

if [ -d "${PIXELOS_SRC}/core" ]; then
    cp -r ${PIXELOS_SRC}/core /usr/local/libexec/pixelos/
    cp -r ${PIXELOS_SRC}/ml /usr/local/libexec/pixelos/ 2>/dev/null || true
    cp -r ${PIXELOS_SRC}/agent /usr/local/libexec/pixelos/ 2>/dev/null || true
    cp -r ${PIXELOS_SRC}/web /usr/local/libexec/pixelos/ 2>/dev/null || true
    cp -r ${PIXELOS_SRC}/cli /usr/local/libexec/pixelos/ 2>/dev/null || true
    for tdir in ${PIXELOS_SRC}/web/templates ${PIXELOS_SRC}/dashboard; do
        [ -d "$tdir" ] && cp -r "$tdir" /usr/local/libexec/pixelos/ 2>/dev/null || true
    done
    ln -sf /usr/local/libexec/pixelos/cli/main.py /usr/local/bin/pixelos
    chmod +x /usr/local/bin/pixelos
else
    log "  [AVERTISSEMENT] Sources PixelOS introuvables dans ${PIXELOS_SRC}"
    log "  Copie depuis structure locale..."
    find ${MEDIA} -name "core" -type d -exec cp -r {} /usr/local/libexec/pixelos/ \; 2>/dev/null || true
fi

# ── 5. httpd reverse proxy + static assets ──────────────────
log "=== [5/10] Configuration httpd reverse proxy ==="
if [ -d /var/www ]; then
    mkdir -p /var/www/htdocs/pixelos/static /var/www/htdocs/pixelos/templates
    if [ -d /usr/local/libexec/pixelos/web/templates ]; then
        cp -r /usr/local/libexec/pixelos/web/templates/* /var/www/htdocs/pixelos/templates/ 2>/dev/null || true
    fi
    if [ -d "${CONFIGS}/../openbsd" ]; then
        cp "${CONFIGS}/../openbsd/httpd.conf" /etc/ 2>/dev/null && log "  httpd.conf → /etc/"
        cp "${CONFIGS}/../openbsd/relayd.conf" /etc/ 2>/dev/null && log "  relayd.conf → /etc/"
    fi
    chown -R ${SYSUSER}:${SYSUSER} /var/www/htdocs/pixelos 2>/dev/null || true
    log "  httpd prêt (port 80 → Flask 9999)"
else
    log "  [AVERTISSEMENT] /var/www introuvable, httpd non configuré"
fi

# ── 6. Compilation daemon série ────────────────────────────
log "=== [5/10] Compilation daemon série RS485 ==="
if [ -f "${SERIAL_SRC}/serial_gateway.c" ]; then
    cc -Wall -Wextra -O2 -std=c99 \
       -o /usr/local/libexec/pixelos/serial_gateway \
       "${SERIAL_SRC}/serial_gateway.c" -lpaho-mqtt3c 2>/dev/null && \
    strip /usr/local/libexec/pixelos/serial_gateway && \
    log "  Compilation OK" || \
    log "  [AVERTISSEMENT] Échec compilation (libpaho-mqtt3c manquante ?)"
else
    log "  Source serial_gateway.c non trouvée, ignoré"
fi

# ── 7. Fichiers de configuration ──────────────────────────
log "=== [7/10] Installation des configurations ==="
for cfg in pf.conf sysctl.conf dhcpd.conf nodes.conf pixelos.yaml; do
    src="${CONFIGS}/${cfg}"
    case "$cfg" in
        pf.conf)     dst="/etc/pf.conf" ;;
        sysctl.conf) dst="/etc/sysctl.conf" ;;
        dhcpd.conf)  dst="/etc/dhcpd.conf" ;;
        nodes.conf)  dst="/etc/pixelos/nodes.conf" ;;
        pixelos.yaml) dst="/etc/pixelos/pixelos.yaml" ;;
    esac
    if [ -f "$src" ]; then
        cp "$src" "$dst" && log "  $cfg → $dst"
    fi
done

pfctl -f /etc/pf.conf 2>/dev/null || true
pfctl -e 2>/dev/null || true

# rc.conf.local additions
if [ -f "${CONFIGS}/rc.conf.local" ]; then
    cat "${CONFIGS}/rc.conf.local" >> /etc/rc.conf.local 2>/dev/null || true
fi

# ── 8. Services rc.d ──────────────────────────────────────
log "=== [8/10] Installation des services rc.d ==="
for svc in serial_gateway pixelos_agent pixelos_web; do
    src="${SERIAL_SRC}/rc.d/${svc}"
    if [ -f "$src" ]; then
        cp "$src" "/etc/rc.d/${svc}"
        chmod 555 "/etc/rc.d/${svc}"
        log "  /etc/rc.d/${svc} installé"
    fi
done

# ── 9. Watchdog ────────────────────────────────────────────
log "=== [9/10] Configuration watchdog ==="
if sysctl -n hw.watchdog 2>/dev/null; then
    echo "watchdog_timeout=30" >> /etc/rc.conf.local
    log "  Watchdog matériel activé (30s)"
else
    log "  Pas de watchdog matériel"
fi

# ── 10. Permissions ───────────────────────────────────────
log "=== [10/10] Permissions ==="
chown -R ${SYSUSER}:${SYSUSER} /usr/local/libexec/pixelos 2>/dev/null || true
chown -R ${SYSUSER}:${SYSUSER} /var/db/pixelos 2>/dev/null || true
chown -R ${SYSUSER}:${SYSUSER} /var/log/pixelos 2>/dev/null || true
chown -R ${GWUSER}:${GWUSER} /etc/pixelos 2>/dev/null || true
chmod +x /usr/local/libexec/pixelos/serial_gateway 2>/dev/null || true

# ── 11. Activation et démarrage ───────────────────────────
log "=== [11/10] Activation des services ==="
for svc in mosquitto serial_gateway pixelos_agent pixelos_web; do
    rcctl enable ${svc} 2>/dev/null || true
done

# Démarrer les services (sauf si en chroot d'install)
if [ -x /sbin/init ] && [ "$(stat -f %d /)" != "$(stat -f %d /mnt 2>/dev/null)" ]; then
    for svc in mosquitto serial_gateway pixelos_agent pixelos_web; do
        rcctl start ${svc} 2>/dev/null || true
    done
fi

# ── Résumé ─────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║        PixelOS - Installation terminée      ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Web UI:      http://agricol-server (port 80 via httpd)"
echo "  Web UI TLS:  https://agricol-server (via relayd)"
echo "  Web direct:  http://agricol-server:9999 (Flask, contourne httpd)"
echo "  MQTT:        tcp://agricol-server:1883"
echo "  Node-RED:    http://agricol-server:1880"
echo "  CLI:         pixelos status"
echo "  Logs:        tail -f /var/log/pixelos/*.log"
echo "  Watchdog:    $(sysctl -n hw.watchdog 2>/dev/null || echo 'N/A')s"
echo ""

logger -t pixelos "Installation terminée (offline)"

exit 0
