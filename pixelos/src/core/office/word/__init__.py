"""Pixel Word — Éditeur de rapports agricoles.

Basé sur Markdown + rich text, avec:
  - Templates de rapports agricoles (récolte, sol, irrigation, biodiversité)
  - Insertion de données IoT en un clic (température, humidité, etc.)
  - Collaboration CRDT temps réel
  - Export PDF/HTML
  - Intégration Pixel Clipboard (coller tableaux Pixel Excel, données Pixel Access)
"""

from __future__ import annotations
import json, re, os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


WORD_DIR = Path("/var/db/pixelos/office/word")
TEMPLATES_DIR = WORD_DIR / "templates"


@dataclass
class WordDocument:
    """Document Pixel Word."""
    doc_id: str
    title: str
    content: str = ""              # Markdown avec extensions Pixel
    author: str = ""
    template: str = "blank"
    tags: list[str] = field(default_factory=list)
    created: str = ""
    modified: str = ""
    category: str = "general"


# Templates agricoles pré-définis
TEMPLATES = {
    "blank": {
        "title": "Document vierge",
        "content": "# {title}\n\nÉcrit par {author}\n\n",
        "description": "Document vide",
    },
    "rapport-recolte": {
        "title": "Rapport de Récolte",
        "content": """# Rapport de Récolte

**Date:** {date}
**Auteur:** {author}
**Espace:** {field:espace}

## Résumé

| Métrique | Valeur |
|----------|--------|
| Surface totale | {field:surface} m² |
| Rendement estimé | {field:rendement} kg |
| Qualité | {field:qualite} |

## Observations

{field:observations}

## Données capteurs

```pixel-sensor
sensor_id={field:capteur_id}
metric=temperature
days=7
```

## Conclusion

""",
        "description": "Template de rapport de récolte agricole",
    },
    "analyse-sol": {
        "title": "Analyse de Sol",
        "content": """# Analyse de Sol

**Date:** {date}
**Espace:** {field:espace}
**Échantillon:** {field:echantillon_id}

## Résultats d'analyse

| Paramètre | Valeur | Seuil |
|-----------|--------|-------|
| pH | {field:ph} | 6.0-7.5 |
| Matière organique | {field:mo}% | >3% |
| Azote (N) | {field:n} mg/kg | >50 |
| Phosphore (P) | {field:p} mg/kg | >30 |
| Potassium (K) | {field:k} mg/kg | >150 |

## Recommandations

{field:recommandations}
""",
        "description": "Template d'analyse physico-chimique du sol",
    },
    "biodiversite": {
        "title": "Fiche Espèce",
        "content": """# Fiche Espèce — {field:nom_scientifique}

**Nom commun:** {field:nom_commun}
**Famille:** {field:famille}
**Statut UICN:** {field:statut_conservation}
**Origine:** {field:pays}

## Description

{field:description}

## Données génomiques

```pixel-biodiversity
species_id={field:species_id}
```

## Observations terrain

{field:observations}
""",
        "description": "Template de fiche espèce pour le réseau fédéré",
    },
    "rapport-irrigation": {
        "title": "Rapport d'Irrigation",
        "content": """# Rapport d'Irrigation

**Période:** {field:date_debut} → {field:date_fin}
**Espace:** {field:espace}

## Synthèse

- Volume total: {field:volume_total} L
- Durée: {field:duree} h
- Cycles: {field:cycles}

## Données capteurs

```pixel-sensor
sensor_id={field:capteur_id}
metric=humidite_sol
days={field:jours}
```

## Analyse IA

```pixel-ml
model=irrigation
zone={field:espace}
```

## Recommandations

{field:recommandations}
""",
        "description": "Template de rapport d'irrigation intelligent",
    },
}


