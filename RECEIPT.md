# Execution Boundary Gateway v0.4.1 — private publication receipt

Date: 2026-10-15
Destination: LalaSkye/execution-boundary-gateway (PRIVATE)

## Hashes at upload
- gateway.py: 9320d1833d81d1b0f4d1bc8330204172513b516424eacb28b08263bb33d8cc17 (byte-for-byte identical to v0.4)
- run_tests.py: e2ca6bb20b5f8c9def4c24051719246a8b90038b5ec317c298dbcb78768ae086 (hard-coded workspace path removed; otherwise unchanged)
- test_results.json: 59cd43b54afd0561116fb8d7dfc79ddabe3853f6d2908c16122c673eafd48978

## Reproduction
From the repository root:
```bash
python3 run_tests.py
```
Observed: pass_count 18, fail_count 0, exit 0.

## Claim ceiling
Bounded, single-process experimental gateway.
Immutable payload snapshot tested.
Duplicate decision ID refused.
Fresh-ID issuance relies on trusted issuer access in this local model.
Concurrency, crash-safe atomicity and production enforcement: NOT PROVED.
T7 bypass remains a separate documented limitation.
No production, concurrent, atomic or universal enforcement claims.
Independent review PENDING.
No licence supplied.
