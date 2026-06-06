from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

import arnold.pipelines.megaplan as megaplan
from arnold.pipelines.megaplan._core import json_dump, load_plan, read_json, save_flag_registry, save_state
from arnold.pipelines.megaplan.workers import WorkerResult, _build_mock_payload

from tests.conftest import make_args_factory


@dataclass
class PlanFixture:
    root: Path
    project_dir: Path
    plan_name: str
    plan_dir: Path
    make_args: Callable[..., Namespace]
    robustness: str


def _make_plan_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    robustness: str,
) -> PlanFixture:
    """Create a plan fixture (bootstrap is handled by ``bootstrap_fixture``)."""
    root = tmp_path / f"root-{robustness}"
    project_dir = tmp_path / f"project-{robustness}"
    config_path = tmp_path / f"config-{robustness}"
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()

    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )

    # Isolate user config so a global ``adaptive_critique = true`` in
    # ~/.config/megaplan/config.json doesn't leak into the test and drive
    # the critique handler down the adaptive-evaluator path that the mock
    # worker doesn't implement. See docs/critique.md.
    import arnold.pipelines.megaplan._core.io as _io_module

    def _config_dir(home: Path | None = None) -> Path:
        del home
        return config_path

    monkeypatch.setattr(_io_module, "config_dir", _config_dir)
    monkeypatch.setattr(megaplan.cli, "config_dir", _config_dir)

    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(root, make_args(name=f"{robustness}-plan", robustness=robustness))
    plan_name = response["plan"]
    return PlanFixture(
        root=root,
        project_dir=project_dir,
        plan_name=plan_name,
        plan_dir=megaplan.plans_root(root) / plan_name,
        make_args=make_args,
        robustness=robustness,
    )


def _advance_to_executed(fixture: PlanFixture) -> None:
    args = fixture.make_args(plan=fixture.plan_name)
    megaplan.handlers.handle_prep(fixture.root, args)
    megaplan.handle_plan(fixture.root, args)
    megaplan.handle_critique(fixture.root, args)
    megaplan.handle_override(
        fixture.root,
        fixture.make_args(plan=fixture.plan_name, override_action="force-proceed", reason="test"),
    )
    megaplan.handle_finalize(fixture.root, args)
    megaplan.handle_execute(
        fixture.root,
        fixture.make_args(plan=fixture.plan_name, confirm_destructive=True, user_approved=True),
    )


def _load_executed_plan(fixture: PlanFixture) -> tuple[Path, dict[str, object]]:
    plan_dir, state = load_plan(fixture.root, fixture.plan_name)
    state["current_state"] = megaplan.STATE_EXECUTED
    save_state(plan_dir, state)
    return plan_dir, state


def _adjacent_calls_review_checks(*, include_status: bool = True, status: str = "blocking") -> list[dict[str, object]]:
    adjacent_calls = megaplan.review.checks.get_check_by_id("adjacent_calls")
    assert adjacent_calls is not None
    finding: dict[str, object] = {
        "detail": (
            "Adjacent caller coverage still misses a sibling entry point, so the original bug remains reproducible "
            "through an alternate path."
        ),
        "flagged": True,
        "evidence_file": "pkg/module.py",
    }
    if include_status:
        finding["status"] = status
    return [
        {
            "id": adjacent_calls.id,
            "question": adjacent_calls.question,
            "findings": [finding],
        }
    ]


def _normalized_pre_check_flags(flags: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "id": item["id"],
            "check": item["check"],
            "detail": item["detail"],
            "severity": item["severity"],
            "evidence_file": item.get("evidence_file", ""),
        }
        for item in flags
    ]


