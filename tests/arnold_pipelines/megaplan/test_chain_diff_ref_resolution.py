"""Tests for _diff_name_only_between_refs() fetch-and-retry hardening."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import pytest

from arnold_pipelines.megaplan.chain import (
    _diff_name_only_between_refs,
    _is_git_ref_resolution_error,
)


# ---------------------------------------------------------------------------
# _is_git_ref_resolution_error — pattern classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "error_text",
    [
        # Explicitly listed patterns
        "fatal: bad object abc123",
        "fatal: unknown revision or path not in the working tree",
        "fatal: bad revision 'HEAD^^^'",
        "fatal: could not resolve ref",
        "fatal: does not point to a valid object",
        "fatal: not a valid object name HEAD~999",
        "fatal: not our ref abc123",
        "error: could not read from remote repository",
        "fatal: ambiguous argument 'main..feature': unknown revision or path",
        "fatal: not a commit",
        "fatal: not a tree",
        # Mixed-case variations
        "FATAL: BAD OBJECT deadbeef",
        "Error: Could not resolve 'refs/heads/gone'",
        "Bad Revision: abc",
        # Realistic git error messages
        "fatal: bad object refs/remotes/origin/main",
        "fatal: Not a valid object name origin/feature",
        "error: Could not resolve host: github.com",
        "fatal: ambiguous argument 'origin/renamed': unknown revision",
    ],
)
def test_is_ref_resolution_error_matches(error_text: str) -> None:
    assert _is_git_ref_resolution_error(error_text.lower()), (
        f"Should classify as ref-resolution error: {error_text!r}"
    )


@pytest.mark.parametrize(
    "error_text",
    [
        # Unrelated git errors that should NOT trigger fetch-and-retry
        "fatal: not a git repository",
        "fatal: refusing to merge unrelated histories",
        "error: merge conflict in file.py",
        "fatal: Unable to create file: Permission denied",
        "error: Your local changes to the following files would be overwritten",
        "fatal: remote origin already exists",
        "error: src refspec main does not match any",
        "fatal: couldn't find remote ref main",
        "fatal: empty ident name not allowed",
        "Permission denied (publickey)",
        "fatal: bad config",
        "fatal: 'foo' is not a valid branch name",
        "",
        "some random non-git output",
    ],
)
def test_is_ref_resolution_error_no_match(error_text: str) -> None:
    assert not _is_git_ref_resolution_error(error_text.lower()), (
        f"Should NOT classify as ref-resolution error: {error_text!r}"
    )


def test_is_ref_resolution_error_empty_string() -> None:
    assert not _is_git_ref_resolution_error("")


# ---------------------------------------------------------------------------
# _diff_name_only_between_refs — fetch-and-retry integration
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if check:
        assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc


def _run_git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run git in an arbitrary working directory."""
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if check:
        assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc


def _init_bare_repo(path: Path) -> Path:
    """Create a bare repo to act as 'origin'."""
    path.mkdir()
    _git(path, "init", "--bare")
    return path


def _init_clone(origin: Path, clone: Path) -> str:
    """Clone *origin* into *clone* and return the initial HEAD SHA."""
    clone.parent.mkdir(parents=True, exist_ok=True)
    _run_git(clone.parent, "clone", str(origin), str(clone))
    _git(clone, "config", "user.email", "test@example.com")
    _git(clone, "config", "user.name", "Test User")
    (clone / "README.md").write_text("initial\n", encoding="utf-8")
    _git(clone, "add", "README.md")
    _git(clone, "commit", "-m", "initial")
    _git(clone, "push", "origin", "HEAD:refs/heads/main")
    result = _git(clone, "rev-parse", "HEAD")
    return result.stdout.strip()


def test_diff_name_only_success_no_fetch(tmp_path: Path) -> None:
    """Happy path: both refs exist locally, no fetch needed."""
    origin = tmp_path / "origin.git"
    _init_bare_repo(origin)
    clone = tmp_path / "clone"
    sha = _init_clone(origin, clone)

    # Write a second commit so we have a diff
    (clone / "file.txt").write_text("hello\n", encoding="utf-8")
    _git(clone, "add", "file.txt")
    _git(clone, "commit", "-m", "add file")
    _git(clone, "push", "origin", "HEAD:refs/heads/main")

    proc = _diff_name_only_between_refs(clone, sha, "HEAD")
    assert proc.returncode == 0
    assert "file.txt" in proc.stdout


