from __future__ import annotations

import logging
import json
from pathlib import Path

from arnold.pipelines.megaplan._core import atomic_write_json
from arnold.pipelines.megaplan.prompts.review import (
    _review_evidence_block,
    _review_template_payload,
    _settled_decisions_block,
)


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

    assert payload["review_completion_status"] == ""
    assert payload["criteria"] == [
        {
            "name": "authoritative criterion",
            "priority": "should",
            "pass": "",
            "evidence": "",
        }
    ]


def test_review_evidence_block_handles_missing_malformed_and_empty_artifacts(tmp_path: Path) -> None:
    missing = _review_evidence_block(tmp_path)
    assert "Fresh review-time evidence (`review_evidence.json`): degraded." in missing
    assert "`review_evidence.json` is absent." in missing

    (tmp_path / "review_evidence.json").write_text("{", encoding="utf-8")
    malformed = _review_evidence_block(tmp_path)
    assert "`review_evidence.json` is malformed or unreadable" in malformed

    atomic_write_json(tmp_path / "review_evidence.json", {"evidence": []})
    empty = _review_evidence_block(tmp_path)
    assert "`review_evidence.json` has zero evidence refs." in empty


def test_review_evidence_block_renders_fresh_evidence_separately(tmp_path: Path) -> None:
    atomic_write_json(
        tmp_path / "review_evidence.json",
        {"evidence": [{"kind": "green_suite", "status": "satisfied", "summary": "ok"}]},
    )

    rendered = _review_evidence_block(tmp_path)

    assert "Fresh review-time evidence (`review_evidence.json`):" in rendered
    parsed = json.loads(rendered.split(":\n", 1)[1])
    assert parsed["evidence"][0]["kind"] == "green_suite"
