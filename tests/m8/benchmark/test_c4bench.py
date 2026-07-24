"""C4 benchmark gate — width × size matrix with median + p95 per cell.

Skipped by default; opt in with ``-m m8_benchmark`` to actually run.
The shape tests (profile constants, report writer correctness) run
unconditionally so the structure of C4BENCH_PROFILE / the report
format are pinned even in non-benchmark CI.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from .c4bench import (
    ARTIFACT_TIERS,
    C4BENCH_PROFILE,
    FANOUT_WIDTHS,
    GATED_WIDTH,
    HOT_PATH_LOCI,
    LINEAR_STAGE_COUNT,
    MAX_PHASE_WALL_CLOCK_REGRESSION_RATIO,
    MAX_SHORT_PHASE_OVERHEAD_SECONDS,
    REPETITIONS_PER_CELL,
    C4BenchRow,
    run_c4bench,
    write_c4bench_report,
)


class TestC4BenchProfileShape:
    """Structural invariants that pin the locked profile and report format."""

    def test_profile_is_frozen_tuple(self) -> None:
        assert isinstance(C4BENCH_PROFILE, tuple)
        assert len(C4BENCH_PROFILE) == len(ARTIFACT_TIERS) * (1 + len(FANOUT_WIDTHS))

    def test_profile_locks_linear_and_fanout_shape(self) -> None:
        assert LINEAR_STAGE_COUNT == 10
        widths = {cell.width for cell in C4BENCH_PROFILE}
        assert FANOUT_WIDTHS == (8, 32, 64)
        assert GATED_WIDTH == 32
        assert widths == {1, 8, 32, 64}

    def test_thresholds_lock_required_values(self) -> None:
        thresholds = {tier.label: tier.p95_threshold_seconds for tier in ARTIFACT_TIERS}
        assert thresholds == {
            "metadata": 0.002,
            "le_1mib": 0.008,
            "1_to_4mib": 0.025,
            "100mib_hash": 0.150,
        }
        assert MAX_PHASE_WALL_CLOCK_REGRESSION_RATIO == 0.10
        assert MAX_SHORT_PHASE_OVERHEAD_SECONDS == 0.500

    def test_repetitions_supports_median_and_p95(self) -> None:
        assert REPETITIONS_PER_CELL == 20

    def test_profile_exercises_required_hot_paths(self) -> None:
        assert set(HOT_PATH_LOCI) == {
            "executor_handoff",
            "chokepoint_validation",
            "structural_audit",
            "by_ref_sidecar_validation",
            "hash_on_write",
        }

    def test_report_writer_emits_required_columns(self, tmp_path: Path) -> None:
        """Writer must emit a header row containing median_s and p95_s."""
        rows = [
            C4BenchRow(
                scenario="linear_10",
                width=1,
                artifact_tier="metadata",
                bytes=1024,
                median_seconds=0.1,
                p95_seconds=0.2,
                p95_threshold_seconds=0.002,
                phase_wall_clock_overhead_seconds=0.001,
                phase_wall_clock_overhead_ratio=0.01,
                passed=True,
            )
        ]
        report_path = tmp_path / "C4BENCH_REPORT.md"
        write_c4bench_report(rows, path=report_path)
        text = report_path.read_text(encoding="utf-8")
        assert "median_s" in text
        assert "p95_s" in text
        assert "p95_threshold_s" in text
        assert "overhead_ratio" in text
        assert "Gate verdict: PASS" in text
        for row in rows:
            assert f"| {row.width} |" in text or f"| {row.width} " in text

    def test_report_writer_marks_threshold_breach_as_fail(
        self, tmp_path: Path
    ) -> None:
        rows = [
            C4BenchRow(
                scenario="fanout",
                width=32,
                artifact_tier="metadata",
                bytes=1024,
                median_seconds=0.4,
                p95_seconds=99.0,
                p95_threshold_seconds=0.002,
                phase_wall_clock_overhead_seconds=0.001,
                phase_wall_clock_overhead_ratio=0.01,
                passed=False,
            ),
        ]
        report_path = tmp_path / "C4BENCH_REPORT.md"
        write_c4bench_report(rows, path=report_path)
        text = report_path.read_text(encoding="utf-8")
        assert "Gate verdict: FAIL" in text
        assert "FAIL" in text


@pytest.mark.m8_benchmark
class TestC4BenchRun:
    """Runs the full matrix; opt-in via ``-m m8_benchmark``."""

    def test_run_produces_rows_and_writes_report(self, tmp_path: Path) -> None:
        rows = run_c4bench(tmp_path)
        assert len(rows) == len(C4BENCH_PROFILE)
        for row, cell in zip(rows, C4BENCH_PROFILE):
            assert row.width == cell.width
            assert row.bytes == cell.bytes
            assert row.median_seconds >= 0
            assert row.p95_seconds >= row.median_seconds - 1e-9

        out = write_c4bench_report(rows, path=tmp_path / "C4BENCH_REPORT.md")
        assert out.exists()


class TestC4BenchAcceptanceWiring:
    """The acceptance verdict must reference the C4 benchmark report."""

    def test_acceptance_verdict_mentions_c4bench_report(self) -> None:
        verdict = (
            Path(__file__).resolve().parents[3]
            / "docs"
            / "m8-acceptance-verdict.md"
        )
        assert verdict.exists()
        text = verdict.read_text(encoding="utf-8")
        assert "C4BENCH_REPORT.md" in text, (
            "docs/m8-acceptance-verdict.md must reference C4BENCH_REPORT.md"
        )
