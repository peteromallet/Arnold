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
    roster_dispatch_spec,
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


# ---------------------------------------------------------------------------
# roster_dispatch_spec — bare roster token -> full, vendor-correct agent spec
# ---------------------------------------------------------------------------


def test_dispatch_spec_routes_deepseek_critics_to_direct_api() -> None:
    """A farmed-out DeepSeek critic must hit DeepSeek's direct API, not fall
    through to OpenRouter via a provider-less bare model name."""
    assert roster_dispatch_spec("deepseek-v4-pro") == "hermes:deepseek:deepseek-v4-pro"
    assert roster_dispatch_spec("deepseek-v4-flash") == "hermes:deepseek:deepseek-v4-flash"


def test_dispatch_spec_premium_roster_tokens_carry_their_agent() -> None:
    from megaplan.types import parse_agent_spec

    assert parse_agent_spec(roster_dispatch_spec("claude-opus-4-7")).agent == "claude"
    assert parse_agent_spec(roster_dispatch_spec("gpt-5.5")).agent == "codex"
    assert parse_agent_spec(roster_dispatch_spec("claude-sonnet-4-6")).agent == "claude"


def test_dispatch_spec_passes_through_valid_agent_specs() -> None:
    # Bare agent names and explicit specs are already dispatchable.
    assert roster_dispatch_spec("claude") == "claude"
    assert roster_dispatch_spec("hermes:deepseek:deepseek-v4-flash") == "hermes:deepseek:deepseek-v4-flash"


def test_dispatch_spec_rejects_unknown_token() -> None:
    with pytest.raises(ValueError):
        roster_dispatch_spec("totally-unknown")


def test_every_roster_model_has_a_rank_stable_dispatch_spec() -> None:
    # Each roster token must resolve to a spec that ranks back to the same entry.
    for entry in CRITIC_MODEL_ROSTER:
        assert roster_rank(roster_dispatch_spec(entry.model)) == entry.rank


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


def test_consistent_duplicate_selection_deduped_not_rejected() -> None:
    """A lens listed twice with the SAME critic_model is deduped (first wins)
    and reported as a warning, NOT hard-rejected — the model agreed with
    itself, so we keep the premium adaptive selection."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "claude"), ("scope", "claude")]
    )
    # Duplicate `scope` with the identical critic_model (the observed Opus bug).
    verdict["selections"].append(
        {"check_id": "scope", "critic_model": "claude", "why": "fire scope again"}
    )
    warnings = validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")
    assert warnings, "consistent duplicate should produce a warning"
    assert any("scope" in w and "deduped" in w for w in warnings)
    # The verdict was deduped in place: each check_id appears once.
    selected_ids = [s["check_id"] for s in verdict["selections"]]
    assert selected_ids.count("scope") == 1
    # First occurrence (why='fire scope') survived, the twin was dropped.
    scope_sel = next(s for s in verdict["selections"] if s["check_id"] == "scope")
    assert scope_sel["why"] == "fire scope"


def test_conflicting_duplicate_selection_hard_rejected() -> None:
    """A lens listed twice with DIFFERENT critic_models is genuinely ambiguous
    and remains a hard reject."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "claude"), ("scope", "claude")]
    )
    verdict["selections"].append(
        {"check_id": "scope", "critic_model": "deepseek-v4-pro", "why": "cheaper"}
    )
    with pytest.raises(ValueError, match="conflicting duplicate check_id"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_consistent_duplicate_skip_deduped_not_rejected() -> None:
    """A skipped lens listed twice is deduped (skips carry no critic, so any
    repeat is consistent) and reported, not hard-rejected."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude")])
    # `scope` is already in skipped (only correctness selected); duplicate it.
    assert any(sk["check_id"] == "scope" for sk in verdict["skipped"])
    verdict["skipped"].append({"check_id": "scope", "why": "skip scope again"})
    warnings = validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")
    assert any("scope" in w and "deduped" in w for w in warnings)
    skipped_ids = [s["check_id"] for s in verdict["skipped"]]
    assert skipped_ids.count("scope") == 1


def test_other_custom_areas_accepted_and_survive() -> None:
    """An evaluator verdict that covers all 9 (selected/skipped) AND adds 1-2
    bespoke `other` custom areas is accepted; the "other" entries survive in
    payload["selections"] and stay OUT of the 9-lens coverage union."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "claude"), ("scope", "claude")]
    )
    verdict["selections"].append({
        "check_id": "other",
        "area": "Migration ordering",
        "critic_model": "deepseek-v4-pro",
        "why": "probe: confirm the data backfill runs before the column drop",
    })
    verdict["selections"].append({
        "check_id": "other",
        "area": "Feature flag rollback",
        "critic_model": "claude",
        "why": "probe: verify the kill-switch disables the new path atomically",
    })
    warnings = validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")
    assert warnings == []
    # Both "other" entries survive in the deduped output.
    other = [s for s in verdict["selections"] if s.get("check_id") == "other"]
    assert len(other) == 2
    assert {s["area"] for s in other} == {"Migration ordering", "Feature flag rollback"}


