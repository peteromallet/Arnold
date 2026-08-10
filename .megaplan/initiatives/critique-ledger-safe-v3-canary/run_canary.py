#!/usr/bin/env python3
"""One finite CL2 planning lifecycle; every admitted path emits a terminal receipt."""

from __future__ import annotations

import hashlib
import base64
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INITIAL_PHASES = ("init", "plan", "critique", "gate")
REVISE_PHASES = ("revise", "critique", "gate")
MAX_PHASES = (*INITIAL_PHASES, *REVISE_PHASES, "finalize")
MODEL_PHASES = frozenset(MAX_PHASES) - {"init"}
CANARY_ID = "critique-ledger-safe-v3-canary"
PLAN_NAME = "critique-ledger-cl2-planning-canary"
PRODUCT_REVISE_STOP_CODES = frozenset(
    {
        "north_star_revise_human_halt",
        "north_star_revise_unresolved_blocking",
    }
)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trusted_phase_failure_artifact(
    plan_dir: Path, phase: str, plan_iteration: int
) -> str:
    """Bind the primary child failure artifact without copying its contents."""
    candidates = sorted(plan_dir.glob(f"{phase}_v{plan_iteration}_raw.txt"))
    if len(candidates) != 1:
        return "unavailable"
    path = candidates[0]
    observed = os.lstat(path)
    if (
        not stat.S_ISREG(observed.st_mode)
        or observed.st_nlink != 1
        or observed.st_uid != os.geteuid()
        or observed.st_mode & 0o022
        or observed.st_size > 1_048_576
    ):
        return "untrusted"
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (observed.st_dev, observed.st_ino):
            return "raced"
        digest = hashlib.sha256()
        while chunk := os.read(fd, 1024 * 1024):
            digest.update(chunk)
    finally:
        os.close(fd)
    return f"{path.name}:sha256={digest.hexdigest()}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def strict_object(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} is not an object")
    return value


