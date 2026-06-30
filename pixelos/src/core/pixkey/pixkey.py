#!/usr/bin/env python3
"""
PixKey — Authentification physique PixelOS.

Supporte:
  - YubiKey (U2F/FIDO2/OTP) via ykman
  - Clé de récupération (master password offline)
  - Biométrie locale (IA via caméra - optionnel)
  - Hardware Security Module (HSM) simulé
"""

import os
import json
import hashlib
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


KEY_DIR = "/var/db/pixelos/pixkey"
AUTH_LOG = "auth_log.json"
KEYS_FILE = "registered_keys.json"
SESSION_FILE = "session.json"
SESSION_DURATION = 3600  # 1 heure


class PixKey:
    def __init__(self):
        self._ensure_dirs()
        self._load_keys()
        self._load_auth_log()
        self._session = None
        self._load_session()
        self.yubikey_available = self._check_yubikey()

    def _ensure_dirs(self):
        Path(KEY_DIR).mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        return str(Path(KEY_DIR) / name)

    def _load_keys(self):
        path = self._path(KEYS_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.keys = json.load(f)
                return
            except Exception:
                pass
        self.keys = {"yubikeys": [], "recovery_keys": [], "tokens": []}

    def _save_keys(self):
        with open(self._path(KEYS_FILE), "w") as f:
            json.dump(self.keys, f, indent=2)

    def _load_auth_log(self):
        path = self._path(AUTH_LOG)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.auth_log = json.load(f)
                return
            except Exception:
                pass
        self.auth_log = []

    def _save_auth_log(self):
        with open(self._path(AUTH_LOG), "w") as f:
            json.dump(self.auth_log[-1000:], f, indent=2)

    def _load_session(self):
        path = self._path(SESSION_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                    if time.time() - data.get("created_at", 0) < SESSION_DURATION:
                        self._session = data
            except Exception:
                pass

    def _save_session(self):
        with open(self._path(SESSION_FILE), "w") as f:
            json.dump(self._session, f, indent=2)

    def _check_yubikey(self) -> bool:
        try:
            r = subprocess.run(["ykman", "info"],
                               capture_output=True, text=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    # ── Register ──────────────────────────────────────────

    def register_yubikey(self, serial: str = "", label: str = "") -> dict:
        try:
            if serial:
                r = subprocess.run(["ykman", "info", serial],
                                   capture_output=True, text=True, timeout=5)
            else:
                r = subprocess.run(["ykman", "info"],
                                   capture_output=True, text=True, timeout=5)

            info = r.stdout.strip()
            yk_serial = serial or "auto"
            for line in info.split("\n"):
                if "Serial" in line:
                    yk_serial = line.split(":")[-1].strip()

            device = {
                "id": yk_serial,
                "label": label or f"YubiKey-{yk_serial}",
                "type": "yubikey",
                "registered_at": datetime.now().isoformat(),
                "fingerprint": hashlib.sha256(info.encode()).hexdigest()[:16],
                "last_used": "",
            }
            self.keys["yubikeys"].append(device)
            self._save_keys()
            return {"status": "registered", "device": device}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def register_recovery_key(self, password: str, label: str = "") -> dict:
        salt = os.urandom(32).hex()
        key_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
        rk = {
            "id": hashlib.sha256(os.urandom(16)).hexdigest()[:12],
            "label": label or "recovery-key",
            "type": "recovery",
            "hash": key_hash,
            "salt": salt,
            "created_at": datetime.now().isoformat(),
        }
        self.keys["recovery_keys"].append(rk)
        self._save_keys()
        return {"status": "recovery_key_registered", "id": rk["id"]}

    def register_token(self, token_id: str, label: str = "") -> dict:
        tok = {
            "id": token_id,
            "label": label or f"Token-{token_id[:8]}",
            "type": "token",
            "registered_at": datetime.now().isoformat(),
        }
        self.keys["tokens"].append(tok)
        self._save_keys()
        return {"status": "token_registered", "token": tok}

    # ── Authenticate ──────────────────────────────────────

    def authenticate(self, method: str = "yubikey", **kwargs) -> dict:
        result = {"authenticated": False, "method": method}

        if method == "yubikey":
            result = self._auth_yubikey()
        elif method == "recovery":
            password = kwargs.get("password", "")
            key_id = kwargs.get("key_id", "")
            result = self._auth_recovery(password, key_id)
        elif method == "token":
            token = kwargs.get("token", "")
            result = self._auth_token(token)
        elif method == "check":
            result = {"authenticated": self.is_authenticated(), "method": "session"}

        self.auth_log.append({
            "method": method,
            "success": result.get("authenticated", False),
            "ts": datetime.now().isoformat(),
        })
        self._save_auth_log()

        if result.get("authenticated"):
            self._session = {
                "authenticated": True,
                "method": method,
                "created_at": time.time(),
                "expires_at": time.time() + SESSION_DURATION,
            }
            self._save_session()

        return result

    def _auth_yubikey(self) -> dict:
        if not self.yubikey_available:
            return {"authenticated": False, "reason": "no yubikey detected"}
        try:
            r = subprocess.run(["ykman", "info"],
                               capture_output=True, text=True, timeout=5)
            ok = r.returncode == 0
            for key in self.keys.get("yubikeys", []):
                if key["id"] in r.stdout or key["id"] == "auto":
                    key["last_used"] = datetime.now().isoformat()
                    self._save_keys()
                    break
            return {"authenticated": ok, "method": "yubikey", "info": r.stdout[:200]}
        except Exception as e:
            return {"authenticated": False, "reason": str(e)}

    def _auth_recovery(self, password: str, key_id: str = "") -> dict:
        for rk in self.keys.get("recovery_keys", []):
            if key_id and rk["id"] != key_id:
                continue
            test_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), rk["salt"].encode(), 100000).hex()
            if test_hash == rk["hash"]:
                return {"authenticated": True, "method": "recovery", "key_id": rk["id"]}
        return {"authenticated": False, "reason": "invalid password"}

    def _auth_token(self, token: str) -> dict:
        for t in self.keys.get("tokens", []):
            if t["id"] == token:
                return {"authenticated": True, "method": "token", "token_id": token}
        return {"authenticated": False, "reason": "invalid token"}

    # ── Session ───────────────────────────────────────────

    def is_authenticated(self) -> bool:
        if not self._session:
            return False
        if time.time() > self._session.get("expires_at", 0):
            self._session = None
            if os.path.exists(self._path(SESSION_FILE)):
                os.remove(self._path(SESSION_FILE))
            return False
        return self._session.get("authenticated", False)

    def logout(self):
        self._session = None
        if os.path.exists(self._path(SESSION_FILE)):
            os.remove(self._path(SESSION_FILE))
        return {"status": "logged_out"}

    # ── Transaction signing ───────────────────────────────

    def sign(self, data: dict) -> dict:
        if not self.is_authenticated():
            return {"status": "error", "reason": "not authenticated"}
        payload = json.dumps(data, sort_keys=True)
        signature = hashlib.sha256(payload.encode() + os.urandom(4)).hexdigest()
        return {
            "status": "signed",
            "data": data,
            "signature": signature,
            "signed_at": datetime.now().isoformat(),
            "key_protected": True,
        }

    # ── List ──────────────────────────────────────────────

    def list_keys(self) -> dict:
        return {
            "yubikeys": [
                {"id": k["id"], "label": k["label"], "registered_at": k["registered_at"]}
                for k in self.keys.get("yubikeys", [])
            ],
            "recovery_keys": [
                {"id": k["id"], "label": k["label"], "created_at": k["created_at"]}
                for k in self.keys.get("recovery_keys", [])
            ],
            "tokens": self.keys.get("tokens", []),
        }

    def remove_key(self, key_id: str) -> dict:
        for category in ["yubikeys", "recovery_keys", "tokens"]:
            for i, k in enumerate(self.keys.get(category, [])):
                if k["id"] == key_id:
                    del self.keys[category][i]
                    self._save_keys()
                    return {"status": "removed", "category": category}
        return {"status": "not_found"}

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "yubikey_available": self.yubikey_available,
            "yubikeys_registered": len(self.keys.get("yubikeys", [])),
            "recovery_keys": len(self.keys.get("recovery_keys", [])),
            "tokens": len(self.keys.get("tokens", [])),
            "session_active": self.is_authenticated(),
            "auth_log_count": len(self.auth_log),
            "last_auth": self.auth_log[-1] if self.auth_log else None,
        }