def test_handle_review_standard_branch_attaches_prechecks_and_updates_flags(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="standard")
    _advance_to_executed(fixture)
    _plan_dir, state = _load_executed_plan(fixture)
    payload = _build_mock_payload("review", state, fixture.plan_dir, summary="Golden review payload.")
    pre_check_flags = [
        {
            "id": "PRECHECK-STANDARD-001",
            "check": "source_touch",
            "detail": "The diff touches a source file.",
            "severity": "minor",
        }
    ]
    call_order: list[str] = []
    update_calls: list[dict[str, object]] = []

    worker = WorkerResult(
        payload=payload,
        raw_output="review",
        duration_ms=1,
        cost_usd=0.0,
        session_id="review-standard",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )

    def _fail_parallel(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("standard review should not invoke parallel review helpers")

    monkeypatch.setattr(megaplan.handlers, "run_parallel_review", _fail_parallel)

    def _run_pre_checks(*args: object, **kwargs: object) -> list[dict[str, str]]:
        del args, kwargs
        call_order.append("run_pre_checks")
        return pre_check_flags

    def _update_flags_after_review(plan_dir: Path, review_payload: dict[str, object], *, iteration: int) -> dict[str, object]:
        update_calls.append(
            {
                "plan_dir": plan_dir,
                "payload": review_payload,
                "iteration": iteration,
            }
        )
        call_order.append("update_flags_after_review")
        return {"flags": []}

    monkeypatch.setattr(megaplan.handlers, "run_pre_checks", _run_pre_checks)
    monkeypatch.setattr(megaplan.handlers, "update_flags_after_review", _update_flags_after_review)
    monkeypatch.setattr(
        megaplan.handlers.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (call_order.append("run_step_with_worker") or (worker, "codex", "persistent", False)),
    )

    megaplan.handle_review(fixture.root, fixture.make_args(plan=fixture.plan_name))
    stored_review = read_json(fixture.plan_dir / "review.json")

    assert stored_review["pre_check_flags"] == _normalized_pre_check_flags(pre_check_flags)
    assert "flags" not in stored_review
    assert len(update_calls) == 1
    assert update_calls[0]["payload"] is worker.payload
    assert update_calls[0]["iteration"] == state["iteration"]
    assert call_order == ["run_pre_checks", "run_step_with_worker", "update_flags_after_review"]


def test_handle_review_light_branch_skips_prechecks_and_keeps_review_payload_unadorned(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="light")
    _advance_to_executed(fixture)
    _plan_dir, state = _load_executed_plan(fixture)
    payload = _build_mock_payload("review", state, fixture.plan_dir, summary="Golden light review payload.")
    golden_path = tmp_path / "golden_light_review.json"
    golden_path.write_text(json_dump(payload), encoding="utf-8")
    update_call_count = 0

    worker = WorkerResult(
        payload=payload,
        raw_output="review",
        duration_ms=1,
        cost_usd=0.0,
        session_id="review-light",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )

    monkeypatch.setattr(
        megaplan.handlers,
        "run_pre_checks",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("light review should not invoke pre-checks")),
    )

    def _update_flags_after_review(*args: object, **kwargs: object) -> None:
        nonlocal update_call_count
        del args, kwargs
        update_call_count += 1

    monkeypatch.setattr(megaplan.handlers, "update_flags_after_review", _update_flags_after_review)
    monkeypatch.setattr(
        megaplan.handlers.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    megaplan.handle_review(fixture.root, fixture.make_args(plan=fixture.plan_name))
    stored_review = read_json(fixture.plan_dir / "review.json")

    assert stored_review.get("pre_check_flags") == []
    assert update_call_count == 0
    golden = read_json(golden_path)
    assert stored_review["review_verdict"] == golden["review_verdict"]
    assert stored_review["checks"] == golden["checks"]
    assert stored_review["pre_check_flags"] == golden["pre_check_flags"]


def test_handle_review_standard_branch_rejects_schema_invalid_model_payload_before_flag_updates(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="standard")
    _advance_to_executed(fixture)
    _plan_dir, state = _load_executed_plan(fixture)
    payload = _build_mock_payload("review", state, fixture.plan_dir, summary="Golden review payload.")
    payload.pop("task_verdicts")
    worker = WorkerResult(
        payload=payload,
        raw_output="review",
        duration_ms=1,
        cost_usd=0.0,
        session_id="review-standard-invalid",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )

    update_call_count = 0

    monkeypatch.setattr(megaplan.handlers, "run_pre_checks", lambda *args, **kwargs: [])

    def _update_flags_after_review(*args: object, **kwargs: object) -> None:
        nonlocal update_call_count
        del args, kwargs
        update_call_count += 1

    monkeypatch.setattr(megaplan.handlers, "update_flags_after_review", _update_flags_after_review)
    monkeypatch.setattr(
        megaplan.handlers.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    with pytest.raises(megaplan.CliError, match="Review output failed schema audit"):
        megaplan.handle_review(fixture.root, fixture.make_args(plan=fixture.plan_name))

    assert update_call_count == 0
    assert not (fixture.plan_dir / "review.json").exists()


def test_resolve_review_outcome_uses_standard_and_robust_caps_separately(tmp_path: Path) -> None:
    state = {
        "history": [
            {"step": "review", "result": "needs_rework"},
            {"step": "review", "result": "needs_rework"},
        ]
    }

    standard_issues: list[str] = []
    robust_issues: list[str] = []

    standard_result = megaplan.handlers._resolve_review_outcome(
        tmp_path,
        "needs_rework",
        2,
        2,
        2,
        2,
        [],
        "standard",
        state,
        standard_issues,
    )
    robust_result = megaplan.handlers._resolve_review_outcome(
        tmp_path,
        "needs_rework",
        2,
        2,
        2,
        2,
        [],
        "robust",
        state,
        robust_issues,
    )

    assert standard_result == ("needs_rework", megaplan.STATE_FINALIZED, "execute")
    assert robust_result == ("force_proceeded", megaplan.STATE_DONE, None)
    assert any("Max review rework cycles (2) reached" in issue for issue in robust_issues)


def _cap_reached_state() -> dict[str, object]:
    return {
        "history": [
            {"step": "review", "result": "needs_rework"},
            {"step": "review", "result": "needs_rework"},
            {"step": "review", "result": "needs_rework"},
        ]
    }


def test_force_proceed_with_unresolved_must_escalates_to_recoverable_blocked(
    tmp_path: Path,
) -> None:
    issues: list[str] = []
    result, next_state, next_step = megaplan.handlers._resolve_review_outcome(
        tmp_path,
        "needs_rework",
        1, 1, 1, 1,
        [],
        "full",
        _cap_reached_state(),
        issues,
        criteria=[{"id": "C1", "priority": "must", "pass": False}],
        rework_items=[{"task_id": "REVIEW", "issue": "manifest rewritten out of scope"}],
    )

    assert (result, next_state, next_step) == ("blocked", megaplan.STATE_BLOCKED, "review")
    assert any("escalating to recoverable blocked" in issue for issue in issues)
    assert not any("Force-proceeding to done" in issue for issue in issues)


def test_force_proceed_with_only_cosmetic_items_still_ships_done(
    tmp_path: Path,
) -> None:
    issues: list[str] = []
    result, next_state, next_step = megaplan.handlers._resolve_review_outcome(
        tmp_path,
        "needs_rework",
        1, 1, 1, 1,
        [],
        "full",
        _cap_reached_state(),
        issues,
        criteria=[{"id": "C1", "priority": "should", "pass": False}],
        rework_items=[{"task_id": "T1", "issue": "nit: wording", "severity": "minor"}],
    )

    assert (result, next_state, next_step) == ("force_proceeded", megaplan.STATE_DONE, None)
    assert any("non-blocking/cosmetic" in issue for issue in issues)
    assert not any("recoverable blocked" in issue for issue in issues)


def test_handle_review_superrobust_path_merges_parallel_review_and_creates_review_rework(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="superrobust")
    _advance_to_executed(fixture)
    _plan_dir, state = load_plan(fixture.root, fixture.plan_name)
    coverage = megaplan.review.checks.get_check_by_id("coverage")
    assert coverage is not None

    pre_check_flags = [
        {
            "id": "PRECHECK-SOURCE_TOUCH",
            "check": "source_touch",
            "detail": "The diff touches a non-test source file.",
            "severity": "minor",
        }
    ]
    criteria_payload = _build_mock_payload("review", state, fixture.plan_dir, review_verdict="approved")
    parallel_result = WorkerResult(
        payload={
            "criteria_payload": criteria_payload,
            "checks": [
                {
                    "id": coverage.id,
                    "question": coverage.question,
                    "findings": [
                            {
                                "detail": "Coverage review found an issue example from the original bug report that the diff still does not address.",
                                "flagged": True,
                                "status": "blocking",
                                "evidence_file": "pkg/module.py",
                                "deterministic_check": {
                                    "command": "pytest tests/test_issue_example.py",
                                    "baseline_status": "failed",
                                    "post_status": "failed",
                                    "evidence_file": "pkg/module.py",
                                },
                            }
                        ],
                    }
            ],
            "verified_flag_ids": ["REVIEW-OLD-001"],
            "disputed_flag_ids": ["REVIEW-OLD-002"],
        },
        raw_output="parallel",
        duration_ms=12,
        cost_usd=0.75,
        session_id=None,
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
    )

    monkeypatch.delenv(megaplan.MOCK_ENV_VAR, raising=False)
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda *args, **kwargs: ("hermes", "persistent", True, "mock-model"),
    )
    monkeypatch.setattr(megaplan.handlers, "run_pre_checks", lambda *args, **kwargs: pre_check_flags)
    monkeypatch.setattr(megaplan.handlers, "run_parallel_review", lambda *args, **kwargs: parallel_result)
    monkeypatch.setattr(
        megaplan.handlers.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("superrobust Hermes review should not use the legacy worker")),
    )

    response = megaplan.handle_review(fixture.root, fixture.make_args(plan=fixture.plan_name))
    stored_review = read_json(fixture.plan_dir / "review.json")
    faults = read_json(fixture.plan_dir / "faults.json")

    assert response["success"] is False
    assert response["state"] == megaplan.STATE_FINALIZED
    assert response["next_step"] == "execute"
    assert stored_review["review_verdict"] == "needs_rework"
    assert stored_review["checks"][0]["id"] == "coverage"
    assert stored_review["pre_check_flags"] == _normalized_pre_check_flags(pre_check_flags)
    assert stored_review["verified_flag_ids"] == ["REVIEW-OLD-001"]
    assert stored_review["disputed_flag_ids"] == ["REVIEW-OLD-002"]
    assert any(item["task_id"] == "REVIEW-coverage" and item["source"] == "review_coverage" for item in stored_review["rework_items"])
    assert any(flag["id"] == "REVIEW-COVERAGE-001" for flag in faults["flags"])


