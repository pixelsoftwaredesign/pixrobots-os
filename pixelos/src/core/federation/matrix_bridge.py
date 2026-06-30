"""Pont Matrix — Messagerie temps réel pour la communauté PixelOS.

Permet:
  - Notifications automatiques (nouveau nœud, nouvelle espèce, proposition)
  - Canal d'entraide entre agriculteurs membres
  - Alertes conservation (espèce en danger critique)
"""

from __future__ import annotations
import json, os, requests, hashlib, time
from pathlib import Path
from typing import Optional
from datetime import datetime
from dataclasses import dataclass


MATRIX_DIR = Path("/var/db/pixelos/matrix")
MATRIX_CONFIG = MATRIX_DIR / "config.json"
MATRIX_CACHE = MATRIX_DIR / "cache"


@dataclass
class MatrixConfig:
    """Configuration du bot Matrix PixelOS."""
    homeserver: str = "https://matrix.pixelos.org"
    user_id: str = "@pixelos-bot:matrix.pixelos.org"
    access_token: str = ""
    room_id: str = "!community:matrix.pixelos.org"   # Salon général
    room_alerts: str = "!alerts:matrix.pixelos.org"  # Alertes conservation
    room_gov: str = "!governance:matrix.pixelos.org" # Gouvernance
    enabled: bool = False


class MatrixBridge:
    """Pont entre PixelOS et Matrix pour la communauté."""

    def __init__(self):
        os.makedirs(MATRIX_DIR, exist_ok=True)
        os.makedirs(MATRIX_CACHE, exist_ok=True)
        self.config = self._load_config()

    def _load_config(self) -> MatrixConfig:
        if MATRIX_CONFIG.exists():
            return MatrixConfig(**json.load(open(MATRIX_CONFIG)))
        return MatrixConfig()

    def _save_config(self):
        with open(MATRIX_CONFIG, "w") as f:
            json.dump({
                "homeserver": self.config.homeserver,
                "user_id": self.config.user_id,
                "access_token": self.config.access_token,
                "room_id": self.config.room_id,
                "room_alerts": self.config.room_alerts,
                "room_gov": self.config.room_gov,
                "enabled": self.config.enabled,
            }, f, ensure_ascii=False, indent=2)

    def configure(self, homeserver: str = "", user_id: str = "",
                  access_token: str = "", room: str = "") -> dict:
        """Configure la connexion Matrix."""
        if homeserver:
            self.config.homeserver = homeserver
        if user_id:
            self.config.user_id = user_id
        if access_token:
            self.config.access_token = access_token
        if room:
            self.config.room_id = room
        self.config.enabled = bool(access_token)
        self._save_config()
        return {"status": "ok", "enabled": self.config.enabled}

    def _send(self, room: str, message: str,
              msgtype: str = "m.text") -> bool:
        """Envoie un message Matrix."""
        if not self.config.enabled or not self.config.access_token:
            return False
        try:
            url = f"{self.config.homeserver}/_matrix/client/v3/rooms/" \
                  f"{room}/send/m.room.message"
            headers = {
                "Authorization": f"Bearer {self.config.access_token}",
                "Content-Type": "application/json",
            }
            body = {
                "msgtype": msgtype,
                "body": message,
                "formatted_body": message.replace("\n", "<br>"),
                "format": "org.matrix.custom.html",
            }
            r = requests.post(url, json=body, headers=headers, timeout=10)
            return r.ok
        except:
            return False

    def notify_new_node(self, node_id: str, nickname: str,
                        country: str = "") -> bool:
        """Annonce l'arrivée d'un nouveau nœud."""
        msg = (
            f"🌱 **Nouveau nœud PixelOS rejoint le réseau !**\n"
            f"ID: `{node_id}`\n"
            f"Nom: {nickname}\n"
            f"Pays: {country or 'Non spécifié'}\n"
            f"Bienvenue dans la communauté internationale !"
        )
        return self._send(self.config.room_id, msg)

    def notify_new_species(self, scientific_name: str, common_name: str,
                            conservation_status: str, node_id: str) -> bool:
        """Annonce une nouvelle espèce enregistrée."""
        status_icons = {
            "gravement_menacee": "🔴 CR",
            "menacee": "🟠 EN",
            "vulnerable": "🟡 VU",
            "quasi_menacee": "🔵 NT",
            "preoccupation_mineure": "🟢 LC",
        }
        icon = status_icons.get(conservation_status, "⚪")
        msg = (
            f"🌿 **Nouvelle espèce enregistrée**\n"
            f"*{scientific_name}* ({common_name})\n"
            f"Statut: {icon}\n"
            f"Enregistré par: `{node_id[:12]}`"
        )
        # Envoyer dans le salon général
        self._send(self.config.room_id, msg)
        # Si espèce menacée, envoyer aussi dans le salon alertes
        if conservation_status in ("gravement_menacee", "menacee"):
            self._send(self.config.room_alerts, msg)
        return True

    def notify_alert(self, title: str, description: str,
                     severity: str = "info") -> bool:
        """Envoie une alerte à la communauté."""
        icons = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}
        icon = icons.get(severity, "ℹ️")
        msg = f"{icon} **{title}**\n{description}"
        return self._send(self.config.room_alerts, msg)

    def notify_proposal(self, proposal_id: str, title: str,
                         proposer: str, deadline: str) -> bool:
        """Annonce une nouvelle proposition de gouvernance."""
        msg = (
            f"📋 **Nouvelle proposition de gouvernance**\n"
            f"ID: `{proposal_id}`\n"
            f"Titre: {title}\n"
            f"Proposé par: `{proposer[:12]}`\n"
            f"Vote jusqu'au: {deadline[:16]}\n"
            f"Voter: `pixelos federation gov-vote --proposal-id {proposal_id}`"
        )
        return self._send(self.config.room_gov, msg)

    def notify_update(self, version: str, changelog: str) -> bool:
        """Annonce une mise à jour disponible."""
        msg = (
            f"🔄 **PixelOS {version} disponible**\n"
            f"Changements:\n{changelog}\n"
            f"Mettre à jour: `pixelos update`"
        )
        return self._send(self.config.room_id, msg)

    def status(self) -> dict:
        """État de la connexion Matrix."""
        return {
            "enabled": self.config.enabled,
            "homeserver": self.config.homeserver,
            "user_id": self.config.user_id,
            "room_main": self.config.room_id,
            "room_alerts": self.config.room_alerts,
            "room_governance": self.config.room_gov,
        }


matrix_bridge = MatrixBridge()
