"""Small, single-operator periodic fixer for registered Megaplan sessions.

The runner intentionally has no dependency on the watchdog, repair queue,
managed-agent service, or L1/L2/L3 contracts.  Deterministic code supplies only
the safety shell: discovery, pause/completion skips, a stable retry brake,
redaction, a singleton lock, and independent before/after evidence.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.cloud.redact import redact_payload, redact_text


TERMINAL_STATES = frozenset({"complete", "completed", "done", "success", "succeeded"})
PAUSED_STATES = frozenset({"paused", "operator_paused"})
VOLATILE_KEYS = frozenset(
    {
        "at",
        "completed_at",
        "created_at",
        "heartbeat_at",
        "last_checked_at",
        "last_seen_at",
        "mtime",
        "observed_at",
        "recorded_at",
        "started_at",
        "timestamp",
        "updated_at",
    }
)
SIDECAR_SUFFIXES = (
    ".chain-health.progress.json",
    ".needs-human.json",
    ".progress.json",
    ".reap-progress.json",
    ".repair-data.json",
    ".repair-progress.json",
)
DEFAULT_MARKER_DIR = Path("/workspace/.megaplan/cloud-sessions")
DEFAULT_REPORT_DIR = Path("/workspace/audit-reports")
DEFAULT_STATE_FILE = Path("/workspace/.megaplan/simple-fixer/attempts.json")
DEFAULT_LOCK_FILE = Path("/workspace/.megaplan/simple-fixer/run.lock")
DEFAULT_SOURCE_ROOT = Path("/workspace/arnold")
MAX_UNCHANGED_ATTEMPTS = 2


@dataclass(frozen=True)
class SessionSnapshot:
    session: str
    workspace: str
    spec: str
    run_kind: str
    plan_name: str
    disposition: str
    fingerprint: str
    live: bool | None
    terminal: bool
    completed_count: int
    current_plan: str
    progress_cursor: str
    heartbeat_at: str
    evidence: tuple[dict[str, Any], ...]

    def public(self) -> dict[str, Any]:
        return {
            "session": self.session,
            "workspace": self.workspace,
            "spec": self.spec,
            "run_kind": self.run_kind,
            "plan_name": self.plan_name,
            "disposition": self.disposition,
            "fingerprint": self.fingerprint,
            "live": self.live,
            "terminal": self.terminal,
            "completed_count": self.completed_count,
            "current_plan": self.current_plan,
            "progress_cursor": self.progress_cursor,
            "heartbeat_at": self.heartbeat_at,
            "evidence": list(self.evidence),
        }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(redact_payload(dict(payload), env=os.environ), handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def _stable(value: Any) -> Any:
    """Remove clocks and ordering noise while preserving operational evidence."""
    if isinstance(value, dict):
        return {
            str(key): _stable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key).lower() not in VOLATILE_KEYS
            and not str(key).lower().endswith(("_at", "_timestamp"))
        }
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def _digest(value: Any) -> str:
    wire = json.dumps(_stable(value), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(wire.encode("utf-8")).hexdigest()


def _tail_digest(path: Path, limit: int = 65536) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - limit))
            data = handle.read()
    except OSError:
        return ""
    return hashlib.sha256(data).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _active_pause(value: Any) -> bool:
    if value is True:
        return True
    return isinstance(value, Mapping) and value.get("active") is True


def _explicit_human_gate(payload: Mapping[str, Any]) -> bool:
    if _active_pause(payload.get("operator_pause")):
        return True
    canonical = _text(payload.get("canonical_state") or payload.get("resolver_state")).upper()
    if canonical == "HUMAN_ACTION_REQUIRED":
        return True
    needs_human = payload.get("needs_human")
    if needs_human is True:
        return True
    if isinstance(needs_human, Mapping) and (
        needs_human.get("present") is True or needs_human.get("active") is True
    ):
        return True
    return bool(_text(payload.get("human_gate_type") or payload.get("gate_type")))


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _heartbeat(payloads: Sequence[Mapping[str, Any]]) -> str:
    values = []
    for payload in payloads:
        for key in ("heartbeat_at", "last_heartbeat_at", "last_activity_at", "updated_at"):
            value = _text(payload.get(key))
            if value:
                values.append(value)
    return max(values, default="")


def _state_paths(marker: Mapping[str, Any], workspace: Path, spec: Path | None) -> list[Path]:
    paths: list[Path] = []
    for key in ("chain_state", "chain_state_path", "state_path"):
        raw = _text(marker.get(key))
        if raw:
            paths.append(Path(raw))
    if spec is not None:
        digest = hashlib.sha1(str(spec.resolve()).encode("utf-8")).hexdigest()[:12]
        paths.append(workspace / ".megaplan" / "plans" / ".chains" / f"{spec.stem}-{digest}.json")
    plan_name = _text(marker.get("plan_name"))
    if plan_name:
        paths.extend(
            (
                workspace / ".megaplan" / "plans" / plan_name / "state.json",
                workspace / ".megaplan" / "plans" / f"{plan_name}.json",
            )
        )
    return list(dict.fromkeys(paths))


def _tmux_live(session: str) -> bool | None:
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", f"={session}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        return None
    return result.returncode == 0


def _marker_paths(marker_dir: Path) -> list[Path]:
    if not marker_dir.is_dir():
        return []
    return [
        path
        for path in sorted(marker_dir.glob("*.json"))
        if not path.name.endswith(SIDECAR_SUFFIXES)
        and path.parent == marker_dir
        and not path.name.startswith(".")
    ]


def snapshot_marker(path: Path, marker_dir: Path) -> SessionSnapshot:
    marker = _read_json(path)
    session = _text(marker.get("session")) or path.stem
    workspace_raw = _text(marker.get("workspace") or marker.get("project_dir"))
    workspace = Path(workspace_raw) if workspace_raw else Path("/")
    spec_raw = _text(marker.get("remote_spec") or marker.get("spec"))
    spec = Path(spec_raw) if spec_raw else None
    state_records: list[dict[str, Any]] = []
    state_payloads: list[dict[str, Any]] = []
    for state_path in _state_paths(marker, workspace, spec):
        if not state_path.is_file():
            continue
        payload = _read_json(state_path)
        state_payloads.append(payload)
        state_records.append({"kind": "state", "path": str(state_path), "sha256": _digest(payload)})

    sidecar_records: list[dict[str, Any]] = []
    sidecar_payloads: list[dict[str, Any]] = []
    for suffix in SIDECAR_SUFFIXES:
        sidecar = marker_dir / f"{session}{suffix}"
        if not sidecar.is_file():
            continue
        payload = _read_json(sidecar)
        sidecar_payloads.append(payload)
        sidecar_records.append({"kind": suffix[1:-5], "path": str(sidecar), "sha256": _digest(payload)})
    repair_data = marker_dir / "repair-data" / f"{session}.repair-data.json"
    if repair_data.is_file():
        payload = _read_json(repair_data)
        sidecar_payloads.append(payload)
        sidecar_records.append(
            {"kind": "repair-data", "path": str(repair_data), "sha256": _digest(payload)}
        )

    log_records: list[dict[str, Any]] = []
    log_candidates = []
    for key in ("log", "log_path", "chain_log"):
        raw = _text(marker.get(key))
        if raw:
            log_candidates.append(Path(raw))
    if workspace_raw:
        log_candidates.extend(
            (
                workspace / ".megaplan" / f"cloud-chain-{session}.log",
                workspace / ".megaplan" / "cloud-chain.log",
            )
        )
    for log_path in dict.fromkeys(log_candidates):
        digest = _tail_digest(log_path)
        if digest:
            log_records.append({"kind": "log-tail", "path": str(log_path), "sha256": digest})

    live = _tmux_live(session)
    state_words = {
        _text(marker.get(key)).lower()
        for key in ("status", "state", "current_state", "last_state", "outcome")
        if _text(marker.get(key))
    }
    for payload in state_payloads:
        state_words.update(
            _text(payload.get(key)).lower()
            for key in ("status", "state", "current_state", "last_state", "outcome")
            if _text(payload.get(key))
        )
    paused = any(word in PAUSED_STATES for word in state_words) or _active_pause(
        marker.get("operator_pause")
    )
    paused = paused or any(
        _active_pause(payload.get("operator_pause"))
        or _active_pause(
            payload.get("metadata", {}).get("operator_pause")
            if isinstance(payload.get("metadata"), Mapping)
            else None
        )
        for payload in state_payloads
    )
    all_payloads = [marker, *state_payloads, *sidecar_payloads]
    explicit_human_gate = any(_explicit_human_gate(payload) for payload in all_payloads)
    if explicit_human_gate and state_words & {"awaiting_human", "awaiting_pr_merge"}:
        paused = True
    current_plan = next(
        (
            _text(payload.get("current_plan_name") or payload.get("current_plan"))
            for payload in reversed(all_payloads)
            if _text(payload.get("current_plan_name") or payload.get("current_plan"))
        ),
        "",
    )
    chain_complete = any(
        payload.get("chain_complete") is True or payload.get("complete") is True
        for payload in all_payloads
    )
    terminal = chain_complete or bool(state_words & TERMINAL_STATES)
    completed_count = max(
        (
            max(
                _integer(payload.get("completed_count")),
                len(payload.get("completed", []))
                if isinstance(payload.get("completed"), list)
                else 0,
            )
            for payload in all_payloads
        ),
        default=0,
    )
    cursor_payload = []
    for payload in all_payloads:
        active_step = payload.get("active_step")
        if not isinstance(active_step, Mapping):
            active_step = {}
        cursor_payload.append(
            {
                "current_plan": _text(
                    payload.get("current_plan_name") or payload.get("current_plan")
                ),
                "completed_count": max(
                    _integer(payload.get("completed_count")),
                    len(payload.get("completed", []))
                    if isinstance(payload.get("completed"), list)
                    else 0,
                ),
                "iteration": _integer(payload.get("iteration")),
                "phase": _text(active_step.get("phase")),
                "attempt": _integer(active_step.get("attempt")),
                "resume_cursor": _stable(payload.get("resume_cursor")),
            }
        )
    progress_cursor = _digest(cursor_payload)
    heartbeat_at = _heartbeat(all_payloads)
    disposition = "completed" if terminal else "paused" if paused else "nonterminal"

    evidence = (
        {"kind": "marker", "path": str(path), "sha256": _digest(marker)},
        *state_records,
        *sidecar_records,
        *log_records,
        {"kind": "process", "live": live},
    )
    fingerprint_payload = {
        "session": session,
        "marker": marker,
        "states": state_payloads,
        "sidecars": sidecar_payloads,
        "logs": log_records,
        "live": live,
    }
    return SessionSnapshot(
        session=session,
        workspace=workspace_raw,
        spec=spec_raw,
        run_kind=_text(marker.get("run_kind")) or "unknown",
        plan_name=_text(marker.get("plan_name")),
        disposition=disposition,
        fingerprint=_digest(fingerprint_payload),
        live=live,
        terminal=terminal,
        completed_count=completed_count,
        current_plan=current_plan,
        progress_cursor=progress_cursor,
        heartbeat_at=heartbeat_at,
        evidence=tuple(evidence),
    )


def discover(marker_dir: Path) -> list[SessionSnapshot]:
    return [snapshot_marker(path, marker_dir) for path in _marker_paths(marker_dir)]


def _load_attempts(path: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json(path)
    sessions = payload.get("sessions")
    if not isinstance(sessions, dict):
        return {}
    return {
        str(key): dict(value)
        for key, value in sessions.items()
        if isinstance(value, dict)
    }


def _attempt_policy(
    snapshots: Sequence[SessionSnapshot],
    attempts: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        previous = attempts.get(snapshot.session, {})
        unchanged = previous.get("fingerprint") == snapshot.fingerprint
        count = int(previous.get("unchanged_attempts", 0)) if unchanged else 0
        decisions[snapshot.session] = {
            "fingerprint": snapshot.fingerprint,
            "unchanged_attempts": count,
            "mutation_allowed": snapshot.disposition == "nonterminal"
            and count < MAX_UNCHANGED_ATTEMPTS,
            "reason": (
                f"unchanged_retry_cap_{MAX_UNCHANGED_ATTEMPTS}"
                if snapshot.disposition == "nonterminal" and count >= MAX_UNCHANGED_ATTEMPTS
                else f"skip_{snapshot.disposition}"
                if snapshot.disposition != "nonterminal"
                else "eligible"
            ),
        }
    return decisions


def _schema() -> dict[str, Any]:
    outcome = {
        "type": "object",
        "additionalProperties": False,
        "required": ["session", "result", "summary", "evidence"],
        "properties": {
            "session": {"type": "string"},
            "result": {"enum": ["healthy", "fixed", "externally_blocked"]},
            "summary": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["outcomes"],
        "properties": {"outcomes": {"type": "array", "items": outcome}},
    }


def _operator_prompt(
    snapshots: Sequence[SessionSnapshot],
    decisions: Mapping[str, Mapping[str, Any]],
    source_root: Path,
) -> str:
    inventory = []
    for item in snapshots:
        public = item.public()
        public["mutation_allowed"] = decisions[item.session]["mutation_allowed"]
        public["retry_reason"] = decisions[item.session]["reason"]
        inventory.append(public)
    return f"""You are the sole periodic Megaplan fixer on this machine.

