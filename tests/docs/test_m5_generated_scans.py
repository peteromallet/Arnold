from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

ACTIVE_DOC_PATHS = (
    Path("docs/arnold/workflow-runtime.md"),
    Path("docs/arnold/workflow-manifest.md"),
    Path("docs/arnold/workflow-manifest-amendments.md"),
    Path("docs/arnold/m5-pipeline-disposition.md"),
    Path("docs/arnold/m5-cli-command-mapping.md"),
    Path("docs/arnold/m5-cli-dispatch-chain.md"),
    Path("docs/arnold/m5-generated-artifact-manifest.md"),
    Path("docs/arnold/m5-script-tool-inventory.md"),
    Path("docs/arnold/m5-package-build-inventory.md"),
    Path("docs/arnold/m5-legacy-test-inventory.md"),
    Path("docs/arnold/m6-deletion-list.md"),
)

# Docs/files that intentionally contain legacy API examples or old command
# strings and are tracked for migration in later phases.
ARCHIVAL_OR_PENDING_PATHS = (
    Path("docs/arnold/authoring-guide.md"),
    Path("docs/arnold/creating-a-new-pipeline.md"),
    Path("docs/arnold/workflow-migration.md"),
    Path("docs/arnold/legacy-surface-inventory.md"),
    Path("docs/arnold/tooling.md"),
    Path("docs/arnold/skill-integration.md"),
    Path("docs/arnold/package-contract.md"),
    Path("docs/arnold/package-authoring-contract.md"),
    Path("docs/arnold/examples/select-tournament.md"),
    Path("docs/arnold/examples/planning-as-composition.md"),
    Path("docs/arnold/examples/jokes.md"),
    Path("docs/arnold/workflow-manifest-runtime-review"),
    Path("docs/arnold/m5b-plugin-relocation-map.md"),
    Path("docs/arnold/megaplan-plugin-clean-gap.md"),
    Path("docs/arnold/megaplan-plugin-clean-codex-assessment.md"),
    Path("docs/arnold/arnold-megaplan-cleanup-plan.md"),
    Path("docs/arnold/arnold-megaplan-subagent-review-synthesis.md"),
    Path("docs/arnold/arnold-abstraction-vetting-synthesis.md"),
    Path("docs/arnold/human-interaction-decision.md"),
    Path("docs/arnold/state-authority-migration.md"),
    Path("docs/arnold/runtime-salvage-deletion-map.md"),
    Path("docs/arnold/branch-transplant-audit.md"),
    Path("docs/arnold/clean-extraction-port-ledger.md"),
    Path("docs/arnold/event-journal-spec.md"),
    Path("docs/arnold/package-disposition.md"),
    Path("docs/arnold/package-disposition.yaml"),
    Path("scripts/generate_arnold_docs.py"),
    Path("scripts/check_workflow_pipeline_inventory.py"),
    Path("scripts/check_pipeline_id_registry.py"),
    Path("scripts/backfill_step_receipts.py"),
    Path("scripts/megaplan_live_watchdog.py"),
    Path("scripts/record_workflow_next_parity.py"),
    Path("arnold/pipelines/_template"),
    Path("arnold/pipelines/megaplan/skills"),
    Path("arnold/pipelines/megaplan/data/_codex_skills"),
    Path("arnold/pipelines/folder_audit/skills"),
    Path("arnold_pipelines/megaplan/skills"),
    Path("arnold_pipelines/megaplan/data/_composed"),
    Path("arnold_pipelines/megaplan/data/_codex_skills"),
)

FORBIDDEN_AUTHORING_TERMS = (
    "PipelineBuilder",
    "Stage(",
    "Edge(",
    "@stage",
    "@step",
    "run_pipeline",
    "from arnold.pipeline",
    "import arnold.pipeline",
    "arnold.pipelines.megaplan",
)

FORBIDDEN_COMMAND_TERMS = (
    "arnold pipelines describe",
    "arnold pipelines check",
    "arnold pipelines doctor",
    "arnold pipelines new",
    "arnold pipeline ",
)

_FENCE_RE = re.compile(r"```python\n(.*?)\n```", re.DOTALL)


def _is_archival_or_pending(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT)
    for prefix in ARCHIVAL_OR_PENDING_PATHS:
        if rel == prefix or str(rel).startswith(str(prefix) + "/"):
            return True
    return False


def _extract_python_fences(text: str) -> list[str]:
    return [match.group(1) for match in _FENCE_RE.finditer(text)]


def _is_migration_context_line(line: str) -> bool:
    lowered = line.lower()
    return any(
        marker in lowered
        for marker in (
            "legacy",
            "migration",
            "delete",
            "archival",
            "m4",
            "m5",
            "m6",
            "old command",
            "disposition",
            "relocates",
            "transition",
            "must not",
            "old ",
            "arnold_pipelines.megaplan",
        )
    )


def test_active_docs_do_not_teach_banned_authoring_or_commands() -> None:
    violations: list[str] = []
    for relative in ACTIVE_DOC_PATHS:
        path = REPO_ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        in_fence = False
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence or stripped.startswith("|"):
                continue
            if _is_migration_context_line(line):
                continue
            for term in FORBIDDEN_AUTHORING_TERMS + FORBIDDEN_COMMAND_TERMS:
                if term in line:
                    violations.append(f"{path}:{lineno}: {term!r}")
    assert not violations, "banned authoring/command language in active docs:\n" + "\n".join(violations)


def test_active_doc_python_fences_compile() -> None:
    failures: list[str] = []
    for relative in ACTIVE_DOC_PATHS:
        path = REPO_ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for index, snippet in enumerate(_extract_python_fences(text), start=1):
            try:
                compile(snippet, f"{path}:{index}", "exec")
            except SyntaxError as exc:
                failures.append(f"{path} fence {index}: {exc}")
    assert not failures, "active doc code fences with syntax errors:\n" + "\n".join(failures)


def test_generator_source_does_not_add_new_forbidden_patterns() -> None:
    """Flag forbidden patterns in generator source outside pending-migration files."""

    violations: list[str] = []
    for path in sorted((REPO_ROOT / "scripts").rglob("*.py")):
        if _is_archival_or_pending(path):
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for term in FORBIDDEN_AUTHORING_TERMS:
                if term in line:
                    violations.append(f"{path}:{lineno}: {term!r}")
    assert not violations, "forbidden authoring patterns in generator scripts:\n" + "\n".join(violations)


def test_skills_and_composed_rules_are_scanned() -> None:
    """Every SKILL.md and composed rule file is reachable and has no unexpected old API."""

    skill_paths = sorted(REPO_ROOT.rglob("SKILL.md"))
    composed_paths = list((REPO_ROOT / "arnold_pipelines" / "megaplan" / "data" / "_composed").rglob("*"))
    if not skill_paths and not composed_paths:
        pytest.skip("no SKILL.md or composed rule files discovered")

    violations: list[str] = []
    for path in skill_paths + composed_paths:
        if path.suffix not in {".md", ".json", ".yaml", ".yml"}:
            continue
        if _is_archival_or_pending(path):
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for term in FORBIDDEN_AUTHORING_TERMS + FORBIDDEN_COMMAND_TERMS:
                if term in line:
                    violations.append(f"{path}:{lineno}: {term!r}")
    assert not violations, "forbidden patterns in active skills/composed rules:\n" + "\n".join(violations)
