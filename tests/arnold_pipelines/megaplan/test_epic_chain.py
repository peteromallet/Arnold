from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

import arnold_pipelines.megaplan.chain as chain_cli
from arnold_pipelines.megaplan.chain.epic_chain import (
    _state_path_for,
    load_epic_chain_spec,
    load_epic_chain_state,
    run_epic_chain,
    save_epic_chain_state,
)
from arnold_pipelines.megaplan.chain.spec import (
    ChainState,
    _state_path_for as _chain_state_path_for,
    load_chain_state,
    save_chain_state,
)
from arnold_pipelines.megaplan.runtime.process import megaplan_engine_root


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _write_plan_state(root: Path, plan_name: str, current_state: str) -> None:
    plan_state = root / ".megaplan" / "plans" / plan_name / "state.json"
    _write_text(
        plan_state,
        json.dumps({"name": plan_name, "current_state": current_state}) + "\n",
    )


def test_chain_start_cli_treats_awaiting_pr_merge_as_success(
    tmp_path: Path, monkeypatch
) -> None:
    spec_path = tmp_path / "chain.yaml"
    _write_text(tmp_path / "NORTHSTAR.md", "# North Star\n")
    _write_text(
        spec_path,
        "base_branch: main\nanchors:\n  north_star: NORTHSTAR.md\nmilestones: []\n",
    )

    def fake_run_chain(*args, **kwargs):
        return {"status": "awaiting_pr_merge", "reason": "PR #42 is open"}

    monkeypatch.setattr(chain_cli, "run_chain", fake_run_chain)

    rc = chain_cli.run_chain_cli(
        tmp_path,
        Namespace(
            chain_action="start",
            spec=str(spec_path),
            project_dir=str(tmp_path),
            no_git_refresh=False,
            no_push=False,
            one=False,
            fresh=False,
            require_anchor=None,
            missing_anchor_ack=None,
        )
    )

    assert rc == 0


def _write_parent_spec(
    root: Path,
    *,
    child_spec: Path,
    observe_spec: Path | None = None,
    second_child_spec: Path | None = None,
    artifact_path: str | None = None,
) -> Path:
    parent_dir = root / ".megaplan" / "briefs" / "native-python-pipelines-completion"
    north_star = root / "briefs" / "native-python-pipelines-completion" / "NORTHSTAR.md"
    _write_text(north_star, "# Parent North Star\n")
    lines = [
        "base_branch: native-python-working-tree",
        "anchors:",
        "  north_star: ../../../briefs/native-python-pipelines-completion/NORTHSTAR.md",
        "epics:",
        "  - id: python-shaped-workflow-authoring",
        f"    spec: {child_spec}",
    ]
    if observe_spec is not None:
        lines.append(f"    observe_spec: {observe_spec}")
    if second_child_spec is not None:
        lines.extend(
            [
                "  - id: native-python-pipelines-completion",
                f"    spec: {second_child_spec}",
                "    handoff_from_previous:",
                "      require_merged_base: true",
            ]
        )
        if artifact_path is not None:
            lines.extend(
                [
                    "      artifacts:",
                    f"        - path: {artifact_path}",
                    "          check: exists",
                ]
            )
    lines.extend(["on_failure:", "  abort: stop_epic_chain"])
    spec_path = parent_dir / "epic-chain.yaml"
    _write_text(spec_path, "\n".join(lines) + "\n")
    return spec_path


def test_epic_chain_spec_and_state_round_trip(tmp_path: Path) -> None:
    child_spec = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    spec_path = _write_parent_spec(tmp_path, child_spec=child_spec)

    spec = load_epic_chain_spec(spec_path)
    assert spec.base_branch == "native-python-working-tree"
    assert spec.epics[0].id == "python-shaped-workflow-authoring"

    state = load_epic_chain_state(spec_path)
    assert state.current_epic_index == -1
    state.current_epic_index = 0
    state.current_epic_id = "python-shaped-workflow-authoring"
    save_epic_chain_state(spec_path, state)

    state_path = _state_path_for(spec_path)
    assert ".epic_chains" in str(state_path)
    assert load_epic_chain_state(spec_path).current_epic_id == "python-shaped-workflow-authoring"


