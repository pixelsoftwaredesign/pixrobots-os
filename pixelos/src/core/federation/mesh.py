# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""WireGuard Mesh — réseau P2P entre nœuds PixelOS fédérés."""

from __future__ import annotations
import os, json, subprocess, socket, hashlib, time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import datetime


MESH_DIR = Path("/var/db/pixelos/mesh")
MESH_CONFIG = MESH_DIR / "mesh.conf"
MESH_PEERS = MESH_DIR / "peers"
MESH_KEY = MESH_DIR / "mesh.key"
MESH_PUB = MESH_DIR / "mesh.pub"


@dataclass
class MeshPeer:
    node_id: str
    public_key: str
    endpoint: str          # IP:publique ou DNS
    wg_port: int = 51820
    allowed_ips: str = ""  # ex: "10.100.0.0/16"
    persistent_keepalive: int = 25
    label: str = ""
    last_handshake: str = ""
    online: bool = False


class WireGuardMesh:
    """Gère le réseau maillé WireGuard entre nœuds PixelOS."""

    MESH_NETWORK = "10.100.0.0/16"
    MESH_PORT = 51821

    def __init__(self):
        os.makedirs(MESH_PEERS, exist_ok=True)
        self.iface = "wgmesh"
        self.config_path = f"/etc/wireguard/{self.iface}.conf"

    def init_mesh(self, node_id: str) -> dict:
        """Initialise l'interface mesh WireGuard."""
        # Générer les clés si nécessaire
        if not MESH_KEY.exists():
            subprocess.run(["wg", "genkey"], capture_output=True,
                           stdout=open(MESH_KEY, "w"))
            subprocess.run(["wg", "pubkey"],
                           stdin=open(MESH_KEY),
                           capture_output=True,
                           stdout=open(MESH_PUB, "w"))

        privkey = MESH_KEY.read_text().strip()
        pubkey = MESH_PUB.read_text().strip()

        # Calculer l'IP mesh à partir du node_id hash
        mesh_ip = self._hash_to_ip(node_id)

        config = (
            f"[Interface]\n"
            f"PrivateKey = {privkey}\n"
            f"Address = {mesh_ip}/16\n"
            f"ListenPort = {self.MESH_PORT}\n"
            f"Table = off\n"
        )

        # Ajouter les pairs connus
        for peer_file in sorted(MESH_PEERS.glob("*.json")):
            try:
                peer = json.load(open(peer_file))
                config += (
                    f"\n[Peer]\n"
                    f"PublicKey = {peer['public_key']}\n"
                    f"Endpoint = {peer['endpoint']}:{peer.get('wg_port', 51821)}\n"
                    f"AllowedIPs = {peer.get('allowed_ips', '10.100.0.0/16')}\n"
                    f"PersistentKeepalive = {peer.get('persistent_keepalive', 25)}\n"
                )
            except:
                pass

        # Écrire la config
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w") as f:
            f.write(config)

        return {
            "interface": self.iface,
            "address": mesh_ip,
            "public_key": pubkey,
            "peers": len(list(MESH_PEERS.glob("*.json"))),
        }

    def _hash_to_ip(self, node_id: str) -> str:
        """Convertit un node_id en IP unique dans le réseau mesh."""
        h = hashlib.sha256(node_id.encode()).hexdigest()
        third = int(h[:2], 16)
        fourth = int(h[2:4], 16)
        return f"10.100.{third}.{fourth}"

    def add_mesh_peer(self, peer_info: dict) -> bool:
        """Ajoute un pair au réseau mesh."""
        peer = MeshPeer(
            node_id=peer_info.get("node_id", ""),
            public_key=peer_info.get("public_key", ""),
            endpoint=peer_info.get("endpoint", ""),
            wg_port=peer_info.get("wg_port", self.MESH_PORT),
            label=peer_info.get("nickname", peer_info.get("node_id", "")),
            last_handshake=datetime.now().isoformat(),
        )
        peer_file = MESH_PEERS / f"{peer.node_id}.json"
        with open(peer_file, "w") as f:
            json.dump(asdict(peer), f, ensure_ascii=False)
        return True

    def remove_mesh_peer(self, node_id: str) -> bool:
        peer_file = MESH_PEERS / f"{node_id}.json"
        if peer_file.exists():
            peer_file.unlink()
            return True
        return False

    def list_mesh_peers(self) -> list[dict]:
        peers = []
        for f in sorted(MESH_PEERS.glob("*.json")):
            try:
                data = json.load(open(f))
                # Vérifier si en ligne
                data["online"] = self._peer_online(data.get("endpoint", ""))
                peers.append(data)
            except:
                pass
        return peers

    def _peer_online(self, endpoint: str) -> bool:
        if not endpoint:
            return False
        try:
            host, port = endpoint.split(":")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((host, int(port) + 1))  # port_api = wg_port + 1
            s.close()
            return True
        except:
            return False

    def bootstrap_peers(self, bootstrap_nodes: list[str]) -> list[dict]:
        """Découvre des pairs via des nœuds d'amorçage."""
        discovered = []
        for node in bootstrap_nodes:
            try:
                url = f"http://{node}:9999/api/federation/announce"
                import requests
                r = requests.get(f"http://{node}:9999/api/node/peers", timeout=5)
                if r.ok:
                    data = r.json()
                    for p in data.get("peers", []):
                        if p.get("node_id") and p.get("public_key"):
                            self.add_mesh_peer(p)
                            discovered.append(p)
            except:
                pass
        return discovered

    def start_mesh(self) -> dict:
        """Active l'interface mesh WireGuard."""
        # S'assurer que la config existe
        if not os.path.exists(self.config_path):
            return {"status": "error", "message": "Config mesh introuvable"}
        try:
            subprocess.run(["wg-quick", "up", self.iface],
                           check=True, capture_output=True)
            return {"status": "ok", "message": f"Interface {self.iface} active"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": e.stderr.decode()}

    def stop_mesh(self) -> dict:
        try:
            subprocess.run(["wg-quick", "down", self.iface],
                           check=True, capture_output=True)
            return {"status": "ok", "message": f"Interface {self.iface} arrêtée"}
        except:
            return {"status": "error", "message": "Impossible d'arrêter le mesh"}

    def mesh_status(self) -> dict:
        peers = self.list_mesh_peers()
        online = sum(1 for p in peers if p["online"])
        return {
            "interface": self.iface,
            "network": self.MESH_NETWORK,
            "peers_total": len(peers),
            "peers_online": online,
            "peers": peers,
        }


wireguard_mesh = WireGuardMesh()