def classify_product_revise_stop(
    plan_dir: Path,
    *,
    stdout: str,
    returncode: int,
    plan_iteration: int,
    ledger_path: Path,
    prior_dispatch_expectations: list[tuple[str, int]],
) -> dict[str, Any] | None:
    """Admit only typed, cross-checked revise product stops.

    The phase CLI is allowed to stop before or after its worker when a carried
    North Star action requires a human or remains unresolved.  Those are
    product outcomes, not provider/infrastructure failures.  Any malformed,
    untyped, state-drifting, or ledger-inconsistent nonzero remains on the
    generic infrastructure-failure path.
    """
    if returncode != 1:
        return None

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate CLI error field: {key}")
            value[key] = item
        return value

    try:
        payload = json.loads(stdout.strip(), object_pairs_hook=reject_duplicates)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("error") not in PRODUCT_REVISE_STOP_CODES:
        return None
    if (
        set(payload) != {"success", "error", "message", "valid_next", "details"}
        or payload.get("success") is not False
        or not isinstance(payload.get("message"), str)
        or not isinstance(payload.get("valid_next"), list)
        or any(not isinstance(item, str) for item in payload["valid_next"])
        or not isinstance(payload.get("details"), dict)
    ):
        raise RuntimeError("product_revise_stop_cli_contract_mismatch")

    error_code = str(payload["error"])
    details = payload["details"]
    action_key = (
        "halt_actions"
        if error_code == "north_star_revise_human_halt"
        else "unresolved_actions"
    )
    if (
        set(details) != {"step", action_key, "count"}
        or details.get("step") != "revise"
        or not isinstance(details.get(action_key), list)
        or not details[action_key]
        or details.get("count") != len(details[action_key])
    ):
        raise RuntimeError("product_revise_stop_details_mismatch")
    action_ids = [
        item.get("id") if isinstance(item, dict) else None
        for item in details[action_key]
    ]
    if (
        any(not isinstance(item, str) or not item for item in action_ids)
        or len(set(action_ids)) != len(action_ids)
    ):
        raise RuntimeError("product_revise_stop_action_identity_mismatch")

    phase_result = strict_object(plan_dir / "phase_result.json")
    blocked_tasks = phase_result.get("blocked_tasks")
    if (
        phase_result.get("schema") != "megaplan.phase_result"
        or phase_result.get("schema_version") != 1
        or phase_result.get("phase_result_contract_version") != 1
        or phase_result.get("phase") != "revise"
        or phase_result.get("exit_kind") != "blocked_by_prereq"
        or phase_result.get("external_error") is not None
        or not isinstance(blocked_tasks, list)
        or len(blocked_tasks) != len(action_ids)
    ):
        raise RuntimeError("product_revise_stop_phase_result_mismatch")
    phase_action_ids: list[str] = []
    for task in blocked_tasks:
        if (
            not isinstance(task, dict)
            or task.get("blocker_kind") != error_code
            or not isinstance(task.get("blocking_action_ids"), list)
            or len(task["blocking_action_ids"]) != 1
            or task.get("task_id") != task["blocking_action_ids"][0]
        ):
            raise RuntimeError("product_revise_stop_blocked_task_mismatch")
        phase_action_ids.append(task["task_id"])
    if phase_action_ids != action_ids:
        raise RuntimeError("product_revise_stop_action_order_mismatch")

    state = strict_object(plan_dir / "state.json")
    if (
        state.get("current_state") != "critiqued"
        or state.get("iteration") != plan_iteration - 1
        or state.get("active_step") not in (None, "")
    ):
        raise RuntimeError("product_revise_stop_state_mismatch")
    carry_path = plan_dir / "gate_carry.json"
    carry = strict_object(carry_path if carry_path.is_file() else plan_dir / "gate.json")
    carried_actions = carry.get("north_star_actions")
    if not isinstance(carried_actions, list):
        raise RuntimeError("product_revise_stop_carry_missing")
    carried_by_id = {
        item.get("id"): item for item in carried_actions
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if any(action_id not in carried_by_id for action_id in action_ids):
        raise RuntimeError("product_revise_stop_not_carried")
    if error_code == "north_star_revise_human_halt" and any(
        carried_by_id[action_id].get("action_type") != "add_human_halt"
        for action_id in action_ids
    ):
        raise RuntimeError("product_revise_human_halt_type_mismatch")

    records = read_dispatch_records(ledger_path)
    revise_dispatched = error_code == "north_star_revise_unresolved_blocking"
    expected = list(prior_dispatch_expectations)
    if revise_dispatched:
        expected.append(("revise", plan_iteration))
    if len(records) != 2 * len(expected):
        raise RuntimeError("product_revise_stop_dispatch_count_mismatch")
    read_dispatch_ledger(ledger_path, expected)
    return {
        "kind": "product_revise_blocked",
        "reason_code": error_code,
        "action_ids": action_ids,
        "revise_dispatch_started": revise_dispatched,
        "state": state,
    }


def classify_gate(
    recommendation: object,
    *,
    current_state: object,
    active_step: object,
    gate_attempt: int,
) -> str:
    """Classify product gate authority before applying generic state checks."""
    if gate_attempt not in {1, 2}:
        raise RuntimeError("gate_attempt_out_of_bounds")
    if recommendation not in {"PROCEED", "ITERATE", "ESCALATE", "TIEBREAKER"}:
        raise RuntimeError("invalid_gate_recommendation")
    if active_step not in (None, ""):
        raise RuntimeError("gate_returned_with_active_state")
    if recommendation == "PROCEED":
        if current_state != "gated":
            raise RuntimeError("proceed_without_gated_state")
        return "finalize"
    if current_state != "critiqued":
        raise RuntimeError("nonproceed_without_critiqued_state")
    if recommendation == "ITERATE" and gate_attempt == 1:
        return "revise_once"
    return "product_gate_not_proceed"


def write_once(path: Path, payload: dict[str, object]) -> None:
    if path.parent.resolve() != path.parent.absolute():
        raise RuntimeError("receipt parent contains a symlink")
    parent_stat = os.lstat(path.parent)
    if stat.S_ISLNK(parent_stat.st_mode) or not stat.S_ISDIR(parent_stat.st_mode):
        raise RuntimeError("receipt parent is not a no-follow directory")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def git_object(root: Path, expression: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", expression], cwd=root, text=True,
        capture_output=True, check=True, env={"PATH": os.environ.get("PATH", "")},
    )
    value = result.stdout.strip()
    if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"invalid git object for {expression}")
    return value


