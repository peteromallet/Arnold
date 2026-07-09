from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.types import CliError

_MISSING_REMOTE_REF_MARKERS = (
    "couldn't find remote ref",
    "could not find remote ref",
    "remote ref does not exist",
)

_NON_FAST_FORWARD_PUSH_MARKERS = (
    "non-fast-forward",
    "[rejected]",
    "fetch first",
    "stale info",
    "failed to push some refs",
)

_CHAIN_RUNTIME_JOURNAL_PATTERNS = (
    ".megaplan/epics/*/events.jsonl",
    ".megaplan/plans/*/events.ndjson",
    ".megaplan/plans/*/execution_trace.jsonl",
)

_CHAIN_INTERNAL_DIRTY_PATTERNS = (
    *_CHAIN_RUNTIME_JOURNAL_PATTERNS,
    ".megaplan/incident-ledger/*",
    ".megaplan/runtime/*",
)

_DEFAULT_COMMAND_TIMEOUT_SECONDS = 120
_GIT_PUSH_TIMEOUT_SECONDS = 600
_GIT_PUSH_TIMEOUT_RECOVERY_WINDOW_SECONDS = 30


@dataclass(frozen=True)
class CommitResult:
    committed: bool
    pushed: bool
    commit_sha: str | None = None
    previous_ref: str | None = None
    previous_sha: str | None = None
    base_branch: str | None = None
    audit_notes: list[str] = field(default_factory=list)


def _compat():
    module = sys.modules.get(__package__)
    if module is None:  # pragma: no cover - defensive import guard
        raise RuntimeError(f"{__package__} not loaded")
    return module


def _refresh_base_branch(
    root: Path,
    base_branch: str,
    *,
    writer,
    no_git_refresh: bool = False,
    expected_sha: str | None = None,
) -> str | None:
    """Run a best-effort refresh of ``base_branch`` before milestone work.

    When ``no_git_refresh`` is True, this is a no-op (still logs that it was
    skipped). This guard exists so developer checkouts running ``megaplan
    chain`` do not get their currently checked-out branch stomped by an
    automatic base-branch checkout.

    ``git checkout <base_branch>`` is intentionally avoided because Git refuses
    to check out a branch that is active in a sibling worktree. The remote
    ``origin/<base_branch>`` ref is refreshed and used as the fork point; a
    local fast-forward pull is only attempted when this worktree is already on
    the base branch.
    """
    if no_git_refresh:
        writer("[chain] skipping git refresh (--no-git-refresh)\n")
        return None
    remote_sha = _compat()._fetch_base_branch(
        root,
        base_branch,
        writer=writer,
        expected_sha=expected_sha,
        error_code="git_refresh_failed",
    )

    current_cmd = ["git", "symbolic-ref", "--short", "HEAD"]
    current = _compat().subprocess.run(
        current_cmd, cwd=str(root), capture_output=True, text=True, check=False, timeout=120
    )
    writer(f"[chain] {' '.join(current_cmd)} -> rc={current.returncode}\n")
    if current.returncode != 0 or current.stdout.strip() != base_branch:
        writer(
            f"[chain] using refreshed origin/{base_branch} as the milestone fork point; "
            f"local {base_branch} checkout refresh skipped\n"
        )
        return

    pull_cmd = ["git", "pull", "--ff-only", "origin", base_branch]
    try:
        proc = _compat().subprocess.run(
            pull_cmd, cwd=str(root), capture_output=True, text=True, check=False, timeout=120
        )
        writer(f"[chain] {' '.join(pull_cmd)} -> rc={proc.returncode}\n")
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            if detail:
                writer(f"[chain] {' '.join(pull_cmd)} output:\n{detail}\n")
            writer(
                "[chain] warning: fast-forward refresh failed; "
                f"falling back to hard reset to refreshed origin/{base_branch} "
                "so the working tree (chain spec + idea files) matches the latest "
                "base. Safe before milestone work starts; discards uncommitted "
                "local edits (committed briefs are preserved).\n"
            )
            # Force the working tree to the refreshed origin/<base> so the chain
            # spec / idea files are read from the latest base commit (a stale
            # working tree is the cause of missing_idea_file / missing_anchor_file
            # when briefs were just pushed). pull --ff-only can fail when the
            # working tree is dirty (e.g. the orchestrator staged spec uploads)
            # or the local base diverged; reset --hard recovers both.
            reset_cmd = ["git", "reset", "--hard", f"origin/{base_branch}"]
            reset_proc = _compat().subprocess.run(
                reset_cmd, cwd=str(root), capture_output=True, text=True, check=False, timeout=120
            )
            writer(f"[chain] {' '.join(reset_cmd)} -> rc={reset_proc.returncode}\n")
            if reset_proc.returncode != 0:
                rdetail = (reset_proc.stderr or reset_proc.stdout or "").strip()
                if rdetail:
                    writer(f"[chain] {' '.join(reset_cmd)} output:\n{rdetail}\n")
                writer(
                    "[chain] warning: hard reset also failed; continuing with the "
                    f"stale local {base_branch} working tree.\n"
                )
    except (_compat().subprocess.TimeoutExpired, FileNotFoundError) as exc:
        writer(f"[chain] {' '.join(pull_cmd)} failed: {exc}\n")
        writer(
            "[chain] warning: fast-forward refresh failed; "
            f"continuing with refreshed origin/{base_branch}. "
            "This is expected when the local base has milestone commits "
            "or origin moved independently.\n"
        )
    return remote_sha


def _command_detail(proc: subprocess.CompletedProcess[str]) -> str:
    return (proc.stderr or proc.stdout or "").strip()


def _is_missing_remote_ref_detail(detail: str) -> bool:
    lowered = detail.lower()
    return any(marker in lowered for marker in _MISSING_REMOTE_REF_MARKERS)


def _is_chain_runtime_journal_path(rel_path: str) -> bool:
    normalized = rel_path.replace(os.sep, "/")
    return any(fnmatchcase(normalized, pattern) for pattern in _CHAIN_RUNTIME_JOURNAL_PATTERNS)