def test_handle_review_superrobust_parallel_branch_rejects_schema_invalid_before_write_and_flags(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="superrobust")
    _advance_to_executed(fixture)
    _plan_dir, state = load_plan(fixture.root, fixture.plan_name)
    criteria_payload = _build_mock_payload("review", state, fixture.plan_dir, review_verdict="approved")
    criteria_payload.pop("sense_check_verdicts")

    parallel_result = WorkerResult(
        payload={
            "criteria_payload": criteria_payload,
            "checks": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        },
        raw_output="parallel-invalid",
        duration_ms=9,
        cost_usd=0.15,
        session_id=None,
        prompt_tokens=4,
        completion_tokens=5,
        total_tokens=9,
    )

    update_call_count = 0

    monkeypatch.delenv(megaplan.MOCK_ENV_VAR, raising=False)
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda *args, **kwargs: ("hermes", "persistent", True, "mock-model"),
    )
    monkeypatch.setattr(megaplan.handlers, "run_pre_checks", lambda *args, **kwargs: [])
    monkeypatch.setattr(megaplan.handlers, "run_parallel_review", lambda *args, **kwargs: parallel_result)

    def _update_flags_after_review(*args: object, **kwargs: object) -> None:
        nonlocal update_call_count
        del args, kwargs
        update_call_count += 1

    monkeypatch.setattr(megaplan.handlers, "update_flags_after_review", _update_flags_after_review)
    monkeypatch.setattr(
        megaplan.handlers.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("superrobust Hermes review should not use the legacy worker")
        ),
    )

    with pytest.raises(megaplan.CliError, match="Review output failed schema audit"):
        megaplan.handle_review(fixture.root, fixture.make_args(plan=fixture.plan_name))

    assert update_call_count == 0
    assert not (fixture.plan_dir / "review.json").exists()


