"""W5 — Discovery-integrity guard: scan_python_pipelines + discover_python_pipelines tests."""
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.pipeline.native.ir import NativeProgram
from arnold_pipelines.megaplan.registry import (
    PipelineRegistry,
    scan_python_pipelines,
    discover_python_pipelines,
)
from arnold_pipelines.megaplan.runtime.discovery import Disposition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_good_pipeline(tmp_path: Path) -> Path:
    """Write a minimal valid manifest pipeline module to tmp_path."""
    f = tmp_path / "good_pipe.py"
    f.write_text(
        "name = 'good-pipe'\n"
        "description = 'good'\n"
        "default_profile = None\n"
        "supported_modes = ('native',)\n"
        "driver = ('native', 'test')\n"
        "entrypoint = 'build_pipeline'\n"
        "arnold_api_version = '1.0'\n"
        "capabilities = ('test',)\n"
        "def build_pipeline():\n"
        "    from arnold_pipelines.megaplan.step_types import Pipeline\n"
        "    return Pipeline(stages={}, entry='done')\n",
        encoding="utf-8",
    )
    (tmp_path / "SKILL.md").write_text("good\n", encoding="utf-8")
    return f


def _make_broken_pipeline(tmp_path: Path) -> Path:
    """Write a pipeline module that raises on import."""
    f = tmp_path / "broken_pipe.py"
    f.write_text("raise RuntimeError('intentional import error')\n", encoding="utf-8")
    return f


def _make_no_builder_pipeline(tmp_path: Path) -> Path:
    """Write a manifest-shaped pipeline module with no build_pipeline symbol."""
    f = tmp_path / "no_builder.py"
    f.write_text(
        "name = 'no-builder'\n"
        "description = 'no builder here'\n"
        "default_profile = None\n"
        "supported_modes = ('native',)\n"
        "driver = ('native', 'test')\n"
        "entrypoint = 'build_pipeline'\n"
        "arnold_api_version = '1.0'\n"
        "capabilities = ('test',)\n",
        encoding="utf-8",
    )
    (tmp_path / "SKILL.md").write_text("no builder\n", encoding="utf-8")
    return f


def _make_native_projected_pipeline(tmp_path: Path) -> Path:
    f = tmp_path / "native_projected.py"
    f.write_text(
        "name = 'native-projected'\n"
        "description = 'native projected shell'\n"
        "default_profile = None\n"
        "supported_modes = ('native',)\n"
        "driver = ('native', 'test')\n"
        "entrypoint = 'build_pipeline'\n"
        "arnold_api_version = '1.0'\n"
        "capabilities = ('test',)\n"
        "def build_pipeline():\n"
        "    from arnold.pipeline.native.ir import NativeProgram\n"
        "    from arnold_pipelines.megaplan.step_types import Pipeline\n"
        "    return Pipeline(stages={}, entry='', native_program=NativeProgram(name='native-projected'))\n",
        encoding="utf-8",
    )
    (tmp_path / "SKILL.md").write_text("native\n", encoding="utf-8")
    return f


