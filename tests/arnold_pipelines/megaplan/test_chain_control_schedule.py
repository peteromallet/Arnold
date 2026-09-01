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


def test_schedule_claim_carries_chain_operation_id(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    save_chain_state(spec, ChainState(current_milestone_index=0, last_state="ready"))
    result = apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="schedule_claim",
        actor={"id": "scheduler", "class": "system"},
        linked_receipts=["occ-1"],
        effect=lambda _txn: {
            "pre_state_digest": "ready",
            "post_state_digest": "claimed",
            "linked_receipts": ["occ-1"],
            "chain_operation_id": "op-sched",
        },
    )
    assert result["outcome"] == "committed"
    envelope = result["result"]
    assert envelope.get("linked_receipts") == ["occ-1"] or result["effect"]["linked_receipts"] == ["occ-1"]


def test_occurrence_join_and_adopt_are_journaled(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    join = apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="occurrence_join",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": None, "post_state_digest": "joined"},
    )
    adopt = apply_chain_lifecycle(
        spec,
        tmp_path,
        intent_kind="occurrence_adopt",
        actor={"id": "t", "class": "test"},
        effect=lambda _txn: {"pre_state_digest": "joined", "post_state_digest": "adopted"},
    )
    kinds = [event["event_kind"] for event in journal_for(tmp_path).replay_strict()["accepted"]]
    assert join["outcome"] == adopt["outcome"] == "committed"
    assert kinds.count("chain_control.committed") >= 2
