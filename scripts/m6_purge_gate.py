from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Iterable


LEGACY_CONSTRUCTORS = {
    "_build_legacy_pipeline",
    "build_legacy_pipeline",
    "compile_planning_pipeline",
}
DEFAULT_PRODUCT_ROOTS = ("arnold_pipelines",)


def _iter_product_roots(repo_root: Path, roots: Iterable[str]) -> list[Path]:
    return [repo_root / root for root in roots if (repo_root / root).exists()]


def _legacy_dirs(product_root: Path) -> list[Path]:
    matches: list[Path] = []
    for path in product_root.rglob("*"):
        if not path.is_dir():
            continue
        if path.name == "_pipeline" or path.name == "stages":
            matches.append(path)
    return sorted(matches)


def _top_level_function_names(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        raise ValueError(f"could not parse {path}: {exc}") from exc
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _literal_all_exports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        raise ValueError(f"could not parse {path}: {exc}") from exc
    exports: set[str] = set()
    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            continue
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            for item in value.elts:
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    exports.add(item.value)
    return exports


# ---------------------------------------------------------------------------
# AST-aware __init__.py surface checks
# ---------------------------------------------------------------------------


def _init_surface_errors(init_path: Path, repo_root: Path) -> list[str]:
    """AST-aware check for legacy names in __init__.py.

    Flags legacy constructors in:
      - ``__all__``
      - ``_SYMBOL_EXPORTS`` dict keys
      - top-level function definitions (wrappers)
      - import statements (direct or aliased)
    """
    errors: list[str] = []
    try:
        tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    except SyntaxError:
        return errors
    rel = str(init_path.relative_to(repo_root))

    # __all__
    exports = _literal_all_exports(init_path)
    leaked = sorted(exports & LEGACY_CONSTRUCTORS)
    for name in leaked:
        errors.append(
            f"{rel} exports legacy constructor via __all__: {name}"
        )

    # _SYMBOL_EXPORTS
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Name) and target.id == "_SYMBOL_EXPORTS"):
                continue
            if isinstance(node.value, ast.Dict):
                for key in node.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        if key.value in LEGACY_CONSTRUCTORS:
                            errors.append(
                                f"{rel} _SYMBOL_EXPORTS contains legacy constructor: {key.value}"
                            )

    # Top-level function definitions (wrapper/alias functions)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in LEGACY_CONSTRUCTORS:
                errors.append(
                    f"{rel} defines legacy constructor wrapper: {node.name}"
                )

    # Import statements
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in LEGACY_CONSTRUCTORS:
                    errors.append(
                        f"{rel} imports legacy constructor: {alias.name}"
                    )
                if alias.asname and alias.asname in LEGACY_CONSTRUCTORS:
                    errors.append(
                        f"{rel} imports legacy alias: {alias.asname} (as {alias.name})"
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in LEGACY_CONSTRUCTORS:
                    errors.append(
                        f"{rel} imports legacy constructor: {alias.name}"
                    )
                if alias.asname and alias.asname in LEGACY_CONSTRUCTORS:
                    errors.append(
                        f"{rel} imports legacy alias: {alias.asname}"
                    )

    return errors


# ---------------------------------------------------------------------------
# Pipeline surface checks (pipeline.py + __init__.py)
# ---------------------------------------------------------------------------


def _pipeline_surface_errors(repo_root: Path) -> list[str]:
    errors: list[str] = []
    pipeline_path = repo_root / "arnold_pipelines" / "megaplan" / "pipeline.py"
    if pipeline_path.exists():
        functions = _top_level_function_names(pipeline_path)
        leaked = sorted(functions & LEGACY_CONSTRUCTORS)
        if leaked:
            errors.append(
                f"{pipeline_path.relative_to(repo_root)} defines legacy constructors: "
                + ", ".join(leaked)
            )
        exports = sorted(_literal_all_exports(pipeline_path) & LEGACY_CONSTRUCTORS)
        if exports:
            errors.append(
                f"{pipeline_path.relative_to(repo_root)} exports legacy constructors via __all__: "
                + ", ".join(exports)
            )
    init_path = repo_root / "arnold_pipelines" / "megaplan" / "__init__.py"
    if init_path.exists():
        errors.extend(_init_surface_errors(init_path, repo_root))
    return errors


# ---------------------------------------------------------------------------
# AST-aware test keepalive scanner
# ---------------------------------------------------------------------------

class _TestUsageVisitor(ast.NodeVisitor):
    """AST visitor that flags positive legacy usage in test files.

    Flags:
      - Import statements importing legacy names
      - Function calls to legacy-named callables
      - ``hasattr(X, "legacy_name")`` in a positive (non-negated) context
      - ``getattr(X, "legacy_name")`` outside ``pytest.raises(AttributeError)``
      - Bare ``Name`` references to legacy constructors in a positive context
    """

    def __init__(self, legacy_names: set[str]) -> None:
        super().__init__()
        self.legacy_names = legacy_names
        self.errors: list[str] = []
        self._stack: list[ast.AST] = []

    def visit(self, node: ast.AST) -> None:
        self._stack.append(node)
        super().visit(node)
        self._stack.pop()

    # -- import checks -------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name in self.legacy_names:
                self.errors.append(
                    f"imports legacy constructor: {alias.name}"
                )
            if alias.asname and alias.asname in self.legacy_names:
                self.errors.append(
                    f"imports legacy alias: {alias.asname}"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name in self.legacy_names:
                self.errors.append(
                    f"imports legacy constructor: {alias.name}"
                )
            if alias.asname and alias.asname in self.legacy_names:
                self.errors.append(
                    f"imports legacy alias: {alias.asname} (as {alias.name})"
                )
        self.generic_visit(node)

    # -- call checks ---------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        # Direct call: legacy_name(...)
        if isinstance(node.func, ast.Name) and node.func.id in self.legacy_names:
            self.errors.append(
                f"calls legacy constructor: {node.func.id}()"
            )
            self.generic_visit(node)
            return

        # Attribute call: module.legacy_name(...)
        if isinstance(node.func, ast.Attribute) and node.func.attr in self.legacy_names:
            self.errors.append(
                f"calls legacy constructor: .{node.func.attr}()"
            )
            self.generic_visit(node)
            return

        # hasattr(X, "legacy_name") — flag only in positive context
        if self._is_hasattr_call(node):
            second_arg = node.args[1] if len(node.args) >= 2 else None
            if isinstance(second_arg, ast.Constant) and isinstance(second_arg.value, str):
                if second_arg.value in self.legacy_names:
                    if not self._in_negation_context():
                        self.errors.append(
                            f"positive hasattr assertion for legacy constructor: {second_arg.value}"
                        )

        # getattr(X, "legacy_name") — flag only in positive context
        if self._is_getattr_call(node):
            second_arg = node.args[1] if len(node.args) >= 2 else None
            if isinstance(second_arg, ast.Constant) and isinstance(second_arg.value, str):
                if second_arg.value in self.legacy_names:
                    if not self._in_negation_context():
                        self.errors.append(
                            f"positive getattr for legacy constructor: {second_arg.value}"
                        )

        self.generic_visit(node)

    # -- name reference checks -----------------------------------------------

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in self.legacy_names:
            # Skip if this Name is the *func* of a parent Call node — already
            # reported by visit_Call as a legacy call.
            if not self._is_func_of_parent_call(node):
                if not self._in_negation_context():
                    self.errors.append(
                        f"references legacy constructor name: {node.id}"
                    )
        self.generic_visit(node)

    def _is_func_of_parent_call(self, node: ast.Name) -> bool:
        if len(self._stack) < 2:
            return False
        parent = self._stack[-2]  # -1 is the Name node (pushed by visit())
        return isinstance(parent, ast.Call) and parent.func is node

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _is_hasattr_call(node: ast.Call) -> bool:
        return (
            isinstance(node.func, ast.Name)
            and node.func.id == "hasattr"
            and len(node.args) >= 2
        )

    @staticmethod
    def _is_getattr_call(node: ast.Call) -> bool:
        return (
            isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
        )

    def _in_negation_context(self) -> bool:
        """Check whether the current node is inside a negation context.

        Returns True if any ancestor is:
          - ``ast.UnaryOp`` with ``ast.Not()`` (covers ``not hasattr(...)``,
            ``not legacy_name``)
          - ``ast.With`` calling ``pytest.raises(AttributeError, ...)``
        """
        for ancestor in reversed(self._stack):
            if isinstance(ancestor, ast.UnaryOp) and isinstance(ancestor.op, ast.Not):
                return True
            if isinstance(ancestor, ast.With):
                for item in ancestor.items:
                    if self._is_pytest_raises_attrerror(item.context_expr):
                        return True
        return False

    @staticmethod
    def _is_pytest_raises_attrerror(expr: ast.expr) -> bool:
        """Check if *expr* is ``pytest.raises(AttributeError, ...)``."""
        if not isinstance(expr, ast.Call):
            return False
        # pytest.raises or just raises (if imported directly)
        if isinstance(expr.func, ast.Attribute):
            if expr.func.attr != "raises":
                return False
        elif isinstance(expr.func, ast.Name):
            if expr.func.id != "raises":
                return False
        else:
            return False
        # Check that AttributeError is in the positional args
        for arg in expr.args:
            if isinstance(arg, ast.Name) and arg.id == "AttributeError":
                return True
        return False


def _test_keepalive_errors(repo_root: Path, test_roots: Iterable[str]) -> list[str]:
    """AST-aware test-file scanner for legacy constructor keepalives.

    Only flags:
      - imports of legacy names
      - calls to legacy-named functions
      - positive ``hasattr``/``getattr`` assertions for legacy names
      - bare name references to legacy constructors in positive context

    Deliberate absence tests (``not hasattr``, ``pytest.raises(AttributeError)``
    around ``getattr``, ``"name" not in __all__``) are *not* flagged.
    """
    errors: list[str] = []
    for root_name in test_roots:
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("test*.py")):
            # Archived tests are intentionally frozen legacy references;
            # fixture helpers are not assertions. Skip both.
            if "archive" in path.parts or "fixtures" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError:
                continue
            visitor = _TestUsageVisitor(LEGACY_CONSTRUCTORS)
            visitor.visit(tree)
            if visitor.errors:
                rel = str(path.relative_to(repo_root))
                # Aggregate legacy names found in this file.
                leaked_names: set[str] = set()
                for err in visitor.errors:
                    # Extract the legacy constructor name from the error detail.
                    for name in LEGACY_CONSTRUCTORS:
                        if name in err:
                            leaked_names.add(name)
                if leaked_names:
                    errors.append(
                        f"{rel} references legacy constructors in tests: "
                        + ", ".join(sorted(leaked_names))
                    )
                # Also emit detailed per-usage errors for diagnostic clarity.
                for err in visitor.errors:
                    errors.append(f"{rel}: {err}")
    return errors


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def check_m6_purge(
    *,
    repo_root: Path,
    product_roots: Iterable[str] = DEFAULT_PRODUCT_ROOTS,
    test_roots: Iterable[str] = ("tests",),
) -> list[str]:
    errors: list[str] = []
    for product_root in _iter_product_roots(repo_root, product_roots):
        for path in _legacy_dirs(product_root):
            errors.append(
                f"legacy runtime directory still exists under shipped product root: "
                f"{path.relative_to(repo_root)}"
            )
    errors.extend(_pipeline_surface_errors(repo_root))
    errors.extend(_test_keepalive_errors(repo_root, test_roots))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail M6 clean-break completion if shipped product packages still carry "
            "legacy _pipeline/stages directories or tests keep legacy constructors alive."
        )
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument(
        "--product-root",
        action="append",
        default=None,
        help="Product package root to scan. May be repeated. Defaults to arnold_pipelines.",
    )
    parser.add_argument(
        "--test-root",
        action="append",
        default=None,
        help="Test root to scan for legacy keepalive assertions. Defaults to tests.",
    )
    args = parser.parse_args(argv)
    try:
        errors = check_m6_purge(
            repo_root=args.root.resolve(strict=False),
            product_roots=args.product_root or DEFAULT_PRODUCT_ROOTS,
            test_roots=args.test_root or ("tests",),
        )
    except ValueError as exc:
        print(f"m6 purge gate failed: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"m6 purge gate failed: {error}", file=sys.stderr)
        return 1
    print("m6 purge gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
