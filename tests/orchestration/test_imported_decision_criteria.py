from __future__ import annotations

from arnold_pipelines.megaplan.handlers.shared import (
    _load_bearing_decision_criteria_issues,
    _merge_imported_decision_criteria,
)


def _state() -> dict:
    return {
        "meta": {
            "imported_decisions": [
                {
                    "id": "C01",
                    "decision": "Bind the runtime to the exact source.",
                    "load_bearing": True,
                },
                {
                    "id": "C02",
                    "decision": "Keep the note for context.",
                    "load_bearing": False,
                },
            ]
        }
    }


def test_machine_bound_load_bearing_decision_needs_no_synthetic_criterion() -> None:
    criteria = [
        {
            "criterion": "C01: runtime and source hashes match exactly",
            "priority": "must",
            "requires": ["run_shell"],
        },
        {
            "criterion": "C02 is recorded for context",
            "priority": "info",
            "requires": [],
        },
    ]

    assert _load_bearing_decision_criteria_issues(_state(), criteria) == []
    assert _merge_imported_decision_criteria(_state(), criteria) == criteria


def test_missing_load_bearing_binding_is_reported_before_synthetic_merge() -> None:
    criteria = [
        {
            "criterion": "Runtime and source hashes match exactly",
            "priority": "must",
            "requires": ["run_shell"],
        }
    ]

    assert _load_bearing_decision_criteria_issues(_state(), criteria) == [
        "C01: no success criterion references the exact decision ID"
    ]
    merged = _merge_imported_decision_criteria(_state(), criteria)
    assert merged[-2]["requires"] == ["subjective_judgment"]
    assert "C01" in merged[-2]["criterion"]


def test_human_only_or_non_must_binding_is_not_mechanical_closure() -> None:
    for criterion in (
        {
            "criterion": "C01 follows the imported decision",
            "priority": "must",
            "requires": ["subjective_judgment"],
        },
        {
            "criterion": "C01 runtime source hashes match",
            "priority": "should",
            "requires": ["run_shell"],
        },
    ):
        issues = _load_bearing_decision_criteria_issues(_state(), [criterion])
        assert len(issues) == 1
        assert issues[0].startswith("C01:")
