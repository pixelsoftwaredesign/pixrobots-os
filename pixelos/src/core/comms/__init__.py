# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""Pixel Comms — Module de communication décentralisé PixelOS.

Architecture:
  Conduit (Matrix)  → Serveur de messagerie décentralisé (Rust/OpenBSD)
  Element Web       → Client Matrix self-hosté
  MatrixCommsBridge → Pont Python pour gestion des salles, utilisateurs, IoT
  IoT Alert Bridge  → Capteurs → salons Matrix (MQTT → Matrix)
  API REST          → Gestion des salles, invitations, webhooks IoT
"""

from .matrix_comms import MatrixCommsBridge, matrix_comms_bridge
from .comms_routes import register_comms_routes
