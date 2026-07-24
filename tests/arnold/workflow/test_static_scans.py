from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

BANNED_AUTHORING_TERMS = (
    "PipelineBuilder",
    "fluent chaining",
    "decorator",
    "@stage",
    ".then(",
    "builder.add_step",
)
BANNED_EDGE_STAGE_TERMS = (
    "Stage(",
    "Edge(",
)
PYTHON_AUTHORING_DOC_PATHS = (
    Path("docs/arnold/python-shaped-authoring-contract.md"),
    Path("docs/arnold/workflow-authoring.md"),
    Path("docs/arnold/package-authoring-contract.md"),
    Path("arnold_pipelines/_template/SKILL.md"),
    Path("arnold_pipelines/_template/skills/pipeline-template/SKILL.md"),
    Path("arnold_pipelines/_template/skills/new-arnold-pipeline/SKILL.md"),
)
PYTHON_AUTHORING_COMPILE_MODULES = (
    Path("arnold/workflow/authoring.py"),
    Path("arnold/workflow/diagnostics.py"),
)
PYTHON_AUTHORING_FIXTURE_ROOT = Path("tests/fixtures/workflow_authoring")
PYTHON_AUTHORING_SUPPORT_MODULES = {"components"}
PYTHON_AUTHORING_BANNED_GUIDANCE = (
    "PipelineBuilder",
    "Pipeline.builder()",
    "builder.add_step",
    "fluent",
    "@stage",
    "arnold.pipeline.native",
    "arnold.execution",
    "_pipeline",
    "stages",
    "generated catalogs as editable source",
    "generated catalogs as source of truth",
)
PYTHON_AUTHORING_FORBIDDEN_IMPORT_PREFIXES = (
    "arnold.execution",
    "arnold.pipeline.native",
    "arnold_pipelines",
    "megaplan",
)
NEUTRAL_IMPLEMENTATION_ROOTS = (
    Path("arnold/workflow"),
    Path("arnold/manifest"),
)
NEUTRAL_IMPLEMENTATION_FORBIDDEN_IMPORT_PREFIXES = (
    "arnold.execution",
    "arnold.runtime",
    "arnold_pipelines",
    "megaplan",
)
NEW_DOC_PATHS = (
    Path("docs/arnold/workflow-authoring.md"),
    Path("docs/arnold/workflow-manifest.md"),
    Path("docs/arnold/workflow-manifest-amendments.md"),
    Path("tests/fixtures/workflow/README.md"),
)


def _is_exclusion_line(line: str) -> bool:
    """Allow banned terms when the line explicitly marks them legacy/banned."""

    lowered = line.lower()
    return any(
        marker in lowered
        for marker in (
            "legacy",
            "non-canonical",
            "banned",
            "do not use",
            "do not teach",
            "forbidden",
            "invalid",
            "must not",
            "non-user-facing",
            "not the user-facing",
            "outside v1",
            "rejected",
        )
    )


def _is_python_authoring_rejected_example(paragraph: str) -> bool:
    lowered = paragraph.lower()
    return any(
        marker in lowered
        for marker in (
            "backend compiler data",
            "compiler output",
            "derived artifacts",
            "do not",
            "forbidden",
            "invalid",
            "legacy",
            "must not",
            "not the user-facing",
            "outside v1",
            "rejected",
            "source diagnostic",
        )
    )


def _python_authoring_guidance_violations(relative: Path, text: str) -> list[str]:
    violations: list[str] = []
    for start, paragraph in _paragraphs(text):
        has_rejected_context = _is_python_authoring_rejected_example(paragraph)
        for term in PYTHON_AUTHORING_BANNED_GUIDANCE:
            if _contains_python_authoring_banned_guidance(paragraph, term) and not has_rejected_context:
                violations.append(f"{relative}:{start}: {term!r}")
    return violations


def _contains_python_authoring_banned_guidance(paragraph: str, term: str) -> bool:
    if term == "_pipeline":
        return re.search(r"(?<![A-Za-z0-9])_pipeline(?![A-Za-z0-9])", paragraph) is not None
    return term in paragraph


