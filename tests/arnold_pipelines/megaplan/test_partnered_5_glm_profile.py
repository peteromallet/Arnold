from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.profiles import load_profile_metadata, load_profiles
from arnold_pipelines.megaplan.profiles.policy import apply_profile_expansion


GLM_SPEC = "hermes:zhipu:glm-5.2"
FORBIDDEN_GPT_TOKENS = ("codex", "openai", "gpt")


def _is_gpt_spec(spec: str) -> bool:
    lowered = spec.lower()
    return any(token in lowered for token in FORBIDDEN_GPT_TOKENS)


def _replace_gpt_specs(value: Any) -> Any:
    if isinstance(value, str):
        return GLM_SPEC if _is_gpt_spec(value) else value
    if isinstance(value, list):
        return [_replace_gpt_specs(item) for item in value]
    if isinstance(value, dict):
        return {key: _replace_gpt_specs(item) for key, item in value.items()}
    return value


def _flatten_specs(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [spec for item in value for spec in _flatten_specs(item)]
    if isinstance(value, dict):
        return [spec for item in value.values() for spec in _flatten_specs(item)]
    return []


def _replace_phase_model_gpt_specs(entries: list[str]) -> list[str]:
    replaced: list[str] = []
    for entry in entries:
        phase, spec = entry.split("=", 1)
        replaced.append(f"{phase}={_replace_gpt_specs(spec)}")
    return replaced


def _profile_args(profile: str) -> Namespace:
    return Namespace(
        profile=profile,
        phase_model=[],
        tier_models=None,
        vendor=None,
        critic=None,
        depth=None,
        deepseek_provider=None,
    )


def test_partnered_5_glm_is_exact_gpt_replacement_of_partnered_5(
    tmp_path: Path,
) -> None:
    profiles = load_profiles(project_dir=tmp_path)
    metadata = load_profile_metadata(project_dir=tmp_path)

    base = profiles["partnered-5"]
    glm = profiles["partnered-5-glm"]
    base_metadata = metadata["partnered-5"]
    glm_metadata = metadata["partnered-5-glm"]

    assert glm == _replace_gpt_specs(base)
    assert glm_metadata["adaptive_critique"] == base_metadata["adaptive_critique"]
    assert glm_metadata["tier_models"] == _replace_gpt_specs(
        base_metadata["tier_models"]
    )


def test_partnered_5_glm_resolution_contains_no_gpt_route(
    tmp_path: Path,
) -> None:
    args = _profile_args("partnered-5-glm")

    apply_profile_expansion(args, tmp_path)

    resolved_specs = [
        *_flatten_specs(args.phase_model),
        *_flatten_specs(args.tier_models),
        *_flatten_specs(args.prep_models),
    ]
    assert resolved_specs
    assert all(not _is_gpt_spec(spec) for spec in resolved_specs)
    assert GLM_SPEC in resolved_specs


def test_partnered_5_glm_preserves_non_gpt_phase_and_tier_routes(
    tmp_path: Path,
) -> None:
    base_args = _profile_args("partnered-5")
    glm_args = _profile_args("partnered-5-glm")

    apply_profile_expansion(base_args, tmp_path)
    apply_profile_expansion(glm_args, tmp_path)

    assert glm_args.phase_model == _replace_phase_model_gpt_specs(base_args.phase_model)
    assert glm_args.tier_models == _replace_gpt_specs(base_args.tier_models)
    assert glm_args.prep_models == _replace_gpt_specs(base_args.prep_models)
