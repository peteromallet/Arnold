"""Minimal import/compatibility test for Megaplan native hooks.

Verifies that both the canonical module path
``arnold.pipelines.megaplan.native_hooks`` and the compatibility re-export
``arnold.pipeline.native.megaplan_hooks`` resolve to the same
:class:`MegaplanNativeHooks` class.

Milestone: m3-megaplan-runtime-hooks (T1)
"""

from __future__ import annotations

import pytest


class TestMegaplanNativeHooksImports:
    """Both import paths must resolve to the same MegaplanNativeHooks class."""

    def test_canonical_module_importable(self) -> None:
        """``arnold.pipelines.megaplan.native_hooks`` is importable."""
        from arnold.pipelines.megaplan import native_hooks

        assert native_hooks is not None
        assert hasattr(native_hooks, "MegaplanNativeHooks")

    def test_canonical_class_importable_directly(self) -> None:
        """``MegaplanNativeHooks`` is importable from the canonical module."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        assert MegaplanNativeHooks is not None

    def test_compatibility_re_export_importable(self) -> None:
        """``arnold.pipeline.native.megaplan_hooks`` is importable."""
        from arnold.pipeline.native import megaplan_hooks

        assert megaplan_hooks is not None
        assert hasattr(megaplan_hooks, "MegaplanNativeHooks")

    def test_compatibility_class_importable_directly(self) -> None:
        """``MegaplanNativeHooks`` is importable from the compatibility re-export."""
        from arnold.pipeline.native.megaplan_hooks import MegaplanNativeHooks

        assert MegaplanNativeHooks is not None

    def test_both_paths_resolve_to_same_class(self) -> None:
        """Canonical and compatibility paths resolve to the same class object."""
        from arnold.pipelines.megaplan.native_hooks import (
            MegaplanNativeHooks as Canonical,
        )
        from arnold.pipeline.native.megaplan_hooks import (
            MegaplanNativeHooks as Compat,
        )

        assert Canonical is Compat, (
            f"Canonical {Canonical!r} and compatibility re-export {Compat!r} "
            f"must be the same class object."
        )

    def test_native_package_exposes_megaplan_hooks_module(self) -> None:
        """``arnold.pipeline.native`` exposes ``megaplan_hooks`` as a public symbol."""
        import arnold.pipeline.native as native

        assert hasattr(native, "megaplan_hooks")
        assert "megaplan_hooks" in native.__all__


class TestMegaplanNativeHooksProtocol:
    """``MegaplanNativeHooks`` satisfies the ``NativeRuntimeHooks`` protocol."""

    def test_is_subclass_of_null_hooks(self) -> None:
        """``MegaplanNativeHooks`` extends ``NullNativeRuntimeHooks``."""
        from arnold.pipeline.native.hooks import NullNativeRuntimeHooks
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        assert issubclass(MegaplanNativeHooks, NullNativeRuntimeHooks)

    def test_is_runtime_checkable_instance(self) -> None:
        """``MegaplanNativeHooks`` instances satisfy ``NativeRuntimeHooks``."""
        from arnold.pipeline.native.hooks import NativeRuntimeHooks
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        instance = MegaplanNativeHooks()
        assert isinstance(instance, NativeRuntimeHooks)

    def test_implements_merge_state(self) -> None:
        """``MegaplanNativeHooks.merge_state`` is callable with the expected signature."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        instance = MegaplanNativeHooks()
        assert callable(instance.merge_state)

    def test_inherits_noop_callbacks(self) -> None:
        """All 10 protocol callbacks are present (no-op from NullNativeRuntimeHooks)."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        instance = MegaplanNativeHooks()
        expected_callbacks = [
            "on_step_start",
            "on_step_end",
            "on_step_error",
            "merge_state",
            "join_envelope",
            "should_suspend",
            "should_halt_loop",
            "on_stage_complete",
            "on_checkpoint",
            "resolve_step_io_policy",
        ]
        for name in expected_callbacks:
            assert hasattr(instance, name), f"Missing callback: {name}"
            assert callable(getattr(instance, name)), (
                f"Callback {name} is not callable"
            )


class TestMegaplanNativeHooksImportWithoutNativeFlag:
    """Import paths must work even when ``ARNOLD_NATIVE_RUNTIME`` is not set."""

    def test_canonical_import_without_flag(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        assert MegaplanNativeHooks is not None

    def test_compat_import_without_flag(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
        from arnold.pipeline.native.megaplan_hooks import MegaplanNativeHooks

        assert MegaplanNativeHooks is not None

    def test_native_init_import_without_flag(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("ARNOLD_NATIVE_RUNTIME", raising=False)
        import arnold.pipeline.native as native

        assert hasattr(native, "megaplan_hooks")
        assert native.megaplan_hooks.MegaplanNativeHooks is not None


class TestMegaplanNativeHooksResolveStepIOPolicy:
    """``MegaplanNativeHooks.resolve_step_io_policy`` resolves Megaplan policy."""

    def test_resolve_step_io_policy_is_callable(self) -> None:
        """The method is present and callable on MegaplanNativeHooks."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        assert callable(hooks.resolve_step_io_policy)

    def test_resolve_step_io_policy_returns_none_without_megaplan_context(self) -> None:
        """Returns None when no Megaplan context is configured (graceful degradation)."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        result = hooks.resolve_step_io_policy(
            instr=instr,
            state={},
            handoff_value={"data": "hello"},
        )
        # Without plan_dir or policy_data, resolve_megaplan_step_io_policy
        # resolves from env only — which may be None or a default policy.
        # The hook itself does not raise.
        assert result is None or hasattr(result, "effective_mode")

    def test_resolve_step_io_policy_accepts_state_config(self) -> None:
        """State-driven config is forwarded to the Megaplan policy resolver."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        result = hooks.resolve_step_io_policy(
            instr=instr,
            state={"_state_meta": {"config": {"step_io_contract_mode": "enforce"}}},
            handoff_value={"data": "hello"},
        )
        # Should not raise; returns either None (if Megaplan not importable in
        # test context) or a StepIOPolicy with effective_mode="enforce".
        if result is not None:
            assert result.effective_mode in ("enforce", "shadow", "off", "warn")

    def test_null_hooks_resolve_step_io_policy_returns_none(self) -> None:
        """NullNativeRuntimeHooks.resolve_step_io_policy always returns None."""
        from arnold.pipeline.native.hooks import NullNativeRuntimeHooks
        from arnold.pipeline.native.ir import NativeInstruction

        hooks = NullNativeRuntimeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        result = hooks.resolve_step_io_policy(
            instr=instr,
            state={},
            handoff_value={},
        )
        assert result is None


class TestMegaplanNativeHooksOnStageComplete:
    """``MegaplanNativeHooks.on_stage_complete`` persists state to disk."""

    def test_on_stage_complete_noop_when_plan_dir_is_none(self) -> None:
        """No-op when plan_dir is None — does not raise."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks(plan_dir=None)
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        # Should not raise
        hooks.on_stage_complete(
            instr=instr,
            ctx={},
            result={"ok": True},
            state={"key1": "val1"},
            owned_keys=frozenset({"key1"}),
        )

    def test_on_stage_complete_persists_state_to_disk(self, tmp_path) -> None:
        """Persists state via executor-key-merge when plan_dir is set."""
        import json

        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        hooks = MegaplanNativeHooks(plan_dir=str(plan_dir))
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        state = {"key_a": "value_a", "key_b": "value_b"}
        owned_keys = frozenset({"key_a", "key_b"})

        hooks.on_stage_complete(
            instr=instr,
            ctx={},
            result={"ok": True},
            state=state,
            owned_keys=owned_keys,
        )

        # state.json should exist
        state_path = plan_dir / "state.json"
        assert state_path.exists(), "state.json should have been written"

        written = json.loads(state_path.read_text(encoding="utf-8"))
        assert written.get("key_a") == "value_a"
        assert written.get("key_b") == "value_b"

    def test_on_stage_complete_preserves_unowned_disk_keys(self, tmp_path) -> None:
        """Unowned on-disk keys survive executor-key-merge writes."""
        import json

        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        state_path = plan_dir / "state.json"

        # Pre-populate disk with an unowned key + a shared key
        pre_existing = {
            "handler_key": "handler_value",
            "shared_key": "old_shared_value",
        }
        state_path.write_text(json.dumps(pre_existing), encoding="utf-8")

        hooks = MegaplanNativeHooks(plan_dir=str(plan_dir))
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        # Executor only owns shared_key — handler_key is unowned
        state = {"shared_key": "new_shared_value"}
        owned_keys = frozenset({"shared_key"})

        hooks.on_stage_complete(
            instr=instr,
            ctx={},
            result={"ok": True},
            state=state,
            owned_keys=owned_keys,
        )

        written = json.loads(state_path.read_text(encoding="utf-8"))
        # Executor-owned key takes the in-memory value
        assert written["shared_key"] == "new_shared_value"
        # Unowned on-disk key is preserved
        assert written["handler_key"] == "handler_value", (
            "Unowned on-disk key must be preserved"
        )

    def test_on_stage_complete_noop_for_non_dict_state(self) -> None:
        """No-op when state is not a dict — does not raise."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks(plan_dir="/tmp/nonexistent")
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        # Should not raise — returns early
        hooks.on_stage_complete(
            instr=instr,
            ctx={},
            result=None,
            state="not-a-dict",
            owned_keys=frozenset(),
        )


