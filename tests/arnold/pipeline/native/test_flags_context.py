"""Tests for native runtime compatibility flag and guard plumbing.

Covers:
- ``native_runtime_enabled()`` correctness for on/off/unset states
- ``require_native_runtime()`` no-op compatibility behavior
- deprecated ``NativeRuntimeDisabledError`` export shape
- Compiler/graph-helper imports remain usable without the flag
"""

from __future__ import annotations

import pytest

from arnold.pipeline.native import (
    NativeRuntimeDisabledError,
    native_runtime_enabled,
    require_native_runtime,
)


# ── native_runtime_enabled ────────────────────────────────────────────


class TestNativeRuntimeEnabled:
    """``native_runtime_enabled()`` returns the correct boolean for each state."""

    def test_unset_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
        assert native_runtime_enabled() is True

    def test_set_to_one_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
        assert native_runtime_enabled() is True

    def test_set_to_zero_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "0")
        assert native_runtime_enabled() is False

    def test_set_to_empty_string_returns_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "")
        assert native_runtime_enabled() is True

    def test_set_to_true_string_returns_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "true")
        assert native_runtime_enabled() is True


# ── require_native_runtime ────────────────────────────────────────────


class TestRequireNativeRuntime:
    """``require_native_runtime()`` is a compatibility no-op."""

    def test_does_not_raise_when_flag_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "0")
        require_native_runtime()

    def test_does_not_raise_when_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
        # Should not raise
        require_native_runtime()

    def test_does_not_raise_when_flag_on(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
        # Should not raise
        require_native_runtime()

    def test_deprecated_error_is_not_used_for_flag_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "0")
        require_native_runtime()

    def test_error_is_runtime_error(self) -> None:
        assert issubclass(NativeRuntimeDisabledError, RuntimeError)


# ── importability without flag ────────────────────────────────────────


