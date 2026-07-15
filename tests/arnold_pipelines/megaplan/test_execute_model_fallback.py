from __future__ import annotations

import argparse
import subprocess
import tomllib
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.execute.batch import (
    _active_step_fallback_fields,
    normalize_tier_map,
)
from arnold_pipelines.megaplan.execute_attempt_safety import WorkspaceSnapshot
from arnold_pipelines.megaplan.fallback_chains import ExecuteFallbackMutationUnsafe
from arnold_pipelines.megaplan.handlers.execute import _extract_execute_tier_map
from arnold_pipelines.megaplan.receipts import build_receipt
from arnold_pipelines.megaplan.types import AgentMode, CliError
from arnold_pipelines.megaplan.workers import WorkerResult, run_step_with_worker


CHAIN = (
    "hermes:zhipu:glm-5.2",
    "hermes:fireworks:accounts/fireworks/models/glm-5p2",
    "codex:gpt-5.4",
)


def _git_repo(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Megaplan Test"], cwd=path, check=True)
    (path / "tracked.txt").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=path, check=True)
    return path


def _mode() -> AgentMode:
    return AgentMode(
        agent="hermes",
        mode="persistent",
        refreshed=False,
        model="zhipu:glm-5.2",
        resolved_model="zhipu:glm-5.2",
    )


def _state(repo: Path) -> dict:
    return {"name": "fallback-fixture", "config": {"project_dir": str(repo)}, "sessions": {}}


def _retryable(code: str, *, safe: bool = True) -> CliError:
    return CliError(
        code,
        f"deterministic {code}",
        extra={
            "progress_reason": code,
            "retryable": True,
            "mutation_safe_to_retry": safe,
        },
    )


def test_original_partnered_5_fixture_preserves_ordered_execute_route() -> None:
    profile_path = (
        Path(__file__).parents[3]
        / "arnold_pipelines/megaplan/profiles/partnered-5.toml"
    )
    raw = tomllib.loads(profile_path.read_text(encoding="utf-8"))
    tier_models = raw["profiles"]["partnered-5"]["tier_models"]

    extracted = _extract_execute_tier_map(tier_models)
    normalized = normalize_tier_map(extracted)

    assert extracted is not None
    assert normalized is not None
    assert extracted[7].specs == CHAIN
    assert normalized[7].specs == CHAIN
    assert extracted[8].specs == CHAIN


def test_tier_route_boundary_migrates_scalars_and_fails_closed_on_ambiguity() -> None:
    migrated = normalize_tier_map({"1": "codex:gpt-5.4"})
    assert migrated is not None
    assert migrated[1].specs == ("codex:gpt-5.4",)

    with pytest.raises(ValueError, match="duplicated"):
        normalize_tier_map({1: "codex:gpt-5.4", "1": "codex:gpt-5.5"})
    with pytest.raises(ValueError, match="boolean"):
        _extract_execute_tier_map({"execute": {True: "codex:gpt-5.4"}})


def test_tier_route_translates_receipt_fields_for_active_step() -> None:
    normalized = normalize_tier_map({7: CHAIN})
    assert normalized is not None

    fields = _active_step_fallback_fields(normalized[7])

    assert fields == {
        "configured_specs": list(CHAIN),
        "attempt_index": 0,
        "attempted_specs": [CHAIN[0]],
        "failed_attempt_reasons": [],
        "fallback_trigger": None,
    }
    assert "selected_spec_index" not in fields
    assert "selected_spec_total" not in fields


