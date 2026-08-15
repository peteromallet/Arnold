"""Tests for the normalized maintenance environment namespace helper."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from arnold_pipelines.megaplan.cloud.maintenance_environment import (
    MAINTENANCE_ENVIRONMENT_ENV_VAR,
    MaintenanceEnvironmentError,
    VALID_MAINTENANCE_ENVIRONMENTS,
    is_non_production,
    is_production,
    resolve_maintenance_environment,
)


# ---------------------------------------------------------------------------
# Explicit arguments
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("namespace", ["production", "staging", "test", "fixture"])
def test_explicit_argument_normalizes(namespace: str) -> None:
    with patch.dict("os.environ", {}, clear=True):
        assert resolve_maintenance_environment(namespace) == namespace


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Production", "production"),
        ("  STAGING  ", "staging"),
        ("TEST", "test"),
        ("Fixture", "fixture"),
    ],
)
def test_explicit_argument_strips_and_casefolds(raw: str, expected: str) -> None:
    with patch.dict("os.environ", {}, clear=True):
        assert resolve_maintenance_environment(raw) == expected


# ---------------------------------------------------------------------------
# Env fallback
# ---------------------------------------------------------------------------


def test_env_fallback_used_when_no_explicit_argument() -> None:
    with patch.dict("os.environ", {MAINTENANCE_ENVIRONMENT_ENV_VAR: "staging"}, clear=True):
        assert resolve_maintenance_environment() == "staging"


def test_explicit_argument_beats_env_var() -> None:
    with patch.dict(
        "os.environ",
        {MAINTENANCE_ENVIRONMENT_ENV_VAR: "staging"},
        clear=True,
    ):
        assert resolve_maintenance_environment("fixture") == "fixture"


def test_injected_environ_mapping_is_honored() -> None:
    assert (
        resolve_maintenance_environment(
            environ={MAINTENANCE_ENVIRONMENT_ENV_VAR: "test"}
        )
        == "test"
    )


# ---------------------------------------------------------------------------
# Rejection (fail closed)
# ---------------------------------------------------------------------------


def test_missing_namespace_fails_closed() -> None:
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(MaintenanceEnvironmentError):
            resolve_maintenance_environment()


def test_empty_explicit_argument_fails_closed() -> None:
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(MaintenanceEnvironmentError):
            resolve_maintenance_environment("")


@pytest.mark.parametrize(
    "invalid",
    ["prod", "dev", "qa", "preprod", "fixture:test", "unknown"],
)
def test_invalid_identity_rejected(invalid: str) -> None:
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(MaintenanceEnvironmentError):
            resolve_maintenance_environment(invalid)


def test_invalid_env_identity_rejected() -> None:
    with patch.dict("os.environ", {MAINTENANCE_ENVIRONMENT_ENV_VAR: "prod"}, clear=True):
        with pytest.raises(MaintenanceEnvironmentError):
            resolve_maintenance_environment()


# ---------------------------------------------------------------------------
# Closed vocabulary and predicates
# ---------------------------------------------------------------------------


def test_valid_environments_is_the_closed_set() -> None:
    assert VALID_MAINTENANCE_ENVIRONMENTS == (
        "production",
        "staging",
        "test",
        "fixture",
    )


def test_is_production_predicates() -> None:
    assert is_production("production") is True
    assert is_production("staging") is False
    assert is_non_production("production") is False
    assert is_non_production("test") is True


def test_predicates_fail_closed_on_invalid_identity() -> None:
    with pytest.raises(MaintenanceEnvironmentError):
        is_production("prod")


def test_production_namespace_isolation_across_input_channels() -> None:
    """Non-production identities stay non-production through every input
    channel: neither an explicit argument nor the env var can alias a
    staging/test/fixture store to production."""
    for namespace in ("staging", "test", "fixture"):
        with patch.dict("os.environ", {}, clear=True):
            assert resolve_maintenance_environment(namespace) == namespace
            assert is_production(namespace) is False
            assert is_non_production(namespace) is True
        with patch.dict(
            "os.environ",
            {MAINTENANCE_ENVIRONMENT_ENV_VAR: namespace},
            clear=True,
        ):
            assert resolve_maintenance_environment() == namespace
            assert is_production(None) is False
        # The production identity remains the single canonical namespace,
        # distinguishable from every non-production identity.
        assert resolve_maintenance_environment("production") == "production"
        assert is_production("production") is True


def test_namespaces_resolve_to_pairwise_distinct_identities() -> None:
    """Each accepted namespace is a distinct identity: no two namespaces
    resolve to the same value, so a fixture/test store can never be read or
    written as the production namespace."""
    with patch.dict("os.environ", {}, clear=True):
        resolved = {
            resolve_maintenance_environment(namespace)
            for namespace in VALID_MAINTENANCE_ENVIRONMENTS
        }
        assert resolved == set(VALID_MAINTENANCE_ENVIRONMENTS)
        assert len(resolved) == len(VALID_MAINTENANCE_ENVIRONMENTS)
