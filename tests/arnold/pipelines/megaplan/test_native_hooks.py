"""Tests for MegaplanNativeHooks state merge and persistence behaviour.

Proves:
- ``_state_meta.versions`` increments only for changed keys.
- Unrelated handler-owned on-disk keys survive ``write_plan_state``
  with ``mode="executor-key-merge"``.
- Typed-port CAS merge vs legacy ``dict.update`` fallback.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from arnold.pipeline.native.ir import NativeInstruction
from arnold.pipelines.megaplan.native_hooks import MegaplanNativeHooks
from arnold.pipelines.megaplan._core.state import write_plan_state
from arnold.pipelines.megaplan._pipeline.types import StateDelta, StateDeltaConflict, apply_delta


# ── helpers ────────────────────────────────────────────────────────────────


def _make_instr(name: str = "test_phase") -> NativeInstruction:
    """Minimal NativeInstruction for merge_state tests."""
    return NativeInstruction(pc=0, op="phase", name=name)


def _state_meta_versions(state: dict) -> dict:
    """Return ``state['_state_meta']['versions']`` or ``{}``."""
    meta = state.get("_state_meta", {})
    return dict(meta.get("versions", {})) if isinstance(meta, dict) else {}


# ── merge_state tests ──────────────────────────────────────────────────────


class TestMergeState:
    """In-memory state merge via MegaplanNativeHooks.merge_state."""

    def test_empty_outputs_noop(self):
        """merge_state with empty outputs returns state and owned_keys unchanged."""
        hooks = MegaplanNativeHooks()
        instr = _make_instr()
        state = {"x": 1, "y": 2}
        owned = frozenset({"y"})
        new_state, new_owned = hooks.merge_state(instr, state, {}, owned)
        assert new_state is state  # identity when no outputs
        assert new_owned is owned

    def test_legacy_dict_update_no_typed_ports(self):
        """When typed ports off, merge_state uses dict.update (legacy path)."""
        hooks = MegaplanNativeHooks()
        instr = _make_instr()
        state = {"a": 1, "_state_meta": {"versions": {"a": 3}}}
        owned = frozenset({"a"})
        outputs = {"b": 2, "c": 3}

        new_state, new_owned = hooks.merge_state(instr, state, outputs, owned)

        assert new_state["a"] == 1
        assert new_state["b"] == 2
        assert new_state["c"] == 3
        # Legacy path: _state_meta.versions is NOT updated for new keys
        versions = _state_meta_versions(new_state)
        assert versions.get("a") == 3  # unchanged
        assert "b" not in versions  # legacy does not track versions
        assert "c" not in versions
        # Owned keys accumulate
        assert new_owned == frozenset({"a", "b", "c"})

    @mock.patch.dict(os.environ, {"MEGAPLAN_TYPED_PORTS": "1"})
    def test_typed_ports_cas_increments_only_changed_keys(self):
        """CAS path increments _state_meta.versions ONLY for keys present in outputs."""
        hooks = MegaplanNativeHooks()
        instr = _make_instr()
        state = {
            "alpha": "old_alpha",
            "beta": "keep_beta",
            "gamma": "keep_gamma",
            "_state_meta": {
                "versions": {"alpha": 2, "beta": 5, "gamma": 1}
            },
        }
        owned = frozenset({"alpha", "beta"})
        # Only alpha changes; beta is not in outputs, gamma is not owned
        outputs = {"alpha": "new_alpha", "delta": "new_delta"}

        new_state, new_owned = hooks.merge_state(instr, state, outputs, owned)

        # Changed key alpha → version incremented
        versions = _state_meta_versions(new_state)
        assert versions["alpha"] == 3  # was 2, now 3
        # Unchanged owned key beta → version unchanged
        assert versions["beta"] == 5
        # Unchanged non-owned key gamma → version unchanged
        assert versions["gamma"] == 1
        # New key delta → version starts at 1
        assert versions["delta"] == 1

        # Values
        assert new_state["alpha"] == "new_alpha"
        assert new_state["beta"] == "keep_beta"
        assert new_state["gamma"] == "keep_gamma"
        assert new_state["delta"] == "new_delta"

        # Owned keys: previous owned + new output keys
        assert new_owned == frozenset({"alpha", "beta", "delta"})

    @mock.patch.dict(os.environ, {"MEGAPLAN_TYPED_PORTS": "1"})
    def test_typed_ports_new_key_starts_at_version_1(self):
        """A brand-new key in outputs gets version 1 via CAS path."""
        hooks = MegaplanNativeHooks()
        instr = _make_instr()
        state: dict = {}  # no existing state or meta
        owned: frozenset[str] = frozenset()
        outputs = {"fresh": 42}

        new_state, new_owned = hooks.merge_state(instr, state, outputs, owned)

        versions = _state_meta_versions(new_state)
        assert versions["fresh"] == 1
        assert new_state["fresh"] == 42
        assert new_owned == frozenset({"fresh"})

    @mock.patch.dict(os.environ, {"MEGAPLAN_TYPED_PORTS": "1"})
    def test_typed_ports_cas_conflict_falls_back_to_lww(self):
        """When StateDeltaConflict fires, merge_state falls back to last-writer-wins."""
        hooks = MegaplanNativeHooks()
        instr = _make_instr()
        # Simulate a stale version: state has version 10 for key "x",
        # but merge_state will compute current_version=10 and pass it as the
        # expected version to StateDelta.  If apply_delta raises
        # StateDeltaConflict, the fallback still writes the value.
        state = {
            "x": "old",
            "_state_meta": {"versions": {"x": 10}},
        }
        owned = frozenset({"x"})
        outputs = {"x": "new"}

        # To trigger the conflict we patch apply_delta to raise
        # StateDeltaConflict on the first call, then use the real one.
        real_apply = apply_delta
        call_count = [0]

        def _conflict_then_real(s, d):
            call_count[0] += 1
            if call_count[0] == 1:
                raise StateDeltaConflict(d.key, d.version, d.version + 5)
            return real_apply(s, d)

        with mock.patch(
            "arnold.pipelines.megaplan._pipeline.types.apply_delta",
            side_effect=_conflict_then_real,
        ):
            new_state, new_owned = hooks.merge_state(instr, state, outputs, owned)

        # Fallback LWW still writes the value
        assert new_state["x"] == "new"
        # Owned keys unchanged
        assert new_owned == frozenset({"x"})

    @mock.patch.dict(os.environ, {"MEGAPLAN_TYPED_PORTS": "1"})
    def test_typed_ports_preserves_unrelated_state_keys(self):
        """CAS merge preserves state keys not in outputs and not in _state_meta."""
        hooks = MegaplanNativeHooks()
        instr = _make_instr()
        state = {
            "handler_owned_1": "h1",
            "handler_owned_2": "h2",
            "executor_owned": "old_exec",
            "_state_meta": {"versions": {"executor_owned": 3}},
        }
        owned = frozenset({"executor_owned"})
        outputs = {"executor_owned": "new_exec"}

        new_state, _ = hooks.merge_state(instr, state, outputs, owned)

        # Unrelated handler-owned keys survive
        assert new_state["handler_owned_1"] == "h1"
        assert new_state["handler_owned_2"] == "h2"
        # Executor-owned key updated
        assert new_state["executor_owned"] == "new_exec"
        versions = _state_meta_versions(new_state)
        assert versions["executor_owned"] == 4

    @mock.patch.dict(os.environ, {"MEGAPLAN_TYPED_PORTS": "1"})
    def test_typed_ports_multiple_changed_keys(self):
        """Multiple changed keys each get their version incremented."""
        hooks = MegaplanNativeHooks()
        instr = _make_instr()
        state = {
            "k1": "v1_old",
            "k2": "v2_old",
            "k3": "v3_keep",
            "_state_meta": {"versions": {"k1": 1, "k2": 2, "k3": 3}},
        }
        owned = frozenset({"k1", "k2", "k3"})
        outputs = {"k1": "v1_new", "k2": "v2_new"}

        new_state, _ = hooks.merge_state(instr, state, outputs, owned)

        versions = _state_meta_versions(new_state)
        assert versions["k1"] == 2
        assert versions["k2"] == 3
        assert versions["k3"] == 3  # unchanged


# ── persistence (executor-key-merge) tests ─────────────────────────────────


class TestExecutorKeyMergePersistence:
    """On-disk ``write_plan_state(..., mode="executor-key-merge")`` behaviour."""

    def test_unrelated_handler_keys_survive_merge(self):
        """Unrelated on-disk keys not in executor_owned_keys are preserved."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            state_path = plan_dir / "state.json"

            # Pre-populate on-disk state with handler-owned keys
            on_disk = {
                "handler_a": "keep_me",
                "handler_b": {"nested": True},
                "exec_key": "old_exec",
                "current_state": "initialized",
                "schema_version": 0,
            }
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(on_disk), encoding="utf-8")

            # Write with executor-key-merge: only exec_key changes
            new_state_data = {"exec_key": "new_exec"}
            result = write_plan_state(
                plan_dir,
                mode="executor-key-merge",
                state=new_state_data,
                executor_owned_keys=["exec_key"],
            )

            # Handler-owned keys survive
            assert result["handler_a"] == "keep_me"
            assert result["handler_b"] == {"nested": True}
            # Executor key updated
            assert result["exec_key"] == "new_exec"
            # Structural keys preserved
            assert result["current_state"] == "initialized"
            assert result["schema_version"] == 0

            # Verify on-disk round-trip
            disk = json.loads(state_path.read_text(encoding="utf-8"))
            assert disk["handler_a"] == "keep_me"
            assert disk["handler_b"] == {"nested": True}
            assert disk["exec_key"] == "new_exec"

    def test_executor_key_not_in_state_not_written(self):
        """Keys in executor_owned_keys but absent from the incoming state are
        left untouched on disk."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            state_path = plan_dir / "state.json"

            on_disk = {
                "alpha": "original",
                "current_state": "initialized",
                "schema_version": 0,
            }
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(on_disk), encoding="utf-8")

            # executor_owned_keys includes "beta" but state only has "alpha"
            new_state_data = {"alpha": "updated"}
            result = write_plan_state(
                plan_dir,
                mode="executor-key-merge",
                state=new_state_data,
                executor_owned_keys=["alpha", "beta"],
            )

            assert result["alpha"] == "updated"
            # On-disk round-trip
            disk = json.loads(state_path.read_text(encoding="utf-8"))
            assert disk["alpha"] == "updated"

    def test_no_existing_state_file_creates_new(self):
        """When state.json doesn't exist, executor-key-merge creates it."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp) / "new_plan"
            plan_dir.mkdir(parents=True, exist_ok=True)
            state_path = plan_dir / "state.json"
            assert not state_path.exists()

            new_state_data = {"key1": "val1", "key2": "val2"}
            result = write_plan_state(
                plan_dir,
                mode="executor-key-merge",
                state=new_state_data,
                executor_owned_keys=["key1"],
            )

            assert result["key1"] == "val1"
            assert result["key2"] == "val2"
            assert state_path.exists()
            disk = json.loads(state_path.read_text(encoding="utf-8"))
            assert disk == result

    @mock.patch.dict(os.environ, {"MEGAPLAN_TYPED_PORTS": "1"})
    def test_executor_key_merge_typed_ports_cas(self):
        """With MEGAPLAN_TYPED_PORTS=1, executor-key-merge uses CAS path."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            state_path = plan_dir / "state.json"

            on_disk = {
                "exec_key": "old",
                "unrelated": "keep",
                "_state_meta": {"versions": {"exec_key": 3}},
                "current_state": "initialized",
                "schema_version": 0,
            }
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(on_disk), encoding="utf-8")

            new_state_data = {"exec_key": "new"}
            result = write_plan_state(
                plan_dir,
                mode="executor-key-merge",
                state=new_state_data,
                executor_owned_keys=["exec_key"],
            )

            assert result["exec_key"] == "new"
            assert result["unrelated"] == "keep"
            versions = _state_meta_versions(result)
            assert versions["exec_key"] == 4  # incremented via CAS

    @mock.patch.dict(os.environ, {"MEGAPLAN_TYPED_PORTS": "1"})
    def test_executor_key_merge_typed_ports_no_existing_state(self):
        """Typed ports CAS path handles missing state.json correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp) / "fresh_plan"
            plan_dir.mkdir(parents=True, exist_ok=True)

            new_state_data = {"exec_key": "first_write"}
            result = write_plan_state(
                plan_dir,
                mode="executor-key-merge",
                state=new_state_data,
                executor_owned_keys=["exec_key"],
            )

            assert result["exec_key"] == "first_write"

    def test_state_meta_versions_preserved_for_unrelated_keys(self):
        """When merging, _state_meta.versions for unrelated keys are untouched."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            state_path = plan_dir / "state.json"

            on_disk = {
                "exec_key": "old_exec",
                "unrelated_key": "keep_unrelated",
                "_state_meta": {"versions": {"exec_key": 2, "unrelated_key": 7}},
                "current_state": "initialized",
                "schema_version": 0,
            }
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(on_disk), encoding="utf-8")

            new_state_data = {"exec_key": "new_exec"}
            result = write_plan_state(
                plan_dir,
                mode="executor-key-merge",
                state=new_state_data,
                executor_owned_keys=["exec_key"],
            )

            # Unrelated key survives unchanged
            assert result["unrelated_key"] == "keep_unrelated"
            # Executor key updated (legacy path since no typed ports flag here)
            assert result["exec_key"] == "new_exec"

    def test_multiple_executor_keys_merged(self):
        """Multiple executor-owned keys are merged while unrelated keys survive."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            state_path = plan_dir / "state.json"

            on_disk = {
                "ek1": "old1",
                "ek2": "old2",
                "ek3": "old3",
                "handler_x": "hx",
                "handler_y": "hy",
                "current_state": "initialized",
                "schema_version": 0,
            }
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(on_disk), encoding="utf-8")

            new_state_data = {"ek1": "new1", "ek2": "new2"}
            result = write_plan_state(
                plan_dir,
                mode="executor-key-merge",
                state=new_state_data,
                executor_owned_keys=["ek1", "ek2", "ek3"],
            )

            assert result["ek1"] == "new1"
            assert result["ek2"] == "new2"
            assert result["ek3"] == "old3"  # in owned_keys but not in state → untouched
            assert result["handler_x"] == "hx"
            assert result["handler_y"] == "hy"


