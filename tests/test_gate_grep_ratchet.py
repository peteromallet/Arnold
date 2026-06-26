"""T13 — Post-M3b gate grep ratchet (GateRecommendation, OverrideAction, kind='gate').

Code-only count of GateRecommendation, OverrideAction, and ``kind='gate'``
references across canonical Megaplan core source files.  After M3b (T12), the
typed GateRecommendation and OverrideAction literals are removed and all
kind='gate' routing edges are migrated to kind='decision' — the baselines
are pinned to zero.

References in comment lines (``#``) are excluded.  Docstring-only
historical references were removed during T13 so all counts reach zero.
"""

from __future__ import annotations

import re
from pathlib import Path


#: Files in the canonical Megaplan core tree that are allowed to name GateRecommendation.
#: Empty — post-M3b, zero code references expected.
_GATEREC_FILES: tuple[str, ...] = ()

#: Total code-only ref baseline (sum of _EXPECTED_PER_FILE values).
_GATEREC_BASELINE: int = 0

#: Per-file expected code-only counts at the pinned baseline.
_GATEREC_EXPECTED_PER_FILE: dict[str, int] = {}

# ── OverrideAction ratchet ─────────────────────────────────────────────

_OVERRIDEACTION_FILES: tuple[str, ...] = ()

_OVERRIDEACTION_BASELINE: int = 0

_OVERRIDEACTION_EXPECTED_PER_FILE: dict[str, int] = {}

# ── kind='gate' routing edge ratchet ───────────────────────────────────

_KIND_GATE_FILES: tuple[str, ...] = ()

_KIND_GATE_BASELINE: int = 0

_KIND_GATE_EXPECTED_PER_FILE: dict[str, int] = {}


def _strip_docstrings_and_comments(content: str) -> str:
    """Return *content* with docstrings and comments removed.

    - Triple-quoted docstrings are removed.
    - Lines starting with ``#`` are removed.
    - Inline ``#`` comments (after code) are stripped.
    """
    # Strip docstrings.
    no_docs = re.sub(r'""".*?"""', '', content, flags=re.DOTALL)
    no_docs = re.sub(r"'''.*?'''", '', no_docs, flags=re.DOTALL)

    lines = no_docs.split("\n")
    clean_lines = []
    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("#"):
            continue
        comment_idx = ln.find("#")
        if comment_idx >= 0:
            ln = ln[:comment_idx]
        clean_lines.append(ln)
    return "\n".join(clean_lines)


def _count_code_refs(filepath: str, pattern: str) -> tuple[int, int]:
    """Return (non_comment_refs, code_only) for *filepath*.

    The code-only count excludes docstrings, comment lines, and
    inline comments.

    *pattern* is the regex to count (e.g. ``GateRecommendation``).
    """
    with open(filepath) as fh:
        content = fh.read()
    clean = _strip_docstrings_and_comments(content)
    total = len(re.findall(pattern, clean))
    return total, total


def _canonical_core_dir() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "arnold_pipelines" / "megaplan" / "_core"


# ═══════════════════════════════════════════════════════════════════════
# GateRecommendation ratchet
# ═══════════════════════════════════════════════════════════════════════

def test_gaterec_ratchet_total_does_not_exceed_baseline():
    """The code-only GateRecommendation count across the allow-listed
    files must not exceed the pinned baseline (post-M3b: 0)."""
    total_code = 0
    for fp in _GATEREC_FILES:
        code, _ = _count_code_refs(fp, r"GateRecommendation")
        total_code += code

    assert total_code <= _GATEREC_BASELINE, (
        f"GateRecommendation code-only ref count {total_code} exceeds "
        f"baseline {_GATEREC_BASELINE} — ratchet FAILED"
    )


def test_gaterec_ratchet_per_file_matches_baseline():
    """Each allow-listed file's code-only count must match its pinned
    baseline. Prevents silent redistribution.  Post-M3b: no files allowed."""
    for fp in _GATEREC_FILES:
        code, _ = _count_code_refs(fp, r"GateRecommendation")
        expected = _GATEREC_EXPECTED_PER_FILE[fp]
        assert code == expected, (
            f"{fp}: code-only count {code} != expected {expected}"
        )


def test_gaterec_no_refs_outside_allow_list():
    """No file under the canonical Megaplan core tree may contain ANY GateRecommendation
    reference in non-comment, non-docstring code.

    Scans every .py file under arnold_pipelines/megaplan/_core (recursively) and
    asserts only the allow-listed files contain the literal string
    ``GateRecommendation`` in code (not comments or docstrings).
    Post-M3b: allow-list is empty — any code reference is a regression.
    """
    repo_root = Path(__file__).resolve().parent.parent
    pipeline_dir = _canonical_core_dir()

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
        clean = _strip_docstrings_and_comments(content)
        if "GateRecommendation" in clean:
            extra_files.append(rel)

    assert not extra_files, (
        f"Unexpected GateRecommendation refs in files outside the "
        f"allow-list: {extra_files}"
    )


