# Pixel Software Design � Copyright 2026
"""TimescaleDB — Migration MongoDB → TimescaleDB pour séries temporelles agricoles.

Hypertables, continuous aggregates, catalog capteurs, events, prédictions.
Backup: chute sur MongoDB/Lake si TimescaleDB indisponible.
"""

import os
import json
import structlog
import numpy as np
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from typing import Optional
from contextlib import contextmanager

log = structlog.get_logger()

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
    HAS_TSDB = True
except ImportError:
    HAS_TSDB = False
    psycopg2 = None

TSDB_HOST = os.environ.get("PIXELOS_TSDB_HOST", "localhost")
TSDB_PORT = int(os.environ.get("PIXELOS_TSDB_PORT", 5432))
TSDB_DB = os.environ.get("PIXELOS_TSDB_DB", "pixelos_ts")
TSDB_USER = os.environ.get("PIXELOS_TSDB_USER", "pixelos")
TSDB_PASS = os.environ.get("PIXELOS_TSDB_PASS", "pixelos_secret")

SCHEMA_SQL = """
-- TimescaleDB Schema v1 — PixelOS Agricultural Time-Series

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 1. Sensor measurements hypertable
CREATE TABLE IF NOT EXISTS sensor_measurements (
    time TIMESTAMPTZ NOT NULL,
    sensor_id TEXT NOT NULL,
    space_id TEXT NOT NULL DEFAULT '',
    value DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    tags JSONB DEFAULT '{}',
    quality SMALLINT NOT NULL DEFAULT 0
);
SELECT create_hypertable('sensor_measurements', 'time', if_not_exists => true);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sm_sensor_time
    ON sensor_measurements (sensor_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_sm_space_time
    ON sensor_measurements (space_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_sm_tags
    ON sensor_measurements USING GIN (tags);

-- 2. Sensor metadata catalog
CREATE TABLE IF NOT EXISTS sensor_catalog (
    sensor_id TEXT PRIMARY KEY,
    space_id TEXT NOT NULL DEFAULT '',
    sensor_type TEXT NOT NULL DEFAULT 'unknown',
    label TEXT NOT NULL DEFAULT '',
    unit TEXT NOT NULL DEFAULT '',
    bus TEXT NOT NULL DEFAULT 'simulation',
    addr TEXT DEFAULT '',
    calibration_offset DOUBLE PRECISION DEFAULT 0.0,
    calibration_gain DOUBLE PRECISION DEFAULT 1.0,
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    enabled BOOLEAN DEFAULT TRUE,
    installed_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- 3. Continuous aggregates (hourly)
CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_aggregates
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 hour', time) AS bucket,
    sensor_id,
    space_id,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    STDDEV(value) AS stddev_value,
    COUNT(*) AS sample_count
FROM sensor_measurements
GROUP BY bucket, sensor_id, space_id
WITH NO DATA;

-- 4. Continuous aggregates (daily)
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_aggregates
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 day', time) AS bucket,
    sensor_id,
    space_id,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    STDDEV(value) AS stddev_value,
    COUNT(*) AS sample_count
FROM sensor_measurements
GROUP BY bucket, sensor_id, space_id
WITH NO DATA;

-- 5. Events hypertable (irrigation, valve, alarms)
CREATE TABLE IF NOT EXISTS events (
    time TIMESTAMPTZ NOT NULL,
    event_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    space_id TEXT NOT NULL DEFAULT '',
    sensor_id TEXT NOT NULL DEFAULT '',
    actor TEXT DEFAULT '',
    value TEXT DEFAULT '',
    details JSONB DEFAULT '{}'
);
SELECT create_hypertable('events', 'time', if_not_exists => true);
CREATE INDEX IF NOT EXISTS idx_ev_type_time ON events (event_type, time DESC);

-- 6. Training runs tracking
CREATE TABLE IF NOT EXISTS training_runs (
    run_id TEXT PRIMARY KEY,
    model_name TEXT NOT NULL,
    model_version TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metrics JSONB DEFAULT '{}',
    features_used TEXT[] DEFAULT '{}',
    training_samples INTEGER DEFAULT 0,
    test_samples INTEGER DEFAULT 0,
    mae DOUBLE PRECISION,
    r2_score DOUBLE PRECISION,
    model_path TEXT DEFAULT ''
);

-- 7. Predictions hypertable
CREATE TABLE IF NOT EXISTS predictions (
    time TIMESTAMPTZ NOT NULL,
    prediction_id TEXT DEFAULT '',
    model_name TEXT NOT NULL,
    sensor_id TEXT DEFAULT '',
    space_id TEXT DEFAULT '',
    predicted_value DOUBLE PRECISION,
    confidence DOUBLE PRECISION DEFAULT 0.0,
    actual_value DOUBLE PRECISION,
    features_snapshot JSONB DEFAULT '{}'
);
SELECT create_hypertable('predictions', 'time', if_not_exists => true);
CREATE INDEX IF NOT EXISTS idx_pred_model_time ON predictions (model_name, time DESC);
"""


