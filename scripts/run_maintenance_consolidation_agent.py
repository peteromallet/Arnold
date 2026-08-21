#!/usr/bin/env python3
"""Dispatch one maintenance-consolidation agent with an auditable receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass
from typing import Any

INTEGRATION_WORKTREE = Path(__file__).resolve().parents[1]
LAUNCHERS = {
    "gpt-5.6-luna": (INTEGRATION_WORKTREE / "arnold_pipelines/megaplan/skills/subagent-launcher/launch_hermes_agent.py", "codex:gpt-5.6-luna"),
    "gpt-5.6-sol": (INTEGRATION_WORKTREE / "arnold_pipelines/megaplan/skills/subagent-launcher/launch_hermes_agent.py", "codex:gpt-5.6-sol"),
    "grok-4.6": (INTEGRATION_WORKTREE / "arnold_pipelines/megaplan/skills/subagent-launcher/launch_omp_agent.py", "grok-4.6"),
}
ROUTES = {
    "XHARD": "grok-4.6", "XHARD-REVIEW": "grok-4.6", "XHARD-REVISION": "grok-4.6", "JUDGMENT": "grok-4.6",
    "HARD": "gpt-5.6-luna", "HARD-REVIEW": "gpt-5.6-luna", "HARD-REVISION": "gpt-5.6-luna",
    "BRIEF": "gpt-5.6-luna", "WORKSPACE": "gpt-5.6-luna", "INTEGRATION": "gpt-5.6-luna",
    "VALIDATION": "gpt-5.6-luna", "REPORT": "gpt-5.6-luna", "SOL-REVIEW": "gpt-5.6-sol",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    temporary.write_bytes(canonical_json(value) + b"\n")
    os.replace(temporary, path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_role(role: str) -> str:
    return role.strip().strip("[]").upper()


def route_for_role(role: str) -> str:
    normalized = normalize_role(role)
    if normalized not in ROUTES:
        raise ValueError(f"UNCLASSIFIED_ROLE:{role}")
    return ROUTES[normalized]


def _assert_disposable_root(root: Path, project: Path) -> None:
    root = root.resolve(strict=False)
    project = project.resolve(strict=False)
    if root == project or project in root.parents:
        raise ValueError("EVIDENCE_ROOT_PROJECT_OVERLAP:evidence root must be outside project directory")
    for env_name in ("MRC_CANDIDATE_ROOT", "MRC_LIVE_RUNTIME_ROOT", "ARNOLD_RUNTIME_ROOT"):
        configured = os.environ.get(env_name)
        if configured:
            forbidden = Path(configured).expanduser().resolve(strict=False)
            if root == forbidden or forbidden in root.parents or root in forbidden.parents:
                raise ValueError(f"EVIDENCE_ROOT_FORBIDDEN:{env_name}")


def allowance_paths(record: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for category in ("production_files", "tests", "fixtures", "exports", "helpers", "generated_surfaces"):
        value = record.get(category, [])
        if not isinstance(value, list):
            raise ValueError(f"MALFORMED_ALLOWANCE:{category} must be a list")
        paths.extend(str(item) for item in value)
    return sorted(set(paths))


def canonical_allowance(value: Any) -> tuple[dict[str, Any], str]:
    if not isinstance(value, dict):
        raise ValueError("MALFORMED_ALLOWANCE:object required")
    record = dict(value)
    if "paths" in record and not any(category in record for category in ("production_files", "tests", "fixtures", "exports", "helpers", "generated_surfaces")):
        record["production_files"] = list(record.pop("paths"))
    for category in ("production_files", "tests", "fixtures", "exports", "helpers", "generated_surfaces"):
        record.setdefault(category, [])
    record.setdefault("lifecycle_state", "active")
    record.setdefault("active", True)
    content = {category: record[category] for category in ("production_files", "tests", "fixtures", "exports", "helpers", "generated_surfaces")}
    content.update({"lifecycle_state": record["lifecycle_state"], "active": record["active"]})
    return record, digest_bytes(canonical_json(content))


def _overlaps(left: str, right: str) -> bool:
    left = str(Path(left))
    right = str(Path(right))
    return left == right or left.startswith(right.rstrip("/") + "/") or right.startswith(left.rstrip("/") + "/")


def reject_allowance_overlap(allowance_file: Path, evidence_dir: Path, project_dir: Path) -> tuple[dict[str, Any], str]:
    record, digest = canonical_allowance(json.loads(allowance_file.read_text(encoding="utf-8")))
    current_paths = allowance_paths(record)
    registry_candidates = [evidence_dir / "manifest.json", project_dir / "docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json"]
    for registry_path in registry_candidates:
        if not registry_path.is_file():
            continue
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for existing in registry.get("allowances", []):
            if not isinstance(existing, dict) or not existing.get("active"):
                continue
            for old_path in allowance_paths(existing):
                if any(_overlaps(new_path, old_path) for new_path in current_paths):
                    raise ValueError(f"OVERLAPPING_ALLOWANCE:{existing.get('allowance_id', 'unknown')}")
    return record, digest


def _resolved_model(stdout: bytes, stderr: bytes = b"") -> str | None:
    text = b"\n".join((stdout, stderr)).decode("utf-8", errors="replace")
    patterns = (r"resolved(?:[_ -]?model)?\s*[:=]\s*[\"']?([^\"'\s,}]+)", r"model\s*[:=]\s*[\"']?([^\"'\s,}]+)")
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _process_identity(process: subprocess.Popen[bytes], started: str) -> dict[str, Any] | str:
    pid = getattr(process, "pid", None)
    if isinstance(pid, int) and pid > 0:
        return {"pid": pid, "started_at": started, "source": "wrapper-observed"}
    return "unknown"


def _build_command(model_route: str, query_file: Path, project_dir: Path, timeout: int) -> list[str]:
    launcher, launcher_model = LAUNCHERS[model_route]
    return [
        sys.executable,
        str(launcher),
        f"--model={launcher_model}",
        f"--query-file={query_file}",
        f"--project-dir={project_dir}",
        f"--timeout={timeout}",
    ]


def _registry_path(project_dir: Path, evidence_dir: Path | None) -> Path:
    if evidence_dir is not None:
        evidence_registry = evidence_dir / "manifest.json"
        if evidence_registry.is_file():
            return evidence_registry
    project_registry = project_dir / "docs/arnold/maintenance-runtime-consolidation-evidence/manifest.json"
    if project_registry.is_file():
        return project_registry
    locations = [str(evidence_dir / "manifest.json")] if evidence_dir is not None else []
    locations.append(str(project_registry))
    raise ValueError(f"MISSING_ALLOWANCE_REGISTRY:{' or '.join(locations)}")


_JSON_WHITESPACE = b" \t\r\n"


@dataclass(frozen=True)
class _JsonMember:
    key: str
    value: "_JsonNode"


@dataclass(frozen=True)
class _JsonNode:
    start: int
    end: int
    kind: str
    members: tuple[_JsonMember, ...] = ()
    elements: tuple["_JsonNode", ...] = ()


def _skip_json_whitespace(source: bytes, position: int) -> int:
    while position < len(source) and source[position] in _JSON_WHITESPACE:
        position += 1
    return position


def _scan_json_string(source: bytes, position: int) -> int:
    if position >= len(source) or source[position] != ord('"'):
        raise ValueError("MALFORMED_ALLOWANCE_REGISTRY:expected JSON string")
    position += 1
    while position < len(source):
        if source[position] == ord("\\"):
            position += 2
        elif source[position] == ord('"'):
            return position + 1
        else:
            position += 1
    raise ValueError("MALFORMED_ALLOWANCE_REGISTRY:unterminated JSON string")


def _scan_json_value(source: bytes, position: int) -> _JsonNode:
    position = _skip_json_whitespace(source, position)
    if position >= len(source):
        raise ValueError("MALFORMED_ALLOWANCE_REGISTRY:missing JSON value")
    start = position
    marker = source[position]
    if marker == ord('"'):
        return _JsonNode(start, _scan_json_string(source, position), "scalar")
    if marker == ord("{"):
        members: list[_JsonMember] = []
        position += 1
        while True:
            position = _skip_json_whitespace(source, position)
            if position >= len(source):
                raise ValueError("MALFORMED_ALLOWANCE_REGISTRY:unterminated JSON object")
            if source[position] == ord("}"):
                return _JsonNode(start, position + 1, "object", tuple(members))
            key_start = position
            key_end = _scan_json_string(source, key_start)
            key = json.loads(source[key_start:key_end])
            position = _skip_json_whitespace(source, key_end)
            if position >= len(source) or source[position] != ord(":"):
                raise ValueError("MALFORMED_ALLOWANCE_REGISTRY:expected JSON object separator")
            value = _scan_json_value(source, position + 1)
            members.append(_JsonMember(key, value))
            position = _skip_json_whitespace(source, value.end)
            if position < len(source) and source[position] == ord(","):
                position += 1
                continue
            if position < len(source) and source[position] == ord("}"):
                return _JsonNode(start, position + 1, "object", tuple(members))
            raise ValueError("MALFORMED_ALLOWANCE_REGISTRY:expected JSON object delimiter")
    if marker == ord("["):
        elements: list[_JsonNode] = []
        position += 1
        while True:
            position = _skip_json_whitespace(source, position)
            if position >= len(source):
                raise ValueError("MALFORMED_ALLOWANCE_REGISTRY:unterminated JSON array")
            if source[position] == ord("]"):
                return _JsonNode(start, position + 1, "array", elements=tuple(elements))
            value = _scan_json_value(source, position)
            elements.append(value)
            position = _skip_json_whitespace(source, value.end)
            if position < len(source) and source[position] == ord(","):
                position += 1
                continue
            if position < len(source) and source[position] == ord("]"):
                return _JsonNode(start, position + 1, "array", elements=tuple(elements))
            raise ValueError("MALFORMED_ALLOWANCE_REGISTRY:expected JSON array delimiter")
    position += 1
    while position < len(source) and source[position] not in _JSON_WHITESPACE + b",]}":
        position += 1
    if position == start + 1 and marker in b",]}":
        raise ValueError("MALFORMED_ALLOWANCE_REGISTRY:missing JSON value")
    return _JsonNode(start, position, "scalar")


def _scan_json_document(source: bytes) -> _JsonNode:
    position = 3 if source.startswith(b"\xef\xbb\xbf") else 0
    node = _scan_json_value(source, position)
    if _skip_json_whitespace(source, node.end) != len(source):
        raise ValueError("MALFORMED_ALLOWANCE_REGISTRY:trailing JSON content")
    return node


def _last_json_member(node: _JsonNode, key: str) -> _JsonMember | None:
    return next((member for member in reversed(node.members) if member.key == key), None)


def _lossless_manifest_update(
    source: bytes,
    target_index: int,
    closed_at_utc: str,
    allowance_digest: str,
) -> bytes:
    root = _scan_json_document(source)
    allowances_member = _last_json_member(root, "allowances")
    if allowances_member is None or allowances_member.value.kind != "array":
        raise ValueError("MALFORMED_ALLOWANCE_REGISTRY:allowances must be a list")
    try:
        target = allowances_member.value.elements[target_index]
    except IndexError as exc:
        raise ValueError("MALFORMED_ALLOWANCE_REGISTRY:allowance index out of range") from exc
    if target.kind != "object":
        raise ValueError("MALFORMED_ALLOWANCE:object required")

    values = {
        "active": b"false",
        "lifecycle_state": b'"closed"',
        "closed_at_utc": json.dumps(closed_at_utc, separators=(",", ":")).encode("utf-8"),
        "allowance_digest": json.dumps(allowance_digest, separators=(",", ":")).encode("utf-8"),
    }
    replacements: list[tuple[int, int, bytes]] = []
    missing: list[bytes] = []
    for key, value in values.items():
        member = _last_json_member(target, key)
        if member is None:
            missing.append(f'"{key}":'.encode("utf-8") + value)
        else:
            replacements.append((member.value.start, member.value.end, value))
    if missing:
        insertion = b",".join(missing)
        prefix = b"," if target.members else b""
        replacements.append((target.end - 1, target.end - 1, prefix + insertion))

    chunks: list[bytes] = []
    cursor = 0
    for start, end, replacement in sorted(replacements):
        chunks.extend((source[cursor:start], replacement))
        cursor = end
    chunks.append(source[cursor:])
    return b"".join(chunks)


def _atomic_manifest(path: Path, source: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(source)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def deactivate_allowance(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).resolve()
    evidence_dir = Path(args.evidence_dir).resolve() if args.evidence_dir else None
    registry_path = _registry_path(project_dir, evidence_dir)
    source = registry_path.read_bytes()
    try:
        registry = json.loads(source.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        message = exc.msg if isinstance(exc, json.JSONDecodeError) else str(exc)
        raise ValueError(f"MALFORMED_ALLOWANCE_REGISTRY:{registry_path}:{message}") from exc
    if not isinstance(registry, dict) or not isinstance(registry.get("allowances"), list):
        raise ValueError(f"MALFORMED_ALLOWANCE_REGISTRY:{registry_path}:allowances must be a list")

    target_index = next(
        (
            index
            for index, record in enumerate(registry["allowances"])
            if isinstance(record, dict) and record.get("allowance_id") == args.deactivate_allowance
        ),
        None,
    )
    if target_index is None:
        raise ValueError(f"ALLOWANCE_NOT_FOUND:{args.deactivate_allowance}")
    allowance = registry["allowances"][target_index]
    if not allowance.get("active") or allowance.get("lifecycle_state") == "closed":
        raise ValueError(f"ALLOWANCE_ALREADY_CLOSED:{args.deactivate_allowance}")

    closed_at_utc = now()
    closed_allowance = dict(allowance)
    closed_allowance.update(
        {
            "active": False,
            "lifecycle_state": "closed",
            "closed_at_utc": closed_at_utc,
        }
    )
    _, allowance_digest = canonical_allowance(closed_allowance)
    updated_source = _lossless_manifest_update(source, target_index, closed_at_utc, allowance_digest)
    _atomic_manifest(registry_path, updated_source)
    print(json.dumps({"allowance_id": args.deactivate_allowance, "manifest": str(registry_path), "status": "closed"}, sort_keys=True))
    return 0




def _require_dispatch_args(args: argparse.Namespace) -> None:
    required = ("task_id", "role", "label", "model_route", "query_file", "allowance_file", "evidence_dir", "timeout")
    missing = [name.replace("_", "-") for name in required if getattr(args, name) is None]
    if missing:
        raise ValueError(f"MISSING_DISPATCH_ARGUMENTS:{','.join(missing)}")


def dispatch(args: argparse.Namespace) -> int:
    _require_dispatch_args(args)
    if args.invocation_id is not None:
        raise ValueError("CALLER_INVOCATION_ID_FORBIDDEN")
    project_dir = Path(args.project_dir).resolve()
    query_file = Path(args.query_file).resolve()
    allowance_file = Path(args.allowance_file).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    if not query_file.is_file():
        raise ValueError("MISSING_BRIEF")
    if not allowance_file.is_file():
        raise ValueError("MISSING_ALLOWANCE")
    if args.timeout <= 0:
        raise ValueError("INVALID_TIMEOUT")
    _assert_disposable_root(evidence_dir, project_dir)
    expected_model = route_for_role(args.role)
    if args.model_route not in LAUNCHERS:
        raise ValueError(f"UNKNOWN_MODEL_ROUTE:{args.model_route}")
    if expected_model != args.model_route:
        raise ValueError(f"WRONG_MODEL_ROUTE:expected={expected_model}:observed={args.model_route}")
    allowance, allowance_digest = reject_allowance_overlap(allowance_file, evidence_dir, project_dir)
    invocation_id = f"mrc-{secrets.token_hex(24)}"
    started_monotonic = time.monotonic()
    start_timestamp = now()
    command = _build_command(args.model_route, query_file, project_dir, args.timeout)
    command_digest = digest_bytes(canonical_json(command))
    brief_digest = digest_file(query_file)
    start_receipt = {
        "schema": "maintenance-consolidation-invocation-receipt.v1",
        "invocation_id": invocation_id,
        "task_id": args.task_id,
        "role": args.role,
        "label": args.label,
        "model": args.model_route,
        "command": command,
        "command_digest": command_digest,
        "brief_path": str(query_file),
        "brief_digest": brief_digest,
        "allowance_path": str(allowance_file),
        "allowance_digest": allowance_digest,
        "allowance_paths": allowance_paths(allowance),
        "start_timestamp": start_timestamp,
        "status": "started",
    }
    receipt_path = evidence_dir / "receipts" / f"{invocation_id}.json"
    atomic_json(receipt_path, start_receipt)
    process: subprocess.Popen[bytes] | None = None
    stdout = b""
    stderr = b""
    exit_status: int | None = None
    timed_out = False
    try:
        process = subprocess.Popen(command, cwd=project_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = process.communicate(timeout=args.timeout)
            exit_status = process.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = (exc.output or b"") if isinstance(exc.output, bytes) else str(exc.output or "").encode()
            stderr = (exc.stderr or b"") if isinstance(exc.stderr, bytes) else str(exc.stderr or "").encode()
            process.kill()
            tail_out, tail_err = process.communicate()
            stdout += tail_out or b""
            stderr += tail_err or b""
            exit_status = 124
    except OSError as exc:
        stderr = str(exc).encode("utf-8")
        exit_status = 127
    resolved_model = _resolved_model(stdout, stderr)
    if exit_status == 0 and resolved_model is None:
        stderr += b"\nlauncher output did not expose a resolved model\n"
        exit_status = 78
    stdout_path = evidence_dir / "artifacts" / f"{invocation_id}.stdout"
    stderr_path = evidence_dir / "artifacts" / f"{invocation_id}.stderr"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    end_timestamp = now()
    result = {
        "invocation_id": invocation_id,
        "status": "failed" if exit_status else "completed",
        "exit_status": exit_status,
        "timed_out": timed_out,
        "resolved_model": resolved_model or "unknown",
        "child_process_identity": _process_identity(process, start_timestamp) if process is not None else "unknown",
        "stdout_digest": digest_bytes(stdout),
        "stderr_digest": digest_bytes(stderr),
    }
    result_bytes = canonical_json(result) + b"\n"
    result_path = evidence_dir / "artifacts" / f"{invocation_id}.result.json"
    result_path.write_bytes(result_bytes)
    closed = {
        **start_receipt,
        "end_timestamp": end_timestamp,
        "elapsed_seconds": max(0.0, time.monotonic() - started_monotonic),
        "exit_status": exit_status,
        "resolved_model": result["resolved_model"],
        "child_process_identity": result["child_process_identity"],
        "stdout_path": str(stdout_path),
        "stdout_digest": result["stdout_digest"],
        "stderr_path": str(stderr_path),
        "stderr_digest": result["stderr_digest"],
        "result_path": str(result_path),
        "result_digest": digest_bytes(result_bytes),
        "status": result["status"],
    }
    atomic_json(receipt_path, closed)
    print(json.dumps({"invocation_id": invocation_id, "receipt": str(receipt_path), "status": closed["status"]}, sort_keys=True))
    return 0 if exit_status == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--deactivate-allowance", default=None)
    parser.add_argument("--task-id")
    parser.add_argument("--role")
    parser.add_argument("--label")
    parser.add_argument("--model-route", choices=tuple(LAUNCHERS))
    parser.add_argument("--query-file")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--allowance-file")
    parser.add_argument("--evidence-dir")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--invocation-id", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.deactivate_allowance is not None:
            return deactivate_allowance(args)
        return dispatch(args)
    except SystemExit as exc:
        return int(exc.code)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"code": str(exc).split(":", 1)[0], "message": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())


