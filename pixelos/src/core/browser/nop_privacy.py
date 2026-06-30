# Pixel Software Design — Copyright 2026
import os
import subprocess
from pathlib import Path


AD_BLOCKLIST_URL = "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"
TRACKER_BLOCKLIST_URL = "https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/fakenews-gambling-porn/hosts"

AD_LIST = "/var/db/pixelos/nop_adblock.txt"
TRACKER_LIST = "/var/db/pixelos/nop_trackerblock.txt"

DEFAULT_ADS = [
    "doubleclick.net", "googlesyndication.com", "googleadservices.com",
    "google-analytics.com", "googletagmanager.com", "facebook.com/tr",
    "ads.", "adservice.", "adserver.", "adzerk.net", "scorecardresearch.com",
    "quantserve.com", "outbrain.com", "taboola.com", "criteo.com",
    "amazon-adsystem.com", "casalemedia.com", "adsrvr.org", "pubmatic.com",
    "rubiconproject.com", "openx.net", "appnexus.com", "sharethis.com",
    "addthis.com", "exelator.com", "bluekai.com", "demdex.net",
]

DEFAULT_TRACKERS = [
    "facebook.com/tr", "pixel.", "analytics.", "track.",
    "metrics.", "collect.", "beacon.", "gtag.",
    "hotjar.com", "mouseflow.com", "fullstory.com",
    "crazyegg.com", "luckyorange.com", "clicky.com",
    "mixpanel.com", "amplitude.com", "segment.io",
    "heap.io", "intercom.io", "drift.com",
    "hubspot.com", "marketo.net", "pardot.com",
]


class NOPPrivacy:
    def __init__(self):
        self.blocked_domains = set()
        self.blocked_count = 0
        self._load_lists()

    def _path(self, p):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
        return p

    def _load_lists(self):
        self.ad_domains = set(DEFAULT_ADS)
        self.tracker_domains = set(DEFAULT_TRACKERS)

        if os.path.exists(AD_LIST):
            try:
                with open(AD_LIST) as f:
                    for line in f:
                        if line.strip() and not line.startswith("#"):
                            parts = line.split()
                            if len(parts) >= 2:
                                self.ad_domains.add(parts[-1].strip())
            except Exception:
                pass

        if os.path.exists(TRACKER_LIST):
            try:
                with open(TRACKER_LIST) as f:
                    for line in f:
                        if line.strip() and not line.startswith("#"):
                            parts = line.split()
                            if len(parts) >= 2:
                                self.tracker_domains.add(parts[-1].strip())
            except Exception:
                pass

        self.blocked_domains = self.ad_domains | self.tracker_domains

    def update_lists(self):
        try:
            import urllib.request
            req = urllib.request.Request(AD_BLOCKLIST_URL,
                headers={"User-Agent": "PixelOS-NOP/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode()
                with open(self._path(AD_LIST), "w") as f:
                    f.write(content)
        except Exception:
            pass

        try:
            req = urllib.request.Request(TRACKER_BLOCKLIST_URL,
                headers={"User-Agent": "PixelOS-NOP/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode()
                with open(self._path(TRACKER_LIST), "w") as f:
                    f.write(content)
        except Exception:
            pass

        self._load_lists()
        return {"ads": len(self.ad_domains), "trackers": len(self.tracker_domains)}

    def is_blocked(self, url):
        for domain in self.blocked_domains:
            if domain in url:
                return True, domain
        return False, None

    def check_url(self, url):
        blocked, rule = self.is_blocked(url)
        if blocked:
            self.blocked_count += 1
            return {"blocked": True, "rule": rule}
        return {"blocked": False}

    def apply_blocks(self, ads=True, trackers=True):
        try:
            pf_table = "nop_blocklist"
            domains_to_block = set()
            if ads:
                domains_to_block |= self.ad_domains
            if trackers:
                domains_to_block |= self.tracker_domains

            unbound_conf = "/var/unbound/etc/unbound.conf"
            if os.path.exists(os.path.dirname(unbound_conf)):
                with open(unbound_conf + ".nop", "w") as f:
                    f.write("server:\n")
                    for domain in list(domains_to_block)[:5000]:
                        f.write(f"  local-zone: \"{domain}\" redirect\n")
                        f.write(f"  local-data: \"{domain} A 127.0.0.1\"\n")

            pf_conf_addon = f"/etc/pf.nop.conf"
            if os.path.exists(os.path.dirname(pf_conf_addon)):
                with open(pf_conf_addon, "w") as f:
                    f.write(f"table <{pf_table}> persist\n")
                    for domain in list(domains_to_block)[:1000]:
                        f.write(f"table <{pf_table}> add {{ {domain} }}\n")

            return {
                "status": "applied",
                "ads_blocked": len(self.ad_domains) if ads else 0,
                "trackers_blocked": len(self.tracker_domains) if trackers else 0,
                "total": len(domains_to_block),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def stats(self):
        return {
            "ad_domains": len(self.ad_domains),
            "tracker_domains": len(self.tracker_domains),
            "total_blocked_domains": len(self.blocked_domains),
            "blocked_count": self.blocked_count,
            "ad_blocklist": sorted(list(self.ad_domains))[:30],
            "tracker_blocklist": sorted(list(self.tracker_domains))[:30],
        }
