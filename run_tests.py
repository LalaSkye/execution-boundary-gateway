#!/usr/bin/env python3
"""
v0.4.1-candidate test runner.
Gateway.py is an unmodified byte-for-byte copy of v0.4.
Actor-mismatch test restored.
Mutation claims are not manufactured; coverage is recorded as not executed.
Runner exits non-zero if any required test fails.
"""

import json
import sys

from gateway import (
    ControlledClock, Issuer, NonceLedger, StateStore, Writer, AuthorisationRecord, Proposal, Gateway, sha256
)

INITIAL = b"initial"
INITIAL_HASH = sha256(INITIAL)
PAYLOAD = b"exact payload"

def make_base():
    clock = ControlledClock("2026-10-15T22:00:00Z")
    issuer = Issuer()
    ledger = NonceLedger()
    state = StateStore("PENDING")
    writer = Writer(INITIAL)
    gate = Gateway(issuer, ledger, state, clock, writer)
    return clock, issuer, ledger, state, writer, gate

def issue(issuer, **kwargs):
    defaults = dict(decision_id="d1", payload=PAYLOAD, actor="actor1", action="write",
                    scope="scope1", target="target1", environment="env1",
                    expires="2027-01-01T00:00:00Z", nonce="n1", consequence="APPROVED")
    defaults.update(kwargs)
    rec = AuthorisationRecord(
        decision_id=defaults["decision_id"],
        payload_hash=sha256(defaults["payload"]),
        actor_id=defaults["actor"],
        action=defaults["action"],
        scope=defaults["scope"],
        target=defaults["target"],
        environment=defaults["environment"],
        expires_at=defaults["expires"],
        nonce=defaults["nonce"],
        permitted_consequence=defaults["consequence"],
    )
    ok = issuer.issue(rec)
    return rec, ok

def denied_ok(res, writer, expected_reason):
    return (
        not res["allowed"]
        and res["reason"] == expected_reason
        and writer.entered == 0
        and writer.mutations == 0
        and writer.unchanged(INITIAL_HASH)
        and res["refused_before_entry"]
    )

def allowed_ok(res, writer):
    return (
        res["allowed"]
        and res["reason"] == "mutation_applied"
        and writer.entered == 1
        and writer.mutations == 1
        and writer.bytes == PAYLOAD
        and res.get("written_matches_digest") is True
        and res["final_state"] == "APPROVED"
        and not res["refused_before_entry"]
    )

results = []

# CONTROL
clock, issuer, ledger, state, writer, gate = make_base()
rec, _ = issue(issuer)
proposal = Proposal(rec.decision_id, PAYLOAD, rec.actor_id, rec.action, rec.scope, rec.target, rec.environment, rec.permitted_consequence)
res = gate.decide_and_execute(proposal)
results.append({"case": "CONTROL", "verdict": "PASS" if allowed_ok(res, writer) else "FAIL"})

# Actor mismatch (restored)
clock, issuer, ledger, state, writer, gate = make_base()
rec, _ = issue(issuer)
proposal = Proposal(rec.decision_id, PAYLOAD, "wrong-actor", rec.action, rec.scope, rec.target, rec.environment, rec.permitted_consequence)
res = gate.decide_and_execute(proposal)
results.append({"case": "ACTOR_MISMATCH", "verdict": "PASS" if denied_ok(res, writer, "binding_mismatch") else "FAIL", "reason": res["reason"], "entered": writer.entered, "mutations": writer.mutations, "target_unchanged": writer.unchanged(INITIAL_HASH)})

# Immutable snapshot
class Hostile(bytes):
    pass

clock, issuer, ledger, state, writer, gate = make_base()
rec, _ = issue(issuer)
proposal = Proposal(rec.decision_id, Hostile(PAYLOAD), rec.actor_id, rec.action, rec.scope, rec.target, rec.environment, rec.permitted_consequence)
res = gate.decide_and_execute(proposal)
results.append({"case": "IMMUTABLE_SNAPSHOT", "verdict": "PASS" if allowed_ok(res, writer) and writer.bytes == PAYLOAD else "FAIL"})

# Post-validation mutation
clock, issuer, ledger, state, writer, gate = make_base()
rec, _ = issue(issuer)
ba = bytearray(PAYLOAD)
proposal = Proposal(rec.decision_id, ba, rec.actor_id, rec.action, rec.scope, rec.target, rec.environment, rec.permitted_consequence)
res = gate.decide_and_execute(proposal)
ba[:] = b"changed after"
results.append({"case": "POST_VALIDATION_MUTATION", "verdict": "PASS" if allowed_ok(res, writer) and writer.bytes == PAYLOAD else "FAIL"})

# Duplicate refusal
clock, issuer, ledger, state, writer, gate = make_base()
_, ok1 = issue(issuer)
_, ok2 = issue(issuer)
results.append({"case": "REFUSE_DUPLICATE", "verdict": "PASS" if ok1 and not ok2 else "FAIL"})

# Forged issuance (duplicate ID)
clock, issuer, ledger, state, writer, gate = make_base()
rec, ok = issue(issuer)
forged = AuthorisationRecord(rec.decision_id, sha256(b"forged"), "actor1", "write", "scope1", "target1", "env1", "2027-01-01T00:00:00Z", "n1", "APPROVED")
ok_forged = issuer.issue(forged)
results.append({"case": "FORGED_ISSUANCE", "verdict": "PASS" if ok and not ok_forged else "FAIL"})

