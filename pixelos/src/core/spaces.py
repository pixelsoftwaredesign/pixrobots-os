# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""PixelOS SpaceManager - Gestion hierarchique des espaces agricoles.

Architecture:
  Sensor     →  Capteur (temperature, humidite, lumiere, NPK, pH, CO2,
                 irrigation_flow, soil_moisture)
  Control    →  Actionneur (vanne_irrigation, chauffage, eclairage, moteur,
                 pompe, brumisateur, extracteur)
  SubZone    →  Sous-zone productive avec produit/culture affectee
  Espace     →  Serre, Pepiniere, Champ, Verger avec capteurs + controles
  SpaceManager → Orchestrateur multi-espaces
"""

import json
import time
import math
import structlog
from pathlib import Path
from datetime import datetime
from typing import Any

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "spaces"

SENSOR_TYPES = ["temperature", "humidite_air", "humidite_sol", "lumiere",
                "npk", "ph", "co2", "irrigation_flow", "vent_vitesse",
                "pression", "uv_index"]
SENSOR_ICONS = {"temperature": "temp", "humidite_air": "humi",
                "humidite_sol": "soil", "lumiere": "sun",
                "npk": "npk", "ph": "ph", "co2": "co2",
                "irrigation_flow": "flow", "vent_vitesse": "wind",
                "pression": "pres", "uv_index": "uv"}
CONTROL_TYPES = ["vanne_irrigation", "vanne_pwm", "chauffage", "eclairage",
                 "pompe", "brumisateur", "extracteur", "ombriere", "volet"]
CONTROL_ICONS = {"vanne_irrigation": "irrig", "vanne_pwm": "valve",
                 "chauffage": "heat", "eclairage": "light",
                 "pompe": "pump", "brumisateur": "fog",
                 "extracteur": "fan", "ombriere": "shade", "volet": "vent"}
ESPACE_TYPES = ["serre", "pepiniere", "plein_champ", "verger", "jardin",
                "tunnel", "autre"]


# ── Sensor ───────────────────────────────────────────────────

class Sensor:
    """Capteur physique attache a un espace."""

    def __init__(self, sensor_id: str, type_: str = "temperature",
                 label: str = "", bus: str = "simulation",
                 addr: str = None, unit: str = "", interval: int = 60):
        self.sensor_id = sensor_id
        self.type = type_
        self.label = label or sensor_id
        self.bus = bus
        self.addr = addr
        self.unit = unit
        self.interval = interval
        self.value = 0.0
        self.raw_value = 0.0
        self.status = "unknown"
        self.last_read = None
        self._sim_base = 25.0
        self.enabled = True
        self.alarm_low = None
        self.alarm_high = None
        self.calibration_offset = 0.0

    def set_alarms(self, low: float = None, high: float = None):
        self.alarm_low = low
        self.alarm_high = high

    def read(self) -> float:
        if not self.enabled:
            return 0.0
        if self.bus == "simulation":
            self._sim_read()
        elif self.bus == "i2c":
            self._i2c_read()
        elif self.bus == "modbus":
            self._modbus_read()
        self.last_read = datetime.now().isoformat()
        self.value += self.calibration_offset
        self.value = round(self.value, 1)
        self.status = "ok"
        if self.alarm_low is not None and self.value < self.alarm_low:
            self.status = "alarm_low"
        if self.alarm_high is not None and self.value > self.alarm_high:
            self.status = "alarm_high"
        return self.value

    def _sim_read(self):
        t = time.time()
        if self.type == "temperature":
            self._sim_base += (22.0 - self._sim_base) * 0.02
            self._sim_base += (hash(str(t)) % 20 - 10) * 0.08
            self.value = round(self._sim_base, 1)
            self.unit = "C"
        elif self.type == "humidite_air":
            self._sim_base += (65.0 - self._sim_base) * 0.01
            self._sim_base += (hash(str(t * 2)) % 20 - 10) * 0.12
            self.value = round(max(0, min(100, self._sim_base)), 1)
            self.unit = "%"
        elif self.type == "humidite_sol":
            self._sim_base += (55.0 - self._sim_base) * 0.015
            self._sim_base += (hash(str(t * 3)) % 20 - 10) * 0.15
            self.value = round(max(0, min(100, self._sim_base)), 1)
            self.unit = "%"
        elif self.type == "lumiere":
            hour = datetime.now().hour + datetime.now().minute / 60.0
            if 6 < hour < 21:
                self.value = round(8000 * math.sin(math.pi * (hour - 6) / 15), 0)
                self.value += hash(str(t)) % 200 - 100
            else:
                self.value = round(max(0, 50 + (hash(str(t)) % 100)), 0)
            self.unit = "lux"
        elif self.type == "npk":
            # N: 0-100, P: 0-100, K: 0-100 simule
            self.value = round(50 + (hash(str(t * 3)) % 50), 0)
            self.unit = "mg/kg"
        elif self.type == "ph":
            self._sim_base += (6.5 - self._sim_base) * 0.01
            self._sim_base += (hash(str(t * 5)) % 10 - 5) * 0.02
            self.value = round(max(0, min(14, self._sim_base)), 1)
            self.unit = "ph"
        elif self.type == "co2":
            self._sim_base += (420 - self._sim_base) * 0.01
            self._sim_base += (hash(str(t * 7)) % 100 - 50) * 0.05
            self.value = round(max(300, self._sim_base), 0)
            self.unit = "ppm"
        elif self.type == "irrigation_flow":
            self._sim_base += (8.0 - self._sim_base) * 0.02
            self._sim_base += (hash(str(t * 11)) % 100 - 50) * 0.03
            self.value = round(max(0, self._sim_base), 1)
            self.unit = "L/min"
        elif self.type == "vent_vitesse":
            self.value = round(abs(hash(str(t * 13)) % 150) * 0.1, 1)
            self.unit = "km/h"
        elif self.type == "pression":
            self._sim_base += (1013 - self._sim_base) * 0.01
            self._sim_base += (hash(str(t * 17)) % 20 - 10) * 0.05
            self.value = round(self._sim_base, 1)
            self.unit = "hPa"
        elif self.type == "uv_index":
            hour = datetime.now().hour
            if 10 <= hour <= 16:
                self.value = round(4 + (hash(str(t * 19)) % 30) * 0.2, 1)
            else:
                self.value = round(max(0, (hash(str(t * 23)) % 10) * 0.2), 1)
            self.unit = "UV"
        else:
            self.value = round(50.0 + (hash(str(t)) % 100) * 0.1, 1)

    def _i2c_read(self):
        self.value = round(25.0 + (hash(str(time.time())) % 10 - 5) * 0.2, 1)

    def _modbus_read(self):
        self.value = round(50.0 + (hash(str(time.time())) % 100) * 0.1, 1)

    def snapshot(self) -> dict:
        return {
            "sensor_id": self.sensor_id,
            "type": self.type,
            "label": self.label,
            "bus": self.bus,
            "addr": self.addr,
            "unit": self.unit,
            "value": self.value,
            "status": self.status,
            "last_read": self.last_read,
            "enabled": self.enabled,
            "alarm_low": self.alarm_low,
            "alarm_high": self.alarm_high,
            "icon": SENSOR_ICONS.get(self.type, "sensor"),
        }


# ── Control ──────────────────────────────────────────────────

class Control:
    """Actionneur pilote par PixelOS pour les espaces."""

    def __init__(self, control_id: str, type_: str = "vanne_irrigation",
                 label: str = "", pin: int = None,
                 default_state: str = "off", auto_mode: bool = False):
        self.control_id = control_id
        self.type = type_
        self.label = label or control_id
        self.pin = pin
        self.state = default_state
        self.value = 0.0
        self.last_command = None
        self.enabled = True
        self.auto_mode = auto_mode
        self.auto_rules = {}

    def turn_on(self, value: float = 100.0):
        self.state = "on"
        self.value = max(0, min(100, value))
        self.last_command = datetime.now().isoformat()

    def turn_off(self):
        self.state = "off"
        self.value = 0.0
        self.last_command = datetime.now().isoformat()

    def set_pwm(self, percent: float):
        pct = max(0, min(100, percent))
        self.state = "pwm" if pct > 0 else "off"
        self.value = pct
        self.last_command = datetime.now().isoformat()

    def snapshot(self) -> dict:
        return {
            "control_id": self.control_id,
            "type": self.type,
            "label": self.label,
            "pin": self.pin,
            "state": self.state,
            "value": self.value,
            "last_command": self.last_command,
            "enabled": self.enabled,
            "auto_mode": self.auto_mode,
            "icon": CONTROL_ICONS.get(self.type, "ctrl"),
        }


# ── SubZone ──────────────────────────────────────────────────

class SubZone:
    """Sous-zone productive avec produit/culture affecte."""

    def __init__(self, zone_id: str, label: str = "",
                 area_m2: float = 10.0, product_id: str = None,
                 planted_at: str = None, culture: str = ""):
        self.zone_id = zone_id
        self.label = label or zone_id
        self.area_m2 = area_m2
        self.product_id = product_id
        self.planted_at = planted_at
        self.culture = culture
        self.notes = ""

    def snapshot(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "label": self.label,
            "area_m2": self.area_m2,
            "product_id": self.product_id,
            "planted_at": self.planted_at,
            "culture": self.culture,
            "notes": self.notes,
        }


# ── Espace ───────────────────────────────────────────────────

class Espace:
    """Espace agricole (serre, pepiniere, champ) avec capteurs + controles."""

    def __init__(self, espace_id: str, type_: str = "serre",
                 label: str = "", location: str = "", description: str = ""):
        self.espace_id = espace_id
        self.type = type_
        self.label = label or espace_id
        self.location = location
        self.description = description
        self.sensors: dict[str, Sensor] = {}
        self.controls: dict[str, Control] = {}
        self.sub_zones: dict[str, SubZone] = {}
        self.enabled = True
        self.created_at = datetime.now().isoformat()
        self.auto_irrigation = False
        self.auto_climate = False
        self.auto_light = False

    def add_sensor(self, sensor: Sensor):
        self.sensors[sensor.sensor_id] = sensor

    def add_control(self, control: Control):
        self.controls[control.control_id] = control

    def add_sub_zone(self, zone: SubZone):
        self.sub_zones[zone.zone_id] = zone

    def remove_sensor(self, sensor_id: str) -> bool:
        if sensor_id in self.sensors:
            del self.sensors[sensor_id]
            return True
        return False

    def remove_control(self, control_id: str) -> bool:
        if control_id in self.controls:
            del self.controls[control_id]
            return True
        return False

    def remove_sub_zone(self, zone_id: str) -> bool:
        if zone_id in self.sub_zones:
            del self.sub_zones[zone_id]
            return True
        return False

    def read_all_sensors(self) -> dict:
        return {sid: s.read() for sid, s in self.sensors.items() if s.enabled}

    def snapshot(self) -> dict:
        return {
            "espace_id": self.espace_id,
            "type": self.type,
            "label": self.label,
            "location": self.location,
            "description": self.description,
            "sensors": {s.sensor_id: s.snapshot() for s in self.sensors.values()},
            "controls": {c.control_id: c.snapshot() for c in self.controls.values()},
            "sub_zones": {z.zone_id: z.snapshot() for z in self.sub_zones.values()},
            "enabled": self.enabled,
            "created_at": self.created_at,
            "auto_irrigation": self.auto_irrigation,
            "auto_climate": self.auto_climate,
            "auto_light": self.auto_light,
        }

    def to_dict(self) -> dict:
        return self.snapshot()


# ── Espaces par defaut ───────────────────────────────────────

DEFAULT_ESPACES_CFG = [
    {
        "id": "serre_a",
        "type": "serre",
        "label": "Serre A - Tomates",
        "location": "Parcelle nord",
        "description": "Serre principale de production tomates",
        "sensors": [
            {"id": "temp_serre_a", "type": "temperature", "label": "Air Serre A"},
            {"id": "hum_air_serre_a", "type": "humidite_air", "label": "Humidite air Serre A"},
            {"id": "hum_sol_serre_a", "type": "humidite_sol", "label": "Humidite sol Serre A"},
            {"id": "lum_serre_a", "type": "lumiere", "label": "Luminosite Serre A"},
            {"id": "npk_serre_a", "type": "npk", "label": "NPK Sol Serre A"},
            {"id": "ph_serre_a", "type": "ph", "label": "pH Sol Serre A"},
            {"id": "co2_serre_a", "type": "co2", "label": "CO2 Serre A"},
            {"id": "flow_serre_a", "type": "irrigation_flow", "label": "Debit irrigation Serre A"},
        ],
        "controls": [
            {"id": "irrig_serre_a", "type": "vanne_irrigation", "label": "Vanne irrigation Serre A", "auto": True},
            {"id": "irrig_serre_a_pwm", "type": "vanne_pwm", "label": "Regulation debit irrigation A", "auto": True},
            {"id": "chauff_serre_a", "type": "chauffage", "label": "Chauffage Serre A", "auto": True},
            {"id": "eclairage_serre_a", "type": "eclairage", "label": "Eclairage croissance A", "auto": True},
            {"id": "brumi_serre_a", "type": "brumisateur", "label": "Brumisateur Serre A", "auto": True},
            {"id": "extract_serre_a", "type": "extracteur", "label": "Extracteur air Serre A", "auto": True},
            {"id": "pompe_serre_a", "type": "pompe", "label": "Pompe irrigation A"},
        ],
        "sub_zones": [
            {"id": "za1", "label": "Zone A1 - Tomates", "area_m2": 45, "product_id": None, "culture": "tomate_coeur_de_boeuf"},
            {"id": "za2", "label": "Zone A2 - Tomates", "area_m2": 40, "product_id": None, "culture": "tomate_coeur_de_boeuf"},
        ],
        "auto_irrigation": True,
        "auto_climate": True,
        "auto_light": True,
    },
    {
        "id": "serre_b",
        "type": "serre",
        "label": "Serre B - Laitues & aromatiques",
        "location": "Parcelle nord",
        "description": "Serre de production laitues et fines herbes",
        "sensors": [
            {"id": "temp_serre_b", "type": "temperature", "label": "Air Serre B"},
            {"id": "hum_air_serre_b", "type": "humidite_air", "label": "Humidite air Serre B"},
            {"id": "hum_sol_serre_b", "type": "humidite_sol", "label": "Humidite sol Serre B"},
            {"id": "lum_serre_b", "type": "lumiere", "label": "Luminosite Serre B"},
            {"id": "npk_serre_b", "type": "npk", "label": "NPK Sol Serre B"},
            {"id": "ph_serre_b", "type": "ph", "label": "pH Sol Serre B"},
            {"id": "flow_serre_b", "type": "irrigation_flow", "label": "Debit irrigation Serre B"},
        ],
        "controls": [
            {"id": "irrig_serre_b", "type": "vanne_irrigation", "label": "Vanne irrigation Serre B", "auto": True},
            {"id": "chauff_serre_b", "type": "chauffage", "label": "Chauffage Serre B", "auto": True},
            {"id": "eclairage_serre_b", "type": "eclairage", "label": "Eclairage croissance B", "auto": True},
            {"id": "brumi_serre_b", "type": "brumisateur", "label": "Brumisateur Serre B"},
            {"id": "extract_serre_b", "type": "extracteur", "label": "Extracteur air Serre B", "auto": True},
        ],
        "sub_zones": [
            {"id": "zb1", "label": "Zone B1 - Laitues", "area_m2": 50, "product_id": None, "culture": "laitue_romaine"},
            {"id": "zb2", "label": "Zone B2 - Aromatiques", "area_m2": 25, "product_id": None},
        ],
        "auto_irrigation": True,
        "auto_climate": True,
        "auto_light": True,
    },
    {
        "id": "pepiniere",
        "type": "pepiniere",
        "label": "Pepiniere - Semis & boutures",
        "location": "Parcelle est",
        "description": "Zone de semis, germination et elevage jeunes plants",
        "sensors": [
            {"id": "temp_pep", "type": "temperature", "label": "Air Pepiniere"},
            {"id": "hum_air_pep", "type": "humidite_air", "label": "Humidite air Pepiniere"},
            {"id": "hum_sol_pep", "type": "humidite_sol", "label": "Humidite substrat Pepiniere"},
            {"id": "lum_pep", "type": "lumiere", "label": "Luminosite Pepiniere"},
            {"id": "co2_pep", "type": "co2", "label": "CO2 Pepiniere"},
        ],
        "controls": [
            {"id": "irrig_pep", "type": "vanne_irrigation", "label": "Irrigation Pepiniere", "auto": True},
            {"id": "chauff_pep", "type": "chauffage", "label": "Chauffage Pepiniere", "auto": True},
            {"id": "eclairage_pep", "type": "eclairage", "label": "Eclairage pepiniere", "auto": True},
            {"id": "ombriere_pep", "type": "ombriere", "label": "Ombriere Pepiniere"},
            {"id": "brumi_pep", "type": "brumisateur", "label": "Brumisateur pepiniere"},
        ],
        "sub_zones": [
            {"id": "zp1", "label": "Table 1 - Semis", "area_m2": 15, "product_id": None, "culture": "semis"},
            {"id": "zp2", "label": "Table 2 - Boutures", "area_m2": 15, "product_id": None, "culture": "boutures"},
            {"id": "zp3", "label": "Table 3 - Repiquage", "area_m2": 12, "product_id": None},
        ],
        "auto_irrigation": True,
        "auto_climate": True,
        "auto_light": True,
    },
    {
        "id": "plein_champ",
        "type": "plein_champ",
        "label": "Plein Champ - Pommiers",
        "location": "Parcelle sud",
        "description": "Vergers de pommiers en pleine terre",
        "sensors": [
            {"id": "temp_champ", "type": "temperature", "label": "Air Plein Champ"},
            {"id": "hum_sol_champ", "type": "humidite_sol", "label": "Humidite sol Plein Champ"},
            {"id": "lum_champ", "type": "lumiere", "label": "Ensoleillement Champ"},
            {"id": "vent_champ", "type": "vent_vitesse", "label": "Vent Plein Champ"},
            {"id": "uv_champ", "type": "uv_index", "label": "UV Plein Champ"},
        ],
        "controls": [
            {"id": "irrig_champ", "type": "vanne_irrigation", "label": "Irrigation Plein Champ", "auto": True},
            {"id": "pompe_champ", "type": "pompe", "label": "Pompe irrigation champ"},
        ],
        "sub_zones": [
            {"id": "zc1", "label": "Champ Est - Pommiers Golden", "area_m2": 200, "product_id": None, "culture": "pommier_golden"},
            {"id": "zc2", "label": "Champ Ouest - Pommiers", "area_m2": 180, "product_id": None, "culture": "pommier_golden"},
        ],
        "auto_irrigation": False,
        "auto_climate": False,
        "auto_light": False,
    },
    {
        "id": "verger",
        "type": "verger",
        "label": "Verger - Arbres fruitiers",
        "location": "Parcelle ouest",
        "description": "Verger mixte avec diverses especes fruitieres",
        "sensors": [
            {"id": "temp_verger", "type": "temperature", "label": "Air Verger"},
            {"id": "hum_sol_verger", "type": "humidite_sol", "label": "Humidite sol Verger"},
            {"id": "lum_verger", "type": "lumiere", "label": "Ensoleillement Verger"},
        ],
        "controls": [
            {"id": "irrig_verger", "type": "vanne_irrigation", "label": "Irrigation Verger", "auto": True},
        ],
        "sub_zones": [
            {"id": "zv1", "label": "Parcelle Ouest", "area_m2": 300, "product_id": None},
        ],
        "auto_irrigation": False,
    },
]


# ── SpaceManager ─────────────────────────────────────────────

class SpaceManager:
    """Orchestrateur des espaces agricoles avec controle environnemental."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.espaces: dict[str, Espace] = {}
        self._load_config()

    def _config_path(self):
        return DATA_DIR / "espaces.json"

    def _load_config(self):
        path = self._config_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    configs = json.load(f)
            except Exception as e:
                log.warning("Erreur chargement espaces", error=str(e))
                configs = DEFAULT_ESPACES_CFG
        else:
            configs = DEFAULT_ESPACES_CFG
        self._init_espaces(configs)
        self._save_config()

    def _init_espaces(self, configs: list[dict]):
        self.espaces = {}
        for c in configs:
            e = Espace(c["id"], c.get("type", "serre"),
                       c.get("label", c["id"]), c.get("location", ""),
                       c.get("description", ""))
            for sc in c.get("sensors", []):
                s = Sensor(sc["id"], sc.get("type", "temperature"),
                           sc.get("label", ""), sc.get("bus", "simulation"),
                           sc.get("addr"))
                s.enabled = sc.get("enabled", True)
                if "alarm_low" in sc:
                    s.alarm_low = sc["alarm_low"]
                if "alarm_high" in sc:
                    s.alarm_high = sc["alarm_high"]
                e.add_sensor(s)
            for cc in c.get("controls", []):
                ctrl = Control(cc["id"], cc.get("type", "vanne_irrigation"),
                               cc.get("label", ""), cc.get("pin"),
                               auto_mode=cc.get("auto", False))
                ctrl.enabled = cc.get("enabled", True)
                e.add_control(ctrl)
            for sz in c.get("sub_zones", []):
                zone = SubZone(sz["id"], sz.get("label", ""),
                               sz.get("area_m2", 10),
                               sz.get("product_id"), sz.get("planted_at"),
                               sz.get("culture", ""))
                e.add_sub_zone(zone)
            e.auto_irrigation = c.get("auto_irrigation", False)
            e.auto_climate = c.get("auto_climate", False)
            e.auto_light = c.get("auto_light", False)
            self.espaces[c["id"]] = e

    def _save_config(self):
        configs = []
        for e in self.espaces.values():
            configs.append({
                "id": e.espace_id,
                "type": e.type,
                "label": e.label,
                "location": e.location,
                "description": e.description,
                "auto_irrigation": e.auto_irrigation,
                "auto_climate": e.auto_climate,
                "auto_light": e.auto_light,
                "sensors": [{"id": s.sensor_id, "type": s.type,
                            "label": s.label, "bus": s.bus, "addr": s.addr,
                            "enabled": s.enabled,
                            "alarm_low": s.alarm_low, "alarm_high": s.alarm_high}
                           for s in e.sensors.values()],
                "controls": [{"id": c.control_id, "type": c.type,
                              "label": c.label, "pin": c.pin,
                              "enabled": c.enabled, "auto": c.auto_mode}
                            for c in e.controls.values()],
                "sub_zones": [{"id": z.zone_id, "label": z.label,
                              "area_m2": z.area_m2, "product_id": z.product_id,
                              "planted_at": z.planted_at, "culture": z.culture}
                            for z in e.sub_zones.values()],
            })
        with open(self._config_path(), "w", encoding="utf-8") as f:
            json.dump(configs, f, indent=2, ensure_ascii=False)

    # ── API Publique ────────────────────────────────────────

    def list_espaces(self) -> list[dict]:
        return [e.snapshot() for e in self.espaces.values()]

    def get_espace(self, espace_id: str) -> dict | None:
        e = self.espaces.get(espace_id)
        return e.to_dict() if e else None

    def add_espace(self, espace_id: str, type_: str = "serre",
                   label: str = "", location: str = "",
                   description: str = "", confirm: bool = False) -> dict:
        if espace_id in self.espaces:
            return {"error": f"Espace {espace_id} existe deja",
                    "status": "exists"}
        if not confirm:
            return {"error": "Confirmation requise",
                    "status": "pending_confirmation",
                    "preview": {
                        "espace_id": espace_id, "type": type_,
                        "label": label, "location": location,
                        "description": description,
                    }}
        e = Espace(espace_id, type_, label or espace_id, location, description)
        self.espaces[espace_id] = e
        self._save_config()
        log.info("Espace ajoute", espace=espace_id, type=type_)
        return {"status": "ok", "espace": e.snapshot()}

    def remove_espace(self, espace_id: str, confirm: bool = False) -> dict:
        if espace_id not in self.espaces:
            return {"error": "not found"}, 404
        if not confirm:
            return {"error": "Confirmation requise pour supprimer",
                    "status": "pending_confirmation",
                    "espace": self.espaces[espace_id].snapshot()}
        label = self.espaces[espace_id].label
        del self.espaces[espace_id]
        self._save_config()
        log.info("Espace supprime", espace=espace_id)
        return {"status": "ok", "removed": espace_id, "label": label}

    def add_sensor_to_espace(self, espace_id: str, sensor_id: str,
                              type_: str = "temperature",
                              label: str = "", bus: str = "simulation",
                              addr: str = None) -> dict:
        e = self.espaces.get(espace_id)
        if not e:
            return {"error": "Espace introuvable"}, 404
        if sensor_id in e.sensors:
            return {"error": "Capteur existe deja"}, 400
        s = Sensor(sensor_id, type_, label or sensor_id, bus, addr)
        e.add_sensor(s)
        self._save_config()
        return {"status": "ok", "sensor": s.snapshot()}

    def remove_sensor(self, espace_id: str, sensor_id: str) -> dict:
        e = self.espaces.get(espace_id)
        if not e:
            return {"error": "not found"}, 404
        if e.remove_sensor(sensor_id):
            self._save_config()
            return {"status": "ok", "removed": sensor_id}
        return {"error": "sensor not found"}, 404

    def add_control_to_espace(self, espace_id: str, control_id: str,
                               type_: str = "vanne_irrigation",
                               label: str = "", pin: int = None,
                               auto_mode: bool = False) -> dict:
        e = self.espaces.get(espace_id)
        if not e:
            return {"error": "Espace introuvable"}, 404
        if control_id in e.controls:
            return {"error": "Controle existe deja"}, 400
        c = Control(control_id, type_, label or control_id, pin, auto_mode=auto_mode)
        e.add_control(c)
        self._save_config()
        return {"status": "ok", "control": c.snapshot()}

    def remove_control(self, espace_id: str, control_id: str) -> dict:
        e = self.espaces.get(espace_id)
        if not e:
            return {"error": "not found"}, 404
        if e.remove_control(control_id):
            self._save_config()
            return {"status": "ok", "removed": control_id}
        return {"error": "control not found"}, 404

    def add_sub_zone(self, espace_id: str, zone_id: str,
                      label: str = "", area_m2: float = 10.0,
                      culture: str = "") -> dict:
        e = self.espaces.get(espace_id)
        if not e:
            return {"error": "Espace introuvable"}, 404
        if zone_id in e.sub_zones:
            return {"error": "Sous-zone existe deja"}, 400
        z = SubZone(zone_id, label or zone_id, area_m2, culture=culture)
        e.add_sub_zone(z)
        self._save_config()
        return {"status": "ok", "sub_zone": z.snapshot()}

    def remove_sub_zone(self, espace_id: str, zone_id: str) -> dict:
        e = self.espaces.get(espace_id)
        if not e:
            return {"error": "not found"}, 404
        if e.remove_sub_zone(zone_id):
            self._save_config()
            return {"status": "ok", "removed": zone_id}
        return {"error": "sub_zone not found"}, 404

    def read_sensors(self, espace_id: str = None) -> dict:
        if espace_id:
            e = self.espaces.get(espace_id)
            if not e:
                return {}
            return {espace_id: e.read_all_sensors()}
        result = {}
        for eid, e in self.espaces.items():
            result[eid] = e.read_all_sensors()
        return result

    def control_action(self, espace_id: str, control_id: str,
                        action: str, value: float = None) -> dict | None:
        e = self.espaces.get(espace_id)
        if not e:
            return None
        ctrl = e.controls.get(control_id)
        if not ctrl:
            return None
        if action == "on":
            ctrl.turn_on(value or 100.0)
        elif action == "off":
            ctrl.turn_off()
        elif action == "pwm":
            ctrl.set_pwm(value or 50.0)
        elif action == "auto_on":
            ctrl.auto_mode = True
        elif action == "auto_off":
            ctrl.auto_mode = False
        self._save_config()
        return ctrl.snapshot()

    def assign_product(self, espace_id: str, sub_zone_id: str,
                        product_id: str, planted_at: str = None) -> dict | None:
        e = self.espaces.get(espace_id)
        if not e:
            return None
        z = e.sub_zones.get(sub_zone_id)
        if not z:
            return None
        z.product_id = product_id
        z.planted_at = planted_at or datetime.now().strftime("%Y-%m-%d")
        self._save_config()
        return z.snapshot()

    def set_auto_mode(self, espace_id: str, auto_type: str,
                       enabled: bool) -> dict | None:
        e = self.espaces.get(espace_id)
        if not e:
            return None
        if auto_type == "irrigation":
            e.auto_irrigation = enabled
        elif auto_type == "climate":
            e.auto_climate = enabled
        elif auto_type == "light":
            e.auto_light = enabled
        self._save_config()
        return e.snapshot()

    def auto_control_cycle(self, espace_id: str = None) -> dict:
        """Cycle de controle automatique base sur les capteurs.
        Regulation irrigation, temperature, eclairage selon les seuils."""
        actions = []
        targets = [self.espaces.get(espace_id)] if espace_id else list(self.espaces.values())
        for e in targets:
            if not e or not e.enabled:
                continue
            e.read_all_sensors()

            # Regulation irrigation
            if e.auto_irrigation:
                soil_sensor = next((s for s in e.sensors.values()
                                    if s.type == "humidite_sol"), None)
                irrig_ctrl = next((c for c in e.controls.values()
                                   if c.type in ("vanne_irrigation", "vanne_pwm")), None)
                if soil_sensor and irrig_ctrl and irrig_ctrl.auto_mode:
                    if soil_sensor.value < 35.0:
                        irrig_ctrl.turn_on(80.0)
                        actions.append(f"{e.label}: Irrigation ON ({soil_sensor.value}% sol)")
                    elif soil_sensor.value > 75.0:
                        irrig_ctrl.turn_off()
                        actions.append(f"{e.label}: Irrigation OFF ({soil_sensor.value}% sol)")
                    elif soil_sensor.value < 50.0:
                        irrig_ctrl.set_pwm(40.0)
                        actions.append(f"{e.label}: Irrigation PWM 40% ({soil_sensor.value}% sol)")
                    else:
                        irrig_ctrl.set_pwm(max(0, irrig_ctrl.value - 5))

            # Regulation temperature
            if e.auto_climate:
                temp_sensor = next((s for s in e.sensors.values()
                                    if s.type == "temperature"), None)
                chauff_ctrl = next((c for c in e.controls.values()
                                    if c.type == "chauffage" and c.auto_mode), None)
                extract_ctrl = next((c for c in e.controls.values()
                                     if c.type == "extracteur" and c.auto_mode), None)
                brumi_ctrl = next((c for c in e.controls.values()
                                   if c.type == "brumisateur" and c.auto_mode), None)
                if temp_sensor:
                    if chauff_ctrl:
                        if temp_sensor.value < 16.0:
                            chauff_ctrl.turn_on(100.0)
                            actions.append(f"{e.label}: Chauffage ON ({temp_sensor.value}C)")
                        elif temp_sensor.value > 22.0:
                            if extract_ctrl:
                                extract_ctrl.turn_on(80.0)
                                actions.append(f"{e.label}: Extraction ON ({temp_sensor.value}C)")
                            if chauff_ctrl:
                                chauff_ctrl.turn_off()
                        else:
                            if extract_ctrl:
                                extract_ctrl.turn_off()
                    if brumi_ctrl:
                        hum_air = next((s for s in e.sensors.values()
                                        if s.type == "humidite_air"), None)
                        if hum_air and hum_air.value < 50.0:
                            brumi_ctrl.set_pwm(60.0)
                        elif hum_air and hum_air.value > 80.0:
                            brumi_ctrl.turn_off()

            # Regulation eclairage
            if e.auto_light:
                light_sensor = next((s for s in e.sensors.values()
                                     if s.type == "lumiere"), None)
                light_ctrl = next((c for c in e.controls.values()
                                   if c.type == "eclairage" and c.auto_mode), None)
                if light_sensor and light_ctrl:
                    hour = datetime.now().hour
                    if hour < 6 or hour > 20:
                        if light_sensor.value < 2000:
                            light_ctrl.turn_on(100.0)
                            actions.append(f"{e.label}: Eclairage ON ({light_sensor.value} lux)")
                        else:
                            light_ctrl.turn_off()
                    else:
                        if light_sensor.value < 5000:
                            light_ctrl.set_pwm(50.0)
                        else:
                            light_ctrl.turn_off()

        self._save_config()
        return {"actions": actions, "count": len(actions)}

    def summary(self) -> dict:
        total = len(self.espaces)
        sensors = sum(len(e.sensors) for e in self.espaces.values())
        controls = sum(len(e.controls) for e in self.espaces.values())
        zones = sum(len(e.sub_zones) for e in self.espaces.values())
        by_type = {}
        for e in self.espaces.values():
            by_type[e.type] = by_type.get(e.type, 0) + 1
        return {
            "total": total,
            "by_type": by_type,
            "sensors": sensors,
            "controls": controls,
            "sub_zones": zones,
            "espaces": [{"id": e.espace_id, "label": e.label,
                        "type": e.type, "location": e.location,
                        "auto_irrigation": e.auto_irrigation,
                        "auto_climate": e.auto_climate,
                        "auto_light": e.auto_light,
                        "sensor_count": len(e.sensors),
                        "control_count": len(e.controls),
                        "zone_count": len(e.sub_zones)}
                       for e in self.espaces.values()],
        }
