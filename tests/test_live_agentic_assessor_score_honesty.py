from __future__ import annotations

import json
from pathlib import Path

from tests.live_agentic_harness.assessor import assess_live_output_dir


def test_recovered_upstream_500_is_warning_when_candidate_succeeded(tmp_path: Path) -> None:
    response = {
        "ok": True,
        "graph_unchanged": False,
        "candidate_graph": {"1": {"class_type": "TestNode"}},
        "warnings": ["Hivemind HTTP error 500: Internal Server Error"],
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    upstream = [issue for issue in assessment["issues"] if issue["check"] == "upstream_failure"]
    assert upstream
    assert {issue["severity"] for issue in upstream} == {"warning"}
    assert assessment["passed"] is True


def test_upstream_500_remains_error_without_candidate(tmp_path: Path) -> None:
    response = {
        "ok": False,
        "graph_unchanged": True,
        "error": "Hivemind HTTP error 500: Internal Server Error",
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    upstream = [issue for issue in assessment["issues"] if issue["check"] == "upstream_failure"]
    assert upstream
    assert {issue["severity"] for issue in upstream} == {"error"}
    assert assessment["passed"] is False


def test_skipped_queue_validation_remains_missing_evidence_when_candidate_succeeded(tmp_path: Path) -> None:
    response = {
        "ok": True,
        "graph_unchanged": False,
        "candidate_graph": {"1": {"class_type": "SaveAudio"}},
        "gates": {
            "ir_validate_ok": True,
            "lower_ok": True,
            "python_load_ok": True,
            "queue_validate_ok": False,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
        "debug": {
            "stage_snapshots": [
                {"stage": "ingest", "ok": True, "issues": []},
                {"stage": "agent_batch", "ok": True, "issues": []},
            ]
        },
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    assert assessment["passed"] is False
    assert [issue["check"] for issue in assessment["issues"]] == [
        "queue_validate_skipped",
        "gates",
    ]
    assert assessment["issues"][0]["severity"] == "warning"
    assert assessment["issues"][1]["severity"] == "error"


def test_queue_validation_stage_failure_still_fails(tmp_path: Path) -> None:
    response = {
        "ok": True,
        "graph_unchanged": False,
        "candidate_graph": {"1": {"class_type": "SaveAudio"}},
        "gates": {
            "ir_validate_ok": True,
            "lower_ok": True,
            "python_load_ok": True,
            "queue_validate_ok": False,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
        "debug": {
            "stage_snapshots": [
                {"stage": "queue_validate", "ok": False, "issues": [{"code": "schema_less_queue_blocker"}]},
            ]
        },
    }
    (tmp_path / "response.json").write_text(json.dumps(response), encoding="utf-8")

    assessment = assess_live_output_dir(
        tmp_path,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    assert assessment["passed"] is False
    assert any(issue["check"] == "gates" for issue in assessment["issues"])