# ═══════════════════════════════════════════════════════════════════════
# OverrideAction ratchet
# ═══════════════════════════════════════════════════════════════════════

def test_overrideaction_ratchet_total_does_not_exceed_baseline():
    """The code-only OverrideAction count across the allow-listed
    files must not exceed the pinned baseline (post-M3b: 0)."""
    total_code = 0
    for fp in _OVERRIDEACTION_FILES:
        code, _ = _count_code_refs(fp, r"OverrideAction")
        total_code += code

    assert total_code <= _OVERRIDEACTION_BASELINE, (
        f"OverrideAction code-only ref count {total_code} exceeds "
        f"baseline {_OVERRIDEACTION_BASELINE} — ratchet FAILED"
    )


def test_overrideaction_ratchet_per_file_matches_baseline():
    """Each allow-listed file's code-only count must match its pinned
    baseline.  Post-M3b: no files allowed."""
    for fp in _OVERRIDEACTION_FILES:
        code, _ = _count_code_refs(fp, r"OverrideAction")
        expected = _OVERRIDEACTION_EXPECTED_PER_FILE[fp]
        assert code == expected, (
            f"{fp}: code-only count {code} != expected {expected}"
        )


def test_overrideaction_no_refs_outside_allow_list():
    """No file under the canonical Megaplan core tree may contain ANY OverrideAction
    reference in non-comment, non-docstring code.  Post-M3b: allow-list
    is empty — any code reference is a regression."""
    repo_root = Path(__file__).resolve().parent.parent
    pipeline_dir = _canonical_core_dir()

    exclude_names = {"run_cli.py"}

    extra_files: list[str] = []
    for py_file in sorted(pipeline_dir.rglob("*.py")):
        if py_file.name in exclude_names:
            continue
        rel = str(py_file.relative_to(repo_root))
        if rel in _OVERRIDEACTION_FILES:
            continue
        with open(py_file) as fh:
            content = fh.read()
        clean = _strip_docstrings_and_comments(content)
        if "OverrideAction" in clean:
            extra_files.append(rel)

    assert not extra_files, (
        f"Unexpected OverrideAction refs in files outside the "
        f"allow-list: {extra_files}"
    )


# ═══════════════════════════════════════════════════════════════════════
# kind='gate' routing edge ratchet
# ═══════════════════════════════════════════════════════════════════════

def test_kind_gate_ratchet_total_does_not_exceed_baseline():
    """The code-only ``kind='gate'`` count across the allow-listed
    files must not exceed the pinned baseline (post-M3b: 0).

    ``kind='gate'`` routing edges were renamed to ``kind='decision'``
    during M3b (T10/T11/T12).  Any remaining ``kind='gate'`` in
    executable code is a regression."""
    total_code = 0
    for fp in _KIND_GATE_FILES:
        code, _ = _count_code_refs(fp, r"""kind\s*=\s*['"]gate['"]""")
        total_code += code

    assert total_code <= _KIND_GATE_BASELINE, (
        f"kind='gate' code-only ref count {total_code} exceeds "
        f"baseline {_KIND_GATE_BASELINE} — ratchet FAILED"
    )


def test_kind_gate_ratchet_per_file_matches_baseline():
    """Each allow-listed file's code-only count must match its pinned
    baseline.  Post-M3b: no files allowed."""
    for fp in _KIND_GATE_FILES:
        code, _ = _count_code_refs(fp, r"""kind\s*=\s*['"]gate['"]""")
        expected = _KIND_GATE_EXPECTED_PER_FILE[fp]
        assert code == expected, (
            f"{fp}: code-only count {code} != expected {expected}"
        )


def test_kind_gate_no_refs_outside_allow_list():
    """No file under the canonical Megaplan core tree may contain ANY ``kind='gate'``
    routing edge in non-comment, non-docstring code.  Post-M3b: allow-list
    is empty — any ``kind='gate'`` in executable code is a regression."""
    repo_root = Path(__file__).resolve().parent.parent
    pipeline_dir = _canonical_core_dir()

    exclude_names = {"run_cli.py"}

    extra_files: list[str] = []
    for py_file in sorted(pipeline_dir.rglob("*.py")):
        if py_file.name in exclude_names:
            continue
        rel = str(py_file.relative_to(repo_root))
        if rel in _KIND_GATE_FILES:
            continue
        with open(py_file) as fh:
            content = fh.read()
        clean = _strip_docstrings_and_comments(content)
        if re.search(r"""kind\s*=\s*['"]gate['"]""", clean):
            extra_files.append(rel)

    assert not extra_files, (
        f"Unexpected kind='gate' routing edges in files outside the "
        f"allow-list: {extra_files}"
    )
