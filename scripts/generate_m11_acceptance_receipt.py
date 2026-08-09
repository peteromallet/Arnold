#!/usr/bin/env python3
"""Generate an independent, correction-bound M11 acceptance receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

CANDIDATE_SCHEMA = "m11.acceptance-candidate.v1"
RECEIPT_SCHEMA = "m11.acceptance-receipt.v1"
CORRECTION_SCHEMA = "m11.lifecycle-correction-plan-receipt.v1"
PROOF_MAP_SCHEMA = "arnold.megaplan.proof_map.v1"
EVIDENCE_NAMES = (
    "full_suite", "no_debt", "runtime", "audit", "genuine_block",
    "recovery", "route", "wbc",
)


class AcceptanceReceiptError(ValueError):
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


def _load_bound_json(
    repo_root: Path, binding: Any, label: str
) -> tuple[dict[str, Any], str, str]:
    if not isinstance(binding, dict):
        raise AcceptanceReceiptError(f"{label}_binding_missing")
    relative = binding.get("path")
    expected = binding.get("sha256")
    if not isinstance(relative, str) or not relative:
        raise AcceptanceReceiptError(f"{label}_path_missing")
    path = Path(relative)
    if not path.is_absolute():
        path = repo_root / path
    try:
        actual = _file_digest(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcceptanceReceiptError(f"{label}_unreadable") from exc
    if actual != expected:
        raise AcceptanceReceiptError(f"{label}_digest_mismatch")
    if not isinstance(payload, dict):
        raise AcceptanceReceiptError(f"{label}_not_object")
    return payload, str(path.resolve()), actual


def _git_state(repo_root: Path) -> tuple[str, str, bool]:
    def run(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(repo_root), *args], text=True
        ).strip()
    commit = run("rev-parse", "HEAD")
    tree = run("rev-parse", "HEAD^{tree}")
    clean = not run("status", "--porcelain=v1", "--untracked-files=all")
    return commit, tree, clean


def _aggregate_complete(payload: Mapping[str, Any]) -> bool:
    if payload.get("schema") != "m11.cross_contract_acceptance.v1":
        return False
    validations = payload.get("artifact_validation")
    if not isinstance(validations, dict) or not validations:
        return False
    if any(
        not isinstance(row, dict) or row.get("passed") is not True
        for row in validations.values()
    ):
        return False
    debt = payload.get("debt_gate")
    if not isinstance(debt, dict) or debt.get("passed") is not True:
        return False
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return False
    blockers = summary.get("blockers", [])
    return isinstance(blockers, list) and all(
        isinstance(row, dict)
        and row.get("expected_class") == "forced_completion_guard"
        for row in blockers
    )


def build_acceptance_receipt(
    candidate: Mapping[str, Any],
    *,
    repo_root: Path,
    git_state_reader: Callable[[Path], tuple[str, str, bool]] = _git_state,
) -> dict[str, Any]:
    if candidate.get("schema") != CANDIDATE_SCHEMA:
        raise AcceptanceReceiptError("candidate_schema_invalid")
    if candidate.get("candidate_sha256") != candidate_digest(candidate):
        raise AcceptanceReceiptError("candidate_digest_mismatch")
    if candidate.get("decision") != "accepted":
        raise AcceptanceReceiptError("decision_not_accepted")
    verifier = candidate.get("verifier_identity")
    producers = candidate.get("producer_identities")
    if (
        not isinstance(verifier, str) or not verifier
        or not isinstance(producers, dict)
        or any(not isinstance(rows, list) for rows in producers.values())
    ):
        raise AcceptanceReceiptError("identity_set_invalid")
    producer_set = {
        str(identity)
        for rows in producers.values()
        for identity in rows
    }
    if verifier in producer_set:
        raise AcceptanceReceiptError("verifier_not_independent")

    commit, tree, clean = git_state_reader(repo_root)
    if not clean:
        raise AcceptanceReceiptError("candidate_tree_dirty")
    if commit != candidate.get("candidate_commit"):
        raise AcceptanceReceiptError("candidate_commit_mismatch")
    if tree != candidate.get("candidate_tree"):
        raise AcceptanceReceiptError("candidate_tree_mismatch")

    forced, forced_path, forced_sha = _load_bound_json(
        repo_root, candidate.get("forced_completion"), "forced_completion"
    )
    if not forced:
        raise AcceptanceReceiptError("forced_completion_empty")
    aggregate, aggregate_path, aggregate_sha = _load_bound_json(
        repo_root, candidate.get("aggregate"), "aggregate"
    )
    if not _aggregate_complete(aggregate):
        raise AcceptanceReceiptError("aggregate_incomplete")

    evidence_bindings = candidate.get("evidence")
    if not isinstance(evidence_bindings, dict):
        raise AcceptanceReceiptError("evidence_bindings_missing")
    bound_evidence: dict[str, dict[str, str]] = {}
    for name in EVIDENCE_NAMES:
        _payload, path, digest = _load_bound_json(
            repo_root, evidence_bindings.get(name), f"evidence_{name}"
        )
        bound_evidence[name] = {"path": path, "sha256": digest}

    proof_map, proof_path, proof_sha = _load_bound_json(
        repo_root, candidate.get("proof_map"), "proof_map"
    )
    if proof_map.get("schema") != PROOF_MAP_SCHEMA:
        raise AcceptanceReceiptError("proof_map_schema_invalid")
    proof_rows = {
        key: value for key, value in proof_map.items() if key != "schema"
    }
    if not proof_rows or any(
        not isinstance(value, list) or not value for value in proof_rows.values()
    ):
        raise AcceptanceReceiptError("proof_map_incomplete")

    correction, correction_path, correction_sha = _load_bound_json(
        repo_root, candidate.get("correction_plan_receipt"), "correction_plan"
    )
    if (
        correction.get("schema") != CORRECTION_SCHEMA
        or correction.get("decision") != "accepted"
        or correction.get("fresh") is not True
        or correction.get("forced_completion_sha256") != forced_sha
        or correction.get("aggregate_sha256") != aggregate_sha
        or correction.get("candidate_commit") != commit
        or correction.get("candidate_tree") != tree
        or correction.get("accepted_by") != verifier
    ):
        raise AcceptanceReceiptError("correction_plan_not_fresh_or_accepted")

    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "decision": "accepted",
        "independent_verifier": True,
        "verifier_identity": verifier,
        "producer_identities": producers,
        "candidate_commit": commit,
        "candidate_tree": tree,
        "candidate_clean": True,
        "forced_completion_path": forced_path,
        "forced_completion_sha256": forced_sha,
        "aggregate": {"path": aggregate_path, "sha256": aggregate_sha},
        "evidence": bound_evidence,
        "proof_map": {"path": proof_path, "sha256": proof_sha},
        "correction_plan_receipt": {
            "path": correction_path, "sha256": correction_sha,
        },
        "candidate_sha256": candidate["candidate_sha256"],
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        if not isinstance(candidate, dict):
            raise AcceptanceReceiptError("candidate_not_object")
        receipt = build_acceptance_receipt(
            candidate, repo_root=args.repo_root
        )
        _write_atomic(args.output, receipt)
    except (OSError, json.JSONDecodeError, AcceptanceReceiptError) as exc:
        parser.exit(2, f"acceptance receipt rejected: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