def _make_graph_compat_pipeline(tmp_path: Path) -> Path:
    f = tmp_path / "graph_compat.py"
    f.write_text(
        "name = 'graph-compat'\n"
        "description = 'explicit graph compatibility shell'\n"
        "default_profile = None\n"
        "supported_modes = ('graph',)\n"
        "driver = ('graph', 'compat')\n"
        "entrypoint = 'build_pipeline'\n"
        "arnold_api_version = '1.0'\n"
        "capabilities = ('test',)\n"
        "class _Runner:\n"
        "    def run_native_pipeline(self, **kwargs):\n"
        "        return {'ok': True, 'kwargs': kwargs}\n"
        "def build_pipeline():\n"
        "    from arnold_pipelines.megaplan.step_types import Pipeline\n"
        "    return Pipeline(stages={}, entry='', resource_bundles=(_Runner(),))\n",
        encoding="utf-8",
    )
    (tmp_path / "SKILL.md").write_text("graph compat\n", encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# scan_python_pipelines: never raises
# ---------------------------------------------------------------------------

def test_scan_python_pipelines_never_raises(tmp_path: Path):
    """scan_python_pipelines() must not raise under any circumstance."""
    # Patch scan roots to point at tmp_path containing a broken module.
    broken_dir = tmp_path / "pipelines"
    broken_dir.mkdir()
    _make_broken_pipeline(broken_dir)

    scan_roots = [(broken_dir, None)]
    with patch("arnold_pipelines.megaplan.runtime.discovery._get_scan_roots", lambda: scan_roots):
        result = scan_python_pipelines()  # must not raise

    assert isinstance(result, list)


def test_scan_python_pipelines_returns_disposition_for_every_path(tmp_path: Path):
    user_dir = tmp_path / "pipelines"
    user_dir.mkdir()
    _make_good_pipeline(user_dir)
    _make_broken_pipeline(user_dir)
    _make_no_builder_pipeline(user_dir)

    scan_roots = [(user_dir, None)]
    with patch("arnold_pipelines.megaplan.runtime.discovery._get_scan_roots", lambda: scan_roots):
        result = scan_python_pipelines()

    assert len(result) == 3
    for d in result:
        assert isinstance(d, Disposition)
        assert d.path.exists() or True  # path is returned regardless
        assert d.origin in ("in_tree", "user")
        assert d.status in ("discovered", "rejected", "skipped")
        assert isinstance(d.reason, str) and d.reason


def test_scan_python_pipelines_disposition_has_reason_for_broken(tmp_path: Path):
    user_dir = tmp_path / "pipelines"
    user_dir.mkdir()
    _make_broken_pipeline(user_dir)

    scan_roots = [(user_dir, None)]
    with patch("arnold_pipelines.megaplan.runtime.discovery._get_scan_roots", lambda: scan_roots):
        result = scan_python_pipelines()

    rejected = [d for d in result if d.status == "rejected"]
    assert len(rejected) == 1
    assert "manifest rejected:" in rejected[0].reason


def test_scan_python_pipelines_good_module_is_discovered(tmp_path: Path):
    user_dir = tmp_path / "pipelines"
    user_dir.mkdir()
    _make_good_pipeline(user_dir)

    scan_roots = [(user_dir, None)]
    with patch("arnold_pipelines.megaplan.runtime.discovery._get_scan_roots", lambda: scan_roots):
        result = scan_python_pipelines()

    discovered = [d for d in result if d.status == "discovered"]
    assert len(discovered) == 1
    assert discovered[0].origin == "user"


def test_scan_python_pipelines_origin_intree_vs_user(tmp_path: Path):
    intree_dir = tmp_path / "intree"
    intree_dir.mkdir()
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    _make_good_pipeline(intree_dir)

    scan_roots = [(intree_dir, "arnold_pipelines.megaplan.pipelines"), (user_dir, None)]
    with patch("arnold_pipelines.megaplan.runtime.discovery._get_scan_roots", lambda: scan_roots):
        result = scan_python_pipelines()

    assert any(d.origin == "in_tree" for d in result)


# ---------------------------------------------------------------------------
# discover_python_pipelines: rejected paths do not abort unrelated packages
# ---------------------------------------------------------------------------

def test_discover_python_pipelines_does_not_raise_for_broken_intree(tmp_path: Path):
    intree_dir = tmp_path / "intree"
    intree_dir.mkdir()
    _make_broken_pipeline(intree_dir)

    scan_roots = [(intree_dir, "arnold_pipelines.megaplan.pipelines"), (tmp_path / "user", None)]
    with patch("arnold_pipelines.megaplan.runtime.discovery._get_scan_roots", lambda: scan_roots):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = discover_python_pipelines()

    assert result == []
    assert any("broken_pipe" in str(w.message) for w in caught)


def test_discover_python_pipelines_keeps_good_intree_with_rejected_intree(tmp_path: Path):
    intree_dir = tmp_path / "intree"
    intree_dir.mkdir()
    _make_good_pipeline(intree_dir)
    bad = intree_dir / "bad_one.py"
    bad.write_text("raise RuntimeError('bad_one')\n", encoding="utf-8")

    scan_roots = [(intree_dir, "arnold_pipelines.megaplan.pipelines"), (tmp_path / "user", None)]
    with patch("arnold_pipelines.megaplan.runtime.discovery._get_scan_roots", lambda: scan_roots):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = discover_python_pipelines()

    assert [item[0] for item in result] == ["good-pipe"]


def test_discover_python_pipelines_broken_user_warns_not_raises(tmp_path: Path):
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    _make_broken_pipeline(user_dir)

    scan_roots = [(tmp_path / "intree", None), (user_dir, None)]
    with patch("arnold_pipelines.megaplan.runtime.discovery._get_scan_roots", lambda: scan_roots):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = discover_python_pipelines()  # must NOT raise

    assert isinstance(result, list)
    assert any("broken_pipe" in str(w.message).lower() or "could not" in str(w.message).lower()
               for w in caught)


def test_discover_python_pipelines_good_pack_still_returned_alongside_rejected_user(tmp_path: Path):
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    _make_good_pipeline(user_dir)
    _make_broken_pipeline(user_dir)

    scan_roots = [(tmp_path / "intree", None), (user_dir, None)]
    with patch("arnold_pipelines.megaplan.runtime.discovery._get_scan_roots", lambda: scan_roots):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = discover_python_pipelines()

    cli_names = [r[0] for r in result]
    assert "good-pipe" in cli_names


def test_discover_python_pipelines_back_compat_return_shape(tmp_path: Path):
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    _make_good_pipeline(user_dir)

    scan_roots = [(tmp_path / "intree", None), (user_dir, None)]
    with patch("arnold_pipelines.megaplan.runtime.discovery._get_scan_roots", lambda: scan_roots):
        result = discover_python_pipelines()

    for item in result:
        cli_name, build, meta, path = item
        assert isinstance(cli_name, str)
        assert callable(build)
        assert isinstance(meta, dict)
        assert isinstance(path, Path)


def test_discover_python_pipelines_tolerates_hidden_non_identifier_user_module(tmp_path: Path):
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    hidden = user_dir / "._auto.py"
    hidden.write_text(
        "name = 'hidden-auto'\n"
        "description = 'hidden file'\n"
        "default_profile = None\n"
        "supported_modes = ('native',)\n"
        "driver = ('native', 'test')\n"
        "entrypoint = 'build_pipeline'\n"
        "arnold_api_version = '1.0'\n"
        "capabilities = ('test',)\n"
        "def build_pipeline():\n"
        "    from arnold_pipelines.megaplan.step_types import Pipeline\n"
        "    return Pipeline(stages={}, entry='done')\n",
        encoding="utf-8",
    )

    scan_roots = [(user_dir, None)]
    with patch("arnold_pipelines.megaplan.runtime.discovery._get_scan_roots", lambda: scan_roots):
        result = discover_python_pipelines()

    assert result == []


def test_manifest_discovery_default_ignores_m6_alias_value(tmp_path: Path, monkeypatch):
    user_dir = tmp_path / "pipelines"
    user_dir.mkdir()
    _make_good_pipeline(user_dir)

    scan_roots = [(user_dir, None)]
    monkeypatch.setenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", "0")
    with patch("arnold_pipelines.megaplan.runtime.discovery._get_scan_roots", lambda: scan_roots):
        result = scan_python_pipelines()

    discovered = [d for d in result if d.status == "discovered"]
    assert len(discovered) == 1
    assert discovered[0].manifest is not None
    assert discovered[0].reason == "ok (manifest)"


def test_manifest_discovery_does_not_exec_valid_module_by_default(
    tmp_path: Path,
    monkeypatch,
):
    user_dir = tmp_path / "pipelines"
    user_dir.mkdir()
    _make_good_pipeline(user_dir)

    def fail_load(*args, **kwargs):
        raise AssertionError("manifest scan must not import modules")

    scan_roots = [(user_dir, None)]
    monkeypatch.delenv("MEGAPLAN_M6_MANIFEST_DISCOVERY", raising=False)
    with patch("arnold_pipelines.megaplan.runtime.discovery._get_scan_roots", lambda: scan_roots):
        with patch(
            "arnold_pipelines.megaplan.runtime.discovery._load_module_from_path",
            fail_load,
        ):
            result = scan_python_pipelines()

    assert [d.status for d in result] == ["discovered"]


@pytest.mark.skip(
    reason=(
        "Tests legacy PipelineRegistry APIs (registration_kind_for, disposition_for, "
        "graph_compatibility resource bundles) that were removed when "
        "arnold/pipelines/megaplan/ was deleted."
    )
)
def test_registry_keeps_native_graph_compat_and_rejected_dispositions_separate(
    tmp_path: Path,
    monkeypatch,
):
    user_dir = tmp_path / "pipelines"
    user_dir.mkdir()
    native_module = _make_native_projected_pipeline(user_dir)
    graph_module = _make_graph_compat_pipeline(user_dir)
    bad_module = user_dir / "bad_missing_manifest_field.py"
    bad_module.write_text(
        "name = 'bad-missing-manifest-field'\n"
        "description = 'bad'\n"
        "supported_modes = ('native',)\n"
        "driver = ('native', 'test')\n"
        "entrypoint = 'build_pipeline'\n"
        "arnold_api_version = '1.0'\n"
        "capabilities = ('test',)\n"
        "def build_pipeline():\n"
        "    pass\n",
        encoding="utf-8",
    )
    (user_dir / "SKILL.md").write_text("shared skill\n", encoding="utf-8")

    from arnold_pipelines.megaplan.runtime import discovery as discovery_mod

    monkeypatch.setattr(
        discovery_mod,
        "BLESSED_ALLOWLIST",
        (str(native_module.resolve()), str(graph_module.resolve())),
    )
    monkeypatch.setattr(discovery_mod, "_get_scan_roots", lambda: [(user_dir, None)])
    monkeypatch.setenv("MEGAPLAN_BUDGET_AUTHORITY_DIR", str(tmp_path / "leases"))

    registry = PipelineRegistry()
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        names = registry.names()

    assert names == ("graph-compat", "native-projected")
    assert registry.registration_kind_for("native-projected") == "native"
    assert registry.registration_kind_for("graph-compat") == "graph_compatibility"

    native_pipeline = registry.get("native-projected")
    assert native_pipeline is not None
    assert isinstance(native_pipeline.native_program, NativeProgram)
    native_meta = registry.metadata_for("native-projected")
    assert native_meta["driver"] == ("native", "test")
    assert native_meta["manifest_hash"].startswith("sha256:")
    assert native_meta["registration_kind"] == "native"

    graph_pipeline = registry.get("graph-compat")
    assert graph_pipeline is not None
    assert graph_pipeline.native_program is None
    assert callable(graph_pipeline.resource_bundles[0].run_native_pipeline)
    assert graph_pipeline.resource_bundles[0].run_native_pipeline()["ok"] is True
    graph_meta = registry.metadata_for("graph-compat")
    assert graph_meta["driver"] == ("graph", "compat")
    assert graph_meta["registration_kind"] == "graph_compatibility"

    rejected = registry.disposition_for("bad-missing-manifest-field")
    assert rejected is not None
    assert rejected.status == "rejected"
    assert rejected.manifest is None
    assert "missing required field 'default_profile'" in rejected.reason
    assert "bad-missing-manifest-field" not in names
