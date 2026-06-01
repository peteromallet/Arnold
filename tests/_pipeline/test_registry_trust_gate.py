"""T8: trust-gated exec_module across both discovery paths.

Verifies (under MEGAPLAN_M6_MANIFEST_DISCOVERY=1):
- (a) flag-ON + in-tree defers exec_module until PipelineRegistry.get(name).
- (b) flag-ON + out-of-tree (QUARANTINED) never calls exec_module.
- (c) the discover_python_pipelines secondary loop does not re-import under flag-ON.
"""

from __future__ import annotations

import textwrap
import warnings
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from megaplan._pipeline import registry


WELL_FORMED_PIPELINE = '''\
"""A well-formed pipeline used for trust-gate tests."""

name = "pipe-placeholder"
description = "test pipeline"
default_profile = "claude-default"
supported_modes = ("code",)
driver = ("subprocess_isolated", "graph+loop-node")
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("plan",)


def build_pipeline():
    raise RuntimeError("exec_module was called — build_pipeline body ran")
'''

SKILL_MD = "# Skill\nverdict vocab.\n"


def _make_in_tree_pkg(in_tree_root: Path, name: str) -> Path:
    pkg = in_tree_root / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        WELL_FORMED_PIPELINE.replace("pipe-placeholder", name.replace("_", "-"))
    )
    (pkg / "SKILL.md").write_text(SKILL_MD)
    return pkg / "__init__.py"


def _make_out_of_tree_pkg(out_root: Path, name: str) -> Path:
    pkg = out_root / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        WELL_FORMED_PIPELINE.replace("pipe-placeholder", name.replace("_", "-"))
    )
    (pkg / "SKILL.md").write_text(SKILL_MD)
    return pkg / "__init__.py"


@pytest.fixture
def flag_on(monkeypatch):
    monkeypatch.setenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", "1")


@pytest.fixture
def flag_off(monkeypatch):
    monkeypatch.setenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", "0")


@pytest.fixture
def isolated_scan_roots(tmp_path, monkeypatch):
    """Patch _get_scan_roots to a clean tmp in-tree dir under megaplan/pipelines."""
    # Simulate an in-tree path inside the megaplan/pipelines fragment so
    # trust.classify() returns AUTO_EXEC for these temp files.
    in_tree_root = tmp_path / "fake_repo" / "megaplan" / "pipelines"
    in_tree_root.mkdir(parents=True)
    out_root = tmp_path / "user" / "pipelines"
    out_root.mkdir(parents=True)
    monkeypatch.setattr(
        registry,
        "_get_scan_roots",
        lambda: [(in_tree_root, "megaplan.pipelines"), (out_root, None)],
    )
    return in_tree_root, out_root


def test_flag_on_in_tree_defers_exec_module_until_get(
    flag_on, isolated_scan_roots, tmp_path,
):
    """(a) Flag-ON, in-tree: scan must not exec_module; only .get(name) does."""
    in_tree_root, _ = isolated_scan_roots
    _make_in_tree_pkg(in_tree_root, "pipe_in_tree_a")

    reg = registry.PipelineRegistry()

    with patch.object(registry, "_load_module_from_path") as load_spy:
        # _ensure_discovered (manifest path) must NOT call _load_module_from_path.
        reg._ensure_discovered()
        assert load_spy.call_count == 0, (
            "exec_module path invoked during discovery under flag-ON"
        )

        # Builder is registered and marked deferred.
        assert "pipe-in-tree-a" in reg.builders
        assert getattr(reg.builders["pipe-in-tree-a"], "_m6_deferred", False)

        # Now .get(name) should trigger exec_module (AUTO_EXEC tier).
        load_spy.return_value = None  # short-circuit; will raise RuntimeError
        with pytest.raises(RuntimeError, match="failed to load"):
            reg.get("pipe-in-tree-a")
        assert load_spy.call_count == 1, (
            "exec_module deferred path not invoked at .get()"
        )


def test_flag_on_out_of_tree_never_calls_exec_module(
    flag_on, isolated_scan_roots, tmp_path, monkeypatch,
):
    """(b) Flag-ON, out-of-tree QUARANTINED: exec_module is never called."""
    _, out_root = isolated_scan_roots
    _make_out_of_tree_pkg(out_root, "pipe_user_a")
    ledger_dir = tmp_path / "budget-ledger"
    monkeypatch.setenv("MEGAPLAN_BUDGET_AUTHORITY_DIR", str(ledger_dir))

    reg = registry.PipelineRegistry()

    with patch.object(registry, "_load_module_from_path") as load_spy:
        reg._ensure_discovered()
        # Discovery: no exec_module under manifest-first.
        assert load_spy.call_count == 0
        assert "pipe-user-a" in reg.builders
        meta = reg.metadata_for("pipe-user-a")
        assert meta["trust_tier"] == "quarantined"
        assert meta["tenant_id"].startswith("pipeline_")
        assert meta["quota_reserved"] is True
        ledger = json.loads((ledger_dir / f"{meta['tenant_id']}.budget.json").read_text())
        assert ledger["sub_budget_usd"] == meta["sub_budget_usd"]

        # .get(name): trust gate must veto exec_module for quarantined paths.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = reg.get("pipe-user-a")
        assert result is None, "quarantined pipeline must return None"
        assert load_spy.call_count == 0, (
            "exec_module was called for a QUARANTINED out-of-tree module"
        )
        assert any("QUARANTINED" in str(w.message) for w in caught), (
            "no QUARANTINED warning emitted"
        )


def test_flag_on_secondary_loop_no_reimport(
    flag_on, isolated_scan_roots,
):
    """(c) registry.py:568 (secondary) loop in discover_python_pipelines
    must not re-import any module under flag-ON.
    """
    in_tree_root, out_root = isolated_scan_roots
    _make_in_tree_pkg(in_tree_root, "pipe_in_tree_b")
    _make_out_of_tree_pkg(out_root, "pipe_user_b")

    with patch.object(registry, "_load_module_from_path") as load_spy:
        quads = registry.discover_python_pipelines()
        assert load_spy.call_count == 0, (
            "discover_python_pipelines re-imported modules under flag-ON"
        )

    names = {q[0] for q in quads}
    assert "pipe-in-tree-b" in names
    assert "pipe-user-b" in names
    # Returned builders are deferred-marked.
    for cli_name, builder, _meta, _path in quads:
        assert getattr(builder, "_m6_deferred", False), (
            f"builder for {cli_name} is not deferred under flag-ON"
        )


def test_flag_off_legacy_path_still_eagerly_imports(
    flag_off, isolated_scan_roots,
):
    """Sanity: flag-OFF path is unchanged — exec_module IS invoked at scan."""
    in_tree_root, _ = isolated_scan_roots
    _make_in_tree_pkg(in_tree_root, "pipe_in_tree_c")

    # Use a real wraps to keep behaviour; just assert it was called.
    with patch.object(
        registry, "_load_module_from_path",
        wraps=registry._load_module_from_path,
    ) as load_spy:
        # Eager discovery may raise because our stub build_pipeline raises
        # on call — but for FLAG-OFF, _load_module_from_path is invoked
        # during the *discovery* pass itself.
        try:
            registry.discover_python_pipelines()
        except Exception:
            pass
        assert load_spy.called, (
            "flag-OFF must invoke _load_module_from_path during discovery"
        )
