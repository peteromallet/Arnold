"""Chain driver — run a pipeline of milestone plans with state kept in megaplan.

This replaces ad-hoc bash orchestration (`chain.sh`). A YAML spec declares an
optional seed plan and an ordered list of milestones; each milestone is
initialized from an idea file, then driven to `done` via the same auto-loop
entry point used by `megaplan auto`.

Plan state stays in megaplan. Bash is no longer responsible for polling or
deciding the next step — only for process/container liveness.

Spec format (YAML)::

    seed:
      plan: milestone-m0-from-docs-state-20260415-0217
    milestones:
      - label: m1
        idea: /workspace/ideas/M1-foundation-store.txt
        branch: megaplan/m1-foundation-store   # optional, currently informational
      - label: m1a
        idea: /workspace/ideas/M1a-settings-store.txt
    on_failure:
      abort: stop_chain          # stop_chain | skip_milestone | retry_milestone
    on_escalate:
      abort: stop_chain          # stop_chain | skip_milestone | retry_milestone

Progress is persisted under ``.megaplan/chains/`` so a relaunched process can
resume where the previous run left off without dirtying milestone branches.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "megaplan chain requires PyYAML. Install with `pip install pyyaml`."
    ) from exc

from megaplan.auto import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_PHASE_TIMEOUT_SECONDS,
    DEFAULT_POLL_SLEEP_SECONDS,
    DEFAULT_STALL_THRESHOLD,
    DEFAULT_STATUS_TIMEOUT_SECONDS,
    DriverOutcome,
    ESCALATE_ACTIONS,
    drive as auto_drive,
)
from megaplan._core import resolve_plan_dir
from megaplan.types import CliError, STATE_AWAITING_PR_MERGE


VALID_FAILURE_ACTIONS = ("stop_chain", "skip_milestone", "retry_milestone")
VALID_MERGE_POLICIES = ("auto", "review")
TERMINAL_SKIP_STATES = ("done", "aborted", "failed")


@dataclass
class MilestoneSpec:
    label: str
    idea: str
    branch: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any], index: int) -> "MilestoneSpec":
        if not isinstance(raw, dict):
            raise CliError("invalid_spec", f"milestones[{index}] must be a mapping")
        label = raw.get("label")
        idea = raw.get("idea")
        if not isinstance(label, str) or not label.strip():
            raise CliError("invalid_spec", f"milestones[{index}].label is required")
        if not isinstance(idea, str) or not idea.strip():
            raise CliError("invalid_spec", f"milestones[{index}].idea is required")
        branch = raw.get("branch")
        if branch is not None and not isinstance(branch, str):
            raise CliError("invalid_spec", f"milestones[{index}].branch must be a string")
        return cls(label=label, idea=idea, branch=branch)


@dataclass
class ChainSpec:
    milestones: list[MilestoneSpec]
    seed_plan: str | None = None
    on_failure: str = "stop_chain"
    on_escalate: str = "stop_chain"
    merge_policy: str = "auto"
    # Driver knobs propagated into auto.drive for each plan.
    stall_threshold: int = DEFAULT_STALL_THRESHOLD
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    poll_sleep: float = DEFAULT_POLL_SLEEP_SECONDS
    phase_timeout: float = DEFAULT_PHASE_TIMEOUT_SECONDS
    status_timeout: float = DEFAULT_STATUS_TIMEOUT_SECONDS
    escalate_action: str = "force-proceed"  # passed to auto.drive on_escalate
    robustness: str = "standard"
    auto_approve: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChainSpec":
        if not isinstance(raw, dict):
            raise CliError("invalid_spec", "chain spec must be a YAML mapping")
        milestones_raw = raw.get("milestones") or []
        if not isinstance(milestones_raw, list):
            raise CliError("invalid_spec", "`milestones` must be a list")
        milestones = [MilestoneSpec.from_dict(m, i) for i, m in enumerate(milestones_raw)]
        seed_raw = raw.get("seed") or {}
        seed_plan: str | None = None
        if seed_raw:
            if not isinstance(seed_raw, dict):
                raise CliError("invalid_spec", "`seed` must be a mapping")
            seed_plan = seed_raw.get("plan")
            if seed_plan is not None and not isinstance(seed_plan, str):
                raise CliError("invalid_spec", "`seed.plan` must be a string")
            if isinstance(seed_plan, str) and not seed_plan.strip():
                seed_plan = None

        def _action(section: str, default: str) -> str:
            block = raw.get(section) or {}
            if not isinstance(block, dict):
                raise CliError("invalid_spec", f"`{section}` must be a mapping")
            value = block.get("abort", default)
            if value not in VALID_FAILURE_ACTIONS:
                raise CliError(
                    "invalid_spec",
                    f"{section}.abort must be one of {VALID_FAILURE_ACTIONS}; got {value!r}",
                )
            return value

        on_failure = _action("on_failure", "stop_chain")
        on_escalate = _action("on_escalate", "stop_chain")
        merge_policy = raw.get("merge_policy", "auto")
        if merge_policy not in VALID_MERGE_POLICIES:
            raise CliError(
                "invalid_spec",
                f"merge_policy must be one of {VALID_MERGE_POLICIES}; got {merge_policy!r}",
            )

        driver_raw = raw.get("driver") or {}
        if not isinstance(driver_raw, dict):
            raise CliError("invalid_spec", "`driver` must be a mapping")
        stall = int(driver_raw.get("stall_threshold", DEFAULT_STALL_THRESHOLD))
        max_iter = int(driver_raw.get("max_iterations", DEFAULT_MAX_ITERATIONS))
        poll = float(driver_raw.get("poll_sleep", DEFAULT_POLL_SLEEP_SECONDS))
        phase_to = float(driver_raw.get("phase_timeout", DEFAULT_PHASE_TIMEOUT_SECONDS))
        status_to = float(driver_raw.get("status_timeout", DEFAULT_STATUS_TIMEOUT_SECONDS))
        esc = driver_raw.get("on_escalate", "force-proceed")
        if esc not in ESCALATE_ACTIONS:
            raise CliError(
                "invalid_spec",
                f"driver.on_escalate must be one of {ESCALATE_ACTIONS}; got {esc!r}",
            )
        robustness = driver_raw.get("robustness", "standard")
        if not isinstance(robustness, str):
            raise CliError("invalid_spec", "driver.robustness must be a string")
        auto_approve = bool(driver_raw.get("auto_approve", True))

        return cls(
            milestones=milestones,
            seed_plan=seed_plan,
            on_failure=on_failure,
            on_escalate=on_escalate,
            merge_policy=merge_policy,
            stall_threshold=stall,
            max_iterations=max_iter,
            poll_sleep=poll,
            phase_timeout=phase_to,
            status_timeout=status_to,
            escalate_action=esc,
            robustness=robustness,
            auto_approve=auto_approve,
        )


@dataclass
class ChainState:
    """Persisted progress for a chain run.

    ``current_milestone_index`` is -1 before any milestone starts (seed phase),
    0 for the first milestone, etc. ``current_plan_name`` is the plan currently
    being driven. ``last_state`` is the terminal driver status string from the
    most recently completed plan.
    """

    current_milestone_index: int = -1
    current_plan_name: str | None = None
    last_state: str | None = None
    pr_number: int | None = None
    pr_state: str | None = None
    completed: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_milestone_index": self.current_milestone_index,
            "current_plan_name": self.current_plan_name,
            "last_state": self.last_state,
            "pr_number": self.pr_number,
            "pr_state": self.pr_state,
            "completed": list(self.completed),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChainState":
        return cls(
            current_milestone_index=int(raw.get("current_milestone_index", -1)),
            current_plan_name=raw.get("current_plan_name"),
            last_state=raw.get("last_state"),
            pr_number=int(raw["pr_number"]) if raw.get("pr_number") is not None else None,
            pr_state=raw.get("pr_state"),
            completed=list(raw.get("completed") or []),
        )


def _state_path_for(spec_path: Path) -> Path:
    spec_resolved = spec_path.resolve()
    digest = hashlib.sha1(str(spec_resolved).encode("utf-8")).hexdigest()[:12]
    return spec_resolved.parent / ".megaplan" / "chains" / f"{spec_resolved.stem}-{digest}.json"


def _legacy_state_path_for(spec_path: Path) -> Path:
    return spec_path.with_name("chain_state.json")


def load_spec(spec_path: Path) -> ChainSpec:
    if not spec_path.exists():
        raise CliError("invalid_spec", f"spec file not found: {spec_path}")
    try:
        raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CliError("invalid_spec", f"YAML parse error: {exc}") from exc
    return ChainSpec.from_dict(raw or {})


def load_chain_state(spec_path: Path) -> ChainState:
    state_path = _state_path_for(spec_path)
    if not state_path.exists():
        legacy_path = _legacy_state_path_for(spec_path)
        if legacy_path.exists():
            state_path = legacy_path
    if not state_path.exists():
        return ChainState()
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError("invalid_chain_state", f"chain_state.json is invalid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise CliError("invalid_chain_state", "chain_state.json must be an object")
    return ChainState.from_dict(raw)


def save_chain_state(spec_path: Path, state: ChainState) -> None:
    state_path = _state_path_for(spec_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")
    tmp.replace(state_path)


def validate_paths(spec: ChainSpec, root: Path) -> None:
    """Check that all idea files exist and the seed plan (if any) is on disk."""
    for m in spec.milestones:
        idea_path = Path(m.idea)
        if not idea_path.exists():
            raise CliError(
                "missing_idea_file",
                f"milestone {m.label!r} idea file not found: {m.idea}",
            )
    if spec.seed_plan:
        try:
            resolve_plan_dir(root, spec.seed_plan)
        except CliError as exc:
            raise CliError(
                "missing_seed_plan",
                f"seed plan {spec.seed_plan!r} not found under {root}: {exc.message}",
            ) from exc


# ---------------------------------------------------------------------------
# Driving
# ---------------------------------------------------------------------------


def _plan_state(root: Path, plan: str, *, timeout: float) -> str:
    """Read just the `state` field of a plan via `megaplan status`.

    Returns "missing" if the plan is not found. Used to decide whether to skip
    driving (plan already terminal) vs. run the full auto loop.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "megaplan", "status", "--plan", plan],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "unknown"
    if proc.returncode != 0:
        return "missing"
    try:
        return json.loads(proc.stdout).get("state", "unknown")
    except json.JSONDecodeError:
        return "unknown"


