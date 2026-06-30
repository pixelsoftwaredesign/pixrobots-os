#!/bin/sh
# AgriCol - Configuration FTP sécurisé par zones agricoles
# À exécuter en root sur OpenBSD
# Configure: utilisateurs, groupes, répertoires chroot, permissions

set -e

FTP_BASE="/var/ftp"
ZONES="zone-nord zone-serre-a zone-serre-b zone-verger zone-plein-champ pepiniere"
GROUPS="ftp-agronomes ftp-techniciens ftp-capteurs"

echo "=== Configuration FTP PixelOS ==="

# --- 1. Création des groupes ---
echo "[+] Création des groupes..."
for g in $GROUPS; do
    groupadd -f "$g" 2>/dev/null || true
done

# --- 2. Création des utilisateurs et répertoires par zone ---
echo "[+] Création des utilisateurs et répertoires FTP..."
for zone in $ZONES; do
    user="ftp-${zone}"
    home="${FTP_BASE}/${zone}"

    # Créer utilisateur (sans shell, home = zone)
    useradd -m -d "$home" -s /sbin/nologin -g ftp-techniciens "$user" 2>/dev/null || true

    # Structure standard de la zone
    mkdir -p "$home/uploads"
    mkdir -p "$home/logs"
    mkdir -p "$home/partage"

    # Logs capteurs : écriture pour ftp-capteurs
    chown "$user:ftp-capteurs" "$home/logs"
    chmod 775 "$home/logs"

    # Uploads : écriture pour le propriétaire + groupe techniciens
    chmod 775 "$home/uploads"

    # Partage : lecture groupe agronomes
    chown "$user:ftp-agronomes" "$home/partage"
    chmod 750 "$home/partage"

    echo "  -> $zone ($user) @ $home"
done

# --- 3. Utilisateur agronome (accès inter-zones en lecture) ---
echo "[+] Création de l'utilisateur agronome..."
useradd -m -d "${FTP_BASE}/agronomes" -s /sbin/nologin -g ftp-agronomes "ftp-agronomes" 2>/dev/null || true
mkdir -p "${FTP_BASE}/agronomes/rapports" "${FTP_BASE}/agronomes/analyses" "${FTP_BASE}/agronomes/partage"

# Monter en lecture seule les zones accessibles aux agronomes
for zone in $ZONES; do
    link="${FTP_BASE}/agronomes/${zone}"
    if [ ! -L "$link" ]; then
        ln -sf "${FTP_BASE}/${zone}/partage" "$link"
    fi
done

# --- 4. Activation ftpd dans inetd ou standalone ---
echo "[+] Activation ftpd..."
if [ -f /etc/inetd.conf ]; then
    # Mode inetd
    sed -i '/^ftp/d' /etc/inetd.conf 2>/dev/null || true
    echo "ftp stream tcp nowait root /usr/libexec/ftpd ftpd -l -A" >> /etc/inetd.conf
    rcctl restart inetd
else
    # Mode standalone
    rcctl enable ftpd
    rcctl set ftpd flags "-l -A -P /var/run/ftpd.pid"
    rcctl start ftpd
fi

# --- 5. Autoriser les utilisateurs FTP ---
echo "[+] Configuration /etc/ftpusers..."
for zone in $ZONES; do
    echo "ftp-${zone}" >> /etc/ftpusers 2>/dev/null || true
done
echo "ftp-agronomes" >> /etc/ftpusers 2>/dev/null || true

echo "=== Configuration FTP terminée ==="
echo "Zones: $ZONES"
echo "Pour ajouter un utilisateur: useradd -m -d ${FTP_BASE}/<zone> -s /sbin/nologin -g ftp-techniciens <user>"
echo "Puis: echo \"<user>\" >> /etc/ftpusers"
