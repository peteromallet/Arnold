#!/usr/bin/env python3
"""Read-only M6 corpus capture tool for CL1.

Captures frozen M6 evidence from the preserved custody-control-plane
repository at an exact Git revision. Inventories rounds v1-v5, extracts
critique artifacts, redacts unstable workspace paths deterministically,
and produces a dual-hashed corpus fixture.

Usage::

    python tools/generate_cl1_m6_corpus.py \\
        --source-repo /workspace/custody-control-plane-20260714/Arnold \\
        --source-plan m6-exact-contract-and-20260716-1303 \\
        --source-revision ea2be1fe36c42c4f19afedd2c096b5dcec7c56df \\
        [--output tests/fixtures/critique_ledger/m6-corpus.json] \\
        [--check]

Design constraints (M6 observe-only):
* NEVER mutates the source repository.
* NEVER mutates lifecycle state, queues, providers, delivery, or notifications.
* All git operations are read-only (cat-file, ls-tree, rev-parse).
* Path redaction is deterministic — same input always produces same output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "tests/fixtures/critique_ledger/m6-corpus.json"

# Required artifact families per round
REQUIRED_ARTIFACTS = [
    "plan_v{N}.meta.json",
    "critique.md",
    "scores.json",
    "phase_result.json",
    "gate.json",
    "gate_signals_v1.json",
    "state.json",
]

# Unstable path patterns to redact (deterministic replacement)
PATH_REDACTIONS: list[tuple[str, str]] = [
    (r"/workspace/custody-control-plane-20260714/Arnold", "<SOURCE_REPO>"),
    (r"/workspace/[^/]+/Arnold", "<SOURCE_REPO>"),
    (r"/root/\.pyenv/versions/[^/]+/lib/python[^/]+/site-packages", "<PYTHON_SITE>"),
    (r"/home/[^/]+", "<HOME>"),
    (r"/tmp/[^/\"]+", "<TMP>"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_git(args: list[str], repo: Path) -> str:
    """Run a read-only git command in the source repo."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            f"Git command failed: git {' '.join(args)}\n"
            f"stderr: {e.stderr.strip()}"
        ) from e


def verify_revision(repo: Path, revision: str) -> str:
    """Verify that the revision exists as a Git object and return its full hash.

    Uses cat-file -t to confirm it's a commit object, never relying on
    mutable working-tree state (HEAD, branches, or index).
    """
    # Resolve to full hash
    full_hash = _run_git(["rev-parse", "--verify", revision], repo)
    if not full_hash or len(full_hash) != 40:
        raise SystemExit(f"Revision {revision!r} did not resolve to a full SHA.")

    # Verify it's a commit object
    obj_type = _run_git(["cat-file", "-t", full_hash], repo)
    if obj_type != "commit":
        raise SystemExit(
            f"Revision {revision!r} resolved to {full_hash} "
            f"which is a {obj_type}, not a commit."
        )

    return full_hash


def redact_paths(text: str) -> str:
    """Deterministically redact unstable workspace paths."""
    result = text
    for pattern, replacement in PATH_REDACTIONS:
        result = re.sub(pattern, replacement, result)
    return result


def hash_bytes(data: bytes) -> str:
    """SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def hash_text(text: str) -> str:
    """SHA-256 hex digest of UTF-8 encoded text."""
    return hash_bytes(text.encode("utf-8"))


def read_file_bytes(repo: Path, rel_path: str, revision: str) -> bytes:
    """Read a file's content at a specific revision from Git object store."""
    try:
        result = subprocess.run(
            ["git", "cat-file", "-p", f"{revision}:{rel_path}"],
            cwd=str(repo),
            capture_output=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            f"Failed to read {rel_path!r} at {revision}: {e.stderr.decode().strip()}"
        ) from e


def read_json(repo: Path, rel_path: str, revision: str) -> Any:
    """Read and parse a JSON file from Git at a revision."""
    raw = read_file_bytes(repo, rel_path, revision)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"Failed to parse JSON from {rel_path!r} at {revision}: {e}"
        ) from e


def list_plan_dir(repo: Path, plan_path: str, revision: str) -> list[str]:
    """List files in a directory within the plan at a revision."""
    try:
        output = _run_git(
            ["ls-tree", "--name-only", "-r", f"{revision}:{plan_path}"],
            repo,
        )
        if not output:
            return []
        return [line for line in output.split("\n") if line]
    except SystemExit:
        return []


# ---------------------------------------------------------------------------
# Artifact inventory
# ---------------------------------------------------------------------------


