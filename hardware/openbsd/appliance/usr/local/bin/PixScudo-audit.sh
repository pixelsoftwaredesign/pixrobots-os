#!/bin/ksh
# PixScudo-audit.sh — Audit de sécurité Pixel OS
# À exécuter quotidiennement via cron (root)
# /var/cron/tabs/root: 0 3 * * * /usr/local/bin/PixScudo-audit.sh

LOG_FILE="/var/log/pixscudo.log"
MATRIX_WEBHOOK="${MATRIX_WEBHOOK_URL:-http://localhost:8008/_matrix/client/r0/rooms/!admin:matrix.pixelos/send/m.room.message?access_token=changeme}"
HOSTNAME=$(hostname)
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] === PixScudo Audit ===" >> "$LOG_FILE"

# 1. Vérification syspatch
PATCHES=$(syspatch -c 2>/dev/null)
if [ -n "$PATCHES" ]; then
    MSG="⚠️ [$HOSTNAME] PixScudo: ${PATCHES} disponible(s)"
    echo "$MSG" >> "$LOG_FILE"
    echo "$MSG"
    curl -s -X POST -H "Content-Type: application/json" \
        -d "{\"msgtype\":\"m.text\",\"body\":\"$MSG\"}" \
        "$MATRIX_WEBHOOK" 2>/dev/null || true
fi

# 2. Vérification intégrité paquets
pkg_check -q 2>/dev/null > /tmp/pixscudo_pkg.txt
if [ $? -ne 0 ]; then
    MSG="🚨 [$HOSTNAME] PixScudo: intégrité paquets compromise"
    echo "$MSG" >> "$LOG_FILE"
    echo "$MSG"
    curl -s -X POST -H "Content-Type: application/json" \
        -d "{\"msgtype\":\"m.text\",\"body\":\"$MSG\"}" \
        "$MATRIX_WEBHOOK" 2>/dev/null || true
fi

# 3. Vérification ports inattendus
PORTS=$(netstat -ln -f inet | grep LISTEN | awk '{print $4}' | grep -oE '[0-9]+$' | sort -n | tr '\n' ' ')
UNEXPECTED=""
for p in $PORTS; do
    case $p in
        22|80|443|8448|9999|21|51820|6167|5300|1883) ;;
        *) UNEXPECTED="$UNEXPECTED $p" ;;
    esac
done
if [ -n "$UNEXPECTED" ]; then
    MSG="⚠️ [$HOSTNAME] PixScudo: ports inattendus détectés:${UNEXPECTED}"
    echo "$MSG" >> "$LOG_FILE"
    echo "$MSG"
    curl -s -X POST -H "Content-Type: application/json" \
        -d "{\"msgtype\":\"m.text\",\"body\":\"$MSG\"}" \
        "$MATRIX_WEBHOOK" 2>/dev/null || true
fi

# 4. Vérification SSH
if grep -q '^PermitRootLogin yes' /etc/ssh/sshd_config 2>/dev/null; then
    MSG="🚨 [$HOSTNAME] PixScudo: SSH PermitRootLogin activé"
    echo "$MSG" >> "$LOG_FILE"
    echo "$MSG"
    curl -s -X POST -H "Content-Type: application/json" \
        -d "{\"msgtype\":\"m.text\",\"body\":\"$MSG\"}" \
        "$MATRIX_WEBHOOK" 2>/dev/null || true
fi

echo "[$DATE] === Fin audit ===" >> "$LOG_FILE"
exit 0
