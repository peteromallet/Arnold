from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from megaplan.calibration.ledger import (
    CapabilityClaim,
    EvaluandRef,
    ModelIdentity,
    _canonical_json,
    capability_class_prior,
    project_claimed_complexity,
    project_tier_models,
)
import megaplan.profiles as profiles_module
from megaplan.profiles import apply_profile_expansion


def _write_profiles(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _worker_args(**overrides: object) -> Namespace:
    data: dict[str, object] = {
        "agent": None,
        "confirm_self_review": False,
        "deepseek_provider": None,
        "ephemeral": False,
        "fresh": False,
        "hermes": None,
        "persist": False,
        "phase_model": [],
        "profile": None,
    }
    data.update(overrides)
    return Namespace(**data)


@pytest.fixture
def sample_ref() -> EvaluandRef:
    return EvaluandRef(
        piece_version="piece-v1",
        judge_version="judge-v1",
        rubric_version="rubric-v1",
        input_set_hash="inputs-v1",
    )


def test_half_life_down_weights_stale_claims(sample_ref: EvaluandRef) -> None:
    now = 10_000.0
    claims = [
        CapabilityClaim(
            outcome=sample_ref,
            task_signature="calibration.route.test",
            model_identity="model-fresh",
            predicted_tier=2,
            timestamp=now,
        ),
        CapabilityClaim(
            outcome=sample_ref,
            task_signature="calibration.route.test",
            model_identity="model-stale",
            predicted_tier=5,
            timestamp=now - (10 * 3600.0),
        ),
    ]

    projected = project_claimed_complexity(
        claims,
        now=now,
        half_life_seconds=3600.0,
    )

    assert projected == 2


def test_half_life_down_weights_stale_claims_canonical(sample_ref: EvaluandRef) -> None:
    """Same as above but uses canonical ``recorded_at`` and ``routed_model``."""
    now = 10_000.0
    claims = [
        CapabilityClaim(
            outcome=sample_ref,
            task_signature="calibration.route.test",
            routed_model=ModelIdentity("model-fresh"),
            predicted_tier=2,
            recorded_at=now,
        ),
        CapabilityClaim(
            outcome=sample_ref,
            task_signature="calibration.route.test",
            routed_model=ModelIdentity("model-stale"),
            predicted_tier=5,
            recorded_at=now - (10 * 3600.0),
        ),
    ]

    projected = project_claimed_complexity(
        claims,
        now=now,
        half_life_seconds=3600.0,
    )

    assert projected == 2


def test_unseen_capability_class_prior_defaults_to_tier_4() -> None:
    assert capability_class_prior(ModelIdentity("brand-new-capability")) == 4


def test_project_tier_models_matches_seeded_toml_after_canonical_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setattr(
        profiles_module,
        "config_dir",
        lambda home=None: home / ".config" / "megaplan" if home is not None else tmp_path / ".config" / "megaplan",
    )

    _write_profiles(
        project_dir / ".megaplan" / "profiles.toml",
        """
        [profiles.seeded]
        plan = "codex:low"

        [profiles.seeded.tier_models.execute]
        1 = "hermes:deepseek:deepseek-v4-flash"
        4 = "claude:medium"
        5 = "codex:high"

        [profiles.seeded.tier_models.review]
        4 = "claude:medium"
        """,
    )

    args = _worker_args(profile="seeded")
    apply_profile_expansion(args, project_dir)
    assert args.tier_models is not None

    expected = {
        phase: {str(tier): spec for tier, spec in tiers.items()}
        for phase, tiers in args.tier_models.items()
    }
    projected = project_tier_models([], args.tier_models)

    assert _canonical_json(projected) == _canonical_json(expected)
    assert json.loads(_canonical_json(projected)) == expected
