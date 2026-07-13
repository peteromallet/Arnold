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
``arnold_pipelines/megaplan/`` tree fails the audit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MEGAPLAN_DIR = REPO_ROOT / "arnold" / "pipelines" / "megaplan"


# Files (relative to repo root) where state.json reads have been classified.
AUTHORITY_FILES = {
    "arnold_pipelines/megaplan/control.py",
    "arnold_pipelines/megaplan/store/plan_repository.py",
    "arnold_pipelines/megaplan/handlers/execute.py",
    "arnold_pipelines/megaplan/_core/state.py",
    "arnold_pipelines/megaplan/orchestration/tiebreaker.py",
    "arnold_pipelines/megaplan/prompts/tiebreaker_orchestrator.py",
}

CACHE_TOLERANT_FILES = {
    "arnold_pipelines/megaplan/bakeoff/metrics.py",
    "arnold_pipelines/megaplan/receipts/report.py",
    "arnold_pipelines/megaplan/receipts/extractors.py",
    "arnold_pipelines/megaplan/cli/status_view.py",
    "arnold_pipelines/megaplan/cli/__init__.py",
    "arnold_pipelines/megaplan/cli/feedback.py",
    "arnold_pipelines/megaplan/observability/doctor.py",
    "arnold_pipelines/megaplan/observability/cost.py",
    "arnold_pipelines/megaplan/observability/introspect.py",
    "arnold_pipelines/megaplan/bakeoff/judge.py",
    "arnold_pipelines/megaplan/store/warrant_sources.py",
}

DORMANT_FILES = {
    "arnold_pipelines/megaplan/auto.py",
}

# state_store.py is the new R1 backend module — its reads are routed via
# its own protocol (ForwardOnlyStateStoreBackend / ReversibleStateStoreBackend);
# state.py owns the writer (atomic_write_json) and read sites outside the
# 8-reader allowlist (snapshot/restore plumbing — they are write-side I/O).
INFRA_ALLOWED_FILES = {
    "arnold_pipelines/megaplan/_core/io.py",  # defines read_plan_state_cached itself
    "arnold_pipelines/megaplan/_core/state.py",  # writer/snapshot plumbing
    "arnold_pipelines/megaplan/_core/state_store.py",  # backend protocol
    "arnold_pipelines/megaplan/_pipeline/executor.py",  # forensic backup path
    "arnold_pipelines/megaplan/_pipeline/resume.py",  # resume cursor probe
    "arnold_pipelines/megaplan/_pipeline/run_cli.py",  # CLI resume probe
    "arnold_pipelines/megaplan/_pipeline/types.py",  # in-process phase dispatch reads live state
    "arnold_pipelines/megaplan/stages/inprocess_step.py",  # in-process driver
    "arnold_pipelines/megaplan/chain/__init__.py",  # chain runner state probes
    "arnold_pipelines/megaplan/supervisor/chain_runner.py",  # supervisor chain state probes
    # write paths / fixture/manifest references / non-reader callers
    "arnold_pipelines/megaplan/observability/fold.py",  # WAL fold authority itself
    "arnold_pipelines/megaplan/bakeoff/merge.py",  # rewrite helper
    "arnold_pipelines/megaplan/orchestration/phase_result.py",  # write path
    "arnold_pipelines/megaplan/workers/_impl.py",  # worker write path
    "arnold_pipelines/megaplan/handlers/init.py",  # artifact manifest string
    "arnold_pipelines/megaplan/loop/handlers.py",  # loop artifact manifest strings
    "arnold_pipelines/megaplan/loop/engine.py",  # loop engine write path
    # test infra (not the megaplan reader surface)
    "arnold_pipelines/megaplan/tests/agentic/adapter.py",
    "arnold_pipelines/megaplan/agent/tests/test_benchmark_scoring.py",
    "arnold_pipelines/megaplan/agent/tests/test_evals/test_run_evals.py",
}