def test_epic_chain_waits_for_live_child_observe_spec_without_relaunch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    live_root = tmp_path / "live"
    child_spec = _write_child_chain_spec(
        source_root, "python-shaped-workflow-authoring"
    )
    live_child_spec = _write_child_chain_spec(
        live_root, "python-shaped-workflow-authoring"
    )
    _write_plan_state(live_root, "m8-generated-assets", "done")
    save_chain_state(
        live_child_spec,
        ChainState(
            current_milestone_index=0,
            current_plan_name="m8-generated-assets",
            last_state="done",
            pr_number=128,
            pr_state="open",
            metadata={
                "execution_environment": {
                    "project_root": str(live_root),
                    "engine_root": str(megaplan_engine_root()),
                }
            },
        ),
    )
    parent_spec = _write_parent_spec(
        source_root,
        child_spec=child_spec,
        observe_spec=live_child_spec,
    )
    _set_preflight_runtime(tmp_path, monkeypatch)

    calls: list[str] = []

    def _start_child(*_args, **_kwargs) -> subprocess.CompletedProcess[str]:
        calls.append("start")
        return subprocess.CompletedProcess([], 0, "", "")

    payload = run_epic_chain(
        source_root,
        parent_spec,
        writer=lambda _msg: None,
        start_child=_start_child,
    )

    assert payload["status"] == "awaiting_pr_merge"
    assert payload["active_child"]["observed_spec_path"] == str(live_child_spec.resolve())
    assert calls == []


def test_epic_chain_advances_completed_child_and_honors_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child_a = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    child_b = _write_child_chain_spec(tmp_path, "native-python-pipelines-completion")
    artifact = tmp_path / "docs" / "arnold" / "python-shaped-authoring-contract.md"
    _write_text(artifact, "contract\n")
    engine_root = _set_preflight_runtime(tmp_path, monkeypatch)
    save_chain_state(
        child_a,
        ChainState(
            current_milestone_index=1,
            last_state="done",
            pr_number=128,
            pr_state="merged",
            completed=[{"label": "m1", "plan": "plan-m1", "status": "done"}],
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                    "engine_root": str(engine_root),
                }
            },
        ),
    )
    # The next child (never launched under --one) must still pass the
    # runtime-binding preflight when the loop observes it.
    save_chain_state(
        child_b,
        ChainState(
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                    "engine_root": str(engine_root),
                }
            }
        ),
    )
    parent_spec = _write_parent_spec(
        tmp_path,
        child_spec=child_a,
        second_child_spec=child_b,
        artifact_path="docs/arnold/python-shaped-authoring-contract.md",
    )

    payload = run_epic_chain(
        tmp_path,
        parent_spec,
        writer=lambda _msg: None,
        one=True,
        start_child=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("should not launch next child under --one")
        ),
    )

    assert payload["status"] == "paused"
    state = load_epic_chain_state(parent_spec)
    assert state.current_epic_index == 1
    assert state.completed[0]["id"] == "python-shaped-workflow-authoring"
    assert state.completed[0]["handoff_verified"]["artifacts"] == [
        {
            "path": str(artifact.resolve()),
            "check": "exists",
        }
    ]


def test_epic_chain_launches_not_started_child_via_chain_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child_spec = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    parent_spec = _write_parent_spec(tmp_path, child_spec=child_spec)
    plan_name = "m1-plan"
    engine_root = _set_preflight_runtime(tmp_path, monkeypatch)
    # The outer-path preflight now runs BEFORE the first observe, so the
    # not-started child must already carry a valid recorded engine root.
    save_chain_state(
        child_spec,
        ChainState(
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                    "engine_root": str(engine_root),
                }
            }
        ),
    )

    def _start_child(child, *, parent_spec_path: Path) -> subprocess.CompletedProcess[str]:
        assert child.id == "python-shaped-workflow-authoring"
        _write_plan_state(tmp_path, plan_name, "done")
        save_chain_state(
            child_spec,
            ChainState(
                current_milestone_index=1,
                current_plan_name=None,
                last_state="done",
                pr_number=42,
                pr_state="merged",
                completed=[{"label": "m1", "plan": plan_name, "status": "done"}],
                metadata={
                    "execution_environment": {
                        "project_root": str(tmp_path),
                        "engine_root": str(engine_root),
                    }
                },
            ),
        )
        return subprocess.CompletedProcess(
            [
                "python3",
                "-P",
                "-m",
                "arnold_pipelines.megaplan",
                "chain",
                "start",
            ],
            0,
            "",
            "",
        )

    payload = run_epic_chain(
        tmp_path,
        parent_spec,
        writer=lambda _msg: None,
        start_child=_start_child,
    )

    assert payload["status"] == "done"
    state = load_epic_chain_state(parent_spec)
    assert state.completed[0]["status"] == "done"