def inventory_round(
    repo: Path,
    plan_path: str,
    round_label: str,
    revision: str,
    plan_name: str,
) -> dict[str, Any]:
    """Inventory all required artifacts for a single critique round.

    Returns a dict with available artifacts, metadata, and any
    unavailable evidence with explicit reopen conditions.
    """
    round_dir = f"{plan_path}/rounds/{round_label}"
    available: dict[str, Any] = {}
    unavailable: list[dict[str, str]] = []

    # Plan meta
    meta_file = f"plan_v{round_label[1:]}.meta.json" if round_label.startswith("v") else None
    if meta_file:
        meta_path = f"{plan_path}/{meta_file}"
        try:
            available["plan_meta"] = {
                "path": meta_path,
                "content": read_json(repo, meta_path, revision),
            }
        except SystemExit:
            unavailable.append({
                "artifact": meta_path,
                "reason": "File not found at revision",
                "reopen_condition": f"Restore {meta_path} from backup",
            })

    # Phase result
    phase_result_path = f"{round_dir}/phase_result.json"
    try:
        available["phase_result"] = {
            "path": phase_result_path,
            "content": read_json(repo, phase_result_path, revision),
        }
    except SystemExit:
        unavailable.append({
            "artifact": phase_result_path,
            "reason": "Not found at revision",
            "reopen_condition": "Regenerate from source artifacts",
        })

    # State
    state_path = f"{round_dir}/state.json"
    try:
        available["state"] = {
            "path": state_path,
            "content": read_json(repo, state_path, revision),
        }
    except SystemExit:
        unavailable.append({
            "artifact": state_path,
            "reason": "Not found at revision",
            "reopen_condition": "Restore state from backup",
        })

    # Critique artifacts
    critique_md_path = f"{round_dir}/critique.md"
    try:
        raw = read_file_bytes(repo, critique_md_path, revision)
        available["critique_md"] = {
            "path": critique_md_path,
            "content_hash": hash_bytes(raw),
            "redacted_content": redact_paths(raw.decode("utf-8", errors="replace")),
        }
    except SystemExit:
        unavailable.append({
            "artifact": critique_md_path,
            "reason": "Not found at revision",
            "reopen_condition": "Restore critique.md from backup",
        })

    # Scores
    scores_path = f"{round_dir}/scores.json"
    try:
        available["scores"] = {
            "path": scores_path,
            "content": read_json(repo, scores_path, revision),
        }
    except SystemExit:
        unavailable.append({
            "artifact": scores_path,
            "reason": "Not found at revision",
            "reopen_condition": "Regenerate scores from critique run",
        })

    # Gate signals
    gate_signals_path = f"{round_dir}/gate_signals_v1.json"
    try:
        available["gate_signals"] = {
            "path": gate_signals_path,
            "content": read_json(repo, gate_signals_path, revision),
        }
    except SystemExit:
        unavailable.append({
            "artifact": gate_signals_path,
            "reason": "Not found at revision",
            "reopen_condition": "Regenerate from gate evaluation",
        })

    # Gate decision
    gate_path = f"{round_dir}/gate.json"
    try:
        available["gate"] = {
            "path": gate_path,
            "content": read_json(repo, gate_path, revision),
        }
    except SystemExit:
        unavailable.append({
            "artifact": gate_path,
            "reason": "Not found at revision",
            "reopen_condition": "Regenerate from gate evaluation",
        })

    # List other files in round directory
    all_files = list_plan_dir(repo, round_dir, revision)
    available["_round_files"] = all_files

    return {
        "round_label": round_label,
        "available": available,
        "unavailable": unavailable,
    }


def inventory_plan(
    repo: Path,
    plan_name: str,
    revision: str,
) -> dict[str, Any]:
    """Inventory the full plan across rounds v1-v5."""
    plan_path = f".megaplan/plans/{plan_name}"
    rounds_data: list[dict[str, Any]] = []

    # Verify plan directory exists
    plan_files = list_plan_dir(repo, plan_path, revision)
    if not plan_files:
        raise SystemExit(
            f"Plan directory '{plan_path}' not found at revision {revision}. "
            f"Verify --source-plan is correct."
        )

    # Inventory rounds v1 through v5
    for round_num in range(1, 6):
        round_label = f"v{round_num}"
        try:
            round_data = inventory_round(repo, plan_path, round_label, revision, plan_name)
            rounds_data.append(round_data)
        except SystemExit as e:
            raise SystemExit(
                f"Failed to inventory round {round_label}: {e}"
            ) from e

    # Extract additional plan-level artifacts
    plan_level: dict[str, Any] = {}

    # State at plan root
    state_path = f"{plan_path}/state.json"
    try:
        plan_level["state"] = read_json(repo, state_path, revision)
    except SystemExit:
        plan_level["state_unavailable"] = True

    # Contract
    contract_path = f"{plan_path}/contract.json"
    try:
        plan_level["contract"] = read_json(repo, contract_path, revision)
    except SystemExit:
        plan_level["contract_unavailable"] = True

    # Evaluator verdict
    verdict_path = f"{plan_path}/evaluator_verdict.json"
    try:
        plan_level["evaluator_verdict"] = read_json(repo, verdict_path, revision)
    except SystemExit:
        plan_level["evaluator_verdict_unavailable"] = True

    # Faults
    faults_path = f"{plan_path}/faults.json"
    try:
        plan_level["faults"] = read_json(repo, faults_path, revision)
    except SystemExit:
        plan_level["faults_unavailable"] = True

    return {
        "plan_name": plan_name,
        "plan_path": plan_path,
        "rounds": rounds_data,
        "plan_level": plan_level,
    }


