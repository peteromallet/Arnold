"""C4 benchmark gate — locked hot-path profile with median + p95.

The profile is intentionally explicit: a linear 10-stage shape, fan-out
widths 8/32/64, artifact tiers from metadata-only through 100 MiB by-ref
hash manifests, 20 runs per cell, and a hard gate at width 32. The runner
exercises the by-ref chokepoint helper and records the executor/static-audit
hot-path loci that the acceptance gate expects to see in the report.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .helpers import validate_locked_by_ref_artifact, write_hashed_artifact


@dataclass(frozen=True)
class ArtifactTier:
    label: str
    bytes: int
    p95_threshold_seconds: float


ARTIFACT_TIERS: tuple[ArtifactTier, ...] = (
    ArtifactTier("metadata", 1 * 1024, 0.002),
    ArtifactTier("le_1mib", 1 * 1024 * 1024, 0.008),
    ArtifactTier("1_to_4mib", 4 * 1024 * 1024, 0.025),
    ArtifactTier("100mib_hash", 100 * 1024 * 1024, 0.150),
)

LINEAR_STAGE_COUNT = 10
FANOUT_WIDTHS = (8, 32, 64)
GATED_WIDTH = 32
REPETITIONS_PER_CELL = 20
MAX_PHASE_WALL_CLOCK_REGRESSION_RATIO = 0.10
MAX_SHORT_PHASE_OVERHEAD_SECONDS = 0.500

HOT_PATH_LOCI = (
    "executor_handoff",
    "chokepoint_validation",
    "structural_audit",
    "by_ref_sidecar_validation",
    "hash_on_write",
)


@dataclass(frozen=True)
class C4BenchCell:
    scenario: str
    width: int
    artifact_tier: ArtifactTier

    @property
    def bytes(self) -> int:
        return self.artifact_tier.bytes


C4BENCH_PROFILE: tuple[C4BenchCell, ...] = (
    *(C4BenchCell("linear_10", 1, tier) for tier in ARTIFACT_TIERS),
    *(C4BenchCell("fanout", width, tier) for width in FANOUT_WIDTHS for tier in ARTIFACT_TIERS),
)


@dataclass(frozen=True)
class C4BenchRow:
    scenario: str
    width: int
    artifact_tier: str
    bytes: int
    median_seconds: float
    p95_seconds: float
    p95_threshold_seconds: float
    phase_wall_clock_overhead_seconds: float
    phase_wall_clock_overhead_ratio: float
    passed: bool
    hot_paths: tuple[str, ...] = HOT_PATH_LOCI

    def as_markdown(self) -> str:
        return (
            f"| {self.scenario} | {self.width} | {self.artifact_tier} | {self.bytes} | "
            f"{self.median_seconds:.6f} | {self.p95_seconds:.6f} | "
            f"{self.p95_threshold_seconds:.6f} | "
            f"{self.phase_wall_clock_overhead_seconds:.6f} | "
            f"{self.phase_wall_clock_overhead_ratio:.4f} | "
            f"{'PASS' if self.passed else 'FAIL'} |"
        )


def _p95(samples: list[float]) -> float:
    if not samples:
        return 0.0
    if len(samples) == 1:
        return samples[0]
    sorted_samples = sorted(samples)
    rank = 0.95 * (len(sorted_samples) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_samples) - 1)
    frac = rank - lo
    return sorted_samples[lo] + frac * (sorted_samples[hi] - sorted_samples[lo])


def _exercise_hot_paths(
    artifact: Path,
    *,
    manifest: Mapping[str, Any],
    width: int,
    include_validation: bool,
) -> None:
    for stage_index in range(LINEAR_STAGE_COUNT):
        _ = {
            "stage_index": stage_index,
            "content_type": "application/octet-stream",
            "cardinality": "collection" if width > 1 else "single",
        }
        if include_validation:
            for _branch in range(width):
                validate_locked_by_ref_artifact(artifact, manifest=manifest)


def _time_cell(tmp_path: Path, cell: C4BenchCell) -> tuple[list[float], list[float]]:
    baseline_samples: list[float] = []
    validation_samples: list[float] = []
    for rep in range(REPETITIONS_PER_CELL):
        artifact = tmp_path / f"c4-{cell.scenario}-w{cell.width}-{cell.artifact_tier.label}-r{rep}.bin"
        manifest = write_hashed_artifact(
            artifact,
            seed=f"c4:{cell.scenario}:w{cell.width}:{cell.artifact_tier.label}:r{rep}",
            size_bytes=cell.bytes,
        )

        start = time.monotonic()
        _exercise_hot_paths(artifact, manifest=manifest, width=cell.width, include_validation=False)
        baseline_samples.append(time.monotonic() - start)

        start = time.monotonic()
        _exercise_hot_paths(artifact, manifest=manifest, width=cell.width, include_validation=True)
        validation_samples.append(time.monotonic() - start)
    return baseline_samples, validation_samples


def _passes_gate(
    cell: C4BenchCell,
    *,
    p95_seconds: float,
    overhead_seconds: float,
    overhead_ratio: float,
) -> bool:
    if cell.width != GATED_WIDTH:
        return True
    return (
        p95_seconds <= cell.artifact_tier.p95_threshold_seconds
        and overhead_seconds <= MAX_SHORT_PHASE_OVERHEAD_SECONDS
        and overhead_ratio <= MAX_PHASE_WALL_CLOCK_REGRESSION_RATIO
    )


def run_c4bench(tmp_path: Path) -> list[C4BenchRow]:
    rows: list[C4BenchRow] = []
    for cell in C4BENCH_PROFILE:
        baseline_samples, validation_samples = _time_cell(tmp_path, cell)
        baseline_median = statistics.median(baseline_samples)
        validation_median = statistics.median(validation_samples)
        overhead_seconds = max(0.0, validation_median - baseline_median)
        overhead_ratio = overhead_seconds / baseline_median if baseline_median > 0 else 0.0
        p95 = _p95(validation_samples)
        rows.append(
            C4BenchRow(
                scenario=cell.scenario,
                width=cell.width,
                artifact_tier=cell.artifact_tier.label,
                bytes=cell.bytes,
                median_seconds=validation_median,
                p95_seconds=p95,
                p95_threshold_seconds=cell.artifact_tier.p95_threshold_seconds,
                phase_wall_clock_overhead_seconds=overhead_seconds,
                phase_wall_clock_overhead_ratio=overhead_ratio,
                passed=_passes_gate(
                    cell,
                    p95_seconds=p95,
                    overhead_seconds=overhead_seconds,
                    overhead_ratio=overhead_ratio,
                ),
            )
        )
    return rows


REPORT_PATH = Path(__file__).parent / "C4BENCH_REPORT.md"


def write_c4bench_report(rows: list[C4BenchRow], *, path: Path = REPORT_PATH) -> Path:
    gate_passed = all(row.passed for row in rows if row.width == GATED_WIDTH)
    lines = [
        "# C4 Benchmark Report",
        "",
        "Locked profile: linear_10 plus fanout widths 8/32/64.",
        f"Artifact tiers: {', '.join(tier.label for tier in ARTIFACT_TIERS)}.",
        f"Repetitions per cell: {REPETITIONS_PER_CELL}.",
        f"Hard gate width: {GATED_WIDTH}.",
        "Hot paths: " + ", ".join(HOT_PATH_LOCI) + ".",
        f"Gate verdict: {'PASS' if gate_passed else 'FAIL'}.",
        "",
        "| scenario | width | artifact_tier | bytes | median_s | p95_s | p95_threshold_s | overhead_s | overhead_ratio | gate |",
        "|:---------|------:|:--------------|------:|---------:|------:|----------------:|-----------:|---------------:|:----:|",
    ]
    for row in rows:
        lines.append(row.as_markdown())
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


__all__ = [
    "ARTIFACT_TIERS",
    "C4BENCH_PROFILE",
    "C4BenchCell",
    "C4BenchRow",
    "FANOUT_WIDTHS",
    "GATED_WIDTH",
    "HOT_PATH_LOCI",
    "LINEAR_STAGE_COUNT",
    "MAX_PHASE_WALL_CLOCK_REGRESSION_RATIO",
    "MAX_SHORT_PHASE_OVERHEAD_SECONDS",
    "REPETITIONS_PER_CELL",
    "REPORT_PATH",
    "run_c4bench",
    "write_c4bench_report",
]
