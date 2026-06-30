# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""Sauvegarde et restauration du système PixelOS."""

import os
import shutil
import tarfile
import subprocess
import structlog
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


log = structlog.get_logger()


class BackupManager:
    """Gestion des backups complets du système agricole."""

    def __init__(self, path: str = "/var/backups/pixelos",
                 retention_days: int = 30):
        self.base = Path(path)
        self.base.mkdir(parents=True, exist_ok=True)
        self.retention = retention_days

    def create(self, comment: str = "") -> str:
        """Crée un backup complet : config + DB + firmwares."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.base / timestamp
        backup_dir.mkdir(parents=True)

        log.info("Création backup", dir=str(backup_dir))

        # 1. Configuration PixelOS
        self._backup_config(backup_dir)

        # 2. Base MySQL
        self._backup_mysql(backup_dir)

        # 3. Firmwares
        self._backup_firmwares(backup_dir)

        # 4. Logs système
        self._backup_logs(backup_dir)

        # 5. Archive
        archive_path = f"{backup_dir}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(backup_dir, arcname=timestamp)

        # Nettoyage
        shutil.rmtree(backup_dir)

        # Rotation
        self._rotate()

        log.info("Backup terminé", path=archive_path)
        return archive_path

    def list_backups(self) -> list[dict]:
        """Liste les backups disponibles."""
        backups = []
        for f in sorted(self.base.glob("*.tar.gz"), reverse=True):
            size = f.stat().st_size
            date = datetime.fromtimestamp(f.stat().st_mtime)
            backups.append({
                "path": str(f),
                "date": date.isoformat(),
                "size": self._format_size(size),
                "id": f.stem,
            })
        return backups

    def restore(self, backup_id: Optional[str] = None) -> bool:
        """Restaure un backup."""
        if backup_id is None:
            backups = self.list_backups()
            if not backups:
                log.error("Aucun backup disponible")
                return False
            backup_id = backups[0]["id"]

        archive = self.base / f"{backup_id}.tar.gz"
        if not archive.exists():
            log.error("Backup introuvable", path=str(archive))
            return False

        log.warning("RESTAURATION en cours", backup=str(archive))
        restore_dir = self.base / "_restore"
        restore_dir.mkdir(exist_ok=True)

        with tarfile.open(archive) as tar:
            tar.extractall(path=restore_dir)

        # Restaurer la config
        extracted = restore_dir / backup_id
        self._restore_config(extracted / "config")
        self._restore_mysql(extracted / "mysql.sql")

        shutil.rmtree(restore_dir)
        log.info("Restauration terminée")
        return True

    # ─── Backup individuels ───

    def _backup_config(self, dest: Path) -> None:
        config_dir = dest / "config"
        config_dir.mkdir()
        for src in ["/etc/pixelos", "/etc/agricol",
                     "/etc/pf.conf", "/etc/dhcpd.conf"]:
            p = Path(src)
            if p.exists():
                if p.is_dir():
                    shutil.copytree(p, config_dir / p.name)
                else:
                    shutil.copy2(p, config_dir)

    def _backup_mysql(self, dest: Path) -> None:
        try:
            with open(dest / "mysql.sql", "w") as f:
                subprocess.run(
                    ["mysqldump", "-u", "agricol", "-p",
                     "--all-databases"],
                    stdout=f, stderr=subprocess.PIPE, timeout=60)
            log.info("Backup MySQL terminé")
        except Exception as e:
            log.warning("Backup MySQL ignoré", error=str(e))

    def _backup_firmwares(self, dest: Path) -> None:
        fw = Path("/var/lib/pixelos/firmware")
        if fw.exists():
            shutil.copytree(fw, dest / "firmware")

    def _backup_logs(self, dest: Path) -> None:
        log_dir = dest / "logs"
        log_dir.mkdir()
        for log_file in ["/var/log/daemon", "/var/log/messages",
                          "/var/log/pflog"]:
            p = Path(log_file)
            if p.exists():
                shutil.copy2(p, log_dir)

    def _restore_config(self, src: Path) -> None:
        for item in src.iterdir():
            dest = Path("/etc") / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
        log.info("Configuration restaurée")

    def _restore_mysql(self, sql_path: Path) -> None:
        if sql_path.exists():
            try:
                subprocess.run(
                    ["mysql", "-u", "agricol", "-p"],
                    stdin=open(sql_path), timeout=300)
                log.info("Base MySQL restaurée")
            except Exception as e:
                log.error("Échec restauration MySQL", error=str(e))

    def _rotate(self) -> None:
        cutoff = datetime.now() - timedelta(days=self.retention)
        for f in self.base.glob("*.tar.gz"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                log.info("Backup expiré supprimé", path=str(f))

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ["o", "Ko", "Mo", "Go"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}To"