def test_chain_state_uses_project_root_path_for_symlinked_chain_spec(tmp_path: Path) -> None:
    spec_path = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    root_alias = tmp_path / "chain.yaml"
    root_alias.symlink_to(spec_path.relative_to(tmp_path))

    save_chain_state(
        root_alias,
        ChainState(
            current_milestone_index=0,
            current_plan_name="m1-plan",
            last_state="awaiting_pr_merge",
        ),
    )

    canonical_path = _chain_state_path_for(root_alias)
    nested_path = spec_path.parent / ".megaplan" / "plans" / ".chains" / canonical_path.name

    assert canonical_path.parent == tmp_path / ".megaplan" / "plans" / ".chains"
    assert canonical_path.exists()
    assert not nested_path.exists()
    assert load_chain_state(spec_path).current_plan_name == "m1-plan"


def test_chain_state_load_prefers_more_advanced_nested_symlink_state(tmp_path: Path) -> None:
    spec_path = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    root_alias = tmp_path / "chain.yaml"
    root_alias.symlink_to(spec_path.relative_to(tmp_path))

    save_chain_state(root_alias, ChainState())

    nested_state_path = (
        spec_path.parent
        / ".megaplan"
        / "plans"
        / ".chains"
        / f"{spec_path.stem}-{hashlib.sha1(str(spec_path.resolve()).encode('utf-8')).hexdigest()[:12]}.json"
    )
    nested_state_path.parent.mkdir(parents=True, exist_ok=True)
    nested_state_path.write_text(
        json.dumps(
            ChainState(
                current_milestone_index=0,
                current_plan_name="m1-plan",
                last_state="awaiting_pr_merge",
            ).to_dict(),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = load_chain_state(spec_path)

    assert loaded.current_plan_name == "m1-plan"
    assert load_chain_state(root_alias).current_plan_name == "m1-plan"


def test_epic_chain_treats_already_running_launch_as_live_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child_spec = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    parent_spec = _write_parent_spec(tmp_path, child_spec=child_spec)
    engine_root = _set_preflight_runtime(tmp_path, monkeypatch)
    save_chain_state(
        child_spec,
        ChainState(
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                    "engine_root": str(engine_root),
                }
            }
        ),
    )

    def _start_child(*_args, **_kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            ["python3", "-P", "-m", "arnold_pipelines.megaplan", "chain", "start"],
            0,
            "megaplan-chain session already running for this epic-chain\n",
            "",
        )

    payload = run_epic_chain(
        tmp_path,
        parent_spec,
        writer=lambda _msg: None,
        start_child=_start_child,
    )

    assert payload["status"] == "running"
    assert payload["reason"] == "child epic python-shaped-workflow-authoring already running"
    assert payload["active_child"]["effective_status"] == "not_started"
    state = load_epic_chain_state(parent_spec)
    assert state.last_state == "running"


