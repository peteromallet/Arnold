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

from arnold_pipelines.megaplan.chain.spec import ChainSpec, ChainState, load_spec
from arnold_pipelines.megaplan.custody.process_adapter_wbc import begin_process_adapter_attempt
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

ACCEPTANCE_GATE_SCHEMA = "arnold.megaplan.cloud.wrapper_acceptance_gate.v1"
ACCEPTANCE_GATE_SCHEMA_VERSION = 1
_ACCEPTANCE_GATE_REQUIRED_FIELDS = frozenset(
    {"schema", "schema_version", "decision", "gate_open", "reason", "identity"}
)
_ACCEPTANCE_GATE_OPTIONAL_FIELDS = frozenset({"blocker_event"})
_ACCEPTANCE_IDENTITY_FIELDS = frozenset(
    {"spec_path", "workspace", "session", "plan_name"}
)

BLOCKER_KIND_BY_CALLER: dict[str, str] = {
    "chain_wrapper": "cloud_chain_wrapper_restart_acceptance_gate_closed",
    "repair_loop": "cloud_repair_loop_relaunch_acceptance_gate_closed",
    "meta_repair": "cloud_meta_repair_relaunch_acceptance_gate_closed",
    "watchdog": "cloud_watchdog_dispatch_acceptance_gate_closed",
    "cloud_wrapper": "cloud_wrapper_acceptance_gate_closed",
}


