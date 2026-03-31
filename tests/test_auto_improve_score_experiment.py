from auto_improve.score_experiment import _normalize_scores_payload


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
