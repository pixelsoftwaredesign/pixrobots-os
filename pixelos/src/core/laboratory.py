# Pixel Software Design � Copyright 2026
"""Pôle Laboratoire PixelOS — Analyses sol, microbiome, microscopie, croissance, génétique.

Architecture:
  LabSample      → Échantillon physique avec chaîne de traçabilité
  SoilAnalysis   → Composition chimique du sol (NPK, pH, MO, CEC, oligo-éléments)
  Microbiome     → Typage bactérien, métagénomique, indices de diversité
  Microscopy     → Observations microscopiques avec images annotées
  GrowthTrack    → Suivi phénologique et morphologique (vision par ordinateur)
  GeneticProfile → Profil génétique, séquences, SNP, résistances
  LabReport      → Rapport de laboratoire consolidé
  LabManager     → Orchestrateur — ingestion, analyse, stockage, export
"""

import json
import uuid
import structlog
import numpy as np
from pathlib import Path
from datetime import datetime, date
from typing import Optional

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "lab"
LAKE_DIR = ROOT / "data" / "lake"


# ── Enums ──────────────────────────────────────────────────

SOIL_TYPES = [
    "sableuse", "limoneuse", "argileuse", "limon-argileuse",
    "sablo-limoneuse", "argilo-limoneuse", "tourbeuse", "calcaire",
]
SOIL_TEXTURES = ["tres_grossiere", "grossiere", "moyenne", "fine", "tres_fine"]
MICROBIOME_METHODS = ["culture_dependante", "metagenomique_16S", "metagenomique_WGS",
                      "qPCR", "Biolog_ECO", "PLFA"]
GENETIC_MARKER_TYPES = ["SNP", "INDEL", "CNV", "STR", "methylation"]
GROWTH_STAGES_LAB = [
    "germination", "levée", "croissance_végétative", "montaison",
    "floraison", "nouaison", "maturation", "sénescence",
]
OBSERVATION_TYPES = [
    "macroscopique", "microscopique", "spectrométrique",
    "moléculaire", "physiologique", "morphologique",
]
QUALITY_GRADES_LAB = ["A+", "A", "B", "C", "D"]


# ── LabSample ──────────────────────────────────────────────

class LabSample:
    """Échantillon de laboratoire avec traçabilité complète."""

    def __init__(self, sample_id: str = None, sample_type: str = "sol",
                 source: str = "", location: str = "",
                 collector: str = "", collection_date: str = None,
                 depth_cm: float = None, mass_g: float = None,
                 notes: str = ""):
        self.sample_id = sample_id or f"PXL-{uuid.uuid4().hex[:8].upper()}"
        self.sample_type = sample_type  # sol, eau, tissu, microbe, adn
        self.source = source
        self.location = location
        self.collector = collector
        self.collection_date = collection_date or date.today().isoformat()
        self.depth_cm = depth_cm
        self.mass_g = mass_g
        self.notes = notes
        self.status = "collected"  # collected, received, in_analysis, completed, archived
        self.barcode = ""
        self.images: list[str] = []
        self.results: dict = {}
        self.created = datetime.now().isoformat()
        self.updated = self.created

    def snapshot(self) -> dict:
        return {
            "sample_id": self.sample_id,
            "sample_type": self.sample_type,
            "source": self.source,
            "location": self.location,
            "collector": self.collector,
            "collection_date": self.collection_date,
            "depth_cm": self.depth_cm,
            "mass_g": self.mass_g,
            "status": self.status,
            "barcode": self.barcode,
            "notes": self.notes,
            "images": self.images,
            "results": self.results,
            "created": self.created,
            "updated": self.updated,
        }


# ── SoilAnalysis ────────────────────────────────────────────

