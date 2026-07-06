"""Focused tests for boundary receipt persistence primitives (T5).

Covers atomic per-boundary JSON writes, JSONL audit record append,
serialization fidelity, best-effort error handling, and isolation
from existing step receipt behavior.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from arnold.workflow.boundary_evidence import (
    AuthorityRecord,
    BoundaryOutcome,
    BoundaryReceipt,
)
from arnold_pipelines.megaplan.receipts.writer import (
    _append_jsonl,
    write_boundary_receipt,
    write_receipt,
)


# ── helpers ─────────────────────────────────────────────────────────────────


def _make_receipt(
    boundary_id: str = "prep_to_plan",
    **overrides: object,
) -> BoundaryReceipt:
    kwargs: dict[str, object] = {
        "boundary_id": boundary_id,
        "workflow_id": "megaplan-review",
        "row_id": "s2-prep-row",
        "invocation_id": "inv-001",
        "artifact_refs": ("research.md", "brief.md"),
        "state_observation": {"current_phase": "prep"},
        "history_ref": "prep_completed",
        "phase_result_ref": "phase_result.json",
        "outcome": BoundaryOutcome.COMPLETE,
        "authority_records": (
            AuthorityRecord(
                actor="system",
                role="orchestrator",
                decision="proceed",
            ),
        ),
        "details": {"note": "boundary complete"},
    }
    kwargs.update(overrides)
    return BoundaryReceipt(**kwargs)  # type: ignore[arg-type]


# ── atomic JSON write ───────────────────────────────────────────────────────


def test_writes_per_boundary_json_atomically(tmp_path: Path) -> None:
    """write_boundary_receipt writes {boundary_id}.json in boundary_receipts/."""
    plan_dir = tmp_path / "plan"
    receipt = _make_receipt("prep_to_plan")
    write_boundary_receipt(plan_dir, receipt)

    json_path = plan_dir / "boundary_receipts" / "prep_to_plan.json"
    assert json_path.is_file(), f"Expected {json_path} to exist"

    data = json.loads(json_path.read_text())
    assert data["boundary_id"] == "prep_to_plan"
    assert data["workflow_id"] == "megaplan-review"
    assert data["outcome"] == "complete"


def test_writes_different_boundary_ids_to_separate_files(tmp_path: Path) -> None:
    """Each boundary_id gets its own JSON file."""
    plan_dir = tmp_path / "plan"
    for bid in ("prep_to_plan", "plan_to_critique", "critique_to_gate"):
        write_boundary_receipt(plan_dir, _make_receipt(bid))

    receipts_dir = plan_dir / "boundary_receipts"
    assert sorted(p.name for p in receipts_dir.iterdir()) == [
        "critique_to_gate.json",
        "plan_to_critique.json",
        "prep_to_plan.json",
    ]


def test_overwrites_existing_boundary_receipt(tmp_path: Path) -> None:
    """Writing the same boundary_id overwrites the previous JSON atomically."""
    plan_dir = tmp_path / "plan"
    r1 = _make_receipt("prep_to_plan", invocation_id="inv-old")
    write_boundary_receipt(plan_dir, r1)

    r2 = _make_receipt("prep_to_plan", invocation_id="inv-new")
    write_boundary_receipt(plan_dir, r2)

    data = json.loads((plan_dir / "boundary_receipts" / "prep_to_plan.json").read_text())
    assert data["invocation_id"] == "inv-new"


# ── JSONL audit record append ───────────────────────────────────────────────


def test_appends_jsonl_audit_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The JSONL audit file gets a record appended for each boundary write."""
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(audit_dir))

    plan_dir = tmp_path / "plan"
    receipt = _make_receipt("prep_to_plan")
    write_boundary_receipt(plan_dir, receipt)

    jsonl_path = audit_dir / "boundary_receipts.jsonl"
    assert jsonl_path.is_file()

    lines = jsonl_path.read_text().strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["boundary_id"] == "prep_to_plan"


