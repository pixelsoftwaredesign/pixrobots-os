# Pixel Software Design � Copyright 2026
"""bgdatasys — Couche d'abstraction Data unifiee pour PixelOS.

4 couches de stockage:
  1. TimescaleDB (hypertables, continuous aggregates) → mesures capteurs (PRIMARY)
  2. MongoDB → mesures capteurs (FALLBACK)
  3. Data Lake (NDJSON.gz/NPZ) → logs, features, models
  4. MySQL (relationnel) → agronomie, plantes, varietes, maladies

Architecture:
  DataSource     → enumeration des sources
  SensorTS       → serie temporelle d'un capteur
  LakeStore      → stockage fichier avec partitioning date
  BgDataSys      → facade unifiee pour tout PixelOS
"""

import json
import gzip
import structlog
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta, date, timezone
from typing import Any, Optional
from collections import defaultdict

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
LAKE_DIR = ROOT / "data" / "lake"
DATA_DIR = ROOT / "data"


# ── DataSource ──────────────────────────────────────────────

class DataSource:
    """Enumeration des sources de donnees."""

    TSDB = "timescaledb"
    MONGO = "mongodb"
    MYSQL = "mysql"
    LAKE = "lake"
    SENSOR_RAW = "lake/raw/capteurs"
    SENSOR_FEATURES = "lake/features"
    MODELS = "lake/models"


# ── SensorTS ────────────────────────────────────────────────

class SensorTS:
    """Serie temporelle pour un capteur.

    Ordre de resolution: TimescaleDB → MongoDB → Lake.
    """

    def __init__(self, space_id: str, sensor_id: str,
                 source: str = DataSource.TSDB):
        self.space_id = space_id
        self.sensor_id = sensor_id
        self.source = source
        self._mongo_collection = None

    def _tsdb(self):
        from core.tsdb import tsdb
        return tsdb

    def _mongo(self, collection: str = "mesures_capteurs"):
        if self._mongo_collection is None:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017/")
            self._mongo_collection = client["agricol_ts"][collection]
        return self._mongo_collection

    def query(self, since: datetime, until: datetime = None,
              agg: str = None, prefer_tsdb: bool = True) -> list[dict]:
        """Requete avec fallback: TimescaleDB → MongoDB → Lake."""
        if prefer_tsdb and self._tsdb().connected:
            rows = self._tsdb().query_range(self.sensor_id, since, until or datetime.now(timezone.utc))
            if rows:
                return rows
        if self.source != DataSource.LAKE:
            try:
                return self._query_mongo(since, until, agg)
            except Exception:
                pass
        return self._query_lake(since, until)

    def _query_mongo(self, since: datetime, until: datetime = None,
                     agg: str = None) -> list[dict]:
        q = {"sensor_id": self.sensor_id, "space_id": self.space_id,
             "timestamp": {"$gte": since}}
        if until:
            q["timestamp"]["$lte"] = until
        cursor = self._mongo().find(q).sort("timestamp", 1)
        return list(cursor)

    def _query_lake(self, since: datetime, until: datetime = None) -> list[dict]:
        """Lit depuis le Data Lake (fichiers NDJSON partitionnes par jour)."""
        results = []
        d = since
        end = until or datetime.now()
        while d <= end:
            day_path = LAKE_DIR / "raw" / "capteurs" / self.space_id / \
                       self.sensor_id / f"{d.strftime('%Y-%m-%d')}.json.gz"
            if day_path.exists():
                try:
                    with gzip.open(day_path, "rt", encoding="utf-8") as f:
                        for line in f:
                            rec = json.loads(line.strip())
                            ts = datetime.fromisoformat(rec["timestamp"])
                            if since <= ts <= (until or datetime.now()):
                                results.append(rec)
                except Exception as e:
                    log.warning("Erreur lecture lake", path=str(day_path),
                                error=str(e))
            d += timedelta(days=1)
        return results

    def write(self, value: float, unit: str = "", tags: dict = None,
              to_lake: bool = True, to_mongo: bool = True,
              to_tsdb: bool = True):
        """Ecrit une mesure dans les backends actifs (TimescaleDB primaire)."""
        ts = datetime.now(timezone.utc)
        if to_tsdb:
            try:
                self._tsdb().write_measurement(
                    self.space_id, self.sensor_id, value, unit, tags, ts)
            except Exception as e:
                log.warning("Erreur ecriture TimescaleDB", error=str(e))

        record = {
            "space_id": self.space_id,
            "sensor_id": self.sensor_id,
            "timestamp": ts.isoformat(),
            "value": value,
            "unit": unit,
            "tags": tags or {},
        }
        if to_mongo:
            try:
                self._mongo().insert_one(record)
            except Exception as e:
                log.warning("Erreur ecriture MongoDB", error=str(e))
        if to_lake:
            try:
                self._lake_write(record)
            except Exception as e:
                log.warning("Erreur ecriture Lake", error=str(e))

    def _lake_write(self, record: dict):
        day = date.today().isoformat()
        path = LAKE_DIR / "raw" / "capteurs" / self.space_id / \
               self.sensor_id
        path.mkdir(parents=True, exist_ok=True)
        fpath = path / f"{day}.json.gz"
        with gzip.open(fpath, "at", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def latest(self) -> Optional[dict]:
        try:
            from core.tsdb import tsdb
            if tsdb.connected:
                rows = tsdb.query_measurements(self.sensor_id, self.space_id, hours=720, limit=1)
                if rows:
                    return rows[0]
        except Exception:
            pass
        try:
            cursor = self._mongo().find(
                {"sensor_id": self.sensor_id, "space_id": self.space_id}
            ).sort("timestamp", -1).limit(1)
            for doc in cursor:
                return doc
        except Exception:
            pass
        return None

    def hourly_avg(self, since: datetime, until: datetime = None) -> list[dict]:
        """Moyenne horaire: TimescaleDB → MongoDB."""
        until = until or datetime.now(timezone.utc)
        try:
            from core.tsdb import tsdb
            if tsdb.connected:
                hours = max(1, int((until - since).total_seconds() / 3600) + 1)
                rows = tsdb.hourly_avg(self.sensor_id, self.space_id, hours=hours)
                if rows:
                    return [{"hour": r["bucket"], "avg": r["avg_value"],
                             "min": r["min_value"], "max": r["max_value"],
                             "count": r["sample_count"]} for r in rows]
        except Exception:
            pass
        # Fallback MongoDB
        pipeline = [
            {"$match": {"sensor_id": self.sensor_id, "space_id": self.space_id,
                        "timestamp": {"$gte": since, "$lte": until}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%dT%H:00:00Z",
                                           "date": "$timestamp"}},
                "avg_value": {"$avg": "$value"},
                "min_value": {"$min": "$value"},
                "max_value": {"$max": "$value"},
                "count": {"$sum": 1},
            }},
            {"$sort": {"_id": 1}},
        ]
        try:
            results = list(self._mongo().aggregate(pipeline))
            return [{
                "hour": r["_id"],
                "avg": round(r["avg_value"], 2),
                "min": round(r["min_value"], 2),
                "max": round(r["max_value"], 2),
                "count": r["count"],
            } for r in results]
        except Exception as e:
            log.warning("Erreur aggregation", error=str(e))
            return []


