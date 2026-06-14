from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from arnold.pipelines.megaplan.calibration import (
    CALIBRATION_EXPERIMENT_EVENT_KIND,
    CalibrationExperimentFinding,
    CheapestRoutingExperiment,
    MonocultureExperiment,
    run_cheapest_routing_experiment,
    run_monoculture_experiment,
    write_experiment_finding,
)
from arnold.pipelines.megaplan.calibration.experiments import (
    _canonical_json,
    _compute_cheap_route_pressure,
)
from arnold.pipelines.megaplan.observability.events import EventKind, _ALL_EVENT_KINDS, read_events


@pytest.fixture
def plan_dir(tmp_path: Path) -> Path:
    root = tmp_path / "plan"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_shared_finding_to_json_and_hash_are_deterministic() -> None:
    first = CalibrationExperimentFinding(
        experiment_name="shared",
        inputs_summary={"phase": "execute", "ratio": 0.5},
        findings=("one", "two"),
        recorded_at=123.0,
    )
    second = CalibrationExperimentFinding(
        experiment_name="shared",
        inputs_summary={"phase": "execute", "ratio": 0.5},
        findings=("one", "two"),
        recorded_at=123.0,
    )

    assert first.to_json() == {
        "experiment_name": "shared",
        "inputs_summary": {"phase": "execute", "ratio": 0.5},
        "findings": ["one", "two"],
        "governs_live_policy": False,
        "recorded_at": 123.0,
    }
    assert first.content_hash == second.content_hash


def test_cheapest_routing_experiment_captures_inputs_summary() -> None:
    finding = CheapestRoutingExperiment(
        phase="execute",
        cheap_route_pressure=0.91,
        prefix_cache_hit_rate=0.22,
        tension_threshold=0.75,
        findings=("cheap route pressure is high while caching is weak",),
        recorded_at=456.0,
    )

    assert finding.experiment_name == "cheapest_routing"
    assert finding.inputs_summary == {
        "phase": "execute",
        "cheap_route_pressure": 0.91,
        "prefix_cache_hit_rate": 0.22,
        "tension_threshold": 0.75,
    }
    assert finding.governs_live_policy is False
    assert "content_hash" not in finding.to_json()


def test_monoculture_experiment_hash_changes_when_inputs_change() -> None:
    first = MonocultureExperiment(
        phase="review",
        monoculture_index=0.81,
        low_confidence_claim_count=3,
        filtered_claim_count=5,
        attractor_threshold=0.7,
        findings=("monoculture attractor detected",),
        recorded_at=789.0,
    )
    second = MonocultureExperiment(
        phase="review",
        monoculture_index=0.91,
        low_confidence_claim_count=3,
        filtered_claim_count=5,
        attractor_threshold=0.7,
        findings=("monoculture attractor detected",),
        recorded_at=789.0,
    )

    assert first.experiment_name == "monoculture"
    assert first.content_hash != second.content_hash


def test_write_experiment_finding_requires_target(
    plan_dir: Path,
) -> None:
    finding = CheapestRoutingExperiment(
        phase="execute",
        cheap_route_pressure=0.8,
        prefix_cache_hit_rate=0.1,
        tension_threshold=0.7,
        findings=("pressure exceeds threshold",),
        recorded_at=111.0,
    )

    with pytest.raises(ValueError, match="plan_dir=.*event_sink="):
        write_experiment_finding(finding)


def test_write_experiment_finding_via_plan_dir_records_event(plan_dir: Path) -> None:
    finding = CheapestRoutingExperiment(
        phase="execute",
        cheap_route_pressure=0.8,
        prefix_cache_hit_rate=0.1,
        tension_threshold=0.7,
        findings=("pressure exceeds threshold",),
        recorded_at=111.0,
    )

    event = write_experiment_finding(finding, plan_dir=plan_dir, scope="calibration")

    assert event["kind"] == CALIBRATION_EXPERIMENT_EVENT_KIND
    assert event["phase"] == "execute"

    events = list(read_events(plan_dir))
    assert len(events) == 1
    assert events[0]["kind"] == CALIBRATION_EXPERIMENT_EVENT_KIND
    assert events[0]["phase"] == "execute"
    assert events[0]["payload"]["experiment_name"] == "cheapest_routing"
    assert events[0]["payload"]["governs_live_policy"] is False
    assert events[0]["payload"]["scope"] == "calibration"
    assert events[0]["payload"]["idempotency_key"] == finding.content_hash


