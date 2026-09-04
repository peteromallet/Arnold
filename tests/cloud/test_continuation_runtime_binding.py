from __future__ import annotations

import json
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

    launch_kwargs: dict[str, object] = {}
    monkeypatch.setattr(
        worker_dispatch,
        "ensure_continuation_provider_probe",
        lambda _project, spec: {
            "spec": spec,
            "catalog_digest": "catalog",
            "probe_session": "probe-session",
            "output": "NBF_MUSE_PROBE_OK",
            "output_sha256": "output-sha",
            "profile_sha256": "profile-sha",
            "observed_at": "2026-09-04T00:00:00Z",
        },
    )
    def fake_launch(**kwargs):
        launch_kwargs.update(kwargs)
        return SimpleNamespace(run_id="continuation-run")

    monkeypatch.setattr(subagent, "launch_managed_subagent_detached", fake_launch)
    result = subagent.launch_superfixer_proactive_managed(
        task="x",
        project_dir=str(_project(tmp_path)),
        model_spec=CONTINUATION_RUNTIME_MODEL_SPEC,
    )
    assert result.run_id == "continuation-run"
    assert launch_kwargs["provider_probe"]["catalog_digest"] == "catalog"  # type: ignore[index]


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

    monkeypatch.setattr(
        worker_dispatch,
        "ensure_continuation_provider_probe",
        lambda _project, spec: {
            "spec": spec,
            "catalog_digest": "catalog",
            "probe_session": "probe-session",
            "output": "NBF_MUSE_PROBE_OK",
            "output_sha256": "output-sha",
            "profile_sha256": "profile-sha",
            "observed_at": "2026-09-04T00:00:00Z",
        },
    )
    ctx = {
        "engine_root": _project(tmp_path),
        "reasoning_effort": "high",
    }
    babysitter_launch._require_continuation_provider_probe(ctx)
    assert ctx["provider_probe"]["output"] == "NBF_MUSE_PROBE_OK"
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


def test_tiebreaker_resolved_mode_preserves_omp_effort(tmp_path: Path) -> None:
    from argparse import Namespace

    from arnold_pipelines.megaplan.prompts.tiebreaker_orchestrator import _build_resolved

    args = Namespace(
        agent=None,
        phase_model=[
            f"tiebreaker_researcher={CONTINUATION_RUNTIME_MODEL_SPEC}"
        ],
        profile=None,
        vendor=None,
        depth=None,
        critic=None,
        fresh=False,
        persist=False,
        ephemeral=True,
    )
    resolved = _build_resolved(
        args,
        "tiebreaker_researcher",
        project_dir=_project(tmp_path),
    )
    assert resolved.model == "openrouter/meta/muse-spark-1.3-contributor"
    assert resolved.effort == "high"
    assert resolved.resolved_model == "openrouter/meta/muse-spark-1.3-contributor"


def test_continuation_rejects_conflicting_cli_agent_override(tmp_path: Path) -> None:
    from argparse import Namespace

    from arnold_pipelines.megaplan.profiles import validate_continuation_agent_override

    with pytest.raises(CliError, match="rejects explicit agent override"):
        validate_continuation_agent_override(
            _project(tmp_path),
            Namespace(agent="codex", phase_model=[]),
            "tiebreaker_researcher",
        )


def test_continuation_rejects_noncanonical_fallback_entry(tmp_path: Path) -> None:
    from argparse import Namespace

    from arnold_pipelines.megaplan.fallback_chains import (
        FallbackSpecChain,
        encode_phase_model_value,
    )
    from arnold_pipelines.megaplan.profiles import validate_continuation_agent_override

    phase_model = encode_phase_model_value(
        "tiebreaker_researcher",
        FallbackSpecChain((CONTINUATION_RUNTIME_MODEL_SPEC, "omp:deepseek/deepseek-v4-pro")),
    )
    with pytest.raises(CliError, match="noncanonical phase-model chain"):
        validate_continuation_agent_override(
            _project(tmp_path),
            Namespace(agent=None, phase_model=[phase_model]),
            "tiebreaker_researcher",
        )


def test_exact_muse_probe_receipt_is_replayable_and_identity_bound(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from arnold_pipelines.megaplan.cloud.worker_dispatch import (
        CONTINUATION_PROVIDER_PROBE_OUTPUT,
        ensure_continuation_provider_probe,
    )

    project = _project(tmp_path)
    calls: list[list[str]] = []

    def runner(argv, **_kwargs):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout=CONTINUATION_PROVIDER_PROBE_OUTPUT + "\n", stderr="")

    def membership(_provider: str, _model: str) -> dict[str, str]:
        return {
            "identity": "openrouter/meta/muse-spark-1.3-contributor",
            "digest": "catalog-digest",
        }
    first = ensure_continuation_provider_probe(
        project,
        CONTINUATION_RUNTIME_MODEL_SPEC,
        runner=runner,
        membership_probe=membership,
        clock=lambda: 1_000.0,
    )
    second = ensure_continuation_provider_probe(
        project,
        CONTINUATION_RUNTIME_MODEL_SPEC,
        runner=lambda *_args, **_kwargs: pytest.fail("valid receipt must replay without a provider call"),
        membership_probe=membership,
        clock=lambda: 1_001.0,
    )
    assert first == second
    assert len(calls) == 1
    assert calls[0][0:3] == ["omp", "-p", "--no-session"]
    assert second["probe_session"]
    assert second["reasoning_effort"] == "high"
    assert second["output"] == CONTINUATION_PROVIDER_PROBE_OUTPUT

    receipt_path = project / ".megaplan" / "continuation-provider-probe.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt.pop("catalog_digest")
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    ensure_continuation_provider_probe(
        project,
        CONTINUATION_RUNTIME_MODEL_SPEC,
        runner=runner,
        membership_probe=membership,
        clock=lambda: 1_002.0,
    )
    assert len(calls) == 2
