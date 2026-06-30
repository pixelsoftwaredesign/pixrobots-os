# Pixel OS ó Copyright 2026
# Free License ó Verifiable and Reliable for Internet Users
# Pixel Software Design ó Copyright 2026
import re
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse


IPFS_GATEWAY = "http://127.0.0.1:8080"
PIXEL_DNS_PORT = 5300

ENS_RPC = "https://rpc.gnosischain.com"
PIXEL_ZONE = "pixel.zone"


class NOPResolver:
    def __init__(self):
        self.cache = {}
        self.cache_file = "/var/db/pixelos/nop_resolver_cache.json"
        self._load_cache()

        self.WEB3_DOMAINS = {
            ".pixelos": self._resolve_pixelos,
            ".pixel": self._resolve_pixel,
            ".pxl": self._resolve_pixel,
            ".ipfs": self._resolve_ipfs,
            ".bit": self._resolve_bit,
            ".crypto": self._resolve_ens,
            ".dao": self._resolve_ens,
            ".nft": self._resolve_ens,
            ".wallet": self._resolve_ens,
            ".defi": self._resolve_ens,
            ".blockchain": self._resolve_ens,
            ".eth": self._resolve_ens,
        }

    def _path(self, p):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
        return p

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file) as f:
                    self.cache = json.load(f)
            except Exception:
                self.cache = {}
        else:
            self.cache = {}

    def _save_cache(self):
        with open(self._path(self.cache_file), "w") as f:
            json.dump(self.cache, f, indent=2)

    def resolve(self, url):
        parsed = urlparse(url if "://" in url else "https://" + url)
        domain = parsed.netloc or parsed.path

        if domain in self.cache:
            cached = self.cache[domain]
            return {**cached, "cached": True}

        sorted_exts = sorted(self.WEB3_DOMAINS.keys(), key=len, reverse=True)
        for ext in sorted_exts:
            if domain.endswith(ext) or "." + domain.split(".")[-1] == ext:
                resolver = self.WEB3_DOMAINS[ext]
                result = resolver(url)
                if result:
                    self.cache[domain] = result
                    self._save_cache()
                    return {**result, "cached": False}

        return {
            "resolved_url": url,
            "type": "standard",
            "web3_type": "standard",
            "cached": False,
        }

    def _resolve_ens(self, url):
        try:
            import json as j
            import urllib.request

            name = url.replace(".eth", "").replace(".crypto", "").replace(".dao", "")
            name = name.replace(".nft", "").replace(".wallet", "").replace(".defi", "")
            name = name.replace(".blockchain", "")
            name = name.split("/")[-1].split(":")[-1].strip()

            body = j.dumps({
                "jsonrpc": "2.0", "method": "eth_call",
                "params": [{
                    "to": "0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e",
                    "data": "0x" + "691f3431" + name.encode().hex().ljust(64, "0")
                }, "latest"],
                "id": 1,
            }).encode()

            try:
                req = urllib.request.Request(
                    ENS_RPC, data=body,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = j.loads(resp.read())
                    addr = data.get("result", "0x")
                    if addr and addr != "0x" * 32 + "00":
                        return {
                            "resolved_url": f"https://{name}.limo",
                            "type": "web3",
                            "web3_type": "ens",
                            "address": addr,
                            "name": name,
                        }
            except Exception:
                pass

            return {
                "resolved_url": f"https://{name}.limo",
                "type": "web3",
                "web3_type": "ens",
                "name": name,
                "note": "r√©solution ENS via passerelle .limo",
            }
        except Exception:
            return {"resolved_url": url, "type": "web3", "web3_type": "ens"}

    def _resolve_pixel(self, url):
        name = url.replace(".pixel", "").replace(".pxl", "")
        name = name.split("/")[-1].split(":")[-1].strip()

        try:
            r = subprocess.run(
                ["dig", f"@{PIXEL_DNS_PORT}", name + ".pixel", "+short"],
                capture_output=True, text=True, timeout=5
            )
            ip = r.stdout.strip()
            if ip and re.match(r"^\d+\.\d+\.\d+\.\d+$", ip):
                return {
                    "resolved_url": f"https://{ip}",
                    "type": "web3",
                    "web3_type": "pixel",
                    "ip": ip,
                    "name": name,
                }
        except Exception:
            pass

        return {
            "resolved_url": f"http://hub.{PIXEL_ZONE}/{name}",
            "type": "web3",
            "web3_type": "pixel",
            "name": name,
            "note": "r√©solution .pixel via hub.pixel.zone",
        }

    def _resolve_ipfs(self, url):
        cid = url.replace("ipfs://", "").replace("/ipfs/", "")
        cid = cid.split("/")[0] if "/" in cid else cid

        return {
            "resolved_url": f"{IPFS_GATEWAY}/ipfs/{cid}",
            "type": "web3",
            "web3_type": "ipfs",
            "cid": cid,
            "gateway": IPFS_GATEWAY,
        }

    def _resolve_bit(self, url):
        name = url.replace(".bit", "").split("/")[-1]
        return {
            "resolved_url": f"https://{name}.bit.hns.to",
            "type": "web3",
            "web3_type": "bit",
            "name": name,
        }

    def _resolve_pixelos(self, url):
        name = url.replace(".pixelos", "").split("/")[-1]
        return {
            "resolved_url": f"https://{name}.pixelos.org",
            "type": "web3",
            "web3_type": "pixelos",
            "name": name,
        }

    def supported_domains(self):
        return list(self.WEB3_DOMAINS.keys())

    def clear_cache(self):
        self.cache = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        return {"status": "cleared"}

    def stats(self):
        return {
            "supported_extensions": self.supported_domains(),
            "cache_size": len(self.cache),
            "cache_entries": list(self.cache.keys())[-20:],
        }
