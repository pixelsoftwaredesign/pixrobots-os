# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
#!/usr/bin/env python3
"""
PixDAO — Decentralized Autonomous Organization.

Gouvernance on-chain des décisions agricoles:
votes, propositions, budget participatif, smart-contracts.
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

DAO_DIR = "/var/db/pixelos/pixdao"


class PixDAO:
    def __init__(self):
        self._ensure_dirs()
        self._load_state()
        self.next_id = max([p.get("id", 0) for p in self.proposals] or [0]) + 1

    def _ensure_dirs(self):
        Path(DAO_DIR).mkdir(parents=True, exist_ok=True)

    def _path(self, name):
        return str(Path(DAO_DIR) / name)

    def _load_state(self):
        path = self._path("proposals.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                    self.proposals = data.get("proposals", [])
                    self.members = data.get("members", {})
                    self.treasury = data.get("treasury", {
                        "balance": 0, "token": "PIX", "transactions": []
                    })
                    self.config = data.get("config", {
                        "quorum": 0.1,
                        "voting_period_h": 72,
                        "min_deposit": 100,
                        "executor": "pixkey",
                    })
                return
            except Exception:
                pass
        self.proposals = []
        self.members = {}
        self.treasury = {"balance": 0, "token": "PIX", "transactions": []}
        self.config = {"quorum": 0.1, "voting_period_h": 72, "min_deposit": 100, "executor": "pixkey"}

    def _save_state(self):
        with open(self._path("proposals.json"), "w") as f:
            json.dump({
                "proposals": self.proposals,
                "members": self.members,
                "treasury": self.treasury,
                "config": self.config,
            }, f, indent=2)

    # ── Proposals ──────────────────────────────────────────

    def create_proposal(self, title: str, description: str = "",
                        proposal_type: str = "general",
                        metadata: dict = None) -> dict:
        prop = {
            "id": self.next_id,
            "title": title,
            "description": description,
            "type": proposal_type,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "ends_at": (datetime.now().timestamp() + self.config["voting_period_h"] * 3600),
            "votes_yes": 0,
            "votes_no": 0,
            "votes_abstain": 0,
            "voters": {},
            "metadata": metadata or {},
            "executed": False,
        }
        self.next_id += 1
        self.proposals.insert(0, prop)
        self._save_state()
        return prop

    def vote(self, proposal_id: int, voter: str, choice: str, weight: float = 1.0) -> dict:
        prop = self._find_proposal(proposal_id)
        if not prop:
            return {"status": "error", "reason": "not found"}
        if prop["status"] != "active":
            return {"status": "error", "reason": "proposal not active"}
        if time.time() > prop["ends_at"]:
            prop["status"] = "closed"
            self._save_state()
            return {"status": "error", "reason": "voting period ended"}
        if voter in prop["voters"]:
            return {"status": "error", "reason": "already voted"}

        choice = choice.lower()
        if choice not in ("yes", "no", "abstain"):
            return {"status": "error", "reason": "invalid choice"}

        prop["voters"][voter] = {"choice": choice, "weight": weight,
                                  "voted_at": datetime.now().isoformat()}
        prop[f"votes_{choice}"] += weight
        self._save_state()

        # Auto-execute if quorum reached
        self._check_execution(prop)
        return {"status": "ok", "proposal_id": proposal_id, "choice": choice, "weight": weight}

    def _find_proposal(self, proposal_id: int) -> Optional[dict]:
        for p in self.proposals:
            if p["id"] == proposal_id:
                return p
        return None

    def _check_execution(self, prop: dict):
        if prop["status"] != "active":
            return
        total_votes = prop["votes_yes"] + prop["votes_no"] + prop["votes_abstain"]
        member_count = max(len(self.members), 1)
        if member_count == 0 or total_votes / member_count >= self.config["quorum"]:
            if time.time() >= prop["ends_at"]:
                prop["status"] = "closed"
                if prop["votes_yes"] > prop["votes_no"] and not prop["executed"]:
                    self._execute_proposal(prop)
                self._save_state()

    def _execute_proposal(self, prop: dict):
        ptype = prop.get("type", "general")
        meta = prop.get("metadata", {})

        if ptype == "treasury":
            amount = meta.get("amount", 0)
            recipient = meta.get("recipient", "")
            if amount > 0 and recipient and self.treasury["balance"] >= amount:
                self.treasury["balance"] -= amount
                self.treasury["transactions"].append({
                    "type": "payout",
                    "amount": amount,
                    "recipient": recipient,
                    "proposal_id": prop["id"],
                    "executed_at": datetime.now().isoformat(),
                })
                prop["executed"] = True

        elif ptype == "config":
            for k, v in meta.get("changes", {}).items():
                if k in self.config:
                    self.config[k] = v
            prop["executed"] = True

        else:
            prop["executed"] = True

        self._save_state()

    def close_expired(self):
        closed = 0
        for prop in self.proposals:
            if prop["status"] == "active" and time.time() > prop["ends_at"]:
                prop["status"] = "closed"
                if prop["votes_yes"] > prop["votes_no"] and not prop["executed"]:
                    self._execute_proposal(prop)
                closed += 1
        if closed:
            self._save_state()
        return closed

    # ── Members ────────────────────────────────────────────

    def add_member(self, address: str, role: str = "member",
                   weight: float = 1.0, label: str = "") -> dict:
        if address in self.members:
            return {"status": "error", "reason": "already member"}
        self.members[address] = {
            "address": address,
            "role": role,
            "weight": weight,
            "label": label or address[:10],
            "joined_at": datetime.now().isoformat(),
            "proposals_created": 0,
            "votes_cast": 0,
        }
        self._save_state()
        return {"status": "member_added", "address": address}

    def remove_member(self, address: str) -> dict:
        if address not in self.members:
            return {"status": "error", "reason": "not found"}
        del self.members[address]
        self._save_state()
        return {"status": "member_removed", "address": address}

    # ── Treasury ───────────────────────────────────────────

    def deposit(self, amount: float, source: str = "") -> dict:
        self.treasury["balance"] += amount
        self.treasury["transactions"].append({
            "type": "deposit",
            "amount": amount,
            "source": source or "unknown",
            "executed_at": datetime.now().isoformat(),
        })
        self._save_state()
        return {"status": "deposited", "new_balance": self.treasury["balance"]}

    def treasury_history(self, limit: int = 50) -> list:
        return self.treasury["transactions"][-limit:]

    # ── Config ─────────────────────────────────────────────

    def update_config(self, changes: dict) -> dict:
        for k, v in changes.items():
            if k in self.config:
                self.config[k] = v
        self._save_state()
        return {"status": "config_updated", "config": self.config}

    # ── List ───────────────────────────────────────────────

    def list_proposals(self, status: str = "") -> list:
        if status:
            return [p for p in self.proposals if p["status"] == status]
        return self.proposals

    def get_proposal(self, proposal_id) -> Optional[dict]:
        return self._find_proposal(proposal_id if isinstance(proposal_id, int) else int(proposal_id))

    def list_members(self) -> dict:
        return self.members

    # ── Stats ──────────────────────────────────────────────

    def stats(self) -> dict:
        active = len([p for p in self.proposals if p["status"] == "active"])
        closed = len([p for p in self.proposals if p["status"] == "closed"])
        passed = len([p for p in self.proposals if p.get("executed")])
        return {
            "proposals_total": len(self.proposals),
            "proposals_active": active,
            "proposals_closed": closed,
            "proposals_passed": passed,
            "members": len(self.members),
            "treasury_balance": self.treasury["balance"],
            "token": self.treasury["token"],
            "quorum": self.config["quorum"],
            "voting_period_h": self.config["voting_period_h"],
        }
