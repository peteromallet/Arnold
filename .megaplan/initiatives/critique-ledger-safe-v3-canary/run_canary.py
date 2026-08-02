#!/usr/bin/env python3
"""One finite CL2 planning lifecycle; no retry, resident, or execute surface."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PHASES = ("init", "plan", "critique", "gate", "finalize")
CANARY_ID = "critique-ledger-safe-v3-canary"
PLAN_NAME = "critique-ledger-cl2-planning-canary"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path: Path, payload: dict[str, object]) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    if os.environ.get("MEGAPLAN_ZERO_RECOVERY_CANARY") != "1":
        raise SystemExit("zero-recovery environment flag is required")
    root = Path.cwd().resolve()
    initiative = root / ".megaplan/initiatives/critique-ledger-safe-v3-canary"
    plan_dir = root / ".megaplan/plans" / PLAN_NAME
    if plan_dir.exists():
        raise SystemExit("finite canary plan identity already exists")
    lock_path = initiative / "receipts/single-use-run.lock"
    receipt_dir = initiative / "receipts"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(lock_fd, "w", encoding="utf-8") as lock:
        lock.write(PLAN_NAME + "\n")
        lock.flush()
        os.fsync(lock.fileno())
    idea = initiative / "briefs/cl2-ledger-persistence-and-replay.md"
    north_star = initiative / "NORTHSTAR.md"
    commands = [
        [sys.executable, "-P", "-m", "arnold_pipelines.megaplan", "init", "--project-dir", str(root), "--name", PLAN_NAME, "--auto-approve", "--idea-file", str(idea), "--north-star", str(north_star), "--robustness", "full", "--no-adaptive-critique", "--vendor", "codex", "--phase-model", "plan=codex:gpt-5.6-sol:high", "--phase-model", "critique=codex:gpt-5.6-sol:high", "--phase-model", "gate=codex:gpt-5.6-sol:high", "--phase-model", "finalize=codex:gpt-5.6-sol:high"],
        *[
            [sys.executable, "-P", "-m", "arnold_pipelines.megaplan", phase, "--plan", PLAN_NAME, "--fresh"]
            for phase in PHASES[1:]
        ],
    ]
    started = datetime.now(timezone.utc)
    results = []
    status = "passed"
    failure = None
    expected_states = dict(zip(PHASES, ("initialized", "planned", "critiqued", "gated", "finalized"), strict=True))
    child_env = {
        key: value
        for key, value in os.environ.items()
        if key not in {
            "OPENAI_API_KEY", "DISCORD_TOKEN", "DISCORD_BOT_TOKEN",
            "MEGAPLAN_RESIDENT", "MEGAPLAN_WATCHDOG", "MEGAPLAN_REPAIR",
        }
    }
    child_env.update({
        "MEGAPLAN_ZERO_RECOVERY_CANARY": "1",
        "MEGAPLAN_TRUSTED_CONTAINER": "1",
        "PYTHONNOUSERSITE": "1",
        "HOME": "/root",
        "PYTHONPATH": str(root),
    })
    for phase, argv in zip(PHASES, commands, strict=True):
        phase_index = len(results)
        try:
            completed = subprocess.run(
                argv, cwd=root, env=child_env, text=True, capture_output=True,
                check=False, timeout=3600,
            )
        except subprocess.TimeoutExpired:
            status = "failed"
            failure = {"phase": phase, "reason": "timeout"}
            write_once(
                receipt_dir / f"{phase_index:02d}-{phase}.phase-receipt.json",
                {"schema": "arnold.megaplan.finite_canary_phase_receipt.v1", "phase": phase, "returncode": 124, "state": None, "status": "failed"},
            )
            break
        if completed.returncode != 0:
            results.append({"phase": phase, "returncode": completed.returncode, "state": None})
            status = "failed"
            failure = {"phase": phase, "reason": "nonzero_returncode", "returncode": completed.returncode}
            write_once(
                receipt_dir / f"{phase_index:02d}-{phase}.phase-receipt.json",
                {"schema": "arnold.megaplan.finite_canary_phase_receipt.v1", "phase": phase, "returncode": completed.returncode, "state": None, "status": "failed"},
            )
            break
        state_path = plan_dir / "state.json"
        if not state_path.is_file():
            status = "failed"
            failure = {"phase": phase, "reason": "state_missing"}
            write_once(
                receipt_dir / f"{phase_index:02d}-{phase}.phase-receipt.json",
                {"schema": "arnold.megaplan.finite_canary_phase_receipt.v1", "phase": phase, "returncode": 0, "state": None, "status": "failed"},
            )
            break
        state = json.loads(state_path.read_text(encoding="utf-8"))
        results.append(
            {
                "phase": phase,
                "returncode": completed.returncode,
                "state": state.get("current_state"),
            }
        )
        if state.get("active_step") not in (None, ""):
            status = "failed"
            failure = {"phase": phase, "reason": "active_step_remained"}
            write_once(receipt_dir / f"{phase_index:02d}-{phase}.phase-receipt.json", {"schema": "arnold.megaplan.finite_canary_phase_receipt.v1", "phase": phase, "returncode": 0, "state": state.get("current_state"), "status": "failed", "state_sha256": sha(state_path)})
            break
        if state.get("current_state") != expected_states[phase]:
            status = "failed"
            failure = {"phase": phase, "reason": "unexpected_state"}
            write_once(receipt_dir / f"{phase_index:02d}-{phase}.phase-receipt.json", {"schema": "arnold.megaplan.finite_canary_phase_receipt.v1", "phase": phase, "returncode": 0, "state": state.get("current_state"), "status": "failed", "state_sha256": sha(state_path)})
            break
        if phase == "gate":
            gate_path = plan_dir / "gate.json"
            if not gate_path.is_file() or json.loads(gate_path.read_text(encoding="utf-8")).get("recommendation") != "PROCEED":
                status = "failed"
                failure = {"phase": phase, "reason": "gate_not_proceed"}
                write_once(receipt_dir / f"{phase_index:02d}-{phase}.phase-receipt.json", {"schema": "arnold.megaplan.finite_canary_phase_receipt.v1", "phase": phase, "returncode": 0, "state": state.get("current_state"), "status": "failed", "state_sha256": sha(state_path)})
                break
        if phase == "finalize" and state.get("current_state") != "finalized":
            status = "failed"
            failure = {"phase": phase, "reason": "terminal_not_finalized"}
            write_once(receipt_dir / f"{phase_index:02d}-{phase}.phase-receipt.json", {"schema": "arnold.megaplan.finite_canary_phase_receipt.v1", "phase": phase, "returncode": 0, "state": state.get("current_state"), "status": "failed", "state_sha256": sha(state_path)})
            break
        write_once(
            receipt_dir / f"{phase_index:02d}-{phase}.phase-receipt.json",
            {"schema": "arnold.megaplan.finite_canary_phase_receipt.v1", "phase": phase, "returncode": 0, "state": state.get("current_state"), "status": "passed", "state_sha256": sha(state_path)},
        )
    completed_at = datetime.now(timezone.utc)
    unsigned = {
        "schema": "arnold.megaplan.finite_canary_run_receipt.v1",
        "status": status,
        "canary_id": CANARY_ID,
        "plan_name": PLAN_NAME,
        "phases": list(PHASES),
        "phase_results": results,
        "terminal_state": "finalized" if status == "passed" else "failed",
        "failure": failure,
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "completed_at": completed_at.isoformat().replace("+00:00", "Z"),
        "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True).stdout.strip(),
        "source_tree": subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True, capture_output=True, check=True).stdout.strip(),
        "canary_spec_sha256": sha(initiative / "canary.yaml"),
        "state_sha256": sha(plan_dir / "state.json") if (plan_dir / "state.json").is_file() else None,
    }
    unsigned["receipt_digest"] = hashlib.sha256(canonical(unsigned)).hexdigest()
    receipt_dir.mkdir(parents=True, exist_ok=True)
    destination = receipt_dir / f"{unsigned['receipt_digest']}.run-receipt.json"
    write_once(destination, unsigned)
    print(destination.relative_to(root))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
