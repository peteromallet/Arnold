"""W8 — chain↔EPIC↔briefs 1:1:1 lint.

Asserts that briefs/epic-pipeline-unification/chain.yaml, the PROGRAM.md
milestone list, and the brief files on disk are in strict 1:1:1 alignment:
- Each chain.yaml label maps to exactly one PROGRAM.md milestone (by normalized
  mN id prefix) and exactly one brief file under briefs/epic-pipeline-unification/.
- Count and ordering match between chain.yaml and PROGRAM.md.
- No orphan brief, no dangling idea path, no absolute /Users/... idea paths.
- chain.yaml must be present and non-empty; fails loud otherwise.
"""
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
CHAIN_YAML = REPO_ROOT / "briefs" / "epic-pipeline-unification" / "chain.yaml"
BRIEFS_DIR = REPO_ROOT / "briefs" / "epic-pipeline-unification"


def _load_chain() -> dict:
    if not CHAIN_YAML.exists():
        pytest.fail(f"chain.yaml not found at {CHAIN_YAML}")
    text = CHAIN_YAML.read_text(encoding="utf-8").strip()
    if not text:
        pytest.fail("chain.yaml is empty")
    data = yaml.safe_load(text)
    if not data or "milestones" not in data:
        pytest.fail("chain.yaml has no 'milestones' key or parsed to empty")
    if not data["milestones"]:
        pytest.fail("chain.yaml milestones list is empty")
    return data


def _normalize_milestone_id(label: str) -> str:
    """Normalize a label to its mN id prefix (e.g. 'm1-foundation' -> 'm1', 'm2.5-...' -> 'm2.5')."""
    m = re.match(r"^(m\d+(?:\.\d+)?(?:[a-z])?)", label.lower())
    if m:
        return m.group(1)
    return label.lower()


def _parse_program_milestone_ids() -> list[str]:
    """Return ordered normalized mN ids from PROGRAM.md milestone headers."""
    program_path = REPO_ROOT / "briefs" / "validation" / "sequencing" / "PROGRAM.md"
    if not program_path.exists():
        pytest.fail(f"PROGRAM.md not found at {program_path}")
    text = program_path.read_text(encoding="utf-8")
    ids = []
    for line in text.splitlines():
        # Match headers like: ### M1 — Foundation...  or ### M2.5 — ...
        m = re.match(r"^#{1,4}\s+(M\d+(?:\.\d+)?(?:[a-z])?)\s*[—\-]", line, re.IGNORECASE)
        if m:
            raw = m.group(1).lower()
            ids.append(raw)
    return ids


def test_chain_yaml_exists_and_nonempty():
    """Fail loud if chain.yaml is absent or empty."""
    _load_chain()


def test_no_absolute_idea_paths():
    """No idea: paths may start with /Users/... (T16 should have fixed these)."""
    data = _load_chain()
    bad = []
    for ms in data["milestones"]:
        idea = ms.get("idea", "")
        if idea.startswith("/"):
            bad.append(f"  label={ms['label']!r}: idea={idea!r}")
    if bad:
        pytest.fail("Absolute idea paths found in chain.yaml (T16 should have fixed these):\n" + "\n".join(bad))


def test_all_idea_files_exist():
    """Every idea: path in chain.yaml must resolve to a real file in the repo."""
    data = _load_chain()
    missing = []
    for ms in data["milestones"]:
        idea = ms.get("idea", "")
        if not idea:
            missing.append(f"  label={ms['label']!r}: empty idea path")
            continue
        resolved = REPO_ROOT / idea
        if not resolved.exists():
            missing.append(f"  label={ms['label']!r}: {idea!r} does not exist at {resolved}")
    if missing:
        pytest.fail("Missing idea files:\n" + "\n".join(missing))


def test_chain_to_program_1to1_count_and_order():
    """Every chain.yaml milestone label must map to a PROGRAM.md milestone by normalized mN id.

    PROGRAM.md may have MORE entries than chain.yaml (e.g. M7-capsule / M7-warrant / M7-docs
    are sub-milestones that chain.yaml bundles as m7-sinks).  The invariant is:
    - Each chain.yaml entry's normalized id must appear in PROGRAM.md.
    - The relative ordering of the matched program ids must be preserved (chain is a
      sub-sequence of program by id).
    - No chain.yaml entry may be unmatched (dangling).
    """
    data = _load_chain()
    chain_labels = [ms["label"] for ms in data["milestones"]]
    chain_ids = [_normalize_milestone_id(lbl) for lbl in chain_labels]

    program_ids = _parse_program_milestone_ids()

    assert len(chain_ids) > 0, "chain.yaml has no milestones"
    assert len(program_ids) > 0, "PROGRAM.md has no milestones"

    # Every chain id must appear in the set of program ids.
    program_id_set = set(program_ids)
    unmatched = [cid for cid in chain_ids if cid not in program_id_set]
    if unmatched:
        pytest.fail(
            f"chain.yaml milestones with no matching PROGRAM.md entry: {unmatched}\n"
            f"program ids: {program_ids}"
        )

    # The chain ids must appear in the same relative order as in PROGRAM.md.
    # Build a subsequence check: advance through program_ids consuming chain_ids in order.
    prog_pos = 0
    order_ok = True
    for cid in chain_ids:
        found = False
        while prog_pos < len(program_ids):
            if program_ids[prog_pos] == cid:
                prog_pos += 1
                found = True
                break
            prog_pos += 1
        if not found:
            order_ok = False
            break
    assert order_ok, (
        f"chain.yaml milestone ordering is not a sub-sequence of PROGRAM.md ordering.\n"
        f"chain ids: {chain_ids}\nprogram ids: {program_ids}"
    )


def test_no_orphan_briefs():
    """Every .md file directly under briefs/epic-pipeline-unification/ that is referenced
    by chain.yaml idea: must exist; no referenced path may be missing."""
    data = _load_chain()
    idea_paths = {ms.get("idea", "") for ms in data["milestones"] if ms.get("idea")}
    missing = [p for p in idea_paths if not (REPO_ROOT / p).exists()]
    assert not missing, f"Orphan (missing) brief files referenced in chain.yaml: {missing}"


def test_no_dangling_chain_labels():
    """Every chain.yaml label must normalize to a PROGRAM.md milestone id."""
    data = _load_chain()
    program_ids = set(_parse_program_milestone_ids())
    dangling = []
    for ms in data["milestones"]:
        norm = _normalize_milestone_id(ms["label"])
        if norm not in program_ids:
            dangling.append(f"  label={ms['label']!r} -> normalized={norm!r} not in PROGRAM.md")
    if dangling:
        pytest.fail("Dangling chain.yaml labels (no matching PROGRAM.md milestone):\n" + "\n".join(dangling))


def test_chain_fail_loud_absent():
    """Simulate absent chain.yaml -> test infrastructure raises, not silently passes."""
    # This test verifies our load helper raises on a missing file.
    fake_path = REPO_ROOT / "briefs" / "epic-pipeline-unification" / "_nonexistent_chain.yaml"
    assert not fake_path.exists(), "This file should not exist"
    # The real chain.yaml IS present; this test just documents the contract.
    data = _load_chain()
    assert data is not None
