from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud import recovered_prechain_admission as admission
from arnold_pipelines.megaplan.incident.chain_control import (
    SCHEMA_VERSION,
    canonical_json,
    chain_id_for_spec,
    compute_event_hash,
    payload_digest_for,
)


SCHEMA = "arnold.megaplan.failed-prechain-recovery.v1"
NOW = "2026-09-03T06:00:00+00:00"
ORIGIN = "https://github.com/example/Arnold.git"


def _write(path: Path, value: object) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    path.write_bytes(raw)
    return raw


def _operation(
    session: str,
    manifest_before: str,
    old_sha: str,
    new_sha: str,
) -> str:
    identity = (
        f"failed_prechain_recovery\0{session}\0{manifest_before}\0{old_sha}\0{new_sha}"
    )
    return hashlib.sha256(identity.encode()).hexdigest()


def _journal_events(
    *,
    operation: str,
    chain_id: str,
    spec: str,
    session: str,
    old_sha: str,
    new_sha: str,
    reviewed_source: str,
    workspace: str,
    engine_runtime: str,
    actor: str,
    archive: str,
    archive_sha: str,
    receipt: str,
    marker_sha: str,
    manifest_sha: str,
) -> list[dict[str, Any]]:
    source_identity = {
        "old_sha": old_sha,
        "new_sha": new_sha,
        "reviewed_source": reviewed_source,
        "chain_workspace": workspace,
        "engine_runtime": engine_runtime,
    }
    context = {"session": session, **source_identity}
    payloads = [
        {
            "intent_kind": "failed_prechain_recovery",
            "expected_revision": None,
            **context,
        },
        {"intent_kind": "failed_prechain_recovery", **context},
        {
            "intent_kind": "failed_prechain_recovery",
            "claim": "single-use",
            **context,
        },
        {
            "intent_kind": "failed_prechain_recovery",
            "effect": {
                "source_old_sha": old_sha,
                "source_new_sha": new_sha,
                "staged_runtime": workspace,
                "manifest_generation": 2,
                "archive_manifest": {"path": archive, "sha256": archive_sha},
                "receipt": receipt,
                "marker_sha256": marker_sha,
                "manifest_sha256": manifest_sha,
                "chain_state": "absent",
                "linked_receipts": [archive, receipt],
            },
        },
    ]
    kinds = (
        "chain_control.intent",
        "chain_control.authority_validated",
        "chain_control.claimed",
        "chain_control.committed",
    )
    events: list[dict[str, Any]] = []
    previous_evidence = "1" * 64
    for index, (kind, payload) in enumerate(zip(kinds, payloads)):
        physical_sequence = 10 + index
        digest = payload_digest_for(payload)
        event_id = hashlib.sha256(
            canonical_json(
                [
                    kind,
                    operation,
                    str(physical_sequence),
                    digest,
                ]
            )
        ).hexdigest()
        event = {
            "schema_version": SCHEMA_VERSION,
            "event_id": event_id,
            "event_kind": kind,
            "operation_id": operation,
            "causation_id": operation if not events else events[-1]["event_id"],
            "correlation_id": operation,
            "recovery_id": "none",
            "chain_id": chain_id,
            "parent_chain_id": None,
            "child_id": None,
            "run_id": None,
            "actor": {"id": actor, "class": "operator"},
            "authority_mode": "file",
            "ledger_id": "ledger-test",
            "created_at": NOW,
            "physical_sequence": physical_sequence,
            "evidence_sequence": 20 + index,
            "semantic_sequence": 1,
            "previous_physical_digest": hashlib.sha256(
                f"physical-{index}".encode()
            ).hexdigest(),
            "previous_evidence_digest": previous_evidence,
            "payload_digest": digest,
            "event_hash": "",
            "intent": "failed_prechain_recovery",
            "semantic_effect": "no_change",
            "expected_cursor": None,
            "expected_revision": None,
            "actual_cursor": None,
            "actual_revision": None,
            "pre_state_digest": None,
            "post_state_digest": None,
            "source_identity": source_identity if index in (0, 3) else None,
            "spec_identity": spec if index in (0, 3) else None,
            "config_identity": None,
            "runtime_identity": None,
            "linked_receipts": [archive] if index == 3 else [],
            "outcome": "committed" if index == 3 else None,
            "failure_class": None,
            "claim_class": "required",
            "payload": payload,
        }
        event["event_hash"] = compute_event_hash(
            authority_mode=event["authority_mode"],
            ledger_id=event["ledger_id"],
            chain_id=event["chain_id"],
            physical_sequence=event["physical_sequence"],
            evidence_sequence=event["evidence_sequence"],
            semantic_sequence=event["semantic_sequence"],
            event_id=event["event_id"],
            event_kind=event["event_kind"],
            operation_id=event["operation_id"],
            causation_id=event["causation_id"],
            correlation_id=event["correlation_id"],
            recovery_id=event["recovery_id"],
            previous_physical_digest=event["previous_physical_digest"],
            previous_evidence_digest=event["previous_evidence_digest"],
            payload=event["payload"],
        )
        previous_evidence = event["event_hash"]
        events.append(event)
    return events


