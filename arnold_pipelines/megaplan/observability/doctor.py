"""``megaplan doctor`` — diagnostic surface for plans and repos.

Plan-level checks (``--plan``):
- Stale lock (lock holder pid vs psutil)
- Phase >80% of phase_timeout
- LLM call with no heartbeat >60s
- Cost trajectory >2× nominal
- Orphan subprocesses
- Outstanding flags with recoverable_via

Repo-level checks (``--repo``):
- Rubric/binary drift (failure modes 4+5)
- Editable-install + dirty working tree
- Multiple megaplan checkouts
- Skill files out of sync
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.observability.events import EventKind, read_events
from arnold_pipelines.megaplan.observability.liveness import unmatched_llm_starts

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_status(
    label: str, ok: bool, *, remediation: str = "", severity: str = "OK"
) -> tuple[str, str, str]:
    """Return (severity, label, message)."""
    icon = {"OK": "OK", "WARN": "WARN", "ERROR": "ERROR"}.get(severity, "??")
    msg = f"[{icon}] {label}"
    if remediation and severity in ("WARN", "ERROR"):
        msg += f"  → {remediation}"
    return severity, label, msg


def _plan_name_from_dir(plan_dir: Path) -> str:
    return plan_dir.name


def _parse_iso(ts_str: str) -> float | None:
    """Parse ISO timestamp to epoch seconds."""
    try:
        from datetime import datetime

        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def _git_branch(project_dir: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _git_dirty(project_dir: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def _is_editable_install() -> bool:
    """Check if megaplan is installed as editable."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "megaplan"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("Editable project location:"):
                    return True
    except Exception:
        pass
    return False


