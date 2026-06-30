# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""Ontologie Agricole PixelOS — Structure de données unifiée pour l'échange inter-systèmes.

Permet de comparer des données culturales entre n'importe quelle région du monde
via un vocabulaire contrôlé et des métadonnées standardisées.

Domaines:
  - Plantes : taxonomie, traits fonctionnels, stades phénologiques
  - Sols : types, textures, classification WRB/USDA
  - Climat : zones Köppen, saisons, normales
  - Intrants : fertilisants, pesticides, amendements
  - Pratiques : rotation, labour, irrigation, biologique
"""

import json
import structlog
from pathlib import Path
from datetime import datetime
from typing import Optional

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_DIR = ROOT / "data" / "ontology"


# ── Vocabulaires contrôlés ──────────────────────────────

PHENOLOGICAL_STAGES = {
    "BBCH": {
        "description": "Échelle BBCH uniforme pour stades phénologiques",
        "reference": "https://www.jki.bund.de/bbch",
        "stages": [
            {"code": "00", "name": "dormance", "description": "Graine sèche / organe de propagation"},
            {"code": "01", "name": "début_imbibition", "description": "Début de l'absorption d'eau"},
            {"code": "05", "name": "radicule", "description": "Radicule sortie de la graine"},
            {"code": "09", "name": "levée", "description": "Plantule émerge du sol"},
            {"code": "10", "name": "feuilles_cotylédons", "description": "Feuilles cotylédonaires étalées"},
            {"code": "11", "name": "1ère_feuille", "description": "Première feuille étalée"},
            {"code": "19", "name": "9_feuilles_ou_plus", "description": "9 feuilles ou plus étalées"},
            {"code": "30", "name": "montaison", "description": "Début élongation de la tige"},
            {"code": "39", "name": "fin_montaison", "description": "Taille finale atteinte"},
            {"code": "51", "name": "début_boutons", "description": "Apparition des boutons floraux"},
            {"code": "59", "name": "boutons_visibles", "description": "Boutons floraux clairement visibles"},
            {"code": "60", "name": "début_floraison", "description": "Premières fleurs ouvertes"},
            {"code": "65", "name": "pleine_floraison", "description": "≥50% des fleurs ouvertes"},
            {"code": "69", "name": "fin_floraison", "description": "Fleurs fanées, début nouaison"},
            {"code": "71", "name": "nouaison", "description": "Fruits/graines en formation"},
            {"code": "81", "name": "début_maturation", "description": "Début de coloration/maturation"},
            {"code": "85", "name": "maturation_avancée", "description": "Fruits mûrs à 50%"},
            {"code": "89", "name": "pleine_maturation", "description": "Fruits entièrement mûrs"},
            {"code": "92", "name": "sénescence", "description": "Début du jaunissement / sénescence"},
            {"code": "99", "name": "récolte", "description": "Produit récolté"},
        ]
    },
    "CUSTOM": {
        "description": "Stades personnalisés PixelOS",
        "stages": [
            {"code": "PS1", "name": "germination"},
            {"code": "PS2", "name": "levée"},
            {"code": "PS3", "name": "croissance_végétative"},
            {"code": "PS4", "name": "montaison"},
            {"code": "PS5", "name": "floraison"},
            {"code": "PS6", "name": "nouaison"},
            {"code": "PS7", "name": "maturation"},
            {"code": "PS8", "name": "sénescence"},
        ]
    },
}

KOPPEN_CLIMATES = {
    "Af": "Tropical_ humide", "Am": "Tropical_ mousson",
    "Aw": "Tropical_ sec_hiver", "BWh": "Aride_chaud",
    "BWk": "Aride_froid", "BSh": "Semi-aride_chaud",
    "BSk": "Semi-aride_froid", "Csa": "Méditerranéen_chaud",
    "Csb": "Méditerranéen_frais", "Cwa": "Subtropical_humide",
    "Cwb": "Subtropical_montagne", "Cfa": "Océanique_humide",
    "Cfb": "Océanique_tempéré", "Dfa": "Continental_chaud",
    "Dfb": "Continental_tempéré", "Dfc": "Continental_froid",
    "ET": "Polaire_toundra", "EF": "Polaire_glace",
}

SOIL_CLASSIFICATION = {
    "WRB": {
        "reference": "World Reference Base for Soil Resources",
        "groups": [
            "Histosol", "Anthrosol", "Technosol", "Cryosol",
            "Leptosol", "Vertisol", "Fluvisol", "Solonetz",
            "Solonchak", "Gleysol", "Andosol", "Podzol",
            "Plinthosol", "Ferralsol", "Planosol", "Stagnosol",
            "Cambisol", "Chernozem", "Kastanozem", "Phaeozem",
            "Umbrisol", "Albeluvisol", "Acrisol", "Lixisol",
            "Arenosol", "Calcisol", "Nitisol", "Regosol",
        ]
    },
    "USDA": {
        "reference": "USDA Soil Taxonomy",
        "orders": [
            "Alfisol", "Andisol", "Aridisol", "Entisol",
            "Gelisol", "Histosol", "Inceptisol", "Mollisol",
            "Oxisol", "Spodosol", "Ultisol", "Vertisol",
        ]
    }
}


# ── PlantTrait ───────────────────────────────────────────

class PlantTrait:
    """Trait fonctionnel d'une plante pour comparaison inter-systèmes."""

    STANDARD_TRAITS = {
        "life_form": ["annuelle", "bisannuelle", "vivace", "ligneuse"],
        "growth_habit": ["herbacé", "arbustif", "arborescent", "grimpant", " rampant"],
        "photosynthesis": ["C3", "C4", "CAM"],
        "root_system": ["fasciculé", "pivotant", "adventif", "tubéreux"],
        "pollination": ["anémophile", "entomophile", "autogame", "hydrophile"],
        "nitrogen_fixation": [True, False],
        "shade_tolerance": ["tolérant", "semi-tolérant", "intolérant"],
        "drought_tolerance": ["élevé", "moyen", "faible"],
        "salinity_tolerance": ["élevé", "moyen", "faible"],
        "water_logging_tolerance": ["élevé", "moyen", "faible"],
    }

    def __init__(self, species_id: str = ""):
        self.species_id = species_id
        self.scientific_name = ""
        self.common_name = ""
        self.family = ""
        self.genus = ""
        self.traits: dict = {}
        self.ecological_notes = ""
        self.origin_region = ""
        self.koppen_zones: list[str] = []
        self.min_temperature_c: float = None
        self.max_temperature_c: float = None
        self.min_precipitation_mm: float = None
        self.max_precipitation_mm: float = None
        self.optimal_ph_min: float = 5.5
        self.optimal_ph_max: float = 7.5
        self.gdd_base_c: float = 10.0
        self.gdd_required: int = None
        self.day_length_sensitivity: str = ""  # neutre, jour_court, jour_long

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    def match_climate(self, koppen_zone: str) -> dict:
        """Compatibilité d'une plante avec une zone climatique."""
        compatible = koppen_zone in self.koppen_zones
        return {
            "species": self.scientific_name,
            "zone": koppen_zone,
            "compatible": compatible,
            "zone_name": KOPPEN_CLIMATES.get(koppen_zone, koppen_zone),
        }

    def compare(self, other: "PlantTrait") -> dict:
        """Compare deux profils de plantes."""
        differences = {}
        for trait, values in self.STANDARD_TRAITS.items():
            v1 = self.traits.get(trait)
            v2 = other.traits.get(trait)
            if v1 != v2:
                differences[trait] = {"a": v1, "b": v2}
        return {
            "species_a": self.scientific_name,
            "species_b": other.scientific_name,
            "differences": differences,
            "similarity_pct": round(
                (1 - len(differences) / max(1, len(self.STANDARD_TRAITS))) * 100, 1),
        }