def _paragraphs(text: str) -> list[tuple[int, str]]:
    """Return (start_line, paragraph) pairs split on blank lines."""

    paragraphs: list[tuple[int, str]] = []
    current: list[str] = []
    start = 1
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.strip() == "":
            if current:
                paragraphs.append((start, "\n".join(current)))
                current = []
            start = lineno + 1
        else:
            current.append(line)
    if current:
        paragraphs.append((start, "\n".join(current)))
    return paragraphs


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _is_forbidden_python_authoring_import(name: str) -> bool:
    return any(
        name == prefix or name.startswith(prefix + ".")
        for prefix in PYTHON_AUTHORING_FORBIDDEN_IMPORT_PREFIXES
    )


def _is_forbidden_neutral_implementation_import(name: str) -> bool:
    return any(
        name == prefix or name.startswith(prefix + ".")
        for prefix in NEUTRAL_IMPLEMENTATION_FORBIDDEN_IMPORT_PREFIXES
    )


def _dynamic_import_module_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        module = node.args[0]
        if not isinstance(module, ast.Constant) or not isinstance(module.value, str):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            names.add(module.value)
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "importlib"
        ):
            names.add(module.value)
    return names


def _implementation_import_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = _imported_modules(path) | _dynamic_import_module_names(tree)
    return sorted(name for name in imports if _is_forbidden_neutral_implementation_import(name))


def test_new_m2_docs_do_not_teach_banned_authoring_language() -> None:
    root = Path(__file__).parent.parent.parent.parent
    violations: list[str] = []
    for relative in NEW_DOC_PATHS:
        path = root / relative
        if not path.exists():
            continue
        for start, paragraph in _paragraphs(path.read_text(encoding="utf-8")):
            has_exclusion = any(_is_exclusion_line(line) for line in paragraph.splitlines())
            for term in BANNED_AUTHORING_TERMS:
                if term in paragraph and not has_exclusion:
                    violations.append(f"{path}:{start}: {term!r}")
            for term in BANNED_EDGE_STAGE_TERMS:
                if term in paragraph and not has_exclusion and "public `Edge`" not in paragraph:
                    violations.append(f"{path}:{start}: {term!r}")

    assert not violations, "banned canonical authoring language in new M2 docs:\n" + "\n".join(violations)


def test_python_authoring_guidance_scan_distinguishes_rejected_examples() -> None:
    allowed = "Rejected imports: arnold.pipeline.native and _pipeline are legacy surfaces."
    banned = "Use PipelineBuilder fluent chaining from arnold.pipeline.native for new workflows."

    assert _python_authoring_guidance_violations(Path("allowed.md"), allowed) == []
    assert _python_authoring_guidance_violations(Path("banned.md"), banned) == [
        "banned.md:1: 'PipelineBuilder'",
        "banned.md:1: 'fluent'",
        "banned.md:1: 'arnold.pipeline.native'",
    ]


def test_python_authoring_docs_do_not_teach_prohibited_surfaces() -> None:
    root = Path(__file__).parent.parent.parent.parent
    violations: list[str] = []

    for relative in PYTHON_AUTHORING_DOC_PATHS:
        path = root / relative
        assert path.exists(), f"missing authoring doc for static scan: {relative}"
        violations.extend(
            _python_authoring_guidance_violations(relative, path.read_text(encoding="utf-8"))
        )

    assert not violations, "prohibited Python authoring guidance:\n" + "\n".join(violations)


def test_python_authoring_contract_modules_keep_static_import_boundary() -> None:
    root = Path(__file__).parent.parent.parent.parent
    violations: dict[str, list[str]] = {}

    for relative in PYTHON_AUTHORING_COMPILE_MODULES:
        path = root / relative
        imports = _imported_modules(path)
        forbidden = sorted(name for name in imports if _is_forbidden_python_authoring_import(name))
        if forbidden:
            violations[relative.as_posix()] = forbidden

    assert not violations, f"forbidden authoring contract imports: {violations}"


