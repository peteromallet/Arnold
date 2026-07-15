"""Atomic read/write of ``completion_verdict.json`` in the plan dir and
content-addressed acceptance snapshot storage with commit/replay lifecycle.

Reuses the project's ``atomic_write_json`` (write .tmp → fsync → rename) so a
partially-written verdict is never observed. Read is fail-soft: a missing or
corrupt file returns ``None``.

Acceptance snapshots are stored as immutable content-addressed artifacts under
``<plan_dir>/_acceptance/snapshots/<hash[:2]>/<hash>.json``.  Acceptance
transactions follow a prepare → commit lifecycle with an explicit commit
marker file so recovery can distinguish committed transactions from
uncommitted candidates.

* On **recovery**, transactions with a commit marker are promoted to
  committed; transactions without a commit marker are discarded.
* **Snapshots** are never modified in-place — content-addressing makes them
  idempotent on re-store and safe for concurrent readers.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.orchestration.completion_contract import CompletionVerdict

log = logging.getLogger("arnold_pipelines.megaplan.orchestration.completion_io")

COMPLETION_VERDICT_FILENAME = "completion_verdict.json"

# ---------------------------------------------------------------------------
# Acceptance artifact layout
# ---------------------------------------------------------------------------

_ACCEPTANCE_DIRNAME = "_acceptance"
_SNAPSHOTS_DIRNAME = "snapshots"
_TRANSACTIONS_DIRNAME = "transactions"

_TX_PREPARE_RE = re.compile(r"^(.+)\.prepare\.json$")
_TX_COMMITTED_RE = re.compile(r"^(.+)\.json$")


def _acceptance_root(plan_dir: Path) -> Path:
    """Return the ``_acceptance/`` directory under *plan_dir*."""
    return plan_dir / _ACCEPTANCE_DIRNAME


def _snapshot_dir(plan_dir: Path) -> Path:
    """Return ``_acceptance/snapshots/`` directory."""
    return _acceptance_root(plan_dir) / _SNAPSHOTS_DIRNAME


def _transaction_dir(plan_dir: Path) -> Path:
    """Return ``_acceptance/transactions/`` directory."""
    return _acceptance_root(plan_dir) / _TRANSACTIONS_DIRNAME


def _snapshot_hex(content_hash: str) -> str:
    """Extract the raw hex digest from a ``sha256:...`` content hash."""
    return content_hash.split(":", 1)[1] if ":" in content_hash else content_hash


def _snapshot_path(plan_dir: Path, content_hash: str) -> Path:
    """Return the content-addressed path for a snapshot.

    Layout: ``_acceptance/snapshots/<first-two-hex>/<full-hex>.json``
    """
    hex_digest = _snapshot_hex(content_hash)
    return _snapshot_dir(plan_dir) / hex_digest[:2] / f"{hex_digest}.json"


def _tx_prepare_path(plan_dir: Path, tx_id: str) -> Path:
    """Return the staging path for a candidate transaction."""
    return _transaction_dir(plan_dir) / f"{tx_id}.prepare.json"


def _tx_commit_marker_path(plan_dir: Path, tx_id: str) -> Path:
    """Return the commit marker path for a transaction."""
    return _transaction_dir(plan_dir) / f"{tx_id}.commit"


def _tx_committed_path(plan_dir: Path, tx_id: str) -> Path:
    """Return the committed transaction path."""
    return _transaction_dir(plan_dir) / f"{tx_id}.json"


# ---------------------------------------------------------------------------
# Completion verdict (unchanged API)
# ---------------------------------------------------------------------------


def write_completion_verdict(plan_dir: Path, verdict: CompletionVerdict) -> Path:
    """Atomically write *verdict* to ``<plan_dir>/completion_verdict.json``.

    Returns the path written. Raises only if the underlying atomic write fails;
    callers in shadow mode wrap this in try/except (fail-open).
    """
    from arnold_pipelines.megaplan._core.io import atomic_write_json

    path = plan_dir / COMPLETION_VERDICT_FILENAME
    atomic_write_json(path, verdict.to_dict())
    return path


def read_completion_verdict(plan_dir: Path) -> dict | None:
    """Read the raw verdict dict, or ``None`` if absent/corrupt."""
    path = plan_dir / COMPLETION_VERDICT_FILENAME
    try:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.debug("could not read %s: %s", path, exc)
        return None


def read_typed_completion_verdict(plan_dir: Path) -> CompletionVerdict | None:
    """Read and deserialize a verdict, or ``None`` if absent/corrupt/untyped."""
    payload = read_completion_verdict(plan_dir)
    if not isinstance(payload, dict):
        return None
    try:
        return CompletionVerdict.from_dict(payload)
    except Exception as exc:
        log.debug("could not deserialize typed verdict in %s: %s", plan_dir, exc)
        return None


# ---------------------------------------------------------------------------
# Acceptance snapshot storage — immutable, content-addressed
# ---------------------------------------------------------------------------


def store_acceptance_snapshot(plan_dir: Path, snapshot: Any) -> Path:
    """Store an :class:`AcceptanceSnapshot` as an immutable content-addressed file.

    The snapshot is serialized once and written to
    ``_acceptance/snapshots/<hash[:2]>/<hash>.json``.  If a snapshot with the
    same content hash already exists on disk, the write is skipped
    (idempotent).

    Returns the path to the stored snapshot file.
    """
    from arnold_pipelines.megaplan._core.io import atomic_write_json

    path = _snapshot_path(plan_dir, snapshot.content_hash)
    if not path.exists():
        atomic_write_json(path, snapshot.to_dict())
    return path


def load_acceptance_snapshot(
    plan_dir: Path,
    content_hash: str,
) -> Any | None:
    """Load a snapshot by its content hash.

    Returns ``None`` when no snapshot exists at the expected content-addressed
    path or when the stored content hash does not match the expected hash.
    """
    from arnold_pipelines.megaplan._core.io import read_json

    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        AcceptanceSnapshot,
    )

    path = _snapshot_path(plan_dir, content_hash)
    if not path.is_file():
        return None
    try:
        payload = read_json(path)
        if not isinstance(payload, dict):
            return None
        snapshot = AcceptanceSnapshot.from_dict(payload)
        # Verify the content hash matches to detect tampering.
        if snapshot.content_hash != content_hash:
            log.warning(
                "acceptance snapshot at %s has hash %s, expected %s — "
                "treating as absent",
                path, snapshot.content_hash, content_hash,
            )
            return None
        return snapshot
    except (ValueError, TypeError, OSError) as exc:
        log.debug("could not load acceptance snapshot from %s: %s", path, exc)
        return None


def snapshot_exists(plan_dir: Path, content_hash: str) -> bool:
    """Return ``True`` when a snapshot with the given hash exists on disk."""
    return _snapshot_path(plan_dir, content_hash).is_file()


# ---------------------------------------------------------------------------
# Acceptance transaction lifecycle — prepare, commit, discard, replay
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AcceptanceReplayResult:
    """Outcome of replaying acceptance transactions from disk.

    ``committed`` maps transaction IDs to their :class:`AcceptanceTransaction`
    records.  ``discarded`` lists transaction IDs whose prepare files existed
    without a commit marker (candidates that were never committed).
    """

    committed: dict[str, Any]  # str → AcceptanceTransaction
    discarded: tuple[str, ...]


def prepare_acceptance_transaction(
    plan_dir: Path,
    transaction: Any,
) -> Path:
    """Stage an acceptance transaction as a candidate (not yet committed).

    Writes the transaction to ``_acceptance/transactions/<tx_id>.prepare.json``.
    The transaction is *not* considered committed until
    :func:`commit_acceptance_transaction` is called.

    Returns the path to the prepare file.
    """
    from arnold_pipelines.megaplan._core.io import atomic_write_json

    prepare_path = _tx_prepare_path(plan_dir, transaction.transaction_id)
    atomic_write_json(prepare_path, transaction.to_dict())
    return prepare_path


def commit_acceptance_transaction(plan_dir: Path, tx_id: str) -> Path | None:
    """Commit a previously prepared acceptance transaction.

    1. Reads the prepare file.
    2. Writes the committed transaction JSON.
    3. Writes an empty commit marker file (``<tx_id>.commit``).
    4. Removes the prepare file.

    Returns the path to the committed transaction file, or ``None`` when no
    prepare file exists for *tx_id*.
    """
    from arnold_pipelines.megaplan._core.io import (
        _write_bytes_direct,
        atomic_write_json,
        read_json,
    )

    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        AcceptanceTransaction,
    )

    prepare_path = _tx_prepare_path(plan_dir, tx_id)
    if not prepare_path.is_file():
        log.debug("commit_acceptance_transaction: no prepare file at %s", prepare_path)
        return None

    payload = read_json(prepare_path)
    if not isinstance(payload, dict):
        prepare_path.unlink()
        return None

    transaction = AcceptanceTransaction.from_dict(payload)
    committed_path = _tx_committed_path(plan_dir, tx_id)
    atomic_write_json(committed_path, transaction.to_dict())

    marker_path = _tx_commit_marker_path(plan_dir, tx_id)
    _write_bytes_direct(marker_path, b"")

    if prepare_path.exists():
        prepare_path.unlink()

    return committed_path


def discard_uncommitted_acceptance_transaction(plan_dir: Path, tx_id: str) -> None:
    """Remove a candidate acceptance transaction (prepare file and any stale
    commit marker) without promoting it to committed.

    Safe to call when no prepare file exists (no-op).
    """
    prepare_path = _tx_prepare_path(plan_dir, tx_id)
    if prepare_path.exists():
        prepare_path.unlink()

    marker_path = _tx_commit_marker_path(plan_dir, tx_id)
    if marker_path.exists():
        marker_path.unlink()


def replay_acceptance_transactions(plan_dir: Path) -> AcceptanceReplayResult:
    """Replay all acceptance transactions found on disk.

    For each prepare file under ``_acceptance/transactions/``:

    * If a commit marker exists → promote to committed (replay).
    * If no commit marker exists → discard (candidate was never committed).

    After replay, all committed transactions are loaded and returned.

    This is the key recovery primitive that ensures only committed
    transactions survive while uncommitted candidates are discarded.
    """
    from arnold_pipelines.megaplan._core.io import read_json

    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        AcceptanceTransaction,
    )

    tx_dir = _transaction_dir(plan_dir)
    committed: dict[str, Any] = {}
    discarded: list[str] = []

    if not tx_dir.is_dir():
        return AcceptanceReplayResult(committed=committed, discarded=tuple(discarded))

    # Phase 1: Replay or discard each prepare file.
    for prepare_path in sorted(tx_dir.glob("*.prepare.json")):
        match = _TX_PREPARE_RE.match(prepare_path.name)
        if match is None:
            continue
        tx_id = match.group(1)
        marker_path = _tx_commit_marker_path(plan_dir, tx_id)
        if marker_path.exists():
            # Commit marker exists — promote to committed.
            commit_acceptance_transaction(plan_dir, tx_id)
        else:
            # No commit marker — candidate was never committed.
            discard_uncommitted_acceptance_transaction(plan_dir, tx_id)
            discarded.append(tx_id)

    # Phase 2: Clean up orphaned commit markers (no corresponding prepare).
    for marker_path in sorted(tx_dir.glob("*.commit")):
        match = re.fullmatch(r"^(.+)\.commit$", marker_path.name)
        if match is None:
            continue
        tx_id = match.group(1)
        if not _tx_prepare_path(plan_dir, tx_id).exists() and not _tx_committed_path(plan_dir, tx_id).exists():
            marker_path.unlink()

    # Phase 3: Load all committed transactions.
    for tx_path in sorted(tx_dir.glob("*.json")):
        match = _TX_COMMITTED_RE.match(tx_path.name)
        if match is None:
            continue
        # Skip prepare files that weren't cleaned up.
        if tx_path.name.endswith(".prepare.json"):
            continue
        tx_id = match.group(1)
        try:
            payload = read_json(tx_path)
            if not isinstance(payload, dict):
                continue
            transaction = AcceptanceTransaction.from_dict(payload)
            committed[tx_id] = transaction
        except (ValueError, TypeError, OSError) as exc:
            log.debug("could not load committed transaction %s: %s", tx_id, exc)

    return AcceptanceReplayResult(committed=committed, discarded=tuple(discarded))


def list_committed_acceptance_transactions(
    plan_dir: Path,
) -> dict[str, Any]:
    """Load all committed acceptance transactions (no replay, read-only).

    Unlike :func:`replay_acceptance_transactions`, this does not touch prepare
    files or commit markers — it only reads already-committed transaction JSON
    files.
    """
    from arnold_pipelines.megaplan._core.io import read_json

    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        AcceptanceTransaction,
    )

    tx_dir = _transaction_dir(plan_dir)
    committed: dict[str, Any] = {}

    if not tx_dir.is_dir():
        return committed

    for tx_path in sorted(tx_dir.glob("*.json")):
        match = _TX_COMMITTED_RE.match(tx_path.name)
        if match is None:
            continue
        if tx_path.name.endswith(".prepare.json"):
            continue
        tx_id = match.group(1)
        try:
            payload = read_json(tx_path)
            if not isinstance(payload, dict):
                continue
            transaction = AcceptanceTransaction.from_dict(payload)
            committed[tx_id] = transaction
        except (ValueError, TypeError, OSError) as exc:
            log.debug("could not load committed transaction %s: %s", tx_id, exc)

    return committed


def list_uncommitted_acceptance_candidates(
    plan_dir: Path,
) -> dict[str, Any]:
    """Load all uncommitted candidate acceptance transactions (prepare files only).

    Returns a dict mapping transaction_id → AcceptanceTransaction for every
    prepare file whose corresponding commit marker does NOT exist.  Only
    transactions that were staged via :func:`prepare_acceptance_transaction`
    but never committed are returned.

    This is the authoritative read for candidate invalidation: any transaction
    that appears here is a candidate that has not yet been committed.
    """
    from arnold_pipelines.megaplan._core.io import read_json

    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        AcceptanceTransaction,
    )

    tx_dir = _transaction_dir(plan_dir)
    candidates: dict[str, Any] = {}

    if not tx_dir.is_dir():
        return candidates

    for prepare_path in sorted(tx_dir.glob("*.prepare.json")):
        match = _TX_PREPARE_RE.match(prepare_path.name)
        if match is None:
            continue
        tx_id = match.group(1)
        # A transaction is only "uncommitted" (candidate) when no commit marker exists.
        marker_path = _tx_commit_marker_path(plan_dir, tx_id)
        if marker_path.exists():
            continue
        try:
            payload = read_json(prepare_path)
            if not isinstance(payload, dict):
                continue
            transaction = AcceptanceTransaction.from_dict(payload)
            candidates[tx_id] = transaction
        except (ValueError, TypeError, OSError) as exc:
            log.debug("could not load uncommitted candidate %s: %s", tx_id, exc)

    return candidates


def load_acceptance_transaction_by_id(
    plan_dir: Path,
    tx_id: str,
) -> Any | None:
    """Load a single committed acceptance transaction by its id.

    Returns ``None`` when the transaction does not exist or cannot be
    deserialized.
    """
    from arnold_pipelines.megaplan._core.io import read_json

    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        AcceptanceTransaction,
    )

    path = _tx_committed_path(plan_dir, tx_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return AcceptanceTransaction.from_dict(payload)


# ---------------------------------------------------------------------------
# Atomic acceptance commit (CAS-backed journal transaction)
# ---------------------------------------------------------------------------
#
# ``prepare_acceptance_commit`` stages everything needed to make a milestone
# completion durable as ONE journal transaction:
#
#   1. the immutable content-addressed snapshot reference,
#   2. the committed acceptance transaction file,
#   3. the ``completed`` record (carrying the acceptance receipt),
#   4. the advanced cursor (``current_milestone_index``), and
#   5. the milestone-boundary evidence.
#
# Nothing is promoted to durable state until :func:`commit_acceptance_commit`
# runs, which evaluates the CAS guard on the chain state file.  A concurrent
# mutation of the state file (or any other CAS violation) leaves the prior
# chain state completely unchanged (fail-closed).  ``discard_acceptance_commit``
# removes the staged prepare without touching durable state.
#
# The fail-closed boundary is strict: a non-accepted boundary result, or one
# whose commit/runtime identity was not validated by the boundary runner, can
# never be staged at all.


@dataclass(frozen=True)
class AcceptanceCommitPlan:
    """A staged atomic acceptance commit described by one CAS journal transaction.

    All durable effects of a milestone completion are captured here and applied
    together by :func:`commit_acceptance_commit` via a single journal commit
    marker plus a CAS guard on the chain state file.
    """

    tx_id: str
    journal_root: Path
    prepare_path: Path
    state_path: Path
    prior_state_sha256: "str | None"
    new_state: dict
    transaction_payload: dict
    snapshot_payload: dict
    snapshot_path: Path
    committed_tx_path: Path
    writes: tuple
    milestone_label: str
    milestone_index: int
    receipt_payload: dict

    def to_audit_dict(self) -> dict:
        """Return a serializable audit view of the staged plan (no secrets)."""
        return {
            "tx_id": self.tx_id,
            "journal_root": str(self.journal_root),
            "prepare_path": str(self.prepare_path),
            "state_path": str(self.state_path),
            "prior_state_sha256": self.prior_state_sha256,
            "milestone_label": self.milestone_label,
            "milestone_index": self.milestone_index,
            "snapshot_path": str(self.snapshot_path),
            "committed_tx_path": str(self.committed_tx_path),
            "has_receipt": bool(self.receipt_payload),
            "write_count": len(self.writes),
            "cas_guarded": any(
                isinstance(w, dict) and w.get("expected_prior_sha256")
                for w in self.writes
            ),
        }


def _state_sha256_for_cas(path: Path) -> "str | None":
    """Return the sha256 of the current bytes at *path*, or ``None`` if absent.

    Used to seed the CAS guard on the chain state file.  A missing state file
    yields ``None`` (no prior hash), which the journal treats as
    ``target_absent``-compatible rather than as a pinned value.

    The returned hash carries the ``sha256:`` prefix to match the canonical
    format used by :func:`arnold_pipelines.megaplan._core.io._path_sha256`
    (which :func:`evaluate_cas_guards` uses to compute the actual value for the
    CAS comparison).  A bare hex digest would never compare equal.
    """
    try:
        import hashlib

        raw = path.read_bytes()
    except OSError:
        return None
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def prepare_acceptance_commit(
    plan_dir: Path,
    spec_path: Path,
    result: Any,
    state: Any,
    *,
    milestone_index: "int | None" = None,
    contract_id: str = "",
    contract_boundary_id: str = "",
    commit_ref: "str | None" = None,
    tip_ref: "str | None" = None,
    branch_head: "str | None" = None,
    pr_head: "str | None" = None,
    pr_number: "int | None" = None,
    pr_state: "str | None" = None,
    expected_prior_state_sha256: "str | None" = None,
    tx_id: "str | None" = None,
) -> AcceptanceCommitPlan:
    """Stage an atomic acceptance commit as one CAS-backed journal transaction.

    Parameters mirror the durable evidence required for a milestone completion:

    * ``result``  - an accepted :class:`AcceptanceBoundaryResult`.
    * ``state``   - the current :class:`ChainState` (read-only; not mutated).
    * ``spec_path``- resolves the chain state file path and journal root.
    * ``expected_prior_state_sha256`` - optional explicit CAS prior hash for
      the chain state file.  When omitted, the current on-disk state file is
      hashed to seed the guard.

    Raises :class:`ValueError` for any fail-closed precondition violation
    (non-accepted boundary, unbound identity, or missing milestone identity).
    """
    from arnold_pipelines.megaplan._core import io as journal_io
    from arnold_pipelines.megaplan.chain import spec as chain_spec
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        AcceptanceReceipt,
        AcceptanceTransaction,
    )

    # --- Fail-closed precondition gates -----------------------------------
    if result is None:
        raise ValueError("cannot stage acceptance commit: boundary result is None")
    snapshot = getattr(result, "snapshot", None)
    if snapshot is None:
        raise ValueError("cannot stage acceptance commit: missing acceptance snapshot")
    accepted = getattr(result, "accepted", False)
    if not accepted:
        raise ValueError(
            "cannot stage acceptance commit: boundary result was not accepted "
            "(fail-closed: never commit unaccepted acceptance evidence)"
        )
    identity_valid = getattr(result, "identity_valid", False)
    if not identity_valid:
        raise ValueError(
            "cannot stage acceptance commit: commit/runtime identity was not "
            "validated by the acceptance boundary (fail-closed: unbound identity)"
        )
    source_commit_ref = getattr(snapshot, "source_commit_ref", None)
    runtime_identity = getattr(snapshot, "runtime_identity", None)
    if not source_commit_ref or not runtime_identity:
        raise ValueError(
            "cannot stage acceptance commit: snapshot source_commit_ref/"
            "runtime_identity are not bound"
        )

    milestone_label = getattr(snapshot, "milestone_label", "") or ""
    plan_name = getattr(snapshot, "plan_name", "") or ""
    snap_milestone_index = getattr(snapshot, "milestone_index", None)
    if milestone_index is None:
        milestone_index = snap_milestone_index if snap_milestone_index is not None else -1

    if not milestone_label:
        raise ValueError("cannot stage acceptance commit: snapshot has no milestone_label")

    # --- Resolve paths ----------------------------------------------------
    state_path = chain_spec._state_path_for(Path(spec_path))
    state_root = state_path.parent
    journal_base = state_root  # journal funcs derive ``<root>/_journal``
    plan_dir = Path(plan_dir)

    if tx_id is None:
        tx_id = f"{getattr(snapshot, 'transaction_id', '') or 'acceptance'}-commit"

    # --- Build the immutable content-addressed snapshot + transaction ------
    snapshot_path = _snapshot_path(plan_dir, snapshot.content_hash)
    snapshot_payload = snapshot.to_dict()

    receipt = AcceptanceReceipt(
        transaction_id=getattr(snapshot, "transaction_id", "") or "",
        snapshot_hash=snapshot.content_hash,
        milestone_label=milestone_label,
        milestone_index=milestone_index,
        plan_name=plan_name,
    )
    receipt_payload = receipt.to_dict()

    transaction = AcceptanceTransaction(
        transaction_id=getattr(snapshot, "transaction_id", "") or "",
        snapshot_hash=snapshot.content_hash,
        accepted=True,
        mode=getattr(result, "mode", "") or "",
        tested_commit_ref=source_commit_ref,
        tested_runtime_identity=runtime_identity,
        verdict_ref=None,
        failure_reasons=tuple(getattr(result, "failure_reasons", []) or []),
        completed_at=getattr(result, "completed_at", None),
    )
    transaction_payload = transaction.to_dict()

    committed_tx_path = _tx_committed_path(plan_dir, tx_id)

    # --- Build the new chain state (completed record + cursor + evidence) --
    from arnold_pipelines.megaplan.chain.spec import MilestoneBoundaryEvidence

    new_state = dict(state.to_dict())
    # deep-ish copies of the mutable containers so the source state is untouched
    completed_list = [dict(r) if isinstance(r, dict) else r for r in new_state.get("completed", [])]
    evidence_map = dict(new_state.get("milestone_boundary_evidence") or {})
    # remove any prior completed record for this label so the receipt attaches cleanly
    completed_list = [r for r in completed_list if not (isinstance(r, dict) and r.get("label") == milestone_label)]

    completed_record = {
        "label": milestone_label,
        "plan": plan_name,
        "milestone_index": milestone_index,
        "transaction_id": getattr(snapshot, "transaction_id", "") or "",
        "snapshot_hash": snapshot.content_hash,
        "source_commit_ref": source_commit_ref,
        "runtime_identity": runtime_identity,
        "completed_at": getattr(result, "completed_at", None),
        "acceptance_receipt": dict(receipt_payload),
    }
    completed_list.append(completed_record)

    evidence = MilestoneBoundaryEvidence(
        milestone_label=milestone_label,
        milestone_index=milestone_index,
        plan_name=plan_name,
        contract_id=contract_id,
        contract_boundary_id=contract_boundary_id,
        state_snapshot_ref=snapshot.content_hash,
        commit_ref=commit_ref,
        tip_ref=tip_ref,
        branch_head=branch_head,
        pr_head=pr_head,
        pr_number=pr_number,
        pr_state=pr_state,
    )
    evidence_map[milestone_label] = evidence.to_dict()

    new_state["completed"] = completed_list
    new_state["milestone_boundary_evidence"] = evidence_map
    # cursor advance: never move the cursor backwards (idempotent on re-stage)
    prior_index = int(new_state.get("current_milestone_index", -1))
    new_state["current_milestone_index"] = max(prior_index, int(milestone_index))

    new_state_text = json.dumps(new_state, sort_keys=True, indent=2, separators=(",", ": "))

    # --- CAS prior hash for the state file --------------------------------
    if expected_prior_state_sha256 is not None:
        prior_state_sha256 = expected_prior_state_sha256
    else:
        prior_state_sha256 = _state_sha256_for_cas(state_path)

    # --- Stage every write in ONE journal transaction ---------------------
    writes: list = []
    # 1. chain state file -- the critical CAS-guarded mutation
    writes.append(
        journal_io.journal_text_write(
            state_path,
            new_state_text,
            tx_id=tx_id,
        )
    )
    # attach the CAS guard to the state-file entry only
    writes[-1] = dict(writes[-1])
    if prior_state_sha256 is not None:
        writes[-1]["expected_prior_sha256"] = prior_state_sha256
    else:
        # state file must be absent -> target_absent enforces no concurrent creation
        writes[-1]["target_absent"] = True

    # 2. committed acceptance transaction file (marks tx committed on apply)
    writes.append(
        journal_io.journal_text_write(
            committed_tx_path,
            json.dumps(transaction_payload, sort_keys=True, indent=2, separators=(",", ": ")),
            tx_id=tx_id,
        )
    )
    # 3. immutable content-addressed snapshot (idempotent; part of the tx)
    writes.append(
        journal_io.journal_text_write(
            snapshot_path,
            json.dumps(snapshot_payload, sort_keys=True, indent=2, separators=(",", ": ")),
            tx_id=tx_id,
        )
    )

    prepare_path = journal_io.prepare_journal_transaction(
        journal_base,
        tx_id,
        writes=tuple(writes),
    )

    return AcceptanceCommitPlan(
        tx_id=tx_id,
        journal_root=journal_base,
        prepare_path=prepare_path,
        state_path=state_path,
        prior_state_sha256=prior_state_sha256,
        new_state=new_state,
        transaction_payload=transaction_payload,
        snapshot_payload=snapshot_payload,
        snapshot_path=snapshot_path,
        committed_tx_path=committed_tx_path,
        writes=tuple(writes),
        milestone_label=milestone_label,
        milestone_index=int(milestone_index),
        receipt_payload=dict(receipt_payload),
    )


def commit_acceptance_commit(plan: AcceptanceCommitPlan) -> Any:
    """Durably apply a staged acceptance commit via the CAS journal.

    Runs :func:`commit_journal_transaction_cas`.  On any CAS violation the
    prepared transaction is discarded by the journal and the prior chain state
    is left completely unchanged (fail-closed).  Returns the
    :class:`JournalCASResult`.
    """
    from arnold_pipelines.megaplan._core import io as journal_io

    return journal_io.commit_journal_transaction_cas(plan.journal_root, plan.tx_id)


def discard_acceptance_commit(plan: AcceptanceCommitPlan) -> None:
    """Discard a staged acceptance commit without touching durable state.

    Removes the journal prepare entry *and* any staged temp/blob files for the
    transaction via :func:`discard_uncommitted_journal_transaction`, which also
    fsyncs the journal directory.  Safe to call after a CAS failure (the journal
    already discards on violation) or when aborting an uncommitted plan.
    """
    from arnold_pipelines.megaplan._core import io as journal_io

    journal_io.discard_uncommitted_journal_transaction(plan.journal_root, plan.tx_id)


def replay_acceptance_commit_journal(journal_root: Path) -> dict:
    """Recover the acceptance-commit journal, promoting committed txs only.

    Thin wrapper over :func:`recover_journal` that returns the recovery summary.
    Committed transactions are applied; uncommitted (prepare-only) plans are
    discarded so a torn commit never exposes completed/successor-ready state.
    """
    from arnold_pipelines.megaplan._core import io as journal_io

    return journal_io.recover_journal(Path(journal_root))
