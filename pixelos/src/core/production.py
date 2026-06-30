"""production — Gestion de production agricole : préparation du sol et mise en place arbres.

Workflow complet:
  1. Planification production (saison, culture, parcelle)
  2. Préparation du sol (travail du sol, amendements, buttage, paillage)
  3. Mise en place (plantation arbres/plantes, semis, repiquage)
  4. Suivi cycle de vie (délégué à LifecycleManager)
  5. Récolte (délégué à AgriProduction)

Liens:
  - SpaceManager (espaces / sous-zones)
  - LifecycleManager (produits / plantations / stades)
  - TaskManager (génération automatique de tâches)
  - AgriProduction (récolte, tri, distribution)
"""

import json
import structlog
import uuid
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from typing import Optional


log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "production"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SOIL_PREP_FILE = DATA_DIR / "soil_preparations.json"
PLANTING_FILE = DATA_DIR / "plantings.json"
PRODUCTION_PLANS_FILE = DATA_DIR / "production_plans.json"

SOIL_PREP_TYPES = [
    "labour", "decompaction", "buttage", "planche", "billonnage",
    "pseudo-labour", "travail_minimal", "strip_till", "semi_direct",
]

AMENDMENT_TYPES = [
    "compost", "fumier", "engrais_vert", "NPK", "organique",
    "chaux", "soufre", "gypse", "biochar", "cendre", "guano",
]

SOIL_CONDITIONS = ["sec", "frais", "humide", "tres_humide", "detrempe"]
TEXTURES = ["argileuse", "limoneuse", "sableuse", "limono_argileuse",
            "argilo_limoneuse", "sablo_limoneuse", "caillouteuse"]

PLANTING_METHODS = ["trou", "butte", "tranchée", "conteneur", "motte", "racine_nue"]
STAKE_TYPES = ["tuteur_bois", "tuteur_metal", "haubanage", "aucun"]
MULCH_TYPES = ["paille", "BRF", "toile_geotextile", "plastique_noir",
               "copeaux", "écorce", "feuilles", "aucun"]
IRRIGATION_TYPES = ["goutte_a_goutte", "micro-aspersion", "aspersion",
                    "gravitaire", "aucun"]

STATUSES = ["planned", "in_progress", "completed", "cancelled"]


def _new_id(prefix: str = "PRD") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_iso() -> str:
    return date.today().isoformat()


# ── Persistance helpers ──────────────────────────────

def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Erreur chargement", path=str(path), error=str(e))
    return {}


def _save_json(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False),
                    encoding="utf-8")


# ── SoilPreparation ──────────────────────────────────

class SoilPreparation:
    """Préparation du sol pour une parcelle / sous-zone."""

    def __init__(self, data: dict):
        self.id = data.get("id", _new_id("SOL"))
        self.name = data.get("name", "")
        self.space_id = data.get("space_id", "")
        self.sub_zone_id = data.get("sub_zone_id", "")
        self.preparation_type = data.get("preparation_type", "labour")
        self.area_m2 = data.get("area_m2", 0)
        self.soil_condition = data.get("soil_condition", "")
        self.texture = data.get("texture", "")
        self.depth_cm = data.get("depth_cm", 0)
        self.amendments = data.get("amendments", [])
        self.activities = data.get("activities", [])
        self.status = data.get("status", "planned")
        self.notes = data.get("notes", "")
        self.assigned_to = data.get("assigned_to", "")
        self.tasks_generated = data.get("tasks_generated", False)
        self.start_date = data.get("start_date", "")
        self.completion_date = data.get("completion_date", "")
        self.created_at = data.get("created_at", _now_iso())
        self.updated_at = _now_iso()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "space_id": self.space_id,
            "sub_zone_id": self.sub_zone_id,
            "preparation_type": self.preparation_type,
            "area_m2": self.area_m2,
            "soil_condition": self.soil_condition,
            "texture": self.texture,
            "depth_cm": self.depth_cm,
            "amendments": self.amendments,
            "activities": self.activities,
            "status": self.status,
            "notes": self.notes,
            "assigned_to": self.assigned_to,
            "tasks_generated": self.tasks_generated,
            "start_date": self.start_date,
            "completion_date": self.completion_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def add_amendment(self, amendment_type: str, quantity_kg: float,
                      product_name: str = "", notes: str = ""):
        self.amendments.append({
            "type": amendment_type,
            "quantity_kg": quantity_kg,
            "product_name": product_name,
            "notes": notes,
            "applied_at": _now_iso(),
        })
        self.updated_at = _now_iso()

    def add_activity(self, activity_name: str, details: str = "",
                     duration_hours: float = 0):
        self.activities.append({
            "activity": activity_name,
            "details": details,
            "duration_hours": duration_hours,
            "performed_at": _now_iso(),
        })
        self.updated_at = _now_iso()


