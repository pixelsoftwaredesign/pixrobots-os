#!/usr/bin/env python3
"""
PixTrust — Système de réputation et de confiance PixNet.

Chaque nœud PixelOS possède une réputation calculée à partir de :
  - Son âge sur le réseau (durée de présence)
  - Son niveau de certification (0=inconnu → 3=association)
  - Les cautions (vouches) des pairs certifiés
  - La qualité de ses contenus indexés (analyse IA ou heuristique)

Intègre un modèle IA local (Ollama / Llama 3 / Mistral) pour :
  - Noter la fiabilité d'un document
  - Vérifier la cohérence scientifique
  - Détecter le contenu publicitaire ou trompeur
"""

import os
import json
import time
import re
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from threading import Lock
from typing import Optional


TRUST_DIR = "/var/db/pixelos/pixnet"
REPUTATION_FILE = "reputation.json"
VOUCHES_FILE = "vouches.json"
CERTIFICATIONS_FILE = "certifications.json"

OLLAMA_API = "http://127.0.0.1:11434"
OLLAMA_MODEL = "llama3.2:1b"

CERTIFICATION_LEVELS = {
    0: "inconnu",
    1: "membre",
    2: "agriculteur_certifie",
    3: "association",
}

BOOST_BY_LEVEL = {0: 0.3, 1: 0.6, 2: 0.85, 3: 1.0}

AD_KEYWORDS = [
    "publicite", "sponsorise", "promotion", "offre limitee",
    "achetez maintenant", "cliquez ici", "profit", "binaire",
    "investissement garanti", "argent facile", "revenu passif",
    "advertisement", "sponsored", "buy now", "click here",
    "limited offer", "free money", "guaranteed returns",
]

FAKE_NEWS_PATTERNS = [
    r"\b(ils cachent|ils ne veulent pas que vous sachiez|revele|choquant)\b",
    r"\b(100%|garanti|miracle|cure secrete)\b",
    r"\b(breaking.*exclusive|vous ne croirez pas|va vous choquer)\b",
]


