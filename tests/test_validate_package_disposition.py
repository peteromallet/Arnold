from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_package_disposition.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_package_disposition", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _init_repo(tmp_path: Path, files: dict[str, str]) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    for relative_path, content in files.items():
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
    manifest_path = repo_root / "docs" / "arnold" / "package-disposition.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    return repo_root, manifest_path


def _manifest_with_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
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
        "deferral_ledger": [],
    }


def _row(
    source: str,
    granularity: str,
    disposition: str,
    *,
    target: str = "arnold/example.py",
) -> dict[str, object]:
    return {
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


def test_validate_manifest_accepts_file_directory_and_split_rows(tmp_path: Path) -> None:
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {
            "arnold_pipelines/megaplan/core/a.py": "A = 1\n",
            "arnold_pipelines/megaplan/pkg/b.py": "B = 2\n",
            "arnold_pipelines/megaplan/cli/arnold.py": "def main():\n    return 0\n",
        },
    )
    manifest = _manifest_with_rows(
        [
            _row("megaplan/core/a.py", "file", "arnold-core"),
            _row("megaplan/pkg", "directory", "megaplan-plugin", target="megaplan/pkg"),
            _row("megaplan/cli/arnold.py", "split", "split-required", target="megaplan/cli/arnold.py"),
            _row("megaplan/cli/arnold.py", "symbol", "megaplan-plugin", target="megaplan/cli/arnold.py"),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)

    assert errors == []


def test_tracked_python_files_include_top_level_megaplan_modules(tmp_path: Path) -> None:
    module = _load_module()
    repo_root, _manifest_path = _init_repo(
        tmp_path,
        {
            "arnold_pipelines/megaplan/auto.py": "AUTO = 1\n",
            "arnold_pipelines/megaplan/control_interface.py": "CONTROL = 2\n",
            "arnold_pipelines/megaplan/subpkg/worker.py": "WORKER = 3\n",
        },
    )

    tracked = module._tracked_python_files(repo_root)

    assert "arnold_pipelines/megaplan/auto.py" in tracked
    assert "arnold_pipelines/megaplan/control_interface.py" in tracked
    assert "arnold_pipelines/megaplan/subpkg/worker.py" in tracked


def test_validate_manifest_rejects_duplicate_coverage_and_missing_split_children(
    tmp_path: Path,
) -> None:
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {
            "arnold_pipelines/megaplan/hybrid/one.py": "ONE = 1\n",
            "arnold_pipelines/megaplan/hybrid/two.py": "TWO = 2\n",
            "arnold_pipelines/megaplan/cli/solo.py": "SOLO = 3\n",
        },
    )
    manifest = _manifest_with_rows(
        [
            _row("megaplan/hybrid", "directory", "megaplan-plugin", target="megaplan/hybrid"),
            _row("megaplan/hybrid/one.py", "file", "megaplan-plugin", target="megaplan/hybrid/one.py"),
            _row("megaplan/cli/solo.py", "split", "split-required", target="megaplan/cli/solo.py"),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    tracked = module._tracked_python_files(repo_root)
    errors = module.validate_manifest(manifest, tracked)

    assert any("needs symbol child rows" in error for error in errors)
    assert any("duplicate coverage" in error for error in errors)


def test_cli_summary_reports_disposition_and_package_counts(tmp_path: Path) -> None:
    module = _load_module()
    repo_root, manifest_path = _init_repo(
        tmp_path,
        {
            "arnold_pipelines/megaplan/core/a.py": "A = 1\n",
            "arnold_pipelines/megaplan/pkg/b.py": "B = 2\n",
        },
    )
    manifest = _manifest_with_rows(
        [
            _row("megaplan/core/a.py", "file", "arnold-core", target="arnold/core.py"),
            _row("megaplan/pkg", "directory", "megaplan-plugin", target="megaplan/pkg"),
        ]
    )
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(repo_root),
            "--manifest",
            str(manifest_path),
            "--summary",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Tracked files: 2" in result.stdout
    assert "Disposition counts:" in result.stdout
    assert "arnold-core: 1" in result.stdout
    assert "megaplan-plugin: 1" in result.stdout
    assert "Target package counts:" in result.stdout
