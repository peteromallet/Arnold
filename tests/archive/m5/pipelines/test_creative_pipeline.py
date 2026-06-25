"""Tests for the native-backed ``creative`` pipeline.

Exercises the first-class ``creative`` pipeline through the same
``megaplan run`` code path the real-model smoke uses:
:func:`megaplan._pipeline.run_cli.cli_run` →
:func:`megaplan._pipeline.run_cli._run_pipeline`.

Required assertions:

(a) Form dispatch wires joke-specific prompts when ``--form joke`` -
    the stage shells carry ``prompt_key=f"<base>:joke"`` and those
    slots are owned by the creative prompt bundle. ``--form poem``
    routes to the generic creative slots while carrying poem metadata
    in state/params.
(b) Provocations sidecar + stance validation are wired in via the
    relocated prompt modules (``critique_creative`` imports
    ``select_active_checks`` from ``megaplan.forms.provocations`` and
    references ``directors_notes.json``; ``execute_creative`` emits
    structured ``stance`` instructions in its rendered prompt).
(c) ``--form xyz`` (unknown form) raises
    ``CliError('invalid_args')`` from ``build_pipeline``.
(d) ``--primary-criterion`` flows into
    ``build_pipeline(primary_criterion=…)`` and surfaces on each stage's
    Step as a dataclass field for downstream prompt rendering.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest


def test_creative_package_init_is_thin_metadata_surface() -> None:
    import arnold.pipelines.megaplan.pipelines.creative as package
    from arnold.pipelines.megaplan.pipelines.creative import pipeline as pipeline_module

    assert package.build_pipeline is pipeline_module.build_pipeline
    assert package.name == "creative"
    assert package.driver[0] == "native"
    assert "native" in package.supported_modes
    assert "creative_native" not in package.__all__
    assert not hasattr(package, "creative_native")


def test_creative_mirror_is_compatibility_shim() -> None:
    import arnold.pipelines.megaplan.pipelines.creative as canonical
    import arnold.pipelines.megaplan.pipelines.creative.pipeline as canonical_pipeline
    import arnold_pipelines.megaplan.pipelines.creative as mirror
    import arnold_pipelines.megaplan.pipelines.creative.pipeline as mirror_pipeline

    assert mirror.build_pipeline is canonical.build_pipeline
    assert mirror_pipeline.build_pipeline is canonical_pipeline.build_pipeline
    assert mirror.__all__ == canonical.__all__


def test_creative_build_pipeline_returns_native_backed_projected_shell() -> None:
    from arnold.pipeline import Pipeline
    from arnold.pipeline.native import NativeProgram
    from arnold.pipelines.megaplan.pipelines.creative import build_pipeline

    pipeline = build_pipeline(form="poem", primary_criterion="image pressure")

    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)
    assert pipeline.native_program.name == "creative"
    assert tuple(pipeline.stages) == (
        "prep",
        "execute_creative",
        "critique_creative",
        "revise_creative",
        "finalize",
    )
    assert tuple(pipeline.resource_bundles) == ()
    assert pipeline.stages["execute_creative"].step.form == "poem"
    assert pipeline.stages["execute_creative"].step.primary_criterion == "image pressure"


def _make_run_args(
    *,
    pipeline_name: str,
    plan_dir: Path,
    state: dict[str, Any] | None = None,
    mode: str | None = None,
    form: str | None = None,
    primary_criterion: str | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        list_pipelines=False,
        pipeline_name=pipeline_name,
        input_file=None,
        plan_dir=str(plan_dir),
        inputs=None,
        state=json.dumps(state) if state is not None else None,
        mode=mode,
        profile=None,
        describe=False,
        resume_choice=None,
        vendor=None,
        form=form,
        primary_criterion=primary_criterion,
    )


# ── (a) Form dispatch: joke vs poem wires the right ``prompt_key`` slots ─


def test_creative_form_joke_dispatches_joke_prompt_keys() -> None:
    from arnold.pipelines.megaplan.pipelines.creative import build_pipeline

    pipeline = build_pipeline(form="joke")
    stage_prompt_keys = {
        name: stage.step.prompt_key for name, stage in pipeline.stages.items()
    }
    assert stage_prompt_keys["prep"] == "prep:joke"
    assert stage_prompt_keys["execute_creative"] == "execute_creative:joke"
    assert stage_prompt_keys["critique_creative"] == "critique_creative:joke"
    assert stage_prompt_keys["revise_creative"] == "revise_creative:joke"
    # finalize is a terminator with no rendered prompt.
    assert stage_prompt_keys["finalize"] is None


def test_creative_form_poem_dispatches_generic_prompt_keys() -> None:
    from arnold.pipelines.megaplan.pipelines.creative import build_pipeline

    pipeline = build_pipeline(form="poem")
    stage_prompt_keys = {
        name: stage.step.prompt_key for name, stage in pipeline.stages.items()
    }
    assert stage_prompt_keys["prep"] == "prep"
    assert stage_prompt_keys["execute_creative"] == "execute_creative"
    assert stage_prompt_keys["critique_creative"] == "critique_creative"
    assert stage_prompt_keys["revise_creative"] == "revise_creative"
    assert stage_prompt_keys["finalize"] is None


def test_creative_pipeline_registers_generic_and_joke_prompt_slots() -> None:
    """The creative prompt bundle owns generic and joke slots only."""

    from arnold.pipelines.megaplan.pipelines.creative.prompts import CREATIVE_PROMPT_BUNDLE
    from arnold.pipelines.megaplan.forms import available_form_ids

    keys = set(CREATIVE_PROMPT_BUNDLE.prompts)
    for base in ("prep", "execute_creative", "critique_creative", "revise_creative"):
        # Generic form (rule-2 fallback when no mode is set).
        assert f"creative/{base}" in keys, (
            f"missing generic creative slot creative/{base}; got "
            f"{sorted(k for k in keys if k.startswith('creative/'))}"
        )
        # Joke-form specialised slot.
        assert f"creative/{base}:joke" in keys, (
            f"missing joke-specialised creative slot creative/{base}:joke; got "
            f"{sorted(k for k in keys if k.startswith('creative/'))}"
        )
        for form_id in available_form_ids():
            if form_id == "joke":
                continue
            assert f"creative/{base}:{form_id}" not in keys, (
                f"non-joke form {form_id!r} should use generic creative/{base}, "
                f"not a form-baked slot; got "
                f"{sorted(k for k in keys if k.startswith('creative/'))}"
            )


def test_generic_creative_poem_prompts_render_from_fresh_state(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan.pipelines.creative.prompts import render_prompt
    from arnold.pipelines.megaplan._pipeline.types import StepContext

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state: dict[str, Any] = {
        "idea": "write a small poem about a blue door",
        "config": {
            "mode": "creative",
            "form": "poem",
            "project_dir": str(project_dir),
            "output_path": "poem.md",
            "primary_criterion": "most surprising exact image",
            "robustness": "standard",
        },
        "iteration": 1,
    }
    ctx = StepContext(
        plan_dir=plan_dir,
        state=state,
        profile=None,
        mode="creative",
        inputs={"_pipeline": "creative"},
    )

    rendered: dict[str, str] = {}
    artifacts: dict[str, str] = {}
    for stage_name in ("prep", "execute_creative", "critique_creative", "revise_creative"):
        stage_dir = plan_dir / stage_name
        stage_dir.mkdir()
        ctx = dataclasses.replace(
            ctx,
            state={**state, "_creative_artifacts": artifacts},
            inputs={"_pipeline": "creative"},
        )
        assert ctx.inputs["_pipeline"] == "creative"
        rendered[stage_name] = render_prompt(
            stage_name,
            ctx,
            params={
                "stage": stage_name,
                "form": "poem",
                "primary_criterion": "most surprising exact image",
                "previous_artifacts": artifacts,
            },
        )
        artifact = stage_dir / "v1.md"
        artifact.write_text(rendered[stage_name], encoding="utf-8")
        artifacts[stage_name] = str(artifact)

    combined = "\n\n".join(rendered.values())
    assert "Poem" in combined
    assert "opening_image" in combined
    assert "most surprising exact image" in combined
    assert "joke-mode" not in rendered["prep"]
    assert "comic" not in rendered["prep"].lower()
    assert "laugh" not in rendered["prep"].lower()
    assert "button" not in rendered["prep"].lower()
    for forbidden in ("plan_versions", "finalize.json", "gate.json"):
        assert forbidden not in combined


def test_joke_specific_prompts_render_from_fresh_state_without_planning_artifacts(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan.pipelines.creative.prompts import render_prompt
    from arnold.pipelines.megaplan._pipeline.types import StepContext

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    state: dict[str, Any] = {
        "idea": "write a short scene about a haunted vending machine",
        "config": {
            "mode": "creative",
            "form": "joke",
            "project_dir": str(project_dir),
            "primary_criterion": "weirdest coherent",
            "robustness": "standard",
        },
        "iteration": 1,
    }
    ctx = StepContext(
        plan_dir=plan_dir,
        state=state,
        profile=None,
        mode="creative",
        inputs={"_pipeline": "creative"},
    )

    rendered: dict[str, str] = {}
    artifacts: dict[str, str] = {}
    for prompt_key in (
        "prep:joke",
        "execute_creative:joke",
        "critique_creative:joke",
        "revise_creative:joke",
    ):
        ctx = dataclasses.replace(
            ctx,
            state={**state, "_creative_artifacts": artifacts},
            inputs={"_pipeline": "creative"},
        )
        rendered[prompt_key] = render_prompt(
            prompt_key,
            ctx,
            params={
                "stage": prompt_key.split(":", 1)[0],
                "form": "joke",
                "primary_criterion": "weirdest coherent",
                "previous_artifacts": artifacts,
            },
        )
        artifact = plan_dir / f"{prompt_key.replace(':', '_')}.md"
        artifact.write_text(rendered[prompt_key], encoding="utf-8")
        artifacts[prompt_key] = str(artifact)

    combined = "\n\n".join(rendered.values())
    assert "Joke-form emphasis" in combined
    assert "Joke-form critique pressure" in combined
    assert "Joke-form revision pressure" in combined
    assert "weirdest coherent" in combined
    for forbidden in ("plan_versions", "finalize.json", "gate.json"):
        assert forbidden not in combined


# ── (b) Provocations sidecar + stance validation are wired in ────────────


def test_creative_critique_prompt_module_wires_provocations_and_directors_notes() -> None:
    """``critique_creative`` must surface the provocations sidecar +
    directors_notes.json reads that the legacy --mode creative path
    relied on; the relocated module preserves the wiring."""

    from arnold.pipelines.megaplan.pipelines.creative.prompts import critique_creative as cc

    # Provocations: the canonical selector is imported.
    from arnold.pipelines.megaplan.forms.provocations import select_active_checks

    assert cc.select_active_checks is select_active_checks
    # Directors notes sidecar: the module body references the canonical
    # filename so the runtime layer can read/write it next to the prompt.
    src = Path(cc.__file__).read_text(encoding="utf-8")
    assert "directors_notes.json" in src, (
        "critique_creative.py must reference directors_notes.json sidecar"
    )


def test_creative_execute_prompt_module_includes_stance_contract() -> None:
    """``execute_creative`` must emit structured ``stance`` instructions
    in its rendered prompt so the worker returns stance fields that
    downstream stance-validation can enforce."""

    from arnold.pipelines.megaplan.pipelines.creative.prompts import execute_creative as ec

    src = Path(ec.__file__).read_text(encoding="utf-8")
    # The prompt body documents the stance contract: fields,
    # voice hint, and the structured-output requirement.
    assert "stance" in src.lower()
    assert "challenge_engaged" in src
    assert "angle_taken" in src
    assert "what_changed" in src


def test_creative_pipeline_validate_stance_remains_callable() -> None:
    """``megaplan.forms.stance.validate_stance`` — the runtime
    validator — is still importable from its canonical location after
    the prompt relocation (the forms package is NOT moved per T1's
    audit; 25+ non-creative consumers depend on it)."""

    from arnold.pipelines.megaplan.forms.stance import validate_stance

    assert callable(validate_stance)


# ── (c) Unknown form raises CliError('invalid_args') ─────────────────────


def test_creative_pipeline_unknown_form_raises_cli_error() -> None:
    from arnold.pipelines.megaplan.pipelines.creative import build_pipeline
    from arnold.pipelines.megaplan.types import CliError

    with pytest.raises(CliError) as excinfo:
        build_pipeline(form="not-a-real-form-xyz")
    err = excinfo.value
    # CliError carries a structured code; assert it's the invalid_args
    # contract the init handler also uses for form rejection.
    assert getattr(err, "code", None) == "invalid_args" or err.args[0] == "invalid_args"
    msg = str(err)
    assert "not-a-real-form-xyz" in msg
    # The error advertises the canonical registry's allowed values.
    from arnold.pipelines.megaplan.forms import available_form_ids

    for form_id in available_form_ids():
        assert form_id in msg, (
            f"CliError should list available form {form_id!r}; got {msg!r}"
        )


# ── (d) --primary-criterion flows into build_pipeline ────────────────────


def test_creative_pipeline_primary_criterion_threads_through_all_stages() -> None:
    from arnold.pipelines.megaplan.pipelines.creative import build_pipeline

    pipeline = build_pipeline(form="joke", primary_criterion="weirdest coherent")
    for name, stage in pipeline.stages.items():
        assert getattr(stage.step, "primary_criterion", None) == "weirdest coherent", (
            f"stage {name!r} did not receive primary_criterion"
        )


def test_creative_pipeline_primary_criterion_default_none() -> None:
    from arnold.pipelines.megaplan.pipelines.creative import build_pipeline

    pipeline = build_pipeline(form="joke")
    for name, stage in pipeline.stages.items():
        assert getattr(stage.step, "primary_criterion", None) is None, (
            f"stage {name!r} primary_criterion default should be None"
        )


# ── cli_run integration: drive the creative pipeline through megaplan run ─


def test_creative_pipeline_runs_through_cli_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end smoke via ``cli_run`` — drives the creative pipeline
    to its terminal ``finalize`` stage with the default ``form='joke'``."""

    from arnold.pipelines.megaplan._pipeline import preflight as preflight_module
    from arnold.pipelines.megaplan._pipeline.run_cli import cli_run

    monkeypatch.setattr(
        preflight_module, "preflight_or_raise", lambda *a, **kw: None
    )

    plan_dir = tmp_path / "creative-cli-run"
    plan_dir.mkdir(parents=True, exist_ok=True)
    args = _make_run_args(pipeline_name="creative", plan_dir=plan_dir)
    rc = cli_run(args)
    assert rc == 0, f"default cli_run('creative') returned non-zero exit code {rc}"
    # Each stage wrote its rendered artifact and prompt snapshot.
    for stage_name in (
        "prep",
        "execute_creative",
        "critique_creative",
        "revise_creative",
        "finalize",
    ):
        assert (plan_dir / stage_name / "v1.md").exists(), (
            f"missing artifact for stage {stage_name!r}"
        )
        assert (plan_dir / stage_name / "prompt_v1.md").exists(), (
            f"missing rendered prompt for stage {stage_name!r}"
        )

    prep_prompt = (plan_dir / "prep" / "prompt_v1.md").read_text()
    execute_prompt = (plan_dir / "execute_creative" / "prompt_v1.md").read_text()
    critique_prompt = (plan_dir / "critique_creative" / "prompt_v1.md").read_text()
    revise_prompt = (plan_dir / "revise_creative" / "prompt_v1.md").read_text()
    assert "Prepare a concise scene-writing brief for the joke-mode task" in prep_prompt
    assert "Joke-form emphasis" in execute_prompt
    assert "Joke-form critique pressure" in critique_prompt
    assert "Joke-form revision pressure" in revise_prompt
    for prompt in (execute_prompt, critique_prompt, revise_prompt):
        assert "finalize.json" not in prompt
        assert "gate.json" not in prompt
        assert "plan_versions" not in prompt
    assert "## prep" in execute_prompt
    assert "## execute_creative" in critique_prompt
    assert "## critique_creative" in revise_prompt


