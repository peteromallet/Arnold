"""Tests for JudgePiece (M5-eval T4)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from megaplan._pipeline.judge_piece import JudgePiece
from megaplan._pipeline.types import Step, StepContext
from megaplan.observability.events import EventKind, read_events


def _ctx(plan_dir: Path) -> StepContext:
    return StepContext(
        plan_dir=plan_dir,
        state={"config": {"project_dir": str(plan_dir), "plan_id": "p1"}},
        profile=None,
        mode="code",
    )


def _mk_judge() -> JudgePiece:
    return JudgePiece(
        name="j", rubric_body="rubric body", judge_model="m@v1", rubric_version="v1"
    )


def _mock_dispatch():
    return {"text": "{}", "model_actual": "m@v1", "usage": {}}


def test_step_protocol_compliance():
    jp = _mk_judge()
    assert isinstance(jp, Step)


def test_empty_rubric_raises():
    with pytest.raises(ValueError):
        JudgePiece(name="j", rubric_body="", judge_model="m", rubric_version="v1")


def test_payload_evaluand_always_attached_flag_off(tmp_path, monkeypatch):
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    jp = _mk_judge()
    with patch(
        "megaplan.workers.hermes.dispatch_judge", return_value=_mock_dispatch()
    ) as m:
        result = jp.run(_ctx(tmp_path))
    assert m.call_count == 1
    assert result.verdict is not None
    assert "evaluand" in result.verdict.payload
    assert result.verdict.recommendation == "proceed"
    assert result.verdict.score == 0.0
    # Flag off → no journal events, no prompt cache dir.
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    assert events == []
    assert not (tmp_path / "evaluand_prompts").exists()


def test_flag_on_emits_once_and_writes_once(tmp_path, monkeypatch):
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    jp = _mk_judge()
    with patch(
        "megaplan.workers.hermes.dispatch_judge", return_value=_mock_dispatch()
    ):
        result = jp.run(_ctx(tmp_path))
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    assert len(events) == 1
    prompts = list((tmp_path / "evaluand_prompts").glob("*.json"))
    assert len(prompts) == 1
    emitted = events[0]["payload"]["record"]
    assert emitted == result.verdict.payload["evaluand"]


def test_judge_version_byte_stable(tmp_path, monkeypatch):
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    with patch(
        "megaplan.workers.hermes.dispatch_judge", return_value=_mock_dispatch()
    ):
        r1 = _mk_judge().run(_ctx(tmp_path))
        r2 = _mk_judge().run(_ctx(tmp_path))
    assert r1.verdict.payload["evaluand"]["judge_version"] == r2.verdict.payload[
        "evaluand"
    ]["judge_version"]


def test_judge_version_changes_with_model(tmp_path, monkeypatch):
    monkeypatch.delenv("MEGAPLAN_UNIFIED_DISPATCH", raising=False)
    a = JudgePiece(name="j", rubric_body="r", judge_model="m@v1", rubric_version="v1")
    b = JudgePiece(name="j", rubric_body="r", judge_model="m@v2", rubric_version="v1")
    with patch(
        "megaplan.workers.hermes.dispatch_judge", return_value=_mock_dispatch()
    ):
        ra = a.run(_ctx(tmp_path))
        rb = b.run(_ctx(tmp_path))
    assert (
        ra.verdict.payload["evaluand"]["judge_version"]
        != rb.verdict.payload["evaluand"]["judge_version"]
    )


def test_provenance_fallback_when_absent(tmp_path):
    jp = _mk_judge()
    ctx = _ctx(tmp_path)
    assert getattr(ctx, "provenance", None) is None
    with patch(
        "megaplan.workers.hermes.dispatch_judge", return_value=_mock_dispatch()
    ):
        result = jp.run(ctx)
    assert result.verdict.payload["evaluand"]["provenance"] == {}


def test_dispatch_invoked_exactly_once(tmp_path):
    jp = _mk_judge()
    with patch(
        "megaplan.workers.hermes.dispatch_judge", return_value=_mock_dispatch()
    ) as m:
        jp.run(_ctx(tmp_path))
    assert m.call_count == 1
