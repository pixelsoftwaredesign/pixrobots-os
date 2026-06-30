# Pixel Software Design � Copyright 2026
"""Standard Biodiversité PixelOS — format universel pour décrire espèces et races."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime
import json, hashlib


# ─── Standards ──────────────────────────────────────────────

CONSERVATION_STATUS = [
    "eteinte", "eteinte_a_l_etat_sauvage",
    "gravement_menacee", "menacee", "vulnerable",
    "quasi_menacee", "preoccupation_mineure",
    "donnees_insuffisantes", "non_evaluee",
]

CONSERVATION_SOURCES = ["iucn", "uicn_france", "association", "locale"]

CONFIDENTIALITY_LEVELS = ["public", "membres", "association", "prive"]


@dataclass
class Geolocation:
    latitude: float = 0.0
    longitude: float = 0.0
    altitude_m: Optional[float] = None
    region: str = ""
    pays: str = ""
    biome: str = ""  # foret_tropicale, desert, mediterraneen, tempere, etc.


@dataclass
class GenomeReference:
    sequence_type: str = ""      # genome_complet, barcode, marqueur
    marker: str = ""             # rbcL, matK, ITS, COI, etc.
    reference_url: str = ""
    gc_content_pct: Optional[float] = None


@dataclass
class CultivationProfile:
    """Profil cultural (besoins pour la conservation/reproduction)."""
    besoin_eau: str = ""           # faible, moyen, eleve
    type_sol: list[str] = field(default_factory=list)
    ph_min: float = 5.5
    ph_max: float = 7.5
    temperature_min_c: float = 0
    temperature_max_c: float = 40
    temperature_optimale_c: float = 20
    exposition: str = ""           # plein_soleil, mi_ombre, ombre
    cycle_vie_jours: int = 0
    rusticite: str = ""            # rustique, semi_rustique, non_rustique
    besoin_froid_h: int = 0        # heures de froid nécessaires


@dataclass
class ConservationRecord:
    status: str = "non_evaluee"   # une des CONSERVATION_STATUS
    source: str = ""               # une des CONSERVATION_SOURCES
    population_estimee: int = 0
    tendance: str = ""             # stable, declin, augmentation, inconnue
    menaces: list[str] = field(default_factory=list)
    dernier_recensement: str = ""


@dataclass
class SeedStock:
    """Stock de semences (banque de semences)."""
    quantite_kg: float = 0
    nombre_individus: int = 0
    lieu_stockage: str = ""
    date_recolte: str = ""
    viabilite_pct: float = 0
    genotype_ref: str = ""


@dataclass
class BiodiversityRecord:
    """Fiche universelle de biodiversité pour le réseau PixelOS."""

    # Identité
    species_id: str = ""
    nom_scientifique: str = ""
    nom_commun: str = ""
    noms_locaux: list[str] = field(default_factory=list)
    famille: str = ""
    genre: str = ""
    rang: str = "espece"  # espece, sous_espece, variete, race, cultivar

    # Classification
    regne: str = "vegetal"  # vegetal, animal, fonge, bacterie
    groupe: str = ""        # angiosperme, gymnosperme, mammifere, etc.
    type_race: str = ""     # rare, locale, ancienne, commerciale, sauvage

    # Conservation
    conservation: ConservationRecord = field(default_factory=ConservationRecord)
    confidentialite: str = "public"   # une des CONFIDENTIALITY_LEVELS

    # Géolocalisation d'origine
    origine: Geolocation = field(default_factory=Geolocation)

    # Culture / élevage
    cultivation: CultivationProfile = field(default_factory=CultivationProfile)
    usages: list[str] = field(default_factory=list)

    # Génétique
    genome: GenomeReference = field(default_factory=GenomeReference)

    # Banque de semences
    seed_stocks: list[SeedStock] = field(default_factory=list)
    banque_url: str = ""

    # Traçabilité
    createur_id: str = ""        # node_id du créateur
    signature: str = ""
    date_creation: str = ""
    date_modification: str = ""
    version: int = 1

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent=2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def fingerprint(self) -> str:
        """Hash unique de l'espèce basé sur ses attributs immuables."""
        raw = f"{self.nom_scientifique}|{self.origine.region}|{self.origine.pays}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def sign(self, private_key: str) -> str:
        """Signe cryptographiquement l'enregistrement."""
        data = self.to_json()
        from hashlib import sha256
        self.signature = sha256((data + private_key).encode()).hexdigest()
        return self.signature

    def verify(self, public_key: str) -> bool:
        """Vérifie la signature."""
        stored_sig = self.signature
        from hashlib import sha256
        self.signature = ""
        data = self.to_json()
        expected = sha256((data + public_key).encode()).hexdigest()
        self.signature = stored_sig
        return stored_sig == expected