def test_write_experiment_finding_via_event_sink_uses_payload_and_hash() -> None:
    finding = MonocultureExperiment(
        phase="review",
        monoculture_index=0.81,
        low_confidence_claim_count=3,
        filtered_claim_count=5,
        attractor_threshold=0.7,
        findings=("monoculture attractor detected",),
        recorded_at=789.0,
    )
    captured: dict[str, object] = {}

    class FakeSink:
        def emit(self, kind: str, **kwargs: object) -> dict[str, object]:
            captured["kind"] = kind
            captured.update(kwargs)
            return {"kind": kind, **kwargs}

    write_experiment_finding(finding, event_sink=FakeSink(), scope="oracle")

    assert captured["kind"] == CALIBRATION_EXPERIMENT_EVENT_KIND
    assert captured["phase"] == "review"
    assert captured["scope"] == "oracle"
    assert captured["idempotency_key"] == finding.content_hash
    assert captured["payload"] == finding.to_json()


# ---------------------------------------------------------------------------
# Experiment feeder tests
# ---------------------------------------------------------------------------


def _claim(
    predicted_tier: int | None = None,
    low_confidence_signal: bool = False,
    taint_class: str | None = None,
) -> SimpleNamespace:
    """Build a minimal claim-like object for feeder tests."""
    return SimpleNamespace(
        predicted_tier=predicted_tier,
        low_confidence_signal=low_confidence_signal,
        taint_class=taint_class,
    )


def _cost_agg(
    phase_prefix_cache_hit_rate: dict[str, float] | None = None,
    monoculture_index: float = 0.0,
) -> dict[str, Any]:
    """Build a minimal cost aggregate dict for feeder tests."""
    return {
        "phase_prefix_cache_hit_rate": phase_prefix_cache_hit_rate or {},
        "monoculture_index": monoculture_index,
    }


class TestComputeCheapRoutePressure:
    def test_empty_claims_returns_zero(self) -> None:
        assert _compute_cheap_route_pressure([]) == 0.0

    def test_all_cheap_claims_returns_one(self) -> None:
        claims = [_claim(1), _claim(2), _claim(1)]
        assert _compute_cheap_route_pressure(claims) == 1.0

    def test_no_cheap_claims_returns_zero(self) -> None:
        claims = [_claim(3), _claim(4), _claim(5)]
        assert _compute_cheap_route_pressure(claims) == 0.0

    def test_mixed_claims_returns_proportion(self) -> None:
        claims = [_claim(1), _claim(3), _claim(2), _claim(4)]
        assert _compute_cheap_route_pressure(claims) == 0.5

    def test_none_tier_excluded_from_count(self) -> None:
        claims = [_claim(None), _claim(1), _claim(3)]
        # 1 cheap (tier=1) out of 3 total = 1/3
        assert _compute_cheap_route_pressure(claims) == pytest.approx(1.0 / 3.0)


class TestRunCheapestRoutingExperiment:
    def test_no_tension_when_pressure_below_threshold(self) -> None:
        agg = _cost_agg({"execute": 0.1}, monoculture_index=0.5)
        claims = [_claim(3), _claim(4)]  # pressure = 0/2 = 0.0
        result = run_cheapest_routing_experiment(
            cost_aggregate=agg,
            claims=claims,
            phase="execute",
            tension_threshold=0.75,
            cache_hit_low_threshold=0.3,
            recorded_at=100.0,
        )
        assert result is None

    def test_no_tension_when_cache_hit_high(self) -> None:
        agg = _cost_agg({"execute": 0.5}, monoculture_index=0.5)
        claims = [_claim(1), _claim(2), _claim(1)]  # pressure = 1.0
        result = run_cheapest_routing_experiment(
            cost_aggregate=agg,
            claims=claims,
            phase="execute",
            tension_threshold=0.75,
            cache_hit_low_threshold=0.3,
            recorded_at=100.0,
        )
        assert result is None

    def test_tension_detected_when_pressure_high_cache_low(self) -> None:
        agg = _cost_agg({"execute": 0.15}, monoculture_index=0.5)
        claims = [_claim(1), _claim(2), _claim(1), _claim(2)]
        result = run_cheapest_routing_experiment(
            cost_aggregate=agg,
            claims=claims,
            phase="execute",
            tension_threshold=0.75,
            cache_hit_low_threshold=0.3,
            recorded_at=100.0,
        )
        assert result is not None
        assert result.experiment_name == "cheapest_routing"
        assert result.cheap_route_pressure == 1.0
        assert result.prefix_cache_hit_rate == 0.15
        assert result.tension_threshold == 0.75
        assert result.governs_live_policy is False
        assert "content_hash" not in result.to_json()

    def test_deterministic_for_identical_inputs(self) -> None:
        agg = _cost_agg({"execute": 0.15}, monoculture_index=0.5)
        claims = [_claim(1), _claim(2)]
        a = run_cheapest_routing_experiment(
            cost_aggregate=agg,
            claims=claims,
            phase="execute",
            recorded_at=100.0,
        )
        b = run_cheapest_routing_experiment(
            cost_aggregate=agg,
            claims=claims,
            phase="execute",
            recorded_at=100.0,
        )
        assert a is not None
        assert b is not None
        assert a.to_json() == b.to_json()
        assert a.content_hash == b.content_hash

    def test_missing_cache_hit_phase_defaults_zero(self) -> None:
        agg = _cost_agg({}, monoculture_index=0.5)
        claims = [_claim(1), _claim(2)]
        result = run_cheapest_routing_experiment(
            cost_aggregate=agg,
            claims=claims,
            phase="execute",
            tension_threshold=0.75,
            cache_hit_low_threshold=0.3,
            recorded_at=100.0,
        )
        # cache_hit=0.0 -> below low threshold; pressure=1.0 -> above
        assert result is not None
        assert result.prefix_cache_hit_rate == 0.0