def test_creative_pipeline_cli_run_threads_form_and_primary_criterion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold.pipelines.megaplan._pipeline import preflight as preflight_module
    from arnold.pipelines.megaplan._pipeline.run_cli import cli_run

    monkeypatch.setattr(
        preflight_module, "preflight_or_raise", lambda *a, **kw: None
    )

    plan_dir = tmp_path / "creative-poem-cli-run"
    plan_dir.mkdir(parents=True, exist_ok=True)
    args = _make_run_args(
        pipeline_name="creative",
        plan_dir=plan_dir,
        form="poem",
        primary_criterion="most surprising exact image",
    )
    rc = cli_run(args)
    assert rc == 0
    state = json.loads((plan_dir / "state.json").read_text())
    assert state["_pipeline_name"] == "creative"
    assert state["config"]["form"] == "poem"
    assert state["config"]["primary_criterion"] == "most surprising exact image"
    assert set(state["_creative_artifacts"]) == {
        "prep",
        "execute_creative",
        "critique_creative",
        "revise_creative",
        "finalize",
    }
    assert (plan_dir / "execute_creative" / "v1.md").exists()
    rendered = (plan_dir / "execute_creative" / "v1.md").read_text()
    assert "most surprising exact image" in rendered
    prompt = (plan_dir / "execute_creative" / "prompt_v1.md").read_text()
    assert "most surprising exact image" in prompt
    assert "finalize.json" not in prompt
    assert "gate.json" not in prompt


