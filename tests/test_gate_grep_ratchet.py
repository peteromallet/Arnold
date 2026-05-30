"""T10 — GateRecommendation grep-gate ratchet (post-de-planning).

Code-only count of GateRecommendation references across the SDK files
that are still allowed to name it (the definition site, the structural
validator, and the planning-binding shim), excluding comment lines and
Sphinx ``:data:`` docstring references. Total baseline pinned to 11
code-only refs across {types.py:4, validator.py:3, planning_bindings.py:4}.

A no-new-files scan additionally forbids any reference (code OR doc) to
``GateRecommendation`` in any ``megaplan/_pipeline/**/*.py`` file
outside the allow-list.
"""

from __future__ import annotations

import re
from pathlib import Path


#: Files in megaplan/_pipeline/ that are allowed to name GateRecommendation.
_GATEREC_FILES: tuple[str, ...] = (
    "megaplan/_pipeline/types.py",
    "megaplan/_pipeline/validator.py",
    "megaplan/_pipeline/planning_bindings.py",
)

#: Total code-only ref baseline (sum of _EXPECTED_PER_FILE values).
_BASELINE: int = 11

#: Per-file expected code-only counts at the pinned baseline.
_EXPECTED_PER_FILE: dict[str, int] = {
    "megaplan/_pipeline/types.py": 4,
    "megaplan/_pipeline/validator.py": 3,
    "megaplan/_pipeline/planning_bindings.py": 4,
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
    non_comment_lines = [ln for ln in lines if not ln.strip().startswith("#")]
    non_comment = "\n".join(non_comment_lines)

    total = len(re.findall(r"GateRecommendation", non_comment))
    data_refs = len(re.findall(r":data:`GateRecommendation`", non_comment))
    code = total - data_refs
    return total, data_refs, code


def test_gaterec_ratchet_total_does_not_exceed_baseline():
    """The code-only GateRecommendation count across the allow-listed
    files must not exceed the pinned baseline of 11 (ratchet)."""
    total_code = 0
    for fp in _GATEREC_FILES:
        _, _, code = _count_code_refs(fp)
        total_code += code

    assert total_code <= _BASELINE, (
        f"GateRecommendation code-only ref count {total_code} exceeds "
        f"baseline {_BASELINE} — ratchet FAILED"
    )


def test_gaterec_ratchet_per_file_matches_baseline():
    """Each allow-listed file's code-only count must match its pinned
    baseline. Prevents silent redistribution."""
    for fp in _GATEREC_FILES:
        _, _, code = _count_code_refs(fp)
        expected = _EXPECTED_PER_FILE[fp]
        assert code == expected, (
            f"{fp}: code-only count {code} != expected {expected}"
        )


def test_gaterec_no_refs_outside_allow_list():
    """No file under megaplan/_pipeline/ outside the allow-list may
    contain ANY GateRecommendation reference (code OR doc).

    Scans every .py file under megaplan/_pipeline/ (recursively) and
    asserts only the allow-listed files contain the literal string
    ``GateRecommendation``.
    """
    repo_root = Path(__file__).resolve().parent.parent
    pipeline_dir = repo_root / "megaplan" / "_pipeline"

    exclude_names = {"run_cli.py"}

    extra_files: list[str] = []
    for py_file in sorted(pipeline_dir.rglob("*.py")):
        if py_file.name in exclude_names:
            continue
        rel = str(py_file.relative_to(repo_root))
        if rel in _GATEREC_FILES:
            continue
        with open(py_file) as fh:
            content = fh.read()
        if "GateRecommendation" in content:
            extra_files.append(rel)

    assert not extra_files, (
        f"Unexpected GateRecommendation refs in files outside the "
        f"allow-list: {extra_files}"
    )
