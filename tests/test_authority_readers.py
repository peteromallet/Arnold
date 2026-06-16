from __future__ import annotations

import json
from pathlib import Path

from arnold.pipelines.megaplan.orchestration.authority_readers import (
    AUTHORITY_DIVERGENCE_LEDGER,
    AuthorityDecision,
    corroborated_completed_task_ids,
    scheduler_completed_ids,
)
from arnold.pipelines.megaplan.observability.events import EventKind, _ALL_EVENT_KINDS
from arnold.pipelines.megaplan.orchestration.evidence_contract import EvidenceStatus


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_corroborated_completed_task_ids_accepts_satisfied_task_output(tmp_path):
    task = {"id": "T1", "status": "done", "files_changed": ["src/a.py"]}
    _write_json(
        tmp_path / "execution_batch_1.json",
        {
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "files_changed": ["src/a.py"],
                }
            ]
        },
    )

    decisions: dict[str, AuthorityDecision] = {}
    completed = corroborated_completed_task_ids([task], plan_dir=tmp_path, decisions=decisions)

    assert completed == {"T1"}
    assert decisions["T1"].status == EvidenceStatus.satisfied
    assert decisions["T1"].diagnostics["raw_terminal_status"] == "done"


def test_corroborated_completed_task_ids_missing_output_is_not_authoritative(tmp_path):
    task = {"id": "T1", "status": "done", "files_changed": ["src/a.py"]}
    _write_json(
        tmp_path / "execution_batch_1.json",
        {"task_updates": [{"task_id": "T1", "status": "done", "commands_run": ["pytest -q"]}]},
    )

    decisions: dict[str, AuthorityDecision] = {}
    completed = corroborated_completed_task_ids([task], plan_dir=tmp_path, decisions=decisions)

    assert completed == set()
    assert decisions["T1"].status == EvidenceStatus.unsatisfied
    assert "files_changed:src/a.py" in decisions["T1"].missing_outputs


def test_corroborated_completed_task_ids_stale_head_and_code_hash_are_not_authoritative(tmp_path):
    task = {
        "id": "T1",
        "status": "done",
        "files_changed": ["src/a.py"],
        "commands_run": ["pytest -q"],
    }
    _write_json(
        tmp_path / "execution_batch_1.json",
        {
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "files_changed": ["src/a.py"],
                    "commands_run": ["pytest -q"],
                    "head_sha": "old-head",
                    "code_hash": "old-hash",
                }
            ]
        },
    )

    decisions: dict[str, AuthorityDecision] = {}
    completed = corroborated_completed_task_ids(
        [task],
        plan_dir=tmp_path,
        current_head="new-head",
        current_code_hash="new-hash",
        decisions=decisions,
    )

    assert completed == set()
    assert decisions["T1"].status == EvidenceStatus.unsatisfied
    assert any(item.startswith("head_mismatch") for item in decisions["T1"].stale_evidence)
    assert any(item.startswith("code_hash_mismatch") for item in decisions["T1"].stale_evidence)


def test_corroborated_completed_task_ids_legacy_done_without_evidence_is_unknown(tmp_path):
    task = {"id": "T1", "status": "done"}
    _write_json(
        tmp_path / "execution_batch_1.json",
        {"task_updates": [{"task_id": "T1", "status": "done"}]},
    )

    decisions: dict[str, AuthorityDecision] = {}
    completed = corroborated_completed_task_ids([task], plan_dir=tmp_path, decisions=decisions)

    assert completed == set()
    assert decisions["T1"].status == EvidenceStatus.unknown
    assert decisions["T1"].would_block_reasons == ("missing_linked_evidence",)
    assert EventKind.AUTHORITY_DIVERGENCE in _ALL_EVENT_KINDS

    divergence_path = tmp_path / AUTHORITY_DIVERGENCE_LEDGER
    assert divergence_path.exists()
    divergence = json.loads(divergence_path.read_text(encoding="utf-8").splitlines()[0])
    assert divergence["task_id"] == "T1"
    assert divergence["diagnostic_version"] == 1
    assert divergence["raw_terminal_status"] == "done"
    assert divergence["authority_status"] == EvidenceStatus.unknown.value
    assert divergence["authoritative"] is False
    assert divergence["reason"] == "missing_linked_evidence"
    assert divergence["missing_outputs"] == []
    assert divergence["stale_evidence"] == []
    assert divergence["would_block_reasons"] == ["missing_linked_evidence"]
    assert divergence["error"] is None
    assert "ts_utc" in divergence

    event_lines = (tmp_path / "events.ndjson").read_text(encoding="utf-8").splitlines()
    emitted = [json.loads(line) for line in event_lines]
    assert emitted[-1]["kind"] == EventKind.AUTHORITY_DIVERGENCE
    assert emitted[-1]["phase"] == "execute"
    assert emitted[-1]["payload"]["task_id"] == "T1"
    assert emitted[-1]["payload"]["raw_terminal_status"] == "done"
    assert emitted[-1]["payload"]["authority_status"] == EvidenceStatus.unknown.value
    assert emitted[-1]["payload"]["missing_outputs"] == []
    assert emitted[-1]["payload"]["stale_evidence"] == []
    assert emitted[-1]["payload"]["would_block_reasons"] == ["missing_linked_evidence"]
    assert emitted[-1]["payload"]["diagnostics"]["raw_terminal_status"] == "done"


