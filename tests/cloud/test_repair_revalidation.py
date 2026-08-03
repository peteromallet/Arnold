from arnold_pipelines.megaplan.cloud.repair_revalidation import revalidate_repair_target
from tests.cloud.repair_identity_fixtures import repair_identity


def _target(*, state="critiqued", cursor=10, pid="101", pid_live=True, tmux=True):
    return {
        "target_id": "session:plan",
        "plan_state": {"current_state": state, "fingerprint": f"plan-{state}"},
        "chain_state": {
            "current_plan_name": "plan",
            "last_state": state,
            "fingerprint": f"chain-{state}",
        },
        "event_cursors": {"line_count": cursor, "mtime": float(cursor)},
        "active_step_heartbeat": {
            "active": pid_live,
            "phase": "finalize",
            "attempt": 1,
            "worker_pid": pid,
            "pid_live": pid_live,
        },
        "tmux_process": {"session_live": tmux, "live_status": "alive" if tmux else "stopped"},
    }


def _identity(*, attempt_number: int = 1, fence_token: str = "fence-1") -> dict[str, object]:
    return repair_identity(
        session="demo",
        plan="plan",
        failure_kind="quality_gate_blocked",
        phase="finalize",
        task="T24",
        attempt=attempt_number,
        plan_revision="sha256:plan-rev-1",
        fence_token=attempt_number,
        coordinator_attempt_id=f"coordinator:{attempt_number}",
        custody_epoch=attempt_number,
    )


def test_stale_pre_gate_evidence_is_superseded_by_current_finalize_target() -> None:
    result = revalidate_repair_target(
        _target(state="critiqued", cursor=10, pid="100"),
        _target(state="gated", cursor=20, pid="200"),
        session_health="alive",
    )
    assert result.superseded is True
    assert "plan_state.current_state" in result.changed_fields
    assert "event_cursors.line_count" in result.changed_fields
    assert result.recovery_verified is True


def test_dead_finalize_worker_is_not_recovered_by_live_tmux_or_stale_activity() -> None:
    before = _target(state="gated", cursor=20, pid="200", pid_live=False)
    result = revalidate_repair_target(before, before, session_health="alive")
    assert result.runner_live is True
    assert result.active_worker_live is False
    assert result.progress_observed is False
    assert result.recovery_verified is False
    assert "active worker is dead" in result.reason


def test_unrelated_process_cannot_supply_recovery_liveness() -> None:
    before = _target(state="gated", cursor=20, pid="200", pid_live=False, tmux=False)
    after = dict(before)
    after["unrelated_processes"] = [{"pid": 999, "cmdline": "pytest tests/cloud"}]
    result = revalidate_repair_target(before, after, session_health="stopped")
    assert result.runner_live is False
    assert result.recovery_verified is False


def test_mismatched_repair_identity_quarantines_receipt() -> None:
    before = _target()
    after = _target()
    before["repair_identity"] = _identity(attempt_number=1, fence_token="fence-1")
    after["repair_identity"] = _identity(attempt_number=2, fence_token="fence-2")

    result = revalidate_repair_target(before, after, session_health="alive")

    assert result.repair_receipt_quarantined is True
    assert result.recovery_verified is False
    assert result.superseded is True
    assert "identity" in result.reason


def test_missing_repair_identity_quarantines_receipt() -> None:
    before = _target()
    after = _target()
    before["repair_identity"] = _identity(attempt_number=1, fence_token="fence-1")

    result = revalidate_repair_target(before, after, session_health="alive")

    assert result.repair_receipt_quarantined is True
    assert result.recovery_verified is False
    assert result.superseded is True


# ═══════════════════════════════════════════════════════════════════════════
# T23 / Step 36-37 — Latency ledger from durable occurrence events
# ═══════════════════════════════════════════════════════════════════════════


