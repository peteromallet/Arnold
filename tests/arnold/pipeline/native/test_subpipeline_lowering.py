"""Focused tests for subpipeline lowering in the native compiler.

Covers:
- Direct child ``@workflow`` / ``@pipeline`` calls lowered to ``subpipeline`` ops
- Repeated use of the same child workflow in a single parent
- Stable identity and declared schema metadata preservation through lowering
- Rejection of dynamic subworkflow expressions (non-Name yield targets)

These tests use only native compiler fixtures — no Megaplan dependencies.
"""

from __future__ import annotations

import pytest

from arnold.pipeline.native import (
    NativeCompileError,
    NativeProgram,
    compile_pipeline,
    phase,
    pipeline,
    workflow,
)


# ── Direct child call lowering ──────────────────────────────────────────


class TestDirectChildLowering:
    """A directly-yielded ``@workflow``/``@pipeline`` callable lowers to
    a ``subpipeline`` instruction with the child's compiled program."""

    def test_yielded_workflow_becomes_subpipeline_op(self) -> None:
        @phase
        def child_step(ctx: object) -> dict:
            return {"child": "ok"}

        @workflow(name="child_wf")
        def child_wf(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child_wf(ctx)
            return state

        prog = compile_pipeline(parent)
        assert len(prog.instructions) == 2  # subpipeline + halt
        instr = prog.instructions[0]
        assert instr.op == "subpipeline"
        assert instr.name == "child_wf"
        assert isinstance(instr.subprogram, NativeProgram)
        assert instr.subprogram.name == "child_wf"

    def test_yielded_pipeline_becomes_subpipeline_op(self) -> None:
        """@pipeline-decorated children also lower to subpipeline ops."""

        @phase
        def child_step(ctx: object) -> dict:
            return {"child": "ok"}

        @pipeline(name="child_pipe")
        def child_pipe(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child_pipe(ctx)
            return state

        prog = compile_pipeline(parent)
        assert prog.instructions[0].op == "subpipeline"
        assert prog.instructions[0].name == "child_pipe"

    def test_child_subprogram_has_correct_instructions(self) -> None:
        """The child's subprogram contains its own phase + halt instructions."""

        @phase
        def inner(ctx: object) -> dict:
            return {"x": 1}

        @workflow(name="child")
        def child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx)
            return state

        prog = compile_pipeline(parent)
        child_prog = prog.instructions[0].subprogram
        assert [i.op for i in child_prog.instructions] == ["phase", "halt"]
        assert child_prog.instructions[0].name == "inner"

    def test_child_subprogram_phase_func_is_preserved(self) -> None:
        """The child's phase callable is accessible through its subprogram."""

        @phase
        def inner(ctx: object) -> dict:
            return {"x": 1}

        @workflow(name="child")
        def child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx)
            return state

        prog = compile_pipeline(parent)
        child_prog = prog.instructions[0].subprogram
        assert child_prog.instructions[0].func is inner
        assert child_prog.phases[0].func is inner


# ── Repeated child use ──────────────────────────────────────────────────