class PixTrust:
    def __init__(self):
        self._lock = Lock()
        self._ensure_dirs()
        self._load_reputation()
        self._load_vouches()
        self._load_certifications()
        self.ai_available = self._check_ollama()

    # ── Persistence ──────────────────────────────────────

    def _ensure_dirs(self):
        Path(TRUST_DIR).mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        p = Path(TRUST_DIR) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)

    def _load_reputation(self):
        path = self._path(REPUTATION_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.reputation = json.load(f)
                return
            except Exception:
                pass
        self.reputation = {}

    def _save_reputation(self):
        with open(self._path(REPUTATION_FILE), "w") as f:
            json.dump(self.reputation, f, indent=2)

    def _load_vouches(self):
        path = self._path(VOUCHES_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.vouches = json.load(f)
                return
            except Exception:
                pass
        self.vouches = {}

    def _save_vouches(self):
        with open(self._path(VOUCHES_FILE), "w") as f:
            json.dump(self.vouches, f, indent=2)

    def _load_certifications(self):
        path = self._path(CERTIFICATIONS_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.certifications = json.load(f)
                return
            except Exception:
                pass
        self.certifications = {}

    def _save_certifications(self):
        with open(self._path(CERTIFICATIONS_FILE), "w") as f:
            json.dump(self.certifications, f, indent=2)

    # ── AI availability ───────────────────────────────────

    def _check_ollama(self) -> bool:
        try:
            req = urllib.request.Request(f"{OLLAMA_API}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                for model in data.get("models", []):
                    if OLLAMA_MODEL in model.get("name", ""):
                        return True
            return False
        except Exception:
            return False

    def _query_ollama(self, prompt: str, model: str = OLLAMA_MODEL) -> Optional[str]:
        try:
            body = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 128},
            }).encode()
            req = urllib.request.Request(
                f"{OLLAMA_API}/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data.get("response", "")
        except Exception:
            return None

    # ── Reputation management ─────────────────────────────

    def get_reputation(self, node_id: str) -> dict:
        if node_id not in self.reputation:
            self.reputation[node_id] = {
                "node_id": node_id,
                "score": 0.3,
                "level": 0,
                "age_days": 0,
                "vouches": 0,
                "content_count": 0,
                "last_seen": datetime.now().isoformat(),
            }
        return self.reputation[node_id]

    def update_reputation(self, node_id: str, **kwargs):
        rep = self.get_reputation(node_id)
        rep.update(kwargs)
        rep["last_seen"] = datetime.now().isoformat()
        rep["score"] = self._compute_score(rep)
        self.reputation[node_id] = rep
        self._save_reputation()
        return rep

    def _compute_score(self, rep: dict) -> float:
        level_boost = BOOST_BY_LEVEL.get(rep.get("level", 0), 0.3)
        age = min(rep.get("age_days", 0) / 365, 1.0)
        vouches = min(rep.get("vouches", 0) / 10, 1.0)
        content = min(rep.get("content_count", 0) / 100, 1.0)
        score = level_boost * 0.4 + age * 0.2 + vouches * 0.25 + content * 0.15
        return round(min(max(score, 0.0), 1.0), 4)

    # ── Certification ─────────────────────────────────────

    def set_certification(self, node_id: str, level: int, certifier: str = ""):
        if level not in CERTIFICATION_LEVELS:
            return {"error": f"level must be 0-3"}
        self.certifications[node_id] = {
            "level": level,
            "label": CERTIFICATION_LEVELS[level],
            "certifier": certifier,
            "certified_at": datetime.now().isoformat(),
        }
        self._save_certifications()
        self.update_reputation(node_id, level=level)
        return {"status": "certified", "node_id": node_id, "level": level}

    def get_certification(self, node_id: str) -> dict:
        return self.certifications.get(node_id, {
            "level": 0, "label": "inconnu", "certifier": ""
        })

    # ── Vouch system ──────────────────────────────────────

    def vouch(self, voter_id: str, target_id: str):
        if target_id not in self.vouches:
            self.vouches[target_id] = []
        self.vouches[target_id].append({
            "voter": voter_id,
            "ts": datetime.now().isoformat(),
        })
        self._save_vouches()
        rep = self.get_reputation(target_id)
        rep["vouches"] = len(self.vouches[target_id])
        self.update_reputation(target_id, vouches=rep["vouches"])
        return {"status": "vouched", "target": target_id, "total": rep["vouches"]}

    # ── Content scoring ───────────────────────────────────

    def score_content(self, entry: dict) -> float:
        score = 0.5  # baseline neutre

        # Heuristic checks
        text = entry.get("summary", "") + " " + " ".join(entry.get("keywords", []))
        text_lower = text.lower()

        # Penalize ads
        for ad in AD_KEYWORDS:
            if ad in text_lower:
                score -= 0.1
                break

        # Penalize fake news patterns
        for pattern in FAKE_NEWS_PATTERNS:
            if re.search(pattern, text_lower):
                score -= 0.15
                break

        # Boost for length (more content = more likely substantive)
        if len(text) > 500:
            score += 0.05
        if len(entry.get("keywords", [])) >= 5:
            score += 0.05

        # Source reputation
        source = entry.get("source_peer", "")
        if source:
            rep = self.get_reputation(source)
            score += rep.get("score", 0.3) * 0.1

        # Content type boost
        ct = entry.get("content_type", "")
        if ct in ("text", "html", "pdf"):
            score += 0.05

        # AI analysis if available
        if self.ai_available:
            ai_score = self._ai_content_check(text)
            if ai_score is not None:
                score = score * 0.5 + ai_score * 0.5

        return round(min(max(score, 0.0), 1.0), 4)

    def _ai_content_check(self, text: str) -> Optional[float]:
        prompt = (
            "Analyse ce document agricole et note sa fiabilite de 0 a 1:\n"
            "- 0 = contenu publicitaire ou trompeur\n"
            "- 0.5 = contenu neutre non verifiable\n"
            "- 1 = contenu scientifique fiable\n\n"
            f"Document: {text[:1500]}\n\n"
            "Reponds UNIQUEMENT par un nombre entre 0 et 1."
        )
        response = self._query_ollama(prompt)
        if response:
            try:
                match = re.search(r"0\.\d+|1\.0|0|1", response.strip())
                if match:
                    return float(match.group())
            except (ValueError, TypeError):
                pass
        return None

    # ── Peer trust ────────────────────────────────────────

    def score_peer(self, node_id: str) -> float:
        rep = self.get_reputation(node_id)
        return rep.get("score", 0.3)

    def rank_peers(self, peer_list: list) -> list:
        scored = []
        for peer in peer_list:
            node_id = peer.get("node_id", "")
            score = self.score_peer(node_id)
            scored.append({**peer, "trust_score": score})
        scored.sort(key=lambda x: -x["trust_score"])
        return scored

    # ── Stats ─────────────────────────────────────────────

    def stats(self) -> dict:
        level_counts = defaultdict(int)
        for cert in self.certifications.values():
            level_counts[cert.get("level", 0)] += 1

        return {
            "nodes_tracked": len(self.reputation),
            "certified_nodes": sum(1 for c in self.certifications.values()
                                   if c.get("level", 0) >= 2),
            "vouches_total": sum(len(v) for v in self.vouches.values()),
            "ai_available": self.ai_available,
            "ai_model": OLLAMA_MODEL if self.ai_available else None,
            "certification_levels": dict(level_counts),
            "score_distribution": {
                "high": sum(1 for r in self.reputation.values() if r["score"] >= 0.7),
                "medium": sum(1 for r in self.reputation.values() if 0.4 <= r["score"] < 0.7),
                "low": sum(1 for r in self.reputation.values() if r["score"] < 0.4),
            },
        }

    def clear_all(self):
        self.reputation = {}
        self.vouches = {}
        self.certifications = {}
        self._save_reputation()
        self._save_vouches()
        self._save_certifications()
        return {"status": "cleared"}
