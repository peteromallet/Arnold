"""Static repo-local Python import graph helpers."""

from __future__ import annotations

import ast
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


DEFAULT_IGNORE_DIRS = frozenset({
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".megaplan",
    ".mypy_cache",
    ".pytest_cache",
    "build",
    "dist",
    ".tox",
    ".eggs",
})


def _is_valid_module_segment(segment: str) -> bool:
    return bool(segment) and segment.isidentifier()


def _module_parts_for_path(
    rel_path: str,
    *,
    package_roots: tuple[str, ...] = (),
) -> tuple[str, ...] | None:
    rel_path = _strip_package_root(rel_path, package_roots)
    path = Path(rel_path)
    without_suffix = path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if any(part.startswith(".") for part in parts):
        return None
    if any(not _is_valid_module_segment(part) for part in parts):
        return None
    return tuple(parts)


@dataclass(frozen=True)
class ImportResolution:
    """Tests that transitively import changed files through repo-local modules."""

    test_files: list[str]
    unresolved: list[str]
    degraded: bool


class ImportGraph:
    """AST-only import graph for Python files under one repository root."""

    def __init__(
        self,
        *,
        file_to_module: dict[str, str],
        module_to_file: dict[str, str],
        forward_edges: dict[str, frozenset[str]],
        degraded: bool,
    ) -> None:
        self._file_to_module = file_to_module
        self._module_to_file = module_to_file
        self._forward_edges = forward_edges
        self._degraded = degraded
        self._reverse_edges = _reverse_edges(forward_edges)

    @classmethod
    def build(
        cls,
        repo_root: Path,
        *,
        ignore_dirs: frozenset[str] = DEFAULT_IGNORE_DIRS,
        package_roots: list[str] | None = None,
    ) -> "ImportGraph":
        """Build a repo-local import graph without importing target code."""

        root = repo_root.resolve()
        py_files: list[Path] = []
        for path in sorted(root.rglob("*.py")):
            try:
                rel_path = path.relative_to(root)
            except ValueError:
                continue
            if any(part in ignore_dirs for part in rel_path.parts):
                continue
            rel_posix = rel_path.as_posix()
            if _module_parts_for_path(rel_posix) is None:
                continue
            py_files.append(path)

        resolved_package_roots = _resolve_package_roots(
            root,
            py_files,
            package_roots,
        )
        file_to_module: dict[str, str] = {}
        module_to_file: dict[str, str] = {}
        for path in py_files:
            rel_path = path.relative_to(root).as_posix()
            module = _module_name_for_path(
                rel_path,
                package_roots=resolved_package_roots,
            )
            file_to_module[rel_path] = module
            module_to_file.setdefault(module, rel_path)

        forward_edges: dict[str, frozenset[str]] = {}
        degraded = False
        for path in py_files:
            rel_path = path.relative_to(root).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel_path)
            except (OSError, SyntaxError, ValueError, UnicodeDecodeError):
                degraded = True
                continue

            imports = _extract_imports(
                tree,
                importer_module=file_to_module[rel_path],
                importer_rel_path=rel_path,
                module_to_file=module_to_file,
            )
            forward_edges[rel_path] = frozenset(imports)

        return cls(
            file_to_module=file_to_module,
            module_to_file=module_to_file,
            forward_edges=forward_edges,
            degraded=degraded,
        )

    def tests_importing(
        self,
        changed_files: Iterable[str],
        *,
        is_test_file: Callable[[str], bool],
    ) -> ImportResolution:
        """Return tests that transitively import any changed repo-local file."""

        test_files: set[str] = set()
        unresolved: set[str] = set()

        normalized = sorted(
            {_normalize_relpath(path) for path in changed_files if path}
        )
        for changed_file in normalized:
            if changed_file not in self._file_to_module:
                unresolved.add(changed_file)
                continue

            queue: deque[str] = deque(self._reverse_edges.get(changed_file, []))
            visited: set[str] = set()
            while queue:
                rel_path = queue.popleft()
                if rel_path in visited:
                    continue
                visited.add(rel_path)
                if is_test_file(rel_path):
                    test_files.add(rel_path)
                for importer in self._reverse_edges.get(rel_path, []):
                    if importer not in visited:
                        queue.append(importer)

        return ImportResolution(
            test_files=sorted(test_files),
            unresolved=sorted(unresolved),
            degraded=self._degraded,
        )


def _normalize_relpath(path: str) -> str:
    return Path(path).as_posix().lstrip("./")


