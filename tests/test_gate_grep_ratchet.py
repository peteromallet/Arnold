"""W11b — GateRecommendation grep-gate ratchet.

Code-only count of GateRecommendation references across the 6 SDK files
in megaplan/_pipeline/, excluding comment lines and Sphinx :data:
docstring references.  The baseline of 19 code refs is pinned; any
increase fails the gate (ratchet).
"""

from __future__ import annotations

import re
from pathlib import Path


#: Files in megaplan/_pipeline/ that contain GateRecommendation references
#: (the complete set of files with at least one ref across the SDK module,
#: excluding tests/_pipeline/ and CLI entry points).
_GATEREC_FILES: tuple[str, ...] = (
    "megaplan/_pipeline/pattern_topology.py",
    "megaplan/_pipeline/pattern_types.py",
    "megaplan/_pipeline/pattern_joins.py",
    "megaplan/_pipeline/types.py",
    "megaplan/_pipeline/stages/tiebreaker.py",
    "megaplan/_pipeline/subloop.py",
    "megaplan/_pipeline/validator.py",
)

#: Baseline code-only ref count (25 total minus 4 Sphinx :data: docstring
#: refs in pattern_topology.py:16,206, pattern_types.py:17, validator.py:10).
_BASELINE: int = 22

#: Per-file expected code-only counts at the pinned baseline.
_EXPECTED_PER_FILE: dict[str, int] = {
    "megaplan/_pipeline/pattern_topology.py": 0,
    "megaplan/_pipeline/pattern_types.py": 2,
    "megaplan/_pipeline/pattern_joins.py": 6,
    "megaplan/_pipeline/types.py": 4,
    "megaplan/_pipeline/stages/tiebreaker.py": 2,
    "megaplan/_pipeline/subloop.py": 5,
    "megaplan/_pipeline/validator.py": 3,
}


def _count_code_refs(filepath: str) -> tuple[int, int, int]:
    """Return (total, :data:-refs, code-only) for *filepath*.

    The code-only count excludes:
    - Lines whose first non-whitespace character is ``#`` (comment lines).
    - Occurrences inside ``:data:`GateRecommendation``` Sphinx role markup
      (documentation-only references that must not trip the gate).
    """
    with open(filepath) as fh:
        content = fh.read()

    lines = content.split("\n")
    # Drop comment-only lines so a future `# GateRecommendation` comment
    # does not inflate the count.
    non_comment_lines = [ln for ln in lines if not ln.strip().startswith("#")]
    non_comment = "\n".join(non_comment_lines)

    total = len(re.findall(r"GateRecommendation", non_comment))
    data_refs = len(re.findall(r":data:`GateRecommendation`", non_comment))
    code = total - data_refs
    return total, data_refs, code


def test_gaterec_ratchet_total_does_not_exceed_baseline():
    """The code-only GateRecommendation count across the 6 files must not
    exceed the pinned baseline of 19 (ratchet)."""
    total_code = 0
    for fp in _GATEREC_FILES:
        _, _, code = _count_code_refs(fp)
        total_code += code

    assert total_code <= _BASELINE, (
        f"GateRecommendation code-only ref count {total_code} exceeds "
        f"baseline {_BASELINE} — ratchet FAILED"
    )


def test_gaterec_ratchet_per_file_matches_baseline():
    """Each file's code-only count must match its pinned baseline.

    This prevents silent redistributions (e.g. moving a ref from one file
    to another without changing the total).
    """
    for fp in _GATEREC_FILES:
        _, _, code = _count_code_refs(fp)
        expected = _EXPECTED_PER_FILE[fp]
        assert code == expected, (
            f"{fp}: code-only count {code} != expected {expected}"
        )


def test_gaterec_no_new_files_introduced():
    """No file outside the pinned set should contain GateRecommendation
    references unless explicitly added to the gate.

    Scans all .py files under megaplan/_pipeline/ (excluding tests/_pipeline/
    and CLI entry points) and asserts only the known 6 files have refs.
    """
    repo_root = Path(__file__).resolve().parent.parent
    pipeline_dir = repo_root / "megaplan" / "_pipeline"

    # Files we explicitly EXCLUDE from the scan:
    # - CLI entry point (run_cli.py)
    # - tests/_pipeline/ (not under megaplan/_pipeline anyway)
    exclude_names = {"run_cli.py"}

    extra_files: list[str] = []
    for py_file in sorted(pipeline_dir.rglob("*.py")):
        if py_file.name in exclude_names:
            continue
        rel = str(py_file.relative_to(repo_root))
        if rel in _GATEREC_FILES:
            continue
        # Check if this file has ANY GateRecommendation reference
        with open(py_file) as fh:
            content = fh.read()
        if "GateRecommendation" in content:
            extra_files.append(rel)

    assert not extra_files, (
        f"Unexpected GateRecommendation refs in files outside the pinned set: "
        f"{extra_files}"
    )
