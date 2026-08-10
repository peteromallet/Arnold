from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from arnold_pipelines.megaplan.bakeoff.channel_shadow import (
    evaluate_channel_shadow_gate,
    channel_shadow_sample_rate,
    maybe_run_channel_shadow,
)
from arnold_pipelines.megaplan.bakeoff.state import CHANNEL_SHADOW_SCHEMA_VERSION, load_channel_shadow_state
from arnold_pipelines.megaplan.types import AgentMode, CliError
from arnold_pipelines.megaplan.workers import WorkerResult


def _state(project_dir: Path) -> dict:
    return {
        "name": "plan-shadow",
        "iteration": 0,
        "config": {"project_dir": str(project_dir), "mode": "code"},
        "sessions": {},
        "meta": {},
    }


def _worker(channel: str, *, rate_limit: dict | None = None) -> WorkerResult:
    return WorkerResult(
        payload={"task_updates": [], "sense_check_acknowledgments": []},
        raw_output="{}",
        duration_ms=100,
        cost_usd=0.01,
        session_id=f"{channel}-session",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        rate_limit=rate_limit,
        worker_channel=channel,
        auth_channel="subscription",
    )


def _write_api_proof(root: Path, *, live: bool) -> None:
    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "shannon-stream-api-proof-record.json").write_text(
        (
            '{"proof_kind":"live","live_api_phase_completed":true}'
            if live
            else '{"proof_kind":"dry_run","live_api_phase_completed":false}'
        ),
        encoding="utf-8",
    )


def _real_pass_record(index: int) -> dict:
    return {
        "recorded_at": f"2026-06-12T09:0{index}:00Z",
        "real_parity_success_count": index + 1,
        "channel_pair": {
            "primary_worker_channel": "shannon_tmux",
            "primary_auth_channel": "subscription",
            "shadow_worker_channel": "shannon_stream",
            "shadow_auth_channel": "subscription",
        },
        "provenance": {
            "source": "channel_shadow_hook",
            "fixture": False,
            "sample_key": f"real-{index}",
            "plan_id": "plan-shadow",
            "phase": "execute",
        },
        "decision": {
            "sampled": True,
            "skipped": False,
            "skip_reason": None,
            "sample_rate": 1.0,
            "sample_key": f"real-{index}",
        },
        "primary_receipt": {},
        "shadow_receipt": {},
        "drift": None,
        "parity_result": {
            "passed": True,
            "exit_kind_match": True,
            "payload_schema_valid_match": True,
            "landed_diff_match": True,
            "worker_did_work_match": True,
            "compared_at": "2026-06-12T09:00:00Z",
            "details": {},
        },
    }


def _run_shadow(tmp_path: Path, primary: WorkerResult, *, sample_key: str = "sample") -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    plan_dir = root / ".megaplan" / "plans" / "plan-shadow"
    project_dir.mkdir(parents=True)
    plan_dir.mkdir(parents=True)
    maybe_run_channel_shadow(
        root=root,
        plan_dir=plan_dir,
        state=_state(project_dir),
        args=Namespace(),
        step="execute",
        primary_worker=primary,
        primary_agent="shannon",
        prompt_override="prompt",
        sample_key=sample_key,
        resolved=AgentMode(
            agent="shannon",
            mode="persistent",
            refreshed=False,
            model="claude-opus-4-1",
            resolved_model="claude-opus-4-1",
        ),
    )


def test_channel_shadow_default_sample_rate_is_ten_percent(monkeypatch) -> None:
    monkeypatch.delenv("MEGAPLAN_CHANNEL_SHADOW_SAMPLE_RATE", raising=False)

    assert channel_shadow_sample_rate() == 0.10


