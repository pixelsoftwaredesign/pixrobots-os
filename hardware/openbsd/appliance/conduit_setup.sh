#!/bin/ksh
# ============================================================
# Conduit Matrix Server — Installation sur OpenBSD
# Serveur de communication décentralisé pour PixelOS
# Architecture: résilient, léger (Rust), fédération WireGuard
# ============================================================
set -e

VERSION="0.8.0"
CONDUIT_USER="_conduit"
CONDUIT_DIR="/var/conduit"
CONDUIT_PORT="6167"
FEDERATION_PORT="8448"
DB_DIR="${CONDUIT_DIR}/database"

echo "╔════════════════════════════════════════════╗"
echo "║  PixelOS — Installation Conduit ${VERSION}      ║"
echo "║  Serveur Matrix décentralisé               ║"
echo "╚════════════════════════════════════════════╝"

# ── Vérifications ──
if [ "$(id -u)" -ne 0 ]; then
    echo "❌ Root requis" >&2; exit 1
fi
if [ "$(uname -s)" != "OpenBSD" ]; then
    echo "⚠️  Ce script est conçu pour OpenBSD"
fi

# ── 1. Installation de Rust ──
echo ""
echo "[1] Installation de Rust..."
if ! command -v rustc >/dev/null 2>&1; then
    pkg_add rust rust-gdb 2>/dev/null || {
        echo "   Téléchargement depuis rustup..."
        ftp -o /tmp/rustup.sh https://sh.rustup.rs
        chmod +x /tmp/rustup.sh
        su -c "/tmp/rustup.sh -y" _pixelos 2>/dev/null || \
        env RUSTUP_HOME=/usr/local/rust CARGO_HOME=/usr/local/rust \
            /tmp/rustup.sh -y --default-toolchain stable
    }
else
    echo "   Rust déjà installé: $(rustc --version)"
fi

# ── 2. Compilation de Conduit ──
echo ""
echo "[2] Compilation de Conduit (Rust)..."
if [ ! -f "${CONDUIT_DIR}/conduit" ]; then
    cd /tmp
    test -d conduit || {
        ftp -o conduit.tar.gz \
            "https://gitlab.com/famedly/conduit/-/archive/v${VERSION}/conduit-v${VERSION}.tar.gz"
        tar xzf conduit.tar.gz
        mv "conduit-v${VERSION}" conduit
    }
    cd conduit
    echo "   Compilation (peut prendre 20-40 min)..."
    cargo build --release --features "rocksdb"
    cp target/release/conduit "${CONDUIT_DIR}/conduit"
    chmod 755 "${CONDUIT_DIR}/conduit"
    cd /tmp
    rm -rf conduit conduit.tar.gz
else
    echo "   Conduit déjà compilé"
fi

# ── 3. Création de l'utilisateur et des répertoires ──
echo ""
echo "[3] Création des répertoires..."
if ! id -u "${CONDUIT_USER}" >/dev/null 2>&1; then
    useradd -r -s /sbin/nologin -d "${CONDUIT_DIR}" "${CONDUIT_USER}"
fi
mkdir -p "${CONDUIT_DIR}/database" "${CONDUIT_DIR}/media"
chown -R "${CONDUIT_USER}:${CONDUIT_USER}" "${CONDUIT_DIR}"

# ── 4. Configuration Conduit ──
echo ""
echo "[4] Génération de la configuration..."
HOSTNAME=$(hostname -s 2>/dev/null || echo "pixelos")
FQDN="${HOSTNAME}.pixel"
SERVER_NAME="${FQDN}"

cat > "${CONDUIT_DIR}/conduit.toml" << EOF
# Conduit — Configuration PixelOS
# Fédération interne via WireGuard (10.100.0.0/16)

[global]
# Nom du serveur (utilisé dans les IDs Matrix: @user:server.pixel)
server_name = "${SERVER_NAME}"

# Port pour les clients Matrix (Element, etc.)
port = ${CONDUIT_PORT}

# Port pour la fédération (autres serveurs Matrix)
federation_port = ${FEDERATION_PORT}

# Adresse d'écoute
bind = "127.0.0.1"

# Chemin de la base de données
database_path = "${DB_DIR}"

# Type de base de données: rocksdb (performant) ou sqlite (léger)
database_backend = "rocksdb"

# Répertoire pour les médias (images, fichiers)
media_dir = "${CONDUIT_DIR}/media"

# Taille maximale des fichiers (50 Mo)
max_request_size = 52428800

# Nombre de workers
workers = 2

# Activer le chiffrement de bout en bout
allow_encryption = true

# Activer la fédération
allow_federation = true

# Activer l'enregistrement (inscription des nouveaux membres)
allow_registration = true

# L'enregistrement nécessite une invitation
registration_requires_invite = false

# Token d'inscription (laissez vide pour désactiver)
registration_token = ""

# Logs
log = "info"
log_file = "${CONDUIT_DIR}/conduit.log"