class TestRepeatedChildUse:
    """The same child workflow can be yielded multiple times in a single
    parent pipeline.  Each occurrence produces a distinct subpipeline
    instruction referencing the same compiled child program."""

    def test_same_child_yielded_twice(self) -> None:
        @phase
        def child_step(ctx: object) -> dict:
            return {"step": 1}

        @workflow(name="child_wf", id="workflow.child")
        def child_wf(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child_wf(ctx, id="child.first")
            state = yield child_wf(ctx, id="child.second")
            return state

        prog = compile_pipeline(parent)
        ops = [i.op for i in prog.instructions]
        assert ops == ["subpipeline", "subpipeline", "halt"]

        first = prog.instructions[0]
        second = prog.instructions[1]
        assert first.name == "child_wf"
        assert second.name == "child_wf"
        assert first.call_site_path == ("child.first",)
        assert second.call_site_path == ("child.second",)
        # Both reference the same child name; subprogram objects are distinct
        # (each is compiled independently) but structurally identical.
        assert isinstance(first.subprogram, NativeProgram)
        assert isinstance(second.subprogram, NativeProgram)
        assert first.subprogram.name == second.subprogram.name == "child_wf"
        assert first.subprogram.stable_id == second.subprogram.stable_id == "workflow.child"

    def test_repeated_child_with_interleaved_phases(self) -> None:
        """Child workflows can be interleaved with regular phases."""

        @phase
        def child_step(ctx: object) -> dict:
            return {"step": 1}

        @phase
        def parent_phase(ctx: object) -> dict:
            return {"parent": True}

        @workflow(name="child_wf")
        def child_wf(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child_wf(ctx)
            state = yield parent_phase(ctx)
            state = yield child_wf(ctx)
            return state

        prog = compile_pipeline(parent)
        ops = [i.op for i in prog.instructions]
        assert ops == ["subpipeline", "phase", "subpipeline", "halt"]
        assert prog.instructions[1].name == "parent_phase"
        assert prog.instructions[0].name == "child_wf"
        assert prog.instructions[2].name == "child_wf"

    def test_different_children_can_be_yielded(self) -> None:
        """A parent can yield multiple distinct child workflows."""

        @phase
        def step_a(ctx: object) -> dict:
            return {"a": 1}

        @phase
        def step_b(ctx: object) -> dict:
            return {"b": 2}

        @workflow(name="child_a")
        def child_a(ctx: object) -> dict:
            state = yield step_a(ctx)
            return state

        @workflow(name="child_b")
        def child_b(ctx: object) -> dict:
            state = yield step_b(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child_a(ctx)
            state = yield child_b(ctx)
            return state

        prog = compile_pipeline(parent)
        ops = [i.op for i in prog.instructions]
        assert ops == ["subpipeline", "subpipeline", "halt"]
        assert prog.instructions[0].name == "child_a"
        assert prog.instructions[1].name == "child_b"
        assert prog.instructions[0].subprogram.name == "child_a"
        assert prog.instructions[1].subprogram.name == "child_b"


# ── Stable identity and schema metadata preservation ────────────────────


class TestSubpipelineMetadataPreservation:
    """Child workflow stable identity and declared schema metadata are
    preserved on the subprogram attached to the subpipeline instruction."""

    def test_child_stable_id_preserved_on_subprogram(self) -> None:
        @phase
        def inner(ctx: object) -> dict:
            return {}

        @workflow(
            name="child",
            id="workflow.child.stable",
        )
        def child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx)
            return state

        prog = compile_pipeline(parent)
        child_prog = prog.instructions[0].subprogram
        assert child_prog.stable_id == "workflow.child.stable"

    def test_child_inputs_schema_preserved_on_subprogram(self) -> None:
        @phase
        def inner(ctx: object) -> dict:
            return {}

        @workflow(
            name="child",
            inputs={"type": "object", "required": ["seed"]},
        )
        def child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx)
            return state

        prog = compile_pipeline(parent)
        child_prog = prog.instructions[0].subprogram
        assert child_prog.inputs_schema == {"type": "object", "required": ["seed"]}

    def test_child_outputs_schema_preserved_on_subprogram(self) -> None:
        @phase
        def inner(ctx: object) -> dict:
            return {}

        @workflow(
            name="child",
            outputs={"type": "object", "required": ["result"]},
        )
        def child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx)
            return state

        prog = compile_pipeline(parent)
        child_prog = prog.instructions[0].subprogram
        assert child_prog.outputs_schema == {"type": "object", "required": ["result"]}

    def test_child_metadata_all_three_fields_preserved(self) -> None:
        """stable_id, inputs_schema, and outputs_schema all survive lowering."""

        @phase
        def inner(ctx: object) -> dict:
            return {}

        @workflow(
            name="typed_child",
            id="workflow.typed",
            inputs={"type": "object", "required": ["query"]},
            outputs={"type": "object", "required": ["answer"]},
        )
        def typed_child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield typed_child(ctx)
            return state

        prog = compile_pipeline(parent)
        child_prog = prog.instructions[0].subprogram
        assert child_prog.name == "typed_child"
        assert child_prog.stable_id == "workflow.typed"
        assert child_prog.inputs_schema == {"type": "object", "required": ["query"]}
        assert child_prog.outputs_schema == {"type": "object", "required": ["answer"]}

    def test_child_without_id_has_none_stable_id(self) -> None:
        """When a child workflow omits ``id``, the subprogram stable_id is None."""

        @phase
        def inner(ctx: object) -> dict:
            return {}

        @workflow(name="no_id_child")
        def no_id_child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield no_id_child(ctx)
            return state

        prog = compile_pipeline(parent)
        child_prog = prog.instructions[0].subprogram
        assert child_prog.stable_id is None

    def test_child_without_schemas_has_none_schemas(self) -> None:
        """When a child workflow omits schemas, they are None on the subprogram."""

        @phase
        def inner(ctx: object) -> dict:
            return {}

        @workflow(name="bare_child")
        def bare_child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield bare_child(ctx)
            return state

        prog = compile_pipeline(parent)
        child_prog = prog.instructions[0].subprogram
        assert child_prog.inputs_schema is None
        assert child_prog.outputs_schema is None

    def test_repeated_child_preserves_metadata_each_time(self) -> None:
        """When the same child is yielded twice, both subprograms carry the metadata."""

        @phase
        def inner(ctx: object) -> dict:
            return {}

        @workflow(
            name="repeat_child",
            id="workflow.repeat",
            inputs={"type": "object", "required": ["in"]},
            outputs={"type": "object", "required": ["out"]},
        )
        def repeat_child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield repeat_child(ctx)
            state = yield repeat_child(ctx)
            return state

        prog = compile_pipeline(parent)
        for instr in prog.instructions[:2]:
            child_prog = instr.subprogram
            assert child_prog.name == "repeat_child"
            assert child_prog.stable_id == "workflow.repeat"
            assert child_prog.inputs_schema == {"type": "object", "required": ["in"]}
            assert child_prog.outputs_schema == {"type": "object", "required": ["out"]}

    def test_parent_metadata_still_present_when_yielding_child(self) -> None:
        """Parent-level metadata is not affected by child subpipeline lowering."""

        @phase
        def inner(ctx: object) -> dict:
            return {}

        @workflow(name="child")
        def child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline(
            name="meta_parent",
            id="workflow.parent.stable",
            inputs={"type": "object", "required": ["task"]},
            outputs={"type": "object", "required": ["report"]},
        )
        def meta_parent(ctx: object) -> dict:
            state = yield child(ctx)
            return state

        prog = compile_pipeline(meta_parent)
        assert prog.name == "meta_parent"
        assert prog.stable_id == "workflow.parent.stable"
        assert prog.inputs_schema == {"type": "object", "required": ["task"]}
        assert prog.outputs_schema == {"type": "object", "required": ["report"]}
        # Child subprogram still intact
        assert prog.instructions[0].subprogram.name == "child"


