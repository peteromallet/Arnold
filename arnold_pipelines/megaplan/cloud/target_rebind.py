"""Cloud fce owner for ``target_rebind`` (T4.2).

J2 freeze: rebind CAS is import_root + generation interpreter (Live Tree
Authority). This module binds operator intent, accepts milestone identity
label ``m7`` and rejects sequence index ``6`` with an error identifying
``_identity_labels``, then delegates to the existing fce
``chain.target_rebind.target_rebind``. Rollback restores the exact prior
binding. Cursor and plan payload stay byte-equivalent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold_pipelines.megaplan.chain.execution_binding import _identity_labels
from arnold_pipelines.megaplan.chain.target_rebind import (
    target_rebind as _fce_target_rebind,
)
from arnold_pipelines.megaplan.cloud.current_target_liveness import (
    MutationCapability,
    MutationDenied,
)
from arnold_pipelines.megaplan.cloud.occurrence_adoption import (
    assert_disposable_root,
    bind_operator_intent,
    plan_payload_without_pause,
    resume_cursor_bytes,
)
from arnold_pipelines.megaplan.types import CliError

REBIND_ACTION = "target_rebind"
MILESTONE_LABEL_M7 = "m7"
SEQUENCE_INDEX_FORBIDDEN = "6"


def require_milestone_identity_label(
    expected_current_milestone: str,
    *,
    identity: Mapping[str, Any] | None = None,
) -> str:
    """Accept label ``m7``; reject numeric sequence index ``6``.

    The error names ``_identity_labels`` so callers cannot authorize rebind
    by a sequence index.
    """

    label = str(expected_current_milestone or "").strip()
    if label == SEQUENCE_INDEX_FORBIDDEN or label.isdigit():
        raise CliError(
            "chain_runtime_binding_drift",
            "runtime-rebind refused: expected_current_milestone must be a "
            "milestone identity label from _identity_labels, not a sequence "
            f"index ({label!r}); use {MILESTONE_LABEL_M7!r}",
            extra={
                "guard": "_identity_labels",
                "rejected": label,
                "accepted_example": MILESTONE_LABEL_M7,
            },
        )
    if identity is not None:
        labels = _identity_labels(identity)
        if labels and label not in labels:
            raise CliError(
                "chain_runtime_binding_drift",
                "runtime-rebind refused: expected_current_milestone is not in "
                "_identity_labels",
                extra={"guard": "_identity_labels", "labels": labels, "requested": label},
            )
    if label != MILESTONE_LABEL_M7 and identity is None:
        # Isolated fixer-contract fixture: only m7 is the authorized recovery
        # identity. Broader fce cutover still names the exact current label
        # when an identity sequence is supplied.
        raise CliError(
            "chain_runtime_binding_drift",
            "runtime-rebind refused: fixer recovery requires milestone "
            f"identity label {MILESTONE_LABEL_M7!r} from _identity_labels",
            extra={"guard": "_identity_labels", "requested": label},
        )
    return label


def _load_plan(project_root: Path, plan_name: str) -> dict[str, Any] | None:
    path = Path(project_root) / ".megaplan" / "plans" / plan_name / "state.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def target_rebind(
    spec_path: Path,
    project_root: Path,
    *,
    direction: str,
    expected_session_id: str,
    expected_current_milestone: str,
    expected_current_plan: str,
    from_branch: str,
    from_head: str,
    from_milestone_base: str,
    from_ref: str,
    to_branch: str,
    to_head: str,
    to_ref: str,
    expected_spec_sha256: str,
    expected_chain_state_sha256: str,
    expected_plan_state_sha256: str,
    reason: str,
    actor: str = "operator",
    expected_target_spec_sha256: str | None = None,
    verified_external_runtime_identity: Mapping[str, Any] | None = None,
    failure_injector: Callable[[str], None] | None = None,
    capability: MutationCapability | Mapping[str, Any] | None = None,
    occurrence: str = "",
    target: str = "",
    fence_epoch: int | None = None,
    binding_root: Path | None = None,
    identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Cut over or roll back only the explicitly authorized binding under CAS/fence."""

    if binding_root is not None:
        assert_disposable_root(binding_root)
    if capability is None or not occurrence or not target or fence_epoch is None:
        raise MutationDenied(
            "target_rebind requires a minted MutationCapability bound to "
            "action, occurrence, target, and fence epoch",
            code="capability_absent",
        )
    minted = bind_operator_intent(
        capability,
        action=REBIND_ACTION,
        occurrence=occurrence,
        target=target,
        fence_epoch=fence_epoch,
        scope=REBIND_ACTION,
    )
    label = require_milestone_identity_label(
        expected_current_milestone,
        identity=identity,
    )
    if minted.import_root and verified_external_runtime_identity:
        live = str(
            verified_external_runtime_identity.get("import_root")
            or verified_external_runtime_identity.get("runtime_root")
            or ""
        ).strip()
        if live and Path(minted.import_root).resolve() != Path(live).expanduser().resolve():
            raise MutationDenied(
                "rebind CAS is import_root plus generation interpreter; "
                "runtime identity import_root does not match the capability",
                code="import_root_mismatch",
            )

    plan_before = _load_plan(project_root, expected_current_plan)
    cursor_before = resume_cursor_bytes(plan_before or {})
    payload_before = plan_payload_without_pause(plan_before or {}) if plan_before else b""

    result = _fce_target_rebind(
        spec_path,
        project_root,
        direction=direction,
        expected_session_id=expected_session_id,
        expected_current_milestone=label,
        expected_current_plan=expected_current_plan,
        from_branch=from_branch,
        from_head=from_head,
        from_milestone_base=from_milestone_base,
        from_ref=from_ref,
        to_branch=to_branch,
        to_head=to_head,
        to_ref=to_ref,
        expected_spec_sha256=expected_spec_sha256,
        expected_target_spec_sha256=expected_target_spec_sha256,
        expected_chain_state_sha256=expected_chain_state_sha256,
        expected_plan_state_sha256=expected_plan_state_sha256,
        reason=reason,
        actor=actor,
        verified_external_runtime_identity=verified_external_runtime_identity,
        failure_injector=failure_injector,
    )
    plan_after = _load_plan(project_root, expected_current_plan)
    if plan_before is not None and plan_after is not None:
        if resume_cursor_bytes(plan_after) != cursor_before:
            raise CliError(
                "cursor_mutated",
                "target_rebind must not move the logical resume cursor",
            )
        if plan_payload_without_pause(plan_after) != payload_before:
            raise CliError(
                "plan_payload_mutated",
                "target_rebind may append receipts but cannot alter the plan payload",
            )
    result["bound_occurrence"] = occurrence
    result["bound_target"] = target
    result["bound_fence_epoch"] = fence_epoch
    result["bound_action"] = REBIND_ACTION
    result["milestone_label"] = label
    return result