def _fixture(tmp_path: Path) -> dict[str, Any]:
    session = "native-build-forward-c2-test"
    slug = "native-build-forward-continuation-test"
    runtime = tmp_path / "old-engine"
    runtime.mkdir(parents=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    reviewed_source = str(tmp_path / "reviewed-source")
    engine_runtime = str(runtime)
    Path(reviewed_source).mkdir()
    marker = tmp_path / "cloud-sessions" / f"{session}.json"
    manifest = tmp_path / "manifests" / f"{slug}.json"
    state = tmp_path / "chain-state.json"
    spec = str(tmp_path / "initiatives" / "test" / "chain.yaml")
    new_sha = "a" * 40
    old_sha = "c" * 40
    manifest_before = "e" * 64
    operation = _operation(session, manifest_before, old_sha, new_sha)
    reason = "admit reviewed recovery"
    actor = "operator-test"
    branch = "fixer/test"
    manifest_value = {
        "runtime_id": "runtime-test-1",
        "schema": "1",
        "generation": 2,
        "epic_id": slug,
        "state": "active",
        "owner": "test-owner",
        "base": {
            "ref": "main",
            "commit": new_sha,
            "editable_install_path": "",
            "venv_path": "/tmp/generation",
            "origin_url": ORIGIN,
        },
        "epic": {
            "branch": branch,
            "worktree_path": str(workspace),
            "venv_path": "/tmp/generation",
            "runtime_root": str(workspace),
            "expected_head": new_sha,
            "repair_bin": str(workspace / "arnold-babysitter"),
            "deps_lockfile": str(workspace / "uv.lock"),
            "origin_url": ORIGIN,
            "dependency_generation": {
                "id": "f" * 64,
                "frozen_spec_sha256": "f" * 64,
                "interpreter_path": "/tmp/generation/bin/python",
                "venv_digest": "d" * 64,
                "created": NOW,
            },
        },
        "indirection": {
            "host_path": str(workspace),
            "container_path": "",
            "mount_table": [],
            "execution_namespace": "",
            "verified_head": new_sha,
            "last_verified_at": NOW,
            "attestation": {
                "module_file": str(workspace / "arnold_pipelines" / "__init__.py"),
                "module_digest": "2" * 64,
                "mount_id": "mount-test",
            },
        },
        "policy": {
            "policy_sha": "3" * 64,
            "model_policy_sha": "4" * 64,
            "sync_policy": {},
        },
        "promotions": [
            {
                "previous_generation": 1,
                "previous_commit": old_sha,
                "previous_runtime_root": engine_runtime,
                "previous_venv_path": "/tmp/old-generation",
                "previous_repair_bin": str(Path(engine_runtime) / "arnold-babysitter"),
                "reason": reason,
                "at": NOW,
            }
        ],
        "timestamps": {"created": NOW, "updated": NOW, "closed": None},
        "gc_policy": {"closed_only": True, "restore_proven_required": True},
        "commands": [],
        "deviations": [],
        "compatibility_only": False,
    }
    manifest_raw = _write(manifest, manifest_value)
    archive = tmp_path / "custody" / operation / "manifest.json"
    tracked = b"diff --git a/dirty.txt b/dirty.txt\n"
    tracked_path = archive.parent / "tracked.diff"
    tracked_path.parent.mkdir(parents=True)
    tracked_path.write_bytes(tracked)
    archive_value = {
        "schema": SCHEMA,
        "operation_id": operation,
        "source_head": old_sha,
        "status": [" M dirty.txt"],
        "worktree_fingerprint": [
            {
                "path": "dirty.txt",
                "status": " M",
                "kind": "file",
                "sha256": "5" * 64,
                "size": 1,
            }
        ],
        "entries": [
            {
                "path": "tracked.diff",
                "sha256": hashlib.sha256(tracked).hexdigest(),
                "size": len(tracked),
            }
        ],
        "created_at": NOW,
    }
    archive_raw = _write(archive, archive_value)
    (archive.parent / "failed-workspace").mkdir()
    launch_outcome = {"status": "failed", "code": "launch_not_advanced"}
    marker_value = {
        "session": session,
        "workspace": str(workspace),
        "remote_spec": spec,
        "bootstrap_manifest_path": str(manifest),
        "should_run": True,
        "operator_pause": None,
        "launch_outcome": launch_outcome,
        "launch_outcome_history": [launch_outcome],
        "failed_prechain_recovery": {
            "schema": SCHEMA,
            "operation_id": operation,
            "old_sha": old_sha,
            "new_sha": new_sha,
            "reviewed_source": reviewed_source,
            "chain_workspace": str(workspace),
            "engine_runtime_before": engine_runtime,
            "engine_runtime_after": str(workspace),
            "archive_manifest": {
                "path": str(archive),
                "sha256": hashlib.sha256(archive_raw).hexdigest(),
            },
            "manifest_generation": 2,
            "reason": reason,
            "actor": actor,
        },
    }
    marker_raw = _write(marker, marker_value)
    receipt_path = archive.parent / "recovery-receipt.json"
    receipt_value = {
        "schema": SCHEMA,
        "operation_id": operation,
        "session": session,
        "chain_id": chain_id_for_spec(Path(spec)),
        "marker": {
            "path": str(marker),
            "before_sha256": "9" * 64,
            "after_sha256": hashlib.sha256(marker_raw).hexdigest(),
        },
        "manifest": {
            "path": str(manifest),
            "before_sha256": manifest_before,
            "after_sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "generation": 2,
        },
        "source": {"path": reviewed_source, "old_sha": old_sha, "new_sha": new_sha},
        "staged_runtime": str(workspace),
        "preserved_failed_workspace": str(archive.parent / "failed-workspace"),
        "workspace": str(workspace),
        "engine_runtime": {"old_path": engine_runtime, "new_path": str(workspace)},
        "archive_manifest": {
            "path": str(archive),
            "sha256": hashlib.sha256(archive_raw).hexdigest(),
        },
        "launch_outcome": launch_outcome,
        "outcome": "recovered",
        "created_at": NOW,
    }
    _write(receipt_path, receipt_value)
    events = _journal_events(
        operation=operation,
        chain_id=chain_id_for_spec(Path(spec)),
        spec=spec,
        session=session,
        old_sha=old_sha,
        new_sha=new_sha,
        reviewed_source=reviewed_source,
        workspace=str(workspace),
        engine_runtime=engine_runtime,
        actor=actor,
        archive=str(archive),
        archive_sha=hashlib.sha256(archive_raw).hexdigest(),
        receipt=str(receipt_path),
        marker_sha=hashlib.sha256(marker_raw).hexdigest(),
        manifest_sha=hashlib.sha256(manifest_raw).hexdigest(),
    )
    ledger = workspace / ".megaplan" / "incident-ledger" / "events.jsonl"
    _write(ledger, {"fixture": "strict replay is supplied by the test"})
    lease = marker.parent / f"{session}.liveness-lease.json"
    _write(
        lease,
        {
            "session": session,
            "status": "stopped",
            "workspace": str(workspace),
            "remote_spec": spec,
            "expires_at": "2000-01-01T00:00:00Z",
            "marker_binding": f"sha256:{hashlib.sha256(marker_raw).hexdigest()}",
            "target_pid": 999999,
        },
    )
    fence = marker.parent / f".{session}.liveness-fence.json"
    _write(fence, {"session": session, "status": "stopped"})
    return {
        "manifest": manifest,
        "marker": marker,
        "state": state,
        "runtime": runtime,
        "workspace": workspace,
        "session": session,
        "slug": slug,
        "spec": spec,
        "lease": lease,
        "fence": fence,
        "new_sha": new_sha,
        "old_sha": old_sha,
        "operation": operation,
        "archive": archive,
        "receipt": receipt_path,
        "ledger": ledger,
        "events": events,
        "branch": branch,
        "origin": ORIGIN,
    }


def _run_admit(fixture: dict[str, Any]) -> None:
    admission._admit(
        manifest_path=fixture["manifest"],
        marker_path=fixture["marker"],
        state_path=fixture["state"],
        runtime_src=str(fixture["runtime"]),
        session=fixture["session"],
        slug=fixture["slug"],
        expected_spec=fixture["spec"],
        expected_workspace=str(fixture["workspace"]),
        canonical_origin=fixture["origin"],
    )


def _mock_external_authorities(
    monkeypatch: pytest.MonkeyPatch,
    fixture: dict[str, Any],
) -> None:
    events = fixture["events"]

    class Journal:
        def replay_strict(self) -> dict[str, Any]:
            return {
                "accepted": events,
                "operations": {fixture["operation"]: events[-1]},
                "torn_tail": False,
            }

    monkeypatch.setattr(admission, "journal_for", lambda _root: Journal())

    def git_identity(runtime: Path, *args: Any, **kwargs: Any) -> tuple[str, ...]:
        fixture.setdefault("git_paths", []).append(runtime)
        return (
            fixture["new_sha"],
            "8" * 40,
            fixture["origin"],
            fixture["branch"],
        )

    monkeypatch.setattr(
        admission,
        "_git_identity",
        git_identity,
    )
    real_run = subprocess.run

    def run(
        command: list[str], *args: Any, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if command[0] == "tmux":
            return subprocess.CompletedProcess(command, 1, "", "")
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(admission.subprocess, "run", run)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _descend(value: Any, path: tuple[str | int, ...]) -> tuple[Any, str | int]:
    parent = value
    for key in path[:-1]:
        parent = parent[key]
    return parent, path[-1]


def _changed(value: Any) -> Any:
    if value is None:
        return "tampered"
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, str):
        return "tampered"
    if isinstance(value, list):
        return ["tampered"]
    if isinstance(value, dict):
        return {"tampered": True}
    raise AssertionError(f"unsupported fixture value {value!r}")


MARKER_AUTHORITY = (
    ("session",),
    ("workspace",),
    ("remote_spec",),
    ("bootstrap_manifest_path",),
    ("should_run",),
    ("launch_outcome", "status"),
    ("launch_outcome", "code"),
    ("launch_outcome_history",),
    ("failed_prechain_recovery", "schema"),
    ("failed_prechain_recovery", "operation_id"),
    ("failed_prechain_recovery", "old_sha"),
    ("failed_prechain_recovery", "new_sha"),
    ("failed_prechain_recovery", "reviewed_source"),
    ("failed_prechain_recovery", "chain_workspace"),
    ("failed_prechain_recovery", "engine_runtime_before"),
    ("failed_prechain_recovery", "engine_runtime_after"),
    ("failed_prechain_recovery", "archive_manifest", "path"),
    ("failed_prechain_recovery", "archive_manifest", "sha256"),
    ("failed_prechain_recovery", "manifest_generation"),
    ("failed_prechain_recovery", "reason"),
    ("failed_prechain_recovery", "actor"),
)
MANIFEST_AUTHORITY = (
    ("runtime_id",),
    ("schema",),
    ("generation",),
    ("epic_id",),
    ("state",),
    ("owner",),
    ("compatibility_only",),
    ("base", "ref"),
    ("base", "commit"),
    ("base", "editable_install_path"),
    ("base", "venv_path"),
    ("base", "origin_url"),
    ("epic", "branch"),
    ("epic", "worktree_path"),
    ("epic", "venv_path"),
    ("epic", "runtime_root"),
    ("epic", "expected_head"),
    ("epic", "repair_bin"),
    ("epic", "deps_lockfile"),
    ("epic", "origin_url"),
    ("epic", "dependency_generation", "id"),
    ("epic", "dependency_generation", "frozen_spec_sha256"),
    ("epic", "dependency_generation", "interpreter_path"),
    ("epic", "dependency_generation", "venv_digest"),
    ("epic", "dependency_generation", "created"),
    ("indirection", "host_path"),
    ("indirection", "container_path"),
    ("indirection", "mount_table"),
    ("indirection", "execution_namespace"),
    ("indirection", "verified_head"),
    ("indirection", "last_verified_at"),
    ("indirection", "attestation", "module_file"),
    ("indirection", "attestation", "module_digest"),
    ("indirection", "attestation", "mount_id"),
    ("policy", "policy_sha"),
    ("policy", "model_policy_sha"),
    ("policy", "sync_policy"),
    ("promotions", 0, "previous_generation"),
    ("promotions", 0, "previous_commit"),
    ("promotions", 0, "previous_runtime_root"),
    ("promotions", 0, "previous_venv_path"),
    ("promotions", 0, "previous_repair_bin"),
    ("promotions", 0, "reason"),
    ("promotions", 0, "at"),
    ("timestamps", "created"),
    ("timestamps", "updated"),
    ("timestamps", "closed"),
    ("gc_policy",),
    ("commands",),
)
ARCHIVE_AUTHORITY = (
    ("schema",),
    ("operation_id",),
    ("source_head",),
    ("status",),
    ("worktree_fingerprint", 0, "path"),
    ("worktree_fingerprint", 0, "status"),
    ("worktree_fingerprint", 0, "kind"),
    ("worktree_fingerprint", 0, "sha256"),
    ("worktree_fingerprint", 0, "size"),
    ("entries", 0, "path"),
    ("entries", 0, "sha256"),
    ("entries", 0, "size"),
    ("created_at",),
)
RECEIPT_AUTHORITY = (
    ("schema",),
    ("operation_id",),
    ("session",),
    ("chain_id",),
    ("marker", "path"),
    ("marker", "before_sha256"),
    ("marker", "after_sha256"),
    ("manifest", "path"),
    ("manifest", "before_sha256"),
    ("manifest", "after_sha256"),
    ("manifest", "generation"),
    ("source", "path"),
    ("source", "old_sha"),
    ("source", "new_sha"),
    ("staged_runtime",),
    ("preserved_failed_workspace",),
    ("workspace",),
    ("engine_runtime", "old_path"),
    ("engine_runtime", "new_path"),
    ("archive_manifest", "path"),
    ("archive_manifest", "sha256"),
    ("launch_outcome", "status"),
    ("launch_outcome", "code"),
    ("outcome",),
    ("created_at",),
)
JOURNAL_ENVELOPE_AUTHORITY = (
    "schema_version",
    "event_id",
    "event_hash",
    "event_kind",
    "operation_id",
    "causation_id",
    "correlation_id",
    "recovery_id",
    "chain_id",
    "actor",
    "authority_mode",
    "ledger_id",
    "physical_sequence",
    "evidence_sequence",
    "semantic_sequence",
    "previous_physical_digest",
    "previous_evidence_digest",
    "payload_digest",
    "intent",
    "semantic_effect",
    "source_identity",
    "spec_identity",
    "linked_receipts",
    "outcome",
    "claim_class",
)
JOURNAL_PAYLOAD_AUTHORITY = tuple(
    (index, "payload", key)
    for index, keys in enumerate(
        (
            (
                "intent_kind",
                "expected_revision",
                "session",
                "old_sha",
                "new_sha",
                "reviewed_source",
                "chain_workspace",
                "engine_runtime",
            ),
            (
                "intent_kind",
                "session",
                "old_sha",
                "new_sha",
                "reviewed_source",
                "chain_workspace",
                "engine_runtime",
            ),
            (
                "intent_kind",
                "claim",
                "session",
                "old_sha",
                "new_sha",
                "reviewed_source",
                "chain_workspace",
                "engine_runtime",
            ),
        )
    )
    for key in keys
) + tuple(
    (3, "payload", "effect", key)
    for key in (
        "source_old_sha",
        "source_new_sha",
        "staged_runtime",
        "manifest_generation",
        "archive_manifest",
        "receipt",
        "marker_sha256",
        "manifest_sha256",
        "chain_state",
        "linked_receipts",
    )
)
JOURNAL_AUTHORITY = (
    tuple((index, key) for index in range(4) for key in JOURNAL_ENVELOPE_AUTHORITY)
    + JOURNAL_PAYLOAD_AUTHORITY
)
TAMPER_CASES = tuple(
    (artifact, path, mutation)
    for artifact, paths in (
        ("marker", MARKER_AUTHORITY),
        ("manifest", MANIFEST_AUTHORITY),
        ("archive", ARCHIVE_AUTHORITY),
        ("receipt", RECEIPT_AUTHORITY),
        ("journal", JOURNAL_AUTHORITY),
    )
    for path in paths
    for mutation in ("delete", "change")
)


def _case_id(case: tuple[str, tuple[str | int, ...], str]) -> str:
    artifact, path, mutation = case
    return f"{artifact}-{'.'.join(map(str, path))}-{mutation}"


@pytest.mark.parametrize(
    "artifact,path,mutation",
    TAMPER_CASES,
    ids=[_case_id(case) for case in TAMPER_CASES],
)
def test_every_recovery_authority_field_fails_closed_when_tampered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact: str,
    path: tuple[str | int, ...],
    mutation: str,
) -> None:
    fixture = _fixture(tmp_path)
    _mock_external_authorities(monkeypatch, fixture)
    if artifact == "journal":
        value = fixture["events"]
    else:
        artifact_path = fixture[artifact]
        value = _load(artifact_path)
    parent, key = _descend(value, path)
    if mutation == "delete":
        del parent[key]
    else:
        parent[key] = _changed(parent[key])
    if artifact != "journal":
        _write(artifact_path, value)
    with pytest.raises(SystemExit) as exc:
        _run_admit(fixture)
    assert exc.value.code == 78


