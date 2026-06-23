You are a DeepSeek subagent auditing overlap between the proposed AgentBox plan and existing Megaplan functionality. The brief embeds local file excerpts because you do not have filesystem tools. Return: existing functionality reusable directly, functionality needing extraction/generalization, missing pieces, risks/gotchas, and a recommended first implementation slice. Keep under 900 words and cite file names/sections.\nFocus only on repo registry and worktree service overlap.


--- FILE: docs/agentbox-persistent-machine-plan.md (1,180p) ---
# AgentBox Persistent Machine Plan

## Goal

Build a persistent remote agent machine that can host many repositories, receive selected credentials from the user's laptop, launch and supervise many concurrent coding operations, and expose the whole system through a resident Discord control plane.

This is broader than the current Megaplan Cloud worker. Megaplan Cloud is a remote runner for plans/chains. AgentBox is a remote development and agent operations machine.

The short version:

- the user can spin up Megaplan plans or chains on the machine;
- each run gets an isolated worktree, branch, tmux session, logs, and operation record;
- a **Guardian** checks all active operations every `X` minutes and safely keeps them moving;
- a **Discord Operator** starts on user messages, has access to AgentBox state/tools, and can launch or inspect work on demand;
- both actors use the same operation registry and safety/approval system.

The core constraint is:

- one persistent machine;
- many repos on that machine;
- one canonical repo checkout or bare repo per source repo;
- one git worktree per operation per repo;
- one tmux/session/process group per operation;
- one Guardian daemon supervising all known operations;
- one Discord-triggered Operator agent for interactive control;
- Discord as the primary human control surface.

## Resident Actors

AgentBox has two primary resident actors. They share the same state, tools, and safety policy, but they wake up for different reasons.

### Guardian

The Guardian is a long-running supervisor daemon. It wakes on a fixed cadence, for example every 5, 10, or 15 minutes, and checks every active operation.

Responsibilities:

- scan the operation registry;
- inspect tmux/process liveness;
- inspect Megaplan plan or chain status;
- read recent logs and structured state;
- classify operations as running, stale, blocked, failed, completed, or awaiting approval;
- restart a missing runner when the operation type has a known-safe restart path;
- advance a chain when the next step is unambiguous;
- file or update pending approvals for risky actions;
- notify Discord when a run blocks, fails, completes, or needs human input;
- update operation state and health summaries.

The Guardian should not silently make product decisions, resolve merge conflicts, delete worktrees, merge PRs, or accept quality debt. Those become explicit pending approvals.

### Discord Operator

The Discord Operator is an on-demand agent launched by Discord messages. It is the interactive control plane.

Responsibilities:

- answer "what is running?";
- launch a Megaplan plan or chain in a fresh worktree;
- launch Codex, Claude, subagent, shell, or test operations;
- inspect logs and summarize failures;
- ask the Guardian what is stuck;
- approve or reject pending actions;
- stop, restart, or clean up operations when authorized;
- inspect repo/worktree/branch state;
- push branches or open PRs when authorized.

The Operator should have access to all AgentBox data and tools, but it should still go through the same safety policy as the Guardian. Discord messages are the trigger, not a bypass.

### Shared State

Both actors depend on the same durable records:

```text
operation id
operation kind
repo(s)
worktree(s)
branch(es)
tmux session
command
log path
current status
last check timestamp
pending approvals
Discord conversation/thread/message ids
PR/CI metadata
```

This operation registry is the center of the system. The Guardian is scheduled/autonomous; the Discord Operator is user-triggered/interactive.

## Recommendation

Use a Hetzner VM or dedicated server as the primary target. Keep Railway support for simpler one-off hosted runners, but do not force the full resident-machine model into Railway's persistent-container model.

Start with a Hetzner `CX53`-class box for the prototype:

- 16 vCPU
- 32 GB RAM
- 320 GB disk
- enough to validate several concurrent agents, tests, and repos

If the workload saturates shared CPU or disk, move the same bootstrap to a dedicated or auction server. The design should make host migration boring.

## Target Layout

```text
/workspace
  /repos
    /megaplan.git
    /reigh-app.git
    /reigh-worker.git

  /worktrees
    /op-20260623-foo
      /megaplan
      /reigh-app
    /op-20260623-bar
      /megaplan

  /runs
    /op-20260623-foo
      manifest.yaml
      state.json
      log.txt
      events.ndjson

  /secrets
    agentbox.env
    codex-auth.json
    claude-refresh-token.env

  /manager
    agentbox.db
    config.yaml
```

