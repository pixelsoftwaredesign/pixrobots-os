# Pixel OS — Copyright 2026
# Free License — Verifiable and Reliable for Internet Users
# Pixel Software Design — Copyright 2026
import subprocess
import json
import os
from pathlib import Path


class NOPWalletBridge:
    def __init__(self):
        self.wallet_api = "http://127.0.0.1:9999/api/web3"
        self.available = False
        self._check_available()

    def _check_available(self):
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.wallet_api}/wallet/status")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                self.available = True
                return data
        except Exception:
            self.available = False
            return {"available": False}

    def is_available(self):
        return self.available

    def check_site_for_payment(self, url):
        if not self.available:
            return {"payment_required": False, "note": "wallet non disponible"}

        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.wallet_api}/payment/check",
                data=json.dumps({"url": url}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read())
        except Exception:
            return {"payment_required": False}

    def sign_transaction(self, tx_data):
        if not self.available:
            return {"status": "error", "error": "wallet non disponible"}

        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.wallet_api}/transaction/sign",
                data=json.dumps(tx_data).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_balance(self, address=None):
        if not self.available:
            return {"balance": "0", "error": "wallet non disponible"}

        try:
            import urllib.request
            params = f"?address={address}" if address else ""
            req = urllib.request.Request(f"{self.wallet_api}/wallet/balance{params}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"balance": "0", "error": str(e)}

    def prompt_payment(self, amount, to, description=""):
        return {
            "status": "prompted",
            "amount": amount,
            "to": to,
            "description": description,
            "note": "transaction soumise au wallet â€” validation requise",
        }