def test_handle_review_superrobust_parallel_branch_audits_merged_payload_before_write_and_flags(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="superrobust")
    _advance_to_executed(fixture)
    _plan_dir, state = load_plan(fixture.root, fixture.plan_name)

    pre_check_flags = [
        {
            "id": "PRECHECK-SOURCE_TOUCH",
            "check": "source_touch",
            "detail": "The diff touches a non-test source file.",
            "severity": "minor",
        }
    ]
    criteria_payload = _build_mock_payload("review", state, fixture.plan_dir, review_verdict="approved")
    parallel_result = WorkerResult(
        payload={
            "criteria_payload": criteria_payload,
            "checks": [],
            "verified_flag_ids": ["REVIEW-OLD-001"],
            "disputed_flag_ids": ["REVIEW-OLD-002"],
        },
        raw_output="parallel-valid",
        duration_ms=11,
        cost_usd=0.2,
        session_id=None,
        prompt_tokens=6,
        completion_tokens=7,
        total_tokens=13,
    )

    call_order: list[str] = []
    update_payloads: list[dict[str, object]] = []

    monkeypatch.delenv(megaplan.MOCK_ENV_VAR, raising=False)
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda *args, **kwargs: ("hermes", "persistent", True, "mock-model"),
    )
    monkeypatch.setattr(megaplan.handlers, "run_pre_checks", lambda *args, **kwargs: pre_check_flags)
    monkeypatch.setattr(
        megaplan.handlers,
        "run_parallel_review",
        lambda *args, **kwargs: (call_order.append("run_parallel_review") or parallel_result),
    )

    def _update_flags_after_review(
        plan_dir: Path, review_payload: dict[str, object], *, iteration: int
    ) -> dict[str, object]:
        update_payloads.append(review_payload)
        call_order.append("update_flags_after_review")
        assert plan_dir == fixture.plan_dir
        assert iteration == state["iteration"]
        stored_review = read_json(plan_dir / "review.json")
        assert stored_review == review_payload
        return {"flags": []}

    monkeypatch.setattr(megaplan.handlers, "update_flags_after_review", _update_flags_after_review)
    monkeypatch.setattr(
        megaplan.handlers.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("superrobust Hermes review should not use the legacy worker")
        ),
    )

    response = megaplan.handle_review(fixture.root, fixture.make_args(plan=fixture.plan_name))
    stored_review = read_json(fixture.plan_dir / "review.json")

    assert response["success"] is True
    assert stored_review["review_verdict"] == criteria_payload["review_verdict"]
    assert stored_review["task_verdicts"] == criteria_payload["task_verdicts"]
    assert stored_review["sense_check_verdicts"] == criteria_payload["sense_check_verdicts"]
    assert stored_review["pre_check_flags"] == _normalized_pre_check_flags(pre_check_flags)
    assert stored_review["verified_flag_ids"] == ["REVIEW-OLD-001"]
    assert stored_review["disputed_flag_ids"] == ["REVIEW-OLD-002"]
    assert len(update_payloads) == 1
    assert update_payloads[0] == stored_review
    assert call_order == ["run_parallel_review", "update_flags_after_review"]


