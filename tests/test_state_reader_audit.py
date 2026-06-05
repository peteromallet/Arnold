"""T25 / Step 20: state.json reader-audit grep gate.

Enforces the three allowlists from the R1 authority flip:

- AUTHORITY: 8 readers that MUST route through
  ``read_plan_state_cached(..., mode='authority')``.
- CACHE_TOLERANT: 11 readers that explicitly tolerate cache staleness and
  carry a ``# cache-tolerant:`` annotation at the read site.
- DORMANT_PATH: 10 reads in ``auto.py`` on the subprocess-driver supervision
  seam (retired at M6); each carries the ``# dormant-path: subprocess seam,
  retired at M6`` annotation.

Any other ``read_json(plan_dir / "state.json")``-shaped read found in the
``arnold/pipelines/megaplan/`` tree fails the audit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MEGAPLAN_DIR = REPO_ROOT / "arnold" / "pipelines" / "megaplan"


# Files (relative to repo root) where state.json reads have been classified.
AUTHORITY_FILES = {
    "arnold/pipelines/megaplan/control.py",
    "arnold/pipelines/megaplan/store/plan_repository.py",
    "arnold/pipelines/megaplan/handlers/execute.py",
    "arnold/pipelines/megaplan/_core/state.py",
    "arnold/pipelines/megaplan/orchestration/tiebreaker.py",
    "arnold/pipelines/megaplan/prompts/tiebreaker_orchestrator.py",
}

CACHE_TOLERANT_FILES = {
    "arnold/pipelines/megaplan/bakeoff/metrics.py",
    "arnold/pipelines/megaplan/receipts/report.py",
    "arnold/pipelines/megaplan/receipts/extractors.py",
    "arnold/pipelines/megaplan/cli/status_view.py",
    "arnold/pipelines/megaplan/cli/__init__.py",
    "arnold/pipelines/megaplan/cli/feedback.py",
    "arnold/pipelines/megaplan/observability/doctor.py",
    "arnold/pipelines/megaplan/observability/cost.py",
    "arnold/pipelines/megaplan/observability/introspect.py",
    "arnold/pipelines/megaplan/bakeoff/judge.py",
    "arnold/pipelines/megaplan/store/warrant_sources.py",
}

DORMANT_FILES = {
    "arnold/pipelines/megaplan/auto.py",
    # _legacy_subprocess is the frozen pre-T25 snapshot of auto.py's
    # supervisor loop; its reads are dormant by construction.
    "arnold/pipelines/megaplan/_legacy_subprocess/__init__.py",
}

# state_store.py is the new R1 backend module — its reads are routed via
# its own protocol (ForwardOnlyStateStoreBackend / ReversibleStateStoreBackend);
# state.py owns the writer (atomic_write_json) and read sites outside the
# 8-reader allowlist (snapshot/restore plumbing — they are write-side I/O).
INFRA_ALLOWED_FILES = {
    "arnold/pipelines/megaplan/_core/io.py",  # defines read_plan_state_cached itself
    "arnold/pipelines/megaplan/_core/state.py",  # writer/snapshot plumbing
    "arnold/pipelines/megaplan/_core/state_store.py",  # backend protocol
    "arnold/pipelines/megaplan/_pipeline/executor.py",  # forensic backup path
    "arnold/pipelines/megaplan/_pipeline/resume.py",  # resume cursor probe
    "arnold/pipelines/megaplan/_pipeline/run_cli.py",  # CLI resume probe
    "arnold/pipelines/megaplan/_pipeline/types.py",  # in-process phase dispatch reads live state
    "arnold/pipelines/megaplan/stages/inprocess_step.py",  # in-process driver
    "arnold/pipelines/megaplan/chain/__init__.py",  # chain runner state probes
    "arnold/pipelines/megaplan/supervisor/chain_runner.py",  # supervisor chain state probes
    # write paths / fixture/manifest references / non-reader callers
    "arnold/pipelines/megaplan/observability/fold.py",  # WAL fold authority itself
    "arnold/pipelines/megaplan/bakeoff/merge.py",  # rewrite helper
    "arnold/pipelines/megaplan/orchestration/phase_result.py",  # write path
    "arnold/pipelines/megaplan/workers/_impl.py",  # worker write path
    "arnold/pipelines/megaplan/handlers/init.py",  # artifact manifest string
    "arnold/pipelines/megaplan/loop/handlers.py",  # loop artifact manifest strings
    "arnold/pipelines/megaplan/loop/engine.py",  # loop engine write path
    # test infra (not the megaplan reader surface)
    "arnold/pipelines/megaplan/tests/agentic/adapter.py",
    "arnold/pipelines/megaplan/agent/tests/test_benchmark_scoring.py",
    "arnold/pipelines/megaplan/agent/tests/test_evals/test_run_evals.py",
}

ALLOWED_FILES = (
    AUTHORITY_FILES | CACHE_TOLERANT_FILES | DORMANT_FILES | INFRA_ALLOWED_FILES
)

STATE_JSON_PATTERN = re.compile(r'["\']state\.json["\']')


def _iter_megaplan_py_files() -> list[Path]:
    return [
        p
        for p in MEGAPLAN_DIR.rglob("*.py")
        if "__pycache__" not in p.parts
    ]


def test_authority_files_route_through_read_plan_state_cached():
    """The 8 authority readers must call ``read_plan_state_cached``."""
    for rel in AUTHORITY_FILES:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "read_plan_state_cached" in text, (
            f"{rel}: expected `read_plan_state_cached(..., mode='authority')` "
            "but it was not found — authority allowlist violated."
        )
        assert 'mode="authority"' in text or "mode='authority'" in text, (
            f"{rel}: must read with mode='authority'."
        )


def test_cache_tolerant_files_carry_annotation():
    """The 11 cache-tolerant readers must carry a ``# cache-tolerant:`` tag."""
    for rel in CACHE_TOLERANT_FILES:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "# cache-tolerant:" in text, (
            f"{rel}: missing `# cache-tolerant:` annotation at the read site."
        )


def test_dormant_path_reads_carry_annotation():
    """All auto.py state.json reads must carry the dormant-path annotation."""
    auto_path = REPO_ROOT / "arnold/pipelines/megaplan/auto.py"
    text = auto_path.read_text(encoding="utf-8")
    expected_marker = "# dormant-path: subprocess seam, retired at M6"
    count = text.count(expected_marker)
    # 10 dormant reads per the Step 20 inventory.
    assert count >= 10, (
        f"arnold/pipelines/megaplan/auto.py: expected ≥10 `{expected_marker}` annotations, "
        f"found {count}."
    )


def test_no_unclassified_state_json_reads_in_megaplan_tree():
    """No `state.json` read may appear outside the three allowlists."""
    unclassified: list[tuple[str, int, str]] = []
    for path in _iter_megaplan_py_files():
        rel = str(path.relative_to(REPO_ROOT))
        if rel in ALLOWED_FILES:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if STATE_JSON_PATTERN.search(line):
                unclassified.append((rel, lineno, line.strip()))
    assert not unclassified, (
        "Unclassified `state.json` reads found — extend one of the three "
        "allowlists (AUTHORITY / CACHE_TOLERANT / DORMANT) or route through "
        "`read_plan_state_cached`:\n"
        + "\n".join(f"  {rel}:{ln}: {src}" for rel, ln, src in unclassified)
    )


def test_three_allowlists_are_disjoint():
    assert not (AUTHORITY_FILES & CACHE_TOLERANT_FILES)
    assert not (AUTHORITY_FILES & DORMANT_FILES)
    assert not (CACHE_TOLERANT_FILES & DORMANT_FILES)