# ── override tests ─────────────────────────────────────────────────────────


class TestOverrides:
    """Override resolution via MegaplanNativeHooks.on_step_start."""

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _make_instr(name: str = "planning_gate", op: str = "decision") -> NativeInstruction:
        """Build a decision instruction for override tests."""
        return NativeInstruction(
            pc=0,
            op=op,
            name=name,
            decision_vocabulary=frozenset({"proceed", "iterate", "tiebreaker", "escalate"}),
        )

    @staticmethod
    def _state_with_overrides(*overrides: dict) -> dict:
        """Return a working state dict carrying the provided override entries."""
        return {
            "meta": {
                "overrides": list(overrides),
            },
        }

    # ── control overrides skip the decision callable ───────────────────

    def test_control_override_transition_sets_override_route(self):
        """A transition override sets __override_route__ and skips the decision."""
        hooks = MegaplanNativeHooks()
        instr = self._make_instr()
        state = self._state_with_overrides(
            {"action": "force-proceed", "source": "cli"},
        )
        ctx = {"state": state}

        result = hooks.on_step_start(instr, ctx)

        assert "__override_route__" in result
        assert result["__override_route__"] == "override force-proceed"
        # The route label uses the CLI spelling, not the internal one
        assert result["__override_route__"].startswith("override ")

    def test_control_override_termination_sets_override_route(self):
        """A termination override (abort) sets __override_route__."""
        hooks = MegaplanNativeHooks()
        instr = self._make_instr()
        state = self._state_with_overrides(
            {"action": "abort", "source": "user"},
        )
        ctx = {"state": state}

        result = hooks.on_step_start(instr, ctx)

        assert "__override_route__" in result
        assert result["__override_route__"] == "override abort"

    def test_control_override_recovery_sets_override_route(self):
        """A recovery override (recover-blocked) sets __override_route__."""
        hooks = MegaplanNativeHooks()
        instr = self._make_instr()
        state = self._state_with_overrides(
            {"action": "recover-blocked", "source": "auto"},
        )
        ctx = {"state": state}

        result = hooks.on_step_start(instr, ctx)

        assert "__override_route__" in result
        assert result["__override_route__"] == "override recover-blocked"

    def test_control_override_first_wins(self):
        """When multiple control overrides are present, the first (in reversed
        order, i.e. last in the list) wins — matching the first-control-wins
        short-circuit behaviour in the implementation."""
        hooks = MegaplanNativeHooks()
        instr = self._make_instr()
        # Last entry in the list is processed first (reversed iteration),
        # so it wins.
        state = self._state_with_overrides(
            {"action": "abort", "source": "auto"},
            {"action": "force-proceed", "source": "cli"},
        )
        ctx = {"state": state}

        result = hooks.on_step_start(instr, ctx)

        # force-proceed is last in the list → processed first → wins
        assert result["__override_route__"] == "override force-proceed"

    @mock.patch(
        "arnold.pipelines.megaplan.native_hooks.MegaplanNativeHooks._get_override_catalog",
        return_value={"force-proceed": {"kind": "transition"}},
    )
    def test_control_override_does_not_modify_state(self, _mock_catalog):
        """A control override short-circuits without mutating working state."""
        hooks = MegaplanNativeHooks()
        instr = self._make_instr()
        original_state = self._state_with_overrides(
            {"action": "force-proceed", "source": "cli"},
        )
        state = dict(original_state)
        ctx = {"state": state}

        result = hooks.on_step_start(instr, ctx)

        # State should be unmodified (no additive changes)
        assert result.get("state", {}) == state

    # ── additive overrides still call the decision ─────────────────────

    def test_additive_override_annotation_no_route_set(self):
        """An annotation override (add-note) mutates state but does NOT set
        __override_route__, so the decision callable is still invoked."""
        hooks = MegaplanNativeHooks()
        instr = self._make_instr()
        state = self._state_with_overrides(
            {"action": "add-note", "reason": "test note", "source": "reviewer"},
        )
        ctx = {"state": state}

        result = hooks.on_step_start(instr, ctx)

        # No override route set — decision runs normally
        assert "__override_route__" not in result
        # State is mutated: note appended to meta.notes
        meta = result["state"]["meta"]
        assert "notes" in meta
        assert len(meta["notes"]) == 1
        assert meta["notes"][0]["text"] == "test note"
        assert meta["notes"][0]["source"] == "reviewer"

    def test_additive_override_config_no_route_set(self):
        """A config override (set-model) mutates state.config but does NOT set
        __override_route__."""
        hooks = MegaplanNativeHooks()
        instr = self._make_instr()
        state = self._state_with_overrides(
            {"action": "set-model", "model": "claude-4", "source": "cli"},
        )
        ctx = {"state": state}

        result = hooks.on_step_start(instr, ctx)

        # No override route set
        assert "__override_route__" not in result
        # Config mutated
        assert result["state"]["config"]["model"] == "claude-4"

    def test_additive_override_set_profile_no_route_set(self):
        """A config override (set-profile) mutates state.config."""
        hooks = MegaplanNativeHooks()
        instr = self._make_instr()
        state = self._state_with_overrides(
            {"action": "set-profile", "profile": "thorough", "source": "cli"},
        )
        ctx = {"state": state}

        result = hooks.on_step_start(instr, ctx)

        assert "__override_route__" not in result
        assert result["state"]["config"]["profile"] == "thorough"

    def test_additive_override_no_overrides_noop(self):
        """When meta.overrides is empty or absent, ctx is returned unchanged."""
        hooks = MegaplanNativeHooks()
        instr = self._make_instr()
        # No overrides at all
        state = {"meta": {}}
        ctx = {"state": state}

        result = hooks.on_step_start(instr, ctx)
        assert result is ctx  # identity preserved for no-op

        # Empty overrides list
        state2 = {"meta": {"overrides": []}}
        ctx2 = {"state": state2}
        result2 = hooks.on_step_start(instr, ctx2)
        assert result2 is ctx2

    def test_additive_override_no_state_noop(self):
        """When ctx has no 'state' key, the hook returns ctx unchanged."""
        hooks = MegaplanNativeHooks()
        instr = self._make_instr()
        ctx: dict = {"other": "value"}

        result = hooks.on_step_start(instr, ctx)
        assert result == ctx

    # ── CLI spelling normalization ─────────────────────────────────────

    def test_cli_to_internal_hyphen_to_underscore(self):
        """The _cli_to_internal helper normalizes known hyphenated CLI labels."""
        hooks = MegaplanNativeHooks()
        # force-proceed → force_proceed (explicitly mapped in routing module)
        assert hooks._cli_to_internal("force-proceed") == "force_proceed"
        # Labels not in the explicit mapping pass through unchanged
        # (the catalog lookup handles both spellings)
        assert hooks._cli_to_internal("add-note") == "add-note"
        assert hooks._cli_to_internal("recover-blocked") == "recover-blocked"
        assert hooks._cli_to_internal("set-model") == "set-model"
        assert hooks._cli_to_internal("set-profile") == "set-profile"

    def test_cli_to_internal_already_underscored(self):
        """Already underscore-separated labels pass through unchanged."""
        hooks = MegaplanNativeHooks()
        assert hooks._cli_to_internal("force_proceed") == "force_proceed"
        assert hooks._cli_to_internal("abort") == "abort"
        assert hooks._cli_to_internal("replan") == "replan"

    def test_cli_normalization_in_override_resolution(self):
        """When an override uses CLI spelling (hyphenated), the normalization
        still resolves the correct catalog kind."""
        hooks = MegaplanNativeHooks()
        instr = self._make_instr()
        # Use CLI spelling "force-proceed"
        state = self._state_with_overrides(
            {"action": "force-proceed", "source": "cli"},
        )
        ctx = {"state": state}

        result = hooks.on_step_start(instr, ctx)

        # Should resolve via CLI→internal normalization
        assert result["__override_route__"] == "override force-proceed"

    # ── OVERRIDE_APPLIED event payload ─────────────────────────────────

    def test_override_applied_event_emitted_with_plan_dir(self):
        """When plan_dir is configured, a control override emits OVERRIDE_APPLIED
        with the correct event payload keys."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            hooks = MegaplanNativeHooks(plan_dir=plan_dir)
            instr = self._make_instr()
            state = self._state_with_overrides(
                {"action": "force-proceed", "source": "cli"},
            )
            ctx = {"state": state}

            result = hooks.on_step_start(instr, ctx)

            # Route was set
            assert result["__override_route__"] == "override force-proceed"

            # Check that an event was written to events.ndjson
            events_path = plan_dir / "events.ndjson"
            assert events_path.exists(), "OVERRIDE_APPLIED event should be written"

            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").strip().splitlines()]
            override_events = [e for e in events if e.get("kind") == "override_applied"]
            assert len(override_events) == 1

            event = override_events[0]
            payload = event.get("payload", {})
            assert payload.get("step_id") == "planning_gate"
            assert payload.get("override_key") == "force_proceed"  # internal spelling
            assert payload.get("source") == "cli"
            assert payload.get("resolved_value") == "override force-proceed"
            assert "timestamp" in payload

    def test_override_applied_event_not_emitted_without_plan_dir(self):
        """When plan_dir is None, OVERRIDE_APPLIED is not emitted (no-op)."""
        hooks = MegaplanNativeHooks()  # no plan_dir
        instr = self._make_instr()
        state = self._state_with_overrides(
            {"action": "abort", "source": "user"},
        )
        ctx = {"state": state}

        result = hooks.on_step_start(instr, ctx)

        # Route is set even without plan_dir
        assert result["__override_route__"] == "override abort"
        # No file written

    def test_override_applied_event_not_emitted_for_additive(self):
        """Additive overrides do NOT emit OVERRIDE_APPLIED events."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            hooks = MegaplanNativeHooks(plan_dir=plan_dir)
            instr = self._make_instr()
            state = self._state_with_overrides(
                {"action": "add-note", "reason": "test", "source": "reviewer"},
            )
            ctx = {"state": state}

            hooks.on_step_start(instr, ctx)

            # No events.ndjson should exist for additive-only
            events_path = plan_dir / "events.ndjson"
            # May or may not exist; if it exists, it should not have override_applied
            if events_path.exists():
                events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").strip().splitlines()]
                override_events = [e for e in events if e.get("kind") == "override_applied"]
                assert len(override_events) == 0

    # ── event order before the next routed step ────────────────────────

    def test_event_order_override_applied_before_route_returned(self):
        """OVERRIDE_APPLIED is emitted before __override_route__ is set in the
        returned context.  We verify this by capturing the sequence of calls."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            hooks = MegaplanNativeHooks(plan_dir=plan_dir)
            instr = self._make_instr()
            state = self._state_with_overrides(
                {"action": "force-proceed", "source": "cli"},
            )
            ctx = {"state": state}

            # Instrument _emit_override_applied to record call order
            call_order = []

            original_emit = hooks._emit_override_applied

            def tracking_emit(**kwargs):
                call_order.append("emit")
                return original_emit(**kwargs)

            hooks._emit_override_applied = tracking_emit  # type: ignore[method-assign]

            result = hooks.on_step_start(instr, ctx)

            # After on_step_start returns, __override_route__ is set
            assert result["__override_route__"] == "override force-proceed"
            # The emit call happened (was tracked)
            assert call_order == ["emit"], (
                "emit should be called exactly once before the route is returned"
            )

    def test_event_payload_matches_returned_route(self):
        """The OVERRIDE_APPLIED resolved_value matches the __override_route__
        returned in ctx."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            hooks = MegaplanNativeHooks(plan_dir=plan_dir)
            instr = self._make_instr("safety_gate")
            state = self._state_with_overrides(
                {"action": "abort", "source": "user"},
            )
            ctx = {"state": state}

            result = hooks.on_step_start(instr, ctx)

            events_path = plan_dir / "events.ndjson"
            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").strip().splitlines()]
            event = [e for e in events if e.get("kind") == "override_applied"][0]

            # Route in ctx matches resolved_value in event
            assert result["__override_route__"] == event["payload"]["resolved_value"]
            assert result["__override_route__"] == "override abort"
            assert event["payload"]["step_id"] == "safety_gate"

    def test_override_applied_event_sequence_number_monotonic(self):
        """Consecutive override events get increasing sequence numbers."""
        with tempfile.TemporaryDirectory() as tmp:
            plan_dir = Path(tmp)
            hooks = MegaplanNativeHooks(plan_dir=plan_dir)
            instr = self._make_instr()

            # First override
            state1 = self._state_with_overrides(
                {"action": "force-proceed", "source": "cli"},
            )
            hooks.on_step_start(instr, {"state": state1})

            # Second override (different step)
            state2 = self._state_with_overrides(
                {"action": "abort", "source": "auto"},
            )
            instr2 = self._make_instr("second_gate")
            hooks.on_step_start(instr2, {"state": state2})

            events_path = plan_dir / "events.ndjson"
            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").strip().splitlines()]
            override_events = [e for e in events if e.get("kind") == "override_applied"]

            assert len(override_events) == 2
            seqs = [e["seq"] for e in override_events]
            assert seqs == sorted(seqs), "sequence numbers should be monotonically increasing"


