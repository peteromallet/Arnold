"""Tests for T12: delta persistence in completion_verdict.json, exit-code
semantics, and structured telemetry emission.

Covers:
  (i)   verdict JSON contains ``green_suite.delta`` with all keys
  (ii)  runner_error path → unsatisfied with ``failures=['runner_error']``
  (iii) not_applicable path (genuine zero-collected on both sides)
  (iv)  baseline collected > 0 but verification collected == 0 → runner_error
  (v)   telemetry log line is emitted with the required fields
"""

from __future__ import annotations

import contextlib
import json
import logging
from pathlib import Path
from unittest import mock

import pytest

from arnold.pipelines.megaplan.orchestration.completion_contract import (
    COMPLETION_VERDICT_CONTRACT_VERSION,
    COMPLETION_VERDICT_SCHEMA,
    COMPLETION_VERDICT_SCHEMA_VERSION,
    CompletionContext,
    CompletionSubject,
    CompletionVerdict,
    EvidenceRef,
    EvidenceStatus,
    GreenSuiteProvider,
    TrustClass,
    compute_verdict,
)
from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _subject(name: str = "plan-x") -> CompletionSubject:
    return CompletionSubject(kind="plan", name=name, to_state="done", plan_name=name)


def _make_result(**overrides: object) -> SuiteRunResult:
    """Build a SuiteRunResult with sensible defaults, overridable by kwarg."""
    defaults: dict[str, object] = {
        "run_id": "fake-run-id",
        "phase": "verification",
        "command": "pytest --tb=no -q --no-header -rA",
        "duration": 0.1,
        "collected": 2,
        "collected_ids": ["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
        "failures": [],
        "passes": ["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
        "status": "passed",
        "exit_code": 0,
        "raw_log_path": Path("/dev/null"),
        "code_hash": "abc123",
        "collections_parse_ok": True,
    }
    defaults.update(overrides)
    return SuiteRunResult(**defaults)  # type: ignore[arg-type]


def _ctx(tmp_path: Path, **config_overrides: object) -> CompletionContext:
    """Create a CompletionContext rooted at *tmp_path*."""
    config: dict[str, object] = {
        "test_baseline_timeout": 900,
        "project_dir": str(tmp_path),
    }
    config.update(config_overrides)
    state: dict[str, object] = {"config": config}
    return CompletionContext(
        plan_dir=tmp_path,
        project_dir=tmp_path,
        state=state,
        subject=_subject(),
    )


def _mock_collect_deps(
    verification: SuiteRunResult,
    *,
    baseline: SuiteRunResult | None = None,
) -> list[mock._patch]:
    """Return mock patches needed for GreenSuiteProvider.collect to succeed."""
    patches: list[mock._patch] = []

    # Stub out append_suite_run (no-op).
    patches.append(
        mock.patch(
            "arnold.pipelines.megaplan.orchestration.suite_runner.append_suite_run",
        )
    )
    # Stub out _compute_code_hash to return a stable value.
    # Must mock at the source module (suite_runner) because collect() does
    # a fresh `from suite_runner import _compute_code_hash` each call.
    patches.append(
        mock.patch(
            "arnold.pipelines.megaplan.orchestration.suite_runner._compute_code_hash",
            return_value="abc123",
        )
    )
    # Stub freshness_skip to return None (no cache hit).
    patches.append(
        mock.patch(
            "arnold.pipelines.megaplan.orchestration.suite_runner.freshness_skip",
            return_value=None,
        )
    )
    # Stub out _read_finalize to return an empty dict.
    patches.append(
        mock.patch(
            "arnold.pipelines.megaplan.orchestration.completion_contract._read_finalize",
            return_value={},
        )
    )

    # Stub the baseline lookup.
    if baseline is not None:

        def _make_baseline_record(b: SuiteRunResult) -> dict[str, object]:
            return {
                "run_id": b.run_id,
                "phase": b.phase,
                "code_hash": b.code_hash,
                "command": b.command,
                "duration": b.duration,
                "collected": b.collected,
                "collected_ids": list(b.collected_ids),
                "failures": list(b.failures),
                "passes": list(b.passes),
                "status": b.status,
                "exit_code": b.exit_code,
                "raw_log_path": str(b.raw_log_path),
                "collections_parse_ok": b.collections_parse_ok,
            }

        patches.append(
            mock.patch(
                "arnold.pipelines.megaplan.orchestration.suite_runner.latest_run_for_phase",
                return_value=_make_baseline_record(baseline),
            )
        )
    else:
        patches.append(
            mock.patch(
                "arnold.pipelines.megaplan.orchestration.suite_runner.latest_run_for_phase",
                return_value=None,
            )
        )

    # Stub run_suite to return the verification result.
    patches.append(
        mock.patch(
            "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
            return_value=verification,
        )
    )

    return patches


# ---------------------------------------------------------------------------
# (i) verdict JSON contains green_suite.delta with all keys
# ---------------------------------------------------------------------------


def test_verdict_json_contains_green_suite_delta(tmp_path: Path) -> None:
    """The serialised completion_verdict.json has a top-level ``green_suite``
    key with ``delta`` containing all expected keys."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        status="passed",
    )
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        code_hash="abc123",  # same hash → baseline_stale=False
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    # Build a minimal verdict with just the green_suite evidence.
    verdict = CompletionVerdict(
        mode="shadow",
        subject=_subject(),
        evidence=(ref,),
        accepted=True,
    )
    verdict_dict = verdict.to_dict()

    # Top-level green_suite key exists.
    assert "green_suite" in verdict_dict
    gs = verdict_dict["green_suite"]
    assert isinstance(gs, dict)

    # delta is present.
    assert "delta" in gs
    delta = gs["delta"]
    assert isinstance(delta, dict)

    # All expected delta keys are present.
    expected_keys = {
        "computable",
        "newly_failing",
        "newly_passing",
        "still_red",
        "still_green",
        "deleted_tests",
        "added_tests",
        "flakes",
        "tests_collected",
        "duration",
        "flake_retry_skipped",
        "flake_retry_reason",
    }
    assert set(delta.keys()) == expected_keys

    # New telemetry fields (T14) are present at the verdict level.
    assert verdict_dict["schema"] == COMPLETION_VERDICT_SCHEMA
    assert verdict_dict["schema_version"] == COMPLETION_VERDICT_SCHEMA_VERSION
    assert verdict_dict["evidence_contract_version"] == COMPLETION_VERDICT_CONTRACT_VERSION
    assert "providers_used" in verdict_dict
    assert isinstance(verdict_dict["providers_used"], list)
    assert "legacy_evidence_count" in verdict_dict
    assert isinstance(verdict_dict["legacy_evidence_count"], int)
    assert "unknown_evidence_count" in verdict_dict
    assert isinstance(verdict_dict["unknown_evidence_count"], int)
    assert "would_block_reasons" in verdict_dict
    assert isinstance(verdict_dict["would_block_reasons"], list)


def test_evidence_details_contain_required_fields(tmp_path: Path) -> None:
    """The green_suite EvidenceRef details contain flake_retried, baseline_stale,
    and delta.computable."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        status="passed",
    )
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        code_hash="abc123",
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    details = ref.details
    assert "flake_retried" in details
    assert isinstance(details["flake_retried"], bool)
    assert "baseline_stale" in details
    assert isinstance(details["baseline_stale"], bool)
    assert "delta.computable" in details
    assert isinstance(details["delta.computable"], bool)


def test_green_suite_evidence_ref_is_enriched_with_provenance(
    tmp_path: Path,
) -> None:
    """Green suite evidence carries deterministic provenance from available artifacts."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()
    verification_dir = tmp_path / "verification"
    verification_dir.mkdir(exist_ok=True)
    raw_log = verification_dir / "raw_vf-1.log"
    raw_log.write_text("PASSED tests/test_a.py::test_x\n", encoding="utf-8")
    suite_log = verification_dir / "suite_runs.ndjson"
    suite_log.write_text(
        json.dumps(
            {
                "run_id": "vf-1",
                "phase": "verification",
                "code_hash": "abc123",
                "command": "pytest --tb=no -q --no-header -rA",
                "duration": 0.1,
                "collected": 2,
                "collected_ids": ["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
                "failures": [],
                "passes": ["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
                "status": "passed",
                "raw_log_path": str(raw_log),
                "collections_parse_ok": True,
                "ts": "2026-06-07T20:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        raw_log_path=raw_log,
        code_hash="abc123",
        status="passed",
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=None):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    assert ref.trust_class == TrustClass.evidence
    assert ref.provider == "GreenSuiteProvider"
    assert ref.provider_version == "1"
    assert ref.source == "verification:vf-1"
    assert ref.subject == "plan:plan-x"
    assert ref.observed_at == "2026-06-07T20:00:00Z"
    assert ref.code_hash == "abc123"
    assert ref.artifact is not None
    assert ref.artifact.path == "verification/raw_vf-1.log"
    assert [artifact.path for artifact in ref.artifacts] == [
        "verification/raw_vf-1.log",
        "verification/suite_runs.ndjson",
    ]
    assert ref.details["suite_run_log_path"] == "verification/suite_runs.ndjson"
    assert ref.details["suite_run_log_ts"] == "2026-06-07T20:00:00Z"
    assert ref.details["evidence_id"].startswith("sha256:")
    assert len(ref.details["artifact_refs"]) == 2


def test_green_suite_evidence_id_is_deterministic_for_same_inputs(
    tmp_path: Path,
) -> None:
    """The evidence id is stable for the same subject, run facts, and artifacts."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()
    verification_dir = tmp_path / "verification"
    verification_dir.mkdir(exist_ok=True)
    raw_log = verification_dir / "raw_vf-1.log"
    raw_log.write_text("PASSED tests/test_a.py::test_x\n", encoding="utf-8")
    suite_log = verification_dir / "suite_runs.ndjson"
    suite_log.write_text(
        json.dumps(
            {
                "run_id": "vf-1",
                "phase": "verification",
                "code_hash": "abc123",
                "command": "pytest --tb=no -q --no-header -rA",
                "duration": 0.1,
                "collected": 2,
                "collected_ids": ["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
                "failures": [],
                "passes": ["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
                "status": "passed",
                "raw_log_path": str(raw_log),
                "collections_parse_ok": True,
                "ts": "2026-06-07T20:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        raw_log_path=raw_log,
        code_hash="abc123",
        status="passed",
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=None):
            stack.enter_context(p)
        first = provider.collect(ctx)
        second = provider.collect(ctx)

    assert first.details["evidence_id"] == second.details["evidence_id"]


def test_baseline_stale_true_when_code_hash_differs(tmp_path: Path) -> None:
    """baseline_stale is True when baseline.code_hash != current_code_hash."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        code_hash="xyz789",
        status="passed",
    )
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        code_hash="old456",  # differs from current "abc123"
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    assert ref.details["baseline_stale"] is True


def test_baseline_stale_false_when_code_hash_matches(tmp_path: Path) -> None:
    """baseline_stale is False when baseline.code_hash == current_code_hash."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        code_hash="abc123",
        status="passed",
    )
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        code_hash="abc123",  # same as _compute_code_hash mock
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    assert ref.details["baseline_stale"] is False


# ---------------------------------------------------------------------------
# (ii) runner_error path → unsatisfied with failures=['runner_error']
# ---------------------------------------------------------------------------


def test_runner_error_returns_unsatisfied_with_failures(tmp_path: Path) -> None:
    """When verification status is runner_error, evidence is unsatisfied
    and details.failures contains ['runner_error']."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        status="runner_error",
        exit_code=2,
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=None):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    assert ref.status == EvidenceStatus.unsatisfied
    assert ref.details.get("failures") == ["runner_error"]
    assert "runner error" in ref.summary.lower()


def test_timeout_returns_unsatisfied_with_failures(tmp_path: Path) -> None:
    """When verification status is timeout, evidence is unsatisfied
    and details.failures contains ['runner_error']."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        status="timeout",
        exit_code=None,
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=None):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    assert ref.status == EvidenceStatus.unsatisfied
    assert ref.details.get("failures") == ["runner_error"]
    assert "timed out" in ref.summary.lower()


# ---------------------------------------------------------------------------
# (iii) not_applicable path — genuine zero-collected on both sides
# ---------------------------------------------------------------------------


def test_not_applicable_genuine_zero_collected(tmp_path: Path) -> None:
    """When both baseline and verification collected zero, evidence is
    not_applicable."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        status="not_applicable",
        exit_code=5,
        collected=0,
        collected_ids=[],
        failures=[],
        passes=[],
    )
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected=0,
        collected_ids=[],
        failures=[],
        passes=[],
        status="not_applicable",
        exit_code=5,
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    assert ref.status == EvidenceStatus.not_applicable
    assert "not applicable" in ref.summary.lower()
    # No runner_error failures — genuine not_applicable.
    # (failures key absent or empty; not ['runner_error'])
    assert ref.details.get("failures") != ["runner_error"]


def test_not_applicable_no_baseline_is_still_not_applicable(
    tmp_path: Path,
) -> None:
    """When there is no baseline record and verification collects zero,
    it is still not_applicable (baseline_collected defaults to 0)."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        status="not_applicable",
        exit_code=5,
        collected=0,
        collected_ids=[],
        failures=[],
        passes=[],
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=None):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    assert ref.status == EvidenceStatus.not_applicable


# ---------------------------------------------------------------------------
# (iv) baseline collected > 0 but verification collected == 0 → runner_error
# ---------------------------------------------------------------------------


def test_baseline_collected_but_verification_zero_is_runner_error(
    tmp_path: Path,
) -> None:
    """When baseline collected tests but verification collected zero,
    this is a runner_error (silent partial-drop not tolerated)."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        status="not_applicable",
        exit_code=5,
        collected=0,
        collected_ids=[],
        failures=[],
        passes=[],
    )
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected=5,
        collected_ids=[f"tests/test_x.py::test_{i}" for i in range(5)],
        failures=[],
        passes=[f"tests/test_x.py::test_{i}" for i in range(5)],
        status="passed",
        exit_code=0,
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    assert ref.status == EvidenceStatus.unsatisfied
    assert ref.details.get("failures") == ["runner_error"]
    assert "partial-drop" in ref.summary.lower()
    assert "baseline collected 5" in ref.summary.lower()


# ---------------------------------------------------------------------------
# (v) telemetry log line is emitted with required fields
# ---------------------------------------------------------------------------


def test_telemetry_line_is_emitted_on_passed_run(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A structured telemetry log line is emitted for a passed run
    with the required fields."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        status="passed",
        code_hash="abc123",
        duration=2.5,
    )
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        code_hash="abc123",
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        with caplog.at_level(logging.INFO, logger="megaplan.orchestration.completion_contract"):
            provider.collect(ctx)

    # Find the telemetry log line.
    telemetry_lines = [
        r.message
        for r in caplog.records
        if "green_suite telemetry" in r.message
    ]
    assert len(telemetry_lines) == 1
    msg = telemetry_lines[0]

    # Verify all required fields are present.
    assert "mode=" in msg
    assert "status=passed" in msg
    assert "newly_failing=" in msg
    assert "deleted_tests=" in msg
    assert "duration=" in msg
    assert "code_hash=abc123" in msg
    assert "freshness_skip=" in msg


def test_telemetry_line_is_emitted_on_failed_run(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Telemetry is emitted for failed runs with correct status and counts."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        status="failed",
        failures=["tests/test_a.py::test_x"],
        passes=["tests/test_b.py::test_y"],
        code_hash="abc123",
        duration=1.2,
    )
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        code_hash="abc123",
        failures=[],
        passes=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        with caplog.at_level(logging.INFO, logger="megaplan.orchestration.completion_contract"):
            provider.collect(ctx)

    telemetry_lines = [
        r.message
        for r in caplog.records
        if "green_suite telemetry" in r.message
    ]
    assert len(telemetry_lines) == 1
    msg = telemetry_lines[0]

    assert "status=failed" in msg
    assert "newly_failing=1" in msg
    assert "duration=1.20" in msg


def test_telemetry_line_is_emitted_on_runner_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Telemetry is emitted for runner_error runs."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        status="runner_error",
        exit_code=2,
        code_hash="abc123",
        duration=0.0,
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=None):
            stack.enter_context(p)
        with caplog.at_level(logging.INFO, logger="megaplan.orchestration.completion_contract"):
            provider.collect(ctx)

    telemetry_lines = [
        r.message
        for r in caplog.records
        if "green_suite telemetry" in r.message
    ]
    assert len(telemetry_lines) == 1
    msg = telemetry_lines[0]

    assert "status=runner_error" in msg
    assert "newly_failing=0" in msg
    assert "freshness_skip=false" in msg


def test_telemetry_includes_freshness_skip_true(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Telemetry shows freshness_skip=true when cache hit occurred."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    cached_result = _make_result(
        run_id="vf-cached",
        phase="verification",
        status="passed",
        code_hash="abc123",
    )

    with contextlib.ExitStack() as stack:
        # Mock append_suite_run (no-op)
        stack.enter_context(
            mock.patch(
                "arnold.pipelines.megaplan.orchestration.suite_runner.append_suite_run",
            )
        )
        # Mock _compute_code_hash (at source module, see note above)
        stack.enter_context(
            mock.patch(
                "arnold.pipelines.megaplan.orchestration.suite_runner._compute_code_hash",
                return_value="abc123",
            )
        )
        # Mock freshness_skip to return a cached result (cache hit!)
        stack.enter_context(
            mock.patch(
                "arnold.pipelines.megaplan.orchestration.suite_runner.freshness_skip",
                return_value=cached_result,
            )
        )
        # Mock _read_finalize
        stack.enter_context(
            mock.patch(
                "arnold.pipelines.megaplan.orchestration.completion_contract._read_finalize",
                return_value={},
            )
        )

        with caplog.at_level(logging.INFO, logger="megaplan.orchestration.completion_contract"):
            provider.collect(ctx)

    telemetry_lines = [
        r.message
        for r in caplog.records
        if "green_suite telemetry" in r.message
    ]
    assert len(telemetry_lines) == 1
    msg = telemetry_lines[0]

    assert "freshness_skip=true" in msg
    assert "status=passed" in msg


def test_telemetry_includes_deleted_tests_count(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Telemetry shows correct deleted_tests count."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        status="passed",
        collected_ids=["tests/test_b.py::test_y"],
        failures=[],
        passes=["tests/test_b.py::test_y"],
        collected=1,
        code_hash="abc123",
    )
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=[
            "tests/test_a.py::test_x",
            "tests/test_b.py::test_y",
        ],
        failures=[],
        passes=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
        collected=2,
        code_hash="abc123",
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        with caplog.at_level(logging.INFO, logger="megaplan.orchestration.completion_contract"):
            provider.collect(ctx)

    telemetry_lines = [
        r.message
        for r in caplog.records
        if "green_suite telemetry" in r.message
    ]
    assert len(telemetry_lines) == 1
    msg = telemetry_lines[0]

    # test_a was deleted (baseline had it, verification doesn't)
    assert "deleted_tests=1" in msg


# ---------------------------------------------------------------------------
# (vi) Verdict one_line and to_dict include T14 telemetry fields
# ---------------------------------------------------------------------------


def test_verdict_one_line_includes_telemetry_fields() -> None:
    """``CompletionVerdict.one_line()`` surfaces providers, legacy_evidence,
    and unknown_evidence when populated."""
    ref = EvidenceRef(
        kind="green_suite",
        status=EvidenceStatus.satisfied,
        summary="passed",
        details={"status": "passed", "code_hash": "abc123"},
    )
    verdict = CompletionVerdict(
        mode="shadow",
        subject=_subject(),
        evidence=(ref,),
        accepted=True,
        providers_used=("green_suite", "phase_coverage"),
        legacy_evidence_count=2,
        unknown_evidence_count=0,
    )
    line = verdict.one_line()

    # Check individual fields without requiring full-text format.
    assert "providers=[green_suite,phase_coverage]" in line
    assert "legacy_evidence=2" in line
    assert "unknown_evidence=0" in line
    assert "completion verdict" in line
    assert "accepted" in line


def test_verdict_one_line_defaults_when_no_providers() -> None:
    """``one_line()`` shows ``providers=[none]`` when providers_used is empty."""
    verdict = CompletionVerdict(
        mode="shadow",
        subject=_subject(),
        evidence=(),
        accepted=False,
    )
    line = verdict.one_line()
    assert "providers=[none]" in line
    assert "legacy_evidence=0" in line
    assert "unknown_evidence=0" in line


def test_verdict_to_dict_surfaces_telemetry_when_set(
    tmp_path: Path,
) -> None:
    """``to_dict()`` surfaces providers_used, counts, and would_block_reasons
    when they are populated by the verdict (e.g. via compute_verdict path)."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        status="passed",
        code_hash="abc123",
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=None):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    verdict = CompletionVerdict(
        mode="shadow",
        subject=_subject(),
        evidence=(ref,),
        accepted=True,
        providers_used=("green_suite",),
        legacy_evidence_count=0,
        unknown_evidence_count=0,
        would_block_reasons=(),
    )
    d = verdict.to_dict()

    assert d["providers_used"] == ["green_suite"]
    assert d["legacy_evidence_count"] == 0
    assert d["unknown_evidence_count"] == 0
    assert d["would_block_reasons"] == []
