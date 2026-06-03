"""W7 — pipelines check static graph validator tests (T13).

Validator scope: Edge.target real-stage-or-halt, no 'halt' as edge LABEL
(except the conventional terminal pair), every decision edge has a valid
label matching the stage's decision vocabulary, and reachability from
entry. NO Port resolution (M2).  M3b: decision edges use kind='decision';
kind='gate' edges are legacy and validated alongside kind='decision'.
"""

from __future__ import annotations

import subprocess
import sys
import os
from argparse import Namespace

from megaplan._pipeline.judge_manifest import (
    EVALUAND_RECORD_CONTENT_TYPE,
    JudgeManifestPort,
    dump_judge_manifest,
    make_judge_manifest,
)
from megaplan._pipeline.judge_manifest_discovery import validate_judge_manifest
from megaplan._pipeline.registry import get_pipeline
from megaplan._pipeline.types import Edge, Pipeline, Stage
from megaplan._pipeline.validator import Diagnostics, validate


class _NoopStep:
    name = "noop"
    kind = "produce"
    prompt_key = None
    slot = None

    @property
    def produces(self) -> tuple:
        return ()

    @property
    def consumes(self) -> tuple:
        return ()

    def run(self, ctx):  # pragma: no cover - never called by static check
        raise RuntimeError("static validator must not dispatch")


def _stage(name: str, *edges: Edge) -> Stage:
    return Stage(name=name, step=_NoopStep(), edges=tuple(edges))


def test_planning_passes_validate() -> None:
    diag = validate(get_pipeline("planning"))
    assert diag.ok, diag.defects


def test_edge_to_nonexistent_stage_is_flagged() -> None:
    pipeline = Pipeline(
        stages={
            "start": _stage("start", Edge(label="go", target="missing")),
        },
        entry="start",
    )
    diag = validate(pipeline)
    assert not diag.ok
    assert any("missing" in d for d in diag.defects)


def test_gate_verdict_with_no_edge_is_flagged() -> None:
    # A gate edge without a recommendation cannot dispatch ⇒ defect.
    pipeline = Pipeline(
        stages={
            "start": _stage(
                "start",
                Edge(label="g", target="halt", kind="gate", recommendation=None),
            ),
        },
        entry="start",
    )
    diag = validate(pipeline)
    assert not diag.ok
    assert any("no recommendation" in d for d in diag.defects)


def test_unreachable_stage_is_flagged() -> None:
    pipeline = Pipeline(
        stages={
            "start": _stage("start", Edge(label="halt", target="halt")),
            "orphan": _stage("orphan", Edge(label="halt", target="halt")),
        },
        entry="start",
    )
    diag = validate(pipeline)
    assert not diag.ok
    assert any("'orphan'" in d and "unreachable" in d for d in diag.defects)


def test_halt_label_is_ok_when_target_is_halt() -> None:
    # The conventional terminal label='halt' target='halt' must NOT be flagged.
    pipeline = Pipeline(
        stages={
            "start": _stage("start", Edge(label="halt", target="halt")),
        },
        entry="start",
    )
    diag = validate(pipeline)
    assert diag.ok, diag.defects


def test_halt_label_with_non_halt_target_is_flagged() -> None:
    pipeline = Pipeline(
        stages={
            "start": _stage("start", Edge(label="halt", target="end")),
            "end": _stage("end", Edge(label="halt", target="halt")),
        },
        entry="start",
    )
    diag = validate(pipeline)
    assert not diag.ok
    assert any("reserved label 'halt'" in d for d in diag.defects)


def test_diagnostics_ok_property() -> None:
    assert Diagnostics(defects=[]).ok is True
    assert Diagnostics(defects=["x"]).ok is False


def _run_cli(*argv: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "megaplan", *argv],
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_pipelines_check_planning_exits_zero() -> None:
    result = _run_cli("pipelines", "check", "planning")
    assert result.returncode == 0, result.stderr
    assert "planning" in result.stdout


def test_cli_pipelines_check_no_name_exits_zero() -> None:
    result = _run_cli("pipelines", "check")
    assert result.returncode == 0


def test_cli_pipelines_check_judge_manifest_does_not_import_implementation(
    tmp_path,
) -> None:
    user_dir = tmp_path / ".megaplan" / "pipelines"
    user_dir.mkdir(parents=True)
    (user_dir / "exploding_judge.py").write_text(
        "raise RuntimeError('implementation import must not run')\n",
        encoding="utf-8",
    )
    manifest = make_judge_manifest(
        name="exploding-judge",
        implementation="exploding_judge:Judge",
        arnold_api_version="2026-05-31",
        model_identity="model:gpt-5.4",
        rubric_body={"rubric": "score deterministically"},
        consumes=(JudgeManifestPort("candidate", "text/markdown"),),
        produces=(JudgeManifestPort("evaluand", EVALUAND_RECORD_CONTENT_TYPE),),
        source_hash="sha256:deadbeef",
    )
    dump_judge_manifest(manifest, user_dir / "exploding-judge.judge.json")

    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    result = _run_cli("pipelines", "check", "exploding-judge", env=env)

    assert result.returncode == 0, result.stderr
    assert "exploding-judge" in result.stdout
    assert "implementation import must not run" not in result.stderr


def test_cli_pipelines_check_falls_back_to_pipeline_registry() -> None:
    result = _run_cli("pipelines", "check", "planning")
    assert result.returncode == 0, result.stderr
    assert "planning" in result.stdout


def test_m5_judge_manifest_shape_validates() -> None:
    manifest = make_judge_manifest(
        name="m5-wrapper-eval",
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
        model_identity="model:gpt-5.4",
        rubric_body={"rubric": "return an EvaluandRecord judgment"},
        consumes=(JudgeManifestPort("candidate", "text/markdown"),),
        produces=(JudgeManifestPort("evaluand", EVALUAND_RECORD_CONTENT_TYPE),),
        source_hash="sha256:cafebabe",
    )

    diag = validate_judge_manifest(manifest, path="m5-wrapper-eval.judge.json")

    assert diag.ok, diag.defects


def test_cli_pipelines_check_registered_m5_manifest_does_not_import_wrapper(
    monkeypatch,
) -> None:
    from megaplan.cli import _handle_pipelines

    def blocked_import(name, package=None):
        if name == "megaplan._pipeline.eval_judge_wrapper":
            raise AssertionError("pipelines check imported the eval judge wrapper")
        return real_import_module(name, package=package)

    import importlib

    real_import_module = importlib.import_module
    monkeypatch.setattr(importlib, "import_module", blocked_import)

    rc = _handle_pipelines(
        os.getcwd(),
        Namespace(pipelines_action="check", pipeline_name="m5-wrapper-eval"),
    )

    assert rc == 0
