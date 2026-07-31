"""Fail-closed WBC validation helpers for GitHub publication surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

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


GITHUB_SYNC_CREATE_WRITER_ID = "megaplan.cloud.github_sync.create"
GITHUB_SYNC_CREATE_SURFACE = "megaplan.cloud.github_sync.create"
GITHUB_SYNC_COMMENT_WRITER_ID = "megaplan.cloud.github_sync.comment"
GITHUB_SYNC_COMMENT_SURFACE = "megaplan.cloud.github_sync.comment"


@dataclass(frozen=True)
class GitHubSyncRule:
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
    function_name: str,
) -> ControlledWriter:
    return ControlledWriter(
        writer_id=writer_id,
        surface_name=surface_name,
        cohort=Cohort.ACTIVE,
        contract_ids=(contract_id,),
        source_file="arnold_pipelines/megaplan/cloud/github_sync.py",
        function_name=function_name,
        required_wbc_phases=("source_lookup", "fixture_authorization"),
        action_kind="publication",
    )


_GITHUB_SYNC_WRITERS: tuple[ControlledWriter, ...] = (
    _controlled_writer(
        writer_id=GITHUB_SYNC_CREATE_WRITER_ID,
        surface_name=GITHUB_SYNC_CREATE_SURFACE,
        contract_id="megaplan.cloud.github_sync.create.v1",
        function_name="sync_persistent_problems",
    ),
    _controlled_writer(
        writer_id=GITHUB_SYNC_COMMENT_WRITER_ID,
        surface_name=GITHUB_SYNC_COMMENT_SURFACE,
        contract_id="megaplan.cloud.github_sync.comment.v1",
        function_name="sync_persistent_problems",
    ),
)


def register_github_sync_wbc_writers() -> None:
    for writer in _GITHUB_SYNC_WRITERS:
        try:
            register_writer(writer)
        except ValueError:
            continue


def validate_github_sync_publication(
    *,
    writer_id: str,
    surface_name: str,
    action: str,
    problem_id: str,
    project_dir: Path,
    rules: Sequence[GitHubSyncRule] = (),
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    register_github_sync_wbc_writers()

    action_value = str(action).strip()
    subject_value = str(problem_id).strip()
    if not action_value:
        raise CliError(
            "github_sync_wbc_action_missing",
            f"{surface_name} requires a non-empty action name",
        )
    if not subject_value:
        raise CliError(
            "github_sync_wbc_problem_missing",
            f"{surface_name} requires a non-empty problem id",
        )

    guard = writer_guard(
        writer_id=writer_id,
        surface_name=surface_name,
        override_enforcement=True,
        override_fail_closed=True,
    )
    if guard.decision is not WriteGuardDecision.ALLOWED:
        raise CliError(
            "github_sync_wbc_contract_missing",
            f"{surface_name} is not registered as an allowed controlled writer",
            extra={
                "action": action_value,
                "problem_id": subject_value,
                "writer_guard": {
                    "decision": guard.decision.value,
                    "writer_id": guard.writer_id,
                    "surface_name": guard.surface_name,
                    "diagnostics": list(guard.diagnostics),
                },
            },
        )

    source = source_record_for_path(source_path=Path(__file__).with_name("github_sync.py"), project_dir=project_dir)
    if not source.get("exists", True) or source.get("errors"):
        raise CliError(
            "github_sync_wbc_source_missing",
            f"{surface_name} could not reread the exact source record for {action_value!r}",
            extra={
                "action": action_value,
                "problem_id": subject_value,
                "source_record": source,
            },
        )

    normalized_rules = [rule.to_dict() for rule in rules]
    failed_rule = next((rule for rule in normalized_rules if not rule["satisfied"]), None)
    if failed_rule is not None:
        raise CliError(
            "github_sync_wbc_validation_failed",
            (
                f"{surface_name} action {action_value!r} refused: "
                f"validation {failed_rule['identity']!r} is stale or missing"
            ),
            extra={
                "action": action_value,
                "problem_id": subject_value,
                "source_record": source,
                "rules": normalized_rules,
                "failed_rule": failed_rule,
            },
        )

    fixture_decision = classify_fixture_safety(
        workspace=str(project_dir),
        payload={"workspace": str(project_dir)},
    )
    if not fixture_decision.authorized:
        raise CliError(
            "github_sync_action_off",
            (
                f"{surface_name} remains action-off outside fixture-authorized execution "
                f"during WBC adoption"
            ),
            extra={
                "action": action_value,
                "problem_id": subject_value,
                "source_record": source,
                "fixture_safety": {
                    "authorized": fixture_decision.authorized,
                    "reason": fixture_decision.reason,
                },
            },
        )

    payload: dict[str, Any] = {
        "schema": "arnold.megaplan.github_sync_wbc_evidence.v1",
        "writer_id": writer_id,
        "surface_name": surface_name,
        "action": action_value,
        "problem_id": subject_value,
        "source_record": source,
        "rules": normalized_rules,
        "fixture_safety": {
            "authorized": fixture_decision.authorized,
            "reason": fixture_decision.reason,
        },
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


__all__ = [
    "GITHUB_SYNC_COMMENT_SURFACE",
    "GITHUB_SYNC_COMMENT_WRITER_ID",
    "GITHUB_SYNC_CREATE_SURFACE",
    "GITHUB_SYNC_CREATE_WRITER_ID",
    "GitHubSyncRule",
    "register_github_sync_wbc_writers",
    "validate_github_sync_publication",
]
