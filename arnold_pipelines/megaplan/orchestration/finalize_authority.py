"""Single transactional authority for ``finalize.json``.

The finalized graph is long lived while several runtime paths need to add
execution observations to it.  Those paths must not become independent
whole-document authorities.  This module provides the only mutation seam:

* every caller carries the hash and version it actually read (CAS);
* publication happens under the plan lock;
* owners may change only their allowlisted fields; and
* every successful mutation leaves immutable, content-addressed history.

Callers should load through :func:`load_finalize_for_update`, mutate the
returned dictionary in memory, then call :func:`publish_finalize_update`.
The read token is kept out of the JSON document and is advanced only after a
successful publish, so a stale in-memory copy fails closed.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from arnold_pipelines.megaplan._core import now_utc, plan_lock
from arnold_pipelines.megaplan.store import write_plan_artifact_json


FinalizeOwner = Literal["finalize", "execute", "auto", "baseline"]


class FinalizeAuthorityError(RuntimeError):
    """Base class for fail-closed finalize authority violations."""


class FinalizeCASMismatch(FinalizeAuthorityError):
    """The caller did not mutate the document version it claims to own."""


class FinalizeFieldOwnershipError(FinalizeAuthorityError):
    """A mutation crossed its owner's field boundary."""


@dataclass(frozen=True)
class FinalizeMutationContext:
    owner: FinalizeOwner
    operation: str
    attempt_id: str
    run_id: str | None = None

    def __post_init__(self) -> None:
        if not self.operation.strip():
            raise ValueError("finalize mutation operation must be non-empty")
        if not self.attempt_id.strip():
            raise ValueError("finalize mutation attempt_id must be non-empty")


@dataclass(frozen=True)
class FinalizeReadToken:
    sha256: str | None
    version: int


# Keep tokens out of the schema-owned document.  Holding the object reference
# also prevents id reuse from making a different dict inherit an old token.
_READ_TOKENS: dict[int, tuple[dict[str, Any], FinalizeReadToken]] = {}

_EXECUTE_TASK_MUTABLE = frozenset(
    {
        "status",
        "executor_notes",
        "files_changed",
        "commands_run",
        "evidence_files",
        "reviewer_verdict",
        "auto_attributed_files",
        "recorded_invocation_id",
        "sections_written",
        "stance",
        "stop_signal",
        # Soft stance-validation metadata the execute seam computes and merges
        # onto task records (merge.py: validate_stance stamps
        # stance_violations; merge_fields includes it in creative mode, and
        # test_merge_scope asserts it lands on the row).  The execute owner
        # must be able to publish it, or any creative batch whose stance fails
        # soft validation aborts with FinalizeFieldOwnershipError — reached by
        # reconcile-latest-execution-batch and by normal creative executes.
        "stance_violations",
        # Evidence-context fields the execute seam stamps/merges onto task
        # records (batch.py:_stamp_head_sha_on_task_records and
        # merge.py evidence_context_fields).  The M2 authority reader treats
        # evidence without a matching head_sha as stale, so the execute owner
        # must be able to publish them or every completed batch aborts with
        # FinalizeFieldOwnershipError before finalize.json is updated.
        "head_sha",
        "code_hash",
        # Scope-reconciliation field the execute seam stamps onto task records
        # (aggregation.py:reconcile_finalized_review_scope_claims — merges
        # review-verdict evidence_files into files_changed and records the
        # reconciled additions).  The execute owner computes and publishes it
        # during the aggregate-execute publish, so it must be publishable or
        # every post-review execute aborts with FinalizeFieldOwnershipError
        # before finalize.json is updated (recurring scope-drift blocker).
        "scope_reconciled_files",
        # Typed blocker disposition stamped by the execute auto-loop when a
        # worker reports a task status=blocked: "prerequisite_blocked" (explicit
        # prereq/user-action blocker) or "validation_blocked" (task-scoped
        # worker/policy block with no accepted terminal authority). The loop
        # parks these rows and continues with the dependency-independent
        # frontier; the kind is surfaced in phase_result BlockedTask.blocker_kind.
        "blocked_reason",
    }
)
_EXECUTE_SENSE_CHECK_MUTABLE = frozenset({"verdict", "executor_note"})
_BASELINE_FIELDS = frozenset(
    {
        "baseline_test_failures",
        "baseline_test_command",
        "baseline_test_note",
        "baseline_test_collection_errors",
    }
)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _document_bytes(value: object) -> bytes:
    """Bytes emitted by the canonical plan-artifact JSON writer."""

    return (json.dumps(value, indent=2, sort_keys=False) + "\n").encode("utf-8")


