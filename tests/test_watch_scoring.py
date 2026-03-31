import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from evals.manifest import TaskManifest
import evals.watch_scoring as watch_scoring


def _make_results_root(tmp_path: Path, task_ids: list[str]) -> tuple[Path, TaskManifest, Path]:
    results_root = tmp_path / "results" / "watch-run"
    predictions_dir = results_root / "_swebench_predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)
    manifest = TaskManifest.create(results_root / "_task_manifest.json", task_ids)
    return results_root, manifest, predictions_dir


def _write_prediction(
    predictions_dir: Path,
    instance_id: str,
    *,
    model_name: str = "test-model",
    model_patch: str = "diff --git a/x b/x\n+fix\n",
) -> Path:
    prediction_path = predictions_dir / f"{instance_id}.jsonl"
    prediction_path.write_text(
        json.dumps(
            {
                "instance_id": instance_id,
                "model_name_or_path": model_name,
                "model_patch": model_patch,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return prediction_path


@pytest.fixture
def watch_test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    state = {
        "calls": [],
        "harness_ids": [],
        "docker_calls": [],
        "resolved": {},
        "skip_reports": set(),
        "docker_images_stdout": "",
    }

    def fake_run(command, **kwargs):
        command_list = list(command)
        state["calls"].append(command_list)

        if command_list[:3] == [sys.executable, "-m", "swebench.harness.run_evaluation"]:
            predictions_path = Path(command_list[command_list.index("--predictions_path") + 1])
            prediction = json.loads(predictions_path.read_text(encoding="utf-8").splitlines()[0])
            instance_id = prediction["instance_id"]
            model_name = prediction["model_name_or_path"]
            run_id = command_list[command_list.index("--run_id") + 1]
            state["harness_ids"].append(instance_id)
            if instance_id not in state["skip_reports"]:
                report_path = (
                    tmp_path
                    / "logs"
                    / "run_evaluation"
                    / run_id
                    / model_name
                    / instance_id
                    / "report.json"
                )
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(
                    json.dumps({instance_id: {"resolved": state["resolved"].get(instance_id, True)}}),
                    encoding="utf-8",
                )
            return subprocess.CompletedProcess(command_list, 0, stdout="ok", stderr="")

        if command_list[:2] == ["docker", "images"]:
            state["docker_calls"].append(command_list)
            return subprocess.CompletedProcess(
                command_list,
                0,
                stdout=state["docker_images_stdout"],
                stderr="",
            )

        if command_list[:2] == ["docker", "rmi"] or command_list[:3] == ["docker", "image", "prune"]:
            state["docker_calls"].append(command_list)
            return subprocess.CompletedProcess(command_list, 0, stdout="", stderr="")

        raise AssertionError(f"unexpected subprocess.run call: {command_list}")

    with patch.object(watch_scoring.subprocess, "run", side_effect=fake_run):
        yield state


def test_manifest_gated_filtering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    watch_test_env,
) -> None:
    results_root, manifest, predictions_dir = _make_results_root(
        tmp_path,
        ["task-1", "task-2", "task-3"],
    )
    for instance_id in ["task-1", "task-2", "task-3"]:
        _write_prediction(predictions_dir, instance_id)

    manifest.mark_done("task-1", "worker-0")
    manifest.mark_done("task-2", "worker-0")

    sleep_calls = {"count": 0}

    def fake_sleep(_: float) -> None:
        if sleep_calls["count"] == 0:
            manifest.mark_done("task-3", "worker-0")
        sleep_calls["count"] += 1

    monkeypatch.setattr(watch_scoring.time, "sleep", fake_sleep)

    result = watch_scoring.watch_and_score(
        results_root,
        poll_interval=0,
        timeout=5,
        cleanup_docker=False,
    )

    assert watch_test_env["harness_ids"] == ["task-1", "task-2", "task-3"]
    assert result["scored"] == 3
    assert result["resolved"] == 3


def test_exit_on_all_done_with_no_patch_tasks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    watch_test_env,
) -> None:
    results_root, manifest, predictions_dir = _make_results_root(
        tmp_path,
        ["task-1", "task-2", "task-3", "task-4", "task-5"],
    )
    for instance_id in ["task-1", "task-2", "task-3"]:
        _write_prediction(predictions_dir, instance_id)

    manifest.mark_done("task-1", "worker-0")
    manifest.mark_done("task-2", "worker-0")
    manifest.mark_done("task-3", "worker-0")
    manifest.mark_error("task-4", "worker-0", "no patch")
    manifest.mark_done("task-5", "worker-0")

    monkeypatch.setattr(watch_scoring.time, "sleep", lambda _: None)

    result = watch_scoring.watch_and_score(
        results_root,
        poll_interval=0,
        timeout=5,
        cleanup_docker=False,
    )

    assert watch_test_env["harness_ids"] == ["task-1", "task-2", "task-3"]
    assert result["scored"] == 3
    assert result["manifest_total"] == 5
    assert result["manifest_done"] == 4
    assert result["manifest_error"] == 1
    assert result["stop_reason"] == "completed"


def test_parse_swebench_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    report_path = (
        tmp_path
        / "logs"
        / "run_evaluation"
        / "run-1"
        / "test-model"
        / "task-1"
        / "report.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"resolved_ids": ["task-1"]}), encoding="utf-8")

    assert watch_scoring._parse_swebench_report("task-1", "run-1", "test-model") is True
    assert watch_scoring._parse_swebench_report("missing-task", "run-1", "test-model") is None


def test_restart_idempotency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    watch_test_env,
) -> None:
    results_root, manifest, predictions_dir = _make_results_root(
        tmp_path,
        ["task-1", "task-2", "task-3"],
    )
    for instance_id in ["task-1", "task-2", "task-3"]:
        _write_prediction(predictions_dir, instance_id)
        manifest.mark_done(instance_id, "worker-0")

    scores_path = results_root / "_watch_scores.json"
    scores_path.write_text(
        json.dumps(
            {
                "manifest_total": 3,
                "manifest_done": 2,
                "manifest_error": 0,
                "scored": 2,
                "resolved": 2,
                "failed": 0,
                "errors": 0,
                "pass_rate": 1.0,
                "last_updated": "2026-01-01T00:00:00+00:00",
                "tasks": {
                    "task-1": {"resolved": True, "scored_at": "2026-01-01T00:00:00+00:00"},
                    "task-2": {"resolved": True, "scored_at": "2026-01-01T00:00:01+00:00"},
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(watch_scoring.time, "sleep", lambda _: None)

    result = watch_scoring.watch_and_score(
        results_root,
        poll_interval=0,
        timeout=5,
        cleanup_docker=False,
    )

    assert watch_test_env["harness_ids"] == ["task-3"]
    assert result["scored"] == 3
    assert result["resolved"] == 3


def test_incremental_results_format(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    watch_test_env,
) -> None:
    results_root, manifest, predictions_dir = _make_results_root(tmp_path, ["task-1"])
    _write_prediction(predictions_dir, "task-1")
    manifest.mark_done("task-1", "worker-0")

    monkeypatch.setattr(watch_scoring.time, "sleep", lambda _: None)

    watch_scoring.watch_and_score(
        results_root,
        poll_interval=0,
        timeout=5,
        cleanup_docker=False,
    )

    scores = json.loads((results_root / "_watch_scores.json").read_text(encoding="utf-8"))

    expected_keys = {
        "manifest_total",
        "manifest_done",
        "manifest_error",
        "scored",
        "resolved",
        "failed",
        "errors",
        "error_breakdown",
        "pass_rate",
        "last_updated",
        "tasks",
    }
    assert expected_keys.issubset(scores)
    assert scores["manifest_total"] == 1
    assert scores["scored"] == 1
    assert scores["resolved"] == 1
    assert scores["pass_rate"] == 1.0
    assert scores["tasks"]["task-1"]["resolved"] is True
    assert "scored_at" in scores["tasks"]["task-1"]


def test_timeout_exits_with_partial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    watch_test_env,
) -> None:
    results_root, manifest, predictions_dir = _make_results_root(
        tmp_path,
        ["task-1", "task-2"],
    )
    _write_prediction(predictions_dir, "task-1")
    manifest.mark_done("task-1", "worker-0")

    clock = {"value": 0.0}

    def fake_monotonic() -> float:
        current = clock["value"]
        clock["value"] += 0.6
        return current

    monkeypatch.setattr(watch_scoring.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(watch_scoring.time, "sleep", lambda _: None)

    result = watch_scoring.watch_and_score(
        results_root,
        poll_interval=0,
        timeout=1,
        cleanup_docker=False,
    )

    scores = json.loads((results_root / "_watch_scores.json").read_text(encoding="utf-8"))
    assert watch_test_env["harness_ids"] == ["task-1"]
    assert result["stop_reason"] == "timeout"
    assert scores["scored"] == 1
    assert scores["tasks"]["task-1"]["resolved"] is True


def test_watch_scoring_integration_smoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    watch_test_env,
) -> None:
    results_root, manifest, predictions_dir = _make_results_root(
        tmp_path,
        ["task-1", "task-2", "task-3"],
    )
    _write_prediction(predictions_dir, "task-1")
    _write_prediction(predictions_dir, "task-2")
    manifest.mark_done("task-1", "worker-0")
    manifest.mark_done("task-2", "worker-0")
    manifest.mark_done("task-3", "worker-0")

    monkeypatch.setattr(watch_scoring.time, "sleep", lambda _: None)

    result = watch_scoring.watch_and_score(
        results_root,
        poll_interval=0,
        timeout=5,
        cleanup_docker=False,
    )

    scores = json.loads((results_root / "_watch_scores.json").read_text(encoding="utf-8"))
    assert result["scored"] == 2
    assert result["resolved"] == 2
    assert result["stop_reason"] == "completed"
    assert scores["scored"] == 2
    assert sorted(scores["tasks"]) == ["task-1", "task-2"]


def test_watch_scoring_retries_missing_report_three_times(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    watch_test_env,
) -> None:
    results_root, manifest, predictions_dir = _make_results_root(tmp_path, ["task-1"])
    _write_prediction(predictions_dir, "task-1")
    manifest.mark_done("task-1", "worker-0")
    watch_test_env["skip_reports"].add("task-1")

    monkeypatch.setattr(watch_scoring.time, "sleep", lambda _: None)

    result = watch_scoring.watch_and_score(
        results_root,
        poll_interval=0,
        timeout=5,
        cleanup_docker=False,
    )

    scores = json.loads((results_root / "_watch_scores.json").read_text(encoding="utf-8"))
    assert watch_test_env["harness_ids"] == ["task-1", "task-1", "task-1"]
    assert result["errors"] == 1
    assert result["error_breakdown"] == {"report_parse": 1}
    assert scores["tasks"]["task-1"]["attempts"] == 3
    assert scores["tasks"]["task-1"]["error_category"] == "report_parse"


def test_categorize_scoring_error_variants() -> None:
    assert watch_scoring._categorize_scoring_error(
        None,
        {"error": "run_evaluation timed out after 1800s"},
    ) == "timeout"
    assert watch_scoring._categorize_scoring_error(
        None,
        {"stderr": "Modal sandbox mount failed"},
    ) == "modal_sandbox"
    assert watch_scoring._categorize_scoring_error(
        None,
        {"error": "missing or unparseable SWE-bench report"},
    ) == "report_parse"


def test_format_stop_line_includes_error_breakdown() -> None:
    line = watch_scoring._format_stop_line(
        {
            "scored": 3,
            "resolved": 1,
            "error_breakdown": {"modal_sandbox": 2, "timeout": 1},
        },
        {"done": 3, "total_tasks": 5, "error": 1},
        "timeout",
    )

    assert "[errors modal_sandbox=2, timeout=1]" in line