# ── step-IO policy resolver tests ──────────────────────────────────────────


class TestStepIOPolicyResolver:
    """Tests for ``MegaplanNativeHooks.step_io_policy_resolver``.

    Proves the resolver delegates to ``resolve_megaplan_step_io_policy``
    with the correct parameters and matches the expectations established
    in ``tests/arnold/pipelines/megaplan/test_step_io_policy_adapter.py``.
    """

    def test_property_returns_callable(self):
        """step_io_policy_resolver is a callable (not None, not a class)."""
        hooks = MegaplanNativeHooks()
        resolver = hooks.step_io_policy_resolver
        assert callable(resolver), "step_io_policy_resolver must be callable"

    def test_resolver_delegates_to_resolve_megaplan_step_io_policy(self):
        """The resolver forwards its keyword arguments to
        resolve_megaplan_step_io_policy and returns a StepIOPolicy."""
        hooks = MegaplanNativeHooks()
        resolver = hooks.step_io_policy_resolver

        from arnold.pipeline.step_io_policy import StepIOPolicy
        from arnold.pipelines.megaplan._pipeline.step_io_policy_adapter import (
            CONTRACT_MODE_ENFORCE as _MEGA_ENFORCE,
        )

        policy = resolver(
            plan_dir=None,
            state_config={"step_io_contract_mode": _MEGA_ENFORCE},
            producer_typed=True,
            consumer_typed=True,
        )

        assert isinstance(policy, StepIOPolicy)
        assert policy.configured_mode == _MEGA_ENFORCE
        assert policy.effective_mode == _MEGA_ENFORCE
        assert policy.producer_typed is True
        assert policy.consumer_typed is True
        assert policy.enforcement_eligible is True

    def test_resolver_requires_consumer_typing_for_enforcement(self):
        """Matching test_step_io_policy_adapter.py expectation: enforcement
        requires consumer_typed=True; otherwise effective_mode downgrades."""
        hooks = MegaplanNativeHooks()
        resolver = hooks.step_io_policy_resolver

        from arnold.pipeline.step_io_policy import StepIOPolicy
        from arnold.pipelines.megaplan._pipeline.step_io_policy_adapter import (
            CONTRACT_MODE_ENFORCE as _MEGA_ENFORCE,
        )

        policy = resolver(
            plan_dir=None,
            state_config={"step_io_contract_mode": _MEGA_ENFORCE},
            producer_typed=True,
            consumer_typed=False,
        )

        assert isinstance(policy, StepIOPolicy)
        assert policy.configured_mode == _MEGA_ENFORCE
        # When consumer isn't typed, effective drops to shadow
        assert policy.effective_mode != _MEGA_ENFORCE
        assert policy.enforcement_eligible is False

    def test_resolver_respects_plan_dir(self, tmp_path):
        """When plan_dir is provided, the resolver reads policy from the
        Megaplan policy file on disk — matching the precedence documented
        in test_step_io_policy_adapter.py."""
        from arnold.pipeline.step_io_policy import StepIOPolicy
        from arnold.pipelines.megaplan._pipeline.step_io_policy_adapter import (
            CONTRACT_MODE_WARN as _MEGA_WARN,
            megaplan_step_io_policy_path,
        )

        plan_dir = tmp_path / "project" / ".megaplan" / "plans" / "demo-plan"
        plan_dir.mkdir(parents=True)
        policy_path = megaplan_step_io_policy_path(plan_dir)
        policy_path.parent.mkdir(parents=True)
        policy_path.write_text(
            json.dumps({"configured_mode": _MEGA_WARN}), encoding="utf-8"
        )

        hooks = MegaplanNativeHooks()
        resolver = hooks.step_io_policy_resolver

        policy = resolver(
            plan_dir=plan_dir,
            producer_typed=True,
            consumer_typed=True,
        )

        assert isinstance(policy, StepIOPolicy)
        assert policy.configured_mode == _MEGA_WARN
        assert policy.effective_mode == _MEGA_WARN

    def test_resolver_falls_back_to_configured_plan_dir(self, tmp_path):
        """When the resolver receives plan_dir=None but _plan_dir is
        configured on the hooks instance, it uses the configured dir."""
        from arnold.pipeline.step_io_policy import StepIOPolicy
        from arnold.pipelines.megaplan._pipeline.step_io_policy_adapter import (
            CONTRACT_MODE_ENFORCE as _MEGA_ENFORCE,
            megaplan_step_io_policy_path,
        )

        plan_dir = tmp_path / "project" / ".megaplan" / "plans" / "fallback-plan"
        plan_dir.mkdir(parents=True)
        policy_path = megaplan_step_io_policy_path(plan_dir)
        policy_path.parent.mkdir(parents=True)
        policy_path.write_text(
            json.dumps({"configured_mode": _MEGA_ENFORCE}), encoding="utf-8"
        )

        hooks = MegaplanNativeHooks(plan_dir=plan_dir)
        resolver = hooks.step_io_policy_resolver

        # Call with plan_dir=None → should fall back to _plan_dir
        policy = resolver(
            plan_dir=None,
            producer_typed=True,
            consumer_typed=True,
        )

        assert isinstance(policy, StepIOPolicy)
        assert policy.configured_mode == _MEGA_ENFORCE

    def test_resolver_ignores_extra_kwargs(self):
        """The resolver is compatible with any future extra kwargs the
        native runtime might pass — extras are silently ignored."""
        hooks = MegaplanNativeHooks()
        resolver = hooks.step_io_policy_resolver

        from arnold.pipeline.step_io_policy import StepIOPolicy

        # Pass unknown kwargs — should not raise
        policy = resolver(
            plan_dir=None,
            state_config={"step_io_contract_mode": "shadow"},
            producer_typed=True,
            consumer_typed=True,
            extra_unknown_kwarg=42,
            another_one="ignored",
        )

        assert isinstance(policy, StepIOPolicy)

    def test_resolver_without_plan_dir_and_no_config_returns_default(self):
        """When no plan_dir, state_config, or env override is available,
        the resolver returns a default StepIOPolicy (mode=shadow)."""
        hooks = MegaplanNativeHooks()
        resolver = hooks.step_io_policy_resolver

        from arnold.pipeline.step_io_policy import StepIOPolicy

        policy = resolver(
            plan_dir=None,
            state_config=None,
            producer_typed=True,
            consumer_typed=True,
        )

        assert isinstance(policy, StepIOPolicy)
        # Default is shadow mode
        assert policy.configured_mode == "shadow" or policy.effective_mode == "shadow"


