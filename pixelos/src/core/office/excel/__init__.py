"""Pixel Excel — Moteur de calcul et grille de tableur.

Fonctionnalités:
  - Grille infinie (virtuelle), format JSON
  - Moteur de calcul avec formules (SUM, AVG, MIN, MAX, COUNT, IF, etc.)
  - Graphiques intégrés (courbes, barres, camemberts)
  - Import données capteurs IoT en temps réel
  - Export vers Pixel Word / Pixel Access
"""

from __future__ import annotations
import json, re, math, statistics
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta

EXCEL_DIR = Path("/var/db/pixelos/office/excel")


@dataclass
class Cell:
    """Cellule de tableur."""
    value: Any = None
    formula: str = ""
    formatted: str = ""
    style: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class Sheet:
    """Feuille de calcul."""
    name: str = "Sheet1"
    cells: dict = field(default_factory=dict)  # "A1" -> Cell
    row_count: int = 100
    col_count: int = 26
    frozen_rows: int = 0
    frozen_cols: int = 0


@dataclass
class Chart:
    """Graphique intégré."""
    chart_id: str
    chart_type: str = "line"   # line, bar, pie, scatter, area
    title: str = ""
    data_range: str = ""       # ex: "A1:B10"
    labels_range: str = ""
    width: int = 400
    height: int = 300


