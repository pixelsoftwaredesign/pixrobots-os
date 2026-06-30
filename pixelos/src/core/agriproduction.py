"""AgriProduction — Prévision pré-récolte, cycle récolte, tri, étiquetage, distribution.

Extension du HarvestManager avec cycle complet:
  Pré-récolte → Récolte → Tri/Calibrage → Étiquetage → Stockage → Distribution → Vente
  
Classes:
  HarvestForecast   → Prévision IA par zone/ligne avec données capteurs + cycle de vie
  SortingGrade      → Qualité: calibre, poids unitaire, défauts, classification
  DistributionOrder → Ordre de distribution avec traçabilité destination
  DeliveryNote      → Bon de livraison / facture
  SalesJournal      → Journal des ventes comptable
  LabelGenerator    → Génération PDF/ZPL avec QR pleine traçabilité
  AgriProduction    → Orchestrateur complet
"""

import json
import uuid
import structlog
import numpy as np
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "agriproduction"


# ── Constantes ──────────────────────────────────────────────

CALIBRE_CLASSES = ["extra", "I", "II", "III"]
SORTING_METHODS = ["manuel", "optique", "gravimétrique", "tamis"]
DEFECT_TYPES = ["meurtri", "pourri", "déformé", "taché", "verreux",
                "insecte", "moisissure", "fissuré", "immature", "sur-mûr"]
DISTRIBUTION_STATUSES = ["préparé", "chargé", "en_transit", "livré", "confirmé"]
PAYMENT_METHODS = ["espèces", "carte", "virement", "chèque", "facture"]
SORTING_OUTCOMES = ["commercialisable", "transformable", "déchet"]
CERTIFICATION_TYPES = ["bio", "label_rouge", "AOP", "IGP", "commerce_équitable",
                        "sans_OGM", "agriculture_raisonnée"]

# Normes de calibrage par produit (diamètre en mm)
CALIBRE_NORMS = {
    "tomate_coeur_de_boeuf": {"extra": (67, 999), "I": (57, 67), "II": (47, 57), "III": (0, 47)},
    "pommier_golden": {"extra": (70, 999), "I": (65, 70), "II": (60, 65), "III": (0, 60)},
    "laitue_romaine": {"extra": (400, 999), "I": (300, 400), "II": (200, 300), "III": (0, 200)},
    "basilic_grand_vert": {"extra": (15, 999), "I": (10, 15), "II": (5, 10), "III": (0, 5)},
}

PRIX_MARCHÉ = {
    "tomate_coeur_de_boeuf": 4.50,
    "tomate_cherry": 5.80,
    "laitue_romaine": 2.80,
    "pommier_golden": 3.20,
    "basilic_grand_vert": 8.00,
    "concombre": 3.50,
    "courgette": 3.00,
    "aubergine": 4.00,
    "poivron": 5.00,
    "fraise": 7.50,
    "melon": 4.50,
}


# ── HarvestForecast ─────────────────────────────────────────

