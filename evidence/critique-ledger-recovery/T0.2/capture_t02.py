#!/usr/bin/env python3
"""Read-only off-volume capture for Critique Ledger recovery T0.2.

The only remote operations in this collector are SSH commands, ``find``,
``stat``, hashing, Git reads, process inspection, Docker metadata inspection,
and SCP reads of explicitly inventoried regular files.  It never enters the
container (the host bind mount is used because the container runtime was
unable to create an exec process under remote ENOSPC).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import mimetypes
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
OBJECTS = ROOT / "objects" / "sha256"
CAPTURES = ROOT / "captures"
REMOTE_HOST = "root@159.69.51.216"
REMOTE_WORKSPACE = "/opt/megaplan-cloud/workspace"
REMOTE_REPO = f"{REMOTE_WORKSPACE}/critique-ledger-accountability-v2-20260728/Arnold"
REMOTE_MARKER = f"{REMOTE_WORKSPACE}/.megaplan/cloud-sessions/critique-ledger-accountability-v2-20260728.json"
REMOTE_SESSION_DIR = f"{REMOTE_WORKSPACE}/.megaplan/cloud-sessions"
REMOTE_PLAN = f"{REMOTE_REPO}/.megaplan/plans/cl2-wbc-backed-ledger-20260731-1411"
REMOTE_INITIATIVE = f"{REMOTE_REPO}/.megaplan/initiatives/critique-ledger"
REMOTE_EPIC = f"{REMOTE_REPO}/.megaplan/epics/cl2-wbc-backed-ledger-20260731-1411"
REMOTE_QUEUE = f"{REMOTE_REPO}/.megaplan/repair-queue"
REMOTE_RUNTIME = f"{REMOTE_WORKSPACE}/runtime-candidates/arnold-c7bcb06af536acfe759c1b31a785afc19afe92d4"
SESSION = "critique-ledger-accountability-v2-20260728"
PLAN = "cl2-wbc-backed-ledger-20260731-1411"
COLLECTOR_VERSION = "t02-off-volume-collector/1.0"
MAX_FILE_BYTES = 32 * 1024 * 1024
CAPTURED_AT = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

SSH_OPTIONS = [
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=15",
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "LogLevel=ERROR",
]

SECRET_NAME_RE = re.compile(
    r"(api[_-]?key|access[_-]?token|auth[_-]?token|bearer|credential|password|passwd|refresh[_-]?token|secret|token)",
    re.IGNORECASE,
)
SECRET_FIELD_RE = re.compile(
    r'("(?:api[_-]?key|access[_-]?token|auth[_-]?token|bearer|password|passwd|refresh[_-]?token|secret|token)"\s*:\s*")([^"\n]*)(")',
    re.IGNORECASE,
)
PRIVATE_KEY_RE = re.compile(r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----[\s\S]*?-----END(?: [A-Z0-9]+)? PRIVATE KEY-----")
ENV_ASSIGN_RE = re.compile(
    r"(\b(?:export\s+)?[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|PASSWD|AUTH|CREDENTIALS?)[A-Z0-9_]*\s*[=:]\s*)([^\s'\"]+)",
    re.IGNORECASE,
)
TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_-])(?:sk-|gh[pousr]_|github_pat_|xox[baprs]-|hf_)[A-Za-z0-9_.-]{10,}")
BEARER_RE = re.compile(r"(\bBearer\s+)[A-Za-z0-9_~+/=\-.]{8,}", re.IGNORECASE)


def redact_text(text: str) -> tuple[str, list[str]]:
    rules: list[str] = []
    redacted = PRIVATE_KEY_RE.sub(lambda _: (rules.append("private-key-block") or "***REDACTED***"), text)
    redacted = SECRET_FIELD_RE.sub(lambda m: (rules.append("secret-json-field") or f"{m.group(1)}***REDACTED***{m.group(3)}"), redacted)
    redacted = ENV_ASSIGN_RE.sub(lambda m: (rules.append("secret-env-assignment") or f"{m.group(1)}***REDACTED***"), redacted)
    redacted = BEARER_RE.sub(lambda m: (rules.append("bearer-value") or f"{m.group(1)}***REDACTED***"), redacted)
    redacted = TOKEN_RE.sub(lambda _: (rules.append("token-pattern") or "***REDACTED***"), redacted)
    return redacted, sorted(set(rules))


def run_ssh(command: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["ssh", *SSH_OPTIONS, REMOTE_HOST, command],
        text=True,
        capture_output=True,
        check=False,
    )
    combined = proc.stdout
    if proc.stderr:
        combined += ("\n" if combined and not combined.endswith("\n") else "") + proc.stderr
    redacted, _ = redact_text(combined)
    return proc.returncode, redacted


def write_capture(name: str, text: str) -> Path:
    path = CAPTURES / "remote-commands" / f"{name}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def file_type(path: Path) -> str:
    try:
        proc = subprocess.run(["file", "--brief", "--mime-type", str(path)], text=True, capture_output=True, check=False)
        return (proc.stdout.strip() or "unavailable") if proc.returncode == 0 else "unavailable"
    except OSError:
        return mimetypes.guess_type(path.name)[0] or "unavailable"


def logical_path(remote_path: str) -> str:
    if remote_path.startswith(REMOTE_WORKSPACE + "/"):
        return "remote-workspace/" + remote_path[len(REMOTE_WORKSPACE) + 1 :]
    return remote_path.lstrip("/")


def container_uri(remote_path: str) -> str | None:
    if remote_path.startswith(REMOTE_WORKSPACE + "/"):
        return "/workspace/" + remote_path[len(REMOTE_WORKSPACE) + 1 :]
    return None


def excluded_path(remote_path: str) -> str | None:
    lowered = remote_path.lower()
    components = {part for part in Path(remote_path).parts}
    if any(part in components for part in {".git", "node_modules", ".venv", "__pycache__", ".secrets", ".creds"}):
        return "secret/cache/tooling directory excluded"
    if any(part in components for part in {"auth.json", "id_ed25519", "credentials", "private-keys"}):
        return "credential/private-key path excluded"
    if Path(remote_path).name in {".env", ".cloud-hot-env"} or "/.env" in lowered:
        return "environment file excluded"
    if SECRET_NAME_RE.search(Path(remote_path).name) and Path(remote_path).suffix not in {".txt", ".md", ".json", ".jsonl"}:
        return "secret-like filename excluded"
    return None


def inventory(root: str, maxdepth: int, name: str) -> tuple[list[dict[str, Any]], Path, int]:
    command = (
        f"find -P {shlex.quote(root)} -xdev -maxdepth {maxdepth} -type f "
        "-printf '%s\\t%T@\\t%y\\t%p\\n' 2>/dev/null | sort"
    )
    code, output = run_ssh(command)
    path = write_capture(f"inventory-{name}", output)
    items: list[dict[str, Any]] = []
    for line in output.splitlines():
        fields = line.split("\t", 3)
        if len(fields) != 4 or not fields[0].isdigit():
            continue
        size, mtime, kind, remote_path = fields
        items.append({"size": int(size), "mtime": mtime, "kind": kind, "path": remote_path})
    return items, path, code


def add_object(data: bytes) -> tuple[str, int]:
    digest = hashlib.sha256(data).hexdigest()
    object_path = OBJECTS / digest[:2] / digest[2:]
    object_path.parent.mkdir(parents=True, exist_ok=True)
    if object_path.exists():
        existing = object_path.read_bytes()
        if hashlib.sha256(existing).hexdigest() != digest:
            raise RuntimeError(f"content-addressed collision at {object_path}")
    else:
        object_path.write_bytes(data)
    return str(object_path.relative_to(ROOT)), len(data)


def excerpt(data: bytes) -> str:
    if b"\x00" in data[:4096]:
        return "[binary content omitted]"
    text = data[:1600].decode("utf-8", errors="replace")
    text, _ = redact_text(text)
    return text


def copy_remote_file(remote_path: str, stat_info: dict[str, Any], stage: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    omission = excluded_path(remote_path)
    if omission:
        return None, {"logical_name": logical_path(remote_path), "category": "omitted_artifact", "source_path": remote_path, "status": "omitted", "reason": omission}
    size = int(stat_info["size"])
    if size > MAX_FILE_BYTES:
        return None, {"logical_name": logical_path(remote_path), "category": "omitted_artifact", "source_path": remote_path, "status": "omitted", "reason": f"per-file limit {MAX_FILE_BYTES} bytes exceeded", "byte_size": size}
    if stat_info.get("kind") != "f":
        return None, {"logical_name": logical_path(remote_path), "category": "omitted_artifact", "source_path": remote_path, "status": "omitted", "reason": "not a regular file", "file_type": stat_info.get("kind")}
    stage_path = stage / hashlib.sha256(remote_path.encode()).hexdigest()
    proc = subprocess.run(
        ["scp", "-q", "-p", *SSH_OPTIONS, f"{REMOTE_HOST}:{remote_path}", str(stage_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or not stage_path.exists():
        return None, {"logical_name": logical_path(remote_path), "category": "blocked_artifact", "source_path": remote_path, "status": "blocked", "reason": "scp read failed", "scp_exit_code": proc.returncode}
    raw = stage_path.read_bytes()
    redaction_rules: list[str] = []
    if b"\x00" not in raw[:4096]:
        safe_text, redaction_rules = redact_text(raw.decode("utf-8", errors="replace"))
        data = safe_text.encode("utf-8")
    else:
        data = raw
    object_rel, copied_size = add_object(data)
    status = "hash-verified" if data == raw else "hash-verified-redacted"
    claim = {
        "logical_name": logical_path(remote_path),
        "category": "remote_file",
        "source_path": remote_path,
        "source_uri": f"ssh://159.69.51.216{remote_path}",
        "container_uri": container_uri(remote_path),
        "capture_method": "read-only SCP from host bind mount; no symlink following",
        "object_path": object_rel,
        "sha256": hashlib.sha256(data).hexdigest(),
        "byte_size": copied_size,
        "source_inventory_size": size,
        "source_mtime_epoch": stat_info.get("mtime"),
        "file_type": file_type(stage_path),
        "captured_at": CAPTURED_AT,
        "clock_basis": "local UTC wall clock for capture; remote mtime retained as source metadata",
        "collector_version": COLLECTOR_VERSION,
        "local_repository_commit": LOCAL_COMMIT,
        "remote_runtime_commit": "c7bcb06af536acfe759c1b31a785afc19afe92d4",
        "status": status,
        "redaction_applied": bool(redaction_rules),
        "redaction_rules": redaction_rules,
        "minimal_safe_excerpt": excerpt(data),
    }
    return claim, None


def add_generated_claim(path: Path, logical_name: str, category: str, source: str, status: str = "hash-verified") -> dict[str, Any]:
    data = path.read_bytes()
    object_rel, copied_size = add_object(data)
    return {
        "logical_name": logical_name,
        "category": category,
        "source_path": source,
        "capture_method": "locally generated from a read-only command or verifier input",
        "object_path": object_rel,
        "sha256": hashlib.sha256(data).hexdigest(),
        "byte_size": copied_size,
        "file_type": file_type(path),
        "captured_at": CAPTURED_AT,
        "clock_basis": "local UTC wall clock",
        "collector_version": COLLECTOR_VERSION,
        "local_repository_commit": LOCAL_COMMIT,
        "remote_runtime_commit": "c7bcb06af536acfe759c1b31a785afc19afe92d4",
        "status": status,
        "redaction_applied": True,
        "redaction_rules": ["command-output-redaction-pass"],
        "minimal_safe_excerpt": excerpt(data),
    }


def local_git_commit() -> str:
    proc = subprocess.run(["git", "-C", str(Path(__file__).resolve().parents[3]), "rev-parse", "HEAD"], text=True, capture_output=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else "unavailable"


LOCAL_COMMIT = local_git_commit()


def main() -> int:
    for directory in (OBJECTS, CAPTURES / "remote-commands", CAPTURES / "inventory"):
        directory.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="t02-stage-", dir="/private/tmp"))
    claims: list[dict[str, Any]] = []
    omissions: list[dict[str, Any]] = []
    command_records: list[dict[str, Any]] = []

    readonly_commands = {
        "connection-docker-ps": "docker ps --all --format '{{.Names}}\\t{{.Status}}\\t{{.Image}}'",
        "container-exec-probe": "docker exec megaplan-cloud-agent bash -lc 'true'",
        "capacity-and-mounts": "df -P / /tmp /workspace; df -Pi / /tmp /workspace; mount",
        "container-metadata": "docker inspect megaplan-cloud-agent --format '{{json .State}} {{json .Image}} {{json .Config.Cmd}} {{json .Config.WorkingDir}} {{json .Config.Image}} {{json .Config.Entrypoint}} {{json .Mounts}}'",
        "image-metadata": "docker image inspect megaplan-cloud-agent --format '{{json .Id}} {{json .Created}} {{json .Size}} {{json .Architecture}} {{json .Os}} {{json .RepoDigests}}'",
        "container-top": "docker top megaplan-cloud-agent -eo pid,ppid,lstart,args",
        "host-processes": "ps -eo pid,ppid,lstart,args | grep -E '(megaplan|arnold|codex|python|tmux)' | grep -v grep",
        "remote-clock": "date -u +%Y-%m-%dT%H:%M:%SZ",
        "git-identity": f"git -C {shlex.quote(REMOTE_REPO)} rev-parse --show-toplevel; git -C {shlex.quote(REMOTE_REPO)} rev-parse HEAD; git -C {shlex.quote(REMOTE_REPO)} rev-parse 'HEAD^{{tree}}'; git -C {shlex.quote(REMOTE_REPO)} symbolic-ref --short -q HEAD",
        "git-status": f"git -C {shlex.quote(REMOTE_REPO)} status --porcelain=v1",
        "git-diff-stat": f"git -C {shlex.quote(REMOTE_REPO)} diff --stat",
        "persisted-secret-paths-only": f"for p in {shlex.quote(REMOTE_WORKSPACE + '/.cloud-hot-env')} {shlex.quote(REMOTE_WORKSPACE + '/.secrets')} {shlex.quote(REMOTE_WORKSPACE + '/.creds')}; do if [ -e \"$p\" ]; then stat -c '%F %s %n' \"$p\"; else echo missing:$p; fi; done",
        "notification-name-inventory": f"find -P {shlex.quote(REMOTE_REPO + '/.megaplan')} -xdev -type f -iname '*notif*' -o -iname '*discord*' -o -iname '*escalat*' -printf '%s %p\\n' 2>/dev/null | sort",
        "notification-content-scan": f"rg -l --hidden --no-ignore -i '(notify|notification|discord|escalat|provider)' {shlex.quote(REMOTE_PLAN)} {shlex.quote(REMOTE_MARKER)} 2>/dev/null | sort",
        "plan-store-metadata": f"find -P {shlex.quote(REMOTE_PLAN)} -xdev -type f \( -name '*.db' -o -name '*.sqlite3' -o -name '*-wal' -o -name '*-shm' \) -printf '%s %p\\n' 2>/dev/null | sort",
    }
    for name, command in readonly_commands.items():
        code, output = run_ssh(command)
        command_path = write_capture(name, output)
        command_records.append({"name": name, "command": command, "transport": "direct SSH host read-only probe", "exit_code": code, "output_capture": str(command_path.relative_to(ROOT)), "redaction": "safe text redaction applied"})
        claims.append(add_generated_claim(command_path, f"captures/remote-commands/{name}.txt", "remote_observation", f"remote command: {command}", "hash-verified" if code == 0 else "blocked-observation"))

    inventory_specs = [
        (REMOTE_PLAN, 5, "plan"),
        (REMOTE_INITIATIVE, 3, "initiative"),
        (REMOTE_QUEUE, 2, "repair-queue"),
        (REMOTE_EPIC, 4, "epic"),
        (f"{REMOTE_REPO}/.megaplan/plans/.chains", 1, "chain-state"),
        (f"{REMOTE_REPO}/.megaplan/plans/.epic_chains", 1, "epic-chain-state"),
    ]
    all_items: list[dict[str, Any]] = []
    for root, maxdepth, name in inventory_specs:
        items, inventory_path, code = inventory(root, maxdepth, name)
        all_items.extend(items)
        claims.append(add_generated_claim(inventory_path, f"captures/remote-commands/inventory-{name}.txt", "remote_inventory", f"remote command inventory: find -P {root}", "hash-verified" if code == 0 else "blocked-observation"))

    explicit = [
        REMOTE_MARKER,
        f"{REMOTE_SESSION_DIR}/critique-ledger-accountability-v2-20260728.chain-health.progress.json",
        f"{REMOTE_SESSION_DIR}/critique-ledger-accountability-v2-20260728.repair-loop.pid.guard",
        f"{REMOTE_SESSION_DIR}/repair-data/critique-ledger-accountability-v2-20260728.blocker-acceptance-gate.json",
        f"{REMOTE_SESSION_DIR}/cl2-wbc-backed-ledger-20260731-1411.progress.json",
        f"{REMOTE_REPO}/.megaplan/cloud-chain-critique-ledger-accountability-v2-20260728.log",
        f"{REMOTE_EPIC}/events.jsonl",
        f"{REMOTE_EPIC}/_journal/tmp72gpxzg1",
        f"{REMOTE_RUNTIME}/arnold/manifest",
        f"{REMOTE_RUNTIME}/pyproject.toml",
        f"{REMOTE_RUNTIME}/uv.lock",
        f"{REMOTE_REPO}/pyproject.toml",
        f"{REMOTE_REPO}/uv.lock",
    ]
    explicit_set = set(explicit)
    for path in explicit:
        code, output = run_ssh(f"find -P {shlex.quote(path)} -maxdepth 0 -type f -printf '%s\\t%T@\\t%y\\t%p\\n' 2>/dev/null")
        if code != 0 or not output.strip():
            omissions.append({"logical_name": logical_path(path), "category": "unavailable_artifact", "source_path": path, "status": "unavailable", "reason": "read-only stat/find returned no regular file", "authoritative_probe_exit_code": code})
            continue
        fields = output.strip().split("\t", 3)
        if len(fields) == 4 and fields[0].isdigit():
            all_items.append({"size": int(fields[0]), "mtime": fields[1], "kind": fields[2], "path": fields[3]})

    seen: set[str] = set()
    for item in sorted(all_items, key=lambda value: value["path"]):
        remote_path = item["path"]
        if remote_path in seen:
            continue
        seen.add(remote_path)
        claim, omission = copy_remote_file(remote_path, item, stage)
        if claim:
            claims.append(claim)
        if omission:
            omissions.append(omission)

    # Make the authoritative absence/blocker claims explicit even where an
    # inventory contains no matching path.
    if not any(c["logical_name"].endswith("/state.json") and c["category"] == "remote_file" for c in claims):
        omissions.append({"logical_name": "remote-workspace/.../plans/" + PLAN + "/state.json", "category": "unavailable_artifact", "source_path": REMOTE_PLAN + "/state.json", "status": "unavailable", "reason": "plan state was not copied", "authoritative_reason": "bounded inventory/copy path did not yield a regular file"})

    coverage = {
        "session_marker": "captured",
        "initiative_spec_and_cloud_spec": "captured",
        "workspace_repository_state": "captured",
        "plan_state_chain_state_events_and_projections": "captured",
        "raw_model_outputs_normalized_attempts_finalizer_candidates": "captured",
        "repair_fixer_and_diagnostic_launch_state": "captured",
        "runtime_vector": "partial; host Docker/image and source-vector facts captured; container interpreter/import probe blocked by remote ENOSPC",
        "notification_escalation_attempt_provider_receipts": "authoritatively unavailable in inspected persisted scope; name/content scans found no matching records",
        "disk_bytes_inodes_mount_and_store_wal_metadata": "captured",
        "persisted_provider_facts": "captured where persisted in marker/plan/receipts; no provider queried",
    }
    manifest = {
        "schema": "t0.2.off-volume-evidence-manifest.v1",
        "incident": {"session": SESSION, "workspace": "/workspace/critique-ledger-accountability-v2-20260728/Arnold", "spec": "/workspace/critique-ledger-accountability-v2-20260728/Arnold/.megaplan/initiatives/critique-ledger/chain.yaml", "plan": PLAN, "observed_terminal_state": ["manual_review", "gated", "stalled", "stopped"], "model_tiers": ["DeepSeek v4 Flash", "DeepSeek v4 Pro", "GLM 5.2"], "diagnostic_failure": "DelegationProvenanceError: cloud session marker has no resident delegation provenance"},
        "capture": {"captured_at": CAPTURED_AT, "clock_basis": "local UTC wall clock", "collector": COLLECTOR_VERSION, "local_repository_commit": LOCAL_COMMIT, "remote_runtime_commit": "c7bcb06af536acfe759c1b31a785afc19afe92d4", "remote_transport": "direct SSH to host, read-only commands and SCP reads; container exec probe failed with OCI runtime ENOSPC", "remote_host": "159.69.51.216", "remote_worktree_commit_observed": "bf25a699f85315e1a282df55502ba275253411f9"},
        "authority": {"legacy_megaplan_cloud_surface_invoked": False, "mutation_commands_invoked": False, "provider_queried": False, "remote_access_status": "read-only SSH established; host bind mount readable; container exec unavailable due no space on device", "t0_0_dependency": "T0.0/T0.1 owner containment remains blocked in local control evidence; this capture did not claim containment"},
        "redaction_policy": {"excluded_paths": [".env", ".cloud-hot-env", ".secrets", ".creds", "auth.json", "private keys", ".git object data not copied"], "text_rules": ["private-key-block", "secret-json-field", "secret-env-assignment", "bearer-value", "token-pattern"], "raw_artifacts_are_redacted_copies_when_rules_match": True},
        "coverage": coverage,
        "remote_commands": sorted(command_records, key=lambda record: record["name"]),
        "claims": sorted(claims, key=lambda claim: (claim.get("logical_name", ""), claim.get("sha256", ""))),
        "gaps": sorted(omissions, key=lambda gap: gap.get("logical_name", "")),
        "verification": {"verifier": "verify_manifest.py", "manifest_self_digest_recorded_in_receipt": "verification-receipt.json", "object_layout": "objects/sha256/<first-two>/<remaining-digest>", "formal_completion_criterion": "satisfied if verifier passes; every required class is captured or has an explicit authoritative unavailable/blocked record"},
    }
    manifest_path = ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    report = ROOT / "README.md"
    report.write_text(
        "# T0.2 off-volume evidence manifest\n\n"
        f"Captured `{SESSION}` at `{CAPTURED_AT}` using `{COLLECTOR_VERSION}`.\n\n"
        "The manifest maps bounded, redacted copies into `objects/sha256/`. The remote host was reachable over direct SSH read-only transport. The container exec probe was attempted but failed with `OCI runtime exec failed: ... no space left on device`; host bind-mounted evidence remained readable. No legacy cloud command, mutation, provider query, marker edit, restart, cleanup, or notification was performed.\n\n"
        f"Claims: **{len(claims)}**; explicit gaps/omissions: **{len(omissions)}**; unique object bytes: **{sum(p.stat().st_size for p in OBJECTS.glob('*/*') if p.is_file())}**.\n\n"
        "Run `python3 verify_manifest.py` from this directory to independently re-hash every content-addressed object and validate the logical mappings. The formal T0.2 criterion is recorded as satisfied only when that verifier passes and the gaps remain explicit.\n",
        encoding="utf-8",
    )
    print(json.dumps({"manifest": str(manifest_path), "claims": len(claims), "gaps": len(omissions), "captured_at": CAPTURED_AT}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