def test_rework_item_synthesized_for_flagged_finding_with_empty_status() -> None:
    rework_items = megaplan.handlers._synthesize_review_rework_items(
        _adjacent_calls_review_checks(status="")
    )

    assert any(item["source"] == "review_adjacent_calls" for item in rework_items)


def test_rework_item_synthesized_for_flagged_finding_with_missing_status_key() -> None:
    rework_items = megaplan.handlers._synthesize_review_rework_items(
        _adjacent_calls_review_checks(include_status=False)
    )

    assert any(item["source"] == "review_adjacent_calls" for item in rework_items)


def test_rework_item_not_synthesized_for_significant_status() -> None:
    rework_items = megaplan.handlers._synthesize_review_rework_items(
        _adjacent_calls_review_checks(status="significant")
    )

    assert rework_items == []


def test_rework_item_not_synthesized_for_minor_status() -> None:
    rework_items = megaplan.handlers._synthesize_review_rework_items(
        _adjacent_calls_review_checks(status="minor")
    )

    assert rework_items == []


def test_rework_item_actual_does_not_duplicate_issue() -> None:
    """The rework item's `actual` field must not be a copy of `issue`.

    Historically both fields were populated from the finding's `detail`,
    which duplicated the sentence in the executor's rework prompt. The
    polish pass replaces `actual` with a templated acknowledgment.
    """
    rework_items = megaplan.handlers._synthesize_review_rework_items(
        _adjacent_calls_review_checks(status="blocking")
    )
    assert rework_items, "Expected at least one rework item for a blocking finding"
    for item in rework_items:
        assert item["issue"] != item["actual"], (
            f"issue and actual must differ, got both={item['issue']!r}"
        )
        assert "did not resolve" in item["actual"]


