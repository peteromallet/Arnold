"""Chain driver — run a pipeline of milestone plans with state kept in megaplan.

This replaces ad-hoc bash orchestration (`chain.sh`). A YAML spec declares an
optional seed plan and an ordered list of milestones; each milestone is
initialized from an idea file, then driven to `done` via the same auto-loop
entry point used by `megaplan auto`.

Plan state stays in megaplan. Bash is no longer responsible for polling or
deciding the next step — only for process/container liveness.

Spec format (YAML)::

    base_branch: main
    seed:
      plan: milestone-m0-from-docs-state-20260415-0217
    milestones:
      - label: m1
        idea: /workspace/ideas/M1-foundation-store.txt
        branch: megaplan/m1-foundation-store   # optional, currently informational
        profile: thoughtful                     # optional init rubric knobs
        robustness: standard
        vendor: claude
        depth: high
        critic: kimi
        with_prep: true
        with_feedback: true
        prep_direction: |               # optional steering for the prep phase
          focus on the worker shutdown path and how cancel signals propagate
          to inflight tasks; skip CLI plumbing.
        deepseek_provider: fireworks
      - label: m1a
        idea: /workspace/ideas/M1a-settings-store.txt
    on_failure:
      abort: stop_chain          # stop_chain | skip_milestone | retry_milestone
    on_escalate:
      abort: stop_chain          # stop_chain | skip_milestone | retry_milestone

Progress is persisted under ``.megaplan/plans/.chains/`` so a relaunched
process can resume where the previous run left off without dirtying milestone
branches.
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
from megaplan._core.user_config import VALID_VENDORS
from megaplan.profiles import (
    VALID_CRITIC_CHOICES,
    VALID_DEEPSEEK_PROVIDER_CHOICES,
    VALID_DEPTH_CHOICES,
)
from megaplan.types import CliError, STATE_AWAITING_PR_MERGE, STATE_EXECUTED


VALID_FAILURE_ACTIONS = ("stop_chain", "skip_milestone", "retry_milestone")
VALID_MERGE_POLICIES = ("auto", "review")
TERMINAL_SKIP_STATES = ("done", "aborted", "failed")
GH_TRANSIENT_ERROR_PATTERNS = (
    " 500",
    " 502",
    " 503",
    " 504",
    "deadline exceeded",
    "http 500",
    "http 502",
    "http 503",
    "http 504",
    "gateway timeout",
    "i/o timeout",
    "net/http:",
    "service unavailable",
    "bad gateway",
    "graphql: timeout",
    "graphql timeout",
    "temporary failure",
    "temporarily unavailable",
    "timed out",
    "try again",
)
GH_PR_STATE_ATTEMPTS = 3
BLOCKED_EXECUTE_OUTCOME_STATUSES = {"blocked", "worker_blocked"}


def _optional_choice(
    raw: dict[str, Any],
    key: str,
    choices: tuple[str, ...],
    *,
    index: int,
) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CliError("invalid_spec", f"milestones[{index}].{key} must be a string")
    if value not in choices:
        raise CliError(
            "invalid_spec",
            f"milestones[{index}].{key} must be one of {choices}; got {value!r}",
        )
    return value


def _optional_bool(raw: dict[str, Any], key: str, *, index: int) -> bool:
    value = raw.get(key, False)
    if not isinstance(value, bool):
        raise CliError("invalid_spec", f"milestones[{index}].{key} must be a boolean")
    return value


@dataclass
class MilestoneSpec:
    label: str
    idea: str
    branch: str | None = None
    profile: str | None = None
    robustness: str | None = None
    vendor: str | None = None
    depth: str | None = None
    critic: str | None = None
    deepseek_provider: str | None = None
    with_prep: bool = False
    with_feedback: bool = False
    prep_direction: str | None = None
    phase_model: list[str] = field(default_factory=list)
    bakeoff: dict[str, Any] | None = None
    notes: str | None = None

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
        profile = raw.get("profile")
        if profile is not None and not isinstance(profile, str):
            raise CliError("invalid_spec", f"milestones[{index}].profile must be a string")
        robustness = raw.get("robustness")
        if robustness is not None and not isinstance(robustness, str):
            raise CliError("invalid_spec", f"milestones[{index}].robustness must be a string")
        vendor = _optional_choice(
            raw,
            "vendor",
            VALID_VENDORS,
            index=index,
        )
        depth = _optional_choice(
            raw,
            "depth",
            VALID_DEPTH_CHOICES,
            index=index,
        )
        critic = _optional_choice(
            raw,
            "critic",
            VALID_CRITIC_CHOICES,
            index=index,
        )
        deepseek_provider = _optional_choice(
            raw,
            "deepseek_provider",
            VALID_DEEPSEEK_PROVIDER_CHOICES,
            index=index,
        )
        with_prep = _optional_bool(raw, "with_prep", index=index)
        with_feedback = _optional_bool(raw, "with_feedback", index=index)
        prep_direction_raw = raw.get("prep_direction")
        if prep_direction_raw is None:
            prep_direction = None
        elif isinstance(prep_direction_raw, str):
            stripped = prep_direction_raw.strip()
            if not stripped:
                raise CliError(
                    "invalid_spec",
                    f"milestones[{index}].prep_direction must be non-empty when provided",
                )
            prep_direction = stripped
        else:
            raise CliError(
                "invalid_spec",
                f"milestones[{index}].prep_direction must be a string",
            )
        phase_model_raw = raw.get("phase_model") or []
        if isinstance(phase_model_raw, str):
            phase_model = [phase_model_raw]
        elif isinstance(phase_model_raw, list) and all(isinstance(item, str) for item in phase_model_raw):
            phase_model = list(phase_model_raw)
        else:
            raise CliError("invalid_spec", f"milestones[{index}].phase_model must be a string or list of strings")
        bakeoff = raw.get("bakeoff")
        if bakeoff is not None and not isinstance(bakeoff, dict):
            raise CliError("invalid_spec", f"milestones[{index}].bakeoff must be a mapping")
        notes = raw.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise CliError("invalid_spec", f"milestones[{index}].notes must be a string")
        return cls(
            label=label,
            idea=idea,
            branch=branch,
            profile=profile,
            robustness=robustness,
            vendor=vendor,
            depth=depth,
            critic=critic,
            deepseek_provider=deepseek_provider,
            with_prep=with_prep,
            with_feedback=with_feedback,
            prep_direction=prep_direction,
            phase_model=phase_model,
            bakeoff=bakeoff,
            notes=notes,
        )


@dataclass
class ChainSpec:
    milestones: list[MilestoneSpec]
    seed_plan: str | None = None
    base_branch: str = "main"
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
        base_branch = raw.get("base_branch", "main")
        if not isinstance(base_branch, str) or not base_branch.strip():
            raise CliError("invalid_spec", "`base_branch` must be a non-empty string")
        base_branch = base_branch.strip()
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
            base_branch=base_branch,
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
    return spec_resolved.parent / ".megaplan" / "plans" / ".chains" / f"{spec_resolved.stem}-{digest}.json"


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


def _refresh_base_branch(
    root: Path,
    base_branch: str,
    *,
    writer,
    no_git_refresh: bool = False,
) -> None:
    """Run `git fetch + checkout <base_branch> + pull`, aborting on refresh failures.

    When ``no_git_refresh`` is True, this is a no-op (still logs that it was
    skipped). This guard exists so developer checkouts running ``megaplan
    chain`` do not get their currently checked-out branch stomped by an
    automatic base-branch checkout.
    """
    if no_git_refresh:
        writer("[chain] skipping git refresh (--no-git-refresh)\n")
        return
    for cmd in (
        ["git", "fetch", "origin", base_branch],
        ["git", "checkout", base_branch],
        ["git", "pull", "--ff-only", "origin", base_branch],
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


def _checkout_milestone_branch(root: Path, branch: str, *, base_branch: str, writer) -> None:
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
    _run_command(root, ["git", "checkout", "-B", branch, base_branch], writer=writer, error_code="git_branch_failed")
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
    number = _parse_pr_number_from_url(proc.stdout.strip())
    if number is not None:
        return number
    created = _list_open_pr_for_branch(root, milestone.branch, writer=writer)
    if created and isinstance(created.get("number"), int):
        return int(created["number"])
    raise CliError("gh_pr_create_failed", f"could not determine PR number for {milestone.branch}")


def _claimed_paths(root: Path, plan_name: str) -> set[str]:
    plan_dir = root / ".megaplan" / "plans" / plan_name
    claimed_paths: set[str] = set()
    for artifact_name in ("finalize.json", "execution.json"):
        artifact = plan_dir / artifact_name
        if not artifact.exists():
            continue
        try:
            payload = json.loads(artifact.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
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
    for raw_path in _claimed_paths(root, plan_name):
        path = Path(raw_path)
        if path.is_absolute():
            try:
                path = path.resolve().relative_to(root_abs)
            except (OSError, ValueError):
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
    for raw_path in _claimed_paths(root, plan_name):
        path = Path(raw_path)
        if path.is_absolute():
            try:
                path = path.resolve().relative_to(root_abs)
            except (OSError, ValueError):
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
    return sorted(_claimed_nested_repo_paths(root, plan_name), key=lambda repo: repo.as_posix())


def _dirty_nested_repos_from_claimed_paths(root: Path, plan_name: str, *, writer) -> list[str]:
    dirty: list[str] = []
    root_abs = root.resolve()
    for repo, paths in sorted(
        _claimed_nested_repo_paths(root, plan_name).items(),
        key=lambda item: item[0].as_posix(),
    ):
        proc = subprocess.run(
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
            rel = repo.as_posix()
        dirty.append(rel)
    return dirty


def _dirty_worktree_paths(root: Path) -> list[Path]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
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
            continue
    if rel_paths:
        cmd = ["git", "reset", "--", *sorted(set(rel_paths))]
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        writer(f"[chain] {' '.join(cmd)} -> rc={proc.returncode}\n")


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
    dirty_nested = _dirty_nested_repos_from_claimed_paths(root, plan, writer=writer)
    if dirty_nested:
        raise CliError(
            "nested_repo_changes_uncommitted",
            "Plan claimed changes in nested git repositories that top-level chain commits "
            "cannot publish: "
            + ", ".join(dirty_nested)
            + ". Commit and push those nested repositories separately, or run the plan with "
            "a project_dir rooted at the repository being changed.",
        )
    _run_command(root, ["git", "add", "-A"], writer=writer, error_code="git_commit_failed")
    claimed_root_paths = _claimed_root_paths(root, plan)
    claimed_nested_repo_roots: set[str] = set()
    root_abs = root.resolve()
    for repo in _claimed_nested_repos(root, plan):
        try:
            claimed_nested_repo_roots.add(repo.resolve().relative_to(root_abs).as_posix())
        except (OSError, ValueError):
            continue
    preexisting_unclaimed: list[Path] = []
    for path in preexisting_dirty_paths or []:
        try:
            rel = path.resolve().relative_to(root_abs).as_posix()
        except (OSError, ValueError):
            continue
        if rel not in claimed_root_paths and rel not in claimed_nested_repo_roots:
            preexisting_unclaimed.append(path)
    _reset_staged_paths(root, preexisting_unclaimed, writer=writer)
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


def _enable_auto_merge(root: Path, pr_number: int, *, writer) -> str:
    try:
        _run_command(
            root,
            ["gh", "pr", "merge", str(pr_number), "--auto", "--squash", "--delete-branch"],
            writer=writer,
            timeout=120,
            error_code="gh_pr_merge_failed",
        )
        return "merged" if _pr_state(root, pr_number, writer=writer) == "merged" else "open"
    except CliError as exc:
        combined = f"{exc.message} {exc.extra.get('stdout', '')} {exc.extra.get('stderr', '')}"
        if "Auto merge is not allowed" not in combined:
            raise
        writer("[chain] auto-merge unavailable; falling back to immediate squash merge\n")
    _run_command(
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
    return any(pattern in combined for pattern in GH_TRANSIENT_ERROR_PATTERNS)


def _pr_state(root: Path, pr_number: int, *, writer) -> str:
    for attempt in range(1, GH_PR_STATE_ATTEMPTS + 1):
        try:
            proc = _run_command(
                root,
                ["gh", "pr", "view", str(pr_number), "--json", "state"],
                writer=writer,
                timeout=120,
                error_code="gh_pr_view_failed",
            )
            break
        except CliError as exc:
            if attempt >= GH_PR_STATE_ATTEMPTS or not _is_transient_gh_error(exc):
                raise
            writer(
                "[chain] transient gh pr view failure; "
                f"retrying ({attempt}/{GH_PR_STATE_ATTEMPTS})\n"
            )
            time.sleep(min(2 * attempt, 5))
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
    profile: str | None = None,
    vendor: str | None = None,
    depth: str | None = None,
    critic: str | None = None,
    deepseek_provider: str | None = None,
    with_prep: bool = False,
    with_feedback: bool = False,
    prep_direction: str | None = None,
    phase_model: list[str] | None = None,
    writer,
) -> str:
    """Run `megaplan init --idea-file ...` and return the plan name."""
    args = [sys.executable, "-m", "megaplan", "init", "--project-dir", str(root)]
    if auto_approve:
        args.append("--auto-approve")
    args.extend(["--robustness", robustness])
    if profile:
        args.extend(["--profile", profile])
    if vendor:
        args.extend(["--vendor", vendor])
    if depth:
        args.extend(["--depth", depth])
    if critic:
        args.extend(["--critic", critic])
    if deepseek_provider:
        args.extend(["--deepseek-provider", deepseek_provider])
    if with_prep:
        args.append("--with-prep")
    if with_feedback:
        args.append("--with-feedback")
    if prep_direction:
        args.extend(["--prep-direction", prep_direction])
    for override in phase_model or []:
        args.extend(["--phase-model", override])
    args.extend(["--idea-file", str(idea_path)])
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


def _execution_batch_sort_key(path: Path) -> tuple[int, str]:
    match = re.fullmatch(r"execution_batch_(\d+)\.json", path.name)
    if match:
        return (int(match.group(1)), path.name)
    return (-1, path.name)


def _latest_execute_result(plan_dir: Path) -> str | None:
    try:
        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    history = state.get("history")
    if not isinstance(history, list):
        return None
    for entry in reversed(history):
        if isinstance(entry, dict) and entry.get("step") == "execute":
            result = entry.get("result")
            return result if isinstance(result, str) else None
    return None


def _latest_execution_batch_all_tasks_done(plan_dir: Path) -> tuple[bool, str]:
    batches = sorted(
        plan_dir.glob("execution_batch_*.json"),
        key=_execution_batch_sort_key,
    )
    if not batches:
        return False, "no execution_batch_*.json artifact found"
    latest = batches[-1]
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return False, f"{latest.name} could not be read: {error}"
    if not isinstance(payload, dict):
        return False, f"{latest.name} payload is not an object"

    task_records: list[dict[str, Any]] = []
    for key in ("task_updates", "tasks"):
        raw_records = payload.get(key)
        if isinstance(raw_records, list):
            task_records.extend(item for item in raw_records if isinstance(item, dict))
    if not task_records:
        return False, f"{latest.name} has no task records"

    incomplete: list[str] = []
    for task in task_records:
        if task.get("status") == "done":
            continue
        task_id = task.get("task_id") or task.get("id") or "?"
        incomplete.append(f"{task_id}={task.get('status')!r}")
    if incomplete:
        return False, f"{latest.name} has non-done tasks: {', '.join(incomplete)}"
    finalize_path = plan_dir / "finalize.json"
    if finalize_path.exists():
        try:
            finalize_payload = json.loads(finalize_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            return False, f"finalize.json could not be read: {error}"
        finalize_tasks = (
            finalize_payload.get("tasks") if isinstance(finalize_payload, dict) else None
        )
        if isinstance(finalize_tasks, list) and finalize_tasks:
            pending = [
                f"{(task.get('id') or '?')}={task.get('status')!r}"
                for task in finalize_tasks
                if isinstance(task, dict) and task.get("status") not in {"done", "skipped"}
            ]
            if pending:
                return False, f"finalize.json has incomplete tasks: {', '.join(pending)}"
    return True, latest.name


def _mark_blocked_execute_as_executed(plan_dir: Path) -> None:
    state_path = plan_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        return
    state["current_state"] = STATE_EXECUTED
    state.pop("active_step", None)
    state.pop("latest_failure", None)
    state.pop("resume_cursor", None)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _recover_blocked_execute_if_tasks_done(
    root: Path,
    outcome: DriverOutcome,
    *,
    writer,
) -> bool:
    if outcome.status not in BLOCKED_EXECUTE_OUTCOME_STATUSES:
        return False
    try:
        plan_dir = resolve_plan_dir(root, outcome.plan)
    except CliError:
        return False
    if _latest_execute_result(plan_dir) != "blocked":
        return False

    all_done, reason = _latest_execution_batch_all_tasks_done(plan_dir)
    if not all_done:
        writer(
            f"[chain] execute result=blocked for {outcome.plan}; treating as real block: {reason}\n"
        )
        return False

    _mark_blocked_execute_as_executed(plan_dir)
    writer(
        f"[chain] execute result=blocked for {outcome.plan}, but {reason} has all tasks done; "
        "continuing from executed state\n"
    )
    return True


def _drive_plan_with_blocked_execute_recovery(
    root: Path,
    plan: str,
    spec: ChainSpec,
    *,
    on_phase_complete: Callable[[str, int, str, str], None] | None = None,
    writer,
) -> DriverOutcome:
    outcome = _drive_plan(
        root,
        plan,
        spec,
        on_phase_complete=on_phase_complete,
        writer=writer,
    )
    if not _recover_blocked_execute_if_tasks_done(root, outcome, writer=writer):
        return outcome
    return _drive_plan(
        root,
        plan,
        spec,
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
    one: bool = False,
) -> dict[str, Any]:
    """Drive the full chain. Returns a structured JSON-serializable result."""
    spec = load_spec(spec_path)
    validate_paths(spec, root)
    state = load_chain_state(spec_path)
    preexisting_dirty_paths = _dirty_worktree_paths(root)
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
            outcome = _drive_plan_with_blocked_execute_recovery(
                root,
                spec.seed_plan,
                spec,
                writer=writer,
            )
            state.last_state = outcome.status
            save_chain_state(spec_path, state)
            decision = _handle_outcome(outcome, spec=spec, writer=writer)
            if decision == "stop":
                return _result("stopped", state, events, spec=spec, reason=f"seed plan {outcome.status}")
            if decision == "retry":
                # Recursive retry kept simple: re-drive seed once.
                outcome = _drive_plan_with_blocked_execute_recovery(
                    root,
                    spec.seed_plan,
                    spec,
                    writer=writer,
                )
                state.last_state = outcome.status
                save_chain_state(spec_path, state)
                if outcome.status != "done":
                    return _result("stopped", state, events, spec=spec, reason="seed retry failed")
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
                        spec=spec,
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
                _checkout_milestone_branch(
                    root,
                    milestone.branch or "",
                    base_branch=spec.base_branch,
                    writer=writer,
                )
                state.pr_number = _ensure_milestone_pr(
                    root,
                    milestone,
                    base_branch=spec.base_branch,
                    writer=writer,
                )
                state.pr_state = "open"
                save_chain_state(spec_path, state)
        else:
            _refresh_base_branch(
                root,
                spec.base_branch,
                writer=writer,
                no_git_refresh=no_git_refresh,
            )
            if use_pr:
                _checkout_milestone_branch(
                    root,
                    milestone.branch or "",
                    base_branch=spec.base_branch,
                    writer=writer,
                )
            plan_name = _init_plan(
                root,
                milestone.idea,
                robustness=milestone.robustness or spec.robustness,
                auto_approve=spec.auto_approve,
                profile=milestone.profile,
                vendor=milestone.vendor,
                depth=milestone.depth,
                critic=milestone.critic,
                deepseek_provider=milestone.deepseek_provider,
                with_prep=milestone.with_prep,
                with_feedback=milestone.with_feedback,
                prep_direction=milestone.prep_direction,
                phase_model=milestone.phase_model,
                writer=writer,
            )
            state.current_milestone_index = idx
            state.current_plan_name = plan_name
            save_chain_state(spec_path, state)
            if use_pr:
                _commit_and_push_phase(
                    root,
                    milestone.branch or "",
                    plan_name,
                    "init",
                    writer=writer,
                    preexisting_dirty_paths=preexisting_dirty_paths,
                )
                state.pr_number = _ensure_milestone_pr(
                    root,
                    milestone,
                    base_branch=spec.base_branch,
                    writer=writer,
                )
                state.pr_state = "open"
                save_chain_state(spec_path, state)

        def phase_callback(phase: str, _code: int, _out: str, _err: str) -> None:
            if use_pr and milestone.branch:
                _commit_and_push_phase(
                    root,
                    milestone.branch,
                    plan_name,
                    phase,
                    writer=writer,
                    preexisting_dirty_paths=preexisting_dirty_paths,
                )

        outcome = _drive_plan_with_blocked_execute_recovery(
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
                spec=spec,
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
            _commit_and_push_phase(
                root,
                milestone.branch or "",
                plan_name,
                "done",
                writer=writer,
                preexisting_dirty_paths=preexisting_dirty_paths,
            )
            current_pr_state = _pr_state(root, state.pr_number, writer=writer)
            if current_pr_state == "merged":
                state.pr_state = "merged"
                save_chain_state(spec_path, state)
            else:
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
                        spec=spec,
                        reason=f"milestone {milestone.label} PR #{state.pr_number} awaiting merge",
                    )
                state.pr_state = _enable_auto_merge(root, state.pr_number, writer=writer)
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
        if one:
            log(f"paused after milestone {milestone.label}")
            return _result(
                "paused",
                state,
                events,
                spec=spec,
                reason=f"completed one milestone: {milestone.label}",
            )

    log("all milestones complete")
    return _result("done", state, events, spec=spec)


def _result(
    status: str, state: ChainState, events: list[dict[str, Any]], *, spec: ChainSpec | None = None, reason: str = ""
) -> dict[str, Any]:
    result = {
        "status": status,
        "reason": reason,
        "chain_state": state.to_dict(),
        "events": events,
    }
    if spec is not None:
        result["base_branch"] = spec.base_branch
    return result


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
        "base_branch": spec.base_branch,
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
    writer(f"Base branch: {summary.get('base_branch') or 'main'}\n")
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
            "Skip the automatic base-branch checkout and pull that runs "
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
    chain_parser.add_argument(
        "--one",
        action="store_true",
        help="Drive at most one pending milestone, persist progress, then stop cleanly.",
    )

    start_parser = chain_sub.add_parser("start", help="Drive a chain spec")
    start_parser.add_argument("--spec", required=True, help="Path to the chain spec YAML")
    start_parser.add_argument(
        "--no-git-refresh",
        action="store_true",
        help=(
            "Skip the automatic base-branch checkout and pull that runs "
            "before each milestone."
        ),
    )
    start_parser.add_argument(
        "--no-push",
        action="store_true",
        help="Disable branch/PR/push lifecycle for no-network runs.",
    )
    start_parser.add_argument(
        "--one",
        action="store_true",
        help="Drive at most one pending milestone, persist progress, then stop cleanly.",
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
            "base_branch": spec.base_branch,
            "chain_state": chain_state.to_dict(),
            "summary": summary,
        }
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
        return 0

    if action not in (None, "start"):
        return _emit_error(CliError("invalid_args", f"Unknown chain action: {action}"))

    no_git_refresh = bool(getattr(args, "no_git_refresh", False))
    no_push = bool(getattr(args, "no_push", False))
    one = bool(getattr(args, "one", False))
    try:
        result = run_chain(
            spec_path,
            root,
            no_git_refresh=no_git_refresh,
            no_push=no_push,
            one=one,
        )
    except CliError as exc:
        return _emit_error(exc)
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    if result["status"] in {"done", "paused"}:
        return 0
    return 1


def _emit_error(error: CliError) -> int:
    payload = {"success": False, "error": error.code, "message": error.message}
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return error.exit_code or 1
