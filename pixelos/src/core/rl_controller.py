# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""rl_controller — Reinforcement Learning pour irrigation et chauffage.

Q-learning avec etats discrets pour ajuster les vannes d'irrigation et les
consignes de chauffage geothermique en fonction des lectures capteurs et du
rendement obtenu.

State  = (soil_moisture_bucket, temperature_bucket, hour_bucket)
Action = [IRR_INCREASE, IRR_DECREASE, IRR_MAINTAIN,
          HEAT_INCREASE, HEAT_DECREASE, HEAT_MAINTAIN]
Reward = sante_plantes + economie_eau + economie_energie
"""

import json
import structlog
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Optional

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "rl"

# Hyperparametres par defaut
DEFAULT_ALPHA = 0.1       # taux d'apprentissage
DEFAULT_GAMMA = 0.9       # facteur d'actualisation
DEFAULT_EPSILON = 1.0     # exploration initiale
DEFAULT_EPSILON_MIN = 0.01
DEFAULT_EPSILON_DECAY = 0.995
DEFAULT_BATCH_SIZE = 32
DEFAULT_MEMORY_SIZE = 10000

# Actions
IRR_INCREASE = 0
IRR_DECREASE = 1
IRR_MAINTAIN = 2
HEAT_INCREASE = 3
HEAT_DECREASE = 4
HEAT_MAINTAIN = 5

ACTION_LABELS = {
    IRR_INCREASE: "augmenter_irrigation",
    IRR_DECREASE: "diminuer_irrigation",
    IRR_MAINTAIN: "maintenir_irrigation",
    HEAT_INCREASE: "augmenter_chauffage",
    HEAT_DECREASE: "diminuer_chauffage",
    HEAT_MAINTAIN: "maintenir_chauffage",
}

# Discretisation
MOISTURE_BUCKETS = 5   # 0-100% en 5 paliers: tres sec, sec, optimal, humide, detrempe
TEMP_BUCKETS = 5        # 0-40°C en 5 paliers: froid, frais, optimal, chaud, tres chaud
HOUR_BUCKETS = 6        # 24h en 6 creneaux: nuit, matin, midi, apres-midi, soir, fin_soir


def _to_buckets(soil_moisture: float, temperature: float, hour: int) -> tuple:
    """Discretise les entrees continues en indices de buckets."""
    m = min(int(soil_moisture / 20), MOISTURE_BUCKETS - 1)
    t = min(int(temperature / 8), TEMP_BUCKETS - 1)
    h = min(hour // 4, HOUR_BUCKETS - 1)
    return (m, t, h)


class RLController:
    """Controleur RL pour irrigation et chauffage agricole."""

    def __init__(self, zone_id: str = "serre_a", load_persisted: bool = True):
        self.zone_id = zone_id
        self.alpha = DEFAULT_ALPHA
        self.gamma = DEFAULT_GAMMA
        self.epsilon = DEFAULT_EPSILON
        self.epsilon_min = DEFAULT_EPSILON_MIN
        self.epsilon_decay = DEFAULT_EPSILON_DECAY
        self.batch_size = DEFAULT_BATCH_SIZE
        self.memory_size = DEFAULT_MEMORY_SIZE

        self.q_table: dict[tuple, np.ndarray] = defaultdict(
            lambda: np.zeros(len(ACTION_LABELS)))
        self.replay_memory: list[tuple] = []
        self._step_count = 0

        self._ensure_dirs()
        if load_persisted:
            self._load_q_table()
            self._load_hyperparams()

    def _ensure_dirs(self):
        (DATA_DIR / self.zone_id).mkdir(parents=True, exist_ok=True)

    def _zone_path(self) -> Path:
        return DATA_DIR / self.zone_id

    def _q_path(self) -> Path:
        return self._zone_path() / "q_table.json"

    def _params_path(self) -> Path:
        return self._zone_path() / "params.json"

    def _history_path(self) -> Path:
        return self._zone_path() / "history.jsonl"

    def _load_q_table(self):
        p = self._q_path()
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                for k, v in raw.items():
                    parts = tuple(json.loads(k))
                    self.q_table[parts] = np.array(v, dtype=np.float64)
                log.info("Q-table chargee", zone=self.zone_id,
                         states=len(raw))
            except Exception as e:
                log.warning("Echec chargement Q-table", error=str(e))

    def _save_q_table(self):
        raw = {json.dumps(list(k)): v.tolist() for k, v in self.q_table.items()}
        self._q_path().write_text(
            json.dumps(raw, indent=2), encoding="utf-8")

    def _load_hyperparams(self):
        p = self._params_path()
        if p.exists():
            try:
                params = json.loads(p.read_text(encoding="utf-8"))
                self.alpha = params.get("alpha", DEFAULT_ALPHA)
                self.gamma = params.get("gamma", DEFAULT_GAMMA)
                self.epsilon = params.get("epsilon", DEFAULT_EPSILON)
                log.info("Hyperparametres charges", zone=self.zone_id)
            except Exception:
                pass

    def _save_hyperparams(self):
        self._params_path().write_text(json.dumps({
            "alpha": self.alpha, "gamma": self.gamma, "epsilon": self.epsilon,
            "epsilon_min": self.epsilon_min, "epsilon_decay": self.epsilon_decay,
            "batch_size": self.batch_size, "step": self._step_count,
            "updated": datetime.now().isoformat(),
        }, indent=2), encoding="utf-8")

    def _count_states(self) -> int:
        return len(self.q_table)

    def _count_actions(self) -> int:
        return sum(len(v) for v in self.q_table.values())

    def _memory_usage_kb(self) -> int:
        p = self._q_path()
        return round(p.stat().st_size / 1024, 1) if p.exists() else 0

    def stats(self) -> dict:
        return {
            "zone": self.zone_id,
            "states": self._count_states(),
            "total_q_values": self._count_actions(),
            "epsilon": round(self.epsilon, 4),
            "alpha": self.alpha,
            "gamma": self.gamma,
            "steps": self._step_count,
            "memory_size": len(self.replay_memory),
            "memory_kb": self._memory_usage_kb(),
        }

    def choose_action(self, soil_moisture: float, temperature: float,
                      hour: int = None) -> int:
        """Epsilon-greedy: choisit une action pour l'etat courant."""
        if hour is None:
            hour = datetime.now().hour
        state = _to_buckets(soil_moisture, temperature, hour)

        if np.random.random() < self.epsilon:
            return int(np.random.randint(len(ACTION_LABELS)))
        q_vals = self.q_table[state]
        # Si tous les Q sont a 0 (etat jamais visite), exploration
        if np.all(q_vals == 0):
            return int(np.random.randint(len(ACTION_LABELS)))
        return int(np.argmax(q_vals))

    def step(self, soil_moisture: float, temperature: float,
             hour: int, action: int,
             next_soil_moisture: float, next_temperature: float,
             next_hour: int, reward: float) -> dict:
        """Execute une etape d'apprentissage."""
        state = _to_buckets(soil_moisture, temperature, hour)
        next_state = _to_buckets(next_soil_moisture, next_temperature, next_hour)

        self._step_count += 1

        # Experience replay memory
        self.replay_memory.append((state, action, reward, next_state))
        if len(self.replay_memory) > self.memory_size:
            self.replay_memory.pop(0)

        # Replay batch
        if len(self.replay_memory) >= self.batch_size:
            self._replay_batch()

        # Q-learning mise a jour directe
        td_target = reward + self.gamma * np.max(self.q_table[next_state])
        td_error = td_target - self.q_table[state][action]
        self.q_table[state][action] += self.alpha * td_error

        # Decroissance epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        return {
            "state": list(state),
            "action": action,
            "action_label": ACTION_LABELS[action],
            "reward": round(reward, 2),
            "td_error": round(float(td_error), 4),
            "epsilon": round(self.epsilon, 4),
        }

    def _replay_batch(self):
        """Apprentissage par experience replay."""
        indices = np.random.choice(
            len(self.replay_memory), self.batch_size, replace=False)
        for idx in indices:
            state, action, reward, next_state = self.replay_memory[idx]
            td_target = reward + self.gamma * np.max(self.q_table[next_state])
            td_error = td_target - self.q_table[state][action]
            self.q_table[state][action] += self.alpha * td_error

    def compute_reward(self, soil_moisture: float, temperature: float,
                       water_used_l: float = 0, energy_kwh: float = 0,
                       plant_health: float = 1.0) -> float:
        """Calcule la recompense: sante plantes + economie eau + economie energie.

        Args:
            soil_moisture: Humidite du sol en % (0-100)
            temperature: Temperature en °C
            water_used_l: Litres d'eau utilises dans le cycle
            energy_kwh: kWh d'energie consomme pour chauffage
            plant_health: Score de sante des plantes (0-1)
        """
        r = 0.0

        # Recompense pour humidite optimale (30-70%)
        if 30 <= soil_moisture <= 70:
            r += 10.0
        elif soil_moisture < 20 or soil_moisture > 80:
            r -= 5.0
        elif soil_moisture < 25 or soil_moisture > 75:
            r -= 2.0
        else:
            r += 5.0

        # Recompense pour temperature optimale (18-28°C)
        if 18 <= temperature <= 28:
            r += 8.0
        elif temperature < 10 or temperature > 35:
            r -= 5.0
        elif temperature < 15 or temperature > 32:
            r -= 2.0
        else:
            r += 4.0

        # Penalite consommation eau (normalisee)
        r -= water_used_l * 0.1

        # Penalite consommation energie
        r -= energy_kwh * 0.05

        # Recompense sante plantes
        r += plant_health * 15.0

        return r

    def save(self):
        """Persiste Q-table et hyperparametres."""
        self._save_q_table()
        self._save_hyperparams()
        log.info("RLController sauvegarde", zone=self.zone_id,
                 states=self._count_states(), steps=self._step_count)

    def log_transition(self, entry: dict):
        """Enregistre une transition dans l'historique."""
        with open(self._history_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def history(self, limit: int = 100) -> list[dict]:
        """Lit l'historique des transitions recentes."""
        p = self._history_path()
        if not p.exists():
            return []
        lines = p.read_text(encoding="utf-8").strip().split("\n")
        return [json.loads(l) for l in lines[-limit:]]

    def get_best_action(self, soil_moisture: float, temperature: float,
                        hour: int = None) -> dict:
        """Retourne la meilleure action sans exploration."""
        if hour is None:
            hour = datetime.now().hour
        state = _to_buckets(soil_moisture, temperature, hour)
        q_vals = self.q_table[state]
        action = int(np.argmax(q_vals))
        return {
            "state": list(state),
            "action": action,
            "action_label": ACTION_LABELS[action],
            "q_values": q_vals.tolist(),
            "max_q": round(float(q_vals[action]), 4),
        }

    def reset_epsilon(self):
        """Reset epsilon pour re-exploration."""
        self.epsilon = DEFAULT_EPSILON
        log.info("Epsilon reset", zone=self.zone_id)

    def apply_action_to_geothermal(self, action: int,
                                    current_valve_pct: float,
                                    current_setpoint: float) -> dict:
        """Traduit une action RL en commandes pour geothermal.

        Returns:
            dict avec valve_pct et setpoint ajustes.
        """
        valve_pct = current_valve_pct
        setpoint = current_setpoint

        if action == IRR_INCREASE:
            valve_pct = min(100, current_valve_pct + 10)
        elif action == IRR_DECREASE:
            valve_pct = max(0, current_valve_pct - 10)
        elif action == IRR_MAINTAIN:
            pass  # inchangé

        if action == HEAT_INCREASE:
            setpoint = min(35, current_setpoint + 1.0)
        elif action == HEAT_DECREASE:
            setpoint = max(5, current_setpoint - 1.0)
        elif action == HEAT_MAINTAIN:
            pass  # inchangé

        return {"valve_pct": valve_pct, "setpoint": setpoint}
