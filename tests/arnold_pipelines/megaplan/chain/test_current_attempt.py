from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace

import pytest

from arnold_pipelines.megaplan.chain import current_attempt
def _write_json(path: Path, value: dict[str, object]) -> bytes:
    raw = (json.dumps(value, indent=2) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def _fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    chain_path = tmp_path / "chain-state.json"
    plan_dir = tmp_path / ".megaplan" / "plans" / "C2"
    plan_path = plan_dir / "state.json"
    marker_path = tmp_path / "session-marker.json"
    chain_id = "chain-c2-test"
    session = "session-c2"
    pause = {"active": True, "reason": "operator-hold", "session": session}
    source = {"branch": "docs/nbf-epic-artifact-update-20260903", "sha": "b0"}
    runtime = {"container": "runtime-c2", "commit": "b0"}
    prefix = [{"label": f"S{i}", "sha256": f"prefix-{i}"} for i in range(6)]
    chain = {
        "metadata": {
            "chain_id": chain_id,
            "operator_pause": pause,
            "project_source_binding": source,
            "execution_binding": {"launched_identity": {"runtime": runtime}},
            "_nbf08_revision": 4,
        },
        "chain_session": session,
        "current_milestone_index": 6,
        "current_plan_name": "C2",
        "last_state": "paused",
        "completed": prefix,
    }
    plan_pause = dict(pause)
    plan = {
        "name": "C2",
        "current_state": "paused",
        "active_step": {
            "invocation_id": "inv-1",
            "phase": "execute",
            "run_id": "run-1",
            "attempt_number": 1,
            "phase_wbc": {"phase": "execute", "attempt_id": "wbc-1"},
        },
        "meta": {
            "current_invocation_id": "inv-1",
            "run_id": "run-1",
            "attempt_number": 1,
            "phase_wbc": {"phase": "execute", "attempt_id": "wbc-1"},
            "operator_pause": plan_pause,
            "project_source_binding": source,
            "_nbf08_revision": 2,
        },
    }
    marker = {
        "should_run": False,
        "operator_pause": pause,
        "operator_resume_hold": {"active": True, "session": session, "spec": str(spec_path.resolve())},
        "runtime_identity": runtime,
    }
    chain_raw = _write_json(chain_path, chain)
    plan_raw = _write_json(plan_path, plan)
    marker_raw = _write_json(marker_path, marker)
    monkeypatch.setattr(current_attempt, "find_plan_dir", lambda _root, _name: plan_dir)
    monkeypatch.setattr(current_attempt.chain_spec, "_state_path_for", lambda _path: chain_path)
    monkeypatch.setattr(current_attempt.chain_spec, "load_spec", lambda _path: SimpleNamespace(milestones=[SimpleNamespace(label=f"S{i}") for i in range(6)] + [SimpleNamespace(label="C2")]))
    monkeypatch.setattr(current_attempt, "chain_id_for_spec", lambda _path: chain_id)
    guards = current_attempt.CurrentAttemptGuards(
        expected_session_id=session,
        expected_current_plan="C2",
        expected_current_milestone="C2",
        expected_cursor=6,
        expected_spec_sha256=hashlib.sha256(spec_path.read_bytes()).hexdigest(),
        expected_chain_state_sha256=hashlib.sha256(chain_raw).hexdigest(),
        expected_plan_state_sha256=hashlib.sha256(plan_raw).hexdigest(),
        expected_marker_sha256=hashlib.sha256(marker_raw).hexdigest(),
        expected_attempt_identity={
            "schema": "arnold.megaplan.current-attempt-identity.v1",
            "invocation_id": "inv-1",
            "phase": "execute",
            "run_id": "run-1",
            "attempt_number": 1,
            "wbc_attempt_id": "wbc-1",
        },
        expected_completed_prefix=tuple(prefix),
        expected_chain_revision=4,
        expected_plan_revision=2,
        expected_source_binding=source,
        expected_runtime_identity=runtime,
        expected_hold=marker["operator_resume_hold"],
    )
    args = {
        "spec_path": spec_path,
        "project_dir": tmp_path,
        "marker_path": marker_path,
        "guards": guards,
        "reason": "recover paused progressed C2",
    }
    return args, {"chain_path": chain_path, "plan_path": plan_path, "marker_path": marker_path, "prefix": prefix}


def test_adoption_preserves_prefix_and_replays_without_dispatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args, paths = _fixture(monkeypatch, tmp_path)
    first = current_attempt.restart_current_attempt(**args)
    second = current_attempt.restart_current_attempt(**args)

    assert first["outcome"] == "committed"
    assert second["outcome"] == "replay"
    chain = json.loads(paths["chain_path"].read_text())
    assert chain["current_milestone_index"] == 6
    assert chain["current_plan_name"] is None
    assert chain["completed"] == paths["prefix"]
    assert chain["metadata"]["current_attempt_continuation"]["continuation_id"].startswith("c2-continuation-")
    events = current_attempt.journal_for(tmp_path).replay_strict()["accepted"]
    assert [event["event_kind"] for event in events].count("chain_control.current_attempt_adopted") == 1
    assert [event["event_kind"] for event in events].count("chain_control.replay") == 1
    terminal = next(event for event in events if event["event_kind"] == "chain_control.current_attempt_adopted")
    assert terminal["payload"]["effect"]["continuation"]["cursor"] == 6
    assert terminal["payload"]["effect"]["continuation"]["session"] == "session-c2"


def test_adoption_recovers_after_partial_plan_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args, paths = _fixture(monkeypatch, tmp_path)

    def crash(stage: str) -> None:
        if stage == "after_plan_cas":
            raise RuntimeError("simulated crash")

    with pytest.raises(RuntimeError, match="simulated crash"):
        current_attempt.restart_current_attempt(**args, failure_injector=crash)
    recovered = current_attempt.restart_current_attempt(**args)
    assert recovered["outcome"] == "committed"
    chain = json.loads(paths["chain_path"].read_text())
    assert chain["current_plan_name"] is None
    assert chain["completed"] == paths["prefix"]


def test_interrupted_recovery_rejects_spec_byte_divergence_without_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args, paths = _fixture(monkeypatch, tmp_path)

    def crash(stage: str) -> None:
        if stage == "after_plan_cas":
            raise RuntimeError("simulated crash")

    with pytest.raises(RuntimeError, match="simulated crash"):
        current_attempt.restart_current_attempt(**args, failure_injector=crash)
    journal = current_attempt.journal_for(tmp_path)
    snapshot_paths = (
        paths["chain_path"], paths["plan_path"], paths["marker_path"], args["spec_path"], journal.ledger.events_path
    )
    before = {path: path.read_bytes() for path in snapshot_paths}
    args["spec_path"].write_bytes(args["spec_path"].read_bytes() + b"# semantic-preserving change\n")

    with pytest.raises(current_attempt.CurrentAttemptAdoptionError) as exc:
        current_attempt.restart_current_attempt(**args)

    assert exc.value.code == "identity_mismatch"
    after = {path: path.read_bytes() for path in snapshot_paths}
    assert after[args["spec_path"]] != before[args["spec_path"]]
    assert all(after[path] == before[path] for path in snapshot_paths if path != args["spec_path"])
    assert json.loads(paths["chain_path"].read_text())["current_plan_name"] == "C2"


def test_interrupted_recovery_rejects_marker_byte_divergence_without_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args, paths = _fixture(monkeypatch, tmp_path)

    def crash(stage: str) -> None:
        if stage == "after_plan_cas":
            raise RuntimeError("simulated crash")

    with pytest.raises(RuntimeError, match="simulated crash"):
        current_attempt.restart_current_attempt(**args, failure_injector=crash)
    journal = current_attempt.journal_for(tmp_path)
    snapshot_paths = (
        paths["chain_path"], paths["plan_path"], paths["marker_path"], args["spec_path"], journal.ledger.events_path
    )
    before = {path: path.read_bytes() for path in snapshot_paths}
    args["marker_path"].write_bytes(args["marker_path"].read_bytes() + b"\n")

    with pytest.raises(current_attempt.CurrentAttemptAdoptionError) as exc:
        current_attempt.restart_current_attempt(**args)

    assert exc.value.code == "identity_mismatch"
    after = {path: path.read_bytes() for path in snapshot_paths}
    assert after[args["marker_path"]] != before[args["marker_path"]]
    assert all(after[path] == before[path] for path in snapshot_paths if path != args["marker_path"])
    assert json.loads(paths["chain_path"].read_text())["current_plan_name"] == "C2"


def test_ambiguous_attempt_refuses_before_journal_mutation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args, paths = _fixture(monkeypatch, tmp_path)
    plan = json.loads(paths["plan_path"].read_text())
    plan["meta"]["current_invocation_id"] = "different"
    _write_json(paths["plan_path"], plan)
    with pytest.raises(current_attempt.CurrentAttemptAdoptionError) as exc:
        current_attempt.restart_current_attempt(**args)
    assert exc.value.code == "identity_mismatch"
    assert json.loads(paths["chain_path"].read_text())["current_plan_name"] == "C2"


@pytest.mark.parametrize(
    "missing_guard",
    ["expected_plan_revision", "expected_source_binding", "expected_runtime_identity", "expected_hold"],
)
def test_missing_authority_guard_refuses_without_creating_journal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, missing_guard: str
) -> None:
    args, _paths = _fixture(monkeypatch, tmp_path)
    args["guards"] = replace(args["guards"], **{missing_guard: None})
    dispatches: list[dict[str, object]] = []
    args["dispatch_handoff"] = dispatches.append
    journal = current_attempt.journal_for(tmp_path)
    events_path = journal.ledger.events_path
    before = events_path.read_bytes() if events_path.exists() else None

    with pytest.raises(current_attempt.CurrentAttemptAdoptionError, match="complete authority guards") as exc:
        current_attempt.restart_current_attempt(**args)

    assert exc.value.code == "missing_guard"
    after = events_path.read_bytes() if events_path.exists() else None
    assert after == before
    assert dispatches == []


