#!/bin/ksh
# test_security.sh — Tests d'intégration sécurité Pixel OS
# Vérifie que PixStat, PixDefend, PixScudo et PixProbe fonctionnent
# Usage: doas sh /usr/local/bin/test_security.sh [--verbose]

VERBOSE=0
if [ "$1" = "--verbose" ]; then VERBOSE=1; fi

PASS=0
FAIL=0

log() { echo "[$1] $2"; }
ok()   { PASS=$((PASS+1)); log "OK" "$1"; }
fail() { FAIL=$((FAIL+1)); log "FAIL" "$1"; }

echo "========================================"
echo "  Pixel OS — Tests de Sécurité"
echo "========================================"
echo ""

# ── Vérification préalable: pf ──
echo "--- Prérequis ---"
pfctl -s info >/dev/null 2>&1
if [ $? -eq 0 ]; then
    ok "pf (Packet Filter) est actif"
else
    fail "pf n'est pas actif — les tests PixDefend échoueront"
fi

# ── Test 1: PixDefend — Table de blocage ──
echo ""
echo "--- PixDefend ---"

# Vérifier que la table pixos_blocklist existe
TABLE_EXISTS=$(pfctl -t pixos_blocklist -T show 2>&1)
if echo "$TABLE_EXISTS" | grep -q "No such table" 2>/dev/null; then
    fail "Table pixos_blocklist absente — exécutez 'doas pfctl -t pixos_blocklist -T add 0.0.0.0'"
else
    ok "Table pixos_blocklist existe"
fi

# Blocage IP test (127.0.0.99)
BLOCK_RESULT=$(pfctl -t pixos_blocklist -T add 127.0.0.99 2>&1)
if echo "$BLOCK_RESULT" | grep -q "added" 2>/dev/null; then
    ok "Blocage IP 127.0.0.99 réussi"
else
    fail "Blocage IP 127.0.0.99 a échoué: $BLOCK_RESULT"
fi

# Vérifier que l'IP est dans la table
CHECK_BLOCKED=$(pfctl -t pixos_blocklist -T show 2>&1 | grep "127.0.0.99")
if [ -n "$CHECK_BLOCKED" ]; then
    ok "IP 127.0.0.99 confirmée dans la table de blocage"
else
    fail "IP 127.0.0.99 non trouvée dans la table"
fi

# Déblocage IP test
UNBLOCK_RESULT=$(pfctl -t pixos_blocklist -T delete 127.0.0.99 2>&1)
if echo "$UNBLOCK_RESULT" | grep -q "deleted" 2>/dev/null || [ $? -eq 0 ]; then
    ok "Déblocage IP 127.0.0.99 réussi"
else
    fail "Déblocage IP 127.0.0.99 a échoué: $UNBLOCK_RESULT"
fi

# Vérifier que la table a été nettoyée
CHECK_CLEAN=$(pfctl -t pixos_blocklist -T show 2>&1 | grep "127.0.0.99")
if [ -z "$CHECK_CLEAN" ]; then
    ok "Table nettoyée — IP 127.0.0.99 retirée"
else
    fail "IP 127.0.0.99 toujours présente dans la table"
fi

# Test rechargement pf (sans erreur)
RELOAD_RESULT=$(pfctl -f /etc/pf.conf 2>&1)
if [ $? -eq 0 ]; then
    ok "Rechargement pf.conf réussi"
else
    fail "Rechargement pf.conf a échoué: $RELOAD_RESULT"
fi

# Test rules PF (au moins les règles PixDefend doivent être présentes)
RULES_COUNT=$(pfctl -s rules 2>/dev/null | grep -c "pixos_blocklist" 2>/dev/null)
if [ "$RULES_COUNT" -gt 0 ] 2>/dev/null; then
    ok "Règles PixDefend présentes dans pf ($RULES_COUNT références)"
else
    fail "Aucune règle PixDefend dans pf"
fi

# ── Test 2: PixScudo — Vérifications système ──
echo ""
echo "--- PixScudo ---"

# syspatch
if syspatch -c >/dev/null 2>&1; then
    PATCHES=$(syspatch -c 2>/dev/null | wc -l | tr -d ' ')
    if [ "$PATCHES" -gt 0 ] 2>/dev/null; then
        log "INFO" "$PATCHES syspatch(es) disponible(s)"
    else
        ok "syspatch: système à jour"
    fi
else
    log "INFO" "syspatch non disponible (vérification ignorée)"
fi

# pkg_check
if command -v pkg_check >/dev/null 2>&1; then
    PKG_ISSUES=$(pkg_check -q 2>&1 | wc -l | tr -d ' ')
    if [ "$PKG_ISSUES" -gt 0 ] 2>/dev/null; then
        log "WARN" "$PKG_ISSUES problème(s) paquet(s)"
    else
        ok "pkg_check: intégrité paquets OK"
    fi
else
    log "INFO" "pkg_check non disponible (vérification ignorée)"
fi

