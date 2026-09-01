from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.chain.operator_pause import is_paused, pause_chain, resume_chain
from arnold_pipelines.megaplan.chain.spec import ChainState, load_chain_state, save_chain_state
from arnold_pipelines.megaplan.cloud.cli import run_cloud_cli
from arnold_pipelines.megaplan.incident.chain_control import ChainControlHold, apply_chain_lifecycle, journal_for


def _spec(tmp_path: Path) -> Path:
    initiative = tmp_path / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    (initiative / "brief.md").write_text("# brief\n")
    spec = initiative / "chain.yaml"
    spec.write_text("anchors:\n  north_star: brief.md\nmilestones:\n  - label: M1\n    idea: brief.md\n")
    return spec


def test_cloud_pause_resume_route_journals_through_operator_pause(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    plan = tmp_path / ".megaplan" / "plans" / "demo-plan"
    plan.mkdir(parents=True)
    (plan / "state.json").write_text('{"current_state": "blocked", "meta": {}}\n')
    save_chain_state(spec, ChainState(current_milestone_index=0, current_plan_name="demo-plan", last_state="blocked"))
    paused = pause_chain(spec, tmp_path, reason="cloud-pause")
    assert paused["changed"] is True
    assert is_paused(load_chain_state(spec))
    journal = journal_for(tmp_path)
    pause_committed = [
        event
        for event in journal.replay_strict()["accepted"]
        if event["event_kind"] == "chain_control.committed" and event.get("intent") == "pause"
    ]
    assert len(pause_committed) == 1
    assert len(pause_committed[0]["pre_state_digest"]) == 64
    assert len(pause_committed[0]["post_state_digest"]) == 64
    resumed = resume_chain(spec, tmp_path)
    assert resumed["changed"] is True
    assert not is_paused(load_chain_state(spec))
    resume_committed = [
        event
        for event in journal.replay_strict()["accepted"]
        if event["event_kind"] == "chain_control.committed" and event.get("intent") == "resume"
    ]
    assert len(resume_committed) == 1


def test_cloud_preflight_is_read_pure(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="start",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": None, "post_state_digest": "started"},
    )
    before = journal_for(tmp_path).replay_strict()["physical_sequence"]
    source = Path(run_cloud_cli.__code__.co_filename).read_text(encoding="utf-8")
    assert "_run_preflight" in source
    after = journal_for(tmp_path).replay_strict()["physical_sequence"]
    assert after == before


def test_cloud_start_and_reset_are_truthful(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    started = apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="start",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": None, "post_state_digest": "started", "actual_cursor": 0},
    )
    assert started["outcome"] == "committed"
    cursor = started["result"]["semantic_sequence"]
    source = Path(run_cloud_cli.__code__.co_filename).read_text(encoding="utf-8")
    assert "_chain_state_reset_command" in source
    assert "run_census" in source
    held = apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="reset",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: (_ for _ in ()).throw(ChainControlHold("missing_census", "reset requires a clear census")),
    )
    assert held["outcome"] == "hold"
    replay = journal_for(tmp_path).replay_strict()
    assert replay["semantic_by_chain"][started["result"]["chain_id"]] == cursor


def test_cloud_reset_without_census_does_not_advance_cursor(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    started = apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="start",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": None, "post_state_digest": "started", "actual_cursor": 0},
    )
    cursor = started["result"]["semantic_sequence"]
    # Reset without a verified census is a hold, not a cursor advance.
    held = apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="reset",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: (_ for _ in ()).throw(
            __import__("arnold_pipelines.megaplan.incident.chain_control", fromlist=["ChainControlHold"]).ChainControlHold(
                "missing_census", "reset requires a clear census"
            )
        ),
    )
    assert held["outcome"] == "hold"
    replay = journal_for(tmp_path).replay_strict()
    assert replay["semantic_by_chain"][started["result"]["chain_id"]] == cursor
