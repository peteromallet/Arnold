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
