from __future__ import annotations

import json

from arnold_pipelines.megaplan.resident import vp_todo


def test_load_missing_file_is_empty(tmp_path) -> None:
    assert vp_todo.load_items(tmp_path / "missing.json") == []


def test_load_empty_and_malformed(tmp_path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text("")
    assert vp_todo.load_items(empty) == []
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert vp_todo.load_items(bad) == []


def test_add_then_complete_clears(tmp_path) -> None:
    path = tmp_path / "todo.json"
    item = vp_todo.add_item(path, "do the thing")
    assert item["status"] == "pending"
    assert len(vp_todo.load_items(path)) == 1

    completed = vp_todo.complete_item(path, item["id"], "done!")
    assert completed is not None
    assert completed["status"] == "done"
    assert completed["result"] == "done!"
    # completing clears the item from the file
    assert vp_todo.load_items(path) == []


def test_fail_is_retained_and_not_pending(tmp_path) -> None:
    path = tmp_path / "todo.json"
    item = vp_todo.add_item(path, "do the thing")
    failed = vp_todo.fail_item(path, item["id"], "boom")
    assert failed is not None
    assert failed["status"] == "failed"
    assert failed["reason"] == "boom"
    items = vp_todo.load_items(path)
    assert len(items) == 1
    assert items[0]["status"] == "failed"
    # failed items are retained, not picked up as pending
    assert vp_todo.pending_items(path) == []


def test_supersede_by_canonical_record_retains_history_without_completion(tmp_path) -> None:
    path = tmp_path / "todo.json"
    item = vp_todo.add_item(path, "launch retired initiative")

    resolved = vp_todo.supersede_by_record(
        path,
        item["id"],
        canonical_record_id="initiative:replacement",
        evidence="target-ref:.megaplan/initiatives/old/.retired@abc123",
        resolution="canonical initiative retirement replaced this launch intent",
    )

    assert resolved is not None
    assert resolved["status"] == vp_todo.SUPERSEDED
    assert resolved["canonical_record_id"] == "initiative:replacement"
    assert resolved["canonical_record_evidence"].endswith("@abc123")
    assert resolved["transition_history"][-1]["from"] == vp_todo.PENDING
    assert resolved["transition_history"][-1]["to"] == vp_todo.SUPERSEDED
    assert vp_todo.pending_items(path) == []
    assert vp_todo.load_items(path)[0]["status"] != vp_todo.DONE


def test_supersede_by_record_normalizes_unreleased_status_for_old_runtime_compatibility(
    tmp_path,
) -> None:
    path = tmp_path / "todo.json"
    item = vp_todo.add_item(path, "obsolete launch")
    record_id = "initiative:replacement"
    evidence = "retirement.json#sha256=abc"
    vp_todo.save_items(
        path,
        [
            {
                **item,
                "status": vp_todo.SUPERSEDED_BY_RECORD,
                "canonical_record_id": record_id,
                "canonical_record_evidence": evidence,
                "resolution": "retired",
            }
        ],
    )

    normalized = vp_todo.supersede_by_record(
        path,
        item["id"],
        canonical_record_id=record_id,
        evidence=evidence,
        resolution="retired",
    )

    assert normalized is not None
    assert normalized["status"] == vp_todo.SUPERSEDED
    assert normalized["transition_history"][-1]["from"] == vp_todo.SUPERSEDED_BY_RECORD
    assert vp_todo.load_items(path)[0]["status"] == vp_todo.SUPERSEDED


def test_pending_filters_terminal_states(tmp_path) -> None:
    path = tmp_path / "todo.json"
    vp_todo.save_items(
        path,
        [
            {"id": "a", "task": "t1", "status": "pending", "result": "", "reason": "", "updated_at": "x"},
            {"id": "b", "task": "t2", "status": "done", "result": "", "reason": "", "updated_at": "x"},
            {"id": "c", "task": "t3", "status": "failed", "result": "", "reason": "", "updated_at": "x"},
        ],
    )
    pending = vp_todo.pending_items(path)
    assert [item["id"] for item in pending] == ["a"]


def test_complete_and_fail_unknown_return_none(tmp_path) -> None:
    path = tmp_path / "todo.json"
    vp_todo.add_item(path, "x")
    assert vp_todo.complete_item(path, "nope", "r") is None
    assert vp_todo.fail_item(path, "nope", "r") is None


def test_coerces_user_authored_file(tmp_path) -> None:
    path = tmp_path / "todo.json"
    path.write_text(json.dumps({"items": [{"task": "hello"}, {"task": "world", "status": "pending"}]}))
    items = vp_todo.load_items(path)
    assert [item["task"] for item in items] == ["hello", "world"]
    assert all(item["status"] == "pending" for item in items)
    assert all(item["id"] for item in items)  # ids synthesized when absent


def test_save_is_atomic_round_trip(tmp_path) -> None:
    path = tmp_path / "nested" / "todo.json"
    vp_todo.add_item(path, "one")
    vp_todo.add_item(path, "two")
    raw = json.loads(path.read_text())
    assert [item["task"] for item in raw["items"]] == ["one", "two"]
    assert not (path.with_suffix(".json.tmp")).exists()


def test_add_and_coerce_preserve_when(tmp_path) -> None:
    path = tmp_path / "todo.json"
    item = vp_todo.add_item(path, "ship it", when="once epic ABC is done")
    assert item["when"] == "once epic ABC is done"
    # round-trips through load/coerce
    reloaded = vp_todo.load_items(path)
    assert reloaded[0]["when"] == "once epic ABC is done"
    # default when is empty string
    other = vp_todo.add_item(path, "no condition")
    assert other["when"] == ""


def test_delegate_transfers_pending_item_to_canonical_run(tmp_path) -> None:
    path = tmp_path / "todo.json"
    item = vp_todo.add_item(path, "execute durable work")

    delegated = vp_todo.delegate_item(
        path,
        item["id"],
        canonical_run_id="run-123",
        evidence="/runs/run-123/manifest.json",
    )

    assert delegated is not None
    assert delegated["status"] == vp_todo.DELEGATED
    assert delegated["canonical_run_id"] == "run-123"
    assert vp_todo.pending_items(path) == []
    assert delegated["transition_history"][-1]["from"] == vp_todo.PENDING
