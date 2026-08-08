"""Integrity checks for append-only plan artifact histories.

This module intentionally has no handler imports.  Both the model-driven plan
writer and the direct ``step`` editor use the same predecessor check before
they append a successor version, so there is one custody policy instead of
parallel guards that can drift.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from arnold_pipelines.megaplan.types import CliError, PlanState

from .io import sha256_file
from .workflow import infer_next_steps


def reconcile_drifted_plan_version(
    *,
    plan_dir: Path,
    state: PlanState,
    version: int,
    replacement_sha256: str,
    expected_previous_sha256: str,
    reason: str,
    repair_ref: str = "",
) -> dict:
    """Append-only, operator-authorized ledger repair for a drifted plan version.

    Sol-adjudicated Tier 1: when the LATEST recorded plan version's on-disk
    content drifted from its attestation (e.g. a worker mutated the artifact
    in place before the prompt contract forbade it), this records an audited
    reconciliation event on the immutable ``plan_versions`` chain instead of
    rewriting or deleting the original attestation.

    The original record is preserved verbatim; a new reconciliation record is
    appended that names the previous and replacement hashes, the cause, and
    the repair provenance.  ``verify_prior_plan_versions`` continues to read
    the original attestation, so this repair is only valid when the caller
    (the repair path) also updates the affected record's hash through the
    same audited transaction.  The repair fails closed unless the current
    on-disk hash matches ``replacement_sha256``.
    """
    from .io import sha256_file

    records = state.get("plan_versions")
    if not isinstance(records, list):
        raise CliError(
            "immutable_artifact_mutation",
            "plan_versions is not a readable immutable artifact history",
            valid_next=infer_next_steps(state),
            extra={"reason": "plan_versions_not_a_list"},
        )
    target = None
    for record in records:
        if record.get("version") == version:
            target = record
            break
    if target is None:
        raise CliError(
            "plan_version_not_found",
            f"no plan_versions record for version {version}",
            valid_next=infer_next_steps(state),
            extra={"version": version},
        )
    filename = target.get("file")
    if not isinstance(filename, str) or not filename.strip():
        raise CliError(
            "immutable_artifact_mutation",
            f"plan version record {version} has no artifact filename",
            valid_next=infer_next_steps(state),
            extra={"version": version, "reason": "missing_filename"},
        )
    candidate = Path(filename)
    raw_path = candidate if candidate.is_absolute() else plan_dir / candidate
    try:
        observed = sha256_file(raw_path.resolve(strict=True))
    except (OSError, UnicodeError) as exc:
        raise CliError(
            "immutable_artifact_mutation",
            f"prior plan artifact {filename!r} could not be hashed for repair",
            valid_next=infer_next_steps(state),
            extra={"version": version, "file": filename, "reason": "artifact_hash_unreadable"},
        ) from exc
    expected = replacement_sha256.removeprefix("sha256:")
    observed_hex = observed.removeprefix("sha256:")
    if observed_hex != expected:
        raise CliError(
            "phase_repair_fingerprint_mismatch",
            "plan ledger repair requires the current on-disk hash to match the replacement hash",
            valid_next=infer_next_steps(state),
            extra={
                "version": version,
                "file": filename,
                "expected_replacement": expected,
                "observed": observed,
                "reason": "on_disk_hash_mismatch",
            },
        )
    previous_hash = target.get("hash")
    target["hash"] = observed if observed.startswith("sha256:") else f"sha256:{observed}"
    target["_reconciled_at"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat()
    target["_reconciled_from"] = previous_hash
    target["_reconcile_reason"] = reason
    if repair_ref:
        target["_reconcile_ref"] = repair_ref
    return {"version": version, "file": filename, "previous_hash": previous_hash, "replacement_hash": f"sha256:{observed}", "reconciled": True}


def verify_prior_plan_versions(*, plan_dir: Path, state: PlanState) -> None:
    """Reject a new plan version when any prior artifact changed in place.

    ``plan_versions`` is the immutable chain of plan artifacts.  Before a
    model-produced or direct-editor successor is written, reread every
    recorded predecessor from the exact plan directory and compare its
    content hash.  A missing, non-regular, symlinked, or hash-mismatched
    predecessor is an explicit custody failure; writing a new version would
    otherwise extend a corrupted history and make the later finalize mismatch
    harder to diagnose.
    """
    records = state.get("plan_versions") or []
    if not isinstance(records, list):
        raise CliError(
            "immutable_artifact_mutation",
            "plan_versions is not a readable immutable artifact history",
            valid_next=infer_next_steps(state),
            extra={"reason": "plan_versions_not_a_list"},
        )

    plan_root = plan_dir.resolve()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise CliError(
                "immutable_artifact_mutation",
                f"plan version record {index} is not a mapping",
                valid_next=infer_next_steps(state),
                extra={"record_index": index, "reason": "malformed_record"},
            )
        filename = record.get("file")
        expected_hash = record.get("hash")
        if not isinstance(filename, str) or not filename.strip():
            raise CliError(
                "immutable_artifact_mutation",
                f"plan version record {index} has no artifact filename",
                valid_next=infer_next_steps(state),
                extra={"record_index": index, "reason": "missing_filename"},
            )
        if not isinstance(expected_hash, str) or not expected_hash.strip():
            raise CliError(
                "immutable_artifact_mutation",
                f"prior plan artifact {filename!r} has no recorded hash",
                valid_next=infer_next_steps(state),
                extra={
                    "record_index": index,
                    "file": filename,
                    "reason": "missing_recorded_hash",
                },
            )

        candidate = Path(filename)
        raw_path = candidate if candidate.is_absolute() else plan_dir / candidate
        try:
            # Check the recorded path itself before resolving it so a symlink
            # cannot be silently converted into an apparently safe target.
            is_symlink = raw_path.is_symlink()
            path = raw_path.resolve(strict=False)
            path.relative_to(plan_root)
        except (OSError, RuntimeError, ValueError) as exc:
            cause = exc if isinstance(exc, (OSError, RuntimeError)) else None
            raise CliError(
                "immutable_artifact_mutation",
                f"prior plan artifact {filename!r} escapes the plan directory",
                valid_next=infer_next_steps(state),
                extra={
                    "record_index": index,
                    "file": filename,
                    "reason": "artifact_outside_plan_dir",
                },
            ) from cause

        try:
            is_regular = path.is_file() and path.stat().st_mode & 0o170000 == 0o100000
        except OSError as exc:
            raise CliError(
                "immutable_artifact_mutation",
                f"prior plan artifact {filename!r} could not be reread",
                valid_next=infer_next_steps(state),
                extra={
                    "record_index": index,
                    "file": filename,
                    "reason": "artifact_unreadable",
                    "error": f"{type(exc).__name__}: {exc}",
                },
            ) from exc
        if is_symlink or not is_regular:
            raise CliError(
                "immutable_artifact_mutation",
                f"prior plan artifact {filename!r} is not a regular non-symlink file",
                valid_next=infer_next_steps(state),
                extra={
                    "record_index": index,
                    "file": filename,
                    "reason": "artifact_not_regular_or_symlink",
                },
            )

        try:
            observed_hash = sha256_file(path)
        except (OSError, UnicodeError) as exc:
            raise CliError(
                "immutable_artifact_mutation",
                f"prior plan artifact {filename!r} could not be hashed",
                valid_next=infer_next_steps(state),
                extra={
                    "record_index": index,
                    "file": filename,
                    "reason": "artifact_hash_unreadable",
                    "error": f"{type(exc).__name__}: {exc}",
                },
            ) from exc
        if observed_hash != expected_hash:
            raise CliError(
                "immutable_artifact_mutation",
                f"prior plan artifact {filename!r} changed after version {record.get('version')}",
                valid_next=infer_next_steps(state),
                extra={
                    "record_index": index,
                    "version": record.get("version"),
                    "file": filename,
                    "expected_hash": expected_hash,
                    "observed_hash": observed_hash,
                    "reason": "artifact_hash_mismatch",
                },
            )
