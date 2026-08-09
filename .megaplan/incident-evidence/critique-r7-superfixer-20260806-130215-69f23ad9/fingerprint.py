#!/usr/bin/env python
"""Authoritative fingerprint for the R7 superfixer occurrence.

Covers: launch checkout status/head, pinned runtime git identity, chain state,
plan state/events/receipts, leases, fences, repair queues, incident evidence.
Outputs a canonical sha256 over all collected facts.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path("/workspace")
WS = ROOT / "critique-ledger-accountability-v3-r7-launch-20260805/Arnold"
RUNTIME = ROOT / "runtime-candidates/arnold-r7-fresh-child-20260805"
PLAN = WS / ".megaplan/plans/cl2-wbc-backed-ledger-20260805-2140"
CHAIN = WS / ".megaplan/plans/.chains/chain-880bd6e04632.json"
MARKER = ROOT / ".megaplan/cloud-sessions/critique-ledger-accountability-v3-r7-launch-20260805.json"
SESS = ROOT / ".megaplan/cloud-sessions"

def sh(cmd, cwd=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
        return {"rc": r.returncode, "out": r.stdout[:2000], "err": r.stderr[:500]}
    except Exception as e:
        return {"rc": -1, "out": "", "err": str(e)[:500]}

def sha256_file(p):
    try:
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    except Exception:
        return ""

facts = {
    "generated_at_utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip(),
    "launch_checkout": {
        "head": sh(["git", "rev-parse", "HEAD"], cwd=WS),
        "branch": sh(["git", "branch", "--show-current"], cwd=WS),
        "status_porcelain": sh(["git", "status", "--porcelain=v1", "--untracked-files=no"], cwd=WS),
        "status_sha256": sha256_file(str(WS / ".git/HEAD")),
    },
    "runtime": {
        "head": sh(["git", "rev-parse", "HEAD"], cwd=RUNTIME),
        "branch": sh(["git", "branch", "--show-current"], cwd=RUNTIME),
        "status_porcelain": sh(["git", "status", "--porcelain=v1", "--untracked-files=no"], cwd=RUNTIME),
    },
    "chain_state": {
        "path": str(CHAIN),
        "sha256": sha256_file(CHAIN),
        "mtime": sh(["stat", "-c", "%y", str(CHAIN)]),
    },
    "plan_state": {
        "path": str(PLAN / "state.json"),
        "sha256": sha256_file(str(PLAN / "state.json")),
        "mtime": sh(["stat", "-c", "%y", str(PLAN / "state.json")]),
    },
    "plan_artifacts": {
        "faults.json": sha256_file(str(PLAN / "faults.json")),
        "gate.json": sha256_file(str(PLAN / "gate.json")),
        "gate_carry.json": sha256_file(str(PLAN / "gate_carry.json")),
        "critique_custody_v5.json": sha256_file(str(PLAN / "critique_custody_v5.json")),
        "events.ndjson": sha256_file(str(PLAN / "events.ndjson")),
        "events_seq": (PLAN / ".events.seq").read_text() if (PLAN / ".events.seq").exists() else "",
    },
    "session_marker": {
        "path": str(MARKER),
        "sha256": sha256_file(MARKER),
        "mtime": sh(["stat", "-c", "%y", str(MARKER)]),
    },
    "liveness": {
        "lease": sha256_file(str(SESS / "critique-ledger-accountability-v3-r7-launch-20260805.liveness-lease.json")),
        "lease_mtime": sh(["stat", "-c", "%y", str(SESS / "critique-ledger-accountability-v3-r7-launch-20260805.liveness-lease.json")]),
        "fence": sha256_file(str(SESS / "critique-ledger-accountability-v3-r7-launch-20260805.liveness-fence.json")),
    },
    "repair_queues": {
        "requests": [str(p) for p in (WS / ".megaplan/repair-queue").glob("**/*") if p.is_file()] if (WS / ".megaplan/repair-queue").exists() else [],
    },
    "processes": sh(["ps", "-eo", "pid,args"], cwd="/"),
}

payload = json.dumps(facts, sort_keys=True, indent=2)
digest = hashlib.sha256(payload.encode()).hexdigest()
out = {"schema": "arnold.superfixer.observation_fingerprint.v1", "sha256": digest, "facts": facts}
print(json.dumps(out, indent=2))
