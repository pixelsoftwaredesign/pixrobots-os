"""Vision par ordinateur PixelOS — Suivi de croissance, segmentation, NDVI.

Modules:
  1. PlantSegmenter → Segmentation d'images de plantes (fond/feuille/tige/fleur/racine)
  2. GrowthAnalyzer → Métriques de croissance (hauteur, surface foliaire, biomasse)
  3. NDVICalculator → Indice de végétation NDVI depuis images multispectrales
  4. RootAnalyzer → Analyse du système racinaire (longueur, angles, ramifications)
  5. DiseaseDetector → Détection de maladies foliaires par CNN
  6. VisionPipeline → Pipeline complet d'analyse d'images
"""

import structlog
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = ROOT / "data" / "images"
PROCESSED_DIR = ROOT / "data" / "images" / "processed"

# Couleurs HSV pour segmentation
COLOR_RANGES = {
    "green_leaf": [(35, 40, 40), (85, 255, 255)],
    "yellow_leaf": [(20, 50, 50), (35, 255, 255)],
    "brown_stem": [(10, 30, 30), (20, 255, 200)],
    "flower_white": [(0, 0, 180), (180, 30, 255)],
    "flower_color": [(140, 50, 50), (170, 255, 255)],
    "root": [(0, 0, 0), (180, 255, 50)],
    "soil": [(0, 0, 20), (180, 50, 100)],
}


class PlantSegmenter:
    """Segmentation d'images de plantes par couleur et morphologie."""

    def __init__(self):
        self.reference_object_cm = 2.0  # Taille d'un objet de référence (pièce, règle)

    def segment(self, image_path: str) -> dict:
        """Segmente une image de plante en régions (feuilles, tige, fleurs, fond)."""
        import cv2
        img = cv2.imread(image_path)
        if img is None:
            return {"status": "error", "message": "Image non trouvée"}
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, w = img.shape[:2]

        regions = {}
        for name, (lower, upper) in COLOR_RANGES.items():
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                                     np.ones((3, 3), np.uint8))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                                     np.ones((5, 5), np.uint8))
            pixel_count = int(np.sum(mask > 0))
            regions[name] = {
                "pixels": pixel_count,
                "area_pct": round(pixel_count / max(1, h * w) * 100, 2),
            }

            # Contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                            cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest = max(contours, key=cv2.contourArea)
                regions[name]["contours"] = len(contours)
                regions[name]["largest_area"] = int(cv2.contourArea(largest))

        # Feuilles vertes totales
        green_pct = regions.get("green_leaf", {}).get("area_pct", 0)
        yellow_pct = regions.get("yellow_leaf", {}).get("area_pct", 0)
        total_plant = green_pct + yellow_pct

        return {
            "status": "ok",
            "dimensions": {"width": w, "height": h},
            "regions": regions,
            "plant_coverage_pct": round(total_plant, 2),
            "green_ratio": round(green_pct / max(1, total_plant), 3) if total_plant > 0 else 0,
            "green_yellow_ratio": round(green_pct / max(1, yellow_pct), 2) if yellow_pct > 0 else float('inf'),
            "image_path": image_path,
        }

    def estimate_leaf_area(self, image_path: str,
                           reference_cm: float = 2.0) -> dict:
        """Estime la surface foliaire à partir d'une image avec référence."""
        seg = self.segment(image_path)
        if seg.get("status") != "ok":
            return seg

        import cv2
        img = cv2.imread(image_path)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, w = img.shape[:2]

        # Masque feuilles vertes
        mask = cv2.inRange(hsv, np.array(COLOR_RANGES["green_leaf"][0]),
                           np.array(COLOR_RANGES["green_leaf"][1]))
        green_pixels = int(np.sum(mask > 0))

        # Résolution (cm par pixel via objet de référence)
        px_per_cm = w / reference_cm  # Approximation
        leaf_area_cm2 = green_pixels / max(1, px_per_cm ** 2)

        return {
            "status": "ok",
            "leaf_pixels": green_pixels,
            "estimated_area_cm2": round(leaf_area_cm2, 2),
            "reference_cm": reference_cm,
            "resolution_px_per_cm": round(px_per_cm, 2),
        }