def test_other_area_allows_all_nine_skipped() -> None:
    """An all-skip-of-9 verdict is accepted when it carries >=1 `other` area
    (the additive "other" satisfies the >=1-selection invariant)."""
    verdict = {
        "selections": [{
            "check_id": "other",
            "area": "Concurrency model",
            "critic_model": "claude",
            "why": "probe: verify the lock ordering avoids the A/B deadlock",
        }],
        "skipped": [{"check_id": cid, "why": f"skip {cid}"} for cid in ALL_CHECK_IDS],
        "evaluator_model": "claude-opus-4-7",
    }
    assert validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7") == []


def test_third_other_area_rejected_cap() -> None:
    """A 3rd `other` area exceeds MAX_OTHER_AREAS and is rejected."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude")])
    for n in range(3):
        verdict["selections"].append({
            "check_id": "other",
            "area": f"Custom area {n}",
            "critic_model": "claude",
            "why": f"probe {n}",
        })
    with pytest.raises(ValueError, match="at most 2 'other'"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_other_area_missing_name_rejected() -> None:
    """An `other` selection without a non-empty `area` is rejected."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude")])
    verdict["selections"].append({
        "check_id": "other",
        "critic_model": "claude",
        "why": "probe something",
    })
    with pytest.raises(ValueError, match="needs a non-empty `area`"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")


def test_other_area_duplicate_deduped() -> None:
    """Two `other` selections with the same area key are deduped + warned."""
    verdict = _full_coverage_verdict(selected=[("correctness", "claude")])
    verdict["selections"].append({
        "check_id": "other", "area": "Migration ordering",
        "critic_model": "claude", "why": "probe a",
    })
    verdict["selections"].append({
        "check_id": "other", "area": "migration ordering",  # same key (case)
        "critic_model": "claude", "why": "probe b",
    })
    warnings = validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")
    assert any("migration ordering" in w.lower() and "deduped" in w for w in warnings)
    other = [s for s in verdict["selections"] if s.get("check_id") == "other"]
    assert len(other) == 1
    assert other[0]["area"] == "Migration ordering"  # first occurrence survives


def test_clean_verdict_returns_no_warnings() -> None:
    """A clean verdict returns an empty warning list (backward-compatible)."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "claude"), ("scope", "claude")]
    )
    assert validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7") == []


def test_dedupe_then_all_skipped_rejected() -> None:
    """Coverage and at-least-one-selection invariants still hold after dedupe:
    if the only selection was a duplicate that collapses to nothing... (here we
    confirm coverage still enforced when a duplicated selection is deduped)."""
    # Select only `correctness`, but list it twice (consistent). After dedupe
    # the union must still cover all lenses — it does (one selection + skips).
    verdict = _full_coverage_verdict(selected=[("correctness", "claude")])
    verdict["selections"].append(
        {"check_id": "correctness", "critic_model": "claude", "why": "again"}
    )
    warnings = validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7")
    assert warnings
    assert len(verdict["selections"]) == 1


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

    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    # Critic runs on hermes; the evaluator routes to claude (its own slot), so
    # it can validly assign premium critics (rater >= dispatchee).
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda step, args: (
            ("claude", "persistent", False, "claude-opus-4-7")
            if step == "critique_evaluator"
            else ("hermes", "persistent", False, "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro")
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


def test_other_selection_synthesized_into_active_checks(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An evaluator `other` selection is synthesized into the critique's
    active_checks as a lens whose question is the evaluator's probe, and its
    synthesized id flows through to expected_ids."""
    import json

    from megaplan.prompts import create_claude_prompt

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

    # Critic runs on hermes; the evaluator routes to claude (its own slot), so
    # it can validly assign premium critics (rater >= dispatchee).
    monkeypatch.setattr(
        megaplan.handlers,
        "resolve_agent_mode",
        lambda step, args: (
            ("claude", "persistent", False, "claude-opus-4-7")
            if step == "critique_evaluator"
            else ("hermes", "persistent", False, "hermes:fireworks:accounts/fireworks/models/deepseek-v4-pro")
        ),
    )
    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])

    def _boom(*args, **kwargs):
        raise RuntimeError("forced parallel failure")

    monkeypatch.setattr(critique_mod, "run_parallel_critique", _boom)

    verdict = _full_coverage_verdict(selected=[("correctness", "claude")])
    verdict["selections"].append({
        "check_id": "other",
        "area": "Migration ordering",
        "critic_model": "claude",
        "why": "probe: confirm the data backfill runs before the column drop",
    })

    captured: dict[str, object] = {}

    def fake_run_step_with_worker(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
        if step == "critique_evaluator":
            return (
                WorkerResult(payload=verdict, raw_output="{}", duration_ms=1, cost_usd=0.0, session_id="ev"),
                "claude",
                "persistent",
                False,
            )
        captured["prompt_kwargs"] = prompt_kwargs
        payload = {
            "checks": [{"id": cid, "summary": "ok", "findings": []}
                       for cid in prompt_kwargs["expected_ids"]],
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

    pk = captured["prompt_kwargs"]
    expected_ids = pk["expected_ids"]
    # The synthesized "other" id is present and prefixed.
    oid = next((i for i in expected_ids if i.startswith("other_")), None)
    assert oid == "other_migration_ordering"
    # And its question is the evaluator's probe.
    synth = next(c for c in pk["active_checks"] if c["id"] == oid)
    assert synth["question"] == (
        "probe: confirm the data backfill runs before the column drop"
    )
    assert synth["category"] == "custom"


def test_evaluator_artifacts_preserved_per_iteration(
    plan_fixture: PlanFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each critique iteration's evaluator artifacts are preserved under a
    per-iteration suffix (`evaluator_verdict_v{n}.json` /
    `critique_evaluator_raw_v{n}.txt`) while the canonical fixed-path files
    keep pointing at the latest iteration for existing downstream readers.

    Regression: the canonical paths were the *only* write, so iteration 2
    silently overwrote iteration 1 and the stage-1 lens-selection reasoning of
    earlier passes was lost.
    """
    import json

    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    state_path = plan_fixture.plan_dir / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["config"]["adaptive_critique"] = True
    state_path.write_text(json.dumps(persisted, indent=2), encoding="utf-8")

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
    monkeypatch.setattr(critique_mod, "validate_critique_checks", lambda payload, **kw: [])

    def _boom(*args, **kwargs):
        raise RuntimeError("forced parallel failure")

    monkeypatch.setattr(critique_mod, "run_parallel_critique", _boom)

    # Distinct verdict + raw text per iteration so we can prove no overwrite.
    # Critic must be no stronger than the evaluator (deepseek-v4-pro, rank 3);
    # use a same-rank deepseek critic so the verdict validates.
    _critic = "deepseek-v4-pro"
    iter_verdicts = {
        1: _full_coverage_verdict(selected=[("correctness", _critic)]),
        2: _full_coverage_verdict(selected=[("correctness", _critic), ("scope", _critic)]),
    }
    current = {"iteration": 1}

    def fake_run_step_with_worker(step, state, plan_dir, args, *, root=None, prompt_kwargs=None, **kwargs):
        n = current["iteration"]
        if step == "critique_evaluator":
            return (
                WorkerResult(
                    payload=iter_verdicts[n],
                    raw_output=f"RAW-ITER-{n}",
                    duration_ms=1,
                    cost_usd=0.0,
                    session_id="ev",
                ),
                "claude",
                "persistent",
                False,
            )
        payload = {
            "checks": [{"id": cid, "summary": "ok", "findings": []}
                       for cid in prompt_kwargs["expected_ids"]],
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

    plan_dir = plan_fixture.plan_dir
    state_path = plan_dir / "state.json"

    # --- Iteration 1 ---
    megaplan.handle_critique(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name),
    )

    # --- Iteration 2: reset the gate so the PLANNED guard passes again, bump
    # the iteration counter exactly as the revise loop would. ---
    state = json.loads(state_path.read_text())
    state["iteration"] = 2
    state["current_state"] = "planned"
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    current["iteration"] = 2
    megaplan.handle_critique(
        plan_fixture.root,
        plan_fixture.make_args(plan=plan_fixture.plan_name),
    )

    # Per-iteration verdicts both survive and carry that iteration's selections.
    v1 = json.loads((plan_dir / "evaluator_verdict_v1.json").read_text())
    v2 = json.loads((plan_dir / "evaluator_verdict_v2.json").read_text())
    assert {s["check_id"] for s in v1["selections"]} == {"correctness"}
    assert {s["check_id"] for s in v2["selections"]} == {"correctness", "scope"}

    # Per-iteration raw artifacts both survive, distinct per pass.
    assert (plan_dir / "critique_evaluator_raw_v1.txt").read_text() == "RAW-ITER-1"
    assert (plan_dir / "critique_evaluator_raw_v2.txt").read_text() == "RAW-ITER-2"

    # Canonical "latest" files exist and reflect the final iteration (so
    # existing downstream readers keep seeing the most recent verdict).
    canonical = json.loads((plan_dir / "evaluator_verdict.json").read_text())
    assert {s["check_id"] for s in canonical["selections"]} == {"correctness", "scope"}
    assert (plan_dir / "critique_evaluator_raw.txt").read_text() == "RAW-ITER-2"


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
    assert "deepseek-v4-pro" in prompt
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


# ---------------------------------------------------------------------------
# Vendor gate: hallucinated out-of-vendor critic model rejection
# ---------------------------------------------------------------------------


def test_out_of_vendor_premium_critic_rejected_under_codex() -> None:
    """A Claude critic model (claude-sonnet-4-6) is rejected under --vendor codex."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "claude-sonnet-4-6"), ("scope", "claude")],
        evaluator_model="gpt-5.5",
    )
    with pytest.raises(ValueError, match="not available under --vendor codex"):
        validate_evaluator_verdict(verdict, evaluator_model="gpt-5.5", vendor="codex")


def test_out_of_vendor_premium_critic_rejected_under_claude() -> None:
    """A Codex critic model (gpt-5.5) is rejected under --vendor claude."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "gpt-5.5"), ("scope", "claude")],
        evaluator_model="claude-opus-4-7",
    )
    with pytest.raises(ValueError, match="not available under --vendor claude"):
        validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7", vendor="claude")


def test_alias_resolving_to_same_vendor_passes() -> None:
    """The alias 'claude' resolves to claude-opus-4-7 and passes under --vendor claude."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "claude"), ("scope", "claude")],
        evaluator_model="claude-opus-4-7",
    )
    # Does not raise — alias "claude" → "claude-opus-4-7" is owned by "claude"
    validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7", vendor="claude")


def test_same_vendor_premium_passes() -> None:
    """A same-vendor premium critic (gpt-5.5 under codex) is accepted."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "gpt-5.5"), ("scope", "gpt-5.5")],
        evaluator_model="gpt-5.5",
    )
    # Does not raise
    validate_evaluator_verdict(verdict, evaluator_model="gpt-5.5", vendor="codex")


def test_deepseek_critic_passes_under_either_vendor() -> None:
    """DeepSeek tiers are vendor-independent — they pass under any vendor."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "deepseek-v4-pro"), ("scope", "deepseek-v4-pro")],
        evaluator_model="deepseek-v4-pro",
    )
    validate_evaluator_verdict(verdict, evaluator_model="deepseek-v4-pro", vendor="codex")
    validate_evaluator_verdict(verdict, evaluator_model="deepseek-v4-pro", vendor="claude")