ALLOWED_FILES = (
    AUTHORITY_FILES | CACHE_TOLERANT_FILES | DORMANT_FILES | INFRA_ALLOWED_FILES
)

STATE_JSON_PATTERN = re.compile(r'["\']state\.json["\']')


def _parse_line_range(line_range: str) -> set[int]:
    lines: set[int] = set()
    for chunk in line_range.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start_text, end_text = chunk.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            lines.update(range(start, end + 1))
        else:
            lines.add(int(chunk))
    return lines


def _inventory_lines_by_file():
    from arnold_pipelines.megaplan.orchestration.authority_readers import AUTHORITY_ROUTES

    lines_by_file: dict[str, set[int]] = {}
    for route in AUTHORITY_ROUTES:
        lines_by_file.setdefault(route.file, set()).update(_parse_line_range(route.line_range))
    return lines_by_file


RAW_AUTHORITY_GREP_PATTERNS = (
    re.compile(r'task\.get\("status"\)\s*==\s*"done"'),
    re.compile(r'task\.get\("status"\)\s*!=\s*"done"'),
    re.compile(r'task\.get\("status"\)\s*in\s*\{"done",\s*"skipped"\}'),
    re.compile(r't\.get\("status"\)\s*==\s*"done"'),
    re.compile(r't\.get\("status"\)\s*in\s*\{"done",\s*"skipped"\}'),
    re.compile(r"terminal_status\s*==\s*\"done\""),
    re.compile(r"status\s+in\s+\{\"done\",\s*\"finalized\"\}"),
    re.compile(r"\bcompute_verdict\("),
)


RAW_AUTHORITY_AUDIT_FILES = {
    "arnold_pipelines/megaplan/execute/batch.py",
    "arnold_pipelines/megaplan/execute/_binding/reducer.py",
    "arnold_pipelines/megaplan/execute/timeout.py",
    "arnold_pipelines/megaplan/prompts/execute.py",
    "arnold_pipelines/megaplan/auto.py",
    "arnold_pipelines/megaplan/chain/__init__.py",
    "arnold_pipelines/megaplan/orchestration/completion_contract.py",
    "arnold_pipelines/megaplan/cli/status_view.py",
}


# Raw-status reads that are intentionally non-authority in current production code.
NON_AUTHORITY_RAW_STATUS_SNIPPETS = {
    "arnold_pipelines/megaplan/execute/_binding/reducer.py": {
        'if task.get("status") == "done":',
        'if task.get("id") == task_id and task.get("status") in {"done", "skipped"}',
    },
    "arnold_pipelines/megaplan/execute/timeout.py": {
        'if task.get("status") != "done":',
    },
}


