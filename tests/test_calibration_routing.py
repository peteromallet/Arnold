from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from arnold.pipelines.megaplan._pipeline.flags import calibration_query_route_on
from arnold.pipelines.megaplan.calibration.ledger import (
    CapabilityClaim,
    EvaluandRef,
    ModelIdentity,
    filter_shared_claims,
    project_tier_models_if_enabled,
    query_route_if_enabled,
    route,
)


@pytest.fixture
def sample_ref() -> EvaluandRef:
    return EvaluandRef(
        piece_version="piece-v1",
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="inputs-v1",
    )


def test_calibration_query_route_flag_is_exact_and_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    monkeypatch.delenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", raising=False)
    assert calibration_query_route_on() is False

    monkeypatch.setenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", "0")
    assert calibration_query_route_on() is False

    monkeypatch.setenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", "true")
    assert calibration_query_route_on() is False

    monkeypatch.setenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", "1")
    assert calibration_query_route_on() is True


def test_route_uses_tier_4_fallback_for_unseen_class() -> None:
    suggestion = route(
        "brand-new-capability",
        claims=[],
        tier_models={"execute": {"4": "codex:high"}},
        default_tier=4,
    )

    assert suggestion.tier_spec == "codex:high"
    assert suggestion.exploration is False
    assert suggestion.reason == "greedy (no claims)"


def test_zero_exploration_budget_never_emits_off_policy_route(
    sample_ref: EvaluandRef,
) -> None:
    claims = [
        CapabilityClaim(
            outcome=sample_ref,
            task_signature="sig",
            model_identity="model-a",
            predicted_tier=2,
            timestamp=10_000.0,
        ),
        CapabilityClaim(
            outcome=sample_ref,
            task_signature="sig",
            model_identity="model-b",
            predicted_tier=2,
            timestamp=9_900.0,
        ),
    ]

    suggestion = route(
        "sig",
        claims=claims,
        tier_models={"execute": {"2": "claude:medium", "5": "codex:high"}},
        exploration_budget=0.0,
        seed=7,
        now=10_000.0,
    )

    assert suggestion.tier_spec == "claude:medium"
    assert suggestion.exploration is False
    assert suggestion.counterfactual_tag is None


def test_route_confidence_drops_when_fresh_claims_conflict(
    sample_ref: EvaluandRef,
) -> None:
    consensus = route(
        "sig",
        claims=[
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="sig",
                routed_model="model-a",
                predicted_tier=2,
                recorded_at=10_000.0,
            ),
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="sig",
                routed_model="model-b",
                predicted_tier=2,
                recorded_at=9_950.0,
            ),
        ],
        tier_models={"execute": {"2": "claude:medium", "4": "codex:high"}},
        now=10_000.0,
    )
    conflicting = route(
        "sig",
        claims=[
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="sig",
                routed_model="model-a",
                predicted_tier=2,
                recorded_at=10_000.0,
            ),
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="sig",
                routed_model="model-b",
                predicted_tier=4,
                recorded_at=9_950.0,
            ),
        ],
        tier_models={"execute": {"2": "claude:medium", "4": "codex:high"}},
        now=10_000.0,
    )

    assert consensus.tier_spec == "claude:medium"
    assert conflicting.projected_tier == 3
    assert conflicting.tier_spec is None
    assert conflicting.confidence < consensus.confidence


def test_route_uses_recorded_at_for_decay_with_canonical_claims(
    sample_ref: EvaluandRef,
) -> None:
    """``route()`` decays on ``recorded_at`` when claims use canonical fields."""
    now = 10_000.0
    half = 3600.0
    claims = [
        CapabilityClaim(
            outcome=sample_ref,
            task_signature="sig",
            routed_model=ModelIdentity("fresh-model"),
            predicted_tier=2,
            recorded_at=now,
        ),
        CapabilityClaim(
            outcome=sample_ref,
            task_signature="sig",
            routed_model=ModelIdentity("stale-model"),
            predicted_tier=5,
            recorded_at=now - (10 * half),
        ),
    ]
    suggestion = route(
        "sig",
        claims=claims,
        tier_models={"execute": {"2": "claude:medium", "5": "codex:high"}},
        half_life_seconds=half,
        now=now,
    )
    # Fresh claim (tier 2) dominates stale claim (tier 5) after decay
    assert suggestion.tier_spec == "claude:medium"
    assert suggestion.projected_tier == 2


