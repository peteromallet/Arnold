from __future__ import annotations

import json
import subprocess
import sys

from vibecomfy.comfy_nodes.agent.executor_response import serialize_executor_result


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_executor_response_module_import_does_not_load_routes_or_executor_core() -> None:
    code = """
import sys
import vibecomfy.comfy_nodes.agent.executor_response
assert "vibecomfy.comfy_nodes.agent.routes" not in sys.modules
assert "vibecomfy.executor.core" not in sys.modules
"""

    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_serialize_executor_result_shapes_clarify_response_without_apply_fields() -> None:
    payload = {
        "ok": True,
        "route": "clarify",
        "reply": "Which model should I use?",
        "candidate": {"graph": {"nodes": []}},
        "candidate_graph": {"nodes": []},
        "graph": {"nodes": []},
        "apply_eligible": True,
        "apply_eligibility": {"applyable": True, "reason": "applyable"},
        "eligibility": {"applyable": True, "reason": "applyable"},
        "apply_allowed": True,
        "canvas_apply_allowed": True,
        "queue_allowed": True,
    }

    serialized = serialize_executor_result(payload)

    assert serialized == {
        "ok": True,
        "route": "clarify",
        "reply": "Which model should I use?",
        "message": "Which model should I use?",
        "graph_unchanged": False,
        "outcome": {
            "kind": "clarify",
            "question": "Which model should I use?",
            "clarification": {"message": "Which model should I use?"},
        },
        "clarification_required": True,
        "clarification_message": "Which model should I use?",
    }


def test_serialize_executor_result_strips_non_applyable_response_fields() -> None:
    payload = {
        "ok": True,
        "route": "requires_custom_nodes",
        "reply": "Install custom nodes before applying edits.",
        "outcome": {"kind": "requires_custom_nodes", "candidates": [{"expected_classes": ["VHS_VideoCombine"]}]},
        "candidate": {"graph": {"nodes": [{"id": 1}], "links": []}},
        "candidate_graph": {"nodes": [{"id": 1}], "links": []},
        "graph": {"nodes": [{"id": 1}], "links": []},
        "apply_eligible": True,
        "apply_eligibility": {"applyable": True, "reason": "applyable"},
        "eligibility": {"applyable": True, "reason": "applyable"},
        "apply_allowed": True,
        "canvas_apply_allowed": True,
        "queue_allowed": True,
    }

    serialized = serialize_executor_result(payload)

    assert serialized["outcome"] == payload["outcome"]
    for forbidden_key in (
        "candidate",
        "candidate_graph",
        "graph",
        "apply_eligible",
        "apply_eligibility",
        "eligibility",
        "apply_allowed",
        "canvas_apply_allowed",
        "queue_allowed",
    ):
        assert forbidden_key not in serialized


def test_routes_executor_serializer_matches_extracted_helper(monkeypatch) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    from vibecomfy.comfy_nodes.agent import routes

    payload = {
        "ok": True,
        "route": "clarify",
        "reply": "What style should I use?",
        "candidate": {"graph": {"nodes": []}},
        "apply_eligible": True,
    }

    assert _canonical_json(routes._serialize_executor_result(payload)) == _canonical_json(
        serialize_executor_result(payload)
    )
