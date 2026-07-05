"""Focused tests for shared pack-closure validation."""

from __future__ import annotations

import pytest

from arnold.pipeline.native import (
    ExportEntry,
    PACK_CLOSURE_MAX_DEPTH,
    PackClosureValidationError,
    PackManifest,
    PackRegistry,
    compile_pipeline,
    parallel_map,
    phase,
    pipeline,
    validate_shared_pack_closure,
)
from arnold.pipeline.native.ir import NativeInstruction, NativeProgram
from arnold.pipeline.native.ir import ParallelMapInstruction


@phase
def _noop(ctx: dict) -> dict:
    return ctx


@pipeline(id="workflow.leaf")
def _leaf(ctx: dict):
    yield _noop(ctx)


@pipeline(id="workflow.child")
def _child(ctx: dict):
    yield _leaf(ctx, id="leaf_call")


@pipeline(id="workflow.parent")
def _parent(ctx: dict):
    yield _child(ctx, id="child_call")
    yield parallel_map(items="items", step=_leaf, name="fanout", id="fanout")


def _halt_program(*, name: str, stable_id: str) -> NativeProgram:
    return NativeProgram(
        name=name,
        stable_id=stable_id,
        instructions=(NativeInstruction(pc=0, op="halt"),),
    )


def _nested_depth_program(depth: int) -> NativeProgram:
    child = _halt_program(name=f"workflow_{depth}", stable_id=f"workflow.{depth}")
    for index in range(depth - 1, -1, -1):
        child = NativeProgram(
            name=f"workflow_{index}",
            stable_id=f"workflow.{index}",
            instructions=(
                NativeInstruction(
                    pc=0,
                    op="subpipeline",
                    name=f"child_{index}",
                    subprogram=child,
                ),
                NativeInstruction(pc=1, op="halt"),
            ),
        )
    return child


def _parallel_map_cycle_program() -> NativeProgram:
    root = NativeProgram(
        name="mapper_parent",
        stable_id="workflow.mapper_parent",
        instructions=(
            NativeInstruction(pc=0, op="parallel_map", name="fanout"),
            NativeInstruction(pc=1, op="halt"),
        ),
    )
    child = NativeProgram(
        name="mapper_child",
        stable_id="workflow.mapper_child",
        instructions=(
            NativeInstruction(
                pc=0,
                op="subpipeline",
                name="parent_call",
                subprogram=root,
            ),
            NativeInstruction(pc=1, op="halt"),
        ),
    )
    block = ParallelMapInstruction(
        name="fanout",
        items_ref="items",
        mapper=child,
        mapper_name="mapper_child",
        path_template="fanout/{index}",
        merge_pc=1,
    )
    object.__setattr__(
        root,
        "instructions",
        (
            NativeInstruction(
                pc=0,
                op="parallel_map",
                name="fanout",
                subprogram=block,
                next_pc=1,
            ),
            root.instructions[1],
        ),
    )
    return root


class TestValidateSharedPackClosure:
    def test_accepts_nested_subpipelines_and_parallel_map_workflows(self) -> None:
        program = compile_pipeline(_parent)

        validate_shared_pack_closure(
            program,
            pack_id="library.pack",
            export_stable_id="workflow.parent",
        )

    def test_rejects_subpipeline_cycle(self) -> None:
        recursive = NativeProgram(
            name="recursive",
            stable_id="workflow.recursive",
            instructions=(
                NativeInstruction(pc=0, op="subpipeline", name="recursive"),
                NativeInstruction(pc=1, op="halt"),
            ),
        )
        recursive_instr = NativeInstruction(
            pc=0,
            op="subpipeline",
            name="recursive",
            subprogram=recursive,
        )
        object.__setattr__(recursive, "instructions", (recursive_instr, recursive.instructions[1]))

        with pytest.raises(
            PackClosureValidationError,
            match="pack closure cycle detected.*workflow.recursive -> workflow.recursive",
        ):
            validate_shared_pack_closure(recursive)

    def test_rejects_parallel_map_mapper_cycle(self) -> None:
        program = _parallel_map_cycle_program()

        with pytest.raises(
            PackClosureValidationError,
            match="pack closure cycle detected.*workflow.mapper_parent -> workflow.mapper_child -> workflow.mapper_parent",
        ):
            validate_shared_pack_closure(
                program,
                pack_id="mapper.pack",
                export_stable_id="workflow.mapper_parent",
            )

    def test_rejects_depth_overflow_at_shared_limit(self) -> None:
        program = _nested_depth_program(PACK_CLOSURE_MAX_DEPTH + 1)

        with pytest.raises(
            PackClosureValidationError,
            match=rf"pack closure depth exceeded {PACK_CLOSURE_MAX_DEPTH}",
        ):
            validate_shared_pack_closure(program)


class TestPackRegistryClosureIntegration:
    def test_register_pack_rejects_invalid_closure_without_partial_registration(self) -> None:
        registry = PackRegistry()
        valid_export = ExportEntry(stable_id="workflow.parent", kind="workflow", name="parent")
        invalid_export = ExportEntry(stable_id="workflow.mapper_parent", kind="workflow", name="mapper")
        manifest = PackManifest(
            name="shared_pack",
            version="1.0.0",
            exports=(valid_export, invalid_export),
        )

        with pytest.raises(
            PackClosureValidationError,
            match="workflow.mapper_parent",
        ):
            registry.register_pack(
                manifest,
                {
                    "workflow.parent": compile_pipeline(_parent),
                    "workflow.mapper_parent": _parallel_map_cycle_program(),
                },
            )

        assert registry.registrations_for("workflow.parent") == ()
        assert registry.registrations_for("workflow.mapper_parent") == ()
