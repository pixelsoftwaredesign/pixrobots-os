# Pixel OS — Copyright 2026
# Free License — Verifiable and Reliable for Internet Users
# Pixel Software Design — Copyright 2026
import json
import os
import time
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from .pixstat import PixStat
from .pixdefend import PixDefend


PROFILE_DIR = "/var/db/pixelos/profiles"
DEFAULT_PROFILE_PATH = os.path.join(PROFILE_DIR, "traffic_baseline.json")
LEARNING_WINDOW_HOURS = 24
LEARNING_INTERVAL_S = 300


class TrafficProfile:
    def __init__(self):
        self.hourly_avg_connections = defaultdict(float)
        self.hourly_max_connections = defaultdict(int)
        self.known_ips = {}  # ip -> {"first_seen": ..., "avg_conns": ..., "max_conns": ...}
        self.known_protocols = defaultdict(float)
        self.bandwidth_avg_rx = 0
        self.bandwidth_avg_tx = 0
        self.bandwidth_max_rx = 0
        self.bandwidth_max_tx = 0
        self.sample_count = 0
        self.learned_at = None
        self.learning_hours = 0

    def to_dict(self):
        return {
            "hourly_avg_connections": dict(self.hourly_avg_connections),
            "hourly_max_connections": dict(self.hourly_max_connections),
            "known_ips": self.known_ips,
            "known_protocols": dict(self.known_protocols),
            "bandwidth_avg_rx": self.bandwidth_avg_rx,
            "bandwidth_avg_tx": self.bandwidth_avg_tx,
            "bandwidth_max_rx": self.bandwidth_max_rx,
            "bandwidth_max_tx": self.bandwidth_max_tx,
            "sample_count": self.sample_count,
            "learned_at": self.learned_at,
            "learning_hours": self.learning_hours,
        }

    @classmethod
    def from_dict(cls, data):
        p = cls()
        p.hourly_avg_connections = defaultdict(float, data.get("hourly_avg_connections", {}))
        p.hourly_max_connections = defaultdict(int, data.get("hourly_max_connections", {}))
        p.known_ips = data.get("known_ips", {})
        p.known_protocols = defaultdict(float, data.get("known_protocols", {}))
        p.bandwidth_avg_rx = data.get("bandwidth_avg_rx", 0)
        p.bandwidth_avg_tx = data.get("bandwidth_avg_tx", 0)
        p.bandwidth_max_rx = data.get("bandwidth_max_rx", 0)
        p.bandwidth_max_tx = data.get("bandwidth_max_tx", 0)
        p.sample_count = data.get("sample_count", 0)
        p.learned_at = data.get("learned_at")
        p.learning_hours = data.get("learning_hours", 0)
        return p


