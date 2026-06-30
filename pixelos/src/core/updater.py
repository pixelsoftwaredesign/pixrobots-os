"""updater — Mise à jour de PixelOS (online + offline).

Supporte 4 modes:
  - git pull (dépôt GitHub)
  - USB / siteXX.tgz (offline)
  - mise à jour partielle (pip, pkg, configs)
  - rollback vers version précédente

Architecture:
  UpdateManager
  ├── check()          → version actuelle + dispo
  ├── update(mode)     → git | usb | pip | pkg | all
  ├── rollback()       → restore backup
  ├── backup()         → backup avant update
  └── history()        → historique des updates
"""

import json
import shutil
import structlog
import subprocess
import tarfile
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
PIXELOS_HOME = ROOT
BACKUP_DIR = ROOT / ".backups"
VERSION_FILE = ROOT / "VERSION"
UPDATE_HISTORY = ROOT / "data" / "updates.json"
INSTALL_PREFIX = Path("/usr/local/libexec/pixelos")
OPENBSD_PREFIX = Path("/usr/local")
ETC_PIXELOS = Path("/etc/pixelos")
ETC_PF = Path("/etc/pf.conf")
ETC_SYSTEM = Path("/etc")

GIT_REPO = "https://github.com/pixelsoftwaredesign/pixelos-agricol.git"
GIT_BRANCH = "main"


