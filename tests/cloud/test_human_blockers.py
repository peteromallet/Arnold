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


def _current_target_proof_resolver(
    session: str,
    current_plan: str,
    authoritative_source: str = "plan_state",
    plan_state_present: bool = True,
    chain_state_present: bool = True,
) -> dict[str, object]:
    """Build a minimal resolver record that passes current-target proof checks."""
    return {
        "schema_version": 1,
        "session": session,
        "authoritative_source": authoritative_source,
        "current_refs": {"current_plan_name": current_plan},
        "needs_human": {
            "path": "/fake/path",
            "present": True,
            "plan_refs": [current_plan],
        },
        "plan_state": {
            "path": "/fake/plan/state.json",
            "present": plan_state_present,
            "mtime": 1234567890.0,
            "fingerprint": "abc123",
        },
        "chain_state": {
            "path": "/fake/chain/state.json",
            "present": chain_state_present,
            "mtime": 1234567890.0,
            "fingerprint": "def456",
        },
        "chain_log": {
            "path": "/fake/chain.log",
            "present": False,
            "mtime": 0.0,
        },
        "active_step_heartbeat": {
            "active": False,
            "phase": "",
        },
        "stale_evidence": [],
    }


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
    assert classification.is_mechanical is False
    assert classification.should_block is True
    assert classification.session == session
    assert classification.current_plan == current_plan
    assert classification.needs_human_payload is not None
    assert classification.needs_human_payload["summary"] == "repair exhausted — awaiting human"
    assert any("references current plan" in r for r in classification.rationale)
    assert any("current-target proof" in r for r in classification.rationale)


def test_classify_true_blocker_requires_current_target_proof(
    marker_fixture: dict[str, Path],
) -> None:
    """Without current-target proof, a plan-ref match alone is AMBIGUOUS, not TRUE_BLOCKER."""
    session = "no-proof-session"
    current_plan = "m2-current-plan"

    # Preloaded resolver lacking authoritative source and live evidence
    resolver_no_proof = {
        "schema_version": 1,
        "session": session,
        "authoritative_source": "resolver_observe_disabled",
        "current_refs": {"current_plan_name": current_plan},
        "needs_human": {
            "path": "/fake/path",
            "present": True,
            "plan_refs": [current_plan],
        },
        "plan_state": {"present": False},
        "chain_state": {"present": False},
        "chain_log": {"present": False},
        "active_step_heartbeat": {"active": False},
        "stale_evidence": [],
    }

    classification = classify_needs_human_blocker(
        session,
        current_plan=current_plan,
        marker_dir=marker_fixture["marker_dir"],
        needs_human_payload={
            "summary": "repair exhausted",
            "plan_name": current_plan,
        },
        resolver_record=resolver_no_proof,
    )

    assert classification.verdict == BlockerVerdict.AMBIGUOUS_BLOCKER
    assert classification.is_ambiguous is True
    assert classification.is_true_blocker is False
    assert any("lacks current-target proof" in r for r in classification.rationale)


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

    preloaded_resolver = _current_target_proof_resolver(
        session, current_plan, authoritative_source="chain_state"
    )

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


# ---------------------------------------------------------------------------
# Mechanical blocker tests
# ---------------------------------------------------------------------------


def test_classify_mechanical_blocker_from_summary_keyword(
    marker_fixture: dict[str, Path],
) -> None:
    """A needs-human with mechanical/liveness keywords classifies as MECHANICAL_BLOCKER."""
    session = "mech-session"
    current_plan = "m2-current-plan"

    preloaded_payload = {
        "summary": "mechanical_launch failure — rate-limit exceeded",
        "plan_name": current_plan,
        "current_plan_name": current_plan,
    }

    preloaded_resolver = _current_target_proof_resolver(session, current_plan)

    classification = classify_needs_human_blocker(
        session,
        current_plan=current_plan,
        marker_dir=marker_fixture["marker_dir"],
        needs_human_payload=preloaded_payload,
        resolver_record=preloaded_resolver,
    )

    assert classification.verdict == BlockerVerdict.MECHANICAL_BLOCKER
    assert classification.is_mechanical is True
    assert classification.is_true_blocker is False
    assert classification.should_block is True
    assert any("mechanical/liveness gate" in r for r in classification.rationale)


def test_classify_mechanical_blocker_from_liveness_timeout(
    marker_fixture: dict[str, Path],
) -> None:
    """A liveness timeout without human-gate keywords → MECHANICAL_BLOCKER."""
    session = "liveness-session"
    current_plan = "m2-current-plan"

    preloaded_payload = {
        "summary": "liveness timeout after 3 retries — tool crash",
        "plan_name": current_plan,
        "current_plan_name": current_plan,
    }

    preloaded_resolver = _current_target_proof_resolver(session, current_plan)

    classification = classify_needs_human_blocker(
        session,
        current_plan=current_plan,
        marker_dir=marker_fixture["marker_dir"],
        needs_human_payload=preloaded_payload,
        resolver_record=preloaded_resolver,
    )

    assert classification.verdict == BlockerVerdict.MECHANICAL_BLOCKER
    assert classification.is_mechanical is True


