"""M4 T26 — doctor.py check functions accept a composition parameter
while preserving plan_dir for the flag-OFF path."""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.observability import doctor
from arnold.pipelines.megaplan.observability.composition_obs import InMemoryCompositionObs

CHECK_FUNCTIONS = [
    doctor._check_stale_lock,
    doctor._check_phase_timeout,
    doctor._check_llm_liveness,
    doctor._check_cost_trajectory,
    doctor._check_orphan_subprocesses,
    doctor._check_outstanding_flags,
]


@pytest.mark.parametrize("fn", CHECK_FUNCTIONS, ids=lambda f: f.__name__)
def test_check_accepts_composition_kwarg(fn):
    sig = inspect.signature(fn)
    assert "composition" in sig.parameters
    assert "plan_dir" in sig.parameters


@pytest.mark.parametrize("fn", CHECK_FUNCTIONS, ids=lambda f: f.__name__)
def test_check_callable_with_composition(tmp_path: Path, fn):
    composition = InMemoryCompositionObs()
    result = fn(tmp_path, composition=composition)
    assert isinstance(result, tuple) and len(result) == 3


@pytest.mark.parametrize("fn", CHECK_FUNCTIONS, ids=lambda f: f.__name__)
def test_check_flag_off_legacy_plan_dir_still_works(tmp_path: Path, fn):
    result = fn(tmp_path)
    assert isinstance(result, tuple) and len(result) == 3
