"""Graph projection: convert a NativeProgram into a Pipeline.

Walks a compiled :class:`NativeProgram` and builds a :class:`Pipeline`
with stage/edge metadata, guarded-loop ``loop_condition``, and an
optional typed-port binding map derived via ``derive_binding_map()``.

The resulting Pipeline validates cleanly through
:func:`arnold.workflow.validator.validate` and can be executed by the
existing graph executor (``run_pipeline`` / ``run_pipeline_resume``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Callable

from arnold.pipeline.declaration_lowering import derive_binding_map
from arnold.pipeline.native.decorators import (
    get_decision_meta,
    get_phase_meta,
    is_phase,
    is_pipeline,
)
from arnold.pipeline.native.ir import (
    DynamicMapMetadata,
    NativeInstruction,
    NativeTopology,
    NativeProgram,
    PATH_DELIMITER,
    ParallelInstruction,
    ParallelMapInstruction,
    ROOT_PATH,
    TopologyEdge,
    TopologyNode,
)
from arnold.pipeline.native.pack_validation import (
    PackClosureValidationError,
    validate_shared_pack_closure,
)
from arnold.pipeline.pattern_dynamic import (
    FanoutConcurrency,
    FanoutJoinContract,
    FanoutMetadata,
)
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Port,
    PortRef,
    Stage,
    Step,
    StepContext,
    StepResult,
)


# ── lightweight Step adapters ───────────────────────────────────────


class _NativePhaseStep:
    """Minimal Step adapter wrapping a native-phase callable."""

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        produces: tuple[Port, ...] = (),
        consumes: tuple[PortRef, ...] = (),
    ) -> None:
        self.name = name
        self.func = func
        self.kind = "native_phase"
        self.produces: tuple[Port, ...] = produces
        self.consumes: tuple[PortRef, ...] = consumes

    def run(self, ctx: StepContext) -> StepResult:
        return _coerce_step_result(self.func(ctx))


class _NativeDecisionStep:
    """Minimal Step adapter wrapping a native-decision callable."""

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        decision_vocabulary: frozenset[str] | None = None,
        decision_routes: dict[str, str | None] | None = None,
        override_vocabulary: frozenset[str] | None = None,
        human_gate: bool = False,
        artifact_stage: str = "",
        choices: tuple[str, ...] = (),
        resume_input_schema: Mapping[str, Any] | None = None,
        override_routes: dict[str, str | None] | None = None,
    ) -> None:
        self.name = name
        self.func = func
        self.kind = "native_decision"
        self.produces: tuple[Port, ...] = ()
        self.consumes: tuple[PortRef, ...] = ()
        self.decision_vocabulary: frozenset[str] = (
            decision_vocabulary if decision_vocabulary is not None else frozenset()
        )
        self.decision_routes: dict[str, str | None] = (
            dict(decision_routes) if decision_routes is not None else {}
        )
        self.override_vocabulary: frozenset[str] = (
            override_vocabulary if override_vocabulary is not None else frozenset()
        )
        self.human_gate = bool(human_gate)
        self.artifact_stage = artifact_stage
        self.choices = tuple(choices)
        self.resume_input_schema = (
            dict(resume_input_schema) if isinstance(resume_input_schema, Mapping) else {}
        )
        self.override_routes = dict(override_routes) if override_routes is not None else {}

    def run(self, ctx: StepContext) -> StepResult:
        result = self.func(ctx)
        if isinstance(result, StepResult):
            return result
        if hasattr(result, "next"):
            next_value = getattr(result, "next", None)
            return StepResult(next=str(next_value) if next_value else "__falsy__")
        next_label = str(result) if result else "__falsy__"
        return StepResult(next=next_label)


class _NativeSubpipelineStep:
    """Minimal Step adapter wrapping a child :class:`NativeProgram`.

    When the graph executor invokes ``run(ctx)``, the child program is
    executed via :func:`run_native_pipeline` in an isolated artifact
    root and the resulting state is returned as outputs.
    """

    def __init__(
        self,
        name: str,
        child_program: NativeProgram | None,
        output_bindings: Mapping[str, str] | None = None,
        produces: tuple[Port, ...] = (),
        consumes: tuple[PortRef, ...] = (),
    ) -> None:
        self.name = name
        self.child_program = child_program
        self.kind = "native_subpipeline"
        self.output_bindings = dict(output_bindings or {})
        self.produces: tuple[Port, ...] = produces
        self.consumes: tuple[PortRef, ...] = consumes

    def run(self, ctx: StepContext) -> StepResult:
        from pathlib import Path

        from arnold.pipeline.native.runtime import (
            _extract_child_inputs,
            _extract_child_outputs,
            run_native_pipeline,
        )

        if self.child_program is None:
            return StepResult(outputs={}, next="halt")

        child_artifact_root = Path(ctx.artifact_root) / f"_child_{self.name}"
        child_artifact_root.mkdir(parents=True, exist_ok=True)

        child_initial_state: dict[str, Any] = {}
        if isinstance(ctx.state, Mapping):
            child_initial_state = _extract_child_inputs(
                ctx.state,
                self.child_program.inputs_schema,
            )

        result = run_native_pipeline(
            program=self.child_program,
            artifact_root=child_artifact_root,
            initial_state=child_initial_state,
        )

        return StepResult(
            outputs=_extract_child_outputs(
                result.state,
                self.child_program.outputs_schema,
                self.output_bindings,
            ),
            next="halt",
        )


class _NativeParallelMapStep:
    """Step adapter for a runtime-list dynamic fan-out block."""

    def __init__(
        self,
        name: str,
        parallel_map: ParallelMapInstruction,
        call_site_path: tuple[str, ...],
    ) -> None:
        self.name = name
        self.parallel_map = parallel_map
        self.call_site_path = call_site_path
        self.kind = "native_parallel_map"
        self.produces: tuple[Port, ...] = ()
        self.consumes: tuple[PortRef, ...] = ()
        self.fanout_metadata = FanoutMetadata(
            concurrency=FanoutConcurrency(mode="sequential"),
            join_contract=FanoutJoinContract(
                arity="many",
                result_kind="reduce" if parallel_map.reducer is not None else "collect",
            ),
        )

    def run(self, ctx: StepContext) -> StepResult:
        from pathlib import Path

        from arnold.pipeline.native.compiler import compile_pipeline
        from arnold.pipeline.native.runtime import (
            _extract_child_inputs,
            _extract_child_outputs,
            _extract_state_patch,
            _normalize_phase_result,
            _parallel_map_item_coordinate,
            _parallel_map_item_state,
            _resolve_parallel_map_items,
            run_native_pipeline,
        )

        state = dict(ctx.state) if isinstance(ctx.state, Mapping) else {}
        inputs = dict(ctx.inputs) if isinstance(ctx.inputs, Mapping) else {}
        items = _resolve_parallel_map_items(
            items_ref=self.parallel_map.items_ref,
            state=state,
            parameter_values=inputs,
        )

        mapper = self.parallel_map.mapper
        if mapper is None:
            return StepResult(outputs={}, next="halt")

        mapper_results: list[Any] = []
        compiled_mapper_program: NativeProgram | None = None
        if not getattr(mapper, "__phase__", False):
            compiled_mapper_program = compile_pipeline(mapper)

        for index, item in enumerate(items):
            item_coordinate = _parallel_map_item_coordinate(
                path_template=self.parallel_map.path_template,
                item=item,
                index=index,
                items_ref=self.parallel_map.items_ref,
            )
            item_path = (*self.call_site_path, item_coordinate)
            item_state = _parallel_map_item_state(
                state,
                item=item,
                index=index,
                items_ref=self.parallel_map.items_ref,
                item_path=item_path,
            )
            if getattr(mapper, "__phase__", False):
                result = mapper(
                    {
                        "state": dict(item_state),
                        "inputs": dict(item_state),
                        "artifact_root": ctx.artifact_root,
                        "item": item,
                        "item_index": index,
                        "call_site_path": item_path,
                    }
                )
                outputs, _ = _normalize_phase_result(result, self.parallel_map.name or self.name)
                item_result = dict(outputs)
                item_result.update(_extract_state_patch(result))
            else:
                assert compiled_mapper_program is not None
                child_artifact_root = (
                    Path(ctx.artifact_root)
                    / f"_child_{compiled_mapper_program.name}"
                    / _safe_name(item_coordinate)
                )
                child_artifact_root.mkdir(parents=True, exist_ok=True)
                child_result = run_native_pipeline(
                    program=compiled_mapper_program,
                    artifact_root=child_artifact_root,
                    initial_state=_extract_child_inputs(
                        item_state,
                        compiled_mapper_program.inputs_schema,
                    ),
                )
                item_result = _extract_child_outputs(
                    child_result.state,
                    compiled_mapper_program.outputs_schema,
                    {},
                )
            mapper_results.append(item_result)

        if self.parallel_map.reducer is not None:
            reducer_result = self.parallel_map.reducer(mapper_results)
            outputs, _ = _normalize_phase_result(reducer_result, self.parallel_map.name or self.name)
            reduced = dict(outputs)
            reduced.update(_extract_state_patch(reducer_result))
            return StepResult(outputs=reduced, next="halt")
        return StepResult(outputs={self.name: mapper_results}, next="halt")


# ── default parallel join ───────────────────────────────────────────


def _default_parallel_join(results: list[StepResult], ctx: StepContext) -> StepResult:
    """Default fan-in join: collect all branch outputs into a merged dict.

    When a :class:`ParallelInstruction` has no custom ``reducer``, this
    default collects the outputs from every completed branch into a
    single ``StepResult`` that the runtime can merge into working state.
    """
    merged: dict[str, Any] = {}
    for r in results:
        if r.outputs:
            merged.update(r.outputs)
    return StepResult(outputs=merged, next="halt")


# ── public entry point ──────────────────────────────────────────────


def project_graph(program: NativeProgram, key_mode: str = "pc") -> Pipeline:
    """Project a compiled :class:`NativeProgram` into a :class:`Pipeline`.

    Only ``phase`` and ``decision`` instructions become stages.
    ``jump`` and ``halt`` instructions route edges but do not create
    their own stages.  ``parallel`` markers project into
    :class:`ParallelStage` entries whose ``steps`` are the inlined
    branch phases and whose ``join`` is the reducer (or a default
    collector).

    Args:
        program: A :class:`NativeProgram` from :func:`compile_pipeline`.
        key_mode: Stage naming strategy:
            ``"pc"`` (default) — ``{prefix}__{name}__pc{pc}``,
            ``"phase"`` — ``{name}`` with ``{name}__pc{pc}`` fallback
            for duplicate names, unless a callable opts into public-stage
            collapsing via projection metadata.

    Returns:
        A :class:`Pipeline` with stages, edges, loop_condition guards, and
        a typed-port binding map.
    """
    try:
        validate_shared_pack_closure(program)
    except PackClosureValidationError as exc:
        raise ValueError(f"Invalid native projection closure: {exc}") from exc
    if key_mode not in ("pc", "phase"):
        raise ValueError(f"Unknown key_mode: {key_mode!r}; expected 'pc' or 'phase'")

    instructions = program.instructions
    if not instructions:
        raise ValueError("NativeProgram has no instructions")

    prefix = _safe_name(program.name)

    # ── pre-scan: parallel blocks ─────────────────────────────────
    # Identify every parallel marker, the branch-phase PCs that belong to
    # it, and the merge PC.  Branch PCs are absorbed into a ParallelStage
    # and must not become standalone Stage entries.
    parallel_blocks: dict[int, ParallelInstruction] = {}  # marker_pc -> ParallelInstruction
    parallel_branch_pcs: set[int] = set()
    parallel_merge_pcs: dict[int, int] = {}  # marker_pc -> merge_pc

    for i, instr in enumerate(instructions):
        if instr.op == "parallel" and instr.subprogram is not None:
            if isinstance(instr.subprogram, ParallelInstruction):
                pi = instr.subprogram
                parallel_blocks[instr.pc] = pi
                parallel_merge_pcs[instr.pc] = pi.merge_pc if pi.merge_pc is not None else len(instructions)
                # Branch phases lie between marker_pc+1 and merge_pc-1
                merge = pi.merge_pc if pi.merge_pc is not None else len(instructions)
                for j in range(instr.pc + 1, merge):
                    if j < len(instructions):
                        parallel_branch_pcs.add(j)

    # ── loop header detection ─────────────────────────────────────
    loop_header_pcs: set[int] = set()
    for i, instr in enumerate(instructions):
        if instr.op == "jump" and instr.next_pc is not None:
            target_pc = instr.next_pc
            if target_pc < i and target_pc >= 0:
                loop_header_pcs.add(target_pc)

    duplicate_names = _duplicate_public_names(
        instructions, key_mode=key_mode, parallel_branch_pcs=parallel_branch_pcs
    )

    # ── build real_instrs + pc_to_stage ───────────────────────────
    real_instrs: list[NativeInstruction] = []
    pc_to_stage: dict[int, str] = {}

    for instr in instructions:
        # Parallel markers become ParallelStage entries.
        if instr.op in ("parallel", "parallel_map"):
            pi = parallel_blocks.get(instr.pc)
            block_name = pi.name if pi is not None else f"parallel_{instr.pc}"
            if instr.op == "parallel_map":
                stage_name = _parallel_map_stage_name(
                    instr,
                    key_mode=key_mode,
                    prefix=prefix,
                )
            else:
                stage_name = _parallel_stage_name(
                    block_name, instr.pc, key_mode=key_mode, prefix=prefix, instr=instr
                )
            pc_to_stage[instr.pc] = stage_name
            real_instrs.append(instr)
            continue

        if instr.op not in ("phase", "decision", "subpipeline"):
            continue
        if instr.pc in parallel_branch_pcs:
            continue  # Absorbed into a ParallelStage
        func = instr.func
        if func is not None and _projection_flag(func, "skip_stage", False):
            continue
        stage_name = _stage_name_for_instruction(
            instr,
            key_mode=key_mode,
            prefix=prefix,
            duplicate_names=duplicate_names,
        )
        pc_to_stage[instr.pc] = stage_name
        real_instrs.append(instr)

    if not real_instrs:
        raise ValueError("NativeProgram has no phase or decision instructions")

    # ── edge-resolution helpers ───────────────────────────────────

    def _resolve_next_real_pc(start_pc: int) -> int | None:
        """Follow jumps to find the next phase/decision/parallel pc, or None for halt."""
        visited: set[int] = set()
        cur = start_pc
        while cur >= 0 and cur < len(instructions):
            if cur in visited:
                return None
            visited.add(cur)
            instr = instructions[cur]
            if instr.op in ("phase", "decision", "parallel", "subpipeline"):
                return cur
            if instr.op == "halt":
                return None
            if instr.op == "jump":
                cur = instr.next_pc if instr.next_pc is not None else -1
            else:
                cur += 1
        return None

    def _resolve_next_public_pc(start_pc: int) -> int | None:
        """Follow jumps until a public stage instruction is reached."""
        visited: set[int] = set()
        cur = start_pc
        while cur >= 0 and cur < len(instructions):
            if cur in visited:
                return None
            visited.add(cur)
            if cur in pc_to_stage:
                return cur
            instr = instructions[cur]
            if instr.op == "halt":
                return None
            if instr.op == "jump":
                cur = instr.next_pc if instr.next_pc is not None else -1
            else:
                cur += 1
        return None

    # ── build stages ──────────────────────────────────────────────
    stages: dict[str, Stage | ParallelStage] = {}
    edges_by_src: dict[str, list[Edge]] = {}
    entry: str | None = None
    # Track which marker PCs have already been processed (avoid double-processing
    # when a parallel instruction appears in real_instrs alongside its branches).
    processed_parallel_markers: set[int] = set()

    for instr in real_instrs:
        src_name = pc_to_stage[instr.pc]
        if entry is None:
            entry = src_name

        # ── parallel stage ──────────────────────────────────────
        if instr.op == "parallel":
            if instr.pc in processed_parallel_markers:
                continue
            processed_parallel_markers.add(instr.pc)

            pi = parallel_blocks.get(instr.pc)
            if pi is None:
                # Degenerate: parallel marker without metadata — skip
                continue

            # Collect branch-phase steps from the instruction stream.
            merge = pi.merge_pc if pi.merge_pc is not None else len(instructions)
            branch_steps: list[Step] = []
            branch_produces: tuple[Port, ...] = ()
            branch_consumes: tuple[PortRef, ...] = ()
            for j in range(instr.pc + 1, merge):
                if j >= len(instructions):
                    break
                binstr = instructions[j]
                if binstr.op != "phase":
                    continue
                bf = binstr.func
                bname = binstr.name
                bproduces = getattr(binstr, "produces", ()) or ()
                bconsumes = getattr(binstr, "consumes", ()) or ()
                if bf is not None:
                    branch_steps.append(
                        _NativePhaseStep(
                            name=bname,
                            func=bf,
                            produces=bproduces,
                            consumes=bconsumes,
                        )
                    )
                    branch_produces = _merge_unique(branch_produces, bproduces)
                    branch_consumes = _merge_unique(branch_consumes, bconsumes)
                else:
                    branch_steps.append(
                        _NativePhaseStep(name=bname, func=lambda _: {})
                    )

            if not branch_steps:
                # Parallel block with no branch phases — skip
                continue

            # Build edges for the parallel stage (to merge point).
            edges = _projected_parallel_edges(
                pi=pi,
                merge_pc=merge,
                pc_to_stage=pc_to_stage,
                resolve_next_real_pc=_resolve_next_real_pc,
                resolve_next_public_pc=_resolve_next_public_pc,
            )

            join_func = pi.reducer if pi.reducer is not None else _default_parallel_join

            parallel_stage = ParallelStage(
                name=src_name,
                steps=tuple(branch_steps),
                join=join_func,
                edges=tuple(edges),
                produces=branch_produces,
                consumes=branch_consumes,
            )
            stages[src_name] = parallel_stage
            edges_by_src[src_name] = list(edges)
            continue

        if instr.op == "parallel_map":
            block = instr.subprogram if isinstance(instr.subprogram, ParallelMapInstruction) else None
            if block is None:
                continue
            edges = _projected_edges_for_instruction(
                instr,
                pc_to_stage=pc_to_stage,
                resolve_next_real_pc=_resolve_next_real_pc,
                resolve_next_public_pc=_resolve_next_public_pc,
            )
            step = _NativeParallelMapStep(
                name=src_name,
                parallel_map=block,
                call_site_path=instr.call_site_path,
            )
            stages[src_name] = Stage(
                name=src_name,
                step=step,
                edges=tuple(edges),
            )
            edges_by_src[src_name] = list(edges)
            continue

        # ── subpipeline stage ────────────────────────────────────
        if instr.op == "subpipeline":
            child_prog = instr.subprogram
            edges = _projected_edges_for_instruction(
                instr,
                pc_to_stage=pc_to_stage,
                resolve_next_real_pc=_resolve_next_real_pc,
                resolve_next_public_pc=_resolve_next_public_pc,
            )
            subpipeline_produces: tuple[Port, ...] = getattr(instr, "produces", ()) or ()
            subpipeline_consumes: tuple[PortRef, ...] = getattr(instr, "consumes", ()) or ()

            step = _NativeSubpipelineStep(
                name=src_name,
                child_program=child_prog if isinstance(child_prog, NativeProgram) else None,  # type: ignore[arg-type]
                output_bindings=getattr(instr, "output_bindings", {}),
                produces=subpipeline_produces,
                consumes=subpipeline_consumes,
            )

            stages[src_name] = Stage(
                name=src_name,
                step=step,
                edges=tuple(edges),
                produces=subpipeline_produces,
                consumes=subpipeline_consumes,
            )
            edges_by_src[src_name] = list(edges)
            continue

        # ── regular phase / decision stage (existing logic) ──────
        func = instr.func
        edges = _projected_edges_for_instruction(
            instr,
            pc_to_stage=pc_to_stage,
            resolve_next_real_pc=_resolve_next_real_pc,
            resolve_next_public_pc=_resolve_next_public_pc,
        )

        loop_condition: Callable[[Any], bool] | None = None
        if instr.pc in loop_header_pcs and func is not None:
            loop_condition = func
        loop_condition = _projection_value(func, "loop_condition", loop_condition)

        decision_routes: dict[str, str | None] = {}
        phase_produces: tuple[Port, ...] = getattr(instr, "produces", ()) or ()
        phase_consumes: tuple[PortRef, ...] = getattr(instr, "consumes", ()) or ()
        human_gate_meta = _human_gate_projection_meta(func, src_name)

        instr_vocab = frozenset(
            getattr(instr, "decision_vocabulary", frozenset()) or frozenset()
        )
        instr_vocab = frozenset(
            _projection_value(func, "decision_vocabulary", instr_vocab) or frozenset()
        )
        if human_gate_meta["choices"]:
            instr_vocab = frozenset(instr_vocab | frozenset(human_gate_meta["choices"]))
        override_vocab = frozenset(
            _projection_value(func, "override_vocabulary", frozenset()) or frozenset()
        )
        if human_gate_meta["override_routes"]:
            override_vocab = frozenset(
                override_vocab | frozenset(human_gate_meta["override_routes"].keys())
            )
            edges = _merge_edges(
                edges,
                _projected_human_gate_override_edges(
                    instr,
                    override_routes=human_gate_meta["override_routes"],
                    pc_to_stage=pc_to_stage,
                    instructions=instructions,
                    resolve_next_real_pc=_resolve_next_real_pc,
                    resolve_next_public_pc=_resolve_next_public_pc,
                ),
            )

        if instr.op == "decision":
            for label, branch_pc in instr.branches.items():
                next_real = _resolve_next_public_pc(branch_pc)
                if next_real is None:
                    next_real = _resolve_next_real_pc(branch_pc)
                decision_routes[label] = label if next_real in pc_to_stage else None
        custom_routes = _projection_value(func, "decision_routes")
        if isinstance(custom_routes, Mapping):
            decision_routes = {
                str(label): (None if target is None else str(target))
                for label, target in custom_routes.items()
            }

        if instr.op == "decision" and func is not None:
            step: Step = _NativeDecisionStep(
                name=src_name,
                func=func,
                decision_vocabulary=instr_vocab,
                decision_routes=decision_routes,
                override_vocabulary=override_vocab,
                human_gate=human_gate_meta["human_gate"],
                artifact_stage=human_gate_meta["artifact_stage"],
                choices=human_gate_meta["choices"],
                resume_input_schema=human_gate_meta["suspension_schema"],
                override_routes=human_gate_meta["override_routes"],
            )
        elif func is not None:
            step = _NativePhaseStep(
                name=src_name,
                func=func,
                produces=phase_produces,
                consumes=phase_consumes,
            )
        else:
            step = _NativePhaseStep(name=src_name, func=lambda _: {})

        if src_name in stages:
            existing = stages[src_name]
            if not isinstance(existing, Stage):
                # Should not happen: only Stage entries use duplicate names
                stages[src_name] = Stage(
                    name=src_name,
                    step=step,
                    edges=tuple(edges),
                    loop_condition=loop_condition,
                    decision_vocabulary=instr_vocab,
                    override_vocabulary=override_vocab,
                    decision_routes=decision_routes,
                    suspension_schema=human_gate_meta["suspension_schema"],
                    produces=phase_produces,
                    consumes=phase_consumes,
                )
                edges_by_src[src_name] = list(edges)
                continue
            merged_edges = _merge_edges(existing.edges, edges)
            merged_vocab = frozenset(existing.decision_vocabulary | instr_vocab)
            merged_override = frozenset(existing.override_vocabulary | override_vocab)
            merged_routes = dict(existing.decision_routes)
            merged_routes.update(decision_routes)
            merged_produces = _merge_unique(existing.produces, phase_produces)
            merged_consumes = _merge_unique(existing.consumes, phase_consumes)
            stages[src_name] = Stage(
                name=src_name,
                step=existing.step,
                edges=merged_edges,
                loop_condition=existing.loop_condition or loop_condition,
                decision_vocabulary=merged_vocab,
                override_vocabulary=merged_override,
                decision_routes=merged_routes,
                suspension_schema=existing.suspension_schema
                or human_gate_meta["suspension_schema"],
                produces=merged_produces,
                consumes=merged_consumes,
            )
            edges_by_src[src_name] = list(merged_edges)
            continue

        stages[src_name] = Stage(
            name=src_name,
            step=step,
            edges=tuple(edges),
            loop_condition=loop_condition,
            decision_vocabulary=instr_vocab,
            override_vocabulary=override_vocab,
            decision_routes=decision_routes,
            suspension_schema=human_gate_meta["suspension_schema"],
            produces=phase_produces,
            consumes=phase_consumes,
        )
        edges_by_src[src_name] = list(edges)

    # ── binding map ───────────────────────────────────────────────
    binding_map = None
    if not any(
        instr.func is not None and _projection_flag(instr.func, "disable_binding_map", False)
        for instr in real_instrs
    ):
        edge_pairs = [
            (src, edge.target)
            for src, edge_list in edges_by_src.items()
            for edge in edge_list
            if edge.target != "halt"
        ]
        binding_map = derive_binding_map(stages, edge_pairs)

    return Pipeline(
        stages=stages,
        entry=entry or "",
        binding_map=binding_map,
        native_program=program,
    )


def derive_topology(program: NativeProgram) -> NativeTopology:
    """Derive a static topology from a compiled native program without execution."""
    return _TopologyBuilder(program).build()


# ── helpers ─────────────────────────────────────────────────────────


def _safe_name(name: str) -> str:
    """Return a name safe for use as a stage-name prefix."""
    return name.replace(" ", "_").replace("-", "_")


class _TopologyBuilder:
    """Build a structural topology alongside the execution projection."""

    def __init__(self, program: NativeProgram) -> None:
        self.program = program
        self.instructions = program.instructions
        self.nodes: list[TopologyNode] = []
        self.edges: list[TopologyEdge] = []
        self.node_ids_by_pc: dict[int, str] = {}
        self._used_paths: set[str] = set()
        self._loop_guards_by_pc = self._detect_loop_headers()

    def build(self) -> NativeTopology:
        for instr in self.instructions:
            if not self._is_public_topology_instruction(instr):
                continue
            node = self._build_node(instr)
            self.nodes.append(node)
            self.node_ids_by_pc[instr.pc] = node.node_id
            if instr.op == "subpipeline":
                self._inline_child_program(node, instr.subprogram, edge_kind="child_workflow")
            elif instr.op == "parallel_map":
                self._inline_parallel_map_mapper(node, instr.subprogram)

        for instr in self.instructions:
            if instr.pc not in self.node_ids_by_pc:
                continue
            source = self.node_ids_by_pc[instr.pc]
            if instr.op == "decision":
                vocabulary = frozenset(instr.decision_vocabulary or frozenset())
                labels = tuple(sorted(vocabulary | frozenset(instr.branches.keys())))
                for label in labels:
                    branch_pc = instr.branches.get(label)
                    if branch_pc is None:
                        continue
                    target_pc = self._resolve_next_public_pc(branch_pc)
                    if target_pc is None:
                        continue
                    target = self.node_ids_by_pc.get(target_pc)
                    if target is None:
                        continue
                    self.edges.append(
                        TopologyEdge(
                            source=source,
                            target=target,
                            label=label,
                            kind="control_flow",
                        )
                    )
                continue

            next_pc = instr.next_pc
            if next_pc is None:
                continue
            target_pc = self._resolve_next_public_pc(next_pc)
            if target_pc is None:
                continue
            target = self.node_ids_by_pc.get(target_pc)
            if target is None:
                continue
            self.edges.append(
                TopologyEdge(
                    source=source,
                    target=target,
                    label="next",
                    kind="control_flow",
                )
            )

        return NativeTopology(
            name=self.program.name,
            nodes=tuple(self.nodes),
            edges=tuple(self.edges),
            root_path=ROOT_PATH,
            path_delimiter=PATH_DELIMITER,
        )

    def _detect_loop_headers(self) -> dict[int, Any]:
        loop_header_pcs: list[int] = []
        for index, instr in enumerate(self.instructions):
            if instr.op == "jump" and instr.next_pc is not None and instr.next_pc < index:
                loop_header_pcs.append(instr.next_pc)
        return {
            pc: self.program.loop_guards[index]
            for index, pc in enumerate(loop_header_pcs)
            if index < len(self.program.loop_guards)
        }

    def _is_public_topology_instruction(self, instr: NativeInstruction) -> bool:
        return instr.op in {"phase", "decision", "subpipeline", "parallel_map"}

    def _build_node(self, instr: NativeInstruction) -> TopologyNode:
        if instr.op == "phase":
            meta = get_phase_meta(instr.func) if instr.func is not None else None
            path = self._reserve_path(ROOT_PATH, self._node_segments(instr, meta))
            return TopologyNode(
                node_id=path,
                kind="phase",
                label=instr.name,
                path=path,
                stable_id=meta.get("id") if isinstance(meta, Mapping) else None,
                metadata={
                    "inputs_schema": meta.get("inputs") if isinstance(meta, Mapping) else None,
                    "outputs_schema": meta.get("outputs") if isinstance(meta, Mapping) else None,
                },
            )

        if instr.op == "subpipeline":
            child_program = instr.subprogram if isinstance(instr.subprogram, NativeProgram) else None
            path = self._reserve_path(ROOT_PATH, self._node_segments(instr, None))
            return TopologyNode(
                node_id=path,
                kind="child_workflow",
                label=instr.name,
                path=path,
                stable_id=child_program.stable_id if child_program is not None else None,
                metadata={
                    "child_name": child_program.name if child_program is not None else instr.name,
                    "child_stable_id": child_program.stable_id if child_program is not None else None,
                    "inputs_schema": child_program.inputs_schema if child_program is not None else None,
                    "outputs_schema": child_program.outputs_schema if child_program is not None else None,
                    "output_bindings": dict(instr.output_bindings),
                },
            )

        if instr.op == "parallel_map":
            block = instr.subprogram if isinstance(instr.subprogram, ParallelMapInstruction) else None
            path = self._reserve_path(ROOT_PATH, self._node_segments(instr, None))
            dynamic_map_metadata = DynamicMapMetadata(
                items_ref=block.items_ref if block is not None else "",
                mapper_name=block.mapper_name if block is not None else "",
                path_template=block.path_template if block is not None else "",
                collection_schema=block.collection_schema if block is not None else None,
                reducer_name=getattr(block.reducer, "__name__", "") if block is not None and block.reducer is not None else "",
                fan_in=bool(block is not None and block.reducer is not None),
            )
            return TopologyNode(
                node_id=path,
                kind="dynamic_map",
                label=instr.name,
                path=path,
                metadata={"dynamic_map_metadata": dynamic_map_metadata},
            )

        decision_meta = get_decision_meta(instr.func) if instr.func is not None else None
        loop_guard = self._loop_guards_by_pc.get(instr.pc)
        if loop_guard is not None:
            stable_id = loop_guard.stable_id or (
                decision_meta.get("id") if isinstance(decision_meta, Mapping) else None
            )
            stable_identity = stable_id or loop_guard.name or instr.name
            path = self._reserve_path(
                ROOT_PATH,
                self._node_segments(
                    instr,
                    {"id": stable_identity, "name": loop_guard.name or instr.name},
                ),
            )
            return TopologyNode(
                node_id=path,
                kind="loop",
                label=loop_guard.name or instr.name,
                path=path,
                stable_id=stable_identity,
                metadata={
                    "loop_stable_id": stable_identity,
                    "guard_name": getattr(loop_guard.guard, "__name__", loop_guard.name),
                    "vocabulary": sorted(instr.decision_vocabulary or ()),
                },
            )

        path = self._reserve_path(ROOT_PATH, self._node_segments(instr, decision_meta))
        return TopologyNode(
            node_id=path,
            kind="decision",
            label=instr.name,
            path=path,
            stable_id=decision_meta.get("id") if isinstance(decision_meta, Mapping) else None,
            metadata={
                "vocabulary": sorted(instr.decision_vocabulary or ()),
                "decision_routes": dict(getattr(instr, "branches", {})),
                "human_gate": bool(decision_meta.get("human_gate")) if isinstance(decision_meta, Mapping) else False,
                "choices": tuple(decision_meta.get("choices", ())) if isinstance(decision_meta, Mapping) else (),
            },
        )

    def _node_segments(
        self,
        instr: NativeInstruction,
        meta: Mapping[str, Any] | None,
    ) -> tuple[str, ...]:
        if instr.call_site_path:
            return tuple(str(segment) for segment in instr.call_site_path if str(segment))
        stable_id = meta.get("id") if isinstance(meta, Mapping) else None
        preferred = stable_id or instr.name or instr.op
        return (str(preferred),)

    def _reserve_path(self, base_path: str, segments: tuple[str, ...]) -> str:
        normalized = tuple(segment for segment in segments if segment)
        if not normalized:
            normalized = ("node",)
        candidate = _join_topology_path(base_path, normalized)
        if candidate not in self._used_paths:
            self._used_paths.add(candidate)
            return candidate
        stem = normalized[-1]
        index = 1
        while True:
            candidate = _join_topology_path(base_path, (*normalized[:-1], f"{stem}_{index}"))
            if candidate not in self._used_paths:
                self._used_paths.add(candidate)
                return candidate
            index += 1

    def _resolve_next_public_pc(self, start_pc: int) -> int | None:
        visited: set[int] = set()
        current = start_pc
        while current >= 0 and current < len(self.instructions):
            if current in visited:
                return None
            visited.add(current)
            if current in self.node_ids_by_pc:
                return current
            instr = self.instructions[current]
            if instr.op == "halt":
                return None
            if instr.op == "jump":
                current = instr.next_pc if instr.next_pc is not None else -1
            else:
                current += 1
        return None

    def _inline_child_program(
        self,
        parent_node: TopologyNode,
        child_program: Any,
        *,
        edge_kind: str,
        edge_label: str = "",
    ) -> None:
        if not isinstance(child_program, NativeProgram):
            return
        child_topology = child_program.topology
        if not isinstance(child_topology, NativeTopology):
            child_topology = derive_topology(child_program)
        rebased_nodes, rebased_edges = _rebase_topology(child_topology, parent_node.path)
        if rebased_nodes:
            self.edges.append(
                TopologyEdge(
                    source=parent_node.node_id,
                    target=rebased_nodes[0].node_id,
                    label=edge_label or parent_node.label,
                    kind=edge_kind,
                )
            )
        for node in rebased_nodes:
            if node.node_id not in self._used_paths:
                self._used_paths.add(node.node_id)
            self.nodes.append(node)
        self.edges.extend(rebased_edges)

    def _inline_parallel_map_mapper(
        self,
        parent_node: TopologyNode,
        subprogram: Any,
    ) -> None:
        if not isinstance(subprogram, ParallelMapInstruction) or subprogram.mapper is None:
            return
        template_segments = tuple(
            segment for segment in subprogram.path_template.split(PATH_DELIMITER) if segment
        ) or ("item",)
        if is_pipeline(subprogram.mapper):
            from arnold.pipeline.native.compiler import compile_pipeline

            mapper_program = compile_pipeline(subprogram.mapper)
            mapper_topology = mapper_program.topology
            if not isinstance(mapper_topology, NativeTopology):
                mapper_topology = derive_topology(mapper_program)
            rebased_nodes, rebased_edges = _rebase_topology(
                mapper_topology,
                _join_topology_path(parent_node.path, template_segments),
            )
            if rebased_nodes:
                self.edges.append(
                    TopologyEdge(
                        source=parent_node.node_id,
                        target=rebased_nodes[0].node_id,
                        label=subprogram.path_template or PATH_DELIMITER.join(template_segments),
                        kind="dynamic_map_item",
                    )
                )
            for node in rebased_nodes:
                if node.node_id not in self._used_paths:
                    self._used_paths.add(node.node_id)
                self.nodes.append(node)
            self.edges.extend(rebased_edges)
            return

        if not is_phase(subprogram.mapper):
            return
        mapper_meta = get_phase_meta(subprogram.mapper)
        mapper_path = self._reserve_path(parent_node.path, template_segments)
        self.nodes.append(
            TopologyNode(
                node_id=mapper_path,
                kind="phase",
                label=subprogram.mapper_name or getattr(subprogram.mapper, "__name__", "mapper"),
                path=mapper_path,
                stable_id=mapper_meta.get("id") if isinstance(mapper_meta, Mapping) else None,
                metadata={
                    "inputs_schema": mapper_meta.get("inputs") if isinstance(mapper_meta, Mapping) else None,
                    "outputs_schema": mapper_meta.get("outputs") if isinstance(mapper_meta, Mapping) else None,
                },
            )
        )
        self.edges.append(
            TopologyEdge(
                source=parent_node.node_id,
                target=mapper_path,
                label=subprogram.path_template or PATH_DELIMITER.join(template_segments),
                kind="dynamic_map_item",
            )
        )


def _join_topology_path(base_path: str, segments: tuple[str, ...]) -> str:
    if not segments:
        return base_path
    return PATH_DELIMITER.join((base_path, *segments))


def _relative_topology_segments(path: str) -> tuple[str, ...]:
    if not path or path == ROOT_PATH:
        return ()
    prefix = f"{ROOT_PATH}{PATH_DELIMITER}"
    if path.startswith(prefix):
        path = path[len(prefix):]
    return tuple(segment for segment in path.split(PATH_DELIMITER) if segment)


def _rebase_topology(
    topology: NativeTopology,
    base_path: str,
) -> tuple[list[TopologyNode], list[TopologyEdge]]:
    node_id_map: dict[str, str] = {}
    rebased_nodes: list[TopologyNode] = []
    for node in topology.nodes:
        relative_segments = _relative_topology_segments(node.path)
        new_path = _join_topology_path(base_path, relative_segments)
        node_id_map[node.node_id] = new_path
        rebased_nodes.append(
            TopologyNode(
                node_id=new_path,
                kind=node.kind,
                label=node.label,
                path=new_path,
                stable_id=node.stable_id,
                metadata=node.metadata,
            )
        )
    rebased_edges = [
        TopologyEdge(
            source=node_id_map.get(edge.source, edge.source),
            target=node_id_map.get(edge.target, edge.target),
            label=edge.label,
            kind=edge.kind,
            metadata=edge.metadata,
        )
        for edge in topology.edges
        if edge.source in node_id_map and edge.target in node_id_map
    ]
    return rebased_nodes, rebased_edges


def _coerce_step_result(result: Any) -> StepResult:
    """Normalize foreign step results into the neutral StepResult dataclass."""
    if isinstance(result, StepResult):
        return result
    if hasattr(result, "outputs") and hasattr(result, "next"):
        # Already StepResult-shaped (e.g. Megaplan StepResult with envelope).
        # Preserve it so runtimes that expect extra fields (envelope) keep them.
        return result
    if isinstance(result, dict):
        return StepResult(outputs=result, next="halt")
    if hasattr(result, "outputs") or hasattr(result, "next") or hasattr(result, "verdict"):
        outputs = getattr(result, "outputs", {})
        if not isinstance(outputs, Mapping):
            outputs = {}
        state_patch = getattr(result, "state_patch", {})
        if not isinstance(state_patch, Mapping):
            state_patch = {}
        hook_metadata = getattr(result, "hook_metadata", {})
        if not isinstance(hook_metadata, Mapping):
            hook_metadata = {}
        return StepResult(
            outputs=dict(outputs),
            verdict=getattr(result, "verdict", None),
            next=str(getattr(result, "next", "halt") or "halt"),
            state_patch=dict(state_patch),
            contract_result=getattr(result, "contract_result", None),
            hook_metadata=dict(hook_metadata),
        )
    return StepResult(outputs={"value": result}, next="halt")


def _projection_attr_name(key: str) -> str:
    return f"__native_projection_{key}__"


def _projection_value(func: Callable[..., Any] | None, key: str, default: Any = None) -> Any:
    if func is None:
        return default
    return getattr(func, _projection_attr_name(key), default)


def _projection_flag(func: Callable[..., Any] | None, key: str, default: bool = False) -> bool:
    return bool(_projection_value(func, key, default))


def _decision_attr(func: Callable[..., Any] | None, key: str, default: Any = None) -> Any:
    if func is None:
        return default
    return getattr(func, f"__decision_{key}__", default)


def _public_name_for_instruction(instr: NativeInstruction) -> str:
    func = instr.func
    hinted_name = _projection_value(func, "stage_name")
    if isinstance(hinted_name, str) and hinted_name:
        return hinted_name
    if instr.op == "decision" and bool(_decision_attr(func, "human_gate", False)):
        decision_name = _decision_attr(func, "name", "")
        if isinstance(decision_name, str) and decision_name:
            return decision_name
    if instr.op == "subpipeline" and instr.subprogram is not None:
        sub = instr.subprogram
        if isinstance(sub, NativeProgram) and sub.stable_id:
            return sub.stable_id
    return instr.name


def _call_site_identity(instr: NativeInstruction) -> str:
    if not instr.call_site_path:
        return ""
    return "/".join(str(segment) for segment in instr.call_site_path if str(segment))


def _normalized_route_map(raw: Any) -> dict[str, str | None]:
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(label): (None if target is None else str(target))
        for label, target in raw.items()
    }


def _schema_has_choice_enum(schema: Mapping[str, Any]) -> bool:
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return False
    choice = properties.get("choice")
    if not isinstance(choice, Mapping):
        return False
    enum = choice.get("enum")
    return isinstance(enum, (list, tuple)) and bool(enum)


def _human_gate_suspension_schema(
    *,
    stage_name: str,
    decision_name: str,
    artifact_stage: str,
    choices: tuple[str, ...],
    resume_input_schema: Mapping[str, Any] | None,
    override_routes: Mapping[str, str | None],
) -> dict[str, Any]:
    schema: dict[str, Any] = (
        dict(resume_input_schema) if isinstance(resume_input_schema, Mapping) else {}
    )
    if choices and not _schema_has_choice_enum(schema):
        properties = dict(schema.get("properties", {})) if isinstance(
            schema.get("properties"), Mapping
        ) else {}
        properties["choice"] = {
            "type": "string",
            "enum": list(choices),
        }
        schema["type"] = schema.get("type", "object")
        schema["properties"] = properties
        required = schema.get("required")
        if isinstance(required, (list, tuple)):
            schema["required"] = list(dict.fromkeys([*required, "choice"]))
        else:
            schema["required"] = ["choice"]

    schema["x-arnold-human-gate"] = {
        "stage": stage_name,
        "decision": decision_name,
        "artifact_stage": artifact_stage,
        "choices": list(choices),
        "override_routes": dict(override_routes),
    }
    return schema


def _human_gate_projection_meta(
    func: Callable[..., Any] | None,
    stage_name: str,
) -> dict[str, Any]:
    if not bool(_decision_attr(func, "human_gate", False)):
        return {
            "human_gate": False,
            "artifact_stage": "",
            "choices": (),
            "override_routes": {},
            "suspension_schema": None,
        }

    decision_name = str(_decision_attr(func, "name", "") or stage_name)
    artifact_stage = str(_decision_attr(func, "artifact_stage", "") or decision_name)
    choices = tuple(str(choice) for choice in (_decision_attr(func, "choices", ()) or ()))
    resume_input_schema = _decision_attr(func, "resume_input_schema", None)
    override_routes = _normalized_route_map(_decision_attr(func, "override_routes", None))
    suspension_schema = _human_gate_suspension_schema(
        stage_name=stage_name,
        decision_name=decision_name,
        artifact_stage=artifact_stage,
        choices=choices,
        resume_input_schema=resume_input_schema
        if isinstance(resume_input_schema, Mapping)
        else None,
        override_routes=override_routes,
    )
    return {
        "human_gate": True,
        "artifact_stage": artifact_stage,
        "choices": choices,
        "override_routes": override_routes,
        "suspension_schema": suspension_schema,
    }


def _duplicate_public_names(
    instructions: Iterable[NativeInstruction],
    *,
    key_mode: str,
    parallel_branch_pcs: set[int] | None = None,
) -> frozenset[str]:
    if key_mode != "phase":
        return frozenset()
    skip_pcs = parallel_branch_pcs or set()
    counts: dict[str, int] = {}
    for instr in instructions:
        if instr.op not in ("phase", "decision", "subpipeline"):
            continue
        if instr.pc in skip_pcs:
            continue
        func = instr.func
        if func is not None and _projection_flag(func, "skip_stage", False):
            continue
        if func is not None and _projection_flag(func, "merge_stage", False):
            continue
        public_name = _public_name_for_instruction(instr)
        counts[public_name] = counts.get(public_name, 0) + 1
    return frozenset(name for name, count in counts.items() if count > 1)


def _parallel_stage_name(
    block_name: str,
    pc: int,
    *,
    key_mode: str,
    prefix: str,
    instr: NativeInstruction | None = None,
) -> str:
    """Return a stable stage name for a parallel block.

    When *instr* carries a ``call_site_path``, the call-site identity is
    preferred over *block_name*, matching the behaviour of
    :func:`_parallel_map_stage_name` and subpipeline stage naming.
    """
    if instr is not None:
        identity = _call_site_identity(instr)
        if identity:
            safe_block = identity.replace(" ", "_").replace("-", "_").replace("/", "__")
            if key_mode == "pc":
                return f"{prefix}__{safe_block}__pc{pc}"
            return safe_block
    safe_block = block_name.replace(" ", "_").replace("-", "_")
    if key_mode == "pc":
        return f"{prefix}__{safe_block}__pc{pc}"
    return safe_block


def _parallel_map_stage_name(
    instr: NativeInstruction,
    *,
    key_mode: str,
    prefix: str,
) -> str:
    name = _call_site_identity(instr) or instr.name
    safe_name = name.replace(" ", "_").replace("-", "_").replace("/", "__")
    if key_mode == "pc":
        return f"{prefix}__{safe_name}__pc{instr.pc}"
    return safe_name


def _stage_name_for_instruction(
    instr: NativeInstruction,
    *,
    key_mode: str,
    prefix: str,
    duplicate_names: frozenset[str],
) -> str:
    func = instr.func
    public_name = _public_name_for_instruction(instr)

    if key_mode == "pc":
        return f"{prefix}__{public_name}__pc{instr.pc}"
    if func is not None and _projection_flag(func, "merge_stage", False):
        return public_name
    if instr.op == "subpipeline":
        call_site_identity = _call_site_identity(instr)
        if call_site_identity:
            safe_identity = call_site_identity.replace(" ", "_").replace("-", "_").replace("/", "__")
            if public_name in duplicate_names:
                return f"{public_name}__{safe_identity}"
            return safe_identity
    if public_name in duplicate_names:
        return f"{public_name}__pc{instr.pc}"
    return public_name


def _projected_parallel_edges(
    pi: ParallelInstruction,
    merge_pc: int,
    *,
    pc_to_stage: Mapping[int, str],
    resolve_next_real_pc: Callable[[int], int | None],
    resolve_next_public_pc: Callable[[int], int | None],
) -> list[Edge]:
    """Build outgoing edges for a parallel block's ParallelStage.

    The merge point is the PC immediately after the last branch body.
    If a next public stage exists at or after the merge point, the edge
    targets that stage; otherwise the edge targets ``"halt"``.
    """
    next_real = resolve_next_public_pc(merge_pc)
    if next_real is None:
        next_real = resolve_next_real_pc(merge_pc)
    if next_real is not None and next_real in pc_to_stage:
        target = pc_to_stage[next_real]
        return [Edge(label=target, target=target)]
    return [Edge(label="halt", target="halt")]


def _projected_human_gate_override_edges(
    instr: NativeInstruction,
    *,
    override_routes: Mapping[str, str | None],
    pc_to_stage: Mapping[int, str],
    instructions: tuple[NativeInstruction, ...],
    resolve_next_real_pc: Callable[[int], int | None],
    resolve_next_public_pc: Callable[[int], int | None],
) -> list[Edge]:
    edges: list[Edge] = []
    for label, route_target in override_routes.items():
        target = _resolve_projected_route_target(
            route_target,
            instr=instr,
            pc_to_stage=pc_to_stage,
            instructions=instructions,
            resolve_next_real_pc=resolve_next_real_pc,
            resolve_next_public_pc=resolve_next_public_pc,
        )
        edges.append(
            Edge(label=f"override {label}", target=target, kind="override")
        )
    return edges


def _resolve_projected_route_target(
    route_target: str | None,
    *,
    instr: NativeInstruction,
    pc_to_stage: Mapping[int, str],
    instructions: tuple[NativeInstruction, ...],
    resolve_next_real_pc: Callable[[int], int | None],
    resolve_next_public_pc: Callable[[int], int | None],
) -> str:
    if route_target is None or route_target == "halt":
        return "halt"

    if route_target in instr.branches:
        return _projected_target_for_pc(
            instr.branches[route_target],
            pc_to_stage=pc_to_stage,
            resolve_next_real_pc=resolve_next_real_pc,
            resolve_next_public_pc=resolve_next_public_pc,
        )

    for pc, stage_name in pc_to_stage.items():
        if stage_name == route_target:
            return stage_name
        candidate = instructions[pc] if 0 <= pc < len(instructions) else None
        if candidate is not None and _public_name_for_instruction(candidate) == route_target:
            return stage_name

    for candidate in instructions:
        if candidate.op not in ("phase", "decision", "parallel", "subpipeline"):
            continue
        if candidate.name != route_target and _public_name_for_instruction(candidate) != route_target:
            continue
        return _projected_target_for_pc(
            candidate.pc,
            pc_to_stage=pc_to_stage,
            resolve_next_real_pc=resolve_next_real_pc,
            resolve_next_public_pc=resolve_next_public_pc,
        )

    return route_target


def _projected_target_for_pc(
    pc: int,
    *,
    pc_to_stage: Mapping[int, str],
    resolve_next_real_pc: Callable[[int], int | None],
    resolve_next_public_pc: Callable[[int], int | None],
) -> str:
    next_real = resolve_next_public_pc(pc)
    if next_real is None:
        next_real = resolve_next_real_pc(pc)
    if next_real is not None and next_real in pc_to_stage:
        return pc_to_stage[next_real]
    return "halt"


def _projected_edges_for_instruction(
    instr: NativeInstruction,
    *,
    pc_to_stage: Mapping[int, str],
    resolve_next_real_pc: Callable[[int], int | None],
    resolve_next_public_pc: Callable[[int], int | None],
) -> list[Edge]:
    func = instr.func
    custom_edges = _projection_value(func, "edges")
    if custom_edges:
        return list(_normalize_edges(custom_edges))

    edges: list[Edge] = []
    if instr.op in ("phase", "subpipeline"):
        next_real = resolve_next_public_pc(instr.pc + 1) if instr.next_pc is not None else None
        if next_real is not None and next_real in pc_to_stage:
            target = pc_to_stage[next_real]
            edges.append(Edge(label=target, target=target))
        else:
            edges.append(Edge(label="halt", target="halt"))
        return edges

    if instr.op == "decision":
        for label, branch_pc in instr.branches.items():
            next_real = resolve_next_public_pc(branch_pc)
            if next_real is None:
                next_real = resolve_next_real_pc(branch_pc)
            if next_real is not None and next_real in pc_to_stage:
                edges.append(Edge(label=label, target=pc_to_stage[next_real]))
            else:
                edges.append(Edge(label=label, target="halt"))
        if not edges:
            edges.append(Edge(label="halt", target="halt"))
    return edges


def _normalize_edges(raw_edges: Any) -> tuple[Edge, ...]:
    normalized: list[Edge] = []
    if not isinstance(raw_edges, Iterable):
        return ()
    for raw in raw_edges:
        if isinstance(raw, Edge):
            normalized.append(raw)
            continue
        label = getattr(raw, "label", None)
        target = getattr(raw, "target", None)
        kind = getattr(raw, "kind", "normal")
        if isinstance(label, str) and isinstance(target, str):
            normalized.append(Edge(label=label, target=target, kind=str(kind or "normal")))
            continue
        if isinstance(raw, tuple) and len(raw) >= 2:
            normalized.append(
                Edge(
                    label=str(raw[0]),
                    target=str(raw[1]),
                    kind=str(raw[2]) if len(raw) >= 3 else "normal",
                )
            )
    return _merge_edges((), normalized)


def _merge_edges(existing: Iterable[Edge], new_edges: Iterable[Edge]) -> tuple[Edge, ...]:
    merged: list[Edge] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in tuple(existing) + tuple(new_edges):
        key = (edge.label, edge.target, edge.kind)
        if key in seen:
            continue
        seen.add(key)
        merged.append(edge)
    return tuple(merged)


def _merge_unique(existing: Iterable[Any], new_values: Iterable[Any]) -> tuple[Any, ...]:
    merged: list[Any] = []
    for value in tuple(existing) + tuple(new_values):
        if value in merged:
            continue
        merged.append(value)
    return tuple(merged)
