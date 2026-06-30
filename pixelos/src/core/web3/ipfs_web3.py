# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""Pont Web3 IPFS — Souveraineté décentralisée pour PixelOS.

Fonctionnalités:
  - Publication site web PixelOS sur IPFS (DNSLink)
  - Hébergement décentralisé des fichiers communautaires
  - Synchronisation des profils membres via IPNS
  - Gateway IPFS locale pour le réseau .pixel
"""

import json
import structlog
import os
import subprocess
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "web3" / "ipfs"
SITES_DIR = DATA_DIR / "sites"
PUBLIC_DIR = DATA_DIR / "public"
MANIFEST_FILE = DATA_DIR / "manifest.json"

IPFS_REPO = Path("/var/db/pixelos/ipfs/repo")

DNSLINK_RECORDS = {
    "_dnslink.pixelos.pxl": "dnslink=/ipns/",
    "_dnslink.wallet.pxl": "dnslink=/ipns/",
    "_dnslink.hub.pxl": "dnslink=/ipns/",
    "_dnslink.community.pxl": "dnslink=/ipns/",
}

class Web3IPFS:
    """Pont IPFS Web3 pour PixelOS — stockage décentralisé souverain."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SITES_DIR.mkdir(parents=True, exist_ok=True)
        PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
        self._available = self._check_ipfs()
        self.manifest: dict = {}
        self._load_manifest()

    def _check_ipfs(self) -> bool:
        try:
            r = subprocess.run(["ipfs", "--version"],
                               capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    @property
    def available(self) -> bool:
        return self._available

    def _load_manifest(self):
        if MANIFEST_FILE.exists():
            try:
                self.manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.manifest = {}

    def _save_manifest(self):
        MANIFEST_FILE.write_text(
            json.dumps(self.manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    def _ipfs_env(self) -> dict:
        env = os.environ.copy()
        if IPFS_REPO.exists():
            env["IPFS_PATH"] = str(IPFS_REPO)
        return env

    # ── Publication de contenu ──────────────────────────

    def publish_site(self, source_dir: str | Path,
                     site_name: str = "pixelos") -> Optional[dict]:
        """Publie un répertoire statique sur IPFS."""
        if not self._available:
            return {"status": "error", "message": "IPFS non installé"}

        src = Path(source_dir)
        if not src.is_dir():
            return {"status": "error", "message": "Répertoire source introuvable"}

        try:
            r = subprocess.run(
                ["ipfs", "add", "-Q", "--pin", "-r", str(src)],
                env=self._ipfs_env(),
                capture_output=True, text=True, timeout=60
            )
            cid = r.stdout.strip()

            # Publier IPNS
            key_name = f"site-{site_name}"
            subprocess.run(
                ["ipfs", "key", "gen", key_name],
                env=self._ipfs_env(), capture_output=True, timeout=10
            )
            ipns_r = subprocess.run(
                ["ipfs", "name", "publish", f"/ipfs/{cid}", f"--key={key_name}"],
                env=self._ipfs_env(), capture_output=True, text=True, timeout=30
            )
            ipns_name = ipns_r.stdout.strip() if ipns_r.returncode == 0 else ""

            entry = {
                "site": site_name,
                "cid": cid,
                "ipns": ipns_name,
                "path": str(src),
                "published": datetime.now().isoformat(),
                "size_bytes": sum(f.stat().st_size for f in src.rglob("*") if f.is_file()),
            }
            self.manifest[site_name] = entry
            self._save_manifest()

            log.info("Site publié sur IPFS", site=site_name, cid=cid, ipns=ipns_name)
            return entry

        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "TimeOut IPFS"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def publish_file(self, file_path: str | Path,
                     pin: bool = True) -> Optional[dict]:
        """Publie un fichier sur IPFS."""
        if not self._available:
            return None
        fp = Path(file_path)
        if not fp.exists():
            return None

        try:
            r = subprocess.run(
                ["ipfs", "add", "-Q", "--pin" if pin else "",
                 str(fp)],
                env=self._ipfs_env(),
                capture_output=True, text=True, timeout=30
            )
            cid = r.stdout.strip()
            return {
                "cid": cid,
                "file": str(fp),
                "size": fp.stat().st_size,
                "pinned": pin,
                "published": datetime.now().isoformat(),
            }
        except Exception:
            return None

    def publish_json(self, data: dict, name: str = "data",
                     pin: bool = True) -> Optional[dict]:
        """Publie un objet JSON sur IPFS."""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.close()
        result = self.publish_file(tmp.name, pin)
        os.unlink(tmp.name)
        return result

    def fetch(self, cid_or_ipns: str) -> Optional[bytes]:
        """Récupère le contenu depuis IPFS."""
        if not self._available:
            return None
        try:
            r = subprocess.run(
                ["ipfs", "cat", cid_or_ipns],
                env=self._ipfs_env(),
                capture_output=True, timeout=30
            )
            return r.stdout if r.returncode == 0 else None
        except Exception:
            return None

    def fetch_json(self, cid_or_ipns: str) -> Optional[dict]:
        data = self.fetch(cid_or_ipns)
        if data:
            try:
                return json.loads(data.decode())
            except Exception:
                pass
        return None

    # ── DNSLink ─────────────────────────────────────────

    def generate_dnslink(self, cid: str, subdomain: str = "") -> dict:
        """Génère les enregistrements DNSLink pour un CID."""
        domain = f"_dnslink.{subdomain}.pxl" if subdomain else "_dnslink.pxl"
        return {
            "record": domain,
            "value": f"dnslink=/ipfs/{cid}",
            "type": "TXT",
            "ttl": 3600,
        }

    def publish_dnslink(self, subdomain: str, cid: str) -> dict:
        """Prépare la mise à jour DNSLink."""
        domain = f"_dnslink.{subdomain}.pxl" if subdomain else "_dnslink.pxl"
        entry = {
            "domain": domain,
            "value": f"dnslink=/ipfs/{cid}",
            "cid": cid,
            "subdomain": subdomain,
            "updated": datetime.now().isoformat(),
        }
        dnslink_file = DATA_DIR / "dnslink.json"
        dnslink_data = {}
        if dnslink_file.exists():
            dnslink_data = json.loads(dnslink_file.read_text(encoding="utf-8"))
        dnslink_data[subdomain or "root"] = entry
        dnslink_file.write_text(
            json.dumps(dnslink_data, indent=2, ensure_ascii=False), encoding="utf-8")

        log.info("DNSLink préparé", domain=domain, cid=cid)
        return entry

    def list_dnslink(self) -> dict:
        dnslink_file = DATA_DIR / "dnslink.json"
        if dnslink_file.exists():
            return json.loads(dnslink_file.read_text(encoding="utf-8"))
        return {}

    # ── Gestion des clés IPNS ───────────────────────────

    def list_keys(self) -> list[dict]:
        """Liste les clés IPNS."""
        if not self._available:
            return []
        try:
            r = subprocess.run(
                ["ipfs", "key", "list", "-l"],
                env=self._ipfs_env(),
                capture_output=True, text=True, timeout=10
            )
            keys = []
            for line in r.stdout.strip().split("\n"):
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        keys.append({"id": parts[0], "name": parts[1]})
            return keys
        except Exception:
            return []

    # ── Pin management ──────────────────────────────────

    def pin(self, cid: str) -> bool:
        try:
            subprocess.run(["ipfs", "pin", "add", cid],
                           env=self._ipfs_env(),
                           capture_output=True, timeout=30)
            return True
        except Exception:
            return False

    def unpin(self, cid: str) -> bool:
        try:
            subprocess.run(["ipfs", "pin", "rm", cid],
                           env=self._ipfs_env(),
                           capture_output=True, timeout=30)
            return True
        except Exception:
            return False

    def list_pins(self) -> list[str]:
        try:
            r = subprocess.run(["ipfs", "pin", "ls", "--type=recursive"],
                               env=self._ipfs_env(),
                               capture_output=True, text=True, timeout=15)
            return [line.split()[0] for line in r.stdout.strip().split("\n") if line]
        except Exception:
            return []

    # ── Stats ───────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "available": self._available,
            "published_sites": list(self.manifest.keys()),
            "sites_count": len(self.manifest),
            "pin_count": len(self.list_pins()) if self._available else 0,
            "keys_count": len(self.list_keys()) if self._available else 0,
            "dnslink_records": self.list_dnslink(),
        }


web3_ipfs = Web3IPFS()
