from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.live_agentic_harness.assessor import _collect_message_artifact_contradictions
from tests.live_agentic_harness.guard import guard_output_dir
from tests.harness_common import (
    DISPATCHER_FAKE,
    DISPATCHER_FAKING,
    DISPATCHER_REAL,
    FLOW_KIND_LIVE_AGENTIC_HEADLESS,
    MODEL_BEHAVIOR_AGENTIC,
    MODEL_BEHAVIOR_DETERMINISTIC,
    MODEL_BEHAVIOR_SCRIPTED,
    STATUS_BLOCKED_PREREQUISITE,
    STATUS_SUCCESS,
)


def _write_flow_metadata(output_dir: Path, **overrides: object) -> None:
    metadata = {
        "flow_kind": FLOW_KIND_LIVE_AGENTIC_HEADLESS,
        "dispatcher": DISPATCHER_REAL,
        "model_behavior": MODEL_BEHAVIOR_AGENTIC,
        "status": STATUS_SUCCESS,
    }
    metadata.update(overrides)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "flow_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")


def _write_successful_candidate(output_dir: Path, **overrides: object) -> None:
    response = {
        "ok": True,
        "graph_unchanged": False,
        "candidate_graph": {"nodes": [{"id": 1}], "links": []},
        "outcome": {"kind": "candidate"},
        "gates": {
            "ir_validate_ok": True,
            "lower_ok": True,
            "plan_validate_ok": True,
            "python_load_ok": True,
            "queue_validate_ok": True,
            "state_match_ok": True,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
    }
    response.update(overrides)
    (output_dir / "response.json").write_text(json.dumps(response), encoding="utf-8")


def _write_ui_pair(output_dir: Path, original: dict, candidate: dict) -> None:
    (output_dir / "original.ui.json").write_text(json.dumps(original), encoding="utf-8")
    (output_dir / "candidate.ui.json").write_text(json.dumps(candidate), encoding="utf-8")


def _effective_target_scenario() -> dict:
    return {
        "id": "effective-edit",
        "assessment": {
            "expect_graph_changed": True,
            "skip_intent_judge": True,
            "effective_edit_targets": [
                {
                    "label": "frame_count",
                    "node_id": 2,
                    "input_name": "frame_count",
                    "widget_index": 0,
                    "source_widget_index": 0,
                }
            ],
        },
    }


def _frame_count_graph(
    *,
    source_value: int = 8,
    target_value: int = 8,
    linked: bool = True,
    shared_source: bool = False,
    save_prefix: str | None = None,
) -> dict:
    link_id = 10 if linked else None
    nodes = []
    links = []
    if linked:
        nodes.append({"id": 1, "type": "PrimitiveInt", "widgets_values": [source_value]})
        links.append([10, 1, 0, 2, 0, "INT"])
    nodes.append(
        {
            "id": 2,
            "type": "VideoGenerator",
            "widgets_values": [target_value],
            "inputs": [{"name": "frame_count", "type": "INT", "link": link_id}],
        }
    )
    if save_prefix is not None:
        nodes.append({"id": 3, "type": "SaveVideo", "widgets_values": [save_prefix]})
    if linked and shared_source:
        nodes.append(
            {
                "id": 4,
                "type": "OtherConsumer",
                "widgets_values": [target_value],
                "inputs": [{"name": "other_count", "type": "INT", "link": 11}],
            }
        )
        links.append([11, 1, 0, 4, 0, "INT"])
    return {"nodes": nodes, "links": links}


@pytest.mark.parametrize("dispatcher", [DISPATCHER_FAKE, DISPATCHER_FAKING])
def test_agentic_guard_rejects_fake_dispatchers(tmp_path: Path, dispatcher: str) -> None:
    output_dir = tmp_path / dispatcher
    _write_flow_metadata(output_dir, dispatcher=dispatcher)

    with pytest.raises(ValueError, match="fake/faking dispatcher"):
        guard_output_dir(output_dir)


@pytest.mark.parametrize("model_behavior", [MODEL_BEHAVIOR_DETERMINISTIC, MODEL_BEHAVIOR_SCRIPTED, None])
def test_agentic_guard_rejects_non_agentic_model_behavior(
    tmp_path: Path,
    model_behavior: str | None,
) -> None:
    output_dir = tmp_path / str(model_behavior)
    _write_flow_metadata(output_dir, model_behavior=model_behavior)

    with pytest.raises(ValueError, match="agentic model behavior"):
        guard_output_dir(output_dir)


def test_agentic_guard_allows_blocked_real_agentic_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "blocked"
    _write_flow_metadata(output_dir, status=STATUS_BLOCKED_PREREQUISITE)

    verdict = guard_output_dir(output_dir)

    assert verdict["live_agentic_success"] is False
    assert verdict["dispatcher"] == DISPATCHER_REAL
    assert verdict["model_behavior"] == MODEL_BEHAVIOR_AGENTIC


def test_agentic_guard_catches_unchanged_graph_and_upstream_errors(tmp_path: Path) -> None:
    """Deep assessment fails a run that reports success but produced no edit."""
    output_dir = tmp_path / "hotshot-failure"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)

    response = {
        "ok": True,
        "graph_unchanged": True,
        "no_candidate_reason": "no_changes",
        "outcome": {"kind": "requires_custom_nodes"},
        "gates": {
            "ir_validate_ok": False,
            "lower_ok": False,
            "python_load_ok": False,
            "queue_validate_ok": False,
            "state_match_ok": True,
            "ui_emit_ok": False,
            "ui_fidelity_ok": False,
            "ui_load_safe_ok": False,
        },
        "report": {
            "executor": {
                "plan": {
                    "implement": True,
                    "route": "adapt",
                },
            },
        },
        "warnings": ["hivemind: Hivemind HTTP error: HTTP Error 500: Internal Server Error"],
    }
    (output_dir / "response.json").write_text(json.dumps(response), encoding="utf-8")
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"message": "The graph is unchanged."}),
        encoding="utf-8",
    )

    scenario = {"id": "hotshot-failure", "assessment": {"expect_graph_changed": True}}
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["metadata_success"] is True
    assert verdict["live_agentic_success"] is False
    assessment = verdict["assessment"]
    assert assessment["passed"] is False
    assert assessment["expect_graph_changed"] is True
    checks = {issue["check"] for issue in assessment["issues"] if issue["severity"] == "error"}
    assert "graph_changed" in checks
    assert "outcome_kind" in checks
    assert "upstream_failure" in checks
    assert "implementation_result" in checks
    assert "gates" in checks


