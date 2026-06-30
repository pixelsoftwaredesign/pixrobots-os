# Pixel Software Design � Copyright 2026
"""Gouvernance PixelOS — signatures, consensus, mises à jour communautaires."""

from __future__ import annotations
import json, hashlib, hmac, time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


GOV_DIR = Path("/var/db/pixelos/governance")
CONSENSUS_FILE = GOV_DIR / "consensus.json"
MEMBERS_FILE = GOV_DIR / "members.json"
PROPOSALS_DIR = GOV_DIR / "proposals"


@dataclass
class Member:
    """Membre de l'association internationale PixelOS."""
    node_id: str
    public_key: str
    nickname: str
    role: str = "member"         # member, validator, council, founder
    reputation: int = 100
    joined: str = ""
    last_active: str = ""
    country: str = ""
    region: str = ""
    votes: int = 1               # poids du vote
    banned: bool = False


@dataclass
class Proposal:
    """Proposition de mise à jour du réseau."""
    proposal_id: str = ""
    title: str = ""
    description: str = ""
    proposal_type: str = "update"  # update, new_member, policy, budget
    proposer_id: str = ""
    status: str = "open"         # open, voting, approved, rejected, implemented
    votes_for: list[str] = field(default_factory=list)
    votes_against: list[str] = field(default_factory=list)
    created: str = ""
    deadline: str = ""
    approved_by: str = ""


class Governance:
    """Système de gouvernance décentralisée du réseau PixelOS."""

    CONSENSUS_THRESHOLD = 0.67   # 67% des votes requis
    VOTING_PERIOD_H = 72         # 72h pour voter

    def __init__(self):
        os.makedirs(PROPOSALS_DIR, exist_ok=True)

    def register_member(self, node_id: str, public_key: str,
                        nickname: str = "", country: str = "",
                        region: str = "") -> Member:
        """Enregistre un nouveau membre de l'association."""
        member = Member(
            node_id=node_id,
            public_key=public_key,
            nickname=nickname or node_id[:8],
            role="member",
            joined=datetime.now().isoformat(),
            last_active=datetime.now().isoformat(),
            country=country,
            region=region,
        )
        members = self.list_members()
        # Vérifier si déjà enregistré
        for m in members:
            if m["node_id"] == node_id:
                return Member(**m)
        members.append(asdict(member))
        with open(MEMBERS_FILE, "w") as f:
            json.dump(members, f, ensure_ascii=False, indent=2)
        return member

    def list_members(self) -> list[dict]:
        if not MEMBERS_FILE.exists():
            return []
        return json.load(open(MEMBERS_FILE))

    def member_count(self) -> int:
        return len(self.list_members())

    def create_proposal(self, title: str, description: str,
                        proposal_type: str = "update",
                        proposer_id: str = "") -> Proposal:
        """Crée une proposition soumise au vote de la communauté."""
        proposal_id = hashlib.sha256(
            f"{title}{time.time()}{proposer_id}".encode()
        ).hexdigest()[:12]

        proposal = Proposal(
            proposal_id=proposal_id,
            title=title,
            description=description,
            proposal_type=proposal_type,
            proposer_id=proposer_id,
            created=datetime.now().isoformat(),
            deadline=datetime.fromtimestamp(
                time.time() + self.VOTING_PERIOD_H * 3600
            ).isoformat(),
        )
        with open(PROPOSALS_DIR / f"{proposal_id}.json", "w") as f:
            json.dump(asdict(proposal), f, ensure_ascii=False, indent=2)
        return proposal

    def vote(self, proposal_id: str, node_id: str, vote: bool) -> dict:
        """Vote sur une proposition."""
        prop_file = PROPOSALS_DIR / f"{proposal_id}.json"
        if not prop_file.exists():
            return {"status": "error", "message": "Proposition introuvable"}

        proposal = json.load(open(prop_file))

        # Vérifier si la période de vote est terminée
        if proposal["deadline"] < datetime.now().isoformat():
            return {"status": "error", "message": "Période de vote terminée"}

        # Vérifier si déjà voté
        if node_id in proposal["votes_for"] or node_id in proposal["votes_against"]:
            return {"status": "error", "message": "Déjà voté"}

        if vote:
            proposal["votes_for"].append(node_id)
        else:
            proposal["votes_against"].append(node_id)

        # Vérifier le consensus
        total_votes = len(proposal["votes_for"]) + len(proposal["votes_against"])
        if total_votes >= self.member_count() * self.CONSENSUS_THRESHOLD:
            approval = len(proposal["votes_for"]) / max(total_votes, 1)
            if approval >= self.CONSENSUS_THRESHOLD:
                proposal["status"] = "approved"
            else:
                proposal["status"] = "rejected"

        with open(prop_file, "w") as f:
            json.dump(proposal, f, ensure_ascii=False, indent=2)

        return {
            "status": "ok",
            "proposal_id": proposal_id,
            "vote": "for" if vote else "against",
            "total_votes": total_votes,
            "approval": f"{approval:.0%}" if total_votes > 0 else "0%",
        }

    def list_proposals(self, status: str = "") -> list[dict]:
        proposals = []
        for f in sorted(PROPOSALS_DIR.glob("*.json")):
            try:
                prop = json.load(open(f))
                if not status or prop["status"] == status:
                    proposals.append(prop)
            except:
                pass
        return proposals

    def verify_update(self, update_package: str, signatures: list[str]) -> bool:
        """Vérifie qu'une mise à jour est signée par assez de validateurs."""
        valid = 0
        members = self.list_members()
        validators = [m for m in members if m["role"] in ("validator", "council")]

        for sig in signatures:
            for v in validators:
                expected = hashlib.sha3_256(
                    (open(update_package, "rb").read() + v["public_key"].encode())
                ).hexdigest()
                if sig == expected:
                    valid += 1
                    break

        return valid >= len(validators) * self.CONSENSUS_THRESHOLD

    def governance_status(self) -> dict:
        proposals = self.list_proposals()
        members = self.list_members()
        return {
            "members": len(members),
            "validators": sum(1 for m in members if m["role"] in ("validator", "council")),
            "proposals_open": len([p for p in proposals if p["status"] == "open"]),
            "proposals_approved": len([p for p in proposals if p["status"] == "approved"]),
            "proposals_rejected": len([p for p in proposals if p["status"] == "rejected"]),
            "consensus_threshold": f"{self.CONSENSUS_THRESHOLD:.0%}",
            "voting_period_h": self.VOTING_PERIOD_H,
        }


import os
governance = Governance()
