"""Unit tests for megaplan._pipeline.discovery.trust."""

from __future__ import annotations

from pathlib import Path

import pytest

from arnold.pipelines.megaplan._pipeline.discovery.trust import (
    BLESSED_ALLOWLIST,
    KNOWN_CAPABILITIES,
    TrustTier,
    check_capabilities,
    classify,
    derive_tenant_id,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_in_tree_path(tmp_path: Path) -> Path:
    """Create a fake in-tree pipeline module path under megaplan/pipelines/."""
    p = tmp_path / "megaplan" / "pipelines" / "myplan" / "__init__.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    return p


def _make_out_of_tree_path(tmp_path: Path) -> Path:
    """Create a fake out-of-tree pipeline module path (user home style)."""
    p = tmp_path / "home" / ".megaplan" / "pipelines" / "custom.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    return p


# ---------------------------------------------------------------------------
# TrustTier.AUTO_EXEC — in-tree classification
# ---------------------------------------------------------------------------


def test_in_tree_package_is_auto_exec(tmp_path: Path) -> None:
    path = _make_in_tree_path(tmp_path)
    assert classify(path) is TrustTier.AUTO_EXEC


def test_in_tree_sibling_py_is_auto_exec(tmp_path: Path) -> None:
    p = tmp_path / "megaplan" / "pipelines" / "simple.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    assert classify(p) is TrustTier.AUTO_EXEC


# ---------------------------------------------------------------------------
# TrustTier.QUARANTINED — out-of-tree classification
# ---------------------------------------------------------------------------


def test_out_of_tree_path_is_quarantined(tmp_path: Path) -> None:
    path = _make_out_of_tree_path(tmp_path)
    assert classify(path) is TrustTier.QUARANTINED


def test_unrelated_path_is_quarantined(tmp_path: Path) -> None:
    p = tmp_path / "other" / "pipeline.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    assert classify(p) is TrustTier.QUARANTINED


# ---------------------------------------------------------------------------
# TrustTier.BLESSED — allowlist promotion
# ---------------------------------------------------------------------------


def test_blessed_allowlist_promotes_out_of_tree(tmp_path: Path) -> None:
    path = _make_out_of_tree_path(tmp_path)
    resolved = str(path.resolve())
    assert classify(path, blessed_allowlist=(resolved,)) is TrustTier.BLESSED


def test_blessed_allowlist_also_works_for_in_tree(tmp_path: Path) -> None:
    """An in-tree path explicitly blessed stays BLESSED (allowlist wins first)."""
    path = _make_in_tree_path(tmp_path)
    resolved = str(path.resolve())
    assert classify(path, blessed_allowlist=(resolved,)) is TrustTier.BLESSED


def test_empty_blessed_allowlist_default(tmp_path: Path) -> None:
    """The module-level BLESSED_ALLOWLIST constant must be empty."""
    assert BLESSED_ALLOWLIST == ()


def test_blessed_allowlist_not_matched_falls_through(tmp_path: Path) -> None:
    """A path NOT in the allowlist falls through to path-derived tier."""
    path = _make_out_of_tree_path(tmp_path)
    # Different path string in allowlist — should not match.
    assert classify(path, blessed_allowlist=("/some/other/path.py",)) is TrustTier.QUARANTINED


# ---------------------------------------------------------------------------
# Capability allowlist helper
# ---------------------------------------------------------------------------


def test_known_capabilities_no_unknowns() -> None:
    caps = ("plan", "execute", "review", "gate", "doc", "creative")
    assert check_capabilities(caps) == []


def test_check_capabilities_returns_unknown_kinds() -> None:
    caps = ("plan", "teleport", "mind_control")
    result = check_capabilities(caps)
    assert set(result) == {"teleport", "mind_control"}


def test_check_capabilities_empty_input() -> None:
    assert check_capabilities(()) == []


def test_known_capabilities_is_frozenset() -> None:
    assert isinstance(KNOWN_CAPABILITIES, frozenset)
    assert "plan" in KNOWN_CAPABILITIES
    assert "execute" in KNOWN_CAPABILITIES


# ---------------------------------------------------------------------------
# TrustTier enum sanity
# ---------------------------------------------------------------------------


def test_trust_tier_values() -> None:
    assert TrustTier.AUTO_EXEC.value == "auto_exec"
    assert TrustTier.QUARANTINED.value == "quarantined"
    assert TrustTier.BLESSED.value == "blessed"


def test_derive_tenant_id_is_stable_for_name_and_resolved_path(tmp_path: Path) -> None:
    path = _make_out_of_tree_path(tmp_path)
    assert derive_tenant_id("custom", path) == derive_tenant_id("custom", path)
    assert derive_tenant_id("custom", path).startswith("pipeline_")


def test_derive_tenant_id_changes_with_name_or_path(tmp_path: Path) -> None:
    path = _make_out_of_tree_path(tmp_path)
    other = tmp_path / "elsewhere" / "custom.py"
    other.parent.mkdir(parents=True)
    other.touch()
    assert derive_tenant_id("custom", path) != derive_tenant_id("other", path)
    assert derive_tenant_id("custom", path) != derive_tenant_id("custom", other)
