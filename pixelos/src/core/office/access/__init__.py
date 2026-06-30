# Pixel Software Design � Copyright 2026
"""Pixel Access — Interface base de données agricole.

Connectée directement à bgdatasys et aux capteurs IoT.
Permet de:
  - Naviguer les tables agricoles (produits, plantations, récoltes, capteurs)
  - Exécuter des requêtes SQL
  - Exporter vers Pixel Word/Excel via le Clipboard
  - Synchroniser avec le réseau fédéré
"""

from __future__ import annotations
import json, sqlite3, csv, io
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


ACCESS_DIR = Path("/var/db/pixelos/office/access")
ACCESS_DB = ACCESS_DIR / "pixel_access.db"
SCHEMAS_DIR = ACCESS_DIR / "schemas"
REPORTS_DIR = ACCESS_DIR / "reports"


@dataclass
class AccessTable:
    """Table agricole dans Pixel Access."""
    name: str
    schema: dict
    row_count: int = 0
    description: str = ""
    category: str = "general"   # production, sensors, inventory, federation
    synced: bool = False


@dataclass
class AccessQuery:
    """Requête sauvegardée."""
    query_id: str
    name: str
    sql: str
    description: str = ""
    created: str = ""
    author: str = ""


class PixelAccess:
    """Interface de base de données agricole."""

    SCHEMAS = {
        "produits": {
            "columns": [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("nom", "TEXT NOT NULL"),
                ("variete", "TEXT"),
                ("categorie", "TEXT"),
                ("cycle", "TEXT"),
                ("besoin_eau", "TEXT"),
                ("saison_plantation", "TEXT"),
                ("duree_cycle_jours", "INTEGER"),
                ("rendement_estime_kg", "REAL"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
            "description": "Catalogue des produits agricoles",
            "category": "production",
        },
        "plantations": {
            "columns": [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("product_id", "INTEGER REFERENCES produits(id)"),
                ("espace_id", "TEXT"),
                ("sub_zone", "TEXT"),
                ("quantite_plants", "INTEGER"),
                ("surface_m2", "REAL"),
                ("date_plantation", "DATE"),
                ("date_recolte_estimee", "DATE"),
                ("statut", "TEXT DEFAULT 'en_cours'"),
                ("notes", "TEXT"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
            "description": "Registre des plantations en cours",
            "category": "production",
        },
        "recoltes": {
            "columns": [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("plantation_id", "INTEGER REFERENCES plantations(id)"),
                ("date_recolte", "DATE"),
                ("poids_kg", "REAL"),
                ("qualite", "TEXT"),
                ("prix_unitaire", "REAL"),
                ("cout_total", "REAL"),
                ("notes", "TEXT"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
            "description": "Registre des récoltes",
            "category": "production",
        },
        "capteurs": {
            "columns": [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("nom", "TEXT"),
                ("type", "TEXT"),
                ("espace_id", "TEXT"),
                ("bus", "TEXT"),
                ("adresse", "TEXT"),
                ("unite", "TEXT"),
                ("intervalle_secondes", "INTEGER"),
                ("actif", "INTEGER DEFAULT 1"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
            "description": "Catalogue des capteurs IoT déployés",
            "category": "sensors",
        },
        "mesures": {
            "columns": [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("capteur_id", "INTEGER REFERENCES capteurs(id)"),
                ("valeur", "REAL"),
                ("unite", "TEXT"),
                ("timestamp", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
            "description": "Mesures des capteurs (cache local)",
            "category": "sensors",
        },
        "espace": {
            "columns": [
                ("id", "TEXT PRIMARY KEY"),
                ("label", "TEXT"),
                ("type", "TEXT"),
                ("location", "TEXT"),
                ("description", "TEXT"),
                ("surface_m2", "REAL"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
            "description": "Espaces agricoles (serres, champs, vergers)",
            "category": "inventory",
        },
        "especes_biodiversite": {
            "columns": [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("nom_scientifique", "TEXT UNIQUE"),
                ("nom_commun", "TEXT"),
                ("famille", "TEXT"),
                ("statut_conservation", "TEXT"),
                ("pays_origine", "TEXT"),
                ("biome", "TEXT"),
                ("fingerprint", "TEXT"),
                ("confidentialite", "TEXT DEFAULT 'public'"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
            "description": "Espèces enregistrées sur le réseau fédéré",
            "category": "federation",
        },
        "membres_federation": {
            "columns": [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("node_id", "TEXT UNIQUE"),
                ("nickname", "TEXT"),
                ("pays", "TEXT"),
                ("role", "TEXT DEFAULT 'member'"),
                ("derniere_connexion", "TIMESTAMP"),
                ("especes_partagees", "INTEGER DEFAULT 0"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
            "description": "Membres du réseau fédéré PixelOS",
            "category": "federation",
        },
    }

    def __init__(self):
        os.makedirs(ACCESS_DIR, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialise la base de données avec les schémas agricoles."""
        conn = sqlite3.connect(str(ACCESS_DB))
        for name, schema in self.SCHEMAS.items():
            cols = ", ".join(f"{c[0]} {c[1]}" for c in schema["columns"])
            conn.execute(f"CREATE TABLE IF NOT EXISTS {name} ({cols})")
        conn.commit()
        conn.close()

    # ─── Tables ───────────────────────────────────────

    def list_tables(self) -> list[dict]:
        """Liste toutes les tables agricoles disponibles."""
        conn = sqlite3.connect(str(ACCESS_DB))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = []
        for row in cursor.fetchall():
            name = row[0]
            schema = self.SCHEMAS.get(name, {})
            count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            tables.append({
                "name": name,
                "row_count": count,
                "description": schema.get("description", ""),
                "category": schema.get("category", "general"),
                "columns": [c[0] for c in schema.get("columns", [])],
            })
        conn.close()
        return tables

    def get_table(self, table_name: str, limit: int = 100,
                  offset: int = 0) -> Optional[dict]:
        """Récupère le contenu d'une table."""
        if table_name not in self.SCHEMAS:
            return None
        conn = sqlite3.connect(str(ACCESS_DB))
        schema = self.SCHEMAS[table_name]
        columns = [c[0] for c in schema["columns"]]

        total = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        cursor = conn.execute(f"SELECT * FROM {table_name} LIMIT ? OFFSET ?",
                              (limit, offset))
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return {
            "name": table_name,
            "columns": columns,
            "rows": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def insert(self, table_name: str, data: dict) -> Optional[dict]:
        """Insère une ligne dans une table agricole."""
        if table_name not in self.SCHEMAS:
            return None
        conn = sqlite3.connect(str(ACCESS_DB))
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        values = list(data.values())
        try:
            cursor = conn.execute(
                f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})",
                values)
            conn.commit()
            row_id = cursor.lastrowid
            conn.close()
            return {"status": "ok", "row_id": row_id, "table": table_name}
        except Exception as e:
            conn.close()
            return {"status": "error", "message": str(e)}

    def update(self, table_name: str, row_id: int,
               data: dict) -> dict:
        """Met à jour une ligne."""
        conn = sqlite3.connect(str(ACCESS_DB))
        sets = ", ".join(f"{k} = ?" for k in data.keys())
        values = list(data.values()) + [row_id]
        try:
            conn.execute(f"UPDATE {table_name} SET {sets} WHERE id = ?", values)
            conn.commit()
            conn.close()
            return {"status": "ok", "updated": conn.total_changes}
        except Exception as e:
            conn.close()
            return {"status": "error", "message": str(e)}

    def delete(self, table_name: str, row_id: int) -> dict:
        """Supprime une ligne."""
        conn = sqlite3.connect(str(ACCESS_DB))
        try:
            conn.execute(f"DELETE FROM {table_name} WHERE id = ?", (row_id,))
            conn.commit()
            conn.close()
            return {"status": "ok", "deleted": True}
        except Exception as e:
            conn.close()
            return {"status": "error", "message": str(e)}

    # ─── Requêtes ─────────────────────────────────────

    def execute_query(self, sql: str) -> dict:
        """Exécute une requête SQL arbitraire."""
        conn = sqlite3.connect(str(ACCESS_DB))
        try:
            cursor = conn.execute(sql)
            if sql.strip().upper().startswith("SELECT"):
                columns = [desc[0] for desc in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                result = {"columns": columns, "rows": rows, "total": len(rows)}
            else:
                conn.commit()
                result = {"affected": conn.total_changes, "status": "ok"}
            conn.close()
            return result
        except Exception as e:
            conn.close()
            return {"status": "error", "message": str(e)}

    def save_query(self, name: str, sql: str,
                   author: str = "", description: str = "") -> AccessQuery:
        """Sauvegarde une requête pour réutilisation."""
        import hashlib, time
        qid = hashlib.sha256(f"{name}{time.time()}".encode()).hexdigest()[:12]
        query = AccessQuery(
            query_id=qid, name=name, sql=sql,
            description=description, author=author,
            created=datetime.now().isoformat(),
        )
        os.makedirs(ACCESS_DIR, exist_ok=True)
        queries_file = ACCESS_DIR / "saved_queries.json"
        existing = json.load(open(queries_file)) if queries_file.exists() else []
        existing.append(asdict(query))
        with open(queries_file, "w") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        return query

    def list_queries(self) -> list[dict]:
        queries_file = ACCESS_DIR / "saved_queries.json"
        if not queries_file.exists():
            return []
        return json.load(open(queries_file))

    # ─── Export ───────────────────────────────────────

    def export_csv(self, table_name: str) -> Optional[str]:
        """Exporte une table en CSV."""
        data = self.get_table(table_name, limit=10000)
        if not data:
            return None
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(data["columns"])
        for row in data["rows"]:
            writer.writerow(row.values())
        return output.getvalue()

    def export_json(self, table_name: str) -> Optional[str]:
        data = self.get_table(table_name, limit=10000)
        if not data:
            return None
        return json.dumps(data["rows"], ensure_ascii=False, indent=2)

    def export_to_clipboard(self, table_name: str) -> Optional[dict]:
        """Copie une table dans le presse-papier Pixel (pour Word/Excel)."""
        data = self.get_table(table_name, limit=500)
        if not data:
            return None
        from core.office.clipboard import clipboard
        return clipboard.copy(
            data_type="table",
            source_app="access",
            content={"headers": data["columns"], "rows": [list(r.values()) for r in data["rows"]]},
            metadata={"table": table_name, "total_rows": data["total"]},
        )

    # ─── Statistiques ─────────────────────────────────

    def stats(self) -> dict:
        tables = self.list_tables()
        total_rows = sum(t["row_count"] for t in tables)
        return {
            "tables": len(tables),
            "total_rows": total_rows,
            "database_path": str(ACCESS_DB),
            "tables_detail": tables,
        }


access_db = PixelAccess()
