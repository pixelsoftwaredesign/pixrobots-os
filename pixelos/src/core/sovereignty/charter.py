"""Charte de Souveraineté PixelOS.

Affichée au premier démarrage et accessible via l'API.
L'acceptation est enregistrée et horodatée.
"""

import structlog
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

log = structlog.get_logger()

CHARTER_TEXT = """
╔══════════════════════════════════════════════════════════════╗
║            CHARTE DE SOUVERAINETÉ PixelOS                    ║
║       Liberté & Responsabilité — Souveraineté Numérique      ║
╚══════════════════════════════════════════════════════════════╝

PRÉAMBULE
PixelOS est un système d'exploitation libre et décentralisé
conçu pour l'agriculture de conservation et la protection de
la biodiversité. Il met à disposition des outils techniques
(DNS, IPFS, Matrix, Wallet, Fédération P2P) permettant à
chaque utilisateur d'exercer une souveraineté numérique
totale sur ses données, ses communications et ses transactions.

ARTICLE 1 — PROPRIÉTÉ ET CONTRÔLE
L'utilisateur est l'unique propriétaire et administrateur de
son nœud PixelOS. Les clés privées (chiffrement, Wallet,
identité fédérée) sont générées localement et ne sont jamais
transmises à la communauté PixelOS ni à aucun tiers.

ARTICLE 2 — RESPONSABILITÉ JURIDIQUE
L'utilisateur est seul responsable :
  • Du contenu hébergé sur son nœud (fichiers, bases de données)
  • Des transactions financières effectuées via son Wallet
  • Des communications échangées via Matrix depuis son serveur
  • De la conformité de ses activités avec les lois de sa
    juridiction (RGPD, agriculture, commerce, fiscalité)

ARTICLE 3 — ABSENCE DE CONTRÔLE CENTRAL
La communauté PixelOS ne dispose d'aucun accès technique aux
nœuds individuels. En conséquence :
  • Aucune donnée utilisateur n'est stockée sur des serveurs
    centraux appartenant à la communauté
  • Aucune clé privée n'est détenue ou gérable par la communauté
  • Aucune interruption de service ne peut être imposée par la
    communauté à un nœud spécifique
  • Le réseau fédéré est une infrastructure P2P où chaque nœud
    est juridiquement indépendant

ARTICLE 4 — SOUS-DOMAINES GRATUITS *.PIXELOS.ORG
Les sous-domaines gratuits (ex: ma-ferme.pixelos.org) sont
fournis via DNS dynamique à titre d'outil technique. Leur
utilisation est soumise à :
  • L'acceptation de la présente Charte
  • L'engagement à ne pas utiliser le sous-domaine pour des
    activités illicites
  • La compréhension que la résolution DNS peut être
    interrompue si l'utilisateur contrevient aux lois applicables
  • La recommandation d'acquérir un nom de domaine personnel
    pour une souveraineté totale

ARTICLE 5 — DOMAINES PERSONNALISÉS
L'utilisateur qui configure son propre nom de domaine
(registraire classique ou domaine Web3 ENS/HNS) devient
entièrement indépendant de l'infrastructure DNS de la
communauté. Aucun lien technique ou juridique ne subsiste
entre la communauté et le contenu hébergé sous ce domaine.

ARTICLE 6 — DONNÉES PERSONNELLES
Conformément au RGPD et aux lois applicables :
  • Aucune donnée personnelle n'est collectée par le logiciel
    PixelOS lui-même
  • Les données de l'utilisateur restent sur son nœud
  • L'utilisateur est seul responsable des données qu'il
    partage via la fédération avec d'autres nœuds
  • L'utilisateur peut à tout moment supprimer son nœud et
    toutes ses données

ARTICLE 7 — ENGAGEMENT COMMUNAUTAIRE
En rejoignant le réseau fédéré PixelOS, l'utilisateur s'engage
à :
  • Respecter les lois de sa juridiction
  • Ne pas utiliser le réseau pour nuire à d'autres membres
  • Contribuer à la protection de la biodiversité agricole
  • Participer à la gouvernance décentralisée de la communauté

ACCEPTATION
En installant et en utilisant PixelOS, vous reconnaissez
avoir lu, compris et accepté les termes de la présente Charte
de Souveraineté. Vous confirmez être seul responsable de
votre nœud et de vos activités au sein du réseau PixelOS.

PixelOS — Logiciel Libre — Communauté Décentralisée
https://github.com/pixelsoftwaredesign/pixelos-agricol
"""


class Charter:
    """Gestion de la Charte de Souveraineté.

    Enregistre l'acceptation, l'horodatage, le hash du nœud.
    """

    def __init__(self):
        self._accepted = False
        self._accepted_at: Optional[str] = None
        self._node_id: Optional[str] = None
        self._acceptance_file = Path("/var/db/pixelos/charter_accepted")
        self._load()

    def _load(self):
        if self._acceptance_file.exists():
            try:
                data = json.loads(self._acceptance_file.read_text())
                self._accepted = data.get("accepted", False)
                self._accepted_at = data.get("accepted_at")
                self._node_id = data.get("node_id")
            except Exception:
                pass

    def _save(self):
        self._acceptance_file.parent.mkdir(parents=True, exist_ok=True)
        self._acceptance_file.write_text(json.dumps({
            "accepted": self._accepted,
            "accepted_at": self._accepted_at,
            "node_id": self._node_id,
            "version": "1.0",
        }, indent=2))

    @property
    def text(self) -> str:
        return CHARTER_TEXT

    @property
    def accepted(self) -> bool:
        return self._accepted

    def accept(self, node_id: str = "") -> dict:
        """Enregistre l'acceptation de la Charte."""
        self._accepted = True
        self._accepted_at = datetime.utcnow().isoformat() + "Z"
        self._node_id = node_id
        self._save()
        log.info("Charte acceptée", node_id=node_id)
        return self.status()

    def status(self) -> dict:
        return {
            "accepted": self._accepted,
            "accepted_at": self._accepted_at,
            "node_id": self._node_id,
            "version": "1.0",
            "charter_summary": (
                "Charte de Souveraineté PixelOS — "
                "L'utilisateur est seul responsable de son nœud."
            ),
        }


charter = Charter()
