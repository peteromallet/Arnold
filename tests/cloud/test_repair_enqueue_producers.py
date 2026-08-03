"""Tests for occurrence-bound enqueue producers (Step 39 / T25).

Covers:
* Lifecycle failure enqueue binds exact occurrence identity (F01 tuple).
* Supervised-run-exhausted enqueue binds exact occurrence identity.
* Partial occurrence identity is rejected with zero_authority_rejected.
* Missing occurrence identity is rejected.
* Terminal receipt expectations are carried on the request.
* Evidence cursor digest is carried on the request.
* Legacy callers (without occurrence_identity) continue to work.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.repair_requests import (
    F01_REPAIR_OCCURRENCE_FIELDS,
    build_normalized_repair_identity,
    enqueue_occurrence_bound_repair_request,
    enqueue_repair_request,
    validate_queue_root,
)
from arnold_pipelines.megaplan.custody.contracts import (
    CustodyTargetKey,
)

# ── helpers ─────────────────────────────────────────────────────────────────

_DEFAULT_F01 = {
    "environment": "/workspace/test",
    "session": "test-session",
    "chain": "/workspace/test/chain.yaml",
    "plan_revision": "sha256:test-rev",
    "phase": "execute",
    "task": "T1",
    "attempt": "1",
    "normalized_failure_kind": "blocked_step",
    "blocker_or_phase_result_hash": "sha256:test-blocker",
    "fence": "fence-token-1",
}


def _queue_dir(tmp_path):
    """A valid central queue root shape."""
    root = tmp_path / ".megaplan" / "repair-queue"
    root.mkdir(parents=True, exist_ok=True)
    return str(root)


def _problem_sig(**overrides):
    sig = {
        "failure_kind": "blocked_step",
        "current_state": "blocked",
        "phase_or_step": "execute",
        "milestone_or_plan": "test-plan",
        "gate_recommendation": "",
        "blocked_task_id": "T1",
    }
    sig.update(overrides)
    return sig


def _occurrence_identity(**overrides):
    fields = dict(_DEFAULT_F01)
    fields.update({k: v for k, v in overrides.items() if k in fields})
    try:
        target = CustodyTargetKey(**fields)
    except Exception:
        return fields
    result = build_normalized_repair_identity(
        target=target,
        run_id=str(overrides.get("run_id") or "run-1"),
        run_revision=str(overrides.get("run_revision") or fields["plan_revision"]),
        run_incarnation_id=str(
            overrides.get("run_incarnation_id") or "run-incarnation-1"
        ),
        coordinator_attempt_id=str(
            overrides.get("coordinator_attempt_id") or "coordinator-1"
        ),
        fence_token=int(overrides.get("coordinator_fence_token") or 1),
        wbc_attempt_reference=str(
            overrides.get("wbc_attempt_reference") or "wbc-1"
        ),
        run_authority_grant_id=str(
            overrides.get("run_authority_grant_id") or "grant-1"
        ),
        lease_id=str(overrides.get("lease_id") or "lease-1"),
        custody_epoch=int(overrides.get("custody_epoch") or 1),
    )
    assert result is not None
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Lifecycle + supervise enqueue — occurrence identity binding
# ═══════════════════════════════════════════════════════════════════════════


def test_lifecycle_and_supervise_enqueue_bind_occurrence_identity(tmp_path):
    """Both lifecycle-failure and supervised-run-exhausted requests carry
    the full F01 occurrence identity, evidence cursor digest, source,
    failure kind, and terminal receipt expectations.
    """
    queue_dir = _queue_dir(tmp_path)
    occurrence = _occurrence_identity()

    result = enqueue_occurrence_bound_repair_request(
        queue_root=queue_dir,
        session="test-session",
        problem_signature=_problem_sig(),
        root_cause_hint="test failure",
        source="lifecycle_failure",
        workspace="/workspace/test",
        run_kind="plan",
        target={
            "plan_dir": "/workspace/test/plans/test-plan",
            "plan_name": "test-plan",
        },
        occurrence_identity=occurrence,
        evidence_cursor_digest="sha256:test-cursor-digest",
        terminal_receipt_expectations=["five_minute", "one_hour", "next_three_hour"],
    )

    # Must be queued (accepted).
    assert result["status"] == "queued", f"Expected queued, got {result.get('status')}"

    request = result["request"]
    assert isinstance(request, dict)

    # Verify repair_identity carries the F01 tuple.
    identity = request.get("repair_identity", {})
    assert isinstance(identity, dict), "repair_identity must be a dict"

    target_identity = identity["occurrence"]["target"]
    for field_name in F01_REPAIR_OCCURRENCE_FIELDS:
        assert field_name in target_identity, (
            f"F01 field {field_name!r} missing from repair_identity"
        )
        assert target_identity[field_name], (
            f"F01 field {field_name!r} is empty in repair_identity"
        )

    assert "evidence_cursor_digest" not in identity
    assert "terminal_receipt_expectations" not in identity

    # Verify source and failure kind in the request record.
    assert request["source"] == "lifecycle_failure"
    ps = request.get("problem_signature", {})
    assert ps.get("failure_kind") == "blocked_step"


def test_supervise_source_binds_occurrence_identity(tmp_path):
    """Supervised-run-exhausted source carries the full F01 tuple."""
    queue_dir = _queue_dir(tmp_path)
    occurrence = _occurrence_identity(
        normalized_failure_kind="supervised_run_exhausted",
        phase="arnold-supervise",
        task="supervisor-process",
    )

    result = enqueue_occurrence_bound_repair_request(
        queue_root=queue_dir,
        session="chain-session",
        problem_signature=_problem_sig(
            failure_kind="supervised_run_exhausted",
            current_state="process_exited",
            phase_or_step="arnold-supervise",
            blocked_task_id="",
        ),
        root_cause_hint={"reason": "process exited", "supervise_log": "/tmp/log"},
        source="arnold_supervise_exit",
        workspace="/workspace/test",
        run_kind="chain",
        occurrence_identity=occurrence,
        evidence_cursor_digest="sha256:supervise-cursor",
        terminal_receipt_expectations=["five_minute", "one_hour", "next_three_hour"],
    )

    assert result["status"] == "queued"

    identity = result["request"].get("repair_identity", {})
    assert identity["occurrence"]["target"]["normalized_failure_kind"] == "supervised_run_exhausted"
    assert identity.get("source") is None  # source is not an F01 field
    assert result["request"]["source"] == "arnold_supervise_exit"


def test_partial_occurrence_identity_is_rejected(tmp_path):
    """A partial F01 tuple (fewer than 10 non-empty fields) is rejected
    with zero_authority_rejected — authority must not be derived from
    a label, liveness signal, WBC receipt, or rebuildable projection.
    """
    queue_dir = _queue_dir(tmp_path)
    # Only 5 of 10 fields non-empty.
    partial = _occurrence_identity(
        environment="",
        chain="",
        plan_revision="",
        fence="",
        task="",
    )

    result = enqueue_occurrence_bound_repair_request(
        queue_root=queue_dir,
        session="test-session",
        problem_signature=_problem_sig(),
        root_cause_hint="test",
        source="lifecycle_failure",
        occurrence_identity=partial,
        evidence_cursor_digest="sha256:test",
    )

    assert result["status"] == "zero_authority_rejected"
    assert result["outcome"] == "zero_authority_rejected"
    evidence = result.get("evidence", {})
    assert "normalized repair identity" in str(evidence.get("reason", ""))


def test_missing_occurrence_identity_is_rejected(tmp_path):
    """When occurrence_identity is None, the request is rejected."""
    queue_dir = _queue_dir(tmp_path)

    result = enqueue_occurrence_bound_repair_request(
        queue_root=queue_dir,
        session="test-session",
        problem_signature=_problem_sig(),
        root_cause_hint="test",
        source="lifecycle_failure",
        occurrence_identity=None,
    )

    assert result["status"] == "zero_authority_rejected"
    assert result["outcome"] == "zero_authority_rejected"


def test_legacy_enqueue_without_occurrence_identity_is_read_only(tmp_path):
    queue_dir = _queue_dir(tmp_path)

    result = enqueue_repair_request(
        queue_root=queue_dir,
        session="legacy-session",
        problem_signature=_problem_sig(failure_kind="legacy_failure"),
        root_cause_hint="legacy test",
        source="legacy_producer",
        workspace="/workspace/legacy",
        run_kind="plan",
        target={
            "plan_dir": "/workspace/legacy/plans/test",
            "plan_name": "test",
        },
        # No repair_identity — legacy path.
    )

    assert result["status"] == "zero_authority_rejected"


def test_f01_fields_are_normalized_on_request_record(tmp_path):
    """Each of the ten F01 fields is individually recognizable in the
    repair_identity block when supplied, and identical inputs produce
    identical normalized outputs.
    """
    queue_dir = _queue_dir(tmp_path)
    occurrence = _occurrence_identity()

    result1 = enqueue_occurrence_bound_repair_request(
        queue_root=queue_dir,
        session="test-session",
        problem_signature=_problem_sig(
            failure_kind="test_failure_A",
            blocked_task_id="T1",
        ),
        root_cause_hint="test A",
        source="test_producer",
        occurrence_identity=occurrence,
        evidence_cursor_digest="sha256:cursor-a",
    )

    result2 = enqueue_occurrence_bound_repair_request(
        queue_root=queue_dir,
        session="test-session",
        problem_signature=_problem_sig(
            failure_kind="test_failure_B",
            blocked_task_id="T2",
        ),
        root_cause_hint="test B",  # different hint → different request
        source="test_producer",
        occurrence_identity=occurrence,
        evidence_cursor_digest="sha256:cursor-a",
    )

    assert result1["status"] == "queued", f"Expected queued, got {result1.get('status')}"
    assert result2["status"] == "queued", f"Expected queued, got {result2.get('status')}"

    id1 = result1["request"]["repair_identity"]
    id2 = result2["request"]["repair_identity"]

    # Same occurrence identity → same normalized F01 fields.
    target1 = id1["occurrence"]["target"]
    target2 = id2["occurrence"]["target"]
    for field_name in F01_REPAIR_OCCURRENCE_FIELDS:
        assert target1.get(field_name) == target2.get(field_name), (
            f"F01 field {field_name!r} differs between identical occurrences"
        )

    assert id1 == id2


def test_terminal_receipt_expectations_default_to_none(tmp_path):
    """When terminal_receipt_expectations is not provided, it is absent
    from the repair_identity block (not defaulted to a guess).
    """
    queue_dir = _queue_dir(tmp_path)
    occurrence = _occurrence_identity()

    result = enqueue_occurrence_bound_repair_request(
        queue_root=queue_dir,
        session="test-session",
        problem_signature=_problem_sig(),
        root_cause_hint="test",
        source="test_producer",
        occurrence_identity=occurrence,
        evidence_cursor_digest="sha256:test",
        # terminal_receipt_expectations not provided
    )

    assert result["status"] == "queued"
    identity = result["request"].get("repair_identity", {})
    assert "terminal_receipt_expectations" not in identity


def test_empty_receipt_expectations_list_not_stored(tmp_path):
    """An empty terminal_receipt_expectations list is not stored."""
    queue_dir = _queue_dir(tmp_path)
    occurrence = _occurrence_identity()

    result = enqueue_occurrence_bound_repair_request(
        queue_root=queue_dir,
        session="test-session",
        problem_signature=_problem_sig(),
        root_cause_hint="test",
        source="test_producer",
        occurrence_identity=occurrence,
        evidence_cursor_digest="sha256:test",
        terminal_receipt_expectations=[],
    )

    assert result["status"] == "queued"
    identity = result["request"].get("repair_identity", {})
    # Empty list is not stored because the normalization checks truthiness.
    assert "terminal_receipt_expectations" not in identity


def test_grant_fence_lease_epoch_carried_when_provided(tmp_path):
    """When occurrence_identity includes grant/fence/lease/epoch fields,
    they are normalized into the repair_identity block.
    """
    queue_dir = _queue_dir(tmp_path)
    occurrence = _occurrence_identity(
        run_authority_grant_id="grant-123",
        coordinator_fence_token=42,
        lease_id="lease-abc",
        custody_epoch=7,
    )

    result = enqueue_occurrence_bound_repair_request(
        queue_root=queue_dir,
        session="test-session",
        problem_signature=_problem_sig(),
        root_cause_hint="test",
        source="test_producer",
        occurrence_identity=occurrence,
        evidence_cursor_digest="sha256:test",
        terminal_receipt_expectations=["five_minute"],
    )

    assert result["status"] == "queued"
    identity = result["request"].get("repair_identity", {})
    assert identity.get("run_authority_grant_id") == "grant-123"
    assert identity["occurrence"]["fence_token"] == 42
    assert identity.get("lease_id") == "lease-abc"
    assert identity.get("custody_epoch") == 7


# ═══════════════════════════════════════════════════════════════════════════
# Step 40 (T26) — Bridge and native human-gate enqueue → occurrence-bound
# ═══════════════════════════════════════════════════════════════════════════


def test_bridge_and_native_human_gate_enqueue_bind_occurrence_identity(tmp_path):
    """Bridge and native human-gate enqueue either binds exact occurrence
    identity (when the full F01 tuple is supplied) or emits typed
    zero-authority rejection with current custody evidence (when the
    identity is missing or incomplete).

    This is the single test for Step 40 (T26): two callers (bridge wiring
    and native HumanGateStep hook) both funnel through
    ``enqueue_human_gate_repair_request``, so exercising that function
    directly with the three canonical scenarios covers both paths.
    """
    from arnold_pipelines.megaplan.cloud.repair_requests import (
        F01_REPAIR_OCCURRENCE_FIELDS,
        enqueue_human_gate_repair_request,
        enqueue_occurrence_bound_repair_request,
    )
    from arnold_pipelines.megaplan.custody.contracts import (
        F01_REPAIR_OCCURRENCE_FIELDS as _F01,
    )

    queue_dir = str(
        tmp_path / ".megaplan" / "repair-queue"
    )
    Path(queue_dir).mkdir(parents=True, exist_ok=True)
    marker_dir = str(tmp_path / "markers")
    Path(marker_dir).mkdir(parents=True, exist_ok=True)

    common_kwargs = dict(
        queue_root=queue_dir,
        marker_dir=marker_dir,
        session="test-session",
        workspace=str(tmp_path),
        run_kind="plan",
        plan_name="test-plan",
        pipeline_name="demo_judges",
        artifact_stage="review",
        step_name="human_gate",
        prompt="Please review the artifact",
    )

    # ── Scenario A: full F01 tuple → occurrence-bound enqueue ──────────
    full_f01 = _occurrence_identity(
        phase="review", task="human_gate", normalized_failure_kind="human_gate"
    )

    result_a = enqueue_human_gate_repair_request(
        **common_kwargs,
        occurrence_identity=full_f01,
        evidence_cursor_digest="sha256:test-cursor",
        terminal_receipt_expectations=["five_minute", "one_hour"],
    )

    assert result_a is not None, "Feature flag is on; result must not be None"
    assert result_a["status"] == "queued", (
        f"Full F01 tuple must produce queued status, got {result_a.get('status')}"
    )
    request = result_a["request"]
    assert request["source"] == "human_gate"
    identity = request.get("repair_identity", {})
    target_identity = identity["occurrence"]["target"]
    for field_name in F01_REPAIR_OCCURRENCE_FIELDS:
        assert field_name in target_identity, (
            f"F01 field {field_name!r} missing from repair_identity"
        )
        assert target_identity[field_name], (
            f"F01 field {field_name!r} is empty in repair_identity"
        )
    assert "evidence_cursor_digest" not in identity
    assert "terminal_receipt_expectations" not in identity

    # ── Scenario B: partial F01 tuple → zero_authority_rejected ────────
    partial_f01 = {
        "environment": "/workspace/test",
        "session": "test-session",
        "chain": "",          # 2 missing
        "plan_revision": "",  # 3 missing
        "phase": "review",
        "task": "human_gate",
        "attempt": "1",
        "normalized_failure_kind": "human_gate",
        "blocker_or_phase_result_hash": "",
        "fence": "",
    }

    result_b = enqueue_human_gate_repair_request(
        **common_kwargs,
        occurrence_identity=partial_f01,
    )

    assert result_b is not None
    assert result_b["status"] == "zero_authority_rejected"
    assert result_b["outcome"] == "zero_authority_rejected"
    evidence = result_b.get("evidence", {})
    assert "normalized run/custody identity" in str(evidence.get("reason", ""))
    # Custody evidence must include the human-gate context.
    assert evidence.get("plan_name") == "test-plan"
    assert evidence.get("pipeline_name") == "demo_judges"
    assert evidence.get("step_name") == "human_gate"

    # ── Scenario C: no occurrence_identity → zero_authority_rejected ───
    result_c = enqueue_human_gate_repair_request(**common_kwargs)

    assert result_c is not None
    assert result_c["status"] == "zero_authority_rejected"
    assert result_c["outcome"] == "zero_authority_rejected"
    evidence_c = result_c.get("evidence", {})
    assert "manual/liveness context cannot become repair authority" in str(
        evidence_c.get("reason", "")
    )
    # Custody evidence must still be present.
    assert evidence_c.get("plan_name") == "test-plan"
    assert evidence_c.get("artifact_stage") == "review"