def test_creative_native_runtime_persists_artifacts_and_resumes(
    tmp_path: Path,
) -> None:
    from arnold.pipeline.native import run_native_pipeline
    from arnold.pipelines.megaplan.pipelines.creative import build_pipeline

    plan_dir = tmp_path / "creative-native-resume"
    pipeline = build_pipeline(
        form="poem",
        primary_criterion="most surprising exact image",
    )
    initial_state: dict[str, Any] = {
        "idea": "write a small poem about a blue door",
        "config": {
            "mode": "creative",
            "form": "poem",
            "project_dir": str(tmp_path),
            "primary_criterion": "most surprising exact image",
        },
    }

    suspended = run_native_pipeline(
        pipeline.native_program,
        artifact_root=plan_dir,
        initial_state=initial_state,
        max_phases=2,
    )
    assert suspended.suspended is True
    assert (plan_dir / "resume_cursor.json").exists()
    assert (plan_dir / "prep" / "v1.md").exists()
    assert (plan_dir / "execute_creative" / "v1.md").exists()
    assert not (plan_dir / "critique_creative" / "v1.md").exists()

    resumed = run_native_pipeline(
        pipeline.native_program,
        artifact_root=plan_dir,
        initial_state={},
        resume=True,
    )

    assert resumed.suspended is False
    assert resumed.state["config"]["form"] == "poem"
    assert (
        resumed.state["config"]["primary_criterion"]
        == "most surprising exact image"
    )
    assert set(resumed.state["_creative_artifacts"]) == {
        "prep",
        "execute_creative",
        "critique_creative",
        "revise_creative",
        "finalize",
    }
    assert (plan_dir / "critique_creative" / "v1.md").exists()
    assert (plan_dir / "revise_creative" / "v1.md").exists()
    final_artifact = plan_dir / "finalize" / "v1.md"
    assert final_artifact.exists()
    assert "most surprising exact image" in final_artifact.read_text()


def test_creative_run_builder_receives_cli_parameters() -> None:
    from arnold.pipelines.megaplan._pipeline.run_cli import _build_pipeline_for_run

    args = _make_run_args(
        pipeline_name="creative",
        plan_dir=Path("unused"),
        form="poem",
        primary_criterion="most surprising exact image",
    )
    pipeline = _build_pipeline_for_run(args)
    for stage in pipeline.stages.values():
        assert getattr(stage.step, "form", None) == "poem"
        assert (
            getattr(stage.step, "primary_criterion", None)
            == "most surprising exact image"
        )
