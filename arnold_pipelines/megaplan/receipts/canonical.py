"""Prompt canonicalization for step receipts."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

CANONICALIZATION_VERSION = 1

REDACTION_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b",
        "<TS>",
    ),
    (
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b",
        "<UUID>",
    ),
)


def canonicalize_prompt(
    prompt: str,
    *,
    project_dir: str | Path,
    plan_dir: str | Path,
    plan_id: str,
) -> str:
    """Return a stable prompt form with known transient values redacted."""
    canonical = prompt
    canonical = canonical.replace(str(plan_dir), "<PLAN_DIR>")
    canonical = canonical.replace(str(project_dir), "<PROJECT_DIR>")
    canonical = canonical.replace(plan_id, "<PLAN_ID>")
    for pattern, replacement in REDACTION_PATTERNS:
        canonical = re.sub(pattern, replacement, canonical)
    return canonical


def hash_prompts(
    prompt: str,
    *,
    project_dir: str | Path,
    plan_dir: str | Path,
    plan_id: str,
) -> tuple[str, str]:
    """Return raw and canonical SHA-256 hex digests for a rendered prompt."""
    raw_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    canonical = canonicalize_prompt(
        prompt,
        project_dir=project_dir,
        plan_dir=plan_dir,
        plan_id=plan_id,
    )
    canonical_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return raw_hash, canonical_hash
