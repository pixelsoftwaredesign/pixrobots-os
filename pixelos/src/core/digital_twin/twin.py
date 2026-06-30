#!/usr/bin/env python3
"""
Digital Twin — Jumeau numérique temps réel.

Miroir logiciel de chaque équipement/culture:
- Synchronisation des capteurs
- Simulation de scénarios (prédictif)
- Historique de vie complet
- Détection de dérive
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

TWIN_DIR = "/var/db/pixelos/digital_twin"


class DigitalTwin:
    def __init__(self):
        self._ensure_dirs()
        self._load_state()

    def _ensure_dirs(self):
        Path(TWIN_DIR).mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        return str(Path(TWIN_DIR) / name)

    def _load_state(self):
        path = self._path("twins.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.twins = json.load(f)
                return
            except Exception:
                pass
        self.twins = {}

    def _save_state(self):
        with open(self._path("twins.json"), "w") as f:
            json.dump(self.twins, f, indent=2)

    # ── Lifecycle ──────────────────────────────────────────

    def create(self, name: str, entity_type: str = "equipment",
               metadata: dict = None) -> dict:
        twin_id = f"{entity_type}_{name.lower().replace(' ', '_')}"
        if twin_id in self.twins:
            return {"status": "error", "reason": "twin already exists"}

        twin = {
            "id": twin_id,
            "name": name,
            "type": entity_type,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "last_sync": datetime.now().isoformat(),
            "metadata": metadata or {},
            "sensors": {},
            "actuators": {},
            "state": {},
            "history": [],
            "alerts": [],
        }
        self.twins[twin_id] = twin
        self._save_state()
        return {"status": "created", "twin": twin}

    def delete(self, twin_id: str) -> dict:
        if twin_id not in self.twins:
            return {"status": "error", "reason": "not found"}
        del self.twins[twin_id]
        self._save_state()
        return {"status": "deleted"}

    # ── Synchronization ────────────────────────────────────

    def sync_sensor(self, twin_id: str, sensor_id: str, value: float,
                    unit: str = "") -> dict:
        twin = self.twins.get(twin_id)
        if not twin:
            return {"status": "error", "reason": "twin not found"}

        ts = datetime.now().isoformat()
        twin["sensors"][sensor_id] = {
            "value": value,
            "unit": unit,
            "ts": ts,
        }
        twin["last_sync"] = ts
        twin["history"].append({
            "type": "sensor",
            "sensor_id": sensor_id,
            "value": value,
            "unit": unit,
            "ts": ts,
        })
        twin["history"] = twin["history"][-1000:]
        self._check_alerts(twin, sensor_id, value)
        self._save_state()
        return {"status": "synced", "twin_id": twin_id, "sensor_id": sensor_id}

    def sync_actuator(self, twin_id: str, actuator_id: str,
                      state: str) -> dict:
        twin = self.twins.get(twin_id)
        if not twin:
            return {"status": "error", "reason": "twin not found"}

        ts = datetime.now().isoformat()
        twin["actuators"][actuator_id] = {"state": state, "ts": ts}
        twin["last_sync"] = ts
        twin["history"].append({
            "type": "actuator",
            "actuator_id": actuator_id,
            "state": state,
            "ts": ts,
        })
        twin["history"] = twin["history"][-1000:]
        self._save_state()
        return {"status": "synced", "twin_id": twin_id, "actuator_id": actuator_id}

    def sync_state(self, twin_id: str, state: dict) -> dict:
        twin = self.twins.get(twin_id)
        if not twin:
            return {"status": "error", "reason": "twin not found"}
        twin["state"].update(state)
        twin["last_sync"] = datetime.now().isoformat()
        self._save_state()
        return {"status": "synced"}

    # ── Alerts ─────────────────────────────────────────────

    def _check_alerts(self, twin: dict, sensor_id: str, value: float):
        thresholds = twin.get("metadata", {}).get("thresholds", {})
        if sensor_id in thresholds:
            t = thresholds[sensor_id]
            if value < t.get("min", -float("inf")):
                self._add_alert(twin, sensor_id, f"below minimum ({t['min']})")
            elif value > t.get("max", float("inf")):
                self._add_alert(twin, sensor_id, f"above maximum ({t['max']})")

    def _add_alert(self, twin: dict, sensor_id: str, message: str):
        alert = {
            "sensor_id": sensor_id,
            "message": message,
            "ts": datetime.now().isoformat(),
        }
        twin["alerts"].append(alert)
        twin["alerts"] = twin["alerts"][-100:]

    def set_threshold(self, twin_id: str, sensor_id: str,
                      min_val: float = None, max_val: float = None) -> dict:
        twin = self.twins.get(twin_id)
        if not twin:
            return {"status": "error", "reason": "twin not found"}
        if "thresholds" not in twin.get("metadata", {}):
            twin.setdefault("metadata", {})["thresholds"] = {}
        if min_val is not None:
            twin["metadata"]["thresholds"][sensor_id] = {
                **twin["metadata"]["thresholds"].get(sensor_id, {}), "min": min_val}
        if max_val is not None:
            twin["metadata"]["thresholds"][sensor_id] = {
                **twin["metadata"]["thresholds"].get(sensor_id, {}), "max": max_val}
        self._save_state()
        return {"status": "threshold_set"}

    # ── Simulation ─────────────────────────────────────────

    def simulate(self, twin_id: str, scenario: str = "normal",
                 params: dict = None) -> dict:
        twin = self.twins.get(twin_id)
        if not twin:
            return {"status": "error", "reason": "twin not found"}

        params = params or {}
        base_temp = params.get("base_temp", 25.0)
        base_humidity = params.get("base_humidity", 60.0)

        if scenario == "heatwave":
            temp = base_temp + 12 + (hash(str(time.time())) % 5)
            humidity = base_humidity - 20
        elif scenario == "frost":
            temp = -2 + (hash(str(time.time())) % 5)
            humidity = base_humidity + 10
        elif scenario == "optimal":
            temp = base_temp
            humidity = base_humidity
        else:
            temp = base_temp + (hash(str(time.time())) % 6 - 3)
            humidity = base_humidity + (hash(str(time.time())) % 10 - 5)

        self.sync_sensor(twin_id, "temp_simulated", temp, "°C")
        self.sync_sensor(twin_id, "humidity_simulated", humidity, "%")

        return {
            "status": "simulated",
            "scenario": scenario,
            "result": {"temperature": temp, "humidity": humidity},
        }

    # ── Health ─────────────────────────────────────────────

    def health_check(self, twin_id: str) -> dict:
        twin = self.twins.get(twin_id)
        if not twin:
            return {"status": "error", "reason": "not found"}

        now = time.time()
        last = datetime.fromisoformat(twin["last_sync"]).timestamp()
        drift_hours = (now - last) / 3600

        health = "healthy" if drift_hours < 1 else "degraded" if drift_hours < 24 else "stale"
        return {
            "twin_id": twin_id,
            "health": health,
            "drift_hours": round(drift_hours, 2),
            "last_sync": twin["last_sync"],
            "sensors_online": len(twin["sensors"]),
            "alerts_count": len(twin["alerts"]),
        }

    # ── List ───────────────────────────────────────────────

    def list(self) -> dict:
        return {tid: {
            "id": t["id"],
            "name": t["name"],
            "type": t["type"],
            "status": t["status"],
            "sensors_count": len(t["sensors"]),
            "last_sync": t["last_sync"],
            "alerts_count": len(t["alerts"]),
        } for tid, t in self.twins.items()}

    def get(self, twin_id: str) -> Optional[dict]:
        return self.twins.get(twin_id)

    def history(self, twin_id: str, limit: int = 100) -> list:
        twin = self.twins.get(twin_id)
        if not twin:
            return []
        return twin["history"][-limit:]

    # ── Stats ──────────────────────────────────────────────

    def stats(self) -> dict:
        types = {}
        statuses = {}
        for t in self.twins.values():
            types[t["type"]] = types.get(t["type"], 0) + 1
            statuses[t["status"]] = statuses.get(t["status"], 0) + 1
        return {
            "total": len(self.twins),
            "by_type": types,
            "by_status": statuses,
            "total_sensors": sum(len(t["sensors"]) for t in self.twins.values()),
            "total_alerts": sum(len(t["alerts"]) for t in self.twins.values()),
        }
