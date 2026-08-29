"""Auto-publish → runtime-manifest pin advance (occurrence d51891b51841).

The chain's auto-publish commit (``_publish_done_plan``) moves the runtime
root HEAD; without a matching manifest pin advance the NEXT worker launch
fails closed with ``runtime_launch_attestation_mismatch``. These tests pin
the hook contract: advance when a new local commit lands (even when the
remote push is refused by custody), idempotent when already pinned, skipped
when no manifest is bound or the root mismatches, refused — recorded, never
raised into the publish result — when the pin is not an ancestor, the
dependency proof does not bind, or the CAS detects a concurrent advance.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan import auto
from arnold_pipelines.megaplan.cloud.install_sync import (
    compute_venv_digest,
    frozen_spec_sha256,
)
from arnold_pipelines.megaplan.cloud.runtime_manifest import (
    MANIFEST_SCHEMA_VERSION,
    ManifestError,
    RuntimeManifest,
    load_manifest,
    write_manifest,
)
from arnold_pipelines.megaplan.types import CliError


def _spec_repo(tmp_path: Path) -> tuple[Path, str]:
    """A REAL git repo WITH the frozen dependency spec (pyproject.toml +
    uv.lock) the strict frozen-spec gate requires. Returns (root, head)."""
    root = tmp_path / "spec-repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (root / "uv.lock").write_text(
        'version = 1\nrequires-python = ">=3.11"\n', encoding="utf-8"
    )
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "seed"], check=True)
    sha = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return root, sha


def _bound_proof(tmp_path: Path, root: Path) -> dict[str, object]:
    """A dependency-generation proof that ACTUALLY binds to *root*."""
    frozen = frozen_spec_sha256(root)
    gen_dir = tmp_path / "runtime-venvs" / frozen
    (gen_dir / "bin").mkdir(parents=True, exist_ok=True)
    interpreter = gen_dir / "bin" / "python"
    interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
    interpreter.chmod(0o755)
    (gen_dir / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    return {
        "id": frozen,
        "frozen_spec_sha256": frozen,
        "interpreter_path": str(interpreter),
        "venv_digest": compute_venv_digest(interpreter),
        "created": "2026-08-07T00:00:00+00:00",
    }


def _unbound_proof(tmp_path: Path) -> dict[str, object]:
    """A structurally valid proof that does NOT bind to any real repo."""
    return {
        "id": "a" * 64,
        "frozen_spec_sha256": "a" * 64,
        "interpreter_path": str(tmp_path / "no-such-venv" / "bin" / "python"),
        "venv_digest": "b" * 64,
        "created": "2026-08-07T00:00:00+00:00",
    }


def _manifest_dict(
    tmp_path: Path,
    root: Path,
    head: str,
    generation: int = 26,
    proof: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "runtime_id": "runtime-native-demo",
        "schema": MANIFEST_SCHEMA_VERSION,
        "generation": generation,
        "epic_id": "native-demo",
        "state": "active",
        "owner": "superfixer",
        "base": {
            "ref": "refs/heads/base/editable-install",
            "commit": "87a912beb",
            "editable_install_path": "",
            "venv_path": str(tmp_path / "base-venv"),
        },
        "epic": {
            "branch": "fixer/native-demo-20260824",
            "worktree_path": str(root),
            "venv_path": str(tmp_path / "demo-venv"),
            "runtime_root": str(root),
            "expected_head": head,
            "repair_bin": str(tmp_path / "bin" / "arnold-babysitter"),
            "deps_lockfile": str(root / "uv.lock"),
            "dependency_generation": (
                proof if proof is not None else _bound_proof(tmp_path, root)
            ),
        },
        "indirection": {
            "host_path": str(root),
            "container_path": "",
            "mount_table": [],
            "execution_namespace": "",
            "verified_head": head,
            "last_verified_at": "2026-08-07T00:00:00+00:00",
            "attestation": {
                "module_file": str(root / "arnold_pipelines" / "__init__.py"),
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


def _write_bound_manifest(
    tmp_path: Path, root: Path, head: str, path: Path, generation: int = 26
) -> RuntimeManifest:
    manifest = RuntimeManifest.from_dict(_manifest_dict(tmp_path, root, head, generation))
    write_manifest(manifest, path)
    return manifest


def _dirty(root: Path) -> None:
    (root / "publish-me.txt").write_text("milestone work\n", encoding="utf-8")


def _patch_push(monkeypatch: pytest.MonkeyPatch, ok: bool) -> None:
    real = auto._git_text

    def fake_git_text(root: Path, args: list[str], **kwargs: object) -> str:
        if args and args[0] == "git" and "push" in args:
            if ok:
                return "push ok"
            raise CliError("custody_refused", "push refused by custody control")
        return real(root, args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(auto, "_git_text", fake_git_text)


def _publish(root: Path, tmp_path: Path) -> dict:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir(exist_ok=True)
    lines: list[str] = []
    payload = auto._publish_done_plan(
        plan="demo",
        plan_dir=plan_dir,
        root=root,
        branch="megaplan/demo",
        writer=lines.append,
    )
    assert payload is not None
    assert (plan_dir / "publish.json").is_file()
    assert json.loads((plan_dir / "publish.json").read_text(encoding="utf-8")) == payload
    return payload


def test_publish_advances_manifest_and_records_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, head = _spec_repo(tmp_path)
    manifest_path = tmp_path / "runtime-manifest.json"
    _write_bound_manifest(tmp_path, root, head, manifest_path)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest_path))
    _patch_push(monkeypatch, ok=True)
    _dirty(root)
    payload = _publish(root, tmp_path)
    commit_sha = payload["commit_sha"]
    assert commit_sha != head
    assert payload["status"] == "pushed"
    advance = payload["manifest_advance"]
    assert advance["schema"] == "megaplan.auto_publish.manifest_advance"
    assert advance["status"] == "advanced"
    assert advance["generation"] == 27
    assert advance["expected_head"] == commit_sha
    on_disk = load_manifest(manifest_path)
    assert on_disk.generation == 27
    assert on_disk.epic["expected_head"] == commit_sha
    assert on_disk.promotions[-1]["previous_commit"] == head


def test_publish_push_failure_still_advances_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, head = _spec_repo(tmp_path)
    manifest_path = tmp_path / "runtime-manifest.json"
    _write_bound_manifest(tmp_path, root, head, manifest_path)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest_path))
    _patch_push(monkeypatch, ok=False)
    _dirty(root)
    payload = _publish(root, tmp_path)
    commit_sha = payload["commit_sha"]
    # custody refusal flips the OUTER status only…
    assert payload["status"] == "publish_failed"
    # …but the local commit is real and the manifest pin moves with it
    advance = payload["manifest_advance"]
    assert advance["status"] == "advanced"
    assert advance["generation"] == 27
    assert advance["expected_head"] == commit_sha
    assert load_manifest(manifest_path).epic["expected_head"] == commit_sha


def test_publish_hook_idempotent_when_already_pinned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, head = _spec_repo(tmp_path)
    manifest_path = tmp_path / "runtime-manifest.json"
    _write_bound_manifest(tmp_path, root, head, manifest_path)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest_path))
    result = auto._advance_runtime_manifest_after_publish(
        root=root,
        plan="demo",
        commit_sha=head,
        head_sha_before="0" * 40,
    )
    assert result is not None
    assert result["status"] == "current"
    assert result["generation"] == 26  # no bump on retry of the same commit
    assert load_manifest(manifest_path).generation == 26


def test_publish_hook_skips_without_manifest_or_mismatched_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, head = _spec_repo(tmp_path)
    # no new commit at all -> no record
    assert (
        auto._advance_runtime_manifest_after_publish(
            root=root, plan="demo", commit_sha=head, head_sha_before=head
        )
        is None
    )
    # no manifest bound -> skipped, never raised
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    result = auto._advance_runtime_manifest_after_publish(
        root=root, plan="demo", commit_sha=head, head_sha_before="0" * 40
    )
    assert result == {
        "schema": "megaplan.auto_publish.manifest_advance",
        "plan": "demo",
        "commit_sha": head,
        "status": "skipped",
        "reason": "no_manifest_bound",
    }
    # manifest bound to a DIFFERENT runtime root -> skipped (the hook skips
    # before any proof work, so an unbound fake proof is fine here)
    other = tmp_path / "other-root"
    other.mkdir()
    manifest_path = tmp_path / "runtime-manifest.json"
    unbound = _manifest_dict(tmp_path, other, head, proof=_unbound_proof(tmp_path))
    write_manifest(RuntimeManifest.from_dict(unbound), manifest_path)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest_path))
    result = auto._advance_runtime_manifest_after_publish(
        root=root, plan="demo", commit_sha=head, head_sha_before="0" * 40
    )
    assert result is not None
    assert result["status"] == "skipped"
    assert result["reason"] == "runtime_root_mismatch"


def test_publish_records_refusal_pin_not_ancestor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, head = _spec_repo(tmp_path)
    manifest_path = tmp_path / "runtime-manifest.json"
    # pin at a fabricated non-ancestor commit
    _write_bound_manifest(tmp_path, root, "f" * 40, manifest_path)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest_path))
    _patch_push(monkeypatch, ok=True)
    _dirty(root)
    payload = _publish(root, tmp_path)
    advance = payload["manifest_advance"]
    assert advance["status"] == "refused"
    assert advance["reason"] == "pin_not_ancestor"
    # outer publish result unchanged; manifest untouched (zero mutation)
    assert payload["status"] == "pushed"
    on_disk = load_manifest(manifest_path)
    assert on_disk.generation == 26
    assert on_disk.epic["expected_head"] == "f" * 40


def test_publish_records_refusal_on_proof_and_cas_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, head = _spec_repo(tmp_path)
    _dirty(root)

    # (a) dependency proof does not bind to the repo -> advance refuses
    manifest_path = tmp_path / "runtime-manifest.json"
    bad = _manifest_dict(tmp_path, root, head, proof=_unbound_proof(tmp_path))
    write_manifest(RuntimeManifest.from_dict(bad), manifest_path)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest_path))
    _patch_push(monkeypatch, ok=True)
    payload = _publish(root, tmp_path)
    advance = payload["manifest_advance"]
    assert advance["status"] == "refused"
    assert advance["reason"] == "ManifestError"
    assert "frozen_spec_sha256" in advance["error"]
    assert payload["status"] == "pushed"
    assert load_manifest(manifest_path).generation == 26

    # (b) concurrent advance under the hook -> CAS refusal, publish intact
    manifest_path2 = tmp_path / "runtime-manifest-2.json"
    _write_bound_manifest(tmp_path, root, head, manifest_path2)
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest_path2))
    (root / "publish-me-2.txt").write_text("more work\n", encoding="utf-8")

    import arnold_pipelines.megaplan.cloud.runtime_manifest as runtime_manifest_module

    def raise_concurrent(*args: object, **kwargs: object) -> object:
        raise ManifestError("advance_generation_at_path refused: concurrent advance")

    monkeypatch.setattr(
        runtime_manifest_module, "advance_generation_at_path", raise_concurrent
    )
    payload2 = _publish(root, tmp_path)
    advance2 = payload2["manifest_advance"]
    assert advance2["status"] == "refused"
    assert advance2["reason"] == "ManifestError"
    assert payload2["status"] == "pushed"
