from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain import _apply_ladder_action
from arnold_pipelines.megaplan.chain.epic_chain import EpicChainState, save_epic_chain_state
from arnold_pipelines.megaplan.chain.operator_pause import is_paused, pause_chain, resume_chain
from arnold_pipelines.megaplan.chain.spec import ChainState, load_chain_state, load_spec, save_chain_state
from arnold_pipelines.megaplan.incident.chain_control import (
    ChainControlHold,
    ChainControlJournal,
    UnattributedStateChange,
    apply_chain_lifecycle,
    chain_id_for_spec,
    journal_for,
)
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
    AcceptanceSnapshot,
    AcceptanceTransaction,
)
from arnold_pipelines.megaplan.orchestration.completion_io import (
    commit_acceptance_transaction,
    prepare_acceptance_transaction,
    store_acceptance_snapshot,
)
from arnold_pipelines.megaplan.orchestration.evidence_contract import EvidenceRef, EvidenceStatus


def _spec(tmp_path: Path) -> Path:
    initiative = tmp_path / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    brief = initiative / "brief.md"
    brief.write_text("# brief\n")
    spec = initiative / "chain.yaml"
    spec.write_text(
        "anchors:\n  north_star: brief.md\n"
        "milestones:\n  - label: M1\n    idea: brief.md\n"
    )
    return spec