class SoilAnalysis:
    """Analyse physico-chimique complète du sol."""

    def __init__(self, sample_id: str):
        self.sample_id = sample_id
        self.soil_type = ""
        self.texture = ""
        self.ph = 7.0
        self.cec_meq_100g: float = None
        self.matiere_organique_pct: float = None
        self.conductivite_us_cm: float = None
        self.carbonate_caco3_pct: float = None

        # Macro-éléments (mg/kg)
        self.n_total_pct: float = None     # Azote total
        self.n_no3_mg_kg: float = None     # Nitrates
        self.n_nh4_mg_kg: float = None     # Ammonium
        self.p_phosphore_mg_kg: float = None  # Phosphore Olsen
        self.k_potassium_mg_kg: float = None
        self.ca_calcium_mg_kg: float = None
        self.mg_magnesium_mg_kg: float = None
        self.s_soufre_mg_kg: float = None

        # Oligo-éléments (mg/kg)
        self.fe_fer_mg_kg: float = None
        self.mn_manganese_mg_kg: float = None
        self.zn_zinc_mg_kg: float = None
        self.cu_cuivre_mg_kg: float = None
        self.b_bore_mg_kg: float = None
        self.mo_molybdene_mg_kg: float = None
        self.cl_chlore_mg_kg: float = None
        self.si_silicium_mg_kg: float = None

        # Métaux lourds (mg/kg)
        self.pb_plomb_mg_kg: float = None
        self.cd_cadmium_mg_kg: float = None
        self.hg_mercure_mg_kg: float = None
        self.as_arsenic_mg_kg: float = None

        # Granulométrie
        self.sable_pct: float = None
        self.limon_pct: float = None
        self.argile_pct: float = None

        # Rapports
        self.c_n_ratio: float = None
        self.ca_mg_ratio: float = None
        self.k_mg_ratio: float = None

        self.analyst = ""
        self.analysis_date = None
        self.method_notes = ""
        self.quality_grade = "A"

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, sample_id: str, data: dict) -> "SoilAnalysis":
        a = cls(sample_id)
        for k, v in data.items():
            if hasattr(a, k):
                setattr(a, k, v)
        return a

    def fertility_index(self) -> dict:
        """Indice de fertilité global basé sur les normes agronomiques."""
        score = 0
        details = {}

        # pH (cible 6.0-7.0)
        if 6.0 <= self.ph <= 7.0:
            score += 15; details["pH"] = "optimal"
        elif 5.5 <= self.ph <= 7.5:
            score += 10; details["pH"] = "acceptable"
        else:
            score += 5; details["pH"] = "hors_optimum"

        # MO (>3% idéal)
        if self.matiere_organique_pct:
            if self.matiere_organique_pct >= 3:
                score += 15; details["MO"] = "élevé"
            elif self.matiere_organique_pct >= 1.5:
                score += 10; details["MO"] = "moyen"
            else:
                score += 5; details["MO"] = "faible"

        # NPK
        if self.n_total_pct:
            if self.n_total_pct >= 0.15: score += 10; details["N"] = "optimal"
            elif self.n_total_pct >= 0.08: score += 7; details["N"] = "moyen"
            else: score += 3; details["N"] = "faible"

        if self.p_phosphore_mg_kg:
            if self.p_phosphore_mg_kg >= 30: score += 10; details["P"] = "optimal"
            elif self.p_phosphore_mg_kg >= 15: score += 7; details["P"] = "moyen"
            else: score += 3; details["P"] = "faible"

        if self.k_potassium_mg_kg:
            if self.k_potassium_mg_kg >= 150: score += 10; details["K"] = "optimal"
            elif self.k_potassium_mg_kg >= 80: score += 7; details["K"] = "moyen"
            else: score += 3; details["K"] = "faible"

        # CEC (>15 idéal)
        if self.cec_meq_100g:
            if self.cec_meq_100g >= 15: score += 10; details["CEC"] = "élevé"
            elif self.cec_meq_100g >= 8: score += 7; details["CEC"] = "moyen"
            else: score += 3; details["CEC"] = "faible"

        return {
            "score": score,
            "max_score": 70,
            "index": round(score / 70 * 100, 1),
            "details": details,
            "interpretation": "très_fertile" if score >= 50 else
                             "fertile" if score >= 35 else
                             "modérément_fertile" if score >= 20 else
                             "peu_fertile",
        }

    def recommendations(self) -> list[dict]:
        """Recommandations agronomiques basées sur l'analyse."""
        recs = []

        if self.ph and self.ph < 5.5:
            recs.append({
                "type": "amendement", "priority": "haute",
                "message": f"Chauler: pH {self.ph} trop acide. Apport 2-4 t/ha CaCO3",
            })
        elif self.ph and self.ph > 7.5:
            recs.append({
                "type": "amendement", "priority": "moyenne",
                "message": f"Soufrer: pH {self.ph} trop alcalin. Apport soufre élémentaire",
            })

        if self.matiere_organique_pct and self.matiere_organique_pct < 1.5:
            recs.append({
                "type": "matiere_organique", "priority": "haute",
                "message": f"MO={self.matiere_organique_pct}% faible. Apport compost 20-30 t/ha",
            })

        if self.n_total_pct and self.n_total_pct < 0.08:
            recs.append({
                "type": "fertilisation", "priority": "moyenne",
                "message": f"N={self.n_total_pct}% bas. Apport engrais azoté 80-120 kgN/ha",
            })

        if self.p_phosphore_mg_kg and self.p_phosphore_mg_kg < 15:
            recs.append({
                "type": "fertilisation", "priority": "moyenne",
                "message": f"P={self.p_phosphore_mg_kg} mg/kg bas. Apport superphosphate 40-60 kgP2O5/ha",
            })

        if self.k_potassium_mg_kg and self.k_potassium_mg_kg < 80:
            recs.append({
                "type": "fertilisation", "priority": "moyenne",
                "message": f"K={self.k_potassium_mg_kg} mg/kg bas. Apport potasse 60-80 kgK2O/ha",
            })

        return recs


