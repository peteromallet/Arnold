"""P1 admission conformance: launchers resolve via the runtime manifest.

The per-runtime manifest is the ONLY post-bootstrap resolver.  A PRESENT
manifest must load and validate (corrupt / schema-mismatched manifests exit
78 with a typed ``manifest_invalid`` error before any dispatch).  A genuinely
ABSENT manifest is admitted ONLY by a valid, unexpired ``allow_manifestless``
permit in the ``.runtime_policy.json`` sidecar (``dirname(ARNOLD_RUNTIME_MANIFEST)
/.runtime_policy.json``, or the ``ARNOLD_RUNTIME_POLICY`` override); without a
permit the launcher fails closed with exit 78.  The legacy
``with_name(...)`` / env / SRC_DIR runtime-selection fallback chains are
REMOVED — env pins survive only as explicit operator/test overrides on top of
the manifest.  A drift-check unit exercises ``attest_runtime`` content
attestation.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPERS_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
TRIGGER = WRAPPERS_DIR / "arnold-repair-trigger"
WATCHDOG = WRAPPERS_DIR / "arnold-watchdog"
RUNTIME_LIB = WRAPPERS_DIR / "arnold-supervisor-runtime-lib"
DEFAULT_MANIFEST_PATH = "/workspace/.megaplan/runtime-manifest.json"


def _base_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _write_allow_manifestless_policy(
    policy_path: Path,
    *,
    issued_at: str | None = None,
    expires_at: str | None = None,
    permits: list[dict[str, object]] | None = None,
) -> Path:
    """Write a ``.runtime_policy.json`` sidecar with one valid permit by default.

    The settled permit contract: ``kind="allow_manifestless"``, non-empty
    ``id``, ``issued_at``/``expires_at`` ISO8601 UTC with
    ``0 < expires_at - issued_at <= 24h`` and current-unexpired, plus
    ``actor``, ``reason``, ``evidence``, ``chain_digest``.  ``permits``
    overrides the whole list for multi-record / revoked / expired cases.
    """
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    if permits is not None:
        payload = {"permits": permits}
    else:
        now = datetime.now(timezone.utc)
        payload = {
            "permits": [
                {
                    "kind": "allow_manifestless",
                    "id": "permit-test-1",
                    "issued_at": issued_at or now.isoformat(),
                    "expires_at": expires_at or (now + timedelta(hours=1)).isoformat(),
                    "actor": "launcher-conformance-test",
                    "reason": "wave-2 test harness admission",
                    "evidence": ["test harness injects a valid permit"],
                    "chain_digest": hashlib.sha256(b"test-chain").hexdigest(),
                }
            ]
        }
    policy_path.write_text(json.dumps(payload), encoding="utf-8")
    return policy_path


def _run_trigger(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TRIGGER)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=60,
    )


def test_trigger_resolves_repair_bins_manifest_only() -> None:
    """The trigger resolves repair bins from the runtime manifest ONLY.

    ``_default_repair_bin`` / ``_default_meta_repair_bin`` read
    ``epic.repair_bin`` / ``epic.runtime_root`` from the bootstrapped manifest;
    the env vars are explicit operator/test pins layered on top.  There is NO
    ``with_name(...)`` sibling fallback — an unresolved default fails closed at
    dispatch.
    """
    text = TRIGGER.read_text(encoding="utf-8")

    assert "runtime_manifest" in text
    # The with_name fallback chain is REMOVED — no Path(__file__).with_name.
    assert 'with_name("arnold-repair-loop")' not in text
    assert 'with_name("arnold-meta-repair-loop")' not in text
    # Manifest-only resolvers + explicit env pins.
    assert "def _default_repair_bin()" in text
    assert "def _default_meta_repair_bin()" in text
    assert "_manifest_repair_bin()" in text
    assert "_manifest_runtime_root()" in text
    assert "ARNOLD_REPAIR_TRIGGER_REPAIR_BIN" in text
    assert "ARNOLD_REPAIR_TRIGGER_META_REPAIR_BIN" in text
    # Stable bootstrap path env/default are present.
    assert "ARNOLD_RUNTIME_MANIFEST" in text
    assert DEFAULT_MANIFEST_PATH in text


def test_trigger_keeps_env_pins_without_with_name_fallback() -> None:
    """Env pins survive as operator/test overrides; with_name is gone."""
    text = TRIGGER.read_text(encoding="utf-8")

    assert "ARNOLD_REPAIR_TRIGGER_REPAIR_BIN" in text
    assert "ARNOLD_REPAIR_TRIGGER_META_REPAIR_BIN" in text
    assert 'with_name("arnold-meta-repair-loop")' not in text
    assert 'with_name("arnold-repair-loop")' not in text


def test_watchdog_references_manifest_resolution_for_bins() -> None:
    """The watchdog resolves PRIMARY/META/TRIGGER bins from the manifest.

    The shared supervisor runtime lib is sourced and is the SOLE manifest
    reader: the watchdog calls ``arnold_runtime_manifest_authority`` (the
    P1 admission gate) and reads ``epic.repair_bin`` / ``epic.runtime_root``
    through ``arnold_runtime_manifest_epic_field``.  Source/fallback bins and
    env overrides remain as explicit pins.
    """
    text = WATCHDOG.read_text(encoding="utf-8")
    lib = RUNTIME_LIB.read_text(encoding="utf-8")

    # The lib defines the canonical reader + admission gate.
    assert "arnold_runtime_manifest_path()" in lib
    assert "arnold_runtime_manifest_epic_field()" in lib
    assert "arnold_runtime_manifest_authority()" in lib
    assert DEFAULT_MANIFEST_PATH in lib
    # The watchdog uses the lib gate before any field read.
    assert "arnold_runtime_manifest_authority watchdog" in text
    assert 'MANIFEST_REPAIR_BIN="$(arnold_runtime_manifest_epic_field epic.repair_bin)"' in text
    assert 'MANIFEST_RUNTIME_ROOT="$(arnold_runtime_manifest_epic_field epic.runtime_root)"' in text
    # Source/fallback bins + env overrides still exist as explicit pins.
    assert "CLOUD_WATCHDOG_PRIMARY_REPAIR_BIN" in text
    assert "CLOUD_WATCHDOG_META_REPAIR_BIN" in text
    assert "CLOUD_WATCHDOG_REPAIR_TRIGGER_BIN" in text
    assert 'PRIMARY_REPAIR_SOURCE_BIN="$SRC_DIR/arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"' in text
    assert 'META_REPAIR_SOURCE_BIN="$SRC_DIR/arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop"' in text


def test_launcher_sources_parse() -> None:
    """bash -n and py_compile must both succeed on the edited launchers."""
    bash_n = subprocess.run(["bash", "-n", str(WATCHDOG)], capture_output=True, text=True)
    assert bash_n.returncode == 0, f"bash -n arnold-watchdog failed:\n{bash_n.stderr}"

    py_compile = subprocess.run(
        [sys.executable, "-m", "py_compile", str(TRIGGER)],
        capture_output=True,
        text=True,
    )
    assert py_compile.returncode == 0, f"py_compile arnold-repair-trigger failed:\n{py_compile.stderr}"


def test_trigger_refuses_present_but_invalid_manifest(tmp_path: Path) -> None:
    """A present-but-invalid manifest fails closed BEFORE any dispatch.

    ``ARNOLD_RUNTIME_MANIFEST`` set means the manifest is THE resolver: a
    corrupt manifest must exit non-zero with a typed ``manifest_invalid``
    error, never fall back to env/with_name.  A permit cannot rescue a
    present-but-invalid manifest (the manifest is present; absence is the
    only permitted case).
    """
    corrupt = tmp_path / "runtime-manifest.json"
    corrupt.write_text("{not valid json", encoding="utf-8")
    policy = _write_allow_manifestless_policy(tmp_path / ".runtime_policy.json")
    env = {
        **_base_env(),
        "ARNOLD_RUNTIME_MANIFEST": str(corrupt),
        "ARNOLD_RUNTIME_POLICY": str(policy),
    }
    proc = _run_trigger(env)
    assert proc.returncode == 78
    assert "manifest_invalid:" in proc.stderr


def test_trigger_absent_manifest_without_permit_fails_closed(tmp_path: Path) -> None:
    """A genuinely absent manifest (no env, no file) BLOCKS without a permit.

    The with_name/env/SRC_DIR fallback chain is removed: absence is never an
    allow.  The launcher must exit 78 with the typed failing-closed message.
    """
    env = _base_env()
    env.pop("ARNOLD_RUNTIME_MANIFEST", None)
    env.pop("ARNOLD_RUNTIME_POLICY", None)
    proc = _run_trigger(env)
    assert proc.returncode == 78
    assert "runtime manifest absent without a valid allow_manifestless permit" in proc.stderr


def test_trigger_absent_manifest_admitted_by_valid_permit(tmp_path: Path) -> None:
    """A valid unexpired allow_manifestless permit admits the manifestless run."""
    policy = _write_allow_manifestless_policy(tmp_path / ".runtime_policy.json")
    env = {
        **_base_env(),
        "ARNOLD_RUNTIME_POLICY": str(policy),
    }
    proc = _run_trigger(env)
    # Admission passes; with an empty queue the trigger exits 0 (no dispatch).
    assert proc.returncode == 0, proc.stderr
    assert "manifest_invalid:" not in proc.stderr


def test_trigger_rejects_expired_permit(tmp_path: Path) -> None:
    """Expiry rejects admission — an expired permit never admits."""
    now = datetime.now(timezone.utc)
    expired = now - timedelta(hours=2)
    permit = {
        "kind": "allow_manifestless",
        "id": "permit-expired",
        "issued_at": (expired - timedelta(hours=1)).isoformat(),
        "expires_at": expired.isoformat(),
        "actor": "launcher-conformance-test",
        "reason": "expired permit fixture",
        "evidence": [],
        "chain_digest": hashlib.sha256(b"chain").hexdigest(),
    }
    policy = _write_allow_manifestless_policy(
        tmp_path / ".runtime_policy.json", permits=[permit]
    )
    env = {
        **_base_env(),
        "ARNOLD_RUNTIME_POLICY": str(policy),
    }
    proc = _run_trigger(env)
    assert proc.returncode == 78
    assert "runtime manifest absent without a valid allow_manifestless permit" in proc.stderr


def test_trigger_rejects_revoked_permit(tmp_path: Path) -> None:
    """A revoked permit (revoked_at tombstone) never admits."""
    now = datetime.now(timezone.utc)
    permit = {
        "kind": "allow_manifestless",
        "id": "permit-revoked",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "actor": "launcher-conformance-test",
        "reason": "revoked permit fixture",
        "evidence": [],
        "chain_digest": hashlib.sha256(b"chain").hexdigest(),
        "revoked_at": now.isoformat(),
    }
    policy = _write_allow_manifestless_policy(
        tmp_path / ".runtime_policy.json", permits=[permit]
    )
    env = {
        **_base_env(),
        "ARNOLD_RUNTIME_POLICY": str(policy),
    }
    proc = _run_trigger(env)
    assert proc.returncode == 78
    assert "runtime manifest absent without a valid allow_manifestless permit" in proc.stderr


def test_trigger_last_valid_unexpired_permit_wins(tmp_path: Path) -> None:
    """The LAST unrevoked, valid, unexpired allow_manifestless record wins.

    Expired/revoked records stay loadable but never admit; a later valid
    record after an expired one admits; a later expired record after a valid
    one does NOT invalidate the earlier valid record (last-valid-wins, not
    last-record-wins).
    """
    now = datetime.now(timezone.utc)
    expired = {
        "kind": "allow_manifestless",
        "id": "permit-expired-first",
        "issued_at": (now - timedelta(hours=2)).isoformat(),
        "expires_at": (now - timedelta(hours=1)).isoformat(),
        "actor": "launcher-conformance-test",
        "reason": "expired earlier record",
        "evidence": [],
        "chain_digest": hashlib.sha256(b"chain").hexdigest(),
    }
    valid = {
        "kind": "allow_manifestless",
        "id": "permit-valid-later",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "actor": "launcher-conformance-test",
        "reason": "valid later record",
        "evidence": [],
        "chain_digest": hashlib.sha256(b"chain").hexdigest(),
    }
    # Expired record first, valid record later -> last valid wins -> admit.
    policy = _write_allow_manifestless_policy(
        tmp_path / "policy-later-valid.json", permits=[expired, valid]
    )
    env = {
        **_base_env(),
        "ARNOLD_RUNTIME_POLICY": str(policy),
    }
    proc = _run_trigger(env)
    assert proc.returncode == 0, proc.stderr

    # Valid record first, expired record later -> earlier valid still active.
    policy2 = _write_allow_manifestless_policy(
        tmp_path / "policy-later-expired.json", permits=[valid, expired]
    )
    env2 = {
        **_base_env(),
        "ARNOLD_RUNTIME_POLICY": str(policy2),
    }
    proc2 = _run_trigger(env2)
    assert proc2.returncode == 0, proc2.stderr


def test_trigger_rejects_permit_outside_24h_lifetime(tmp_path: Path) -> None:
    """Permits with 0 < expires_at - issued_at > 24h are structurally invalid."""
    now = datetime.now(timezone.utc)
    permit = {
        "kind": "allow_manifestless",
        "id": "permit-too-long",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=25)).isoformat(),
        "actor": "launcher-conformance-test",
        "reason": "oversized lifetime fixture",
        "evidence": [],
        "chain_digest": hashlib.sha256(b"chain").hexdigest(),
    }
    policy = _write_allow_manifestless_policy(
        tmp_path / ".runtime_policy.json", permits=[permit]
    )
    env = {
        **_base_env(),
        "ARNOLD_RUNTIME_POLICY": str(policy),
    }
    proc = _run_trigger(env)
    assert proc.returncode == 78
    assert "runtime manifest absent without a valid allow_manifestless permit" in proc.stderr


def test_watchdog_fail_closed_manifest_gate_and_reactive_dispatch() -> None:
    """The watchdog gates through the lib authority and dispatches reactive.

    The shared lib's ``arnold_runtime_manifest_authority`` is the SOLE
    manifest resolver and is wired into the watchdog before any field read;
    the reactive dispatch seam names the mode explicitly.
    """
    text = WATCHDOG.read_text(encoding="utf-8")
    lib = RUNTIME_LIB.read_text(encoding="utf-8")
    # Gate: the lib defines the typed admission kernel with fail-closed paths.
    assert "arnold_runtime_manifest_authority()" in lib
    assert "manifest present without epic.branch; failing closed" in lib
    assert "runtime manifest absent without a valid allow_manifestless permit; failing closed" in lib
    assert "arnold_manifest_allow_manifestless()" in lib
    # The watchdog wires the gate BEFORE field reads.
    assert "arnold_runtime_manifest_authority watchdog" in text
    assert text.index("arnold_runtime_manifest_authority watchdog") < text.index(
        "MANIFEST_REPAIR_BIN="
    )
    # Dispatch through the unified seam names the mode explicitly.
    assert '--command-display "arnold-repair-loop --mode=reactive $session"' in text
    assert '"$PRIMARY_REPAIR_BIN" --mode=reactive "$session" "$workspace" "$remote_spec"' in text
    # Manifest runtime binding: PYTHONPATH/SRC_DIR follow the manifest runtime
    # root so the selected executable and imported code share one runtime.
    assert "REPAIR_DISPATCH_RUNTIME_SRC" in text
    assert 'ARNOLD_REPAIR_RUNTIME_SRC="$SRC_DIR"' in text


def test_lib_manifest_authority_gate_blocks_and_admits(tmp_path: Path) -> None:
    """The shared lib admission kernel: present+valid passes, corrupt blocks,
    absent without permit blocks, absent with valid permit passes."""
    status_dir = tmp_path / "status"

    def run_gate(
        *,
        manifest_path: Path | None,
        policy_path: Path | None,
    ) -> subprocess.CompletedProcess[str]:
        script = f"""
