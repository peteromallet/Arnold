"""Compatibility projection for the canonical Megaplan workflow.

This module is intentionally narrow: it projects the authored workflow DSL
pipeline into the neutral Arnold graph shell and attaches a NativeProgram.
The authored source in ``workflows/planning.py`` remains the canonical DSL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import argparse
from typing import Any, Mapping
from pathlib import Path

from arnold.manifest.manifests import WorkflowManifest
from arnold.pipeline.native.ir import NativeInstruction, NativePhase, NativeProgram
from arnold.pipeline.types import Edge, Pipeline as NeutralPipeline, Stage
from arnold.pipeline.types import StepContext, StepResult
from arnold.workflow.compiler import compile_pipeline as compile_workflow_manifest
from arnold.workflow.dsl import Pipeline as DslPipeline, Step as DslStep


@dataclass(frozen=True)
class CompatibilityPipelineShell(NeutralPipeline):
    """Neutral pipeline shell that preserves workflow-manifest identity."""

    manifest: WorkflowManifest | None = None
    authored_pipeline: DslPipeline | None = field(default=None, repr=False, compare=False)

    @property
    def id(self) -> str:
        return self.manifest.id if self.manifest is not None else ""

    @property
    def version(self) -> str:
        return self.manifest.version if self.manifest is not None else ""

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self.manifest.metadata if self.manifest is not None else {}

    @property
    def nodes(self) -> tuple[Any, ...]:
        return self.manifest.nodes if self.manifest is not None else ()

    @property
    def edges(self) -> tuple[Any, ...]:
        return self.manifest.edges if self.manifest is not None else ()

    @property
    def capabilities(self) -> tuple[Any, ...]:
        if self.authored_pipeline is not None:
            return self.authored_pipeline.capabilities
        return ()

    @property
    def steps(self) -> tuple[Any, ...]:
        return self.authored_pipeline.steps if self.authored_pipeline is not None else ()

    @property
    def routes(self) -> tuple[Any, ...]:
        return self.authored_pipeline.routes if self.authored_pipeline is not None else ()

    @property
    def policy(self) -> Any:
        return self.authored_pipeline.policy if self.authored_pipeline is not None else None

    @property
    def source_span(self) -> Any:
        return self.authored_pipeline.source_span if self.authored_pipeline is not None else None

    @property
    def manifest_hash(self) -> str:
        return self.manifest.manifest_hash if self.manifest is not None else ""

    @property
    def topology_hash(self) -> str:
        return self.manifest.topology_hash if self.manifest is not None else ""

    def to_json(self) -> dict[str, Any]:
        if self.manifest is None:
            return {}
        return self.manifest.to_json()


@dataclass(frozen=True)
class _CompatibilityStep:
    """Neutral step adapter carrying authored Megaplan handler metadata."""

    name: str
    kind: str
    handler_ref: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    default_next: str = "halt"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(next=self.default_next)


def build_compatibility_shell(pipeline: DslPipeline) -> CompatibilityPipelineShell:
    """Project an authored DSL pipeline to a native-backed neutral shell."""

    manifest = compile_workflow_manifest(pipeline)
    native_program = _native_program_from_dsl(pipeline)
    stages = _stages_from_dsl(pipeline)
    return CompatibilityPipelineShell(
        stages=stages,
        entry=pipeline.entry,
        binding_map=None,
        resource_bundles=(),
        native_program=native_program,
        manifest=manifest,
        authored_pipeline=pipeline,
    )


def _stages_from_dsl(pipeline: DslPipeline) -> dict[str, Stage]:
    routes_by_source: dict[str, list[Any]] = {}
    for route in pipeline.routes:
        routes_by_source.setdefault(route.source, []).append(route)

    stages: dict[str, Stage] = {}
    for step in pipeline.steps:
        outgoing = tuple(routes_by_source.get(step.id, ()))
        default_next = outgoing[0].label if outgoing else "halt"
        edges = tuple(Edge(label=route.label, target=route.target) for route in outgoing)
        labels = frozenset(route.label for route in outgoing)
        handler_ref = _handler_ref(step)
        stages[step.id] = Stage(
            name=step.id,
            step=_CompatibilityStep(
                name=step.id,
                kind=step.kind,
                handler_ref=handler_ref,
                metadata=dict(step.metadata),
                default_next=default_next,
            ),
            edges=edges,
            decision_vocabulary=labels if len(labels) > 1 else frozenset(),
        )
    return stages


def _native_program_from_dsl(pipeline: DslPipeline) -> NativeProgram:
    routes_by_source: dict[str, list[Any]] = {}
    for route in pipeline.routes:
        routes_by_source.setdefault(route.source, []).append(route)
    step_pc = {step.id: index for index, step in enumerate(pipeline.steps)}

    phases: list[NativePhase] = []
    instructions: list[NativeInstruction] = []
    for pc, step in enumerate(pipeline.steps):
        func = _native_phase_func(step)
        phase = NativePhase(name=step.id, func=func)
        phases.append(phase)
        outgoing = routes_by_source.get(step.id, [])
        next_pc = _default_next_pc(outgoing, step_pc)
        instructions.append(
            NativeInstruction(
                pc=pc,
                op="phase",
                name=step.id,
                func=func,
                next_pc=next_pc,
            )
        )

    return NativeProgram(
        name=pipeline.id,
        instructions=tuple(instructions),
        phases=tuple(phases),
        description=(
            "Substrate proof only: compatibility projection from authored "
            "Megaplan workflow DSL to neutral native shell."
        ),
    )


def _native_phase_func(step: DslStep) -> Any:
    handler_ref = _handler_ref(step)
    metadata = dict(step.metadata)
    default_next = "halt"
    phase_name = step.id

    def _run(ctx: object) -> dict[str, Any]:
        if isinstance(ctx, Mapping) and ctx.get("__megaplan_auto_phase__") is True:
            return _run_megaplan_native_phase(
                phase_name,
                ctx,
                handler_ref=handler_ref,
            )
        return {}

    _run.__name__ = f"_megaplan_{step.id}_compat_phase"
    _run.__qualname__ = _run.__name__
    _run.__native_phase_name__ = step.id
    _run.__handler_ref__ = handler_ref
    _run.__dsl_step_kind__ = step.kind
    _run.__dsl_step_metadata__ = metadata
    _run.__default_next__ = default_next
    return _run


def _run_megaplan_native_phase(
    phase_name: str,
    ctx: Mapping[str, Any],
    *,
    handler_ref: str | None,
) -> dict[str, Any]:
    """Execute one canonical Megaplan phase through the native phase function."""

    del handler_ref
    root = _ctx_path(ctx.get("cwd")) or Path.cwd()
    plan = ctx.get("plan")
    if not isinstance(plan, str) or not plan:
        return {"exit_code": 1, "stdout": "", "stderr": "missing --plan"}
    argv = ctx.get("argv")
    args = _namespace_from_argv(
        phase_name,
        plan=plan,
        argv=argv if isinstance(argv, list) else [],
    )
    try:
        from arnold_pipelines.megaplan.cli import COMMAND_HANDLERS
        from arnold_pipelines.megaplan._core.io import json_dump
        from arnold_pipelines.megaplan.types import CliError

        handler = COMMAND_HANDLERS.get(phase_name)
        if handler is None:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"native phase {phase_name!r} is unsupported",
            }
        response = handler(root, args)
        return {"exit_code": 0, "stdout": json_dump(response), "stderr": ""}
    except CliError as error:
        payload: dict[str, Any] = {
            "success": False,
            "error": error.code,
            "message": error.message,
        }
        if error.extra:
            payload["details"] = dict(error.extra)
        import json

        return {
            "exit_code": error.exit_code,
            "stdout": "",
            "stderr": json.dumps(payload),
        }
    except Exception as error:  # noqa: BLE001 - preserve CLI-shaped failure surface.
        return {
            "exit_code": 1,
            "stdout": "",
            "stderr": f"{type(error).__name__}: {error}",
        }


def _ctx_path(value: Any) -> Path | None:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value:
        return Path(value)
    return None


def _namespace_from_argv(
    phase_name: str,
    *,
    plan: str,
    argv: list[Any],
) -> argparse.Namespace:
    args = argparse.Namespace(
        plan=plan,
        fresh=False,
        persist=False,
        ephemeral=False,
        confirm_destructive=False,
        user_approved=False,
        retry_blocked_tasks=False,
        confirm_self_review=False,
        batch=None,
        agent=None,
        hermes=None,
        phase_model=[],
        tier_models=None,
        max_execute_tier=None,
        profile=None,
        vendor=None,
        deepseek_provider=None,
        critic=None,
        progress_emitter=None,
        prep_direction=None,
    )
    index = 1 if argv and str(argv[0]) == phase_name else 0
    while index < len(argv):
        token = str(argv[index])
        if token == "--plan" and index + 1 < len(argv):
            args.plan = str(argv[index + 1])
            index += 2
            continue
        if token == "--fresh":
            args.fresh = True
        elif token == "--persist":
            args.persist = True
        elif token == "--ephemeral":
            args.ephemeral = True
        elif token == "--confirm-destructive":
            args.confirm_destructive = True
        elif token == "--user-approved":
            args.user_approved = True
        elif token == "--retry-blocked-tasks":
            args.retry_blocked_tasks = True
        elif token == "--confirm-self-review":
            args.confirm_self_review = True
        elif token == "--batch" and index + 1 < len(argv):
            try:
                args.batch = int(str(argv[index + 1]))
            except ValueError:
                args.batch = None
            index += 1
        elif token == "--agent" and index + 1 < len(argv):
            args.agent = str(argv[index + 1])
            index += 1
        elif token == "--hermes" and index + 1 < len(argv):
            args.hermes = str(argv[index + 1])
            index += 1
        elif token == "--phase-model" and index + 1 < len(argv):
            args.phase_model.append(str(argv[index + 1]))
            index += 1
        elif token == "--profile" and index + 1 < len(argv):
            args.profile = str(argv[index + 1])
            index += 1
        elif token == "--vendor" and index + 1 < len(argv):
            args.vendor = str(argv[index + 1])
            index += 1
        index += 1
    return args


def _default_next_pc(routes: list[Any], step_pc: Mapping[str, int]) -> int | None:
    if not routes:
        return None
    target = routes[0].target
    if target == "halt":
        return None
    return step_pc.get(target)


def _handler_ref(step: DslStep) -> str | None:
    value = step.metadata.get("handler_ref")
    return value if isinstance(value, str) else None


__all__ = ["CompatibilityPipelineShell", "build_compatibility_shell"]
