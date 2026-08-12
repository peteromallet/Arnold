"""Tests for content attestation in the current-target resolver (design §6).

Covers ``attestation_section`` (module __file__ + digest + mount id evidence
projection) and its wiring into ``resolve_current_target`` as the additive
``runtime_attestation`` key, which is ALWAYS present in the returned record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.current_target import (
    _resolver_tree_path,
    attestation_section,
    resolve_current_target,
)

_ATTESTATION_KEYS = {
    "tree_path",
    "module_file",
    "module_digest",
    "mount_id",
    "declared_vs_observed_match",
    "errors",
}


def _write_marker(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_tree(tmp_path: Path) -> Path:
    """Minimal runtime tree for attestation.

    Mirrors the shadow_attestation bounded digest subset:
    ``arnold_pipelines/megaplan/cloud/*.py``.
    """
    tree = tmp_path / "tree"
    cloud = tree / "arnold_pipelines" / "megaplan" / "cloud"
    cloud.mkdir(parents=True)
    (tree / "arnold_pipelines" / "__init__.py").write_text(
        "# pkg\n", encoding="utf-8"
    )
    (tree / "arnold_pipelines" / "megaplan" / "__init__.py").write_text(
        "# megaplan\n", encoding="utf-8"
    )
    (cloud / "__init__.py").write_text("# cloud\n", encoding="utf-8")
    (cloud / "alpha.py").write_text("ALPHA = 1\n", encoding="utf-8")
    return tree


# ── attestation_section ─────────────────────────────────────────────────────


def test_attestation_section_tree_path_unavailable_when_none() -> None:
    section = attestation_section(None)
    assert section == {"errors": ["tree_path_unavailable"]}


def test_attestation_section_tree_path_unavailable_when_missing(
    tmp_path: Path,
) -> None:
    section = attestation_section(tmp_path / "does-not-exist")
    assert section == {"errors": ["tree_path_unavailable"]}


def test_attestation_section_returns_six_keys_for_existing_tree(
    tmp_path: Path,
) -> None:
    tree = _make_tree(tmp_path)
    section = attestation_section(tree)
    assert set(section) == _ATTESTATION_KEYS
    assert section["tree_path"] == str(tree.resolve())
    # module_file may be the observed namespace or the tree-search fallback —
    # either way the section is complete and never raises.
    assert isinstance(section["module_file"], str)
    assert isinstance(section["module_digest"], str)
    assert isinstance(section["mount_id"], str)
    assert isinstance(section["declared_vs_observed_match"], bool)
    assert isinstance(section["errors"], list)


# ── resolver tree-path picker ───────────────────────────────────────────────


def test_resolver_tree_path_prefers_manifest_runtime_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_root = tmp_path / "manifest-tree"
    manifest_root.mkdir()
    manifest = tmp_path / "runtime-manifest.json"
    manifest.write_text(
        json.dumps({"epic": {"runtime_root": str(manifest_root)}}),
        encoding="utf-8",
    )
    workspace = tmp_path / "ws"
    workspace.mkdir()
    # The manifest (provenance) outranks the workspace and the spec parent,
    # and the legacy env selector is never consulted.
    monkeypatch.setenv("MEGAPLAN_RUNTIME_SRC", str(tmp_path / "env-tree"))
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))
    spec = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    assert _resolver_tree_path(workspace, spec) == manifest_root
    assert _resolver_tree_path(workspace, None) == manifest_root
    assert _resolver_tree_path(None, None) == manifest_root


def test_resolver_tree_path_ignores_runtime_src_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # G2: the legacy selector env is no longer read — with no manifest, no
    # workspace, and no spec parent, resolution reports UNKNOWN even when the
    # env is set.
    monkeypatch.setenv("MEGAPLAN_RUNTIME_SRC", str(tmp_path / "env-tree"))
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    assert _resolver_tree_path(None, None) is None
    workspace = tmp_path / "ws"
    workspace.mkdir()
    assert _resolver_tree_path(workspace, None) == workspace


def test_resolver_tree_path_falls_back_when_manifest_unreadable_or_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.cloud.runtime_manifest import ManifestError

    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    # Env set but file missing -> genuinely absent -> workspace wins.
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(tmp_path / "missing.json"))
    assert _resolver_tree_path(workspace, None) == workspace
    # Env set, file PRESENT but no epic.runtime_root -> present-but-invalid
    # fails closed (typed) — never a silent workspace fallback.
    manifest = tmp_path / "bare.json"
    manifest.write_text(json.dumps({"epic": {"branch": "main"}}), encoding="utf-8")
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))
    with pytest.raises(ManifestError, match="lacks a nonempty epic.runtime_root"):
        _resolver_tree_path(workspace, None)
    # Unset env -> unchanged workspace/spec fallback chain.
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    assert _resolver_tree_path(workspace, spec) == workspace
    assert _resolver_tree_path(None, spec) == spec.parent
    assert _resolver_tree_path(None, None) is None


def test_resolver_tree_path_dangling_symlink_manifest_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DANGLING symlink at the bound manifest path is PRESENT but
    unreadable — it must raise ManifestError, NEVER degrade to absent (which
    would let the resolver silently select the workspace as the executed
    tree, T-0024 absent-vs-invalid distinction)."""
    from arnold_pipelines.megaplan.cloud.runtime_manifest import ManifestError

    workspace = tmp_path / "ws"
    workspace.mkdir()
    dangling = tmp_path / "dangling-manifest.json"
    dangling.symlink_to(tmp_path / "missing-target.json")
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(dangling))
    with pytest.raises(ManifestError, match="present but unreadable"):
        _resolver_tree_path(workspace, None)


def test_resolver_tree_path_falls_back_to_workspace_and_spec_parent(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    spec = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    assert _resolver_tree_path(workspace, spec) == workspace
    assert _resolver_tree_path(None, spec) == spec.parent
    assert _resolver_tree_path(None, None) is None


# ── resolve_current_target wiring ───────────────────────────────────────────


def test_resolve_current_target_includes_runtime_attestation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = _make_tree(tmp_path)
    _write_marker(
        marker_dir / "demo.json",
        {
            "session": "demo",
            "workspace": str(workspace),
            "run_kind": "chain",
            "plan_name": "m1-plan",
        },
    )
    record = resolve_current_target("demo", marker_dir=marker_dir)
    assert "runtime_attestation" in record
    section = record["runtime_attestation"]
    assert set(section) == _ATTESTATION_KEYS
    assert section["tree_path"] == str(workspace.resolve())


def test_resolve_current_target_attestation_present_when_tree_unresolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ARNOLD_RUNTIME_MANIFEST", raising=False)
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    # Marker with neither workspace nor remote_spec -> no tree candidate.
    _write_marker(marker_dir / "demo.json", {"session": "demo", "run_kind": "chain"})
    record = resolve_current_target("demo", marker_dir=marker_dir)
    assert "runtime_attestation" in record
    assert record["runtime_attestation"] == {"errors": ["tree_path_unavailable"]}
