"""Guarded occurrence adoption primitive (T4.2).

T4.3 calls :func:`guarded_occurrence_adoption`. Operator intent is bound to
one exact action type, occurrence, target identity, root
``MutationCapability``, and fence epoch. PID, tmux, repo-path similarity,
stopped leases, and stale markers are diagnostic only and cannot grant
adoption. The logical resume cursor and plan payload are never rewritten.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.cloud.current_target_liveness import (
    MutationCapability,
    MutationDenied,
    require_mutation_capability,
    resolve_mutation_capability,
)
from arnold_pipelines.megaplan.types import CliError

ADOPTION_SCHEMA = "arnold.megaplan.guarded-occurrence-adoption.v1"
ADOPTION_ACTION = "occurrence_adoption"
ADOPTION_SENTINEL = ".t42-disposable-root"
_OPERATIONAL_EVIDENCE_KEYS = frozenset(
    {
        "pid",
        "worker_pid",
        "tmux",
        "tmux_session",
        "repo_path",
        "path_similarity",
        "lease",
        "stopped_lease",
        "stale_marker",
        "marker",
        "heartbeat",
        "live_process",
    }
)


def assert_disposable_root(root: Path) -> Path:
    """Require an explicit disposable root that is not a live runtime tree."""

    resolved = Path(root).expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    if "runtime-candidates" in resolved.parts:
        raise MutationDenied(
            "adoption root resembles a candidate runtime",
            code="disposable_root_required",
        )
    if any(part in {"live"} and "runtime" in resolved.parts for part in resolved.parts):
        raise MutationDenied(
            "adoption root resembles a live runtime",
            code="disposable_root_required",
        )
    if (resolved / "arnold_pipelines" / "megaplan").exists():
        raise MutationDenied(
            "adoption root is a project or live runtime package tree",
            code="disposable_root_required",
        )
    (resolved / ADOPTION_SENTINEL).write_text("disposable\n", encoding="utf-8")
    return resolved


def _text(value: Any) -> str:
    return str(value or "").strip()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def plan_payload_without_pause(plan: Mapping[str, Any]) -> bytes:
    """Byte-stable logical plan payload excluding append-only pause metadata.

    Pause may change ``current_state`` to ``paused`` and may append
    ``meta.operator_pause`` / schema bookkeeping. Those are not the logical
    resume cursor or plan payload.
    """

    payload = json.loads(json.dumps(dict(plan), default=str))
    payload.pop("current_state", None)
    payload.pop("schema_version", None)
    meta = payload.get("meta")
    if isinstance(meta, dict):
        meta.pop("operator_pause", None)
        # Authorized binding receipt (import_root / interpreter / project
        # source) is not the logical plan payload. G4-003 preserves cursor
        # + payload; rebind may update only the authorized binding.
        meta.pop("project_source_binding", None)
        policy = meta.get("chain_policy")
        if isinstance(policy, dict):
            policy.pop("milestone_base_sha", None)
            meta["chain_policy"] = policy
        execution = meta.get("execution_environment")
        if isinstance(execution, dict):
            execution.pop("target_head", None)
            execution.pop("last_observed_phase", None)
            meta["execution_environment"] = execution
        payload["meta"] = meta
    return _canonical_bytes(payload)



def resume_cursor_bytes(plan: Mapping[str, Any]) -> bytes:
    return _canonical_bytes(plan.get("resume_cursor"))


def bind_operator_intent(
    capability: MutationCapability | Mapping[str, Any] | None,
    *,
    action: str,
    occurrence: str,
    target: str,
    fence_epoch: int,
    scope: str = "",
) -> MutationCapability:
    """Bind operator intent to one action, occurrence, target, capability, and epoch."""

    wanted_action = _text(action)
    wanted_occurrence = _text(occurrence)
    wanted_target = _text(target)
    if not wanted_action or not wanted_occurrence or not wanted_target:
        raise MutationDenied(
            "operator intent requires action, occurrence, and target identity",
            code="identity_incomplete",
        )
    if isinstance(fence_epoch, bool) or not isinstance(fence_epoch, int) or fence_epoch < 0:
        raise MutationDenied(
            "operator intent requires a non-negative fence epoch",
            code="identity_incomplete",
        )
    minted = require_mutation_capability(
        capability,
        action=wanted_action,
        occurrence=wanted_occurrence,
        scope=_text(scope) or wanted_action,
    )
    if minted.target != wanted_target:
        raise MutationDenied(
            f"capability target {minted.target!r} does not match {wanted_target!r}",
            code="target_mismatch",
        )
    if minted.fence_epoch != fence_epoch:
        raise MutationDenied(
            f"capability fence epoch {minted.fence_epoch!r} does not match {fence_epoch!r}",
            code="stale_fence",
        )
    return minted


def require_production_operator_binding(
    args: Any,
    *,
    action: str,
    scope: str,
) -> MutationCapability:
    """Bind production CLI args to one minted capability and exact identity."""

    occurrence = str(
        getattr(args, "occurrence", None)
        or getattr(args, "expected_session_id", None)
        or ""
    ).strip()
    target = str(
        getattr(args, "bound_target", None)
        or getattr(args, "target", None)
        or occurrence
    ).strip()
    fence_raw = getattr(args, "fence_epoch", None)
    try:
        fence_epoch = int(fence_raw) if fence_raw is not None else None
    except (TypeError, ValueError):
        fence_epoch = None
    handle = str(getattr(args, "capability_handle", None) or occurrence).strip()
    capability = resolve_mutation_capability(handle)
    if capability is None:
        capability = getattr(args, "mutation_capability", None)
    if capability is None or not occurrence or not target or fence_epoch is None:
        raise MutationDenied(
            f"{action} requires a minted MutationCapability bound to "
            "action, occurrence, target, and fence epoch",
            code="capability_absent",
        )
    return bind_operator_intent(
        capability,
        action=action,
        occurrence=occurrence,
        target=target,
        fence_epoch=fence_epoch,
        scope=scope,
    )



def _adoption_path(root: Path, occurrence: str) -> Path:
    # Diagnostic fixture path only. Production adoption writes the fce owner
    # record under plan evidence/occurrence-adoptions/.
    directory = root / ".megaplan" / "plans"
    return directory / f"{occurrence}.adoption-binding.json"


def _refuse_operational_authority(evidence: Mapping[str, Any] | None) -> None:
    if not isinstance(evidence, Mapping):
        return
    present = [key for key in _OPERATIONAL_EVIDENCE_KEYS if evidence.get(key) not in (None, "", False)]
    if present and evidence.get("authorizes_from_operational_evidence") is True:
        raise MutationDenied(
            "PID, tmux, repo-path similarity, stopped lease, or stale marker "
            "cannot authorize adoption",
            code="operational_evidence_not_authority",
        )
    # Diagnostic operational facts may be present. They never grant adoption
    # even when a caller omits the explicit claim flag.
    if present and not evidence.get("capability") and not evidence.get("mutation_capability"):
        # Capability is supplied separately; leftover operational keys are ignored.
        return



def guarded_occurrence_adoption(
    *,
    capability: MutationCapability | Mapping[str, Any] | None,
    occurrence: str,
    target: str,
    fence_epoch: int,
    binding_root: Path | None = None,
    plan: Mapping[str, Any] | None = None,
    runtime_identity: Mapping[str, Any] | None = None,
    expected_plan: str = "",
    expected_runtime: str = "",
    evidence: Mapping[str, Any] | None = None,
    fce_adopt: Any | None = None,
    fce_kwargs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Adopt one exact occurrence under a minted root capability.

    Idempotent for the same bound identity. Fails closed on any occurrence,
    plan, runtime, target, or fence contradiction. Never consults PID, tmux,
    path similarity, lease, or marker as a grant. Does not rewrite the
    resume cursor or plan payload.
    """

    root = assert_disposable_root(binding_root) if binding_root is not None else None
    _refuse_operational_authority(evidence)
    capability = bind_operator_intent(
        capability,
        action=ADOPTION_ACTION,
        occurrence=occurrence,
        target=target,
        fence_epoch=fence_epoch,
        scope=ADOPTION_ACTION,
    )
    plan_name = ""
    runtime_name = ""
    if isinstance(plan, Mapping):
        plan_name = _text(plan.get("name") or plan.get("plan") or expected_plan)
        cursor_before = resume_cursor_bytes(plan)
        payload_before = plan_payload_without_pause(plan)
    else:
        cursor_before = b""
        payload_before = b""
    if expected_plan and plan_name and expected_plan != plan_name:
        raise CliError(
            "plan_mismatch",
            f"adoption refused: plan {plan_name!r} does not match {expected_plan!r}",
        )
    if isinstance(runtime_identity, Mapping):
        runtime_name = _text(
            runtime_identity.get("import_root")
            or runtime_identity.get("runtime_root")
            or expected_runtime
        )
    if expected_runtime and runtime_name and expected_runtime != runtime_name:
        raise CliError(
            "runtime_mismatch",
            f"adoption refused: runtime {runtime_name!r} does not match {expected_runtime!r}",
        )
    if capability.import_root and runtime_name:
        if Path(capability.import_root).resolve() != Path(runtime_name).expanduser().resolve():
            raise CliError(
                "runtime_mismatch",
                "adoption refused: capability import_root does not match runtime identity",
            )

    record = {
        "schema": ADOPTION_SCHEMA,
        "action": ADOPTION_ACTION,
        "occurrence": capability.occurrence,
        "target": capability.target,
        "fence_epoch": capability.fence_epoch,
        "import_root": capability.import_root,
        "interpreter": capability.interpreter,
        "plan": plan_name or expected_plan,
        "runtime": runtime_name or expected_runtime,
        "cursor_sha256": resume_cursor_bytes(plan or {}).hex() if plan else "",
    }
    if fce_adopt is not None:
        result = fce_adopt(**dict(fce_kwargs or {}))
        result["bound_occurrence"] = capability.occurrence
        result["bound_target"] = capability.target
        result["bound_fence_epoch"] = capability.fence_epoch
        result["bound_action"] = ADOPTION_ACTION
        result["record"] = record
        if isinstance(plan, Mapping):
            if resume_cursor_bytes(plan) != cursor_before:
                raise CliError("cursor_mutated", "adoption must not move the logical resume cursor")
            if plan_payload_without_pause(plan) != payload_before:
                raise CliError("plan_payload_mutated", "adoption must not alter the plan payload")
        return result

    # Fixture-only identity proof: no parallel store. Same bound identity is
    # idempotent in-process via the fce owner when production calls.
    if isinstance(plan, Mapping):
        if resume_cursor_bytes(plan) != cursor_before:
            raise CliError("cursor_mutated", "adoption must not move the logical resume cursor")
        if plan_payload_without_pause(plan) != payload_before:
            raise CliError("plan_payload_mutated", "adoption must not alter the plan payload")
    if root is None:
        return {"changed": True, "adopted": True, "record": record}
    # Fixture identity is recorded beside the disposable plan tree in the same
    # fce evidence layout so there is no second adoption authority.
    evidence_dir = root / ".megaplan" / "evidence" / "occurrence-adoptions"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / "current.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        identity_keys = ("occurrence", "target", "fence_epoch", "action")
        existing_id = {key: existing.get(key) for key in identity_keys}
        requested_id = {key: record.get(key) for key in identity_keys}
        if existing_id != requested_id:
            raise CliError(
                "identity_contradiction",
                "duplicate adoption with a different bound identity fails closed",
                extra={"existing": existing, "requested": record},
            )
        return {"changed": False, "adopted": True, "record": existing, "path": str(path)}
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return {"changed": True, "adopted": True, "record": record, "path": str(path)}


__all__ = [
    "ADOPTION_ACTION",
    "ADOPTION_SCHEMA",
    "assert_disposable_root",
    "bind_operator_intent",
    "require_production_operator_binding",
    "guarded_occurrence_adoption",
    "plan_payload_without_pause",
    "resume_cursor_bytes",
]
