#!/usr/bin/env python3
"""
PixelOS Agent - Daemon de gestion et monitoring déployé sur chaque machine.
Collecte les métriques, exécute les commandes, et maintient le heartbeat.

Installation:
  - Sur OpenBSD: rcctl enable pixelos_agent
  - Sur Raspberry Pi: systemctl enable pixelos-agent
"""

import os
import sys
import json
import time
import signal
import structlog
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.config import PixelOSConfig
from core.mqtt import PixelOSMQTT


log = structlog.get_logger()


class Agent:
    """Agent PixelOS déployé sur chaque nœud du système."""

    def __init__(self, node_id: str, role: str, boot: bool = False):
        self.node_id = node_id
        self.role = role
        self.boot = boot
        self.config = PixelOSConfig()
        self.mqtt = PixelOSMQTT(
            broker=self.config.get("mqtt.broker", "localhost"),
            port=self.config.get("mqtt.port", 1883),
            client_id=f"pixelos-agent-{node_id}",
        )
        self.running = True
        self._interval = self.config.get("monitoring.poll_interval", 10)
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

        # Auto-détection du rôle si non spécifié
        if self.role == "unknown":
            self._detect_role()

        # Composants intégrés
        self._collector = None
        self._edge_inference = None
        self._rl_controllers: dict[str, any] = {}
        self._training_scheduler = None

    def _stop(self, *args):
        self.running = False
        if self._collector:
            try:
                self._collector.stop()
            except Exception:
                pass

    def start(self) -> None:
        log.info("Agent démarré", node=self.node_id, role=self.role,
                 boot=self.boot)

        # Démarrage automatique des services au boot
        if self.boot or self.role == "server":
            self._startup_services()

        self.mqtt.connect()

        # Souscription aux commandes
        self.mqtt.subscribe(f"pixelos/agent/{self.node_id}/cmd/#",
                            self._on_command)
        self.mqtt.subscribe("pixelos/agent/all/cmd/#", self._on_command)

        # Démarrage collecteur asynchrone MQTT
        self._start_collector()

        # Chargement du moteur ONNX edge
        self._init_edge_inference()

        while self.running:
            try:
                # Collecte métriques
                metrics = self._collect_metrics()

                # Heartbeat
                self.mqtt.publish(f"pixelos/agent/{self.node_id}/heartbeat", {
                    "node": self.node_id,
                    "role": self.role,
                    "ts": datetime.now().isoformat(),
                    "metrics": metrics,
                })

                # Vérification alertes locales
                self._check_alerts(metrics)

                # Inférence edge à chaque cycle
                self._run_edge_inference()

                # Surveillance (toutes les 5 minutes)
                if int(time.time()) % 300 < self._interval:
                    self._monitor_tasks()
                    self._monitor_geothermal()
                    self._monitor_energy()
                    self._monitor_lifecycle()
                    self._monitor_harvest()
                    self._monitor_cultivation()
                    self._monitor_ml()
                    self._monitor_lab()
                    self._monitor_rl()
                    self._monitor_rl_reward()
                    self._monitor_discovery()
                    self._monitor_production()

                time.sleep(self._interval)

            except Exception as e:
                log.error("Erreur agent", error=str(e))
                time.sleep(5)

    def _collect_metrics(self) -> dict[str, Any]:
        metrics = {
            "cpu": self._get_cpu(),
            "memory": self._get_memory(),
            "disk": self._get_disk(),
            "uptime": self._get_uptime(),
            "processes": self._get_processes(),
        }

        # Métriques spécifiques au rôle
        if self.role == "openbsd":
            metrics.update(self._get_openbsd_metrics())
        elif self.role == "rpi":
            metrics.update(self._get_rpi_metrics())
        elif self.role == "gateway":
            metrics.update(self._get_gateway_metrics())

        return metrics

    def _get_cpu(self) -> dict:
        try:
            import psutil
            return {
                "percent": psutil.cpu_percent(interval=1),
                "count": psutil.cpu_count(),
                "load": os.getloadavg() if hasattr(os, "getloadavg") else [],
            }
        except:
            return {"percent": 0}

    def _get_memory(self) -> dict:
        try:
            import psutil
            m = psutil.virtual_memory()
            return {"total": m.total, "available": m.available,
                    "percent": m.percent}
        except:
            return {"percent": 0}

    def _get_disk(self) -> dict:
        try:
            import psutil
            d = psutil.disk_usage("/")
            return {"total": d.total, "used": d.used, "free": d.free,
                    "percent": d.percent}
        except:
            return {"percent": 0}

    def _get_uptime(self) -> float:
        try:
            with open("/proc/uptime") as f:
                return float(f.read().split()[0])
        except:
            return 0

    def _get_processes(self) -> list:
        try:
            import psutil
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    procs.append(p.info)
                except:
                    pass
            return sorted(procs, key=lambda x: x.get("cpu_percent", 0),
                          reverse=True)[:20]
        except:
            return []

    def _get_openbsd_metrics(self) -> dict:
        metrics = {}
        try:
            # Sensor temperature
            result = subprocess.run(
                ["sysctl", "hw.sensors"],
                capture_output=True, text=True, timeout=5)
            metrics["sensors"] = result.stdout.strip()
        except:
            pass

        try:
            # PF state count
            result = subprocess.run(
                ["pfctl", "-s", "info"],
                capture_output=True, text=True, timeout=5)
            for line in result.stdout.split("\n"):
                if "entries" in line:
                    metrics["pf_states"] = line.strip()
        except:
            pass

        try:
            # Watchdog status
            result = subprocess.run(
                ["sysctl", "-n", "hw.watchdog"],
                capture_output=True, text=True, timeout=5)
            metrics["watchdog"] = result.stdout.strip()
        except:
            pass

        return metrics

    def _get_rpi_metrics(self) -> dict:
        metrics = {}
        try:
            result = subprocess.run(
                ["vcgencmd", "measure_temp"],
                capture_output=True, text=True, timeout=5)
            metrics["cpu_temp"] = result.stdout.strip()
        except:
            pass
        return metrics

    def _get_gateway_metrics(self) -> dict:
        metrics = {}
        try:
            # Serial gateway health
            result = subprocess.run(
                ["pgrep", "-a", "serial_gateway"],
                capture_output=True, text=True, timeout=5)
            metrics["gateway_running"] = bool(result.stdout.strip())
        except:
            metrics["gateway_running"] = False
        return metrics

    def _check_alerts(self, metrics: dict) -> None:
        """Vérifie les conditions d'alerte locales."""
        if metrics.get("cpu", {}).get("percent", 0) > 90:
            self.mqtt.publish(f"pixelos/agent/{self.node_id}/alert", {
                "type": "cpu_high",
                "value": metrics["cpu"]["percent"],
                "severity": "warning",
            })

        disk = metrics.get("disk", {}).get("percent", 0)
        if disk > 90:
            self.mqtt.publish(f"pixelos/agent/{self.node_id}/alert", {
                "type": "disk_full",
                "value": disk,
                "severity": "critical",
            })

    def _monitor_energy(self) -> None:
        """Surveille l'etat energetique et publie sur MQTT."""
        try:
            from core.energy import EnergyManager
            em = EnergyManager()
            em.run_cycle()
            summary = em.summary()

            self.mqtt.publish("pixelos/energy/status", {
                "node": self.node_id,
                "solar_w": summary["current_solar_w"],
                "load_w": summary["current_load_w"],
                "battery_soc": summary["battery_soc"],
                "grid_available": summary["grid_available"],
                "ts": datetime.now().isoformat(),
            })

            # Alertes batterie faible
            if summary["battery_soc"] < 20:
                log.warning("Batterie faible", soc=summary["battery_soc"])
                self.mqtt.publish("pixelos/energy/alert", {
                    "node": self.node_id,
                    "type": "battery_low",
                    "soc": summary["battery_soc"],
                    "ts": datetime.now().isoformat(),
                })
            # Production nulle en jour (possible panne)
            h = datetime.now().hour
            if 9 <= h <= 17 and summary["current_solar_w"] < 10 and summary["irradiance"] > 0:
                log.warning("Production solaire anormalement basse")
                self.mqtt.publish("pixelos/energy/alert", {
                    "node": self.node_id,
                    "type": "solar_low",
                    "solar_w": summary["current_solar_w"],
                    "irradiance": summary["irradiance"],
                    "ts": datetime.now().isoformat(),
                })

        except ImportError:
            pass
        except Exception as e:
            log.warning("Erreur surveillance energie", error=str(e))

    def _monitor_geothermal(self) -> None:
        """Surveille les anomalies geothermie et cree taches si besoin."""
        try:
            from core.geothermal import GeothermalManager
            gm = GeothermalManager()
            anomalies = gm.check_anomalies()
            if anomalies:
                log.warning("Anomalies geothermiques detectees", count=len(anomalies))
                self.mqtt.publish("pixelos/geothermal/anomaly", {
                    "node": self.node_id,
                    "count": len(anomalies),
                    "anomalies": anomalies,
                    "ts": datetime.now().isoformat(),
                })
                from core.tasks import TaskManager
                tm = TaskManager()
                for a in anomalies:
                    zone_name = a["zone"]
                    tm.create_task(
                        title=f"Maintenance geothermie: {zone_name}",
                        description=a["message"],
                        priority="urgent" if a["severity"] == "critical" else "high",
                        category="maintenance",
                        zone=zone_name.split(" ")[-1].lower(),
                    )
                log.info("Taches creees depuis anomalies geothermie",
                         count=len(anomalies))
        except ImportError:
            pass
        except Exception as e:
            log.warning("Erreur surveillance geothermie", error=str(e))

    def _monitor_lifecycle(self) -> None:
        """Genere automatiquement les taches basees sur les cycles de vie."""
        try:
            from core.lifecycle import LifecycleManager
            lm = LifecycleManager()
            tasks = lm.generate_tasks(force=False)
            if tasks:
                log.info("Taches generees depuis cycles de vie", count=len(tasks))
                self.mqtt.publish("pixelos/lifecycle/tasks", {
                    "node": self.node_id,
                    "count": len(tasks),
                    "tasks": tasks[:5],
                    "ts": datetime.now().isoformat(),
                })

            suggestions = lm.get_suggestions()
            if suggestions:
                log.info("Suggestions lifecycle", count=len(suggestions))
                urgent = [s for s in suggestions if s.get("priority") == "high"]
                if urgent:
                    self.mqtt.publish("pixelos/lifecycle/suggestions", {
                        "node": self.node_id,
                        "count": len(suggestions),
                        "urgent": len(urgent),
                        "suggestions": urgent[:3],
                        "ts": datetime.now().isoformat(),
                    })
        except ImportError:
            pass
        except Exception as e:
            log.warning("Erreur surveillance lifecycle", error=str(e))

    def _monitor_harvest(self) -> None:
        """Suggestions de recolte et publication MQTT."""
        try:
            from core.harvest import HarvestManager
            hm = HarvestManager()
            hm.estimate_all()
            suggestions = hm.get_harvest_suggestions()
            if suggestions:
                log.info("Suggestions recolte", count=len(suggestions))
                self.mqtt.publish("pixelos/harvest/suggestions", {
                    "node": self.node_id,
                    "count": len(suggestions),
                    "suggestions": suggestions[:5],
                    "ts": datetime.now().isoformat(),
                })
                from core.tasks import TaskManager
                tm = TaskManager()
                for sg in suggestions:
                    tm.create_task(
                        title=sg["message"][:100],
                        description=(f"Recolte estimee: {sg['estimated_kg']}kg, "
                                     f"{sg['estimated_value']:.2f}EUR"),
                        priority="high",
                        category="recolte",
                        zone=sg["zone"],
                    )
                log.info("Taches recolte creees", count=len(suggestions))

            inv = hm.inventory.snapshot()
            self.mqtt.publish("pixelos/harvest/inventory", {
                "node": self.node_id,
                "inventory": inv,
                "ts": datetime.now().isoformat(),
            })
        except ImportError:
            pass
        except Exception as e:
            log.warning("Erreur surveillance recolte", error=str(e))

    def _monitor_cultivation(self) -> None:
        """Surveillance intelligente de la production agricole."""
        try:
            from core.cultivation import CultivationManager
            cm = CultivationManager()
            result = cm.smart_monitor()

            # Publier deviations sur MQTT
            if result["deviations"]:
                log.info("Deviations environnementales detectees",
                         count=len(result["deviations"]))
                self.mqtt.publish("pixelos/cultivation/deviations", {
                    "node": self.node_id,
                    "count": len(result["deviations"]),
                    "deviations": result["deviations"][:5],
                    "ts": datetime.now().isoformat(),
                })

            # Publier actions auto-control
            if result["auto_actions"]:
                log.info("Actions auto-controle", count=len(result["auto_actions"]))
                self.mqtt.publish("pixelos/cultivation/auto_control", {
                    "node": self.node_id,
                    "count": len(result["auto_actions"]),
                    "actions": result["auto_actions"],
                    "ts": datetime.now().isoformat(),
                })

            # Publier taches creees
            if result["tasks_created"]:
                log.info("Taches creees par cultivation",
                         count=len(result["tasks_created"]))
                self.mqtt.publish("pixelos/cultivation/tasks", {
                    "node": self.node_id,
                    "count": len(result["tasks_created"]),
                    "tasks": result["tasks_created"][:5],
                    "ts": datetime.now().isoformat(),
                })

        except ImportError:
            pass
        except Exception as e:
            log.warning("Erreur surveillance cultivation", error=str(e))

    def _monitor_ml(self) -> None:
        try:
            if self._training_scheduler is None:
                from agent.training_scheduler import TrainingScheduler
                self._training_scheduler = TrainingScheduler(self.mqtt)
            result = self._training_scheduler.check_and_run()
            if result["status"] != "skipped":
                log.info("Auto-retrain ML", **result)
                if self._edge_inference:
                    self._edge_inference.reload()
        except ImportError:
            pass
        except Exception as e:
            log.warning("Erreur surveillance ML", error=str(e))

    def _monitor_lab(self) -> None:
        """Surveille les analyses laboratoire et notifie les déviations."""
        try:
            from core.laboratory import LabManager
            lm = LabManager()
            stats = lm.stats()

            # Vérifier les échantillons en attente d'analyse
            pending = stats.get("samples_by_status", {}).get("collected", 0)
            if pending > 5:
                log.info("Échantillons en attente", count=pending)
                self.mqtt.publish("pixelos/lab/pending", {
                    "node": self.node_id,
                    "count": pending,
                    "ts": datetime.now().isoformat(),
                })

            # Vérifier la fertilité moyenne
            avg_f = stats.get("avg_fertility_index", 100)
            if avg_f < 30:
                self.mqtt.publish("pixelos/lab/alert", {
                    "node": self.node_id,
                    "type": "low_fertility",
                    "avg_fertility": avg_f,
                    "ts": datetime.now().isoformat(),
                })
                log.warning("Fertilité basse", avg_fertility=avg_f)

        except ImportError:
            pass
        except Exception as e:
            log.warning("Erreur surveillance lab", error=str(e))

    def _monitor_discovery(self) -> None:
        """Scan périodique des dispositifs IoT (Wi-Fi/BLE/Modbus)."""
        try:
            from core.discovery import device_manager
            stats = device_manager.stats()
            total = stats.get("total", 0)

            # Scan tous les 10 cycles (~50 min)
            cycle_key = f"discovery_scan_{self.node_id}"
            last_scan = getattr(self, cycle_key, 0)
            now = int(time.time())
            if now - last_scan > 3000:
                log.info("Scan dispositifs IoT...")
                results = device_manager.scan_all(timeout=20)
                setattr(self, cycle_key, now)
                new = results.get("total_new", 0)
                if new > 0:
                    self.mqtt.publish(f"pixelos/discovery/new", {
                        "node": self.node_id,
                        "new_devices": new,
                        "total": stats["total"],
                        "by_protocol": stats["by_protocol"],
                        "ts": datetime.now().isoformat(),
                    })
                    log.info("Nouveaux dispositifs découverts", count=new)

            # Publier statut périodique
            self.mqtt.publish(f"pixelos/discovery/status", {
                "node": self.node_id,
                "total_devices": total,
                "by_protocol": stats["by_protocol"],
                "by_status": stats["by_status"],
                "ts": datetime.now().isoformat(),
            })

        except ImportError:
            pass
        except Exception as e:
            log.warning("Erreur surveillance découverte", error=str(e))

    def _monitor_production(self) -> None:
        """Surveillance des préparations sol, plantations et plans de production."""
        try:
            from core.production import production_manager
            stats = production_manager.stats()

            self.mqtt.publish(f"pixelos/production/status", {
                "node": self.node_id,
                "stats": stats,
                "ts": datetime.now().isoformat(),
            })

            if stats.get("active_plans", 0) > 0:
                log.info("Production active", plans=stats["active_plans"])

        except ImportError:
            pass
        except Exception as e:
            log.warning("Erreur surveillance production", error=str(e))

    def _start_collector(self):
        """Demarre le collecteur asynchrone MQTT."""
        try:
            from agent.collector import MQTTCollector
            self._collector = MQTTCollector(self.mqtt)
            self._collector.start()
            log.info("Collecteur MQTT demarre")
        except Exception as e:
            log.warning("Echec demarrage collecteur MQTT", error=str(e))

    def _init_edge_inference(self):
        """Initialise le moteur d'inference ONNX edge."""
        try:
            from agent.edge_inference import EdgeInferenceEngine
            self._edge_inference = EdgeInferenceEngine(self.mqtt)
            result = self._edge_inference.load_model()
            log.info("Edge inference initialise", **result)
        except Exception as e:
            log.warning("Echec init edge inference", error=str(e))

    def _run_edge_inference(self):
        """Execute l'inference edge sur les donnees capteurs recentes."""
        if not self._edge_inference or not self._edge_inference.is_loaded():
            return
        try:
            from core.bgdatasys import bgdatasys
            latest = bgdatasys.query_sensors(hours=1, limit=1)
            if not latest:
                return
            sensor_data = {
                "humidite_sol": latest[0].get("value",
                                   latest[0].get("humidite_sol", 50)),
                "temperature": latest[0].get("temperature",
                                 latest[0].get("temp_air", 20)),
                "humidite": latest[0].get("humidite_air",
                              latest[0].get("humidity_air", 50)),
                "pression": latest[0].get("pression", 1013),
                "vent": latest[0].get("vent", latest[0].get("wind_speed", 0)),
            }
            space_id = latest[0].get("space_id", "serre_a")
            self._edge_inference.predict_and_act(space_id, sensor_data)
        except Exception as e:
            log.warning("Erreur edge inference", error=str(e))

    def _monitor_rl(self) -> None:
        """Boucle RL: choisit et applique une action d'irrigation/chauffage."""
        try:
            from core.rl_controller import RLController, ACTION_LABELS
            from core.bgdatasys import bgdatasys
            from core.config import PixelOSConfig

            config = PixelOSConfig()
            zones = config.get("rl.zones", ["serre_a"])

            for zone_id in zones:
                if zone_id not in self._rl_controllers:
                    self._rl_controllers[zone_id] = RLController(zone_id)

                rl = self._rl_controllers[zone_id]

                # Lire les dernieres mesures
                rows = bgdatasys.query_sensors(space=zone_id, hours=1, limit=5)
                if not rows:
                    continue

                avg_moisture = sum(
                    r.get("value", r.get("humidite_sol", 50)) for r in rows
                ) / len(rows)
                avg_temp = sum(
                    r.get("temperature", r.get("temp_air", 20)) for r in rows
                ) / len(rows)

                now = datetime.now()
                action = rl.choose_action(avg_moisture, avg_temp, now.hour)

                # Appliquer l'action via geothermal si disponible
                try:
                    from core.geothermal import GeothermalManager
                    gm = GeothermalManager()
                    zone_cfg = gm.get_zone(zone_id)
                    if zone_cfg:
                        current_valve = zone_cfg.get("valve_pct", 50)
                        current_setpoint = zone_cfg.get("target_temp", 20)
                        adjustments = rl.apply_action_to_geothermal(
                            action, current_valve, current_setpoint)
                        gm.update_zone(zone_id, **adjustments)
                except Exception:
                    pass

                # Publier l'action RL sur MQTT
                self.mqtt.publish(f"pixelos/{zone_id}/rl/action", {
                    "action": int(action),
                    "action_label": ACTION_LABELS[action],
                    "soil_moisture": round(avg_moisture, 1),
                    "temperature": round(avg_temp, 1),
                    "epsilon": round(rl.epsilon, 4),
                    "ts": now.isoformat(),
                })

        except ImportError:
            pass
        except Exception as e:
            log.warning("Erreur monitoring RL", error=str(e))

    def _monitor_rl_reward(self) -> None:
        """Calcule la recompense RL de l'heure precedente et met a jour Q-table."""
        try:
            from core.rl_controller import RLController
            from core.bgdatasys import bgdatasys
            from core.config import PixelOSConfig

            config = PixelOSConfig()
            zones = config.get("rl.zones", ["serre_a"])

            for zone_id in zones:
                if zone_id not in self._rl_controllers:
                    continue

                rl = self._rl_controllers[zone_id]

                # Lire les mesures de l'heure courante et precedente
                now = datetime.now()
                rows_now = bgdatasys.query_sensors(space=zone_id, hours=1, limit=5)
                rows_before = bgdatasys.query_sensors(space=zone_id, hours=2,
                                                      limit=5)

                if len(rows_now) < 1 or len(rows_before) < 1:
                    continue

                avg_moisture_now = sum(
                    r.get("value", r.get("humidite_sol", 50)) for r in rows_now
                ) / len(rows_now)
                avg_temp_now = sum(
                    r.get("temperature", r.get("temp_air", 20)) for r in rows_now
                ) / len(rows_now)

                avg_moisture_before = sum(
                    r.get("value", r.get("humidite_sol", 50)) for r in rows_before
                ) / len(rows_before)
                avg_temp_before = sum(
                    r.get("temperature", r.get("temp_air", 20)) for r in rows_before
                ) / len(rows_before)

                hour_now = now.hour
                hour_before = (now - timedelta(hours=1)).hour

                reward = rl.compute_reward(avg_moisture_now, avg_temp_now)

                # Chercher la derniere action effectuee dans l'historique
                history = rl.history(limit=1)
                if history:
                    last_entry = history[-1]
                    step_result = rl.step(
                        last_entry.get("prev_moisture", avg_moisture_before),
                        last_entry.get("prev_temp", avg_temp_before),
                        hour_before,
                        last_entry["action"],
                        avg_moisture_now, avg_temp_now, hour_now, reward,
                    )
                else:
                    step_result = rl.step(
                        avg_moisture_before, avg_temp_before, hour_before,
                        rl.choose_action(avg_moisture_before, avg_temp_before,
                                         hour_before),
                        avg_moisture_now, avg_temp_now, hour_now, reward,
                    )

                rl.log_transition({
                    "ts": now.isoformat(),
                    "zone": zone_id,
                    "prev_moisture": round(avg_moisture_before, 1),
                    "prev_temp": round(avg_temp_before, 1),
                    "moisture": round(avg_moisture_now, 1),
                    "temp": round(avg_temp_now, 1),
                    "reward": reward,
                    **step_result,
                })

                rl.save()

                self.mqtt.publish(f"pixelos/{zone_id}/rl/reward", {
                    "zone": zone_id,
                    "reward": round(reward, 2),
                    "epsilon": round(rl.epsilon, 4),
                    "states": rl.stats()["states"],
                    "td_error": step_result.get("td_error", 0),
                    "ts": now.isoformat(),
                })

        except ImportError:
            pass
        except Exception as e:
            log.warning("Erreur monitoring RL reward", error=str(e))

    def _monitor_tasks(self) -> None:
        """Surveille les taches urgentes/retard et notifie via MQTT."""
        try:
            from core.tasks import TaskManager
            tm = TaskManager()
            alerts = tm.alerts()
            if not alerts:
                return

            log.info("Alertes taches detectees", count=len(alerts))
            self.mqtt.publish("pixelos/tasks/alert", {
                "node": self.node_id,
                "count": len(alerts),
                "alerts": alerts,
                "ts": datetime.now().isoformat(),
            })

            # Allouer plus de ressources si tache urgente liee a une zone
            zones_urgentes = set(a["zone"] for a in alerts if a.get("zone"))
            if zones_urgentes:
                log.info("Zones avec taches urgentes", zones=list(zones_urgentes))
                try:
                    import psutil
                    proc = psutil.Process()
                    if hasattr(proc, "nice"):
                        proc.nice(psutil.HIGH_PRIORITY_CLASS
                                  if sys.platform == "win32" else -10)
                        log.info("Priorite agent augmentee pour taches urgentes")
                except Exception:
                    pass
        except ImportError:
            pass
        except Exception as e:
            log.warning("Erreur surveillance taches", error=str(e))

    def _on_command(self, topic: str, payload: dict) -> None:
        """Exécute une commande reçue via MQTT."""
        cmd = payload.get("cmd")
        log.info("Commande reçue", topic=topic, cmd=cmd)

        if cmd == "restart":
            log.warning("Redémarrage demandé")
            subprocess.run(["shutdown", "-r", "now"])
        elif cmd == "update":
            self._self_update()
        elif cmd == "ping":
            self.mqtt.publish(f"pixelos/agent/{self.node_id}/pong", {
                "ts": datetime.now().isoformat(),
            })
        elif cmd == "exec":
            script = payload.get("script", "")
            try:
                result = subprocess.run(
                    script, shell=True, capture_output=True,
                    text=True, timeout=30)
                self.mqtt.publish(
                    f"pixelos/agent/{self.node_id}/exec_result", {
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "returncode": result.returncode,
                    })
            except Exception as e:
                self.mqtt.publish(
                    f"pixelos/agent/{self.node_id}/exec_result", {
                        "error": str(e),
                    })

    def _startup_services(self) -> None:
        """Démarre tous les services PixelOS au boot."""
        try:
            from core.services import ServiceManager
            svc = ServiceManager()
            log.info("Démarrage automatique des services PixelOS...")
            result = svc.start()
            status = svc.health()
            log.info("Services démarrés",
                     running=status["running"],
                     total=status["total"])
            # Envoyer heartbeat de boot
            if hasattr(self, "mqtt") and self.mqtt:
                self.mqtt.publish("pixelos/server/boot", {
                    "node": self.node_id,
                    "services": status,
                    "ts": datetime.now().isoformat(),
                })
        except ImportError:
            log.warning("ServiceManager non disponible")
        except Exception as e:
            log.error("Échec démarrage services", error=str(e))

    def _detect_role(self) -> None:
        """Détecte automatiquement le rôle du nœud courant."""
        try:
            # Serveur PixelOS : Docker, ports clés ou config indiquent le serveur
            # 1. Docker est installé ?
            r = subprocess.run(["docker", "info"],
                               capture_output=True, text=True, timeout=5)
            has_docker = r.returncode == 0
        except:
            has_docker = False

        try:
            # 2. Ports des services PixelOS accessibles en local ?
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            has_mysql = s.connect_ex(("127.0.0.1", 3306)) == 0
            s.close()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            has_mongo = s.connect_ex(("127.0.0.1", 27017)) == 0
            s.close()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            has_mqtt = s.connect_ex(("127.0.0.1", 1883)) == 0
            s.close()
        except:
            has_mysql = has_mongo = has_mqtt = False

        # 3. Fichier de configuration PixelOS avec nodes ?
        has_config = False
        try:
            nodes = self.config.get("nodes", [])
            has_config = len(nodes) > 0
        except:
            pass

        # Logique de détection
        if has_docker and (has_mysql or has_mongo or has_mqtt):
            self.role = "server"
            hostname = os.uname()[1] if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "")
            if hostname and self.node_id == hostname:
                self.node_id = "pixelos-server"
            log.info("Rôle auto-détecté", role="server",
                     docker=has_docker, mysql=has_mysql,
                     mongo=has_mongo, mqtt=has_mqtt)
        elif has_config:
            self.role = "gateway"
            log.info("Rôle auto-détecté", role="gateway")
        elif has_docker:
            self.role = "server"
            log.info("Rôle auto-détecté", role="server (docker)")
        else:
            self.role = "node"
            log.info("Rôle auto-détecté", role="node")

    def _self_update(self) -> None:
        """Mise à jour de PixelOS via UpdateManager."""
        try:
            from core.updater import UpdateManager
            um = UpdateManager()
            mode = "git" if um._has_git() else "pip"
            result = um.update(mode=mode)
            status = "ok" if any(
                v.get("status") == "ok" for v in result.values()
                if isinstance(v, dict) and "status" in v
            ) else "error"
            self.mqtt.publish(f"pixelos/agent/{self.node_id}/update", {
                "ts": datetime.now().isoformat(),
                "version": result.get("new_version", "?"),
                "status": status,
                "mode": mode,
            })
            if status == "ok":
                log.info("Agent mis à jour, redémarrage...")
                os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            log.error("Échec mise à jour agent", error=str(e))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PixelOS Agent")
    parser.add_argument("--boot", action="store_true",
                        help="Mode boot: demarre tous les services au lancement")
    args = parser.parse_args()

    hostname = os.uname()[1] if hasattr(os, "uname") else os.environ.get("COMPUTERNAME", "pixelos")
    node_id = os.environ.get("PIXELOS_NODE_ID", hostname)
    role = os.environ.get("PIXELOS_ROLE", "unknown")

    agent = Agent(node_id, role, boot=args.boot)
    agent.start()