# ── TreePlanting ─────────────────────────────────────

class TreePlanting:
    """Mise en place d'arbres / plantes / cultures."""

    def __init__(self, data: dict):
        self.id = data.get("id", _new_id("PLT"))
        self.name = data.get("name", "")
        self.space_id = data.get("space_id", "")
        self.sub_zone_id = data.get("sub_zone_id", "")
        self.product_id = data.get("product_id", "")
        self.product_name = data.get("product_name", "")
        self.variety = data.get("variety", "")
        self.rootstock = data.get("rootstock", "")
        self.plant_count = data.get("plant_count", 0)
        self.spacing_m = data.get("spacing_m", 0.0)
        self.spacing_plant = data.get("spacing_plant", 0.0)
        self.row_orientation = data.get("row_orientation", "")
        self.planting_method = data.get("planting_method", "trou")
        self.hole_depth_cm = data.get("hole_depth_cm", 0)
        self.hole_width_cm = data.get("hole_width_cm", 0)
        self.stake_type = data.get("stake_type", "aucun")
        self.initial_watering_l = data.get("initial_watering_l", 0)
        self.mulch_type = data.get("mulch_type", "aucun")
        self.irrigation_type = data.get("irrigation_type", "aucun")
        self.fertilizer_initial = data.get("fertilizer_initial", "")
        self.fertilizer_quantity_kg = data.get("fertilizer_quantity_kg", 0)
        self.status = data.get("status", "planned")
        self.planting_date = data.get("planting_date", "")
        self.notes = data.get("notes", "")
        self.assigned_to = data.get("assigned_to", "")
        self.tasks_generated = data.get("tasks_generated", False)
        self.created_at = data.get("created_at", _now_iso())
        self.updated_at = _now_iso()
        self.lifecycle_plantation_id = data.get("lifecycle_plantation_id", "")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "space_id": self.space_id,
            "sub_zone_id": self.sub_zone_id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "variety": self.variety,
            "rootstock": self.rootstock,
            "plant_count": self.plant_count,
            "spacing_m": self.spacing_m,
            "spacing_plant": self.spacing_plant,
            "row_orientation": self.row_orientation,
            "planting_method": self.planting_method,
            "hole_depth_cm": self.hole_depth_cm,
            "hole_width_cm": self.hole_width_cm,
            "stake_type": self.stake_type,
            "initial_watering_l": self.initial_watering_l,
            "mulch_type": self.mulch_type,
            "irrigation_type": self.irrigation_type,
            "fertilizer_initial": self.fertilizer_initial,
            "fertilizer_quantity_kg": self.fertilizer_quantity_kg,
            "status": self.status,
            "planting_date": self.planting_date,
            "notes": self.notes,
            "assigned_to": self.assigned_to,
            "tasks_generated": self.tasks_generated,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "lifecycle_plantation_id": self.lifecycle_plantation_id,
        }


# ── ProductionPlan ───────────────────────────────────

