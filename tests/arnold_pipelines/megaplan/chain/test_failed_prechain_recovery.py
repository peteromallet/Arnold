"""Focused contract tests for the failed pre-chain recovery seam."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import arnold_pipelines.megaplan.chain.failed_prechain_recovery as recovery
from arnold_pipelines.megaplan.types import CliError


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "workspace"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "recovery-test")
    (root / "tracked.txt").write_text("old\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "old")
    old = _git(root, "rev-parse", "HEAD")
    (root / "reviewed.txt").write_text("new\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "reviewed")
    new = _git(root, "rev-parse", "HEAD")
    _git(root, "checkout", "-q", old)
    return root, old, new


def test_staging_archives_dirty_workspace_without_mutating_it(tmp_path: Path) -> None:
    source, old, new = _repo(tmp_path)
    (source / "tracked.txt").write_text("generated reconcile\n", encoding="utf-8")
    (source / "briefs").mkdir()
    (source / "briefs" / "reconcile.md").write_text("generated\n", encoding="utf-8")
    before = (source / "tracked.txt").read_bytes()
    archive, payload = recovery._archive_dirty_state(source, tmp_path / "custody", "op")
    recovery._verify_archive(archive, payload, "op")
    recovery._stage_runtime(source, tmp_path / "staged", old, new)
    assert (source / "tracked.txt").read_bytes() == before
    assert (source / "briefs" / "reconcile.md").read_text() == "generated\n"
    assert recovery._head(source) == old
    assert recovery._head(tmp_path / "staged") == new


def test_staging_rejects_non_descendant_without_touching_source(tmp_path: Path) -> None:
    source, old, _new = _repo(tmp_path)
    before = _git(source, "rev-parse", "HEAD")
    with pytest.raises(CliError, match="not a descendant"):
        recovery._stage_runtime(source, tmp_path / "staged", old, "f" * 40)
    assert recovery._head(source) == before
    assert not (tmp_path / "staged").exists()


def test_archive_fingerprint_rejects_new_dirty_path(tmp_path: Path) -> None:
    source, _old, _new = _repo(tmp_path)
    (source / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    archive, payload = recovery._archive_dirty_state(source, tmp_path / "custody", "op")
    (source / "new-generated.md").write_text("late\n", encoding="utf-8")
    with pytest.raises(CliError, match="differs from the archive"):
        recovery._assert_source_archive_fingerprint(source, archive, payload)


def test_secret_like_operator_text_is_rejected_before_persistence() -> None:
    with pytest.raises(CliError, match="credential-like"):
        recovery._safe_text("operator api_key=should-not-persist", label="reason")


def test_wrong_identity_or_live_owner_has_zero_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, old, _new = _repo(tmp_path)
    (source / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    project = tmp_path / "session"
    (project / ".megaplan" / "initiatives" / "x").mkdir(parents=True)
    spec = project / ".megaplan" / "initiatives" / "x" / "chain.yaml"
    spec.write_text("milestones: []\n", encoding="utf-8")
    marker = project / "marker.json"
    marker.write_text(json.dumps({"session": "session", "workspace": str(source), "owner": "live", "launch_outcome": {"status": "failed", "code": "launch_not_advanced"}}) + "\n")
    manifest = project / "manifest.json"
    manifest.write_text("{}\n")
    monkeypatch.setattr(recovery, "load_manifest", lambda _path: SimpleNamespace(epic={"runtime_root": str(source), "expected_head": old}, generation=1))
    before = {path: path.read_bytes() for path in (marker, manifest)}
    with pytest.raises(CliError, match="no live owner"):
        recovery.recover_failed_prechain(
            spec, project, marker_path=marker, manifest_path=manifest,
            source_path=source, workspace_path=source, staged_runtime_path=tmp_path / "staged",
            custody_dir=tmp_path / "custody", expected_session_id="session",
            expected_marker_sha256=hashlib.sha256(marker.read_bytes()).hexdigest(),
            expected_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
            expected_spec_sha256=hashlib.sha256(spec.read_bytes()).hexdigest(),
            expected_old_sha=old, reviewed_new_sha="a" * 40, reason="test",
        )
    assert {path: path.read_bytes() for path in (marker, manifest)} == before


def test_recovery_is_idempotent_and_leaves_chain_state_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, old, new = _repo(tmp_path)
    (source / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    (source / "briefs").mkdir()
    (source / "briefs" / "reconcile.md").write_text("generated\n", encoding="utf-8")
    project = tmp_path / "session"
    (project / ".megaplan" / "initiatives" / "x").mkdir(parents=True)
    spec = project / ".megaplan" / "initiatives" / "x" / "chain.yaml"
    spec.write_text("milestones: []\n", encoding="utf-8")
    marker = project / "marker.json"
    marker.write_text(json.dumps({"session": "session", "workspace": str(source), "bootstrap_manifest_path": str(project / "manifest.json"), "launch_outcome": {"status": "failed", "code": "launch_not_advanced"}}) + "\n")
    manifest = project / "manifest.json"
    manifest.write_text("manifest-before\n")
    current = SimpleNamespace(epic={"runtime_root": str(source), "expected_head": old, "venv_path": "/tmp/venv", "repair_bin": "/tmp/bin"}, generation=1)
    monkeypatch.setattr(recovery, "load_manifest", lambda _path: current)
    class Promoted:
        generation = 2
        epic = {"runtime_root": str(tmp_path / "staged"), "expected_head": new}
    monkeypatch.setattr(recovery, "cutover_runtime_manifest", lambda *_args, **_kwargs: Promoted())
    monkeypatch.setattr(recovery, "write_manifest", lambda _manifest, path: path.write_text("manifest-after\n"))
    kwargs = dict(
        marker_path=marker, manifest_path=manifest, source_path=source, workspace_path=source,
        staged_runtime_path=tmp_path / "staged", custody_dir=tmp_path / "custody",
        expected_session_id="session", expected_marker_sha256=hashlib.sha256(marker.read_bytes()).hexdigest(),
        expected_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        expected_spec_sha256=hashlib.sha256(spec.read_bytes()).hexdigest(), expected_old_sha=old,
        reviewed_new_sha=new, reason="failed pre-chain recovery",
    )
    first = recovery.recover_failed_prechain(spec, project, **kwargs)
    assert first["outcome"] == "committed"
    assert not recovery.chain_spec._state_path_for(spec).exists()
    assert recovery._head(source) == new
    assert recovery._head(tmp_path / "custody" / first["operation_id"] / "failed-workspace") == old
    second = recovery.recover_failed_prechain(spec, project, **kwargs)
    assert second["outcome"] == "replay"


def test_three_root_recovery_preserves_engine_and_reviewed_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, old, new = _repo(tmp_path)
    ledger = source / ".megaplan" / "incident-ledger"
    ledger.mkdir(parents=True)
    (ledger / ".events.seq").write_text("0\n", encoding="utf-8")
    (ledger / ".events.init_ts").write_text("2026-01-01T00:00:00+00:00\n", encoding="utf-8")
    (ledger / "events.jsonl").write_text("", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-qm", "ledger baseline")
    old = _git(source, "rev-parse", "HEAD")
    (source / "reviewed.txt").write_text("newer\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-qm", "reviewed with ledger")
    new = _git(source, "rev-parse", "HEAD")
    _git(source, "checkout", "-q", old)
    engine = tmp_path / "engine"
    workspace = tmp_path / "chain-workspace"
    project = tmp_path / "session"
    subprocess.run(["git", "clone", "-q", str(source), str(engine)], check=True)
    subprocess.run(["git", "clone", "-q", str(source), str(workspace)], check=True)
    (workspace / "tracked.txt").write_text("generated reconcile\n", encoding="utf-8")
    (workspace / "briefs").mkdir()
    (workspace / "briefs" / "reconcile.md").write_text("generated\n", encoding="utf-8")
    spec = workspace / ".megaplan" / "initiatives" / "x" / "chain.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text("milestones: []\n", encoding="utf-8")
    project.mkdir()
    marker = project / "marker.json"
    marker.write_text(json.dumps({"session": project.name, "workspace": str(workspace), "bootstrap_manifest_path": str(project / "manifest.json"), "launch_outcome": {"status": "failed", "code": "launch_not_advanced"}}) + "\n")
    manifest = project / "manifest.json"
    manifest.write_text("manifest-before\n")
    current = SimpleNamespace(epic={"runtime_root": str(engine), "expected_head": old, "venv_path": "/tmp/venv", "repair_bin": "/tmp/bin"}, generation=1)
    from arnold_pipelines.megaplan.incident import chain_control
    original_journal_for = chain_control.journal_for
    monkeypatch.setattr(chain_control, "journal_for", lambda _root: original_journal_for(workspace))
    probe_journal = original_journal_for(workspace)
    probe_paths = recovery._journal_owned_paths(probe_journal, chain_control.chain_id_for_spec(spec), workspace)
    probe_archive, probe_payload = recovery._archive_dirty_state(workspace, tmp_path / "probe-custody", "probe", exclude_paths=probe_paths)
    (workspace / "unrelated-ledger-or-product.md").write_text("must reject\n", encoding="utf-8")
    with pytest.raises(CliError, match="differs from the archive"):
        recovery._assert_source_archive_fingerprint(workspace, probe_archive, probe_payload, exclude_paths=probe_paths)
    (workspace / "unrelated-ledger-or-product.md").unlink()
    monkeypatch.setattr(recovery, "load_manifest", lambda _path: current)
    monkeypatch.setattr(recovery, "cutover_runtime_manifest", lambda *_args, **_kwargs: SimpleNamespace(generation=2, epic={"runtime_root": str(workspace), "expected_head": new}))
    monkeypatch.setattr(recovery, "write_manifest", lambda _manifest, path: path.write_text("manifest-after\n"))
    marker_before, manifest_before = marker.read_bytes(), manifest.read_bytes()
    kwargs = dict(marker_path=marker, manifest_path=manifest, source_path=source, workspace_path=workspace, staged_runtime_path=tmp_path / "staged", custody_dir=tmp_path / "custody", expected_session_id=project.name, expected_marker_sha256=hashlib.sha256(marker_before).hexdigest(), expected_manifest_sha256=hashlib.sha256(manifest_before).hexdigest(), expected_spec_sha256=hashlib.sha256(spec.read_bytes()).hexdigest(), expected_old_sha=old, reviewed_new_sha=new, reason="three root recovery")
    result = recovery.recover_failed_prechain(spec, project, **kwargs)
    assert result["outcome"] == "committed"
    assert recovery._head(source) == old
    assert not recovery._status(source)
    assert recovery._head(engine) == old
    assert not recovery._status(engine)
    assert recovery._head(workspace) == new
    assert all(
        item[3:].rstrip("/").startswith(".megaplan/incident-ledger/")
        for item in recovery._status(workspace)
    )
    failed = tmp_path / "custody" / result["operation_id"] / "failed-workspace"
    assert recovery._head(failed) == old
    assert (failed / ".megaplan" / "incident-ledger" / "events.jsonl").read_text(encoding="utf-8")


def test_manifest_failure_rolls_back_workspace_and_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, old, new = _repo(tmp_path)
    (source / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    project = tmp_path / "session"
    (project / ".megaplan" / "initiatives" / "x").mkdir(parents=True)
    spec = project / ".megaplan" / "initiatives" / "x" / "chain.yaml"
    spec.write_text("milestones: []\n", encoding="utf-8")
    marker = project / "marker.json"
    marker.write_text(json.dumps({"session": "session", "workspace": str(source), "launch_outcome": {"status": "failed", "code": "launch_not_advanced"}}) + "\n")
    manifest = project / "manifest.json"
    manifest.write_text("manifest-before\n")
    current = SimpleNamespace(epic={"runtime_root": str(source), "expected_head": old, "venv_path": "/tmp/venv", "repair_bin": "/tmp/bin"}, generation=1)
    monkeypatch.setattr(recovery, "load_manifest", lambda _path: current)
    monkeypatch.setattr(recovery, "cutover_runtime_manifest", lambda *_args, **_kwargs: SimpleNamespace(generation=2, epic={"runtime_root": str(source), "expected_head": new}))
    monkeypatch.setattr(recovery, "write_manifest", lambda *_args: (_ for _ in ()).throw(RuntimeError("injected manifest failure")))
    marker_before, manifest_before = marker.read_bytes(), manifest.read_bytes()
    kwargs = dict(marker_path=marker, manifest_path=manifest, source_path=source, workspace_path=source, staged_runtime_path=tmp_path / "staged", custody_dir=tmp_path / "custody", expected_session_id="session", expected_marker_sha256=hashlib.sha256(marker_before).hexdigest(), expected_manifest_sha256=hashlib.sha256(manifest_before).hexdigest(), expected_spec_sha256=hashlib.sha256(spec.read_bytes()).hexdigest(), expected_old_sha=old, reviewed_new_sha=new, reason="rollback test")
    with pytest.raises(CliError, match="injected manifest failure"):
        recovery.recover_failed_prechain(spec, project, **kwargs)
    assert marker.read_bytes() == marker_before
    assert manifest.read_bytes() == manifest_before
    assert recovery._head(source) == old
    assert recovery._head(tmp_path / "staged") == new
    assert not recovery.chain_spec._state_path_for(spec).exists()


def test_committed_event_failure_rolls_back_and_leaves_durable_hold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, old, new = _repo(tmp_path)
    (source / "tracked.txt").write_text("dirty\n", encoding="utf-8")
    project = tmp_path / "session"
    (project / ".megaplan" / "initiatives" / "x").mkdir(parents=True)
    spec = project / ".megaplan" / "initiatives" / "x" / "chain.yaml"
    spec.write_text("milestones: []\n", encoding="utf-8")
    marker = project / "marker.json"
    marker.write_text(json.dumps({"session": "session", "workspace": str(source), "launch_outcome": {"status": "failed", "code": "launch_not_advanced"}}) + "\n")
    manifest = project / "manifest.json"
    manifest.write_text("manifest-before\n")
    current = SimpleNamespace(epic={"runtime_root": str(source), "expected_head": old, "venv_path": "/tmp/venv", "repair_bin": "/tmp/bin"}, generation=1)
    monkeypatch.setattr(recovery, "load_manifest", lambda _path: current)
    monkeypatch.setattr(recovery, "cutover_runtime_manifest", lambda *_args, **_kwargs: SimpleNamespace(generation=2, epic={"runtime_root": str(source), "expected_head": new}))
    monkeypatch.setattr(recovery, "write_manifest", lambda _manifest, path: path.write_text("manifest-after\n"))
    from arnold_pipelines.megaplan.incident.chain_control import ChainControlJournal
    original_append = ChainControlJournal.append_under_lock

    def fail_final_append(self, txn, **kwargs):
        if kwargs.get("event_kind") == "chain_control.committed":
            raise OSError("injected committed append/fsync failure")
        return original_append(self, txn, **kwargs)

    monkeypatch.setattr(ChainControlJournal, "append_under_lock", fail_final_append)
    marker_before, manifest_before = marker.read_bytes(), manifest.read_bytes()
    kwargs = dict(marker_path=marker, manifest_path=manifest, source_path=source, workspace_path=source, staged_runtime_path=tmp_path / "staged", custody_dir=tmp_path / "custody", expected_session_id="session", expected_marker_sha256=hashlib.sha256(marker_before).hexdigest(), expected_manifest_sha256=hashlib.sha256(manifest_before).hexdigest(), expected_spec_sha256=hashlib.sha256(spec.read_bytes()).hexdigest(), expected_old_sha=old, reviewed_new_sha=new, reason="append rollback test")
    with pytest.raises(CliError, match="injected committed append/fsync failure"):
        recovery.recover_failed_prechain(spec, project, **kwargs)
    assert marker.read_bytes() == marker_before
    assert manifest.read_bytes() == manifest_before
    assert recovery._head(source) == old
    assert recovery._head(tmp_path / "staged") == new
    assert not recovery.chain_spec._state_path_for(spec).exists()
    events = [json.loads(line) for line in (project / ".megaplan" / "incident-ledger" / "events.jsonl").read_text().splitlines() if line.strip()]
    assert any(item.get("payload", {}).get("failure_class") == "committed_event_append_failed" for item in events)
    with pytest.raises(CliError, match="no durable terminal result"):
        recovery.recover_failed_prechain(spec, project, **kwargs)


def _held_recovery_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    (tmp_path / "source-repo").mkdir()
    source, old, new = _repo(tmp_path / "source-repo")
    engine = tmp_path / "engine"
    workspace = tmp_path / "workspace"
    subprocess.run(["git", "clone", "-q", str(source), str(engine)], check=True)
    subprocess.run(["git", "clone", "-q", str(source), str(workspace)], check=True)
    project = tmp_path / "native-build-forward-c2-test-session"
    spec = project / ".megaplan" / "initiatives" / "continuation" / "chain.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text("milestones: []\n", encoding="utf-8")
    marker = project / "marker.json"
    manifest = project / "manifest.json"
    marker.write_text(
        json.dumps(
            {
                "session": project.name,
                "workspace": str(workspace),
                "bootstrap_manifest_path": str(manifest),
                "launch_outcome": {"status": "failed", "code": "launch_not_advanced"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest.write_text("manifest-before\n", encoding="utf-8")
    current = SimpleNamespace(
        epic={"runtime_root": str(engine), "expected_head": old},
        generation=1,
    )
    monkeypatch.setattr(recovery, "load_manifest", lambda _path: current)
    custody = project / "custody"
    operation_id = "held-recovery-operation"
    evidence = custody / operation_id / "manifest.json"
    (workspace / "generated-reconcile.md").write_text("immutable failed-launch evidence\n", encoding="utf-8")
    evidence, _archive = recovery._archive_dirty_state(workspace, custody, operation_id)
    from arnold_pipelines.megaplan.incident.chain_control import ChainControlHold, chain_id_for_spec, journal_for

    journal = journal_for(project)
    chain_id = chain_id_for_spec(spec)
    journal.ensure_genesis(chain_id=chain_id, actor={"id": "operator", "class": "operator"}, spec_identity=str(spec))
    source_identity = {
        "old_sha": old,
        "new_sha": new,
        "reviewed_source": str(source),
        "chain_workspace": str(workspace),
        "engine_runtime": str(engine),
    }
    hold_result = journal.mutate(
        chain_id=chain_id,
        operation_id=operation_id,
        intent_kind=recovery.RECOVERY_INTENT,
        actor={"id": "operator", "class": "operator"},
        linked_receipts=[str(evidence)],
        spec_identity=str(spec),
        source_identity=source_identity,
        intent_context={
            "session": project.name,
            "old_sha": old,
            "new_sha": new,
            "reviewed_source": str(source),
            "chain_workspace": str(workspace),
            "engine_runtime": str(engine),
        },
        effect=lambda _txn: (_ for _ in ()).throw(
            ChainControlHold("source_cas_conflict", "archived dirty state differs")
        ),
    )
    # Avoid depending on a private journal projection: the hold is the durable
    # operation's latest event and its hash is the only accepted target.
    events = journal.replay_strict()["accepted"]
    hold = next(event for event in events if event.get("operation_id") == operation_id and event.get("event_kind") == "chain_control.hold")
    return {
        "source": source,
        "engine": engine,
        "workspace": workspace,
        "project": project,
        "spec": spec,
        "marker": marker,
        "manifest": manifest,
        "custody": custody,
        "evidence": evidence,
        "old": old,
        "new": new,
        "operation_id": operation_id,
        "chain_id": chain_id,
        "hold_hash": hold["event_hash"],
        "marker_sha": hashlib.sha256(marker.read_bytes()).hexdigest(),
        "manifest_sha": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "spec_sha": hashlib.sha256(spec.read_bytes()).hexdigest(),
    }


def test_reconcile_exact_held_prechain_operation_is_terminal_and_replayable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = _held_recovery_fixture(tmp_path, monkeypatch)
    kwargs = dict(
        marker_path=f["marker"], manifest_path=f["manifest"], source_path=f["source"],
        workspace_path=f["workspace"], custody_dir=f["custody"], held_operation_id=f["operation_id"],
        expected_hold_event_hash=f["hold_hash"], expected_session_id=f["project"].name,
        expected_marker_sha256=f["marker_sha"], expected_manifest_sha256=f["manifest_sha"],
        expected_spec_sha256=f["spec_sha"], expected_old_sha=f["old"], held_reviewed_new_sha=f["new"],
        recovery_evidence=f["evidence"], reason="reconcile exact held operation", actor="operator",
    )
    before = {path: path.read_bytes() for path in (f["marker"], f["manifest"], f["spec"])}
    first = recovery.reconcile_failed_prechain_hold(f["spec"], f["project"], **kwargs)
    assert first["outcome"] == "committed"
    from arnold_pipelines.megaplan.incident.chain_control import journal_for
    journal = journal_for(f["project"])
    replay = journal.replay_strict()
    assert replay["operations"][f["operation_id"]]["event_kind"] == "chain_control.hold_reconciled"
    from arnold_pipelines.megaplan.incident.chain_control import _incomplete_operation_statuses
    assert not _incomplete_operation_statuses(replay, f["chain_id"])
    assert not recovery.chain_spec._state_path_for(f["spec"]).exists()
    assert {path: path.read_bytes() for path in (f["marker"], f["manifest"], f["spec"])} == before
    second = recovery.reconcile_failed_prechain_hold(f["spec"], f["project"], **kwargs)
    assert second["outcome"] == "replay"


def test_reconcile_rejects_wrong_identity_and_existing_effect_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = _held_recovery_fixture(tmp_path, monkeypatch)
    kwargs = dict(
        marker_path=f["marker"], manifest_path=f["manifest"], source_path=f["source"],
        workspace_path=f["workspace"], custody_dir=f["custody"], held_operation_id=f["operation_id"],
        expected_hold_event_hash=f["hold_hash"], expected_session_id="wrong-session",
        expected_marker_sha256=f["marker_sha"], expected_manifest_sha256=f["manifest_sha"],
        expected_spec_sha256=f["spec_sha"], expected_old_sha=f["old"], held_reviewed_new_sha=f["new"],
        recovery_evidence=f["evidence"], reason="wrong identity", actor="operator",
    )
    events_before = (f["project"] / ".megaplan" / "incident-ledger" / "events.jsonl").read_bytes()
    kwargs["expected_session_id"] = f["project"].name
    kwargs["held_operation_id"] = "wrong-operation"
    with pytest.raises(CliError, match="does not belong to this chain"):
        recovery.reconcile_failed_prechain_hold(f["spec"], f["project"], **kwargs)
    kwargs["held_operation_id"] = f["operation_id"]
    kwargs["expected_session_id"] = "wrong-session"
    with pytest.raises(CliError, match="guarded session"):
        recovery.reconcile_failed_prechain_hold(f["spec"], f["project"], **kwargs)
    assert (f["project"] / ".megaplan" / "incident-ledger" / "events.jsonl").read_bytes() == events_before

    marker_before = f["marker"].read_bytes()
    marker = json.loads(marker_before)
    marker["failed_prechain_recovery"] = {"operation_id": "forged-effect"}
    f["marker"].write_text(json.dumps(marker) + "\n", encoding="utf-8")
    kwargs["expected_session_id"] = f["project"].name
    kwargs["expected_marker_sha256"] = hashlib.sha256(f["marker"].read_bytes()).hexdigest()
    with pytest.raises(CliError, match="effect is already present"):
        recovery.reconcile_failed_prechain_hold(f["spec"], f["project"], **kwargs)
