"""Seam-coverage completeness test (T10).

Parses ``docs/m8-seam-coverage-matrix.md``, extracts the seam rows, and
asserts:

1. The matrix covers exactly the canonical set of architectural-spine
   seams (no missing rows, no extra rows).
2. Every ``file:line`` locus referenced in implementation tables points
   to a file that exists in the repository.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPO_ROOT / "docs" / "m8-seam-coverage-matrix.md"

CANONICAL_SEAMS: frozenset[str] = frozenset(
    {
        "Step⇄Step (inter-step data flow)",
        "Step⇄Model (incl. Engine⇄Worker)",
        "Step⇄State",
        "Author⇄Runtime",
        "Engine⇄World",
        "Control-flow forks",
        "Named Artifact Suspend/Continuation (Evidence-Pack)",
        "Aggregate Registry",
    }
)

_SECTION_RE = re.compile(r"^##\s+\d+\.\s+(.+?)\s*$", re.MULTILINE)
# Only validate paths containing a directory separator — the summary table
# uses bare filenames as shorthand and is not intended as a navigable locus.
_LOCUS_RE = re.compile(r"`((?:[\w\-.]+/)+[\w\-.]+\.py):\d+(?:-\d+)?`")


def _extract_seam_titles(markdown: str) -> set[str]:
    return {m.group(1).strip() for m in _SECTION_RE.finditer(markdown)}


def test_matrix_file_exists() -> None:
    assert MATRIX_PATH.is_file(), f"missing seam matrix at {MATRIX_PATH}"


def test_matrix_covers_exactly_canonical_seams() -> None:
    titles = _extract_seam_titles(MATRIX_PATH.read_text(encoding="utf-8"))
    missing = CANONICAL_SEAMS - titles
    extra = titles - CANONICAL_SEAMS
    assert not missing, f"seam matrix missing canonical seams: {sorted(missing)}"
    assert not extra, f"seam matrix has non-canonical extra seams: {sorted(extra)}"


def test_all_loci_files_exist() -> None:
    text = MATRIX_PATH.read_text(encoding="utf-8")
    bad: list[str] = []
    seen: set[str] = set()
    for m in _LOCUS_RE.finditer(text):
        rel = m.group(1)
        if rel in seen:
            continue
        seen.add(rel)
        candidate = REPO_ROOT / rel
        if not candidate.is_file():
            bad.append(rel)
    assert not bad, f"loci reference missing files: {bad[:10]}"