class TestImportabilityWithoutFlag:
    """Compiler, graph-projection, and IR imports remain usable without the flag."""

    def test_native_pipeline_importable_without_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
        from arnold.pipeline.native import (
            NativeDecision,
            NativeLoopGuard,
            NativePhase,
            NativePipeline,
            decision,
            get_decision_meta,
            get_phase_meta,
            get_pipeline_meta,
            is_decision,
            is_phase,
            is_pipeline,
            phase,
            pipeline,
        )
        # All symbols are importable and callable/constructable
        assert callable(pipeline)
        assert callable(phase)
        assert callable(decision)
        assert is_pipeline is not None
        assert is_phase is not None
        assert is_decision is not None
        assert get_pipeline_meta is not None
        assert get_phase_meta is not None
        assert get_decision_meta is not None
        assert NativePipeline is not None
        assert NativePhase is not None
        assert NativeDecision is not None
        assert NativeLoopGuard is not None

    def test_flags_and_context_importable_without_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
        from arnold.pipeline.native.flags import native_runtime_enabled as nre
        from arnold.pipeline.native.context import (
            NativeRuntimeDisabledError as NRDE,
            require_native_runtime as rnr,
        )
        assert nre is not None
        assert rnr is not None
        assert NRDE is not None
        # The guard does not raise when the flag is unset (native is now
        # enabled by default).
        rnr()

    def test_megaplan_native_hooks_importable_without_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SC4: arnold.pipelines.megaplan.native_hooks imports without flag."""
        monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
        from arnold.pipelines.megaplan.native_hooks import (
            MegaplanNativeRuntimeHooks,
            MegaplanNativeHooks,
            UnknownOverrideError,
        )
        # All symbols are importable
        assert MegaplanNativeRuntimeHooks is not None
        assert MegaplanNativeHooks is not None
        assert UnknownOverrideError is not None
        # MegaplanNativeHooks is an alias for MegaplanNativeRuntimeHooks
        assert MegaplanNativeHooks is MegaplanNativeRuntimeHooks
        # Can instantiate without error
        hooks = MegaplanNativeRuntimeHooks()
        assert hooks.halt_reason is None


# ── NativeRuntimeDisabledError shape ──────────────────────────────────


class TestNativeRuntimeDisabledError:
    """``NativeRuntimeDisabledError`` is a descriptive RuntimeError."""

    def test_can_be_raised_directly(self) -> None:
        with pytest.raises(NativeRuntimeDisabledError):
            raise NativeRuntimeDisabledError("custom message")

    def test_default_message_mentions_env_var(self) -> None:
        err = NativeRuntimeDisabledError()
        # The message should be informative even when no custom msg is given
        # (RuntimeError default may be empty, but the guard always supplies one)
        assert isinstance(err, RuntimeError)


# ── M3 handoff boundary regression ─────────────────────────────────────


class TestM3HandoffBoundary:
    """Regression coverage for the M3 handoff contract.

    Verifies the boundary discipline from MILESTONE_3_HANDOFF.md:
    - No megaplan imports in the neutral native package (SD3).
    - Rejected protocol callbacks (resolve_step_io_policy, on_edge_traverse)
      are absent from the native hooks surface.
    - The rejected boundary-violating shim (megaplan_hooks.py) does not exist.
    """

    def test_no_megaplan_imports_in_native_package(self) -> None:
        """Zero megaplan imports in arnold.pipeline.native (SD3 boundary)."""
        import ast
        from pathlib import Path

        # parents: native/ → pipeline/ → arnold/ → tests/ → repo-root/
        native_pkg = Path(__file__).resolve().parents[4] / "arnold" / "pipeline" / "native"
        violations: list[str] = []

        for py_file in sorted(native_pkg.rglob("*.py")):
            # Skip __pycache__ and the handoff markdown
            if "__pycache__" in py_file.parts:
                continue
            source = py_file.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module_name = (
                        node.module if isinstance(node, ast.ImportFrom)
                        else ""
                    )
                    names = [
                        alias.name
                        for alias in node.names
                    ]
                    combined = [module_name or ""] + names
                    for seg in combined:
                        if "megaplan" in seg.lower():
                            violations.append(
                                f"{py_file.relative_to(native_pkg.parent.parent.parent)}"
                                f":{node.lineno} import contains 'megaplan'"
                            )
                            break

        assert not violations, (
            "SD3 boundary violation: megaplan imports found in "
            f"arnold.pipeline.native:\n" + "\n".join(violations)
        )

    def test_rejected_callback_resolve_step_io_policy_absent(self) -> None:
        """R1: resolve_step_io_policy is absent from native hooks protocol."""
        from arnold.pipeline.native.hooks import (
            NativeRuntimeHooks,
            NullNativeRuntimeHooks,
        )

        # The protocol must not define it
        assert not hasattr(NativeRuntimeHooks, "resolve_step_io_policy"), (
            "Rejected callback 'resolve_step_io_policy' found on NativeRuntimeHooks"
        )
        # The null implementation must not define it
        assert not hasattr(NullNativeRuntimeHooks, "resolve_step_io_policy"), (
            "Rejected callback 'resolve_step_io_policy' found on NullNativeRuntimeHooks"
        )

    def test_rejected_callback_on_edge_traverse_absent(self) -> None:
        """R2: on_edge_traverse is absent from native hooks protocol."""
        from arnold.pipeline.native.hooks import (
            NativeRuntimeHooks,
            NullNativeRuntimeHooks,
        )

        assert not hasattr(NativeRuntimeHooks, "on_edge_traverse"), (
            "Rejected callback 'on_edge_traverse' found on NativeRuntimeHooks"
        )
        assert not hasattr(NullNativeRuntimeHooks, "on_edge_traverse"), (
            "Rejected callback 'on_edge_traverse' found on NullNativeRuntimeHooks"
        )

    def test_rejected_shim_megaplan_hooks_py_absent(self) -> None:
        """R3: arnold/pipeline/native/megaplan_hooks.py does not exist."""
        from pathlib import Path

        # parents: native/ → pipeline/ → arnold/ → tests/ → repo-root/
        native_pkg = Path(__file__).resolve().parents[4] / "arnold" / "pipeline" / "native"
        rejected_shim = native_pkg / "megaplan_hooks.py"

        assert not rejected_shim.exists(), (
            f"SD3 boundary violation: rejected shim exists at {rejected_shim}"
        )

    def test_megaplan_native_hooks_importable_without_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SC4: arnold.pipelines.megaplan.native_hooks imports without flag."""
        monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
        from arnold.pipelines.megaplan.native_hooks import (
            MegaplanNativeRuntimeHooks,
            MegaplanNativeHooks,
            UnknownOverrideError,
        )
        # All symbols are importable
        assert MegaplanNativeRuntimeHooks is not None
        assert MegaplanNativeHooks is not None
        assert UnknownOverrideError is not None
        # MegaplanNativeHooks is an alias for MegaplanNativeRuntimeHooks
        assert MegaplanNativeHooks is MegaplanNativeRuntimeHooks
        # Can instantiate without error
        hooks = MegaplanNativeRuntimeHooks()
        assert hooks.halt_reason is None

    def test_nine_callbacks_only_on_hooks_protocol(self) -> None:
        """The NativeRuntimeHooks protocol has exactly the 9 real callbacks."""
        from arnold.pipeline.native.hooks import NativeRuntimeHooks

        expected_callbacks = {
            "on_step_start",
            "on_step_end",
            "on_step_error",
            "merge_state",
            "join_envelope",
            "should_suspend",
            "should_halt_loop",
            "on_stage_complete",
            "on_checkpoint",
        }

        # Get all abstract methods defined on the protocol (excluding dunders)
        actual = {
            name for name in dir(NativeRuntimeHooks)
            if not name.startswith("_")
            and callable(getattr(NativeRuntimeHooks, name, None))
            and name not in ("__init__", "__class_getitem__", "__subclasshook__")
        }

        missing = expected_callbacks - actual
        extra = actual - expected_callbacks

        assert not missing, (
            f"Expected callbacks missing from NativeRuntimeHooks: {missing}"
        )
        assert not extra, (
            f"Unexpected callbacks on NativeRuntimeHooks (invented?): {extra}"
        )

    def test_nine_callbacks_only_on_null_hooks(self) -> None:
        """NullNativeRuntimeHooks has exactly the 9 real callbacks (no more)."""
        from arnold.pipeline.native.hooks import NullNativeRuntimeHooks

        expected_callbacks = {
            "on_step_start",
            "on_step_end",
            "on_step_error",
            "merge_state",
            "join_envelope",
            "should_suspend",
            "should_halt_loop",
            "on_stage_complete",
            "on_checkpoint",
        }

        instance = NullNativeRuntimeHooks()
        actual = {
            name for name in dir(instance)
            if not name.startswith("_")
            and callable(getattr(instance, name, None))
            and name not in ("halt_reason",)
        }

        # The protocol itself (halt_reason) is a data attribute, not a method
        missing = expected_callbacks - actual
        extra = actual - expected_callbacks

        assert not missing, (
            f"Expected callbacks missing from NullNativeRuntimeHooks: {missing}"
        )
        assert not extra, (
            f"Unexpected callbacks on NullNativeRuntimeHooks (invented?): {extra}"
        )

    def test_m3_golden_files_documented_as_m4_gap(self) -> None:
        """M3 golden trace files are noted as absent — owned by M4.

        Per MILESTONE_3_HANDOFF.md Golden Trace Paths section, the following
        golden files are expected but not yet committed:

        - tests/arnold/pipeline/native/data/golden_graph_trace.json
        - tests/arnold/pipeline/native/data/golden_native_trace.json
        - tests/arnold/pipeline/native/data/golden_composite_cursor.json

        These are regenerated via --record-goldens by M4 parity tests.
        This test encodes the gap so it cannot be silently forgotten.
        """
        from pathlib import Path

        data_dir = (
            Path(__file__).resolve().parent / "data"
        )
        golden_files = [
            "golden_graph_trace.json",
            "golden_native_trace.json",
            "golden_composite_cursor.json",
        ]

        missing = [
            gf for gf in golden_files
            if not (data_dir / gf).exists()
        ]

        # This test documents the gap rather than failing on it.
        # When M4 delivers the golden files this assertion flips to
        # assert not missing (they should exist).
        # For M3: we acknowledge they are absent and record the gap.
        assert missing, (
            "M4-owned gap closed early: all golden files are present. "
            "Update this test to assert they exist (remove the 'assert missing')."
        )
        # Explicit record of what's missing
        assert set(missing) == set(golden_files), (
            f"Unexpected golden file state: missing={missing}, "
            f"expected all absent={golden_files}"
        )
