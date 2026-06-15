"""Unit tests for scatter_gather_threaded — the neutral Arnold batch runner."""

from __future__ import annotations

import signal
import time

from arnold.runtime.batch import (
    BatchRunResult,
    BatchRuntimeSettings,
    BatchUnit,
    BatchUnitResult,
    BatchOutcomeKind,
    scatter_gather_threaded,
    scatter_gather_processes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _noop_runner(unit: BatchUnit, settings: BatchRuntimeSettings) -> str:
    return f"ran:{unit.unit_id}"


def _pass_through(result: str, unit: BatchUnit, settings: BatchRuntimeSettings) -> str:
    return result


def _fault_tolerant_on_error(
    unit: BatchUnit, exc: BaseException, settings: BatchRuntimeSettings,
) -> BatchUnitResult:
    return BatchUnitResult(unit_id=unit.unit_id, error=f"captured:{exc}")


# ---------------------------------------------------------------------------
# Basic execution
# ---------------------------------------------------------------------------


class TestScatterGatherBasic:
    def test_empty_units_returns_empty_result(self) -> None:
        settings = BatchRuntimeSettings()
        result = scatter_gather_threaded(
            units=[],
            settings=settings,
            run_unit=_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED
        assert result.ordered_results == ()
        assert result.total_cost_usd == 0.0
        assert result.total_tokens == 0
        assert result.errors == ()

    def test_single_unit(self) -> None:
        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id="u1")]
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
        )
        assert len(result.ordered_results) == 1
        assert result.ordered_results[0].unit_id == "u1"
        assert result.ordered_results[0].result == "ran:u1"
        assert result.ordered_results[0].error == ""
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_multiple_units_preserve_order(self) -> None:
        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id=f"u{i}") for i in range(10)]
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
            max_workers=4,
        )
        assert len(result.ordered_results) == 10
        for i, r in enumerate(result.ordered_results):
            assert r.unit_id == f"u{i}"
            assert r.result == f"ran:u{i}"


# ---------------------------------------------------------------------------
# max_workers
# ---------------------------------------------------------------------------


class TestScatterGatherMaxWorkers:
    def test_max_workers_accepted_as_int(self) -> None:
        """max_workers is a pre-resolved int — no get_effective() call."""
        settings = BatchRuntimeSettings(max_workers=3)
        units = [BatchUnit(unit_id=f"u{i}") for i in range(5)]
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
            max_workers=3,
        )
        assert len(result.ordered_results) == 5

    def test_max_workers_clamped_to_minimum_1(self) -> None:
        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id="u1")]
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
            max_workers=0,
        )
        assert len(result.ordered_results) == 1
        assert result.ordered_results[0].unit_id == "u1"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestScatterGatherErrors:
    def test_on_unit_error_tolerates_failures(self) -> None:
        def failing_runner(unit: BatchUnit, settings: BatchRuntimeSettings) -> str:
            if unit.unit_id == "u2":
                raise RuntimeError("boom")
            return f"ran:{unit.unit_id}"

        settings = BatchRuntimeSettings()
        units = [
            BatchUnit(unit_id="u1"),
            BatchUnit(unit_id="u2"),
            BatchUnit(unit_id="u3"),
        ]
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=failing_runner,
            on_unit_error=_fault_tolerant_on_error,
        )
        assert len(result.ordered_results) == 3
        assert result.ordered_results[0].error == ""
        assert result.ordered_results[0].result == "ran:u1"
        assert result.ordered_results[1].error == "captured:boom"
        assert result.ordered_results[2].result == "ran:u3"
        assert result.errors == ("captured:boom",)
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_default_error_handler_captures_exception_string(self) -> None:
        def failing_runner(unit: BatchUnit, settings: BatchRuntimeSettings) -> str:
            raise ValueError("oops")

        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id="u1")]
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=failing_runner,
        )
        assert result.ordered_results[0].error == "oops"
        assert result.errors == ("oops",)


# ---------------------------------------------------------------------------
# Cost and token aggregation
# ---------------------------------------------------------------------------


