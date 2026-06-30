# Pixel Software Design � Copyright 2026
"""VPN Manager — WireGuard tunnel + DNS forwarder."""

import os, sys, json, socket, subprocess, time
from pathlib import Path

WIREGUARD_DIR = Path(os.environ.get("USERPROFILE", "~")) / ".pixelos-wg"
CONFIG_DIR = Path(os.environ.get("APPDATA", "~\\AppData\\Roaming")) / "WireGuard" / "Configurations"
WG_EXE = "C:\\Program Files\\WireGuard\\wg.exe"
WG_UI = "C:\\Program Files\\WireGuard\\wireguard.exe"
TUNNEL_NAME = "pixelos"
SERVICE_NAME = f"WireGuardTunnel${TUNNEL_NAME}"
DNS_FORWARDER_SCRIPT = WIREGUARD_DIR / "dns_forwarder.py"

log = __import__("structlog").get_logger()


def _ensure_dir():
    WIREGUARD_DIR.mkdir(parents=True, exist_ok=True)


def _run_wg(*args):
    return subprocess.run([WG_EXE] + list(args), capture_output=True, text=True)


def _is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def _elevate_self():
    """Relance le script courant en admin (bloquant)."""
    import ctypes
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )


def _check_service():
    r = subprocess.run(["sc", "query", SERVICE_NAME], capture_output=True, text=True)
    return "RUNNING" in r.stdout


def _service_exists():
    r = subprocess.run(["sc", "query", SERVICE_NAME], capture_output=True, text=True)
    return "does not exist" not in r.stderr.lower() and r.returncode == 0


FWD_PID_FILE = WIREGUARD_DIR / "dns_forwarder.pid"