class HarvestForecast:
    """Prévision de rendement pré-récolte par zone/ligne."""

    def __init__(self):
        self.confidence_level = 0.85

    def predict_line(self, line_id: str, product_id: str, plant_count: int,
                     days_since_planting: int, cycle_days: int,
                     avg_temperature: float = 20.0,
                     avg_humidity: float = 60.0,
                     avg_light_lux: float = 25000.0,
                     soil_moisture_avg: float = 45.0,
                     health_index: float = 0.9,
                     previous_yield_kg: float = None) -> dict:
        """Prévision de rendement pour une ligne avec paramètres culturaux."""
        base_yield_per_plant = self._base_yield(product_id)

        # Facteurs correctifs
        progress = min(1.0, days_since_planting / max(1, cycle_days))
        temp_factor = max(0.3, 1 - abs(avg_temperature - 22) * 0.02)
        hum_factor = max(0.3, 1 - abs(avg_humidity - 65) * 0.01)
        light_factor = max(0.3, min(1.2, avg_light_lux / 25000))
        moist_factor = max(0.3, min(1.1, soil_moisture_avg / 45))
        health_factor = max(0.1, health_index)

        if progress < 0.3:
            maturity_factor = 0.0
            confidence = 0.3
        elif progress < 0.6:
            maturity_factor = progress * 1.2
            confidence = 0.5
        elif progress < 0.85:
            maturity_factor = progress * 1.1
            confidence = 0.75
        else:
            maturity_factor = 1.0
            confidence = 0.9

        predicted_kg_per_plant = (base_yield_per_plant * maturity_factor
                                  * temp_factor * hum_factor * light_factor
                                  * moist_factor * health_factor)
        total_kg = round(predicted_kg_per_plant * plant_count, 2)
        unit_price = PRIX_MARCHÉ.get(product_id, 3.0)
        total_value = round(total_kg * unit_price, 2)

        # Comparaison avec historique si disponible
        if previous_yield_kg:
            deviation = ((total_kg - previous_yield_kg) / max(0.1, previous_yield_kg)) * 100
        else:
            deviation = 0

        return {
            "line_id": line_id,
            "product_id": product_id,
            "plant_count": plant_count,
            "predicted_kg": total_kg,
            "predicted_kg_per_plant": round(predicted_kg_per_plant, 3),
            "unit_price": unit_price,
            "predicted_value": total_value,
            "confidence_pct": round(confidence * 100, 1),
            "maturity_progress_pct": round(progress * 100, 1),
            "factors": {
                "temperature": round(temp_factor, 3),
                "humidity": round(hum_factor, 3),
                "light": round(light_factor, 3),
                "soil_moisture": round(moist_factor, 3),
                "health": round(health_factor, 3),
            },
            "deviation_from_previous_pct": round(deviation, 1),
            "estimated_harvest_date": self._estimate_harvest_date(
                days_since_planting, cycle_days),
        }

    def predict_zone(self, zone_id: str, lines: list[dict],
                     sensor_data: dict = None) -> dict:
        """Prévision agrégée pour une zone entière."""
        total_kg = 0
        total_value = 0
        line_predictions = []
        confidences = []

        for line in lines:
            pred = self.predict_line(
                line.get("line_id", ""),
                line.get("product_id", ""),
                line.get("plant_count", 0),
                line.get("days_since_planting", 30),
                line.get("cycle_days", 120),
                avg_temperature=sensor_data.get("temp_air", 20) if sensor_data else 20,
                avg_humidity=sensor_data.get("humidite", 60) if sensor_data else 60,
                avg_light_lux=sensor_data.get("lumiere", 25000) if sensor_data else 25000,
                soil_moisture_avg=sensor_data.get("humidite_sol", 45) if sensor_data else 45,
                health_index=line.get("health_index", 0.9),
                previous_yield_kg=line.get("previous_yield_kg"),
            )
            line_predictions.append(pred)
            total_kg += pred["predicted_kg"]
            total_value += pred["predicted_value"]
            confidences.append(pred["confidence_pct"])

        return {
            "zone_id": zone_id,
            "lines": len(lines),
            "predicted_total_kg": round(total_kg, 2),
            "predicted_total_value": round(total_value, 2),
            "avg_confidence_pct": round(np.mean(confidences), 1) if confidences else 0,
            "line_predictions": line_predictions,
            "estimated_harvest_dates": sorted(set(
                p["estimated_harvest_date"] for p in line_predictions
                if p["estimated_harvest_date"])),
        }

    def _base_yield(self, product_id: str) -> float:
        from core.harvest import YIELD_DEFAULTS
        return YIELD_DEFAULTS.get(product_id, {}).get("kg_per_plant", 1.0)

    def _estimate_harvest_date(self, days_since: int, cycle_days: int) -> str:
        remaining = max(1, cycle_days - days_since)
        return (date.today() + timedelta(days=remaining)).isoformat()

    def market_price(self, product_id: str) -> float:
        return PRIX_MARCHÉ.get(product_id, 3.0)

    def update_market_price(self, product_id: str, price: float):
        PRIX_MARCHÉ[product_id] = price
        log.info("Prix marché mis à jour", product=product_id, price=price)


