"""Graph projection: convert a NativeProgram into a Pipeline.

Walks a compiled :class:`NativeProgram` and builds a :class:`Pipeline`
with stage/edge metadata, guarded-loop ``loop_condition``, and an
optional typed-port binding map derived via ``derive_binding_map()``.

The resulting Pipeline validates cleanly through
:func:`arnold.pipeline.validator.validate` and can be executed by the
existing graph executor (``run_pipeline`` / ``run_pipeline_resume``).
"""

from __future__ import annotations

from typing import Any, Callable

from arnold.pipeline.declaration_lowering import derive_binding_map
from arnold.pipeline.types import (
    Edge,
    Pipeline,
    Port,
    PortRef,
    Stage,
    Step,
    StepContext,
    StepResult,
)

from arnold.pipeline.native.ir import (
    NativeInstruction,
    NativeProgram,
)


# ── lightweight Step adapters ───────────────────────────────────────


class _NativePhaseStep:
    """Minimal Step adapter wrapping a native-phase callable.

    Implements the :class:`Step` Protocol so the returned :class:`Stage`
    objects are compatible with the graph executor.
    """

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
        result = self.func(ctx)
        if isinstance(result, dict):
            return StepResult(outputs=result, next="halt")
        if isinstance(result, StepResult):
            return result
        return StepResult(outputs={"value": result}, next="halt")