def runtime_rebind(
    *,
    capability: MutationCapability | Mapping[str, Any] | None,
    occurrence: str,
    target: str,
    fence_epoch: int,
    expected_current_milestone: str,
    binding_root: Path,
    from_import_root: str,
    from_interpreter: str,
    to_import_root: str,
    to_interpreter: str,
    direction: str = "cutover",
    identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebind only import_root + generation interpreter under CAS/fence.

    Live Tree Authority: Git SHA is telemetry, not the CAS. Rollback returns
    the exact prior binding. Label ``m7`` is required; index ``6`` is refused
    with an error naming ``_identity_labels``.
    """

    root = assert_disposable_root(binding_root)
    if direction not in {"cutover", "rollback"}:
        raise CliError("project_source_rebind_refused", "direction must be cutover or rollback")
    minted = bind_operator_intent(
        capability,
        action=REBIND_ACTION,
        occurrence=occurrence,
        target=target,
        fence_epoch=fence_epoch,
        scope=REBIND_ACTION,
    )
    label = require_milestone_identity_label(
        expected_current_milestone,
        identity=identity,
    )
    store = root / ".t42-runtime-binding.json"
    prior = json.loads(store.read_text(encoding="utf-8")) if store.exists() else None
    from_root = str(Path(from_import_root).expanduser().resolve())
    from_python = str(Path(from_interpreter).expanduser().resolve())
    to_root = str(Path(to_import_root).expanduser().resolve())
    to_python = str(Path(to_interpreter).expanduser().resolve())
    if direction == "cutover" and Path(minted.import_root).resolve() != Path(from_root):
        raise MutationDenied(
            "rebind CAS is import_root plus generation interpreter",
            code="import_root_mismatch",
        )
    if direction == "cutover":
        binding = {
            "schema": "arnold.megaplan.t42-runtime-rebind.v1",
            "direction": "cutover",
            "occurrence": minted.occurrence,
            "target": minted.target,
            "fence_epoch": minted.fence_epoch,
            "milestone_label": label,
            "from": {"import_root": from_root, "interpreter": from_python},
            "to": {"import_root": to_root, "interpreter": to_python},
        }
        store.write_text(json.dumps(binding, indent=2) + "\n", encoding="utf-8")
        return {"changed": True, "binding": binding, "prior": prior, "path": str(store)}
    if prior is None:
        raise CliError(
            "project_source_rebind_refused",
            "rollback requires the exact prior binding",
        )
    expected_from = prior.get("to") if isinstance(prior, Mapping) else None
    expected_to = prior.get("from") if isinstance(prior, Mapping) else None
    if not isinstance(expected_from, Mapping) or not isinstance(expected_to, Mapping):
        raise CliError("project_source_rebind_refused", "prior binding is malformed")
    if (
        str(expected_from.get("import_root")) != from_root
        or str(expected_from.get("interpreter")) != from_python
        or str(expected_to.get("import_root")) != to_root
        or str(expected_to.get("interpreter")) != to_python
    ):
        raise CliError(
            "project_source_rebind_refused",
            "rollback must return to the exact prior binding",
            extra={"prior": prior, "requested_from": from_root, "requested_to": to_root},
        )
    rolled = {
        "schema": "arnold.megaplan.t42-runtime-rebind.v1",
        "direction": "rollback",
        "occurrence": minted.occurrence,
        "target": minted.target,
        "fence_epoch": minted.fence_epoch,
        "milestone_label": label,
        "from": {"import_root": from_root, "interpreter": from_python},
        "to": {"import_root": to_root, "interpreter": to_python},
        "restored": dict(expected_to),
    }
    store.write_text(json.dumps(rolled, indent=2) + "\n", encoding="utf-8")
    return {"changed": True, "binding": rolled, "prior": prior, "path": str(store)}


__all__ = [
    "MILESTONE_LABEL_M7",
    "REBIND_ACTION",
    "SEQUENCE_INDEX_FORBIDDEN",
    "require_milestone_identity_label",
    "runtime_rebind",
    "target_rebind",
]