def repository_integrity(
    root: Path,
    *,
    source_commit: str,
    source_tree: str,
    checkpoint: str,
) -> dict[str, Any]:
    """Prove admitted Git identity and allow only exact canary runtime outputs."""
    head = git_object(root, "HEAD")
    tree = git_object(root, "HEAD^{tree}")
    if head != source_commit or tree != source_tree:
        raise RuntimeError(f"repository identity drift at {checkpoint}")
    git_env = {"PATH": os.environ.get("PATH", "")}
    for argv in (
        ["git", "diff", "--quiet", "HEAD", "--"],
        ["git", "diff", "--cached", "--quiet", "HEAD", "--"],
    ):
        result = subprocess.run(argv, cwd=root, env=git_env, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"tracked or index mutation at {checkpoint}")
    allowed_roots = (
        f".megaplan/plans/{PLAN_NAME}",
        ".megaplan/initiatives/critique-ledger-safe-v3-canary/receipts",
    )
    runtime_delta: list[dict[str, Any]] = []
    untracked: set[str] = set()
    for argv in (
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "-z"],
    ):
        result = subprocess.run(
            argv, cwd=root, env=git_env, capture_output=True, check=True
        )
        for raw_path in result.stdout.split(b"\0"):
            if not raw_path:
                continue
            relative = raw_path.decode("utf-8", errors="strict")
            normalized = Path(relative)
            if (
                normalized.is_absolute()
                or ".." in normalized.parts
                or normalized.as_posix() != relative
            ):
                raise RuntimeError(f"invalid Git runtime path at {checkpoint}")
            untracked.add(relative)
    for relative in sorted(untracked):
        if not any(
            relative == allowed or relative.startswith(allowed + "/")
            for allowed in allowed_roots
        ):
            raise RuntimeError(f"forbidden untracked path at {checkpoint}: {relative}")
        candidate = root / relative
        if candidate.is_symlink():
            identity = hashlib.sha256(os.readlink(candidate).encode()).hexdigest()
            kind = "symlink"
        elif candidate.is_file():
            identity = sha(candidate)
            kind = "file"
        else:
            raise RuntimeError(f"unsupported runtime path at {checkpoint}: {relative}")
        runtime_delta.append({"path": relative, "kind": kind, "sha256": identity})
    runtime_delta.sort(key=lambda item: str(item["path"]))
    unsigned: dict[str, Any] = {
        "schema": "arnold.megaplan.finite_canary_repository_integrity.v1",
        "checkpoint": checkpoint,
        "head": head,
        "tree": tree,
        "tracked_clean": True,
        "runtime_delta": runtime_delta,
    }
    unsigned["runtime_delta_digest"] = hashlib.sha256(
        canonical(runtime_delta)
    ).hexdigest()
    return unsigned


def read_dispatch_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    records: list[dict[str, Any]] = []
    for line in lines:
        def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError(f"duplicate dispatch field: {key}")
                value[key] = item
            return value

        value = json.loads(line, object_pairs_hook=reject_duplicates)
        if not isinstance(value, dict):
            raise ValueError("dispatch record is not an object")
        records.append(value)
    return records


def read_dispatch_ledger(
    path: Path, expected: list[tuple[str, int]]
) -> list[dict[str, Any]]:
    records = read_dispatch_records(path)
    if not expected:
        if records:
            raise ValueError("init unexpectedly dispatched a model")
        return []
    if len(records) != 2 * len(expected):
        raise ValueError("dispatch ledger does not contain one start/terminal pair per phase")
    for index, (phase, plan_iteration) in enumerate(expected, start=1):
        start, terminal = records[(index - 1) * 2 : (index - 1) * 2 + 2]
        if (
            start.get("schema") != "arnold.megaplan.zero_recovery_dispatch.v2"
            or terminal.get("schema") != "arnold.megaplan.zero_recovery_dispatch.v2"
            or start.get("event") != "start"
            or terminal.get("event") != "terminal"
            or start.get("phase") != phase
            or terminal.get("phase") != phase
            or not isinstance(start.get("dispatch_id"), str)
            or terminal.get("dispatch_id") != start.get("dispatch_id")
            or start.get("selected_agent") != "codex"
            or terminal.get("actual_agent") != "codex"
            or start.get("selected_model") != "gpt-5.6-sol"
            or terminal.get("actual_model") != "gpt-5.6-sol"
            or terminal.get("model_evidence") != "codex_cli_turn_context"
            or terminal.get("privilege_receipt_path")
            != (
                f".zero-recovery-{index:02d}-{phase}-i{plan_iteration}"
                "-privilege-receipt.json"
            )
            or not isinstance(terminal.get("privilege_receipt_sha256"), str)
            or len(terminal["privilege_receipt_sha256"]) != 64
            or sha(path.parent / terminal["privilege_receipt_path"])
            != terminal["privilege_receipt_sha256"]
            or not isinstance(terminal.get("rollout_path"), str)
            or not terminal["rollout_path"].startswith("sessions/")
            or ".." in Path(terminal["rollout_path"]).parts
            or not isinstance(terminal.get("rollout_sha256"), str)
            or len(terminal["rollout_sha256"]) != 64
            or start.get("selected_effort") != "high"
            or start.get("model_cli_argv") != ["-c", "model='gpt-5.6-sol'"]
            or terminal.get("actual_effort") != "high"
            or start.get("attempt") != 1
            or terminal.get("attempt") != 1
            or start.get("plan_iteration") != plan_iteration
            or terminal.get("plan_iteration") != plan_iteration
            or start.get("dispatch_ordinal") != index
            or terminal.get("dispatch_ordinal") != index
            or terminal.get("result") != "returned"
            or any(item.get(key) is not False for item in (start, terminal) for key in ("retry", "fallback", "json_repair", "adaptive_routing"))
        ):
            raise ValueError("dispatch ledger contains retry, fallback, repair, or model drift")
    return records