def test_rework_item_expected_is_actionable_per_check() -> None:
    """`expected` should be a per-check actionable directive, not the check's self-question.

    Exercises each of the 4 review checks by synthesizing a flagged finding
    via the helper and asserting `expected` carries the per-check template
    from `_EXPECTED_BY_CHECK_ID`.
    """
    per_check_markers = {
        "coverage": "every concrete failing example",
        "placement": "upstream",
        "adjacent_calls": "additional call site",
        "simplicity": "unjustified",
    }
    for check_id, marker in per_check_markers.items():
        checks = [
            {
                "id": check_id,
                "question": "Generic placeholder question for the test.",
                "findings": [
                    {
                        "flagged": True,
                        "status": "blocking",
                        "detail": f"A real concern from {check_id} that must be surfaced to the executor.",
                    }
                ],
            }
        ]
        rework_items = megaplan.handlers._synthesize_review_rework_items(checks)
        assert rework_items, f"Expected rework item for check {check_id}"
        expected = rework_items[0]["expected"]
        assert marker in expected, (
            f"Expected per-check marker {marker!r} for {check_id}, got {expected!r}"
        )
        assert "Generic placeholder question" not in expected, (
            f"Expected should not fall back to the check question when a template exists, got {expected!r}"
        )


def test_rework_item_task_id_is_scoped_by_check_id() -> None:
    """`task_id` should be `REVIEW-<check_id>`, not the bare `REVIEW` sentinel."""
    rework_items = megaplan.handlers._synthesize_review_rework_items(
        _adjacent_calls_review_checks(status="blocking")
    )
    assert rework_items
    for item in rework_items:
        assert item["task_id"] == "REVIEW-adjacent_calls", (
            f"Expected REVIEW-adjacent_calls, got {item['task_id']!r}"
        )
        # Lock down the regression — the plain sentinel must not return.
        assert item["task_id"] != "REVIEW"