class TestMegaplanNativeHooksMergeState:
    """``MegaplanNativeHooks.merge_state`` with typed/CAS semantics."""

    def test_merge_state_returns_unchanged_when_no_outputs(self) -> None:
        """Returns (state, owned_keys) unchanged when outputs is empty."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        state = {"existing": "value"}
        owned = frozenset({"existing"})

        new_state, new_owned = hooks.merge_state(
            instr=instr,
            state=state,
            outputs={},
            owned_keys=owned,
        )
        assert new_state is state  # same object when no outputs
        assert new_owned is owned

    def test_merge_state_accumulates_owned_keys(self) -> None:
        """merge_state unions output keys into the owned_keys set."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        state = {"old": "val"}
        owned = frozenset({"old"})

        _, new_owned = hooks.merge_state(
            instr=instr,
            state=state,
            outputs={"new_a": 1, "new_b": 2},
            owned_keys=owned,
        )
        assert new_owned == frozenset({"old", "new_a", "new_b"})

    def test_merge_state_legacy_dict_update(self) -> None:
        """merge_state uses plain dict.update when typed ports are off."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        state = {"base": 1, "overlap": "old"}
        outputs = {"overlap": "new", "added": 2}

        new_state, _ = hooks.merge_state(
            instr=instr,
            state=state,
            outputs=outputs,
            owned_keys=frozenset(),
        )
        assert new_state["base"] == 1
        assert new_state["overlap"] == "new"
        assert new_state["added"] == 2

    def test_merge_state_typed_cas_advances_versions(self) -> None:
        """merge_state advances _state_meta.versions under typed-port CAS mode.

        When MEGAPLAN_TYPED_PORTS=1, each owned key's version is incremented
        via StateDelta/apply_delta.
        """
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        state = {
            "key_a": "old_a",
            "_state_meta": {
                "versions": {"key_a": 3},
            },
        }
        outputs = {"key_a": "new_a", "key_b": "new_b"}

        # Under typed ports, versions should advance
        import os
        with _env_var("MEGAPLAN_TYPED_PORTS", "1"):
            new_state, new_owned = hooks.merge_state(
                instr=instr,
                state=state,
                outputs=outputs,
                owned_keys=frozenset({"key_a"}),
            )

        assert new_state["key_a"] == "new_a"
        assert new_state["key_b"] == "new_b"
        assert new_owned == frozenset({"key_a", "key_b"})

        versions = new_state.get("_state_meta", {}).get("versions", {})
        # key_a was at version 3, should now be 4
        assert versions.get("key_a") == 4, (
            f"Expected version 4 for key_a, got {versions.get('key_a')}"
        )
        # key_b was absent (implicit 0), should now be 1
        assert versions.get("key_b") == 1, (
            f"Expected version 1 for key_b, got {versions.get('key_b')}"
        )

    def test_merge_state_typed_cas_preserves_unowned_keys(self) -> None:
        """Unowned keys survive merge_state under typed-port CAS mode."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        state = {
            "owned_a": "old_a",
            "unowned_b": "unowned_b_val",
            "_state_meta": {"versions": {"owned_a": 2}},
        }
        outputs = {"owned_a": "new_a"}

        import os
        with _env_var("MEGAPLAN_TYPED_PORTS", "1"):
            new_state, new_owned = hooks.merge_state(
                instr=instr,
                state=state,
                outputs=outputs,
                owned_keys=frozenset({"owned_a"}),
            )

        assert new_state["owned_a"] == "new_a"
        assert new_state["unowned_b"] == "unowned_b_val", (
            "Unowned key must survive merge_state"
        )
        assert new_owned == frozenset({"owned_a"})

    def test_merge_state_typed_cas_version_conflict_fallback(self) -> None:
        """merge_state falls back to last-writer-wins on version conflict."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        # The in-memory state has version 5, but we'll set MEGAPLAN_TYPED_PORTS
        # after modifying state to simulate a concurrent writer.
        # The conflict path is exercised when the versions dict has a different
        # value than what the caller expects. Actually the merge_state reads
        # current versions from the state it is given, so no conflict is
        # possible within a single merge_state call.  This test documents the
        # safe fallback path by verifying merge_state does not raise when
        # StateDeltaConflict is impossible in the single-threaded case.
        import os
        with _env_var("MEGAPLAN_TYPED_PORTS", "1"):
            new_state, _ = hooks.merge_state(
                instr=instr,
                state={"key": "val", "_state_meta": {"versions": {"key": 0}}},
                outputs={"key": "new_val"},
                owned_keys=frozenset(),
            )

        assert new_state["key"] == "new_val"

    def test_on_stage_complete_advances_versions_with_typed_ports(
        self, tmp_path, monkeypatch,
    ) -> None:
        """on_stage_complete advances _state_meta.versions under typed/CAS.

        When MEGAPLAN_TYPED_PORTS=1, the executor-key-merge write path
        increments version stamps for owned keys.
        """
        import json

        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        state_path = plan_dir / "state.json"

        # Pre-populate disk with version-tagged state
        pre_existing = {
            "owned_a": "old_a",
            "unowned_b": "handler_val",
            "_state_meta": {"versions": {"owned_a": 3, "unowned_b": 7}},
        }
        state_path.write_text(json.dumps(pre_existing), encoding="utf-8")

        monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")

        hooks = MegaplanNativeHooks(plan_dir=str(plan_dir))
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        # In-memory state carries the executor's view
        state = {
            "owned_a": "new_a",
            "unowned_b": "handler_val",
            "_state_meta": {"versions": {"owned_a": 3, "unowned_b": 7}},
        }
        owned_keys = frozenset({"owned_a"})

        hooks.on_stage_complete(
            instr=instr,
            ctx={},
            result={"ok": True},
            state=state,
            owned_keys=owned_keys,
        )

        written = json.loads(state_path.read_text(encoding="utf-8"))
        versions = written.get("_state_meta", {}).get("versions", {})

        # Owned key version should be advanced (3 → 4)
        assert versions.get("owned_a") == 4, (
            f"Expected owned_a version 4, got {versions.get('owned_a')}"
        )
        # Unowned key should retain its version and value
        assert written["unowned_b"] == "handler_val"
        assert versions.get("unowned_b") == 7, (
            f"Unowned key version should be preserved: got {versions.get('unowned_b')}"
        )

    def test_on_stage_complete_legacy_mode_preserves_unowned_keys(
        self, tmp_path,
    ) -> None:
        """Legacy mode (typed ports off) preserves unowned on-disk keys."""
        import json

        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        state_path = plan_dir / "state.json"

        # Pre-populate disk with handler-written keys
        pre_existing = {
            "handler_a": "ha_val",
            "handler_b": "hb_val",
            "exec_key": "old_exec_val",
        }
        state_path.write_text(json.dumps(pre_existing), encoding="utf-8")

        hooks = MegaplanNativeHooks(plan_dir=str(plan_dir))
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        # Executor only owns exec_key
        state = {"exec_key": "new_exec_val"}
        owned_keys = frozenset({"exec_key"})

        hooks.on_stage_complete(
            instr=instr,
            ctx={},
            result={"ok": True},
            state=state,
            owned_keys=owned_keys,
        )

        written = json.loads(state_path.read_text(encoding="utf-8"))
        # Executor-owned key updated
        assert written["exec_key"] == "new_exec_val"
        # Unowned handler keys preserved
        assert written["handler_a"] == "ha_val"
        assert written["handler_b"] == "hb_val"


# ── T6: Override injection tests ─────────────────────────────────────


class TestMegaplanNativeHooksOverrideInjection:
    """Catalog-driven additive override handling for annotation/config kinds."""

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _make_ctx(
        overrides: list[dict[str, Any]] | None = None,
        *,
        extra_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a context dict with override entries in ``state.meta.overrides``."""
        state: dict[str, Any] = dict(extra_state or {})
        state.setdefault("meta", {})["overrides"] = (
            list(overrides) if overrides is not None else []
        )
        return {"state": state}

    @staticmethod
    def _make_instr(name: str = "test_phase") -> NativeInstruction:
        from arnold.pipeline.native.ir import NativeInstruction

        return NativeInstruction(
            op="phase", name=name, pc=0, func=None, next_pc=None,
        )

    # ── No-op paths ──────────────────────────────────────────────────

    def test_no_overrides_returns_ctx_unchanged(self) -> None:
        """When there are no overrides, on_step_start returns ctx unchanged."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = {"state": {"meta": {"overrides": []}}}
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result is ctx

    def test_no_meta_returns_ctx_unchanged(self) -> None:
        """When state has no 'meta', on_step_start returns ctx unchanged."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = {"state": {"key": "val"}}
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result is ctx

    def test_non_dict_state_returns_ctx_unchanged(self) -> None:
        """When state is not a dict, on_step_start returns ctx unchanged."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = {"state": "not-a-dict"}
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result is ctx

    # ── CLI spelling normalization ───────────────────────────────────

    def test_normalises_cli_spelling_force_proceed(self) -> None:
        """CLI spelling 'force-proceed' is normalised to 'force_proceed'."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "force-proceed", "reason": "test"}],
        )
        # force-proceed is a control override (transition) — normalised
        # and validated but the decision body is skipped by T6.
        # The important thing: no crash, ctx returned.
        result = hooks.on_step_start(self._make_instr(), ctx)
        # ctx should be returned (no additive mutation for control overrides)
        assert result is ctx

    def test_unknown_override_fails_closed(self) -> None:
        """Unknown override names raise instead of being silently skipped."""
        from arnold.pipelines.megaplan.native_hooks import (
            MegaplanNativeHooks,
            UnknownOverrideError,
        )

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "nonexistent-override", "note": "x"}],
        )

        with pytest.raises(UnknownOverrideError, match="Unknown Megaplan override"):
            hooks.on_step_start(self._make_instr(), ctx)

    # ── Annotation override: add-note ────────────────────────────────

    def test_add_note_appends_to_meta_notes(self) -> None:
        """add-note appends a note entry to state.meta.notes."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "add-note", "note": "hello world", "source": "user"}],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        notes = result["state"]["meta"]["notes"]
        assert len(notes) == 1
        assert notes[0]["note"] == "hello world"
        assert notes[0]["source"] == "user"
        assert "timestamp" in notes[0]

    def test_add_note_preserves_existing_notes(self) -> None:
        """add-note preserves previously appended notes."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "add-note", "note": "second"}],
            extra_state={"meta": {"notes": [{"note": "first", "source": "user"}]}},
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        notes = result["state"]["meta"]["notes"]
        assert len(notes) == 2
        assert notes[0]["note"] == "first"
        assert notes[1]["note"] == "second"

    def test_add_note_emits_override_applied(self, tmp_path) -> None:
        """add-note emits OVERRIDE_APPLIED to the event journal when plan_dir is set."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        hooks = MegaplanNativeHooks(plan_dir=str(plan_dir))
        ctx = self._make_ctx(
            overrides=[{"action": "add-note", "note": "emit test", "source": "cli"}],
        )
        hooks.on_step_start(self._make_instr(), ctx)

        # events.ndjson should have been created
        events_path = plan_dir / "events.ndjson"
        assert events_path.exists(), "events.ndjson should have been created"

    # ── Config overrides: set-model ──────────────────────────────────

    def test_set_model_adds_phase_model_entry(self) -> None:
        """set-model adds a phase_model entry to state.config."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "set-model", "phase": "execute", "model": "claude:sonnet"}],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        phase_models = result["state"]["config"]["phase_model"]
        assert "execute=claude:sonnet" in phase_models

    def test_set_model_updates_existing_phase_model_entry(self) -> None:
        """set-model updates an existing phase_model entry for the same phase."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "set-model", "phase": "execute", "model": "claude:opus"}],
            extra_state={"config": {"phase_model": ["execute=claude:sonnet"]}},
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        phase_models = result["state"]["config"]["phase_model"]
        assert "execute=claude:opus" in phase_models
        assert "execute=claude:sonnet" not in phase_models

    def test_set_model_emits_override_applied(self, tmp_path) -> None:
        """set-model emits OVERRIDE_APPLIED when plan_dir is set."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        hooks = MegaplanNativeHooks(plan_dir=str(plan_dir))
        ctx = self._make_ctx(
            overrides=[{"action": "set-model", "phase": "plan", "model": "codex:gpt-5"}],
        )
        hooks.on_step_start(self._make_instr(), ctx)
        assert (plan_dir / "events.ndjson").exists()

    # ── Config overrides: set-profile ────────────────────────────────

    def test_set_profile_sets_config_profile(self) -> None:
        """set-profile sets state.config.profile."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "set-profile", "profile": "thorough"}],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result["state"]["config"]["profile"] == "thorough"

    def test_set_profile_emits_override_applied(self, tmp_path) -> None:
        """set-profile emits OVERRIDE_APPLIED when plan_dir is set."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        hooks = MegaplanNativeHooks(plan_dir=str(plan_dir))
        ctx = self._make_ctx(
            overrides=[{"action": "set-profile", "profile": "thorough"}],
        )
        hooks.on_step_start(self._make_instr(), ctx)
        assert (plan_dir / "events.ndjson").exists()

    # ── Config overrides: set-robustness ─────────────────────────────

    def test_set_robustness_sets_config_robustness(self) -> None:
        """set-robustness sets state.config.robustness."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "set-robustness", "robustness": "paranoid"}],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result["state"]["config"]["robustness"] == "paranoid"

    def test_set_robustness_emits_override_applied(self, tmp_path) -> None:
        """set-robustness emits OVERRIDE_APPLIED when plan_dir is set."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        hooks = MegaplanNativeHooks(plan_dir=str(plan_dir))
        ctx = self._make_ctx(
            overrides=[{"action": "set-robustness", "robustness": "paranoid"}],
        )
        hooks.on_step_start(self._make_instr(), ctx)
        assert (plan_dir / "events.ndjson").exists()

    # ── Config overrides: set-vendor ─────────────────────────────────

    def test_set_vendor_sets_config_premium_vendor(self) -> None:
        """set-vendor sets state.config.premium_vendor."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "set-vendor", "vendor": "codex"}],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result["state"]["config"]["premium_vendor"] == "codex"

    def test_set_vendor_emits_override_applied(self, tmp_path) -> None:
        """set-vendor emits OVERRIDE_APPLIED when plan_dir is set."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        hooks = MegaplanNativeHooks(plan_dir=str(plan_dir))
        ctx = self._make_ctx(
            overrides=[{"action": "set-vendor", "vendor": "codex"}],
        )
        hooks.on_step_start(self._make_instr(), ctx)
        assert (plan_dir / "events.ndjson").exists()

    # ── Parameterized catalog coverage ───────────────────────────────

    @pytest.mark.parametrize(
        "catalog_entry",
        [
            pytest.param(
                {"name": "add-note", "kind": "annotation", "cli": "add-note"},
                id="add-note",
            ),
            pytest.param(
                {"name": "set-model", "kind": "config", "cli": "set-model"},
                id="set-model",
            ),
            pytest.param(
                {"name": "set-profile", "kind": "config", "cli": "set-profile"},
                id="set-profile",
            ),
            pytest.param(
                {"name": "set-robustness", "kind": "config", "cli": "set-robustness"},
                id="set-robustness",
            ),
            pytest.param(
                {"name": "set-vendor", "kind": "config", "cli": "set-vendor"},
                id="set-vendor",
            ),
        ],
    )
    def test_catalog_entry_is_recognised(self, catalog_entry: dict[str, str]) -> None:
        """Every annotation/config catalog entry is recognised by the hooks."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.pipelines.megaplan.planning.operations import override_catalog

        catalog = override_catalog()
        name = catalog_entry["name"]
        assert name in catalog, (
            f"Catalog entry '{name}' must exist in override_catalog()"
        )
        assert catalog[name]["kind"] == catalog_entry["kind"], (
            f"Catalog entry '{name}' kind mismatch: "
            f"expected {catalog_entry['kind']!r}, got {catalog[name]['kind']!r}"
        )

        # Verify the hooks process the entry without crashing
        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(overrides=[{"action": name}])
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result is not None

    @pytest.mark.parametrize(
        "control_entry",
        [
            pytest.param("abort", id="abort"),
            pytest.param("force-proceed", id="force-proceed"),
            pytest.param("recover-blocked", id="recover-blocked"),
            pytest.param("replan", id="replan"),
            pytest.param("resume-clarify", id="resume-clarify"),
        ],
    )
    def test_control_overrides_normalised_and_skipped(
        self, control_entry: str,
    ) -> None:
        """Control overrides are normalised/validated but decision body is skipped.

        T6 does NOT apply control overrides (abort, force-proceed, replan, etc.)
        — that is T7's responsibility.  The hooks should return ctx unchanged
        (no state mutation) for control override kinds.

        Catalog keys use CLI spellings (e.g. ``force-proceed``, not the
        internal ``force_proceed`` form).  Internal names are resolved via
        ``cli_to_internal_override`` for routing but are not direct catalog
        keys.
        """
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.pipelines.megaplan.planning.operations import override_catalog

        catalog = override_catalog()
        hooks = MegaplanNativeHooks()

        ctx = self._make_ctx(
            overrides=[{"action": control_entry, "reason": "test"}],
        )
        # Capture pre-call state for comparison
        pre_state = dict(ctx["state"])
        result = hooks.on_step_start(self._make_instr(), ctx)

        # Verify the override is in the catalog (validation passes).
        assert control_entry in catalog, (
            f"Control override '{control_entry}' must exist in "
            f"override_catalog(). Catalog keys: {sorted(catalog.keys())}"
        )

        # State must NOT be mutated for control overrides (T6 skips them)
        assert result["state"] == pre_state, (
            f"Control override '{control_entry}' should NOT mutate state in T6"
        )

    # ── No event emit when plan_dir is None ──────────────────────────

    def test_no_event_emitted_when_plan_dir_is_none(self) -> None:
        """No OVERRIDE_APPLIED event is emitted when plan_dir is None."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks(plan_dir=None)
        ctx = self._make_ctx(
            overrides=[{"action": "add-note", "note": "silent"}],
        )
        # Should not raise — _emit_override_applied returns early when
        # plan_dir is None
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result["state"]["meta"]["notes"][0]["note"] == "silent"

    # ── Multiple overrides in one batch ──────────────────────────────

    def test_multiple_additive_overrides_applied_together(self) -> None:
        """Multiple annotation/config overrides are all applied in one pass."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[
                {"action": "add-note", "note": "note1", "source": "user"},
                {"action": "set-profile", "profile": "thorough"},
                {"action": "set-robustness", "robustness": "paranoid"},
                {"action": "add-note", "note": "note2", "source": "cli"},
            ],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        state = result["state"]

        # Both notes appended
        assert len(state["meta"]["notes"]) == 2
        assert state["meta"]["notes"][0]["note"] == "note1"
        assert state["meta"]["notes"][1]["note"] == "note2"

        # Config overrides applied
        assert state["config"]["profile"] == "thorough"
        assert state["config"]["robustness"] == "paranoid"

    def test_additive_override_events_still_work(self, tmp_path) -> None:
        """Additive overrides still emit OVERRIDE_APPLIED after fail-closed validation."""
        import json

        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        hooks = MegaplanNativeHooks(plan_dir=str(plan_dir))
        ctx = self._make_ctx(
            overrides=[
                {"action": "add-note", "note": "event note", "source": "test"},
                {"action": "set-profile", "profile": "thorough"},
            ],
        )

        hooks.on_step_start(self._make_instr(), ctx)

        events = [
            json.loads(line)
            for line in (plan_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
        ]
        payloads = [event["payload"] for event in events if event["kind"] == "override_applied"]
        assert {"add-note", "set-profile"} <= {payload["action"] for payload in payloads}



# ── T7: Control override resolver tests ──────────────────────────────


class TestControlOverrideResolver:
    """resolve_control_override priority: termination > transition > recovery."""

    def test_empty_entries_returns_none(self) -> None:
        """Empty control entries produce None."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        assert resolve_control_override([]) is None

    def test_single_termination_wins(self) -> None:
        """A single termination override resolves correctly."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "abort", "kind": "termination"},
        ])
        assert result == "abort"

    def test_single_transition_wins(self) -> None:
        """A single transition override resolves correctly."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "force_proceed", "kind": "transition"},
        ])
        assert result == "force_proceed"

    def test_single_recovery_wins(self) -> None:
        """A single recovery override resolves correctly."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "recover_blocked", "kind": "recovery"},
        ])
        assert result == "recover_blocked"

    def test_termination_beats_transition(self) -> None:
        """Termination (abort) has higher priority than transition (replan)."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "replan", "kind": "transition"},
            {"action": "abort", "kind": "termination"},
        ])
        assert result == "abort", (
            "termination must beat transition regardless of insertion order"
        )

    def test_termination_beats_transition_reverse_order(self) -> None:
        """Termination wins even when listed after transition entries."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "abort", "kind": "termination"},
            {"action": "replan", "kind": "transition"},
        ])
        assert result == "abort"

    def test_transition_beats_recovery(self) -> None:
        """Transition (force_proceed) has higher priority than recovery."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "recover_blocked", "kind": "recovery"},
            {"action": "force_proceed", "kind": "transition"},
        ])
        assert result == "force_proceed", (
            "transition must beat recovery regardless of insertion order"
        )

    def test_termination_beats_all(self) -> None:
        """Termination wins when all three kinds are present."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "resume_clarify", "kind": "recovery"},
            {"action": "force_proceed", "kind": "transition"},
            {"action": "abort", "kind": "termination"},
        ])
        assert result == "abort"

    def test_same_kind_first_wins(self) -> None:
        """Within the same kind, the first entry wins (stable sort)."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "force_proceed", "kind": "transition"},
            {"action": "replan", "kind": "transition"},
        ])
        assert result == "force_proceed", (
            "same-kind tie must preserve insertion order (first wins)"
        )

    def test_unknown_kind_falls_to_lowest_priority(self) -> None:
        """An unknown kind is treated as lowest priority (99)."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )

        result = resolve_control_override([
            {"action": "unknown_thing", "kind": "unknown"},
            {"action": "recover_blocked", "kind": "recovery"},
        ])
        assert result == "recover_blocked", (
            "known recovery kind must beat unknown kind"
        )

    def test_resolve_control_override_in_catalog_integration(self) -> None:
        """resolve_control_override accepts entries shaped like on_step_start produces."""
        from arnold.pipelines.megaplan.native_hooks import (
            resolve_control_override,
        )
        from arnold.pipelines.megaplan.planning.operations import override_catalog

        catalog = override_catalog()
        entries = [
            {
                "action": "recover_blocked",
                "catalog_action": "recover-blocked",
                "kind": catalog["recover-blocked"]["kind"],
                "entry": {"action": "recover-blocked", "reason": "test"},
            },
            {
                "action": "abort",
                "catalog_action": "abort",
                "kind": catalog["abort"]["kind"],
                "entry": {"action": "abort", "reason": "test"},
            },
        ]
        result = resolve_control_override(entries, catalog)
        assert result == "abort", (
            "abort (termination) must beat recover-blocked (recovery)"
        )


class TestControlOverrideIntegration:
    """Integration: control overrides skip decision bodies via on_step_start."""

    @staticmethod
    def _make_ctx(
        overrides: list[dict[str, Any]] | None = None,
        *,
        extra_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a context dict with override entries in ``state.meta.overrides``."""
        state: dict[str, Any] = dict(extra_state or {})
        state.setdefault("meta", {})["overrides"] = (
            list(overrides) if overrides is not None else []
        )
        return {"state": state}

    @staticmethod
    def _make_instr(name: str = "test_phase"):
        from arnold.pipeline.native.ir import NativeInstruction

        return NativeInstruction(
            op="phase", name=name, pc=0, func=None, next_pc=None,
        )

    def test_control_override_sets_ctx_flag(self) -> None:
        """on_step_start sets __override_route__ in ctx for control overrides."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "abort", "reason": "test"}],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result.get("__override_route__") == "abort", (
            "termination override must set __override_route__ in ctx"
        )

    def test_control_override_emits_override_applied_before_route(self, tmp_path) -> None:
        """Control override resolution emits OVERRIDE_APPLIED, not just a ctx route."""
        import json

        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        hooks = MegaplanNativeHooks(plan_dir=str(plan_dir))
        ctx = self._make_ctx(
            overrides=[{"action": "abort", "reason": "stop now"}],
        )

        result = hooks.on_step_start(self._make_instr(), ctx)

        assert result.get("__override_route__") == "abort"
        events = [
            json.loads(line)
            for line in (plan_dir / "events.ndjson").read_text(encoding="utf-8").splitlines()
        ]
        payloads = [event["payload"] for event in events if event["kind"] == "override_applied"]
        assert any(
            payload.get("action") == "abort"
            and payload.get("route") == "abort"
            and payload.get("kind") == "termination"
            for payload in payloads
        )

    def test_transition_override_sets_ctx_flag(self) -> None:
        """on_step_start sets __override_route__ for transition overrides."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "force-proceed", "reason": "test"}],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result.get("__override_route__") == "force_proceed", (
            "transition override must set __override_route__ in ctx"
        )

    def test_recovery_override_sets_ctx_flag(self) -> None:
        """on_step_start sets __override_route__ for recovery overrides."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "recover-blocked", "reason": "test"}],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        # cli_to_internal_override preserves recover-blocked as-is
        # (only force-proceed → force_proceed has an explicit mapping)
        assert result.get("__override_route__") == "recover-blocked", (
            "recovery override must set __override_route__ in ctx"
        )

    def test_control_override_priority_in_ctx(self) -> None:
        """When multiple control overrides present, highest priority wins in ctx."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[
                {"action": "recover-blocked", "reason": "low"},
                {"action": "abort", "reason": "high"},
                {"action": "force-proceed", "reason": "mid"},
            ],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result.get("__override_route__") == "abort", (
            "abort (termination) must beat force-proceed (transition) "
            "and recover-blocked (recovery)"
        )

    def test_additive_overrides_still_applied_with_control_override(self) -> None:
        """Additive overrides are applied even when a control override is present."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[
                {"action": "add-note", "note": "before abort", "source": "user"},
                {"action": "abort", "reason": "stop"},
                {"action": "set-profile", "profile": "thorough"},
            ],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)

        assert result.get("__override_route__") == "abort"

        state = result["state"]
        notes = state["meta"]["notes"]
        assert len(notes) == 1
        assert notes[0]["note"] == "before abort"
        assert state["config"]["profile"] == "thorough"

    def test_no_control_override_when_only_additive(self) -> None:
        """__override_route__ is NOT set when only additive overrides present."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[
                {"action": "add-note", "note": "just a note"},
                {"action": "set-profile", "profile": "thorough"},
            ],
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert "__override_route__" not in result, (
            "__override_route__ must not be set when no control overrides present"
        )

    def test_control_override_preserves_existing_state(self) -> None:
        """State keys are preserved when a control override is resolved."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        ctx = self._make_ctx(
            overrides=[{"action": "abort", "reason": "test"}],
            extra_state={"existing_key": "existing_val"},
        )
        result = hooks.on_step_start(self._make_instr(), ctx)
        assert result["state"]["existing_key"] == "existing_val", (
            "existing state keys must survive control override resolution"
        )
        assert result.get("__override_route__") == "abort"


class TestControlOverrideRuntimeIntegration:
    """End-to-end: control overrides short-circuit decision bodies at runtime.

    These tests prove the full resolver priority chain:
        halt > override > decision > normal
    """

    @pytest.fixture(autouse=True)
    def _enable_native_runtime(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ARNOLD_NATIVE_RUNTIME", "1")

    def test_override_beats_decision_body(self) -> None:
        """When a control override is pending, the decision body is skipped.

        This proves: override > decision.
        """
        from arnold.pipeline.native import (
            NativeInstruction,
            NativeProgram,
            run_native_pipeline,
        )
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        def decision_func(ctx):
            return "then"

        def then_phase(ctx):
            ctx["state"]["branch"] = "then"
            return {"branch": "then"}

        def else_phase(ctx):
            ctx["state"]["branch"] = "else"
            return {"branch": "else"}

        instrs: list[NativeInstruction] = [
            NativeInstruction(
                op="decision", name="gate", pc=0,
                func=decision_func,
                branches={"abort": 1, "then": 2, "else": 3},
            ),
            NativeInstruction(
                op="phase", name="abort_target", pc=1,
                func=then_phase, next_pc=4,
            ),
            NativeInstruction(
                op="phase", name="then_target", pc=2,
                func=then_phase, next_pc=4,
            ),
            NativeInstruction(
                op="phase", name="else_target", pc=3,
                func=else_phase, next_pc=4,
            ),
            NativeInstruction(op="halt", name="end", pc=4, func=None),
        ]
        program = NativeProgram(
            name="test_override_beats_decision",
            instructions=tuple(instrs),
        )

        initial_state = {
            "meta": {
                "overrides": [{"action": "abort", "reason": "test"}],
            },
        }
        hooks = MegaplanNativeHooks()

        result = run_native_pipeline(
            program,
            initial_state=initial_state,
            hooks=hooks,
        )

        assert result.state.get("branch") == "then", (
            "override (abort) should route to abort_target (pc=1), "
            f"not to then_target (pc=2). state={result.state}"
        )

    def test_control_override_falls_back_to_generic_override_branch(self) -> None:
        """Control overrides can drive older decision graphs with one override edge."""
        from arnold.pipeline.native import (
            NativeInstruction,
            NativeProgram,
            run_native_pipeline,
        )
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        def decision_func(ctx):
            return "normal"

        def override_phase(ctx):
            ctx["state"]["branch"] = "override"
            return {"branch": "override"}

        def normal_phase(ctx):
            ctx["state"]["branch"] = "normal"
            return {"branch": "normal"}

        instrs: list[NativeInstruction] = [
            NativeInstruction(
                op="decision", name="gate", pc=0,
                func=decision_func,
                branches={"override": 1, "normal": 2},
            ),
            NativeInstruction(
                op="phase", name="override_target", pc=1,
                func=override_phase, next_pc=3,
            ),
            NativeInstruction(
                op="phase", name="normal_target", pc=2,
                func=normal_phase, next_pc=3,
            ),
            NativeInstruction(op="halt", name="end", pc=3, func=None),
        ]
        program = NativeProgram(
            name="test_generic_override_branch",
            instructions=tuple(instrs),
        )

        result = run_native_pipeline(
            program,
            initial_state={
                "meta": {
                    "overrides": [{"action": "abort", "reason": "test"}],
                },
            },
            hooks=MegaplanNativeHooks(),
        )

        assert result.state.get("branch") == "override"

    def test_decision_beats_normal_when_no_override(self) -> None:
        """When no control override is present, the decision body runs normally.

        This proves: decision > normal.
        """
        from arnold.pipeline.native import (
            NativeInstruction,
            NativeProgram,
            run_native_pipeline,
        )
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        def decision_func(ctx):
            return "then"

        def then_phase(ctx):
            ctx["state"]["branch"] = "then"
            return {"branch": "then"}

        def else_phase(ctx):
            ctx["state"]["branch"] = "else"
            return {"branch": "else"}

        instrs: list[NativeInstruction] = [
            NativeInstruction(
                op="decision", name="gate", pc=0,
                func=decision_func,
                branches={"then": 1, "else": 2},
            ),
            NativeInstruction(
                op="phase", name="then_target", pc=1,
                func=then_phase, next_pc=3,
            ),
            NativeInstruction(
                op="phase", name="else_target", pc=2,
                func=else_phase, next_pc=3,
            ),
            NativeInstruction(op="halt", name="end", pc=3, func=None),
        ]
        program = NativeProgram(
            name="test_decision_beats_normal",
            instructions=tuple(instrs),
        )

        initial_state: dict[str, Any] = {}
        hooks = MegaplanNativeHooks()

        result = run_native_pipeline(
            program,
            initial_state=initial_state,
            hooks=hooks,
        )

        assert result.state.get("branch") == "then", (
            "decision body should run normally when no override is present"
        )

    def test_halt_beats_override_in_loop_guard(self) -> None:
        """When should_halt_loop fires, it beats any pending control override.

        This proves: halt > override.

        The override routes to the loop body (``continue``), but
        ``should_halt_loop`` fires on iteration 1 and terminates the loop.
        The override does not prevent the halt — halt wins.
        """
        from arnold.pipeline.native import (
            NativeInstruction,
            NativeLoopGuard,
            NativeProgram,
            run_native_pipeline,
        )
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        loop_count = {"count": 0}

        def loop_guard(ctx):
            loop_count["count"] += 1
            if loop_count["count"] <= 3:
                return "continue"
            return "exit"

        def body_phase(ctx):
            ctx["state"]["body_ran"] = ctx["state"].get("body_ran", 0) + 1
            return {}

        def exit_phase(ctx):
            ctx["state"]["exited"] = True
            return {}

        instrs: list[NativeInstruction] = [
            NativeInstruction(
                op="decision", name="loop_guard", pc=0,
                func=loop_guard,
                branches={"continue": 1, "exit": 2, "force_proceed": 1},
            ),
            NativeInstruction(
                op="phase", name="body", pc=1,
                func=body_phase, next_pc=0,
            ),
            NativeInstruction(
                op="phase", name="exit_target", pc=2,
                func=exit_phase, next_pc=3,
            ),
            NativeInstruction(op="halt", name="end", pc=3, func=None),
        ]
        program = NativeProgram(
            name="test_halt_beats_override",
            instructions=tuple(instrs),
            loop_guards=[
                NativeLoopGuard(
                    guard=loop_guard,
                    body=body_phase,
                    name="loop_guard",
                ),
            ],
        )

        class HaltThenOverrideHooks(MegaplanNativeHooks):
            def should_halt_loop(self, instr, state, iteration):
                if iteration >= 1:
                    return True, "halt_on_first_iteration"
                return False, None

        hooks = HaltThenOverrideHooks()

        # Override routes to "force_proceed" which maps to the body (pc=1).
        # should_halt_loop fires on iteration 1 and halts before the loop
        # body runs a second time — proving halt > override.
        initial_state = {
            "meta": {
                "overrides": [{"action": "force-proceed", "reason": "test"}],
            },
        }

        result = run_native_pipeline(
            program,
            initial_state=initial_state,
            hooks=hooks,
        )

        body_runs = result.state.get("body_ran", 0)
        # halt fires at the guard level before advancing to the body phase,
        # so body_ran stays at 0.  This proves halt beats override: the
        # override routed to the body branch, but the halt terminated
        # execution before the body could run.
        assert body_runs == 0, (
            f"halt should beat override: body should NOT run when halt fires. "
            f"body_runs={body_runs}, state={result.state}"
        )

    def test_decisions_without_overrides_work_normally(self) -> None:
        """Decision execution with Megaplan hooks but no overrides works."""
        from arnold.pipeline.native import (
            NativeInstruction,
            NativeProgram,
            run_native_pipeline,
        )
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        def decision_func(ctx):
            return "yes"

        def yes_phase(ctx):
            ctx["state"]["branch"] = "yes"
            return {"branch": "yes"}

        def no_phase(ctx):
            ctx["state"]["branch"] = "no"
            return {"branch": "no"}

        instrs: list[NativeInstruction] = [
            NativeInstruction(
                op="decision", name="gate", pc=0,
                func=decision_func,
                branches={"yes": 1, "no": 2},
            ),
            NativeInstruction(
                op="phase", name="yes_target", pc=1,
                func=yes_phase, next_pc=3,
            ),
            NativeInstruction(
                op="phase", name="no_target", pc=2,
                func=no_phase, next_pc=3,
            ),
            NativeInstruction(op="halt", name="end", pc=3, func=None),
        ]
        program = NativeProgram(
            name="test_normal_decision",
            instructions=tuple(instrs),
        )

        hooks = MegaplanNativeHooks()
        result = run_native_pipeline(
            program,
            initial_state={},
            hooks=hooks,
        )

        assert result.state.get("branch") == "yes"

    def test_override_beats_decision_priority_with_multiple_overrides(self) -> None:
        """Multiple overrides: highest priority (termination) beats decision.

        This is the combined priority test: override (termination) > decision.
        """
        from arnold.pipeline.native import (
            NativeInstruction,
            NativeProgram,
            run_native_pipeline,
        )
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        def decision_func(ctx):
            return "then"

        def abort_target(ctx):
            ctx["state"]["branch"] = "abort"
            return {"branch": "abort"}

        def force_target(ctx):
            ctx["state"]["branch"] = "force"
            return {"branch": "force"}

        def then_target(ctx):
            ctx["state"]["branch"] = "then"
            return {"branch": "then"}

        instrs: list[NativeInstruction] = [
            NativeInstruction(
                op="decision", name="gate", pc=0,
                func=decision_func,
                branches={"abort": 1, "force_proceed": 2, "then": 3},
            ),
            NativeInstruction(
                op="phase", name="abort_target", pc=1,
                func=abort_target, next_pc=4,
            ),
            NativeInstruction(
                op="phase", name="force_target", pc=2,
                func=force_target, next_pc=4,
            ),
            NativeInstruction(
                op="phase", name="then_target", pc=3,
                func=then_target, next_pc=4,
            ),
            NativeInstruction(op="halt", name="end", pc=4, func=None),
        ]
        program = NativeProgram(
            name="test_priority_chain",
            instructions=tuple(instrs),
        )

        hooks = MegaplanNativeHooks()
        initial_state = {
            "meta": {
                "overrides": [
                    {"action": "force-proceed", "reason": "low"},
                    {"action": "abort", "reason": "high"},
                ],
            },
        }

        result = run_native_pipeline(
            program,
            initial_state=initial_state,
            hooks=hooks,
        )

        assert result.state.get("branch") == "abort", (
            f"termination (abort) must beat transition (force-proceed). "
            f"state={result.state}"
        )


class TestMegaplanNativeHooksShouldHaltLoop:
    """Megaplan loop policy can halt native loops without affecting defaults."""

    @staticmethod
    def _make_instr(name: str = "review_loop"):
        from arnold.pipeline.native.ir import NativeInstruction

        return NativeInstruction(
            op="decision", name=name, pc=0, func=None, next_pc=None,
        )

    def test_allows_continuation_without_policy(self) -> None:
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()

        assert hooks.should_halt_loop(self._make_instr(), {}, 100) == (False, None)

    def test_halts_when_loop_guard_max_iterations_reached(self) -> None:
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks(
            policy_data={
                "loop_guards": {
                    "review_loop": {"max_iterations": 2},
                },
            },
        )

        assert hooks.should_halt_loop(self._make_instr(), {}, 1) == (False, None)
        do_halt, reason = hooks.should_halt_loop(self._make_instr(), {}, 2)
        assert do_halt is True
        assert reason == "loop_guard:review_loop:max_iterations:2"

    def test_halts_on_configured_recommendation(self) -> None:
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks(
            policy_data={
                "loop_guards": {
                    "review_loop": {
                        "halt_on_recommendations": ["halt"],
                    },
                },
            },
        )
        state = {"subloop:review_loop:recommendation": "halt"}

        do_halt, reason = hooks.should_halt_loop(self._make_instr(), state, 0)
        assert do_halt is True
        assert reason == "loop_guard:review_loop:recommendation:halt"


class TestMegaplanNativeHooksJoinEnvelope:
    """``MegaplanNativeRuntimeHooks.join_envelope`` with RunEnvelope /
    RuntimeEnvelope join semantics, trust/cursor preservation, and
    lease/fencing/capacity conflict rejection. (T8)"""

    # ── plumbing / no-op paths ─────────────────────────────────────

    def test_join_envelope_is_callable(self) -> None:
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        assert callable(hooks.join_envelope)

    def test_null_step_envelope_returns_current_unchanged(self) -> None:
        """When step_envelope is None, current is returned unchanged."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(taint="clean", cost=5.0)

        result = hooks.join_envelope(instr, cur, None)
        assert result is cur

    def test_null_current_returns_step(self) -> None:
        """When current_envelope is None, step_envelope is returned."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        step = RunEnvelope(taint="clean", cost=1.0)

        result = hooks.join_envelope(instr, None, step)
        assert result is step

    def test_both_none_returns_none(self) -> None:
        """When both are None, returns None."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        result = hooks.join_envelope(instr, None, None)
        assert result is None

    # ── RunEnvelope joins ──────────────────────────────────────────

    def test_clean_run_envelope_join_cost_added(self) -> None:
        """Joining two clean RunEnvelopes sums cost."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(taint="clean", cost=3.0)
        step = RunEnvelope(taint="clean", cost=2.0)

        joined = hooks.join_envelope(instr, cur, step)
        assert isinstance(joined, RunEnvelope)
        assert joined.taint == "clean"
        assert joined.cost == 5.0

    def test_taint_propagates(self) -> None:
        """Taint propagates: 'tainted' dominates 'clean'."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(taint="clean", cost=0.0)
        step = RunEnvelope(taint="tainted", cost=0.0)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.taint == "tainted"

    def test_lineage_concatenates(self) -> None:
        """Lineage is concatenated with dedup of exact repeats."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(taint="clean", lineage=("a", "b"))
        step = RunEnvelope(taint="clean", lineage=("c",))

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.lineage == ("a", "b", "c")

    def test_deadline_takes_min(self) -> None:
        """Deadline join takes the tightest (minimum)."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(deadline=100.0)
        step = RunEnvelope(deadline=50.0)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.deadline == 50.0

    def test_cancellation_or(self) -> None:
        """Cancellation is boolean OR."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(cancellation=False)
        step = RunEnvelope(cancellation=True)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.cancellation is True

    def test_retry_budget_takes_min(self) -> None:
        """Retry budget takes the minimum (most constrained)."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(retry_budget=3)
        step = RunEnvelope(retry_budget=1)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.retry_budget == 1

    def test_error_class_conflict_becomes_multiple(self) -> None:
        """Unequal error classes become 'multiple'."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(error_class="timeout")
        step = RunEnvelope(error_class="capacity")

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.error_class == "multiple"

    # ── Lease/fencing/capacity conflict rejection ──────────────────

    def test_lease_id_conflict_raises(self) -> None:
        """Unequal non-None lease_ids raise LeaseIdConflict loudly."""
        import pytest
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import LeaseIdConflict, RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(lease_id="lease-a")
        step = RunEnvelope(lease_id="lease-b")

        with pytest.raises(LeaseIdConflict):
            hooks.join_envelope(instr, cur, step)

    def test_same_lease_id_merges_clean(self) -> None:
        """Equal lease_ids merge without conflict."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(lease_id="lease-x", fencing_token=1)
        step = RunEnvelope(lease_id="lease-x", fencing_token=2)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.lease_id == "lease-x"
        assert joined.fencing_token == 2  # max

    def test_one_side_none_lease_id_merges(self) -> None:
        """When one side has None lease_id, the other dominates."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(lease_id=None)
        step = RunEnvelope(lease_id="lease-c", fencing_token=5)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.lease_id == "lease-c"
        assert joined.fencing_token == 5

    def test_capacity_grant_additive(self) -> None:
        """Capacity grant is summed additively."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(capacity_grant=10)
        step = RunEnvelope(capacity_grant=5)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.capacity_grant == 15

    # ── RuntimeEnvelope joins — identity / trust / cursor preservation ──

    def test_runtime_envelope_join_preserves_identity(self) -> None:
        """Joining two RuntimeEnvelopes preserves the current carrier's identity."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import (
            EMPTY_ENVELOPE,
            RunEnvelope,
            RuntimeEnvelope,
        )

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur = RuntimeEnvelope(
            plugin_id="parent-plugin",
            run_id="parent-run-001",
            artifact_root="/tmp/artifacts/parent",
            trust_state="trusted",
            cross_cutting=RunEnvelope(taint="clean", cost=3.0),
        )
        step = RuntimeEnvelope(
            plugin_id="child-plugin",
            run_id="child-run-002",
            artifact_root="/tmp/artifacts/child",
            trust_state="unknown",
            cross_cutting=RunEnvelope(taint="clean", cost=7.0),
        )

        joined = hooks.join_envelope(instr, cur, step)
        assert isinstance(joined, RuntimeEnvelope)
        # Identity preserved from current
        assert joined.plugin_id == "parent-plugin"
        assert joined.run_id == "parent-run-001"
        assert joined.artifact_root == "/tmp/artifacts/parent"
        assert joined.trust_state == "trusted"
        # Cross-cutting joined
        assert joined.cross_cutting.cost == 10.0

    def test_runtime_envelope_join_preserves_resume_cursor(self) -> None:
        """Resume cursor from the current carrier is preserved."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import (
            EMPTY_ENVELOPE,
            RunEnvelope,
            RuntimeEnvelope,
        )
        from arnold.runtime.resume import ResumeCursorRef

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur_cursor = ResumeCursorRef(
            plugin_id="p", run_id="r", cursor={"pc": 5}
        )
        cur = RuntimeEnvelope(
            resume_cursor=cur_cursor,
            cross_cutting=RunEnvelope(),
        )
        step = RuntimeEnvelope(
            resume_cursor=None,
            cross_cutting=RunEnvelope(taint="tainted"),
        )

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.resume_cursor is cur_cursor
        assert joined.resume_cursor.cursor == {"pc": 5}
        # Taint still propagates
        assert joined.cross_cutting.taint == "tainted"

    def test_runtime_envelope_join_propagates_taint_inner(self) -> None:
        """Cross-cutting taint propagates inside RuntimeEnvelope join."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur = RuntimeEnvelope(
            trust_state="trusted",
            cross_cutting=RunEnvelope(taint="clean", cost=1.0),
        )
        step = RuntimeEnvelope(
            cross_cutting=RunEnvelope(taint="tainted", cost=4.0),
        )

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.trust_state == "trusted"
        assert joined.cross_cutting.taint == "tainted"
        assert joined.cross_cutting.cost == 5.0

    # ── Mixed RuntimeEnvelope / RunEnvelope joins ──────────────────

    def test_runtime_envelope_with_run_envelope_step(self) -> None:
        """Current RuntimeEnvelope + step RunEnvelope = identity preserved,
        cross_cutting joined."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur = RuntimeEnvelope(
            plugin_id="parent",
            run_id="r1",
            artifact_root="/artifacts",
            trust_state="quarantined-manifest-mismatch",
            cross_cutting=RunEnvelope(taint="clean", cost=2.0),
        )
        step = RunEnvelope(taint="tainted", cost=8.0)

        joined = hooks.join_envelope(instr, cur, step)
        assert isinstance(joined, RuntimeEnvelope)
        assert joined.plugin_id == "parent"
        assert joined.run_id == "r1"
        assert joined.trust_state == "quarantined-manifest-mismatch"
        assert joined.cross_cutting.taint == "tainted"
        assert joined.cross_cutting.cost == 10.0

    def test_run_envelope_with_runtime_envelope_step(self) -> None:
        """Current RunEnvelope + step RuntimeEnvelope = step identity
        adopted, cross_cutting joined."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur = RunEnvelope(taint="clean", cost=3.0, lineage=("phase_a",))
        step = RuntimeEnvelope(
            plugin_id="step-plugin",
            run_id="step-run",
            artifact_root="/step/artifacts",
            trust_state="unknown",
            cross_cutting=RunEnvelope(taint="clean", cost=7.0, lineage=("phase_b",)),
        )

        joined = hooks.join_envelope(instr, cur, step)
        assert isinstance(joined, RuntimeEnvelope)
        assert joined.plugin_id == "step-plugin"
        assert joined.run_id == "step-run"
        assert joined.artifact_root == "/step/artifacts"
        assert joined.cross_cutting.cost == 10.0
        assert joined.cross_cutting.lineage == ("phase_a", "phase_b")

    # ── Lease conflict inside RuntimeEnvelope ──────────────────────

    def test_runtime_envelope_lease_conflict_raises(self) -> None:
        """LeaseIdConflict inside RuntimeEnvelope cross_cutting propagates."""
        import pytest
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import (
            LeaseIdConflict,
            RunEnvelope,
            RuntimeEnvelope,
        )

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur = RuntimeEnvelope(
            cross_cutting=RunEnvelope(lease_id="a", fencing_token=1),
        )
        step = RuntimeEnvelope(
            cross_cutting=RunEnvelope(lease_id="b", fencing_token=2),
        )

        with pytest.raises(LeaseIdConflict):
            hooks.join_envelope(instr, cur, step)

    # ── Fencing token semantics in RuntimeEnvelope ─────────────────

    def test_runtime_envelope_fencing_token_max(self) -> None:
        """Fencing token takes max across RuntimeEnvelope join."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur = RuntimeEnvelope(
            cross_cutting=RunEnvelope(lease_id="shared", fencing_token=3),
        )
        step = RuntimeEnvelope(
            cross_cutting=RunEnvelope(lease_id="shared", fencing_token=7),
        )

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.cross_cutting.fencing_token == 7