# Withdrawn
clock, issuer, ledger, state, writer, gate = make_base()
rec, _ = issue(issuer)
issuer.withdraw(rec.decision_id)
proposal = Proposal(rec.decision_id, PAYLOAD, rec.actor_id, rec.action, rec.scope, rec.target, rec.environment, rec.permitted_consequence)
res = gate.decide_and_execute(proposal)
results.append({"case": "WITHDRAWN_REUSE", "verdict": "PASS" if denied_ok(res, writer, "record_missing_or_withdrawn") else "FAIL"})

# Other mismatches
for name, field, bad in [
    ("ACTION_MISMATCH", "action", "other-action"),
    ("SCOPE_MISMATCH", "scope", "other-scope"),
    ("TARGET_MISMATCH", "target", "other-target"),
    ("ENVIRONMENT_MISMATCH", "environment", "other-env"),
    ("CONSEQUENCE_MISMATCH", "requested_state", "REJECTED"),
]:
    clock, issuer, ledger, state, writer, gate = make_base()
    rec, _ = issue(issuer)
    kwargs = dict(decision_id=rec.decision_id, payload=PAYLOAD, actor_id=rec.actor_id, action=rec.action,
                  scope=rec.scope, target=rec.target, environment=rec.environment, requested_state=rec.permitted_consequence)
    kwargs[field] = bad
    proposal = Proposal(**kwargs)
    res = gate.decide_and_execute(proposal)
    results.append({"case": name, "verdict": "PASS" if denied_ok(res, writer, "binding_mismatch") else "FAIL"})

# Forged / substitution / T4 / T5 / T6 / retry
clock, issuer, ledger, state, writer, gate = make_base()
rec, _ = issue(issuer)
proposal = Proposal(rec.decision_id, b"forged payload", rec.actor_id, rec.action, rec.scope, rec.target, rec.environment, rec.permitted_consequence)
res = gate.decide_and_execute(proposal)
results.append({"case": "FORGED_RECORD", "verdict": "PASS" if denied_ok(res, writer, "binding_mismatch") else "FAIL"})

clock, issuer, ledger, state, writer, gate = make_base()
rec, _ = issue(issuer)
proposal = Proposal(rec.decision_id, b"substituted", rec.actor_id, rec.action, rec.scope, rec.target, rec.environment, rec.permitted_consequence)
res = gate.decide_and_execute(proposal)
results.append({"case": "SUBSTITUTION", "verdict": "PASS" if denied_ok(res, writer, "binding_mismatch") else "FAIL"})

clock, issuer, ledger, state, writer, gate = make_base()
rec, _ = issue(issuer)
clock.advance("2028-01-01T00:00:00Z")
proposal = Proposal(rec.decision_id, PAYLOAD, rec.actor_id, rec.action, rec.scope, rec.target, rec.environment, rec.permitted_consequence)
res = gate.decide_and_execute(proposal)
results.append({"case": "T4", "verdict": "PASS" if denied_ok(res, writer, "expired") else "FAIL"})

clock, issuer, ledger, state, writer, gate = make_base()
rec, _ = issue(issuer)
proposal = Proposal(rec.decision_id, PAYLOAD, rec.actor_id, rec.action, rec.scope, rec.target, rec.environment, rec.permitted_consequence)
res1 = gate.decide_and_execute(proposal)
res2 = gate.decide_and_execute(proposal)
results.append({"case": "T5", "verdict": "PASS" if allowed_ok(res1, writer) and not res2["allowed"] and res2["reason"] == "nonce_replay" else "FAIL"})

clock, issuer, ledger, state, writer, gate = make_base()
rec, _ = issue(issuer)
state.state = "PAID"
proposal = Proposal(rec.decision_id, PAYLOAD, rec.actor_id, rec.action, rec.scope, rec.target, rec.environment, rec.permitted_consequence)
res = gate.decide_and_execute(proposal)
results.append({"case": "T6", "verdict": "PASS" if denied_ok(res, writer, "inadmissible_transition") else "FAIL"})

clock, issuer, ledger, state, writer, gate = make_base()
rec, _ = issue(issuer)
state.state = "PAID"
proposal = Proposal(rec.decision_id, PAYLOAD, rec.actor_id, rec.action, rec.scope, rec.target, rec.environment, rec.permitted_consequence)
res_deny = gate.decide_and_execute(proposal)
state.state = "PENDING"
res_retry = gate.decide_and_execute(proposal)
results.append({"case": "RETRY_AFTER_DENIAL", "verdict": "PASS" if (not res_deny["allowed"] and res_retry["allowed"] and writer.entered == 1) else "FAIL"})

# Unsafe comparator (separate)
unsafe = Writer(INITIAL)
unsafe.write(PAYLOAD)
results.append({"case": "UNSAFE_COMPARATOR", "entered": unsafe.entered, "note": "skips gate; not a gateway result"})

# T7
bypass = Writer(INITIAL)
bypass.write(PAYLOAD)
results.append({"case": "T7_BYPASS", "entered": bypass.entered, "note": "separate documented limitation"})

pass_count = sum(1 for r in results if r.get("verdict") == "PASS")
fail_count = sum(1 for r in results if r.get("verdict") == "FAIL")

output = {
    "results": results,
    "mutation_coverage": "not executed",
    "pass_count": pass_count,
    "fail_count": fail_count,
    "issuer_note": "Duplicate-ID substitution is blocked. Fresh-ID issuance still relies on trusted issuer access in this local model."
}
print(json.dumps(output, indent=2))

if fail_count > 0:
    sys.exit(1)
sys.exit(0)
