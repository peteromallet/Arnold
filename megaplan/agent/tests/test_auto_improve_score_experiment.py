import json

import pytest

import auto_improve.score_experiment as score_experiment
from auto_improve.score_experiment import _normalize_scores_payload, _ordered_task_ids


def test_normalize_scores_payload_preserves_error_category():
    normalized = _normalize_scores_payload(
        iteration=2,
        raw_task_payloads={
            "task-1": {
                "resolved": None,
                "error": "missing or unparseable SWE-bench report",
                "error_category": "report_parse",
            }
        },
        ordered_task_ids=["task-1"],
        manifest_payload={"tasks": {"task-1": {"status": "done"}}},
        timestamp="2026-03-30T00:00:00+00:00",
    )

    assert normalized["tasks"]["task-1"]["status"] == "error"
    assert normalized["tasks"]["task-1"]["error"] == "missing or unparseable SWE-bench report"
    assert normalized["tasks"]["task-1"]["error_category"] == "report_parse"


def test_ordered_task_ids_prefers_run_config_subset(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    results_root = tmp_path / "results" / "iteration-123"
    results_root.mkdir(parents=True)
    (results_root / "_run_config.json").write_text(
        json.dumps({"evals_to_run": ["task-c", "task-a"]}) + "\n",
        encoding="utf-8",
    )

    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text(json.dumps(["global-1", "global-2"]) + "\n", encoding="utf-8")
    monkeypatch.setattr(score_experiment, "TASKS_PATH", tasks_path)

    ordered = _ordered_task_ids(
        {"tasks": {"task-a": {}, "task-b": {}, "task-c": {}}},
        results_root,
    )

    assert ordered == ["task-c", "task-a", "task-b"]