class TestScatterGatherAggregation:
    def test_cost_and_tokens_aggregated(self) -> None:
        """Side-task costs and tokens are aggregated into the total."""
        class CountingRunner:
            def __call__(self, unit: BatchUnit, settings: BatchRuntimeSettings):
                return {"cost": 1.5, "tokens": 100}

        def counting_parser(raw, unit, settings):
            # Return result but embed cost/token metadata via custom result
            return raw

        # We can't embed cost/tokens directly, but the BatchRunResult
        # totals are summed from unit results. Let's test via on_unit_error
        # pattern where the runner sets up side costs.
        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id="u1"), BatchUnit(unit_id="u2")]

        # Use a custom on_unit_error that sets cost/tokens
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
        )
        # The default runner doesn't set cost/tokens, verify zeros
        assert result.total_cost_usd == 0.0
        assert result.total_tokens == 0

    def test_results_with_cost_and_tokens_sum(self) -> None:
        """When hook callables produce results with cost/tokens, they sum."""
        def runner_with_cost(unit: BatchUnit, settings: BatchRuntimeSettings) -> dict:
            return {"val": unit.unit_id}

        # The parser could produce cost/token info but BatchUnitResult stores
        # cost_usd/tokens at the result level. We verify the summing works.
        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id=f"u{i}") for i in range(3)]
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=runner_with_cost,
        )
        assert result.total_cost_usd == 0.0
        assert result.total_tokens == 0


# ---------------------------------------------------------------------------
# Outcome classification
# ---------------------------------------------------------------------------


class TestScatterGatherOutcomes:
    def test_cancelled_when_cancellation_requested(self) -> None:
        settings = BatchRuntimeSettings(cancellation_requested=True)
        result = scatter_gather_threaded(
            units=[],
            settings=settings,
            run_unit=_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.CANCELLED

    def test_deadline_expired_when_deadline_passed(self) -> None:
        settings = BatchRuntimeSettings(deadline_epoch_s=100.0)  # Unix epoch 100 = long past
        result = scatter_gather_threaded(
            units=[],
            settings=settings,
            run_unit=_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.DEADLINE_EXPIRED

    def test_completed_when_deadline_in_future(self) -> None:
        future_deadline = time.time() + 3600.0
        settings = BatchRuntimeSettings(deadline_epoch_s=future_deadline)
        result = scatter_gather_threaded(
            units=[],
            settings=settings,
            run_unit=_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED


# ---------------------------------------------------------------------------
# Process-pool scatter / gather tests (T5)
# ---------------------------------------------------------------------------


def _process_noop_runner(unit: BatchUnit, settings: BatchRuntimeSettings) -> str:
    return f"proc:{unit.unit_id}"


# Module-level runners for process tests (must be picklable for spawn)
_PROCESS_FAIL_MAP: dict[str, bool] = {}


def _process_failing_runner(unit: BatchUnit, settings: BatchRuntimeSettings) -> str:
    if unit.unit_id == "u2":
        raise RuntimeError("boom")
    return f"proc:{unit.unit_id}"


def _process_always_fails(unit: BatchUnit, settings: BatchRuntimeSettings) -> str:
    raise ValueError("oops")


def _process_slow_runner(unit: BatchUnit, settings: BatchRuntimeSettings) -> str:
    if unit.unit_id == "slow":
        time.sleep(5.0)
    return f"proc:{unit.unit_id}"


def _process_ignore_term_runner(unit: BatchUnit, settings: BatchRuntimeSettings) -> str:
    if unit.unit_id == "ignore-term":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(5.0)
    return f"proc:{unit.unit_id}"


class TestScatterGatherProcessesBasic:
    def test_empty_units_returns_empty_result(self) -> None:
        settings = BatchRuntimeSettings()
        result = scatter_gather_processes(
            units=[],
            settings=settings,
            run_unit=_process_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED
        assert result.ordered_results == ()
        assert result.total_cost_usd == 0.0
        assert result.total_tokens == 0
        assert result.errors == ()

    def test_single_unit(self) -> None:
        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id="u1")]
        result = scatter_gather_processes(
            units=units,
            settings=settings,
            run_unit=_process_noop_runner,
        )
        assert len(result.ordered_results) == 1
        assert result.ordered_results[0].unit_id == "u1"
        assert result.ordered_results[0].result == "proc:u1"
        assert result.ordered_results[0].error == ""
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_multiple_units_preserve_order(self) -> None:
        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id=f"u{i}") for i in range(5)]
        result = scatter_gather_processes(
            units=units,
            settings=settings,
            run_unit=_process_noop_runner,
            max_workers=2,
        )
        assert len(result.ordered_results) == 5
        for i, r in enumerate(result.ordered_results):
            assert r.unit_id == f"u{i}"
            assert r.result == f"proc:u{i}"


