from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan import cli
from arnold_pipelines.megaplan.auto import _admit_auto_driver
from arnold_pipelines.megaplan.custody.admission_control import (
    AdmissionFence,
    CHAIN_RUNNER_ADMISSION_SURFACE,
    CHAIN_RUNNER_ADMISSION_WRITER_ID,
    INIT_ADMISSION_SURFACE,
    INIT_ADMISSION_WRITER_ID,
    SOURCE_BINDING_ADMISSION_SURFACE,
    SOURCE_BINDING_ADMISSION_WRITER_ID,
    SUPERVISOR_ADMISSION_SURFACE,
    SUPERVISOR_ADMISSION_WRITER_ID,
    register_admission_writers,
    synthetic_text_source_record,
    validate_admission_mutation,
)
from arnold_pipelines.megaplan.custody.controlled_writer_registry import _clear_registry
from arnold_pipelines.megaplan.handlers.init import handle_init
from arnold_pipelines.megaplan.chain.spec import ChainState, load_spec
from arnold_pipelines.megaplan.planning.source_binding import capture_canonical_source_binding
from arnold_pipelines.megaplan.supervisor.chain_runner import _admit_chain_materialization
from arnold_pipelines.megaplan.supervisor.driver import DefaultRunDriver, RunRequest
from arnold_pipelines.megaplan.types import CliError

from .test_chain_execution_binding import _pinned_chain


@pytest.fixture(autouse=True)
def _reset_writer_registry() -> None:
    _clear_registry()
    yield
    _clear_registry()


def _plan_state(root: Path, source: Path) -> tuple[Path, dict[str, object]]:
    plan_dir = root / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    state: dict[str, object] = {
        "name": "demo",
        "idea": source.read_text(encoding="utf-8"),
        "idea_snapshot_path": "idea_snapshot.md",
        "current_state": "finalized",
        "iteration": 1,
        "config": {"project_dir": str(root)},
        "meta": {},
    }
    (plan_dir / "idea_snapshot.md").write_text(str(state["idea"]), encoding="utf-8")
    capture_canonical_source_binding(state, source_path=source, project_dir=root)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return plan_dir, state


def test_admission_guard_requires_registered_writer() -> None:
    with pytest.raises(CliError, match="controlled writer"):
        validate_admission_mutation(
            writer_id=INIT_ADMISSION_WRITER_ID,
            surface_name=INIT_ADMISSION_SURFACE,
            selector="demo",
            source_record=synthetic_text_source_record(
                selector="demo",
                label="guard",
                text="demo",
            ),
        )


def test_admission_guard_rejects_missing_selector_manifest_and_fence() -> None:
    register_admission_writers()
    source_record = synthetic_text_source_record(
        selector="demo",
        label="guard",
        text="demo",
    )

    with pytest.raises(CliError, match="non-empty selector"):
        validate_admission_mutation(
            writer_id=SOURCE_BINDING_ADMISSION_WRITER_ID,
            surface_name=SOURCE_BINDING_ADMISSION_SURFACE,
            selector="",
            source_record=source_record,
        )

    with pytest.raises(CliError, match="exact source record"):
        validate_admission_mutation(
            writer_id=SOURCE_BINDING_ADMISSION_WRITER_ID,
            surface_name=SOURCE_BINDING_ADMISSION_SURFACE,
            selector="demo",
            source_record={"exists": False, "errors": ["canonical_source_missing"]},
        )

    with pytest.raises(CliError, match="fence"):
        validate_admission_mutation(
            writer_id=CHAIN_RUNNER_ADMISSION_WRITER_ID,
            surface_name=CHAIN_RUNNER_ADMISSION_SURFACE,
            selector="demo",
            source_record=source_record,
            fences=(
                AdmissionFence(
                    identity="current_plan_name",
                    expected=None,
                    observed="demo",
                    satisfied=False,
                ),
            ),
        )


def test_handle_init_records_admission_evidence(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    brief = project_dir / "brief.md"
    brief.write_text("# Goal\n\n- Preserve admission checks.\n", encoding="utf-8")

    base = cli.build_parser().parse_args(["init"])
    args = argparse.Namespace(**vars(base))
    args.project_dir = str(project_dir)
    args.idea = str(brief.relative_to(project_dir))
    args.name = "fixture-plan"
    args.robustness = "standard"

    response = handle_init(root, args)
    plan_dir = root / ".megaplan" / "plans" / response["plan"]
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    evidence = state["meta"]["admission_controls"]["init"]

    assert evidence["writer_id"] == INIT_ADMISSION_WRITER_ID
    assert evidence["selector"] == "fixture-plan"
    assert evidence["source_record"]["semantic_sha256"]


def test_auto_admission_rejects_stale_canonical_source_before_dispatch(tmp_path: Path) -> None:
    source = tmp_path / "brief.md"
    source.write_text("# Criteria\n\n- Original invariant.\n", encoding="utf-8")
    plan_dir, _state = _plan_state(tmp_path, source)
    source.write_text("# Criteria\n\n- Narrowed invariant.\n", encoding="utf-8")

    with pytest.raises(CliError, match="canonical source binding is changed"):
        _admit_auto_driver(plan_dir, "demo")


def test_supervisor_driver_requires_current_root_fence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    driver = DefaultRunDriver()
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.supervisor.driver.auto_drive",
        lambda *_args, **_kwargs: pytest.fail("auto drive should not run when admission fails"),
    )

    with pytest.raises(CliError, match="fence"):
        driver.drive(
            RunRequest(
                root=tmp_path / "missing-root",
                plan="demo",
            )
        )


def test_chain_runner_admission_blocks_re_materializing_current_milestone(tmp_path: Path) -> None:
    spec_path = _pinned_chain(tmp_path)
    spec = load_spec(spec_path)
    state = ChainState(current_milestone_index=0, current_plan_name="c1-plan")

    with pytest.raises(CliError, match="fence"):
        _admit_chain_materialization(
            root=tmp_path,
            spec_path=spec_path,
            spec=spec,
            state=state,
            milestone=spec.milestones[0],
            milestone_index=0,
        )
