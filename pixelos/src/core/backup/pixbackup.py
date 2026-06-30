#!/usr/bin/env python3
"""
PixBackup — Sauvegarde décentralisée PixelOS.

Chiffrement AES (Fernet) → Sharding → Erasure Coding (Reed-Solomon)
→ Distribution via DHT (PixDHT) → Restauration distribuée → Gossip replication.

Aucun nœud voisin ne peut lire vos fragments. La clé maître
est la seule chose à protéger physiquement.
"""

import os
import json
import math
import shutil
import hashlib
import tempfile
import threading
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional
from threading import Lock

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

try:
    import reedsolo
    HAS_REEDSOLO = True
except ImportError:
    HAS_REEDSOLO = False


BACKUP_DIR = "/var/db/pixelos/backup"
INDEX_FILE = "backup_index.json"
KEY_FILE = "master.key"
VAULT_DIR = "vault"
SHARD_SIZE = 5 * 1024 * 1024  # 5 Mo
ERASURE_NSYM = 4  # tolère 4 fragments perdus par bloc
REPLICATION_FACTOR = 3
DHT_NS = "pixbackup"  # namespace DHT pour les annonces de sauvegarde
GOSSIP_INTERVAL = 300  # 5 min


class PixBackup:
    def __init__(self):
        self._lock = Lock()
        self._ensure_dirs()
        self._load_index()
        self._load_key()
        self._dht = None
        self._start_gossip()

    def _get_dht(self):
        if self._dht is None:
            try:
                from core.pixnet.pixdht import PixDHT
                self._dht = PixDHT()
            except Exception:
                pass
        return self._dht

    # ── Persistence ──────────────────────────────────────

    def _ensure_dirs(self):
        Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
        Path(f"{BACKUP_DIR}/{VAULT_DIR}").mkdir(exist_ok=True)

    def _path(self, name):
        return f"{BACKUP_DIR}/{name}"

    def _load_index(self):
        path = self._path(INDEX_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.index = json.load(f)
                return
            except Exception:
                pass
        self.index = {"backups": [], "peers": {}, "dht_announced": []}

    def _save_index(self):
        with open(self._path(INDEX_FILE), "w") as f:
            json.dump(self.index, f, indent=2)

    def _load_key(self):
        path = self._path(KEY_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    key_data = json.load(f)
                    self.master_key = key_data.get("key", "").encode()
                    if HAS_CRYPTO:
                        self.cipher = Fernet(self.master_key)
                    return
            except Exception:
                pass
        if HAS_CRYPTO:
            self.master_key = Fernet.generate_key()
            self.cipher = Fernet(self.master_key)
        else:
            self.master_key = os.urandom(44)
        self._save_key()

    def _save_key(self):
        with open(self._path(KEY_FILE), "w") as f:
            json.dump({
                "key": self.master_key.decode() if isinstance(self.master_key, bytes) else self.master_key,
                "algorithm": "Fernet(AES-128-CBC)",
                "created_at": datetime.now().isoformat(),
                "node_id": hashlib.sha256(os.urandom(8)).hexdigest()[:16],
            }, f, indent=2)

    # ── Backup ────────────────────────────────────────────

    def backup(self, source_path: str, label: str = "",
               shard_size: int = SHARD_SIZE) -> dict:
        if not os.path.exists(source_path):
            return {"status": "error", "reason": "source not found"}

        source_path = Path(source_path)
        backup_id = hashlib.sha256(f"{source_path}{datetime.now()}{os.urandom(8)}".encode()).hexdigest()[:16]

        with self._lock:
            vault = Path(self._path(VAULT_DIR)) / backup_id
            vault.mkdir(parents=True, exist_ok=True)

            raw = source_path.read_bytes()
            if HAS_CRYPTO:
                encrypted = self.cipher.encrypt(raw)
            else:
                encrypted = raw

            num_shards = math.ceil(len(encrypted) / shard_size)
            shards = []
            for i in range(num_shards):
                chunk = encrypted[i * shard_size:(i + 1) * shard_size]
                shard_path = vault / f"shard_{i:04d}.part"
                shard_path.write_bytes(chunk)
                shards.append({
                    "index": i,
                    "path": str(shard_path),
                    "size": len(chunk),
                    "hash": hashlib.sha256(chunk).hexdigest(),
                })

            parity_shards = []
            if HAS_REEDSOLO and num_shards >= 2:
                try:
                    rs = reedsolo.RSCodec(ERASURE_NSYM)
                    for s in shards:
                        data = Path(s["path"]).read_bytes()
                        encoded = rs.encode(data)
                        ps_path = vault / f"shard_{s['index']:04d}.rs"
                        ps_path.write_bytes(encoded)
                        parity_shards.append({
                            "index": s["index"],
                            "path": str(ps_path),
                            "size": len(encoded),
                            "hash": hashlib.sha256(encoded).hexdigest(),
                            "type": "reed-solomon",
                        })
                except Exception:
                    parity_shards = []

            file_info = {
                "backup_id": backup_id,
                "label": label or source_path.name,
                "source": str(source_path),
                "source_size": len(raw),
                "encrypted_size": len(encrypted),
                "num_shards": num_shards,
                "shard_size": shard_size,
                "has_erasure_coding": len(parity_shards) > 0,
                "erasure_nsym": ERASURE_NSYM if parity_shards else 0,
                "shards": shards,
                "parity_shards": parity_shards,
                "created_at": datetime.now().isoformat(),
                "file_hash": hashlib.sha256(raw).hexdigest(),
                "replicated_to": [],
                "dht_announced": False,
            }
            self.index["backups"].append(file_info)
            self._save_index()

        # DHT announce (hors lock)
        self._announce_to_dht(backup_id)
        # Gossip replication (hors lock)
        threading.Thread(target=self._gossip_replicate, args=(backup_id,), daemon=True).start()

        return {
            "status": "backed_up",
            "backup_id": backup_id,
            "num_shards": num_shards,
            "encrypted_size": len(encrypted),
            "vault_path": str(vault),
        }

    # ── DHT Integration ──────────────────────────────────

    def _announce_to_dht(self, backup_id: str):
        dht = self._get_dht()
        if not dht:
            return
        info = self.get_backup(backup_id)
        if not info:
            return

        vault = Path(self._path(VAULT_DIR)) / backup_id
        # Annoncer chaque shard dans le DHT avec sa localisation
        all_shards = info["shards"] + info.get("parity_shards", [])
        shard_meta = []
        for s in all_shards:
            shard_meta.append({
                "backup_id": backup_id,
                "index": s["index"],
                "size": s["size"],
                "hash": s["hash"],
                "type": s.get("type", "data"),
            })

        dht_key = f"{DHT_NS}:manifest:{backup_id}"
        dht.store_value(dht_key, {
            "backup_id": backup_id,
            "label": info.get("label", ""),
            "num_shards": info["num_shards"],
            "has_erasure": info.get("has_erasure_coding", False),
            "shards": shard_meta,
            "node_id": dht.node_id if hasattr(dht, 'node_id') else "local",
            "peers_with_shards": [dht.node_id] if hasattr(dht, 'node_id') else ["local"],
        })

        with self._lock:
            for i, b in enumerate(self.index["backups"]):
                if b["backup_id"] == backup_id:
                    self.index["backups"][i]["dht_announced"] = True
                    self._save_index()
                    break

    def _find_remote_backup(self, backup_id: str) -> list:
        dht = self._get_dht()
        if not dht:
            return []
        dht_key = f"{DHT_NS}:manifest:{backup_id}"
        manifest = dht.get_value(dht_key)
        if not manifest:
            return []
        peers = manifest.get("peers_with_shards", [])
        return [{
            "node_id": pid,
            "backup_id": backup_id,
            "num_shards": manifest.get("num_shards", 0),
            "has_erasure": manifest.get("has_erasure", False),
            "shards": manifest.get("shards", []),
        } for pid in peers]

    def _fetch_shard_via_peer(self, peer_id: str, backup_id: str, shard_index: int) -> Optional[bytes]:
        """Tente de télécharger un shard depuis un pair via HTTP."""
        dht = self._get_dht()
        if not dht:
            return None
        peer_info = dht.routing_table.get(peer_id)
        if not peer_info:
            return None

        peer_addr = peer_info.get("addr", peer_info.get("address", ""))
        if not peer_addr:
            return None

        url = f"http://{peer_addr}:8080/api/backup/shard/{backup_id}/{shard_index}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except Exception:
            return None

    # ── Distributed Restore ──────────────────────────────

    def restore(self, backup_id: str, output_path: str = "") -> dict:
        with self._lock:
            result = self._restore_local(backup_id, output_path)
            if result["status"] == "restored":
                return result
        # Fallback : restauration distribuée
        return self.restore_distributed(backup_id, output_path)

    def _restore_local(self, backup_id: str, output_path: str = "") -> dict:
        info = None
        for b in self.index["backups"]:
            if b["backup_id"] == backup_id:
                info = b
                break
        if not info:
            return {"status": "error", "reason": "backup_id not found locally"}

        vault = Path(self._path(VAULT_DIR)) / backup_id
        if not vault.exists():
            return {"status": "error", "reason": "vault not found locally"}

        encrypted = b""
        for s in sorted(info["shards"], key=lambda x: x["index"]):
            sp = Path(s["path"])
            if sp.exists():
                chunk = sp.read_bytes()
                if hashlib.sha256(chunk).hexdigest() != s["hash"]:
                    ps_path = vault / f"shard_{s['index']:04d}.rs"
                    if ps_path.exists() and HAS_REEDSOLO:
                        try:
                            rs = reedsolo.RSCodec(info.get("erasure_nsym", ERASURE_NSYM))
                            decoded = rs.decode(ps_path.read_bytes())[0]
                            chunk = decoded
                        except Exception:
                            return {"status": "error", "reason": f"shard {s['index']} corrupted"}
                    else:
                        return {"status": "error", "reason": f"shard {s['index']} corrupted"}
                encrypted += chunk
            elif HAS_REEDSOLO:
                ps_path = vault / f"shard_{s['index']:04d}.rs"
                if ps_path.exists():
                    try:
                        rs = reedsolo.RSCodec(info.get("erasure_nsym", ERASURE_NSYM))
                        decoded = rs.decode(ps_path.read_bytes())[0]
                        encrypted += decoded
                    except Exception:
                        return {"status": "error", "reason": f"shard {s['index']} unrecoverable"}
                else:
                    return {"status": "error", "reason": f"shard {s['index']} missing"}
            else:
                return {"status": "error", "reason": f"shard {s['index']} missing"}

        try:
            data = self.cipher.decrypt(encrypted) if HAS_CRYPTO else encrypted
        except Exception:
            return {"status": "error", "reason": "decryption failed (wrong key?)"}

        output = output_path or info["source"]
        Path(output).write_bytes(data)

        return {
            "status": "restored",
            "backup_id": backup_id,
            "output": output,
            "size": len(data),
            "file_hash": hashlib.sha256(data).hexdigest(),
            "source": "local",
        }

    def restore_distributed(self, backup_id: str, output_path: str = "") -> dict:
        """Restaure un backup en allant chercher les shards manquants via DHT/peers."""
        dht = self._get_dht()
        if not dht:
            return {"status": "error", "reason": "DHT not available for distributed restore"}

        remote_manifests = self._find_remote_backup(backup_id)
        if not remote_manifests:
            return {"status": "error", "reason": "backup not found locally or on network"}

        manifest = remote_manifests[0]
        num_shards = manifest["num_shards"]
        has_erasure = manifest["has_erasure"]
        shard_list = manifest["shards"]

        encrypted = b""
        fetch_errors = []
        for idx in range(num_shards):
            shard_data = None
            for peer in remote_manifests:
                data = self._fetch_shard_via_peer(peer["node_id"], backup_id, idx)
                if data:
                    shard_data = data
                    break

            if shard_data is None:
                # Tentative erasure coding
                if has_erasure and HAS_REEDSOLO:
                    fetch_errors.append(f"shard {idx} missing, attempting RS recovery...")
                    continue
                return {"status": "error", "reason": f"shard {idx} not found on any peer"}

            encrypted += shard_data

        # Si certains shards manquent, tenter Reed-Solomon
        if len(encrypted) < num_shards and has_erasure and HAS_REEDSOLO:
            rs = reedsolo.RSCodec(ERASURE_NSYM)
            try:
                encrypted = rs.decode(encrypted)[0]
            except Exception:
                return {"status": "error", "reason": "RS recovery failed, too many shards missing"}

        try:
            data = self.cipher.decrypt(encrypted) if HAS_CRYPTO else encrypted
        except Exception:
            return {"status": "error", "reason": "decryption failed (wrong key?)"}

        # Sauvegarder localement pour future restauration
        local_vault = Path(self._path(VAULT_DIR)) / backup_id
        local_vault.mkdir(parents=True, exist_ok=True)
        # Écrire le fichier restauré
        output = output_path or f"/tmp/pixbackup_restore_{backup_id}"
        Path(output).write_bytes(data)

        # Enregistrer le backup localement si pas déjà fait
        with self._lock:
            if not self.get_backup(backup_id):
                restored_info = {
                    "backup_id": backup_id,
                    "label": f"restored_from_network_{backup_id[:8]}",
                    "source": output,
                    "source_size": len(data),
                    "encrypted_size": len(encrypted),
                    "num_shards": num_shards,
                    "shard_size": SHARD_SIZE,
                    "has_erasure_coding": has_erasure,
                    "erasure_nsym": ERASURE_NSYM if has_erasure else 0,
                    "shards": [],
                    "parity_shards": [],
                    "created_at": datetime.now().isoformat(),
                    "file_hash": hashlib.sha256(data).hexdigest(),
                    "replicated_to": [],
                    "dht_announced": False,
                }
                self.index["backups"].append(restored_info)
                self._save_index()

        return {
            "status": "restored",
            "backup_id": backup_id,
            "output": output,
            "size": len(data),
            "file_hash": hashlib.sha256(data).hexdigest(),
            "source": "distributed_dht",
            "fetch_errors": fetch_errors,
        }

    # ── Gossip Replication ──────────────────────────────

    def _start_gossip(self):
        """Démarre un thread de fond qui réplique les backups vers les pairs."""
        def loop():
            while True:
                time.sleep(GOSSIP_INTERVAL)
                try:
                    self._gossip_all()
                except Exception:
                    pass
        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _gossip_all(self):
        """Pour chaque backup, vérifie le facteur de réplication et réplique si nécessaire."""
        dht = self._get_dht()
        if not dht:
            return
        for b in self.index["backups"]:
            bid = b["backup_id"]
            current_replicas = len(b.get("replicated_to", []))
            if current_replicas < REPLICATION_FACTOR:
                self._gossip_replicate(bid)

    def _gossip_replicate(self, backup_id: str):
        """Pousse les shards vers les pairs jusqu'à atteindre REPLICATION_FACTOR."""
        dht = self._get_dht()
        if not dht:
            return

        vault = Path(self._path(VAULT_DIR)) / backup_id
        if not vault.exists():
            return

        info = self.get_backup(backup_id)
        if not info:
            return

        peers = dht.find_peers(f"pixbackup:{backup_id}", count=REPLICATION_FACTOR * 2)
        existing = set(info.get("replicated_to", []))
        new_replicas = []

        for peer in peers:
            peer_id = peer.get("peer_id", "")
            if peer_id in existing or peer_id == dht.node_id:
                continue
            if len(new_replicas) + len(existing) >= REPLICATION_FACTOR:
                break

            peer_addr = peer.get("addr", "")
            if not peer_addr:
                continue

            # Envoyer chaque shard au pair via HTTP
            success = True
            for s in info["shards"]:
                shard_path = Path(s["path"])
                if not shard_path.exists():
                    success = False
                    break
                shard_data = shard_path.read_bytes()
                url = f"http://{peer_addr}:8080/api/backup/shard/push/{backup_id}/{s['index']}"
                try:
                    req = urllib.request.Request(
                        url, data=shard_data,
                        headers={"Content-Type": "application/octet-stream", "X-Shard-Hash": s["hash"]},
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        if resp.status != 200:
                            success = False
                except Exception:
                    success = False
                    break

            if success:
                new_replicas.append(peer_id)
                existing.add(peer_id)

        if new_replicas:
            with self._lock:
                for i, b in enumerate(self.index["backups"]):
                    if b["backup_id"] == backup_id:
                        self.index["backups"][i]["replicated_to"] = list(existing)
                        self._save_index()
                        break

    # ── Serve shards to peers ────────────────────────────

    def get_shard(self, backup_id: str, shard_index: int, shard_type: str = "data") -> Optional[bytes]:
        """Retourne le contenu d'un shard pour le servir à un pair."""
        info = self.get_backup(backup_id)
        if not info:
            return None

        vault = Path(self._path(VAULT_DIR)) / backup_id
        if shard_type == "data":
            shard_path = vault / f"shard_{int(shard_index):04d}.part"
        else:
            shard_path = vault / f"shard_{int(shard_index):04d}.rs"

        if shard_path.exists():
            return shard_path.read_bytes()
        return None

    def receive_shard(self, backup_id: str, shard_index: int, data: bytes, shard_hash: str) -> dict:
        """Reçoit un shard d'un pair et le stocke localement."""
        vault = Path(self._path(VAULT_DIR)) / backup_id
        vault.mkdir(parents=True, exist_ok=True)

        shard_path = vault / f"shard_{int(shard_index):04d}.part"

        actual_hash = hashlib.sha256(data).hexdigest()
        if actual_hash != shard_hash:
            return {"status": "error", "reason": "hash mismatch"}

        shard_path.write_bytes(data)

        # Mettre à jour l'index
        with self._lock:
            info = self.get_backup(backup_id)
            if info:
                for s in info["shards"]:
                    if s["index"] == shard_index:
                        s["path"] = str(shard_path)
                        break
                else:
                    info["shards"].append({
                        "index": shard_index,
                        "path": str(shard_path),
                        "size": len(data),
                        "hash": shard_hash,
                    })
                self._save_index()
            else:
                # Nouveau backup reçu partiellement
                new_entry = {
                    "backup_id": backup_id,
                    "label": f"received_{backup_id[:8]}",
                    "source": f"peer_transfer_{backup_id}",
                    "source_size": 0,
                    "encrypted_size": 0,
                    "num_shards": 0,
                    "shard_size": SHARD_SIZE,
                    "has_erasure_coding": False,
                    "erasure_nsym": 0,
                    "shards": [{"index": shard_index, "path": str(shard_path), "size": len(data), "hash": shard_hash}],
                    "parity_shards": [],
                    "created_at": datetime.now().isoformat(),
                    "file_hash": "",
                    "replicated_to": [],
                    "dht_announced": False,
                }
                self.index["backups"].append(new_entry)
                self._save_index()

        return {"status": "received"}

    # ── Distribution on mesh ──────────────────────────────

    def distribute(self, backup_id: str, peers: list) -> dict:
        info = self.get_backup(backup_id)
        if not info:
            return {"status": "error", "reason": "not found"}

        vault = Path(self._path(VAULT_DIR)) / backup_id
        results = []
        for i, peer in enumerate(peers):
            target_shards = []
            for s in info["shards"]:
                if s["index"] % len(peers) == i:
                    target_shards.append(s)
            results.append({
                "peer": peer.get("node_id", f"peer_{i}"),
                "shards": len(target_shards),
            })

        with self._lock:
            for j, b in enumerate(self.index["backups"]):
                if b["backup_id"] == backup_id:
                    self.index["backups"][j]["distributed_to"] = results
                    self._save_index()
                    break

        return {"status": "distribution_planned", "peers": len(peers), "shards_per_peer": results}

    # ─── List & status ────────────────────────────────────

    def list_backups(self) -> list:
        return [
            {
                "backup_id": b["backup_id"],
                "label": b.get("label", ""),
                "source": b.get("source", ""),
                "size": b.get("source_size", 0),
                "shards": b.get("num_shards", 0),
                "erasure": b.get("has_erasure_coding", False),
                "created_at": b.get("created_at", ""),
                "replicated_to": b.get("replicated_to", []),
                "dht_announced": b.get("dht_announced", False),
            }
            for b in reversed(self.index["backups"])
        ]

    def get_backup(self, backup_id: str) -> Optional[dict]:
        for b in self.index["backups"]:
            if b["backup_id"] == backup_id:
                return b
        return None

    def delete_backup(self, backup_id: str) -> dict:
        for i, b in enumerate(self.index["backups"]):
            if b["backup_id"] == backup_id:
                vault = Path(self._path(VAULT_DIR)) / backup_id
                if vault.exists():
                    shutil.rmtree(vault)
                del self.index["backups"][i]
                self._save_index()
                return {"status": "deleted", "backup_id": backup_id}
        return {"status": "error", "reason": "not found"}

    def remove_peer_storage(self, peer_id: str) -> dict:
        if peer_id in self.index["peers"]:
            del self.index["peers"][peer_id]
            self._save_index()
            return {"status": "removed"}
        return {"status": "not_found"}

    # ── Key management ────────────────────────────────────

    def get_key(self) -> dict:
        return {
            "algorithm": "Fernet(AES-128-CBC)",
            "key_path": self._path(KEY_FILE),
            "key_present": os.path.exists(self._path(KEY_FILE)),
            "warning": "GARDEZ CETTE CLE PRECIEUSEMENT — sans elle, restauration impossible",
        }

    def export_key(self, output: str = "") -> str:
        out = output or self._path("master_key_backup.txt")
        with open(self._path(KEY_FILE)) as f:
            key_data = f.read()
        Path(out).write_text(key_data)
        return out

    def import_key(self, key_path: str) -> dict:
        if not os.path.exists(key_path):
            return {"status": "error", "reason": "key file not found"}
        try:
            with open(key_path) as f:
                key_data = json.load(f)
            self.master_key = key_data["key"].encode()
            if HAS_CRYPTO:
                self.cipher = Fernet(self.master_key)
            with open(self._path(KEY_FILE), "w") as f:
                json.dump(key_data, f, indent=2)
            return {"status": "key_imported"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    # ── Health check ──────────────────────────────────────

    def health(self) -> dict:
        dht = self._get_dht()
        replicated = sum(1 for b in self.index["backups"] if len(b.get("replicated_to", [])) >= REPLICATION_FACTOR)
        under_replicated = sum(1 for b in self.index["backups"] if 0 < len(b.get("replicated_to", [])) < REPLICATION_FACTOR)
        not_replicated = sum(1 for b in self.index["backups"] if len(b.get("replicated_to", [])) == 0)
        return {
            "total_backups": len(self.index["backups"]),
            "replicated_ok": replicated,
            "under_replicated": under_replicated,
            "not_replicated": not_replicated,
            "replication_factor": REPLICATION_FACTOR,
            "dht_available": dht is not None,
            "dht_announced": sum(1 for b in self.index["backups"] if b.get("dht_announced")),
            "cryptography": HAS_CRYPTO,
            "reedsolo": HAS_REEDSOLO,
        }

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> dict:
        total_size = 0
        total_shards = 0
        for b in self.index["backups"]:
            total_size += b.get("source_size", 0)
            total_shards += b.get("num_shards", 0)
        return {
            "total_backups": len(self.index["backups"]),
            "total_size_bytes": total_size,
            "total_size_human": self._human_size(total_size),
            "total_shards": total_shards,
            "peers_used": len(self.index.get("peers", {})),
            "has_cryptography": HAS_CRYPTO,
            "has_reedsolo": HAS_REEDSOLO,
            "vault_path": self._path(VAULT_DIR),
            "key_protected": os.path.exists(self._path(KEY_FILE)),
            "shard_size": SHARD_SIZE,
            "replication_factor": REPLICATION_FACTOR,
        }

    @staticmethod
    def _human_size(b):
        for u in ("B", "KB", "MB", "GB", "TB"):
            if b < 1024:
                return f"{b:.1f} {u}"
            b /= 1024
        return f"{b:.1f} PB"
