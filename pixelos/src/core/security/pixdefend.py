import subprocess
import os
from datetime import datetime


PF_CONF = "/etc/pf.conf"
PF_TABLE = "pixos_blocklist"


class PixDefend:
    def __init__(self):
        self.threshold_conns = 50
        self.threshold_rate = 30
        self.threshold_window = 60
        self.blocked_ips = set()
        self.alert_history = []

    def _pfctl(self, args):
        try:
            r = subprocess.run(
                ["doas", "pfctl"] + args,
                capture_output=True, text=True, timeout=15
            )
            return r.returncode == 0, r.stdout, r.stderr
        except Exception as e:
            return False, "", str(e)

    def table_exists(self):
        try:
            r = subprocess.run(
                ["pfctl", "-t", PF_TABLE, "-T", "show"],
                capture_output=True, text=True, timeout=5
            )
            return r.returncode == 0
        except Exception:
            return False

    def ensure_table(self):
        if not self.table_exists():
            ok, out, err = self._pfctl(["-t", PF_TABLE, "-T", "add", "0.0.0.0"])
            if not ok:
                return {"status": "error", "error": err}
        return {"status": "ok"}

    def block_ip(self, ip):
        ok, out, err = self._pfctl(["-t", PF_TABLE, "-T", "add", ip])
        if ok:
            self.blocked_ips.add(ip)
            self.alert_history.append({
                "ip": ip, "action": "block",
                "timestamp": datetime.now().isoformat(),
            })
        return {"status": "blocked" if ok else "error", "ip": ip, "error": err}

    def unblock_ip(self, ip):
        ok, out, err = self._pfctl(["-t", PF_TABLE, "-T", "delete", ip])
        if ok:
            self.blocked_ips.discard(ip)
        return {"status": "unblocked" if ok else "error", "ip": ip, "error": err}

    def list_blocked(self):
        ok, out, err = self._pfctl(["-t", PF_TABLE, "-T", "show"])
        if not ok:
            return {"ips": [], "count": 0, "error": err}
        ips = [line.strip() for line in out.splitlines() if line.strip() and not line.startswith("No")]
        self.blocked_ips = set(ips)
        return {"ips": sorted(ips), "count": len(ips)}

    def reload_pf(self):
        ok, out, err = self._pfctl(["-f", PF_CONF])
        return {"status": "ok" if ok else "error", "output": out, "error": err}

    def get_pf_status(self):
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

    def get_pf_rules(self):
        ok, out, err = self._pfctl(["-s", "rules"])
        if not ok:
            return {"rules": [], "error": err}
        rules = [line.strip() for line in out.splitlines() if line.strip()]
        return {"rules": rules, "count": len(rules)}

    def add_rate_limit_rule(self, port, max_conn=10, rate=5, seconds=60):
        rule = (
            f"pass in on egress proto tcp from any to any port {port} "
            f"flags S/SA keep state "
            f"(max-src-conn {max_conn}, max-src-conn-rate {rate}/{seconds}, "
            f"overload <{PF_TABLE}> flush)"
        )
        return {"rule": rule, "note": "add to pf.conf manually or use reload_pf"}

    def auto_block(self, ip, reason="rate_limit"):
        result = self.block_ip(ip)
        result["reason"] = reason
        return result

    def check_and_block(self, stats_by_ip):
        alerts = []
        for ip, count in stats_by_ip.items():
            if count > self.threshold_conns:
                if ip not in self.blocked_ips:
                    self.auto_block(ip, f"exceeded {count} connections")
                    alerts.append({"ip": ip, "count": count, "action": "blocked"})
        return alerts

    def stats(self):
        bl = self.list_blocked()
        pf = self.get_pf_status()
        return {
            "blocked": bl["count"],
            "blocked_ips": bl.get("ips", []),
            "pf_enabled": pf.get("enabled", False),
            "threshold_conns": self.threshold_conns,
            "threshold_rate": self.threshold_rate,
            "alerts_total": len(self.alert_history),
            "alerts_recent": self.alert_history[-20:] if self.alert_history else [],
        }