class _NativeDecisionStep:
    """Minimal Step adapter wrapping a native-decision callable.

    Decisions are treated as pass-through stages that route via
    their return value.
    """

    def __init__(
        self,
        name: str,
        func: Callable[..., Any],
        decision_vocabulary: frozenset[str] | None = None,
        decision_routes: dict[str, str | None] | None = None,
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

    def run(self, ctx: StepContext) -> StepResult:
        result = self.func(ctx)
        next_label = str(result) if result else "__falsy__"
        return StepResult(next=next_label)


# ── public entry point ──────────────────────────────────────────────


def project_graph(program: NativeProgram) -> Pipeline:
    """Project a compiled :class:`NativeProgram` into a :class:`Pipeline`.

    Only ``phase`` and ``decision`` instructions become stages.
    ``jump`` and ``halt`` instructions route edges but do not create
    their own stages.

    Args:
        program: A :class:`NativeProgram` from :func:`compile_pipeline`.

    Returns:
        A :class:`Pipeline` with stages, edges, loop_condition guards, and
        a typed-port binding map.
    """
    instructions = program.instructions
    if not instructions:
        raise ValueError("NativeProgram has no instructions")

    prefix = _safe_name(program.name)

    # ── identify loop structures ──────────────────────────────────
    loop_header_pcs: set[int] = set()  # PCs of while-loop header (decision) instructions
    loop_body_pcs: set[int] = set()    # PCs of phase instructions inside loops

    for i, instr in enumerate(instructions):
        if instr.op == "jump" and instr.next_pc is not None:
            target_pc = instr.next_pc
            if target_pc < i and target_pc >= 0:
                # Back-edge jump → loop
                loop_header_pcs.add(target_pc)
                for body_pc in range(target_pc + 1, i):
                    loop_body_pcs.add(body_pc)

    # ── build pc→stage_name mapping (only for phase/decision) ─────
    # Collect all "real" instructions (phase + decision)
    real_instrs: list[NativeInstruction] = []
    pc_to_stage: dict[int, str] = {}

    for instr in instructions:
        if instr.op in ("phase", "decision"):
            stage_name = f"{prefix}__{instr.name}__pc{instr.pc}"
            pc_to_stage[instr.pc] = stage_name
            real_instrs.append(instr)

    if not real_instrs:
        raise ValueError("NativeProgram has no phase or decision instructions")

    # ── helper: resolve next real pc (follow jumps) ───────────────
    def _resolve_next_real_pc(start_pc: int) -> int | None:
        """Follow jump chain to find the next real instruction pc, or None for halt."""
        visited: set[int] = set()
        cur = start_pc
        while cur >= 0 and cur < len(instructions):
            if cur in visited:
                return None  # cycle (handled separately)
            visited.add(cur)
            instr = instructions[cur]
            if instr.op in ("phase", "decision"):
                return cur
            if instr.op == "halt":
                return None
            if instr.op == "jump":
                cur = instr.next_pc if instr.next_pc is not None else -1
            else:
                # fallback: try linear next
                cur = cur + 1
        return None

    # ── build stages and edges ────────────────────────────────────
    stages: dict[str, Stage] = {}
    edges_by_src: dict[str, list[Edge]] = {}
    entry: str | None = None

    for instr in real_instrs:
        src_name = pc_to_stage[instr.pc]
        if entry is None:
            entry = src_name

        edges: list[Edge] = []
        func = instr.func

        if instr.op == "phase":
            # Follow next_pc through jumps to find the next real stage
            next_real = _resolve_next_real_pc(instr.pc + 1) if instr.next_pc is not None else None
            if next_real is not None and next_real in pc_to_stage:
                edges.append(Edge(label=pc_to_stage[next_real], target=pc_to_stage[next_real]))
            else:
                edges.append(Edge(label="halt", target="halt"))

        elif instr.op == "decision":
            for label, branch_pc in instr.branches.items():
                next_real = _resolve_next_real_pc(branch_pc)
                if next_real is not None and next_real in pc_to_stage:
                    edges.append(Edge(label=label, target=pc_to_stage[next_real]))
                else:
                    edges.append(Edge(label=label, target="halt"))
            if not edges:
                edges.append(Edge(label="halt", target="halt"))

        # Determine loop_condition
        loop_condition: Callable[[Any], bool] | None = None
        is_loop_header = instr.pc in loop_header_pcs
        if is_loop_header and func is not None:
            loop_condition = func

        # ── Compute decision_routes for decision stages ──────────────
        # decision_routes maps decision keys → edge labels (not stage names).
        # Edge labels are the branch labels themselves; None means terminal.
        decision_routes: dict[str, str | None] = {}

        # Extract typed port metadata from the instruction
        phase_produces: tuple[Port, ...] = getattr(instr, "produces", ()) or ()
        phase_consumes: tuple[PortRef, ...] = getattr(instr, "consumes", ()) or ()

        # Extract decision vocabulary from the instruction
        instr_vocab: frozenset[str] = frozenset(
            getattr(instr, "decision_vocabulary", frozenset()) or frozenset()
        )

        # Create the appropriate Step adapter
        if instr.op == "decision":
            # Compute decision_routes: map each branch label → edge label.
            # The edge label is the same as the decision key.  Only set to
            # None when the branch has no reachable target (terminal).
            for label, branch_pc in instr.branches.items():
                next_real = _resolve_next_real_pc(branch_pc)
                if next_real is not None and next_real in pc_to_stage:
                    # Edge label matches the decision key
                    decision_routes[label] = label
                else:
                    decision_routes[label] = None

        if is_loop_header and func is not None:
            step: Step = _NativeDecisionStep(
                name=src_name,
                func=func,
                decision_vocabulary=instr_vocab,
                decision_routes=decision_routes,
            )
        elif instr.op == "decision" and func is not None:
            step = _NativeDecisionStep(
                name=src_name,
                func=func,
                decision_vocabulary=instr_vocab,
                decision_routes=decision_routes,
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

        stages[src_name] = Stage(
            name=src_name,
            step=step,
            edges=tuple(edges),
            loop_condition=loop_condition,
            decision_vocabulary=instr_vocab,
            decision_routes=decision_routes,
            produces=phase_produces,
            consumes=phase_consumes,
        )
        edges_by_src[src_name] = edges

    # ── derive binding map ────────────────────────────────────────
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
    )


# ── helpers ─────────────────────────────────────────────────────────


def _safe_name(name: str) -> str:
    """Return a name safe for use as a stage-name prefix."""
    return name.replace(" ", "_").replace("-", "_")