def test_classify_true_blocker_overrides_mechanical_when_human_gate_present(
    marker_fixture: dict[str, Path],
) -> None:
    """Human-gate keywords in summary override mechanical indicators → TRUE_BLOCKER."""
    session = "mixed-session"
    current_plan = "m2-current-plan"

    # Has "mechanical" but also "needs review" → human gate indicator takes precedence
    preloaded_payload = {
        "summary": "mechanical failure — needs review by human operator",
        "plan_name": current_plan,
        "current_plan_name": current_plan,
    }

    preloaded_resolver = _current_target_proof_resolver(session, current_plan)

    classification = classify_needs_human_blocker(
        session,
        current_plan=current_plan,
        marker_dir=marker_fixture["marker_dir"],
        needs_human_payload=preloaded_payload,
        resolver_record=preloaded_resolver,
    )

    assert classification.verdict == BlockerVerdict.TRUE_BLOCKER
    assert classification.is_true_blocker is True
    assert classification.is_mechanical is False


def test_classify_mechanical_blocker_from_active_step_heartbeat(
    marker_fixture: dict[str, Path],
) -> None:
    """Active step heartbeat with no human-gate summary → MECHANICAL_BLOCKER."""
    session = "heartbeat-session"
    current_plan = "m2-current-plan"

    preloaded_payload = {
        "summary": "repair in progress",
        "plan_name": current_plan,
        "current_plan_name": current_plan,
    }

    preloaded_resolver = {
        "schema_version": 1,
        "session": session,
        "authoritative_source": "plan_state",
        "current_refs": {"current_plan_name": current_plan},
        "needs_human": {
            "path": "/fake/path",
            "present": True,
            "plan_refs": [current_plan],
        },
        "plan_state": {"present": True, "mtime": 1234567890.0},
        "chain_state": {"present": False, "mtime": 0.0},
        "chain_log": {"present": False},
        "active_step_heartbeat": {
            "active": True,
            "phase": "repairing",
            "attempt": 1,
            "worker_pid": "12345",
            "started_at": "2026-07-01T00:00:00Z",
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

    assert classification.verdict == BlockerVerdict.MECHANICAL_BLOCKER
    assert classification.is_mechanical is True


def test_classify_mechanical_from_purely_mechanical_iterations(
    marker_fixture: dict[str, Path],
) -> None:
    """Iterations with only mechanical failures and no human-gate diagnosis → MECHANICAL_BLOCKER."""
    session = "iter-mech-session"
    current_plan = "m2-current-plan"

    preloaded_payload = {
        "summary": "repair exhausted after 3 iterations",
        "plan_name": current_plan,
        "current_plan_name": current_plan,
        "iterations": [
            {
                "i": 1,
                "dev_model": "gpt-5.5",
                "mechanical_launch": "failed:rate-limit",
                "kimi_launch": "failed:bad-creds",
                "why": "tool failure",
                "kimi_diagnosis": "crash in repair worker",
            },
            {
                "i": 2,
                "dev_model": "gpt-5.5",
                "mechanical_launch": "timeout",
                "kimi_launch": "n/a",
                "why": "liveness timeout",
            },
        ],
    }

    preloaded_resolver = _current_target_proof_resolver(session, current_plan)

    classification = classify_needs_human_blocker(
        session,
        current_plan=current_plan,
        marker_dir=marker_fixture["marker_dir"],
        needs_human_payload=preloaded_payload,
        resolver_record=preloaded_resolver,
    )

    assert classification.verdict == BlockerVerdict.MECHANICAL_BLOCKER
    assert classification.is_mechanical is True


# ---------------------------------------------------------------------------
# Marker / pointer tests
# ---------------------------------------------------------------------------


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
    assert marker["discord_status"] == "queued"

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
                "why": "Authorization: Bearer bearer...ue",
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


def test_build_needs_human_marker_includes_discord_status_as_metadata(
    tmp_path: Path,
) -> None:
    """Discord delivery status is recorded as metadata in the marker, not as proof."""
    data_path = tmp_path / "repair-data.json"
    repair_payload = {
        "session": "ds-session",
        "workspace": "/tmp/workspace",
        "plan_name": "m1-plan",
        "iterations": [],
    }
    marker = build_needs_human_marker(
        repair_payload,
        repair_data_path=data_path,
        discord_status="delivered",
        recorded_at="2026-07-01T00:00:00+00:00",
    )
    assert marker["discord_status"] == "delivered"
    # The Discord status is metadata — the current pointer is separate
    assert "current" in marker
    assert isinstance(marker["current"], dict)


def test_marker_build_with_failed_discord_status(
    tmp_path: Path,
) -> None:
    """Failed Discord delivery is still recorded as metadata only."""
    data_path = tmp_path / "repair-data.json"
    repair_payload = {
        "session": "fail-session",
        "workspace": "/tmp/workspace",
        "plan_name": "m1-plan",
        "iterations": [],
    }
    marker = build_needs_human_marker(
        repair_payload,
        repair_data_path=data_path,
        discord_status="failed:webhook-timeout",
        recorded_at="2026-07-01T00:00:00+00:00",
    )
    assert marker["discord_status"] == "failed:webhook-timeout"


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


def test_ledger_classification_includes_discord_metadata(tmp_path: Path) -> None:
    """Ledger records include Discord delivery status as metadata."""
    sidecar_dir = tmp_path / "sidecars"
    writer = EscalationLedgerWriter()
    writer.enable(sidecar_dir)

    classification = HumanBlockerClassification(
        verdict=BlockerVerdict.TRUE_BLOCKER,
        session="ds-session",
        current_plan="m1-plan",
        needs_human_path="/fake/path/needs-human.json",
        rationale=("references current plan",),
        resolver_record={
            "stale_evidence": [],
            "authoritative_source": "chain_state",
            "plan_state": {"mtime": 1234567890.0},
            "chain_state": {"mtime": 1234567890.0},
        },
        needs_human_payload={
            "summary": "test",
            "discord_status": "delivered",
        },
    )

    result = writer.write_classification(classification)
    assert result is not None

    records = read_jsonl_records(result)
    assert len(records) == 1
    record = records[0]
    assert record["discord_status"] == "delivered"
    assert record["authoritative_source"] == "chain_state"
    assert record["plan_state_mtime"] == 1234567890.0
    assert record["chain_state_mtime"] == 1234567890.0


def test_ledger_classification_with_failed_discord_status(tmp_path: Path) -> None:
    """Failed Discord delivery is recorded as metadata, not treated as success blocker."""
    sidecar_dir = tmp_path / "sidecars"
    writer = EscalationLedgerWriter()
    writer.enable(sidecar_dir)

    classification = HumanBlockerClassification(
        verdict=BlockerVerdict.AMBIGUOUS_BLOCKER,
        session="fail-session",
        current_plan="m1-plan",
        needs_human_payload={
            "summary": "needs human",
            "discord_status": "failed:webhook-timeout",
        },
        resolver_record={"stale_evidence": []},
    )

    result = writer.write_classification(classification)
    assert result is not None

    records = read_jsonl_records(result)
    assert len(records) == 1
    record = records[0]
    assert record["discord_status"] == "failed:webhook-timeout"
    # Failed Discord does not change the verdict
    assert record["verdict"] == "AMBIGUOUS_BLOCKER"


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


def test_ledger_multiple_verdicts_including_mechanical(tmp_path: Path) -> None:
    """Ledger correctly records MECHANICAL_BLOCKER alongside other verdicts."""
    sidecar_dir = tmp_path / "sidecars"
    writer = EscalationLedgerWriter()
    writer.enable(sidecar_dir)

    for verdict in BlockerVerdict:
        classification = HumanBlockerClassification(
            verdict=verdict,
            session="cover-session",
            current_plan="m1-plan",
        )
        writer.write_classification(classification)

    from arnold_pipelines.megaplan.cloud.repair_contract import _sidecar_jsonl_path

    all_records = read_jsonl_records(_sidecar_jsonl_path(sidecar_dir, "incidents"))
    verdicts = [r["verdict"] for r in all_records if r.get("kind") == "blocker_classified"]
    assert "TRUE_BLOCKER" in verdicts
    assert "STALE_MISMATCH" in verdicts
    assert "AMBIGUOUS_BLOCKER" in verdicts
    assert "MECHANICAL_BLOCKER" in verdicts


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
    mechanical = HumanBlockerClassification(
        verdict=BlockerVerdict.MECHANICAL_BLOCKER,
        session="s",
        current_plan="p",
    )

    assert true_blocker.should_block is True
    assert stale.should_block is False
    assert ambiguous.should_block is True
    assert mechanical.should_block is True


def test_is_mechanical_property() -> None:
    """is_mechanical is True only for MECHANICAL_BLOCKER verdict."""
    mech = HumanBlockerClassification(
        verdict=BlockerVerdict.MECHANICAL_BLOCKER,
        session="s",
        current_plan="p",
    )
    true_b = HumanBlockerClassification(
        verdict=BlockerVerdict.TRUE_BLOCKER,
        session="s",
        current_plan="p",
    )

    assert mech.is_mechanical is True
    assert mech.is_true_blocker is False
    assert true_b.is_mechanical is False
    assert true_b.is_true_blocker is True
