"""Fixture smoke tests for the package-disposition manifest validator.

Covers: file rows, directory rows, split parents with children, symbol
children that do not add coverage, duplicate coverage, orphan detection,
generated/cache exclusion matching, path normalization, and a real-manifest
entry point.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_package_disposition.py"


# ── helpers ──────────────────────────────────────────────────────────────


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "validate_package_disposition", SCRIPT_PATH
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _init_repo(tmp_path: Path, files: dict[str, str]) -> tuple[Path, Path]:
    """Create a temp git repo with the given files; return (repo_root, manifest_path)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(
        ["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True
    )
    for relative_path, content in files.items():
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(
        ["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True
    )
    manifest_path = repo_root / "docs" / "arnold" / "package-disposition.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    return repo_root, manifest_path


def _manifest_with_rows(
    rows: list[dict[str, object]], **overrides: object
) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": 1,
        "valid_dispositions": [
            "arnold-core",
            "arnold-service-interface",
            "arnold-adapter",
            "arnold-shared-leaf",
            "megaplan-plugin",
            "product-app",
            "legacy-hold",
            "delete-merge",
            "split-required",
        ],
        "valid_granularities": ["directory", "file", "symbol", "split"],
        "coverage_exclusions": [],
        "rows": rows,
        "parity_gates": [],
        "runtime_settings_gates": [],
    }
    base.update(overrides)
    return base


def _row(
    source: str,
    granularity: str,
    disposition: str,
    *,
    target: str = "arnold/example.py",
    **overrides: object,
) -> dict[str, object]:
    data: dict[str, object] = {
        "source": source,
        "target": target,
        "granularity": granularity,
        "disposition": disposition,
        "reason": "test row",
        "blockers": [],
        "allowed_imports": [],
        "forbidden_imports": [],
        "vocabulary_owned": [],
        "string_policy": [],
        "extraction_prerequisite": [],
        "first_extraction_unit": None,
        "tests_gates": [],
        "configurable_seams": [],
    }
    data.update(overrides)
    return data


# ── file rows ────────────────────────────────────────────────────────────


def test_file_row_covers_tracked_file(tmp_path: Path) -> None:
    """A file row for a tracked file is accepted and covers exactly that file."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {
            "megaplan/core/a.py": "A = 1\n",
            "megaplan/core/b.py": "B = 2\n",
        },
    )
    manifest = _manifest_with_rows(
        [
            _row("megaplan/core/a.py", "file", "arnold-core"),
            _row("megaplan/core/b.py", "file", "arnold-core"),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert errors == [], f"Unexpected errors: {errors}"


def test_file_row_rejects_nonexistent_file(tmp_path: Path) -> None:
    """A file row pointing to a non-existent tracked file produces an error."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/real.py": "REAL = 1\n"},
    )
    manifest = _manifest_with_rows(
        [
            _row("megaplan/real.py", "file", "arnold-core"),
            _row("megaplan/fake.py", "file", "arnold-core"),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "must be an exact tracked file" in e for e in errors
    ), f"Expected 'exact tracked file' error, got: {errors}"


# ── directory rows ───────────────────────────────────────────────────────


def test_directory_row_covers_recursive_files(tmp_path: Path) -> None:
    """A directory row covers all tracked .py files recursively under it."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {
            "megaplan/pkg/a.py": "A = 1\n",
            "megaplan/pkg/b.py": "B = 2\n",
            "megaplan/pkg/sub/c.py": "C = 3\n",
        },
    )
    manifest = _manifest_with_rows(
        [_row("megaplan/pkg", "directory", "megaplan-plugin", target="megaplan/pkg")]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert errors == [], f"Unexpected errors: {errors}"


def test_directory_row_rejects_file_path(tmp_path: Path) -> None:
    """A directory row whose source is a tracked file produces an error."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/pkg/a.py": "A = 1\n"},
    )
    manifest = _manifest_with_rows(
        [_row("megaplan/pkg/a.py", "directory", "megaplan-plugin", target="megaplan/pkg")]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "is a tracked file" in e for e in errors
    ), f"Expected 'tracked file' error, got: {errors}"