source {str(RUNTIME_LIB)!r}
export MEGAPLAN_SUPERVISOR_STDLIB_PYTHON={shlex.quote(sys.executable)}
export ARNOLD_RUNTIME_MANIFEST={shlex.quote(str(manifest_path)) if manifest_path else ""}
export ARNOLD_RUNTIME_POLICY={shlex.quote(str(policy_path)) if policy_path else ""}
export MEGAPLAN_SUPERVISOR_STATUS_DIR={shlex.quote(str(status_dir))}
arnold_runtime_manifest_authority gate-test
echo "GATE_OK"
"""
        env = dict(os.environ)
        env["PATH"] = f"{Path(sys.executable).parent}:{env.get('PATH', '')}"
        return subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    # 1) Absent manifest without a permit -> fail closed (78).
    blocked = run_gate(
        manifest_path=tmp_path / "no-such-manifest.json",
        policy_path=tmp_path / "no-such-policy.json",
    )
    assert blocked.returncode == 78
    assert "runtime manifest absent without a valid allow_manifestless permit" in blocked.stderr

    # 2) Absent manifest with a valid permit -> admit.
    policy = _write_allow_manifestless_policy(tmp_path / ".runtime_policy.json")
    admitted = run_gate(
        manifest_path=tmp_path / "no-such-manifest.json",
        policy_path=policy,
    )
    assert admitted.returncode == 0, admitted.stderr
    assert "GATE_OK" in admitted.stdout

    # 3) Present corrupt manifest -> fail closed (78) regardless of permit.
    corrupt = tmp_path / "corrupt-manifest.json"
    corrupt.write_text("{not valid json", encoding="utf-8")
    corrupt_blocked = run_gate(
        manifest_path=corrupt,
        policy_path=policy,
    )
    assert corrupt_blocked.returncode == 78
    assert "manifest present without epic.branch" in corrupt_blocked.stderr

    # 4) Present valid manifest (epic.branch) -> admit.
    valid = tmp_path / "valid-manifest.json"
    valid.write_text(
        json.dumps({"epic": {"branch": "fixer/p1-wave2"}}),
        encoding="utf-8",
    )
    valid_ok = run_gate(
        manifest_path=valid,
        policy_path=tmp_path / "no-such-policy.json",
    )
    assert valid_ok.returncode == 0, valid_ok.stderr
    assert "GATE_OK" in valid_ok.stdout


def test_lib_authority_treats_compatibility_only_pointer_as_absent(
    tmp_path: Path,
) -> None:
    """G2 correction 1: a ``compatibility_only`` pointer is NON-AUTHORITATIVE.

    The lib admission gate treats it as ABSENT — the run falls through to the
    permit check (block without a valid permit), it is never "present without
    epic.branch", and the pointer's own contents never admit a run.
    """
    status_dir = tmp_path / "status"
    pointer = tmp_path / "runtime-manifest.json"
    pointer.write_text(
        json.dumps(
            {"compatibility_only": True, "epic": {"branch": "fixer/p1-wave2"}}
        ),
        encoding="utf-8",
    )

    def run_gate(policy_path: Path | None) -> subprocess.CompletedProcess[str]:
        script = f"""
