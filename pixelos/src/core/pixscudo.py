# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
#!/usr/bin/env python3
"""
PixScudo — Audit d'intégrité et sécurité PixelOS.

Vérifications:
  - Intégrité des binaires critiques (SHA256)
  - Patches système disponibles
  - Intégrité des paquets
  - Permissions des fichiers sensibles
  - Configuration SSH
  - Ports ouverts inattendus
  - Processus suspects
  - Score de sécurité global
  - Conformité CIS
"""

import subprocess
import os
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

SCUDO_DIR = "/var/db/pixelos/pixscudo"
AUDIT_LOG = "/var/log/pixscudo_audit.log"
BASELINE_FILE = "baseline.json"
REPORT_FILE = "audit_report.json"

CRITICAL_BINS = [
    "/bin/sh", "/bin/ls", "/bin/cat", "/sbin/init", "/sbin/pfctl",
    "/usr/bin/ssh", "/usr/sbin/httpd", "/usr/sbin/nsd",
    "/usr/bin/python3", "/usr/bin/python",
]

SENSITIVE_FILES = [
    "/etc/pf.conf", "/etc/ssh/sshd_config",
    "/etc/httpd.conf", "/etc/nsd.conf",
    "/etc/rc.conf.local", "/etc/master.passwd",
    "/var/db/pixelos",
]

SUSPICIOUS_PROCESSES = [
    "nc -l", "ncat", "cryptomin", "xmrig", "tcpdump",
    "nmap", "masscan", "hydra", "medusa", "john",
]

EXPECTED_PORTS = {22, 80, 443, 8448, 9999, 21, 51820, 6167, 5300, 1883}


