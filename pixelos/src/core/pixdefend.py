#!/usr/bin/env python3
"""
PixDefend — Règles pf, rate limiting, blocage dynamique.

Fonctionnalités:
  - Gestion table pf (blocage IP)
  - Rate limiting (max-src-conn, max-src-conn-rate)
  - Règles pf automatiques (anti-DDoS, anti-bruteforce)
  - Analyse de trafic et blocage automatique
  - Alertes de sécurité
  - Interface unifiée avec PixStat
"""

import subprocess
import os
import re
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

PF_CONF = "/etc/pf.conf"
PF_CONF_DIR = "/etc/pf.d"
PF_TABLE = "pixos_blocklist"

RATE_LIMITS = {
    22: {"max_conn": 5, "rate": 3, "seconds": 60},
    80: {"max_conn": 100, "rate": 50, "seconds": 60},
    443: {"max_conn": 100, "rate": 50, "seconds": 60},
    1883: {"max_conn": 50, "rate": 20, "seconds": 60},
    51820: {"max_conn": 10, "rate": 5, "seconds": 60},
}


class PixDefend:
    def __init__(self):
        self.threshold_conns = 50
        self.threshold_rate = 30
        self.threshold_window = 60
        self.blocked_ips = set()
        self.alert_history = []
        self.rule_files = {}

    def _pfctl(self, args, use_doas=True):
        try:
            cmd = ["doas", "pfctl"] + args if use_doas else ["pfctl"] + args
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return r.returncode == 0, r.stdout, r.stderr
        except Exception as e:
            return False, "", str(e)

    # ── Table management ─────────────────────────────────

    def table_exists(self):
        ok, out, _ = self._pfctl(["-t", PF_TABLE, "-T", "show"])
        return ok

    def ensure_table(self):
        if not self.table_exists():
            ok, _, err = self._pfctl(["-t", PF_TABLE, "-T", "add", "0.0.0.0"])
            return {"status": "ok" if ok else "error", "error": err if not ok else ""}
        return {"status": "ok"}

    def block_ip(self, ip: str) -> dict:
        ok, _, err = self._pfctl(["-t", PF_TABLE, "-T", "add", ip])
        if ok:
            self.blocked_ips.add(ip)
            self.alert_history.append({
                "ip": ip, "action": "block",
                "timestamp": datetime.now().isoformat(),
            })
        return {"status": "blocked" if ok else "error", "ip": ip, "error": err}

    def unblock_ip(self, ip: str) -> dict:
        ok, _, err = self._pfctl(["-t", PF_TABLE, "-T", "delete", ip])
        if ok:
            self.blocked_ips.discard(ip)
        return {"status": "unblocked" if ok else "error", "ip": ip, "error": err}

    def list_blocked(self) -> dict:
        ok, out, err = self._pfctl(["-t", PF_TABLE, "-T", "show"])
        if not ok:
            return {"ips": [], "count": 0, "error": err}
        ips = [line.strip() for line in out.splitlines()
               if line.strip() and not line.startswith("No")]
        self.blocked_ips = set(ips)
        return {"ips": sorted(ips), "count": len(ips)}

    def unblock_all(self) -> dict:
        blocked = self.list_blocked()
        count = 0
        for ip in blocked.get("ips", []):
            self.unblock_ip(ip)
            count += 1
        return {"status": "unblocked_all", "count": count}

    # ── pf.conf management ───────────────────────────────

    def reload_pf(self) -> dict:
        ok, out, err = self._pfctl(["-f", PF_CONF])
        return {"status": "ok" if ok else "error", "output": out, "error": err}

    def get_pf_status(self) -> dict:
        ok, out, err = self._pfctl(["-s", "info"])
        if not ok:
            return {"enabled": False, "error": err}
        enabled = "Enabled" in out or "Status: Enabled" in out
        stats = {"enabled": enabled}
        for line in out.splitlines():
            if "Bytes" in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        stats["bytes"] = int(parts[-1])
                    except ValueError:
                        pass
        return stats

    def get_pf_rules(self) -> dict:
        ok, out, err = self._pfctl(["-s", "rules"])
        if not ok:
            return {"rules": [], "error": err}
        rules = [line.strip() for line in out.splitlines() if line.strip()]
        return {"rules": rules, "count": len(rules)}

    # ── Rate limiting ────────────────────────────────────

    def apply_rate_limits(self) -> dict:
        """Génère des règles de rate limiting pour les ports standards."""
        rules = []
        for port, cfg in RATE_LIMITS.items():
            rule = (
                f"pass in on egress proto tcp from any to any port {port} "
                f"flags S/SA keep state "
                f"(max-src-conn {cfg['max_conn']}, "
                f"max-src-conn-rate {cfg['rate']}/{cfg['seconds']}, "
                f"overload <{PF_TABLE}> flush)"
            )
            rules.append({"port": port, "rule": rule, **cfg})
        return {
            "generated_rules": rules,
            "count": len(rules),
            "note": "ajouter manuellement dans pf.conf ou utiliser write_pf_conf",
        }

    def generate_pf_conf(self) -> str:
        """Génère une configuration pf complète avec rate limiting PixDefend."""
        lines = [
            '# ── PixDefend — Configuration pf automatique ──',
            f'table <{PF_TABLE}> persist',
            f'block in quick from <{PF_TABLE}> to any',
            '',
            '# ── Rate limiting ──',
        ]
        for port, cfg in RATE_LIMITS.items():
            lines.append(
                f'pass in on egress proto tcp from any to any port {port} '
                f'flags S/SA keep state '
                f'(max-src-conn {cfg["max_conn"]}, '
                f'max-src-conn-rate {cfg["rate"]}/{cfg["seconds"]}, '
                f'overload <{PF_TABLE}> flush)'
            )
        lines.extend([
            '',
            '# ── Anti-spoof ──',
            'antispoof for egress',
            '',
            '# ── ICMP rate limit ──',
            'pass in inet proto icmp all icmp-type echoreq',
            '',
            '# ── SSH protection ──',
            'block in on egress proto tcp from any to any port 22 \\',
            '    (os "Linux", os "Windows")',
        ])
        return "\n".join(lines)

    def write_pf_conf(self, path: str = "") -> dict:
        path = path or PF_CONF
        try:
            content = self.generate_pf_conf()
            with open(path, "w") as f:
                f.write(content)
            return {"status": "written", "path": path, "rules_count": len(RATE_LIMITS) + 4}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ── Rule files ───────────────────────────────────────

    def save_rule_file(self, name: str, content: str) -> dict:
        Path(PF_CONF_DIR).mkdir(parents=True, exist_ok=True)
        path = os.path.join(PF_CONF_DIR, name)
        try:
            with open(path, "w") as f:
                f.write(content)
            self.rule_files[name] = content
            return {"status": "saved", "path": path}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def list_rule_files(self) -> list:
        if os.path.isdir(PF_CONF_DIR):
            return os.listdir(PF_CONF_DIR)
        return []

    # ── Auto-block ───────────────────────────────────────

    def auto_block(self, ip: str, reason: str = "rate_limit") -> dict:
        result = self.block_ip(ip)
        result["reason"] = reason
        return result

    def check_and_block(self, stats_by_ip: dict) -> list:
        alerts = []
        for ip, count in stats_by_ip.items():
            if count > self.threshold_conns and ip not in self.blocked_ips:
                self.auto_block(ip, f"exceeded {count} connections")
                alerts.append({"ip": ip, "count": count, "action": "blocked"})
        return alerts

    def get_rate_limit_rules(self) -> list:
        return [
            {
                "port": port,
                "max_conn": cfg["max_conn"],
                "rate": cfg["rate"],
                "window_s": cfg["seconds"],
            }
            for port, cfg in RATE_LIMITS.items()
        ]

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> dict:
        bl = self.list_blocked()
        pf = self.get_pf_status()
        return {
            "blocked": bl["count"],
            "blocked_ips": bl.get("ips", []),
            "pf_enabled": pf.get("enabled", False),
            "threshold_conns": self.threshold_conns,
            "threshold_rate": self.threshold_rate,
            "rate_limits_configured": len(RATE_LIMITS),
            "alerts_total": len(self.alert_history),
            "alerts_recent": self.alert_history[-20:] if self.alert_history else [],
        }