def test_epic_chain_authority_drift_captured_when_legacy_complete_but_views_disagree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Child-run aggregation captures drift when legacy says complete but
    authority views (execution batches) say otherwise.

    This proves that child-run aggregation avoids raw plan-state shortcuts
    as authority — the legacy ``completed_prefix >= len(milestones)`` check
    is still the effective decision (fail-safe), but authority drift is
    observable in ``ObservedChildEpic.authority_drift`` and inside the
    classification metadata.
    """
    child_spec = _write_child_chain_spec(tmp_path, "test-child")
    parent_spec = _write_parent_spec(tmp_path, child_spec=child_spec)

    # Set up chain state: all milestones "completed" but the plan directory
    # has no execution batch artifacts, so authority views will disagree.
    # NOTE: current_milestone_index must be 0 (not past completed milestones)
    # to prevent _normalize_stale_current_plan_reference from clearing
    # current_plan_name on load. The effective_status is still "complete"
    # because completed_prefix (1) >= len(milestones) (1).
    plan_name = "test-plan"
    _write_plan_state(tmp_path, plan_name, "done")
    engine_root = _set_preflight_runtime(tmp_path, monkeypatch)
    save_chain_state(
        child_spec,
        ChainState(
            current_milestone_index=0,
            current_plan_name=plan_name,
            last_state="done",
            completed=[{"label": "m1", "plan": plan_name, "status": "done"}],
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                    "engine_root": str(engine_root),
                }
            },
        ),
    )

    from arnold_pipelines.megaplan.chain.epic_chain import _observe_child_epic, EpicSpec

    epic = EpicSpec(id="test-child", spec=str(child_spec))
    child = _observe_child_epic(epic, parent_spec_path=parent_spec)

    # Legacy classification says complete (all milestones done).
    assert child.effective_status == "complete"
    assert child.reason == "all_child_milestones_completed"

    # Authority drift should be captured because no execution batches exist.
    assert child.authority_drift is not None
    assert child.authority_drift["kind"] == "legacy_complete_authority_disagrees"
    assert child.authority_drift["legacy_effective_status"] == "complete"
    assert child.authority_drift["authority_verdict"] is False
    assert "no execution_batch_" in child.authority_drift["authority_reason"]

    # Classification metadata should also carry the drift annotation.
    metadata = child.classification.get("metadata", {})
    assert isinstance(metadata, dict)
    assert "epic_chain_authority_drift" in metadata
    drift = metadata["epic_chain_authority_drift"]
    assert drift["kind"] == "legacy_complete_authority_disagrees"


def test_epic_chain_no_authority_drift_when_plan_dir_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the child has no project_root or no current_plan_name, the
    authority drift check is skipped cleanly — the child is still classified
    correctly and there are no false-positive drifts."""
    child_spec = _write_child_chain_spec(tmp_path, "test-child")
    parent_spec = _write_parent_spec(tmp_path, child_spec=child_spec)

    # Chain state with completed milestones but NO current_plan_name and
    # NO execution_environment.project_root (so project_root is None) — the
    # runtime-binding preflight still needs a recorded engine_root + manifest.
    engine_root = _set_preflight_runtime(tmp_path, monkeypatch)
    save_chain_state(
        child_spec,
        ChainState(
            current_milestone_index=1,
            last_state="done",
            completed=[{"label": "m1", "plan": "some-plan", "status": "done"}],
            metadata={
                "execution_environment": {
                    "engine_root": str(engine_root),
                }
            },
        ),
    )

    from arnold_pipelines.megaplan.chain.epic_chain import _observe_child_epic, EpicSpec

    epic = EpicSpec(id="test-child", spec=str(child_spec))
    child = _observe_child_epic(epic, parent_spec_path=parent_spec)

    assert child.effective_status == "complete"
    # Authority drift should be None when the check can't run (no project_root/plan).
    assert child.authority_drift is None


# ── T-0011: child relaunch enforces recorded = manifest = live engine root ──


def _write_runtime_manifest_file(root: Path, runtime_root: Path) -> Path:
    manifest = root / "runtime-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "epic": {
                    "runtime_root": str(runtime_root),
                    "expected_head": "a" * 40,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def _set_preflight_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    engine_root: Path | None = None,
) -> Path:
    """Pin a valid per-session runtime binding so the child-runtime preflight
    (T-0011 / G2 round-5 finding 1) passes on observe paths that must
    legitimately load child state."""
    root = engine_root or megaplan_engine_root()
    manifest = _write_runtime_manifest_file(tmp_path, root)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))
    return root


