# Execution Boundary Gateway — v0.4.1 candidate

A small, **experimental Python gateway** for testing a particular question:

> Before a write happens, does the proposed action still match the authorisation for those bytes, that actor, that operation and that consequence?

This repository is a **bounded, single-process, in-memory demonstration**, not a production security control.

## What it does

On the instrumented gateway path, the candidate:

- Captures one immutable `bytes` snapshot and uses that same snapshot for hashing and writing.
- Retrieves an active authorisation record from a trusted in-memory issuer.
- Compares the payload digest, actor identifier, action, scope, target, environment and permitted consequence.
- Checks expiry, nonce replay and whether the requested state transition is currently admissible.
- Refuses a failed check before writer entry; after checks pass, consumes the nonce and performs the modelled write and state transition.
- Refuses issuance that reuses an existing decision ID, including one subsequently withdrawn.

The actor and destination fields are **compared labels**, not authenticated real-world identities or independently verified external destinations.

## Run the tests

From the repository root, with Python 3:

```bash
python3 run_tests.py
```

The included `test_results.json` records **18 PASS / 0 FAIL** for the supplied suite. The runner returns a non-zero exit code if a required test fails. Re-run the tests to obtain results in your own environment.

The suite includes normal execution, payload and context mismatches, withdrawn or expired approval, nonce replay, inadmissible state, duplicate-ID refusal, and a post-write mutation attempt on the caller's buffer.

**Mutation testing is not included as executed evidence.** `UNSAFE_COMPARATOR` and `T7_BYPASS` illustrate bypass paths and are not counted as gateway passes. Independent review of this released candidate remains **PENDING**.

## Files

- `gateway.py` — experimental gateway, issuer, nonce ledger, state and writer
- `run_tests.py` — portable local test runner
- `test_results.json` — recorded test output
- `RECEIPT.md` — source hashes, observed results and claim limits at upload

The receipt records the earlier **private upload**. The repository was subsequently made **public** without changing those four files.

## Limits — read before relying on it

This example **does not prove**:

- Authenticated caller identity or control of access to the issuer (someone with issuer access can issue a fresh decision ID).
- Safety under concurrency or changes between the final check and the write.
- Crash-safe atomicity, durable replay records or recovery.
- That every possible write goes through the gateway: calling the writer directly bypasses it (T7).
- Production suitability, universal enforcement or a cryptographic authorisation scheme.

The writer and state store are local test objects; this is not an integrated deployment.

## Licence

**No licence has been supplied.** Public source visibility does not itself grant permission to reuse, modify or redistribute the code.