def _sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def finalize_sha256(plan_dir: Path) -> str | None:
    try:
        return _sha_bytes((plan_dir / "finalize.json").read_bytes())
    except FileNotFoundError:
        return None


def _history_root(plan_dir: Path) -> Path:
    return plan_dir / "finalize_history"


def _committed_receipts(plan_dir: Path, current_sha: str | None) -> list[dict[str, Any]]:
    if current_sha is None:
        return []
    receipts: list[dict[str, Any]] = []
    history = _history_root(plan_dir)
    for marker_path in sorted((history / "commits").glob("*.json")):
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            receipt_ref = str(marker["receipt_ref"])
            receipt_path = history / receipt_ref
            receipt_raw = receipt_path.read_bytes()
            if _sha_bytes(receipt_raw) != marker.get("receipt_sha256"):
                continue
            value = json.loads(receipt_raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        except (KeyError, TypeError, ValueError):
            continue
        if (
            isinstance(value, dict)
            and marker.get("result_sha256") == value.get("result_sha256")
            and marker.get("version") == value.get("version")
        ):
            receipts.append(value)
    # A receipt is committed only when it belongs to the ancestry ending at
    # the current bytes.  Pre-written receipts left by a crash are ignored.
    by_result = {
        str(item.get("result_sha256")): item
        for item in receipts
        if isinstance(item.get("result_sha256"), str)
    }
    chain: list[dict[str, Any]] = []
    cursor: str | None = current_sha
    seen: set[str] = set()
    while cursor and cursor not in seen and cursor in by_result:
        seen.add(cursor)
        item = by_result[cursor]
        chain.append(item)
        parent = item.get("parent_sha256")
        cursor = parent if isinstance(parent, str) else None
    chain.reverse()
    return chain


def current_finalize_token(plan_dir: Path) -> FinalizeReadToken:
    digest = finalize_sha256(plan_dir)
    receipts = _committed_receipts(plan_dir, digest)
    version = int(receipts[-1].get("version", 0)) if receipts else 0
    return FinalizeReadToken(digest, version)


def load_finalize_for_update(plan_dir: Path) -> dict[str, Any]:
    path = plan_dir / "finalize.json"
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise FinalizeAuthorityError("finalize.json must contain an object")
    token = current_finalize_token(plan_dir)
    # Bind to the bytes actually parsed, even if a concurrent writer raced the
    # token scan.  The subsequent CAS will then fail rather than bless staleness.
    token = FinalizeReadToken(_sha_bytes(raw), token.version)
    _READ_TOKENS[id(value)] = (value, token)
    return value


def _token_for(payload: dict[str, Any]) -> FinalizeReadToken:
    registered = _READ_TOKENS.get(id(payload))
    if registered is None or registered[0] is not payload:
        raise FinalizeCASMismatch(
            "finalize payload has no read token; load it through "
            "load_finalize_for_update or supply an explicit initial-publish token"
        )
    return registered[1]


def _changed_keys(before: Mapping[str, Any], after: Mapping[str, Any]) -> set[str]:
    return {key for key in set(before) | set(after) if before.get(key) != after.get(key)}


def _rows_by_id(value: object, *, field: str) -> tuple[list[str], dict[str, dict[str, Any]]]:
    if not isinstance(value, list):
        raise FinalizeFieldOwnershipError(f"{field} must remain a list")
    ids: list[str] = []
    rows: dict[str, dict[str, Any]] = {}
    for row in value:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise FinalizeFieldOwnershipError(f"{field} rows must retain string ids")
        row_id = row["id"]
        if row_id in rows:
            raise FinalizeFieldOwnershipError(f"{field} contains duplicate id {row_id!r}")
        ids.append(row_id)
        rows[row_id] = row
    return ids, rows


def _require_row_field_scope(
    before: object,
    after: object,
    *,
    field: str,
    mutable: frozenset[str],
) -> list[str]:
    before_ids, before_rows = _rows_by_id(before, field=field)
    after_ids, after_rows = _rows_by_id(after, field=field)
    if before_ids != after_ids:
        raise FinalizeFieldOwnershipError(
            f"{field} identity/order is immutable after Finalize admission"
        )
    paths: list[str] = []
    for row_id in before_ids:
        changed = _changed_keys(before_rows[row_id], after_rows[row_id])
        forbidden = changed - mutable
        if forbidden:
            raise FinalizeFieldOwnershipError(
                f"owner may not mutate {field}[{row_id}] fields: {sorted(forbidden)}"
            )
        paths.extend(f"{field}[{row_id}].{key}" for key in sorted(changed))
    return paths


def _validate_field_ownership(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    context: FinalizeMutationContext,
) -> list[str]:
    changed = _changed_keys(before, after)
    if context.owner == "finalize":
        return sorted(changed)
    if context.owner == "baseline":
        forbidden = changed - _BASELINE_FIELDS
        if forbidden:
            raise FinalizeFieldOwnershipError(
                f"baseline owner may not mutate finalize fields: {sorted(forbidden)}"
            )
        return sorted(changed)
    if context.owner == "auto":
        forbidden_top = changed - {"tasks"}
        if forbidden_top:
            raise FinalizeFieldOwnershipError(
                f"auto owner may not mutate finalize fields: {sorted(forbidden_top)}"
            )
        return _require_row_field_scope(
            before.get("tasks", []),
            after.get("tasks", []),
            field="tasks",
            mutable=frozenset({"tier_override"}),
        )
    if context.owner == "execute":
        forbidden_top = changed - ({"tasks", "sense_checks"} | _BASELINE_FIELDS)
        if forbidden_top:
            raise FinalizeFieldOwnershipError(
                f"execute owner may not mutate finalize fields: {sorted(forbidden_top)}"
            )
        paths = sorted(changed & _BASELINE_FIELDS)
        if "tasks" in changed:
            paths.extend(
                _require_row_field_scope(
                    before.get("tasks", []),
                    after.get("tasks", []),
                    field="tasks",
                    mutable=_EXECUTE_TASK_MUTABLE,
                )
            )
        if "sense_checks" in changed:
            paths.extend(
                _require_row_field_scope(
                    before.get("sense_checks", []),
                    after.get("sense_checks", []),
                    field="sense_checks",
                    mutable=_EXECUTE_SENSE_CHECK_MUTABLE,
                )
            )
        return paths
    raise FinalizeFieldOwnershipError(f"unknown finalize owner {context.owner!r}")


def _write_immutable_json(path: Path, value: Mapping[str, Any]) -> None:
    encoded = _canonical_bytes(value)
    _write_immutable_bytes(path, encoded)


def _write_immutable_bytes(path: Path, encoded: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            # Hard-link publication is atomic and refuses replacement, unlike
            # os.replace.  Readers therefore see either no immutable record or
            # all of it, never a partial file.
            os.link(temporary_name, path)
        except FileExistsError:
            if path.read_bytes() != encoded:
                raise FinalizeAuthorityError(
                    f"immutable finalize history collision at {path}"
                )
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def _publish_locked(
    plan_dir: Path,
    payload: dict[str, Any],
    *,
    context: FinalizeMutationContext,
    expected: FinalizeReadToken,
) -> FinalizeReadToken:
    current = current_finalize_token(plan_dir)
    if current != expected:
        raise FinalizeCASMismatch(
            "stale finalize mutation refused: "
            f"expected sha/version {expected.sha256}/{expected.version}, "
            f"found {current.sha256}/{current.version}"
        )
    if current.sha256 is None:
        before: dict[str, Any] = {}
        if context.owner != "finalize":
            raise FinalizeFieldOwnershipError("only Finalize may create finalize.json")
    else:
        before_raw = (plan_dir / "finalize.json").read_bytes()
        if _sha_bytes(before_raw) != current.sha256:
            raise FinalizeCASMismatch("finalize.json changed during CAS validation")
        loaded = json.loads(before_raw)
        if not isinstance(loaded, dict):
            raise FinalizeAuthorityError("current finalize.json is not an object")
        before = loaded

    changed_paths = _validate_field_ownership(before, payload, context)
    result_raw = _document_bytes(payload)
    result_sha = _sha_bytes(result_raw)
    if result_sha == current.sha256:
        return current
    next_version = current.version + 1

    history = _history_root(plan_dir)
    if current.sha256 is not None:
        _write_immutable_bytes(
            history / "snapshots" / f"{current.sha256}.json",
            before_raw,
        )
    _write_immutable_bytes(
        history / "snapshots" / f"{result_sha}.json",
        result_raw,
    )
    receipt = {
        "schema": "megaplan.finalize_mutation_receipt",
        "schema_version": 1,
        "version": next_version,
        "parent_sha256": current.sha256,
        "result_sha256": result_sha,
        "owner": context.owner,
        "operation": context.operation,
        "attempt_id": context.attempt_id,
        "run_id": context.run_id,
        "changed_paths": changed_paths,
        "published_at": now_utc(),
    }
    receipt_digest = _sha_bytes(_canonical_bytes(receipt))
    receipt_path = history / "mutations" / f"{next_version:08d}-{receipt_digest}.json"
    _write_immutable_json(receipt_path, receipt)
    # Publication is deliberately last.  A crash before this point leaves
    # uncommitted immutable evidence, never a partially updated authority.
    write_plan_artifact_json(plan_dir, "finalize.json", payload, contract_context=None)
    actual = finalize_sha256(plan_dir)
    if actual != result_sha:
        raise FinalizeAuthorityError(
            f"finalize publication hash mismatch: expected {result_sha}, got {actual}"
        )
    # Only this post-publication marker makes the prepared receipt part of the
    # committed ancestry.  A failed write can leave snapshots/receipts, but a
    # later identical-content attempt cannot accidentally inherit their owner
    # or attempt identity.
    _write_immutable_json(
        history / "commits" / f"{next_version:08d}-{receipt_digest}.json",
        {
            "schema": "megaplan.finalize_mutation_commit",
            "schema_version": 1,
            "version": next_version,
            "result_sha256": result_sha,
            "receipt_ref": receipt_path.relative_to(history).as_posix(),
            "receipt_sha256": _sha_bytes(receipt_path.read_bytes()),
            "committed_at": now_utc(),
        },
    )
    return FinalizeReadToken(result_sha, next_version)


def publish_finalize_update(
    plan_dir: Path,
    payload: dict[str, Any],
    *,
    context: FinalizeMutationContext,
    lock_held: bool = False,
) -> FinalizeReadToken:
    """Publish a token-bound update and advance that payload's token."""

    expected = _token_for(payload)
    if lock_held:
        result = _publish_locked(plan_dir, payload, context=context, expected=expected)
    else:
        with plan_lock(plan_dir, step=f"finalize-mutation:{context.operation}"):
            result = _publish_locked(plan_dir, payload, context=context, expected=expected)
    _READ_TOKENS[id(payload)] = (payload, result)
    return result


def publish_finalize_candidate(
    plan_dir: Path,
    payload: dict[str, Any],
    *,
    context: FinalizeMutationContext,
    expected_parent: FinalizeReadToken,
    lock_held: bool = False,
) -> FinalizeReadToken:
    """Publish a fully admitted candidate through the sole Finalize owner."""

    if context.owner != "finalize":
        raise FinalizeFieldOwnershipError("candidate publication requires finalize owner")
    if lock_held:
        result = _publish_locked(plan_dir, payload, context=context, expected=expected_parent)
    else:
        with plan_lock(plan_dir, step=f"finalize-publish:{context.operation}"):
            result = _publish_locked(plan_dir, payload, context=context, expected=expected_parent)
    _READ_TOKENS[id(payload)] = (payload, result)
    return result


__all__ = [
    "FinalizeAuthorityError",
    "FinalizeCASMismatch",
    "FinalizeFieldOwnershipError",
    "FinalizeMutationContext",
    "FinalizeReadToken",
    "current_finalize_token",
    "finalize_sha256",
    "load_finalize_for_update",
    "publish_finalize_candidate",
    "publish_finalize_update",
]