# ── LakeStore ─────────────────────────────────────────────

class LakeStore:
    """Data Lake PixelOS — stockage fichier partitionne."""

    def __init__(self):
        self._ensure_dirs()

    def _ensure_dirs(self):
        for d in ["raw/capteurs", "raw/logs", "features",
                   "models", "predictions"]:
            (LAKE_DIR / d).mkdir(parents=True, exist_ok=True)

    def write_log(self, component: str, entry: dict):
        """Ecrit un log dans le lake (archive JSON .gz)."""
        now = datetime.now()
        path = LAKE_DIR / "raw" / "logs" / component
        path.mkdir(parents=True, exist_ok=True)
        fname = f"{now.strftime('%Y-%m')}.json.gz"
        entry["_ts"] = now.isoformat()
        with gzip.open(path / fname, "at", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def query_logs(self, component: str, since: str = None,
                   until: str = None) -> list[dict]:
        results = []
        path = LAKE_DIR / "raw" / "logs" / component
        if not path.exists():
            return results
        for fpath in sorted(path.glob("*.json.gz")):
            try:
                with gzip.open(fpath, "rt", encoding="utf-8") as f:
                    for line in f:
                        rec = json.loads(line.strip())
                        ts = rec.get("_ts", "")
                        if since and ts < since:
                            continue
                        if until and ts > until:
                            continue
                        results.append(rec)
            except Exception as e:
                log.warning("Erreur lecture logs", error=str(e))
        return results

    def save_features(self, name: str, X: np.ndarray,
                      y: np.ndarray = None, feature_names: list[str] = None,
                      metadata: dict = None):
        """Sauvegarde un jeu de features pre-calculees au format NPZ."""
        path = LAKE_DIR / "features"
        path.mkdir(parents=True, exist_ok=True)
        data = {"X": X}
        if y is not None:
            data["y"] = y
        if feature_names:
            data["feature_names"] = np.array(feature_names)
        npz_path = path / f"{name}_{date.today().isoformat()}.npz"
        np.savez_compressed(npz_path, **data)
        meta_path = npz_path.with_suffix(".meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "name": name,
                "created": datetime.now().isoformat(),
                "rows": len(X),
                "cols": X.shape[1] if len(X.shape) > 1 else 1,
                "has_target": y is not None,
                "feature_names": feature_names,
                "metadata": metadata or {},
            }, f, indent=2)
        log.info("Features sauvegardees", path=str(npz_path),
                 rows=len(X))

    def load_features(self, name: str, date_str: str = None) -> dict:
        """Charge un jeu de features."""
        path = LAKE_DIR / "features"
        if date_str:
            npz_path = path / f"{name}_{date_str}.npz"
        else:
            files = sorted(path.glob(f"{name}_*.npz"))
            npz_path = files[-1] if files else None
        if not npz_path or not npz_path.exists():
            return {}
        data = np.load(npz_path)
        result = {"X": data["X"]}
        if "y" in data:
            result["y"] = data["y"]
        if "feature_names" in data:
            result["feature_names"] = list(data["feature_names"])
        return result