class AcceptanceGateDecisionError(ValueError):
    """A wrapper acceptance decision was not safe to consume."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


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


def _load_resolved_chain_state(state_path: Path) -> ChainState:
    """Load an already-resolved chain-state JSON file."""

    raw = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("chain state must be a JSON object")
    return ChainState.from_dict(raw)


def _resolved_path(path: Path) -> str:
    """Resolve a path for identity comparison without requiring it to exist."""
    try:
        return str(path.expanduser().resolve(strict=False))
    except OSError:
        return str(path.expanduser())


def _decision_identity(
    spec: Path,
    *,
    workspace: Path | None,
    state: ChainState | None = None,
    expected_session: str | None = None,
    expected_plan_name: str | None = None,
) -> dict[str, Any]:
    """Build the identity attached to every canonical gate decision."""
    resolved_workspace = workspace or spec.parent
    state_session = getattr(state, "chain_session", None) if state else None
    state_plan = getattr(state, "current_plan_name", None) if state else None
    session = expected_session or state_session or "chain"
    plan_name = expected_plan_name if expected_plan_name is not None else state_plan
    return {
        "spec_path": _resolved_path(spec),
        "workspace": _resolved_path(resolved_workspace),
        "session": str(session),
        "plan_name": str(plan_name) if plan_name is not None else None,
    }


def validate_wrapper_acceptance_decision(
    value: str | bytes | dict[str, Any],
    *,
    spec_path: str,
    workspace: str | None = None,
    chain_state_path: str | None = None,
    expected_session: str | None = None,
    expected_plan_name: str | None = None,
    require_open: bool = True,
) -> dict[str, Any]:
    """Validate one serialized canonical decision at a process boundary.

    This is deliberately the only JSON decision parser used by production
    launch wrappers.  A decision is consumable only when its schema, required
    fields, open/closed vocabulary, and spec/workspace/session/plan identity
    all match the intended launch.
    """
    if isinstance(value, (str, bytes)):
        try:
            decoded = json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise AcceptanceGateDecisionError(
                "acceptance_gate_malformed_json",
                "acceptance helper returned malformed JSON; rerun the helper and inspect its stderr",
            ) from exc
    else:
        decoded = value
    if not isinstance(decoded, dict):
        raise AcceptanceGateDecisionError(
            "acceptance_gate_schema_invalid",
            "acceptance helper decision must be a JSON object",
        )

    unknown_fields = sorted(
        set(decoded) - _ACCEPTANCE_GATE_REQUIRED_FIELDS - _ACCEPTANCE_GATE_OPTIONAL_FIELDS
    )
    if unknown_fields:
        raise AcceptanceGateDecisionError(
            "acceptance_gate_schema_invalid",
            f"acceptance helper decision has unknown field {unknown_fields[0]!r}",
        )
    missing_fields = sorted(_ACCEPTANCE_GATE_REQUIRED_FIELDS - set(decoded))
    if missing_fields:
        raise AcceptanceGateDecisionError(
            "acceptance_gate_schema_invalid",
            f"acceptance helper decision is missing required field {missing_fields[0]!r}",
        )
    if decoded.get("schema") != ACCEPTANCE_GATE_SCHEMA:
        raise AcceptanceGateDecisionError(
            "acceptance_gate_schema_unknown",
            f"acceptance helper returned unknown schema {decoded.get('schema')!r}",
        )
    if decoded.get("schema_version") != ACCEPTANCE_GATE_SCHEMA_VERSION:
        raise AcceptanceGateDecisionError(
            "acceptance_gate_schema_unknown",
            f"acceptance helper returned unsupported schema version {decoded.get('schema_version')!r}",
        )
    decision = decoded.get("decision")
    gate_open = decoded.get("gate_open")
    if decision not in {"open", "closed"} or not isinstance(gate_open, bool):
        raise AcceptanceGateDecisionError(
            "acceptance_gate_schema_invalid",
            "acceptance helper decision must contain decision=open|closed and boolean gate_open",
        )
    if gate_open != (decision == "open"):
        raise AcceptanceGateDecisionError(
            "acceptance_gate_schema_invalid",
            "acceptance helper decision and gate_open disagree",
        )
    reason = decoded.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise AcceptanceGateDecisionError(
            "acceptance_gate_schema_invalid",
            "acceptance helper decision requires a non-empty actionable reason",
        )

    identity = decoded.get("identity")
    if not isinstance(identity, dict):
        raise AcceptanceGateDecisionError(
            "acceptance_gate_identity_mismatch",
            "acceptance helper decision requires an identity object",
        )
    if set(identity) != _ACCEPTANCE_IDENTITY_FIELDS:
        missing_identity = sorted(_ACCEPTANCE_IDENTITY_FIELDS - set(identity))
        if missing_identity:
            detail = f"missing identity field {missing_identity[0]!r}"
        else:
            detail = f"unknown identity field {sorted(set(identity) - _ACCEPTANCE_IDENTITY_FIELDS)[0]!r}"
        raise AcceptanceGateDecisionError("acceptance_gate_identity_mismatch", detail)
    for field_name in ("spec_path", "workspace", "session"):
        if not isinstance(identity.get(field_name), str) or not identity[field_name].strip():
            raise AcceptanceGateDecisionError(
                "acceptance_gate_identity_mismatch",
                f"identity.{field_name} must be a non-empty string",
            )
    if identity.get("plan_name") is not None and (
        not isinstance(identity.get("plan_name"), str) or not identity["plan_name"].strip()
    ):
        raise AcceptanceGateDecisionError(
            "acceptance_gate_identity_mismatch",
            "identity.plan_name must be a non-empty string or null",
        )

    expected_spec = Path(spec_path)
    expected_workspace = Path(workspace) if workspace else None
    expected_state: ChainState | None = None
    expected_state_path = _resolve_state_path(
        expected_spec,
        workspace=expected_workspace,
        explicit_state_path=Path(chain_state_path) if chain_state_path else None,
    )
    if expected_state_path is not None:
        try:
            expected_state = _load_resolved_chain_state(expected_state_path)
        except Exception:
            # A closed decision may correctly describe an unreadable state;
            # the helper's own identity remains the authoritative evidence.
            expected_state = None
    expected_identity = _decision_identity(
        expected_spec,
        workspace=expected_workspace,
        state=expected_state,
        expected_session=expected_session,
        expected_plan_name=expected_plan_name,
    )
    for field_name, expected in expected_identity.items():
        if identity.get(field_name) != expected:
            raise AcceptanceGateDecisionError(
                "acceptance_gate_identity_mismatch",
                f"identity.{field_name} does not match the intended launch "
                f"(expected {expected!r}, got {identity.get(field_name)!r})",
            )
    if require_open and not gate_open:
        raise AcceptanceGateDecisionError(
            "acceptance_gate_closed",
            f"acceptance gate is explicitly closed: {reason.strip()}",
        )
    return decoded


def check_wrapper_acceptance_gate(
    spec_path: str,
    *,
    workspace: str | None = None,
    chain_state_path: str | None = None,
    caller_kind: str = "cloud_wrapper",
    expected_session: str | None = None,
    expected_plan_name: str | None = None,
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
    expected_session / expected_plan_name:
        Optional launch identity supplied by the caller.  When omitted, the
        canonical helper binds the decision to the persisted chain state (or
        the initial ``chain`` session and no active plan).

    Returns
    -------
    dict
        A schema-versioned decision with ``decision`` and ``identity`` fields.
        An explicit ``decision=open`` is required before a wrapper may proceed.
        when the gate is closed and the wrapper must NOT restart / relaunch.
    """
    spec = Path(spec_path)
    ws = Path(workspace) if workspace else None
    explicit = Path(chain_state_path) if chain_state_path else None
    evidence_root = (ws or explicit.parent if explicit is not None else spec.parent).resolve()
    attempt = begin_process_adapter_attempt(
        evidence_root,
        producer_family="cloud_wrapper_adapter",
        adapter_name="wrapper_acceptance_gate",
        surface=caller_kind,
        start_details={
            "spec_path": spec_path,
            "workspace": workspace,
            "chain_state_path": chain_state_path,
            "caller_kind": caller_kind,
        },
    )
    gate_state: ChainState | None = None

    def _finish(
        gate_open: bool,
        reason: str,
        **extra: Any,
    ) -> dict[str, Any]:
        attempt.terminal(
            status="gate_open" if gate_open else "gate_closed",
            outcome="succeeded" if gate_open else "blocked",
            details={
                "reason": reason,
                "caller_kind": caller_kind,
                **extra,
            },
        )
        result: dict[str, Any] = {
            "schema": ACCEPTANCE_GATE_SCHEMA,
            "schema_version": ACCEPTANCE_GATE_SCHEMA_VERSION,
            "decision": "open" if gate_open else "closed",
            "gate_open": gate_open,
            "reason": reason,
            "identity": _decision_identity(
                spec,
                workspace=ws,
                state=gate_state,
                expected_session=expected_session,
                expected_plan_name=expected_plan_name,
            ),
        }
        result.update(extra)
        return result

    if not spec.exists():
        return _finish(False, f"spec not found: {spec_path}")

    spec_obj = _load_spec(spec)
    if spec_obj is None:
        return _finish(False, f"spec unreadable: {spec_path}; acceptance gate closed")

    # ── resolve chain state ───────────────────────────────────────────
    state_path = _resolve_state_path(
        spec, workspace=ws, explicit_state_path=explicit
    )
    if state_path is None:
        # No persisted state yet — chain hasn't run, gate is open.
        return _finish(True, "no chain state yet")

    try:
        state = _load_resolved_chain_state(state_path)
    except Exception as exc:
        blocker_kind = BLOCKER_KIND_BY_CALLER.get(
            caller_kind, BLOCKER_KIND_BY_CALLER["cloud_wrapper"]
        )
        blocker_event = {
            "kind": blocker_kind,
            "predicate_kind": PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
            "evidence_kind": f"cloud_wrapper_{caller_kind}",
            "summary": (
                f"cloud wrapper {caller_kind!r} blocked: chain-state evidence "
                f"could not be read at the acceptance boundary"
            ),
            "details": {
                "caller_kind": caller_kind,
                "spec_path": str(spec),
                "chain_state_path": str(state_path),
                "error": str(exc),
            },
        }
        return _finish(
            False,
            "chain state unreadable; gate closed",
            blocker_event=blocker_event,
        )

    gate_state = state

    identity = _decision_identity(
        spec,
        workspace=ws,
        state=state,
        expected_session=expected_session,
        expected_plan_name=expected_plan_name,
    )
    identity_failures: list[str] = []
    state_session = state.chain_session
    if expected_session and state_session and expected_session != state_session:
        identity_failures.append(
            f"session mismatch: expected {expected_session!r}, state has {state_session!r}"
        )
    if expected_plan_name is not None and state.current_plan_name != expected_plan_name:
        identity_failures.append(
            f"plan mismatch: expected {expected_plan_name!r}, state has {state.current_plan_name!r}"
        )
    if state.resolved_workspace:
        intended_workspace = _resolved_path(ws or spec.parent)
        if _resolved_path(Path(state.resolved_workspace)) != intended_workspace:
            identity_failures.append(
                "workspace mismatch: persisted chain workspace does not match the intended launch"
            )
    if identity_failures:
        return _finish(
            False,
            "acceptance gate identity mismatch; verify the intended spec, session, and plan before relaunch",
            blocker_event={
                "kind": BLOCKER_KIND_BY_CALLER.get(
                    caller_kind, BLOCKER_KIND_BY_CALLER["cloud_wrapper"]
                ),
                "predicate_kind": PREDICATE_KIND_UNKNOWN_ACCEPTANCE_FAILURE,
                "evidence_kind": f"cloud_wrapper_{caller_kind}",
                "summary": "acceptance gate identity mismatch",
                "details": {"identity": identity, "failures": identity_failures},
            },
        )

    # ── check mode ─────────────────────────────────────────────────────
    mode = normalize_contract_mode(state.completion_contract_mode)
    if not is_fail_closed_mode(mode):
        return _finish(True, f"mode={mode}; gate always open in non-fail-closed mode")

    # ── check successors ───────────────────────────────────────────────
    successors = getattr(spec_obj, "successors", None) or []
    if not successors:
        return _finish(True, "no declared successors")

    any_require = any(
        getattr(s, "require_accepted_transaction", True) for s in successors
    )
    if not any_require:
        return _finish(True, "no successor requires acceptance")

    # ── check for completion + receipt ─────────────────────────────────
    # The gate is only meaningful when the chain has actually completed at
    # least its final milestone.  If the chain is still in-progress the
    # restart is fine — the Python-level gate inside run_chain will handle it.
    milestones = getattr(spec_obj, "milestones", None) or []
    if not milestones:
        return _finish(True, "no milestones declared")

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
        return _finish(
            True,
            (
                f"final milestone {final_milestone.label!r} not yet completed; "
                f"successor boundary not reached"
            ),
        )

    has_receipt = state.has_acceptance_receipt(final_milestone.label)
    if has_receipt:
        return _finish(
            True,
            (
                f"acceptance receipt present for {final_milestone.label!r}; "
                f"gate open"
            ),
        )

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

    return _finish(
        False,
        (
            f"acceptance gate closed for {final_milestone.label!r}: "
            f"no acceptance receipt"
        ),
        blocker_event=blocker_event,
    )


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
    if not isinstance(args, dict):
        print(json.dumps({"gate_open": False, "reason": "input must be a JSON object"}))
        sys.exit(2)

    result = check_wrapper_acceptance_gate(
        spec_path=args.get("spec_path", ""),
        workspace=args.get("workspace"),
        chain_state_path=args.get("chain_state_path"),
        caller_kind=args.get("caller_kind", "cloud_wrapper"),
        expected_session=args.get("expected_session"),
        expected_plan_name=args.get("expected_plan_name"),
    )
    try:
        validate_wrapper_acceptance_decision(
            result,
            spec_path=str(args.get("spec_path", "")),
            workspace=args.get("workspace"),
            chain_state_path=args.get("chain_state_path"),
            expected_session=args.get("expected_session"),
            expected_plan_name=args.get("expected_plan_name"),
            require_open=False,
        )
    except AcceptanceGateDecisionError as exc:
        print(
            json.dumps(
                {
                    "schema": ACCEPTANCE_GATE_SCHEMA,
                    "schema_version": ACCEPTANCE_GATE_SCHEMA_VERSION,
                    "decision": "closed",
                    "gate_open": False,
                    "reason": f"{exc.code}: {exc}",
                    "identity": _decision_identity(
                        Path(str(args.get("spec_path", ""))),
                        workspace=(
                            Path(args["workspace"])
                            if isinstance(args.get("workspace"), str)
                            else None
                        ),
                        expected_session=args.get("expected_session"),
                        expected_plan_name=args.get("expected_plan_name"),
                    ),
                },
                sort_keys=True,
            )
        )
        sys.exit(2)
    print(json.dumps(result, sort_keys=True))
    sys.exit(0 if result.get("gate_open") else 1)


if __name__ == "__main__":
    _main()