def _exclude_chain_runtime_journals_from_commit(root: Path, *, writer) -> None:
    staged = _compat().subprocess.run(
        ["git", "diff", "--cached", "--name-only", "-z"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if staged.returncode != 0:
        detail = (staged.stderr or staged.stdout or "").strip()
        raise CliError(
            "git_commit_failed",
            f"git diff --cached --name-only exited {staged.returncode}",
            extra={"stdout": staged.stdout, "stderr": detail},
        )
    paths = [path for path in staged.stdout.split("\0") if path]
    runtime_paths = [path for path in paths if _is_chain_runtime_journal_path(path)]
    if not runtime_paths:
        return
    _compat()._reset_staged_paths(root, [root / path for path in runtime_paths], writer=writer)
    tracked_paths: list[str] = []
    for path in runtime_paths:
        tracked_check = _compat().subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", path],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if tracked_check.returncode == 0:
            tracked_paths.append(path)
    if tracked_paths:
        _compat()._run_command(
            root,
            ["git", "update-index", "--skip-worktree", "--", *tracked_paths],
            writer=writer,
            error_code="git_commit_failed",
        )
    writer(
        "[chain] excluded runtime journal paths from milestone commit: "
        + ", ".join(runtime_paths)
        + "\n"
    )


def _is_missing_remote_ref_result(proc: subprocess.CompletedProcess[str]) -> bool:
    if proc.returncode == 2:
        return True
    detail = _command_detail(proc)
    return proc.returncode == 128 and _is_missing_remote_ref_detail(detail)


def _resolve_commitish(root: Path, commitish: str, *, writer) -> str | None:
    proc = _compat().subprocess.run(
        ["git", "rev-parse", "--verify", f"{commitish}^{{commit}}"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    writer(f"[chain] git rev-parse --verify {commitish}^{{commit}} -> rc={proc.returncode}\n")
    if proc.returncode != 0:
        return None
    sha = proc.stdout.strip()
    return sha or None


def _recover_missing_remote_base_branch(
    root: Path,
    base_branch: str,
    *,
    writer,
    expected_sha: str | None,
) -> str:
    candidates: list[tuple[str, str]] = []
    for ref in (f"refs/heads/{base_branch}", f"refs/remotes/origin/{base_branch}"):
        sha = _resolve_commitish(root, ref, writer=writer)
        if sha is not None:
            candidates.append((ref, sha))

    if expected_sha:
        for ref, sha in candidates:
            if sha == expected_sha:
                source_ref = ref
                recovered_sha = sha
                break
        else:
            recovered_sha = _resolve_commitish(root, expected_sha, writer=writer)
            if recovered_sha is not None:
                source_ref = expected_sha
            else:
                raise CliError(
                    "missing_base_ref",
                    (
                        f"Base branch {base_branch!r} is missing on origin and cannot be "
                        f"restored from local refs at expected sha {expected_sha}."
                    ),
                    extra={
                        "base_branch": base_branch,
                        "last_known_sha": expected_sha,
                        "local_candidates": [{"ref": ref, "sha": sha} for ref, sha in candidates],
                    },
                )
    elif candidates:
        source_ref, recovered_sha = candidates[0]
    else:
        raise CliError(
            "missing_base_ref",
            (
                f"Base branch {base_branch!r} is missing on origin and no local ref is "
                "available to restore it."
            ),
            extra={
                "base_branch": base_branch,
                "last_known_sha": expected_sha,
                "local_candidates": [],
            },
        )

    push_cmd = ["git", "push", "origin", f"{source_ref}:refs/heads/{base_branch}"]
    try:
        proc = _compat().subprocess.run(
            push_cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_PUSH_TIMEOUT_SECONDS,
        )
    except (_compat().subprocess.TimeoutExpired, FileNotFoundError) as exc:
        writer(f"[chain] {' '.join(push_cmd)} failed: {exc}\n")
        raise CliError(
            "missing_base_ref",
            (
                f"Base branch {base_branch!r} is missing on origin and local recovery "
                f"failed while re-pushing {source_ref}: {exc}"
            ),
            extra={
                "base_branch": base_branch,
                "last_known_sha": expected_sha or recovered_sha,
                "source_ref": source_ref,
                "error": str(exc),
            },
        ) from exc
    writer(f"[chain] {' '.join(push_cmd)} -> rc={proc.returncode}\n")
    if proc.returncode != 0:
        detail = _command_detail(proc)
        if detail:
            writer(f"[chain] {' '.join(push_cmd)} output:\n{detail}\n")
        raise CliError(
            "missing_base_ref",
            (
                f"Base branch {base_branch!r} is missing on origin and local recovery "
                f"failed while re-pushing {source_ref}."
            ),
            extra={
                "base_branch": base_branch,
                "last_known_sha": expected_sha or recovered_sha,
                "source_ref": source_ref,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            },
        )
    writer(
        f"[chain] re-pushed missing base branch {base_branch} from local at {recovered_sha}\n"
    )
    return recovered_sha


def _fetch_base_branch(
    root: Path,
    base_branch: str,
    *,
    writer,
    expected_sha: str | None,
    error_code: str,
) -> str:
    ls_remote_cmd = ["git", "ls-remote", "--exit-code", "--heads", "origin", base_branch]
    try:
        remote = _compat().subprocess.run(
            ls_remote_cmd, cwd=str(root), capture_output=True, text=True, check=False, timeout=120
        )
    except (_compat().subprocess.TimeoutExpired, FileNotFoundError) as exc:
        writer(f"[chain] {' '.join(ls_remote_cmd)} failed: {exc}\n")
        raise CliError(
            error_code,
            f"{' '.join(ls_remote_cmd)} failed with {exc}",
            extra={"command": ls_remote_cmd, "error": str(exc)},
        ) from exc
    writer(f"[chain] {' '.join(ls_remote_cmd)} -> rc={remote.returncode}\n")

    recovered_sha: str | None = None
    if remote.returncode == 0 and remote.stdout.strip():
        recovered_sha = remote.stdout.strip().splitlines()[0].split()[0]
    elif _is_missing_remote_ref_result(remote):
        recovered_sha = _recover_missing_remote_base_branch(
            root,
            base_branch,
            writer=writer,
            expected_sha=expected_sha,
        )
    else:
        detail = _command_detail(remote)
        raise CliError(
            error_code,
            f"{' '.join(ls_remote_cmd)} exited {remote.returncode}: {detail}",
            extra={
                "command": ls_remote_cmd,
                "returncode": remote.returncode,
                "stdout": remote.stdout,
                "stderr": remote.stderr,
            },
        )

    fetch_cmd = ["git", "fetch", "origin", base_branch]
    try:
        proc = _compat().subprocess.run(
            fetch_cmd, cwd=str(root), capture_output=True, text=True, check=False, timeout=120
        )
    except (_compat().subprocess.TimeoutExpired, FileNotFoundError) as exc:
        writer(f"[chain] {' '.join(fetch_cmd)} failed: {exc}\n")
        raise CliError(
            error_code,
            (
                f"{' '.join(fetch_cmd)} failed with {exc}. "
                "Resolve the fetch failure or rerun with --no-git-refresh."
            ),
            extra={"command": fetch_cmd, "error": str(exc)},
        ) from exc
    writer(f"[chain] {' '.join(fetch_cmd)} -> rc={proc.returncode}\n")
    if proc.returncode != 0 and _is_missing_remote_ref_result(proc):
        recovered_sha = _recover_missing_remote_base_branch(
            root,
            base_branch,
            writer=writer,
            expected_sha=expected_sha or recovered_sha,
        )
        proc = _compat().subprocess.run(
            fetch_cmd, cwd=str(root), capture_output=True, text=True, check=False, timeout=120
        )
        writer(f"[chain] {' '.join(fetch_cmd)} -> rc={proc.returncode}\n")
    if proc.returncode != 0:
        detail = _command_detail(proc)
        if detail:
            writer(f"[chain] {' '.join(fetch_cmd)} output:\n{detail}\n")
        raise CliError(
            error_code,
            (
                "Chain git refresh failed before milestone initialization: "
                f"{' '.join(fetch_cmd)} exited {proc.returncode}. "
                "Resolve the fetch failure or rerun with --no-git-refresh."
            ),
            extra={
                "command": fetch_cmd,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            },
        )

    remote_sha = _resolve_commitish(root, f"refs/remotes/origin/{base_branch}", writer=writer)
    return remote_sha or recovered_sha or expected_sha or base_branch


def _run_command(
    root: Path,
    cmd: list[str],
    *,
    writer,
    timeout: float = _DEFAULT_COMMAND_TIMEOUT_SECONDS,
    error_code: str = "command_failed",
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a git/gh command and raise CliError with captured output on failure."""
    command_env = env if env is not None else _compat()._command_env(cmd)
    try:
        proc = _compat().subprocess.run(
            cmd,
            cwd=str(root),
            env=command_env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (_compat().subprocess.TimeoutExpired, FileNotFoundError) as exc:
        writer(f"[chain] {' '.join(cmd)} failed: {exc}\n")
        raise CliError(
            error_code,
            f"{' '.join(cmd)} failed with {exc}",
            extra={"command": cmd, "error": str(exc)},
        ) from exc
    if _compat()._should_retry_gh_without_env(cmd, proc):
        writer(
            "[chain] gh auth failed with GH_TOKEN/GITHUB_TOKEN present; "
            "retrying with gh env tokens cleared\n"
        )
        try:
            proc = _compat().subprocess.run(
                cmd,
                cwd=str(root),
                env=_compat()._command_env_without_gh_tokens(cmd),
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except (_compat().subprocess.TimeoutExpired, FileNotFoundError) as exc:
            writer(f"[chain] {' '.join(cmd)} failed: {exc}\n")
            raise CliError(
                error_code,
                f"{' '.join(cmd)} failed with {exc}",
                extra={"command": cmd, "error": str(exc)},
            ) from exc
    writer(f"[chain] {' '.join(cmd)} -> rc={proc.returncode}\n")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        if detail:
            writer(f"[chain] {' '.join(cmd)} output:\n{detail}\n")
        raise CliError(
            error_code,
            f"{' '.join(cmd)} exited {proc.returncode}",
            extra={
                "command": cmd,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            },
        )
    return proc


def _run_git_push_command(
    root: Path,
    cmd: list[str],
    *,
    writer,
    error_code: str = "git_push_failed",
) -> subprocess.CompletedProcess[str]:
    try:
        return _compat()._run_command(
            root,
            cmd,
            writer=writer,
            timeout=_GIT_PUSH_TIMEOUT_SECONDS,
            error_code=error_code,
            env=_git_push_env(cmd),
        )
    except CliError as exc:
        error = exc.extra.get("error") if isinstance(exc.extra, dict) else None
        if (
            isinstance(error, str)
            and "timed out" in error.lower()
            and _recover_timed_out_git_push(root, cmd, writer=writer)
        ):
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if _should_retry_force_with_lease_push(cmd, exc):
            retry_cmd = _force_with_lease_variant(cmd)
            if retry_cmd is not None:
                writer(
                    "[chain] git push rejected after local publish prep; "
                    "retrying with --force-with-lease\n"
                )
                return _compat()._run_command(
                    root,
                    retry_cmd,
                    writer=writer,
                    timeout=_GIT_PUSH_TIMEOUT_SECONDS,
                    error_code=error_code,
                    env=_git_push_env(retry_cmd),
                )
        raise


def _should_retry_force_with_lease_push(cmd: list[str], exc: CliError) -> bool:
    if cmd[:2] != ["git", "push"] or "--force-with-lease" in cmd:
        return False
    if not any(token.startswith("HEAD:") for token in cmd):
        return False
    detail_parts: list[str] = []
    if exc.message:
        detail_parts.append(exc.message)
    if isinstance(exc.extra, dict):
        for key in ("stderr", "stdout", "error"):
            value = exc.extra.get(key)
            if isinstance(value, str) and value:
                detail_parts.append(value)
    detail = "\n".join(detail_parts).lower()
    return any(marker in detail for marker in _NON_FAST_FORWARD_PUSH_MARKERS)


def _force_with_lease_variant(cmd: list[str]) -> list[str] | None:
    if cmd[:2] != ["git", "push"] or "--force-with-lease" in cmd:
        return None
    retry_cmd = list(cmd)
    try:
        origin_index = retry_cmd.index("origin")
    except ValueError:
        return None
    retry_cmd.insert(origin_index, "--force-with-lease")
    return retry_cmd


def _git_push_env(cmd: list[str]) -> dict[str, str] | None:
    if len(cmd) < 2 or cmd[0] != "git" or cmd[1] != "push":
        return None
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    token = env.get("GITHUB_TOKEN") or env.get("GH_TOKEN")
    if token:
        auth = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
        try:
            count = int(env.get("GIT_CONFIG_COUNT") or "0")
        except ValueError:
            count = 0
        env["GIT_CONFIG_COUNT"] = str(count + 1)
        env[f"GIT_CONFIG_KEY_{count}"] = "http.https://github.com/.extraheader"
        env[f"GIT_CONFIG_VALUE_{count}"] = f"AUTHORIZATION: basic {auth}"
    return env

def _recover_timed_out_git_push(root: Path, cmd: list[str], *, writer) -> bool:
    """Treat timed-out pushes as success when origin reached the expected sha."""
    target = _expected_remote_push_target(root, cmd)
    if target is None:
        return False
    branch, expected_sha = target
    deadline = time.monotonic() + _GIT_PUSH_TIMEOUT_RECOVERY_WINDOW_SECONDS
    while time.monotonic() < deadline:
        remote_sha = _remote_branch_head(root, branch)
        if remote_sha == expected_sha:
            writer(
                "[chain] git push timed out locally, but origin/"
                f"{branch} now points at {expected_sha}; continuing\n"
            )
            return True
        time.sleep(2)
    writer(
        "[chain] git push timed out and origin/"
        f"{branch} did not reach expected sha {expected_sha} during recovery window\n"
    )
    return False


def _expected_remote_push_target(root: Path, cmd: list[str]) -> tuple[str, str] | None:
    """Best-effort parse of the remote branch and source sha for a git push."""
    if len(cmd) < 4 or cmd[0] != "git" or cmd[1] != "push":
        return None
    try:
        origin_index = cmd.index("origin")
    except ValueError:
        return None
    refspecs = [token for token in cmd[origin_index + 1 :] if not token.startswith("-")]
    if not refspecs:
        return None
    branch: str | None = None
    source_ref: str | None = None
    first = refspecs[0]
    if ":" in first:
        source_ref, dest_ref = first.split(":", 1)
        if dest_ref.startswith("refs/heads/"):
            branch = dest_ref.removeprefix("refs/heads/")
        else:
            branch = dest_ref
    else:
        branch = first
        source_ref = first
    if not branch or not source_ref:
        return None
    expected_sha = _resolve_commitish(root, source_ref, writer=writer)
    if expected_sha is None and source_ref == "HEAD":
        expected_sha = _resolve_commitish(root, "HEAD", writer=writer)
    if expected_sha is None:
        return None
    return branch, expected_sha


def _should_retry_gh_without_env(cmd: list[str], proc: subprocess.CompletedProcess[str]) -> bool:
    if not cmd or cmd[0] != "gh" or proc.returncode == 0:
        return False
    if "GH_TOKEN" not in os.environ and "GITHUB_TOKEN" not in os.environ:
        return False
    combined = f"{proc.stdout or ''}\n{proc.stderr or ''}".lower()
    return any(
        marker in combined
        for marker in (
            "bad credentials",
            "authentication failed",
            "invalid token",
            "requires authentication",
            "http 401",
            "status code 401",
        )
    )


def _command_env(cmd: list[str]) -> dict[str, str] | None:
    """Return a subprocess env for commands whose auth may need a retry policy.

    ``gh`` gives ``GH_TOKEN``/``GITHUB_TOKEN`` precedence over any logged-in
    keychain auth. The first attempt must still preserve those variables so
    token-only cloud runtimes can authenticate; if the provided token is stale,
    ``_run_command`` retries with those variables cleared.
    """
    if not cmd or cmd[0] != "gh":
        return None
    return os.environ.copy()


def _command_env_without_gh_tokens(cmd: list[str]) -> dict[str, str] | None:
    """Return a ``gh`` env with token overrides cleared for auth fallback."""
    env = _command_env(cmd)
    if env is None:
        return None
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    return env


def _require_git_worktree_root(root: Path, *, operation: str) -> None:
    """Fail before mutating when *root* is not the intended git worktree root."""
    root = Path(root).expanduser().resolve()
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        toplevel = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        raise CliError(
            "chain_git_worktree_required",
            f"{operation} requires a valid git worktree root at {root}: {exc}",
        ) from exc
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        detail = (inside.stderr or inside.stdout or "").strip()
        raise CliError(
            "chain_git_worktree_required",
            f"{operation} requires a valid git worktree root at {root}: {detail}",
        )
    if toplevel.returncode != 0:
        detail = (toplevel.stderr or toplevel.stdout or "").strip()
        raise CliError(
            "chain_git_worktree_required",
            f"{operation} could not resolve git toplevel for {root}: {detail}",
        )
    actual = Path(toplevel.stdout.strip()).resolve()
    if actual != root:
        raise CliError(
            "chain_git_worktree_required",
            f"{operation} must run at the intended git worktree root; got {root}, git toplevel is {actual}",
        )


def _remote_branch_exists(root: Path, branch: str, *, writer) -> bool:
    proc = _compat().subprocess.run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    writer(f"[chain] git ls-remote --heads origin {branch} -> rc={proc.returncode}\n")
    if proc.returncode == 0:
        return True
    if proc.returncode == 2:
        return False
    detail = (proc.stderr or proc.stdout or "").strip()
    raise CliError(
        "git_branch_lookup_failed",
        f"git ls-remote --heads origin {branch} exited {proc.returncode}: {detail}",
        extra={"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr},
    )


def _clear_megaplan_index_safety_bits(root: Path, writer) -> bool:
    """Make tracked .megaplan runtime files resettable before branch checkout."""
    proc = subprocess.run(
        ["git", "ls-files", "-v", "-z", ".megaplan"],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
        check=False,
        timeout=120,
    )
    if proc.returncode != 0 or not proc.stdout:
        return False
    paths: list[str] = []
    for entry in proc.stdout.split("\0"):
        if not entry:
            continue
        if entry.startswith(("S ", "h ")):
            paths.append(entry[2:])
    if not paths:
        return False
    writer("[chain] clearing .megaplan skip-worktree/assume-unchanged bits before cleanup\n")
    for offset in range(0, len(paths), 100):
        batch = paths[offset : offset + 100]
        for flag in ("--no-skip-worktree", "--no-assume-unchanged"):
            _compat()._run_command(
                root,
                ["git", "update-index", flag, "--", *batch],
                writer=writer,
                error_code="git_clean_failed",
            )
    return True


def _clean_worktree_for_chain(root: Path, writer) -> None:
    """Reset tracked changes and remove megaplan-generated untracked files.

    Chain execution re-creates .megaplan metadata each phase; stale working-tree
    changes from a previous run (modified schemas, deleted events.jsonl files,
    telemetry dumps, lock files) would otherwise block branch checkouts.
    """
    _require_git_worktree_root(root, operation="chain worktree cleanup")
    writer("[chain] cleaning worktree for automated branch checkout\n")
    _clear_megaplan_index_safety_bits(root, writer)
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
    expected_base_ref: str | None = None,
) -> str | None:
    """Create or resume the milestone branch and push it to origin.

    When ``from_origin`` is True, a new milestone branch forks from
    ``origin/<base_branch>`` so it includes prior squash-merged milestone PRs.
    Local ``<base_branch>`` can be stale in that workflow because the squash
    merge creates a fresh commit only on the remote base branch.
    """
    if _compat()._remote_branch_exists(root, branch, writer=writer):
        _clean_worktree_for_chain(root, writer)
        _compat()._run_command(root, ["git", "fetch", "origin", branch], writer=writer, error_code="git_branch_failed")
        base_sha: str | None = None
        if from_origin:
            base_sha = _compat()._fetch_base_branch(
                root,
                base_branch,
                writer=writer,
                expected_sha=expected_base_ref,
                error_code="git_branch_failed",
            )
        _compat()._run_command(
            root,
            ["git", "checkout", "-B", branch, f"origin/{branch}"],
            writer=writer,
            error_code="git_branch_failed",
        )
        if from_origin:
            fork_point = f"origin/{base_branch}"
            ancestor = _compat().subprocess.run(
                ["git", "merge-base", "--is-ancestor", fork_point, "HEAD"],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            writer(
                f"[chain] git merge-base --is-ancestor {fork_point} HEAD -> "
                f"rc={ancestor.returncode}\n"
            )
            if ancestor.returncode == 0:
                writer(f"[chain] {branch} already contains {fork_point}\n")
            elif ancestor.returncode == 1:
                rebase = _compat().subprocess.run(
                    ["git", "rebase", fork_point],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=120,
                )
                writer(f"[chain] git rebase {fork_point} -> rc={rebase.returncode}\n")
                if rebase.returncode != 0:
                    detail = (rebase.stderr or rebase.stdout or "").strip()
                    if detail:
                        writer(f"[chain] git rebase {fork_point} output:\n{detail}\n")
                    abort = _compat().subprocess.run(
                        ["git", "rebase", "--abort"],
                        cwd=str(root),
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=120,
                    )
                    writer(f"[chain] git rebase --abort -> rc={abort.returncode}\n")
                    raise CliError(
                        "git_branch_reconcile_failed",
                        (
                            f"Could not rebase existing milestone branch {branch} "
                            f"onto {fork_point}. Resolve the branch conflict before "
                            "relaunching the chain."
                        ),
                        extra={
                            "branch": branch,
                            "fork_point": fork_point,
                            "stdout": rebase.stdout,
                            "stderr": rebase.stderr,
                        },
                    )
                _run_git_push_command(
                    root,
                    ["git", "push", "--no-verify", "--force-with-lease", "origin", branch],
                    writer=writer,
                    error_code="git_push_failed",
                )
            else:
                detail = (ancestor.stderr or ancestor.stdout or "").strip()
                raise CliError(
                    "git_branch_reconcile_failed",
                    (
                        f"Could not compare existing milestone branch {branch} "
                        f"with {fork_point}: {detail}"
                    ),
                    extra={
                        "branch": branch,
                        "fork_point": fork_point,
                        "returncode": ancestor.returncode,
                        "stdout": ancestor.stdout,
                        "stderr": ancestor.stderr,
                    },
                )
        return base_sha
    _clean_worktree_for_chain(root, writer)
    fork_point = base_branch
    base_sha: str | None = None
    if from_origin:
        base_sha = _compat()._fetch_base_branch(
            root,
            base_branch,
            writer=writer,
            expected_sha=expected_base_ref,
            error_code="git_branch_failed",
        )
        fork_point = f"origin/{base_branch}"
        writer(
            f"[chain] forking {branch} from {fork_point} "
            "(authoritative merged history)\n"
        )
    _compat()._run_command(root, ["git", "checkout", "-B", branch, fork_point], writer=writer, error_code="git_branch_failed")
    _run_git_push_command(
        root,
        ["git", "push", "--no-verify", "-u", "origin", branch],
        writer=writer,
        error_code="git_push_failed",
    )
    return base_sha


def _parse_pr_number_from_url(output: str) -> int | None:
    match = re.search(r"/pull/(\d+)", output)
    return int(match.group(1)) if match else None


def _list_open_pr_for_branch(root: Path, branch: str, *, writer) -> dict[str, Any] | None:
    proc = _compat()._run_command(
        root,
        ["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number,state"],
        writer=writer,
        timeout=120,
        error_code="gh_pr_lookup_failed",
    )
    try:
        payload = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise CliError("gh_pr_lookup_failed", f"gh pr list produced non-JSON output: {exc}") from exc
    if isinstance(payload, list) and payload:
        first = payload[0]
        return first if isinstance(first, dict) else None
    return None


def _ensure_milestone_pr(root: Path, milestone: MilestoneSpec, *, base_branch: str, writer) -> int | None:
    """Create or reuse the draft PR for a milestone branch."""
    if not milestone.branch:
        raise CliError("missing_branch", f"milestone {milestone.label!r} has no branch")
    if shutil.which("gh") is None:
        writer(
            "[chain] gh executable not found; continuing with branch commits/pushes "
            f"but skipping PR creation for {milestone.branch}\n"
        )
        return None
    existing = _compat()._list_open_pr_for_branch(root, milestone.branch, writer=writer)
    if existing and isinstance(existing.get("number"), int):
        writer(f"[chain] reusing PR #{existing['number']} for {milestone.branch}\n")
        return int(existing["number"])
    title = f"{milestone.label}: megaplan milestone"
    body = (
        f"Automated megaplan chain milestone `{milestone.label}`.\n\n"
        f"Idea file: `{milestone.idea}`\n"
    )
    try:
        proc = _compat()._run_command(
            root,
            [
                "gh",
                "pr",
                "create",
                "--draft",
                "--base",
                base_branch,
                "--head",
                milestone.branch,
                "--title",
                title,
                "--body",
                body,
            ],
            writer=writer,
            timeout=120,
            error_code="gh_pr_create_failed",
        )
    except CliError as exc:
        extra = exc.extra if isinstance(exc.extra, dict) else {}
        detail = "\n".join(
            str(part).strip()
            for part in (exc.message, extra.get("stderr"), extra.get("stdout"))
            if isinstance(part, str) and part.strip()
        ).lower()
        if "no commits between" in detail:
            writer(
                f"[chain] deferring PR creation for {milestone.branch}: "
                f"no commits are ahead of {base_branch} yet\n"
            )
            return None
        raise
    number = _compat()._parse_pr_number_from_url(proc.stdout.strip())
    if number is not None:
        return number
    created = _compat()._list_open_pr_for_branch(root, milestone.branch, writer=writer)
    if created and isinstance(created.get("number"), int):
        return int(created["number"])
    raise CliError("gh_pr_create_failed", f"could not determine PR number for {milestone.branch}")


def _claimed_paths(root: Path, plan_name: str) -> set[str]:
    plan_dir = root / ".megaplan" / "plans" / plan_name
    claimed_paths: set[str] = set()
    artifacts = [
        plan_dir / "finalize.json",
        plan_dir / "execution.json",
        *sorted(plan_dir.glob("execution_batch_*.json")),
    ]
    for artifact in artifacts:
        if not artifact.exists():
            continue
        try:
            payload = json.loads(artifact.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            _compat()._warn_chain_fallback(
                "M3A_WARN_CHAIN_CLAIMED_PATHS",
                reason="corrupt_json",
                path=artifact,
            )
            continue
        for path in payload.get("files_changed") or []:
            if isinstance(path, str) and path.strip():
                claimed_paths.add(path.strip())
        for task in payload.get("tasks") or payload.get("task_updates") or []:
            if not isinstance(task, dict):
                continue
            for path in task.get("files_changed") or []:
                if isinstance(path, str) and path.strip():
                    claimed_paths.add(path.strip())
    return claimed_paths


def _claimed_nested_repo_paths(root: Path, plan_name: str) -> dict[Path, set[str]]:
    repo_paths: dict[Path, set[str]] = {}
    root_abs = root.resolve()
    for raw_path in _compat()._claimed_paths(root, plan_name):
        path = Path(raw_path)
        if path.is_absolute():
            try:
                path = path.resolve().relative_to(root_abs)
            except (OSError, ValueError):
                _compat()._warn_chain_fallback(
                    "M3A_WARN_NESTED_REPO_PATHS",
                    reason="path_normalization",
                    context={"raw_path": raw_path},
                )
                continue
        cursor = root
        for part in path.parts[:-1]:
            cursor = cursor / part
            if (cursor / ".git").exists():
                rel_to_repo = Path(*path.parts[len(cursor.relative_to(root).parts):])
                repo_paths.setdefault(cursor, set()).add(rel_to_repo.as_posix())
                break
    return repo_paths


def _claimed_root_paths(root: Path, plan_name: str) -> set[str]:
    root_paths: set[str] = set()
    root_abs = root.resolve()
    for raw_path in _compat()._claimed_paths(root, plan_name):
        path = Path(raw_path)
        if path.is_absolute():
            try:
                path = path.resolve().relative_to(root_abs)
            except (OSError, ValueError):
                _compat()._warn_chain_fallback(
                    "M3A_WARN_ROOT_PATHS",
                    reason="path_normalization",
                    context={"raw_path": raw_path},
                )
                continue
        cursor = root
        in_nested_repo = False
        for part in path.parts[:-1]:
            cursor = cursor / part
            if (cursor / ".git").exists():
                in_nested_repo = True
                break
        if not in_nested_repo:
            root_paths.add(path.as_posix())
    return root_paths


def _claimed_nested_repos(root: Path, plan_name: str) -> list[Path]:
    return sorted(_compat()._claimed_nested_repo_paths(root, plan_name), key=lambda repo: repo.as_posix())


def _dirty_nested_repos_from_claimed_paths(root: Path, plan_name: str, *, writer) -> list[str]:
    dirty: list[str] = []
    root_abs = root.resolve()
    for repo, paths in sorted(
        _compat()._claimed_nested_repo_paths(root, plan_name).items(),
        key=lambda item: item[0].as_posix(),
    ):
        proc = _compat().subprocess.run(
            ["git", "status", "--short", "--", *sorted(paths)],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        writer(
            f"[chain] git -C {repo} status --short -- "
            f"{' '.join(sorted(paths))} -> rc={proc.returncode}\n"
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            continue
        try:
            rel = repo.resolve().relative_to(root_abs).as_posix()
        except (OSError, ValueError):
            _compat()._warn_chain_fallback(
                "M3A_WARN_DIRTY_NESTED_REPOS",
                reason="path_normalization",
                context={"repo": repo.as_posix()},
            )
            rel = repo.as_posix()
        dirty.append(rel)
    return dirty


def _dirty_worktree_paths(root: Path) -> list[Path]:
    proc = _compat().subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    paths: list[Path] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        raw_path = line[3:]
        candidates = raw_path.split(" -> ", 1) if " -> " in raw_path else [raw_path]
        for path in candidates:
            path = path.strip()
            if path:
                paths.append(root / path)
    return paths


def _reset_staged_paths(root: Path, paths: list[Path], *, writer) -> None:
    if not paths:
        return
    root_abs = root.resolve()
    rel_paths: list[str] = []
    for path in paths:
        try:
            rel_paths.append(path.resolve().relative_to(root_abs).as_posix())
        except (OSError, ValueError):
            _compat()._warn_chain_fallback(
                "M3A_WARN_RESET_STAGED",
                reason="path_normalization",
                context={"path": path.as_posix()},
            )
            continue
    if rel_paths:
        cmd = ["git", "reset", "--", *sorted(set(rel_paths))]
        proc = _compat().subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        writer(f"[chain] {' '.join(cmd)} -> rc={proc.returncode}\n")


def _git_stdout(root: Path, cmd: list[str], *, error_code: str) -> str:
    proc = _compat().subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if proc.returncode != 0:
        raise CliError(
            error_code,
            f"{' '.join(cmd)} exited {proc.returncode}",
            extra={"command": cmd, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr},
        )
    return proc.stdout.strip()


def _current_git_ref(root: Path) -> tuple[str, str]:
    previous_sha = _git_stdout(root, ["git", "rev-parse", "HEAD"], error_code="git_commit_artifacts_failed")
    proc = _compat().subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    previous_ref = proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else previous_sha
    return previous_ref, previous_sha


def _porcelain_paths(root: Path) -> set[str]:
    proc = _compat().subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if proc.returncode != 0:
        raise CliError(
            "git_commit_artifacts_failed",
            f"git status --porcelain exited {proc.returncode}",
            extra={"stdout": proc.stdout, "stderr": proc.stderr},
        )
    paths: set[str] = set()
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        raw_path = line[3:]
        candidates = raw_path.split(" -> ", 1) if " -> " in raw_path else [raw_path]
        paths.update(path.strip() for path in candidates if path.strip())
    return paths


def _is_internal_dirty_path(path: str) -> bool:
    normalized = path.strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return any(
        normalized == pattern.rstrip("/*") or fnmatchcase(normalized, pattern)
        for pattern in _CHAIN_INTERNAL_DIRTY_PATTERNS
    )


def read_plan_artifact_from_commit(root: Path, commit_sha: str, rel_path: str) -> str | None:
    """Read a file's content from a git commit, returning None only for missing files.

    Uses ``git show <commit_sha>:<rel_path>``. Returns the file content as a
    string when the file exists in the commit. Returns ``None`` when git
    reports the path does not exist in the given tree-ish (e.g. "does not
    exist", "exists on disk, but not in", "bad revision"). Raises
    ``CliError`` for real git failures (non-zero exit for other reasons).
    """
    try:
        proc = subprocess.run(
            ["git", "show", f"{commit_sha}:{rel_path}"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        raise CliError(
            "git_artifact_read_failed",
            f"git show {commit_sha}:{rel_path} failed with {exc}",
        ) from exc

    if proc.returncode == 0:
        return proc.stdout

    # Distinguish "file missing from this commit" (None) from real git errors.
    stderr_lower = (proc.stderr or "").lower()
    if (
        "does not exist" in stderr_lower
        or "exists on disk" in stderr_lower
        or "bad revision" in stderr_lower
    ):
        return None

    raise CliError(
        "git_artifact_read_failed",
        f"git show {commit_sha}:{rel_path} exited {proc.returncode}",
        extra={
            "command": ["git", "show", f"{commit_sha}:{rel_path}"],
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        },
    )


def _artifact_relpath(root: Path, path: Path) -> str:
    candidate = path if path.is_absolute() else root / path
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        raise CliError(
            "invalid_plan_artifact",
            f"plan artifact path is outside the repository: {path}",
        ) from exc


def commit_plan_artifacts_to_base(
    root: Path,
    base_branch: str,
    plan_name: str,
    artifact_paths: list[Path],
    push_enabled: bool,
    dry_run: bool = False,
) -> CommitResult:
    """Force-add explicit plan artifacts on ``base_branch`` and restore caller ref."""
    writer = lambda _msg: None
    previous_ref, previous_sha = _current_git_ref(root)
    audit_notes: list[str] = []
    explicit_paths = [_artifact_relpath(root, Path(path)) for path in artifact_paths]
    explicit_set = set(explicit_paths)
    required_state = f".megaplan/plans/{plan_name}/state.json"
    if required_state not in explicit_set:
        explicit_paths.insert(0, required_state)
        explicit_set.add(required_state)
    required_path = root / required_state
    if not required_path.exists():
        raise CliError(
            "missing_plan_state",
            f"required plan artifact is missing: {required_state}",
        )

    dirty_paths = _porcelain_paths(root)
    unexpected_dirty = sorted(path for path in dirty_paths if path not in explicit_set)
    if unexpected_dirty:
        raise CliError(
            "dirty_worktree",
            "refusing to commit plan artifacts with unrelated dirty worktree paths: "
            + ", ".join(unexpected_dirty[:10]),
            extra={"dirty_paths": unexpected_dirty},
        )

    present_paths: list[str] = []
    for rel in explicit_paths:
        if (root / rel).exists():
            present_paths.append(rel)
        else:
            audit_notes.append(f"optional artifact missing: {rel}")

    if dry_run:
        return CommitResult(
            committed=False,
            pushed=False,
            previous_ref=previous_ref,
            previous_sha=previous_sha,
            base_branch=base_branch,
            audit_notes=audit_notes,
        )

    # Commit the artifacts onto ``base_branch`` purely via git plumbing
    # (write-tree / commit-tree / update-ref). We deliberately never run
    # ``git checkout <base_branch>``: that fails with exit 128 when the base
    # branch is already checked out in a *different* git worktree (git forbids
    # the same branch in two worktrees), and it also needlessly churns the
    # caller's working tree/HEAD. Plumbing leaves HEAD, the working tree, and
    # the live index completely untouched while still landing a real commit on
    # ``refs/heads/<base_branch>`` — and works identically whether or not the
    # base branch is the currently checked-out branch.
    base_ref = f"refs/heads/{base_branch}"
    base_sha = _git_stdout(
        root, ["git", "rev-parse", "--verify", base_ref], error_code="git_commit_artifacts_failed"
    )
    base_tree = _git_stdout(
        root, ["git", "rev-parse", "--verify", f"{base_ref}^{{tree}}"], error_code="git_commit_artifacts_failed"
    )

    # Use a throwaway index seeded from the base tree so we never disturb the
    # caller's live staging area or working tree.
    git_dir = _git_stdout(
        root, ["git", "rev-parse", "--git-dir"], error_code="git_commit_artifacts_failed"
    )
    git_dir_path = Path(git_dir)
    if not git_dir_path.is_absolute():
        git_dir_path = (root / git_dir_path).resolve()
    tmp_index = git_dir_path / f"megaplan-artifact-index-{os.getpid()}"
    index_env = dict(os.environ)
    index_env["GIT_INDEX_FILE"] = str(tmp_index)

    def _run_indexed(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        proc = _compat().subprocess.run(
            cmd,
            cwd=str(root),
            env=index_env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if proc.returncode != 0:
            raise CliError(
                "git_commit_artifacts_failed",
                f"{' '.join(cmd)} exited {proc.returncode}",
                extra={"command": cmd, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr},
            )
        return proc

    try:
        _run_indexed(["git", "read-tree", base_tree])
        if present_paths:
            _run_indexed(["git", "add", "-f", "--", *present_paths])
        new_tree = _run_indexed(["git", "write-tree"]).stdout.strip()
        if new_tree == base_tree:
            audit_notes.append("no staged artifact changes")
            return CommitResult(
                committed=False,
                pushed=False,
                previous_ref=previous_ref,
                previous_sha=previous_sha,
                base_branch=base_branch,
                audit_notes=audit_notes,
            )
        commit_sha = _run_indexed(
            [
                "git",
                "commit-tree",
                new_tree,
                "-p",
                base_sha,
                "-m",
                f"megaplan: persist plan artifacts for {plan_name}",
            ]
        ).stdout.strip()
        # Atomically advance the base branch ref, asserting it still points at
        # the sha we built on top of (guards against a concurrent advance).
        _run_indexed(["git", "update-ref", base_ref, commit_sha, base_sha])
        # When HEAD is on the base branch (the common case), advancing the ref
        # alone leaves the *live* index pointing at the old tree, so the freshly
        # committed artifacts would show up as a staged deletion in
        # ``git status``. Refresh the live index for those paths so the working
        # tree reads clean against the new commit. (When HEAD is on another
        # branch — including a sibling worktree — the live index is unrelated to
        # base and must not be touched.)
        if previous_ref == base_branch and present_paths:
            _run_command(
                root,
                ["git", "update-index", "--add", "--", *present_paths],
                writer=writer,
                error_code="git_commit_artifacts_failed",
            )
        pushed = False
        if push_enabled:
            _run_command(
                root,
                ["git", "push", "--no-verify", "origin", base_branch],
                writer=writer,
                error_code="git_push_failed",
            )
            pushed = True
        return CommitResult(
            committed=True,
            pushed=pushed,
            commit_sha=commit_sha,
            previous_ref=previous_ref,
            previous_sha=previous_sha,
            base_branch=base_branch,
            audit_notes=audit_notes,
        )
    finally:
        try:
            tmp_index.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Git helpers for sync state classification
# ---------------------------------------------------------------------------


def _branch_head(root: Path) -> str | None:
    """Return the sha of HEAD or *None* if the command fails (e.g. no repo)."""
    try:
        proc = _compat().subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if proc.returncode == 0:
            return proc.stdout.strip() or None
    except (_compat().subprocess.TimeoutExpired, FileNotFoundError, OSError):
        _compat()._warn_chain_fallback(
            "M3A_WARN_BRANCH_HEAD",
            reason="git_error",
            context={"root": root.as_posix()},
        )
    return None


def _remote_branch_head(root: Path, branch: str) -> str | None:
    """Return the sha of ``origin/<branch>`` or *None* if unresolvable."""
    try:
        proc = _compat().subprocess.run(
            ["git", "ls-remote", "--heads", "origin", branch],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if proc.returncode == 0:
            line = proc.stdout.strip().splitlines()
            if line:
                return line[0].split()[0] if line[0] else None
    except (_compat().subprocess.TimeoutExpired, FileNotFoundError, OSError):
        _compat()._warn_chain_fallback(
            "M3A_WARN_REMOTE_BRANCH_HEAD",
            reason="git_error",
            context={"root": root.as_posix(), "branch": branch},
        )
    return None


def _is_worktree_dirty(root: Path) -> bool:
    """True when ``git status --porcelain`` reports unstaged/uncommitted changes."""
    try:
        proc = _compat().subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        return bool(proc.stdout.strip())
    except (_compat().subprocess.TimeoutExpired, FileNotFoundError, OSError):
        _compat()._warn_chain_fallback(
            "M3A_WARN_WORKTREE_DIRTY",
            reason="git_error",
            context={"root": root.as_posix()},
        )
        return False


def _classify_sync_state(
    *,
    branch_head: str | None,
    pr_head: str | None,
    last_pushed_commit: str | None,
    dirty: bool,
) -> str:
    """Classify sync state independently from merge_policy.

    Returns one of ``SYNC_CLEAN``, ``SYNC_STALE``, ``SYNC_DIRTY`` (from
    ``megaplan.types``).
    """
    from arnold_pipelines.megaplan.types import SYNC_CLEAN, SYNC_DIRTY, SYNC_STALE

    if dirty:
        return SYNC_DIRTY
    if branch_head and last_pushed_commit and branch_head != last_pushed_commit:
        return SYNC_DIRTY  # diverged from what was last pushed
    if pr_head and last_pushed_commit and pr_head != last_pushed_commit:
        return SYNC_STALE  # remote/PR head moved past our last push
    if branch_head and pr_head and branch_head != pr_head:
        return SYNC_STALE  # local branch behind PR head
    if branch_head and last_pushed_commit and branch_head == last_pushed_commit:
        return SYNC_CLEAN
    # Not enough data to classify confidently.
    return SYNC_CLEAN


def _capture_sync_state(
    root: Path,
    spec_path: Path,
    *,
    branch: str | None = None,
    pr_number: int | None = None,
    extra_repos: list[str] | None = None,
) -> None:
    """Update the persisted chain state with fresh sync fields.

    Reads live git data, classifies sync, and saves to the chain state.
    Does nothing if ``root`` is not a git repo (all helpers return None).

    When *extra_repos* is provided each path is probed for branch head,
    dirty flag, and sync state.  Results are stored in
    ``ChainState.extra_repo_sync``.  Extra repo probing is best-effort and
    never destructive (no push, reset, or delete).
    """
    state = _compat().load_chain_state(spec_path)
    branch_head = _compat()._branch_head(root)
    pr_head: str | None = None
    if branch:
        pr_head = _compat()._remote_branch_head(root, branch)
    dirty = _compat()._is_worktree_dirty(root)
    state.branch_head = branch_head
    state.pr_head = pr_head
    state.dirty_flag = dirty
    state.last_pushed_commit = branch_head  # live rev-parse — best-effort push tracking
    state.sync_state = _compat()._classify_sync_state(
        branch_head=branch_head,
        pr_head=pr_head,
        last_pushed_commit=state.last_pushed_commit,
        dirty=dirty,
    )

    # Best-effort extra repo probing (non-destructive).
    if extra_repos:
        extra_sync: list[dict[str, Any]] = []
        for repo_path_str in extra_repos:
            try:
                repo_path = Path(repo_path_str)
                if not repo_path.exists():
                    extra_sync.append(
                        {"path": repo_path_str, "status": "missing"}
                    )
                    continue
                er_head = _compat()._branch_head(repo_path)
                if er_head is None:
                    extra_sync.append(
                        {"path": repo_path_str, "status": "not_a_git_repo"}
                    )
                    continue
                er_dirty = _compat()._is_worktree_dirty(repo_path)
                er_sync = _compat()._classify_sync_state(
                    branch_head=er_head,
                    pr_head=None,
                    last_pushed_commit=er_head,
                    dirty=er_dirty,
                )
                extra_sync.append(
                    {
                        "path": repo_path_str,
                        "branch_head": er_head,
                        "dirty": er_dirty,
                        "sync_state": er_sync,
                    }
                )
            except Exception:
                extra_sync.append(
                    {"path": repo_path_str, "status": "error"}
                )
        state.extra_repo_sync = extra_sync

    _compat().save_chain_state(spec_path, state)


def _commit_phase(
    root: Path,
    plan: str,
    phase: str,
    *,
    writer,
    preexisting_dirty_paths: list[Path] | None = None,
) -> str | None:
    """Stage and commit the current milestone diff onto the CURRENT branch (HEAD).

    This is the commit half of milestone integration, deliberately split from the
    push so it can be used in two situations:

    * **PR/push runs** — HEAD is on the milestone branch; the caller
      (:func:`_commit_and_push_phase`) commits here and then pushes the branch.
    * **``--no-push`` runs** — there is no milestone branch and HEAD stays on the
      base branch, so committing here lands the milestone's work *directly on the
      base branch* and advances HEAD. That is what lets the next milestone (whose
      base is ``_current_head_sha``) build on this one's integrated tree instead
      of all milestones forking the same frozen base while their output piles up
      as uncommitted WIP.

    It never runs ``git checkout`` and never pushes. Returns the new commit sha,
    or ``None`` when there was nothing to commit (and ``phase != "init"``).
    """
    _require_git_worktree_root(root, operation=f"chain phase commit ({phase})")
    dirty_nested = _compat()._dirty_nested_repos_from_claimed_paths(root, plan, writer=writer)
    if dirty_nested:
        raise CliError(
            "nested_repo_changes_uncommitted",
            "Plan claimed changes in nested git repositories that top-level chain commits "
            "cannot publish: "
            + ", ".join(dirty_nested)
            + ". Commit and push those nested repositories separately, or run the plan with "
            "a project_dir rooted at the repository being changed.",
        )
    _compat()._run_command(root, ["git", "add", "-A"], writer=writer, error_code="git_commit_failed")
    _exclude_chain_runtime_journals_from_commit(root, writer=writer)
    claimed_root_paths = _compat()._claimed_root_paths(root, plan)
    claimed_nested_repo_roots: set[str] = set()
    root_abs = root.resolve()
    for repo in _compat()._claimed_nested_repos(root, plan):
        try:
            claimed_nested_repo_roots.add(repo.resolve().relative_to(root_abs).as_posix())
        except (OSError, ValueError):
            _compat()._warn_chain_fallback(
                "M3A_WARN_COMMIT_PUSH_PATH",
                reason="path_normalization",
                context={"repo": repo.as_posix()},
            )
            continue
    preexisting_unclaimed: list[Path] = []
    for path in preexisting_dirty_paths or []:
        try:
            rel = path.resolve().relative_to(root_abs).as_posix()
        except (OSError, ValueError):
            _compat()._warn_chain_fallback(
                "M3A_WARN_COMMIT_PUSH_PATH2",
                reason="path_normalization",
                context={"path": path.as_posix()},
            )
            continue
        if rel not in claimed_root_paths and rel not in claimed_nested_repo_roots:
            preexisting_unclaimed.append(path)
    # Only unstage *tracked* preexisting-unclaimed paths. Untracked files that
    # happen to share a path with preexisting dirt are typically new work
    # produced by the current plan; resetting them would drop them from the
    # milestone commit. Tracked preexisting changes are left unstaged so they
    # do not pollute the milestone diff.
    tracked_preexisting_unclaimed: list[Path] = []
    for path in preexisting_unclaimed:
        try:
            rel = path.resolve().relative_to(root_abs).as_posix()
        except (OSError, ValueError):
            continue
        tracked_check = _compat().subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", rel],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if tracked_check.returncode == 0:
            tracked_preexisting_unclaimed.append(path)
    _compat()._reset_staged_paths(root, tracked_preexisting_unclaimed, writer=writer)
    staged = _compat().subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if staged.returncode != 0 and staged.returncode != 1:
        raise CliError(
            "git_commit_failed",
            f"git diff --cached --quiet exited {staged.returncode}",
            extra={"stdout": staged.stdout, "stderr": staged.stderr},
        )
    nothing_staged = staged.returncode == 0
    message = f"megaplan: {plan} {phase}"
    # --no-verify: a programmatic milestone commit must not run the repo's
    # interactive pre-commit hooks. Those hooks are authored for human commits
    # and routinely fail for reasons unrelated to whether the milestone's code
    # should land — e.g. a worktree that shares the umbrella .git's hooks but has
    # intentionally removed the package the hook drives (the arnold migration
    # worktree tombstones `megaplan`, so the megaplan-regen pre-commit hook errors
    # and would block every milestone commit). The chain owns its own staging and
    # verification; hook side effects here are noise that turns a healthy
    # milestone into a hard chain stall.
    commit_argv = ["git", "commit", "--no-verify", "-m", message]
    if nothing_staged:
        if phase != "init":
            writer(f"[chain] no changes to commit after {phase}\n")
            return None
        # Anchor the milestone branch with an empty init commit so a draft PR
        # can be opened before any phase produces a real diff.
        commit_argv.insert(2, "--allow-empty")
    _compat()._run_command(root, commit_argv, writer=writer, error_code="git_commit_failed")
    return _git_stdout(root, ["git", "rev-parse", "HEAD"], error_code="git_commit_failed")


def _commit_and_push_phase(
    root: Path,
    branch: str,
    plan: str,
    phase: str,
    *,
    writer,
    preexisting_dirty_paths: list[Path] | None = None,
) -> None:
    """Commit any current diff and push the milestone branch."""
    committed_sha = _commit_phase(
        root, plan, phase, writer=writer, preexisting_dirty_paths=preexisting_dirty_paths
    )
    # Execution/output aggregation can append plan state (events.jsonl, lock
    # files) and preexisting-unclaimed untracked files can survive the first
    # commit. Stage and commit any remaining tracked or untracked changes so
    # the subsequent rebase/push sees a clean worktree and no milestone file
    # is left unpublished.
    # The cleanup commit intentionally does NOT reset preexisting-unclaimed
    # paths, so that plan-state files (chain-state.json, events.jsonl, etc.)
    # that were modified after the first commit are themselves committed and
    # the worktree is clean before rebase/push.
    cleanup_commit_sha = _commit_phase(
        root,
        plan,
        f"{phase}-cleanup",
        writer=writer,
        preexisting_dirty_paths=[],
    )
    published_sha = cleanup_commit_sha or committed_sha
    if published_sha is None:
        # Nothing committed (and not an init anchor) — nothing to publish.
        return
    # Reconcile with origin so a resumed chain whose local branch diverged
    # from the remote milestone branch (e.g. reset to base) can still push.
    fetch = _compat().subprocess.run(
        ["git", "fetch", "origin", branch],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    writer(f"[chain] git fetch origin {branch} -> rc={fetch.returncode}\n")
    if fetch.returncode == 0:
        rebase = _compat().subprocess.run(
            ["git", "rebase", f"origin/{branch}"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        writer(f"[chain] git rebase origin/{branch} -> rc={rebase.returncode}\n")
        if rebase.returncode != 0:
            detail = (rebase.stderr or rebase.stdout or "").strip()
            writer(
                f"[chain] rebase failed; aborting and falling back to force push"
                f"{(': ' + detail) if detail else ''}\n"
            )
            abort = _compat().subprocess.run(
                ["git", "rebase", "--abort"],
                cwd=str(root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            writer(f"[chain] git rebase --abort -> rc={abort.returncode}\n")
            if abort.returncode != 0:
                abort_detail = (abort.stderr or abort.stdout or "").strip()
                writer(
                    "[chain] warning: git rebase --abort failed during fallback; "
                    "continuing to force-with-lease push"
                    f"{(': ' + abort_detail) if abort_detail else ''}\n"
                )
            _compat()._run_command(
                root,
                ["git", "push", "--no-verify", "--force-with-lease", "origin", f"HEAD:{branch}"],
                writer=writer,
                error_code="git_push_failed",
            )
            return
    _run_git_push_command(
        root,
        ["git", "push", "--no-verify", "origin", f"HEAD:{branch}"],
        writer=writer,
        error_code="git_push_failed",
    )


def _mark_pr_ready(root: Path, pr_number: int, *, writer) -> None:
    _compat()._run_command(root, ["gh", "pr", "ready", str(pr_number)], writer=writer, error_code="gh_pr_ready_failed")


def _enable_auto_merge(root: Path, pr_number: int, *, writer) -> str:
    status = _compat().subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if status.returncode != 0:
        raise CliError(
            "git_status_failed",
            "git status --porcelain -uall failed before PR merge",
            extra={"stdout": status.stdout, "stderr": status.stderr},
    )
    dirty_lines = [
        line
        for line in status.stdout.splitlines()
        if line.strip()
        and not _is_internal_dirty_path(line[3:] if len(line) > 3 else line)
    ]
    if dirty_lines:
        sample = ", ".join(
            line[3:] if len(line) > 3 else line for line in dirty_lines[:8]
        )
        raise CliError(
            "dirty_worktree_before_pr_merge",
            "refusing to merge PR with a dirty worktree; publish or clean local "
            f"changes first: {sample}",
            extra={"dirty_status": status.stdout},
        )
    try:
        _compat()._run_command(
            root,
            [
                "gh",
                "pr",
                "merge",
                str(pr_number),
                "--auto",
                "--squash",
                "--delete-branch",
            ],
            writer=writer,
            timeout=120,
            error_code="gh_pr_merge_failed",
        )
        return (
            "merged"
            if _compat()._pr_state(root, pr_number, writer=writer) == "merged"
            else "open"
        )
    except CliError as exc:
        combined = (
            f"{exc.message} {exc.extra.get('stdout', '')} "
            f"{exc.extra.get('stderr', '')}"
        )
        if "already checked out" in combined:
            # --delete-branch needs a local branch switch, which fails when the
            # chain runs in a git worktree whose base branch is checked out
            # elsewhere. Retry without local branch deletion (remote branch is
            # cleaned up by GitHub's delete-on-merge or left for manual GC).
            writer(
                "[chain] --delete-branch impossible from worktree; retrying "
                "auto-merge without it\n"
            )
            _compat()._run_command(
                root,
                ["gh", "pr", "merge", str(pr_number), "--auto", "--squash"],
                writer=writer,
                timeout=120,
                error_code="gh_pr_merge_failed",
            )
            return (
                "merged"
                if _compat()._pr_state(root, pr_number, writer=writer) == "merged"
                else "open"
            )
        if "Auto merge is not allowed" not in combined:
            raise
        writer("[chain] auto-merge unavailable; falling back to immediate squash merge\n")
    _compat()._run_command(
        root,
        ["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch"],
        writer=writer,
        timeout=120,
        error_code="gh_pr_merge_failed",
    )
    return "merged"


def _is_transient_gh_error(exc: CliError) -> bool:
    combined = " ".join(
        str(part or "")
        for part in (
            exc.message,
            exc.extra.get("stdout", ""),
            exc.extra.get("stderr", ""),
        )
    ).lower()
    return any(pattern in combined for pattern in _compat().GH_TRANSIENT_ERROR_PATTERNS)


def _pr_state(root: Path, pr_number: int, *, writer) -> str:
    for attempt in range(1, _compat().GH_PR_STATE_ATTEMPTS + 1):
        try:
            proc = _compat()._run_command(
                root,
                ["gh", "pr", "view", str(pr_number), "--json", "state,mergedAt"],
                writer=writer,
                timeout=120,
                error_code="gh_pr_view_failed",
            )
            break
        except CliError as exc:
            if attempt >= _compat().GH_PR_STATE_ATTEMPTS or not _compat()._is_transient_gh_error(exc):
                raise
            writer(
                "[chain] transient gh pr view failure; "
                f"retrying ({attempt}/{_compat().GH_PR_STATE_ATTEMPTS})\n"
            )
            _compat().time.sleep(min(2 * attempt, 5))
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise CliError("gh_pr_view_failed", f"gh pr view produced non-JSON output: {exc}") from exc
    value = payload.get("state")
    if payload.get("mergedAt"):
        return "merged"
    if not isinstance(value, str):
        raise CliError("gh_pr_view_failed", "gh pr view did not return a string state")
    return value.lower()


def _reconcile_terminal_pr_state(
    root: Path,
    spec_path: Path,
    state: ChainState,
    *,
    writer,
) -> ChainState:
    """Refresh live PR state even when the chain index is already terminal."""
    pr_number = state.pr_number
    completed_entry: dict[str, Any] | None = None
    if pr_number is None:
        for entry in reversed(state.completed):
            if isinstance(entry, dict) and isinstance(entry.get("pr_number"), int):
                completed_entry = entry
                pr_number = int(entry["pr_number"])
                break
    if pr_number is None:
        return state

    live_state = _compat()._pr_state(root, pr_number, writer=writer)
    reconciled = live_state
    if state.pr_number is not None:
        state.pr_state = reconciled
    if completed_entry is not None:
        completed_entry["pr_state"] = reconciled
    _compat().save_chain_state(spec_path, state)
    return state
