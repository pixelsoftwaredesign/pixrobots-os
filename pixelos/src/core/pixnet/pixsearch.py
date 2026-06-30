# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
#!/usr/bin/env python3
"""
PixSearch — Moteur de recherche décentralisé PixNet.

Requêtes P2P vers les voisins, filtrage par IA de confiance,
classement par pertinence + réputation. Complètement hors-ligne,
sans annonceur, sans tracking.
"""

import os
import json
import re
import time
import math
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Optional
from threading import Lock
from .pixcrawler import PixCrawler
from .pixtrust import PixTrust
from .pixmesh import PixMesh


SEARCH_DIR = "/var/db/pixelos/pixnet"
CACHE_FILE = "search_cache.json"
QUERY_LOG = "query_log.json"

DEFAULT_PEER_TIMEOUT = 30


class PixSearch:
    def __init__(self, crawler: Optional[PixCrawler] = None,
                 trust: Optional[PixTrust] = None,
                 mesh: Optional[PixMesh] = None):
        self.crawler = crawler or PixCrawler()
        self.trust = trust or PixTrust()
        self.mesh = mesh or PixMesh()
        self._lock = Lock()
        self._ensure_dirs()
        self._load_cache()
        self._load_query_log()
        self.query_count = 0

    # ── Persistence ──────────────────────────────────────

    def _ensure_dirs(self):
        Path(SEARCH_DIR).mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        p = Path(SEARCH_DIR) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)

    def _load_cache(self):
        path = self._path(CACHE_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.cache = json.load(f)
                return
            except Exception:
                pass
        self.cache = {}

    def _save_cache(self):
        with open(self._path(CACHE_FILE), "w") as f:
            json.dump(self.cache, f, indent=2)

    def _load_query_log(self):
        path = self._path(QUERY_LOG)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.query_log = json.load(f)
                return
            except Exception:
                pass
        self.query_log = []

    def _save_query_log(self):
        with open(self._path(QUERY_LOG), "w") as f:
            json.dump(self.query_log[-1000:], f, indent=2)

    # ── TF-IDF ranking ────────────────────────────────────

    def _tokenize(self, text: str) -> list:
        return re.findall(r"\b\w{3,}\b", text.lower())

    def _compute_tf(self, tokens: list) -> dict:
        tf = defaultdict(float)
        for t in tokens:
            tf[t] += 1.0
        total = len(tokens)
        if total > 0:
            for t in tf:
                tf[t] /= total
        return dict(tf)

    def _compute_idf(self, docs: list) -> dict:
        idf = defaultdict(float)
        n = len(docs)
        for doc in docs:
            tokens = set(self._tokenize(doc.get("summary", "") + " " +
                                        " ".join(doc.get("keywords", []))))
            for t in tokens:
                idf[t] += 1.0
        for t in idf:
            idf[t] = math.log((n + 1) / (idf[t] + 1)) + 1
        return dict(idf)

    def _cosine_similarity(self, query_vec: dict, doc_vec: dict) -> float:
        dot = 0.0
        norm_q = 0.0
        norm_d = 0.0
        for term, weight in query_vec.items():
            norm_q += weight ** 2
            dw = doc_vec.get(term, 0.0)
            dot += weight * dw
            norm_d += dw ** 2
        for term, weight in doc_vec.items():
            if term not in query_vec:
                norm_d += weight ** 2
        if norm_q == 0 or norm_d == 0:
            return 0.0
        return dot / (math.sqrt(norm_q) * math.sqrt(norm_d))

    # ── Local search ──────────────────────────────────────

    def search_local(self, query: str, limit: int = 30) -> list:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        docs = self.crawler.get_recent(2000)
        idf = self._compute_idf(docs)
        query_vec = {}
        qt = self._compute_tf(query_tokens)
        for term, tf in qt.items():
            query_vec[term] = tf * idf.get(term, 1.0)

        scored = []
        for doc in docs:
            doc_text = doc.get("summary", "") + " " + " ".join(doc.get("keywords", []))
            doc_tokens = self._tokenize(doc_text)
            doc_tf = self._compute_tf(doc_tokens)
            doc_vec = {}
            for term, tf in doc_tf.items():
                doc_vec[term] = tf * idf.get(term, 1.0)

            relevance = self._cosine_similarity(query_vec, doc_vec)
            if relevance > 0.01:
                trust_score = self.trust.score_content(doc)
                combined = relevance * 0.6 + trust_score * 0.4
                scored.append((combined, doc))

        scored.sort(key=lambda x: -x[0])
        return [
            {**doc, "score": round(score, 4), "relevance": round(score * 0.6 / 0.6 if score > 0 else 0, 4),
             "trust_score": round(self.trust.score_content(doc), 4)}
            for score, doc in scored[:limit]
        ]

    # ── P2P search ────────────────────────────────────────

    def search_peers(self, query: str, timeout: int = DEFAULT_PEER_TIMEOUT) -> list:
        peer_results = []
        peers = self.mesh.get_connected_peers()

        for peer in peers[:10]:
            try:
                peer_url = peer.get("api_url", "")
                if not peer_url:
                    continue
                url = f"{peer_url}/api/pixnet/search?q={urllib.parse.quote(query)}&limit=10"
                req = urllib.request.Request(url,
                    headers={"User-Agent": "PixSearch/1.0 (PixelOS PixNet)"})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read())
                    for result in data.get("results", []):
                        result["source_peer"] = peer.get("node_id", "unknown")
                        result["source_type"] = "peer"
                        peer_results.append(result)
            except Exception:
                pass

        peer_results.sort(key=lambda x: -x.get("score", 0))
        return peer_results

    # ── Search orchestrator ───────────────────────────────

    def search(self, query: str, limit: int = 30, include_peers: bool = True) -> dict:
        cache_key = query.lower().strip()
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached.get("ts", 0) < 300:
                return {**cached, "cached": True}

        local_results = self.search_local(query, limit)

        peer_results = []
        if include_peers:
            peer_results = self.search_peers(query)

        all_results = local_results + peer_results
        all_results.sort(key=lambda x: -x.get("score", 0))

        unique = {}
        for r in all_results:
            cid = r.get("cid", "")
            if cid and cid not in unique:
                unique[cid] = r
        results = list(unique.values())[:limit]

        self.query_count += 1
        self.query_log.append({
            "query": query, "results": len(results),
            "local": len(local_results), "peer": len(peer_results),
            "ts": datetime.now().isoformat(),
        })
        self._save_query_log()

        response = {
            "query": query,
            "results": results,
            "total_local": len(local_results),
            "total_peer": len(peer_results),
            "total_unique": len(results),
            "ts": datetime.now().isoformat(),
        }

        self.cache[cache_key] = response
        self._save_cache()
        return response

    # ── Aggregation ───────────────────────────────────────

    def aggregate(self, peer_responses: list) -> list:
        merged = {}
        for resp in peer_responses:
            for result in resp.get("results", []):
                cid = result.get("cid", "")
                if cid and cid not in merged:
                    merged[cid] = result
                elif cid:
                    merged[cid]["score"] = max(
                        merged[cid].get("score", 0),
                        result.get("score", 0)
                    )
        return sorted(merged.values(), key=lambda x: -x.get("score", 0))

    # ── Trending ──────────────────────────────────────────

    def trending(self, limit: int = 20) -> list:
        kw_freq = defaultdict(int)
        for entry in self.crawler.get_recent(500):
            for kw in entry.get("keywords", []):
                kw_freq[kw] += 1
        top_kw = sorted(kw_freq.items(), key=lambda x: -x[1])[:limit]
        return [{"keyword": kw, "count": count} for kw, count in top_kw]

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "queries_total": self.query_count,
            "queries_logged": len(self.query_log),
            "cache_size": len(self.cache),
            "local_index_size": len(self.crawler.index),
            "peers_available": len(self.mesh.get_connected_peers()),
            "trending": self.trending(10),
        }

    def clear_cache(self):
        self.cache = {}
        self._save_cache()
        return {"status": "cleared"}

    def clear_query_log(self):
        self.query_log = []
        self._save_query_log()
        return {"status": "cleared"}
