#!/usr/bin/env python3
"""
PixStat / Heartbeat — Statistiques système et heartbeat PixelOS.

Collecte:
  - Connexions réseau, interfaces, bande passante
  - CPU, mémoire, disque
  - Heartbeat MQTT périodique
  - Uptime, temperature CPU
  - Alertes auto en cas de seuils dépassés
"""

import os
import json
import time
import subprocess
import re
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

STAT_DIR = "/var/db/pixelos/pixstat"
HB_INTERVAL = 30
ALERT_CPU = 80
ALERT_MEM = 85
ALERT_DISK = 90


class PixStat:
    def __init__(self):
        self._ensure_dirs()
        self.history = []
        self.alerts = []
        self.blocklist = set()
        self._stop = threading.Event()
        self._hb_thread: Optional[threading.Thread] = None
        self._start_heartbeat()

    def _ensure_dirs(self):
        Path(STAT_DIR).mkdir(parents=True, exist_ok=True)

    # ── Réseau ────────────────────────────────────────────

    def get_connections(self):
        try:
            r = subprocess.run(
                ["netstat", "-nt", "-f", "inet"],
                capture_output=True, text=True, timeout=10
            )
        except Exception:
            return {"connections": [], "total": 0}

        conns = []
        for line in r.stdout.splitlines():
            if "ESTABLISHED" not in line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            remote = parts[4]
            ip = remote.rsplit(".", 1)[0] if "." in remote else remote
            port = remote.rsplit(".", 1)[-1] if "." in remote else ""
            local = parts[3]
            conns.append({
                "local": local, "remote": remote,
                "ip": ip, "port": port,
            })

        by_ip = Counter(c["ip"] for c in conns)
        return {
            "connections": conns,
            "total": len(conns),
            "by_ip": dict(by_ip),
            "timestamp": datetime.now().isoformat(),
        }

    def get_interfaces(self):
        try:
            r = subprocess.run(
                ["ifconfig"],
                capture_output=True, text=True, timeout=10
            )
        except Exception:
            return []
        ifaces, current = [], {}
        for line in r.stdout.splitlines():
            m = re.match(r"^(\w[\w0-9]*):", line)
            if m:
                if current:
                    ifaces.append(current)
                current = {"name": m.group(1), "inet": [], "status": "down"}
            m2 = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", line)
            if m2 and current:
                current["inet"].append(m2.group(1))
            if "status: active" in line and current:
                current["status"] = "up"
            if "status: no carrier" in line and current:
                current["status"] = "no carrier"
        if current:
            ifaces.append(current)
        return ifaces

    def get_bandwidth(self, iface="vio0", interval=2):
        try:
            r1 = subprocess.run(
                ["netstat", "-I", iface, "-b"],
                capture_output=True, text=True, timeout=10
            )
            time.sleep(interval)
            r2 = subprocess.run(
                ["netstat", "-I", iface, "-b"],
                capture_output=True, text=True, timeout=10
            )
        except Exception:
            return {"rx_bytes": 0, "tx_bytes": 0}

        def parse_bytes(out):
            for line in out.splitlines():
                if iface in line and "bytes" in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        try:
                            return int(parts[2]), int(parts[4])
                        except ValueError:
                            pass
            return 0, 0

        rx1, tx1 = parse_bytes(r1.stdout)
        rx2, tx2 = parse_bytes(r2.stdout)
        return {
            "rx_bytes_per_sec": max(0, (rx2 - rx1) // interval),
            "tx_bytes_per_sec": max(0, (tx2 - tx1) // interval),
            "iface": iface,
        }

    # ── Système ───────────────────────────────────────────

    def get_cpu(self):
        try:
            if os.name == "nt":
                import psutil
                return {"percent": psutil.cpu_percent(interval=1)}
            r = subprocess.run(["sysctl", "hw.cpuhistory"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                vals = re.findall(r"(\d+\.?\d*)", r.stdout)
                if vals:
                    return {"percent": sum(float(v) for v in vals) / len(vals)}
            # Fallback: vmstat
            r2 = subprocess.run(["vmstat", "1", "2"],
                                capture_output=True, text=True, timeout=5)
            lines = r2.stdout.splitlines()
            if len(lines) >= 3:
                parts = lines[-1].split()
                if len(parts) >= 16:
                    idle = float(parts[-1])
                    return {"percent": max(0, 100 - idle)}
        except Exception:
            pass
        return {"percent": 0}

    def get_memory(self):
        try:
            r = subprocess.run(["sysctl", "hw.usermem", "hw.physmem"],
                               capture_output=True, text=True, timeout=5)
            mems = {}
            for line in r.stdout.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    mems[k.strip()] = int(v.strip())
            total = mems.get("hw.physmem", 0)
            user = mems.get("hw.usermem", 0)
            if total > 0:
                percent = round(100 * (1 - user / total), 1)
                return {"total": total, "used": total - user, "percent": percent}
        except Exception:
            pass
        return {"percent": 0}

    def get_disk(self):
        try:
            r = subprocess.run(["df", "-h", "/"],
                               capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0].startswith("/"):
                    usage = parts[4].replace("%", "")
                    return {"percent": float(usage), "total": parts[1],
                            "used": parts[2], "available": parts[3]}
        except Exception:
            pass
        return {"percent": 0}

    def get_uptime(self):
        try:
            r = subprocess.run(["sysctl", "kern.boottime"],
                               capture_output=True, text=True, timeout=5)
            m = re.search(r"(\d+)", r.stdout)
            if m:
                boot = int(m.group(1))
                uptime = time.time() - boot
                return {"uptime_s": uptime, "uptime_str": self._format_uptime(uptime)}
        except Exception:
            pass
        return {"uptime_s": 0}

    def get_temp(self):
        try:
            r = subprocess.run(["sysctl", "hw.sensors"],
                               capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                if "temp" in line.lower():
                    m = re.search(r"(\d+\.?\d*)\s*degC", line)
                    if m:
                        return {"celsius": float(m.group(1))}
        except Exception:
            pass
        return {"celsius": 0}

    @staticmethod
    def _format_uptime(s):
        d = s // 86400
        h = (s % 86400) // 3600
        m = (s % 3600) // 60
        return f"{int(d)}j {int(h)}h {int(m)}m"

    # ── Summary ───────────────────────────────────────────

    def summary(self):
        conns = self.get_connections()
        ifaces = self.get_interfaces()
        bw = self.get_bandwidth()
        cpu = self.get_cpu()
        mem = self.get_memory()
        disk = self.get_disk()
        uptime = self.get_uptime()
        temp = self.get_temp()

        warnings = []
        if cpu.get("percent", 0) > ALERT_CPU:
            warnings.append(f"CPU à {cpu['percent']}%")
        if mem.get("percent", 0) > ALERT_MEM:
            warnings.append(f"Mémoire à {mem['percent']}%")
        if disk.get("percent", 0) > ALERT_DISK:
            warnings.append(f"Disque à {disk['percent']}%")

        record = {
            "connections": conns["total"],
            "by_ip": conns["by_ip"],
            "interfaces": ifaces,
            "bandwidth": bw,
            "cpu": cpu,
            "memory": mem,
            "disk": disk,
            "uptime": uptime,
            "temperature": temp,
            "blocklist_size": len(self.blocklist),
            "warnings": warnings,
            "alerts_count": len(self.alerts),
            "timestamp": conns["timestamp"],
        }
        self.history.append(record)
        self.history = self.history[-1000:]
        return record

    def snapshot(self):
        return self.summary()

    # ── Heartbeat MQTT ────────────────────────────────────

    def _start_heartbeat(self):
        def loop():
            while not self._stop.is_set():
                self._stop.wait(HB_INTERVAL)
                if self._stop.is_set():
                    break
                try:
                    self._publish_heartbeat()
                except Exception:
                    pass
        self._hb_thread = threading.Thread(target=loop, daemon=True)
        self._hb_thread.start()

    def _publish_heartbeat(self):
        try:
            from core.mqtt import PixelOSMQTT
            mqtt = PixelOSMQTT()
            stats = self.summary()
            hostname = os.uname().nodename if hasattr(os, "uname") else "pixelos"
            node_id = hashlib.sha256(hostname.encode()).hexdigest()[:16]
            import hashlib
            node_id = hashlib.sha256(hostname.encode()).hexdigest()[:16]

            hb = {
                "hostname": hostname,
                "node_id": node_id,
                "cpu": stats["cpu"],
                "memory": stats["memory"],
                "disk": stats["disk"],
                "uptime": stats["uptime"],
                "temperature": stats["temperature"],
                "connections": stats["connections"],
                "warnings": stats["warnings"],
                "ts": datetime.now().isoformat(),
            }
            mqtt.publish(f"pixelos/node/{node_id}/heartbeat", json.dumps(hb))
            if stats["warnings"]:
                mqtt.publish(f"pixelos/node/{node_id}/alerts", json.dumps({
                    "alerts": stats["warnings"], "ts": hb["ts"],
                }))
        except Exception:
            pass

    def send_heartbeat_now(self) -> dict:
        self._publish_heartbeat()
        return {"status": "sent"}

    def stop_heartbeat(self):
        self._stop.set()
        if self._hb_thread:
            self._hb_thread.join(timeout=5)

    # ── History ───────────────────────────────────────────

    def get_history(self, limit: int = 100) -> list:
        return self.history[-limit:]

    def clear_history(self) -> dict:
        self.history.clear()
        return {"status": "cleared"}

    def get_alerts(self) -> list:
        return self.alerts[-100:] if self.alerts else []

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> dict:
        s = self.summary()
        return {
            **s,
            "heartbeat_active": self._hb_thread is not None and self._hb_thread.is_alive(),
            "history_size": len(self.history),
            "blocklist_size": len(self.blocklist),
        }