class TestRunMonocultureExperiment:
    def test_no_attractor_when_index_below_threshold(self) -> None:
        agg = _cost_agg({"execute": 0.5}, monoculture_index=0.5)
        claims: list[Any] = []
        result = run_monoculture_experiment(
            cost_aggregate=agg,
            claims=claims,
            phase="execute",
            attractor_threshold=0.7,
            recorded_at=100.0,
        )
        assert result is None

    def test_attractor_detected_when_index_above_threshold(self) -> None:
        agg = _cost_agg({"execute": 0.5}, monoculture_index=0.85)
        claims = [_claim(1, low_confidence_signal=True), _claim(3)]
        result = run_monoculture_experiment(
            cost_aggregate=agg,
            claims=claims,
            phase="execute",
            attractor_threshold=0.7,
            recorded_at=100.0,
        )
        assert result is not None
        assert result.experiment_name == "monoculture"
        assert result.monoculture_index == 0.85
        assert result.attractor_threshold == 0.7
        assert result.low_confidence_claim_count == 1
        assert result.filtered_claim_count >= 0
        assert result.governs_live_policy is False
        assert "content_hash" not in result.to_json()

    def test_counts_low_confidence_and_filtered_claims(self) -> None:
        agg = _cost_agg({"execute": 0.5}, monoculture_index=0.9)
        claims = [
            _claim(1, low_confidence_signal=True),
            _claim(2, low_confidence_signal=True),
            _claim(3, low_confidence_signal=False),
            _claim(4, low_confidence_signal=False),
        ]
        result = run_monoculture_experiment(
            cost_aggregate=agg,
            claims=claims,
            phase="review",
            attractor_threshold=0.7,
            recorded_at=100.0,
        )
        assert result is not None
        assert result.low_confidence_claim_count == 2
        # filtered: low_confidence_signal=True makes claims non-shared (2)
        # plus no tainted claims → total filtered = 2
        assert result.filtered_claim_count == 2

    def test_tainted_claims_are_filtered(self) -> None:
        """Claims with taint_class != None default to TENANT_LOCAL (filtered)."""
        agg = _cost_agg({"execute": 0.5}, monoculture_index=0.9)
        claims = [
            _claim(1, taint_class="private"),
            _claim(2),
        ]
        result = run_monoculture_experiment(
            cost_aggregate=agg,
            claims=claims,
            phase="execute",
            attractor_threshold=0.7,
            recorded_at=100.0,
        )
        assert result is not None
        assert result.filtered_claim_count == 1

    def test_deterministic_for_identical_inputs(self) -> None:
        agg = _cost_agg({"execute": 0.5}, monoculture_index=0.85)
        claims = [_claim(1, low_confidence_signal=True)]
        a = run_monoculture_experiment(
            cost_aggregate=agg,
            claims=claims,
            phase="execute",
            recorded_at=100.0,
        )
        b = run_monoculture_experiment(
            cost_aggregate=agg,
            claims=claims,
            phase="execute",
            recorded_at=100.0,
        )
        assert a is not None
        assert b is not None
        assert a.to_json() == b.to_json()
        assert a.content_hash == b.content_hash

    def test_missing_monoculture_index_defaults_zero(self) -> None:
        agg: dict[str, Any] = {"phase_prefix_cache_hit_rate": {}}
        claims: list[Any] = []
        result = run_monoculture_experiment(
            cost_aggregate=agg,
            claims=claims,
            phase="execute",
            attractor_threshold=0.7,
            recorded_at=100.0,
        )
        # index=0.0 -> below 0.7, no finding
        assert result is None