def test_channel_shadow_records_not_sampled_without_running_worker(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEGAPLAN_CHANNEL_SHADOW_SAMPLE_RATE", "0")
    with patch("arnold_pipelines.megaplan.bakeoff.channel_shadow.worker_module.run_step_with_worker") as run_worker:
        _run_shadow(tmp_path, _worker("shannon_tmux"))

    state = load_channel_shadow_state(tmp_path / "root", "plan-shadow")
    record = state["records"][0]
    assert record["decision"]["sampled"] is False
    assert record["decision"]["skip_reason"] == "not_sampled"
    assert record["shadow_receipt"] is None
    run_worker.assert_not_called()


def test_channel_shadow_records_pressure_skip_without_counting_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEGAPLAN_CHANNEL_SHADOW_SAMPLE_RATE", "1")
    monkeypatch.setenv("MEGAPLAN_CHANNEL_SHADOW_PRESSURE", "1")
    with patch("arnold_pipelines.megaplan.bakeoff.channel_shadow.worker_module.run_step_with_worker") as run_worker:
        _run_shadow(tmp_path, _worker("shannon_tmux"))

    state = load_channel_shadow_state(tmp_path / "root", "plan-shadow")
    record = state["records"][0]
    assert record["decision"]["sampled"] is True
    assert record["decision"]["skip_reason"] == "cap_pressure"
    assert record["real_parity_success_count"] == 0
    assert state["real_parity_success_count"] == 0
    run_worker.assert_not_called()


def test_channel_shadow_admitted_shadow_routes_through_worker_seam(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEGAPLAN_CHANNEL_SHADOW_SAMPLE_RATE", "1")
    with patch(
        "arnold_pipelines.megaplan.bakeoff.channel_shadow.worker_module.run_step_with_worker",
        return_value=(_worker("shannon_stream"), "shannon", "persistent", False),
    ) as run_worker:
        _run_shadow(tmp_path, _worker("shannon_tmux"))

    state = load_channel_shadow_state(tmp_path / "root", "plan-shadow")
    record = state["records"][0]
    assert record["decision"]["skip_reason"] is None
    assert record["shadow_receipt"]["worker_channel"] == "shannon_stream"
    assert record["drift"]["latency_drift_ms"] == 0
    assert record["parity_result"]["passed"] is True
    assert record["real_parity_success_count"] == 1
    assert state["real_parity_success_count"] == 1
    assert state["gate"]["greenlight"] is False
    assert state["gate"]["blockers"] == ["insufficient_real_parity_successes"]
    run_worker.assert_called_once()


def test_channel_shadow_rate_limit_refusal_is_recorded_as_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MEGAPLAN_CHANNEL_SHADOW_SAMPLE_RATE", "1")
    error = CliError(
        "rate_limit",
        "cap full",
        extra={"source": "provider_rate_limit", "retryable": True},
    )
    with patch(
        "arnold_pipelines.megaplan.bakeoff.channel_shadow.worker_module.run_step_with_worker",
        side_effect=error,
    ):
        _run_shadow(tmp_path, _worker("shannon_tmux"))

    state = load_channel_shadow_state(tmp_path / "root", "plan-shadow")
    record = state["records"][0]
    assert record["decision"]["sampled"] is True
    assert record["decision"]["skip_reason"] == "shadow_unavailable"
    assert record["shadow_receipt"] is None


def test_channel_shadow_gate_requires_five_real_subscription_stream_tmux_passes(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _write_api_proof(root, live=True)
    state = {
        "schema_version": CHANNEL_SHADOW_SCHEMA_VERSION,
        "experiment_id": "plan-shadow",
        "real_parity_success_count": 0,
        "records": [_real_pass_record(index) for index in range(5)],
    }

    gate = evaluate_channel_shadow_gate(root, state)

    assert gate["greenlight"] is True
    assert gate["real_parity_success_count"] == 5
    assert gate["real_parity_failure_count"] == 0
    assert gate["channel_pair"] == state["records"][-1]["channel_pair"]
    assert gate["provenance"]["source"] == "channel_shadow_hook"
    assert gate["api_channel_greenlight"] is True


def test_channel_shadow_gate_blocks_on_real_parity_failure(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _write_api_proof(root, live=True)
    records = [_real_pass_record(index) for index in range(5)]
    failed = _real_pass_record(5)
    failed["parity_result"] = {**failed["parity_result"], "passed": False}
    records.append(failed)
    state = {
        "schema_version": CHANNEL_SHADOW_SCHEMA_VERSION,
        "experiment_id": "plan-shadow",
        "real_parity_success_count": 0,
        "records": records,
    }

    gate = evaluate_channel_shadow_gate(root, state)

    assert gate["greenlight"] is False
    assert gate["real_parity_success_count"] == 5
    assert gate["real_parity_failure_count"] == 1
    assert "real_parity_failures_present" in gate["blockers"]


def test_channel_shadow_gate_ignores_skipped_and_fixture_only_samples(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _write_api_proof(root, live=True)
    skipped = _real_pass_record(0)
    skipped["decision"] = {
        **skipped["decision"],
        "sampled": False,
        "skipped": True,
        "skip_reason": "not_sampled",
    }
    fixture = _real_pass_record(1)
    fixture["provenance"] = {**fixture["provenance"], "source": "fixture", "fixture": True}
    state = {
        "schema_version": CHANNEL_SHADOW_SCHEMA_VERSION,
        "experiment_id": "plan-shadow",
        "real_parity_success_count": 0,
        "records": [skipped, fixture],
    }

    gate = evaluate_channel_shadow_gate(root, state)

    assert gate["greenlight"] is False
    assert gate["real_parity_success_count"] == 0
    assert gate["skipped_count"] == 1
    assert gate["fixture_count"] == 1
    assert gate["blockers"] == ["insufficient_real_parity_successes"]


def test_channel_shadow_gate_defers_api_greenlight_after_dry_run_proof(tmp_path: Path) -> None:
    root = tmp_path / "root"
    _write_api_proof(root, live=False)
    state = {
        "schema_version": CHANNEL_SHADOW_SCHEMA_VERSION,
        "experiment_id": "plan-shadow",
        "real_parity_success_count": 0,
        "records": [_real_pass_record(index) for index in range(5)],
    }

    gate = evaluate_channel_shadow_gate(root, state)

    assert gate["greenlight"] is True
    assert gate["api_channel_greenlight"] is False
    assert gate["api_channel_blockers"] == ["api_proof_not_live"]