There is exactly one operator in this cycle: you. Work sequentially. Do not
spawn, delegate to, message, or launch any subagent, managed agent, investigator,
reviewer, watchdog, repair-loop, meta-repair, or other model process.

Inspect every session in the inventory below. Completed and explicitly
operator-paused sessions are preserved and skipped. For a nonterminal session
whose mutation_allowed value is false, inspect and report only: make no change.
For each mutation_allowed session, leave it alone if it is alive and making
meaningful progress. Otherwise inspect live processes, marker and chain state,
recent logs, repository state, and relevant external state; find and fix the
concrete root cause. If old repair machinery caused the problem, simplify or
repair that machinery instead of hand-advancing state.

Run focused tests, deploy the exact tested version when deployment is necessary,
retrigger the original failed operation, and verify the real session advances.
Do not accept your own statement as proof; cite fresh paths, commands, hashes, or
state. Do not fabricate progress, weaken completion guards, expose or rotate
credentials, delete user data, rewrite unrelated work, or deploy unrelated apps.

Return only the requested JSON outcome object, one outcome for each nonterminal
session. Use healthy, fixed, or externally_blocked.

Arnold source root: {source_root}
Session inventory:
{json.dumps(inventory, sort_keys=True, indent=2)}
"""


def _run_codex(
    *,
    prompt: str,
    cycle_dir: Path,
    source_root: Path,
    codex_bin: str,
    model: str,
    timeout: int,
) -> tuple[int, dict[str, Any], str]:
    schema_path = cycle_dir / "output-schema.json"
    last_path = cycle_dir / "operator-result.json"
    _atomic_json(schema_path, _schema())
    command = [
        codex_bin,
        "exec",
        "--json",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(last_path),
        "--sandbox",
        "danger-full-access",
        "--ephemeral",
        "-C",
        str(source_root),
        "-m",
        model,
        "-",
    ]
    try:
        proc = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        returncode = proc.returncode
        transcript = proc.stdout + ("\n[stderr]\n" + proc.stderr if proc.stderr else "")
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else exc.stdout or ""
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr or ""
        transcript = stdout + "\n[runner] operator timed out\n" + stderr
    (cycle_dir / "operator-transcript.jsonl").write_text(
        redact_text(transcript, env=os.environ), encoding="utf-8"
    )
    result = _read_json(last_path)
    return returncode, result, command[0]


def _markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Megaplan three-hour fixer",
        "",
        f"- Cycle: `{report['cycle_id']}`",
        f"- Operator launched: `{str(report['operator']['launched']).lower()}`",
        f"- Operator exit: `{report['operator'].get('exit_code')}`",
        "",
        "## Sessions",
        "",
    ]
    for item in report["sessions"]:
        lines.extend(
            (
                f"### {item['session']}",
                "",
                f"- Before: `{item['before_disposition']}`",
                f"- Retry decision: `{item['retry_reason']}`",
                f"- Independent verification: `{item['verification']}`",
                f"- Fingerprint changed: `{str(item['fingerprint_changed']).lower()}`",
                f"- Claimed result: `{item.get('claimed_result') or 'none'}`",
                "",
            )
        )
    return "\n".join(lines)


def _fresh_heartbeat(value: str, now: datetime) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    age = (now - parsed.astimezone(timezone.utc)).total_seconds()
    return 0 <= age <= 30 * 60


def _verified_progress(
    before: SessionSnapshot,
    after: SessionSnapshot | None,
    now: datetime,
) -> str:
    if after is None:
        return "session_evidence_missing"
    if not before.terminal and after.terminal:
        return "terminal_transition"
    if after.completed_count > before.completed_count:
        return "completed_count_advanced"
    if (
        before.current_plan
        and after.current_plan
        and before.current_plan != after.current_plan
    ):
        return "current_plan_advanced"
    if after.progress_cursor != before.progress_cursor:
        return "state_cursor_advanced"
    if before.live is not True and after.live is True and _fresh_heartbeat(after.heartbeat_at, now):
        return "fresh_live_transition"
    return "no_independent_progress"


def run_cycle(args: argparse.Namespace) -> int:
    marker_dir = Path(args.marker_dir)
    report_dir = Path(args.report_dir)
    state_file = Path(args.state_file)
    lock_file = Path(args.lock_file)
    source_root = Path(args.source_root)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = lock_file.open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("arnold-progress-auditor: singleton already running")
        return 0

    now = datetime.now(timezone.utc)
    cycle_id = now.strftime("%Y%m%dT%H%M%S.%fZ")
    cycle_dir = report_dir / cycle_id
    cycle_dir.mkdir(parents=True, exist_ok=False)
    before = discover(marker_dir)
    attempts = _load_attempts(state_file)
    decisions = _attempt_policy(before, attempts)

    nonterminal = [item for item in before if item.disposition == "nonterminal"]
    eligible = [item for item in nonterminal if decisions[item.session]["mutation_allowed"]]
    launched = bool(eligible)
    operator_exit: int | None = None
    operator_result: dict[str, Any] = {}
    if launched:
        # Count an authorized scheduled attempt before launch, so crashes cannot
        # evade the stable-fingerprint retry brake.
        for item in eligible:
            decision = decisions[item.session]
            if decision["mutation_allowed"]:
                decision["unchanged_attempts"] += 1
        _atomic_json(
            state_file,
            {
                "schema_version": 1,
                "sessions": decisions,
            },
        )
        prompt = _operator_prompt(before, decisions, source_root)
        (cycle_dir / "operator-prompt.txt").write_text(
            redact_text(prompt, env=os.environ), encoding="utf-8"
        )
        operator_exit, operator_result, _ = _run_codex(
            prompt=prompt,
            cycle_dir=cycle_dir,
            source_root=source_root,
            codex_bin=args.codex_bin,
            model=args.model,
            timeout=args.timeout,
        )
    else:
        _atomic_json(state_file, {"schema_version": 1, "sessions": decisions})

    after_by_session = {item.session: item for item in discover(marker_dir)}
    claimed = {
        _text(item.get("session")): item
        for item in operator_result.get("outcomes", [])
        if isinstance(item, dict) and _text(item.get("session"))
    }
    session_reports = []
    for item in before:
        after = after_by_session.get(item.session)
        changed = bool(after and after.fingerprint != item.fingerprint)
        decision = decisions[item.session]
        if item.disposition != "nonterminal":
            verification = f"preserved_{item.disposition}"
        elif not decision["mutation_allowed"]:
            verification = "retry_capped_no_mutation_authorized"
        else:
            verification = _verified_progress(item, after, datetime.now(timezone.utc))
        claim = claimed.get(item.session, {})
        session_reports.append(
            {
                "session": item.session,
                "before_disposition": item.disposition,
                "before_fingerprint": item.fingerprint,
                "after_fingerprint": after.fingerprint if after else None,
                "fingerprint_changed": changed,
                "retry_reason": decision["reason"],
                "unchanged_attempts": decision["unchanged_attempts"],
                "mutation_allowed": decision["mutation_allowed"],
                "verification": verification,
                "claimed_result": claim.get("result"),
                "claimed_summary": claim.get("summary"),
                "claimed_evidence": claim.get("evidence", []),
            }
        )
    report = redact_payload(
        {
            "schema_version": 1,
            "cycle_id": cycle_id,
            "started_at": now.isoformat(),
            "operator": {
                "launched": launched,
                "count": 1 if launched else 0,
                "exit_code": operator_exit,
                "model": args.model if launched else None,
                "children_allowed": False,
            },
            "sessions": session_reports,
        },
        env=os.environ,
    )
    _atomic_json(cycle_dir / "report.json", report)
    (cycle_dir / "report.md").write_text(_markdown(report), encoding="utf-8")
    latest = report_dir / "latest.json"
    _atomic_json(latest, report)
    print(f"arnold-progress-auditor: report={cycle_dir / 'report.json'}")
    return 0 if operator_exit in (None, 0) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--marker-dir", default=os.getenv("MEGAPLAN_AUDIT_MARKER_DIR") or str(DEFAULT_MARKER_DIR)
    )
    parser.add_argument(
        "--report-dir", default=os.getenv("MEGAPLAN_AUDIT_REPORT_DIR") or str(DEFAULT_REPORT_DIR)
    )
    parser.add_argument(
        "--state-file", default=os.getenv("MEGAPLAN_SIMPLE_FIXER_STATE") or str(DEFAULT_STATE_FILE)
    )
    parser.add_argument(
        "--lock-file", default=os.getenv("MEGAPLAN_SIMPLE_FIXER_LOCK") or str(DEFAULT_LOCK_FILE)
    )
    parser.add_argument(
        "--source-root",
        default=os.getenv("MEGAPLAN_AUDIT_ARNOLD_SRC") or str(DEFAULT_SOURCE_ROOT),
    )
    parser.add_argument("--codex-bin", default=os.getenv("MEGAPLAN_SIMPLE_FIXER_CODEX_BIN", "codex"))
    parser.add_argument(
        "--model", default=os.getenv("MEGAPLAN_SIMPLE_FIXER_MODEL") or "gpt-5.6-sol"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.getenv("MEGAPLAN_SIMPLE_FIXER_TIMEOUT_SECS") or "7200"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return run_cycle(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