# ── no-resolver case: generic native behaviour is unchanged ────────────────


class TestNoResolverNativeHandoff:
    """Prove that when no ``step_io_policy_resolver`` is configured,
    the generic native runtime behaviour is unchanged — no Megaplan
    code is invoked, and the base policy resolution path is followed.

    These tests exercise ``_enforce_native_typed_handoff`` directly
    and also run a minimal native pipeline without a resolver to
    confirm end-to-end behaviour.
    """

    # ── unit-level: _enforce_native_typed_handoff no-resolver path ────

    def test_no_resolver_noop_when_no_typed_produces(self):
        """_enforce_native_typed_handoff is a no-op when the phase has
        no typed produces ports — this is true with or without a resolver."""
        from arnold.pipeline.native.runtime import _enforce_native_typed_handoff

        instr = NativeInstruction(pc=0, op="phase", name="no_ports")
        instructions: tuple[NativeInstruction, ...] = (instr,)

        # Should not raise — no typed ports means early return
        _enforce_native_typed_handoff(
            instr=instr,
            handoff_value={"x": 1},
            instructions=instructions,
            artifact_root="/tmp",
            step_io_policy_resolver=None,
        )

    def test_no_resolver_noop_when_no_consumers(self):
        """_enforce_native_typed_handoff returns early when no consumer
        references the producer's port — resolver-free path unchanged."""
        from arnold.pipeline.native.runtime import _enforce_native_typed_handoff

        # A producer with a typed port but no consumer referencing it
        instr = NativeInstruction(
            pc=0, op="phase", name="lonely_producer",
            produces=(mock.MagicMock(),),
        )
        instr.produces[0].name = "lonely_port"

        # Consumer phase with no matching consumes
        consumer = NativeInstruction(
            pc=1, op="phase", name="unrelated_consumer",
            consumes=(),
        )
        instructions: tuple[NativeInstruction, ...] = (instr, consumer)

        # Should not raise — no matching consumers
        _enforce_native_typed_handoff(
            instr=instr,
            handoff_value={"lonely_port": "data"},
            instructions=instructions,
            artifact_root="/tmp",
            step_io_policy_resolver=None,
        )

    def test_no_resolver_calls_evaluate_without_megaplan_code(self):
        """When resolver is None, _enforce_native_typed_handoff calls
        evaluate_step_io_handoff with resolved_policy=None — no Megaplan
        import or resolver invocation occurs."""
        from arnold.pipeline.native.runtime import _enforce_native_typed_handoff

        # Create a producer with typed produces and a matching consumer
        producer_port = mock.MagicMock()
        producer_port.name = "typed_port"
        consumer_port = mock.MagicMock()
        # consumer_port needs both port_name (for matching) and name
        consumer_port.port_name = "typed_port"
        consumer_port.name = "typed_port"

        instr = NativeInstruction(
            pc=0, op="phase", name="typed_producer",
            produces=(producer_port,),
        )
        consumer = NativeInstruction(
            pc=1, op="phase", name="typed_consumer",
            consumes=(consumer_port,),
        )
        instructions: tuple[NativeInstruction, ...] = (instr, consumer)

        # Patch evaluate_step_io_handoff to capture the policy arg
        captured_policy = {}

        def _fake_evaluate(handoff_value, *, policy=None, **kwargs):
            captured_policy["policy"] = policy
            # Return a mock with .decision and .policy attributes so
            # effective_blocks_write can inspect it without error.
            result = mock.MagicMock()
            result.decision = mock.MagicMock()
            result.policy = policy
            return result

        with mock.patch(
            # evaluate_step_io_handoff is a lazy import inside
            # _enforce_native_typed_handoff — patch at the source module
            "arnold.pipeline.step_io_handoff.evaluate_step_io_handoff",
            side_effect=_fake_evaluate,
        ), mock.patch(
            "arnold.pipeline.step_io_policy.effective_blocks_write",
            return_value=False,
        ):
            _enforce_native_typed_handoff(
                instr=instr,
                handoff_value={"typed_port": "value"},
                instructions=instructions,
                artifact_root="/tmp",
                step_io_policy_resolver=None,
            )

        # The policy forwarded to evaluate_step_io_handoff is None
        # (no resolver → no resolved_policy → base path)
        assert captured_policy.get("policy") is None, (
            "Without a resolver, resolved_policy must be None "
            "(base resolve_step_io_policy path)"
        )

    # ── integration: run_native_pipeline without resolver ──────────────

    def test_pipeline_runs_without_resolver(self):
        """A minimal native pipeline with typed phases runs successfully
        without a step_io_policy_resolver — generic behaviour is unchanged."""
        from arnold.pipeline.native import (
            compile_pipeline,
            phase,
            pipeline,
            run_native_pipeline,
        )
        from arnold.pipeline.native.context import require_native_runtime

        # Ensure native runtime is active
        with mock.patch.dict(os.environ, {"ARNOLD_NATIVE_RUNTIME": "1"}):
            @phase
            def step1(ctx: dict) -> dict:
                return {"key1": "val1"}

            @phase
            def step2(ctx: dict) -> dict:
                return {"key2": "val2"}

            @pipeline
            def my_pipe(ctx: dict) -> dict:
                state = yield step1(ctx)
                state = yield step2(ctx)
                return state

            prog = compile_pipeline(my_pipe)
            result = run_native_pipeline(
                prog,
                step_io_policy_resolver=None,  # explicitly no resolver
            )

            assert result.state == {"key1": "val1", "key2": "val2"}
            assert len(result.stages) == 2
            assert not result.suspended

    def test_pipeline_with_typed_ports_runs_without_resolver(self):
        """A native pipeline with typed produces/consumes ports runs
        without a resolver — no Megaplan code is triggered."""
        from arnold.pipeline.native import (
            compile_pipeline,
            phase,
            pipeline,
            run_native_pipeline,
        )
        from arnold.pipeline.types import Port, PortRef

        data_port = Port(name="data", content_type="text/plain")
        data_ref = PortRef(port_name="data", content_type="text/plain")

        with mock.patch.dict(os.environ, {"ARNOLD_NATIVE_RUNTIME": "1"}):
            @phase(name="typed_producer", produces=(data_port,))
            def typed_producer(ctx: dict) -> dict:
                return {"data": "hello"}

            @phase(name="typed_consumer", consumes=(data_ref,))
            def typed_consumer(ctx: dict) -> dict:
                return {"consumed": ctx.get("inputs", {}).get("data", "missing")}

            @pipeline
            def typed_pipe(ctx: dict) -> dict:
                state = yield typed_producer(ctx)
                state = yield typed_consumer(ctx)
                return state

            prog = compile_pipeline(typed_pipe)

            # Run WITHOUT resolver — this exercises the no-resolver path
            # in _enforce_native_typed_handoff
            result = run_native_pipeline(
                prog,
                step_io_policy_resolver=None,
            )

            assert "data" in result.state
            assert "consumed" in result.state
            assert len(result.stages) == 2

    def test_no_resolver_with_null_hooks_is_unchanged(self):
        """Using NullNativeRuntimeHooks (which has no step_io_policy_resolver)
        produces identical behaviour to hooks=None — generic path unchanged."""
        from arnold.pipeline.native import (
            NativeProgram,
            NativeInstruction,
            run_native_pipeline,
        )
        from arnold.pipeline.native.hooks import NullNativeRuntimeHooks

        with mock.patch.dict(os.environ, {"ARNOLD_NATIVE_RUNTIME": "1"}):
            instr = NativeInstruction(pc=0, op="halt", name="end")
            prog = NativeProgram(
                name="null_hooks_test",
                instructions=(instr,),
            )

            # Run with NullNativeRuntimeHooks (no resolver)
            result = run_native_pipeline(
                prog,
                hooks=NullNativeRuntimeHooks(),
                step_io_policy_resolver=None,
            )

            assert result.pc == 0
            assert len(result.stages) == 0
            assert not result.suspended
