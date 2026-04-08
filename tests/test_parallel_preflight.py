from __future__ import annotations

import json
from pathlib import Path

import pytest

from auto_improve.probe_keys import KeyStatus
from evals.manifest import TaskManifest
import evals.parallel as parallel
import evals.run_evals as run_evals


MODELS = {
    "plan": "plan-model",
    "critique": "critique-model",
    "revise": "revise-model",
    "gate": "gate-model",
    "finalize": "finalize-model",
    "execute": "execute-model",
    "review": "review-model",
}


class FakeBenchmark:
    def __init__(self, root: Path):
        self.root = root

    def setup_source(self, config):
        source_root = self.root / "sources" / config.run_name.replace("/", "__")
        source_root.mkdir(parents=True, exist_ok=True)
        return source_root

    def list_tasks(self, source_root: Path, configured: list[str], cli_selected: list[str] | None) -> list[str]:
        return list(cli_selected or configured)


def _write_config(root: Path, *, run_name: str, workspace_dir: Path, results_dir: Path) -> Path:
    config_path = root / f"{run_name.replace('/', '_')}.json"
    payload = {
        "benchmark": "swe-bench",
        "models": dict(MODELS),
        "evals_to_run": [f"task-{index}" for index in range(5)],
        "swebench_dataset": "princeton-nlp/SWE-bench_Verified",
        "workspace_dir": str(workspace_dir),
        "results_dir": str(results_dir),
        "run_name": run_name,
        "workers": 5,
    }
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return config_path


def _api_key_pool(size: int) -> list[dict[str, str]]:
    return [
        {
            "key": f"deadbeef{i:02d}cafebabe{i:02d}",
            "base_url": "https://api.z.ai/api/coding/paas/v4",
        }
        for i in range(size)
    ]


def _key_status(
    key: str,
    status: str,
    *,
    reset_at: str | None = None,
    detail: str = "detail",
) -> KeyStatus:
    return KeyStatus(
        key=key,
        provider="zhipu",
        status=status,
        detail=detail,
        reset_at=reset_at,
        masked_key=f"{key[:8]}...{key[-4:]}",
    )


