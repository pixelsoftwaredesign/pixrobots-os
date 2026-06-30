"""PixelOS LifecycleManager - Cycle de vie des produits agricoles.

Architecture:
  Stage        →  Phase du cycle (germination, croissance, floraison, etc.)
  Product      →  Produit cultive (legume, fruit, arbre) avec stages
  Plantation   →  Association produit + zone + date plantation
  LifecycleManager → Orchestrateur cycles + generation auto de taches
"""

import json
import structlog
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Any

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "lifecycle"

PRODUCT_TYPES = ["legume", "fruit", "arbre_fruitier", "arbre_ornemental",
                 "aromatique", "fleur", "cereale", "autre"]
STAGE_NAMES = ["germination", "croissance", "floraison", "fructification",
               "recolte", "dormance", "taille", "traitement"]


# ── Stage ────────────────────────────────────────────────────

class Stage:
    """Phase du cycle de vie d'un produit."""

    def __init__(self, name: str, day_start: int = 0, day_end: int = 10,
                 temp_min: float = 10.0, temp_max: float = 35.0,
                 humidity_min: float = 40.0, humidity_max: float = 90.0,
                 light_hours: float = 12.0, light_lux_min: float = 0.0,
                 light_lux_max: float = 80000.0,
                 soil_moisture_min: float = 30.0,
                 soil_moisture_max: float = 80.0,
                 water_need: str = "medium",
                 tasks: list[str] = None):
        self.name = name
        self.day_start = day_start
        self.day_end = day_end
        self.temp_min = temp_min
        self.temp_max = temp_max
        self.humidity_min = humidity_min
        self.humidity_max = humidity_max
        self.light_hours = light_hours
        self.light_lux_min = light_lux_min
        self.light_lux_max = light_lux_max
        self.soil_moisture_min = soil_moisture_min
        self.soil_moisture_max = soil_moisture_max
        self.water_need = water_need
        self.tasks = tasks or []

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "day_start": self.day_start,
            "day_end": self.day_end,
            "temp_min": self.temp_min,
            "temp_max": self.temp_max,
            "humidity_min": self.humidity_min,
            "humidity_max": self.humidity_max,
            "light_hours": self.light_hours,
            "light_lux_min": self.light_lux_min,
            "light_lux_max": self.light_lux_max,
            "soil_moisture_min": self.soil_moisture_min,
            "soil_moisture_max": self.soil_moisture_max,
            "water_need": self.water_need,
            "tasks": self.tasks,
        }


# ── Product ──────────────────────────────────────────────────

class Product:
    """Produit agricole avec son cycle de vie complet."""

    def __init__(self, product_id: str, label: str = "",
                 type_: str = "legume", variete: str = "",
                 cycle_days: int = 90, family: str = "",
                 stages: list[Stage] = None):
        self.product_id = product_id
        self.label = label or product_id
        self.type = type_
        self.variete = variete
        self.cycle_days = cycle_days
        self.family = family
        self.stages = stages or []
        self.tags = []

    def get_stage_for_day(self, day: int) -> Stage | None:
        for s in self.stages:
            if s.day_start <= day <= s.day_end:
                return s
        return self.stages[-1] if self.stages else None

    def snapshot(self) -> dict:
        return {
            "product_id": self.product_id,
            "label": self.label,
            "type": self.type,
            "variete": self.variete,
            "cycle_days": self.cycle_days,
            "family": self.family,
            "stages": [s.snapshot() for s in self.stages],
            "tags": self.tags,
            "stage_count": len(self.stages),
        }


# ── Plantation ───────────────────────────────────────────────

