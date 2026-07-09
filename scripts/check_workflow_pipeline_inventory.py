#!/usr/bin/env python3
"""Inventory gate for shipped / example workflow pipelines.

Fails when:
* a shipped root is not listed in the disposition table,
* a tracked shipped file contains a forbidden pattern outside allowlisted
  archival paths,
* the disposition table contains an unknown status.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from arnold.conformance.authoring_terms import FORBIDDEN_AUTHORING_TERMS

REPO_ROOT = Path(__file__).resolve().parents[1]

# Every shipped / example root under arnold/pipelines or arnold_pipelines that
# exists today must have a disposition row.  A root is either a package
# directory or a single-file module.
PIPELINE_DISPOSITION: dict[str, dict[str, Any]] = {
    # Survivors (migrate)
    "arnold_pipelines/megaplan/pipelines/planning": {
        "status": "migrate",
        "registry_id": "megaplan.planning",
        "migrated": False,
    },
    "arnold_pipelines/megaplan/pipelines/doc": {
        "status": "migrate",
        "registry_id": "megaplan.doc",
        "migrated": True,
    },
    "arnold_pipelines/megaplan/pipelines/creative": {
        "status": "migrate",
        "registry_id": "megaplan.creative",
        "migrated": True,
    },
    "arnold_pipelines/megaplan/pipelines/jokes": {
        "status": "migrate",
        "registry_id": "megaplan.jokes",
        "migrated": True,
    },
    "arnold_pipelines/megaplan/pipelines/live_supervisor": {
        "status": "migrate",
        "registry_id": "megaplan.live_supervisor",
        "migrated": True,
    },
    "arnold_pipelines/megaplan/pipelines/select_tournament": {
        "status": "migrate",
        "registry_id": "megaplan.select_tournament",
        "migrated": True,
    },
    "arnold_pipelines/megaplan/pipelines/writing_panel_strict": {
        "status": "migrate",
        "registry_id": "megaplan.writing_panel_strict",
        "migrated": True,
    },
    "arnold/pipelines/evidence_pack": {
        "status": "delete",
        "registry_id": None,
        "migrated": False,
    },
    "arnold_pipelines/evidence_pack": {
        "status": "migrate",
        "registry_id": "evidence_pack.verifier",
        "migrated": True,
    },
    "arnold/pipelines/_template": {
        "status": "delete",
        "registry_id": None,
        "migrated": False,
    },
    "arnold_pipelines/_template": {
        "status": "migrate",
        "registry_id": None,
        "migrated": True,
    },
    "arnold/pipelines/folder_audit": {
        "status": "archive",
        "registry_id": "arnold.folder_audit",
        "migrated": False,
    },
    "arnold/pipelines/deliberation": {
        "status": "archive",
        "registry_id": "arnold.deliberation",
        "migrated": False,
    },
    # Archives
    "arnold_pipelines/megaplan/pipelines/epic_blitz.py": {
        "status": "archive",
        "registry_id": None,
    },
    "arnold/pipelines/simplify_writing": {
        "status": "archive",
        "registry_id": None,
    },
    "arnold/pipelines/vibecomfy_executor": {
        "status": "archive",
        "registry_id": None,
    },
    "arnold/pipelines/epic_blitz": {
        "status": "archive",
        "registry_id": None,
    },
    "arnold/pipelines/_deliberation_example": {
        "status": "archive",
        "registry_id": None,
    },
    "arnold/pipelines/briefs": {
        "status": "archive",
        "registry_id": None,
    },
    # Deletes (legacy duplicates)
    "arnold/pipelines/jokes": {
        "status": "delete",
        "registry_id": None,
    },
    "arnold/pipelines/creative": {
        "status": "delete",
        "registry_id": None,
    },
    "arnold/pipelines/doc": {
        "status": "delete",
        "registry_id": None,
    },
    "arnold/pipelines/live_supervisor": {
        "status": "delete",
        "registry_id": None,
    },
    "arnold/pipelines/select_tournament": {
        "status": "delete",
        "registry_id": None,
    },
    "arnold/pipelines/writing_panel_strict.py": {
        "status": "delete",
        "registry_id": None,
    },
    "arnold/pipelines/writing_panel_strict": {
        "status": "delete",
        "registry_id": None,
    },
    "arnold/pipelines/__init__.py": {
        "status": "delete",
        "registry_id": None,
    },
    "arnold/pipelines/_authoring.py": {
        "status": "whitelist",
        "registry_id": None,
    },
    "arnold_pipelines/megaplan/pipelines/epic-blitz": {
        "status": "archive",
        "registry_id": None,
    },
}

VALID_STATUSES = {"migrate", "delete", "archive", "whitelist"}

# Forbidden patterns for shipped pipeline source files. Sourced from the shared
# arnold.conformance.authoring_terms module (single source of truth) rather than
# re-authored here, so this list cannot drift from the boundary test's set.
FORBIDDEN_STRING_PATTERNS = FORBIDDEN_AUTHORING_TERMS

CANONICAL_NATIVE_ALLOWED_PATTERNS = {
    "from arnold.pipeline",
    "import arnold.pipeline",
    "Stage(",
    "Edge(",
}

# Command examples that must not appear in active docs/skills.
FORBIDDEN_DOC_PATTERNS = (
    "arnold pipelines describe",
    "arnold pipelines check",
    "arnold pipelines doctor",
    "arnold pipelines new",
    "arnold pipeline ",
)

# Files / directories where forbidden patterns are allowed (archival migration
# notes, legacy tests, and generated fixtures that intentionally capture old
# API examples).
ARCHIVAL_ALLOWLIST: tuple[str, ...] = (
    "arnold/pipelines/_deliberation_example",
    "arnold/pipelines/deliberation",
    "arnold/pipelines/epic_blitz",
    "arnold/pipelines/folder_audit",
    "arnold/pipelines/simplify_writing",
    "arnold/pipelines/vibecomfy_executor",
    "arnold/pipelines/briefs",
    "arnold/pipelines/evidence_pack",
    "arnold/pipelines/_template",
    "arnold_pipelines/megaplan/pipelines/epic_blitz.py",
    "arnold_pipelines/megaplan/pipelines/epic-blitz",
    # Legacy runtime shells kept inside migrated roots until M6 deletion.
    "arnold_pipelines/megaplan/pipelines/creative/steps.py",
    "arnold_pipelines/megaplan/pipelines/creative/prompts/__init__.py",
    "arnold_pipelines/megaplan/pipelines/doc/steps.py",
    "arnold_pipelines/megaplan/pipelines/doc/prompts/__init__.py",
    "arnold_pipelines/megaplan/pipelines/jokes/steps.py",
    "arnold_pipelines/megaplan/pipelines/jokes/prompts/__init__.py",
    "arnold_pipelines/megaplan/pipelines/live_supervisor/steps.py",
    "arnold_pipelines/megaplan/pipelines/live_supervisor/pipelines.py",
    "arnold_pipelines/megaplan/pipelines/live_supervisor/rules.py",
    "arnold_pipelines/megaplan/pipelines/live_supervisor/repair_agent.py",
    "arnold_pipelines/megaplan/pipelines/live_supervisor/model.py",
    "arnold_pipelines/megaplan/pipelines/select_tournament/steps.py",
    "arnold_pipelines/megaplan/pipelines/select_tournament/prompts/__init__.py",
    "docs/arnold/workflow-migration.md",
    "docs/arnold/legacy-surface-inventory.md",
    "docs/arnold/authoring-guide.md",
    "docs/arnold/creating-a-new-pipeline.md",
    "docs/arnold/skill-integration.md",
    "docs/arnold/tooling.md",
    "docs/arnold/arnold-megaplan-cleanup-plan.md",
    "docs/arnold/arnold-megaplan-subagent-review-synthesis.md",
    "docs/arnold/arnold-abstraction-vetting-synthesis.md",
    "docs/arnold/m3-5-canonical-megaplan-source-path-reconciliation.md",
    "docs/arnold/m5-cli-command-mapping.md",
    "docs/arnold/m5-generated-artifact-manifest.md",
    "docs/arnold/package-authoring-contract.md",
    "docs/arnold/package-contract.md",
    "docs/arnold/workflow-manifest-runtime-review",
    "docs/arnold/examples/my-pipeline.md",
    "docs/arnold/examples/select-tournament.md",
    "docs/arnold/examples/planning-as-composition.md",
    "docs/arnold/pipelines",
    "tests/archive/m5",
)


def _normalize_root(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _discover_shipped_roots() -> list[Path]:
    roots: list[Path] = []
    for base in (REPO_ROOT / "arnold" / "pipelines", REPO_ROOT / "arnold_pipelines" / "megaplan" / "pipelines"):
        if not base.exists():
            continue
        for child in sorted(base.iterdir()):
            if child.name == "__pycache__":
                continue
            if child.is_dir() or child.suffix == ".py":
                roots.append(child)
    return roots


def _is_archival(path: Path) -> bool:
    rel = _normalize_root(path)
    for prefix in ARCHIVAL_ALLOWLIST:
        if rel == prefix or rel.startswith(prefix + "/"):
            return True
    return False


def _check_forbidden_strings(path: Path) -> list[str]:
    errors: list[str] = []
    if path.suffix != ".py":
        return errors
    rel = _normalize_root(path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        for pattern in FORBIDDEN_STRING_PATTERNS:
            if (
                rel.startswith("arnold_pipelines/megaplan/pipelines/")
                and pattern in CANONICAL_NATIVE_ALLOWED_PATTERNS
            ):
                continue
            if pattern in line:
                errors.append(f"{path}:{lineno}: forbidden pattern {pattern!r}")
    return errors


def _check_forbidden_doc_strings(path: Path) -> list[str]:
    errors: list[str] = []
    if path.suffix != ".md":
        return errors
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        for pattern in FORBIDDEN_DOC_PATTERNS:
            if pattern in line:
                errors.append(f"{path}:{lineno}: forbidden doc example {pattern!r}")
    return errors


def _python_files_under(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(root.rglob("*.py"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-docs",
        action="store_true",
        help="Also scan active docs/skills for forbidden command examples.",
    )
    args = parser.parse_args(argv)

    errors: list[str] = []

    # Validate the inventory itself.
    for root, info in PIPELINE_DISPOSITION.items():
        if info.get("status") not in VALID_STATUSES:
            errors.append(f"inventory {root!r} has invalid status {info.get('status')!r}")

    # Discover roots and compare against inventory.
    discovered = _discover_shipped_roots()
    expected = set(PIPELINE_DISPOSITION)
    for root in discovered:
        rel = _normalize_root(root)
        if rel not in expected:
            errors.append(f"unlisted shipped root: {rel}")

    # Scan source files for forbidden patterns.
    # Only roots marked migrate (or whitelist) AND explicitly flagged migrated
    # are held to the new authoring surface. Archive/delete roots and migrate
    # roots awaiting Phase 3 conversion are allowed to retain legacy patterns.
    for root in discovered:
        rel = _normalize_root(root)
        info = PIPELINE_DISPOSITION.get(rel, {})
        status = info.get("status")
        if status not in {"migrate", "whitelist"}:
            continue
        if not info.get("migrated"):
            continue
        for path in _python_files_under(root):
            if _is_archival(path):
                continue
            errors.extend(_check_forbidden_strings(path))

    if args.check_docs:
        docs_root = REPO_ROOT / "docs" / "arnold"
        for path in sorted(docs_root.rglob("*.md")):
            if _is_archival(path):
                continue
            errors.extend(_check_forbidden_doc_strings(path))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"workflow pipeline inventory check passed ({len(discovered)} roots)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