def _refresh_main(root: Path, *, writer, no_git_refresh: bool = False) -> None:
    """Run `git fetch + checkout main + pull`, aborting on refresh failures.

    When ``no_git_refresh`` is True, this is a no-op (still logs that it was
    skipped). This guard exists so developer checkouts running ``megaplan
    chain`` do not get their currently checked-out branch stomped by an
    automatic ``git checkout main``.
    """
    if no_git_refresh:
        writer("[chain] skipping git refresh (--no-git-refresh)\n")
        return
    for cmd in (
        ["git", "fetch", "origin", "main"],
        ["git", "checkout", "main"],
        ["git", "pull", "--ff-only", "origin", "main"],
    ):
        try:
            proc = subprocess.run(
                cmd, cwd=str(root), capture_output=True, text=True, check=False, timeout=120
            )
            writer(f"[chain] {' '.join(cmd)} -> rc={proc.returncode}\n")
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "").strip()
                if detail:
                    writer(f"[chain] {' '.join(cmd)} output:\n{detail}\n")
                raise CliError(
                    "git_refresh_failed",
                    (
                        "Chain git refresh failed before milestone initialization: "
                        f"{' '.join(cmd)} exited {proc.returncode}. "
                        "Resolve the checkout or rerun with --no-git-refresh for a developer workspace."
                    ),
                    extra={
                        "command": cmd,
                        "returncode": proc.returncode,
                        "stdout": proc.stdout,
                        "stderr": proc.stderr,
                    },
                )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            writer(f"[chain] {' '.join(cmd)} failed: {exc}\n")
            raise CliError(
                "git_refresh_failed",
                (
                    "Chain git refresh failed before milestone initialization: "
                    f"{' '.join(cmd)} failed with {exc}. "
                    "Resolve the checkout or rerun with --no-git-refresh for a developer workspace."
                ),
                extra={"command": cmd, "error": str(exc)},
            ) from exc


