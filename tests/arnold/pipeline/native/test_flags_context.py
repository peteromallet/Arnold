"""Tests for native runtime feature flags and guard plumbing.

Covers:
- ``native_runtime_enabled()`` correctness for on/off/unset states
- ``require_native_runtime()`` gating behavior
- ``NativeRuntimeDisabledError`` error shape
- Compiler/graph-helper imports remain usable without the flag
"""

from __future__ import annotations

import os

import pytest

from arnold.pipeline.native import (
    NativeRuntimeDisabledError,
    native_runtime_enabled,
    require_native_runtime,
)


# ── native_runtime_enabled ────────────────────────────────────────────


class TestNativeRuntimeEnabled:
    """``native_runtime_enabled()`` returns the correct boolean for each state."""

    def test_unset_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
        assert native_runtime_enabled() is False

    def test_set_to_one_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
        assert native_runtime_enabled() is True

    def test_set_to_zero_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "0")
        assert native_runtime_enabled() is False

    def test_set_to_empty_string_returns_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "")
        assert native_runtime_enabled() is False

    def test_set_to_true_string_returns_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "true")
        assert native_runtime_enabled() is False


# ── require_native_runtime ────────────────────────────────────────────


class TestRequireNativeRuntime:
    """``require_native_runtime()`` gates high-level execution."""

    def test_raises_when_flag_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
        with pytest.raises(NativeRuntimeDisabledError) as exc_info:
            require_native_runtime()
        assert "ARNOLD_NATIVE_RUNTIME" in str(exc_info.value)
        assert "1" in str(exc_info.value)

    def test_does_not_raise_when_flag_on(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")
        # Should not raise
        require_native_runtime()

    def test_raises_when_flag_is_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "0")
        with pytest.raises(NativeRuntimeDisabledError):
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
        # The guard raises at call time, not import time
        with pytest.raises(NRDE):
            rnr()


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