# ─── Registry Mondial ──────────────────────────────────────

class BiodiversityRegistry:
    """Index local des espèces enregistrées sur ce nœud."""

    def __init__(self, path: str = "data/biodiversity/"):
        self.path = path
        import os
        os.makedirs(path, exist_ok=True)

    def save(self, record: BiodiversityRecord) -> str:
        fp = record.fingerprint()
        filepath = f"{self.path}/{fp}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(record.to_json())
        return fp

    def load(self, fingerprint: str) -> Optional[BiodiversityRecord]:
        filepath = f"{self.path}/{fingerprint}.json"
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            return self._from_dict(data)
        except:
            return None

    def search(self, query: str) -> list[dict]:
        results = []
        import glob
        for f in glob.glob(f"{self.path}/*.json"):
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if (query.lower() in data.get("nom_scientifique", "").lower()
                or query.lower() in data.get("nom_commun", "").lower()
                or query.lower() in data.get("famille", "").lower()):
                results.append(data)
        return results

    def list_by_status(self, status: str) -> list[dict]:
        results = []
        import glob
        for f in glob.glob(f"{self.path}/*.json"):
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("conservation", {}).get("status") == status:
                results.append(data)
        return results

    def _from_dict(self, data: dict) -> BiodiversityRecord:
        cons = ConservationRecord(**data.get("conservation", {}))
        orig = Geolocation(**data.get("origine", {}))
        cult = CultivationProfile(**data.get("cultivation", {}))
        gen = GenomeReference(**data.get("genome", {}))
        stocks = [SeedStock(**s) for s in data.get("seed_stocks", [])]
        return BiodiversityRecord(
            **{k: v for k, v in data.items()
               if k not in ("conservation", "origine", "cultivation",
                            "genome", "seed_stocks")},
            conservation=cons, origine=orig, cultivation=cult,
            genome=gen, seed_stocks=stocks,
        )

    def stats(self) -> dict:
        import glob
        all_files = list(glob.glob(f"{self.path}/*.json"))
        species = []
        for f in all_files:
            with open(f, encoding="utf-8") as fh:
                species.append(json.load(fh))
        return {
            "total": len(species),
            "par_statut": {s: sum(1 for x in species
                                  if x.get("conservation", {}).get("status") == s)
                          for s in CONSERVATION_STATUS},
            "par_confidentialite": {s: sum(1 for x in species
                                           if x.get("confidentialite") == s)
                                   for s in CONFIDENTIALITY_LEVELS},
            "par_type_race": {s: sum(1 for x in species
                                     if x.get("type_race") == s)
                             for s in ["rare", "locale", "ancienne",
                                       "commerciale", "sauvage"]},
            "par_biome": {s: sum(1 for x in species
                                 if x.get("origine", {}).get("biome") == s)
                         for s in set(x.get("origine", {}).get("biome", "")
                                      for x in species if x.get("origine", {}).get("biome"))},
        }


biodiversity_registry = BiodiversityRegistry()