def test_probe_and_filter_keys_keeps_all_alive_without_warning(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    api_keys = _api_key_pool(5)
    monkeypatch.setattr(
        parallel,
        "probe_keys",
        lambda raw_keys, provider="zhipu": [_key_status(key, "alive") for key in raw_keys],
    )

    filtered, worker_count = parallel._probe_and_filter_keys(api_keys, 4)
    stderr = capsys.readouterr().err

    assert filtered == api_keys
    assert worker_count == 4
    assert "WARNING" not in stderr
    assert "[alive]" in stderr
    for entry in api_keys:
        assert entry["key"] not in stderr


def test_probe_and_filter_keys_scales_down_and_masks_keys(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    api_keys = _api_key_pool(5)
    statuses = [
        _key_status(api_keys[0]["key"], "alive"),
        _key_status(api_keys[1]["key"], "alive"),
        _key_status(api_keys[2]["key"], "alive"),
        _key_status(api_keys[3]["key"], "exhausted", reset_at="2026-04-08 11:55:35"),
        _key_status(api_keys[4]["key"], "invalid"),
    ]
    monkeypatch.setattr(parallel, "probe_keys", lambda raw_keys, provider="zhipu": statuses)

    filtered, worker_count = parallel._probe_and_filter_keys(api_keys, 5)
    stderr = capsys.readouterr().err

    assert filtered == api_keys[:3]
    assert worker_count == 3
    assert "Scaling workers 5 -> 3" in stderr
    assert "1 exhausted" in stderr
    assert "1 invalid" in stderr
    for entry in api_keys:
        assert entry["key"] not in stderr


def test_probe_and_filter_keys_raises_when_zero_alive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_keys = _api_key_pool(2)
    statuses = [
        _key_status(api_keys[0]["key"], "exhausted", reset_at="2026-04-08 11:55:35"),
        _key_status(api_keys[1]["key"], "unreachable"),
    ]
    monkeypatch.setattr(parallel, "probe_keys", lambda raw_keys, provider="zhipu": statuses)

    with pytest.raises(RuntimeError) as excinfo:
        parallel._probe_and_filter_keys(api_keys, 2)

    message = str(excinfo.value)
    assert "No alive API keys" in message
    assert "exhausted" in message
    for entry in api_keys:
        assert entry["key"] not in message


def test_probe_and_filter_keys_preserves_empty_input() -> None:
    filtered, worker_count = parallel._probe_and_filter_keys([], 4)

    assert filtered == []
    assert worker_count == 4


def test_run_parallel_workers_reserves_scaled_worker_count(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(
        tmp_path,
        run_name="preflight-scaled",
        workspace_dir=tmp_path / "workspaces",
        results_dir=tmp_path / "results",
    )
    api_keys = _api_key_pool(5)
    statuses = [
        _key_status(api_keys[0]["key"], "alive"),
        _key_status(api_keys[1]["key"], "alive"),
        _key_status(api_keys[2]["key"], "alive"),
        _key_status(api_keys[3]["key"], "invalid"),
        _key_status(api_keys[4]["key"], "unreachable"),
    ]
    reserve_calls: list[list[str]] = []
    launch_calls: list[dict[str, object]] = []
    original_reserve = TaskManifest.reserve_specific_worker_ids

    def record_reserve(self: TaskManifest, worker_ids: list[str]) -> None:
        reserve_calls.append(list(worker_ids))
        original_reserve(self, worker_ids)

    def fake_launch(
        original_config_path,
        workspace_dir,
        worker_ids,
        predictions_dir,
        manifest_path,
        results_root,
        *,
        api_keys=None,
        replace_pidfile_workers=False,
    ):
        launch_calls.append(
            {
                "worker_ids": list(worker_ids),
                "api_keys": list(api_keys or []),
                "replace_pidfile_workers": replace_pidfile_workers,
            }
        )
        worker_log_dir = results_root / "_worker_logs"
        worker_log_dir.mkdir(parents=True, exist_ok=True)
        return [], [], worker_log_dir

    monkeypatch.setattr(run_evals, "_resolve_benchmark", lambda config: FakeBenchmark(tmp_path))
    monkeypatch.setattr(parallel, "_load_api_keys", lambda: api_keys)
    monkeypatch.setattr(parallel, "probe_keys", lambda raw_keys, provider="zhipu": statuses)
    monkeypatch.setattr(parallel, "_launch_worker_processes", fake_launch)
    monkeypatch.setattr(parallel, "_wait_for_workers", lambda *args, **kwargs: {})
    monkeypatch.setattr(TaskManifest, "reserve_specific_worker_ids", record_reserve)

    summary = parallel.run_parallel_workers(config_path, None, 5, scoring_mode="none")

    assert summary["workers"] == 3
    assert reserve_calls == [["worker-0", "worker-1", "worker-2"]]
    assert launch_calls[0]["worker_ids"] == ["worker-0", "worker-1", "worker-2"]
    assert launch_calls[0]["api_keys"] == api_keys[:3]


def test_run_parallel_workers_zero_alive_raises_before_reservation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(
        tmp_path,
        run_name="preflight-zero",
        workspace_dir=tmp_path / "workspaces",
        results_dir=tmp_path / "results",
    )
    api_keys = _api_key_pool(5)
    statuses = [_key_status(entry["key"], "invalid") for entry in api_keys]
    reserve_called = False

    def record_reserve(self: TaskManifest, worker_ids: list[str]) -> None:
        nonlocal reserve_called
        reserve_called = True

    monkeypatch.setattr(run_evals, "_resolve_benchmark", lambda config: FakeBenchmark(tmp_path))
    monkeypatch.setattr(parallel, "_load_api_keys", lambda: api_keys)
    monkeypatch.setattr(parallel, "probe_keys", lambda raw_keys, provider="zhipu": statuses)
    monkeypatch.setattr(TaskManifest, "reserve_specific_worker_ids", record_reserve)
    monkeypatch.setattr(
        parallel,
        "_launch_worker_processes",
        lambda *args, **kwargs: pytest.fail("_launch_worker_processes should not be called"),
    )

    with pytest.raises(RuntimeError) as excinfo:
        parallel.run_parallel_workers(config_path, None, 5, scoring_mode="none")

    assert "No alive API keys" in str(excinfo.value)
    assert reserve_called is False
