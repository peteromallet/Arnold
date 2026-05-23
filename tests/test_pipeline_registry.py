"""How a user feeds in a new sequence — the registry + invoke-by-name path.

End-to-end story:

1. Define a Pipeline value in your module (single function returning
   :class:`Pipeline`).
2. Call ``register_pipeline("my-name", builder)`` at import time.
3. Invoke it via ``run_pipeline_by_name("my-name", plan_dir=..., ...)``.

That's it. No subclassing the executor, no CLI surgery — the named
pipeline IS the new sequence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from megaplan._pipeline import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)
from megaplan._pipeline.registry import (
    PipelineRegistry,
    describe_pipeline,
    get_pipeline,
    register_pipeline,
    registered_pipelines,
    run_pipeline_by_name,
)


def test_builtin_pipelines_are_registered() -> None:
    """Three pipelines ship as built-ins."""
    names = registered_pipelines()
    assert "planning" in names
    assert "doc-critique" in names
    assert "judges" in names


def test_each_builtin_has_a_description() -> None:
    for name in registered_pipelines():
        assert describe_pipeline(name), name


def test_get_pipeline_returns_a_real_pipeline() -> None:
    for name in registered_pipelines():
        pipeline = get_pipeline(name)
        assert isinstance(pipeline, Pipeline)


def test_get_unknown_name_raises_with_helpful_message() -> None:
    with pytest.raises(KeyError, match="no pipeline named"):
        get_pipeline("does-not-exist")


def test_run_doc_critique_by_name_drives_to_done(tmp_path: Path) -> None:
    """The full "feed in a new sequence" story for the 3× critique demo."""
    fixture = tmp_path / "fixture.md"
    fixture.write_text(
        "The original document. The critic reads this. The reviser "
        "appends to it. Three passes total."
    )

    result = run_pipeline_by_name(
        "doc-critique",
        plan_dir=tmp_path,
        inputs={"doc": fixture},
        state={"critique_iter": 0},
        mode="code",
    )

    # 3 critique versions + 2 revise versions + state.json — exactly
    # the artifact set the doc-critique demo produces.
    assert len(list((tmp_path / "critique_versions").glob("critique_v*.json"))) == 3
    assert len(list((tmp_path / "doc_versions").glob("doc_v*.md"))) == 2
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["critique_iter"] == 3


def test_run_judges_by_name_writes_fan_out_artifacts(tmp_path: Path) -> None:
    fixture = tmp_path / "doc.md"
    fixture.write_text("A short document for the judges to score together.")
    artifact_root = tmp_path / "artifacts"

    run_pipeline_by_name(
        "judges",
        plan_dir=artifact_root,
        inputs={"doc": fixture},
        state={},
    )

    assert {
        path.relative_to(artifact_root).as_posix()
        for path in artifact_root.rglob("*")
        if path.is_file()
    } == {
        "judges/judge_clarity/verdict.json",
        "judges/judge_concreteness/verdict.json",
        "judges/judge_brevity/verdict.json",
        "synthesis/synthesis.md",
        "state.json",
    }


# ---------------------------------------------------------------------------
# The user-defined-pipeline story: register at runtime + invoke.
# ---------------------------------------------------------------------------


@dataclass
class _Counter:
    """A trivial Step that counts how many times it ran."""
    name: str = "counter"
    kind: str = "produce"
    prompt_key = None
    slot = None
    target: int = 3

    def run(self, ctx: StepContext) -> StepResult:
        count = int(ctx.state.get("count", 0)) + 1
        out = ctx.plan_dir / f"tick_{count}.json"
        out.write_text(json.dumps({"count": count}))
        next_label = "again" if count < self.target else "done"
        return StepResult(
            outputs={"tick": out},
            next=next_label,
            state_patch={"count": count},
        )


def _build_user_pipeline() -> Pipeline:
    """A user's hand-built Pipeline: count to 5, then halt."""
    counter = _Counter(target=5)
    return Pipeline(
        stages={
            "counter": Stage(
                name="counter", step=counter,
                edges=(
                    Edge(label="again", target="counter"),
                    Edge(label="done", target="halt"),
                ),
            ),
        },
        entry="counter",
    )


def test_user_can_register_and_run_a_custom_pipeline(tmp_path: Path) -> None:
    """User-defined pipelines compose into the registry."""
    register_pipeline(
        "user-counter-test",
        _build_user_pipeline,
        description="A test pipeline that counts to 5.",
    )
    try:
        result = run_pipeline_by_name(
            "user-counter-test",
            plan_dir=tmp_path,
            state={},
        )
        assert result["state"]["count"] == 5
        ticks = sorted(tmp_path.glob("tick_*.json"))
        assert len(ticks) == 5
    finally:
        # Don't leak into other tests — use a private registry below if
        # needed. The global registry forbids re-registration.
        pass


def test_private_registry_does_not_leak_into_global() -> None:
    private = PipelineRegistry()
    private.register("private-only", _build_user_pipeline)
    assert "private-only" in private.names()
    assert "private-only" not in registered_pipelines()


def test_global_registry_forbids_duplicate_names() -> None:
    with pytest.raises(ValueError, match="already registered"):
        register_pipeline("planning", _build_user_pipeline)
