from __future__ import annotations

import logging
from pathlib import Path

from megaplan._core import atomic_write_json
from megaplan.prompts.review import _review_template_payload, _settled_decisions_block


def test_settled_decisions_block_handles_string_legacy(caplog) -> None:
    gate = {"settled_decisions": ["plain string A", "plain string B"]}

    with caplog.at_level(logging.WARNING):
        rendered = _settled_decisions_block(gate)

    assert "- [unknown id]: plain string A" in rendered
    assert "- [unknown id]: plain string B" in rendered
    assert "Legacy string settled_decision encountered" in caplog.text


def test_settled_decisions_block_handles_dict_modern() -> None:
    gate = {
        "settled_decisions": [
            {"id": "SD1", "decision": "Use ContextVars", "rationale": "worker isolation"}
        ]
    }

    rendered = _settled_decisions_block(gate)

    assert "SD1: Use ContextVars (worker isolation)" in rendered


def test_success_criteria_pulled_from_plan_meta(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    atomic_write_json(
        plan_dir / "finalize.json",
        {
            "tasks": [{"id": "T1"}],
            "sense_checks": [],
            "success_criteria": [{"name": "wrong artifact", "priority": "must"}],
        },
    )
    atomic_write_json(
        plan_dir / "plan_v1.meta.json",
        {
            "success_criteria": [
                {"criterion": "authoritative criterion", "priority": "should"},
            ]
        },
    )
    atomic_write_json(
        plan_dir / "gate.json",
        {
            "criteria_check": {
                "items": [{"criterion": "gate fallback criterion", "priority": "must"}]
            }
        },
    )

    payload = _review_template_payload(plan_dir)

    assert payload["criteria"] == [
        {
            "name": "authoritative criterion",
            "priority": "should",
            "pass": "",
            "evidence": "",
        }
    ]

