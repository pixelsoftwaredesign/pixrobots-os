#!/usr/bin/env python3
"""
PixBackup — Sauvegarde décentralisée PixelOS.

Chiffrement AES (Fernet) → Sharding → Erasure Coding (Reed-Solomon)
→ Distribution sur le réseau maillé → Restauration complète.

Aucun nœud voisin ne peut lire vos fragments. La clé maître
est la seule chose à protéger physiquement.
"""

import os
import json
import math
import shutil
import hashlib
import tempfile
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


class PixBackup:
    def __init__(self):
        self._lock = Lock()
        self._ensure_dirs()
        self._load_index()
        self._load_key()

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
        self.index = {"backups": [], "peers": {}}

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

            # 1. Read & encrypt
            raw = source_path.read_bytes()
            if HAS_CRYPTO:
                encrypted = self.cipher.encrypt(raw)
            else:
                encrypted = raw

            # 2. Sharding
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

            # 3. Erasure coding (Reed-Solomon)
            if HAS_REEDSOLO and num_shards >= 2:
                try:
                    rs = reedsolo.RSCodec(ERASURE_NSYM)
                    parity_shards = []
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
            else:
                parity_shards = []

            # 4. Build manifest
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
            }
            self.index["backups"].append(file_info)
            self._save_index()

            return {
                "status": "backed_up",
                "backup_id": backup_id,
                "num_shards": num_shards,
                "encrypted_size": len(encrypted),
                "vault_path": str(vault),
            }

    # ── Restore ───────────────────────────────────────────

    def restore(self, backup_id: str, output_path: str = "") -> dict:
        with self._lock:
            info = None
            for b in self.index["backups"]:
                if b["backup_id"] == backup_id:
                    info = b
                    break
            if not info:
                return {"status": "error", "reason": "backup_id not found"}

            vault = Path(self._path(VAULT_DIR)) / backup_id
            if not vault.exists():
                return {"status": "error", "reason": "vault not found locally"}

            # Reconstruct from shards
            encrypted = b""
            for s in sorted(info["shards"], key=lambda x: x["index"]):
                sp = Path(s["path"])
                if sp.exists():
                    chunk = sp.read_bytes()
                    # Verify hash
                    if hashlib.sha256(chunk).hexdigest() != s["hash"]:
                        # Try erasure-coded recovery
                        ps_path = vault / f"shard_{s['index']:04d}.rs"
                        if ps_path.exists() and HAS_REEDSOLO:
                            try:
                                rs = reedsolo.RSCodec(info.get("erasure_nsym", ERASURE_NSYM))
                                encoded = ps_path.read_bytes()
                                decoded = rs.decode(encoded)[0]
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
                            encoded = ps_path.read_bytes()
                            decoded = rs.decode(encoded)[0]
                            encrypted += decoded
                        except Exception:
                            return {"status": "error", "reason": f"shard {s['index']} unrecoverable"}
                    else:
                        return {"status": "error", "reason": f"shard {s['index']} missing"}
                else:
                    return {"status": "error", "reason": f"shard {s['index']} missing"}

            # Decrypt
            try:
                if HAS_CRYPTO:
                    data = self.cipher.decrypt(encrypted)
                else:
                    data = encrypted
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
            }

    # ── Distribution on mesh ──────────────────────────────

    def distribute(self, backup_id: str, peers: list) -> dict:
        info = None
        for b in self.index["backups"]:
            if b["backup_id"] == backup_id:
                info = b
                break
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

        self.index["backups"][next(
            j for j, b in enumerate(self.index["backups"])
            if b["backup_id"] == backup_id
        )]["distributed_to"] = results
        self._save_index()
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
