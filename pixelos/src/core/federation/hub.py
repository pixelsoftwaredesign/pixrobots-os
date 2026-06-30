# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""PixelHub API — protocole fédéré d'échange entre nœuds PixelOS."""

from __future__ import annotations
import json, hashlib, hmac
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict


# ─── Messages du protocole ─────────────────────────────────

@dataclass
class FederationMessage:
    """Message standard entre nœuds PixelOS."""
    msg_type: str               # ping, announce, biodiversity_search, biodiversity_push, peer_list
    sender_id: str
    sender_pubkey: str
    timestamp: str
    payload: dict
    signature: str = ""

    def sign(self, private_key: str):
        raw = json.dumps({"type": self.msg_type, "sender": self.sender_id,
                          "ts": self.timestamp, "payload": self.payload},
                         sort_keys=True)
        self.signature = hmac.new(private_key.encode(), raw.encode(),
                                  hashlib.sha3_256).hexdigest()

    def verify(self, public_key: str) -> bool:
        stored = self.signature
        self.signature = ""
        # Au niveau du protocole, on vérifie via la clé publique
        raw = json.dumps({"type": self.msg_type, "sender": self.sender_id,
                          "ts": self.timestamp, "payload": self.payload},
                         sort_keys=True)
        expected = hmac.new(public_key.encode(), raw.encode(),
                            hashlib.sha3_256).hexdigest()
        self.signature = stored
        return stored == expected