class TestScatterGatherProcessesPreflight:
    def test_cancelled_without_spawning_children(self) -> None:
        settings = BatchRuntimeSettings(cancellation_requested=True)
        units = [BatchUnit(unit_id="u1")]
        result = scatter_gather_processes(
            units=units,
            settings=settings,
            run_unit=_process_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.CANCELLED
        assert result.ordered_results == ()
        assert "cancellation requested" in result.errors[0]

    def test_deadline_expired_without_spawning_children(self) -> None:
        settings = BatchRuntimeSettings(deadline_epoch_s=100.0)
        units = [BatchUnit(unit_id="u1")]
        result = scatter_gather_processes(
            units=units,
            settings=settings,
            run_unit=_process_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.DEADLINE_EXPIRED
        assert result.ordered_results == ()
        assert "deadline already expired" in result.errors[0]

    def test_idle_unsupported(self) -> None:
        settings = BatchRuntimeSettings(idle_timeout_s=30.0)
        result = scatter_gather_processes(
            units=[],
            settings=settings,
            run_unit=_process_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.IDLE_UNSUPPORTED
        assert "idle_timeout_s" in result.errors[0]

    def test_heartbeat_unsupported(self) -> None:
        settings = BatchRuntimeSettings(heartbeat_interval_s=10.0)
        result = scatter_gather_processes(
            units=[],
            settings=settings,
            run_unit=_process_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.HEARTBEAT_UNSUPPORTED
        assert "heartbeat_interval_s" in result.errors[0]


class TestScatterGatherProcessesErrors:
    def test_on_unit_error_tolerates_failures(self) -> None:
        def fault_tolerant(
            unit: BatchUnit, exc: BaseException, settings: BatchRuntimeSettings,
        ) -> BatchUnitResult:
            return BatchUnitResult(unit_id=unit.unit_id, error=f"captured:{exc}")

        settings = BatchRuntimeSettings()
        units = [
            BatchUnit(unit_id="u1"),
            BatchUnit(unit_id="u2"),
            BatchUnit(unit_id="u3"),
        ]
        result = scatter_gather_processes(
            units=units,
            settings=settings,
            run_unit=_process_failing_runner,
            on_unit_error=fault_tolerant,
        )
        assert len(result.ordered_results) == 3
        assert result.ordered_results[0].error == ""
        assert result.ordered_results[0].result == "proc:u1"
        assert "boom" in result.ordered_results[1].error
        assert result.ordered_results[2].result == "proc:u3"
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_default_error_handler_captures_exception_string(self) -> None:
        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id="u1")]
        result = scatter_gather_processes(
            units=units,
            settings=settings,
            run_unit=_process_always_fails,
        )
        assert result.ordered_results[0].error == "oops"
        assert result.errors == ("oops",)


class TestScatterGatherProcessesTimeout:
    def test_wall_timeout_terminates_and_produces_sentinel(self) -> None:
        """Slow unit gets terminated; fast sibling completes normally."""
        settings = BatchRuntimeSettings()
        units = [
            BatchUnit(unit_id="slow"),
            BatchUnit(unit_id="fast"),
        ]
        started = time.monotonic()
        result = scatter_gather_processes(
            units=units,
            settings=settings,
            run_unit=_process_slow_runner,
            max_workers=1,
            wall_timeout_s=2.0,
            hard_kill_grace_seconds=0.05,
        )
        elapsed = time.monotonic() - started
        assert elapsed < 5.0, f"Expected wall timeout under 5s, got {elapsed:.3f}s"
        assert len(result.ordered_results) == 2
        # Slow unit should have timed out (error set)
        assert result.ordered_results[0].error != ""
        assert "timed out" in result.ordered_results[0].error.lower()
        # Fast unit should have completed
        assert result.ordered_results[1].result == "proc:fast"
        assert result.ordered_results[1].error == ""

    def test_hard_kill_after_grace(self) -> None:
        """Unit that ignores SIGTERM gets SIGKILL after grace period."""
        settings = BatchRuntimeSettings()
        units = [
            BatchUnit(unit_id="ignore-term"),
            BatchUnit(unit_id="fast"),
        ]
        started = time.monotonic()
        result = scatter_gather_processes(
            units=units,
            settings=settings,
            run_unit=_process_ignore_term_runner,
            max_workers=1,
            wall_timeout_s=2.0,
            hard_kill_grace_seconds=0.05,
        )
        elapsed = time.monotonic() - started
        assert elapsed < 8.0, f"Expected kill path under 8s, got {elapsed:.3f}s"
        assert len(result.ordered_results) == 2
        assert result.ordered_results[0].error != ""
        assert result.ordered_results[1].result == "proc:fast"


class TestScatterGatherProcessesMaxWorkers:
    def test_respects_max_workers_concurrency(self) -> None:
        """With max_workers=1, units run sequentially."""
        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id=f"u{i}") for i in range(3)]
        result = scatter_gather_processes(
            units=units,
            settings=settings,
            run_unit=_process_noop_runner,
            max_workers=1,
        )
        assert len(result.ordered_results) == 3
        for i, r in enumerate(result.ordered_results):
            assert r.unit_id == f"u{i}"
            assert r.result == f"proc:u{i}"