class Plantation:
    """Association produit + espace/zone + date de plantation."""

    def __init__(self, plantation_id: str, product_id: str,
                 espace_id: str, sub_zone_id: str = "",
                 planted_at: str = None, quantity: int = 1,
                 label: str = ""):
        self.plantation_id = plantation_id
        self.product_id = product_id
        self.espace_id = espace_id
        self.sub_zone_id = sub_zone_id
        self.planted_at = planted_at or datetime.now().strftime("%Y-%m-%d")
        self.quantity = quantity
        self.label = label or ""
        self.status = "active"
        self.harvested_at = None
        self.notes = ""
        self.last_task_generation = None

    @property
    def day_of_cycle(self) -> int:
        if not self.planted_at:
            return 0
        try:
            start = date.fromisoformat(self.planted_at)
            return (date.today() - start).days
        except (ValueError, TypeError):
            return 0

    def snapshot(self) -> dict:
        return {
            "plantation_id": self.plantation_id,
            "product_id": self.product_id,
            "espace_id": self.espace_id,
            "sub_zone_id": self.sub_zone_id,
            "planted_at": self.planted_at,
            "quantity": self.quantity,
            "label": self.label,
            "status": self.status,
            "day_of_cycle": self.day_of_cycle,
            "harvested_at": self.harvested_at,
            "notes": self.notes,
        }


# ── Produits par defaut ──────────────────────────────────────

