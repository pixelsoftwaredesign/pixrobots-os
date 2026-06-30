# Pixel Software Design � Copyright 2026
"""Pixel Wallet — Gestion des portefeuilles BITROOT (BRT).

Architecture:
  - Génération de clés Ethereum (ECDSA)
  - Gestion des soldes (offline + on-chain)
  - Historique des transactions signées
  - Cryptage local des clés privées (AES-256-GCM)
"""

import json
import os
import structlog
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "web3" / "wallets"
WALLET_FILE = DATA_DIR / "wallets.json"
TX_FILE = DATA_DIR / "transactions.json"

CHAIN_IDS = {
    "gnosis": 100,
    "polygon": 137,
    "sepolia": 11155111,
}

@dataclass
class WalletEntry:
    address: str
    label: str
    encrypted_key: str
    salt: str
    iv: str
    auth_tag: str
    created: str
    last_used: str = ""
    balance_brt: float = 0.0
    balance_wei: int = 0
    is_default: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

class WalletManager:
    """Gère les portefeuilles BITROOT locaux."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._wallets: dict[str, WalletEntry] = {}
        self._tx_history: list[dict] = []
        self._load()

    def _load(self):
        if WALLET_FILE.exists():
            try:
                data = json.loads(WALLET_FILE.read_text(encoding="utf-8"))
                for w in data:
                    self._wallets[w["address"]] = WalletEntry(**w)
            except Exception as e:
                log.warning("Erreur chargement wallets", error=str(e))
        if TX_FILE.exists():
            try:
                self._tx_history = json.loads(TX_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._tx_history = []

    def _save(self):
        WALLET_FILE.write_text(
            json.dumps([w.to_dict() for w in self._wallets.values()],
                       indent=2, ensure_ascii=False),
            encoding="utf-8")

    def _save_tx(self):
        TX_FILE.write_text(
            json.dumps(self._tx_history[-500:], indent=2, ensure_ascii=False),
            encoding="utf-8")

    def _derive_key(self, password: str, salt: str) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200000, 32)

    def _encrypt_key(self, private_key_hex: str, password: str) -> tuple[str, str, str, str]:
        import secrets, hashlib
        from Crypto.Cipher import AES
        salt = secrets.token_hex(16)
        key = self._derive_key(password, salt)
        cipher = AES.new(key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(private_key_hex.encode())
        return ciphertext.hex(), salt, cipher.nonce.hex(), tag.hex()

    def _decrypt_key(self, encrypted_hex: str, password: str, salt: str, iv_hex: str, tag_hex: str) -> Optional[str]:
        try:
            from Crypto.Cipher import AES
            key = self._derive_key(password, salt)
            cipher = AES.new(key, AES.MODE_GCM, nonce=bytes.fromhex(iv_hex))
            data = cipher.decrypt_and_verify(bytes.fromhex(encrypted_hex), bytes.fromhex(tag_hex))
            return data.decode()
        except Exception as e:
            log.warning("Echec decryptage", error=str(e))
            return None

    def create_wallet(self, label: str = "", password: str = "pixelos_default",
                      make_default: bool = False) -> dict:
        """Crée un nouveau portefeuille BITROOT."""
        from eth_account import Account
        import secrets
        acct = Account.create(secrets.token_hex(32))
        private_key = acct.key.hex()
        address = acct.address

        encrypted, salt, iv, tag = self._encrypt_key(private_key, password)
        entry = WalletEntry(
            address=address,
            label=label or f"Wallet {address[:8]}",
            encrypted_key=encrypted,
            salt=salt,
            iv=iv,
            auth_tag=tag,
            created=datetime.now().isoformat(),
            is_default=make_default or len(self._wallets) == 0,
        )
        self._wallets[address] = entry
        if make_default:
            for w in self._wallets.values():
                w.is_default = (w.address == address)
        self._save()
        log.info("Portefeuille créé", address=address, label=entry.label)
        return {
            "address": address,
            "label": entry.label,
            "created": entry.created,
            "is_default": entry.is_default,
            "warning": "Sauvegardez votre clé privée hors ligne",
            "private_key": private_key,
        }

    def import_wallet(self, private_key_hex: str, label: str = "",
                      password: str = "pixelos_default",
                      make_default: bool = False) -> Optional[dict]:
        """Importe un portefeuille existant via sa clé privée."""
        from eth_account import Account
        try:
            acct = Account.from_key(private_key_hex)
            address = acct.address
        except Exception as e:
            log.warning("Clé privée invalide", error=str(e))
            return None

        if address in self._wallets:
            return {"error": "Portefeuille déjà existant", "address": address}

        encrypted, salt, iv, tag = self._encrypt_key(private_key_hex, password)
        entry = WalletEntry(
            address=address,
            label=label or f"Wallet {address[:8]}",
            encrypted_key=encrypted,
            salt=salt,
            iv=iv,
            auth_tag=tag,
            created=datetime.now().isoformat(),
            is_default=make_default or len(self._wallets) == 0,
        )
        self._wallets[address] = entry
        if make_default:
            for w in self._wallets.values():
                w.is_default = (w.address == address)
        self._save()
        log.info("Portefeuille importé", address=address)
        return entry.to_dict()

    def get_wallet(self, address: str, password: str = "pixelos_default") -> Optional[dict]:
        """Récupère les infos d'un portefeuille (sans clé privée)."""
        w = self._wallets.get(address)
        if not w:
            return None
        d = w.to_dict()
        d.pop("encrypted_key", None)
        d.pop("salt", None)
        d.pop("iv", None)
        d.pop("auth_tag", None)
        return d

    def get_private_key(self, address: str, password: str = "pixelos_default") -> Optional[str]:
        """Décrypte et retourne la clé privée."""
        w = self._wallets.get(address)
        if not w:
            return None
        return self._decrypt_key(w.encrypted_key, password, w.salt, w.iv, w.auth_tag)

    def list_wallets(self) -> list[dict]:
        """Liste tous les portefeuilles (sans clés privées)."""
        return [w.to_dict() for w in self._wallets.values()]

    def get_default_wallet(self) -> Optional[WalletEntry]:
        for w in self._wallets.values():
            if w.is_default:
                return w
        if self._wallets:
            w = list(self._wallets.values())[0]
            w.is_default = True
            self._save()
            return w
        return None

    def set_default(self, address: str) -> bool:
        w = self._wallets.get(address)
        if not w:
            return False
        for w2 in self._wallets.values():
            w2.is_default = (w2.address == address)
        self._save()
        return True

    def delete_wallet(self, address: str) -> bool:
        if address not in self._wallets:
            return False
        del self._wallets[address]
        self._save()
        return True

    def add_transaction(self, tx: dict):
        self._tx_history.append({
            **tx,
            "recorded_at": datetime.now().isoformat(),
        })
        self._save_tx()

    def get_transactions(self, address: str = None, limit: int = 50) -> list[dict]:
        if address:
            return [t for t in self._tx_history[-limit:]
                    if t.get("from", "").lower() == address.lower()
                    or t.get("to", "").lower() == address.lower()]
        return self._tx_history[-limit:]

    def stats(self) -> dict:
        return {
            "wallet_count": len(self._wallets),
            "transaction_count": len(self._tx_history),
            "default_address": self.get_default_wallet().address if self.get_default_wallet() else None,
            "total_balance_brt": sum(w.balance_brt for w in self._wallets.values()),
        }

    def sign_message(self, address: str, message: str,
                     password: str = "pixelos_default") -> Optional[dict]:
        """Signe un message avec la clé privée du portefeuille."""
        pk = self.get_private_key(address, password)
        if not pk:
            return None
        from eth_account import Account
        from eth_account.messages import encode_defunct
        msg_hash = encode_defunct(text=message)
        signed = Account.sign_message(msg_hash, private_key=pk)
        return {
            "message": message,
            "signature": signed.signature.hex(),
            "signer": address,
        }

wallet_manager = WalletManager()
