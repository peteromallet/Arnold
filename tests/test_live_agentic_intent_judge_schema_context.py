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
