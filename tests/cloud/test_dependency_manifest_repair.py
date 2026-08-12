from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain.spec import (
    ChainSpec,
    ChainState,
    load_chain_state,
    save_chain_state,
    validate_paths,
)
from arnold_pipelines.megaplan.cloud.dependency_manifest_repair import (
    CensusRefusalError,
    _sync_completed_prerequisite,
    repair_dependency_manifests,
)


def test_dependency_manifest_repair_marks_review_chain_state_only_publication(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_root.mkdir()
    target_root.mkdir()
    source_chain = source_root / ".megaplan" / "initiatives" / "upstream" / "chain.yaml"
    target_chain = target_root / ".megaplan" / "initiatives" / "upstream" / "chain.yaml"
    source_chain.parent.mkdir(parents=True)
    target_chain.parent.mkdir(parents=True)
    body = """
merge_policy: review
milestones:
  - label: m1
    idea: m1.md
"""
    source_chain.write_text(body, encoding="utf-8")
    target_chain.write_text(body, encoding="utf-8")
    (target_root / "m1.md").write_text("# M1\n", encoding="utf-8")
    warning = (
        r"merge_policy should only be set away from `auto` when the user "
        r"explicitly requests a human PR merge gate"
    )
    with pytest.warns(UserWarning, match=warning):
        spec = ChainSpec.from_dict(
            {
                "merge_policy": "review",
                "milestones": [{"label": "m1", "idea": "m1.md"}],
            }
        )
    state = ChainState(
        current_milestone_index=1,
        completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
    )

    result = _sync_completed_prerequisite(
        target_root=target_root,
        target_chain=target_chain,
        source_root=source_root,
        source_chain=source_chain,
        spec=spec,
        state=state,
    )

    manifest_path = Path(result["manifest"]["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["milestones"][0]["publication_evidence"] == "chain_state_only"
    with pytest.warns(UserWarning, match=warning):
        saved = load_chain_state(target_chain)
    assert saved.completed[0]["publication_evidence"] == "chain_state_only"

    dependent_path = target_root / "dependent.yaml"
    dependent_path.write_text("milestones: []\n", encoding="utf-8")
    dependent_spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "upstream complete",
                    "kind": "chain_completed",
                    "chain": str(target_chain.relative_to(target_root)),
                    "require_manifest": True,
                }
            ],
            "milestones": [],
        }
    )
    with pytest.warns(UserWarning, match=warning):
        validate_paths(dependent_spec, target_root, spec_path=dependent_path)


def test_dependency_manifest_repair_finds_legacy_dot_chain_sibling(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    marker_dir = tmp_path / "markers"
    source_root.mkdir()
    target_root.mkdir()
    marker_dir.mkdir()
    source_chain = source_root / ".megaplan" / "initiatives" / "upstream.chain" / "chain.yaml"
    target_chain = target_root / ".megaplan" / "initiatives" / "upstream" / "chain.yaml"
    source_chain.parent.mkdir(parents=True)
    target_chain.parent.mkdir(parents=True)
    source_chain.write_text(
        """
milestones:
  - label: m1
    idea: .megaplan/initiatives/upstream.chain/briefs/m1.md
""",
        encoding="utf-8",
    )
    target_chain.write_text(
        """
milestones:
  - label: m1
    idea: .megaplan/initiatives/upstream/briefs/m1.md
""",
        encoding="utf-8",
    )
    (source_chain.parent / "briefs").mkdir()
    (target_chain.parent / "briefs").mkdir()
    (source_chain.parent / "briefs" / "m1.md").write_text("# M1\n", encoding="utf-8")
    (target_chain.parent / "briefs" / "m1.md").write_text("# M1\n", encoding="utf-8")
    save_chain_state(
        source_chain,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
        ),
    )
    marker = marker_dir / "upstream.json"
    marker.write_text(json.dumps({"workspace": str(source_root)}) + "\n", encoding="utf-8")
    dependent_chain = target_root / "dependent-chain.yaml"
    dependent_chain.write_text(
        """
launch_preconditions:
  - name: upstream complete
    kind: chain_completed
    chain: .megaplan/initiatives/upstream/chain.yaml
    require_manifest: true
milestones: []
""",
        encoding="utf-8",
    )

    result = repair_dependency_manifests(
        workspace=target_root,
        remote_spec=dependent_chain,
        marker_dir=marker_dir,
    )

    assert result.repaired is True
    manifest = json.loads(target_chain.with_name("completion-manifest.json").read_text(encoding="utf-8"))
    assert manifest["chain"]["path"] == ".megaplan/initiatives/upstream/chain.yaml"
    assert manifest["milestones"][0]["brief_path"] == (
        ".megaplan/initiatives/upstream/briefs/m1.md"
    )
    validate_paths(
        ChainSpec.from_dict(
            {
                "launch_preconditions": [
                    {
                        "name": "upstream complete",
                        "kind": "chain_completed",
                        "chain": ".megaplan/initiatives/upstream/chain.yaml",
                        "require_manifest": True,
                    }
                ],
                "milestones": [],
            }
        ),
        target_root,
        spec_path=dependent_chain,
    )


