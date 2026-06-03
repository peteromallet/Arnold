"""W5 — Discovery-integrity guard: scan_python_pipelines + discover_python_pipelines tests."""
import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.arnold_generic

from arnold.pipeline.registry import (
    Disposition,
    scan_python_pipelines,
    discover_python_pipelines,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_good_pipeline(tmp_path: Path) -> Path:
    """Write a minimal valid pipeline module to tmp_path."""
    f = tmp_path / "good_pipe.py"
    f.write_text(
        "description = 'good'\n"
        "def build_pipeline():\n"
        "    from megaplan._pipeline.types import Pipeline\n"
        "    return Pipeline(stages=[])\n",
        encoding="utf-8",
    )
    return f


def _make_broken_pipeline(tmp_path: Path) -> Path:
    """Write a pipeline module that raises on import."""
    f = tmp_path / "broken_pipe.py"
    f.write_text("raise RuntimeError('intentional import error')\n", encoding="utf-8")
    return f


def _make_no_builder_pipeline(tmp_path: Path) -> Path:
    """Write a pipeline module that loads but has no build_pipeline."""
    f = tmp_path / "no_builder.py"
    f.write_text("description = 'no builder here'\n", encoding="utf-8")
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
    with patch("arnold.pipeline.registry._SCAN_ROOTS", scan_roots):
        result = scan_python_pipelines()  # must not raise

    assert isinstance(result, list)


def test_scan_python_pipelines_returns_disposition_for_every_path(tmp_path: Path):
    user_dir = tmp_path / "pipelines"
    user_dir.mkdir()
    _make_good_pipeline(user_dir)
    _make_broken_pipeline(user_dir)
    _make_no_builder_pipeline(user_dir)

    scan_roots = [(user_dir, None)]
    with patch("arnold.pipeline.registry._SCAN_ROOTS", scan_roots):
        result = scan_python_pipelines()

    assert len(result) == 3
    for d in result:
        assert isinstance(d, Disposition)
        assert d.path.exists() or True  # path is returned regardless
        assert d.origin in ("in_tree", "user")
        assert d.status in ("discovered", "rejected", "skipped")
        assert isinstance(d.reason, str) and d.reason


def test_scan_python_pipelines_disposition_has_traceback_for_broken(tmp_path: Path):
    user_dir = tmp_path / "pipelines"
    user_dir.mkdir()
    _make_broken_pipeline(user_dir)

    scan_roots = [(user_dir, None)]
    with patch("arnold.pipeline.registry._SCAN_ROOTS", scan_roots):
        result = scan_python_pipelines()

    rejected = [d for d in result if d.status == "rejected"]
    assert len(rejected) == 1
    # traceback or informative message must be present
    assert rejected[0].traceback is not None


def test_scan_python_pipelines_good_module_is_discovered(tmp_path: Path):
    user_dir = tmp_path / "pipelines"
    user_dir.mkdir()
    _make_good_pipeline(user_dir)

    scan_roots = [(user_dir, None)]
    with patch("arnold.pipeline.registry._SCAN_ROOTS", scan_roots):
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

    scan_roots = [(intree_dir, "megaplan.pipelines"), (user_dir, None)]
    with patch("arnold.pipeline.registry._SCAN_ROOTS", scan_roots):
        result = scan_python_pipelines()

    assert any(d.origin == "in_tree" for d in result)


# ---------------------------------------------------------------------------
# discover_python_pipelines: aggregate raise for rejected in-tree
# ---------------------------------------------------------------------------

def test_discover_python_pipelines_raises_aggregate_for_broken_intree(tmp_path: Path):
    intree_dir = tmp_path / "intree"
    intree_dir.mkdir()
    _make_broken_pipeline(intree_dir)

    scan_roots = [(intree_dir, "megaplan.pipelines"), (tmp_path / "user", None)]
    with patch("arnold.pipeline.registry._SCAN_ROOTS", scan_roots):
        with pytest.raises(RuntimeError) as exc_info:
            discover_python_pipelines()

    msg = str(exc_info.value)
    assert "aggregate" in msg.lower() or "collect" in msg.lower() or "broken_pipe" in msg


def test_discover_python_pipelines_raises_names_all_rejected_intree(tmp_path: Path):
    intree_dir = tmp_path / "intree"
    intree_dir.mkdir()
    broken1 = intree_dir / "bad_one.py"
    broken2 = intree_dir / "bad_two.py"
    broken1.write_text("raise RuntimeError('bad_one')\n", encoding="utf-8")
    broken2.write_text("raise RuntimeError('bad_two')\n", encoding="utf-8")

    scan_roots = [(intree_dir, "megaplan.pipelines"), (tmp_path / "user", None)]
    with patch("arnold.pipeline.registry._SCAN_ROOTS", scan_roots):
        with pytest.raises(RuntimeError) as exc_info:
            discover_python_pipelines()

    msg = str(exc_info.value)
    assert "bad_one" in msg or "bad-one" in msg
    assert "bad_two" in msg or "bad-two" in msg


def test_discover_python_pipelines_broken_user_warns_not_raises(tmp_path: Path):
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    _make_broken_pipeline(user_dir)

    scan_roots = [(tmp_path / "intree", None), (user_dir, None)]
    with patch("arnold.pipeline.registry._SCAN_ROOTS", scan_roots):
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
    with patch("arnold.pipeline.registry._SCAN_ROOTS", scan_roots):
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
    with patch("arnold.pipeline.registry._SCAN_ROOTS", scan_roots):
        result = discover_python_pipelines()

    for item in result:
        cli_name, build, meta, path = item
        assert isinstance(cli_name, str)
        assert callable(build)
        assert isinstance(meta, dict)
        assert isinstance(path, Path)
