from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.review import mechanical
from arnold.pipelines.megaplan.review.mechanical import run_pre_checks


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)


def _git_commit_all(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, capture_output=True, text=True)


def _state(project_dir: Path) -> dict[str, object]:
    return {
        "idea": "Fix the parser edge case without changing unrelated behavior.",
        "meta": {"notes": []},
        "config": {"project_dir": str(project_dir)},
    }


def test_run_pre_checks_flags_test_only_diff_and_small_patch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init(repo)
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    _git_commit_all(repo, "initial")

    test_file = repo / "tests" / "test_only.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("assert True\n", encoding="utf-8")

    flags = run_pre_checks(tmp_path / "plan", _state(repo), repo)
    checks = {flag["check"]: flag for flag in flags}

    assert checks["source_touch"]["severity"] == "significant"
    assert "only touches test-like files" in checks["source_touch"]["detail"]
    assert checks["diff_size_sanity"]["check"] == "diff_size_sanity"
    assert "changed_lines=" in checks["diff_size_sanity"]["detail"]


def test_diff_noise_filter_excludes_megaplan_and_caches(tmp_path: Path) -> None:
    """Ensure mechanical pre-checks ignore .megaplan/ metadata, pycache, and other workspace noise.

    This locks down the fix for the `.megaplan/` diff_size_sanity bug found
    during iteration-022-robust validation — the old implementation reported
    workspace metadata as source changes (e.g., 2912 changed lines for a
    2-line source fix). The real source file must still be accounted for.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init(repo)
    (repo / "src.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    _git_commit_all(repo, "initial")

    # Real source change: 1 line.
    (repo / "src.py").write_text("def f():\n    return 2\n", encoding="utf-8")

    # A pile of workspace noise that should be ignored.
    (repo / ".megaplan").mkdir()
    (repo / ".megaplan" / "plan.md").write_text("x\n" * 500, encoding="utf-8")
    (repo / ".megaplan" / "critique.json").write_text("{}\n" * 200, encoding="utf-8")
    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "src.cpython-311.pyc").write_bytes(b"\x00" * 128)
    (repo / ".pytest_cache").mkdir()
    (repo / ".pytest_cache" / "v").write_text("noise\n" * 100, encoding="utf-8")

    flags = run_pre_checks(tmp_path / "plan", _state(repo), repo)
    sanity = next(flag for flag in flags if flag["check"] == "diff_size_sanity")

    # With the filter working, changed_lines should reflect only src.py's
    # 1-line change, not the hundreds of lines of .megaplan/ metadata.
    assert "changed_lines=1" in sanity["detail"] or "changed_lines=2" in sanity["detail"], (
        f"Expected tiny changed-line count but got: {sanity['detail']}"
    )
    assert "files=1" in sanity["detail"], (
        f"Expected exactly 1 source file in diff but got: {sanity['detail']}"
    )
    # Explicitly assert the noise wasn't counted.
    assert "2912" not in sanity["detail"]
    assert ".megaplan" not in sanity.get("evidence_file", "")


def test_diff_size_sanity_scales_for_finalized_multi_task_integration_plan(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init(repo)
    (repo / "src.py").write_text("BASELINE = True\n", encoding="utf-8")
    _git_commit_all(repo, "initial")

    (repo / "src.py").write_text(
        "BASELINE = True\n" + "\n".join(f"VALUE_{index} = {index}" for index in range(400)) + "\n",
        encoding="utf-8",
    )
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [{"id": f"T{index}"} for index in range(1, 14)], "sense_checks": []}) + "\n",
        encoding="utf-8",
    )

    flags = run_pre_checks(plan_dir, _state(repo), repo)
    sanity_flags = [flag for flag in flags if flag["check"] == "diff_size_sanity"]

    assert not any(flag["severity"] == "significant" and "expected≈10" in flag["detail"] for flag in sanity_flags)


def test_run_pre_checks_dead_guard_static_gracefully_reports_parse_failures(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init(repo)
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    _git_commit_all(repo, "initial")

    (repo / "broken.py").write_text("if True:\n    broken(\n", encoding="utf-8")

    flags = run_pre_checks(tmp_path / "plan", _state(repo), repo)

    assert any(
        flag["check"] == "dead_guard_static"
        and flag["id"].endswith("PARSE")
        and "could not be parsed as Python" in flag["detail"]
        for flag in flags
    )


def test_dead_guard_static_skips_oversized_callsite_files(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    small_caller = repo / "caller.py"
    large_caller = repo / "large_generated.py"
    small_caller.write_text("target(True)\n", encoding="utf-8")
    large_caller.write_text("target(True)\n" + ("# generated\n" * 30_000), encoding="utf-8")

    func_source = "def target(flag=True):\n    if flag:\n        return 1\n"
    func = mechanical.ast.parse(func_source, filename="changed.py").body[0]

    parsed_filenames: list[str] = []
    real_parse = mechanical.ast.parse

    def spy_parse(source: str, filename: str = "<unknown>", *args, **kwargs):
        parsed_filenames.append(filename)
        return real_parse(source, filename=filename, *args, **kwargs)

    monkeypatch.setattr(mechanical.ast, "parse", spy_parse)

    assert mechanical._candidate_call_truthiness(repo, "target", "flag", func) == [True]
    assert str(small_caller) in parsed_filenames
    assert str(large_caller) not in parsed_filenames


def test_dead_guard_static_does_not_parse_files_without_target_name(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target_caller = repo / "caller.py"
    unrelated = repo / "unrelated.py"
    target_caller.write_text("target(True)\n", encoding="utf-8")
    unrelated.write_text("other(True)\n", encoding="utf-8")

    func_source = "def target(flag=True):\n    if flag:\n        return 1\n"
    func = mechanical.ast.parse(func_source, filename="changed.py").body[0]

    parsed_filenames: list[str] = []
    real_parse = mechanical.ast.parse

    def spy_parse(source: str, filename: str = "<unknown>", *args, **kwargs):
        parsed_filenames.append(filename)
        return real_parse(source, filename=filename, *args, **kwargs)

    monkeypatch.setattr(mechanical.ast, "parse", spy_parse)

    assert mechanical._candidate_call_truthiness(repo, "target", "flag", func) == [True]
    assert str(target_caller) in parsed_filenames
    assert str(unrelated) not in parsed_filenames


def test_dead_guard_static_skips_migration_sized_diffs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    metadata = mechanical._DiffMetadata(
        patch="",
        files=[f"pkg/module_{index}.py" for index in range(101)],
        hunks=101,
        changed_lines=101,
        added_lines={f"pkg/module_{index}.py": {1} for index in range(101)},
    )

    flags = mechanical._dead_guard_static_flags(repo, metadata)

    assert len(flags) == 1
    assert flags[0]["id"] == "PRECHECK-DEAD_GUARD_STATIC-SKIPPED_LARGE_DIFF"
    assert flags[0]["severity"] == "minor"
    assert "too large for bounded advisory AST scanning" in flags[0]["detail"]


def test_dead_guard_static_skips_added_line_heavy_diffs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    metadata = mechanical._DiffMetadata(
        patch="",
        files=["pkg/module.py"],
        hunks=1,
        changed_lines=5_001,
        added_lines={"pkg/module.py": set(range(1, 5_002))},
    )

    flags = mechanical._dead_guard_static_flags(repo, metadata)

    assert len(flags) == 1
    assert flags[0]["id"] == "PRECHECK-DEAD_GUARD_STATIC-SKIPPED_LARGE_DIFF"
    assert "added_python_lines=5001" in flags[0]["detail"]


@pytest.mark.parametrize(
    "module_name",
    [
        "arnold.pipelines.megaplan.review.mechanical",
        "arnold_pipelines.megaplan.review.mechanical",
    ],
)
def test_static_scan_prunes_excluded_directories_for_both_import_paths(
    tmp_path: Path,
    module_name: str,
) -> None:
    module = importlib.import_module(module_name)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "ok.py").write_text("target(True)\n", encoding="utf-8")
    (repo / ".megaplan").mkdir()
    (repo / ".megaplan" / "skip.py").write_text("target(True)\n", encoding="utf-8")

    scanned = {path.relative_to(repo).as_posix() for path in module._iter_python_files(repo)}

    assert scanned == {"src/ok.py"}
