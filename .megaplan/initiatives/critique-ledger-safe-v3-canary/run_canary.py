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

PHASES = ("init", "plan", "critique", "gate", "finalize")
MODEL_PHASES = PHASES[1:]
STATES = ("initialized", "planned", "critiqued", "gated", "finalized")
CANARY_ID = "critique-ledger-safe-v3-canary"
PLAN_NAME = "critique-ledger-cl2-planning-canary"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def read_dispatch_ledger(path: Path, expected: tuple[str, ...]) -> list[dict[str, Any]]:
    records = read_dispatch_records(path)
    if not expected:
        if records:
            raise ValueError("init unexpectedly dispatched a model")
        return []
    if len(records) != 2 * len(expected):
        raise ValueError("dispatch ledger does not contain one start/terminal pair per phase")
    for index, phase in enumerate(expected):
        start, terminal = records[index * 2 : index * 2 + 2]
        if (
            start.get("schema") != "arnold.megaplan.zero_recovery_dispatch.v1"
            or terminal.get("schema") != "arnold.megaplan.zero_recovery_dispatch.v1"
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
            or terminal.get("model_evidence") != "rollout_turn_context"
            or start.get("selected_effort") != "high"
            or start.get("model_cli_argv") != ["-c", "model='gpt-5.6-sol'"]
            or terminal.get("actual_effort") != "high"
            or start.get("attempt") != 1
            or terminal.get("attempt") != 1
            or terminal.get("result") != "returned"
            or any(item.get(key) is not False for item in (start, terminal) for key in ("retry", "fallback", "json_repair", "adaptive_routing"))
        ):
            raise ValueError("dispatch ledger contains retry, fallback, repair, or model drift")
    return records


def phase_receipt(
    receipt_dir: Path,
    index: int,
    phase: str,
    *,
    status: str,
    returncode: int,
    state: str | None,
    reason: str | None,
    argv: list[str],
    state_path: Path,
    ledger_path: Path,
) -> None:
    payload: dict[str, object] = {
        "schema": "arnold.megaplan.finite_canary_phase_receipt.v2",
        "phase": phase,
        "status": status,
        "returncode": returncode,
        "state": state,
        "reason": reason,
        "argv": argv,
        "state_sha256": sha(state_path) if state_path.is_file() else None,
        "dispatch_ledger_sha256": sha(ledger_path) if ledger_path.is_file() else None,
        "completed_at": now(),
    }
    write_once(receipt_dir / f"{index:02d}-{phase}.phase-receipt.json", payload)


