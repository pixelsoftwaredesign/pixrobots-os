# Pixel Software Design � Copyright 2026
#!/usr/bin/env python3
"""
PixDHT — Table de hachage distribuée + nommage décentralisé PixNet.

Remplace le DNS centralisé par :
  - DHT (Distributed Hash Table) pour la découverte de pairs
  - Handshake (HNS) pour les noms de domaine blockchain
  - ENS (Ethereum Name Service) pour les noms .eth
  - Résolution .pixel TLD local
  - Identité nœud (paire de clés cryptographique)
"""

import os
import json
import time
import hashlib
import subprocess
import socket
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from threading import Thread, Lock, Event
from typing import Optional


DHT_DIR = "/var/db/pixelos/pixnet"
DHT_FILE = "dht_routing.json"
IDENTITY_FILE = "node_identity.json"
HNS_CACHE = "hns_cache.json"

HANDSHAKE_RPC = "http://127.0.0.1:12037"
HANDSHAKE_API_KEY = ""
ENS_RPC = "https://rpc.gnosischain.com"
PIXEL_DNS_PORT = 5300

K_BUCKET_SIZE = 20
REFRESH_INTERVAL = 600


class PixDHT:
    def __init__(self):
        self._lock = Lock()
        self.node_id = self._generate_node_id()
        self._ensure_dirs()
        self._load_identity()
        self._load_routing_table()
        self._load_hns_cache()
        self.routing_table = {}
        self._refresh_thread: Optional[Thread] = None
        self._stop = Event()

    def _ensure_dirs(self):
        Path(DHT_DIR).mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        p = Path(DHT_DIR) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)

    # ── Node identity ─────────────────────────────────────

    def _generate_node_id(self) -> str:
        raw = f"{socket.gethostname()}-{os.urandom(16).hex()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _load_identity(self):
        path = self._path(IDENTITY_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                    self.private_key = data.get("private_key", "")
                    self.public_key = data.get("public_key", "")
                    self.node_id = data.get("node_id", self.node_id)
                return
            except Exception:
                pass
        self.private_key = hashlib.sha256(os.urandom(32)).hexdigest()
        self.public_key = hashlib.sha256(self.private_key.encode()).hexdigest()
        self._save_identity()

    def _save_identity(self):
        with open(self._path(IDENTITY_FILE), "w") as f:
            json.dump({
                "node_id": self.node_id,
                "public_key": self.public_key,
                "private_key": self.private_key,
                "created_at": datetime.now().isoformat(),
            }, f, indent=2)

    def get_identity(self) -> dict:
        return {
            "node_id": self.node_id,
            "public_key": self.public_key,
            "created_at": datetime.fromtimestamp(
                os.path.getctime(self._path(IDENTITY_FILE))
            ).isoformat() if os.path.exists(self._path(IDENTITY_FILE)) else "",
        }

    # ── Routing table ─────────────────────────────────────

    def _load_routing_table(self):
        path = self._path(DHT_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.routing_table = json.load(f)
                return
            except Exception:
                pass
        self.routing_table = {}

    def _save_routing_table(self):
        with open(self._path(DHT_FILE), "w") as f:
            json.dump(self.routing_table, f, indent=2)

    def find_peers(self, key: str, count: int = 10) -> list:
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        scored = []
        for peer_id, info in self.routing_table.items():
            dist = self._xor_distance(key_hash, peer_id)
            scored.append((dist, peer_id, info))
        scored.sort(key=lambda x: x[0])
        return [{"peer_id": pid, **info} for _, pid, info in scored[:count]]

    def _xor_distance(self, a: str, b: str) -> int:
        a_int = int(a, 16)
        b_int = int(b, 16)
        return a_int ^ b_int

    def store_value(self, key: str, value: dict) -> dict:
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        self.routing_table[key_hash] = {
            "key": key,
            "value": value,
            "stored_at": datetime.now().isoformat(),
            "ttl": 86400,
            "stored_by": self.node_id,
        }
        self._save_routing_table()
        return {"status": "stored", "key_hash": key_hash}

    def get_value(self, key: str) -> Optional[dict]:
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        entry = self.routing_table.get(key_hash)
        if entry:
            return entry.get("value")
        return None

    def announce_peer(self, peer_info: dict) -> dict:
        peer_id = peer_info.get("node_id", "")
        if not peer_id:
            return {"status": "error", "reason": "no node_id"}

        self.routing_table[peer_id] = {
            **peer_info,
            "last_seen": datetime.now().isoformat(),
            "announced_by": self.node_id,
        }
        self._save_routing_table()
        return {"status": "announced", "peer_id": peer_id}

    def remove_peer(self, peer_id: str) -> dict:
        if peer_id in self.routing_table:
            del self.routing_table[peer_id]
            self._save_routing_table()
            return {"status": "removed"}
        return {"status": "not_found"}

    def refresh_routing(self):
        now = time.time()
        expired = []
        for peer_id, info in self.routing_table.items():
            last = info.get("last_seen", "")
            if last:
                try:
                    last_ts = datetime.fromisoformat(last).timestamp()
                    if now - last_ts > 86400:
                        expired.append(peer_id)
                except Exception:
                    expired.append(peer_id)
        for peer_id in expired:
            del self.routing_table[peer_id]
        self._save_routing_table()
        return {"removed": len(expired), "total": len(self.routing_table)}

    def start_refresh(self, interval: int = REFRESH_INTERVAL):
        self._stop.clear()

        def loop():
            while not self._stop.is_set():
                self._stop.wait(interval)
                if self._stop.is_set():
                    break
                self.refresh_routing()

        self._refresh_thread = Thread(target=loop, daemon=True)
        self._refresh_thread.start()
        return {"status": "started"}

    def stop_refresh(self):
        self._stop.set()
        if self._refresh_thread:
            self._refresh_thread.join(timeout=5)
        return {"status": "stopped"}

    # ── Handshake (HNS) resolution ────────────────────────

    def _load_hns_cache(self):
        path = self._path(HNS_CACHE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.hns_cache = json.load(f)
                return
            except Exception:
                pass
        self.hns_cache = {}

    def _save_hns_cache(self):
        with open(self._path(HNS_CACHE), "w") as f:
            json.dump(self.hns_cache, f, indent=2)

    def resolve_hns(self, name: str) -> Optional[dict]:
        name = name.replace(".", "").lower()
        if name in self.hns_cache:
            cached = self.hns_cache[name]
            if time.time() - cached.get("ts", 0) < 3600:
                return cached

        try:
            body = json.dumps({
                "method": "getnameinfo",
                "params": [name],
                "id": 1,
            }).encode()
            headers = {"Content-Type": "application/json"}
            if HANDSHAKE_API_KEY:
                headers["Authorization"] = HANDSHAKE_API_KEY
            req = urllib.request.Request(
                HANDSHAKE_RPC, data=body, headers=headers
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                info = data.get("result", {})
                result = {
                    "name": name,
                    "owner": info.get("owner", ""),
                    "records": info.get("records", []),
                    "resolved_at": datetime.now().isoformat(),
                }
                self.hns_cache[name] = {**result, "ts": time.time()}
                self._save_hns_cache()
                return result
        except Exception:
            pass

        # Fallback: public HNS resolver
        try:
            url = f"https://hns.name/api/records/{name}"
            req = urllib.request.Request(url,
                headers={"User-Agent": "PixDHT/1.0 (PixelOS PixNet)"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                result = {
                    "name": name,
                    "records": data.get("records", []),
                    "resolved_at": datetime.now().isoformat(),
                }
                self.hns_cache[name] = {**result, "ts": time.time()}
                self._save_hns_cache()
                return result
        except Exception:
            pass

        return None

    def resolve_ens(self, name: str) -> Optional[dict]:
        name = name.replace(".eth", "").lower()
        cache_key = f"ens_{name}"
        if cache_key in self.hns_cache:
            cached = self.hns_cache[cache_key]
            if time.time() - cached.get("ts", 0) < 3600:
                return cached

        try:
            body = json.dumps({
                "jsonrpc": "2.0", "method": "eth_call",
                "params": [{
                    "to": "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e",
                    "data": "0x" + "691f3431" + name.encode().hex().ljust(64, "0")
                }, "latest"],
                "id": 1,
            }).encode()
            req = urllib.request.Request(
                ENS_RPC, data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                addr = data.get("result", "0x")
                result = {
                    "name": name + ".eth",
                    "address": addr,
                    "resolved_url": f"https://{name}.limo" if addr != "0x" * 32 + "00" else None,
                    "resolved_at": datetime.now().isoformat(),
                }
                self.hns_cache[cache_key] = {**result, "ts": time.time()}
                self._save_hns_cache()
                return result
        except Exception:
            pass
        return None

    # ── .pixel TLD resolution ─────────────────────────────

    def resolve_pixel(self, name: str) -> Optional[dict]:
        name = name.replace(".pixel", "").lower()
        try:
            r = subprocess.run(
                ["dig", f"@{PIXEL_DNS_PORT}", name + ".pixel", "+short"],
                capture_output=True, text=True, timeout=5
            )
            ip = r.stdout.strip()
            if ip:
                return {
                    "name": name + ".pixel",
                    "ip": ip,
                    "resolved_url": f"http://{ip}",
                    "resolved_at": datetime.now().isoformat(),
                }
        except Exception:
            pass
        return None

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "node_id": self.node_id[:16],
            "routing_table_size": len(self.routing_table),
            "hns_cache_size": len(self.hns_cache),
            "refresh_running": self._refresh_thread is not None and self._refresh_thread.is_alive(),
            "public_key": self.public_key[:16] + "...",
        }

    def clear_routing(self):
        self.routing_table = {}
        self._save_routing_table()
        return {"status": "cleared"}
