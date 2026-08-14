from __future__ import annotations

import copy
import inspect

import pytest

from arnold_pipelines.megaplan.audits.critique_evaluator import (
    validate_evaluator_verdict,
)
from arnold_pipelines.megaplan.orchestration.critique_runtime import (
    _EVALUATOR_HANDOFF_REFS,
    _fail_closed_on_unverifiable_evaluator_handoff,
)
from arnold_pipelines.megaplan.schemas import SCHEMAS


def _skip(check_id: str) -> dict[str, str]:
    return {"check_id": check_id, "why": "Not needed for this plan."}


def _full_skips() -> list[dict[str, str]]:
    return [
        _skip("issue_hints"),
        _skip("correctness"),
        _skip("scope"),
        _skip("all_locations"),
        _skip("callers"),
        _skip("conventions"),
        _skip("verification"),
        _skip("criteria_quality"),
    ]


def _legacy_four_field_payload() -> dict:
    """The pre-CL3 raw-candidate shape: selections + skipped only."""
    return {
        "selections": [
            {
                "check_id": "prerequisite_ordering",
                "complexity": 4,
                "complexity_justification": "Preconditions matter.",
                "why": "Ordering.",
            }
        ],
        "skipped": _full_skips(),
    }


def test_critique_evaluator_coerces_hard_floor_complexity() -> None:
    payload = {
        "selections": [
            {
                "check_id": "prerequisite_ordering",
                "complexity": 3,
                "complexity_justification": "Partial preconditions need review.",
                "why": "Check the dependency ordering.",
            }
        ],
        "skipped": _full_skips(),
    }

    warnings = validate_evaluator_verdict(
        payload,
        evaluator_model="gpt-5.5",
        vendor="codex",
    )

    assert payload["selections"][0]["complexity"] == 4
    assert any("raised to the hard floor 4" in warning for warning in warnings)


# ── CL3 validation matrix (T20) ──────────────────────────────────────


def test_legacy_four_field_payload_passes_raw_candidate_validation() -> None:
    """A pre-CL3 verdict with only the four legacy fields still validates."""
    payload = _legacy_four_field_payload()
    warnings = validate_evaluator_verdict(
        payload, evaluator_model="gpt-5.5", vendor="codex",
    )
    assert isinstance(warnings, list)
    # Floor coercion still green: complexity 4 is already at the floor.
    assert payload["selections"][0]["complexity"] == 4


def test_invalid_critique_mode_is_rejected() -> None:
    payload = _legacy_four_field_payload()
    payload["critique_mode"] = "STEALTH"
    with pytest.raises(ValueError, match="critique_mode"):
        validate_evaluator_verdict(
            payload, evaluator_model="gpt-5.5", vendor="codex",
            accepted_context={},
        )


def test_critique_mode_allowed_set_restricts_mode() -> None:
    payload = _legacy_four_field_payload()
    payload["critique_mode"] = "BLIND"
    with pytest.raises(ValueError, match="not permitted"):
        validate_evaluator_verdict(
            payload, evaluator_model="gpt-5.5", vendor="codex",
            accepted_context={"allowed_critique_modes": ["HISTORY_AWARE"]},
        )
    # Permitted mode passes.
    payload_ok = _legacy_four_field_payload()
    payload_ok["critique_mode"] = "HISTORY_AWARE"
    validate_evaluator_verdict(
        payload_ok, evaluator_model="gpt-5.5", vendor="codex",
        accepted_context={"allowed_critique_modes": ["HISTORY_AWARE"]},
    )


def test_expected_revision_mismatch_is_rejected() -> None:
    payload = _legacy_four_field_payload()
    payload["expected_revision"] = "rev-999"
    with pytest.raises(ValueError, match="expected_revision"):
        validate_evaluator_verdict(
            payload, evaluator_model="gpt-5.5", vendor="codex",
            accepted_context={"expected_revision": "rev-1"},
        )


def test_expected_briefing_hash_mismatch_is_rejected() -> None:
    payload = _legacy_four_field_payload()
    payload["expected_briefing_hash"] = "deadbeef"
    with pytest.raises(ValueError, match="expected_briefing_hash"):
        validate_evaluator_verdict(
            payload, evaluator_model="gpt-5.5", vendor="codex",
            accepted_context={"expected_briefing_hash": "feedface"},
        )


def test_bad_budgets_type_warns_and_non_integer_max_findings_rejects() -> None:
    # Non-object budgets -> warning (not a hard reject), verdict still returns.
    payload = _legacy_four_field_payload()
    payload["budgets"] = "not-an-object"
    warnings = validate_evaluator_verdict(
        payload, evaluator_model="gpt-5.5", vendor="codex",
        accepted_context={},
    )
    assert any("budgets" in w for w in warnings)

    # A non-negative-integer cap value is a hard reject.
    payload2 = _legacy_four_field_payload()
    payload2["budgets"] = {"max_findings": "plenty"}
    with pytest.raises(ValueError, match="max_findings"):
        validate_evaluator_verdict(
            payload2, evaluator_model="gpt-5.5", vendor="codex",
            accepted_context={},
        )


def test_selection_reasons_must_carry_target_and_reason() -> None:
    payload = _legacy_four_field_payload()
    payload["selection_reasons"] = [{"target": "critique_ledger"}]  # missing reason
    with pytest.raises(ValueError, match="selection_reasons"):
        validate_evaluator_verdict(
            payload, evaluator_model="gpt-5.5", vendor="codex",
            accepted_context={},
        )