def phase_receipt(
    receipt_dir: Path,
    index: int,
    phase: str,
    plan_iteration: int,
    dispatch_ordinal: int | None,
    *,
    status: str,
    returncode: int,
    state: str | None,
    reason: str | None,
    argv: list[str],
    state_path: Path,
    ledger_path: Path,
    integrity_before: dict[str, Any] | None,
    integrity_after: dict[str, Any] | None,
    stdout: str,
    stderr: str,
) -> None:
    phase_terminals = [
        record
        for record in read_dispatch_records(ledger_path)
        if record.get("event") == "terminal"
        and record.get("dispatch_ordinal") == dispatch_ordinal
    ]
    privilege_receipt_sha256 = (
        phase_terminals[0].get("privilege_receipt_sha256")
        if len(phase_terminals) == 1
        else None
    )
    payload: dict[str, object] = {
        "schema": "arnold.megaplan.finite_canary_phase_receipt.v3",
        "phase": phase,
        "plan_iteration": plan_iteration,
        "dispatch_ordinal": dispatch_ordinal,
        "status": status,
        "returncode": returncode,
        "state": state,
        "reason": reason,
        "argv": argv,
        "state_sha256": sha(state_path) if state_path.is_file() else None,
        "dispatch_ledger_sha256": sha(ledger_path) if ledger_path.is_file() else None,
        "privilege_receipt_sha256": privilege_receipt_sha256,
        "integrity_before": integrity_before,
        "integrity_after": integrity_after,
        "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
        "stdout_tail": stdout[-4096:],
        "stderr_tail": stderr[-4096:],
        "completed_at": now(),
    }
    write_once(receipt_dir / f"{index:02d}-{phase}.phase-receipt.json", payload)


