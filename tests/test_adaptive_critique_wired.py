"""CI guard: adaptive critique must stay wired end-to-end on every profile.

Background
----------
A regression in May 2026 silently disabled adaptive critique on every
``partnered`` / ``premium`` / ``apex`` run. The critique handler called
``_run_worker("critique_evaluator", ...)`` which dispatched through
``STEP_SCHEMA_FILENAMES[step]`` in ``megaplan/workers/_impl.py``. No
``critique_evaluator`` key was registered — KeyError. A broad
``except Exception`` in ``megaplan/handlers/critique.py`` swallowed it, wrote
``fallback: true`` to ``evaluator_verdict.json``, and fell through to static
lenses. The plan still shipped because static lenses produce reasonable
output, but the adaptive design never ran.

These tests fail loudly if the wiring ever regresses — at any of the
schema-dispatch, schema-registration, prompt-template, or required-keys
layers. They also assert that every shipped profile with
``adaptive_critique = true`` passes the in-memory probe, and that the
``handle_init`` path raises ``AdaptiveCritiqueMisconfiguredError`` if the
wiring is broken when ``adaptive_critique`` resolves True (so the
silent-fallback bug class cannot recur even with the swallow-except still
nominally in place at the critique handler).

These tests are deliberately offline — no LLM calls, no plan dirs, no
disk schema rendering. They guard the static wiring that the original bug
broke.
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

import megaplan
import megaplan.cli as cli_module
import megaplan._core.io as io_module
from megaplan.audits.critique_evaluator import (
    assert_adaptive_critique_wired,
    probe_adaptive_critique_wiring,
)
from megaplan.profiles import load_profile_metadata
from megaplan.types import AdaptiveCritiqueMisconfiguredError


@pytest.fixture
def isolated_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Module-local copy of the fixture in tests/test_config.py — keeps the
    test self-contained so a future move of test_config.py doesn't break the
    CI guard."""
    config_path = tmp_path / ".config" / "megaplan"

    def fake_config_dir(home: Path | None = None) -> Path:
        del home
        return config_path

    monkeypatch.setattr(io_module, "config_dir", fake_config_dir)
    monkeypatch.setattr(cli_module, "config_dir", fake_config_dir)
    return config_path


# ---------------------------------------------------------------------------
# Probe-level guard
# ---------------------------------------------------------------------------


def test_adaptive_critique_wiring_probe_passes_on_clean_install() -> None:
    """Every wiring probe must pass on a clean checkout. This is the CI guard
    that would have caught the original May 2026 KeyError bug.

    If this fails: adaptive critique is silently disabled at runtime. Look at
    the failing probe to see which layer regressed (step dispatch, schema
    dict, prompt template, or required-keys table).
    """
    results = probe_adaptive_critique_wiring()
    failures = [(label, detail) for label, passed, detail in results if not passed]
    assert not failures, (
        "adaptive critique wiring regression — these probes failed:\n"
        + "\n".join(f"  - {label}: {detail}" for label, detail in failures)
    )


def test_assert_adaptive_critique_wired_is_a_noop_on_clean_install() -> None:
    """The init-time gate must not raise on a healthy tree."""
    assert_adaptive_critique_wired()  # must not raise


def test_assert_adaptive_critique_wired_raises_when_step_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The init-time gate must raise AdaptiveCritiqueMisconfiguredError when
    the ``critique_evaluator`` step is unregistered. Simulates the original
    bug by popping the registration.

    This test is the load-bearing one — if the original silent-fallback bug
    recurs (someone removes the schema/dispatch entry), this test fires
    immediately at PR time.
    """
    from megaplan.workers import _impl as worker_impl

    patched = dict(worker_impl.STEP_SCHEMA_FILENAMES)
    patched.pop("critique_evaluator", None)
    monkeypatch.setattr(worker_impl, "STEP_SCHEMA_FILENAMES", patched)

    with pytest.raises(AdaptiveCritiqueMisconfiguredError) as exc_info:
        assert_adaptive_critique_wired()

    assert "critique_evaluator" in str(exc_info.value)
    assert "missing" in str(exc_info.value).lower() or "STEP_SCHEMA_FILENAMES" in str(exc_info.value)


def test_assert_adaptive_critique_wired_raises_when_schema_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate must raise when the dispatch points at a schema filename that
    isn't in the SCHEMAS dict. This catches the half-fixed case where someone
    registers the step but forgets the schema entry."""
    from megaplan import schemas as schemas_module

    patched = dict(schemas_module.SCHEMAS)
    patched.pop("critique_evaluator.json", None)
    monkeypatch.setattr(schemas_module, "SCHEMAS", patched)

    with pytest.raises(AdaptiveCritiqueMisconfiguredError) as exc_info:
        assert_adaptive_critique_wired()

    assert "critique_evaluator.json" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Profile-level guard: every shipped profile with adaptive_critique=true