class ProductionPlan:
    """Plan de production complet liant sol → plantation → cycle → récolte."""

    def __init__(self, data: dict):
        self.id = data.get("id", _new_id("PRD"))
        self.name = data.get("name", "")
        self.space_id = data.get("space_id", "")
        self.sub_zone_id = data.get("sub_zone_id", "")
        self.product_id = data.get("product_id", "")
        self.product_name = data.get("product_name", "")
        self.season = data.get("season", "")
        self.year = data.get("year", date.today().year)
        self.soil_prep_id = data.get("soil_prep_id", "")
        self.planting_id = data.get("planting_id", "")
        self.lifecycle_plantation_id = data.get("lifecycle_plantation_id", "")
        self.status = data.get("status", "draft")
        self.estimated_yield_kg = data.get("estimated_yield_kg", 0)
        self.estimated_value = data.get("estimated_value", 0.0)
        self.start_date = data.get("start_date", "")
        self.estimated_end_date = data.get("estimated_end_date", "")
        self.notes = data.get("notes", "")
        self.created_at = data.get("created_at", _now_iso())
        self.updated_at = _now_iso()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "space_id": self.space_id,
            "sub_zone_id": self.sub_zone_id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "season": self.season,
            "year": self.year,
            "soil_prep_id": self.soil_prep_id,
            "planting_id": self.planting_id,
            "lifecycle_plantation_id": self.lifecycle_plantation_id,
            "status": self.status,
            "estimated_yield_kg": self.estimated_yield_kg,
            "estimated_value": self.estimated_value,
            "start_date": self.start_date,
            "estimated_end_date": self.estimated_end_date,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ── ProductionManager ────────────────────────────────

