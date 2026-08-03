#!/usr/bin/env python3
"""Verify the offline built-image smoke from inside the stopped-soon container."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan.chain.spec import (
    _finite_canary_privilege_receipt_is_valid,
)


ROOT = Path("/workspace/Arnold")
PLAN = ROOT / ".megaplan/plans/critique-ledger-cl2-planning-canary"
RECEIPTS = ROOT / ".megaplan/initiatives/critique-ledger-safe-v3-canary/receipts"
PHASES = ["plan", "critique", "gate", "finalize"]


def _strict(path: Path) -> dict[str, object]:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate field: {key}")
            result[key] = value
        return result

    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates
    )
    if not isinstance(value, dict):
        raise ValueError(f"not an object: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    run_receipts = list(RECEIPTS.glob("*.run-receipt.json"))
    if len(run_receipts) != 1:
        raise SystemExit("offline smoke did not produce exactly one run receipt")
    run = _strict(run_receipts[0])
    if (
        run.get("status") != "passed"
        or run.get("terminal_state") != "finalized"
        or [item.get("phase") for item in run.get("phase_results", [])]
        != ["init", *PHASES]
        or [item.get("returncode") for item in run.get("phase_results", [])]
        != [0, 0, 0, 0, 0]
    ):
        raise SystemExit("offline smoke lifecycle was not an exact pass")
    dispatches = run.get("dispatches")
    if not isinstance(dispatches, list) or len(dispatches) != 8:
        raise SystemExit("offline smoke did not produce four dispatch pairs")
    terminals = [item for item in dispatches if item.get("event") == "terminal"]
    if (
        [item.get("phase") for item in terminals] != PHASES
        or any(
            item.get("model_evidence") != "codex_cli_turn_context" for item in terminals
        )
        or any(item.get("attempt") != 1 for item in terminals)
    ):
        raise SystemExit("offline smoke dispatch evidence drifted")
    privilege_hashes: list[str] = []
    for phase in PHASES:
        path = PLAN / f".zero-recovery-{phase}-privilege-receipt.json"
        payload = _strict(path)
        if not _finite_canary_privilege_receipt_is_valid(
            payload, phase=phase, plan_dir=PLAN
        ):
            raise SystemExit(f"offline smoke privilege receipt invalid: {phase}")
        privilege_hashes.append(_sha(path))
    remaining = subprocess.run(
        ["/usr/bin/pgrep", "-u", "65532"], capture_output=True, check=False
    )
    if remaining.returncode != 1:
        raise SystemExit("offline smoke left a finite-model process")
    auth = Path("/root/.codex/auth.json")
    config = Path("/root/.codex/config.toml")
    for path in (auth, config):
        item = path.lstat()
        if item.st_uid != 0 or item.st_gid != 0 or item.st_mode & 0o077:
            raise SystemExit("offline smoke dummy auth custody drifted")
    receipt = {
        "schema": "arnold.megaplan.zero_recovery_offline_structural_smoke.v1",
        "status": "passed",
        "evidence_scope": "offline_structural_only_not_model_provider_proof",
        "network": "none",
        "phases": ["init", *PHASES],
        "model_uid": 65532,
        "model_gid": 65532,
        "run_receipt_sha256": _sha(run_receipts[0]),
        "privilege_receipt_sha256": privilege_hashes,
        "source_commit": run.get("source_commit"),
        "source_tree": run.get("source_tree"),
        "production_image_id": os.environ.get("STRUCTURAL_SMOKE_PRODUCTION_IMAGE_ID"),
        "derived_image_id": os.environ.get("STRUCTURAL_SMOKE_DERIVED_IMAGE_ID"),
    }
    receipt["receipt_digest"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