class PixelWord:
    """Éditeur de rapports agricoles Pixel Word."""

    def __init__(self):
        os.makedirs(WORD_DIR, exist_ok=True)
        os.makedirs(TEMPLATES_DIR, exist_ok=True)

    def list_templates(self) -> list[dict]:
        """Liste les templates disponibles."""
        return [
            {"id": tid, "title": t["title"], "description": t.get("description", "")}
            for tid, t in TEMPLATES.items()
        ]

    def get_template(self, template_id: str) -> Optional[dict]:
        return TEMPLATES.get(template_id)

    def create_from_template(self, template_id: str, title: str,
                             author: str = "", fields: dict = None,
                             tags: list = None) -> Optional[WordDocument]:
        """Crée un document depuis un template agricole."""
        tmpl = TEMPLATES.get(template_id)
        if not tmpl:
            return None

        import hashlib, time
        doc_id = hashlib.sha256(f"{title}{time.time()}{author}".encode()).hexdigest()[:16]
        fields = fields or {}
        content = tmpl["content"]

        # Remplacer les champs
        now = datetime.now().strftime("%Y-%m-%d")
        content = content.replace("{date}", now)
        content = content.replace("{author}", author or "Utilisateur")
        content = content.replace("{title}", title)
        for key, val in fields.items():
            content = content.replace(f"{{field:{key}}}", str(val))

        return WordDocument(
            doc_id=doc_id,
            title=title,
            content=content,
            author=author,
            template=template_id,
            tags=tags or [],
            created=datetime.now().isoformat(),
            modified=datetime.now().isoformat(),
            category=TEMPLATES[template_id].get("category", "general"),
        )

    def render_markdown(self, doc: WordDocument) -> str:
        """Convertit le contenu Pixel Word en HTML."""
        content = doc.content

        # Remplacer les blocs spéciaux Pixel
        # Capteurs IoT
        content = re.sub(
            r'```pixel-sensor\n(.*?)```',
            self._render_sensor_block,
            content, flags=re.DOTALL
        )
        # Biodiversité
        content = re.sub(
            r'```pixel-biodiversity\n(.*?)```',
            '<div class="pixel-block biodiversity">📊 Données biodiversité</div>',
            content, flags=re.DOTALL
        )
        # ML
        content = re.sub(
            r'```pixel-ml\n(.*?)```',
            '<div class="pixel-block ml">🤖 Prédiction IA</div>',
            content, flags=re.DOTALL
        )

        # Markdown basique -> HTML
        html = content
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

        # Tableaux
        html = re.sub(
            r'(\|.+\|\n\|[-|]+\|\n(?:\|.+\|\n?)+)',
            self._render_table, html
        )

        html = re.sub(r'\n', '<br>', html)
        return f'<div class="pixel-word-content">{html}</div>'

    def _render_sensor_block(self, match) -> str:
        """Rend un bloc capteur IoT."""
        params = match.group(1)
        return f'<div class="pixel-block sensor">📡 Données capteur: {params.strip()}</div>'

    def _render_table(self, match) -> str:
        """Convertit un tableau Markdown en HTML."""
        lines = match.group(0).strip().split("\n")
        if len(lines) < 2:
            return match.group(0)
        headers = [h.strip() for h in lines[0].strip("|").split("|")]
        html = "<table><thead><tr>"
        for h in headers:
            html += f"<th>{h}</th>"
        html += "</tr></thead><tbody>"
        for line in lines[2:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            html += "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
        html += "</tbody></table>"
        return html

    def save(self, doc: WordDocument) -> dict:
        """Sauvegarde un document Word."""
        path = WORD_DIR / f"{doc.doc_id}.pword"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(doc), f, ensure_ascii=False, indent=2)
        return {"status": "ok", "doc_id": doc.doc_id}

    def open(self, doc_id: str) -> Optional[WordDocument]:
        path = WORD_DIR / f"{doc_id}.pword"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return WordDocument(**json.load(f))

    def list(self, category: str = "", author: str = "") -> list[dict]:
        docs = []
        for path in sorted(WORD_DIR.glob("*.pword")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if category and data.get("category") != category:
                        continue
                    if author and data.get("author") != author:
                        continue
                    docs.append({
                        "doc_id": data["doc_id"],
                        "title": data["title"],
                        "template": data.get("template", ""),
                        "author": data.get("author", ""),
                        "modified": data.get("modified", ""),
                        "category": data.get("category", ""),
                    })
            except:
                pass
        return docs

    def export_pdf(self, doc_id: str) -> Optional[str]:
        """Exporte en PDF (HTML simple)."""
        doc = self.open(doc_id)
        if not doc:
            return None
        html = self.render_markdown(doc)
        html_full = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, serif; padding: 2cm; line-height: 1.6; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
  th {{ background: #f5f5f5; }}
  .pixel-block {{ padding: 1em; margin: 1em 0; border-radius: 8px; background: #f0fdf4; border-left: 4px solid #22c55e; }}
  h1 {{ color: #166534; }}
</style></head><body>{html}</body></html>"""
        path = WORD_DIR / f"{doc_id}.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_full)
        return str(path)


word = PixelWord()