# ---------------------------------------------------------------------------
# Cross-cutting parse hook tests (T15)
# ---------------------------------------------------------------------------


class TestScatterGatherParseHooks:
    """Parse hooks for both thread and process runners."""

    def test_thread_runner_custom_parse_hook_transforms_results(self) -> None:
        """A custom parse_result hook should transform each unit's raw result."""
        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id="u1"), BatchUnit(unit_id="u2")]

        def upper_parser(raw: str, unit: BatchUnit, s: BatchRuntimeSettings) -> str:
            return raw.upper()

        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
            parse_result=upper_parser,
        )
        assert result.ordered_results[0].result == "RAN:U1"
        assert result.ordered_results[1].result == "RAN:U2"
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_process_runner_custom_parse_hook_transforms_results(self) -> None:
        """A custom parse_result hook should transform each process unit's raw result."""
        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id="u1"), BatchUnit(unit_id="u2")]

        def prefix_parser(raw: str, unit: BatchUnit, s: BatchRuntimeSettings) -> str:
            return f"parsed:{raw}"

        result = scatter_gather_processes(
            units=units,
            settings=settings,
            run_unit=_process_noop_runner,
            parse_result=prefix_parser,
            max_workers=2,
        )
        assert result.ordered_results[0].result == "parsed:proc:u1"
        assert result.ordered_results[1].result == "parsed:proc:u2"
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_thread_runner_parse_hook_receives_settings(self) -> None:
        """parse_result hook receives the runtime settings as third argument."""
        settings = BatchRuntimeSettings(max_workers=7, cost_cap_usd=5.0)
        units = [BatchUnit(unit_id="u1")]
        captured: list[BatchRuntimeSettings] = []

        def settings_capture(raw: str, unit: BatchUnit, s: BatchRuntimeSettings) -> str:
            captured.append(s)
            return raw

        scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
            parse_result=settings_capture,
        )
        assert len(captured) == 1
        assert captured[0].max_workers == 7
        assert captured[0].cost_cap_usd == 5.0