class ProductionManager:
    """Orchestrateur de production agricole."""

    def __init__(self):
        self._soil_preps = {}
        self._plantings = {}
        self._plans = {}
        self._load_all()

    def _load_all(self):
        for sid, d in _load_json(SOIL_PREP_FILE).items():
            self._soil_preps[sid] = SoilPreparation(d)
        for pid, d in _load_json(PLANTING_FILE).items():
            self._plantings[pid] = TreePlanting(d)
        for pid, d in _load_json(PRODUCTION_PLANS_FILE).items():
            self._plans[pid] = ProductionPlan(d)

    def _save_soil_preps(self):
        _save_json(SOIL_PREP_FILE, {k: v.to_dict() for k, v in self._soil_preps.items()})

    def _save_plantings(self):
        _save_json(PLANTING_FILE, {k: v.to_dict() for k, v in self._plantings.items()})

    def _save_plans(self):
        _save_json(PRODUCTION_PLANS_FILE, {k: v.to_dict() for k, v in self._plans.items()})

    # ── Soil Preparation ─────────────────────────────

    def create_soil_prep(self, name: str, space_id: str = "",
                         sub_zone_id: str = "",
                         preparation_type: str = "labour",
                         area_m2: float = 0,
                         depth_cm: float = 0,
                         soil_condition: str = "",
                         texture: str = "",
                         notes: str = "",
                         assigned_to: str = "",
                         start_date: str = "") -> SoilPreparation:
        sp = SoilPreparation({
            "name": name,
            "space_id": space_id,
            "sub_zone_id": sub_zone_id,
            "preparation_type": preparation_type,
            "area_m2": area_m2,
            "depth_cm": depth_cm,
            "soil_condition": soil_condition,
            "texture": texture,
            "notes": notes,
            "assigned_to": assigned_to,
            "start_date": start_date or _today_iso(),
        })
        self._soil_preps[sp.id] = sp
        self._save_soil_preps()
        self._generate_soil_prep_tasks(sp.id)
        log.info("Préparation sol créée", id=sp.id, space=space_id, type=preparation_type)
        return sp

    def get_soil_prep(self, prep_id: str) -> Optional[SoilPreparation]:
        return self._soil_preps.get(prep_id)

    def list_soil_preps(self, space_id: str = None, status: str = None) -> list[dict]:
        results = [s.to_dict() for s in self._soil_preps.values()]
        if space_id:
            results = [r for r in results if r["space_id"] == space_id]
        if status:
            results = [r for r in results if r["status"] == status]
        return sorted(results, key=lambda r: r.get("start_date", ""), reverse=True)

    def update_soil_prep(self, prep_id: str, **kwargs) -> Optional[SoilPreparation]:
        sp = self._soil_preps.get(prep_id)
        if not sp:
            return None
        for k, v in kwargs.items():
            if hasattr(sp, k) and k not in ("id", "created_at"):
                setattr(sp, k, v)
        sp.updated_at = _now_iso()
        self._save_soil_preps()
        if kwargs.get("status") == "completed":
            self._on_soil_prep_completed(prep_id)
        return sp

    def delete_soil_prep(self, prep_id: str) -> bool:
        if prep_id in self._soil_preps:
            del self._soil_preps[prep_id]
            self._save_soil_preps()
            return True
        return False

    def add_soil_amendment(self, prep_id: str, amendment_type: str,
                           quantity_kg: float, product_name: str = "",
                           notes: str = "") -> Optional[SoilPreparation]:
        sp = self._soil_preps.get(prep_id)
        if not sp:
            return None
        sp.add_amendment(amendment_type, quantity_kg, product_name, notes)
        self._save_soil_preps()
        return sp

    def add_soil_activity(self, prep_id: str, activity_name: str,
                          details: str = "", duration_hours: float = 0) -> Optional[SoilPreparation]:
        sp = self._soil_preps.get(prep_id)
        if not sp:
            return None
        sp.add_activity(activity_name, details, duration_hours)
        self._save_soil_preps()
        return sp

    def _generate_soil_prep_tasks(self, prep_id: str):
        """Génère les tâches TaskManager pour une préparation de sol."""
        sp = self._soil_preps.get(prep_id)
        if not sp or sp.tasks_generated:
            return
        try:
            from core.tasks import TaskManager
            tm = TaskManager()
            tasks_data = [
                ("Préparation sol: " + sp.name,
                 f"Type: {sp.preparation_type}, Surface: {sp.area_m2}m2, "
                 f"Profondeur: {sp.depth_cm}cm, Zone: {sp.space_id}/{sp.sub_zone_id}",
                 "high", sp.start_date),
            ]
            if sp.amendments:
                amends_str = "; ".join(
                    f"{a['type']}: {a['quantity_kg']}kg" for a in sp.amendments)
                tasks_data.append(
                    ("Apport amendements: " + sp.name,
                     f"Amendements: {amends_str}", "medium", sp.start_date))
            for title, desc, prio, echeance in tasks_data:
                tm.create(
                    title=title, description=desc,
                    categorie="traitement", priorite=prio,
                    zone=sp.space_id, echeance=echeance,
                )
            sp.tasks_generated = True
            sp.updated_at = _now_iso()
            self._save_soil_preps()
            log.info("Tâches préparation sol générées", prep_id=prep_id, count=len(tasks_data))
        except Exception as e:
            log.warning("Erreur génération tâches sol", error=str(e))

    def _on_soil_prep_completed(self, prep_id: str):
        """Déclenché quand une préparation sol est terminée."""
        sp = self._soil_preps.get(prep_id)
        if not sp:
            return
        sp.completion_date = _today_iso()
        log.info("Préparation sol terminée", id=prep_id, space=sp.space_id)

    # ── Tree Planting ────────────────────────────────

    def create_planting(self, name: str, space_id: str = "",
                        sub_zone_id: str = "",
                        product_id: str = "",
                        product_name: str = "",
                        variety: str = "",
                        rootstock: str = "",
                        plant_count: int = 0,
                        spacing_m: float = 0,
                        spacing_plant: float = 0,
                        planting_method: str = "trou",
                        planting_date: str = "",
                        notes: str = "",
                        assigned_to: str = "",
                        **kwargs) -> TreePlanting:
        tp = TreePlanting({
            "name": name,
            "space_id": space_id,
            "sub_zone_id": sub_zone_id,
            "product_id": product_id,
            "product_name": product_name,
            "variety": variety,
            "rootstock": rootstock,
            "plant_count": plant_count,
            "spacing_m": spacing_m,
            "spacing_plant": spacing_plant,
            "planting_method": planting_method,
            "planting_date": planting_date or _today_iso(),
            "notes": notes,
            "assigned_to": assigned_to,
            **{k: v for k, v in kwargs.items() if hasattr(TreePlanting({}), k)},
        })
        self._plantings[tp.id] = tp
        self._save_plantings()
        self._generate_planting_tasks(tp.id)
        log.info("Plantation créée", id=tp.id, space=space_id, product=product_name)
        return tp

    def get_planting(self, planting_id: str) -> Optional[TreePlanting]:
        return self._plantings.get(planting_id)

    def list_plantings(self, space_id: str = None, status: str = None,
                       product_id: str = None) -> list[dict]:
        results = [p.to_dict() for p in self._plantings.values()]
        if space_id:
            results = [r for r in results if r["space_id"] == space_id]
        if status:
            results = [r for r in results if r["status"] == status]
        if product_id:
            results = [r for r in results if r["product_id"] == product_id]
        return sorted(results, key=lambda r: r.get("planting_date", ""), reverse=True)

    def update_planting(self, planting_id: str, **kwargs) -> Optional[TreePlanting]:
        tp = self._plantings.get(planting_id)
        if not tp:
            return None
        for k, v in kwargs.items():
            if hasattr(tp, k) and k not in ("id", "created_at"):
                setattr(tp, k, v)
        tp.updated_at = _now_iso()
        self._save_plantings()
        if kwargs.get("status") == "completed":
            self._on_planting_completed(planting_id)
        return tp

    def delete_planting(self, planting_id: str) -> bool:
        if planting_id in self._plantings:
            del self._plantings[planting_id]
            self._save_plantings()
            return True
        return False

    def _generate_planting_tasks(self, planting_id: str):
        """Génère les tâches pour une plantation."""
        tp = self._plantings.get(planting_id)
        if not tp or tp.tasks_generated:
            return
        try:
            from core.tasks import TaskManager
            tm = TaskManager()
            tasks_data = [
                ("Préparation trous plantation: " + tp.name,
                 f"{tp.plant_count} plants, méthode: {tp.planting_method}, "
                 f"trou: {tp.hole_depth_cm}×{tp.hole_width_cm}cm, "
                 f"espacement: {tp.spacing_m}m × {tp.spacing_plant}m",
                 "high", tp.planting_date),
            ]
            if tp.stake_type and tp.stake_type != "aucun":
                tasks_data.append(
                    ("Mise en place tuteurs: " + tp.name,
                     f"Type: {tp.stake_type}", "medium", tp.planting_date))
            if tp.irrigation_type and tp.irrigation_type != "aucun":
                tasks_data.append(
                    ("Installation irrigation: " + tp.name,
                     f"Type: {tp.irrigation_type}", "high", tp.planting_date))
            if tp.initial_watering_l > 0:
                tasks_data.append(
                    ("Arrosage initial: " + tp.name,
                     f"{tp.initial_watering_l}L/plant", "high", tp.planting_date))
            if tp.mulch_type and tp.mulch_type != "aucun":
                tasks_data.append(
                    ("Paillage: " + tp.name,
                     f"Type: {tp.mulch_type}", "medium", tp.planting_date))

            for title, desc, prio, echeance in tasks_data:
                tm.create(
                    title=title, description=desc,
                    categorie="plantation", priorite=prio,
                    zone=tp.space_id, echeance=echeance,
                    plante=tp.product_name,
                )
            tp.tasks_generated = True
            tp.updated_at = _now_iso()
            self._save_plantings()
            log.info("Tâches plantation générées", planting_id=planting_id, count=len(tasks_data))
        except Exception as e:
            log.warning("Erreur génération tâches plantation", error=str(e))

    def _on_planting_completed(self, planting_id: str):
        """Déclenché quand une plantation est terminée → crée Lifecycle plantation."""
        tp = self._plantings.get(planting_id)
        if not tp:
            return
        try:
            from core.lifecycle import LifecycleManager
            lm = LifecycleManager()
            if tp.product_id and tp.space_id:
                plantation = lm.create_plantation(
                    product_id=tp.product_id,
                    espace_id=tp.space_id,
                    sub_zone=tp.sub_zone_id,
                    quantity=tp.plant_count,
                    planted_at=tp.planting_date,
                    label=tp.name,
                )
                if plantation:
                    tp.lifecycle_plantation_id = plantation.get("id", "")
                    self._save_plantings()
                    log.info("Lifecycle plantation liée", planting=planting_id,
                             lifecycle_id=tp.lifecycle_plantation_id)

            # Assigner le produit à la sous-zone SpaceManager
            if tp.product_id and tp.space_id and tp.sub_zone_id:
                from core.spaces import SpaceManager
                sm = SpaceManager()
                sm.assign_product(tp.space_id, tp.sub_zone_id, tp.product_id,
                                  planted_at=tp.planting_date)
        except Exception as e:
            log.warning("Erreur liaison plantation→lifecycle", error=str(e))

    # ── Production Plans ─────────────────────────────

    def create_plan(self, name: str, space_id: str = "",
                    sub_zone_id: str = "", product_id: str = "",
                    product_name: str = "", season: str = "",
                    year: int = None,
                    estimated_yield_kg: float = 0,
                    start_date: str = "",
                    estimated_end_date: str = "",
                    notes: str = "") -> ProductionPlan:
        plan = ProductionPlan({
            "name": name,
            "space_id": space_id,
            "sub_zone_id": sub_zone_id,
            "product_id": product_id,
            "product_name": product_name,
            "season": season,
            "year": year or date.today().year,
            "estimated_yield_kg": estimated_yield_kg,
            "start_date": start_date or _today_iso(),
            "estimated_end_date": estimated_end_date,
            "notes": notes,
        })
        self._plans[plan.id] = plan
        self._save_plans()
        log.info("Plan de production créé", id=plan.id, season=season)
        return plan

    def get_plan(self, plan_id: str) -> Optional[ProductionPlan]:
        return self._plans.get(plan_id)

    def list_plans(self, space_id: str = None, status: str = None,
                   season: str = None, year: int = None) -> list[dict]:
        results = [p.to_dict() for p in self._plans.values()]
        if space_id:
            results = [r for r in results if r["space_id"] == space_id]
        if status:
            results = [r for r in results if r["status"] == status]
        if season:
            results = [r for r in results if r["season"] == season]
        if year:
            results = [r for r in results if r["year"] == year]
        return sorted(results, key=lambda r: r.get("start_date", ""), reverse=True)

    def update_plan(self, plan_id: str, **kwargs) -> Optional[ProductionPlan]:
        plan = self._plans.get(plan_id)
        if not plan:
            return None
        for k, v in kwargs.items():
            if hasattr(plan, k) and k not in ("id", "created_at"):
                setattr(plan, k, v)
        plan.updated_at = _now_iso()
        self._save_plans()
        return plan

    def delete_plan(self, plan_id: str) -> bool:
        if plan_id in self._plans:
            del self._plans[plan_id]
            self._save_plans()
            return True
        return False

    def link_soil_prep_to_plan(self, plan_id: str, soil_prep_id: str) -> bool:
        plan = self._plans.get(plan_id)
        sp = self._soil_preps.get(soil_prep_id)
        if not plan or not sp:
            return False
        plan.soil_prep_id = soil_prep_id
        plan.updated_at = _now_iso()
        self._save_plans()
        return True

    def link_planting_to_plan(self, plan_id: str, planting_id: str) -> bool:
        plan = self._plans.get(plan_id)
        tp = self._plantings.get(planting_id)
        if not plan or not tp:
            return False
        plan.planting_id = planting_id
        plan.updated_at = _now_iso()
        self._save_plans()
        return True

    # ── Dashboard / Stats ────────────────────────────

    def stats(self) -> dict:
        soil_preps = self.list_soil_preps()
        plantings = self.list_plantings()
        plans = self.list_plans()

        return {
            "total_soil_preps": len(soil_preps),
            "soil_preps_by_status": self._count_by(soil_preps, "status"),
            "soil_preps_by_type": self._count_by(soil_preps, "preparation_type"),
            "total_amendments": sum(len(s.get("amendments", [])) for s in soil_preps),
            "total_plantings": len(plantings),
            "plantings_by_status": self._count_by(plantings, "status"),
            "plantings_by_method": self._count_by(plantings, "planting_method"),
            "total_plants": sum(p.get("plant_count", 0) for p in plantings),
            "total_plans": len(plans),
            "plans_by_status": self._count_by(plans, "status"),
            "plans_by_season": self._count_by(plans, "season"),
            "active_plans": len([p for p in plans if p["status"] == "active"]),
            "estimated_total_yield_kg": sum(p.get("estimated_yield_kg", 0) for p in plans),
        }

    def _count_by(self, items: list[dict], key: str) -> dict:
        counts = {}
        for item in items:
            k = item.get(key, "unknown")
            counts[k] = counts.get(k, 0) + 1
        return counts

    def full_dashboard(self) -> dict:
        """Données complètes pour le dashboard web."""
        return {
            "stats": self.stats(),
            "soil_preparations": self.list_soil_preps(),
            "plantings": self.list_plantings(),
            "plans": self.list_plans(),
            "today": _today_iso(),
        }


# Singleton
production_manager = ProductionManager()