# ── BgDataSys ──────────────────────────────────────────────

class BgDataSys:
    """Facade unifiee de donnees pour PixelOS.

    4 couches: TimescaleDB (primaire) → MongoDB (fallback) → Lake (archive) → MySQL (relationnel).

    Usage:
        from core.bgdatasys import bgdatasys
        # Lire les dernieres mesures
        rows = bgdatasys.query_sensors(space="serre_a", hours=24)
        # Ecrire une mesure
        bgdatasys.write_measurement("serre_a", "temp_air", 22.5, "C")
        # Aggregation horaire
        hourly = bgdatasys.hourly_avg("serre_a", "temp_air", hours=72)
        # Logger un evenement ML
        bgdatasys.log_ml_event("train", {"model": "irrigation", "mae": 0.83})
    """

    def __init__(self):
        self.lake = LakeStore()
        self._sensor_cache: dict[str, SensorTS] = {}
        self._tsdb_initialized = False

    def _init_tsdb(self):
        if not self._tsdb_initialized:
            try:
                from core.tsdb import tsdb
                tsdb.connect()
            except Exception:
                pass
            self._tsdb_initialized = True

    @property
    def tsdb(self):
        from core.tsdb import tsdb
        self._init_tsdb()
        return tsdb

    def sensor(self, space_id: str, sensor_id: str,
               source: str = DataSource.TSDB) -> SensorTS:
        """Retourne (ou cree) une instance SensorTS."""
        key = f"{space_id}/{sensor_id}"
        if key not in self._sensor_cache:
            self._sensor_cache[key] = SensorTS(space_id, sensor_id, source)
        return self._sensor_cache[key]

    # ── Mesures capteurs ──────────────────────────────────

    def query_sensors(self, space: str = None, sensor: str = None,
                      hours: int = 24, until: datetime = None,
                      source: str = None) -> list[dict]:
        """Requete multi-capteurs. Try TimescaleDB → MongoDB → Lake."""
        since = (until or datetime.now(timezone.utc)) - timedelta(hours=hours)
        until = until or datetime.now(timezone.utc)
        source = source or DataSource.TSDB

        if source == DataSource.TSDB:
            rows = self._query_tsdb_sensors(space, sensor, since, until)
            if rows:
                return rows
            rows = self._query_mongo_sensors(space, sensor, since, until)
            if rows:
                return rows
            return self._query_lake_sensors(space, sensor, since, until)

        if source == DataSource.MONGO:
            return self._query_mongo_sensors(space, sensor, since, until)
        if source == DataSource.LAKE:
            return self._query_lake_sensors(space, sensor, since, until)
        return []

    def _query_tsdb_sensors(self, space: str, sensor: str,
                             since: datetime, until: datetime) -> list[dict]:
        try:
            tsdb = self.tsdb
            if not tsdb.connected:
                return []
            return tsdb.query_measurements(sensor, space,
                                           hours=max(1, int((until - since).total_seconds() / 3600) + 1),
                                           limit=10000)
        except Exception as e:
            log.warning("Erreur query TimescaleDB", error=str(e))
            return []

    def _query_mongo_sensors(self, space: str, sensor: str,
                              since: datetime, until: datetime) -> list[dict]:
        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017/")
            db = client["agricol_ts"]["mesures_capteurs"]
            q = {"timestamp": {"$gte": since, "$lte": until}}
            if space:
                q["space_id"] = space
            if sensor:
                q["sensor_id"] = sensor
            return list(db.find(q).sort("timestamp", 1).limit(10000))
        except Exception as e:
            log.warning("Erreur query MongoDB", error=str(e))
            return []

    def _query_lake_sensors(self, space: str, sensor: str,
                             since: datetime, until: datetime) -> list[dict]:
        results = []
        d = since
        while d <= until:
            base = LAKE_DIR / "raw" / "capteurs"
            if space and sensor:
                dirs = [base / space / sensor]
            elif space:
                dirs = list((base / space).glob("*"))
            else:
                dirs = []
                for sp in base.iterdir():
                    if sp.is_dir():
                        for sens in sp.iterdir():
                            dirs.append(sens)

            for spath in dirs:
                if not spath.exists():
                    continue
                fpath = spath / f"{d.strftime('%Y-%m-%d')}.json.gz"
                if fpath.exists():
                    try:
                        with gzip.open(fpath, "rt", encoding="utf-8") as f:
                            for line in f:
                                rec = json.loads(line.strip())
                                ts = datetime.fromisoformat(
                                    rec["timestamp"].replace("Z", "+00:00"))
                                if since <= ts <= until:
                                    results.append(rec)
                    except Exception:
                        pass
            d += timedelta(days=1)
        return results

    def write_measurement(self, space_id: str, sensor_id: str,
                           value: float, unit: str = "",
                           tags: dict = None,
                           to_lake: bool = True, to_mongo: bool = True,
                           to_tsdb: bool = True):
        """Ecrit une mesure dans les backends (TimescaleDB primaire)."""
        sts = self.sensor(space_id, sensor_id)
        sts.write(value, unit, tags, to_lake, to_mongo, to_tsdb)

    # ── Aggregations TimescaleDB ──────────────────────────

    def hourly_avg(self, space_id: str = None, sensor_id: str = None,
                   hours: int = 168) -> list[dict]:
        """Moyennes horaires via TimescaleDB (fallback MongoDB)."""
        try:
            tsdb = self.tsdb
            if tsdb.connected:
                rows = tsdb.hourly_avg(sensor_id, space_id, hours)
                if rows:
                    return rows
        except Exception:
            pass
        # Fallback
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        sts = self.sensor(space_id or "_", sensor_id or "_")
        return sts.hourly_avg(since, datetime.now(timezone.utc))

    def daily_avg(self, space_id: str = None, sensor_id: str = None,
                  days: int = 90) -> list[dict]:
        """Moyennes journalieres via TimescaleDB."""
        try:
            tsdb = self.tsdb
            if tsdb.connected:
                return tsdb.daily_avg(sensor_id, space_id, days)
        except Exception:
            pass
        return []

    def register_sensor(self, sensor_id: str, space_id: str = "",
                        sensor_type: str = "unknown",
                        label: str = "", unit: str = "",
                        bus: str = "simulation", addr: str = "",
                        metadata: dict = None) -> bool:
        """Enregistre un capteur dans le catalogue TimescaleDB."""
        try:
            return self.tsdb.register_sensor(
                sensor_id, space_id, sensor_type, label, unit, bus, addr, metadata)
        except Exception:
            return False

    def list_sensors(self, space_id: str = None,
                     sensor_type: str = None) -> list[dict]:
        try:
            return self.tsdb.list_sensors(space_id, sensor_type)
        except Exception:
            return []

    # ── Events ────────────────────────────────────────────

    def write_event(self, event_type: str, space_id: str = "",
                    sensor_id: str = "", actor: str = "",
                    value: str = "", details: dict = None) -> bool:
        try:
            return self.tsdb.write_event(event_type, space_id, sensor_id,
                                         actor, value, details)
        except Exception:
            # Fallback lake
            self.lake.write_log("events", {
                "event_type": event_type, "space_id": space_id,
                "sensor_id": sensor_id, "actor": actor, "value": value,
                "details": details or {},
            })
            return True

    def query_events(self, event_type: str = None, space_id: str = None,
                     hours: int = 72) -> list[dict]:
        try:
            tsdb = self.tsdb
            if tsdb.connected:
                return tsdb.query_events(event_type, space_id, hours)
        except Exception:
            pass
        return []

    # ── Training runs ─────────────────────────────────────

    def record_training(self, run_id: str, model_name: str,
                        status: str = "running", metrics: dict = None,
                        features: list = None, training_samples: int = 0,
                        test_samples: int = 0, mae: float = None,
                        r2: float = None, model_path: str = "") -> bool:
        try:
            return self.tsdb.record_training(
                run_id, model_name, status, metrics, features,
                training_samples, test_samples, mae, r2, model_path)
        except Exception:
            self.lake.write_log("training", {
                "run_id": run_id, "model_name": model_name, "status": status,
                "metrics": metrics, "mae": mae, "r2": r2,
            })
            return True

    def list_training_runs(self, model_name: str = None, limit: int = 20) -> list[dict]:
        try:
            tsdb = self.tsdb
            if tsdb.connected:
                return tsdb.list_training_runs(model_name, limit)
        except Exception:
            pass
        # Fallback lake logs
        logs = self.lake.query_logs("training")
        return logs[:limit]

    # ── Predictions ───────────────────────────────────────

    def write_prediction(self, model_name: str, sensor_id: str = "",
                         space_id: str = "", predicted_value: float = None,
                         confidence: float = 0.0, actual_value: float = None,
                         features: dict = None) -> bool:
        try:
            return self.tsdb.write_prediction(
                model_name, sensor_id, space_id,
                predicted_value, confidence, actual_value, features)
        except Exception:
            self.lake.write_log("predictions", {
                "model_name": model_name, "sensor_id": sensor_id,
                "space_id": space_id, "predicted_value": predicted_value,
                "confidence": confidence, "actual_value": actual_value,
            })
            return True

    def query_predictions(self, model_name: str = None,
                          space_id: str = None, hours: int = 720) -> list[dict]:
        try:
            tsdb = self.tsdb
            if tsdb.connected:
                return tsdb.query_predictions(model_name, space_id, hours)
        except Exception:
            pass
        return []

    # ── Migration ─────────────────────────────────────────

    def migrate_from_mongodb(self, hours: int = 720) -> dict:
        """Migre les donnees MongoDB → TimescaleDB."""
        return self.tsdb.migrate_from_mongodb(hours)

    def seed_test_data(self, days: int = 30, interval_minutes: int = 15) -> dict:
        """Genere donnees de test dans TimescaleDB."""
        return self.tsdb.seed_test_data(days, interval_minutes)

    # ── MySQL ─────────────────────────────────────────────

    def query_mysql(self, query: str, params: tuple = ()) -> list[dict]:
        """Execute une requete MySQL et retourne les resultats."""
        try:
            import mysql.connector
            from core.config import PixelOSConfig
            cfg = PixelOSConfig()
            conn = mysql.connector.connect(
                host=cfg.get("database.mysql.host", "localhost"),
                port=cfg.get("database.mysql.port", 3306),
                user=cfg.get("database.mysql.user", "agricol"),
                password=cfg.get("database.mysql.password", ""),
                database=cfg.get("database.mysql.database", "agricol"),
            )
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return rows
        except Exception as e:
            log.warning("Erreur MySQL", query=query[:80], error=str(e))
            return []

    # ── Logs ML ───────────────────────────────────────────

    def log_ml_event(self, event_type: str, data: dict):
        """Log un evenement ML (train, predict, eval)."""
        self.lake.write_log("ml_events", {
            "event_type": event_type,
            **data,
        })

    # ── Statistiques ──────────────────────────────────────

    def stats(self) -> dict:
        """Statistiques d'utilisation du systeme de donnees."""
        sensor_count = sum(1 for _ in (LAKE_DIR / "raw" / "capteurs").rglob("*.json.gz"))
        log_count = sum(1 for _ in (LAKE_DIR / "raw" / "logs").rglob("*.json.gz"))
        feature_count = len(list((LAKE_DIR / "features").glob("*.npz")))

        tsdb_stats = {"connected": False}
        try:
            tsdb_stats = self.tsdb.stats()
        except Exception:
            pass

        return {
            "tsdb": tsdb_stats,
            "lake_sensor_files": sensor_count,
            "lake_log_files": log_count,
            "lake_feature_sets": feature_count,
            "sensor_cache_size": len(self._sensor_cache),
            "lake_path": str(LAKE_DIR),
        }


# Singleton
bgdatasys = BgDataSys()
