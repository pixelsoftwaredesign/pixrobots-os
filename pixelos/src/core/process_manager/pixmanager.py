# Pixel Software Design � Copyright 2026
import os
import sys
import time
import signal
import subprocess
import threading
from datetime import datetime
from pathlib import Path

WHITELIST_PATH = "/var/db/pixelos/process_whitelist.json"
PROCESS_LOG_DIR = "/var/log/pixelos/processes"
DEFAULT_WHITELIST = {
    "kernel": ["kernel", "init", "scheduler"],
    "system": ["pfctl", "syslogd", "sshd", "httpd", "nsd",
               "relayd", "ftpd", "dhclient", "ntpd", "iked"],
    "pixelos": ["python3", "pixelos", "pixutil", "conduit",
                "mosquitto", "node-red", "java", "streamlit"],
    "network": ["tcpdump", "ping", "traceroute", "nc", "curl",
                "wget", "dig", "nslookup"],
    "shell": ["ksh", "sh", "bash", "zsh", "csh", "tcsh"],
}

PROCESS_PRIORITY = {
    "pfctl": 100, "relayd": 95, "httpd": 90, "sshd": 85,
    "conduit": 80, "nsd": 75, "mosquitto": 70, "syslogd": 65,
    "python3": 50, "java": 40, "streamlit": 30,
    "node-red": 30, "ksh": 10, "sh": 10, "bash": 10,
}


