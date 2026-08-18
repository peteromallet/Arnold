"""P1 admission kernel: expiring ``allow_manifestless`` permit records and the
``require_runtime_manifest_permit`` chain admission gate.

Settled contract (2026-08-09, codex-approved): a session that binds a runtime
manifest (per-session, never the global pointer) must carry a present+valid
manifest; a manifestless session must carry a valid unexpired
``allow_manifestless`` permit. Permits validate
``0 < expires_at - issued_at <= 24h`` and current-unexpired at admission;
revocation is an auditable ``revoked_at`` tombstone, never a silent delete;
expired records stay loadable but never admit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.chain import run_chain_cli
from arnold_pipelines.megaplan.chain import spec as chain_spec_module
from arnold_pipelines.megaplan.chain.spec import (
    PERMIT_KIND_ALLOW_MANIFESTLESS,
    RUNTIME_MANIFEST_BINDING_ENV,
    TRUSTED_CONTAINER_ENV,
    active_allow_manifestless_permit,
    chain_spec_sha256,
    has_valid_allow_manifestless_permit,
    issue_allow_manifestless_permit,
    require_runtime_manifest_permit,
    revoke_allow_manifestless_permit,
    runtime_policy_sidecar_path,
    session_runtime_manifest_path,
)
from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    COMPATIBILITY_ONLY_KEY,
    manifest_present,
)
from arnold_pipelines.megaplan.types import CliError


def _chain(tmp_path: Path) -> Path:
    """A minimal valid chain spec: `.megaplan/initiatives/demo/chain.yaml`."""
    initiative = tmp_path / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    (initiative / "brief.md").write_text("# brief\n", encoding="utf-8")
    spec = initiative / "chain.yaml"
    spec.write_text(
        "anchors:\n  north_star: brief.md\nmilestones: []\n",
        encoding="utf-8",
    )
    return spec


def _valid_manifest() -> dict[str, object]:
    """A fully valid runtime manifest (schema "1") for gate-pass tests."""
    return {
        "runtime_id": "runtime-test-1",
        "schema": "1",
        "generation": 3,
        "epic_id": "epic-demo",
        "state": "active",
        "owner": "superfixer",
        "base": {
            "ref": "refs/heads/base/editable-install",
            "commit": "87a912beb",
            "editable_install_path": "/opt/arnold/base",
            "venv_path": "/opt/arnold/base/venv",
        },
        "epic": {
            "branch": "fixer/epic-demo-20260807",
            "worktree_path": "/opt/arnold/runtime-candidates/epic-demo",
            "venv_path": "/opt/arnold/runtime-candidates/epic-demo/venv",
            "runtime_root": "/opt/arnold/runtime-candidates/epic-demo/runtime",
            "expected_head": "abc123def",
            "repair_bin": "/opt/arnold/runtime-candidates/epic-demo/venv/bin/arnold-babysitter",
            "deps_lockfile": "/opt/arnold/base/uv.lock",
        },
        "indirection": {
            "host_path": "/opt/arnold/runtime-candidates/epic-demo",
            "container_path": "/workspace/epic-demo",
            "mount_table": [],
            "execution_namespace": "epic-demo-ns",
            "verified_head": "abc123def",
            "last_verified_at": "2026-08-07T00:00:00+00:00",
            "attestation": {
                "module_file": "/opt/arnold/runtime-candidates/epic-demo/arnold_pipelines/__init__.py",
                "module_digest": "d41d8cd98f00b204e9800998ecf8427e",
                "mount_id": "0:42",
            },
        },
        "policy": {
            "policy_sha": "policy-sha-1",
            "model_policy_sha": "model-sha-1",
            "sync_policy": "push-on-promote",
        },
        "promotions": [],
        "timestamps": {
            "created": "2026-08-07T00:00:00+00:00",
            "updated": "2026-08-07T00:00:00+00:00",
            "closed": "",
        },
        "gc_policy": "closed-only",
        "commands": ["megaplan chain"],
    }


def _utc(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat(timespec="seconds")


def _write_manifest(path: Path, manifest: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _record(**overrides: object) -> dict[str, object]:
    """A structurally valid, currently-unexpired permit record."""
    record: dict[str, object] = {
        "kind": PERMIT_KIND_ALLOW_MANIFESTLESS,
        "id": "perm-0001",
        "issued_at": _utc(timedelta(0)),
        "expires_at": _utc(timedelta(hours=1)),
        "actor": "operator",
        "reason": "box migration window",
        "evidence": ["incident-42", "approval-email"],
        "chain_digest": "sha256:deadbeef",
    }
    record.update(overrides)
    return record


def _write_expired_record(spec_path: Path) -> None:
    """Plant an EXPIRED permit directly in the sidecar (admission-time only)."""
    chain_spec_module._save_runtime_permit_records(
        spec_path,
        [
            {
                "kind": PERMIT_KIND_ALLOW_MANIFESTLESS,
                "id": "perm-expired",
                "issued_at": _utc(timedelta(hours=-2)),
                "expires_at": _utc(timedelta(hours=-1)),
                "actor": "operator",
                "reason": "already elapsed",
                "evidence": [],
                "chain_digest": "sha256:deadbeef",
            }
        ],
    )


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _git_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com", "add", ".")
    _git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "fixture",
    )


# ── permit write / read / expiry round-trip ─────────────────────────────────


def test_permit_write_read_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    monkeypatch.delenv(TRUSTED_CONTAINER_ENV, raising=False)
    spec = _chain(tmp_path)

    issued = issue_allow_manifestless_permit(
        spec,
        reason="migration window",
        expires_at=_utc(timedelta(hours=2)),
        actor="operator",
        evidence=["incident-42", "approval-email"],
    )

    # written to the sidecar with the settled shape
    sidecar = runtime_policy_sidecar_path(spec)
    assert sidecar.exists()
    raw = json.loads(sidecar.read_text(encoding="utf-8"))
    assert raw["permits"] == [issued]
    for field in (
        "kind",
        "id",
        "issued_at",
        "expires_at",
        "actor",
        "reason",
        "evidence",
        "chain_digest",
    ):
        assert issued[field]
    assert issued["kind"] == PERMIT_KIND_ALLOW_MANIFESTLESS
    assert issued["chain_digest"] == chain_spec_sha256(spec)
    assert isinstance(issued["evidence"], list) and all(
        isinstance(item, str) for item in issued["evidence"]
    )

    # readable back as the active permit; gate passes on it
    assert active_allow_manifestless_permit(spec) == issued
    assert has_valid_allow_manifestless_permit(spec) is True
    require_runtime_manifest_permit(spec)


def test_expired_permit_stays_loadable_but_never_admits(
    tmp_path: Path, monkeypatch
) -> None:
    # bind a (missing) session manifest so the admission gate is in force
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(tmp_path / "missing.json"))
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    spec = _chain(tmp_path)
    _write_expired_record(spec)

    # the expired record is still loadable from the sidecar
    records = chain_spec_module._load_runtime_permit_records(spec)
    assert len(records) == 1
    assert records[0]["kind"] == PERMIT_KIND_ALLOW_MANIFESTLESS

    # but it never admits
    assert active_allow_manifestless_permit(spec) is None
    assert has_valid_allow_manifestless_permit(spec) is False
    with pytest.raises(CliError, match="no runtime manifest is bound"):
        require_runtime_manifest_permit(spec)


# ── permit validation: TTL, missing fields, malformed timestamps ────────────


def test_permit_rejects_lifetime_over_24h(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    spec = _chain(tmp_path)
    with pytest.raises(CliError) as exc_info:
        issue_allow_manifestless_permit(
            spec,
            reason="too long",
            expires_at=_utc(timedelta(hours=25)),
            actor="operator",
            evidence=[],
        )
    assert exc_info.value.code == "invalid_permit"
    assert active_allow_manifestless_permit(spec) is None


def test_permit_rejects_zero_or_negative_lifetime(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    spec = _chain(tmp_path)
    with pytest.raises(CliError) as exc_info:
        issue_allow_manifestless_permit(
            spec,
            reason="no lifetime",
            expires_at=_utc(timedelta(seconds=-5)),
            actor="operator",
            evidence=[],
        )
    assert exc_info.value.code == "invalid_permit"
    assert active_allow_manifestless_permit(spec) is None


def test_permit_rejects_missing_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    spec = _chain(tmp_path)
    # public boundary: empty reason/actor/expires_at are rejected
    for field, value in (("reason", ""), ("actor", ""), ("expires_at", "")):
        with pytest.raises(CliError) as exc_info:
            issue_allow_manifestless_permit(
                spec,
                reason="r" if field != "reason" else value,
                expires_at=_utc(timedelta(hours=1)) if field != "expires_at" else value,
                actor="a" if field != "actor" else value,
                evidence=[],
            )
        assert exc_info.value.code == "invalid_permit"
    # record-level: every settled field is required by the shared validator
    for field in (
        "kind",
        "id",
        "issued_at",
        "expires_at",
        "actor",
        "reason",
        "evidence",
        "chain_digest",
    ):
        bad = dict(_record())
        del bad[field]
        with pytest.raises(CliError) as exc_info:
            chain_spec_module._validate_permit_record(bad)
        assert exc_info.value.code == "invalid_permit"


def test_permit_rejects_malformed_expires_at(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    spec = _chain(tmp_path)
    with pytest.raises(CliError) as exc_info:
        issue_allow_manifestless_permit(
            spec,
            reason="bad date",
            expires_at="not-a-date",
            actor="operator",
            evidence=[],
        )
    assert exc_info.value.code == "invalid_permit"
    # naive timestamps (no UTC offset) are rejected
    with pytest.raises(CliError) as exc_info:
        issue_allow_manifestless_permit(
            spec,
            reason="naive",
            expires_at="2026-08-10T12:00:00",
            actor="operator",
            evidence=[],
        )
    assert exc_info.value.code == "invalid_permit"
    assert active_allow_manifestless_permit(spec) is None


# ── revocation: auditable tombstone, never a silent delete ──────────────────


def test_revoke_stamps_tombstone_and_keeps_record(tmp_path: Path, monkeypatch) -> None:
    # bind a (missing) session manifest so the admission gate is in force
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(tmp_path / "missing.json"))
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    spec = _chain(tmp_path)
    issued = issue_allow_manifestless_permit(
        spec,
        reason="migration",
        expires_at=_utc(timedelta(hours=1)),
        actor="operator",
        evidence=[],
    )

    tombstoned = revoke_allow_manifestless_permit(spec)
    assert tombstoned is not None
    assert tombstoned["id"] == issued["id"]
    assert tombstoned["revoked_at"]

    # the record is STILL in the sidecar (auditable), just tombstoned
    records = chain_spec_module._load_runtime_permit_records(spec)
    assert records == [tombstoned]
    assert records[0]["revoked_at"]

    # a revoked permit never admits, and revoking again reports no active one
    assert active_allow_manifestless_permit(spec) is None
    with pytest.raises(CliError, match="no runtime manifest is bound"):
        require_runtime_manifest_permit(spec)
    assert revoke_allow_manifestless_permit(spec) is None


# ── the admission gate ──────────────────────────────────────────────────────


def test_gate_passes_with_valid_bound_manifest(tmp_path: Path, monkeypatch) -> None:
    spec = _chain(tmp_path)
    manifest = _write_manifest(
        tmp_path / "runtime" / "runtime-manifest.json", _valid_manifest()
    )
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(manifest))
    require_runtime_manifest_permit(spec)  # no permit needed


def test_gate_passes_with_valid_permit_bound_manifestless(
    tmp_path: Path, monkeypatch
) -> None:
    spec = _chain(tmp_path)
    # bound to a manifest path that does not exist on disk => manifestless
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(tmp_path / "missing.json"))
    issue_allow_manifestless_permit(
        spec,
        reason="migration window",
        expires_at=_utc(timedelta(hours=1)),
        actor="operator",
        evidence=["incident-42"],
    )
    # the permit lives next to the session manifest, where bash also reads it
    assert (tmp_path / ".runtime_policy.json").exists()
    require_runtime_manifest_permit(spec)


def test_gate_inert_without_session_binding(tmp_path: Path, monkeypatch) -> None:
    """No session binding and no trusted container => no runtime regime in
    force: the gate passes even with no manifest and no permit (legacy local
    operation is preserved; enforcement is enabled per session by binding a
    manifest, or unconditionally by MEGAPLAN_TRUSTED_CONTAINER=1)."""
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    monkeypatch.delenv(TRUSTED_CONTAINER_ENV, raising=False)
    spec = _chain(tmp_path)
    assert session_runtime_manifest_path() is None
    require_runtime_manifest_permit(spec)


def test_gate_denies_absent_without_permit(tmp_path: Path, monkeypatch) -> None:
    spec = _chain(tmp_path)
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(tmp_path / "missing.json"))
    with pytest.raises(CliError, match="no runtime manifest is bound"):
        require_runtime_manifest_permit(spec)


def test_gate_denies_expired_permit(tmp_path: Path, monkeypatch) -> None:
    spec = _chain(tmp_path)
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(tmp_path / "missing.json"))
    _write_expired_record(spec)
    with pytest.raises(CliError, match="no runtime manifest is bound"):
        require_runtime_manifest_permit(spec)


def test_gate_denies_invalid_bound_manifest_even_with_permit(
    tmp_path: Path, monkeypatch
) -> None:
    spec = _chain(tmp_path)
    manifest = _write_manifest(tmp_path / "runtime" / "runtime-manifest.json", {})
    manifest.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(manifest))
    issue_allow_manifestless_permit(
        spec,
        reason="permit must not rescue a broken manifest",
        expires_at=_utc(timedelta(hours=1)),
        actor="operator",
        evidence=[],
    )
    with pytest.raises(CliError, match="bound runtime manifest is invalid"):
        require_runtime_manifest_permit(spec)


def test_gate_denies_dangling_symlink_manifest_even_with_permit(
    tmp_path: Path, monkeypatch
) -> None:
    """A DANGLING symlink at the bound manifest path is PRESENT but unreadable
    — the gate fails closed with ``runtime_manifest_invalid`` and NEVER
    reaches the manifestless permit (which authorizes only a genuinely absent
    file, G5 round-12)."""
    spec = _chain(tmp_path)
    dangling = tmp_path / "runtime" / "runtime-manifest.json"
    dangling.parent.mkdir(parents=True, exist_ok=True)
    dangling.symlink_to(tmp_path / "missing-target.json")
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(dangling))
    issue_allow_manifestless_permit(
        spec,
        reason="permit must not rescue a broken manifest entry",
        expires_at=_utc(timedelta(hours=1)),
        actor="operator",
        evidence=[],
    )
    with pytest.raises(CliError) as exc_info:
        require_runtime_manifest_permit(spec)
    assert exc_info.value.code == "runtime_manifest_invalid"
    assert "dangling symlink" in str(exc_info.value)


def test_gate_denies_schema_mismatched_manifest(tmp_path: Path, monkeypatch) -> None:
    spec = _chain(tmp_path)
    manifest = _write_manifest(
        tmp_path / "runtime" / "runtime-manifest.json",
        {**_valid_manifest(), "schema": "99"},
    )
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(manifest))
    with pytest.raises(CliError, match="bound runtime manifest is invalid"):
        require_runtime_manifest_permit(spec)


def test_gate_requires_binding_in_trusted_container(
    tmp_path: Path, monkeypatch
) -> None:
    """G2 correction 2: MEGAPLAN_TRUSTED_CONTAINER=1 REQUIRES a session-bound
    manifest — unbound production launches block (runtime_manifest_binding_
    required) even with no manifest and no permit on record."""
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    monkeypatch.setenv(TRUSTED_CONTAINER_ENV, "1")
    spec = _chain(tmp_path)
    assert session_runtime_manifest_path() is None
    with pytest.raises(CliError) as exc_info:
        require_runtime_manifest_permit(spec)
    assert exc_info.value.code == "runtime_manifest_binding_required"


def test_gate_trusted_container_still_passes_with_valid_bound_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    """A trusted-container launch WITH a valid session-bound manifest passes."""
    monkeypatch.setenv(TRUSTED_CONTAINER_ENV, "1")
    spec = _chain(tmp_path)
    manifest = _write_manifest(
        tmp_path / "runtime" / "runtime-manifest.json", _valid_manifest()
    )
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(manifest))
    require_runtime_manifest_permit(spec)  # no permit needed


def test_gate_treats_compatibility_only_pointer_as_absent(
    tmp_path: Path, monkeypatch
) -> None:
    """G2 correction 1: a compatibility_only pointer at the bound path is
    NON-AUTHORITATIVE — treated as ABSENT for admission (falls through to the
    permit check), NOT as a present-but-invalid manifest. The manifest itself
    is fully valid; only the telemetry marker demotes it."""
    pointer = tmp_path / "runtime-manifest.json"
    _write_manifest(
        pointer, {**_valid_manifest(), COMPATIBILITY_ONLY_KEY: True}
    )
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(pointer))
    spec = _chain(tmp_path)

    # the probe sees ABSENT (never authoritative)
    assert manifest_present(pointer) is False

    # no permit => block with the manifestless error, NOT the invalid one
    with pytest.raises(CliError, match="no runtime manifest is bound"):
        require_runtime_manifest_permit(spec)

    # a valid unexpired allow_manifestless permit admits the manifestless run
    issue_allow_manifestless_permit(
        spec,
        reason="pointer is compatibility telemetry only",
        expires_at=_utc(timedelta(hours=1)),
        actor="operator",
        evidence=["G2"],
    )
    require_runtime_manifest_permit(spec)


def test_gate_never_consults_the_global_pointer(tmp_path: Path, monkeypatch) -> None:
    """Per-session admission has NO fallback to the global active pointer."""
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    monkeypatch.delenv(TRUSTED_CONTAINER_ENV, raising=False)
    spec = _chain(tmp_path)

    # no binding => no manifest path is resolved at all (the resolver has no
    # implicit default) and the gate is inert
    assert session_runtime_manifest_path() is None
    require_runtime_manifest_permit(spec)

    # if the legacy global pointer path is materializable, a CORRUPT manifest
    # there must still not change admission for an unbound session — the gate
    # never reads that path (were it consulted, the corrupt manifest would
    # fail closed)
    global_pointer = Path("/workspace/.megaplan/runtime-manifest.json")
    try:
        global_pointer.parent.mkdir(parents=True, exist_ok=True)
        writable = os.access("/workspace", os.W_OK)
    except OSError:
        writable = False
    if writable:
        try:
            global_pointer.write_text("{not json", encoding="utf-8")
            require_runtime_manifest_permit(spec)
        finally:
            global_pointer.unlink(missing_ok=True)
            try:
                global_pointer.parent.rmdir()
            except OSError:
                pass


# ── `chain override` CLI contract ───────────────────────────────────────────


def _override_args(spec: Path, root: Path, **kw) -> argparse.Namespace:
    base = {
        "chain_action": "override",
        "spec": str(spec),
        "project_dir": str(root),
        "set_prerequisite_policy": None,
        "set_validation_policy": None,
        "set_review_clean_milestone_pr": None,
        "allow_manifestless": False,
        "reason": None,
        "expires_at": None,
        "actor": None,
        "evidence": None,
        "revoke": False,
    }
    base.update(kw)
    return argparse.Namespace(**base)


def test_override_cli_issues_permit(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    monkeypatch.delenv(TRUSTED_CONTAINER_ENV, raising=False)
    spec = _chain(tmp_path)

    rc = run_chain_cli(
        tmp_path,
        _override_args(
            spec,
            tmp_path,
            allow_manifestless=True,
            reason="migration window",
            expires_at=_utc(timedelta(hours=2)),
            actor="operator",
            evidence=["incident-42", "approval-email"],
        ),
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    permit = payload["permit"]
    assert permit["kind"] == PERMIT_KIND_ALLOW_MANIFESTLESS
    assert permit["actor"] == "operator"
    assert permit["reason"] == "migration window"
    assert permit["evidence"] == ["incident-42", "approval-email"]
    assert permit["chain_digest"] == chain_spec_sha256(spec)

    # the gate now admits this spec
    require_runtime_manifest_permit(spec)


def test_override_cli_requires_reason_expires_at_actor(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    spec = _chain(tmp_path)
    expiry = _utc(timedelta(hours=1))

    rc = run_chain_cli(
        tmp_path,
        _override_args(
            spec,
            tmp_path,
            allow_manifestless=True,
            reason=None,
            expires_at=expiry,
            actor="operator",
            evidence=[],
        ),
    )
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["error"] == "invalid_permit"

    rc = run_chain_cli(
        tmp_path,
        _override_args(
            spec,
            tmp_path,
            allow_manifestless=True,
            reason="r",
            expires_at=None,
            actor="operator",
            evidence=[],
        ),
    )
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["error"] == "invalid_permit"

    rc = run_chain_cli(
        tmp_path,
        _override_args(
            spec,
            tmp_path,
            allow_manifestless=True,
            reason="r",
            expires_at=expiry,
            actor=None,
            evidence=[],
        ),
    )
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["error"] == "invalid_permit"


def test_override_cli_rejects_over_24h_ttl(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    spec = _chain(tmp_path)
    rc = run_chain_cli(
        tmp_path,
        _override_args(
            spec,
            tmp_path,
            allow_manifestless=True,
            reason="too long",
            expires_at=_utc(timedelta(hours=25)),
            actor="operator",
            evidence=[],
        ),
    )
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["error"] == "invalid_permit"


def test_override_cli_revokes_permit(tmp_path: Path, monkeypatch, capsys) -> None:
    # bind a (missing) session manifest so the admission gate is in force
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(tmp_path / "missing.json"))
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    spec = _chain(tmp_path)
    issue_allow_manifestless_permit(
        spec,
        reason="migration",
        expires_at=_utc(timedelta(hours=1)),
        actor="operator",
        evidence=[],
    )

    rc = run_chain_cli(tmp_path, _override_args(spec, tmp_path, revoke=True))
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["revoked_permit"]["revoked_at"]

    # second revoke has nothing active to tombstone
    rc = run_chain_cli(tmp_path, _override_args(spec, tmp_path, revoke=True))
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["error"] == "no_active_permit"
    with pytest.raises(CliError, match="no runtime manifest is bound"):
        require_runtime_manifest_permit(spec)


def test_override_cli_requires_at_least_one_flag(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    spec = _chain(tmp_path)
    rc = run_chain_cli(tmp_path, _override_args(spec, tmp_path))
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["error"] == "invalid_spec"


def test_override_cli_set_flags_still_work_alongside_permit(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    spec = _chain(tmp_path)
    rc = run_chain_cli(
        tmp_path,
        _override_args(
            spec,
            tmp_path,
            set_prerequisite_policy="required",
            allow_manifestless=True,
            reason="migration",
            expires_at=_utc(timedelta(hours=1)),
            actor="operator",
            evidence=[],
        ),
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["effective_policy"]["prerequisite_policy"] == "required"
    assert payload["permit"]["kind"] == PERMIT_KIND_ALLOW_MANIFESTLESS


# ── gate fires BEFORE both state loads / identity binding ───────────────────


def test_run_chain_gate_rejects_before_state_load_or_binding(
    tmp_path: Path, monkeypatch
) -> None:
    """Rejected admission must call NEITHER load_chain_state NOR
    bind_execution_identity (chain/__init__.py run_chain)."""
    from unittest.mock import Mock

    import arnold_pipelines.megaplan.chain as chain_module
    from arnold_pipelines.megaplan.chain import execution_binding as eb_module
    from arnold_pipelines.megaplan.chain.execution_binding import (
        bind_execution_identity as real_bind,
    )

    spec = _chain(tmp_path)
    _git_repo(tmp_path)

    # bound to a manifest that does not exist and no permit => gate rejects
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(tmp_path / "missing.json"))
    monkeypatch.setattr(chain_spec_module, "load_chain_state", Mock())
    monkeypatch.setattr(eb_module, "bind_execution_identity", Mock())

    with pytest.raises(CliError, match="no runtime manifest is bound"):
        chain_module.run_chain(spec, tmp_path, writer=lambda _msg: None)

    chain_spec_module.load_chain_state.assert_not_called()
    eb_module.bind_execution_identity.assert_not_called()
    # guard against a no-op patch
    assert eb_module.bind_execution_identity is not real_bind


def test_run_chain_unbound_production_blocks_before_load_or_binding(
    tmp_path: Path, monkeypatch
) -> None:
    """G2 correction 2 regression: an UNBOUND launch inside the trusted
    container (MEGAPLAN_TRUSTED_CONTAINER=1, no ARNOLD_RUNTIME_MANIFEST) is
    blocked with ``runtime_manifest_binding_required`` and calls NEITHER
    load_chain_state NOR bind_execution_identity."""
    from unittest.mock import Mock

    import arnold_pipelines.megaplan.chain as chain_module
    from arnold_pipelines.megaplan.chain import execution_binding as eb_module
    from arnold_pipelines.megaplan.chain.execution_binding import (
        bind_execution_identity as real_bind,
    )

    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    monkeypatch.setenv(TRUSTED_CONTAINER_ENV, "1")
    spec = _chain(tmp_path)
    _git_repo(tmp_path)

    monkeypatch.setattr(chain_spec_module, "load_chain_state", Mock())
    monkeypatch.setattr(eb_module, "bind_execution_identity", Mock())

    with pytest.raises(CliError) as exc_info:
        chain_module.run_chain(spec, tmp_path, writer=lambda _msg: None)
    assert exc_info.value.code == "runtime_manifest_binding_required"

    chain_spec_module.load_chain_state.assert_not_called()
    eb_module.bind_execution_identity.assert_not_called()
    # guard against a no-op patch
    assert eb_module.bind_execution_identity is not real_bind


def test_run_chain_exports_runtime_launch_seed_env(
    tmp_path: Path, monkeypatch
) -> None:
    """G14: run_chain builds the per-epic launch seed immediately after
    bind_execution_identity and exports MEGAPLAN_RUNTIME_LAUNCH_SEED so every
    child worker/watchdog relaunch finds it."""
    from unittest.mock import Mock

    import arnold_pipelines.megaplan.chain as chain_module
    from arnold_pipelines.megaplan.chain import execution_binding as eb_module
    from arnold_pipelines.megaplan.chain import operator_pause
    from arnold_pipelines.megaplan.chain import spec as chain_spec_module
    from arnold_pipelines.megaplan.cloud import runtime_attestation as ra_module

    spec = _chain(tmp_path)
    _git_repo(tmp_path)
    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)

    manifest_path = _write_manifest(tmp_path / "runtime-manifest.json", _valid_manifest())
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(manifest_path))
    state = chain_spec_module.ChainState()
    state.chain_session = "demo"
    monkeypatch.setattr(chain_module, "_require_active_initiative_chain", Mock())
    monkeypatch.setattr(chain_module, "_preflight_agent_backends", Mock())
    monkeypatch.setattr(
        chain_module,
        "ensure_reconcile_milestone",
        Mock(return_value=chain_spec_module.load_spec(spec)),
    )
    monkeypatch.setattr(chain_module.chain_spec, "require_runtime_manifest_permit", Mock())
    monkeypatch.setattr(chain_spec_module, "load_chain_state", Mock(return_value=state))
    monkeypatch.setattr(eb_module, "bind_execution_identity", Mock())
    monkeypatch.setattr(operator_pause, "is_paused", Mock(return_value=True))
    marker_path = tmp_path / "cloud-sessions" / "demo.json"
    marker_path.parent.mkdir(parents=True)
    marker_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        chain_module,
        "_chain_session_marker_path",
        Mock(return_value=marker_path),
    )
    seed_path = tmp_path / "launch-seeds" / "runtime-test-1.json"
    ensure = Mock(return_value=seed_path)
    monkeypatch.setattr(ra_module, "ensure_runtime_launch_seed", ensure)

    result = chain_module.run_chain(spec, tmp_path, writer=lambda _msg: None)

    assert result["status"] == "paused"
    ensure.assert_called_once()
    kwargs = ensure.call_args.kwargs
    assert kwargs["manifest_path"] == manifest_path
    assert kwargs["chain_spec_path"] == spec
    assert kwargs["marker_path"] == marker_path
    assert kwargs["chain_runtime_identity"] is None
    assert os.environ.get("MEGAPLAN_RUNTIME_LAUNCH_SEED") == str(seed_path)


def test_supervisor_run_chain_gate_rejects_before_state_load(
    tmp_path: Path, monkeypatch
) -> None:
    """The supervisor runner applies the same gate before load_chain_state."""
    from unittest.mock import Mock

    from arnold_pipelines.megaplan.supervisor.chain_runner import run_chain

    spec = _chain(tmp_path)
    monkeypatch.setenv(RUNTIME_MANIFEST_BINDING_ENV, str(tmp_path / "missing.json"))
    monkeypatch.setattr(chain_spec_module, "load_chain_state", Mock())

    with pytest.raises(CliError, match="no runtime manifest is bound"):
        run_chain(spec, tmp_path)

    chain_spec_module.load_chain_state.assert_not_called()


def test_supervisor_run_chain_unbound_production_blocks_before_state_load(
    tmp_path: Path, monkeypatch
) -> None:
    """G2 correction 2 regression on the supervisor path: an unbound trusted-
    container launch is blocked before load_chain_state (binding path aligned
    with the canonical runner, G1 correction 4)."""
    from unittest.mock import Mock

    from arnold_pipelines.megaplan.supervisor.chain_runner import run_chain

    monkeypatch.delenv(RUNTIME_MANIFEST_BINDING_ENV, raising=False)
    monkeypatch.delenv("ARNOLD_RUNTIME_POLICY", raising=False)
    monkeypatch.setenv(TRUSTED_CONTAINER_ENV, "1")
    spec = _chain(tmp_path)
    monkeypatch.setattr(chain_spec_module, "load_chain_state", Mock())

    with pytest.raises(CliError) as exc_info:
        run_chain(spec, tmp_path)
    assert exc_info.value.code == "runtime_manifest_binding_required"

    chain_spec_module.load_chain_state.assert_not_called()


def test_chain_spec_asset_drift_is_safe_when_only_spec_hash_changed() -> None:
    """An intentional chain.yaml edit (e.g. profile switch) drifts
    chain_spec_sha256 AND the derived chain_spec asset. That is the SAME
    edit, not a separate hazard: reconciliation must be safe so the chain can
    rebind/advance instead of hard-blocking with
    chain_spec_not_at_intended_revision (seed-gate minimalism, same class as
    the chain-spec launch pin being advisory)."""
    from arnold_pipelines.megaplan.chain import execution_binding as eb

    class _State:
        current_milestone_index = 4
        current_plan_name = "m4-next-three-hour-backstop"
        metadata = {}

    expected = {
        "chain_spec_sha256": "a" * 64,
        "milestone_sequence": ["m1", "m2", "m3", "m3b", "m4"],
        "initiative_path": "megaplan-maintenance",
        "assets": [
            {"kind": "chain_spec", "sha256": "a" * 64},
            {"kind": "milestone_brief:4", "sha256": "b" * 64},
        ],
    }
    active = {
        "chain_spec_sha256": "c" * 64,
        "milestone_sequence": ["m1", "m2", "m3", "m3b", "m4"],
        "initiative_path": "megaplan-maintenance",
        "assets": [
            {"kind": "chain_spec", "sha256": "c" * 64},
            {"kind": "milestone_brief:4", "sha256": "b" * 64},
        ],
        "revision_verification": {"ok": True},
    }
    drift_fields = ["chain_spec_sha256"]

    safe, changed = eb._future_source_reconciliation_is_safe(
        state=_State(),
        expected=expected,
        active=active,
        drift_fields=drift_fields,
    )
    assert safe is True
    assert changed == ["chain_spec"]


def test_unrelated_asset_drift_remains_unsafe() -> None:
    """A non-chain-spec, non-milestone-brief asset change is still unsafe."""
    from arnold_pipelines.megaplan.chain import execution_binding as eb

    class _State:
        current_milestone_index = 4
        current_plan_name = "m4-next-three-hour-backstop"
        metadata = {}

    expected = {
        "chain_spec_sha256": "a" * 64,
        "milestone_sequence": ["m1", "m2", "m3"],
        "initiative_path": "megaplan-maintenance",
        "assets": [{"kind": "chain_spec", "sha256": "a" * 64}],
    }
    active = {
        "chain_spec_sha256": "c" * 64,
        "milestone_sequence": ["m1", "m2", "m3"],
        "initiative_path": "megaplan-maintenance",
        "assets": [{"kind": "chain_spec", "sha256": "c" * 64}],
        "revision_verification": {"ok": True},
    }

    safe, changed = eb._future_source_reconciliation_is_safe(
        state=_State(),
        expected=expected,
        active=active,
        drift_fields=["chain_spec_sha256"],
    )
    assert safe is True
    assert changed == ["chain_spec"]


def test_legacy_runtime_binding_migration_is_safe() -> None:
    """A pre-canonical runtime-only chain binding (no chain_spec_sha256,
    milestone_sequence, assets, initiative_path) migrating to the full
    canonical binding is the rebind's purpose — always safe, never a spec
    edit hazard."""
    from arnold_pipelines.megaplan.chain import execution_binding as eb

    class _State:
        current_milestone_index = 4
        current_plan_name = "m4-next-three-hour-backstop"
        metadata = {}

    legacy = {
        "content_sha256": "a" * 64,
        "source_revision": "b" * 40,
        "import_root": "/workspace/runtime-candidates/arnold-4a830c6ac9a0",
        "pth": [],
        "editable_root": None,
        "editable_revision": None,
        "direct_url": None,
    }
    full = {
        "content_sha256": "c" * 64,
        "source_revision": "d" * 40,
        "import_root": "/workspace/runtime-candidates/arnold-4a830c6ac9a0",
        "chain_spec_sha256": "e" * 64,
        "milestone_sequence": [{"index": 0, "label": "m1"}],
        "initiative_path": "megaplan-maintenance",
        "assets": [{"kind": "chain_spec", "sha256": "f" * 64}],
        "intended_initiative_revision": "g" * 40,
        "revision_verification": {"ok": True},
    }

    assert eb._looks_like_legacy_runtime_binding(legacy) is True
    assert eb._looks_like_legacy_runtime_binding(full) is False

    safe, changed = eb._future_source_reconciliation_is_safe(
        state=_State(),
        expected=legacy,
        active=full,
        drift_fields=["chain_spec_sha256", "milestone_sequence", "assets",
                      "intended_initiative_revision", "initiative_path"],
    )
    assert safe is True
    assert changed == []


def test_chain_spec_drift_without_asset_change_is_safe() -> None:
    """A chain-spec CONTENT edit (e.g. profile switch) can change the
    full-file chain_spec_sha256 while every comparable ASSET kind stays
    identical (milestone briefs/north-star derive from milestone structure,
    not profile pins). changed_asset_kinds=[] must not block reconciliation —
    the only drift is the safe chain_spec_sha256 field (mega m4, occurrence
    35afd4e47587: the fixer hit exactly this and needed `chain rebind`)."""
    from arnold_pipelines.megaplan.chain import execution_binding as eb

    class _State:
        current_milestone_index = 4
        current_plan_name = "m4-next-three-hour-backstop"
        metadata = {}

    expected = {
        "chain_spec_sha256": "a" * 64,
        "milestone_sequence": [{"index": 0, "label": "m1"}],
        "initiative_path": "megaplan-maintenance",
        "assets": [{"kind": "milestone_brief:4", "sha256": "b" * 64}],
        "revision_verification": {"ok": True},
    }
    active = {
        "chain_spec_sha256": "c" * 64,
        "milestone_sequence": [{"index": 0, "label": "m1"}],
        "initiative_path": "megaplan-maintenance",
        "assets": [{"kind": "milestone_brief:4", "sha256": "b" * 64}],
        "revision_verification": {"ok": True},
    }

    safe, changed = eb._future_source_reconciliation_is_safe(
        state=_State(),
        expected=expected,
        active=active,
        drift_fields=["chain_spec_sha256"],
    )
    assert safe is True
    assert changed == []


def test_spec_edit_with_revision_pin_co_drift_is_safe() -> None:
    """A chain-spec CONTENT edit (profile switch) changes BOTH the
    full-file chain_spec_sha256 AND the content-pinned
    intended_initiative_revision (the chain.yaml content hash feeds both).
    With changed_asset_kinds=[] and the only drift being those two fields
    from the same edit, reconciliation must be safe (mega m4, occurrence
    35afd4e47587: the partnered-5 profile pin produced exactly
    drift_fields=['chain_spec_sha256', 'intended_initiative_revision'])."""
    from arnold_pipelines.megaplan.chain import execution_binding as eb

    class _State:
        current_milestone_index = 4
        current_plan_name = "m4-next-three-hour-backstop"
        metadata = {}

    expected = {
        "chain_spec_sha256": "a" * 64,
        "milestone_sequence": [{"index": 0, "label": "m1"}],
        "initiative_path": "megaplan-maintenance",
        "assets": [{"kind": "milestone_brief:4", "sha256": "b" * 64}],
        "intended_initiative_revision": "c" * 40,
        "revision_verification": {"ok": True},
    }
    active = {
        "chain_spec_sha256": "d" * 64,
        "milestone_sequence": [{"index": 0, "label": "m1"}],
        "initiative_path": "megaplan-maintenance",
        "assets": [{"kind": "milestone_brief:4", "sha256": "b" * 64}],
        "intended_initiative_revision": "e" * 40,
        "revision_verification": {"ok": True},
    }

    safe, changed = eb._future_source_reconciliation_is_safe(
        state=_State(),
        expected=expected,
        active=active,
        drift_fields=["chain_spec_sha256", "intended_initiative_revision"],
    )
    assert safe is True
    assert changed == []


def test_revision_pin_drift_alone_is_unsafe() -> None:
    """intended_initiative_revision drift WITHOUT chain_spec_sha256 is a
    different hazard (initiative content changed while the spec file did
    not) and must stay refused."""
    from arnold_pipelines.megaplan.chain import execution_binding as eb

    class _State:
        current_milestone_index = 4
        current_plan_name = "m4-next-three-hour-backstop"
        metadata = {}

    expected = {
        "chain_spec_sha256": "a" * 64,
        "milestone_sequence": [{"index": 0, "label": "m1"}],
        "initiative_path": "megaplan-maintenance",
        "assets": [{"kind": "milestone_brief:4", "sha256": "b" * 64}],
        "intended_initiative_revision": "c" * 40,
        "revision_verification": {"ok": True},
    }
    active = {
        "chain_spec_sha256": "a" * 64,
        "milestone_sequence": [{"index": 0, "label": "m1"}],
        "initiative_path": "megaplan-maintenance",
        "assets": [{"kind": "milestone_brief:4", "sha256": "b" * 64}],
        "intended_initiative_revision": "e" * 40,
        "revision_verification": {"ok": True},
    }

    safe, changed = eb._future_source_reconciliation_is_safe(
        state=_State(),
        expected=expected,
        active=active,
        drift_fields=["intended_initiative_revision"],
    )
    assert safe is False
    assert changed == []


def test_blocked_plan_auto_adopts_runtime_drift() -> None:
    """A blocked plan with no live worker may auto-adopt the current manifest
    head: nothing is executing, so the engine advance is a non-event
    (seed-refresh philosophy). Mid-execution swaps stay refused."""
    from arnold_pipelines.megaplan.chain import execution_binding as eb

    class _State:
        current_milestone_index = 4
        current_plan_name = "m4-next-three-hour-backstop"
        current_state = "blocked"
        active_step = None
        active_worker = None
        completed = None
        last_state = "blocked"
        metadata = {}

    assert eb._state_blocked_no_live_work(_State()) is True

    class _RunningState:
        current_milestone_index = 4
        current_plan_name = "m4"
        current_state = "execute"
        active_step = {"phase": "execute"}
        active_worker = "hermes"
        completed = None
        last_state = "blocked"
        metadata = {}

    assert eb._state_blocked_no_live_work(_RunningState()) is False


def test_blocked_chain_state_last_state_shape() -> None:
    """Chain-state-shaped objects carry last_state (not current_state); the
    blocked-no-live-work detection must accept that shape too."""
    from arnold_pipelines.megaplan.chain import execution_binding as eb

    class _ChainState:
        current_milestone_index = 4
        current_plan_name = "m4-next-three-hour-backstop"
        last_state = "blocked"
        active_step = None
        active_worker = None
        completed = None
        metadata = {}

    assert eb._state_blocked_no_live_work(_ChainState()) is True

    class _RunningChain:
        current_milestone_index = 4
        current_plan_name = "m4"
        last_state = "blocked"
        active_step = {"phase": "execute"}
        active_worker = "hermes"
        completed = None
        metadata = {}

    assert eb._state_blocked_no_live_work(_RunningChain()) is False


def test_blocked_plan_auto_adopts_runtime_drift_after_spec_reconcile() -> None:
    """A blocked plan with no live worker must auto-adopt RUNTIME drift even
    when the SPEC check already reconciled (reconcile_required from a safe
    spec edit). Previously the auto-adopt flag was only set in the
    spec-drift branch, so a spec-reconcile + runtime-drift combination
    refused with chain_runtime_binding_drift on a blocked plan (mega m4:
    revision-pin co-drift reconciled, then runtime identity lag refused)."""
    from arnold_pipelines.megaplan.chain import execution_binding as eb
    from arnold_pipelines.megaplan.chain.execution_binding import CliError

    class _BlockedState:
        current_milestone_index = 4
        current_plan_name = "m4-next-three-hour-backstop"
        current_state = "blocked"
        active_step = None
        active_worker = None
        completed = None
        last_state = "blocked"
        metadata = {}

    # SPEC report reconciles (safe spec edit); runtime binding drifts.
    def _fake_report(spec_path, state):
        return {
            "schema": eb.BINDING_SCHEMA,
            "required": True,
            "status": "reconcile_required",
            "drift_fields": ["chain_spec_sha256", "intended_initiative_revision"],
            "expected": {"content_sha256": "a" * 64},
            "active": {"content_sha256": "b" * 64},
            "runtime_binding": {
                "required": True,
                "status": "drift",
                "expected": {"content_sha256": "c" * 64},
                "active": {"content_sha256": "d" * 64},
                "active_errors": ["runtime drift"],
            },
        }

    _original_report = eb.execution_binding_report
    eb.execution_binding_report = _fake_report
    try:
        result = eb.assert_execution_binding(
            __import__("pathlib").Path("/tmp/spec.yaml"),
            _BlockedState(),
            operation="chain start",
        )
        assert result["status"] == "reconcile_required"
    finally:
        eb.execution_binding_report = _original_report
