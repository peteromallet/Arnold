#!/usr/bin/env python3
"""AST-based census of silent failure sites in the megaplan codebase.

Scans ``megaplan/**/*.py`` for:
1. Silent ``except`` handlers — bodies that swallow exceptions without any
   logging, raising, or complex recovery.
2. Named ``print(..., file=sys.stderr)`` sites — direct writes to stderr
   that bypass the logging framework.

Results are classified into four buckets according to the M3a policy:
- ``in_scope_core``: Hits in allowlisted core files (eligible for M3a patching).
- ``explicitly_excluded``: Hits in explicitly excluded surfaces (agent, cloud,
  workers, CLI, tests, generated).
- ``classified_out_of_m3a``: Hits in non-allowlisted hand-written core-adjacent
  files documented in the appendix (not patched in M3a).
- ``needs_review``: Everything else — blocks Phase 2 until resolved.

Usage:
    python tools/silent_failure_census.py [--json] [--quiet]

Output goes to stdout as a human-readable report (default) or JSON.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Policy: file classification rules
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

ALLOWLISTED_CORE: set[str] = {
    "megaplan/handlers/gate.py",
    "megaplan/handlers/critique.py",
    "megaplan/handlers/override.py",
    "megaplan/handlers/verifiability.py",
    "megaplan/handlers/shared.py",
    "megaplan/handlers/finalize.py",
    "megaplan/_pipeline/executor.py",
    "megaplan/_pipeline/faults.py",
    "megaplan/_pipeline/run_cli.py",
    "megaplan/_pipeline/stages/inprocess_step.py",
    "megaplan/execute/core.py",
    "megaplan/execute/quality.py",
    "megaplan/auto.py",
    "megaplan/_core/io.py",
    "megaplan/chain.py",
}

EXPLICITLY_EXCLUDED_GLOBS: tuple[str, ...] = (
    "megaplan/agent/",
    "megaplan/cloud/",
    "megaplan/workers/",
    "megaplan/tests/",
)

EXPLICITLY_EXCLUDED_FILES: set[str] = {
    "megaplan/cli.py",
}

CLASSIFIED_OUT_OF_M3A: set[str] = {
    # ── Previously classified (T2) ──
    "megaplan/_core/state.py",
    "megaplan/handlers/review.py",
    "megaplan/_core/hermes_fanout.py",
    # ── Phase 1 checkpoint classification (T3): all 66 needs_review files ──
    # _core (2)
    "megaplan/_core/phase_runtime.py",
    "megaplan/_core/user_config.py",
    # _pipeline (6)
    "megaplan/_pipeline/patterns.py",
    "megaplan/_pipeline/preflight.py",
    "megaplan/_pipeline/registry.py",
    "megaplan/_pipeline/resume.py",
    "megaplan/_pipeline/step_helpers.py",
    "megaplan/_pipeline/steps/human_gate.py",
    # audits (1)
    "megaplan/audits/hermes_vendoring.py",
    # bakeoff (7)
    "megaplan/bakeoff/handlers.py",
    "megaplan/bakeoff/judge.py",
    "megaplan/bakeoff/lifecycle.py",
    "megaplan/bakeoff/live_status.py",
    "megaplan/bakeoff/merge.py",
    "megaplan/bakeoff/metrics.py",
    "megaplan/bakeoff/worktree.py",
    # blocker_recovery (1)
    "megaplan/blocker_recovery.py",
    # execute (1) — merge.py is execute-adjacent, not in allowlist
    "megaplan/execute/merge.py",
    # forms (1)
    "megaplan/forms/directors_notes.py",
    # handlers (2) — init/tickets not in allowlist
    "megaplan/handlers/init.py",
    "megaplan/handlers/tickets.py",
    # loop (2)
    "megaplan/loop/engine.py",
    "megaplan/loop/git.py",
    # observability (4)
    "megaplan/observability/doctor.py",
    "megaplan/observability/events.py",
    "megaplan/observability/introspect.py",
    "megaplan/observability/trace.py",
    # orchestration (5)
    "megaplan/orchestration/evaluation.py",
    "megaplan/orchestration/feedback.py",
    "megaplan/orchestration/phase_result.py",
    "megaplan/orchestration/prep_research.py",
    "megaplan/orchestration/progress.py",
    # pipelines (3)
    "megaplan/pipelines/creative/prompts/critique_creative.py",
    "megaplan/pipelines/doc/prompts/execute_doc.py",
    "megaplan/pipelines/doc/steps.py",
    # pricing (3)
    "megaplan/pricing/claude.py",
    "megaplan/pricing/codex.py",
    "megaplan/pricing/fireworks.py",
    # profiles (1)
    "megaplan/profiles/__init__.py",
    # prompts (7)
    "megaplan/prompts/execute.py",
    "megaplan/prompts/feedback.py",
    "megaplan/prompts/planning.py",
    "megaplan/prompts/review.py",
    "megaplan/prompts/review_doc.py",
    "megaplan/prompts/review_joke.py",
    "megaplan/prompts/tiebreaker_researcher.py",
    # receipts (4)
    "megaplan/receipts/drift.py",
    "megaplan/receipts/query.py",
    "megaplan/receipts/report.py",
    "megaplan/receipts/schema.py",
    # resident (3)
    "megaplan/resident/agent_loop.py",
    "megaplan/resident/cloud.py",
    "megaplan/resident/profile.py",
    # review (1)
    "megaplan/review/mechanical.py",
    # runtime (4)
    "megaplan/runtime/doc_assembly.py",
    "megaplan/runtime/key_pool.py",
    "megaplan/runtime/process.py",
    "megaplan/runtime/sandbox.py",
    # store (4)
    "megaplan/store/compat.py",
    "megaplan/store/db.py",
    "megaplan/store/identity.py",
    "megaplan/store/multi.py",
    # tickets (4)
    "megaplan/tickets/core.py",
    "megaplan/tickets/files.py",
    "megaplan/tickets/identity.py",
    "megaplan/tickets/registry.py",
}


# ---------------------------------------------------------------------------
# AST detection helpers
# ---------------------------------------------------------------------------

def _is_silent_body(stmts: list[ast.stmt]) -> bool:
    """Return True if *stmts* represent a silent exception-swallowing body.

    Detects:
    - ``pass``
    - ``continue``
    - ``return`` / ``return None`` / ``return False`` / ``return []`` / ...
    - ``return cls()`` or ``return SomeClass()`` (no-arg constructor fallback)
    - single assignment of a default/empty value (e.g. ``x = []``)
    - single assignment of any fallback expression (e.g. ``idx = len(x)``)
      when it is the *only* statement and serves as a silent fallback.
    - two-statement bodies where the first is a fallback assignment and the
      second is ``continue`` or ``return``.
    """
    if not stmts:
        return True
    if len(stmts) > 2:
        return False

    for stmt in stmts:
        if isinstance(stmt, ast.Pass):
            continue
        elif isinstance(stmt, ast.Continue):
            continue
        elif isinstance(stmt, ast.Return):
            if stmt.value is None:
                continue  # bare ``return``
            if _is_default_value(stmt.value):
                continue  # ``return None``, ``return []``, etc.
            if isinstance(stmt.value, ast.Call):
                if _is_simple_constructor(stmt.value):
                    continue  # ``return cls()``, ``return FaultRegistry()``
            return False
        elif isinstance(stmt, ast.Assign):
            # Single-target assignment to a simple name is a common
            # "compute a fallback" pattern in except handlers.
            if len(stmt.targets) != 1:
                return False
            if not isinstance(stmt.targets[0], ast.Name):
                return False
            # Accept any RHS as a silent fallback assignment (the handler
            # is recovering from the error with a computed default).
            continue
        elif isinstance(stmt, ast.Expr):
            # A bare expression statement — string constant (docstring/comment)
            # is silent; anything else (e.g. log.warning(...)) is not silent.
            if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                continue
            return False
        else:
            return False
    return True


def _is_default_value(node: ast.expr) -> bool:
    """Return True if *node* represents a sentinel default value.

    Covers: ``None``, ``False``, ``True``, ``[]``, ``{}``, ``set()``,
    ``""``, ``0``, ``0.0``, ``list()``, ``dict()``.
    """
    if isinstance(node, ast.Constant):
        val = node.value
        if val is None:
            return True
        if isinstance(val, bool) and val is False:
            return True
        if val == "" or val == 0 or val == 0.0:
            return True
        return False
    # In Python 3.8+, empty list/dict literals are separate AST nodes.
    if isinstance(node, ast.List):
        return len(node.elts) == 0
    if isinstance(node, ast.Dict):
        return len(node.keys) == 0 and len(node.values) == 0
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id in ("set", "list", "dict", "tuple"):
                if not node.args and not node.keywords:
                    return True
    return False


def _is_simple_constructor(call: ast.Call) -> bool:
    """Return True if *call* is a no-arg constructor like ``cls()`` or ``FaultRegistry()``."""
    if call.args or call.keywords:
        return False
    if isinstance(call.func, ast.Name):
        return True
    if isinstance(call.func, ast.Attribute):
        return True
    return False


def _is_print_to_stderr(call: ast.Call) -> bool:
    """Return True if *call* is ``print(..., file=sys.stderr)``."""
    if not isinstance(call.func, ast.Name):
        return False
    if call.func.id != "print":
        return False
    for kw in call.keywords:
        if kw.arg == "file":
            if isinstance(kw.value, ast.Attribute):
                if (
                    isinstance(kw.value.value, ast.Name)
                    and kw.value.value.id == "sys"
                    and kw.value.attr == "stderr"
                ):
                    return True
    return False


def _find_enclosing_function(node: ast.AST, tree: ast.AST) -> str | None:
    """Walk back up the AST (approximate) to find enclosing function name.

    Since we don't have parent pointers, we walk the tree and track scope.
    """
    # Simplified: we'll use a tree walker that tracks current function/class.
    class ScopeFinder(ast.NodeVisitor):
        def __init__(self, target_lineno: int):
            self.target_lineno = target_lineno
            self.scope: list[str] = []
            self.result: str | None = None

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if self.result is not None:
                return
            if node.lineno <= self.target_lineno <= (node.end_lineno or node.lineno):
                self.scope.append(node.name)
                self.result = ".".join(self.scope) if self.scope else node.name
            self.generic_visit(node)
            if self.scope and self.scope[-1] == node.name:
                self.scope.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            if self.result is not None:
                return
            if node.lineno <= self.target_lineno <= (node.end_lineno or node.lineno):
                self.scope.append(node.name)
            self.generic_visit(node)
            if self.scope and self.scope[-1] == node.name:
                self.scope.pop()

    finder = ScopeFinder(node.lineno)
    finder.visit(tree)
    return finder.result


# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------

def scan_file(filepath: Path) -> dict[str, Any]:
    """Parse *filepath* and return a dict of findings."""
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return {"path": str(filepath), "error": "unreadable", "silent_handlers": [], "stderr_prints": []}

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as exc:
        return {"path": str(filepath), "error": f"syntax: {exc}", "silent_handlers": [], "stderr_prints": []}

    silent_handlers: list[dict[str, Any]] = []
    stderr_prints: list[dict[str, Any]] = []

    class Visitor(ast.NodeVisitor):
        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if _is_silent_body(node.body):
                func_name = _find_enclosing_function(node, tree)
                silent_handlers.append({
                    "line": node.lineno,
                    "end_line": node.end_lineno,
                    "type": self._exception_type(node),
                    "function": func_name,
                    "body_kind": self._body_kind(node.body),
                })
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            if _is_print_to_stderr(node):
                func_name = _find_enclosing_function(node, tree)
                stderr_prints.append({
                    "line": node.lineno,
                    "end_line": node.end_lineno,
                    "function": func_name,
                })
            self.generic_visit(node)

        @staticmethod
        def _exception_type(node: ast.ExceptHandler) -> str:
            if node.type is None:
                return "bare-except"
            if isinstance(node.type, ast.Name):
                return node.type.id
            if isinstance(node.type, ast.Tuple):
                parts = []
                for elt in node.type.elts:
                    if isinstance(elt, ast.Name):
                        parts.append(elt.id)
                    elif isinstance(elt, ast.Attribute):
                        parts.append(ast.unparse(elt) if hasattr(ast, "unparse") else str(elt))
                return " | ".join(parts) if parts else "tuple"
            if isinstance(node.type, ast.Attribute):
                return ast.unparse(node.type) if hasattr(ast, "unparse") else str(node.type)
            return ast.dump(node.type)

        @staticmethod
        def _body_kind(body: list[ast.stmt]) -> str:
            if not body:
                return "empty"
            stmt = body[0]
            if isinstance(stmt, ast.Pass):
                return "pass"
            if isinstance(stmt, ast.Continue):
                return "continue"
            if isinstance(stmt, ast.Return):
                if stmt.value is None:
                    return "return"
                if isinstance(stmt.value, ast.Constant):
                    return f"return {repr(stmt.value.value)}"
                if isinstance(stmt.value, (ast.List, ast.Dict)):
                    return "return <empty-collection>"
                if isinstance(stmt.value, ast.Call):
                    return "return cls()" if not stmt.value.args else "return <call>"
                return "return <expr>"
            if isinstance(stmt, ast.Assign):
                if isinstance(stmt.value, ast.Constant):
                    return f"assign {repr(stmt.value.value)}"
                if isinstance(stmt.value, (ast.List, ast.Dict)):
                    return "assign <empty-collection>"
                if isinstance(stmt.value, ast.Call):
                    fn_name = ast.unparse(stmt.value.func) if hasattr(ast, "unparse") else "?"
                    return f"assign {fn_name}(...)"
                return "assign <fallback>"
            return "other"

    Visitor().visit(tree)

    return {
        "path": str(filepath),
        "silent_handlers": silent_handlers,
        "stderr_prints": stderr_prints,
    }


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify(filepath: str) -> str:
    """Map a file path to one of the four census buckets."""
    rel = str(Path(filepath).relative_to(REPO_ROOT) if Path(filepath).is_absolute() else filepath)

    if rel in ALLOWLISTED_CORE:
        return "in_scope_core"

    if rel in EXPLICITLY_EXCLUDED_FILES:
        return "explicitly_excluded"

    for prefix in EXPLICITLY_EXCLUDED_GLOBS:
        if rel.startswith(prefix):
            return "explicitly_excluded"

    if rel in CLASSIFIED_OUT_OF_M3A:
        return "classified_out_of_m3a"

    return "needs_review"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def run_census() -> dict[str, Any]:
    """Run the full census and return structured results."""
    src_dir = REPO_ROOT / "megaplan"

    buckets: dict[str, list[dict[str, Any]]] = {
        "in_scope_core": [],
        "explicitly_excluded": [],
        "classified_out_of_m3a": [],
        "needs_review": [],
    }

    # Collect all .py files under megaplan/, excluding __pycache__.
    py_files: list[Path] = []
    for py_file in sorted(src_dir.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        if ".egg" in py_file.parts:
            continue
        py_files.append(py_file)

    summary = {
        "total_files_scanned": len(py_files),
        "files_with_findings": 0,
        "total_silent_handlers": 0,
        "total_stderr_prints": 0,
    }

    for py_file in py_files:
        result = scan_file(py_file)
        rel = str(py_file.relative_to(REPO_ROOT))
        bucket = classify(rel)

        file_entry: dict[str, Any] = {
            "file": rel,
            "bucket": bucket,
            "silent_handlers": result.get("silent_handlers", []),
            "stderr_prints": result.get("stderr_prints", []),
        }

        if result.get("error"):
            file_entry["error"] = result["error"]

        has_findings = bool(file_entry["silent_handlers"] or file_entry["stderr_prints"])
        if has_findings:
            summary["files_with_findings"] += 1

        summary["total_silent_handlers"] += len(file_entry["silent_handlers"])
        summary["total_stderr_prints"] += len(file_entry["stderr_prints"])

        if has_findings:
            buckets[bucket].append(file_entry)

    return {
        "summary": summary,
        "buckets": buckets,
    }


def format_report(results: dict[str, Any]) -> str:
    """Format results as a human-readable report."""
    lines: list[str] = []
    summary = results["summary"]
    buckets = results["buckets"]

    lines.append("=" * 72)
    lines.append("M3a Silent Failure Census")
    lines.append("=" * 72)
    lines.append(f"Files scanned:          {summary['total_files_scanned']}")
    lines.append(f"Files with findings:    {summary['files_with_findings']}")
    lines.append(f"Silent except handlers: {summary['total_silent_handlers']}")
    lines.append(f"stderr print() sites:   {summary['total_stderr_prints']}")
    lines.append("")

    bucket_order = ["in_scope_core", "explicitly_excluded", "classified_out_of_m3a", "needs_review"]
    bucket_labels = {
        "in_scope_core": "IN-SCOPE CORE (eligible for M3a patching)",
        "explicitly_excluded": "EXPLICITLY EXCLUDED (worker/cloud/agent/CLI/tests)",
        "classified_out_of_m3a": "CLASSIFIED OUT OF M3A (documented, not patched)",
        "needs_review": "NEEDS REVIEW (blocks Phase 2 until resolved)",
    }

    for bucket_name in bucket_order:
        entries = buckets.get(bucket_name, [])
        lines.append("-" * 72)
        lines.append(f"{bucket_labels[bucket_name]} — {len(entries)} file(s)")
        lines.append("-" * 72)
        if not entries:
            lines.append("  (none)")
            lines.append("")
            continue

        for entry in entries:
            lines.append(f"  {entry['file']}")
            if entry.get("error"):
                lines.append(f"    ERROR: {entry['error']}")
            for sh in entry.get("silent_handlers", []):
                func = f" in {sh['function']}" if sh.get("function") else ""
                lines.append(
                    f"    L{sh['line']}: except {sh['type']}: {sh['body_kind']}{func}"
                )
            for sp in entry.get("stderr_prints", []):
                func = f" in {sp['function']}" if sp.get("function") else ""
                lines.append(f"    L{sp['line']}: print(..., file=sys.stderr){func}")
            lines.append("")

    # Needs review summary
    needs = buckets.get("needs_review", [])
    if needs:
        lines.append("=" * 72)
        lines.append(f"⚠️  NEEDS REVIEW: {len(needs)} file(s) — blocking Phase 2")
        lines.append("=" * 72)
        lines.append("These files are not in the allowlist, excluded set, or")
        lines.append("classified-out list.  Every entry must be moved to one of the")
        lines.append("other buckets before implementation proceeds.")
    else:
        lines.append("=" * 72)
        lines.append("✅ NEEDS REVIEW is EMPTY — Phase 1 checkpoint satisfied")
        lines.append("=" * 72)

    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="M3a silent failure census")
    parser.add_argument(
        "--json", action="store_true", help="Output results as JSON"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress report; useful with --json"
    )
    args = parser.parse_args()

    results = run_census()

    if args.json:
        json.dump(results, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    elif not args.quiet:
        print(format_report(results))

    # Exit non-zero if needs_review is non-empty (for CI/gate use).
    if results["buckets"].get("needs_review"):
        sys.exit(1)


if __name__ == "__main__":
    main()
