"""Shared test-suite runner for the mechanical-test gate.

Provides :class:`SuiteRunResult` (a frozen dataclass capturing every run) and
:func:`run_suite` (the authoritative subprocess lifecycle for any
single invocation of the configured test command).

Uses ``megaplan/runtime/process.py`` (``spawn`` / ``kill_group``) for
process-group management — NOT raw ``subprocess.Popen`` — so the harness
can reliably reap the whole process tree on deadline expiry (gate warning #1).
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from megaplan._core.io import sha256_text
from megaplan.runtime.process import kill_group, spawn

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status type
# ---------------------------------------------------------------------------

SuiteStatus = Literal[
    "passed", "failed", "runner_error", "not_applicable", "timeout"
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# code_hash helper
# ---------------------------------------------------------------------------

def _compute_code_hash(
    project_dir: Path, *, paths: list[str] | None = None,
) -> str:
    """Primary: ``git -C <project_dir> ls-tree -r HEAD -- <paths> | sha256sum``.

    Falls back to ``find <dirs> -type f -printf '%P %s %T@\\n' | sort | sha256sum``
    when git is unavailable or the working tree is not a repo.

    Parameters
    ----------
    project_dir:
        Root of the project under test.
    paths:
        Relative paths / globs to scope the hash (e.g. test dirs, source dirs).
        When ``None``, defaults to ``["."]`` (everything under *project_dir*).
    """
    if paths is None:
        paths = ["."]

    # --- Primary: git ls-tree -------------------------------------------------
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

    # --- Fallback: find with metadata (GNU find) ------------------------------
    try:
        argv = [
            "find",
            *[str(project_dir / p) for p in paths],
            "-type", "f",
            "-printf", "%P %s %T@\\n",
        ]
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Sort for deterministic output
            lines = sorted(result.stdout.strip().split("\n"))
            return sha256_text("\n".join(lines))
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # --- Last-resort: hash the project_dir path itself ------------------------
    return sha256_text(str(project_dir))


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------

# Regex to extract nodeid from ``^FAILED <nodeid>`` / ``^PASSED <nodeid>``
# lines in the pytest short-test-summary (``-rN``).  Captures the full nodeid
# including parametrized suffixes like ``test_foo[a-1]``.
# Deliberately avoids the old substring-slice approach used in
# ``megaplan/handlers/finalize.py:584-586`` (``endswith(" FAILED")`` /
# ``line[:-len(" FAILED")]``).
_NODEID_LINE_RE = re.compile(
    r"^(FAILED|PASSED)\s+(\S+)"
)


def _parse_pytest_output(stdout: str) -> dict[str, Any]:
    """Extract collected count, failures, passes, and collected ids from
    pytest stdout (assumes ``--tb=no -q --no-header -rN`` flags).

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

    # --- FAILED / PASSED node IDs (regex, *not* substring slice) ---
    # Pytest ``-rN`` short-test-summary lists each failure/pass on its own
    # line, e.g.:
    #   FAILED tests/test_foo.py::test_param[a-1] - AssertionError
    #   PASSED tests/test_bar.py::test_basic
    # The regex captures the status keyword and the nodeid (non-whitespace
    # token immediately following).  Parametrized suffixes are naturally
    # included because they are part of the nodeid token.
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

    # --- summary-line pass / fail counts (fill gaps when per-ID parsing
    #     didn't capture everything) ---
    m = re.search(r"(\d+)\s+passed", stdout)
    if m:
        summary_passed = int(m.group(1))
        if len(passes) < summary_passed:
            missing = summary_passed - len(passes)
            passes.extend(
                f"<test-{i}>" for i in range(len(passes), summary_passed)
            )
        parse_ok = True
    m = re.search(r"(\d+)\s+failed", stdout)
    if m:
        summary_failed = int(m.group(1))
        if len(failures) < summary_failed:
            missing = summary_failed - len(failures)
            failures.extend(
                f"<test-{i}>" for i in range(len(failures), summary_failed)
            )
        parse_ok = True

    # --- collected_ids is the union of all parsed nodeids ---
    collected_ids = list(dict.fromkeys(failures + passes))

    return {
        "collected": collected,
        "collected_ids": collected_ids,
        "failures": failures,
        "passes": passes,
        "parse_ok": parse_ok,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_suite(
    project_dir: Path,
    config: dict[str, Any],
    *,
    phase: str,
    deadline_seconds: float,
) -> SuiteRunResult:
    """Run the configured test command with a hard deadline.

    Uses ``megaplan/runtime/process.py`` for process-group management:
    ``spawn`` (defaults ``start_new_session=True``) and ``kill_group``
    (SIGTERM → 5 s grace → SIGKILL).

    Parameters
    ----------
    project_dir:
        Root of the project under test (working directory for the command).
    config:
        Plan-state config dict.  Expected keys: ``test_command`` (str|None),
        ``project_dir`` (str|None).  Falls back to ``pytest``.
    phase:
        Label for the run (e.g. ``"baseline"``, ``"post_execute"``).
    deadline_seconds:
        Wall-clock deadline from ``time.monotonic()``.  When the current
        monotonic time exceeds this value the process group is killed.

    Returns
    -------
    SuiteRunResult
        Immutable record of the run.
    """
    run_id = uuid4().hex[:12]

    # Resolve command (always append -rN so the short-test-summary lists every
    # failure/pass on its own line — required by _parse_pytest_output).
    command: str | None = (
        config.get("test_command") if isinstance(config, dict) else None
    )
    if not command:
        command = "pytest --tb=no -q --no-header -rN"
    elif "pytest" in command:
        if "--tb" not in command:
            command = f"{command} --tb=no"
        if "-q" not in command.split():
            command = f"{command} -q"
        if "--no-header" not in command:
            command = f"{command} --no-header"
        if "-rN" not in command:
            command = f"{command} -rN"

    # Resolve plan_dir for log output
    plan_dir_str: str | None = (
        config.get("plan_dir") if isinstance(config, dict) else None
    )
    if plan_dir_str:
        plan_dir = Path(plan_dir_str)
    else:
        plan_dir = project_dir / ".megaplan" / "verification"
    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)

    raw_log_path = ver_dir / f"raw_{run_id}.log"

    # Resolve hash paths from config (test_dirs + source_globs)
    hash_paths: list[str] | None = None
    if isinstance(config, dict):
        test_dirs = config.get("test_dirs")
        source_globs = config.get("source_globs")
        if test_dirs or source_globs:
            hash_paths = []
            if test_dirs:
                if isinstance(test_dirs, list):
                    hash_paths.extend(test_dirs)
                elif isinstance(test_dirs, str):
                    hash_paths.append(test_dirs)
            if source_globs:
                if isinstance(source_globs, list):
                    hash_paths.extend(source_globs)
                elif isinstance(source_globs, str):
                    hash_paths.append(source_globs)

    code_hash = _compute_code_hash(project_dir, paths=hash_paths)

    t0 = time.monotonic()

    # Parse the command into argv list
    argv = shlex.split(command)

    # Open log file for streaming
    log_fh = raw_log_path.open("w", encoding="utf-8")

    proc = None
    try:
        proc = spawn(
            argv,
            cwd=str(project_dir),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        log_fh.close()
        duration = time.monotonic() - t0
        return SuiteRunResult(
            run_id=run_id,
            phase=phase,
            command=command,
            duration=duration,
            collected=0,
            collected_ids=[],
            failures=[],
            passes=[],
            status="runner_error",
            exit_code=None,
            raw_log_path=raw_log_path,
            code_hash=code_hash,
            collections_parse_ok=False,
        )

    # Wait for process or deadline
    exit_code: int | None = None
    timed_out = False

    try:
        while time.monotonic() < deadline_seconds:
            remaining = deadline_seconds - time.monotonic()
            if remaining <= 0:
                break
            try:
                exit_code = proc.wait(timeout=min(0.5, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
            except (ProcessLookupError, OSError):
                break
    except Exception:
        pass

    if exit_code is None and proc.poll() is None:
        # Deadline reached — kill the process group
        timed_out = True
        kill_group(proc, grace_s=5.0, escalate=True, label=f"suite_runner:{run_id}")

    # Final wait to collect exit code
    if not timed_out:
        try:
            exit_code = proc.wait(timeout=2)
        except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
            exit_code = proc.poll()

    duration = time.monotonic() - t0
    log_fh.close()

    # Read back the log for parsing
    raw_output = raw_log_path.read_text(encoding="utf-8")

    # Parse
    parsed = _parse_pytest_output(raw_output)

    # --- Exit-code mapping: 0→passed, 1→failed, 2→runner_error,
    #     5→not_applicable, other→runner_error.  (Do NOT infer green from
    #     absent FAILED lines — always use the exit code.) ---
    if timed_out:
        status: SuiteStatus = "timeout"
    elif exit_code is None:
        status = "runner_error"
    elif exit_code == 0:
        status = "passed"
    elif exit_code == 1:
        status = "failed"
    elif exit_code == 2:
        status = "runner_error"
    elif exit_code == 5:
        status = "not_applicable"
    else:
        status = "runner_error"

    collected_ids = parsed["collected_ids"]
    collections_parse_ok = parsed["parse_ok"]

    # --- Fallback: if we got zero collected ids AND exit_code != 5 AND
    #     the command is pytest, try pytest --collect-only -q.
    #     If that also fails, set runner_error. ---
    if (
        not collected_ids
        and exit_code != 5
        and not timed_out
        and "pytest" in command
    ):
        collections_parse_ok = False
        fallback_ids = _run_collect_only(project_dir, command)
        if fallback_ids:
            collected_ids = fallback_ids
            collections_parse_ok = True
        else:
            status = "runner_error"

    return SuiteRunResult(
        run_id=run_id,
        phase=phase,
        command=command,
        duration=duration,
        collected=parsed["collected"],
        collected_ids=collected_ids,
        failures=parsed["failures"],
        passes=parsed["passes"],
        status=status,
        exit_code=exit_code,
        raw_log_path=raw_log_path,
        code_hash=code_hash,
        collections_parse_ok=collections_parse_ok,
    )


# ---------------------------------------------------------------------------
# Append-only ndjson log
# ---------------------------------------------------------------------------

# Thin clock shim — prefer a harness-wide ``clock()`` if one exists;
# otherwise fall back to ``time.time`` for unix-second timestamps.
try:
    from megaplan._core.io import clock  # type: ignore[attr-defined]
except ImportError:
    _now = time.time
else:
    _now = clock  # type: ignore[assignment]


KNOWN_STATUSES: frozenset[str] = frozenset({
    "passed", "failed", "runner_error", "not_applicable", "timeout",
})

REQUIRED_RECORD_FIELDS: frozenset[str] = frozenset({
    "run_id", "phase", "code_hash", "command", "duration",
    "collected", "collected_ids", "failures", "passes", "status",
    "raw_log_path", "collections_parse_ok", "ts",
})


def append_suite_run(plan_dir: Path, result: SuiteRunResult) -> None:
    """Append one JSON-line record to the suite-runs ndjson log.

    We intentionally choose plain ndjson (``open('a')`` + ``os.fsync``) over
    the existing ``append_framed_json_records()`` in ``megaplan/_core/io.py``
    so operators can ``tail -f`` the file — a 4-byte-length-prefix binary
    frame would make human inspection at the gate impractical (gate warning #2).
    """
    ver_dir = plan_dir / "verification"
    ver_dir.mkdir(parents=True, exist_ok=True)

    record: dict[str, object] = {
        "run_id": result.run_id,
        "phase": result.phase,
        "code_hash": result.code_hash,
        "command": result.command,
        "duration": result.duration,
        "collected": result.collected,
        "collected_ids": result.collected_ids,
        "failures": result.failures,
        "passes": result.passes,
        "status": result.status,
        "raw_log_path": str(result.raw_log_path),
        "collections_parse_ok": result.collections_parse_ok,
        "ts": _now(),
    }

    path = ver_dir / "suite_runs.ndjson"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def latest_run_for_phase(plan_dir: Path, phase: str) -> dict[str, Any] | None:
    """Return the most recent record for *phase* from ``suite_runs.ndjson``.

    Returns ``None`` when the log file does not exist or no matching record
    is found.
    """
    path = plan_dir / "verification" / "suite_runs.ndjson"
    if not path.is_file():
        return None

    latest: dict[str, Any] | None = None
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record: dict[str, Any] = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if record.get("phase") == phase:
                # Keep the last one — plain ndjson is append-only so the
                # last matching record is the most recent.
                latest = record
    return latest


def freshness_skip(
    plan_dir: Path, current_code_hash: str, *, phase: str = "post_execute",
) -> SuiteRunResult | None:
    """Check whether a fresh run is needed for *phase*.

    Returns a ``SuiteRunResult`` built from the cached record when the
    cached *code_hash* matches *current_code_hash* and the record passes
    validation.  Returns ``None`` when a fresh run is required (hash
    mismatch **or** cached record fails structural validation).

    On validation failure the function emits a structured warning (via
    ``logging.warning``) so operators can detect silent log corruption.
    """
    record = latest_run_for_phase(plan_dir, phase)
    if record is None:
        return None

    # --- Validate required fields -------------------------------------------------
    missing = REQUIRED_RECORD_FIELDS - set(record.keys())
    if missing:
        logger.warning(
            "freshness_skip: cached %s record %s is missing fields %s; "
            "triggering fresh run.",
            phase,
            record.get("run_id", "<unknown>"),
            sorted(missing),
        )
        return None

    if record.get("status") not in KNOWN_STATUSES:
        logger.warning(
            "freshness_skip: cached %s record %s has unknown status %r; "
            "triggering fresh run.",
            phase,
            record.get("run_id", "<unknown>"),
            record.get("status"),
        )
        return None

    if not isinstance(record.get("failures"), list):
        logger.warning(
            "freshness_skip: cached %s record %s has non-list 'failures'; "
            "triggering fresh run.",
            phase,
            record.get("run_id", "<unknown>"),
        )
        return None

    if not isinstance(record.get("collected_ids"), list):
        logger.warning(
            "freshness_skip: cached %s record %s has non-list 'collected_ids'; "
            "triggering fresh run.",
            phase,
            record.get("run_id", "<unknown>"),
        )
        return None

    # --- Hash match ---------------------------------------------------------------
    if record["code_hash"] != current_code_hash:
        return None

    # Build SuiteRunResult from cached record
    raw_log_path = record.get("raw_log_path", "")
    return SuiteRunResult(
        run_id=str(record["run_id"]),
        phase=str(record["phase"]),
        code_hash=str(record["code_hash"]),
        command=str(record["command"]),
        duration=float(record["duration"]),
        collected=int(record["collected"]),
        collected_ids=list(record["collected_ids"]),
        failures=list(record["failures"]),
        passes=list(record["passes"]),
        status=str(record["status"]),
        exit_code=None,
        raw_log_path=Path(raw_log_path) if raw_log_path else Path(),
        collections_parse_ok=bool(record.get("collections_parse_ok", False)),
    )


def is_baseline_stale(
    plan_dir: Path,
    project_dir: Path,
    *,
    hash_paths: list[str] | None = None,
) -> bool:
    """Return ``True`` when the most recent baseline record's *code_hash*
    no longer matches the current HEAD (or filesystem state when not a repo).

    Used by the post-execute harness to decide whether to re-baseline before
    computing the test delta.  When the baseline is stale the caller should
    set ``baseline_stale=True`` in the verdict and write a fresh baseline
    record before the verification record.
    """
    baseline_record = latest_run_for_phase(plan_dir, "baseline")
    if baseline_record is None:
        # No baseline exists yet — not "stale", just absent.
        return False

    current_hash = _compute_code_hash(project_dir, paths=hash_paths)
    return baseline_record.get("code_hash") != current_hash


# ---------------------------------------------------------------------------
# Failure detail extraction (for the revise-prompt delta block)
# ---------------------------------------------------------------------------

# Regex to parse ``FAILED <nodeid> - <error_type>: <message>`` from the
# pytest short-test-summary (``-rN``) lines.
_FAILED_LINE_RE = re.compile(
    r"^FAILED\s+(?P<nodeid>\S+)(?:\s+-\s+(?P<detail>.+))?$",
    re.MULTILINE,
)

# Traceback header pattern: a long run of underscores with the nodeid
# sandwiched, e.g. ``_________________ test_foo _________________``
# Curly braces are doubled because this is a ``.format()`` template.
_TRACEBACK_HEADER_RE_TEMPLATE = r"_{{10,}}\s+{nodeid_pattern}\s+_{{10,}}"


def extract_failure_details(
    raw_log_path: Path, nodeids: list[str],
) -> list[dict[str, str]]:
    """Parse failure details from the raw log for each *newly_failing* nodeid.

    Returns one ``{nodeid, error_type, message, traceback_head}`` dict per
    nodeid.  *traceback_head* is the first ≤500 chars of the traceback when
    present; when the traceback cannot be parsed the sentinel ``'<could not
    extract>'`` is used.

    **Entries are NEVER dropped:** if a nodeid cannot be located in the log
    at all, every field is set to its sentinel value:
    ``{nodeid, error_type: '<unknown>', message: '<unparsed>',
       traceback_head: '<could not extract>'}``

    Parameters
    ----------
    raw_log_path:
        Path to the raw pytest log file (the ``raw_<run_id>.log`` written by
        :func:`run_suite`).
    nodeids:
        The *newly_failing* nodeids (from the delta) for which to extract
        failure details.  Order is preserved in the output.
    """
    # --- sentinel fallback for every nodeid (used when the log is unreadable) ---
    _sentinel = {
        "error_type": "<unknown>",
        "message": "<unparsed>",
        "traceback_head": "<could not extract>",
    }

    try:
        content = raw_log_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [
            {"nodeid": nid, **_sentinel}
            for nid in nodeids
        ]

    results: list[dict[str, str]] = []

    # --- pre-index all FAILED lines by nodeid for O(1) lookup ---
    failed_by_nodeid: dict[str, str] = {}  # nodeid → detail part
    for m in _FAILED_LINE_RE.finditer(content):
        nid = m.group("nodeid")
        if nid:
            failed_by_nodeid[nid] = m.group("detail") or ""

    for nid in nodeids:
        detail: dict[str, str] = {"nodeid": nid, **_sentinel}

        # --- (a) extract error_type + message from the FAILED summary line ---
        summary_detail = failed_by_nodeid.get(nid)
        if summary_detail is not None:
            # ``summary_detail`` may be e.g. ``AssertionError: expected 2 but got 1``
            # or just ``assert 1 == 2`` (no explicit exception type)
            parts = summary_detail.split(": ", 1)
            if len(parts) == 2 and parts[0]:
                detail["error_type"] = parts[0].strip()
                detail["message"] = parts[1].strip()
            elif summary_detail.strip():
                detail["message"] = summary_detail.strip()

        # --- (b) attempt to extract traceback_head from the raw log ---
        # Build a regex to find the traceback header for this nodeid.
        # We escape the nodeid (it may contain regex metacharacters like `.`).
        tb_header_pat = _TRACEBACK_HEADER_RE_TEMPLATE.format(
            nodeid_pattern=re.escape(nid)
        )
        tb_match = re.search(tb_header_pat, content)
        if tb_match:
            tb_start = tb_match.end()
            tb_rest = content[tb_start:]

            # The traceback ends at the next separator: another traceback
            # header, a FAILED/PASSED line, a pytest ``=====`` separator,
            # or a blank-line followed by a non-indented line.
            end_pos: int = len(tb_rest)
            _end_patterns = [
                r"\n=+",            # pytest separator
                r"\n_{10,}",        # next traceback header
                r"\nFAILED\s+",     # short-test-summary FAILED line
                r"\nPASSED\s+",     # short-test-summary PASSED line
                r"\n\n[^\s]",       # blank line followed by non-whitespace
            ]
            for ep in _end_patterns:
                m = re.search(ep, tb_rest)
                if m is not None and m.start() < end_pos:
                    end_pos = m.start()

            tb_slice = tb_rest[:end_pos].strip()
            if tb_slice:
                detail["traceback_head"] = tb_slice[:500]

        results.append(detail)

    return results