def test_appends_multiple_records_to_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each write appends one line to the same JSONL audit file."""
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(audit_dir))

    plan_dir = tmp_path / "plan"
    for bid in ("prep_to_plan", "plan_to_critique"):
        write_boundary_receipt(plan_dir, _make_receipt(bid))

    jsonl_path = audit_dir / "boundary_receipts.jsonl"
    lines = jsonl_path.read_text().strip().split("\n")
    assert len(lines) == 2
    ids = {json.loads(line)["boundary_id"] for line in lines}
    assert ids == {"prep_to_plan", "plan_to_critique"}


def test_uses_default_audit_dir_when_env_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When MEGAPLAN_AUDIT_DIR is not set, falls back to ~/.megaplan/audit."""
    monkeypatch.delenv("MEGAPLAN_AUDIT_DIR", raising=False)
    fake_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(fake_home))

    plan_dir = tmp_path / "plan"
    write_boundary_receipt(plan_dir, _make_receipt("prep_to_plan"))

    jsonl_path = fake_home / ".megaplan" / "audit" / "boundary_receipts.jsonl"
    assert jsonl_path.is_file()


# ── project_dir mirroring ───────────────────────────────────────────────────


def test_mirrors_to_repo_audit_when_flag_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When MEGAPLAN_REPO_AUDIT_MIRROR=1, also writes to project .megaplan/audit."""
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(audit_dir))
    monkeypatch.setenv("MEGAPLAN_REPO_AUDIT_MIRROR", "1")

    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    write_boundary_receipt(plan_dir, _make_receipt("prep_to_plan"), project_dir=project_dir)

    repo_jsonl = project_dir / ".megaplan" / "audit" / "boundary_receipts.jsonl"
    assert repo_jsonl.is_file()


def test_mirrors_to_repo_audit_when_dir_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the repo audit dir already exists, mirror even without the env flag."""
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(audit_dir))
    monkeypatch.delenv("MEGAPLAN_REPO_AUDIT_MIRROR", raising=False)

    project_dir = tmp_path / "project"
    (project_dir / ".megaplan" / "audit").mkdir(parents=True)
    plan_dir = tmp_path / "plan"

    write_boundary_receipt(plan_dir, _make_receipt("prep_to_plan"), project_dir=project_dir)

    repo_jsonl = project_dir / ".megaplan" / "audit" / "boundary_receipts.jsonl"
    assert repo_jsonl.is_file()


def test_does_not_mirror_when_flag_off_and_dir_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No mirror when flag is unset and repo audit dir doesn't exist."""
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(audit_dir))
    monkeypatch.delenv("MEGAPLAN_REPO_AUDIT_MIRROR", raising=False)

    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"

    write_boundary_receipt(plan_dir, _make_receipt("prep_to_plan"), project_dir=project_dir)

    repo_jsonl = project_dir / ".megaplan" / "audit" / "boundary_receipts.jsonl"
    assert not repo_jsonl.exists()


def test_no_mirror_when_project_dir_is_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When project_dir is None, no mirroring is attempted."""
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(audit_dir))
    monkeypatch.setenv("MEGAPLAN_REPO_AUDIT_MIRROR", "1")

    plan_dir = tmp_path / "plan"
    # Should not raise or attempt mirroring
    write_boundary_receipt(plan_dir, _make_receipt("prep_to_plan"), project_dir=None)

    # Only the primary audit log should have the record
    jsonl_path = audit_dir / "boundary_receipts.jsonl"
    assert jsonl_path.is_file()


# ── serialization fidelity ──────────────────────────────────────────────────


def test_serializes_artifact_refs(tmp_path: Path) -> None:
    """Artifact refs are serialized as a JSON list."""
    plan_dir = tmp_path / "plan"
    receipt = _make_receipt("prep_to_plan", artifact_refs=("a.md", "b.md"))
    write_boundary_receipt(plan_dir, receipt)

    data = json.loads((plan_dir / "boundary_receipts" / "prep_to_plan.json").read_text())
    assert data["artifact_refs"] == ["a.md", "b.md"]


def test_serializes_authority_records(tmp_path: Path) -> None:
    """Authority records are serialized with all fields preserved."""
    plan_dir = tmp_path / "plan"
    ar = AuthorityRecord(
        actor="alice",
        role="reviewer",
        decision="approved",
        scope="full",
        conditions=("no-urgent",),
        evidence_refs=("ev-1",),
        expiry="2026-12-31",
        waiver_reason=None,
    )
    receipt = _make_receipt("prep_to_plan", authority_records=(ar,))
    write_boundary_receipt(plan_dir, receipt)

    data = json.loads((plan_dir / "boundary_receipts" / "prep_to_plan.json").read_text())
    assert len(data["authority_records"]) == 1
    rec = data["authority_records"][0]
    assert rec["actor"] == "alice"
    assert rec["role"] == "reviewer"
    assert rec["decision"] == "approved"
    assert rec["scope"] == "full"
    assert rec["conditions"] == ["no-urgent"]
    assert rec["evidence_refs"] == ["ev-1"]
    assert rec["expiry"] == "2026-12-31"


def test_serializes_state_observation(tmp_path: Path) -> None:
    """State observation dict is fully serialized."""
    plan_dir = tmp_path / "plan"
    receipt = _make_receipt(
        "prep_to_plan",
        state_observation={"current_phase": "prep", "iteration": 3},
    )
    write_boundary_receipt(plan_dir, receipt)

    data = json.loads((plan_dir / "boundary_receipts" / "prep_to_plan.json").read_text())
    assert data["state_observation"] == {"current_phase": "prep", "iteration": 3}


def test_serializes_all_outcome_values(tmp_path: Path) -> None:
    """Every BoundaryOutcome value serializes correctly."""
    plan_dir = tmp_path / "plan"
    for outcome in BoundaryOutcome:
        receipt = _make_receipt(f"test_{outcome.value}", outcome=outcome)
        write_boundary_receipt(plan_dir, receipt)

        data = json.loads(
            (plan_dir / "boundary_receipts" / f"test_{outcome.value}.json").read_text(),
        )
        assert data["outcome"] == outcome.value


def test_receipt_version_in_payload(tmp_path: Path) -> None:
    """The receipt_version field is included in the serialized payload."""
    plan_dir = tmp_path / "plan"
    receipt = _make_receipt("prep_to_plan")
    write_boundary_receipt(plan_dir, receipt)

    data = json.loads((plan_dir / "boundary_receipts" / "prep_to_plan.json").read_text())
    assert data["receipt_version"] == "arnold.workflow.boundary_receipt.v1"


# ── best-effort error handling ──────────────────────────────────────────────


def test_does_not_raise_on_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When the write path is invalid, the function returns without raising."""
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(audit_dir))

    # Use a plan_dir that is actually a file, causing mkdir to fail
    plan_dir = tmp_path / "plan"
    plan_dir.write_text("not-a-dir")

    receipt = _make_receipt("prep_to_plan")
    # Must not raise
    write_boundary_receipt(plan_dir, receipt)