def test_handle_review_superrobust_iteration_two_marks_verified_review_flags(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="superrobust")
    _advance_to_executed(fixture)
    _plan_dir, state = load_plan(fixture.root, fixture.plan_name)
    state["iteration"] = 2
    state["current_state"] = megaplan.STATE_EXECUTED
    save_state(fixture.plan_dir, state)
    save_flag_registry(
        fixture.plan_dir,
        {
            "flags": [
                {
                    "id": "REVIEW-COVERAGE-001",
                    "concern": "Coverage gap is still open",
                    "category": "completeness",
                    "severity_hint": "likely-significant",
                    "evidence": "prior issue",
                    "status": "open",
                    "severity": "significant",
                    "verified": False,
                    "raised_in": "review_v1.json",
                }
            ]
        },
    )
    coverage = megaplan.review.checks.get_check_by_id("coverage")
    assert coverage is not None
    criteria_payload = _build_mock_payload("review", state, fixture.plan_dir, review_verdict="approved")
    parallel_result = WorkerResult(
        payload={
            "criteria_payload": criteria_payload,
            "checks": [
                {
                    "id": coverage.id,
                    "question": coverage.question,
                    "findings": [
                        {
                            "detail": "Confirmed the previous coverage concern is now resolved for the original issue example.",
                            "flagged": False,
                            "status": "n/a",
                        }
                    ],
                }
            ],
            "verified_flag_ids": ["REVIEW-COVERAGE-001"],
            "disputed_flag_ids": [],
        },
        raw_output="parallel",
        duration_ms=8,
        cost_usd=0.2,
        session_id=None,
        prompt_tokens=5,
        completion_tokens=6,
        total_tokens=11,
    )

    monkeypatch.delenv(megaplan.MOCK_ENV_VAR, raising=False)
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda *args, **kwargs: ("hermes", "persistent", True, "mock-model"),
    )
    monkeypatch.setattr(megaplan.handlers, "run_pre_checks", lambda *args, **kwargs: [])
    monkeypatch.setattr(megaplan.handlers, "run_parallel_review", lambda *args, **kwargs: parallel_result)
    monkeypatch.setattr(
        megaplan.handlers.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("superrobust Hermes review should not use the legacy worker")),
    )

    response = megaplan.handle_review(fixture.root, fixture.make_args(plan=fixture.plan_name))
    faults = read_json(fixture.plan_dir / "faults.json")
    coverage_flag = next(flag for flag in faults["flags"] if flag["id"] == "REVIEW-COVERAGE-001")

    assert response["success"] is True
    assert response["state"] == megaplan.STATE_DONE
    assert coverage_flag["status"] == "verified"
    assert coverage_flag["verified_in"] == "review_v2.json"


