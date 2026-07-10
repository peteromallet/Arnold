from __future__ import annotations

import json
from pathlib import Path

from tests.live_agentic_harness.intent_judge import judge_edit_intent


def test_intent_judge_includes_compiled_api_schema_context(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    original = tmp_path / "original.ui.json"
    candidate = tmp_path / "candidate.ui.json"
    original.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    candidate.write_text(json.dumps({"nodes": []}), encoding="utf-8")
    (tmp_path / "response.json").write_text(
        json.dumps(
            {
                "artifacts": {
                    "original_ui": str(original),
                    "candidate_ui": str(candidate),
                }
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "implementation_payload.json").write_text(
        json.dumps(
            {
                "graph": {
                    "compiled_api": {
                        "3": {
                            "class_type": "llama_cpp_parameters",
                            "inputs": {
                                "max_tokens": 512,
                                "temperature": 0.8,
                                "top_p": 0.9,
                            },
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202
        seen["messages"] = messages
        return {
            "content": json.dumps(
                {
                    "pass_": True,
                    "criteria": {
                        "correct_node_targeted": True,
                        "correct_parameter_changed": True,
                        "value_semantically_matches_intent": True,
                        "no_orphaned_wiring": True,
                    },
                    "rationale": "ok",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )

    verdict = judge_edit_intent(
        tmp_path,
        {"query": "set temperature to 0.8 and max tokens to 512"},
    )

    assert verdict["pass_"] is True
    messages = seen["messages"]
    assert isinstance(messages, list)
    payload = json.loads(messages[1]["content"])
    assert payload["schema_context"]["compiled_api"]["3"]["inputs"]["temperature"] == 0.8
    assert "Schema and widget evidence" in messages[0]["content"]


def test_intent_judge_labels_static_widget_removal_and_preserved_dynamic_input(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    original = tmp_path / "original.ui.json"
    candidate = tmp_path / "candidate.ui.json"
    original.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 184,
                        "type": "Florence2Run",
                        "outputs": [{"name": "STRING", "type": "STRING", "slot_index": 0, "links": [7]}],
                    },
                    {
                        "id": 182,
                        "type": "StringFunction",
                        "inputs": [{"name": "text_a", "type": "STRING", "link": 7}],
                        "widgets_values": ["append", "", "", "", "real footage", "fabricated couch caption"],
                    },
                ],
                "links": [[7, 184, 0, 182, 0, "STRING"]],
            }
        ),
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 184,
                        "type": "Florence2Run",
                        "outputs": [{"name": "STRING", "type": "STRING", "slot_index": 0, "links": [7]}],
                    },
                    {
                        "id": 182,
                        "type": "StringFunction",
                        "inputs": [{"name": "text_a", "type": "STRING", "link": 7}],
                        "widgets_values": ["append", "", "", "", "real footage", ""],
                    },
                ],
                "links": [[7, 184, 0, 182, 0, "STRING"]],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "response.json").write_text(
        json.dumps({"artifacts": {"original_ui": str(original), "candidate_ui": str(candidate)}}),
        encoding="utf-8",
    )

    seen: dict[str, object] = {}

    def fake_run_model_turn(task, *, messages, **kwargs):  # noqa: ANN001, ANN202
        seen["messages"] = messages
        return {
            "content": json.dumps(
                {
                    "pass_": True,
                    "criteria": {
                        "correct_node_targeted": True,
                        "correct_parameter_changed": True,
                        "value_semantically_matches_intent": True,
                        "no_orphaned_wiring": True,
                    },
                    "rationale": "ok",
                }
            )
        }

    monkeypatch.setattr(
        "tests.live_agentic_harness.intent_judge.run_model_turn",
        fake_run_model_turn,
    )

    verdict = judge_edit_intent(
        tmp_path,
        {"query": "The prompt it generates doesn't capture what's actually in the image."},
    )

    assert verdict["pass_"] is True
    messages = seen["messages"]
    assert isinstance(messages, list)
    payload = json.loads(messages[1]["content"])
    dataflow = payload["schema_context"]["dataflow_context"]
    removals = dataflow["static_widget_removals_with_preserved_dynamic_inputs"]
    assert removals[0]["node_id"] == "182"
    assert removals[0]["widget_index"] == 5
    assert removals[0]["preserved_dynamic_inputs"] is True
    assert removals[0]["linked_inputs_post"][0]["source"]["class_type"] == "Florence2Run"
    assert "static widget" in messages[0]["content"]