def test_does_not_raise_when_audit_dir_unwritable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the audit dir cannot be created, the function still returns."""
    # Point audit to a path whose parent is a file, not a dir
    bad_audit = tmp_path / "file_block" / "audit"
    (tmp_path / "file_block").write_text("blocked")
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(bad_audit))

    plan_dir = tmp_path / "plan"
    receipt = _make_receipt("prep_to_plan")
    # Must not raise — the JSON write succeeds, audit append fails silently
    write_boundary_receipt(plan_dir, receipt)

    # The primary JSON file should still be written
    json_path = plan_dir / "boundary_receipts" / "prep_to_plan.json"
    assert json_path.is_file()


def test_does_not_raise_when_receipt_to_dict_fails() -> None:
    """A receipt whose to_dict raises is caught by the try/except."""
    plan_dir = Path("/nonexistent/tmp/plan")

    class BrokenReceipt:
        boundary_id = "broken"

        def to_dict(self) -> dict:
            raise RuntimeError("serialization exploded")

    # Must not propagate the exception
    write_boundary_receipt(plan_dir, BrokenReceipt())  # type: ignore[arg-type]


# ── isolation from existing step receipt behavior ───────────────────────────


def test_step_receipt_unchanged_by_boundary_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """write_boundary_receipt does not affect the step receipt output path."""
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(audit_dir))

    plan_dir = tmp_path / "plan"
    step_receipt = {"phase": "prep", "iteration": 1, "success": True}
    write_receipt(plan_dir, step_receipt)

    # Write a boundary receipt — must not overwrite or interfere
    write_boundary_receipt(plan_dir, _make_receipt("prep_to_plan"))

    # Step receipt still intact
    step_path = plan_dir / "step_receipt_prep_v1.json"
    assert step_path.is_file()
    step_data = json.loads(step_path.read_text())
    assert step_data["phase"] == "prep"
    assert step_data["iteration"] == 1


def test_step_receipt_audit_log_unchanged_by_boundary_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Boundary writes go to boundary_receipts.jsonl, not receipts.jsonl."""
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("MEGAPLAN_AUDIT_DIR", str(audit_dir))

    plan_dir = tmp_path / "plan"
    write_receipt(plan_dir, {"phase": "prep", "iteration": 1})

    step_audit = audit_dir / "receipts.jsonl"
    assert step_audit.is_file()
    step_lines_before = len(step_audit.read_text().strip().split("\n"))

    # Write boundary receipts — must not add to receipts.jsonl
    write_boundary_receipt(plan_dir, _make_receipt("prep_to_plan"))
    write_boundary_receipt(plan_dir, _make_receipt("plan_to_critique"))

    step_lines_after = len(step_audit.read_text().strip().split("\n"))
    assert step_lines_after == step_lines_before

    # Boundary records go to their own file
    boundary_audit = audit_dir / "boundary_receipts.jsonl"
    assert boundary_audit.is_file()
    boundary_lines = len(boundary_audit.read_text().strip().split("\n"))
    assert boundary_lines == 2


