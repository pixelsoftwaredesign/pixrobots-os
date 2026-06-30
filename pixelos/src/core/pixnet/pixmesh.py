#!/usr/bin/env python3
"""
PixMesh — Réseau maillé P2P PixNet.

Intègre Yggdrasil (réseau IPv6 crypté) et Nebula (overlay mesh)
pour créer un Internet parallèle décentralisé entre nœuds PixelOS.
Chaque nœud est client, serveur et routeur.
"""

import os
import json
import time
import subprocess
import socket
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from threading import Thread, Lock, Event
from typing import Optional


MESH_DIR = "/var/db/pixelos/pixnet"
PEERS_FILE = "mesh_peers.json"
MESH_CONFIG_FILE = "mesh_config.json"

YGGDRASIL_CTL = "yggdrasilctl"
NEBULA_BIN = "nebula"
NEBULA_CONFIG = "/etc/nebula/config.yml"

YGGDRASIL_DEFAULT_PEERS = [
    "tcp://163.172.189.32:4151",   # Yggdrasil public peer 1
    "tcp://51.158.217.187:4151",   # Yggdrasil public peer 2
]

DEFAULT_MESH_CONFIG = {
    "enabled": False,
    "protocol": "yggdrasil",
    "auto_connect": True,
    "listen_port": 0,
    "peer_discovery_interval": 300,
    "max_peers": 50,
    "node_name": "",
    "node_location": "",
    "public_endpoint": "",
    "capabilities": ["crawler", "search", "storage"],
}


