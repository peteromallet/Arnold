#!/usr/bin/env python3
"""Run one frozen M11 pytest partition under durable process custody."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from arnold_pipelines.megaplan.runtime.process import (
    CUSTODY_ADOPTION_POLICY_TERMINATE,
    ProcessCustodyReceipt,
    command_hash,
    coordinator_birth_identity,
    kill_group,
    spawn,
)


SHARD_SCHEMA = "m11.test-shard-receipt.v1"
AGGREGATE_SCHEMA = "m11.no-debt-aggregate.v1"
KINDS = {"full_suite", "semantic_carrier"}
OUTCOMES = ("passed", "failed", "skipped", "xfailed", "xpassed", "errors")
STATUS_MAP = {
    "PASSED": "passed",
    "FAILED": "failed",
    "SKIPPED": "skipped",
    "XFAIL": "xfailed",
    "XPASS": "xpassed",
    "ERROR": "errors",
}
RESULT_RE = re.compile(
    r"^(?P<nodeid>\S+::\S+?)\s+(?P<status>PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)"
    r"(?:\s|$)"
)
SUMMARY_RE = re.compile(
    r"(?P<count>\d+)\s+(?P<status>passed|failed|skipped|xfailed|xpassed|error|errors|deselected)\b"
)


class ValidationShardError(RuntimeError):
    """The shard cannot produce admissible evidence."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationShardError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValidationShardError(f"JSON root must be an object: {path}")
    return value


def _validate_self_hash(value: Mapping[str, Any], *, label: str) -> None:
    unhashed = dict(value)
    observed = unhashed.pop("content_sha256", None)
    if observed != _digest(unhashed):
        raise ValidationShardError(f"{label} content hash mismatch")


def _atomic_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValidationShardError(f"immutable artifact already exists: {path}")
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    except FileExistsError as exc:
        raise ValidationShardError(f"immutable artifact already exists: {path}") from exc
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