def test_recovered_prechain_marker_is_admitted_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    _mock_external_authorities(monkeypatch, fixture)
    paths = (
        fixture["marker"],
        fixture["manifest"],
        fixture["archive"],
        fixture["receipt"],
        fixture["ledger"],
        fixture["lease"],
        fixture["fence"],
        fixture["archive"].parent / "tracked.diff",
    )
    before = {path: path.read_bytes() for path in paths}
    _run_admit(fixture)
    assert {path: path.read_bytes() for path in paths} == before
    assert not fixture["state"].exists()
    assert fixture["git_paths"] == [fixture["workspace"], fixture["workspace"]]


def test_authority_change_during_admission_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    _mock_external_authorities(monkeypatch, fixture)
    calls = 0

    def mutate_after_attestation(*args: Any, **kwargs: Any) -> tuple[str, ...]:
        nonlocal calls
        calls += 1
        if calls == 1:
            fixture["receipt"].write_bytes(fixture["receipt"].read_bytes() + b" ")
        return fixture["new_sha"], "8" * 40, fixture["origin"], fixture["branch"]

    monkeypatch.setattr(admission, "_git_identity", mutate_after_attestation)
    with pytest.raises(SystemExit) as exc:
        _run_admit(fixture)
    assert exc.value.code == 78


