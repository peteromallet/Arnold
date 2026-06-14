"""Tests for ``arnold.agent.dispatcher.ArnoldDispatcher``.

Covers:
* register / dispatch happy path
* unknown agent raises LookupError
* ``isinstance(ArnoldDispatcher(), AgentDispatcher)`` is True
* ``sys.modules`` snapshot before ``import arnold.agent.dispatcher`` shows
  no ``arnold.pipelines.megaplan*`` module loaded as a side-effect
"""

from __future__ import annotations

import sys

import pytest

from arnold.agent.contracts import AgentDispatcher, AgentRequest, AgentResult
from arnold.agent.dispatcher import ArnoldDispatcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_adapter(request: AgentRequest) -> AgentResult:
    """Trivial adapter that returns a canned AgentResult."""
    return AgentResult(
        payload={"echo": request.prompt},
        raw_output=request.prompt or "",
        duration_ms=42,
        cost_usd=0.0,
        model_actual=request.resolved_model or request.model,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestRegisterDispatch:
    def test_register_and_dispatch_returns_agent_result(self):
        """Happy path: register an adapter and dispatch a request through it."""
        dispatcher = ArnoldDispatcher()
        dispatcher.register("hermes", _fake_adapter)

        request = AgentRequest(
            agent="hermes",
            mode="default",
            prompt="hello",
        )
        result = dispatcher.dispatch(request)

        assert isinstance(result, AgentResult)
        assert result.payload == {"echo": "hello"}
        assert result.raw_output == "hello"
        assert result.duration_ms == 42

    def test_multiple_agents_routed_independently(self):
        """Each agent key routes to its own adapter."""
        dispatcher = ArnoldDispatcher()

        def adapter_hermes(req: AgentRequest) -> AgentResult:
            return AgentResult(
                payload={"backend": "hermes"},
                raw_output="h",
                duration_ms=1,
                cost_usd=0.0,
            )

        def adapter_codex(req: AgentRequest) -> AgentResult:
            return AgentResult(
                payload={"backend": "codex"},
                raw_output="c",
                duration_ms=1,
                cost_usd=0.0,
            )

        dispatcher.register("hermes", adapter_hermes)
        dispatcher.register("codex", adapter_codex)

        hr = dispatcher.dispatch(
            AgentRequest(agent="hermes", mode="default", prompt="h")
        )
        cr = dispatcher.dispatch(
            AgentRequest(agent="codex", mode="default", prompt="c")
        )

        assert hr.payload == {"backend": "hermes"}
        assert cr.payload == {"backend": "codex"}

    def test_register_overwrites_previous(self):
        """Registering twice for the same agent key overwrites the adapter."""
        dispatcher = ArnoldDispatcher()

        dispatcher.register("x", _fake_adapter)

        def replacement(req: AgentRequest) -> AgentResult:
            return AgentResult(
                payload={"replaced": True},
                raw_output="r",
                duration_ms=99,
                cost_usd=0.0,
            )

        dispatcher.register("x", replacement)

        result = dispatcher.dispatch(
            AgentRequest(agent="x", mode="default", prompt="ignored")
        )

        assert result.payload == {"replaced": True}
        assert result.duration_ms == 99


# ---------------------------------------------------------------------------
# Unknown agent
# ---------------------------------------------------------------------------


class TestUnknownAgent:
    def test_dispatch_unknown_agent_raises_lookuperror(self):
        """Dispatch with an unregistered agent raises LookupError."""
        dispatcher = ArnoldDispatcher()

        with pytest.raises(LookupError, match="no adapter registered for agent="):
            dispatcher.dispatch(
                AgentRequest(agent="nonexistent", mode="default", prompt="boom")
            )

    def test_lookuperror_message_contains_agent_name(self):
        """The error message includes the offending agent name."""
        dispatcher = ArnoldDispatcher()

        with pytest.raises(LookupError) as exc_info:
            dispatcher.dispatch(
                AgentRequest(agent="gremlin", mode="default", prompt="x")
            )

        assert "gremlin" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_arnold_dispatcher_satisfies_agent_dispatcher_protocol(self):
        """ArnoldDispatcher instances pass isinstance against AgentDispatcher."""
        d = ArnoldDispatcher()
        assert isinstance(d, AgentDispatcher), (
            "ArnoldDispatcher must satisfy the AgentDispatcher Protocol"
        )

    def test_empty_dispatcher_satisfies_protocol(self):
        """Even without registrations, a fresh dispatcher is an AgentDispatcher."""
        assert isinstance(ArnoldDispatcher(), AgentDispatcher)


# ---------------------------------------------------------------------------
# Zero-leak: no megaplan modules loaded as side-effect of import
# ---------------------------------------------------------------------------


class TestZeroLeakSysModules:
    """Verify that importing ``arnold.agent.dispatcher`` does not load any
    ``arnold.pipelines.megaplan*`` module into ``sys.modules`` as a side-effect.
    """

    def test_import_dispatcher_does_not_load_megaplan_modules(self):
        # Take a snapshot *before* the import under test.
        # The test file itself already imports ArnoldDispatcher at the top,
        # so we snapshot the modules that *were already loaded* and then
        # verify no NEW megaplan module appeared since.
        megaplan_prefix = "arnold.pipelines.megaplan"

        # Collect all currently-loaded megaplan modules (there may be some
        # from test infrastructure / other imports).
        pre = {k for k in sys.modules if k.startswith(megaplan_prefix)}

        # Force-reimport to exercise the module's import machinery again.
        # Actually, the module is already imported at the top of this file.
        # We verify that no *additional* megaplan module was loaded since
        # the top-level import by checking against the full set now.
        # But since we took the snapshot AFTER the import, the stronger
        # check is: were any megaplan modules loaded at all that were NOT
        # already loaded before *any* arnold.agent.dispatcher import?
        #
        # We do this by importing the module again under a fresh key:
        import importlib

        # Save the original module
        orig = sys.modules.get("arnold.agent.dispatcher")

        # Clear it so we can watch the fresh import
        sys.modules.pop("arnold.agent.dispatcher", None)
        # Also clear the sub-modules that dispatcher pulls in
        for mod_key in list(sys.modules):
            if mod_key.startswith("arnold.agent.adapters"):
                sys.modules.pop(mod_key, None)

        pre_fresh = {k for k in sys.modules if k.startswith(megaplan_prefix)}

        # Now do a fresh import
        import arnold.agent.dispatcher  # noqa: F811

        post = {k for k in sys.modules if k.startswith(megaplan_prefix)}

        # Restore the original module
        if orig is not None:
            sys.modules["arnold.agent.dispatcher"] = orig

        new_megaplan = post - pre_fresh
        assert not new_megaplan, (
            f"Importing arnold.agent.dispatcher loaded megaplan modules: {new_megaplan}"
        )

    def test_zero_leak_gate_on_imports(self):
        """Standalone check: no import of arnold.pipelines.megaplan in dispatcher or adapters."""
        import ast
        import inspect
        from pathlib import Path

        import arnold.agent.adapters
        import arnold.agent.dispatcher

        megaplan_ref = "arnold.pipelines.megaplan"

        files_to_check = [
            Path(inspect.getfile(arnold.agent.dispatcher)),
            Path(inspect.getfile(arnold.agent.adapters)),
            Path(inspect.getfile(arnold.agent.adapters)).parent / "deepseek.py",
            Path(inspect.getfile(arnold.agent.adapters)).parent / "_pricing.py",
        ]

        for path in files_to_check:
            if not path.exists():
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    # For ImportFrom, the module is node.module
                    if isinstance(node, ast.ImportFrom):
                        if node.module and megaplan_ref in node.module:
                            raise AssertionError(
                                f"{path} imports {node.module}"
                            )
                    # For Import, check each alias
                    else:
                        for alias in node.names:
                            if megaplan_ref in alias.name:
                                raise AssertionError(
                                    f"{path} imports {alias.name}"
                                )
