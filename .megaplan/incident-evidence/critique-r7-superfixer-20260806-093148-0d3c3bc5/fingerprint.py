#!/usr/bin/env python3
"""Occurrence fingerprint guard for the r7 superfixer backstop.

Covers: launch checkout status/head, chain state, plan state/events, admitted
receipts, leases/fences, and repair queues. Outputs a JSON manifest plus a
combined sha256 to stdout and to <out>.
Read-only. Usage: python3 fingerprint.py <out.json>
"""
import hashlib, json, os, subprocess, sys, datetime

WS = "/workspace/critique-ledger-accountability-v3-r7-launch-20260805/Arnold"
PLAN = WS + "/.megaplan/plans/cl2-wbc-backed-ledger-20260805-2140"
CHAINS = WS + "/.megaplan/plans/.chains"
SESS = "/workspace/.megaplan/cloud-sessions"
RQ = "/workspace/.megaplan/repair-queue"

def sha(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        return f"ERR:{e}"

def git(path, args):
    try:
        r = subprocess.run(["git", "-C", path] + args, capture_output=True, text=True, timeout=30)
        return r.stdout.strip()
    except Exception as e:
        return f"ERR:{e}"

manifest = {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}

# launch checkout status/head
manifest["checkout"] = {
    "head": git(WS, ["rev-parse", "HEAD"]),
    "branch": git(WS, ["branch", "--show-current"]),
    "status_porcelain": git(WS, ["status", "--porcelain"]),
    "status_sha256": hashlib.sha256(git(WS, ["status", "--porcelain"]).encode()).hexdigest(),
    "upstream_ahead_behind": git(WS, ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"]),
}

# chain state
manifest["chain_state"] = {
    "file": sha(CHAINS + "/chain-880bd6e04632.json"),
}
import glob
for p in sorted(glob.glob(CHAINS + "/*.json")):
    manifest["chain_state"][os.path.basename(p)] = sha(p)

# plan artifacts
plan_files = [
    "state.json", "events.ndjson", "phase_result.json", "gate.json", "gate_carry.json",
    "faults.json", "fresh_child_admission.json", "work_ledger.ndjson", "gate_output.json",
    "critique_clearance.json",
]
for f in sorted(glob.glob(PLAN + "/critique_custody_v*.json")):
    plan_files.append(os.path.basename(f))
for f in sorted(glob.glob(PLAN + "/critique_v*.json")):
    plan_files.append(os.path.basename(f))
for f in sorted(glob.glob(PLAN + "/step_receipt_*.json")):
    plan_files.append(os.path.basename(f))
for f in sorted(glob.glob(PLAN + "/evaluator_verdict*.json")):
    plan_files.append(os.path.basename(f))
plan = {}
for f in sorted(set(plan_files)):
    plan[f] = sha(PLAN + "/" + f)
manifest["plan"] = plan

# leases / fences / markers
manifest["leases"] = {
    "liveness_lease": sha(SESS + "/critique-ledger-accountability-v3-r7-launch-20260805.liveness-lease.json"),
    "liveness_fence": sha(SESS + "/critique-ledger-accountability-v3-r7-launch-20260805.liveness-fence.json"),
    "session_marker": sha(SESS + "/critique-ledger-accountability-v3-r7-launch-20260805.json"),
    "custody_lease_state": sha(WS + "/.megaplan/authority/custody/lease:arnold.megaplan.fresh_child_admission.v1:8ef0d95eb34a7a55563cfeb5fd92a066bc8ae386a54ef3bea6d749d546906c74.state.json"),
    "custody_lease_history": sha(WS + "/.megaplan/authority/custody/lease:arnold.megaplan.fresh_child_admission.v1:8ef0d95eb34a7a55563cfeb5fd92a066bc8ae386a54ef3bea6d749d546906c74.history.jsonl"),
    "run_authority_db": sha(WS + "/.megaplan/authority/run-authority.sqlite3"),
    "wbc_db": sha(WS + "/.megaplan/authority/wbc.sqlite3"),
}

# repair queues
def dir_manifest(d):
    out = {}
    for p in sorted(glob.glob(d + "/*")):
        if os.path.isfile(p):
            out[os.path.basename(p)] = sha(p)
    return out
manifest["repair_queue"] = {
    "requests": dir_manifest(RQ + "/requests"),
    "decisions": dir_manifest(RQ + "/decisions"),
    "occurrence_claims": dir_manifest(RQ + "/occurrence-claims"),
    "attempts": dir_manifest(RQ + "/attempts"),
}

combined = hashlib.sha256()
for key in ["checkout", "chain_state", "plan", "leases", "repair_queue"]:
    payload = json.dumps(manifest[key], sort_keys=True).encode()
    combined.update(key.encode())
    combined.update(payload)
manifest["combined_sha256"] = "sha256:" + combined.hexdigest()

out_path = sys.argv[1] if len(sys.argv) > 1 else "fingerprint.json"
with open(out_path, "w") as f:
    json.dump(manifest, f, indent=1, sort_keys=True)
print(manifest["combined_sha256"])
