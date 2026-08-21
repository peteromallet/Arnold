#!/usr/bin/env python3
"""Status-trigger babysitter launch module.

The watchdog's status trigger (``MEGAPLAN_SUPERFIXER_ONLY=1``) Popen's
``arnold-babysitter``, which executes this module.  The babysitter is ONE
detached ``hermes:deepseek:deepseek-v4-flash`` managed agent whose goal prompt
drives the entire recovery flow itself — bounded swarm -> codex -> implement
-> relaunch -> prove (see the rendered goal).  There is deliberately NO coded
multi-stage orchestrator: the single agent IS the orchestrator.

Flow (fail closed at every step — the caller's grace poll turns an early
non-zero rc into a hard abort, never a fallthrough to another repair route):

    1. Parse the watchdog's flags (--goal-file, --session, --workspace,
       --plan, --run-kind, --occurrence, --remote-spec, --run-id, --run-root,
       --mode) with ARNOLD_BABYSITTER_* env fallbacks.
    2. Dedup: if a babysitter receipt for this session already shows a live
       supervisor pid for the same occurrence digest (and that pid is not
       us), exit 0 with status=already_running.  No second agent, no queue
       enqueue, no claim.
    3. Resolve the goal file (--goal-file / ARNOLD_BABYSITTER_GOAL_FILE), or
       render it via the live engine's
       ``skills/babysitter/scripts/render_babysitter_goal.py`` (watchdog-
       compatible engine-root resolution).
    4. Launch ONE managed Flash agent through
       ``arnold_pipelines.megaplan.managed_agent`` (backend=babysitter); the
       worker is ``launch_hermes_agent.py --model=hermes:deepseek:deepseek-v4-flash
       --toolsets=file,web,terminal --query-file=<goal> --project-dir=<engine>``
       so the agent can run fan.py and codex exec.  This process stays alive
       as the managed-agent supervisor for the whole run, so the watchdog's
       early-rc check and receipt pid liveness are honest.
    5. Write an ``arnold.superfixer.babysitter_launch_receipt.v1`` receipt
       (status running -> terminal, babysitter_pid, run_id, occurrence
       digest, managed run id) and propagate the worker rc.

Env overrides (all optional):
    ARNOLD_BABYSITTER_SESSION / _WORKSPACE / _PLAN / _RUN_KIND / _OCCURRENCE /
    _GOAL_FILE / _MARKER_DIR / _REPAIR_DATA_DIR   watchdog-provided context
    ARNOLD_BABYSITTER_MODEL       Flash model (default hermes:deepseek:deepseek-v4-flash)
    ARNOLD_BABYSITTER_DIFFICULTY  managed-run difficulty D1-D10 (default 8)
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import runpy
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from arnold_pipelines.megaplan.cloud.babysitter.routing import (
    cli_model,
    resolve_babysitter_routing,
)
from arnold_pipelines.megaplan.managed_agent import (
    ManagedCommandSpec,
    machine_origin_provenance,
    run_managed_command,
    stable_managed_run_id,
)

LAUNCH_RECEIPT_SCHEMA = "arnold.superfixer.babysitter_launch_receipt.v1"
DISPATCH_RECEIPT_NAME = "{session}.babysitter-receipt.json"
LAUNCH_RECEIPT_NAME = "{session}.babysitter-launch-receipt.json"

DEFAULT_MODEL = "hermes:deepseek:deepseek-v4-flash"
TOOLSETS = "file,web,terminal"
RUN_KIND = "automatic_watchdog_source_repair"
ORIGIN_KIND = "watchdog_source_repair"
ORIGIN_COMPONENT = "arnold-babysitter"
ROUTE_CLASS = "watchdog_babysitter"
BACKEND = "babysitter"
TASK_KIND = "autonomous"
REASONING_EFFORT = "bounded"
DEFAULT_DIFFICULTY = 8

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _provenance_safe(text: str) -> str:
    """Keep the managed-agent provenance-safe charset (letters, digits, . _ : / -)."""
    return "".join(
        character if character in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:/-" else "_"
        for character in text
    )


def _eprint(message: str) -> None:
    print(message, file=sys.stderr)
    sys.stderr.flush()


def _pid_live(pid: object) -> bool:
    """Portable pid liveness probe (mirrors managed_agent._pid_live)."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        state = stat.rsplit(") ", 1)[1].split()[0]
        if state == "Z":
            return False
    except (OSError, IndexError):
        pass
    return True