# ── SortingGrade ─────────────────────────────────────────────

class SortingGrade:
    """Tri et calibrage de la production."""

    def __init__(self, batch_id: str):
        self.sorting_id = f"TRI-{uuid.uuid4().hex[:8].upper()}"
        self.batch_id = batch_id
        self.method = "manuel"
        self.date = date.today().isoformat()
        self.operator = ""
        self.entries: list[dict] = []
        self.summary: dict = {}

    def add_entry(self, weight_kg: float, calibre: str = "I",
                  defect: str = "", outcome: str = "commercialisable",
                  unit_weight_g: float = None,
                  length_mm: float = None, diameter_mm: float = None,
                  notes: str = ""):
        """Ajoute une entrée de tri."""
        entry = {
            "id": f"ENT-{uuid.uuid4().hex[:6].upper()}",
            "weight_kg": weight_kg,
            "calibre": calibre if calibre in CALIBRE_CLASSES else "I",
            "defect": defect,
            "outcome": outcome if outcome in SORTING_OUTCOMES else "commercialisable",
            "unit_weight_g": unit_weight_g,
            "length_mm": length_mm,
            "diameter_mm": diameter_mm,
            "notes": notes,
            "timestamp": datetime.now().isoformat(),
        }
        self.entries.append(entry)
        return entry

    def compute_summary(self) -> dict:
        """Calcule le résumé du tri."""
        total_kg = sum(e["weight_kg"] for e in self.entries)
        by_calibre = {}
        by_outcome = {}
        by_defect = {}
        total_value = 0

        for e in self.entries:
            cal = e["calibre"]
            by_calibre[cal] = by_calibre.get(cal, 0) + e["weight_kg"]
            out = e["outcome"]
            by_outcome[out] = by_outcome.get(out, 0) + e["weight_kg"]
            if e["defect"]:
                by_defect[e["defect"]] = by_defect.get(e["defect"], 0) + e["weight_kg"]

        self.summary = {
            "sorting_id": self.sorting_id,
            "batch_id": self.batch_id,
            "date": self.date,
            "method": self.method,
            "operator": self.operator,
            "total_kg": round(total_kg, 2),
            "entries_count": len(self.entries),
            "by_calibre": {k: round(v, 2) for k, v in sorted(by_calibre.items())},
            "by_outcome": {k: round(v, 2) for k, v in by_outcome.items()},
            "by_defect": {k: round(v, 2) for k, v in sorted(by_defect.items())},
            "commercialisable_pct": round(
                by_outcome.get("commercialisable", 0) / max(0.1, total_kg) * 100, 1),
            "yield_pct": round(
                (by_outcome.get("commercialisable", 0) + by_outcome.get("transformable", 0))
                / max(0.1, total_kg) * 100, 1),
        }
        return self.summary

    def to_dict(self) -> dict:
        if not self.summary:
            self.compute_summary()
        return {
            **self.summary,
            "entries": self.entries,
        }

    @staticmethod
    def classify_calibre(product_id: str, diameter_mm: float,
                         weight_g: float = None) -> str:
        """Classifie le calibre selon les normes du produit."""
        norms = CALIBRE_NORMS.get(product_id, {"I": (0, 999)})
        for calibre, (min_d, max_d) in sorted(norms.items(),
                                               key=lambda x: -x[1][0]):
            if min_d <= diameter_mm <= max_d:
                return calibre
        return "III"


# ── DistributionOrder ───────────────────────────────────────