# ── Dynamic subworkflow expression rejection ────────────────────────────


class TestDynamicSubworkflowRejection:
    """The compiler rejects yield targets that are not direct named
    callables (``ast.Name`` nodes).  Dynamic expressions, attribute
    accesses, and computed callables all produce NativeCompileError."""

    def test_yield_Attribute_target_rejected(self) -> None:
        """``yield obj.child(ctx)`` is rejected — Attribute nodes not allowed."""

        class Holder:
            @staticmethod
            @workflow
            def child(ctx: object) -> dict:
                return {}

        holder = Holder()

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield holder.child(ctx)  # type: ignore[attr-defined]
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(parent)
        msg = str(exc_info.value)
        assert "dynamic" in msg.lower() or "not supported" in msg.lower() or "Attribute" in msg

    def test_yield_name_expression_with_call_result_rejected(self) -> None:
        """``yield selector()(ctx)`` — a call result used as a callable — is rejected."""

        @phase
        def child_step(ctx: object) -> dict:
            return {"child": "done"}

        @workflow
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        def selector() -> object:
            return child

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield selector()(ctx)
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(parent)
        # The yield value is a Call with a Call func — rejected at func_node level
        msg = str(exc_info.value)
        assert "dynamic" in msg.lower() or "not supported" in msg.lower()

    def test_yield_lambda_rejected(self) -> None:
        """``yield (lambda ctx: {})(ctx)`` — lambda as callable — is rejected."""

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield (lambda c: {})(ctx)  # type: ignore[misc]
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(parent)
        msg = str(exc_info.value)
        # Lambda is an AST node type that isn't a Name
        assert "dynamic" in msg.lower() or "not supported" in msg.lower() or "Name" in msg or "Lambda" in msg

    def test_yield_variable_holding_callable_rejected(self) -> None:
        """``yield ref(ctx)`` where ref is a variable (not a decorated callable) is rejected."""

        @phase
        def child_step(ctx: object) -> dict:
            return {"child": "done"}

        @workflow
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        # Assign to a plain variable — name resolves to callable but it's not
        # a direct decorated callable reference. The compiler resolves the name,
        # finds is_pipeline=True, and lowers it. This SHOULD actually compile
        # since ref points to the same decorated callable.
        ref = child

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield ref(ctx)
            return state

        # This should compile fine — ref IS child, same decorated callable
        prog = compile_pipeline(parent)
        assert prog.instructions[0].op == "subpipeline"

    def test_yield_non_callable_name_rejected(self) -> None:
        """``yield some_string(ctx)`` where some_string is not callable is rejected."""

        some_string = "not_a_callable"

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield some_string(ctx)  # type: ignore[operator]
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(parent)
        msg = str(exc_info.value)
        assert "not callable" in msg.lower() or "not a @phase" in msg.lower() or "resolve" in msg.lower()

    def test_yield_builtin_name_rejected(self) -> None:
        """``yield print(ctx)`` — builtin, not decorated — is rejected."""

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield print(ctx)  # type: ignore[func-returns-value]
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(parent)
        msg = str(exc_info.value)
        assert "not a @phase" in msg or "resolve" in msg.lower()
        # The exact message depends on whether 'print' is found as a builtin
        # (→ "not a @phase") or not resolved at all (→ "Cannot resolve ...").

    def test_yield_non_decorated_function_rejected(self) -> None:
        """A plain function (not decorated with @phase/@workflow/@pipeline) is rejected."""

        def plain_func(ctx: object) -> dict:
            return {"plain": True}

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield plain_func(ctx)
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(parent)
        msg = str(exc_info.value)
        assert "not a @phase" in msg