def test_unbound_bootstrap_save_still_works(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    save_chain_state(spec, ChainState(current_milestone_index=0, last_state="ready"))
    loaded = load_chain_state(spec)
    assert loaded.last_state == "ready"
    assert not (tmp_path / ".megaplan" / "incident-ledger" / "events.jsonl").exists()


def test_context_free_bound_save_fails_closed(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    save_chain_state(spec, ChainState(current_milestone_index=0, last_state="ready"))
    journal = journal_for(tmp_path)
    journal.ensure_genesis(chain_id=chain_id_for_spec(spec), actor={"id": "t", "class": "test"})
    with pytest.raises(UnattributedStateChange):
        save_chain_state(spec, ChainState(current_milestone_index=1, last_state="x"), _direct=True)
    loaded = load_chain_state(spec)
    assert loaded.last_state == "ready"


def test_bound_save_installs_committed_revision_for_repeated_saves(tmp_path: Path) -> None:
    """A bound caller can persist successive lifecycle changes without self-conflict."""
    spec = _spec(tmp_path)
    journal = journal_for(tmp_path)
    journal.ensure_genesis(chain_id=chain_id_for_spec(spec), actor={"id": "t", "class": "test"})
    state = ChainState(current_milestone_index=-1, last_state="starting")

    save_chain_state(spec, state)
    assert state.metadata["_nbf08_revision"] == 0
    state.current_milestone_index = 0
    state.last_state = "initialized"
    save_chain_state(spec, state)
    assert state.metadata["_nbf08_revision"] == 1
    state.current_plan_name = "demo-plan"
    save_chain_state(spec, state)
    assert state.metadata["_nbf08_revision"] == 2

    loaded = load_chain_state(spec)
    assert loaded.metadata["_nbf08_revision"] == 2
    projection = tmp_path / ".megaplan" / "plans" / ".chains" / "projections" / "chain-state.projection.jsonl"
    rows = [json.loads(line) for line in projection.read_text(encoding="utf-8").splitlines()]
    assert [row["payload"]["state"]["metadata"].get("_nbf08_revision") for row in rows] == [0, 1, 2]


def test_pause_resume_drive_production_door_and_journal(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    plan = tmp_path / ".megaplan" / "plans" / "demo-plan"
    plan.mkdir(parents=True)
    (plan / "state.json").write_text(
        json.dumps({"current_state": "blocked", "resume_cursor": {"phase": "execute"}, "meta": {}})
    )
    save_chain_state(spec, ChainState(current_milestone_index=0, current_plan_name="demo-plan", last_state="blocked"))
    paused = pause_chain(spec, tmp_path, reason="capacity")
    assert paused["changed"] is True
    assert is_paused(load_chain_state(spec))
    journal = ChainControlJournal(IncidentLedger(tmp_path))
    kinds = [event["event_kind"] for event in journal.replay_strict()["accepted"]]
    assert "chain_control.genesis_accepted" in kinds
    assert "chain_control.committed" in kinds
    resumed = resume_chain(spec, tmp_path)
    assert resumed["restored_plan_state"] == "blocked"
    assert not is_paused(load_chain_state(spec))


def test_parent_child_sorted_locks_and_retry_skip_failure(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    save_chain_state(spec, ChainState(current_milestone_index=0, last_state="ready"))
    retry = apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="retry",
        actor={"id": "t", "class": "test"},
        parent_chain_id="chain-parent",
        effect=lambda txn: {
            "pre_state_digest": "ready",
            "post_state_digest": "retry",
            "actual_cursor": 0,
            "locks": list(txn.chain_ids),
        },
    )
    assert retry["outcome"] == "committed"
    assert retry["effect"]["locks"][0] < retry["effect"]["locks"][-1] or len(retry["effect"]["locks"]) == 1
    skip = apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="skip",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": "retry", "post_state_digest": "skip"},
    )
    fail = apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="failure",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": "skip", "post_state_digest": "failed"},
    )
    assert skip["outcome"] == fail["outcome"] == "committed"


def test_completion_links_prepare_commit_receipts(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    plan = tmp_path / ".megaplan" / "plans" / "demo-plan"
    plan.mkdir(parents=True)
    snapshot = AcceptanceSnapshot(
        transaction_id="txn-cc-1",
        chain_run_id="run-1",
        milestone_label="M1",
        milestone_index=0,
        plan_name="demo-plan",
        source_commit_ref="abc",
        runtime_identity="test",
        evidence=(EvidenceRef(kind="green_suite", status=EvidenceStatus.satisfied, summary="ok"),),
    )
    store_acceptance_snapshot(plan, snapshot)
    tx = AcceptanceTransaction(
        transaction_id="txn-cc-1",
        snapshot_hash=snapshot.content_hash,
        accepted=True,
        mode="shadow",
        tested_commit_ref="abc",
        tested_runtime_identity="test",
    )
    prepare_acceptance_transaction(plan, tx)
    committed = commit_acceptance_transaction(plan, "txn-cc-1")
    assert committed is not None
    result = apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="completion",
        actor={"id": "t", "class": "test"},
        linked_receipts=["txn-cc-1"],
        effect=lambda _txn: {
            "pre_state_digest": "incomplete",
            "post_state_digest": "completed",
            "linked_receipts": ["txn-cc-1"],
        },
    )
    assert result["outcome"] == "committed"
    assert "txn-cc-1" in (result["result"].get("linked_receipts") or []) or result["effect"]["linked_receipts"] == ["txn-cc-1"]


def test_terminal_completed_cannot_be_appended(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        completed=[{"label": "M1", "plan": "demo-plan", "status": "done"}],
    )
    save_chain_state(spec, state)
    import arnold_pipelines.megaplan.chain as chain_mod

    with pytest.raises(ChainControlHold, match="terminal"):
        chain_mod._append_completed_with_guard(
            tmp_path,
            state,
            {"label": "M1", "plan": "demo-plan", "status": "done"},
            implementation_milestone=True,
            writer=lambda _msg: None,
            spec_path=spec,
        )


def test_epic_direct_save_fail_closed_when_bound(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    save_epic_chain_state(spec, EpicChainState())
    journal = journal_for(tmp_path)
    journal.ensure_genesis(chain_id=chain_id_for_spec(spec), actor={"id": "t", "class": "test"})
    with pytest.raises(UnattributedStateChange):
        save_epic_chain_state(spec, EpicChainState(), _direct=True)


def test_tampered_bound_ledger_cannot_become_unbound_or_direct_save(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    save_chain_state(spec, ChainState(current_milestone_index=0, last_state="ready"))
    journal = journal_for(tmp_path)
    chain_id = chain_id_for_spec(spec)
    journal.ensure_genesis(chain_id=chain_id, actor={"id": "t", "class": "test"})
    path = journal.ledger.events_path
    path.write_bytes(b"{not-json}\n" + path.read_bytes())
    with pytest.raises(ChainControlHold):
        journal.is_bound(chain_id)
    with pytest.raises(ChainControlHold):
        save_chain_state(spec, ChainState(current_milestone_index=1, last_state="x"))
    with pytest.raises(ChainControlHold):
        save_chain_state(spec, ChainState(current_milestone_index=1, last_state="x"), _direct=True)


def test_pause_resume_are_one_saga_with_real_digests(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    plan = tmp_path / ".megaplan" / "plans" / "demo-plan"
    plan.mkdir(parents=True)
    (plan / "state.json").write_text(
        json.dumps({"current_state": "blocked", "resume_cursor": {"phase": "execute"}, "meta": {}})
    )
    save_chain_state(spec, ChainState(current_milestone_index=0, current_plan_name="demo-plan", last_state="blocked"))
    paused = pause_chain(spec, tmp_path, reason="capacity")
    assert paused["changed"] is True
    journal = ChainControlJournal(IncidentLedger(tmp_path))
    accepted = journal.replay_strict()["accepted"]
    pause_committed = [
        event
        for event in accepted
        if event["event_kind"] == "chain_control.committed" and event.get("intent") == "pause"
    ]
    assert len(pause_committed) == 1
    assert len(pause_committed[0]["pre_state_digest"]) == 64
    assert len(pause_committed[0]["post_state_digest"]) == 64
    assert pause_committed[0]["pre_state_digest"] != pause_committed[0]["post_state_digest"]
    resumed = resume_chain(spec, tmp_path)
    assert resumed["restored_plan_state"] == "blocked"
    resume_committed = [
        event
        for event in journal.replay_strict()["accepted"]
        if event["event_kind"] == "chain_control.committed" and event.get("intent") == "resume"
    ]
    assert len(resume_committed) == 1
    assert len(resume_committed[0]["pre_state_digest"]) == 64
    assert len(resume_committed[0]["post_state_digest"]) == 64
    assert "_nbf08_lifecycle" not in (load_chain_state(spec).metadata or {})


def test_production_skip_retry_one_mutate(tmp_path: Path) -> None:
    spec_path = _spec(tmp_path)
    save_chain_state(spec_path, ChainState(current_milestone_index=0, last_state="ready"))
    spec = load_spec(spec_path)
    state = load_chain_state(spec_path)
    skip = _apply_ladder_action(
        "skip_milestone",
        milestone=spec.milestones[0],
        state=state,
        spec=spec,
        writer=lambda _msg: None,
        spec_path=spec_path,
        root=tmp_path,
    )
    retry = _apply_ladder_action(
        "retry_milestone",
        milestone=spec.milestones[0],
        state=state,
        spec=spec,
        writer=lambda _msg: None,
        spec_path=spec_path,
        root=tmp_path,
    )
    assert skip == "skip"
    assert retry == "retry"
    loaded = load_chain_state(spec_path)
    assert "_nbf08_lifecycle" not in (loaded.metadata or {})
    accepted = journal_for(tmp_path).replay_strict()["accepted"]
    skip_events = [event for event in accepted if event.get("intent") == "skip" and event["event_kind"] == "chain_control.committed"]
    retry_events = [event for event in accepted if event.get("intent") == "retry" and event["event_kind"] == "chain_control.committed"]
    assert len(skip_events) == 1
    assert len(retry_events) == 1
    assert len(skip_events[0]["pre_state_digest"]) == 64
    assert len(skip_events[0]["post_state_digest"]) == 64
    assert len(retry_events[0]["pre_state_digest"]) == 64
    assert len(retry_events[0]["post_state_digest"]) == 64


def test_two_epic_writes_are_distinct_operations(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    save_epic_chain_state(spec, EpicChainState())
    journal = journal_for(tmp_path)
    journal.ensure_genesis(chain_id=chain_id_for_spec(spec), actor={"id": "t", "class": "test"})
    save_epic_chain_state(spec, EpicChainState(current_epic_index=0, last_state="a"))
    save_epic_chain_state(spec, EpicChainState(current_epic_index=1, last_state="b"))
    committed = [
        event
        for event in journal.replay_strict()["accepted"]
        if event["event_kind"] == "chain_control.committed" and event.get("intent") == "save_epic_chain_state"
    ]
    assert len(committed) == 2
    assert committed[0]["operation_id"] != committed[1]["operation_id"]
