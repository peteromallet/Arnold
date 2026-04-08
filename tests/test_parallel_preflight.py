from __future__ import annotations

import json
import time
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


class ImmediateProc:
    def __init__(self, pid: int, retcode: int = 0):
        self.pid = pid
        self._retcode = retcode

    def poll(self) -> int:
        return self._retcode


class FakeLoadedManifest:
    def __init__(self, summary: dict[str, int]):
        self._summary = dict(summary)

    def summary(self) -> dict[str, int]:
        return dict(self._summary)


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


def _api_key_pool(size: int) -> list[str]:
    return [f"deadbeef{i:02d}cafebabe{i:02d}" for i in range(size)]


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


def _fake_launch_result(
    results_root: Path,
    worker_ids: list[str],
) -> tuple[list[tuple[str, ImmediateProc, Path]], list[Path], Path]:
    worker_log_dir = results_root / "_worker_logs"
    worker_log_dir.mkdir(parents=True, exist_ok=True)
    worker_procs: list[tuple[str, ImmediateProc, Path]] = []
    temp_configs: list[Path] = []
    for index, worker_id in enumerate(worker_ids):
        temp_config = results_root / f"{worker_id}.tmp.json"
        temp_config.write_text("{}", encoding="utf-8")
        temp_configs.append(temp_config)
        worker_procs.append((worker_id, ImmediateProc(4000 + index), temp_config))
    return worker_procs, temp_configs, worker_log_dir


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
    for key in api_keys:
        assert key not in stderr