class GrowthAnalyzer:
    """Analyseur de croissance à partir d'images temporelles."""

    @staticmethod
    def track_growth(image_history: list[str],
                     reference_cm: float = 2.0) -> dict:
        """Analyse la croissance à travers une série temporelle d'images."""
        if len(image_history) < 2:
            return {"status": "error", "message": "Minimum 2 images requises"}

        segmenter = PlantSegmenter()
        measurements = []

        for img_path in image_history:
            seg = segmenter.estimate_leaf_area(img_path, reference_cm)
            if seg.get("status") != "ok":
                continue
            measurements.append({
                "image": img_path,
                "leaf_area_cm2": seg.get("estimated_area_cm2", 0),
                "plant_coverage": segmenter.segment(img_path).get("plant_coverage_pct", 0),
            })

        if len(measurements) < 2:
            return {"status": "error", "message": "Pas assez de mesures valides"}

        areas = [m["leaf_area_cm2"] for m in measurements]
        growth = {
            "initial_area_cm2": areas[0],
            "final_area_cm2": areas[-1],
            "total_growth_cm2": round(areas[-1] - areas[0], 2),
            "growth_rate_cm2_per_day": round(
                (areas[-1] - areas[0]) / max(1, len(measurements)), 2),
            "relative_growth_pct": round(
                (areas[-1] - areas[0]) / max(0.1, areas[0]) * 100, 1),
            "measurements": measurements,
        }
        return growth

    @staticmethod
    def height_from_image(image_path: str, top_ratio: float = 0.1,
                          bottom_ratio: float = 0.9) -> dict:
        """Estime la hauteur d'une plante à partir de l'image."""
        import cv2
        img = cv2.imread(image_path)
        if img is None:
            return {"status": "error", "message": "Image non trouvée"}

        # Trouver le bounding box du feuillage vert
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(COLOR_RANGES["green_leaf"][0]),
                           np.array(COLOR_RANGES["green_leaf"][1]))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE,
                                 np.ones((5, 5), np.uint8))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return {"status": "error", "message": "Aucun feuillage détecté"}

        all_points = np.vstack(contours)
        x, y, bw, bh = cv2.boundingRect(all_points)

        # Hauteur estimée en pixels
        plant_top = y
        plant_bottom = y + bh
        image_height = img.shape[0]

        # Hauteur relative (0-1) normalisée
        rel_height = (plant_bottom - plant_top) / image_height

        return {
            "status": "ok",
            "bounding_box": {"x": int(x), "y": int(y),
                             "width": int(bw), "height": int(bh)},
            "height_pixels": int(bh),
            "height_ratio": round(rel_height, 3),
            "center_x": int(x + bw // 2),
            "center_y": int(y + bh // 2),
        }


class NDVICalculator:
    """Calcul de NDVI (Normalized Difference Vegetation Index)."""

    @staticmethod
    def calculate(nir_image_path: str, red_image_path: str) -> dict:
        """Calcule le NDVI à partir d'images NIR et Rouge."""
        import cv2
        nir = cv2.imread(nir_image_path, cv2.IMREAD_GRAYSCALE)
        red = cv2.imread(red_image_path, cv2.IMREAD_GRAYSCALE)

        if nir is None or red is None:
            return {"status": "error", "message": "Images NIR/Rouge non trouvées"}

        nir_f = nir.astype(np.float32)
        red_f = red.astype(np.float32)

        ndvi = (nir_f - red_f) / (nir_f + red_f + 1e-10)

        mean_ndvi = float(np.mean(ndvi))
        max_ndvi = float(np.max(ndvi))
        std_ndvi = float(np.std(ndvi))

        # Seuillage NDVI
        healthy = float(np.sum(ndvi > 0.6))
        moderate = float(np.sum((ndvi > 0.3) & (ndvi <= 0.6)))
        stressed = float(np.sum((ndvi > 0.1) & (ndvi <= 0.3)))
        bare = float(np.sum(ndvi <= 0.1))
        total = max(1, healthy + moderate + stressed + bare)

        return {
            "status": "ok",
            "mean_ndvi": round(mean_ndvi, 3),
            "max_ndvi": round(max_ndvi, 3),
            "std_ndvi": round(std_ndvi, 3),
            "classification": {
                "healthy_pct": round(healthy / total * 100, 1),
                "moderate_pct": round(moderate / total * 100, 1),
                "stressed_pct": round(stressed / total * 100, 1),
                "bare_soil_pct": round(bare / total * 100, 1),
            },
            "interpretation": "végétation_dense" if mean_ndvi > 0.6 else
                              "végétation_modérée" if mean_ndvi > 0.3 else
                              "végétation_clairsemée" if mean_ndvi > 0.1 else
                              "sol_nu",
            "nir_image": nir_image_path,
            "red_image": red_image_path,
        }


class RootAnalyzer:
    """Analyse du système racinaire à partir d'images."""

    @staticmethod
    def _thin(img: np.ndarray) -> np.ndarray:
        """Algorithme d'amincissement Zhang-Suen (fallback sans ximgproc)."""
        thin = img.copy() // 255  # binariser à 0/1
        prev = np.zeros_like(thin)
        while not np.array_equal(thin, prev):
            prev = thin.copy()
            # Étape 1
            mask = np.zeros_like(thin, dtype=bool)
            for i in range(1, thin.shape[0] - 1):
                for j in range(1, thin.shape[1] - 1):
                    if thin[i, j] != 1: continue
                    p = [thin[i-1,j], thin[i-1,j+1], thin[i,j+1],
                         thin[i+1,j+1], thin[i+1,j], thin[i+1,j-1],
                         thin[i,j-1], thin[i-1,j-1]]
                    B = sum(p)
                    A = sum(1 for k in range(8) if p[k] == 0 and p[(k+1)%8] == 1)
                    p2, p4, p6, p8 = p[0], p[2], p[4], p[6]
                    if 2 <= B <= 6 and A == 1 and p2*p4*p8 == 0 and p2*p4*p6 == 0:
                        mask[i, j] = True
            thin[mask] = 0
            # Étape 2
            mask = np.zeros_like(thin, dtype=bool)
            for i in range(1, thin.shape[0] - 1):
                for j in range(1, thin.shape[1] - 1):
                    if thin[i, j] != 1: continue
                    p = [thin[i-1,j], thin[i-1,j+1], thin[i,j+1],
                         thin[i+1,j+1], thin[i+1,j], thin[i+1,j-1],
                         thin[i,j-1], thin[i-1,j-1]]
                    B = sum(p)
                    A = sum(1 for k in range(8) if p[k] == 0 and p[(k+1)%8] == 1)
                    p2, p4, p6, p8 = p[0], p[2], p[4], p[6]
                    if 2 <= B <= 6 and A == 1 and p2*p4*p6 == 0 and p2*p6*p8 == 0:
                        mask[i, j] = True
            thin[mask] = 0
        return (thin * 255).astype(np.uint8)

    @staticmethod
    def analyze(root_image_path: str, scale_cm_per_px: float = 0.01) -> dict:
        """Analyse la morphologie racinaire."""
        import cv2
        img = cv2.imread(root_image_path)
        if img is None:
            return {"status": "error", "message": "Image non trouvée"}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY_INV)

        # Squelettisation (Zhang-Suen manuelle si ximgproc indisponible)
        try:
            skeleton = cv2.ximgproc.thinning(binary)
        except AttributeError:
            skeleton = RootAnalyzer._thin(binary)
        skeleton_px = int(np.sum(skeleton > 0))

        # Branchements (détection des points de jonction)
        kernel_branch = np.array([[1, 1, 1], [1, 10, 1], [1, 1, 1]], dtype=np.uint8)
        filtered = cv2.filter2D(skeleton.astype(np.uint8), -1, kernel_branch)
        branch_points = int(np.sum(filtered >= 12))

        # Longueur totale estimée
        total_length_cm = skeleton_px * scale_cm_per_px

        # Enveloppe convexe
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            all_pts = np.vstack(contours)
            hull = cv2.convexHull(all_pts)
            hull_area = cv2.contourArea(hull)
        else:
            hull_area = 0

        return {
            "status": "ok",
            "total_skeleton_pixels": skeleton_px,
            "estimated_length_cm": round(total_length_cm, 2),
            "branch_points": branch_points,
            "branching_density": round(branch_points / max(1, skeleton_px), 4)
                if skeleton_px > 0 else 0,
            "convex_hull_area_px": int(hull_area),
            "scale_cm_per_px": scale_cm_per_px,
        }


class DiseaseDetector:
    """Détection de maladies foliaires par analyse visuelle."""

    SYMPTOM_COLORS = {
        "chlorosis": [(20, 50, 50), (40, 255, 255)],  # Jaune
        "necrosis": [(0, 30, 30), (10, 200, 150)],    # Brun
        "powdery_mildew": [(0, 0, 200), (180, 30, 255)],  # Blanc
        "rust": [(0, 100, 100), (20, 255, 255)],       # Orange/rouille
        "mosaic": [(35, 30, 30), (85, 100, 200)],      # Panaché vert clair/foncé
    }

    @staticmethod
    def detect_symptoms(image_path: str) -> dict:
        """Détecte les symptômes visuels de maladies sur feuilles."""
        import cv2
        img = cv2.imread(image_path)
        if img is None:
            return {"status": "error", "message": "Image non trouvée"}
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, w = img.shape[:2]
        total_px = h * w

        symptoms = {}
        for name, (lower, upper) in DiseaseDetector.SYMPTOM_COLORS.items():
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                                     np.ones((5, 5), np.uint8))
            pixel_count = int(np.sum(mask > 0))
            symptoms[name] = {
                "pixels": pixel_count,
                "area_pct": round(pixel_count / max(1, total_px) * 100, 3),
            }

        return {
            "status": "ok",
            "symptoms": symptoms,
            "total_affected_pct": round(
                sum(s["area_pct"] for s in symptoms.values()), 2),
            "severity": "critique" if any(
                s["area_pct"] > 30 for s in symptoms.values()) else
                       "modéré" if any(
                s["area_pct"] > 10 for s in symptoms.values()) else
                       "léger" if any(
                s["area_pct"] > 2 for s in symptoms.values()) else
                       "sain",
        }