def test_wrong_canonical_prefix_refuses_before_journal_mutation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args, paths = _fixture(monkeypatch, tmp_path)
    chain = json.loads(paths["chain_path"].read_text())
    chain["completed"][2]["label"] = "spoofed-prefix"
    chain_raw = _write_json(paths["chain_path"], chain)
    args["guards"] = replace(args["guards"], expected_chain_state_sha256=hashlib.sha256(chain_raw).hexdigest())
    journal = current_attempt.journal_for(tmp_path)
    events_path = journal.ledger.events_path

    with pytest.raises(current_attempt.CurrentAttemptAdoptionError) as exc:
        current_attempt.restart_current_attempt(**args)

    assert exc.value.code == "prefix_mismatch"
    assert not events_path.exists()


def test_plan_pause_authority_mismatch_refuses_without_journal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args, paths = _fixture(monkeypatch, tmp_path)
    plan = json.loads(paths["plan_path"].read_text())
    plan["meta"]["operator_pause"]["session"] = "different-session"
    plan_raw = _write_json(paths["plan_path"], plan)
    args["guards"] = replace(args["guards"], expected_plan_state_sha256=hashlib.sha256(plan_raw).hexdigest())
    journal = current_attempt.journal_for(tmp_path)

    with pytest.raises(current_attempt.CurrentAttemptAdoptionError) as exc:
        current_attempt.restart_current_attempt(**args)

    assert exc.value.code == "identity_mismatch"
    assert not journal.ledger.events_path.exists()


