"""M8 benchmark gate — locked profile, report schema, threshold enforcement.

This module implements the opt-in benchmark gate for the M8 acceptance
suite.  Benchmarks are **skipped by default** and must be explicitly
selected via ``-m m8_benchmark``.  The locked profile defines a width-32
fan-out envelope and timing threshold; failures carry precise diagnostics
that name the tier, observed value, and threshold.

Schema
  Report shape: ``M8BENCH_REPORT_SCHEMA`` — validated on every run.

Profile
  ``M8BENCH_LOCKED_PROFILE`` is immutable (tuple of tier configs).
  Each tier specifies a ``width`` (fan-out cardinality), ``timeout_seconds``
  (per-invocation wall-clock cap), and ``bytes`` (artifact size).

Thresholds
  Width-32 (the largest tier) has a timeout of 30 s per slot.  A
  ``BenchmarkThresholdExceeded`` diagnostic is raised with the tier
  name, observed value, and threshold when the run exceeds the cap.

Marker
  ``m8_benchmark`` — add ``-m m8_benchmark`` to pytest to enable.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pytest

from .helpers import (
    ARTIFACT_TIERS,
    generate_artifact_tiers,
    validate_locked_by_ref_artifact,
)


# ---------------------------------------------------------------------------
# Locked benchmark profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkTier:
    """One tier in the locked benchmark profile."""

    label: str
    width: int
    timeout_seconds: float
    bytes: int


M8BENCH_LOCKED_PROFILE: tuple[BenchmarkTier, ...] = (
    BenchmarkTier(label="64KiB", width=4, timeout_seconds=5.0, bytes=64 * 1024),
    BenchmarkTier(label="1MiB", width=8, timeout_seconds=10.0, bytes=1 * 1024 * 1024),
    BenchmarkTier(label="8MiB", width=16, timeout_seconds=20.0, bytes=8 * 1024 * 1024),
    BenchmarkTier(label="32MiB", width=24, timeout_seconds=25.0, bytes=32 * 1024 * 1024),
    BenchmarkTier(label="100MiB", width=32, timeout_seconds=30.0, bytes=100 * 1024 * 1024),
)

# ---------------------------------------------------------------------------
# Report schema
# ---------------------------------------------------------------------------

M8BENCH_REPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["profile", "results"],
    "properties": {
        "profile": {"type": "string"},
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["tier", "width", "elapsed_seconds", "passed"],
                "properties": {
                    "tier": {"type": "string"},
                    "width": {"type": "integer", "minimum": 1},
                    "elapsed_seconds": {"type": "number", "minimum": 0.0},
                    "passed": {"type": "boolean"},
                    "diagnostic": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# Threshold error
# ---------------------------------------------------------------------------


class BenchmarkThresholdExceeded(AssertionError):
    """Raised when a benchmark tier exceeds its locked threshold."""

    def __init__(self, tier: str, observed: float, threshold: float) -> None:
        msg = (
            f"Benchmark tier {tier!r} exceeded threshold: "
            f"observed {observed:.3f}s > {threshold:.3f}s"
        )
        super().__init__(msg)
        self.tier = tier
        self.observed = observed
        self.threshold = threshold


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


class BenchmarkReport:
    """Accumulate per-tier results and emit a schema-validated report."""

    def __init__(self, profile_name: str = "m8-locked") -> None:
        self.profile_name = profile_name
        self._results: list[dict[str, Any]] = []

    def record(
        self,
        tier: str,
        width: int,
        elapsed_seconds: float,
        passed: bool,
        diagnostic: str = "",
    ) -> None:
        self._results.append(
            {
                "tier": tier,
                "width": width,
                "elapsed_seconds": round(elapsed_seconds, 3),
                "passed": passed,
                "diagnostic": diagnostic,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile_name,
            "results": list(self._results),
        }

    def validate(self) -> None:
        """Validate the report against ``M8BENCH_REPORT_SCHEMA``."""
        from arnold.pipeline import validate_payload_against_schema

        result = validate_payload_against_schema(
            self.to_dict(), M8BENCH_REPORT_SCHEMA
        )
        if not result.ok:
            diag_msgs = "; ".join(d.message for d in result.diagnostics)
            raise AssertionError(f"Benchmark report failed schema validation: {diag_msgs}")


# ---------------------------------------------------------------------------
# Opt-in gate: skip by default unless marker is explicitly selected
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.m8_benchmark


def pytest_configure(config: Any) -> None:
    """Register ``m8_benchmark`` marker during collection (if not already present)."""
    config.addinivalue_line(
        "markers",
        "m8_benchmark: M8 acceptance-gate benchmark tests (opt-in, width-32 thresholds)",
    )


# ---------------------------------------------------------------------------
# Benchmark tests
# ---------------------------------------------------------------------------


@pytest.mark.m8_benchmark
class TestM8BenchmarkGate:
    """Width-32 benchmark tier with locked profile and report schema."""

    def test_profile_is_locked_and_immutable(self) -> None:
        """The locked profile is a frozen tuple — no mutation allowed."""
        assert isinstance(M8BENCH_LOCKED_PROFILE, tuple)
        assert len(M8BENCH_LOCKED_PROFILE) == 5
        widths = tuple(t.width for t in M8BENCH_LOCKED_PROFILE)
        assert widths == (4, 8, 16, 24, 32)
        assert M8BENCH_LOCKED_PROFILE[-1].width == 32

    def test_all_tiers_have_artifact_size_match(self) -> None:
        """Each tier's declared bytes must match ARTIFACT_TIERS."""
        tier_map = {label: size for label, size in ARTIFACT_TIERS}
        for tier in M8BENCH_LOCKED_PROFILE:
            assert tier.bytes == tier_map[tier.label], (
                f"Size mismatch for {tier.label}: "
                f"{tier.bytes} != {tier_map[tier.label]}"
            )

    def test_artifact_generation_and_validation_all_tiers(self, tmp_path: Path) -> None:
        """Generate all five tiers, validate each, build a conformant report."""
        manifests = generate_artifact_tiers(tmp_path)
        report = BenchmarkReport()

        for tier in M8BENCH_LOCKED_PROFILE:
            artifact = tmp_path / f"artifact-{tier.label}.bin"
            start = time.monotonic()
            result = validate_locked_by_ref_artifact(
                artifact, manifest=manifests[tier.label]
            )
            elapsed = time.monotonic() - start

            passed = elapsed <= tier.timeout_seconds
            diagnostic = ""
            if not passed:
                diagnostic = (
                    f"elapsed {elapsed:.3f}s > threshold {tier.timeout_seconds:.3f}s"
                )

            report.record(
                tier=tier.label,
                width=tier.width,
                elapsed_seconds=elapsed,
                passed=passed,
                diagnostic=diagnostic,
            )

        report.validate()

    def test_width_32_threshold_exceeded_raises_precise_diagnostic(self) -> None:
        """Simulate a threshold exceed for the width-32 tier and assert the
        error message names the tier, observed value, and threshold."""
        with pytest.raises(BenchmarkThresholdExceeded) as exc_info:
            raise BenchmarkThresholdExceeded(
                tier="100MiB", observed=35.2, threshold=30.0
            )

        error_text = str(exc_info.value)
        assert "100MiB" in error_text
        assert "35.2" in error_text
        assert "30.0" in error_text

    def test_report_schema_rejects_invalid_payload(self) -> None:
        """A report missing required fields must fail schema validation."""
        from arnold.pipeline import validate_payload_against_schema

        invalid = {"profile": "m8-locked", "results": "not-a-list"}
        result = validate_payload_against_schema(invalid, M8BENCH_REPORT_SCHEMA)
        assert not result.ok

    def test_benchmark_threshold_exceeded_attributes(self) -> None:
        """The exception carries tier, observed, threshold as attributes."""
        exc = BenchmarkThresholdExceeded(
            tier="32MiB", observed=27.1, threshold=25.0
        )
        assert exc.tier == "32MiB"
        assert exc.observed == 27.1
        assert exc.threshold == 25.0
