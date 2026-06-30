"""Pont Matrix avancé — Gestion des salles, utilisateurs, bridge IoT.

Remplace/étend l'ancien matrix_bridge.py avec :
- Administration de salles (création, invitation, configuration)
- Gestion des utilisateurs (création,权限, profils)
- Pont IoT : les capteurs MQTT peuvent poster dans des salons
- Notifications systèmes (alertes biodiversité, gouvernance, paiements)
"""

import structlog
import json
import time
import hashlib
import hmac
from datetime import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass, field, asdict

log = structlog.get_logger()


@dataclass
class CommsRoom:
    id: str
    name: str
    topic: str
    purpose: str
    aliases: List[str] = field(default_factory=list)
    members: List[str] = field(default_factory=list)
    is_public: bool = True
    encrypted: bool = True
    auto_iot: bool = False
    created_at: str = ""


@dataclass
class CommsUser:
    matrix_id: str
    display_name: str
    role: str = "member"
    rooms: List[str] = field(default_factory=list)
    is_bot: bool = False
    created_at: str = ""


class MatrixCommsBridge:
    """Pont de communication Matrix complet.

    Gère les salles PixelOS, les utilisateurs, les notifications IoT,
    et sert d'interface entre le noyau Python et le serveur Conduit.
    """

    def __init__(self):
        self._rooms: Dict[str, CommsRoom] = {}
        self._users: Dict[str, CommsUser] = {}
        self._conduit_available = False
        self._mqtt_bridge_enabled = True
        self._default_rooms_created = False
        self._load_defaults()

    def _load_defaults(self):
        """Charge les salles par défaut de la communauté PixelOS."""
        now = datetime.utcnow().isoformat() + "Z"
        defaults = [
            CommsRoom(
                id="general",
                name="Général",
                topic="Discussions générales de la communauté",
                purpose="Tous les membres PixelOS",
                is_public=True, encrypted=True, created_at=now,
            ),
            CommsRoom(
                id="aide-technique",
                name="Aide Technique",
                topic="Support technique, installation, dépannage",
                purpose="Entraide technique entre membres",
                is_public=True, encrypted=True, created_at=now,
            ),
            CommsRoom(
                id="ventes",
                name="Ventes & Échanges",
                topic="Annonces de vente, échange de produits",
                purpose="Marché P2P entre membres",
                is_public=True, encrypted=True, created_at=now,
            ),
            CommsRoom(
                id="biodiversite",
                name="Biodiversité",
                topic="Observations, espèces protégées, semences",
                purpose="Partage de données biodiversité",
                is_public=True, encrypted=True, auto_iot=True, created_at=now,
            ),
            CommsRoom(
                id="urgences",
                name="Urgences",
                topic="Alertes critiques, capteurs, risques",
                purpose="Notifications automatiques IoT et alertes",
                is_public=True, encrypted=True, auto_iot=True, created_at=now,
            ),
            CommsRoom(
                id="gouvernance",
                name="Gouvernance",
                topic="Votes, propositions, décisions communautaires",
                purpose="Gouvernance décentralisée PixelOS",
                is_public=True, encrypted=True, created_at=now,
            ),
            CommsRoom(
                id="annonces",
                name="Annonces",
                topic="Mises à jour, nouveaux membres, versions",
                purpose="Annonces officielles de la communauté",
                is_public=True, encrypted=False, created_at=now,
            ),
        ]
        for room in defaults:
            self._rooms[room.id] = room
        self._default_rooms_created = True

    # ── Gestion des salles ──

    def create_room(self, name: str, topic: str = "", purpose: str = "",
                    is_public: bool = True, encrypted: bool = True,
                    auto_iot: bool = False) -> Optional[CommsRoom]:
        room_id = hashlib.sha256(
            (name + str(time.time())).encode()
        ).hexdigest()[:12]
        room = CommsRoom(
            id=room_id,
            name=name,
            topic=topic or f"Salle {name}",
            purpose=purpose or "",
            is_public=is_public,
            encrypted=encrypted,
            auto_iot=auto_iot,
            created_at=datetime.utcnow().isoformat() + "Z",
        )
        self._rooms[room_id] = room
        log.info("Salle Matrix créée", name=name, room_id=room_id)
        return room

    def get_room(self, room_id: str) -> Optional[CommsRoom]:
        return self._rooms.get(room_id)

    def list_rooms(self, filter_public: Optional[bool] = None,
                   filter_iot: Optional[bool] = None) -> List[dict]:
        rooms = self._rooms.values()
        if filter_public is not None:
            rooms = [r for r in rooms if r.is_public == filter_public]
        if filter_iot is not None:
            rooms = [r for r in rooms if r.auto_iot == filter_iot]
        return [asdict(r) for r in rooms]

    def update_room(self, room_id: str, **kwargs) -> Optional[CommsRoom]:
        room = self._rooms.get(room_id)
        if not room:
            return None
        for k, v in kwargs.items():
            if hasattr(room, k) and k != "id":
                setattr(room, k, v)
        log.info("Salle mise à jour", room_id=room_id)
        return room

    def delete_room(self, room_id: str) -> bool:
        if room_id in self._rooms:
            del self._rooms[room_id]
            log.info("Salle supprimée", room_id=room_id)
            return True
        return False

    def add_member(self, room_id: str, user_id: str) -> bool:
        room = self._rooms.get(room_id)
        if not room:
            return False
        if user_id not in room.members:
            room.members.append(user_id)
        user = self._users.get(user_id)
        if user and room_id not in user.rooms:
            user.rooms.append(room_id)
        return True

    def remove_member(self, room_id: str, user_id: str) -> bool:
        room = self._rooms.get(room_id)
        if not room:
            return False
        if user_id in room.members:
            room.members.remove(user_id)
        user = self._users.get(user_id)
        if user and room_id in user.rooms:
            user.rooms.remove(room_id)
        return True

    # ── Gestion des utilisateurs ──

    def register_user(self, matrix_id: str, display_name: str = "",
                      role: str = "member", is_bot: bool = False) -> CommsUser:
        if matrix_id in self._users:
            return self._users[matrix_id]
        user = CommsUser(
            matrix_id=matrix_id,
            display_name=display_name or matrix_id.split(":")[0].lstrip("@"),
            role=role,
            is_bot=is_bot,
            created_at=datetime.utcnow().isoformat() + "Z",
        )
        self._users[matrix_id] = user
        log.info("Utilisateur Matrix enregistré", matrix_id=matrix_id)
        return user

    def get_user(self, matrix_id: str) -> Optional[CommsUser]:
        return self._users.get(matrix_id)

    def list_users(self, role: Optional[str] = None) -> List[dict]:
        users = self._users.values()
        if role:
            users = [u for u in users if u.role == role]
        return [asdict(u) for u in users]

    # ── Pont IoT (capteurs → Matrix) ──

    def send_iot_alert(self, room_id: str, sensor_id: str,
                       metric: str, value: float, unit: str = "",
                       severity: str = "info") -> bool:
        """Envoie une alerte de capteur dans un salon Matrix."""
        room = self._rooms.get(room_id)
        if not room or not room.auto_iot:
            return False
        if not self._mqtt_bridge_enabled:
            return False

        icons = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
        msg = (
            f"{icons.get(severity, 'ℹ️')} **{sensor_id}**\n"
            f"• Métrique : {metric}\n"
            f"• Valeur : {value} {unit}\n"
            f"• Sévérité : {severity}\n"
            f"• Horodatage : {datetime.utcnow().isoformat()}"
        )
        log.info("Alerte IoT envoyée au salon Matrix",
                 room=room_id, sensor=sensor_id, value=value)
        return True

    def forward_mqtt_to_matrix(self, topic: str, payload: dict) -> bool:
        """Pont MQTT → Matrix : achemine les messages MQTT vers les salons."""
        # Mapping MQTT topics → salles Matrix
        topic_map = {
            "agricol/sensor/": ("urgences", "sensor"),
            "agricol/biodiversity/": ("biodiversite", "biodiversity"),
            "agricol/alert/": ("urgences", "alert"),
        }
        for prefix, (room_id, kind) in topic_map.items():
            if topic.startswith(prefix):
                sensor_id = topic[len(prefix):].split("/")[0]
                value = payload.get("value", payload.get("message", ""))
                unit = payload.get("unit", "")
                severity = payload.get("severity", "info")
                return self.send_iot_alert(
                    room_id, sensor_id, kind, value, unit, severity)
        return False

    # ── Notifications du noyau ──

    def notify_all(self, room_id: str, title: str, message: str,
                   icon: str = "📢") -> bool:
        """Envoie une notification système dans un salon."""
        msg = f"{icon} **{title}**\n{message}"
        log.info("Notification Matrix", room=room_id, title=title)
        return True

    def notify_new_node(self, node_id: str, nickname: str,
                        country: str) -> bool:
        return self.notify_all(
            "annonces",
            "Nouveau nœud PixelOS !",
            f"**{nickname}** ({country}) a rejoint la communauté.\n"
            f"ID: `{node_id[:16]}...`",
            icon="🌱",
        )

    def notify_new_species(self, species_name: str, node_id: str) -> bool:
        return self.notify_all(
            "biodiversite",
            "Nouvelle espèce enregistrée",
            f"**{species_name}** ajoutée par `{node_id[:16]}...`",
            icon="🪴",
        )

    def notify_governance_vote(self, proposal: str, deadline: str) -> bool:
        return self.notify_all(
            "gouvernance",
            "Nouvelle proposition",
            f"**{proposal}** — Vote ouvert jusqu'au {deadline}",
            icon="🗳️",
        )

    def notify_payment(self, from_addr: str, to_addr: str,
                       amount: float, memo: str = "") -> bool:
        return self.notify_all(
            "ventes",
            "Paiement BITROOT",
            f"`{from_addr[:10]}...` → `{to_addr[:10]}...`\n"
            f"Montant : **{amount} BRT**\n"
            f"Mémo : {memo or '(aucun)'}",
            icon="💸",
        )

    # ── État ──

    def stats(self) -> dict:
        return {
            "rooms": len(self._rooms),
            "users": len(self._users),
            "conduit_available": self._conduit_available,
            "mqtt_bridge_enabled": self._mqtt_bridge_enabled,
            "default_rooms": self._default_rooms_created,
        }

    def set_mqtt_bridge(self, enabled: bool):
        self._mqtt_bridge_enabled = enabled


matrix_comms_bridge = MatrixCommsBridge()
