import subprocess
import re
import time
from collections import Counter
from datetime import datetime


class PixStat:
    def __init__(self):
        self.history = []
        self.blocklist = set()

    def get_connections(self):
        try:
            r = subprocess.run(
                ["netstat", "-nt", "-f", "inet"],
                capture_output=True, text=True, timeout=10
            )
        except Exception:
            return {"connections": [], "total": 0, "error": "netstat failed"}

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
                "ip": ip, "port": port, "proto": "tcp",
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

        ifaces = []
        current = {}
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

    def get_routes(self):
        try:
            r = subprocess.run(
                ["netstat", "-rn", "-f", "inet"],
                capture_output=True, text=True, timeout=10
            )
        except Exception:
            return []

        routes = []
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            if not re.match(r"^\d+\.", parts[0]):
                continue
            routes.append({
                "destination": parts[0],
                "gateway": parts[1],
                "flags": parts[2] if len(parts) > 2 else "",
            })
        return routes

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
            return {"rx_bytes": 0, "tx_bytes": 0, "error": True}

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
            "interval_s": interval,
            "iface": iface,
        }

    def summary(self):
        conns = self.get_connections()
        ifaces = self.get_interfaces()
        bw = self.get_bandwidth()
        return {
            "connections": conns["total"],
            "by_ip": conns["by_ip"],
            "interfaces": ifaces,
            "bandwidth": bw,
            "blocklist_size": len(self.blocklist),
            "timestamp": conns["timestamp"],
        }

    def snapshot(self):
        return self.summary()
