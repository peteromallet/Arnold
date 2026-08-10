from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from arnold_pipelines.megaplan import chain as chain_module
from arnold_pipelines.megaplan.chain.ci_hook import (
    HINGE_GATE_GREEN_STAMP,
    GateOutcome,
    run_chain_ci,
)
from arnold_pipelines.megaplan.chain.epic_chain import (
    load_epic_chain_state,
    run_epic_chain,
)
from arnold_pipelines.megaplan.chain.execution_binding import (
    active_execution_identity,
    bind_execution_identity,
    rebind_execution_identity,
)
from arnold_pipelines.megaplan.chain.git_ops import (
    _capture_pr_merged_evidence,
    _capture_pr_ready_evidence,
)
import arnold_pipelines.megaplan.chain.git_ops as git_ops_module
from arnold_pipelines.megaplan.chain.hinge_gate import (
    OracleOutcome,
    run_hinge_gate,
    run_with_escalation,
)
from arnold_pipelines.megaplan.chain.spec import ChainState, save_chain_state


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_chain(root: Path, labels: tuple[str, ...]) -> Path:
    initiative = root / ".megaplan" / "initiatives" / "demo"
    briefs = initiative / "briefs"
    briefs.mkdir(parents=True, exist_ok=True)
    (initiative / "NORTHSTAR.md").write_text("# Durable destination\n", encoding="utf-8")
    milestones = []
    for label in labels:
        brief = briefs / f"{label}.md"
        brief.write_text(f"# {label}\n", encoding="utf-8")
        milestones.append(
            {
                "label": label,
                "idea": f".megaplan/initiatives/demo/briefs/{label}.md",
            }
        )
    payload = {
        "anchors": {"north_star": "NORTHSTAR.md"},
        "milestones": milestones,
        "driver": {
            "execution_binding": "required",
            "initiative_path": ".megaplan/initiatives/demo",
            "intended_initiative_revision": "UNSET_REQUIRED_BEFORE_LAUNCH",
            "require_editable_runtime_match": False,
        },
    }
    spec_path = initiative / "chain.yaml"
    spec_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return spec_path


def _pinned_chain(tmp_path: Path, labels: tuple[str, ...]) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "tests@example.com")
    _git(tmp_path, "config", "user.name", "Tests")
    spec_path = _write_chain(tmp_path, labels)
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "initiative revision")
    revision = _git(tmp_path, "rev-parse", "HEAD")
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["driver"]["intended_initiative_revision"] = revision
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return spec_path


def _bound_state(spec_path: Path) -> ChainState:
    state = ChainState()
    report = bind_execution_identity(spec_path, state)
    assert report["status"] == "match"
    save_chain_state(spec_path, state)
    return state


def _replace_and_repin(spec_path: Path, labels: tuple[str, ...]) -> None:
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    raw["milestones"] = []
    for label in labels:
        brief = spec_path.parent / "briefs" / f"{label}.md"
        brief.write_text(f"# {label}\n", encoding="utf-8")
        raw["milestones"].append(
            {
                "label": label,
                "idea": f".megaplan/initiatives/demo/briefs/{label}.md",
            }
        )
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    root = spec_path.parents[3]
    _git(root, "add", ".")
    _git(root, "commit", "-m", "replace initiative revision")
    raw["driver"]["intended_initiative_revision"] = _git(root, "rev-parse", "HEAD")
    spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _write_child_chain_spec(root: Path, slug: str) -> Path:
    north_star = root / ".megaplan" / "briefs" / slug / "NORTHSTAR.md"
    idea = root / ".megaplan" / "briefs" / slug / "m1.md"
    spec_path = root / ".megaplan" / "briefs" / slug / "chain.yaml"
    _write_text(north_star, "# North Star\n")
    _write_text(idea, "# M1\n")
    _write_text(
        spec_path,
        "base_branch: native-python-working-tree\n"
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        "    idea: m1.md\n"
        "    branch: test/m1\n",
    )
    return spec_path


def _write_parent_spec(root: Path, *, child_spec: Path) -> Path:
    parent_dir = root / ".megaplan" / "briefs" / "parent"
    north_star = root / "briefs" / "parent" / "NORTHSTAR.md"
    _write_text(north_star, "# Parent North Star\n")
    spec_path = parent_dir / "epic-chain.yaml"
    _write_text(
        spec_path,
        "\n".join(
            [
                "base_branch: native-python-working-tree",
                "anchors:",
                "  north_star: ../../../briefs/parent/NORTHSTAR.md",
                "epics:",
                "  - id: child-epic",
                f"    spec: {child_spec}",
                "on_failure:",
                "  abort: stop_epic_chain",
            ]
        )
        + "\n",
    )
    return spec_path