def test_input_set_hashes_empty_list_warns() -> None:
    payload = _legacy_four_field_payload()
    payload["input_set_hashes"] = []
    warnings = validate_evaluator_verdict(
        payload, evaluator_model="gpt-5.5", vendor="codex",
        accepted_context={},
    )
    assert any("input_set_hashes" in w for w in warnings)


def test_domain_selections_and_skips_overlap_is_rejected() -> None:
    payload = _legacy_four_field_payload()
    payload["domain_selections"] = [{"domain": "critique_ledger", "why": "core"}]
    payload["domain_skips"] = [{"domain": "critique_ledger", "why": "skip"}]
    with pytest.raises(ValueError, match="Overlap"):
        validate_evaluator_verdict(
            payload, evaluator_model="gpt-5.5", vendor="codex",
            accepted_context={"available_domains": ["critique_ledger", "second"]},
        )


def test_evaluator_schema_is_strict_closed_with_additional_properties_false() -> None:
    from arnold_pipelines.megaplan._core.io import _enforce_openai_strict_mode

    schema = _enforce_openai_strict_mode(
        copy.deepcopy(SCHEMAS["critique_evaluator.json"])
    )
    assert schema.get("additionalProperties") is False
    # Nested object schemas must also stay closed under strict mode.
    for _name, prop in schema.get("properties", {}).items():
        if isinstance(prop, dict) and prop.get("type") == "object":
            assert prop.get("additionalProperties") is False


def test_evaluator_prompt_enumerates_every_cl3_output_key() -> None:
    from arnold_pipelines.megaplan.prompts import critique_evaluator as ce_prompt

    src = inspect.getsource(ce_prompt)
    required_keys = (
        "domain_selections",
        "domain_skips",
        "critique_mode",
        "budgets",
        "expected_revision",
        "expected_briefing_hash",
        "selection_reasons",
        "input_set_hashes",
    )
    missing = [k for k in required_keys if k not in src]
    assert not missing, f"prompt missing CL3 output keys: {missing}"


# ── Occurrence a2c3644905c0 regression: self-declared fields must not fail ──
# closed when the runtime declares no matching cap/handoff. `budgets` and
# `input_set_hashes` are prompt-mandated self-declared fields; the validator
# enforces `budgets.max_findings` only when a cap is declared and shape-checks
# `input_set_hashes`. The fail-closed handoff check must only cover accepted
# runtime context (provenance echoes / routing refs).


def test_budgets_without_declared_cap_do_not_fail_closed() -> None:
    payload = _legacy_four_field_payload()
    payload["budgets"] = {
        "max_tokens": 18000,
        "max_latency_seconds": 900,
        "max_findings": 8,
    }
    # No raise: accepted context declares no max_budget_findings.
    _fail_closed_on_unverifiable_evaluator_handoff(payload, {})
    warnings = validate_evaluator_verdict(
        payload, evaluator_model="gpt-5.5", vendor="codex",
        accepted_context={},
    )
    assert isinstance(warnings, list)


def test_input_set_hashes_without_ledger_handoff_do_not_fail_closed() -> None:
    payload = _legacy_four_field_payload()
    payload["input_set_hashes"] = [
        "sha256:51b0bfe556d41b98eed5d09c1f2c6d82ebd1ecc805261bc41c1dd958ab0462d6",
        "sha256:1c1dbb394915e41352101ef791b625fadf7a095661fb8ee0caa8119bb6d18a1d",
    ]
    # No raise: accepted context has no input_set_hash (no ledger handoff).
    _fail_closed_on_unverifiable_evaluator_handoff(payload, {})
    warnings = validate_evaluator_verdict(
        payload, evaluator_model="gpt-5.5", vendor="codex",
        accepted_context={},
    )
    assert isinstance(warnings, list)


def test_budgets_with_declared_cap_still_enforced_by_validator() -> None:
    payload = _legacy_four_field_payload()
    payload["budgets"] = {"max_tokens": 1, "max_latency_seconds": 1, "max_findings": 8}
    _fail_closed_on_unverifiable_evaluator_handoff(
        payload, {"max_budget_findings": 8},
    )
    with pytest.raises(ValueError, match="exceeds accepted cap"):
        validate_evaluator_verdict(
            payload, evaluator_model="gpt-5.5", vendor="codex",
            accepted_context={"max_budget_findings": 7},
        )


def test_remaining_handoff_refs_still_fail_closed() -> None:
    # The six remaining refs (provenance echoes / routing refs) must keep
    # failing closed when the accepted context cannot corroborate them.
    refs = {
        "expected_revision": "expected_revision",
        "expected_briefing_hash": "expected_briefing_hash",
        "domain_selections": "known_domains",
        "domain_skips": "known_domains",
        "evidence_targets": "known_finding_refs",
        "critique_mode": "allowed_critique_modes",
    }
    assert refs == _EVALUATOR_HANDOFF_REFS
    for field, ctx_key in refs.items():
        payload = _legacy_four_field_payload()
        payload[field] = {
            "expected_revision": "rev-1",
            "expected_briefing_hash": "brief-1",
            "domain_selections": [{"domain": "critique_ledger", "why": "core"}],
            "domain_skips": [{"domain": "other", "why": "not needed"}],
            "evidence_targets": ["finding-1"],
            "critique_mode": "BLIND",
        }[field]
        with pytest.raises(ValueError, match="unverifiable handoff reference"):
            _fail_closed_on_unverifiable_evaluator_handoff(payload, {})