[rooms]
# Taille maximale des salles
default_room_version = "10"
max_room_size = 1000

[presence]
# Activer la présence (en ligne/hors ligne)
allow_presence = true
EOF

chown "${CONDUIT_USER}:${CONDUIT_USER}" "${CONDUIT_DIR}/conduit.toml"

# ── 5. Service rc.d ──
echo ""
echo "[5] Création du service rc.d..."
cat > /etc/rc.d/conduit << 'EOF'
#!/bin/ksh
# rc.d script for Conduit Matrix Server

daemon="/var/conduit/conduit"
daemon_user="_conduit"
daemon_flags=""
rc_reload="NO"

. /etc/rc.d/rc.subr

pexp="${daemon} ${daemon_flags}"

rc_cmd $1
EOF
chmod 755 /etc/rc.d/conduit

# ── 6. Configuration relayd (reverse proxy TLS) ──
echo ""
echo "[6] Configuration relayd pour la fédération Matrix..."
cat >> /etc/relayd.conf << 'RCFG'

# ── Matrix Federation (Conduit) ──
# Port 8448: fédération Matrix (TLS obligatoire)
# Port 443: clients Matrix (Element Web, SDK)

table <matrix_backends> { 127.0.0.1 }

# Frontend fédération :8448
protocol "matrix_fed" {
    tcp { nodelay, sack, socket buffer 65536 }
    tls { keypair "pixelos" }
}

relay "matrix_federation" {
    listen on egress port 8448
    protocol "matrix_fed"
    forward to <matrix_backends> port 6167
}

# Frontend clients Matrix :443 (dans le relay existant)
# Les chemins /_matrix/* sont proxyfiés vers Conduit
RCFG

echo "   relayd.conf mis à jour"

# ── 7. Configuration PF ──
echo ""
echo "[7] Configuration PF..."
cat >> /etc/pf.conf << 'PFCFG'

# ── Matrix / Comms ──
pass in on egress proto tcp to port 8448      # Fédération Matrix
pass in on egress proto tcp to port 443       # Clients Matrix (déjà ouvert)
PFCFG
pfctl -f /etc/pf.conf 2>/dev/null || true

# ── 8. Installation Element Web ──
echo ""
echo "[8] Installation Element Web (client Matrix)..."
ELEMENT_DIR="/var/www/htdocs/comms"
if [ ! -d "${ELEMENT_DIR}" ]; then
    mkdir -p "${ELEMENT_DIR}"
    echo "   Téléchargement de Element Web..."
    ftp -o /tmp/element.tar.gz \
        "https://github.com/vector-im/element-web/releases/download/v1.11.84/element-v1.11.84.tar.gz"
    tar xzf /tmp/element.tar.gz -C "${ELEMENT_DIR}" --strip-components=1
    rm /tmp/element.tar.gz

    # Configuration Element
    cat > "${ELEMENT_DIR}/config.json" << 'ECFG'
{
    "default_server_config": {
        "m.homeserver": {
            "base_url": "https://pixelos.pixel:443",
            "server_name": "pixelos.pixel"
        },
        "m.identity_server": {
            "base_url": ""
        }
    },
    "disable_custom_urls": true,
    "disable_3pid_login": true,
    "brand": "Pixel Comms",
    "default_country_code": "MA",
    "show_labs_settings": false,
    "features": {
        "feature_video_rooms": true,
        "feature_group_calls": true
    },
    "default_federate": true,
    "welcomeUserId": "@admin:pixelos.pixel",
    "room_directory": {
        "servers": ["pixelos.pixel"]
    }
}
ECFG
    chown -R www:www "${ELEMENT_DIR}"
    echo "   Element Web installé dans ${ELEMENT_DIR}"
else
    echo "   Element Web déjà présent"
fi

# ── 9. Démarrage ──
echo ""
echo "[9] Démarrage..."
rcctl enable conduit
rcctl start conduit 2>/dev/null || echo "   ⚠️  Conduit n'a pas démarré — vérifiez les logs: ${CONDUIT_DIR}/conduit.log"
rcctl restart relayd 2>/dev/null || true

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║  Conduit Matrix Server — Terminé !        ║"
echo "╠════════════════════════════════════════════╣"
echo "║ Serveurs :                                ║"
echo "║   Matrix Client    : https://pixelos.pixel:443  ║"
echo "║   Fédération       : https://pixelos.pixel:8448 ║"
echo "║   Element Web      : https://pixelos.pixel/comms║"
echo "║                                              ║"
echo "║ Connexion :                                   ║"
echo "║   Client : Element (app) → pixelos.pixel      ║"
echo "║   Web    : http://pixelos.pixel:9999/comms    ║"
echo "║                                              ║"
echo "║ Logs: ${CONDUIT_DIR}/conduit.log         ║"
echo "║ Base: ${DB_DIR}                    ║"
echo "╚════════════════════════════════════════════╝"
