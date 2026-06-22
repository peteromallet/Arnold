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
        text = init_path.read_text(encoding="utf-8")
        leaked = sorted(name for name in LEGACY_CONSTRUCTORS if name in text)
        if leaked:
            errors.append(
                f"{init_path.relative_to(repo_root)} references legacy constructors: "
                + ", ".join(leaked)
            )
    return errors


def _test_keepalive_errors(repo_root: Path, test_roots: Iterable[str]) -> list[str]:
    errors: list[str] = []
    for root_name in test_roots:
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("test*.py")):
            text = path.read_text(encoding="utf-8")
            leaked_names = sorted(name for name in LEGACY_CONSTRUCTORS if name in text)
            if not leaked_names:
                continue
            errors.append(
                f"{path.relative_to(repo_root)} references legacy constructors in tests: "
                + ", ".join(leaked_names)
            )
    return errors


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
