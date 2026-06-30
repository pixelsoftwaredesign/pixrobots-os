"""Module Fédération PixelOS — réseau mondial de biodiversité.

Modules:
  - biodiversity.py   : Standard de données biodiversité (espèces, conservation, génome)
  - node.py           : Identité, clés, pairs, découverte DHT
  - hub.py            : API REST Flask du protocole fédéré
  - mesh.py           : Réseau WireGuard mesh P2P entre nœuds
  - governance.py     : Gouvernance communautaire (votes, consensus, mises à jour)
  - ipfs_store.py     : Stockage décentralisé IPFS pour données publiques
  - bootstrap.py      : Portail d'amorçage communauté (seed nodes, ISO, miroirs)
  - matrix_bridge.py  : Pont Matrix pour messagerie temps réel
"""

from .biodiversity import BiodiversityRecord, ConservationRecord, Geolocation, CultivationProfile, SeedStock, GenomeReference, BiodiversityRegistry, biodiversity_registry
from .node import PixelNodeIdentity, NodeManager, node_manager
from .hub import FederationProtocol, FederationMessage, register_federation_routes
from .mesh import WireGuardMesh, wireguard_mesh, MeshPeer
from .governance import Governance, governance, Member, Proposal
from .ipfs_store import IPFSStore, ipfs_store
from .bootstrap import BootstrapPortal, bootstrap_portal, BootstrapNode, CommunityStats
from .matrix_bridge import MatrixBridge, matrix_bridge, MatrixConfig
