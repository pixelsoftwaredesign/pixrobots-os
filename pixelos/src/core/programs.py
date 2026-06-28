"""PixelOS Programs - Gestion des programmes Text, Audio, Video."""

import os
import json
import uuid
import shutil
import structlog
from pathlib import Path
from datetime import datetime

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
NOTES_DIR = DATA_DIR / "notes"
AUDIO_DIR = DATA_DIR / "audio"
VIDEO_DIR = DATA_DIR / "video"


class ProgramManager:
    """Gère les programmes text, audio et video de PixelOS."""

    def __init__(self):
        for d in (NOTES_DIR, AUDIO_DIR, VIDEO_DIR):
            d.mkdir(parents=True, exist_ok=True)

    # ── TEXT (Notes) ────────────────────────────────────────

    def notes_list(self) -> list[dict]:
        path = NOTES_DIR / "notes.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _notes_save(self, notes: list[dict]):
        path = NOTES_DIR / "notes.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)

    def note_create(self, title: str, content: str = "", categorie: str = "general") -> dict:
        notes = self.notes_list()
        note = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "content": content,
            "categorie": categorie,
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat(),
        }
        notes.insert(0, note)
        self._notes_save(notes)
        log.info("Note créée", id=note["id"], title=title)
        return note

    def note_get(self, note_id: str) -> dict | None:
        for n in self.notes_list():
            if n["id"] == note_id:
                return n
        return None

    def note_update(self, note_id: str, title: str = None,
                    content: str = None, categorie: str = None) -> dict | None:
        notes = self.notes_list()
        for n in notes:
            if n["id"] == note_id:
                if title is not None:
                    n["title"] = title
                if content is not None:
                    n["content"] = content
                if categorie is not None:
                    n["categorie"] = categorie
                n["updated"] = datetime.now().isoformat()
                self._notes_save(notes)
                log.info("Note mise à jour", id=note_id)
                return n
        return None

    def note_delete(self, note_id: str) -> bool:
        notes = self.notes_list()
        filtered = [n for n in notes if n["id"] != note_id]
        if len(filtered) == len(notes):
            return False
        self._notes_save(filtered)
        log.info("Note supprimée", id=note_id)
        return True

    def note_search(self, query: str) -> list[dict]:
        q = query.lower()
        return [n for n in self.notes_list()
                if q in n["title"].lower() or q in n["content"].lower()]

    def note_categories(self) -> list[str]:
        cats = set()
        for n in self.notes_list():
            if n.get("categorie"):
                cats.add(n["categorie"])
        return sorted(cats)

    # ── AUDIO ───────────────────────────────────────────────

    def audio_list(self) -> list[dict]:
        path = AUDIO_DIR / "audio.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _audio_save_meta(self, items: list[dict]):
        path = AUDIO_DIR / "audio.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

    def audio_add(self, filename: str, title: str = None,
                  duration: float = 0, size: int = 0) -> dict:
        items = self.audio_list()
        entry = {
            "id": str(uuid.uuid4())[:8],
            "filename": filename,
            "title": title or Path(filename).stem,
            "duration": duration,
            "size": size,
            "created": datetime.now().isoformat(),
        }
        items.insert(0, entry)
        self._audio_save_meta(items)
        log.info("Audio ajouté", id=entry["id"], filename=filename)
        return entry

    def audio_delete(self, audio_id: str) -> bool:
        items = self.audio_list()
        entry = None
        for a in items:
            if a["id"] == audio_id:
                entry = a
                break
        if not entry:
            return False
        items = [a for a in items if a["id"] != audio_id]
        self._audio_save_meta(items)
        fpath = AUDIO_DIR / entry["filename"]
        if fpath.exists():
            fpath.unlink()
        log.info("Audio supprimé", id=audio_id)
        return True

    def audio_path(self, audio_id: str) -> str | None:
        for a in self.audio_list():
            if a["id"] == audio_id:
                fp = AUDIO_DIR / a["filename"]
                return str(fp) if fp.exists() else None
        return None

    # ── VIDEO ───────────────────────────────────────────────

    def video_list(self) -> list[dict]:
        path = VIDEO_DIR / "video.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _video_save_meta(self, items: list[dict]):
        path = VIDEO_DIR / "video.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

    def video_add(self, source: str, title: str = None,
                  source_type: str = "url", duration: int = 0) -> dict:
        """Ajoute une video par URL ou chemin fichier."""
        items = self.video_list()
        entry = {
            "id": str(uuid.uuid4())[:8],
            "title": title or "Vidéo " + datetime.now().strftime("%d/%m/%Y"),
            "source": source,
            "source_type": source_type,
            "duration": duration,
            "created": datetime.now().isoformat(),
        }
        items.insert(0, entry)
        self._video_save_meta(items)
        log.info("Vidéo ajoutée", id=entry["id"], source=source)
        return entry

    def video_delete(self, video_id: str) -> bool:
        items = self.video_list()
        items = [v for v in items if v["id"] != video_id]
        if len(items) == len(self.video_list()):
            return False
        self._video_save_meta(items)
        log.info("Vidéo supprimée", id=video_id)
        return True

    def video_update(self, video_id: str, title: str = None,
                     source: str = None) -> dict | None:
        items = self.video_list()
        for v in items:
            if v["id"] == video_id:
                if title is not None:
                    v["title"] = title
                if source is not None:
                    v["source"] = source
                self._video_save_meta(items)
                return v
        return None