def _reject_admission_spies(monkeypatch: pytest.MonkeyPatch):
    """Spy state load, execution binding, spawn, and child observation; all
    must stay untouched when the runtime-binding preflight rejects a
    relaunch or an outer-path observe. The observe spy wraps the REAL
    function (records, then delegates) so a call that slips past the
    preflight is a genuine regression, not a stub artifact."""
    from arnold_pipelines.megaplan.chain import epic_chain as epic_chain_module
    from arnold_pipelines.megaplan.chain import execution_binding as binding_module

    state_loads: list = []
    binds: list = []
    spawns: list = []
    observes: list = []
    real_observe = epic_chain_module._observe_child_epic
    monkeypatch.setattr(
        epic_chain_module,
        "load_chain_state",
        lambda *args, **kwargs: state_loads.append(args) or ChainState(),
    )
    monkeypatch.setattr(
        binding_module,
        "bind_execution_identity",
        lambda *args, **kwargs: binds.append(args) or {},
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: spawns.append(args)
        or subprocess.CompletedProcess([], 0, "", ""),
    )
    monkeypatch.setattr(
        epic_chain_module,
        "_observe_child_epic",
        lambda *args, **kwargs: observes.append(args)
        or real_observe(*args, **kwargs),
    )
    return state_loads, binds, spawns, observes


def test_epic_chain_child_relaunch_requires_manifest_pin_before_state_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold_pipelines.megaplan.chain.epic_chain import (
        EpicSpec,
        _default_start_child_chain,
    )
    from arnold_pipelines.megaplan.runtime.process import megaplan_engine_root
    from arnold_pipelines.megaplan.types import CliError

    child_spec = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    parent_spec = _write_parent_spec(tmp_path, child_spec=child_spec)
    save_chain_state(
        child_spec,
        ChainState(
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                    "engine_root": str(megaplan_engine_root()),
                }
            }
        ),
    )
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    state_loads, binds, spawns, observes = _reject_admission_spies(monkeypatch)

    epic = EpicSpec(id="test-child", spec=str(child_spec))
    with pytest.raises(CliError) as excinfo:
        _default_start_child_chain(epic, parent_spec_path=parent_spec)

    assert excinfo.value.code == "chain_runtime_binding_drift"
    assert "missing runtime manifest pin" in excinfo.value.message
    assert state_loads == []
    assert binds == []
    assert spawns == []
    assert observes == []


def test_epic_chain_child_relaunch_fails_closed_on_manifest_without_runtime_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold_pipelines.megaplan.chain.epic_chain import (
        EpicSpec,
        _default_start_child_chain,
    )
    from arnold_pipelines.megaplan.runtime.process import megaplan_engine_root
    from arnold_pipelines.megaplan.types import CliError

    child_spec = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    parent_spec = _write_parent_spec(tmp_path, child_spec=child_spec)
    save_chain_state(
        child_spec,
        ChainState(
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                    "engine_root": str(megaplan_engine_root()),
                }
            }
        ),
    )
    manifest = tmp_path / "runtime-manifest.json"
    manifest.write_text(
        json.dumps({"epic": {"expected_head": "a" * 40}}) + "\n", encoding="utf-8"
    )
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))
    state_loads, binds, spawns, observes = _reject_admission_spies(monkeypatch)

    epic = EpicSpec(id="test-child", spec=str(child_spec))
    with pytest.raises(CliError) as excinfo:
        _default_start_child_chain(epic, parent_spec_path=parent_spec)

    assert excinfo.value.code == "chain_runtime_binding_drift"
    assert "lacks a nonempty epic.runtime_root" in excinfo.value.message
    assert state_loads == []
    assert binds == []
    assert spawns == []
    assert observes == []


