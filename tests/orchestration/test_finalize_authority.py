from __future__ import annotations

import json
import hashlib
import ast
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.orchestration.finalize_authority import (
    FinalizeCASMismatch,
    FinalizeFieldOwnershipError,
    FinalizeMutationContext,
    FinalizeReadToken,
    current_finalize_token,
    load_finalize_for_update,
    publish_finalize_candidate,
    publish_finalize_update,
)


def _candidate(description: str = "implement authority") -> dict:
    return {
        "tasks": [
            {
                "id": "T1",
                "description": description,
                "kind": "code",
                "depends_on": [],
                "complexity": 4,
                "complexity_justification": "Touches the publication boundary.",
                "status": "pending",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            }
        ],
        "sense_checks": [
            {
                "id": "SC1",
                "task_id": "T1",
                "question": "Is authority singular?",
                "verdict": "",
            }
        ],
        "watch_items": [],
        "user_actions": [],
        "meta_commentary": "",
    }


def _context(owner: str, operation: str, attempt: str) -> FinalizeMutationContext:
    return FinalizeMutationContext(  # type: ignore[arg-type]
        owner=owner,
        operation=operation,
        attempt_id=attempt,
        run_id="run-9",
    )


def _publish_initial(plan_dir: Path) -> None:
    publish_finalize_candidate(
        plan_dir,
        _candidate(),
        context=_context("finalize", "publish-candidate", "finalize-9"),
        expected_parent=FinalizeReadToken(None, 0),
    )


def test_stale_execute_writer_cannot_overwrite_newer_valid_candidate(tmp_path: Path) -> None:
    _publish_initial(tmp_path)
    stale = load_finalize_for_update(tmp_path)

    replacement = _candidate("new admitted candidate")
    publish_finalize_candidate(
        tmp_path,
        replacement,
        context=_context("finalize", "publish-replacement", "finalize-10"),
        expected_parent=current_finalize_token(tmp_path),
    )

    stale["tasks"][0]["status"] = "done"
    with pytest.raises(FinalizeCASMismatch, match="stale finalize mutation refused"):
        publish_finalize_update(
            tmp_path,
            stale,
            context=_context("execute", "late-timeout", "execute-8"),
        )

    saved = json.loads((tmp_path / "finalize.json").read_text(encoding="utf-8"))
    assert saved["tasks"][0]["description"] == "new admitted candidate"
    assert saved["tasks"][0]["status"] == "pending"


def test_stale_finalize_attempt_cannot_replace_newer_receipt(tmp_path: Path) -> None:
    _publish_initial(tmp_path)
    stale_parent = current_finalize_token(tmp_path)
    publish_finalize_candidate(
        tmp_path,
        _candidate("winning candidate"),
        context=_context("finalize", "publish-winning", "finalize-10"),
        expected_parent=stale_parent,
    )

    with pytest.raises(FinalizeCASMismatch):
        publish_finalize_candidate(
            tmp_path,
            _candidate("late stale candidate"),
            context=_context("finalize", "publish-late", "finalize-9-retry"),
            expected_parent=stale_parent,
        )

    saved = json.loads((tmp_path / "finalize.json").read_text(encoding="utf-8"))
    assert saved["tasks"][0]["description"] == "winning candidate"


def test_execute_owner_is_field_scoped(tmp_path: Path) -> None:
    _publish_initial(tmp_path)
    payload = load_finalize_for_update(tmp_path)
    payload["tasks"][0]["description"] = "silently changed graph"

    with pytest.raises(FinalizeFieldOwnershipError, match="description"):
        publish_finalize_update(
            tmp_path,
            payload,
            context=_context("execute", "merge-batch", "execute-9"),
        )

    assert json.loads((tmp_path / "finalize.json").read_text())["tasks"][0][
        "description"
    ] == "implement authority"