class PixScudo:
    def __init__(self):
        self._ensure_dirs()
        self._load_baseline()
        self.results = []

    def _ensure_dirs(self):
        Path(SCUDO_DIR).mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        return str(Path(SCUDO_DIR) / name)

    def _load_baseline(self):
        path = self._path(BASELINE_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.baseline = json.load(f)
                return
            except Exception:
                pass
        self.baseline = {}

    def _save_baseline(self):
        with open(self._path(BASELINE_FILE), "w") as f:
            json.dump(self.baseline, f, indent=2)

    # ── Baseline (référence d'intégrité) ─────────────────

    def create_baseline(self) -> dict:
        new_baseline = {}
        for path in CRITICAL_BINS:
            if not os.path.exists(path):
                new_baseline[path] = {"exists": False}
                continue
            try:
                with open(path, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()
                stat = os.stat(path)
                new_baseline[path] = {
                    "exists": True,
                    "sha256": digest,
                    "size": stat.st_size,
                    "mode": oct(stat.st_mode)[-4:],
                    "uid": stat.st_uid,
                    "baselined_at": datetime.now().isoformat(),
                }
            except Exception as e:
                new_baseline[path] = {"exists": True, "error": str(e)}
        self.baseline = new_baseline
        self._save_baseline()
        return {"baseline_created": len(new_baseline), "files": new_baseline}

    # ── System patches ────────────────────────────────────

    def check_syspatch(self) -> dict:
        try:
            r = subprocess.run(
                ["syspatch", "-c"],
                capture_output=True, text=True, timeout=30
            )
        except Exception:
            return {"patches": [], "available": 0}
        patches = [p.strip() for p in r.stdout.splitlines() if p.strip()]
        return {"patches": patches, "available": len(patches),
                "timestamp": datetime.now().isoformat()}

    # ── Package integrity ─────────────────────────────────

    def check_packages(self) -> dict:
        try:
            r = subprocess.run(
                ["pkg_check", "-q"],
                capture_output=True, text=True, timeout=60
            )
        except Exception:
            return {"issues": [], "count": 0}
        issues = [p.strip() for p in r.stdout.splitlines() if p.strip()]
        return {"issues": issues, "count": len(issues)}

    # ── Binary integrity ─────────────────────────────────

    def verify_integrity(self) -> list:
        results = []
        for path in CRITICAL_BINS:
            if not os.path.exists(path):
                results.append({"path": path, "exists": False, "status": "missing"})
                continue
            try:
                with open(path, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()
                stat = os.stat(path)
                baseline_entry = self.baseline.get(path, {})
                changed = False
                if baseline_entry.get("sha256") and baseline_entry["sha256"] != digest:
                    changed = True
                results.append({
                    "path": path,
                    "exists": True,
                    "sha256": digest,
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "changed": changed,
                    "baseline_sha256": baseline_entry.get("sha256", ""),
                })
            except Exception as e:
                results.append({"path": path, "exists": True, "error": str(e)})
        return results

    # ── SSH configuration ────────────────────────────────

    def check_ssh(self) -> dict:
        try:
            r = subprocess.run(
                ["grep", "-E",
                 "^(PermitRootLogin|PasswordAuthentication|PubkeyAuthentication|"
                 "Port|AllowUsers|Protocol|UsePAM)",
                 "/etc/ssh/sshd_config"],
                capture_output=True, text=True, timeout=10
            )
        except Exception:
            return {"settings": []}

        settings = [l.strip() for l in r.stdout.splitlines() if l.strip()]
        warnings = []
        for s in settings:
            if "PermitRootLogin yes" in s:
                warnings.append("SSH root login enabled (CIS 5.2.8)")
            if "PasswordAuthentication yes" in s:
                warnings.append("SSH password auth enabled (use keys)")
            if "Protocol 1" in s:
                warnings.append("SSH protocol 1 insecure")
            if "UsePAM yes" in s:
                warnings.append("SSH PAM enabled")
        recommendations = []
        if "PermitRootLogin prohibit-password" not in str(settings):
            recommendations.append("set PermitRootLogin prohibit-password")
        return {"settings": settings, "warnings": warnings,
                "recommendations": recommendations}

    # ── File permissions ─────────────────────────────────

    def check_permissions(self) -> list:
        results = []
        for path in SENSITIVE_FILES:
            if not os.path.exists(path):
                results.append({"path": path, "exists": False})
                continue
            try:
                stat = os.stat(path)
                mode = oct(stat.st_mode)[-4:]
                warnings = []
                permissive = int(mode) > 0o644 if mode.startswith("0") else False
                if mode == "0777" or mode == "0755" and path.endswith("passwd"):
                    warnings.append(f"permissive mode {mode}")
                results.append({
                    "path": path,
                    "exists": True,
                    "mode": mode,
                    "uid": stat.st_uid,
                    "gid": stat.st_gid,
                    "warnings": warnings,
                })
            except Exception as e:
                results.append({"path": path, "exists": True, "error": str(e)})
        return results

    # ── Open ports ───────────────────────────────────────

    def check_open_ports(self) -> dict:
        try:
            r = subprocess.run(
                ["netstat", "-ln", "-f", "inet"],
                capture_output=True, text=True, timeout=10
            )
        except Exception:
            return {"ports": [], "count": 0}

        ports = []
        for line in r.stdout.splitlines():
            m = re.search(r"\.(\d+)\s+.*LISTEN", line)
            if m:
                ports.append(int(m.group(1)))
        unexpected = [p for p in ports if p not in EXPECTED_PORTS]
        return {
            "ports": sorted(set(ports)),
            "count": len(set(ports)),
            "expected": sorted(EXPECTED_PORTS),
            "unexpected": sorted(set(unexpected)),
        }

    # ── Suspicious processes ─────────────────────────────

    def check_processes(self) -> dict:
        try:
            r = subprocess.run(
                ["ps", "-axo", "pid,comm,args"],
                capture_output=True, text=True, timeout=10
            )
        except Exception:
            return {"processes": [], "suspicious": [], "count": 0}

        procs = []
        suspicious = []
        for line in r.stdout.splitlines():
            parts = line.strip().split(None, 2)
            if len(parts) < 2:
                continue
            proc = {"pid": parts[0], "command": parts[1],
                    "args": parts[2] if len(parts) > 2 else ""}
            procs.append(proc)
            for sp in SUSPICIOUS_PROCESSES:
                if sp in proc.get("args", "") or sp in proc.get("command", ""):
                    suspicious.append(proc)
                    break
        return {
            "total": len(procs),
            "suspicious": suspicious,
            "suspicious_count": len(suspicious),
        }

    # ── Full audit ───────────────────────────────────────

    def run_full_audit(self) -> dict:
        self.results = []
        checks = {
            "syspatch": self.check_syspatch(),
            "packages": self.check_packages(),
            "integrity": self.verify_integrity(),
            "ssh": self.check_ssh(),
            "permissions": self.check_permissions(),
            "open_ports": self.check_open_ports(),
            "processes": self.check_processes(),
        }
        for name, data in checks.items():
            self.results.append((name, data))

        score = self._compute_score(checks)
        report = {
            "checks": self.results,
            "score": score,
            "grade": self._grade(score),
            "timestamp": datetime.now().isoformat(),
        }
        with open(self._path(REPORT_FILE), "w") as f:
            json.dump(report, f, indent=2)
        return report

    def _compute_score(self, checks: dict) -> int:
        score = 100
        patches = checks.get("syspatch", {})
        if patches.get("available", 0) > 0:
            score -= 15 * patches["available"]
        pkgs = checks.get("packages", {})
        if pkgs.get("count", 0) > 0:
            score -= 10 * pkgs["count"]
        integrity = checks.get("integrity", [])
        changed = sum(1 for c in integrity if c.get("changed"))
        score -= 25 * changed
        ssh = checks.get("ssh", {})
        if ssh.get("warnings"):
            score -= 10 * len(ssh["warnings"])
        ports = checks.get("open_ports", {})
        unexpected = ports.get("unexpected", [])
        score -= 10 * len(unexpected)
        perms = checks.get("permissions", [])
        perm_warnings = sum(len(p.get("warnings", [])) for p in perms)
        score -= 5 * perm_warnings
        procs = checks.get("processes", {})
        score -= 30 * procs.get("suspicious_count", 0)
        return max(0, score)

    @staticmethod
    def _grade(score: int) -> str:
        if score >= 90: return "A"
        if score >= 75: return "B"
        if score >= 50: return "C"
        if score >= 25: return "D"
        return "F"

    # ── CIS compliance ───────────────────────────────────

    def cis_check(self) -> dict:
        checks = []
        # CIS 1.1 - permissions des fichiers
        perms = self.check_permissions()
        for p in perms:
            if p.get("warnings"):
                checks.append({"id": "CIS-1.1", "path": p["path"],
                               "status": "FAIL", "detail": str(p["warnings"])})
        # CIS 5.2 - SSH
        ssh = self.check_ssh()
        if ssh.get("warnings"):
            for w in ssh["warnings"]:
                checks.append({"id": "CIS-5.2", "status": "FAIL", "detail": w})
        # CIS 6.2 - unused services
        ports = self.check_open_ports()
        for p in ports.get("unexpected", []):
            checks.append({"id": "CIS-6.2", "port": p,
                           "status": "WARN", "detail": f"port {p} inattendu"})
        # Score
        passed = sum(1 for c in checks if c.get("status") == "PASS")
        failed = sum(1 for c in checks if c.get("status") in ("FAIL", "WARN"))
        return {
            "checks": checks,
            "total": len(checks),
            "passed": passed,
            "failed": failed,
            "compliance_pct": round(100 * passed / max(len(checks), 1), 1),
        }

    # ── Summary ──────────────────────────────────────────

    def summary(self) -> dict:
        patches = self.check_syspatch()
        pkg = self.check_packages()
        ports = self.check_open_ports()
        ssh = self.check_ssh()
        procs = self.check_processes()

        warnings = []
        if patches.get("available", 0) > 0:
            warnings.append(f"{patches['available']} syspatch(es) disponible(s)")
        if pkg.get("count", 0) > 0:
            warnings.append(f"{pkg['count']} problème(s) paquet(s)")
        if ports.get("unexpected"):
            warnings.append(f"ports inattendus: {ports['unexpected']}")
        if ssh.get("warnings"):
            warnings.extend(ssh["warnings"])
        if procs.get("suspicious_count", 0) > 0:
            warnings.append(f"{procs['suspicious_count']} processus suspect(s)")

        score = self._compute_score({
            "syspatch": patches, "packages": pkg,
            "integrity": self.verify_integrity(),
            "ssh": ssh, "permissions": self.check_permissions(),
            "open_ports": ports, "processes": procs,
        })
        return {
            "patches_available": patches.get("available", 0),
            "package_issues": pkg.get("count", 0),
            "open_ports": ports.get("count", 0),
            "unexpected_ports": ports.get("unexpected", []),
            "ssh_warnings": ssh.get("warnings", []),
            "suspicious_processes": procs.get("suspicious_count", 0),
            "score": score,
            "grade": self._grade(score),
            "warnings": warnings,
            "baseline_exists": len(self.baseline) > 0,
        }
