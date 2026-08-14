"""Node-aware pytest-selector existence tests.

A selector ``file.py::node`` exists only when the file exists AND the node is
defined in the source AST — the file alone is not enough.  This is what lets
planned-created test nodes land in ``missing_test_selectors`` instead of being
silently treated as existing.
"""

from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.orchestration.test_selection import (
    _existing_pytest_selector_path,
    pytest_node_defined_in_source,
    sanitize_blast_radius_paths,
    split_pytest_selector,
)


def _write(repo: Path, rel_path: str, content: str = "") -> None:
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or f"# {rel_path}\n", encoding="utf-8")


def _exists(repo: Path, selector: str) -> bool:
    return _existing_pytest_selector_path(repo, selector)


# ---------------------------------------------------------------------------
# split_pytest_selector / pytest_node_defined_in_source
# ---------------------------------------------------------------------------


def test_split_pytest_selector_strips_parametrize_suffix() -> None:
    assert split_pytest_selector("tests/test_a.py") == ("tests/test_a.py", ())
    assert split_pytest_selector("tests/test_a.py::test_foo") == (
        "tests/test_a.py",
        ("test_foo",),
    )
    assert split_pytest_selector("tests/test_a.py::TestCls::test_bar[param]") == (
        "tests/test_a.py",
        ("TestCls", "test_bar"),
    )


def test_pytest_node_defined_in_source_ast_rules() -> None:
    source = (
        "def test_module():\n"
        "    pass\n"
        "\n"
        "class TestCls:\n"
        "    def test_method(self):\n"
        "        pass\n"
    )
    assert pytest_node_defined_in_source(source, ("test_module",)) is True
    assert pytest_node_defined_in_source(source, ("TestCls",)) is True
    assert pytest_node_defined_in_source(source, ("TestCls", "test_method")) is True
    assert pytest_node_defined_in_source(source, ("test_module", "nested")) is False
    assert pytest_node_defined_in_source(source, ("TestCls", "test_absent")) is False
    assert pytest_node_defined_in_source(source, ("absent_module",)) is False
    assert pytest_node_defined_in_source(source, ()) is False
    assert pytest_node_defined_in_source("def broken(:\n", ("test_foo",)) is False


# ---------------------------------------------------------------------------
# Node-aware existence table
# ---------------------------------------------------------------------------


def test_existing_file_without_node_is_existing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "tests/test_a.py", "def test_foo():\n    pass\n")
    assert _exists(repo, "tests/test_a.py")


def test_existing_file_with_existing_function_node_is_existing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "tests/test_a.py", "def test_foo():\n    pass\n")
    assert _exists(repo, "tests/test_a.py::test_foo")


def test_existing_file_with_absent_node_is_missing_and_sanitized(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write(repo, "tests/test_a.py", "def test_foo():\n    pass\n")

    sanitized = sanitize_blast_radius_paths(
        {
            "selectors": [{"kind": "path", "value": "tests/test_a.py::test_new"}],
            "always_run": [],
            "rationale": "",
        },
        repo,
    )

    assert sanitized["selectors"] == []
    assert sanitized["missing_test_selectors"] == ["tests/test_a.py::test_new"]
    assert "Dropped nonexistent pytest path(s)" in sanitized["rationale"]


def test_existing_file_with_absent_class_method_node_is_missing(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write(
        repo,
        "tests/test_a.py",
        "class TestCls:\n    def test_foo(self):\n        pass\n",
    )
    assert not _exists(repo, "tests/test_a.py::TestCls::test_new")


def test_existing_file_with_parametrized_defined_function_is_existing(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write(repo, "tests/test_a.py", "def test_foo():\n    pass\n")
    assert _exists(repo, "tests/test_a.py::test_foo[param-0]")


def test_missing_file_with_node_is_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    assert not _exists(repo, "tests/test_missing.py::anything")


def test_directory_selector_without_node_is_existing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    assert _exists(repo, "tests")


def test_directory_selector_with_node_is_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    assert not _exists(repo, "tests::test_foo")


def test_syntax_error_file_with_node_is_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "tests/test_broken.py", "def broken(:\n")
    assert not _exists(repo, "tests/test_broken.py::test_foo")


def test_archived_or_hidden_path_is_not_existing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "archive/test_old.py", "def test_foo():\n    pass\n")
    _write(repo, "tests/.hidden_test.py", "def test_foo():\n    pass\n")
    assert not _exists(repo, "archive/test_old.py::test_foo")
    assert not _exists(repo, "tests/.hidden_test.py::test_foo")


# ---------------------------------------------------------------------------
# Sanitize re-validates prior missing entries
# ---------------------------------------------------------------------------


def test_sanitize_revalidates_existing_missing_entries(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo, "tests/test_a.py", "def test_foo():\n    pass\n")
    _write(repo, "tests/test_b.py", "def test_bar():\n    pass\n")

    sanitized = sanitize_blast_radius_paths(
        {
            "selectors": [{"kind": "path", "value": "tests/test_a.py"}],
            "always_run": [],
            "rationale": "",
            "missing_test_selectors": [
                "tests/test_a.py::test_foo",  # now defined -> dropped
                "tests/test_b.py::test_absent",  # still absent -> kept
                "tests/test_c.py",  # file absent -> kept
            ],
        },
        repo,
    )

    assert sanitized["missing_test_selectors"] == [
        "tests/test_b.py::test_absent",
        "tests/test_c.py",
    ]


def test_sanitize_drops_stale_missing_field_when_everything_now_exists(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _write(repo, "tests/test_a.py", "def test_foo():\n    pass\n")

    sanitized = sanitize_blast_radius_paths(
        {
            "selectors": [{"kind": "path", "value": "tests/test_a.py"}],
            "always_run": [],
            "rationale": "",
            "missing_test_selectors": ["tests/test_a.py::test_foo"],
        },
        repo,
    )

    assert "missing_test_selectors" not in sanitized
