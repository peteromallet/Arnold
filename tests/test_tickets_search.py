"""Tests for ``megaplan ticket search`` — local-mode coverage.

Covers:
- Multi-keyword OR default (any matches)
- ``--all`` switches to AND (all must match)
- ``--status`` and ``--tags`` compose with keywords
- Sort by created, length, title
- ``--all-projects`` discovers via known-repos registry
- ``--project PATH`` scopes to a specific repo
- No-keyword form acts like a sortable listing
- ``--limit`` truncates results
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _init_git_repo(repo_root: Path) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo_root, check=True, capture_output=True, text=True)
    (repo_root / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_root, check=True, capture_output=True, text=True)


def _run(argv: list[str], *, cwd: Path, registry_home: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("MEGAPLAN_BACKEND", None)
    env["MEGAPLAN_REGISTRY_HOME"] = str(registry_home)
    return subprocess.run(
        [sys.executable, "-m", "arnold_pipelines.megaplan", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture
def registry_home(tmp_path: Path) -> Path:
    """Isolated registry home so tests don't read/write the real user file."""
    home = tmp_path / "registry"
    home.mkdir()
    return home


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    _init_git_repo(repo_root)
    return repo_root


def _make(repo: Path, registry: Path, title: str, body: str, tags: str | None = None) -> str:
    args = ["ticket", "new", title, "-b", body]
    if tags:
        args += ["--tags", tags]
    proc = _run(args, cwd=repo, registry_home=registry)
    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    return proc.stdout.strip()


class TestKeywordMatching:
    def test_or_default(self, repo: Path, registry_home: Path) -> None:
        _make(repo, registry_home, "Alpha bug", "first body about widgets")
        _make(repo, registry_home, "Beta crash", "second body about gadgets")
        _make(repo, registry_home, "Unrelated", "nothing here")

        proc = _run(["ticket", "search", "widgets", "crash", "--json"], cwd=repo, registry_home=registry_home)
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        titles = sorted(r["title"] for r in data)
        assert titles == ["Alpha bug", "Beta crash"]

    def test_all_flag_is_and(self, repo: Path, registry_home: Path) -> None:
        _make(repo, registry_home, "Alpha", "widgets and gadgets in one")
        _make(repo, registry_home, "Beta", "only widgets here")
        _make(repo, registry_home, "Gamma", "only gadgets here")

        proc = _run(
            ["ticket", "search", "widgets", "gadgets", "--keywords-all", "--json"],
            cwd=repo, registry_home=registry_home,
        )
        data = json.loads(proc.stdout)
        assert [r["title"] for r in data] == ["Alpha"]

    def test_case_insensitive(self, repo: Path, registry_home: Path) -> None:
        _make(repo, registry_home, "Title", "PaymentFlow crash")
        proc = _run(["ticket", "search", "paymentflow", "--json"], cwd=repo, registry_home=registry_home)
        data = json.loads(proc.stdout)
        assert len(data) == 1

    def test_matches_tags(self, repo: Path, registry_home: Path) -> None:
        _make(repo, registry_home, "Tagged", "body", tags="urgent,backend")
        proc = _run(["ticket", "search", "urgent", "--json"], cwd=repo, registry_home=registry_home)
        data = json.loads(proc.stdout)
        assert len(data) == 1


class TestFilterCompose:
    def test_status_filter(self, repo: Path, registry_home: Path) -> None:
        u1 = _make(repo, registry_home, "Open one", "widget")
        u2 = _make(repo, registry_home, "Done one", "widget")
        _run(["ticket", "dismiss", u2], cwd=repo, registry_home=registry_home)

        proc = _run(
            ["ticket", "search", "widget", "--status", "open", "--json"],
            cwd=repo, registry_home=registry_home,
        )
        data = json.loads(proc.stdout)
        assert [r["id"] for r in data] == [u1]

    def test_tags_filter(self, repo: Path, registry_home: Path) -> None:
        u1 = _make(repo, registry_home, "T1", "widget alpha", tags="frontend")
        _make(repo, registry_home, "T2", "widget beta", tags="backend")
        proc = _run(
            ["ticket", "search", "widget", "--tags", "frontend", "--json"],
            cwd=repo, registry_home=registry_home,
        )
        data = json.loads(proc.stdout)
        assert [r["id"] for r in data] == [u1]