def test_positive_exploration_budget_is_deterministic_and_tagged(
    sample_ref: EvaluandRef,
) -> None:
    claims = [
        CapabilityClaim(
            outcome=sample_ref,
            task_signature="sig",
            model_identity="model-a",
            predicted_tier=2,
            timestamp=10_000.0,
        )
    ]
    tier_models = {
        "execute": {
            "1": "hermes:deepseek:deepseek-v4-flash",
            "2": "claude:medium",
            "5": "codex:high",
        }
    }

    first = route(
        "sig",
        claims=claims,
        tier_models=tier_models,
        exploration_budget=1.0,
        seed=23,
        now=10_000.0,
    )
    second = route(
        "sig",
        claims=claims,
        tier_models=tier_models,
        exploration_budget=1.0,
        seed=23,
        now=10_000.0,
    )

    assert first.exploration is True
    assert first.counterfactual_tag is not None
    assert first.tier_spec != "claude:medium"
    assert first.counterfactual_tag == second.counterfactual_tag
    assert first.tier_spec == second.tier_spec
    assert ":greedy=2:" in first.counterfactual_tag


def test_seeded_exploration_is_stable_across_processes() -> None:
    script = """
import json
from arnold.pipelines.megaplan.calibration.ledger import CapabilityClaim, EvaluandRef, route
ref = EvaluandRef(piece_version='p', judge_version='j', rubric_version='r', input_set_hash='i')
claim = CapabilityClaim(outcome=ref, task_signature='sig', model_identity='model-a', predicted_tier=2, timestamp=10000.0)
s = route('sig', claims=[claim], tier_models={'execute': {'1': 'flash', '2': 'medium', '5': 'high'}}, exploration_budget=1.0, seed=23, now=10000.0)
print(json.dumps({'tier_spec': s.tier_spec, 'tag': s.counterfactual_tag}, sort_keys=True))
"""
    outputs = [
        subprocess.check_output([sys.executable, "-c", script], text=True).strip()
        for _ in range(2)
    ]
    assert json.loads(outputs[0]) == json.loads(outputs[1])


def test_cost_pressured_claims_are_excluded_from_shared_aggregation(
    sample_ref: EvaluandRef,
) -> None:
    flagged = CapabilityClaim(
        outcome=sample_ref,
        task_signature="sig",
        model_identity="flagged-model",
        predicted_tier=1,
        low_confidence_signal=True,
        verifier_tier="1",
        timestamp=10_000.0,
    )
    clean = CapabilityClaim(
        outcome=sample_ref,
        task_signature="sig",
        model_identity="clean-model",
        predicted_tier=4,
        timestamp=10_000.0,
    )

    shared = filter_shared_claims([flagged, clean])
    assert shared == (clean,)

    suggestion = route(
        "sig",
        claims=[flagged, clean],
        tier_models={"execute": {"1": "hermes:deepseek:deepseek-v4-pro", "4": "claude:medium"}},
        now=10_000.0,
    )

    assert suggestion.tier_spec == "claude:medium"
    assert "1 claims" in (suggestion.reason or "")


def test_calibration_wrappers_return_none_when_flag_off_or_projection_unusable(
    monkeypatch: pytest.MonkeyPatch,
    sample_ref: EvaluandRef,
) -> None:
    monkeypatch.delenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", raising=False)

    assert project_tier_models_if_enabled([], {"execute": {4: "claude:medium"}}) is None
    assert query_route_if_enabled(
        "sig",
        claims=[],
        tier_models={"execute": {"4": "claude:medium"}},
    ) is None

    monkeypatch.setenv("MEGAPLAN_CALIBRATION_QUERY_ROUTE", "1")

    assert project_tier_models_if_enabled([], None) is None
    assert query_route_if_enabled("sig", claims=[], tier_models=None) is None

    suggestion = query_route_if_enabled(
        "sig",
        claims=[
            CapabilityClaim(
                outcome=sample_ref,
                task_signature="sig",
                model_identity="model-a",
                predicted_tier=4,
                timestamp=10_000.0,
            )
        ],
        tier_models={"execute": {"4": "claude:medium"}},
        now=10_000.0,
    )

    assert suggestion is not None
    assert suggestion.tier_spec == "claude:medium"

    projected = project_tier_models_if_enabled([], {"execute": {4: "claude:medium"}})
    assert projected == {"execute": {"4": "claude:medium"}}