def test_directory_row_rejects_empty_directory(tmp_path: Path) -> None:
    """A directory row with no tracked .py files produces an error."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {
            "megaplan/pkg/readme.txt": "not python\n",
            "megaplan/other/a.py": "A = 1\n",
        },
    )
    manifest = _manifest_with_rows(
        [
            _row("megaplan/pkg", "directory", "megaplan-plugin", target="megaplan/pkg"),
            _row("megaplan/other/a.py", "file", "arnold-core"),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "does not contain tracked" in e for e in errors
    ), f"Expected 'does not contain tracked' error, got: {errors}"


# ── split parents with children ──────────────────────────────────────────


def test_split_file_parent_with_symbol_children_accepted(tmp_path: Path) -> None:
    """Split file parent with symbol children is accepted; coverage held by split."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {
            "megaplan/cli/arnold.py": "def main(): pass\n",
            "megaplan/other/a.py": "A = 1\n",
        },
    )
    manifest = _manifest_with_rows(
        [
            _row(
                "megaplan/cli/arnold.py",
                "split",
                "split-required",
                target="megaplan/cli/arnold.py",
            ),
            _row(
                "megaplan/cli/arnold.py",
                "symbol",
                "megaplan-plugin",
                target="megaplan/cli/arnold.py",
            ),
            _row(
                "megaplan/cli/arnold.py",
                "symbol",
                "arnold-core",
                target="megaplan/cli/arnold.py",
            ),
            _row("megaplan/other/a.py", "file", "arnold-core"),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert errors == [], f"Unexpected errors: {errors}"


def test_split_directory_parent_with_descendant_children_accepted(tmp_path: Path) -> None:
    """Split directory parent with descendant file rows is accepted."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {
            "megaplan/cli/arnold.py": "def main(): pass\n",
            "megaplan/cli/helpers.py": "def help(): pass\n",
        },
    )
    manifest = _manifest_with_rows(
        [
            _row("megaplan/cli", "split", "split-required", target="megaplan/cli"),
            _row(
                "megaplan/cli/arnold.py",
                "file",
                "megaplan-plugin",
                target="megaplan/cli/arnold.py",
            ),
            _row(
                "megaplan/cli/helpers.py",
                "file",
                "arnold-core",
                target="megaplan/cli/helpers.py",
            ),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert errors == [], f"Unexpected errors: {errors}"


def test_split_file_parent_without_symbol_children_rejected(tmp_path: Path) -> None:
    """Split file parent without symbol child rows produces an error."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/cli/solo.py": "SOLO = 1\n"},
    )
    manifest = _manifest_with_rows(
        [
            _row(
                "megaplan/cli/solo.py",
                "split",
                "split-required",
                target="megaplan/cli/solo.py",
            ),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "needs symbol child rows" in e for e in errors
    ), f"Expected 'needs symbol child rows', got: {errors}"


def test_split_directory_parent_without_descendants_rejected(tmp_path: Path) -> None:
    """Split directory parent without descendant rows produces an error."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/cli/solo.py": "SOLO = 1\n"},
    )
    manifest = _manifest_with_rows(
        [_row("megaplan/cli", "split", "split-required", target="megaplan/cli")]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "needs descendant child rows" in e for e in errors
    ), f"Expected 'needs descendant child rows', got: {errors}"


# ── symbol children do not add coverage ──────────────────────────────────


def test_symbol_children_do_not_cause_duplicate_coverage(tmp_path: Path) -> None:
    """Multiple symbol children for the same split parent do not cause duplicate coverage."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/hybrid/x.py": "X = 1\n"},
    )
    manifest = _manifest_with_rows(
        [
            _row(
                "megaplan/hybrid/x.py",
                "split",
                "split-required",
                target="megaplan/hybrid/x.py",
            ),
            _row(
                "megaplan/hybrid/x.py",
                "symbol",
                "megaplan-plugin",
                target="megaplan/hybrid/x.py",
            ),
            _row(
                "megaplan/hybrid/x.py",
                "symbol",
                "arnold-core",
                target="megaplan/hybrid/x.py",
            ),
            _row(
                "megaplan/hybrid/x.py",
                "symbol",
                "arnold-adapter",
                target="megaplan/hybrid/x.py",
            ),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert not any(
        "duplicate coverage" in e for e in errors
    ), f"Unexpected duplicate coverage: {errors}"
    assert errors == [], f"Unexpected errors: {errors}"


# ── duplicate coverage ───────────────────────────────────────────────────


def test_duplicate_coverage_file_and_directory(tmp_path: Path) -> None:
    """File and directory rows covering the same file produce duplicate coverage error."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {
            "megaplan/hybrid/one.py": "ONE = 1\n",
            "megaplan/hybrid/two.py": "TWO = 2\n",
        },
    )
    manifest = _manifest_with_rows(
        [
            _row("megaplan/hybrid", "directory", "megaplan-plugin", target="megaplan/hybrid"),
            _row(
                "megaplan/hybrid/one.py",
                "file",
                "megaplan-plugin",
                target="megaplan/hybrid/one.py",
            ),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "duplicate coverage" in e for e in errors
    ), f"Expected 'duplicate coverage', got: {errors}"


def test_duplicate_coverage_two_directories(tmp_path: Path) -> None:
    """Two directory rows with overlapping files produce duplicate coverage error."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {
            "megaplan/pkg/a.py": "A = 1\n",
            "megaplan/pkg/sub/b.py": "B = 2\n",
        },
    )
    manifest = _manifest_with_rows(
        [
            _row("megaplan/pkg", "directory", "megaplan-plugin", target="megaplan/pkg"),
            _row(
                "megaplan/pkg/sub",
                "directory",
                "megaplan-plugin",
                target="megaplan/pkg/sub",
            ),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "duplicate coverage" in e for e in errors
    ), f"Expected 'duplicate coverage', got: {errors}"


def test_duplicate_row_same_source_granularity_rejected(tmp_path: Path) -> None:
    """Two rows with the same source and granularity are rejected at parse time."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/core/a.py": "A = 1\n"},
    )
    manifest = _manifest_with_rows(
        [
            _row("megaplan/core/a.py", "file", "arnold-core"),
            _row("megaplan/core/a.py", "file", "arnold-core", target="arnold/other.py"),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "duplicates an earlier row" in e for e in errors
    ), f"Expected 'duplicates an earlier row', got: {errors}"


# ── orphan detection ─────────────────────────────────────────────────────


def test_orphan_symbol_without_any_parent(tmp_path: Path) -> None:
    """Symbol row without a split parent produces an orphan error."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/core/a.py": "A = 1\n"},
    )
    manifest = _manifest_with_rows(
        [
            _row(
                "megaplan/core/a.py",
                "symbol",
                "megaplan-plugin",
                target="megaplan/core/a.py",
            ),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "must refine a split row" in e for e in errors
    ), f"Expected 'must refine a split row', got: {errors}"


def test_orphan_symbol_with_file_row_not_split(tmp_path: Path) -> None:
    """Symbol row paired with a file row (not split) still produces orphan error."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/core/a.py": "A = 1\n"},
    )
    manifest = _manifest_with_rows(
        [
            _row("megaplan/core/a.py", "file", "arnold-core"),
            _row(
                "megaplan/core/a.py",
                "symbol",
                "megaplan-plugin",
                target="megaplan/core/a.py",
            ),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "must refine a split row" in e for e in errors
    ), f"Expected 'must refine a split row', got: {errors}"


# ── generated / cache exclusion matching ─────────────────────────────────


def test_exclusion_matches_remove_from_coverage(tmp_path: Path) -> None:
    """Exclusion glob that matches tracked files removes them from coverage."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {
            "megaplan/core/a.py": "A = 1\n",
            "megaplan/core/__pycache__/cached.py": "# auto-generated cache\n",
            "megaplan/core/b.py": "B = 2\n",
        },
    )
    manifest = _manifest_with_rows(
        [
            _row("megaplan/core/a.py", "file", "arnold-core"),
            _row("megaplan/core/b.py", "file", "arnold-core"),
        ],
        coverage_exclusions=[
            {
                "source": "megaplan/core/__pycache__/*.py",
                "reason": "CPython bytecode cache, not authored source",
                "evidence": "git ls-files match against __pycache__ artifacts",
            },
        ],
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert errors == [], f"Unexpected errors with exclusion: {errors}"


def test_exclusion_with_no_matches_produces_error(tmp_path: Path) -> None:
    """Exclusion glob that matches nothing produces an error."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/core/a.py": "A = 1\n"},
    )
    manifest = _manifest_with_rows(
        [_row("megaplan/core/a.py", "file", "arnold-core")],
        coverage_exclusions=[
            {
                "source": "megaplan/**/nonexistent/**/*.py",
                "reason": "Nothing to exclude",
                "evidence": "N/A",
            },
        ],
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "does not match any tracked" in e for e in errors
    ), f"Expected 'does not match any tracked', got: {errors}"


def test_exclusion_allows_uncovered_when_excluded(tmp_path: Path) -> None:
    """An excluded file is not required to have a covering row."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {
            "megaplan/core/a.py": "A = 1\n",
            "megaplan/gen/generated.py": "# auto-generated\n",
        },
    )
    manifest = _manifest_with_rows(
        [_row("megaplan/core/a.py", "file", "arnold-core")],
        coverage_exclusions=[
            {
                "source": "megaplan/gen/generated.py",
                "reason": "Auto-generated file",
                "evidence": "Contains 'auto-generated' header",
            },
        ],
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert errors == [], f"Unexpected errors: {errors}"


# ── path normalization ───────────────────────────────────────────────────


def test_normalize_path_rejects_absolute(tmp_path: Path) -> None:
    """Absolute path in source is rejected."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/core/a.py": "A = 1\n"},
    )
    manifest = _manifest_with_rows(
        [_row("/absolute/path.py", "file", "arnold-core")]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "must be repo-relative" in e for e in errors
    ), f"Expected 'must be repo-relative', got: {errors}"


def test_normalize_path_rejects_parent_traversal(tmp_path: Path) -> None:
    """Parent traversal '..' in source is rejected."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/core/a.py": "A = 1\n"},
    )
    manifest = _manifest_with_rows(
        [_row("megaplan/../escape.py", "file", "arnold-core")]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "must not escape the repo root" in e for e in errors
    ), f"Expected 'must not escape', got: {errors}"


