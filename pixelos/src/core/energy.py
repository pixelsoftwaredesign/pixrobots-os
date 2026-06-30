"""PixelOS EnergyManager - Gestion energetique solaire.

Architecture:
  SolarPanel    →  Panneau solaire (Wc, simulation irradiation)
  BatteryBank   →  Batterie avec SOC, charge/decharge
  PowerLoad     →  Consommateur (pompe, chauffage, vanne) avec priorite
  LoadScheduler →  Ordonnancement avec load-shedding
  EnergyManager →  Orchestrateur supervision energetique
"""

import json
import math
import time
import structlog
from pathlib import Path
from datetime import datetime, date, time as dtime
from typing import Any

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "energy"


# ── Constantes ───────────────────────────────────────────────

W_PER_M2 = 1000.0  # Irradiance standard STC
LOAD_PRIORITIES = ["critical", "high", "medium", "low", "sheddable"]
LOAD_STATES = ["on", "off", "throttled", "standby"]


# ── Modele Irradiation Solaire ───────────────────────────────

def solar_irradiance(lat: float = 43.6, lon: float = 3.9,
                     hour: int = None) -> float:
    """Estime l'irradiation solaire (W/m2) en fonction de l'heure.

    Modele simplifie : courbe cosinusoidale avec pic a 13h.
    Utile pour simulation sans capteur pyranometre reel.
    """
    if hour is None:
        hour = datetime.now().hour + datetime.now().minute / 60.0
    sunrise, sunset = 6.5, 20.5
    if hour < sunrise or hour > sunset:
        return 0.0
    day_frac = (hour - sunrise) / (sunset - sunrise)
    return round(W_PER_M2 * math.sin(math.pi * day_frac), 1)


# ── Panneau Solaire ──────────────────────────────────────────

class SolarPanel:
    """Panneau photovoltaique avec suivi de production."""

    def __init__(self, panel_id: str, label: str = "",
                 peak_power_w: float = 400.0, efficiency: float = 0.20,
                 area_m2: float = 2.0, tilt: float = 30.0,
                 temp_coeff: float = -0.0035):
        self.panel_id = panel_id
        self.label = label or panel_id
        self.peak_power_w = peak_power_w
        self.efficiency = efficiency
        self.area_m2 = area_m2
        self.tilt = tilt
        self.temp_coeff = temp_coeff
        self.current_power_w = 0.0
        self.daily_kwh = 0.0
        self.total_kwh = 0.0
        self._last_hour = datetime.now().hour
        self.enabled = True

    def update(self, irradiance_wm2: float = None,
               ambient_temp_c: float = 25.0) -> float:
        if not self.enabled:
            self.current_power_w = 0.0
            return 0.0

        if irradiance_wm2 is None:
            irradiance_wm2 = solar_irradiance()

        # Perte thermique: puissance baisse avec la chaleur
        cell_temp = ambient_temp_c + irradiance_wm2 * 0.03
        temp_loss = 1.0 + self.temp_coeff * (cell_temp - 25.0)
        temp_loss = max(0.5, min(1.0, temp_loss))

        # Production instantanee
        raw = self.peak_power_w * (irradiance_wm2 / W_PER_M2)
        self.current_power_w = round(raw * temp_loss, 1)

        # Accumulation journaliere
        now = datetime.now()
        if now.hour != self._last_hour:
            self.daily_kwh += self.current_power_w / 1000.0
            self._last_hour = now.hour
        self.total_kwh += self.current_power_w / 1000.0 / 3600.0

        return self.current_power_w

    def snapshot(self) -> dict:
        return {
            "panel_id": self.panel_id,
            "label": self.label,
            "peak_power_w": self.peak_power_w,
            "current_power_w": self.current_power_w,
            "daily_kwh": round(self.daily_kwh, 3),
            "total_kwh": round(self.total_kwh, 3),
            "enabled": self.enabled,
        }


# ── Batterie ─────────────────────────────────────────────────

