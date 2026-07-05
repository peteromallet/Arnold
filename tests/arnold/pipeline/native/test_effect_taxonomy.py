"""Tests for side-effect taxonomy metadata in the native pipeline path.

Covers:
- ``effect_taxonomy`` module: operation/effect-class validation
  and stable ``derive_idempotency_key`` derivation.
- Decorator metadata: ``@phase``/``@step`` with ``operation``,
  ``target``, ``idempotency_key``, ``effect_class`` parameters.
- Compiler propagation: side-effect fields survive round-tripping
  through ``NativePhase`` and ``NativeInstruction`` IR.
- Pure steps remain unchanged (all side-effect fields ``None``).
- Derived idempotency keys are stable across recompilations.
"""

from __future__ import annotations

import pytest

from arnold.pipeline.native.decorators import (
    get_phase_meta,
    is_phase,
    phase,
    step,
)
from arnold.pipeline.native.effect_taxonomy import (
    derive_idempotency_key,
    is_valid_effect_class,
    is_valid_operation,
)


# ── effect_taxonomy unit tests ──────────────────────────────────────


class TestEffectTaxonomy:
    """Unit-level tests for the effect taxonomy module."""

    # ── operation validation ─────────────────────────────────────

    def test_valid_operations_recognised(self) -> None:
        assert is_valid_operation("file_write") is True
        assert is_valid_operation("git_branch_create") is True
        assert is_valid_operation("git_branch_delete") is True
        assert is_valid_operation("git_commit") is True
        assert is_valid_operation("git_force_push") is True
        assert is_valid_operation("git_pr_create") is True
        assert is_valid_operation("git_pr_merge") is True
        assert is_valid_operation("git_push") is True
        assert is_valid_operation("git_worktree_op") is True

    def test_unknown_operation_rejected(self) -> None:
        assert is_valid_operation("bogus") is False
        assert is_valid_operation("") is False
        assert is_valid_operation("FILE_WRITE") is False

    # ── effect-class validation ──────────────────────────────────

    def test_valid_effect_classes_recognised(self) -> None:
        assert is_valid_effect_class("filesystem_mutation") is True
        assert is_valid_effect_class("git_repo_mutation") is True
        assert is_valid_effect_class("network_side_effect") is True
        assert is_valid_effect_class("external_service_call") is True

    def test_unknown_effect_class_rejected(self) -> None:
        assert is_valid_effect_class("bogus") is False
        assert is_valid_effect_class("") is False

    # ── idempotency-key derivation ───────────────────────────────

    def test_derive_with_target(self) -> None:
        key = derive_idempotency_key("root/validate", "file_write", "out/report.json")
        assert key == "root/validate:file_write:out/report.json"

    def test_derive_without_target(self) -> None:
        key = derive_idempotency_key("root/validate", "git_commit")
        assert key == "root/validate:git_commit"

    def test_derive_is_deterministic(self) -> None:
        a = derive_idempotency_key("a/b", "file_write", "x")
        b = derive_idempotency_key("a/b", "file_write", "x")
        assert a == b

    def test_different_paths_produce_different_keys(self) -> None:
        k1 = derive_idempotency_key("root/a", "file_write", "f")
        k2 = derive_idempotency_key("root/b", "file_write", "f")
        assert k1 != k2

    def test_different_operations_produce_different_keys(self) -> None:
        k1 = derive_idempotency_key("root/a", "file_write", "f")
        k2 = derive_idempotency_key("root/a", "git_commit", "f")
        assert k1 != k2


# ── Decorator metadata tests ────────────────────────────────────────


class TestSideEffectDecoratorMetadata:
    """Side-effect metadata is attached by ``@phase``/``@step``."""

    def test_phase_with_operation_and_target(self) -> None:
        @phase(operation="file_write", target="report.json")
        def write_step(ctx):
            return {"ok": True}

        meta = get_phase_meta(write_step)
        assert meta is not None
        assert meta["operation"] == "file_write"
        assert meta["target"] == "report.json"
        assert meta["idempotency_key"] is None  # not specified
        assert meta["effect_class"] is None  # not specified

    def test_phase_with_all_side_effect_fields(self) -> None:
        @phase(
            operation="git_commit",
            target="main",
            idempotency_key="explicit-key-42",
            effect_class="git_repo_mutation",
        )
        def commit_step(ctx):
            return {"ok": True}

        meta = get_phase_meta(commit_step)
        assert meta is not None
        assert meta["operation"] == "git_commit"
        assert meta["target"] == "main"
        assert meta["idempotency_key"] == "explicit-key-42"
        assert meta["effect_class"] == "git_repo_mutation"

    def test_step_alias_forwards_side_effect_metadata(self) -> None:
        @step(operation="git_branch_create", target="feature/x")
        def branch_step(ctx):
            return {"ok": True}

        meta = get_phase_meta(branch_step)
        assert meta is not None
        assert meta["operation"] == "git_branch_create"
        assert meta["target"] == "feature/x"

    def test_pure_phase_has_no_side_effect_metadata(self) -> None:
        @phase
        def pure(ctx):
            return {"ok": True}

        meta = get_phase_meta(pure)
        assert meta is not None
        assert meta["operation"] is None
        assert meta["target"] is None
        assert meta["idempotency_key"] is None
        assert meta["effect_class"] is None

    def test_pure_step_has_no_side_effect_metadata(self) -> None:
        @step
        def pure(ctx):
            return {"ok": True}

        meta = get_phase_meta(pure)
        assert meta is not None
        assert meta["operation"] is None
        assert meta["target"] is None
        assert meta["idempotency_key"] is None
        assert meta["effect_class"] is None

    def test_is_phase_still_works_with_side_effect_metadata(self) -> None:
        @phase(operation="file_write", target="out.txt")
        def write_step(ctx):
            return {"ok": True}

        assert is_phase(write_step) is True

    def test_phase_without_callable_parens_works(self) -> None:
        @phase
        def auto(ctx):
            return {"ok": True}

        assert is_phase(auto) is True
        meta = get_phase_meta(auto)
        assert meta is not None
        assert meta["name"] == "auto"