def test_boundary_receipt_does_not_create_step_receipt_files(tmp_path: Path) -> None:
    """Boundary writes only create boundary_receipts/, never step_receipt_* files."""
    plan_dir = tmp_path / "plan"
    write_boundary_receipt(plan_dir, _make_receipt("prep_to_plan"))

    step_files = list(plan_dir.glob("step_receipt_*"))
    assert len(step_files) == 0


# ── _append_jsonl helper ────────────────────────────────────────────────────


def test_append_jsonl_creates_parent_dirs(tmp_path: Path) -> None:
    """_append_jsonl creates parent directories as needed."""
    jsonl_path = tmp_path / "deep" / "nested" / "audit.jsonl"
    _append_jsonl(jsonl_path, {"key": "value"})
    assert jsonl_path.is_file()


def test_append_jsonl_appends_lines(tmp_path: Path) -> None:
    """Each call to _append_jsonl adds one newline-delimited JSON record."""
    path = tmp_path / "log.jsonl"
    _append_jsonl(path, {"a": 1})
    _append_jsonl(path, {"b": 2})
    _append_jsonl(path, {"c": 3})

    lines = path.read_text().strip().split("\n")
    assert len(lines) == 3
    assert json.loads(lines[0]) == {"a": 1}
    assert json.loads(lines[1]) == {"b": 2}
    assert json.loads(lines[2]) == {"c": 3}


def test_append_jsonl_sorted_keys_roundtrip(tmp_path: Path) -> None:
    """Records are serialized with sorted keys for deterministic output."""
    path = tmp_path / "log.jsonl"
    _append_jsonl(path, {"z": 3, "a": 1, "m": 2})
    raw = path.read_text().strip()
    parsed = json.loads(raw)
    # Keys are serialized sorted, so the first key in raw should be 'a'
    assert raw.startswith('{"a":')
    assert parsed == {"a": 1, "m": 2, "z": 3}


# ── completeness ────────────────────────────────────────────────────────────


def test_write_boundary_receipt_accepts_minimal_receipt(tmp_path: Path) -> None:
    """A receipt with only boundary_id and workflow_id is valid."""
    plan_dir = tmp_path / "plan"
    receipt = BoundaryReceipt(boundary_id="minimal", workflow_id="wf")
    write_boundary_receipt(plan_dir, receipt)

    data = json.loads((plan_dir / "boundary_receipts" / "minimal.json").read_text())
    assert data["boundary_id"] == "minimal"
    assert data["workflow_id"] == "wf"


def test_write_boundary_receipt_with_all_optional_fields_none(tmp_path: Path) -> None:
    """A receipt with only required fields and all optionals as None serializes cleanly."""
    plan_dir = tmp_path / "plan"
    receipt = _make_receipt(
        "sparse",
        row_id=None,
        invocation_id=None,
        artifact_refs=(),
        state_observation={},
        history_ref=None,
        phase_result_ref=None,
        outcome=None,
        authority_records=(),
        details={},
    )
    write_boundary_receipt(plan_dir, receipt)

    data = json.loads((plan_dir / "boundary_receipts" / "sparse.json").read_text())
    assert data["boundary_id"] == "sparse"
    assert "row_id" not in data
    assert "invocation_id" not in data
    assert "artifact_refs" not in data
    assert "state_observation" not in data
    assert "history_ref" not in data
    assert "phase_result_ref" not in data
    assert "outcome" not in data
    assert "authority_records" not in data
    assert "details" not in data


def test_write_boundary_receipt_preserves_details(tmp_path: Path) -> None:
    """Custom details dict is preserved in the serialized output."""
    plan_dir = tmp_path / "plan"
    receipt = _make_receipt("detailed", details={"source": "test", "count": 42})
    write_boundary_receipt(plan_dir, receipt)

    data = json.loads((plan_dir / "boundary_receipts" / "detailed.json").read_text())
    assert data["details"] == {"source": "test", "count": 42}