source {str(RUNTIME_LIB)!r}
export MEGAPLAN_SUPERVISOR_STDLIB_PYTHON={shlex.quote(sys.executable)}
export ARNOLD_RUNTIME_MANIFEST={shlex.quote(str(pointer))}
export ARNOLD_RUNTIME_POLICY={shlex.quote(str(policy_path)) if policy_path else ""}
export MEGAPLAN_SUPERVISOR_STATUS_DIR={shlex.quote(str(status_dir))}
arnold_runtime_manifest_authority gate-test
echo "GATE_OK"
"""
        env = dict(os.environ)
        env["PATH"] = f"{Path(sys.executable).parent}:{env.get('PATH', '')}"
        return subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    # No permit -> the compatibility_only pointer is treated as ABSENT -> the
    # absent-manifest fail-closed message, never the present-but-invalid one.
    blocked = run_gate(tmp_path / "no-such-policy.json")
    assert blocked.returncode == 78
    assert (
        "runtime manifest absent without a valid allow_manifestless permit"
        in blocked.stderr
    )
    assert "present without epic.branch" not in blocked.stderr

    # A valid unexpired permit admits the manifestless run (the pointer alone
    # never selects a runtime).
    policy = _write_allow_manifestless_policy(tmp_path / ".runtime_policy.json")
    admitted = run_gate(policy)
    assert admitted.returncode == 0, admitted.stderr
    assert "GATE_OK" in admitted.stdout


LEAF_WRAPPERS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("arnold-repair-loop", ("sess-test", "ws", "spec.yaml"), "ARNOLD_REPAIR_RUNTIME_SRC"),
    ("arnold-kimi-goal-operator", ("sess-test", "ws", "spec.yaml"), "KIMI_GOAL_ARNOLD_SRC"),
    ("arnold-meta-repair-loop", ("sess-test",), "MEGAPLAN_META_ARNOLD_SRC"),
)


@pytest.mark.parametrize(
    ("wrapper_name", "extra_args", "src_env"),
    LEAF_WRAPPERS,
    ids=[entry[0] for entry in LEAF_WRAPPERS],
)
def test_leaf_wrapper_direct_invocation_blocks_without_manifest_or_permit(
    tmp_path: Path,
    wrapper_name: str,
    extra_args: tuple[str, ...],
    src_env: str,
) -> None:
    """G2 correction 3: leaf fixer wrappers fail closed on DIRECT invocation.

    With no session-bound manifest and no valid ``allow_manifestless`` permit
    the wrapper's entry admission gate must exit 78 with the exact
    fail-closed message — before any dispatch.  Direct invocation is not
    rescued by the expected parent.
    """
    wrapper = WRAPPERS_DIR / wrapper_name
    env = _base_env()
    env["PATH"] = f"{Path(sys.executable).parent}:{env.get('PATH', '')}"
    env["MEGAPLAN_SUPERVISOR_STATUS_DIR"] = str(tmp_path / "status")
    env["ARNOLD_REPAIR_LOOP_SKIP_SELF_COPY"] = "1"
    # Pin the source root so arnold_supervisor_runtime_init (which runs before
    # the entry gate) validates against the repo tree.
    env[src_env] = str(REPO_ROOT)
    env.pop("ARNOLD_RUNTIME_MANIFEST", None)
    env.pop("ARNOLD_RUNTIME_POLICY", None)

    proc = subprocess.run(
        ["bash", str(wrapper), *extra_args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=240,
    )
    assert proc.returncode == 78, proc.stderr
    assert (
        "runtime manifest absent without a valid allow_manifestless permit; failing closed"
        in proc.stderr
    )


def _fake_runtime_manifest(tmp_path: Path, module_digest: str) -> dict:
    """A schema-shaped fake manifest with attestation fields (Phase 2 schema)."""

    tree = tmp_path / "runtime-tree"
    tree.mkdir(parents=True, exist_ok=True)
    module_file = tree / "arnold_pipelines" / "__init__.py"
    module_file.parent.mkdir(parents=True, exist_ok=True)
    module_file.write_text("# observed content\n", encoding="utf-8")
    return {
        "runtime_id": "drift-test-runtime",
        "schema": "1",
        "generation": 1,
        "epic_id": "drift-test-epic",
        "state": "active",
        "owner": "launcher-conformance-test",
        "base": {
            "ref": "refs/heads/base/editable-install",
            "commit": "0" * 40,
            "editable_install_path": str(tree),
            "venv_path": str(tree / "venv"),
        },
        "epic": {
            "branch": "fixer/drift-test",
            "worktree_path": str(tree),
            "venv_path": str(tree / "venv"),
            "runtime_root": str(tree),
            "expected_head": "0" * 40,
            "repair_bin": str(tree / "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop"),
            "deps_lockfile": "deps_lockfile.txt",
        },
        "indirection": {
            "host_path": str(tree),
            "container_path": str(tree),
            "mount_table": [],
            "execution_namespace": "drift-test",
            "verified_head": "0" * 40,
            "last_verified_at": "2026-08-07T00:00:00Z",
            "attestation": {
                "module_file": str(module_file),
                "module_digest": module_digest,
                "mount_id": "drift-test-mount",
            },
        },
        "policy": {
            "policy_sha": "0" * 64,
            "model_policy_sha": "0" * 64,
            "sync_policy": {"enabled": False},
        },
        "promotions": [],
        "timestamps": {
            "created": "2026-08-07T00:00:00Z",
            "updated": "2026-08-07T00:00:00Z",
            "closed": None,
        },
        "gc_policy": "default",
        "commands": [],
    }


def test_attest_runtime_detects_tree_content_drift(tmp_path: Path) -> None:
    """attest_runtime must fail loudly when the tree content differs.

    A fake manifest points at a tmp tree whose content does not match the
    actually-observed module; the drift check must surface as
    declared_vs_observed_match False (never a silent pass).
    """
    pytest.importorskip("arnold_pipelines.megaplan.cloud.runtime_manifest")
    from arnold_pipelines.megaplan.cloud.runtime_manifest import (
        attest_runtime,
        bootstrap_manifest,
    )

    declared_digest = hashlib.sha256(b"declared-but-not-observed-content\n").hexdigest()
    manifest_path = tmp_path / "runtime-manifest.json"
    manifest_path.write_text(
        json.dumps(_fake_runtime_manifest(tmp_path, module_digest=declared_digest)),
        encoding="utf-8",
    )

    manifest = bootstrap_manifest(manifest_path)
    result = attest_runtime(manifest)

    assert isinstance(result, dict)
    assert result["declared_vs_observed_match"] is False
    # Contract keys all present.
    for key in ("module_file", "module_digest", "mount_id", "declared_vs_observed_match", "errors"):
        assert key in result
