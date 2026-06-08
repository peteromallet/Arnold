from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.runtime.execution_environment import (
    append_engine_overlap_waiver,
    classify_path_overlap,
    git_provenance,
    isolation_cli_error,
    merge_isolation_evidence,
    preflight_mutating_phase,
    preflight_phase,
    resolve_execution_environment,
)
from arnold.pipelines.megaplan.runtime.engine_isolation import engine_write_barrier
from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan.workers import set_work_dir_override


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE)


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "file.txt").write_text("initial\n", encoding="utf-8")
    _git(repo, "add", "file.txt")
    _git(repo, "commit", "-m", "initial")


def test_path_overlap_is_prefix_safe(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    target = tmp_path / "engine-target"
    nested = engine / "target"

    assert classify_path_overlap(engine, engine) == "equal"
    assert classify_path_overlap(engine, nested) == "left_contains_right"
    assert classify_path_overlap(nested, engine) == "right_contains_left"
    assert classify_path_overlap(engine, target) == "disjoint"


def test_git_provenance_without_git_metadata_is_stable(tmp_path: Path) -> None:
    path = tmp_path / "plain"
    path.mkdir()

    first = git_provenance(path)
    second = git_provenance(path)

    assert first.head is None
    assert first.base is None
    assert first.base_ref is None
    assert first.dirty is False
    assert first.fallback_reason == "git_metadata_unavailable"
    assert first.signature == second.signature
    assert first.signature.startswith("sha256:")


def test_git_provenance_tracks_head_base_and_dirty_status(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()

    clean = git_provenance(repo, base_ref="main")
    (repo / "file.txt").write_text("changed\n", encoding="utf-8")
    dirty = git_provenance(repo, base_ref="main")

    assert clean.head == head
    assert clean.base == head
    assert clean.base_ref == "main"
    assert clean.dirty is False
    assert dirty.head == head
    assert dirty.dirty is True
    assert dirty.signature != clean.signature


def test_resolver_returns_absolute_contract_and_target_provenance(tmp_path: Path) -> None:
    project_root = tmp_path / "driver"
    target_root = tmp_path / "target"
    engine_root = tmp_path / "engine"
    work_dir = target_root / "subdir"
    _init_repo(target_root)
    _init_repo(engine_root)
    work_dir.mkdir()

    set_work_dir_override(work_dir)
    try:
        env = resolve_execution_environment(
            root=project_root,
            state={"config": {"project_dir": str(target_root), "base_branch": "main"}},
            engine_root=engine_root,
        )
    finally:
        set_work_dir_override(None)

    assert env.project_root == project_root.resolve()
    assert env.target_root == target_root.resolve()
    assert env.work_dir == work_dir.resolve()
    assert env.engine_root == engine_root.resolve()
    assert env.engine_commit is not None
    assert env.engine_signature.startswith("sha256:")
    assert env.engine_dirty is False
    assert env.target_head is not None
    assert env.target_base == env.target_head
    assert env.target_base_ref == "main"
    assert env.target_fallback_reason is None


def test_isolation_cli_error_attaches_contract(tmp_path: Path) -> None:
    target_root = tmp_path / "target"
    engine_root = tmp_path / "engine"
    _init_repo(target_root)
    _init_repo(engine_root)

    env = resolve_execution_environment(
        root=tmp_path,
        state={"config": {"project_dir": str(target_root)}},
        engine_root=engine_root,
    )
    error = isolation_cli_error(
        "engine_target_overlap",
        "engine and target overlap",
        env=env,
        extra={"phase": "execute"},
    )

    assert isinstance(error, CliError)
    assert error.extra["phase"] == "execute"
    assert error.extra["target_root"] == str(target_root.resolve())
    assert error.extra["engine_root"] == str(engine_root.resolve())


def test_isolation_metadata_merge_pins_existing_values_and_records_drift(tmp_path: Path) -> None:
    target_root = tmp_path / "target"
    engine_root = tmp_path / "engine"
    _init_repo(target_root)
    _init_repo(engine_root)
    env = resolve_execution_environment(
        root=tmp_path,
        state={"config": {"project_dir": str(target_root)}},
        engine_root=engine_root,
    )

    metadata = merge_isolation_evidence(
        {"engine_isolation": {"engine_root": "/pinned/engine"}},
        env,
        phase="chain_start",
    )

    record = metadata["engine_isolation"]
    assert record["engine_root"] == "/pinned/engine"
    assert record["target_root"] == str(target_root.resolve())
    assert record["last_observed_phase"] == "chain_start"
    assert record["drift"][0]["field"] == "engine_root"


def test_engine_overlap_waiver_is_append_only_and_scoped(tmp_path: Path) -> None:
    target_root = tmp_path / "target"
    engine_root = tmp_path / "engine"
    _init_repo(target_root)
    _init_repo(engine_root)
    env = resolve_execution_environment(
        root=tmp_path,
        state={"config": {"project_dir": str(target_root)}},
        engine_root=engine_root,
    )

    metadata, waiver = append_engine_overlap_waiver(
        {"engine_isolation": {"engine_root": str(engine_root.resolve()), "engine_signature": env.engine_signature}},
        env,
        reason="intentional local overlap",
        phase="execute",
        timestamp="2026-06-07T00:00:00Z",
    )
    deduped, same_waiver = append_engine_overlap_waiver(
        metadata,
        env,
        reason="intentional local overlap",
        phase="execute",
        timestamp="2026-06-07T00:00:00Z",
    )

    assert waiver["id"] == same_waiver["id"]
    assert len(deduped["engine_overlap_waivers"]) == 1
    assert deduped["latest_engine_overlap_waiver_id"] == waiver["id"]
    assert waiver["scope"]["target_root"] == str(target_root.resolve())
    assert waiver["scope"]["engine_root"] == str(engine_root.resolve())


def test_preflight_phase_persists_contract_and_refuses_engine_pin_drift(tmp_path: Path) -> None:
    target_root = tmp_path / "target"
    engine_root = tmp_path / "engine"
    _init_repo(target_root)
    _init_repo(engine_root)
    state = {"config": {"project_dir": str(target_root)}, "meta": {}}

    env = preflight_phase(root=tmp_path, state=state, phase="execute", engine_root=engine_root)

    record = state["meta"]["engine_isolation"]
    assert record["engine_root"] == str(engine_root.resolve())
    assert record["engine_signature"] == env.engine_signature
    assert record["last_observed_phase"] == "execute"

    other_engine = tmp_path / "other-engine"
    _init_repo(other_engine)
    with pytest.raises(CliError) as excinfo:
        preflight_phase(root=tmp_path, state=state, phase="review", engine_root=other_engine)
    assert excinfo.value.code == "engine_pin_drift"
    assert excinfo.value.extra["phase"] == "review"
    assert "engine_root" in excinfo.value.extra["drift"]


def test_preflight_phase_refuses_ambient_engine_signature_drift(tmp_path: Path) -> None:
    target_root = tmp_path / "target"
    engine_root = tmp_path / "engine"
    _init_repo(target_root)
    _init_repo(engine_root)
    state = {"config": {"project_dir": str(target_root)}, "meta": {}}

    env = preflight_phase(root=tmp_path, state=state, phase="execute", engine_root=engine_root)
    (engine_root / "ambient.txt").write_text("changed outside worker\n", encoding="utf-8")

    with pytest.raises(CliError) as excinfo:
        preflight_phase(root=tmp_path, state=state, phase="review", engine_root=engine_root)

    assert excinfo.value.code == "engine_pin_drift"
    drift = excinfo.value.extra["drift"]["engine_signature"]
    assert drift["pinned"] == env.engine_signature
    assert drift["observed"] != env.engine_signature


def test_preflight_mutating_phase_refuses_overlap_without_valid_waiver(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine"
    target_root = engine_root / "target"
    _init_repo(engine_root)
    target_root.mkdir()
    state = {"config": {"project_dir": str(target_root)}, "meta": {}}

    with pytest.raises(CliError) as excinfo:
        preflight_mutating_phase(root=tmp_path, state=state, phase="execute", engine_root=engine_root)

    assert excinfo.value.code == "engine_target_overlap_requires_waiver"
    assert excinfo.value.extra["waiver_invalid_reason"] == "missing"
    assert excinfo.value.extra["waiver_action"] == "waive-engine-overlap"
    assert "waive-engine-overlap" in excinfo.value.message


def test_preflight_mutating_phase_consumes_valid_waiver_and_rejects_reuse(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine"
    target_root = engine_root / "target"
    _init_repo(engine_root)
    target_root.mkdir()
    state = {"config": {"project_dir": str(target_root)}, "meta": {}}
    env = resolve_execution_environment(root=tmp_path, state=state, engine_root=engine_root)
    state["meta"], waiver = append_engine_overlap_waiver(
        state["meta"],
        env,
        reason="intentional colocated dogfood",
        phase="execute",
        timestamp="2026-06-07T00:00:00Z",
    )

    preflight_mutating_phase(
        root=tmp_path,
        state=state,
        phase="execute",
        engine_root=engine_root,
        now="2026-06-07T00:01:00Z",
    )

    latest = state["meta"]["engine_overlap_waivers"][0]
    assert latest["id"] == waiver["id"]
    assert latest["consumed_at"] == "2026-06-07T00:01:00Z"
    assert latest["consumed_by_phase"] == "execute"
    with pytest.raises(CliError) as excinfo:
        preflight_mutating_phase(
            root=tmp_path,
            state=state,
            phase="execute",
            engine_root=engine_root,
            now="2026-06-07T00:02:00Z",
        )
    assert excinfo.value.extra["waiver_invalid_reason"] == "consumed"


def test_preflight_mutating_phase_honors_waiver_run_limit(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine"
    target_root = engine_root / "target"
    _init_repo(engine_root)
    target_root.mkdir()
    state = {"config": {"project_dir": str(target_root)}, "meta": {}}
    env = resolve_execution_environment(root=tmp_path, state=state, engine_root=engine_root)
    state["meta"], waiver = append_engine_overlap_waiver(
        state["meta"],
        env,
        reason="intentional colocated dogfood",
        phase="execute",
        timestamp="2026-06-07T00:00:00Z",
        expires_after_runs=2,
    )

    preflight_mutating_phase(
        root=tmp_path,
        state=state,
        phase="execute",
        engine_root=engine_root,
        now="2026-06-07T00:01:00Z",
    )
    latest = state["meta"]["engine_overlap_waivers"][0]
    assert latest["id"] == waiver["id"]
    assert latest["remaining_runs"] == 1
    assert latest["consumed_at"] is None
    assert latest["last_consumed_at"] == "2026-06-07T00:01:00Z"

    preflight_mutating_phase(
        root=tmp_path,
        state=state,
        phase="execute",
        engine_root=engine_root,
        now="2026-06-07T00:02:00Z",
    )
    latest = state["meta"]["engine_overlap_waivers"][0]
    assert latest["remaining_runs"] == 0
    assert latest["consumed_at"] == "2026-06-07T00:02:00Z"

    with pytest.raises(CliError) as excinfo:
        preflight_mutating_phase(
            root=tmp_path,
            state=state,
            phase="execute",
            engine_root=engine_root,
            now="2026-06-07T00:03:00Z",
        )
    assert excinfo.value.extra["waiver_invalid_reason"] == "consumed"


def test_engine_write_barrier_supports_local_immutable_probe_provider(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.runtime.engine_isolation import engine_write_barrier, select_provider

    target_root = tmp_path / "target"
    engine_root = tmp_path / "engine"
    _init_repo(target_root)
    _init_repo(engine_root)
    env = resolve_execution_environment(
        root=tmp_path,
        state={"config": {"project_dir": str(target_root)}},
        engine_root=engine_root,
    )

    assert select_provider({"MEGAPLAN_ENGINE_ISOLATION_PROVIDER": "local_immutable_probe"}) == "local_immutable_probe"

    # Simulate a real local deny provider by replacing the probe functions; the
    # provider selection must not require MEGAPLAN_TRUSTED_CONTAINER.
    import arnold.pipelines.megaplan.runtime.engine_isolation as isolation

    original_allowed = isolation._probe_write_allowed
    original_denied = isolation._probe_write_denied
    try:
        isolation._probe_write_allowed = lambda _root: True
        isolation._probe_write_denied = lambda _root: (True, False)
        proof = engine_write_barrier(
            env,
            "execute",
            env_vars={"MEGAPLAN_ENGINE_ISOLATION_PROVIDER": "local_immutable_probe"},
        )
    finally:
        isolation._probe_write_allowed = original_allowed
        isolation._probe_write_denied = original_denied

    assert proof.provider == "local_immutable_probe"
    assert proof.trusted_container is False
    assert proof.engine_write_denied is True
    assert proof.target_write_allowed is True


def test_preflight_mutating_phase_rejects_expired_waiver(tmp_path: Path) -> None:
    engine_root = tmp_path / "engine"
    target_root = engine_root / "target"
    _init_repo(engine_root)
    target_root.mkdir()
    state = {"config": {"project_dir": str(target_root)}, "meta": {}}
    env = resolve_execution_environment(root=tmp_path, state=state, engine_root=engine_root)
    state["meta"], _waiver = append_engine_overlap_waiver(
        state["meta"],
        env,
        reason="intentional colocated dogfood",
        phase="execute",
        timestamp="2026-06-07T00:00:00Z",
    )
    state["meta"]["engine_overlap_waivers"][0]["expires_at"] = "2026-06-07T00:00:30Z"

    with pytest.raises(CliError) as excinfo:
        preflight_mutating_phase(
            root=tmp_path,
            state=state,
            phase="execute",
            engine_root=engine_root,
            now="2026-06-07T00:01:00Z",
        )
    assert excinfo.value.extra["waiver_invalid_reason"] == "expired"


def test_engine_write_barrier_fails_closed_without_verified_provider(tmp_path: Path) -> None:
    target_root = tmp_path / "target"
    engine_root = tmp_path / "engine"
    _init_repo(target_root)
    _init_repo(engine_root)
    env = resolve_execution_environment(
        root=tmp_path,
        state={"config": {"project_dir": str(target_root)}},
        engine_root=engine_root,
    )

    try:
        engine_write_barrier(env, "execute", env_vars={})
    except CliError as exc:
        assert exc.code == "engine_write_isolation_unverified"
        assert exc.extra["proof"]["same_user_chmod_accepted"] is False
        assert "chmod" in exc.message
    else:
        raise AssertionError("engine_write_barrier should fail closed")


def test_trusted_container_probe_rejects_same_user_chmod_denial(tmp_path: Path) -> None:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root can bypass chmod-only write denial")
    target_root = tmp_path / "target"
    engine_root = tmp_path / "engine"
    _init_repo(target_root)
    _init_repo(engine_root)
    env = resolve_execution_environment(
        root=tmp_path,
        state={"config": {"project_dir": str(target_root)}},
        engine_root=engine_root,
    )
    original_mode = engine_root.stat().st_mode
    engine_root.chmod(original_mode & ~0o222)
    try:
        try:
            engine_write_barrier(env, "execute", env_vars={"MEGAPLAN_TRUSTED_CONTAINER": "1"})
        except CliError as exc:
            assert exc.code == "engine_write_isolation_unverified"
            assert exc.extra["proof"]["engine_write_denied"] is False
            assert exc.extra["proof"]["diagnostic"] == "same_user_chmod_is_diagnostic_only_not_m0_proof"
        else:
            raise AssertionError("same-user chmod denial must not satisfy engine isolation")
    finally:
        engine_root.chmod(original_mode)


def test_trusted_container_probe_allows_target_and_denies_engine_with_verified_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target_root = tmp_path / "target"
    engine_root = tmp_path / "engine"
    _init_repo(target_root)
    _init_repo(engine_root)
    env = resolve_execution_environment(
        root=tmp_path,
        state={"config": {"project_dir": str(target_root)}},
        engine_root=engine_root,
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.runtime.engine_isolation._probe_write_denied",
        lambda root: (root == engine_root.resolve(), False),
    )
    proof = engine_write_barrier(env, "execute", env_vars={"MEGAPLAN_TRUSTED_CONTAINER": "1"})
    assert proof.provider == "trusted_container_probe"
    assert proof.engine_write_denied is True
    assert proof.target_write_allowed is True
