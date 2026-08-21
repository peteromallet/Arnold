"""Cloud fce owner for ``pause_chain`` / ``reconcile_quiesced_plan_pause`` (T4.2).

G0/J2 freeze: these remain the fce pause primitives. This module binds
operator intent to one exact action, occurrence, target, root
``MutationCapability``, and fence epoch, then delegates to the existing
chain owners. It never infers pause from PID, tmux, lease, or marker
observation, and never rewrites the logical resume cursor or plan payload.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.chain.operator_pause import (
    pause_chain as _fce_pause_chain,
    reconcile_quiesced_plan_pause as _fce_reconcile_quiesced_plan_pause,
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

PAUSE_ACTION = "pause_chain"
RECONCILE_ACTION = "reconcile_quiesced_plan_pause"


def _load_plan(project_root: Path, plan_name: str | None) -> dict[str, Any] | None:
    if not plan_name:
        return None
    path = Path(project_root) / ".megaplan" / "plans" / plan_name / "state.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def pause_chain(
    spec_path: Path,
    project_root: Path,
    *,
    reason: str,
    actor: str = "operator",
    capability: MutationCapability | Mapping[str, Any] | None = None,
    occurrence: str = "",
    target: str = "",
    fence_epoch: int | None = None,
    binding_root: Path | None = None,
) -> dict[str, Any]:
    """Persist pause authority without moving the resume cursor or plan payload.

    Operator intent must name one action/occurrence/target/capability/epoch.
    Replay of a valid token against another occurrence or action rejects.
    Duplicate pause of the same bound identity is idempotent.
    """

    if binding_root is not None:
        assert_disposable_root(binding_root)
    if capability is None or not occurrence or not target or fence_epoch is None:
        raise MutationDenied(
            "pause_chain requires a minted MutationCapability bound to "
            "action, occurrence, target, and fence epoch",
            code="capability_absent",
        )
    minted = bind_operator_intent(
        capability,
        action=PAUSE_ACTION,
        occurrence=occurrence,
        target=target,
        fence_epoch=fence_epoch,
        scope=PAUSE_ACTION,
    )
    plan_before = None
    cursor_before = b""
    payload_before = b""
    from arnold_pipelines.megaplan.chain import spec as chain_spec

    state = chain_spec.load_chain_state(spec_path)
    plan_before = _load_plan(project_root, state.current_plan_name)
    if isinstance(plan_before, Mapping):
        cursor_before = resume_cursor_bytes(plan_before)
        payload_before = plan_payload_without_pause(plan_before)

    result = _fce_pause_chain(
        spec_path,
        project_root,
        reason=reason,
        actor=actor,
        occurrence=minted.occurrence,
        target=minted.target,
        capability_token=minted.token,
        fence_epoch=minted.fence_epoch,
    )
    plan_after = _load_plan(project_root, state.current_plan_name)
    if isinstance(plan_before, Mapping) and isinstance(plan_after, Mapping):
        if resume_cursor_bytes(plan_after) != cursor_before:
            raise CliError(
                "cursor_mutated",
                "pause_chain must not move the logical resume cursor",
            )
        if plan_payload_without_pause(plan_after) != payload_before:
            raise CliError(
                "plan_payload_mutated",
                "pause_chain may append pause metadata but cannot alter the plan payload",
            )
    result["bound_occurrence"] = occurrence
    result["bound_target"] = target
    result["bound_fence_epoch"] = fence_epoch
    result["bound_action"] = PAUSE_ACTION
    return result


def reconcile_quiesced_plan_pause(
    spec_path: Path,
    project_root: Path,
    *,
    session: str,
    authority: Mapping[str, Any],
    capability: MutationCapability | Mapping[str, Any] | None = None,
    occurrence: str = "",
    target: str = "",
    fence_epoch: int | None = None,
    binding_root: Path | None = None,
) -> bool:
    """Converge the writer-after-pause race. Liveness is observation only."""

    if binding_root is not None:
        assert_disposable_root(binding_root)
    if capability is None or not occurrence or not target or fence_epoch is None:
        raise MutationDenied(
            "reconcile_quiesced_plan_pause requires a minted MutationCapability",
            code="capability_absent",
        )
    minted_action = getattr(capability, "action", RECONCILE_ACTION) or RECONCILE_ACTION
    if minted_action not in {RECONCILE_ACTION, PAUSE_ACTION}:
        raise MutationDenied(
            f"capability action {minted_action!r} cannot authorize pause reconcile",
            code="action_mismatch",
        )
    bind_operator_intent(
        capability,
        action=minted_action,
        occurrence=occurrence,
        target=target,
        fence_epoch=fence_epoch,
        scope=getattr(capability, "scope", minted_action) or minted_action,
    )
    return _fce_reconcile_quiesced_plan_pause(
        spec_path,
        project_root,
        session=session,
        authority=authority,
    )



def resume_chain(
    spec_path: Path,
    project_root: Path,
    *,
    actor: str = "operator",
    capability: MutationCapability | Mapping[str, Any] | None = None,
    occurrence: str = "",
    target: str = "",
    fence_epoch: int | None = None,
    verify_execution_binding: bool = True,
    expected_resume_authority: Mapping[str, Any] | None = None,
    allow_legacy_authority_cleared_hold: bool = False,
    binding_root: Path | None = None,
) -> dict[str, Any]:
    """Clear pause authority only for the exact bound identity."""

    from arnold_pipelines.megaplan.chain.operator_pause import (
        resume_chain as _fce_resume_chain,
    )

    if binding_root is not None:
        assert_disposable_root(binding_root)
    if capability is None or not occurrence or not target or fence_epoch is None:
        raise MutationDenied(
            "resume_chain requires a minted MutationCapability bound to "
            "action, occurrence, target, and fence epoch",
            code="capability_absent",
        )
    minted_action = getattr(capability, "action", PAUSE_ACTION) or PAUSE_ACTION
    if minted_action not in {PAUSE_ACTION, "resume_chain"}:
        raise MutationDenied(
            f"capability action {minted_action!r} cannot authorize resume",
            code="action_mismatch",
        )
    bind_operator_intent(
        capability,
        action=minted_action,
        occurrence=occurrence,
        target=target,
        fence_epoch=fence_epoch,
        scope=getattr(capability, "scope", minted_action) or minted_action,
    )
    return _fce_resume_chain(
        spec_path,
        project_root,
        actor=actor,
        verify_execution_binding=verify_execution_binding,
        expected_resume_authority=expected_resume_authority,
        allow_legacy_authority_cleared_hold=allow_legacy_authority_cleared_hold,
    )


__all__ = [
    "PAUSE_ACTION",
    "RECONCILE_ACTION",
    "pause_chain",
    "reconcile_quiesced_plan_pause",
    "resume_chain",
]