def test_latency_ledger_uses_durable_occurrence_events():
    """Latency ledger is generated from durable events and terminal receipts."""

    from arnold_pipelines.megaplan.cloud.repair_revalidation import (
        LatencyLedgerRow,
        RecoveryLatencyLedger,
        generate_latency_ledger,
    )

    # ── Build rows directly ─────────────────────────────────────────
    row = LatencyLedgerRow.from_event_and_receipt(
        occurrence_fingerprint="sha256:test-fp-1",
        durable_event_kind="blocked_occurrence",
        durable_event_timestamp="2026-07-28T10:00:00+00:00",
        terminal_receipt_kind="accepted_repair",
        terminal_receipt_timestamp="2026-07-28T10:03:00+00:00",
        terminal_receipt_id="sha256:receipt-1",
    )
    assert row.cohort_eligible is True
    assert row.latency_seconds == 180.0  # 3 minutes
    assert row.durable_event_kind == "blocked_occurrence"

    # ── Ineligible: no RA grant ─────────────────────────────────────
    row_no_ra = LatencyLedgerRow.from_event_and_receipt(
        occurrence_fingerprint="sha256:test-fp-2",
        durable_event_kind="process_exit",
        durable_event_timestamp="2026-07-28T10:00:00+00:00",
        terminal_receipt_kind="typed_escalation",
        terminal_receipt_timestamp="2026-07-28T10:05:00+00:00",
        terminal_receipt_id="sha256:receipt-2",
        has_current_ra_grant=False,
    )
    assert row_no_ra.cohort_eligible is False
    assert "no current Run Authority" in row_no_ra.eligibility_reason

    # ── Ineligible: no custody lease ────────────────────────────────
    row_no_custody = LatencyLedgerRow.from_event_and_receipt(
        occurrence_fingerprint="sha256:test-fp-3",
        durable_event_kind="blocked_occurrence",
        durable_event_timestamp="2026-07-28T10:00:00+00:00",
        terminal_receipt_kind="accepted_repair",
        terminal_receipt_timestamp="2026-07-28T10:10:00+00:00",
        terminal_receipt_id="sha256:receipt-3",
        has_current_custody_lease=False,
    )
    assert row_no_custody.cohort_eligible is False
    assert "no current Custody" in row_no_custody.eligibility_reason

    # ── Ineligible: no verifier receipts ────────────────────────────
    row_no_verifier = LatencyLedgerRow.from_event_and_receipt(
        occurrence_fingerprint="sha256:test-fp-4",
        durable_event_kind="blocked_occurrence",
        durable_event_timestamp="2026-07-28T10:00:00+00:00",
        terminal_receipt_kind="accepted_repair",
        terminal_receipt_timestamp="2026-07-28T10:02:00+00:00",
        terminal_receipt_id="sha256:receipt-4",
        has_verifier_receipts=False,
    )
    assert row_no_verifier.cohort_eligible is False
    assert "missing same-occurrence verifier receipts" in row_no_verifier.eligibility_reason

    # ── Build a ledger with 20+ eligible rows ───────────────────────
    rows: list[LatencyLedgerRow] = []
    for i in range(25):
        latency = 60.0 + (i * 10.0)  # 60, 70, 80, ..., 300
        r = LatencyLedgerRow(
            occurrence_fingerprint=f"sha256:fp-bulk-{i}",
            durable_event_kind="blocked_occurrence",
            durable_event_timestamp="2026-07-28T10:00:00+00:00",
            terminal_receipt_kind="accepted_repair",
            terminal_receipt_timestamp=f"2026-07-28T10:0{int(latency // 60):02d}:00+00:00",
            terminal_receipt_id=f"sha256:rec-bulk-{i}",
            latency_seconds=latency,
            cohort_eligible=True,
            eligibility_reason="eligible",
        )
        rows.append(r)

    ledger = RecoveryLatencyLedger(rows=tuple(rows))
    assert ledger.sample_count == 25
    assert ledger.sample_count >= 20

    p95 = ledger.p95_seconds
    assert p95 is not None
    # nearest-rank ceil(0.95 * 25) = ceil(23.75) = 24
    # 24th value in sorted ascending (1-indexed): index 23 (0-indexed)
    # latencies: 60,70,...,290,300 -> sorted ascending: same order
    # 24th element (1-indexed) = value at index 23 = 60 + 23*10 = 290
    assert p95 == 290.0

    # With p95=290 < 300, SLO is met (sample_count >= 20)
    assert ledger.slo_met is True

    # ── Ledger with insufficient sample ─────────────────────────────
    small_ledger = RecoveryLatencyLedger(rows=tuple(rows[:5]))
    assert small_ledger.sample_count == 5
    assert small_ledger.slo_met is False  # sample_count < 20

    # ── Generate from raw events/receipts ───────────────────────────
    events = [
        {
            "occurrence_fingerprint": "sha256:fp-evt-1",
            "kind": "blocked_occurrence",
            "timestamp": "2026-07-28T10:00:00+00:00",
            "has_current_ra_grant": True,
            "has_current_custody_lease": True,
            "has_verifier_receipts": True,
        },
        {
            "occurrence_fingerprint": "sha256:fp-evt-2",
            "kind": "process_exit",
            "timestamp": "2026-07-28T10:05:00+00:00",
            "has_current_ra_grant": False,
            "has_current_custody_lease": True,
            "has_verifier_receipts": True,
        },
    ]
    receipts = [
        {
            "occurrence_fingerprint": "sha256:fp-evt-1",
            "kind": "accepted_repair",
            "emitted_at": "2026-07-28T10:02:00+00:00",
            "receipt_id": "sha256:rec-evt-1",
        },
        {
            "occurrence_fingerprint": "sha256:fp-evt-2",
            "kind": "typed_escalation",
            "emitted_at": "2026-07-28T10:10:00+00:00",
            "receipt_id": "sha256:rec-evt-2",
        },
    ]
    generated = generate_latency_ledger(events=events, receipts=receipts)
    assert generated.sample_count == 1  # Only fp-evt-1 is eligible (fp-evt-2 has no RA grant)
    assert generated.total_rows == 2

    # ── Empty ledger ────────────────────────────────────────────────
    empty = generate_latency_ledger()
    assert empty.sample_count == 0
    assert empty.p95_seconds is None
    assert empty.slo_met is False

    # ── to_dict / write round-trip ──────────────────────────────────
    d = ledger.to_dict()
    assert d["schema_version"] == 1
    assert d["milestone"] == "M11"
    assert d["sample_count"] == 25
    assert d["p95_seconds"] == 290.0
    assert d["slo_met"] is True
    assert d["minimum_cohort_size"] == 20
    assert len(d["latency_ledger_rows"]) == 25