# ---------------------------------------------------------------------------


def _adaptive_critique_profiles() -> list[str]:
    """All built-in profiles that ship with adaptive_critique = true."""
    metadata = load_profile_metadata()
    return sorted(
        name
        for name, meta in metadata.items()
        if meta.get("adaptive_critique") is True
    )


@pytest.mark.parametrize("profile_name", _adaptive_critique_profiles())
def test_profile_with_adaptive_critique_passes_wiring_probe(profile_name: str) -> None:
    """For every shipped profile that turns adaptive critique on by default,
    the wiring must pass the probe. If a profile sets adaptive_critique=true
    but the runtime cannot dispatch the step, every plan run on that profile
    would silently degrade to static lenses.

    Parametrized over the profile set so a newly-added adaptive profile is
    automatically guarded.
    """
    results = probe_adaptive_critique_wiring()
    failures = [(label, detail) for label, passed, detail in results if not passed]
    assert not failures, (
        f"profile {profile_name!r} sets adaptive_critique=true but the "
        f"runtime wiring is broken:\n"
        + "\n".join(f"  - {label}: {detail}" for label, detail in failures)
    )


# ---------------------------------------------------------------------------
# End-to-end: handle_init refuses to seed adaptive critique on a broken tree
# ---------------------------------------------------------------------------


def _make_init_namespace(project_dir: Path, *, profile: str = "partnered") -> Namespace:
    return Namespace(
        project_dir=str(project_dir),
        name="adaptive-wired-guard",
        auto_approve=None,
        robustness=None,
        hermes=None,
        phase_model=[],
        idea="idea",
        profile=profile,
        adaptive_critique=True,
        strict_adaptive_critique=None,
        critic_model=None,
        strict_notes=None,
        max_tasks_per_batch=None,
    )


def test_handle_init_refuses_adaptive_critique_when_wiring_broken(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``handle_init`` must reject a request to enable adaptive critique when
    the runtime wiring is broken. This is the layered defense against the
    original silent-fallback bug: even with the swallow-except left at the
    critique handler, no plan would survive ``init`` long enough to hit it
    because init rejects misconfigured runs fast.

    Without the init-time gate, the bug surfaces only at critique time —
    after planning cost has been paid and after the plan looks committed.
    """
    from megaplan.workers import _impl as worker_impl

    patched = dict(worker_impl.STEP_SCHEMA_FILENAMES)
    patched.pop("critique_evaluator", None)
    monkeypatch.setattr(worker_impl, "STEP_SCHEMA_FILENAMES", patched)

    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()

    with pytest.raises(AdaptiveCritiqueMisconfiguredError):
        megaplan.handle_init(root, _make_init_namespace(project_dir))


def test_handle_init_succeeds_when_wiring_healthy(
    isolated_config_dir: Path, tmp_path: Path
) -> None:
    """The init-time gate is a no-op on a healthy tree. Confirms the gate
    doesn't introduce a false-positive regression for clean checkouts."""
    isolated_config_dir.mkdir(parents=True, exist_ok=True)
    (isolated_config_dir / "config.json").write_text(
        json.dumps({"execution": {}}), encoding="utf-8"
    )

    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()

    response = megaplan.handle_init(root, _make_init_namespace(project_dir))
    state_path = root / ".megaplan" / "plans" / response["plan"] / "state.json"
    state: dict[str, Any] = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["config"]["adaptive_critique"] is True
    # The strict-mode field also flows through (default False).
    assert state["config"]["strict_adaptive_critique"] is False


def test_handle_init_threads_strict_adaptive_critique_when_explicit(
    isolated_config_dir: Path, tmp_path: Path
) -> None:
    """``--strict-adaptive-critique`` (or
    ``[execution] strict_adaptive_critique = true``) must flow through to
    ``state['config']['strict_adaptive_critique']`` so the critique handler
    can refuse the silent fallback."""
    isolated_config_dir.mkdir(parents=True, exist_ok=True)
    (isolated_config_dir / "config.json").write_text(
        json.dumps({"execution": {"strict_adaptive_critique": True}}),
        encoding="utf-8",
    )

    root = tmp_path / "root"
    project_dir = tmp_path / "project"
    root.mkdir()
    project_dir.mkdir()

    response = megaplan.handle_init(root, _make_init_namespace(project_dir))
    state_path = root / ".megaplan" / "plans" / response["plan"] / "state.json"
    state: dict[str, Any] = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["config"]["strict_adaptive_critique"] is True
