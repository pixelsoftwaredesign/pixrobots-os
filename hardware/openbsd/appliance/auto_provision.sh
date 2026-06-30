#!/bin/ksh
# ============================================================
# PixelOS Auto-Provisioning — Premier démarrage d'un nœud
# Exécuté automatiquement au premier boot par rc.firsttime
# ============================================================
set -e

NODE_ID_FILE="/var/db/pixelos/node_id"
CONFIG_FILE="/etc/pixelos/pixelos.yaml"
LOG="/var/log/pixelos-provision.log"

echo "=== PixelOS Auto-Provisioning ===" > "${LOG}"
echo "Démarrage: $(date)" >> "${LOG}"

# --- 1. Afficher la Charte de Souveraineté ---
CHARTER_FILE="/etc/pixelos/charter.txt"
CHARTER_ACCEPTED="/var/db/pixelos/charter_accepted"

if [ ! -f "${CHARTER_FILE}" ]; then
    cat > "${CHARTER_FILE}" << 'CHARTER'
╔══════════════════════════════════════════════════════════════╗
║            CHARTE DE SOUVERAINETÉ PixelOS                    ║
╚══════════════════════════════════════════════════════════════╝

En installant PixelOS, vous reconnaissez que vous êtes l'unique
administrateur de votre serveur. Vous êtes seul responsable :
  • Du contenu hébergé sur votre nœud
  • Des transactions BITROOT effectuées via votre Wallet
  • Des communications échangées via votre serveur Matrix
  • De la conformité avec les lois de votre juridiction

La communauté PixelOS fournit des outils techniques (logiciel libre)
et ne possède aucun accès à votre infrastructure, vos clés privées
ou vos données.

Voir la Charte complète : https://pixelos.org/legal
CHARTER
fi

if [ ! -f "${CHARTER_ACCEPTED}" ]; then
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
    if [ "${ACCEPT}" = "oui" ]; then
        echo "{\"accepted\":true,\"accepted_at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > "${CHARTER_ACCEPTED}"
        echo "Charte acceptée." | tee -a "${LOG}"
    else
        echo "❌ Vous devez accepter la Charte pour utiliser PixelOS."
        echo "   Consultez la version complète: https://pixelos.org/legal"
        exit 1
    fi
fi

# --- 2. Générer l'identité unique du nœud ---
if [ ! -f "${NODE_ID_FILE}" ]; then
    echo "[2] Génération de l'identité du nœud..." | tee -a "${LOG}"

    # ID unique basé sur MAC + random
    MAC=$(ifconfig vio0 | grep lladdr | awk '{print $2}')
    RAND=$(openssl rand -hex 8)
    NODE_ID=$(echo -n "${MAC}${RAND}" | sha256 | cut -c1-16)

    echo "${NODE_ID}" > "${NODE_ID_FILE}"
    echo "Node ID: ${NODE_ID}" >> "${LOG}"

    # Générer les clés Ed25519 pour la fédération
    openssl genpkey -algorithm ed25519 -out /var/db/pixelos/identity.key 2>/dev/null
    openssl pkey -in /var/db/pixelos/identity.key -pubout \
        -out /var/db/pixelos/identity.pub 2>/dev/null
    echo "Clés fédération générées" >> "${LOG}"
fi

NODE_ID=$(cat "${NODE_ID_FILE}")

# --- 3. Configurer le réseau ---
echo "[3] Configuration réseau..." | tee -a "${LOG}"

# Détecter l'interface principale
IFACE=$(ifconfig | grep -E '^[a-z]' | grep -v lo | head -1 | cut -d: -f1)
echo "Interface: ${IFACE}" >> "${LOG}"

# Configurer hostname
echo "pixelos-${NODE_ID}" > /etc/myname
hostname "pixelos-${NODE_ID}"

# --- 4. Initialiser le DNS local ---
echo "[4] Configuration DNS..." | tee -a "${LOG}"

cat >> /etc/hosts << EOF
127.0.0.1    localhost pixelos-${NODE_ID} pixelos.pxl
::1          localhost
EOF

# Configurer résolveur DNS
cat > /etc/resolv.conf << EOF
nameserver 127.0.0.1
lookup file bind
EOF

# --- 5. Générer la configuration WireGuard ---
echo "[5] Configuration WireGuard..." | tee -a "${LOG}"

WG_DIR="/etc/wireguard"
mkdir -p "${WG_DIR}"

# Générer les clés WireGuard
wg genkey > "${WG_DIR}/private.key" 2>/dev/null
wg pubkey < "${WG_DIR}/private.key" > "${WG_DIR}/public.key" 2>/dev/null
chmod 600 "${WG_DIR}/private.key"

# --- 6. Démarrer les services essentiels ---
echo "[6] Démarrage des services..." | tee -a "${LOG}"

# Démarrer NSD (DNS .pixel)
if [ -f /etc/nsd.conf ]; then
    rcctl enable nsd
    rcctl start nsd
    echo "NSD démarré" >> "${LOG}"
fi

# Démarrer Mosquitto (MQTT local)
rcctl enable mosquitto
rcctl start mosquitto 2>/dev/null || true
echo "Mosquitto démarré" >> "${LOG}"

# Démarrer le service PixelOS Web
if [ -f /usr/local/bin/pixelos ]; then
    pixelos web --port 9999 &
    echo "PixelOS Web démarré sur :9999" >> "${LOG}"
fi

# --- 7. Enregistrement auprès de l'Association ---
echo "[7] Enregistrement communauté..." | tee -a "${LOG}"

# Récupérer le nickname depuis l'utilisateur
if [ -f /root/.pixelos_nickname ]; then
    NICKNAME=$(cat /root/.pixelos_nickname)
else
    NICKNAME="Node-${NODE_ID}"
fi

# Tenter de rejoindre la fédération
PUBKEY=$(cat "${WG_DIR}/public.key" 2>/dev/null || echo "")
pixelos federation gov-register --name "${NICKNAME}" \
    --country "$(hostname -s | cut -d- -f2-)" \
    2>/dev/null || true

# --- 8. Lancer le daemon IPFS ---
if command -v ipfs >/dev/null 2>&1; then
    echo "[8] Démarrage IPFS..." | tee -a "${LOG}"
    pixelos ipfs init 2>/dev/null || true
    pixelos ipfs start 2>/dev/null || true
fi

# --- 9. Notification au réseau ---
echo "[9] Annonce au réseau fédéré..." | tee -a "${LOG}"

# Scanne les pairs WireGuard sur le réseau local
pixelos federation discover 2>/dev/null || true
pixelos federation announce 2>/dev/null || true

# --- 10. Nettoyage et finalisation ---
echo "[10] Finalisation..." | tee -a "${LOG}"

# Marquer le provisioning comme terminé
touch /var/db/pixelos/provisioned
echo "Provisioning terminé: $(date)" >> "${LOG}"

# Afficher le résumé
echo ""
echo "╔════════════════════════════════════════════╗"
echo "║     PixelOS — Nœud prêt !                 ║"
echo "╠════════════════════════════════════════════╣"
echo "║ Node ID : ${NODE_ID}"
echo "║ Hostname: pixelos-${NODE_ID}"
echo "║ Console : http://pixelos-${NODE_ID}.pxl:9999"
echo "║ SSH     : ssh root@pixelos-${NODE_ID}.pxl"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "Interface web: http://$(ifconfig ${IFACE} | grep inet | head -1 | awk '{print $2}'):9999"
