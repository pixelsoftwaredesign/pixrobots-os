#!/bin/sh
# PixelOS - Installation de l'agent sur un nœud (RPi, ESP32, OpenBSD)

set -e

NODE_ID="${1:-$(hostname)}"
ROLE="${2:-edge}"
SERVER="${3:-10.0.0.1}"

echo "PixelOS Agent - Installation sur $NODE_ID (rôle: $ROLE)"

# Installer Python si nécessaire
if ! command -v python3 >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update && apt-get install -y python3 python3-pip
    elif command -v pkg_add >/dev/null 2>&1; then
        pkg_add python
    fi
fi

# Créer répertoires
mkdir -p /usr/local/lib/pixelos /etc/pixelos /var/log/pixelos

# Copier l'agent
cp src/agent/agent.py /usr/local/lib/pixelos/

# Configuration
cat > /etc/pixelos/agent.yaml << CONF
node_id: "$NODE_ID"
role: "$ROLE"
server: "$SERVER"
mqtt_broker: "$SERVER"
mqtt_port: 1883
poll_interval: 10
CONF

# Service
if command -v systemctl >/dev/null 2>&1; then
    cat > /etc/systemd/system/pixelos-agent.service << SERVICE
[Unit]
Description=PixelOS Agent
After=network.target

[Service]
ExecStart=/usr/bin/python3 /usr/local/lib/pixelos/agent.py
Environment=PIXELOS_NODE_ID=$NODE_ID
Environment=PIXELOS_ROLE=$ROLE
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE
    systemctl daemon-reload
    systemctl enable pixelos-agent
    systemctl start pixelos-agent
fi

echo "✅ Agent PixelOS installé sur $NODE_ID"
echo "   Rôle: $ROLE | Serveur: $SERVER"
