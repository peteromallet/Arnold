"""Current terminal recovery verification coverage.

The former shell ``TERMINAL_AUDIT_MODE`` path was retired: it retriggered an
already-terminal repair and could not prove a recovery delta.  Terminal
acceptance now belongs to the separated recovery verifier, which rereads
current authority and joins exact request-bound occurrence evidence.
"""

from __future__ import annotations

from arnold_pipelines.megaplan.cloud.recovery_events import (
    RecoveryEvent,
    RecoveryEventKind,
    RecoveryEventStore,
)
from arnold_pipelines.megaplan.cloud.recovery_verifier import (
    OccurrenceOrder,
    RecoveryVerifier,
    RereadSnapshot,
    VerificationTarget,
    VerificationVerdict,
)
from arnold_pipelines.megaplan.cloud.current_target_liveness import SCHEMA
from arnold_pipelines.megaplan.cloud import terminal_audit


def _snapshot(_request_id: str) -> RereadSnapshot:
    return RereadSnapshot(
        ra_grant_id="grant-1",
        ra_fence_token=7,
        ra_decision="SATISFIED",
        custody_lease_id="lease-1",
        custody_epoch=3,
        custody_owner="repair-owner",
    )


def _target(**overrides: object) -> VerificationTarget:
    values = {
        "repair_request_id": "request-1",
        "expected_occurrence_key": "occurrence-1",
        "expected_grant_id": "grant-1",
        "expected_fence_token": 7,
        "expected_epoch": 3,
        "expected_lease_id": "lease-1",
        "expected_basename": "m10-recovery",
    }
    values.update(overrides)
    return VerificationTarget(**values)


def _complete_store() -> RecoveryEventStore:
    store = RecoveryEventStore()
    rows = (
        (RecoveryEventKind.BLOCKER_DETECTED, "2026-07-28T00:00:00+00:00", "", ""),
        (RecoveryEventKind.REPAIR_REQUEST_ENQUEUED, "2026-07-28T00:00:01+00:00", "", ""),
        (
            RecoveryEventKind.REPAIR_CLAIMED,
            "2026-07-28T00:00:02+00:00",
            "2026-07-28T00:00:02+00:00",
            "",
        ),
        (
            RecoveryEventKind.REPAIR_TERMINAL,
            "2026-07-28T00:00:03+00:00",
            "",
            "2026-07-28T00:00:03+00:00",
        ),
    )
    for index, (kind, recorded_at, claim_time, terminal_time) in enumerate(rows):
        store.record(
            RecoveryEvent(
                event_id=f"event-{index}",
                kind=kind,
                occurred_at="2026-07-28T00:00:00+00:00",
                recorded_at=recorded_at,
                request_id="request-1",
                claim_time=claim_time,
                terminal_time=terminal_time,
            )
        )
    return store


def test_current_recovery_verifier_accepts_exact_independent_proof() -> None:
    result = RecoveryVerifier(
        event_store=_complete_store(),
        ra_reread_fn=_snapshot,
    ).verify(_target())

    assert result.verdict == VerificationVerdict.VERIFIED
    assert result.ordering == OccurrenceOrder.IN_ORDER
    assert len(result.events_joined) == 4


def test_current_recovery_verifier_rejects_stale_identity() -> None:
    result = RecoveryVerifier(
        event_store=_complete_store(),
        ra_reread_fn=lambda _request_id: RereadSnapshot(
            ra_grant_id="stale-grant",
            ra_fence_token=7,
            ra_decision="SATISFIED",
            custody_epoch=3,
        ),
    ).verify(_target())

    assert result.verdict == VerificationVerdict.REJECTED_STALE_IDENTITY
    assert result.is_blocked


def test_current_recovery_verifier_rejects_missing_occurrences() -> None:
    result = RecoveryVerifier(
        event_store=RecoveryEventStore(),
        ra_reread_fn=_snapshot,
    ).verify(_target())

    assert result.verdict == VerificationVerdict.REJECTED_LOST
    assert result.ordering == OccurrenceOrder.LOST


def test_terminal_audit_rejects_arbitrary_repair_loop_bin() -> None:
    """Step 78: terminal audit must reject arbitrary ``--repair-loop-bin`` execution.

    The terminal audit module routes through typed delegation shim.  It must
    never directly subprocess-execute an arbitrary repair-loop binary and treat
    its returncode as accepted repair.  Instead it emits typed rejection or
    delegates through ``delegate_to_simple_fixer``.
    """
    import ast
    from pathlib import Path

    source_path = (
        Path(__file__).resolve().parents[2]
        / "arnold_pipelines"
        / "megaplan"
        / "cloud"
        / "terminal_audit.py"
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Collect all function definitions and their subprocess/exec calls.
    subprocess_calls: list[str] = []

    class _Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute):
                full = f"{ast.unparse(node.func.value)}.{node.func.attr}" if hasattr(ast, 'unparse') else str(node.func.attr)
                if "subprocess" in full or "os.system" in full:
                    subprocess_calls.append(full)
            elif isinstance(node.func, ast.Name):
                if node.func.id in ("exec", "eval"):
                    subprocess_calls.append(node.func.id)
            self.generic_visit(node)

    _Visitor().visit(tree)

    # The terminal_audit module must not contain any direct subprocess.run,
    # subprocess.Popen, subprocess.call, os.system, or exec calls that
    # execute arbitrary repair-loop binaries.
    for call in subprocess_calls:
        assert "subprocess.run" not in call, (
            f"terminal_audit.py must not use {call} — "
            "repair-loop execution must route through typed delegation shim"
        )

    # Must import from the delegation shim.
    assert "from arnold_pipelines.megaplan.cloud.wrappers.repair_delegation import" in source
    assert "build_repair_delegation" in source
    assert "emit_zero_authority_rejection" in source
    assert "delegate_to_simple_fixer" in source

    # The run_terminal_audit function must accept repair_loop_bin as a parameter
    # but never execute it via subprocess.
    run_func_start = source.index("def run_terminal_audit(")
    run_func_end = source.index("\ndef main(", run_func_start)
    run_func = source[run_func_start:run_func_end]

    # Must have delegation code path (not just subprocess execution).
    assert "delegation = build_repair_delegation" in run_func
    assert "emit_zero_authority_rejection" in run_func
    assert "delegate_to_simple_fixer" in run_func

    # The comment must document the delegation intent.
    assert "Route retrigger through typed delegation shim (Step 76-80)" in source
    assert "Terminal audit never directly executes a repair-loop binary" in source


def test_terminal_audit_unknown_liveness_never_delegates(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        terminal_audit,
        "capture_terminal_snapshot",
        lambda _session, _marker_dir: {
            "captured_at": "2026-08-03T18:00:00+00:00",
            "workspace": "/workspace/demo",
            "current_target_liveness": {
                "schema": SCHEMA,
                "state": "unknown",
                "known": False,
            },
        },
    )
    monkeypatch.setattr(
        terminal_audit,
        "delegate_to_simple_fixer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("UNKNOWN liveness delegated a retrigger")
        ),
    )

    record = terminal_audit.run_terminal_audit(
        session="demo",
        repair_loop_bin=tmp_path / "repair-loop",
        marker_dir=tmp_path / "markers",
        repair_data_dir=tmp_path / "repair-data",
    )

    assert record["accepted"] is False
    assert record["command"] == []
    assert "UNKNOWN" in record["post_retrigger_verification"]["rejection_reason"]
