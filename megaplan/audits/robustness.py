"""Critique check registry and helpers."""

from __future__ import annotations

from typing import Any, Final, TypedDict


VALID_SEVERITY_HINTS: Final[set[str]] = {"likely-significant", "likely-minor", "uncertain"}


class CritiqueCheckSpec(TypedDict):
    id: str
    question: str
    guidance: str
    category: str
    default_severity: str
    tier: str


CRITIQUE_CHECKS: Final[tuple[CritiqueCheckSpec, ...]] = (
    {
        "id": "issue_hints",
        "question": "Did the work fully address the issue hints, user notes, and approved plan requirements?",
        "guidance": (
            "Cross-check the result against explicit user notes, critique corrections, and watch items. "
            "Flag anything the implementation ignored, contradicted, or only partially covered."
        ),
        "category": "completeness",
        "default_severity": "likely-significant",
        "tier": "core",
    },
    {
        "id": "correctness",
        "question": "Are the proposed changes technically correct?",
        "guidance": (
            "Look for logic errors, invalid assumptions, broken invariants, schema mismatches, "
            "or behavior that would fail at runtime. When the fix adds a conditional branch, "
            "check whether it handles all relevant cases — not just the one reported in the issue."
        ),
        "category": "correctness",
        "default_severity": "likely-significant",
        "tier": "core",
    },
    {
        "id": "scope",
        "question": "Search for related code that handles the same concept. Is the reported issue a symptom of something broader?",
        "guidance": (
            "Look at how the changed function is used across the codebase. Does the fix only address "
            "one caller's scenario while others remain broken? Flag missing required work or out-of-scope "
            "edits. A minimal patch is often right, but check whether the underlying problem is bigger "
            "than what the issue describes."
        ),
        "category": "completeness",
        "default_severity": "likely-significant",
        "tier": "core",
    },
    {
        "id": "all_locations",
        "question": "Does the change touch all locations AND supporting infrastructure?",
        "guidance": (
            "Search for all instances of the symbol/pattern being changed. Also ask: does this "
            "feature require setup, registration, or integration code beyond the core logic? "
            "Missing glue code causes test failures even when the core fix is correct."
        ),
        "category": "completeness",
        "default_severity": "likely-significant",
        "tier": "core",
    },
    {
        "id": "callers",
        "question": "Find the callers of the changed function. What arguments do they actually pass? Does the fix handle all of them?",
        "guidance": (
            "Grep for call sites. For each caller, check what values it passes — especially edge cases "
            "like None, zero, empty, or composite inputs. Then ask: should this change be here, or in "
            "a caller, callee, or new method?"
        ),
        "category": "correctness",
        "default_severity": "likely-significant",
        "tier": "core",
    },
    {
        "id": "conventions",
        "question": "Does the approach match how the codebase solves similar problems?",
        "guidance": (
            "Check not just naming/style but how similar PROBLEMS are solved in this codebase. "
            "If the codebase adds new methods for similar cases, the plan should too. "
            "Do not spend findings on trivial stylistic preferences."
        ),
        "category": "maintainability",
        "default_severity": "likely-minor",
        "tier": "extended",
    },
    {
        "id": "verification",
        "question": "Is there convincing verification for the change?",
        "guidance": (
            "Flag missing tests or weak validation. If verification tests exist, trace the test's "
            "execution path through your patch — does every branch it exercises produce the expected "
            "result? A patch can look correct but fail because it misses one code path the test covers. "
            "If you manually verify an edge case because existing tests don't cover it, also test the cases next to it."
        ),
        "category": "completeness",
        "default_severity": "likely-minor",
        "tier": "extended",
    },
    {
        "id": "criteria_quality",
        "question": "Are the success criteria well-prioritized and verifiable?",
        "guidance": (
            "Check that each `must` criterion has a clear yes/no answer verifiable from code, tests, or "
            "git diff. Subjective goals, numeric guidelines, and aspirational targets should be `should`, "
            "not `must`. Criteria requiring manual testing or human judgment should be `info`. "
            "Flag any `must` criterion that is ambiguous, subjective, or unverifiable in the review pipeline."
        ),
        "category": "completeness",
        "default_severity": "likely-significant",
        "tier": "extended",
    },
)


def _joke_check(check_id: str, lens_quality: str, persona_guidance: str) -> CritiqueCheckSpec:
    return {
        "id": check_id,
        "question": (
            f"What is the most {lens_quality} move this scene could make while still "
            "serving the declared primary criterion?"
        ),
        "guidance": (
            f"{persona_guidance} Propose and commit to ONE FLAG with a concrete named "
            "proposal (specific beat, line, prop, reveal, turn, or button). Do not hedge, "
            "do not offer multiple alternatives, and do not write 'consider'."
        ),
        "category": "generative",
        "default_severity": "likely-minor",
        "tier": "core",
    }


