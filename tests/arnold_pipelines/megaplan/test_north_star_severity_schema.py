"""Focused tests for North Star action severity normalization.

Proves: dangerous categories are schema-forced to blocking, worker-provided
blocking severity is preserved for non-dangerous categories, and normalized
metadata (identity, concern, evidence, plan refs, etc.) survives the round-trip
intact.
"""

from __future__ import annotations

from typing import Any

import pytest

from arnold_pipelines.megaplan.north_star_actions import (
    SEVERITY_ADVISORY,
    SEVERITY_BLOCKING,
    SEVERITY_SOURCE_EXPLICIT,
    SEVERITY_SOURCE_SCHEMA,
    SEVERITY_SOURCE_WORKER,
    NORTH_STAR_DANGEROUS_CATEGORIES,
    NORTH_STAR_SEVERITY_SOURCES,
    NorthStarActionValidationError,
    blocking_north_star_actions,
    is_blocking_action,
    is_blocking_category,
    normalize_north_star_action,
    normalize_north_star_actions,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _base_action(**overrides: Any) -> dict[str, Any]:
    """Minimal well-formed advisory action the normalizer accepts."""
    action: dict[str, Any] = {
        "id": "ns-001",
        "concern": "The plan should include a rollback step.",
        "category": "completeness",
        "action_type": "change_plan",
        "severity": SEVERITY_ADVISORY,
        "severity_source": SEVERITY_SOURCE_WORKER,
        "evidence": "Step 3 has no undo path.",
    }
    action.update(overrides)
    return action


# --------------------------------------------------------------------------- #
# Dangerous categories – schema-authoritative blocking
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("dangerous_cat", sorted(NORTH_STAR_DANGEROUS_CATEGORIES))
def test_dangerous_category_forced_to_blocking_regardless_of_producer_label(
    dangerous_cat: str,
) -> None:
    """A dangerous-category action MUST normalize to blocking/schema even when
    the producer labelled it advisory."""
    raw = _base_action(
        category=dangerous_cat,
        severity=SEVERITY_ADVISORY,
        severity_source=SEVERITY_SOURCE_WORKER,
    )
    result = normalize_north_star_action(raw)

    assert result["severity"] == SEVERITY_BLOCKING, (
        f"Dangerous category {dangerous_cat!r} was not forced to blocking"
    )
    assert result["severity_source"] == SEVERITY_SOURCE_SCHEMA, (
        f"Dangerous category {dangerous_cat!r} should have schema source"
    )


@pytest.mark.parametrize("dangerous_cat", sorted(NORTH_STAR_DANGEROUS_CATEGORIES))
def test_dangerous_category_blocking_when_producer_omits_severity(
    dangerous_cat: str,
) -> None:
    """When the producer omits severity entirely, dangerous categories still
    become blocking/schema."""
    raw = _base_action(category=dangerous_cat)
    raw.pop("severity", None)
    raw.pop("severity_source", None)

    result = normalize_north_star_action(raw)

    assert result["severity"] == SEVERITY_BLOCKING
    assert result["severity_source"] == SEVERITY_SOURCE_SCHEMA


@pytest.mark.parametrize("dangerous_cat", sorted(NORTH_STAR_DANGEROUS_CATEGORIES))
def test_dangerous_category_blocking_when_producer_already_says_blocking(
    dangerous_cat: str,
) -> None:
    """Even when the producer correctly labels a dangerous action blocking,
    the source must still flip to schema."""
    raw = _base_action(
        category=dangerous_cat,
        severity=SEVERITY_BLOCKING,
        severity_source=SEVERITY_SOURCE_WORKER,
    )
    result = normalize_north_star_action(raw)

    assert result["severity"] == SEVERITY_BLOCKING
    assert result["severity_source"] == SEVERITY_SOURCE_SCHEMA


# --------------------------------------------------------------------------- #
# Non-dangerous categories – worker-provided blocking preserved
# --------------------------------------------------------------------------- #


def test_non_dangerous_worker_blocking_preserved() -> None:
    """A non-dangerous action explicitly marked blocking by the worker stays
    blocking and carries the worker's severity_source."""
    raw = _base_action(
        severity=SEVERITY_BLOCKING,
        severity_source=SEVERITY_SOURCE_WORKER,
        evidence="Must add a guard before merging.",
    )
    result = normalize_north_star_action(raw)

    assert result["severity"] == SEVERITY_BLOCKING
    assert result["severity_source"] == SEVERITY_SOURCE_WORKER


def test_non_dangerous_worker_blocking_explicit_source() -> None:
    """When severity_source is missing/unknown but severity=blocking, the
    normalizer records 'explicit' as provenance."""
    raw = _base_action(
        severity=SEVERITY_BLOCKING,
        evidence="Concrete evidence.",
    )
    raw.pop("severity_source", None)

    result = normalize_north_star_action(raw)

    assert result["severity"] == SEVERITY_BLOCKING
    assert result["severity_source"] == SEVERITY_SOURCE_EXPLICIT


def test_non_dangerous_advisory_stays_advisory() -> None:
    """A non-dangerous action labelled advisory remains advisory."""
    raw = _base_action(severity=SEVERITY_ADVISORY)
    result = normalize_north_star_action(raw)

    assert result["severity"] == SEVERITY_ADVISORY
    # Advisory actions preserve explicit provenance when available,
    # else get 'explicit'.
    assert result["severity_source"] in NORTH_STAR_SEVERITY_SOURCES


def test_non_dangerous_no_severity_defaults_advisory() -> None:
    """When no severity is provided for a non-dangerous action, it defaults
    to advisory."""
    raw = _base_action()
    raw.pop("severity", None)
    raw.pop("severity_source", None)

    result = normalize_north_star_action(raw)

    assert result["severity"] == SEVERITY_ADVISORY


# --------------------------------------------------------------------------- #
# Metadata preservation
# --------------------------------------------------------------------------- #


def test_normalized_action_preserves_identity_fields() -> None:
    """id, question_id, and question are carried through unchanged."""
    raw = _base_action(
        id="ns-identity-1",
        question_id="q-42",
        question="Does this plan handle rollback?",
    )
    result = normalize_north_star_action(raw)

    assert result["id"] == "ns-identity-1"
    assert result["question_id"] == "q-42"
    assert result["question"] == "Does this plan handle rollback?"


def test_normalized_action_preserves_core_fields() -> None:
    """concern, category, action_type, evidence survive normalization."""
    raw = _base_action(
        concern="Missing fallback handler.",
        category="correctness",
        action_type="add_gate",
        evidence="Trace in issue #112.",
    )
    result = normalize_north_star_action(raw)

    assert result["concern"] == "Missing fallback handler."
    assert result["category"] == "correctness"
    assert result["action_type"] == "add_gate"
    assert result["evidence"] == "Trace in issue #112."


def test_normalized_action_preserves_plan_refs() -> None:
    """plan_refs list is carried through when well-formed."""
    raw = _base_action(plan_refs=["section-3", "section-7"])
    result = normalize_north_star_action(raw)

    assert result["plan_refs"] == ["section-3", "section-7"]


def test_normalized_action_preserves_required_change() -> None:
    """required_change prose is preserved."""
    raw = _base_action(required_change="Add a rollback gate before deploy.")
    result = normalize_north_star_action(raw)

    assert result["required_change"] == "Add a rollback gate before deploy."


def test_optional_fields_omitted_when_not_present() -> None:
    """Fields not in the raw input are not injected into the normalized dict."""
    raw = _base_action()
    raw.pop("question_id", None)
    raw.pop("question", None)
    raw.pop("plan_refs", None)
    raw.pop("required_change", None)

    result = normalize_north_star_action(raw)

    assert "question_id" not in result
    assert "question" not in result
    assert "plan_refs" not in result
    assert "required_change" not in result


# --------------------------------------------------------------------------- #
# Validation errors (fail-loud)
# --------------------------------------------------------------------------- #


def test_raises_on_non_dict() -> None:
    with pytest.raises(NorthStarActionValidationError, match="must be an object"):
        normalize_north_star_action(["not", "a", "dict"])


def test_raises_on_missing_id() -> None:
    raw = _base_action()
    raw.pop("id")
    with pytest.raises(NorthStarActionValidationError, match="missing or empty 'id'"):
        normalize_north_star_action(raw)


def test_raises_on_empty_id() -> None:
    raw = _base_action(id="   ")
    with pytest.raises(NorthStarActionValidationError, match="missing or empty 'id'"):
        normalize_north_star_action(raw)


def test_raises_on_missing_concern() -> None:
    raw = _base_action()
    raw.pop("concern")
    with pytest.raises(NorthStarActionValidationError, match="missing or empty 'concern'"):
        normalize_north_star_action(raw)


def test_raises_on_invalid_category() -> None:
    raw = _base_action(category="not_a_real_category")
    with pytest.raises(NorthStarActionValidationError, match="invalid or missing 'category'"):
        normalize_north_star_action(raw)


def test_raises_on_invalid_action_type() -> None:
    raw = _base_action(action_type="do_something_vague")
    with pytest.raises(NorthStarActionValidationError, match="invalid or missing 'action_type'"):
        normalize_north_star_action(raw)


def test_raises_blocking_without_evidence() -> None:
    """A blocking action (dangerous category) with empty evidence must raise."""
    raw = _base_action(
        category="route_authority",
        evidence="",
    )
    with pytest.raises(NorthStarActionValidationError, match="missing non-empty 'evidence'"):
        normalize_north_star_action(raw)


def test_raises_blocking_with_whitespace_only_evidence() -> None:
    raw = _base_action(
        category="baselines",
        evidence="   ",
    )
    with pytest.raises(NorthStarActionValidationError, match="missing non-empty 'evidence'"):
        normalize_north_star_action(raw)


def test_raises_blocking_non_dangerous_without_evidence() -> None:
    """A non-dangerous action the worker labelled blocking must also carry evidence."""
    raw = _base_action(
        severity=SEVERITY_BLOCKING,
        evidence="",
    )
    with pytest.raises(NorthStarActionValidationError, match="missing non-empty 'evidence'"):
        normalize_north_star_action(raw)


# --------------------------------------------------------------------------- #
# Batch normalization
# --------------------------------------------------------------------------- #


def test_normalize_north_star_actions_empty_on_none() -> None:
    assert normalize_north_star_actions(None) == []


def test_normalize_north_star_actions_empty_on_empty_list() -> None:
    assert normalize_north_star_actions([]) == []


def test_normalize_north_star_actions_normalizes_batch() -> None:
    raw = [
        _base_action(id="a1", category="route_authority"),
        _base_action(id="a2", severity=SEVERITY_BLOCKING, evidence="Evidence for a2."),
    ]
    result = normalize_north_star_actions(raw)

    assert len(result) == 2
    # First is dangerous -> schema blocking
    assert result[0]["id"] == "a1"
    assert result[0]["severity"] == SEVERITY_BLOCKING
    assert result[0]["severity_source"] == SEVERITY_SOURCE_SCHEMA
    # Second is non-dangerous, worker-blocking
    assert result[1]["id"] == "a2"
    assert result[1]["severity"] == SEVERITY_BLOCKING
    assert result[1]["severity_source"] == SEVERITY_SOURCE_WORKER


def test_normalize_north_star_actions_raises_on_non_list() -> None:
    with pytest.raises(NorthStarActionValidationError, match="must be a list"):
        normalize_north_star_actions({"key": "value"})


def test_normalize_north_star_actions_raises_if_any_element_invalid() -> None:
    raw = [
        _base_action(id="ok"),
        _base_action(id="bad", category="INVALID"),
    ]
    with pytest.raises(NorthStarActionValidationError, match="invalid or missing 'category'"):
        normalize_north_star_actions(raw)


def test_normalize_north_star_actions_includes_index_in_error() -> None:
    """A malformed action at a known index should surface the index in the error message."""
    raw = [
        _base_action(id="first"),
        {"id": "second", "concern": "missing required fields"},
    ]
    with pytest.raises(NorthStarActionValidationError, match="north_star_actions\\[1\\]"):
        normalize_north_star_actions(raw)


# --------------------------------------------------------------------------- #
# Helpers: is_blocking_category / is_blocking_action / blocking_north_star_actions
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("dangerous_cat", sorted(NORTH_STAR_DANGEROUS_CATEGORIES))
def test_is_blocking_category_true_for_dangerous(dangerous_cat: str) -> None:
    assert is_blocking_category(dangerous_cat) is True


def test_is_blocking_category_false_for_advisory() -> None:
    assert is_blocking_category("correctness") is False
    assert is_blocking_category("other") is False


def test_is_blocking_category_false_for_unknown() -> None:
    assert is_blocking_category("nonexistent") is False
    assert is_blocking_category(None) is False


def test_is_blocking_action_true_for_normalized_blocking() -> None:
    assert is_blocking_action({"severity": SEVERITY_BLOCKING}) is True


def test_is_blocking_action_false_for_normalized_advisory() -> None:
    assert is_blocking_action({"severity": SEVERITY_ADVISORY}) is False


def test_is_blocking_action_false_when_severity_missing() -> None:
    assert is_blocking_action({}) is False


def test_blocking_north_star_actions_filters_correctly() -> None:
    actions = [
        {"id": "a1", "severity": SEVERITY_BLOCKING},
        {"id": "a2", "severity": SEVERITY_ADVISORY},
        {"id": "a3", "severity": SEVERITY_BLOCKING},
    ]
    result = blocking_north_star_actions(actions)
    assert len(result) == 2
    assert [a["id"] for a in result] == ["a1", "a3"]


def test_blocking_north_star_actions_empty_for_all_advisory() -> None:
    assert blocking_north_star_actions([{"severity": SEVERITY_ADVISORY}]) == []


def test_blocking_north_star_actions_empty_for_empty_list() -> None:
    assert blocking_north_star_actions([]) == []


def test_blocking_north_star_actions_returns_deep_copies() -> None:
    """blocking_north_star_actions returns dict copies, not references."""
    original = {"id": "a1", "severity": SEVERITY_BLOCKING, "concern": "X"}
    result = blocking_north_star_actions([original])
    result[0]["concern"] = "Y"
    assert original["concern"] == "X"
