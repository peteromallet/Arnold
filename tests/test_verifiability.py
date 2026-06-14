"""Tests for megaplan.audits.capabilities and megaplan.audits.verifiability modules."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.audits.capabilities import (
    ALL_CAPABILITIES,
    CONTAINER_CAPABILITIES,
    DEFAULT_CONTAINER_CAPABILITIES,
    DEFAULT_HUMAN_CAPABILITIES,
    HUMAN_CAPABILITIES,
    get_worker_capabilities,
    union_verifies,
    validate_capabilities,
)
from arnold.pipelines.megaplan.orchestration.verifiability import (
    CriterionAudit,
    audit_criteria,
    classify_criteria,
    validate_requires,
)
from arnold.pipelines.megaplan.handlers.verifiability import get_human_verification_status


# ---------------------------------------------------------------------------
# Capability registry tests
# ---------------------------------------------------------------------------


def test_validate_capabilities_known_accepted() -> None:
    assert validate_capabilities(["run_tests"]) == []
    assert validate_capabilities(["run_tests", "read_files", "drive_browser"]) == []
    assert validate_capabilities(list(ALL_CAPABILITIES)) == []


def test_validate_capabilities_unknown_rejected() -> None:
    result = validate_capabilities(["made_up_cap"])
    assert result == ["made_up_cap"]


def test_validate_capabilities_mixed() -> None:
    result = validate_capabilities(["run_tests", "teleport", "read_files", "quantum_compute"])
    assert set(result) == {"teleport", "quantum_compute"}


def test_registry_sets_no_overlap() -> None:
    assert CONTAINER_CAPABILITIES & HUMAN_CAPABILITIES == frozenset()
    assert ALL_CAPABILITIES == CONTAINER_CAPABILITIES | HUMAN_CAPABILITIES
    assert len(ALL_CAPABILITIES) == 11


def test_defaults_match_full_sets() -> None:
    assert DEFAULT_CONTAINER_CAPABILITIES == CONTAINER_CAPABILITIES
    assert DEFAULT_HUMAN_CAPABILITIES == HUMAN_CAPABILITIES


# ---------------------------------------------------------------------------
# audit_criteria tests
# ---------------------------------------------------------------------------


def _container_only_caps() -> dict[str, set[str]]:
    return {"codex": set(CONTAINER_CAPABILITIES)}


def _container_plus_human_caps() -> dict[str, set[str]]:
    return {
        "codex": set(CONTAINER_CAPABILITIES),
        "human": set(HUMAN_CAPABILITIES),
    }


def _empty_worker_caps() -> dict[str, set[str]]:
    return {"codex": set()}


def test_audit_requires_run_tests_container_is_machine_verifiable() -> None:
    criteria = [{"criterion": "All tests pass", "priority": "must", "requires": ["run_tests"]}]
    audits = audit_criteria(criteria, _container_only_caps())
    assert len(audits) == 1
    assert audits[0].verdict == "machine_verifiable"
    assert audits[0].missing_caps == []


def test_audit_requires_drive_browser_container_only_is_human_only() -> None:
    criteria = [{"criterion": "UI looks right", "priority": "must", "requires": ["drive_browser"]}]
    audits = audit_criteria(criteria, _container_only_caps())
    assert len(audits) == 1
    assert audits[0].verdict == "human_only"
    assert "drive_browser" in audits[0].missing_caps


def test_audit_requires_drive_browser_no_human_worker_is_unverifiable() -> None:
    criteria = [{"criterion": "UI looks right", "priority": "must", "requires": ["drive_browser"]}]
    audits = audit_criteria(criteria, _empty_worker_caps())
    assert len(audits) == 1
    assert audits[0].verdict == "human_only"


def test_audit_requires_unknown_cap_is_unverifiable() -> None:
    criteria = [{"criterion": "Magic check", "priority": "must", "requires": ["teleport_check"]}]
    audits = audit_criteria(criteria, _container_only_caps())
    assert len(audits) == 1
    assert audits[0].verdict == "unverifiable_no_worker"


def test_audit_empty_requires_is_machine_verifiable() -> None:
    criteria = [{"criterion": "Simple check", "priority": "should", "requires": []}]
    audits = audit_criteria(criteria, _container_only_caps())
    assert len(audits) == 1
    assert audits[0].verdict == "machine_verifiable"


def test_audit_mixed_criteria() -> None:
    criteria = [
        {"criterion": "Tests pass", "priority": "must", "requires": ["run_tests"]},
        {"criterion": "UI check", "priority": "must", "requires": ["drive_browser"]},
        {"criterion": "Perf check", "priority": "should", "requires": []},
    ]
    audits = audit_criteria(criteria, _container_only_caps())
    assert audits[0].verdict == "machine_verifiable"
    assert audits[1].verdict == "human_only"
    assert audits[2].verdict == "machine_verifiable"


# ---------------------------------------------------------------------------
# validate_requires tests
# ---------------------------------------------------------------------------


def test_validate_requires_must_with_empty_requires_deprecation() -> None:
    criteria = [{"criterion": "All tests pass", "priority": "must"}]
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        issues = validate_requires(criteria)
    assert len(issues) == 1
    assert "empty requires" in issues[0]
    assert any(issubclass(warning.category, DeprecationWarning) for warning in w)


def test_validate_requires_unknown_cap() -> None:
    criteria = [{"criterion": "Check", "priority": "must", "requires": ["run_tests", "fly_drone"]}]
    issues = validate_requires(criteria)
    assert len(issues) == 1
    assert "fly_drone" in issues[0]


def test_validate_requires_all_valid() -> None:
    criteria = [{"criterion": "Tests", "priority": "must", "requires": ["run_tests", "read_files"]}]
    issues = validate_requires(criteria)
    assert issues == []


def test_validate_requires_should_with_empty_requires_no_warning() -> None:
    criteria = [{"criterion": "Nice to have", "priority": "should", "requires": []}]
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        issues = validate_requires(criteria)
    assert issues == []
    assert not any(issubclass(warning.category, DeprecationWarning) for warning in w)


# ---------------------------------------------------------------------------
# classify_criteria tests
# ---------------------------------------------------------------------------


def test_classify_criteria_correct_split() -> None:
    criteria = [
        {"criterion": "Tests pass", "priority": "must", "requires": ["run_tests"]},
        {"criterion": "UI check", "priority": "must", "requires": ["drive_browser"]},
        {"criterion": "Lint clean", "priority": "should", "requires": ["run_linter"]},
        {"criterion": "Visual check", "priority": "info", "requires": ["inspect_runtime_ui"]},
    ]
    machine, human = classify_criteria(criteria, _container_only_caps())
    assert len(machine) == 2
    assert len(human) == 2
    assert machine[0]["criterion"] == "Tests pass"
    assert machine[1]["criterion"] == "Lint clean"
    assert human[0]["criterion"] == "UI check"
    assert human[1]["criterion"] == "Visual check"


def test_classify_criteria_all_machine() -> None:
    criteria = [
        {"criterion": "Tests", "priority": "must", "requires": ["run_tests"]},
        {"criterion": "Lint", "priority": "should", "requires": ["run_linter"]},
    ]
    machine, human = classify_criteria(criteria, _container_only_caps())
    assert len(machine) == 2
    assert len(human) == 0


def test_classify_criteria_empty() -> None:
    machine, human = classify_criteria([], _container_only_caps())
    assert machine == []
    assert human == []


# ---------------------------------------------------------------------------
# Worker capability discovery tests
# ---------------------------------------------------------------------------


def test_get_worker_capabilities_explicit_config() -> None:
    state = {
        "config": {
            "workers": {
                "my-agent": {"verifies": ["run_tests", "read_files"]},
                "human": {"verifies": ["drive_browser"]},
            }
        }
    }
    caps = get_worker_capabilities(state)
    assert caps["my-agent"] == {"run_tests", "read_files"}
    assert caps["human"] == {"drive_browser"}


def test_get_worker_capabilities_default_fallback() -> None:
    state = {"config": {}}
    caps = get_worker_capabilities(state)
    assert len(caps) > 0
    assert "premium" not in caps
    assert "claude" in caps
    for agent_caps in caps.values():
        assert agent_caps == set(DEFAULT_CONTAINER_CAPABILITIES)


def test_get_worker_capabilities_vendor_fallback_uses_codex_not_symbolic_premium() -> None:
    state = {"config": {"vendor": "codex"}}
    caps = get_worker_capabilities(state)
    assert "premium" not in caps
    assert "codex" in caps
    assert "claude" not in caps


# ---------------------------------------------------------------------------
# T20: Capability tests — no bogus "premium" worker, concrete premium
#      workers (Claude/Codex) still represented with correct capabilities
# ---------------------------------------------------------------------------


def test_default_fallback_exact_agents_no_premium_leakage() -> None:
    """Default fallback must contain exactly claude + hermes, never premium."""
    state = {"config": {}}
    caps = get_worker_capabilities(state)
    # No symbolic premium worker anywhere.
    assert "premium" not in caps
    # Default vendor is claude, so claude must be present alongside hermes.
    assert set(caps.keys()) == {"claude", "hermes"}
    # Every agent must have the full container capabilities.
    for agent_caps in caps.values():
        assert agent_caps == set(DEFAULT_CONTAINER_CAPABILITIES)


def test_codex_vendor_fallback_exact_agents_no_premium_leakage() -> None:
    """Codex-vendor fallback must contain exactly codex + hermes, never premium or claude."""
    state = {"config": {"vendor": "codex"}}
    caps = get_worker_capabilities(state)
    # No symbolic premium worker, and claude must not leak in.
    assert "premium" not in caps
    assert "claude" not in caps
    assert set(caps.keys()) == {"codex", "hermes"}
    for agent_caps in caps.values():
        assert agent_caps == set(DEFAULT_CONTAINER_CAPABILITIES)


def test_claude_vendor_fallback_exact_agents_no_premium_leakage() -> None:
    """Explicit claude-vendor fallback must contain exactly claude + hermes, never premium or codex."""
    state = {"config": {"vendor": "claude"}}
    caps = get_worker_capabilities(state)
    assert "premium" not in caps
    assert "codex" not in caps
    assert set(caps.keys()) == {"claude", "hermes"}
    for agent_caps in caps.values():
        assert agent_caps == set(DEFAULT_CONTAINER_CAPABILITIES)


def test_explicit_workers_config_never_leaks_premium_from_defaults() -> None:
    """When explicit workers are configured, premium must not leak in from defaults."""
    state = {
        "config": {
            "workers": {
                "custom-agent": {"verifies": ["run_tests"]},
            }
        }
    }
    caps = get_worker_capabilities(state)
    assert "premium" not in caps
    assert "claude" not in caps
    assert "codex" not in caps
    assert "hermes" not in caps
    assert set(caps.keys()) == {"custom-agent"}
    assert caps["custom-agent"] == {"run_tests"}


def test_union_verifies_merges_all() -> None:
    state = {
        "config": {
            "workers": {
                "a": {"verifies": ["run_tests"]},
                "b": {"verifies": ["read_files", "run_linter"]},
            }
        }
    }
    result = union_verifies(state)
    assert result == {"run_tests", "read_files", "run_linter"}


@pytest.mark.parametrize(
    ("payload", "error", "expected_warning"),
    [
        (None, None, False),
        ("{not valid json", None, True),
        (None, PermissionError("denied"), True),
    ],
)
def test_get_human_verification_status_read_visibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    payload: str | None,
    error: Exception | None,
    expected_warning: bool,
) -> None:
    verifications_path = tmp_path / "human_verifications.json"
    if payload is not None:
        verifications_path.write_text(payload, encoding="utf-8")
    elif error is not None:
        verifications_path.write_text("[]", encoding="utf-8")

    if error is not None:
        original_read_text = Path.read_text

        def _read_text(self: Path, *args, **kwargs):
            if self == verifications_path:
                raise error
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", _read_text)

    caplog.set_level("WARNING", logger="megaplan")
    status = get_human_verification_status(
        tmp_path,
        {"success_criteria": [{"criterion": "c1", "priority": "must", "requires": ["drive_browser"]}]},
        worker_caps={"codex": {"run_tests"}},
    )

    assert status["verified"] == 0
    assert status["pending"] == 1
    messages = [record.getMessage() for record in caplog.records]
    if expected_warning:
        assert any("M3A_WARN_CORRUPT_VERIFICATIONS" in message for message in messages)
    else:
        assert not messages