class ExcelEngine:
    """Moteur de calcul Pixel Excel."""

    # Fonctions supportées
    FUNCTIONS = {
        "SUM": lambda args: sum(args),
        "AVG": lambda args: statistics.mean(args) if args else 0,
        "AVERAGE": lambda args: statistics.mean(args) if args else 0,
        "MIN": lambda args: min(args) if args else 0,
        "MAX": lambda args: max(args) if args else 0,
        "COUNT": lambda args: len([x for x in args if x is not None and x != ""]),
        "COUNTA": lambda args: len([x for x in args if x is not None]),
        "STDEV": lambda args: statistics.stdev(args) if len(args) > 1 else 0,
        "MEDIAN": lambda args: statistics.median(args) if args else 0,
        "ROUND": lambda args: round(args[0], int(args[1])) if len(args) >= 2 else args[0],
        "ABS": lambda args: abs(args[0]) if args else 0,
        "IF": lambda args: args[0] if args[0] else args[1] if len(args) >= 2 else "",
        "CONCAT": lambda args: "".join(str(a) for a in args),
        "UPPER": lambda args: str(args[0]).upper() if args else "",
        "LOWER": lambda args: str(args[0]).lower() if args else "",
        "LEN": lambda args: len(str(args[0])) if args else 0,
        "TODAY": lambda args: datetime.now().strftime("%Y-%m-%d"),
        "NOW": lambda args: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "YEAR": lambda args: int(str(args[0])[:4]) if args else 0,
        "MONTH": lambda args: int(str(args[0])[5:7]) if args and len(str(args[0])) >= 7 else 0,
        "DAY": lambda args: int(str(args[0])[8:10]) if args and len(str(args[0])) >= 10 else 0,
    }

    def __init__(self):
        os.makedirs(EXCEL_DIR, exist_ok=True)

    # ─── Grille ───────────────────────────────────────

    def create_sheet(self, name: str = "Sheet1",
                     rows: int = 100, cols: int = 26) -> Sheet:
        return Sheet(name=name, row_count=rows, col_count=cols)

    def _col_letter(self, n: int) -> str:
        """Convertit 0 -> A, 1 -> B, ..., 25 -> Z, 26 -> AA"""
        s = ""
        while n >= 0:
            s = chr(65 + n % 26) + s
            n = n // 26 - 1
        return s

    def _cell_ref(self, col: int, row: int) -> str:
        return f"{self._col_letter(col)}{row + 1}"

    def get_cell(self, sheet: Sheet, ref: str) -> Cell:
        if ref not in sheet.cells:
            sheet.cells[ref] = Cell()
        return sheet.cells[ref]

    def set_cell(self, sheet: Sheet, ref: str, value: Any = None,
                 formula: str = "") -> Cell:
        cell = self.get_cell(sheet, ref)
        cell.value = value
        cell.formula = formula
        cell.error = ""
        if formula:
            result = self.eval_formula(sheet, formula)
            if result.get("status") == "ok":
                cell.value = result["value"]
                cell.formatted = result.get("formatted", str(result["value"]))
            else:
                cell.error = result.get("message", "Erreur")
        else:
            cell.formatted = self._format_value(value)
        sheet.cells[ref] = cell
        return cell

    def _format_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            if value == int(value):
                return str(int(value))
            return f"{value:.2f}"
        return str(value)

    # ─── Moteur de formules ───────────────────────────

    def eval_formula(self, sheet: Sheet, formula: str) -> dict:
        """Évalue une formule Excel (=SUM(A1:A10))."""
        try:
            formula = formula.strip()
            if formula.startswith("="):
                formula = formula[1:]

            # Parser les fonctions
            for func_name, func_impl in self.FUNCTIONS.items():
                pattern = rf"{func_name}\((.*?)\)"
                match = re.search(pattern, formula, re.IGNORECASE)
                if match:
                    args_str = match.group(1)
                    args = self._parse_args(sheet, args_str)
                    try:
                        result = func_impl(args)
                        formula = formula.replace(match.group(0), str(result))
                    except Exception as e:
                        return {"status": "error", "message": f"{func_name}: {e}"}

            # Évaluer l'expression arithmétique restante
            try:
                result = eval(formula, {"__builtins__": {}}, {})
                formatted = result
                if isinstance(result, float):
                    formatted = round(result, 2)
                return {"status": "ok", "value": result, "formatted": str(formatted)}
            except:
                return {"status": "ok", "value": formula, "formatted": formula}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _parse_args(self, sheet: Sheet, args_str: str) -> list:
        """Parse les arguments d'une fonction: SUM(A1:A10) ou SUM(1,2,3)."""
        args = []
        for part in args_str.split(","):
            part = part.strip()
            if ":" in part:
                # Plage: A1:A10
                start, end = part.split(":")
                col_start = self._col_to_num(start[0])
                row_start = int(start[1:]) - 1
                col_end = self._col_to_num(end[0])
                row_end = int(end[1:]) - 1

                for r in range(row_start, row_end + 1):
                    for c in range(col_start, col_end + 1):
                        ref = self._cell_ref(c, r)
                        cell = self.get_cell(sheet, ref)
                        try:
                            val = cell.value
                            if val is not None and val != "":
                                args.append(float(val))
                        except:
                            pass
            else:
                # Valeur simple ou référence
                if part[0].isalpha() and part[0].isupper():
                    cell = self.get_cell(sheet, part)
                    try:
                        args.append(float(cell.value) if cell.value is not None else 0)
                    except:
                        args.append(0)
                else:
                    try:
                        args.append(float(part))
                    except:
                        args.append(part)
        return args

    def _col_to_num(self, col: str) -> int:
        """Convertit A -> 0, B -> 1, Z -> 25, AA -> 26"""
        result = 0
        for c in col:
            result = result * 26 + (ord(c.upper()) - 65)
        return result

    # ─── Import données ──────────────────────────────

    def import_sensor_data(self, sheet: Sheet, sensor_id: str,
                           metric: str = "", days: int = 7) -> dict:
        """Importe les données d'un capteur IoT dans la feuille."""
        try:
            from core.tsdb import tsdb
            data = tsdb.query_sensor(sensor_id, hours=days * 24)
            if not data:
                return {"imported": 0, "message": "Aucune donnée"}
            # En-têtes
            self.set_cell(sheet, "A1", "Timestamp")
            self.set_cell(sheet, "B1", metric or "Valeur")
            for i, row in enumerate(data[:1000], start=2):
                self.set_cell(sheet, f"A{i}", row.get("timestamp", ""))
                self.set_cell(sheet, f"B{i}", row.get("valeur", 0))
            return {"imported": len(data[:1000]), "sensor": sensor_id}
        except:
            return {"imported": 0, "message": "Erreur accès capteur"}

    def import_table(self, sheet: Sheet, table_name: str,
                     start_cell: str = "A1") -> dict:
        """Importe une table Pixel Access dans la feuille."""
        try:
            from core.office.access import access_db
            data = access_db.get_table(table_name, limit=500)
            if not data:
                return {"imported": 0, "message": "Table vide"}
            col_offset = ord(start_cell[0]) - 65
            row_offset = int(start_cell[1:]) - 1
            # En-têtes
            for j, col in enumerate(data["columns"]):
                ref = self._cell_ref(col_offset + j, row_offset)
                self.set_cell(sheet, ref, col)
            # Données
            for i, row in enumerate(data["rows"], start=1):
                for j, col in enumerate(data["columns"]):
                    ref = self._cell_ref(col_offset + j, row_offset + i)
                    self.set_cell(sheet, ref, row[col])
            return {"imported": len(data["rows"]), "table": table_name}
        except Exception as e:
            return {"imported": 0, "message": str(e)}

    # ─── Graphiques ──────────────────────────────────

    def create_chart(self, sheet: Sheet, chart_type: str = "line",
                     data_range: str = "", title: str = "") -> Chart:
        chart = Chart(
            chart_id=hashlib.sha256(f"{title}{datetime.now()}".encode()).hexdigest()[:12],
            chart_type=chart_type,
            title=title or f"Graphique {chart_type}",
            data_range=data_range,
        )
        if not hasattr(sheet, 'charts'):
            sheet.charts = []
        sheet.charts.append(asdict(chart))
        return chart

    def chart_data(self, sheet: Sheet, data_range: str) -> dict:
        """Extrait les données pour un graphique."""
        try:
            start, end = data_range.split(":")
            col_start = self._col_to_num(start[0])
            row_start = int(start[1:]) - 1
            col_end = self._col_to_num(end[0])
            row_end = int(end[1:]) - 1
            labels = []
            datasets = []
            for c in range(col_start, col_end + 1):
                series = []
                for r in range(row_start, row_end + 1):
                    ref = self._cell_ref(c, r)
                    cell = self.get_cell(sheet, ref)
                    series.append(cell.value)
                if c == col_start:
                    labels = [str(s) for s in series[1:]] if series else []
                else:
                    datasets.append({
                        "label": str(series[0]) if series else "",
                        "data": [float(s) if s else 0 for s in series[1:]],
                    })
            return {"labels": labels, "datasets": datasets}
        except:
            return {"labels": [], "datasets": []}

    # ─── Sérialisation ───────────────────────────────

    def to_dict(self, sheet: Sheet) -> dict:
        data = asdict(sheet)
        # Convertir les cellules en structure plate
        cells_data = {}
        for ref, cell in sheet.cells.items():
            cells_data[ref] = asdict(cell)
        data["cells"] = cells_data
        return data

    def from_dict(self, data: dict) -> Sheet:
        sheet = Sheet(
            name=data.get("name", "Sheet1"),
            row_count=data.get("row_count", 100),
            col_count=data.get("col_count", 26),
        )
        for ref, cell_data in data.get("cells", {}).items():
            sheet.cells[ref] = Cell(**cell_data)
        return sheet


import hashlib, os
excel_engine = ExcelEngine()
