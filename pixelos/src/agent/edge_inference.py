"""edge_inference — Inférence ONNX embarquée dans le cycle agent.

Charge le modele ONNX quantifie et execute des predictions sur les dernieres
lectures capteurs a chaque cycle. Publie les resultats via MQTT et peut
declencher des actions (irrigation, alertes) basees sur les predictions.
"""

import structlog
from datetime import datetime, timezone
from typing import Optional

log = structlog.get_logger()

DEFAULT_CONFIDENCE_THRESHOLD = 0.6
DEFAULT_CRITICAL_HOURS = 4


class EdgeInferenceEngine:
    """Moteur d'inference ONNX embarque dans l'agent.

    Usage:
        engine = EdgeInferenceEngine(mqtt_client)
        engine.load_model()
        result = engine.predict_and_act(latest_sensor_data)
    """

    def __init__(self, mqtt_client, bgdatasys_instance=None,
                 model_name: str = "irrigation_model",
                 confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
                 critical_hours: int = DEFAULT_CRITICAL_HOURS):
        self.mqtt = mqtt_client
        self._bgdatasys = bgdatasys_instance
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.critical_hours = critical_hours
        self._engine = None
        self._loaded = False
        self._last_predictions: list[dict] = []
        self._stats = {
            "predictions": 0,
            "actions_triggered": 0,
            "errors": 0,
            "backend": "none",
        }

    @property
    def bgdatasys(self):
        if self._bgdatasys is None:
            from core.bgdatasys import bgdatasys
            self._bgdatasys = bgdatasys
        return self._bgdatasys

    @property
    def onnx_engine(self):
        if self._engine is None:
            from ml.serving.onnx_engine import OnnxEngine
            self._engine = OnnxEngine(self.model_name)
        return self._engine

    def load_model(self) -> dict:
        """Charge (ou re-charge) le modele ONNX."""
        try:
            engine = self.onnx_engine
            self._loaded = engine.backend != "none"
            self._stats["backend"] = engine.backend
            log.info("Modele ONNX charge", backend=engine.backend,
                     model=self.model_name)
            return {"status": "ok", "backend": engine.backend}
        except Exception as e:
            self._loaded = False
            self._stats["errors"] += 1
            log.error("Echec chargement modele ONNX", error=str(e))
            return {"status": "error", "message": str(e)}

    def is_loaded(self) -> bool:
        return self._loaded

    def predict(self, sensor_data: dict) -> dict:
        """Execute une prediction ONNX sur les donnees capteurs."""
        if not self._loaded:
            result = self.load_model()
            if result["status"] != "ok":
                return {"status": "error", "message": "Modele non disponible"}

        try:
            result = self.onnx_engine.predict(sensor_data)
            self._stats["predictions"] += 1
            self._last_predictions.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                **result,
            })
            if len(self._last_predictions) > 100:
                self._last_predictions = self._last_predictions[-100:]
            return result
        except Exception as e:
            self._stats["errors"] += 1
            log.error("Echec inference ONNX", error=str(e))
            return {"status": "error", "message": str(e)}

    def predict_and_act(self, space_id: str, sensor_data: dict) -> dict:
        """Predict + publie MQTT + declenche actions si necessaire.

        Args:
            space_id: Identifiant de l'espace (ex: serre_a)
            sensor_data: Dictionnaire de lectures capteurs

        Returns:
            dict avec prediction, action, et publication MQTT.
        """
        pred = self.predict(sensor_data)
        if pred.get("status") == "error":
            return pred

        action = self._decide_action(pred)

        # Publication MQTT
        self._publish_prediction(space_id, pred, action)

        # Enregistrement dans bgdatasys
        try:
            self.bgdatasys.write_prediction(
                model_name=self.model_name,
                space_id=space_id,
                predicted_value=pred.get("predicted_humidity_6h"),
                confidence=pred.get("confidence_pct", 0) / 100.0,
                features={"current_humidity": sensor_data.get("humidite_sol"),
                          "temperature": sensor_data.get("temperature")},
            )
        except Exception as e:
            log.warning("Echec enregistrement prediction bgdatasys", error=str(e))

        result = {
            "prediction": pred,
            "action": action,
        }

        if action.get("triggered"):
            self._stats["actions_triggered"] += 1
            self._trigger_action(space_id, pred, action)

        return result

    def _decide_action(self, pred: dict) -> dict:
        """Decide si une action est necessaire selon la prediction."""
        should_irrigate = pred.get("should_irrigate", False)
        hours_to_critical = pred.get("hours_to_critical_threshold", 999)
        confidence = pred.get("confidence_pct", 0) / 100.0
        recommendation = pred.get("recommendation", "")

        triggered = False
        action_type = "none"
        severity = "info"

        if confidence < self.confidence_threshold:
            action_type = "low_confidence"
            severity = "warning"

        if should_irrigate and confidence >= self.confidence_threshold:
            triggered = True
            action_type = "irrigate"
            severity = "critical" if hours_to_critical < 2 else "warning"

        if hours_to_critical < self.critical_hours and hours_to_critical > 0:
            triggered = True
            if action_type == "none":
                action_type = "prepare_irrigation"
                severity = "warning"

        return {
            "triggered": triggered,
            "action_type": action_type,
            "severity": severity,
            "hours_to_critical": round(hours_to_critical, 1),
            "confidence": round(confidence, 2),
            "recommendation": recommendation,
        }

    def _publish_prediction(self, space_id: str, pred: dict, action: dict):
        """Publie la prediction et l'action sur MQTT."""
        try:
            self.mqtt.publish(f"pixelos/{space_id}/ml/prediction", {
                "model": self.model_name,
                "backend": pred.get("backend"),
                "current_humidity": pred.get("current_humidity"),
                "predicted_humidity_6h": pred.get("predicted_humidity_6h"),
                "hours_to_critical": pred.get("hours_to_critical_threshold"),
                "water_needed": pred.get("water_needed_l_per_m2"),
                "confidence": pred.get("confidence_pct"),
                "recommendation": pred.get("recommendation"),
                "action": action,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            log.warning("Echec publication prediction MQTT", error=str(e))

        if action.get("triggered"):
            topic = (f"pixelos/{space_id}/ml/alert"
                     if action["severity"] == "critical"
                     else f"pixelos/{space_id}/ml/action")
            try:
                self.mqtt.publish(topic, {
                    "action_type": action["action_type"],
                    "severity": action["severity"],
                    "hours_to_critical": action["hours_to_critical"],
                    "recommendation": action["recommendation"],
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                log.warning("Echec publication action MQTT", error=str(e))

    def _trigger_action(self, space_id: str, pred: dict, action: dict):
        """Declenche une action physique (irrigation, alerte)."""
        try:
            self.mqtt.publish(f"pixelos/{space_id}/actuator/irrigation/cmd", {
                "cmd": "irrigate",
                "water_needed_l_per_m2": pred.get("water_needed_l_per_m2"),
                "hours_to_critical": action["hours_to_critical"],
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            log.info("Action irrigation declenchee",
                     space_id=space_id,
                     liters=pred.get("water_needed_l_per_m2"))
        except Exception as e:
            log.warning("Echec declenchement action", error=str(e))

    def stats(self) -> dict:
        return {
            "loaded": self._loaded,
            "model": self.model_name,
            "backend": self._stats["backend"],
            "total_predictions": self._stats["predictions"],
            "actions_triggered": self._stats["actions_triggered"],
            "errors": self._stats["errors"],
            "cached_predictions": len(self._last_predictions),
        }

    def last_predictions(self, limit: int = 10) -> list[dict]:
        return self._last_predictions[-limit:]

    def reload(self) -> dict:
        """Recharge le modele (apres un retrain par exemple)."""
        self._engine = None
        self._loaded = False
        return self.load_model()
