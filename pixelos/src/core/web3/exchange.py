# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""Pixel Exchange — Marché P2P BITROOT entre membres de la communauté.

Architecture:
  - Annonces de vente/achat de produits agricoles en BRT
  - Catalogue local des produits disponibles
  - Transactions P2P avec escrow simplifié
  - Commandes et suivi de livraison
"""

import json
import structlog
import uuid
import hashlib
import time
from pathlib import Path
from datetime import datetime, date
from typing import Optional

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "web3" / "exchange"
LISTINGS_FILE = DATA_DIR / "listings.json"
ORDERS_FILE = DATA_DIR / "orders.json"
CATALOG_FILE = DATA_DIR / "catalog.json"

LISTING_TYPES = ["vente", "achat", "service", "don"]
LISTING_STATUSES = ["active", "reserved", "sold", "cancelled", "expired"]
ORDER_STATUSES = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
PRODUCT_CATEGORIES = [
    "legume", "fruit", "herbe_aromatique", "plante", "graine",
    "outil", "service", "transformation", "autre",
]


class ExchangeMarket:
    """Marché P2P BITROOT entre membres."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.listings: list[dict] = []
        self.orders: list[dict] = []
        self.catalog: list[dict] = []
        self._load()

    def _load(self):
        for f, attr in [(LISTINGS_FILE, "listings"),
                         (ORDERS_FILE, "orders"),
                         (CATALOG_FILE, "catalog")]:
            if f.exists():
                try:
                    setattr(self, attr, json.loads(f.read_text(encoding="utf-8")))
                except Exception:
                    setattr(self, attr, [])

    def _save_listings(self):
        LISTINGS_FILE.write_text(
            json.dumps(self.listings, indent=2, ensure_ascii=False), encoding="utf-8")

    def _save_orders(self):
        ORDERS_FILE.write_text(
            json.dumps(self.orders, indent=2, ensure_ascii=False), encoding="utf-8")

    def _save_catalog(self):
        CATALOG_FILE.write_text(
            json.dumps(self.catalog, indent=2, ensure_ascii=False), encoding="utf-8")

    def _generate_id(self, prefix: str = "EX") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

    # ── Annonces ────────────────────────────────────────

    def create_listing(self, seller_address: str, product_name: str,
                       price_brt: float, quantity_kg: float = 1.0,
                       category: str = "legume",
                       listing_type: str = "vente",
                       description: str = "",
                       location: str = "",
                       images: list[str] = None,
                       organic: bool = False,
                       variety: str = "") -> dict:
        """Crée une annonce de vente/achat en BITROOT."""
        if category not in PRODUCT_CATEGORIES:
            category = "autre"
        if listing_type not in LISTING_TYPES:
            listing_type = "vente"

        listing = {
            "id": self._generate_id("ANN"),
            "seller": seller_address,
            "product_name": product_name,
            "variety": variety,
            "price_brt": price_brt,
            "price_eur": round(price_brt * 0.5, 2),  # taux estimé
            "quantity_kg": quantity_kg,
            "category": category,
            "type": listing_type,
            "description": description,
            "location": location,
            "images": images or [],
            "organic": organic,
            "status": "active",
            "created": datetime.now().isoformat(),
            "expires": "",
            "views": 0,
        }
        self.listings.insert(0, listing)
        self._save_listings()
        log.info("Annonce créée", id=listing["id"], product=product_name,
                 price=price_brt, seller=seller_address[:8])
        return listing

    def search_listings(self, query: str = "", category: str = None,
                        listing_type: str = None, min_price: float = None,
                        max_price: float = None, organic: bool = None,
                        seller: str = None, location: str = None) -> list[dict]:
        """Recherche dans les annonces actives."""
        results = []
        q = query.lower() if query else ""

        for l in self.listings:
            if l.get("status") != "active":
                continue
            if category and l.get("category") != category:
                continue
            if listing_type and l.get("type") != listing_type:
                continue
            if seller and l.get("seller", "").lower() != seller.lower():
                continue
            if organic is not None and l.get("organic") != organic:
                continue
            if location and location.lower() not in l.get("location", "").lower():
                continue
            if min_price is not None and l.get("price_brt", 0) < min_price:
                continue
            if max_price is not None and l.get("price_brt", 0) > max_price:
                continue
            if q and q not in l.get("product_name", "").lower() \
                   and q not in l.get("description", "").lower() \
                   and q not in l.get("variety", "").lower():
                continue
            results.append(l)
        return results

    def get_listing(self, listing_id: str) -> Optional[dict]:
        for l in self.listings:
            if l["id"] == listing_id:
                l["views"] = l.get("views", 0) + 1
                self._save_listings()
                return l
        return None

    def update_listing(self, listing_id: str, **kwargs) -> Optional[dict]:
        for l in self.listings:
            if l["id"] == listing_id:
                for k in ("product_name", "price_brt", "quantity_kg",
                          "description", "status", "location", "organic", "variety"):
                    if k in kwargs and kwargs[k] is not None:
                        l[k] = kwargs[k]
                l["updated"] = datetime.now().isoformat()
                self._save_listings()
                return l
        return None

    def my_listings(self, seller_address: str) -> list[dict]:
        return [l for l in self.listings
                if l.get("seller", "").lower() == seller_address.lower()]

    # ── Commandes ───────────────────────────────────────

    def create_order(self, listing_id: str, buyer_address: str,
                     quantity_kg: float = None) -> Optional[dict]:
        """Crée une commande pour une annonce."""
        listing = self.get_listing(listing_id)
        if not listing:
            return None
        if listing.get("status") != "active":
            return {"error": "Annonce non disponible"}

        qty = quantity_kg or listing.get("quantity_kg", 1)
        total_brt = round(listing["price_brt"] * qty / listing.get("quantity_kg", 1), 4)

        order = {
            "id": self._generate_id("CMD"),
            "listing_id": listing_id,
            "listing": listing["product_name"],
            "seller": listing["seller"],
            "buyer": buyer_address,
            "quantity_kg": qty,
            "price_brt": listing["price_brt"],
            "total_brt": total_brt,
            "status": "pending",
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
            "tx_hash": None,
            "notes": "",
        }
        self.orders.insert(0, order)

        # Marquer l'annonce comme réservée
        listing["status"] = "reserved"
        self._save_listings()
        self._save_orders()

        log.info("Commande créée", id=order["id"], buyer=buyer_address[:8],
                 product=listing["product_name"], total=total_brt)
        return order

    def confirm_order(self, order_id: str, tx_hash: str) -> Optional[dict]:
        """Confirme le paiement d'une commande."""
        for o in self.orders:
            if o["id"] == order_id:
                o["status"] = "confirmed"
                o["tx_hash"] = tx_hash
                o["updated"] = datetime.now().isoformat()

                # Marquer l'annonce comme vendue
                for l in self.listings:
                    if l["id"] == o["listing_id"]:
                        l["status"] = "sold"
                        break
                self._save_listings()
                self._save_orders()
                return o
        return None

    def update_order(self, order_id: str, status: str,
                     notes: str = None) -> Optional[dict]:
        if status not in ORDER_STATUSES:
            return None
        for o in self.orders:
            if o["id"] == order_id:
                o["status"] = status
                o["updated"] = datetime.now().isoformat()
                if notes is not None:
                    o["notes"] = notes
                self._save_orders()
                return o
        return None

    def my_orders(self, address: str) -> dict:
        """Commandes en tant qu'acheteur et vendeur."""
        addr_lower = address.lower()
        return {
            "as_buyer": [o for o in self.orders
                        if o.get("buyer", "").lower() == addr_lower],
            "as_seller": [o for o in self.orders
                         if o.get("seller", "").lower() == addr_lower],
        }

    # ── Catalogue Produits ──────────────────────────────

    def add_to_catalog(self, name: str, category: str = "legume",
                       description: str = "", unit: str = "kg",
                       default_price_brt: float = 0,
                       variety: str = "") -> dict:
        """Ajoute un produit au catalogue local."""
        item = {
            "id": self._generate_id("CAT"),
            "name": name,
            "variety": variety,
            "category": category if category in PRODUCT_CATEGORIES else "autre",
            "description": description,
            "unit": unit,
            "default_price_brt": default_price_brt,
            "created": datetime.now().isoformat(),
        }
        self.catalog.append(item)
        self._save_catalog()
        return item

    def search_catalog(self, query: str = "", category: str = None) -> list[dict]:
        q = query.lower() if query else ""
        results = []
        for c in self.catalog:
            if category and c.get("category") != category:
                continue
            if q and q not in c.get("name", "").lower() \
                   and q not in c.get("description", "").lower():
                continue
            results.append(c)
        return results

    # ── Stats ───────────────────────────────────────────

    def stats(self) -> dict:
        active = [l for l in self.listings if l.get("status") == "active"]
        return {
            "active_listings": len(active),
            "total_listings": len(self.listings),
            "orders": len(self.orders),
            "confirmed_orders": sum(1 for o in self.orders if o["status"] == "confirmed"),
            "catalog_items": len(self.catalog),
            "categories": {c: sum(1 for l in active if l.get("category") == c)
                          for c in PRODUCT_CATEGORIES},
            "total_value_brt": round(sum(l.get("price_brt", 0)
                                        for l in active), 4),
        }


exchange_market = ExchangeMarket()
