"""T13: tests for the 0.23 `--mode` deprecation handler.

Pinned by T10 + USER DECISION 1/2:

* The init handler must seed ``state['config']`` per the pinned table for
  each of the four deprecated modes (``doc``, ``creative``, ``metaplan``,
  ``joke``), including the ``metaplan→mode='doc'`` and
  ``joke→mode='joke'`` coercions (verbatim — joke is NOT rewritten to
  ``mode='creative'``).
* A verbatim deprecation warning must be printed to stderr that names
  both the deprecated mode and the new ``megaplan run <pipeline>``
  entry point. ``--mode creative`` warnings cite ``--form …``; doc /
  metaplan warnings do NOT.
* ``--mode code`` writes ``mode='code'``, leaves ``pipeline``/``form``
  unset, and emits NO warning.
* Hard ``--form`` contract (USER DECISION 1): ``--form joke`` on doc /
  metaplan is rejected; missing ``--form`` on creative is rejected.

Coverage targets the four T10 step (2)+(3)+(4)+(7) assertions and the
T13 sense-check.
"""

from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

import pytest

import megaplan
from megaplan.types import CliError


def _args(project_dir: Path, **overrides: object) -> Namespace:
    data: dict[str, object] = {
        "plan": None,
        "idea": "mode-deprecation test",
        "name": None,
        "project_dir": str(project_dir),
        "auto_approve": None,
        "robustness": "standard",
        "agent": None,
        "mode": "code",
        "form": None,
        "output": None,
        "primary_criterion": None,
        "from_doc": None,
        "hermes": None,
    }
    data.update(overrides)
    return Namespace(**data)


def _load_state(root: Path, plan_name: str) -> dict:
    return json.loads(
        (megaplan.plans_root(root) / plan_name / "state.json").read_text(encoding="utf-8")
    )