def _run_command(
    root: Path,
    cmd: list[str],
    *,
    writer,
    timeout: float = 120,
    error_code: str = "command_failed",
) -> subprocess.CompletedProcess[str]:
    """Run a git/gh command and raise CliError with captured output on failure."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
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


def _remote_branch_exists(root: Path, branch: str, *, writer) -> bool:
    proc = subprocess.run(
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


def _checkout_milestone_branch(root: Path, branch: str, *, writer) -> None:
    """Create or resume the milestone branch and push it to origin."""
    if _remote_branch_exists(root, branch, writer=writer):
        _run_command(root, ["git", "fetch", "origin", branch], writer=writer, error_code="git_branch_failed")
        _run_command(
            root,
            ["git", "checkout", "-B", branch, f"origin/{branch}"],
            writer=writer,
            error_code="git_branch_failed",
        )
        return
    _run_command(root, ["git", "checkout", "-B", branch, "main"], writer=writer, error_code="git_branch_failed")
    _run_command(root, ["git", "push", "-u", "origin", branch], writer=writer, error_code="git_push_failed")


def _parse_pr_number_from_url(output: str) -> int | None:
    match = re.search(r"/pull/(\d+)", output)
    return int(match.group(1)) if match else None


def _list_open_pr_for_branch(root: Path, branch: str, *, writer) -> dict[str, Any] | None:
    proc = _run_command(
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


def _ensure_milestone_pr(root: Path, milestone: MilestoneSpec, *, writer) -> int | None:
    """Create or reuse the draft PR for a milestone branch."""
    if not milestone.branch:
        raise CliError("missing_branch", f"milestone {milestone.label!r} has no branch")
    if shutil.which("gh") is None:
        writer(
            "[chain] gh executable not found; continuing with branch commits/pushes "
            f"but skipping PR creation for {milestone.branch}\n"
        )
        return None
    existing = _list_open_pr_for_branch(root, milestone.branch, writer=writer)
    if existing and isinstance(existing.get("number"), int):
        writer(f"[chain] reusing PR #{existing['number']} for {milestone.branch}\n")
        return int(existing["number"])
    title = f"{milestone.label}: megaplan milestone"
    body = (
        f"Automated megaplan chain milestone `{milestone.label}`.\n\n"
        f"Idea file: `{milestone.idea}`\n"
    )
    proc = _run_command(
        root,
        [
            "gh",
            "pr",
            "create",
            "--draft",
            "--base",
            "main",
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
    number = _parse_pr_number_from_url(proc.stdout.strip())
    if number is not None:
        return number
    created = _list_open_pr_for_branch(root, milestone.branch, writer=writer)
    if created and isinstance(created.get("number"), int):
        return int(created["number"])
    raise CliError("gh_pr_create_failed", f"could not determine PR number for {milestone.branch}")


def _commit_and_push_phase(root: Path, branch: str, plan: str, phase: str, *, writer) -> None:
    """Commit any current diff and push the milestone branch."""
    _run_command(root, ["git", "add", "-A"], writer=writer, error_code="git_commit_failed")
    staged = subprocess.run(
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
    commit_argv = ["git", "commit", "-m", message]
    if nothing_staged:
        if phase != "init":
            writer(f"[chain] no changes to commit after {phase}\n")
            return
        # Anchor the milestone branch with an empty init commit so a draft PR
        # can be opened before any phase produces a real diff.
        commit_argv.insert(2, "--allow-empty")
    _run_command(root, commit_argv, writer=writer, error_code="git_commit_failed")
    _run_command(root, ["git", "push", "origin", branch], writer=writer, error_code="git_push_failed")


def _mark_pr_ready(root: Path, pr_number: int, *, writer) -> None:
    _run_command(root, ["gh", "pr", "ready", str(pr_number)], writer=writer, error_code="gh_pr_ready_failed")


def _enable_auto_merge(root: Path, pr_number: int, *, writer) -> None:
    _run_command(
        root,
        ["gh", "pr", "merge", str(pr_number), "--auto", "--squash", "--delete-branch"],
        writer=writer,
        timeout=120,
        error_code="gh_pr_merge_failed",
    )


def _pr_state(root: Path, pr_number: int, *, writer) -> str:
    proc = _run_command(
        root,
        ["gh", "pr", "view", str(pr_number), "--json", "state"],
        writer=writer,
        timeout=120,
        error_code="gh_pr_view_failed",
    )
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise CliError("gh_pr_view_failed", f"gh pr view produced non-JSON output: {exc}") from exc
    value = payload.get("state")
    if not isinstance(value, str):
        raise CliError("gh_pr_view_failed", "gh pr view did not return a string state")
    return value.lower()


def _init_plan(
    root: Path,
    idea_path: str,
    *,
    robustness: str,
    auto_approve: bool,
    writer,
) -> str:
    """Run `megaplan init --idea-file ...` and return the plan name."""
    args = [sys.executable, "-m", "megaplan", "init", "--project-dir", str(root)]
    if auto_approve:
        args.append("--auto-approve")
    args.extend(["--robustness", robustness, "--idea-file", str(idea_path)])
    writer(f"[chain] initializing plan from {idea_path}\n")
    proc = subprocess.run(
        args, cwd=str(root), capture_output=True, text=True, check=False, timeout=300
    )
    if proc.returncode != 0:
        raise CliError(
            "init_failed",
            f"megaplan init failed (rc={proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()[-400:]}",
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CliError("init_failed", f"megaplan init produced non-JSON output: {exc}") from exc
    plan = payload.get("plan")
    if not isinstance(plan, str) or not plan:
        raise CliError("init_failed", "megaplan init did not return a plan name")
    writer(f"[chain] launched plan={plan}\n")
    return plan


def _drive_plan(
    root: Path,
    plan: str,
    spec: ChainSpec,
    *,
    on_phase_complete: Callable[[str, int, str, str], None] | None = None,
    writer,
) -> DriverOutcome:
    """Run the auto driver for a single plan."""
    return auto_drive(
        plan,
        cwd=root,
        stall_threshold=spec.stall_threshold,
        max_iterations=spec.max_iterations,
        on_escalate=spec.escalate_action,
        poll_sleep=spec.poll_sleep,
        phase_timeout=spec.phase_timeout,
        status_timeout=spec.status_timeout,
        on_phase_complete=on_phase_complete,
        writer=writer,
    )


def _handle_outcome(
    outcome: DriverOutcome,
    *,
    spec: ChainSpec,
    writer,
) -> str:
    """Decide the next action given a DriverOutcome.

    Returns one of: "advance" (move to next milestone), "stop" (chain halts),
    "retry" (re-run the same milestone), "skip" (advance without waiting).
    """
    status = outcome.status
    if status == "done":
        return "advance"
    if status == "aborted":
        # auto.drive returns aborted both for user aborts and on-escalate=abort.
        # Treat according to on_escalate policy so the chain can skip if asked.
        writer(f"[chain] plan {outcome.plan} ended aborted\n")
        policy = spec.on_escalate
    elif status == "escalated":
        writer(f"[chain] plan {outcome.plan} escalated — applying on_escalate policy\n")
        policy = spec.on_escalate
    else:
        # failed, stalled, cap → treat as failure
        writer(f"[chain] plan {outcome.plan} ended {status}: {outcome.reason}\n")
        policy = spec.on_failure
    if policy == "stop_chain":
        return "stop"
    if policy == "skip_milestone":
        return "skip"
    if policy == "retry_milestone":
        return "retry"
    return "stop"


def run_chain(
    spec_path: Path,
    root: Path,
    *,
    writer=sys.stdout.write,
    no_git_refresh: bool = False,
    no_push: bool = False,
) -> dict[str, Any]:
    """Drive the full chain. Returns a structured JSON-serializable result."""
    spec = load_spec(spec_path)
    validate_paths(spec, root)
    state = load_chain_state(spec_path)
    push_enabled = not no_push and os.environ.get("MEGAPLAN_CHAIN_NO_PUSH") not in {"1", "true", "TRUE", "yes", "YES"}

    events: list[dict[str, Any]] = []

    def log(msg: str, **fields: Any) -> None:
        events.append({"msg": msg, **fields})
        writer(f"[chain] {msg}\n")

    # ---- Seed phase ----
    if spec.seed_plan and state.current_milestone_index < 0:
        seed_state = _plan_state(root, spec.seed_plan, timeout=spec.status_timeout)
        log(f"seed plan {spec.seed_plan} state={seed_state}")
        if seed_state not in TERMINAL_SKIP_STATES:
            state.current_plan_name = spec.seed_plan
            save_chain_state(spec_path, state)
            outcome = _drive_plan(root, spec.seed_plan, spec, writer=writer)
            state.last_state = outcome.status
            save_chain_state(spec_path, state)
            decision = _handle_outcome(outcome, spec=spec, writer=writer)
            if decision == "stop":
                return _result("stopped", state, events, reason=f"seed plan {outcome.status}")
            if decision == "retry":
                # Recursive retry kept simple: re-drive seed once.
                outcome = _drive_plan(root, spec.seed_plan, spec, writer=writer)
                state.last_state = outcome.status
                save_chain_state(spec_path, state)
                if outcome.status != "done":
                    return _result("stopped", state, events, reason="seed retry failed")
            # skip / advance both proceed to milestones
        state.completed.append(
            {"label": "seed", "plan": spec.seed_plan, "status": state.last_state or seed_state}
        )
        state.current_milestone_index = 0
        state.current_plan_name = None
        save_chain_state(spec_path, state)

    elif state.current_milestone_index < 0:
        state.current_milestone_index = 0
        save_chain_state(spec_path, state)

    # ---- Milestones ----
    idx = max(state.current_milestone_index, 0)
    while idx < len(spec.milestones):
        milestone = spec.milestones[idx]
        log(f"milestone {milestone.label} starting")
        use_pr = push_enabled and bool(milestone.branch)

        if state.last_state == STATE_AWAITING_PR_MERGE and state.current_milestone_index == idx:
            if not use_pr or state.pr_number is None:
                log(f"review merge wait for {milestone.label} has no PR context; advancing")
                state.pr_state = None
            else:
                pr_state = _pr_state(root, state.pr_number, writer=writer)
                state.pr_state = "merged" if pr_state == "merged" else "awaiting_merge"
                save_chain_state(spec_path, state)
                if pr_state != "merged":
                    log(f"PR #{state.pr_number} state={pr_state}; awaiting merge")
                    return _result(
                        STATE_AWAITING_PR_MERGE,
                        state,
                        events,
                        reason=f"milestone {milestone.label} PR #{state.pr_number} is {pr_state}",
                    )
                log(f"PR #{state.pr_number} merged; advancing past {milestone.label}")
            state.completed.append(
                {
                    "label": milestone.label,
                    "plan": state.current_plan_name,
                    "status": "done",
                    "pr_number": state.pr_number,
                    "pr_state": "merged" if state.pr_number is not None else None,
                }
            )
            idx += 1
            state.current_milestone_index = idx
            state.current_plan_name = None
            state.last_state = "done"
            state.pr_number = None
            state.pr_state = None
            save_chain_state(spec_path, state)
            continue

        # Resume mid-milestone if we already have a plan name recorded.
        if (
            state.current_plan_name
            and state.current_milestone_index == idx
            and _plan_state(root, state.current_plan_name, timeout=spec.status_timeout)
            not in ("missing",)
        ):
            plan_name = state.current_plan_name
            log(f"resuming existing plan {plan_name} for {milestone.label}")
            if use_pr and state.pr_number is None:
                _checkout_milestone_branch(root, milestone.branch or "", writer=writer)
                state.pr_number = _ensure_milestone_pr(root, milestone, writer=writer)
                state.pr_state = "open"
                save_chain_state(spec_path, state)
        else:
            _refresh_main(root, writer=writer, no_git_refresh=no_git_refresh)
            if use_pr:
                _checkout_milestone_branch(root, milestone.branch or "", writer=writer)
            plan_name = _init_plan(
                root,
                milestone.idea,
                robustness=spec.robustness,
                auto_approve=spec.auto_approve,
                writer=writer,
            )
            state.current_milestone_index = idx
            state.current_plan_name = plan_name
            save_chain_state(spec_path, state)
            if use_pr:
                _commit_and_push_phase(root, milestone.branch or "", plan_name, "init", writer=writer)
                state.pr_number = _ensure_milestone_pr(root, milestone, writer=writer)
                state.pr_state = "open"
                save_chain_state(spec_path, state)

        def phase_callback(phase: str, _code: int, _out: str, _err: str) -> None:
            if use_pr and milestone.branch:
                _commit_and_push_phase(root, milestone.branch, plan_name, phase, writer=writer)

        outcome = _drive_plan(
            root,
            plan_name,
            spec,
            on_phase_complete=phase_callback if use_pr else None,
            writer=writer,
        )
        state.last_state = outcome.status
        save_chain_state(spec_path, state)
        decision = _handle_outcome(outcome, spec=spec, writer=writer)

        if decision == "stop":
            return _result(
                "stopped",
                state,
                events,
                reason=f"milestone {milestone.label} ended {outcome.status}",
            )
        if decision == "retry":
            log(f"retrying milestone {milestone.label}")
            state.current_plan_name = None  # force re-init next loop
            state.pr_number = None
            state.pr_state = None
            save_chain_state(spec_path, state)
            continue
        if decision == "advance" and use_pr and state.pr_number is not None:
            _commit_and_push_phase(root, milestone.branch or "", plan_name, "done", writer=writer)
            _mark_pr_ready(root, state.pr_number, writer=writer)
            if spec.merge_policy == "review":
                state.last_state = STATE_AWAITING_PR_MERGE
                state.pr_state = "awaiting_merge"
                save_chain_state(spec_path, state)
                log(f"PR #{state.pr_number} ready; awaiting manual merge")
                return _result(
                    STATE_AWAITING_PR_MERGE,
                    state,
                    events,
                    reason=f"milestone {milestone.label} PR #{state.pr_number} awaiting merge",
                )
            _enable_auto_merge(root, state.pr_number, writer=writer)
            state.pr_state = "open"
            save_chain_state(spec_path, state)
        # advance or skip
        state.completed.append(
            {
                "label": milestone.label,
                "plan": plan_name,
                "status": outcome.status,
                "pr_number": state.pr_number,
                "pr_state": state.pr_state,
            }
        )
        idx += 1
        state.current_milestone_index = idx
        state.current_plan_name = None
        state.pr_number = None
        state.pr_state = None
        save_chain_state(spec_path, state)

    log("all milestones complete")
    return _result("done", state, events)


def _result(
    status: str, state: ChainState, events: list[dict[str, Any]], *, reason: str = ""
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "chain_state": state.to_dict(),
        "events": events,
    }


def format_chain_status(spec: ChainSpec, state: ChainState) -> dict[str, Any]:
    completed_labels = {
        entry.get("label")
        for entry in state.completed
        if isinstance(entry, dict) and isinstance(entry.get("label"), str)
    }
    current_milestone: dict[str, Any] | None = None
    if 0 <= state.current_milestone_index < len(spec.milestones):
        milestone = spec.milestones[state.current_milestone_index]
        current_milestone = {
            "label": milestone.label,
            "index": state.current_milestone_index,
        }
        if milestone.branch:
            current_milestone["branch"] = milestone.branch

    per_milestone: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for index, milestone in enumerate(spec.milestones):
        if milestone.label in completed_labels:
            status = "completed"
        elif index == state.current_milestone_index and state.current_plan_name:
            status = "in_progress"
        else:
            status = "pending"
        entry = {"label": milestone.label, "index": index, "status": status}
        per_milestone.append(entry)
        if status == "completed":
            completed.append({"label": milestone.label, "index": index})
        else:
            remaining.append({"label": milestone.label, "index": index})

    summary = {
        "current_milestone": current_milestone,
        "completed": completed,
        "remaining": remaining,
        "per_milestone": per_milestone,
        "seed_plan": spec.seed_plan,
        "current_plan_name": state.current_plan_name,
        "last_state": state.last_state,
    }
    if state.pr_number is not None:
        summary["pr_number"] = state.pr_number
        summary["pr_state"] = state.pr_state
    return summary


def _write_chain_status_pretty(summary: dict[str, Any], *, writer) -> None:
    current = summary.get("current_milestone")
    current_label = "none"
    if isinstance(current, dict):
        current_label = f"{current['label']} (index {current['index']})"
    completed = summary.get("completed") or []
    remaining = summary.get("remaining") or []
    completed_labels = ", ".join(item["label"] for item in completed) if completed else "none"
    remaining_labels = ", ".join(item["label"] for item in remaining) if remaining else "none"
    writer(f"Current milestone: {current_label}\n")
    writer(f"Completed: {completed_labels}\n")
    writer(f"Remaining: {remaining_labels}\n")
    if summary.get("seed_plan"):
        writer(f"Seed plan: {summary['seed_plan']}\n")
    if summary.get("current_plan_name"):
        writer(f"Current plan: {summary['current_plan_name']}\n")
    if summary.get("last_state"):
        writer(f"Last state: {summary['last_state']}\n")
    if summary.get("pr_number"):
        writer(f"Current PR: #{summary['pr_number']} ({summary.get('pr_state') or 'unknown'})\n")
    writer("Per-milestone:\n")
    for item in summary.get("per_milestone") or []:
        writer(f"  - [{item['status']}] {item['label']} (index {item['index']})\n")


# ---------------------------------------------------------------------------
# CLI plumbing
# ---------------------------------------------------------------------------


def build_chain_parser(subparsers: Any) -> None:
    chain_parser = subparsers.add_parser(
        "chain",
        help="Drive a pipeline of milestone plans described by a YAML spec",
    )
    chain_sub = chain_parser.add_subparsers(dest="chain_action")
    # No action == run. `start` is the explicit spelling, kept in sync with the
    # backcompat top-level alias.
    chain_parser.add_argument(
        "--spec",
        required=False,
        help="Path to the chain spec YAML (required at top-level or on subcommands)",
    )
    chain_parser.add_argument(
        "--no-git-refresh",
        action="store_true",
        help=(
            "Skip the automatic `git checkout main && git pull` that runs "
            "before each milestone. Use this on developer checkouts where "
            "you do not want chain to stomp on the currently checked-out "
            "branch. Default: refresh enabled (preserves CI/orchestrator "
            "behavior)."
        ),
    )
    chain_parser.add_argument(
        "--no-push",
        action="store_true",
        help=(
            "Disable milestone branch creation, PR creation, commits, and pushes. "
            "Also enabled by MEGAPLAN_CHAIN_NO_PUSH=1; intended for local/no-network tests."
        ),
    )

    start_parser = chain_sub.add_parser("start", help="Drive a chain spec")
    start_parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")
    start_parser.add_argument(
        "--no-git-refresh",
        action="store_true",
        help=(
            "Skip the automatic `git checkout main && git pull` that runs "
            "before each milestone."
        ),
    )
    start_parser.add_argument(
        "--no-push",
        action="store_true",
        help="Disable branch/PR/push lifecycle for no-network runs.",
    )

    status_parser = chain_sub.add_parser(
        "status", help="Show persisted chain progress without driving"
    )
    status_parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")


def run_chain_cli(root: Path, args: argparse.Namespace, *, writer=sys.stderr.write) -> int:
    action = getattr(args, "chain_action", None)
    spec_arg = getattr(args, "spec", None)
    if not spec_arg:
        sys.stderr.write("megaplan chain: --spec is required\n")
        return 64
    spec_path = Path(spec_arg).expanduser().resolve()

    if action == "status":
        try:
            spec = load_spec(spec_path)
            chain_state = load_chain_state(spec_path)
        except CliError as exc:
            return _emit_error(exc)
        summary = format_chain_status(spec, chain_state)
        _write_chain_status_pretty(summary, writer=writer)
        payload = {
            "success": True,
            "spec": str(spec_path),
            "milestone_count": len(spec.milestones),
            "seed_plan": spec.seed_plan,
            "chain_state": chain_state.to_dict(),
            "summary": summary,
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0

    if action not in (None, "start"):
        return _emit_error(CliError("invalid_args", f"Unknown chain action: {action}"))

    no_git_refresh = bool(getattr(args, "no_git_refresh", False))
    no_push = bool(getattr(args, "no_push", False))
    try:
        result = run_chain(spec_path, root, no_git_refresh=no_git_refresh, no_push=no_push)
    except CliError as exc:
        return _emit_error(exc)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    if result["status"] == "done":
        return 0
    return 1


def _emit_error(error: CliError) -> int:
    payload = {"success": False, "error": error.code, "message": error.message}
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return error.exit_code or 1
