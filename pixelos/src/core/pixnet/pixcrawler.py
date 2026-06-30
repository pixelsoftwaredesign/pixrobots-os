#!/usr/bin/env python3
"""
PixCrawler — Agent d'indexation décentralisé PixNet.

Parcourt les contenus IPFS, crée un index local index.json,
partage les découvertes avec les pairs du réseau PixNet.
Fonctionne en continu avec crawl incrémental.
"""

import os
import json
import time
import re
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from threading import Thread, Event
from typing import Optional


IPFS_GATEWAY = "http://127.0.0.1:8080"
IPFS_API = "http://127.0.0.1:5001"

INDEX_DIR = "/var/db/pixelos/pixnet"
INDEX_FILE = "index.json"
SEEN_FILE = "seen_cids.json"
CRAWL_LOG = "crawl_log.json"

DEFAULT_SEEDS = [
    "/ipns/en.wikipedia-on-ipfs.org",
    "/ipns/dist.ipfs.io",
    "/ipns/docs.ipfs.io",
    "/ipns/blog.ipfs.io",
    "/ipns/ipfs.io",
]

CONTENT_TYPES = {
    "text/html": "html",
    "text/plain": "text",
    "application/json": "json",
    "application/pdf": "pdf",
    "image/": "image",
    "video/": "video",
    "audio/": "audio",
}


