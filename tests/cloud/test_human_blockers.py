"""Tests for conservative human-blocker classifier and disabled ledger writer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.human_blockers import (
    BlockerVerdict,
    EscalationLedgerWriter,
    HumanBlockerClassification,
    build_needs_human_marker,
    classify_needs_human_blocker,
    write_needs_human_marker_payload,
)
from arnold_pipelines.megaplan.cloud.redact import REDACTION
from arnold_pipelines.megaplan.cloud.repair_contract import read_jsonl_records


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def marker_fixture(tmp_path: Path) -> dict[str, Path]:
    """Create a minimal marker/repair-data directory tree for testing."""
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    workspace = tmp_path / "ws"
    plans_dir = workspace / ".megaplan" / "plans"

    marker_dir.mkdir(parents=True)
    repair_data_dir.mkdir(parents=True)
    workspace.mkdir(parents=True)
    plans_dir.mkdir(parents=True)

    return {
        "marker_dir": marker_dir,
        "repair_data_dir": repair_data_dir,
        "workspace": workspace,
        "plans_dir": plans_dir,
    }


def _write_needs_human(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_marker(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_plan_state(plans_dir: Path, plan_name: str, state: dict[str, object]) -> None:
    plan_dir = plans_dir / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


# ---------------------------------------------------------------------------
# Classifier tests
# ---------------------------------------------------------------------------


def test_classify_true_blocker_when_needs_human_refs_current_plan(
    marker_fixture: dict[str, Path],
) -> None:
    """A needs-human sidecar that references the current plan is a TRUE_BLOCKER."""
    session = "demo-session"
    current_plan = "m2-current-plan"
    marker_dir = marker_fixture["marker_dir"]
    repair_data_dir = marker_fixture["repair_data_dir"]
    plans_dir = marker_fixture["plans_dir"]

    _write_marker(
        marker_dir / f"{session}.json",
        {
            "session": session,
            "workspace": str(marker_fixture["workspace"]),
            "plan_name": current_plan,
            "run_kind": "plan",
        },
    )
    _write_plan_state(plans_dir, current_plan, {"name": current_plan, "current_state": "running"})
    _write_needs_human(
        repair_data_dir / f"{session}.needs-human.json",
        {
            "summary": "repair exhausted — awaiting human",
            "plan_name": current_plan,
            "current_plan_name": current_plan,
        },
    )

    classification = classify_needs_human_blocker(
        session,
        current_plan=current_plan,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )

    assert classification.verdict == BlockerVerdict.TRUE_BLOCKER
    assert classification.is_true_blocker is True
    assert classification.is_stale_mismatch is False
    assert classification.is_ambiguous is False
    assert classification.should_block is True
    assert classification.session == session
    assert classification.current_plan == current_plan
    assert classification.needs_human_payload is not None
    assert classification.needs_human_payload["summary"] == "repair exhausted — awaiting human"
    assert any("references current plan" in r for r in classification.rationale)


def test_classify_stale_mismatch_via_explicit_stale_evidence(
    marker_fixture: dict[str, Path],
) -> None:
    """When resolver produces stale_needs_human_plan_ref, verdict is STALE_MISMATCH."""
    session = "demo-session"
    current_plan = "m2-current-plan"
    old_plan = "m1-old-plan"
    marker_dir = marker_fixture["marker_dir"]
    repair_data_dir = marker_fixture["repair_data_dir"]
    plans_dir = marker_fixture["plans_dir"]

    _write_marker(
        marker_dir / f"{session}.json",
        {
            "session": session,
            "workspace": str(marker_fixture["workspace"]),
            "plan_name": current_plan,
            "run_kind": "plan",
        },
    )
    _write_plan_state(plans_dir, current_plan, {"name": current_plan, "current_state": "running"})
    _write_needs_human(
        repair_data_dir / f"{session}.needs-human.json",
        {
            "summary": "old repair exhaustion",
            "plan_name": old_plan,
            "current_plan_name": old_plan,
        },
    )

    classification = classify_needs_human_blocker(
        session,
        current_plan=current_plan,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )

    assert classification.verdict == BlockerVerdict.STALE_MISMATCH
    assert classification.is_true_blocker is False
    assert classification.is_stale_mismatch is True
    assert classification.is_ambiguous is False
    assert classification.should_block is False
    assert any("stale needs-human" in r for r in classification.rationale)


def test_classify_stale_mismatch_via_plan_ref_difference(
    marker_fixture: dict[str, Path],
) -> None:
    """When resolver plan_refs exclude the current plan, verdict is STALE_MISMATCH."""
    session = "demo-session"
    current_plan = "m3-new-plan"
    old_plan = "m2-old-plan"
    marker_dir = marker_fixture["marker_dir"]
    repair_data_dir = marker_fixture["repair_data_dir"]
    plans_dir = marker_fixture["plans_dir"]

    _write_marker(
        marker_dir / f"{session}.json",
        {
            "session": session,
            "workspace": str(marker_fixture["workspace"]),
            "plan_name": current_plan,
            "run_kind": "plan",
        },
    )
    _write_plan_state(plans_dir, current_plan, {"name": current_plan, "current_state": "running"})
    # needs-human references only old_plan, not current_plan
    _write_needs_human(
        repair_data_dir / f"{session}.needs-human.json",
        {
            "summary": "old repair exhaustion",
            "plan_name": old_plan,
            "current_plan_name": old_plan,
        },
    )

    classification = classify_needs_human_blocker(
        session,
        current_plan=current_plan,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )

    assert classification.verdict == BlockerVerdict.STALE_MISMATCH
    assert classification.should_block is False


def test_classify_ambiguous_when_needs_human_missing(
    marker_fixture: dict[str, Path],
) -> None:
    """Missing needs-human sidecar → AMBIGUOUS_BLOCKER (conservative)."""
    session = "ghost-session"
    current_plan = "m1-plan"
    marker_dir = marker_fixture["marker_dir"]
    repair_data_dir = marker_fixture["repair_data_dir"]

    # No needs-human file written

    classification = classify_needs_human_blocker(
        session,
        current_plan=current_plan,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )

    assert classification.verdict == BlockerVerdict.AMBIGUOUS_BLOCKER
    assert classification.is_ambiguous is True
    assert classification.should_block is True
    assert classification.needs_human_payload is None
    assert any("missing or unreadable" in r for r in classification.rationale)


def test_classify_ambiguous_when_resolver_plan_refs_empty(
    marker_fixture: dict[str, Path],
) -> None:
    """Empty resolver plan_refs → AMBIGUOUS_BLOCKER (conservative)."""
    session = "bare-session"
    current_plan = "m1-plan"
    marker_dir = marker_fixture["marker_dir"]
    repair_data_dir = marker_fixture["repair_data_dir"]

    _write_marker(
        marker_dir / f"{session}.json",
        {
            "session": session,
            "workspace": str(marker_fixture["workspace"]),
            "plan_name": current_plan,
            "run_kind": "plan",
        },
    )
    # needs-human has no plan_name / current_plan_name fields
    _write_needs_human(
        repair_data_dir / f"{session}.needs-human.json",
        {"summary": "generic exhaustion", "recorded_at": "2026-01-01T00:00:00Z"},
    )

    classification = classify_needs_human_blocker(
        session,
        current_plan=current_plan,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )

    assert classification.verdict == BlockerVerdict.AMBIGUOUS_BLOCKER
    assert classification.should_block is True
    assert any("did not produce plan_refs" in r for r in classification.rationale)


def test_classify_ambiguous_when_needs_human_unreadable(
    marker_fixture: dict[str, Path],
) -> None:
    """Corrupt needs-human sidecar → AMBIGUOUS_BLOCKER."""
    session = "corrupt-session"
    current_plan = "m1-plan"
    marker_dir = marker_fixture["marker_dir"]
    repair_data_dir = marker_fixture["repair_data_dir"]

    (repair_data_dir / f"{session}.needs-human.json").write_text(
        "not-valid-json!!!", encoding="utf-8"
    )

    classification = classify_needs_human_blocker(
        session,
        current_plan=current_plan,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )

    assert classification.verdict == BlockerVerdict.AMBIGUOUS_BLOCKER
    assert classification.needs_human_payload is None


def test_classify_with_preloaded_payload_and_resolver(
    marker_fixture: dict[str, Path],
) -> None:
    """Pre-loaded payload and resolver record bypass file I/O."""
    session = "preload-session"
    current_plan = "m1-plan"

    preloaded_payload = {
        "summary": "manual intervention needed",
        "plan_name": current_plan,
        "current_plan_name": current_plan,
    }

    preloaded_resolver = {
        "schema_version": 1,
        "session": session,
        "current_refs": {"current_plan_name": current_plan},
        "needs_human": {
            "path": "/fake/path",
            "present": True,
            "plan_refs": [current_plan],
        },
        "stale_evidence": [],
    }

    classification = classify_needs_human_blocker(
        session,
        current_plan=current_plan,
        marker_dir=marker_fixture["marker_dir"],
        needs_human_payload=preloaded_payload,
        resolver_record=preloaded_resolver,
    )

    assert classification.verdict == BlockerVerdict.TRUE_BLOCKER
    assert classification.needs_human_payload == preloaded_payload
    assert classification.resolver_record == preloaded_resolver


def test_classify_with_explicit_needs_human_path(
    marker_fixture: dict[str, Path],
) -> None:
    """Explicit needs_human_path is used instead of derived path."""
    session = "custom-session"
    current_plan = "m1-plan"
    marker_dir = marker_fixture["marker_dir"]
    repair_data_dir = marker_fixture["repair_data_dir"]

    # Put the needs-human at the repair-data dir with standard naming so the
    # resolver can find it, but pass the explicit path to verify it is used.
    custom_path = repair_data_dir / f"{session}.needs-human.json"

    _write_marker(
        marker_dir / f"{session}.json",
        {
            "session": session,
            "workspace": str(marker_fixture["workspace"]),
            "plan_name": current_plan,
            "run_kind": "plan",
        },
    )
    _write_plan_state(
        marker_fixture["plans_dir"],
        current_plan,
        {"name": current_plan, "current_state": "running"},
    )
    _write_needs_human(custom_path, {"summary": "custom", "plan_name": current_plan})

    classification = classify_needs_human_blocker(
        session,
        current_plan=current_plan,
        marker_dir=marker_dir,
        needs_human_path=custom_path,
    )

    assert classification.verdict == BlockerVerdict.TRUE_BLOCKER
    assert classification.needs_human_path == str(custom_path)


def test_write_needs_human_marker_payload_preserves_legacy_keys_and_adds_current_pointer(
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "repair-data.json"
    marker_path = tmp_path / "demo-session.needs-human.json"
    repair_payload = {
        "session": "demo-session",
        "workspace": "/tmp/workspace",
        "spec": "/tmp/workspace/.megaplan/initiatives/demo/chain.yaml",
        "run_kind": "chain",
        "plan_name": "m2-current-plan",
        "current_failure_context": {
            "resolver_output": {
                "target_id": "demo-session:m2-current-plan",
                "authoritative_source": "chain_state",
                "current_refs": {
                    "current_plan_name": "m2-current-plan",
                    "chain_current_plan_name": "m2-current-plan",
                },
            }
        },
        "iterations": [
            {
                "i": 1,
                "dev_model": "gpt-5.5",
                "dev_fix_sha": "abc1234",
                "mechanical_launch": "running",
                "kimi_launch": "failed:bad-creds",
                "why": "blocked by follow-up",
                "chain_state_summary": {"current_plan_name": "m2-current-plan"},
            }
        ],
    }
    marker = build_needs_human_marker(
        repair_payload,
        repair_data_path=data_path,
        discord_status="queued",
        recorded_at="2026-07-01T00:00:00+00:00",
    )
    assert marker["plan_name"] == "m2-current-plan"
    assert marker["chain_current_plan_name"] == "m2-current-plan"
    assert marker["current_plan_name"] == "m2-current-plan"
    assert marker["target_id"] == "demo-session:m2-current-plan"
    assert marker["authoritative_source"] == "chain_state"

    persisted = write_needs_human_marker_payload(
        marker_path,
        repair_payload,
        repair_data_path=data_path,
        discord_status="queued",
        recorded_at="2026-07-01T00:00:00+00:00",
    )
    assert persisted == marker
    on_disk = json.loads(marker_path.read_text(encoding="utf-8"))
    assert on_disk == marker


def test_write_needs_human_marker_payload_redacts_summary_strings(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    marker_path = tmp_path / "demo-session.needs-human.json"
    repair_payload = {
        "session": "demo-session",
        "workspace": "/tmp/workspace",
        "spec": "/tmp/workspace/.megaplan/initiatives/demo/chain.yaml",
        "run_kind": "chain",
        "plan_name": "m2-current-plan",
        "current_failure_context": {
            "resolver_output": {
                "target_id": "demo-session:m2-current-plan",
                "authoritative_source": "chain_state",
                "current_refs": {
                    "current_plan_name": "m2-current-plan",
                    "chain_current_plan_name": "m2-current-plan",
                },
            }
        },
        "iterations": [
            {
                "i": 1,
                "dev_model": "gpt-5.5",
                "dev_fix_sha": "abc1234",
                "mechanical_launch": "running",
                "kimi_launch": "failed",
                "why": "Authorization: Bearer bearer-secret-token-value",
                "chain_state_summary": {"current_plan_name": "m2-current-plan"},
            }
        ],
    }

    marker = write_needs_human_marker_payload(
        marker_path,
        repair_payload,
        repair_data_path=data_path,
        discord_status="queued",
        recorded_at="2026-07-01T00:00:00+00:00",
    )

    assert "bearer-secret-token-value" not in marker["summary"]
    assert marker["summary"].endswith(f"why=Authorization: Bearer {REDACTION}")


# ---------------------------------------------------------------------------
# Escalation ledger writer tests (disabled by default)
# ---------------------------------------------------------------------------


def test_ledger_writer_disabled_by_default() -> None:
    """New EscalationLedgerWriter instances are disabled."""
    writer = EscalationLedgerWriter()
    assert writer.enabled is False


def test_ledger_write_classification_is_noop_when_disabled() -> None:
    """write_classification returns None when ledger is disabled."""
    writer = EscalationLedgerWriter()
    classification = HumanBlockerClassification(
        verdict=BlockerVerdict.TRUE_BLOCKER,
        session="test",
        current_plan="m1-plan",
    )
    result = writer.write_classification(classification)
    assert result is None


def test_ledger_write_incident_is_noop_when_disabled() -> None:
    """write_incident returns None when ledger is disabled."""
    writer = EscalationLedgerWriter()
    result = writer.write_incident("test-session", kind="test", summary="no-op")
    assert result is None


def test_ledger_write_classification_when_enabled(tmp_path: Path) -> None:
    """When enabled, write_classification appends a record to the incidents sidecar."""
    sidecar_dir = tmp_path / "sidecars"
    writer = EscalationLedgerWriter()
    writer.enable(sidecar_dir)

    classification = HumanBlockerClassification(
        verdict=BlockerVerdict.TRUE_BLOCKER,
        session="demo-session",
        current_plan="m1-plan",
        needs_human_path="/fake/path/needs-human.json",
        rationale=("references current plan",),
        resolver_record={"stale_evidence": []},
        needs_human_payload={"summary": "test"},
    )

    result = writer.write_classification(classification)
    assert result is not None
    assert result.exists()

    records = read_jsonl_records(result)
    assert len(records) == 1
    record = records[0]
    assert record["session"] == "demo-session"
    assert record["kind"] == "blocker_classified"
    assert record["verdict"] == "TRUE_BLOCKER"
    assert record["current_plan"] == "m1-plan"
    assert record["rationale"] == ["references current plan"]


def test_ledger_write_incident_when_enabled(tmp_path: Path) -> None:
    """When enabled, write_incident appends a generic incident record."""
    sidecar_dir = tmp_path / "sidecars"
    writer = EscalationLedgerWriter()
    writer.enable(sidecar_dir)

    result = writer.write_incident(
        "demo-session",
        kind="manual_override",
        summary="human confirmed blocker",
        extra={"source": "operator"},
    )
    assert result is not None
    assert result.exists()

    records = read_jsonl_records(result)
    assert len(records) == 1
    record = records[0]
    assert record["session"] == "demo-session"
    assert record["kind"] == "manual_override"
    assert record["summary"] == "human confirmed blocker"
    assert record["source"] == "operator"


def test_ledger_disable_then_reenable(tmp_path: Path) -> None:
    """disable() stops writes; enable() resumes them."""
    sidecar_dir = tmp_path / "sidecars"
    writer = EscalationLedgerWriter()

    writer.enable(sidecar_dir)
    result1 = writer.write_incident("s1", kind="first", summary="before disable")
    assert result1 is not None

    writer.disable()
    result2 = writer.write_incident("s1", kind="second", summary="after disable")
    assert result2 is None

    writer.enable(sidecar_dir)
    result3 = writer.write_incident("s1", kind="third", summary="after re-enable")
    assert result3 is not None

    # All records should be in the same file
    records = read_jsonl_records(result3)
    assert len(records) == 2
    assert records[0]["kind"] == "first"
    assert records[1]["kind"] == "third"


def test_ledger_multiple_classifications_appended(tmp_path: Path) -> None:
    """Multiple classification writes append in order."""
    sidecar_dir = tmp_path / "sidecars"
    writer = EscalationLedgerWriter()
    writer.enable(sidecar_dir)

    for i, verdict in enumerate(
        [BlockerVerdict.TRUE_BLOCKER, BlockerVerdict.STALE_MISMATCH, BlockerVerdict.AMBIGUOUS_BLOCKER]
    ):
        classification = HumanBlockerClassification(
            verdict=verdict,
            session=f"session-{i}",
            current_plan=f"plan-{i}",
        )
        writer.write_classification(classification)

    records = read_jsonl_records(writer.write_incident("final", kind="check", summary="done") or Path("."))
    # Re-read the actual file
    jsonl_path = writer.sidecar_dir
    if jsonl_path:
        from arnold_pipelines.megaplan.cloud.repair_contract import _sidecar_jsonl_path

        all_records = read_jsonl_records(_sidecar_jsonl_path(jsonl_path, "incidents"))
        assert len(all_records) == 4
        verdicts = [r["verdict"] for r in all_records if r.get("kind") == "blocker_classified"]
        assert verdicts == ["TRUE_BLOCKER", "STALE_MISMATCH", "AMBIGUOUS_BLOCKER"]


def test_ledger_sidecar_dir_none_after_disable(tmp_path: Path) -> None:
    """Even after disable, sidecar_dir is retained but writes are no-ops."""
    sidecar_dir = tmp_path / "sidecars"
    writer = EscalationLedgerWriter()
    writer.enable(sidecar_dir)
    writer.disable()

    # sidecar_dir is still set but writes are suppressed
    assert writer.sidecar_dir == str(sidecar_dir)
    assert writer.enabled is False

    result = writer.write_incident("s1", kind="test", summary="should be noop")
    assert result is None


# ---------------------------------------------------------------------------
# HumanBlockerClassification property coverage
# ---------------------------------------------------------------------------


def test_should_block_false_only_for_stale_mismatch() -> None:
    """Only STALE_MISMATCH returns should_block=False."""
    true_blocker = HumanBlockerClassification(
        verdict=BlockerVerdict.TRUE_BLOCKER,
        session="s",
        current_plan="p",
    )
    stale = HumanBlockerClassification(
        verdict=BlockerVerdict.STALE_MISMATCH,
        session="s",
        current_plan="p",
    )
    ambiguous = HumanBlockerClassification(
        verdict=BlockerVerdict.AMBIGUOUS_BLOCKER,
        session="s",
        current_plan="p",
    )

    assert true_blocker.should_block is True
    assert stale.should_block is False
    assert ambiguous.should_block is True
