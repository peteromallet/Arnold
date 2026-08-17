"""Regression: chain-authoritative auto_approve sync + canonical awaiting-human token."""
import json
import tempfile
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain import _sync_plan_auto_approve, _awaiting_human_can_retry


def _make_plan(root: Path, auto_approve: bool = False) -> Path:
    plan_dir = root / ".megaplan" / "plans" / "p1"
    plan_dir.mkdir(parents=True)
    state = {"name": "p1", "current_state": "finalized",
             "config": {"auto_approve": auto_approve},
             "meta": {"chain_policy": {"source": "chain_yaml"}}}
    (plan_dir / "state.json").write_text(json.dumps(state))
    return plan_dir


def test_sync_stale_false_to_true():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_plan(root, False)
        _sync_plan_auto_approve(root, "p1", True)
        state = json.loads((root / ".megaplan/plans/p1/state.json").read_text())
        assert state["config"]["auto_approve"] is True
        assert state["meta"]["chain_policy"]["driver_auto_approve"] is True


def test_sync_true_to_false_symmetric():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_plan(root, True)
        _sync_plan_auto_approve(root, "p1", False)
        state = json.loads((root / ".megaplan/plans/p1/state.json").read_text())
        assert state["config"]["auto_approve"] is False
        assert state["meta"]["chain_policy"]["driver_auto_approve"] is False


def test_sync_idempotent():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _make_plan(root, False)
        _sync_plan_auto_approve(root, "p1", True)
        p = root / ".megaplan/plans/p1/state.json"
        before = p.read_bytes()
        _sync_plan_auto_approve(root, "p1", True)
        assert p.read_bytes() == before


def test_awaiting_human_can_retry_accepts_verify_token():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        plan_dir = root / ".megaplan" / "plans" / "p1"
        plan_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(json.dumps(
            {"name": "p1", "current_state": "awaiting_human_verify"}))
        (plan_dir / "finalize.json").write_text(json.dumps({
            "user_actions": [{"id": "U1"}]}))
        (plan_dir / "user_action_resolutions.json").write_text(json.dumps({
            "U1": {"state": "waived", "created_at": "2026-08-17T10:41:58Z"}}))
        assert _awaiting_human_can_retry(root, "p1") is True


def test_awaiting_human_can_retry_negative_without_resolution():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        plan_dir = root / ".megaplan" / "plans" / "p1"
        plan_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(json.dumps(
            {"name": "p1", "current_state": "awaiting_human_verify"}))
        (plan_dir / "finalize.json").write_text(json.dumps({
            "user_actions": [{"id": "U1"}]}))
        assert _awaiting_human_can_retry(root, "p1") is False
