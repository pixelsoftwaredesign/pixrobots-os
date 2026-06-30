#!/usr/bin/env python3
"""
Zero-Touch Installer — Installation automatisée PixelOS.

Détection du système d'exploitation, installation des dépendances,
configuration initiale, démarrage des services. Sans intervention humaine.

Nouvelles fonctionnalités:
  - install.site : script d'installation automatique OpenBSD
  - Génération ISO bootable (OpenBSD + Linux)
  - Détection matériel avancée
  - Post-install hooks
"""

import os
import sys
import json
import shutil
import subprocess
import platform
import tempfile
import stat
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
        results = {}
        svc_path = "/etc/systemd/system/pixelos.service"
        if os.path.exists("/etc/systemd/system"):
            try:
                with open(svc_path, "w") as f:
                    f.write(self._systemd_unit())
                self._run("systemctl daemon-reload")
                self._run("systemctl enable pixelos.service")
                results["systemd"] = {"status": "installed", "path": svc_path}
            except Exception as e:
                results["systemd"] = {"status": "error", "error": str(e)}
        else:
            results["systemd"] = {"status": "skipped", "reason": "no systemd"}

        if self.os_type == "openbsd":
            rc_path = "/etc/rc.d/pixelos"
            try:
                with open(rc_path, "w") as f:
                    f.write(self._openbsd_rc())
                os.chmod(rc_path, 0o755)
                results["rc.d"] = {"status": "created", "path": rc_path}
            except Exception as e:
                results["rc.d"] = {"status": "error", "error": str(e)}

        self.log_step("services", results.get("systemd", {}).get("status", "ok"),
                      json.dumps(results))
        return results

    @staticmethod
    def _systemd_unit() -> str:
        return """[Unit]
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

    @staticmethod
    def _openbsd_rc() -> str:
        return """#!/bin/ksh
# PixelOS rc.d script for OpenBSD

daemon="/usr/local/bin/python3"
daemon_flags="/opt/pixelos/src/web/app.py"
daemon_user="root"

. /etc/rc.d/rc.subr

rc_reload=NO

rc_cmd $1
"""

    # ── install.site (OpenBSD auto-install) ─────────────

    def generate_install_site(self, output_dir: str = "") -> dict:
        """Génère le script install.site pour installation automatique OpenBSD."""
        out = output_dir or INSTALL_DIR
        Path(out).mkdir(parents=True, exist_ok=True)

        content = """#!/bin/ksh
# install.site — PixelOS OpenBSD automatic installation
# Placez ce fichier dans le repertoire racine de l'installateur OpenBSD
# Execution automatique apres le premier redemarrage

echo "=== PixelOS Post-Install ==="

# Reseau
echo "Configuring network..."
echo "dhcp" > /etc/hostname.em0

# Paquets
export PKG_PATH=https://cdn.openbsd.org/pub/OpenBSD/$(uname -r)/packages/$(uname -m)/
pkg_add python3 git curl wget py3-pip

# Dependances Python
pip3 install flask paho-mqtt cryptography requests pyyaml psutil reedsolo pyserial

# Repertoires
install -d -o root -g wheel /opt/pixelos
install -d -o root -g wheel /var/db/pixelos
install -d -o root -g wheel /var/log/pixelos

# Recuperation du code source
if [ -f /mnt/pixelos.tar.gz ]; then
    tar xzf /mnt/pixelos.tar.gz -C /opt/pixelos