INVENTORIED_RAW_AUTHORITY_SNIPPETS = {
    "arnold_pipelines/megaplan/auto.py": {
        'if terminal_status == "done":': "RESUME-04",
        'elif terminal_status == "done":': "RESUME-04",
        "verdict = compute_verdict(": "STATUS-05",
    },
    "arnold_pipelines/megaplan/chain/__init__.py": {
        "verdict = compute_verdict(": "STATUS-06",
        'if status == "done":': "CHAIN-02",
    },
    "arnold_pipelines/megaplan/cli/status_view.py": {
        'tasks_done = sum(1 for t in tasks if t.get("status") == "done")': "STATUS-01",
        'if t.get("status") in {"done", "skipped"} and isinstance(t.get("id"), str)': "STATUS-01",
    },
    "arnold_pipelines/megaplan/execute/batch.py": {
        'task.get("status") in {"done", "skipped"}': "EXEC-03",
        'any_done = any(task.get("status") == "done" for task in tracked_tasks)': "EXEC-03",
    },
    "arnold_pipelines/megaplan/orchestration/completion_contract.py": {
        "def compute_verdict(": "STATUS-04",
    },
    "arnold_pipelines/megaplan/prompts/execute.py": {
        'done_tasks = [task for task in tasks if task.get("status") in ("done", "skipped")]': "EXEC-09",
    },
    "arnold_pipelines/megaplan/execute/timeout.py": {
        'if t.get("status") in {"done", "skipped"}': "EXEC-08",
        'raw_terminal_tasks = [t for t in tasks if t.get("status") in {"done", "skipped"}]': "EXEC-08",
    },
}


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
    auto_path = REPO_ROOT / "arnold_pipelines/megaplan/auto.py"
    text = auto_path.read_text(encoding="utf-8")
    expected_marker = "# dormant-path: subprocess seam, retired at M6"
    count = text.count(expected_marker)
    # 10 dormant reads per the Step 20 inventory.
    assert count >= 10, (
        f"arnold_pipelines/megaplan/auto.py: expected ≥10 `{expected_marker}` annotations, "
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


# ── M2: authority-reader route inventory audit ──────────────────────────


def test_m2_authority_readers_inventory_exists():
    """The M2 authority route inventory module must be importable and non-empty."""
    from arnold_pipelines.megaplan.orchestration.authority_readers import (
        AUTHORITY_ROUTES,
    )
    assert AUTHORITY_ROUTES, "AUTHORITY_ROUTES inventory must not be empty"
    assert len(AUTHORITY_ROUTES) >= 20, (
        f"Expected ≥20 routes in the inventory; found {len(AUTHORITY_ROUTES)}"
    )


def test_m2_authority_readers_every_route_has_disposition_and_reason():
    """Every route must have a valid disposition and a non-empty owner_or_reason."""
    from arnold_pipelines.megaplan.orchestration.authority_readers import (
        AUTHORITY_ROUTES,
        ENFORCED,
        WARN_ONLY,
        SHADOW_ONLY,
        DEFERRED,
        INFORMATIONAL,
    )

    valid_dispositions = {ENFORCED, WARN_ONLY, SHADOW_ONLY, DEFERRED, INFORMATIONAL}
    for route in AUTHORITY_ROUTES:
        assert route.disposition in valid_dispositions, (
            f"Route {route.id}: disposition {route.disposition!r} not in "
            f"{sorted(valid_dispositions)!r}"
        )
        assert route.owner_or_reason.strip(), (
            f"Route {route.id}: owner_or_reason must not be empty "
            f"(disposition={route.disposition!r})"
        )
        assert route.id.strip(), (
            f"Route has empty id (file={route.file}, desc={route.description!r})"
        )
        assert route.file.strip(), (
            f"Route {route.id}: file must not be empty"
        )
        assert route.description.strip(), (
            f"Route {route.id}: description must not be empty"
        )
        assert route.route_family.strip(), (
            f"Route {route.id}: route_family must not be empty"
        )


def test_m2_authority_readers_no_unclassified_routes():
    """No route may have an unrecognized disposition."""
    from arnold_pipelines.megaplan.orchestration.authority_readers import (
        AUTHORITY_ROUTES,
        ENFORCED,
        WARN_ONLY,
        SHADOW_ONLY,
        DEFERRED,
        INFORMATIONAL,
    )

    for route in AUTHORITY_ROUTES:
        assert route.disposition in {ENFORCED, WARN_ONLY, SHADOW_ONLY, DEFERRED, INFORMATIONAL}, (
            f"Route {route.id}: unrecognized disposition {route.disposition!r}"
        )


def test_m2_authority_readers_required_families_present():
    """All Step 1 route families must be represented: execute, resume, chain,
    supervisor, status, timeout."""
    from arnold_pipelines.megaplan.orchestration.authority_readers import (
        AUTHORITY_ROUTES,
    )

    families = {r.route_family for r in AUTHORITY_ROUTES}
    required = {"execute", "resume", "chain", "supervisor", "status", "timeout"}
    missing = required - families
    assert not missing, (
        f"M2 inventory is missing required route families: {sorted(missing)}. "
        f"Present: {sorted(families)}"
    )


def test_m2_authority_readers_execute_routes_have_key_sites():
    """Verify key execute authority-increasing sites are inventoried."""
    from arnold_pipelines.megaplan.orchestration.authority_readers import (
        AUTHORITY_ROUTES,
    )

    execute_routes = [r for r in AUTHORITY_ROUTES if r.route_family == "execute"]
    execute_files = {r.file for r in execute_routes}
    required_files = {
        "arnold_pipelines/megaplan/execute/batch.py",
        "arnold_pipelines/megaplan/_core/io.py",
        "arnold_pipelines/megaplan/_core/scheduler/topo.py",
        "arnold_pipelines/megaplan/execute/_binding/reducer.py",
        "arnold_pipelines/megaplan/execute/timeout.py",
        "arnold_pipelines/megaplan/prompts/execute.py",
    }
    missing = required_files - execute_files
    assert not missing, (
        f"Execute inventory missing required files: {sorted(missing)}. "
        f"Present: {sorted(execute_files)}"
    )


def test_m2_authority_readers_resume_routes_have_key_sites():
    """Verify key resume/redrive authority-increasing sites are inventoried."""
    from arnold_pipelines.megaplan.orchestration.authority_readers import (
        AUTHORITY_ROUTES,
    )

    resume_routes = [r for r in AUTHORITY_ROUTES if r.route_family == "resume"]
    resume_files = {r.file for r in resume_routes}
    required_files = {
        "arnold_pipelines/megaplan/_core/workflow.py",
        "arnold_pipelines/megaplan/_pipeline/resume.py",
        "arnold_pipelines/megaplan/auto.py",
    }
    missing = required_files - resume_files
    assert not missing, (
        f"Resume inventory missing required files: {sorted(missing)}. "
        f"Present: {sorted(resume_files)}"
    )


def test_m2_authority_readers_chain_routes_have_key_sites():
    """Verify key chain authority-increasing sites are inventoried."""
    from arnold_pipelines.megaplan.orchestration.authority_readers import (
        AUTHORITY_ROUTES,
    )

    chain_routes = [r for r in AUTHORITY_ROUTES if r.route_family == "chain"]
    chain_files = {r.file for r in chain_routes}
    assert "arnold_pipelines/megaplan/chain/__init__.py" in chain_files, (
        f"Chain inventory missing chain/__init__.py. Present: {sorted(chain_files)}"
    )


def test_m2_authority_readers_supervisor_routes_have_key_sites():
    """Verify key supervisor authority-increasing sites are inventoried."""
    from arnold_pipelines.megaplan.orchestration.authority_readers import (
        AUTHORITY_ROUTES,
    )

    supervisor_routes = [r for r in AUTHORITY_ROUTES if r.route_family == "supervisor"]
    supervisor_files = {r.file for r in supervisor_routes}
    assert "arnold_pipelines/megaplan/supervisor/chain_runner.py" in supervisor_files, (
        f"Supervisor inventory missing chain_runner.py. Present: {sorted(supervisor_files)}"
    )


def test_m2_authority_readers_status_routes_are_deferred_or_informational():
    """Status/shadow routes must be deferred or informational, not enforced or warn-only."""
    from arnold_pipelines.megaplan.orchestration.authority_readers import (
        AUTHORITY_ROUTES,
        ENFORCED,
        WARN_ONLY,
    )

    for route in AUTHORITY_ROUTES:
        if route.route_family == "status":
            assert route.disposition not in (ENFORCED, WARN_ONLY), (
                f"Route {route.id}: status/informational route should not be "
                f"marked '{route.disposition}' — status/shadow reads are "
                f"fail-open and non-blocking (SD3)"
            )


def test_m2_authority_readers_deferred_routes_have_explicit_reasons():
    """Every deferred route must carry an explicit deferral reason in owner_or_reason."""
    from arnold_pipelines.megaplan.orchestration.authority_readers import (
        AUTHORITY_ROUTES,
        DEFERRED,
    )

    for route in AUTHORITY_ROUTES:
        if route.disposition == DEFERRED:
            assert route.owner_or_reason.strip(), (
                f"Route {route.id}: deferred routes must have an explicit "
                f"deferral reason in owner_or_reason"
            )
    deferred = [r for r in AUTHORITY_ROUTES if r.disposition == DEFERRED]
    assert deferred, (
        "Expected at least one deferred route (shadow verdict, completion contract, etc.)"
    )


def test_m2_authority_reader_grep_audit_classifies_all_raw_authority_patterns():
    """Every grep-visible raw terminal/milestone authority pattern must be classified.

    Production occurrences must either:
    - land inside an inventoried authority route line range, or
    - be explicitly documented here as informational/non-authority.
    """
    from arnold_pipelines.megaplan.orchestration.authority_readers import AUTHORITY_ROUTES

    route_ids = {route.id for route in AUTHORITY_ROUTES}
    unclassified: list[str] = []

    for rel in sorted(RAW_AUTHORITY_AUDIT_FILES):
        lines = (REPO_ROOT / rel).read_text(encoding="utf-8").splitlines()
        non_authority_snippets = NON_AUTHORITY_RAW_STATUS_SNIPPETS.get(rel, set())
        inventoried_snippets = INVENTORIED_RAW_AUTHORITY_SNIPPETS.get(rel, {})
        for lineno, line in enumerate(lines, start=1):
            if not any(pattern.search(line) for pattern in RAW_AUTHORITY_GREP_PATTERNS):
                continue
            stripped = line.strip()
            if stripped in non_authority_snippets:
                continue
            route_id = inventoried_snippets.get(stripped)
            if route_id is not None:
                assert route_id in route_ids, f"{rel}: expected inventory route {route_id} for {stripped!r}"
                continue
            unclassified.append(f"{rel}:{lineno}: {stripped}")

    assert not unclassified, (
        "Unclassified raw terminal/milestone authority grep hits found. "
        "Each production occurrence must be inventoried as migrated/deferred/"
        "informational or documented as non-authority:\n"
        + "\n".join(f"  {entry}" for entry in unclassified)
    )


def test_m2_completion_contract_and_shadow_routes_remain_deferred_infrastructure():
    """Completion verdict readers stay shadow/evidence infrastructure in M2."""
    from arnold_pipelines.megaplan.orchestration.authority_readers import (
        AUTHORITY_ROUTES,
        DEFERRED,
    )

    routes_by_id = {route.id: route for route in AUTHORITY_ROUTES}
    expected_deferred = {"STATUS-02", "STATUS-03", "STATUS-04", "STATUS-05", "STATUS-06"}
    assert expected_deferred <= routes_by_id.keys()

    for route_id in sorted(expected_deferred):
        route = routes_by_id[route_id]
        assert route.disposition == DEFERRED, (
            f"{route_id} must remain deferred shadow/evidence infrastructure "
            f"in M2, not enforcement authority."
        )
        reason = route.owner_or_reason.lower()
        assert (
            "shadow" in reason
            or "fail-open" in reason
            or "deferred" in reason
            or "enforcement" in reason
        ), f"{route_id} reason should explain its shadow/evidence-only role: {route.owner_or_reason!r}"

    completion_contract_route = routes_by_id["STATUS-04"]
    assert completion_contract_route.file == (
        "arnold_pipelines/megaplan/orchestration/completion_contract.py"
    )
    assert "compute_verdict" in completion_contract_route.description


def test_m2_informational_status_read_remains_fail_open():
    """Operator-facing raw status reads must remain informational, not authority."""
    from arnold_pipelines.megaplan.orchestration.authority_readers import (
        AUTHORITY_ROUTES,
        INFORMATIONAL,
        ENFORCED,
        WARN_ONLY,
    )

    status_route = next(route for route in AUTHORITY_ROUTES if route.id == "STATUS-01")
    assert status_route.file == "arnold_pipelines/megaplan/cli/status_view.py"
    assert status_route.disposition == INFORMATIONAL
    assert status_route.disposition not in {ENFORCED, WARN_ONLY}
    assert "does not skip" in status_route.owner_or_reason.lower()
