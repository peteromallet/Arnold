"""Acceptance gate check for cloud wrapper restart / relaunch paths.

Provides :func:`check_wrapper_acceptance_gate` so bash wrappers can verify
that a chain's acceptance state supports continuing past an acceptance
milestone (e.g. M5A) before they restart or relaunch chain execution.

In fail-closed (atomic/enforce) mode a chain whose declared successors
require acceptance MUST carry a validated acceptance receipt for its final
milestone.  When the receipt is absent or unsupported the wrapper must keep
the successor milestone pending and emit a typed blocker event instead of
blindly restarting.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.chain.spec import ChainSpec, ChainState, load_chain_state, load_spec
from arnold_pipelines.megaplan.orchestration.completion_contract import (
    PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
    is_fail_closed_mode,
    normalize_contract_mode,
)

CALLER_KINDS = frozenset(
    {
        "chain_wrapper",
        "repair_loop",
        "meta_repair",
        "watchdog",
        "cloud_wrapper",  # generic fallback
    }
)

BLOCKER_KIND_BY_CALLER: dict[str, str] = {
    "chain_wrapper": "cloud_chain_wrapper_restart_acceptance_gate_closed",
    "repair_loop": "cloud_repair_loop_relaunch_acceptance_gate_closed",
    "meta_repair": "cloud_meta_repair_relaunch_acceptance_gate_closed",
    "watchdog": "cloud_watchdog_dispatch_acceptance_gate_closed",
    "cloud_wrapper": "cloud_wrapper_acceptance_gate_closed",
}


def _load_spec(spec_path: Path) -> ChainSpec | None:
    """Load a chain spec from *spec_path* (YAML)."""
    try:
        return load_spec(spec_path)
    except Exception:
        return None


def _resolve_state_path(
    spec_path: Path,
    *,
    workspace: Path | None,
    explicit_state_path: Path | None,
) -> Path | None:
    """Find the chain-state file for *spec_path*."""
    import hashlib

    if explicit_state_path is not None and explicit_state_path.exists():
        return explicit_state_path

    root = workspace or spec_path.parent
    try:
        resolved = spec_path.resolve()
    except OSError:
        resolved = spec_path
    digest = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:12]

    candidates: list[Path] = [
        root / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json",
        root / ".megaplan" / "plans" / ".chains" / f"{resolved.stem}-{digest}.json",
        resolved.parent / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json",
        resolved.parent / ".megaplan" / "plans" / ".chains" / f"{resolved.stem}-{digest}.json",
        resolved.with_name("chain_state.json"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def check_wrapper_acceptance_gate(
    spec_path: str,
    *,
    workspace: str | None = None,
    chain_state_path: str | None = None,
    caller_kind: str = "cloud_wrapper",
) -> dict[str, Any]:
    """Check the acceptance gate before a cloud wrapper restarts / relaunches.

    Parameters
    ----------
    spec_path:
        Path to the chain spec (YAML).
    workspace:
        Project workspace directory (used to locate chain-state when
        *chain_state_path* is not provided).
    chain_state_path:
        Explicit path to the persisted chain-state JSON.
    caller_kind:
        One of ``chain_wrapper``, ``repair_loop``, ``meta_repair``,
        ``watchdog``, or ``cloud_wrapper`` (generic fallback).

    Returns
    -------
    dict
        ``{"gate_open": true, "reason": "..."}`` when the wrapper may proceed,
        or ``{"gate_open": false, "reason": "...", "blocker_event": {...}}``
        when the gate is closed and the wrapper must NOT restart / relaunch.
    """
    spec = Path(spec_path)
    if not spec.exists():
        return {"gate_open": False, "reason": f"spec not found: {spec_path}"}

    spec_obj = _load_spec(spec)
    if spec_obj is None:
        # If we can't read the spec, we can't determine whether successors
        # require acceptance — err on the side of allowing the restart.
        return {
            "gate_open": True,
            "reason": f"spec unreadable: {spec_path}; gate open by default",
        }

    # ── resolve chain state ───────────────────────────────────────────
    ws = Path(workspace) if workspace else None
    explicit = Path(chain_state_path) if chain_state_path else None
    state_path = _resolve_state_path(
        spec, workspace=ws, explicit_state_path=explicit
    )
    if state_path is None:
        # No persisted state yet — chain hasn't run, gate is open.
        return {"gate_open": True, "reason": "no chain state yet"}

    try:
        state = load_chain_state(state_path)
    except Exception:
        # If the state can't be loaded (e.g. because of atomic-mode
        # validation rejecting completed records without acceptance
        # receipts), the Python-level gate inside run_chain will handle
        # it.  The wrapper should allow the restart.
        return {"gate_open": True, "reason": "chain state unreadable; gate open"}

    # ── check mode ─────────────────────────────────────────────────────
    mode = normalize_contract_mode(state.completion_contract_mode)
    if not is_fail_closed_mode(mode):
        return {
            "gate_open": True,
            "reason": f"mode={mode}; gate always open in non-fail-closed mode",
        }

    # ── check successors ───────────────────────────────────────────────
    successors = getattr(spec_obj, "successors", None) or []
    if not successors:
        return {"gate_open": True, "reason": "no declared successors"}

    any_require = any(
        getattr(s, "require_accepted_transaction", True) for s in successors
    )
    if not any_require:
        return {
            "gate_open": True,
            "reason": "no successor requires acceptance",
        }

    # ── check for completion + receipt ─────────────────────────────────
    # The gate is only meaningful when the chain has actually completed at
    # least its final milestone.  If the chain is still in-progress the
    # restart is fine — the Python-level gate inside run_chain will handle it.
    milestones = getattr(spec_obj, "milestones", None) or []
    if not milestones:
        return {"gate_open": True, "reason": "no milestones declared"}

    # Only apply the gate when the chain has advanced past or to the final
    # milestone AND the final milestone's label appears in completed records.
    final_milestone = milestones[-1]
    completed = getattr(state, "completed", None) or []
    completed_labels = {
        str(item.get("label") or item.get("plan") or "").strip()
        for item in completed
        if isinstance(item, dict)
    }

    # If the final milestone isn't completed yet, we aren't at the
    # successor boundary — the gate doesn't apply.
    if final_milestone.label not in completed_labels:
        return {
            "gate_open": True,
            "reason": (
                f"final milestone {final_milestone.label!r} not yet completed; "
                f"successor boundary not reached"
            ),
        }

    has_receipt = state.has_acceptance_receipt(final_milestone.label)
    if has_receipt:
        return {
            "gate_open": True,
            "reason": (
                f"acceptance receipt present for {final_milestone.label!r}; "
                f"gate open"
            ),
        }

    # ── Gate is closed — build typed blocker event ────────────────────
    blocker_kind = BLOCKER_KIND_BY_CALLER.get(
        caller_kind, BLOCKER_KIND_BY_CALLER["cloud_wrapper"]
    )

    blocker_event: dict[str, Any] = {
        "kind": blocker_kind,
        "predicate_kind": PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
        "evidence_kind": f"cloud_wrapper_{caller_kind}",
        "summary": (
            f"cloud wrapper {caller_kind!r} blocked: chain completed "
            f"{final_milestone.label!r} but no validated acceptance receipt; "
            f"declared successors require acceptance evidence before "
            f"restart / relaunch"
        ),
        "details": {
            "milestone_label": final_milestone.label,
            "completion_contract_mode": mode,
            "successor_count": len(successors),
            "caller_kind": caller_kind,
            "spec_path": str(spec),
            "chain_state_path": str(state_path) if state_path else None,
        },
    }

    return {
        "gate_open": False,
        "reason": (
            f"acceptance gate closed for {final_milestone.label!r}: "
            f"no acceptance receipt"
        ),
        "blocker_event": blocker_event,
    }


# ── CLI entry point for bash wrappers ──────────────────────────────────
def _main() -> None:
    """CLI: ``python3 -m arnold_pipelines.megaplan.cloud.wrapper_acceptance_gate ...``

    Expects JSON on stdin with keys: spec_path, workspace (optional),
    chain_state_path (optional), caller_kind (optional, default "cloud_wrapper").
    Writes JSON result to stdout.
    Exits 0 when gate is open, 1 when gate is closed.
    """
    raw = sys.stdin.read()
    try:
        args = json.loads(raw)
    except json.JSONDecodeError:
        print(json.dumps({"gate_open": False, "reason": "invalid JSON input"}))
        sys.exit(2)

    result = check_wrapper_acceptance_gate(
        spec_path=args.get("spec_path", ""),
        workspace=args.get("workspace"),
        chain_state_path=args.get("chain_state_path"),
        caller_kind=args.get("caller_kind", "cloud_wrapper"),
    )
    print(json.dumps(result, sort_keys=True))
    sys.exit(0 if result.get("gate_open") else 1)


if __name__ == "__main__":
    _main()
