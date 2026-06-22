"""Tests for hard-floor test blast-radius merging."""

from __future__ import annotations

from copy import deepcopy

from arnold_pipelines.megaplan.orchestration.test_selection import merge_blast_radius_floor


def _radius(
    *,
    strategy: str = "scoped",
    confidence: str = "high",
    selectors: list[dict[str, str]] | None = None,
    changed_surfaces: list[str] | None = None,
    always_run: list[str] | None = None,
    rationale: str = "radius",
    full_suite_fallback: bool = True,
) -> dict:
    return {
        "strategy": strategy,
        "confidence": confidence,
        "selectors": selectors or [],
        "changed_surfaces": changed_surfaces or [],
        "always_run": always_run or [],
        "full_suite_fallback": full_suite_fallback,
        "rationale": rationale,
    }


def _selector(value: str, *, reason: str = "reason") -> dict[str, str]:
    return {"kind": "path", "value": value, "reason": reason}


def _selector_values(radius: dict) -> list[str]:
    return [selector["value"] for selector in radius["selectors"]]


def test_model_narrower_than_floor_preserves_floor_selectors_and_strategy() -> None:
    floor = _radius(
        selectors=[_selector("tests/test_floor.py")],
        changed_surfaces=["pkg/floor.py"],
        rationale="deterministic floor",
    )
    floor["import_graph"] = {
        "degraded": False,
        "dependent_tests": 1,
        "unresolved": [],
    }
    candidate = _radius(strategy="none", selectors=[], rationale="model narrowed")

    merged = merge_blast_radius_floor(floor, candidate)

    assert merged is not None
    assert merged["strategy"] == "scoped"
    assert _selector_values(merged) == ["tests/test_floor.py"]
    assert merged["import_graph"] == floor["import_graph"]
    assert "Floor widened the candidate" in merged["rationale"]


def test_model_wider_than_floor_adds_selectors_and_escalates_to_full() -> None:
    floor = _radius(selectors=[_selector("tests/test_floor.py")])
    candidate = _radius(
        strategy="full",
        selectors=[
            _selector("tests/test_floor.py", reason="duplicate"),
            _selector("tests/test_candidate.py"),
        ],
    )

    merged = merge_blast_radius_floor(floor, candidate)

    assert merged is not None
    assert merged["strategy"] == "full"
    assert _selector_values(merged) == [
        "tests/test_floor.py",
        "tests/test_candidate.py",
    ]


def test_full_floor_cannot_be_narrowed_to_scoped() -> None:
    floor = _radius(strategy="full", selectors=[_selector("tests/test_floor.py")])
    candidate = _radius(
        strategy="scoped",
        selectors=[_selector("tests/test_candidate.py")],
    )

    merged = merge_blast_radius_floor(floor, candidate)

    assert merged is not None
    assert merged["strategy"] == "full"


def test_none_handling_returns_the_present_side() -> None:
    floor = _radius(selectors=[_selector("tests/test_floor.py")])
    candidate = _radius(selectors=[_selector("tests/test_candidate.py")])

    assert merge_blast_radius_floor(None, candidate) == candidate
    assert merge_blast_radius_floor(floor, None) == floor
    assert merge_blast_radius_floor(None, None) is None


def test_confidence_uses_more_conservative_value() -> None:
    assert (
        merge_blast_radius_floor(
            _radius(confidence="high"),
            _radius(confidence="low"),
        )["confidence"]
        == "low"
    )
    assert (
        merge_blast_radius_floor(
            _radius(confidence="low"),
            _radius(confidence="high"),
        )["confidence"]
        == "low"
    )


def test_always_run_and_changed_surfaces_are_stable_unions() -> None:
    floor = _radius(
        changed_surfaces=["pkg/floor.py", "pkg/shared.py"],
        always_run=["tests/test_core.py"],
    )
    candidate = _radius(
        changed_surfaces=["pkg/shared.py", "pkg/candidate.py"],
        always_run=["tests/test_core.py", "tests/test_candidate_core.py"],
    )

    merged = merge_blast_radius_floor(floor, candidate)

    assert merged is not None
    assert merged["changed_surfaces"] == [
        "pkg/floor.py",
        "pkg/shared.py",
        "pkg/candidate.py",
    ]
    assert merged["always_run"] == [
        "tests/test_core.py",
        "tests/test_candidate_core.py",
    ]


def test_merge_is_deterministic_with_stable_selector_order() -> None:
    floor = _radius(
        selectors=[
            _selector("tests/test_a.py"),
            _selector("tests/test_b.py"),
        ],
    )
    candidate = _radius(
        selectors=[
            _selector("tests/test_b.py", reason="duplicate"),
            _selector("tests/test_c.py"),
        ],
    )

    first = merge_blast_radius_floor(deepcopy(floor), deepcopy(candidate))
    second = merge_blast_radius_floor(deepcopy(floor), deepcopy(candidate))

    assert first == second
    assert first is not None
    assert _selector_values(first) == [
        "tests/test_a.py",
        "tests/test_b.py",
        "tests/test_c.py",
    ]


def test_merge_is_idempotent_when_candidate_is_already_merged() -> None:
    floor = _radius(
        selectors=[_selector("tests/test_floor.py")],
        changed_surfaces=["pkg/floor.py"],
        rationale="deterministic floor",
    )
    candidate = _radius(
        selectors=[_selector("tests/test_candidate.py")],
        changed_surfaces=["pkg/candidate.py"],
        rationale="model widening",
    )

    once = merge_blast_radius_floor(deepcopy(floor), deepcopy(candidate))
    twice = merge_blast_radius_floor(deepcopy(floor), deepcopy(once))

    assert twice == once
