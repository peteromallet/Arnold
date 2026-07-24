"""Progress query tests for healthy, slow-progressing, idle, dead, and
stuck-but-alive classifications across available persistence backends.

Covers ordered event/audit/checkpoint snapshots with realistic timestamped
artifact fixtures and backend parity.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import pytest

from arnold.pipeline.native.persistence import (
    FileNativePersistenceBackend,
    NativePersistenceBackend,
    NativePersistenceScope,
    OrderedPersistenceRow,
    bind_legacy_artifact_root,
)
from arnold.supervisor.progress import (
    ProgressClassification,
    ProgressSignal,
    ProgressSnapshot,
    ProgressUsage,
    ProgressWindows,
    build_progress_snapshot,
    build_progress_snapshot_for_artifact_root,
)


# ── helpers ────────────────────────────────────────────────────────────────


def _utc_ts(offset_seconds: int = 0) -> datetime:
    return datetime(2026, 7, 5, 0, 0, tzinfo=UTC) + timedelta(seconds=offset_seconds)


def _ts_iso(offset_seconds: int = 0) -> str:
    return _utc_ts(offset_seconds).isoformat()


def _event_row(
    kind: str,
    payload: Mapping[str, Any],
    *,
    ts_offset: int = 0,
    sequence: int = 1,
) -> OrderedPersistenceRow:
    return OrderedPersistenceRow(
        sequence=sequence,
        kind=kind,
        payload={
            "ts_utc": _ts_iso(ts_offset),
            "payload": dict(payload),
            "kind": kind,
        },
    )


def _audit_row(
    payload: Mapping[str, Any],
    *,
    sequence: int = 1,
) -> OrderedPersistenceRow:
    return OrderedPersistenceRow(
        sequence=sequence,
        kind="audit",
        payload=dict(payload),
    )


class _StubBackend:
    """In-memory backend that returns controlled event/audit/checkpoint data."""

    def __init__(
        self,
        events: list[OrderedPersistenceRow] | None = None,
        audits: list[OrderedPersistenceRow] | None = None,
        checkpoint: Mapping[str, Any] | None = None,
    ):
        self._events = events or []
        self._audits = audits or []
        self._checkpoint = checkpoint

    def read_events(self, scope: NativePersistenceScope) -> list[OrderedPersistenceRow]:
        return list(self._events)

    def read_audit_records(
        self, scope: NativePersistenceScope
    ) -> list[OrderedPersistenceRow]:
        return list(self._audits)

    def read_trace_artifact(
        self, scope: NativePersistenceScope, *, name: str
    ) -> Any:
        if name == "checkpoint.json" and self._checkpoint is not None:
            return dict(self._checkpoint)
        return None

    # Remaining protocol methods are not exercised by progress queries.
    def write_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def read_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def delete_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def read_state_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def write_composite_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def read_composite_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def delete_composite_resume_cursor(self, *args, **kwargs) -> None:
        pass

    def write_human_gate(self, *args, **kwargs) -> None:
        pass

    def read_human_gate(self, *args, **kwargs) -> None:
        pass

    def delete_human_gate(self, *args, **kwargs) -> None:
        pass

    def resolve_resume_surface(self, *args, **kwargs):
        from arnold.pipeline.native.persistence import ResolvedResumeSurface
        return ResolvedResumeSurface(source="none", kind="none", blocked=False)

    def append_audit_record(self, *args, **kwargs) -> OrderedPersistenceRow:
        return OrderedPersistenceRow(sequence=1, payload={}, kind="audit")

    def emit_event(self, *args, **kwargs) -> OrderedPersistenceRow:
        return OrderedPersistenceRow(sequence=1, payload={}, kind="event")

    def write_trace_artifact(self, *args, **kwargs) -> None:
        pass


_SCOPE = NativePersistenceScope(
    project_id="test-project",
    run_id="test-run",
    artifact_id="test-artifact",
)


def _make_snapshot(
    events: list[OrderedPersistenceRow] | None = None,
    audits: list[OrderedPersistenceRow] | None = None,
    checkpoint: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
    windows: ProgressWindows | None = None,
) -> ProgressSnapshot:
    backend = _StubBackend(events=events, audits=audits, checkpoint=checkpoint)
    return build_progress_snapshot(backend, _SCOPE, now=now, windows=windows)


# ── classification tests ───────────────────────────────────────────────────


class TestHealthyClassification:
    def test_recent_event_and_audit_yields_healthy(self) -> None:
        now = _utc_ts(0)
        events = [_event_row("phase.start", {"path": "/root"}, ts_offset=-60)]
        audits = [
            _audit_row(
                {
                    "attempt_id": "a1",
                    "status": "success",
                    "ended_at": _ts_iso(-30),
                    "run_path": "/root",
                }
            )
        ]
        snap = _make_snapshot(events=events, audits=audits, now=now)
        assert snap.classification is ProgressClassification.HEALTHY
        assert snap.last_signal_at is not None
        assert snap.signal_age is not None
        assert snap.signal_age <= timedelta(minutes=1)

    def test_recent_checkpoint_yields_healthy(self) -> None:
        now = _utc_ts(0)
        events = [_event_row("checkpoint", {}, ts_offset=-60)]
        checkpoint = {
            "status": "completed",
            "run_path": "/root",
            "final": False,
        }
        snap = _make_snapshot(events=events, checkpoint=checkpoint, now=now)
        assert snap.classification is ProgressClassification.HEALTHY


class TestSlowProgressingClassification:
    def test_older_progress_but_recent_signal_yields_slow(self) -> None:
        """Progress is stale but some signal arrived recently."""
        windows = ProgressWindows(
            healthy_progress_window=timedelta(minutes=5),
            slow_signal_window=timedelta(minutes=15),
            stuck_progress_window=timedelta(minutes=30),
            stuck_liveness_window=timedelta(minutes=15),
            idle_signal_window=timedelta(hours=1),
            dead_signal_window=timedelta(hours=2),
        )
        now = _utc_ts(0)
        # Last progress (audit) is 10 minutes ago — beyond healthy window
        audits = [
            _audit_row(
                {
                    "attempt_id": "a1",
                    "status": "success",
                    "ended_at": _ts_iso(-600),
                    "run_path": "/root",
                }
            )
        ]
        # But a recent event arrived 3 minutes ago — within slow window
        events = [
            _event_row(
                "phase.start", {"path": "/root"}, ts_offset=-180
            )
        ]
        snap = _make_snapshot(
            events=events, audits=audits, now=now, windows=windows
        )
        assert snap.classification is ProgressClassification.SLOW_PROGRESSING


class TestIdleClassification:
    def test_stale_progress_past_slow_window_yields_idle(self) -> None:
        windows = ProgressWindows(
            healthy_progress_window=timedelta(minutes=5),
            slow_signal_window=timedelta(minutes=15),
            stuck_progress_window=timedelta(minutes=30),
            stuck_liveness_window=timedelta(minutes=15),
            idle_signal_window=timedelta(hours=1),
            dead_signal_window=timedelta(hours=2),
        )
        now = _utc_ts(0)
        # Signal is 20 minutes old — past slow window, within idle window
        events = [
            _event_row(
                "phase.start", {"path": "/root"}, ts_offset=-1200
            )
        ]
        snap = _make_snapshot(events=events, now=now, windows=windows)
        assert snap.classification is ProgressClassification.IDLE


class TestDeadClassification:
    def test_no_signals_at_all_yields_dead(self) -> None:
        snap = _make_snapshot()
        assert snap.classification is ProgressClassification.DEAD
        assert snap.last_signal_at is None

    def test_signal_past_dead_window_yields_dead(self) -> None:
        windows = ProgressWindows(
            healthy_progress_window=timedelta(minutes=5),
            slow_signal_window=timedelta(minutes=15),
            stuck_progress_window=timedelta(minutes=30),
            stuck_liveness_window=timedelta(minutes=15),
            idle_signal_window=timedelta(hours=1),
            dead_signal_window=timedelta(hours=2),
        )
        now = _utc_ts(0)
        # Signal is 3 hours old — past dead window
        events = [
            _event_row(
                "phase.start", {"path": "/root"}, ts_offset=-10800
            )
        ]
        snap = _make_snapshot(events=events, now=now, windows=windows)
        assert snap.classification is ProgressClassification.DEAD
        assert snap.last_signal_at is not None
        assert snap.signal_age is not None
        assert snap.signal_age > timedelta(hours=2)


class TestStuckButAliveClassification:
    def test_alive_signal_but_no_progress_for_long_yields_stuck(self) -> None:
        """Liveness signal is recent but actual progress is stale."""
        windows = ProgressWindows(
            healthy_progress_window=timedelta(minutes=5),
            slow_signal_window=timedelta(minutes=15),
            stuck_progress_window=timedelta(minutes=30),
            stuck_liveness_window=timedelta(minutes=15),
            idle_signal_window=timedelta(hours=1),
            dead_signal_window=timedelta(hours=2),
        )
        now = _utc_ts(0)
        # Progress (stage complete) is 40 minutes old — past stuck window
        events = [
            _event_row(
                "stage.complete",
                {"stage": "build", "path": "/root"},
                ts_offset=-2400,
                sequence=1,
            ),
            # But liveness signal is 5 minutes ago — within stuck liveness
            _event_row(
                "phase.start",
                {"path": "/root"},
                ts_offset=-300,
                sequence=2,
            ),
        ]
        snap = _make_snapshot(events=events, now=now, windows=windows)
        assert snap.classification is ProgressClassification.STUCK_BUT_ALIVE


# ── snapshot field tests ────────────────────────────────────────────────────


class TestSnapshotFields:
    def test_token_progress_contributes_to_progress_rate_when_metadata_present(self) -> None:
        windows = ProgressWindows(
            healthy_progress_window=timedelta(minutes=5),
            slow_signal_window=timedelta(minutes=15),
            stuck_progress_window=timedelta(minutes=30),
            stuck_liveness_window=timedelta(minutes=15),
            idle_signal_window=timedelta(hours=1),
            dead_signal_window=timedelta(hours=2),
        )
        now = _utc_ts(0)
        events = [
            _event_row(
                "stage.complete",
                {"stage": "draft", "path": "/root"},
                ts_offset=-2400,
                sequence=1,
            ),
            _event_row(
                "token_progress",
                {
                    "input_tokens": 11,
                    "output_tokens": 7,
                    "cache_read_tokens": 3,
                    "cache_write_tokens": 2,
                    "reasoning_tokens": 5,
                    "estimated_cost_usd": 0.0125,
                    "cost_status": "priced",
                    "cost_source": "catalog",
                    "model": "mock-model",
                    "trace": {"path": "/root/provider"},
                },
                ts_offset=-60,
                sequence=2,
            ),
        ]
        snap = _make_snapshot(events=events, now=now, windows=windows)
        assert snap.classification is ProgressClassification.HEALTHY
        assert snap.progress_age == timedelta(seconds=60)
        assert snap.current_path == "/root/provider"
        assert snap.latest_usage.present is True
        assert snap.usage_delta == ProgressUsage(
            input_tokens=11,
            output_tokens=7,
            cache_read_tokens=3,
            cache_write_tokens=2,
            reasoning_tokens=5,
            estimated_cost_usd=0.0125,
            cost_status="priced",
            cost_source="catalog",
            model="mock-model",
        )
        assert snap.usage_delta.total_tokens == 28

    def test_provider_usage_metadata_absence_does_not_create_progress_rate(self) -> None:
        windows = ProgressWindows(
            healthy_progress_window=timedelta(minutes=5),
            slow_signal_window=timedelta(minutes=15),
            stuck_progress_window=timedelta(minutes=30),
            stuck_liveness_window=timedelta(minutes=15),
            idle_signal_window=timedelta(hours=1),
            dead_signal_window=timedelta(hours=2),
        )
        now = _utc_ts(0)
        events = [
            _event_row(
                "stage.complete",
                {"stage": "draft", "path": "/root"},
                ts_offset=-2400,
                sequence=1,
            ),
            _event_row(
                "token_progress",
                {"trace": {"path": "/root/provider"}},
                ts_offset=-60,
                sequence=2,
            ),
        ]
        snap = _make_snapshot(events=events, now=now, windows=windows)
        assert snap.classification is ProgressClassification.STUCK_BUT_ALIVE
        assert snap.progress_age == timedelta(seconds=2400)
        assert snap.latest_usage.present is True
        assert snap.usage_delta.present is False
        assert snap.usage_delta.total_tokens == 0

    def test_current_path_from_latest_signal(self) -> None:
        events = [
            _event_row(
                "phase.start",
                {"path": "/root/step-1"},
                ts_offset=-60,
                sequence=2,
            ),
            _event_row(
                "phase.start",
                {"path": "/root/step-2"},
                ts_offset=-30,
                sequence=3,
            ),
        ]
        snap = _make_snapshot(events=events)
        assert snap.current_path == "/root/step-2"

    def test_current_stage_from_latest_stage_complete(self) -> None:
        events = [
            _event_row(
                "stage.complete",
                {"stage": "init", "path": "/root"},
                ts_offset=-120,
                sequence=1,
            ),
            _event_row(
                "stage.complete",
                {"stage": "plan", "path": "/root"},
                ts_offset=-60,
                sequence=2,
            ),
        ]
        snap = _make_snapshot(events=events)
        assert snap.current_stage == "plan"

    def test_checkpoint_status_reflected(self) -> None:
        now = _utc_ts(0)
        checkpoint = {
            "status": "suspended",
            "run_path": "/root",
            "cursor_stage": "review",
        }
        snap = _make_snapshot(checkpoint=checkpoint, now=now)
        assert snap.checkpoint_status == "suspended"

    def test_terminal_status_falls_back_to_audit(self) -> None:
        now = _utc_ts(0)
        audits = [
            _audit_row(
                {
                    "attempt_id": "a1",
                    "status": "failed",
                    "ended_at": _ts_iso(-60),
                    "run_path": "/root",
                }
            )
        ]
        snap = _make_snapshot(audits=audits, now=now)
        assert snap.terminal_status == "failed"

    def test_cancelled_checkpoint_yields_cancelled_status(self) -> None:
        now = _utc_ts(0)
        events = [_event_row("checkpoint", {}, ts_offset=-60)]
        checkpoint = {
            "status": "cancelled",
            "run_path": "/root",
            "cancellation": {"reason": "user_requested", "boundary": "step"},
        }
        snap = _make_snapshot(events=events, checkpoint=checkpoint, now=now)
        assert snap.checkpoint_status == "cancelled"
        assert snap.terminal_status == "cancelled"

    def test_signal_age_computed_when_signals_present(self) -> None:
        now = _utc_ts(0)
        events = [
            _event_row("phase.start", {"path": "/root"}, ts_offset=-600)
        ]
        snap = _make_snapshot(events=events, now=now)
        assert snap.signal_age is not None
        assert snap.signal_age == timedelta(seconds=600)
        assert snap.last_signal_at == _utc_ts(-600)

    def test_empty_snapshot_has_null_ages(self) -> None:
        snap = _make_snapshot()
        assert snap.signal_age is None
        assert snap.progress_age is None
        assert snap.last_signal_at is None
        assert snap.last_progress_at is None


# ── ProgressWindows validation ──────────────────────────────────────────────


class TestProgressWindowsValidation:
    def test_default_windows_pass_validation(self) -> None:
        windows = ProgressWindows()
        assert windows.healthy_progress_window == timedelta(minutes=5)

    def test_dead_must_be_gte_idle(self) -> None:
        with pytest.raises(ValueError, match="dead_signal_window"):
            ProgressWindows(
                dead_signal_window=timedelta(minutes=30),
                idle_signal_window=timedelta(hours=1),
            )

    def test_zero_windows_rejected(self) -> None:
        with pytest.raises(ValueError, match="healthy_progress_window"):
            ProgressWindows(healthy_progress_window=timedelta(0))

    def test_custom_windows_accepted(self) -> None:
        windows = ProgressWindows(
            healthy_progress_window=timedelta(seconds=10),
            dead_signal_window=timedelta(hours=2),
            idle_signal_window=timedelta(hours=1),
        )
        assert windows.healthy_progress_window == timedelta(seconds=10)


# ── ProgressSignal ──────────────────────────────────────────────────────────


class TestProgressSignal:
    def test_empty_signal_not_present(self) -> None:
        sig = ProgressSignal(source="event")
        assert sig.present is False

    def test_populated_signal_is_present(self) -> None:
        sig = ProgressSignal(
            source="event",
            observed_at=_utc_ts(0),
            kind="phase.start",
            path="/root",
        )
        assert sig.present is True


# ── File backend parity ─────────────────────────────────────────────────────


class TestFileBackendProgress:
    def test_snapshot_from_populated_artifact_root(self, tmp_path: Path) -> None:
        """End-to-end: write events/audit/checkpoint via file backend, read snapshot."""
        root = tmp_path / "run-01"
        root.mkdir(parents=True)

        binding = bind_legacy_artifact_root(root)

        def _resolver(scope: NativePersistenceScope) -> Path:
            if scope == binding.scope:
                return binding.artifact_root
            raise KeyError(scope)

        backend = FileNativePersistenceBackend(_resolver)

        # Write an event
        backend.emit_event(
            binding.scope,
            kind="stage.complete",
            payload={
                "stage": "validate",
                "pc": 1,
                "trace": {"path": "/root", "run_path": "/root"},
            },
        )

        # Write an audit record
        backend.append_audit_record(
            binding.scope,
            payload={
                "attempt_id": "attempt-1",
                "status": "success",
                "started_at": _ts_iso(-120),
                "ended_at": _ts_iso(-60),
                "run_path": "/root",
            },
        )

        # Write a checkpoint
        backend.write_trace_artifact(
            binding.scope,
            name="checkpoint.json",
            payload={
                "status": "completed",
                "run_path": "/root",
                "final": True,
            },
        )

        now = _utc_ts(0)
        snapshot = build_progress_snapshot(backend, binding.scope, now=now)
        assert snapshot.classification is ProgressClassification.HEALTHY
        assert snapshot.current_stage == "validate"
        assert snapshot.checkpoint_status == "completed"
        assert snapshot.terminal_status == "completed"
        assert snapshot.last_signal_at is not None

    def test_snapshot_for_artifact_root_helper(self, tmp_path: Path) -> None:
        """The legacy-compat helper returns a valid snapshot for an empty root."""
        root = tmp_path / "empty-run"
        root.mkdir()
        snapshot = build_progress_snapshot_for_artifact_root(str(root))
        assert snapshot.classification is ProgressClassification.DEAD
        assert snapshot.scope.project_id == "native-file-compat"


# ── Classification boundary tests ───────────────────────────────────────────


class TestClassificationBoundaries:
    def test_exactly_at_healthy_boundary_is_healthy(self) -> None:
        windows = ProgressWindows(healthy_progress_window=timedelta(minutes=5))
        now = _utc_ts(0)
        # Progress exactly at boundary
        audits = [
            _audit_row(
                {
                    "attempt_id": "a1",
                    "status": "success",
                    "ended_at": _ts_iso(-300),
                    "run_path": "/root",
                }
            )
        ]
        snap = _make_snapshot(audits=audits, now=now, windows=windows)
        assert snap.classification is ProgressClassification.HEALTHY

    def test_just_past_healthy_is_slow(self) -> None:
        windows = ProgressWindows(
            healthy_progress_window=timedelta(minutes=5),
            slow_signal_window=timedelta(minutes=15),
        )
        now = _utc_ts(0)
        events = [
            _event_row("phase.start", {"path": "/root"}, ts_offset=-301)
        ]
        snap = _make_snapshot(events=events, now=now, windows=windows)
        assert snap.classification is ProgressClassification.SLOW_PROGRESSING

    def test_progress_from_audit_classified_correctly(self) -> None:
        """Audit records contribute to progress age (not just signal age)."""
        windows = ProgressWindows(
            healthy_progress_window=timedelta(minutes=5),
            slow_signal_window=timedelta(minutes=15),
            stuck_progress_window=timedelta(minutes=30),
            stuck_liveness_window=timedelta(minutes=15),
            idle_signal_window=timedelta(hours=1),
            dead_signal_window=timedelta(hours=2),
        )
        now = _utc_ts(0)
        # Audit 10 min ago — progress is past healthy window
        audits = [
            _audit_row(
                {
                    "attempt_id": "a1",
                    "status": "success",
                    "ended_at": _ts_iso(-600),
                    "run_path": "/root",
                }
            )
        ]
        # Recent event keeps signal age low
        events = [
            _event_row("phase.start", {"path": "/root"}, ts_offset=-60)
        ]
        snap = _make_snapshot(events=events, audits=audits, now=now, windows=windows)
        # progress_age=600s > 300s healthy, signal_age=60s < 900s slow window => SLOW
        assert snap.classification is ProgressClassification.SLOW_PROGRESSING

    def test_audit_without_attempt_id_is_skipped(self) -> None:
        """Audit rows without attempt_id should not contribute to progress signals."""
        now = _utc_ts(0)
        audits = [
            _audit_row(
                {
                    "status": "success",
                    "ended_at": _ts_iso(-60),
                    "run_path": "/root",
                    # no attempt_id
                }
            )
        ]
        snap = _make_snapshot(audits=audits, now=now)
        # No valid audit signal => no signal at all => DEAD
        assert snap.classification is ProgressClassification.DEAD
        assert snap.latest_audit.present is False