DEFAULT_PRODUCTS = [
    {
        "id": "tomate_coeur_de_boeuf",
        "label": "Tomate Coeur de Boeuf",
        "type": "legume", "variete": "Coeur de Boeuf",
        "cycle_days": 90, "family": "Solanacees",
        "stages": [
            {"name": "germination", "day_start": 0, "day_end": 10,
             "temp_min": 18, "temp_max": 28, "humidity_min": 70, "humidity_max": 90,
             "light_hours": 14, "light_lux_min": 3000, "light_lux_max": 15000,
             "soil_moisture_min": 60, "soil_moisture_max": 85,
             "water_need": "high",
             "tasks": ["Semer en godets sous abri chauffe",
                       "Maintenir substrat humide",
                       "Surveiller emergence J5-J10"]},
            {"name": "croissance", "day_start": 11, "day_end": 45,
             "temp_min": 16, "temp_max": 26, "humidity_min": 60, "humidity_max": 80,
             "light_hours": 16, "light_lux_min": 10000, "light_lux_max": 40000,
             "soil_moisture_min": 40, "soil_moisture_max": 70,
             "water_need": "medium",
             "tasks": ["Arroser regulierement sans exces",
                       "Apporter engrais NPK 10-10-10 toutes les 2 semaines",
                       "Tuteurer les plants",
                       "Surveiller mildiou et aleurodes"]},
            {"name": "floraison", "day_start": 46, "day_end": 65,
             "temp_min": 18, "temp_max": 30, "humidity_min": 50, "humidity_max": 70,
             "light_hours": 14, "light_lux_min": 15000, "light_lux_max": 50000,
             "soil_moisture_min": 35, "soil_moisture_max": 65,
             "water_need": "medium",
             "tasks": ["Tailler les gourmands",
                       "Apporter engrais potassique",
                       "Secouer les fleurs pour pollinisation",
                       "Surveiller botrytis"]},
            {"name": "fructification", "day_start": 66, "day_end": 85,
             "temp_min": 18, "temp_max": 30, "humidity_min": 50, "humidity_max": 75,
             "light_hours": 14, "light_lux_min": 15000, "light_lux_max": 45000,
             "soil_moisture_min": 45, "soil_moisture_max": 75,
             "water_need": "high",
             "tasks": ["Arrosage regulier (eviter alternance sec/humide)",
                       "Apporter engrais potassique",
                       "Soutenir les branches chargees de fruits",
                       "Surveiller oidium"]},
            {"name": "recolte", "day_start": 86, "day_end": 90,
             "temp_min": 16, "temp_max": 28, "humidity_min": 50, "humidity_max": 75,
             "light_hours": 12, "light_lux_min": 8000, "light_lux_max": 35000,
             "soil_moisture_min": 30, "soil_moisture_max": 60,
             "water_need": "low",
             "tasks": ["Recolter les fruits a maturite",
                       "Retirer les fruits abimes",
                       "Preparer les plants pour la rotation culturale"]},
        ],
    },
    {
        "id": "laitue_romaine",
        "label": "Laitue Romaine",
        "type": "legume", "variete": "Romaine",
        "cycle_days": 60, "family": "Asteracees",
        "stages": [
            {"name": "germination", "day_start": 0, "day_end": 8,
             "temp_min": 15, "temp_max": 22, "humidity_min": 70, "humidity_max": 90,
             "light_hours": 12, "light_lux_min": 2000, "light_lux_max": 10000,
             "soil_moisture_min": 60, "soil_moisture_max": 85,
             "water_need": "high",
             "tasks": ["Semer en terrine fine",
                       "Maintenir humidite constante",
                       "Ne pas enterrer les graines"]},
            {"name": "croissance", "day_start": 9, "day_end": 45,
             "temp_min": 12, "temp_max": 22, "humidity_min": 60, "humidity_max": 80,
             "light_hours": 12, "light_lux_min": 8000, "light_lux_max": 30000,
             "soil_moisture_min": 40, "soil_moisture_max": 70,
             "water_need": "medium",
             "tasks": ["Arroser au pied",
                       "Apporter compost mûr",
                       "Surveiller limaces",
                       "Eclaircir a 25cm"]},
            {"name": "recolte", "day_start": 46, "day_end": 60,
             "temp_min": 10, "temp_max": 22, "humidity_min": 50, "humidity_max": 80,
             "light_hours": 12, "light_lux_min": 5000, "light_lux_max": 25000,
             "soil_moisture_min": 30, "soil_moisture_max": 60,
             "water_need": "low",
             "tasks": ["Recolter les pommes fermes",
                       "Couper au couteau pres du collet",
                       "Stockage au frais"]},
        ],
    },
    {
        "id": "pommier_golden",
        "label": "Pommier Golden",
        "type": "arbre_fruitier", "variete": "Golden Delicious",
        "cycle_days": 365, "family": "Rosacees",
        "stages": [
            {"name": "dormance", "day_start": 0, "day_end": 60,
             "temp_min": -5, "temp_max": 10, "humidity_min": 40, "humidity_max": 80,
             "light_hours": 8, "light_lux_min": 0, "light_lux_max": 8000,
             "soil_moisture_min": 20, "soil_moisture_max": 50,
             "water_need": "low",
             "tasks": ["Taille d'hiver",
                        "Appliquer enduit de cicatrisation",
                        "Pulveriser bouillie bordelaise"]},
            {"name": "floraison", "day_start": 61, "day_end": 100,
             "temp_min": 8, "temp_max": 22, "humidity_min": 50, "humidity_max": 75,
             "light_hours": 12, "light_lux_min": 10000, "light_lux_max": 50000,
             "soil_moisture_min": 30, "soil_moisture_max": 60,
             "water_need": "medium",
             "tasks": ["Surveiller gelées tardives",
                        "Introduction ruches pour pollinisation",
                        "Traitement anti-tavelure"]},
            {"name": "croissance_fruits", "day_start": 101, "day_end": 200,
             "temp_min": 14, "temp_max": 28, "humidity_min": 50, "humidity_max": 75,
             "light_hours": 14, "light_lux_min": 15000, "light_lux_max": 60000,
             "soil_moisture_min": 35, "soil_moisture_max": 65,
             "water_need": "medium",
             "tasks": ["Eclaircir les fruits (1-2 par bouquet)",
                        "Arrosage en periode seche",
                        "Surveiller carpocapse"]},
            {"name": "maturation", "day_start": 201, "day_end": 280,
             "temp_min": 12, "temp_max": 28, "humidity_min": 50, "humidity_max": 75,
             "light_hours": 12, "light_lux_min": 10000, "light_lux_max": 50000,
             "soil_moisture_min": 25, "soil_moisture_max": 55,
             "water_need": "low",
             "tasks": ["Arreter l'arrosage 2 semaines avant recolte",
                        "Surveiller coloration des fruits",
                        "Preparer le materiel de recolte"]},
            {"name": "recolte", "day_start": 281, "day_end": 300,
             "temp_min": 8, "temp_max": 22, "humidity_min": 50, "humidity_max": 80,
             "light_hours": 10, "light_lux_min": 5000, "light_lux_max": 30000,
             "soil_moisture_min": 20, "soil_moisture_max": 45,
             "water_need": "low",
             "tasks": ["Recolter a maturite optimale",
                        "Trier et stocker en chambre froide"]},
            {"name": "post_recolte", "day_start": 301, "day_end": 365,
             "temp_min": -5, "temp_max": 10, "humidity_min": 40, "humidity_max": 80,
             "light_hours": 8, "light_lux_min": 0, "light_lux_max": 8000,
             "soil_moisture_min": 20, "soil_moisture_max": 45,
             "water_need": "low",
             "tasks": ["Apport de fumier composte",
                        "Taille de formation",
                        "Traitement d'automne"]},
        ],
    },
    {
        "id": "basilic_grand_vert",
        "label": "Basilic Grand Vert",
        "type": "aromatique", "variete": "Grand Vert",
        "cycle_days": 60, "family": "Lamiacees",
        "stages": [
            {"name": "germination", "day_start": 0, "day_end": 12,
             "temp_min": 18, "temp_max": 25, "humidity_min": 70, "humidity_max": 90,
             "light_hours": 14, "light_lux_min": 3000, "light_lux_max": 12000,
             "soil_moisture_min": 60, "soil_moisture_max": 85,
             "water_need": "high",
             "tasks": ["Semer en godets a 20°C min",
                        "Arroser en pluie fine",
                        "Ne pas laisser secher"]},
            {"name": "croissance", "day_start": 13, "day_end": 45,
             "temp_min": 16, "temp_max": 28, "humidity_min": 60, "humidity_max": 80,
             "light_hours": 14, "light_lux_min": 10000, "light_lux_max": 35000,
             "soil_moisture_min": 40, "soil_moisture_max": 70,
             "water_need": "medium",
             "tasks": ["Pincer les extremites pour favoriser ramification",
                        "Arroser regulierement",
                        "Apporter engrais azote faible dose"]},
            {"name": "recolte", "day_start": 46, "day_end": 60,
             "temp_min": 14, "temp_max": 28, "humidity_min": 50, "humidity_max": 75,
             "light_hours": 12, "light_lux_min": 5000, "light_lux_max": 30000,
             "soil_moisture_min": 30, "soil_moisture_max": 60,
             "water_need": "medium",
             "tasks": ["Recolter les feuilles avant floraison",
                        "Couper au-dessus d'un noeud",
                        "Conserver au frais ou secher"]},
        ],
    },
]


