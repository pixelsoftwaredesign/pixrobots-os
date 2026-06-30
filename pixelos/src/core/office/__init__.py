# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""Pixel Office Suite — Suite bureautique agricole intelligente.

Modules:
  document.py   — Moteur Pixel Document (format .pdoc, CRDT, signature)
  clipboard.py  — Presse-papier unifié inter-applications
  access/       — Pixel Access (base de données agricole)
  word/         — Pixel Word (éditeur de rapports)
  excel/        — Pixel Excel (tableur + calculs)
"""

from .document import PixelDocument, PixelDocumentEngine, CRDTHash, engine
from .clipboard import PixelClipboard, PixelClipboardData, clipboard