# ═══════════════════════════════════════════════════════════════════════════
# T45 / Steps 92-94 — Recovery SLO proof with closed-routes gate
# ═══════════════════════════════════════════════════════════════════════════


def _make_eligible_rows(count: int, *, base_latency: float = 60.0, step: float = 8.0):
    """Build ``count`` cohort-eligible latency rows for SLO tests."""
    from arnold_pipelines.megaplan.cloud.repair_revalidation import LatencyLedgerRow

    rows = []
    for i in range(count):
        latency = base_latency + (i * step)
        rows.append(
            LatencyLedgerRow(
                occurrence_fingerprint=f"sha256:slo-fp-{i}",
                durable_event_kind="blocked_occurrence",
                durable_event_timestamp="2026-07-28T10:00:00+00:00",
                terminal_receipt_kind="accepted_repair",
                terminal_receipt_timestamp="2026-07-28T10:03:00+00:00",
                terminal_receipt_id=f"sha256:slo-rec-{i}",
                latency_seconds=latency,
                cohort_eligible=True,
                eligibility_reason="eligible",
            )
        )
    return rows


_CLOSED_ROUTES = {
    "closure_complete": True,
    "unplanned_count": 0,
    "planned_pending_count": 0,
}


_OPEN_ROUTES_UNPLANNED = {
    "closure_complete": False,
    "unplanned_count": 2,
    "planned_pending_count": 0,
}


_OPEN_ROUTES_PLANNED_PENDING = {
    "closure_complete": False,
    "unplanned_count": 0,
    "planned_pending_count": 1,
}