def test_handle_review_non_hermes_branch_rejects_schema_invalid_payload_before_finalize(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="superrobust")
    _advance_to_executed(fixture)
    _plan_dir, state = _load_executed_plan(fixture)
    payload = _build_mock_payload("review", state, fixture.plan_dir, summary="Golden review payload.")
    payload.pop("sense_check_verdicts")
    worker = WorkerResult(
        payload=payload,
        raw_output="review",
        duration_ms=1,
        cost_usd=0.0,
        session_id="review-non-hermes-invalid",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )

    monkeypatch.delenv(megaplan.MOCK_ENV_VAR, raising=False)
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda *args, **kwargs: ("codex", "persistent", False, "mock-model"),
    )
    monkeypatch.setattr(
        megaplan.handlers.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    with pytest.raises(megaplan.CliError, match="Review output failed schema audit"):
        megaplan.handle_review(fixture.root, fixture.make_args(plan=fixture.plan_name))

    state_after = read_json(fixture.plan_dir / "state.json")
    assert state_after["current_state"] == megaplan.STATE_EXECUTED


# ── T17: Thorough (robust → thorough) and non-Hermes valid path tests ──────

def test_handle_review_thorough_branch_rejects_schema_invalid_before_write_and_flags(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove that for thorough (robust→thorough) review, schema audit rejects
    invalid model output before write_plan_artifact_json and flag updates."""
    fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="robust")
    _advance_to_executed(fixture)
    _plan_dir, state = _load_executed_plan(fixture)
    payload = _build_mock_payload("review", state, fixture.plan_dir, summary="Golden review payload.")
    payload.pop("task_verdicts")
    worker = WorkerResult(
        payload=payload,
        raw_output="review",
        duration_ms=1,
        cost_usd=0.0,
        session_id="review-robust-invalid",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )

    update_call_count = 0

    monkeypatch.setattr(megaplan.handlers, "run_pre_checks", lambda *args, **kwargs: [])

    def _update_flags_after_review(*args: object, **kwargs: object) -> None:
        nonlocal update_call_count
        del args, kwargs
        update_call_count += 1

    monkeypatch.setattr(megaplan.handlers, "update_flags_after_review", _update_flags_after_review)
    monkeypatch.setattr(
        megaplan.handlers.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    with pytest.raises(megaplan.CliError, match="Review output failed schema audit"):
        megaplan.handle_review(fixture.root, fixture.make_args(plan=fixture.plan_name))

    assert update_call_count == 0
    assert not (fixture.plan_dir / "review.json").exists()


def test_handle_review_thorough_branch_valid_payload_audited_then_written_and_flags_updated(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove that for thorough (robust→thorough) review with a valid payload,
    schema audit passes, then write_plan_artifact_json and flag updates proceed."""
    fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="robust")
    _advance_to_executed(fixture)
    _plan_dir, state = _load_executed_plan(fixture)
    payload = _build_mock_payload("review", state, fixture.plan_dir, summary="Golden thorough payload.")
    pre_check_flags = [
        {
            "id": "PRECHECK-ROBUST-001",
            "check": "source_touch",
            "detail": "The diff touches a source file.",
            "severity": "minor",
        }
    ]
    call_order: list[str] = []
    update_calls: list[dict[str, object]] = []

    worker = WorkerResult(
        payload=payload,
        raw_output="review",
        duration_ms=1,
        cost_usd=0.0,
        session_id="review-robust-valid",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )

    monkeypatch.setattr(megaplan.handlers, "run_pre_checks", lambda *args, **kwargs: pre_check_flags)

    def _update_flags_after_review(
        plan_dir: Path, review_payload: dict[str, object], *, iteration: int
    ) -> dict[str, object]:
        update_calls.append({"plan_dir": plan_dir, "payload": review_payload, "iteration": iteration})
        call_order.append("update_flags_after_review")
        return {"flags": []}

    monkeypatch.setattr(megaplan.handlers, "update_flags_after_review", _update_flags_after_review)
    monkeypatch.setattr(
        megaplan.handlers.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (
            call_order.append("run_step_with_worker") or (worker, "codex", "persistent", False)
        ),
    )

    megaplan.handle_review(fixture.root, fixture.make_args(plan=fixture.plan_name))
    stored_review = read_json(fixture.plan_dir / "review.json")

    assert stored_review["review_verdict"] == payload["review_verdict"]
    assert stored_review["task_verdicts"] == payload["task_verdicts"]
    assert stored_review["sense_check_verdicts"] == payload["sense_check_verdicts"]
    assert stored_review["pre_check_flags"] == _normalized_pre_check_flags(pre_check_flags)
    assert len(update_calls) == 1
    assert update_calls[0]["payload"] is worker.payload
    assert "update_flags_after_review" in call_order


def test_handle_review_non_hermes_branch_valid_payload_audited_then_written(
    tmp_path: Path,
    bootstrap_fixture: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove that for the non-Hermes path with a valid payload, schema audit
    passes, then the payload is written to review.json before finalize."""
    fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="superrobust")
    _advance_to_executed(fixture)
    _plan_dir, state = _load_executed_plan(fixture)
    payload = _build_mock_payload("review", state, fixture.plan_dir, summary="Golden non-hermes payload.")

    worker = WorkerResult(
        payload=payload,
        raw_output="review",
        duration_ms=1,
        cost_usd=0.0,
        session_id="review-non-hermes-valid",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )

    monkeypatch.delenv(megaplan.MOCK_ENV_VAR, raising=False)
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda *args, **kwargs: ("codex", "persistent", False, "mock-model"),
    )
    monkeypatch.setattr(
        megaplan.handlers.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (worker, "codex", "persistent", False),
    )

    response = megaplan.handle_review(fixture.root, fixture.make_args(plan=fixture.plan_name))

    assert response["success"] is True
    stored_review = read_json(fixture.plan_dir / "review.json")
    assert stored_review["review_verdict"] == payload["review_verdict"]
    assert stored_review["task_verdicts"] == payload["task_verdicts"]
    assert stored_review["sense_check_verdicts"] == payload["sense_check_verdicts"]