def test_python_authoring_fixtures_only_use_prohibited_imports_as_invalid_cases() -> None:
    root = Path(__file__).parent.parent.parent.parent
    fixture_root = root / PYTHON_AUTHORING_FIXTURE_ROOT
    assert fixture_root.exists(), "missing Python authoring fixtures"
    violations: dict[str, list[str]] = {}

    for path in fixture_root.glob("*.py"):
        if path.stem in PYTHON_AUTHORING_SUPPORT_MODULES:
            continue
        expected = path.with_suffix(".expected.json")
        assert expected.exists(), f"missing expected sidecar for {path.name}"
        text = expected.read_text(encoding="utf-8")
        is_invalid_fixture = '"outcome": "invalid"' in text
        forbidden = sorted(name for name in _imported_modules(path) if _is_forbidden_python_authoring_import(name))
        if forbidden and not is_invalid_fixture:
            violations[path.relative_to(root).as_posix()] = forbidden

    assert not violations, f"valid fixtures import prohibited authoring surfaces: {violations}"


def test_compile_only_modules_do_not_import_execution() -> None:
    root = Path(__file__).parent.parent.parent.parent
    compile_roots = [root / "arnold" / "workflow", root / "arnold" / "patterns"]
    violations: dict[str, list[str]] = {}
    for compile_root in compile_roots:
        for path in compile_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            hits: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "arnold.execution" or alias.name.startswith("arnold.execution."):
                            hits.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module == "arnold.execution" or (
                        node.module is not None and node.module.startswith("arnold.execution.")
                    ):
                        hits.add(node.module)
            if hits:
                violations[path.as_posix()] = sorted(hits)

    assert not violations, f"forbidden arnold.execution imports: {violations}"


def test_neutral_workflow_manifest_implementation_files_do_not_import_runtime_or_harness() -> None:
    root = Path(__file__).parent.parent.parent.parent
    violations: dict[str, list[str]] = {}

    for relative_root in NEUTRAL_IMPLEMENTATION_ROOTS:
        for path in (root / relative_root).rglob("*.py"):
            forbidden = _implementation_import_violations(path)
            if forbidden:
                violations[path.relative_to(root).as_posix()] = forbidden

    assert not violations, f"neutral implementation imports runtime/harness modules: {violations}"


def test_workflow_manifest_amendments_clarifies_loop_reentry() -> None:
    path = Path(__file__).parent.parent.parent.parent / "docs" / "arnold" / "workflow-manifest-amendments.md"
    text = path.read_text(encoding="utf-8")
    assert "WorkflowPolicy.loop.max_iterations" in text
    assert "SuspensionRoute.reentry_id" in text
    lowered = text.lower()
    assert "arbitrary graph cycles" in lowered or "arbitrary cycles" in lowered


# ── M6 composition doc/scaffold forbidden-pattern scans ───────────────────

_COMPOSITION_DOC_SCAN_PATHS = (
    Path("docs/arnold/native-composition-contract.md"),
    Path("docs/arnold/authoring-guide.md"),
    Path("docs/arnold/package-authoring-contract.md"),
    Path("docs/arnold/workflow-authoring.md"),
    Path("docs/arnold/creating-a-new-pipeline.md"),
)

_ACTIVE_SCAFFOLD_DIR = Path("arnold_pipelines/_template")
_LEGACY_SCAFFOLD_DIR = Path("arnold/pipelines/_template")

_FORBIDDEN_SHIM_FALLBACK_TERMS = (
    "shim",
    "fallback builder",
    "graph fallback",
    "dual-mode package",
    "compatibility namespace",
    "_legacy.py",
    "temporary wrapper",
    "--driver graph",
)

_FORBIDDEN_DIRECT_AUTHORITY_TERMS = (
    "hand-authored WorkflowManifest",
    "hand-authored NativeProgram",
    "direct IR construction",
    "native_program as source of truth",
    "native_program defines composition",
)