# ── Microbiome ──────────────────────────────────────────────

class Microbiome:
    """Analyse du microbiote du sol/plante."""

    def __init__(self, sample_id: str):
        self.sample_id = sample_id
        self.method = "metagenomique_16S"
        self.total_bacteria_cfu_g: float = None
        self.total_fungi_cfu_g: float = None
        self.total_actinomycetes_cfu_g: float = None
        self.bacterial_diversity_shannon: float = None
        self.bacterial_richness_chao1: float = None
        self.fungal_diversity_shannon: float = None
        self.fungal_richness_chao1: float = None

        # Phyla distribution (pourcentage)
        self.phylum_abundance: dict[str, float] = {}  # ex: {"Proteobacteria": 35.2, "Actinobacteria": 20.1}

        # Groupes fonctionnels
        self.nitrogen_fixers_cfu_g: float = None
        self.phosphate_solubilizers_cfu_g: float = None
        self.cellulose_decomposers_cfu_g: float = None
        self.pathogens_detected: list[dict] = []  # [{"name": "Fusarium", "abundance": 0.5, "risk": "low"}]

        # Métagénomique (16S/WGS)
        self.otu_count: int = None
        self.asv_count: int = None
        self.dominant_taxa: list[dict] = []
        self.functional_genes: dict[str, float] = {}
        self.metabolic_pathways: dict[str, float] = {}

        self.analyst = ""
        self.analysis_date = None
        self.sequence_file: str = ""
        self.quality_grade = "A"

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    def diversity_index(self) -> dict:
        """Indice de santé microbienne."""
        score = 0
        if self.bacterial_diversity_shannon:
            if self.bacterial_diversity_shannon >= 5: score += 25
            elif self.bacterial_diversity_shannon >= 3.5: score += 18
            elif self.bacterial_diversity_shannon >= 2: score += 10
            else: score += 5

        if self.total_bacteria_cfu_g:
            if self.total_bacteria_cfu_g >= 1e7: score += 15
            elif self.total_bacteria_cfu_g >= 1e6: score += 10
            else: score += 5

        ratio = (self.total_fungi_cfu_g or 0) / max(1, self.total_bacteria_cfu_g or 1)
        if ratio < 0.1: score += 10
        elif ratio < 0.3: score += 7
        else: score += 3

        if self.nitrogen_fixers_cfu_g and self.nitrogen_fixers_cfu_g >= 1e4: score += 10
        if self.pathogens_detected:
            high_risk = sum(1 for p in self.pathogens_detected if p.get("risk") == "high")
            score -= high_risk * 8

        return {
            "score": max(0, score),
            "max_score": 60,
            "index": round(max(0, score) / 60 * 100, 1),
            "interpretation": "excellente" if score >= 45 else
                             "bonne" if score >= 30 else
                             "moyenne" if score >= 15 else
                             "dégradée",
        }