# ── G6 round-10: census-gated plan rematerialization ────────────────────────


@pytest.fixture(autouse=True)
def _sandbox_census_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point every reference-census store at (absent) sandbox dirs so the
    repair's census gate is hermetic and injectable per test (a missing
    store dir is not a reference; a test overrides the var it needs)."""
    for var, sub in (
        ("ARNOLD_BASE_DIR", "base"),
        ("ARNOLD_RUNTIME_MANIFEST_DIR", "manifests"),
        ("ARNOLD_REFERENCE_CHAIN_STORE", "chains"),
        ("ARNOLD_REFERENCE_MARKER_STORE", "markers"),
        ("ARNOLD_REFERENCE_SCHEDULE_STORES", "schedules"),
        ("ARNOLD_REFERENCE_REPAIR_QUEUE", "repair-queue"),
        ("ARNOLD_REFERENCE_LEASE_STORE", "leases"),
        ("ARNOLD_REFERENCE_PLAN_LEASE_ROOT", "plan-leases"),
        ("ARNOLD_REFERENCE_MANAGED_RUN_STORE", "managed-runs"),
        ("ARNOLD_REFERENCE_STATUS_DIR", "status"),
        ("ARNOLD_REFERENCE_OPS_STORE", "ops"),
    ):
        monkeypatch.setenv(var, str(tmp_path / sub))


def _lease_event() -> dict:
    """A REAL dispatch custody-lease acquire event (worker_dispatch_wbc.py
    open_lease_store(plan_dir / "custody" / "leases") -> acquire): owner
    identity triple + grant refs, NO path field of any kind — the per-plan
    lease STORE's presence is the census reference (G6)."""
    return {
        "event_id": "acquire-custody-lease-abc123",
        "lease_id": "custody-lease-abc123",
        "sequence": 1,
        "event_type": "acquire",
        "occurred_at": "2026-08-12T00:00:00+00:00",
        "custody_epoch": 1,
        "owner_host": "agentbox",
        "owner_pid": "4242",
        "owner_boot_id": "boot-1",
        "run_authority_grant_id": "attempt-1",
        "coordinator_fence_token": 0,
        "wbc_attempt_reference": "attempt-1",
        "occurrence_digest": "sha256:abc123",
        "idempotency_key": "attempt-1:start",
        "payload": {"expires_at": "2026-08-12T01:00:00+00:00"},
    }


