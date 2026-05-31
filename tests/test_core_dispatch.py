"""Tests for ``megaplan._core.dispatch`` — tier→spec and tier→agent resolution."""

from __future__ import annotations

import ast
import argparse
import textwrap

import pytest

from megaplan._core.dispatch import resolve_dispatch_spec, resolve_dispatch_agent

# ---------------------------------------------------------------------------
# resolve_dispatch_spec
# ---------------------------------------------------------------------------


class TestResolveDispatchSpec:
    """Tests for ``resolve_dispatch_spec``."""

    def test_ordinal_hit(self):
        """Look up an existing ordinal returns the tier spec."""
        tier_models = {"execute": {2: "claude-sonnet-4-20250514=think"}}
        result = resolve_dispatch_spec(tier_models, "execute", 2)
        assert result == "claude-sonnet-4-20250514=think"

    def test_ordinal_miss_returns_callers_default(self):
        """Missing ordinal returns the caller-supplied default."""
        tier_models = {"execute": {2: "claude-sonnet-4-20250514=think"}}
        result = resolve_dispatch_spec(tier_models, "execute", 99, default="fallback")
        assert result == "fallback"

    def test_ordinal_miss_no_default_returns_none(self):
        """Missing ordinal with no default returns None."""
        tier_models = {"execute": {2: "claude-sonnet-4-20250514=think"}}
        result = resolve_dispatch_spec(tier_models, "execute", 99)
        assert result is None

    def test_missing_slot_returns_default(self):
        """Missing slot key returns the default."""
        tier_models = {"execute": {2: "claude-sonnet-4-20250514=think"}}
        result = resolve_dispatch_spec(tier_models, "nonexistent", 2, default="fb")
        assert result == "fb"

    def test_none_tier_models_returns_default(self):
        """None tier_models returns the default."""
        result = resolve_dispatch_spec(None, "execute", 2, default="fb")
        assert result == "fb"

    def test_non_dict_slot_returns_default(self):
        """A slot value that is not a dict returns the default."""
        tier_models = {"execute": None}
        result = resolve_dispatch_spec(tier_models, "execute", 2, default="fb")
        assert result == "fb"

    def test_malformed_tier_models(self):
        """Malformed tier_models with wrong types still returns default."""
        tier_models: dict = {"execute": "not_a_dict"}
        result = resolve_dispatch_spec(tier_models, "execute", 2, default="fb")
        assert result == "fb"


# ---------------------------------------------------------------------------
# resolve_dispatch_agent
# ---------------------------------------------------------------------------


class TestResolveDispatchAgent:
    """Tests for ``resolve_dispatch_agent``."""

    def test_resolve_dispatch_agent_calls_resolve_agent_mode(self, monkeypatch):
        """``resolve_dispatch_agent`` copies args, sets phase_model, and calls
        ``worker_module.resolve_agent_mode`` with the correct arguments."""

        captured_phase = None
        captured_args = None

        def fake_resolve_agent_mode(phase, args):
            nonlocal captured_phase, captured_args
            captured_phase = phase
            captured_args = args
            return ("test_agent", "test_mode", False, "test_model")

        monkeypatch.setattr(
            "megaplan.workers.resolve_agent_mode",
            fake_resolve_agent_mode,
        )

        args = argparse.Namespace()
        args.phase_model = ["original=value"]
        args.some_other = "keep_me"

        agent, mode, model = resolve_dispatch_agent(args, "my_spec:mode")

        # Return values from the fake
        assert agent == "test_agent"
        assert mode == "test_mode"
        assert model == "test_model"

        # The phase passed to resolve_agent_mode
        assert captured_phase == "execute"

        # The copy should have the tier spec phase_model
        assert captured_args is not None
        assert captured_args.phase_model == ["execute=my_spec:mode"]

        # Original args must NOT be mutated
        assert args.phase_model == ["original=value"]
        assert args.some_other == "keep_me"


# ---------------------------------------------------------------------------
# AST scans — no rubric-shaped tokens
# ---------------------------------------------------------------------------


def test_dispatch_module_no_rubric_tokens():
    """The dispatch module must contain zero rubric-shaped literals:
    no ``1..5`` (as a string), ``tier 4``, ``Opus``, or ``Sonnet``."""
    import megaplan._core.dispatch as mod

    source = textwrap.dedent(open(mod.__file__).read())
    tree = ast.parse(source)

    forbidden = {"Opus", "Sonnet"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Check for rubric-shaped substrings
            lower = node.value.lower()
            if "tier" in lower and any(
                d in lower for d in ("1", "2", "3", "4", "5")
            ):
                # Only flag if it looks like a numeric tier reference
                # ("tier 4", "tier 3", etc.)
                import re

                if re.search(r"tier\s*[1-5]", lower):
                    pytest.fail(
                        f"Rubric token found in dispatch.py string literal: "
                        f"{node.value!r} at line {node.lineno}"
                    )
            for token in forbidden:
                if token.lower() in lower:
                    pytest.fail(
                        f"Forbidden token '{token}' found in dispatch.py "
                        f"string literal: {node.value!r} at line {node.lineno}"
                    )
            # Also check for "1..5" pattern
            if "1..5" in node.value:
                pytest.fail(
                    f"Rubric range '1..5' found in dispatch.py string literal: "
                    f"{node.value!r} at line {node.lineno}"
                )


def test_dispatch_module_no_deleted_handler_symbol():
    """``_resolve_execute_tier_spec`` must NOT be importable from
    ``megaplan.handlers.execute``."""
    with pytest.raises(ImportError):
        from megaplan.handlers.execute import _resolve_execute_tier_spec  # noqa: F401