# ── pinned config-write table (T10 step 2+3+7) ────────────────────────────
#
# Mapping from `--mode <X>` to the exact (mode, pipeline, form) triple
# that handle_init must write into `state['config']`. Verbatim from the
# plan Overview pinned table.
def test_mode_doc_writes_pinned_state_config(
    bootstrap_fixture: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """--mode doc → mode='doc', pipeline='doc', form unset."""
    root, project_dir = bootstrap_fixture
    response = megaplan.handle_init(
        root, _args(project_dir, mode="doc", output="docs/out.md")
    )
    state = _load_state(root, response["plan"])

    assert state["config"]["mode"] == "doc"
    assert state["config"]["pipeline"] == "doc"
    assert "form" not in state["config"]


def test_mode_creative_writes_pinned_state_config(
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    """--mode creative --form poem → mode='creative', pipeline='creative', form='poem'."""
    root, project_dir = bootstrap_fixture
    response = megaplan.handle_init(
        root,
        _args(project_dir, mode="creative", form="poem", output="poems/p.md"),
    )
    state = _load_state(root, response["plan"])

    assert state["config"]["mode"] == "creative"
    assert state["config"]["pipeline"] == "creative"
    assert state["config"]["form"] == "poem"


def test_mode_metaplan_coerces_mode_to_doc(
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    """--mode metaplan → mode='doc' (coerced, T10 step 2 — preserve init.py:55-56
    coercion verbatim), pipeline='doc', form unset."""
    root, project_dir = bootstrap_fixture
    response = megaplan.handle_init(
        root, _args(project_dir, mode="metaplan", output="docs/m.md")
    )
    state = _load_state(root, response["plan"])

    assert state["config"]["mode"] == "doc"
    assert state["config"]["pipeline"] == "doc"
    assert "form" not in state["config"]


def test_mode_joke_does_not_rewrite_mode_to_creative(
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    """--mode joke → mode='joke' (NOT rewritten to 'creative'),
    pipeline='creative', form='joke' (implicit). This preserves the
    legacy is_prose_mode/creative_form_id semantics required by USER
    DECISION 2 for the retained --auto-start legacy path."""
    root, project_dir = bootstrap_fixture
    response = megaplan.handle_init(
        root, _args(project_dir, mode="joke", output="jokes/j.md")
    )
    state = _load_state(root, response["plan"])

    assert state["config"]["mode"] == "joke"
    assert state["config"]["pipeline"] == "creative"
    assert state["config"]["form"] == "joke"


# ── verbatim deprecation warning (T10 step 4) ────────────────────────────
def test_mode_doc_emits_verbatim_deprecation_warning_to_stderr(
    bootstrap_fixture: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """T10 step (4) pins the verbatim stderr text. The substring assertions
    below cover the placeholder slots (<X>=doc, <pipeline>=doc) plus the
    fixed 0.23/0.24 NOTE and removal-target text. doc/metaplan warnings
    do NOT cite `--form …` (only creative does)."""
    root, project_dir = bootstrap_fixture
    megaplan.handle_init(
        root, _args(project_dir, mode="doc", output="docs/out.md")
    )
    err = capsys.readouterr().err

    assert "[deprecation] megaplan init --mode doc is deprecated;" in err
    assert 'use "megaplan run doc"' in err
    assert "in 0.23, --auto-start after init --mode still runs the" in err
    assert "LEGACY planning + mode-overlay path" in err
    assert "Full integration ships in 0.24." in err
    assert "--mode will be removed in 0.24." in err
    # doc warning must NOT cite --form …
    assert "--form" not in err


def test_mode_creative_warning_includes_form_suffix(
    bootstrap_fixture: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """`--form …` suffix appears only on creative-pipeline routings so the
    deprecation hint matches the new `megaplan run creative --form <X>`
    surface."""
    root, project_dir = bootstrap_fixture
    megaplan.handle_init(
        root,
        _args(project_dir, mode="creative", form="joke", output="jokes/j.md"),
    )
    err = capsys.readouterr().err

    assert "[deprecation] megaplan init --mode creative is deprecated;" in err
    assert 'use "megaplan run creative --form …"' in err


def test_mode_metaplan_warning_cites_doc_pipeline(
    bootstrap_fixture: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """metaplan redirects to the doc pipeline — the deprecation warning must
    reference `megaplan run doc`, NOT `megaplan run metaplan`."""
    root, project_dir = bootstrap_fixture
    megaplan.handle_init(
        root, _args(project_dir, mode="metaplan", output="docs/m.md")
    )
    err = capsys.readouterr().err

    assert "[deprecation] megaplan init --mode metaplan is deprecated;" in err
    assert 'use "megaplan run doc"' in err


def test_mode_joke_warning_cites_creative_pipeline_with_form(
    bootstrap_fixture: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """joke redirects to creative --form joke — the warning must cite
    `megaplan run creative --form …`."""
    root, project_dir = bootstrap_fixture
    megaplan.handle_init(
        root, _args(project_dir, mode="joke", output="jokes/j.md")
    )
    err = capsys.readouterr().err

    assert "[deprecation] megaplan init --mode joke is deprecated;" in err
    assert 'use "megaplan run creative --form …"' in err


# ── --mode code is clean (T10 step 7) ────────────────────────────────────
def test_mode_code_writes_state_config_without_pipeline_or_form(
    bootstrap_fixture: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """--mode code is the default; it writes mode='code', leaves
    pipeline/form unset, and emits NO deprecation warning to stderr."""
    root, project_dir = bootstrap_fixture
    response = megaplan.handle_init(root, _args(project_dir, mode="code"))
    state = _load_state(root, response["plan"])
    err = capsys.readouterr().err

    assert state["config"]["mode"] == "code"
    assert "pipeline" not in state["config"]
    assert "form" not in state["config"]
    assert "[deprecation]" not in err
    assert err == ""


# ── HARD CONTRACT: --form rules (USER DECISION 1) ────────────────────────
def test_form_joke_rejected_on_mode_doc(
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    """USER DECISION 1: --form joke on --mode doc must raise
    CliError('invalid_args'). The hard contract lives at init.py and is
    NOT deferred."""
    root, project_dir = bootstrap_fixture
    with pytest.raises(CliError) as excinfo:
        megaplan.handle_init(
            root,
            _args(project_dir, mode="doc", form="joke", output="docs/o.md"),
        )
    assert excinfo.value.code == "invalid_args"
    assert "--form" in str(excinfo.value)


def test_form_joke_rejected_on_mode_metaplan(
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    """USER DECISION 1: --form joke on --mode metaplan must raise
    CliError('invalid_args'). metaplan coerces to mode='doc' BEFORE the
    --form check, so the same gate that rejects --form on doc applies."""
    root, project_dir = bootstrap_fixture
    with pytest.raises(CliError) as excinfo:
        megaplan.handle_init(
            root,
            _args(project_dir, mode="metaplan", form="joke", output="docs/o.md"),
        )
    assert excinfo.value.code == "invalid_args"
    assert "--form" in str(excinfo.value)


def test_missing_form_rejected_on_mode_creative(
    bootstrap_fixture: tuple[Path, Path],
) -> None:
    """USER DECISION 1: --mode creative WITHOUT --form must raise
    CliError('invalid_args'). The creative pipeline cannot dispatch
    without a form id."""
    root, project_dir = bootstrap_fixture
    with pytest.raises(CliError) as excinfo:
        megaplan.handle_init(
            root,
            _args(project_dir, mode="creative", form=None, output="creative/o.md"),
        )
    assert excinfo.value.code == "invalid_args"
    assert "--form" in str(excinfo.value)
