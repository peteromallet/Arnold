"""Typed, replayable adoption of a paused progressed C2 attempt.

This is deliberately narrower than reconciliation or target-rebind.  It only
retires the current paused plan and clears it from the chain's active-plan
projection; the cursor, completed prefix, source, runtime and pause authority
remain guarded inputs.  A later runner invocation may materialize a fresh plan
from the committed continuation identity.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, NoReturn

from arnold_pipelines.megaplan._core.io import atomic_write_json, find_plan_dir
from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.incident.chain_control import (
    ChainControlHold,
    ChainControlJournal,
    DurabilityUnknown,
    canonical_json,
    chain_id_for_spec,
    journal_for,
    sha256_hex,
    state_digest_for,
)

SCHEMA = "arnold.megaplan.current-attempt-adoption.v1"
CONTINUATION_SCHEMA = "arnold.megaplan.current-attempt-continuation.v1"
RETIREMENT_SCHEMA = "arnold.megaplan.current-attempt-retirement.v1"
INTENT_KIND = "restart-current-attempt"
COMMITTED_EVENT_KIND = "chain_control.current_attempt_adopted"
ERROR_CODE = "current_attempt_adoption_refused"
_FULL_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CurrentAttemptAdoptionError(ChainControlHold):
    """Fail-closed refusal for an invalid or divergent C2 adoption."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(code, message, details=dict(details or {}))


@dataclass(frozen=True)
class CurrentAttemptGuards:
    """The complete precondition tuple for one adoption operation."""

    expected_session_id: str
    expected_current_plan: str
    expected_current_milestone: str
    expected_cursor: int
    expected_spec_sha256: str
    expected_chain_state_sha256: str
    expected_plan_state_sha256: str
    expected_marker_sha256: str
    expected_attempt_identity: Mapping[str, Any] | str
    expected_completed_prefix: tuple[Mapping[str, Any], ...]
    expected_chain_revision: Any = None
    expected_plan_revision: Any = None
    expected_source_binding: Mapping[str, Any] | None = None
    expected_runtime_identity: Mapping[str, Any] | None = None
    expected_hold: Mapping[str, Any] | None = None


def _require_complete_guards(guards: CurrentAttemptGuards) -> None:
    """Reject an incomplete authority tuple before any journal access/write."""
    missing = [
        name
        for name, value in (
            ("expected_chain_revision", guards.expected_chain_revision),
            ("expected_plan_revision", guards.expected_plan_revision),
            ("expected_source_binding", guards.expected_source_binding),
            ("expected_runtime_identity", guards.expected_runtime_identity),
            ("expected_hold", guards.expected_hold),
        )
        if value is None
    ]
    if missing:
        _fail("missing_guard", "complete authority guards are required", missing=missing)
    if not isinstance(guards.expected_source_binding, Mapping):
        _fail("invalid_guard", "expected_source_binding must be a mapping")
    if not isinstance(guards.expected_runtime_identity, Mapping):
        _fail("invalid_guard", "expected_runtime_identity must be a mapping")
    if not isinstance(guards.expected_hold, Mapping):
        _fail("invalid_guard", "expected_hold must be a mapping")


def _fail(code: str, message: str, **details: Any) -> NoReturn:
    raise CurrentAttemptAdoptionError(code, message, details=details)



def _sha(value: Any, label: str) -> str:
    value = str(value or "").strip().lower()
    if not _FULL_SHA256.fullmatch(value):
        _fail("invalid_guard", f"{label} must be a full SHA-256")
    return value