class DistributionOrder:
    """Ordre de distribution d'un lot."""

    def __init__(self, batch_id: str, product: str = "",
                 quantity_kg: float = 0.0, destination: str = "",
                 client: str = "", client_ref: str = ""):
        self.order_id = f"DIST-{uuid.uuid4().hex[:8].upper()}"
        self.batch_id = batch_id
        self.product = product
        self.quantity_kg = quantity_kg
        self.destination = destination
        self.client = client
        self.client_ref = client_ref
        self.status = "préparé"
        self.delivery_date = date.today().isoformat()
        self.unit_price = 0.0
        self.total_value = 0.0
        self.shipping_cost = 0.0
        self.payment_method = "facture"
        self.certifications: list[str] = []
        self.notes = ""
        self.created = datetime.now().isoformat()
        self.updated = self.created

    def calculate_total(self) -> float:
        self.total_value = round(self.quantity_kg * self.unit_price
                                 + self.shipping_cost, 2)
        return self.total_value

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "batch_id": self.batch_id,
            "product": self.product,
            "quantity_kg": self.quantity_kg,
            "destination": self.destination,
            "client": self.client,
            "client_ref": self.client_ref,
            "status": self.status,
            "delivery_date": self.delivery_date,
            "unit_price": self.unit_price,
            "total_value": self.total_value or self.calculate_total(),
            "shipping_cost": self.shipping_cost,
            "payment_method": self.payment_method,
            "certifications": self.certifications,
            "notes": self.notes,
            "created": self.created,
            "updated": self.updated,
        }


# ── DeliveryNote ─────────────────────────────────────────────

class DeliveryNote:
    """Bon de livraison / facture."""

    def __init__(self, order_id: str, client: str = "",
                 client_address: str = ""):
        self.note_id = f"DN-{uuid.uuid4().hex[:8].upper()}"
        self.order_id = order_id
        self.client = client
        self.client_address = client_address
        self.date = date.today().isoformat()
        self.lines: list[dict] = []
        self.total_ht = 0.0
        self.tva_pct = 5.5
        self.total_ttc = 0.0
        self.paid = False
        self.paid_date = None
        self.notes = ""

    def add_line(self, product: str, quantity_kg: float,
                 unit_price: float, calibre: str = "",
                 lot: str = ""):
        total_ht = round(quantity_kg * unit_price, 2)
        self.lines.append({
            "product": product,
            "quantity_kg": quantity_kg,
            "unit_price": unit_price,
            "total_ht": total_ht,
            "calibre": calibre,
            "lot": lot,
        })
        self.total_ht += total_ht
        self.total_ttc = round(self.total_ht * (1 + self.tva_pct / 100), 2)

    def mark_paid(self, date: str = None):
        self.paid = True
        self.paid_date = date or date.today().isoformat()

    def to_dict(self) -> dict:
        return {
            "note_id": self.note_id,
            "order_id": self.order_id,
            "client": self.client,
            "client_address": self.client_address,
            "date": self.date,
            "lines": self.lines,
            "total_ht": round(self.total_ht, 2),
            "tva_pct": self.tva_pct,
            "total_ttc": round(self.total_ttc, 2),
            "paid": self.paid,
            "paid_date": self.paid_date,
            "notes": self.notes,
        }


# ── SalesJournal ─────────────────────────────────────────────

class SalesJournal:
    """Journal des ventes comptable."""

    def __init__(self):
        self.entries: list[dict] = []

    def record_sale(self, delivery_note: DeliveryNote) -> dict:
        entry = {
            "entry_id": f"ACC-{uuid.uuid4().hex[:8].upper()}",
            "note_id": delivery_note.note_id,
            "client": delivery_note.client,
            "date": delivery_note.date,
            "total_ht": delivery_note.total_ht,
            "tva": round(delivery_note.total_ht * delivery_note.tva_pct / 100, 2),
            "total_ttc": delivery_note.total_ttc,
            "paid": delivery_note.paid,
            "paid_date": delivery_note.paid_date,
            "lines_count": len(delivery_note.lines),
            "recorded": datetime.now().isoformat(),
        }
        self.entries.append(entry)
        return entry

    def summary(self) -> dict:
        total_ht = sum(e["total_ht"] for e in self.entries)
        total_paid = sum(e["total_ht"] for e in self.entries if e.get("paid"))
        return {
            "total_entries": len(self.entries),
            "total_ht": round(total_ht, 2),
            "total_paid": round(total_paid, 2),
            "total_outstanding": round(total_ht - total_paid, 2),
            "paid_count": sum(1 for e in self.entries if e.get("paid")),
            "unpaid_count": sum(1 for e in self.entries if not e.get("paid")),
            "last_entry": self.entries[-1] if self.entries else None,
        }