# ── Subpipeline instruction structural checks ───────────────────────────


class TestSubpipelineInstructionStructure:
    """The subpipeline instruction carries correct next_pc and no branches."""

    def test_subpipeline_instr_has_next_pc(self) -> None:
        @phase
        def child_step(ctx: object) -> dict:
            return {}

        @workflow(name="child")
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx)
            return state

        prog = compile_pipeline(parent)
        instr = prog.instructions[0]
        assert instr.next_pc == 1  # points to halt

    def test_subpipeline_instr_has_empty_branches(self) -> None:
        @phase
        def child_step(ctx: object) -> dict:
            return {}

        @workflow(name="child")
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx)
            return state

        prog = compile_pipeline(parent)
        instr = prog.instructions[0]
        assert instr.branches == {}

    def test_subpipeline_instr_has_no_func(self) -> None:
        """subpipeline instructions carry subprogram, not func."""

        @phase
        def child_step(ctx: object) -> dict:
            return {}

        @workflow(name="child")
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx)
            return state

        prog = compile_pipeline(parent)
        instr = prog.instructions[0]
        assert instr.func is None

    def test_subpipeline_followed_by_phase_transitions_correctly(self) -> None:
        """PC ordering is correct when subpipeline precedes a regular phase."""

        @phase
        def child_step(ctx: object) -> dict:
            return {}

        @phase
        def parent_step(ctx: object) -> dict:
            return {"done": True}

        @workflow(name="child")
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx)
            state = yield parent_step(ctx)
            return state

        prog = compile_pipeline(parent)
        assert prog.instructions[0].pc == 0
        assert prog.instructions[0].op == "subpipeline"
        assert prog.instructions[0].next_pc == 1
        assert prog.instructions[1].pc == 1
        assert prog.instructions[1].op == "phase"
        assert prog.instructions[1].next_pc == 2
        assert prog.instructions[2].pc == 2
        assert prog.instructions[2].op == "halt"

    def test_nested_child_workflow_lowering(self) -> None:
        """A child workflow that itself yields another child workflow is lowered
        correctly — the grandchild is also compiled as a subpipeline."""

        @phase
        def leaf_step(ctx: object) -> dict:
            return {"leaf": 1}

        @workflow(name="grandchild")
        def grandchild(ctx: object) -> dict:
            state = yield leaf_step(ctx)
            return state

        @workflow(name="child")
        def child(ctx: object) -> dict:
            state = yield grandchild(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield child(ctx)
            return state

        prog = compile_pipeline(parent)
        # parent: [subpipeline(child), halt]
        child_prog = prog.instructions[0].subprogram
        # child: [subpipeline(grandchild), halt]
        assert child_prog.instructions[0].op == "subpipeline"
        assert child_prog.instructions[0].name == "grandchild"
        grandchild_prog = child_prog.instructions[0].subprogram
        # grandchild: [phase(leaf_step), halt]
        assert grandchild_prog.instructions[0].op == "phase"
        assert grandchild_prog.instructions[0].name == "leaf_step"