# ── Compiler propagation tests ──────────────────────────────────────


class TestCompilerSideEffectPropagation:
    """Side-effect metadata survives compilation into NativePhase/NativeInstruction."""

    def test_side_effecting_phase_metadata_in_compiled_ir(self) -> None:
        from arnold.pipeline.native.compiler import compile_pipeline
        from arnold.pipeline.native.decorators import pipeline as pline

        @phase(operation="file_write", target="report.json", effect_class="filesystem_mutation")
        def write_report(ctx):
            return {"ok": True}

        @pline
        def my_pipe():
            state = yield write_report(ctx)

        prog = compile_pipeline(my_pipe)

        # Find the phase instruction
        phase_instrs = [i for i in prog.instructions if i.op == "phase"]
        assert len(phase_instrs) == 1
        instr = phase_instrs[0]
        assert instr.operation == "file_write"
        assert instr.target == "report.json"
        assert instr.effect_class == "filesystem_mutation"
        # No explicit key => derived from (step_path, operation, target)
        assert instr.idempotency_key is not None
        assert instr.idempotency_key.startswith("my_pipe/")
        assert ":file_write:report.json" in instr.idempotency_key

        # Check NativePhase also carries the metadata
        write_phases = [p for p in prog.phases if p.name == "write_report"]
        assert len(write_phases) == 1
        ph = write_phases[0]
        assert ph.operation == "file_write"
        assert ph.target == "report.json"
        assert ph.effect_class == "filesystem_mutation"
        assert ph.idempotency_key is not None

    def test_pure_phase_has_no_side_effect_in_compiled_ir(self) -> None:
        from arnold.pipeline.native.compiler import compile_pipeline
        from arnold.pipeline.native.decorators import pipeline as pline

        @phase
        def pure(ctx):
            return {"ok": True}

        @pline
        def my_pipe():
            state = yield pure(ctx)

        prog = compile_pipeline(my_pipe)

        phase_instrs = [i for i in prog.instructions if i.op == "phase"]
        assert len(phase_instrs) == 1
        instr = phase_instrs[0]
        assert instr.operation is None
        assert instr.target is None
        assert instr.idempotency_key is None
        assert instr.effect_class is None

        pure_phases = [p for p in prog.phases if p.name == "pure"]
        assert len(pure_phases) == 1
        ph = pure_phases[0]
        assert ph.operation is None
        assert ph.target is None
        assert ph.idempotency_key is None
        assert ph.effect_class is None

    def test_mixed_pipeline_pure_and_side_effecting(self) -> None:
        from arnold.pipeline.native.compiler import compile_pipeline
        from arnold.pipeline.native.decorators import pipeline as pline

        @phase(operation="git_commit", target="main", effect_class="git_repo_mutation")
        def commit_step(ctx):
            return {"ok": True}

        @phase
        def clean_step(ctx):
            return {"ok": True}

        @pline
        def my_pipe():
            state = yield commit_step(ctx)
            state = yield clean_step(ctx)

        prog = compile_pipeline(my_pipe)

        commit_instrs = [i for i in prog.instructions if i.name == "commit_step"]
        clean_instrs = [i for i in prog.instructions if i.name == "clean_step"]
        assert len(commit_instrs) == 1
        assert len(clean_instrs) == 1

        assert commit_instrs[0].operation == "git_commit"
        assert commit_instrs[0].effect_class == "git_repo_mutation"

        assert clean_instrs[0].operation is None
        assert clean_instrs[0].effect_class is None

    def test_explicit_idempotency_key_survives_compilation(self) -> None:
        from arnold.pipeline.native.compiler import compile_pipeline
        from arnold.pipeline.native.decorators import pipeline as pline

        @phase(operation="file_write", target="out.log", idempotency_key="explicit-key-99")
        def log_step(ctx):
            return {"ok": True}

        @pline
        def my_pipe():
            state = yield log_step(ctx)

        prog = compile_pipeline(my_pipe)

        log_instrs = [i for i in prog.instructions if i.name == "log_step"]
        assert len(log_instrs) == 1
        assert log_instrs[0].idempotency_key == "explicit-key-99"

    def test_derived_idempotency_key_is_stable(self) -> None:
        from arnold.pipeline.native.compiler import compile_pipeline
        from arnold.pipeline.native.decorators import pipeline as pline

        @phase(operation="file_write", target="f.txt")
        def write_step(ctx):
            return {"ok": True}

        @pline
        def stable_pipe():
            state = yield write_step(ctx)

        prog1 = compile_pipeline(stable_pipe)
        prog2 = compile_pipeline(stable_pipe)

        key1 = [i for i in prog1.instructions if i.name == "write_step"][0].idempotency_key
        key2 = [i for i in prog2.instructions if i.name == "write_step"][0].idempotency_key
        assert key1 == key2
        assert key1 is not None