def test_execute_owner_can_publish_only_runtime_fields(tmp_path: Path) -> None:
    _publish_initial(tmp_path)
    payload = load_finalize_for_update(tmp_path)
    payload["tasks"][0]["status"] = "done"
    payload["tasks"][0]["executor_notes"] = "verified"
    payload["sense_checks"][0]["executor_note"] = "checked"

    token = publish_finalize_update(
        tmp_path,
        payload,
        context=_context("execute", "publish-completion", "execute-9"),
    )

    assert token.version == 2
    saved = json.loads((tmp_path / "finalize.json").read_text())
    assert saved["tasks"][0]["status"] == "done"
    assert saved["tasks"][0]["description"] == "implement authority"


def test_execute_owner_can_publish_stamped_evidence_context_fields(tmp_path: Path) -> None:
    """Regression: the execute seam stamps/merges head_sha and code_hash onto
    task records (batch.py:_stamp_head_sha_on_task_records and merge.py
    evidence_context_fields).  The execute owner must be able to publish those
    fields, or every completed batch aborts with FinalizeFieldOwnershipError
    before finalize.json is updated — which surfaced as the recurring
    ``17/17 sense checks have no executor acknowledgment`` execute blocker.
    """
    _publish_initial(tmp_path)
    payload = load_finalize_for_update(tmp_path)
    payload["tasks"][0]["status"] = "done"
    payload["tasks"][0]["executor_notes"] = "verified"
    payload["tasks"][0]["head_sha"] = "8e80ecc950e36e3126f14f1d24e73919d6779b7d"
    payload["tasks"][0]["code_hash"] = "sha256:deadbeef"
    payload["sense_checks"][0]["executor_note"] = "checked"

    token = publish_finalize_update(
        tmp_path,
        payload,
        context=_context("execute", "publish-completion", "execute-9"),
    )

    assert token.version == 2
    saved = json.loads((tmp_path / "finalize.json").read_text())
    assert saved["tasks"][0]["status"] == "done"
    assert saved["tasks"][0]["head_sha"] == "8e80ecc950e36e3126f14f1d24e73919d6779b7d"
    assert saved["tasks"][0]["code_hash"] == "sha256:deadbeef"
    assert saved["sense_checks"][0]["executor_note"] == "checked"


def test_execute_owner_can_publish_durable_budget_block_identity(
    tmp_path: Path,
) -> None:
    """Regression (astrid-first 0a0ce24c3510 drive5): the merge budget gate
    stamps a durable ``task_test_budget_exhausted`` string on the task row
    (merge.py:_enforce_task_test_budgets, occurrence 0513dbf3f069) so the
    retry reset cannot erase the budget-block identity.  The execute publisher
    propagates the merged rows into the finalize projection at the end of the
    auto loop; finalize_authority must let the execute owner publish that field
    or the publish aborts with FinalizeFieldOwnershipError and the plan wedges
    with done tasks never published (observed: T2 row, batch_23 merge).
    """
    _publish_initial(tmp_path)
    payload = load_finalize_for_update(tmp_path)
    payload["tasks"][0]["status"] = "blocked"
    payload["tasks"][0]["executor_notes"] = (
        "[harness] task_test_budget_exhausted: declared test timeout total "
        "240s exceeds max_seconds=120"
    )
    payload["tasks"][0]["task_test_budget_exhausted"] = (
        "task_test_budget_exhausted: declared test timeout total 240s exceeds "
        "max_seconds=120"
    )

    token = publish_finalize_update(
        tmp_path,
        payload,
        context=_context("execute", "publish-completion", "execute-9"),
    )

    assert token.version == 2
    saved = json.loads((tmp_path / "finalize.json").read_text())
    assert saved["tasks"][0]["status"] == "blocked"
    assert "task_test_budget_exhausted" in saved["tasks"][0]
    assert saved["tasks"][0]["task_test_budget_exhausted"].startswith(
        "task_test_budget_exhausted:"
    )


