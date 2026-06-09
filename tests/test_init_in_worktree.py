"""Tests for `megaplan init --in-worktree <name>`."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import megaplan


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=check
    )


def _init_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    return head


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def _run_init(
    argv: list[str],
    *,
    cwd: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[int, dict | None]:
    monkeypatch.chdir(cwd)
    code = megaplan.main(argv)
    out = capsys.readouterr().out.strip()
    payload: dict | None
    try:
        payload = json.loads(out) if out else None
    except json.JSONDecodeError:
        payload = None
    return code, payload


def test_in_worktree_happy_path(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    head = _init_repo(repo)

    code, payload = _run_init(
        ["init", "--in-worktree", "feature-x", "my idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code == 0, payload
    assert payload and payload.get("success") is True

    expected_wt = fake_home / "Documents" / ".megaplan-worktrees" / "feature-x"
    assert expected_wt.is_dir()
    # Plan dir lives inside the worktree.
    plan_name = payload["plan"]
    plan_dir = expected_wt / ".megaplan" / "plans" / plan_name
    assert plan_dir.is_dir()
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    wt = state["meta"]["worktree"]
    assert wt["name"] == "feature-x"
    assert wt["branch"] == "feature-x"
    assert wt["base_sha"] == head
    assert wt["path"] == str(expected_wt)
    # New branch exists in the original repo.
    branches = _git(repo, "branch", "--list").stdout
    assert "feature-x" in branches
    # Main worktree untouched (still on main, clean).
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"
    assert _git(repo, "status", "--porcelain").stdout.strip() == ""


@pytest.mark.parametrize(
    "name",
    ["BadCase", "with/slash", "a" * 65, ".dotstart", "_leadingunderscore"],
)
def test_in_worktree_invalid_name_rejected(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    """Names that parse as one argv token but fail our regex must surface
    a structured invalid_worktree_name CliError (not argparse exit-2)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    code, payload = _run_init(
        ["init", "--in-worktree", name, "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code != 0
    assert payload and payload.get("error") == "invalid_worktree_name"
    # No worktree created.
    assert not (fake_home / "Documents" / ".megaplan-worktrees" / name).exists()


def test_in_worktree_empty_name_rejected(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty string passed via =-syntax must reject cleanly."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    code, payload = _run_init(
        ["init", "--in-worktree=", "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code != 0
    assert payload and payload.get("error") == "invalid_worktree_name"


def test_in_worktree_refuses_when_target_exists(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    target = fake_home / "Documents" / ".megaplan-worktrees" / "occupied"
    target.mkdir(parents=True)
    (target / "stray.txt").write_text("hi", encoding="utf-8")

    code, payload = _run_init(
        ["init", "--in-worktree", "occupied", "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code != 0
    assert payload and payload.get("error") == "worktree_target_exists"
    # Stray file was NOT touched.
    assert (target / "stray.txt").read_text(encoding="utf-8") == "hi"


def test_in_worktree_refuses_when_branch_exists(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "branch", "preexisting")

    code, payload = _run_init(
        ["init", "--in-worktree", "preexisting", "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code != 0
    assert payload and payload.get("error") == "worktree_branch_exists"
    assert not (fake_home / "Documents" / ".megaplan-worktrees" / "preexisting").exists()


def test_in_worktree_refuses_during_rebase(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    # Simulate an in-progress rebase by dropping a marker dir.
    (repo / ".git" / "rebase-merge").mkdir()

    code, payload = _run_init(
        ["init", "--in-worktree", "blocked", "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code != 0
    assert payload and payload.get("error") == "repo_busy"
    assert not (fake_home / "Documents" / ".megaplan-worktrees" / "blocked").exists()


def test_in_worktree_refuses_during_merge(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / ".git" / "MERGE_HEAD").write_text("deadbeef\n", encoding="utf-8")

    code, payload = _run_init(
        ["init", "--in-worktree", "blocked2", "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code != 0
    assert payload and payload.get("error") == "repo_busy"


def test_in_worktree_worktree_from_overrides_base(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    head1 = _init_repo(repo)
    # Make a second commit so HEAD moves.
    (repo / "second.txt").write_text("hi", encoding="utf-8")
    _git(repo, "add", "second.txt")
    _git(repo, "commit", "-m", "second")
    head2 = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert head1 != head2

    code, payload = _run_init(
        [
            "init",
            "--in-worktree",
            "from-base",
            "--worktree-from",
            head1,
            "idea",
        ],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code == 0, payload
    expected_wt = fake_home / "Documents" / ".megaplan-worktrees" / "from-base"
    # The worktree's HEAD should match head1, not head2.
    wt_head = _git(expected_wt, "rev-parse", "HEAD").stdout.strip()
    assert wt_head == head1
    # No 'second.txt' in the worktree — proves the base ref took effect.
    assert not (expected_wt / "second.txt").exists()


def test_in_worktree_rejects_with_project_dir(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    code, payload = _run_init(
        [
            "init",
            "--in-worktree",
            "double",
            "--project-dir",
            str(repo),
            "idea",
        ],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code != 0
    assert payload and payload.get("error") == "invalid_args"


def test_worktree_from_without_in_worktree_rejected(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    code, payload = _run_init(
        [
            "init",
            "--worktree-from",
            "HEAD",
            "--project-dir",
            str(repo),
            "idea",
        ],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code != 0
    assert payload and payload.get("error") == "invalid_args"


def test_init_without_project_dir_or_in_worktree_errors(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    code, payload = _run_init(
        ["init", "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code != 0
    assert payload and payload.get("error") == "invalid_args"


# ---- Carry-dirty tests ----


def _porcelain(repo: Path) -> str:
    return _git(repo, "status", "--porcelain").stdout


def test_carry_dirty_modified_tracked_file(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "README.md").write_text("modified content\n", encoding="utf-8")

    code, payload = _run_init(
        ["init", "--in-worktree", "carry-mod", "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code == 0, payload

    wt = fake_home / "Documents" / ".megaplan-worktrees" / "carry-mod"
    assert (wt / "README.md").read_text(encoding="utf-8") == "modified content\n"
    # Source untouched (still modified, not reset).
    assert (repo / "README.md").read_text(encoding="utf-8") == "modified content\n"
    assert "README.md" in _porcelain(repo)


def test_carry_dirty_staged_file_becomes_unstaged(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "README.md").write_text("staged change\n", encoding="utf-8")
    _git(repo, "add", "README.md")

    code, payload = _run_init(
        ["init", "--in-worktree", "carry-staged", "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code == 0, payload

    wt = fake_home / "Documents" / ".megaplan-worktrees" / "carry-staged"
    # In the new worktree, the change shows up but is unstaged.
    porcelain = _porcelain(wt)
    # " M README.md" means modified-unstaged; "M  README.md" means staged.
    assert " M README.md" in porcelain, porcelain
    assert "M  README.md" not in porcelain, porcelain
    # Source still has the change staged.
    src_porcelain = _porcelain(repo)
    assert "M  README.md" in src_porcelain, src_porcelain


def test_carry_dirty_untracked_file(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "notes.txt").write_text("hello\n", encoding="utf-8")

    code, payload = _run_init(
        ["init", "--in-worktree", "carry-untracked", "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code == 0, payload

    wt = fake_home / "Documents" / ".megaplan-worktrees" / "carry-untracked"
    assert (wt / "notes.txt").read_text(encoding="utf-8") == "hello\n"
    # Source still has it too.
    assert (repo / "notes.txt").read_text(encoding="utf-8") == "hello\n"


def test_carry_dirty_skips_gitignored(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "add gitignore")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "foo.js").write_text("ignored\n", encoding="utf-8")

    code, payload = _run_init(
        ["init", "--in-worktree", "carry-ignore", "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code == 0, payload

    wt = fake_home / "Documents" / ".megaplan-worktrees" / "carry-ignore"
    assert not (wt / "node_modules").exists()


def test_carry_dirty_skips_megaplan_worktrees_dir(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    # Simulate a stray .megaplan-worktrees/ dir in the source (not gitignored).
    stray = repo / ".megaplan-worktrees" / "old-wt"
    stray.mkdir(parents=True)
    (stray / "junk.txt").write_text("junk\n", encoding="utf-8")

    code, payload = _run_init(
        ["init", "--in-worktree", "carry-norec", "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code == 0, payload

    wt = fake_home / "Documents" / ".megaplan-worktrees" / "carry-norec"
    assert not (wt / ".megaplan-worktrees").exists()


def test_clean_worktree_skips_carry(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "README.md").write_text("dirty\n", encoding="utf-8")
    (repo / "extra.txt").write_text("untracked\n", encoding="utf-8")

    code, payload = _run_init(
        ["init", "--in-worktree", "clean-fork", "--clean-worktree", "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code == 0, payload
    wt = fake_home / "Documents" / ".megaplan-worktrees" / "clean-fork"
    # New worktree's README matches HEAD ("base\n"), not the dirty content.
    assert (wt / "README.md").read_text(encoding="utf-8") == "base\n"
    assert not (wt / "extra.txt").exists()


def test_carry_dirty_and_clean_worktree_rejected(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    code, payload = _run_init(
        [
            "init",
            "--in-worktree",
            "conflict",
            "--carry-dirty",
            "--clean-worktree",
            "idea",
        ],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code != 0
    assert payload and payload.get("error") == "invalid_args"


def test_no_warning_when_source_clean(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    monkeypatch.chdir(repo)
    code = megaplan.main(["init", "--in-worktree", "clean-source", "idea"])
    captured = capsys.readouterr()
    assert code == 0, captured.out
    assert "warning: carried" not in captured.err


def test_warning_when_source_dirty(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "README.md").write_text("dirty\n", encoding="utf-8")
    (repo / "stray.txt").write_text("hi\n", encoding="utf-8")

    monkeypatch.chdir(repo)
    code = megaplan.main(["init", "--in-worktree", "dirty-source", "idea"])
    captured = capsys.readouterr()
    assert code == 0, captured.out
    err = captured.err
    assert "warning: carried 1 uncommitted file change(s)" in err, err
    assert "1 untracked file(s)" in err
    assert "--clean-worktree" in err
    assert "unstaged in the new worktree" in err


def test_rollback_on_patch_failure(
    tmp_path: Path,
    fake_home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If `git apply` fails inside the new worktree, the worktree must be
    removed and the source repo left unchanged."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "README.md").write_text("about-to-fail\n", encoding="utf-8")

    # Monkeypatch the patch-apply helper to raise as if git apply failed.
    from megaplan.bakeoff import worktree as wt_mod
    from megaplan.types import CliError

    def boom(*_a, **_kw):
        raise CliError("carry_dirty_failed", "simulated apply failure")

    monkeypatch.setattr(wt_mod, "_apply_patch", boom)

    code, payload = _run_init(
        ["init", "--in-worktree", "rollback", "idea"],
        cwd=repo,
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert code != 0, payload
    assert payload and payload.get("error") == "carry_dirty_failed"
    # New worktree dir should be gone.
    assert not (fake_home / "Documents" / ".megaplan-worktrees" / "rollback").exists()
    # Source unchanged (README still has dirty content; branch should be gone
    # too since `worktree remove --force` also drops the branch... actually
    # `git worktree remove` does NOT delete the branch by default. We just
    # assert the source's working tree is intact.
    assert (repo / "README.md").read_text(encoding="utf-8") == "about-to-fail\n"

def test_carry_includes_gitignored_briefs_excludes_run_state(tmp_path: Path) -> None:
    """`.megaplan/briefs/` is gitignored INPUT and must be carried into the
    worktree; `.megaplan/plans/` (run state) must NOT be. Regression for the
    `missing_idea_file` launch failure when `.megaplan/` is gitignored."""
    from megaplan.bakeoff import worktree as wt

    repo = tmp_path / "repo"
    head = _init_repo(repo)
    # Gitignore the whole .megaplan dir (as real repos do).
    (repo / ".gitignore").write_text(".megaplan/\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "ignore megaplan")

    # Input material (briefs) — gitignored but required by the run.
    briefs = repo / ".megaplan" / "briefs" / "epic"
    briefs.mkdir(parents=True)
    (briefs / "chain.yaml").write_text("milestones: []\n", encoding="utf-8")
    (briefs / "m0.md").write_text("# m0\n", encoding="utf-8")
    # Run state — gitignored AND must stay out of the carry.
    plans = repo / ".megaplan" / "plans" / "run1"
    plans.mkdir(parents=True)
    (plans / "state.json").write_text("{}", encoding="utf-8")

    target = tmp_path / "worktrees" / "wt1"
    wt.create_named_worktree(repo, target, head, "epic/test")

    tracked, untracked = wt.carry_dirty_state(repo, target)

    assert (target / ".megaplan" / "briefs" / "epic" / "chain.yaml").is_file()
    assert (target / ".megaplan" / "briefs" / "epic" / "m0.md").is_file()
    # Run state was NOT carried.
    assert not (target / ".megaplan" / "plans" / "run1" / "state.json").exists()
    assert untracked >= 2