def test_guarded_rebind_records_wbc_transition_evidence(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path, ("m5", "m6"))
    state = _bound_state(spec_path)
    state.current_milestone_index = 0
    state.current_plan_name = "m5-plan"
    previous_bundle = state.metadata["execution_binding"]["launched_identity"][
        "bundle_sha256"
    ]

    _replace_and_repin(spec_path, ("m5", "m5a", "m6"))
    active_bundle = active_execution_identity(spec_path)["bundle_sha256"]
    rebind_execution_identity(
        spec_path,
        state,
        expected_previous_bundle_sha256=previous_bundle,
        expected_active_bundle_sha256=active_bundle,
        expected_current_milestone="m5",
        expected_current_plan="m5-plan",
        expected_next_milestone="m5a",
        reason="insert successor",
    )

    evidence = state.metadata["execution_binding"]["wbc_transition_evidence"][
        "execution_rebind:m5:m5a"
    ]
    assert evidence["transition"] == "execution_rebind"
    assert evidence["subject"] == "m5->m5a"


def test_append_completed_with_guard_records_chain_wbc_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec_path = _pinned_chain(tmp_path, ("m1",))
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True)
    state = ChainState(completion_contract_mode="shadow")
    record = {"label": "m1", "plan": "plan-m1", "status": "done"}

    monkeypatch.setattr(
        chain_module,
        "_chain_completion_guard",
        lambda *_args, **_kwargs: (True, "ok"),
    )

    advanced, _reason = chain_module._append_completed_with_guard(
        tmp_path,
        state,
        record,
        implementation_milestone=True,
        writer=lambda _message: None,
        spec_path=spec_path,
        plan_dir=plan_dir,
        milestone_index=0,
    )

    assert advanced is True
    evidence = state.metadata["wbc_transition_evidence"]["chain_advance:m1:0"]
    assert evidence["transition"] == "chain_milestone_advance"


def test_epic_chain_records_wbc_transition_evidence_for_completion(tmp_path: Path) -> None:
    child_spec = _write_child_chain_spec(tmp_path, "child")
    save_chain_state(
        child_spec,
        ChainState(
            current_milestone_index=1,
            last_state="done",
            completed=[{"label": "m1", "plan": "plan-m1", "status": "done"}],
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                }
            },
        ),
    )
    parent_spec = _write_parent_spec(tmp_path, child_spec=child_spec)

    payload = run_epic_chain(tmp_path, parent_spec, writer=lambda _msg: None, one=True)

    assert payload["status"] == "paused"
    parent_state = load_epic_chain_state(parent_spec)
    evidence = parent_state.metadata["wbc_transition_evidence"]["epic_complete:child-epic:0"]
    assert evidence["transition"] == "epic_child_complete"


def test_capture_pr_transition_evidence_preserves_validation_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validation = {"schema": "arnold.megaplan.chain_wbc_transition_evidence.v1", "rules": []}

    monkeypatch.setattr(
        git_ops_module,
        "_capture_pr_head_evidence",
        lambda *_args, **_kwargs: ("a" * 40, "b" * 40),
    )
    monkeypatch.setattr(
        git_ops_module,
        "_capture_merge_commit_evidence",
        lambda *_args, **_kwargs: "c" * 40,
    )
    monkeypatch.setattr(
        git_ops_module,
        "_check_merge_tip_containment",
        lambda *_args, **_kwargs: (True, True, "ok"),
    )

    ready = _capture_pr_ready_evidence(
        tmp_path,
        17,
        writer=lambda _msg: None,
        validation_evidence=validation,
    )
    merged = _capture_pr_merged_evidence(
        tmp_path,
        17,
        writer=lambda _msg: None,
        validation_evidence=validation,
    )

    assert ready.validation_evidence == validation
    assert merged.validation_evidence == validation


def test_run_chain_ci_returns_validated_green_label() -> None:
    result = run_chain_ci(
        gates=(
            ("a", lambda: GateOutcome(name="a", ok=True, detail="ok")),
            ("b", lambda: GateOutcome(name="b", ok=True, detail="ok")),
        )
    )

    assert result.validation_evidence is not None
    assert result.commit_label() == HINGE_GATE_GREEN_STAMP


def test_hinge_gate_results_and_escalation_carry_validation(tmp_path: Path) -> None:
    green = run_hinge_gate(
        oracles=(("green", lambda: OracleOutcome(name="green", ok=True, detail="ok")),)
    )
    assert green.validation_evidence is not None
    assert green.r1_flip_allowed is True

    red = run_with_escalation(
        run_gate=lambda: run_hinge_gate(
            oracles=(("red", lambda: OracleOutcome(name="red", ok=False, detail="nope")),)
        ),
        ticket_dir=tmp_path / "tickets",
        max_retries=0,
    )
    assert red.passed is False
    assert red.validation_evidence is not None
    assert red.ticket_path is not None and red.ticket_path.exists()
