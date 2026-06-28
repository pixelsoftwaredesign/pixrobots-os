"""Gestion des mises à jour firmware OTA pour ESP32/Arduino."""

import os
import subprocess
import json
import structlog
from pathlib import Path
from datetime import datetime, time
from typing import Optional


log = structlog.get_logger()


class FirmwareOTA:
    """Build, signe, et déploie les firmwares sur les nœuds."""

    def __init__(self, repo_path: str = "/var/lib/pixelos/firmware",
                 arduino_cli: str = "arduino-cli",
                 esp_tool: str = "esptool.py"):
        self.repo = Path(repo_path)
        self.repo.mkdir(parents=True, exist_ok=True)
        self.arduino_cli = arduino_cli
        self.esp_tool = esp_tool

    def build(self, node_type: str, variant: str = "release") -> Path:
        """Compile le firmware pour un type de nœud."""
        fw_dir = Path(f"../firmware/{node_type}")
        if not fw_dir.exists():
            raise FileNotFoundError(f"Source firmware introuvable: {fw_dir}")

        build_dir = self.repo / node_type / variant
        build_dir.mkdir(parents=True, exist_ok=True)

        log.info("Compilation firmware", type=node_type, variant=variant)
        result = subprocess.run(
            [self.arduino_cli, "compile", "--fqbn", "esp32:esp32:esp32",
             "--output-dir", str(build_dir), str(fw_dir)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            log.error("Échec compilation", error=result.stderr)
            raise RuntimeError(f"Compilation échouée: {result.stderr}")

        firmware_path = build_dir / f"{node_type}.bin"
        log.info("Firmware compilé", path=str(firmware_path))
        return firmware_path

    def list_versions(self) -> dict:
        """Liste les versions disponibles pour chaque type."""
        versions = {}
        for d in self.repo.iterdir():
            if d.is_dir():
                for v in d.iterdir():
                    bin_files = list(v.glob("*.bin"))
                    if bin_files:
                        versions.setdefault(d.name, []).append({
                            "variant": v.name,
                            "files": [str(f) for f in bin_files],
                            "modified": datetime.fromtimestamp(
                                max(f.stat().st_mtime for f in bin_files)
                            ).isoformat(),
                        })
        return versions

    def flash(self, node_id: str, firmware_path: Path,
              port: str = "/dev/ttyUSB0") -> bool:
        """Flash le firmware sur un nœud via OTA ou série."""
        ext = firmware_path.suffix.lower()

        if ext == ".bin":
            cmd = [self.esp_tool, "--chip", "esp32",
                   "--port", port, "--baud", "921600",
                   "write_flash", "-z", "0x1000", str(firmware_path)]
        else:
            log.error("Format firmware non supporté", ext=ext)
            return False

        log.info("Flash firmware", node=node_id, port=port)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            log.error("Échec flash", error=result.stderr)
            return False

        log.info("Flash réussi", node=node_id)
        return True

    def ota_update(self, node_ip: str, firmware_path: Path) -> bool:
        """Mise à jour OTA via Wi-Fi pour ESP32."""
        from urllib import request

        url = f"http://{node_ip}/update"
        try:
            with open(firmware_path, "rb") as f:
                data = f.read()
            req = request.Request(url, data=data,
                                  headers={"Content-Type": "application/octet-stream"})
            request.urlopen(req, timeout=60)
            log.info("OTA réussi", node=node_ip)
            return True
        except Exception as e:
            log.error("Échec OTA", node=node_ip, error=str(e))
            return False