def _fwd_running():
    """Vérifie si le forwarder écoute réellement sur 10.0.0.1:53."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("10.0.0.1", 53))
        s.close()
        return True
    except:
        pass
    # Fallback: vérifier PID file
    if FWD_PID_FILE.exists():
        try:
            pid = int(FWD_PID_FILE.read_text().strip())
            proc = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                  capture_output=True, text=True, timeout=3)
            return f"{pid}" in proc.stdout
        except:
            pass
    return False


class VPNForwarder:
    """DNS forwarder sous-processus 10.0.0.1:53 -> 127.0.0.1:5300."""

    def __init__(self):
        self._process = None

    @property
    def running(self):
        if self._process is not None and self._process.poll() is None:
            return True
        return _fwd_running()

    def start(self):
        if self.running:
            return {"status": "ok", "message": "Déjà en cours"}
        if not DNS_FORWARDER_SCRIPT.exists():
            return {"status": "error", "message": "Script forwarder introuvable"}
        self._process = subprocess.Popen(
            [sys.executable, str(DNS_FORWARDER_SCRIPT)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0,
        )
        # Écrire PID file pour détection cross-process
        try:
            FWD_PID_FILE.write_text(str(self._process.pid))
        except:
            pass
        time.sleep(0.5)
        if self.running:
            return {"status": "ok", "message": "DNS forwarder démarré"}
        return {"status": "error", "message": "Échec démarrage forwarder"}

    def stop(self):
        if self._process is not None and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except:
                try:
                    self._process.kill()
                except:
                    pass
            self._process = None
        else:
            # Tuer via PID file ou port
            _kill_fwd()
        try:
            FWD_PID_FILE.unlink()
        except:
            pass
        return {"status": "ok", "message": "DNS forwarder arrêté"}

    def status(self):
        return {
            "running": self.running,
            "script": str(DNS_FORWARDER_SCRIPT),
            "listen": "10.0.0.1:53",
            "forward": "127.0.0.1:5300",
        }


def _kill_fwd():
    """Kill forwarder par PID file ou par port."""
    if FWD_PID_FILE.exists():
        try:
            pid = int(FWD_PID_FILE.read_text().strip())
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=3)
        except:
            pass
    # Fallback: kill python process that has the dns_forwarder script
    try:
        subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI",
                        f"WINDOWTITLE eq *dns_forwarder*"],
                       capture_output=True, timeout=3)
    except:
        pass


class VPNManager:
    """Gestion du tunnel WireGuard PixelOS."""

    def __init__(self):
        _ensure_dir()
        self.forwarder = VPNForwarder()

    @property
    def tunnel_installed(self):
        return _service_exists()

    @property
    def tunnel_running(self):
        if not self.tunnel_installed:
            return False
        return _check_service()

    @property
    def admin(self):
        return _is_admin()

    def _require_admin(self, msg="Action nécessite admin"):
        if not self.admin:
            return {"status": "elevate", "message": msg}
        return None

    def _tunnel_path(self):
        path = CONFIG_DIR / f"{TUNNEL_NAME}.conf"
        if path.exists():
            return path
        return WIREGUARD_DIR / f"{TUNNEL_NAME}.conf"

    def status(self, full=False):
        """État complet du VPN."""
        st = {
            "tunnel": {"name": TUNNEL_NAME, "port": 51820, "server_ip": "10.0.0.1"},
            "tunnel_installed": self.tunnel_installed,
            "tunnel_running": self.tunnel_running,
            "forwarder": self.forwarder.status(),
            "config_dir": str(WIREGUARD_DIR),
            "admin": self.admin,
        }

        if self.tunnel_running:
            r = _run_wg("show", TUNNEL_NAME)
            if r.returncode == 0:
                st["tunnel"]["wg_show"] = r.stdout

        client_configs = list(WIREGUARD_DIR.glob("client*.conf"))
        st["client_configs"] = len(client_configs)
        st["clients"] = []
        for cc in client_configs:
            st["clients"].append({"file": cc.name, "path": str(cc)})

        key_path = WIREGUARD_DIR / "server.pub"
        if key_path.exists():
            st["server_public_key"] = key_path.read_text(encoding="ascii").strip()

        if full:
            st["config"] = self._read_config()

        return st

    def _read_config(self):
        path = self._tunnel_path()
        if path.exists():
            return path.read_text()
        return ""

    def install_tunnel(self):
        """Installe le tunnel WireGuard comme service Windows."""
        req = self._require_admin("Installation du tunnel admin requis")
        if req:
            return req
        path = self._tunnel_path()
        if not path.exists():
            return {"status": "error", "message": "Config tunnel introuvable"}
        if self.tunnel_installed:
            return {"status": "ok", "message": "Déjà installé"}
        r = subprocess.run(
            [WG_UI, "/installtunnelservice", str(path)],
            capture_output=True, text=True,
        )
        if r.returncode == 0 or self.tunnel_installed:
            return {"status": "ok", "message": "Tunnel installé"}
        return {"status": "error", "message": r.stderr or r.stdout or "Échec installation"}

    def uninstall_tunnel(self):
        """Désinstalle le tunnel."""
        req = self._require_admin("Désinstallation tunnel admin requis")
        if req:
            return req
        if not self.tunnel_installed:
            return {"status": "ok", "message": "Pas installé"}
        r = subprocess.run(
            [WG_UI, "/uninstalltunnelservice", TUNNEL_NAME],
            capture_output=True, text=True,
        )
        return {"status": "ok" if r.returncode == 0 else "error",
                "message": r.stderr or r.stdout or "Désinstallé"}

    def start(self):
        """Démarre tunnel + forwarder."""
        results = {}

        if not self.tunnel_installed:
            inst = self.install_tunnel()
            results["tunnel_install"] = inst
            if inst.get("status") == "elevate":
                return results
        if self.tunnel_running:
            results["tunnel"] = {"status": "ok", "message": "Déjà en cours"}
        else:
            r = subprocess.run(["net", "start", SERVICE_NAME], capture_output=True, text=True)
            if r.returncode != 0:
                # Try with admin
                if not self.admin:
                    return {"status": "elevate", "message": "Démarrage tunnel admin requis"}
            results["tunnel"] = {"status": "ok" if r.returncode == 0 else "error",
                                  "message": r.stderr or "Démarré"}

        results["forwarder"] = self.forwarder.start()
        return results

    def stop(self):
        """Arrête tunnel + forwarder."""
        results = {}
        results["forwarder"] = self.forwarder.stop()
        if self.tunnel_running:
            r = subprocess.run(["net", "stop", SERVICE_NAME], capture_output=True, text=True)
            if r.returncode != 0 and self.admin:
                pass  # already stopped or error
            results["tunnel"] = {"status": "ok" if r.returncode == 0 else "error",
                                  "message": r.stderr or "Arrêté"}
        else:
            results["tunnel"] = {"status": "ok", "message": "Pas en cours"}
        return results

    def restart(self):
        self.stop()
        time.sleep(1)
        return self.start()

    def start_all(self):
        """Démarre tunnel → forwarder → DNS (ordre strict pour le bind 10.0.0.1:53)."""
        results = {}

        # 1. Tunnel seul (sans forwarder ni DNS)
        if not self.tunnel_installed:
            inst = self.install_tunnel()
            results["tunnel_install"] = inst
            if inst.get("status") == "elevate":
                return results
        if not self.tunnel_running:
            r = subprocess.run(["net", "start", SERVICE_NAME], capture_output=True, text=True)
            results["tunnel"] = {"status": "ok" if r.returncode == 0 else "error",
                                 "message": r.stderr or "Démarré"}
            time.sleep(2)  # attendre l'interface 10.0.0.1
        else:
            results["tunnel"] = {"status": "ok", "message": "Déjà en cours"}

        # 2. Forwarder DNS (bind 10.0.0.1:53 → 127.0.0.1:5300)
        results["forwarder"] = self.forwarder.start()

        # 3. DNS PixelOS (serveur .pxl sur port 5300)
        try:
            from core.dns import PixelDNSServer
            from core.config import PixelOSConfig
            cfg = PixelOSConfig()
            dns_cfg = cfg.get("dns", {})
            self._dns_server = PixelDNSServer(dns_cfg)
            self._dns_server.start()
            results["dns"] = {"status": "ok", "message": f"DNS démarré port {self._dns_server.port} tld=.{self._dns_server.tld}"}
        except Exception as e:
            results["dns"] = {"status": "error", "message": str(e)}

        return results

    def stop_all(self):
        """Arrête tout."""
        results = {}
        results["forwarder"] = self.forwarder.stop()
        results["tunnel"] = self.stop().get("tunnel", {"status": "ok", "message": "Arrêté"})
        if hasattr(self, "_dns_server") and self._dns_server:
            try:
                self._dns_server.stop()
                results["dns"] = {"status": "ok", "message": "DNS arrêté"}
            except:
                pass
        return results

    def gen_client_config(self, client_name="client", public_key=None,
                          server_endpoint="196.179.160.78:51820"):
        """Génère une config client pour accès distant."""
        server_pub = (WIREGUARD_DIR / "server.pub").read_text(encoding="ascii").strip()

        if not public_key:
            r = _run_wg("genkey")
            if r.returncode != 0:
                return {"status": "error", "message": "Échec génération clé"}
            client_priv = r.stdout.strip()
            r = subprocess.run([WG_EXE, "pubkey"], input=client_priv, capture_output=True, text=True)
            client_pub = r.stdout.strip()
        else:
            client_priv = None
            client_pub = public_key

        client_num = 2
        existing = list(WIREGUARD_DIR.glob("client*.conf"))
        for f in existing:
            try:
                n = int(f.stem.replace("client", ""))
                client_num = max(client_num, n + 1)
            except:
                pass

        client_ip = f"10.0.0.{client_num}"

        client_conf = (
            f"[Interface]\n"
            f"PrivateKey = {client_priv or '<PRIVATE_KEY>'}\n"
            f"Address = {client_ip}/24\n"
            f"DNS = 10.0.0.1\n"
            f"\n"
            f"[Peer]\n"
            f"PublicKey = {server_pub}\n"
            f"AllowedIPs = 10.0.0.0/24, 192.168.0.0/24\n"
            f"Endpoint = {server_endpoint}\n"
            f"PersistentKeepalive = 25\n"
        )

        config_path = WIREGUARD_DIR / f"{client_name}{client_num}.conf"
        config_path.write_text(client_conf)

        server_config_path = self._tunnel_path()
        if server_config_path.exists():
            server_conf = server_config_path.read_text(encoding="ascii")
            peer_block = (
                f"\n[Peer]\n"
                f"PublicKey = {client_pub}\n"
                f"AllowedIPs = {client_ip}/32\n"
            )
            if client_pub not in server_conf:
                server_conf += peer_block
                server_config_path.write_text(server_conf, encoding="ascii")
                if self.tunnel_running:
                    _run_wg("set", TUNNEL_NAME, "peer", client_pub,
                            "allowed-ips", f"{client_ip}/32")

        return {
            "status": "ok",
            "client_name": f"{client_name}{client_num}",
            "client_ip": client_ip,
            "config_file": str(config_path),
            "public_key": client_pub,
            "private_key": client_priv,
            "config": client_conf,
        }

    def list_clients(self):
        clients = []
        for f in sorted(WIREGUARD_DIR.glob("client*.conf")):
            content = f.read_text()
            ip = ""
            for line in content.splitlines():
                if line.startswith("Address"):
                    ip = line.split("=")[-1].strip().split("/")[0]
            clients.append({"file": f.name, "ip": ip})
        return clients


vpn_manager = VPNManager()
