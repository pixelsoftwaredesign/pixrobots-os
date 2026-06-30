# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""Moteur Pixel Document — format commun, CRDT, rendu.

Tous les documents Pixel Office (Word, Excel, Access) utilisent:
  - Format: JSON compressé (.pdoc)
  - Collaboration: CRDT (Conflict-free Replicated Data Types)
  - Rendu: Skia/Canvas via HTML5
  - Signature: HMAC-SHA256 pour l'intégrité
"""

from __future__ import annotations
import json, gzip, hashlib, hmac, time, os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


PDOC_DIR = Path("/var/db/pixelos/documents")
PDOC_EXT = ".pdoc"


@dataclass
class PixelDocument:
    """Document Pixel Office universel."""
    doc_id: str
    title: str
    doc_type: str = "document"   # word, excel, access, report
    version: int = 1
    content: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    author: str = ""
    created: str = ""
    modified: str = ""
    signature: str = ""
    collaborators: list[str] = field(default_factory=list)
    # CRDT
    crdt_clock: int = 0
    crdt_ops: list[dict] = field(default_factory=list)


@dataclass
class CRDTHash:
    """Opération CRDT pour la collaboration temps réel."""
    op_id: str
    op_type: str          # insert, delete, update, merge
    position: int = 0
    content: str = ""
    author: str = ""
    timestamp: str = ""
    hash_prev: str = ""
    hash_current: str = ""


class PixelDocumentEngine:
    """Cœur de la suite Pixel Office — gestion, CRDT, rendu."""

    EXTENSION = ".pdoc"
    CRDT_SEED = "pixelos-crdt-v1"

    def __init__(self):
        os.makedirs(PDOC_DIR, exist_ok=True)

    # ─── CRUD Documents ───────────────────────────────

    def create(self, title: str, doc_type: str = "document",
               author: str = "", content: dict = None) -> PixelDocument:
        """Crée un nouveau document Pixel."""
        doc_id = hashlib.sha256(
            f"{title}{time.time()}{author}".encode()
        ).hexdigest()[:16]

        doc = PixelDocument(
            doc_id=doc_id,
            title=title,
            doc_type=doc_type,
            content=content or {},
            author=author,
            created=datetime.now().isoformat(),
            modified=datetime.now().isoformat(),
            crdt_clock=0,
        )
        doc.signature = self._sign(doc)
        self._save(doc)
        return doc

    def open(self, doc_id: str) -> Optional[PixelDocument]:
        """Ouvre un document depuis le stockage local."""
        path = PDOC_DIR / f"{doc_id}{self.EXTENSION}"
        if not path.exists():
            return None
        with gzip.open(path, "rt") as f:
            data = json.load(f)
            doc = PixelDocument(**data)
            if not self._verify(doc):
                print(f"⚠️  Signature invalide pour {doc_id}")
            return doc

    def save(self, doc: PixelDocument) -> bool:
        """Sauvegarde un document (incrémente version)."""
        doc.version += 1
        doc.modified = datetime.now().isoformat()
        doc.signature = self._sign(doc)
        self._save(doc)
        return True

    def delete(self, doc_id: str) -> bool:
        path = PDOC_DIR / f"{doc_id}{self.EXTENSION}"
        if path.exists():
            path.unlink()
            return True
        return False

    def list(self, doc_type: str = "",
             author: str = "") -> list[dict]:
        """Liste tous les documents Pixel."""
        docs = []
        for path in sorted(PDOC_DIR.glob(f"*{self.EXTENSION}")):
            with gzip.open(path, "rt") as f:
                try:
                    data = json.load(f)
                    if doc_type and data.get("doc_type") != doc_type:
                        continue
                    if author and data.get("author") != author:
                        continue
                    docs.append({
                        "doc_id": data["doc_id"],
                        "title": data["title"],
                        "type": data.get("doc_type", ""),
                        "version": data.get("version", 0),
                        "modified": data.get("modified", ""),
                        "author": data.get("author", ""),
                        "collaborators": data.get("collaborators", []),
                    })
                except:
                    pass
        return docs

    def search(self, query: str) -> list[dict]:
        """Recherche plein texte dans les documents."""
        results = []
        for doc in self.list():
            if query.lower() in doc["title"].lower():
                results.append(doc)
                continue
            full = self.open(doc["doc_id"])
            if full and json.dumps(full.content).lower().find(query.lower()) >= 0:
                results.append(doc)
        return results

    # ─── CRDT (Collaboration temps réel) ──────────────

    def crdt_push_op(self, doc: PixelDocument, op_type: str,
                     position: int, content: str = "",
                     author: str = "") -> CRDTHash:
        """Ajoute une opération CRDT à l'historique."""
        doc.crdt_clock += 1
        prev_hash = doc.crdt_ops[-1]["hash_current"] if doc.crdt_ops else ""

        op = CRDTHash(
            op_id=f"{doc.doc_id}-{doc.crdt_clock}",
            op_type=op_type,
            position=position,
            content=content,
            author=author or doc.author,
            timestamp=datetime.now().isoformat(),
            hash_prev=prev_hash,
            hash_current=hashlib.sha256(
                f"{doc.crdt_clock}{op_type}{position}{content}{prev_hash}{self.CRDT_SEED}".encode()
            ).hexdigest()[:16],
        )
        doc.crdt_ops.append(asdict(op))
        return op

    def crdt_merge(self, doc: PixelDocument,
                   remote_ops: list[dict]) -> dict:
        """Fusionne les opérations CRDT distantes (conflit résolu par position)."""
        merged = 0
        conflicts = 0
        local_hashes = set(o["hash_current"] for o in doc.crdt_ops)

        for op in remote_ops:
            if op["hash_current"] not in local_hashes:
                # Vérifier la chaîne de hash
                prev_hash = doc.crdt_ops[-1]["hash_current"] if doc.crdt_ops else ""
                expected = hashlib.sha256(
                    f"{op['op_id'].split('-')[-1]}{op['op_type']}{op['position']}"
                    f"{op['content']}{prev_hash}{self.CRDT_SEED}".encode()
                ).hexdigest()[:16]

                if op["hash_current"] == expected or not prev_hash:
                    doc.crdt_ops.append(op)
                    merged += 1
                else:
                    conflicts += 1

        doc.crdt_clock = max(doc.crdt_clock,
                             max((int(o["op_id"].split("-")[-1]) for o in doc.crdt_ops), default=0))
        return {"merged": merged, "conflicts": conflicts, "total": len(doc.crdt_ops)}

    # ─── Signature et intégrité ───────────────────────

    def _sign(self, doc: PixelDocument) -> str:
        raw = json.dumps({
            "id": doc.doc_id, "title": doc.title, "type": doc.doc_type,
            "version": doc.version, "content_hash": hashlib.sha256(
                json.dumps(doc.content, sort_keys=True).encode()).hexdigest(),
        }, sort_keys=True)
        return hmac.new(self.CRDT_SEED.encode(), raw.encode(),
                        hashlib.sha256).hexdigest()[:16]

    def _verify(self, doc: PixelDocument) -> bool:
        stored = doc.signature
        doc.signature = ""
        expected = self._sign(doc)
        doc.signature = stored
        return stored == expected

    def _save(self, doc: PixelDocument):
        path = PDOC_DIR / f"{doc.doc_id}{self.EXTENSION}"
        with gzip.open(path, "wt") as f:
            json.dump(asdict(doc), f, ensure_ascii=False, indent=2)

    # ─── Statistiques ─────────────────────────────────

    def stats(self) -> dict:
        docs = self.list()
        types = {}
        for d in docs:
            t = d["type"]
            types[t] = types.get(t, 0) + 1
        return {
            "total_documents": len(docs),
            "by_type": types,
            "storage_path": str(PDOC_DIR),
            "format": self.EXTENSION,
        }


engine = PixelDocumentEngine()
