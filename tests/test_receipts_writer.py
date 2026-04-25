from __future__ import annotations

import builtins
import logging
from pathlib import Path

import pytest

import megaplan
import megaplan.receipts.writer as writer_module
from tests.conftest import PlanFixture


def test_finish_step_receipt_write_failure_is_best_effort(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(tmp_path / "audit"))

    def _raise_atomic_write(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(writer_module, "atomic_write_json", _raise_atomic_write)

    with caplog.at_level(logging.WARNING):
        response = megaplan.handle_plan(
            plan_fixture.root,
            plan_fixture.make_args(plan=plan_fixture.plan_name),
        )

    assert response["success"] is True
    assert "receipt write failed" in caplog.text
    assert (plan_fixture.plan_dir / "state.json").exists()


def test_jsonl_append_failure_is_best_effort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(audit_dir))

    real_open = builtins.open

    def _raise_for_jsonl(path: object, *args: object, **kwargs: object) -> object:
        if Path(path) == audit_dir / "receipts.jsonl":
            raise OSError("jsonl unavailable")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(writer_module, "open", _raise_for_jsonl, raising=False)
    receipt = {
        "phase": "plan",
        "iteration": 1,
        "plan_id": "test-plan",
    }

    with caplog.at_level(logging.WARNING):
        writer_module.write_receipt(plan_dir, receipt)

    assert "receipt write failed" in caplog.text

