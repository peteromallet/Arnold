"""Tests for the adaptive critique evaluator (T11).

Covers:
  * tier-validity guard over CRITIQUE_CHECKS
  * roster_rank normalization + raise-on-unknown
  * validate_evaluator_verdict hard-reject discipline
  * the single-source / sequential-fallback regression (FLAG-001): the
    verdict's checks reach the sequential `_critique_prompt` via the REAL
    create_prompt dispatch path, while the flag-off path recomputes
  * the revise-loop differential (iteration N>=2) prompt
  * ROBUSTNESS_LEVELS never gains "adaptive"/"variable"
  * finalize rank <= strongest execute-tier rank for variable/directed/apex
"""

from __future__ import annotations

import tomllib
from importlib.resources import files
from pathlib import Path

import pytest

import megaplan
import megaplan.handlers
import megaplan.handlers.critique as critique_mod
from megaplan.audits.critique_evaluator import (
    CRITIC_MODEL_ROSTER,
    roster_rank,
    validate_evaluator_verdict,
)
from megaplan.audits.robustness import CRITIQUE_CHECKS
from megaplan.types import ROBUSTNESS_LEVELS
from megaplan.workers import WorkerResult
from tests.conftest import PlanFixture, load_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_CHECK_IDS = [c["id"] for c in CRITIQUE_CHECKS]


def _full_coverage_verdict(
    *,
    selected: list[tuple[str, str]],
    evaluator_model: str = "claude-opus-4-7",
) -> dict:
    """Build a verdict whose selections + skips cover every lens exactly once."""
    selected_ids = {cid for cid, _ in selected}
    selections = [
        {"check_id": cid, "critic_model": critic, "why": f"fire {cid}"}
        for cid, critic in selected
    ]
    skipped = [
        {"check_id": cid, "why": f"skip {cid} — covered by selection set"}
        for cid in ALL_CHECK_IDS
        if cid not in selected_ids
    ]
    return {
        "selections": selections,
        "skipped": skipped,
        "evaluator_model": evaluator_model,
    }


# ---------------------------------------------------------------------------
# Tier-validity guard
# ---------------------------------------------------------------------------

def test_every_critique_check_has_a_valid_tier() -> None:
    """Maintainer guard: a silent lens with a bad tier would be dropped from
    the core/extended robustness sets without anyone noticing."""
    valid_tiers = {"core", "extended"}
    for check in CRITIQUE_CHECKS:
        assert "tier" in check, f"check {check.get('id')!r} is missing `tier`"
        assert check["tier"] in valid_tiers, (
            f"check {check['id']!r} has invalid tier {check['tier']!r}; "
            f"expected one of {sorted(valid_tiers)}"
        )


# ---------------------------------------------------------------------------
# roster_rank normalization
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "spec, expected_rank",
    [
        ("claude", 1),
        ("codex", 1),
        ("claude:low", 1),
        ("codex:high", 1),
        ("claude:claude-opus-4-7", 1),
        ("claude:claude-sonnet-4-6", 2),
        ("hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro", 3),
        ("hermes:deepseek:deepseek-v4-pro", 3),
        ("hermes:deepseek:deepseek-v4-flash", 4),
    ],
)
def test_roster_rank_normalizes_legitimate_profile_strings(spec: str, expected_rank: int) -> None:
    assert roster_rank(spec) == expected_rank


@pytest.mark.parametrize(
    "spec",
    ["", "   ", "deepseek-v3p2", "openai:gpt-4o", "claude:claude-opus-9", "totally-unknown"],
)
def test_roster_rank_raises_on_unknown(spec: str) -> None:
    with pytest.raises(ValueError):
        roster_rank(spec)


def test_claude_and_codex_co_ranked_top() -> None:
    top = [e.model for e in CRITIC_MODEL_ROSTER if e.rank == 1]
    assert "claude-opus-4-7" in top
    assert "gpt-5.5" in top