JOKE_CRITIQUE_CHECKS: Final[tuple[CritiqueCheckSpec, ...]] = (
    _joke_check(
        "absurdist",
        "absurdist",
        "You are the absurdist lens: push the scene into boldly illogical but still playable behavior.",
    ),
    _joke_check(
        "twist_ending",
        "twist-ending",
        "You are the twist-ending lens: force a late reveal or reversal that recontextualizes the scene's final beat.",
    ),
    _joke_check(
        "hyper_specific_detail",
        "hyper-specific-detail",
        "You are the hyper-specific-detail lens: make the comedy land through oddly precise, concrete particulars.",
    ),
    _joke_check(
        "genre_swap",
        "genre-swap",
        "You are the genre-swap lens: make the scene suddenly obey the logic, tone, or stakes of a different genre.",
    ),
    _joke_check(
        "subtext_inversion",
        "subtext-inversion",
        "You are the subtext-inversion lens: flip what the scene is secretly about without changing the surface action.",
    ),
    _joke_check(
        "prop_as_character",
        "prop-as-character",
        "You are the prop-as-character lens: turn an object into an active comic presence with intention or status.",
    ),
    _joke_check(
        "bathos",
        "bathos",
        "You are the bathos lens: crash lofty emotion, stakes, or rhetoric into something humiliatingly mundane.",
    ),
    _joke_check(
        "scale_shift",
        "scale-shift",
        "You are the scale-shift lens: distort the scene by making the stakes or framing wildly too big or too small.",
    ),
    _joke_check(
        "narrator_reveal",
        "narrator_reveal",
        "You are the narrator-reveal lens: add a telling frame, hidden storyteller, or point-of-view reveal that snaps the scene into a stranger shape.",
    ),
)

_CHECK_BY_ID: Final[dict[str, CritiqueCheckSpec]] = {check["id"]: check for check in CRITIQUE_CHECKS}
_CORE_CRITIQUE_CHECKS: Final[tuple[CritiqueCheckSpec, ...]] = tuple(
    check for check in CRITIQUE_CHECKS if check["tier"] == "core"
)


def get_check_ids() -> list[str]:
    return [check["id"] for check in CRITIQUE_CHECKS]


def get_check_by_id(check_id: str) -> CritiqueCheckSpec | None:
    return _CHECK_BY_ID.get(check_id)


def build_check_category_map() -> dict[str, str]:
    return {check["id"]: check["category"] for check in CRITIQUE_CHECKS}


def checks_for_robustness(robustness: str) -> tuple[CritiqueCheckSpec, ...]:
    if robustness in {"robust", "superrobust"}:
        return CRITIQUE_CHECKS
    if robustness in {"light", "tiny"}:
        return ()
    return _CORE_CRITIQUE_CHECKS


def creative_checks_for_robustness(form: Any, robustness: str) -> tuple[CritiqueCheckSpec, ...]:
    if robustness == "tiny":
        return ()
    from megaplan.forms import Form
    from megaplan.forms.provocations import select_active_checks

    form_id = form.id if isinstance(form, Form) else str(form)
    state = {"config": {"mode": "creative", "form": form_id}, "iteration": 1}
    return tuple(select_active_checks(state, robustness))


def joke_checks_for_robustness(robustness: str) -> tuple[CritiqueCheckSpec, ...]:
    from megaplan.forms import get_form

    return creative_checks_for_robustness(get_form("joke"), robustness)


def build_empty_template(checks: tuple[CritiqueCheckSpec, ...] | None = None) -> list[dict[str, Any]]:
    active_checks = CRITIQUE_CHECKS if checks is None else checks
    return [
        {
            "id": check["id"],
            "question": check["question"],
            "findings": [],
        }
        for check in active_checks
    ]


_MIN_FINDING_DETAIL_LENGTH = 40  # Must describe what was checked, not just "No issue"


def _valid_findings(findings: Any) -> bool:
    if not isinstance(findings, list) or not findings:
        return False
    for finding in findings:
        if not isinstance(finding, dict):
            return False
        detail = finding.get("detail")
        flagged = finding.get("flagged")
        if not isinstance(detail, str) or not detail.strip():
            return False
        if len(detail.strip()) < _MIN_FINDING_DETAIL_LENGTH:
            return False
        if not isinstance(flagged, bool):
            return False
    return True


def validate_critique_checks(
    payload: Any,
    *,
    expected_ids: tuple[str, ...] | list[str] | None = None,
) -> list[str]:
    raw_checks = payload.get("checks") if isinstance(payload, dict) else payload
    expected = get_check_ids() if expected_ids is None else list(expected_ids)
    if not isinstance(raw_checks, list):
        return expected

    expected_set = set(expected)
    valid_ids: set[str] = set()
    invalid_expected_ids: set[str] = set()
    invalid_unknown_ids: set[str] = set()
    seen_counts: dict[str, int] = {}

    for raw_check in raw_checks:
        if not isinstance(raw_check, dict):
            continue
        check_id = raw_check.get("id")
        if not isinstance(check_id, str) or not check_id:
            continue

        seen_counts[check_id] = seen_counts.get(check_id, 0) + 1
        if check_id not in expected_set:
            invalid_unknown_ids.add(check_id)
            continue
        if seen_counts[check_id] > 1:
            invalid_expected_ids.add(check_id)
            continue

        question = raw_check.get("question")
        findings = raw_check.get("findings")
        if not isinstance(question, str) or not question.strip():
            invalid_expected_ids.add(check_id)
            continue
        if not _valid_findings(findings):
            invalid_expected_ids.add(check_id)
            continue
        valid_ids.add(check_id)

    return [
        check_id
        for check_id in expected
        if check_id not in valid_ids or check_id in invalid_expected_ids
    ] + sorted(invalid_unknown_ids)


__all__ = [
    "CRITIQUE_CHECKS",
    "JOKE_CRITIQUE_CHECKS",
    "VALID_SEVERITY_HINTS",
    "build_check_category_map",
    "build_empty_template",
    "checks_for_robustness",
    "get_check_by_id",
    "get_check_ids",
    "joke_checks_for_robustness",
    "validate_critique_checks",
]
