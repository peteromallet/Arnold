"""Patch custody path helpers and hardened patch bundle capture."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from megaplan._core import atomic_write_bytes, atomic_write_json, now_utc

from .identity import (
    TaskIdentity,
    TaskIdentityError,
    build_task_identity_map,
    make_task_identity,
    validate_trailer_identity,
)
from .paths import custody_paths, validate_run_id, validate_task_id
from .registry import append_registry_entry
from .secrets import SECRET_SCAN_MODES, run_gitleaks_policy

PATCH_BUNDLE_SCHEMA_VERSION = 1
MAX_BINARY_HUNK_BYTES = 10 * 1024 * 1024
DIFF_FLAGS = [
    "--cached",
    "--binary",
    "--full-index",
    "--find-renames",
    "--no-color",
    "--no-ext-diff",
    "--no-textconv",
]


@dataclass(frozen=True)
class PatchCaptureResult:
    run_id: str
    task_id: str
    patch_path: Path
    manifest_path: Path
    patch_sha256: str
    patch_size_bytes: int
    changed_paths: list[str]


@dataclass(frozen=True)
class PatchBundleRecord:
    run_id: str
    task_id: str
    patch_path: Path
    manifest_path: Path
    patch_sha256: str
    patch_size_bytes: int
    manifest: dict[str, Any]
    base_head: str | None
    task_key: str | None
    identity: dict[str, Any] | None
    trailers: dict[str, str] | None
    secret_scan: dict[str, Any] | None


class PatchCaptureError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_bundle_for_apply(repo: str | Path, bundle: PatchBundleRecord | PatchCaptureResult) -> dict[str, Any]:
    """Validate a patch bundle before it is handed to git apply."""
    repo_path = Path(repo).resolve()
    patch_bytes = _bundle_bytes(bundle)
    return _validate_patch_bytes_for_apply(repo_path, patch_bytes)


def git_apply_check_bundle(repo: str | Path, bundle: PatchBundleRecord | PatchCaptureResult) -> dict[str, Any]:
    """Run git apply --check only after coordinator-side bundle validation passes."""
    repo_path = Path(repo).resolve()
    patch_bytes = _bundle_bytes(bundle)
    validation = _validate_patch_bytes_for_apply(repo_path, patch_bytes)
    if not validation["ok"]:
        return {"ok": False, "validation": validation, "git_apply_ran": False}

    proc = _run_git_apply_check(repo_path, patch_bytes)
    return {
        "ok": proc.returncode == 0,
        "validation": validation,
        "git_apply_ran": True,
        "returncode": proc.returncode,
        "stdout": proc.stdout.decode("utf-8", errors="replace"),
        "stderr": proc.stderr.decode("utf-8", errors="replace"),
    }


def patch_bundle_dir(project_dir: str | Path, run_id: str) -> Path:
    return custody_paths(project_dir).patch_run_dir(run_id)


def patch_task_dir(project_dir: str | Path, run_id: str, task_id: str) -> Path:
    return custody_paths(project_dir).patch_task_dir(run_id, task_id)


def patch_manifest_path(project_dir: str | Path, run_id: str, task_id: str) -> Path:
    return custody_paths(project_dir).patch_manifest(run_id, task_id)


def patch_payload_path(project_dir: str | Path, run_id: str, task_id: str) -> Path:
    return custody_paths(project_dir).patch_payload(run_id, task_id)


def load_patch_bundle(project_dir: str | Path, run_id: str, task_id: str) -> PatchBundleRecord:
    """Load a coordinator-owned patch bundle from the custody manifest."""
    run_id = validate_run_id(run_id)
    task_id = validate_task_id(task_id)
    paths = custody_paths(project_dir)
    manifest_path = paths.patch_manifest(run_id, task_id)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PatchCaptureError("manifest_missing", f"patch manifest not found: {manifest_path}") from exc
    patch_meta = manifest.get("patch")
    if not isinstance(patch_meta, dict):
        raise PatchCaptureError("manifest_invalid", "patch manifest is missing patch metadata")
    expected_patch = paths.patch_payload(run_id, task_id)
    patch_path = _manifest_patch_path(paths.custody_root, patch_meta)
    if patch_path.resolve() != expected_patch.resolve():
        raise PatchCaptureError("manifest_invalid", "patch manifest does not point at the coordinator-owned bundle")
    if not isinstance(patch_meta.get("sha256"), str) or not isinstance(patch_meta.get("size_bytes"), int):
        raise PatchCaptureError("manifest_invalid", "patch manifest hash and size metadata are required")
    return PatchBundleRecord(
        run_id=run_id,
        task_id=task_id,
        patch_path=patch_path,
        manifest_path=manifest_path,
        patch_sha256=patch_meta.get("sha256"),
        patch_size_bytes=patch_meta.get("size_bytes"),
        manifest=manifest,
        base_head=manifest.get("base_head") if isinstance(manifest.get("base_head"), str) else None,
        task_key=manifest.get("task_key") if isinstance(manifest.get("task_key"), str) else None,
        identity=manifest.get("identity") if isinstance(manifest.get("identity"), dict) else None,
        trailers=manifest.get("trailers") if isinstance(manifest.get("trailers"), dict) else None,
        secret_scan=manifest.get("secret_scan") if isinstance(manifest.get("secret_scan"), dict) else None,
    )


def capture_patch_bundle(
    project_dir: str | Path,
    run_id: str,
    task_id: str,
    task_worktree: str | Path,
    *,
    secret_scan_mode: str,
    identity: TaskIdentity | None = None,
) -> PatchCaptureResult:
    """Capture a task worktree patch without mutating its real index."""
    run_id = validate_run_id(run_id)
    task_id = validate_task_id(task_id)
    identity = identity or make_task_identity(task_id)
    if identity.original_task_id != task_id:
        raise PatchCaptureError("identity_mismatch", "patch capture identity must match the task id")
    if secret_scan_mode not in SECRET_SCAN_MODES:
        raise PatchCaptureError(
            "invalid_secret_scan_mode",
            f"secret_scan_mode must be one of {sorted(SECRET_SCAN_MODES)}",
        )

    worktree = Path(task_worktree).resolve()
    _ensure_git_worktree(worktree)
    paths = custody_paths(project_dir)
    bundle_dir = paths.patch_task_dir(run_id, task_id)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    patch_path = paths.patch_payload(run_id, task_id)
    manifest_path = paths.patch_manifest(run_id, task_id)

    with tempfile.NamedTemporaryFile(prefix=".megaplan-index-", delete=False) as handle:
        temp_index = Path(handle.name)
    try:
        head = _git_stdout(worktree, ["rev-parse", "HEAD"])
        env = _hardened_git_env(temp_index)
        _run_git(worktree, ["read-tree", "HEAD"], env=env)
        _run_git(worktree, ["add", "-A", "--", "."], env=env)
        changed_paths = _git_stdout(
            worktree,
            ["diff", "--cached", "--name-only", "-z", "HEAD", "--"],
            env=env,
            text=False,
        ).decode("utf-8").split("\0")
        changed_paths = [path for path in changed_paths if path]
        patch_bytes = _run_git(
            worktree,
            ["diff", *DIFF_FLAGS, "HEAD", "--"],
            env=env,
            text=False,
        ).stdout
        atomic_write_bytes(patch_path, patch_bytes)
        patch_sha = _sha256_bytes(patch_bytes)
        secret_scan = run_gitleaks_policy(worktree, mode=secret_scan_mode)
        manifest = {
            "schema_version": PATCH_BUNDLE_SCHEMA_VERSION,
            "run_id": run_id,
            "task_id": task_id,
            "task_key": identity.task_key,
            "identity": identity.registry_identity(),
            "trailers": identity.trailer_fields(),
            "created_at": now_utc(),
            "worktree": str(worktree),
            "base_head": head.strip(),
            "patch": {
                "path": patch_path.relative_to(paths.custody_root).as_posix(),
                "sha256": patch_sha,
                "size_bytes": len(patch_bytes),
                "changed_paths": changed_paths,
            },
            "git": {
                "temporary_index": True,
                "diff_flags": DIFF_FLAGS,
                "hardened_environment": {
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_PAGER": "cat",
                    "GIT_EXTERNAL_DIFF": "",
                    "GIT_DIFF_OPTS": "",
                },
                "hardened_config": [
                    "color.ui=false",
                    "core.pager=cat",
                    "pager.diff=false",
                    "diff.external=",
                    "diff.textconv=false",
                ],
            },
            "secret_scan": secret_scan,
        }
        atomic_write_json(manifest_path, manifest)
        append_registry_entry(
            project_dir,
            run_id,
            "patch_captured",
            {
                "task_id": task_id,
                "task_key": identity.task_key,
                "base_head": head.strip(),
                "patch": manifest["patch"],
                "secret_scan": secret_scan,
                "identity": identity.registry_identity(),
                "trailers": identity.trailer_fields(),
            },
            identity=identity,
        )
        if secret_scan["status"] == "failed":
            raise PatchCaptureError(
                "secret_scan_failed",
                secret_scan["redacted_reason"] or "secret scan failed",
            )
        return PatchCaptureResult(
            run_id=run_id,
            task_id=task_id,
            patch_path=patch_path,
            manifest_path=manifest_path,
            patch_sha256=patch_sha,
            patch_size_bytes=len(patch_bytes),
            changed_paths=changed_paths,
        )
    finally:
        try:
            temp_index.unlink()
        except FileNotFoundError:
            pass


def prevalidate_patch_apply(
    project_dir: str | Path,
    run_id: str,
    task_id: str,
    milestone_repo: str | Path,
    finalize_data: dict[str, Any],
) -> dict[str, Any]:
    """Validate a task patch bundle against finalized identity and milestone HEAD before apply."""
    run_id = validate_run_id(run_id)
    task_id = validate_task_id(task_id)
    repo_path = Path(milestone_repo).resolve()
    identity = _identity_from_finalize(finalize_data, task_id)
    bundle = load_patch_bundle(project_dir, run_id, task_id)
    current_head = _current_milestone_head(repo_path)
    issues: list[dict[str, Any]] = []

    if bundle.base_head is None:
        issues.append(_issue("manifest_missing_base_head", "patch manifest is missing base_head"))
    elif bundle.base_head != current_head:
        issues.append(
            _issue(
                "base_head_mismatch",
                "patch manifest base_head does not match current milestone HEAD",
            )
        )

    issues.extend(_manifest_identity_issues(bundle, identity))
    if issues:
        payload = _apply_prevalidation_payload(
            bundle,
            identity,
            current_head=current_head,
            ok=False,
            errors=issues,
            apply_check={"ok": False, "git_apply_ran": False},
        )
        _record_apply_checked(project_dir, run_id, identity, payload)
        return payload

    apply_check = git_apply_check_bundle(repo_path, bundle)
    payload = _apply_prevalidation_payload(
        bundle,
        identity,
        current_head=current_head,
        ok=bool(apply_check.get("ok")),
        errors=[] if apply_check.get("ok") else apply_check.get("validation", {}).get("errors", []),
        apply_check=apply_check,
    )
    _record_apply_checked(project_dir, run_id, identity, payload)
    return payload


def _identity_from_finalize(finalize_data: dict[str, Any], task_id: str) -> TaskIdentity:
    tasks = finalize_data.get("tasks")
    if not isinstance(tasks, list):
        raise PatchCaptureError("finalize_tasks_missing", "finalize data must contain a tasks list")
    try:
        identity_map = build_task_identity_map(tasks)
    except Exception as exc:
        raise PatchCaptureError("finalize_identity_invalid", str(exc)) from exc
    identity = identity_map.get(task_id)
    if identity is None:
        raise PatchCaptureError("task_identity_missing", f"finalize data does not contain task {task_id!r}")
    return identity


def _current_milestone_head(repo_path: Path) -> str:
    _ensure_git_worktree(repo_path)
    return str(_git_stdout(repo_path, ["rev-parse", "HEAD"])).strip()


def _manifest_identity_issues(bundle: PatchBundleRecord, identity: TaskIdentity) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    manifest_task_id = bundle.manifest.get("task_id")
    if manifest_task_id != identity.original_task_id:
        issues.append(_issue("identity_mismatch", "patch manifest task_id does not match finalized task identity"))
    if bundle.task_key != identity.task_key:
        issues.append(_issue("identity_mismatch", "patch manifest task_key does not match finalized task identity"))
    if bundle.identity != identity.registry_identity():
        issues.append(_issue("identity_mismatch", "patch manifest identity metadata does not match finalized task identity"))
    trailers = bundle.trailers
    if not isinstance(trailers, dict):
        issues.append(_issue("trailer_identity_mismatch", "patch manifest is missing task identity trailers"))
        return issues
    try:
        validated_identity = validate_trailer_identity(trailers, {identity.original_task_id: identity})
    except TaskIdentityError as exc:
        issues.append(_issue("trailer_identity_mismatch", str(exc)))
        return issues
    if validated_identity != identity:
        issues.append(_issue("trailer_identity_mismatch", "patch manifest trailers do not match finalized task identity"))
    if trailers != identity.trailer_fields():
        issues.append(_issue("trailer_identity_mismatch", "patch manifest trailer fields do not match expected encoding"))
    return issues


def _apply_prevalidation_payload(
    bundle: PatchBundleRecord,
    identity: TaskIdentity,
    *,
    current_head: str,
    ok: bool,
    errors: list[dict[str, Any]],
    apply_check: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": ok,
        "task_id": identity.original_task_id,
        "task_key": identity.task_key,
        "base_head": bundle.base_head,
        "current_head": current_head,
        "patch": {
            "path": bundle.patch_path.as_posix(),
            "sha256": bundle.patch_sha256,
            "size_bytes": bundle.patch_size_bytes,
            "changed_paths": bundle.manifest.get("patch", {}).get("changed_paths", []),
        },
        "secret_scan": bundle.secret_scan,
        "identity": identity.registry_identity(),
        "trailers": identity.trailer_fields(),
        "errors": errors,
        "apply_check": apply_check,
    }


def _record_apply_checked(
    project_dir: str | Path,
    run_id: str,
    identity: TaskIdentity,
    payload: dict[str, Any],
) -> None:
    append_registry_entry(project_dir, run_id, "apply_checked", payload, identity=identity)


def _ensure_git_worktree(worktree: Path) -> None:
    if not (worktree / ".git").exists():
        raise PatchCaptureError("not_git_worktree", f"{worktree} is not a git worktree")


def _sha256_bytes(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _hardened_git_env(temp_index: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "GIT_INDEX_FILE": str(temp_index),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_PAGER": "cat",
            "GIT_EXTERNAL_DIFF": "",
            "GIT_DIFF_OPTS": "",
        }
    )
    return env


def _git_command(args: list[str]) -> list[str]:
    return [
        "git",
        "-c",
        "color.ui=false",
        "-c",
        "core.pager=cat",
        "-c",
        "pager.diff=false",
        "-c",
        "diff.external=",
        "-c",
        "diff.textconv=false",
        *args,
    ]


def _run_git(
    worktree: Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    text: bool = False,
) -> subprocess.CompletedProcess[Any]:
    try:
        proc = subprocess.run(
            _git_command(args),
            cwd=str(worktree),
            env=env,
            capture_output=True,
            text=text,
            check=False,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise PatchCaptureError("git_not_found", "git not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise PatchCaptureError("git_timeout", f"git {' '.join(args)} timed out") from exc
    if proc.returncode != 0:
        stderr = proc.stderr if isinstance(proc.stderr, str) else proc.stderr.decode("utf-8", errors="replace")
        stdout = proc.stdout if isinstance(proc.stdout, str) else proc.stdout.decode("utf-8", errors="replace")
        detail = (stderr or stdout).strip()
        raise PatchCaptureError("git_failed", f"git {' '.join(args)} failed: {detail}")
    return proc


def _git_stdout(
    worktree: Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    text: bool = True,
) -> Any:
    return _run_git(worktree, args, env=env, text=text).stdout


def _bundle_bytes(bundle: PatchBundleRecord | PatchCaptureResult) -> bytes:
    if not isinstance(bundle, (PatchBundleRecord, PatchCaptureResult)):
        raise PatchCaptureError(
            "invalid_bundle_record",
            "patch validation requires a coordinator-created bundle record",
        )
    patch_path = Path(bundle.patch_path)
    manifest_path = Path(bundle.manifest_path)
    _verify_bundle_record_layout(bundle, patch_path, manifest_path)
    if not patch_path.exists():
        raise PatchCaptureError("bundle_missing", f"patch bundle not found: {patch_path}")
    if not manifest_path.exists():
        raise PatchCaptureError("manifest_missing", f"patch manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    patch_meta = manifest.get("patch")
    if not isinstance(patch_meta, dict):
        raise PatchCaptureError("manifest_invalid", "patch manifest is missing patch metadata")
    manifest_patch_path = _manifest_patch_path(_custody_root_from_manifest(manifest_path), patch_meta)
    if manifest_patch_path.resolve() != patch_path.resolve():
        raise PatchCaptureError("manifest_invalid", "patch manifest does not match the bundle record")
    patch_bytes = patch_path.read_bytes()
    patch_sha = _sha256_bytes(patch_bytes)
    if (
        patch_sha != bundle.patch_sha256
        or len(patch_bytes) != bundle.patch_size_bytes
        or patch_sha != patch_meta.get("sha256")
        or len(patch_bytes) != patch_meta.get("size_bytes")
    ):
        raise PatchCaptureError("bundle_drift", "patch bundle hash or size differs from the coordinator manifest")
    return patch_bytes


def _verify_bundle_record_layout(
    bundle: PatchBundleRecord | PatchCaptureResult,
    patch_path: Path,
    manifest_path: Path,
) -> None:
    if manifest_path.name != "manifest.json":
        raise PatchCaptureError("invalid_bundle_record", "bundle manifest must use the coordinator manifest filename")
    if patch_path.name != "bundle.patch":
        raise PatchCaptureError("invalid_bundle_record", "bundle patch must use the coordinator payload filename")
    if patch_path.parent.resolve() != manifest_path.parent.resolve():
        raise PatchCaptureError("invalid_bundle_record", "bundle patch and manifest must share a task custody directory")
    if manifest_path.parent.name != f"task-{validate_task_id(bundle.task_id)}":
        raise PatchCaptureError("invalid_bundle_record", "bundle manifest is not in the expected task custody directory")
    if manifest_path.parent.parent.name != validate_run_id(bundle.run_id):
        raise PatchCaptureError("invalid_bundle_record", "bundle manifest is not in the expected run custody directory")
    if manifest_path.parent.parent.parent.name != "patches":
        raise PatchCaptureError("invalid_bundle_record", "bundle manifest is not under coordinator patch custody storage")
    if manifest_path.parent.parent.parent.parent.name != "worktrees":
        raise PatchCaptureError("invalid_bundle_record", "bundle manifest is not under coordinator worktree custody storage")


def _custody_root_from_manifest(manifest_path: Path) -> Path:
    return manifest_path.parent.parent.parent.parent


def _manifest_patch_path(custody_root: Path, patch_meta: dict[str, Any]) -> Path:
    raw_path = patch_meta.get("path")
    if not isinstance(raw_path, str):
        raise PatchCaptureError("manifest_invalid", "patch manifest path must be a string")
    path = Path(raw_path)
    if path.is_absolute():
        raise PatchCaptureError("manifest_invalid", "patch manifest path must be relative to custody root")
    patch_path = (custody_root / path).resolve()
    custody_root_real = custody_root.resolve()
    if not _is_relative_to(patch_path, custody_root_real):
        raise PatchCaptureError("manifest_invalid", "patch manifest path escapes custody storage")
    return patch_path


def _validate_patch_bytes_for_apply(repo_path: Path, patch_bytes: bytes) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if not (repo_path / ".git").exists():
        issues.append(_issue("not_git_repo", "repository does not contain .git"))
        return {"ok": False, "errors": issues}

    patch_text = patch_bytes.decode("utf-8", errors="replace")
    current_old_dev_null = False
    seen_old_header = False
    for line_no, line in enumerate(patch_text.splitlines(), start=1):
        if line.startswith("diff --git "):
            seen_old_header = False
            current_old_dev_null = False
            _validate_diff_header(repo_path, line, line_no, issues)
            continue
        if line.startswith("--- "):
            path = _first_header_token(line[4:], line_no, issues)
            seen_old_header = True
            current_old_dev_null = path == "/dev/null"
            if path is not None:
                _validate_patch_path(repo_path, path, line_no, issues, prefix="a/", allow_dev_null=True)
            continue
        if line.startswith("+++ "):
            path = _first_header_token(line[4:], line_no, issues)
            if path == "/dev/null" and seen_old_header and current_old_dev_null:
                issues.append(_issue("invalid_dev_null", "both file headers point at /dev/null", line_no))
            if path is not None:
                _validate_patch_path(repo_path, path, line_no, issues, prefix="b/", allow_dev_null=True)
            continue
        for header in ("rename from ", "rename to ", "copy from ", "copy to "):
            if line.startswith(header):
                path = _decode_path_token(line[len(header):], line_no, issues)
                if path is not None:
                    _validate_patch_path(repo_path, path, line_no, issues, allow_dev_null=False)
                break
        _validate_mode_line(line, line_no, issues)
        _validate_binary_line(line, line_no, issues)

    return {"ok": not issues, "errors": issues}


def _issue(code: str, message: str, line: int | None = None, path: str | None = None) -> dict[str, Any]:
    issue: dict[str, Any] = {"code": code, "message": message}
    if line is not None:
        issue["line"] = line
    if path is not None:
        issue["path"] = path
    return issue


def _validate_diff_header(repo: Path, line: str, line_no: int, issues: list[dict[str, Any]]) -> None:
    tokens = _split_header_tokens(line[len("diff --git "):], line_no, issues)
    if len(tokens) != 2:
        issues.append(_issue("malformed_patch_header", "diff header must contain two paths", line_no))
        return
    _validate_patch_path(repo, tokens[0], line_no, issues, prefix="a/", allow_dev_null=False)
    _validate_patch_path(repo, tokens[1], line_no, issues, prefix="b/", allow_dev_null=False)


def _first_header_token(rest: str, line_no: int, issues: list[dict[str, Any]]) -> str | None:
    tokens = _split_header_tokens(rest, line_no, issues)
    return tokens[0] if tokens else None


def _split_header_tokens(text: str, line_no: int, issues: list[dict[str, Any]]) -> list[str]:
    tokens: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        while index < length and text[index].isspace():
            index += 1
        if index >= length:
            break
        if text[index] == '"':
            token, index = _read_quoted_token(text, index, line_no, issues)
            if token is None:
                break
            tokens.append(token)
            continue
        start = index
        while index < length and not text[index].isspace():
            index += 1
        tokens.append(text[start:index])
    return tokens


def _decode_path_token(text: str, line_no: int, issues: list[dict[str, Any]]) -> str | None:
    stripped = text.strip()
    if stripped.startswith('"'):
        token, end = _read_quoted_token(stripped, 0, line_no, issues)
        if token is None:
            return None
        if stripped[end:].strip():
            issues.append(_issue("malformed_quoted_path", "unexpected trailing content after quoted path", line_no))
        return token
    return stripped


def _read_quoted_token(
    text: str,
    index: int,
    line_no: int,
    issues: list[dict[str, Any]],
) -> tuple[str | None, int]:
    output = bytearray()
    index += 1
    while index < len(text):
        char = text[index]
        if char == '"':
            try:
                return output.decode("utf-8"), index + 1
            except UnicodeDecodeError:
                issues.append(_issue("malformed_quoted_path", "quoted path is not valid UTF-8", line_no))
                return None, len(text)
        if char != "\\":
            output.extend(char.encode("utf-8"))
            index += 1
            continue
        index += 1
        if index >= len(text):
            issues.append(_issue("malformed_quoted_path", "unterminated escape in quoted path", line_no))
            return None, len(text)
        escaped = text[index]
        if escaped in {'"', "\\"}:
            output.extend(escaped.encode("utf-8"))
            index += 1
        elif escaped == "n":
            output.append(0x0A)
            index += 1
        elif escaped == "t":
            output.append(0x09)
            index += 1
        elif escaped == "r":
            output.append(0x0D)
            index += 1
        elif escaped in "01234567":
            digits = escaped
            index += 1
            while index < len(text) and len(digits) < 3 and text[index] in "01234567":
                digits += text[index]
                index += 1
            output.append(int(digits, 8))
        else:
            issues.append(_issue("malformed_quoted_path", f"unsupported quoted escape \\{escaped}", line_no))
            return None, len(text)
    issues.append(_issue("malformed_quoted_path", "unterminated quoted path", line_no))
    return None, len(text)


def _validate_patch_path(
    repo: Path,
    raw_path: str,
    line_no: int,
    issues: list[dict[str, Any]],
    *,
    prefix: str | None = None,
    allow_dev_null: bool,
) -> None:
    normalized = _normalize_patch_path(raw_path, line_no, issues, prefix=prefix, allow_dev_null=allow_dev_null)
    if normalized is None:
        return
    _reject_symlink_escape(repo, normalized, line_no, issues)
    _reject_submodule_edit(repo, normalized, line_no, issues)


def _normalize_patch_path(
    raw_path: str,
    line_no: int,
    issues: list[dict[str, Any]],
    *,
    prefix: str | None,
    allow_dev_null: bool,
) -> Path | None:
    if raw_path == "/dev/null":
        if allow_dev_null:
            return None
        issues.append(_issue("invalid_dev_null", "/dev/null is not valid in this patch header", line_no, raw_path))
        return None
    if prefix is not None:
        if not raw_path.startswith(prefix):
            issues.append(_issue("malformed_patch_path", f"path must start with {prefix}", line_no, raw_path))
            return None
        raw_path = raw_path[len(prefix):]
    if not raw_path:
        issues.append(_issue("empty_path", "patch path is empty", line_no))
        return None
    if "\x00" in raw_path:
        issues.append(_issue("malformed_patch_path", "patch path contains NUL", line_no, raw_path))
        return None
    if raw_path.startswith(("/", "\\")):
        issues.append(_issue("absolute_path", "patch path must be relative", line_no, raw_path))
        return None
    if "\\" in raw_path:
        issues.append(_issue("malformed_patch_path", "patch path must use forward slashes", line_no, raw_path))
        return None
    if re.match(r"^[A-Za-z]:", raw_path):
        issues.append(_issue("drive_letter_path", "patch path must not use a drive letter", line_no, raw_path))
        return None
    parts = raw_path.split("/")
    if any(part in {"", "."} for part in parts):
        issues.append(_issue("malformed_patch_path", "patch path contains empty or current-directory segment", line_no, raw_path))
        return None
    if any(part == ".." for part in parts):
        issues.append(_issue("traversal_path", "patch path must not traverse outside the repository", line_no, raw_path))
        return None
    return Path(*parts)


def _reject_symlink_escape(repo: Path, rel_path: Path, line_no: int, issues: list[dict[str, Any]]) -> None:
    repo_real = repo.resolve()
    current = repo
    for part in rel_path.parts:
        current = current / part
        if current.is_symlink() and not _is_relative_to(current.resolve(), repo_real):
            issues.append(
                _issue(
                    "symlink_escape",
                    "patch path crosses a symlink that resolves outside the repository",
                    line_no,
                    rel_path.as_posix(),
                )
            )
            return
        if not current.exists():
            break
    resolved_parent = (repo / rel_path).parent.resolve()
    if not _is_relative_to(resolved_parent, repo_real):
        issues.append(_issue("symlink_escape", "patch parent resolves outside the repository", line_no, rel_path.as_posix()))


def _reject_submodule_edit(repo: Path, rel_path: Path, line_no: int, issues: list[dict[str, Any]]) -> None:
    candidates = [Path(*rel_path.parts[:index]) for index in range(1, len(rel_path.parts) + 1)]
    for candidate in candidates:
        proc = subprocess.run(
            _git_command(["ls-files", "-s", "--", candidate.as_posix()]),
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if proc.returncode == 0 and any(line.startswith("160000 ") for line in proc.stdout.splitlines()):
            issues.append(_issue("submodule_edit", "patch edits a submodule gitlink", line_no, rel_path.as_posix()))
            return


def _validate_mode_line(line: str, line_no: int, issues: list[dict[str, Any]]) -> None:
    match = re.match(r"^(?:old mode|new mode|deleted file mode|new file mode) ([0-7]{6})$", line)
    if match is None:
        if line.startswith("index ") and line.rstrip().endswith(" 160000"):
            issues.append(_issue("submodule_edit", "patch edits a submodule gitlink", line_no))
        return
    mode = match.group(1)
    if mode == "120000":
        issues.append(_issue("symlink_edit", "patch creates or edits a symlink", line_no))
    if mode == "160000":
        issues.append(_issue("submodule_edit", "patch creates or edits a submodule gitlink", line_no))


def _validate_binary_line(line: str, line_no: int, issues: list[dict[str, Any]]) -> None:
    match = re.match(r"^(?:literal|delta) ([0-9]+)$", line)
    if match is None:
        return
    size = int(match.group(1))
    if size > MAX_BINARY_HUNK_BYTES:
        issues.append(
            _issue(
                "oversized_binary_hunk",
                f"binary hunk declares {size} bytes, limit is {MAX_BINARY_HUNK_BYTES}",
                line_no,
            )
        )


def _run_git_apply_check(repo: Path, patch_bytes: bytes) -> subprocess.CompletedProcess[bytes]:
    env = dict(os.environ)
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_PAGER": "cat",
            "GIT_EXTERNAL_DIFF": "",
            "GIT_DIFF_OPTS": "",
        }
    )
    return subprocess.run(
        _git_command(["apply", "--check", "--binary", "--whitespace=nowarn", "-"]),
        cwd=str(repo),
        input=patch_bytes,
        env=env,
        capture_output=True,
        check=False,
        timeout=30,
    )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
