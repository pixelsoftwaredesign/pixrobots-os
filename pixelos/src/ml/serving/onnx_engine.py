"""onnx_engine — Export ONNX du RandomForestRegressor + fallback Python.

Le RandomForestRegressor pickle (models/irrigation_model.pkl) est exporté au
format ONNX avec quantification INT8 pour inférence légère. Un fallback
transparent vers scikit-learn est maintenu si ONNXruntime est indisponible.

Usage:
    from ml.serving.onnx_engine import OnnxEngine
    engine = OnnxEngine()
    pred = engine.predict({"humidite_sol": 45, "temperature": 22, ...})
"""

import pickle
import structlog
import numpy as np
from pathlib import Path
from typing import Optional

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = ROOT / "models"
ONNX_DIR = MODELS_DIR / "onnx"


class OnnxEngine:
    """Moteur d'inférence ONNX avec fallback sklearn."""

    def __init__(self, model_name: str = "irrigation_model"):
        self.model_name = model_name
        self.pickle_path = MODELS_DIR / f"{model_name}.pkl"
        self.onnx_path = ONNX_DIR / f"{model_name}.onnx"
        self.onnx_quant_path = ONNX_DIR / f"{model_name}_quant.onnx"
        self._backend = None
        self._ort_session = None
        self._sklearn_model = None
        self.feature_names = [
            "hour", "minute", "day_of_year", "month",
            "temp_air", "humidity_air", "pressure",
            "humidity_soil_lag1", "humidity_soil_lag3", "humidity_soil_lag6",
            "rain_last_3h", "wind_speed",
        ]
        self._load()

    def _load(self):
        """Charge le modèle ONNX quantifié, puis ONNX, puis pickle."""
        if self.onnx_quant_path.exists():
            try:
                self._init_ort(self.onnx_quant_path)
                self._backend = "onnx_quant"
                log.info("ONNX quantifié chargé", path=str(self.onnx_quant_path))
                return
            except Exception as e:
                log.warning("Echec ONNX quantifié", error=str(e))

        if self.onnx_path.exists():
            try:
                self._init_ort(self.onnx_path)
                self._backend = "onnx"
                log.info("ONNX chargé", path=str(self.onnx_path))
                return
            except Exception as e:
                log.warning("Echec ONNX", error=str(e))

        self._fallback()

    def _init_ort(self, path: Path):
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.intra_op_num_threads = 2
        self._ort_session = ort.InferenceSession(str(path), opts)
        self._ort_session.disable_fallback()
        self._backend = "onnx"

    def _fallback(self):
        """Fallback vers sklearn pickle."""
        if self.pickle_path.exists():
            try:
                with open(self.pickle_path, "rb") as f:
                    self._sklearn_model = pickle.load(f)
                self._backend = "sklearn"
                log.info("Fallback sklearn", path=str(self.pickle_path))
            except Exception as e:
                log.error("Echec chargement pickle", error=str(e))
                self._backend = None
        else:
            log.warning("Aucun modèle trouvé")
            self._backend = None

    @property
    def backend(self) -> str:
        return self._backend or "none"

    def predict(self, data: dict) -> dict:
        """Prédit humidité future + recommandations.

        Accepte le même format dict que PredictorEngine.predict().
        """
        features = self._extract_features(data)
        features_2d = np.array(features).reshape(1, -1).astype(np.float32)

        if self._backend and self._backend.startswith("onnx"):
            pred = self._predict_onnx(features_2d)
        elif self._sklearn_model is not None:
            pred = self._sklearn_model.predict(features_2d)[0]
        else:
            return {"status": "error", "message": "Aucun modèle disponible",
                    "backend": "none"}

        current_hum = data.get("humidite_sol", 50)
        threshold = data.get("seuil_secheresse", 30)
        drop_rate = max(0.5, (current_hum - float(pred)) / 6.0)
        hours_to_critical = max(0, (current_hum - threshold) / drop_rate) if drop_rate > 0 else 999
        water_needed = max(0, (current_hum - threshold) * 0.3)
        confidence = min(95, max(50, 100 - abs(float(pred) - current_hum) * 2))

        return {
            "status": "ok",
            "backend": self._backend or "none",
            "current_humidity": round(current_hum, 1),
            "predicted_humidity_6h": round(float(pred), 1),
            "drop_rate_pct_per_h": round(drop_rate, 2),
            "hours_to_critical_threshold": round(hours_to_critical, 1),
            "water_needed_l_per_m2": round(water_needed, 2),
            "confidence_pct": round(confidence, 1),
            "should_irrigate": hours_to_critical < 4 and current_hum > threshold,
            "recommendation": self._recommend(current_hum, float(pred), threshold, hours_to_critical),
        }

    def _predict_onnx(self, features_2d: np.ndarray) -> float:
        """Inférence via ONNX runtime."""
        input_name = self._ort_session.get_inputs()[0].name
        ort_inputs = {input_name: features_2d}
        ort_outs = self._ort_session.run(None, ort_inputs)
        return float(ort_outs[0][0])

    def _extract_features(self, data: dict) -> list:
        from datetime import datetime
        now = datetime.now()
        return [
            now.hour, now.minute, now.timetuple().tm_yday, now.month,
            data.get("temperature", 20),
            data.get("humidite", 50),
            data.get("pression", 1013),
            data.get("humidite_sol_lag1", data.get("humidite_sol", 50)),
            data.get("humidite_sol_lag3", data.get("humidite_sol", 50)),
            data.get("humidite_sol_lag6", data.get("humidite_sol", 50)),
            data.get("pluie_3h", 0),
            data.get("vent", 0),
        ]

    def _recommend(self, current: float, predicted: float, threshold: float, hours: float) -> str:
        if current <= threshold:
            return "IRRIGUER IMMÉDIATEMENT - Humidité sous le seuil critique"
        if hours < 2:
            return f"Irrigation urgente dans {hours:.0f}h - {current}% → {predicted:.0f}%"
        if hours < 6:
            return f"Prévoir irrigation dans ~{hours:.0f}h ({predicted:.0f}% attendu)"
        if predicted > threshold + 10:
            return f"Aucune irrigation nécessaire ({predicted:.0f}% dans 6h)"
        return f"Surveiller - humidité stable à {current}%"

    def export_onnx(self, quantize: bool = True) -> dict:
        """Exporte le modèle pickle vers ONNX, optionnellement quantifié INT8."""
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType

        if not self.pickle_path.exists():
            return {"status": "error", "message": "Pickle introuvable"}

        if self._sklearn_model is None:
            with open(self.pickle_path, "rb") as f:
                self._sklearn_model = pickle.load(f)

        ONNX_DIR.mkdir(parents=True, exist_ok=True)

        n_features = self._sklearn_model.n_features_in_
        initial_type = [("float_input", FloatTensorType([None, n_features]))]
        onx = convert_sklearn(self._sklearn_model, initial_types=initial_type,
                              target_opset=18, options={"zipmap": False})

        with open(self.onnx_path, "wb") as f:
            f.write(onx.SerializeToString())

        result = {
            "status": "ok",
            "backend": "onnx",
            "model": str(self.onnx_path),
            "size_kb": round(self.onnx_path.stat().st_size / 1024, 1),
        }

        if quantize:
            qr = self._quantize()
            result["quantized"] = qr

        self._load()
        log.info("Export ONNX réussi", **result)
        return result

    def _quantize(self) -> dict:
        """Quantification INT8 du modèle ONNX."""
        try:
            from onnxruntime.quantization import quantize_dynamic, QuantType
            qpath = self.onnx_quant_path
            quantize_dynamic(
                str(self.onnx_path),
                str(qpath),
                weight_type=QuantType.QInt8,
            )
            return {
                "status": "ok",
                "model": str(qpath),
                "size_kb": round(qpath.stat().st_size / 1024, 1),
                "quant_type": "QInt8",
            }
        except Exception as e:
            log.warning("Echec quantification", error=str(e))
            return {"status": "error", "message": str(e)}

    def stats(self) -> dict:
        return {
            "backend": self._backend or "none",
            "pickle": str(self.pickle_path) if self.pickle_path.exists() else None,
            "onnx": str(self.onnx_path) if self.onnx_path.exists() else None,
            "onnx_quant": str(self.onnx_quant_path) if self.onnx_quant_path.exists() else None,
            "pickle_size_kb": round(self.pickle_path.stat().st_size / 1024, 1) if self.pickle_path.exists() else 0,
            "onnx_size_kb": round(self.onnx_path.stat().st_size / 1024, 1) if self.onnx_path.exists() else 0,
            "onnx_quant_size_kb": round(self.onnx_quant_path.stat().st_size / 1024, 1) if self.onnx_quant_path.exists() else 0,
        }
