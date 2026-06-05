"""M6 dual-run oracle for retiring PR4.

This is the SOLE retirement authority for PR4. It compares a planning-shaped
throwaway plan through the legacy planning compiler and the discovered planning
package, then checks the release-recorded recovery/escalate/blocked traces that
must stay present for replay coverage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

import arnold.pipelines.megaplan as megaplan
import arnold.pipelines.megaplan.cli as megaplan_cli
from arnold.pipelines import megaplan
import arnold.pipelines.megaplan._core
import arnold.pipelines.megaplan._core.io as io_module
from arnold.pipelines.megaplan._pipeline.planning import compile_planning_pipeline
from arnold.pipelines.megaplan._pipeline.types import Pipeline, Stage, StepContext

from tests.conftest import make_args_factory


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
DOC_PATH = Path(__file__).resolve().parents[2] / "briefs" / "m6" / "oracle-bake-time.md"


def _bootstrap(root: Path, project_dir: Path, config_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root.mkdir()
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    config_path.mkdir()

    def _config_dir(home: Path | None = None) -> Path:
        del home
        return config_path

    monkeypatch.setenv(megaplan.MOCK_ENV_VAR, "1")
    monkeypatch.setattr(
        megaplan._core.shutil,
        "which",
        lambda name: "/usr/bin/mock" if name in {"claude", "codex"} else None,
    )
    monkeypatch.setattr(io_module, "config_dir", _config_dir)
    monkeypatch.setattr(megaplan.cli, "config_dir", _config_dir)


def _pipeline_signature(pipeline: Pipeline) -> dict[str, Any]:
    signature: dict[str, Any] = {"entry": pipeline.entry, "stages": {}}
    for name, node in sorted(pipeline.stages.items()):
        assert isinstance(node, Stage), f"planning stage {name!r} is not a Stage"
        signature["stages"][name] = {
            "step_class": type(node.step).__name__,
            "edges": [
                {
                    "label": edge.label,
                    "target": edge.target,
                    "kind": edge.kind,
                    "recommendation": edge.recommendation,
                }
                for edge in node.edges
            ],
        }
    return signature


def _init_throwaway_plan(root: Path, project_dir: Path, *, name: str) -> Path:
    make_args = make_args_factory(project_dir)
    response = megaplan.handle_init(
        root,
        make_args(
            name=name,
            idea="ship the M6 dual-run oracle throwaway plan",
            robustness="standard",
        ),
    )
    plan_name = response["plan"]
    megaplan.handle_override(
        root,
        make_args(
            plan=plan_name,
            override_action="add-note",
            note="dual-run oracle release trace",
        ),
    )
    return megaplan.plans_root(root) / plan_name


def _read_state(plan_dir: Path) -> dict[str, Any]:
    return json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))


def _ctx(plan_dir: Path, root: Path, project_dir: Path, plan_name: str) -> StepContext:
    return StepContext(
        plan_dir=plan_dir,
        state={"name": plan_name, **_read_state(plan_dir)},
        profile={"root": root, "project_dir": project_dir},
        mode="code",
        inputs={},
        budget=None,
    )


def _drive_throwaway_pipeline(
    *,
    plan_dir: Path,
    root: Path,
    project_dir: Path,
    pipeline: Pipeline,
) -> dict[str, Any]:
    plan_name = plan_dir.name
    visits: list[str] = []

    state_to_stage = {
        "initialized": "prep",
        "prepped": "plan",
        "planned": "critique",
        "critiqued": "gate",
        "gated": "finalize",
        "finalized": "execute",
        "executed": "review",
    }

    for _ in range(25):
        state = _read_state(plan_dir)
        current = state.get("current_state")
        if current in {"done", "aborted"}:
            visits.append(f"terminal:{current}")
            return {
                "final_state": current,
                "visits": visits,
                "artifacts": sorted(
                    name
                    for name in (
                        "prep.json",
                        "plan_v1.md",
                        "gate.json",
                        "final.md",
                        "finalize.json",
                        "execution.json",
                        "review.json",
                    )
                    if (plan_dir / name).exists()
                ),
            }
        stage_name = state_to_stage.get(str(current))
        if stage_name is None:
            raise AssertionError(f"unexpected planning state {current!r}")

        node = pipeline.stages[stage_name]
        assert isinstance(node, Stage)
        result = node.step.run(_ctx(plan_dir, root, project_dir, plan_name))
        visits.append(f"{current}->{stage_name}:{result.next}")
        if stage_name == "gate" and result.verdict is not None and result.verdict.recommendation == "iterate":
            revise = pipeline.stages["revise"]
            assert isinstance(revise, Stage)
            revise_result = revise.step.run(_ctx(plan_dir, root, project_dir, plan_name))
            visits.append(f"revise:{revise_result.next}")

    raise AssertionError(f"planning pipeline did not terminate; visits={visits!r}")


def _run_case(
    *,
    root: Path,
    project_dir: Path,
    discovered: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    monkeypatch.setenv("MEGAPLAN_M6_DISCOVERED_PLANNING", "1" if discovered else "0")
    pipeline = compile_planning_pipeline()
    plan_dir = _init_throwaway_plan(
        root,
        project_dir,
        name="dual-run-discovered" if discovered else "dual-run-legacy",
    )
    summary = _drive_throwaway_pipeline(
        plan_dir=plan_dir,
        root=root,
        project_dir=project_dir,
        pipeline=pipeline,
    )
    summary["pipeline_signature"] = _pipeline_signature(pipeline)
    return summary


def test_planning_dual_run_oracle_matches_legacy_and_discovered_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    _bootstrap(root, project_dir, tmp_path / "config", monkeypatch)

    legacy = _run_case(
        root=root,
        project_dir=project_dir,
        discovered=False,
        monkeypatch=monkeypatch,
    )
    discovered = _run_case(
        root=root,
        project_dir=project_dir,
        discovered=True,
        monkeypatch=monkeypatch,
    )

    assert discovered["final_state"] == "done"
    assert discovered == legacy


def _load_fixture(name: str) -> Mapping[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_recorded_real_run_traces_cover_recovery_escalate_and_blocked() -> None:
    manifest = _load_fixture("manifest.json")

    assert manifest["retirement_authority"] == "SOLE retirement authority for PR4"
    roles = {entry["role"]: entry for entry in manifest["traces"]}
    assert set(roles) == {"blocked", "escalate", "recovery"}

    expectations = {
        "blocked": ("worker_blocked", "finalized"),
        "escalate": ("escalated", "gated"),
        "recovery": ("done", "done"),
    }
    for role, (status, final_state) in expectations.items():
        payload = _load_fixture(roles[role]["fixture"])
        assert payload["recording_kind"] == "recorded-real-run-trace"
        assert payload["role"] == role
        assert payload["outcome"]["status"] == status
        assert payload["outcome"]["final_state"] == final_state
        assert payload["events"], f"{role} trace must carry replay events"


def test_release_recording_harness_and_soak_time_note_are_present() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "record_oracle_traces.py"
    assert script.exists()
    assert DOC_PATH.exists()
    text = DOC_PATH.read_text(encoding="utf-8")
    assert "SOLE retirement authority for PR4" in text
    assert "same-day green carries weaker evidence than a soak-period green" in text
