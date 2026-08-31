"""Fail-closed custody proof for completed chain babysitter runs."""

from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.cloud.babysitter.launch import (
    CHAIN_DRIVE_RECEIPT_SCHEMA,
    _chain_drive_custody_error,
    _validate_chain_drive_receipt,
)


def _ctx(tmp_path: Path) -> dict[str, str]:
    return {
        "session": "native-build-forward",
        "occurrence": "occurrence-1",
        "plan": "native-c1-completion-contract-1",
        "workspace": str(tmp_path),
        "run_kind": "chain",
        "run_root": str(tmp_path / "run"),
    }


def _receipt(ctx: dict[str, str]) -> dict[str, object]:
    return {
        "schema": CHAIN_DRIVE_RECEIPT_SCHEMA,
        "session": ctx["session"],
        "occurrence_digest": ctx["occurrence"],
        "plan": ctx["plan"],
        "workspace": ctx["workspace"],
        "status": "launched",
        "custody": {
            "persist": True,
            "detached": True,
            "pty": False,
            "restart": "no",
            "ready_matcher": None,
        },
    }


def test_valid_receipt_binds_identity_and_custody_contract(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    assert _validate_chain_drive_receipt(ctx, _receipt(ctx)) is None


def test_missing_receipt_blocks_chain_completion(tmp_path: Path) -> None:
    assert "receipt is missing" in (_chain_drive_custody_error(_ctx(tmp_path)) or "")


def test_receipt_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    receipt = _receipt(ctx)
    receipt["occurrence_digest"] = "different-occurrence"
    assert "identity mismatch" in (_validate_chain_drive_receipt(ctx, receipt) or "")


def test_each_invalid_custody_field_is_rejected(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    for field, value in (
        ("persist", False),
        ("detached", False),
        ("pty", True),
        ("restart", "on-failure"),
        ("ready_matcher", "ready"),
    ):
        receipt = _receipt(ctx)
        receipt["custody"][field] = value  # type: ignore[index]
        assert field in (_validate_chain_drive_receipt(ctx, receipt) or "")


def test_non_chain_runs_do_not_require_chain_receipt(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    ctx["run_kind"] = "plan"
    assert _chain_drive_custody_error(ctx) is None