def test_agentic_guard_allows_explicit_safe_refusal_scenarios(tmp_path: Path) -> None:
    output_dir = tmp_path / "safe-refusal"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "no_candidate_reason": "no_changes",
                "outcome": {"kind": "clarify"},
                "gates": {
                    "ir_validate_ok": False,
                    "lower_ok": False,
                    "python_load_ok": False,
                    "queue_validate_ok": False,
                    "state_match_ok": True,
                    "ui_emit_ok": False,
                    "ui_fidelity_ok": False,
                    "ui_load_safe_ok": False,
                },
                "message": "No validated replacement node was found.",
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"message": "No validated replacement node was found."}),
        encoding="utf-8",
    )

    scenario = {
        "id": "safe-refusal",
        "assessment": {
            "expect_graph_changed": False,
            "expected_outcome_kinds": ["clarify", "requires_custom_nodes"],
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is True
    assessment = verdict["assessment"]
    assert assessment["passed"] is True
    assert assessment["expect_graph_changed"] is False
    assert assessment["expected_outcome_kinds"] == ["clarify", "requires_custom_nodes"]


def test_agentic_guard_rejects_unexpected_noop_for_safe_refusal_scenarios(tmp_path: Path) -> None:
    output_dir = tmp_path / "wrong-refusal"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "no_candidate_reason": "no_changes",
                "outcome": {"kind": "noop"},
                "message": "No changes.",
            }
        ),
        encoding="utf-8",
    )

    scenario = {
        "id": "wrong-refusal",
        "assessment": {
            "expect_graph_changed": False,
            "expected_outcome_kind": "clarify",
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is False
    assessment = verdict["assessment"]
    assert assessment["passed"] is False
    assert {issue["check"] for issue in assessment["issues"]} == {"outcome_kind"}


def test_agentic_guard_allows_safe_refusal_as_alternative_to_expected_edit(tmp_path: Path) -> None:
    output_dir = tmp_path / "edit-or-refuse"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "no_candidate_reason": "no_changes",
                "outcome": {"kind": "requires_custom_nodes"},
                "gates": {
                    "ir_validate_ok": False,
                    "lower_ok": False,
                    "python_load_ok": False,
                    "queue_validate_ok": False,
                    "state_match_ok": True,
                    "ui_emit_ok": False,
                    "ui_fidelity_ok": False,
                    "ui_load_safe_ok": False,
                },
                "message": "No schema-backed replacement node was found.",
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "implementation_result.json").write_text(
        json.dumps({"message": "The graph is unchanged."}),
        encoding="utf-8",
    )

    scenario = {
        "id": "edit-or-refuse",
        "assessment": {
            "expect_graph_changed": True,
            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is True
    assessment = verdict["assessment"]
    assert assessment["passed"] is True
    assert assessment["expect_graph_changed"] is True
    assert assessment["allow_safe_refusal_outcome_kinds"] == ["clarify", "requires_custom_nodes"]
    assert {issue["check"] for issue in assessment["issues"]} == {"safe_refusal"}


def test_agentic_guard_rejects_unallowed_noop_when_edit_or_refuse_expected(tmp_path: Path) -> None:
    output_dir = tmp_path / "edit-or-refuse-noop"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": True,
                "no_candidate_reason": "no_changes",
                "outcome": {"kind": "noop"},
                "message": "No changes.",
            }
        ),
        encoding="utf-8",
    )

    scenario = {
        "id": "edit-or-refuse-noop",
        "assessment": {
            "expect_graph_changed": True,
            "allow_safe_refusal_outcome_kinds": ["clarify", "requires_custom_nodes"],
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is False
    checks = {issue["check"] for issue in verdict["assessment"]["issues"] if issue["severity"] == "error"}
    assert "graph_changed" in checks
    assert "no_candidate_reason" in checks


def test_agentic_guard_rejects_oversized_model_request(tmp_path: Path) -> None:
    output_dir = tmp_path / "oversized-model-request"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": False,
                "outcome": {"kind": "candidate"},
                "candidate": {"nodes": [{"id": 1}]},
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "model_request.json").write_text("x" * 101, encoding="utf-8")

    scenario = {
        "id": "oversized-model-request",
        "assessment": {
            "expect_graph_changed": True,
            "skip_intent_judge": True,
            "max_model_request_bytes": 100,
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is False
    issues = verdict["assessment"]["issues"]
    assert {
        issue["check"]
        for issue in issues
        if issue["severity"] == "error"
    } == {"model_request_size"}


def test_agentic_guard_rejects_forbidden_model_request_substrings(tmp_path: Path) -> None:
    output_dir = tmp_path / "forbidden-model-request"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    (output_dir / "response.json").write_text(
        json.dumps(
            {
                "ok": True,
                "graph_unchanged": False,
                "outcome": {"kind": "candidate"},
                "candidate": {"nodes": [{"id": 1}]},
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "model_request.json").write_text(
        '{"turns":[{"messages":[{"content":"raw \\"workflow_schema\\" leaked"}]}]}',
        encoding="utf-8",
    )

    scenario = {
        "id": "forbidden-model-request",
        "assessment": {
            "expect_graph_changed": True,
            "skip_intent_judge": True,
            "forbid_model_request_substrings": ["\"workflow_schema\""],
        },
    }
    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is False
    issues = verdict["assessment"]["issues"]
    assert {
        issue["check"]
        for issue in issues
        if issue["severity"] == "error"
    } == {"model_request_forbidden_substring"}


def test_agentic_guard_rejects_static_widget_edit_overridden_by_link(tmp_path: Path) -> None:
    output_dir = tmp_path / "inert-linked-widget"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    _write_ui_pair(
        output_dir,
        _frame_count_graph(source_value=8, target_value=8, linked=True),
        _frame_count_graph(source_value=8, target_value=16, linked=True),
    )

    verdict = guard_output_dir(output_dir, scenario=_effective_target_scenario())

    assert verdict["live_agentic_success"] is False
    checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert checks == {"inert_effective_edit"}


def test_agentic_guard_rejects_no_effective_value_change_for_claimed_target(tmp_path: Path) -> None:
    output_dir = tmp_path / "no-effective-target-change"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    _write_ui_pair(
        output_dir,
        _frame_count_graph(target_value=8, linked=False, save_prefix="before"),
        _frame_count_graph(target_value=8, linked=False, save_prefix="after"),
    )

    verdict = guard_output_dir(output_dir, scenario=_effective_target_scenario())

    assert verdict["live_agentic_success"] is False
    checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert checks == {"effective_edit"}


def test_agentic_guard_accepts_linked_source_edit_that_changes_effective_value(tmp_path: Path) -> None:
    output_dir = tmp_path / "linked-source-effective-change"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    _write_ui_pair(
        output_dir,
        _frame_count_graph(source_value=8, target_value=8, linked=True),
        _frame_count_graph(source_value=16, target_value=8, linked=True),
    )

    verdict = guard_output_dir(output_dir, scenario=_effective_target_scenario())

    assert verdict["live_agentic_success"] is True
    assert verdict["assessment"]["passed"] is True


def test_collect_message_artifact_contradictions_flags_graph_and_outcome_mismatch() -> None:
    contradictions = _collect_message_artifact_contradictions(
        {
            "message": "Applied 1 edit and updated the workflow.",
            "graph_unchanged": True,
            "outcome": {"kind": "noop"},
            "internal_outcome": {"kind": "noop"},
            "change_details": {"landed_operation_count": 0},
        }
    )

    assert "message claims edits even though response.graph_unchanged is True" in contradictions
    assert "message claims edits even though outcome.kind='noop'" in contradictions
    assert "message claims edits even though internal_outcome.kind='noop'" in contradictions
    assert "message claims landed edits even though landed_operation_count=0" in contradictions


def test_collect_message_artifact_contradictions_flags_missing_clarify_question() -> None:
    contradictions = _collect_message_artifact_contradictions(
        {
            "message": "Applied 1 edit. I need one more detail before continuing.",
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
            "internal_outcome": {"kind": "edit+clarify"},
            "change_details": {"landed_operation_count": 1},
        }
    )

    assert contradictions == [
        "message omits a direct question for internal_outcome.kind='edit+clarify'"
    ]


def test_collect_message_artifact_contradictions_flags_landed_count_mismatch() -> None:
    contradictions = _collect_message_artifact_contradictions(
        {
            "message": "Applied 2 edits to the workflow.",
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
            "internal_outcome": {"kind": "edit"},
            "change_details": {"landed_operation_count": 1},
        }
    )

    assert contradictions == [
        "message claims a landed operation count that disagrees with change_details"
    ]


def test_collect_message_artifact_contradictions_flags_validation_diagnostic_mismatch() -> None:
    contradictions = _collect_message_artifact_contradictions(
        {
            "message": "Applied 1 edit and it is ready to apply.",
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
            "internal_outcome": {"kind": "edit"},
            "change_details": {"landed_operation_count": 1},
            "gates": {
                "python_load_ok": True,
                "ir_validate_ok": False,
                "ui_load_safe_ok": True,
            },
        }
    )

    assert contradictions == [
        "message claims validation success even though diagnostics or gates show failure"
    ]


def test_collect_message_artifact_contradictions_ignores_grounded_non_contradiction() -> None:
    contradictions = _collect_message_artifact_contradictions(
        {
            "message": "Applied 1 edit. Should I also rename the file stem?",
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
            "internal_outcome": {"kind": "edit+clarify"},
            "change_details": {"landed_operation_count": 1},
            "gates": {
                "python_load_ok": True,
                "ir_validate_ok": True,
                "ui_load_safe_ok": True,
                "queue_validate_ok": True,
                "plan_validate_ok": True,
                "state_match_ok": True,
            },
        }
    )

    assert contradictions == []


def test_agentic_guard_rejects_shared_linked_source_edit_by_default(tmp_path: Path) -> None:
    output_dir = tmp_path / "shared-linked-source-effective-change"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    _write_ui_pair(
        output_dir,
        _frame_count_graph(source_value=8, target_value=8, linked=True, shared_source=True),
        _frame_count_graph(source_value=16, target_value=8, linked=True, shared_source=True),
    )

    verdict = guard_output_dir(output_dir, scenario=_effective_target_scenario())

    assert verdict["live_agentic_success"] is False
    checks = {
        issue["check"]
        for issue in verdict["assessment"]["issues"]
        if issue["severity"] == "error"
    }
    assert checks == {"shared_effective_source_edit"}


def test_agentic_guard_allows_shared_linked_source_edit_when_declared(tmp_path: Path) -> None:
    output_dir = tmp_path / "shared-linked-source-intentional"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(output_dir)
    _write_ui_pair(
        output_dir,
        _frame_count_graph(source_value=8, target_value=8, linked=True, shared_source=True),
        _frame_count_graph(source_value=16, target_value=8, linked=True, shared_source=True),
    )
    scenario = _effective_target_scenario()
    scenario["assessment"]["effective_edit_targets"][0]["allow_shared_source_edit"] = True

    verdict = guard_output_dir(output_dir, scenario=scenario)

    assert verdict["live_agentic_success"] is True
    assert verdict["assessment"]["passed"] is True


def test_agentic_guard_treats_skipped_queue_validation_as_warning(tmp_path: Path) -> None:
    output_dir = tmp_path / "queue-skipped"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(
        output_dir,
        gates={
            "ir_validate_ok": True,
            "lower_ok": True,
            "python_load_ok": True,
            "queue_validate_ok": False,
            "state_match_ok": True,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
        debug={
            "stage_snapshots": [
                {"stage": "ingest", "ok": True, "issues": []},
                {"stage": "agent_batch", "ok": True, "issues": []},
            ]
        },
    )

    verdict = guard_output_dir(
        output_dir,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    assert verdict["live_agentic_success"] is True
    assert verdict["score_class"] == "pass"
    assert verdict["assessment"]["passed"] is True
    assert [issue["check"] for issue in verdict["assessment"]["issues"]] == [
        "queue_validate_skipped",
    ]
    assert verdict["assessment"]["issues"][0]["severity"] == "warning"


def test_agentic_guard_product_fails_real_queue_validation_failure(tmp_path: Path) -> None:
    output_dir = tmp_path / "queue-failed"
    _write_flow_metadata(output_dir, status=STATUS_SUCCESS, live=True)
    _write_successful_candidate(
        output_dir,
        gates={
            "ir_validate_ok": True,
            "lower_ok": True,
            "python_load_ok": True,
            "queue_validate_ok": False,
            "state_match_ok": True,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
        debug={
            "stage_snapshots": [
                {
                    "stage": "queue_validate",
                    "ok": False,
                    "issues": [{"code": "schema_less_queue_blocker"}],
                },
            ]
        },
    )

    verdict = guard_output_dir(
        output_dir,
        scenario={"assessment": {"expect_graph_changed": True, "skip_intent_judge": True}},
    )

    assert verdict["live_agentic_success"] is False
    assert verdict["score_class"] == "product_fail"
    assert [issue["check"] for issue in verdict["assessment"]["issues"]] == ["gates"]
    assert "queue_validate_ok" in verdict["assessment"]["issues"][0]["detail"]
