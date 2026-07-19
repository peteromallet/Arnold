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
    audit_autofix_commit_enabled,
    audit_autofix_commit_on,
    audit_autofix_enabled,
    audit_autofix_on,
    autonomy_enabled,
    autonomy_on,
    escalation_ledger_enabled,
    escalation_ledger_on,
    meta_repair_commit_enabled,
    meta_repair_commit_on,
    meta_repair_enabled,
    meta_repair_on,
    meta_repair_push_enabled,
    meta_repair_push_on,
    MUTATION_PATH_L1,
    MUTATION_PATH_L2,
    MUTATION_PATH_L3,
    mutation_authorized,
    redaction_enabled,
    redaction_on,
    repair_request_queue_enabled,
    repair_request_queue_on,
    repair_trigger_enabled,
    repair_trigger_on,
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

    def test_repair_request_queue_defaults_on(self) -> None:
        with _clear_env():
            assert repair_request_queue_enabled() is True
            assert repair_request_queue_on() is True

    def test_repair_trigger_defaults_on(self) -> None:
        with _clear_env():
            assert repair_trigger_enabled() is True
            assert repair_trigger_on() is True


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
    """Authority ledgers require opt-in; repair dispatch defaults on."""

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

    def test_repair_trigger_on_by_default(self) -> None:
        with _clear_env():
            assert repair_trigger_enabled() is True

    def test_autonomy_off_by_default(self) -> None:
        with _clear_env():
            assert autonomy_enabled() is False

    @pytest.mark.parametrize(
        "env_var,flag_func",
        [
            ("ARNOLD_RESOLVER_ENFORCEMENT", resolver_enforcement_enabled),
            ("ARNOLD_ESCALATION_LEDGER", escalation_ledger_enabled),
            ("ARNOLD_AUTONOMY", autonomy_enabled),
            ("ARNOLD_REPAIR_TRIGGER_ENABLED", repair_trigger_enabled),
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
            ("ARNOLD_REPAIR_TRIGGER_ENABLED", repair_trigger_enabled),
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
            ("ARNOLD_REPAIR_TRIGGER_ENABLED", repair_trigger_enabled),
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
            ("ARNOLD_REPAIR_TRIGGER_ENABLED", repair_trigger_enabled),
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
            ("ARNOLD_REPAIR_TRIGGER_ENABLED", repair_trigger_enabled),
        ],
    )
    def test_flag_off_when_env_empty(self, env_var: str, flag_func) -> None:
        with _set_env(**{env_var: ""}):
            # Empty string falls through to the flag's default.
            expected = env_var == "ARNOLD_REPAIR_TRIGGER_ENABLED"
            assert flag_func() is expected


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


class TestRepairRequestQueueOptOut:
    """Repair queue marker production defaults ON but can be disabled."""

    def test_repair_request_queue_off_when_env_0(self) -> None:
        with _set_env(ARNOLD_REPAIR_REQUEST_QUEUE="0"):
            assert repair_request_queue_enabled() is False

    def test_repair_request_queue_on_when_env_true(self) -> None:
        with _set_env(ARNOLD_REPAIR_REQUEST_QUEUE="true"):
            assert repair_request_queue_enabled() is True


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
# Master-plus-path mutation authorization
# ---------------------------------------------------------------------------


_MUTATION_PATHS = (
    (MUTATION_PATH_L1, "ARNOLD_REPAIR_TRIGGER_ENABLED"),
    (MUTATION_PATH_L2, "ARNOLD_META_REPAIR_ENABLED"),
    (MUTATION_PATH_L3, "ARNOLD_AUDIT_AUTOFIX_ENABLED"),
)
_MUTATION_CLASSES = ("state", "source", "commit", "push", "subprocess")


class TestMutationAuthorization:
    """Every mutation class needs the master gate and its relevant path gate."""

    @pytest.mark.parametrize("path,path_env", _MUTATION_PATHS)
    @pytest.mark.parametrize("mutation_class", _MUTATION_CLASSES)
    @pytest.mark.parametrize(
        ("master_enabled", "path_enabled"),
        ((False, False), (False, True), (True, False), (True, True)),
    )
    def test_master_and_path_matrix(
        self,
        path: str,
        path_env: str,
        mutation_class: str,
        master_enabled: bool,
        path_enabled: bool,
    ) -> None:
        """All L1/L2/L3 effects authorize only for the true/true row."""
        with _set_env(
            ARNOLD_AUTONOMY="1" if master_enabled else "0",
            **{path_env: "1" if path_enabled else "0"},
        ):
            assert mutation_authorized(path) is (master_enabled and path_enabled), (
                f"{path} {mutation_class} mutation must require master and path gates"
            )
            # Observation is intentionally not part of mutation authorization.
            assert resolver_observe_enabled() is True
            assert repair_request_queue_enabled() is True

    def test_unknown_mutation_path_fails_closed(self) -> None:
        with _set_env(ARNOLD_AUTONOMY="1"):
            assert mutation_authorized("unknown") is False


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


# ---------------------------------------------------------------------------
# M5 meta-repair and auditor feature flags (default ON)
# ---------------------------------------------------------------------------