# ---------------------------------------------------------------------------
# validate_evaluator_verdict — hard-reject discipline
# ---------------------------------------------------------------------------

def test_valid_verdict_accepted() -> None:
    verdict = _full_coverage_verdict(
        selected=[("correctness", "claude"), ("scope", "claude")]
    )
    # Does not raise.
    validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_unknown_check_id_rejected() -> None:
    verdict = _full_coverage_verdict(selected=[("correctness", "claude")])
    verdict["selections"].append(
        {"check_id": "not_a_real_lens", "critic_model": "claude", "why": "x"}
    )
    with pytest.raises(ValueError, match="unknown check_id"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_non_covering_union_rejected() -> None:
    verdict = _full_coverage_verdict(selected=[("correctness", "claude")])
    # Drop one skip so the union no longer covers all lenses.
    verdict["skipped"].pop()
    with pytest.raises(ValueError, match="Not all lenses covered"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_overlapping_union_rejected() -> None:
    verdict = _full_coverage_verdict(selected=[("correctness", "claude")])
    # Re-add a selected id into skipped to force overlap.
    verdict["skipped"].append({"check_id": "correctness", "why": "also skipped"})
    with pytest.raises(ValueError, match="Overlap"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_unjustified_skip_rejected() -> None:
    verdict = _full_coverage_verdict(selected=[("correctness", "claude")])
    verdict["skipped"][0]["why"] = "   "
    with pytest.raises(ValueError, match="non-empty `why`"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_empty_selections_rejected() -> None:
    # All lenses skipped, no selection.
    verdict = {
        "selections": [],
        "skipped": [{"check_id": cid, "why": f"skip {cid}"} for cid in ALL_CHECK_IDS],
        "evaluator_model": "claude-opus-4-7",
    }
    with pytest.raises(ValueError, match="At least one lens"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_rater_weaker_than_dispatchee_rejected() -> None:
    """A weak evaluator may not dispatch a stronger critic (rank 1 = strongest)."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "claude")],
        evaluator_model="hermes:deepseek:deepseek-v4-flash",
    )
    with pytest.raises(ValueError, match="stronger than evaluator"):
        validate_evaluator_verdict(
            verdict, evaluator_model="hermes:deepseek:deepseek-v4-flash"
        )


def test_rater_equal_or_stronger_than_dispatchee_accepted() -> None:
    """A flash evaluator dispatching a flash critic is allowed (equal rank)."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "hermes:deepseek:deepseek-v4-flash")],
        evaluator_model="hermes:deepseek:deepseek-v4-flash",
    )
    validate_evaluator_verdict(
        verdict, evaluator_model="hermes:deepseek:deepseek-v4-flash"
    )


# ---------------------------------------------------------------------------
# Single-source dispatch: REAL create_prompt -> _critique_prompt
# ---------------------------------------------------------------------------

def test_critique_prompt_uses_passed_active_checks_via_real_dispatch(
    plan_fixture: PlanFixture,
) -> None:
    """create_claude_prompt('critique', ..., active_checks=subset) drives the
    real _critique_prompt with the provided subset, NOT recomputed defaults."""
    from megaplan._core import load_plan
    from megaplan.prompts import create_claude_prompt

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)

    subset = [c for c in CRITIQUE_CHECKS if c["id"] in {"correctness", "scope"}]
    expected_ids = [c["id"] for c in subset]

    default_prompt = create_claude_prompt(
        "critique", state, plan_fixture.plan_dir, root=plan_fixture.root
    )
    verdict_prompt = create_claude_prompt(
        "critique",
        state,
        plan_fixture.plan_dir,
        root=plan_fixture.root,
        active_checks=subset,
        expected_ids=expected_ids,
    )

    # The verdict-driven prompt reflects exactly the 2 selected lenses.
    assert "it contains 2 checks" in verdict_prompt
    # The flag-off (recomputed) default differs from the 2-lens verdict set.
    assert "it contains 2 checks" not in default_prompt


def test_forced_parallel_failure_sequential_fallback_honors_verdict(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FLAG-001 regression: with the flag on, force the parallel critique path
    to raise; the sequential fallback must build its prompt from the verdict's
    checks (threaded via prompt_kwargs through the REAL create_prompt dispatch),
    not recompute from robustness defaults."""
    import json

    from megaplan.prompts import create_claude_prompt

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))

    # Enable adaptive critique in the persisted config (it is a config flag set
    # at init time, not a per-invocation arg read during critique).
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    # Evaluator escalates to claude (roster top) because critique runs on hermes.
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda step, args: (
            "hermes",
            "persistent",
            False,
            "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro",
        ),
    )
    # Skip downstream check-payload validation; we only care about prompt build.
    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])
    # Force the parallel path to fail so the handler falls back to sequential.
    def _boom(*args, **kwargs):
        raise RuntimeError("forced parallel failure")

    monkeypatch.setattr(critique_mod, "run_parallel_critique", _boom)

    verdict = _full_coverage_verdict(
        selected=[("correctness", "claude"), ("scope", "claude")]
    )

    captured: dict[str, object] = {}

    def fake_run_step_with_worker(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "claude",
                "persistent",
                False,
            )
        # Sequential critique fallback — drive the REAL dispatch path.
        captured["prompt_kwargs"] = prompt_kwargs
        captured["rendered"] = create_claude_prompt(
            step, state, plan_dir, root=root, **(prompt_kwargs or {})
        )
        payload = {
            "checks": [
                {"id": "correctness", "summary": "ok", "findings": []},
                {"id": "scope", "summary": "ok", "findings": []},
            ],
            "flags": [],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        }
        return (
            WorkerResult(payload=payload, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="cr"),
            "hermes",
            "persistent",
            False,
        )

    monkeypatch.setattr(megaplan.workers, "run_step_with_worker", fake_run_step_with_worker)

    megaplan.handle_critique(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name),
    )

    # The verdict reached the sequential fallback via prompt_kwargs.
    pk = captured["prompt_kwargs"]
    assert pk is not None, "sequential fallback received no prompt_kwargs"
    assert sorted(pk["expected_ids"]) == ["correctness", "scope"]
    # And the REAL prompt was built from the verdict's 2 lenses, not the
    # robustness-default (standard => more than 2 core checks).
    assert "it contains 2 checks" in captured["rendered"]
    # The verdict artifact was written before fan-out.
    assert (plan_fixture.plan_dir / "evaluator_verdict.json").exists()


# ---------------------------------------------------------------------------
# Revise-loop differential (iteration N>=2)
# ---------------------------------------------------------------------------

def test_differential_section_present_only_on_iteration_n(
    plan_fixture: PlanFixture,
) -> None:
    """Iteration N>=2 with faults/pressure/gate signals produces a differential
    prompt distinct from the blind iteration-1 selection."""
    from megaplan._core import load_plan
    from megaplan.prompts.critique_evaluator import _critique_evaluator_prompt

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)

    flag_lifecycle = {
        "flags": [
            {"id": "F1", "status": "verified", "concern": "off-by-one already fixed"},
        ]
    }
    iteration_pressure = [
        {
            "fuzzy_group_id": "G1",
            "member_flag_ids": ["F2", "F3"],
            "iterations_open": 3,
            "addressed_then_reopened_count": 2,
            "representative_concern": "caller signature mismatch keeps reopening",
        }
    ]
    gate_signals = {
        "signals": {
            "unresolved_flags": [
                {"id": "F4", "category": "correctness", "severity": "significant", "concern": "race condition"},
            ],
            "recurring_critiques": ["the same scope concern keeps recurring"],
            "loop_summary": "two prior iterations, pressure rising",
            "plan_delta_from_previous": 12.5,
        }
    }

    # Iteration 1 (blind) — no differential context.
    state["iteration"] = 1
    blind = _critique_evaluator_prompt(state, plan_fixture.plan_dir, root=plan_fixture.root)
    assert "Revise-Loop Differential Context" not in blind

    # Iteration 2 — differential context consumes faults/pressure/gate signals.
    state["iteration"] = 2
    differential = _critique_evaluator_prompt(
        state,
        plan_fixture.plan_dir,
        root=plan_fixture.root,
        flag_lifecycle=flag_lifecycle,
        iteration_pressure=iteration_pressure,
        gate_signals=gate_signals,
    )
    assert "Revise-Loop Differential Context (Iteration 2)" in differential
    assert differential != blind
    # Reused signals surface in the differential guidance.
    assert "caller signature mismatch keeps reopening" in differential
    assert "off-by-one already fixed" in differential
    assert "race condition" in differential


def test_prep_section_present_when_prep_artifacts_supplied(
    plan_fixture: PlanFixture,
) -> None:
    """The evaluator prompt surfaces the prep dossier + coverage signals when
    prep artifacts are passed, and omits the section when they are not."""
    from megaplan._core import load_plan
    from megaplan.prompts.critique_evaluator import _critique_evaluator_prompt

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)

    # Blind — no prep context passed.
    blind = _critique_evaluator_prompt(state, plan_fixture.plan_dir, root=plan_fixture.root)
    assert "Prep that preceded this plan" not in blind

    # With prep dossier + metrics, the section renders and decision-relevant
    # coverage signals (counts, gaps, contradictions) surface.
    prep_metrics = {
        "area_count": 4,
        "fanout_count": 3,
        "completed_count": 2,
        "partial_count": 0,
        "timed_out_count": 1,
        "error_count": 0,
        "gap_notes": ["auth token refresh path never researched"],
        "contradiction_notes": ["two sources disagree on retry semantics"],
    }
    prep_dossier = "## Prep dossier\n\nTriaged 4 areas; fanned out 3 research units."
    with_prep = _critique_evaluator_prompt(
        state,
        plan_fixture.plan_dir,
        root=plan_fixture.root,
        prep_dossier_text=prep_dossier,
        prep_metrics=prep_metrics,
    )
    assert "Prep that preceded this plan" in with_prep
    assert "timed_out_count=1" in with_prep
    assert "auth token refresh path never researched" in with_prep
    assert "two sources disagree on retry semantics" in with_prep
    assert "fanned out 3 research units" in with_prep
    assert with_prep != blind


def test_evaluator_prompt_steers_cheapest_capable_critic(
    plan_fixture: PlanFixture,
) -> None:
    """The evaluator prompt must instruct the premium adjudicator to assign the
    cheapest capable critic per lens, escalating to premium only when a lens
    genuinely demands it — the embodiment of the cheapest-capable philosophy."""
    from megaplan._core import load_plan
    from megaplan.prompts.critique_evaluator import _critique_evaluator_prompt

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)

    prompt = _critique_evaluator_prompt(state, plan_fixture.plan_dir, root=plan_fixture.root)

    # The steer headline and the cost-ordered preference for cheap critics.
    assert "cheapest capable critic" in prompt.lower()
    assert "configured lowest-cost critic" in prompt.lower()
    # Escalation to premium must be conditional / justified, not the default.
    lower = prompt.lower()
    assert "escalate" in lower
    assert "only" in lower
    # The pre-existing rater >= dispatchee ceiling must survive intact.
    assert "no weaker than" in prompt


# ---------------------------------------------------------------------------
# ROBUSTNESS_LEVELS purity
# ---------------------------------------------------------------------------

def test_adaptive_never_a_robustness_level() -> None:
    """The flag is a boolean config knob; it must never become a robustness level."""
    assert "adaptive" not in ROBUSTNESS_LEVELS
    assert "variable" not in ROBUSTNESS_LEVELS


# ---------------------------------------------------------------------------
# Prompt/model-ID guard — no hardcoded model identifiers in prompt source
# ---------------------------------------------------------------------------

#: Model identifiers that must not appear as hardcoded strings in prompt-building
#: Python sources (``megaplan/prompts/**/*.py``).  These belong in the
#: ``CRITIC_MODEL_ROSTER`` (``megaplan/audits/critique_evaluator.py``) and
#: profile/config modules, not in natural-language prompt text.
_PROHIBITED_MODEL_IDS_IN_PROMPTS: tuple[str, ...] = (
    "deepseek-v4-pro",
    "deepseek-v4-flash",
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "gpt-5.5",
)


def test_no_model_identifier_strings_in_prompt_python_sources() -> None:
    """Guard: ``megaplan/prompts/**/*.py`` files must not contain hardcoded
    model identifier strings used in natural-language prompt guidance.

    Model names live in the roster (``megaplan/audits/critique_evaluator.py``)
    and profile/config modules.  Prompt text should refer to critics by their
    configured / roster-derived role (\"the configured lowest-cost critic\",
    \"the configured fallback critic\"), not by concrete model id.
    """
    prompts_dir = Path(__file__).parent.parent / "megaplan" / "prompts"
    py_files = sorted(prompts_dir.rglob("*.py"))
    assert py_files, f"No Python files found under {prompts_dir}"

    violations: list[tuple[str, int, str]] = []
    for py_file in py_files:
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            for model_id in _PROHIBITED_MODEL_IDS_IN_PROMPTS:
                if model_id in line:
                    violations.append((str(py_file), lineno, model_id))

    assert not violations, (
        "Hardcoded model identifier(s) found in prompt-building Python sources.\n"
        "Prompt text must use configured-critic wording (e.g. \"the configured "
        "lowest-cost critic\"), not concrete model ids.  Model ids belong in "
        "the roster (megaplan/audits/critique_evaluator.py).\n\n"
        + "\n".join(f"  {f}:{lineno} → {mid!r}" for f, lineno, mid in violations)
    )


# ---------------------------------------------------------------------------
# Finalize rank >= strongest execute-tier model
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("profile_name", ["variable", "directed", "apex"])
def test_finalize_rank_not_weaker_than_strongest_execute_tier(profile_name: str) -> None:
    """rater>=dispatchee for finalize: roster_rank(finalize) <= roster_rank of the
    strongest execute-tier model (rank 1 = strongest)."""
    data = tomllib.loads(
        files("megaplan.profiles").joinpath(f"{profile_name}.toml").read_text()
    )
    profile = data["profiles"][profile_name]
    finalize_model = profile["finalize"]
    execute_tier = profile["tier_models"]["execute"]
    strongest_execute_rank = min(roster_rank(m) for m in execute_tier.values())
    assert roster_rank(finalize_model) <= strongest_execute_rank, (
        f"{profile_name}: finalize {finalize_model!r} (rank "
        f"{roster_rank(finalize_model)}) is weaker than the strongest "
        f"execute-tier model (rank {strongest_execute_rank})"
    )


# ---------------------------------------------------------------------------
# T8: flag_verifications validator — valid + each invalid branch
# ---------------------------------------------------------------------------


def test_flag_verifications_valid_accepted() -> None:
    """A valid verdict with well-formed flag_verifications passes validation."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude"), ("scope", "claude")])
    verdict["flag_verifications"] = [
        {"flag_id": "FLAG-001", "lens": "correctness", "outcome": "verified", "rationale": "diff confirms fix"},
    ]
    validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_flag_verifications_missing_flag_id_rejected() -> None:
    """flag_verifications entry with empty flag_id is rejected."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude"), ("scope", "claude")])
    verdict["flag_verifications"] = [
        {"flag_id": "", "lens": "correctness", "outcome": "verified", "rationale": "x"},
    ]
    with pytest.raises(ValueError, match="missing a non-empty `flag_id`"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_flag_verifications_missing_lens_rejected() -> None:
    """flag_verifications entry with empty lens is rejected."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude"), ("scope", "claude")])
    verdict["flag_verifications"] = [
        {"flag_id": "FLAG-001", "lens": "", "outcome": "verified", "rationale": "x"},
    ]
    with pytest.raises(ValueError, match="missing non-empty `lens`"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_flag_verifications_unknown_lens_rejected() -> None:
    """flag_verifications entry with lens not in CRITIQUE_CHECKS is rejected."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude"), ("scope", "claude")])
    verdict["flag_verifications"] = [
        {"flag_id": "FLAG-001", "lens": "nonexistent_lens", "outcome": "verified", "rationale": "x"},
    ]
    with pytest.raises(ValueError, match="unknown lens"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_flag_verifications_invalid_outcome_rejected() -> None:
    """flag_verifications entry with outcome not in {verified,open,accepted_tradeoff} is rejected."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude"), ("scope", "claude")])
    verdict["flag_verifications"] = [
        {"flag_id": "FLAG-001", "lens": "correctness", "outcome": "resolved", "rationale": "x"},
    ]
    with pytest.raises(ValueError, match="`outcome` must be one of"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_flag_verifications_empty_rationale_rejected() -> None:
    """flag_verifications entry with empty rationale is rejected."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude"), ("scope", "claude")])
    verdict["flag_verifications"] = [
        {"flag_id": "FLAG-001", "lens": "correctness", "outcome": "verified", "rationale": ""},
    ]
    with pytest.raises(ValueError, match="missing non-empty `rationale`"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_flag_verifications_duplicate_flag_id_rejected() -> None:
    """flag_verifications with duplicate flag_id in the same payload is rejected."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude"), ("scope", "claude")])
    verdict["flag_verifications"] = [
        {"flag_id": "FLAG-001", "lens": "correctness", "outcome": "verified", "rationale": "x"},
        {"flag_id": "FLAG-001", "lens": "scope", "outcome": "open", "rationale": "y"},
    ]
    with pytest.raises(ValueError, match="duplicate flag_id"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_flag_verifications_not_a_list_rejected() -> None:
    """flag_verifications that is not a list is rejected."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude"), ("scope", "claude")])
    verdict["flag_verifications"] = "not a list"
    with pytest.raises(ValueError, match="`flag_verifications` must be a list"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_flag_verifications_not_an_object_rejected() -> None:
    """flag_verifications entry that is not a dict is rejected."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude"), ("scope", "claude")])
    verdict["flag_verifications"] = ["not a dict"]
    with pytest.raises(ValueError, match="flag_verification 1 must be an object"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_flag_verifications_coverage_still_enforced() -> None:
    """Valid flag_verifications do not weaken the coverage requirement — missing lens still rejected."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude")])
    # Valid flag_verifications present, but a lens is missing from the coverage union.
    verdict["flag_verifications"] = [
        {"flag_id": "FLAG-001", "lens": "correctness", "outcome": "verified", "rationale": "diff supports fix"},
    ]
    # Intentionally remove one skip so coverage is incomplete.
    verdict["skipped"].pop()
    with pytest.raises(ValueError, match="Not all lenses covered"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_flag_verifications_rater_still_enforced() -> None:
    """Valid flag_verifications do not weaken the rater>=dispatchee invariant."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "claude")],
        evaluator_model="hermes:deepseek:deepseek-v4-flash",
    )
    verdict["flag_verifications"] = [
        {"flag_id": "FLAG-001", "lens": "correctness", "outcome": "verified", "rationale": "diff supports fix"},
    ]
    with pytest.raises(ValueError, match="stronger than evaluator"):
        validate_evaluator_verdict(verdict, evaluator_model="hermes:deepseek:deepseek-v4-flash")


def test_flag_verifications_optional_field_absent_accepted() -> None:
    """A verdict without flag_verifications still passes (field is optional)."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude"), ("scope", "claude")])
    # No flag_verifications key at all.
    assert "flag_verifications" not in verdict
    validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")
