from __future__ import annotations

"""Marker-only collection tests for multi-ComfyUI version compatibility.

All tests in this module are skipped by default unless an explicit
environment variable or config flag is set (COMFY_VERSION_COMPAT=1).
This keeps them out of the default CI suite.

Collection must work offline:
    python -m pytest -m comfy_version_compat --collect-only

Cross-version execution is Sprint 4 scope.
"""

import os

import pytest


# ---------------------------------------------------------------------------
# Skip guard: only run when explicitly opted in
# ---------------------------------------------------------------------------

def _compat_enabled() -> bool:
    """Check if ComfyUI version compat tests are explicitly enabled."""
    env_val = os.environ.get("COMFY_VERSION_COMPAT", "")
    return env_val.strip() in ("1", "true", "yes", "on")


# Mark all tests in this module with the comfy_version_compat marker
pytestmark = [
    pytest.mark.comfy_version_compat,
    pytest.mark.skipif(
        not _compat_enabled(),
        reason="Cross-version execution is Sprint 4 scope. Set COMFY_VERSION_COMPAT=1 to enable.",
    ),
]


# ---------------------------------------------------------------------------
# Four target ComfyUI channels
# ---------------------------------------------------------------------------

# Channel descriptions are documented in docs/comfy_version_support.md.
# These tests describe the contracts that Sprint 4 will implement.

CHANNEL_CURRENT = "comfyui-0.26.0"
"""Currently pinned pip-installable ComfyUI package — the active development target."""

CHANNEL_PREVIOUS = "previous-release"
"""One previous release pin — backward compatibility baseline."""

CHANNEL_AHEAD = "ahead-candidate"
"""One ahead candidate commit — forward compatibility smoke test."""

CHANNEL_UPSTREAM_HEAD = "upstream-main-head"
"""Upstream main HEAD — bleeding edge compatibility check."""

ALL_CHANNELS = [
    CHANNEL_CURRENT,
    CHANNEL_PREVIOUS,
    CHANNEL_AHEAD,
    CHANNEL_UPSTREAM_HEAD,
]


# ---------------------------------------------------------------------------
# Marker-only tests (contract descriptions)
# ---------------------------------------------------------------------------


@pytest.mark.comfy_version_compat
def test_channel_current_pip_package_contract() -> None:
    """Sprint 4 will verify: currently pinned pip-installable ComfyUI package passes
    the full port_convert_workflow + strict-ready validation suite.

    This is the primary development target.
    """
    pass


@pytest.mark.comfy_version_compat
def test_channel_previous_release_contract() -> None:
    """Sprint 4 will verify: one previous release pin (backward compat baseline)
    passes the port_convert_workflow validation suite.

    Guards against regressions in older-but-still-used ComfyUI versions.
    """
    pass


@pytest.mark.comfy_version_compat
def test_channel_ahead_candidate_contract() -> None:
    """Sprint 4 will verify: one ahead candidate commit (forward compat smoke)
    produces results that are at least importable and buildable.

    Early warning for upcoming breaking changes.
    """
    pass


@pytest.mark.comfy_version_compat
def test_channel_upstream_main_head_contract() -> None:
    """Sprint 4 will verify: upstream main HEAD (bleeding edge) can at minimum
    load and validate without hard crashes.

    Informs Sprint planning for ComfyUI version upgrades.
    """
    pass


@pytest.mark.comfy_version_compat
def test_all_channels_enumerated() -> None:
    """Sprint 4 will verify: all four channels are enumerated and individually
    testable via pytest markers or CLI flags.

    Validates that the channel selection mechanism works correctly.
    """
    assert len(ALL_CHANNELS) == 4
    assert CHANNEL_CURRENT == "comfyui-0.26.0"
    assert CHANNEL_PREVIOUS == "previous-release"
    assert CHANNEL_AHEAD == "ahead-candidate"
    assert CHANNEL_UPSTREAM_HEAD == "upstream-main-head"
