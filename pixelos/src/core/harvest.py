# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""PixelOS HarvestManager - Prevision recolte, poids/prix, lots, etiquettes, inventaire.

Architecture:
  ProductionLine → Ligne de plantation avec rendement estime
  HarvestBatch   → Lot recolte avec poids/prix/qualite
  Label          → Etiquette QR/Code-barres pour tracabilite
  Inventory      → Stock (en_culture, pret_vente, distribue)
  HarvestManager → Orchestrateur prevision + recolte + distribution
"""

import json
import uuid
import structlog
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Any

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "harvest"

QUALITY_GRADES = ["A", "B", "C", "D"]
BATCH_STATUSES = ["pending", "labeled", "stored", "distributed", "sold"]
LINE_STATUSES = ["active", "harvested", "fallow"]


# ── ProductionLine ──────────────────────────────────────────

class ProductionLine:
    """Ligne de plantation avec suivi de rendement."""

    def __init__(self, line_id: str, zone_id: str = "", label: str = "",
                 product_id: str = "", plant_count: int = 0,
                 planted_at: str = None, row_spacing_cm: float = 50.0,
                 plant_spacing_cm: float = 30.0):
        self.line_id = line_id
        self.zone_id = zone_id
        self.label = label or line_id
        self.product_id = product_id
        self.plant_count = plant_count
        self.planted_at = planted_at
        self.row_spacing_cm = row_spacing_cm
        self.plant_spacing_cm = plant_spacing_cm
        self.status = "active"
        self.expected_yield_kg = 0.0
        self.estimated_value = 0.0
        self.actual_yield_kg = 0.0
        self.notes = ""

    def estimate_yield(self, yield_per_plant_kg: float = 1.5,
                       unit_price: float = 3.0) -> dict:
        self.expected_yield_kg = round(self.plant_count * yield_per_plant_kg, 2)
        self.estimated_value = round(self.expected_yield_kg * unit_price, 2)
        return {
            "expected_yield_kg": self.expected_yield_kg,
            "estimated_value": self.estimated_value,
            "plant_count": self.plant_count,
            "yield_per_plant_kg": yield_per_plant_kg,
            "unit_price": unit_price,
        }

    def snapshot(self) -> dict:
        return {
            "line_id": self.line_id,
            "zone_id": self.zone_id,
            "label": self.label,
            "product_id": self.product_id,
            "plant_count": self.plant_count,
            "planted_at": self.planted_at,
            "status": self.status,
            "expected_yield_kg": self.expected_yield_kg,
            "estimated_value": self.estimated_value,
            "actual_yield_kg": self.actual_yield_kg,
            "row_spacing_cm": self.row_spacing_cm,
            "plant_spacing_cm": self.plant_spacing_cm,
            "notes": self.notes,
        }


# ── HarvestBatch ─────────────────────────────────────────────

class HarvestBatch:
    """Lot de recolte avec suivi poids/prix/qualite."""

    def __init__(self, batch_id: str, product_id: str,
                 zone_id: str = "", line_id: str = "",
                 harvest_date: str = None):
        self.batch_id = batch_id
        self.product_id = product_id
        self.zone_id = zone_id
        self.line_id = line_id
        self.harvest_date = harvest_date or date.today().isoformat()
        self.weight_kg = 0.0
        self.unit_price = 0.0
        self.total_value = 0.0
        self.quality_grade = "A"
        self.status = "pending"
        self.label_id = None
        self.stored_at = None
        self.distributed_at = None
        self.destination = ""
        self.notes = ""

    @property
    def total_value_calc(self) -> float:
        return round(self.weight_kg * self.unit_price, 2)

    def set_price(self, unit_price: float):
        self.unit_price = unit_price
        self.total_value = self.total_value_calc

    def snapshot(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "product_id": self.product_id,
            "zone_id": self.zone_id,
            "line_id": self.line_id,
            "harvest_date": self.harvest_date,
            "weight_kg": self.weight_kg,
            "unit_price": self.unit_price,
            "total_value": self.total_value or self.total_value_calc,
            "quality_grade": self.quality_grade,
            "status": self.status,
            "label_id": self.label_id,
            "stored_at": self.stored_at,
            "distributed_at": self.distributed_at,
            "destination": self.destination,
            "notes": self.notes,
        }


# ── Label ────────────────────────────────────────────────────

class Label:
    """Etiquette de tracabilite (QR/Code-barres)."""

    def __init__(self, label_id: str, batch_id: str,
                 product: str = "", variety: str = "",
                 zone: str = "", weight_kg: float = 0.0,
                 unit_price: float = 0.0, harvest_date: str = None,
                 quality: str = "A"):
        self.label_id = label_id
        self.batch_id = batch_id
        self.product = product
        self.variety = variety
        self.zone = zone
        self.weight_kg = weight_kg
        self.unit_price = unit_price
        self.total = round(weight_kg * unit_price, 2)
        self.harvest_date = harvest_date or date.today().isoformat()
        self.quality = quality
        self.qr_data = self._generate_qr_data()

    def _generate_qr_data(self) -> str:
        data = (f"PIXELOS-BATCH:{self.batch_id}|"
                f"PROD:{self.product}|"
                f"ZONE:{self.zone}|"
                f"POIDS:{self.weight_kg}kg|"
                f"DATE:{self.harvest_date}|"
                f"QUAL:{self.quality}")
        return data

    def snapshot(self) -> dict:
        return {
            "label_id": self.label_id,
            "batch_id": self.batch_id,
            "product": self.product,
            "variety": self.variety,
            "zone": self.zone,
            "weight_kg": self.weight_kg,
            "unit_price": self.unit_price,
            "total": self.total,
            "harvest_date": self.harvest_date,
            "quality": self.quality,
            "qr_data": self.qr_data,
        }


# ── Inventory ────────────────────────────────────────────────

class Inventory:
    """Stock agricole (en_culture, pret_vente, distribue)."""

    def __init__(self):
        self.en_culture_kg = 0.0
        self.pret_vente_kg = 0.0
        self.distribue_kg = 0.0
        self.vendu_kg = 0.0
        self.valeur_totale = 0.0
        self.last_updated = None

    def snapshot(self) -> dict:
        return {
            "en_culture_kg": round(self.en_culture_kg, 2),
            "pret_vente_kg": round(self.pret_vente_kg, 2),
            "distribue_kg": round(self.distribue_kg, 2),
            "vendu_kg": round(self.vendu_kg, 2),
            "total_stock_kg": round(self.en_culture_kg + self.pret_vente_kg, 2),
            "valeur_totale": round(self.valeur_totale, 2),
            "last_updated": self.last_updated,
        }


# ── HarvestManager ──────────────────────────────────────────

YIELD_DEFAULTS = {
    "tomate_coeur_de_boeuf": {"kg_per_plant": 2.5, "price_per_kg": 4.50},
    "laitue_romaine": {"kg_per_plant": 0.4, "price_per_kg": 2.80},
    "pommier_golden": {"kg_per_plant": 25.0, "price_per_kg": 3.20},
    "basilic_grand_vert": {"kg_per_plant": 0.3, "price_per_kg": 8.00},
}

DEFAULT_LINES = [
    {"line_id": "serre_a_l1", "zone_id": "serre_a", "label": "Serre A - Ligne 1",
     "product_id": "tomate_coeur_de_boeuf", "plant_count": 20,
     "planted_at": "2026-03-15", "row_spacing_cm": 60, "plant_spacing_cm": 40},
    {"line_id": "serre_a_l2", "zone_id": "serre_a", "label": "Serre A - Ligne 2",
     "product_id": "tomate_coeur_de_boeuf", "plant_count": 18,
     "planted_at": "2026-03-15", "row_spacing_cm": 60, "plant_spacing_cm": 40},
    {"line_id": "serre_b_l1", "zone_id": "serre_b", "label": "Serre B - Ligne 1",
     "product_id": "laitue_romaine", "plant_count": 40,
     "planted_at": "2026-04-01", "row_spacing_cm": 30, "plant_spacing_cm": 25},
    {"line_id": "plein_champ_l1", "zone_id": "plein_champ", "label": "Plein Champ - Ligne 1",
     "product_id": "pommier_golden", "plant_count": 8,
     "planted_at": "2024-11-01", "row_spacing_cm": 400, "plant_spacing_cm": 300},
    {"line_id": "pepiniere_t1", "zone_id": "pepiniere", "label": "Pepiniere - Table 1",
     "product_id": "basilic_grand_vert", "plant_count": 30,
     "planted_at": "2026-05-01", "row_spacing_cm": 20, "plant_spacing_cm": 15},
]


class HarvestManager:
    """Orchestrateur prevision recolte, lots, etiquettes, inventaire."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.lines: dict[str, ProductionLine] = {}
        self.batches: dict[str, HarvestBatch] = {}
        self.labels: dict[str, Label] = {}
        self.inventory = Inventory()
        self._load_config()

    def _config_path(self):
        return DATA_DIR / "harvest.json"

    def _load_config(self):
        path = self._config_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self._init_lines(cfg.get("lines", DEFAULT_LINES))
                self._init_batches(cfg.get("batches", []))
                self._init_labels(cfg.get("labels", []))
                inv = cfg.get("inventory", {})
                if inv:
                    self.inventory = Inventory()
                    self.inventory.en_culture_kg = inv.get("en_culture_kg", 0)
                    self.inventory.pret_vente_kg = inv.get("pret_vente_kg", 0)
                    self.inventory.distribue_kg = inv.get("distribue_kg", 0)
                    self.inventory.vendu_kg = inv.get("vendu_kg", 0)
                    self.inventory.valeur_totale = inv.get("valeur_totale", 0)
                log.info("Configuration harvest chargee",
                         lines=len(self.lines), batches=len(self.batches))
            except Exception as e:
                log.warning("Erreur chargement harvest", error=str(e))
                self._init_defaults()
        else:
            self._init_defaults()
        self._save_config()

    def _init_defaults(self):
        self._init_lines(DEFAULT_LINES)
        self.batches = {}
        self.labels = {}
        self.inventory = Inventory()

    def _init_lines(self, configs: list[dict]):
        self.lines = {}
        for c in configs:
            lid = c.get("line_id") or c.get("id")
            line = ProductionLine(lid, c.get("zone_id", ""),
                                 c.get("label", ""), c.get("product_id", ""),
                                 c.get("plant_count", 0), c.get("planted_at"),
                                 c.get("row_spacing_cm", 50),
                                 c.get("plant_spacing_cm", 30))
            line.status = c.get("status", "active")
            line.expected_yield_kg = c.get("expected_yield_kg", 0)
            line.estimated_value = c.get("estimated_value", 0)
            line.actual_yield_kg = c.get("actual_yield_kg", 0)
            self.lines[lid] = line

    def _init_batches(self, configs: list[dict]):
        self.batches = {}
        for c in configs:
            bid = c.get("batch_id") or c.get("id")
            b = HarvestBatch(bid, c["product_id"],
                            c.get("zone_id", ""), c.get("line_id", ""),
                            c.get("harvest_date"))
            b.weight_kg = c.get("weight_kg", 0)
            b.unit_price = c.get("unit_price", 0)
            b.total_value = c.get("total_value", 0)
            b.quality_grade = c.get("quality_grade", "A")
            b.status = c.get("status", "pending")
            b.label_id = c.get("label_id")
            b.stored_at = c.get("stored_at")
            b.distributed_at = c.get("distributed_at")
            b.destination = c.get("destination", "")
            b.notes = c.get("notes", "")
            self.batches[bid] = b

    def _init_labels(self, configs: list[dict]):
        self.labels = {}
        for c in configs:
            lid = c.get("label_id") or c.get("id")
            lbl = Label(lid, c["batch_id"],
                       c.get("product", ""), c.get("variety", ""),
                       c.get("zone", ""), c.get("weight_kg", 0),
                       c.get("unit_price", 0), c.get("harvest_date"),
                       c.get("quality", "A"))
            self.labels[lid] = lbl

    def _save_config(self):
        cfg = {
            "lines": [l.snapshot() for l in self.lines.values()],
            "batches": [b.snapshot() for b in self.batches.values()],
            "labels": [lbl.snapshot() for lbl in self.labels.values()],
            "inventory": self.inventory.snapshot(),
            "updated": datetime.now().isoformat(),
        }
        with open(self._config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

    # ── Estimation / Prediction ────────────────────────────

    def estimate_all(self) -> list[dict]:
        results = []
        for lid, line in self.lines.items():
            if line.status != "active":
                continue
            defaults = YIELD_DEFAULTS.get(line.product_id, {"kg_per_plant": 1.0, "price_per_kg": 3.0})
            r = line.estimate_yield(defaults["kg_per_plant"], defaults["price_per_kg"])
            results.append({"line_id": lid, **r})
        self._update_inventory()
        self._save_config()
        return results

    def predict_by_zone(self, zone_id: str = None) -> dict:
        """Prediction de rendement par zone."""
        zones = {}
        for line in self.lines.values():
            if zone_id and line.zone_id != zone_id:
                continue
            if line.status != "active":
                continue
            zid = line.zone_id
            if zid not in zones:
                zones[zid] = {"zone_id": zid, "lines": 0, "plants": 0,
                             "expected_kg": 0.0, "estimated_value": 0.0}
            zones[zid]["lines"] += 1
            zones[zid]["plants"] += line.plant_count
            zones[zid]["expected_kg"] += line.expected_yield_kg
            zones[zid]["estimated_value"] += line.estimated_value
        for z in zones.values():
            z["expected_kg"] = round(z["expected_kg"], 2)
            z["estimated_value"] = round(z["estimated_value"], 2)
        return zones

    # ── Harvest (Recolte) ──────────────────────────────────

    def create_batch(self, line_id: str, weight_kg: float,
                     unit_price: float = None, quality: str = "A",
                     harvest_date: str = None) -> dict | None:
        line = self.lines.get(line_id)
        if not line:
            return None
        if line.status != "active":
            return None

        batch_id = f"REC-{date.today().isoformat()}-{str(uuid.uuid4())[:4]}"
        b = HarvestBatch(batch_id, line.product_id,
                        line.zone_id, line_id, harvest_date)
        b.weight_kg = weight_kg
        b.quality_grade = quality

        if unit_price is not None:
            b.set_price(unit_price)
        else:
            defaults = YIELD_DEFAULTS.get(line.product_id, {"price_per_kg": 3.0})
            b.set_price(defaults["price_per_kg"])

        self.batches[batch_id] = b

        # Marquer la ligne comme partiellement recoltee
        line.actual_yield_kg += weight_kg

        # Generer etiquette automatiquement
        label = self._create_label(b)
        b.label_id = label.label_id
        b.status = "labeled"

        self._update_inventory()
        self._save_config()

        log.info("Lot recolte cree", batch=batch_id, line=line_id,
                 weight=weight_kg, value=b.total_value)
        return b.snapshot()

    def _create_label(self, batch: HarvestBatch) -> Label:
        from core.lifecycle import LifecycleManager
        label_id = f"LBL-{batch.batch_id}"
        product_name = batch.product_id
        variety = ""
        try:
            lm = LifecycleManager()
            p = lm.get_product(batch.product_id)
            if p:
                product_name = p.get("label", batch.product_id)
                variety = p.get("variete", "")
        except Exception:
            pass

        lbl = Label(label_id, batch.batch_id,
                   product_name, variety,
                   batch.zone_id, batch.weight_kg,
                   batch.unit_price, batch.harvest_date,
                   batch.quality_grade)
        self.labels[label_id] = lbl
        return lbl

    def update_batch(self, batch_id: str, **kwargs) -> dict | None:
        b = self.batches.get(batch_id)
        if not b:
            return None
        for k in ("weight_kg", "unit_price", "quality_grade", "status",
                  "destination", "notes"):
            if k in kwargs and kwargs[k] is not None:
                setattr(b, k, kwargs[k])
        if "unit_price" in kwargs:
            b.total_value = b.total_value_calc
        if "status" in kwargs:
            if kwargs["status"] == "stored":
                b.stored_at = datetime.now().isoformat()
            elif kwargs["status"] == "distributed":
                b.distributed_at = datetime.now().isoformat()
        self._update_inventory()
        self._save_config()
        return b.snapshot()

    # ── Labels ─────────────────────────────────────────────

    def get_labels_for_batch(self, batch_id: str) -> list[dict]:
        return [lbl.snapshot() for lbl in self.labels.values()
                if lbl.batch_id == batch_id]

    # ── Inventory ──────────────────────────────────────────

    def _update_inventory(self):
        total_en_culture = sum(l.expected_yield_kg - l.actual_yield_kg
                              for l in self.lines.values() if l.status == "active")
        total_pret_vente = sum(b.weight_kg for b in self.batches.values()
                              if b.status in ("labeled", "stored"))
        total_distribue = sum(b.weight_kg for b in self.batches.values()
                            if b.status == "distributed")
        total_vendu = sum(b.weight_kg for b in self.batches.values()
                         if b.status == "sold")
        valeur = sum(b.total_value for b in self.batches.values()
                    if b.status in ("labeled", "stored", "distributed"))

        self.inventory.en_culture_kg = max(0, total_en_culture)
        self.inventory.pret_vente_kg = total_pret_vente
        self.inventory.distribue_kg = total_distribue
        self.inventory.vendu_kg = total_vendu
        self.inventory.valeur_totale = valeur
        self.inventory.last_updated = datetime.now().isoformat()

    # ── Suggestions ────────────────────────────────────────

    def get_harvest_suggestions(self) -> list[dict]:
        """Suggestions de recolte basees sur les cycles de vie."""
        from core.lifecycle import LifecycleManager
        lm = LifecycleManager()
        suggestions = []

        for line in self.lines.values():
            if line.status != "active":
                continue
            if not line.product_id:
                continue

            # Trouver les plantations actives sur cette ligne
            for pl in lm.list_plantations():
                if pl.get("sub_zone_id") != line.line_id and pl.get("espace_id") != line.zone_id:
                    continue
                if pl.get("status") != "active":
                    continue

                day = pl.get("day_of_cycle", 0)
                product = lm.get_product(line.product_id)
                if not product:
                    continue

                stage = None
                for s in product.get("stages", []):
                    if s.get("day_start", 0) <= day <= s.get("day_end", 999):
                        stage = s
                        break

                if stage and stage["name"] == "recolte":
                    defaults = YIELD_DEFAULTS.get(line.product_id, {})
                    kg = defaults.get("kg_per_plant", 1.0) * line.plant_count * 0.3
                    suggestions.append({
                        "type": "harvest_ready",
                        "line_id": line.line_id,
                        "product": product.get("label", line.product_id),
                        "zone": line.zone_id,
                        "estimated_kg": round(kg, 1),
                        "estimated_value": round(kg * defaults.get("price_per_kg", 3.0), 2),
                        "day": day,
                        "message": (f"{product.get('label', line.product_id)} pret a recolter "
                                   f"sur {line.label} (~{round(kg,1)}kg estimes)"),
                        "priority": "high",
                    })
        return suggestions

    # ── API Publique ───────────────────────────────────────

    def list_lines(self) -> list[dict]:
        return [l.snapshot() for l in self.lines.values()]

    def get_line(self, line_id: str) -> dict | None:
        l = self.lines.get(line_id)
        return l.snapshot() if l else None

    def list_batches(self, status: str = None) -> list[dict]:
        if status:
            return [b.snapshot() for b in self.batches.values() if b.status == status]
        return [b.snapshot() for b in self.batches.values()]

    def get_batch(self, batch_id: str) -> dict | None:
        b = self.batches.get(batch_id)
        return b.snapshot() if b else None

    def summary(self) -> dict:
        self._update_inventory()
        active_lines = sum(1 for l in self.lines.values() if l.status == "active")
        total_batches = len(self.batches)
        recent = [b.snapshot() for b in sorted(self.batches.values(),
                  key=lambda x: x.harvest_date, reverse=True)[:5]]
        return {
            "lines": len(self.lines),
            "active_lines": active_lines,
            "batches": total_batches,
            "recent_batches": recent,
            "inventory": self.inventory.snapshot(),
            "product_types": list(set(l.product_id for l in self.lines.values()
                                      if l.product_id)),
        }