def test_normalize_path_rejects_glob_in_row_source(tmp_path: Path) -> None:
    """Glob syntax in a regular row source is rejected."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/core/a.py": "A = 1\n"},
    )
    manifest = _manifest_with_rows(
        [_row("megaplan/core/*.py", "file", "arnold-core")]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "must not contain glob syntax" in e for e in errors
    ), f"Expected 'must not contain glob syntax', got: {errors}"


def test_normalize_path_strips_whitespace(tmp_path: Path) -> None:
    """Leading/trailing whitespace is stripped from source paths."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/core/a.py": "A = 1\n"},
    )
    manifest = _manifest_with_rows(
        [_row("  megaplan/core/a.py  ", "file", "arnold-core")]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert errors == [], f"Whitespace should be stripped, got: {errors}"


def test_normalize_path_rejects_empty_source(tmp_path: Path) -> None:
    """Empty string source is rejected."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {"megaplan/core/a.py": "A = 1\n"},
    )
    manifest = _manifest_with_rows(
        [_row("", "file", "arnold-core")]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "must not be empty" in e for e in errors
    ), f"Expected 'must not be empty', got: {errors}"


def test_normalize_path_direct_rejects_empty() -> None:
    """_normalize_path directly rejects empty strings."""
    module = _load_module()
    try:
        module._normalize_path("", allow_glob=False)
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "must not be empty" in str(exc)


def test_normalize_path_direct_rejects_whitespace_only() -> None:
    """_normalize_path directly rejects whitespace-only strings."""
    module = _load_module()
    try:
        module._normalize_path("   ", allow_glob=False)
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "must not be empty" in str(exc)


def test_normalize_path_direct_strips_redundant_dots() -> None:
    """_normalize_path strips redundant ./ components."""
    module = _load_module()
    result = module._normalize_path("./megaplan/core/a.py", allow_glob=False)
    assert result == "megaplan/core/a.py", f"Expected normalized path, got {result!r}"


def test_normalize_path_direct_rejects_dots_only() -> None:
    """_normalize_path rejects paths that resolve to '.'."""
    module = _load_module()
    try:
        module._normalize_path("././.", allow_glob=False)
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "must not resolve to '.'" in str(exc)


def test_normalize_path_direct_converts_backslashes() -> None:
    """_normalize_path converts backslashes to forward slashes."""
    module = _load_module()
    result = module._normalize_path("megaplan\\core\\a.py", allow_glob=False)
    assert result == "megaplan/core/a.py", f"Expected forward slashes, got {result!r}"


# ── uncovered file detection ─────────────────────────────────────────────


def test_uncovered_file_without_any_row(tmp_path: Path) -> None:
    """Files with no covering row produce uncovered errors."""
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {
            "megaplan/core/a.py": "A = 1\n",
            "megaplan/core/b.py": "B = 2\n",
        },
    )
    manifest = _manifest_with_rows(
        [_row("megaplan/core/a.py", "file", "arnold-core")]
        # b.py is intentionally uncovered
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)
    assert any(
        "is uncovered" in e for e in errors
    ), f"Expected 'is uncovered', got: {errors}"


# ── real-manifest entry-point smoke test ─────────────────────────────────


def test_real_manifest_loads_and_validates_without_crash() -> None:
    """The real manifest loads and validates without crashing.

    With an empty rows list and populated tracked files the validator
    will produce uncovered-file errors, but it must not crash.
    """
    module = _load_module()
    manifest_path = REPO_ROOT / "docs" / "arnold" / "package-disposition.yaml"
    assert manifest_path.exists(), f"Real manifest not found at {manifest_path}"

    data = module._load_yaml(manifest_path)
    assert isinstance(data, dict), "Real manifest must be a mapping"

    try:
        tracked = module._tracked_python_files(REPO_ROOT)
    except subprocess.CalledProcessError:
        tracked = []

    errors = module.validate_manifest(data, tracked)
    summary = module.render_summary(data, tracked)

    assert "Tracked files:" in summary
    assert "Rows:" in summary

    # With an empty manifest and non-empty tracked files, uncovered errors
    # are expected.  The test only asserts that validate_manifest returns
    # a list of strings (not None, not an exception).
    assert isinstance(errors, list)
