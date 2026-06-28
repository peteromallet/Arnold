from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from arnold_pipelines.megaplan.profiles.policy import apply_profile_expansion


def test_explicit_prep_phase_model_overrides_profile_prep_models(tmp_path: Path) -> None:
    args = Namespace(
        profile="partnered-5",
        phase_model=["prep=hermes:kimi:kimi-k2.7-code"],
        tier_models=None,
        vendor=None,
        critic=None,
        depth=None,
        deepseek_provider=None,
    )

    apply_profile_expansion(args, tmp_path)

    assert args.prep_models == {
        "triage": "hermes:kimi:kimi-k2.7-code",
        "fanout": "hermes:kimi:kimi-k2.7-code",
        "distill": "hermes:kimi:kimi-k2.7-code",
    }