class FederationProtocol:
    """Protocole d'échange fédéré entre nœuds PixelOS."""

    API_VERSION = "1.0"
    PIXELOS_FEDERATION = "pixelos-federation"

    @staticmethod
    def ping() -> dict:
        return {
            "api_version": FederationProtocol.API_VERSION,
            "protocol": FederationProtocol.PIXELOS_FEDERATION,
            "timestamp": datetime.now().isoformat(),
            "status": "ok",
        }

    @staticmethod
    def build_biodiversity_query(query: str, confidentiality: str = "public",
                                 sender_id: str = "", sender_pubkey: str = "") -> dict:
        return {
            "type": "biodiversity_search",
            "query": query,
            "confidentiality": confidentiality,
            "sender_id": sender_id,
            "sender_pubkey": sender_pubkey,
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def build_biodiversity_push(records: list[dict], sender_id: str = "",
                                sender_pubkey: str = "", signature: str = "") -> dict:
        return {
            "type": "biodiversity_push",
            "records": records,
            "count": len(records),
            "sender_id": sender_id,
            "sender_pubkey": sender_pubkey,
            "signature": signature,
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def build_peer_list(peers: list[dict], sender_id: str = "",
                        sender_pubkey: str = "") -> dict:
        return {
            "type": "peer_list",
            "peers": peers,
            "count": len(peers),
            "sender_id": sender_id,
            "sender_pubkey": sender_pubkey,
            "timestamp": datetime.now().isoformat(),
        }

    @staticmethod
    def parse_message(data: dict) -> Optional[FederationMessage]:
        try:
            return FederationMessage(
                msg_type=data.get("type", ""),
                sender_id=data.get("sender_id", ""),
                sender_pubkey=data.get("sender_pubkey", ""),
                timestamp=data.get("timestamp", ""),
                payload=data.get("payload", {}),
                signature=data.get("signature", ""),
            )
        except:
            return None


# ─── Routes API REST pour le PixelHub ──────────────────────

def register_federation_routes(app):
    """Enregistre les routes de l'API fédérée sur l'application Flask."""

    @app.route("/api/node/ping")
    def node_ping():
        return {"status": "ok", "node": "pixelos",
                "version": FederationProtocol.API_VERSION}

    @app.route("/api/node/identity")
    def node_identity():
        from core.federation.node import node_manager
        return node_manager.announce()

    @app.route("/api/node/peers")
    def node_peers():
        from core.federation.node import node_manager
        return {"peers": node_manager.list_peers(),
                "count": len(node_manager.list_peers())}

    @app.route("/api/biodiversity/search", methods=["GET"])
    def biodiversity_search():
        from flask import request
        from core.federation.biodiversity import biodiversity_registry
        query = request.args.get("q", "")
        status = request.args.get("status", "")
        if status:
            results = biodiversity_registry.list_by_status(status)
        elif query:
            results = biodiversity_registry.search(query)
        else:
            results = []
        return {"query": query, "results": results, "count": len(results)}

    @app.route("/api/biodiversity/stats")
    def biodiversity_stats():
        from core.federation.biodiversity import biodiversity_registry
        return biodiversity_registry.stats()

    @app.route("/api/federation/announce", methods=["POST"])
    def federation_announce():
        """Réception d'une annonce d'un autre nœud."""
        from flask import request
        from core.federation.node import node_manager
        data = request.get_json(force=True)
        if data:
            node_manager.add_peer(data)
        return {"status": "ok", "timestamp": datetime.now().isoformat()}

    # ─── Routes Mesh WireGuard ────────────────────────────

    @app.route("/api/mesh/status")
    def mesh_status():
        from core.federation.mesh import wireguard_mesh
        return wireguard_mesh.mesh_status()

    @app.route("/api/mesh/peers")
    def mesh_peers():
        from core.federation.mesh import wireguard_mesh
        return {"peers": wireguard_mesh.list_mesh_peers()}

    @app.route("/api/mesh/connect", methods=["POST"])
    def mesh_connect():
        from flask import request
        from core.federation.mesh import wireguard_mesh
        data = request.get_json(force=True)
        if data:
            wireguard_mesh.add_mesh_peer(data)
        return {"status": "ok", "peer": data.get("node_id", "") if data else ""}

    # ─── Routes Gouvernance ───────────────────────────────

    @app.route("/api/gov/status")
    def gov_status():
        from core.federation.governance import governance
        return governance.governance_status()

    @app.route("/api/gov/members")
    def gov_members():
        from core.federation.governance import governance
        return {"members": governance.list_members(),
                "count": governance.member_count()}

    @app.route("/api/gov/proposals", methods=["GET"])
    def gov_proposals_list():
        from flask import request
        from core.federation.governance import governance
        status = request.args.get("status", "")
        return {"proposals": governance.list_proposals(status)}

    @app.route("/api/gov/propose", methods=["POST"])
    def gov_propose():
        from flask import request
        from core.federation.governance import governance
        data = request.get_json(force=True)
        prop = governance.create_proposal(
            title=data.get("title", ""),
            description=data.get("description", ""),
            proposal_type=data.get("type", "update"),
            proposer_id=data.get("proposer_id", ""),
        )
        return {"status": "ok", "proposal_id": prop.proposal_id}

    @app.route("/api/gov/vote", methods=["POST"])
    def gov_vote():
        from flask import request
        from core.federation.governance import governance
        data = request.get_json(force=True)
        result = governance.vote(
            proposal_id=data.get("proposal_id", ""),
            node_id=data.get("node_id", ""),
            vote=data.get("vote", True),
        )
        return result

    # ─── Routes IPFS ──────────────────────────────────────

    @app.route("/api/ipfs/status")
    def ipfs_status():
        from core.federation.ipfs_store import ipfs_store
        return ipfs_store.status()

    @app.route("/api/ipfs/publish", methods=["POST"])
    def ipfs_publish():
        from flask import request
        from core.federation.ipfs_store import ipfs_store
        from core.federation.biodiversity import biodiversity_registry
        data = request.get_json(force=True) or {}
        records = biodiversity_registry.search(data.get("query", ""))
        pub = ipfs_store.publish_biodiversity(
            records, node_id=data.get("node_id", ""))
        if pub:
            return {"status": "ok", "cid": pub.cid, "ipns": pub.ipns,
                    "records": pub.record_count}
        return {"status": "error", "message": "Publication échouée"}

    @app.route("/api/ipfs/fetch/<cid>")
    def ipfs_fetch(cid):
        from core.federation.ipfs_store import ipfs_store
        data = ipfs_store.fetch_biodiversity(cid)
        if data:
            return data
        return {"status": "error", "message": "CID introuvable"}

    # ─── Routes Portail Communauté ─────────────────────────

    @app.route("/api/portal/stats")
    def portal_stats():
        from core.federation.bootstrap import bootstrap_portal
        return bootstrap_portal.community_stats()

    @app.route("/api/portal/join", methods=["POST"])
    def portal_join():
        from flask import request
        from core.federation.bootstrap import bootstrap_portal
        data = request.get_json(force=True)
        return bootstrap_portal.join_request(
            nickname=data.get("nickname", ""),
            email=data.get("email", ""),
            country=data.get("country", ""),
            reason=data.get("reason", ""),
        )

    @app.route("/api/portal/mirrors")
    def portal_mirrors():
        from core.federation.bootstrap import bootstrap_portal
        return {"mirrors": bootstrap_portal.get_mirrors()}

    @app.route("/api/portal/iso")
    def portal_iso():
        from core.federation.bootstrap import bootstrap_portal
        return {"url": bootstrap_portal.get_iso_url()}

    # ─── Routes Matrix ─────────────────────────────────────

    @app.route("/api/matrix/status")
    def matrix_status():
        from core.federation.matrix_bridge import matrix_bridge
        return matrix_bridge.status()

    # ─── Routes Dashboard Fédération ──────────────────────

    @app.route("/federation")
    def federation_dashboard():
        from flask import render_template
        return render_template("federation.html")

    @app.route("/community")
    def community_page():
        from flask import render_template
        return render_template("community.html")

    @app.route("/download")
    def download_page():
        from flask import render_template
        return render_template("download.html")