# ---------------------------------------------------------------------------
# Corpus assembly
# ---------------------------------------------------------------------------


def build_corpus(
    repo: Path,
    plan_name: str,
    revision: str,
    full_hash: str,
) -> dict[str, Any]:
    """Build the complete M6 corpus from the source repository."""

    plan_data = inventory_plan(repo, plan_name, revision)

    # Collect all artifact identities for duplicate detection
    all_identities: list[str] = []
    for rd in plan_data["rounds"]:
        round_id = (
            f"round:{rd['round_label']}",
        )
        all_identities.append(rd["round_label"])

    # Check for duplicate round labels
    round_labels = [rd["round_label"] for rd in plan_data["rounds"]]
    if len(round_labels) != len(set(round_labels)):
        duplicates = {r for r in round_labels if round_labels.count(r) > 1}
        raise SystemExit(f"Duplicate round labels detected: {duplicates}")

    # Serialize to compute hashes
    raw_json = json.dumps(plan_data, indent=2, sort_keys=True, default=str)
    raw_hash = hash_text(raw_json)

    # Redact and re-hash
    redacted_json = redact_paths(raw_json)
    redacted_hash = hash_text(redacted_json)

    corpus = {
        "meta": {
            "schema_version": "cl.m6-corpus.v1",
            "generated_by": "tools/generate_cl1_m6_corpus.py",
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_revision": full_hash,
            "source_revision_short": revision,
            "source_plan": plan_name,
            "raw_hash": f"sha256:{raw_hash}",
            "redacted_hash": f"sha256:{redacted_hash}",
        },
        "plan": plan_data,
    }

    return corpus


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture frozen M6 corpus from preserved repository."
    )
    parser.add_argument(
        "--source-repo",
        required=True,
        help="Path to the preserved custody-control-plane repository",
    )
    parser.add_argument(
        "--source-plan",
        required=True,
        help="Plan name (e.g., m6-exact-contract-and-20260716-1303)",
    )
    parser.add_argument(
        "--source-revision",
        required=True,
        help="Exact Git revision (full or short SHA)",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Output path for corpus JSON (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check mode: regenerate and compare against existing output",
    )
    args = parser.parse_args()

    source_repo = Path(args.source_repo).resolve()
    if not source_repo.is_dir():
        raise SystemExit(f"Source repository not found: {source_repo}")

    # Verify it's a git repo
    if not (source_repo / ".git").exists():
        raise SystemExit(f"Not a git repository: {source_repo}")

    # Verify revision
    print(f"Verifying revision {args.source_revision!r}...", file=sys.stderr)
    full_hash = verify_revision(source_repo, args.source_revision)
    print(f"  Resolved: {full_hash}", file=sys.stderr)

    # Build corpus
    print(f"Inventoring plan {args.source_plan!r}...", file=sys.stderr)
    try:
        corpus = build_corpus(
            source_repo,
            args.source_plan,
            args.source_revision,
            full_hash,
        )
    except SystemExit as e:
        print(f"CAPTURE FAILED: {e}", file=sys.stderr)
        sys.exit(1)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    redacted_json = redact_paths(
        json.dumps(corpus, indent=2, sort_keys=True, default=str)
    )

    if args.check:
        # Compare against existing output
        if not output_path.exists():
            raise SystemExit(
                f"Check mode: output file {output_path} does not exist. "
                f"Run without --check first."
            )
        existing = output_path.read_text()
        existing_hash = hash_text(existing)
        new_hash = hash_text(redacted_json)
        if existing_hash != new_hash:
            raise SystemExit(
                f"Check mode: output has changed!\n"
                f"  Existing hash: sha256:{existing_hash}\n"
                f"  New hash:      sha256:{new_hash}"
            )
        print(
            f"Check passed: output matches ({output_path})",
            file=sys.stderr,
        )
    else:
        output_path.write_text(redacted_json)
        print(
            f"Corpus written to {output_path} "
            f"(sha256:{hash_text(redacted_json)})",
            file=sys.stderr,
        )

    # Summary
    round_count = len(corpus["plan"]["rounds"])
    total_unavailable = sum(
        len(rd["unavailable"]) for rd in corpus["plan"]["rounds"]
    )
    print(
        f"Done: {round_count} rounds captured, "
        f"{total_unavailable} unavailable artifacts.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