def _read_json(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _fail("missing_or_malformed", f"{label} is unavailable or malformed", path=str(path))
    if not isinstance(value, dict):
        _fail("missing_or_malformed", f"{label} must be a JSON object", path=str(path))
    return raw, value


def _assert_equal(label: str, observed: Any, expected: Any) -> None:
    if observed != expected:
        _fail("identity_mismatch", f"{label} does not match its guard", expected=expected, observed=observed)


def _candidate(values: list[tuple[str, Any]], label: str) -> Any:
    present = [(where, value) for where, value in values if value not in (None, "")]
    if not present:
        return None
    first = present[0][1]
    if any(value != first for _, value in present[1:]):
        _fail("ambiguous_attempt", f"attempt {label} has conflicting coordinates", candidates=present)
    return first


def _attempt_identity(plan: Mapping[str, Any]) -> dict[str, Any]:
    meta = plan.get("meta") if isinstance(plan.get("meta"), Mapping) else {}
    active = plan.get("active_step") if isinstance(plan.get("active_step"), Mapping) else {}
    wbc = active.get("phase_wbc") if isinstance(active.get("phase_wbc"), Mapping) else {}
    meta_wbc = meta.get("phase_wbc") if isinstance(meta.get("phase_wbc"), Mapping) else {}
    invocation = _candidate(
        [("meta.current_invocation_id", meta.get("current_invocation_id")), ("active_step.invocation_id", active.get("invocation_id"))],
        "invocation",
    )
    phase = _candidate(
        [("active_step.phase", active.get("phase")), ("active_step.step", active.get("step")), ("wbc.phase", wbc.get("phase")), ("meta_wbc.phase", meta_wbc.get("phase"))],
        "phase",
    )
    run_id = _candidate(
        [("active_step.run_id", active.get("run_id")), ("meta.run_id", meta.get("run_id"))],
        "run_id",
    )
    attempt_number = _candidate(
        [("active_step.attempt_number", active.get("attempt_number")), ("active_step.attempt", active.get("attempt")), ("meta.attempt_number", meta.get("attempt_number"))],
        "attempt_number",
    )
    wbc_attempt = _candidate(
        [("active_step.phase_wbc.attempt_id", wbc.get("attempt_id")), ("meta.phase_wbc.attempt_id", meta_wbc.get("attempt_id")), ("meta.wbc_attempt_id", meta.get("wbc_attempt_id"))],
        "wbc_attempt_id",
    )
    if invocation is None:
        _fail("missing_attempt", "current_invocation_id is required")
    if phase is None and run_id is None and attempt_number is None and wbc_attempt is None:
        _fail("missing_attempt", "no active-step or WBC attempt coordinate is present")
    result: dict[str, Any] = {"schema": "arnold.megaplan.current-attempt-identity.v1", "invocation_id": str(invocation)}
    for key, value in (("phase", phase), ("run_id", run_id), ("attempt_number", attempt_number), ("wbc_attempt_id", wbc_attempt)):
        if value is not None:
            result[key] = value
    return result


def _prefix_digest(prefix: list[dict[str, Any]]) -> str:
    return sha256_hex(b"NBF08-C2-COMPLETED-PREFIX-V1\x00" + canonical_json(prefix))


def _assert_artifact_hashes(root: Path, prefix: list[dict[str, Any]]) -> None:
    """Verify optional path/hash pairs carried by completed records."""
    for record in prefix:
        artifacts = record.get("artifacts")
        pairs: list[tuple[Any, Any]] = []
        if isinstance(artifacts, Mapping):
            pairs.extend((key, value) for key, value in artifacts.items())
        elif isinstance(artifacts, list):
            pairs.extend(
                (item.get("path"), item.get("sha256"))
                for item in artifacts
                if isinstance(item, Mapping)
            )
        for path_value, digest in pairs:
            if not isinstance(path_value, str) or not isinstance(digest, str):
                _fail("artifact_identity_mismatch", "completed artifact reference is malformed")
            target = (root / path_value).resolve(strict=False)
            try:
                target.relative_to(root.resolve(strict=False))
                observed = hashlib.sha256(target.read_bytes()).hexdigest()
            except (OSError, ValueError):
                _fail("artifact_identity_mismatch", "completed artifact is unavailable", path=path_value)
            _assert_equal(f"completed artifact {path_value}", observed, digest.lower())


def _guard_marker(marker: Mapping[str, Any], guards: CurrentAttemptGuards, spec_path: Path) -> None:
    if marker.get("should_run") is not False:
        _fail("marker_mismatch", "adoption requires should_run=false")
    pause = marker.get("operator_pause")
    if not isinstance(pause, Mapping) or pause.get("active") is not True:
        _fail("marker_mismatch", "adoption requires an active operator pause")
    hold = marker.get("operator_resume_hold")
    if not isinstance(hold, Mapping) or hold.get("active") is not True:
        _fail("hold_mismatch", "adoption requires the exact active resume hold")
    _assert_equal("marker hold session", hold.get("session"), guards.expected_session_id)
    _assert_equal("marker hold spec", hold.get("spec"), str(spec_path.resolve(strict=False)))
    if guards.expected_hold is not None:
        _assert_equal("resume hold", dict(hold), dict(guards.expected_hold))
    if guards.expected_runtime_identity is not None:
        runtime = marker.get("runtime_identity")
        if not isinstance(runtime, Mapping):
            runtime = marker.get("runtime")
        _assert_equal("marker runtime identity", runtime, dict(guards.expected_runtime_identity))


def _guard_state(
    *,
    root: Path,
    spec_path: Path,
    guards: CurrentAttemptGuards,
    chain_raw: bytes,
    chain: Mapping[str, Any],
    plan_raw: bytes,
    plan: Mapping[str, Any],
    marker_raw: bytes,
    marker: Mapping[str, Any],
) -> dict[str, Any]:
    spec_sha = _sha(guards.expected_spec_sha256, "spec SHA-256")
    chain_sha = _sha(guards.expected_chain_state_sha256, "chain-state SHA-256")
    plan_sha = _sha(guards.expected_plan_state_sha256, "plan-state SHA-256")
    marker_sha = _sha(guards.expected_marker_sha256, "marker SHA-256")
    _assert_equal("chain spec SHA-256", hashlib.sha256(spec_path.read_bytes()).hexdigest(), spec_sha)
    _assert_equal("chain state SHA-256", hashlib.sha256(chain_raw).hexdigest(), chain_sha)
    _assert_equal("plan state SHA-256", hashlib.sha256(plan_raw).hexdigest(), plan_sha)
    _assert_equal("marker SHA-256", hashlib.sha256(marker_raw).hexdigest(), marker_sha)
    _assert_equal("chain id", chain_id_for_spec(spec_path), chain.get("metadata", {}).get("chain_id", chain_id_for_spec(spec_path)))
    _assert_equal("chain session", chain.get("chain_session"), guards.expected_session_id)
    _assert_equal("chain cursor", chain.get("current_milestone_index"), guards.expected_cursor)
    _assert_equal("chain active plan", chain.get("current_plan_name"), guards.expected_current_plan)
    _assert_equal("chain lifecycle", chain.get("last_state"), "paused")
    prefix = chain.get("completed")
    expected_prefix = [dict(item) for item in guards.expected_completed_prefix]
    if not isinstance(prefix, list) or len(prefix) != len(expected_prefix):
        _fail("prefix_mismatch", "completed prefix length does not match the guard")
    if len(expected_prefix) != 6:
        _fail("prefix_mismatch", "exactly six completed records are required")
    try:
        milestones = chain_spec.load_spec(spec_path).milestones
        canonical_labels = [str(item.label) for item in milestones[:6]]
    except (AttributeError, TypeError, ValueError):
        _fail("prefix_mismatch", "chain spec does not expose six canonical milestones")
    observed_labels = [item.get("label") if isinstance(item, Mapping) else None for item in prefix]
    expected_labels = [item.get("label") for item in expected_prefix]
    if observed_labels != canonical_labels:
        _fail("prefix_mismatch", "completed labels do not match the canonical chain prefix", expected=canonical_labels, observed=observed_labels)
    if expected_labels != canonical_labels:
        _fail("prefix_mismatch", "prefix guard labels do not match the canonical chain prefix", expected=canonical_labels, observed=expected_labels)
    _assert_equal("completed prefix", prefix, expected_prefix)
    _assert_artifact_hashes(root, prefix)
    observed_attempt = _attempt_identity(plan)
    expected_attempt = guards.expected_attempt_identity
    if isinstance(expected_attempt, Mapping):
        _assert_equal("attempt identity", observed_attempt, dict(expected_attempt))
    else:
        _assert_equal("attempt identity digest", sha256_hex(canonical_json(observed_attempt)), str(expected_attempt))
    _assert_equal("plan name", plan.get("name"), guards.expected_current_plan)
    if plan.get("current_state") != "paused":
        _fail("plan_mismatch", "current C2 plan is not paused")
    chain_meta = chain.get("metadata") if isinstance(chain.get("metadata"), Mapping) else {}
    plan_meta = plan.get("meta") if isinstance(plan.get("meta"), Mapping) else {}
    _assert_equal("chain pause authority", chain_meta.get("operator_pause"), marker.get("operator_pause"))
    plan_pause = plan_meta.get("operator_pause")
    if not isinstance(plan_pause, Mapping):
        _fail("pause_mismatch", "plan-side operator pause authority is missing")
    _assert_equal("plan pause authority", dict(plan_pause), dict(chain_meta.get("operator_pause") or {}))
    if guards.expected_source_binding is not None:
        _assert_equal("source binding", chain_meta.get("project_source_binding"), dict(guards.expected_source_binding))
        _assert_equal("plan source binding", plan_meta.get("project_source_binding"), dict(guards.expected_source_binding))
    if guards.expected_runtime_identity is not None:
        binding = chain_meta.get("execution_binding") if isinstance(chain_meta.get("execution_binding"), Mapping) else {}
        launched = binding.get("launched_identity") if isinstance(binding.get("launched_identity"), Mapping) else {}
        _assert_equal("runtime identity", launched.get("runtime"), dict(guards.expected_runtime_identity))
    plan_revision = plan_meta.get("_nbf08_revision")
    if guards.expected_plan_revision is not None:
        _assert_equal("plan revision", plan_revision, guards.expected_plan_revision)
    if guards.expected_chain_revision is not None:
        _assert_equal("chain revision", chain_meta.get("_nbf08_revision"), guards.expected_chain_revision)
    _guard_marker(marker, guards, spec_path)
    return {
        "attempt": observed_attempt,
        "prefix": copy.deepcopy(prefix),
        "prefix_digest": _prefix_digest(prefix),
        "chain_revision": chain_meta.get("_nbf08_revision"),
        "plan_revision": plan_revision,
        "chain_digest": state_digest_for(chain),
        "plan_digest": hashlib.sha256(plan_raw).hexdigest(),
        "spec_sha256": spec_sha,
        "marker_sha256": marker_sha,
    }


def _plan_write(plan_path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_json(plan_path, dict(payload))


def _guard_recovery_authority(
    *,
    guards: CurrentAttemptGuards,
    spec_path: Path,
    marker_path: Path,
    chain: Mapping[str, Any],
    plan: Mapping[str, Any],
    marker: Mapping[str, Any],
) -> None:
    """Recheck mandatory authority bindings on replay and interrupted recovery."""
    _assert_equal(
        "recovery spec SHA-256",
        hashlib.sha256(spec_path.read_bytes()).hexdigest(),
        guards.expected_spec_sha256,
    )
    _assert_equal(
        "recovery marker SHA-256",
        hashlib.sha256(marker_path.read_bytes()).hexdigest(),
        guards.expected_marker_sha256,
    )
    chain_meta = chain.get("metadata") if isinstance(chain.get("metadata"), Mapping) else {}
    plan_meta = plan.get("meta") if isinstance(plan.get("meta"), Mapping) else {}
    _assert_equal("recovery source binding", chain_meta.get("project_source_binding"), dict(guards.expected_source_binding or {}))
    _assert_equal("recovery plan source binding", plan_meta.get("project_source_binding"), dict(guards.expected_source_binding or {}))
    binding = chain_meta.get("execution_binding") if isinstance(chain_meta.get("execution_binding"), Mapping) else {}
    launched = binding.get("launched_identity") if isinstance(binding.get("launched_identity"), Mapping) else {}
    _assert_equal("recovery runtime identity", launched.get("runtime"), dict(guards.expected_runtime_identity or {}))
    _assert_equal("recovery plan pause authority", plan_meta.get("operator_pause"), dict(chain_meta.get("operator_pause") or {}))
    _assert_equal("recovery chain pause authority", chain_meta.get("operator_pause"), marker.get("operator_pause"))
    _guard_marker(marker, guards, spec_path)


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Return the exact bytes produced by ``atomic_write_json``."""
    return (json.dumps(dict(payload), indent=2, sort_keys=False) + "\n").encode("utf-8")


def _post_states(chain: Mapping[str, Any], plan: Mapping[str, Any], continuation: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    next_chain = copy.deepcopy(dict(chain))
    next_meta = dict(next_chain.get("metadata") or {})
    next_meta["current_attempt_continuation"] = dict(continuation)
    next_meta["current_attempt_adoption"] = {
        "schema": SCHEMA,
        "operation_id": continuation["operation_id"],
        "retired_plan": continuation["retired_plan"],
        "continuation_id": continuation["continuation_id"],
    }
    next_chain["metadata"] = next_meta
    next_chain["current_plan_name"] = None
    next_chain["last_state"] = "paused"
    next_plan = copy.deepcopy(dict(plan))
    next_plan_meta = dict(next_plan.get("meta") or {})
    next_plan_meta["current_attempt_retirement"] = {
        "schema": RETIREMENT_SCHEMA,
        "operation_id": continuation["operation_id"],
        "continuation_id": continuation["continuation_id"],
        "retired_at": continuation["created_at"],
    }
    next_plan["meta"] = next_plan_meta
    return next_chain, next_plan


def _verify_post(
    *, chain_path: Path, plan_path: Path, post_chain: Mapping[str, Any], post_plan: Mapping[str, Any], effect: Mapping[str, Any]
) -> None:
    chain_raw, chain = _read_json(chain_path, "chain state")
    plan_raw, plan = _read_json(plan_path, "plan state")
    if state_digest_for(chain) != effect.get("post_chain_digest"):
        _fail("recovery_divergence", "chain state is neither the guarded pre-state nor committed post-state")
    if hashlib.sha256(plan_raw).hexdigest() != effect.get("post_plan_sha256"):
        _fail("recovery_divergence", "plan state is not the committed post-state")
    if chain != dict(post_chain) or plan != dict(post_plan):
        _fail("recovery_divergence", "committed state does not match the recorded transition")


def _replay(
    journal: ChainControlJournal,
    *,
    chain_id: str,
    operation_id: str,
    existing: Mapping[str, Any],
    actor: str,
    state_paths: list[Path],
) -> dict[str, Any]:
    with journal.transaction(chain_ids=[chain_id], state_paths=state_paths, operation_id=operation_id, actor={"id": actor, "class": "operator"}) as txn:
        event = _append_replay_under_lock(journal, txn, chain_id=chain_id, operation_id=operation_id, existing=existing, actor=actor)
    return {"outcome": "replay", "receipt": dict(existing), "replay_event": event, "external_effect": False}


def _append_replay_under_lock(
    journal: ChainControlJournal,
    txn: Any,
    *,
    chain_id: str,
    operation_id: str,
    existing: Mapping[str, Any],
    actor: str,
) -> dict[str, Any]:
    return journal.append_under_lock(
        txn,
        event_kind="chain_control.replay",
        chain_id=chain_id,
        operation_id=operation_id,
        causation_id=str(existing.get("event_id") or operation_id),
        correlation_id=operation_id,
        payload={"schema": SCHEMA, "original_event_id": existing.get("event_id"), "original_outcome": existing.get("outcome"), "intent_kind": INTENT_KIND},
        semantic_effect="no_change",
        claim_class="evidence-only",
        actor={"id": actor, "class": "operator"},
        outcome="replay",
        intent=INTENT_KIND,
        expected_cursor=existing.get("expected_cursor"),
        expected_revision=existing.get("expected_revision"),
    )


def restart_current_attempt(
    *,
    spec_path: Path,
    project_dir: Path,
    marker_path: Path,
    guards: CurrentAttemptGuards,
    reason: str,
    actor: str = "operator",
    operation_id: str | None = None,
    failure_injector: Callable[[str], None] | None = None,
    dispatch_handoff: Callable[[Mapping[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Retire a paused progressed-C2 plan and commit one continuation identity."""
    if not reason.strip() or not actor.strip():
        _fail("invalid_guard", "reason and actor are required")
    # This check deliberately precedes journal construction/genesis so a
    # malformed authority tuple has no observable journal side effect.
    _require_complete_guards(guards)
    spec_path = spec_path.resolve(strict=False)
    project_dir = project_dir.resolve(strict=False)
    marker_path = marker_path.resolve(strict=False)
    plan_dir = find_plan_dir(project_dir, guards.expected_current_plan)
    if plan_dir is None:
        _fail("missing_plan", "current C2 plan directory is unavailable")
    chain_path = chain_spec._state_path_for(spec_path)
    plan_path = plan_dir / "state.json"
    try:
        spec_path.relative_to(project_dir)
        marker_path.relative_to(project_dir)
    except ValueError:
        _fail("invalid_guard", "spec and marker must be inside the guarded project directory")
    spec = chain_spec.load_spec(spec_path)
    if guards.expected_cursor < 0 or guards.expected_cursor >= len(spec.milestones):
        _fail("milestone_mismatch", "guarded cursor is outside the chain spec")
    if spec.milestones[guards.expected_cursor].label != guards.expected_current_milestone:
        _fail("milestone_mismatch", "guarded current milestone is not the spec successor")
    if guards.expected_cursor != 6 or len(guards.expected_completed_prefix) != 6:
        _fail("milestone_mismatch", "current-attempt adoption only accepts the progressed C2 six-prefix")
    chain_id = chain_id_for_spec(spec_path)
    expected_identity_material = {
        "schema": SCHEMA,
        "chain_id": chain_id,
        "session": guards.expected_session_id,
        "plan": guards.expected_current_plan,
        "milestone": guards.expected_current_milestone,
        "cursor": guards.expected_cursor,
        "spec_sha256": _sha(guards.expected_spec_sha256, "spec SHA-256"),
        "chain_state_sha256": _sha(guards.expected_chain_state_sha256, "chain-state SHA-256"),
        "plan_state_sha256": _sha(guards.expected_plan_state_sha256, "plan-state SHA-256"),
        "marker_sha256": _sha(guards.expected_marker_sha256, "marker SHA-256"),
        "chain_revision": guards.expected_chain_revision,
        "plan_revision": guards.expected_plan_revision,
        "source_binding": guards.expected_source_binding,
        "runtime_identity": guards.expected_runtime_identity,
        "expected_hold": guards.expected_hold,
        "attempt": guards.expected_attempt_identity,
        "prefix_digest": _prefix_digest([dict(item) for item in guards.expected_completed_prefix]),
    }
    derived_operation_id = "c2-adopt-" + sha256_hex(canonical_json(expected_identity_material))
    if operation_id is not None and operation_id != derived_operation_id:
        _fail("operation_identity_mismatch", "operation identity does not match guarded inputs")
    operation_id = derived_operation_id
    journal = journal_for(project_dir)
    existing = journal.operation_result(operation_id)
    if existing is not None and existing.get("event_kind") == COMMITTED_EVENT_KIND:
        effect = existing.get("payload", {}).get("effect") if isinstance(existing.get("payload"), Mapping) else None
        if not isinstance(effect, Mapping):
            _fail("recovery_divergence", "committed adoption receipt has no effect")
        chain_raw, chain = _read_json(chain_path, "chain state")
        plan_raw, plan = _read_json(plan_path, "plan state")
        marker_raw, marker = _read_json(marker_path, "session marker")
        _assert_equal("spec SHA-256", hashlib.sha256(spec_path.read_bytes()).hexdigest(), expected_identity_material["spec_sha256"])
        _assert_equal("marker SHA-256", hashlib.sha256(marker_raw).hexdigest(), expected_identity_material["marker_sha256"])
        post_chain = effect.get("post_chain")
        post_plan = effect.get("post_plan")
        if not isinstance(post_chain, Mapping) or not isinstance(post_plan, Mapping):
            _fail("recovery_divergence", "committed adoption receipt lacks replay state")
        if state_digest_for(chain) != effect.get("post_chain_digest") or hashlib.sha256(plan_raw).hexdigest() != effect.get("post_plan_sha256"):
            _fail("recovery_divergence", "authoritative state diverged from committed adoption")
        _guard_recovery_authority(
            guards=guards, spec_path=spec_path, marker_path=marker_path, chain=chain, plan=plan, marker=marker
        )
        return _replay(journal, chain_id=chain_id, operation_id=operation_id, existing=existing, actor=actor, state_paths=[chain_path, plan_path])
    replay = journal.replay_strict()
    incomplete = [event for event in replay.get("accepted", []) if event.get("operation_id") == operation_id and event.get("event_kind") == "chain_control.intent"]
    chain_raw, chain = _read_json(chain_path, "chain state")
    plan_raw, plan = _read_json(plan_path, "plan state")
    marker_raw, marker = _read_json(marker_path, "session marker")
    if incomplete:
        intent = incomplete[-1]
        context = intent.get("payload") if isinstance(intent.get("payload"), Mapping) else {}
        post_chain = context.get("post_chain")
        post_plan = context.get("post_plan")
        effect = context.get("effect")
        if not isinstance(post_chain, Mapping) or not isinstance(post_plan, Mapping) or not isinstance(effect, Mapping):
            raise DurabilityUnknown("incomplete adoption intent lacks recovery material")
        if state_digest_for(chain) not in {effect.get("pre_chain_digest"), effect.get("post_chain_digest")}:
            _fail("recovery_divergence", "chain state diverged during interrupted adoption")
        if hashlib.sha256(plan_raw).hexdigest() not in {effect.get("pre_plan_sha256"), effect.get("post_plan_sha256")}:
            _fail("recovery_divergence", "plan state diverged during interrupted adoption")
        with journal.transaction(chain_ids=[chain_id], state_paths=[chain_path, plan_path, marker_path, spec_path], operation_id=operation_id, actor={"id": actor, "class": "operator"}) as txn:
            _guard_recovery_authority(
                guards=guards, spec_path=spec_path, marker_path=marker_path, chain=chain, plan=plan, marker=marker
            )
            if state_digest_for(chain) == effect.get("pre_chain_digest"):
                chain_payload = dict(post_chain)
                chain_adapter = __import__("arnold_pipelines.megaplan.incident.chain_control", fromlist=["ChainStateAdapter"]).ChainStateAdapter(txn, chain_path)
                chain_adapter.cas_write(chain_payload, expected_revision=effect.get("pre_chain_revision"))
            if hashlib.sha256(plan_raw).hexdigest() == effect.get("pre_plan_sha256"):
                _plan_write(plan_path, post_plan)
            final_chain_raw, final_chain = _read_json(chain_path, "chain state")
            final_plan_raw, final_plan = _read_json(plan_path, "plan state")
            if state_digest_for(final_chain) != effect.get("post_chain_digest") or hashlib.sha256(final_plan_raw).hexdigest() != effect.get("post_plan_sha256"):
                raise DurabilityUnknown("adoption recovery did not reach its recorded post-state")
            committed = journal.append_under_lock(txn, event_kind=COMMITTED_EVENT_KIND, chain_id=chain_id, operation_id=operation_id, causation_id=str(intent.get("event_id") or operation_id), correlation_id=operation_id, payload={"schema": SCHEMA, "effect": effect}, semantic_effect="metadata_only", claim_class="required", actor={"id": actor, "class": "operator"}, outcome="committed", intent=INTENT_KIND, expected_cursor=guards.expected_cursor, expected_revision=guards.expected_chain_revision, actual_cursor=guards.expected_cursor, actual_revision=effect.get("post_chain_revision"), pre_state_digest=effect.get("pre_chain_digest"), post_state_digest=effect.get("post_chain_digest"), source_identity=guards.expected_source_binding, spec_identity=str(spec_path))
            result = {"outcome": "committed", "receipt": committed, "continuation": effect["continuation"]}
            if dispatch_handoff is not None:
                dispatch_handoff(dict(effect["continuation"]))
            return result
    observed = _guard_state(
        root=project_dir,
        spec_path=spec_path,
        guards=guards,
        chain_raw=chain_raw,
        chain=chain,
        plan_raw=plan_raw,
        plan=plan,
        marker_raw=marker_raw,
        marker=marker,
    )
    # Only a fully validated pre-state may create the genesis record.  This
    # keeps all refusal paths (including malformed/ambiguous fixtures) truly
    # zero-write while retaining the existing journal authority model.
    journal.ensure_genesis(
        chain_id=chain_id,
        actor={"id": actor, "class": "operator"},
        spec_identity=str(spec_path),
        source_identity=guards.expected_source_binding,
    )
    # Re-read all guarded inputs after acquiring the ordered locks.  The
    # initial validation above is only an early refusal; this is the commit
    # precondition and prevents a stale plan/spec/marker from being adopted.
    with journal.transaction(
        chain_ids=[chain_id],
        state_paths=[chain_path, plan_path, marker_path, spec_path],
        expected_revision=guards.expected_chain_revision,
        operation_id=operation_id,
        actor={"id": actor, "class": "operator"},
    ) as txn:
        locked_spec_sha = hashlib.sha256(spec_path.read_bytes()).hexdigest()
        locked_marker_raw, locked_marker = _read_json(marker_path, "session marker")
        locked_chain_raw, locked_chain = _read_json(chain_path, "chain state")
        locked_plan_raw, locked_plan = _read_json(plan_path, "plan state")
        # A concurrent adopter may have committed while this caller was
        # validating its pre-state.  Once the ordered locks are held, replay
        # the already-committed operation under this transaction rather than
        # treating its legitimate post-state as a stale-writer failure.
        locked_existing = journal.operation_result(operation_id)
        if locked_existing is not None and locked_existing.get("event_kind") == COMMITTED_EVENT_KIND:
            locked_payload = locked_existing.get("payload")
            locked_effect = locked_payload.get("effect") if isinstance(locked_payload, Mapping) else None
            if not isinstance(locked_effect, Mapping):
                _fail("recovery_divergence", "committed adoption receipt has no effect")
            _assert_equal("locked spec SHA-256", locked_spec_sha, expected_identity_material["spec_sha256"])
            _assert_equal("locked marker SHA-256", hashlib.sha256(locked_marker_raw).hexdigest(), expected_identity_material["marker_sha256"])
            _assert_equal("locked chain post-state", state_digest_for(locked_chain), locked_effect.get("post_chain_digest"))
            _assert_equal("locked plan post-state", hashlib.sha256(locked_plan_raw).hexdigest(), locked_effect.get("post_plan_sha256"))
            _guard_marker(locked_marker, guards, spec_path)
            replay_event = _append_replay_under_lock(
                journal,
                txn,
                chain_id=chain_id,
                operation_id=operation_id,
                existing=locked_existing,
                actor=actor,
            )
            return {"outcome": "replay", "receipt": dict(locked_existing), "replay_event": replay_event, "external_effect": False}
        locked = _guard_state(
            root=project_dir,
            spec_path=spec_path,
            guards=guards,
            chain_raw=locked_chain_raw,
            chain=locked_chain,
            plan_raw=locked_plan_raw,
            plan=locked_plan,
            marker_raw=locked_marker_raw,
            marker=locked_marker,
        )
        _assert_equal("locked spec SHA-256", locked_spec_sha, observed["spec_sha256"])
        _assert_equal("locked chain state", locked["chain_digest"], observed["chain_digest"])
        _assert_equal("locked plan state", hashlib.sha256(locked_plan_raw).hexdigest(), observed["plan_digest"])
        continuation_id = "c2-continuation-" + sha256_hex(canonical_json({"operation_id": operation_id, "attempt": locked["attempt"], "prefix_digest": locked["prefix_digest"]}))
        continuation = {"schema": CONTINUATION_SCHEMA, "continuation_id": continuation_id, "operation_id": operation_id, "chain_id": chain_id, "session": guards.expected_session_id, "milestone": guards.expected_current_milestone, "cursor": guards.expected_cursor, "retired_plan": guards.expected_current_plan, "attempt": locked["attempt"], "source_binding": copy.deepcopy(guards.expected_source_binding), "runtime_identity": copy.deepcopy(guards.expected_runtime_identity), "created_at": "committed"}
        post_chain, post_plan = _post_states(locked_chain, locked_plan, continuation)
        pre_chain_revision = locked["chain_revision"]
        post_chain_revision = 0 if pre_chain_revision is None else int(pre_chain_revision) + 1
        post_chain_meta = dict(post_chain.get("metadata") or {})
        post_chain_meta["_nbf08_revision"] = post_chain_revision
        post_chain["metadata"] = post_chain_meta
        post_plan_meta = dict(post_plan.get("meta") or {})
        pre_plan_revision = post_plan_meta.get("_nbf08_revision")
        post_plan_meta["_nbf08_revision"] = 0 if pre_plan_revision is None else int(pre_plan_revision) + 1
        post_plan["meta"] = post_plan_meta
        effect = {"schema": SCHEMA, "continuation": continuation, "pre_chain_digest": state_digest_for(locked_chain), "post_chain_digest": state_digest_for(post_chain), "pre_chain_revision": pre_chain_revision, "post_chain_revision": post_chain_revision, "pre_plan_sha256": hashlib.sha256(locked_plan_raw).hexdigest(), "post_plan_sha256": hashlib.sha256(_json_bytes(post_plan)).hexdigest(), "post_chain": post_chain, "post_plan": post_plan}
        intent_context = {"schema": SCHEMA, "operation_id": operation_id, "post_chain": post_chain, "post_plan": post_plan, "effect": effect}
        intent = journal.append_under_lock(txn, event_kind="chain_control.intent", chain_id=chain_id, operation_id=operation_id, causation_id=operation_id, correlation_id=operation_id, payload=intent_context, semantic_effect="no_change", claim_class="required", actor={"id": actor, "class": "operator"}, intent=INTENT_KIND, expected_cursor=guards.expected_cursor, expected_revision=guards.expected_chain_revision, source_identity=guards.expected_source_binding, spec_identity=str(spec_path))
        if failure_injector:
            failure_injector("after_intent")
        _plan_write(plan_path, post_plan)
        if failure_injector:
            failure_injector("after_plan_cas")
        from arnold_pipelines.megaplan.incident.chain_control import ChainStateAdapter
        ChainStateAdapter(txn, chain_path).cas_write(post_chain, expected_revision=guards.expected_chain_revision)
        if failure_injector:
            failure_injector("after_chain_cas")
        _verify_post(
            chain_path=chain_path,
            plan_path=plan_path,
            post_chain=post_chain,
            post_plan=post_plan,
            effect=effect,
        )
        if failure_injector:
            failure_injector("before_commit")
        committed = journal.append_under_lock(txn, event_kind=COMMITTED_EVENT_KIND, chain_id=chain_id, operation_id=operation_id, causation_id=str(intent.get("payload", {}).get("event_id") or operation_id), correlation_id=operation_id, payload={"schema": SCHEMA, "effect": effect}, semantic_effect="metadata_only", claim_class="required", actor={"id": actor, "class": "operator"}, outcome="committed", intent=INTENT_KIND, expected_cursor=guards.expected_cursor, expected_revision=guards.expected_chain_revision, actual_cursor=guards.expected_cursor, actual_revision=effect["post_chain_revision"], pre_state_digest=effect["pre_chain_digest"], post_state_digest=effect["post_chain_digest"], source_identity=guards.expected_source_binding, spec_identity=str(spec_path))
    result = {"outcome": "committed", "receipt": committed, "continuation": continuation}
    if dispatch_handoff is not None:
        dispatch_handoff(dict(continuation))
    return result


__all__ = ["CurrentAttemptAdoptionError", "CurrentAttemptGuards", "restart_current_attempt", "SCHEMA", "CONTINUATION_SCHEMA"]
