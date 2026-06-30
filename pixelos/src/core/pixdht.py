#!/usr/bin/env python3
"""
PixDHT — PixNet Query Engine.

Couche requête distribuée au-dessus de PixDHT (core/pixnet/pixdht.py).
Ajoute:
  - Requêtes structurées (SQL-like) sur le réseau DHT
  - Indexation et recherche plein texte
  - Agrégation multi-pairs
  - Cache de requêtes
  - Export/import de données
"""

import os
import json
import time
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

DHT_DIR = "/var/db/pixelos/pixdht"
INDEX_FILE = "query_index.json"
CACHE_FILE = "query_cache.json"


class PixDHTQueryEngine:
    def __init__(self):
        self._ensure_dirs()
        self._load_index()
        self._load_cache()
        self._dht = None

    def _get_dht(self):
        if self._dht is None:
            try:
                from core.pixnet.pixdht import PixDHT
                self._dht = PixDHT()
            except Exception:
                pass
        return self._dht

    def _ensure_dirs(self):
        Path(DHT_DIR).mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        return str(Path(DHT_DIR) / name)

    def _load_index(self):
        path = self._path(INDEX_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.index = json.load(f)
                return
            except Exception:
                pass
        self.index = {}

    def _save_index(self):
        with open(self._path(INDEX_FILE), "w") as f:
            json.dump(self.index, f, indent=2)

    def _load_cache(self):
        path = self._path(CACHE_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.cache = json.load(f)
                return
            except Exception:
                pass
        self.cache = {}

    def _save_cache(self):
        with open(self._path(CACHE_FILE), "w") as f:
            json.dump(self.cache, f, indent=2)

    # ── Query execution ────────────────────────────────────

    def query(self, statement: str) -> dict:
        """Exécute une requête structurée.
        Syntaxe:
          SELECT <fields> FROM <namespace> [WHERE <conditions>] [LIMIT n]
        """
        start = time.time()
        parsed = self._parse_query(statement)
        if "error" in parsed:
            return {"status": "error", "error": parsed["error"], "query": statement}

        cache_key = hashlib.sha256(statement.encode()).hexdigest()
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached.get("ts", 0) < 60:
                return {"status": "cached", "query": statement, **cached["result"]}

        results = self._execute_query(parsed)
        elapsed = time.time() - start
        result = {
            "status": "ok",
            "query": statement,
            "parsed": parsed,
            "results": results,
            "count": len(results),
            "elapsed_s": round(elapsed, 3),
        }
        self.cache[cache_key] = {"result": result, "ts": time.time()}
        self._save_cache()
        return result

    def _parse_query(self, stmt: str) -> dict:
        stmt = stmt.strip()
        parsed = {}

        # SELECT
        m = re.search(r"SELECT\s+(.+?)\s+FROM\s+(\S+)", stmt, re.IGNORECASE)
        if not m:
            return {"error": "syntax: SELECT <fields> FROM <namespace>"}
        parsed["fields"] = [f.strip() for f in m.group(1).split(",")]
        parsed["namespace"] = m.group(2).lower()

        # WHERE
        m2 = re.search(r"WHERE\s+(.+)", stmt, re.IGNORECASE)
        if m2:
            parsed["where"] = self._parse_where(m2.group(1))

        # LIMIT
        m3 = re.search(r"LIMIT\s+(\d+)", stmt, re.IGNORECASE)
        parsed["limit"] = int(m3.group(1)) if m3 else 100

        return parsed

    def _parse_where(self, clause: str) -> list:
        conditions = []
        parts = re.split(r"\s+(AND|OR)\s+", clause, flags=re.IGNORECASE)
        for part in parts:
            part = part.strip()
            if part.upper() in ("AND", "OR"):
                conditions.append({"op": part.upper()})
                continue
            m = re.match(r"(\S+)\s*(=|!=|>|<|>=|<=|LIKE|IN)\s*(.+)", part, re.IGNORECASE)
            if m:
                conditions.append({
                    "field": m.group(1).strip(),
                    "operator": m.group(2).upper(),
                    "value": m.group(3).strip().strip("'\""),
                })
            else:
                conditions.append({"raw": part})
        return conditions

    def _execute_query(self, parsed: dict) -> list:
        dht = self._get_dht()
        ns = parsed["namespace"]
        fields = parsed["fields"]
        limit = parsed["limit"]
        conditions = parsed.get("where", [])
        results = []

        # Chercher dans le namespace DHT
        if dht:
            peers = dht.find_peers(ns, count=limit * 2)
            for peer in peers:
                if len(results) >= limit:
                    break
                entry = {"_peer": peer.get("peer_id", "")[:12]}
                # Extraire les champs demandés
                for f in fields:
                    if f == "*":
                        entry.update({k: v for k, v in peer.items() if not k.startswith("_")})
                    else:
                        entry[f] = peer.get(f, None)
                if self._match_conditions(entry, conditions):
                    results.append(entry)

        # Chercher dans l'index local
        ns_data = self.index.get(ns, {})
        for key, value in ns_data.items():
            if len(results) >= limit:
                break
            entry = {"_key": key}
            for f in fields:
                if f == "*":
                    if isinstance(value, dict):
                        entry.update(value)
                    else:
                        entry["value"] = value
                elif f == "_key":
                    entry[f] = key
                elif isinstance(value, dict):
                    entry[f] = value.get(f)
                else:
                    entry[f] = value
            if self._match_conditions(entry, conditions):
                results.append(entry)

        return results

    def _match_conditions(self, entry: dict, conditions: list) -> bool:
        if not conditions:
            return True
        result = True
        current_op = "AND"
        for c in conditions:
            if "op" in c:
                current_op = c["op"]
                continue
            field = c.get("field", "")
            actual = entry.get(field)
            expected = c.get("value", "")
            op = c.get("operator", "=")
            match = self._compare(actual, op, expected) if actual is not None else False
            if current_op == "AND":
                result = result and match
            else:
                result = result or match
        return result

    def _compare(self, actual, op, expected):
        try:
            actual_s = str(actual).lower()
            expected_s = str(expected).lower()
            if op == "=":
                return actual_s == expected_s
            elif op == "!=":
                return actual_s != expected_s
            elif op == "LIKE":
                return expected_s in actual_s
            elif op == "IN":
                return actual_s in [x.strip().lower() for x in expected_s.split(",")]
            else:
                actual_n = float(actual)
                expected_n = float(expected)
                if op == ">": return actual_n > expected_n
                if op == "<": return actual_n < expected_n
                if op == ">=": return actual_n >= expected_n
                if op == "<=": return actual_n <= expected_n
        except (ValueError, TypeError):
            pass
        return False

    # ── Index management ──────────────────────────────────

    def index_data(self, namespace: str, key: str, data: dict) -> dict:
        if namespace not in self.index:
            self.index[namespace] = {}
        self.index[namespace][key] = {
            **data,
            "_indexed_at": datetime.now().isoformat(),
        }
        self._save_index()
        return {"status": "indexed", "namespace": namespace, "key": key}

    def delete_index(self, namespace: str, key: str = "") -> dict:
        if key:
            if namespace in self.index and key in self.index[namespace]:
                del self.index[namespace][key]
                self._save_index()
                return {"status": "deleted"}
            return {"status": "not_found"}
        if namespace in self.index:
            del self.index[namespace]
            self._save_index()
            return {"status": "namespace_deleted"}
        return {"status": "not_found"}

    def list_namespaces(self) -> list:
        return list(self.index.keys())

    def list_indexed(self, namespace: str) -> list:
        data = self.index.get(namespace, {})
        return [{"key": k, **v} for k, v in data.items()]

    # ── Bulk operations ───────────────────────────────────

    def bulk_index(self, namespace: str, entries: list) -> dict:
        count = 0
        for entry in entries:
            key = entry.get("key", hashlib.sha256(str(entry).encode()).hexdigest()[:12])
            data = {k: v for k, v in entry.items() if k != "key"}
            self.index_data(namespace, key, data)
            count += 1
        return {"status": "bulk_indexed", "namespace": namespace, "count": count}

    def export_namespace(self, namespace: str) -> dict:
        data = self.index.get(namespace, {})
        return {"namespace": namespace, "count": len(data), "data": data}

    def import_namespace(self, namespace: str, data: dict) -> dict:
        self.index[namespace] = data
        self._save_index()
        return {"status": "imported", "namespace": namespace, "count": len(data)}

    # ── DHT passthrough ───────────────────────────────────

    def dht_store(self, key: str, value: dict) -> dict:
        dht = self._get_dht()
        if not dht:
            return {"status": "error", "error": "DHT not available"}
        return dht.store_value(key, value)

    def dht_get(self, key: str) -> Optional[dict]:
        dht = self._get_dht()
        if not dht:
            return None
        return dht.get_value(key)

    def dht_find_peers(self, key: str, count: int = 10) -> list:
        dht = self._get_dht()
        if not dht:
            return []
        return dht.find_peers(key, count)

    def dht_identity(self) -> dict:
        dht = self._get_dht()
        if not dht:
            return {"node_id": "dht_unavailable"}
        return dht.get_identity()

    def dht_stats(self) -> dict:
        dht = self._get_dht()
        if not dht:
            return {"dht_available": False}
        stats = dht.stats()
        stats["dht_available"] = True
        return stats

    def resolve_hns(self, name: str) -> Optional[dict]:
        dht = self._get_dht()
        if not dht:
            return None
        return dht.resolve_hns(name)

    def resolve_ens(self, name: str) -> Optional[dict]:
        dht = self._get_dht()
        if not dht:
            return None
        return dht.resolve_ens(name)

    def resolve_pixel(self, name: str) -> Optional[dict]:
        dht = self._get_dht()
        if not dht:
            return None
        return dht.resolve_pixel(name)

    # ── Health / Stats ────────────────────────────────────

    def stats(self) -> dict:
        return {
            "namespaces": len(self.index),
            "indexed_entries": sum(len(v) for v in self.index.values()),
            "cache_entries": len(self.cache),
            "dht_available": self._get_dht() is not None,
        }