class PixCrawler:
    def __init__(self):
        self.running = False
        self._stop = Event()
        self._thread: Optional[Thread] = None
        self._ensure_dirs()
        self._load_index()
        self._load_seen()
        self.crawl_count = 0
        self.peers_shared = 0

    # ── Persistence ──────────────────────────────────────

    def _ensure_dirs(self):
        Path(INDEX_DIR).mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        p = Path(INDEX_DIR) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)

    def _load_index(self):
        path = self._path(INDEX_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.index = json.load(f)
                return
            except Exception:
                pass
        self.index = []

    def _save_index(self):
        with open(self._path(INDEX_FILE), "w") as f:
            json.dump(self.index[-50000:], f, indent=2)

    def _load_seen(self):
        path = self._path(SEEN_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.seen_cids = set(json.load(f))
                return
            except Exception:
                pass
        self.seen_cids = set()

    def _save_seen(self):
        with open(self._path(SEEN_FILE), "w") as f:
            json.dump(sorted(self.seen_cids)[-100000:], f, indent=2)

    # ── IPFS helpers ──────────────────────────────────────

    def _ipfs_cat(self, cid: str) -> Optional[str]:
        try:
            url = f"{IPFS_GATEWAY}/ipfs/{cid}"
            req = urllib.request.Request(url,
                headers={"User-Agent": "PixCrawler/1.0 (PixelOS PixNet)"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                content_type = resp.headers.get("Content-Type", "")
                data = resp.read()
                return data.decode("utf-8", errors="replace"), content_type
        except Exception:
            return None, ""

    def _ipfs_ls(self, cid: str) -> list:
        try:
            url = f"{IPFS_API}/api/v0/ls?arg={cid}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                return data.get("Objects", [{}])[0].get("Links", [])
        except Exception:
            return []

    def _ipfs_pin(self, cid: str) -> bool:
        try:
            url = f"{IPFS_API}/api/v0/pin/add?arg={cid}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30):
                return True
        except Exception:
            return False

    # ── Content analysis ──────────────────────────────────

    def _extract_keywords(self, text: str, max_kw: int = 10) -> list:
        stopwords = {
            "le", "la", "les", "des", "de", "du", "et", "est", "un", "une",
            "dans", "pour", "sur", "que", "qui", "pas", "avec", "son", "sa",
            "ses", "ce", "cet", "cette", "ces", "the", "a", "an", "in",
            "on", "at", "to", "of", "and", "is", "it", "or", "by", "for",
            "with", "from", "as", "was", "are", "has", "been", "were",
        }
        words = re.findall(r"\b[a-zA-Z]\w+\b", text.lower())
        freq = {}
        for w in words:
            if w not in stopwords and len(w) > 3:
                freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: -x[1])
        return [w for w, _ in sorted_words[:max_kw]]

    def _detect_content_type(self, mime: str, url: str = "") -> str:
        for prefix, ctype in CONTENT_TYPES.items():
            if prefix in mime:
                return ctype
        ext = url.split(".")[-1].lower() if url else ""
        ext_map = {
            "html": "html", "htm": "html", "txt": "text",
            "json": "json", "pdf": "pdf", "md": "text",
            "jpg": "image", "jpeg": "image", "png": "image",
            "gif": "image", "svg": "image", "webp": "image",
            "mp4": "video", "webm": "video", "mp3": "audio",
            "wav": "audio", "ogg": "audio",
        }
        return ext_map.get(ext, "unknown")

    def _generate_summary(self, text: str, max_len: int = 200) -> str:
        clean = re.sub(r"\s+", " ", text[:2000]).strip()
        if len(clean) <= max_len:
            return clean
        sentences = re.split(r"(?<=[.!?])\s+", clean)
        summary = ""
        for s in sentences:
            if len(summary) + len(s) > max_len:
                break
            summary += s + " "
        return summary.strip()[:max_len]

    # ── Crawl logic ───────────────────────────────────────

    def crawl(self, cid: str, depth: int = 2) -> dict:
        if cid in self.seen_cids or depth < 0:
            return {"status": "skipped", "reason": "seen or max depth"}

        self.seen_cids.add(cid)
        self._save_seen()

        content, content_type = self._ipfs_cat(cid)
        if content is None:
            return {"status": "error", "reason": "unreachable", "cid": cid}

        ctype = self._detect_content_type(content_type, cid)

        keywords = self._extract_keywords(content)
        summary = self._generate_summary(content)
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        entry = {
            "cid": cid,
            "url": f"ipfs://{cid}",
            "content_type": ctype,
            "content_hash": content_hash,
            "keywords": keywords,
            "summary": summary,
            "title": keywords[0].title() if keywords else cid[:20],
            "crawled_at": datetime.now().isoformat(),
            "crawl_depth": depth,
        }

        self.index.append(entry)
        self.crawl_count += 1
        self._save_index()

        if depth > 0:
            links = self._ipfs_ls(cid)
            for link in links[:20]:
                child_cid = link.get("Hash", "")
                if child_cid and child_cid not in self.seen_cids:
                    self.crawl(child_cid, depth - 1)
                    self._ipfs_pin(child_cid)

        return {"status": "indexed", "entry": entry}

    def crawl_seeds(self, depth: int = 2):
        results = []
        for seed in DEFAULT_SEEDS:
            cid = seed.replace("/ipns/", "").replace("/ipfs/", "")
            r = self.crawl(cid, depth)
            results.append(r)
        return results

    # ── Continuous crawling ───────────────────────────────

    def start(self, interval: int = 3600, depth: int = 2):
        if self.running:
            return {"status": "already_running"}

        self.running = True
        self._stop.clear()

        def loop():
            self.crawl_seeds(depth)
            while not self._stop.is_set():
                self._stop.wait(interval)
                if self._stop.is_set():
                    break
                self.crawl_seeds(depth)

        self._thread = Thread(target=loop, daemon=True)
        self._thread.start()
        return {"status": "started", "interval": interval, "depth": depth}

    def stop(self):
        self.running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        return {"status": "stopped"}

    # ── Sharing with peers ────────────────────────────────

    def get_recent(self, limit: int = 100) -> list:
        return list(reversed(self.index[-limit:]))

    def get_by_keyword(self, keyword: str, limit: int = 50) -> list:
        kw = keyword.lower()
        results = []
        for entry in reversed(self.index):
            if any(kw in k.lower() for k in entry.get("keywords", [])):
                results.append(entry)
                if len(results) >= limit:
                    break
            elif kw in entry.get("summary", "").lower():
                results.append(entry)
                if len(results) >= limit:
                    break
        return results

    def get_by_type(self, content_type: str, limit: int = 50) -> list:
        return [e for e in reversed(self.index)
                if e.get("content_type") == content_type][:limit]

    def merge_peer_index(self, peer_entries: list) -> int:
        added = 0
        for entry in peer_entries:
            cid = entry.get("cid")
            if cid and cid not in self.seen_cids:
                self.seen_cids.add(cid)
                entry["source"] = "peer"
                self.index.append(entry)
                added += 1
        self._save_index()
        self._save_seen()
        self.peers_shared += added
        return added

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> dict:
        types = {}
        for e in self.index:
            ct = e.get("content_type", "unknown")
            types[ct] = types.get(ct, 0) + 1

        return {
            "total_indexed": len(self.index),
            "total_seen": len(self.seen_cids),
            "crawl_count": self.crawl_count,
            "peers_shared": self.peers_shared,
            "running": self.running,
            "content_types": types,
            "recent": self.get_recent(5),
        }

    def clear_index(self):
        self.index = []
        self.seen_cids = set()
        self._save_index()
        self._save_seen()
        return {"status": "cleared"}