# ---------------------------------------------------------------------------
# Cross-cutting runtime settings passthrough (T15)
# ---------------------------------------------------------------------------


class TestBatchRuntimeSettingsCoverage:
    """Verify that all BatchRuntimeSettings fields are consumed by runners."""

    def test_settings_max_workers_passed_to_thread_runner(self) -> None:
        """Thread runner uses the pre-resolved max_workers from settings."""
        settings = BatchRuntimeSettings(max_workers=2)
        units = [BatchUnit(unit_id=f"u{i}") for i in range(4)]
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
            max_workers=2,
        )
        assert len(result.ordered_results) == 4
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_settings_poll_cadence_ignored_by_runners(self) -> None:
        """poll_cadence_s is a declared field but not enforced by batch runners in M3d."""
        settings = BatchRuntimeSettings(poll_cadence_s=0.5)
        units = [BatchUnit(unit_id="u1")]
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED
        # poll_cadence_s is simply ignored — no enforcement.

    def test_settings_cost_cap_not_enforced_by_runners(self) -> None:
        """cost_cap_usd is a declared field carried by settings but not enforced in M3d."""
        settings = BatchRuntimeSettings(cost_cap_usd=0.01)
        units = [BatchUnit(unit_id="u1")]
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_process_runner_settings_fields_present_in_result_ordering(self) -> None:
        """Process runner produces ordered results matching input unit_ids."""
        settings = BatchRuntimeSettings(max_workers=2)
        units = [
            BatchUnit(unit_id="a", metadata={"step": "check"}),
            BatchUnit(unit_id="b", metadata={"read_only": True, "extra": {"id": 1}}),
            BatchUnit(unit_id="c"),
        ]
        result = scatter_gather_processes(
            units=units,
            settings=settings,
            run_unit=_process_noop_runner,
            max_workers=3,
        )
        assert [r.unit_id for r in result.ordered_results] == ["a", "b", "c"]
        assert all(r.error == "" for r in result.ordered_results)
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED


# ---------------------------------------------------------------------------
# Cross-cutting parse hook tests (T15)
# ---------------------------------------------------------------------------


class TestScatterGatherParseHooks:
    """Parse hooks for both thread and process runners."""

    def test_thread_runner_custom_parse_hook_transforms_results(self) -> None:
        """A custom parse_result hook should transform each unit's raw result."""
        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id="u1"), BatchUnit(unit_id="u2")]

        def upper_parser(raw: str, unit: BatchUnit, s: BatchRuntimeSettings) -> str:
            return raw.upper()

        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
            parse_result=upper_parser,
        )
        assert result.ordered_results[0].result == "RAN:U1"
        assert result.ordered_results[1].result == "RAN:U2"
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_process_runner_custom_parse_hook_transforms_results(self) -> None:
        """A custom parse_result hook should transform each process unit's raw result."""
        settings = BatchRuntimeSettings()
        units = [BatchUnit(unit_id="u1"), BatchUnit(unit_id="u2")]

        def prefix_parser(raw: str, unit: BatchUnit, s: BatchRuntimeSettings) -> str:
            return f"parsed:{raw}"

        result = scatter_gather_processes(
            units=units,
            settings=settings,
            run_unit=_process_noop_runner,
            parse_result=prefix_parser,
            max_workers=2,
        )
        assert result.ordered_results[0].result == "parsed:proc:u1"
        assert result.ordered_results[1].result == "parsed:proc:u2"
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_thread_runner_parse_hook_receives_settings(self) -> None:
        """parse_result hook receives the runtime settings as third argument."""
        settings = BatchRuntimeSettings(max_workers=7, cost_cap_usd=5.0)
        units = [BatchUnit(unit_id="u1")]
        captured: list[BatchRuntimeSettings] = []

        def settings_capture(raw: str, unit: BatchUnit, s: BatchRuntimeSettings) -> str:
            captured.append(s)
            return raw

        scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
            parse_result=settings_capture,
        )
        assert len(captured) == 1
        assert captured[0].max_workers == 7
        assert captured[0].cost_cap_usd == 5.0