BWRAP_PROBE_ARGV = ("bwrap", "--ro-bind", "/", "/", "--", "true")
SANDBOX_DANGER_FULL_ACCESS = "danger-full-access"
SANDBOX_READ_ONLY = "read-only"


def probe_bwrap_userns(*, run=subprocess.run) -> bool:
    """True when ``bwrap --ro-bind / / -- true`` succeeds on this host.

    Probe failure is the transport signal that ``--sandbox read-only`` cannot
    be created here. Tests inject ``run`` so the fixture never depends on a
    real cloud/container.
    """
    try:
        completed = run(
            BWRAP_PROBE_ARGV,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except (OSError, FileNotFoundError):
        return False
    return int(getattr(completed, "returncode", 1) or 1) == 0


def investigator_sandbox_flag(*, bwrap_ok: bool | None = None, run=subprocess.run) -> str:
    """One sandbox flag for goal text and every sandbox-bearing exec argv.

    Process-level transport only. Product read-only remains a no-mutation
    contract plus pre/post fingerprints, not a sandbox claim. Probe failure
    never emits ``--sandbox read-only``.
    """
    if bwrap_ok is None:
        bwrap_ok = probe_bwrap_userns(run=run)
    return SANDBOX_DANGER_FULL_ACCESS if not bwrap_ok else SANDBOX_READ_ONLY


def _ctx_sandbox(ctx: dict[str, Any]) -> str:
    sandbox = ctx.get("investigator_sandbox")
    if not sandbox:
        sandbox = investigator_sandbox_flag()
        ctx["investigator_sandbox"] = sandbox
    return str(sandbox)


def investigator_exec_argv(*, sandbox: str, investigator_model: str) -> list[str]:
    """Sandbox-bearing investigator argv that must agree with goal text."""
    return [
        "codex",
        "exec",
        "--sandbox",
        sandbox,
        "--ephemeral",
        "-m",
        investigator_model.split(":", 1)[-1],
        "-c",
        "model_reasoning_effort=high",
        "-",
    ]


def _recorded_babysitter_pid(payload: dict[str, Any]) -> object:
    """Liveness evidence is the recorded babysitter_pid, never supervisor_pid."""
    return payload.get("babysitter_pid")


def classify_owner_receipt(payload: object) -> dict[str, Any]:
    """Classify a launched/running receipt from recorded babysitter_pid liveness.

    A recorded PID is evidence of liveness only, never authority. Dead,
    invalid, non-positive, boolean, and zombie PIDs are reclaimable; only a
    live recorded babysitter_pid stands down a new launch. ``supervisor_pid``
    is compatibility and must not override babysitter_pid.
    """
    if not isinstance(payload, dict):
        return {
            "active_owner": False,
            "reclaimable": True,
            "status": "failed",
            "reason": "invalid_receipt",
        }
    status = str(payload.get("status") or "")
    if status not in {"launched", "running"}:
        return {
            "active_owner": False,
            "reclaimable": status in {"failed", "completed", "interrupted", "already_running"},
            "status": status or "unknown",
            "reason": "not_active_status",
        }
    pid = _recorded_babysitter_pid(payload)
    if _pid_live(pid):
        return {
            "active_owner": True,
            "reclaimable": False,
            "status": status,
            "reason": "live_babysitter_pid",
        }
    return {
        "active_owner": False,
        "reclaimable": True,
        "status": "failed",
        "reason": "dead_or_invalid_babysitter_pid",
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_product_tree_paths(root: Path) -> list[Path]:
    skip_names = {".git", ".megaplan", "__pycache__", ".pytest_cache", ".babysitter-runs"}
    paths: list[Path] = []
    if not root.is_dir():
        return paths
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in sorted(dirnames) if name not in skip_names]
        current_path = Path(current)
        for name in sorted(filenames):
            if name.endswith(".pyc"):
                continue
            paths.append(current_path / name)
    return paths


def product_tree_fingerprint(root: Path) -> str:
    """Canonical product-tree fingerprint from disposable/canonical files."""
    digest = hashlib.sha256()
    root = Path(root)
    for path in _collect_product_tree_paths(root):
        rel = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(rel)
        digest.update(b"\0")
        try:
            digest.update(_sha256_file(path).encode("ascii"))
        except OSError:
            digest.update(b"unreadable")
        digest.update(b"\n")
    return digest.hexdigest()


def _canonical_plan_state_path(workspace: str, plan_name: str) -> Path:
    return Path(workspace) / ".megaplan" / "plans" / plan_name / "state.json"


def _canonical_failure_fingerprint(plan_payload: dict[str, Any]) -> str:
    failure = plan_payload.get("latest_failure")
    if not isinstance(failure, dict):
        failure = {}
    explicit = str(
        failure.get("fingerprint")
        or failure.get("failure_fingerprint")
        or plan_payload.get("failure_fingerprint")
        or ""
    ).strip()
    if explicit:
        return explicit
    parts = (
        str(plan_payload.get("current_state") or ""),
        str(failure.get("kind") or ""),
        str(failure.get("message") or ""),
    )
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def evaluate_canonical_honesty(
    ctx: dict[str, Any],
    *,
    pre_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Fail closed from canonical/disposable state, never a self-report."""
    plan_name = str(ctx.get("plan") or "").strip()
    workspace = str(ctx.get("workspace") or "").strip()
    reasons: list[str] = []
    still_blocked = False
    fingerprint_mismatch = False
    post_fingerprint = ""
    failure_fingerprint = ""
    current_state = ""
    if workspace:
        post_fingerprint = product_tree_fingerprint(Path(workspace))
    if plan_name and workspace:
        plan_state_path = _canonical_plan_state_path(workspace, plan_name)
        if plan_state_path.is_file():
            try:
                plan_payload = json.loads(plan_state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                reasons.append(f"canonical_state_unreadable:{type(exc).__name__}")
                plan_payload = {}
            if isinstance(plan_payload, dict) and plan_payload:
                current_state = str(plan_payload.get("current_state") or "")
                failure_fingerprint = _canonical_failure_fingerprint(plan_payload)
                if current_state in {"blocked", "failed"}:
                    still_blocked = True
                    failure = plan_payload.get("latest_failure") or {}
                    failure_kind = (
                        str(failure.get("kind") or "") if isinstance(failure, dict) else ""
                    )
                    reasons.append(
                        f"plan still {current_state} after fixer exit; "
                        f"failure_kind={failure_kind or 'unknown'}"
                    )
                recorded_pre = str(ctx.get("pre_failure_fingerprint") or "").strip()
                if recorded_pre and failure_fingerprint and recorded_pre == failure_fingerprint:
                    fingerprint_mismatch = True
                    reasons.append("failure_fingerprint_unchanged")
                expected_failure = str(ctx.get("occurrence") or "").strip()
                if (
                    expected_failure
                    and failure_fingerprint
                    and expected_failure == failure_fingerprint
                    and "failure_fingerprint_unchanged" not in reasons
                ):
                    fingerprint_mismatch = True
                    reasons.append("failure_fingerprint_unchanged")
        expected_pre = pre_fingerprint or str(ctx.get("pre_product_tree_fingerprint") or "")
        if (
            expected_pre
            and post_fingerprint
            and post_fingerprint != expected_pre
            and (still_blocked or fingerprint_mismatch)
        ):
            fingerprint_mismatch = True
            reasons.append("product_tree_fingerprint_mismatch")
    failed = still_blocked or fingerprint_mismatch or bool(reasons)
    return {
        "failed": failed,
        "still_blocked": still_blocked,
        "fingerprint_mismatch": fingerprint_mismatch,
        "current_state": current_state,
        "failure_fingerprint": failure_fingerprint,
        "post_fingerprint": post_fingerprint,
        "reason": "; ".join(reasons),
    }


def terminal_transport_result(
    *,
    worker_rc: int,
    managed_terminal: str,
    honesty: dict[str, Any] | None = None,
) -> tuple[str, int, str]:
    """One enforcement point: receipt status and process rc are one fact."""
    honesty = honesty or {}
    if managed_terminal == "interrupted":
        status = "interrupted"
    elif worker_rc == 0 and managed_terminal == "completed":
        status = "completed"
    else:
        status = "failed"
    reason = str(honesty.get("reason") or "")
    if status == "completed" and honesty.get("failed"):
        status = "failed"
        if not reason:
            reason = "honesty_downgrade"
    if status == "failed":
        return status, (1 if int(worker_rc) == 0 else int(worker_rc)), reason
    return status, int(worker_rc), reason


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def _engine_roots() -> list[Path]:
    """Live engine roots in watchdog precedence, our own tree as the fallback.

    Mirrors the watchdog's ``_superfixer_engine_roots`` so the babysitter
    resolves the goal renderer / hermes launcher from the SAME runtime the
    watchdog dispatch used, never a stale hardcoded tree.
    """
    roots: list[Path] = []
    for env_name in (
        "ARNOLD_WATCHDOG_MANIFEST_RUNTIME_ROOT",
        "ARNOLD_WATCHDOG_RUNTIME_SRC",
        "SRC_DIR",
    ):
        value = os.environ.get(env_name, "").strip()
        if value:
            roots.append(Path(value))
    origin = os.environ.get("ARNOLD_WATCHDOG_ORIGIN", "").strip()
    if origin:
        roots.append(Path(origin).resolve().parents[4])
    roots.append(_REPO_ROOT)
    return roots


def _resolve_asset(relative: str) -> Path:
    for root in _engine_roots():
        candidate = root / relative
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        f"babysitter asset unavailable under live engine roots: {relative}"
    )


def _resolve_engine_root() -> Path:
    """The live engine root: the first candidate tree carrying the babysitter
    assets (renderer + hermes subagent launcher), mirroring the watchdog."""
    renderer_rel = (
        "arnold_pipelines/megaplan/skills/babysitter/scripts/render_babysitter_goal.py"
    )
    launcher_rel = (
        "arnold_pipelines/megaplan/skills/subagent-launcher/launch_hermes_agent.py"
    )
    for root in _engine_roots():
        if (root / renderer_rel).is_file() and (root / launcher_rel).is_file():
            return root.resolve()
    raise RuntimeError("babysitter launch: no live engine root with babysitter assets")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m arnold_pipelines.megaplan.cloud.babysitter.launch",
        description=(
            "Launch ONE detached hermes:deepseek:deepseek-v4-flash managed "
            "babysitter whose goal prompt drives swarm -> codex -> implement "
            "-> relaunch -> prove."
        ),
    )
    parser.add_argument("--goal-file", default="", help="rendered goal prompt file")
    parser.add_argument("--session", default="", help="epic/session target")
    parser.add_argument(
        "--target", dest="session", default=None,
        help="alias for --session (renderer CLI naming)",
    )
    parser.add_argument("--workspace", default="", help="chain workspace path")
    parser.add_argument("--plan", default="", help="plan name")
    parser.add_argument("--run-kind", dest="run_kind", default="", help="chain|plan|epic_chain")
    parser.add_argument("--occurrence", default="", help="occurrence/failure digest")
    parser.add_argument(
        "--occurrence-digest", dest="occurrence", default=None,
        help="alias for --occurrence (renderer CLI naming)",
    )
    parser.add_argument("--remote-spec", dest="remote_spec", default="", help="remote spec path")
    parser.add_argument("--run-id", dest="run_id", default="", help="occurrence-scoped run id")
    parser.add_argument("--run-root", dest="run_root", default="", help="run directory")
    parser.add_argument("--mode", default="", help="babysitter mode (e.g. superfixer)")
    parser.add_argument("--failure-json", default=None, help="path to latest_failure JSON")
    parser.add_argument("--planner-repair-json", default=None, help="path to planner_repair JSON")
    return parser


def _env_or_flag(cli_value: str | None, env_name: str, default: str = "") -> str:
    if cli_value:
        return cli_value
    return os.environ.get(env_name, "").strip() or default


def _collect_context(args: argparse.Namespace) -> dict[str, Any]:
    """Merge CLI flags, ARNOLD_BABYSITTER_* env, and defaults into one ctx."""
    session = _env_or_flag(args.session, "ARNOLD_BABYSITTER_SESSION")
    if not session:
        raise ValueError("babysitter session is required (--session / ARNOLD_BABYSITTER_SESSION)")
    workspace = _env_or_flag(args.workspace, "ARNOLD_BABYSITTER_WORKSPACE")
    plan = _env_or_flag(args.plan, "ARNOLD_BABYSITTER_PLAN")
    run_kind = _env_or_flag(args.run_kind, "ARNOLD_BABYSITTER_RUN_KIND")
    occurrence = _env_or_flag(args.occurrence, "ARNOLD_BABYSITTER_OCCURRENCE")
    marker_dir_raw = _env_or_flag("", "ARNOLD_BABYSITTER_MARKER_DIR")
    repair_data_raw = _env_or_flag("", "ARNOLD_BABYSITTER_REPAIR_DATA_DIR")
    marker_dir = Path(marker_dir_raw) if marker_dir_raw else None
    repair_data_dir = (
        Path(repair_data_raw)
        if repair_data_raw
        else (marker_dir / "repair-data" if marker_dir else None)
    )
    run_id = args.run_id or f"babysitter-{_provenance_safe(session[:48])}-{occurrence or 'occurrence'}"
    run_root_raw = args.run_root
    if not run_root_raw and repair_data_dir is not None:
        run_root_raw = str(repair_data_dir / "babysitter-runs" / run_id)
    run_root = Path(run_root_raw) if run_root_raw else _REPO_ROOT / ".babysitter-runs" / run_id
    routing = resolve_babysitter_routing()
    return {
        "session": session,
        "workspace": workspace,
        "plan": plan,
        "run_kind": run_kind,
        "occurrence": occurrence,
        "remote_spec": args.remote_spec,
        "run_id": run_id,
        "run_root": run_root,
        "mode": args.mode,
        "marker_dir": marker_dir,
        "repair_data_dir": repair_data_dir,
        "goal_file_cli": args.goal_file,
        "failure_json": args.failure_json,
        "planner_repair_json": args.planner_repair_json,
        "model": routing.controller_model
        if routing.mode == "codex"
        else os.environ.get("ARNOLD_BABYSITTER_MODEL", "").strip() or DEFAULT_MODEL,
        "routing": routing,
        "difficulty": _difficulty_env(),
    }


def _difficulty_env() -> int:
    raw = os.environ.get("ARNOLD_BABYSITTER_DIFFICULTY", "").strip()
    if not raw:
        return DEFAULT_DIFFICULTY
    try:
        difficulty = int(raw)
    except ValueError as exc:
        raise ValueError("ARNOLD_BABYSITTER_DIFFICULTY must be an integer D1-D10") from exc
    if not 1 <= difficulty <= 10:
        raise ValueError("ARNOLD_BABYSITTER_DIFFICULTY must be D1-D10")
    return difficulty


def _load_optional_json(path_raw: str | None) -> dict[str, object] | None:
    if not path_raw:
        return None
    path = Path(path_raw)
    if not path.is_file():
        raise RuntimeError(f"babysitter evidence JSON is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"babysitter evidence JSON is not an object: {path}")
    return payload


def _recovery_evidence_root(workspace: str) -> str:
    """Chain recovery evidence root, scanned for prior fixer occurrences.

    Each fixer incarnation persists its evidence under
    ``<workspace>/.megaplan/plans/.chains/recovery/<occurrence_digest>/``
    (swarm-briefs/, swarm-results/, codex/, execution/).  The goal renderer
    lists prior occurrences so the next babysitter reads the previous
    handoff instead of re-deriving the same diagnosis from scratch.
    """
    if not workspace:
        return ""
    return str(
        Path(workspace) / ".megaplan" / "plans" / ".chains" / "recovery"
    )


def _receipt_payload(ctx: dict[str, Any], *, status: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": LAUNCH_RECEIPT_SCHEMA,
        "session": ctx["session"],
        "occurrence_digest": ctx["occurrence"],
        "run_id": ctx["run_id"],
        "run_root": str(ctx["run_root"]),
        "plan": ctx["plan"],
        "run_kind": ctx["run_kind"],
        "workspace": ctx["workspace"],
        "remote_spec": ctx["remote_spec"],
        "mode": ctx["mode"],
        "model": ctx["model"],
        "toolsets": TOOLSETS,
        "babysitter_pid": os.getpid(),
        "supervisor_pid": os.getpid(),
        "status": status,
        "launched_at": ctx["launched_at"],
    }
    if ctx.get("marker_dir") is not None:
        payload["marker_dir"] = str(ctx["marker_dir"])
    if ctx.get("repair_data_dir") is not None:
        payload["repair_data_dir"] = str(ctx["repair_data_dir"])
    if ctx.get("goal_path") is not None:
        payload["goal_path"] = str(ctx["goal_path"])
    if ctx.get("engine_root") is not None:
        payload["engine_root"] = str(ctx["engine_root"])
    if ctx.get("renderer_path") is not None:
        payload["renderer_path"] = str(ctx["renderer_path"])
    if ctx.get("identity_key") is not None:
        payload["identity_key"] = ctx["identity_key"]
    if ctx.get("managed_run_id") is not None:
        payload["managed_run_id"] = ctx["managed_run_id"]
    if ctx.get("managed_manifest_path") is not None:
        payload["managed_manifest_path"] = str(ctx["managed_manifest_path"])
    routing = ctx.get("routing")
    if routing is not None:
        payload.update(routing.as_dict())
    payload.update({key: value for key, value in extra.items() if value is not None})
    return payload


def _write_receipts(ctx: dict[str, Any], payload: dict[str, Any]) -> None:
    """Write the launch receipt where the watchdog's dedup reads it
    (repair_data_dir) plus a mirror under the run root for run-local tooling."""
    _atomic_write_json(ctx["run_root"] / LAUNCH_RECEIPT_NAME.format(session=ctx["session"]), payload)
    if ctx.get("repair_data_dir") is not None:
        _atomic_write_json(
            ctx["repair_data_dir"] / LAUNCH_RECEIPT_NAME.format(session=ctx["session"]),
            payload,
        )


def _receipt_candidates(ctx: dict[str, Any]) -> list[Path]:
    names = (
        LAUNCH_RECEIPT_NAME.format(session=ctx["session"]),
        DISPATCH_RECEIPT_NAME.format(session=ctx["session"]),
    )
    directories = [ctx["run_root"]]
    if ctx.get("repair_data_dir") is not None:
        directories.append(ctx["repair_data_dir"])
    if ctx.get("marker_dir") is not None:
        directories.append(ctx["marker_dir"])
    return [directory / name for directory in directories for name in names]


def _dedup_already_running(ctx: dict[str, Any]) -> bool:
    """True only when a genuinely live recorded babysitter_pid owns this occurrence."""
    occurrence = ctx["occurrence"]
    if not occurrence:
        return False
    for path in _receipt_candidates(ctx):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("occurrence_digest") or "") != occurrence:
            continue
        pid = _recorded_babysitter_pid(payload)
        if pid == os.getpid():
            continue
        classification = classify_owner_receipt(payload)
        if classification["active_owner"]:
            return True
    return False


def _resolve_goal_file(ctx: dict[str, Any]) -> Path:
    """Prefer the supplied goal file; otherwise render one into the run root."""
    raw = ctx["goal_file_cli"] or os.environ.get("ARNOLD_BABYSITTER_GOAL_FILE", "").strip()
    if raw:
        candidate = Path(raw)
        if not candidate.is_file():
            raise RuntimeError(f"babysitter goal file is not a file: {candidate}")
        return candidate
    renderer = _resolve_asset(
        "arnold_pipelines/megaplan/skills/babysitter/scripts/render_babysitter_goal.py"
    )
    namespace = runpy.run_path(str(renderer))
    render = namespace.get("render_babysitter_goal")
    if not callable(render):
        raise RuntimeError("babysitter goal renderer is unavailable")
    sandbox = _ctx_sandbox(ctx)
    render_kwargs = {
        "workspace": ctx["workspace"],
        "plan": ctx["plan"],
        "run_kind": ctx["run_kind"],
        "latest_failure": _load_optional_json(ctx["failure_json"]),
        "planner_repair": _load_optional_json(ctx["planner_repair_json"]),
        "occurrence_digest": ctx["occurrence"],
        "recovery_dir": _recovery_evidence_root(ctx["workspace"]),
        "investigator_sandbox": sandbox,
    }
    try:
        goal_text = render(ctx["session"], **render_kwargs)
    except TypeError:
        render_kwargs.pop("investigator_sandbox")
        goal_text = render(ctx["session"], **render_kwargs)
    goal_path = ctx["run_root"] / "babysitter-goal.md"
    goal_path.parent.mkdir(parents=True, exist_ok=True)
    goal_path.write_text(goal_text, encoding="utf-8")
    ctx["renderer_path"] = str(renderer)
    return goal_path


def _managed_spec(
    ctx: dict[str, Any], *, goal_path: Path, identity_key: str
) -> ManagedCommandSpec:
    engine_root = ctx["engine_root"]
    routing = ctx["routing"]
    if routing.mode == "codex":
        # Codex reads the sealed goal from stdin.  Keeping the goal out of argv
        # also makes the managed manifest's stdin hash the exact controller
        # input used for this occurrence.
        sandbox = _ctx_sandbox(ctx)
        worker_argv = [
            "codex",
            "exec",
            "--sandbox", sandbox,
            "--ephemeral",
            "-m", cli_model(routing.controller_model),
            "-c", "model_reasoning_effort=high",
            "--output-last-message", str(ctx["run_root"] / "controller-last-message.md"),
            "-",
        ]
        stdin_path = goal_path
        backend = "codex"
        route_class = "watchdog_babysitter_codex_override"
        description = (
            f"Codex babysitter session={ctx['session']} "
            f"occurrence={ctx['occurrence'] or 'unknown'} plan={ctx['plan'] or 'current target'} — "
            "codex investigators -> codex controller -> implement -> relaunch -> prove"
        )
    else:
        sandbox = _ctx_sandbox(ctx)
        launcher = (
            engine_root
            / "arnold_pipelines/megaplan/skills/subagent-launcher/launch_hermes_agent.py"
        )
        if not launcher.is_file():
            raise RuntimeError(f"hermes subagent launcher unavailable: {launcher}")
        # Strip the managed-agent env vars the supervisor injects, so the hermes
        # launcher runs the goal as a DIRECT worker of this managed run instead
        # of re-exec'ing itself as a nested "research" run.
        worker_argv = [
            "/usr/bin/env",
            "-u", "ARNOLD_MANAGED_AGENT_RUN_ID",
            "-u", "ARNOLD_MANAGED_AGENT_MANIFEST",
            "-u", "ARNOLD_MANAGED_AGENT_ORIGIN",
            sys.executable,
            str(launcher),
            f"--model={ctx['model']}",
            f"--toolsets={TOOLSETS}",
            f"--query-file={goal_path}",
            f"--project-dir={engine_root}",
        ]
        stdin_path = None
        backend = BACKEND
        route_class = ROUTE_CLASS
        description = (
            f"Single Flash babysitter session={ctx['session']} "
            f"occurrence={ctx['occurrence'] or 'unknown'} plan={ctx['plan'] or 'current target'} — "
            "swarm -> codex -> implement -> relaunch -> prove"
        )
    links: dict[str, Any] = {
        "cloud_session": ctx["session"],
        "occurrence_digest": ctx["occurrence"],
        "run_id": ctx["run_id"],
        "goal_path": str(goal_path),
        "babysitter_mode": ctx["mode"] or "superfixer",
        "routing": routing.as_dict(),
        "investigator_sandbox": _ctx_sandbox(ctx),
        "investigator_exec_argv": investigator_exec_argv(
            sandbox=_ctx_sandbox(ctx),
            investigator_model=routing.investigator_model,
        ),
    }
    if ctx.get("repair_data_dir") is not None:
        links["repair_data_dir"] = str(ctx["repair_data_dir"])
    if ctx.get("marker_dir") is not None:
        links["marker_dir"] = str(ctx["marker_dir"])
    if ctx["remote_spec"]:
        links["chain"] = ctx["remote_spec"]
    if ctx["plan"]:
        links["plan"] = ctx["plan"]
    if ctx["workspace"]:
        links["workspace"] = ctx["workspace"]
    spec = ManagedCommandSpec(
        run_kind=RUN_KIND,
        identity_key=identity_key,
        project_dir=engine_root,
        argv=tuple(worker_argv),
        task_kind=TASK_KIND,
        difficulty=ctx["difficulty"],
        model=ctx["model"],
        reasoning_effort=REASONING_EFFORT,
        route_class=route_class,
        backend=backend,
        command_display=(
            f"arnold-babysitter {routing.controller_model} agent session={ctx['session']} "
            f"occurrence={ctx['occurrence'] or 'unknown'}"
        ),
        description=description,
        launch_provenance=machine_origin_provenance(
            origin_kind=ORIGIN_KIND,
            origin_id=_provenance_safe(ctx["run_id"]),
            component=ORIGIN_COMPONENT,
            trigger_id=_provenance_safe(ctx["occurrence"] or ctx["run_id"]),
        ),
        links=links,
        lineage_key=f"babysitter:{ctx['session']}",
        run_root=ctx["run_root"],
        stdin_path=stdin_path,
    )
    return spec


def launch_babysitter(argv: Sequence[str] | None = None) -> int:
    """Run the single-flash babysitter launch flow; returns the process rc."""
    args = _build_parser().parse_args(argv)
    ctx = _collect_context(args)
    ctx["launched_at"] = _utcnow_iso()
    # ROOT FIX (grok consult 2026-08-17): assert session-identity consistency
    # before any worker spawn. If ARNOLD_REPAIR_SESSION disagrees with the
    # babysitter --session, a stale box-global env would leak into the
    # agent's resume/execute workers and hijack another session's liveness
    # lock/marker/lease (astrid -> mega collision observed 2026-08-17).
    _babysitter_session = str(ctx.get("session") or "").strip()
    _repair_env_session = str(os.environ.get("ARNOLD_REPAIR_SESSION") or "").strip()
    if _babysitter_session and _repair_env_session and _babysitter_session != _repair_env_session:
        os.environ["ARNOLD_REPAIR_SESSION"] = _babysitter_session
    os.environ["ARNOLD_BABYSITTER_SESSION"] = _babysitter_session
    try:
        if _dedup_already_running(ctx):
            _eprint(
                f"[babysitter] already_running session={ctx['session']} "
                f"occurrence={ctx['occurrence']} — exiting 0"
            )
            return 0

        ctx["engine_root"] = _resolve_engine_root()
        goal_path = _resolve_goal_file(ctx)
        ctx["goal_path"] = str(goal_path)

        identity_key = (
            f"babysitter:{ctx['session']}:{ctx['occurrence']}:{ctx['run_id']}:"
            f"{time.time_ns()}"
        )
        ctx["identity_key"] = identity_key
        managed_run_id = stable_managed_run_id(RUN_KIND, identity_key)
        ctx["managed_run_id"] = managed_run_id
        ctx["managed_manifest_path"] = str(ctx["run_root"] / managed_run_id / "manifest.json")
        workspace = str(ctx.get("workspace") or "").strip()
        if workspace:
            ctx["pre_product_tree_fingerprint"] = product_tree_fingerprint(Path(workspace))
            plan_name = str(ctx.get("plan") or "").strip()
            if plan_name:
                plan_state_path = _canonical_plan_state_path(workspace, plan_name)
                if plan_state_path.is_file():
                    try:
                        pre_payload = json.loads(plan_state_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        pre_payload = {}
                    if isinstance(pre_payload, dict) and pre_payload:
                        ctx["pre_failure_fingerprint"] = _canonical_failure_fingerprint(pre_payload)
        spec = _managed_spec(ctx, goal_path=goal_path, identity_key=identity_key)

        _write_receipts(ctx, _receipt_payload(ctx, status="running"))
        # The managed supervisor reserves the run itself (clean
        # created=True "supervisor_start" path — no pre-reservation, which
        # would be misread as a dead-supervisor restart) and then blocks
        # until the Flash agent finishes.
        rc = run_managed_command(spec)
        managed_terminal = "unknown"
        try:
            managed_terminal = str(
                json.loads(
                    (ctx["run_root"] / managed_run_id / "manifest.json").read_text(
                        encoding="utf-8"
                    )
                ).get("status")
                or "unknown"
            )
        except (OSError, json.JSONDecodeError):
            pass
        honesty = evaluate_canonical_honesty(
            ctx,
            pre_fingerprint=ctx.get("pre_product_tree_fingerprint"),
        )
        terminal_status, transport_rc, false_success_reason = terminal_transport_result(
            worker_rc=rc,
            managed_terminal=managed_terminal,
            honesty=honesty,
        )
        if false_success_reason:
            _eprint(
                f"[babysitter] FALSE SUCCESS downgraded to failed "
                f"session={ctx.get('session', '?')} occurrence={ctx.get('occurrence', '?')} "
                f"reason={false_success_reason}"
            )
        _write_receipts(
            ctx,
            _receipt_payload(
                ctx,
                status=terminal_status,
                finished_at=_utcnow_iso(),
                returncode=transport_rc,
                managed_terminal_status=managed_terminal,
                false_success_reason=false_success_reason or None,
                honesty=honesty,
            ),
        )
        return transport_rc
    except SystemExit:
        raise
    except BaseException as exc:
        _eprint(f"[babysitter] launch failed session={ctx.get('session', '?')} err={exc!r}")
        try:
            _write_receipts(
                ctx,
                _receipt_payload(
                    ctx,
                    status="failed",
                    finished_at=_utcnow_iso(),
                    returncode=1,
                    error=f"{type(exc).__name__}: {exc}",
                ),
            )
        except BaseException as write_exc:
            _eprint(f"[babysitter] could not record failure receipt: {write_exc!r}")
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    return launch_babysitter(argv)


if __name__ == "__main__":
    raise SystemExit(main())