class VisionPipeline:
    """Pipeline complet de vision par ordinateur."""

    def __init__(self):
        self.segmenter = PlantSegmenter()
        self.growth = GrowthAnalyzer()
        self.ndvi = NDVICalculator()
        self.root = RootAnalyzer()
        self.disease = DiseaseDetector()
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    def analyze_plant(self, image_path: str) -> dict:
        """Analyse complète d'une image de plante."""
        result = {
            "image": image_path,
            "timestamp": datetime.now().isoformat(),
        }

        result["segmentation"] = self.segmenter.segment(image_path)
        result["height"] = GrowthAnalyzer.height_from_image(image_path)
        result["leaf_area"] = self.segmenter.estimate_leaf_area(image_path)
        result["symptoms"] = DiseaseDetector.detect_symptoms(image_path)
        result["disease_severity"] = result["symptoms"].get("severity", "unknown")

        return result

    def analyze_growth_series(self, image_paths: list[str],
                              reference_cm: float = 2.0) -> dict:
        """Analyse d'une série temporelle de croissance."""
        result = {
            "images": image_paths,
            "count": len(image_paths),
            "timestamp": datetime.now().isoformat(),
        }

        descriptions = []
        for p in image_paths:
            descriptions.append(self.segmenter.segment(p))

        result["first"] = descriptions[0] if descriptions else {}
        result["last"] = descriptions[-1] if descriptions else {}
        result["growth"] = GrowthAnalyzer.track_growth(image_paths, reference_cm)

        return result

    def analyze_root(self, root_image_path: str) -> dict:
        """Analyse du système racinaire."""
        return RootAnalyzer.analyze(root_image_path)

    def calculate_ndvi(self, nir_path: str, red_path: str) -> dict:
        """Calcul NDVI."""
        return NDVICalculator.calculate(nir_path, red_path)

    def stats(self) -> dict:
        """Statistiques du module vision."""
        images = list(IMAGES_DIR.glob("*.*"))
        processed = list(PROCESSED_DIR.glob("*.*"))
        return {
            "raw_images": len(images),
            "processed_images": len(processed),
            "images_dir": str(IMAGES_DIR),
            "has_opencv": True,
        }
