from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from arnold_pipelines.megaplan.profiles.policy import apply_profile_expansion
from arnold_pipelines.megaplan.types import parse_agent_spec


GLM_SPEC = "hermes:zhipu:glm-5.2"
GLM_PHASES = {
    "critique",
    "critique_evaluator",
    "execute",
    "feedback",
    "loop_execute",
    "review",
    "tiebreaker_researcher",
    "tiebreaker_challenger",
}


def test_all_open_persists_provider_qualified_glm_routes(
    tmp_path: Path,
) -> None:
    args = Namespace(
        profile="all-open",
        phase_model=[],
        tier_models=None,
        vendor=None,
        critic=None,
        depth=None,
        deepseek_provider=None,
    )

    apply_profile_expansion(args, tmp_path)

    phase_models = {
        phase: spec
        for phase, spec in (
            entry.split("=", 1)
            for entry in args.phase_model
        )
    }
    assert GLM_PHASES <= phase_models.keys()
    for phase in GLM_PHASES:
        spec = phase_models[phase]
        assert spec == GLM_SPEC
        parsed = parse_agent_spec(spec)
        assert parsed.agent == "hermes"
        assert parsed.model == "zhipu:glm-5.2"
