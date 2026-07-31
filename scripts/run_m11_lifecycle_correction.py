#!/usr/bin/env python3
"""Admit and attest a verification-only M11 lifecycle correction subject."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Protocol

CANDIDATE_SCHEMA = "m11.lifecycle-correction-candidate.v1"
RECEIPT_SCHEMA = "m11.lifecycle-correction-plan-receipt.v1"
AGGREGATE_SCHEMA = "m11.cross_contract_acceptance.v1"


class LifecycleCorrectionError(ValueError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_digest(candidate: Mapping[str, Any]) -> str:
    return _digest({
        key: value for key, value in candidate.items()
        if key != "candidate_sha256"
    })


class LifecycleAPI(Protocol):
    def subject_exists(self, subject_id: str) -> bool: ...
    def admit_verification_subject(
        self, subject_id: str, idea: str
    ) -> Mapping[str, Any]: ...
    def committed_transactions(
        self, subject_id: str
    ) -> list[Mapping[str, Any]]: ...


class SupportedMegaplanLifecycle:
    """Adapter over the supported Megaplan CLI and acceptance-transaction API."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()

    def _plan_dir(self, subject_id: str) -> Path:
        return self.repo_root / ".megaplan" / "plans" / subject_id

    def subject_exists(self, subject_id: str) -> bool:
        return self._plan_dir(subject_id).is_dir()

    def admit_verification_subject(
        self, subject_id: str, idea: str
    ) -> Mapping[str, Any]:
        command = [
            sys.executable, "-P", "-m", "arnold_pipelines.megaplan",
            "init", "--name", subject_id,
            "--project-dir", str(self.repo_root),
            "--idea", idea,
            "--mode", "code",
        ]
        result = subprocess.run(
            command,
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise LifecycleCorrectionError(
                "supported_lifecycle_admission_failed:"
                + (result.stderr.strip() or result.stdout.strip())
            )
        return {
            "subject_id": subject_id,
            "plan_dir": str(self._plan_dir(subject_id)),
            "command_sha256": _digest(command),
        }

    def committed_transactions(
        self, subject_id: str
    ) -> list[Mapping[str, Any]]:
        from arnold_pipelines.megaplan.orchestration.completion_io import (
            list_committed_acceptance_transactions,
        )
        committed = list_committed_acceptance_transactions(
            self._plan_dir(subject_id)
        )
        return [
            transaction.to_dict()
            for _tx_id, transaction in sorted(committed.items())
        ]


def _git_state(repo_root: Path) -> tuple[str, str, bool]:
    def run(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), *args], text=True
        ).strip()
    return (
        run("rev-parse", "HEAD"),
        run("rev-parse", "HEAD^{tree}"),
        not bool(run("status", "--porcelain=v1", "--untracked-files=all")),
    )