def _get_profiles_list() -> list[str]:
    """Get profiles from the binary via ``megaplan config profiles list``.

    Returns the list of profile names installed with the current binary.
    Falls back to reading ``megaplan/profiles/`` directory glob if the
    CLI call fails.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "arnold_pipelines.megaplan", "config", "profiles", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "MEGAPLAN_NO_COLOR": "1"},
        )
        if result.returncode == 0:
            # The command returns a JSON object with a "profiles" list
            import json as _json
            data = _json.loads(result.stdout)
            profile_list = data.get("profiles", [])
            if isinstance(profile_list, list):
                names = [
                    p.get("name", "") for p in profile_list
                    if isinstance(p, dict) and p.get("name")
                ]
                if names:
                    return names
            # Fallback: maybe the output is line-by-line names
            names: list[str] = []
            for line in result.stdout.splitlines():
                name = line.strip()
                if name and not name.startswith("{"):
                    names.append(name)
            if names:
                return names
    except Exception:
        pass
    # Fallback: glob the profiles directory
    try:
        import arnold_pipelines.megaplan.profiles as megaplan_profiles

        profiles_dir = Path(megaplan_profiles.__file__).parent
        return sorted(
            p.stem for p in profiles_dir.glob("*.toml") if p.stem != "__init__"
        )
    except Exception:
        return []


def _parse_decision_skill_profiles() -> list[str]:
    """Parse the megaplan-prep skill (prep_skill.md) for profile references.

    Extracts profile names from --profile mentions, tier-name lists,
    and table entries. Returns a deduplicated list.
    """
    try:
        import arnold_pipelines.megaplan.data as megaplan_data

        skill_path = Path(megaplan_data.__file__).parent / "prep_skill.md"
        if not skill_path.exists():
            return []
        content = skill_path.read_text(encoding="utf-8")
    except Exception:
        return []

    import re

    names: set[str] = set()

    # Known canonical tier/profile names
    known = {
        "solo", "directed", "partnered", "premium", "apex",
        "all-deepseek-pro", "all-deepseek-pro-direct", "all-claude",
        "all-codex", "all-open", "all-deepseek-flash", "all-fireworks-deepseek",
    }

    for name in known:
        if re.search(rf"\b{re.escape(name)}\b", content, re.IGNORECASE):
            names.add(name)

    # Also extract --profile NAME patterns
    for m in re.finditer(r"--profile\s+(\S+)", content):
        name = m.group(1).strip().strip('"').strip("'")
        if name:
            names.add(name)

    return sorted(names)


def _find_megaplan_checkouts() -> list[Path]:
    """Walk ~ for directories with .git/config containing megaplan origin."""
    home = Path.home()
    checkouts: list[Path] = []
    try:
        for gitdir in home.rglob(".git"):
            if not gitdir.is_dir():
                continue
            config = gitdir / "config"
            if not config.exists():
                continue
            try:
                text = config.read_text(encoding="utf-8")
                if "megaplan" in text.lower():
                    checkouts.append(gitdir.parent)
            except Exception:
                continue
    except Exception:
        pass
    return checkouts


# ---------------------------------------------------------------------------
# Plan-level checks
# ---------------------------------------------------------------------------


def _check_stale_lock(plan_dir: Path, *, composition: object | None = None) -> tuple[str, str, str]:
    """T26 — `composition` (CompositionObservability) is the flag-ON path for
    non-plan composers; today it is accepted but unused (plan_dir remains
    authoritative for flag-OFF). Strangler discipline keeps the legacy
    plan_dir call sites unchanged."""
    lock_file = plan_dir / ".lock"
    if not lock_file.exists():
        return _check_status("Lock", True)

    try:
        import psutil

        data = json.loads(lock_file.read_text(encoding="utf-8"))
        pid = data.get("pid")
        if pid is None:
            return _check_status(
                "Lock file exists but no PID",
                False,
                severity="WARN",
                remediation="Lock file is malformed. Run 'megaplan unlock --plan <name>'.",
            )
        if not psutil.pid_exists(pid):
            return _check_status(
                f"Stale lock (PID {pid} not running)",
                False,
                severity="WARN",
                remediation=f"Lock holder PID {pid} is dead. Run 'megaplan unlock --plan <name>' to clear.",
            )
        return _check_status("Lock held by live process", True)
    except Exception as e:
        return _check_status(
            "Lock check failed",
            False,
            severity="WARN",
            remediation=f"Could not verify lock status: {e}",
        )


def _check_phase_timeout(plan_dir: Path, *, composition: object | None = None) -> tuple[str, str, str]:
    # cache-tolerant: doctor probe.
    state_file = plan_dir / "state.json"
    if not state_file.exists():
        return _check_status("Phase timeout", True, severity="OK")

    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return _check_status("Phase timeout (unreadable state)", True, severity="OK")

    # Check if there's an active phase
    active = state.get("active_step")
    if not isinstance(active, dict):
        return _check_status("No active phase", True)

    started = active.get("started_at")
    if not started:
        return _check_status("Active phase has no started_at", True, severity="OK")

    import time
    from datetime import datetime, timezone

    try:
        started_ts = datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return _check_status("Phase timeout (unparseable timestamp)", True, severity="OK")

    elapsed = time.time() - started_ts
    # Default phase_timeout = 3600
    phase_timeout = 3600

    if elapsed > phase_timeout * 0.8:
        return _check_status(
            f"Phase running {elapsed:.0f}s (>{80}% of {phase_timeout}s timeout)",
            False,
            severity="WARN",
            remediation="Consider extending timeout or killing the phase.",
        )
    return _check_status(f"Phase running {elapsed:.0f}s (within timeout)", True)


def _check_llm_liveness(plan_dir: Path, *, composition: object | None = None) -> tuple[str, str, str]:
    """Check for unmatched llm_call_start (no end) with no heartbeat >60s."""
    import time

    now = time.time()
    events = list(read_events(plan_dir))
    from arnold_pipelines.megaplan.observability.liveness import unmatched_llm_starts

    unmatched_starts = unmatched_llm_starts(
        events,
        start_kind=EventKind.LLM_CALL_START,
        end_kind=EventKind.LLM_CALL_END,
    )

    active_step: dict[str, Any] = {}
    state_path = plan_dir / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if isinstance(state.get("active_step"), dict):
            active_step = state["active_step"]
    except (OSError, json.JSONDecodeError, TypeError):
        pass

    for ev in unmatched_starts:
        # Check for recent heartbeat
        ts = _parse_iso(ev.get("ts_utc", ""))
        if ts is None:
            continue
        age = now - ts
        if age > 60:
            # Check if there's a heartbeat after this start
            has_heartbeat = any(
                e.get("kind") == EventKind.LLM_TOKEN_HEARTBEAT
                and _parse_iso(e.get("ts_utc", "")) is not None
                and _parse_iso(e.get("ts_utc", "")) > ts
                for e in events
            )
            active_last_activity = _parse_iso(str(active_step.get("last_activity_at") or ""))
            active_matches = (
                active_step.get("phase") == ev.get("phase")
                and active_step.get("model") == ev.get("payload", {}).get("model")
            )
            if (
                active_matches
                and active_last_activity is not None
                and active_last_activity > ts
                and now - active_last_activity <= 60
            ):
                has_heartbeat = True
            if not has_heartbeat:
                return _check_status(
                    f"LLM call started {age:.0f}s ago with no heartbeat",
                    False,
                    severity="WARN",
                    remediation="The LLM call may be wedged. Consider killing the phase.",
                )

    return _check_status("LLM liveness", True)


def _check_cost_trajectory(plan_dir: Path, *, composition: object | None = None) -> tuple[str, str, str]:
    """Compare cumulative cost_recorded sum against nominal tier cap."""
    events = list(read_events(plan_dir))
    total_cost = 0.0
    for ev in events:
        if ev.get("kind") == EventKind.COST_RECORDED:
            total_cost += float(ev.get("payload", {}).get("cost_usd", 0))

    # Nominal tier cap: $30 for standard plans (this is configurable)
    tier_cap = 30.0
    if total_cost > tier_cap * 2:
        return _check_status(
            f"Cost ${total_cost:.2f} exceeds 2× tier cap (${tier_cap * 2:.2f})",
            False,
            severity="WARN",
            remediation="Unexpected spend. Review cost trajectory and consider tightening caps.",
        )
    return _check_status(f"Cost ${total_cost:.2f} (within 2× cap)", True)


def _check_orphan_subprocesses(plan_dir: Path, *, composition: object | None = None) -> tuple[str, str, str]:
    """Check for megaplan subprocesses with dead parents."""
    try:
        import psutil
    except ImportError:
        return _check_status("Orphan subprocesses (psutil not available)", True, severity="OK")

    plan_name = _plan_name_from_dir(plan_dir)
    orphans: list[int] = []
    try:
        for proc in psutil.process_iter(["pid", "cmdline", "ppid"]):
            cmdline = proc.info.get("cmdline") or []
            cmd_str = " ".join(cmdline)
            if "megaplan" not in cmd_str.lower():
                continue
            if plan_name not in cmd_str:
                continue
            ppid = proc.info.get("ppid")
            if ppid and not psutil.pid_exists(ppid):
                orphans.append(proc.info["pid"])
    except Exception:
        pass

    if orphans:
        return _check_status(
            f"Orphan subprocesses: {orphans}",
            False,
            severity="WARN",
            remediation=f"Orphan processes with dead parents. Review and kill if needed: kill {' '.join(map(str, orphans))}",
        )
    return _check_status("No orphan subprocesses", True)


def _check_outstanding_flags(plan_dir: Path, *, composition: object | None = None) -> tuple[str, str, str]:
    """Check for outstanding flags and enumerate recoverable_via."""
    from arnold_pipelines.megaplan._core.workflow import workflow_next

    # cache-tolerant: doctor probe.
    state_file = plan_dir / "state.json"
    if not state_file.exists():
        return _check_status("Outstanding flags (no state)", True, severity="OK")

    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return _check_status("Outstanding flags (unreadable state)", True, severity="OK")

    # Count unresolved flags from gate signals
    flags_count = 0
    for path in sorted(plan_dir.glob("gate_signals_v*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            flags = data.get("unresolved_flags", [])
            if isinstance(flags, list):
                flags_count = len(flags)
            break
        except Exception:
            continue

    if flags_count > 0:
        recoverable = workflow_next(state) if isinstance(state, dict) else []
        recov_str = ", ".join(recoverable) if recoverable else "none"
        return _check_status(
            f"{flags_count} outstanding flag(s)",
            False,
            severity="WARN",
            remediation=f"Recoverable via: {recov_str}",
        )
    return _check_status("No outstanding flags", True)


# ---------------------------------------------------------------------------
# Repo-level checks
# ---------------------------------------------------------------------------


def _check_rubric_drift() -> list[tuple[str, str, str]]:
    """Check rubric/binary drift: diff prep_skill.md profiles vs installed profiles."""
    results: list[tuple[str, str, str]] = []

    referenced = _parse_decision_skill_profiles()
    if not referenced:
        results.append(_check_status(
            "Rubric profiles referenced",
            True,
            severity="OK",
        ))
        return results

    installed = _get_profiles_list()
    installed_set = set(installed)

    missing = [p for p in referenced if p not in installed_set]
    if missing:
        results.append(_check_status(
            f"Rubric/binary drift: {len(missing)} profile(s) in prep_skill.md not found in binary",
            False,
            severity="WARN",
            remediation=(
                f"Missing profiles: {', '.join(sorted(missing))}. "
                "The decision skill references profiles your binary doesn't expose. "
                "Run 'megaplan config profiles list' to see available profiles."
            ),
        ))
    else:
        results.append(_check_status(
            f"Rubric/binary profiles match ({len(referenced)} referenced, {len(installed)} installed)",
            True,
        ))

    return results


def _check_editable_install() -> tuple[str, str, str]:
    """Check for editable install + dirty working tree."""
    is_editable = _is_editable_install()
    if not is_editable:
        return _check_status("Editable install", True)

    # Find the megaplan source tree
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "megaplan"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        location: str | None = None
        for line in result.stdout.splitlines():
            if line.startswith("Editable project location:"):
                location = line.split(":", 1)[1].strip()
                break
    except Exception:
        location = None

    if location:
        loc_path = Path(location)
        if _git_dirty(loc_path):
            branch = _git_branch(loc_path) or "?"
            return _check_status(
                f"Editable install + dirty tree (branch: {branch})",
                False,
                severity="WARN",
                remediation=(
                    "Uncommitted changes in the megaplan source tree will affect behavior immediately. "
                    "Commit or stash changes before running plans."
                ),
            )
        else:
            return _check_status(
                f"Editable install (branch: {_git_branch(loc_path) or '?'})",
                True,
                severity="OK",
            )

    return _check_status("Editable install (source location unknown)", True, severity="WARN")


def _check_multiple_checkouts() -> tuple[str, str, str]:
    checkouts = _find_megaplan_checkouts()
    if len(checkouts) > 1:
        paths = [str(c) for c in checkouts]
        return _check_status(
            f"Multiple megaplan checkouts: {len(checkouts)}",
            False,
            severity="WARN",
            remediation=f"Multiple checkouts found: {', '.join(paths[:5])}. Potential confusion source.",
        )
    return _check_status("Single megaplan checkout", True)


def _check_skill_sync() -> list[tuple[str, str, str]]:
    """Check that installed skill files match the canonical copies."""
    results: list[tuple[str, str, str]] = []

    skill_pairs = [
        ("megaplan-prep", "prep_skill.md"),
        ("megaplan-observe", "observe_skill.md"),
    ]

    for skill_name, src_filename in skill_pairs:
        try:
            import arnold_pipelines.megaplan.data as megaplan_data

            src_path = Path(megaplan_data.__file__).parent / src_filename
            if not src_path.exists():
                continue
            src_content = src_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Check Claude skills path
        claude_path = Path.home() / ".claude" / "skills" / skill_name / "SKILL.md"
        if claude_path.exists():
            try:
                installed = claude_path.read_text(encoding="utf-8")
                if installed != src_content:
                    results.append(_check_status(
                        f"Skill out of sync: {skill_name} (Claude)",
                        False,
                        severity="WARN",
                        remediation=f"Run 'megaplan setup' to re-sync {skill_name}.",
                    ))
                else:
                    results.append(_check_status(
                        f"Skill in sync: {skill_name} (Claude)",
                        True,
                    ))
            except Exception:
                pass

        # Check Codex skills path
        codex_path = Path.home() / ".codex" / "skills" / skill_name / "SKILL.md"
        if codex_path.exists():
            try:
                installed = codex_path.read_text(encoding="utf-8")
                if installed != src_content:
                    results.append(_check_status(
                        f"Skill out of sync: {skill_name} (Codex)",
                        False,
                        severity="WARN",
                        remediation=f"Run 'megaplan setup' to re-sync {skill_name}.",
                    ))
                else:
                    results.append(_check_status(
                        f"Skill in sync: {skill_name} (Codex)",
                        True,
                    ))
            except Exception:
                pass

    return results


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------


def _doctor_plan(plan_dir: Path) -> int:
    """Run plan-level checks. Returns exit code."""
    checks = [
        _check_stale_lock(plan_dir),
        _check_phase_timeout(plan_dir),
        _check_llm_liveness(plan_dir),
        _check_cost_trajectory(plan_dir),
        _check_orphan_subprocesses(plan_dir),
        _check_outstanding_flags(plan_dir),
    ]

    has_error = False
    for severity, label, msg in checks:
        print(msg, flush=True)
        if severity == "ERROR":
            has_error = True

    return 1 if has_error else 0


def _doctor_repo(project_dir: Path) -> int:
    """Run repo-level checks. Returns exit code."""
    checks: list[tuple[str, str, str]] = []

    checks.extend(_check_rubric_drift())
    checks.append(_check_editable_install())
    checks.append(_check_multiple_checkouts())
    checks.extend(_check_skill_sync())

    has_error = False
    for severity, label, msg in checks:
        print(msg, flush=True)
        if severity == "ERROR":
            has_error = True

    return 1 if has_error else 0


def _doctor_adaptive_critique() -> int:
    """Probe the adaptive critique wiring. Returns 0 if every probe passes,
    1 otherwise. Pure read-only — no LLM calls, no plan-dir state.
    """
    from arnold_pipelines.megaplan.audits.critique_evaluator import probe_adaptive_critique_wiring

    results = probe_adaptive_critique_wiring()
    has_failure = False
    for label, passed, detail in results:
        marker = "[OK]   " if passed else "[FAIL] "
        suffix = f"  ({detail})" if detail else ""
        print(f"{marker}{label}{suffix}", flush=True)
        if not passed:
            has_failure = True

    if has_failure:
        print(
            "\nadaptive critique would fall back to static lenses at runtime.\n"
            "  - to fix: investigate the failing probe(s) above\n"
            "  - to suppress: set `[execution] adaptive_critique = false`\n"
            "  - to refuse the silent fallback: "
            "set `[execution] strict_adaptive_critique = true` (raises at run time)",
            file=sys.stderr,
            flush=True,
        )
        return 1
    print("\nadaptive critique wiring is healthy.", flush=True)
    return 0


def handle_doctor(root: Path, args: argparse.Namespace) -> int:
    """``megaplan doctor`` entry point; returns exit code."""
    plan_name = getattr(args, "plan", None)
    repo_mode = getattr(args, "repo", False)
    adaptive_critique_mode = getattr(args, "adaptive_critique", False)

    if plan_name:
        from arnold_pipelines.megaplan._core import find_plan_dir

        cwd = Path.cwd()
        plan_dir = find_plan_dir(cwd, plan_name)
        if plan_dir is None:
            print(f"doctor: plan '{plan_name}' not found", file=sys.stderr)
            return 1
        return _doctor_plan(plan_dir)

    if repo_mode:
        return _doctor_repo(root)

    if adaptive_critique_mode:
        return _doctor_adaptive_critique()

    print("doctor: specify --plan X, --repo, or --adaptive-critique", file=sys.stderr)
    return 1