# ── Microscopy ──────────────────────────────────────────────

class Microscopy:
    """Observation microscopique avec annotations et mesures."""

    def __init__(self, sample_id: str, observation_id: str = None):
        self.observation_id = observation_id or f"OBS-{uuid.uuid4().hex[:8].upper()}"
        self.sample_id = sample_id
        self.observation_type = "microscopique"
        self.microscope = ""  # modèle
        self.magnification = 400  # 100x, 400x, 1000x
        self.stain = ""  # coloration (Gram, lactophenol, etc.)
        self.mounting = ""  # montage (frais, coloration, etc.)
        self.images: list[str] = []  # chemins fichiers image
        self.annotations: list[dict] = []
        self.structures_observed: list[str] = []
        self.measurements: dict[str, float] = {}
        self.notes = ""
        self.observer = ""
        self.observation_date = date.today().isoformat()

    def add_annotation(self, label: str, x: int, y: int,
                       width: int = 0, height: int = 0,
                       measurement_um: float = None,
                       classification: str = ""):
        self.annotations.append({
            "id": f"ANN-{uuid.uuid4().hex[:8]}",
            "label": label,
            "x": x, "y": y, "width": width, "height": height,
            "measurement_um": measurement_um,
            "classification": classification,
            "created": datetime.now().isoformat(),
        })

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# ── GrowthTrack ─────────────────────────────────────────────

class GrowthTrack:
    """Suivi de croissance phénologique et morphologique."""

    def __init__(self, plant_id: str, product_id: str = ""):
        self.plant_id = plant_id
        self.product_id = product_id
        self.espace_id = ""
        self.sub_zone_id = ""
        self.tracking: list[dict] = []
        self.images: list[str] = []
        self.root_images: list[str] = []
        self.measurements_history: list[dict] = []

    def record_observation(self, stage: str, height_cm: float = None,
                           leaf_count: int = None, leaf_area_cm2: float = None,
                           stem_diameter_mm: float = None,
                           root_length_cm: float = None,
                           branching_count: int = None,
                           chlorophyll_spad: float = None,
                           ndvi: float = None,
                           image_path: str = "",
                           notes: str = ""):
        obs = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "height_cm": height_cm,
            "leaf_count": leaf_count,
            "leaf_area_cm2": leaf_area_cm2,
            "stem_diameter_mm": stem_diameter_mm,
            "root_length_cm": root_length_cm,
            "branching_count": branching_count,
            "chlorophyll_spad": chlorophyll_spad,
            "ndvi": ndvi,
            "image_path": image_path,
            "notes": notes,
            "day_of_growth": len(self.tracking) + 1,
        }
        self.tracking.append(obs)
        return obs

    def growth_rate(self) -> dict:
        """Calcule le taux de croissance moyen."""
        if len(self.tracking) < 2:
            return {"rate_cm_per_day": 0, "period_days": 0}
        heights = [t.get("height_cm") for t in self.tracking if t.get("height_cm")]
        if len(heights) < 2:
            return {"rate_cm_per_day": 0, "period_days": 0}
        total_growth = heights[-1] - heights[0]
        days = len(self.tracking)
        return {
            "rate_cm_per_day": round(total_growth / max(1, days), 2),
            "total_growth_cm": round(total_growth, 1),
            "period_days": days,
            "current_height_cm": heights[-1],
        }

    def summary(self) -> dict:
        if not self.tracking:
            return {"plant_id": self.plant_id, "status": "aucune_donnée"}
        latest = self.tracking[-1]
        return {
            "plant_id": self.plant_id,
            "product_id": self.product_id,
            "days_tracked": len(self.tracking),
            "current_stage": latest.get("stage", ""),
            "current_height_cm": latest.get("height_cm"),
            "leaf_count": latest.get("leaf_count"),
            "growth_rate": self.growth_rate(),
            "last_observed": latest["timestamp"],
        }