def _spy_deletions(monkeypatch: pytest.MonkeyPatch, *, forbid: bool = False) -> list[tuple]:
    """Spy shutil.rmtree / shutil.copytree (record every call).  With
    forbid=True any call raises AssertionError — refusal tests must prove
    ZERO deletion/overwrite."""
    calls: list[tuple] = []
    real_rmtree = shutil.rmtree
    real_copytree = shutil.copytree

    def rmtree(path: Path, *args: object, **kwargs: object) -> None:
        calls.append(("rmtree", str(path)))
        if forbid:
            raise AssertionError(f"rmtree called during refused replacement: {path}")
        real_rmtree(path, *args, **kwargs)

    def copytree(src: Path, dst: Path, *args: object, **kwargs: object) -> None:
        calls.append(("copytree", str(src), str(dst)))
        if forbid:
            raise AssertionError(f"copytree called during refused replacement: {src} -> {dst}")
        real_copytree(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", rmtree)
    monkeypatch.setattr(shutil, "copytree", copytree)
    return calls


def _sync_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path, ChainSpec, ChainState]:
    """Completed source chain (with a plan artifact + brief) and a stale
    target chain with a target plan dir ready to be replaced.  Returns
    (source_root, target_root, source_chain, target_chain, target_plan,
    spec, state)."""
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_root.mkdir()
    target_root.mkdir()
    source_chain = source_root / ".megaplan" / "initiatives" / "upstream" / "chain.yaml"
    target_chain = target_root / ".megaplan" / "initiatives" / "upstream" / "chain.yaml"
    source_chain.parent.mkdir(parents=True)
    target_chain.parent.mkdir(parents=True)
    (source_chain.parent / "briefs").mkdir()
    (target_chain.parent / "briefs").mkdir()
    (source_chain.parent / "briefs" / "m1.md").write_text("# M1\n", encoding="utf-8")
    (target_chain.parent / "briefs" / "m1.md").write_text("# M1\n", encoding="utf-8")
    chain_body = """
milestones:
  - label: m1
    idea: .megaplan/initiatives/upstream/briefs/m1.md
"""
    source_chain.write_text(chain_body, encoding="utf-8")
    target_chain.write_text(chain_body, encoding="utf-8")
    source_plan = source_root / ".megaplan" / "plans" / "plan-m1"
    source_plan.mkdir(parents=True)
    (source_plan / "plan.md").write_text("fresh plan content\n", encoding="utf-8")
    target_plan = target_root / ".megaplan" / "plans" / "plan-m1"
    target_plan.mkdir(parents=True)
    (target_plan / "plan.md").write_text("STALE target plan content\n", encoding="utf-8")
    save_chain_state(
        source_chain,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
        ),
    )
    spec = ChainSpec.from_dict(
        {
            "milestones": [
                {"label": "m1", "idea": ".megaplan/initiatives/upstream/briefs/m1.md"}
            ]
        }
    )
    state = ChainState(
        current_milestone_index=1,
        completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
    )
    return source_root, target_root, source_chain, target_chain, target_plan, spec, state


def test_sync_completed_prerequisite_refuses_plan_replacement_when_lease_referenced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G6 round-10: a target plan dir holding a live custody lease store is
    REFERENCED by the census — the replacement is refused with ZERO
    rmtree/copytree and the plan dir + lease store stay intact."""
    (
        source_root,
        target_root,
        source_chain,
        target_chain,
        target_plan,
        spec,
        state,
    ) = _sync_fixture(tmp_path)
    lease_store = target_plan / "custody" / "leases"
    lease_store.mkdir(parents=True)
    (lease_store / "custody-lease-abc123.history.jsonl").write_text(
        json.dumps(_lease_event()) + "\n", encoding="utf-8"
    )
    monkeypatch.setenv(
        "ARNOLD_REFERENCE_PLAN_LEASE_ROOT", str(target_root / ".megaplan" / "plans")
    )
    calls = _spy_deletions(monkeypatch, forbid=True)

    with pytest.raises(CensusRefusalError) as excinfo:
        _sync_completed_prerequisite(
            target_root=target_root,
            target_chain=target_chain,
            source_root=source_root,
            source_chain=source_chain,
            spec=spec,
            state=state,
        )

    assert excinfo.value.verdict == "REFERENCED"
    assert str(excinfo.value.path) == str(target_plan)
    assert calls == []  # zero rmtree/copytree
    assert (target_plan / "plan.md").read_text(encoding="utf-8") == (
        "STALE target plan content\n"
    )
    assert lease_store.exists()


def test_sync_completed_prerequisite_refuses_plan_replacement_when_census_store_corrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G6 round-10 fail-closed: a corrupt lease file in the plan's own
    custody/leases store makes the census UNKNOWN — the replacement is
    refused (delete-on-unknown never happens; zero rmtree/copytree)."""
    (
        source_root,
        target_root,
        source_chain,
        target_chain,
        target_plan,
        spec,
        state,
    ) = _sync_fixture(tmp_path)
    lease_store = target_plan / "custody" / "leases"
    lease_store.mkdir(parents=True)
    (lease_store / "lease-corrupt.history.jsonl").write_text(
        '{"lease_id": "lease-corrupt", "event_type": "acquire", "payload": {"expires_at": "',
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "ARNOLD_REFERENCE_PLAN_LEASE_ROOT", str(target_root / ".megaplan" / "plans")
    )
    calls = _spy_deletions(monkeypatch, forbid=True)

    with pytest.raises(CensusRefusalError) as excinfo:
        _sync_completed_prerequisite(
            target_root=target_root,
            target_chain=target_chain,
            source_root=source_root,
            source_chain=source_chain,
            spec=spec,
            state=state,
        )

    assert excinfo.value.verdict == "UNKNOWN"
    assert str(excinfo.value.path) == str(target_plan)
    assert calls == []  # zero rmtree/copytree
    assert (target_plan / "plan.md").read_text(encoding="utf-8") == (
        "STALE target plan content\n"
    )
    assert lease_store.exists()