class BatteryBank:
    """Banque de batteries avec SOC et simulation charge/decharge."""

    def __init__(self, battery_id: str = "main",
                 capacity_kwh: float = 10.0,
                 max_charge_rate_w: float = 3000.0,
                 max_discharge_rate_w: float = 5000.0,
                 efficiency: float = 0.92,
                 min_soc: float = 0.15, max_soc: float = 0.95):
        self.battery_id = battery_id
        self.capacity_kwh = capacity_kwh
        self.max_charge_rate_w = max_charge_rate_w
        self.max_discharge_rate_w = max_discharge_rate_w
        self.efficiency = efficiency
        self.min_soc = min_soc
        self.max_soc = max_soc
        self.soc = 0.5  # Initial SOC 50%
        self.current_power_w = 0.0  # >0 = charge, <0 = decharge
        self.cycle_count = 0
        self._last_soc_pct = 50.0

    def charge(self, power_w: float, dt_hours: float = 1.0 / 3600) -> float:
        """Charge la batterie avec une puissance disponible."""
        if self.soc >= self.max_soc:
            self.current_power_w = 0.0
            return 0.0
        limited = min(power_w, self.max_charge_rate_w)
        # Rendement
        effective = limited * self.efficiency
        # Conversion W -> kWh
        delta_kwh = effective * dt_hours / 1000.0
        old_soc = self.soc
        self.soc = min(self.max_soc, self.soc + delta_kwh / self.capacity_kwh)
        self.current_power_w = limited
        if old_soc < self.min_soc and self.soc >= self.min_soc:
            self.cycle_count += 1
        return limited

    def discharge(self, power_w: float, dt_hours: float = 1.0 / 3600) -> float:
        """Decharge la batterie pour fournir une puissance."""
        if self.soc <= self.min_soc:
            self.current_power_w = 0.0
            return 0.0
        limited = min(power_w, self.max_discharge_rate_w)
        delta_kwh = limited * dt_hours / 1000.0
        self.soc = max(self.min_soc, self.soc - delta_kwh / self.capacity_kwh)
        self.current_power_w = -limited
        return limited

    def snapshot(self) -> dict:
        return {
            "battery_id": self.battery_id,
            "capacity_kwh": self.capacity_kwh,
            "soc": round(self.soc * 100, 1),
            "soc_pct": round(self.soc * 100, 1),
            "current_power_w": self.current_power_w,
            "max_charge_rate_w": self.max_charge_rate_w,
            "max_discharge_rate_w": self.max_discharge_rate_w,
            "cycle_count": self.cycle_count,
            "min_soc_pct": self.min_soc * 100,
            "max_soc_pct": self.max_soc * 100,
        }


# ── Consommateur (Load) ──────────────────────────────────────

class PowerLoad:
    """Equipement consommateur d'electricite avec priorite."""

    def __init__(self, load_id: str, label: str = "",
                 nominal_w: float = 500.0,
                 priority: str = "medium",
                 category: str = "general"):
        self.load_id = load_id
        self.label = label or load_id
        self.nominal_w = nominal_w
        self.priority = priority
        self.category = category
        self.state = "off"
        self.current_draw_w = 0.0
        self.throttle_pct = 100.0
        self.runtime_hours = 0.0
        self._last_state_change = time.time()

    def turn_on(self, throttle: float = 100.0):
        self.state = "on"
        self.throttle_pct = max(0.0, min(100.0, throttle))
        self.current_draw_w = round(self.nominal_w * self.throttle_pct / 100.0, 1)
        self._last_state_change = time.time()
        log.info("Load ON", load=self.load_id, power=self.current_draw_w)

    def turn_off(self):
        self.state = "off"
        self.current_draw_w = 0.0
        self.throttle_pct = 0.0
        self._last_state_change = time.time()
        log.info("Load OFF", load=self.load_id)

    def throttle(self, pct: float):
        pct = max(0.0, min(100.0, pct))
        self.throttle_pct = pct
        if pct > 0 and self.state == "on":
            self.current_draw_w = round(self.nominal_w * pct / 100.0, 1)
        elif pct <= 0:
            self.turn_off()

    def snapshot(self) -> dict:
        return {
            "load_id": self.load_id,
            "label": self.label,
            "nominal_w": self.nominal_w,
            "current_draw_w": self.current_draw_w,
            "priority": self.priority,
            "category": self.category,
            "state": self.state,
            "throttle_pct": self.throttle_pct,
        }


