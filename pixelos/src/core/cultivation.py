# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""PixelOS CultivationManager - Orchestration intelligente de la production agricole.

Integration transverse entre:
  - SpaceManager (capteurs, controles, espaces)
  - LifecycleManager (produits, stages, plantations)
  - TaskManager (taches)
  - HarvestManager (recoltes, lots)
  - GeothermalManager (chauffage/refroidissement)
  - EnergyManager (energie solaire/batterie)

Fonctionnalites:
  1. Surveillance intelligente: capteurs -> stage -> deviations -> alertes
  2. Auto-controle: deviations -> commandes automatiques (irrigation, chauffage, eclairage)
  3. Generation de taches contextees: liant capteurs + cycle de vie
  4. Suggestions agregees: toutes les sources en un seul endpoint
  5. Rapport de culture: etat complet de chaque plantation
"""

import structlog
from datetime import datetime

log = structlog.get_logger()


class CultivationManager:
    """Orchestrateur transverse de la production agricole."""

    def __init__(self):
        self._managers_loaded = False
        self.sm = None
        self.lm = None
        self.tm = None
        self.hm = None
        self.gm = None
        self.em = None

    def _load_managers(self):
        if self._managers_loaded:
            return
        try:
            from core.spaces import SpaceManager
            self.sm = SpaceManager()
        except Exception as e:
            log.warning("SpaceManager non disponible", error=str(e))

        try:
            from core.lifecycle import LifecycleManager
            self.lm = LifecycleManager()
        except Exception as e:
            log.warning("LifecycleManager non disponible", error=str(e))

        try:
            from core.tasks import TaskManager
            self.tm = __import__("core.tasks", fromlist=["TaskManager"]).TaskManager()
        except Exception as e:
            log.warning("TaskManager non disponible", error=str(e))

        try:
            from core.harvest import HarvestManager
            self.hm = HarvestManager()
        except Exception as e:
            log.warning("HarvestManager non disponible", error=str(e))

        try:
            from core.geothermal import GeothermalManager
            self.gm = GeothermalManager()
        except Exception as e:
            log.warning("GeothermalManager non disponible", error=str(e))

        try:
            from core.energy import EnergyManager
            self.em = EnergyManager()
        except Exception as e:
            log.warning("EnergyManager non disponible", error=str(e))

        self._managers_loaded = True

    # ── Smart Monitor ───────────────────────────────────────

    def smart_monitor(self) -> dict:
        """Cycle de surveillance complet:
           1. Lit tous les capteurs
           2. Execute le cycle auto-control des espaces
           3. Verifie les ecarts environnementaux vs stage
           4. Genere taches et suggestions
           5. Met a jour les lots recolte
        """
        self._load_managers()
        results = {
            "sensors": {},
            "auto_actions": [],
            "deviations": [],
            "tasks_created": [],
            "suggestions": [],
            "energy_status": {},
            "ts": datetime.now().isoformat(),
        }

        # 1. Lecture capteurs + auto-control
        if self.sm:
            try:
                results["sensors"] = self.sm.read_sensors()
                auto = self.sm.auto_control_cycle()
                results["auto_actions"] = auto["actions"]
            except Exception as e:
                log.warning("Erreur monitoring espaces", error=str(e))

        # 2. Recuperer suggestions lifecycle (inclut deviations capteurs)
        if self.lm:
            try:
                suggestions = self.lm.get_suggestions()
                results["suggestions"] = suggestions
                # Separer deviations environnementales
                results["deviations"] = [s for s in suggestions
                                         if s["type"] in (
                                             "temp_too_low", "temp_too_high",
                                             "soil_dry", "soil_wet",
                                             "light_low", "light_high",
                                             "humidity_low", "humidity_high")]
            except Exception as e:
                log.warning("Erreur suggestions lifecycle", error=str(e))

        # 3. Generer taches pour les deviations urgentes
        for dev in results["deviations"]:
            if dev.get("priority") in ("urgent", "high"):
                try:
                    task_title = dev["message"][:80]
                    existing = self.tm.search(query=task_title[:40],
                                              zone=dev.get("espace", ""))
                    if any(t["status"] in ("todo", "in_progress") for t in existing):
                        continue
                    t = self.tm.create(
                        title=task_title,
                        description=dev["message"],
                        categorie="plantation",
                        priorite=dev["priority"],
                        echeance=datetime.now().strftime("%Y-%m-%d"),
                        zone=dev.get("espace", ""),
                        plante=dev.get("product", ""),
                    )
                    results["tasks_created"].append(t)
                except Exception as e:
                    log.warning("Erreur creation tache dev", error=str(e))

        # 4. Generer taches depuis lifecycle (stages)
        if self.lm:
            try:
                tasks = self.lm.generate_tasks(force=False)
                results["tasks_created"].extend(tasks)
            except Exception as e:
                log.warning("Erreur generation taches lifecycle", error=str(e))

        # 5. Estimer rendements recolte
        if self.hm:
            try:
                self.hm.estimate_all()
                results["harvest_summary"] = self.hm.summary()
            except Exception as e:
                log.warning("Erreur estimation recolte", error=str(e))

        # 6. Verifier energie
        if self.em:
            try:
                self.em.run_cycle()
                results["energy_status"] = self.em.summary()
            except Exception as e:
                log.warning("Erreur monitoring energie", error=str(e))

        results["counts"] = {
            "deviations": len(results["deviations"]),
            "suggestions": len(results["suggestions"]),
            "tasks_created": len(results["tasks_created"]),
            "auto_actions": len(results["auto_actions"]),
        }
        return results

    # ── Rapport de Culture ──────────────────────────────────

    def culture_report(self, espace_id: str = None,
                       plantation_id: str = None) -> dict:
        """Rapport detaille sur une ou toutes les plantations actives."""
        self._load_managers()
        report = {
            "plantations": [],
            "sensors": {},
            "energy": {},
            "ts": datetime.now().isoformat(),
        }

        plantations = []
        if self.lm:
            all_pl = self.lm.list_plantations()
            if plantation_id:
                pl = self.lm.get_plantation(plantation_id)
                if pl:
                    plantations = [pl]
            elif espace_id:
                plantations = [p for p in all_pl if p["espace_id"] == espace_id]
            else:
                plantations = [p for p in all_pl if p["status"] == "active"]

        for pl in plantations:
            pl_report = dict(pl)
            # Ajouter info produit
            if self.lm:
                product = self.lm.get_product(pl["product_id"])
                if product:
                    day = pl.get("day_of_cycle", 0)
                    stage = None
                    for s in product.get("stages", []):
                        if s["day_start"] <= day <= s["day_end"]:
                            stage = s
                            break
                    pl_report["product"] = product
                    pl_report["current_stage"] = stage

            # Ajouter donnees capteurs de l'espace
            if self.sm and not espace_id:
                try:
                    sensors = self.sm.read_sensors(pl["espace_id"])
                    pl_report["sensors"] = sensors.get(pl["espace_id"], {})
                except Exception:
                    pass

            report["plantations"].append(pl_report)

        # Capteurs generaux
        if self.sm:
            try:
                report["sensors"] = self.sm.read_sensors(espace_id)
            except Exception:
                pass

        # Energie
        if self.em:
            try:
                report["energy"] = self.em.summary()
            except Exception:
                pass

        report["count"] = len(report["plantations"])
        return report

    # ── Suggestions Agregees ────────────────────────────────

    def all_suggestions(self) -> list[dict]:
        """Toutes les suggestions en provenance de tous les modules."""
        self._load_managers()
        all_s = []

        # Lifecycle suggestions (inclut deviations capteurs)
        if self.lm:
            try:
                all_s.extend(self.lm.get_suggestions())
            except Exception:
                pass

        # Harvest suggestions
        if self.hm:
            try:
                all_s.extend(self.hm.get_harvest_suggestions())
            except Exception:
                pass

        # Lifecycle stage transitions
        if self.lm:
            try:
                for pl in self.lm.list_plantations():
                    if pl["status"] != "active":
                        continue
                    product = self.lm.get_product(pl["product_id"])
                    if not product:
                        continue
                    day = pl.get("day_of_cycle", 0)
                    for s in product.get("stages", []):
                        if s["day_start"] <= day <= s["day_end"]:
                            jours_rest = max(0, s["day_end"] - day)
                            if jours_rest <= 3 and s["name"] not in ("recolte", "dormance"):
                                next_stages = [st for st in product["stages"]
                                               if st["day_start"] > s["day_end"]]
                                if next_stages:
                                    ns = next_stages[0]
                                    all_s.append({
                                        "type": "stage_transition",
                                        "product": product["label"],
                                        "plantation": pl["plantation_id"],
                                        "espace": pl["espace_id"],
                                        "from_stage": s["name"],
                                        "to_stage": ns["name"],
                                        "message": (f"{product['label']}: "
                                                   f"Transition {s['name']} -> {ns['name']}"
                                                   f" dans {jours_rest} jours"),
                                        "priority": "medium",
                                    })
                            break
            except Exception:
                pass

        # Trier par priorite
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        all_s.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 4))
        return all_s

    # ── Resume Global ───────────────────────────────────────

    def global_status(self) -> dict:
        """Etat global de la production agricole."""
        self._load_managers()
        status = {}

        if self.lm:
            status["lifecycle"] = self.lm.summary()

        if self.sm:
            status["spaces"] = self.sm.summary()

        if self.hm:
            status["harvest"] = self.hm.summary()

        if self.em:
            try:
                status["energy"] = self.em.summary()
            except Exception:
                pass

        if self.gm:
            try:
                status["geothermal"] = self.gm.summary()
            except Exception:
                pass

        status["suggestions"] = len(self.all_suggestions())
        return status
