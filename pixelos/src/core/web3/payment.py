"""Pixel Pay — Moteur de paiement P2P BITROOT (BRT).

Architecture:
  - Création et signature de transactions offline
  - Simulation on-chain via RPC (Gnosis/Polygon)
  - File d'attente de transactions avec rejeu
  - Factures (invoices) avec QR données
  - Cache de taux de change BRT/EUR
"""

import json
import structlog
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional
from decimal import Decimal

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "web3" / "payments"
INVOICES_FILE = DATA_DIR / "invoices.json"
QUEUE_FILE = DATA_DIR / "queue.json"
RATES_FILE = DATA_DIR / "rates.json"

WEI_PER_BRT = 10**18
GAS_LIMIT_DEFAULT = 100000
GAS_PRICE_GWEI = 1  # Gnosis: ~1 Gwei

MEMO_CATEGORIES = ["achat_produit", "service", "don", "salaire", "remboursement", "echange", "autre"]


class PaymentEngine:
    """Moteur de paiement BITROOT P2P."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.invoices: list[dict] = []
        self.queue: list[dict] = []
        self.rates: dict = {"brt_per_eur": 0.0, "eur_per_brt": 0.0, "updated": ""}
        self._load()

    def _load(self):
        if INVOICES_FILE.exists():
            try:
                self.invoices = json.loads(INVOICES_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.invoices = []
        if QUEUE_FILE.exists():
            try:
                self.queue = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.queue = []
        if RATES_FILE.exists():
            try:
                self.rates = json.loads(RATES_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _save_invoices(self):
        INVOICES_FILE.write_text(
            json.dumps(self.invoices, indent=2, ensure_ascii=False), encoding="utf-8")

    def _save_queue(self):
        QUEUE_FILE.write_text(
            json.dumps(self.queue, indent=2, ensure_ascii=False), encoding="utf-8")

    def _save_rates(self):
        RATES_FILE.write_text(
            json.dumps(self.rates, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Transactions ────────────────────────────────────

    def create_transaction(self, from_address: str, to_address: str,
                           amount_brt: float, memo: str = "",
                           category: str = "autre") -> dict:
        """Crée une transaction BITROOT signée localement."""
        if category not in MEMO_CATEGORIES:
            category = "autre"
        amount_wei = int(Decimal(str(amount_brt)) * Decimal(str(WEI_PER_BRT)))
        nonce = int(time.time() * 1000) % 2**32

        tx = {
            "from": from_address,
            "to": to_address,
            "value_wei": amount_wei,
            "value_brt": amount_brt,
            "gas_limit": GAS_LIMIT_DEFAULT,
            "gas_price_gwei": GAS_PRICE_GWEI,
            "nonce": nonce,
            "memo": memo,
            "category": category,
            "chain_id": 100,  # Gnosis par défaut
            "created": datetime.now().isoformat(),
            "status": "draft",
            "tx_hash": None,
            "block_number": None,
        }
        return tx

    def sign_and_send(self, tx: dict, private_key: str,
                      rpc_url: str = "https://rpc.gnosis.gateway.fm") -> dict:
        """Signe et envoie une transaction sur la blockchain."""
        from web3 import Web3
        from eth_account import Account

        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            tx["status"] = "offline"
            tx["error"] = "RPC non joignable"
            return tx

        try:
            acct = Account.from_key(private_key)
            nonce = w3.eth.get_transaction_count(acct.address)

            chain_id = tx.get("chain_id", 100)
            gas_price = w3.eth.gas_price
            tx_data = {
                "nonce": nonce,
                "to": tx["to"],
                "value": tx["value_wei"],
                "gas": tx.get("gas_limit", GAS_LIMIT_DEFAULT),
                "gasPrice": gas_price,
                "chainId": chain_id,
            }

            # Ajouter data si mémo
            if tx.get("memo"):
                memo_hex = tx["memo"].encode().hex()
                tx_data["data"] = "0x" + memo_hex

            signed = acct.sign_transaction(tx_data)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

            tx["status"] = "sent"
            tx["tx_hash"] = tx_hash.hex()
            tx["nonce"] = nonce
            tx["sent_at"] = datetime.now().isoformat()

            # Ajouter à la file d'attente pour confirmation
            self.queue.append(tx)
            self._save_queue()

            from .wallet import wallet_manager
            wallet_manager.add_transaction(tx)

            log.info("Transaction envoyée", tx_hash=tx["tx_hash"],
                     from_addr=tx["from"], to_addr=tx["to"],
                     amount=tx["value_brt"])
            return tx

        except Exception as e:
            tx["status"] = "error"
            tx["error"] = str(e)
            log.warning("Erreur envoi transaction", error=str(e))
            return tx

    def send_offline(self, tx: dict) -> dict:
        """Enregistre une transaction en mode offline (queue pour envoi ultérieur)."""
        tx["status"] = "queued"
        tx["queued_at"] = datetime.now().isoformat()
        self.queue.append(tx)
        self._save_queue()

        from .wallet import wallet_manager
        wallet_manager.add_transaction(tx)

        log.info("Transaction mise en file d'attente", from_addr=tx["from"],
                 to_addr=tx["to"], amount=tx["value_brt"])
        return tx

    def process_queue(self, rpc_url: str = "https://rpc.gnosis.gateway.fm",
                      password: str = "pixelos_default") -> list[dict]:
        """Tente d'envoyer toutes les transactions en attente."""
        from .wallet import wallet_manager
        results = []
        remaining = []

        for tx in self.queue:
            if tx.get("status") in ("sent", "confirmed", "failed"):
                continue
            pk = wallet_manager.get_private_key(tx["from"], password)
            if not pk:
                tx["error"] = "Clé privée indisponible"
                results.append(tx)
                continue
            result = self.sign_and_send(tx, pk, rpc_url)
            results.append(result)
            if result.get("status") == "error":
                remaining.append(tx)

        self.queue = remaining
        self._save_queue()
        return results

    def confirm_transaction(self, tx_hash: str,
                            rpc_url: str = "https://rpc.gnosis.gateway.fm") -> Optional[dict]:
        """Vérifie le statut d'une transaction sur la blockchain."""
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            return None
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if receipt:
                for tx in self.queue:
                    if tx.get("tx_hash") == tx_hash:
                        tx["status"] = "confirmed" if receipt["status"] == 1 else "failed"
                        tx["block_number"] = receipt["blockNumber"]
                        tx["confirmed_at"] = datetime.now().isoformat()
                        self._save_queue()
                        return tx
                return {
                    "tx_hash": tx_hash,
                    "status": "confirmed" if receipt["status"] == 1 else "failed",
                    "block_number": receipt["blockNumber"],
                    "gas_used": receipt["gasUsed"],
                }
        except Exception:
            pass
        return None

    # ── Factures (Invoices) ─────────────────────────────

    def create_invoice(self, from_address: str, to_address: str,
                       amount_brt: float, label: str = "",
                       description: str = "", due_date: str = "") -> dict:
        """Crée une facture en BITROOT."""
        inv = {
            "id": hashlib.sha256(f"{from_address}{to_address}{time.time()}".encode()).hexdigest()[:12],
            "from": from_address,
            "to": to_address,
            "amount_brt": amount_brt,
            "amount_wei": int(Decimal(str(amount_brt)) * Decimal(str(WEI_PER_BRT))),
            "label": label or f"Facture {amount_brt} BRT",
            "description": description,
            "due_date": due_date,
            "status": "emise",
            "created": datetime.now().isoformat(),
            "paid_at": None,
            "tx_hash": None,
        }
        self.invoices.insert(0, inv)
        self._save_invoices()
        return inv

    def list_invoices(self, address: str = None, status: str = None) -> list[dict]:
        results = self.invoices
        if address:
            addr_lower = address.lower()
            results = [i for i in results
                       if i["from"].lower() == addr_lower
                       or i["to"].lower() == addr_lower]
        if status:
            results = [i for i in results if i["status"] == status]
        return results

    def mark_invoice_paid(self, invoice_id: str, tx_hash: str) -> Optional[dict]:
        for inv in self.invoices:
            if inv["id"] == invoice_id:
                inv["status"] = "payee"
                inv["paid_at"] = datetime.now().isoformat()
                inv["tx_hash"] = tx_hash
                self._save_invoices()
                return inv
        return None

    def invoice_qr_data(self, invoice_id: str) -> Optional[str]:
        for inv in self.invoices:
            if inv["id"] == invoice_id:
                data = (f"ethereum:{inv['to']}"
                        f"?value={inv['amount_wei']}"
                        f"&label={inv['label']}")
                return data
        return None

    # ── Taux de Change ─────────────────────────────────

    def set_rate(self, brt_per_eur: float):
        """Définit manuellement le taux BRT/EUR."""
        self.rates = {
            "brt_per_eur": brt_per_eur,
            "eur_per_brt": round(1.0 / brt_per_eur, 6) if brt_per_eur > 0 else 0,
            "updated": datetime.now().isoformat(),
        }
        self._save_rates()

    def convert_brt_to_eur(self, amount_brt: float) -> float:
        return round(amount_brt * self.rates.get("brt_per_eur", 1.0), 2)

    def convert_eur_to_brt(self, amount_eur: float) -> float:
        rate = self.rates.get("eur_per_brt", 1.0)
        return round(amount_eur * rate, 4)

    def get_rates(self) -> dict:
        return self.rates

    # ── Stats ───────────────────────────────────────────

    def stats(self) -> dict:
        total_sent = sum(t.get("value_brt", 0) for t in self.queue
                        if t.get("status") in ("sent", "confirmed"))
        pending = sum(1 for t in self.queue if t.get("status") == "queued")
        return {
            "queue_length": len(self.queue),
            "pending_count": pending,
            "total_sent_brt": round(total_sent, 4),
            "invoice_count": len(self.invoices),
            "paid_invoices": sum(1 for i in self.invoices if i["status"] == "payee"),
            "rates": self.rates,
        }


payment_engine = PaymentEngine()
