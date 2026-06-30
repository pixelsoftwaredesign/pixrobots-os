"""training_scheduler — Entrainement automatique planifie par TaskManager.

Planifie et execute des taches recurrentes d'entrainement ML via:
  - Calendrier: verification periodique si >7 jours depuis dernier train
  - Volume de donnees: declenchement si nouvelles donnees disponibles
  - Performance: declenchement si degradation du modele detectee
"""

import structlog
from datetime import datetime, timezone, timedelta
from typing import Optional

log = structlog.get_logger()

DEFAULT_MIN_DAYS = 7
DEFAULT_MIN_LAKE_FILES = 10


class TrainingScheduler:
    """Planificateur d'entrainement automatique.

    Usage:
        scheduler = TrainingScheduler(mqtt_client)
        reason = scheduler.should_train()
        if reason:
            scheduler.run_training()
    """

    def __init__(self, mqtt_client, bgdatasys_instance=None,
                 min_days: int = DEFAULT_MIN_DAYS,
                 min_lake_files: int = DEFAULT_MIN_LAKE_FILES):
        self.mqtt = mqtt_client
        self._bgdatasys = bgdatasys_instance
        self.min_days = min_days
        self.min_lake_files = min_lake_files
        self._last_train_check: Optional[datetime] = None
        self._stats = {
            "checks": 0,
            "trainings_triggered": 0,
            "trainings_skipped": 0,
            "errors": 0,
        }

    @property
    def bgdatasys(self):
        if self._bgdatasys is None:
            from core.bgdatasys import bgdatasys
            self._bgdatasys = bgdatasys
        return self._bgdatasys

    def should_train(self) -> Optional[str]:
        """Verifie si un entrainement est necessaire.

        Returns:
            Raison (str) si un train est necessaire, None sinon.
        """
        self._stats["checks"] += 1

        # 1. Verifier s'il y a deja un train en cours
        from core.tasks import TaskManager
        tm = TaskManager()
        running = tm.search(categorie="training", status="in_progress")
        if running:
            log.info("Train deja en cours, skip", task_id=running[0]["id"])
            self._stats["trainings_skipped"] += 1
            return None

        # 2. Verifier le temps depuis le dernier train
        done = tm.search(categorie="training", status="done")
        if done:
            recent = any(
                t.get("updated", "")[:10] >=
                (datetime.now() - timedelta(days=self.min_days)).strftime("%Y-%m-%d")
                for t in done
            )
            if recent:
                self._stats["trainings_skipped"] += 1
                return None

        # 3. Verifier le volume de donnees
        try:
            stats = self.bgdatasys.stats()
            lake_files = stats.get("lake_sensor_files", 0)
            tsdb_measurements = stats.get("tsdb", {}).get("total_measurements", 0)
        except Exception as e:
            log.warning("Echec stats bgdatasys", error=str(e))
            lake_files = 0
            tsdb_measurements = 0

        reasons = []
        if tsdb_measurements < 100:
            reasons.append(f"donnees insuffisantes: {tsdb_measurements} mesures")
        if lake_files < self.min_lake_files:
            reasons.append(
                f"fichiers lake insuffisants: {lake_files} < {self.min_lake_files}")

        if reasons:
            self._stats["trainings_skipped"] += 1
            log.info("Train skip", reasons=reasons)
            return None

        # 4. Verifier si un retrain a deja ete fait ce jour
        today = datetime.now().strftime("%Y-%m-%d")
        today_tasks = [t for t in done
                       if t.get("created", "")[:10] == today]
        if len(today_tasks) >= 2:
            log.info("Deja 2 trains aujourd'hui, skip")
            self._stats["trainings_skipped"] += 1
            return None

        # 5. Verifier si la performance s'est degradee
        perf_reason = self._check_performance_degradation()
        if perf_reason:
            return perf_reason

        return "calendrier: >{} jours depuis dernier train".format(self.min_days)

    def _check_performance_degradation(self) -> Optional[str]:
        """Verifie si le modele s'est degrade sur les dernieres predictions."""
        try:
            recent_preds = self.bgdatasys.query_predictions(
                model_name="irrigation_model", hours=168)
            if not recent_preds:
                return None

            with_actual = [p for p in recent_preds
                           if p.get("actual_value") is not None]
            if len(with_actual) < 10:
                return None

            errors = [abs(p["predicted_value"] - p["actual_value"])
                      for p in with_actual]
            avg_error = sum(errors) / len(errors)

            # Chercher le dernier MAE enregistre
            runs = self.bgdatasys.list_training_runs(
                model_name="irrigation_model", limit=1)
            last_mae = None
            if runs:
                last_mae = runs[0].get("mae", None)

            if last_mae and avg_error > last_mae * 1.5:
                return (f"degradation performance: "
                        f"avg_error={avg_error:.2f} vs mae={last_mae:.2f}")

        except Exception as e:
            log.warning("Echec verification performance", error=str(e))

        return None

    def run_training(self, force: bool = False) -> dict:
        """Execute un entrainement via le pipeline ML.

        Returns:
            dict avec le resultat du pipeline.
        """
        from core.tasks import TaskManager
        tm = TaskManager()

        task = tm.create(
            title="Auto-retrain irrigation (Scheduler)",
            description="Declenche par TrainingScheduler",
            categorie="training",
            priorite="medium",
        )

        try:
            from ml.pipeline import TrainingPipeline
            pipeline = TrainingPipeline()
            result = pipeline.run(days=30, force=force,
                                  trigger_task_id=task["id"])
            self._stats["trainings_triggered"] += 1

            self._publish_result(result, task["id"])

            log.info("Auto-retrain ML reussi",
                     task_id=task["id"],
                     mae=result.get("metrics", {}).get("mae"),
                     r2=result.get("metrics", {}).get("r2_score"))
            return result

        except Exception as e:
            self._stats["errors"] += 1
            log.error("Echec auto-retrain ML", error=str(e))
            tm.update(task["id"], status="done",
                      description=f"Echec: {str(e)}")
            return {"status": "error", "message": str(e), "task_id": task["id"]}

    def _publish_result(self, result: dict, task_id: str):
        """Publie le resultat du train sur MQTT."""
        try:
            self.mqtt.publish("pixelos/ml/pipeline", {
                "status": result.get("status"),
                "metrics": result.get("metrics", {}),
                "task_id": task_id,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            log.warning("Echec publication resultat MQTT", error=str(e))

    def check_and_run(self) -> dict:
        """Verifie si un train est necessaire et l'execute si oui.

        Returns:
            dict avec la raison et le resultat (ou skipped).
        """
        reason = self.should_train()
        if not reason:
            return {"status": "skipped", "reason": "pas necessaire"}

        log.info("Auto-retrain ML declenche", reason=reason)
        result = self.run_training()
        return {
            "status": result.get("status", "error"),
            "reason": reason,
            "result": result,
        }

    def stats(self) -> dict:
        return {**self._stats}

    def schedule_recurring(self, cron_expression: str = "0 */12 * * *") -> dict:
        """Cree une tache recurrente d'entrainement dans TaskManager."""
        from core.tasks import TaskManager
        tm = TaskManager()
        existing = tm.search(categorie="training",
                             status="todo")
        recurring = [t for t in existing
                     if "recurring" in t.get("description", "").lower()]
        if recurring:
            return {"status": "ok", "message": "Tache recurrente deja existante",
                    "task_id": recurring[0]["id"]}

        task = tm.create(
            title="Auto-retrain recurrent irrigation (toutes les 12h)",
            description="Tache recurrente planifiee par TrainingScheduler",
            categorie="training",
            priorite="medium",
        )
        return {"status": "ok", "task_id": task["id"]}
