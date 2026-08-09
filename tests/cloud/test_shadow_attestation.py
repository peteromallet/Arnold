"""Tests for the Phase-0 shadow gate: content attestation of fixer edit targets."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import shadow_attestation
from arnold_pipelines.megaplan.cloud.runtime_attestation import _sha256_file
from arnold_pipelines.megaplan.cloud.shadow_attestation import (
    ShadowedTargetError,
    attest_target_content,
    refuse_shadowed_target,
)


def _make_attestation_tree(tmp_path: Path) -> Path:
    """Build a minimal importable-layout tree for attestation.

    The layout mirrors the bounded digest subset:
    ``arnold_pipelines/megaplan/cloud/*.py`` + ``wrappers/*``.
    """
    tree = tmp_path / "tree"
    cloud = tree / "arnold_pipelines" / "megaplan" / "cloud"
    cloud.mkdir(parents=True)
    (tree / "arnold_pipelines" / "__init__.py").write_text("# pkg\n", encoding="utf-8")
    (tree / "arnold_pipelines" / "megaplan" / "__init__.py").write_text(
        "# megaplan\n", encoding="utf-8"
    )
    (cloud / "__init__.py").write_text("# cloud\n", encoding="utf-8")
    (cloud / "alpha.py").write_text("ALPHA = 1\n", encoding="utf-8")
    (cloud / "beta.py").write_text("BETA = 2\n", encoding="utf-8")
    wrappers = cloud / "wrappers"
    wrappers.mkdir()
    (wrappers / "arnold-watchdog").write_text("#!/bin/sh\n", encoding="utf-8")
    (wrappers / "helper.py").write_text("HELPER = 3\n", encoding="utf-8")
    return tree


def _not_importable(module_name: str) -> str:
    """Stand-in for ``find_spec`` returning nothing (module not importable)."""
    return ""


def test_attest_target_content_falls_back_to_tree_search(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = _make_attestation_tree(tmp_path)
    monkeypatch.setattr(shadow_attestation, "_find_spec_origin", _not_importable)

    att = attest_target_content(tree)
    pkg_init = tree / "arnold_pipelines" / "__init__.py"

    assert att.tree_path == str(tree.resolve())
    assert att.tree_head == ""  # temp tree is not a git repo
    assert att.tree_digest
    assert att.module_file == str(pkg_init)
    assert att.module_digest == _sha256_file(pkg_init)
    assert att.declared_vs_observed_match is True
    if sys.platform == "linux":
        assert att.mount_id != "unavailable"
    else:
        assert att.mount_id == "unavailable"
        assert any("mount_id_unavailable" in entry for entry in att.errors)


def test_attest_records_git_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = _make_attestation_tree(tmp_path)
    subprocess.run(["git", "-C", str(tree), "init", "-q", "-b", "main"], check=True)
    subprocess.run(["git", "-C", str(tree), "config", "user.email", "a@b"], check=True)
    subprocess.run(["git", "-C", str(tree), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(tree), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(tree), "-c", "commit.gpgsign=false", "commit", "-q", "-m", "seed"],
        check=True,
    )
    expected_head = subprocess.run(
        ["git", "-C", str(tree), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setattr(shadow_attestation, "_find_spec_origin", _not_importable)

    att = attest_target_content(tree)
    assert att.tree_head == expected_head


def test_tree_digest_is_deterministic_and_content_sensitive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = _make_attestation_tree(tmp_path)
    monkeypatch.setattr(shadow_attestation, "_find_spec_origin", _not_importable)

    first = attest_target_content(tree)
    second = attest_target_content(tree)
    assert first.tree_digest == second.tree_digest
    assert first.module_digest == second.module_digest

    (tree / "arnold_pipelines" / "megaplan" / "cloud" / "alpha.py").write_text(
        "ALPHA = 999\n", encoding="utf-8"
    )
    changed = attest_target_content(tree)
    assert changed.tree_digest != first.tree_digest


def test_refuse_raises_when_module_file_outside_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = _make_attestation_tree(tmp_path)
    outside = tmp_path / "elsewhere" / "arnold_pipelines" / "__init__.py"
    outside.parent.mkdir(parents=True)
    outside.write_text("# other copy\n", encoding="utf-8")
    # observed module resolves outside the declared tree (bind-mount shadowing)
    monkeypatch.setattr(shadow_attestation, "_find_spec_origin", lambda name: str(outside))

    att = attest_target_content(tree)
    assert att.module_file == str(outside)
    assert att.declared_vs_observed_match is False

    with pytest.raises(ShadowedTargetError) as excinfo:
        refuse_shadowed_target(att)
    message = str(excinfo.value)
    assert "module_file_outside_tree" in message
    assert "refusing shadowed target" in message


def test_refuse_raises_on_content_mismatch_inside_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = _make_attestation_tree(tmp_path)
    # observed module resolves inside the tree but to a different file than the
    # tree copy of the module (namespace drift within the tree)
    wrong_file = tree / "arnold_pipelines" / "megaplan" / "cloud" / "__init__.py"
    monkeypatch.setattr(shadow_attestation, "_find_spec_origin", lambda name: str(wrong_file))

    att = attest_target_content(tree)
    assert att.module_file == str(wrong_file)
    assert att.declared_vs_observed_match is False

    with pytest.raises(ShadowedTargetError) as excinfo:
        refuse_shadowed_target(att)
    message = str(excinfo.value)
    assert "module_content_mismatch" in message
    assert "module_file_outside_tree" not in message


def test_refuse_does_not_raise_when_everything_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = _make_attestation_tree(tmp_path)
    monkeypatch.setattr(shadow_attestation, "_find_spec_origin", _not_importable)

    att = attest_target_content(tree)
    assert att.declared_vs_observed_match is True
    # must not raise: module inside tree, digests equal, and the mount gate is
    # Linux-only (mount_id is "unavailable" on this host)
    refuse_shadowed_target(att)


def test_mount_id_unavailable_is_gated_to_linux(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = _make_attestation_tree(tmp_path)
    monkeypatch.setattr(shadow_attestation, "_find_spec_origin", _not_importable)
    monkeypatch.setattr(
        shadow_attestation,
        "_mount_identity_for_path",
        lambda path: ("unavailable", "mount_id_unavailable:test"),
    )

    att = attest_target_content(tree)
    assert att.mount_id == "unavailable"
    assert any("mount_id_unavailable" in entry for entry in att.errors)

    if sys.platform == "linux":
        with pytest.raises(ShadowedTargetError) as excinfo:
            refuse_shadowed_target(att)
        assert "mount_id_unavailable_on_linux" in str(excinfo.value)
    else:
        # on non-Linux the mount probe is inherently unavailable and must not
        # gate the shadow check
        refuse_shadowed_target(att)