def test_diff_name_only_bad_object_triggers_fetch_and_retry(tmp_path: Path) -> None:
    """Missing local object triggers fetch --prune and retry succeeds."""
    origin = tmp_path / "origin.git"
    _init_bare_repo(origin)
    clone = tmp_path / "clone"
    sha = _init_clone(origin, clone)

    # Create a second commit and push it
    (clone / "file.txt").write_text("hello\n", encoding="utf-8")
    _git(clone, "add", "file.txt")
    _git(clone, "commit", "-m", "add file")
    _git(clone, "push", "origin", "HEAD:refs/heads/main")
    new_sha = _git(clone, "rev-parse", "HEAD").stdout.strip()

    # Remove the object from the local object store so git diff fails with
    # "bad object"
    object_dir = clone / ".git" / "objects" / new_sha[:2]
    object_file = object_dir / new_sha[2:]
    object_file.unlink()

    # Should still succeed because fetch --prune restores the object
    proc = _diff_name_only_between_refs(clone, sha, new_sha)
    assert proc.returncode == 0


def test_diff_name_only_unknown_revision_triggers_fetch_and_retry(
    tmp_path: Path,
) -> None:
    """Reference to a revision not in the local repo triggers fetch."""
    origin = tmp_path / "origin.git"
    _init_bare_repo(origin)
    clone = tmp_path / "clone"
    sha = _init_clone(origin, clone)

    # Create second commit on a separate clone to simulate remote-only ref
    clone2 = tmp_path / "clone2"
    _run_git(clone2.parent, "clone", str(origin), str(clone2))
    _git(clone2, "config", "user.email", "other@example.com")
    _git(clone2, "config", "user.name", "Other")
    (clone2 / "remote_only.txt").write_text("remote\n", encoding="utf-8")
    _git(clone2, "add", "remote_only.txt")
    _git(clone2, "commit", "-m", "remote commit")
    _git(clone2, "push", "origin", "HEAD:refs/heads/main")
    remote_sha = _git(clone2, "rev-parse", "HEAD").stdout.strip()

    # The first clone doesn't have this commit, so git diff should fail
    # with "unknown revision" or "bad object", then fetch should fix it
    proc = _diff_name_only_between_refs(clone, sha, remote_sha)
    assert proc.returncode == 0


def test_diff_name_only_non_ref_error_surfaces_immediately(tmp_path: Path) -> None:
    """Non-ref errors (e.g. merge conflict) should NOT trigger fetch."""
    origin = tmp_path / "origin.git"
    _init_bare_repo(origin)
    clone = tmp_path / "clone"
    sha = _init_clone(origin, clone)

    # Pass a totally bogus ref that is NOT a ref-resolution error
    # (e.g. --cached which changes diff mode)
    with mock.patch("subprocess.run") as mock_run:
        # First call: fail with non-ref error
        fail_proc = subprocess.CompletedProcess(
            args=["git", "diff"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository\n",
        )
        # We only mock the first subprocess.run call
        mock_run.side_effect = lambda *a, **kw: fail_proc
        proc = _diff_name_only_between_refs(clone, sha, "HEAD")
        assert proc.returncode == 128
        # Only one call — no fetch, no retry
        assert mock_run.call_count == 1


def test_diff_name_only_retry_still_fails_surfaces_real_error(
    tmp_path: Path,
) -> None:
    """When fetch succeeds but retry still fails, the real error is surfaced."""
    origin = tmp_path / "origin.git"
    _init_bare_repo(origin)
    clone = tmp_path / "clone"
    sha = _init_clone(origin, clone)

    # Reference a SHA that truly doesn't exist anywhere
    bogus_sha = "deadbeef" * 5  # 40 hex chars, not a real object

    proc = _diff_name_only_between_refs(clone, sha, bogus_sha)
    # Should fail because even after fetch, the object doesn't exist
    assert proc.returncode != 0
    combined = f"{proc.stderr or ''}\n{proc.stdout or ''}".lower()
    assert "bad object" in combined or "unknown revision" in combined or "bad revision" in combined


def test_diff_name_only_first_attempt_succeeds_on_second_clone(
    tmp_path: Path,
) -> None:
    """After fetch--prune, a previously missing ref should become available."""
    origin = tmp_path / "origin.git"
    _init_bare_repo(origin)
    a = tmp_path / "a"
    sha_a = _init_clone(origin, a)

    # Create a second commit from a different clone
    b = tmp_path / "b"
    _run_git(b.parent, "clone", str(origin), str(b))
    _git(b, "config", "user.email", "b@example.com")
    _git(b, "config", "user.name", "B")
    (b / "b.txt").write_text("b\n", encoding="utf-8")
    _git(b, "add", "b.txt")
    _git(b, "commit", "-m", "b commit")
    _git(b, "push", "origin", "HEAD:refs/heads/main")
    sha_b = _git(b, "rev-parse", "HEAD").stdout.strip()

    # Clone 'a' doesn't have sha_b yet, so diff should fail then succeed
    proc = _diff_name_only_between_refs(a, sha_a, sha_b)
    assert proc.returncode == 0
    assert "b.txt" in proc.stdout
