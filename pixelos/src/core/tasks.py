# Pixel Software Design � Copyright 2026
"""PixelOS TaskManager - Gestion des tâches agricoles."""

import json
import uuid
import structlog
from pathlib import Path
from datetime import datetime, date

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "tasks"
STATUSES = ["todo", "in_progress", "done", "cancelled"]
PRIORITIES = ["low", "medium", "high", "urgent"]
CATEGORIES = [
    "plantation", "irrigation", "recolte", "traitement",
    "maintenance", "observation", "administration", "autre",
]


class TaskManager:
    """Gère les tâches agricoles PixelOS."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _path(self):
        return DATA_DIR / "tasks.json"

    def all(self) -> list[dict]:
        p = self._path()
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save(self, tasks: list[dict]):
        with open(self._path(), "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)

    def create(self, title: str, description: str = "",
               categorie: str = "autre", priorite: str = "medium",
               echeance: str = None, assigne: str = "",
               zone: str = "", plante: str = "") -> dict:
        tasks = self.all()
        t = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "description": description,
            "status": "todo",
            "categorie": categorie if categorie in CATEGORIES else "autre",
            "priorite": priorite if priorite in PRIORITIES else "medium",
            "echeance": echeance,
            "assigne": assigne,
            "zone": zone,
            "plante": plante,
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
            "completed": None,
        }
        tasks.insert(0, t)
        self._save(tasks)
        log.info("Tâche créée", id=t["id"], title=title)
        return t

    def get(self, task_id: str) -> dict | None:
        for t in self.all():
            if t["id"] == task_id:
                return t
        return None

    def update(self, task_id: str, **kwargs) -> dict | None:
        tasks = self.all()
        for t in tasks:
            if t["id"] == task_id:
                for k in ("title", "description", "categorie",
                          "priorite", "echeance", "assigne",
                          "zone", "plante"):
                    if k in kwargs and kwargs[k] is not None:
                        t[k] = kwargs[k]
                if "status" in kwargs and kwargs["status"] in STATUSES:
                    t["status"] = kwargs["status"]
                    if kwargs["status"] == "done":
                        t["completed"] = datetime.now().isoformat()
                t["updated"] = datetime.now().isoformat()
                self._save(tasks)
                return t
        return None

    def delete(self, task_id: str) -> bool:
        tasks = self.all()
        n = len(tasks)
        tasks = [t for t in tasks if t["id"] != task_id]
        if len(tasks) == n:
            return False
        self._save(tasks)
        return True

    def search(self, query: str = "", status: str = None,
               categorie: str = None, priorite: str = None,
               zone: str = None) -> list[dict]:
        q = query.lower() if query else ""
        results = []
        for t in self.all():
            if status and t["status"] != status:
                continue
            if categorie and t["categorie"] != categorie:
                continue
            if priorite and t["priorite"] != priorite:
                continue
            if zone and zone.lower() not in t.get("zone", "").lower():
                continue
            if q and q not in t["title"].lower() and q not in t.get("description", "").lower():
                continue
            results.append(t)
        return results

    def stats(self) -> dict:
        tasks = self.all()
        total = len(tasks)
        return {
            "total": total,
            "todo": sum(1 for t in tasks if t["status"] == "todo"),
            "in_progress": sum(1 for t in tasks if t["status"] == "in_progress"),
            "done": sum(1 for t in tasks if t["status"] == "done"),
            "cancelled": sum(1 for t in tasks if t["status"] == "cancelled"),
            "urgent": sum(1 for t in tasks if t["priorite"] == "urgent" and t["status"] != "done"),
            "en_retard": sum(1 for t in tasks
                             if t.get("echeance") and t["status"] not in ("done", "cancelled")
                             and t["echeance"] < date.today().isoformat()),
            "categories": {c: sum(1 for t in tasks if t["categorie"] == c) for c in CATEGORIES},
        }

    def list_by_status(self) -> dict[str, list[dict]]:
        tasks = self.all()
        return {s: [t for t in tasks if t["status"] == s] for s in STATUSES}

    def urgent(self) -> list[dict]:
        """Taches urgentes non terminees."""
        today = date.today().isoformat()
        return [t for t in self.all()
                if t["status"] not in ("done", "cancelled")
                and (t["priorite"] == "urgent"
                     or (t.get("echeance") and t["echeance"] <= today))]

    def overdue(self) -> list[dict]:
        """Taches en retard (echeance passee, non terminees)."""
        today = date.today().isoformat()
        return [t for t in self.all()
                if t.get("echeance") and t["echeance"] < today
                and t["status"] not in ("done", "cancelled")]

    def due_soon(self, hours: int = 24) -> list[dict]:
        """Taches dont l'echeance approche dans <hours> heures."""
        from datetime import timedelta
        seuil = (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d")
        today = date.today().isoformat()
        return [t for t in self.all()
                if t.get("echeance") and t["echeance"] <= seuil
                and t["echeance"] >= today
                and t["status"] not in ("done", "cancelled")]

    def alerts(self) -> list[dict]:
        """Genere la liste des alertes taches actives."""
        alerts = []
        seen = set()
        for t in self.urgent():
            if t["id"] in seen:
                continue
            seen.add(t["id"])
            overdue = t.get("echeance") and t["echeance"] < date.today().isoformat()
            alerts.append({
                "id": t["id"],
                "title": t["title"],
                "type": "overdue" if overdue else "urgent",
                "priorite": t["priorite"],
                "echeance": t.get("echeance"),
                "categorie": t.get("categorie", ""),
                "zone": t.get("zone", ""),
                "plante": t.get("plante", ""),
            })
        return alerts
