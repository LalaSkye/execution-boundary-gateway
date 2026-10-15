#!/usr/bin/env python3
"""
v0.4-candidate execution-boundary gateway.
Isolated local prototype. Prior versions and repositories untouched.

Immutable payload: one ordinary bytes snapshot is captured at the start of decide_and_execute.
That same snapshot is hashed and, if all checks pass, written. The original caller object is never reread.

Issuer control: issue() refuses a duplicate decision ID. Only the issuer may write the store.
Execution path only retrieves. Caller-controlled records cannot replace an existing entry.
What is assumed rather than enforced: the Issuer object itself is not shared with untrusted callers;
in this local model the test harness holds the issuer and does not expose issue() to the proposal path.

Nonce consumption remains after all other checks, immediately before the write.
Crash-safe atomicity, cryptographic authentication and concurrent safety are not claimed.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

class ControlledClock:
    def __init__(self, start: str = "2026-10-15T22:00:00Z"):
        self.now_iso = start

    def now(self) -> datetime:
        return datetime.fromisoformat(self.now_iso.replace("Z", "+00:00"))

    def advance(self, iso: str):
        self.now_iso = iso

class Issuer:
    """Issuer-controlled store. issue() is the only write path and refuses duplicates."""
    def __init__(self):
        self._records: Dict[str, "AuthorisationRecord"] = {}
        self._active: Dict[str, bool] = {}

    def issue(self, record: "AuthorisationRecord") -> bool:
        if record.decision_id in self._records:
            return False  # refuse overwrite
        self._records[record.decision_id] = record
        self._active[record.decision_id] = True
        return True

    def withdraw(self, decision_id: str) -> None:
        self._active[decision_id] = False

    def retrieve(self, decision_id: str) -> Optional["AuthorisationRecord"]:
        if not self._active.get(decision_id, False):
            return None
        return self._records.get(decision_id)

class NonceLedger:
    def __init__(self):
        self.consumed: set[str] = set()

    def is_fresh(self, nonce: str) -> bool:
        return nonce not in self.consumed

    def consume(self, nonce: str) -> bool:
        if nonce in self.consumed:
            return False
        self.consumed.add(nonce)
        return True

class StateStore:
    def __init__(self, initial_state: str = "PENDING"):
        self.state = initial_state
        self.admissible = {
            ("PENDING", "APPROVED"),
            ("PENDING", "REJECTED"),
            ("APPROVED", "PAID"),
        }

    def is_admissible(self, requested: str) -> bool:
        return (self.state, requested) in self.admissible

    def apply(self, requested: str):
        self.state = requested

class Writer:
    def __init__(self, initial: bytes = b"initial"):
        self.entered = 0
        self.mutations = 0
        self.bytes = initial
        self.hash_before: Optional[str] = None
        self.hash_after: Optional[str] = None

    def write(self, snapshot: bytes):
        self.entered += 1
        self.hash_before = sha256(self.bytes)
        self.bytes = snapshot  # the captured snapshot, never a re-read
        self.mutations += 1
        self.hash_after = sha256(self.bytes)

    def unchanged(self, initial_hash: str) -> bool:
        return self.entered == 0 and self.mutations == 0 and sha256(self.bytes) == initial_hash

@dataclass(frozen=True)
class AuthorisationRecord:
    decision_id: str
    payload_hash: str
    actor_id: str
    action: str
    scope: str
    target: str
    environment: str
    expires_at: str
    nonce: str
    permitted_consequence: str

@dataclass
class Proposal:
    decision_id: str
    payload: Any  # may be hostile; snapshot taken immediately
    actor_id: str
    action: str
    scope: str
    target: str
    environment: str
    requested_state: str

class Gateway:
    def __init__(self, issuer: Issuer, nonce_ledger: NonceLedger, state: StateStore, clock: ControlledClock, writer: Writer):
        self.issuer = issuer
        self.nonce_ledger = nonce_ledger
        self.state = state
        self.clock = clock
        self.writer = writer

    def decide_and_execute(self, proposal: Proposal) -> Dict[str, Any]:
        checks: Dict[str, bool] = {}
        # Capture one immutable ordinary bytes snapshot. Never reread proposal.payload.
        try:
            snapshot = bytes(proposal.payload)
        except Exception:
            return self._refuse("payload_not_bytes", checks)
        snapshot_hash = sha256(snapshot)

        record = self.issuer.retrieve(proposal.decision_id)
        checks["record_present_and_active"] = record is not None
        if record is None:
            return self._refuse("record_missing_or_withdrawn", checks)

        checks["payload_digest"] = snapshot_hash == record.payload_hash
        checks["actor"] = proposal.actor_id == record.actor_id
        checks["action"] = proposal.action == record.action
        checks["scope"] = proposal.scope == record.scope
        checks["target"] = proposal.target == record.target
        checks["environment"] = proposal.environment == record.environment
        checks["consequence_match"] = proposal.requested_state == record.permitted_consequence
        if not all(checks[k] for k in ["payload_digest", "actor", "action", "scope", "target", "environment", "consequence_match"]):
            return self._refuse("binding_mismatch", checks)

        now = self.clock.now()
        try:
            exp = datetime.fromisoformat(record.expires_at.replace("Z", "+00:00"))
            checks["not_expired"] = now <= exp
        except Exception:
            checks["not_expired"] = False
        if not checks["not_expired"]:
            return self._refuse("expired", checks)

        checks["nonce_fresh"] = self.nonce_ledger.is_fresh(record.nonce)
        if not checks["nonce_fresh"]:
            return self._refuse("nonce_replay", checks)

        checks["admissible"] = self.state.is_admissible(record.permitted_consequence)
        if not checks["admissible"]:
            return self._refuse("inadmissible_transition", checks)

        if not self.nonce_ledger.consume(record.nonce):
            return self._refuse("nonce_replay", checks)
        self.writer.write(snapshot)  # the same snapshot that was hashed
        self.state.apply(record.permitted_consequence)
        return {
            "allowed": True,
            "reason": "mutation_applied",
            "checks": checks,
            "writer_entered": self.writer.entered,
            "mutations": self.writer.mutations,
            "hash_before": self.writer.hash_before,
            "hash_after": self.writer.hash_after,
            "final_state": self.state.state,
            "written_matches_digest": self.writer.hash_after == record.payload_hash,
            "refused_before_entry": False,
        }

    def _refuse(self, reason: str, checks: Dict[str, bool]) -> Dict[str, Any]:
        return {
            "allowed": False,
            "reason": reason,
            "checks": checks,
            "writer_entered": self.writer.entered,
            "mutations": self.writer.mutations,
            "hash_before": self.writer.hash_before,
            "hash_after": self.writer.hash_after,
            "final_state": self.state.state,
            "written_matches_digest": False,
            "refused_before_entry": True,
        }