def run_locked(root: Path, initiative: Path, receipt_dir: Path) -> tuple[int, dict[str, object]]:
    plan_dir = root / ".megaplan/plans" / PLAN_NAME
    if plan_dir.exists():
        raise RuntimeError("finite canary plan identity already exists")
    idea = initiative / "briefs/cl2-ledger-persistence-and-replay.md"
    north_star = initiative / "NORTHSTAR.md"
    init_command = [
        sys.executable, "-P", "-m", "arnold_pipelines.megaplan", "init",
        "--project-dir", str(root), "--name", PLAN_NAME, "--auto-approve",
        "--idea-file", str(idea), "--north-star", str(north_star),
        "--robustness", "full", "--no-adaptive-critique", "--vendor", "codex",
        "--phase-model", "plan=codex:gpt-5.6-sol:high",
        "--phase-model", "critique=codex:gpt-5.6-sol:high",
        "--phase-model", "gate=codex:gpt-5.6-sol:high",
        "--phase-model", "revise=codex:gpt-5.6-sol:high",
        "--phase-model", "finalize=codex:gpt-5.6-sol:high",
    ]

    def command_for(phase: str) -> list[str]:
        if phase == "init":
            return list(init_command)
        return [
            sys.executable, "-P", "-m", "arnold_pipelines.megaplan", phase,
            "--plan", PLAN_NAME, "--fresh",
        ]

    maximum_commands = [command_for(phase) for phase in MAX_PHASES]
    allowed_environment = (
        "PATH", "LANG", "LC_ALL", "LC_CTYPE", "SSL_CERT_FILE", "SSL_CERT_DIR",
        "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    )
    child_env = {key: os.environ[key] for key in allowed_environment if key in os.environ}
    child_env.update({
        "MEGAPLAN_ZERO_RECOVERY_CANARY": "1",
        "MEGAPLAN_TRUSTED_CONTAINER": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOME": "/root",
        "PYTHONPATH": str(root),
    })
    source_commit = git_object(root, "HEAD")
    source_tree = git_object(root, "HEAD^{tree}")
    if source_commit != os.environ.get("ZERO_RECOVERY_SOURCE_COMMIT") or source_tree != os.environ.get("ZERO_RECOVERY_SOURCE_TREE"):
        raise RuntimeError("runner source identity differs from host admission")
    # This is the sole Git-backed admission check. No Git command is trusted
    # after a child process has run.
    repository_integrity(
        root,
        source_commit=source_commit,
        source_tree=source_tree,
        checkpoint="pre-import-admission",
    )
    import arnold_pipelines.megaplan as megaplan
    from arnold_pipelines.megaplan.workers._impl import (
        _assert_zero_recovery_source_unchanged,
        _zero_recovery_source_identity,
    )
    from arnold_pipelines.megaplan._core import ensure_runtime_layout
    import_root = Path(megaplan.__file__).resolve()
    if root not in import_root.parents:
        raise RuntimeError("megaplan import escaped admitted checkout")
    # Init rewrites these ignored projections from tracked canonical schemas.
    # Establish and bind them before the direct-source baseline so post:init
    # verification admits only the exact unchanged schema set.
    ensure_runtime_layout(root)
    source_manifest = _zero_recovery_source_identity(root, plan_dir)
    if source_manifest is None:
        raise RuntimeError("direct source manifest was not enabled")

    def direct_integrity(checkpoint: str) -> dict[str, Any]:
        nonlocal source_manifest
        observed = _assert_zero_recovery_source_unchanged(
            root, plan_dir, source_manifest
        )
        if observed is None:
            raise RuntimeError("direct source verification was not enabled")
        source_manifest = observed
        runtime_delta = [
            {
                "path": item["path"],
                "kind": item["kind"],
                "sha256": item["sha256"],
            }
            for item in observed["runtime_delta"]
        ]
        engine_runtime = {
            name: (
                {
                    key: value
                    for key, value in record.items()
                    if key != "_raw"
                }
                if record is not None
                else None
            )
            for name, record in observed["engine_runtime"].items()
        }
        unsigned: dict[str, Any] = {
            "schema": "arnold.megaplan.finite_canary_repository_integrity.v1",
            "checkpoint": checkpoint,
            "head": source_commit,
            "tree": source_tree,
            "tracked_clean": True,
            "source_manifest_digest": hashlib.sha256(
                canonical(source_manifest["tracked"])
            ).hexdigest(),
            "git_metadata_digest": hashlib.sha256(
                canonical(source_manifest["git_metadata"])
            ).hexdigest(),
            "runtime_delta": runtime_delta,
            "engine_runtime": engine_runtime,
        }
        unsigned["runtime_delta_digest"] = hashlib.sha256(
            canonical(runtime_delta)
        ).hexdigest()
        return unsigned

    integrity_checkpoints = [direct_integrity("baseline")]
    manifest_paths = (
        ".megaplan/initiatives/critique-ledger-safe-v3-canary/canary.yaml",
        ".megaplan/initiatives/critique-ledger-safe-v3-canary/cloud.yaml",
        ".megaplan/initiatives/critique-ledger-safe-v3-canary/proof-map.json",
        ".megaplan/initiatives/critique-ledger-safe-v3-canary/traceability.json",
    )
    def reject_manifest_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate manifest hash: {key}")
            result[key] = value
        return result

    admitted_manifest_hashes = json.loads(
        base64.b64decode(
            os.environ.get("ZERO_RECOVERY_MANIFEST_SHA256_B64", ""), validate=True
        ).decode("utf-8"),
        object_pairs_hook=reject_manifest_duplicates,
    )
    actual_manifest_hashes = {relative: sha(root / relative) for relative in manifest_paths}
    if admitted_manifest_hashes != actual_manifest_hashes:
        raise RuntimeError("runner manifest hashes differ from host admission")
    write_once(receipt_dir / "run-context.json", {
        "schema": "arnold.megaplan.finite_canary_run_context.v2",
        "source_commit": source_commit,
        "source_tree": source_tree,
        "import_root": str(import_root),
        "maximum_phase_commands": maximum_commands,
        "launch_manifest_sha256": actual_manifest_hashes,
        "recorded_at": now(),
    })

    started_at = now()
    results: list[dict[str, object]] = []
    failure: dict[str, object] | None = None
    infrastructure_status = "passed"
    terminal_state = "failed"
    product_outcome: dict[str, object] | None = None
    gate_attempts: list[dict[str, object]] = []
    ledger_path = plan_dir / "zero_recovery_dispatch_ledger.ndjson"
    scheduled = list(INITIAL_PHASES)
    dispatch_expectations: list[tuple[str, int]] = []
    index = 0
    while index < len(scheduled):
        phase = scheduled[index]
        argv = command_for(phase)
        pre_iteration = 0
        pre_state_path = plan_dir / "state.json"
        if pre_state_path.is_file():
            pre_state = strict_object(pre_state_path)
            pre_iteration = int(pre_state.get("iteration", 0) or 0)
        phase_plan_iteration = (
            pre_iteration + 1 if phase in {"plan", "revise"} else pre_iteration
        )
        dispatch_ordinal = (
            len(dispatch_expectations) + 1 if phase in MODEL_PHASES else None
        )
        integrity_before = direct_integrity(f"pre:{phase}")
        integrity_checkpoints.append(integrity_before)
        write_once(receipt_dir / f"{index:02d}-{phase}.started.json", {
            "schema": "arnold.megaplan.finite_canary_phase_checkpoint.v2",
            "phase": phase, "plan_iteration": phase_plan_iteration,
            "dispatch_ordinal": dispatch_ordinal,
            "argv": argv, "started_at": now(),
            "import_root": str(import_root),
            "repository_integrity": integrity_before,
        })
        integrity_after: dict[str, Any] | None = None
        phase_stdout = ""
        phase_stderr = ""
        phase_execution_error: BaseException | None = None
        completed: subprocess.CompletedProcess[str] | None = None
        try:
            try:
                try:
                    completed = subprocess.run(
                        argv, cwd=root, env=child_env, text=True, capture_output=True,
                        check=False, timeout=3600,
                    )
                except BaseException as exc:
                    phase_execution_error = exc
                    raise
                phase_stdout = completed.stdout or ""
                phase_stderr = completed.stderr or ""
            finally:
                # This executes on success, nonzero exit, timeout, and signal.
                # Do not parse child output before checkout identity and the
                # complete runtime delta have been re-established.
                try:
                    integrity_after = direct_integrity(f"post:{phase}")
                    integrity_checkpoints.append(integrity_after)
                except BaseException as integrity_exc:
                    if phase_execution_error is not None:
                        primary = type(phase_execution_error).__name__
                    elif completed is not None and completed.returncode != 0:
                        primary = (
                            f"child_nonzero:{completed.returncode};"
                            "primary_artifact="
                            f"{trusted_phase_failure_artifact(plan_dir, phase, phase_plan_iteration)}"
                        )
                    else:
                        raise
                    raise RuntimeError(
                        f"{primary};secondary_integrity="
                        f"{type(integrity_exc).__name__}:{integrity_exc}"
                    ) from integrity_exc
            returncode = completed.returncode
            if completed.returncode != 0:
                product_stop = (
                    classify_product_revise_stop(
                        plan_dir,
                        stdout=phase_stdout,
                        returncode=returncode,
                        plan_iteration=phase_plan_iteration,
                        ledger_path=ledger_path,
                        prior_dispatch_expectations=dispatch_expectations,
                    )
                    if phase == "revise"
                    else None
                )
                if product_stop is not None:
                    revise_dispatched = bool(product_stop["revise_dispatch_started"])
                    if revise_dispatched:
                        dispatch_expectations.append((phase, phase_plan_iteration))
                    state = product_stop.pop("state")
                    current_state = state.get("current_state")
                    terminal_state = "product_revise_blocked"
                    product_outcome = {
                        **product_stop,
                        "gate_attempt": len(gate_attempts),
                    }
                    results.append({
                        "phase": phase,
                        "plan_iteration": phase_plan_iteration,
                        "dispatch_ordinal": (
                            dispatch_ordinal if revise_dispatched else None
                        ),
                        "returncode": returncode,
                        "state": current_state,
                        "gate_recommendation": None,
                    })
                    phase_receipt(
                        receipt_dir,
                        index,
                        phase,
                        plan_iteration=phase_plan_iteration,
                        dispatch_ordinal=(
                            dispatch_ordinal if revise_dispatched else None
                        ),
                        status="product_terminal",
                        returncode=returncode,
                        state=str(current_state),
                        reason=str(product_outcome["reason_code"]),
                        argv=argv,
                        state_path=plan_dir / "state.json",
                        ledger_path=ledger_path,
                        integrity_before=integrity_before,
                        integrity_after=integrity_after,
                        stdout=phase_stdout,
                        stderr=phase_stderr,
                    )
                    index += 1
                    break
                raise RuntimeError(f"nonzero_returncode:{returncode}")
            state_path = plan_dir / "state.json"
            state = strict_object(state_path)
            current_state = state.get("current_state")
            actual_iteration = int(state.get("iteration", 0) or 0)
            if actual_iteration != phase_plan_iteration:
                raise RuntimeError("phase_plan_iteration_mismatch")
            if phase in MODEL_PHASES:
                dispatch_expectations.append((phase, phase_plan_iteration))
                read_dispatch_ledger(ledger_path, dispatch_expectations)
            gate_recommendation: str | None = None
            if phase == "gate":
                gate = strict_object(plan_dir / "gate.json")
                gate_recommendation = gate.get("recommendation")
                gate_route = classify_gate(
                    gate_recommendation,
                    current_state=current_state,
                    active_step=state.get("active_step"),
                    gate_attempt=len(gate_attempts) + 1,
                )
                gate_attempts.append({
                    "attempt": len(gate_attempts) + 1,
                    "plan_iteration": actual_iteration,
                    "recommendation": gate_recommendation,
                    "state": current_state,
                    "gate_sha256": sha(plan_dir / "gate.json"),
                })
                if gate_route == "finalize":
                    product_outcome = {
                        "kind": "proceed", "gate_attempt": len(gate_attempts),
                        "recommendation": gate_recommendation,
                    }
                    scheduled.append("finalize")
                elif gate_route == "revise_once":
                    scheduled.extend(REVISE_PHASES)
                else:
                    terminal_state = "product_gate_not_proceed"
                    product_outcome = {
                        "kind": "product_gate_not_proceed",
                        "gate_attempt": len(gate_attempts),
                        "recommendation": gate_recommendation,
                    }
            else:
                expected_state = {
                    "init": "initialized", "plan": "planned",
                    "critique": "critiqued", "revise": "planned",
                    "finalize": "finalized",
                }[phase]
                if current_state != expected_state or state.get("active_step") not in (None, ""):
                    raise RuntimeError("unexpected_or_active_state")
                if phase == "finalize":
                    terminal_state = "finalized"
                    product_outcome = {
                        "kind": "proceed_finalized",
                        "gate_attempt": len(gate_attempts),
                        "recommendation": "PROCEED",
                    }
            results.append({
                "phase": phase, "plan_iteration": actual_iteration,
                "dispatch_ordinal": dispatch_ordinal,
                "returncode": 0, "state": current_state,
                "gate_recommendation": gate_recommendation,
            })
            phase_receipt(receipt_dir, index, phase,
                          plan_iteration=actual_iteration,
                          dispatch_ordinal=dispatch_ordinal,
                          status="passed", returncode=0,
                          state=str(current_state), reason=None, argv=argv,
                          state_path=state_path, ledger_path=ledger_path,
                          integrity_before=integrity_before,
                          integrity_after=integrity_after,
                          stdout=phase_stdout, stderr=phase_stderr)
        except subprocess.TimeoutExpired as exc:
            raw_stdout = exc.stdout or ""
            raw_stderr = exc.stderr or ""
            phase_stdout = (
                raw_stdout.decode("utf-8", errors="replace")
                if isinstance(raw_stdout, bytes) else raw_stdout
            )
            phase_stderr = (
                raw_stderr.decode("utf-8", errors="replace")
                if isinstance(raw_stderr, bytes) else raw_stderr
            )
            returncode = 124
            reason = "timeout"
        except BaseException as exc:
            returncode = locals().get("returncode", 1)
            reason = f"{type(exc).__name__}:{str(exc)[:160]}"
        else:
            index += 1
            if terminal_state in {
                "product_gate_not_proceed",
                "product_revise_blocked",
            }:
                break
            continue
        infrastructure_status = "failed"
        terminal_state = "failed"
        failure = {"phase": phase, "reason": reason, "returncode": returncode}
        state_path = plan_dir / "state.json"
        current_state = None
        if state_path.is_file():
            try:
                current_state = strict_object(state_path).get("current_state")
            except BaseException:
                pass
        results.append({
            "phase": phase, "plan_iteration": phase_plan_iteration,
            "dispatch_ordinal": dispatch_ordinal,
            "returncode": returncode, "state": current_state,
            "gate_recommendation": None,
        })
        phase_receipt(receipt_dir, index, phase,
                      plan_iteration=phase_plan_iteration,
                      dispatch_ordinal=dispatch_ordinal,
                      status="failed", returncode=returncode,
                      state=str(current_state) if current_state is not None else None,
                      reason=reason, argv=argv, state_path=state_path,
                      ledger_path=ledger_path,
                      integrity_before=integrity_before,
                      integrity_after=integrity_after,
                      stdout=phase_stdout, stderr=phase_stderr)
        break

    state_path = plan_dir / "state.json"
    ledger_records = (
        read_dispatch_ledger(ledger_path, dispatch_expectations)
        if infrastructure_status == "passed"
        else read_dispatch_records(ledger_path)
    )
    dispatch_integrity = (
        "complete"
        if infrastructure_status == "passed"
        else "partial"
        if ledger_records
        else "not_started"
    )
    phase_receipt_entries = [
        {
            "phase": result["phase"],
            "plan_iteration": result["plan_iteration"],
            "dispatch_ordinal": result["dispatch_ordinal"],
            "path": str(
                (
                    receipt_dir
                    / f"{index:02d}-{result['phase']}.phase-receipt.json"
                ).relative_to(root)
            ),
            "sha256": sha(
                receipt_dir / f"{index:02d}-{result['phase']}.phase-receipt.json"
            ),
        }
        for index, result in enumerate(results)
    ]
    phase_manifest = {
        "schema": "arnold.megaplan.finite_canary_phase_receipts_manifest.v2",
        "canary_id": CANARY_ID,
        "plan_name": PLAN_NAME,
        "entries": phase_receipt_entries,
    }
    phase_manifest_path = receipt_dir / "phase-receipts-manifest.json"
    write_once(phase_manifest_path, phase_manifest)
    privilege_entries = [
        {
            "phase": record["phase"],
            "plan_iteration": record["plan_iteration"],
            "dispatch_ordinal": record["dispatch_ordinal"],
            "path": str(
                (plan_dir / record["privilege_receipt_path"]).relative_to(root)
            ),
            "sha256": record["privilege_receipt_sha256"],
        }
        for record in ledger_records
        if record.get("event") == "terminal"
    ]
    privilege_manifest_path = receipt_dir / "privilege-receipts-manifest.json"
    write_once(privilege_manifest_path, {
        "schema": "arnold.megaplan.zero_recovery_privilege_receipts_manifest.v2",
        "entries": privilege_entries,
    })
    final_integrity = direct_integrity("final")
    integrity_checkpoints.append(final_integrity)
    unsigned: dict[str, object] = {
        "schema": "arnold.megaplan.finite_canary_run_receipt.v3",
        "status": infrastructure_status,
        "canary_id": CANARY_ID,
        "plan_name": PLAN_NAME,
        "phases": [result["phase"] for result in results],
        "phase_results": results,
        "terminal_state": terminal_state,
        "product_outcome": product_outcome,
        "gate_attempts": gate_attempts,
        "failure": failure,
        "started_at": started_at,
        "completed_at": now(),
        "source_commit": source_commit,
        "source_tree": source_tree,
        "canary_spec_sha256": sha(initiative / "canary.yaml"),
        "launch_manifest_sha256": actual_manifest_hashes,
        "state_sha256": sha(state_path) if state_path.is_file() else None,
        "gate_sha256": sha(plan_dir / "gate.json") if (plan_dir / "gate.json").is_file() else None,
        "dispatch_ledger_sha256": sha(ledger_path) if ledger_path.is_file() else None,
        "dispatches": ledger_records,
        "dispatch_integrity": dispatch_integrity,
        "import_root": str(import_root),
        "phase_commands": [command_for(str(result["phase"])) for result in results],
        "phase_receipts_manifest_sha256": sha(phase_manifest_path),
        "phase_receipt_sha256": [entry["sha256"] for entry in phase_receipt_entries],
        "privilege_receipt_sha256": [
            record["privilege_receipt_sha256"]
            for record in ledger_records
            if record.get("event") == "terminal"
        ],
        "privilege_receipts_manifest_sha256": sha(privilege_manifest_path),
        "repository_integrity": integrity_checkpoints,
    }
    if infrastructure_status != "passed":
        return 1, unsigned
    return (0 if terminal_state == "finalized" else 2), unsigned


def main() -> int:
    if os.environ.get("MEGAPLAN_ZERO_RECOVERY_CANARY") != "1":
        raise SystemExit("zero-recovery environment flag is required")
    root = Path.cwd().resolve()
    initiative = root / ".megaplan/initiatives/critique-ledger-safe-v3-canary"
    receipt_dir = initiative / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    lock_path = receipt_dir / "single-use-run.lock"
    lock_fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "w", encoding="utf-8") as lock:
        lock.write(PLAN_NAME + "\n")
        lock.flush()
        os.fsync(lock.fileno())

    exit_code = 1
    try:
        exit_code, unsigned = run_locked(root, initiative, receipt_dir)
    except BaseException as exc:
        context_path = receipt_dir / "run-context.json"
        try:
            context = strict_object(context_path) if context_path.is_file() else {}
        except BaseException:
            context = {}
        source_commit = context.get("source_commit") or os.environ.get("ZERO_RECOVERY_SOURCE_COMMIT", "unknown")
        source_tree = context.get("source_tree") or os.environ.get("ZERO_RECOVERY_SOURCE_TREE", "unknown")
        ledger_path = root / ".megaplan/plans" / PLAN_NAME / "zero_recovery_dispatch_ledger.ndjson"
        try:
            emergency_dispatches = read_dispatch_records(ledger_path)
            dispatch_integrity = "partial" if emergency_dispatches else "not_started"
        except BaseException as ledger_exc:
            emergency_dispatches = [{
                "schema": "arnold.megaplan.zero_recovery_dispatch_unreadable.v1",
                "reason": type(ledger_exc).__name__,
            }]
            dispatch_integrity = "unreadable"
        unsigned = {
            "schema": "arnold.megaplan.finite_canary_run_receipt.v3",
            "status": "failed", "canary_id": CANARY_ID, "plan_name": PLAN_NAME,
            "phases": [], "phase_results": [], "terminal_state": "failed",
            "product_outcome": None, "gate_attempts": [],
            "failure": {"phase": "runner", "reason": f"{type(exc).__name__}:{str(exc)[:160]}", "returncode": 1},
            "started_at": now(), "completed_at": now(),
            "source_commit": source_commit, "source_tree": source_tree,
            "canary_spec_sha256": sha(initiative / "canary.yaml") if (initiative / "canary.yaml").is_file() else None,
            "launch_manifest_sha256": context.get("launch_manifest_sha256"),
            "state_sha256": None,
            "gate_sha256": None,
            "dispatch_ledger_sha256": sha(ledger_path) if ledger_path.is_file() else None,
            "dispatches": emergency_dispatches,
            "dispatch_integrity": dispatch_integrity,
            "import_root": context.get("import_root"),
            "phase_commands": [],
            "phase_receipts_manifest_sha256": None,
            "phase_receipt_sha256": [],
            "privilege_receipt_sha256": [],
            "privilege_receipts_manifest_sha256": None,
            "repository_integrity": [],
        }
    unsigned["receipt_digest"] = hashlib.sha256(canonical(unsigned)).hexdigest()
    destination = receipt_dir / f"{unsigned['receipt_digest']}.run-receipt.json"
    write_once(destination, unsigned)
    print(destination.relative_to(root))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
