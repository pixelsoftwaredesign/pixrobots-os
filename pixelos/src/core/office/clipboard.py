# Pixel Software Design � Copyright 2026
"""Pixel Clipboard — Presse-papier unifié entre les apps Pixel Office.

Permet de copier-coller entre Pixel Access → Pixel Word → Pixel Excel
sans perte de données ni de formatage.
"""

from __future__ import annotations
import json, time, hashlib
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class PixelClipboardData:
    """Élément dans le presse-papier Pixel."""
    data_type: str        # text, table, chart, database_row, sensor_data
    source_app: str       # access, word, excel
    content: dict
    format: str = "pixel-clip-v1"
    metadata: dict = None
    timestamp: str = ""
    clipboard_id: str = ""


class PixelClipboard:
    """Presse-papier intelligent inter-applications.

    Supporte:
      - Texte enrichi (Word → Excel)
      - Lignes de base de données (Access → Word/Excel)
      - Données de capteurs IoT (Access → Excel)
      - Graphiques (Excel → Word)
    """

    def __init__(self):
        self._data: Optional[PixelClipboardData] = None

    def copy(self, data_type: str, source_app: str,
             content: dict, metadata: dict = None) -> PixelClipboardData:
        """Copie des données dans le presse-papier."""
        clip = PixelClipboardData(
            data_type=data_type,
            source_app=source_app,
            content=self._normalize(data_type, content),
            metadata=metadata or {},
            timestamp=datetime.now().isoformat(),
            clipboard_id=hashlib.sha256(
                f"{data_type}{source_app}{time.time()}".encode()
            ).hexdigest()[:16],
        )
        self._data = clip
        return clip

    def paste(self) -> Optional[PixelClipboardData]:
        """Colle le dernier élément copié."""
        return self._data

    def paste_as(self, target_type: str) -> Optional[dict]:
        """Colle en convertissant vers le format cible."""
        if not self._data:
            return None
        return self._convert(self._data, target_type)

    def _normalize(self, data_type: str, content: dict) -> dict:
        """Normalise le contenu selon le type."""
        if data_type == "table":
            return {
                "headers": content.get("headers", []),
                "rows": content.get("rows", []),
                "total_rows": len(content.get("rows", [])),
                "total_columns": len(content.get("headers", [])),
            }
        elif data_type == "database_row":
            return {
                "table": content.get("table", ""),
                "columns": content.get("columns", []),
                "values": content.get("values", []),
                "primary_key": content.get("primary_key", ""),
            }
        elif data_type == "sensor_data":
            return {
                "sensor_id": content.get("sensor_id", ""),
                "metric": content.get("metric", ""),
                "values": content.get("values", []),
                "unit": content.get("unit", ""),
                "period": content.get("period", ""),
            }
        elif data_type == "chart":
            return {
                "chart_type": content.get("chart_type", "line"),
                "labels": content.get("labels", []),
                "datasets": content.get("datasets", []),
                "title": content.get("title", ""),
            }
        elif data_type == "text":
            return {
                "text": content.get("text", ""),
                "format": content.get("format", "plain"),
                "html": content.get("html", ""),
            }
        return content

    def _convert(self, clip: PixelClipboardData,
                 target_type: str) -> Optional[dict]:
        """Convertit entre formats."""
        if clip.data_type == target_type:
            return clip.content

        # Table → Texte
        if clip.data_type == "table" and target_type == "text":
            rows = []
            headers = clip.content.get("headers", [])
            if headers:
                rows.append(" | ".join(headers))
                rows.append("-" * sum(len(h) + 3 for h in headers))
            for row in clip.content.get("rows", []):
                rows.append(" | ".join(str(c) for c in row))
            return {"text": "\n".join(rows)}

        # Database row → Table
        if clip.data_type == "database_row" and target_type == "table":
            return {
                "headers": clip.content.get("columns", []),
                "rows": [clip.content.get("values", [])],
            }

        # Sensor data → Table
        if clip.data_type == "sensor_data" and target_type == "table":
            values = clip.content.get("values", [])
            return {
                "headers": ["Temps", f"{clip.content.get('metric','Valeur')} ({clip.content.get('unit','')})"],
                "rows": [[v.get("time", ""), v.get("value", 0)] for v in values],
            }

        # Text → Table (essaye de parser TSV)
        if clip.data_type == "text" and target_type == "table":
            lines = clip.content.get("text", "").strip().split("\n")
            if len(lines) >= 2:
                headers = lines[0].split("\t")
                rows = [l.split("\t") for l in lines[1:]]
                return {"headers": headers, "rows": rows}

        return None

    def clear(self):
        self._data = None

    def has_data(self) -> bool:
        return self._data is not None

    def peek(self) -> Optional[dict]:
        if not self._data:
            return None
        return asdict(self._data)


clipboard = PixelClipboard()