# ── GeneticProfile ──────────────────────────────────────────

class GeneticProfile:
    """Profil génétique d'une plante/variété."""

    def __init__(self, profile_id: str = None, plant_id: str = "",
                 species: str = "", variety: str = ""):
        self.profile_id = profile_id or f"GEN-{uuid.uuid4().hex[:8].upper()}"
        self.plant_id = plant_id
        self.species = species
        self.variety = variety
        self.genome_size_mb: float = None
        self.chromosome_count: int = None
        self.ploidy: str = ""  # diploïde, tétraploïde, etc.

        # Marqueurs génétiques
        self.snp_markers: list[dict] = []
        self.genes_of_interest: list[dict] = []
        self.resistance_genes: list[str] = []

        # Séquences
        self.sequences: dict[str, str] = {}  # gene_name -> sequence
        self.sequence_files: list[str] = []  # FASTA/GenBank paths

        # Alignements
        self.alignment_data: dict = {}
        self.phylogenetic_notes = ""

        # Expression
        self.expression_data: dict[str, float] = {}  # gene -> expression level

        self.analyst = ""
        self.analysis_date = None
        self.quality_grade = "A"

    def add_snp(self, gene: str, position: int, ref: str, alt: str,
                 effect: str = "", impact: str = ""):
        self.snp_markers.append({
            "gene": gene, "position": position,
            "reference": ref, "alternative": alt,
            "effect": effect, "impact": impact,
        })

    def add_gene(self, name: str, function: str,
                 expression_level: float = None,
                 notes: str = ""):
        self.genes_of_interest.append({
            "name": name, "function": function,
            "expression_level": expression_level,
            "notes": notes,
        })

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# ── LabManager ──────────────────────────────────────────────