class UpdateManager:
    """Gestionnaire de mise à jour PixelOS."""

    def __init__(self, install_prefix: Path = None):
        self.src = PIXELOS_HOME
        self.prefix = install_prefix or (
            INSTALL_PREFIX if INSTALL_PREFIX.exists() else PIXELOS_HOME
        )
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # ── Version ──────────────────────────────────────────

    def current_version(self) -> str:
        if VERSION_FILE.exists():
            return VERSION_FILE.read_text(encoding="utf-8").strip()
        return "dev"

    def _write_version(self, version: str):
        VERSION_FILE.write_text(version.strip() + "\n", encoding="utf-8")

    def _next_version(self) -> str:
        base = self.current_version()
        parts = base.lstrip("v").split(".")
        try:
            patch = int(parts[-1]) + 1 if len(parts) >= 3 else 1
            return f"v{parts[0]}.{parts[1]}.{patch}"
        except (ValueError, IndexError):
            return f"v{datetime.now().strftime('%Y%m%d-%H%M')}"

    # ── Vérification ─────────────────────────────────────

    def check(self) -> dict:
        """Vérifie la version actuelle et si une mise à jour est dispo."""
        result = {
            "current_version": self.current_version(),
            "install_path": str(self.prefix),
            "mode": self._detect_mode(),
        }

        # Mode git : vérifier remote
        if self._has_git():
            try:
                r = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    capture_output=True, text=True, timeout=10,
                )
                result["git_commit"] = r.stdout.strip()
                r2 = subprocess.run(
                    ["git", "rev-list", "--count", "HEAD"],
                    capture_output=True, text=True, timeout=10,
                )
                result["git_commits"] = r2.stdout.strip()
            except Exception:
                pass

        # Détecter présence USB
        for mount in ["/mnt", "/media"]:
            p = Path(mount)
            usb_conf = p / "install.conf"
            usb_site = list(p.glob("*/site*.tgz")) + list(p.glob("site*.tgz"))
            if usb_conf.exists() or usb_site:
                result["usb_available"] = str(p)
                break

        result["needs_update"] = False
        return result

    def _detect_mode(self) -> str:
        if self._has_git():
            return "git"
        if self.prefix != self.src:
            return "installed"
        return "source"

    def _has_git(self) -> bool:
        git_dir = self.src / ".git"
        return git_dir.exists() and (git_dir / "HEAD").exists()

    # ─── Sauvegarde avant mise à jour ────────────────────

    def backup(self) -> dict:
        """Sauvegarde l'état actuel avant mise à jour."""
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        name = f"pre-update-{ts}"
        dst = BACKUP_DIR / name
        dst.mkdir(parents=True, exist_ok=True)

        # Sauvegarder les sources
        if self.prefix.exists():
            shutil.copytree(
                str(self.prefix), str(dst / "pixelos"),
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
            )

        # Sauvegarder les configs
        if ETC_PIXELOS.exists():
            shutil.copytree(str(ETC_PIXELOS), str(dst / "etc_pixelos"))

        saved = {
            "version": self.current_version(),
            "timestamp": ts,
            "path": str(dst),
            "size_kb": round(sum(
                f.stat().st_size for f in dst.rglob("*") if f.is_file()
            ) / 1024, 1),
        }
        log.info("Backup créé", **saved)
        return saved

    # ─── Mise à jour depuis git ──────────────────────────

    def _update_git(self) -> dict:
        """Met à jour les sources depuis GitHub."""
        if not self._has_git():
            return {"status": "error", "message": "Pas de dépôt git"}

        try:
            r = subprocess.run(
                ["git", "pull", "--ff-only", GIT_REPO, GIT_BRANCH],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                return {"status": "error", "message": r.stderr.strip()}
            return {
                "status": "ok",
                "message": r.stdout.strip()[:200],
                "version": self._next_version(),
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Timeout git pull"}
        except FileNotFoundError:
            return {"status": "error", "message": "git non installé"}

    # ─── Mise à jour depuis USB (siteXX.tgz) ─────────────

    def _update_usb(self, usb_path: Path = None) -> dict:
        """Met à jour depuis un siteXX.tgz sur support USB."""
        if usb_path is None:
            usb_path = self._detect_usb()
        if not usb_path:
            return {"status": "error", "message": "Aucune clé USB détectée"}

        tgz = self._find_site_tgz(usb_path)
        if not tgz:
            return {"status": "error",
                    "message": f"Aucun site*.tgz dans {usb_path}"}

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Extraire l'archive
                with tarfile.open(tgz, "r:gz") as tar:
                    tar.extractall(path=tmpdir)

                tmp = Path(tmpdir)

                # Mettre à jour les sources PixelOS
                px_dir = tmp / "pixelos"
                if px_dir.exists():
                    for item in px_dir.iterdir():
                        dst = self.prefix / item.name
                        if item.is_dir():
                            shutil.copytree(item, dst, dirs_exist_ok=True,
                                            ignore=shutil.ignore_patterns(
                                                "__pycache__", "*.pyc"))
                        else:
                            shutil.copy2(item, dst)

                # Mettre à jour les configs
                configs_dir = tmp / "configs"
                if configs_dir.exists():
                    for cfg in configs_dir.iterdir():
                        dst_map = {
                            "pf.conf": ETC_PF,
                            "sysctl.conf": ETC_SYSTEM / "sysctl.conf",
                            "dhcpd.conf": ETC_SYSTEM / "dhcpd.conf",
                            "nodes.conf": ETC_PIXELOS / "nodes.conf",
                            "pixelos.yaml": ETC_PIXELOS / "pixelos.yaml",
                        }
                        dst = dst_map.get(cfg.name, ETC_PIXELOS / cfg.name)
                        shutil.copy2(cfg, dst)

                # Installer dépendances Python si présentes
                pip_dir = usb_path / "pip_packages"
                req_file = usb_path / "requirements.txt"
                if pip_dir.exists() and req_file.exists():
                    subprocess.run(
                        ["pip3", "install", "--no-index",
                         "--find-links", str(pip_dir),
                         "-r", str(req_file)],
                        capture_output=True, text=True, timeout=120,
                    )

            version = self._next_version()
            self._write_version(version)
            return {"status": "ok", "version": version,
                    "source": str(tgz)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _detect_usb(self) -> Optional[Path]:
        for mount in ["/mnt", "/media"]:
            p = Path(mount)
            if (p / "install.conf").exists() or (p / "requirements.txt").exists():
                return p
        return None

    def _find_site_tgz(self, usb_path: Path) -> Optional[Path]:
        # Chercher siteXX.tgz à la racine ou dans un sous-dossier
        candidates = list(usb_path.glob("site*.tgz"))
        candidates += list(usb_path.glob("*/site*.tgz"))
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)
        return None

    # ─── Mise à jour partielle : pip ─────────────────────

    def _update_pip(self) -> dict:
        """Met à jour les dépendances Python."""
        try:
            r = subprocess.run(
                ["pip3", "install", "--upgrade",
                 "structlog", "paho-mqtt", "flask", "numpy",
                 "scikit-learn", "onnxruntime", "opencv-python-headless",
                 "psutil", "pymongo", "psycopg2-binary"],
                capture_output=True, text=True, timeout=120,
            )
            return {
                "status": "ok" if r.returncode == 0 else "error",
                "message": r.stdout.strip()[:200] or r.stderr.strip()[:200],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ─── Rollback ────────────────────────────────────────

    def rollback(self, version: str = None) -> dict:
        """Restaure une version précédente depuis les backups."""
        backups = sorted(BACKUP_DIR.iterdir()) if BACKUP_DIR.exists() else []
        if not backups:
            return {"status": "error", "message": "Aucun backup disponible"}

        target = None
        if version:
            for b in backups:
                if version in b.name:
                    target = b
                    break
            if not target:
                return {"status": "error",
                        "message": f"Backup {version} introuvable"}
        else:
            target = backups[-1]

        try:
            src_px = target / "pixelos"
            if src_px.exists():
                shutil.rmtree(self.prefix, ignore_errors=True)
                shutil.copytree(src_px, self.prefix)

            src_etc = target / "etc_pixelos"
            if src_etc.exists():
                shutil.rmtree(ETC_PIXELOS, ignore_errors=True)
                shutil.copytree(src_etc, ETC_PIXELOS)

            log.info("Rollback effectué", backup=target.name)
            return {"status": "ok", "backup": target.name, "path": str(target)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ─── Point d'entrée principal ────────────────────────

    def update(self, mode: str = "auto", usb_path: str = None) -> dict:
        """Point d'entrée principal : met à jour PixelOS.

        Args:
            mode: "git", "usb", "pip", "pkg", "all" ou "auto"
        """
        log.info("PixelOS update", mode=mode, current=self.current_version())

        # Backup avant tout
        backup_info = self.backup()

        result = {"mode": mode, "backup": backup_info}

        if mode in ("auto", "all", "git"):
            if mode == "auto" and self._has_git():
                r = self._update_git()
                result["git"] = r
                if r["status"] == "ok":
                    self._write_version(self._next_version())
                    result["version"] = r.get("version")
            elif mode == "auto":
                r = self._update_usb()
                result["usb"] = r
                if r["status"] == "ok":
                    result["version"] = r.get("version")

        if mode == "usb":
            usb_path_obj = Path(usb_path) if usb_path else None
            r = self._update_usb(usb_path_obj)
            result["usb"] = r
            if r["status"] == "ok":
                result["version"] = r.get("version")

        if mode in ("all", "pip"):
            result["pip"] = self._update_pip()

        result["new_version"] = self.current_version()
        self._log_history(result)

        if result.get("version"):
            log.info("PixelOS mis à jour", version=result["version"])
        return result

    def _log_history(self, entry: dict):
        """Enregistre l'opération dans l'historique."""
        UPDATE_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        history = []
        if UPDATE_HISTORY.exists():
            try:
                history = json.loads(UPDATE_HISTORY.read_text(encoding="utf-8"))
            except Exception:
                pass
        history.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "version": entry.get("version") or entry.get("new_version", "?"),
            "mode": entry.get("mode", "?"),
            "backup": entry.get("backup", {}).get("path"),
            "status": "ok" if any(
                v.get("status") == "ok" for v in entry.values()
                if isinstance(v, dict) and "status" in v
            ) else "partial",
        })
        UPDATE_HISTORY.write_text(
            json.dumps(history[-50:], indent=2), encoding="utf-8")

    def history(self, limit: int = 20) -> list[dict]:
        if not UPDATE_HISTORY.exists():
            return []
        try:
            history = json.loads(UPDATE_HISTORY.read_text(encoding="utf-8"))
            return history[-limit:]
        except Exception:
            return []
