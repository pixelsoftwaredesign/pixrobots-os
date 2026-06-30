# Pixel OS — Copyright 2026
# Free License — Verifiable and Reliable for Internet Users
# Pixel Software Design — Copyright 2026
"""Gestion centralisÃ©e de la configuration PixelOS."""

import os
import yaml
import json
from pathlib import Path
from typing import Any, Optional


_PKG_DIR = Path(__file__).resolve().parent.parent.parent  # pixelos/

_ENV_CONFIG = os.environ.get("PIXELOS_CONFIG", "")
CONFIG_PATHS = [
    p for p in [
        _ENV_CONFIG,
        "/etc/pixelos/pixelos.yaml",
        "/usr/local/etc/pixelos/pixelos.yaml",
        str(_PKG_DIR / "config" / "pixelos.yaml"),
        "./config/pixelos.yaml",
        os.path.expanduser("~/.pixelos.yaml"),
    ] if p
]


class PixelOSConfig:
    """Configuration hiÃ©rarchique fusionnÃ©e."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or self._find_config()
        self.data = self._load(self.path)
        self.nodes = self._load_nodes()
        self.alerts = self._load_alerts()

    def _find_config(self) -> str:
        for p in CONFIG_PATHS:
            if Path(p).exists():
                return p
        raise FileNotFoundError("Configuration PixelOS introuvable")

    def _load(self, path: str) -> dict:
        with open(path) as f:
            return yaml.safe_load(f) or {}

    def _load_nodes(self) -> dict:
        base = Path(self.path).parent
        for p in [base / "nodes.yaml", Path("./config/nodes.yaml")]:
            if p.exists():
                data = yaml.safe_load(open(p)) or {}
                return {n["id"]: n for n in data.get("nodes", [])}
        return {}

    def _load_alerts(self) -> list:
        base = Path(self.path).parent
        for p in [base / "alerts.yaml", Path("./config/alerts.yaml")]:
            if p.exists():
                data = yaml.safe_load(open(p)) or {}
                return data.get("alerts", [])
        return []

    def get(self, key: str, default: Any = None) -> Any:
        """AccÃ¨s hiÃ©rarchique: config.get('mqtt.port')"""
        parts = key.split(".")
        val = self.data
        for p in parts:
            if isinstance(val, dict):
                val = val.get(p)
            else:
                return default
        return val if val is not None else default

    def set(self, key: str, value: Any) -> None:
        parts = key.split(".")
        d = self.data
        for p in parts[:-1]:
            d = d.setdefault(p, {})
        d[parts[-1]] = value
        self._save()

    def _save(self) -> None:
        with open(self.path, "w") as f:
            yaml.dump(self.data, f, default_flow_style=False)

    def get_node(self, node_id: str) -> Optional[dict]:
        return self.nodes.get(node_id)

    def get_nodes_by_type(self, type_name: str) -> list:
        return [n for n in self.nodes.values() if n["type"] == type_name]

    def to_json(self) -> str:
        return json.dumps({
            "config": self.data,
            "nodes": self.nodes,
            "alerts": self.alerts,
        }, indent=2)
