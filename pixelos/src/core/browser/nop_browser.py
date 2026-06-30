# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
import os
import subprocess
import json
import re
from datetime import datetime
from pathlib import Path
from .nop_resolver import NOPResolver
from .nop_privacy import NOPPrivacy
from .nop_wallet_bridge import NOPWalletBridge


HISTORY_FILE = "/var/db/pixelos/nop_history.json"
BOOKMARKS_FILE = "/var/db/pixelos/nop_bookmarks.json"
SETTINGS_FILE = "/var/db/pixelos/nop_settings.json"

DEFAULT_SETTINGS = {
    "homepage": "https://opencode.ai",
    "search_engine": "https://duckduckgo.com/?q=",
    "block_ads": True,
    "block_trackers": True,
    "disable_scripts": False,
    "web3_resolver": True,
    "wallet_integration": True,
    "privacy_mode": False,
    "max_tabs": 10,
    "user_agent": "Mozilla/5.0 (X11; OpenBSD amd64) PixelOS-NOP/1.0",
}


class NOPBrowser:
    def __init__(self):
        self.resolver = NOPResolver()
        self.privacy = NOPPrivacy()
        self.wallet = NOPWalletBridge()
        self._load_settings()
        self._load_history()
        self._load_bookmarks()
        self.tabs = []

    # ── Settings ─────────────────────────────────────────

    def _path(self, p):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
        return p

    def _load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE) as f:
                    self.settings = {**DEFAULT_SETTINGS, **json.load(f)}
                return
            except Exception:
                pass
        self.settings = dict(DEFAULT_SETTINGS)
        self._save_settings()

    def _save_settings(self):
        with open(self._path(SETTINGS_FILE), "w") as f:
            json.dump(self.settings, f, indent=2)

    def get_settings(self):
        return self.settings

    def update_settings(self, updates):
        self.settings.update(updates)
        self._save_settings()
        if "block_ads" in updates or "block_trackers" in updates:
            if self.settings["block_ads"] or self.settings["block_trackers"]:
                self.privacy.apply_blocks(
                    ads=self.settings["block_ads"],
                    trackers=self.settings["block_trackers"]
                )
        return {"status": "ok", "settings": self.settings}

    # ── History ──────────────────────────────────────────

    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE) as f:
                    self.history = json.load(f)
                return
            except Exception:
                pass
        self.history = []

    def _save_history(self):
        with open(self._path(HISTORY_FILE), "w") as f:
            json.dump(self.history[-1000:], f, indent=2)

    def add_history(self, url, title=""):
        entry = {
            "url": url, "title": title,
            "timestamp": datetime.now().isoformat(),
        }
        self.history.append(entry)
        self._save_history()
        return entry

    def get_history(self, limit=100, search=None):
        entries = list(reversed(self.history))
        if search:
            entries = [e for e in entries
                       if search.lower() in e["url"].lower()
                       or search.lower() in e["title"].lower()]
        return entries[:limit]

    def clear_history(self):
        self.history = []
        self._save_history()
        return {"status": "cleared"}

    # ── Bookmarks ────────────────────────────────────────

    def _load_bookmarks(self):
        if os.path.exists(BOOKMARKS_FILE):
            try:
                with open(BOOKMARKS_FILE) as f:
                    self.bookmarks = json.load(f)
                return
            except Exception:
                pass
        self.bookmarks = []

    def _save_bookmarks(self):
        with open(self._path(BOOKMARKS_FILE), "w") as f:
            json.dump(self.bookmarks, f, indent=2)

    def get_bookmarks(self):
        return self.bookmarks

    def add_bookmark(self, url, title="", tags=None):
        bm = {
            "url": url, "title": title or url,
            "tags": tags or [],
            "added_at": datetime.now().isoformat(),
        }
        self.bookmarks.append(bm)
        self._save_bookmarks()
        return {"status": "added", "bookmark": bm}

    def remove_bookmark(self, url):
        self.bookmarks = [b for b in self.bookmarks if b["url"] != url]
        self._save_bookmarks()
        return {"status": "removed"}

    # ── URL resolution ───────────────────────────────────

    def resolve_url(self, url):
        if not url or url.strip() == "":
            return {"url": self.settings["homepage"], "type": "homepage"}

        url = url.strip()

        r = self.resolver.resolve(url)
        if r.get("web3_type") != "standard":
            return {
                "original": url,
                "resolved": r.get("resolved_url", url),
                "type": r.get("type", "web3"),
                "web3_type": r.get("web3_type", "standard"),
                "resolver_info": r,
            }

        if not url.startswith("http://") and not url.startswith("https://"):
            if "." in url:
                url = "https://" + url
            else:
                url = self.settings["search_engine"] + url

        return {
            "original": url,
            "resolved": url,
            "type": "web",
            "web3_type": "standard",
        }

    def navigate(self, url):
        resolved = self.resolve_url(url)
        tab_id = len(self.tabs) + 1
        tab = {
            "id": tab_id,
            "url": resolved["resolved"],
            "original": resolved.get("original", url),
            "type": resolved["type"],
            "web3_type": resolved["web3_type"],
            "created_at": datetime.now().isoformat(),
        }
        self.tabs.append(tab)
        self.add_history(resolved["resolved"], title=url)
        return {"tab": tab, "resolution": resolved}

    # ── Render (proxy / iframe) ──────────────────────────

    def get_render_url(self, target_url, mode="proxy"):
        resolved = self.resolve_url(target_url)
        final_url = resolved["resolved"]

        if mode == "direct":
            return {"url": final_url, "mode": "direct"}

        if mode == "proxy":
            proxy_url = f"/api/browser/proxy?url={final_url}"
            if self.settings.get("disable_scripts"):
                proxy_url += "&noscript=1"
            return {"url": proxy_url, "mode": "proxy"}

        return {"url": final_url, "mode": "direct"}

    def proxy_fetch(self, url):
        try:
            import urllib.request
            headers = {"User-Agent": self.settings["user_agent"]}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read()
                content_type = resp.headers.get("Content-Type", "text/html")

            if self.settings.get("disable_scripts"):
                decoded = content.decode("utf-8", errors="replace")
                decoded = re.sub(r'<script[^>]*>.*?</script>', '', decoded, flags=re.DOTALL)
                decoded = re.sub(r'\bon\w+\s*=\s*"[^"]*"', '', decoded)
                decoded = re.sub(r'\bon\w+\s*=\s*\'[^\']*\'', '', decoded)
                content = decoded.encode("utf-8")

            return {
                "status": "ok",
                "content": content,
                "content_type": content_type,
                "url": url,
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "url": url}

    # ── Wallet integration ───────────────────────────────

    def check_wallet(self, url):
        return self.wallet.check_site_for_payment(url)

    def sign_tx(self, tx_data):
        return self.wallet.sign_transaction(tx_data)

    # ── Ad blocking stats ────────────────────────────────

    def privacy_stats(self):
        return self.privacy.stats()

    def update_blocklists(self):
        self.privacy.update_lists()
        if self.settings.get("block_ads") or self.settings.get("block_trackers"):
            self.privacy.apply_blocks(
                ads=self.settings["block_ads"],
                trackers=self.settings["block_trackers"]
            )
        return {"status": "updated"}

    # ── Tabs ─────────────────────────────────────────────

    def list_tabs(self):
        return self.tabs

    def close_tab(self, tab_id):
        self.tabs = [t for t in self.tabs if t["id"] != tab_id]
        return {"status": "closed"}

    # ── Stats ────────────────────────────────────────────

    def stats(self):
        return {
            "tabs_open": len(self.tabs),
            "history_size": len(self.history),
            "bookmarks": len(self.bookmarks),
            "settings": self.settings,
            "wallet_available": self.wallet.is_available(),
            "ad_blocking": self.settings.get("block_ads", False),
            "tracker_blocking": self.settings.get("block_trackers", False),
            "web3_resolver": self.settings.get("web3_resolver", True),
            "privacy_mode": self.settings.get("privacy_mode", False),
        }
