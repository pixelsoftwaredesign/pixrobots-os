# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""Portal Bootstrap PixelOS — page communautaire + téléchargement ISO."""

from __future__ import annotations
import json, os, platform, time
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict


BOOTSTRAP_DIR = Path("/var/db/pixelos/bootstrap")
BOOTSTRAP_CONFIG = BOOTSTRAP_DIR / "community.json"
BOOTSTRAP_MIRRORS = BOOTSTRAP_DIR / "mirrors.json"
BOOTSTRAP_NODES = BOOTSTRAP_DIR / "seed_nodes.json"


@dataclass
class BootstrapNode:
    """Nœud d'amorçage du réseau PixelOS."""
    node_id: str
    public_key: str
    address: str          # IP publique ou DNS
    wg_port: int = 51820
    api_port: int = 9999
    nickname: str = ""
    country: str = ""
    region: str = ""
    role: str = "seed"    # seed, relay, hub
    last_seen: str = ""
    version: str = ""
    species_count: int = 0


@dataclass
class CommunityStats:
    """Statistiques de la communauté mondiale."""
    total_nodes: int = 0
    total_countries: int = 0
    total_species: int = 0
    total_members: int = 0
    total_proposals: int = 0
    online_nodes: int = 0
    latest_iso_version: str = ""
    latest_node_added: str = ""


class BootstrapPortal:
    """Portail d'amorçage pour la communauté PixelOS.

    Rôle:
      - Maintient la liste des nœuds fondateurs (seed nodes)
      - Sert la page de téléchargement de l'ISO
      - Agège les statistiques globales du réseau
      - Permet aux nouveaux membres de rejoindre
    """

    MIRRORS_DEFAULT = [
        {"name": "PixelOS Association (Europe)", "url": "https://dl.pixelos.org/iso/",
         "country": "FR", "status": "official"},
        {"name": "Africa Agri-Hub", "url": "https://africa.pixelos.org/iso/",
         "country": "MA", "status": "community"},
        {"name": "Asia Pacific Mirror", "url": "https://asia.pixelos.org/iso/",
         "country": "JP", "status": "community"},
    ]

    def __init__(self, node_id: str = "", public_key: str = "",
                 nickname: str = "", country: str = "",
                 public_ip: str = ""):
        os.makedirs(BOOTSTRAP_DIR, exist_ok=True)
        self.node = BootstrapNode(
            node_id=node_id or self._generate_node_id(),
            public_key=public_key or "",
            address=public_ip or self._detect_public_ip(),
            nickname=nickname or f"Node-{(node_id or 'xxxx')[:8]}",
            country=country or "",
            last_seen=datetime.now().isoformat(),
        )

    def _generate_node_id(self) -> str:
        import hashlib
        raw = f"{time.time()}{platform.node()}{os.urandom(8).hex()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _detect_public_ip(self) -> str:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "0.0.0.0"

    def register_seed(self) -> dict:
        """Enregistre ce nœud comme seed pour la communauté."""
        seeds = self.get_seed_nodes()
        # Vérifier si déjà enregistré
        for s in seeds:
            if s["node_id"] == self.node.node_id:
                return {"status": "ok", "message": "Déjà enregistré"}

        seeds.append(asdict(self.node))
        with open(BOOTSTRAP_NODES, "w") as f:
            json.dump(seeds, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "message": f"Nœud seed enregistré: {self.node.node_id}"}

    def get_seed_nodes(self) -> list[dict]:
        if not BOOTSTRAP_NODES.exists():
            return []
        return json.load(open(BOOTSTRAP_NODES))

    def get_mirrors(self) -> list[dict]:
        if not BOOTSTRAP_MIRRORS.exists():
            return self.MIRRORS_DEFAULT
        return json.load(open(BOOTSTRAP_MIRRORS))

    def add_mirror(self, name: str, url: str,
                   country: str = "", status: str = "community") -> dict:
        mirrors = self.get_mirrors()
        mirrors.append({
            "name": name, "url": url,
            "country": country, "status": status,
        })
        with open(BOOTSTRAP_MIRRORS, "w") as f:
            json.dump(mirrors, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "count": len(mirrors)}

    def get_iso_url(self, version: str = "latest") -> str:
        """Retourne l'URL de téléchargement de l'ISO PixelOS."""
        mirrors = self.get_mirrors()
        if not mirrors:
            return ""
        # Essayer un miroir officiel d'abord
        for m in mirrors:
            if m["status"] == "official":
                return m["url"] + f"pixelos-{version}.iso"
        return mirrors[0]["url"] + f"pixelos-{version}.iso"

    def community_stats(self) -> dict:
        """Statistiques agrégées de la communauté."""
        seeds = self.get_seed_nodes()
        countries = set(s.get("country", "") for s in seeds if s.get("country"))

        return {
            "total_nodes": len(seeds),
            "total_countries": len(countries),
            "countries": sorted(countries),
            "online_nodes": sum(1 for s in seeds if s.get("last_seen", "")),
            "seed_nodes": seeds[:10],  # Top 10 seeds
            "mirrors": self.get_mirrors(),
            "iso_url": self.get_iso_url(),
            "portal_version": "2.0",
            "timestamp": datetime.now().isoformat(),
        }

    def join_request(self, nickname: str, email: str = "",
                     country: str = "", reason: str = "") -> dict:
        """Enregistre une demande de rejoindre la communauté."""
        request = {
            "nickname": nickname,
            "email": email,
            "country": country,
            "reason": reason,
            "requested_at": datetime.now().isoformat(),
            "node_id": self.node.node_id,
            "status": "pending",
        }
        requests_file = BOOTSTRAP_DIR / "join_requests.json"
        existing = []
        if requests_file.exists():
            existing = json.load(open(requests_file))
        existing.append(request)
        with open(requests_file, "w") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        return request


bootstrap_portal = BootstrapPortal()
