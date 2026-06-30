# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""PixelOS GeothermalControl - Regulation thermique des sols agricoles.

Architecture:
  PIDController  →  Algorithme de regulation PID
  HardwareProbe  →  Abstraction capteurs (I2C/GPIO + simulation)
  GeothermalZone →  Zone avec sonde, vanne, PID, historique
  GeothermalManager → Orchestrateur multi-zones
"""

import json
import time
import math
import structlog
from pathlib import Path
from datetime import datetime, date
from typing import Any

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "geothermal"


# ── PID Controller ──────────────────────────────────────────

class PIDController:
    """Controleur PID discret avec anti-windup et saturation.

    u(t) = Kp * e(t) + Ki * ∫e(t)dt + Kd * de(t)/dt
    """

    def __init__(self, Kp: float = 2.0, Ki: float = 0.5, Kd: float = 0.1,
                 setpoint: float = 20.0, output_min: float = 0.0,
                 output_max: float = 100.0):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = setpoint
        self.output_min = output_min
        self.output_max = output_max
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_time = None

    def reset(self):
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_time = None

    def compute(self, current_value: float, dt: float = None) -> float:
        now = time.time()
        if dt is None:
            if self._last_time is None:
                dt = 1.0
            else:
                dt = max(0.01, now - self._last_time)
        self._last_time = now

        error = self.setpoint - current_value

        # Proportionnel
        P = self.Kp * error

        # Integral avec anti-windup
        self._integral += error * dt
        I = self.Ki * self._integral

        # Derive
        D = self.Kd * (error - self._prev_error) / dt if dt > 0 else 0.0
        self._prev_error = error

        # Saturation
        output = P + I + D
        output = max(self.output_min, min(self.output_max, output))

        # Anti-windup: arreter integration si sature
        if output <= self.output_min or output >= self.output_max:
            self._integral -= error * dt

        return round(output, 1)

    def tune_aggresive(self):
        self.Kp = 4.0
        self.Ki = 1.0
        self.Kd = 0.5

    def tune_conservative(self):
        self.Kp = 1.0
        self.Ki = 0.2
        self.Kd = 0.05

    def to_dict(self) -> dict:
        return {
            "Kp": self.Kp, "Ki": self.Ki, "Kd": self.Kd,
            "setpoint": self.setpoint,
            "output_min": self.output_min, "output_max": self.output_max,
        }


# ── Hardware Abstraction ────────────────────────────────────

class HardwareProbe:
    """Abstraction pour les sondes de temperature/humidite sol.

    En mode simulation, retourne des valeurs aleatoires proches
    de la cible pour tester le PID sans materiel reel.
    """

    def __init__(self, zone_id: str, probe_type: str = "ds18b20",
                 bus: str = "simulation", addr: str = None):
        self.zone_id = zone_id
        self.probe_type = probe_type
        self.bus = bus
        self.addr = addr
        self._sim_temp = 18.0
        self._sim_hum = 45.0

    def read_temperature(self) -> float:
        if self.bus == "simulation":
            self._sim_temp += (20.0 - self._sim_temp) * 0.05
            self._sim_temp += (hash(str(time.time())) % 20 - 10) * 0.05
            return round(self._sim_temp, 2)
        if self.bus == "i2c":
            try:
                import board
                import adafruit_ds18x20
                sensor = adafruit_ds18x20.DS18X20(board.D18)
                return round(sensor.temperature, 2)
            except Exception as e:
                log.warning("Erreur sonde I2C", zone=self.zone_id, error=str(e))
                return -1
        if self.bus == "gpio":
            try:
                import RPi.GPIO as GPIO
                GPIO.setmode(GPIO.BCM)
                pin = int(self.addr or 4)
                raw = GPIO.input(pin)
                return round(20.0 + raw * 0.5, 2)
            except Exception as e:
                log.warning("Erreur sonde GPIO", zone=self.zone_id, error=str(e))
                return -1
        return -1

    def read_humidity(self) -> float:
        if self.bus == "simulation":
            self._sim_hum += (50.0 - self._sim_hum) * 0.03
            self._sim_hum += (hash(str(time.time() * 2)) % 10 - 5) * 0.1
            return round(self._sim_hum, 1)
        return self.read_temperature() * 2.5  # Approximation simple

    def to_dict(self) -> dict:
        return {
            "zone": self.zone_id,
            "type": self.probe_type,
            "bus": self.bus,
            "addr": self.addr,
        }


# ── Vanne (Valve) ───────────────────────────────────────────

class HeatingValve:
    """Vanne de chauffage pilotee par PWM (0-100%)."""

    def __init__(self, zone_id: str, valve_id: str, pin: int = None):
        self.zone_id = zone_id
        self.valve_id = valve_id
        self.pin = pin
        self.position = 0.0
        self._last_command = 0.0

    def open(self, percent: float = 100.0):
        pct = max(0.0, min(100.0, percent))
        self.position = pct
        self._last_command = time.time()
        if self.pin is not None:
            try:
                import RPi.GPIO as GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.pin, GPIO.OUT)
                pwm = GPIO.PWM(self.pin, 50)
                pwm.start(pct / 100.0 * 100.0)
            except Exception as e:
                log.warning("Erreur PWM vanne", zone=self.zone_id, error=str(e))
        log.info("Vanne ouverte", zone=self.zone_id, valve=self.valve_id, percent=pct)

    def close(self):
        self.position = 0.0
        if self.pin is not None:
            try:
                import RPi.GPIO as GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.pin, GPIO.OUT)
                GPIO.output(self.pin, False)
            except Exception:
                pass
        log.info("Vanne fermee", zone=self.zone_id, valve=self.valve_id)

    def to_dict(self) -> dict:
        return {
            "zone": self.zone_id,
            "valve_id": self.valve_id,
            "pin": self.pin,
            "position": self.position,
            "last_command": self._last_command,
        }


# ── Zone Geothermal ─────────────────────────────────────────

MODE_HYBRID = "hybrid"
MODE_HEATING = "heating"
MODE_COOLING = "cooling"
MODE_IDLE = "idle"


class GeothermalZone:
    """Zone geothermique avec son PID, sa sonde, sa vanne et son historique."""

    def __init__(self, zone_id: str, label: str = "",
                 target_temp: float = 20.0, hysteresis: float = 1.0,
                 Kp: float = 2.0, Ki: float = 0.5, Kd: float = 0.1):
        self.zone_id = zone_id
        self.label = label or zone_id
        self.pid = PIDController(Kp=Kp, Ki=Ki, Kd=Kd, setpoint=target_temp)
        self.hysteresis = hysteresis
        self.probe = HardwareProbe(zone_id)
        self.valve = HeatingValve(zone_id, f"valve_{zone_id}")
        self.mode = MODE_IDLE
        self.current_temp = target_temp
        self.current_humidity = 50.0
        self.heating_active = False
        self.history = []
        self.max_history = 1440  # 24h a 1 mesure/min
        self.enabled = True

    def update(self) -> dict:
        if not self.enabled:
            return self.snapshot()

        self.current_temp = self.probe.read_temperature()
        self.current_humidity = self.probe.read_humidity()

        if self.current_temp < 0:
            self.mode = MODE_IDLE
            self.heating_active = False
            return self.snapshot()

        # Mode hybride : chauffe si T < cible - hysteresis, refroidit si T > cible + hysteresis
        target = self.pid.setpoint
        if self.current_temp < target - self.hysteresis:
            self.mode = MODE_HEATING
            output = self.pid.compute(self.current_temp)
            self.valve.open(output)
            self.heating_active = output > 5.0
        elif self.current_temp > target + self.hysteresis:
            self.mode = MODE_COOLING
            self.valve.close()
            self.heating_active = False
        else:
            self.mode = MODE_IDLE
            self.heating_active = False

        self._log_history()
        return self.snapshot()

    def _log_history(self):
        self.history.append({
            "ts": datetime.now().isoformat(),
            "temp": self.current_temp,
            "humidity": self.current_humidity,
            "valve": self.valve.position,
            "target": self.pid.setpoint,
            "mode": self.mode,
        })
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def snapshot(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "label": self.label,
            "current_temp": self.current_temp,
            "current_humidity": self.current_humidity,
            "target_temp": self.pid.setpoint,
            "hysteresis": self.hysteresis,
            "valve_position": self.valve.position,
            "heating_active": self.heating_active,
            "mode": self.mode,
            "pid": self.pid.to_dict(),
            "enabled": self.enabled,
            "history_len": len(self.history),
        }

    def to_dict(self) -> dict:
        d = self.snapshot()
        d["probe"] = self.probe.to_dict()
        d["valve"] = self.valve.to_dict()
        d["history"] = self.history[-60:]  # derniere heure
        return d


# ── Geothermal Manager ──────────────────────────────────────

DEFAULT_ZONES = [
    {"id": "serre_a", "label": "Serre A", "target_temp": 22.0, "hysteresis": 1.5},
    {"id": "serre_b", "label": "Serre B", "target_temp": 18.0, "hysteresis": 1.0},
    {"id": "plein_champ", "label": "Plein Champ", "target_temp": 15.0, "hysteresis": 2.0},
    {"id": "pépiniere", "label": "Pepiniere", "target_temp": 25.0, "hysteresis": 0.5},
]


class GeothermalManager:
    """Orchestrateur du controle geothermique multi-zones."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.zones: dict[str, GeothermalZone] = {}
        self._load_config()

    def _config_path(self):
        return DATA_DIR / "config.json"

    def _load_config(self):
        configs = DEFAULT_ZONES
        path = self._config_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    configs = json.load(f)
            except Exception as e:
                log.warning("Erreur chargement config geothermal", error=str(e))
        self._init_zones(configs)
        self._save_config()

    def _save_config(self):
        configs = []
        for z in self.zones.values():
            configs.append({
                "id": z.zone_id,
                "label": z.label,
                "target_temp": z.pid.setpoint,
                "hysteresis": z.hysteresis,
                "Kp": z.pid.Kp, "Ki": z.pid.Ki, "Kd": z.pid.Kd,
                "enabled": z.enabled,
                "probe_type": z.probe.probe_type,
                "probe_bus": z.probe.bus,
                "valve_pin": z.valve.pin,
            })
        with open(self._config_path(), "w", encoding="utf-8") as f:
            json.dump(configs, f, indent=2, ensure_ascii=False)

    def _init_zones(self, configs: list[dict]):
        self.zones = {}
        for c in configs:
            z = GeothermalZone(
                zone_id=c["id"],
                label=c.get("label", c["id"]),
                target_temp=c.get("target_temp", 20.0),
                hysteresis=c.get("hysteresis", 1.0),
                Kp=c.get("Kp", 2.0), Ki=c.get("Ki", 0.5), Kd=c.get("Kd", 0.1),
            )
            z.enabled = c.get("enabled", True)
            if "probe_bus" in c:
                z.probe = HardwareProbe(c["id"], c.get("probe_type", "ds18b20"),
                                        c.get("probe_bus", "simulation"),
                                        c.get("probe_addr"))
            if "valve_pin" in c:
                z.valve = HeatingValve(c["id"], f"valve_{c['id']}", c.get("valve_pin"))
            self.zones[c["id"]] = z

    # ── API Publique ────────────────────────────────────────

    def list_zones(self) -> list[dict]:
        return [z.snapshot() for z in self.zones.values()]

    def get_zone(self, zone_id: str) -> dict | None:
        z = self.zones.get(zone_id)
        return z.to_dict() if z else None

    def update_zone(self, zone_id: str, **kwargs) -> dict | None:
        z = self.zones.get(zone_id)
        if not z:
            return None
        if "target_temp" in kwargs and kwargs["target_temp"] is not None:
            z.pid.setpoint = float(kwargs["target_temp"])
        if "hysteresis" in kwargs and kwargs["hysteresis"] is not None:
            z.hysteresis = float(kwargs["hysteresis"])
        if "Kp" in kwargs and kwargs["Kp"] is not None:
            z.pid.Kp = float(kwargs["Kp"])
        if "Ki" in kwargs and kwargs["Ki"] is not None:
            z.pid.Ki = float(kwargs["Ki"])
        if "Kd" in kwargs and kwargs["Kd"] is not None:
            z.pid.Kd = float(kwargs["Kd"])
        if "enabled" in kwargs and kwargs["enabled"] is not None:
            z.enabled = bool(kwargs["enabled"])
        if "label" in kwargs and kwargs["label"] is not None:
            z.label = kwargs["label"]
        self._save_config()
        return z.snapshot()

    def run_cycle(self) -> dict:
        """Execute un cycle de regulation pour toutes les zones."""
        results = {}
        for zid, z in self.zones.items():
            results[zid] = z.update()
        return results

    def get_history(self, zone_id: str = None, limit: int = 120) -> dict:
        if zone_id:
            z = self.zones.get(zone_id)
            return {zone_id: z.history[-limit:] if z else []}
        return {zid: z.history[-limit:] for zid, z in self.zones.items()}

    def summary(self) -> dict:
        zones = self.list_zones()
        heating = sum(1 for z in zones if z["heating_active"])
        total = len(zones)
        avg_temp = sum(z["current_temp"] for z in zones) / total if total else 0
        return {
            "total_zones": total,
            "heating_active": heating,
            "cooling_active": sum(1 for z in zones if z["mode"] == MODE_COOLING),
            "idle": sum(1 for z in zones if z["mode"] == MODE_IDLE),
            "avg_temp": round(avg_temp, 1),
            "enabled": sum(1 for z in zones if z["enabled"]),
        }

    def check_anomalies(self) -> list[dict]:
        """Detecte les anomalies (sonde HS, chauffage inefficace, etc.)."""
        anomalies = []
        for zid, z in self.zones.items():
            sn = z.snapshot()
            # Sonde HS
            if sn["current_temp"] < 0:
                anomalies.append({
                    "zone": zid, "type": "probe_failure",
                    "severity": "critical",
                    "message": f"Sonde HS sur {z.label} (T={sn['current_temp']})",
                })
            # Chauffage inefficace
            if sn["heating_active"] and sn["valve_position"] > 50:
                recent = [h for h in z.history[-10:] if h["mode"] == MODE_HEATING]
                if len(recent) >= 5:
                    trend = recent[-1]["temp"] - recent[0]["temp"]
                    if trend < 0.5:
                        anomalies.append({
                            "zone": zid, "type": "heating_inefficient",
                            "severity": "warning",
                            "message": f"Chauffage inefficace sur {z.label}: "
                                       f"vanne a {sn['valve_position']}% mais T={sn['current_temp']}C",
                        })
            # Temp anormale
            if z.enabled and abs(sn["current_temp"] - z.pid.setpoint) > 5:
                anomalies.append({
                    "zone": zid, "type": "temp_abnormal",
                    "severity": "warning",
                    "message": f"Temperature anormale sur {z.label}: "
                               f"{sn['current_temp']}C (cible {z.pid.setpoint}C)",
                })
        return anomalies

    def auto_create_tasks(self) -> list[dict]:
        """Cree automatiquement des taches TaskManager pour les anomalies."""
        from core.tasks import TaskManager
        tm = TaskManager()
        created = []
        for anomaly in self.check_anomalies():
            if anomaly["severity"] == "critical":
                t = tm.create(
                    title=anomaly["message"][:80],
                    description=anomaly["message"],
                    categorie="maintenance",
                    priorite="urgent",
                    zone=anomaly["zone"],
                )
                created.append(t)
                log.info("Tache creee depuis anomalie geothermal",
                         zone=anomaly["zone"], type=anomaly["type"])
        return created