# ---------------------------------------------------------------------------
# EventKind registration + canonical JSON tests
# ---------------------------------------------------------------------------


def test_calibration_experiment_event_kind_is_registered() -> None:
    """CALIBRATION_EXPERIMENT_EVENT_KIND is a member of EventKind and
    included in _ALL_EVENT_KINDS."""
    assert hasattr(EventKind, "CALIBRATION_EXPERIMENT")
    assert EventKind.CALIBRATION_EXPERIMENT == "calibration_experiment"
    assert CALIBRATION_EXPERIMENT_EVENT_KIND == EventKind.CALIBRATION_EXPERIMENT
    assert EventKind.CALIBRATION_EXPERIMENT in _ALL_EVENT_KINDS


def test_canonical_json_is_deterministic() -> None:
    """_canonical_json produces identical output for identical input
    regardless of insertion order in underlying dict."""
    a = {"z": 1, "a": 2, "nested": {"b": 3, "c": 4}}
    b = {"a": 2, "nested": {"c": 4, "b": 3}, "z": 1}
    assert _canonical_json(a) == _canonical_json(b)
    # Verify sorted, compact form
    result = _canonical_json(a)
    assert result == '{"a":2,"nested":{"b":3,"c":4},"z":1}'


def test_canonical_json_handles_sequences() -> None:
    """_canonical_json round-trips lists, tuples, and nested structures."""
    import json as _json

    value = {
        "tags": ("alpha", "beta"),
        "scores": [3, 1, 2],
        "meta": {"v": 1},
    }
    encoded = _canonical_json(value)
    decoded = _json.loads(encoded)
    assert decoded["tags"] == ["alpha", "beta"]
    assert decoded["scores"] == [3, 1, 2]
    assert decoded["meta"] == {"v": 1}


def test_governs_live_policy_always_false_in_payload() -> None:
    """Every CalibrationExperimentFinding subclass hard-codes
    governs_live_policy=False in its to_json() payload."""
    base = CalibrationExperimentFinding(
        experiment_name="any",
        inputs_summary={"k": "v"},
        findings=("f1",),
        recorded_at=1.0,
    )
    assert base.to_json()["governs_live_policy"] is False
    assert base.governs_live_policy is False

    cheap = CheapestRoutingExperiment(
        phase="execute",
        cheap_route_pressure=0.5,
        prefix_cache_hit_rate=0.5,
        tension_threshold=0.8,
        findings=("tension",),
        recorded_at=2.0,
    )
    assert cheap.to_json()["governs_live_policy"] is False
    assert cheap.governs_live_policy is False

    mono = MonocultureExperiment(
        phase="review",
        monoculture_index=0.1,
        low_confidence_claim_count=0,
        filtered_claim_count=0,
        attractor_threshold=0.5,
        findings=("none",),
        recorded_at=3.0,
    )
    assert mono.to_json()["governs_live_policy"] is False
    assert mono.governs_live_policy is False


def test_content_hash_excludes_itself_from_payload() -> None:
    """content_hash is computed from to_json() which does NOT contain
    a 'content_hash' key — preventing recursive drift."""
    finding = CalibrationExperimentFinding(
        experiment_name="hash-test",
        inputs_summary={"x": 1},
        findings=("stable",),
        recorded_at=42.0,
    )
    payload = finding.to_json()
    assert "content_hash" not in payload
    # Hash is stable under repeated calls
    h1 = finding.content_hash
    h2 = finding.content_hash
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


def test_content_hash_changes_when_findings_differ() -> None:
    """Stable content hashes must differ when any finding field changes."""
    a = CalibrationExperimentFinding(
        experiment_name="test",
        inputs_summary={"k": "v"},
        findings=("one",),
        recorded_at=1.0,
    )
    b = CalibrationExperimentFinding(
        experiment_name="test",
        inputs_summary={"k": "v"},
        findings=("two",),
        recorded_at=1.0,
    )
    assert a.content_hash != b.content_hash


def test_event_kind_in_written_event_matches_eventkind_enum(
    plan_dir: Path,
) -> None:
    """When written via plan_dir, the emitted event's 'kind' field
    equals the EventKind.CALIBRATION_EXPERIMENT value."""
    finding = CalibrationExperimentFinding(
        experiment_name="ev",
        inputs_summary={},
        findings=("f",),
        recorded_at=1.0,
    )
    event = write_experiment_finding(finding, plan_dir=plan_dir, scope="test")
    assert event["kind"] == EventKind.CALIBRATION_EXPERIMENT
    assert event["kind"] == "calibration_experiment"
