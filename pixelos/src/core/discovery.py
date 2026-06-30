# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""discovery — Découverte, fingerprinting et catalogage unifié des dispositifs IoT.

Supporte 4 protocoles : Wi-Fi (mDNS/MQTT), BLE, Radio (LoRa/433MHz), Modbus RS485.

Device lifecycle:
  discovered → fingerprinted → provisioned → active → retired

Chaque device est stocké dans device_catalog (TimescaleDB) avec fallback JSON.
"""

import json
import structlog
import subprocess
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "devices"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FINGERPRINT_DB = {
    # Wi-Fi / MQTT - capteurs sol
    "soil-moisture-*": {"manufacturer": "Generic", "device_type": "capteur_sol", "sensor_type": "humidite_sol"},
    "temp-humidity-*": {"manufacturer": "Generic", "device_type": "capteur_sol", "sensor_type": "temperature"},
    # BLE - balises
    "PIXL-*": {"manufacturer": "PixelOS", "device_type": "gateway", "sensor_type": "multisensor"},
    # Modbus
    "modbus:1-50": {"manufacturer": "Generic", "device_type": "capteur_sol", "sensor_type": "humidite_sol"},
    "modbus:100-150": {"manufacturer": "Generic", "device_type": "vanne", "sensor_type": "valve"},
}

PROTOCOLS = ["wifi", "ble", "radio", "modbus"]
STATUSES = ["discovered", "fingerprinted", "provisioned", "active", "retired"]


class DeviceManager:
    """Gestionnaire unifié de catalogage de dispositifs IoT."""

    def __init__(self):
        self._cache = {}
        self._tsdb_ready = False

    # ── Persistance ──────────────────────────────────────

    def _tsdb(self):
        from core.tsdb import tsdb
        return tsdb

    def _ensure_schema(self):
        if self._tsdb_ready:
            return True
        try:
            tsdb = self._tsdb()
            if not tsdb.connected:
                tsdb.connect()
            if tsdb.connected:
                with tsdb._conn() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS device_catalog (
                            device_id TEXT PRIMARY KEY,
                            protocol TEXT NOT NULL DEFAULT 'unknown',
                            fingerprint TEXT NOT NULL DEFAULT '',
                            manufacturer TEXT DEFAULT '',
                            model TEXT DEFAULT '',
                            device_type TEXT DEFAULT 'unknown',
                            sensor_type TEXT DEFAULT '',
                            space_id TEXT DEFAULT '',
                            space_label TEXT DEFAULT '',
                            parent_device_id TEXT DEFAULT '',
                            status TEXT DEFAULT 'discovered',
                            provision_step INTEGER DEFAULT 0,
                            ip_address TEXT DEFAULT '',
                            mac_address TEXT DEFAULT '',
                            mqtt_topic TEXT DEFAULT '',
                            last_seen TIMESTAMPTZ,
                            firmware_version TEXT DEFAULT '',
                            signal_strength INTEGER DEFAULT 0,
                            battery_level REAL DEFAULT 100.0,
                            meta JSONB DEFAULT '{}',
                            discovered_at TIMESTAMPTZ DEFAULT NOW(),
                            provisioned_at TIMESTAMPTZ,
                            active_at TIMESTAMPTZ,
                            retired_at TIMESTAMPTZ
                        )
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_dc_protocol ON device_catalog (protocol)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_dc_status ON device_catalog (status)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_dc_space ON device_catalog (space_id)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_dc_type ON device_catalog (device_type)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_dc_last_seen ON device_catalog (last_seen DESC)
                    """)
                    conn.commit()
                self._tsdb_ready = True
                log.info("device_catalog schema ready")
                return True
        except Exception as e:
            log.warning("device_catalog TSDB indisponible, fallback JSON", error=str(e))
            return False

    def _json_path(self) -> Path:
        return DATA_DIR / "device_catalog.json"

    def _load_json(self) -> dict[str, dict]:
        p = self._json_path()
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_json(self, data: dict[str, dict]):
        self._json_path().write_text(
            json.dumps(data, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8")

    def _write_tsdb(self, device: dict) -> bool:
        try:
            tsdb = self._tsdb()
            if not tsdb.connected:
                return False
            with tsdb._conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO device_catalog (
                        device_id, protocol, fingerprint, manufacturer, model,
                        device_type, sensor_type, space_id, space_label,
                        parent_device_id, status, provision_step,
                        ip_address, mac_address, mqtt_topic, last_seen,
                        firmware_version, signal_strength, battery_level, meta,
                        discovered_at, provisioned_at, active_at, retired_at
                    ) VALUES (
                        %(device_id)s, %(protocol)s, %(fingerprint)s, %(manufacturer)s, %(model)s,
                        %(device_type)s, %(sensor_type)s, %(space_id)s, %(space_label)s,
                        %(parent_device_id)s, %(status)s, %(provision_step)s,
                        %(ip_address)s, %(mac_address)s, %(mqtt_topic)s, %(last_seen)s,
                        %(firmware_version)s, %(signal_strength)s, %(battery_level)s, %(meta)s,
                        %(discovered_at)s, %(provisioned_at)s, %(active_at)s, %(retired_at)s
                    )
                    ON CONFLICT (device_id) DO UPDATE SET
                        protocol = EXCLUDED.protocol,
                        fingerprint = EXCLUDED.fingerprint,
                        manufacturer = EXCLUDED.manufacturer,
                        model = EXCLUDED.model,
                        device_type = EXCLUDED.device_type,
                        sensor_type = EXCLUDED.sensor_type,
                        space_id = EXCLUDED.space_id,
                        space_label = EXCLUDED.space_label,
                        status = EXCLUDED.status,
                        provision_step = EXCLUDED.provision_step,
                        ip_address = EXCLUDED.ip_address,
                        mac_address = EXCLUDED.mac_address,
                        mqtt_topic = EXCLUDED.mqtt_topic,
                        last_seen = EXCLUDED.last_seen,
                        firmware_version = EXCLUDED.firmware_version,
                        signal_strength = EXCLUDED.signal_strength,
                        battery_level = EXCLUDED.battery_level,
                        meta = EXCLUDED.meta,
                        provisioned_at = EXCLUDED.provisioned_at,
                        active_at = EXCLUDED.active_at,
                        retired_at = EXCLUDED.retired_at
                """, device)
                conn.commit()
            return True
        except Exception as e:
            log.warning("Erreur ecriture device_catalog TSDB", error=str(e))
            return False

    def _query_tsdb(self, status: str = None, protocol: str = None,
                    space_id: str = None, device_type: str = None) -> list[dict]:
        try:
            tsdb = self._tsdb()
            if not tsdb.connected:
                return []
            conditions = []
            params = {}
            if status:
                conditions.append("status = %(status)s")
                params["status"] = status
            if protocol:
                conditions.append("protocol = %(protocol)s")
                params["protocol"] = protocol
            if space_id:
                conditions.append("space_id = %(space_id)s")
                params["space_id"] = space_id
            if device_type:
                conditions.append("device_type = %(device_type)s")
                params["device_type"] = device_type
            where = " WHERE " + " AND ".join(conditions) if conditions else ""

            with tsdb._conn() as conn:
                import psycopg2.extras
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute(f"""
                    SELECT * FROM device_catalog {where}
                    ORDER BY last_seen DESC NULLS LAST, discovered_at DESC
                """, params)
                rows = []
                for r in cur.fetchall():
                    d = dict(r)
                    for k in ("last_seen", "discovered_at", "provisioned_at", "active_at", "retired_at"):
                        if isinstance(d.get(k), datetime):
                            d[k] = d[k].isoformat()
                    rows.append(d)
                return rows
        except Exception as e:
            log.warning("Erreur query device_catalog TSDB", error=str(e))
            return []

    # ── Registration ─────────────────────────────────────

    def register_device(self, device_id: str, protocol: str = "unknown",
                        fingerprint: str = "", manufacturer: str = "",
                        model: str = "", device_type: str = "unknown",
                        sensor_type: str = "", space_id: str = "",
                        ip_address: str = "", mac_address: str = "",
                        signal_strength: int = 0, battery_level: float = 100.0,
                        meta: dict = None) -> dict:
        """Enregistre un nouveau dispositif découvert."""
        meta = meta or {}
        now = datetime.now(timezone.utc)
        device = {
            "device_id": device_id,
            "protocol": protocol,
            "fingerprint": fingerprint,
            "manufacturer": manufacturer,
            "model": model,
            "device_type": device_type,
            "sensor_type": sensor_type,
            "space_id": space_id,
            "space_label": meta.get("space_label", ""),
            "parent_device_id": meta.get("parent_device_id", ""),
            "status": "discovered",
            "provision_step": 0,
            "ip_address": ip_address,
            "mac_address": mac_address,
            "mqtt_topic": meta.get("mqtt_topic", f"pixelos/{device_id}"),
            "last_seen": now,
            "firmware_version": meta.get("firmware_version", ""),
            "signal_strength": signal_strength,
            "battery_level": battery_level,
            "meta": json.dumps(meta),
            "discovered_at": now,
            "provisioned_at": None,
            "active_at": None,
            "retired_at": None,
        }

        # Try TSDB first, fallback JSON
        if not self._write_tsdb(device):
            data = self._load_json()
            data[device_id] = device
            self._save_json(data)

        log.info("Device enregistre", device_id=device_id, protocol=protocol,
                 device_type=device_type)
        return device

    # ── Fingerprinting ───────────────────────────────────

    def fingerprint(self, device_id: str, protocol: str,
                    fingerprint_str: str, meta: dict = None) -> Optional[dict]:
        """Identifie le type de dispositif à partir d'un fingerprint."""
        meta = meta or {}
        match = None

        # Chercher dans FINGERPRINT_DB
        for pattern, info in FINGERPRINT_DB.items():
            if protocol == "wifi" and pattern.endswith("*"):
                if fingerprint_str.startswith(pattern.rstrip("*")):
                    match = info
                    break
            elif protocol == "ble" and pattern.endswith("*"):
                if fingerprint_str.startswith(pattern.rstrip("*")):
                    match = info
                    break
            elif protocol == "modbus" and pattern.startswith("modbus:"):
                try:
                    addr = int(fingerprint_str)
                    range_str = pattern.split(":")[1]
                    lo, hi = range_str.split("-")
                    if int(lo) <= addr <= int(hi):
                        match = info
                        break
                except (ValueError, IndexError):
                    pass

        if match:
            result = dict(match)
            result["fingerprint"] = fingerprint_str
            self._update(device_id, {
                "manufacturer": match["manufacturer"],
                "device_type": match["device_type"],
                "sensor_type": match.get("sensor_type", ""),
                "status": "fingerprinted",
                "provision_step": 1,
                "meta": json.dumps({**meta, "fingerprint_matched": pattern}),
            })
            log.info("Device fingerprinted", device_id=device_id,
                     device_type=match["device_type"])
            return result

        return None

    # ── CRUD ─────────────────────────────────────────────

    def get_device(self, device_id: str) -> Optional[dict]:
        rows = self._query_tsdb()
        for r in rows:
            if r["device_id"] == device_id:
                return r
        return self._load_json().get(device_id)

    def list_devices(self, status: str = None, protocol: str = None,
                     space_id: str = None, device_type: str = None) -> list[dict]:
        rows = self._query_tsdb(status, protocol, space_id, device_type)
        if rows:
            return rows
        # Fallback JSON
        data = self._load_json().values()
        result = list(data)
        if status:
            result = [d for d in result if d.get("status") == status]
        if protocol:
            result = [d for d in result if d.get("protocol") == protocol]
        if space_id:
            result = [d for d in result if d.get("space_id") == space_id]
        if device_type:
            result = [d for d in result if d.get("device_type") == device_type]
        return result

    def _update(self, device_id: str, updates: dict) -> bool:
        """Update interne (sans log)."""
        now = datetime.now(timezone.utc)
        updates.setdefault("last_seen", now)

        # TSDB
        try:
            tsdb = self._tsdb()
            if tsdb.connected:
                sets = []
                params = {"device_id": device_id}
                for k, v in updates.items():
                    sets.append(f"{k} = %({k})s")
                    params[k] = v
                if "last_seen" not in updates:
                    updates["last_seen"] = now
                with tsdb._conn() as conn:
                    cur = conn.cursor()
                    cur.execute(f"""
                        UPDATE device_catalog
                        SET {', '.join(sets)}
                        WHERE device_id = %(device_id)s
                    """, params)
                    conn.commit()
                return True
        except Exception:
            pass

        # Fallback JSON
        data = self._load_json()
        if device_id in data:
            data[device_id].update(updates)
            self._save_json(data)
            return True
        return False

    def update_device(self, device_id: str, **kwargs) -> bool:
        """Met à jour les champs d'un dispositif."""
        ok = self._update(device_id, kwargs)
        if ok:
            log.info("Device mis à jour", device_id=device_id, updates=list(kwargs.keys()))
        return ok

    def delete_device(self, device_id: str) -> bool:
        """Supprime un dispositif."""
        deleted = False
        try:
            tsdb = self._tsdb()
            if tsdb.connected:
                with tsdb._conn() as conn:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM device_catalog WHERE device_id = %s", (device_id,))
                    conn.commit()
                deleted = True
        except Exception:
            pass
        # Fallback JSON
        data = self._load_json()
        if device_id in data:
            del data[device_id]
            self._save_json(data)
            deleted = True
        if deleted:
            log.info("Device supprime", device_id=device_id)
        return deleted

    # ── Provisioning ─────────────────────────────────────

    def provision(self, device_id: str, space_id: str = "",
                  space_label: str = "", device_type: str = None) -> bool:
        """Passe un dispositif de fingerprinted → provisioned."""
        updates = {
            "status": "provisioned",
            "provision_step": 2,
            "provisioned_at": datetime.now(timezone.utc),
        }
        if space_id:
            updates["space_id"] = space_id
        if space_label:
            updates["space_label"] = space_label
        if device_type:
            updates["device_type"] = device_type
        ok = self._update(device_id, updates)
        if ok:
            log.info("Device provisionne", device_id=device_id, space=space_id)
        return ok

    def activate(self, device_id: str) -> bool:
        """Passe un dispositif en actif."""
        ok = self._update(device_id, {
            "status": "active",
            "provision_step": 3,
            "active_at": datetime.now(timezone.utc),
        })
        if ok:
            log.info("Device active", device_id=device_id)
        return ok

    def retire(self, device_id: str) -> bool:
        """Passe un dispositif en retraité."""
        ok = self._update(device_id, {
            "status": "retired",
            "provision_step": -1,
            "retired_at": datetime.now(timezone.utc),
        })
        if ok:
            log.info("Device retire", device_id=device_id)
        return ok

    # ── Scan ─────────────────────────────────────────────

    def scan_wifi(self, timeout: int = 10) -> list[dict]:
        """Scan Wi-Fi via mDNS/avahi pour découvrir des services _pixelos._tcp."""
        found = []
        try:
            # avahi-browse pour les services mDNS PixelOS
            r = subprocess.run(
                ["avahi-browse", "-apt", "_pixelos._tcp"],
                capture_output=True, text=True, timeout=timeout,
            )
            for line in r.stdout.splitlines():
                parts = line.split(";")
                if len(parts) >= 8:
                    hostname = parts[6]
                    ip = parts[7]
                    txt = parts[8] if len(parts) > 8 else ""
                    device_id = f"wifi-{hostname}"
                    found.append({
                        "device_id": device_id,
                        "protocol": "wifi",
                        "fingerprint": hostname,
                        "ip_address": ip,
                        "meta": {"hostname": hostname, "txt": txt},
                    })
        except FileNotFoundError:
            log.debug("avahi-browse non installe, skip scan Wi-Fi mDNS")
        except subprocess.TimeoutExpired:
            log.debug("Scan Wi-Fi mDNS timeout")
        except Exception as e:
            log.debug("Erreur scan Wi-Fi", error=str(e))

        # Ajouter aussi les devices déjà enregistrés avec IP
        for d in self.list_devices(protocol="wifi"):
            if d.get("ip_address"):
                found.append({
                    "device_id": d["device_id"],
                    "protocol": "wifi",
                    "fingerprint": d.get("fingerprint", ""),
                    "ip_address": d["ip_address"],
                    "meta": {},
                })

        return found

    def scan_ble(self, timeout: int = 15) -> list[dict]:
        """Scan BLE via bluetoothctl."""
        found = []
        try:
            r = subprocess.run(
                ["bluetoothctl", "--timeout", str(timeout), "scan", "on"],
                capture_output=True, text=True, timeout=timeout + 5,
            )
            devices = set()
            for line in r.stdout.splitlines():
                m = re.search(r"Device\s+([0-9A-Fa-f:]{17})\s+(.*)", line)
                if m:
                    mac = m.group(1).upper()
                    name = m.group(2).strip()
                    device_id = f"ble-{mac}"
                    fingerprint = name or mac
                    if device_id not in devices:
                        devices.add(device_id)
                        found.append({
                            "device_id": device_id,
                            "protocol": "ble",
                            "fingerprint": fingerprint,
                            "mac_address": mac,
                            "meta": {"name": name},
                        })
        except FileNotFoundError:
            log.debug("bluetoothctl non installe, skip scan BLE")
        except Exception as e:
            log.debug("Erreur scan BLE", error=str(e))
        return list(found)

    def scan_modbus(self, start: int = 1, end: int = 247,
                    port: str = "/dev/ttyUSB0", timeout: int = 30) -> list[dict]:
        """Scan Modbus RTU sur RS485."""
        found = []
        try:
            import minimalmodbus
            for addr in range(start, end + 1):
                try:
                    instrument = minimalmodbus.Instrument(port, addr)
                    instrument.serial.baudrate = 9600
                    instrument.serial.timeout = 0.5
                    # Try reading identification
                    identity = instrument.read_string(0x00, 4)
                    device_id = f"modbus-{addr}"
                    found.append({
                        "device_id": device_id,
                        "protocol": "modbus",
                        "fingerprint": str(addr),
                        "model": identity.strip(),
                        "meta": {"address": addr, "identity": identity.strip()},
                    })
                except Exception:
                    continue
        except ImportError:
            log.debug("minimalmodbus non installe, skip scan Modbus")
        except Exception as e:
            log.debug("Erreur scan Modbus", error=str(e))
        return found

    def scan_all(self, timeout: int = 30) -> dict:
        """Lance tous les scans disponibles et enregistre les découvertes."""
        results = {"wifi": [], "ble": [], "modbus": [], "total_new": 0}

        for d in self.scan_wifi(timeout=min(10, timeout)):
            existing = self.get_device(d["device_id"])
            if not existing:
                dev = self.register_device(
                    device_id=d["device_id"],
                    protocol="wifi",
                    fingerprint=d.get("fingerprint", ""),
                    ip_address=d.get("ip_address", ""),
                    meta=d.get("meta", {}),
                )
                self.fingerprint(d["device_id"], "wifi", d["fingerprint"])
                results["wifi"].append(dev)
                results["total_new"] += 1
            else:
                self._update(d["device_id"], {"last_seen": datetime.now(timezone.utc)})
                results["wifi"].append(existing)

        for d in self.scan_ble(timeout=min(15, timeout)):
            existing = self.get_device(d["device_id"])
            if not existing:
                dev = self.register_device(
                    device_id=d["device_id"],
                    protocol="ble",
                    fingerprint=d.get("fingerprint", ""),
                    mac_address=d.get("mac_address", ""),
                    meta=d.get("meta", {}),
                )
                self.fingerprint(d["device_id"], "ble", d["fingerprint"])
                results["ble"].append(dev)
                results["total_new"] += 1
            else:
                self._update(d["device_id"], {"last_seen": datetime.now(timezone.utc)})
                results["ble"].append(existing)

        for d in self.scan_modbus(timeout=min(30, timeout)):
            existing = self.get_device(d["device_id"])
            if not existing:
                dev = self.register_device(
                    device_id=d["device_id"],
                    protocol="modbus",
                    fingerprint=d.get("fingerprint", ""),
                    model=d.get("model", ""),
                    meta=d.get("meta", {}),
                )
                self.fingerprint(d["device_id"], "modbus", d["fingerprint"])
                results["modbus"].append(dev)
                results["total_new"] += 1
            else:
                self._update(d["device_id"], {"last_seen": datetime.now(timezone.utc)})
                results["modbus"].append(existing)

        log.info("Scan terminé", total_new=results["total_new"],
                 wifi=len(results["wifi"]), ble=len(results["ble"]),
                 modbus=len(results["modbus"]))
        return results

    # ── Stats ────────────────────────────────────────────

    def stats(self) -> dict:
        """Statistiques du catalogue de dispositifs."""
        devices = self.list_devices()
        by_protocol = {}
        by_status = {}
        by_type = {}
        for d in devices:
            p = d.get("protocol", "unknown")
            by_protocol[p] = by_protocol.get(p, 0) + 1
            s = d.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
            t = d.get("device_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total": len(devices),
            "by_protocol": by_protocol,
            "by_status": by_status,
            "by_type": by_type,
            "fingerprint_db_size": len(FINGERPRINT_DB),
            "tsdb_ready": self._tsdb_ready,
        }


# Singleton
device_manager = DeviceManager()
