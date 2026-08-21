"""T4.3 delivery/cutover coordinator: consumer of frozen fce owners.

J2 freeze owner order (do not add a second pause/quiescence/rebind/claim
authority; do not port 7272 prepare/commit facades):

1. MutationCapability
2. pause_chain + reconcile_quiesced_plan_pause
3. quiesced-writer proof (observe_liveness_lease is observation only)
4. target_rebind / runtime_rebind direction=cutover under import_root +
   generation-interpreter CAS
5. apply_runtime_manifest_cutover / write_manifest under one lock + rollback
   receipt
6. update_marker_runtime
7. existing fce cutover_runtime_identity thin wrapper
8. rollback via target_rebind/runtime_rebind direction=rollback + verified
   fce rollback receipt restoring the prior selection

Live delivery is out of scope. Tests and callers must pass an explicit
disposable binding_root that is not a project, candidate, or live runtime.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold_pipelines.megaplan.chain.execution_binding import cutover_runtime_identity
from arnold_pipelines.megaplan.cloud.current_target_liveness import (
    MutationCapability,
    MutationDenied,
    require_mutation_capability,
)
from arnold_pipelines.megaplan.cloud.liveness_lease import observe_liveness_lease
from arnold_pipelines.megaplan.cloud.occurrence_adoption import (
    assert_disposable_root,
    bind_operator_intent,
    plan_payload_without_pause,
    resume_cursor_bytes,
)
from arnold_pipelines.megaplan.cloud.operator_pause import (
    PAUSE_ACTION,
    pause_chain,
    reconcile_quiesced_plan_pause,
)
from arnold_pipelines.megaplan.cloud.runtime_cutover import (
    marker_runtime_identity,
    update_marker_runtime,
)
from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    RuntimeManifest,
    apply_runtime_manifest_cutover,
    load_manifest,
    write_manifest,
)
from arnold_pipelines.megaplan.cloud.runtime_provenance import (
    verify_runtime_manifest_cutover_rollback_receipt,
)
from arnold_pipelines.megaplan.cloud.target_rebind import (
    REBIND_ACTION,
    runtime_rebind,
    target_rebind,
)
from arnold_pipelines.megaplan.types import CliError

CUTOVER_ACTION = "maintenance_cutover"
DELIVERY_JOURNAL_SCHEMA = "arnold.megaplan.maintenance_delivery_journal.v1"
DELIVERY_SENTINEL = ".t43-disposable-root"
PUBLICATION_BOUNDARIES = (
    "before_pause",
    "after_pause",
    "after_quiesce",
    "after_rebind",
    "before_selector",
    "after_selector",
    "after_receipt",
    "before_marker",
    "after_marker",
    "before_identity",
    "after_identity",
    "committed",
)
_ALLOWED_ROOT_ACTIONS = frozenset(
    {CUTOVER_ACTION, "engine_runtime", PAUSE_ACTION, REBIND_ACTION}
)
_LIVE_LEASE_STATES = frozenset({"live"})


def _canonical_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_plan(project_root: Path, plan_name: str | None) -> dict[str, Any] | None:
    if not plan_name:
        return None
    path = Path(project_root) / ".megaplan" / "plans" / plan_name / "state.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _journal_path(binding_root: Path) -> Path:
    return (
        Path(binding_root)
        / ".megaplan"
        / "plans"
        / "fixture"
        / "evidence"
        / "delivery-journal.json"
    )


def _write_journal(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(dict(payload), indent=2, sort_keys=True) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(encoded, encoding="utf-8")
    tmp.replace(path)


def _load_journal(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _inject(failure_injector: Callable[[str], None] | None, boundary: str) -> None:
    if failure_injector is not None:
        failure_injector(boundary)


def _refuse_report_trigger(report: Mapping[str, Any] | None) -> None:
    if report is not None:
        raise CliError(
            "report_cannot_trigger_delivery",
            "no report directly triggers delivery; cutover requires a minted "
            "root MutationCapability and T4.2 pause/quiescence proof",
        )


def _bind_root_capability(
    capability: MutationCapability | Mapping[str, Any] | None,
    *,
    occurrence: str,
    target: str,
    fence_epoch: int,
) -> MutationCapability:
    if capability is None:
        raise MutationDenied(
            "cutover requires a minted root MutationCapability",
            code="capability_absent",
        )
    action = str(getattr(capability, "action", "") or CUTOVER_ACTION)
    if action not in _ALLOWED_ROOT_ACTIONS:
        raise MutationDenied(
            f"capability action {action!r} cannot authorize maintenance cutover",
            code="action_mismatch",
        )
    return bind_operator_intent(
        capability,
        action=action,
        occurrence=occurrence,
        target=target,
        fence_epoch=fence_epoch,
        scope=getattr(capability, "scope", action) or action,
    )


def prove_quiesced_writers(
    marker: Mapping[str, Any],
    *,
    marker_dir: Path,
) -> dict[str, Any]:
    """Observation-only quiesced-writer proof. Live leases refuse cutover."""

    observed = observe_liveness_lease(marker, marker_dir=Path(marker_dir))
    if observed.get("live") is True or observed.get("state") in _LIVE_LEASE_STATES:
        raise CliError(
            "live_writer_refused",
            "cutover refuses live writers; observe_liveness_lease is not a grant",
            extra={"lease": observed},
        )
    return {
        "quiesced": True,
        "lease_state": observed.get("state"),
        "live": False,
        "observation_only": True,
        "lease": observed,
    }


def _selection_snapshot(
    *,
    manifest_path: Path,
    marker_path: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    identity = marker_runtime_identity(marker) or {}
    epic = manifest.get("epic") if isinstance(manifest.get("epic"), Mapping) else {}
    return {
        "manifest_sha256": _sha256_file(manifest_path),
        "marker_sha256": _sha256_file(marker_path),
        "generation": manifest.get("generation"),
        "runtime_root": epic.get("runtime_root"),
        "expected_head": epic.get("expected_head"),
        "interpreter": (epic.get("dependency_generation") or {}).get("interpreter_path")
        if isinstance(epic.get("dependency_generation"), Mapping)
        else None,
        "marker_import_root": identity.get("import_root"),
        "marker_source_revision": identity.get("source_revision"),
        "marker_runtime_sha256": identity.get("content_sha256"),
    }


def _assert_selector_marker_match(
    *,
    manifest_path: Path,
    marker_path: Path,
    allow_torn: bool = False,
) -> None:
    snapshot = _selection_snapshot(manifest_path=manifest_path, marker_path=marker_path)
    manifest_root = str(snapshot.get("runtime_root") or "").strip()
    marker_root = str(snapshot.get("marker_import_root") or "").strip()
    if not manifest_root or not marker_root:
        raise CliError(
            "manifest_marker_mismatch",
            "cutover refuses incomplete selector/marker identity",
            extra=snapshot,
        )
    if Path(manifest_root).expanduser().resolve() != Path(marker_root).expanduser().resolve():
        if allow_torn:
            return
        raise CliError(
            "manifest_marker_mismatch",
            "cutover refuses manifest/marker import_root mismatch",
            extra=snapshot,
        )


def _same_root(left: str, right: str) -> bool:
    if not str(left or "").strip() or not str(right or "").strip():
        return False
    return Path(left).expanduser().resolve() == Path(right).expanduser().resolve()


def _selector_already_cut_over(
    *,
    manifest_path: Path,
    to_runtime_root: str,
    expect_generation: int,
) -> bool:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    epic = manifest.get("epic") if isinstance(manifest.get("epic"), Mapping) else {}
    return _same_root(str(epic.get("runtime_root") or ""), to_runtime_root) and int(
        manifest.get("generation") or 0
    ) == int(expect_generation) + 1


def _marker_already_cut_over(
    *,
    marker_path: Path,
    active_runtime_identity: Mapping[str, Any],
) -> bool:
    marker = json.loads(Path(marker_path).read_text(encoding="utf-8"))
    current = marker_runtime_identity(marker) or {}
    wanted = marker_runtime_identity({"runtime_binding": {"current_identity": dict(active_runtime_identity)}}) or {}
    return bool(
        current.get("content_sha256")
        and current.get("content_sha256") == wanted.get("content_sha256")
    )


def _idempotency_key(
    *,
    occurrence: str,
    from_import_root: str,
    to_import_root: str,
) -> str:
    return _canonical_digest(
        {
            "occurrence": occurrence,
            "from_import_root": str(Path(from_import_root).expanduser().resolve()),
            "to_import_root": str(Path(to_import_root).expanduser().resolve()),
        }
    )


def deliver_runtime_cutover(
    *,
    capability: MutationCapability | Mapping[str, Any] | None,
    occurrence: str,
    target: str,
    fence_epoch: int,
    binding_root: Path,
    spec_path: Path,
    project_root: Path,
    reason: str,
    actor: str = "operator",
    pause_capability: MutationCapability | Mapping[str, Any] | None = None,
    rebind_capability: MutationCapability | Mapping[str, Any] | None = None,
    pause_session: str = "",
    expected_current_milestone: str = "m7",
    expected_current_plan: str = "",
    identity: Mapping[str, Any] | None = None,
    from_import_root: str,
    from_interpreter: str,
    to_import_root: str,
    to_interpreter: str,
    manifest_path: Path,
    expect_manifest_sha256: str,
    expect_generation: int,
    from_runtime_root: str,
    from_expected_head: str,
    to_runtime_root: str,
    to_expected_head: str,
    to_venv_path: str,
    to_repair_bin: str,
    runtime_identity_path: Path,
    runtime_provenance_receipt_path: Path,
    receipt_path: Path | None = None,
    to_dependency_generation: Mapping[str, Any] | None = None,
    marker_path: Path,
    expected_marker_sha256: str,
    expected_previous_runtime_sha256: str,
    active_runtime_identity: Mapping[str, Any],
    relaunch_command: str,
    source_branch: str = "",
    marker: Mapping[str, Any],
    marker_dir: Path,
    chain_state: Any | None = None,
    expected_previous_runtime_sha256_identity: str = "",
    expected_active_runtime_sha256_identity: str = "",
    verified_external_runtime_identity: Mapping[str, Any] | None = None,
    target_rebind_kwargs: Mapping[str, Any] | None = None,
    failure_injector: Callable[[str], None] | None = None,
    report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the frozen fce-owner cutover order against disposable fixtures."""

    _refuse_report_trigger(report)
    root = assert_disposable_root(binding_root)
    (root / DELIVERY_SENTINEL).write_text("disposable\n", encoding="utf-8")
    minted = _bind_root_capability(
        capability,
        occurrence=occurrence,
        target=target,
        fence_epoch=fence_epoch,
    )
    require_mutation_capability(
        minted,
        action=minted.action,
        occurrence=occurrence,
        scope=minted.scope,
    )

    if pause_capability is None or rebind_capability is None:
        raise MutationDenied(
            "cutover requires T4.2 pause and rebind capabilities in frozen order",
            code="capability_absent",
        )
    pause_cap = pause_capability
    rebind_cap = rebind_capability
    key = _idempotency_key(
        occurrence=occurrence,
        from_import_root=from_import_root,
        to_import_root=to_import_root,
    )
    journal_path = _journal_path(root)
    existing = _load_journal(journal_path)

    plan_before = _load_plan(project_root, expected_current_plan)
    cursor_before = resume_cursor_bytes(plan_before or {})
    payload_before = (
        plan_payload_without_pause(plan_before) if isinstance(plan_before, Mapping) else b""
    )
    torn = bool(
        isinstance(existing, Mapping)
        and existing.get("idempotency_key") == key
        and existing.get("status") in {"in_progress", "committed"}
        and (
            existing.get("status") == "in_progress"
            or _selector_already_cut_over(
                manifest_path=Path(manifest_path),
                to_runtime_root=to_runtime_root,
                expect_generation=expect_generation,
            )
            or _marker_already_cut_over(
                marker_path=Path(marker_path),
                active_runtime_identity=active_runtime_identity,
            )
        )
    )
    if (
        isinstance(existing, Mapping)
        and existing.get("schema") == DELIVERY_JOURNAL_SCHEMA
        and existing.get("idempotency_key") == key
        and existing.get("status") == "committed"
        and _selector_already_cut_over(
            manifest_path=Path(manifest_path),
            to_runtime_root=to_runtime_root,
            expect_generation=expect_generation,
        )
        and _marker_already_cut_over(
            marker_path=Path(marker_path),
            active_runtime_identity=active_runtime_identity,
        )
    ):
        return {
            "changed": False,
            "duplicate": True,
            "status": "committed",
            "idempotent": True,
            "journal": existing,
        }
    torn_mismatch = bool(
        isinstance(existing, Mapping)
        and existing.get("status") == "in_progress"
        and existing.get("idempotency_key") == key
    )
    _assert_selector_marker_match(
        manifest_path=Path(manifest_path),
        marker_path=Path(marker_path),
        allow_torn=torn_mismatch,
    )
    prior_selection = (
        dict(existing.get("prior_selection"))
        if torn and isinstance(existing.get("prior_selection"), Mapping)
        else _selection_snapshot(
            manifest_path=Path(manifest_path),
            marker_path=Path(marker_path),
        )
    )

    journal: dict[str, Any] = dict(existing) if isinstance(existing, Mapping) else {}
    journal.update(
        {
            "schema": DELIVERY_JOURNAL_SCHEMA,
            "status": "in_progress",
            "idempotency_key": key,
            "occurrence": occurrence,
            "target": target,
            "fence_epoch": fence_epoch,
            "prior_selection": prior_selection,
            "resumable": True,
        }
    )
    _write_journal(journal_path, journal)

    try:
        _inject(failure_injector, "before_pause")
        pause_result = pause_chain(
            Path(spec_path),
            Path(project_root),
            reason=reason,
            actor=actor,
            capability=pause_cap,
            occurrence=occurrence,
            target=target,
            fence_epoch=fence_epoch,
            binding_root=root,
        )
        session = pause_session or str(Path(project_root).name)
        if pause_result.get("changed"):
            reconcile_quiesced_plan_pause(
                Path(spec_path),
                Path(project_root),
                session=session,
                authority=pause_result["authority"],
                capability=pause_cap,
                occurrence=occurrence,
                target=target,
                fence_epoch=fence_epoch,
                binding_root=root,
            )
        journal["pause"] = {
            "paused": pause_result.get("paused"),
            "changed": pause_result.get("changed"),
        }
        journal["stage"] = "after_pause"
        _write_journal(journal_path, journal)
        _inject(failure_injector, "after_pause")

        quiesce = prove_quiesced_writers(marker, marker_dir=Path(marker_dir))
        journal["quiesce"] = {
            "lease_state": quiesce.get("lease_state"),
            "observation_only": True,
        }
        journal["stage"] = "after_quiesce"
        _write_journal(journal_path, journal)
        _inject(failure_injector, "after_quiesce")

        rebind_result = runtime_rebind(
            Path(spec_path) if target_rebind_kwargs else None,
            chain_state if target_rebind_kwargs else None,
            capability=rebind_cap,
            occurrence=occurrence,
            target=target,
            fence_epoch=fence_epoch,
            expected_current_milestone=expected_current_milestone,
            expected_current_plan=expected_current_plan,
            from_import_root=from_import_root,
            from_interpreter=from_interpreter,
            to_import_root=to_import_root,
            to_interpreter=to_interpreter,
            direction="cutover",
            identity=identity,
            reason=reason,
            actor=actor,
            verified_external_runtime_identity=verified_external_runtime_identity,
            binding_root=root,
        )
        project_rebind = None
        if target_rebind_kwargs:
            project_rebind = target_rebind(
                Path(spec_path),
                Path(project_root),
                capability=rebind_cap,
                occurrence=occurrence,
                target=target,
                fence_epoch=fence_epoch,
                binding_root=root,
                identity=identity,
                verified_external_runtime_identity=verified_external_runtime_identity,
                failure_injector=failure_injector,
                **dict(target_rebind_kwargs),
            )
        journal["rebind"] = {
            "cas": rebind_result.get("cas"),
            "direction": "cutover",
            "to": {"import_root": to_import_root, "interpreter": to_interpreter},
        }
        journal["stage"] = "after_rebind"
        _write_journal(journal_path, journal)
        _inject(failure_injector, "after_rebind")

        selector_done = _selector_already_cut_over(
            manifest_path=Path(manifest_path),
            to_runtime_root=to_runtime_root,
            expect_generation=expect_generation,
        )
        marker_done = _marker_already_cut_over(
            marker_path=Path(marker_path),
            active_runtime_identity=active_runtime_identity,
        )
        if selector_done:
            rollback_receipt_path = Path(
                str(
                    (journal.get("selector") or {}).get("rollback_receipt_path")
                    or receipt_path
                    or (str(Path(manifest_path)) + ".cutover-rollback.json")
                )
            )
            verify_runtime_manifest_cutover_rollback_receipt(
                rollback_receipt_path,
                expected_manifest_before_sha256=str(
                    (journal.get("selector") or {}).get("manifest_before_sha256")
                    or prior_selection.get("manifest_sha256")
                    or ""
                ),
            )
            manifest_result = journal.get("selector_result") or journal.get("selector") or {
                "rollback_receipt_path": str(rollback_receipt_path),
                "generation_after": expect_generation + 1,
            }
            journal["selector"] = {
                **dict(journal.get("selector") or {}),
                "rollback_receipt_path": str(rollback_receipt_path),
                "resumed": True,
            }
            journal["stage"] = "after_selector"
            _write_journal(journal_path, journal)
        else:
            _inject(failure_injector, "before_selector")
            manifest_result = apply_runtime_manifest_cutover(
                Path(manifest_path),
                expect_manifest_sha256=expect_manifest_sha256,
                expect_generation=expect_generation,
                from_runtime_root=from_runtime_root,
                from_expected_head=from_expected_head,
                to_runtime_root=to_runtime_root,
                to_expected_head=to_expected_head,
                to_venv_path=to_venv_path,
                to_repair_bin=to_repair_bin,
                runtime_identity_path=Path(runtime_identity_path),
                runtime_provenance_receipt_path=Path(runtime_provenance_receipt_path),
                reason=reason,
                actor=actor,
                receipt_path=Path(receipt_path) if receipt_path is not None else None,
                to_dependency_generation=to_dependency_generation,
            )
            rollback_receipt_path = Path(str(manifest_result["rollback_receipt_path"]))
            verify_runtime_manifest_cutover_rollback_receipt(
                rollback_receipt_path,
                expected_manifest_before_sha256=str(
                    manifest_result["manifest_before_sha256"]
                ),
            )
            journal["selector"] = {
                "manifest_before_sha256": manifest_result["manifest_before_sha256"],
                "manifest_after_sha256": manifest_result["manifest_after_sha256"],
                "generation_before": manifest_result["generation_before"],
                "generation_after": manifest_result["generation_after"],
                "rollback_receipt_path": str(rollback_receipt_path),
            }
            journal["selector_result"] = {
                "manifest_before_sha256": manifest_result["manifest_before_sha256"],
                "manifest_after_sha256": manifest_result["manifest_after_sha256"],
                "generation_before": manifest_result["generation_before"],
                "generation_after": manifest_result["generation_after"],
                "rollback_receipt_path": str(rollback_receipt_path),
            }
            journal["stage"] = "after_selector"
            _write_journal(journal_path, journal)
            _inject(failure_injector, "after_selector")
            _inject(failure_injector, "after_receipt")

        if marker_done:
            marker_result = journal.get("marker_result") or journal.get("marker") or {
                "marker_after_sha256": _sha256_file(Path(marker_path)),
                "resumed": True,
            }
            journal["marker"] = {
                **dict(journal.get("marker") or {}),
                "resumed": True,
            }
            journal["stage"] = "after_marker"
            _write_journal(journal_path, journal)
        else:
            _inject(failure_injector, "before_marker")
            marker_result = update_marker_runtime(
                Path(marker_path),
                expected_marker_sha256=expected_marker_sha256,
                expected_previous_runtime_sha256=expected_previous_runtime_sha256,
                active_runtime_identity=active_runtime_identity,
                relaunch_command=relaunch_command,
                reason=reason,
                actor=actor,
                direction="cutover",
                source_branch=source_branch,
            )
            journal["marker"] = {
                "marker_before_sha256": marker_result["marker_before_sha256"],
                "marker_after_sha256": marker_result["marker_after_sha256"],
            }
            journal["marker_result"] = {
                "marker_before_sha256": marker_result["marker_before_sha256"],
                "marker_after_sha256": marker_result["marker_after_sha256"],
            }
            journal["stage"] = "after_marker"
            _write_journal(journal_path, journal)
            _inject(failure_injector, "after_marker")

        identity_result: dict[str, Any] | None = None
        _inject(failure_injector, "before_identity")
        if chain_state is not None and expected_previous_runtime_sha256_identity:
            identity_result = cutover_runtime_identity(
                Path(spec_path),
                chain_state,
                expected_previous_runtime_sha256=expected_previous_runtime_sha256_identity,
                expected_active_runtime_sha256=expected_active_runtime_sha256_identity,
                expected_current_milestone=expected_current_milestone,
                expected_current_plan=expected_current_plan,
                reason=reason,
                actor=actor,
                direction="cutover",
                verified_external_runtime_identity=verified_external_runtime_identity,
            )
            journal["identity"] = {
                "wrapper": "cutover_runtime_identity",
                "second_lock": False,
            }
        else:
            journal["identity"] = {
                "wrapper": "cutover_runtime_identity",
                "skipped": "no_chain_runtime_binding",
                "second_lock": False,
            }
        journal["stage"] = "after_identity"
        _write_journal(journal_path, journal)
        _inject(failure_injector, "after_identity")

        plan_after = _load_plan(project_root, expected_current_plan)
        if isinstance(plan_before, Mapping) and isinstance(plan_after, Mapping):
            if resume_cursor_bytes(plan_after) != cursor_before:
                raise CliError(
                    "cursor_mutated",
                    "cutover must not move the logical resume cursor",
                )
            if plan_payload_without_pause(plan_after) != payload_before:
                raise CliError(
                    "plan_payload_mutated",
                    "cutover may append receipts but cannot rewrite plan state",
                )

        current = _selection_snapshot(
            manifest_path=Path(manifest_path),
            marker_path=Path(marker_path),
        )
        journal["current_selection"] = current
        journal["status"] = "committed"
        journal["stage"] = "committed"
        journal["resumable"] = False
        _write_journal(journal_path, journal)
        _inject(failure_injector, "committed")
    except BaseException:
        journal["status"] = "in_progress"
        journal["resumable"] = True
        _write_journal(journal_path, journal)
        raise

    return {
        "changed": True,
        "duplicate": False,
        "status": "committed",
        "idempotent": False,
        "pause": pause_result,
        "quiesce": quiesce,
        "rebind": rebind_result,
        "project_rebind": project_rebind,
        "manifest": manifest_result,
        "marker": marker_result,
        "identity": identity_result,
        "journal": journal,
        "prior_selection": prior_selection,
        "current_selection": current,
        "rollback_receipt_path": str(rollback_receipt_path),
    }


