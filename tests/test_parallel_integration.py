import json
import os
import subprocess as real_subprocess
import sys
import tempfile
import threading
import time as real_time
from pathlib import Path

import pytest

from evals.manifest import TaskManifest
import evals.parallel as parallel
import evals.run_evals as run_evals


FAKE_WORKER_SCRIPT = r"""
import json
import os
import sys
import time
from pathlib import Path

from evals.manifest import TaskManifest

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
manifest = TaskManifest.load(config["manifest_path"])
worker_id = config["worker_id"]
batch_size = int(config.get("claim_batch_size", 10) or 10)
predictions_dir = Path(config["predictions_dir"]).expanduser().resolve()
predictions_dir.mkdir(parents=True, exist_ok=True)
results_root = Path(config["results_dir"]).expanduser().resolve() / config["run_name"]
results_root.mkdir(parents=True, exist_ok=True)
delay = float(os.environ.get("FAKE_WORKER_DELAY", "0"))
evals = []

while True:
    batch = manifest.claim_batch(worker_id, batch_size)
    if not batch:
        break
    for instance_id in batch:
        if delay:
            time.sleep(delay)
        prediction = {
            "instance_id": instance_id,
            "model_name_or_path": config["models"]["execute"],
            "model_patch": f"patch-{worker_id}-{instance_id}",
        }
        (predictions_dir / f"{instance_id}.jsonl").write_text(
            json.dumps(prediction) + "\n",
            encoding="utf-8",
        )
        manifest.mark_done(instance_id, worker_id)
        evals.append({"eval_name": instance_id, "status": "passed"})

(results_root / "summary_fake.json").write_text(json.dumps({"evals": evals}), encoding="utf-8")
"""


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


