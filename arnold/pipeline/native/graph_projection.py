"""Graph projection: convert a NativeProgram into a Pipeline.

Walks a compiled :class:`NativeProgram` and builds a :class:`Pipeline`
with stage/edge metadata, guarded-loop ``loop_condition``, and an
optional typed-port binding map derived via ``derive_binding_map()``.

The resulting Pipeline validates cleanly through
:func:`arnold.pipeline.validator.validate` and can be executed by the
existing graph executor (``run_pipeline`` / ``run_pipeline_resume``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Callable

from arnold.pipeline.declaration_lowering import derive_binding_map
from arnold.pipeline.native.ir import NativeInstruction, NativeProgram
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
        if isinstance(result, StepResult):
            return result
        if hasattr(result, "next"):
            next_value = getattr(result, "next", None)
            return StepResult(next=str(next_value) if next_value else "__falsy__")
        next_label = str(result) if result else "__falsy__"
        return StepResult(next=next_label)


# ── public entry point ──────────────────────────────────────────────


def project_graph(program: NativeProgram, key_mode: str = "pc") -> Pipeline:
    """Project a compiled :class:`NativeProgram` into a :class:`Pipeline`.

    Only ``phase`` and ``decision`` instructions become stages.
    ``jump`` and ``halt`` instructions route edges but do not create
    their own stages.

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
    if key_mode not in ("pc", "phase"):
        raise ValueError(f"Unknown key_mode: {key_mode!r}; expected 'pc' or 'phase'")

    instructions = program.instructions
    if not instructions:
        raise ValueError("NativeProgram has no instructions")

    prefix = _safe_name(program.name)

    loop_header_pcs: set[int] = set()
    for i, instr in enumerate(instructions):
        if instr.op == "jump" and instr.next_pc is not None:
            target_pc = instr.next_pc
            if target_pc < i and target_pc >= 0:
                loop_header_pcs.add(target_pc)

    duplicate_names = _duplicate_public_names(instructions, key_mode=key_mode)

    real_instrs: list[NativeInstruction] = []
    pc_to_stage: dict[int, str] = {}
    for instr in instructions:
        if instr.op not in ("phase", "decision"):
            continue
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

    def _resolve_next_real_pc(start_pc: int) -> int | None:
        """Follow jumps to find the next phase/decision pc, or None for halt."""
        visited: set[int] = set()
        cur = start_pc
        while cur >= 0 and cur < len(instructions):
            if cur in visited:
                return None
            visited.add(cur)
            instr = instructions[cur]
            if instr.op in ("phase", "decision"):
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

    stages: dict[str, Stage] = {}
    edges_by_src: dict[str, list[Edge]] = {}
    entry: str | None = None

    for instr in real_instrs:
        src_name = pc_to_stage[instr.pc]
        if entry is None:
            entry = src_name

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

        instr_vocab = frozenset(
            getattr(instr, "decision_vocabulary", frozenset()) or frozenset()
        )
        instr_vocab = frozenset(
            _projection_value(func, "decision_vocabulary", instr_vocab) or frozenset()
        )
        override_vocab = frozenset(
            _projection_value(func, "override_vocabulary", frozenset()) or frozenset()
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
            produces=phase_produces,
            consumes=phase_consumes,
        )
        edges_by_src[src_name] = list(edges)

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
    )


# ── helpers ─────────────────────────────────────────────────────────


def _safe_name(name: str) -> str:
    """Return a name safe for use as a stage-name prefix."""
    return name.replace(" ", "_").replace("-", "_")


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


def _duplicate_public_names(
    instructions: Iterable[NativeInstruction],
    *,
    key_mode: str,
) -> frozenset[str]:
    if key_mode != "phase":
        return frozenset()
    counts: dict[str, int] = {}
    for instr in instructions:
        if instr.op not in ("phase", "decision"):
            continue
        func = instr.func
        if func is not None and _projection_flag(func, "skip_stage", False):
            continue
        if func is not None and _projection_flag(func, "merge_stage", False):
            continue
        hinted_name = _projection_value(func, "stage_name")
        public_name = (
            str(hinted_name)
            if isinstance(hinted_name, str) and hinted_name
            else instr.name
        )
        counts[public_name] = counts.get(public_name, 0) + 1
    return frozenset(name for name, count in counts.items() if count > 1)


def _stage_name_for_instruction(
    instr: NativeInstruction,
    *,
    key_mode: str,
    prefix: str,
    duplicate_names: frozenset[str],
) -> str:
    func = instr.func
    hinted_name = _projection_value(func, "stage_name")
    public_name = (
        str(hinted_name)
        if isinstance(hinted_name, str) and hinted_name
        else instr.name
    )

    if key_mode == "pc":
        return f"{prefix}__{instr.name}__pc{instr.pc}"
    if func is not None and _projection_flag(func, "merge_stage", False):
        return public_name
    if public_name in duplicate_names:
        return f"{public_name}__pc{instr.pc}"
    return public_name


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
    if instr.op == "phase":
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
