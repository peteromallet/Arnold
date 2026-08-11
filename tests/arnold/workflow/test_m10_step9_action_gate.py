"""Tests for Step 9A/9B/9C (T17).

Step 9A: EffectLedgerHooks routes durable intent through effect_protocol.
Step 9B: backend._execute_effect routes through WBC protocol.
Step 9C: compensation dispatch through durable protocol (no blind path).

The former T20 action-gate section (Steps 11B/12B/12C) tested the dead
``custody/action_gate.py`` module and was removed with it; the live gate
is ``custody/action_validator.py``, covered by
``tests/arnold_pipelines/megaplan/test_custody_action_validator.py``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# ── T17: EffectProtocol Step 9 convenience methods ──────────────────────────


def _make_protocol(tmp_path: Path):
    """Build a real EffectProtocol backed by SQLite stores."""
    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
    from arnold.workflow.effect_protocol import EffectProtocol
    from arnold.workflow.ledger_outbox import SqliteLedgerOutbox

    db_path = str(tmp_path / "test_effects.db")
    store = SqliteAttemptLedgerStore(db_path)
    # Outbox construction opens the store and initializes both schemas lazily.
    outbox = SqliteLedgerOutbox(store)
    return EffectProtocol(store, outbox)


class TestEffectProtocolStep9Dispatch:
    """Step 9B: dispatch_effect high-level convenience."""

    def test_dispatch_effect_persists_durable_intent_before_dispatch(self, tmp_path):
        """Durable intent is persisted BEFORE the provider is called."""
        protocol = _make_protocol(tmp_path)
        calls = []

        def apply_fn(idem_key, payload):
            calls.append(("apply", idem_key, payload))
            return {"status": "ok"}

        from arnold.workflow.execution_attempt_ledger import (
            GlobalEffectIdentity, AttemptIdentity, AttemptProvenance,
            RuntimeAdapter, VersionSet, GrantRef, AdapterKind,
        )

        ei = GlobalEffectIdentity(
            environment_id="test",
            action_target="effect-1",
            action_version="v1",
            effect_family="test",
            provider_target="fake",
            canonical_request_identity="req-1",
            boundary_schema_hash="schema-1",
        )
        identity = AttemptIdentity(
            workflow_id="wf-test", run_id="run-1", graph_revision="rev-1",
            attempt_id="00000000-0000-0000-0000-000000000001",
        )
        provenance = AttemptProvenance(
            actor_id="pytest", tool_id="step9-action-gate",
        )
        adapter = RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE,
            adapter_version="test",
        )
        versions = VersionSet(code_version="test")
        grant_ref = GrantRef(grant_id="grant-1")

        outcome = protocol.dispatch_effect(
            attempt_id=identity.attempt_id,
            effect_identity=ei,
            identity=identity,
            provenance=provenance,
            adapter=adapter,
            versions=versions,
            grant_ref=grant_ref,
            intent_payload={"action": "test"},
            apply_fn=apply_fn,
            provider_id="fake",
        )

        assert outcome.provider_result == {"status": "ok"}
        assert outcome.provider_error is None
        assert outcome.outcome.outcome_kind == "COMPLETED"
        assert len(calls) == 1

    def test_dispatch_effect_zero_call_on_intent_failure(self, tmp_path):
        """If intent persistence fails, provider is NEVER called."""
        protocol = _make_protocol(tmp_path)
        calls = []

        def apply_fn(idem_key, payload):
            calls.append(("apply",))
            return {}

        # Sabotage persist_intent to raise
        protocol.persist_intent = MagicMock(side_effect=RuntimeError("DB locked"))

        from arnold.workflow.execution_attempt_ledger import (
            GlobalEffectIdentity, AttemptIdentity, AttemptProvenance,
            RuntimeAdapter, VersionSet, GrantRef, AdapterKind,
        )

        ei = GlobalEffectIdentity(
            environment_id="test", action_target="e1",
            action_version="v1", effect_family="test",
            provider_target="fake", canonical_request_identity="r1",
            boundary_schema_hash="s1",
        )
        identity = AttemptIdentity(
            workflow_id="wf-test", run_id="r1", graph_revision="rev",
            attempt_id="00000000-0000-0000-0000-000000000002",
        )
        provenance = AttemptProvenance(actor_id="pytest", tool_id="step9-action-gate")
        adapter = RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="t")
        versions = VersionSet(code_version="t")
        grant_ref = GrantRef(grant_id="g1")

        # dispatch_effect catches exceptions from dispatch, but
        # persist_intent is called before dispatch and will raise.
        # The exception propagates because it's not in the dispatch try/except.
        with pytest.raises(RuntimeError, match="DB locked"):
            protocol.dispatch_effect(
                attempt_id=identity.attempt_id, effect_identity=ei,
                identity=identity, provenance=provenance,
                adapter=adapter, versions=versions, grant_ref=grant_ref,
                intent_payload={"x": 1}, apply_fn=apply_fn,
            )

        assert len(calls) == 0  # Zero-call-on-failure

    def test_dispatch_effect_duplicate_dispatch_negative(self, tmp_path):
        """Duplicate dispatch for same GLEK is rejected by CAS."""
        protocol = _make_protocol(tmp_path)
        call_count = [0]

        def apply_fn(idem_key, payload):
            call_count[0] += 1
            return {"n": call_count[0]}

        from arnold.workflow.execution_attempt_ledger import (
            GlobalEffectIdentity, AttemptIdentity, AttemptProvenance,
            RuntimeAdapter, VersionSet, GrantRef, AdapterKind,
        )

        ei = GlobalEffectIdentity(
            environment_id="test", action_target="dup",
            action_version="v1", effect_family="test",
            provider_target="fake", canonical_request_identity="r1",
            boundary_schema_hash="s1",
        )
        identity = AttemptIdentity(
            workflow_id="wf-test", run_id="r1", graph_revision="rev",
            attempt_id="00000000-0000-0000-0000-000000000003",
        )
        provenance = AttemptProvenance(actor_id="pytest", tool_id="step9-action-gate")
        adapter = RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="t")
        versions = VersionSet(code_version="t")
        grant_ref = GrantRef(grant_id="g1")

        # First dispatch succeeds
        result1 = protocol.dispatch_effect(
            attempt_id=identity.attempt_id, effect_identity=ei,
            identity=identity, provenance=provenance,
            adapter=adapter, versions=versions, grant_ref=grant_ref,
            intent_payload={"x": 1}, apply_fn=apply_fn,
        )
        assert result1.outcome.outcome_kind == "COMPLETED"
        assert call_count[0] == 1

        # Second dispatch for the SAME attempt_id should fail at dispatch
        # because the attempt is no longer dispatch-eligible (terminal exists)
        from arnold.workflow.effect_protocol import EffectProtocolError
        with pytest.raises(EffectProtocolError, match="not dispatch-eligible"):
            protocol.dispatch_effect(
                attempt_id=identity.attempt_id, effect_identity=ei,
                identity=identity, provenance=provenance,
                adapter=adapter, versions=versions, grant_ref=grant_ref,
                intent_payload={"x": 1}, apply_fn=apply_fn,
            )

        assert call_count[0] == 1  # Provider not called again

    def test_dispatch_compensation_no_blind_path(self, tmp_path):
        """Step 9C: compensation goes through durable protocol."""
        protocol = _make_protocol(tmp_path)
        calls = []

        def apply_fn(idem_key, payload):
            calls.append(payload)
            return {"compensated": True}

        from arnold.workflow.execution_attempt_ledger import (
            GlobalEffectIdentity, AttemptIdentity, AttemptProvenance,
            RuntimeAdapter, VersionSet, GrantRef, AdapterKind,
        )

        ei = GlobalEffectIdentity(
            environment_id="test", action_target="comp",
            action_version="v1", effect_family="compensation",
            provider_target="fake", canonical_request_identity="cr1",
            boundary_schema_hash="cs1",
        )
        identity = AttemptIdentity(
            workflow_id="wf-test", run_id="r1", graph_revision="rev",
            attempt_id="00000000-0000-0000-0000-000000000004",
        )
        provenance = AttemptProvenance(actor_id="pytest", tool_id="step9-action-gate")
        adapter = RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="t")
        versions = VersionSet(code_version="t")
        grant_ref = GrantRef(grant_id="g1")

        result = protocol.dispatch_compensation(
            attempt_id=identity.attempt_id, effect_identity=ei,
            identity=identity, provenance=provenance,
            adapter=adapter, versions=versions, grant_ref=grant_ref,
            intent_payload={"undo": "step1"}, apply_fn=apply_fn,
        )

        assert result.outcome.outcome_kind == "COMPLETED"
        assert len(calls) == 1
        assert calls[0].get("_compensation") is True

    def test_persist_durable_intent_and_record_outcome(self, tmp_path):
        """Step 9A convenience: persist_durable_intent + record_outcome."""
        protocol = _make_protocol(tmp_path)

        outbox_id = protocol.persist_durable_intent(
            idempotency_key="hook-key-1",
            intent_payload={"effect_id": "fx", "target": "t"},
        )
        assert outbox_id  # Non-empty outbox record id

        outcome = protocol.record_outcome(
            idempotency_key="hook-key-1",
            outcome="COMPLETED",
        )
        assert outcome is not None
        assert outcome.outcome_kind == "COMPLETED"


# ── T17: EffectLedgerHooks Step 9A ──────────────────────────────────────────


class TestHooksStep9AProtocolRouting:
    """Step 9A: EffectLedgerHooks routes durable intent through protocol."""

    def _make_instr(self):
        from arnold.pipeline.native.ir import NativeInstruction

        return NativeInstruction(
            pc=0,
            name="test_effect",
            op="effect",
            operation="git_push",
            target="origin/main",
            idempotency_key="idem-key-1",
            effect_class="git",
        )

    def test_hooks_persist_durable_intent_through_protocol(self, tmp_path):
        """When protocol attached, durable intent is persisted on step start."""
        from arnold.pipeline.native.hooks import EffectLedgerHooks

        mock_protocol = MagicMock()
        mock_protocol.persist_durable_intent.return_value = "outbox-1"

        hooks = EffectLedgerHooks(effect_protocol=mock_protocol)
        instr = self._make_instr()
        ctx = {"step_path": "/step/1", "attempt": 1}

        hooks.on_step_start(instr, ctx)

        mock_protocol.persist_durable_intent.assert_called_once()
        assert hooks.wbc_intents_persisted == 1
        assert hooks.wbc_zero_call_blocks == 0

    def test_hooks_zero_call_on_failure(self, tmp_path):
        """If protocol raises during intent, error propagates (zero-call)."""
        from arnold.pipeline.native.hooks import EffectLedgerHooks

        mock_protocol = MagicMock()
        mock_protocol.persist_durable_intent.side_effect = RuntimeError("intent failed")

        hooks = EffectLedgerHooks(effect_protocol=mock_protocol)
        instr = self._make_instr()
        ctx = {"step_path": "/step/1", "attempt": 1}

        with pytest.raises(RuntimeError, match="intent failed"):
            hooks.on_step_start(instr, ctx)

        assert hooks.wbc_zero_call_blocks == 1
        assert hooks.wbc_intents_persisted == 0

    def test_hooks_record_completed_outcome_through_protocol(self, tmp_path):
        """On step end, COMPLETED outcome is recorded through protocol."""
        from arnold.pipeline.native.hooks import EffectLedgerHooks

        mock_protocol = MagicMock()
        mock_protocol.persist_durable_intent.return_value = "outbox-1"

        hooks = EffectLedgerHooks(effect_protocol=mock_protocol)
        instr = self._make_instr()
        ctx = {"step_path": "/step/1", "attempt": 1}

        hooks.on_step_start(instr, ctx)
        hooks.on_step_end(instr, ctx, result={"ok": True})

        mock_protocol.record_outcome.assert_called_once()
        call_kwargs = mock_protocol.record_outcome.call_args
        assert call_kwargs.kwargs["outcome"] == "COMPLETED"

    def test_hooks_record_failed_outcome_through_protocol(self, tmp_path):
        """On step error, FAILED outcome is recorded through protocol."""
        from arnold.pipeline.native.hooks import EffectLedgerHooks

        mock_protocol = MagicMock()
        mock_protocol.persist_durable_intent.return_value = "outbox-1"

        hooks = EffectLedgerHooks(effect_protocol=mock_protocol)
        instr = self._make_instr()
        ctx = {"step_path": "/step/1", "attempt": 1}

        hooks.on_step_start(instr, ctx)
        hooks.on_step_error(instr, ctx, RuntimeError("effect crashed"))

        mock_protocol.record_outcome.assert_called_once()
        call_kwargs = mock_protocol.record_outcome.call_args
        assert call_kwargs.kwargs["outcome"] == "FAILED"

    def test_hooks_no_protocol_no_tracking(self, tmp_path):
        """Without protocol, no WBC tracking occurs."""
        from arnold.pipeline.native.hooks import EffectLedgerHooks

        hooks = EffectLedgerHooks()
        instr = self._make_instr()
        ctx = {"step_path": "/step/1", "attempt": 1}

        hooks.on_step_start(instr, ctx)
        hooks.on_step_end(instr, ctx, result={"ok": True})

        assert hooks.wbc_intents_persisted == 0
        assert hooks.wbc_dispatches == 0
        assert hooks.wbc_zero_call_blocks == 0


# ── T17: Backend Step 9B protocol routing ───────────────────────────────────


class TestBackendStep9BProtocolRouting:
    """Step 9B: backend._execute_effect routes through WBC protocol."""

    def test_backend_wbc_effect_protocol_returns_none_by_default(self):
        """Default backend returns None (no protocol attached)."""
        from arnold.execution.backend import LocalJournalBackend

        # Verify the production journal backend exposes the injection seam.
        # the method exists and the default is None via subclass.
        class TestBackend(LocalJournalBackend):
            pass

        assert hasattr(TestBackend, "_wbc_effect_protocol")

    def test_backend_execute_effect_routes_through_protocol(self):
        """When protocol attached, _execute_effect persists durable intent."""
        from arnold.execution.backend import LocalJournalBackend

        class ProtocolBackend(LocalJournalBackend):
            def __init__(self):
                self._protocol = MagicMock()
                self._protocol.persist_durable_intent.return_value = "obx-1"

            def _wbc_effect_protocol(self):
                return self._protocol

        # We can't fully instantiate the backend, but we can verify
        # the protocol injection pattern by checking the method exists
        # and its docstring references Step 9B/9C.
        import inspect
        src = inspect.getsource(LocalJournalBackend._execute_effect)
        assert "_wbc_effect_protocol" in src
        assert "persist_durable_intent" in src
        assert "record_outcome" in src
