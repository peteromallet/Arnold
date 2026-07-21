"""Process-to-plan correlation for the live watchdog."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


# Worker-liveness classifications. Each non-``matched`` class MUST resolve to a
# ``runner_verdict`` of ``unknown`` or ``lost`` — never ``success`` or
# ``repair``. Liveness is correlated evidence about an in-flight attempt, not a
# terminal or completion verdict. See ``classify_worker_liveness``.
LIVENESS_MATCHED = "matched"
LIVENESS_RECYCLED = "recycled"
LIVENESS_HUNG = "hung"
LIVENESS_DEAD = "dead"
LIVENESS_UNRELATED = "unrelated"

# runner_verdict values. ``unknown`` means the worker's relationship to the
# current attempt identity cannot be confirmed (recycled, unrelated, or no WBC
# attempt identity supplied). ``lost`` means the worker was tied to the attempt
# but is no longer making progress (hung) or is no longer alive (dead).
RUNNER_UNKNOWN = "unknown"
RUNNER_LOST = "lost"


@dataclass(frozen=True)
class WorkerLivenessClassification:
    """Display-only worker-liveness verdict.

    ``authority`` is always ``evidence_extracted_non_authoritative``: this
    classification may *describe* what a process/heartbeat/tmux signal looks
    like, but it must never feed dispatch, completion, cancellation,
    publication, or delivery.
    """

    classification: str
    runner_verdict: str
    reason: str
    evidence_basis: tuple[str, ...] = ()
    evidence_gaps: dict[str, Any] = field(default_factory=dict)
    authority: str = "evidence_extracted_non_authoritative"

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "runner_verdict": self.runner_verdict,
            "reason": self.reason,
            "evidence_basis": list(self.evidence_basis),
            "evidence_gaps": dict(self.evidence_gaps),
            "authority": self.authority,
        }


def _format_source_cursor(cursor_vector: Mapping[str, Any] | None) -> dict[str, Any]:
    """Format a source cursor vector for display, never granting authority."""
    if isinstance(cursor_vector, Mapping) and cursor_vector:
        return {
            "authority": "evidence_extracted_display_only",
            "value": dict(cursor_vector),
        }
    return {
        "authority": "absent",
        "reason": "no_source_cursor_vector_provided",
    }


def _collect_liveness_evidence_gaps(
    *,
    process: Any,
    attempt_session_token: str | None,
    attempt_start_epoch: float | None,
    runner_lease_ref: str | None,
    heartbeat_fresh: bool | None,
    heartbeat_age_seconds: float | None,
    wbc_attempt_identity_supplied: bool,
) -> dict[str, Any]:
    """Collect structured evidence gaps for the liveness join.

    Each gap is a ``{gap, reason, evidence_status}`` triple. Gaps are pure
    display annotations and never feed dispatch/completion/etc.
    """
    gaps: dict[str, Any] = {}

    is_live = bool(getattr(process, "is_live", False)) if not isinstance(process, dict) else bool(process.get("is_live", False))
    proc_session = getattr(process, "session_token", None) if not isinstance(process, dict) else process.get("session_token")
    proc_birth = getattr(process, "birth_time_seconds", None) if not isinstance(process, dict) else process.get("birth_time_seconds")

    if attempt_session_token is None:
        gaps["attempt_session_token"] = {
            "gap": "attempt_identity_unavailable",
            "reason": "no WBC attempt session token supplied; cannot confirm worker belongs to this attempt",
            "evidence_status": "missing",
        }
    elif proc_session is None:
        gaps["worker_session_token"] = {
            "gap": "worker_session_token_unextracted",
            "reason": "process cmdline did not yield a session token; identity join inconclusive",
            "evidence_status": "missing",
        }
    elif proc_session != attempt_session_token:
        gaps["session_token_mismatch"] = {
            "gap": "worker_session_token_mismatch",
            "reason": "process session token differs from attempt session token; worker is unrelated or PID was recycled",
            "evidence_status": "conflict",
        }

    if attempt_start_epoch is not None and proc_birth is not None and proc_birth > attempt_start_epoch:
        gaps["recycled_pid"] = {
            "gap": "pid_birth_after_attempt_start",
            "reason": "process birth time is newer than the attempt start; PID was recycled and does not belong to this attempt",
            "evidence_status": "conflict",
        }

    if not is_live:
        gaps["process_liveness"] = {
            "gap": "process_dead",
            "reason": "process is not live; worker cannot be making progress",
            "evidence_status": "dead",
        }

    if heartbeat_fresh is False:
        gaps["heartbeat_freshness"] = {
            "gap": "heartbeat_stale",
            "reason": "no fresh heartbeat observed; worker may be hung",
            "evidence_status": "stale",
        }
    elif heartbeat_fresh is None and heartbeat_age_seconds is None:
        gaps["heartbeat_freshness"] = {
            "gap": "heartbeat_unobserved",
            "reason": "no heartbeat signal available; freshness cannot be confirmed",
            "evidence_status": "missing",
        }

    if runner_lease_ref is None:
        gaps["runner_lease"] = {
            "gap": "runner_lease_ref_unavailable",
            "reason": "no runner lease reference supplied; lease validity unconfirmed",
            "evidence_status": "missing",
        }

    if not wbc_attempt_identity_supplied:
        gaps["wbc_attempt_identity"] = {
            "gap": "wbc_attempt_identity_absent",
            "reason": "no canonical WBC attempt identity supplied; liveness cannot be joined to a current attempt",
            "evidence_status": "missing",
        }

    return gaps


def classify_worker_liveness(
    process: Any,
    *,
    attempt_session_token: str | None = None,
    attempt_start_epoch: float | None = None,
    runner_lease_ref: str | None = None,
    heartbeat_fresh: bool | None = None,
    heartbeat_age_seconds: float | None = None,
    wbc_attempt_identity_supplied: bool = False,
    source_cursor_vector: Mapping[str, Any] | None = None,
) -> WorkerLivenessClassification:
    """Classify a worker process against a WBC attempt identity.

    The classification joins process facts (PID liveness, birth time, session
    token, runner lease ref) with heartbeat freshness. The result is always
    evidence-only:

    * ``matched``      — worker is live, heartbeat fresh, and identity matches
                         the current attempt. ``runner_verdict`` is still
                         ``unknown``: a live worker proves an in-flight attempt,
                         NOT success or completion.
    * ``recycled``     — PID exists but birth time postdates the attempt start,
                         or the session token differs. ``runner_verdict=unknown``.
    * ``hung``         — worker is live but heartbeat is stale. ``runner_verdict=lost``.
    * ``dead``         — worker process is not live. ``runner_verdict=lost``.
    * ``unrelated``    — worker exists but no evidence ties it to the attempt
                         (no WBC attempt identity, or session/lease mismatch
                         without a recycled-PID signal). ``runner_verdict=unknown``.

    No classification path returns ``success`` or ``repair``: liveness never
    authorizes a terminal or completion transition.
    """
    gaps = _collect_liveness_evidence_gaps(
        process=process,
        attempt_session_token=attempt_session_token,
        attempt_start_epoch=attempt_start_epoch,
        runner_lease_ref=runner_lease_ref,
        heartbeat_fresh=heartbeat_fresh,
        heartbeat_age_seconds=heartbeat_age_seconds,
        wbc_attempt_identity_supplied=wbc_attempt_identity_supplied,
    )

    is_live = bool(getattr(process, "is_live", False)) if not isinstance(process, dict) else bool(process.get("is_live", False))
    proc_session = getattr(process, "session_token", None) if not isinstance(process, dict) else process.get("session_token")
    proc_birth = getattr(process, "birth_time_seconds", None) if not isinstance(process, dict) else process.get("birth_time_seconds")

    basis: list[str] = []
    if is_live:
        basis.append("process_live")
    if proc_session is not None:
        basis.append("session_token")
    if proc_birth is not None:
        basis.append("birth_time")

    # 1. Dead — process not live. Always ``lost``.
    if not is_live:
        return WorkerLivenessClassification(
            classification=LIVENESS_DEAD,
            runner_verdict=RUNNER_LOST,
            reason="worker process is not live; cannot be making progress",
            evidence_basis=tuple(basis),
            evidence_gaps=gaps,
        )

    # 2. Recycled — PID birth time postdates the attempt start, or session
    #    token conflicts with the attempt identity. Always ``unknown`` (the
    #    PID cannot be attributed to this attempt).
    if attempt_start_epoch is not None and proc_birth is not None and proc_birth > attempt_start_epoch:
        return WorkerLivenessClassification(
            classification=LIVENESS_RECYCLED,
            runner_verdict=RUNNER_UNKNOWN,
            reason="PID was recycled: process birth postdates attempt start",
            evidence_basis=tuple(basis),
            evidence_gaps=gaps,
        )
    if (
        attempt_session_token is not None
        and proc_session is not None
        and proc_session != attempt_session_token
    ):
        return WorkerLivenessClassification(
            classification=LIVENESS_RECYCLED,
            runner_verdict=RUNNER_UNKNOWN,
            reason="process session token conflicts with attempt session token; PID likely recycled or unrelated",
            evidence_basis=tuple(basis),
            evidence_gaps=gaps,
        )

    # 3. Hung — worker is live but heartbeat is stale. Always ``lost``.
    if heartbeat_fresh is False:
        return WorkerLivenessClassification(
            classification=LIVENESS_HUNG,
            runner_verdict=RUNNER_LOST,
            reason="worker is live but heartbeat is stale; presumed hung",
            evidence_basis=tuple(basis + ["heartbeat_stale"]),
            evidence_gaps=gaps,
        )

    # 4. Matched — worker is live, heartbeat fresh (or unobserved), and either
    #    the session token matches the attempt identity OR no attempt identity
    #    was supplied (in which case we cannot upgrade beyond ``unknown`` even
    #    though the process looks alive).
    session_matches = (
        attempt_session_token is not None
        and proc_session is not None
        and proc_session == attempt_session_token
    )
    if session_matches and (heartbeat_fresh is True or heartbeat_fresh is None):
        return WorkerLivenessClassification(
            classification=LIVENESS_MATCHED,
            # Even a matched, live worker is NOT success — it proves an
            # in-flight attempt only.
            runner_verdict=RUNNER_UNKNOWN,
            reason="worker is live and session token matches the current attempt identity",
            evidence_basis=tuple(basis + ["session_token_match"]),
            evidence_gaps=gaps,
        )

    # 5. Unrelated / indeterminate — no positive identity join. ``unknown``.
    return WorkerLivenessClassification(
        classification=LIVENESS_UNRELATED,
        runner_verdict=RUNNER_UNKNOWN,
        reason="worker exists but cannot be positively joined to the current attempt identity",
        evidence_basis=tuple(basis),
        evidence_gaps=gaps,
    )


@dataclass(frozen=True)
class Correlation:
    plan_dir: Path
    process_pid: int
    method: str
    # M9 — correlated-evidence annotations. ``confidence`` is one of
    # ``high``/``medium``/``low``/``evidence_only`` and reflects how strongly
    # the cmdline/path/cwd signals tie this process to the plan; it never
    # implies success or repair. ``evidence_basis`` lists the signal names that
    # produced the match (e.g. ``("exact_name", "cwd_match")``) for diagnostics.
    # ``liveness_authority`` carries the classified worker liveness
    # (matched/recycled/hung/dead/unrelated) and is always marked
    # ``evidence_extracted_non_authoritative``.
    confidence: str = "evidence_only"
    evidence_basis: tuple[str, ...] = ()
    liveness_authority: dict[str, Any] | None = None


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
    "WorkerLivenessClassification",
    "classify_worker_liveness",
    "LIVENESS_MATCHED",
    "LIVENESS_RECYCLED",
    "LIVENESS_HUNG",
    "LIVENESS_DEAD",
    "LIVENESS_UNRELATED",
    "RUNNER_UNKNOWN",
    "RUNNER_LOST",
]