def test_execute_advances_zhipu_to_fireworks_to_codex_with_reasoned_receipt_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = _git_repo(tmp_path / "repo")
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    hermes_models: list[str | None] = []

    def fake_hermes(*args, **kwargs):
        hermes_models.append(kwargs.get("model"))
        if len(hermes_models) == 1:
            raise _retryable("slow_visible_output")
        raise _retryable("streaming_timeout")

    def fake_codex(*args, **kwargs):
        return WorkerResult(
            payload={"success": True, "result": "implemented"},
            raw_output="{}",
            duration_ms=3,
            cost_usd=0.0,
            model_actual="gpt-5.4",
        )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.hermes.run_hermes_step", fake_hermes
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers._impl.run_codex_step", fake_codex
    )

    cli_args = argparse.Namespace(
        phase_model=[], agent=None, hermes=None, profile="partnered-5"
    )
    state = _state(repo)
    worker, agent, _mode_name, _fresh = run_step_with_worker(
        "execute",
        state,
        plan_dir,
        cli_args,
        root=repo,
        resolved=_mode(),
        read_only=False,
        record_routing=False,
        ledger_configured_specs=CHAIN,
    )

    assert hermes_models == [
        "zhipu:glm-5.2",
        "fireworks:accounts/fireworks/models/glm-5p2",
    ]
    assert agent == "codex"
    assert worker.configured_specs == CHAIN
    assert worker.attempted_specs == CHAIN
    assert worker.attempt_index == 2
    assert worker.failed_attempt_reasons == (
        "slow_visible_output",
        "streaming_timeout",
    )
    assert worker.fallback_trigger == "streaming_timeout"
    assert worker.mutation_safety is not None
    assert worker.mutation_safety["safe"] is True
    assert [attempt["trigger"] for attempt in worker.mutation_safety["attempts"]] == [
        "slow_visible_output",
        "streaming_timeout",
    ]

    receipt = build_receipt(
        phase="execute",
        state=state,
        plan_dir=plan_dir,
        args=cli_args,
        worker=worker,
        agent=agent,
        mode="persistent",
        output_file="execution_batch_1.json",
        artifact_hash="sha256:fixture",
        verdict="success",
    )
    assert receipt["configured_specs"] == list(CHAIN)
    assert receipt["attempted_specs"] == list(CHAIN)
    assert receipt["failed_attempt_reasons"] == [
        "slow_visible_output",
        "streaming_timeout",
    ]
    assert receipt["fallback_trigger"] == "streaming_timeout"
    assert receipt["mutation_safety"]["safe"] is True


def test_execute_semantic_failure_is_not_eligible(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = _git_repo(tmp_path / "repo")
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    codex_calls = 0

    def fail_semantically(*args, **kwargs):
        raise CliError("semantic", "task failed its semantic postcondition")

    def unexpected_codex(*args, **kwargs):
        nonlocal codex_calls
        codex_calls += 1
        raise AssertionError("semantic failures must not advance")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.hermes.run_hermes_step", fail_semantically
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers._impl.run_codex_step", unexpected_codex
    )

    with pytest.raises(CliError, match="semantic postcondition"):
        run_step_with_worker(
            "execute",
            _state(repo),
            plan_dir,
            argparse.Namespace(phase_model=[], agent=None, hermes=None),
            root=repo,
            resolved=_mode(),
            read_only=False,
            record_routing=False,
            ledger_configured_specs=CHAIN,
        )
    assert codex_calls == 0


@pytest.mark.parametrize("attestation", [False, None])
def test_execute_rejects_tool_activity_or_unknown_external_mutation_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    attestation: bool | None,
) -> None:
    repo = _git_repo(tmp_path / "repo")
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    def fail(*args, **kwargs):
        error = _retryable("slow_visible_output", safe=False)
        if attestation is None:
            error.extra.pop("mutation_safe_to_retry")
        raise error

    monkeypatch.setattr("arnold_pipelines.megaplan.workers.hermes.run_hermes_step", fail)

    with pytest.raises(ExecuteFallbackMutationUnsafe) as raised:
        run_step_with_worker(
            "execute",
            _state(repo),
            plan_dir,
            argparse.Namespace(phase_model=[], agent=None, hermes=None),
            root=repo,
            resolved=_mode(),
            read_only=False,
            record_routing=False,
            ledger_configured_specs=CHAIN,
        )
    assert "external side effects" in str(raised.value) or "proof unavailable" in str(
        raised.value
    )


def test_execute_rejects_and_preserves_partial_workspace_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = _git_repo(tmp_path / "repo")
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    def mutate_then_fail(*args, **kwargs):
        (repo / "tracked.txt").write_text("partial mutation\n", encoding="utf-8")
        raise _retryable("streaming_timeout")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.hermes.run_hermes_step", mutate_then_fail
    )

    with pytest.raises(ExecuteFallbackMutationUnsafe) as raised:
        run_step_with_worker(
            "execute",
            _state(repo),
            plan_dir,
            argparse.Namespace(phase_model=[], agent=None, hermes=None),
            root=repo,
            resolved=_mode(),
            read_only=False,
            record_routing=False,
            ledger_configured_specs=CHAIN,
        )
    assert "tracked.txt" in raised.value.changed_paths
    assert "@git-status/index-and-submodules" in raised.value.changed_paths
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "partial mutation\n"


def test_workspace_guard_covers_untracked_files() -> None:
    # A new untracked file is still a mutation even though it is absent from
    # ``git diff`` without --no-index/--others handling.
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as directory:
        repo = _git_repo(Path(directory) / "repo")
        before = WorkspaceSnapshot.capture(repo)
        (repo / "new.txt").write_text("side effect\n", encoding="utf-8")
        evidence = before.compare(WorkspaceSnapshot.capture(repo))
    assert evidence.safe is False
    assert "new.txt" in evidence.changed_paths
    assert "@git-status/index-and-submodules" in evidence.changed_paths
