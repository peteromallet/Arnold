from __future__ import annotations

import subprocess
from pathlib import Path

import megaplan.audits.quality_gates as quality


def _write_lines(path: Path, count: int, *, prefix: str = "line") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{prefix}_{index}" for index in range(count)) + "\n", encoding="utf-8")


def test_file_growth_flags_large_growth(tmp_path: Path) -> None:
    target = tmp_path / "big.py"
    _write_lines(target, 260)

    advisories = quality._check_file_growth(
        tmp_path,
        ["big.py"],
        {"big.py": 10},
        {"threshold_lines": 200},
    )

    assert advisories == ["Advisory quality: big.py grew by 250 lines (threshold 200)."]


def test_file_growth_under_threshold_no_flag(tmp_path: Path) -> None:
    target = tmp_path / "small.py"
    _write_lines(target, 60)

    advisories = quality._check_file_growth(
        tmp_path,
        ["small.py"],
        {"small.py": 10},
        {"threshold_lines": 200},
    )

    assert advisories == []


def test_file_growth_new_file(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    target = tmp_path / "new.py"
    _write_lines(target, 250)

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=128,
            stdout=b"",
            stderr=b"fatal: path 'new.py' exists on disk, but not in 'HEAD'",
        )

    monkeypatch.setattr(quality.subprocess, "run", fake_run)

    advisories = quality._check_file_growth(
        tmp_path,
        ["new.py"],
        {},
        {"threshold_lines": 200},
    )

    assert advisories == ["Advisory quality: new.py grew by 250 lines (threshold 200)."]


def test_file_growth_clean_file_uses_git_show(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".git").mkdir()
    target = tmp_path / "clean.py"
    _write_lines(target, 350)

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=("\n".join(f"base_{index}" for index in range(100)) + "\n").encode("utf-8"),
            stderr=b"",
        )

    monkeypatch.setattr(quality.subprocess, "run", fake_run)

    advisories = quality._check_file_growth(
        tmp_path,
        ["clean.py"],
        {},
        {"threshold_lines": 200},
    )

    assert advisories == ["Advisory quality: clean.py grew by 250 lines (threshold 200)."]


def test_file_growth_uses_threshold_config_key(tmp_path: Path) -> None:
    target = tmp_path / "threshold.py"
    _write_lines(target, 150)

    advisories = quality._check_file_growth(
        tmp_path,
        ["threshold.py"],
        {"threshold.py": 10},
        {"threshold": 100},
    )

    assert advisories == ["Advisory quality: threshold.py grew by 140 lines (threshold 100)."]


def test_duplicate_functions_detected(tmp_path: Path) -> None:
    target = tmp_path / "dupes.py"
    target.write_text(
        "def alpha(value):\n"
        "    total = value + 1\n"
        "    adjusted = total * 2\n"
        "    return adjusted\n\n"
        "def beta(value):\n"
        "    total = value + 1\n"
        "    adjusted = total * 2\n"
        "    return adjusted\n",
        encoding="utf-8",
    )

    advisories = quality._check_duplicate_functions(
        tmp_path,
        ["dupes.py"],
        {},
        {"similarity_threshold": 0.8, "max_file_lines": 1000},
    )

    assert advisories == [
        "Advisory quality: dupes.py has similar functions alpha and beta (100% similarity)."
    ]


def test_duplicate_functions_no_flag_when_bodies_differ(tmp_path: Path) -> None:
    target = tmp_path / "distinct.py"
    target.write_text(
        "def alpha(value):\n"
        "    total = value + 1\n"
        "    return total * 2\n\n"
        "def beta(value):\n"
        "    items = [value, value + 1]\n"
        "    return sum(items)\n",
        encoding="utf-8",
    )

    advisories = quality._check_duplicate_functions(
        tmp_path,
        ["distinct.py"],
        {},
        {"similarity_threshold": 0.8, "max_file_lines": 1000},
    )

    assert advisories == []


def test_dead_imports_detected(tmp_path: Path) -> None:
    target = tmp_path / "imports.py"
    target.write_text(
        "import os\n"
        "import sys\n\n"
        "print(os.getcwd())\n",
        encoding="utf-8",
    )

    advisories = quality._check_dead_imports(tmp_path, ["imports.py"], {}, {})

    assert advisories == ["Advisory quality: imports.py adds unused imports: sys."]


def test_dead_imports_no_flag_when_imports_are_used(tmp_path: Path) -> None:
    target = tmp_path / "used_imports.py"
    target.write_text(
        "import os\n"
        "import sys\n\n"
        "print(os.getcwd(), sys.version)\n",
        encoding="utf-8",
    )

    advisories = quality._check_dead_imports(tmp_path, ["used_imports.py"], {}, {})

    assert advisories == []


def test_dead_imports_init_skipped(tmp_path: Path) -> None:
    target = tmp_path / "pkg" / "__init__.py"
    target.parent.mkdir()
    target.write_text("import os\n", encoding="utf-8")

    advisories = quality._check_dead_imports(tmp_path, ["pkg/__init__.py"], {}, {})

    assert advisories == []


def test_dead_imports_future_annotations_skipped(tmp_path: Path) -> None:
    target = tmp_path / "mod.py"
    target.write_text("from __future__ import annotations\n\ndef f() -> int:\n    return 1\n", encoding="utf-8")

    advisories = quality._check_dead_imports(tmp_path, ["mod.py"], {}, {})

    assert advisories == []


def test_test_coverage_flags_missing_tests(tmp_path: Path) -> None:
    target = tmp_path / "megaplan" / "feature.py"
    target.parent.mkdir()
    target.write_text("def feature():\n    return True\n", encoding="utf-8")

    advisories = quality._check_test_coverage(tmp_path, ["megaplan/feature.py"], {}, {})

    assert advisories == [
        "Advisory quality: code changes lacked test updates: megaplan/feature.py."
    ]


def test_test_coverage_no_flag_when_tests_present(tmp_path: Path) -> None:
    source = tmp_path / "megaplan" / "feature.py"
    source.parent.mkdir()
    source.write_text("def feature():\n    return True\n", encoding="utf-8")
    test_file = tmp_path / "tests" / "test_feature.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_feature():\n    assert True\n", encoding="utf-8")

    advisories = quality._check_test_coverage(
        tmp_path,
        ["megaplan/feature.py", "tests/test_feature.py"],
        {},
        {},
    )

    assert advisories == []


def test_config_disables_check(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    _write_lines(target, 300)

    advisories = quality.run_quality_checks(
        tmp_path,
        changed_paths=["notes.txt"],
        before_line_counts={"notes.txt": 0},
        config={"file_growth": {"enabled": False}},
    )

    assert advisories == []


def test_run_quality_checks_returns_advisory_strings(tmp_path: Path) -> None:
    target = tmp_path / "module.py"
    target.write_text(
        "import os\n"
        + "\n".join(f"line_{index} = {index}" for index in range(220))
        + "\nprint('ready')\n",
        encoding="utf-8",
    )

    advisories = quality.run_quality_checks(
        tmp_path,
        changed_paths=["module.py"],
        before_line_counts={"module.py": 1},
        config={},
    )

    assert advisories
    assert all(item.startswith("Advisory quality:") for item in advisories)
    assert any("module.py grew by" in item for item in advisories)
    assert any("unused imports: os" in item for item in advisories)
    assert any("code changes lacked test updates" in item for item in advisories)