class PixMesh:
    def __init__(self):
        self._lock = Lock()
        self.peers = {}
        self.node_id = self._generate_node_id()
        self._ensure_dirs()
        self._load_config()
        self._load_peers()
        self._discovery_thread: Optional[Thread] = None
        self._stop = Event()

    def _ensure_dirs(self):
        Path(MESH_DIR).mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        p = Path(MESH_DIR) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)

    def _generate_node_id(self) -> str:
        import hashlib
        raw = f"{socket.gethostname()}-{time.time()}-{os.urandom(8).hex()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _load_config(self):
        path = self._path(MESH_CONFIG_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.config = {**DEFAULT_MESH_CONFIG, **json.load(f)}
                return
            except Exception:
                pass
        self.config = dict(DEFAULT_MESH_CONFIG)
        self.config["node_name"] = socket.gethostname()
        self._save_config()

    def _save_config(self):
        with open(self._path(MESH_CONFIG_FILE), "w") as f:
            json.dump(self.config, f, indent=2)

    def _load_peers(self):
        path = self._path(PEERS_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.peers = json.load(f)
                return
            except Exception:
                pass
        self.peers = {}

    def _save_peers(self):
        with open(self._path(PEERS_FILE), "w") as f:
            json.dump(self.peers, f, indent=2)

    # ── Yggdrasil integration ─────────────────────────────

    def _yggdrasil_status(self) -> dict:
        try:
            r = subprocess.run(
                [YGGDRASIL_CTL, "getself"],
                capture_output=True, text=True, timeout=5
            )
            out = r.stdout.strip()
            if out:
                data = {}
                for line in out.split("\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        data[k.strip()] = v.strip()
                return {
                    "running": True,
                    "ipv6": data.get("IPv6", ""),
                    "public_key": data.get("public key", ""),
                    "coords": data.get("coords", ""),
                }
        except Exception:
            pass
        return {"running": False}

    def _yggdrasil_peers(self) -> list:
        try:
            r = subprocess.run(
                [YGGDRASIL_CTL, "getpeers"],
                capture_output=True, text=True, timeout=5
            )
            peers = []
            for line in r.stdout.strip().split("\n"):
                if ":" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        peers.append({
                            "uri": parts[0],
                            "ipv6": parts[1] if len(parts) > 1 else "",
                        })
            return peers
        except Exception:
            return []

    # ── Nebula integration ────────────────────────────────

    def _nebula_status(self) -> dict:
        try:
            r = subprocess.run(
                [NEBULA_BIN, "-config", NEBULA_CONFIG, "-status"],
                capture_output=True, text=True, timeout=5
            )
            return {"running": True, "output": r.stdout.strip()[:200]}
        except Exception:
            return {"running": False}

    # ── Peer discovery ────────────────────────────────────

    def discover_peers(self) -> list:
        found = []

        # Yggdrasil peers
        if self.config.get("protocol") == "yggdrasil":
            ygg = self._yggdrasil_peers()
            for p in ygg:
                peer_id = hashlib.sha256(p.get("uri", "").encode()).hexdigest()[:16]
                found.append({
                    "node_id": peer_id,
                    "uri": p.get("uri", ""),
                    "ipv6": p.get("ipv6", ""),
                    "protocol": "yggdrasil",
                    "api_url": f"http://[{p.get('ipv6', '')}]:9999",
                    "first_seen": datetime.now().isoformat(),
                    "last_seen": datetime.now().isoformat(),
                    "uptime": 0,
                    "capabilities": ["unknown"],
                })
                self.peers[peer_id] = found[-1]

        # DNS discovery (.pixel TLD)
        try:
            hostname = f"_pixnet._tcp.pixel."
            r = subprocess.run(
                ["dig", f"@{5300}", hostname, "SRV", "+short"],
                capture_output=True, text=True, timeout=5
            )
            if r.stdout.strip():
                for line in r.stdout.strip().split("\n"):
                    parts = line.split()
                    if len(parts) >= 4:
                        peer_id = hashlib.sha256(parts[3].encode()).hexdigest()[:16]
                        if peer_id not in self.peers:
                            found.append({
                                "node_id": peer_id,
                                "host": parts[3],
                                "port": int(parts[2]),
                                "protocol": "dns_pixel",
                                "api_url": f"http://{parts[3]}:{parts[2]}",
                                "first_seen": datetime.now().isoformat(),
                                "last_seen": datetime.now().isoformat(),
                                "uptime": 0,
                                "capabilities": ["unknown"],
                            })
                            self.peers[peer_id] = found[-1]
        except Exception:
            pass

        self._save_peers()
        return found

    # ── Continuous discovery ──────────────────────────────

    def start_discovery(self, interval: int = 300):
        if self._discovery_thread and self._discovery_thread.is_alive():
            return {"status": "already_running"}

        self._stop.clear()

        def loop():
            self.discover_peers()
            while not self._stop.is_set():
                self._stop.wait(interval)
                if self._stop.is_set():
                    break
                self.discover_peers()

        self._discovery_thread = Thread(target=loop, daemon=True)
        self._discovery_thread.start()
        return {"status": "started"}

    def stop_discovery(self):
        self._stop.set()
        if self._discovery_thread:
            self._discovery_thread.join(timeout=5)
        return {"status": "stopped"}

    # ── Peer management ───────────────────────────────────

    def get_connected_peers(self) -> list:
        now = time.time()
        connected = []
        for peer_id, info in self.peers.items():
            last = info.get("last_seen", "")
            if last:
                try:
                    last_ts = datetime.fromisoformat(last).timestamp()
                    if now - last_ts < 3600:
                        connected.append(info)
                except Exception:
                    connected.append(info)
        return connected

    def get_all_peers(self) -> list:
        return list(self.peers.values())

    def remove_peer(self, peer_id: str) -> dict:
        if peer_id in self.peers:
            del self.peers[peer_id]
            self._save_peers()
            return {"status": "removed"}
        return {"status": "not_found"}

    def update_peer(self, peer_id: str, **kwargs):
        if peer_id in self.peers:
            self.peers[peer_id].update(kwargs)
            self._save_peers()

    def register_self(self, api_url: str, capabilities: list = None):
        self.peers[self.node_id] = {
            "node_id": self.node_id,
            "name": self.config.get("node_name", ""),
            "location": self.config.get("node_location", ""),
            "api_url": api_url,
            "protocol": self.config.get("protocol", "yggdrasil"),
            "capabilities": capabilities or self.config.get("capabilities", []),
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "is_self": True,
        }
        self._save_peers()

    # ── Health check peers ────────────────────────────────

    def ping_peer(self, api_url: str) -> bool:
        try:
            req = urllib.request.Request(f"{api_url}/api/pixnet/ping",
                headers={"User-Agent": "PixMesh/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False

    def health_check(self) -> dict:
        alive = 0
        dead = 0
        for peer_id, info in self.peers.items():
            api = info.get("api_url", "")
            if api and self.ping_peer(api):
                alive += 1
                info["status"] = "online"
            else:
                dead += 1
                info["status"] = "offline"
        self._save_peers()
        return {"alive": alive, "dead": dead, "total": len(self.peers)}

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> dict:
        ygg_status = self._yggdrasil_status()
        connected = self.get_connected_peers()

        caps_count = {}
        for info in self.peers.values():
            for cap in info.get("capabilities", []):
                caps_count[cap] = caps_count.get(cap, 0) + 1

        return {
            "node_id": self.node_id,
            "node_name": self.config.get("node_name", ""),
            "protocol": self.config.get("protocol", ""),
            "enabled": self.config.get("enabled", False),
            "yggdrasil": ygg_status,
            "peers_total": len(self.peers),
            "peers_connected": len(connected),
            "capabilities": caps_count,
            "discovery_running": self._discovery_thread is not None and self._discovery_thread.is_alive(),
        }

    def update_config(self, updates: dict):
        self.config.update(updates)
        self._save_config()
        return {"status": "updated", "config": self.config}
