#!/usr/bin/env python3
"""
Zero-Touch Installer — Installation automatisée PixelOS.

Détection du système d'exploitation, installation des dépendances,
configuration initiale, démarrage des services. Sans intervention humaine.
"""

import os
import sys
import json
import shutil
import subprocess
import platform
from pathlib import Path
from datetime import datetime

INSTALL_DIR = "/opt/pixelos"
VAR_DIR = "/var/db/pixelos"
LOG_DIR = "/var/log/pixelos"


class ZeroTouchInstaller:
    def __init__(self):
        self.os_type = platform.system().lower()
        self.distro = self._detect_distro()
        self.arch = platform.machine()
        self.hostname = platform.node()
        self.errors = []
        self.steps = []

    def _detect_distro(self):
        if self.os_type != "linux":
            return self.os_type
        try:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("ID="):
                            return line.split("=")[-1].strip().strip('"')
        except Exception:
            pass
        return "unknown"

    def log_step(self, name: str, status: str, detail: str = ""):
        self.steps.append({
            "step": name,
            "status": status,
            "detail": detail,
            "ts": datetime.now().isoformat(),
        })

    # ── System checks ─────────────────────────────────────

    def check_system(self) -> dict:
        checks = {
            "os": self.os_type,
            "distro": self.distro,
            "arch": self.arch,
            "hostname": self.hostname,
            "python_version": sys.version,
            "pip_available": shutil.which("pip3") or shutil.which("pip") is not None,
            "git_available": shutil.which("git") is not None,
            "docker_available": shutil.which("docker") is not None,
            "node_available": shutil.which("node") is not None,
            "rust_available": shutil.which("rustc") is not None,
        }
        self.log_step("system_check", "ok" if shutil.which("python3") else "warn", json.dumps(checks))
        return checks

    # ── Dependencies ──────────────────────────────────────

    def install_dependencies(self) -> dict:
        results = {}
        base_pkgs = ["python3", "python3-pip", "git", "curl", "wget", "build-essential"]

        if self.os_type == "linux":
            pm = self._get_package_manager()
            if pm:
                r = self._run(f"{pm} update")
                results["update"] = r

                if pm == "apt-get":
                    r = self._run(f"{pm} install -y {' '.join(base_pkgs)}")
                elif pm == "dnf" or pm == "yum":
                    r = self._run(f"{pm} install -y python3 python3-pip git curl wget gcc")
                elif pm == "pacman":
                    r = self._run(f"{pm} -Syu --noconfirm python python-pip git curl wget base-devel")
                else:
                    r = {"status": "skipped", "reason": f"unsupported pm: {pm}"}
                results["install"] = r

        elif self.os_type == "darwin":
            if shutil.which("brew"):
                r = self._run("brew install python3 git curl wget")
                results["install"] = r
        elif self.os_type == "openbsd":
            r = self._run("pkg_add python3 git curl wget")
            results["install"] = r
        elif self.os_type == "windows":
            results["install"] = {"status": "skipped", "reason": "use WSL or manual install"}

        pip = shutil.which("pip3") or shutil.which("pip")
        if pip:
            py_reqs = [
                "flask", "paho-mqtt", "cryptography", "requests",
                "pyyaml", "psutil", "reedsolo", "pyserial",
            ]
            r = self._run(f"{pip} install {' '.join(py_reqs)}")
            results["pip"] = r

        self.log_step("dependencies", "ok" if not self.errors else "error", json.dumps(results))
        return results

    def _get_package_manager(self) -> str:
        for pm in ["apt-get", "dnf", "yum", "pacman", "zypper"]:
            if shutil.which(pm):
                return pm
        return ""

    def _run(self, cmd: str) -> dict:
        try:
            r = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=300)
            return {
                "status": "ok" if r.returncode == 0 else "error",
                "returncode": r.returncode,
                "stdout": r.stdout[-500:],
                "stderr": r.stderr[-500:],
            }
        except Exception as e:
            self.errors.append(str(e))
            return {"status": "exception", "error": str(e)}

    # ── Directory Setup ───────────────────────────────────

    def setup_directories(self) -> dict:
        dirs = [INSTALL_DIR, VAR_DIR, LOG_DIR,
                f"{VAR_DIR}/backup", f"{VAR_DIR}/pixkey",
                f"{VAR_DIR}/pixdao", f"{VAR_DIR}/digital_twin",
                f"{VAR_DIR}/pixhal", f"{VAR_DIR}/pixauto"]
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)
        self.log_step("directories", "ok", f"created {len(dirs)} dirs")
        return {"status": "ok", "dirs_created": len(dirs)}

    # ── Service Installation ──────────────────────────────

    def install_services(self) -> dict:
        svc_content = """[Unit]
Description=PixelOS - Agricultural Operating System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/pixelos
ExecStart=/usr/bin/python3 /opt/pixelos/src/web/app.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
        results = {}
        svc_path = "/etc/systemd/system/pixelos.service"
        if os.path.exists("/etc/systemd/system"):
            try:
                with open(svc_path, "w") as f:
                    f.write(svc_content)
                self._run("systemctl daemon-reload")
                self._run("systemctl enable pixelos.service")
                results["systemd"] = {"status": "installed", "path": svc_path}
            except Exception as e:
                results["systemd"] = {"status": "error", "error": str(e)}
        else:
            results["systemd"] = {"status": "skipped", "reason": "no systemd"}

        # rc.d for OpenBSD
        if self.os_type == "openbsd":
            rc_content = "pixelos_flags=\"\"\n"
            rc_path = "/etc/rc.d/pixelos"
            try:
                with open(rc_path, "w") as f:
                    f.write(rc_content)
                results["rc.d"] = {"status": "created", "path": rc_path}
            except Exception as e:
                results["rc.d"] = {"status": "error", "error": str(e)}

        self.log_step("services", results.get("systemd", {}).get("status", "ok"),
                      json.dumps(results))
        return results

    # ── Config ────────────────────────────────────────────

    def generate_config(self) -> dict:
        cfg = {
            "instance_name": self.hostname,
            "version": "2.1.0",
            "created_at": datetime.now().isoformat(),
            "os": self.os_type,
            "distro": self.distro,
            "arch": self.arch,
            "autostart": True,
            "modules": {
                "backup": True,
                "pixauto": True,
                "pixhal": True,
                "pixkey": True,
                "pixdao": True,
                "digital_twin": True,
                "browser": True,
                "pixnet": True,
                "mqtt": True,
                "federation": True,
                "comms": True,
                "energy": True,
                "spaces": True,
                "geothermal": True,
            },
            "network": {
                "host": "0.0.0.0",
                "port": 8080,
                "pixnet_port": 8337,
                "mqtt_port": 1883,
            },
        }
        cfg_path = f"{INSTALL_DIR}/config.json"
        try:
            with open(cfg_path, "w") as f:
                json.dump(cfg, f, indent=2)
            self.log_step("config", "ok", cfg_path)
            return {"status": "ok", "path": cfg_path, "config": cfg}
        except Exception as e:
            self.log_step("config", "error", str(e))
            return {"status": "error", "error": str(e)}

    # ── Full Install ──────────────────────────────────────

    def run(self, skip_deps: bool = False) -> dict:
        self.log_step("install_started", "ok", f"PixelOS v2.1.0 on {self.os_type}/{self.arch}")
        results = {"system": self.check_system()}

        if not skip_deps:
            results["dependencies"] = self.install_dependencies()

        results["directories"] = self.setup_directories()
        results["config"] = self.generate_config()
        results["services"] = self.install_services()
        results["steps"] = self.steps
        results["errors"] = self.errors
        results["completed_at"] = datetime.now().isoformat()
        results["success"] = len(self.errors) == 0
        return results


def main():
    installer = ZeroTouchInstaller()
    import json
    result = installer.run()
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