class PixManager:
    def __init__(self):
        self.known_pids = set()
        self.new_processes = []
        self.monitoring = False
        self._monitor_thread = None
        self._stop_event = threading.Event()
        self._load_whitelist()

    # ── Whitelist ──────────────────────────────────────────

    def _whitelist_path(self):
        Path(WHITELIST_PATH).parent.mkdir(parents=True, exist_ok=True)
        return WHITELIST_PATH

    def _load_whitelist(self):
        if os.path.exists(WHITELIST_PATH):
            try:
                import json
                with open(WHITELIST_PATH) as f:
                    self.whitelist = json.load(f)
                return
            except Exception:
                pass
        self.whitelist = dict(DEFAULT_WHITELIST)
        self._save_whitelist()

    def _save_whitelist(self):
        import json
        self._whitelist_path()
        with open(WHITELIST_PATH, "w") as f:
            json.dump(self.whitelist, f, indent=2)

    def is_whitelisted(self, name):
        name_lower = name.lower()
        for category, procs in self.whitelist.items():
            if name_lower in [p.lower() for p in procs]:
                return category
        return None

    def whitelist_add(self, name, category="custom"):
        name_clean = name.strip().lower()
        for cat, procs in self.whitelist.items():
            if name_clean in [p.lower() for p in procs]:
                return {"status": "exists", "category": cat}
        if category not in self.whitelist:
            self.whitelist[category] = []
        self.whitelist[category].append(name_clean)
        self._save_whitelist()
        return {"status": "added", "name": name_clean, "category": category}

    def whitelist_remove(self, name):
        name_clean = name.strip().lower()
        for cat, procs in list(self.whitelist.items()):
            self.whitelist[cat] = [p for p in procs if p.lower() != name_clean]
            if not self.whitelist[cat]:
                del self.whitelist[cat]
        self._save_whitelist()
        return {"status": "removed", "name": name_clean}

    def whitelist_list(self):
        flat = {}
        for cat, procs in self.whitelist.items():
            for p in procs:
                flat[p] = cat
        return {"by_category": dict(self.whitelist), "flat": flat, "total": len(flat)}

    # ── Process listing ────────────────────────────────────

    def list_processes(self, sort_by="cpu", limit=50):
        try:
            if sys.platform == "openbsd" or os.name == "posix":
                r = subprocess.run(
                    ["ps", "axo", "pid,ppid,pcpu,pmem,rss,vsz,state,start,command"],
                    capture_output=True, text=True, timeout=15
                )
            else:
                r = subprocess.run(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=15
                )
                return self._parse_tasklist(r.stdout, sort_by, limit)
        except Exception:
            return {"processes": [], "total": 0, "error": "ps failed"}

        procs = []
        lines = r.stdout.splitlines()
        if not lines:
            return {"processes": [], "total": 0}

        for line in lines[1:]:
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue
            try:
                pid = int(parts[0])
                ppid = int(parts[1])
                cpu = float(parts[2])
                mem = float(parts[3])
                rss = int(parts[4]) * 1024 if parts[4].isdigit() else 0
                vsz = int(parts[5]) * 1024 if parts[5].isdigit() else 0
                state = parts[6]
                start = parts[7]
                cmd = parts[8][:200]
                name = cmd.split("/")[-1].split()[0] if cmd else ""
            except (ValueError, IndexError):
                continue

            wl = self.is_whitelisted(name)
            prio = PROCESS_PRIORITY.get(name, 20)
            procs.append({
                "pid": pid, "ppid": ppid, "name": name,
                "cpu_pct": cpu, "mem_pct": mem,
                "rss_bytes": rss, "vsz_bytes": vsz,
                "state": state, "started": start,
                "command": cmd,
                "whitelisted": wl is not None,
                "whitelist_category": wl or "unknown",
                "priority": prio,
            })

        if sort_by == "cpu":
            procs.sort(key=lambda p: -p["cpu_pct"])
        elif sort_by == "mem":
            procs.sort(key=lambda p: -p["mem_pct"])
        elif sort_by == "pid":
            procs.sort(key=lambda p: p["pid"])
        elif sort_by == "name":
            procs.sort(key=lambda p: p["name"])
        elif sort_by == "priority":
            procs.sort(key=lambda p: -p["priority"])

        total_cpu = sum(p["cpu_pct"] for p in procs)
        total_mem = sum(p["mem_pct"] for p in procs)
        total_rss = sum(p["rss_bytes"] for p in procs)

        return {
            "processes": procs[:limit],
            "total": len(procs),
            "total_cpu": round(total_cpu, 1),
            "total_mem": round(total_mem, 1),
            "total_rss": total_rss,
            "whitelisted_count": sum(1 for p in procs if p["whitelisted"]),
            "unknown_count": sum(1 for p in procs if not p["whitelisted"]),
            "timestamp": datetime.now().isoformat(),
        }

    def _parse_tasklist(self, output, sort_by, limit):
        import csv, io
        reader = csv.reader(io.StringIO(output))
        procs = []
        for row in reader:
            if len(row) < 8:
                continue
            try:
                pid = int(row[1])
                name = row[0].strip()
                mem_kb = int(row[4].replace(",", "")) if row[4].replace(",", "").isdigit() else 0
            except (ValueError, IndexError):
                continue
            wl = self.is_whitelisted(name)
            procs.append({
                "pid": pid, "ppid": 0, "name": name,
                "cpu_pct": 0, "mem_pct": 0,
                "rss_bytes": mem_kb * 1024, "vsz_bytes": 0,
                "state": "running", "started": "",
                "command": name,
                "whitelisted": wl is not None,
                "whitelist_category": wl or "unknown",
                "priority": PROCESS_PRIORITY.get(name, 20),
            })
        procs.sort(key=lambda p: -p["rss_bytes"])
        return {
            "processes": procs[:limit],
            "total": len(procs),
            "total_cpu": 0, "total_mem": 0,
            "total_rss": sum(p["rss_bytes"] for p in procs),
            "whitelisted_count": sum(1 for p in procs if p["whitelisted"]),
            "unknown_count": sum(1 for p in procs if not p["whitelisted"]),
            "timestamp": datetime.now().isoformat(),
        }

    # ── Process detail ─────────────────────────────────────

    def get_process(self, pid):
        try:
            r = subprocess.run(
                ["ps", "-o", "pid,ppid,pcpu,pmem,rss,vsz,state,start,command", "-p", str(pid)],
                capture_output=True, text=True, timeout=10
            )
        except Exception:
            return {"error": "process not found"}

        lines = r.stdout.splitlines()
        if len(lines) < 2:
            return {"error": f"PID {pid} not found"}

        parts = lines[1].split(None, 8)
        if len(parts) < 9:
            return {"error": "parse error"}

        try:
            name = parts[8].split("/")[-1].split()[0]
            wl = self.is_whitelisted(name)
            return {
                "pid": int(parts[0]), "ppid": int(parts[1]),
                "cpu_pct": float(parts[2]), "mem_pct": float(parts[3]),
                "rss_bytes": int(parts[4]) * 1024,
                "vsz_bytes": int(parts[5]) * 1024,
                "state": parts[6], "started": parts[7],
                "command": parts[8][:500],
                "name": name,
                "whitelisted": wl is not None,
                "whitelist_category": wl or "unknown",
            }
        except (ValueError, IndexError) as e:
            return {"error": str(e)}

    # ── Kill ───────────────────────────────────────────────

    def kill_process(self, pid, sig=signal.SIGTERM):
        try:
            os.kill(pid, sig)
            return {"status": "killed", "pid": pid, "signal": sig}
        except ProcessLookupError:
            return {"status": "not_found", "pid": pid}
        except PermissionError:
            return {"status": "permission_denied", "pid": pid}
        except Exception as e:
            return {"status": "error", "pid": pid, "error": str(e)}

    def kill_by_name(self, name, sig=signal.SIGTERM):
        try:
            r = subprocess.run(
                ["pkill", "-" + str(sig), name],
                capture_output=True, text=True, timeout=10
            )
            return {"status": "ok" if r.returncode == 0 else "not_found",
                    "name": name, "signal": sig, "output": r.stdout}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def kill_all_by_priority(self, max_priority=20):
        procs = self.list_processes(sort_by="priority", limit=500)
        killed = []
        for p in procs.get("processes", []):
            if p.get("whitelisted"):
                continue
            if p.get("priority", 20) <= max_priority:
                r = self.kill_process(p["pid"])
                if r["status"] == "killed":
                    killed.append({"pid": p["pid"], "name": p["name"]})
        return {"killed": killed, "count": len(killed)}

    def kill_by_memory(self, threshold_mb=500):
        procs = self.list_processes(sort_by="mem")
        killed = []
        for p in procs.get("processes", []):
            if p.get("whitelisted"):
                continue
            rss_mb = p.get("rss_bytes", 0) / (1024 * 1024)
            if rss_mb > threshold_mb:
                r = self.kill_process(p["pid"])
                if r["status"] == "killed":
                    killed.append({"pid": p["pid"], "name": p["name"], "rss_mb": round(rss_mb, 1)})
        return {"killed": killed, "count": len(killed)}

    # ── Trace (ktrace) ─────────────────────────────────────

    def trace_process(self, pid, duration=10):
        trace_file = f"/tmp/pixos_trace_{pid}.ktrace"
        try:
            subprocess.run(
                ["ktrace", "-p", str(pid), "-f", trace_file],
                capture_output=True, timeout=duration
            )
            subprocess.run(
                ["ktrace", "-C", "-p", str(pid)],
                capture_output=True, timeout=5
            )
            r = subprocess.run(
                ["kdump", "-f", trace_file, "-l", "-m", "100"],
                capture_output=True, text=True, timeout=10
            )
            lines = r.stdout.splitlines()[:50]
            return {
                "status": "traced", "pid": pid,
                "trace_file": trace_file,
                "duration_s": duration,
                "syscalls": lines,
                "count": len(lines),
            }
        except FileNotFoundError:
            return self._trace_fallback(pid, duration)
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _trace_fallback(self, pid, duration=10):
        try:
            r = subprocess.run(
                ["ps", "-o", "pid,ppid,pcpu,pmem,rss,state,command", "-p", str(pid)],
                capture_output=True, text=True, timeout=5
            )
            snapshots = []
            for _ in range(min(duration, 10)):
                r2 = subprocess.run(
                    ["ps", "-o", "pid,pcpu,pmem,rss,command", "-p", str(pid)],
                    capture_output=True, text=True, timeout=5
                )
                snapshots.append(r2.stdout.strip())
                time.sleep(1)
            return {
                "status": "monitored",
                "pid": pid,
                "duration_s": len(snapshots),
                "snapshots": snapshots,
                "note": "ktrace non disponible, monitoring via ps",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def trace_stop(self, pid):
        try:
            subprocess.run(["ktrace", "-C", "-p", str(pid)], capture_output=True, timeout=5)
            return {"status": "stopped", "pid": pid}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ── New process detection ──────────────────────────────

    def detect_new_processes(self):
        current = set()
        try:
            for p in os.listdir("/proc"):
                if p.isdigit():
                    current.add(int(p))
        except FileNotFoundError:
            try:
                r = subprocess.run(
                    ["ps", "-eo", "pid"],
                    capture_output=True, text=True, timeout=10
                )
                current = set(int(line.strip()) for line in r.stdout.splitlines()
                              if line.strip().isdigit())
            except Exception:
                return {"new": [], "error": "procfs unavailable"}

        if not self.known_pids:
            self.known_pids = current
            return {"new": [], "initialized": True, "known_count": len(current)}

        new_pids = current - self.known_pids
        self.known_pids = current
        new_procs = []
        for pid in new_pids:
            try:
                r = subprocess.run(
                    ["ps", "-o", "pid,ppid,command", "-p", str(pid)],
                    capture_output=True, text=True, timeout=5
                )
                lines = r.stdout.splitlines()
                if len(lines) >= 2:
                    parts = lines[1].split(None, 2)
                    if len(parts) >= 3:
                        cmd = parts[2][:200]
                        name = cmd.split("/")[-1].split()[0]
                        wl = self.is_whitelisted(name)
                        entry = {
                            "pid": pid, "ppid": int(parts[1]),
                            "name": name, "command": cmd,
                            "whitelisted": wl is not None,
                            "whitelist_category": wl or "unknown",
                            "detected_at": datetime.now().isoformat(),
                        }
                        new_procs.append(entry)
                        self.new_processes.append(entry)
            except Exception:
                pass

        return {"new": new_procs, "count": len(new_procs), "known_count": len(current)}

    def get_new_processes(self, since=None):
        if not self.new_processes:
            return {"processes": [], "count": 0}
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
                filtered = [p for p in self.new_processes
                            if datetime.fromisoformat(p["detected_at"]) >= since_dt]
                return {"processes": filtered, "count": len(filtered)}
            except Exception:
                pass
        return {"processes": self.new_processes[-200:], "count": len(self.new_processes)}

    # ── Monitoring daemon ──────────────────────────────────

    def start_monitoring(self, interval=5, callback=None):
        if self.monitoring:
            return {"status": "already_running"}
        self.monitoring = True
        self._stop_event.clear()

        def _run():
            self.detect_new_processes()
            while not self._stop_event.is_set():
                result = self.detect_new_processes()
                if result.get("new") and callback:
                    callback(result["new"])
                if result.get("new"):
                    import json
                    log_path = os.path.join(PROCESS_LOG_DIR, "new_processes.log")
                    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(log_path, "a") as f:
                        for p in result["new"]:
                            f.write(json.dumps(p) + "\n")
                self._stop_event.wait(interval)

        self._monitor_thread = threading.Thread(target=_run, daemon=True)
        self._monitor_thread.start()
        return {"status": "started", "interval_s": interval}

    def stop_monitoring(self):
        self.monitoring = False
        self._stop_event.set()
        return {"status": "stopped"}

    def monitoring_status(self):
        return {
            "monitoring": self.monitoring,
            "known_pids": len(self.known_pids),
            "new_processes_logged": len(self.new_processes),
            "thread_alive": self._monitor_thread and self._monitor_thread.is_alive(),
        }

    # ── Resource summary ───────────────────────────────────

    def resource_summary(self):
        try:
            if sys.platform == "openbsd" or os.name == "posix":
                r = subprocess.run(
                    ["top", "-b", "-n", "1"],
                    capture_output=True, text=True, timeout=15
                )
            else:
                return {"error": "top not available on this platform"}
        except Exception:
            return {"error": "top failed"}

        lines = r.stdout.splitlines()
        summary = {}
        for line in lines:
            if line.startswith("CPU:"):
                summary["cpu"] = line
            elif line.startswith("Memory") or line.startswith("Mem:"):
                summary["memory"] = line
            elif line.startswith("Load"):
                summary["load"] = line
            elif line.startswith("Swap"):
                summary["swap"] = line
            if len(summary) >= 4:
                break

        procs = self.list_processes(sort_by="cpu", limit=5)
        return {
            "top_summary": summary,
            "total_processes": procs["total"],
            "total_cpu_pct": procs["total_cpu"],
            "total_mem_pct": procs["total_mem"],
            "top_cpu": procs["processes"][:5] if procs["processes"] else [],
            "whitelisted": procs["whitelisted_count"],
            "unknown": procs["unknown_count"],
            "monitoring": self.monitoring,
            "timestamp": datetime.now().isoformat(),
        }

    # ── Stats ──────────────────────────────────────────────

    def stats(self):
        procs = self.list_processes(sort_by="cpu", limit=500)
        return {
            "total_processes": procs["total"],
            "total_cpu": procs["total_cpu"],
            "total_mem": procs["total_mem"],
            "total_rss": procs["total_rss"],
            "whitelisted": procs["whitelisted_count"],
            "unknown": procs["unknown_count"],
            "monitoring": self.monitoring,
            "new_processes_total": len(self.new_processes),
            "whitelist_total": self.whitelist_list()["total"],
            "timestamp": datetime.now().isoformat(),
        }
