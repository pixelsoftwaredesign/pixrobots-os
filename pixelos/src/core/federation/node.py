# Pixel Software Design � Copyright 2026
"""Protocole PixelNode — auto-provisioning, clés, fédération P2P."""

from __future__ import annotations
import os, json, socket, subprocess, hashlib, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from datetime import datetime


NODE_DIR = Path(os.environ.get("PIXELOS_NODE_DIR", "/var/db/pixelos/node"))
NODE_CONFIG = NODE_DIR / "node.json"
NODE_KEY = NODE_DIR / "node.key"
NODE_PUB = NODE_DIR / "node.pub"
PEERS_DIR = NODE_DIR / "peers"
ANNOUNCE_FILE = NODE_DIR / "announce.json"


@dataclass
class PixelNodeIdentity:
    """Identité unique d'un nœud PixelOS dans le réseau mondial."""
    node_id: str = ""
    public_key: str = ""
    nickname: str = ""
    region: str = ""
    country: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    version: str = ""
    features: list[str] = field(default_factory=lambda: [
        "biodiversity", "iot", "ftp", "dns"
    ])
    ip_vpn: str = ""       # IP sur le réseau WireGuard
    port_api: int = 9999

    first_seen: str = ""
    last_seen: str = ""

    # Endpoint public (si exposé)
    endpoint: str = ""     # IP publique ou nom DNS
    wg_port: int = 51820

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent=2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class NodeManager:
    """Gère l'identité, les clés et les pairs du nœud."""

    def __init__(self, data_dir: Path = NODE_DIR):
        self.data_dir = data_dir
        self.peers_dir = data_dir / "peers"
        os.makedirs(self.peers_dir, exist_ok=True)

        # Charger ou générer l'identité
        if NODE_CONFIG.exists():
            self.identity = self._load_identity()
        else:
            self.identity = self._generate_identity()

    def _generate_keys(self) -> tuple[str, str]:
        """Génère paire de clés Ed25519 via OpenBSD ou Python."""
        priv_path = NODE_KEY
        pub_path = NODE_PUB
        if os.path.exists(priv_path) and os.path.exists(pub_path):
            return (open(priv_path).read().strip(),
                    open(pub_path).read().strip())
        # Utiliser openssl ou python
        try:
            # Essayer OpenBSD's signify ou openssl
            subprocess.run([
                "openssl", "genpkey", "-algorithm", "ED25519",
                "-out", str(priv_path)
            ], check=True, capture_output=True)
            subprocess.run([
                "openssl", "pkey", "-in", str(priv_path),
                "-pubout", "-out", str(pub_path)
            ], check=True, capture_output=True)
        except:
            # Fallback: clé simple avec hash
            seed = os.urandom(32).hex()
            priv = hashlib.sha3_256(f"pixelos-node-{seed}".encode()).hexdigest()
            pub = hashlib.sha3_256(priv.encode()).hexdigest()
            open(priv_path, "w").write(priv)
            open(pub_path, "w").write(pub)
        return (open(priv_path).read().strip(),
                open(pub_path).read().strip())

    def _generate_identity(self) -> PixelNodeIdentity:
        priv, pub = self._generate_keys()
        node_id = hashlib.sha3_256(pub.encode()).hexdigest()[:16]
        hostname = socket.gethostname()

        identity = PixelNodeIdentity(
            node_id=node_id,
            public_key=pub,
            nickname=hostname,
            version=self._get_version(),
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
        )
        self._save_identity(identity)
        return identity

    def _load_identity(self) -> PixelNodeIdentity:
        data = json.load(open(NODE_CONFIG))
        return PixelNodeIdentity(**data)

    def _save_identity(self, identity: PixelNodeIdentity):
        with open(NODE_CONFIG, "w") as f:
            f.write(identity.to_json())

    def _get_version(self) -> str:
        try:
            r = subprocess.run(["pixelos", "--version"],
                               capture_output=True, text=True, timeout=3)
            return r.stdout.strip() or "2.0.0"
        except:
            return "2.0.0"

    def announce(self) -> dict:
        """Prépare les données publiques de ce nœud."""
        self.identity.last_seen = datetime.now().isoformat()
        self._save_identity(self.identity)
        data = self.identity.to_dict()
        # Ajouter les stats biodiversité locale
        try:
            from core.federation.biodiversity import biodiversity_registry
            data["biodiversity"] = biodiversity_registry.stats()
        except:
            data["biodiversity"] = {"total": 0}
        # Ajouter les pairs connus
        data["peers_count"] = len(self.list_peers())
        with open(ANNOUNCE_FILE, "w") as f:
            json.dump(data, f)
        return data

    def add_peer(self, peer_announce: dict) -> bool:
        """Ajoute ou met à jour un pair connu."""
        peer_id = peer_announce.get("node_id", "")
        if not peer_id:
            return False
        peer_file = self.peers_dir / f"{peer_id}.json"
        peer_announce["last_seen"] = datetime.now().isoformat()
        with open(peer_file, "w") as f:
            json.dump(peer_announce, f, ensure_ascii=False)
        return True

    def remove_peer(self, peer_id: str) -> bool:
        peer_file = self.peers_dir / f"{peer_id}.json"
        if peer_file.exists():
            peer_file.unlink()
            return True
        return False

    def list_peers(self) -> list[dict]:
        peers = []
        for f in sorted(self.peers_dir.glob("*.json")):
            try:
                peers.append(json.load(open(f)))
            except:
                pass
        return peers

    def discover_peers_dht(self) -> list[dict]:
        """Découvre des pairs via DHT simplifié (broadcast WireGuard)."""
        peers = []
        # Scanner le réseau WireGuard 10.0.0.0/24
        for i in range(2, 255):
            ip = f"10.0.0.{i}"
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                s.connect((ip, 9999))
                s.send(b"GET /api/node/ping HTTP/1.0\r\nHost: localhost\r\n\r\n")
                data = s.recv(4096)
                s.close()
                if data:
                    peers.append({"ip": ip, "discovered": True})
            except:
                pass
        return peers

    def federation_status(self) -> dict:
        peers = self.list_peers()
        return {
            "node_id": self.identity.node_id,
            "nickname": self.identity.nickname,
            "public_key": self.identity.public_key[:20] + "...",
            "peers_known": len(peers),
            "peers_online": sum(1 for p in peers if self._peer_online(p)),
        }

    def _peer_online(self, peer: dict) -> bool:
        ip = peer.get("ip_vpn", "") or peer.get("endpoint", "")
        if not ip:
            return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((ip, peer.get("port_api", 9999)))
            s.close()
            return True
        except:
            return False


node_manager = NodeManager()
