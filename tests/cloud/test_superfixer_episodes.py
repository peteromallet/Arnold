from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.superfixer_episodes import (
    EpisodeValidationError,
    SIBLING_REQUIREMENTS,
    archive_raw_evidence,
    bounded_prompt_projection,
    build_episode,
    deterministic_recurrence,
    persist_episode,
    promote_validated_lesson,
    retroactive_l3_classification,
    revise_episode,
    validate_episode_for_learning,
)


OBSERVED_AT = "2026-07-13T22:44:58+00:00"
SESSION = "workflow-boundary-contracts-corrective-20260710"
PLAN = "s3-megaplan-boundary-coverage-20260713-1934"


def _archive_fixture(tmp_path: Path) -> list[dict]:
    raw_root = tmp_path / "raw-inputs"
    evidence_root = tmp_path / "episode-store"
    payloads = {
        "live_process": b"process=false tmux=false worker_pid=3136480 pid_live=false\n",
        "marker_json": b'{"session":"workflow-boundary-contracts-corrective-20260710","should_run":true}\n',
        "chain_json": b'{"last_state":"between_milestones","completed_count":2}\n',
        "plan_state": b'{"current_state":"finalized","active_step":{"worker_pid":3136480}}\n',
        "log_tail": b"ModuleNotFoundError: No module named 'yaml'\n",
        "repair_queue": b'{"status":"accepted","claim_count":0,"attempt_count":0}\n',
        "l3_request": b'{"failure_kind":"DRIFT_DETECTED","deterministic_superfixer_evidence":{}}\n',
    }
    refs = []
    for kind, data in payloads.items():
        path = raw_root / f"{kind}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        refs.append(
            archive_raw_evidence(
                path,
                evidence_root=evidence_root,
                kind=kind,
                observed_at=OBSERVED_AT,
            )
        )
    return refs


def _wbc_episode(tmp_path: Path) -> dict:
    evidence = _archive_fixture(tmp_path)
    return build_episode(
        observed_at=OBSERVED_AT,
        session=SESSION,
        plan=PLAN,
        symptom={
            "kind": "runner_stopped",
            "summary": "status said executing while the runner and active-step PID were dead",
            "derived_status": "repair_dispatched",
            "ground_truth_status": "stopped",
        },
        mechanism={
            "kind": "dependency_import_failure",
            "signature": "ModuleNotFoundError: No module named 'yaml' at agentbox/config.py:10",
            "exception_type": "ModuleNotFoundError",
            "dependency": "PyYAML",
            "observation_path": "watchdog marker sweep",
        },
        root_cause={
            "layer": "watchdog",
            "axis": "TRACKED",
            "failure_class": "dependency_import_failure",
            "summary": "the watchdog could not observe the dead run after its source import failed",
        },
        missed_backstop={
            "layer": "L3",
            "axis": "CONTEXT",
            "summary": "the auditor request carried generic drift and no deterministic root-cause evidence",
        },
        evidence=evidence,
        contradictions=[
            {
                "left": "derived watchdog status=repair_dispatched",
                "right": "request/claim/attempt=1/0/0 and runner stopped",
                "diagnostic": "self-reported dispatch had no custody receipt",
            }
        ],
        facts={
            "accepted_unclaimed_request": True,
            "watchdog_report_stale": True,
            "l3_deterministic_evidence_empty": True,
            "repair_reported_dispatched_without_claim": True,
        },
    )


