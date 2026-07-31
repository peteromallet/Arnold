"""Fail-closed WBC validation helpers for chain-family transitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

from arnold_pipelines.megaplan.custody.admission_control import source_record_for_path
from arnold_pipelines.megaplan.custody.controlled_writer_registry import (
    Cohort,
    ControlledWriter,
    WriteGuardDecision,
    register_writer,
    writer_guard,
)
from arnold_pipelines.megaplan.types import CliError


CHAIN_ADVANCE_WRITER_ID = "megaplan.chain.wbc.advance"
CHAIN_ADVANCE_SURFACE = "megaplan.chain.wbc.advance"
EPIC_PROGRESS_WRITER_ID = "megaplan.chain.wbc.epic_progress"
EPIC_PROGRESS_SURFACE = "megaplan.chain.wbc.epic_progress"
EXECUTION_REBIND_WRITER_ID = "megaplan.chain.wbc.execution_rebind"
EXECUTION_REBIND_SURFACE = "megaplan.chain.wbc.execution_rebind"
GIT_PR_READY_WRITER_ID = "megaplan.chain.wbc.git_pr_ready"
GIT_PR_READY_SURFACE = "megaplan.chain.wbc.git_pr_ready"
GIT_PR_MERGE_WRITER_ID = "megaplan.chain.wbc.git_pr_merge"
GIT_PR_MERGE_SURFACE = "megaplan.chain.wbc.git_pr_merge"
CHAIN_CI_WRITER_ID = "megaplan.chain.wbc.ci"
CHAIN_CI_SURFACE = "megaplan.chain.wbc.ci"
HINGE_GATE_WRITER_ID = "megaplan.chain.wbc.hinge_gate"
HINGE_GATE_SURFACE = "megaplan.chain.wbc.hinge_gate"


@dataclass(frozen=True)
class ChainWbcRule:
    identity: str
    expected: Any
    observed: Any
    satisfied: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "expected": self.expected,
            "observed": self.observed,
            "satisfied": self.satisfied,
            "detail": self.detail,
        }


def _controlled_writer(
    *,
    writer_id: str,
    surface_name: str,
    contract_id: str,
    source_file: str,
    function_name: str,
) -> ControlledWriter:
    return ControlledWriter(
        writer_id=writer_id,
        surface_name=surface_name,
        cohort=Cohort.ACTIVE,
        contract_ids=(contract_id,),
        source_file=source_file,
        function_name=function_name,
        required_wbc_phases=("source_lookup", "fence"),
        action_kind="chain_transition",
    )


_CHAIN_WBC_WRITERS: tuple[ControlledWriter, ...] = (
    _controlled_writer(
        writer_id=CHAIN_ADVANCE_WRITER_ID,
        surface_name=CHAIN_ADVANCE_SURFACE,
        contract_id="megaplan.chain.wbc.advance.v1",
        source_file="arnold_pipelines/megaplan/chain/__init__.py",
        function_name="_append_completed_with_guard",
    ),
    _controlled_writer(
        writer_id=EPIC_PROGRESS_WRITER_ID,
        surface_name=EPIC_PROGRESS_SURFACE,
        contract_id="megaplan.chain.wbc.epic_progress.v1",
        source_file="arnold_pipelines/megaplan/chain/epic_chain.py",
        function_name="run_epic_chain",
    ),
    _controlled_writer(
        writer_id=EXECUTION_REBIND_WRITER_ID,
        surface_name=EXECUTION_REBIND_SURFACE,
        contract_id="megaplan.chain.wbc.execution_rebind.v1",
        source_file="arnold_pipelines/megaplan/chain/execution_binding.py",
        function_name="rebind_execution_identity",
    ),
    _controlled_writer(
        writer_id=GIT_PR_READY_WRITER_ID,
        surface_name=GIT_PR_READY_SURFACE,
        contract_id="megaplan.chain.wbc.git_pr_ready.v1",
        source_file="arnold_pipelines/megaplan/chain/git_ops.py",
        function_name="_capture_pr_ready_evidence",
    ),
    _controlled_writer(
        writer_id=GIT_PR_MERGE_WRITER_ID,
        surface_name=GIT_PR_MERGE_SURFACE,
        contract_id="megaplan.chain.wbc.git_pr_merge.v1",
        source_file="arnold_pipelines/megaplan/chain/git_ops.py",
        function_name="_capture_pr_merged_evidence",
    ),
    _controlled_writer(
        writer_id=CHAIN_CI_WRITER_ID,
        surface_name=CHAIN_CI_SURFACE,
        contract_id="megaplan.chain.wbc.ci.v1",
        source_file="arnold_pipelines/megaplan/chain/ci_hook.py",
        function_name="run_chain_ci",
    ),
    _controlled_writer(
        writer_id=HINGE_GATE_WRITER_ID,
        surface_name=HINGE_GATE_SURFACE,
        contract_id="megaplan.chain.wbc.hinge_gate.v1",
        source_file="arnold_pipelines/megaplan/chain/hinge_gate.py",
        function_name="run_hinge_gate",
    ),
)


def register_chain_wbc_writers() -> None:
    for writer in _CHAIN_WBC_WRITERS:
        try:
            register_writer(writer)
        except ValueError:
            continue


def validate_chain_wbc_transition(
    *,
    writer_id: str,
    surface_name: str,
    transition_name: str,
    subject: str,
    source_path: Path,
    project_dir: Path,
    rules: Sequence[ChainWbcRule] = (),
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    register_chain_wbc_writers()

    transition_value = str(transition_name).strip()
    subject_value = str(subject).strip()
    if not transition_value:
        raise CliError(
            "chain_wbc_transition_missing",
            f"{surface_name} requires a non-empty transition name",
        )
    if not subject_value:
        raise CliError(
            "chain_wbc_subject_missing",
            f"{surface_name} requires a non-empty subject",
        )

    guard = writer_guard(
        writer_id=writer_id,
        surface_name=surface_name,
        override_enforcement=True,
        override_fail_closed=True,
    )
    if guard.decision is not WriteGuardDecision.ALLOWED:
        raise CliError(
            "chain_wbc_contract_missing",
            f"{surface_name} is not registered as an allowed controlled writer",
            extra={
                "transition": transition_value,
                "subject": subject_value,
                "writer_guard": {
                    "decision": guard.decision.value,
                    "writer_id": guard.writer_id,
                    "surface_name": guard.surface_name,
                    "diagnostics": list(guard.diagnostics),
                },
            },
        )

    source = source_record_for_path(
        source_path=source_path,
        project_dir=project_dir,
    )
    if not source.get("exists", True) or source.get("errors"):
        raise CliError(
            "chain_wbc_source_missing",
            f"{surface_name} could not reread the exact source record for {transition_value!r}",
            extra={
                "transition": transition_value,
                "subject": subject_value,
                "source_record": source,
            },
        )

    normalized_rules = [rule.to_dict() for rule in rules]
    failed_rule = next((rule for rule in normalized_rules if not rule["satisfied"]), None)
    if failed_rule is not None:
        raise CliError(
            "chain_wbc_validation_failed",
            (
                f"{surface_name} transition {transition_value!r} refused: "
                f"validation {failed_rule['identity']!r} is stale or missing"
            ),
            extra={
                "transition": transition_value,
                "subject": subject_value,
                "source_record": source,
                "rules": normalized_rules,
                "failed_rule": failed_rule,
            },
        )

    payload: dict[str, Any] = {
        "schema": "arnold.megaplan.chain_wbc_transition_evidence.v1",
        "writer_id": writer_id,
        "surface_name": surface_name,
        "transition": transition_value,
        "subject": subject_value,
        "source_record": source,
        "rules": normalized_rules,
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def record_chain_wbc_evidence(
    metadata: MutableMapping[str, Any],
    *,
    entry_key: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    entry = dict(evidence)
    registry = metadata.setdefault("wbc_transition_evidence", {})
    if not isinstance(registry, dict):
        registry = {}
        metadata["wbc_transition_evidence"] = registry
    registry[str(entry_key)] = entry
    return entry


def finalize_receipt_candidates(plan_dir: Path) -> list[str]:
    candidates = (
        "step_receipt_finalize_v2.json",
        "step_receipt_finalize_v1.json",
        "boundary_receipts/final_projection.json",
        "boundary_receipts/finalize_artifacts.json",
    )
    present: list[str] = []
    for relative in candidates:
        if (plan_dir / relative).exists():
            present.append(relative)
    return present


def finalize_artifact_candidates(plan_dir: Path) -> list[str]:
    candidates = (
        "final.md",
        "finalize.json",
        "finalize_output.json",
    )
    present: list[str] = []
    for relative in candidates:
        if (plan_dir / relative).exists():
            present.append(relative)
    return present


__all__ = [
    "CHAIN_ADVANCE_SURFACE",
    "CHAIN_ADVANCE_WRITER_ID",
    "CHAIN_CI_SURFACE",
    "CHAIN_CI_WRITER_ID",
    "ChainWbcRule",
    "EPIC_PROGRESS_SURFACE",
    "EPIC_PROGRESS_WRITER_ID",
    "EXECUTION_REBIND_SURFACE",
    "EXECUTION_REBIND_WRITER_ID",
    "GIT_PR_MERGE_SURFACE",
    "GIT_PR_MERGE_WRITER_ID",
    "GIT_PR_READY_SURFACE",
    "GIT_PR_READY_WRITER_ID",
    "HINGE_GATE_SURFACE",
    "HINGE_GATE_WRITER_ID",
    "finalize_artifact_candidates",
    "finalize_receipt_candidates",
    "record_chain_wbc_evidence",
    "register_chain_wbc_writers",
    "validate_chain_wbc_transition",
]