def rollback_runtime_cutover(
    *,
    capability: MutationCapability | Mapping[str, Any] | None,
    occurrence: str,
    target: str,
    fence_epoch: int,
    binding_root: Path,
    spec_path: Path,
    project_root: Path,
    reason: str,
    actor: str = "operator",
    rebind_capability: MutationCapability | Mapping[str, Any] | None = None,
    expected_current_milestone: str = "m7",
    expected_current_plan: str = "",
    identity: Mapping[str, Any] | None = None,
    from_import_root: str,
    from_interpreter: str,
    to_import_root: str,
    to_interpreter: str,
    manifest_path: Path,
    receipt_path: Path,
    expected_manifest_before_sha256: str,
    marker_path: Path,
    expected_marker_sha256: str,
    expected_previous_runtime_sha256: str,
    prior_runtime_identity: Mapping[str, Any],
    relaunch_command: str,
    source_branch: str = "",
    verified_external_runtime_identity: Mapping[str, Any] | None = None,
    report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Restore the exact prior selection without rewriting plan state."""

    _refuse_report_trigger(report)
    root = assert_disposable_root(binding_root)
    del spec_path
    minted = _bind_root_capability(
        capability,
        occurrence=occurrence,
        target=target,
        fence_epoch=fence_epoch,
    )
    rebind_cap = rebind_capability if rebind_capability is not None else minted
    plan_before = _load_plan(project_root, expected_current_plan)
    cursor_before = resume_cursor_bytes(plan_before or {})
    payload_before = (
        plan_payload_without_pause(plan_before) if isinstance(plan_before, Mapping) else b""
    )

    receipt = verify_runtime_manifest_cutover_rollback_receipt(
        Path(receipt_path),
        expected_manifest_before_sha256=expected_manifest_before_sha256,
    )
    previous = receipt.get("previous_manifest")
    if not isinstance(previous, Mapping):
        raise CliError(
            "incomplete_rollback_evidence",
            "rollback receipt does not carry the prior manifest selection",
        )

    rebind_result = runtime_rebind(
        capability=rebind_cap,
        occurrence=occurrence,
        target=target,
        fence_epoch=fence_epoch,
        expected_current_milestone=expected_current_milestone,
        expected_current_plan=expected_current_plan,
        from_import_root=from_import_root,
        from_interpreter=from_interpreter,
        to_import_root=to_import_root,
        to_interpreter=to_interpreter,
        direction="rollback",
        identity=identity,
        reason=reason,
        actor=actor,
        verified_external_runtime_identity=verified_external_runtime_identity,
        binding_root=root,
    )
    write_manifest(RuntimeManifest.from_dict(previous), Path(manifest_path))
    marker_result = update_marker_runtime(
        Path(marker_path),
        expected_marker_sha256=expected_marker_sha256,
        expected_previous_runtime_sha256=expected_previous_runtime_sha256,
        active_runtime_identity=prior_runtime_identity,
        relaunch_command=relaunch_command,
        reason=reason,
        actor=actor,
        direction="rollback",
        source_branch=source_branch,
    )

    plan_after = _load_plan(project_root, expected_current_plan)
    if isinstance(plan_before, Mapping) and isinstance(plan_after, Mapping):
        if resume_cursor_bytes(plan_after) != cursor_before:
            raise CliError(
                "cursor_mutated",
                "rollback must not move the logical resume cursor",
            )
        if plan_payload_without_pause(plan_after) != payload_before:
            raise CliError(
                "plan_payload_mutated",
                "rollback restores selection without rewriting plan state",
            )

    restored = _selection_snapshot(
        manifest_path=Path(manifest_path),
        marker_path=Path(marker_path),
    )
    journal_path = _journal_path(root)
    journal = _load_journal(journal_path) or {}
    journal.update(
        {
            "schema": DELIVERY_JOURNAL_SCHEMA,
            "status": "rolled_back",
            "stage": "rolled_back",
            "restored_selection": restored,
        }
    )
    _write_journal(journal_path, journal)
    return {
        "changed": True,
        "status": "rolled_back",
        "receipt": receipt,
        "rebind": rebind_result,
        "marker": marker_result,
        "restored_selection": restored,
        "journal": journal,
    }


def same_import_root_commit_after_cutover(
    *,
    binding_root: Path,
    import_root: Path,
    manifest_path: Path,
    new_head: str,
    require_rebind: bool = False,
    require_generation_bump: bool = False,
) -> dict[str, Any]:
    """Same-import_root commit after T4.3 cutover is a non-event.

    A caller that still requires the pre-T4.3 expected_head + content-digest
    rebind dance fails closed. This is the must-fail contract for a test that
    still demands that tax after gate deletion.
    """

    root = assert_disposable_root(binding_root)
    del root
    if require_rebind or require_generation_bump:
        raise CliError(
            "same_import_root_is_non_event",
            "after cutover, same-import_root commit requires no rebind and "
            "no generation bump",
            extra={
                "require_rebind": require_rebind,
                "require_generation_bump": require_generation_bump,
                "new_head": new_head,
            },
        )
    manifest = load_manifest(Path(manifest_path))
    current_root = Path(str(manifest.epic.get("runtime_root") or "")).expanduser().resolve()
    live_root = Path(import_root).expanduser().resolve()
    if current_root != live_root:
        raise CliError(
            "import_root_changed",
            "this helper only covers same-import_root commits after cutover",
            extra={"current_root": str(current_root), "import_root": str(live_root)},
        )
    return {
        "non_event": True,
        "rebind": False,
        "generation_bump": False,
        "generation": manifest.generation,
        "import_root": str(live_root),
        "expected_head": str(manifest.epic.get("expected_head") or ""),
        "new_head_telemetry_only": new_head,
        "seed_gates": False,
    }


def inspect_transition(binding_root: Path) -> dict[str, Any] | None:
    """Return the durable transition journal, if any."""

    root = assert_disposable_root(binding_root)
    return _load_journal(_journal_path(root))


__all__ = [
    "CUTOVER_ACTION",
    "DELIVERY_JOURNAL_SCHEMA",
    "DELIVERY_SENTINEL",
    "PUBLICATION_BOUNDARIES",
    "deliver_runtime_cutover",
    "inspect_transition",
    "prove_quiesced_writers",
    "rollback_runtime_cutover",
    "same_import_root_commit_after_cutover",
]