def test_corroborated_completed_task_ids_accepts_substantive_audit_notes(tmp_path):
    notes = (
        "Verified the control-flow contract by inspecting validator.py and types.py: "
        "decision_routes are read via getattr, non-None route values are checked "
        "against outgoing labels, and suspension_schema remains available on both "
        "stage types for schema-key conformance."
    )
    task = {"id": "T1", "status": "done", "kind": "audit"}
    _write_json(
        tmp_path / "execution_batch_1.json",
        {
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "kind": "audit",
                    "executor_notes": notes,
                    "files_changed": [],
                    "commands_run": [],
                }
            ]
        },
    )

    decisions: dict[str, AuthorityDecision] = {}
    completed = corroborated_completed_task_ids([task], plan_dir=tmp_path, decisions=decisions)

    assert completed == {"T1"}
    assert decisions["T1"].status == EvidenceStatus.satisfied
    assert decisions["T1"].evidence[0].kind == "task_executor_notes"


def test_corroborated_completed_task_ids_rejects_code_task_with_notes_only(tmp_path):
    notes = (
        "Verified behavior carefully and wrote detailed notes, but this code task "
        "does not include changed files or commands that can corroborate the claim."
    )
    task = {"id": "T1", "status": "done", "kind": "code"}
    _write_json(
        tmp_path / "execution_batch_1.json",
        {
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "kind": "code",
                    "executor_notes": notes,
                    "files_changed": [],
                    "commands_run": [],
                }
            ]
        },
    )

    decisions: dict[str, AuthorityDecision] = {}
    completed = corroborated_completed_task_ids([task], plan_dir=tmp_path, decisions=decisions)

    assert completed == set()
    assert decisions["T1"].status == EvidenceStatus.unknown
    assert decisions["T1"].would_block_reasons == ("missing_linked_evidence",)


def test_corroborated_completed_task_ids_skipped_with_waiver_is_authoritative(tmp_path):
    task = {"id": "T1", "status": "skipped"}
    _write_json(
        tmp_path / "execution_batch_1.json",
        {
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "skipped",
                    "evidence": [
                        {
                            "kind": "operator_waiver",
                            "status": "waived",
                            "summary": "waived by reviewer",
                            "subject": "T1",
                            "details": {"task_id": "T1"},
                        }
                    ],
                }
            ]
        },
    )

    decisions: dict[str, AuthorityDecision] = {}
    completed = corroborated_completed_task_ids([task], plan_dir=tmp_path, decisions=decisions)

    assert completed == {"T1"}
    assert decisions["T1"].status == EvidenceStatus.waived


def test_corroborated_completed_task_ids_skipped_without_waiver_is_unknown(tmp_path):
    task = {"id": "T1", "status": "skipped"}
    _write_json(
        tmp_path / "execution_batch_1.json",
        {"task_updates": [{"task_id": "T1", "status": "skipped"}]},
    )

    decisions: dict[str, AuthorityDecision] = {}
    completed = corroborated_completed_task_ids([task], plan_dir=tmp_path, decisions=decisions)

    assert completed == set()
    assert decisions["T1"].status == EvidenceStatus.unknown


def test_corroborated_completed_task_ids_continues_after_partial_batch_failure(tmp_path):
    tasks = [
        {"id": "T1", "status": "done"},
        {"id": "T2", "status": "done", "files_changed": ["src/b.py"]},
    ]
    (tmp_path / "execution_batch_1.json").write_text("{not-json", encoding="utf-8")
    _write_json(
        tmp_path / "execution_batch_2.json",
        {
            "task_updates": [
                {"task_id": "T2", "status": "done", "files_changed": ["src/b.py"]}
            ]
        },
    )

    decisions: dict[str, AuthorityDecision] = {}
    completed = corroborated_completed_task_ids(tasks, plan_dir=tmp_path, decisions=decisions)

    assert completed == {"T2"}
    assert decisions["T1"].status == EvidenceStatus.unknown
    assert decisions["T2"].status == EvidenceStatus.satisfied


def test_scheduler_completed_ids_uses_authority_adapter_semantics(tmp_path):
    tasks = [
        {"id": "T1", "status": "done", "files_changed": ["src/a.py"]},
        {"id": "T2", "status": "done"},
    ]
    _write_json(
        tmp_path / "execution_batch_1.json",
        {
            "task_updates": [
                {
                    "task_id": "T1",
                    "status": "done",
                    "files_changed": ["src/a.py"],
                },
                {
                    "task_id": "T2",
                    "status": "done",
                },
            ]
        },
    )

    assert scheduler_completed_ids(tasks, plan_dir=tmp_path) == {"T1"}


def test_corroborated_completed_task_ids_ignores_divergence_write_failures(tmp_path, monkeypatch):
    task = {"id": "T1", "status": "done"}
    _write_json(
        tmp_path / "execution_batch_1.json",
        {"task_updates": [{"task_id": "T1", "status": "done"}]},
    )

    def _raise_jsonl(*args, **kwargs):
        raise OSError("jsonl down")

    def _raise_event(*args, **kwargs):
        raise RuntimeError("event sink down")

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.orchestration.authority_readers._append_authority_divergence_jsonl",
        _raise_jsonl,
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.orchestration.authority_readers.emit",
        _raise_event,
    )

    decisions: dict[str, AuthorityDecision] = {}
    completed = corroborated_completed_task_ids([task], plan_dir=tmp_path, decisions=decisions)

    assert completed == set()
    assert decisions["T1"].status == EvidenceStatus.unknown
    assert not (tmp_path / AUTHORITY_DIVERGENCE_LEDGER).exists()
    assert not (tmp_path / "events.ndjson").exists()
