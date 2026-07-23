"""Process-to-plan correlation for the live watchdog.

Correlation produces typed :class:`Correlation` records that link process
identities to plan directories.  Uncorrelated workers produce ``UNRELATED``
liveness — they are evidence of activity, not of specific plan progress.
Recycled PIDs are detected via boot_id mismatch.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.watchdog.worker_identity import (
    LivenessState,
    WorkerIdentity,
    WorkerCorrelation,
    WorkerLiveness,
)


@dataclass(frozen=True)
class Correlation:
    plan_dir: Path
    process_pid: int
    method: str

    def to_worker_correlation(
        self,
        *,
        is_pid_live: bool | None = None,
        worker_type: str = "",
        cmdline: str = "",
        cwd: str = "",
    ) -> WorkerCorrelation:
        """Convert this correlation to a typed WorkerCorrelation with liveness.

        Args:
            is_pid_live: Whether the PID is currently alive.
            worker_type: Worker category from process scanner.
            cmdline: Full command line.
            cwd: Working directory.

        Returns:
            A WorkerCorrelation with evaluated liveness.
        """
        identity = WorkerIdentity.from_process_record(
            pid=self.process_pid,
            worker_type=worker_type,
            cmdline=cmdline,
            cwd=cwd,
        )
        liveness = WorkerLiveness.evaluate(identity, is_pid_live=is_pid_live)
        return WorkerCorrelation(
            identity=identity,
            liveness=liveness,
            plan_dirs=(str(self.plan_dir),),
            correlation_method=self.method,
        )


def _read_chain_current_plan(chain_spec_path: str | None) -> str | None:
    if not chain_spec_path:
        return None
    legacy_path = Path(chain_spec_path).with_name("chain_state.json")
    for path in (_chain_state_path(Path(chain_spec_path)), legacy_path):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            current = raw.get("current_plan_name")
            if isinstance(current, str) and current:
                return current
        except Exception:
            continue
    return None


def _chain_state_path(spec_path: Path) -> Path:
    """Mirror of chain.spec._state_path_for (digest-based chain state)."""
    import hashlib

    spec_resolved = spec_path.resolve()
    digest = hashlib.sha1(str(spec_resolved).encode("utf-8")).hexdigest()[:12]
    return (
        spec_resolved.parent
        / ".megaplan"
        / "plans"
        / ".chains"
        / f"{spec_resolved.stem}-{digest}.json"
    )


_PLAN_PATH_RE = re.compile(r"(\S*\.megaplan/plans/([^/\s]+))")


def _extract_plan_paths_from_cmdline(cmdline: str) -> tuple[Path, ...]:
    """Return plan directories embedded in the cmdline (e.g. --mcp-config paths)."""
    dirs: list[Path] = []
    for match in _PLAN_PATH_RE.finditer(cmdline):
        plan_dir = Path(match.group(1))
        if ".megaplan/plans/" in str(plan_dir):
            dirs.append(plan_dir)
    return tuple(dirs)


def _path_contains(parent: Path, child: Path) -> bool:
    """True if *child* is equal to or inside *parent*."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def correlate_processes_to_plans(
    processes: tuple[Any, ...],
    plans: tuple[Any, ...],
) -> tuple[Correlation, ...]:
    """Correlate process records to plan directories.

    Matching preference:
      1. Exact plan-name match in the process cmdline.
      2. Exact plan-directory path match in the process cmdline.
      3. Cmdline path containing ``.megaplan/plans/<plan_id>``.
      4. Chain-state ``current_plan_name`` matches a plan name in the cmdline.
      5. Process cwd is inside the plan directory or repo path.

    Broad repo-path-only matches are explicitly rejected.
    """
    correlations: list[Correlation] = []
    seen: set[tuple[int, Path]] = set()

    plan_by_dir: dict[Path, Any] = {}
    plan_by_name: dict[str, Any] = {}
    for plan in plans:
        plan_dir = Path(plan.plan_dir) if hasattr(plan, "plan_dir") else Path(plan)
        plan_name = getattr(plan, "plan_name", plan_dir.name)
        plan_by_dir[plan_dir.resolve()] = plan
        plan_by_name[plan_name] = plan

    for proc in processes:
        if isinstance(proc, dict):
            pid = int(proc["pid"])
            cmdline = proc["cmdline"]
        else:
            pid = int(getattr(proc, "pid"))
            cmdline = getattr(proc, "cmdline")
        matched: Correlation | None = None

        # 1. Exact plan-name match (whole word, not merely a path component).
        # This avoids matching a worktree directory name that happens to appear
        # in every command run inside it. We scan every occurrence so a plan name
        # embedded in a brief filename does not hide the real ``--name`` argument.
        for name, plan in plan_by_name.items():
            if not name:
                continue
            start = 0
            while True:
                idx = cmdline.find(name, start)
                if idx == -1:
                    break
                before = cmdline[idx - 1] if idx > 0 else " "
                after = cmdline[idx + len(name)] if idx + len(name) < len(cmdline) else " "
                start = idx + len(name)
                # Reject if the match is inside a path (surrounded by /).
                if before == "/" or after == "/":
                    continue
                if before in {" ", "-", "_", "\"", "'"} and after in {" ", "-", "_", "\"", "'"}:
                    plan_dir = Path(plan.plan_dir) if hasattr(plan, "plan_dir") else Path(plan)
                    matched = Correlation(plan_dir=plan_dir, process_pid=pid, method="exact_name")
                    break
            if matched is not None:
                break

        # 2. Exact plan-dir match.
        if matched is None:
            for plan_dir_path, plan in plan_by_dir.items():
                if str(plan_dir_path) in cmdline:
                    matched = Correlation(plan_dir=plan_dir_path, process_pid=pid, method="exact_dir")
                    break

        # 3. Cmdline path match: paths like .../.megaplan/plans/<plan_id>/...
        if matched is None:
            for candidate in _extract_plan_paths_from_cmdline(cmdline):
                resolved = candidate.resolve()
                for plan_dir_path, plan in plan_by_dir.items():
                    if _path_contains(plan_dir_path, resolved):
                        matched = Correlation(plan_dir=plan_dir_path, process_pid=pid, method="cmdline_plan_path")
                        break
                    if resolved == plan_dir_path:
                        matched = Correlation(plan_dir=plan_dir_path, process_pid=pid, method="cmdline_plan_path")
                        break
                if matched is not None:
                    break

        # 4. Chain current_plan match: if this is a chain process, read the
        # chain state for each plan that has a chain_spec_path and correlate
        # when current_plan_name equals the plan name.
        if matched is None and ("chain" in cmdline.lower() or "arnold" in cmdline.lower()):
            for plan in plans:
                chain_spec_path = getattr(plan, "chain_spec_path", None)
                current_plan = _read_chain_current_plan(chain_spec_path)
                plan_name = getattr(plan, "plan_name", Path(plan.plan_dir).name)
                if current_plan and current_plan == plan_name:
                    plan_dir = Path(plan.plan_dir) if hasattr(plan, "plan_dir") else Path(plan)
                    matched = Correlation(plan_dir=plan_dir, process_pid=pid, method="chain_current_plan")
                    break

        # 5. Cwd-based match: the process is running inside the plan directory.
        # Repo-root-only matches are only used when the repo contains a single
        # discovered plan, otherwise a global daemon cwd would match every plan.
        if matched is None:
            cwd_str = proc.get("cwd") if isinstance(proc, dict) else getattr(proc, "cwd", None)
            if cwd_str:
                cwd = Path(cwd_str).resolve()
                plan_dir_matches: list[Path] = []
                repo_matches: list[Path] = []
                for plan in plans:
                    plan_dir = Path(plan.plan_dir).resolve() if hasattr(plan, "plan_dir") else Path(plan).resolve()
                    repo_path = Path(getattr(plan, "repo_path", plan_dir)).resolve()
                    if _path_contains(plan_dir, cwd):
                        plan_dir_matches.append(plan_dir)
                    elif _path_contains(repo_path, cwd):
                        repo_matches.append(plan_dir)
                if plan_dir_matches:
                    matched = Correlation(plan_dir=plan_dir_matches[0], process_pid=pid, method="cwd_match")
                elif len(repo_matches) == 1:
                    matched = Correlation(plan_dir=repo_matches[0], process_pid=pid, method="repo_cwd_match")

        if matched is not None:
            key = (matched.process_pid, matched.plan_dir.resolve())
            if key not in seen:
                seen.add(key)
                correlations.append(matched)

    return tuple(correlations)


def infer_plan_dirs_from_processes(processes: tuple[Any, ...]) -> tuple[Path, ...]:
    """Return plan directories implied by process cmdlines but not yet discovered.

    Only returns directories that actually exist and contain a ``state.json``,
    filtering out code fragments that happen to mention a plan path.
    """
    seen: set[Path] = set()
    result: list[Path] = []
    for proc in processes:
        cmdline = proc["cmdline"] if isinstance(proc, dict) else getattr(proc, "cmdline")
        for plan_dir in _extract_plan_paths_from_cmdline(cmdline):
            try:
                resolved = plan_dir.resolve()
            except Exception:
                resolved = plan_dir
            if resolved in seen:
                continue
            if not resolved.is_dir() or not (resolved / "state.json").is_file():
                continue
            seen.add(resolved)
            result.append(resolved)
    return tuple(result)


__all__ = [
    "Correlation",
    "correlate_processes_to_plans",
    "infer_plan_dirs_from_processes",
]
