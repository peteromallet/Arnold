"""Composition-graph derivation and serialization helpers.

Derives a :class:`NativeCompositionGraph` from a compiled
:class:`NativeProgram` via a single post-compile walk over the
instruction stream. No second AST walk is performed; the existing IR
already carries the structural metadata required to recover the static
topology.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from arnold.pipeline.native.decorators import get_decision_meta, get_phase_meta
from arnold.pipeline.native.ir import (
    CompositionEdge,
    CompositionNode,
    CompositionNodeKind,
    NativeCompositionGraph,
    NativeInstruction,
    NativeProgram,
    ParallelInstruction,
    ParallelMapInstruction,
)


class _GraphBuilder:
    def __init__(self, root_program: NativeProgram) -> None:
        self._root_program = root_program
        self._root_id = f"__root__{_safe_id(root_program.name)}"
        self._node_specs: dict[str, dict[str, Any]] = {
            self._root_id: {
                "node_id": self._root_id,
                "kind": CompositionNodeKind.ROOT,
                "label": root_program.name,
                "stable_id": root_program.stable_id,
                "parent_id": None,
                "path_segments": (),
                "inputs_schema": (
                    dict(root_program.inputs_schema)
                    if isinstance(root_program.inputs_schema, Mapping) else None
                ),
                "outputs_schema": (
                    dict(root_program.outputs_schema)
                    if isinstance(root_program.outputs_schema, Mapping) else None
                ),
            }
        }
        self._children: dict[str, list[str]] = {self._root_id: []}
        self._edge_keys: set[tuple[str, str, str, str]] = set()
        self._edges: list[CompositionEdge] = []
        self._untaken_route_labels: set[str] = set()

    def build(self) -> NativeCompositionGraph:
        self._add_program_nodes(
            self._root_program,
            container_id=self._root_id,
            path_prefix=(),
        )
        nodes = {
            node_id: CompositionNode(
                child_ids=tuple(self._children.get(node_id, ())),
                **spec,
            )
            for node_id, spec in self._node_specs.items()
        }
        return NativeCompositionGraph(
            program_name=self._root_program.name,
            root_id=self._root_id,
            nodes=nodes,
            edges=tuple(self._edges),
            untaken_route_labels=tuple(sorted(self._untaken_route_labels)),
        )

    def _add_program_nodes(
        self,
        program: NativeProgram,
        *,
        container_id: str,
        path_prefix: tuple[str, ...],
    ) -> dict[int, str]:
        instructions = program.instructions
        loop_regions = _collect_loop_regions(instructions)
        pc_to_node: dict[int, str] = {}

        def visit_interval(start_pc: int, end_pc: int, parent_id: str, parent_path: tuple[str, ...]) -> None:
            pc = start_pc
            while pc < end_pc and pc < len(instructions):
                instr = instructions[pc]
                if instr.op == "halt" or instr.op == "jump":
                    pc += 1
                    continue

                if instr.op == "parallel":
                    node_id, node_path = self._add_instruction_node(
                        program=program,
                        instr=instr,
                        parent_id=parent_id,
                        path_prefix=parent_path,
                        loop_region=loop_regions.get(pc),
                    )
                    pc_to_node[pc] = node_id
                    merge_pc = _parallel_merge_pc(program, instr)
                    visit_interval(pc + 1, min(merge_pc, end_pc), node_id, node_path)
                    pc = merge_pc
                    continue

                loop_region = loop_regions.get(pc)
                if loop_region is not None:
                    node_id, node_path = self._add_instruction_node(
                        program=program,
                        instr=instr,
                        parent_id=parent_id,
                        path_prefix=parent_path,
                        loop_region=loop_region,
                    )
                    pc_to_node[pc] = node_id
                    visit_interval(
                        loop_region["body_start_pc"],
                        min(loop_region["back_jump_pc"], end_pc - 1) + 1,
                        node_id,
                        node_path,
                    )
                    pc = loop_region["exit_pc"]
                    continue

                node_id, node_path = self._add_instruction_node(
                    program=program,
                    instr=instr,
                    parent_id=parent_id,
                    path_prefix=parent_path,
                    loop_region=None,
                )
                pc_to_node[pc] = node_id
                if instr.op == "subpipeline" and isinstance(instr.subprogram, NativeProgram):
                    self._add_program_nodes(
                        instr.subprogram,
                        container_id=node_id,
                        path_prefix=node_path,
                    )
                pc += 1

        visit_interval(0, len(instructions), container_id, path_prefix)
        self._add_program_edges(program, pc_to_node)
        return pc_to_node

    def _add_instruction_node(
        self,
        *,
        program: NativeProgram,
        instr: NativeInstruction,
        parent_id: str,
        path_prefix: tuple[str, ...],
        loop_region: Mapping[str, int] | None,
    ) -> tuple[str, tuple[str, ...]]:
        stable_id = _stable_id_for_instruction(instr)
        local_segments = _path_segments_for_instruction(instr, stable_id=stable_id)
        path_segments = path_prefix + local_segments
        node_id = _node_id_for_instruction(
            instr,
            program_name=program.name,
            path_segments=path_segments,
        )
        spec = _node_spec_for_instruction(
            instr,
            node_id=node_id,
            parent_id=parent_id,
            path_segments=path_segments,
            stable_id=stable_id,
            loop_region=loop_region,
        )
        self._node_specs[node_id] = spec
        self._children.setdefault(parent_id, []).append(node_id)
        self._children.setdefault(node_id, [])
        untaken = spec.get("untaken_branches", ())
        self._untaken_route_labels.update(str(label) for label in untaken)
        return node_id, path_segments

    def _add_program_edges(self, program: NativeProgram, pc_to_node: Mapping[int, str]) -> None:
        instructions = program.instructions
        for instr in instructions:
            source_id = pc_to_node.get(instr.pc)
            if source_id is None:
                continue

            if instr.op == "decision":
                vocabulary = tuple(sorted(instr.decision_vocabulary))
                for label, target_pc in instr.branches.items():
                    target_id = _resolve_next_node_id(target_pc, instructions, pc_to_node)
                    if target_id is None:
                        continue
                    kind = "loop" if target_pc <= instr.pc else "branch"
                    self._add_edge(source_id, target_id, label=label, kind=kind)
                for label in vocabulary:
                    if label not in instr.branches:
                        self._untaken_route_labels.add(label)
                continue

            if instr.op == "parallel":
                target_id = _resolve_next_node_id(
                    _parallel_merge_pc(program, instr),
                    instructions,
                    pc_to_node,
                )
                if target_id is not None:
                    self._add_edge(source_id, target_id, label="merge", kind="flow")
                continue

            if instr.op == "parallel_map":
                target_id = _resolve_next_node_id(
                    _parallel_map_merge_pc(program, instr),
                    instructions,
                    pc_to_node,
                )
                if target_id is not None:
                    self._add_edge(source_id, target_id, label="merge", kind="flow")
                continue

            start_pc = instr.next_pc if instr.next_pc is not None else instr.pc + 1
            target_id = _resolve_next_node_id(start_pc, instructions, pc_to_node)
            if target_id is not None:
                self._add_edge(source_id, target_id, label="", kind="flow")

    def _add_edge(self, source_id: str, target_id: str, *, label: str, kind: str) -> None:
        key = (source_id, target_id, label, kind)
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self._edges.append(
            CompositionEdge(
                source_id=source_id,
                target_id=target_id,
                label=label,
                kind=kind,
            )
        )


def derive_composition_graph(program: NativeProgram) -> NativeCompositionGraph:
    """Derive a static composition graph from a compiled *program*."""
    return _GraphBuilder(program).build()


def embed_composition_graph(program: NativeProgram) -> dict[str, Any]:
    """Return *program.routing_topology* plus an additive composition graph."""
    topology = dict(program.routing_topology) if program.routing_topology else {}
    topology["composition_graph"] = derive_composition_graph(program).to_dict()
    return topology


def attach_composition_graph(program: NativeProgram) -> NativeProgram:
    """Return a copy of *program* with ``routing_topology.composition_graph`` set."""
    return replace(program, routing_topology=embed_composition_graph(program))


def extract_composition_graph(program: NativeProgram) -> NativeCompositionGraph | None:
    """Deserialize an embedded composition graph from *program*, if present."""
    topology = program.routing_topology
    if not isinstance(topology, Mapping):
        return None
    raw = topology.get("composition_graph")
    if not isinstance(raw, Mapping):
        return None
    return NativeCompositionGraph.from_dict(raw)


def _safe_id(name: str) -> str:
    return name.replace(" ", "_").replace("-", "_").replace("/", "_")


def _stable_id_for_instruction(instr: NativeInstruction) -> str | None:
    if instr.op == "phase" and instr.func is not None:
        meta = get_phase_meta(instr.func)
        if meta is not None:
            stable_id = meta.get("id")
            if isinstance(stable_id, str) and stable_id:
                return stable_id
    if instr.op == "decision" and instr.func is not None:
        meta = get_decision_meta(instr.func)
        if meta is not None:
            stable_id = meta.get("id")
            if isinstance(stable_id, str) and stable_id:
                return stable_id
    if instr.op == "subpipeline" and isinstance(instr.subprogram, NativeProgram):
        return instr.subprogram.stable_id
    return None


def _path_segments_for_instruction(
    instr: NativeInstruction,
    *,
    stable_id: str | None,
) -> tuple[str, ...]:
    """Return stable path segments for *instr*.

    Path segments are anchored by call-site identity and stable_id;
    display name/label is metadata-only per SD2 and MUST NOT influence
    path segments.
    """
    if instr.call_site_path:
        return tuple(str(segment) for segment in instr.call_site_path)
    if stable_id:
        return (stable_id,)
    # Deterministic instruction-based fallback — never the display name.
    return (f"{instr.op}_pc{instr.pc}",)


def _node_id_for_instruction(
    instr: NativeInstruction,
    *,
    program_name: str,
    path_segments: tuple[str, ...],
) -> str:
    if path_segments:
        base = "/".join(path_segments)
    elif instr.name:
        base = instr.name
    else:
        base = instr.op
    return f"__n_{_safe_id(program_name)}_{_safe_id(base)}_pc{instr.pc}"


def _node_spec_for_instruction(
    instr: NativeInstruction,
    *,
    node_id: str,
    parent_id: str,
    path_segments: tuple[str, ...],
    stable_id: str | None,
    loop_region: Mapping[str, int] | None,
) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "node_id": node_id,
        "kind": _kind_for_instruction(instr, loop_region),
        "label": instr.name,
        "stable_id": stable_id,
        "parent_id": parent_id,
        "path_segments": path_segments,
    }

    if instr.op == "phase" and instr.func is not None:
        meta = get_phase_meta(instr.func) or {}
        spec["inputs_schema"] = (
            dict(meta["inputs"]) if isinstance(meta.get("inputs"), Mapping) else None
        )
        spec["outputs_schema"] = (
            dict(meta["outputs"]) if isinstance(meta.get("outputs"), Mapping) else None
        )
        return spec

    if instr.op == "decision":
        vocabulary = tuple(sorted(instr.decision_vocabulary))
        branch_labels = tuple(instr.branches.keys()) + tuple(
            label for label in vocabulary if label not in instr.branches
        )
        spec["branch_labels"] = branch_labels
        spec["decision_vocabulary"] = instr.decision_vocabulary
        spec["untaken_branches"] = tuple(
            label for label in vocabulary if label not in instr.branches
        )
        if loop_region is not None:
            spec["metadata"] = {
                "body_start_pc": loop_region["body_start_pc"],
                "exit_pc": loop_region["exit_pc"],
                "back_jump_pc": loop_region["back_jump_pc"],
            }
        return spec

    if instr.op == "subpipeline" and isinstance(instr.subprogram, NativeProgram):
        spec["inputs_schema"] = (
            dict(instr.subprogram.inputs_schema)
            if isinstance(instr.subprogram.inputs_schema, Mapping) else None
        )
        spec["outputs_schema"] = (
            dict(instr.subprogram.outputs_schema)
            if isinstance(instr.subprogram.outputs_schema, Mapping) else None
        )
        return spec

    if instr.op == "parallel":
        parallel = instr.subprogram if isinstance(instr.subprogram, ParallelInstruction) else None
        spec["parallel_branches"] = parallel.branches if parallel is not None else ()
        spec["parallel_map_has_reducer"] = (
            parallel.reducer is not None if parallel is not None else False
        )
        return spec

    if instr.op == "parallel_map":
        parallel_map = (
            instr.subprogram if isinstance(instr.subprogram, ParallelMapInstruction) else None
        )
        spec["parallel_map_items_ref"] = (
            parallel_map.items_ref if parallel_map is not None else ""
        )
        spec["parallel_map_path_template"] = (
            parallel_map.path_template if parallel_map is not None else ""
        )
        spec["parallel_map_mapper_name"] = (
            parallel_map.mapper_name if parallel_map is not None else ""
        )
        spec["parallel_map_has_reducer"] = (
            parallel_map.reducer is not None if parallel_map is not None else False
        )
        return spec

    return spec


def _kind_for_instruction(
    instr: NativeInstruction,
    loop_region: Mapping[str, int] | None,
) -> CompositionNodeKind:
    if loop_region is not None:
        return CompositionNodeKind.LOOP
    if instr.op == "phase":
        return CompositionNodeKind.PHASE
    if instr.op == "decision":
        return CompositionNodeKind.DECISION
    if instr.op == "subpipeline":
        return CompositionNodeKind.SUBPIPELINE
    if instr.op == "parallel":
        return CompositionNodeKind.PARALLEL
    if instr.op == "parallel_map":
        return CompositionNodeKind.PARALLEL_MAP
    return CompositionNodeKind.PHASE


def _collect_loop_regions(
    instructions: tuple[NativeInstruction, ...],
) -> dict[int, dict[str, int]]:
    regions: dict[int, dict[str, int]] = {}
    for instr in instructions:
        if instr.op != "decision" or not instr.branches:
            continue
        back_jump_pc = None
        for candidate in instructions[instr.pc + 1:]:
            if candidate.op == "jump" and candidate.next_pc == instr.pc:
                back_jump_pc = candidate.pc
        if back_jump_pc is None:
            continue
        body_targets = [
            target_pc
            for target_pc in instr.branches.values()
            if instr.pc < target_pc <= back_jump_pc
        ]
        if not body_targets:
            continue
        exit_targets = [
            target_pc
            for target_pc in instr.branches.values()
            if target_pc > back_jump_pc
        ]
        body_start_pc = min(body_targets)
        exit_pc = min(exit_targets) if exit_targets else back_jump_pc + 1
        regions[instr.pc] = {
            "body_start_pc": body_start_pc,
            "exit_pc": exit_pc,
            "back_jump_pc": back_jump_pc,
        }
    return regions


def _parallel_merge_pc(program: NativeProgram, instr: NativeInstruction) -> int:
    if isinstance(instr.subprogram, ParallelInstruction) and instr.subprogram.merge_pc is not None:
        return instr.subprogram.merge_pc
    if instr.parallel_index is not None and 0 <= instr.parallel_index < len(program.parallel_blocks):
        merge_pc = program.parallel_blocks[instr.parallel_index].merge_pc
        if merge_pc is not None:
            return merge_pc
    return len(program.instructions)


def _parallel_map_merge_pc(program: NativeProgram, instr: NativeInstruction) -> int:
    if (
        isinstance(instr.subprogram, ParallelMapInstruction)
        and instr.subprogram.merge_pc is not None
    ):
        return instr.subprogram.merge_pc
    if (
        instr.parallel_map_index is not None
        and 0 <= instr.parallel_map_index < len(program.parallel_map_blocks)
    ):
        merge_pc = program.parallel_map_blocks[instr.parallel_map_index].merge_pc
        if merge_pc is not None:
            return merge_pc
    return len(program.instructions)


def _resolve_next_node_id(
    start_pc: int,
    instructions: tuple[NativeInstruction, ...],
    pc_to_node: Mapping[int, str],
) -> str | None:
    visited: set[int] = set()
    pc = start_pc
    while 0 <= pc < len(instructions):
        if pc in visited:
            return None
        visited.add(pc)
        if pc in pc_to_node:
            return pc_to_node[pc]
        instr = instructions[pc]
        if instr.op == "halt":
            return None
        if instr.op == "jump":
            pc = instr.next_pc if instr.next_pc is not None else -1
            continue
        pc += 1
    return None
