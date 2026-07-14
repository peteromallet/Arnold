"""Shared test-suite runner for the mechanical-test gate.

Provides :class:`SuiteRunResult` (a frozen dataclass capturing every run) and
:func:`run_suite` (the authoritative subprocess lifecycle for any
single invocation of the configured test command).

Uses ``megaplan/runtime/process.py`` (``spawn`` / ``kill_group``) for
process-group management — NOT raw ``subprocess.Popen`` — so the harness
can reliably reap the whole process tree on deadline expiry (gate warning #1).
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Literal
from uuid import uuid4

from arnold_pipelines.megaplan._core.io import sha256_text
from arnold_pipelines.megaplan.runtime.process import kill_group, spawn

SuiteStatus = Literal[
    "passed", "failed", "runner_error", "not_applicable", "timeout"
]


@dataclass(frozen=True)
class SuiteRunResult:
    """Immutable record of a single test-suite invocation."""

    run_id: str
    phase: str
    command: str
    duration: float
    collected: int
    collected_ids: list[str]
    failures: list[str]
    passes: list[str]
    status: SuiteStatus
    exit_code: int | None
    raw_log_path: Path
    code_hash: str
    collections_parse_ok: bool
    collection_errors: list[str] | None = None
    # Set only when ``status == "timeout"``: ``"idle"`` (output stalled — suite
    # wedged) vs ``"deadline"`` (hit the absolute runaway ceiling). ``None``
    # otherwise. Lets callers write an accurate, actionable timeout note.
    timeout_reason: str | None = None


def _compute_code_hash(
    project_dir: Path, *, paths: list[str] | None = None,
) -> str:
    """Primary: ``git -C <project_dir> ls-tree -r HEAD -- <paths> | sha256sum``.

    Falls back to a portable, deterministic Python filesystem hash when git is
    unavailable or the working tree is not a repo.
    """
    if paths is None:
        paths = ["."]

    try:
        argv = ["git", "-C", str(project_dir), "ls-tree", "-r", "HEAD", "--", *paths]
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return sha256_text(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return _compute_filesystem_hash(project_dir, paths)


def _iter_hash_files(project_dir: Path, paths: Iterable[str]) -> list[Path]:
    files: set[Path] = set()
    for raw in paths:
        candidates = list(project_dir.glob(raw)) if any(c in raw for c in "*?[") else [project_dir / raw]
        for candidate in candidates:
            if not candidate.exists():
                continue
            if candidate.is_file():
                files.add(candidate)
            elif candidate.is_dir():
                files.update(p for p in candidate.rglob("*") if p.is_file())
    return sorted(files, key=lambda p: p.relative_to(project_dir).as_posix())


def _compute_filesystem_hash(project_dir: Path, paths: list[str]) -> str:
    digest = sha256()
    for path in _iter_hash_files(project_dir, paths):
        try:
            rel = path.relative_to(project_dir).as_posix()
            stat = path.stat()
            digest.update(rel.encode("utf-8", "surrogateescape"))
            digest.update(b"\0")
            digest.update(str(stat.st_size).encode("ascii"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        except OSError:
            continue
    return f"sha256:{digest.hexdigest()}"

# Regex to extract nodeid from ``^FAILED <nodeid>`` / ``^PASSED <nodeid>``
# lines in the pytest short-test-summary (``-rA``).  Captures the full nodeid
# including parametrized suffixes like ``test_foo[a-1]``.
# Deliberately avoids the old substring-slice approach used in
# ``megaplan/handlers/finalize.py:584-586`` (``endswith(" FAILED")`` /
# ``line[:-len(" FAILED")]``).
_NODEID_LINE_RE = re.compile(
    r"^(FAILED|PASSED)\s+(\S+)"
)
_SUMMARY_COUNT_RE = re.compile(r"(\d+)\s+(failed|passed)\b")
_COLLECTION_ERROR_LINE_RE = re.compile(
    r"^ERROR(?:\s+collecting)?\s+(.+?)(?:\s+-\s+.*)?$"
)
_COLLECTION_ERROR_KEYWORDS = (
    "ImportError",
    "ModuleNotFoundError",
    "collection error",
    "No module named",
    "Interrupted:",
    "errors during collection",
)
_NODE_TEST_RESULT_RE = re.compile(r"^(ok|not ok)\s+\d+\s+-\s+(.+?)\s*$")


def _dedupe_preserving_order(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _collection_errors_from_output(stdout: str, exit_code: int | None) -> list[str]:
    """Return structural pytest collection/import failures as stable IDs."""
    has_collection_signal = exit_code == 2 or any(
        keyword in stdout for keyword in _COLLECTION_ERROR_KEYWORDS
    )
    if not has_collection_signal:
        return []

    errors: list[str] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        match = _COLLECTION_ERROR_LINE_RE.match(stripped)
        if not match:
            continue
        target = match.group(1).strip()
        if target and not target.startswith(("at ", "(")):
            errors.append(target)

    if not errors:
        errors.append("pytest_collection_error")
    return _dedupe_preserving_order(errors)


def _parse_pytest_output(stdout: str, exit_code: int | None = None) -> dict[str, Any]:
    """Extract collected count, failures, passes, and collected ids from
    pytest stdout (assumes ``--tb=no -q --no-header -rA`` flags).

    Returns a dict with keys ``collected``, ``collected_ids``, ``failures``,
    ``passes``, ``parse_ok``.
    """
    collected = 0
    collected_ids: list[str] = []
    failures: list[str] = []
    passes: list[str] = []
    parse_ok = False

    # --- collected count ---
    m = re.search(r"collected\s+(\d+)\s+item", stdout)
    if not m:
        m = re.search(r"(\d+)\s+tests?\s+collected", stdout)
    if m:
        collected = int(m.group(1))
        parse_ok = True

    for line in stdout.splitlines():
        m = _NODEID_LINE_RE.match(line.strip())
        if not m:
            continue
        status_kw = m.group(1)
        nodeid = m.group(2)
        if not nodeid:
            continue
        if status_kw == "FAILED":
            failures.append(nodeid)
        elif status_kw == "PASSED":
            passes.append(nodeid)

    summary = {"passed": 0, "failed": 0}
    for count, kind in _SUMMARY_COUNT_RE.findall(stdout):
        summary[kind] = int(count)
        parse_ok = True
    if len(passes) != summary["passed"] or len(failures) != summary["failed"]:
        parse_ok = False

    collected_ids = list(dict.fromkeys(failures + passes))
    collection_errors = _collection_errors_from_output(stdout, exit_code)
    if collection_errors:
        failures = _dedupe_preserving_order(failures + collection_errors)
        collected_ids = _dedupe_preserving_order(collected_ids + collection_errors)
        parse_ok = True
        collected = max(collected, len(collected_ids))

    return {
        "collected": collected,
        "collected_ids": collected_ids,
        "failures": failures,
        "passes": passes,
        "collection_errors": collection_errors,
        "parse_ok": parse_ok,
    }


def _parse_node_test_output(stdout: str) -> dict[str, Any]:
    """Extract pass/fail identities from ``node --test`` TAP output."""
    collected_ids: list[str] = []
    failures: list[str] = []
    passes: list[str] = []

    for line in stdout.splitlines():
        match = _NODE_TEST_RESULT_RE.match(line.strip())
        if not match:
            continue
        nodeid = match.group(2).strip()
        if not nodeid:
            continue
        collected_ids.append(nodeid)
        if match.group(1) == "ok":
            passes.append(nodeid)
        else:
            failures.append(nodeid)

    collected_ids = _dedupe_preserving_order(collected_ids)
    passes = _dedupe_preserving_order(passes)
    failures = _dedupe_preserving_order(failures)
    return {
        "collected": len(collected_ids),
        "collected_ids": collected_ids,
        "failures": failures,
        "passes": passes,
        "collection_errors": [],
        "parse_ok": bool(collected_ids),
    }


def _run_collect_only(project_dir: Path, command: str) -> list[str]:
    """Fallback: run ``pytest --collect-only -q`` to enumerate all test ids.

    Returns a list of nodeid strings, or an empty list on failure.
    """
    try:
        result = subprocess.run(
            ["pytest", "--collect-only", "-q"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode not in (0, 1, 5):
            return []
        ids: list[str] = []
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped and "::" in stripped and not stripped.startswith("!"):
                ids.append(stripped)
        return ids
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []


def _hash_paths_from_config(config: dict[str, Any]) -> list[str] | None:
    out: list[str] = []
    for key in ("test_dirs", "source_globs"):
        value = config.get(key)
        if isinstance(value, list):
            out.extend(str(v) for v in value)
        elif isinstance(value, str):
            out.append(value)
    return out or None


def _pytest_command(command: str | None) -> str:
    if not command:
        return f"{shlex.quote(sys.executable)} -m pytest --tb=no -q --no-header -rA"
    parts = shlex.split(command)
    if not parts:
        return f"{shlex.quote(sys.executable)} -m pytest --tb=no -q --no-header -rA"
    first = Path(parts[0]).name
    if first == "pytest":
        parts = [sys.executable, "-m", "pytest", *parts[1:]]
    elif first.startswith("pytest"):
        parts = [sys.executable, "-m", "pytest", *parts[1:]]
    elif first in {"python", "python3"} or first.startswith("python"):
        pass
    elif "pytest" not in command:
        return command
    parts = ["-rA" if p == "-rN" else p for p in parts]
    present = set(parts)
    for flag in ("--tb=no", "-q", "--no-header", "-rA"):
        if flag not in present:
            parts.append(flag)
    return " ".join(shlex.quote(p) for p in parts)


def _is_node_test_command(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return len(parts) >= 2 and Path(parts[0]).name == "node" and parts[1] == "--test"


def _raw_log_path(project_dir: Path, config: dict[str, Any], run_id: str) -> Path:
    plan_dir_str = config.get("plan_dir") if isinstance(config, dict) else None
    plan_dir = Path(plan_dir_str) if plan_dir_str else project_dir / ".megaplan" / "verification"
    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)
    return ver_dir / f"raw_{run_id}.log"


# How often the soft progress heartbeat fires while the suite is running.
_PROGRESS_HEARTBEAT_S = 60.0


def _spawn_to_log(project_dir: Path, argv: list[str], raw_log_path: Path) -> tuple[Any | None, Any]:
    log_fh = raw_log_path.open("w", encoding="utf-8")
    # Force the child to flush stdout per-test rather than block-buffering to an
    # 8 KB pipe-to-file boundary. Without this the raw log grows in coarse chunks
    # and the progress/idle detector in ``_wait_for_process`` can't tell a
    # slow-but-moving suite from a wedged one. ``pytest -q`` emits one char per
    # test; unbuffered means each lands in the log immediately, so *log growth ==
    # real progress*.
    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    # The suite verifies ``project_dir``. Cloud runners commonly import the
    # Megaplan engine from a separate editable checkout via PYTHONPATH; leaving
    # that engine root first silently tests the engine checkout instead of the
    # milestone branch. Keep the engine available after the subject checkout.
    project_root = str(project_dir.resolve())
    inherited_pythonpath = env.get("PYTHONPATH", "")
    pythonpath_parts = [project_root]
    pythonpath_parts.extend(
        part
        for part in inherited_pythonpath.split(os.pathsep)
        if part and str(Path(part).resolve()) != project_root
    )
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    try:
        return spawn(
            argv,
            cwd=str(project_dir),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            env=env,
        ), log_fh
    except Exception:
        log_fh.close()
        return None, None


def _make_progress_writer(raw_log_path: Path) -> Any:
    """Append soft 'still running' heartbeats to a sibling ``.progress`` file.

    Written to a *different* file than the raw log so the heartbeat itself never
    counts as suite progress (which would defeat the idle detector).
    """
    progress_path = raw_log_path.with_suffix(".progress")

    def _cb(elapsed_s: float, log_bytes: int) -> None:
        try:
            with progress_path.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"[suite] still running: {elapsed_s:.0f}s elapsed, "
                    f"{log_bytes} bytes of test output captured\n"
                )
        except OSError:
            pass

    return _cb


def _wait_for_process(
    proc: Any,
    run_id: str,
    deadline_seconds: float,
    *,
    raw_log_path: Path | None = None,
    idle_seconds: float | None = None,
    progress_cb: Any | None = None,
) -> tuple[int | None, bool, str | None]:
    """Wait for the suite process, killing it on a stall or the absolute ceiling.

    Two independent caps:

    * ``idle_seconds`` (primary, opt-in) — a *hang detector*. While the raw log
      keeps growing the suite is making progress, so the idle clock is reset; only
      a log that goes silent for ``idle_seconds`` is treated as wedged. This is
      independent of total suite size, so it does not need re-tuning as the suite
      grows (a 10 k-test suite is never silent for 3 minutes unless a test hangs).
    * ``deadline_seconds`` (always) — an absolute runaway ceiling, a last resort
      that should essentially never trip for a healthy, moving suite.

    ``progress_cb(elapsed_s, log_bytes)`` is invoked roughly every
    ``_PROGRESS_HEARTBEAT_S`` so callers can emit a soft "still running" signal.

    Returns ``(exit_code, timed_out, timeout_reason)`` where ``timeout_reason`` is
    ``"idle"``, ``"deadline"`` or ``None``.
    """
    exit_code: int | None = None
    timed_out = False
    timeout_reason: str | None = None
    last_size = -1
    start = time.monotonic()
    last_progress_t = start
    last_heartbeat_t = start
    try:
        while True:
            now = time.monotonic()
            if now >= deadline_seconds:
                timeout_reason = "deadline"
                break
            if idle_seconds and raw_log_path is not None:
                try:
                    size = raw_log_path.stat().st_size
                except OSError:
                    size = last_size
                if size != last_size:
                    last_size = size
                    last_progress_t = now
                elif now - last_progress_t >= idle_seconds:
                    timeout_reason = "idle"
                    break
            if progress_cb is not None and now - last_heartbeat_t >= _PROGRESS_HEARTBEAT_S:
                last_heartbeat_t = now
                try:
                    progress_cb(now - start, max(last_size, 0))
                except Exception:
                    pass
            try:
                exit_code = proc.wait(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                continue
            except (ProcessLookupError, OSError):
                break
    except Exception:
        pass

    if exit_code is None and proc.poll() is None:
        timed_out = True
        if timeout_reason is None:
            timeout_reason = "deadline"
        kill_group(proc, grace_s=5.0, escalate=True, label=f"suite_runner:{run_id}")
    if not timed_out:
        timeout_reason = None
        try:
            exit_code = proc.wait(timeout=2)
        except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
            exit_code = proc.poll()
    return exit_code, timed_out, timeout_reason


def _status_from_exit(exit_code: int | None, timed_out: bool) -> SuiteStatus:
    if timed_out:
        return "timeout"
    if exit_code == 0:
        return "passed"
    if exit_code == 1:
        return "failed"
    if exit_code == 5:
        return "not_applicable"
    return "runner_error"


def _parsed_collection_state(
    project_dir: Path,
    command: str,
    exit_code: int | None,
    timed_out: bool,
    parsed: dict[str, Any],
    status: SuiteStatus,
) -> tuple[list[str], bool, SuiteStatus]:
    collected_ids = parsed["collected_ids"]
    collections_parse_ok = parsed["parse_ok"]
    if parsed.get("collection_errors"):
        return collected_ids, True, "failed"
    if not collections_parse_ok and (parsed["passes"] or parsed["failures"]):
        status = "runner_error"
    if not collected_ids and exit_code != 5 and not timed_out and "pytest" in command:
        collections_parse_ok = False
        fallback_ids = _run_collect_only(project_dir, command)
        if fallback_ids:
            collected_ids = fallback_ids
            collections_parse_ok = True
        else:
            status = "runner_error"
    return collected_ids, collections_parse_ok, status


def _spawn_error_result(
    run_id: str, phase: str, command: str, raw_log_path: Path, code_hash: str, t0: float
) -> SuiteRunResult:
    return SuiteRunResult(
        run_id=run_id,
        phase=phase,
        command=command,
        duration=time.monotonic() - t0,
        collected=0,
        collected_ids=[],
        failures=[],
        passes=[],
        status="runner_error",
        exit_code=None,
        raw_log_path=raw_log_path,
        code_hash=code_hash,
        collections_parse_ok=False,
        collection_errors=[],
    )


def run_suite(
    project_dir: Path,
    config: dict[str, Any],
    *,
    phase: str,
    deadline_seconds: float,
    idle_seconds: float | None = None,
) -> SuiteRunResult:
    """Run the configured test command.

    ``deadline_seconds`` is an absolute runaway ceiling. ``idle_seconds`` (opt-in)
    adds a progress-based stall detector: the suite is killed only if its output
    log stops growing for that long, so a slow-but-moving suite is never killed
    merely for being large. See :func:`_wait_for_process`. When ``idle_seconds``
    is set, a soft heartbeat is written to ``raw_<id>.progress`` alongside the log.
    """
    run_id = uuid4().hex[:12]
    command = _pytest_command(config.get("test_command") if isinstance(config, dict) else None)
    raw_log_path = _raw_log_path(project_dir, config, run_id)
    hash_paths = _hash_paths_from_config(config) if isinstance(config, dict) else None
    code_hash = _compute_code_hash(project_dir, paths=hash_paths)
    t0 = time.monotonic()
    proc, log_fh = _spawn_to_log(project_dir, shlex.split(command), raw_log_path)
    if proc is None:
        return _spawn_error_result(run_id, phase, command, raw_log_path, code_hash, t0)

    progress_cb = _make_progress_writer(raw_log_path) if idle_seconds else None
    exit_code, timed_out, timeout_reason = _wait_for_process(
        proc,
        run_id,
        deadline_seconds,
        raw_log_path=raw_log_path,
        idle_seconds=idle_seconds,
        progress_cb=progress_cb,
    )
    duration = time.monotonic() - t0
    log_fh.close()
    raw_output = raw_log_path.read_text(encoding="utf-8")
    if _is_node_test_command(command):
        parsed = _parse_node_test_output(raw_output)
    else:
        parsed = _parse_pytest_output(
            raw_output,
            exit_code=exit_code,
        )
    status = _status_from_exit(exit_code, timed_out)
    collected_ids, collections_parse_ok, status = _parsed_collection_state(
        project_dir, command, exit_code, timed_out, parsed, status
    )
    if status == "runner_error" and collections_parse_ok and parsed["failures"]:
        status = "failed"
    return SuiteRunResult(
        run_id=run_id, phase=phase, command=command, duration=duration,
        collected=parsed["collected"], collected_ids=collected_ids,
        failures=parsed["failures"], passes=parsed["passes"], status=status,
        exit_code=exit_code, raw_log_path=raw_log_path, code_hash=code_hash,
        collections_parse_ok=collections_parse_ok,
        timeout_reason=timeout_reason,
        collection_errors=parsed.get("collection_errors", []),
    )


from arnold_pipelines.megaplan.orchestration.suite_failure_details import extract_failure_details
from arnold_pipelines.megaplan.orchestration.suite_runs_log import (
    append_suite_run,
    freshness_skip,
    is_baseline_stale,
    latest_run_for_phase,
)