@contextmanager
def exclusive_slot(path: Path) -> Iterator[None]:
    """Hold a non-blocking process-wide filesystem slot for one shard."""

    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValidationShardError(f"validation slot already held: {path}") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(
            json.dumps(
                {"pid": os.getpid(), "acquired_at": _utc_now()},
                sort_keys=True,
            )
            + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _git_identity(root: Path) -> dict[str, str]:
    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise ValidationShardError(
                f"git {' '.join(args)} failed: {result.stderr.strip()}"
            )
        return result.stdout.strip()

    dirty = git("status", "--porcelain=v1", "--untracked-files=all")
    if dirty:
        raise ValidationShardError("frozen validation root is dirty")
    return {
        "git_commit": git("rev-parse", "HEAD"),
        "git_tree": git("rev-parse", "HEAD^{tree}"),
    }


def _runtime_identity() -> dict[str, Any]:
    executable = Path(sys.executable).resolve(strict=True)
    return {
        "python": str(executable),
        "python_sha256": _file_digest(executable),
        "safe_path": bool(sys.flags.safe_path),
        "version": list(sys.version_info[:3]),
    }


def _assert_identity(
    *,
    root: Path,
    expected_revision: str,
    expected_tree: str,
    expected_python_sha256: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    revision = _git_identity(root)
    runtime = _runtime_identity()
    if revision != {
        "git_commit": expected_revision,
        "git_tree": expected_tree,
    }:
        raise ValidationShardError("revision/tree differs from frozen binding")
    if runtime["python_sha256"] != expected_python_sha256:
        raise ValidationShardError("interpreter hash differs from frozen binding")
    if runtime["safe_path"] is not True:
        raise ValidationShardError("runner must be invoked with Python -P")
    return revision, runtime


def _pytest_argv(
    root: Path,
    *,
    selectors: Sequence[str],
    ignores: Sequence[str],
    collect_only: bool,
) -> list[str]:
    if not selectors:
        raise ValidationShardError("at least one selector is required")
    argv = [
        sys.executable,
        "-P",
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        *selectors,
    ]
    argv.extend(f"--ignore={value}" for value in ignores)
    if collect_only:
        argv.extend(["--collect-only", "-q"])
    else:
        argv.extend(["-vv", "--tb=no", "--no-header", "-rA"])
    return argv


def _collect_inventory(root: Path, argv: Sequence[str], timeout: float) -> list[str]:
    result = subprocess.run(
        list(argv),
        cwd=root,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if result.returncode not in (0, 5):
        raise ValidationShardError(
            f"collect-only failed with {result.returncode}: {result.stderr[-1000:]}"
        )
    inventory = sorted(
        {
            line.strip()
            for line in result.stdout.splitlines()
            if "::" in line
            and not line.startswith(("=", "ERROR", "WARNING"))
            and " " not in line.strip()
        }
    )
    if not inventory:
        raise ValidationShardError("collect-only produced no exact nodeids")
    return inventory


def _parse_outcomes(output: str) -> tuple[dict[str, int], list[str]]:
    statuses: dict[str, str] = {}
    for raw in output.splitlines():
        match = RESULT_RE.match(raw.strip())
        if match:
            statuses[match.group("nodeid")] = STATUS_MAP[match.group("status")]
    counts = {name: 0 for name in OUTCOMES}
    for status in statuses.values():
        counts[status] += 1
    deselected = 0
    for match in SUMMARY_RE.finditer(output):
        if match.group("status") == "deselected":
            deselected = int(match.group("count"))
    counts["deselected"] = deselected
    counts["debt"] = counts["skipped"] + counts["xfailed"] + counts["xpassed"]
    counts["collected"] = len(statuses)
    return counts, sorted(statuses)


def run_validation_shard(
    *,
    project_root: Path,
    kind: str,
    selectors: Sequence[str],
    ignores: Sequence[str],
    expected_revision: str,
    expected_tree: str,
    expected_python_sha256: str,
    output: Path,
    lock_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Collect and execute one exact pytest partition under exclusive custody."""

    root = project_root.resolve(strict=True)
    if kind not in KINDS:
        raise ValidationShardError(f"unknown shard kind: {kind}")
    with exclusive_slot(lock_path):
        revision, runtime = _assert_identity(
            root=root,
            expected_revision=expected_revision,
            expected_tree=expected_tree,
            expected_python_sha256=expected_python_sha256,
        )
        collect_argv = _pytest_argv(
            root, selectors=selectors, ignores=ignores, collect_only=True
        )
        inventory = _collect_inventory(root, collect_argv, timeout_seconds)
        command = _pytest_argv(
            root, selectors=selectors, ignores=ignores, collect_only=False
        )
        log_path = output.with_suffix(output.suffix + ".log")
        custody_path = output.with_suffix(output.suffix + ".custody.json")
        terminal_path = output.with_suffix(output.suffix + ".terminal.json")
        for artifact in (output, log_path, custody_path, terminal_path):
            if artifact.exists():
                raise ValidationShardError(
                    f"immutable artifact already exists: {artifact}"
                )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        birth = coordinator_birth_identity()
        launched_at = _utc_now()
        with log_path.open("x", encoding="utf-8") as log:
            process = spawn(
                command,
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            custody = ProcessCustodyReceipt(
                receipt_id=_digest(
                    {
                        "command": command,
                        "revision": revision,
                        "kind": kind,
                        "launched_at": launched_at,
                    }
                ),
                coordinator_pid=int(birth["pid"]),
                coordinator_host=birth["host"],
                coordinator_boot_id=birth["boot_id"],
                process_group_id=os.getpgid(process.pid),
                command=tuple(command),
                command_hash=command_hash(command),
                receipt_path=str(custody_path),
                adoption_policy=CUSTODY_ADOPTION_POLICY_TERMINATE,
                deterministic_log_path=str(log_path),
                validation_outcome="running",
                launched_at=launched_at,
            )
            custody_payload = custody.to_dict()
            custody_payload["content_sha256"] = _digest(custody_payload)
            _atomic_new(custody_path, custody_payload)
            timed_out = False
            try:
                exit_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                kill_group(
                    process,
                    grace_s=5.0,
                    escalate=True,
                    label=f"m11-validation:{kind}",
                )
                exit_code = process.wait(timeout=10)

        output_text = log_path.read_text(encoding="utf-8")
        counts, executed_inventory = _parse_outcomes(output_text)
        after_revision, after_runtime = _assert_identity(
            root=root,
            expected_revision=expected_revision,
            expected_tree=expected_tree,
            expected_python_sha256=expected_python_sha256,
        )
        exact_inventory = executed_inventory == inventory
        terminal = {
            "schema": "m11.validation-terminal-receipt.v1",
            "custody_receipt_sha256": custody_payload["content_sha256"],
            "command_hash": command_hash(command),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "log_sha256": _file_digest(log_path),
            "inventory_sha256": _digest(inventory),
            "executed_inventory_sha256": _digest(executed_inventory),
            "exact_inventory": exact_inventory,
            "revision_before": revision,
            "revision_after": after_revision,
            "runtime_before": runtime,
            "runtime_after": after_runtime,
            "completed_at": _utc_now(),
        }
        terminal["content_sha256"] = _digest(terminal)
        _atomic_new(terminal_path, terminal)
        receipt = {
            "schema": SHARD_SCHEMA,
            "kind": kind,
            "command": command,
            "exit_code": exit_code,
            "revision": revision,
            "runtime": runtime,
            "inventory": inventory,
            "counts": counts,
            "debt": (
                []
                if counts["debt"] == 0
                else [
                    f"{key}:{counts[key]}"
                    for key in ("skipped", "xfailed", "xpassed")
                    if counts[key]
                ]
            ),
            "custody_receipt_sha256": custody_payload["content_sha256"],
            "terminal_receipt_sha256": terminal["content_sha256"],
            "exact_inventory": exact_inventory,
        }
        # The aggregate consumer accepts only this exact public schema.
        public = {
            key: receipt[key]
            for key in (
                "schema",
                "kind",
                "command",
                "exit_code",
                "revision",
                "runtime",
                "inventory",
                "counts",
                "debt",
                "custody_receipt_sha256",
                "terminal_receipt_sha256",
                "exact_inventory",
            )
        }
        public["content_sha256"] = _digest(public)
        _atomic_new(output, public)
        if not exact_inventory:
            raise ValidationShardError(
                "executed nodeids differ from frozen collect-only inventory"
            )
        return public


def build_aggregate(
    *,
    shard_receipts: Sequence[Mapping[str, Any]],
    expected_inventory: Sequence[str],
) -> dict[str, Any]:
    """Build an exact no-overlap/no-gap aggregate accepted by the generator."""

    expected = sorted(expected_inventory)
    if not expected or len(expected) != len(set(expected)):
        raise ValidationShardError(
            "expected inventory must be non-empty and duplicate-free"
        )
    seen: set[str] = set()
    revision: dict[str, Any] | None = None
    runtime: dict[str, Any] | None = None
    entries: list[dict[str, Any]] = []
    kinds: set[str] = set()
    hashes: set[str] = set()
    for index, raw in enumerate(shard_receipts):
        receipt = dict(raw)
        _validate_self_hash(receipt, label=f"shard[{index}]")
        if receipt.get("schema") != SHARD_SCHEMA:
            raise ValidationShardError(f"shard[{index}] schema mismatch")
        kind = receipt.get("kind")
        if kind not in KINDS:
            raise ValidationShardError(f"shard[{index}] kind mismatch")
        digest = str(receipt["content_sha256"])
        if digest in hashes:
            raise ValidationShardError("duplicate shard receipt")
        hashes.add(digest)
        inventory = receipt.get("inventory")
        if (
            not isinstance(inventory, list)
            or inventory != sorted(inventory)
            or len(inventory) != len(set(inventory))
        ):
            raise ValidationShardError(f"shard[{index}] inventory is not canonical")
        overlap = seen.intersection(inventory)
        if overlap:
            raise ValidationShardError(
                f"shard inventories overlap: {sorted(overlap)!r}"
            )
        seen.update(inventory)
        shard_revision = receipt.get("revision")
        shard_runtime = receipt.get("runtime")
        if revision is None:
            revision = dict(shard_revision)
            runtime = dict(shard_runtime)
        elif shard_revision != revision or shard_runtime != runtime:
            raise ValidationShardError("shard revision/runtime mismatch")
        command = receipt.get("command")
        if not isinstance(command, list) or not command:
            raise ValidationShardError(f"shard[{index}] command missing")
        entries.append(
            {
                "kind": kind,
                "content_sha256": digest,
                "command": command,
                "inventory": inventory,
            }
        )
        kinds.add(kind)
    if kinds != KINDS:
        raise ValidationShardError(
            "full_suite and semantic_carrier shards are both required"
        )
    if sorted(seen) != expected:
        raise ValidationShardError("shard union has gaps or unexpected nodeids")
    aggregate = {
        "schema": AGGREGATE_SCHEMA,
        "revision": revision,
        "runtime": runtime,
        "expected_inventory": expected,
        "receipts": sorted(entries, key=lambda row: row["content_sha256"]),
    }
    aggregate["content_sha256"] = _digest(aggregate)
    return aggregate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--project-root", type=Path, required=True)
    run.add_argument("--kind", choices=sorted(KINDS), required=True)
    run.add_argument("--selector", action="append", required=True)
    run.add_argument("--ignore", action="append", default=[])
    run.add_argument("--expected-revision", required=True)
    run.add_argument("--expected-tree", required=True)
    run.add_argument("--expected-python-sha256", required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--lock", type=Path, required=True)
    run.add_argument("--timeout-seconds", type=float, default=3600)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--shard", type=Path, action="append", required=True)
    preflight.add_argument("--expected-inventory", type=Path, required=True)
    preflight.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "run":
        run_validation_shard(
            project_root=args.project_root,
            kind=args.kind,
            selectors=args.selector,
            ignores=args.ignore,
            expected_revision=args.expected_revision,
            expected_tree=args.expected_tree,
            expected_python_sha256=args.expected_python_sha256,
            output=args.output,
            lock_path=args.lock,
            timeout_seconds=args.timeout_seconds,
        )
    else:
        expected_payload = _load(args.expected_inventory)
        expected = expected_payload.get("inventory")
        if not isinstance(expected, list):
            raise ValidationShardError(
                "expected inventory file must contain an inventory array"
            )
        aggregate = build_aggregate(
            shard_receipts=[_load(path) for path in args.shard],
            expected_inventory=expected,
        )
        _atomic_new(args.output, aggregate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
