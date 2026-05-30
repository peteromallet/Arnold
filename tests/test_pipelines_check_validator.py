"""W7 — pipelines check static graph validator tests (T13).

Validator scope: Edge.target real-stage-or-halt, no 'halt' as edge LABEL
(except the conventional terminal pair), every gate edge has a valid
GateRecommendation, and reachability from entry. NO Port resolution (M2).
"""

from __future__ import annotations

import subprocess
import sys

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


def _run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "megaplan", *argv],
        capture_output=True,
        text=True,
    )


def test_cli_pipelines_check_planning_exits_zero() -> None:
    result = _run_cli("pipelines", "check", "planning")
    assert result.returncode == 0, result.stderr
    assert "planning" in result.stdout


def test_cli_pipelines_check_no_name_exits_zero() -> None:
    result = _run_cli("pipelines", "check")
    assert result.returncode == 0