def _verified_wbc_episode(tmp_path: Path) -> dict:
    episode = _wbc_episode(tmp_path)
    refs = {item["kind"]: item for item in episode["evidence"]}
    repair = {
        "fixer_fixed": True,
        "backstop_fixed": True,
        "commit_sha": "a" * 40,
        "ordinary_retrigger_run_id": "managed-l1-retrigger-wbc",
        "ordinary_retrigger_manifest_path": "/workspace/managed-l1-retrigger-wbc/manifest.json",
    }
    verification = {
        "original_session_advanced": True,
        "fix_deployed": True,
        "guard_weakened": False,
        "ground_truth": {
            "live_process": {
                "result": "pass",
                "path": refs["live_process"]["archive_path"],
                "sha256": refs["live_process"]["sha256"],
            },
            "marker_json": {
                "result": "pass",
                "path": refs["marker_json"]["archive_path"],
                "sha256": refs["marker_json"]["sha256"],
            },
            "chain_json": {
                "result": "pass",
                "path": refs["chain_json"]["archive_path"],
                "sha256": refs["chain_json"]["sha256"],
            },
            "plan_state": {
                "result": "pass",
                "path": refs["plan_state"]["archive_path"],
                "sha256": refs["plan_state"]["sha256"],
            },
            "log_tail": {
                "result": "pass",
                "path": refs["log_tail"]["archive_path"],
                "sha256": refs["log_tail"]["sha256"],
            },
            "external_state": {"result": "not_applicable"},
        },
    }
    detection_rules = [
        {
            "rule_id": "watchdog_observation_path_failure",
            "implementation_path": "arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor",
            "test_nodes": [
                "tests/cloud/test_superfixer_episodes.py::test_retroactive_l3_detects_exact_wbc_episode_with_actionable_context"
            ],
        }
    ]
    regression_receipts = [
        {
            "kind": "historical_episode_replay",
            "test_node": "tests/cloud/test_superfixer_episodes.py::test_retroactive_l3_detects_exact_wbc_episode_with_actionable_context",
            "pre_fix_failed": True,
            "post_fix_passed": True,
        },
        {
            "kind": "sibling_failure_class",
            "test_node": "tests/cloud/test_superfixer_episodes.py::test_dependency_import_failure_requires_full_sibling_hunt",
            "pre_fix_failed": True,
            "post_fix_passed": True,
        },
    ]
    sibling_hunt_receipts = [
        {"sibling_class": sibling, "checked": True, "result": "covered"}
        for sibling in SIBLING_REQUIREMENTS["dependency_import_failure"]
    ]
    review = {
        "approved": True,
        "reviewer": "senior-superfixer-review",
        "approved_at": "2026-07-13T23:00:00+00:00",
        "rollback_ref": "origin/main-before-superfixer-fix",
    }
    return revise_episode(
        episode,
        repair=repair,
        verification=verification,
        detection_rules=detection_rules,
        regression_receipts=regression_receipts,
        sibling_hunt_receipts=sibling_hunt_receipts,
        review=review,
        learning_status="validated",
    )


def _proposal() -> dict:
    return {
        "prompt_template_ids": [
            "include_raw_failure_mechanism",
            "require_fixer_and_backstop_receipts",
            "require_ground_truth_reverification",
            "require_sibling_failure_hunt",
            "reject_guard_weakening",
        ],
        "classifier_feature_ids": [
            "accepted_unclaimed_repair_request",
            "false_success_ground_truth_disagreement",
            "stale_watchdog_report",
            "watchdog_observation_path_failure",
        ],
        "detector_rule_ids": ["watchdog_observation_path_failure"],
        "target_layers": ["L1", "L2", "L3"],
        "rollback": {
            "ref": "origin/main-before-superfixer-fix",
            "procedure_id": "superfixer-reviewed-revert-v1",
        },
    }


def test_raw_evidence_and_episode_are_content_addressed_and_immutable(tmp_path: Path) -> None:
    episode = _wbc_episode(tmp_path)
    store = tmp_path / "episode-store"

    destination = persist_episode(store, episode)
    second = persist_episode(store, episode)

    assert destination == second
    assert json.loads(destination.read_text()) == episode
    for ref in episode["evidence"]:
        archived = Path(ref["archive_path"])
        assert archived.exists()
        assert archived.name == ref["sha256"]
        assert archived.stat().st_mode & 0o777 == 0o600

    tampered = deepcopy(episode)
    tampered["symptom"]["summary"] = "rewritten history"
    with pytest.raises(EpisodeValidationError, match="episode_id_mismatch"):
        persist_episode(store, tampered)