# ── LabelGenerator ───────────────────────────────────────────

class LabelGenerator:
    """Génération d'étiquettes avec QR et données de traçabilité."""

    def __init__(self):
        self.label_counter = 0

    def generate_qr_data(self, batch_id: str, product: str, zone: str,
                          weight_kg: float, unit_price: float,
                          harvest_date: str, quality: str,
                          calibre: str = "", certifications: list = None,
                          lot: str = "", producer: str = "PixelOS Farm") -> str:
        """Données complètes pour QR code traçabilité."""
        data = (
            f"PIXELOS-AGRI:v2|"
            f"BATCH:{batch_id}|"
            f"LOT:{lot or batch_id[:8]}|"
            f"PROD:{product}|"
            f"ZONE:{zone}|"
            f"POIDS:{weight_kg}kg|"
            f"PRIX:{unit_price}€/kg|"
            f"DATE:{harvest_date}|"
            f"QUAL:{quality}|"
            f"CAL:{calibre}|"
            f"CERT:{','.join(certifications or [])}|"
            f"PROD:{producer}|"
            f"TRACE:{uuid.uuid4().hex[:12].upper()}"
        )
        return data

    def generate_label_data(self, batch: dict, sorting: dict = None,
                             order: dict = None) -> dict:
        """Génère les données complètes d'étiquette."""
        label_id = f"LBL-{uuid.uuid4().hex[:10].upper()}"
        qr = self.generate_qr_data(
            batch.get("batch_id", ""),
            batch.get("product_id", batch.get("product", "")),
            batch.get("zone_id", batch.get("zone", "")),
            batch.get("weight_kg", 0),
            batch.get("unit_price", 0),
            batch.get("harvest_date", date.today().isoformat()),
            batch.get("quality_grade", batch.get("quality", "A")),
            calibre=sorting.get("calibre", "") if sorting else "",
            certifications=batch.get("certifications", []),
            lot=batch.get("batch_id", "")[:8],
        )
        return {
            "label_id": label_id,
            "qr_data": qr,
            "batch_id": batch.get("batch_id", ""),
            "product": batch.get("product_id", batch.get("product", "")),
            "zone": batch.get("zone_id", batch.get("zone", "")),
            "weight_kg": batch.get("weight_kg", 0),
            "unit_price": batch.get("unit_price", 0),
            "total": round(batch.get("weight_kg", 0) * batch.get("unit_price", 0), 2),
            "harvest_date": batch.get("harvest_date", ""),
            "quality": batch.get("quality_grade", batch.get("quality", "A")),
            "calibre": sorting.get("calibre", "") if sorting else "",
            "outcome": sorting.get("outcome", "") if sorting else "",
            "certifications": batch.get("certifications", []),
            "lot": batch.get("batch_id", "")[:8],
            "generated": datetime.now().isoformat(),
        }

    def format_zpl(self, label: dict, copies: int = 1) -> str:
        """Génère une étiquette ZPL (Zebra Programming Language)."""
        zpl = "^XA^CF0,25"
        zpl += f"^FO50,30^FD{label['product']}^FS"
        zpl += f"^FO50,65^FDZone: {label['zone']} | Lot: {label['lot']}^FS"
        zpl += f"^FO50,100^FDPoids: {label['weight_kg']}kg | Qual: {label['quality']}^FS"
        if label.get("calibre"):
            zpl += f"^FO50,135^FDCalibre: {label['calibre']}^FS"
        zpl += f"^FO50,170^FDDate: {label['harvest_date']}^FS"
        zpl += f"^FO50,205^FDPrix: {label['unit_price']}EUR/kg^FS"
        zpl += f"^FO50,240^FDTotal: {label['total']}EUR^FS"
        zpl += f"^FO400,30^BQN,2,8^FDQA,{label['qr_data']}^FS"
        zpl += f"^FO50,300^FD{label['label_id']}^FS"
        zpl += "^PQ" + str(copies) + "^XZ"
        return zpl


