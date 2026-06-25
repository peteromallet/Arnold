"""Regression tests for hermes worker template-content detection."""

import json

from arnold.pipelines.megaplan.workers.hermes import (
    _persist_template_fallback_payload,
    _template_has_content,
    parse_agent_output,
)


def _seed() -> dict:
    return {
        "selections": [],
        "skipped": [
            {"check_id": "issue_hints", "why": ""},
            {"check_id": "correctness", "why": ""},
        ],
        "evaluator_model": "",
        "flag_verifications": [],
    }


def _valid_verdict() -> dict:
    return {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 4,
                "complexity_justification": "non-empty",
                "area": "",
            }
        ],
        "skipped": [
            {"check_id": "issue_hints", "why": "not applicable"},
        ],
        "evaluator_model": "claude-sonnet-4-6",
        "flag_verifications": [],
    }


def test_critique_evaluator_seed_has_no_content() -> None:
    assert _template_has_content(_seed(), "critique_evaluator") is False


def test_critique_evaluator_valid_verdict_has_content() -> None:
    assert _template_has_content(_valid_verdict(), "critique_evaluator") is True


def test_critique_evaluator_all_skipped_with_justifications_has_no_content() -> None:
    verdict = {
        "selections": [],
        "skipped": [
            {"check_id": "issue_hints", "why": "not applicable"},
            {"check_id": "correctness", "why": "not applicable"},
        ],
        "evaluator_model": "model-x",
        "flag_verifications": [],
    }
    assert _template_has_content(verdict, "critique_evaluator") is False


def test_critique_evaluator_requires_skip_reasons() -> None:
    verdict = {
        "selections": [
            {
                "check_id": "correctness",
                "complexity": 4,
                "complexity_justification": "Correctness remains load-bearing.",
            }
        ],
        "skipped": [
            {"check_id": "issue_hints", "why": ""},
        ],
        "evaluator_model": "model-x",
        "flag_verifications": [],
    }
    assert _template_has_content(verdict, "critique_evaluator") is False


def test_critique_evaluator_missing_model_has_no_content() -> None:
    verdict = dict(_valid_verdict())
    verdict["evaluator_model"] = ""
    assert _template_has_content(verdict, "critique_evaluator") is False


def test_critique_evaluator_valid_other_selection_has_content() -> None:
    verdict = {
        "selections": [
            {
                "check_id": "other",
                "area": "Packaging",
                "why": "Check packaging-specific release drift.",
                "complexity": 2,
                "complexity_justification": "Localized metadata review.",
            }
        ],
        "skipped": [
            {"check_id": "issue_hints", "why": "not applicable"},
        ],
        "evaluator_model": "model-x",
        "flag_verifications": [],
    }
    assert _template_has_content(verdict, "critique_evaluator") is True


def test_other_steps_use_generic_detection() -> None:
    # A generic step with a non-empty array should still be treated as content.
    assert _template_has_content({"items": [1]}, "some_other_step") is True
    # An empty generic payload is not content.
    assert _template_has_content({"items": []}, "some_other_step") is False


def _gate_seed() -> dict:
    return {
        "recommendation": "",
        "rationale": "",
        "signals_assessment": "",
        "warnings": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [
            {
                "flag_id": "",
                "concern": "",
                "subsystem": "",
                "rationale": "",
            }
        ],
        "settled_decisions": [],
    }


def _gate_verdict() -> dict:
    return {
        "recommendation": "ITERATE",
        "rationale": "Blocking correctness concern remains unresolved.",
        "signals_assessment": "One significant flag remains open.",
        "warnings": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
        "settled_decisions": [],
    }


def test_gate_seed_has_no_content_despite_placeholder_tradeoff() -> None:
    assert _template_has_content(_gate_seed(), "gate") is False


def test_gate_verdict_has_content() -> None:
    assert _template_has_content(_gate_verdict(), "gate") is True


def test_persist_fallback_payload_replaces_critique_evaluator_seed(tmp_path) -> None:
    output_path = tmp_path / "critique_evaluator_output.json"
    output_path.write_text(json.dumps(_seed(), indent=2), encoding="utf-8")

    _persist_template_fallback_payload(
        output_path,
        _valid_verdict(),
        "critique_evaluator",
    )

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == _valid_verdict()


def test_persist_fallback_payload_replaces_gate_seed(tmp_path) -> None:
    output_path = tmp_path / "gate_output.json"
    output_path.write_text(json.dumps(_gate_seed(), indent=2), encoding="utf-8")

    _persist_template_fallback_payload(output_path, _gate_verdict(), "gate")

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == _gate_verdict()


def test_persist_fallback_payload_does_not_write_empty_skip_reasons(tmp_path) -> None:
    output_path = tmp_path / "critique_evaluator_output.json"
    output_path.write_text(json.dumps(_seed(), indent=2), encoding="utf-8")

    invalid = _valid_verdict()
    invalid["skipped"] = [{"check_id": "issue_hints", "why": ""}]

    _persist_template_fallback_payload(output_path, invalid, "critique_evaluator")

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == _seed()


def test_parse_agent_output_persists_markdown_fallback_to_template_file(tmp_path) -> None:
    output_path = tmp_path / "critique_evaluator_output.json"
    output_path.write_text(json.dumps(_seed(), indent=2), encoding="utf-8")
    verdict = _valid_verdict()
    result = {
        "final_response": "```json\n" + json.dumps(verdict) + "\n```",
        "messages": [],
    }

    payload, _ = parse_agent_output(
        agent=None,
        result=result,
        output_path=output_path,
        schema={},
        step="critique_evaluator",
        project_dir=tmp_path,
        plan_dir=tmp_path,
    )

    assert payload == verdict
    assert json.loads(output_path.read_text(encoding="utf-8")) == verdict
