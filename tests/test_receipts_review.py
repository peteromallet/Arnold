from __future__ import annotations

import json
from pathlib import Path

import pytest

import arnold.pipelines.megaplan as megaplan
import arnold.pipelines.megaplan.handlers as megaplan_handlers
from arnold.pipelines.megaplan._core import load_plan
from arnold.pipelines.megaplan.workers import WorkerResult, _build_mock_payload
from tests.conftest import PlanFixture, read_json
from tests.test_handle_review_robustness import (
    _advance_to_executed,
    _make_plan_fixture,
)


def _review_receipts(audit_dir: Path, plan_id: str) -> list[dict[str, object]]:
    receipts_path = audit_dir / "receipts.jsonl"
    assert receipts_path.exists()
    return [
        payload
        for payload in (
            json.loads(line)
            for line in receipts_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if payload.get("plan_id") == plan_id and payload.get("phase") == "review"
    ]


def _assert_review_receipt(
    *,
    plan_dir: Path,
    audit_dir: Path,
    plan_id: str,
    verdict: str,
) -> None:
    receipt_path = plan_dir / "step_receipt_review_v1.json"
    assert receipt_path.exists()
    receipt = read_json(receipt_path)
    assert receipt["phase"] == "review"
    assert receipt["verdict"] == verdict
    assert receipt["scope_drift_severity"] is None

    audit_receipts = _review_receipts(audit_dir, plan_id)
    assert audit_receipts
    matching = audit_receipts[-1]
    assert matching["phase"] == "review"
    assert matching["verdict"] == verdict
    assert matching["scope_drift_severity"] is None


def test_review_receipt_written_for_non_parallel_branch(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(audit_dir))
    args = plan_fixture.make_args(plan=plan_fixture.plan_name)

    megaplan.handle_plan(plan_fixture.root, args)
    megaplan.handle_critique(plan_fixture.root, args)
    megaplan.handle_override(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            override_action="force-proceed",
            reason="test",
        ),
    )
    megaplan.handle_finalize(plan_fixture.root, args)
    megaplan.handle_execute(
        plan_fixture.root,
        plan_fixture.make_args(
            plan=plan_fixture.plan_name,
            confirm_destructive=True,
            user_approved=True,
        ),
    )

    response = megaplan.handle_review(plan_fixture.root, args)

    assert response["success"] is True
    _assert_review_receipt(
        plan_dir=plan_fixture.plan_dir,
        audit_dir=audit_dir,
        plan_id=plan_fixture.plan_name,
        verdict="approved",
    )


def test_review_receipt_written_for_parallel_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(audit_dir))
    fixture = _make_plan_fixture(tmp_path, monkeypatch, robustness="superrobust")
    _advance_to_executed(fixture)
    _plan_dir, state = load_plan(fixture.root, fixture.plan_name)
    criteria_payload = _build_mock_payload(
        "review",
        state,
        fixture.plan_dir,
        review_verdict="approved",
    )
    parallel_result = WorkerResult(
        payload={
            "criteria_payload": criteria_payload,
            "checks": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
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
    monkeypatch.setattr(megaplan.handlers, "run_pre_checks", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        megaplan.handlers,
        "run_parallel_review",
        lambda *args, **kwargs: parallel_result,
    )
    monkeypatch.setattr(
        megaplan.handlers.worker_module,
        "run_step_with_worker",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("parallel review should not use the legacy worker")
        ),
    )

    response = megaplan.handle_review(
        fixture.root,
        fixture.make_args(plan=fixture.plan_name),
    )

    assert response["success"] is True
    _assert_review_receipt(
        plan_dir=fixture.plan_dir,
        audit_dir=audit_dir,
        plan_id=fixture.plan_name,
        verdict="approved",
    )