def test_two_concurrent_adopters_commit_once_and_mocked_handoff_dispatches_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args, _paths = _fixture(monkeypatch, tmp_path)
    dispatches: list[str] = []

    def handoff(continuation: dict[str, object]) -> None:
        dispatches.append(str(continuation["continuation_id"]))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _index: current_attempt.restart_current_attempt(**(args | {"dispatch_handoff": handoff})),
                range(2),
            )
        )

    assert sorted(result["outcome"] for result in results) == ["committed", "replay"]
    assert len(dispatches) == 1
    events = current_attempt.journal_for(tmp_path).replay_strict()["accepted"]
    assert [event["event_kind"] for event in events].count("chain_control.current_attempt_adopted") == 1


def test_replay_rejects_forged_source_binding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args, paths = _fixture(monkeypatch, tmp_path)
    current_attempt.restart_current_attempt(**args)
    forged = replace(args["guards"], expected_source_binding={"branch": "forged", "sha": "forged"})
    with pytest.raises(current_attempt.CurrentAttemptAdoptionError) as exc:
        current_attempt.restart_current_attempt(**(args | {"guards": forged}))
    assert exc.value.code == "identity_mismatch"
    assert json.loads(paths["chain_path"].read_text())["current_plan_name"] is None


def test_interrupted_recovery_rejects_forged_source_binding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args, paths = _fixture(monkeypatch, tmp_path)

    def crash(stage: str) -> None:
        if stage == "after_plan_cas":
            raise RuntimeError("simulated crash")

    with pytest.raises(RuntimeError, match="simulated crash"):
        current_attempt.restart_current_attempt(**args, failure_injector=crash)
    forged = replace(args["guards"], expected_source_binding={"branch": "forged", "sha": "forged"})
    with pytest.raises(current_attempt.CurrentAttemptAdoptionError) as exc:
        current_attempt.restart_current_attempt(**(args | {"guards": forged}))
    assert exc.value.code == "identity_mismatch"
    assert json.loads(paths["chain_path"].read_text())["current_plan_name"] == "C2"