# ── LifecycleManager ─────────────────────────────────────────

class LifecycleManager:
    """Orchestrateur des cycles de vie et generation auto de taches."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.products: dict[str, Product] = {}
        self.plantations: dict[str, Plantation] = {}
        self._load_config()

    def _config_path(self):
        return DATA_DIR / "lifecycle.json"

    def _load_config(self):
        path = self._config_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self._init_products(cfg.get("products", DEFAULT_PRODUCTS))
                self._init_plantations(cfg.get("plantations", []))
                log.info("Configuration lifecycle chargee",
                         products=len(self.products),
                         plantations=len(self.plantations))
            except Exception as e:
                log.warning("Erreur chargement lifecycle", error=str(e))
                self._init_defaults()
        else:
            self._init_defaults()
        self._save_config()

    def _init_defaults(self):
        self._init_products(DEFAULT_PRODUCTS)
        self.plantations = {}

    def _init_products(self, configs: list[dict]):
        self.products = {}
        for c in configs:
            pid = c.get("product_id") or c.get("id")
            stages = []
            for s in c.get("stages", []):
                stage_kw = {k: v for k, v in s.items()
                           if k in ("name", "day_start", "day_end",
                                    "temp_min", "temp_max",
                                    "humidity_min", "humidity_max",
                                    "light_hours", "light_lux_min",
                                    "light_lux_max", "soil_moisture_min",
                                    "soil_moisture_max",
                                    "water_need", "tasks")}
                stages.append(Stage(**stage_kw))
            p = Product(pid, c.get("label", pid),
                       c.get("type", "legume"), c.get("variete", ""),
                       c.get("cycle_days", 90), c.get("family", ""),
                       stages)
            p.tags = c.get("tags", [])
            self.products[pid] = p

    def _init_plantations(self, configs: list[dict]):
        self.plantations = {}
        for c in configs:
            pid = c.get("plantation_id") or c.get("id")
            p = Plantation(pid, c["product_id"],
                          c["espace_id"], c.get("sub_zone_id", ""),
                          c.get("planted_at"), c.get("quantity", 1),
                          c.get("label", ""))
            p.status = c.get("status", "active")
            p.harvested_at = c.get("harvested_at")
            p.notes = c.get("notes", "")
            p.last_task_generation = c.get("last_task_generation")
            self.plantations[c["plantation_id"]] = p

    def _save_config(self):
        cfg = {
            "products": [{
                "product_id": p.product_id,
                "label": p.label,
                "type": p.type,
                "variete": p.variete,
                "cycle_days": p.cycle_days,
                "family": p.family,
                "tags": p.tags,
                "stages": [s.snapshot() for s in p.stages],
            } for p in self.products.values()],
            "plantations": [pl.snapshot() for pl in self.plantations.values()],
            "updated": datetime.now().isoformat(),
        }
        with open(self._config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

    # ── API Publique ────────────────────────────────────────

    def list_products(self) -> list[dict]:
        return [p.snapshot() for p in self.products.values()]

    def get_product(self, product_id: str) -> dict | None:
        p = self.products.get(product_id)
        return p.snapshot() if p else None

    def list_plantations(self) -> list[dict]:
        return [p.snapshot() for p in self.plantations.values()]

    def get_plantation(self, plantation_id: str) -> dict | None:
        p = self.plantations.get(plantation_id)
        return p.snapshot() if p else None

    def create_plantation(self, product_id: str, espace_id: str,
                          sub_zone_id: str = "", quantity: int = 1,
                          label: str = "", planted_at: str = None) -> dict:
        import uuid
        pl = Plantation(
            plantation_id=str(uuid.uuid4())[:8],
            product_id=product_id,
            espace_id=espace_id,
            sub_zone_id=sub_zone_id,
            planted_at=planted_at or datetime.now().strftime("%Y-%m-%d"),
            quantity=quantity,
            label=label,
        )
        self.plantations[pl.plantation_id] = pl
        self._save_config()

        # Generer tache initiale
        self._generate_tasks_for(pl)
        return pl.snapshot()

    def update_plantation(self, plantation_id: str, **kwargs) -> dict | None:
        pl = self.plantations.get(plantation_id)
        if not pl:
            return None
        for k in ("status", "quantity", "notes", "harvested_at"):
            if k in kwargs and kwargs[k] is not None:
                setattr(pl, k, kwargs[k])
        self._save_config()
        return pl.snapshot()

    def generate_tasks(self, plantation_id: str = None,
                       force: bool = False) -> list[dict]:
        from core.tasks import TaskManager
        tm = TaskManager()
        generated = []

        if plantation_id:
            pl = self.plantations.get(plantation_id)
            if pl:
                generated.extend(self._generate_tasks_for(pl, force))
        else:
            for pl in self.plantations.values():
                if pl.status == "active":
                    generated.extend(self._generate_tasks_for(pl, force))
        return generated

    def _generate_tasks_for(self, pl: Plantation,
                            force: bool = False) -> list[dict]:
        from core.tasks import TaskManager
        tm = TaskManager()
        product = self.products.get(pl.product_id)
        if not product:
            return []

        day = pl.day_of_cycle
        stage = product.get_stage_for_day(day)
        if not stage:
            return []

        generated = []
        today_str = date.today().isoformat()

        for task_desc in stage.tasks:
            title = f"[{stage.name}] {pl.label or product.label}: {task_desc[:60]}"
            desc = (f"Produit: {product.label}\n"
                    f"Stage: {stage.name} (J{day}/{product.cycle_days})\n"
                    f"Tache: {task_desc}\n"
                    f"Zone: {pl.espace_id}/{pl.sub_zone_id}")

            # Verifier si tache identique existe deja
            if not force:
                existing = tm.search(query=task_desc[:30],
                                     zone=pl.espace_id)
                todays = [t for t in existing
                          if t["status"] in ("todo", "in_progress")]
                if todays:
                    continue

            t = tm.create(
                title=title[:80],
                description=desc,
                categorie="plantation",
                priorite="medium",
                echeance=(date.today() + timedelta(days=3)).isoformat(),
                zone=pl.espace_id,
                plante=pl.product_id,
            )
            generated.append(t)

        pl.last_task_generation = today_str
        self._save_config()
        return generated

    def get_suggestions(self, espace_id: str = None) -> list[dict]:
        """Genere des suggestions intelligentes basees sur les cycles actifs
        et les ecarts environnementaux lus par les capteurs."""
        from core.tasks import TaskManager
        tm = TaskManager()
        suggestions = []

        # Charger les donnees capteurs si disponibles
        sensors_data = {}
        try:
            from core.spaces import SpaceManager
            sm = SpaceManager()
            sensors_data = sm.read_sensors()
        except Exception:
            pass

        for pl in self.plantations.values():
            if pl.status != "active":
                continue
            if espace_id and pl.espace_id != espace_id:
                continue

            product = self.products.get(pl.product_id)
            if not product:
                continue

            day = pl.day_of_cycle
            stage = product.get_stage_for_day(day)
            if not stage:
                continue

            jours_restants = max(0, stage.day_end - day)

            # Comparaison capteurs vs parametres ideaux du stage
            space_sensors = sensors_data.get(pl.espace_id, {})
            for sname, sval in space_sensors.items():
                sname_lower = sname.lower()

                # Temperature
                if "temp" in sname_lower:
                    if sval < stage.temp_min:
                        suggestions.append({
                            "type": "temp_too_low",
                            "product": product.label,
                            "plantation": pl.plantation_id,
                            "espace": pl.espace_id,
                            "current_stage": stage.name,
                            "sensor": sname, "value": sval,
                            "ideal_min": stage.temp_min,
                            "message": (f"{product.label} ({stage.name}): "
                                       f"Temperature trop basse {sval}C (ideal >{stage.temp_min}C) "
                                       f"- Activer chauffage"),
                            "priority": "high",
                        })
                    elif sval > stage.temp_max:
                        suggestions.append({
                            "type": "temp_too_high",
                            "product": product.label,
                            "plantation": pl.plantation_id,
                            "espace": pl.espace_id,
                            "sensor": sname, "value": sval,
                            "ideal_max": stage.temp_max,
                            "message": (f"{product.label} ({stage.name}): "
                                       f"Temperature trop haute {sval}C (ideal <{stage.temp_max}C)"
                                       f" - Activer ventilation"),
                            "priority": "high",
                        })

                # Humidite sol
                if "humidite_sol" in sname_lower or "hum_sol" in sname_lower:
                    if sval < stage.soil_moisture_min:
                        suggestions.append({
                            "type": "soil_dry",
                            "product": product.label,
                            "plantation": pl.plantation_id,
                            "espace": pl.espace_id,
                            "sensor": sname, "value": sval,
                            "ideal_min": stage.soil_moisture_min,
                            "message": (f"{product.label} ({stage.name}): "
                                       f"Sol trop sec {sval}% (ideal >{stage.soil_moisture_min}%)"
                                       f" - Declencher irrigation"),
                            "priority": "urgent" if sval < stage.soil_moisture_min - 15 else "high",
                        })
                    elif sval > stage.soil_moisture_max:
                        suggestions.append({
                            "type": "soil_wet",
                            "product": product.label,
                            "plantation": pl.plantation_id,
                            "espace": pl.espace_id,
                            "sensor": sname, "value": sval,
                            "ideal_max": stage.soil_moisture_max,
                            "message": (f"{product.label} ({stage.name}): "
                                       f"Sol trop humide {sval}% (ideal <{stage.soil_moisture_max}%)"
                                       f" - Reduire irrigation"),
                            "priority": "medium",
                        })

                # Luminosite
                if "lumiere" in sname_lower or "lum" in sname_lower:
                    if sval < stage.light_lux_min:
                        suggestions.append({
                            "type": "light_low",
                            "product": product.label,
                            "plantation": pl.plantation_id,
                            "espace": pl.espace_id,
                            "sensor": sname, "value": sval,
                            "ideal_min": stage.light_lux_min,
                            "message": (f"{product.label} ({stage.name}): "
                                       f"Lumiere insuffisante {sval}lux (ideal >{stage.light_lux_min}lux)"
                                       f" - Activer eclairage"),
                            "priority": "medium",
                        })
                    elif sval > stage.light_lux_max:
                        suggestions.append({
                            "type": "light_high",
                            "product": product.label,
                            "plantation": pl.plantation_id,
                            "espace": pl.espace_id,
                            "sensor": sname, "value": sval,
                            "ideal_max": stage.light_lux_max,
                            "message": (f"{product.label} ({stage.name}): "
                                       f"Lumiere excessive {sval}lux (ideal <{stage.light_lux_max}lux)"
                                       f" - Fermer ombrieres"),
                            "priority": "medium",
                        })

                # Humidite air
                if "humidite_air" in sname_lower or "hum_air" in sname_lower:
                    if sval < stage.humidity_min:
                        suggestions.append({
                            "type": "humidity_low",
                            "product": product.label,
                            "plantation": pl.plantation_id,
                            "espace": pl.espace_id,
                            "sensor": sname, "value": sval,
                            "ideal_min": stage.humidity_min,
                            "message": (f"{product.label} ({stage.name}): "
                                       f"Air trop sec {sval}% (ideal >{stage.humidity_min}%)"
                                       f" - Activer brumisateur"),
                            "priority": "medium",
                        })
                    elif sval > stage.humidity_max:
                        suggestions.append({
                            "type": "humidity_high",
                            "product": product.label,
                            "plantation": pl.plantation_id,
                            "espace": pl.espace_id,
                            "sensor": sname, "value": sval,
                            "ideal_max": stage.humidity_max,
                            "message": (f"{product.label} ({stage.name}): "
                                       f"Air trop humide {sval}% (ideal <{stage.humidity_max}%)"
                                       f" - Activer extraction"),
                            "priority": "medium",
                        })

            # Transition de stage
            if jours_restants <= 3 and stage.name not in ("recolte", "dormance"):
                suggestions.append({
                    "type": "transition_stage",
                    "product": product.label,
                    "plantation": pl.plantation_id,
                    "espace": pl.espace_id,
                    "current_stage": stage.name,
                    "message": (f"{product.label} en {stage.name} "
                                f"(J{day}) - {jours_restants} jours restants"),
                    "priority": "medium",
                })

            # Alerte si date recolte approche
            if stage.name == "recolte" and jours_restants <= 7:
                suggestions.append({
                    "type": "harvest_soon",
                    "product": product.label,
                    "plantation": pl.plantation_id,
                    "espace": pl.espace_id,
                    "message": f"{product.label} arrive a maturite ! Preparer la recolte",
                    "priority": "high",
                })

        return suggestions

        return suggestions

    def summary(self) -> dict:
        return {
            "products": len(self.products),
            "plantations": len(self.plantations),
            "active": sum(1 for p in self.plantations.values() if p.status == "active"),
            "harvested": sum(1 for p in self.plantations.values() if p.status == "harvested"),
            "by_type": {t: sum(1 for p in self.products.values() if p.type == t)
                       for t in PRODUCT_TYPES},
        }