# ── AgriProduction ──────────────────────────────────────────

class AgriProduction:
    """Orchestrateur production agricole complet.

    Agrège HarvestManager + HarvestForecast + Sorting + Distribution + Comptabilité.
    """

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.forecast = HarvestForecast()
        self.labels = LabelGenerator()
        self.journal = SalesJournal()
        self._sortings_file = DATA_DIR / "sortings.json"
        self._orders_file = DATA_DIR / "orders.json"
        self._deliveries_file = DATA_DIR / "deliveries.json"
        self._journal_file = DATA_DIR / "journal.json"

    # ── Forecaster ──────────────────────────────────────

    def full_forecast(self, sensor_data: dict = None) -> dict:
        """Prévision complète pour toutes les zones."""
        from core.harvest import HarvestManager
        hm = HarvestManager()
        predictions = {}

        for zone_id in set(l.zone_id for l in hm.lines.values()):
            lines_in_zone = [l.snapshot() for l in hm.lines.values()
                             if l.zone_id == zone_id and l.status == "active"]
            if not lines_in_zone:
                continue

            from core.lifecycle import LifecycleManager
            lm_life = LifecycleManager()

            for line in lines_in_zone:
                line["days_since_planting"] = self._days_since(
                    line.get("planted_at"))
                line["cycle_days"] = self._get_cycle_days(
                    line.get("product_id"))
                line["health_index"] = self._estimate_health(
                    line["line_id"], lm_life, hm)
                line["previous_yield_kg"] = line.get("actual_yield_kg")

            pred = self.forecast.predict_zone(zone_id, lines_in_zone, sensor_data)
            predictions[zone_id] = pred

        total_kg = sum(p["predicted_total_kg"] for p in predictions.values())
        total_value = sum(p["predicted_total_value"] for p in predictions.values())
        avg_conf = np.mean([p["avg_confidence_pct"] for p in predictions.values()]) if predictions else 0

        return {
            "zones": predictions,
            "total_predicted_kg": round(total_kg, 2),
            "total_predicted_value": round(total_value, 2),
            "avg_confidence_pct": round(avg_conf, 1),
            "zone_count": len(predictions),
            "generated": datetime.now().isoformat(),
        }

    # ── Cycle récolte ──────────────────────────────────

    def harvest_readiness(self) -> list[dict]:
        """Liste les lignes prêtes à récolter avec détails."""
        from core.harvest import HarvestManager
        hm = HarvestManager()
        suggestions = hm.get_harvest_suggestions()

        for s in suggestions:
            line = hm.get_line(s["line_id"])
            if line:
                s["plant_count"] = line.get("plant_count", 0)
                s["zone_id"] = line.get("zone_id", "")
                s["planted_at"] = line.get("planted_at", "")
            forecast = self.forecast.predict_line(
                s["line_id"], s.get("product", ""),
                s.get("plant_count", 0),
                self._days_since(line.get("planted_at") if line else None),
                self._get_cycle_days(s.get("product", "")),
            )
            s["forecast"] = {
                "kg": forecast["predicted_kg"],
                "value": forecast["predicted_value"],
                "confidence": forecast["confidence_pct"],
            }
        return suggestions

    def execute_harvest(self, line_id: str, weight_kg: float,
                        unit_price: float = None, quality: str = "A",
                        harvest_date: str = None) -> dict:
        """Exécute une récolte complète avec tri initial."""
        from core.harvest import HarvestManager
        hm = HarvestManager()
        batch = hm.create_batch(line_id, weight_kg, unit_price, quality, harvest_date)
        if not batch:
            return {"status": "error", "message": "Récolte impossible"}
        batch["certifications"] = []
        return {"status": "ok", "batch": batch}

    # ── Tri ────────────────────────────────────────────

    def create_sorting(self, batch_id: str, method: str = "manuel",
                       entries: list[dict] = None) -> dict:
        """Crée un tri pour un lot récolté."""
        sg = SortingGrade(batch_id)
        sg.method = method
        if entries:
            for e in entries:
                sg.add_entry(**e)
        result = sg.to_dict()
        sortings = self._load_json(self._sortings_file)
        sortings.append(result)
        self._save_json(self._sortings_file, sortings)
        return result

    def get_sorting(self, sorting_id: str) -> Optional[dict]:
        for s in self._load_json(self._sortings_file):
            if s.get("sorting_id") == sorting_id:
                return s
        return None

    def list_sortings(self, batch_id: str = None) -> list[dict]:
        if batch_id:
            return [s for s in self._load_json(self._sortings_file)
                    if s.get("batch_id") == batch_id]
        return self._load_json(self._sortings_file)

    # ── Distribution ──────────────────────────────────

    def create_order(self, batch_id: str, product: str = "",
                     quantity_kg: float = 0.0, destination: str = "",
                     client: str = "", client_ref: str = "",
                     unit_price: float = None,
                     certifications: list = None) -> dict:
        """Crée un ordre de distribution."""
        if unit_price is None:
            unit_price = PRIX_MARCHÉ.get(product, 3.0)

        order = DistributionOrder(batch_id, product, quantity_kg,
                                   destination, client, client_ref)
        order.unit_price = unit_price
        order.calculate_total()
        if certifications:
            order.certifications = certifications

        data = order.to_dict()
        orders = self._load_json(self._orders_file)
        orders.append(data)
        self._save_json(self._orders_file, orders)

        # Mettre à jour le statut du batch dans HarvestManager
        try:
            from core.harvest import HarvestManager
            hm = HarvestManager()
            hm.update_batch(batch_id, status="distributed",
                            destination=destination)
        except Exception:
            pass

        log.info("Ordre distribution créé", order=order.order_id,
                 client=client, kg=quantity_kg)
        return data

    def update_order(self, order_id: str, **kwargs) -> Optional[dict]:
        orders = self._load_json(self._orders_file)
        for i, o in enumerate(orders):
            if o["order_id"] == order_id:
                for k, v in kwargs.items():
                    if k in o and v is not None:
                        o[k] = v
                o["updated"] = datetime.now().isoformat()
                if k == "status" and v in ("livré", "confirmé"):
                    try:
                        from core.harvest import HarvestManager
                        hm = HarvestManager()
                        hm.update_batch(o["batch_id"], status="sold")
                    except Exception:
                        pass
                orders[i] = o
                self._save_json(self._orders_file, orders)
                return o
        return None

    def list_orders(self, status: str = None, client: str = None) -> list[dict]:
        results = self._load_json(self._orders_file)
        if status:
            results = [o for o in results if o.get("status") == status]
        if client:
            results = [o for o in results if client.lower() in o.get("client", "").lower()]
        return sorted(results, key=lambda x: x.get("created", ""), reverse=True)

    def get_order(self, order_id: str) -> Optional[dict]:
        for o in self._load_json(self._orders_file):
            if o["order_id"] == order_id:
                return o
        return None

    # ── Livraison / Facture ───────────────────────────

    def create_delivery_note(self, order_id: str, client: str = "",
                              client_address: str = "",
                              tva_pct: float = 5.5) -> dict:
        """Crée un bon de livraison/facture pour une commande."""
        order = self.get_order(order_id)
        if not order:
            return {"status": "error", "message": "Commande introuvable"}

        dn = DeliveryNote(order_id, client or order.get("client", ""),
                          client_address)
        dn.tva_pct = tva_pct
        dn.add_line(order.get("product", ""), order.get("quantity_kg", 0),
                    order.get("unit_price", 0),
                    calibre="", lot=order.get("batch_id", "")[:8])

        result = dn.to_dict()
        deliveries = self._load_json(self._deliveries_file)
        deliveries.append(result)
        self._save_json(self._deliveries_file, deliveries)
        return result

    def list_delivery_notes(self, client: str = None,
                             paid: bool = None) -> list[dict]:
        results = self._load_json(self._deliveries_file)
        if client:
            results = [d for d in results if client.lower() in d.get("client", "").lower()]
        if paid is not None:
            results = [d for d in results if d.get("paid") == paid]
        return sorted(results, key=lambda x: x.get("date", ""), reverse=True)

    def mark_delivery_paid(self, note_id: str, paid_date: str = None) -> Optional[dict]:
        deliveries = self._load_json(self._deliveries_file)
        for i, d in enumerate(deliveries):
            if d["note_id"] == note_id:
                d["paid"] = True
                d["paid_date"] = paid_date or date.today().isoformat()
                deliveries[i] = d
                self._save_json(self._deliveries_file, deliveries)

                # Journal comptable
                dn = DeliveryNote(d.get("order_id", ""))
                dn.note_id = d["note_id"]
                dn.client = d.get("client", "")
                dn.date = d.get("date", "")
                dn.total_ht = d.get("total_ht", 0)
                dn.tva_pct = d.get("tva_pct", 5.5)
                dn.total_ttc = d.get("total_ttc", 0)
                dn.paid = True
                dn.paid_date = d.get("paid_date", "")
                self.journal.record_sale(dn)
                self._save_journal()

                return d
        return None

    # ── Journal de ventes ─────────────────────────────

    def _save_journal(self):
        self._save_json(self._journal_file, self.journal.entries)

    def _load_journal(self):
        self.journal.entries = self._load_json(self._journal_file)

    def sales_summary(self) -> dict:
        self._load_journal()
        s = self.journal.summary()
        s["orders"] = len(self.list_orders())
        s["delivery_notes"] = len(self.list_delivery_notes())
        return s

    # ── Statistiques ──────────────────────────────────

    def stats(self) -> dict:
        sortings = self._load_json(self._sortings_file)
        orders = self._load_json(self._orders_file)
        deliveries = self._load_json(self._deliveries_file)
        self._load_journal()

        return {
            "forecast": {
                "zones": len(self.full_forecast().get("zones", {})),
                "market_prices": len(PRIX_MARCHÉ),
            },
            "sortings": len(sortings),
            "orders": len(orders),
            "by_order_status": {
                s: sum(1 for o in orders if o.get("status") == s)
                for s in DISTRIBUTION_STATUSES
            },
            "delivery_notes": len(deliveries),
            "sales": self.journal.summary(),
            "labels_generated": self.labels.label_counter,
        }

    # ── Helpers ───────────────────────────────────────

    def _days_since(self, date_str: str) -> int:
        if not date_str:
            return 30
        try:
            d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            return (date.today() - d).days
        except Exception:
            return 30

    def _get_cycle_days(self, product_id: str) -> int:
        try:
            from core.lifecycle import LifecycleManager
            lm = LifecycleManager()
            p = lm.get_product(product_id)
            if p:
                return p.get("cycle_days", 120)
        except Exception:
            pass
        return 120

    def _estimate_health(self, line_id: str, lm_life=None,
                          hm=None) -> float:
        """Estime un indice de santé (0-1) basé sur les données disponibles."""
        health = 0.85  # valeur par défaut

        if lm_life and hm:
            try:
                line = hm.get_line(line_id)
                if line:
                    for pl in lm_life.list_plantations():
                        if pl.get("sub_zone_id") == line_id:
                            day = pl.get("day_of_cycle", 0)
                            health = max(0.3, min(1.0, 1 - abs(day - 60) * 0.005))
                            break
            except Exception:
                pass
        return round(health, 2)

    def _load_json(self, path: Path) -> list:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_json(self, path: Path, data: list):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
