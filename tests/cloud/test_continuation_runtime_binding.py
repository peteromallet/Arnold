from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.babysitter.routing import (
    resolve_babysitter_routing,
)
from arnold_pipelines.megaplan.cloud.babysitter import launch as babysitter_launch
from arnold_pipelines.megaplan.cloud.fixer_model_policy import (
    CONTINUATION_FIXER_MODEL_SPEC,
    PolicyError,
    resolve_continuation_fixer_policy,
)
from arnold_pipelines.megaplan.cloud.preflight import (
    resolve_cloud_chain_runtime_dependencies,
)
from arnold_pipelines.megaplan.chain.spec import load_spec
from arnold_pipelines.megaplan.profiles import (
    CONTINUATION_RUNTIME_MODEL_SPEC,
    resolve_continuation_runtime_model,
)
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers.omp import validate_omp_catalog_model
from arnold_pipelines.megaplan.workers.omp import _verify_omp_session_binding


PROFILE_TEXT = """\
[profiles.all-muse-spark-1-3-contributor]
plan = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
prep = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
critique = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
critique_evaluator = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
revise = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
gate = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
finalize = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
execute = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
feedback = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
loop_plan = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
loop_execute = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
review = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
tiebreaker_researcher = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
tiebreaker_challenger = "omp:openrouter/meta/muse-spark-1.3-contributor:high"
"""


def _project(tmp_path: Path, text: str = PROFILE_TEXT) -> Path:
    (tmp_path / ".megaplan").mkdir()
    (tmp_path / ".megaplan" / "profiles.toml").write_text(text, encoding="utf-8")
    return tmp_path


def test_continuation_profile_is_one_strict_binding(tmp_path: Path) -> None:
    assert resolve_continuation_runtime_model(_project(tmp_path)) == CONTINUATION_RUNTIME_MODEL_SPEC


def test_continuation_profile_rejects_partial_or_conflicting_values(tmp_path: Path) -> None:
    project = _project(tmp_path, PROFILE_TEXT.replace(
        "review = \"omp:openrouter/meta/muse-spark-1.3-contributor:high\"",
        "review = \"omp:deepseek/deepseek-v4-flash\"",
        1,
    ))
    with pytest.raises(CliError, match="must be exactly"):
        resolve_continuation_runtime_model(project)


def test_catalog_and_babysitter_use_muse_13_high(tmp_path: Path) -> None:
    assert validate_omp_catalog_model(
        "openrouter", "meta/muse-spark-1.3-contributor"
    ) == "openrouter/meta/muse-spark-1.3-contributor"
    route = resolve_babysitter_routing({}, project_dir=_project(tmp_path))
    assert route.controller_model == CONTINUATION_RUNTIME_MODEL_SPEC
    assert route.investigator_model == CONTINUATION_RUNTIME_MODEL_SPEC


def test_babysitter_rejects_ambient_conflict_for_continuation(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="conflicts"):
        resolve_babysitter_routing(
            {"ARNOLD_BABYSITTER_OMP_MODEL": "omp:deepseek/deepseek-v4-flash"},
            project_dir=_project(tmp_path),
        )


def test_babysitter_managed_spec_carries_high_canonical_model(tmp_path: Path) -> None:
    project = _project(tmp_path)
    route = resolve_babysitter_routing({}, project_dir=project)
    goal = tmp_path / "goal.md"
    goal.write_text("continuation", encoding="utf-8")
    ctx = {
        "engine_root": Path(__file__).resolve().parents[2],
        "run_root": tmp_path / "run",
        "session": "continuation",
        "occurrence": "occurrence",
        "run_id": "run",
        "plan": "c2",
        "routing": route,
        "model": route.controller_model,
        "reasoning_effort": "high",
        "difficulty": 5,
        "remote_spec": "",
        "workspace": str(project),
        "mode": "superfixer",
    }
    spec = babysitter_launch._managed_spec(
        ctx, goal_path=goal, identity_key="identity"
    )
    assert spec.model == CONTINUATION_RUNTIME_MODEL_SPEC
    assert spec.reasoning_effort == "high"
    assert f"--model={CONTINUATION_RUNTIME_MODEL_SPEC}" in spec.argv


def test_continuation_fixer_policy_requires_exact_binding() -> None:
    row = resolve_continuation_fixer_policy(
        "l3_orchestrator", runtime_model_spec=CONTINUATION_FIXER_MODEL_SPEC
    )
    assert row.agent_backend == "omp"
    assert row.provider_spec == "openrouter"
    assert row.model == "openrouter/meta/muse-spark-1.3-contributor"
    with pytest.raises(PolicyError, match="binding"):
        resolve_continuation_fixer_policy(
            "l3_orchestrator", runtime_model_spec="omp:deepseek/deepseek-v4-pro"
        )


def test_preflight_exposes_all_continuation_roles() -> None:
    repo = Path(__file__).resolve().parents[2]
    chain = load_spec(
        repo / ".megaplan/initiatives/native-build-forward-continuation-20260904/chain.yaml"
    )
    result = resolve_cloud_chain_runtime_dependencies(chain, project_dir=repo)
    binding = result["runtime_model_binding"]
    assert binding["spec"] == CONTINUATION_RUNTIME_MODEL_SPEC
    assert binding["babysitter_enabled"] is False
    assert {value["spec"] for value in binding["roles"].values()} == {
        CONTINUATION_RUNTIME_MODEL_SPEC
    }


def test_omp_readback_rejects_effective_thinking_mismatch() -> None:
    class Client:
        def get_state(self):
            return type(
                "State",
                (),
                {
                    "model": type(
                        "Model", (),
                        {
                            "provider": "openrouter",
                            "id": "meta/muse-spark-1.3-contributor",
                        },
                    )(),
                    "thinking_level": None,
                },
            )()

    with pytest.raises(CliError, match="thinking level"):
        _verify_omp_session_binding(
            Client(),
            provider="openrouter",
            model_id="meta/muse-spark-1.3-contributor",
            thinking="high",
        )
