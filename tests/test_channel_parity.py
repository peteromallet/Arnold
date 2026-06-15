from arnold.pipelines.megaplan.orchestration.channel_parity import compare_channel_parity


def _summary(**overrides):
    data = {
        "exit_kind": "success",
        "payload_schema_valid": True,
        "landed_diff": "satisfied",
        "worker_did_work": "satisfied",
        "latency_ms": 1000,
        "cost_usd": 0.02,
        "total_tokens": 100,
    }
    data.update(overrides)
    return data


def test_channel_parity_passes_matching_semantics() -> None:
    result = compare_channel_parity(_summary(), _summary())

    assert result["passed"] is True
    assert result["details"]["drift"]["latency_drift_ms"] == 0


def test_channel_parity_fails_schema_invalid() -> None:
    result = compare_channel_parity(_summary(), _summary(payload_schema_valid=False))

    assert result["passed"] is False
    assert result["payload_schema_valid_match"] is False


def test_channel_parity_fails_landed_diff_mismatch() -> None:
    result = compare_channel_parity(_summary(), _summary(landed_diff="missing"))

    assert result["passed"] is False
    assert result["landed_diff_match"] is False


def test_channel_parity_fails_worker_did_work_mismatch() -> None:
    result = compare_channel_parity(_summary(), _summary(worker_did_work="missing"))

    assert result["passed"] is False
    assert result["worker_did_work_match"] is False


def test_channel_parity_records_drift_without_failing() -> None:
    result = compare_channel_parity(
        _summary(latency_ms=1000, cost_usd=0.02, total_tokens=100),
        _summary(latency_ms=1300, cost_usd=0.03, total_tokens=140),
    )

    assert result["passed"] is True
    assert result["details"]["drift"]["latency_drift_ms"] == 300
    assert result["details"]["drift"]["cost_drift_usd"] == 0.009999999999999998
    assert result["details"]["drift"]["total_token_drift"] == 40
