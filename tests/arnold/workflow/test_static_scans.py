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
        )
    )


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


def test_workflow_manifest_amendments_clarifies_loop_reentry() -> None:
    path = Path(__file__).parent.parent.parent.parent / "docs" / "arnold" / "workflow-manifest-amendments.md"
    text = path.read_text(encoding="utf-8")
    assert "WorkflowPolicy.loop.max_iterations" in text
    assert "SuspensionRoute.reentry_id" in text
    lowered = text.lower()
    assert "arbitrary graph cycles" in lowered or "arbitrary cycles" in lowered