@pytest.fixture
def parallel_test_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    temp_home = tmp_path / "home"
    temp_home.mkdir()
    original_popen = real_subprocess.Popen
    original_sleep = real_time.sleep

    def fake_popen(command, *, env=None, stdout=None, stderr=None, cwd=None, **kwargs):
        if command[:3] != [sys.executable, "-m", "evals.run_evals"]:
            return original_popen(command, env=env, stdout=stdout, stderr=stderr, cwd=cwd, **kwargs)
        config_path = command[command.index("--config") + 1]
        worker_env = dict(env or {})
        worker_env["PYTHONPATH"] = os.pathsep.join(
            filter(None, [str(Path.cwd()), worker_env.get("PYTHONPATH", "")])
        )
        return original_popen(
            [sys.executable, "-c", FAKE_WORKER_SCRIPT, config_path],
            env=worker_env,
            stdout=stdout,
            stderr=stderr,
            cwd=cwd,
            **kwargs,
        )

    monkeypatch.setattr(run_evals, "_resolve_benchmark", lambda config: FakeBenchmark(tmp_path))
    monkeypatch.setattr(parallel, "_run_batch_scoring", lambda *args, **kwargs: {"returncode": 0})
    monkeypatch.setattr(parallel, "DEFAULT_CLAIM_BATCH_SIZE", 2)
    monkeypatch.setattr(parallel.Path, "home", classmethod(lambda cls: temp_home))
    monkeypatch.setattr(parallel.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(parallel.time, "sleep", lambda _: original_sleep(0.01))
    return tmp_path


def _write_config(
    root: Path,
    *,
    run_name: str,
    workspace_dir: Path,
    results_dir: Path,
    evals_to_run: list[str],
    workers: int = 2,
) -> Path:
    config_path = root / f"{run_name.replace('/', '_')}.json"
    payload = {
        "benchmark": "swe-bench",
        "models": dict(MODELS),
        "evals_to_run": evals_to_run,
        "swebench_dataset": "princeton-nlp/SWE-bench_Verified",
        "workspace_dir": str(workspace_dir),
        "results_dir": str(results_dir),
        "run_name": run_name,
        "workers": workers,
    }
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return config_path


def _prediction_ids(path: Path) -> list[str]:
    return [
        json.loads(line)["instance_id"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_parallel_run_processes_all_tasks_without_duplicates(
    parallel_test_env: Path,
) -> None:
    tmp_path = parallel_test_env
    config_path = _write_config(
        tmp_path,
        run_name="integration-run",
        workspace_dir=tmp_path / "workspaces-a",
        results_dir=tmp_path / "results",
        evals_to_run=[f"task-{i}" for i in range(5)],
    )

    summary = parallel.run_parallel_workers(config_path, None, 2)

    results_root = tmp_path / "results" / "integration-run"
    manifest = TaskManifest.load(results_root / "_task_manifest.json")
    combined_path = results_root / "_swebench_predictions" / "all_predictions.jsonl"
    prediction_ids = _prediction_ids(combined_path)

    assert summary["mode"] == "parallel"
    assert manifest.all_done() is True
    assert len(prediction_ids) == 5
    assert len(set(prediction_ids)) == 5


def test_join_parallel_run_avoids_duplicate_task_processing(
    parallel_test_env: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path = parallel_test_env
    monkeypatch.setenv("FAKE_WORKER_DELAY", "0.05")

    config_path = _write_config(
        tmp_path,
        run_name="join-run",
        workspace_dir=tmp_path / "join-workspaces",
        results_dir=tmp_path / "results",
        evals_to_run=[f"task-{i}" for i in range(10)],
    )

    results_root = tmp_path / "results" / "join-run"
    manifest_path = results_root / "_task_manifest.json"
    canonical_config_path = results_root / "_run_config.json"
    results_root.mkdir(parents=True, exist_ok=True)
    predictions_dir = results_root / "_swebench_predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)

    manifest = TaskManifest.create(manifest_path, [f"task-{i}" for i in range(10)])
    manifest.reserve_specific_worker_ids(["worker-0", "worker-1"])
    canonical_config_path.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")

    worker_procs, temp_configs, worker_log_dir = parallel._launch_worker_processes(
        canonical_config_path,
        str(tmp_path / "join-workspaces"),
        ["worker-0", "worker-1"],
        predictions_dir,
        manifest_path,
        results_root,
    )
    real_time.sleep(0.05)

    join_summary = parallel.join_parallel_run(config_path, "join-run", 1)
    parallel._wait_for_workers(worker_procs, worker_log_dir)

    for temp_config in temp_configs:
        temp_config.unlink(missing_ok=True)

    manifest = TaskManifest.load(manifest_path)
    combined_path = predictions_dir / "all_predictions.jsonl"
    parallel._combine_predictions(predictions_dir, combined_path, valid_ids=manifest.done_task_ids())
    prediction_ids = _prediction_ids(combined_path)

    assert join_summary["worker_ids"] == ["worker-2"]
    assert manifest.all_done() is True
    assert len(prediction_ids) == 10
    assert len(set(prediction_ids)) == 10


def test_multi_model_parallel_runs_keep_manifests_and_workspaces_isolated(
    parallel_test_env: Path,
) -> None:
    tmp_path = parallel_test_env
    config_a = _write_config(
        tmp_path,
        run_name="model-a",
        workspace_dir=tmp_path / "workspaces-a",
        results_dir=tmp_path / "results",
        evals_to_run=["task-a1", "task-a2"],
    )
    config_b = _write_config(
        tmp_path,
        run_name="model-b",
        workspace_dir=tmp_path / "workspaces-b",
        results_dir=tmp_path / "results",
        evals_to_run=["task-b1", "task-b2"],
    )

    results: dict[str, dict[str, object]] = {}
    errors: list[Exception] = []

    def _run(label: str, config_path: Path) -> None:
        try:
            results[label] = parallel.run_parallel_workers(config_path, None, 2)
        except Exception as exc:  # pragma: no cover - assertion path
            errors.append(exc)

    threads = [
        threading.Thread(target=_run, args=("a", config_a)),
        threading.Thread(target=_run, args=("b", config_b)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert results["a"]["mode"] == "parallel"
    assert results["b"]["mode"] == "parallel"

    results_root_a = tmp_path / "results" / "model-a"
    results_root_b = tmp_path / "results" / "model-b"

    assert TaskManifest.load(results_root_a / "_task_manifest.json").all_done() is True
    assert TaskManifest.load(results_root_b / "_task_manifest.json").all_done() is True
    assert (tmp_path / "workspaces-a" / "worker-0").exists()
    assert (tmp_path / "workspaces-b" / "worker-0").exists()
    assert (results_root_a / "_swebench_predictions" / "all_predictions.jsonl").exists()
    assert (results_root_b / "_swebench_predictions" / "all_predictions.jsonl").exists()
    assert (tmp_path / "workspaces-a" / "worker-0").resolve() != (tmp_path / "workspaces-b" / "worker-0").resolve()


def test_combine_predictions_filters_stale_entries(tmp_path: Path) -> None:
    predictions_dir = tmp_path / "predictions"
    predictions_dir.mkdir()
    output_path = predictions_dir / "all_predictions.jsonl"

    (predictions_dir / "task-a.jsonl").write_text(
        json.dumps({"instance_id": "task-a", "model_patch": "a"}) + "\n",
        encoding="utf-8",
    )
    (predictions_dir / "stale.jsonl").write_text(
        json.dumps({"instance_id": "stale-task", "model_patch": "stale"}) + "\n",
        encoding="utf-8",
    )

    count = parallel._combine_predictions(predictions_dir, output_path, valid_ids={"task-a"})
    prediction_ids = _prediction_ids(output_path)

    assert count == 1
    assert prediction_ids == ["task-a"]