def test_epic_chain_child_relaunch_fails_closed_when_recorded_engine_root_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold_pipelines.megaplan.chain.epic_chain import (
        EpicSpec,
        _default_start_child_chain,
    )
    from arnold_pipelines.megaplan.runtime.process import megaplan_engine_root
    from arnold_pipelines.megaplan.types import CliError

    child_spec = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    parent_spec = _write_parent_spec(tmp_path, child_spec=child_spec)
    # Chain state persists WITHOUT metadata.execution_environment.engine_root.
    save_chain_state(
        child_spec,
        ChainState(
            metadata={"execution_environment": {"project_root": str(tmp_path)}}
        ),
    )
    manifest = _write_runtime_manifest_file(tmp_path, megaplan_engine_root())
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))
    state_loads, binds, spawns, observes = _reject_admission_spies(monkeypatch)

    epic = EpicSpec(id="test-child", spec=str(child_spec))
    with pytest.raises(CliError) as excinfo:
        _default_start_child_chain(epic, parent_spec_path=parent_spec)

    assert excinfo.value.code == "chain_runtime_binding_drift"
    assert "lacks metadata.execution_environment.engine_root" in excinfo.value.message
    assert state_loads == []
    assert binds == []
    assert spawns == []
    assert observes == []


def test_epic_chain_child_relaunch_fails_closed_when_recorded_engine_root_dangling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold_pipelines.megaplan.chain.epic_chain import (
        EpicSpec,
        _default_start_child_chain,
    )
    from arnold_pipelines.megaplan.types import CliError

    child_spec = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    parent_spec = _write_parent_spec(tmp_path, child_spec=child_spec)
    gone_root = tmp_path / "gone-runtime"
    save_chain_state(
        child_spec,
        ChainState(
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                    "engine_root": str(gone_root),
                }
            }
        ),
    )
    # The manifest agrees with the recorded root, but the root itself is gone.
    manifest = _write_runtime_manifest_file(tmp_path, gone_root)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))
    state_loads, binds, spawns, observes = _reject_admission_spies(monkeypatch)

    epic = EpicSpec(id="test-child", spec=str(child_spec))
    with pytest.raises(CliError) as excinfo:
        _default_start_child_chain(epic, parent_spec_path=parent_spec)

    assert excinfo.value.code == "chain_runtime_binding_drift"
    assert "is missing or dangling" in excinfo.value.message
    assert state_loads == []
    assert binds == []
    assert spawns == []
    assert observes == []


def test_epic_chain_child_relaunch_rejects_engine_root_mismatch_against_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold_pipelines.megaplan.chain.epic_chain import (
        EpicSpec,
        _default_start_child_chain,
    )
    from arnold_pipelines.megaplan.runtime.process import megaplan_engine_root
    from arnold_pipelines.megaplan.types import CliError

    child_spec = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    parent_spec = _write_parent_spec(tmp_path, child_spec=child_spec)
    live_root = megaplan_engine_root()
    other_root = tmp_path / "other-runtime"
    other_root.mkdir()
    save_chain_state(
        child_spec,
        ChainState(
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                    "engine_root": str(live_root),
                }
            }
        ),
    )
    # Manifest names a different runtime than the recorded/live root.
    manifest = _write_runtime_manifest_file(tmp_path, other_root)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))
    state_loads, binds, spawns, observes = _reject_admission_spies(monkeypatch)

    epic = EpicSpec(id="test-child", spec=str(child_spec))
    with pytest.raises(CliError) as excinfo:
        _default_start_child_chain(epic, parent_spec_path=parent_spec)

    assert excinfo.value.code == "chain_runtime_binding_drift"
    assert "engine root mismatch" in excinfo.value.message
    assert str(live_root) in excinfo.value.message
    assert str(other_root) in excinfo.value.message
    assert state_loads == []
    assert binds == []
    assert spawns == []
    assert observes == []


def test_epic_chain_child_relaunch_rejects_engine_root_mismatch_against_live_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold_pipelines.megaplan.chain import epic_chain as epic_chain_module
    from arnold_pipelines.megaplan.chain.epic_chain import (
        EpicSpec,
        _default_start_child_chain,
    )
    from arnold_pipelines.megaplan.runtime.process import megaplan_engine_root
    from arnold_pipelines.megaplan.types import CliError

    child_spec = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    parent_spec = _write_parent_spec(tmp_path, child_spec=child_spec)
    live_root = megaplan_engine_root()
    save_chain_state(
        child_spec,
        ChainState(
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                    "engine_root": str(live_root),
                }
            }
        ),
    )
    manifest = _write_runtime_manifest_file(tmp_path, live_root)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))
    # The live import root differs from the recorded/manifest root.
    monkeypatch.setattr(
        epic_chain_module,
        "megaplan_engine_root",
        lambda: tmp_path / "live-import-root",
    )
    state_loads, binds, spawns, observes = _reject_admission_spies(monkeypatch)

    epic = EpicSpec(id="test-child", spec=str(child_spec))
    with pytest.raises(CliError) as excinfo:
        _default_start_child_chain(epic, parent_spec_path=parent_spec)

    assert excinfo.value.code == "chain_runtime_binding_drift"
    assert "engine root mismatch" in excinfo.value.message
    assert state_loads == []
    assert binds == []
    assert spawns == []
    assert observes == []