def test_stale_revision_and_wrong_runtime_are_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args, paths = _fixture(monkeypatch, tmp_path)
    args["guards"] = replace(args["guards"], expected_chain_revision=3)
    with pytest.raises(current_attempt.CurrentAttemptAdoptionError) as stale:
        current_attempt.restart_current_attempt(**args)
    assert stale.value.code == "identity_mismatch"
    assert json.loads(paths["chain_path"].read_text())["current_plan_name"] == "C2"

    args, paths = _fixture(monkeypatch, tmp_path / "runtime")
    args["guards"] = replace(args["guards"], expected_runtime_identity={"container": "wrong"})
    with pytest.raises(current_attempt.CurrentAttemptAdoptionError) as wrong:
        current_attempt.restart_current_attempt(**args)
    assert wrong.value.code == "identity_mismatch"
    assert json.loads(paths["chain_path"].read_text())["current_plan_name"] == "C2"


def _aborted_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[dict[str, object], dict[str, object]]:
    args, paths = _fixture(monkeypatch, tmp_path)
    chain = json.loads(paths["chain_path"].read_text())
    chain["current_plan_name"] = None
    chain_raw = _write_json(paths["chain_path"], chain)
    plan = json.loads(paths["plan_path"].read_text())
    plan["current_state"] = "aborted"
    plan["active_step"] = None
    plan_raw = _write_json(paths["plan_path"], plan)
    rows = [{"id": f"row-{index}", "state": "running", "lock_version": index + 1} for index in range(9)]
    rows_path = tmp_path / "operation-runs.json"
    rows_raw = _write_json(rows_path, {"operations": rows})
    guards = current_attempt.AbortedC2AuthorityGuards(
        expected_session_id="session-c2",
        expected_plan_name="C2",
        expected_chain_state_sha256=hashlib.sha256(chain_raw).hexdigest(),
        expected_plan_state_sha256=hashlib.sha256(plan_raw).hexdigest(),
        expected_marker_sha256=hashlib.sha256(paths["marker_path"].read_bytes()).hexdigest(),
        expected_spec_sha256=hashlib.sha256(args["spec_path"].read_bytes()).hexdigest(),
        expected_chain_revision=4,
        expected_completed_prefix=tuple(chain["completed"]),
        expected_source_binding=args["guards"].expected_source_binding,
        expected_runtime_identity=args["guards"].expected_runtime_identity,
        expected_hold=args["guards"].expected_hold,
        expected_operation_rows=tuple(rows),
        expected_historical_spec_sha256=None,
        expected_operation_rows_sha256=hashlib.sha256(rows_raw).hexdigest(),
    )
    args = {
        "spec_path": args["spec_path"],
        "project_dir": tmp_path,
        "marker_path": args["marker_path"],
        "aborted_plan_path": paths["plan_path"],
        "guards": guards,
        "expected_operation_rows_path": rows_path,
        "reason": "admit paused aborted C2 authority",
    }
    paths["rows_path"] = rows_path
    paths["rows"] = rows
    return args, paths


