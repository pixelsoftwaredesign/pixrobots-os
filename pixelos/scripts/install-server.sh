#!/bin/sh
# PixelOS - Installation du serveur de gestion principal

set -e

PIXELOS_VERSION="2.0.0"
PIXELOS_ROOT="/usr/local/lib/pixelos"
CONFIG_ROOT="/etc/pixelos"
VAR_ROOT="/var/lib/pixelos"

echo "╔══════════════════════════════════════════╗"
echo "║     PixelOS Server Installation v$PIXELOS_VERSION    ║"
echo "╚══════════════════════════════════════════╝"

# Vérification OpenBSD
if [ "$(uname)" != "OpenBSD" ]; then
    echo "⚠️  Ce script est optimisé pour OpenBSD"
    echo "   Installation continue en mode compatible..."
fi

# Installation Python + dépendances
echo "[+] Installation des dépendances..."
if command -v pkg_add >/dev/null 2>&1; then
    pkg_add python py3-pip py3-yaml
elif command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y python3 python3-pip python3-yaml
fi

# Création des répertoires
echo "[+] Création des répertoires..."
mkdir -p "$PIXELOS_ROOT" "$CONFIG_ROOT" "$VAR_ROOT/firmware" \
         "$VAR_ROOT/db" "$VAR_ROOT/logs" "/var/backups/pixelos"

# Copie des sources
echo "[+] Installation de PixelOS..."
cp -r src/* "$PIXELOS_ROOT/"
cp config/*.yaml "$CONFIG_ROOT/"

# Installation pip
pip install -e .

# Création du wrapper CLI
echo "[+] Création du wrapper CLI..."
cat > /usr/local/bin/pixelos << 'WRAPPER'
#!/bin/sh
exec python3 -m cli.main "$@"
WRAPPER
chmod +x /usr/local/bin/pixelos

# RC script pour l'agent
if command -v rcctl >/dev/null 2>&1; then
    echo "[+] Configuration service OpenBSD..."
    cat > /etc/rc.d/pixelos_agent << 'RC'
#!/bin/sh
daemon="/usr/local/bin/pixelos-agent"
daemon_flags=""
daemon_user="root"

. /etc/rc.d/rc.subr

rc_cmd $1
RC
    chmod +x /etc/rc.d/pixelos_agent
    rcctl enable pixelos_agent
fi

# Cron pour backup auto
echo "[+] Configuration backup automatique..."
cat > /var/cron/tabs/root << 'CRON'
# PixelOS - Backup quotidien à 3h
0 3 * * * /usr/local/bin/pixelos backup create
# PixelOS - Nettoyage backups vieux de 30 jours
0 4 * * * find /var/backups/pixelos -name "*.tar.gz" -mtime +30 -delete
CRON

echo ""
echo "✅ PixelOS Server installé !"
echo "   CLI:  pixelos status"
echo "   Web:  http://$(hostname):9999"
echo "   Logs: $VAR_ROOT/logs/agent.log"