_REJECTION_MARKERS = (
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


def _is_rejection_line(line: str) -> bool:
    lowered = line.lower()
    # Normalize markdown bold/italic
    lowered = lowered.replace("**", "").replace("*", "").replace("__", "")
    return any(marker in lowered for marker in _REJECTION_MARKERS)


def _paragraph_has_rejection_m6(paragraph_lines: list[str]) -> bool:
    """Return True if any line in the paragraph has a rejection marker."""
    return any(_is_rejection_line(line) for line in paragraph_lines)


def _paragraphs_from_lines_m6(lines: list[str]) -> list[tuple[int, list[str]]]:
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


def _is_table_or_fence(stripped: str) -> bool:
    return stripped.startswith("|") or stripped.startswith("```")


def test_m6_scaffold_python_no_forbidden_shim_fallback() -> None:
    """Active scaffold Python files must not contain shim/fallback terms outside rejection context."""
    root = Path(__file__).parent.parent.parent.parent
    violations: list[str] = []
    scaffold = root / _ACTIVE_SCAFFOLD_DIR
    for py_file in sorted(scaffold.rglob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _is_rejection_line(line):
                continue
            lowered = line.lower()
            for term in _FORBIDDEN_SHIM_FALLBACK_TERMS:
                if term.lower() in lowered:
                    violations.append(f"{py_file.relative_to(root)}:{lineno}: {term!r}")
    assert not violations, "Scaffold Python contains forbidden shim/fallback terms:\n" + "\n".join(violations)


def test_m6_scaffold_python_no_direct_manifest_authority() -> None:
    """Active scaffold Python files must not teach direct manifest/native_program authority."""
    root = Path(__file__).parent.parent.parent.parent
    violations: list[str] = []
    scaffold = root / _ACTIVE_SCAFFOLD_DIR
    for py_file in sorted(scaffold.rglob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _is_rejection_line(line):
                continue
            lowered = line.lower()
            for term in _FORBIDDEN_DIRECT_AUTHORITY_TERMS:
                if term.lower() in lowered:
                    violations.append(f"{py_file.relative_to(root)}:{lineno}: {term!r}")
    assert not violations, (
        "Scaffold Python contains forbidden direct-manifest authority terms:\n" + "\n".join(violations)
    )


def test_m6_scaffold_skill_md_no_forbidden_shim_fallback() -> None:
    """Active scaffold SKILL.md files must not teach shim/fallback outside rejection context."""
    root = Path(__file__).parent.parent.parent.parent
    violations: list[str] = []
    scaffold = root / _ACTIVE_SCAFFOLD_DIR
    for md_file in sorted(scaffold.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        for start, para_lines in _paragraphs_from_lines_m6(text.splitlines()):
            if _paragraph_has_rejection_m6(para_lines):
                continue
            for offset, line in enumerate(para_lines):
                stripped = line.strip()
                if _is_table_or_fence(stripped):
                    continue
                lineno = start + offset
                lowered = line.lower()
                for term in _FORBIDDEN_SHIM_FALLBACK_TERMS:
                    if term.lower() in lowered:
                        violations.append(f"{md_file.relative_to(root)}:{lineno}: {term!r}")
    assert not violations, (
        "Scaffold SKILL.md contains forbidden shim/fallback terms:\n" + "\n".join(violations)
    )


def test_m6_scaffold_skill_md_no_direct_manifest_authority() -> None:
    """Active scaffold SKILL.md files must not teach direct manifest/native_program authority."""
    root = Path(__file__).parent.parent.parent.parent
    violations: list[str] = []
    scaffold = root / _ACTIVE_SCAFFOLD_DIR
    for md_file in sorted(scaffold.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        for start, para_lines in _paragraphs_from_lines_m6(text.splitlines()):
            if _paragraph_has_rejection_m6(para_lines):
                continue
            for offset, line in enumerate(para_lines):
                stripped = line.strip()
                if _is_table_or_fence(stripped):
                    continue
                lineno = start + offset
                lowered = line.lower()
                for term in _FORBIDDEN_DIRECT_AUTHORITY_TERMS:
                    if term.lower() in lowered:
                        violations.append(f"{md_file.relative_to(root)}:{lineno}: {term!r}")
    assert not violations, (
        "Scaffold SKILL.md contains forbidden direct-manifest authority terms:\n" + "\n".join(violations)
    )


def test_m6_composition_docs_no_forbidden_shim_fallback() -> None:
    """Composition docs must not teach shim/fallback authority patterns outside rejection context."""
    root = Path(__file__).parent.parent.parent.parent
    violations: list[str] = []
    for rel in _COMPOSITION_DOC_SCAN_PATHS:
        p = root / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        for start, para_lines in _paragraphs_from_lines_m6(text.splitlines()):
            if _paragraph_has_rejection_m6(para_lines):
                continue
            for offset, line in enumerate(para_lines):
                stripped = line.strip()
                if _is_table_or_fence(stripped):
                    continue
                lineno = start + offset
                lowered = line.lower()
                for term in _FORBIDDEN_SHIM_FALLBACK_TERMS:
                    if term.lower() in lowered:
                        violations.append(f"{rel}:{lineno}: {term!r}")
    assert not violations, (
        "Composition docs contain forbidden shim/fallback terms:\n" + "\n".join(violations)
    )


def test_m6_composition_docs_no_direct_manifest_authority() -> None:
    """Composition docs must not teach direct manifest/native_program authority outside rejection."""
    root = Path(__file__).parent.parent.parent.parent
    violations: list[str] = []
    for rel in _COMPOSITION_DOC_SCAN_PATHS:
        p = root / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        bullets_in_toleration: set[int] = set()
        all_paragraphs = _paragraphs_from_lines_m6(text.splitlines())
        for i, (start, para_lines) in enumerate(all_paragraphs):
            para_text = " ".join(line.strip() for line in para_lines).lower()
            if "tolerated" in para_text and "bridge debt" in para_text:
                if i + 1 < len(all_paragraphs):
                    next_start, next_lines = all_paragraphs[i + 1]
                    if next_lines and next_lines[0].strip().startswith("-"):
                        for off in range(len(next_lines)):
                            bullets_in_toleration.add(next_start + off)
        for start, para_lines in all_paragraphs:
            if _paragraph_has_rejection_m6(para_lines):
                continue
            for offset, line in enumerate(para_lines):
                stripped = line.strip()
                if _is_table_or_fence(stripped):
                    continue
                lineno = start + offset
                if lineno in bullets_in_toleration:
                    continue
                lowered = line.lower()
                for term in _FORBIDDEN_DIRECT_AUTHORITY_TERMS:
                    if term.lower() in lowered:
                        violations.append(f"{rel}:{lineno}: {term!r}")
    assert not violations, (
        "Composition docs contain forbidden direct-manifest authority terms:\n" + "\n".join(violations)
    )


def test_m6_legacy_scaffold_path_not_resurrected() -> None:
    """The legacy ``arnold/pipelines/_template/`` directory must not exist."""
    root = Path(__file__).parent.parent.parent.parent
    legacy = root / _LEGACY_SCAFFOLD_DIR
    assert not legacy.exists(), (
        f"Legacy scaffold path {_LEGACY_SCAFFOLD_DIR} must NOT exist. "
        f"Use active path: {_ACTIVE_SCAFFOLD_DIR}"
    )


def test_m6_active_scaffold_does_not_reference_legacy_path() -> None:
    """Active scaffold files must not reference the legacy scaffold path."""
    root = Path(__file__).parent.parent.parent.parent
    violations: list[str] = []
    scaffold = root / _ACTIVE_SCAFFOLD_DIR
    for f in sorted(scaffold.rglob("*")):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        if "arnold/pipelines/_template" in text:
            violations.append(str(f.relative_to(root)))
    assert not violations, (
        f"Active scaffold references legacy path arnold/pipelines/_template/: {violations}"
    )


def test_m6_scaffold_skill_md_native_program_substrate_language() -> None:
    """Scaffold SKILL.md mentioning native_program must use substrate/dispatch language."""
    root = Path(__file__).parent.parent.parent.parent
    violations: list[str] = []
    scaffold = root / _ACTIVE_SCAFFOLD_DIR
    for md_file in sorted(scaffold.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8").lower()
        if "native_program" in text:
            has_substrate = "substrate" in text or "dispatch" in text
            if not has_substrate:
                violations.append(str(md_file.relative_to(root)))
    assert not violations, (
        "Scaffold SKILL.md mentions native_program without substrate/dispatch language:\n"
        + "\n".join(violations)
    )