Each operation gets its own isolated worktree and branch. No two agents mutate the same checkout.

## Existing Megaplan Pieces To Reuse

### Worktree Mechanics

Megaplan already has the basic worktree substrate:

- `megaplan init --in-worktree NAME`
- `megaplan chain start --in-worktree NAME`
- `--worktree-from`
- `--clean-worktree`
- `--carry-dirty`
- `--fresh` for chain worktrees
- worktree metadata persisted into plan state

The shared primitives live in:

- `arnold_pipelines/megaplan/bakeoff/worktree.py`

Useful functions include:

- `validate_worktree_name`
- `ensure_no_inprogress_op`
- `resolve_ref`
- `branch_exists`
- `worktree_registered`
- `create_named_worktree`
- `create_worktree`
- `remove_worktree`
- dirty-state carry helpers

Current limitation: these are command-scoped and current-repo scoped. AgentBox needs them promoted into a machine-scoped operation service.

### Discord Resident Runtime

Megaplan already has Discord-facing resident infrastructure:

- `arnold_pipelines/megaplan/resident/discord.py`
- `arnold_pipelines/megaplan/resident/runtime.py`
- `arnold_pipelines/megaplan/resident/auth.py`
- `arnold_pipelines/megaplan/resident/cloud.py`
- `arnold_pipelines/megaplan/resident/cli.py`


--- FILE: arnold_pipelines/megaplan/bakeoff/worktree.py (1,340p) ---
"""Git worktree lifecycle helpers for bake-offs."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from arnold_pipelines.megaplan._core.io import atomic_write_json, now_utc
from arnold_pipelines.megaplan.types import CliError


def _git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CliError("bakeoff_git_failed", str(exc)) from exc


def _git_error_detail(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or "").strip() or "git command failed"


# ---- Shared primitives (used by --in-worktree on `megaplan init` too) ----

_WORKTREE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def validate_worktree_name(name: str) -> str:
    if not isinstance(name, str) or not _WORKTREE_NAME_RE.match(name):
        raise CliError(
            "invalid_worktree_name",
            "worktree name must match ^[a-z0-9][a-z0-9._-]{0,63}$ "
            "(lowercase alnum, dot, underscore, hyphen; 1-64 chars; "
            f"must start alnum). Got: {name!r}",
        )
    return name


def ensure_no_inprogress_op(repo: Path) -> None:
    """Refuse if the repo is mid-rebase/merge/cherry-pick/bisect.

    Untracked / modified files are fine; an interrupted operation is not,
    because forking a worktree off such a state is asking for confusion.
    """
    git_dir_result = _git(repo, ["rev-parse", "--git-dir"])
    if git_dir_result.returncode != 0:
        raise CliError("not_a_git_repo", _git_error_detail(git_dir_result))
    git_dir = Path(git_dir_result.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (repo / git_dir).resolve()
    markers = {
        "rebase-merge": "in-progress rebase (rebase-merge)",
        "rebase-apply": "in-progress rebase (rebase-apply)",
        "MERGE_HEAD": "in-progress merge",
        "CHERRY_PICK_HEAD": "in-progress cherry-pick",
        "REVERT_HEAD": "in-progress revert",
        "BISECT_LOG": "in-progress bisect",
    }
    for marker, label in markers.items():
        if (git_dir / marker).exists():
            raise CliError(
                "repo_busy",
                f"refusing to create worktree: {label} detected in {git_dir}",
            )


def resolve_ref(repo: Path, ref: str) -> str:
    """Resolve *ref* to a full SHA in *repo*; raises if unknown."""
    result = _git(repo, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
    if result.returncode != 0:
        raise CliError(
            "invalid_worktree_ref",
            f"--worktree-from ref does not resolve in this repo: {ref}",
        )
    return result.stdout.strip()


def branch_exists(repo: Path, branch: str) -> bool:
    """Return True if *branch* exists locally or on any remote."""
    # Local branches
    local = _git(repo, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"])
    if local.returncode == 0:
        return True
    # Remote-tracking branches across all remotes
    listing = _git(repo, ["for-each-ref", "--format=%(refname)", "refs/remotes/"])
    if listing.returncode == 0:
        suffix = f"/{branch}"
        for line in listing.stdout.splitlines():
            # refs/remotes/<remote>/<branch> — strip first three components
            tail = line.removeprefix("refs/remotes/")
            if "/" in tail and tail.split("/", 1)[1] == branch:
                return True
            # Defensive: in case branch contains slashes
            if tail.endswith(suffix):
                return True
    return False


def worktree_registered(repo: Path, target: Path) -> bool:
    """Return True if *target* is registered in `git worktree list` even if its
    on-disk directory was deleted by hand (a 'prunable' worktree)."""
    result = _git(repo, ["worktree", "list", "--porcelain"])
    if result.returncode != 0:
        return False
    target_resolved = str(target.resolve())
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            wt = line.removeprefix("worktree ").strip()
            try:
                if str(Path(wt).resolve()) == target_resolved:
                    return True
            except OSError:
                if wt == str(target):
                    return True
    return False


def create_named_worktree(
    repo: Path,
    target: Path,
    base_ref: str,
    branch: str,
) -> None:
    """Create a new worktree at *target* on a brand-new *branch* off *base_ref*.

    Unlike :func:`create_worktree` (which checks out detached for bakeoff),
    this allocates a real branch — useful when the user intends to commit
    inside the worktree.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    result = _git(
        repo,
        ["worktree", "add", "-b", branch, str(target), base_ref],
    )
    if result.returncode != 0:
        raise CliError("worktree_create_failed", _git_error_detail(result))


