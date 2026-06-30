"""collector — Collecteur asynchrone MQTT pour l'agent PixelOS.

Daemon dedie qui souscrit aux topics MQTT capteurs, bufferise les donnees
en memoire, et les ecrit en batch periodiquement dans bgdatasys
(TimescaleDB + MongoDB + Lake).

Topics souscrits:
  - pixelos/+/sensor/+   (mesures capteurs)
  - pixelos/+/event/+    (evenements: irrigation, vannes, alertes)
  - pixelos/+/status/+   (statuts equipements)
"""

import json
import queue
import structlog
import threading
from datetime import datetime, timezone
from typing import Optional, Callable

log = structlog.get_logger()

BATCH_INTERVAL = 5        # secondes entre chaque flush batch
BATCH_SIZE = 100           # taille maximale d'un batch
MAX_QUEUE_SIZE = 10000     # taille maximale de la file d'attente
FLUSH_TIMEOUT = 10         # timeout pour un flush


class MQTTCollector:
    """Collecteur asynchrone de donnees capteurs via MQTT.

    Usage:
        collector = MQTTCollector(mqtt_client)
        collector.start()
        # ... l'agent tourne ...
        collector.stop()
    """

    def __init__(self, mqtt_client, bgdatasys_instance=None,
                 batch_interval: int = BATCH_INTERVAL,
                 batch_size: int = BATCH_SIZE):
        self.mqtt = mqtt_client
        self._bgdatasys = bgdatasys_instance
        self.batch_interval = batch_interval
        self.batch_size = batch_size
        self._queue: queue.Queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._flush_event = threading.Event()
        self._stats = {
            "received": 0,
            "enqueued": 0,
            "flushed": 0,
            "errors": 0,
            "dropped": 0,
            "queue_size": 0,
        }
        self._lock = threading.Lock()

    @property
    def bgdatasys(self):
        if self._bgdatasys is None:
            from core.bgdatasys import bgdatasys
            self._bgdatasys = bgdatasys
        return self._bgdatasys

    def start(self):
        """Demarre le collecteur: souscrit aux topics et lance le thread de flush."""
        if self._running:
            return
        self._running = True

        self.mqtt.subscribe("pixelos/+/sensor/+", self._on_sensor)
        self.mqtt.subscribe("pixelos/+/event/+", self._on_event)
        self.mqtt.subscribe("pixelos/+/status/+", self._on_status)

        self._thread = threading.Thread(target=self._flush_loop, daemon=True,
                                         name="mqtt-collector")
        self._thread.start()
        log.info("Collecteur MQTT demarre",
                 batch_interval=self.batch_interval)

    def stop(self):
        """Arrete le collecteur et vide la queue."""
        self._running = False
        self._flush_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=FLUSH_TIMEOUT)
        self._flush()
        log.info("Collecteur MQTT arrete", stats=self._stats)

    def _on_sensor(self, topic: str, payload: dict):
        """Callback pour les mesures capteurs."""
        self._update_stats("received")
        try:
            parts = topic.split("/")
            space_id = parts[1] if len(parts) > 2 else "unknown"
            sensor_id = parts[3] if len(parts) > 3 else "unknown"

            record = {
                "space_id": space_id,
                "sensor_id": sensor_id,
                "timestamp": payload.get("ts", datetime.now(timezone.utc).isoformat()),
                "value": float(payload.get("value", payload.get("val", 0))),
                "unit": payload.get("unit", ""),
                "tags": payload.get("tags", {}),
                "topic": topic,
            }
            self._enqueue(record)
        except Exception as e:
            log.warning("Echec traitement message capteur",
                        topic=topic, error=str(e))
            self._update_stats("errors")

    def _on_event(self, topic: str, payload: dict):
        """Callback pour les evenements (irrigation, vannes, etc.)."""
        self._update_stats("received")
        try:
            parts = topic.split("/")
            space_id = parts[1] if len(parts) > 2 else "unknown"
            event_type = parts[3] if len(parts) > 3 else "unknown"

            record = {
                "event_type": event_type,
                "space_id": space_id,
                "timestamp": payload.get("ts", datetime.now(timezone.utc).isoformat()),
                "actor": payload.get("actor", "mqtt"),
                "value": str(payload.get("value", "")),
                "details": payload.get("details", payload),
                "topic": topic,
            }
            # Les evenements sont ecrits directement, pas par batch
            try:
                self.bgdatasys.write_event(
                    event_type=event_type,
                    space_id=space_id,
                    actor=payload.get("actor", "mqtt"),
                    value=str(payload.get("value", "")),
                    details=payload.get("details", payload),
                )
                self._update_stats("flushed")
            except Exception as e:
                log.warning("Echec ecriture evenement", error=str(e))
                self._update_stats("errors")
        except Exception as e:
            log.warning("Echec traitement evenement", topic=topic, error=str(e))
            self._update_stats("errors")

    def _on_status(self, topic: str, payload: dict):
        """Callback pour les statuts equipements (stockes comme evenements)."""
        self._update_stats("received")
        try:
            parts = topic.split("/")
            space_id = parts[1] if len(parts) > 2 else "unknown"
            status_type = parts[3] if len(parts) > 3 else "unknown"

            self.bgdatasys.write_event(
                event_type=f"status_{status_type}",
                space_id=space_id,
                actor="device",
                value=json.dumps(payload.get("status", {})),
                details=payload,
            )
            self._update_stats("flushed")
        except Exception as e:
            log.warning("Echec traitement status", topic=topic, error=str(e))
            self._update_stats("errors")

    def _enqueue(self, record: dict):
        """Ajoute un enregistrement dans la file d'attente."""
        try:
            self._queue.put_nowait(record)
            self._update_stats("enqueued")
        except queue.Full:
            log.warning("File d'attente pleine, message ignore")
            self._update_stats("dropped")

    def _flush(self):
        """Vide la queue et ecrit dans bgdatasys par batch."""
        batch = []
        while not self._queue.empty() and len(batch) < self.batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if not batch:
            return

        try:
            self.bgdatasys.tsdb.write_batch(batch)
            self._update_stats_by(len(batch), "flushed")
        except Exception as e:
            log.warning("Echec ecriture batch TimescaleDB, fallback individuel",
                        error=str(e), batch_size=len(batch))
            for rec in batch:
                try:
                    self.bgdatasys.write_measurement(
                        space_id=rec["space_id"],
                        sensor_id=rec["sensor_id"],
                        value=rec["value"],
                        unit=rec.get("unit", ""),
                        tags=rec.get("tags"),
                    )
                    self._update_stats("flushed")
                except Exception as e2:
                    log.warning("Echec ecriture mesure individuelle",
                                error=str(e2), sensor=rec.get("sensor_id"))
                    self._update_stats("errors")

    def _flush_loop(self):
        """Boucle de flush periodique dans un thread separe."""
        while self._running:
            self._flush_event.wait(timeout=self.batch_interval)
            self._flush_event.clear()
            try:
                self._flush()
            except Exception as e:
                log.error("Erreur dans flush loop", error=str(e))
                self._update_stats("errors")

    def force_flush(self):
        """Force un flush immediat."""
        self._flush_event.set()

    def _update_stats(self, key: str):
        with self._lock:
            self._stats[key] = self._stats.get(key, 0) + 1

    def _update_stats_by(self, count: int, key: str):
        with self._lock:
            self._stats[key] = self._stats.get(key, 0) + count

    def stats(self) -> dict:
        with self._lock:
            qsize = self._queue.qsize()
            return {
                **self._stats,
                "queue_size": qsize,
                "running": self._running,
            }

    def inject_measurement(self, space_id: str, sensor_id: str,
                            value: float, unit: str = "",
                            tags: dict = None):
        """Injection directe (utilisee par les capteurs simules locaux)."""
        record = {
            "space_id": space_id,
            "sensor_id": sensor_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "value": value,
            "unit": unit,
            "tags": tags or {},
            "topic": "local",
        }
        self._enqueue(record)