class TestSort:
    def test_sort_by_length(self, repo: Path, registry_home: Path) -> None:
        u1 = _make(repo, registry_home, "Short", "a")
        u2 = _make(repo, registry_home, "Medium", "a" * 50)
        u3 = _make(repo, registry_home, "Long", "a" * 200)

        proc = _run(["ticket", "search", "--sort", "length", "--json"], cwd=repo, registry_home=registry_home)
        data = json.loads(proc.stdout)
        ids = [r["id"] for r in data]
        assert ids == [u3, u2, u1]  # desc by default

        proc_asc = _run(
            ["ticket", "search", "--sort", "length", "--asc", "--json"],
            cwd=repo, registry_home=registry_home,
        )
        assert [r["id"] for r in json.loads(proc_asc.stdout)] == [u1, u2, u3]

    def test_sort_by_title(self, repo: Path, registry_home: Path) -> None:
        u_c = _make(repo, registry_home, "Charlie", "x")
        u_a = _make(repo, registry_home, "Alpha", "x")
        u_b = _make(repo, registry_home, "Bravo", "x")

        proc = _run(
            ["ticket", "search", "--sort", "title", "--asc", "--json"],
            cwd=repo, registry_home=registry_home,
        )
        data = json.loads(proc.stdout)
        assert [r["title"] for r in data] == ["Alpha", "Bravo", "Charlie"]

    def test_limit(self, repo: Path, registry_home: Path) -> None:
        for i in range(5):
            _make(repo, registry_home, f"T{i}", "body")
        proc = _run(
            ["ticket", "search", "--limit", "2", "--json"],
            cwd=repo, registry_home=registry_home,
        )
        data = json.loads(proc.stdout)
        assert len(data) == 2


class TestProjectScope:
    def test_default_scope_is_current_repo(self, tmp_path: Path, registry_home: Path) -> None:
        a = tmp_path / "a"; _init_git_repo(a)
        b = tmp_path / "b"; _init_git_repo(b)
        _make(a, registry_home, "In A", "alpha")
        _make(b, registry_home, "In B", "alpha")

        proc = _run(["ticket", "search", "alpha", "--json"], cwd=a, registry_home=registry_home)
        data = json.loads(proc.stdout)
        assert [r["title"] for r in data] == ["In A"]

    def test_all_projects_via_registry(self, tmp_path: Path, registry_home: Path) -> None:
        a = tmp_path / "a"; _init_git_repo(a)
        b = tmp_path / "b"; _init_git_repo(b)
        _make(a, registry_home, "In A", "shared keyword")
        _make(b, registry_home, "In B", "shared keyword")

        # Both should now be in the registry — search from anywhere with --all-projects.
        proc = _run(
            ["ticket", "search", "shared", "--all-projects", "--json"],
            cwd=a, registry_home=registry_home,
        )
        data = json.loads(proc.stdout)
        titles = sorted(r["title"] for r in data)
        assert titles == ["In A", "In B"]

    def test_specific_project_by_path(self, tmp_path: Path, registry_home: Path) -> None:
        a = tmp_path / "a"; _init_git_repo(a)
        b = tmp_path / "b"; _init_git_repo(b)
        _make(a, registry_home, "In A", "shared keyword")
        _make(b, registry_home, "In B", "shared keyword")

        proc = _run(
            ["ticket", "search", "shared", "--project", str(b), "--json"],
            cwd=a, registry_home=registry_home,
        )
        data = json.loads(proc.stdout)
        assert [r["title"] for r in data] == ["In B"]


class TestEmptyAndNoKeyword:
    def test_no_keywords_lists_everything(self, repo: Path, registry_home: Path) -> None:
        _make(repo, registry_home, "T1", "x")
        _make(repo, registry_home, "T2", "y")
        proc = _run(["ticket", "search", "--json"], cwd=repo, registry_home=registry_home)
        data = json.loads(proc.stdout)
        assert {r["title"] for r in data} == {"T1", "T2"}

    def test_no_matches_returns_empty(self, repo: Path, registry_home: Path) -> None:
        _make(repo, registry_home, "T1", "body")
        proc = _run(
            ["ticket", "search", "nonexistentkeyword", "--json"],
            cwd=repo, registry_home=registry_home,
        )
        data = json.loads(proc.stdout)
        assert data == []

    def test_snippet_present_when_keywords(self, repo: Path, registry_home: Path) -> None:
        _make(repo, registry_home, "Has match", "the special token is here in the body")
        proc = _run(
            ["ticket", "search", "special", "--json"],
            cwd=repo, registry_home=registry_home,
        )
        data = json.loads(proc.stdout)
        assert len(data) == 1
        assert "special" in (data[0].get("snippet") or "").lower()