# ---------------------------------------------------------------------------
# Flag-off characterization — TOML routing surfaces unchanged
# ---------------------------------------------------------------------------


def test_flag_off_compute_batch_complexity_unchanged() -> None:
    """``compute_batch_complexity`` returns max task complexity (TOML path).

    The calibration query route flag does not affect this pure function —
    it must continue to return the expected fail-safe and max-of-complexities
    behaviour regardless of ``MEGAPLAN_CALIBRATION_QUERY_ROUTE``.
    """
    from arnold.pipelines.megaplan._core import compute_batch_complexity

    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "complexity": 2,
                "complexity_justification": "Simple.",
                "depends_on": [],
            },
            {
                "id": "T2",
                "complexity": 4,
                "complexity_justification": "Complex.",
                "depends_on": ["T1"],
            },
        ]
    }

    # Max complexity in the batch
    assert compute_batch_complexity(finalize_data, ["T1", "T2"]) == 4

    # Single task
    assert compute_batch_complexity(finalize_data, ["T1"]) == 2

    # Missing task → fail-safe 5
    assert compute_batch_complexity(finalize_data, ["T99"]) == 5

    # Empty batch → fail-safe 5
    assert compute_batch_complexity({"tasks": []}, []) == 5

    # Missing complexity → fail-safe 5
    assert (
        compute_batch_complexity(
            {"tasks": [{"id": "T1", "complexity_justification": "ok"}]},
            ["T1"],
        )
        == 5
    )

    # Out-of-range complexity → fail-safe 5
    assert (
        compute_batch_complexity(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "complexity": 99,
                        "complexity_justification": "Too high.",
                    }
                ]
            },
            ["T1"],
        )
        == 5
    )


def test_flag_off_resolve_dispatch_spec_unchanged() -> None:
    """``resolve_dispatch_spec`` resolves tier ordinal → spec (TOML path).

    This function drills from a complexity integer to a tier spec string
    via the TOML-derived ``tier_models`` mapping.  The calibration route
    flag does not affect it.
    """
    from arnold.pipelines.megaplan._core import resolve_dispatch_spec

    tier_models = {
        "execute": {
            1: "hermes:openai/gpt-4.1-mini",
            2: "hermes:openai/gpt-4.1-mini",
            3: "hermes:openai/gpt-4.1",
            4: "hermes:openai/gpt-4.1",
            5: "hermes:openai/gpt-4.5-preview",
        }
    }

    # Known ordinal returns the spec
    assert (
        resolve_dispatch_spec(tier_models, "execute", 1)
        == "hermes:openai/gpt-4.1-mini"
    )
    assert (
        resolve_dispatch_spec(tier_models, "execute", 5)
        == "hermes:openai/gpt-4.5-preview"
    )

    # Missing ordinal returns caller default
    assert (
        resolve_dispatch_spec(tier_models, "execute", 99, default="fallback")
        == "fallback"
    )

    # Missing ordinal with no default returns None
    assert resolve_dispatch_spec(tier_models, "execute", 99) is None

    # Missing slot returns default
    assert (
        resolve_dispatch_spec(tier_models, "nonexistent", 3, default="fb")
        == "fb"
    )

    # None tier_models returns default
    assert resolve_dispatch_spec(None, "execute", 3, default="fb") == "fb"


