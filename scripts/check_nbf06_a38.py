#!/usr/bin/env python3
"""Fail-closed ownership check for the executable NBF-06 surface.

The checker deliberately checks ownership, not prose or generated hashes.  It
enumerates the small set of authority symbols that NBF-06 is allowed to have,
checks their repository-relative locations against the frozen matrix, and
then runs each supplied negative fixture in isolation.  A fixture is expected
to contain one concrete duplicate authority and therefore must be rejected.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]

# These are the five durable authority classes whose duplication would create
# a second NBF-06 policy graph.  Helpers and compatibility aliases are not
# counted as authorities.
AUTHORITIES: dict[str, tuple[str, str]] = {
    "classifier": ("arnold_pipelines/megaplan/fallback_chains.py", "classify_retryability"),
    "selector": ("arnold_pipelines/megaplan/orchestration/provider_resilience.py", "select_provider_route"),
    "applier": ("arnold_pipelines/megaplan/orchestration/provider_resilience.py", "apply_provider_route_decision_locked"),
    "terminal": ("arnold_pipelines/megaplan/incident/ledger.py", "append_terminal_outcome"),
    "child": ("arnold_pipelines/megaplan/incident/ledger.py", "reserve_provider_route_child"),
}


def _definitions(path: Path) -> list[tuple[str, str, int]]:
    """Return ``(name, qualified-name, line)`` for function definitions."""

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"cannot parse {path}: {exc}") from exc

    result: list[tuple[str, str, int]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.parents: list[str] = []

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            qualified = ".".join((*self.parents, node.name))
            result.append((node.name, qualified, node.lineno))
            self.parents.append(node.name)
            self.generic_visit(node)
            self.parents.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            self._visit_function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            self._visit_function(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
            self.parents.append(node.name)
            self.generic_visit(node)
            self.parents.pop()

    Visitor().visit(tree)
    return result


def _source_files(root: Path) -> Iterable[Path]:
    package = root / "arnold_pipelines" / "megaplan"
    for path in sorted(package.rglob("*.py")):
        if any(part in {"__pycache__", ".venv"} for part in path.parts):
            continue
        yield path


def _authority_hits(root: Path, *, include: Iterable[Path] | None = None) -> dict[str, list[str]]:
    paths = list(include) if include is not None else list(_source_files(root))
    hits: dict[str, list[str]] = {kind: [] for kind in AUTHORITIES}
    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"cannot read {path}: {exc}") from exc
        if not any(re.search(rf"\b{re.escape(symbol)}\b", source) for _, symbol in AUTHORITIES.values()):
            continue
        definitions = _definitions(path)
        for kind, (expected_file, symbol) in AUTHORITIES.items():
            if relative != expected_file and include is None:
                # A definition in an unexpected production file is a second
                # authority even when the canonical file also defines it.
                for name, qualified, line in definitions:
                    if name == symbol:
                        hits[kind].append(f"{relative}:{qualified}:{line}")
                continue
            for name, qualified, line in definitions:
                if name == symbol:
                    hits[kind].append(f"{relative}:{qualified}:{line}")
    return hits


def _matrix_symbols(matrix: Path) -> set[str]:
    text = matrix.read_text(encoding="utf-8")
    # The allowlist is intentionally file-qualified.  Strip a possible class
    # prefix because both ``ledger.py:append_terminal_outcome`` and
    # ``ledger.py:IncidentLedger.append_terminal_outcome`` are equivalent
    # spellings in the frozen registry.
    return set(re.findall(r"arnold_pipelines/megaplan/[A-Za-z0-9_./-]+:[A-Za-z_][A-Za-z0-9_.]*", text))


def _check_production(root: Path, matrix: Path) -> list[str]:
    problems: list[str] = []
    symbols = _matrix_symbols(matrix)
    for kind, (file_name, symbol) in AUTHORITIES.items():
        hits = _authority_hits(root)[kind]
        if len(hits) != 1:
            problems.append(f"{kind} authority count={len(hits)} ({', '.join(hits)})")
            continue
        # The frozen registry must name the canonical location/symbol.  This
        # avoids silently accepting a moved authority while still allowing the
        # matrix to qualify a method with its owning class.
        if not any(
            file_name in item
            and (item.endswith(f":{symbol}") or f".{symbol}" in item)
            for item in symbols
        ):
            problems.append(f"{kind} authority is absent from matrix allowlist: {file_name}:{symbol}")
    return problems


def _check_fixture(path: Path, root: Path) -> str | None:
    try:
        hits = _authority_hits(root, include=[path])
    except ValueError as exc:
        return str(exc)
    duplicated = [f"{kind}={len(values)}" for kind, values in hits.items() if len(values) > 1]
    if duplicated:
        return None
    return "fixture does not contain a duplicate authority: " + ", ".join(
        f"{kind}={len(values)}" for kind, values in hits.items()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument("--negative-fixtures", type=Path, required=True)
    args = parser.parse_args(argv)

    matrix = args.matrix if args.matrix.is_absolute() else ROOT / args.matrix
    allowlist = args.allowlist if args.allowlist.is_absolute() else ROOT / args.allowlist
    fixtures = args.negative_fixtures if args.negative_fixtures.is_absolute() else ROOT / args.negative_fixtures

    problems = []
    if not matrix.is_file():
        problems.append(f"matrix missing: {matrix}")
    if not allowlist.is_file():
        problems.append(f"allowlist missing: {allowlist}")
    elif matrix.is_file() and allowlist.read_bytes() != matrix.read_bytes():
        problems.append("allowlist must be the file-qualified frozen matrix")
    if matrix.is_file() and allowlist.is_file():
        problems.extend(_check_production(ROOT, matrix))

    fixture_problems: list[str] = []
    if not fixtures.is_dir():
        fixture_problems.append(f"negative fixture directory missing: {fixtures}")
    else:
        fixture_paths = sorted(fixtures.glob("*.py"))
        if not fixture_paths:
            fixture_problems.append("negative fixture directory is empty")
        for path in fixture_paths:
            error = _check_fixture(path, ROOT)
            if error is not None:
                fixture_problems.append(f"{path.name}: {error}")

    if problems or fixture_problems:
        for problem in (*problems, *fixture_problems):
            print(f"A38 checker: FAIL; {problem}")
        return 1

    print("A38 checker: ALLOWLIST PASS; forbidden=0; negative_fixtures=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
