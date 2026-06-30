# Pixel Software Design � Copyright 2026
#!/usr/bin/env python3
"""
PixManager Daemon — Service de monitoring des processus Pixel OS
Lance la détection automatique des nouveaux processus et la surveillance
des ressources en arrière-plan.
"""
import sys
import os
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "pixelos" / "src"))

from core.process_manager.pixmanager import PixManager


def main():
    pm = PixManager()
    pid_file = "/var/run/pixmanager.pid"
    log_file = "/var/log/pixelos/pixmanager.log"

    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))

    pm.start_monitoring(interval=5)

    with open(log_file, "a") as log:
        log.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] PixManager démarré (PID {os.getpid()})\n")

    try:
        while True:
            time.sleep(60)
            stats = pm.stats()
            with open(log_file, "a") as log:
                log.write(json.dumps({
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "total": stats["total_processes"],
                    "new": stats["new_processes_total"],
                    "monitoring": stats["monitoring"],
                }) + "\n")
    except KeyboardInterrupt:
        pm.stop_monitoring()
        with open(log_file, "a") as log:
            log.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] PixManager arrêté\n")


if __name__ == "__main__":
    main()