class TimescaleDBManager:
    """Gestionnaire TimescaleDB — écriture, lecture, agrégation, migration.

    Pattern Singleton. Fallback silencieux si TimescaleDB indisponible.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._pool = None
        self._connected = False
        self._schema_loaded = False

    @property
    def connected(self) -> bool:
        return self._connected and self._pool is not None

    def connect(self) -> bool:
        if not HAS_TSDB:
            log.warning("psycopg2 non installé — TimescaleDB désactivé")
            return False
        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                1, 5,
                host=TSDB_HOST, port=TSDB_PORT,
                dbname=TSDB_DB, user=TSDB_USER, password=TSDB_PASS,
                connect_timeout=3,
            )
            self._connected = True
            self._init_schema()
            log.info("TimescaleDB connecté", host=TSDB_HOST, port=TSDB_PORT, db=TSDB_DB)
            return True
        except Exception as e:
            log.warning("TimescaleDB indisponible", error=str(e))
            self._connected = False
            self._pool = None
            return False

    def disconnect(self):
        if self._pool:
            self._pool.closeall()
            self._pool = None
        self._connected = False

    def _init_schema(self):
        if self._schema_loaded:
            return
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT extname FROM pg_extension WHERE extname='timescaledb'")
                if not cur.fetchone():
                    log.warning("Extension TimescaleDB non installée dans PostgreSQL")
                    return
                cur.execute(SCHEMA_SQL)
                conn.commit()
                self._schema_loaded = True
                log.info("Schema TimescaleDB v1 chargé")

                # Rafraîchir les vues matérialisées
                try:
                    cur.execute("CALL refresh_continuous_aggregate('hourly_aggregates', NULL, NULL)")
                    cur.execute("CALL refresh_continuous_aggregate('daily_aggregates', NULL, NULL)")
                    conn.commit()
                except Exception:
                    pass
        except Exception as e:
            log.warning("Échec init schema TimescaleDB", error=str(e))

    @contextmanager
    def _conn(self):
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def _ensure_connected(self) -> bool:
        if not self.connected:
            return self.connect()
        return self.connected

    # ── Sensor measurements ─────────────────────────────

    def write_measurement(self, space_id: str, sensor_id: str, value: float,
                          unit: str = "", tags: dict = None,
                          time: datetime = None) -> bool:
        if not self._ensure_connected():
            return False
        try:
            t = time or datetime.now(timezone.utc)
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO sensor_measurements (time, sensor_id, space_id, value, unit, tags)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (t, sensor_id, space_id, float(value), unit,
                      json.dumps(tags or {})))
                conn.commit()
            return True
        except Exception as e:
            log.error("Erreur écriture TimescaleDB", error=str(e))
            return False

    def write_batch(self, measurements: list[dict]) -> int:
        """Écriture batch optimisée. Retourne le nombre d'insertions."""
        if not self._ensure_connected():
            return 0
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                psycopg2.extras.execute_values(
                    cur,
                    """INSERT INTO sensor_measurements (time, sensor_id, space_id, value, unit, tags)
                       VALUES %s""",
                    [(
                        m.get("time", datetime.now(timezone.utc)),
                        m["sensor_id"], m.get("space_id", ""),
                        float(m["value"]), m.get("unit", ""),
                        json.dumps(m.get("tags", {}))
                    ) for m in measurements],
                    template="(%s, %s, %s, %s, %s, %s)",
                )
                conn.commit()
            return len(measurements)
        except Exception as e:
            log.error("Erreur écriture batch TimescaleDB", error=str(e))
            return 0

    def query_measurements(self, sensor_id: str = None, space_id: str = None,
                           hours: int = 24, limit: int = 10000,
                           order: str = "DESC") -> list[dict]:
        """Requête flexible avec filtres."""
        if not self._ensure_connected():
            return []
        conditions = []
        params = []
        if sensor_id:
            conditions.append("sensor_id = %s")
            params.append(sensor_id)
        if space_id:
            conditions.append("space_id = %s")
            params.append(space_id)

        where = "AND " + " AND ".join(conditions) if conditions else ""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        try:
            with self._conn() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(f"""
                    SELECT time, sensor_id, space_id, value, unit, tags, quality
                    FROM sensor_measurements
                    WHERE time >= %s {where}
                    ORDER BY time {order}
                    LIMIT %s
                """, [since] + params + [limit])
                rows = []
                for r in cur.fetchall():
                    d = dict(r)
                    d["time"] = d["time"].isoformat()
                    if isinstance(d.get("tags"), dict):
                        d["tags"] = {k: v for k, v in d["tags"].items() if v is not None}
                    rows.append(d)
                return rows
        except Exception as e:
            log.error("Erreur requête TimescaleDB", error=str(e))
            return []

    def query_range(self, sensor_id: str, start: datetime, end: datetime) -> list[dict]:
        """Requête sur une plage temporelle exacte."""
        if not self._ensure_connected():
            return []
        try:
            with self._conn() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT time, sensor_id, space_id, value, unit, tags, quality
                    FROM sensor_measurements
                    WHERE sensor_id = %s AND time >= %s AND time <= %s
                    ORDER BY time ASC
                """, (sensor_id, start, end))
                rows = []
                for r in cur.fetchall():
                    d = dict(r)
                    d["time"] = d["time"].isoformat()
                    rows.append(d)
                return rows
        except Exception as e:
            log.error("Erreur query_range TimescaleDB", error=str(e))
            return []

    # ── Aggregates ──────────────────────────────────────

    def hourly_avg(self, sensor_id: str = None, space_id: str = None,
                   hours: int = 168) -> list[dict]:
        """Moyennes horaires (7j par défaut)."""
        if not self._ensure_connected():
            return []
        conditions = []
        params = []
        if sensor_id:
            conditions.append("sensor_id = %s")
            params.append(sensor_id)
        if space_id:
            conditions.append("space_id = %s")
            params.append(space_id)
        where = "AND " + " AND ".join(conditions) if conditions else ""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        try:
            with self._conn() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(f"""
                    SELECT time_bucket('1 hour', time) AS bucket,
                           sensor_id, space_id,
                           AVG(value) AS avg_value,
                           MIN(value) AS min_value,
                           MAX(value) AS max_value,
                           COUNT(*) AS sample_count
                    FROM sensor_measurements
                    WHERE time >= %s {where}
                    GROUP BY bucket, sensor_id, space_id
                    ORDER BY bucket DESC
                """, [since] + params)
                rows = []
                for r in cur.fetchall():
                    d = dict(r)
                    d["bucket"] = d["bucket"].isoformat()
                    d["avg_value"] = round(d["avg_value"], 4) if d["avg_value"] else 0
                    d["min_value"] = round(d["min_value"], 4) if d["min_value"] else 0
                    d["max_value"] = round(d["max_value"], 4) if d["max_value"] else 0
                    rows.append(d)
                return rows
        except Exception as e:
            log.error("Erreur hourly_avg TimescaleDB", error=str(e))
            return []

    def daily_avg(self, sensor_id: str = None, space_id: str = None,
                  days: int = 90) -> list[dict]:
        """Moyennes journalières."""
        if not self._ensure_connected():
            return []
        conditions = []
        params = []
        if sensor_id:
            conditions.append("sensor_id = %s")
            params.append(sensor_id)
        if space_id:
            conditions.append("space_id = %s")
            params.append(space_id)
        where = "AND " + " AND ".join(conditions) if conditions else ""
        since = datetime.now(timezone.utc) - timedelta(days=days)

        try:
            with self._conn() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(f"""
                    SELECT time_bucket('1 day', time) AS bucket,
                           sensor_id, space_id,
                           AVG(value) AS avg_value,
                           MIN(value) AS min_value,
                           MAX(value) AS max_value,
                           COUNT(*) AS sample_count
                    FROM sensor_measurements
                    WHERE time >= %s {where}
                    GROUP BY bucket, sensor_id, space_id
                    ORDER BY bucket DESC
                """, [since] + params)
                rows = []
                for r in cur.fetchall():
                    d = dict(r)
                    d["bucket"] = d["bucket"].isoformat()
                    d["avg_value"] = round(d["avg_value"], 4) if d["avg_value"] else 0
                    d["min_value"] = round(d["min_value"], 4) if d["min_value"] else 0
                    d["max_value"] = round(d["max_value"], 4) if d["max_value"] else 0
                    rows.append(d)
                return rows
        except Exception as e:
            log.error("Erreur daily_avg TimescaleDB", error=str(e))
            return []

    # ── Sensor catalog ──────────────────────────────────

    def register_sensor(self, sensor_id: str, space_id: str = "",
                        sensor_type: str = "unknown",
                        label: str = "", unit: str = "",
                        bus: str = "simulation", addr: str = "",
                        metadata: dict = None) -> bool:
        if not self._ensure_connected():
            return False
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO sensor_catalog (sensor_id, space_id, sensor_type, label, unit, bus, addr, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (sensor_id) DO UPDATE SET
                        space_id = EXCLUDED.space_id,
                        label = EXCLUDED.label,
                        bus = EXCLUDED.bus,
                        metadata = EXCLUDED.metadata
                """, (sensor_id, space_id, sensor_type, label, unit, bus, addr,
                      json.dumps(metadata or {})))
                conn.commit()
            return True
        except Exception as e:
            log.error("Erreur register_sensor", error=str(e))
            return False

    def list_sensors(self, space_id: str = None, sensor_type: str = None) -> list[dict]:
        if not self._ensure_connected():
            return []
        conditions = []
        params = []
        if space_id:
            conditions.append("space_id = %s")
            params.append(space_id)
        if sensor_type:
            conditions.append("sensor_type = %s")
            params.append(sensor_type)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        try:
            with self._conn() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(f"""
                    SELECT sensor_id, space_id, sensor_type, label, unit, bus, addr,
                           calibration_offset, calibration_gain, enabled, installed_at, metadata
                    FROM sensor_catalog {where}
                    ORDER BY sensor_id
                """, params)
                rows = []
                for r in cur.fetchall():
                    d = dict(r)
                    if isinstance(d.get("installed_at"), datetime):
                        d["installed_at"] = d["installed_at"].isoformat()
                    rows.append(d)
                return rows
        except Exception as e:
            log.error("Erreur list_sensors", error=str(e))
            return []

    # ── Events ──────────────────────────────────────────

    def write_event(self, event_type: str, space_id: str = "",
                    sensor_id: str = "", actor: str = "",
                    value: str = "", details: dict = None,
                    time: datetime = None) -> bool:
        if not self._ensure_connected():
            return False
        try:
            t = time or datetime.now(timezone.utc)
            import uuid
            eid = f"EV-{uuid.uuid4().hex[:8].upper()}"
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO events (time, event_id, event_type, space_id, sensor_id, actor, value, details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (t, eid, event_type, space_id, sensor_id, actor, value,
                      json.dumps(details or {})))
                conn.commit()
            return True
        except Exception as e:
            log.error("Erreur write_event", error=str(e))
            return False

    def query_events(self, event_type: str = None, space_id: str = None,
                     hours: int = 72, limit: int = 500) -> list[dict]:
        if not self._ensure_connected():
            return []
        conditions = []
        params = []
        if event_type:
            conditions.append("event_type = %s")
            params.append(event_type)
        if space_id:
            conditions.append("space_id = %s")
            params.append(space_id)
        where = "AND " + " AND ".join(conditions) if conditions else ""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        try:
            with self._conn() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(f"""
                    SELECT time, event_id, event_type, space_id, sensor_id, actor, value, details
                    FROM events
                    WHERE time >= %s {where}
                    ORDER BY time DESC
                    LIMIT %s
                """, [since] + params + [limit])
                rows = []
                for r in cur.fetchall():
                    d = dict(r)
                    d["time"] = d["time"].isoformat()
                    rows.append(d)
                return rows
        except Exception as e:
            log.error("Erreur query_events", error=str(e))
            return []

    # ── Training runs ───────────────────────────────────

    def record_training(self, run_id: str, model_name: str,
                        status: str = "running", metrics: dict = None,
                        features: list = None,
                        training_samples: int = 0, test_samples: int = 0,
                        mae: float = None, r2: float = None,
                        model_path: str = "") -> bool:
        if not self._ensure_connected():
            return False
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO training_runs (run_id, model_name, status, metrics, features_used,
                                               training_samples, test_samples, mae, r2_score, model_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        completed_at = CASE WHEN EXCLUDED.status = 'completed' THEN NOW() ELSE NULL END,
                        metrics = EXCLUDED.metrics,
                        mae = EXCLUDED.mae,
                        r2_score = EXCLUDED.r2_score
                """, (run_id, model_name, status, json.dumps(metrics or {}),
                      features or [], training_samples, test_samples,
                      mae, r2, model_path))
                conn.commit()
            return True
        except Exception as e:
            log.error("Erreur record_training", error=str(e))
            return False

    def list_training_runs(self, model_name: str = None, limit: int = 20) -> list[dict]:
        if not self._ensure_connected():
            return []
        where = "WHERE model_name = %s" if model_name else ""
        params = [model_name] if model_name else []

        try:
            with self._conn() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(f"""
                    SELECT run_id, model_name, model_version, status, started_at, completed_at,
                           metrics, features_used, training_samples, test_samples, mae, r2_score, model_path
                    FROM training_runs {where}
                    ORDER BY started_at DESC
                    LIMIT %s
                """, params + [limit])
                rows = []
                for r in cur.fetchall():
                    d = dict(r)
                    if isinstance(d.get("started_at"), datetime):
                        d["started_at"] = d["started_at"].isoformat()
                    if isinstance(d.get("completed_at"), datetime):
                        d["completed_at"] = d["completed_at"].isoformat()
                    rows.append(d)
                return rows
        except Exception as e:
            log.error("Erreur list_training_runs", error=str(e))
            return []

    # ── Predictions ─────────────────────────────────────

    def write_prediction(self, model_name: str, sensor_id: str = "",
                         space_id: str = "", predicted_value: float = None,
                         confidence: float = 0.0, actual_value: float = None,
                         features: dict = None,
                         time: datetime = None) -> bool:
        if not self._ensure_connected():
            return False
        try:
            t = time or datetime.now(timezone.utc)
            import uuid
            pid = f"PRED-{uuid.uuid4().hex[:8].upper()}"
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO predictions (time, prediction_id, model_name, sensor_id, space_id,
                                             predicted_value, confidence, actual_value, features_snapshot)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (t, pid, model_name, sensor_id, space_id,
                      float(predicted_value) if predicted_value is not None else None,
                      float(confidence),
                      float(actual_value) if actual_value is not None else None,
                      json.dumps(features or {})))
                conn.commit()
            return True
        except Exception as e:
            log.error("Erreur write_prediction", error=str(e))
            return False

    def query_predictions(self, model_name: str = None, space_id: str = None,
                          hours: int = 720, limit: int = 500) -> list[dict]:
        if not self._ensure_connected():
            return []
        conditions = []
        params = []
        if model_name:
            conditions.append("model_name = %s")
            params.append(model_name)
        if space_id:
            conditions.append("space_id = %s")
            params.append(space_id)
        where = "AND " + " AND ".join(conditions) if conditions else ""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        try:
            with self._conn() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(f"""
                    SELECT time, prediction_id, model_name, sensor_id, space_id,
                           predicted_value, confidence, actual_value, features_snapshot
                    FROM predictions
                    WHERE time >= %s {where}
                    ORDER BY time DESC
                    LIMIT %s
                """, [since] + params + [limit])
                rows = []
                for r in cur.fetchall():
                    d = dict(r)
                    d["time"] = d["time"].isoformat()
                    rows.append(d)
                return rows
        except Exception as e:
            log.error("Erreur query_predictions", error=str(e))
            return []

    # ── Stats & Maintenance ─────────────────────────────

    def stats(self) -> dict:
        if not self._ensure_connected():
            return {"connected": False, "error": "TimescaleDB indisponible"}

        try:
            with self._conn() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                cur.execute("SELECT COUNT(*) AS c FROM sensor_measurements")
                measurements = cur.fetchone()["c"]

                cur.execute("SELECT COUNT(*) AS c FROM sensor_catalog")
                sensors = cur.fetchone()["c"]

                cur.execute("SELECT COUNT(*) AS c FROM events")
                events = cur.fetchone()["c"]

                cur.execute("SELECT COUNT(*) AS c FROM training_runs")
                training_runs = cur.fetchone()["c"]

                cur.execute("SELECT COUNT(*) AS c FROM predictions")
                predictions = cur.fetchone()["c"]

                cur.execute("""
                    SELECT time_bucket('1 day', time) AS day, COUNT(*) AS c
                    FROM sensor_measurements
                    WHERE time >= NOW() - INTERVAL '7 days'
                    GROUP BY day ORDER BY day DESC
                """)
                daily_counts = {str(r["day"].date()): r["c"] for r in cur.fetchall()}

                cur.execute("""
                    SELECT sensor_id, COUNT(*) AS c
                    FROM sensor_measurements
                    WHERE time >= NOW() - INTERVAL '24 hours'
                    GROUP BY sensor_id ORDER BY c DESC
                    LIMIT 10
                """)
                top_sensors = [{"sensor_id": r["sensor_id"], "samples": r["c"]}
                               for r in cur.fetchall()]

                return {
                    "connected": True,
                    "host": TSDB_HOST,
                    "port": TSDB_PORT,
                    "database": TSDB_DB,
                    "measurements": measurements,
                    "sensors_registered": sensors,
                    "events": events,
                    "training_runs": training_runs,
                    "predictions": predictions,
                    "daily_counts_7d": daily_counts,
                    "top_sensors_24h": top_sensors,
                    "schema_version": 1,
                }
        except Exception as e:
            return {"connected": True, "error": str(e)}

    def hypertable_info(self) -> list[dict]:
        """Infos sur les hypertables pour diagnostique."""
        if not self._ensure_connected():
            return []
        try:
            with self._conn() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("""
                    SELECT hypertable_name, table_schema, num_chunks,
                           compression_state, tablespace
                    FROM timescaledb_information.hypertables
                    ORDER BY hypertable_name
                """)
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            log.error("Erreur hypertable_info", error=str(e))
            return []

    # ── Migration MongoDB → TimescaleDB ─────────────────

    def migrate_from_mongodb(self, hours: int = 720, batch_size: int = 1000) -> dict:
        """Migre les données depuis MongoDB vers TimescaleDB."""
        stats = {"total_read": 0, "total_written": 0, "errors": 0}

        try:
            from pymongo import MongoClient
            client = MongoClient("mongodb://localhost:27017/")
            db = client["agricol_ts"]
            collection = db["mesures_capteurs"]

            since = datetime.now(timezone.utc) - timedelta(hours=hours)
            cursor = collection.find({"timestamp": {"$gte": since}},
                                     sort=[("timestamp", 1)],
                                     batch_size=batch_size)

            batch = []
            for doc in cursor:
                stats["total_read"] += 1
                ts = doc.get("timestamp", doc.get("time", datetime.now(timezone.utc)))
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts)
                    except Exception:
                        ts = datetime.now(timezone.utc)

                batch.append({
                    "time": ts,
                    "sensor_id": doc.get("sensor_id", doc.get("capteur_id", "unknown")),
                    "space_id": doc.get("space_id", doc.get("zone", "")),
                    "value": doc.get("valeur", doc.get("value", 0)),
                    "unit": doc.get("unite", doc.get("unit", "")),
                    "tags": doc.get("metadata", doc.get("tags", {})),
                })

                if len(batch) >= batch_size:
                    written = self.write_batch(batch)
                    stats["total_written"] += written
                    stats["errors"] += len(batch) - written
                    batch = []

            if batch:
                written = self.write_batch(batch)
                stats["total_written"] += written
                stats["errors"] += len(batch) - written

            client.close()
            log.info("Migration MongoDB→TimescaleDB terminée",
                     read=stats["total_read"], written=stats["total_written"])
            return stats

        except ImportError:
            log.warning("pymongo non installé — migration MongoDB impossible")
            stats["error"] = "pymongo not installed"
            return stats
        except Exception as e:
            log.error("Erreur migration MongoDB", error=str(e))
            stats["error"] = str(e)
            return stats

    def seed_test_data(self, days: int = 30, interval_minutes: int = 15,
                       sensors: list[dict] = None) -> dict:
        """Génère des données de test réalistes."""
        if sensors is None:
            sensors = [
                {"sensor_id": "temp_serre_a", "space_id": "serre_a", "unit": "°C",
                 "base": 22.0, "amplitude": 8.0, "noise": 0.5, "type": "temperature"},
                {"sensor_id": "hum_serre_a", "space_id": "serre_a", "unit": "%",
                 "base": 65.0, "amplitude": 10.0, "noise": 2.0, "type": "humidite"},
                {"sensor_id": "lum_serre_a", "space_id": "serre_a", "unit": "lux",
                 "base": 25000, "amplitude": 15000, "noise": 500, "type": "lumiere"},
                {"sensor_id": "sol_serre_a", "space_id": "serre_a", "unit": "%",
                 "base": 45.0, "amplitude": 10.0, "noise": 1.5, "type": "humidite_sol"},
                {"sensor_id": "temp_plein_champ", "space_id": "plein_champ", "unit": "°C",
                 "base": 20.0, "amplitude": 10.0, "noise": 0.8, "type": "temperature"},
                {"sensor_id": "hum_plein_champ", "space_id": "plein_champ", "unit": "%",
                 "base": 55.0, "amplitude": 15.0, "noise": 3.0, "type": "humidite"},
            ]

        now = datetime.now(timezone.utc)
        total = 0
        for s in sensors:
            self.register_sensor(
                s["sensor_id"], s["space_id"],
                s.get("type", "unknown"),
                s["sensor_id"], s["unit"],
            )
            pts = []
            for day in range(days):
                for interval in range(24 * 60 // interval_minutes):
                    t = now - timedelta(days=day, minutes=interval * interval_minutes)
                    hour_factor = np.sin(2 * np.pi * t.hour / 24 - np.pi / 2)
                    value = s["base"] + s["amplitude"] * 0.5 * hour_factor + \
                            np.random.normal(0, s["noise"])
                    value = max(0, round(value, 2))
                    pts.append({
                        "time": t,
                        "sensor_id": s["sensor_id"],
                        "space_id": s["space_id"],
                        "value": value,
                        "unit": s["unit"],
                        "tags": {"type": s.get("type", ""), "simulated": True},
                    })

            written = self.write_batch(pts)
            total += written

        log.info("Données de test TimescaleDB générées", points=total, days=days)
        return {"points_generated": total, "sensors": len(sensors), "days": days}


tsdb = TimescaleDBManager()