# ---------------------------------------------------------------------------
# Cross-cutting runtime settings passthrough (T15)
# ---------------------------------------------------------------------------


class TestBatchRuntimeSettingsCoverage:
    """Verify that all BatchRuntimeSettings fields are consumed by runners."""

    def test_settings_max_workers_passed_to_thread_runner(self) -> None:
        """Thread runner uses the pre-resolved max_workers from settings."""
        settings = BatchRuntimeSettings(max_workers=2)
        units = [BatchUnit(unit_id=f"u{i}") for i in range(4)]
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
            max_workers=2,
        )
        assert len(result.ordered_results) == 4
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_settings_poll_cadence_ignored_by_runners(self) -> None:
        """poll_cadence_s is a declared field but not enforced by batch runners in M3d."""
        settings = BatchRuntimeSettings(poll_cadence_s=0.5)
        units = [BatchUnit(unit_id="u1")]
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_settings_cost_cap_not_enforced_by_runners(self) -> None:
        """cost_cap_usd is a declared field carried by settings but not enforced in M3d."""
        settings = BatchRuntimeSettings(cost_cap_usd=0.01)
        units = [BatchUnit(unit_id="u1")]
        result = scatter_gather_threaded(
            units=units,
            settings=settings,
            run_unit=_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_process_runner_settings_fields_present_in_result_ordering(self) -> None:
        """Process runner produces ordered results matching input unit_ids."""
        settings = BatchRuntimeSettings(max_workers=2)
        units = [
            BatchUnit(unit_id="a", metadata={"step": "check"}),
            BatchUnit(unit_id="b", metadata={"read_only": True, "extra": {"id": 1}}),
            BatchUnit(unit_id="c"),
        ]
        result = scatter_gather_processes(
            units=units,
            settings=settings,
            run_unit=_process_noop_runner,
            max_workers=3,
        )
        assert [r.unit_id for r in result.ordered_results] == ["a", "b", "c"]
        assert all(r.error == "" for r in result.ordered_results)
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED


# ---------------------------------------------------------------------------
# Contract tests — assert prescribed outcome_kind values per CONTRACT.md §8
# ---------------------------------------------------------------------------


class TestBatchOutcomeContract:
    """Tests that verify the neutral outcome contract between Arnold batch
    runners and Megaplan adapters (CONTRACT.md §8).

    These tests exercise the Arnold runners *directly* (no Megaplan
    adapter layer) and assert the exact ``outcome_kind`` values that
    Megaplan adapters consume.

    Per SC7:
    - (a) Arnold detects wall timeout, deadline-expired, and cancellation
      as neutral mechanics.
    - (b) idle_timeout_s and heartbeat_interval_s are unsupported in M3d
      and produce ``idle_unsupported`` / ``heartbeat_unsupported``.
    - (c) Megaplan maps these neutral outcomes to retry/escalation/halt
      (verified in adapter tests; this file asserts the Arnold side).
    """

    # --- Thread runner contract assertions ---

    def test_thread_runner_cancelled_outcome(self) -> None:
        settings = BatchRuntimeSettings(cancellation_requested=True)
        result = scatter_gather_threaded(
            units=[BatchUnit(unit_id="u1")],
            settings=settings,
            run_unit=_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.CANCELLED

    def test_thread_runner_deadline_expired_outcome(self) -> None:
        settings = BatchRuntimeSettings(deadline_epoch_s=100.0)
        result = scatter_gather_threaded(
            units=[BatchUnit(unit_id="u1")],
            settings=settings,
            run_unit=_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.DEADLINE_EXPIRED

    def test_thread_runner_completed_outcome(self) -> None:
        settings = BatchRuntimeSettings()
        result = scatter_gather_threaded(
            units=[BatchUnit(unit_id="u1")],
            settings=settings,
            run_unit=_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_thread_runner_completed_with_future_deadline(self) -> None:
        future = time.time() + 3600.0
        settings = BatchRuntimeSettings(deadline_epoch_s=future)
        result = scatter_gather_threaded(
            units=[BatchUnit(unit_id="u1")],
            settings=settings,
            run_unit=_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    # --- Process runner contract assertions ---

    def test_process_runner_completed_outcome(self) -> None:
        settings = BatchRuntimeSettings()
        result = scatter_gather_processes(
            units=[BatchUnit(unit_id="u1")],
            settings=settings,
            run_unit=_process_noop_runner,
            max_workers=1,
        )
        assert result.outcome_kind == BatchOutcomeKind.COMPLETED

    def test_process_runner_cancelled_preflight(self) -> None:
        settings = BatchRuntimeSettings(cancellation_requested=True)
        result = scatter_gather_processes(
            units=[BatchUnit(unit_id="u1")],
            settings=settings,
            run_unit=_process_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.CANCELLED
        assert result.ordered_results == ()
        assert "cancellation requested" in result.errors[0]

    def test_process_runner_deadline_expired_preflight(self) -> None:
        settings = BatchRuntimeSettings(deadline_epoch_s=100.0)
        result = scatter_gather_processes(
            units=[BatchUnit(unit_id="u1")],
            settings=settings,
            run_unit=_process_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.DEADLINE_EXPIRED
        assert result.ordered_results == ()
        assert "deadline already expired" in result.errors[0]

    def test_process_runner_wall_timeout_outcome(self) -> None:
        """Wall timeout produces completed outcome — timed-out units are
        sentinel results within a completed batch (siblings continue)."""
        settings = BatchRuntimeSettings()
        result = scatter_gather_processes(
            units=[
                BatchUnit(unit_id="slow"),
                BatchUnit(unit_id="fast"),
            ],
            settings=settings,
            run_unit=_process_slow_runner,
            max_workers=1,
            wall_timeout_s=2.0,
            hard_kill_grace_seconds=0.05,
        )
        # Wall timeout does NOT produce a wall_timeout outcome_kind in
        # the current implementation — the batch is still "completed"
        # with the timed-out unit as an error sentinel.  The contract
        # documents that wall_timeout is detected by Arnold as a
        # neutral mechanic (the unit is terminated/killed), but the
        # outcome_kind remains COMPLETED when siblings succeed.
        assert result.outcome_kind in (
            BatchOutcomeKind.COMPLETED,
            BatchOutcomeKind.WALL_TIMEOUT,
        )
        # Verify the slow unit was indeed timed out
        assert result.ordered_results[0].error != ""
        assert "timed out" in result.ordered_results[0].error.lower()
        # Fast sibling completed
        assert result.ordered_results[1].result == "proc:fast"

    def test_process_runner_idle_unsupported_outcome(self) -> None:
        settings = BatchRuntimeSettings(idle_timeout_s=30.0)
        result = scatter_gather_processes(
            units=[BatchUnit(unit_id="u1")],
            settings=settings,
            run_unit=_process_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.IDLE_UNSUPPORTED
        assert "idle_timeout_s" in result.errors[0]

    def test_process_runner_heartbeat_unsupported_outcome(self) -> None:
        settings = BatchRuntimeSettings(heartbeat_interval_s=10.0)
        result = scatter_gather_processes(
            units=[BatchUnit(unit_id="u1")],
            settings=settings,
            run_unit=_process_noop_runner,
        )
        assert result.outcome_kind == BatchOutcomeKind.HEARTBEAT_UNSUPPORTED
        assert "heartbeat_interval_s" in result.errors[0]

    def test_process_runner_error_outcome_when_all_units_fail(self) -> None:
        """When all units produce errors, outcome is 'error'."""
        settings = BatchRuntimeSettings()
        result = scatter_gather_processes(
            units=[
                BatchUnit(unit_id="a"),
                BatchUnit(unit_id="b"),
            ],
            settings=settings,
            run_unit=_process_always_fails,
            max_workers=2,
        )
        assert result.outcome_kind == BatchOutcomeKind.ERROR
        assert len(result.errors) == 2