def capture_base_sha(repo: Path) -> str:
    result = _git(repo, ["rev-parse", "HEAD"])
    if result.returncode != 0:
        raise CliError("bakeoff_git_failed", _git_error_detail(result))
    return result.stdout.strip()


def create_worktree(repo: Path, target: Path, base_sha: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = _git(
        repo,
        ["worktree", "add", "--detach", str(target), base_sha],
    )
    if result.returncode != 0:
        raise CliError("bakeoff_worktree_failed", _git_error_detail(result))


def remove_worktree(target: Path, force: bool = True) -> None:
    if not target.exists():
        return
    repo = _main_worktree_for(target)
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(target))
    result = _git(repo, args)
    if result.returncode != 0:
        raise CliError("bakeoff_worktree_failed", _git_error_detail(result))
    _remove_empty_parent(target.parent)


def mark_crashed(target: Path, reason: str) -> None:
    target.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        target / "BAKEOFF_CRASHED",
        {
            "reason": reason,
            "ts": now_utc(),
            "pid": os.getpid(),
        },
    )


def ensure_main_worktree_clean(repo: Path, *, allow_dirty: bool = False) -> None:
    if allow_dirty:
        return
    result = _git(repo, ["status", "--porcelain"])
    if result.returncode != 0:
        raise CliError("bakeoff_git_failed", _git_error_detail(result))
    if result.stdout.strip():
        raise CliError(
            "bakeoff_dirty_worktree",
            "main worktree is dirty; run `git status` or pass --allow-dirty.",
        )


def _main_worktree_for(target: Path) -> Path:
    result = _git(target, ["worktree", "list", "--porcelain"])
    if result.returncode != 0:
        raise CliError("bakeoff_worktree_failed", _git_error_detail(result))
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line.removeprefix("worktree ")).resolve()
    raise CliError("bakeoff_worktree_failed", "could not locate main worktree")