def test_sync_completed_prerequisite_refuses_nested_megaplan_replacement_when_referenced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G6 round-10: the nested .megaplan replacement (rmtree before the plan
    copy loop) is census-gated too — a chain store referencing the nested
    target dir REFUSES the replacement with zero rmtree/copytree."""
    (
        source_root,
        target_root,
        source_chain,
        target_chain,
        target_plan,
        spec,
        state,
    ) = _sync_fixture(tmp_path)
    source_nested = source_chain.parent / ".megaplan"
    target_nested = target_chain.parent / ".megaplan"
    source_nested.mkdir()
    (source_nested / "chain-state.json").write_text("fresh nested\n", encoding="utf-8")
    target_nested.mkdir()
    (target_nested / "chain-state.json").write_text("STALE nested\n", encoding="utf-8")
    chain_store = tmp_path / "chains"
    chain_store.mkdir()
    (chain_store / "chain-ref.json").write_text(
        json.dumps({"engine_root": str(target_nested)}) + "\n", encoding="utf-8"
    )
    monkeypatch.setenv("ARNOLD_REFERENCE_CHAIN_STORE", str(chain_store))
    calls = _spy_deletions(monkeypatch, forbid=True)

    with pytest.raises(CensusRefusalError) as excinfo:
        _sync_completed_prerequisite(
            target_root=target_root,
            target_chain=target_chain,
            source_root=source_root,
            source_chain=source_chain,
            spec=spec,
            state=state,
        )

    assert excinfo.value.verdict == "REFERENCED"
    assert str(excinfo.value.path) == str(target_nested)
    assert calls == []  # zero rmtree/copytree
    assert (target_nested / "chain-state.json").read_text(encoding="utf-8") == (
        "STALE nested\n"
    )
    assert (target_plan / "plan.md").read_text(encoding="utf-8") == (
        "STALE target plan content\n"
    )


def test_sync_completed_prerequisite_replaces_plan_when_census_clear(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G6 round-10 CLEAR side: with no reference store holding the target
    plan dir, the replacement proceeds (rmtree + copytree) and the target
    plan content is replaced by the source content."""
    (
        source_root,
        target_root,
        source_chain,
        target_chain,
        target_plan,
        spec,
        state,
    ) = _sync_fixture(tmp_path)
    calls = _spy_deletions(monkeypatch)  # record + delegate

    result = _sync_completed_prerequisite(
        target_root=target_root,
        target_chain=target_chain,
        source_root=source_root,
        source_chain=source_chain,
        spec=spec,
        state=state,
    )

    assert ("rmtree", str(target_plan)) in calls
    assert (
        "copytree",
        str(source_root / ".megaplan" / "plans" / "plan-m1"),
        str(target_plan),
    ) in calls
    assert (target_plan / "plan.md").read_text(encoding="utf-8") == (
        "fresh plan content\n"
    )
    assert result["copied_plan_artifacts"] == ["plan-m1"]
    assert result["copied_nested_state"] is False