elif [ -d /mnt/pixelos ]; then
    cp -r /mnt/pixelos/* /opt/pixelos/
fi

# rc.d
cp /opt/pixelos/src/core/boot/pixelos.rc /etc/rc.d/pixelos
chmod 755 /etc/rc.d/pixelos
echo "pixelos_flags=\"\"" >> /etc/rc.conf.local
rcctl enable pixelos
rcctl start pixelos

echo "=== PixelOS installed successfully ==="
"""
        site_path = Path(out) / "install.site"
        site_path.write_text(content)
        os.chmod(site_path, 0o755)

        self.log_step("install_site", "ok", str(site_path))
        return {"status": "ok", "path": str(site_path)}

    # ── ISO Generation ──────────────────────────────────

    def generate_openbsd_iso(self, output: str = "") -> dict:
        """Génère une ISO bootable OpenBSD avec PixelOS pré-intégré."""
        out = output or "/tmp/pixelos-openbsd.iso"
        build_dir = Path(tempfile.mkdtemp(prefix="pixelos_iso_"))

        try:
            # Structure de l'ISO
            iso_root = build_dir / "iso"
            etc_dir = iso_root / "etc"
            etc_dir.mkdir(parents=True)

            # install.site
            site_content = """#!/bin/ksh
export PKG_PATH=https://cdn.openbsd.org/pub/OpenBSD/$(uname -r)/packages/$(uname -m)/
pkg_add python3 git curl wget py3-pip
pip3 install flask paho-mqtt cryptography requests pyyaml psutil reedsolo pyserial
install -d -o root -g wheel /opt/pixelos /var/db/pixelos /var/log/pixelos
if [ -f /mnt/pixelos.tgz ]; then
    tar xzf /mnt/pixelos.tgz -C /opt/pixelos
fi
"""
            (etc_dir / "install.site").write_text(site_content)
            os.chmod(etc_dir / "install.site", 0o755)

            # siteXX.tgz avec les fichiers PixelOS
            site_tgz = build_dir / "siteXX.tgz"
            pixelos_dir = build_dir / "pixelos"
            pixelos_dir.mkdir()

            # Copier les sources
            src_dir = Path(INSTALL_DIR)
            if src_dir.exists():
                subprocess.run(["cp", "-r", str(src_dir), str(pixelos_dir / "opt")], timeout=30)
            else:
                # Fallback: créer un tarball du repo local
                (pixelos_dir / "opt" / "pixelos").mkdir(parents=True)
                for p in ["src", "config", "pyproject.toml", "README.md"]:
                    sp = Path(".") / p
                    if sp.exists():
                        if sp.is_dir():
                            subprocess.run(["cp", "-r", str(sp), str(pixelos_dir / "opt" / "pixelos" / p)], timeout=30)
                        else:
                            shutil.copy2(sp, pixelos_dir / "opt" / "pixelos" / p)

            subprocess.run(["tar", "czf", str(site_tgz), "-C", str(build_dir), "pixelos"], timeout=60)

            # Construire l'ISO
            release = subprocess.run(["uname", "-r"], capture_output=True, text=True, timeout=5).stdout.strip() or "7.6"
            arch = self.arch or "amd64"
            mirror = f"https://cdn.openbsd.org/pub/OpenBSD/{release}/{arch}"
            iso_url = f"{mirror}/install{release}.iso"

            self.log_step("iso_download", "info", f"Downloading OpenBSD {release} base ISO from {iso_url}")
            try:
                subprocess.run([
                    "ftp", "-o", str(build_dir / "base.iso"), iso_url
                ], timeout=600)
            except Exception:
                # Fallback: créer une ISO minimale
                self.log_step("iso_download", "warn", "Base ISO download failed; creating minimal ISO")
                self._create_minimal_iso(build_dir, out)
                self.log_step("iso_created", "ok", out)
                return {"status": "ok", "path": out, "type": "minimal"}

            # Monter, injecter siteXX.tgz, rebuild ISO
            mnt = build_dir / "mnt"
            mnt.mkdir()
            subprocess.run(["vnconfig", str(build_dir / "base.iso")], timeout=10)
            subprocess.run(["mount", "-t", "cd9660", "/dev/vnd0", str(mnt)], timeout=10)
            shutil.copy(site_tgz, mnt / f"site{release}.tgz")
            shutil.copy(etc_dir / "install.site", mnt / "install.site")
            subprocess.run(["umount", str(mnt)], timeout=10)
            subprocess.run(["vnconfig", "-u", "/dev/vnd0"], timeout=10)

            subprocess.run([
                "mkisofs", "-R", "-b", f"{release}/{arch}/cdbr",
                "-c", "boot.catalog", "-o", out, str(iso_root)
            ], timeout=120)

            self.log_step("iso_created", "ok", out)
            return {"status": "ok", "path": out, "type": "openbsd"}
        except Exception as e:
            self.log_step("iso_creation", "error", str(e))
            return {"status": "error", "error": str(e)}
        finally:
            shutil.rmtree(build_dir, ignore_errors=True)

    def generate_debian_iso(self, output: str = "") -> dict:
        """Génère une ISO bootable Debian/Ubuntu avec PixelOS auto-install."""
        out = output or "/tmp/pixelos-debian.iso"
        build_dir = Path(tempfile.mkdtemp(prefix="pixelos_debian_iso_"))

        try:
            preseed = """# preseed.cfg — PixelOS auto-install Debian
d-i debconf/priority select critical
d-i mirror/country string manual
d-i mirror/http/hostname string deb.debian.org
d-i mirror/http/directory string /debian
d-i mirror/http/proxy string
d-i passwd/root-login boolean true
d-i passwd/root-password password pixelos
d-i passwd/root-password-again password pixelos
d-i passwd/user-fullname string PixelOS Admin
d-i passwd/username string pixelos
d-i passwd/user-password password pixelos
d-i passwd/user-password-again password pixelos
d-i clock-setup/utc boolean true
d-i timezone/choose string UTC
d-i partman-auto/method string regular
d-i partman-auto/choose_recipe select atomic
d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true
d-i apt-setup/use_mirror boolean false
d-i tasksel/first multiselect standard
d-i pkgsel/include string openssh-server python3 python3-pip python3-venv git curl
d-i grub-installer/only_debian boolean true
d-i finish-install/reboot_in_progress note
d-i preseed/late_command string \\
    in-target sh -c 'pip3 install flask paho-mqtt cryptography requests pyyaml psutil reedsolo pyserial' ; \\
    in-target sh -c 'mkdir -p /opt/pixelos /var/db/pixelos /var/log/pixelos' ; \\
    in-target sh -c 'cd /opt/pixelos && git clone https://github.com/pixelsoftwaredesign/pixelos-agricol.git .' ; \\
    in-target sh -c 'cp /opt/pixelos/pixelos/src/core/boot/pixelos.service /etc/systemd/system/' ; \\
    in-target sh -c 'systemctl enable pixelos.service'
"""
            preseed_path = build_dir / "preseed.cfg"
            preseed_path.write_text(preseed)

            self.log_step("debian_iso", "info", f"Preseed file: {preseed_path}")
            self.log_step("debian_iso", "info",
                          "To build: sudo apt install debootstrap isolinux && "
                          "sudo debootstrap --arch=amd64 stable /tmp/debian-chroot && "
                          "sudo genisoimage -o pixelos-debian.iso -b isolinux/isolinux.bin -c isolinux/boot.cat "
                          "-no-emul-boot -boot-load-size 4 -boot-info-table -R -J -V 'PixelOS' /tmp/debian-chroot")

            return {"status": "preseed_generated", "path": str(preseed_path),
                    "iso_path": out, "instructions": "Run the command above to build the ISO"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
        finally:
            shutil.rmtree(build_dir, ignore_errors=True)

    def _create_minimal_iso(self, build_dir: Path, output: str):
        """Crée une ISO minimale bootable pour dépannage."""
        iso_root = build_dir / "minimal"
        (iso_root / "boot").mkdir(parents=True)
        (iso_root / "pixelos").mkdir(parents=True)

        # Script de boot minimal
        boot_sh = """#!/bin/sh
echo "PixelOS Rescue System"
echo "Mounting filesystems..."
mount -t tmpfs tmpfs /tmp
echo "Starting PixelOS..."
python3 /pixelos/src/web/app.py 2>&1
"""
        (iso_root / "boot" / "boot.sh").write_text(boot_sh)
        os.chmod(iso_root / "boot" / "boot.sh", 0o755)

        # Copier les sources
        src = Path("pixelos/src")
        if src.exists():
            subprocess.run(["cp", "-r", str(src), str(iso_root / "pixelos" / "src")], timeout=30)

        # README
        (iso_root / "README.txt").write_text("PixelOS Rescue ISO\n")

        # Générer ISO avec xorriso si dispo, sinon grub-mkrescue
        if shutil.which("xorriso"):
            subprocess.run([
                "xorriso", "-as", "mkisofs",
                "-o", output,
                "-isohybrid-mbr", "/usr/lib/ISOLINUX/isohdpfx.bin",
                "-b", "isolinux/isolinux.bin", "-c", "isolinux/boot.cat",
                "-no-emul-boot", "-boot-load-size", "4", "-boot-info-table",
                str(iso_root)
            ], timeout=120)
        elif shutil.which("grub-mkrescue"):
            subprocess.run(["grub-mkrescue", "-o", output, str(iso_root)], timeout=120)
        else:
            raise RuntimeError("No ISO generation tool found (xorriso or grub-mkrescue)")

    # ── Post-install hooks ───────────────────────────────

    def post_install_hooks(self) -> dict:
        """Exécute les hooks post-installation (scripts personnalisés)."""
        hooks_dir = Path(INSTALL_DIR) / "hooks"
        results = []
        if hooks_dir.exists():
            for hook in sorted(hooks_dir.glob("*")):
                if hook.name.endswith((".sh", ".py")) and os.access(hook, os.X_OK):
                    try:
                        r = subprocess.run([str(hook)], capture_output=True, text=True, timeout=120)
                        results.append({
                            "hook": hook.name,
                            "status": "ok" if r.returncode == 0 else "error",
                            "output": r.stdout[-200:],
                        })
                    except Exception as e:
                        results.append({"hook": hook.name, "status": "exception", "error": str(e)})
        hooks_dir.mkdir(parents=True, exist_ok=True)
        self.log_step("post_install_hooks", "ok", f"{len(results)} hooks executed")
        return {"hooks_executed": len(results), "results": results}

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
                "backup": True, "pixauto": True, "pixhal": True,
                "pixkey": True, "pixdao": True, "digital_twin": True,
                "browser": True, "pixnet": True, "mqtt": True,
                "federation": True, "comms": True, "energy": True,
                "spaces": True, "geothermal": True,
            },
            "network": {
                "host": "0.0.0.0", "port": 8080,
                "pixnet_port": 8337, "mqtt_port": 1883,
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
        results["install_site"] = self.generate_install_site()
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