def test_only_finalize_owner_can_create_document(tmp_path: Path) -> None:
    payload = _candidate()
    # A detached payload cannot smuggle itself into the update path.
    with pytest.raises(FinalizeCASMismatch, match="no read token"):
        publish_finalize_update(
            tmp_path,
            payload,
            context=_context("execute", "create", "execute-1"),
        )
    with pytest.raises(FinalizeFieldOwnershipError, match="requires finalize owner"):
        publish_finalize_candidate(
            tmp_path,
            payload,
            context=_context("execute", "create", "execute-1"),
            expected_parent=FinalizeReadToken(None, 0),
        )


def test_successful_mutations_leave_immutable_attempt_history(tmp_path: Path) -> None:
    _publish_initial(tmp_path)
    payload = load_finalize_for_update(tmp_path)
    payload["tasks"][0]["status"] = "done"
    publish_finalize_update(
        tmp_path,
        payload,
        context=_context("execute", "publish-completion", "execute-9"),
    )

    receipts = sorted((tmp_path / "finalize_history" / "mutations").glob("*.json"))
    snapshots = sorted((tmp_path / "finalize_history" / "snapshots").glob("*.json"))
    assert len(receipts) == 2
    assert len(snapshots) == 2
    history = [json.loads(path.read_text()) for path in receipts]
    assert [item["version"] for item in history] == [1, 2]
    assert [item["attempt_id"] for item in history] == ["finalize-9", "execute-9"]
    assert history[1]["parent_sha256"] == history[0]["result_sha256"]
    assert "tasks[T1].status" in history[1]["changed_paths"]
    for snapshot in snapshots:
        assert snapshot.stem == hashlib.sha256(snapshot.read_bytes()).hexdigest()


def test_unpublished_receipt_cannot_steal_identical_retry_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import arnold_pipelines.megaplan.orchestration.finalize_authority as authority

    _publish_initial(tmp_path)
    payload = load_finalize_for_update(tmp_path)
    payload["tasks"][0]["status"] = "done"
    real_writer = authority.write_plan_artifact_json

    def fail_publication(*args, **kwargs):
        raise OSError("simulated publication failure")

    monkeypatch.setattr(authority, "write_plan_artifact_json", fail_publication)
    with pytest.raises(OSError, match="simulated publication failure"):
        publish_finalize_update(
            tmp_path,
            payload,
            context=_context("execute", "failed-timeout", "attempt-failed"),
        )

    # The failed attempt prepared a receipt but did not commit it.
    assert len(list((tmp_path / "finalize_history" / "mutations").glob("*.json"))) == 2
    assert len(list((tmp_path / "finalize_history" / "commits").glob("*.json"))) == 1
    assert current_finalize_token(tmp_path).version == 1

    monkeypatch.setattr(authority, "write_plan_artifact_json", real_writer)
    retry = load_finalize_for_update(tmp_path)
    retry["tasks"][0]["status"] = "done"
    publish_finalize_update(
        tmp_path,
        retry,
        context=_context("execute", "successful-retry", "attempt-retry"),
    )

    assert current_finalize_token(tmp_path).version == 2
    committed = []
    history_root = tmp_path / "finalize_history"
    for marker_path in (history_root / "commits").glob("*.json"):
        marker = json.loads(marker_path.read_text())
        committed.append(json.loads((history_root / marker["receipt_ref"]).read_text()))
    assert {item["attempt_id"] for item in committed} == {"finalize-9", "attempt-retry"}
    assert "attempt-failed" not in {item["attempt_id"] for item in committed}


def test_no_competing_finalize_document_writer_remains() -> None:
    package = Path(__file__).resolve().parents[2] / "arnold_pipelines" / "megaplan"
    writers: list[str] = []
    writer_calls = {"atomic_write_json", "write_plan_artifact_json", "_write_json_atomic"}
    for source in package.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ""
            )
            if name not in writer_calls:
                continue
            if any(
                isinstance(child, ast.Constant) and child.value == "finalize.json"
                for child in ast.walk(node)
            ):
                writers.append(f"{source.relative_to(package)}:{node.lineno}:{name}")

    assert len(writers) == 1
    assert writers[0].startswith("orchestration/finalize_authority.py:")
    assert writers[0].endswith(":write_plan_artifact_json")