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
