"""pipeline — Pipeline d'auto-retrain declenche par TaskManager.

Cycle complet:
  1. Lecture des donnees historiques depuis bgdatasys (MongoDB + Lake)
  2. Feature engineering (lags, agregation, normalisation)
  3. Entrainement RandomForestRegressor
  4. Evaluation (MAE, R2, precision)
  5. Sauvegarde pickle
  6. Export ONNX + quantification INT8
  7. Deploiement (remplacement du modele actif)
  8. Notification MQTT + mise a jour de la tache

Usage:
    pipeline = TrainingPipeline()
    result = pipeline.run(trigger_task_id="abc123")
"""

import pickle
import structlog
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = ROOT / "models"


class TrainingPipeline:
    """Pipeline d'auto-retrain pour les modeles ML PixelOS."""

    def __init__(self, model_name: str = "irrigation_model",
                 zone: str = "sol_serre"):
        self.model_name = model_name
        self.zone = zone
        self.feature_names = [
            "hour", "minute", "day_of_year", "month",
            "temp_air", "humidity_air", "pressure",
            "humidity_soil_lag1", "humidity_soil_lag3", "humidity_soil_lag6",
            "rain_last_3h", "wind_speed",
        ]
        self.model_dir = MODELS_DIR
        self.model_dir.mkdir(exist_ok=True)

    def run(self, days: int = 30, force: bool = False,
            trigger_task_id: str = None) -> dict:
        """Execute le pipeline complet."""
        log.info("Pipeline start", model=self.model_name, days=days)

        stages = {}

        # Stage 1-2 : Lecture + Feature Engineering
        s1 = self._load_features(days)
        stages["feature_loading"] = s1
        if s1["status"] != "ok":
            return self._result(stages, "feature_loading")

        X, y = s1["X"], s1["y"]

        # Stage 3 : Entrainement
        s2 = self._train(X, y)
        stages["training"] = s2
        if s2["status"] != "ok":
            return self._result(stages, "training")

        model = s2["model"]

        # Stage 4 : Evaluation
        s3 = self._evaluate(model, X, y)
        stages["evaluation"] = s3

        # Stage 5 : Sauvegarde pickle
        s4 = self._save_pickle(model)
        stages["save_pickle"] = s4

        # Stage 6 : Export ONNX
        s5 = self._export_onnx(s3["metrics"])
        stages["export_onnx"] = s5

        # Stage 7 : Enregistrement dans TimescaleDB
        run_id = f"PL-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        try:
            from core.bgdatasys import bgdatasys
            bgdatasys.record_training(
                run_id, self.model_name, "completed", s3["metrics"],
                self.feature_names, s1["samples"], 0,
                s3["metrics"]["mae"], s3["metrics"]["r2_score"],
                str(MODELS_DIR / f"{self.model_name}.pkl"))
            stages["tsdb_record"] = {"status": "ok", "run_id": run_id}
        except Exception as e:
            stages["tsdb_record"] = {"status": "skipped", "error": str(e)}

        # Stage 8 : Notification + tâche
        if trigger_task_id:
            s6 = self._notify_task(trigger_task_id, s3["metrics"])
            stages["task_update"] = s6

        stages["status"] = "completed"
        log.info("Pipeline completed", metrics=s3["metrics"])
        return self._result(stages, "completed", s3["metrics"])

    def _load_features(self, days: int) -> dict:
        """Charge les donnees depuis bgdatasys et construit X, y."""
        try:
            from core.bgdatasys import bgdatasys

            since = datetime.utcnow() - timedelta(days=days)
            rows = bgdatasys.query_sensors(space=self.zone, hours=days * 24)

            if len(rows) < 50:
                return {"status": "error",
                        "message": f"Pas assez de donnees: {len(rows)}"}

            X, y = [], []
            for i, r in enumerate(rows):
                ts = r.get("timestamp", datetime.utcnow())
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))

                features = [
                    ts.hour, ts.minute, ts.timetuple().tm_yday, ts.month,
                    float(r.get("temperature", r.get("temp_air", 20))),
                    float(r.get("humidity_air", r.get("humidite", 50))),
                    float(r.get("pressure", r.get("pression", 1013))),
                ]

                for lag in [1, 3, 6]:
                    if i >= lag:
                        features.append(float(
                            rows[i - lag].get("humidite_sol",
                                              rows[i - lag].get("value", 0))))
                    else:
                        features.append(features[-1] if features else 50)

                rain_3h = sum(
                    float(rows[j].get("pluie", rows[j].get("rain", 0)))
                    for j in range(max(0, i - 18), i)
                )
                features.append(rain_3h)
                features.append(float(r.get("wind_speed", r.get("vent", 0))))

                future_idx = i + 36
                target_key = "humidite_sol"
                if future_idx < len(rows):
                    target = rows[future_idx].get(
                        target_key, rows[future_idx].get("value", None))
                    if target is not None:
                        y.append(float(target))
                        X.append(features)

            X_arr = np.array(X, dtype=np.float32)
            y_arr = np.array(y, dtype=np.float32)

            return {
                "status": "ok",
                "X": X_arr,
                "y": y_arr,
                "samples": len(X_arr),
                "features": len(self.feature_names),
            }
        except Exception as e:
            log.error("Echec feature loading", error=str(e))
            return {"status": "error", "message": str(e)}

    def _train(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Entraine un RandomForestRegressor."""
        from sklearn.ensemble import RandomForestRegressor

        model = RandomForestRegressor(
            n_estimators=100, max_depth=12, min_samples_leaf=5,
            n_jobs=-1, random_state=42,
        )
        model.fit(X, y)
        return {"status": "ok", "model": model}

    def _evaluate(self, model, X: np.ndarray, y: np.ndarray) -> dict:
        """Evalue le modele via validation croisée simple."""
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_absolute_error, r2_score

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42)

        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        accuracy = round(max(0, 100 - (mae / np.mean(y) * 100)), 1) if np.mean(y) > 0 else 0

        importances = sorted(
            zip(self.feature_names, model.feature_importances_),
            key=lambda x: -x[1])

        metrics = {
            "mae": round(mae, 2),
            "r2_score": round(r2, 3),
            "accuracy_pct": accuracy,
            "samples": len(X),
            "features": [{"name": n, "importance": round(v, 3)}
                         for n, v in importances[:8]],
        }
        return {"status": "ok", "metrics": metrics}

    def _save_pickle(self, model) -> dict:
        """Sauvegarde le modele en pickle."""
        path = self.model_dir / f"{self.model_name}.pkl"
        with open(path, "wb") as f:
            pickle.dump(model, f)
        return {
            "status": "ok",
            "path": str(path),
            "size_kb": round(path.stat().st_size / 1024, 1),
        }

    def _export_onnx(self, metrics: dict) -> dict:
        """Exporte le pickle en ONNX + quantification."""
        try:
            from ml.serving.onnx_engine import OnnxEngine
            engine = OnnxEngine(self.model_name)
            result = engine.export_onnx(quantize=True)
            return {
                "status": "ok",
                "onnx_path": result.get("model"),
                "size_kb": result.get("size_kb"),
                "quantized": result.get("quantized", {}),
            }
        except Exception as e:
            log.warning("Echec export ONNX (non-bloquant)", error=str(e))
            return {"status": "skipped", "message": str(e)}

    def _notify_task(self, task_id: str, metrics: dict) -> dict:
        """Met à jour la tâche déclencheuse avec les résultats."""
        try:
            from core.tasks import TaskManager
            tm = TaskManager()
            title = (f"[Pipeline] {self.model_name} — "
                     f"MAE={metrics['mae']}% R²={metrics['r2_score']}")
            tm.update(task_id, title=title, status="done",
                      description=str(metrics))
            return {"status": "ok", "task_id": task_id}
        except Exception as e:
            log.warning("Echec mise à jour tâche", error=str(e))
            return {"status": "error", "message": str(e)}

    def _result(self, stages: dict, fail_stage: str = None,
                metrics: dict = None) -> dict:
        stages.pop("status", None)
        return {
            "pipeline": self.model_name,
            "zone": self.zone,
            "status": "completed" if fail_stage in (None, "completed") else "failed",
            "fail_stage": fail_stage if fail_stage != "completed" else None,
            "stages": {k: v for k, v in stages.items()
                       if k not in ("X", "y", "model")},
            "metrics": metrics or {},
            "timestamp": datetime.now().isoformat(),
        }

    def rollback(self, version: str = None) -> dict:
        """Restaure une version precedente du modele."""
        from glob import glob
        backups = sorted(
            (self.model_dir / "backups").glob(f"{self.model_name}_*.pkl"))
        if not backups:
            return {"status": "error", "message": "Aucun backup disponible"}
        target = backups[-1] if version is None else \
            next((b for b in backups if version in b.name), None)
        if not target or not target.exists():
            return {"status": "error", "message": f"Version {version} introuvable"}
        with open(target, "rb") as f:
            model = pickle.load(f)
        self._save_pickle(model)
        return {"status": "ok", "restored": str(target)}

    def list_versions(self) -> list[dict]:
        """Liste les versions disponibles."""
        from glob import glob
        backups = sorted(
            (self.model_dir / "backups").glob(f"{self.model_name}_*.pkl"))
        return [{"file": b.name, "size_kb": round(b.stat().st_size / 1024, 1),
                 "modified": datetime.fromtimestamp(b.stat().st_mtime).isoformat()}
                for b in backups]