def test_probe_and_filter_keys_scales_down_and_masks_keys(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    api_keys = _api_key_pool(5)
    statuses = [
        _key_status(api_keys[0], "alive"),
        _key_status(api_keys[1], "alive"),
        _key_status(api_keys[2], "alive"),
        _key_status(api_keys[3], "exhausted", reset_at="2026-04-08 11:55:35"),
        _key_status(api_keys[4], "invalid"),
    ]
    monkeypatch.setattr(parallel, "probe_keys", lambda raw_keys, provider="zhipu": statuses)

    filtered, worker_count = parallel._probe_and_filter_keys(api_keys, 5)
    stderr = capsys.readouterr().err

    assert filtered == api_keys[:3]
    assert worker_count == 3
    assert "Scaling workers 5 -> 3" in stderr
    assert "1 exhausted" in stderr
    assert "1 invalid" in stderr
    for key in api_keys:
        assert key not in stderr


def test_probe_and_filter_keys_returns_zero_workers_when_zero_alive(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    api_keys = _api_key_pool(2)
    statuses = [
        _key_status(api_keys[0], "exhausted", reset_at="2026-04-08 11:55:35"),
        _key_status(api_keys[1], "unreachable"),
    ]
    monkeypatch.setattr(parallel, "probe_keys", lambda raw_keys, provider="zhipu": statuses)

    filtered, worker_count = parallel._probe_and_filter_keys(api_keys, 2)
    stderr = capsys.readouterr().err

    assert filtered == []
    assert worker_count == 0
    assert "No alive API keys" in stderr
    assert "exhausted" in stderr
    for key in api_keys:
        assert key not in stderr


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
        _key_status(api_keys[0], "alive"),
        _key_status(api_keys[1], "alive"),
        _key_status(api_keys[2], "alive"),
        _key_status(api_keys[3], "invalid"),
        _key_status(api_keys[4], "unreachable"),
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
    assert all(isinstance(key, str) for key in launch_calls[0]["api_keys"])


def test_run_parallel_workers_exits_when_no_alive_keys(
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
    reserve_called = False

    def record_reserve(self: TaskManifest, worker_ids: list[str]) -> None:
        nonlocal reserve_called
        reserve_called = True

    monkeypatch.setattr(run_evals, "_resolve_benchmark", lambda config: FakeBenchmark(tmp_path))
    monkeypatch.setattr(parallel, "_load_api_keys", lambda: api_keys)
    monkeypatch.setattr(parallel, "_probe_and_filter_keys", lambda raw_keys, workers: ([], 0))
    monkeypatch.setattr(TaskManifest, "reserve_specific_worker_ids", record_reserve)
    monkeypatch.setattr(
        parallel,
        "_launch_worker_processes",
        lambda *args, **kwargs: pytest.fail("_launch_worker_processes should not be called"),
    )

    summary = parallel.run_parallel_workers(config_path, None, 5, scoring_mode="none")

    assert summary["all_workers_failed"] is True
    assert summary["reason"] == "no_alive_keys"
    assert summary["workers"] == 0
    assert reserve_called is False


def test_launch_workers_does_not_pin_zhipu_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(
        tmp_path,
        run_name="launch-shared-pool",
        workspace_dir=tmp_path / "workspaces",
        results_dir=tmp_path / "results",
    )
    predictions_dir = tmp_path / "predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = tmp_path / "_task_manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    results_root = tmp_path / "results" / "launch-shared-pool"
    api_keys = _api_key_pool(1)
    fake_home = tmp_path / "fake-home"
    real_env_dir = fake_home / ".hermes"
    real_env_dir.mkdir(parents=True, exist_ok=True)
    (real_env_dir / ".env").write_text("ZHIPU_API_KEY=parent-zhipu-key\n", encoding="utf-8")

    captured: list[dict[str, object]] = []

    def fake_popen(command, **kwargs):
        config_arg = Path(command[command.index("--config") + 1])
        config_json = json.loads(config_arg.read_text(encoding="utf-8"))
        captured.append(
            {
                "command": list(command),
                "env": dict(kwargs["env"]),
                "config": config_json,
            }
        )
        kwargs["stdout"].close()
        kwargs["stderr"].close()
        return ImmediateProc(9001)

    monkeypatch.setenv("ZHIPU_API_KEY", "parent-zhipu-key")
    monkeypatch.setattr(parallel, "_clean_editable_installs", lambda: None)
    monkeypatch.setattr(parallel, "_preflight_check_megaplan", lambda: None)
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.setattr(parallel.subprocess, "Popen", fake_popen)

    worker_procs, temp_configs, _ = parallel._launch_worker_processes(
        config_path,
        str(tmp_path / "workspaces"),
        ["worker-0"],
        predictions_dir,
        manifest_path,
        results_root,
        api_keys=api_keys,
        replace_pidfile_workers=True,
    )

    assert [worker_id for worker_id, _, _ in worker_procs] == ["worker-0"]
    assert len(captured) == 1
    assert captured[0]["env"]["ZHIPU_API_KEY"] == "parent-zhipu-key"
    assert "api_key" not in captured[0]["config"]
    assert "base_url" not in captured[0]["config"]

    worker_env_path = Path(captured[0]["env"]["HERMES_HOME"]) / ".env"
    assert worker_env_path.exists()
    assert api_keys[0] not in worker_env_path.read_text(encoding="utf-8")

    for temp_config in temp_configs:
        temp_config.unlink(missing_ok=True)


def test_run_parallel_workers_exits_when_manifest_unfinished_after_workers_die(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(
        tmp_path,
        run_name="manifest-unfinished",
        workspace_dir=tmp_path / "workspaces",
        results_dir=tmp_path / "results",
    )
    api_keys = _api_key_pool(1)

    monkeypatch.setattr(run_evals, "_resolve_benchmark", lambda config: FakeBenchmark(tmp_path))
    monkeypatch.setattr(parallel, "_load_api_keys", lambda: api_keys)
    monkeypatch.setattr(parallel, "_probe_and_filter_keys", lambda raw_keys, workers: (api_keys, 1))
    monkeypatch.setattr(
        parallel,
        "_launch_worker_processes",
        lambda *args, **kwargs: _fake_launch_result(tmp_path / "results" / "manifest-unfinished", ["worker-0"]),
    )
    monkeypatch.setattr(
        TaskManifest,
        "load",
        classmethod(lambda cls, path: FakeLoadedManifest({"pending": 5, "claimed": 0, "done": 0})),
    )

    started = time.monotonic()
    summary = parallel.run_parallel_workers(config_path, None, 5, scoring_mode="none")
    elapsed = time.monotonic() - started

    assert elapsed < 5
    assert summary["all_workers_failed"] is True
    assert "pending=5" in summary["reason"]
    assert summary["workers"] == 1


def test_run_parallel_workers_success_when_manifest_done(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(
        tmp_path,
        run_name="manifest-done",
        workspace_dir=tmp_path / "workspaces",
        results_dir=tmp_path / "results",
    )
    api_keys = _api_key_pool(1)

    monkeypatch.setattr(run_evals, "_resolve_benchmark", lambda config: FakeBenchmark(tmp_path))
    monkeypatch.setattr(parallel, "_load_api_keys", lambda: api_keys)
    monkeypatch.setattr(parallel, "_probe_and_filter_keys", lambda raw_keys, workers: (api_keys, 1))
    monkeypatch.setattr(
        parallel,
        "_launch_worker_processes",
        lambda *args, **kwargs: _fake_launch_result(tmp_path / "results" / "manifest-done", ["worker-0"]),
    )
    monkeypatch.setattr(
        TaskManifest,
        "load",
        classmethod(lambda cls, path: FakeLoadedManifest({"pending": 0, "claimed": 0, "done": 5})),
    )

    summary = parallel.run_parallel_workers(config_path, None, 5, scoring_mode="none")

    assert not summary.get("all_workers_failed", False)
    assert summary["workers"] == 1
    assert summary["scoring"]["skipped"] is True


def test_join_parallel_run_handles_no_alive_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = _write_config(
        tmp_path,
        run_name="join-zero",
        workspace_dir=tmp_path / "workspaces",
        results_dir=tmp_path / "results",
    )
    results_root = tmp_path / "results" / "join-zero"
    results_root.mkdir(parents=True, exist_ok=True)
    TaskManifest.create(results_root / "_task_manifest.json", ["task-0", "task-1"])
    (results_root / "_run_config.json").write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(parallel, "_load_api_keys", lambda: _api_key_pool(1))
    monkeypatch.setattr(parallel, "_probe_and_filter_keys", lambda raw_keys, workers: ([], 0))
    monkeypatch.setattr(
        parallel,
        "_launch_worker_processes",
        lambda *args, **kwargs: pytest.fail("_launch_worker_processes should not be called"),
    )

    summary = parallel.join_parallel_run(config_path, "join-zero", 2)

    assert summary["all_workers_failed"] is True
    assert summary["reason"] == "no_alive_keys"
    assert summary["added_workers"] == 0