def run_locked(root: Path, initiative: Path, receipt_dir: Path) -> tuple[int, dict[str, object]]:
    plan_dir = root / ".megaplan/plans" / PLAN_NAME
    if plan_dir.exists():
        raise RuntimeError("finite canary plan identity already exists")
    idea = initiative / "briefs/cl2-ledger-persistence-and-replay.md"
    north_star = initiative / "NORTHSTAR.md"
    commands = [
        [sys.executable, "-P", "-m", "arnold_pipelines.megaplan", "init", "--project-dir", str(root), "--name", PLAN_NAME, "--auto-approve", "--idea-file", str(idea), "--north-star", str(north_star), "--robustness", "full", "--no-adaptive-critique", "--vendor", "codex", "--phase-model", "plan=codex:gpt-5.6-sol:high", "--phase-model", "critique=codex:gpt-5.6-sol:high", "--phase-model", "gate=codex:gpt-5.6-sol:high", "--phase-model", "finalize=codex:gpt-5.6-sol:high"],
        *[[sys.executable, "-P", "-m", "arnold_pipelines.megaplan", phase, "--plan", PLAN_NAME, "--fresh"] for phase in MODEL_PHASES],
    ]
    allowed_environment = (
        "PATH", "LANG", "LC_ALL", "LC_CTYPE", "SSL_CERT_FILE", "SSL_CERT_DIR",
        "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    )
    child_env = {key: os.environ[key] for key in allowed_environment if key in os.environ}
    child_env.update({
        "MEGAPLAN_ZERO_RECOVERY_CANARY": "1",
        "MEGAPLAN_TRUSTED_CONTAINER": "1",
        "PYTHONNOUSERSITE": "1",
        "HOME": "/root",
        "PYTHONPATH": str(root),
    })
    import arnold_pipelines.megaplan as megaplan
    import_root = Path(megaplan.__file__).resolve()
    if root not in import_root.parents:
        raise RuntimeError("megaplan import escaped admitted checkout")
    source_commit = git_object(root, "HEAD")
    source_tree = git_object(root, "HEAD^{tree}")
    if source_commit != os.environ.get("ZERO_RECOVERY_SOURCE_COMMIT") or source_tree != os.environ.get("ZERO_RECOVERY_SOURCE_TREE"):
        raise RuntimeError("runner source identity differs from host admission")
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
        "schema": "arnold.megaplan.finite_canary_run_context.v1",
        "source_commit": source_commit,
        "source_tree": source_tree,
        "import_root": str(import_root),
        "phase_commands": commands,
        "launch_manifest_sha256": actual_manifest_hashes,
        "recorded_at": now(),
    })

    started_at = now()
    results: list[dict[str, object]] = []
    failure: dict[str, object] | None = None
    status = "passed"
    ledger_path = plan_dir / "zero_recovery_dispatch_ledger.ndjson"
    for index, (phase, expected_state, argv) in enumerate(zip(PHASES, STATES, commands, strict=True)):
        write_once(receipt_dir / f"{index:02d}-{phase}.started.json", {
            "schema": "arnold.megaplan.finite_canary_phase_checkpoint.v1",
            "phase": phase, "argv": argv, "started_at": now(), "import_root": str(import_root),
        })
        try:
            completed = subprocess.run(
                argv, cwd=root, env=child_env, text=True, capture_output=True,
                check=False, timeout=3600,
            )
            returncode = completed.returncode
            if completed.returncode != 0:
                raise RuntimeError(f"nonzero_returncode:{returncode}")
            state_path = plan_dir / "state.json"
            state = strict_object(state_path)
            current_state = state.get("current_state")
            if current_state != expected_state or state.get("active_step") not in (None, ""):
                raise RuntimeError("unexpected_or_active_state")
            if phase == "gate" and strict_object(plan_dir / "gate.json").get("recommendation") != "PROCEED":
                raise RuntimeError("gate_not_proceed")
            read_dispatch_ledger(ledger_path, MODEL_PHASES[:index])
            results.append({"phase": phase, "returncode": 0, "state": current_state})
            phase_receipt(receipt_dir, index, phase, status="passed", returncode=0,
                          state=str(current_state), reason=None, argv=argv,
                          state_path=state_path, ledger_path=ledger_path)
        except subprocess.TimeoutExpired:
            returncode = 124
            reason = "timeout"
        except BaseException as exc:
            returncode = locals().get("returncode", 1)
            reason = f"{type(exc).__name__}:{str(exc)[:160]}"
        else:
            continue
        status = "failed"
        failure = {"phase": phase, "reason": reason, "returncode": returncode}
        state_path = plan_dir / "state.json"
        current_state = None
        if state_path.is_file():
            try:
                current_state = strict_object(state_path).get("current_state")
            except BaseException:
                pass
        results.append({"phase": phase, "returncode": returncode, "state": current_state})
        phase_receipt(receipt_dir, index, phase, status="failed", returncode=returncode,
                      state=str(current_state) if current_state is not None else None,
                      reason=reason, argv=argv, state_path=state_path, ledger_path=ledger_path)
        break

    state_path = plan_dir / "state.json"
    ledger_records = (
        read_dispatch_ledger(ledger_path, MODEL_PHASES)
        if status == "passed"
        else read_dispatch_records(ledger_path)
    )
    dispatch_integrity = (
        "complete"
        if status == "passed"
        else "partial"
        if ledger_records
        else "not_started"
    )
    phase_receipt_entries = [
        {
            "phase": phase,
            "path": str(
                (receipt_dir / f"{index:02d}-{phase}.phase-receipt.json").relative_to(root)
            ),
            "sha256": sha(receipt_dir / f"{index:02d}-{phase}.phase-receipt.json"),
        }
        for index, phase in enumerate(PHASES[:len(results)])
    ]
    phase_manifest = {
        "schema": "arnold.megaplan.finite_canary_phase_receipts_manifest.v1",
        "canary_id": CANARY_ID,
        "plan_name": PLAN_NAME,
        "entries": phase_receipt_entries,
    }
    phase_manifest_path = receipt_dir / "phase-receipts-manifest.json"
    write_once(phase_manifest_path, phase_manifest)
    unsigned: dict[str, object] = {
        "schema": "arnold.megaplan.finite_canary_run_receipt.v2",
        "status": status,
        "canary_id": CANARY_ID,
        "plan_name": PLAN_NAME,
        "phases": list(PHASES),
        "phase_results": results,
        "terminal_state": "finalized" if status == "passed" else "failed",
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
        "phase_commands": commands,
        "phase_receipts_manifest_sha256": sha(phase_manifest_path),
        "phase_receipt_sha256": [entry["sha256"] for entry in phase_receipt_entries],
    }
    return (0 if status == "passed" else 1), unsigned


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
            "schema": "arnold.megaplan.finite_canary_run_receipt.v2",
            "status": "failed", "canary_id": CANARY_ID, "plan_name": PLAN_NAME,
            "phases": list(PHASES), "phase_results": [], "terminal_state": "failed",
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
            "phase_commands": context.get("phase_commands", []),
            "phase_receipts_manifest_sha256": None,
            "phase_receipt_sha256": [],
        }
    unsigned["receipt_digest"] = hashlib.sha256(canonical(unsigned)).hexdigest()
    destination = receipt_dir / f"{unsigned['receipt_digest']}.run-receipt.json"
    write_once(destination, unsigned)
    print(destination.relative_to(root))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
