"""Cross-tool WBC constants coherence test (CL5-T7).

Guards the subtle cross-tool invariant between the two WBC-anchored tools:

* ``validate_m6_evidence.py`` pins ``WBC_INTEGRATION_COMMIT`` and the two
  ``WBC_EXPECTED_*_PARENT`` constants to the original merge commit
  ``24afce00`` and its exact parents. These verify **ancestry identity** — an
  immutable historical fact.

* ``verify_m6_prerequisites.py`` sets its own ``WBC_INTEGRATION_COMMIT`` to an
  **intermediate consolidation commit** (a descendant of ``24afce00``) used as
  the file-hash regression baseline. This constant MAY advance HEAD-ward as the
  tracked files evolve, but must always remain a strict descendant of the
  ancestry anchor.

This test enforces all three legs of the invariant so that a future edit cannot
silently break the historical-integration-point guarantee:

1. The validator ancestry commit and both parents are immutably pinned to
   ``24afce00`` / its exact parents.
2. The prerequisite verifier's file-hash baseline uses a DIFFERENT commit than
   the validator (the two tools intentionally diverge).
3. The file-hash rebind target is a strict descendant of the ancestry anchor
   (the lineage chain is coherent in one direction).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "tools"

# The migration ancestry-anchor values the validator must pin (MIGRATION
# RE-CUT 2026-08-10: the omp-replaces-hermes migration squashed the original
# history into baseline root 401c8f8, so the original 24afce00 merge lineage
# is unreachable; the anchor moved to the baseline root, which carries the
# same WBC substrate tree and is a lineage ROOT with no parents).
IMMUTABLE_ANCESTRY_COMMIT = "401c8f8112ba0547b428d84cf6996912fdda8e45"
IMMUTABLE_FIRST_PARENT = ""
IMMUTABLE_SECOND_PARENT = ""


def _load_module(tool_filename: str, module_name: str):
    """Import a tools/ module by filename without executing its CLI guard."""
    spec = importlib.util.spec_from_file_location(
        module_name, TOOLS_DIR / tool_filename
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def validator():
    return _load_module("validate_m6_evidence.py", "t7_validate_m6_evidence")


@pytest.fixture(scope="module")
def prereqs():
    return _load_module("verify_m6_prerequisites.py", "t7_verify_m6_prerequisites")


def _is_ancestor(maybe_ancestor: str, descendant: str) -> bool:
    """Return True if maybe_ancestor is an ancestor of descendant (git)."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", maybe_ancestor, descendant],
        cwd=str(REPO_ROOT),
    )
    # git returns 0 when it IS an ancestor, 1 when it is not, >1 on error.
    return result.returncode == 0


# ── Leg 1: validator ancestry constants are immutably pinned ──────────────


def test_validator_ancestry_commit_immutable(validator):
    """The validator's WBC_INTEGRATION_COMMIT must stay pinned to the anchor."""
    assert validator.WBC_INTEGRATION_COMMIT == IMMUTABLE_ANCESTRY_COMMIT, (
        "validate_m6_evidence.py WBC_INTEGRATION_COMMIT was changed away from "
        "the migration ancestry anchor (baseline root 401c8f8). This constant "
        "verifies ancestry identity (a historical fact) and must NOT be advanced."
    )


def test_validator_first_parent_immutable(validator):
    """The validator's first-parent constant must stay pinned (empty root)."""
    assert validator.WBC_EXPECTED_FIRST_PARENT == IMMUTABLE_FIRST_PARENT, (
        "validate_m6_evidence.py WBC_EXPECTED_FIRST_PARENT was changed. The "
        "migration anchor is a lineage ROOT with no parents."
    )


def test_validator_second_parent_immutable(validator):
    """The validator's second-parent constant must stay pinned (empty root)."""
    assert validator.WBC_EXPECTED_SECOND_PARENT == IMMUTABLE_SECOND_PARENT, (
        "validate_m6_evidence.py WBC_EXPECTED_SECOND_PARENT was changed. The "
        "migration anchor is a lineage ROOT with no parents."
    )


# ── Leg 2: the two tools intentionally use different commits ──────────────


def test_tools_use_different_wbc_commits(validator, prereqs):
    """The prerequisite verifier's baseline must differ from the validator anchor.

    If the two constants ever coincide, the intended semantic split (ancestry
    identity vs file-hash regression) has collapsed.
    """
    assert (
        validator.WBC_INTEGRATION_COMMIT != prereqs.WBC_INTEGRATION_COMMIT
    ), (
        "validate_m6_evidence.py and verify_m6_prerequisites.py share the same "
        "WBC_INTEGRATION_COMMIT. They must use different commits: the validator "
        "pins ancestry identity (baseline root 401c8f8), the verifier tracks "
        "file hashes at the migration's B1-B5 commit (9d374c6)."
    )


# ── Leg 3: the rebind target is a descendant of the ancestry anchor ───────


def test_rebind_target_is_descendant_of_ancestry_anchor(validator, prereqs):
    """The file-hash rebind target must be a descendant of the ancestry anchor.

    This proves the lineage chain is coherent: the verifier's baseline lives
    HEAD-ward of the immutable integration point, so advancing it never escapes
    the ancestry that the validator has already anchored.
    """
    anchor = validator.WBC_INTEGRATION_COMMIT
    rebind = prereqs.WBC_INTEGRATION_COMMIT
    assert _is_ancestor(anchor, rebind), (
        f"verify_m6_prerequisites.py WBC_INTEGRATION_COMMIT {rebind[:8]} is NOT "
        f"a descendant of the validator ancestry anchor {anchor[:8]}. The "
        f"file-hash rebind target must remain within the anchored lineage."
    )


def test_ancestry_anchor_is_ancestor_of_head(validator):
    """The immutable ancestry anchor must itself be an ancestor of HEAD."""
    assert _is_ancestor(validator.WBC_INTEGRATION_COMMIT, "HEAD"), (
        "The ancestry anchor (migration baseline root 401c8f8) is not an "
        "ancestor of HEAD — the pinned historical integration point has been "
        "severed from the live lineage."
    )
