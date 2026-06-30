#!/usr/bin/env python3
"""
PixAuto — IA d'automatisation agricole PixelOS.

Traduit le langage naturel en:
  1. Smart Contracts (règles blockchain)
  2. Commandes GPIO via PixHAL (actionneurs physiques)
  3. Règles MQTT (IoT)
  4. Scripts pf (sécurité conditionnelle)
  5. Webhooks (services externes)
  6. Digital Twin sync (jumeau numérique)

Intégrations:
  - PixHAL : lecture capteurs réels + écriture actionneurs
  - Digital Twin : synchronisation état après chaque action
  - Scheduler : règles planifiées (cron-like)

Ex: "Si température > 30°C et pas de pluie, ouvre arrosage"
   → Smart Contract: if (temp > 30 && rain == false) { valve.open() }
   → PixHAL: gpio pin 17 HIGH
   → Digital Twin: sync actuator state
"""

import os
import json
import re
import hashlib
import time
import threading
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional


AUTO_DIR = "/var/db/pixelos/pixauto"
RULES_FILE = "automation_rules.json"
HISTORY_FILE = "automation_history.json"
SCHEDULER_INTERVAL = 60  # 60s

TRIGGER_PATTERNS = [
    (r"(si|when|if)\s+(.*?)\s*(alors|then|fait|do)\s+(.*)", "condition"),
    (r"(chaque|every)\s+(\d+)\s*(minute|heure|hour|jour|day)\s*(.*)", "schedule"),
    (r"(sur|on)\s+(evenement|event)\s+(\w+)\s*(.*)", "event"),
]

ACTION_KEYWORDS = {
    "ouvrir": "gpio:open", "fermer": "gpio:close",
    "allumer": "gpio:on", "eteindre": "gpio:off",
    "activer": "mqtt:publish", "desactiver": "mqtt:publish",
    "envoyer": "mqtt:publish", "notifier": "matrix:message",
    "alerter": "matrix:alert", "bloquer": "pf:block",
    "autoriser": "pf:pass", "demarrer": "service:start",
    "arreter": "service:stop", "appeler": "webhook:post",
    "appel": "webhook:post", "webhook": "webhook:post",
    "synchroniser": "digital_twin:sync",
    "sync": "digital_twin:sync",
}

SENSOR_KEYWORDS = {
    "temperature": "temp", "humidite": "humidity",
    "pression": "pressure", "lumiere": "light",
    "luminosite": "light", "vent": "wind",
    "pluie": "rain", "sol": "soil_moisture",
    "ph": "ph", "co2": "co2",
}


