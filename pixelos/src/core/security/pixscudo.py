# Pixel OS ó Copyright 2026
# Free License ó Verifiable and Reliable for Internet Users
# Pixel Software Design ó Copyright 2026
import subprocess
import os
import hashlib
from datetime import datetime


SYS_PATCHES_LOG = "/var/log/pixscudo_patches.log"
AUDIT_LOG = "/var/log/pixscudo_audit.log"
CRITICAL_BINS = [
    "/bin/sh", "/sbin/init", "/sbin/pfctl", "/usr/bin/ssh",
    "/usr/sbin/httpd", "/usr/sbin/nsd", "/usr/bin/python3",
]


class PixScudo:
    def __init__(self):
        self.results = []

    def check_syspatch(self):
        try:
            r = subprocess.run(
                ["syspatch", "-c"],
                capture_output=True, text=True, timeout=30
            )
        except Exception:
            return {"patches": [], "available": 0, "error": "syspatch failed"}

        patches = [p.strip() for p in r.stdout.splitlines() if p.strip()]
        return {
            "patches": patches,
            "available": len(patches),
            "timestamp": datetime.now().isoformat(),
        }

    def check_packages(self):
        try:
            r = subprocess.run(
                ["pkg_check", "-q"],
                capture_output=True, text=True, timeout=60
            )
        except Exception:
            return {"issues": [], "count": 0, "error": "pkg_check failed"}

        issues = [p.strip() for p in r.stdout.splitlines() if p.strip()]
        return {"issues": issues, "count": len(issues)}

    def verify_integrity(self):
        results = []
        for path in CRITICAL_BINS:
            if not os.path.exists(path):
                results.append({"path": path, "exists": False, "error": "not found"})
                continue
            try:
                with open(path, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()
                stat = os.stat(path)
                results.append({
                    "path": path,
                    "exists": True,
                    "sha256": digest,
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except Exception as e:
                results.append({"path": path, "exists": True, "error": str(e)})
        return results

    def check_ssh(self):
        try:
            r = subprocess.run(
                ["grep", "-E", "^(PermitRootLogin|PasswordAuthentication)",
                 "/etc/ssh/sshd_config"],
                capture_output=True, text=True, timeout=10
            )
        except Exception:
            return {"settings": [], "error": "ssh check failed"}

        settings = [l.strip() for l in r.stdout.splitlines() if l.strip()]
        warnings = []
        for s in settings:
            if "PermitRootLogin yes" in s:
                warnings.append("root SSH login enabled")
            if "PasswordAuthentication yes" in s:
                warnings.append("password auth enabled (use keys)")
        return {"settings": settings, "warnings": warnings}

    def check_permissions(self):
        sensitive = [
            "/etc/pf.conf", "/etc/ssh/sshd_config",
            "/etc/httpd.conf", "/etc/nsd.conf",
            "/var/db/pixelos",
        ]
        results = []
        for path in sensitive:
            if not os.path.exists(path):
                results.append({"path": path, "exists": False})
                continue
            try:
                stat = os.stat(path)
                mode = oct(stat.st_mode)[-4:]
                warnings = []
                if mode != "0644" and mode != "0600" and mode != "0700":
                    if mode > "0644":
                        warnings.append(f"permissive mode {mode}")
                results.append({
                    "path": path,
                    "exists": True,
                    "mode": mode,
                    "warnings": warnings,
                })
            except Exception as e:
                results.append({"path": path, "exists": True, "error": str(e)})
        return results

    def check_open_ports(self):
        try:
            r = subprocess.run(
                ["netstat", "-ln", "-f", "inet"],
                capture_output=True, text=True, timeout=10
            )
        except Exception:
            return {"ports": [], "count": 0, "error": "netstat failed"}

        ports = []
        for line in r.stdout.splitlines():
            m = __import__("re").search(r"\.(\d+)\s+.*LISTEN", line)
            if m:
                ports.append(int(m.group(1)))
        expected = {22, 80, 443, 8448, 9999, 21, 51820, 6167, 5300, 1883}
        unexpected = [p for p in ports if p not in expected]
        return {
            "ports": sorted(ports),
            "count": len(ports),
            "expected": sorted(expected),
            "unexpected": unexpected,
        }

    def run_full_audit(self):
        self.results = []
        patches = self.check_syspatch()
        self.results.append(("syspatch", patches))

        packages = self.check_packages()
        self.results.append(("packages", packages))

        integrity = self.verify_integrity()
        self.results.append(("integrity", integrity))

        ssh = self.check_ssh()
        self.results.append(("ssh", ssh))

        perms = self.check_permissions()
        self.results.append(("permissions", perms))

        ports = self.check_open_ports()
        self.results.append(("open_ports", ports))

        score = 100
        if patches.get("available", 0) > 0:
            score -= 15
        if packages.get("count", 0) > 0:
            score -= 10
        if ssh.get("warnings"):
            score -= 20
        unexpected = ports.get("unexpected", [])
        if unexpected:
            score -= 10 * len(unexpected)
        perms_warnings = sum(len(p.get("warnings", [])) for _, p in self.results if _ == "permissions" and isinstance(p, list))
        score -= perms_warnings * 5

        return {
            "checks": self.results,
            "score": max(0, score),
            "timestamp": datetime.now().isoformat(),
        }

    def summary(self):
        patches = self.check_syspatch()
        pkg = self.check_packages()
        ports = self.check_open_ports()
        ssh = self.check_ssh()

        warnings = []
        if patches.get("available", 0) > 0:
            warnings.append(f"{patches['available']} syspatch(es) disponible(s)")
        if pkg.get("count", 0) > 0:
            warnings.append(f"{pkg['count']} probl√®me(s) paquet(s)")
        if ports.get("unexpected"):
            warnings.append(f"ports inattendus: {ports['unexpected']}")
        if ssh.get("warnings"):
            warnings.extend(ssh["warnings"])

        return {
            "patches_available": patches.get("available", 0),
            "package_issues": pkg.get("count", 0),
            "open_ports": ports.get("count", 0),
            "unexpected_ports": ports.get("unexpected", []),
            "ssh_warnings": ssh.get("warnings", []),
            "warnings": warnings,
        }
