from arnold_pipelines.megaplan.cloud.progress_auditor_liveness import (
    classify_runner_liveness,
)


def test_unknown_tmux_without_corroboration_stays_unknown() -> None:
    result = classify_runner_liveness({"live_status": "unknown"}, {}, [])

    assert result["state"] == "unknown"
    assert result["known"] is False
    assert result["live"] is False
    assert result["dead"] is False


def test_canonical_launch_evidence_missing_proves_runner_dead() -> None:
    result = classify_runner_liveness(
        {"live_status": "unknown"},
        {},
        ["canonical_launch_evidence_missing"],
    )

    assert result["state"] == "dead"
    assert result["known"] is True
    assert result["dead"] is True


def test_live_process_evidence_overrides_stale_absence_signal() -> None:
    result = classify_runner_liveness(
        {"pid_live": True, "live_status": "alive"},
        {},
        ["canonical_launch_evidence_missing"],
    )

    assert result["state"] == "alive"
    assert result["live"] is True


def test_terminal_repair_failure_proves_no_repair_runner_without_live_override() -> None:
    result = classify_runner_liveness(
        {"live_status": "unknown"},
        {},
        ["dispatched", "terminal_repair_failure"],
    )

    assert result["state"] == "dead"
    assert result["source"] == "explicit_absence_evidence"


# ═══════════════════════════════════════════════════════════════════════════
# M9 T61: Liveness reason fixtures — deterministic evidence-bound reasons
#
# These tie liveness classification results to exact evidence IDs so
# watchdog and auditor consumers can agree on liveness evidence.
# ═══════════════════════════════════════════════════════════════════════════

import hashlib as _hashlib_liveness


def _liveness_evidence_id(state: str, source: str, known: bool) -> str:
    """Content-addressed evidence ID for liveness classifications."""
    payload = f"liveness:{state}:{source}:{known}"
    return f"liveness:sha256:{_hashlib_liveness.sha256(payload.encode()).hexdigest()[:16]}"


class TestLivenessReasonFixtures:
    """Liveness reason fixtures — deterministic, evidence-bound, once-only."""

    def test_liveness_evidence_id_deterministic(self):
        """Same liveness classification must produce the same evidence ID."""
        eid1 = _liveness_evidence_id("alive", "live_process_evidence", True)
        eid2 = _liveness_evidence_id("alive", "live_process_evidence", True)
        assert eid1 == eid2
        assert eid1.startswith("liveness:sha256:")

    def test_liveness_evidence_id_differs_by_state(self):
        """Different liveness states must produce different evidence IDs."""
        eid_alive = _liveness_evidence_id("alive", "live_process_evidence", True)
        eid_dead = _liveness_evidence_id("dead", "explicit_absence_evidence", True)
        eid_unknown = _liveness_evidence_id("unknown", "insufficient_liveness_evidence", False)
        assert len({eid_alive, eid_dead, eid_unknown}) == 3

    def test_classify_runner_liveness_alive_produces_deterministic_evidence(self):
        """Live process evidence must produce a deterministic evidence-bound reason."""
        result = classify_runner_liveness(
            {"pid_live": True, "live_status": "alive"},
            {},
            [],
        )
        assert result["state"] == "alive"
        eid = _liveness_evidence_id(result["state"], result["source"], result["known"])
        assert eid.startswith("liveness:sha256:")
        # Same inputs → same evidence ID
        result2 = classify_runner_liveness(
            {"pid_live": True, "live_status": "alive"},
            {},
            [],
        )
        eid2 = _liveness_evidence_id(result2["state"], result2["source"], result2["known"])
        assert eid == eid2

    def test_classify_runner_liveness_dead_produces_deterministic_evidence(self):
        """Dead runner evidence must produce a deterministic evidence-bound reason."""
        result = classify_runner_liveness(
            {"live_status": "unknown"},
            {},
            ["canonical_launch_evidence_missing"],
        )
        assert result["state"] == "dead"
        eid = _liveness_evidence_id(result["state"], result["source"], result["known"])
        assert eid.startswith("liveness:sha256:")

    def test_classify_runner_liveness_unknown_produces_deterministic_evidence(self):
        """Unknown liveness must produce a deterministic evidence-bound reason."""
        result = classify_runner_liveness({"live_status": "unknown"}, {}, [])
        assert result["state"] == "unknown"
        eid = _liveness_evidence_id(result["state"], result["source"], result["known"])
        assert eid.startswith("liveness:sha256:")
