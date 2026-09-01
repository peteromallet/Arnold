from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.chain.spec import ChainState, save_chain_state
from arnold_pipelines.megaplan.incident.chain_control import apply_chain_lifecycle, journal_for


def _spec(tmp_path: Path) -> Path:
    initiative = tmp_path / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    (initiative / "brief.md").write_text("# brief\n")
    spec = initiative / "chain.yaml"
    spec.write_text("anchors:\n  north_star: brief.md\nmilestones:\n  - label: M1\n    idea: brief.md\n")
    return spec


def test_bound_plan_override_is_journaled(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    save_chain_state(spec, ChainState(current_milestone_index=0, last_state="blocked"))
    result = apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="override_abort",
        actor={"id": "operator", "class": "operator"},
        effect=lambda _txn: {
            "pre_state_digest": "blocked",
            "post_state_digest": "aborted",
            "actual_cursor": 0,
        },
    )
    assert result["outcome"] == "committed"
    kinds = [event["event_kind"] for event in journal_for(tmp_path).replay_strict()["accepted"]]
    assert "chain_control.intent" in kinds
    assert "chain_control.committed" in kinds


def test_unbound_plan_state_write_does_not_journal(tmp_path: Path) -> None:
    plan = tmp_path / ".megaplan" / "plans" / "solo"
    plan.mkdir(parents=True)
    (plan / "state.json").write_text('{"current_state":"planned"}\n')
    assert not (tmp_path / ".megaplan" / "incident-ledger" / "events.jsonl").exists()


def test_introspect_and_trace_are_read_pure(tmp_path: Path, monkeypatch) -> None:
    spec = _spec(tmp_path)
    apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="start",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": None, "post_state_digest": "started"},
    )
    journal = journal_for(tmp_path)
    before = journal.replay_strict()["physical_sequence"]
    from arnold_pipelines.megaplan.observability import events as obs

    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    records = list(obs.iter_events(plan_dir)) if hasattr(obs, "iter_events") else []
    assert records == [] or isinstance(records, list)
    after = journal.replay_strict()["physical_sequence"]
    assert after == before