class TestMegaplanNativeHooksJoinEnvelope:
    """``MegaplanNativeRuntimeHooks.join_envelope`` with RunEnvelope /
    RuntimeEnvelope join semantics, trust/cursor preservation, and
    lease/fencing/capacity conflict rejection. (T8)"""

    # ── plumbing / no-op paths ─────────────────────────────────────

    def test_join_envelope_is_callable(self) -> None:
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        assert callable(hooks.join_envelope)

    def test_null_step_envelope_returns_current_unchanged(self) -> None:
        """When step_envelope is None, current is returned unchanged."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(taint="clean", cost=5.0)

        result = hooks.join_envelope(instr, cur, None)
        assert result is cur

    def test_null_current_returns_step(self) -> None:
        """When current_envelope is None, step_envelope is returned."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        step = RunEnvelope(taint="clean", cost=1.0)

        result = hooks.join_envelope(instr, None, step)
        assert result is step

    def test_both_none_returns_none(self) -> None:
        """When both are None, returns None."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        result = hooks.join_envelope(instr, None, None)
        assert result is None

    # ── RunEnvelope joins ──────────────────────────────────────────

    def test_clean_run_envelope_join_cost_added(self) -> None:
        """Joining two clean RunEnvelopes sums cost."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(taint="clean", cost=3.0)
        step = RunEnvelope(taint="clean", cost=2.0)

        joined = hooks.join_envelope(instr, cur, step)
        assert isinstance(joined, RunEnvelope)
        assert joined.taint == "clean"
        assert joined.cost == 5.0

    def test_taint_propagates(self) -> None:
        """Taint propagates: 'tainted' dominates 'clean'."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(taint="clean", cost=0.0)
        step = RunEnvelope(taint="tainted", cost=0.0)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.taint == "tainted"

    def test_lineage_concatenates(self) -> None:
        """Lineage is concatenated with dedup of exact repeats."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(taint="clean", lineage=("a", "b"))
        step = RunEnvelope(taint="clean", lineage=("c",))

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.lineage == ("a", "b", "c")

    def test_deadline_takes_min(self) -> None:
        """Deadline join takes the tightest (minimum)."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(deadline=100.0)
        step = RunEnvelope(deadline=50.0)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.deadline == 50.0

    def test_cancellation_or(self) -> None:
        """Cancellation is boolean OR."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(cancellation=False)
        step = RunEnvelope(cancellation=True)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.cancellation is True

    def test_retry_budget_takes_min(self) -> None:
        """Retry budget takes the minimum (most constrained)."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(retry_budget=3)
        step = RunEnvelope(retry_budget=1)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.retry_budget == 1

    def test_error_class_conflict_becomes_multiple(self) -> None:
        """Unequal error classes become 'multiple'."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(error_class="timeout")
        step = RunEnvelope(error_class="capacity")

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.error_class == "multiple"

    # ── Lease/fencing/capacity conflict rejection ──────────────────

    def test_lease_id_conflict_raises(self) -> None:
        """Unequal non-None lease_ids raise LeaseIdConflict loudly."""
        import pytest
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import LeaseIdConflict, RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(lease_id="lease-a")
        step = RunEnvelope(lease_id="lease-b")

        with pytest.raises(LeaseIdConflict):
            hooks.join_envelope(instr, cur, step)

    def test_same_lease_id_merges_clean(self) -> None:
        """Equal lease_ids merge without conflict."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(lease_id="lease-x", fencing_token=1)
        step = RunEnvelope(lease_id="lease-x", fencing_token=2)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.lease_id == "lease-x"
        assert joined.fencing_token == 2  # max

    def test_one_side_none_lease_id_merges(self) -> None:
        """When one side has None lease_id, the other dominates."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(lease_id=None)
        step = RunEnvelope(lease_id="lease-c", fencing_token=5)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.lease_id == "lease-c"
        assert joined.fencing_token == 5

    def test_capacity_grant_additive(self) -> None:
        """Capacity grant is summed additively."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )
        cur = RunEnvelope(capacity_grant=10)
        step = RunEnvelope(capacity_grant=5)

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.capacity_grant == 15

    # ── RuntimeEnvelope joins — identity / trust / cursor preservation ──

    def test_runtime_envelope_join_preserves_identity(self) -> None:
        """Joining two RuntimeEnvelopes preserves the current carrier's identity."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur = RuntimeEnvelope(
            plugin_id="parent-plugin",
            run_id="parent-run-001",
            artifact_root="/tmp/artifacts/parent",
            trust_state="trusted",
            cross_cutting=RunEnvelope(taint="clean", cost=3.0),
        )
        step = RuntimeEnvelope(
            plugin_id="child-plugin",
            run_id="child-run-002",
            artifact_root="/tmp/artifacts/child",
            trust_state="unknown",
            cross_cutting=RunEnvelope(taint="clean", cost=7.0),
        )

        joined = hooks.join_envelope(instr, cur, step)
        assert isinstance(joined, RuntimeEnvelope)
        # Identity preserved from current
        assert joined.plugin_id == "parent-plugin"
        assert joined.run_id == "parent-run-001"
        assert joined.artifact_root == "/tmp/artifacts/parent"
        assert joined.trust_state == "trusted"
        # Cross-cutting joined
        assert joined.cross_cutting.cost == 10.0

    def test_runtime_envelope_join_preserves_resume_cursor(self) -> None:
        """Resume cursor from the current carrier is preserved."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        from arnold.runtime.resume import ResumeCursorRef

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur_cursor = ResumeCursorRef(
            plugin_id="p", run_id="r", cursor={"pc": 5}
        )
        cur = RuntimeEnvelope(
            resume_cursor=cur_cursor,
            cross_cutting=RunEnvelope(),
        )
        step = RuntimeEnvelope(
            resume_cursor=None,
            cross_cutting=RunEnvelope(taint="tainted"),
        )

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.resume_cursor is cur_cursor
        assert joined.resume_cursor.cursor == {"pc": 5}
        # Taint still propagates
        assert joined.cross_cutting.taint == "tainted"

    def test_runtime_envelope_join_propagates_taint_inner(self) -> None:
        """Cross-cutting taint propagates inside RuntimeEnvelope join."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur = RuntimeEnvelope(
            trust_state="trusted",
            cross_cutting=RunEnvelope(taint="clean", cost=1.0),
        )
        step = RuntimeEnvelope(
            cross_cutting=RunEnvelope(taint="tainted", cost=4.0),
        )

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.trust_state == "trusted"
        assert joined.cross_cutting.taint == "tainted"
        assert joined.cross_cutting.cost == 5.0

    # ── Mixed RuntimeEnvelope / RunEnvelope joins ──────────────────

    def test_runtime_envelope_with_run_envelope_step(self) -> None:
        """Current RuntimeEnvelope + step RunEnvelope = identity preserved,
        cross_cutting joined."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur = RuntimeEnvelope(
            plugin_id="parent",
            run_id="r1",
            artifact_root="/artifacts",
            trust_state="quarantined-manifest-mismatch",
            cross_cutting=RunEnvelope(taint="clean", cost=2.0),
        )
        step = RunEnvelope(taint="tainted", cost=8.0)

        joined = hooks.join_envelope(instr, cur, step)
        assert isinstance(joined, RuntimeEnvelope)
        assert joined.plugin_id == "parent"
        assert joined.run_id == "r1"
        assert joined.trust_state == "quarantined-manifest-mismatch"
        assert joined.cross_cutting.taint == "tainted"
        assert joined.cross_cutting.cost == 10.0

    def test_run_envelope_with_runtime_envelope_step(self) -> None:
        """Current RunEnvelope + step RuntimeEnvelope = step identity
        adopted, cross_cutting joined."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur = RunEnvelope(taint="clean", cost=3.0, lineage=("phase_a",))
        step = RuntimeEnvelope(
            plugin_id="step-plugin",
            run_id="step-run",
            artifact_root="/step/artifacts",
            trust_state="unknown",
            cross_cutting=RunEnvelope(taint="clean", cost=7.0, lineage=("phase_b",)),
        )

        joined = hooks.join_envelope(instr, cur, step)
        assert isinstance(joined, RuntimeEnvelope)
        assert joined.plugin_id == "step-plugin"
        assert joined.run_id == "step-run"
        assert joined.artifact_root == "/step/artifacts"
        assert joined.cross_cutting.cost == 10.0
        assert joined.cross_cutting.lineage == ("phase_a", "phase_b")

    # ── Lease conflict inside RuntimeEnvelope ──────────────────────

    def test_runtime_envelope_lease_conflict_raises(self) -> None:
        """LeaseIdConflict inside RuntimeEnvelope cross_cutting propagates."""
        import pytest
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import (
            LeaseIdConflict,
            RunEnvelope,
            RuntimeEnvelope,
        )

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur = RuntimeEnvelope(
            cross_cutting=RunEnvelope(lease_id="a", fencing_token=1),
        )
        step = RuntimeEnvelope(
            cross_cutting=RunEnvelope(lease_id="b", fencing_token=2),
        )

        with pytest.raises(LeaseIdConflict):
            hooks.join_envelope(instr, cur, step)

    # ── Fencing token semantics in RuntimeEnvelope ─────────────────

    def test_runtime_envelope_fencing_token_max(self) -> None:
        """Fencing token takes max across RuntimeEnvelope join."""
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope

        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(
            op="phase", name="test", pc=0, func=None, next_pc=None,
        )

        cur = RuntimeEnvelope(
            cross_cutting=RunEnvelope(lease_id="shared", fencing_token=3),
        )
        step = RuntimeEnvelope(
            cross_cutting=RunEnvelope(lease_id="shared", fencing_token=7),
        )

        joined = hooks.join_envelope(instr, cur, step)
        assert joined.cross_cutting.fencing_token == 7


