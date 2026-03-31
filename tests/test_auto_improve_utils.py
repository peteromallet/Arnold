import json

import auto_improve.utils as utils


def _scores(anchor_ids, retry_ids, infra_ids=(), *, retry_error_category=None):
    tasks = {}
    for task_id in anchor_ids:
        tasks[task_id] = {"resolved": True, "status": "resolved"}
    for task_id in retry_ids:
        tasks[task_id] = {"resolved": False, "status": "failed"}
    for task_id in infra_ids:
        payload = {"resolved": False, "status": "error"}
        if retry_error_category:
            payload["error_category"] = retry_error_category
        tasks[task_id] = payload
    return {"tasks": tasks}


def test_suggest_task_rotation_uses_history_backfill_for_anchor_and_retry_counts():
    latest_scores = _scores(
        [f"anchor-latest-{index}" for index in range(1, 6)],
        [f"retry-latest-{index}" for index in range(1, 4)],
        [f"infra-latest-{index}" for index in range(1, 3)],
        retry_error_category="modal_sandbox",
    )
    previous_scores = _scores(
        [f"anchor-prev-{index}" for index in range(1, 8)],
        [f"retry-prev-{index}" for index in range(1, 6)],
    )
    full_pool = [
        *latest_scores["tasks"].keys(),
        *previous_scores["tasks"].keys(),
        *[f"new-{index}" for index in range(1, 8)],
    ]

    suggestion = utils.suggest_task_rotation(
        latest_scores,
        full_pool,
        historical_scores=[previous_scores],
        attempted_task_ids=set(latest_scores["tasks"]) | set(previous_scores["tasks"]),
        seed=2,
    )

    assert len(suggestion) == 20
    assert suggestion[:10] == [
        "anchor-latest-1",
        "anchor-latest-2",
        "anchor-latest-3",
        "anchor-latest-4",
        "anchor-latest-5",
        "anchor-prev-1",
        "anchor-prev-2",
        "anchor-prev-3",
        "anchor-prev-4",
        "anchor-prev-5",
    ]
    assert suggestion[10:15] == [
        "retry-latest-1",
        "retry-latest-2",
        "retry-latest-3",
        "retry-prev-1",
        "retry-prev-2",
    ]
    assert len(set(suggestion[15:])) == 5
    assert all(task_id.startswith("new-") for task_id in suggestion[15:])


def test_main_suggest_rotation_prints_json(monkeypatch, capsys):
    latest_scores = _scores(
        [f"anchor-{index}" for index in range(1, 11)],
        [f"retry-{index}" for index in range(1, 6)],
    )
    full_pool = [
        *latest_scores["tasks"].keys(),
        *[f"new-{index}" for index in range(1, 8)],
    ]

    monkeypatch.setattr(utils, "_load_score_history", lambda iteration: [latest_scores])
    monkeypatch.setattr(utils, "_load_verified_task_pool", lambda: full_pool)

    exit_code = utils.main(["suggest-rotation", "--iteration", "2"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert len(output) == 20
    assert output[:10] == [f"anchor-{index}" for index in range(1, 11)]
    assert output[10:15] == [f"retry-{index}" for index in range(1, 6)]
