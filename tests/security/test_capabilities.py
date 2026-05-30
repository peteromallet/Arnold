"""Tests for vibecomfy.security.capabilities.

Covers:
- Every mirrored _OUTPUT_CLASSES and OUTPUT_NODE_NAMES entry maps to filesystem_write.
- CLIPTextEncode, KSampler, VAEDecode map to passthrough.
- Unknown class returns documented default (code_exec quarantine).
- Taxonomy values are frozenset.
- No forbidden imports in security/__init__.py or capabilities.py source.
- ≥95% of mirrored ALL_SEEDED classes have explicit taxonomy entries (should-level).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

from vibecomfy.security import CAPABILITY_TAXONOMY, capabilities_for, is_side_effecting, unknown_class_policy
from vibecomfy.security._seed import (
    ALL_SEEDED,
    KNOWN_PASSTHROUGH,
    OUTPUT_NODE_NAMES,
    _OUTPUT_CLASSES_KEYS,
)


# ── Source-level import hygiene ──────────────────────────────────────────────

FORBIDDEN_IMPORT_PATTERNS: list[str] = [
    r"from\s+vibecomfy\.analysis\b",
    r"from\s+vibecomfy\.runtime\b",
    r"from\s+vibecomfy\.porting\b",
    r"from\s+vibecomfy\.registry\b",
    r"import\s+vibecomfy\.analysis\b",
    r"import\s+vibecomfy\.runtime\b",
    r"import\s+vibecomfy\.porting\b",
    r"import\s+vibecomfy\.registry\b",
]

SECURITY_DIR = Path(__file__).resolve().parent.parent.parent / "vibecomfy" / "security"
FILES_TO_CHECK: list[Path] = [
    SECURITY_DIR / "__init__.py",
    SECURITY_DIR / "capabilities.py",
]


@pytest.mark.parametrize("file_path", FILES_TO_CHECK)
def test_no_forbidden_imports_in_source(file_path: Path) -> None:
    """Source-level grep: no import from analysis, runtime, porting, or registry."""
    assert file_path.is_file(), f"Missing file: {file_path}"
    source = file_path.read_text()
    for pattern in FORBIDDEN_IMPORT_PATTERNS:
        assert not re.search(pattern, source), (
            f"Forbidden import pattern {pattern!r} found in {file_path.name}"
        )


# ── Output-class nodes → filesystem_write ────────────────────────────────────


def test_output_classes_map_to_filesystem_write() -> None:
    """Every mirrored _OUTPUT_CLASSES key maps to filesystem_write."""
    for class_type in _OUTPUT_CLASSES_KEYS:
        caps = capabilities_for(class_type)
        assert "filesystem_write" in caps, (
            f"{class_type!r} (from _OUTPUT_CLASSES_KEYS) should have filesystem_write, got {caps}"
        )


def test_output_node_names_map_to_filesystem_write() -> None:
    """Every mirrored OUTPUT_NODE_NAMES entry maps to filesystem_write."""
    for class_type in OUTPUT_NODE_NAMES:
        caps = capabilities_for(class_type)
        assert "filesystem_write" in caps, (
            f"{class_type!r} (from OUTPUT_NODE_NAMES) should have filesystem_write, got {caps}"
        )


# ── Known passthrough nodes ──────────────────────────────────────────────────


def test_cliptextencode_is_passthrough() -> None:
    assert capabilities_for("CLIPTextEncode") == frozenset({"passthrough"})


def test_ksampler_is_passthrough() -> None:
    assert capabilities_for("KSampler") == frozenset({"passthrough"})


def test_vaedecode_is_passthrough() -> None:
    assert capabilities_for("VAEDecode") == frozenset({"passthrough"})


# ── Unknown class → quarantine default ───────────────────────────────────────


def test_unknown_class_returns_quarantine_default() -> None:
    caps = capabilities_for("TotallyMadeUpClassNameThatDoesNotExist")
    assert caps == unknown_class_policy(), (
        f"Unknown class should return quarantine default, got {caps}"
    )
    assert "code_exec" in caps


# ── Taxonomy values are frozenset ────────────────────────────────────────────


def test_taxonomy_values_are_frozenset() -> None:
    for class_type, caps in CAPABILITY_TAXONOMY.items():
        assert isinstance(caps, frozenset), (
            f"CAPABILITY_TAXONOMY[{class_type!r}] must be frozenset, got {type(caps).__name__}"
        )


# ── is_side_effecting helper ─────────────────────────────────────────────────


def test_is_side_effecting_passthrough() -> None:
    assert not is_side_effecting("CLIPTextEncode")
    assert not is_side_effecting("KSampler")
    assert not is_side_effecting("VAEDecode")


def test_is_side_effecting_filesystem_write() -> None:
    assert is_side_effecting("SaveImage")
    assert is_side_effecting("VHS_VideoCombine")


def test_is_side_effecting_unknown() -> None:
    assert is_side_effecting("TotallyMadeUpClassNameThatDoesNotExist")


# ── ≥95% coverage check (should-level) ───────────────────────────────────────


def test_seeded_coverage_at_least_95_percent() -> None:
    """Assert that ≥95% of ALL_SEEDED classes have explicit taxonomy entries.

    This is a *should*-level check — soft by default but surfaces gaps.
    Classes in KNOWN_PASSTHROUGH that are not in ALL_SEEDED are excluded
    from the denominator because they are not seeded custom-node classes.

    The remaining classes (not in CAPABILITY_TAXONOMY and not explicitly
    in KNOWN_PASSTHROUGH) are recorded as uncovered.
    """
    covered: set[str] = set(CAPABILITY_TAXONOMY.keys()) | KNOWN_PASSTHROUGH
    all_seeded_set: set[str] = set(ALL_SEEDED)

    # Classes in ALL_SEEDED that have no explicit entry anywhere
    uncovered: set[str] = all_seeded_set - covered
    total: int = len(all_seeded_set)
    covered_count: int = total - len(uncovered)
    coverage_pct: float = (covered_count / total * 100) if total > 0 else 100.0

    # Record uncovered for diagnostics
    if uncovered:
        print(f"\nUncovered ALL_SEEDED classes ({len(uncovered)}):")
        for cls in sorted(uncovered):
            print(f"  - {cls}")

    assert coverage_pct >= 95.0, (
        f"Coverage is {coverage_pct:.1f}% ({covered_count}/{total}); "
        f"must be ≥95%. Uncovered: {sorted(uncovered)}"
    )
