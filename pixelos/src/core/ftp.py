# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""FTP Manager — Gestion des utilisateurs et zones FTP."""

import os, subprocess, json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


FTP_BASE = Path("/var/ftp")
FTP_CONF = Path("/etc/ftpd.conf")
FTP_USERS = Path("/etc/ftpusers")


@dataclass
class FTPZone:
    name: str
    user: str
    path: str
    enabled: bool = True


class FTPManager:
    """Gère les utilisateurs et répertoires FTP par zone agricole."""

    DEFAULT_ZONES = [
        "zone-nord", "zone-serre-a", "zone-serre-b",
        "zone-verger", "zone-plein-champ", "pepiniere",
    ]

    def __init__(self, base: Path = FTP_BASE):
        self.base = base

    def list_zones(self) -> list[FTPZone]:
        zones = []
        for d in sorted(self.base.iterdir()):
            if d.is_dir() and d.name.startswith("zone-"):
                zones.append(FTPZone(
                    name=d.name,
                    user=f"ftp-{d.name}",
                    path=str(d),
                ))
        return zones

    def create_zone(self, zone_name: str) -> dict:
        """Crée un utilisateur et répertoire FTP pour une nouvelle zone."""
        user = f"ftp-{zone_name}"
        home = self.base / zone_name

        if home.exists():
            return {"status": "error", "message": f"Zone {zone_name} existe déjà"}

        subprocess.run(["useradd", "-m", "-d", str(home), "-s", "/sbin/nologin",
                        "-g", "ftp-techniciens", user], capture_output=True)
        for d in ["uploads", "logs", "partage"]:
            (home / d).mkdir(parents=True, exist_ok=True)
        (home / "logs").chmod(0o775)
        (home / "uploads").chmod(0o775)
        (home / "partage").chmod(0o750)

        # Ajouter aux utilisateurs FTP autorisés
        with open(FTP_USERS, "a") as f:
            f.write(f"{user}\n")

        return {
            "status": "ok",
            "zone": zone_name,
            "user": user,
            "path": str(home),
        }

    def delete_zone(self, zone_name: str) -> dict:
        """Supprime un utilisateur et répertoire FTP."""
        user = f"ftp-{zone_name}"
        home = self.base / zone_name

        subprocess.run(["userdel", "-r", user], capture_output=True)
        if home.exists():
            subprocess.run(["rm", "-rf", str(home)])

        # Retirer de ftpusers
        if FTP_USERS.exists():
            lines = FTP_USERS.read_text().splitlines()
            lines = [l for l in lines if l.strip() != user]
            FTP_USERS.write_text("\n".join(lines) + "\n")

        return {"status": "ok", "zone": zone_name}

    def status(self) -> dict:
        zones = self.list_zones()
        return {
            "total_zones": len(zones),
            "base_path": str(self.base),
            "zones": [asdict(z) for z in zones],
        }


ftp_manager = FTPManager()