def test_epic_chain_child_relaunch_binds_accepted_engine_root_only_on_pythonpath(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold_pipelines.megaplan.chain import epic_chain as epic_chain_module
    from arnold_pipelines.megaplan.chain.epic_chain import (
        EpicSpec,
        _default_start_child_chain,
    )
    from arnold_pipelines.megaplan.runtime.process import megaplan_engine_root

    child_spec = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    parent_spec = _write_parent_spec(tmp_path, child_spec=child_spec)
    live_root = megaplan_engine_root()
    save_chain_state(
        child_spec,
        ChainState(
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                    "engine_root": str(live_root),
                }
            }
        ),
    )
    manifest = _write_runtime_manifest_file(tmp_path, live_root)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))

    state_loads: list = []
    monkeypatch.setattr(
        epic_chain_module,
        "load_chain_state",
        lambda spec_path: state_loads.append(spec_path)
        or ChainState(
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                    "engine_root": str(live_root),
                }
            }
        ),
    )
    captured: dict = {}

    def fake_run(cmd, **kwargs) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env")
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    epic = EpicSpec(id="test-child", spec=str(child_spec))
    result = _default_start_child_chain(epic, parent_spec_path=parent_spec)

    assert result.returncode == 0
    assert len(state_loads) == 1
    env = captured["env"]
    # ONLY the accepted engine root reaches the child's PYTHONPATH (T-0011).
    assert env["PYTHONPATH"] == str(live_root)
    assert env["MEGAPLAN_ENGINE_ROOT"] == str(live_root)
    assert env["PYTHONSAFEPATH"] == "1"
    assert captured["cmd"][:2] == [sys.executable, "-P"]


# ── G2 round-5 finding 1: outer-path observe rejects drift BEFORE state load ──


def test_epic_chain_outer_path_rejects_runtime_drift_before_state_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The outer epic-chain path (run_epic_chain -> _observe_child_epic) must
    run the runtime-binding preflight BEFORE _observe_child_epic or
    load_chain_state: a recorded engine_root that is missing/dangling raises
    chain_runtime_binding_drift with zero child state loads (G2 round-5
    finding 1 — the T-0011 guards were previously only exercised via
    _default_start_child_chain directly)."""
    from arnold_pipelines.megaplan.types import CliError

    child_spec = _write_child_chain_spec(tmp_path, "python-shaped-workflow-authoring")
    parent_spec = _write_parent_spec(tmp_path, child_spec=child_spec)
    # The persisted child state records an engine root that no longer exists
    # (dangling) — the manifest agrees with it, so only the dangling check
    # fires, and it must fire before ANY child state load / observation.
    gone_root = tmp_path / "gone-runtime"
    save_chain_state(
        child_spec,
        ChainState(
            metadata={
                "execution_environment": {
                    "project_root": str(tmp_path),
                    "engine_root": str(gone_root),
                }
            }
        ),
    )
    manifest = _write_runtime_manifest_file(tmp_path, gone_root)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))
    state_loads, binds, spawns, observes = _reject_admission_spies(monkeypatch)

    with pytest.raises(CliError) as excinfo:
        run_epic_chain(tmp_path, parent_spec, writer=lambda _msg: None)

    assert excinfo.value.code == "chain_runtime_binding_drift"
    assert "is missing or dangling" in excinfo.value.message
    # The outer path must reject BEFORE any child state read or observation.
    assert state_loads == []
    assert observes == []
    assert binds == []
    assert spawns == []
