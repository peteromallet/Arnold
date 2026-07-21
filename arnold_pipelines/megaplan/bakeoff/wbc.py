"""Fail-closed WBC validation helpers for bakeoff lifecycle mutations."""

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
from arnold_pipelines.megaplan.notification_safety import classify_fixture_safety
from arnold_pipelines.megaplan.types import CliError


BAKEOFF_RUN_WRITER_ID = "megaplan.bakeoff.wbc.run"
BAKEOFF_RUN_SURFACE = "megaplan.bakeoff.wbc.run"
BAKEOFF_COMPARE_WRITER_ID = "megaplan.bakeoff.wbc.compare"
BAKEOFF_COMPARE_SURFACE = "megaplan.bakeoff.wbc.compare"
BAKEOFF_PICK_WRITER_ID = "megaplan.bakeoff.wbc.pick"
BAKEOFF_PICK_SURFACE = "megaplan.bakeoff.wbc.pick"
BAKEOFF_RESUME_WRITER_ID = "megaplan.bakeoff.wbc.resume"
BAKEOFF_RESUME_SURFACE = "megaplan.bakeoff.wbc.resume"
BAKEOFF_ABANDON_WRITER_ID = "megaplan.bakeoff.wbc.abandon"
BAKEOFF_ABANDON_SURFACE = "megaplan.bakeoff.wbc.abandon"
BAKEOFF_MERGE_WRITER_ID = "megaplan.bakeoff.wbc.merge"
BAKEOFF_MERGE_SURFACE = "megaplan.bakeoff.wbc.merge"


@dataclass(frozen=True)
class BakeoffWbcRule:
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
        required_wbc_phases=("source_lookup", "fixture_authorization"),
        action_kind="bakeoff_transition",
    )


_BAKEOFF_WBC_WRITERS: tuple[ControlledWriter, ...] = (
    _controlled_writer(
        writer_id=BAKEOFF_RUN_WRITER_ID,
        surface_name=BAKEOFF_RUN_SURFACE,
        contract_id="megaplan.bakeoff.wbc.run.v1",
        source_file="arnold_pipelines/megaplan/bakeoff/orchestrator.py",
        function_name="run_bakeoff",
    ),
    _controlled_writer(
        writer_id=BAKEOFF_COMPARE_WRITER_ID,
        surface_name=BAKEOFF_COMPARE_SURFACE,
        contract_id="megaplan.bakeoff.wbc.compare.v1",
        source_file="arnold_pipelines/megaplan/bakeoff/handlers.py",
        function_name="handle_compare",
    ),
    _controlled_writer(
        writer_id=BAKEOFF_PICK_WRITER_ID,
        surface_name=BAKEOFF_PICK_SURFACE,
        contract_id="megaplan.bakeoff.wbc.pick.v1",
        source_file="arnold_pipelines/megaplan/bakeoff/handlers.py",
        function_name="handle_pick",
    ),
    _controlled_writer(
        writer_id=BAKEOFF_RESUME_WRITER_ID,
        surface_name=BAKEOFF_RESUME_SURFACE,
        contract_id="megaplan.bakeoff.wbc.resume.v1",
        source_file="arnold_pipelines/megaplan/bakeoff/lifecycle.py",
        function_name="resume_bakeoff",
    ),
    _controlled_writer(
        writer_id=BAKEOFF_ABANDON_WRITER_ID,
        surface_name=BAKEOFF_ABANDON_SURFACE,
        contract_id="megaplan.bakeoff.wbc.abandon.v1",
        source_file="arnold_pipelines/megaplan/bakeoff/lifecycle.py",
        function_name="abandon_bakeoff",
    ),
    _controlled_writer(
        writer_id=BAKEOFF_MERGE_WRITER_ID,
        surface_name=BAKEOFF_MERGE_SURFACE,
        contract_id="megaplan.bakeoff.wbc.merge.v1",
        source_file="arnold_pipelines/megaplan/bakeoff/merge.py",
        function_name="merge_bakeoff",
    ),
)


def register_bakeoff_wbc_writers() -> None:
    for writer in _BAKEOFF_WBC_WRITERS:
        try:
            register_writer(writer)
        except ValueError:
            continue


def validate_bakeoff_transition(
    *,
    writer_id: str,
    surface_name: str,
    transition_name: str,
    subject: str,
    source_path: Path,
    project_dir: Path,
    destructive: bool = False,
    rules: Sequence[BakeoffWbcRule] = (),
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    register_bakeoff_wbc_writers()

    transition_value = str(transition_name).strip()
    subject_value = str(subject).strip()
    if not transition_value:
        raise CliError(
            "bakeoff_wbc_transition_missing",
            f"{surface_name} requires a non-empty transition name",
        )
    if not subject_value:
        raise CliError(
            "bakeoff_wbc_subject_missing",
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
            "bakeoff_wbc_contract_missing",
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

    source = source_record_for_path(source_path=source_path, project_dir=project_dir)
    if not source.get("exists", True) or source.get("errors"):
        raise CliError(
            "bakeoff_wbc_source_missing",
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
            "bakeoff_wbc_validation_failed",
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

    fixture_decision = classify_fixture_safety(
        workspace=str(project_dir),
        payload={"workspace": str(project_dir)},
    )
    if destructive and not fixture_decision.authorized:
        raise CliError(
            "bakeoff_wbc_action_off",
            (
                f"{surface_name} remains action-off outside fixture-authorized execution "
                f"during WBC adoption"
            ),
            extra={
                "transition": transition_value,
                "subject": subject_value,
                "source_record": source,
                "fixture_safety": {
                    "authorized": fixture_decision.authorized,
                    "reason": fixture_decision.reason,
                },
            },
        )

    payload: dict[str, Any] = {
        "schema": "arnold.megaplan.bakeoff_wbc_transition_evidence.v1",
        "writer_id": writer_id,
        "surface_name": surface_name,
        "transition": transition_value,
        "subject": subject_value,
        "source_record": source,
        "rules": normalized_rules,
        "destructive": destructive,
        "fixture_safety": {
            "authorized": fixture_decision.authorized,
            "reason": fixture_decision.reason,
        },
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def record_bakeoff_wbc_evidence(
    metadata: MutableMapping[str, Any],
    *,
    entry_key: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    registry = metadata.setdefault("wbc_transition_evidence", {})
    if not isinstance(registry, dict):
        registry = {}
        metadata["wbc_transition_evidence"] = registry
    registry[str(entry_key)] = dict(evidence)
    return registry[str(entry_key)]


__all__ = [
    "BAKEOFF_ABANDON_SURFACE",
    "BAKEOFF_ABANDON_WRITER_ID",
    "BAKEOFF_COMPARE_SURFACE",
    "BAKEOFF_COMPARE_WRITER_ID",
    "BAKEOFF_MERGE_SURFACE",
    "BAKEOFF_MERGE_WRITER_ID",
    "BAKEOFF_PICK_SURFACE",
    "BAKEOFF_PICK_WRITER_ID",
    "BAKEOFF_RESUME_SURFACE",
    "BAKEOFF_RESUME_WRITER_ID",
    "BAKEOFF_RUN_SURFACE",
    "BAKEOFF_RUN_WRITER_ID",
    "BakeoffWbcRule",
    "record_bakeoff_wbc_evidence",
    "register_bakeoff_wbc_writers",
    "validate_bakeoff_transition",
]