def test_aborted_authority_admission_preserves_history_and_replays(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args, paths = _aborted_fixture(monkeypatch, tmp_path)
    plan_before = paths["plan_path"].read_bytes()
    marker_before = paths["marker_path"].read_bytes()
    first = current_attempt.reconcile_aborted_c2_authority(**args)
    second = current_attempt.reconcile_aborted_c2_authority(**args)
    assert first["outcome"] == "committed"
    assert second["outcome"] == "replay"
    chain = json.loads(paths["chain_path"].read_text())
    assert chain["current_plan_name"] is None
    assert chain["current_milestone_index"] == 6
    assert chain["last_state"] == "paused"
    assert chain["completed"] == paths["prefix"]
    assert paths["plan_path"].read_bytes() == plan_before
    assert paths["marker_path"].read_bytes() == marker_before
    events = current_attempt.journal_for(tmp_path).replay_strict()["accepted"]
    assert [event["event_kind"] for event in events].count(current_attempt.ABORTED_ADMISSION_KIND) == 1
    assert [event["event_kind"] for event in events].count("chain_control.replay") == 1


@pytest.mark.parametrize("crash_stage", ["after_genesis", "after_intent", "after_chain_cas"])
def test_aborted_authority_admission_recovers_same_operation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, crash_stage: str
) -> None:
    args, paths = _aborted_fixture(monkeypatch, tmp_path)
    plan_before = paths["plan_path"].read_bytes()

    def crash(stage: str) -> None:
        if stage == crash_stage:
            raise RuntimeError("simulated admission crash")

    with pytest.raises(RuntimeError, match="simulated admission crash"):
        current_attempt.reconcile_aborted_c2_authority(**args, failure_injector=crash)
    recovered = current_attempt.reconcile_aborted_c2_authority(**args)
    assert recovered["outcome"] == "committed"
    assert json.loads(paths["chain_path"].read_text())["current_plan_name"] is None
    assert paths["plan_path"].read_bytes() == plan_before


def test_aborted_authority_admission_rejects_row_drift_without_journal_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args, paths = _aborted_fixture(monkeypatch, tmp_path)
    events_path = current_attempt.journal_for(tmp_path).ledger.events_path
    rows = json.loads(paths["rows_path"].read_text())
    rows["operations"][0]["lock_version"] = 999
    _write_json(paths["rows_path"], rows)
    with pytest.raises(current_attempt.CurrentAttemptAdoptionError) as exc:
        current_attempt.reconcile_aborted_c2_authority(**args)
    assert exc.value.code == "identity_mismatch"
    assert not events_path.exists()


def test_aborted_authority_admission_two_callers_commit_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args, _paths = _aborted_fixture(monkeypatch, tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: current_attempt.reconcile_aborted_c2_authority(**args), range(2)))
    assert sorted(result["outcome"] for result in results) == ["committed", "replay"]