def test_recovery_slo_requires_eligible_cohort_and_closed_routes():
    """Step 93-94: SLO proof requires closed routes AND eligible cohort."""
    from arnold_pipelines.megaplan.cloud.repair_revalidation import (
        RECOVERY_SLO_BLOCKER_KINDS,
        LatencyLedgerRow,
        RecoveryLatencyLedger,
        RecoverySloBlocker,
        RecoverySloProof,
        compute_recovery_slo_proof,
    )

    # ── Closed blocker vocabulary is closed (no freeform strings) ────
    assert RECOVERY_SLO_BLOCKER_KINDS == frozenset({
        "route_closure_pending",
        "insufficient_cohort",
        "p95_exceeds_threshold",
    })

    # ── Ineligible rows are excluded from cohort ─────────────────────
    ineligible_rows = [
        LatencyLedgerRow(
            occurrence_fingerprint=f"sha256:ineligible-{i}",
            durable_event_kind="blocked_occurrence",
            durable_event_timestamp="2026-07-28T10:00:00+00:00",
            terminal_receipt_kind="accepted_repair",
            terminal_receipt_timestamp="2026-07-28T10:01:00+00:00",
            terminal_receipt_id=f"sha256:ineligible-rec-{i}",
            latency_seconds=30.0,
            cohort_eligible=False,
            eligibility_reason="no current Run Authority grant/fence",
        )
        for i in range(30)
    ]
    ineligible_ledger = RecoveryLatencyLedger(rows=tuple(ineligible_rows))
    assert ineligible_ledger.sample_count == 0  # none eligible

    # Ineligible cohort with closed routes → insufficient_cohort blocker
    proof_ineligible = compute_recovery_slo_proof(
        ineligible_ledger, route_closure=_CLOSED_ROUTES
    )
    assert proof_ineligible.routes_closed is True
    assert proof_ineligible.sample_count == 0
    assert proof_ineligible.slo_met is False
    assert "insufficient_cohort" in proof_ineligible.blocker_kinds()
    assert proof_ineligible.has_typed_blocker is True

    # ── Routes not closed blocks the SLO regardless of cohort ────────
    good_ledger = RecoveryLatencyLedger(rows=tuple(_make_eligible_rows(25)))
    assert good_ledger.sample_count == 25

    proof_unplanned = compute_recovery_slo_proof(
        good_ledger, route_closure=_OPEN_ROUTES_UNPLANNED
    )
    assert proof_unplanned.routes_closed is False
    assert proof_unplanned.slo_met is False
    assert "route_closure_pending" in proof_unplanned.blocker_kinds()

    proof_pending = compute_recovery_slo_proof(
        good_ledger, route_closure=_OPEN_ROUTES_PLANNED_PENDING
    )
    assert proof_pending.routes_closed is False
    assert proof_pending.slo_met is False
    assert "route_closure_pending" in proof_pending.blocker_kinds()

    # ── No route_closure provided → also blocks ──────────────────────
    proof_no_closure = compute_recovery_slo_proof(good_ledger)
    assert proof_no_closure.routes_closed is False
    assert proof_no_closure.slo_met is False
    assert "route_closure_pending" in proof_no_closure.blocker_kinds()

    # ── Sufficient cohort + closed routes + p95 < 300 → slo_met ──────
    proof_good = compute_recovery_slo_proof(
        good_ledger, route_closure=_CLOSED_ROUTES
    )
    assert proof_good.routes_closed is True
    assert proof_good.sample_count == 25
    assert proof_good.p95_seconds is not None
    assert proof_good.p95_seconds < 300.0
    assert proof_good.slo_met is True
    assert proof_good.has_typed_blocker is False
    assert proof_good.blockers == ()

    # ── RecoverySloProof is a frozen dataclass ───────────────────────
    assert isinstance(proof_good, RecoverySloProof)
    d = proof_good.to_dict()
    assert d["schema_version"] == 1
    assert d["milestone"] == "M11"
    assert d["routes_closed"] is True
    assert d["slo_met"] is True
    assert d["blockers"] == []

    # ── Unknown blocker kind is rejected at construction ─────────────
    try:
        RecoverySloBlocker(blocker_kind="bogus", detail="x")
        raise AssertionError("should have raised ValueError")
    except ValueError:
        pass


