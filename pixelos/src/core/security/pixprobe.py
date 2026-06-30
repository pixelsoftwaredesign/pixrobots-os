# Pixel Software Design � Copyright 2026
import subprocess
import re
from datetime import datetime
from collections import defaultdict


PROTOCOL_SIGNATURES = {
    "matrix": {
        "ports": [443, 8448, 6167],
        "patterns": [br"_matrix", br"m\.room\.",
                     br"/_synapse/admin", br"access_token="],
        "name": "Matrix (Chat/Vidéo)",
        "color": "#0dbd8b",
    },
    "ipfs": {
        "ports": [4001, 4002, 5001, 8080],
        "patterns": [br"/ipfs/", br"/ipns/", br"libp2p",
                     br"/p2p/", br"multihash"],
        "name": "IPFS (Données décentralisées)",
        "color": "#6acad1",
    },
    "blockchain": {
        "ports": [8545, 8546, 8547, 30303],
        "patterns": [br"jsonrpc", br'"method":"eth_',
                     br'"jsonrpc":"2.0"', br"web3",
                     br"ethereum", br"gnosis"],
        "name": "Blockchain (Paiements/Smart Contracts)",
        "color": "#627eea",
    },
    "mqtt": {
        "ports": [1883, 8883],
        "patterns": [br"MQTT", br"CONNECT", br"SUBSCRIBE",
                     br"agricol/", br"pixelos/"],
        "name": "MQTT (Capteurs IoT)",
        "color": "#f16529",
    },
    "wireguard": {
        "ports": [51820],
        "patterns": [br"WireGuard", br"wg0"],
        "name": "WireGuard (VPN Mesh)",
        "color": "#881136",
    },
    "dns": {
        "ports": [53, 5300],
        "patterns": [br"\.pixel", br"pixelos", br"agricol\.local"],
        "name": "DNS .pixel (Résolution locale)",
        "color": "#d29922",
    },
    "web": {
        "ports": [80, 443, 8080, 9999],
        "patterns": [br"HTTP/", br"GET /", br"POST /",
                     br"Host:", br"text/html"],
        "name": "Web (HTTP/HTTPS)",
        "color": "#58a6ff",
    },
    "ftp": {
        "ports": [21, 20],
        "patterns": [br"FTP", br"220 ", br"230 "],
        "name": "FTP (Transfert fichiers)",
        "color": "#f85149",
    },
}

PROTOCOL_BY_PORT = {}
for proto_name, sig in PROTOCOL_SIGNATURES.items():
    for port in sig["ports"]:
        PROTOCOL_BY_PORT[port] = proto_name


class PixProbe:
    def __init__(self):
        self.history = []
        self.samples = []

    def classify_by_port(self, port):
        return PROTOCOL_BY_PORT.get(port, "unknown")

    def get_protocol_info(self, proto_name):
        return PROTOCOL_SIGNATURES.get(proto_name, {
            "name": f"Inconnu ({proto_name})",
            "color": "#8b949e",
        })

    def analyze_connections(self, connections):
        by_protocol = defaultdict(list)
        by_protocol_count = Counter()
        for conn in connections:
            try:
                port = int(conn.get("port", 0))
            except (ValueError, TypeError):
                port = 0
            proto = self.classify_by_port(port)
            by_protocol[proto].append(conn)
            by_protocol_count[proto] += 1

        enriched = []
        for proto, conns in by_protocol.items():
            info = self.get_protocol_info(proto)
            enriched.append({
                "protocol": proto,
                "name": info["name"],
                "color": info["color"],
                "count": len(conns),
                "connections": conns[:20],
            })

        enriched.sort(key=lambda x: -x["count"])
        return {
            "by_protocol": enriched,
            "total_connections": sum(p["count"] for p in enriched),
            "timestamp": datetime.now().isoformat(),
        }

    def analyze_by_tcpdump(self, count=50, iface="vio0"):
        try:
            r = subprocess.run(
                ["tcpdump", "-c", str(count), "-i", iface, "-nn", "-t"],
                capture_output=True, text=True, timeout=30
            )
        except Exception:
            return {"error": "tcpdump failed", "packets": [], "count": 0}

        packets = []
        for line in r.stdout.splitlines():
            if not line.strip():
                continue
            proto = "unknown"
            src_ip = src_port = dst_ip = dst_port = ""
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)\.(\d+)\s+>\s+(\d+\.\d+\.\d+\.\d+)\.(\d+)", line)
            if m:
                src_ip, src_port, dst_ip, dst_port = m.groups()
            if "Flags" in line or "seq" in line:
                proto = "tcp"
            elif "SPORT" in line or "DPORT" in line:
                proto = "udp"
            if "ICMP" in line.upper():
                proto = "icmp"

            try:
                sport = int(src_port) if src_port else 0
                dport = int(dst_port) if dst_port else 0
            except ValueError:
                sport = dport = 0

            p = self.classify_by_port(sport)
            if p == "unknown":
                p = self.classify_by_port(dport)
            proto = p
            info = self.get_protocol_info(proto)

            packets.append({
                "raw": line[:200],
                "src": f"{src_ip}:{src_port}",
                "dst": f"{dst_ip}:{dst_port}",
                "protocol_class": proto,
                "protocol_name": info["name"],
                "color": info["color"],
            })

        return {
            "packets": packets,
            "count": len(packets),
            "iface": iface,
            "timestamp": datetime.now().isoformat(),
        }

    def analyze_by_lsof(self):
        try:
            r = subprocess.run(
                ["lsof", "-i", "-P", "-n"],
                capture_output=True, text=True, timeout=15
            )
        except Exception:
            return {"error": "lsof failed", "processes": [], "count": 0}

        by_proto = defaultdict(lambda: {"processes": set(), "count": 0})
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) < 9:
                continue
            proto_field = parts[4] if len(parts) > 4 else ""
            name = parts[0]
            proc_ports = parts[8]
            m = re.search(r":(\d+)", proc_ports)
            if not m:
                continue
            port = int(m.group(1))
            p = self.classify_by_port(port)
            by_proto[p]["processes"].add(name)
            by_proto[p]["count"] += 1

        result = []
        for proto, data in by_proto.items():
            info = self.get_protocol_info(proto)
            result.append({
                "protocol": proto,
                "name": info["name"],
                "color": info["color"],
                "processes": sorted(data["processes"]),
                "connections": data["count"],
            })
        result.sort(key=lambda x: -x["connections"])
        return {"by_protocol": result, "total": sum(r["connections"] for r in result)}

    def summary(self):
        return {
            "protocols": list(PROTOCOL_SIGNATURES.keys()),
            "protocol_details": {k: {"name": v["name"], "ports": v["ports"], "color": v["color"]}
                                 for k, v in PROTOCOL_SIGNATURES.items()},
            "total_signatures": len(PROTOCOL_SIGNATURES),
        }


from collections import Counter