def test_ordinary_existing_marker_is_not_admitted(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    marker = _load(fixture["marker"])
    marker.pop("failed_prechain_recovery")
    _write(fixture["marker"], marker)
    with pytest.raises(SystemExit) as exc:
        _run_admit(fixture)
    assert exc.value.code == 77


@pytest.mark.parametrize("identity", ["spec", "workspace", "origin"])
def test_recovered_prechain_requires_every_external_identity(
    tmp_path: Path,
    identity: str,
) -> None:
    fixture = _fixture(tmp_path)
    kwargs = {
        "manifest_path": fixture["manifest"],
        "marker_path": fixture["marker"],
        "state_path": fixture["state"],
        "runtime_src": str(fixture["runtime"]),
        "session": fixture["session"],
        "slug": fixture["slug"],
        "expected_spec": fixture["spec"],
        "expected_workspace": str(fixture["workspace"]),
        "canonical_origin": fixture["origin"],
    }
    argument = {
        "spec": "expected_spec",
        "workspace": "expected_workspace",
        "origin": "canonical_origin",
    }[identity]
    kwargs[argument] = None
    with pytest.raises(SystemExit) as exc:
        admission._admit(**kwargs)
    assert exc.value.code == 78


def _git_runtime(tmp_path: Path) -> tuple[Path, str]:
    runtime = tmp_path / "git-runtime"
    runtime.mkdir()
    subprocess.run(["git", "init", "-q", str(runtime)], check=True)
    subprocess.run(
        ["git", "-C", str(runtime), "config", "user.name", "test"], check=True
    )
    subprocess.run(
        ["git", "-C", str(runtime), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    (runtime / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(runtime), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(runtime), "commit", "-qm", "initial"], check=True)
    subprocess.run(
        ["git", "-C", str(runtime), "branch", "-M", "fixer/test"], check=True
    )
    subprocess.run(
        ["git", "-C", str(runtime), "remote", "add", "origin", ORIGIN], check=True
    )
    head = subprocess.run(
        ["git", "-C", str(runtime), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return runtime, head


def test_git_identity_requires_exact_attached_declared_branch(tmp_path: Path) -> None:
    runtime, head = _git_runtime(tmp_path)
    assert (
        admission._git_identity(
            runtime,
            expected_head=head,
            expected_branch="fixer/test",
            canonical_origin=ORIGIN,
        )[3]
        == "fixer/test"
    )

    subprocess.run(
        ["git", "-C", str(runtime), "checkout", "--detach", "-q"], check=True
    )
    with pytest.raises(SystemExit) as detached:
        admission._git_identity(
            runtime,
            expected_head=head,
            expected_branch="fixer/test",
            canonical_origin=ORIGIN,
        )
    assert detached.value.code == 78


def test_git_identity_rejects_wrong_branch_origin_head_and_dirty_tree(
    tmp_path: Path,
) -> None:
    runtime, head = _git_runtime(tmp_path)
    subprocess.run(["git", "-C", str(runtime), "branch", "other"], check=True)
    checks = (
        {"expected_head": head, "expected_branch": "other", "canonical_origin": ORIGIN},
        {
            "expected_head": head,
            "expected_branch": "fixer/test",
            "canonical_origin": ORIGIN + "/wrong",
        },
        {
            "expected_head": "0" * 40,
            "expected_branch": "fixer/test",
            "canonical_origin": ORIGIN,
        },
    )
    for kwargs in checks:
        with pytest.raises(SystemExit) as exc:
            admission._git_identity(runtime, **kwargs)
        assert exc.value.code == 78
    (runtime / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(SystemExit) as dirty:
        admission._git_identity(
            runtime,
            expected_head=head,
            expected_branch="fixer/test",
            canonical_origin=ORIGIN,
        )
    assert dirty.value.code == 78


@pytest.mark.parametrize("change", ["pid", "lease", "fence", "state"])
def test_recovered_prechain_rejects_live_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    fixture = _fixture(tmp_path)
    _mock_external_authorities(monkeypatch, fixture)
    if change == "pid":
        marker = _load(fixture["marker"])
        marker["pid"] = 1
        _write(fixture["marker"], marker)
    elif change == "lease":
        lease = _load(fixture["lease"])
        lease["status"] = "running"
        _write(fixture["lease"], lease)
    elif change == "fence":
        fence = _load(fixture["fence"])
        fence["owner_pid"] = 1
        _write(fixture["fence"], fence)
    else:
        _write(fixture["state"], {})
    with pytest.raises(SystemExit) as exc:
        _run_admit(fixture)
    assert exc.value.code == 78