# ── Planificateur de Charge (Load Scheduler) ─────────────────

PRIORITY_ORDER = {p: i for i, p in enumerate(LOAD_PRIORITIES)}


class LoadScheduler:
    """Distribue la puissance disponible entre les charges selon priorite."""

    def __init__(self):
        self.strategy = "priority"  # priority | balanced | eco

    def schedule(self, available_w: float,
                 loads: list[PowerLoad]) -> list[dict]:
        """Repartit la puissance, eteint les charges non prioritaires si necessaire."""
        total_demand = sum(l.nominal_w for l in loads if l.state == "on")
        decisions = []

        if total_demand <= available_w:
            for l in loads:
                if l.state == "on":
                    l.turn_on(100.0)
                    decisions.append({"load": l.load_id, "action": "on", "power": l.nominal_w})
            return decisions

        # Load-shedding: tri par priorite
        sorted_loads = sorted(loads, key=lambda x: PRIORITY_ORDER.get(x.priority, 99))
        remaining = available_w

        for l in sorted_loads:
            if remaining <= 0:
                l.turn_off()
                decisions.append({"load": l.load_id, "action": "shed", "power": 0})
                continue
            if l.state == "off":
                decisions.append({"load": l.load_id, "action": "off", "power": 0})
                continue
            if l.nominal_w <= remaining:
                l.turn_on(100.0)
                remaining -= l.nominal_w
                decisions.append({"load": l.load_id, "action": "on", "power": l.nominal_w})
            else:
                pct = remaining / l.nominal_w * 100.0
                l.turn_on(pct)
                remaining = 0
                decisions.append({"load": l.load_id, "action": "throttled",
                                  "power": l.current_draw_w})

        return decisions


# ── Gestionnaire Energie ─────────────────────────────────────

DEFAULT_PANELS = [
    {"panel_id": "toit_serre_a", "label": "Toit Serre A", "peak_power_w": 2400.0,
     "area_m2": 12.0, "tilt": 25.0},
    {"panel_id": "toit_serre_b", "label": "Toit Serre B", "peak_power_w": 1800.0,
     "area_m2": 9.0, "tilt": 25.0},
    {"panel_id": "sol_est", "label": "Plein champ Est", "peak_power_w": 3000.0,
     "area_m2": 15.0, "tilt": 30.0},
]

DEFAULT_LOADS = [
    {"load_id": "pompe_irrigation", "label": "Pompe irrigation", "nominal_w": 1500.0,
     "priority": "high", "category": "irrigation"},
    {"load_id": "chauffage_serre_a", "label": "Chauffage Serre A", "nominal_w": 3000.0,
     "priority": "medium", "category": "heating"},
    {"load_id": "chauffage_serre_b", "label": "Chauffage Serre B", "nominal_w": 2000.0,
     "priority": "medium", "category": "heating"},
    {"load_id": "pompe_geothermie", "label": "Pompe geothermie", "nominal_w": 800.0,
     "priority": "medium", "category": "heating"},
    {"load_id": "ventilation", "label": "Ventilation serres", "nominal_w": 300.0,
     "priority": "low", "category": "ventilation"},
    {"load_id": "eclairage", "label": "Eclairage auxiliaire", "nominal_w": 400.0,
     "priority": "low", "category": "lighting"},
    {"load_id": "station_meteo", "label": "Station meteo", "nominal_w": 50.0,
     "priority": "critical", "category": "monitoring"},
    {"load_id": "pixelos_server", "label": "Serveur PixelOS", "nominal_w": 150.0,
     "priority": "critical", "category": "it"},
]


