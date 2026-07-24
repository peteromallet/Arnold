"""M8 acceptance-gate benchmark module — opt-in, width-32 profile.

This module implements the deterministic benchmark gate for the M8 acceptance
suite. It is opt-in (``@pytest.mark.m8_benchmark``), defaults to skip when the
marker is not explicitly selected, and enforces width-32 threshold failures
with precise diagnostics.

Locked profile
--------------

The benchmark profile is locked at compile time and must not drift between
runs.  The profile defines:

* ``artifact_tiers`` — the tier labels and byte-sizes that must be generated.
* ``manifest_only_threshold_bytes`` — the boundary above which validation uses
  the sidecar manifest instead of rehashing blob contents.
* ``tier_timeout_seconds`` — maximum wall-clock seconds per tier.
* ``report_schema`` — JSON Schema that every benchmark report must conform to.

Report schema
-------------

Every benchmark run produces a JSON report that must validate against the
REPORT_SCHEMA defined in this module.  The report includes:

* ``benchmark_profile_hash`` — content-hash of the locked profile values.
* ``tiers`` — per-tier timing and hash records.
* ``aggregate`` — total runtime and pass/fail verdict.

Default skip posture
--------------------

Tests decorated with ``@pytest.mark.m8_benchmark`` are skipped unless the
``--m8-benchmark`` flag is passed on the command line.  This is implemented
via a session-scoped fixture that inspects ``request.config.option``.

Marker registration
-------------------

The ``m8_benchmark`` marker is registered in ``pyproject.toml`` under
``[tool.pytest.ini_options].markers`` as:

    ``m8_benchmark: M8 acceptance-gate benchmark tests (opt-in, width-32 thresholds)``
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Mapping

import pytest

from tests.m8.benchmark.helpers import (
    ARTIFACT_TIERS,
    MANIFEST_ONLY_THRESHOLD_BYTES,
    generate_artifact_tiers,
    validate_locked_by_ref_artifact,
)

# ---------------------------------------------------------------------------
# Locked benchmark profile (compile-time constant — must not drift)
# ---------------------------------------------------------------------------

LOCKED_PROFILE: dict[str, Any] = {
    "artifact_tiers": [
        {"label": label, "size_bytes": size_bytes}
        for label, size_bytes in ARTIFACT_TIERS
    ],
    "manifest_only_threshold_bytes": MANIFEST_ONLY_THRESHOLD_BYTES,
    "tier_timeout_seconds": 120,
    "report_schema_version": "m8-benchmark/v1",
}

LOCKED_PROFILE_HASH: str = "sha256:" + hashlib.sha256(
    json.dumps(LOCKED_PROFILE, sort_keys=True).encode("utf-8")
).hexdigest()

# ---------------------------------------------------------------------------
# Report schema (every benchmark report must validate against this)
# ---------------------------------------------------------------------------

REPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "benchmark_profile_hash",
        "tiers",
        "aggregate",
    ],
    "additionalProperties": False,
    "properties": {
        "benchmark_profile_hash": {"type": "string"},
        "tiers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "size_bytes", "sha256", "runtime_seconds", "mode"],
                "additionalProperties": False,
                "properties": {
                    "label": {"type": "string"},
                    "size_bytes": {"type": "integer"},
                    "sha256": {"type": "string"},
                    "runtime_seconds": {"type": "number"},
                    "mode": {"type": "string"},
                },
            },
        },
        "aggregate": {
            "type": "object",
            "required": ["total_runtime_seconds", "verdict"],
            "additionalProperties": False,
            "properties": {
                "total_runtime_seconds": {"type": "number"},
                "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Width-32 threshold validation
# ---------------------------------------------------------------------------

WIDTH_32_THRESHOLD_BYTES = 32 * 1024 * 1024  # 32 MiB

WIDTH_32_DIAGNOSTIC_TEMPLATE = (
    "M8 width-32 threshold exceeded: tier {label!r} ({size_bytes} bytes) "
    "validation took {runtime_seconds:.3f}s > {timeout}s. "
    "This tier must fit within the width-32 budget to pass the acceptance gate."
)


def _build_report(
    manifests: Mapping[str, dict[str, Any]],
    runtimes: Mapping[str, float],
    *,
    timeout: float,
) -> tuple[dict[str, Any], str]:
    """Build a benchmark report and return (report, verdict)."""
    from tests.m8.benchmark.helpers import locked_by_ref_policy

    tiers: list[dict[str, Any]] = []
    verdict = "PASS"
    for label, size_bytes in ARTIFACT_TIERS:
        manifest = manifests[label]
        runtime = runtimes.get(label, 0.0)
        mode = locked_by_ref_policy(size_bytes)
        if runtime > timeout:
            verdict = "FAIL"
        tiers.append({
            "label": label,
            "size_bytes": size_bytes,
            "sha256": manifest["sha256"],
            "runtime_seconds": runtime,
            "mode": mode,
        })
    total = sum(t["runtime_seconds"] for t in tiers)
    return {
        "benchmark_profile_hash": LOCKED_PROFILE_HASH,
        "tiers": tiers,
        "aggregate": {
            "total_runtime_seconds": total,
            "verdict": verdict,
        },
    }, verdict


def _validate_report(report: dict[str, Any]) -> list[str]:
    """Validate a report against REPORT_SCHEMA.  Returns a list of diagnostics."""
    from arnold.pipeline import validate_payload_against_schema

    result = validate_payload_against_schema(report, REPORT_SCHEMA)
    if result.ok:
        return []
    return [
        f"{d.code} at {d.payload_pointer}: {d.message}"
        for d in result.diagnostics
    ]


# ---------------------------------------------------------------------------
# Benchmark tests
# ---------------------------------------------------------------------------


@pytest.mark.m8_benchmark
class TestM8BenchmarkGate:
    """M8 acceptance-gate benchmark suite.

    These tests run the deterministic artifact tier generation and validation
    pipeline under the locked profile and report any width-32 threshold
    failures with precise diagnostics.
    """

    def test_locked_profile_hash_is_stable(self) -> None:
        """The locked profile hash must not change between runs."""
        assert LOCKED_PROFILE_HASH.startswith("sha256:")
        # Recompute to prove determinism
        recomputed = "sha256:" + hashlib.sha256(
            json.dumps(LOCKED_PROFILE, sort_keys=True).encode("utf-8")
        ).hexdigest()
        assert LOCKED_PROFILE_HASH == recomputed

    def test_report_schema_validates_itself(self) -> None:
        """The report schema is a well-formed JSON Schema document."""
        assert REPORT_SCHEMA["type"] == "object"
        assert "required" in REPORT_SCHEMA
        assert "properties" in REPORT_SCHEMA

    def test_generate_and_validate_all_tiers(self, tmp_path: Path) -> None:
        """Generate all artifact tiers, validate them, and build a report."""
        manifests = generate_artifact_tiers(tmp_path)
        timeout = LOCKED_PROFILE["tier_timeout_seconds"]
        runtimes: dict[str, float] = {}

        for label, size_bytes in ARTIFACT_TIERS:
            artifact = tmp_path / f"artifact-{label}.bin"
            assert artifact.exists(), f"artifact {label} was not generated"
            assert artifact.stat().st_size == size_bytes

            start = time.monotonic()
            result = validate_locked_by_ref_artifact(
                artifact,
                manifest=manifests[label],
            )
            elapsed = time.monotonic() - start
            runtimes[label] = elapsed

            assert result["sha256"] == manifests[label]["sha256"]
            assert result["size_bytes"] == size_bytes

        report, verdict = _build_report(manifests, runtimes, timeout=timeout)
        diagnostics = _validate_report(report)
        assert not diagnostics, (
            f"Report schema validation failed:\n" + "\n".join(diagnostics)
        )

        # Width-32 threshold check
        for tier in report["tiers"]:
            if tier["runtime_seconds"] > timeout:
                msg = WIDTH_32_DIAGNOSTIC_TEMPLATE.format(
                    label=tier["label"],
                    size_bytes=tier["size_bytes"],
                    runtime_seconds=tier["runtime_seconds"],
                    timeout=timeout,
                )
                pytest.fail(msg)

        assert verdict == "PASS", (
            f"Benchmark verdict is FAIL; check tier runtimes:\n"
            + "\n".join(
                f"  {t['label']}: {t['runtime_seconds']:.3f}s"
                for t in report["tiers"]
            )
        )

    @pytest.mark.parametrize("label,size_bytes", ARTIFACT_TIERS)
    def test_individual_tier_threshold(
        self, tmp_path: Path, label: str, size_bytes: int
    ) -> None:
        """Each tier individually must complete within the timeout."""
        manifests = generate_artifact_tiers(tmp_path)
        artifact = tmp_path / f"artifact-{label}.bin"
        timeout = LOCKED_PROFILE["tier_timeout_seconds"]

        start = time.monotonic()
        result = validate_locked_by_ref_artifact(
            artifact,
            manifest=manifests[label],
        )
        elapsed = time.monotonic() - start

        assert result["sha256"] == manifests[label]["sha256"]
        assert elapsed <= timeout, (
            WIDTH_32_DIAGNOSTIC_TEMPLATE.format(
                label=label,
                size_bytes=size_bytes,
                runtime_seconds=elapsed,
                timeout=timeout,
            )
        )

    def test_32mib_tier_hashes_correctly(self, tmp_path: Path) -> None:
        """The 32MiB tier must hash correctly and use the right mode."""
        manifests = generate_artifact_tiers(tmp_path)
        artifact = tmp_path / "artifact-32MiB.bin"

        result = validate_locked_by_ref_artifact(
            artifact,
            manifest=manifests["32MiB"],
        )
        # 32MiB > 1MiB threshold → manifest mode
        assert result["mode"] == "manifest"
        assert result["sha256"] == manifests["32MiB"]["sha256"]
        assert result["size_bytes"] == WIDTH_32_THRESHOLD_BYTES

    def test_report_is_json_serializable(self) -> None:
        """The report structure can be serialized to JSON."""
        report = {
            "benchmark_profile_hash": LOCKED_PROFILE_HASH,
            "tiers": [],
            "aggregate": {
                "total_runtime_seconds": 0.0,
                "verdict": "PASS",
            },
        }
        serialized = json.dumps(report, sort_keys=True)
        assert isinstance(serialized, str)
        roundtripped = json.loads(serialized)
        assert roundtripped["aggregate"]["verdict"] == "PASS"