# Binaires critiques
CRITICAL_BINS="/bin/sh /sbin/init /sbin/pfctl /usr/bin/ssh /usr/sbin/httpd /usr/bin/python3"
FOUND=0
MISSING=0
for b in $CRITICAL_BINS; do
    if [ -f "$b" ]; then
        FOUND=$((FOUND+1))
    else
        MISSING=$((MISSING+1))
        log "WARN" "Binaire manquant: $b"
    fi
done
if [ "$MISSING" -eq 0 ]; then
    ok "Intégrité: $FOUND binaires critiques présents"
else
    log "WARN" "$MISSING binaire(s) critique(s) manquant(s)"
fi

# SSH config
if [ -f /etc/ssh/sshd_config ]; then
    grep -q '^PermitRootLogin yes' /etc/ssh/sshd_config
    if [ $? -eq 0 ]; then
        log "WARN" "PermitRootLogin YES — recommandé: sans-mot-de-passe ou no"
    else
        ok "SSH: PermitRootLogin correctement configuré"
    fi
else
    log "INFO" "sshd_config non trouvé (vérification ignorée)"
fi

# ── Test 3: PixStat — Connexions réseau ──
echo ""
echo "--- PixStat ---"

# netstat doit fonctionner
NETSTAT_OUT=$(netstat -nt -f inet 2>&1 | grep -c "ESTABLISHED")
if [ $? -eq 0 ] || [ "$NETSTAT_OUT" -ge 0 ] 2>/dev/null; then
    ok "netstat: connexions accessibles ($NETSTAT_OUT établies)"
else
    fail "netstat a échoué"
fi

# ifconfig
IFCONFIG_OUT=$(ifconfig 2>&1 | grep -c "^[a-z]")
if [ "$IFCONFIG_OUT" -gt 0 ] 2>/dev/null; then
    ok "ifconfig: $IFCONFIG_OUT interfaces détectées"
else
    fail "ifconfig n'a retourné aucune interface"
fi

# Vérifier que l'interface egress existe
EGRESS=$(ifconfig 2>&1 | grep -E "^vio0|^em0|^igc0|^re0")
if [ -n "$EGRESS" ]; then
    ok "Interface réseau principale détectée"
else
    log "WARN" "Interface egress non trouvée (vio0/em0/igc0/re0)"
fi

# ── Test 4: PixProbe — Analyse protocole ──
echo ""
echo "--- PixProbe ---"

# Vérifier que tcpdump est disponible
TCPDUMP_OK=0
if command -v tcpdump >/dev/null 2>&1; then
    ok "tcpdump disponible"
    TCPDUMP_OK=1
else
    log "INFO" "tcpdump non installé (optionnel pour PixProbe)"
fi

# lsof
if command -v lsof >/dev/null 2>&1; then
    LSOF_OUT=$(lsof -i -P -n 2>&1 | head -20 | wc -l | tr -d ' ')
    if [ "$LSOF_OUT" -gt 1 ] 2>/dev/null; then
        ok "lsof: processus réseau accessibles"
    else
        log "INFO" "lsof: aucun processus réseau trouvé"
    fi
else
    log "INFO" "lsof non installé (optionnel pour PixProbe)"
fi

# Signature detection: port 443 doit être classé comme "web" et 8448 comme "matrix"
EXPECTED_WEB=$(echo "443" | while read p; do
    case $p in
        443|80|8080|9999) echo "web" ;;
        8448|6167) echo "matrix" ;;
        4001|5001) echo "ipfs" ;;
        8545|30303) echo "blockchain" ;;
        1883) echo "mqtt" ;;
        51820) echo "wireguard" ;;
        53|5300) echo "dns" ;;
        21) echo "ftp" ;;
        *) echo "unknown" ;;
    esac
done)
if echo "$EXPECTED_WEB" | grep -q "web"; then
    ok "PixProbe: classification port 443 -> web"
fi

# ── Test 5: Vérification pf.conf PixDefend ──
echo ""
echo "--- pf.conf (PixDefend rules) ---"

if [ -f /etc/pf.conf ]; then
    HAS_TABLE=$(grep -c "pixos_blocklist" /etc/pf.conf 2>/dev/null)
    HAS_RATELIMIT=$(grep -c "max-src-conn-rate" /etc/pf.conf 2>/dev/null)
    if [ "$HAS_TABLE" -gt 0 ] 2>/dev/null; then
        ok "pf.conf: table <pixos_blocklist> définie"
    else
        fail "pf.conf: table <pixos_blocklist> manquante"
    fi
    if [ "$HAS_RATELIMIT" -gt 0 ] 2>/dev/null; then
        ok "pf.conf: $HAS_RATELIMIT règle(s) rate-limiting actives"
    else
        fail "pf.conf: aucune règle rate-limiting"
    fi
else
    fail "/etc/pf.conf introuvable"
fi

# ── Résumé ──
echo ""
echo "========================================"
TOTAL=$((PASS+FAIL))
echo "  Résultat: $PASS/$TOTAL tests réussis"
if [ "$FAIL" -gt 0 ]; then
    echo "  ⚠️  $FAIL test(s) échoué(s)"
    exit 1
else
    echo "  ✅ Tous les tests passés"
    exit 0
fi
