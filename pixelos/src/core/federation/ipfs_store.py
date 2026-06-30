"""Stockage décentralisé IPFS pour les données biodiversité PixelOS.

Permet à chaque nœud de:
  - Publier les données publiques biodiversité sur IPFS
  - Synchroniser le registre mondial des espèces via IPNS
  - Distribuer les mises à jour PixelOS sans serveur central
"""

from __future__ import annotations
import json, os, subprocess, tempfile, hashlib
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import datetime


IPFS_DIR = Path("/var/db/pixelos/ipfs")
IPFS_REPO = IPFS_DIR / "repo"
IPFS_PINNED = IPFS_DIR / "pinned"
IPNS_KEY = IPFS_DIR / "ipns.key"
BOOTSTRAP_PEERS = [
    "/dnsaddr/bootstrap.pixelos.org/p2p/",  # À compléter avec le peer-id fondateur
]


@dataclass
class IPFSPublish:
    """Enregistrement d'une publication IPFS."""
    cid: str
    ipns: str = ""
    path: str = ""
    published: str = ""
    size: int = 0
    record_count: int = 0
    node_id: str = ""


class IPFSStore:
    """Pont IPFS pour PixelOS — publication et synchronisation décentralisée."""

    def __init__(self):
        self._available = self._check_ipfs()
        os.makedirs(IPFS_DIR, exist_ok=True)

    def _check_ipfs(self) -> bool:
        """Vérifie si IPFS est disponible."""
        try:
            r = subprocess.run(["ipfs", "--version"],
                               capture_output=True, timeout=5)
            return r.returncode == 0
        except:
            return False

    @property
    def available(self) -> bool:
        return self._available

    def init_repo(self) -> dict:
        """Initialise le dépôt IPFS local."""
        if not self._available:
            return {"status": "error", "message": "IPFS non installé"}
        if IPFS_REPO.exists():
            return {"status": "ok", "message": "Dépôt déjà initialisé"}

        try:
            os.environ["IPFS_PATH"] = str(IPFS_REPO)
            subprocess.run(["ipfs", "init"],
                           check=True, capture_output=True,
                           env={"IPFS_PATH": str(IPFS_REPO)})

            # Configurer pour le réseau privé PixelOS
            subprocess.run(["ipfs", "config", "--json",
                           "Bootstrap", json.dumps(BOOTSTRAP_PEERS)],
                           check=True, env={"IPFS_PATH": str(IPFS_REPO)})
            subprocess.run(["ipfs", "config", "--json",
                           "Swarm.DisableNatPortMap", "false"],
                           check=True, env={"IPFS_PATH": str(IPFS_REPO)})

            return {"status": "ok", "message": "Dépôt IPFS initialisé",
                    "path": str(IPFS_REPO)}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": e.stderr.decode()}

    def start_daemon(self) -> dict:
        """Lance le daemon IPFS."""
        if not self._available:
            return {"status": "error", "message": "IPFS non installé"}
        try:
            subprocess.Popen(
                ["ipfs", "daemon", "--enable-gc"],
                env={"IPFS_PATH": str(IPFS_REPO)},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"status": "ok", "message": "Daemon IPFS démarré"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def stop_daemon(self) -> dict:
        try:
            subprocess.run(["ipfs", "shutdown"],
                           env={"IPFS_PATH": str(IPFS_REPO)},
                           capture_output=True, timeout=10)
            return {"status": "ok", "message": "Daemon IPFS arrêté"}
        except:
            return {"status": "error", "message": "Impossible d'arrêter le daemon"}

    def publish_biodiversity(self, records: list[dict],
                             node_id: str = "") -> Optional[IPFSPublish]:
        """Publie les données biodiversité sur IPFS et retourne le CID."""
        if not self._available:
            return None

        manifest = {
            "type": "pixelos-biodiversity",
            "version": "2.0",
            "node_id": node_id,
            "published": datetime.now().isoformat(),
            "record_count": len(records),
            "records": records,
        }

        # Écrire dans un fichier temporaire et ajouter à IPFS
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(manifest, tmp, ensure_ascii=False, indent=2)
        tmp.close()

        try:
            r = subprocess.run(
                ["ipfs", "add", "-Q", "--pin", tmp.name],
                env={"IPFS_PATH": str(IPFS_REPO)},
                capture_output=True, text=True, timeout=30
            )
            cid = r.stdout.strip()
            os.unlink(tmp.name)

            # Publier sur IPNS
            ipns_name = self._publish_ipns(cid)

            pub = IPFSPublish(
                cid=cid,
                ipns=ipns_name or "",
                path=tmp.name,
                published=manifest["published"],
                size=os.path.getsize(tmp.name) if os.path.exists(tmp.name) else 0,
                record_count=len(records),
                node_id=node_id,
            )

            # Sauvegarder localement
            os.makedirs(IPFS_PINNED, exist_ok=True)
            with open(IPFS_PINNED / f"{cid[:12]}.json", "w") as f:
                json.dump(asdict(pub), f, ensure_ascii=False, indent=2)

            return pub
        except Exception as e:
            return None

    def _publish_ipns(self, cid: str) -> Optional[str]:
        """Publie le CID sur IPNS."""
        try:
            # Générer une clé IPNS si pas déjà faite
            key_name = "pixelos-node"
            subprocess.run(
                ["ipfs", "key", "gen", key_name],
                env={"IPFS_PATH": str(IPFS_REPO)},
                capture_output=True, timeout=10
            )

            r = subprocess.run(
                ["ipfs", "name", "publish", f"/ipfs/{cid}", f"--key={key_name}"],
                env={"IPFS_PATH": str(IPFS_REPO)},
                capture_output=True, text=True, timeout=30
            )
            return r.stdout.strip()
        except:
            return None

    def fetch_biodiversity(self, cid_or_ipns: str) -> Optional[dict]:
        """Récupère les données biodiversité depuis IPFS."""
        if not self._available:
            return None
        try:
            r = subprocess.run(
                ["ipfs", "cat", cid_or_ipns],
                env={"IPFS_PATH": str(IPFS_REPO)},
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                return json.loads(r.stdout)
        except:
            pass
        return None

    def sync_global_registry(self, bootstrap_nodes: list[str]) -> list[dict]:
        """Synchronise le registre mondial depuis le réseau IPFS."""
        all_records = []
        for node in bootstrap_nodes:
            try:
                # Essayer de récupérer depuis IPNS du nœud
                data = self.fetch_biodiversity(f"/ipns/{node}")
                if data and data.get("records"):
                    all_records.extend(data["records"])
            except:
                pass
        return all_records

    def pin_species(self, record_cid: str) -> bool:
        """Pinner un CID pour garantir sa disponibilité."""
        try:
            subprocess.run(["ipfs", "pin", "add", record_cid],
                           env={"IPFS_PATH": str(IPFS_REPO)},
                           capture_output=True, timeout=30)
            return True
        except:
            return False

    def status(self) -> dict:
        """État du nœud IPFS."""
        if not self._available:
            return {"available": False, "message": "IPFS non installé"}
        try:
            r = subprocess.run(
                ["ipfs", "id"],
                env={"IPFS_PATH": str(IPFS_REPO)},
                capture_output=True, text=True, timeout=10
            )
            info = json.loads(r.stdout) if r.returncode == 0 else {}
            return {
                "available": True,
                "peer_id": info.get("ID", ""),
                "addresses": info.get("Addresses", []),
                "pinned": len(list(IPFS_PINNED.glob("*.json"))),
            }
        except:
            return {"available": False, "message": "Daemon IPFS non lancé"}


ipfs_store = IPFSStore()