def _remove_empty_parent(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass


# ---- Carry-dirty support for `megaplan init --in-worktree` ----

# Directory names that must never be copied as "untracked" content because
# they belong to git/megaplan infrastructure and would either confuse the new
# worktree or cause infinite recursion.
_CARRY_DIRTY_EXCLUDED_PREFIXES: tuple[str, ...] = (
    ".git/",
    ".git\\",
    ".claude/",
    ".claude\\",
    ".megaplan-worktrees/",
    ".megaplan-worktrees\\",
)


def _is_excluded_carry_path(rel_posix: str) -> bool:
    """Reject paths under .git/, .claude/, or .megaplan-worktrees/."""
    if rel_posix in (".git", ".claude", ".megaplan-worktrees"):
        return True
    for prefix in _CARRY_DIRTY_EXCLUDED_PREFIXES:
        if rel_posix.startswith(prefix):
            return True
    return False


def has_dirty_state(repo: Path) -> bool:
    """Return True if *repo* has any tracked modification or untracked file."""
    diff = _git(repo, ["diff", "HEAD", "--quiet"])
    if diff.returncode != 0:
        return True
    others = _git(repo, ["ls-files", "--others", "--exclude-standard", "-z"])
    if others.returncode != 0:
        raise CliError("carry_dirty_failed", _git_error_detail(others))
    return bool(others.stdout)


def _list_untracked(repo: Path) -> list[str]:
    """Return repo-relative POSIX paths of untracked files (excluding ignored)."""
    result = _git(repo, ["ls-files", "--others", "--exclude-standard", "-z"])
    if result.returncode != 0:
        raise CliError("carry_dirty_failed", _git_error_detail(result))
    raw = result.stdout
    if not raw:
        return []
    return [p for p in raw.split("\0") if p]


_CARRY_IGNORED_INPUT_PREFIXES: tuple[str, ...] = (
    ".megaplan/briefs/",
)


def _list_ignored_inputs(repo: Path) -> list[str]:
    """Return repo-relative POSIX paths of gitignored INPUT files to carry anyway.

    ``_list_untracked`` uses ``--exclude-standard`` and therefore hides anything
    matched by ``.gitignore``. But some gitignored paths — notably
    ``.megaplan/briefs/`` (the chain/milestone spec files a ``--in-worktree`` run
    reads) — are required INPUT, not run state, and must travel into the new
    worktree or the run fails with ``missing_idea_file``. Run state
    (``.megaplan/plans/``, ``.state-locks/``) is deliberately NOT included.
    """
    paths: list[str] = []
    for prefix in _CARRY_IGNORED_INPUT_PREFIXES:
        result = _git(
            repo,
            [
                "ls-files",
                "--others",
                "--ignored",
                "--exclude-standard",
                "-z",
                "--",
                prefix,
            ],
        )
        if result.returncode != 0:
            # Non-fatal: missing path or git error -> carry nothing extra here.
            continue
        if result.stdout:
            paths.extend(p for p in result.stdout.split("\0") if p)
    return paths


def _capture_tracked_patch(repo: Path) -> bytes:
    """Capture `git diff HEAD --binary` as bytes (preserves binary diffs)."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--binary", "--no-color"],
            cwd=repo,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CliError("carry_dirty_failed", str(exc)) from exc
    if result.returncode != 0:
        detail = (result.stderr or b"").decode("utf-8", "replace").strip()
        raise CliError("carry_dirty_failed", detail or "git diff HEAD failed")
    return result.stdout


def _apply_patch(repo: Path, patch: bytes) -> None:
    """Apply *patch* in *repo* without touching the index. Errors are hard."""
    try:
        result = subprocess.run(
            ["git", "apply", "--binary"],
            cwd=repo,
            input=patch,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CliError("carry_dirty_failed", str(exc)) from exc
    if result.returncode != 0:
        detail = (result.stderr or b"").decode("utf-8", "replace").strip()
        raise CliError(
            "carry_dirty_failed",
            f"git apply failed in new worktree: {detail or 'unknown error'}",
        )


--- FILE: arnold_pipelines/megaplan/cli/__init__.py (1798,2138p) ---
def _setup_init_worktree(args: argparse.Namespace) -> None:
    """When ``--in-worktree`` is set on ``megaplan init``, create the worktree
    and rewrite ``args`` so the rest of the init flow lands inside it.

    Safety contract: this function MUST be strictly additive. It may only
    create one new branch + one new worktree directory. It never modifies the
    invoking repo, its branches (other than the one it creates), its remotes,
    its stash, or any other worktree. If anything looks ambiguous, it raises.
    """
    name = getattr(args, "in_worktree", None)
    clean_worktree = bool(getattr(args, "clean_worktree", False))
    carry_dirty_flag = bool(getattr(args, "carry_dirty", False))
    if clean_worktree and carry_dirty_flag:
        raise CliError(
            "invalid_args",
            "--clean-worktree and --carry-dirty are mutually exclusive",
        )
    if name is None:
        if getattr(args, "worktree_from", None):
            raise CliError(
                "invalid_args",
                "--worktree-from is only valid alongside --in-worktree",
            )
        if clean_worktree or carry_dirty_flag:
            raise CliError(
                "invalid_args",
                "--clean-worktree / --carry-dirty are only valid with --in-worktree",
            )
        return

    from arnold_pipelines.megaplan.bakeoff.worktree import (
        branch_exists,
        carry_dirty_state_atomic,
        create_named_worktree,
        ensure_no_inprogress_op,
        has_dirty_state,
        resolve_ref,
        validate_worktree_name,
        worktree_registered,
    )

    if getattr(args, "project_dir", None):
        raise CliError(
            "invalid_args",
            "pass either --project-dir or --in-worktree, not both",
        )

    validate_worktree_name(name)

    # Locate the invoking repo. We deliberately do NOT use --project-dir here
    # (we just rejected it above); we use cwd-walk-up so the user can run
    # `megaplan init --in-worktree foo` from anywhere inside the repo.
    invoking_repo = _find_git_root(Path.cwd().resolve())
    if invoking_repo is None:
        raise CliError(
            "not_a_git_repo",
            "--in-worktree requires running from inside a git repository",
        )

    ensure_no_inprogress_op(invoking_repo)

    target = (Path.home() / "Documents" / ".megaplan-worktrees" / name).resolve()
    if target.exists():
        raise CliError(
            "worktree_target_exists",
            f"refusing to create worktree: target path already exists: {target}",
        )
    if worktree_registered(invoking_repo, target):
        raise CliError(
            "worktree_already_registered",
            f"git already has a worktree registered at {target} "
            "(run `git worktree prune` manually if it's stale)",
        )
    if branch_exists(invoking_repo, name):
        raise CliError(
            "worktree_branch_exists",
            f"branch {name!r} already exists locally or on a remote; "
            "pick a different --in-worktree name",
        )

    base_ref = getattr(args, "worktree_from", None) or "HEAD"
    base_sha = resolve_ref(invoking_repo, base_ref)

    create_named_worktree(invoking_repo, target, base_sha, name)

    # Carry uncommitted state from the source repo into the new worktree
    # unless the caller explicitly opted out via --clean-worktree. The source
    # repo is read-only throughout: we only capture a diff and copy untracked
    # files; we never run stash/checkout/reset/clean on it.
    tracked_carried = 0
    untracked_carried = 0
    if not clean_worktree:
        should_carry = carry_dirty_flag or has_dirty_state(invoking_repo)
        if should_carry:
            tracked_carried, untracked_carried = carry_dirty_state_atomic(
                invoking_repo, target
            )

    # Rewrite args so the rest of the init flow lands inside the worktree.
    args.project_dir = str(target)
    # Stash audit data on args so handle_init can persist it into plan state.
    args._worktree_meta = {
        "name": name,
        "path": str(target),
        "branch": name,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "source_repo": str(invoking_repo),
        "carried_tracked": tracked_carried,
        "carried_untracked": untracked_carried,
    }
    # Update work-dir override so subprocess workers run in the worktree.
    from arnold_pipelines.megaplan.workers import set_work_dir_override

    set_work_dir_override(target)

    print(
        f"Created worktree at {target} on branch {name} "
        f"(base {base_sha[:12]}); initializing plan inside it...",
        file=sys.stderr,
    )
    if tracked_carried or untracked_carried:
        print(
            f"warning: carried {tracked_carried} uncommitted file change(s) "
            f"and {untracked_carried} untracked file(s) from {invoking_repo} "
            f"into {target}. Source worktree is unchanged.\n"
            f"  * To start the worktree from a clean base instead, commit your "
            f"changes first or re-run with --clean-worktree.\n"
            f"  * Files were carried as unstaged in the new worktree (staging "
            f"information is not preserved). Run `git diff` or `git status` "
            f"inside the worktree to inspect.",
            file=sys.stderr,
        )


def _reset_chain_worktree_target(
    invoking_repo: Path,
    target: Path,
    branch: str,
    *,
    worktree_registered: Callable[[Path, Path], bool],
) -> None:
    """Clear the named chain worktree target for an explicit --fresh start."""
    if not (target.exists() or worktree_registered(invoking_repo, target)):
        return
    if worktree_registered(invoking_repo, target):
        proc = subprocess.run(
            ["git", "worktree", "remove", "--force", str(target)],
            cwd=str(invoking_repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise CliError(
                "worktree_reset_failed",
                (
                    f"refusing --fresh worktree reset: could not remove registered "
                    f"worktree at {target}: {(proc.stderr or proc.stdout).strip()}"
                ),
            )
    if target.exists():
        shutil.rmtree(target)
    proc = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=str(invoking_repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        delete = subprocess.run(
            ["git", "branch", "-D", branch],
            cwd=str(invoking_repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if delete.returncode != 0:
            raise CliError(
                "worktree_reset_failed",
                (
                    f"refusing --fresh worktree reset: could not delete local "
                    f"branch {branch!r}: {(delete.stderr or delete.stdout).strip()}"
                ),
            )


def _chain_worktree_base_ref(args: argparse.Namespace) -> str:
    """Resolve the git ref to fork the chain's shared worktree from.

    Explicit ``--worktree-from`` always wins. Otherwise default to the chain
    spec's ``base_branch`` — NOT the invoking ``HEAD``. The chain runs every
    milestone off ``base_branch`` (``git checkout -B <milestone> <base_branch>``),
    so forking the worktree from a stale invoking HEAD makes any carried-untracked
    file that is *tracked* on ``base_branch`` collide on that checkout
    ("untracked working tree files would be overwritten"; ticket 01KTQ35AB8).
    Forking from ``base_branch`` lands the carried dirt on top of the base the
    chain actually uses, so the checkout is a no-op base and never collides.
    Falls back to ``HEAD`` if the spec is absent or unreadable.
    """
    explicit = getattr(args, "worktree_from", None)
    if explicit:
        return explicit
    spec_path = getattr(args, "spec", None)
    if spec_path:
        try:
            from arnold_pipelines.megaplan.chain import load_spec

            return load_spec(Path(spec_path)).base_branch
        except CliError:
            pass
    return "HEAD"


def _setup_chain_worktree(args: argparse.Namespace) -> None:
    """Create a shared worktree for ``megaplan chain`` and reroot the command.

    Unlike ``megaplan init --in-worktree``, this creates one worktree for the
    entire chain. Every milestone plan initialized by the chain then receives
    ``--project-dir <that-worktree>`` from the chain driver.
    """
    name = getattr(args, "in_worktree", None)
    clean_worktree = bool(getattr(args, "clean_worktree", False))
    carry_dirty_flag = bool(getattr(args, "carry_dirty", False))
    action = getattr(args, "chain_action", None)
    if clean_worktree and carry_dirty_flag:
        raise CliError(
            "invalid_args",
            "--clean-worktree and --carry-dirty are mutually exclusive",
        )
    if name is None:
        if getattr(args, "worktree_from", None):
            raise CliError(
                "invalid_args",
                "--worktree-from is only valid alongside --in-worktree",
            )
        if clean_worktree or carry_dirty_flag:
            raise CliError(
                "invalid_args",
                "--clean-worktree / --carry-dirty are only valid with --in-worktree",
            )
        return

    if action not in (None, "start", "plan", "execute"):
        raise CliError(
            "invalid_args",
            "--in-worktree is only valid for `megaplan chain start`, `plan`, or `execute`",
        )
    if getattr(args, "project_dir", None):
        raise CliError(
            "invalid_args",
            "pass either --project-dir or --in-worktree, not both",
        )

    from arnold_pipelines.megaplan.bakeoff.worktree import (
        branch_exists,
        carry_dirty_state_atomic,
        create_named_worktree,
        ensure_no_inprogress_op,
        has_dirty_state,
        resolve_ref,
        validate_worktree_name,
        worktree_registered,
    )

    validate_worktree_name(name)

    invoking_repo = _find_git_root(Path.cwd().resolve())
    if invoking_repo is None:
        raise CliError(
            "not_a_git_repo",
            "--in-worktree requires running from inside a git repository",
        )
    ensure_no_inprogress_op(invoking_repo)

    target = (Path.home() / "Documents" / ".megaplan-worktrees" / name).resolve()
    if bool(getattr(args, "fresh", False)):
        _reset_chain_worktree_target(
            invoking_repo,
            target,
            name,
            worktree_registered=worktree_registered,
        )
    if target.exists():
        raise CliError(
            "worktree_target_exists",
            f"refusing to create worktree: target path already exists: {target}",
        )
    if worktree_registered(invoking_repo, target):
        raise CliError(
            "worktree_already_registered",
            f"git already has a worktree registered at {target} "
            "(run `git worktree prune` manually if it's stale)",
        )
    if branch_exists(invoking_repo, name):
        raise CliError(
            "worktree_branch_exists",
            f"branch {name!r} already exists locally or on a remote; "
            "pick a different --in-worktree name",
        )

    base_ref = _chain_worktree_base_ref(args)
    base_sha = resolve_ref(invoking_repo, base_ref)
    create_named_worktree(invoking_repo, target, base_sha, name)

    tracked_carried = 0
    untracked_carried = 0
    if not clean_worktree:
        should_carry = carry_dirty_flag or has_dirty_state(invoking_repo)
        if should_carry:
            tracked_carried, untracked_carried = carry_dirty_state_atomic(
                invoking_repo, target
            )

    args.project_dir = str(target)
    from arnold_pipelines.megaplan.workers import set_work_dir_override

    set_work_dir_override(target)

    # Point engine-isolation at the invoking (engine) checkout.  The target
    # worktree shadows the editable install when Python resolves ``arnold`` from
    # cwd, so ``megaplan_engine_root()`` needs an explicit anchor.
    os.environ["MEGAPLAN_ENGINE_ROOT"] = str(invoking_repo)

    print(
        f"Created chain worktree at {target} on branch {name} "
        f"(base {base_sha[:12]}); running chain inside it...",
        file=sys.stderr,
    )
    if tracked_carried or untracked_carried:
        print(
            f"warning: carried {tracked_carried} uncommitted file change(s) "
            f"and {untracked_carried} untracked file(s) from {invoking_repo} "
            f"into {target}. Source worktree is unchanged.",
            file=sys.stderr,
        )



def _handle_list_pipelines(args: argparse.Namespace) -> StepResponse:

--- FILE: arnold_pipelines/megaplan/chain/git_ops.py (253,330p) ---
def _clean_worktree_for_chain(root: Path, writer) -> None:
    """Reset tracked changes and remove megaplan-generated untracked files.

    Chain execution re-creates .megaplan metadata each phase; stale working-tree
    changes from a previous run (modified schemas, deleted events.jsonl files,
    telemetry dumps, lock files) would otherwise block branch checkouts.
    """
    writer("[chain] cleaning worktree for automated branch checkout\n")
    _compat()._run_command(
        root,
        ["git", "reset", "--hard", "HEAD"],
        writer=writer,
        error_code="git_clean_failed",
    )
    # Remove stale untracked source/output files while preserving megaplan plan
    # state (which lives under .megaplan and may be needed across phases).
    _compat()._run_command(
        root,
        ["git", "clean", "-fd", "-e", ".megaplan"],
        writer=writer,
        error_code="git_clean_failed",
    )
    for subdir in ("epics", "schemas", "telemetry", ".state-locks"):
        path = root / ".megaplan" / subdir
        if path.exists():
            _compat()._run_command(
                root,
                ["git", "clean", "-fd", str(path.relative_to(root))],
                writer=writer,
                error_code="git_clean_failed",
            )


def _checkout_milestone_branch(
    root: Path,
    branch: str,
    *,
    base_branch: str,
    writer,
    from_origin: bool = False,
) -> None:
    """Create or resume the milestone branch and push it to origin.

    When ``from_origin`` is True, a new milestone branch forks from
    ``origin/<base_branch>`` so it includes prior squash-merged milestone PRs.
    Local ``<base_branch>`` can be stale in that workflow because the squash
    merge creates a fresh commit only on the remote base branch.
    """
    if _compat()._remote_branch_exists(root, branch, writer=writer):
        _clean_worktree_for_chain(root, writer)
        _compat()._run_command(root, ["git", "fetch", "origin", branch], writer=writer, error_code="git_branch_failed")
        _compat()._run_command(
            root,
            ["git", "checkout", "-B", branch, f"origin/{branch}"],
            writer=writer,
            error_code="git_branch_failed",
        )
        return
    _clean_worktree_for_chain(root, writer)
    fork_point = base_branch
    if from_origin:
        fetch = _compat().subprocess.run(
            ["git", "fetch", "origin", base_branch],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        writer(f"[chain] git fetch origin {base_branch} -> rc={fetch.returncode}\n")
        if fetch.returncode == 0:
            fork_point = f"origin/{base_branch}"
            writer(
                f"[chain] forking {branch} from {fork_point} "
                "(authoritative merged history)\n"
            )
        else:
            detail = (fetch.stderr or fetch.stdout or "").strip()
