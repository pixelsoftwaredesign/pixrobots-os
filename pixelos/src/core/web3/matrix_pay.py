"""MatrixPay Bridge — Notifications de paiement via Matrix.

Relie le moteur de paiement BITROOT au bridge Matrix existant
pour notifier la communauté en temps réel.
"""

import structlog
import json
from datetime import datetime
from typing import Optional

log = structlog.get_logger()


class MatrixPayBridge:
    """Pont entre paiements BITROOT et notifications Matrix."""

    def __init__(self):
        self._enabled = True
        self._matrix_available = False
        self._check_matrix()

    def _check_matrix(self):
        try:
            from core.federation.matrix_bridge import matrix_bridge
            self._matrix_available = True
        except Exception:
            self._matrix_available = False

    def _get_matrix(self):
        if not self._matrix_available:
            return None
        try:
            from core.federation.matrix_bridge import matrix_bridge
            return matrix_bridge
        except Exception:
            return None

    def notify_payment(self, tx: dict) -> bool:
        """Envoie une notification Matrix pour un paiement effectué."""
        bridge = self._get_matrix()
        if not bridge or not self._enabled:
            return False

        amount = tx.get("value_brt", 0)
        sender = tx.get("from", "")[:10]
        receiver = tx.get("to", "")[:10]
        memo = tx.get("memo", "")

        msg = (
            f"💸 Paiement BITROOT\n"
            f"• Montant : {amount} BRT\n"
            f"• De : {sender}...\n"
            f"• À : {receiver}...\n"
            f"• Mémo : {memo or '(aucun)'}\n"
            f"• Statut : {tx.get('status', 'envoyé')}"
        )
        try:
            bridge.send_message(msg, msgtype="m.notice")
            log.info("Notification paiement envoyée Matrix", amount=amount)
            return True
        except Exception as e:
            log.warning("Échec notification Matrix", error=str(e))
            return False

    def notify_invoice(self, invoice: dict) -> bool:
        """Notifie la communauté d'une nouvelle facture."""
        bridge = self._get_matrix()
        if not bridge or not self._enabled:
            return False

        msg = (
            f"📄 Nouvelle facture BITROOT\n"
            f"• Montant : {invoice.get('amount_brt')} BRT\n"
            f"• De : {invoice.get('from', '')[:10]}...\n"
            f"• À : {invoice.get('to', '')[:10]}...\n"
            f"• Motif : {invoice.get('label', '')}\n"
            f"• Statut : {invoice.get('status', 'émise')}"
        )
        try:
            bridge.send_message(msg, msgtype="m.notice")
            return True
        except Exception as e:
            log.warning("Échec notification facture", error=str(e))
            return False

    def notify_new_listing(self, listing: dict) -> bool:
        """Notifie la communauté d'une nouvelle annonce."""
        bridge = self._get_matrix()
        if not bridge or not self._enabled:
            return False

        msg = (
            f"🛒 Nouvelle annonce sur le marché PixelOS\n"
            f"• Produit : {listing.get('product_name')}\n"
            f"• Prix : {listing.get('price_brt')} BRT\n"
            f"• Quantité : {listing.get('quantity_kg')} kg\n"
            f"• Vendeur : {listing.get('seller', '')[:10]}..."
        )
        try:
            bridge.send_message(msg, msgtype="m.notice")
            return True
        except Exception as e:
            log.warning("Échec notification annonce", error=str(e))
            return False

    def notify_new_order(self, order: dict) -> bool:
        """Notifie le vendeur d'une nouvelle commande."""
        bridge = self._get_matrix()
        if not bridge or not self._enabled:
            return False

        msg = (
            f"📦 Nouvelle commande\n"
            f"• Produit : {order.get('listing')}\n"
            f"• Total : {order.get('total_brt')} BRT\n"
            f"• Acheteur : {order.get('buyer', '')[:10]}..."
        )
        try:
            bridge.send_message(msg, msgtype="m.notice")
            return True
        except Exception as e:
            log.warning("Échec notification commande", error=str(e))
            return False

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def status(self) -> dict:
        return {
            "enabled": self._enabled,
            "matrix_available": self._matrix_available,
        }


matrix_pay_bridge = MatrixPayBridge()