def _repair_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    """Full repair scene for repair_dependency_manifests: a blocked target
    chain (blocker completion manifest) + completed sibling source chain +
    marker pointing at the source workspace + dependent chain whose
    precondition triggers the repair.  Returns (target_root, dependent_chain,
    marker_dir, target_chain, target_plan)."""
    (
        source_root,
        target_root,
        source_chain,
        target_chain,
        target_plan,
        _,
        _,
    ) = _sync_fixture(tmp_path)
    (target_chain.with_name("completion-manifest.json")).write_text(
        json.dumps(
            {
                "schema": "arnold.megaplan.chain_completion_manifest.v1",
                "chain": {"path": ".megaplan/initiatives/upstream/chain.yaml"},
                "milestones": [],
                "_blocker": {
                    "reason": "harness_state_not_sufficient_for_auto_generation"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "upstream.json").write_text(
        json.dumps({"workspace": str(source_root)}) + "\n", encoding="utf-8"
    )
    dependent_chain = target_root / "dependent-chain.yaml"
    dependent_chain.write_text(
        """
launch_preconditions:
  - name: upstream complete
    kind: chain_completed
    chain: .megaplan/initiatives/upstream/chain.yaml
    require_manifest: true
milestones: []
""",
        encoding="utf-8",
    )
    return target_root, dependent_chain, marker_dir, target_chain, target_plan


def test_repair_dependency_manifests_refuses_referenced_plan_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G6 round-10 integration: when the target plan dir is REFERENCED by a
    live custody lease store, repair_dependency_manifests refuses the
    replacement end to end — result.repaired is False with the refusal note
    and ZERO rmtree/copytree (plan dir + lease store intact)."""
    target_root, dependent_chain, marker_dir, target_chain, target_plan = _repair_fixture(
        tmp_path
    )
    lease_store = target_plan / "custody" / "leases"
    lease_store.mkdir(parents=True)
    (lease_store / "custody-lease-abc123.history.jsonl").write_text(
        json.dumps(_lease_event()) + "\n", encoding="utf-8"
    )
    monkeypatch.setenv(
        "ARNOLD_REFERENCE_PLAN_LEASE_ROOT", str(target_root / ".megaplan" / "plans")
    )
    calls = _spy_deletions(monkeypatch, forbid=True)

    result = repair_dependency_manifests(
        workspace=target_root,
        remote_spec=dependent_chain,
        marker_dir=marker_dir,
    )

    assert result.repaired is False
    assert result.reason == "dependency_manifest_repair_refused_census"
    assert len(result.details["repairs"]) == 1
    refused = result.details["repairs"][0]["refused"]
    assert refused["verdict"] == "REFERENCED"
    assert refused["path"] == str(target_plan)
    assert refused["reasons"]
    assert calls == []  # zero rmtree/copytree
    assert (target_plan / "plan.md").read_text(encoding="utf-8") == (
        "STALE target plan content\n"
    )
    assert lease_store.exists()


def test_repair_dependency_manifests_refuses_corrupt_census_store_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G6 round-10 integration fail-closed: a corrupt lease file in the
    target plan's custody/leases store makes the census UNKNOWN — the repair
    refuses (zero rmtree/copytree) instead of replacing a plan dir it cannot
    attest."""
    target_root, dependent_chain, marker_dir, target_chain, target_plan = _repair_fixture(
        tmp_path
    )
    lease_store = target_plan / "custody" / "leases"
    lease_store.mkdir(parents=True)
    (lease_store / "lease-corrupt.history.jsonl").write_text(
        '{"lease_id": "lease-corrupt", "event_type": "acquire", "payload": {"expires_at": "',
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "ARNOLD_REFERENCE_PLAN_LEASE_ROOT", str(target_root / ".megaplan" / "plans")
    )
    calls = _spy_deletions(monkeypatch, forbid=True)

    result = repair_dependency_manifests(
        workspace=target_root,
        remote_spec=dependent_chain,
        marker_dir=marker_dir,
    )

    assert result.repaired is False
    assert result.reason == "dependency_manifest_repair_refused_census"
    assert result.details["repairs"][0]["refused"]["verdict"] == "UNKNOWN"
    assert calls == []  # zero rmtree/copytree
    assert (target_plan / "plan.md").read_text(encoding="utf-8") == (
        "STALE target plan content\n"
    )
    assert lease_store.exists()
