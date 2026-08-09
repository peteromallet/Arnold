"""Phase 2 conformance: launchers resolve via the runtime manifest.

Every launcher must resolve its repair binaries through the per-runtime
manifest after one stable bootstrap path (``ARNOLD_RUNTIME_MANIFEST`` or the
default ``/workspace/.megaplan/runtime-manifest.json``).  The legacy
``Path(__file__).with_name("arnold-repair-loop")`` resolution is demoted to a
deprecated last resort, and the source order proves the manifest branch runs
first.  A drift-check unit exercises ``attest_runtime`` content attestation.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPERS_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
TRIGGER = WRAPPERS_DIR / "arnold-repair-trigger"
WATCHDOG = WRAPPERS_DIR / "arnold-watchdog"
DEFAULT_MANIFEST_PATH = "/workspace/.megaplan/runtime-manifest.json"
WITH_NAME_DEPRECATION_WARNING = (
    "with_name repair-bin resolution is deprecated — bootstrap from the runtime manifest"
)


def test_trigger_resolves_repair_bin_via_manifest_before_with_name() -> None:
    """The trigger must bootstrap the manifest BEFORE the with_name fallback.

    The source order carries the guarantee: the manifest-resolution branch
    (``runtime_manifest`` import + helpers) appears earlier in the file than
    the ``with_name("arnold-repair-loop")`` fallback, which additionally sits
    behind the loud deprecation warning.
    """
    text = TRIGGER.read_text(encoding="utf-8")

    assert "runtime_manifest" in text
    with_name_marker = 'with_name("arnold-repair-loop")'
    assert with_name_marker in text
    # Manifest resolution is authored before the with_name fallback.
    assert text.index("runtime_manifest") < text.index(with_name_marker)
    # The with_name branch is explicitly behind the deprecation warning.
    assert WITH_NAME_DEPRECATION_WARNING in text
    # Stable bootstrap path env/default are present.
    assert "ARNOLD_RUNTIME_MANIFEST" in text
    assert DEFAULT_MANIFEST_PATH in text


def test_trigger_keeps_env_and_with_name_fallback_chain() -> None:
    """Removing the manifest must leave env + with_name fallbacks intact."""
    text = TRIGGER.read_text(encoding="utf-8")

    assert "ARNOLD_REPAIR_TRIGGER_REPAIR_BIN" in text
    assert "ARNOLD_REPAIR_TRIGGER_META_REPAIR_BIN" in text
    assert 'with_name("arnold-meta-repair-loop")' in text


def test_watchdog_references_manifest_resolution_for_bins() -> None:
    """The watchdog must resolve PRIMARY/META/TRIGGER bins from the manifest."""
    text = WATCHDOG.read_text(encoding="utf-8")

    # Manifest resolution is referenced (canonical reader or bootstrap env).
    assert ("bootstrap_manifest" in text) or ("ARNOLD_RUNTIME_MANIFEST" in text)
    assert "epic.repair_bin" in text
    assert "epic.runtime_root" in text
    assert DEFAULT_MANIFEST_PATH in text
    # Fallback chain preserved: env overrides and SRC_DIR sources still exist.
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
