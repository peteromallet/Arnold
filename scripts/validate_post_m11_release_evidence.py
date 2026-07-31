#!/usr/bin/env python3
"""Validate the post-M11 release evidence record without interpreting release policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_RECORD_STATUS = {"in_progress", "complete"}
ALLOWED_RESIDUAL_STATUS = {"pending", "complete"}
REPO_ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _require_sha1(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA1.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase 40-character Git SHA")
    return value


def _validate_sha256_fields(value: Any, label: str = "record") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_label = f"{label}.{key}"
            if key == "sha256" or key.endswith("_sha256"):
                if not isinstance(child, str) or not SHA256.fullmatch(child):
                    raise ValueError(
                        f"{child_label} must be a lowercase 64-character SHA-256"
                    )
            else:
                _validate_sha256_fields(child, child_label)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_sha256_fields(child, f"{label}[{index}]")


def validate(path: Path) -> None:
    repo = Path(_git("rev-parse", "--show-toplevel", cwd=REPO_ROOT))
    data = json.loads(path.read_text(encoding="utf-8"))

    digest_path = path.with_name(path.name + ".sha256")
    if digest_path.is_file():
        expected_digest, expected_name = digest_path.read_text(
            encoding="utf-8"
        ).split()
        actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected_name != path.name or expected_digest != actual_digest:
            raise ValueError("release evidence SHA-256 sidecar mismatch")

    if data.get("schema") != "arnold.post_m11_release_evidence.v1":
        raise ValueError("unsupported schema")
    if data.get("record_status") not in ALLOWED_RECORD_STATUS:
        raise ValueError("invalid record_status")
    _validate_sha256_fields(data)

    authority = data["authority"]
    plan_path = repo / authority["plan_path"]
    if not plan_path.is_file():
        raise ValueError(f"missing plan path: {authority['plan_path']}")

    git_objects: set[str] = set()
    for field in (
        "plan_publication_commit",
        "origin_base_commit",
        "evidence_cut_commit",
        "evidence_cut_tree",
    ):
        git_objects.add(_require_sha1(authority[field], f"authority.{field}"))

    plan_blob = _require_sha1(authority["plan_blob"], "authority.plan_blob")
    actual_plan_blob = _git("hash-object", str(plan_path), cwd=repo)
    if actual_plan_blob != plan_blob:
        raise ValueError(
            f"plan blob mismatch: expected {plan_blob}, got {actual_plan_blob}"
        )
    git_objects.add(plan_blob)
    actual_evidence_tree = _git(
        "rev-parse", f"{authority['evidence_cut_commit']}^{{tree}}", cwd=repo
    )
    if actual_evidence_tree != authority["evidence_cut_tree"]:
        raise ValueError(
            "evidence cut tree mismatch: expected "
            f"{authority['evidence_cut_tree']}, got {actual_evidence_tree}"
        )

    source_refs = data.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs:
        raise ValueError("source_refs must be a non-empty list")
    for index, item in enumerate(source_refs):
        git_objects.add(_require_sha1(item["sha"], f"source_refs[{index}].sha"))
        if item.get("classification") not in {"LAND", "KEEP_CHECKPOINT"}:
            raise ValueError(f"source_refs[{index}] has invalid classification")

    lineage = data.get("integration_lineage")
    if not isinstance(lineage, list) or not lineage:
        raise ValueError("integration_lineage must be a non-empty list")
    for index, item in enumerate(lineage):
        git_objects.add(
            _require_sha1(item["sha"], f"integration_lineage[{index}].sha")
        )

    for index, item in enumerate(data.get("validation_observations", [])):
        if "bound_commit" in item:
            git_objects.add(
                _require_sha1(
                    item["bound_commit"],
                    f"validation_observations[{index}].bound_commit",
                )
            )
        if "bound_tree" in item:
            git_objects.add(
                _require_sha1(
                    item["bound_tree"],
                    f"validation_observations[{index}].bound_tree",
                )
            )

    for collection_name in (
        "historical_superseded_attempts",
        "packaging_artifacts",
    ):
        for index, item in enumerate(data.get(collection_name, [])):
            if "bound_commit" in item:
                git_objects.add(
                    _require_sha1(
                        item["bound_commit"],
                        f"{collection_name}[{index}].bound_commit",
                    )
                )

    for sha in sorted(git_objects):
        _git("cat-file", "-e", f"{sha}^{{object}}", cwd=repo)

    for index, checkpoint in enumerate(data.get("checkpoints", [])):
        digest = checkpoint.get("sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ValueError(f"checkpoints[{index}].sha256 is invalid")
        location = checkpoint.get("location", "")
        if not location.startswith(("$LOCAL_CHECKPOINT_ROOT/", "$CLOUD_WORKSPACE/")):
            raise ValueError(f"checkpoints[{index}].location is not redacted")

    residuals = data.get("residuals")
    if not isinstance(residuals, list) or not residuals:
        raise ValueError("residuals must be a non-empty list")
    seen_residuals: set[str] = set()
    for index, item in enumerate(residuals):
        residual_id = item.get("id")
        if not isinstance(residual_id, str) or not residual_id:
            raise ValueError(f"residuals[{index}].id is missing")
        if residual_id in seen_residuals:
            raise ValueError(f"duplicate residual id: {residual_id}")
        seen_residuals.add(residual_id)
        if item.get("status") not in ALLOWED_RESIDUAL_STATUS:
            raise ValueError(f"residuals[{index}] has invalid status")
        if not isinstance(item.get("required_evidence"), str):
            raise ValueError(f"residuals[{index}].required_evidence is missing")
        if item["status"] == "complete" and not isinstance(
            item.get("completion_evidence"), str
        ):
            raise ValueError(
                f"residuals[{index}] is complete without completion_evidence"
            )

    if data["record_status"] == "complete":
        pending = [item["id"] for item in residuals if item["status"] != "complete"]
        if pending:
            raise ValueError(
                "record_status cannot be complete while residuals are pending: "
                + ", ".join(pending)
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "record",
        nargs="?",
        type=Path,
        default=Path("docs/megaplan/post-m11-release-evidence-20260731.json"),
    )
    parser.add_argument("--print-sha256", action="store_true")
    args = parser.parse_args()
    validate(args.record.resolve())
    if args.print_sha256:
        print(hashlib.sha256(args.record.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