def test_recovery_slo_nearest_rank_p95_under_300_seconds():
    """Step 94: nearest-rank p95 is computed correctly and gated at <300s."""
    from arnold_pipelines.megaplan.cloud.repair_revalidation import (
        LatencyLedgerRow,
        RecoveryLatencyLedger,
        compute_recovery_slo_proof,
    )
    import math

    # ── 25 eligible rows with latencies 60, 68, 76, ..., 252 ─────────
    rows_good = _make_eligible_rows(25, base_latency=60.0, step=8.0)
    ledger_good = RecoveryLatencyLedger(rows=tuple(rows_good))
    assert ledger_good.sample_count == 25

    # nearest-rank p95: ceil(0.95 * 25) = 24th value (1-indexed)
    rank = math.ceil(0.95 * 25)
    assert rank == 24
    sorted_latencies = sorted(r.latency_seconds for r in rows_good)
    expected_p95 = sorted_latencies[rank - 1]  # 24th value, 0-indexed = 23
    assert expected_p95 < 300.0

    p95 = ledger_good.p95_seconds
    assert p95 is not None
    assert p95 == expected_p95
    assert p95 < 300.0

    proof_good = compute_recovery_slo_proof(
        ledger_good, route_closure=_CLOSED_ROUTES
    )
    assert proof_good.p95_seconds == expected_p95
    assert proof_good.slo_met is True

    # ── Exactly 20 eligible rows (minimum cohort boundary) ───────────
    rows_min = _make_eligible_rows(20, base_latency=60.0, step=10.0)
    ledger_min = RecoveryLatencyLedger(rows=tuple(rows_min))
    assert ledger_min.sample_count == 20
    # ceil(0.95 * 20) = ceil(19.0) = 19th value
    sorted_min = sorted(r.latency_seconds for r in rows_min)
    p95_min = sorted_min[19 - 1]
    assert ledger_min.p95_seconds == p95_min
    assert p95_min < 300.0  # 60 + 18*10 = 240

    proof_min = compute_recovery_slo_proof(
        ledger_min, route_closure=_CLOSED_ROUTES
    )
    assert proof_min.sample_count == 20
    assert proof_min.slo_met is True

    # ── 19 eligible rows → insufficient cohort ───────────────────────
    rows_short = _make_eligible_rows(19, base_latency=60.0, step=8.0)
    ledger_short = RecoveryLatencyLedger(rows=tuple(rows_short))
    assert ledger_short.sample_count == 19

    proof_short = compute_recovery_slo_proof(
        ledger_short, route_closure=_CLOSED_ROUTES
    )
    assert proof_short.slo_met is False
    assert "insufficient_cohort" in proof_short.blocker_kinds()

    # ── p95 >= 300 emits p95_exceeds_threshold ───────────────────────
    rows_slow: list[LatencyLedgerRow] = []
    for i in range(25):
        # All latencies >= 300 → p95 will be >= 300
        latency = 300.0 + (i * 5.0)  # 300, 305, ..., 420
        rows_slow.append(
            LatencyLedgerRow(
                occurrence_fingerprint=f"sha256:slow-fp-{i}",
                durable_event_kind="blocked_occurrence",
                durable_event_timestamp="2026-07-28T10:00:00+00:00",
                terminal_receipt_kind="accepted_repair",
                terminal_receipt_timestamp="2026-07-28T10:06:00+00:00",
                terminal_receipt_id=f"sha256:slow-rec-{i}",
                latency_seconds=latency,
                cohort_eligible=True,
                eligibility_reason="eligible",
            )
        )
    ledger_slow = RecoveryLatencyLedger(rows=tuple(rows_slow))
    assert ledger_slow.sample_count == 25
    assert ledger_slow.p95_seconds is not None
    assert ledger_slow.p95_seconds >= 300.0

    proof_slow = compute_recovery_slo_proof(
        ledger_slow, route_closure=_CLOSED_ROUTES
    )
    assert proof_slow.routes_closed is True
    assert proof_slow.sample_count == 25
    assert proof_slow.p95_seconds >= 300.0
    assert proof_slow.slo_met is False
    assert "p95_exceeds_threshold" in proof_slow.blocker_kinds()