def _resolve_package_roots(
    repo_root: Path,
    py_files: list[Path],
    package_roots: list[str] | None,
) -> tuple[str, ...]:
    if package_roots is not None:
        return _normalize_package_roots(package_roots)

    src_dir = repo_root / "src"
    if not src_dir.is_dir() or (src_dir / "__init__.py").exists():
        return ()

    candidate_roots = ("src",)
    if _package_root_mapping_is_ambiguous(repo_root, py_files, candidate_roots):
        return ()
    return candidate_roots


def _normalize_package_roots(package_roots: Iterable[str]) -> tuple[str, ...]:
    normalized: set[str] = set()
    for raw_root in package_roots:
        if not isinstance(raw_root, str) or not raw_root.strip():
            continue
        candidate = Path(raw_root.strip())
        if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
            continue
        rel = candidate.as_posix().strip("/")
        if rel and rel != ".":
            normalized.add(rel)
    return tuple(sorted(normalized, key=lambda value: (-len(Path(value).parts), value)))


def _package_root_mapping_is_ambiguous(
    repo_root: Path,
    py_files: list[Path],
    package_roots: tuple[str, ...],
) -> bool:
    seen: dict[str, str] = {}
    for path in py_files:
        rel_path = path.relative_to(repo_root).as_posix()
        module = _module_name_for_path(rel_path, package_roots=package_roots)
        existing = seen.get(module)
        if existing is not None and existing != rel_path:
            return True
        seen[module] = rel_path
    return False


def _module_name_for_path(
    rel_path: str,
    *,
    package_roots: tuple[str, ...] = (),
) -> str:
    parts = _module_parts_for_path(rel_path, package_roots=package_roots)
    if parts is None:
        raise ValueError(f"path {rel_path!r} is not importable as a Python module")
    return ".".join(parts)


def _strip_package_root(rel_path: str, package_roots: tuple[str, ...]) -> str:
    rel_parts = Path(rel_path).parts
    for package_root in package_roots:
        root_parts = Path(package_root).parts
        if rel_parts[: len(root_parts)] == root_parts:
            stripped = rel_parts[len(root_parts) :]
            if stripped:
                return Path(*stripped).as_posix()
    return rel_path


def _extract_imports(
    tree: ast.AST,
    *,
    importer_module: str,
    importer_rel_path: str,
    module_to_file: dict[str, str],
) -> list[str]:
    imported_files: set[str] = set()
    importer_package = _package_for_importer(importer_module, importer_rel_path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for rel_path in _resolve_known_modules_and_prefixes(
                    alias.name,
                    module_to_file,
                ):
                    imported_files.add(rel_path)
            continue

        if isinstance(node, ast.ImportFrom):
            module = _resolve_from_module(
                node.module,
                node.level,
                importer_package=importer_package,
            )
            if module is None:
                continue

            base_file = module_to_file.get(module)
            if base_file is not None:
                imported_files.add(base_file)

            for alias in node.names:
                if alias.name == "*":
                    continue
                submodule = f"{module}.{alias.name}" if module else alias.name
                submodule_file = module_to_file.get(submodule)
                if submodule_file is not None:
                    imported_files.add(submodule_file)

    return sorted(imported_files)


def _package_for_importer(importer_module: str, importer_rel_path: str) -> str:
    if importer_rel_path.endswith("/__init__.py") or importer_rel_path == "__init__.py":
        return importer_module
    parts = importer_module.split(".")
    return ".".join(parts[:-1])


def _resolve_known_modules_and_prefixes(
    module: str,
    module_to_file: dict[str, str],
) -> list[str]:
    rel_paths: list[str] = []
    parts = module.split(".")
    for end in range(1, len(parts) + 1):
        candidate = ".".join(parts[:end])
        rel_path = module_to_file.get(candidate)
        if rel_path is not None:
            rel_paths.append(rel_path)
    return rel_paths


def _resolve_from_module(
    module: str | None,
    level: int,
    *,
    importer_package: str,
) -> str | None:
    if level == 0:
        return module or ""

    package_parts = importer_package.split(".") if importer_package else []
    ascents = level - 1
    if ascents > len(package_parts):
        return None

    base_parts = package_parts[: len(package_parts) - ascents]
    if module:
        base_parts.extend(module.split("."))
    return ".".join(base_parts)


def _reverse_edges(forward_edges: dict[str, frozenset[str]]) -> dict[str, list[str]]:
    reverse_edges: dict[str, list[str]] = {}
    for importer in sorted(forward_edges):
        for imported in sorted(forward_edges[importer]):
            reverse_edges.setdefault(imported, []).append(importer)
    for importers in reverse_edges.values():
        importers.sort()
    return reverse_edges