def test_flag_off_tier_map_get_routing_unchanged() -> None:
    """Full TOML tier-routing chain: compute + lookup + spec resolution.

    Simulates the exact ``tier_map.get(compute_batch_complexity(...))``
    pattern used in ``batch.py`` for per-batch tier routing.  When the
    calibration route flag is off this chain must produce the same spec
    as it always has.
    """
    from arnold.pipelines.megaplan._core import compute_batch_complexity, resolve_dispatch_spec

    # A realistic tier_map (matching the TOML profile shape)
    tier_map: dict[int, str] = {
        1: "hermes:openai/gpt-4.1-mini",
        2: "hermes:openai/gpt-4.1-mini",
        3: "hermes:openai/gpt-4.1",
        4: "hermes:openai/gpt-4.1",
        5: "hermes:openai/gpt-4.5-preview",
    }

    finalize_data: dict = {
        "tasks": [
            {
                "id": "T1",
                "complexity": 3,
                "complexity_justification": "Moderate risk.",
                "depends_on": [],
            },
            {
                "id": "T2",
                "complexity": 1,
                "complexity_justification": "Trivial.",
                "depends_on": [],
            },
        ]
    }

    # The TOML tier-routing chain
    complexity = compute_batch_complexity(finalize_data, ["T1", "T2"])
    tier_spec = tier_map.get(complexity)

    assert complexity == 3  # max(3, 1)
    assert tier_spec == "hermes:openai/gpt-4.1"

    # Verify spec resolution produces a non-None result
    resolved = resolve_dispatch_spec(
        {"execute": tier_map}, "execute", complexity
    )
    assert resolved == tier_spec


def test_flag_off_finalize_complexity_validation_unchanged(
    tmp_path: Path,
) -> None:
    """Finalize complexity validation enforces 1..5 (TOML path).

    ``_validate_finalize_payload`` rejects tasks with missing, non-integer,
    boolean, or out-of-range complexity.  The calibration query route flag
    does not affect this validation — it must remain unchanged.
    """
    from arnold.pipelines.megaplan.handlers.finalize import _validate_finalize_payload
    from arnold.pipelines.megaplan.workers import WorkerResult

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    state: dict = {
        "name": "test",
        "idea": "test",
        "current_state": "gated",
        "iteration": 1,
        "config": {"project_dir": str(tmp_path), "mode": "code"},
        "plan_versions": [
            {"version": 1, "file": "plan_v1.md", "hash": "sha256:test"}
        ],
        "history": [],
        "sessions": {},
        "meta": {},
    }
    task_base = {
        "id": "T1",
        "description": "Ship the change.",
        "depends_on": [],
        "status": "pending",
        "executor_notes": "",
        "files_changed": [],
        "commands_run": [],
        "evidence_files": [],
        "reviewer_verdict": "",
    }

    def _try_validate(complexity: object) -> str | None:
        """Return error message or None if validation passes."""
        task = {**task_base, "complexity": complexity, "complexity_justification": "ok"}
        payload = {"tasks": [task], "sense_checks": [], "watch_items": []}
        worker = WorkerResult(
            payload=payload,
            raw_output="test",
            duration_ms=1,
            cost_usd=0.0,
            session_id="test",
        )
        try:
            _validate_finalize_payload(plan_dir, state, worker)
            return None
        except Exception as exc:
            return str(exc)

    # Valid complexities 1-5 pass
    for c in (1, 2, 3, 4, 5):
        assert _try_validate(c) is None, f"Complexity {c} should be valid"

    # Out-of-range fails
    for c in (0, 6, 99):
        err = _try_validate(c)
        assert err is not None, f"Complexity {c} should be rejected"
        assert "1..5" in err.lower()

    # Missing, non-integer, boolean fail
    for c in (None, "medium", True, False, 3.5):
        err = _try_validate(c)
        assert err is not None, f"Complexity {c!r} should be rejected"

    # Missing justification fails
    task_no_just = {**task_base, "complexity": 3}
    payload_no_just = {"tasks": [task_no_just], "sense_checks": [], "watch_items": []}
    worker_no_just = WorkerResult(
        payload=payload_no_just,
        raw_output="test",
        duration_ms=1,
        cost_usd=0.0,
        session_id="test",
    )
    with pytest.raises(Exception):
        _validate_finalize_payload(plan_dir, state, worker_no_just)