class LabManager:
    """Gestionnaire du pôle laboratoire PixelOS."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (LAKE_DIR / "raw" / "lab").mkdir(parents=True, exist_ok=True)
        self._samples_file = DATA_DIR / "samples.json"
        self._analyses_file = DATA_DIR / "analyses.json"
        self._microbiomes_file = DATA_DIR / "microbiomes.json"
        self._microscopies_file = DATA_DIR / "microscopies.json"
        self._growth_file = DATA_DIR / "growth.json"
        self._genetics_file = DATA_DIR / "genetics.json"

    # ── Persistance ──────────────────────────────────────

    def _load_json(self, path: Path) -> list:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_json(self, path: Path, data: list):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_dict(self, path: Path) -> dict:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_dict(self, path: Path, data: dict):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ── Échantillons ─────────────────────────────────────

    def create_sample(self, sample_type: str = "sol", source: str = "",
                      location: str = "", collector: str = "",
                      depth_cm: float = None, mass_g: float = None,
                      notes: str = "") -> dict:
        samples = self._load_json(self._samples_file)
        s = LabSample(sample_type=sample_type, source=source,
                      location=location, collector=collector,
                      depth_cm=depth_cm, mass_g=mass_g, notes=notes)
        data = s.snapshot()
        samples.append(data)
        self._save_json(self._samples_file, samples)
        log.info("Échantillon créé", sample_id=s.sample_id, type=sample_type)
        return data

    def get_sample(self, sample_id: str) -> Optional[dict]:
        for s in self._load_json(self._samples_file):
            if s["sample_id"] == sample_id:
                return s
        return None

    def list_samples(self, sample_type: str = None, status: str = None,
                     location: str = None) -> list[dict]:
        results = []
        for s in self._load_json(self._samples_file):
            if sample_type and s["sample_type"] != sample_type:
                continue
            if status and s["status"] != status:
                continue
            if location and location.lower() not in s.get("location", "").lower():
                continue
            results.append(s)
        return results

    def update_sample(self, sample_id: str, **kwargs) -> Optional[dict]:
        samples = self._load_json(self._samples_file)
        for i, s in enumerate(samples):
            if s["sample_id"] == sample_id:
                for k, v in kwargs.items():
                    if k in s and v is not None:
                        s[k] = v
                s["updated"] = datetime.now().isoformat()
                samples[i] = s
                self._save_json(self._samples_file, samples)
                return s
        return None

    def delete_sample(self, sample_id: str) -> bool:
        samples = self._load_json(self._samples_file)
        n = len(samples)
        samples = [s for s in samples if s["sample_id"] != sample_id]
        if len(samples) == n:
            return False
        self._save_json(self._samples_file, samples)
        return True

    # ── Analyses sol ────────────────────────────────────

    def create_soil_analysis(self, sample_id: str, data: dict) -> dict:
        analyses = self._load_json(self._analyses_file)
        existing = [a for a in analyses if a.get("sample_id") == sample_id]
        if existing:
            analyses = [a for a in analyses if a["sample_id"] != sample_id]
        analysis = SoilAnalysis(sample_id)
        for k, v in data.items():
            if hasattr(analysis, k):
                setattr(analysis, k, v)
        analysis.analysis_date = data.get("analysis_date", date.today().isoformat())
        result = analysis.to_dict()
        result["fertility_index"] = analysis.fertility_index()
        result["recommendations"] = analysis.recommendations()
        analyses.append(result)
        self._save_json(self._analyses_file, analyses)

        self.update_sample(sample_id, status="completed")
        log.info("Analyse sol enregistrée", sample_id=sample_id)

        try:
            from core.bgdatasys import bgdatasys
            bgdatasys.log_ml_event("soil_analysis", {
                "sample_id": sample_id,
                "ph": data.get("ph"), "mo": data.get("matiere_organique_pct"),
                "fertility": result["fertility_index"],
            })
        except Exception:
            pass

        return result

    def get_soil_analysis(self, sample_id: str) -> Optional[dict]:
        for a in self._load_json(self._analyses_file):
            if a["sample_id"] == sample_id:
                return a
        return None

    def list_soil_analyses(self, min_fertility: float = None,
                           max_fertility: float = None) -> list[dict]:
        results = []
        for a in self._load_json(self._analyses_file):
            fi = a.get("fertility_index", {}).get("index", 0)
            if min_fertility is not None and fi < min_fertility:
                continue
            if max_fertility is not None and fi > max_fertility:
                continue
            results.append(a)
        return results

    # ── Microbiome ──────────────────────────────────────

    def create_microbiome(self, sample_id: str, data: dict) -> dict:
        items = self._load_json(self._microbiomes_file)
        existing = [m for m in items if m.get("sample_id") == sample_id]
        if existing:
            items = [m for m in items if m["sample_id"] != sample_id]
        m = Microbiome(sample_id)
        for k, v in data.items():
            if hasattr(m, k):
                setattr(m, k, v)
        m.analysis_date = data.get("analysis_date", date.today().isoformat())
        result = m.to_dict()
        result["diversity_index"] = m.diversity_index()
        items.append(result)
        self._save_json(self._microbiomes_file, items)
        log.info("Microbiome enregistré", sample_id=sample_id)

        try:
            from core.bgdatasys import bgdatasys
            bgdatasys.log_ml_event("microbiome", {
                "sample_id": sample_id,
                "method": data.get("method"),
                "diversity": result["diversity_index"],
            })
        except Exception:
            pass

        return result

    def get_microbiome(self, sample_id: str) -> Optional[dict]:
        for m in self._load_json(self._microbiomes_file):
            if m["sample_id"] == sample_id:
                return m
        return None

    def list_microbiomes(self, min_diversity: float = None) -> list[dict]:
        results = []
        for m in self._load_json(self._microbiomes_file):
            di = m.get("diversity_index", {}).get("index", 0)
            if min_diversity is not None and di < min_diversity:
                continue
            results.append(m)
        return results

    # ── Microscopie ─────────────────────────────────────

    def create_microscopy(self, sample_id: str, data: dict) -> dict:
        items = self._load_json(self._microscopies_file)
        obs = Microscopy(sample_id)
        for k, v in data.items():
            if hasattr(obs, k):
                setattr(obs, k, v)
        result = obs.to_dict()
        items.append(result)
        self._save_json(self._microscopies_file, items)
        log.info("Observation microscopique créée", obs_id=obs.observation_id)
        return result

    def get_microscopy(self, observation_id: str) -> Optional[dict]:
        for o in self._load_json(self._microscopies_file):
            if o["observation_id"] == observation_id:
                return o
        return None

    def list_microscopies(self, sample_id: str = None) -> list[dict]:
        if sample_id:
            return [o for o in self._load_json(self._microscopies_file)
                    if o["sample_id"] == sample_id]
        return self._load_json(self._microscopies_file)

    # ── Suivi croissance ───────────────────────────────

    def create_growth_track(self, plant_id: str, product_id: str = "",
                            espace_id: str = "", sub_zone_id: str = "") -> dict:
        tracks = self._load_dict(self._growth_file)
        if plant_id in tracks:
            return tracks[plant_id]
        gt = GrowthTrack(plant_id, product_id)
        gt.espace_id = espace_id
        gt.sub_zone_id = sub_zone_id
        tracks[plant_id] = {"plant_id": plant_id, "product_id": product_id,
                            "espace_id": espace_id, "sub_zone_id": sub_zone_id,
                            "tracking": [], "images": [], "root_images": [],
                            "measurements_history": []}
        self._save_dict(self._growth_file, tracks)
        return tracks[plant_id]

    def record_growth(self, plant_id: str, stage: str,
                      height_cm: float = None, leaf_count: int = None,
                      leaf_area_cm2: float = None,
                      stem_diameter_mm: float = None,
                      root_length_cm: float = None,
                      branching_count: int = None,
                      chlorophyll_spad: float = None,
                      ndvi: float = None,
                      image_path: str = "", notes: str = "") -> Optional[dict]:
        tracks = self._load_dict(self._growth_file)
        if plant_id not in tracks:
            return None
        gt = GrowthTrack(plant_id)
        gt.tracking = tracks[plant_id].get("tracking", [])
        obs = gt.record_observation(stage, height_cm, leaf_count, leaf_area_cm2,
                                    stem_diameter_mm, root_length_cm,
                                    branching_count, chlorophyll_spad, ndvi,
                                    image_path, notes)
        tracks[plant_id]["tracking"].append(obs)
        self._save_dict(self._growth_file, tracks)
        return obs

    def growth_summary(self, plant_id: str) -> Optional[dict]:
        tracks = self._load_dict(self._growth_file)
        if plant_id not in tracks:
            return None
        d = tracks[plant_id]
        gt = GrowthTrack(plant_id)
        gt.tracking = d.get("tracking", [])
        return gt.summary()

    def list_growth_tracks(self, product_id: str = None,
                           espace_id: str = None) -> list[dict]:
        tracks = self._load_dict(self._growth_file)
        results = []
        for pid, d in tracks.items():
            if product_id and d.get("product_id") != product_id:
                continue
            if espace_id and d.get("espace_id") != espace_id:
                continue
            gt = GrowthTrack(pid)
            gt.tracking = d.get("tracking", [])
            results.append(gt.summary())
        return results

    # ── Génétique ──────────────────────────────────────

    def create_genetic_profile(self, plant_id: str, species: str = "",
                               variety: str = "") -> dict:
        profiles = self._load_dict(self._genetics_file)
        if plant_id in profiles:
            return profiles[plant_id]
        gp = GeneticProfile(plant_id=plant_id, species=species, variety=variety)
        data = gp.to_dict()
        profiles[plant_id] = data
        self._save_dict(self._genetics_file, profiles)
        return data

    def update_genetic_profile(self, plant_id: str, data: dict) -> Optional[dict]:
        profiles = self._load_dict(self._genetics_file)
        if plant_id not in profiles:
            return None
        for k, v in data.items():
            if k in profiles[plant_id] and v is not None:
                profiles[plant_id][k] = v
        self._save_dict(self._genetics_file, profiles)
        return profiles[plant_id]

    def get_genetic_profile(self, plant_id: str) -> Optional[dict]:
        profiles = self._load_dict(self._genetics_file)
        return profiles.get(plant_id)

    def list_genetic_profiles(self, species: str = None) -> list[dict]:
        profiles = self._load_dict(self._genetics_file)
        if species:
            return {k: v for k, v in profiles.items()
                    if v.get("species", "").lower() == species.lower()}
        return profiles

    # ── Statistiques ───────────────────────────────────

    def stats(self) -> dict:
        samples = self._load_json(self._samples_file)
        analyses = self._load_json(self._analyses_file)
        microbiomes = self._load_json(self._microbiomes_file)
        microscopies = self._load_json(self._microscopies_file)
        growth = self._load_dict(self._growth_file)

        return {
            "total_samples": len(samples),
            "samples_by_type": {
                t: sum(1 for s in samples if s["sample_type"] == t)
                for t in set(s["sample_type"] for s in samples)
            },
            "soil_analyses": len(analyses),
            "microbiomes": len(microbiomes),
            "microscopies": len(microscopies),
            "growth_tracks": len(growth),
            "genetic_profiles": len(self._load_dict(self._genetics_file)),
            "avg_fertility_index": round(
                sum(a.get("fertility_index", {}).get("index", 0)
                    for a in analyses) / max(1, len(analyses)), 1),
            "samples_by_status": {
                s: sum(1 for x in samples if x["status"] == s)
                for s in set(x["status"] for x in samples)
            },
        }

    def heatmap_data(self) -> dict:
        """Données pour cartes de chaleur de santé biologique."""
        analyses = self._load_json(self._analyses_file)
        microbiomes = self._load_json(self._microbiomes_file)

        zones = {}
        for a in analyses:
            sample = self.get_sample(a["sample_id"])
            if not sample:
                continue
            loc = sample.get("location", "inconnu")
            if loc not in zones:
                zones[loc] = []
            zones[loc].append({
                "fertility": a.get("fertility_index", {}).get("index", 0),
                "ph": a.get("ph"),
                "mo": a.get("matiere_organique_pct"),
                "sample_id": a["sample_id"],
                "date": a.get("analysis_date", ""),
            })

        micro_zones = {}
        for m in microbiomes:
            sample = self.get_sample(m["sample_id"])
            if not sample:
                continue
            loc = sample.get("location", "inconnu")
            if loc not in micro_zones:
                micro_zones[loc] = []
            micro_zones[loc].append({
                "diversity": m.get("diversity_index", {}).get("index", 0),
                "shannon": m.get("bacterial_diversity_shannon"),
                "sample_id": m["sample_id"],
                "date": m.get("analysis_date", ""),
            })

        return {
            "soil_health": {z: {"avg_fertility": round(
                sum(d["fertility"] for d in v) / len(v), 1) if v else 0,
                "avg_ph": round(sum(d["ph"] for d in v if d["ph"]) / max(1,
                    sum(1 for d in v if d["ph"])), 1),
                "count": len(v)} for z, v in zones.items()},
            "microbiome_diversity": {z: {"avg_diversity": round(
                sum(d["diversity"] for d in v) / len(v), 1) if v else 0,
                "avg_shannon": round(sum(d["shannon"] for d in v
                    if d["shannon"]) / max(1, sum(1 for d in v
                    if d["shannon"])), 2) if v else 0,
                "count": len(v)} for z, v in micro_zones.items()},
        }
