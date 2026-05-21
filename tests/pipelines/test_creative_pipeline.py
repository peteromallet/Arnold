"""T9 — tests for the ``creative`` pipeline (0.23 sprint).

Exercises the new first-class ``creative`` pipeline through the same
``megaplan run`` code path the Step 19 real-model smoke uses:
:func:`megaplan._pipeline.run_cli.cli_run` →
:func:`megaplan._pipeline.run_cli._run_pipeline`.

Required assertions (per the batch sense check, SC9):

(a) Form dispatch wires joke-specific prompts when ``--form joke`` —
    the stage shells carry ``prompt_key=f"<base>:{form}"`` and the
    ``creative/<base>:<form>`` slots are registered against the
    PromptRegistry. ``--form poem`` routes to the poem slots instead.
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
import json
from pathlib import Path
from typing import Any

import pytest


def _make_run_args(
    *,
    pipeline_name: str,
    plan_dir: Path,
    state: dict[str, Any] | None = None,
    mode: str | None = None,
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
    )


# ── (a) Form dispatch: joke vs poem wires the right ``prompt_key`` slots ─


def test_creative_form_joke_dispatches_joke_prompt_keys() -> None:
    from megaplan.pipelines.creative import build_pipeline

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


def test_creative_form_poem_dispatches_poem_prompt_keys() -> None:
    from megaplan.pipelines.creative import build_pipeline

    pipeline = build_pipeline(form="poem")
    stage_prompt_keys = {
        name: stage.step.prompt_key for name, stage in pipeline.stages.items()
    }
    assert stage_prompt_keys["prep"] == "prep:poem"
    assert stage_prompt_keys["execute_creative"] == "execute_creative:poem"
    assert stage_prompt_keys["critique_creative"] == "critique_creative:poem"
    assert stage_prompt_keys["revise_creative"] == "revise_creative:poem"


def test_creative_pipeline_registers_form_specialised_prompt_slots() -> None:
    """The relocated creative+joke prompt modules register their
    renderers under both ``creative/<key>:joke`` (rule-1 lookup with
    explicit mode) AND ``creative/<key>:joke`` as a literal key (rule-2
    lookup; the creative pipeline's stage shells carry the form baked
    into ``prompt_key`` as ``"<key>:<form>"``)."""

    # Force registration by importing the creative package.
    import megaplan.pipelines.creative  # noqa: F401
    from megaplan._pipeline.prompts import registered_keys

    keys = set(registered_keys())
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


# ── (b) Provocations sidecar + stance validation are wired in ────────────


def test_creative_critique_prompt_module_wires_provocations_and_directors_notes() -> None:
    """``critique_creative`` must surface the provocations sidecar +
    directors_notes.json reads that the legacy --mode creative path
    relied on; the relocated module preserves the wiring."""

    from megaplan.pipelines.creative.prompts import critique_creative as cc

    # Provocations: the canonical selector is imported.
    from megaplan.forms.provocations import select_active_checks

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

    from megaplan.pipelines.creative.prompts import execute_creative as ec

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

    from megaplan.forms.stance import validate_stance

    assert callable(validate_stance)


# ── (c) Unknown form raises CliError('invalid_args') ─────────────────────


def test_creative_pipeline_unknown_form_raises_cli_error() -> None:
    from megaplan.pipelines.creative import build_pipeline
    from megaplan.types import CliError

    with pytest.raises(CliError) as excinfo:
        build_pipeline(form="not-a-real-form-xyz")
    err = excinfo.value
    # CliError carries a structured code; assert it's the invalid_args
    # contract the init handler also uses for form rejection.
    assert getattr(err, "code", None) == "invalid_args" or err.args[0] == "invalid_args"
    msg = str(err)
    assert "not-a-real-form-xyz" in msg
    # The error advertises the canonical registry's allowed values.
    from megaplan.forms import available_form_ids

    for form_id in available_form_ids():
        assert form_id in msg, (
            f"CliError should list available form {form_id!r}; got {msg!r}"
        )


# ── (d) --primary-criterion flows into build_pipeline ────────────────────


def test_creative_pipeline_primary_criterion_threads_through_all_stages() -> None:
    from megaplan.pipelines.creative import build_pipeline

    pipeline = build_pipeline(form="joke", primary_criterion="weirdest coherent")
    for name, stage in pipeline.stages.items():
        assert getattr(stage.step, "primary_criterion", None) == "weirdest coherent", (
            f"stage {name!r} did not receive primary_criterion"
        )


def test_creative_pipeline_primary_criterion_default_none() -> None:
    from megaplan.pipelines.creative import build_pipeline

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
    to its terminal ``finalize`` stage with the registry-default
    ``form='joke'`` (registry discovery invokes ``build_pipeline()``
    with no kwargs)."""

    from megaplan._pipeline import preflight as preflight_module
    from megaplan._pipeline.run_cli import cli_run

    monkeypatch.setattr(
        preflight_module, "preflight_or_raise", lambda *a, **kw: None
    )

    plan_dir = tmp_path / "creative-cli-run"
    plan_dir.mkdir(parents=True, exist_ok=True)
    args = _make_run_args(pipeline_name="creative", plan_dir=plan_dir)
    rc = cli_run(args)
    assert rc == 0, f"cli_run('creative') returned non-zero exit code {rc}"
    # Each placeholder stage wrote its v1.md artifact.
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
