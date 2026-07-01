"""Tests for centralized cloud repair feature flags.

Covers:
- Default-safe M1 behavior: resolver-observe ON, enforcement OFF,
  escalation-ledger OFF, autonomy OFF, redaction ON.
- Explicit opt-out for redaction.
- Explicit opt-in for ledger, enforcement, autonomy.
- Flag independence (each flag gated by its own env var).
- Integration: flags are correctly wired into their consuming modules.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold_pipelines.megaplan.cloud.feature_flags import (
    autonomy_enabled,
    autonomy_on,
    escalation_ledger_enabled,
    escalation_ledger_on,
    redaction_enabled,
    redaction_on,
    resolver_enforcement_enabled,
    resolver_enforcement_on,
    resolver_observe_enabled,
    resolver_observe_on,
)
from arnold_pipelines.megaplan.cloud.human_blockers import EscalationLedgerWriter
from arnold_pipelines.megaplan.cloud.current_target import resolve_current_target
from arnold_pipelines.megaplan.cloud.redact import (
    REDACTION,
    redact_text as _redact_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_env() -> dict:
    return patch.dict(os.environ, {}, clear=True)


def _set_env(**kwargs: str) -> dict:
    return patch.dict(os.environ, kwargs, clear=True)


# ---------------------------------------------------------------------------
# M1 default-safety: every behaviour-changing flag is OFF
# ---------------------------------------------------------------------------


class TestM1Defaults:
    """In M1 all behavior-changing paths are disabled by default."""

    def test_resolver_observe_defaults_on(self) -> None:
        with _clear_env():
            assert resolver_observe_enabled() is True
            assert resolver_observe_on() is True

    def test_resolver_enforcement_defaults_off(self) -> None:
        with _clear_env():
            assert resolver_enforcement_enabled() is False
            assert resolver_enforcement_on() is False

    def test_escalation_ledger_defaults_off(self) -> None:
        with _clear_env():
            assert escalation_ledger_enabled() is False
            assert escalation_ledger_on() is False

    def test_autonomy_defaults_off(self) -> None:
        with _clear_env():
            assert autonomy_enabled() is False
            assert autonomy_on() is False

    def test_redaction_defaults_on(self) -> None:
        with _clear_env():
            assert redaction_enabled() is True
            assert redaction_on() is True


# ---------------------------------------------------------------------------
# Explicit opt-out for redaction
# ---------------------------------------------------------------------------


class TestRedactionOptOut:
    """Redaction is default-on but supports explicit opt-out via env var."""

    def test_redaction_off_when_env_0(self) -> None:
        with _set_env(ARNOLD_REDACTION_ENABLED="0"):
            assert redaction_enabled() is False

    def test_redaction_off_when_env_false(self) -> None:
        with _set_env(ARNOLD_REDACTION_ENABLED="false"):
            assert redaction_enabled() is False

    def test_redaction_off_when_env_no(self) -> None:
        with _set_env(ARNOLD_REDACTION_ENABLED="no"):
            assert redaction_enabled() is False

    def test_redaction_off_when_env_off(self) -> None:
        with _set_env(ARNOLD_REDACTION_ENABLED="off"):
            assert redaction_enabled() is False

    def test_redaction_actually_skips_when_disabled(self) -> None:
        text = "Authorization: Bearer secret-token-abc123"
        with _set_env(ARNOLD_REDACTION_ENABLED="0"):
            assert _redact_text(text) == text

    def test_redaction_default_on_redacts(self) -> None:
        text = "Authorization: Bearer secret-token-abc123"
        with _clear_env():
            result = _redact_text(text)
            assert "secret-token-abc123" not in result
            assert REDACTION in result


# ---------------------------------------------------------------------------
# Explicit opt-in for behavior-changing flags
# ---------------------------------------------------------------------------


class TestExplicitOptIn:
    """Behaviour-changing flags default OFF and require explicit '1' to enable."""

    @pytest.mark.parametrize(
        "env_var,flag_func",
        [
            ("ARNOLD_RESOLVER_ENFORCEMENT", resolver_enforcement_enabled),
            ("ARNOLD_ESCALATION_LEDGER", escalation_ledger_enabled),
            ("ARNOLD_AUTONOMY", autonomy_enabled),
        ],
    )
    def test_flag_off_by_default(self, env_var: str, flag_func) -> None:
        with _clear_env():
            assert flag_func() is False

    @pytest.mark.parametrize(
        "env_var,flag_func",
        [
            ("ARNOLD_RESOLVER_ENFORCEMENT", resolver_enforcement_enabled),
            ("ARNOLD_ESCALATION_LEDGER", escalation_ledger_enabled),
            ("ARNOLD_AUTONOMY", autonomy_enabled),
        ],
    )
    def test_flag_on_when_env_1(self, env_var: str, flag_func) -> None:
        with _set_env(**{env_var: "1"}):
            assert flag_func() is True

    @pytest.mark.parametrize(
        "env_var,flag_func",
        [
            ("ARNOLD_RESOLVER_ENFORCEMENT", resolver_enforcement_enabled),
            ("ARNOLD_ESCALATION_LEDGER", escalation_ledger_enabled),
            ("ARNOLD_AUTONOMY", autonomy_enabled),
        ],
    )
    def test_flag_off_when_env_0(self, env_var: str, flag_func) -> None:
        with _set_env(**{env_var: "0"}):
            assert flag_func() is False

    @pytest.mark.parametrize(
        "env_var,flag_func",
        [
            ("ARNOLD_RESOLVER_ENFORCEMENT", resolver_enforcement_enabled),
            ("ARNOLD_ESCALATION_LEDGER", escalation_ledger_enabled),
            ("ARNOLD_AUTONOMY", autonomy_enabled),
        ],
    )
    def test_flag_off_when_env_false(self, env_var: str, flag_func) -> None:
        with _set_env(**{env_var: "false"}):
            assert flag_func() is False

    @pytest.mark.parametrize(
        "env_var,flag_func",
        [
            ("ARNOLD_RESOLVER_ENFORCEMENT", resolver_enforcement_enabled),
            ("ARNOLD_ESCALATION_LEDGER", escalation_ledger_enabled),
            ("ARNOLD_AUTONOMY", autonomy_enabled),
        ],
    )
    def test_flag_on_when_env_true(self, env_var: str, flag_func) -> None:
        with _set_env(**{env_var: "true"}):
            # "true" is recognized as truthy (not in the disable-values set)
            assert flag_func() is True

    @pytest.mark.parametrize(
        "env_var,flag_func",
        [
            ("ARNOLD_RESOLVER_ENFORCEMENT", resolver_enforcement_enabled),
            ("ARNOLD_ESCALATION_LEDGER", escalation_ledger_enabled),
            ("ARNOLD_AUTONOMY", autonomy_enabled),
        ],
    )
    def test_flag_off_when_env_empty(self, env_var: str, flag_func) -> None:
        with _set_env(**{env_var: ""}):
            # Empty string → falls through to default (False for these flags)
            assert flag_func() is False


# ---------------------------------------------------------------------------
# Resolver-observe explicit opt-out
# ---------------------------------------------------------------------------


class TestResolverObserveOptOut:
    """Resolver observe defaults ON but supports explicit opt-out."""

    def test_resolver_observe_off_when_env_0(self) -> None:
        with _set_env(ARNOLD_RESOLVER_OBSERVE="0"):
            assert resolver_observe_enabled() is False

    def test_resolver_observe_off_when_env_false(self) -> None:
        with _set_env(ARNOLD_RESOLVER_OBSERVE="false"):
            assert resolver_observe_enabled() is False

    def test_resolver_observe_still_on_when_env_1(self) -> None:
        with _set_env(ARNOLD_RESOLVER_OBSERVE="1"):
            assert resolver_observe_enabled() is True

    def test_resolver_observe_on_by_default(self) -> None:
        with _clear_env():
            assert resolver_observe_enabled() is True


# ---------------------------------------------------------------------------
# Flag independence
# ---------------------------------------------------------------------------


class TestFlagIndependence:
    """Each flag is gated by its own env var — no cross-flag inheritance."""

    def test_resolver_enforcement_independent_of_observe(self) -> None:
        with _set_env(ARNOLD_RESOLVER_OBSERVE="1"):
            assert resolver_enforcement_enabled() is False

    def test_escalation_ledger_independent_of_autonomy(self) -> None:
        with _set_env(ARNOLD_AUTONOMY="1"):
            assert escalation_ledger_enabled() is False

    def test_autonomy_independent_of_enforcement(self) -> None:
        with _set_env(ARNOLD_RESOLVER_ENFORCEMENT="1"):
            assert autonomy_enabled() is False

    def test_redaction_independent_of_other_flags(self) -> None:
        with _set_env(
            ARNOLD_RESOLVER_ENFORCEMENT="1",
            ARNOLD_ESCALATION_LEDGER="1",
            ARNOLD_AUTONOMY="1",
        ):
            # Redaction defaults to ON even when all other flags are explicitly ON
            assert redaction_enabled() is True


# ---------------------------------------------------------------------------
# Integration: EscalationLedgerWriter respects the centralized flag
# ---------------------------------------------------------------------------


class TestLedgerWriterIntegration:
    """EscalationLedgerWriter respects ARNOLD_ESCALATION_LEDGER flag."""

    def test_ledger_writer_disabled_by_default(self) -> None:
        with _clear_env():
            writer = EscalationLedgerWriter()
            assert writer.enabled is False

    def test_ledger_writer_enabled_when_flag_on(self) -> None:
        with _set_env(ARNOLD_ESCALATION_LEDGER="1"):
            writer = EscalationLedgerWriter()
            assert writer.enabled is True

    def test_ledger_writer_still_disabled_when_flag_off(self) -> None:
        with _set_env(ARNOLD_ESCALATION_LEDGER="0"):
            writer = EscalationLedgerWriter()
            assert writer.enabled is False

    def test_ledger_writer_explicit_override(self) -> None:
        """Explicit _enabled kwarg overrides the env-var default."""
        with _set_env(ARNOLD_ESCALATION_LEDGER="1"):
            writer = EscalationLedgerWriter(_enabled=False)
            assert writer.enabled is False

    def test_ledger_writer_explicit_enable_still_works(self, tmp_path: Path) -> None:
        """Explicit enable() works regardless of default state."""
        with _clear_env():
            writer = EscalationLedgerWriter()
            assert writer.enabled is False
            writer.enable(tmp_path / "sidecars")
            assert writer.enabled is True


# ---------------------------------------------------------------------------
# Integration: resolve_current_target returns stub when observe is disabled
# ---------------------------------------------------------------------------


class TestResolverObserveIntegration:
    """resolve_current_target returns a minimal stub when observe is disabled."""

    def test_resolve_returns_stub_when_observe_disabled(self) -> None:
        with _set_env(ARNOLD_RESOLVER_OBSERVE="0"):
            result = resolve_current_target(
                "test-session",
                marker_dir="/nonexistent/markers",
            )
            assert result["schema_version"] == 1
            assert result["session"] == "test-session"
            assert result["authoritative_source"] == "resolver_observe_disabled"
            assert "resolver observe disabled" in result["rationale"][0]
            # Stub contains empty structures, not filesystem-derived data
            assert result["current_refs"] == {}
            assert result["stale_evidence"] == []
            assert result["sibling_sessions"] == []

    def test_resolve_runs_normally_when_observe_enabled(
        self, tmp_path: Path
    ) -> None:
        """When observe is enabled (default), the resolver inspects filesystem."""
        marker_dir = tmp_path / "markers"
        marker_dir.mkdir()
        marker_path = marker_dir / "test-session.json"
        marker_path.write_text('{"session":"test-session","workspace":"/tmp/ws","run_kind":"plan"}')

        workspace = tmp_path / "ws"
        workspace.mkdir()

        with _set_env(ARNOLD_RESOLVER_OBSERVE="1"):
            result = resolve_current_target(
                "test-session",
                marker_dir=str(marker_dir),
            )
            # Should not return the observe-disabled stub
            assert result["authoritative_source"] != "resolver_observe_disabled"
            # Should contain filesystem-derived data
            assert result["marker"]["present"] is True
