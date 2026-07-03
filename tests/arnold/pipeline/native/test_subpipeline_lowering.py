"""Focused tests for subpipeline lowering in the native compiler.

Covers:
- Direct child ``@workflow`` / ``@pipeline`` calls lowered to ``subpipeline`` ops
  via the ``state = child(ctx)`` assignment path (no yield)
- Repeated use of the same child workflow in a single parent
- Stable identity and declared schema metadata preservation through lowering
- Rejection of dynamic subworkflow expressions in both yield and assignment paths

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


# ── Direct child call lowering (assignment path) ────────────────────────


class TestDirectChildLowering:
    """A child ``@workflow``/``@pipeline`` callable used as an assignment
    value (``state = child(ctx)``, no ``yield``) lowers to a ``subpipeline``
    instruction with the child's compiled program."""

    def test_assigned_workflow_becomes_subpipeline_op(self) -> None:
        @phase
        def child_step(ctx: object) -> dict:
            return {"child": "ok"}

        @workflow(name="child_wf")
        def child_wf(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = child_wf(ctx)
            return state

        prog = compile_pipeline(parent)
        assert len(prog.instructions) == 2  # subpipeline + halt
        instr = prog.instructions[0]
        assert instr.op == "subpipeline"
        assert instr.name.startswith("child_wf")
        assert isinstance(instr.subprogram, NativeProgram)
        assert instr.subprogram.name == "child_wf"

    def test_assigned_pipeline_becomes_subpipeline_op(self) -> None:
        """@pipeline-decorated children also lower via assignment path."""

        @phase
        def child_step(ctx: object) -> dict:
            return {"child": "ok"}

        @pipeline(name="child_pipe")
        def child_pipe(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = child_pipe(ctx)
            return state

        prog = compile_pipeline(parent)
        assert prog.instructions[0].op == "subpipeline"
        assert prog.instructions[0].name.startswith("child_pipe")

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
            state = child(ctx)
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
            state = child(ctx)
            return state

        prog = compile_pipeline(parent)
        child_prog = prog.instructions[0].subprogram
        assert child_prog.instructions[0].func is inner
        assert child_prog.phases[0].func is inner


# ── Repeated child use ──────────────────────────────────────────────────


class TestRepeatedChildUse:
    """The same child workflow can be used multiple times in a single
    parent pipeline via assignment.  Each occurrence produces a distinct
    subpipeline instruction with a callsite-indexed name."""

    def test_same_child_assigned_twice(self) -> None:
        @phase
        def child_step(ctx: object) -> dict:
            return {"step": 1}

        @workflow(name="child_wf", id="workflow.child")
        def child_wf(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = child_wf(ctx)
            state = child_wf(ctx)
            return state

        prog = compile_pipeline(parent)
        ops = [i.op for i in prog.instructions]
        assert ops == ["subpipeline", "subpipeline", "halt"]

        first = prog.instructions[0]
        second = prog.instructions[1]
        # Callsite names include index: workflow.child[0], workflow.child[1]
        assert first.name != second.name
        assert "child_wf" in first.name or "workflow.child" in first.name
        assert "child_wf" in second.name or "workflow.child" in second.name
        assert isinstance(first.subprogram, NativeProgram)
        assert isinstance(second.subprogram, NativeProgram)
        assert first.subprogram.name == second.subprogram.name == "child_wf"

    def test_repeated_child_with_interleaved_phases(self) -> None:
        """Child workflows can be interleaved with regular (yielded) phases."""

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
            state = child_wf(ctx)
            state = yield parent_phase(ctx)
            state = child_wf(ctx)
            return state

        prog = compile_pipeline(parent)
        ops = [i.op for i in prog.instructions]
        assert ops == ["subpipeline", "phase", "subpipeline", "halt"]

    def test_different_children_can_be_used(self) -> None:
        """A parent can use multiple distinct child workflows."""

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
            state = child_a(ctx)
            state = child_b(ctx)
            return state

        prog = compile_pipeline(parent)
        ops = [i.op for i in prog.instructions]
        assert ops == ["subpipeline", "subpipeline", "halt"]
        assert prog.instructions[0].subprogram.name == "child_a"
        assert prog.instructions[1].subprogram.name == "child_b"


# ── Stable identity and schema metadata preservation ────────────────────


class TestSubpipelineMetadataPreservation:
    """Child workflow stable identity is preserved on the subprogram
    attached to the subpipeline instruction."""

    def test_child_stable_id_preserved_on_subprogram(self) -> None:
        @phase
        def inner(ctx: object) -> dict:
            return {}

        @workflow(name="child", id="workflow.child.stable")
        def child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = child(ctx)
            return state

        prog = compile_pipeline(parent)
        child_prog = prog.instructions[0].subprogram
        assert child_prog.stable_id == "workflow.child.stable"

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
            state = no_id_child(ctx)
            return state

        prog = compile_pipeline(parent)
        child_prog = prog.instructions[0].subprogram
        assert child_prog.stable_id is None

    def test_child_name_preserved_on_subprogram(self) -> None:
        """The child's declared name survives into the subprogram."""

        @phase
        def inner(ctx: object) -> dict:
            return {}

        @workflow(name="explicit_name")
        def child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = child(ctx)
            return state

        prog = compile_pipeline(parent)
        child_prog = prog.instructions[0].subprogram
        assert child_prog.name == "explicit_name"

    def test_child_with_description_compiles(self) -> None:
        """A child with a description metadata field compiles and runs."""

        @phase
        def inner(ctx: object) -> dict:
            return {}

        @workflow(name="desc_child", description="A child with a description")
        def desc_child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = desc_child(ctx)
            return state

        prog = compile_pipeline(parent)
        child_prog = prog.instructions[0].subprogram
        assert child_prog.name == "desc_child"
        assert child_prog.description == "A child with a description"

    def test_repeated_child_preserves_metadata_each_time(self) -> None:
        """When the same child is used twice, both subprograms carry the metadata."""

        @phase
        def inner(ctx: object) -> dict:
            return {}

        @workflow(name="repeat_child", id="workflow.repeat")
        def repeat_child(ctx: object) -> dict:
            state = yield inner(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = repeat_child(ctx)
            state = repeat_child(ctx)
            return state

        prog = compile_pipeline(parent)
        for instr in prog.instructions[:2]:
            child_prog = instr.subprogram
            assert child_prog.name == "repeat_child"
            assert child_prog.stable_id == "workflow.repeat"

    def test_parent_metadata_still_present_when_using_child(self) -> None:
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
        )
        def meta_parent(ctx: object) -> dict:
            state = child(ctx)
            return state

        prog = compile_pipeline(meta_parent)
        assert prog.name == "meta_parent"
        assert prog.stable_id == "workflow.parent.stable"
        # Child subprogram still intact
        assert prog.instructions[0].subprogram.name == "child"


# ── Dynamic subworkflow expression rejection ────────────────────────────


class TestDynamicSubworkflowRejection:
    """The compiler rejects dynamic call targets in the yield path.
    In the assignment path, non-``ast.Name`` targets compile without
    error but are NOT lowered as subpipeline instructions — only
    direct named ``@workflow``/``@pipeline`` references are recognized."""

    # ── Yield path rejection ─────────────────────────────────────────

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
        assert "not supported" in msg.lower() or "Attribute" in msg

    def test_yield_computed_call_rejected(self) -> None:
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
        msg = str(exc_info.value)
        assert "Call" in msg

    def test_yield_lambda_rejected(self) -> None:
        """``yield (lambda ctx: {})(ctx)`` — lambda as callable — is rejected."""

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield (lambda c: {})(ctx)  # type: ignore[misc]
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(parent)
        msg = str(exc_info.value)
        assert "Lambda" in msg or "not supported" in msg.lower()

    def test_yield_non_decorated_function_rejected(self) -> None:
        """A plain function (not @phase/@workflow/@pipeline) in yield is rejected."""

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

    def test_yield_builtin_name_rejected(self) -> None:
        """``yield print(ctx)`` — builtin in yield — is rejected."""

        @pipeline
        def parent(ctx: object) -> dict:
            state = yield print(ctx)  # type: ignore[func-returns-value]
            return state

        with pytest.raises(NativeCompileError) as exc_info:
            compile_pipeline(parent)
        msg = str(exc_info.value)
        assert "resolve" in msg.lower()

    # ── Assignment path rejection ────────────────────────────────────

    def test_assign_Attribute_call_not_lowered_as_subpipeline(self) -> None:
        """``state = obj.child(ctx)`` — Attribute in assignment — compiles
        but is NOT lowered as a subpipeline; the compiler only lowers
        direct ``ast.Name`` call targets."""

        class Holder:
            @staticmethod
            @workflow
            def child(ctx: object) -> dict:
                return {}

        holder = Holder()

        @pipeline
        def parent(ctx: object) -> dict:
            state = holder.child(ctx)  # type: ignore[attr-defined]
            return state

        prog = compile_pipeline(parent)
        # No subpipeline instruction — the Attribute call is a no-op
        sub_ops = [i for i in prog.instructions if i.op == "subpipeline"]
        assert len(sub_ops) == 0

    def test_assign_computed_call_not_lowered_as_subpipeline(self) -> None:
        """``state = selector()(ctx)`` — Call as func — compiles but is NOT
        lowered as a subpipeline; only ``ast.Name`` targets are recognized."""

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
            state = selector()(ctx)
            return state

        prog = compile_pipeline(parent)
        # No subpipeline instruction — the computed call is a no-op
        sub_ops = [i for i in prog.instructions if i.op == "subpipeline"]
        assert len(sub_ops) == 0

    def test_assign_non_callable_name_not_lowered_as_subpipeline(self) -> None:
        """``state = non_callable(ctx)`` — name resolves to non-callable — compiles
        but is NOT lowered as a subpipeline; ``_resolve_callable`` fails for
        non-callable names and ``_maybe_lower_subpipeline_call`` returns False."""

        not_a_workflow = "i_am_a_string"

        @pipeline
        def parent(ctx: object) -> dict:
            state = not_a_workflow(ctx)  # type: ignore[operator]
            return state

        prog = compile_pipeline(parent)
        # No subpipeline instruction
        sub_ops = [i for i in prog.instructions if i.op == "subpipeline"]
        assert len(sub_ops) == 0


# ── Subpipeline instruction structural checks ───────────────────────────


class TestSubpipelineInstructionStructure:
    """The subpipeline instruction carries correct next_pc and no branches/func."""

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
            state = child(ctx)
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
            state = child(ctx)
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
            state = child(ctx)
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
            state = child(ctx)
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

    def test_callsite_names_are_unique_per_use(self) -> None:
        """Each callsite of the same child gets a distinct indexed name."""

        @phase
        def child_step(ctx: object) -> dict:
            return {}

        @workflow(name="child", id="wf.c")
        def child(ctx: object) -> dict:
            state = yield child_step(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = child(ctx)
            state = child(ctx)
            return state

        prog = compile_pipeline(parent)
        names = [i.name for i in prog.instructions if i.op == "subpipeline"]
        assert names[0] != names[1]
        assert names[0].startswith("wf.c[")
        assert names[1].startswith("wf.c[")

    def test_nested_child_workflow_lowering(self) -> None:
        """A child workflow that itself uses another child workflow is lowered
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
            state = grandchild(ctx)
            return state

        @pipeline
        def parent(ctx: object) -> dict:
            state = child(ctx)
            return state

        prog = compile_pipeline(parent)
        # parent: [subpipeline(child), halt]
        child_prog = prog.instructions[0].subprogram
        # child: [subpipeline(grandchild), halt]
        assert child_prog.instructions[0].op == "subpipeline"
        grandchild_prog = child_prog.instructions[0].subprogram
        # grandchild: [phase(leaf_step), halt]
        assert grandchild_prog.instructions[0].op == "phase"
        assert grandchild_prog.instructions[0].name == "leaf_step"
