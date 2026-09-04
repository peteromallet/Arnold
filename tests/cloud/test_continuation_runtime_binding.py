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
    model_policy_sha,
    resolve_continuation_fixer_policy,
)
from arnold_pipelines.megaplan.cloud.fixer_prompt_policy import policy_sha
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


@pytest.mark.parametrize(
    "mode_rung",
    ("reactive_investigator", "reactive_mutator", "proactive", "l2"),
)
def test_continuation_fixer_policy_bypasses_legacy_flash_gate(mode_rung: str) -> None:
    """An explicit continuation pin must not inherit the legacy Flash gate."""
    row = resolve_continuation_fixer_policy(
        mode_rung, runtime_model_spec=CONTINUATION_FIXER_MODEL_SPEC
    )
    assert row.status == "default"
    assert row.agent_backend == "omp"
    assert row.provider_spec == "openrouter"
    assert row.model == "openrouter/meta/muse-spark-1.3-contributor"


def test_continuation_superfixer_requires_explicit_model(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.resident import subagent

    with pytest.raises(ValueError, match="explicit canonical model"):
        subagent.launch_superfixer_proactive_managed(
            task="x", project_dir=str(_project(tmp_path))
        )


def test_continuation_superfixer_probes_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from arnold_pipelines.megaplan.cloud import worker_dispatch
    from arnold_pipelines.megaplan.resident import subagent

    observed: list[tuple[str, str]] = []

    def fake_probe(provider: str, model: str) -> dict[str, str]:
        observed.append((provider, model))
        return {"identity": f"{provider}/{model}", "model": model, "digest": "catalog"}

    monkeypatch.setattr(worker_dispatch, "resolve_omp_live_membership", fake_probe)
    monkeypatch.setattr(
        subagent,
        "launch_managed_subagent_detached",
        lambda **_kwargs: SimpleNamespace(run_id="continuation-run"),
    )
    result = subagent.launch_superfixer_proactive_managed(
        task="x",
        project_dir=str(_project(tmp_path)),
        model_spec=CONTINUATION_RUNTIME_MODEL_SPEC,
    )
    assert result.run_id == "continuation-run"
    assert observed == [("openrouter", "meta/muse-spark-1.3-contributor")]


def test_continuation_receipt_binds_reasoning_and_effective_policy(tmp_path: Path) -> None:
    route = resolve_babysitter_routing({}, project_dir=_project(tmp_path))
    ctx = {
        "session": "continuation",
        "occurrence": "occurrence",
        "run_id": "run",
        "run_root": tmp_path,
        "plan": "c2",
        "run_kind": "chain",
        "workspace": str(tmp_path),
        "remote_spec": "",
        "mode": "superfixer",
        "model": CONTINUATION_RUNTIME_MODEL_SPEC,
        "reasoning_effort": "high",
        "routing": route,
        "launched_at": "2026-09-04T00:00:00Z",
    }
    payload = babysitter_launch._receipt_payload(ctx, status="running")
    assert payload["reasoning_effort"] == "high"
    assert payload["policy_sha"] == policy_sha()
    assert payload["model_policy_sha"] == model_policy_sha(
        continuation_model_spec=CONTINUATION_FIXER_MODEL_SPEC
    )
    assert payload["model_policy_sha"] != model_policy_sha()


def test_continuation_babysitter_requires_live_probe_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.cloud import worker_dispatch

    observed: list[tuple[str, str]] = []

    def fake_probe(provider: str, model: str) -> dict[str, str]:
        observed.append((provider, model))
        return {
            "identity": f"{provider}/{model}",
            "model": model,
            "digest": "catalog",
            "observed_at": "2026-09-04T00:00:00Z",
        }

    monkeypatch.setattr(worker_dispatch, "resolve_omp_live_membership", fake_probe)
    ctx = {
        "engine_root": _project(tmp_path),
        "reasoning_effort": "high",
    }
    babysitter_launch._require_continuation_provider_probe(ctx)
    assert observed == [("openrouter", "meta/muse-spark-1.3-contributor")]
    assert ctx["provider_probe"]["spec"] == CONTINUATION_RUNTIME_MODEL_SPEC
    assert ctx["provider_probe"]["catalog_digest"] == "catalog"


def test_watchdog_babysitter_off_is_absolute_dispatch_gate() -> None:
    wrapper = (
        Path(__file__).resolve().parents[2]
        / "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog"
    ).read_text(encoding="utf-8")
    start = wrapper.index("babysitter_policy_dispatch() {")
    off_start = wrapper.index('if [[ "$mode" == "off" ]]', start)
    off_end = wrapper.index("\n  fi", off_start)
    off_clause = wrapper[off_start:off_end]
    assert "return 0" in off_clause
    assert "babysitter_parked_chain_stall" not in off_clause


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