def test_no_vendor_gate_when_vendor_none() -> None:
    """When vendor=None, no gate is applied (backward-compatible default)."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "claude-sonnet-4-6"), ("scope", "claude")],
        evaluator_model="claude-opus-4-7",
    )
    # No vendor gate — passes even though claude-sonnet-4-6 might be cross-vendor
    validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7", vendor=None)


def test_spec_alias_resolves_correctly_under_vendor_gate() -> None:
    """A fully-qualified spec like 'claude:claude-opus-4-7' resolves to
    claude-opus-4-7 and passes under --vendor claude."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "claude:claude-opus-4-7"), ("scope", "claude")],
        evaluator_model="claude-opus-4-7",
    )
    validate_evaluator_verdict(verdict, evaluator_model="claude-opus-4-7", vendor="claude")


def test_effort_alias_resolves_correctly_under_vendor_gate() -> None:
    """An effort alias like 'codex:high' resolves to gpt-5.5 and passes under
    --vendor codex."""
    verdict = _full_coverage_verdict(
        selected=[("correctness", "codex:high"), ("scope", "codex")],
        evaluator_model="gpt-5.5",
    )
    validate_evaluator_verdict(verdict, evaluator_model="gpt-5.5", vendor="codex")


# ---------------------------------------------------------------------------
# Wiring regression: STEP_SCHEMA_FILENAMES must register critique_evaluator
# ---------------------------------------------------------------------------