# ── ExchangeRecord ──────────────────────────────────────

class ExchangeRecord:
    """Enregistrement d'échange de données avec un autre système."""

    def __init__(self, remote_system: str = "", remote_url: str = "",
                 data_type: str = "growth_profile"):
        self.record_id = f"EXC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.remote_system = remote_system
        self.remote_url = remote_url
        self.data_type = data_type
        self.exchange_direction = "sent"  # sent, received
        self.data_format = "pixelos_ontology_v1"
        self.records_count = 0
        self.status = "pending"
        self.error = ""
        self.created = datetime.now().isoformat()
        self.completed = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# ── AgriculturalOntology ─────────────────────────────────

class AgriculturalOntology:
    """Ontologie agricole pour l'échange de données standardisé.

    Permet à PixelOS de publier et consommer des profils culturaux
    avec d'autres systèmes de recherche dans le monde.
    """

    def __init__(self):
        ONTOLOGY_DIR.mkdir(parents=True, exist_ok=True)
        self._traits_file = ONTOLOGY_DIR / "plant_traits.json"
        self._exchange_file = ONTOLOGY_DIR / "exchanges.json"

    # ── Vocabulaires ───────────────────────────────────

    def get_phenological_stages(self, system: str = "BBCH") -> list[dict]:
        return PHENOLOGICAL_STAGES.get(system, {}).get("stages", [])

    def get_koppen_zones(self) -> dict:
        return KOPPEN_CLIMATES

    def get_soil_classification(self, system: str = "WRB") -> dict:
        return SOIL_CLASSIFICATION.get(system, {})

    def get_standard_traits(self) -> dict:
        return PlantTrait.STANDARD_TRAITS

    # ── Profils plantes ───────────────────────────────

    def save_plant_trait(self, trait: PlantTrait) -> dict:
        traits = self._load_traits()
        data = trait.to_dict()
        traits[trait.species_id] = data
        self._save_traits(traits)
        return data

    def get_plant_trait(self, species_id: str) -> Optional[dict]:
        traits = self._load_traits()
        return traits.get(species_id)

    def search_plant_traits(self, query: str = "", trait_filter: dict = None) -> list[dict]:
        traits = self._load_traits()
        q = query.lower()
        results = []

        for sid, t in traits.items():
            if q and q not in t.get("scientific_name", "").lower() \
               and q not in t.get("common_name", "").lower() \
               and q not in t.get("family", "").lower():
                continue
            if trait_filter:
                match = True
                for k, v in trait_filter.items():
                    if t.get("traits", {}).get(k) != v:
                        match = False
                        break
                if not match:
                    continue
            results.append(t)

        return results

    def list_all_species(self) -> list[dict]:
        traits = self._load_traits()
        return [{"species_id": k, "scientific_name": v.get("scientific_name", ""),
                 "common_name": v.get("common_name", ""), "family": v.get("family", "")}
                for k, v in traits.items()]

    def compare_species(self, species_a: str, species_b: str) -> Optional[dict]:
        traits = self._load_traits()
        ta = traits.get(species_a)
        tb = traits.get(species_b)
        if not ta or not tb:
            return None
        pta = PlantTrait()
        ptb = PlantTrait()
        for k, v in ta.items():
            setattr(pta, k, v)
        for k, v in tb.items():
            setattr(ptb, k, v)
        return pta.compare(ptb)

    # ── Échanges inter-systèmes ───────────────────────

    def record_exchange(self, remote_system: str, remote_url: str,
                        data_type: str, direction: str = "sent",
                        records_count: int = 0) -> dict:
        exchanges = self._load_exchanges()
        rec = ExchangeRecord(remote_system, remote_url, data_type)
        rec.exchange_direction = direction
        rec.records_count = records_count
        rec.status = "completed"
        rec.completed = datetime.now().isoformat()
        data = rec.to_dict()
        exchanges.append(data)
        self._save_exchanges(exchanges)
        return data

    def export_plant_profile(self, species_id: str) -> Optional[dict]:
        """Export au format standardisé pour échange."""
        trait = self.get_plant_trait(species_id)
        if not trait:
            return None
        return {
            "format": "pixelos_ontology_v1",
            "exported_at": datetime.now().isoformat(),
            "species": {
                "id": species_id,
                "scientific_name": trait.get("scientific_name"),
                "common_name": trait.get("common_name"),
                "family": trait.get("family"),
                "genus": trait.get("genus"),
            },
            "traits": trait.get("traits", {}),
            "ecology": {
                "origin": trait.get("origin_region"),
                "koppen_zones": trait.get("koppen_zones"),
                "temp_range": [trait.get("min_temperature_c"),
                               trait.get("max_temperature_c")],
                "precip_range": [trait.get("min_precipitation_mm"),
                                 trait.get("max_precipitation_mm")],
                "ph_range": [trait.get("optimal_ph_min"),
                             trait.get("optimal_ph_max")],
                "gdd": {"base_c": trait.get("gdd_base_c"),
                        "required": trait.get("gdd_required")},
                "day_length": trait.get("day_length_sensitivity"),
            },
        }

    def import_plant_profile(self, profile: dict) -> dict:
        """Import d'un profil standardisé."""
        try:
            species = profile.get("species", {})
            trait = PlantTrait(species.get("id", f"EXT-{datetime.now().microsecond}"))
            trait.scientific_name = species.get("scientific_name", "")
            trait.common_name = species.get("common_name", "")
            trait.family = species.get("family", "")
            trait.genus = species.get("genus", "")
            trait.traits = profile.get("traits", {})
            eco = profile.get("ecology", {})
            trait.origin_region = eco.get("origin", "")
            trait.koppen_zones = eco.get("koppen_zones", [])
            tr = eco.get("temp_range", [])
            if len(tr) >= 2:
                trait.min_temperature_c, trait.max_temperature_c = tr
            pr = eco.get("precip_range", [])
            if len(pr) >= 2:
                trait.min_precipitation_mm, trait.max_precipitation_mm = pr
            phr = eco.get("ph_range", [])
            if len(phr) >= 2:
                trait.optimal_ph_min, trait.optimal_ph_max = phr
            gdd = eco.get("gdd", {})
            trait.gdd_base_c = gdd.get("base_c", 10)
            trait.gdd_required = gdd.get("required")
            trait.day_length_sensitivity = eco.get("day_length", "")

            return self.save_plant_trait(trait)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_exchanges(self, direction: str = None) -> list[dict]:
        exchanges = self._load_exchanges()
        if direction:
            return [e for e in exchanges if e.get("exchange_direction") == direction]
        return exchanges

    def stats(self) -> dict:
        traits = self._load_traits()
        exchanges = self._load_exchanges()
        return {
            "species_profiles": len(traits),
            "exchanges": len(exchanges),
            "sent": sum(1 for e in exchanges if e.get("exchange_direction") == "sent"),
            "received": sum(1 for e in exchanges if e.get("exchange_direction") == "received"),
            "koppen_zones_available": len(KOPPEN_CLIMATES),
            "soil_classifications": len(SOIL_CLASSIFICATION),
            "ontological_stages": sum(len(v.get("stages", [])) for v in PHENOLOGICAL_STAGES.values()),
        }

    # ── Persistance ───────────────────────────────────

    def _load_traits(self) -> dict:
        if self._traits_file.exists():
            with open(self._traits_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_traits(self, data: dict):
        with open(self._traits_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_exchanges(self) -> list:
        if self._exchange_file.exists():
            with open(self._exchange_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_exchanges(self, data: list):
        with open(self._exchange_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# Singleton
ontology = AgriculturalOntology()
