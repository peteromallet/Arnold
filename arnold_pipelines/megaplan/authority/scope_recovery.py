"""CAS-fenced successor claims for task-contract receipt recovery.

This is not a second task-status system.  It is an immutable amendment journal
adjacent to the existing attempt ledger: a rejected attempt remains rejected,
while one successor generation is allowed to reuse its landed tree and run
verification only.  The execution body is never authorized by this record.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from arnold_pipelines.megaplan._core import atomic_write_json, now_utc, read_json


SCHEMA = "megaplan.task_scope_recovery"
SCHEMA_VERSION = 1


class ScopeRecoveryConflict(ValueError):
    pass


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def normalize_recovery_path(raw: str) -> str:
    """Return a safe repo-relative POSIX path or raise."""

    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("scope recovery path must be a non-empty string")
    value = raw.strip().replace("\\", "/")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\x00" in value:
        raise ValueError(f"unsafe scope recovery path: {raw!r}")
    normalized = path.as_posix().lstrip("./")
    if not normalized or normalized == ".":
        raise ValueError(f"unsafe scope recovery path: {raw!r}")
    return normalized


@dataclass(frozen=True)
class ScopeRecoveryRequest:
    task_id: str
    batch_id: str
    rejected_attempt_id: str
    current_generation: int
    run_revision: str
    authority_digest: str
    pre_attempt_baseline: str
    landed_tree: str
    write_set_version: str
    admitted_paths: tuple[str, ...]
    verification_commands: tuple[str, ...]
    receipt_digest: str

    def __post_init__(self) -> None:
        for name in (
            "task_id",
            "batch_id",
            "rejected_attempt_id",
            "run_revision",
            "authority_digest",
            "pre_attempt_baseline",
            "landed_tree",
            "write_set_version",
            "receipt_digest",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.current_generation < 0:
            raise ValueError("current_generation must be non-negative")
        normalized = tuple(normalize_recovery_path(path) for path in self.admitted_paths)
        if len(set(normalized)) != len(normalized):
            raise ValueError("admitted_paths contains duplicates")
        object.__setattr__(self, "admitted_paths", normalized)
        if not self.verification_commands or any(
            not isinstance(command, str) or not command.strip()
            for command in self.verification_commands
        ):
            raise ValueError("verification_commands must be non-empty strings")

    @property
    def idempotency_key(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "batch_id": self.batch_id,
            "rejected_attempt_id": self.rejected_attempt_id,
            "current_generation": self.current_generation,
            "run_revision": self.run_revision,
            "authority_digest": self.authority_digest,
            "pre_attempt_baseline": self.pre_attempt_baseline,
            "landed_tree": self.landed_tree,
            "write_set_version": self.write_set_version,
            "admitted_paths": list(self.admitted_paths),
            "verification_commands": list(self.verification_commands),
            "receipt_digest": self.receipt_digest,
        }


def request_from_receipt(
    receipt: Mapping[str, Any],
    *,
    task_id: str,
    batch_id: str,
    current_generation: int,
    authority_digest: str,
) -> ScopeRecoveryRequest | None:
    results = receipt.get("test_results")
    amendment = results.get("scope_amendment") if isinstance(results, Mapping) else None
    if not isinstance(amendment, Mapping):
        return None
    return ScopeRecoveryRequest(
        task_id=task_id,
        batch_id=batch_id,
        rejected_attempt_id=str(receipt.get("subject_attempt") or ""),
        current_generation=current_generation,
        run_revision=str(receipt.get("plan_revision") or ""),
        authority_digest=authority_digest,
        pre_attempt_baseline=str(amendment.get("pre_attempt_baseline") or ""),
        landed_tree=str(receipt.get("tree_commit") or ""),
        write_set_version=str(amendment.get("write_set_version") or ""),
        admitted_paths=tuple(amendment.get("admitted_paths") or ()),
        verification_commands=tuple(amendment.get("verification_commands") or ()),
        receipt_digest=str(receipt.get("receipt_digest") or ""),
    )


def claim_successor_generation(
    plan_dir: Path,
    request: ScopeRecoveryRequest,
) -> dict[str, Any]:
    """CAS-claim exactly one no-body successor generation."""

    journal_path = plan_dir / "task_scope_recovery.json"
    lock_path = plan_dir / ".task_scope_recovery.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            journal = (
                read_json(journal_path)
                if journal_path.exists()
                else {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "claims": []}
            )
            claims = journal.get("claims")
            if not isinstance(claims, list):
                raise ScopeRecoveryConflict("scope recovery journal is malformed")
            for claim in claims:
                if not isinstance(claim, Mapping) or claim.get("task_id") != request.task_id:
                    continue
                if claim.get("idempotency_key") == request.idempotency_key:
                    return dict(claim)
                if claim.get("generation") == request.current_generation + 1:
                    raise ScopeRecoveryConflict(
                        f"task {request.task_id} generation {request.current_generation + 1} "
                        "already has a different successor claim"
                    )
            latest_generation = max(
                (
                    int(claim.get("generation", -1))
                    for claim in claims
                    if isinstance(claim, Mapping)
                    and claim.get("task_id") == request.task_id
                    and isinstance(claim.get("generation"), int)
                ),
                default=request.current_generation,
            )
            if latest_generation != request.current_generation:
                raise ScopeRecoveryConflict(
                    f"stale task generation: expected {request.current_generation}, "
                    f"actual {latest_generation}"
                )
            claim = {
                "claim_id": f"scope-successor:{request.idempotency_key}",
                "idempotency_key": request.idempotency_key,
                "task_id": request.task_id,
                "batch_id": request.batch_id,
                "generation": request.current_generation + 1,
                "rejected_attempt_id": request.rejected_attempt_id,
                "run_revision": request.run_revision,
                "authority_digest": request.authority_digest,
                "pre_attempt_baseline": request.pre_attempt_baseline,
                "landed_tree": request.landed_tree,
                "write_set_version": request.write_set_version,
                "admitted_paths": list(request.admitted_paths),
                "verification_commands": list(request.verification_commands),
                "receipt_digest": request.receipt_digest,
                "body_execution_allowed": False,
                "verification_only": True,
                "claimed_at": now_utc(),
            }
            claims.append(claim)
            atomic_write_json(journal_path, journal)
            return claim
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


__all__ = [
    "SCHEMA",
    "SCHEMA_VERSION",
    "ScopeRecoveryConflict",
    "ScopeRecoveryRequest",
    "claim_successor_generation",
    "normalize_recovery_path",
    "request_from_receipt",
]
