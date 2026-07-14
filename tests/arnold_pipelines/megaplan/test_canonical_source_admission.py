from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain.execution_binding import bind_execution_identity
from arnold_pipelines.megaplan.chain.source_admission import (
    admit_milestone_source,
    require_milestone_source_update,
)
from arnold_pipelines.megaplan.chain.spec import ChainState, load_spec, save_chain_state
from arnold_pipelines.megaplan.planning.source_binding import (
    SOURCE_EVIDENCE_FILE,
    assert_canonical_source_current,
    capture_canonical_source_binding,
    reconcile_canonical_source_for_replan,
)
from arnold_pipelines.megaplan.types import CliError

from .test_chain_execution_binding import _pinned_chain


def _plan_state(root: Path, source: Path) -> tuple[Path, dict]:
    plan_dir = root / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    state = {
        "name": "demo",
        "idea": source.read_text(encoding="utf-8"),
        "idea_snapshot_path": "idea_snapshot.md",
        "current_state": "finalized",
        "iteration": 1,
        "config": {"project_dir": str(root)},
        "meta": {},
    }
    (plan_dir / "idea_snapshot.md").write_text(state["idea"], encoding="utf-8")
    capture_canonical_source_binding(state, source_path=source, project_dir=root)
    return plan_dir, state


def test_unchanged_binding_admits_and_frontmatter_only_edit_is_irrelevant(tmp_path: Path) -> None:
    source = tmp_path / "brief.md"
    source.write_text("---\ntitle: Before\n---\n\n# Goal\n\n- Must hold.\n", encoding="utf-8")
    plan_dir, state = _plan_state(tmp_path, source)

    source.write_text("---\ntitle: After\nowner: docs\n---\n\n# Goal  \n\n- Must hold.\n", encoding="utf-8")
    report = assert_canonical_source_current(plan_dir, state, operation="execute")

    assert report["status"] == "match"
    assert json.loads((plan_dir / SOURCE_EVIDENCE_FILE).read_text())["outcome"] == "admitted"


def test_changed_load_bearing_criteria_blocks_before_execution_with_truthful_evidence(tmp_path: Path) -> None:
    source = tmp_path / "brief.md"
    source.write_text("# Criteria\n\n- Original invariant.\n", encoding="utf-8")
    plan_dir, state = _plan_state(tmp_path, source)
    old_sha = state["meta"]["canonical_source_binding"]["bound"]["semantic_sha256"]
    source.write_text("# Criteria\n\n- Updated load-bearing invariant.\n", encoding="utf-8")

    with pytest.raises(CliError, match="canonical source binding is changed"):
        assert_canonical_source_current(plan_dir, state, operation="execute")

    evidence = json.loads((plan_dir / SOURCE_EVIDENCE_FILE).read_text())
    assert evidence["outcome"] == "blocked"
    assert evidence["bound"]["semantic_sha256"] == old_sha
    assert evidence["current"]["semantic_sha256"] != old_sha


def test_replan_reconciliation_produces_new_binding_then_admits(tmp_path: Path) -> None:
    source = tmp_path / "brief.md"
    source.write_text("# Criteria\n\n- Old.\n", encoding="utf-8")
    plan_dir, state = _plan_state(tmp_path, source)
    source.write_text("# Criteria\n\n- New.\n", encoding="utf-8")

    reconciled = reconcile_canonical_source_for_replan(plan_dir, state, reason="criteria changed")
    admitted = assert_canonical_source_current(plan_dir, state, operation="execute after finalize")

    assert reconciled is not None and reconciled["status"] == "match"
    assert admitted["status"] == "match"
    assert state["idea"] == "# Criteria\n\n- New."


def test_missing_current_source_failure_evidence_does_not_claim_a_hash(tmp_path: Path) -> None:
    source = tmp_path / "brief.md"
    source.write_text("# Criteria\n", encoding="utf-8")
    plan_dir, state = _plan_state(tmp_path, source)
    source.unlink()

    with pytest.raises(CliError, match="canonical source binding is changed"):
        assert_canonical_source_current(plan_dir, state, operation="execute")

    evidence = json.loads((plan_dir / SOURCE_EVIDENCE_FILE).read_text())
    assert evidence["outcome"] == "blocked"
    assert evidence["current"]["exists"] is False
    assert evidence["current"]["semantic_sha256"] == ""
    assert evidence["current"]["errors"] == ["canonical_source_missing"]


def test_active_chain_future_stale_milestone_cannot_enter_and_then_reconciles(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path)
    spec = load_spec(spec_path)
    state = ChainState()
    bind_execution_identity(spec_path, state)
    state.current_milestone_index = 0
    state.current_plan_name = "c1-plan"
    save_chain_state(spec_path, state)

    authoritative = tmp_path / "authoritative-c3.md"
    authoritative.write_text("# c3\n\n- New attention-overlay invariant.\n", encoding="utf-8")
    requirement = require_milestone_source_update(
        spec_path=spec_path,
        state=state,
        spec=spec,
        milestone_label="c3",
        authoritative_source=authoritative,
        reason="canonical criteria changed",
    )
    save_chain_state(spec_path, state)

    # The active c1 plan is untouched. When the cursor later reaches c3, the
    # old c3 source is denied before _init_plan can materialize it.
    state.current_milestone_index = 2
    state.current_plan_name = None

    with pytest.raises(CliError, match="admission refused before materialization"):
        admit_milestone_source(
            root=tmp_path,
            spec_path=spec_path,
            spec=spec,
            state=state,
            milestone=spec.milestones[2],
            milestone_index=2,
        )
    assert state.metadata["canonical_source_reconciliations"][-1]["outcome"] == "blocked"
    assert requirement["expected"]["semantic_sha256"]

    installed = tmp_path / spec.milestones[2].idea
    installed.write_text(authoritative.read_text(encoding="utf-8"), encoding="utf-8")
    event = admit_milestone_source(
        root=tmp_path,
        spec_path=spec_path,
        spec=spec,
        state=state,
        milestone=spec.milestones[2],
        milestone_index=2,
    )
    assert event["outcome"] == "reconciled"
    assert requirement["status"] == "reconciled"
    assert event["current_identity"]["semantic_sha256"] == requirement["expected"]["semantic_sha256"]
