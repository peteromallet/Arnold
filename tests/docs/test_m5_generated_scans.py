from __future__ import annotations

import re
from pathlib import Path

import pytest

from arnold.conformance.authoring_terms import (
    FORBIDDEN_AUTHORING_TERMS,
    FORBIDDEN_COMMAND_TERMS,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

ACTIVE_DOC_PATHS = (
    Path("docs/arnold/workflow-runtime.md"),
    Path("docs/arnold/workflow-manifest.md"),
    Path("docs/arnold/workflow-manifest-amendments.md"),
    Path("docs/arnold/workflow-authoring.md"),
    Path("docs/arnold/workflow-boundary-contracts.md"),
    Path("docs/arnold/package-contract.md"),
    Path("docs/arnold/package-authoring-contract.md"),
    Path("docs/arnold/pattern-stability-matrix.md"),
    Path("docs/arnold/m5-pipeline-disposition.md"),
    Path("docs/arnold/m5-cli-command-mapping.md"),
    Path("docs/arnold/m5-cli-dispatch-chain.md"),
    Path("docs/arnold/m5-generated-artifact-manifest.md"),
    Path("docs/arnold/m5-script-tool-inventory.md"),
    Path("docs/arnold/m5-package-build-inventory.md"),
    Path("docs/arnold/m5-legacy-test-inventory.md"),
    Path("docs/arnold/m6-deletion-list.md"),
)

GENERATED_SCAN_EXCLUDED_PREFIXES = (
    Path(".megaplan/runtime"),
    Path(".megaplan/worker_tmp"),
    Path(".worktrees"),
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
    Path("arnold_pipelines/_template"),
    Path("arnold/pipelines/megaplan/skills"),
    Path("arnold/pipelines/megaplan/data/_codex_skills"),
    Path("arnold/pipelines/folder_audit/skills"),
    Path("arnold_pipelines/megaplan/skills"),
    Path("arnold_pipelines/megaplan/data/_composed"),
    Path("arnold_pipelines/megaplan/data/_codex_skills"),
    Path("docs/archive/m5"),
)

# FORBIDDEN_AUTHORING_TERMS / FORBIDDEN_COMMAND_TERMS are imported above from
# arnold.conformance.authoring_terms — the single source of truth shared with
# the boundary scanners under scripts/. See test_forbidden_terms_single_source.


def test_forbidden_terms_single_source() -> None:
    """Forbidden-terms constants come from one shared module and stay in sync.

    Guards against the drift that caused the baseline loop: a scanner and the
    authoring test carrying independent copies of the same forbidden literal.
    """
    from arnold.conformance import authoring_terms as terms

    # The constants this test relies on ARE the shared module's objects.
    assert FORBIDDEN_AUTHORING_TERMS is terms.FORBIDDEN_AUTHORING_TERMS
    assert FORBIDDEN_COMMAND_TERMS is terms.FORBIDDEN_COMMAND_TERMS

    # Every import-path prefix used by AST scanners must be a member of the
    # canonical authoring set, so scanners cannot forbid (or allow) something
    # the authoring test disagrees with.
    authoring = set(terms.FORBIDDEN_AUTHORING_TERMS)
    for prefix in terms.FORBIDDEN_MEGAPLAN_IMPORT_PREFIXES:
        assert prefix in authoring, f"{prefix!r} not in FORBIDDEN_AUTHORING_TERMS"

_FENCE_RE = re.compile(r"```python\n(.*?)\n```", re.DOTALL)


def _is_archival_or_pending(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT)
    for prefix in ARCHIVAL_OR_PENDING_PATHS:
        if rel == prefix or str(rel).startswith(str(prefix) + "/"):
            return True
    return False


def _is_generated_scan_path(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT)
    for prefix in GENERATED_SCAN_EXCLUDED_PREFIXES:
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
        if _is_generated_scan_path(path):
            continue
        if _is_archival_or_pending(path):
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for term in FORBIDDEN_AUTHORING_TERMS + FORBIDDEN_COMMAND_TERMS:
                if term in line:
                    violations.append(f"{path}:{lineno}: {term!r}")
    assert not violations, "forbidden patterns in active skills/composed rules:\n" + "\n".join(violations)


# ── M6 composition forbidden-pattern extensions ───────────────────────────

_M6_FORBIDDEN_SHIM_FALLBACK = (
    "shim",
    "fallback builder",
    "graph fallback",
    "dual-mode package",
    "compatibility namespace",
    "_legacy.py",
    "temporary wrapper",
    "--driver graph",
)

_M6_FORBIDDEN_DIRECT_AUTHORITY = (
    "hand-authored WorkflowManifest",
    "hand-authored NativeProgram",
    "direct IR construction",
    "native_program as source of truth",
    "native_program defines composition",
)

_M6_REJECTION_MARKERS = (
    "do not",
    "do **not**",
    "must not",
    "cannot",
    "forbidden",
    "prohibited",
    "rejected",
    "invalid",
    "legacy",
    "migration",
    "delete",
    "archival",
    "no longer",
    "banned",
    "non-conformant",
    "not conformant",
    "explicitly disallowed",
    "never",
    "tolerated",
    "bridge debt",
    "not the source-authoritative",
)


def _m6_is_rejection(line: str) -> bool:
    lowered = line.lower()
    # Normalize markdown bold/italic
    lowered = lowered.replace("**", "").replace("*", "").replace("__", "")
    return any(m in lowered for m in _M6_REJECTION_MARKERS)

_M6_COMPOSITION_DOCS = (
    Path("docs/arnold/native-composition-contract.md"),
    Path("docs/arnold/authoring-guide.md"),
    Path("docs/arnold/package-authoring-contract.md"),
    Path("docs/arnold/workflow-authoring.md"),
    Path("docs/arnold/creating-a-new-pipeline.md"),
)

_LEGACY_SCAFFOLD = Path("arnold/pipelines/_template")


def _m6_paragraph_has_rejection(para_lines: list[str]) -> bool:
    """Return True if any line in the paragraph has a rejection marker."""
    return any(_m6_is_rejection(line) for line in para_lines)


def _m6_paragraphs(lines: list[str]) -> list[tuple[int, list[str]]]:
    """Split lines into (start_line, paragraph_lines) groups on blank lines."""
    paragraphs: list[tuple[int, list[str]]] = []
    current: list[str] = []
    start = 1
    for lineno, line in enumerate(lines, start=1):
        if line.strip() == "":
            if current:
                paragraphs.append((start, current))
                current = []
            start = lineno + 1
        else:
            current.append(line)
    if current:
        paragraphs.append((start, current))
    return paragraphs


def test_m6_active_docs_no_forbidden_shim_fallback() -> None:
    """Active composition docs must not teach shim/fallback authority patterns."""
    violations: list[str] = []
    for rel in _M6_COMPOSITION_DOCS:
        p = REPO_ROOT / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        for start, para_lines in _m6_paragraphs(text.splitlines()):
            if _m6_paragraph_has_rejection(para_lines):
                continue
            for offset, line in enumerate(para_lines):
                stripped = line.strip()
                if stripped.startswith("|") or stripped.startswith("```"):
                    continue
                lineno = start + offset
                lowered = line.lower()
                for term in _M6_FORBIDDEN_SHIM_FALLBACK:
                    if term.lower() in lowered:
                        violations.append(f"{rel}:{lineno}: {term!r}")
    assert not violations, "Active docs contain forbidden shim/fallback terms:\n" + "\n".join(violations)


def test_m6_active_docs_no_direct_manifest_authority() -> None:
    """Active composition docs must not teach direct manifest/native_program authority."""
    violations: list[str] = []
    for rel in _M6_COMPOSITION_DOCS:
        p = REPO_ROOT / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        bullets_in_toleration: set[int] = set()
        all_paragraphs = _m6_paragraphs(text.splitlines())
        for i, (start, para_lines) in enumerate(all_paragraphs):
            para_text = " ".join(line.strip() for line in para_lines).lower()
            if "tolerated" in para_text and "bridge debt" in para_text:
                if i + 1 < len(all_paragraphs):
                    next_start, next_lines = all_paragraphs[i + 1]
                    if next_lines and next_lines[0].strip().startswith("-"):
                        for off in range(len(next_lines)):
                            bullets_in_toleration.add(next_start + off)
        for start, para_lines in all_paragraphs:
            if _m6_paragraph_has_rejection(para_lines):
                continue
            for offset, line in enumerate(para_lines):
                stripped = line.strip()
                if stripped.startswith("|") or stripped.startswith("```"):
                    continue
                lineno = start + offset
                if lineno in bullets_in_toleration:
                    continue
                lowered = line.lower()
                for term in _M6_FORBIDDEN_DIRECT_AUTHORITY:
                    if term.lower() in lowered:
                        violations.append(f"{rel}:{lineno}: {term!r}")
    assert not violations, (
        "Active docs contain forbidden direct-manifest authority terms:\n" + "\n".join(violations)
    )


def test_m6_legacy_scaffold_not_resurrected() -> None:
    """The legacy ``arnold/pipelines/_template/`` directory must not exist."""
    assert not (REPO_ROOT / _LEGACY_SCAFFOLD).exists(), (
        f"Legacy scaffold path {_LEGACY_SCAFFOLD} must NOT exist. "
        f"Use active path: arnold_pipelines/_template/"
    )


def test_m6_active_scaffold_not_reference_legacy() -> None:
    """Active scaffold files must not reference the legacy scaffold path."""
    active = REPO_ROOT / "arnold_pipelines" / "_template"
    violations: list[str] = []
    for f in sorted(active.rglob("*")):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        if "arnold/pipelines/_template" in text:
            violations.append(str(f.relative_to(REPO_ROOT)))
    assert not violations, (
        f"Active scaffold references legacy path: {violations}"
    )


def test_m6_scaffold_skill_native_program_substrate() -> None:
    """Scaffold SKILL.md files mentioning native_program must use substrate/dispatch language."""
    active = REPO_ROOT / "arnold_pipelines" / "_template"
    violations: list[str] = []
    for md_file in sorted(active.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8").lower()
        if "native_program" in text:
            if "substrate" not in text and "dispatch" not in text:
                violations.append(str(md_file.relative_to(REPO_ROOT)))
    assert not violations, (
        "Scaffold SKILL.md mentions native_program without substrate/dispatch:\n"
        + "\n".join(violations)
    )


def test_m6_scaffold_python_fences_in_docs_compile() -> None:
    """Python code fences in active composition docs must be syntactically valid."""
    failures: list[str] = []
    for rel in _M6_COMPOSITION_DOCS:
        p = REPO_ROOT / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        for index, snippet in enumerate(_extract_python_fences(text), start=1):
            # Try compiling as top-level code first
            try:
                compile(snippet, f"{p}:fence-{index}", "exec")
                continue
            except SyntaxError:
                pass
            # Try compiling as generator body (wrapped in a function for yield support)
            try:
                # Indent and wrap in an async generator function to support yield
                indented = "\n".join("    " + line for line in snippet.splitlines())
                wrapped = f"async def _fence_wrapper():\n{indented}"
                compile(wrapped, f"{p}:fence-{index}", "exec")
            except SyntaxError as exc:
                failures.append(f"{rel} fence {index}: {exc}")
    assert not failures, "Composition doc code fences with syntax errors:\n" + "\n".join(failures)