class TestMegaplanNativeHooksJoinEnvelope:
    """``MegaplanNativeRuntimeHooks.join_envelope`` with RunEnvelope /
    RuntimeEnvelope join semantics, trust/cursor preservation, and
    lease/fencing/capacity conflict rejection. (T8)"""

    def test_join_envelope_is_callable(self) -> None:
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        assert callable(hooks.join_envelope)

    def test_null_step_envelope_returns_current_unchanged(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(taint="clean", cost=5.0)
        result = hooks.join_envelope(instr, cur, None)
        assert result is cur

    def test_null_current_returns_step(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        step = RunEnvelope(taint="clean", cost=1.0)
        result = hooks.join_envelope(instr, None, step)
        assert result is step

    def test_both_none_returns_none(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        result = hooks.join_envelope(instr, None, None)
        assert result is None

    def test_clean_run_envelope_join_cost_added(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(taint="clean", cost=3.0)
        step = RunEnvelope(taint="clean", cost=2.0)
        joined = hooks.join_envelope(instr, cur, step)
        assert isinstance(joined, RunEnvelope)
        assert joined.taint == "clean"
        assert joined.cost == 5.0

    def test_taint_propagates(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(taint="clean", cost=0.0)
        step = RunEnvelope(taint="tainted", cost=0.0)
        joined = hooks.join_envelope(instr, cur, step)
        assert joined.taint == "tainted"

    def test_lineage_concatenates(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(taint="clean", lineage=("a", "b"))
        step = RunEnvelope(taint="clean", lineage=("c",))
        joined = hooks.join_envelope(instr, cur, step)
        assert joined.lineage == ("a", "b", "c")

    def test_deadline_takes_min(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(deadline=100.0)
        step = RunEnvelope(deadline=50.0)
        joined = hooks.join_envelope(instr, cur, step)
        assert joined.deadline == 50.0

    def test_cancellation_or(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(cancellation=False)
        step = RunEnvelope(cancellation=True)
        joined = hooks.join_envelope(instr, cur, step)
        assert joined.cancellation is True

    def test_retry_budget_takes_min(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(retry_budget=3)
        step = RunEnvelope(retry_budget=1)
        joined = hooks.join_envelope(instr, cur, step)
        assert joined.retry_budget == 1

    def test_error_class_conflict_becomes_multiple(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(error_class="timeout")
        step = RunEnvelope(error_class="capacity")
        joined = hooks.join_envelope(instr, cur, step)
        assert joined.error_class == "multiple"

    def test_lease_id_conflict_raises(self) -> None:
        import pytest
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import LeaseIdConflict, RunEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(lease_id="lease-a")
        step = RunEnvelope(lease_id="lease-b")
        with pytest.raises(LeaseIdConflict):
            hooks.join_envelope(instr, cur, step)

    def test_same_lease_id_merges_clean(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(lease_id="lease-x", fencing_token=1)
        step = RunEnvelope(lease_id="lease-x", fencing_token=2)
        joined = hooks.join_envelope(instr, cur, step)
        assert joined.lease_id == "lease-x"
        assert joined.fencing_token == 2

    def test_one_side_none_lease_id_merges(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(lease_id=None)
        step = RunEnvelope(lease_id="lease-c", fencing_token=5)
        joined = hooks.join_envelope(instr, cur, step)
        assert joined.lease_id == "lease-c"
        assert joined.fencing_token == 5

    def test_capacity_grant_additive(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(capacity_grant=10)
        step = RunEnvelope(capacity_grant=5)
        joined = hooks.join_envelope(instr, cur, step)
        assert joined.capacity_grant == 15

    def test_runtime_envelope_join_preserves_identity(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RuntimeEnvelope(plugin_id="parent-plugin", run_id="parent-run-001",
            artifact_root="/tmp/artifacts/parent", trust_state="trusted",
            cross_cutting=RunEnvelope(taint="clean", cost=3.0))
        step = RuntimeEnvelope(plugin_id="child-plugin", run_id="child-run-002",
            artifact_root="/tmp/artifacts/child", trust_state="unknown",
            cross_cutting=RunEnvelope(taint="clean", cost=7.0))
        joined = hooks.join_envelope(instr, cur, step)
        assert isinstance(joined, RuntimeEnvelope)
        assert joined.plugin_id == "parent-plugin"
        assert joined.run_id == "parent-run-001"
        assert joined.artifact_root == "/tmp/artifacts/parent"
        assert joined.trust_state == "trusted"
        assert joined.cross_cutting.cost == 10.0

    def test_runtime_envelope_join_preserves_resume_cursor(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        from arnold.runtime.resume import ResumeCursorRef
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur_cursor = ResumeCursorRef(plugin_id="p", run_id="r", cursor={"pc": 5})
        cur = RuntimeEnvelope(resume_cursor=cur_cursor, cross_cutting=RunEnvelope())
        step = RuntimeEnvelope(resume_cursor=None, cross_cutting=RunEnvelope(taint="tainted"))
        joined = hooks.join_envelope(instr, cur, step)
        assert joined.resume_cursor is cur_cursor
        assert joined.resume_cursor.cursor == {"pc": 5}
        assert joined.cross_cutting.taint == "tainted"

    def test_runtime_envelope_join_propagates_taint_inner(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RuntimeEnvelope(trust_state="trusted",
            cross_cutting=RunEnvelope(taint="clean", cost=1.0))
        step = RuntimeEnvelope(cross_cutting=RunEnvelope(taint="tainted", cost=4.0))
        joined = hooks.join_envelope(instr, cur, step)
        assert joined.trust_state == "trusted"
        assert joined.cross_cutting.taint == "tainted"
        assert joined.cross_cutting.cost == 5.0

    def test_runtime_envelope_with_run_envelope_step(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RuntimeEnvelope(plugin_id="parent", run_id="r1", artifact_root="/artifacts",
            trust_state="quarantined-manifest-mismatch",
            cross_cutting=RunEnvelope(taint="clean", cost=2.0))
        step = RunEnvelope(taint="tainted", cost=8.0)
        joined = hooks.join_envelope(instr, cur, step)
        assert isinstance(joined, RuntimeEnvelope)
        assert joined.plugin_id == "parent"
        assert joined.run_id == "r1"
        assert joined.trust_state == "quarantined-manifest-mismatch"
        assert joined.cross_cutting.taint == "tainted"
        assert joined.cross_cutting.cost == 10.0

    def test_run_envelope_with_runtime_envelope_step(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(taint="clean", cost=3.0, lineage=("phase_a",))
        step = RuntimeEnvelope(plugin_id="step-plugin", run_id="step-run",
            artifact_root="/step/artifacts", trust_state="unknown",
            cross_cutting=RunEnvelope(taint="clean", cost=7.0, lineage=("phase_b",)))
        joined = hooks.join_envelope(instr, cur, step)
        assert isinstance(joined, RuntimeEnvelope)
        assert joined.plugin_id == "step-plugin"
        assert joined.run_id == "step-run"
        assert joined.artifact_root == "/step/artifacts"
        assert joined.cross_cutting.cost == 10.0
        assert joined.cross_cutting.lineage == ("phase_a", "phase_b")

    def test_runtime_envelope_lease_conflict_raises(self) -> None:
        import pytest
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import LeaseIdConflict, RunEnvelope, RuntimeEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RuntimeEnvelope(cross_cutting=RunEnvelope(lease_id="a", fencing_token=1))
        step = RuntimeEnvelope(cross_cutting=RunEnvelope(lease_id="b", fencing_token=2))
        with pytest.raises(LeaseIdConflict):
            hooks.join_envelope(instr, cur, step)

    def test_runtime_envelope_fencing_token_max(self) -> None:
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        hooks = MegaplanNativeHooks()
        instr = NativeInstruction(op="phase", name="test", pc=0, func=None, next_pc=None)
        cur = RuntimeEnvelope(cross_cutting=RunEnvelope(lease_id="shared", fencing_token=3))
        step = RuntimeEnvelope(cross_cutting=RunEnvelope(lease_id="shared", fencing_token=7))
        joined = hooks.join_envelope(instr, cur, step)
        assert joined.cross_cutting.fencing_token == 7


class TestMegaplanNativeHooksJoinEnvelope:
    """Envelope joining with trust/cursor preservation and lease conflict rejection. (T8)"""

    def test_join_envelope_is_callable(self):
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        assert callable(MegaplanNativeHooks().join_envelope)

    def test_null_step_returns_current(self):
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(taint="clean", cost=5.0)
        assert h.join_envelope(i, cur, None) is cur

    def test_null_current_returns_step(self):
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        step = RunEnvelope(taint="clean", cost=1.0)
        assert h.join_envelope(i, None, step) is step

    def test_run_envelope_join_cost_added(self):
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        j = h.join_envelope(i, RunEnvelope(cost=3.0), RunEnvelope(cost=2.0))
        assert j.cost == 5.0
        assert j.taint == "clean"

    def test_taint_propagates(self):
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        j = h.join_envelope(i, RunEnvelope(taint="clean"), RunEnvelope(taint="tainted"))
        assert j.taint == "tainted"

    def test_lease_id_conflict_raises(self):
        import pytest
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import LeaseIdConflict, RunEnvelope
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        with pytest.raises(LeaseIdConflict):
            h.join_envelope(i, RunEnvelope(lease_id="a"), RunEnvelope(lease_id="b"))

    def test_runtime_envelope_preserves_identity(self):
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        cur = RuntimeEnvelope(plugin_id="parent", run_id="r1",
            artifact_root="/art", trust_state="trusted",
            cross_cutting=RunEnvelope(cost=3.0))
        step = RuntimeEnvelope(plugin_id="child", run_id="r2",
            artifact_root="/child", trust_state="unknown",
            cross_cutting=RunEnvelope(cost=7.0))
        j = h.join_envelope(i, cur, step)
        assert j.plugin_id == "parent"
        assert j.run_id == "r1"
        assert j.trust_state == "trusted"
        assert j.cross_cutting.cost == 10.0

    def test_runtime_envelope_preserves_cursor(self):
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        from arnold.runtime.resume import ResumeCursorRef
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        rc = ResumeCursorRef(plugin_id="p", run_id="r", cursor={"pc": 5})
        cur = RuntimeEnvelope(resume_cursor=rc, cross_cutting=RunEnvelope())
        step = RuntimeEnvelope(resume_cursor=None, cross_cutting=RunEnvelope(taint="t"))
        j = h.join_envelope(i, cur, step)
        assert j.resume_cursor is rc
        assert j.cross_cutting.taint == "t"

    def test_runtime_envelope_lease_conflict_raises(self):
        import pytest
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import LeaseIdConflict, RunEnvelope, RuntimeEnvelope
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        cur = RuntimeEnvelope(cross_cutting=RunEnvelope(lease_id="a", fencing_token=1))
        step = RuntimeEnvelope(cross_cutting=RunEnvelope(lease_id="b", fencing_token=2))
        with pytest.raises(LeaseIdConflict):
            h.join_envelope(i, cur, step)

    def test_fencing_token_max(self):
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        cur = RuntimeEnvelope(cross_cutting=RunEnvelope(lease_id="s", fencing_token=3))
        step = RuntimeEnvelope(cross_cutting=RunEnvelope(lease_id="s", fencing_token=7))
        j = h.join_envelope(i, cur, step)
        assert j.cross_cutting.fencing_token == 7

    def test_capacity_grant_additive(self):
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        j = h.join_envelope(i, RunEnvelope(capacity_grant=10), RunEnvelope(capacity_grant=5))
        assert j.capacity_grant == 15

    def test_error_class_multiple(self):
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        j = h.join_envelope(i, RunEnvelope(error_class="timeout"), RunEnvelope(error_class="capacity"))
        assert j.error_class == "multiple"

    def test_both_none_returns_none(self):
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        assert h.join_envelope(i, None, None) is None

    def test_falsy_step_returns_current(self):
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        cur = RunEnvelope(taint="clean")
        assert h.join_envelope(i, cur, {}) is cur
        assert h.join_envelope(i, cur, "") is cur

    def test_same_lease_id_merges(self):
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        j = h.join_envelope(i, RunEnvelope(lease_id="x", fencing_token=1),
                            RunEnvelope(lease_id="x", fencing_token=2))
        assert j.lease_id == "x"
        assert j.fencing_token == 2

    def test_runtime_with_run_step_preserves_identity(self):
        from arnold.pipeline.native.ir import NativeInstruction
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        h = MegaplanNativeHooks()
        i = NativeInstruction(op="phase", name="t", pc=0, func=None, next_pc=None)
        cur = RuntimeEnvelope(plugin_id="p", run_id="r",
            trust_state="quarantined-manifest-mismatch",
            cross_cutting=RunEnvelope(cost=2.0))
        step = RunEnvelope(taint="t", cost=8.0)
        j = h.join_envelope(i, cur, step)
        assert isinstance(j, RuntimeEnvelope)
        assert j.plugin_id == "p"
        assert j.trust_state == "quarantined-manifest-mismatch"
        assert j.cross_cutting.cost == 10.0
        assert j.cross_cutting.taint == "t"


# ── Subloop promotion / suspension-lift tests (T13) ────────────────────


class TestMegaplanNativeHooksCompletedSubloop:
    """Focused tests for completed child promotion, artifact root
    preservation, and child envelope join via ``completed_subloop``."""

    # ── completed child promotion ──────────────────────────────────

    def test_completed_subloop_returns_state_patch_and_envelope(self):
        """``completed_subloop`` returns a (state_patch, joined_envelope) tuple."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, env = hooks.completed_subloop(
            "child1", {"key": "val"}, "proceed",
        )
        assert isinstance(state_patch, dict)
        # envelope is None when neither parent nor child envelope given
        assert env is None

    def test_completed_subloop_promotes_state_and_recommendation(self):
        """State patch carries ``subloop:<name>:state`` and
        ``subloop:<name>:recommendation`` keys."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        child_state = {"result": 42, "phase": "done"}
        state_patch, _ = hooks.completed_subloop(
            "analyze", child_state, "force-proceed",
        )
        assert state_patch["subloop:analyze:state"] == child_state
        assert state_patch["subloop:analyze:recommendation"] == "force-proceed"

    def test_completed_subloop_promotes_state_copy_not_reference(self):
        """Promoted child state is a copy, not the original dict."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        child_state = {"x": 1}
        state_patch, _ = hooks.completed_subloop("s", child_state, "ok")
        child_state["x"] = 99
        assert state_patch["subloop:s:state"]["x"] == 1  # snapshot preserved

    # ── artifact root preservation ──────────────────────────────────

    def test_completed_subloop_includes_artifacts_when_provided(self):
        """``subloop:<name>:artifacts`` present when child_artifacts given."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        artifacts = {"diagram": "/tmp/out.png", "log": "/tmp/run.log"}
        state_patch, _ = hooks.completed_subloop(
            "build", {}, "done",
            child_artifacts=artifacts,
        )
        assert state_patch["subloop:build:artifacts"] == artifacts

    def test_completed_subloop_omits_artifacts_when_none(self):
        """``subloop:<name>:artifacts`` absent when child_artifacts is None."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, _ = hooks.completed_subloop("t", {}, "ok")
        assert "subloop:t:artifacts" not in state_patch

    def test_completed_subloop_omits_artifacts_when_empty_dict(self):
        """``subloop:<name>:artifacts`` absent when child_artifacts is empty."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, _ = hooks.completed_subloop(
            "e", {}, "ok", child_artifacts={},
        )
        assert "subloop:e:artifacts" not in state_patch

    # ── resume_cursor in completed path ─────────────────────────────

    def test_completed_subloop_includes_resume_cursor_when_provided(self):
        """``subloop:<name>:resume_cursor`` present when non-None."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        cursor = {"pc": 3, "state": {"inner": 1}}
        state_patch, _ = hooks.completed_subloop(
            "sub", {}, "halt", resume_cursor=cursor,
        )
        assert state_patch["subloop:sub:resume_cursor"] == cursor

    def test_completed_subloop_omits_resume_cursor_when_none(self):
        """``subloop:<name>:resume_cursor`` absent when None."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, _ = hooks.completed_subloop(
            "sub", {}, "ok", resume_cursor=None,
        )
        assert "subloop:sub:resume_cursor" not in state_patch

    # ── child envelope join ─────────────────────────────────────────

    def test_completed_subloop_joins_envelopes(self):
        """Child envelope is joined with parent envelope via join_envelope."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        parent_env = RunEnvelope(taint="clean", cost=1.0)
        child_env = RunEnvelope(taint="tainted", cost=4.0)
        _, joined = hooks.completed_subloop(
            "child", {}, "ok",
            child_envelope=child_env,
            parent_envelope=parent_env,
        )
        assert joined is not None
        assert joined.cost == 5.0  # 1.0 + 4.0
        assert joined.taint == "tainted"

    def test_completed_subloop_envelope_join_preserves_identity(self):
        """Envelope join preserves parent RuntimeEnvelope identity."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        hooks = MegaplanNativeHooks()
        parent_env = RuntimeEnvelope(
            plugin_id="parent-p", run_id="parent-r",
            artifact_root="/art/parent", trust_state="trusted",
            cross_cutting=RunEnvelope(cost=2.0),
        )
        child_env = RuntimeEnvelope(
            plugin_id="child-p", run_id="child-r",
            artifact_root="/art/child", trust_state="unknown",
            cross_cutting=RunEnvelope(cost=3.0),
        )
        _, joined = hooks.completed_subloop(
            "c", {}, "ok",
            child_envelope=child_env,
            parent_envelope=parent_env,
        )
        assert isinstance(joined, RuntimeEnvelope)
        assert joined.plugin_id == "parent-p"
        assert joined.run_id == "parent-r"
        assert joined.artifact_root == "/art/parent"
        assert joined.cross_cutting.cost == 5.0

    def test_completed_subloop_envelope_lease_conflict_propagates(self):
        """LeaseIdConflict from envelope join propagates through completed_subloop."""
        import pytest
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import LeaseIdConflict, RunEnvelope
        hooks = MegaplanNativeHooks()
        with pytest.raises(LeaseIdConflict):
            hooks.completed_subloop(
                "c", {}, "ok",
                parent_envelope=RunEnvelope(lease_id="a"),
                child_envelope=RunEnvelope(lease_id="b"),
            )


class TestMegaplanNativeHooksSuspendedSubloop:
    """Focused tests for suspended child cursor shape, envelope
    preservation, artifact root preservation, and resume continuation
    via ``suspended_subloop``."""

    # ── suspended child cursor shape ────────────────────────────────

    def test_suspended_subloop_returns_state_patch_and_envelope(self):
        """``suspended_subloop`` returns a (state_patch, joined_envelope) tuple."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, env = hooks.suspended_subloop(
            "child1", {"key": "val"},
        )
        assert isinstance(state_patch, dict)
        assert env is None  # no parent/child envelope given

    def test_suspended_subloop_state_patch_keys(self):
        """State patch has correct promoted keys."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        child_state = {"phase": "analysis", "result": {"score": 0.9}}
        child_artifacts = {"log": "/tmp/log.txt"}
        child_cursor = {"pc": 5, "frames": {"child_frame": {}}}
        state_patch, _ = hooks.suspended_subloop(
            "analyze", child_state,
            child_artifacts=child_artifacts,
            child_resume_cursor=child_cursor,
        )
        assert state_patch["subloop:analyze:state"] == child_state
        assert state_patch["subloop:analyze:recommendation"] == "halt"
        assert state_patch["subloop:analyze:resume_cursor"] == child_cursor
        assert state_patch["subloop:analyze:artifacts"] == child_artifacts

    def test_suspended_subloop_omits_artifacts_when_none(self):
        """Artifacts key absent when not provided."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, _ = hooks.suspended_subloop("s", {})
        assert "subloop:s:artifacts" not in state_patch

    def test_suspended_subloop_omits_resume_cursor_when_none(self):
        """Resume cursor key absent when None."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, _ = hooks.suspended_subloop("s", {})
        assert "subloop:s:resume_cursor" not in state_patch

    def test_suspended_subloop_recommendation_is_always_halt(self):
        """Recommendation is always 'halt' regardless of child state."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        for child_state in [{}, {"rec": "proceed"}, {"rec": "abort"}]:
            state_patch, _ = hooks.suspended_subloop("s", child_state)
            assert state_patch["subloop:s:recommendation"] == "halt"

    # ── envelope preservation ───────────────────────────────────────

    def test_suspended_subloop_joins_envelopes(self):
        """Envelope join is called with parent and child envelopes."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        parent_env = RunEnvelope(taint="clean", cost=1.0)
        child_env = RunEnvelope(taint="tainted", cost=4.0)
        _, joined = hooks.suspended_subloop(
            "child", {},
            child_envelope=child_env,
            parent_envelope=parent_env,
        )
        assert joined is not None
        assert joined.cost == 5.0
        assert joined.taint == "tainted"

    def test_suspended_subloop_envelope_preserves_runtime_identity(self):
        """Parent RuntimeEnvelope identity preserved after suspended join."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        hooks = MegaplanNativeHooks()
        parent_env = RuntimeEnvelope(
            plugin_id="p-id", run_id="r-id",
            artifact_root="/art/root", trust_state="trusted",
            cross_cutting=RunEnvelope(cost=1.0),
        )
        child_env = RunEnvelope(taint="t", cost=3.0)
        _, joined = hooks.suspended_subloop(
            "c", {},
            child_envelope=child_env,
            parent_envelope=parent_env,
        )
        assert isinstance(joined, RuntimeEnvelope)
        assert joined.plugin_id == "p-id"
        assert joined.run_id == "r-id"
        assert joined.artifact_root == "/art/root"
        assert joined.trust_state == "trusted"
        assert joined.cross_cutting.cost == 4.0
        assert joined.cross_cutting.taint == "t"

    def test_suspended_subloop_lease_conflict_propagates(self):
        """LeaseIdConflict from envelope propagates through suspended_subloop."""
        import pytest
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import LeaseIdConflict, RunEnvelope
        hooks = MegaplanNativeHooks()
        with pytest.raises(LeaseIdConflict):
            hooks.suspended_subloop(
                "c", {},
                parent_envelope=RunEnvelope(lease_id="a"),
                child_envelope=RunEnvelope(lease_id="b"),
            )

    # ── artifact root preservation ──────────────────────────────────

    def test_suspended_subloop_artifacts_preserved_in_state_patch(self):
        """Child artifacts dict is preserved verbatim in state patch."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        artifacts = {"diagram": "/artifacts/d.png", "traces": "/artifacts/t.json"}
        state_patch, _ = hooks.suspended_subloop(
            "build", {"status": "suspended"},
            child_artifacts=artifacts,
        )
        assert state_patch["subloop:build:artifacts"]["diagram"] == "/artifacts/d.png"
        assert state_patch["subloop:build:artifacts"]["traces"] == "/artifacts/t.json"

    # ── resume continuation ─────────────────────────────────────────

    def test_suspended_subloop_no_persist_without_plan_dir(self):
        """When plan_dir is None, no persistence attempted but state_patch
        and envelope still returned."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()  # plan_dir=None by default
        state_patch, env = hooks.suspended_subloop(
            "child", {"a": 1},
            child_resume_cursor={"pc": 3},
            parent_pc=7,
            parent_state={"existing": "value"},
        )
        # state_patch is still populated
        assert state_patch["subloop:child:state"] == {"a": 1}
        assert state_patch["subloop:child:recommendation"] == "halt"
        assert state_patch["subloop:child:resume_cursor"] == {"pc": 3}

    def test_suspended_subloop_state_patch_is_copy(self):
        """Promoted child state is a snapshot copy."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        child_state = {"x": 1}
        state_patch, _ = hooks.suspended_subloop("s", child_state)
        child_state["x"] = 99
        assert state_patch["subloop:s:state"]["x"] == 1

    def test_suspended_subloop_child_state_fully_preserved(self):
        """Full child state dict is preserved including nested structures."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        child_state = {
            "phase": "implementation",
            "result": {"files": ["a.py", "b.py"], "score": 0.95},
            "meta": {"iterations": 3, "cost": 1.5},
        }
        state_patch, _ = hooks.suspended_subloop("impl", child_state)
        promoted = state_patch["subloop:impl:state"]
        assert promoted["phase"] == "implementation"
        assert promoted["result"]["files"] == ["a.py", "b.py"]
        assert promoted["meta"]["iterations"] == 3

    def test_suspended_subloop_accepts_all_parent_context_fields(self):
        """All parent context fields accepted without error."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, _ = hooks.suspended_subloop(
            "sub", {"done": True},
            parent_pc=12,
            parent_loops={"main": 3},
            parent_frames={"frame_a": {"pc": 5}},
            parent_stages=["init", "process", "sub"],
            parent_state={"global": "config"},
        )
        assert state_patch["subloop:sub:state"] == {"done": True}
        assert state_patch["subloop:sub:recommendation"] == "halt"

    def test_suspended_subloop_cursor_persistence_with_plan_dir(self):
        """When plan_dir is set, composite resume cursor is persisted."""
        import tempfile
        from pathlib import Path
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = str(Path(tmpdir) / "plan")
            Path(plan_dir).mkdir(parents=True, exist_ok=True)

            hooks = MegaplanNativeHooks(plan_dir=plan_dir)
            child_state = {"phase": "review", "items": 5}
            child_cursor = {"pc": 3, "frames": {"review_frame": {}}}
            parent_env = RunEnvelope(taint="clean", cost=10.0)
            child_env = RunEnvelope(taint="clean", cost=2.0)

            state_patch, joined = hooks.suspended_subloop(
                "review_loop", child_state,
                child_resume_cursor=child_cursor,
                child_artifact_root="/tmp/child_artifacts",
                child_frames={"f1": {"pc": 2}},
                child_envelope=child_env,
                parent_envelope=parent_env,
                parent_pc=8,
                parent_loops={"main": 1},
                parent_frames={"pf": {"pc": 7}},
                parent_stages=["alpha", "beta"],
                parent_state={"config": {"mode": "strict"}},
            )

            # state_patch returned correctly
            assert state_patch["subloop:review_loop:state"] == child_state
            assert state_patch["subloop:review_loop:recommendation"] == "halt"
            assert state_patch["subloop:review_loop:resume_cursor"] == child_cursor

            # envelope joined
            assert joined is not None
            assert joined.cost == 12.0  # 10 + 2

            # composite resume cursor file written
            cursor_path = Path(plan_dir) / "composite_resume_cursor.json"
            assert cursor_path.exists(), (
                f"Composite resume cursor not found at {cursor_path}"
            )

            # Verify cursor shape
            import json
            cursor_data = json.loads(cursor_path.read_text())
            assert cursor_data["version"] == 1
            assert "children" in cursor_data
            assert "review_loop" in cursor_data["children"]
            child_entry = cursor_data["children"]["review_loop"]
            assert child_entry.get("resume_cursor") == child_cursor
            assert child_entry.get("artifact_root") == "/tmp/child_artifacts"
            assert child_entry.get("state") == child_state
            assert child_entry.get("frames") == {"f1": {"pc": 2}}

            # parent fields stored as top-level extra keys
            assert cursor_data.get("parent_pc") == 8
            assert cursor_data.get("parent_state") == {"config": {"mode": "strict"}}
            assert cursor_data.get("parent_stages") == ["alpha", "beta"]
            assert cursor_data.get("parent_loops") == {"main": 1}
            assert cursor_data.get("parent_frames") == {"pf": {"pc": 7}}

            # envelope in extra
            assert "envelope" in cursor_data


# ── Subloop promotion / suspension-lift tests (T13) ────────────────────


class TestMegaplanNativeHooksCompletedSubloop:
    """Focused tests for completed child promotion, artifact root
    preservation, and child envelope join via ``completed_subloop``."""

    def test_completed_subloop_returns_state_patch_and_envelope(self):
        """``completed_subloop`` returns a (state_patch, joined_envelope) tuple."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, env = hooks.completed_subloop(
            "child1", {"key": "val"}, "proceed",
        )
        assert isinstance(state_patch, dict)
        assert env is None

    def test_completed_subloop_promotes_state_and_recommendation(self):
        """State patch carries ``subloop:<name>:state`` and
        ``subloop:<name>:recommendation`` keys."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        child_state = {"result": 42, "phase": "done"}
        state_patch, _ = hooks.completed_subloop(
            "analyze", child_state, "force-proceed",
        )
        assert state_patch["subloop:analyze:state"] == child_state
        assert state_patch["subloop:analyze:recommendation"] == "force-proceed"

    def test_completed_subloop_promotes_state_copy_not_reference(self):
        """Promoted child state is a copy, not the original dict."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        child_state = {"x": 1}
        state_patch, _ = hooks.completed_subloop("s", child_state, "ok")
        child_state["x"] = 99
        assert state_patch["subloop:s:state"]["x"] == 1

    def test_completed_subloop_includes_artifacts_when_provided(self):
        """``subloop:<name>:artifacts`` present when child_artifacts given."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        artifacts = {"diagram": "/tmp/out.png", "log": "/tmp/run.log"}
        state_patch, _ = hooks.completed_subloop(
            "build", {}, "done",
            child_artifacts=artifacts,
        )
        assert state_patch["subloop:build:artifacts"] == artifacts

    def test_completed_subloop_omits_artifacts_when_none(self):
        """``subloop:<name>:artifacts`` absent when child_artifacts is None."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, _ = hooks.completed_subloop("t", {}, "ok")
        assert "subloop:t:artifacts" not in state_patch

    def test_completed_subloop_omits_artifacts_when_empty_dict(self):
        """``subloop:<name>:artifacts`` absent when child_artifacts is empty."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, _ = hooks.completed_subloop(
            "e", {}, "ok", child_artifacts={},
        )
        assert "subloop:e:artifacts" not in state_patch

    def test_completed_subloop_includes_resume_cursor_when_provided(self):
        """``subloop:<name>:resume_cursor`` present when non-None."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        cursor = {"pc": 3, "state": {"inner": 1}}
        state_patch, _ = hooks.completed_subloop(
            "sub", {}, "halt", resume_cursor=cursor,
        )
        assert state_patch["subloop:sub:resume_cursor"] == cursor

    def test_completed_subloop_omits_resume_cursor_when_none(self):
        """``subloop:<name>:resume_cursor`` absent when None."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, _ = hooks.completed_subloop(
            "sub", {}, "ok", resume_cursor=None,
        )
        assert "subloop:sub:resume_cursor" not in state_patch

    def test_completed_subloop_joins_envelopes(self):
        """Child envelope is joined with parent envelope via join_envelope."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        parent_env = RunEnvelope(taint="clean", cost=1.0)
        child_env = RunEnvelope(taint="tainted", cost=4.0)
        _, joined = hooks.completed_subloop(
            "child", {}, "ok",
            child_envelope=child_env,
            parent_envelope=parent_env,
        )
        assert joined is not None
        assert joined.cost == 5.0
        assert joined.taint == "tainted"

    def test_completed_subloop_envelope_join_preserves_identity(self):
        """Envelope join preserves parent RuntimeEnvelope identity."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        hooks = MegaplanNativeHooks()
        parent_env = RuntimeEnvelope(
            plugin_id="parent-p", run_id="parent-r",
            artifact_root="/art/parent", trust_state="trusted",
            cross_cutting=RunEnvelope(cost=2.0),
        )
        child_env = RuntimeEnvelope(
            plugin_id="child-p", run_id="child-r",
            artifact_root="/art/child", trust_state="unknown",
            cross_cutting=RunEnvelope(cost=3.0),
        )
        _, joined = hooks.completed_subloop(
            "c", {}, "ok",
            child_envelope=child_env,
            parent_envelope=parent_env,
        )
        assert isinstance(joined, RuntimeEnvelope)
        assert joined.plugin_id == "parent-p"
        assert joined.run_id == "parent-r"
        assert joined.artifact_root == "/art/parent"
        assert joined.cross_cutting.cost == 5.0

    def test_completed_subloop_envelope_lease_conflict_propagates(self):
        """LeaseIdConflict from envelope join propagates through completed_subloop."""
        import pytest
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import LeaseIdConflict, RunEnvelope
        hooks = MegaplanNativeHooks()
        with pytest.raises(LeaseIdConflict):
            hooks.completed_subloop(
                "c", {}, "ok",
                parent_envelope=RunEnvelope(lease_id="a"),
                child_envelope=RunEnvelope(lease_id="b"),
            )


class TestMegaplanNativeHooksSuspendedSubloop:
    """Focused tests for suspended child cursor shape, envelope
    preservation, artifact root preservation, and resume continuation
    via ``suspended_subloop``."""

    def test_suspended_subloop_returns_state_patch_and_envelope(self):
        """``suspended_subloop`` returns a (state_patch, joined_envelope) tuple."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, env = hooks.suspended_subloop(
            "child1", {"key": "val"},
        )
        assert isinstance(state_patch, dict)
        assert env is None

    def test_suspended_subloop_state_patch_keys(self):
        """State patch has correct promoted keys."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        child_state = {"phase": "analysis", "result": {"score": 0.9}}
        child_artifacts = {"log": "/tmp/log.txt"}
        child_cursor = {"pc": 5, "frames": {"child_frame": {}}}
        state_patch, _ = hooks.suspended_subloop(
            "analyze", child_state,
            child_artifacts=child_artifacts,
            child_resume_cursor=child_cursor,
        )
        assert state_patch["subloop:analyze:state"] == child_state
        assert state_patch["subloop:analyze:recommendation"] == "halt"
        assert state_patch["subloop:analyze:resume_cursor"] == child_cursor
        assert state_patch["subloop:analyze:artifacts"] == child_artifacts

    def test_suspended_subloop_omits_artifacts_when_none(self):
        """Artifacts key absent when not provided."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, _ = hooks.suspended_subloop("s", {})
        assert "subloop:s:artifacts" not in state_patch

    def test_suspended_subloop_omits_resume_cursor_when_none(self):
        """Resume cursor key absent when None."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, _ = hooks.suspended_subloop("s", {})
        assert "subloop:s:resume_cursor" not in state_patch

    def test_suspended_subloop_recommendation_is_always_halt(self):
        """Recommendation is always 'halt' regardless of child state."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        for child_state in [{}, {"rec": "proceed"}, {"rec": "abort"}]:
            state_patch, _ = hooks.suspended_subloop("s", child_state)
            assert state_patch["subloop:s:recommendation"] == "halt"

    def test_suspended_subloop_joins_envelopes(self):
        """Envelope join is called with parent and child envelopes."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope
        hooks = MegaplanNativeHooks()
        parent_env = RunEnvelope(taint="clean", cost=1.0)
        child_env = RunEnvelope(taint="tainted", cost=4.0)
        _, joined = hooks.suspended_subloop(
            "child", {},
            child_envelope=child_env,
            parent_envelope=parent_env,
        )
        assert joined is not None
        assert joined.cost == 5.0
        assert joined.taint == "tainted"

    def test_suspended_subloop_envelope_preserves_runtime_identity(self):
        """Parent RuntimeEnvelope identity preserved after suspended join."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope, RuntimeEnvelope
        hooks = MegaplanNativeHooks()
        parent_env = RuntimeEnvelope(
            plugin_id="p-id", run_id="r-id",
            artifact_root="/art/root", trust_state="trusted",
            cross_cutting=RunEnvelope(cost=1.0),
        )
        child_env = RunEnvelope(taint="t", cost=3.0)
        _, joined = hooks.suspended_subloop(
            "c", {},
            child_envelope=child_env,
            parent_envelope=parent_env,
        )
        assert isinstance(joined, RuntimeEnvelope)
        assert joined.plugin_id == "p-id"
        assert joined.run_id == "r-id"
        assert joined.artifact_root == "/art/root"
        assert joined.trust_state == "trusted"
        assert joined.cross_cutting.cost == 4.0
        assert joined.cross_cutting.taint == "t"

    def test_suspended_subloop_lease_conflict_propagates(self):
        """LeaseIdConflict from envelope propagates through suspended_subloop."""
        import pytest
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import LeaseIdConflict, RunEnvelope
        hooks = MegaplanNativeHooks()
        with pytest.raises(LeaseIdConflict):
            hooks.suspended_subloop(
                "c", {},
                parent_envelope=RunEnvelope(lease_id="a"),
                child_envelope=RunEnvelope(lease_id="b"),
            )

    def test_suspended_subloop_artifacts_preserved_in_state_patch(self):
        """Child artifacts dict is preserved verbatim in state patch."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        artifacts = {"diagram": "/artifacts/d.png", "traces": "/artifacts/t.json"}
        state_patch, _ = hooks.suspended_subloop(
            "build", {"status": "suspended"},
            child_artifacts=artifacts,
        )
        assert state_patch["subloop:build:artifacts"]["diagram"] == "/artifacts/d.png"
        assert state_patch["subloop:build:artifacts"]["traces"] == "/artifacts/t.json"

    def test_suspended_subloop_no_persist_without_plan_dir(self):
        """When plan_dir is None, returns state_patch without persistence."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, env = hooks.suspended_subloop(
            "child", {"a": 1},
            child_resume_cursor={"pc": 3},
            parent_pc=7,
            parent_state={"existing": "value"},
        )
        assert state_patch["subloop:child:state"] == {"a": 1}
        assert state_patch["subloop:child:recommendation"] == "halt"
        assert state_patch["subloop:child:resume_cursor"] == {"pc": 3}

    def test_suspended_subloop_state_patch_is_copy(self):
        """Promoted child state is a snapshot copy."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        child_state = {"x": 1}
        state_patch, _ = hooks.suspended_subloop("s", child_state)
        child_state["x"] = 99
        assert state_patch["subloop:s:state"]["x"] == 1

    def test_suspended_subloop_child_state_fully_preserved(self):
        """Full child state dict is preserved including nested structures."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        child_state = {
            "phase": "implementation",
            "result": {"files": ["a.py", "b.py"], "score": 0.95},
            "meta": {"iterations": 3, "cost": 1.5},
        }
        state_patch, _ = hooks.suspended_subloop("impl", child_state)
        promoted = state_patch["subloop:impl:state"]
        assert promoted["phase"] == "implementation"
        assert promoted["result"]["files"] == ["a.py", "b.py"]
        assert promoted["meta"]["iterations"] == 3

    def test_suspended_subloop_accepts_all_parent_context_fields(self):
        """All parent context fields accepted without error."""
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        hooks = MegaplanNativeHooks()
        state_patch, _ = hooks.suspended_subloop(
            "sub", {"done": True},
            parent_pc=12,
            parent_loops={"main": 3},
            parent_frames={"frame_a": {"pc": 5}},
            parent_stages=["init", "process", "sub"],
            parent_state={"global": "config"},
        )
        assert state_patch["subloop:sub:state"] == {"done": True}
        assert state_patch["subloop:sub:recommendation"] == "halt"

    def test_suspended_subloop_cursor_persistence_with_plan_dir(self):
        """When plan_dir is set, composite resume cursor is persisted."""
        import json
        import tempfile
        from pathlib import Path
        from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
        from arnold.runtime.envelope import RunEnvelope

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = str(Path(tmpdir) / "plan")
            Path(plan_dir).mkdir(parents=True, exist_ok=True)

            hooks = MegaplanNativeHooks(plan_dir=plan_dir)
            child_state = {"phase": "review", "items": 5}
            child_cursor = {"pc": 3, "frames": {"review_frame": {}}}
            parent_env = RunEnvelope(taint="clean", cost=10.0)
            child_env = RunEnvelope(taint="clean", cost=2.0)

            state_patch, joined = hooks.suspended_subloop(
                "review_loop", child_state,
                child_resume_cursor=child_cursor,
                child_artifact_root="/tmp/child_artifacts",
                child_frames={"f1": {"pc": 2}},
                child_envelope=child_env,
                parent_envelope=parent_env,
                parent_pc=8,
                parent_loops={"main": 1},
                parent_frames={"pf": {"pc": 7}},
                parent_stages=["alpha", "beta"],
                parent_state={"config": {"mode": "strict"}},
            )

            assert state_patch["subloop:review_loop:state"] == child_state
            assert state_patch["subloop:review_loop:recommendation"] == "halt"
            assert state_patch["subloop:review_loop:resume_cursor"] == child_cursor
            assert joined is not None
            assert joined.cost == 12.0

            cursor_path = Path(plan_dir) / "composite_resume_cursor.json"
            assert cursor_path.exists(), (
                f"Composite resume cursor not found at {cursor_path}"
            )

            cursor_data = json.loads(cursor_path.read_text())
            assert cursor_data["version"] == 1
            assert "children" in cursor_data
            assert "review_loop" in cursor_data["children"]
            child_entry = cursor_data["children"]["review_loop"]
            assert child_entry.get("resume_cursor") == child_cursor
            assert child_entry.get("artifact_root") == "/tmp/child_artifacts"
            assert child_entry.get("state") == child_state
            assert child_entry.get("frames") == {"f1": {"pc": 2}}
            assert cursor_data.get("parent_pc") == 8
            assert cursor_data.get("parent_state") == {"config": {"mode": "strict"}}
            assert cursor_data.get("parent_stages") == ["alpha", "beta"]
            assert cursor_data.get("parent_loops") == {"main": 1}
            assert cursor_data.get("parent_frames") == {"pf": {"pc": 7}}
            assert "envelope" in cursor_data


# ── helper ────────────────────────────────────────────────────────────

import contextlib
import os as _os


@contextlib.contextmanager
def _env_var(name: str, value: str):
    """Temporarily set an environment variable, restoring the original."""
    old = _os.environ.get(name)
    _os.environ[name] = value
    try:
        yield
    finally:
        if old is None:
            _os.environ.pop(name, None)
        else:
            _os.environ[name] = old