class PixAuto:
    def __init__(self):
        self._ensure_dirs()
        self._load_rules()
        self._load_history()
        self.triggered_count = 0
        self._pixhal = None
        self._twin = None
        self._start_scheduler()

    def _ensure_dirs(self):
        Path(AUTO_DIR).mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        return str(Path(AUTO_DIR) / name)

    def _load_rules(self):
        path = self._path(RULES_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.rules = json.load(f)
                return
            except Exception:
                pass
        self.rules = []

    def _save_rules(self):
        with open(self._path(RULES_FILE), "w") as f:
            json.dump(self.rules, f, indent=2)

    def _load_history(self):
        path = self._path(HISTORY_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.history = json.load(f)
                return
            except Exception:
                pass
        self.history = []

    def _save_history(self):
        with open(self._path(HISTORY_FILE), "w") as f:
            json.dump(self.history[-1000:], f, indent=2)

    # ── PixHAL integration ──────────────────────────────

    def _get_pixhal(self):
        if self._pixhal is None:
            try:
                from core.pixhal.pixhal import PixHAL
                self._pixhal = PixHAL()
            except Exception:
                pass
        return self._pixhal

    def _read_real_sensors(self) -> dict:
        """Lit les valeurs réelles des capteurs via PixHAL."""
        hal = self._get_pixhal()
        if not hal:
            return {}
        try:
            devices = hal.list_devices()
            values = {}
            for sid in devices.get("sensors", {}):
                reading = hal.read_sensor(sid)
                if reading and "error" not in reading:
                    for key in ("temperature", "humidity", "light", "pressure"):
                        if key in reading:
                            values[sid] = reading[key]
                            values[key] = reading[key]
            return values
        except Exception:
            return {}

    def _execute_via_pixhal(self, action: dict) -> dict:
        """Exécute une action via PixHAL."""
        hal = self._get_pixhal()
        if not hal:
            return {"type": action.get("type"), "error": "PixHAL not available", "simulated": True}

        atype = action.get("type", "")
        target = action.get("target", "")
        state = 1 if "on" in atype or "open" in atype else 0

        try:
            # Chercher l'actionneur correspondant dans PixHAL
            devices = hal.list_devices()
            for aid in devices.get("actuators", {}):
                if target in aid.lower():
                    return hal.write_actuator(aid, state)
            # Fallback : tentative directe
            return hal.write_actuator(target, state)
        except Exception as e:
            return {"type": "pixhal", "error": str(e)}

    # ── Digital Twin integration ─────────────────────────

    def _get_twin(self):
        if self._twin is None:
            try:
                from core.digital_twin.twin import DigitalTwin
                self._twin = DigitalTwin()
            except Exception:
                pass
        return self._twin

    def _sync_to_twin(self, rule_id: str, action: dict, result: dict):
        """Synchronise l'état vers le Digital Twin."""
        twin = self._get_twin()
        if not twin:
            return
        try:
            target = action.get("target", "unknown")
            twin_name = f"pixauto_{target}"
            # Créer le twin s'il n'existe pas
            twin.create(twin_name, "automation")
            twin_id = f"automation_{target}"

            state = "on" if "on" in action.get("type", "") or "open" in action.get("type", "") else "off"
            twin.sync_actuator(twin_id, target, state)
            twin.sync_state(twin_id, {
                "last_rule": rule_id,
                "last_action": action.get("type", ""),
                "last_result": str(result.get("status", "")),
                "triggered_at": datetime.now().isoformat(),
            })
        except Exception:
            pass

    # ── Webhook support ─────────────────────────────────

    def _execute_webhook(self, action: dict) -> dict:
        """Exécute un webhook POST/GET."""
        target = action.get("target", "")
        params = action.get("params", {})
        url = params.get("url", target)

        if not url.startswith("http"):
            return {"type": "webhook", "error": "no URL", "simulated": True}

        try:
            payload = json.dumps({"action": action.get("type", ""),
                                   "target": target,
                                   "ts": datetime.now().isoformat()}).encode()
            req = urllib.request.Request(url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                return {"type": "webhook", "url": url, "status": resp.status, "body": resp.read()[:200]}
        except Exception as e:
            return {"type": "webhook", "error": str(e)}

    # ── NL parsing ────────────────────────────────────────

    def parse_natural_language(self, text: str) -> dict:
        text = text.strip()
        result = {"original": text, "trigger": None, "condition": None,
                  "action": None, "actions": [], "confidence": 0.0}

        for pattern, ptype in TRIGGER_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                if ptype == "condition":
                    result["trigger"] = {"type": "condition", "raw": m.group(2)}
                    result["action"] = m.group(3)
                    result["condition"] = self._parse_condition(m.group(2))
                elif ptype == "schedule":
                    result["trigger"] = {
                        "type": "schedule",
                        "interval": int(m.group(2)),
                        "unit": m.group(3),
                    }
                elif ptype == "event":
                    result["trigger"] = {"type": "event", "event": m.group(3)}
                result["actions"] = self._parse_actions(result.get("action", m.group(4) if ptype == "event" else m.group(3)))
                break

        if not result["trigger"]:
            result["actions"] = self._parse_actions(text)

        result["confidence"] = self._compute_confidence(result)
        return result

    def _parse_condition(self, raw: str) -> dict:
        cond = {"raw": raw, "clauses": []}
        parts = re.split(r"\s+(et|and|ou|or)\s+", raw, flags=re.IGNORECASE)
        for part in parts:
            part = part.strip()
            if part.lower() in ("et", "and", "ou", "or"):
                cond["clauses"].append({"operator": part.lower()})
                continue
            m = re.match(r"(.+?)\s*(>|<|>=|<=|==|!=|=|depasse|descend|atteint)\s*(.+)", part, re.IGNORECASE)
            if m:
                sensor = self._map_sensor(m.group(1).strip())
                op = self._map_operator(m.group(2))
                val = self._parse_value(m.group(3).strip())
                cond["clauses"].append({"sensor": sensor, "operator": op, "value": val})
        return cond

    def _parse_actions(self, raw: str) -> list:
        if not raw:
            return []
        actions = []
        for part in re.split(r"\s*(puis|then|et aussi|and also)\s*", raw, flags=re.IGNORECASE):
            part = part.strip()
            action_type = "unknown"
            for kw, atype in ACTION_KEYWORDS.items():
                if kw in part.lower():
                    action_type = atype
                    break
            target = self._extract_target(part)
            actions.append({
                "raw": part[:100],
                "type": action_type,
                "target": target,
                "params": self._extract_params(part),
            })
        return actions

    def _map_sensor(self, text: str) -> str:
        text = text.lower().strip()
        for kw, mapped in SENSOR_KEYWORDS.items():
            if kw in text:
                return mapped
        return text

    def _map_operator(self, op: str) -> str:
        mapping = {
            ">": "gt", "<": "lt", ">=": "gte", "<=": "lte",
            "==": "eq", "!=": "neq", "=": "eq",
            "depasse": "gt", "descend": "lt", "atteint": "eq",
        }
        return mapping.get(op.strip().lower(), op.strip())

    def _parse_value(self, text: str) -> dict:
        m = re.search(r"(\d+\.?\d*)\s*(°C|°F|%|mm|hPa|lx|km/h|ppm)?", text)
        if m:
            return {"value": float(m.group(1)), "unit": m.group(2) or ""}
        if text.lower() in ("vrai", "true", "oui", "yes", "on"):
            return {"value": True}
        if text.lower() in ("faux", "false", "non", "no", "off"):
            return {"value": False}
        return {"value": text}

    def _extract_target(self, text: str) -> str:
        for kw in ["vanne", "pompe", "ventilateur", "lumiere", "chauffage",
                    "valve", "pump", "fan", "light", "heater", "servo",
                    "portail", "gate", "volet", "shutter"]:
            if kw in text.lower():
                return kw
        return "unknown"

    def _extract_params(self, text: str) -> dict:
        params = {}
        m = re.search(r"(\d+)\s*(secondes|minutes|heures|seconds|minutes|hours)", text, re.IGNORECASE)
        if m:
            params["duration"] = f"{m.group(1)} {m.group(2)}"
        m = re.search(r"(\d+)\s*%", text)
        if m:
            params["level"] = float(m.group(1))
        m = re.search(r"(https?://\S+)", text)
        if m:
            params["url"] = m.group(1)
        return params

    def _compute_confidence(self, result: dict) -> float:
        score = 0.0
        if result["trigger"]:
            score += 0.3
        if result.get("condition") and len(result["condition"].get("clauses", [])) > 0:
            score += 0.3
        if len(result.get("actions", [])) > 0:
            score += 0.3
        if result["actions"] and all(a["type"] != "unknown" for a in result["actions"]):
            score += 0.1
        return round(min(score, 1.0), 2)

    # ── Compile ───────────────────────────────────────────

    def compile(self, text: str) -> dict:
        parsed = self.parse_natural_language(text)
        rule = {
            "id": hashlib.sha256(f"{text}{datetime.now()}".encode()).hexdigest()[:12],
            "original": text,
            "parsed": parsed,
            "smart_contract": self._to_smart_contract(parsed) if parsed["confidence"] > 0.5 else None,
            "gpio_commands": self._to_gpio(parsed),
            "mqtt_topics": self._to_mqtt(parsed),
            "webhooks": self._to_webhooks(parsed),
            "created_at": datetime.now().isoformat(),
            "enabled": True,
            "execution_count": 0,
            "last_executed": "",
            "use_pixhal": True,
            "sync_twin": True,
        }
        return rule

    def _to_smart_contract(self, parsed: dict) -> str:
        sc = []
        if parsed.get("condition"):
            sc.append("// Condition: " + parsed["condition"]["raw"])
            clauses = parsed["condition"].get("clauses", [])
            if clauses:
                sc.append("if (")
                for i, c in enumerate(clauses):
                    if c.get("operator") in ("et", "and"):
                        sc.append(" && ")
                    elif c.get("operator") in ("ou", "or"):
                        sc.append(" || ")
                    else:
                        sensor = c.get("sensor", "x")
                        op = c.get("operator", "gt")
                        val = c.get("value", {}).get("value", 0)
                        sc.append(f"{sensor} {self._op_js(op)} {val}")
                sc.append(") {")
        for a in parsed.get("actions", []):
            sc.append(f"  // {a['type']}: {a['target']}")
            sc.append(f"  {a['target']}.exec({json.dumps(a['params'])});")
        if parsed.get("condition"):
            sc.append("}")
        return "\n".join(sc)

    def _to_gpio(self, parsed: dict) -> list:
        cmds = []
        for a in parsed.get("actions", []):
            if a["type"].startswith("gpio:"):
                pin = self._target_to_pin(a.get("target", ""))
                state = 1 if "on" in a["type"] or "open" in a["type"] else 0
                cmds.append({"pin": pin, "state": state, "action": a["type"]})
            elif a["type"] == "unknown":
                pin = self._target_to_pin(a.get("target", ""))
                state = 1
                cmds.append({"pin": pin, "state": state, "action": "gpio:on", "inferred": True})
        return cmds

    def _to_mqtt(self, parsed: dict) -> list:
        topics = []
        for a in parsed.get("actions", []):
            if a["type"].startswith("mqtt:"):
                topic = f"farm/actuator/{a.get('target', 'unknown')}/set"
                payload = "1" if "on" in a["type"] or "open" in a["type"] else "0"
                topics.append({"topic": topic, "payload": payload})
        return topics

    def _to_webhooks(self, parsed: dict) -> list:
        hooks = []
        for a in parsed.get("actions", []):
            if a["type"].startswith("webhook:"):
                url = a.get("params", {}).get("url", "")
                hooks.append({"url": url, "method": "POST"})
        return hooks

    def _target_to_pin(self, target: str) -> int:
        mapping = {"vanne": 17, "valve": 17, "pompe": 18, "pump": 18,
                   "ventilateur": 22, "fan": 22, "lumiere": 23, "light": 23,
                   "chauffage": 24, "heater": 24, "servo": 25,
                   "portail": 27, "gate": 27, "volet": 26, "shutter": 26}
        return mapping.get(target.lower(), 0)

    def _op_js(self, op: str) -> str:
        return {"gt": ">", "lt": "<", "gte": ">=", "lte": "<=",
                "eq": "===", "neq": "!=="}.get(op, "===")

    # ── Rule management ───────────────────────────────────

    def add_rule(self, text: str) -> dict:
        rule = self.compile(text)
        if rule["parsed"]["confidence"] >= 0.3:
            self.rules.append(rule)
            self._save_rules()
            return {"status": "added", "rule": rule}
        return {"status": "low_confidence", "rule": rule}

    def get_rules(self) -> list:
        return self.rules

    def get_rule(self, rule_id: str) -> Optional[dict]:
        for r in self.rules:
            if r["id"] == rule_id:
                return r
        return None

    def toggle_rule(self, rule_id: str) -> dict:
        for r in self.rules:
            if r["id"] == rule_id:
                r["enabled"] = not r.get("enabled", True)
                self._save_rules()
                return {"status": "toggled", "enabled": r["enabled"]}
        return {"status": "not_found"}

    def delete_rule(self, rule_id: str) -> dict:
        for i, r in enumerate(self.rules):
            if r["id"] == rule_id:
                del self.rules[i]
                self._save_rules()
                return {"status": "deleted"}
        return {"status": "not_found"}

    def update_rule(self, rule_id: str, updates: dict) -> dict:
        for r in self.rules:
            if r["id"] == rule_id:
                for k, v in updates.items():
                    if k in ("enabled", "use_pixhal", "sync_twin", "original"):
                        r[k] = v
                self._save_rules()
                return {"status": "updated", "rule": r}
        return {"status": "not_found"}

    # ── Batch operations ──────────────────────────────────

    def import_rules(self, rules_data: list) -> dict:
        count = 0
        for r in rules_data:
            if r.get("original"):
                self.add_rule(r["original"])
                count += 1
        return {"status": "imported", "count": count}

    def export_rules(self) -> list:
        return [{
            "id": r["id"],
            "original": r["original"],
            "created_at": r["created_at"],
            "enabled": r.get("enabled", True),
            "parsed": r.get("parsed", {}),
        } for r in self.rules]

    # ── Execution ─────────────────────────────────────────

    def execute_rule(self, rule_id: str, sensor_values: dict = None) -> dict:
        rule = self.get_rule(rule_id)
        if not rule or not rule.get("enabled", False):
            return {"status": "skipped", "reason": "not found or disabled"}

        parsed = rule.get("parsed", {})
        cond = parsed.get("condition", {})

        # Si des valeurs capteurs sont fournies, les utiliser; sinon lire via PixHAL
        if sensor_values is None:
            sensor_values = self._read_real_sensors()

        triggered = False
        if cond and sensor_values:
            triggered = self._evaluate_condition(cond, sensor_values)
        else:
            triggered = True

        results = []
        if triggered:
            for a in parsed.get("actions", []):
                result = self._execute_action(a, rule_id)
                results.append(result)
            self.triggered_count += 1
            rule["execution_count"] = (rule.get("execution_count", 0) + 1)
            rule["last_executed"] = datetime.now().isoformat()
            self._save_rules()
            self.history.append({
                "rule_id": rule_id,
                "triggered_at": datetime.now().isoformat(),
                "sensor_values": sensor_values,
                "results": results,
            })
            self._save_history()

        return {"triggered": triggered, "results": results, "sensors_used": sensor_values}

    def _evaluate_condition(self, cond: dict, sensors: dict) -> bool:
        clauses = cond.get("clauses", [])
        if not clauses:
            return True
        result = True
        current_op = "et"
        for c in clauses:
            if "operator" in c:
                current_op = c["operator"]
                continue
            sensor = c.get("sensor", "")
            op = c.get("operator", "gt")
            val = c.get("value", {}).get("value", 0)
            actual = sensors.get(sensor)
            if actual is None:
                continue
            check = self._compare(actual, op, val)
            if current_op in ("et", "and"):
                result = result and check
            else:
                result = result or check
        return result

    def _compare(self, actual, op, expected):
        try:
            actual = float(actual)
            expected = float(expected)
            return {"gt": actual > expected, "lt": actual < expected,
                    "gte": actual >= expected, "lte": actual <= expected,
                    "eq": actual == expected, "neq": actual != expected}.get(op, False)
        except (ValueError, TypeError):
            return str(actual) == str(expected)

    def _execute_action(self, action: dict, rule_id: str = "") -> dict:
        atype = action.get("type", "unknown")
        target = action.get("target", "unknown")

        try:
            if atype.startswith("gpio:"):
                # Essayer PixHAL d'abord
                result = self._execute_via_pixhal(action)
                if result.get("simulated"):
                    # Fallback: commande directe
                    pin = self._target_to_pin(target)
                    state = 1 if "on" in atype else 0
                    if os.name != "nt":
                        cmd = ["gpioctl", str(pin), str(state)]
                        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                        result = {"type": "gpio", "output": r.stdout, "pin": pin, "state": state}
                    else:
                        result = {"type": "gpio", "simulated": True, "pin": pin, "state": state}

            elif atype.startswith("mqtt:"):
                topic = f"farm/actuator/{target}/set"
                payload = "1" if "on" in atype else "0"
                if os.name != "nt":
                    cmd = ["mosquitto_pub", "-t", topic, "-m", payload]
                    subprocess.run(cmd, timeout=5)
                result = {"type": "mqtt", "topic": topic, "payload": payload}

            elif atype.startswith("webhook:"):
                result = self._execute_webhook(action)

            elif atype.startswith("digital_twin:"):
                result = self._sync_to_twin(rule_id, action, {"status": "synced"})
                result = {"type": "digital_twin", "target": target, "synced": True}

            elif atype.startswith("matrix:"):
                result = {"type": "matrix", "message": f"Action: {target}", "sent": True}

            elif atype.startswith("pf:"):
                rule = "block" if "block" in atype else "pass"
                result = {"type": "pf", "rule": rule, "applied": True}

            elif atype.startswith("service:"):
                result = {"type": "service", "target": target, "simulated": True}

            else:
                # Essayer PixHAL pour les types non reconnus
                result = self._execute_via_pixhal(action)
                if result.get("simulated"):
                    result = {"type": "unknown", "target": target, "simulated": True}

            # Sync vers Digital Twin
            if result and not result.get("error"):
                self._sync_to_twin(rule_id, action, result)

            return result
        except Exception as e:
            return {"type": atype, "error": str(e)}

    # ── Schedule-based execution ────────────────────────

    def _start_scheduler(self):
        def loop():
            while True:
                time.sleep(SCHEDULER_INTERVAL)
                try:
                    self._check_scheduled_rules()
                except Exception:
                    pass
        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _check_scheduled_rules(self):
        """Vérifie les règles planifiées et les exécute si l'intervalle est écoulé."""
        now = time.time()
        for rule in self.rules:
            if not rule.get("enabled", True):
                continue
            parsed = rule.get("parsed", {})
            trigger = parsed.get("trigger", {})
            if trigger.get("type") != "schedule":
                continue
            interval = trigger.get("interval", 0)
            unit = trigger.get("unit", "minute")
            if interval <= 0:
                continue
            seconds = self._parse_interval(interval, unit)
            last_exec = rule.get("last_executed", "")
            if last_exec:
                try:
                    last_ts = datetime.fromisoformat(last_exec).timestamp()
                    if now - last_ts < seconds:
                        continue
                except Exception:
                    pass
            # Exécuter la règle planifiée
            sensors = self._read_real_sensors()
            self.execute_rule(rule["id"], sensors)

    @staticmethod
    def _parse_interval(value: int, unit: str) -> int:
        unit = unit.lower()
        if unit in ("seconde", "second", "seconds", "secondes"):
            return value
        if unit in ("minute", "minutes"):
            return value * 60
        if unit in ("heure", "hours", "hour", "heures"):
            return value * 3600
        if unit in ("jour", "day", "days", "jours"):
            return value * 86400
        return value * 60

    # ── History ────────────────────────────────────────────

    def get_history(self, limit: int = 100) -> list:
        return self.history[-limit:]

    def clear_history(self) -> dict:
        self.history = []
        self._save_history()
        return {"status": "cleared"}

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> dict:
        types = set()
        for r in self.rules:
            for a in r.get("parsed", {}).get("actions", []):
                at = a.get("type", "unknown")
                if isinstance(at, str):
                    types.add(at)
        hal = self._get_pixhal()
        twin = self._get_twin()
        return {
            "total_rules": len(self.rules),
            "enabled_rules": sum(1 for r in self.rules if r.get("enabled")),
            "triggered_count": self.triggered_count,
            "history_size": len(self.history),
            "action_types": list(types),
            "pixhal_available": hal is not None,
            "digital_twin_available": twin is not None,
            "scheduled_rules": sum(1 for r in self.rules
                                   if r.get("parsed", {}).get("trigger", {}).get("type") == "schedule"),
            "scheduler_running": True,
        }
