"""Système DDNS PixelOS — Sous-domaines *.pixelos.org.

Permet aux nœuds d'obtenir un sous-domaine gratuit avec
avertissement de non-responsabilité.
"""

import structlog
import json
import time
import socket
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

log = structlog.get_logger()


class PixelDDNS:
    """Client DNS dynamique pour sous-domaines pixelos.org.

    Gère l'enregistrement, le rafraîchissement et le disclaimer.
    """

    def __init__(self):
        self._registrations: Dict[str, dict] = {}
        self._load()

    def _load(self):
        f = Path("/var/db/pixelos/ddns_registrations.json")
        if f.exists():
            try:
                self._registrations = json.loads(f.read_text())
            except Exception:
                pass

    def _save(self):
        f = Path("/var/db/pixelos/ddns_registrations.json")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(self._registrations, indent=2))

    def register(self, subdomain: str, ip: str = "",
                 node_id: str = "", disclaimer_accepted: bool = False) -> dict:
        """Enregistre un sous-domaine gratuit."""
        if not disclaimer_accepted:
            return {
                "error": "Vous devez accepter la Charte de Souveraineté "
                         "avant d'obtenir un sous-domaine.",
                "code": "charter_required",
            }

        if not subdomain:
            return {"error": "subdomain required", "code": "invalid"}

        ip = ip or self._detect_ip()
        now = datetime.utcnow().isoformat() + "Z"

        self._registrations[subdomain] = {
            "subdomain": f"{subdomain}.pixelos.org",
            "ip": ip,
            "node_id": node_id,
            "created_at": now,
            "updated_at": now,
            "disclaimer_accepted": True,
            "active": True,
        }
        self._save()

        log.info("Sous-domaine enregistré",
                 subdomain=subdomain, ip=ip, node_id=node_id)
        return self._registrations[subdomain]

    def update(self, subdomain: str, ip: str = "") -> Optional[dict]:
        """Met à jour l'adresse IP du sous-domaine."""
        if subdomain not in self._registrations:
            return None
        ip = ip or self._detect_ip()
        self._registrations[subdomain]["ip"] = ip
        self._registrations[subdomain]["updated_at"] = \
            datetime.utcnow().isoformat() + "Z"
        self._save()
        return self._registrations[subdomain]

    def unregister(self, subdomain: str) -> bool:
        if subdomain in self._registrations:
            self._registrations[subdomain]["active"] = False
            self._save()
            return True
        return False

    def get(self, subdomain: str) -> Optional[dict]:
        return self._registrations.get(subdomain)

    def list(self, node_id: str = "") -> list:
        regs = self._registrations.values()
        if node_id:
            regs = [r for r in regs if r.get("node_id") == node_id]
        return list(regs)

    def _detect_ip(self) -> str:
        """Détecte l'IP publique."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def disclaimer(self) -> dict:
        return {
            "title": "Avis de Non-Responsabilité — Sous-domaine Gratuit",
            "text": (
                "Ce sous-domaine est fourni à titre d'outil technique "
                "par la communauté PixelOS. L'utilisateur est seul "
                "responsable des contenus hébergés sur son nœud. "
                "La communauté PixelOS n'a aucun accès technique "
                "à l'infrastructure de l'utilisateur et ne peut être "
                "tenue responsable des activités menées via ce "
                "sous-domaine. Pour une souveraineté totale, "
                "il est recommandé d'acquérir un nom de domaine "
                "personnel."
            ),
            "required_action": "accept_charter",
        }

    def stats(self) -> dict:
        return {
            "total": len(self._registrations),
            "active": sum(1 for r in self._registrations.values()
                          if r.get("active")),
        }


pixel_ddns = PixelDDNS()
