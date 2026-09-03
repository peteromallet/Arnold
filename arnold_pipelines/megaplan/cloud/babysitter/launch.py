#!/usr/bin/env python3
"""Status-trigger babysitter launch module.

The watchdog's status trigger (``MEGAPLAN_SUPERFIXER_ONLY=1``) Popen's
``arnold-babysitter``, which executes this module.  For ordinary sessions the
babysitter is one detached managed OMP agent whose goal prompt drives the
recovery flow itself.  The native-build-forward continuation is closed to one
exact Muse Spark 1.3 Contributor route with high thinking at every nested
dispatch.  There is deliberately NO coded multi-stage orchestrator: the single
agent IS the orchestrator.

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
       worker is ``launch_omp_agent.py`` with the resolved model route,
       ``--toolsets=file,web,terminal --query-file=<goal> --project-dir=<engine>``
       so the agent can run the bounded recovery flow.  Continuation sessions
       carry the exact Muse model/high-thinking suffix.  This process stays alive
       as the managed-agent supervisor for the whole run, so the watchdog's
       early-rc check and receipt pid liveness are honest.
    5. Write an ``arnold.superfixer.babysitter_launch_receipt.v1`` receipt
       (status running -> terminal, babysitter_pid, run_id, occurrence
       digest, managed run id) and propagate the worker rc.

Env overrides (all optional):
    ARNOLD_BABYSITTER_SESSION / _WORKSPACE / _PLAN / _RUN_KIND / _OCCURRENCE /
    _GOAL_FILE / _MARKER_DIR / _REPAIR_DATA_DIR   watchdog-provided context
    ARNOLD_BABYSITTER_MODEL       ordinary-session model override
    ARNOLD_BABYSITTER_DIFFICULTY  managed-run difficulty D1-D10 (default 8)
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import runpy
import sys
import socket
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.cloud.babysitter.routing import (
    cli_model,
    CONTINUATION_MUSE_THINKING,
    resolve_babysitter_routing,
)
from arnold_pipelines.megaplan.cloud.cli import _omp_openrouter_capability_check
from arnold_pipelines.megaplan.managed_agent import (
    ManagedCommandSpec,
    machine_origin_provenance,
    run_managed_command,
    stable_managed_run_id,
)

LAUNCH_RECEIPT_SCHEMA = "arnold.superfixer.babysitter_launch_receipt.v1"
DISPATCH_RECEIPT_NAME = "{session}.babysitter-receipt.json"
LAUNCH_RECEIPT_NAME = "{session}.babysitter-launch-receipt.json"
CHAIN_DRIVE_RECEIPT_SCHEMA = "arnold.megaplan.chain_drive_launch_receipt.v1"
CHAIN_DRIVE_RECEIPT_NAME = "chain-drive-launch-receipt.json"
CHAIN_DRIVE_RECEIPT_ENV = "ARNOLD_CHAIN_DRIVE_RECEIPT"

DEFAULT_MODEL = "codex:gpt-5.6-luna"
TOOLSETS = "file,web,terminal"
RUN_KIND = "automatic_watchdog_source_repair"
ORIGIN_KIND = "watchdog_source_repair"
ORIGIN_COMPONENT = "arnold-babysitter"
ROUTE_CLASS = "watchdog_babysitter"
BACKEND = "babysitter"
TASK_KIND = "autonomous"
REASONING_EFFORT = "bounded"
DEFAULT_DIFFICULTY = 8
_AUTOMATIC_FINAL_MARKER_LOCK_TIMEOUT_S = 5.0

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
    resolves the goal renderer / omp launcher from the SAME runtime the
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
    assets (renderer + omp subagent launcher), mirroring the watchdog."""
    renderer_rel = (
        "arnold_pipelines/megaplan/skills/babysitter/scripts/render_babysitter_goal.py"
    )
    launcher_rel = (
        "arnold_pipelines/megaplan/skills/subagent-launcher/launch_omp_agent.py"
    )
    for root in _engine_roots():
        if (root / renderer_rel).is_file() and (root / launcher_rel).is_file():
            return root.resolve()
    raise RuntimeError("babysitter launch: no live engine root with babysitter assets")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m arnold_pipelines.megaplan.cloud.babysitter.launch",
        description=(
            "Launch ONE detached managed OMP babysitter whose goal prompt "
            "drives investigate -> review -> implement -> relaunch -> prove."
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
    routing = resolve_babysitter_routing(
        session=session,
    )
    if routing.closed and not str(os.environ.get("ARNOLD_BABYSITTER_MODEL", "")).strip():
        raise ValueError(
            f"{session} requires explicit {routing.controller_model}:high "
            "for resident fixer registration"
        )
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
        # Preserve the legacy environment override for ordinary babysitters;
        # the continuation resolver has already closed its model surface to
        # the exact Muse route and supplies that model here.
        "model": (
            routing.controller_model
            if routing.closed
            else os.environ.get("ARNOLD_BABYSITTER_MODEL", "").strip()
            or routing.controller_model
        ),
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


def _continuation_capability_preflight(ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Use the same authenticated OMP capability evidence as chain launch.

    Closed continuation fixers must prove the route through OMP's broker/store;
    an ambient ``OPENROUTER_API_KEY`` is neither required nor copied.  Keep the
    returned evidence sanitized (the shared helper only returns typed status
    and digests) so a failed fixer admission cannot leak provider credentials.
    """
    routing = ctx.get("routing")
    if routing is None or not getattr(routing, "closed", False):
        return None
    evidence = _omp_openrouter_capability_check(local=True)
    ctx["provider_capability"] = evidence
    if evidence.get("status") != "ok":
        reason = str(evidence.get("reason") or evidence.get("status") or "unknown")
        raise RuntimeError(f"babysitter OMP capability preflight failed: {reason}")
    return evidence


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
    if ctx.get("provider_capability") is not None:
        # The shared OMP probe returns only typed status and fingerprints; do
        # not replace it with raw provider output in a fixer receipt.
        payload["provider_capability"] = ctx["provider_capability"]
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


def _chain_drive_receipt_path(ctx: Mapping[str, Any]) -> Path:
    configured = os.environ.get(CHAIN_DRIVE_RECEIPT_ENV, "").strip()
    if configured:
        return Path(configured)
    return Path(str(ctx["run_root"])) / CHAIN_DRIVE_RECEIPT_NAME


def _chain_drive_receipt_paths(ctx: Mapping[str, Any]) -> list[Path]:
    """Return the run-local path and the canonical project fallback."""
    configured = os.environ.get(CHAIN_DRIVE_RECEIPT_ENV, "").strip()
    if configured:
        return [Path(configured)]
    paths = [_chain_drive_receipt_path(ctx)]
    workspace = str(ctx.get("workspace") or "").strip()
    occurrence = str(ctx.get("occurrence") or "").strip()
    if workspace and occurrence:
        paths.append(
            Path(workspace)
            / ".megaplan"
            / f"chain-drive-launch-receipt-{occurrence}.json"
        )
    return paths


def _chain_drive_authority_error(receipt: Mapping[str, Any]) -> str | None:
    """Check that the receipt points at AgentBox's persisted process resource."""
    operation_id = receipt.get("operation_id")
    resource_id = receipt.get("process_resource_id")
    resource_type = receipt.get("process_resource_type")
    if not isinstance(operation_id, str) or not operation_id:
        return "chain drive receipt is missing the AgentBox operation id"
    if not isinstance(resource_id, str) or not resource_id:
        return "chain drive receipt is missing the process resource id"
    if resource_type != "process_session":
        return "chain drive receipt is not bound to a process-session resource"
    try:
        from agentbox.config import load_agentbox_config
        from agentbox.operations import load_agentbox_operation, open_operation_store
        from arnold.runtime.durable_ops import ResourceType

        load_agentbox_operation(load_agentbox_config(), operation_id)
        resources = open_operation_store(load_agentbox_config()).list_typed_resources(operation_id)
    except Exception as exc:
        return f"chain drive AgentBox authority is unavailable: {type(exc).__name__}"
    for resource in resources:
        if resource.id == resource_id:
            if resource.resource_type is ResourceType.PROCESS_SESSION:
                return None
            return "chain drive authority resource has the wrong type"
    return "chain drive process resource is not present in AgentBox authority"


def _validate_chain_drive_receipt(
    ctx: Mapping[str, Any], receipt: object
) -> str | None:
    """Validate the hub custody proof for a completed chain babysitter.

    The managed agent may finish while a synchronous ``arnold-chain`` child
    is still attached to its lifetime.  A prompt cannot prove that the child
    was handed to durable hub custody, so completion is accepted only when a
    hub-owned receipt binds the exact occurrence and launch contract.
    """
    if not isinstance(receipt, Mapping):
        return "chain drive custody receipt is not a JSON object"
    if receipt.get("schema") != CHAIN_DRIVE_RECEIPT_SCHEMA:
        return "chain drive custody receipt has an invalid schema"
    expected = {
        "session": str(ctx.get("session") or ""),
        "occurrence_digest": str(ctx.get("occurrence") or ""),
        "plan": str(ctx.get("plan") or ""),
        "workspace": str(ctx.get("workspace") or ""),
    }
    for key, value in expected.items():
        if not value or receipt.get(key) != value:
            return f"chain drive custody receipt identity mismatch for {key}"
    if receipt.get("status") not in {"launched", "running", "completed"}:
        return "chain drive custody receipt is not an accepted launch status"
    custody = receipt.get("custody")
    if not isinstance(custody, Mapping):
        return "chain drive custody receipt is missing custody fields"
    required = {
        "persist": True,
        "detached": True,
        "pty": False,
        "restart": "no",
        "ready_matcher": None,
    }
    for key, value in required.items():
        if custody.get(key) != value:
            return f"chain drive custody contract violation: {key}"
    return None


def _chain_drive_custody_error(ctx: Mapping[str, Any]) -> str | None:
    """Return a durable-custody error, or ``None`` when proof is present."""
    if str(ctx.get("run_kind") or "").strip() != "chain":
        return None
    if not str(ctx.get("plan") or "").strip() or not str(ctx.get("workspace") or "").strip():
        return "chain babysitter completion lacks plan/workspace custody identity"
    paths = _chain_drive_receipt_paths(ctx)
    receipt = None
    selected_path = paths[0]
    for path in paths:
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
            selected_path = path
            break
        except FileNotFoundError:
            continue
        except (OSError, json.JSONDecodeError) as exc:
            return f"durable chain drive custody receipt is unreadable: {path} ({exc})"
    if receipt is None:
        return f"durable chain drive custody receipt is missing: {selected_path}"
    error = _validate_chain_drive_receipt(ctx, receipt)
    if error:
        return f"durable chain drive custody proof rejected: {error}"
    authority_error = _chain_drive_authority_error(receipt)
    return (
        f"durable chain drive custody authority rejected: {authority_error}"
        if authority_error
        else None
    )


def _terminal_returncode(returncode: int, terminal_status: str) -> int:
    """Make a downgraded managed completion visible to the watchdog."""
    return returncode if terminal_status == "completed" else (returncode or 1)


def _dedup_already_running(ctx: dict[str, Any]) -> bool:
    """True when a live babysitter supervisor owns this occurrence digest."""
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
        if str(payload.get("status") or "") not in {"launched", "running"}:
            continue
        pid = payload.get("babysitter_pid")
        if not isinstance(pid, int):
            pid = payload.get("supervisor_pid")
        if pid == os.getpid():
            continue
        if _pid_live(pid):
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
    goal_text = render(
        ctx["session"],
        session=ctx["session"],
        workspace=ctx["workspace"],
        plan=ctx["plan"],
        run_kind=ctx["run_kind"],
        latest_failure=_load_optional_json(ctx["failure_json"]),
        planner_repair=_load_optional_json(ctx["planner_repair_json"]),
        occurrence_digest=ctx["occurrence"],
        recovery_dir=_recovery_evidence_root(ctx["workspace"]),
    )
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
        # Strip ambient runtime-identity env (occurrence c2f73c7ddcef,
        # 2026-08-28): a launch seed or manifest inherited from the firing
        # parent silently lags generation advances and made every phase CLI
        # fail admission with source_revision_mismatch. The controller binds
        # identity explicitly from the marker/authoritative manifest instead.
        worker_argv = [
            "/usr/bin/env",
            "-u", "MEGAPLAN_RUNTIME_LAUNCH_SEED",
            "-u", "ARNOLD_RUNTIME_MANIFEST",
            "codex",
            "exec",
            "--sandbox", "danger-full-access",
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
        launcher = (
            engine_root
            / "arnold_pipelines/megaplan/skills/subagent-launcher/launch_omp_agent.py"
        )
        if not launcher.is_file():
            raise RuntimeError(f"omp subagent launcher unavailable: {launcher}")
        # Strip the managed-agent env vars the supervisor injects, so the omp
        # launcher runs the goal as a DIRECT worker of this managed run instead
        # of re-exec'ing itself as a nested "research" run.
        worker_argv = [
            "/usr/bin/env",
            "-u", "ARNOLD_MANAGED_AGENT_RUN_ID",
            "-u", "ARNOLD_MANAGED_AGENT_MANIFEST",
            "-u", "ARNOLD_MANAGED_AGENT_ORIGIN",
            "-u", "MEGAPLAN_RUNTIME_LAUNCH_SEED",
            "-u", "ARNOLD_RUNTIME_MANIFEST",
            sys.executable,
            str(launcher),
            f"--model={ctx['model']}"
            + (f":{CONTINUATION_MUSE_THINKING}" if routing.closed else ""),
            f"--toolsets={TOOLSETS}",
            f"--query-file={goal_path}",
            f"--project-dir={engine_root}",
        ]
        stdin_path = None
        backend = BACKEND
        route_class = ROUTE_CLASS
        description = (
            f"Single OMP babysitter session={ctx['session']} "
            f"occurrence={ctx['occurrence'] or 'unknown'} plan={ctx['plan'] or 'current target'} — "
            "swarm -> review -> implement -> relaunch -> prove"
        )
        if routing.closed:
            route_class = "watchdog_babysitter_continuation_muse"
            description = (
                f"Single Muse Spark 1.3 babysitter session={ctx['session']} "
                f"occurrence={ctx['occurrence'] or 'unknown'} plan={ctx['plan'] or 'current target'} — "
                "all roles Muse/high, no fallback"
            )
    links: dict[str, Any] = {
        "cloud_session": ctx["session"],
        "occurrence_digest": ctx["occurrence"],
        "run_id": ctx["run_id"],
        "goal_path": str(goal_path),
        "babysitter_mode": ctx["mode"] or "superfixer",
        "routing": routing.as_dict(),
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
        reasoning_effort=(
            CONTINUATION_MUSE_THINKING if routing.closed else REASONING_EFFORT
        ),
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


class ManagedLaunchUnresolved(RuntimeError):
    """Typed managed-door hold; keeps the legacy public return code intact."""

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        super().__init__("managed launch remains unresolved")


def _automatic_dispatch_preflight(
    ctx: dict[str, Any],
    spec: ManagedCommandSpec,
):
    """Build the final automatic-only marker/chain admission door.

    The watchdog supplies ``ARNOLD_BABYSITTER_AUTO_DISPATCH``.  Manual
    invocations deliberately do not enter this path.  A short durable marker
    reservation is the linearization point; the worker is launched only after
    the reservation and the existing managed manifest have been committed.
    """
    if os.environ.get("ARNOLD_BABYSITTER_AUTO_DISPATCH", "").strip() not in {"1", "true", "yes"}:
        return None
    marker_dir = ctx.get("marker_dir")
    workspace_raw = str(ctx.get("workspace") or "").strip()
    if not isinstance(marker_dir, Path) or not workspace_raw:
        return lambda _receipt: {
            "suppress": True,
            "evidence_kind": "controlled_adapter",
            "physical_operation_evidence": {
                "schema": "arnold.babysitter.no-launch.v1",
                "reservation_event_id": _receipt.reservation_event_id,
                "admission_receipt_id": _receipt.admission_receipt_id,
                "physical_door_id": _receipt.physical_door_id,
                "launch_state_identity": "not_started",
                "observed_at": _utcnow_iso(),
                "reason": "automatic dispatch lacks canonical marker/workspace authority",
            },
        }

    marker_path = marker_dir / f"{ctx['session']}.json"
    workspace = Path(workspace_raw).expanduser().resolve(strict=False)
    remote_spec_raw = str(ctx.get("remote_spec") or "").strip()
    spec_path = Path(remote_spec_raw).expanduser()
    if not spec_path.is_absolute():
        spec_path = workspace / spec_path
    spec_path = spec_path.resolve(strict=False)

    def preflight(receipt: Any) -> dict[str, Any]:
        from arnold_pipelines.megaplan.chain import spec as chain_spec
        from arnold_pipelines.megaplan._core.io import find_plan_dir
        from arnold_pipelines.megaplan.managed_agent import reserve_managed_command
        from arnold_pipelines.megaplan.cloud.operator_control import (
            _load_marker,
            _write_marker_locked,
            marker_runtime_cutover_lock,
        )
        from arnold_pipelines.megaplan.incident.chain_control import (
            ChainControlError,
            ChainStateAdapter,
            ChainControlJournal,
            chain_id_for_spec,
            state_digest_for,
        )
        from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
        from arnold_pipelines.megaplan.types import CliError

        def evidence(reason: str, **extra: Any) -> dict[str, Any]:
            return {
                "suppress": True,
                "evidence_kind": "controlled_adapter",
                "physical_operation_evidence": {
                    "schema": "arnold.babysitter.no-launch.v1",
                    "reservation_event_id": receipt.reservation_event_id,
                    "admission_receipt_id": receipt.admission_receipt_id,
                    "physical_door_id": receipt.physical_door_id,
                    "launch_state_identity": "not_started",
                    "observed_at": _utcnow_iso(),
                    "reason": reason,
                    **extra,
                },
            }

        if not marker_path.is_file() or not spec_path.is_file():
            return evidence("canonical marker or frozen chain spec is unavailable")
        try:
            ledger = IncidentLedger(workspace)
            state_path = chain_spec._state_path_for(spec_path)
            chain_id = chain_id_for_spec(spec_path)
            journal = ChainControlJournal(ledger)
            # Sequence -> chain scope/state -> marker is the global lock order
            # used by chain control and the marker cutover door.
            with journal.transaction(
                chain_ids=[chain_id],
                state_paths=[state_path],
                expected_revision=None,
                operation_id=receipt.logical_dispatch_id,
                actor={"id": "babysitter", "class": "automatic"},
            ) as txn:
                # This is deliberately the first chain read after acquiring
                # the sequence/scope/state locks.  Never carry a pre-lock
                # ChainState snapshot across the final admission door.
                raw_state = ChainStateAdapter(
                    # Read the exact state path already covered by the
                    # transaction lock; load_chain_state may select a legacy
                    # candidate and would reintroduce a pre-lock identity
                    # race.
                    txn,
                    state_path,
                ).read_expected()
                if not isinstance(raw_state, dict):
                    return evidence("canonical chain state is unavailable")
                state = chain_spec.ChainState.from_dict(raw_state)
                state_revision = (state.metadata or {}).get("_nbf08_revision")
                if state_revision is not None and (
                    isinstance(state_revision, bool) or not isinstance(state_revision, int) or state_revision < 0
                ):
                    return evidence("canonical chain state revision is malformed")
                # The fresh chain state is canonical.  A watchdog context can
                # carry a stale plan from before this transaction acquired
                # its locks; it may only fill an absent legacy value.
                plan_name = str(state.current_plan_name or ctx.get("plan") or "").strip()
                if plan_name:
                    ctx["plan"] = plan_name
                plan_dir = find_plan_dir(workspace, plan_name) if plan_name else None
                with marker_runtime_cutover_lock(marker_path, blocking=False):
                    marker, marker_sha = _load_marker(marker_path)
                    if marker.get("session") != ctx["session"]:
                        return evidence("marker session identity mismatch")
                    if Path(str(marker.get("workspace") or "")).expanduser().resolve(strict=False) != workspace:
                        return evidence("marker workspace identity mismatch")
                    marker_spec = str(marker.get("remote_spec") or "").strip()
                    if marker_spec:
                        marker_spec_path = Path(marker_spec).expanduser()
                        if not marker_spec_path.is_absolute():
                            marker_spec_path = workspace / marker_spec_path
                        if marker_spec_path.resolve(strict=False) != spec_path:
                            return evidence("marker chain spec identity mismatch")
                    marker_pause = marker.get("operator_pause")
                    if "operator_pause" in marker and (
                        not isinstance(marker_pause, dict)
                        or marker_pause.get("schema_version") != "arnold.megaplan.operator-pause.v1"
                        or marker_pause.get("active") is not True
                    ):
                        return evidence("marker pause authority is malformed", marker_sha256=marker_sha)
                    if isinstance(marker_pause, dict) and marker_pause.get("active") is True:
                        return evidence("operator marker pause authority is active", marker_sha256=marker_sha)
                    marker_plan = marker.get("plan")
                    if marker_plan is not None and str(marker_plan) != plan_name:
                        return evidence("marker plan identity mismatch", marker_sha256=marker_sha)
                    if marker.get("should_run") is not True:
                        return evidence("operator marker should_run is not true", marker_sha256=marker_sha)
                    hold = marker.get("operator_resume_hold")
                    if "operator_resume_hold" in marker and not isinstance(hold, dict):
                        return evidence("operator resume hold is malformed", marker_sha256=marker_sha)
                    if isinstance(hold, dict) and hold.get("active") is True:
                        return evidence("operator resume hold is active", marker_sha256=marker_sha)
                    metadata = state.metadata if isinstance(state.metadata, dict) else {}
                    pause = metadata.get("operator_pause")
                    if "operator_pause" in metadata and (
                        not isinstance(pause, dict)
                        or pause.get("schema_version") != "arnold.megaplan.operator-pause.v1"
                        or pause.get("active") is not True
                    ):
                        return evidence("chain pause authority is malformed", marker_sha256=marker_sha)
                    if isinstance(pause, dict) and pause.get("active") is True:
                        return evidence("canonical chain pause authority is active", marker_sha256=marker_sha)
                    if state.last_state == "paused":
                        return evidence("chain state is paused", marker_sha256=marker_sha)
                    if state.current_plan_name and state.current_plan_name != plan_name:
                        return evidence("chain current-plan identity mismatch", marker_sha256=marker_sha)
                    if plan_dir is None:
                        return evidence("canonical plan state is unavailable", marker_sha256=marker_sha)
                    try:
                        plan_payload = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        return evidence("canonical plan state is unreadable", marker_sha256=marker_sha)
                    if not isinstance(plan_payload, dict):
                        return evidence("canonical plan state is malformed", marker_sha256=marker_sha)
                    if plan_payload.get("name") not in {None, plan_name}:
                        return evidence("canonical plan identity mismatch", marker_sha256=marker_sha)
                    if plan_payload.get("current_state") == "paused":
                        return evidence("canonical plan pause state is active", marker_sha256=marker_sha)
                    plan_meta = plan_payload.get("meta")
                    plan_pause = plan_meta.get("operator_pause") if isinstance(plan_meta, dict) else None
                    if isinstance(plan_meta, dict) and "operator_pause" in plan_meta and (
                        not isinstance(plan_pause, dict)
                        or plan_pause.get("schema_version") != "arnold.megaplan.operator-pause.v1"
                        or plan_pause.get("active") is not True
                    ):
                        return evidence("plan pause authority is malformed", marker_sha256=marker_sha)
                    if isinstance(plan_pause, dict) and plan_pause.get("active") is True:
                        return evidence("canonical plan pause authority is active", marker_sha256=marker_sha)

                    reservation_id = hashlib.sha256(
                        json.dumps(
                            ["babysitter-launch-reservation-v1", ctx["session"], ctx["occurrence"], ctx["run_id"], receipt.logical_dispatch_id],
                            sort_keys=True, separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest()
                    reservation = marker.get("babysitter_launch_reservation")
                    if isinstance(reservation, dict):
                        frozen = {
                            key: reservation.get(key)
                            for key in ("schema", "schema_version", "reservation_id", "session", "occurrence_digest", "run_id", "workspace", "managed_run_id", "logical_dispatch_id", "plan", "spec")
                        }
                        expected = {
                            "schema": "arnold.babysitter.launch-reservation.v1",
                            "schema_version": 1,
                            "reservation_id": reservation_id,
                            "session": ctx["session"],
                            "occurrence_digest": ctx["occurrence"],
                            "run_id": ctx["run_id"],
                            "workspace": str(workspace),
                            "managed_run_id": ctx["managed_run_id"],
                            "logical_dispatch_id": receipt.logical_dispatch_id,
                            "plan": plan_name,
                            "spec": str(spec_path),
                        }
                        if frozen != expected:
                            return evidence("marker contains a different launch reservation", marker_sha256=marker_sha)
                        if reservation.get("status") == "cancelled":
                            return evidence("automatic launch reservation was cancelled", marker_sha256=marker_sha)
                        if reservation.get("status") not in {"claimed", "completed"}:
                            return evidence("marker launch reservation has an invalid status", marker_sha256=marker_sha)
                    else:
                        reservation = None

                    admitted = str(receipt.normalized_spec or spec.model)
                    child_spec = spec if admitted == spec.model else replace(spec, model=admitted)
                    manifest_path, manifest, _created = reserve_managed_command(child_spec)
                    if reservation is None:
                        reservation = {
                            "schema": "arnold.babysitter.launch-reservation.v1",
                            "schema_version": 1,
                            "reservation_id": reservation_id,
                            "session": ctx["session"],
                            "occurrence_digest": ctx["occurrence"],
                            "run_id": ctx["run_id"],
                            "workspace": str(workspace),
                            "managed_run_id": str(manifest.get("run_id") or ctx["managed_run_id"]),
                            "logical_dispatch_id": receipt.logical_dispatch_id,
                            "status": "claimed",
                            "claimed_at": _utcnow_iso(),
                            "marker_sha256": marker_sha,
                            "chain_id": chain_id,
                            "chain_state_revision": state_revision,
                            "chain_state_digest": state_digest_for(raw_state),
                            "plan": plan_name,
                            "spec": str(spec_path),
                        }
                        updated = dict(marker)
                        updated["babysitter_launch_reservation"] = reservation
                        _write_marker_locked(marker_path, updated, expected_sha256=marker_sha)
                        ctx["babysitter_launch_reservation"] = reservation
                    else:
                        ctx["babysitter_launch_reservation"] = dict(reservation)
                    ctx["managed_manifest_path"] = str(manifest_path)
                    return {"reservation": dict(reservation), "manifest_path": str(manifest_path)}
        except BlockingIOError:
            return evidence("marker runtime-cutover lock is contended")
        except (ChainControlError, CliError, OSError, ValueError, RuntimeError, TypeError) as exc:
            return evidence(f"automatic admission authority is unreadable: {type(exc).__name__}")

    return preflight


def _validate_automatic_launch_reservation(ctx: Mapping[str, Any]) -> None:
    reservation = ctx.get("babysitter_launch_reservation")
    marker_dir = ctx.get("marker_dir")
    if not isinstance(reservation, Mapping) or not isinstance(marker_dir, Path):
        raise RuntimeError("automatic launch reservation is missing")
    marker_path = marker_dir / f"{ctx['session']}.json"
    from arnold_pipelines.megaplan.cloud.operator_control import (
        _load_marker,
        marker_runtime_cutover_lock,
    )
    from arnold_pipelines.megaplan.chain import spec as chain_spec
    from arnold_pipelines.megaplan.incident.chain_control import (
        ChainControlJournal,
        ChainStateAdapter,
        chain_id_for_spec,
        state_digest_for,
    )
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    workspace = Path(str(ctx.get("workspace") or "")).resolve(strict=False)
    expected_spec = Path(str(ctx.get("remote_spec") or ""))
    if not expected_spec.is_absolute():
        expected_spec = workspace / expected_spec
    expected_spec = expected_spec.resolve(strict=False)
    state_path = chain_spec._state_path_for(expected_spec)
    chain_id = chain_id_for_spec(expected_spec)
    # Keep the same global lock order as automatic preflight and operator
    # pause: sequence -> chain/state -> marker.  The bounded marker wait is
    # intentional after claim: a pause that already owns the marker lock must
    # finish, after which the preserved claimed reservation is re-read.
    journal = ChainControlJournal(IncidentLedger(workspace))
    with journal.transaction(
        chain_ids=[chain_id],
        state_paths=[state_path],
        expected_revision=None,
        operation_id=str(reservation.get("logical_dispatch_id") or ctx.get("run_id") or "automatic-launch"),
        actor={"id": "babysitter", "class": "automatic"},
    ) as txn:
        raw_state = ChainStateAdapter(txn, state_path).read_expected()
        state = None
        if isinstance(raw_state, dict):
            state = chain_spec.ChainState.from_dict(raw_state)
        metadata = state.metadata if state is not None and isinstance(state.metadata, dict) else {}
        current_revision = metadata.get("_nbf08_revision")
        canonical_plan = str(state.current_plan_name or "").strip() if state is not None else ""
        captured_revision = reservation.get("chain_state_revision")
        captured_digest = reservation.get("chain_state_digest")
        with marker_runtime_cutover_lock(
            marker_path,
            blocking=True,
            timeout_s=_AUTOMATIC_FINAL_MARKER_LOCK_TIMEOUT_S,
        ):
            marker, _sha = _load_marker(marker_path)
            current = marker.get("babysitter_launch_reservation")
            if not isinstance(current, Mapping) or dict(current) != dict(reservation):
                raise RuntimeError("automatic launch reservation changed before physical dispatch")
            if (
                current.get("schema") != "arnold.babysitter.launch-reservation.v1"
                or current.get("schema_version") != 1
                or current.get("status") != "claimed"
                or current.get("session") != ctx.get("session")
                or current.get("workspace") != str(workspace)
                or current.get("spec") != str(expected_spec)
                or current.get("occurrence_digest") != ctx.get("occurrence")
                or current.get("run_id") != ctx.get("run_id")
                or current.get("managed_run_id") != ctx.get("managed_run_id")
                or (current.get("chain_id") is not None and current.get("chain_id") != chain_id)
            ):
                raise RuntimeError("automatic launch reservation identity is not canonical")
            reservation_plan = str(current.get("plan") or "").strip()
            # The chain state is the canonical plan authority.  The context
            # may be stale because it was assembled before the transaction;
            # it must neither veto a valid reservation nor authorize drift.
            canonical_plan = canonical_plan or reservation_plan
            if not canonical_plan or reservation_plan != canonical_plan:
                raise RuntimeError("automatic launch reservation plan is not canonical")
            if state is not None and state.current_plan_name and state.current_plan_name != canonical_plan:
                raise RuntimeError("automatic launch chain current-plan identity changed before physical dispatch")
            if marker.get("session") != ctx.get("session"):
                raise RuntimeError("automatic launch marker session changed before physical dispatch")
            if Path(str(marker.get("workspace") or "")).resolve(strict=False) != workspace:
                raise RuntimeError("automatic launch marker workspace changed before physical dispatch")
            marker_spec = str(marker.get("remote_spec") or "")
            if marker_spec:
                marker_spec_path = Path(marker_spec)
                if not marker_spec_path.is_absolute():
                    marker_spec_path = workspace / marker_spec_path
                if marker_spec_path.resolve(strict=False) != expected_spec:
                    raise RuntimeError("automatic launch marker spec changed before physical dispatch")
            if marker.get("plan") is not None and str(marker.get("plan")) != canonical_plan:
                raise RuntimeError("automatic launch marker plan changed before physical dispatch")
            marker_pause = marker.get("operator_pause")
            if "operator_pause" in marker and (
                not isinstance(marker_pause, Mapping)
                or marker_pause.get("schema_version") != "arnold.megaplan.operator-pause.v1"
                or marker_pause.get("active") is not True
            ):
                raise RuntimeError("automatic launch marker pause authority is malformed")
            paused = (
                marker.get("should_run") is False
                and isinstance(marker_pause, Mapping)
                and marker_pause.get("schema_version") == "arnold.megaplan.operator-pause.v1"
                and marker_pause.get("active") is True
            )
            state_changed = (
                ("chain_state_revision" in reservation and captured_revision != current_revision)
                or (
                    "chain_state_digest" in reservation
                    and (raw_state is None or captured_digest != state_digest_for(raw_state))
                )
            )
            # An operator pause is the one authorized post-claim state change:
            # pause_chain advances the state revision/digest and the marker
            # door preserves the exact claimed reservation.  Every other
            # state change remains a CAS failure.  This check is intentionally
            # after the marker lock so it observes the completed pause rather
            # than racing its writer.
            chain_pause = metadata.get("operator_pause")
            chain_pause_valid = (
                isinstance(chain_pause, Mapping)
                and chain_pause.get("schema_version") == "arnold.megaplan.operator-pause.v1"
                and chain_pause.get("active") is True
                and state is not None
                and state.last_state == "paused"
            )
            if state_changed and not (paused and chain_pause_valid):
                raise RuntimeError("automatic launch chain state identity changed before physical dispatch")
            if marker.get("should_run") is not True and not paused:
                raise RuntimeError("automatic launch marker no longer authorizes dispatch")
            hold = marker.get("operator_resume_hold")
            if isinstance(hold, Mapping) and hold.get("active") is True:
                raise RuntimeError("automatic launch marker has an active resume hold")


def _admit_managed_launch(ctx: dict[str, Any], spec: ManagedCommandSpec) -> int:
    """Run the managed command only after one canonical admission decision."""
    from arnold_pipelines.megaplan.cloud.runtime_attestation import require_production_worker_dispatch_runtime
    from arnold_pipelines.megaplan.cloud.runtime_attestation import configured_seed_path
    from arnold_pipelines.megaplan.cloud.runtime_provenance import runtime_provenance
    from arnold_pipelines.megaplan.cloud.worker_dispatch import (
        AdmissionRefusal,
        LaunchResult,
        ManagedCommandResult,
        SchedulingCondition,
        WorkerAdmissionRequest,
        dispatch_with_admission,
        production_provider_probe_executor,
    )
    from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome
    from arnold_pipelines.megaplan.types import parse_agent_spec

    # The immutable managed command spec is the authority for route identity;
    # ambient context cannot substitute a model after the spec is built.
    model = str(spec.model)
    plan = str(ctx.get("plan") or ctx["session"])
    identity = str(ctx.get("managed_run_id") or ctx["run_id"])
    seed_path = configured_seed_path()
    manifest_path = str(os.environ.get("ARNOLD_RUNTIME_MANIFEST") or "")
    seed_identity = ""
    manifest_identity = ""
    try:
        if seed_path is not None and seed_path.is_file():
            seed_identity = hashlib.sha256(seed_path.read_bytes()).hexdigest()
        if manifest_path and Path(manifest_path).is_file():
            manifest_identity = hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest()
    except OSError:
        # Keep the identity empty so the canonical gate returns a typed refusal
        # before the managed command is constructed or started.
        seed_identity = ""
        manifest_identity = ""
    provenance = runtime_provenance()
    configured_specs = tuple(ctx.get("configured_fallback_specs") or (model,))
    request = WorkerAdmissionRequest(
        plan_id=plan,
        phase="babysitter",
        dispatch_family_id=f"babysitter:{ctx['session']}:{ctx['run_id']}",
        logical_dispatch_id=identity,
        physical_door_id="cloud.babysitter.launch",
        configured_spec=model,
        selected_spec=model,
        source_revision=str(provenance.get("source_revision") or ""),
        runtime_vector=provenance,
        manifest_identity=manifest_identity,
        seed_identity=seed_identity,
        dependency_interpreter_identity=str(Path(sys.executable).resolve()),
        prompt_or_phase_input_identity=str(ctx.get("goal_path") or ctx["run_id"]),
        configured_fallback_chain_identity=str(ctx.get("configured_fallback_chain_identity") or ""),
        configured_fallback_specs=configured_specs,
        authorized_route_identity=model,
        projection_key=f"babysitter:{ctx['session']}",
        timeout_budget_s=float(os.environ.get("ARNOLD_BABYSITTER_TIMEOUT_S", "3600")),
        production_intent=True,
        ledger_root=Path(ctx["run_root"]),
        admission_attempt=int(ctx.get("admission_attempt") or 1),
    )

    def launch(context: Any) -> LaunchResult:
        admitted = getattr(context, "selected_spec", None) or model
        parse_agent_spec(admitted)
        if os.environ.get("ARNOLD_BABYSITTER_AUTO_DISPATCH", "").strip() in {"1", "true", "yes"}:
            _validate_automatic_launch_reservation(ctx)
        child_spec = spec if admitted == spec.model else replace(spec, model=admitted)
        pid = os.getpid()
        try:
            from arnold_pipelines.megaplan.watchdog.worker_identity import read_process_start_identity
            start_identity = read_process_start_identity(pid) or f"managed-supervisor:{pid}"
        except Exception:
            start_identity = f"managed-supervisor:{pid}"
        identity_payload = {
            "host": socket.gethostname(),
            "pid": pid,
            "boot_id": "managed-supervisor",
            "process_start_identity": start_identity,
        }
        return LaunchResult(
            True,
            ManagedCommandResult(
                run_managed_command(child_spec),
                worker_identity=identity_payload,
            ),
            worker_identity=identity_payload,
        )

    result = dispatch_with_admission(
        request, launch,
        # Keep the canonical typed outcome at the managed-door boundary.  The
        # integer API is restored below after the outcome is published on ctx.
        gate=require_production_worker_dispatch_runtime,
        probe_executor=production_provider_probe_executor(),
        child_launch=launch,
        admission_preflight=_automatic_dispatch_preflight(ctx, spec),
    )
    if isinstance(result, AdmissionRefusal):
        raise RuntimeError(f"babysitter admission refused: {result.code}: {result.reason}")
    if isinstance(result, SchedulingCondition):
        raise RuntimeError(f"babysitter admission scheduled: {result.reason}")
    if isinstance(result, DispatchOutcome):
        # The managed entry point is an established integer-returning API,
        # while the canonical dispatch path carries the lossless typed
        # terminal outcome.  Keep that outcome on the managed-door context so
        # launch_babysitter can publish it in the receipt without asking the
        # caller to unpack or reinterpret a transport value.
        ctx["dispatch_outcome"] = result.to_dict()
        if result.kind == "no_launch":
            # Suppression is a successful, durable no-start result.  The
            # watchdog maps the child receipt to babysitter_suppressed.
            return 0
        if result.kind == "unresolved_launch":
            raise ManagedLaunchUnresolved(result)
        if result.kind == "success":
            return 0
        if result.kind in {"ordinary_terminal_failure", "provider_exhausted", "worker_disposition"}:
            return 1
    if not isinstance(result, int):
        raise RuntimeError("babysitter admission returned an invalid managed result")
    return result


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
        _continuation_capability_preflight(ctx)
        goal_path = _resolve_goal_file(ctx)
        ctx["goal_path"] = str(goal_path)

        identity_key = (
            f"babysitter:{ctx['session']}:{ctx['occurrence']}:{ctx['run_id']}"
            if os.environ.get("ARNOLD_BABYSITTER_AUTO_DISPATCH", "").strip()
            in {"1", "true", "yes"}
            else (
                f"babysitter:{ctx['session']}:{ctx['occurrence']}:{ctx['run_id']}:"
                f"{time.time_ns()}"
            )
        )
        ctx["identity_key"] = identity_key
        managed_run_id = stable_managed_run_id(RUN_KIND, identity_key)
        ctx["managed_run_id"] = managed_run_id
        ctx["managed_manifest_path"] = str(ctx["run_root"] / managed_run_id / "manifest.json")
        spec = _managed_spec(ctx, goal_path=goal_path, identity_key=identity_key)

        # The managed supervisor reserves the run itself (clean
        # created=True "supervisor_start" path — no pre-reservation, which
        # would be misread as a dead-supervisor restart) and then blocks
        # until the Flash agent finishes.
        rc = _admit_managed_launch(ctx, spec)
        if (ctx.get("dispatch_outcome") or {}).get("kind") == "no_launch":
            _write_receipts(
                ctx,
                _receipt_payload(
                    ctx,
                    status="suppressed",
                    finished_at=_utcnow_iso(),
                    returncode=0,
                    dispatch_outcome=ctx.get("dispatch_outcome"),
                    suppression_reason=(ctx.get("dispatch_outcome") or {}).get("reconciliation_event_id"),
                ),
            )
            return 0
        _write_receipts(ctx, _receipt_payload(ctx, status="running"))
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
        terminal_status = (
            "completed"
            if rc == 0 and managed_terminal == "completed"
            else "interrupted"
            if managed_terminal == "interrupted"
            else "failed"
        )
        # False-success guard (J2/grok consult 2026-08-16): a managed fixer
        # that exits 0 while the target chain/plan is STILL in the failure
        # state is a false success — the watchdog will not re-dispatch a
        # `completed` run, so the chain strands. Downgrade to `failed` when
        # the plan the babysitter was dispatched for is still blocked/failed
        # with a matching failure kind, so the next watchdog scan relaunches
        # the repair for the same occurrence.
        false_success_reason = ""
        if terminal_status == "completed":
            try:
                plan_name = str(ctx.get("plan") or "").strip()
                workspace = str(ctx.get("workspace") or "").strip()
                if plan_name and workspace:
                    plan_state_path = (
                        Path(workspace) / ".megaplan" / "plans" / plan_name / "state.json"
                    )
                    if plan_state_path.is_file():
                        plan_payload = json.loads(
                            plan_state_path.read_text(encoding="utf-8")
                        )
                        state = str(plan_payload.get("current_state") or "")
                        if state in {"blocked", "failed"}:
                            failure = plan_payload.get("latest_failure") or {}
                            failure_kind = str(failure.get("kind") or "")
                            false_success_reason = (
                                f"plan still {state} after fixer exit; "
                                f"failure_kind={failure_kind or 'unknown'}"
                            )
            except (OSError, json.JSONDecodeError):
                pass
        if false_success_reason:
            terminal_status = "failed"
            _eprint(
                f"[babysitter] FALSE SUCCESS downgraded to failed "
                f"session={ctx.get('session', '?')} occurrence={ctx.get('occurrence', '?')} "
                f"reason={false_success_reason}"
            )
        if terminal_status == "completed":
            custody_error = _chain_drive_custody_error(ctx)
            if custody_error:
                terminal_status = "failed"
                false_success_reason = custody_error
                _eprint(
                    f"[babysitter] FALSE SUCCESS downgraded to failed "
                    f"session={ctx.get('session', '?')} occurrence={ctx.get('occurrence', '?')} "
                    f"reason={custody_error}"
                )
        _write_receipts(
            ctx,
            _receipt_payload(
                ctx,
                status=terminal_status,
                finished_at=_utcnow_iso(),
                returncode=rc,
                managed_terminal_status=managed_terminal,
                dispatch_outcome=ctx.get("dispatch_outcome"),
                false_success_reason=false_success_reason or None,
            ),
        )
        return _terminal_returncode(rc, terminal_status)
    except SystemExit:
        raise
    except ManagedLaunchUnresolved as exc:
        _eprint(json.dumps({"dispatch_outcome": exc.outcome.to_dict()}, sort_keys=True))
        try:
            _write_receipts(
                ctx,
                _receipt_payload(
                    ctx,
                    status="unresolved",
                    finished_at=_utcnow_iso(),
                    returncode=2,
                    dispatch_outcome=exc.outcome.to_dict(),
                ),
            )
        except BaseException as write_exc:
            _eprint(f"[babysitter] could not record unresolved receipt: {write_exc!r}")
        return 2
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