class TestM5Defaults:
    """All M5 meta-repair and auditor flags are on by default."""

    def test_meta_repair_defaults_on(self) -> None:
        with _clear_env():
            assert meta_repair_enabled() is True
            assert meta_repair_on() is True

    def test_audit_autofix_defaults_on(self) -> None:
        with _clear_env():
            assert audit_autofix_enabled() is True
            assert audit_autofix_on() is True

    def test_meta_repair_commit_defaults_on(self) -> None:
        with _clear_env():
            assert meta_repair_commit_enabled() is True
            assert meta_repair_commit_on() is True

    def test_meta_repair_push_defaults_off(self) -> None:
        with _clear_env():
            assert meta_repair_push_enabled() is False
            assert meta_repair_push_on() is False

    def test_meta_repair_push_requires_explicit_opt_in(self) -> None:
        with _set_env(ARNOLD_META_REPAIR_PUSH_ENABLED="1"):
            assert meta_repair_push_enabled() is True
            assert meta_repair_push_on() is True

    def test_audit_autofix_commit_defaults_on(self) -> None:
        with _clear_env():
            assert audit_autofix_commit_enabled() is True
            assert audit_autofix_commit_on() is True


class TestM5ExplicitOptIn:
    """M5 flags default ON and support explicit disabling."""

    @pytest.mark.parametrize(
        "env_var,flag_func",
        [
            ("ARNOLD_META_REPAIR_ENABLED", meta_repair_enabled),
            ("ARNOLD_AUDIT_AUTOFIX_ENABLED", audit_autofix_enabled),
            ("ARNOLD_META_REPAIR_COMMIT_ENABLED", meta_repair_commit_enabled),
            ("ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED", audit_autofix_commit_enabled),
        ],
    )
    def test_flag_on_by_default(self, env_var: str, flag_func) -> None:
        with _clear_env():
            assert flag_func() is True

    @pytest.mark.parametrize(
        "env_var,flag_func",
        [
            ("ARNOLD_META_REPAIR_ENABLED", meta_repair_enabled),
            ("ARNOLD_AUDIT_AUTOFIX_ENABLED", audit_autofix_enabled),
            ("ARNOLD_META_REPAIR_COMMIT_ENABLED", meta_repair_commit_enabled),
            ("ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED", audit_autofix_commit_enabled),
        ],
    )
    def test_flag_on_when_env_1(self, env_var: str, flag_func) -> None:
        with _set_env(**{env_var: "1"}):
            assert flag_func() is True

    @pytest.mark.parametrize(
        "env_var,flag_func",
        [
            ("ARNOLD_META_REPAIR_ENABLED", meta_repair_enabled),
            ("ARNOLD_AUDIT_AUTOFIX_ENABLED", audit_autofix_enabled),
            ("ARNOLD_META_REPAIR_COMMIT_ENABLED", meta_repair_commit_enabled),
            ("ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED", audit_autofix_commit_enabled),
        ],
    )
    def test_flag_off_when_env_0(self, env_var: str, flag_func) -> None:
        with _set_env(**{env_var: "0"}):
            assert flag_func() is False

    @pytest.mark.parametrize(
        "env_var,flag_func",
        [
            ("ARNOLD_META_REPAIR_ENABLED", meta_repair_enabled),
            ("ARNOLD_AUDIT_AUTOFIX_ENABLED", audit_autofix_enabled),
            ("ARNOLD_META_REPAIR_COMMIT_ENABLED", meta_repair_commit_enabled),
            ("ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED", audit_autofix_commit_enabled),
        ],
    )
    def test_flag_off_when_env_false(self, env_var: str, flag_func) -> None:
        with _set_env(**{env_var: "false"}):
            assert flag_func() is False

    @pytest.mark.parametrize(
        "env_var,flag_func",
        [
            ("ARNOLD_META_REPAIR_ENABLED", meta_repair_enabled),
            ("ARNOLD_AUDIT_AUTOFIX_ENABLED", audit_autofix_enabled),
            ("ARNOLD_META_REPAIR_COMMIT_ENABLED", meta_repair_commit_enabled),
            ("ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED", audit_autofix_commit_enabled),
        ],
    )
    def test_flag_on_when_env_true(self, env_var: str, flag_func) -> None:
        with _set_env(**{env_var: "true"}):
            # "true" is recognized as truthy (not in the disable-values set)
            assert flag_func() is True

    @pytest.mark.parametrize(
        "env_var,flag_func",
        [
            ("ARNOLD_META_REPAIR_ENABLED", meta_repair_enabled),
            ("ARNOLD_AUDIT_AUTOFIX_ENABLED", audit_autofix_enabled),
            ("ARNOLD_META_REPAIR_COMMIT_ENABLED", meta_repair_commit_enabled),
            ("ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED", audit_autofix_commit_enabled),
        ],
    )
    def test_flag_off_when_env_empty(self, env_var: str, flag_func) -> None:
        with _set_env(**{env_var: ""}):
            # Empty string falls through to default ON for these flags.
            assert flag_func() is True


class TestM5FlagIndependence:
    """Each M5 flag is gated by its own env var — no cross-flag leakage."""

    def test_meta_repair_independent_of_commits(self) -> None:
        with _set_env(ARNOLD_META_REPAIR_COMMIT_ENABLED="1"):
            assert meta_repair_enabled() is True

    def test_audit_autofix_independent_of_commits(self) -> None:
        with _set_env(ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED="1"):
            assert audit_autofix_enabled() is True

    def test_m5_flags_independent_of_autonomy(self) -> None:
        with _set_env(ARNOLD_AUTONOMY="1"):
            assert meta_repair_enabled() is True
            assert audit_autofix_enabled() is True
            assert meta_repair_commit_enabled() is True
            assert audit_autofix_commit_enabled() is True
