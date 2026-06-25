from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from arnold.pipeline import Pipeline
from arnold.pipeline.native import NativeProgram, run_native_pipeline


_EPIC_MODULE = "arnold.pipelines.megaplan.pipelines.epic_blitz"
_EXPECTED_STAGE_ORDER = (
    "high_panel",
    "high_revise",
    "mid_panel",
    "mid_revise",
    "low_panel",
    "readiness",
)
_HIGH_REVIEWERS = (
    "existing_system_reuse",
    "conceptual_fit",
    "missing_abstraction",
    "epic_decomposition",
    "strategic_risk",
)
_MID_REVIEWERS = (
    "codebase_convention_fit",
    "data_artifact_model",
    "orchestration_semantics",
    "agent_model_assignment",
    "blast_radius",
)
_LOW_REVIEWERS = (
    "implementation_feasibility",
    "testability",
    "edge_cases",
    "cli_ux_details",
    "migration_backcompat",
)
_EXPECTED_ARTIFACTS = tuple(
    sorted(
        (
            "draft.md",
            "high_revise/v1.md",
            "mid_revise/v1.md",
            "readiness/v1.md",
            *(f"high_panel/{reviewer}/v1.md" for reviewer in _HIGH_REVIEWERS),
            *(f"mid_panel/{reviewer}/v1.md" for reviewer in _MID_REVIEWERS),
            *(f"low_panel/{reviewer}/v1.md" for reviewer in _LOW_REVIEWERS),
        )
    )
)
_EXPECTED_STATE_KEYS = {
    "draft",
    "high_revise",
    "mid_revise",
    "readiness",
    *_HIGH_REVIEWERS,
    *_MID_REVIEWERS,
    *_LOW_REVIEWERS,
}


@pytest.fixture(autouse=True)
def _typed_ports_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)


def _load_epic_module() -> ModuleType:
    return importlib.import_module(_EPIC_MODULE)


def _build_pipeline() -> Pipeline:
    built = _load_epic_module().build_pipeline()
    assert isinstance(built, Pipeline)
    assert isinstance(built.native_program, NativeProgram)
    return built


def _setup_draft(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "draft.md").write_text(
        "# Epic Draft\n\nA deterministic epic-blitz native draft.\n",
        encoding="utf-8",
    )


def _run_native(root: Path, *, max_phases: int | None = None, resume: bool = False) -> Any:
    _setup_draft(root)
    pipeline = _build_pipeline()
    return run_native_pipeline(
        pipeline.native_program,
        artifact_root=root,
        initial_state={"draft": str(root / "draft.md")} if not resume else {},
        max_phases=max_phases,
        resume=resume,
    )


def _phase_name(stage_id: str) -> str:
    without_prefix = stage_id.removeprefix("epic_blitz__")
    return without_prefix.split("__pc", 1)[0]


def _collapsed_stage_order(stage_ids: list[str]) -> tuple[str, ...]:
    collapsed: list[str] = []
    for stage_id in stage_ids:
        phase = _phase_name(stage_id)
        stage = phase.split(".", 1)[0]
        if not collapsed or collapsed[-1] != stage:
            collapsed.append(stage)
    return tuple(collapsed)


def _artifact_paths(root: Path) -> tuple[str, ...]:
    skipped = {"resume_cursor.json", "events.ndjson", ".events.init_ts", ".events.seq"}
    return tuple(
        sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file() and path.name not in skipped
        )
    )


def _state_relpaths(root: Path, state: dict[str, Any]) -> dict[str, str]:
    relpaths: dict[str, str] = {}
    for key, value in state.items():
        try:
            relpaths[key] = Path(value).relative_to(root).as_posix()
        except (TypeError, ValueError):
            relpaths[key] = str(value)
    return relpaths


def test_epic_blitz_public_builder_attaches_direct_native_program() -> None:
    module = _load_epic_module()
    public_names = set(getattr(module, "__all__", ())) | {
        name for name in vars(module) if not name.startswith("_")
    }

    built = _build_pipeline()

    assert module.name == "epic-blitz"
    assert module.supported_modes == ("native",)
    assert module.driver == ("native", "panel")
    assert module.entrypoint == "build_pipeline"
    assert isinstance(built.native_program, NativeProgram)
    assert built.native_program.name == "epic-blitz"
    assert built.resource_bundles == ()
    assert "build_legacy_graph_pipeline" not in public_names
    assert "build_graph_pipeline" not in public_names


def test_epic_blitz_native_projection_stage_order() -> None:
    built = _build_pipeline()

    assert tuple(built.stages) == _EXPECTED_STAGE_ORDER
    assert built.entry == "high_panel"
    assert _collapsed_stage_order(
        [
            f"epic_blitz__{instr.name}__pc{instr.pc}"
            for instr in built.native_program.instructions
            if instr.op == "phase"
        ]
    ) == _EXPECTED_STAGE_ORDER


def test_epic_blitz_native_execution_writes_panel_artifacts_output_and_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "native"

    result = _run_native(root)

    assert _collapsed_stage_order(result.stages) == _EXPECTED_STAGE_ORDER
    assert _artifact_paths(root) == _EXPECTED_ARTIFACTS
    assert set(result.state) == _EXPECTED_STATE_KEYS
    assert _state_relpaths(root, result.state)["readiness"] == "readiness/v1.md"

    assert "PanelReviewer existing_system_reuse" in (
        root / "high_panel" / "existing_system_reuse" / "v1.md"
    ).read_text(encoding="utf-8")
    assert "AgentStep readiness" in (root / "readiness" / "v1.md").read_text(
        encoding="utf-8"
    )
    assert "prompts/reviser/readiness.md" in (
        root / "readiness" / "v1.md"
    ).read_text(encoding="utf-8")


def test_epic_blitz_native_resume_from_high_panel_barrier(tmp_path: Path) -> None:
    root = tmp_path / "resume"

    suspended = _run_native(root, max_phases=len(_HIGH_REVIEWERS))
    cursor = json.loads((root / "resume_cursor.json").read_text(encoding="utf-8"))

    assert suspended.suspended is True
    assert _collapsed_stage_order(suspended.stages) == ("high_panel",)
    assert cursor["native"]["pc"] == 6
    assert cursor["reentry_stage"] == "epic-blitz__high_revise__pc6"
    assert _artifact_paths(root) == tuple(
        sorted(
            (
                "draft.md",
                *(f"high_panel/{reviewer}/v1.md" for reviewer in _HIGH_REVIEWERS),
            )
        )
    )

    resumed = _run_native(root, resume=True)
    full = _run_native(tmp_path / "full")

    assert resumed.suspended is False
    assert _collapsed_stage_order(resumed.stages) == _EXPECTED_STAGE_ORDER
    assert _artifact_paths(root) == _EXPECTED_ARTIFACTS
    assert _state_relpaths(root, resumed.state) == _state_relpaths(
        tmp_path / "full",
        full.state,
    )
    assert not (root / "high_panel" / "existing_system_reuse" / "v2.md").exists()