class EnergyManager:
    """Orchestrateur de la supervision energetique."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.panels: dict[str, SolarPanel] = {}
        self.battery = BatteryBank()
        self.loads: dict[str, PowerLoad] = {}
        self.scheduler = LoadScheduler()
        self.ambient_temp_c = 25.0
        self.last_irradiance = 0.0
        self.total_solar_w = 0.0
        self.total_load_w = 0.0
        self.grid_power_w = 0.0  # Puissance reseau (si present)
        self.grid_available = False
        self.history = []
        self.max_history = 1440
        self._load_config()

    def _config_path(self):
        return DATA_DIR / "config.json"

    def _load_config(self):
        path = self._config_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self._init_panels(cfg.get("panels", DEFAULT_PANELS))
                self._init_loads(cfg.get("loads", DEFAULT_LOADS))
                batt_cfg = cfg.get("battery", {})
                self.battery = BatteryBank(**batt_cfg)
                self.grid_available = cfg.get("grid_available", False)
                log.info("Configuration energetique chargee", panels=len(self.panels),
                         loads=len(self.loads))
            except Exception as e:
                log.warning("Erreur chargement config energy", error=str(e))
                self._init_defaults()
        else:
            self._init_defaults()
        self._save_config()

    def _init_defaults(self):
        self._init_panels(DEFAULT_PANELS)
        self._init_loads(DEFAULT_LOADS)
        self.battery = BatteryBank()
        self.grid_available = False

    def _init_panels(self, configs: list[dict]):
        self.panels = {}
        for c in configs:
            pid = c.get("panel_id") or c.get("id")
            enabled = c.pop("enabled", True) if isinstance(c, dict) else True
            panel = SolarPanel(**c)
            panel.enabled = enabled
            self.panels[pid] = panel

    def _init_loads(self, configs: list[dict]):
        self.loads = {}
        for c in configs:
            lid = c.get("load_id") or c.get("id")
            self.loads[lid] = PowerLoad(**c)

    def _save_config(self):
        cfg = {
            "panels": [{
                "panel_id": p.panel_id,
                "label": p.label,
                "peak_power_w": p.peak_power_w,
                "efficiency": p.efficiency,
                "area_m2": p.area_m2,
                "tilt": p.tilt,
                "temp_coeff": p.temp_coeff,
                "enabled": p.enabled,
            } for p in self.panels.values()],
            "loads": [{
                "load_id": l.load_id,
                "label": l.label,
                "nominal_w": l.nominal_w,
                "priority": l.priority,
                "category": l.category,
            } for l in self.loads.values()],
            "battery": {
                "battery_id": self.battery.battery_id,
                "capacity_kwh": self.battery.capacity_kwh,
                "max_charge_rate_w": self.battery.max_charge_rate_w,
                "max_discharge_rate_w": self.battery.max_discharge_rate_w,
                "efficiency": self.battery.efficiency,
                "min_soc": self.battery.min_soc,
                "max_soc": self.battery.max_soc,
            },
            "grid_available": self.grid_available,
            "updated": datetime.now().isoformat(),
        }
        with open(self._config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

    # ── API Publique ────────────────────────────────────────

    def update_solar(self) -> dict:
        """Met a jour la production solaire de tous les panneaux."""
        self.last_irradiance = solar_irradiance()
        panel_results = {}
        self.total_solar_w = 0.0
        for pid, panel in self.panels.items():
            power = panel.update(self.last_irradiance, self.ambient_temp_c)
            panel_results[pid] = power
            self.total_solar_w += power
        self.total_solar_w = round(self.total_solar_w, 1)
        return {
            "irradiance": self.last_irradiance,
            "total_w": self.total_solar_w,
            "panels": panel_results,
        }

    def update_loads(self, auto_schedule: bool = True) -> dict:
        """Calcule la consommation totale et optionnelement ordonnance."""
        self.total_load_w = sum(l.current_draw_w for l in self.loads.values())
        return {
            "total_w": round(self.total_load_w, 1),
            "loads": {lid: l.snapshot() for lid, l in self.loads.items()},
        }

    def run_cycle(self, ambient_temp_c: float = None) -> dict:
        """Execute un cycle complet : production, batterie, loadshedding."""
        if ambient_temp_c is not None:
            self.ambient_temp_c = ambient_temp_c

        # 1. Production solaire
        solar = self.update_solar()

        # 2. Calcul surplus/deficit
        total_demand = sum(l.nominal_w for l in self.loads.values() if l.state == "on")
        net_power = self.total_solar_w + self.grid_power_w - total_demand

        # 3. Gestion batterie
        battery_action = "idle"
        if net_power > 0:
            charged = self.battery.charge(net_power)
            battery_action = f"charge({charged}W)"
        elif net_power < 0:
            discharged = self.battery.discharge(-net_power)
            net_power += discharged
            battery_action = f"discharge({discharged}W)"

        # 4. Load-shedding si toujours en deficit
        available = self.total_solar_w + self.grid_power_w
        if not self.grid_available:
            available += abs(self.battery.current_power_w) if self.battery.current_power_w < 0 else 0
        else:
            available += max(0, self.grid_power_w)

        shed_decisions = []
        if net_power < 0 and self.battery.soc <= self.battery.min_soc:
            shed_decisions = self.scheduler.schedule(
                self.total_solar_w + self.grid_power_w,
                list(self.loads.values()),
            )

        # 5. Historique
        entry = {
            "ts": datetime.now().isoformat(),
            "irradiance": self.last_irradiance,
            "solar_w": self.total_solar_w,
            "grid_w": self.grid_power_w,
            "load_w": self.total_load_w,
            "battery_soc": round(self.battery.soc * 100, 1),
            "battery_power_w": self.battery.current_power_w,
            "net_power": round(net_power, 1),
        }
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        return {
            "solar": solar,
            "loads": self.update_loads(auto_schedule=False),
            "battery": self.battery.snapshot(),
            "net_power_w": round(net_power, 1),
            "battery_action": battery_action,
            "shed_decisions": shed_decisions,
        }

    def summary(self) -> dict:
        total_panel_w = sum(p.peak_power_w for p in self.panels.values())
        total_nominal_w = sum(l.nominal_w for l in self.loads.values())
        active_loads = sum(1 for l in self.loads.values() if l.state == "on")
        return {
            "panels": len(self.panels),
            "peak_panel_kw": round(total_panel_w / 1000, 2),
            "loads": len(self.loads),
            "active_loads": active_loads,
            "peak_load_kw": round(total_nominal_w / 1000, 2),
            "current_solar_w": self.total_solar_w,
            "current_load_w": self.total_load_w,
            "battery_soc": round(self.battery.soc * 100, 1),
            "battery_capacity_kwh": self.battery.capacity_kwh,
            "grid_available": self.grid_available,
            "irradiance": self.last_irradiance,
        }

    def forecast(self, hours: int = 24) -> list[dict]:
        """Prevision de production solaire sur les prochaines heures."""
        now = datetime.now()
        forecast = []
        for h in range(hours):
            ts = now.timestamp() + h * 3600
            dt = datetime.fromtimestamp(ts)
            irr = solar_irradiance(hour=dt.hour + dt.minute / 60.0)
            total_power = 0.0
            for panel in self.panels.values():
                raw = panel.peak_power_w * (irr / W_PER_M2)
                total_power += raw
            forecast.append({
                "hour": dt.strftime("%Y-%m-%d %H:00"),
                "irradiance_wm2": irr,
                "estimated_kw": round(total_power / 1000, 3),
            })
        return forecast

    def set_ambient_temp(self, temp_c: float):
        self.ambient_temp_c = temp_c

    def set_grid(self, available: bool, power_w: float = 0.0):
        self.grid_available = available
        self.grid_power_w = power_w if available else 0.0

    def set_load_state(self, load_id: str, state: str,
                       throttle: float = None) -> dict | None:
        load = self.loads.get(load_id)
        if not load:
            return None
        if state == "on":
            load.turn_on(throttle or 100.0)
        elif state == "off":
            load.turn_off()
        elif state == "throttle" and throttle is not None:
            load.throttle(throttle)
        self._save_config()
        return load.snapshot()

    def list_panels(self) -> list[dict]:
        return [p.snapshot() for p in self.panels.values()]

    def list_loads(self) -> list[dict]:
        return [l.snapshot() for l in self.loads.values()]

    def get_history(self, limit: int = 120) -> list[dict]:
        return self.history[-limit:]