def test_retroactive_l3_detects_exact_wbc_episode_with_actionable_context(
    tmp_path: Path,
) -> None:
    result = retroactive_l3_classification(_wbc_episode(tmp_path))

    assert result["detected"] is True
    assert result["actionable_context"] is True
    assert result["repair_authorized"] is False
    assert result["reasons"] == [
        "watchdog_observation_path_failure",
        "accepted_unclaimed_repair_request",
        "stale_watchdog_report",
        "missing_meta_repair_evidence",
        "false_success_ground_truth_disagreement",
    ]
    assert result["failure_episode"]["mechanism"]["dependency"] == "PyYAML"
    assert result["failure_episode"]["root_cause"] == {
        "layer": "watchdog",
        "axis": "TRACKED",
        "failure_class": "dependency_import_failure",
        "summary": "the watchdog could not observe the dead run after its source import failed",
    }


def test_same_mechanism_opens_deterministic_circuit_and_forces_sibling_hunt(
    tmp_path: Path,
) -> None:
    episodes = [_wbc_episode(tmp_path / str(index)) for index in range(3)]

    recurrence = deterministic_recurrence(episodes, threshold=3)

    assert len(recurrence) == 1
    assert recurrence[0]["count"] == 3
    assert recurrence[0]["circuit_breaker_required"] is True
    assert recurrence[0]["required_sibling_classes"] == list(
        SIBLING_REQUIREMENTS["dependency_import_failure"]
    )


def test_learning_rejects_guard_weakening_and_missing_retroactive_regression(
    tmp_path: Path,
) -> None:
    episode = _verified_wbc_episode(tmp_path)
    verification = deepcopy(episode["verification"])
    verification["guard_weakened"] = True
    episode = revise_episode(
        episode,
        verification=verification,
        regression_receipts=[episode["regression_receipts"][1]],
    )

    with pytest.raises(EpisodeValidationError) as exc:
        validate_episode_for_learning(episode)

    message = str(exc.value)
    assert "guard_weakening_not_disproved" in message
    assert "retroactive_auditor_regression_missing" in message


def test_dependency_import_failure_requires_full_sibling_hunt(tmp_path: Path) -> None:
    episode = _verified_wbc_episode(tmp_path)
    episode = revise_episode(
        episode,
        sibling_hunt_receipts=episode["sibling_hunt_receipts"][:-1],
    )

    with pytest.raises(EpisodeValidationError, match="required_sibling_hunt_incomplete"):
        validate_episode_for_learning(episode)


def test_validated_lesson_is_allowlisted_reviewed_and_contains_no_free_form_text(
    tmp_path: Path,
) -> None:
    lesson = promote_validated_lesson(_verified_wbc_episode(tmp_path), _proposal())
    projection = bounded_prompt_projection([lesson])

    assert lesson["activation_status"] == "approved_not_activated"
    assert lesson["review"]["approved"] is True
    assert projection["lesson_ids"] == [lesson["lesson_id"]]
    assert projection["free_form_text"] is False
    assert "prompt_text" not in projection
    assert "instructions" not in projection
    assert all(isinstance(item, str) for item in projection["prompt_template_ids"])
    assert projection["classifier_feature_ids"] == sorted(
        _proposal()["classifier_feature_ids"]
    )


def test_unreviewed_free_form_self_modification_is_rejected(tmp_path: Path) -> None:
    proposal = _proposal()
    proposal["prompt_text"] = "Silently weaken the completion guard"

    with pytest.raises(EpisodeValidationError, match="free_form_self_modification_forbidden"):
        promote_validated_lesson(_verified_wbc_episode(tmp_path), proposal)