class TrafficProfiler:
    def __init__(self, profile_path=DEFAULT_PROFILE_PATH):
        self.pixstat = PixStat()
        self.pixdefend = PixDefend()
        self.profile_path = profile_path
        self.profile = None
        self.learning = False
        self.learning_start = None
        self.samples = []
        self._load_profile()

    def _profile_dir(self):
        d = os.path.dirname(self.profile_path)
        os.makedirs(d, exist_ok=True)
        return d

    def _load_profile(self):
        if os.path.exists(self.profile_path):
            try:
                with open(self.profile_path) as f:
                    self.profile = TrafficProfile.from_dict(json.load(f))
                return True
            except Exception:
                pass
        self.profile = TrafficProfile()
        return False

    def _save_profile(self):
        self._profile_dir()
        with open(self.profile_path, "w") as f:
            json.dump(self.profile.to_dict(), f, indent=2)

    def status(self):
        return {
            "learning": self.learning,
            "learning_start": self.learning_start,
            "samples": len(self.samples),
            "baseline_exists": os.path.exists(self.profile_path),
            "profile": self.profile.to_dict() if self.profile else None,
        }

    def start_learning(self, hours=24):
        self.learning = True
        self.learning_start = datetime.now().isoformat()
        self.samples = []
        self.profile = TrafficProfile()
        self.profile.learning_hours = hours
        self._save_profile()
        return {"status": "started", "hours": hours, "started_at": self.learning_start}

    def stop_learning(self):
        if not self.learning:
            return {"status": "not_learning"}
        self.learning = False
        self._finalize_profile()
        self._save_profile()
        return {"status": "stopped", "samples": len(self.samples)}

    def _finalize_profile(self):
        if not self.samples:
            return
        profile = self.profile
        by_hour = defaultdict(list)
        known_ips = defaultdict(list)
        protocol_hits = defaultdict(list)
        all_rx = []
        all_tx = []

        for s in self.samples:
            try:
                h = datetime.fromisoformat(s["timestamp"]).hour
            except Exception:
                h = 0
            conns = s.get("connections", 0)
            by_hour[h].append(conns)

            bw = s.get("bandwidth", {})
            all_rx.append(bw.get("rx_bytes_per_sec", 0))
            all_tx.append(bw.get("tx_bytes_per_sec", 0))

            for ip, count in s.get("by_ip", {}).items():
                known_ips[ip].append(count)

            for proto, count in s.get("by_protocol", {}).items():
                protocol_hits[proto].append(count)

        for hour, values in by_hour.items():
            profile.hourly_avg_connections[hour] = sum(values) / len(values)
            profile.hourly_max_connections[hour] = max(values)

        for ip, counts in known_ips.items():
            profile.known_ips[ip] = {
                "first_seen": self.samples[0]["timestamp"],
                "last_seen": self.samples[-1]["timestamp"],
                "avg_conns": sum(counts) / len(counts),
                "max_conns": max(counts),
                "total_observations": len(counts),
            }

        for proto, counts in protocol_hits.items():
            profile.known_protocols[proto] = sum(counts) / len(counts)

        profile.bandwidth_avg_rx = sum(all_rx) / len(all_rx) if all_rx else 0
        profile.bandwidth_avg_tx = sum(all_tx) / len(all_tx) if all_tx else 0
        profile.bandwidth_max_rx = max(all_rx) if all_rx else 0
        profile.bandwidth_max_tx = max(all_tx) if all_tx else 0
        profile.sample_count = len(self.samples)
        profile.learned_at = datetime.now().isoformat()

    def collect_sample(self, protocol_data=None):
        stats = self.pixstat.summary()
        sample = {
            "timestamp": datetime.now().isoformat(),
            "connections": stats["connections"],
            "by_ip": stats.get("by_ip", {}),
            "bandwidth": stats.get("bandwidth", {}),
            "by_protocol": protocol_data or {},
        }
        self.samples.append(sample)

        if self.learning:
            elapsed_h = self.learning_start and \
                (datetime.now() - datetime.fromisoformat(self.learning_start)).total_seconds() / 3600
            if elapsed_h and elapsed_h >= self.profile.learning_hours:
                self.stop_learning()
                return {"status": "learning_complete", "samples": len(self.samples)}
            return {"status": "learning", "samples": len(self.samples),
                    "progress_pct": min(100, int(elapsed_h / self.profile.learning_hours * 100)) \
                        if elapsed_h else 0}
        return {"status": "sampled", "sample": len(self.samples)}

    def detect_anomalies(self, protocol_data=None):
        if not self.profile or self.profile.sample_count == 0:
            return {"anomalies": [], "note": "Aucune baseline â€” lancez l'apprentissage d'abord"}

        now = datetime.now()
        hour = now.hour
        stats = self.pixstat.summary()

        anomalies = []

        conns = stats["connections"]
        avg = self.profile.hourly_avg_connections.get(hour, 0)
        mx = self.profile.hourly_max_connections.get(hour, 0)

        threshold = max(avg * 3, mx * 1.5)
        if threshold > 10 and conns > threshold:
            anomalies.append({
                "type": "traffic_spike",
                "severity": "high" if conns > threshold * 2 else "medium",
                "message": f"Pic de connexions: {conns} (baseline: {avg:.0f}, max: {mx})",
                "current": conns,
                "baseline_avg": avg,
                "baseline_max": mx,
                "hour": hour,
                "timestamp": now.isoformat(),
            })

        bw = stats.get("bandwidth", {})
        rx = bw.get("rx_bytes_per_sec", 0)
        tx = bw.get("tx_bytes_per_sec", 0)
        bw_threshold_rx = max(self.profile.bandwidth_avg_rx * 5, self.profile.bandwidth_max_rx * 2)
        bw_threshold_tx = max(self.profile.bandwidth_avg_tx * 5, self.profile.bandwidth_max_tx * 2)

        if bw_threshold_rx > 10000 and rx > bw_threshold_rx:
            anomalies.append({
                "type": "bandwidth_spike_rx",
                "severity": "high" if rx > bw_threshold_rx * 2 else "medium",
                "message": f"Pic bande passante entrante: {rx} B/s (baseline: {self.profile.bandwidth_avg_rx:.0f} B/s)",
                "current": rx, "baseline_avg": self.profile.bandwidth_avg_rx,
                "baseline_max": self.profile.bandwidth_max_rx,
                "timestamp": now.isoformat(),
            })

        if bw_threshold_tx > 10000 and tx > bw_threshold_tx:
            anomalies.append({
                "type": "bandwidth_spike_tx",
                "severity": "high" if tx > bw_threshold_tx * 2 else "medium",
                "message": f"Pic bande passante sortante: {tx} B/s (baseline: {self.profile.bandwidth_avg_tx:.0f} B/s)",
                "current": tx, "baseline_avg": self.profile.bandwidth_avg_tx,
                "baseline_max": self.profile.bandwidth_max_tx,
                "timestamp": now.isoformat(),
            })

        by_ip = stats.get("by_ip", {})
        for ip, count in by_ip.items():
            if ip in self.profile.known_ips:
                info = self.profile.known_ips[ip]
                ip_threshold = max(info["avg_conns"] * 4, info["max_conns"] * 2)
                if ip_threshold > 5 and count > ip_threshold:
                    anomalies.append({
                        "type": "ip_anomaly",
                        "severity": "high" if count > ip_threshold * 2 else "medium",
                        "message": f"ActivitÃ© anormale {ip}: {count} connexions (baseline: {info['avg_conns']:.0f})",
                        "ip": ip, "current": count,
                        "baseline_avg": info["avg_conns"],
                        "baseline_max": info["max_conns"],
                        "timestamp": now.isoformat(),
                    })
            else:
                anomalies.append({
                    "type": "unknown_ip",
                    "severity": "low",
                    "message": f"IP inconnue dÃ©tectÃ©e: {ip} ({count} connexions)",
                    "ip": ip, "count": count,
                    "timestamp": now.isoformat(),
                })

        if protocol_data:
            for proto, count in protocol_data.items():
                baseline = self.profile.known_protocols.get(proto, 0)
                if baseline > 0 and count > baseline * 5:
                    anomalies.append({
                        "type": "protocol_anomaly",
                        "severity": "medium",
                        "message": f"Trafic {proto} anormal: {count} (baseline: {baseline:.0f})",
                        "protocol": proto, "current": count, "baseline": baseline,
                        "timestamp": now.isoformat(),
                    })

        blocked = []
        for a in anomalies:
            if a["type"] in ("traffic_spike", "ip_anomaly", "unknown_ip") and \
               a.get("ip") and a["severity"] == "high":
                ip = a["ip"]
                if ip not in self.pixdefend.blocked_ips:
                    r = self.pixdefend.auto_block(ip, a["type"])
                    blocked.append({"ip": ip, "reason": a["type"], "result": r})

        return {
            "anomalies": anomalies,
            "blocked": blocked,
            "total_anomalies": len(anomalies),
            "total_blocked": len(blocked),
            "timestamp": now.isoformat(),
        }

    def learning_progress(self):
        if not self.learning or not self.learning_start:
            return {"learning": False, "progress_pct": 100 if self.profile and self.profile.sample_count > 0 else 0}
        elapsed = (datetime.now() - datetime.fromisoformat(self.learning_start)).total_seconds()
        total = self.profile.learning_hours * 3600
        pct = min(100, int(elapsed / total * 100))
        remaining_h = max(0, (total - elapsed) / 3600)
        return {
            "learning": True,
            "progress_pct": pct,
            "samples": len(self.samples),
            "elapsed_h": round(elapsed / 3600, 1),
            "remaining_h": round(remaining_h, 1),
            "started_at": self.learning_start,
        }

    def reset_profile(self):
        self.profile = TrafficProfile()
        self.samples = []
        self.learning = False
        self.learning_start = None
        if os.path.exists(self.profile_path):
            os.remove(self.profile_path)
        return {"status": "reset"}
