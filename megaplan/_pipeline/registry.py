"""Pipeline registry — how to feed in a new sequence by name.

A new workflow type is three lines of registration code:

    from megaplan._pipeline.registry import register_pipeline
    from megaplan._pipeline.types import Pipeline, Stage, Edge

    def my_three_critique_loop() -> Pipeline:
        return Pipeline(stages={...}, entry="critique")

    register_pipeline("three-critique", my_three_critique_loop)

Then invoke it via :func:`run_pipeline_by_name` or the
``megaplan run-pipeline three-critique --fixture path/to/doc.md``
CLI subcommand (see :mod:`megaplan._pipeline.run_cli`).

Built-in pipelines registered at module import:

- ``planning``: the production planning Pipeline
  (``compile_runnable_pipeline()``).
- ``doc-critique``: the 3× critique→revise loop.
- ``judges``: the fan-out judges demo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from megaplan._pipeline.types import Pipeline


PipelineBuilder = Callable[[], Pipeline]


@dataclass
class PipelineRegistry:
    """Map names → builder callables → Pipeline values.

    Builders return a Pipeline; the registry calls them on demand so
    a registered pipeline isn't materialised until requested. This
    keeps import cost flat regardless of how many pipelines exist.
    """

    builders: dict[str, PipelineBuilder] = field(default_factory=dict)
    descriptions: dict[str, str] = field(default_factory=dict)

    def register(
        self,
        name: str,
        builder: PipelineBuilder,
        *,
        description: str = "",
    ) -> None:
        if name in self.builders:
            raise ValueError(f"pipeline {name!r} already registered")
        self.builders[name] = builder
        if description:
            self.descriptions[name] = description

    def get(self, name: str) -> Pipeline:
        if name not in self.builders:
            raise KeyError(
                f"no pipeline named {name!r}; available: {sorted(self.builders)}"
            )
        return self.builders[name]()

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self.builders))

    def describe(self, name: str) -> str:
        return self.descriptions.get(name, "")


_GLOBAL_REGISTRY = PipelineRegistry()


def register_pipeline(
    name: str,
    builder: PipelineBuilder,
    *,
    description: str = "",
) -> None:
    _GLOBAL_REGISTRY.register(name, builder, description=description)


def get_pipeline(name: str) -> Pipeline:
    return _GLOBAL_REGISTRY.get(name)


def registered_pipelines() -> tuple[str, ...]:
    return _GLOBAL_REGISTRY.names()


def describe_pipeline(name: str) -> str:
    return _GLOBAL_REGISTRY.describe(name)


def run_pipeline_by_name(
    name: str,
    *,
    plan_dir: Path,
    artifact_root: Path | None = None,
    profile: Any = None,
    mode: str = "code",
    inputs: Mapping[str, Path] | None = None,
    state: Mapping[str, Any] | None = None,
    policy: Any = None,
) -> dict[str, Any]:
    """Look up a registered pipeline and run it under the executor.

    When ``policy`` is set (a :class:`RuntimePolicy` instance), the
    walk uses ``run_pipeline_with_policy`` (stall + cost + escalate
    guarded). Otherwise the bare executor is used. Returns the
    executor's result dict (``{state, final_stage, halt_reason?}``).
    """

    from megaplan._pipeline.executor import (
        run_pipeline,
        run_pipeline_with_policy,
    )
    from megaplan._pipeline.types import StepContext

    pipeline = get_pipeline(name)
    artifact_root = Path(artifact_root or plan_dir)
    ctx = StepContext(
        plan_dir=Path(plan_dir),
        state=dict(state or {}),
        profile=profile,
        mode=mode,
        inputs=dict(inputs or {}),
        budget=None,
    )
    if policy is None:
        return run_pipeline(pipeline, ctx, artifact_root=artifact_root)
    return run_pipeline_with_policy(
        pipeline, ctx, artifact_root=artifact_root, policy=policy,
    )


# ---------------------------------------------------------------------------
# Built-in pipelines registered at import time.
# ---------------------------------------------------------------------------


def _planning_builder() -> Pipeline:
    from megaplan._pipeline.planning import compile_runnable_pipeline
    return compile_runnable_pipeline()


def _doc_critique_builder() -> Pipeline:
    from megaplan._pipeline.demos.doc_critique import build_pipeline
    return build_pipeline()


def _judges_builder() -> Pipeline:
    from megaplan._pipeline.demo_judges import build_pipeline
    return build_pipeline()


register_pipeline(
    "planning", _planning_builder,
    description="Production planning — runnable shape "
                "(prep→plan→critique→gate→…→review).",
)
register_pipeline(
    "doc-critique", _doc_critique_builder,
    description="3× critique→revise loop on a markdown doc.",
)
register_pipeline(
    "judges", _judges_builder,
    description="Fan-out judges + synthesis demo.",
)