def _load_binding(
    repo_root: Path, binding: Any, label: str
) -> tuple[dict[str, Any], str, str]:
    if not isinstance(binding, dict):
        raise LifecycleCorrectionError(f"{label}_binding_missing")
    raw_path, expected = binding.get("path"), binding.get("sha256")
    if not isinstance(raw_path, str) or not raw_path:
        raise LifecycleCorrectionError(f"{label}_path_missing")
    path = Path(raw_path)
    if not path.is_absolute():
        path = repo_root / path
    try:
        actual = _file_digest(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleCorrectionError(f"{label}_unreadable") from exc
    if actual != expected:
        raise LifecycleCorrectionError(f"{label}_digest_mismatch")
    if not isinstance(payload, dict):
        raise LifecycleCorrectionError(f"{label}_not_object")
    return payload, str(path.resolve()), actual


def _aggregate_complete(aggregate: Mapping[str, Any]) -> bool:
    if aggregate.get("schema") != AGGREGATE_SCHEMA:
        return False
    validations = aggregate.get("artifact_validation")
    debt = aggregate.get("debt_gate")
    summary = aggregate.get("summary")
    return (
        isinstance(validations, dict)
        and bool(validations)
        and all(
            isinstance(row, dict) and row.get("passed") is True
            for row in validations.values()
        )
        and isinstance(debt, dict)
        and debt.get("passed") is True
        and isinstance(summary, dict)
        and isinstance(summary.get("blockers", []), list)
        and all(
            isinstance(row, dict)
            and row.get("expected_class") == "forced_completion_guard"
            for row in summary.get("blockers", [])
        )
    )


def preflight(
    candidate: Mapping[str, Any],
    *,
    repo_root: Path,
    lifecycle: LifecycleAPI,
    require_fresh_subject: bool = True,
    git_state_reader=_git_state,
) -> dict[str, Any]:
    if candidate.get("schema") != CANDIDATE_SCHEMA:
        raise LifecycleCorrectionError("candidate_schema_invalid")
    if candidate.get("candidate_sha256") != candidate_digest(candidate):
        raise LifecycleCorrectionError("candidate_digest_mismatch")
    verifier = candidate.get("verifier_identity")
    producers = candidate.get("producer_identities")
    if not isinstance(verifier, str) or not verifier or not isinstance(producers, list):
        raise LifecycleCorrectionError("identity_set_invalid")
    if verifier in {str(value) for value in producers}:
        raise LifecycleCorrectionError("verifier_not_independent")
    commit, tree, clean = git_state_reader(repo_root)
    if not clean:
        raise LifecycleCorrectionError("candidate_tree_dirty")
    if commit != candidate.get("candidate_commit"):
        raise LifecycleCorrectionError("candidate_commit_mismatch")
    if tree != candidate.get("candidate_tree"):
        raise LifecycleCorrectionError("candidate_tree_mismatch")
    forced, forced_path, forced_sha = _load_binding(
        repo_root, candidate.get("forced_completion"), "forced_completion"
    )
    if not forced:
        raise LifecycleCorrectionError("forced_completion_empty")
    aggregate, aggregate_path, aggregate_sha = _load_binding(
        repo_root, candidate.get("aggregate"), "aggregate"
    )
    if not _aggregate_complete(aggregate):
        raise LifecycleCorrectionError("aggregate_incomplete")
    subject_id = (
        f"m11-lifecycle-correction-{forced_sha[7:19]}-{aggregate_sha[7:19]}"
    )
    if require_fresh_subject and lifecycle.subject_exists(subject_id):
        raise LifecycleCorrectionError("correction_subject_not_fresh")
    return {
        "ok": True,
        "verification_only": True,
        "subject_id": subject_id,
        "candidate_commit": commit,
        "candidate_tree": tree,
        "forced_completion_path": forced_path,
        "forced_completion_sha256": forced_sha,
        "aggregate_path": aggregate_path,
        "aggregate_sha256": aggregate_sha,
        "verifier_identity": verifier,
        "runtime_identity_sha256": candidate.get("runtime_identity_sha256"),
    }


def admit(
    candidate: Mapping[str, Any],
    *,
    repo_root: Path,
    lifecycle: LifecycleAPI,
    dry_run: bool,
    git_state_reader=_git_state,
) -> dict[str, Any]:
    check = preflight(
        candidate,
        repo_root=repo_root,
        lifecycle=lifecycle,
        git_state_reader=git_state_reader,
    )
    if dry_run:
        return {"status": "preflight_passed", **check}
    idea = "\n".join([
        "M11 lifecycle correction — verification only",
        "",
        "This subject may verify and attest existing acceptance evidence only.",
        "It must not implement, repair, deploy, or directly edit plan state/finalize JSON.",
        f"Preserved forced completion: {check['forced_completion_path']}",
        f"Forced completion SHA-256: {check['forced_completion_sha256']}",
        f"Aggregate SHA-256: {check['aggregate_sha256']}",
        f"Candidate commit: {check['candidate_commit']}",
        f"Independent verifier: {check['verifier_identity']}",
    ])
    admission = lifecycle.admit_verification_subject(
        check["subject_id"], idea
    )
    return {"status": "admitted", **check, "admission": dict(admission)}


def emit_receipt(
    candidate: Mapping[str, Any],
    *,
    repo_root: Path,
    lifecycle: LifecycleAPI,
    git_state_reader=_git_state,
) -> dict[str, Any]:
    check = preflight(
        candidate,
        repo_root=repo_root,
        lifecycle=lifecycle,
        require_fresh_subject=False,
        git_state_reader=git_state_reader,
    )
    if not lifecycle.subject_exists(check["subject_id"]):
        raise LifecycleCorrectionError("correction_subject_not_admitted")
    accepted = [
        dict(tx) for tx in lifecycle.committed_transactions(check["subject_id"])
        if tx.get("accepted") is True
        and tx.get("snapshot_hash") == check["aggregate_sha256"]
        and tx.get("tested_commit_ref") == check["candidate_commit"]
        and tx.get("tested_runtime_identity") == check["runtime_identity_sha256"]
        and tx.get("mode") in {"atomic", "enforce"}
    ]
    if len(accepted) != 1:
        raise LifecycleCorrectionError("authoritative_accepted_transaction_missing_or_ambiguous")
    transaction = accepted[0]
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "decision": "accepted",
        "fresh": True,
        "verification_only": True,
        "subject_id": check["subject_id"],
        "forced_completion_sha256": check["forced_completion_sha256"],
        "aggregate_sha256": check["aggregate_sha256"],
        "candidate_commit": check["candidate_commit"],
        "candidate_tree": check["candidate_tree"],
        "accepted_by": check["verifier_identity"],
        "acceptance_transaction_id": transaction.get("transaction_id"),
        "acceptance_transaction_sha256": _digest(transaction),
    }
    receipt["content_sha256"] = _digest(receipt)
    return receipt


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path = path.resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--admit", action="store_true")
    action.add_argument("--emit-receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        if not isinstance(candidate, dict):
            raise LifecycleCorrectionError("candidate_not_object")
        lifecycle = SupportedMegaplanLifecycle(args.repo_root)
        if args.emit_receipt:
            result = emit_receipt(
                candidate, repo_root=args.repo_root, lifecycle=lifecycle
            )
            _write_atomic(args.emit_receipt, result)
        else:
            result = admit(
                candidate,
                repo_root=args.repo_root,
                lifecycle=lifecycle,
                dry_run=args.dry_run,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
    except (OSError, json.JSONDecodeError, LifecycleCorrectionError) as exc:
        parser.exit(2, f"lifecycle correction rejected: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