def test_critique_evaluator_step_registered_in_schema_filenames() -> None:
    """Regression: silent KeyError('critique_evaluator') in shannon/codex worker.

    Until this entry existed, the adaptive critique path called
    ``_run_worker("critique_evaluator", ...)`` which dispatched to
    ``run_step_with_worker`` which then tried
    ``STEP_SCHEMA_FILENAMES["critique_evaluator"]`` and KeyError'd. The
    handler caught the KeyError, wrote a ``fallback: true`` evaluator_verdict
    and downgraded to the static robustness lens list — silently, for every
    iteration of every (non-creative) plan run.
    """
    from megaplan.schemas import SCHEMAS
    from megaplan.workers._impl import STEP_SCHEMA_FILENAMES, _STEP_REQUIRED_KEYS

    assert "critique_evaluator" in STEP_SCHEMA_FILENAMES, (
        "critique_evaluator step must have a schema filename or the adaptive "
        "critique path silently falls back to static lens selection"
    )
    schema_filename = STEP_SCHEMA_FILENAMES["critique_evaluator"]
    assert schema_filename in SCHEMAS, (
        f"{schema_filename!r} must be a known SCHEMAS entry"
    )
    # The required keys must match the validator in audits/critique_evaluator.py
    required = set(_STEP_REQUIRED_KEYS["critique_evaluator"])
    assert {"selections", "skipped", "evaluator_model"}.issubset(required)
