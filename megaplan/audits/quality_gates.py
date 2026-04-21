from __future__ import annotations

import ast
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable

DEFAULT_TIME_BUDGET_SECONDS = 5.0
DEFAULT_FILE_GROWTH_THRESHOLD = 200
DEFAULT_DUPLICATE_SIMILARITY_THRESHOLD = 0.8
DEFAULT_DUPLICATE_MAX_FILE_LINES = 1000


def capture_before_line_counts(project_dir: Path, paths: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for relative_path in paths:
        if not isinstance(relative_path, str) or not relative_path.strip():
            continue
        line_count, _ = _read_text_file(project_dir / relative_path)
        if line_count is None:
            continue
        counts[relative_path] = _count_lines(line_count)
    return counts


def run_quality_checks(
    project_dir: Path,
    *,
    changed_paths: Iterable[str],
    before_line_counts: dict[str, int] | None = None,
    config: dict[str, Any] | None = None,
) -> list[str]:
    normalized_paths = sorted(
        {
            path.strip()
            for path in changed_paths
            if isinstance(path, str) and path.strip()
        }
    )
    if not normalized_paths:
        return []

    resolved_config = _resolve_quality_config(config)
    budget_seconds = resolved_config["time_budget_seconds"]
    start = time.monotonic()
    advisories: list[str] = []
    checks = [
        ("file_growth", _check_file_growth),
        ("duplicate_functions", _check_duplicate_functions),
        ("dead_imports", _check_dead_imports),
        ("test_coverage", _check_test_coverage),
    ]

    for index, (check_name, check_fn) in enumerate(checks):
        check_config = resolved_config[check_name]
        if not check_config["enabled"]:
            continue
        if time.monotonic() - start >= budget_seconds:
            advisories.append(_advisory(_time_budget_message(budget_seconds)))
            break
        try:
            advisories.extend(
                check_fn(
                    project_dir,
                    normalized_paths,
                    before_line_counts or {},
                    check_config,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive guard for advisory-only checks.
            advisories.append(_advisory(f"skipped {check_name} check due to unexpected failure: {exc}"))
        if index < len(checks) - 1 and time.monotonic() - start >= budget_seconds:
            advisories.append(_advisory(_time_budget_message(budget_seconds)))
            break

    return advisories


def _check_file_growth(
    project_dir: Path,
    changed_paths: list[str],
    before_line_counts: dict[str, int],
    config: dict[str, Any],
) -> list[str]:
    threshold = _as_int(
        config.get("threshold", config.get("threshold_lines")),
        DEFAULT_FILE_GROWTH_THRESHOLD,
    )
    advisories: list[str] = []

    for relative_path in changed_paths:
        target = project_dir / relative_path
        if not target.exists() or not target.is_file():
            continue
        text, error = _read_text_file(target)
        if text is None:
            advisories.append(_advisory(f"skipped file growth for {relative_path}: {error}"))
            continue
        baseline = before_line_counts.get(relative_path)
        if baseline is None:
            baseline, error = _line_count_from_head(project_dir, relative_path)
            if baseline is None:
                advisories.append(_advisory(f"skipped file growth for {relative_path}: {error}"))
                continue
        growth = _count_lines(text) - baseline
        if growth > threshold:
            advisories.append(
                _advisory(f"{relative_path} grew by {growth} lines (threshold {threshold}).")
            )

    return advisories


def _check_duplicate_functions(
    project_dir: Path,
    changed_paths: list[str],
    _before_line_counts: dict[str, int],
    config: dict[str, Any],
) -> list[str]:
    similarity_threshold = _as_float(
        config.get("similarity_threshold"),
        DEFAULT_DUPLICATE_SIMILARITY_THRESHOLD,
    )
    max_file_lines = _as_int(config.get("max_file_lines"), DEFAULT_DUPLICATE_MAX_FILE_LINES)
    advisories: list[str] = []

    for relative_path in changed_paths:
        if Path(relative_path).suffix != ".py":
            continue
        target = project_dir / relative_path
        if not target.exists() or not target.is_file():
            continue
        text, error = _read_text_file(target)
        if text is None:
            advisories.append(_advisory(f"skipped duplicate detection for {relative_path}: {error}"))
            continue
        lines = text.splitlines()
        if len(lines) > max_file_lines:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            advisories.append(_advisory(f"skipped duplicate detection for {relative_path}: syntax error ({exc.msg})."))
            continue

        functions = _function_bodies(tree, lines)
        for left_index, (left_name, left_body) in enumerate(functions):
            for right_name, right_body in functions[left_index + 1:]:
                similarity = _jaccard_similarity(left_body, right_body)
                if similarity >= similarity_threshold:
                    advisories.append(
                        _advisory(
                            f"{relative_path} has similar functions {left_name} and {right_name} "
                            f"({similarity:.0%} similarity)."
                        )
                    )

    return advisories


def _check_dead_imports(
    project_dir: Path,
    changed_paths: list[str],
    _before_line_counts: dict[str, int],
    _config: dict[str, Any],
) -> list[str]:
    advisories: list[str] = []

    for relative_path in changed_paths:
        if Path(relative_path).suffix != ".py" or Path(relative_path).name == "__init__.py":
            continue
        target = project_dir / relative_path
        if not target.exists() or not target.is_file():
            continue
        text, error = _read_text_file(target)
        if text is None:
            advisories.append(_advisory(f"skipped dead import detection for {relative_path}: {error}"))
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            advisories.append(_advisory(f"skipped dead import detection for {relative_path}: syntax error ({exc.msg})."))
            continue

        used_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        unused_imports = [
            display_name
            for display_name, binding_name in _import_bindings(tree)
            if binding_name and binding_name not in used_names
        ]
        if unused_imports:
            advisories.append(
                _advisory(
                    f"{relative_path} adds unused imports: {', '.join(sorted(unused_imports))}."
                )
            )

    return advisories


def _check_test_coverage(
    project_dir: Path,
    changed_paths: list[str],
    _before_line_counts: dict[str, int],
    _config: dict[str, Any],
) -> list[str]:
    code_paths: list[str] = []
    test_paths: list[str] = []

    for relative_path in changed_paths:
        target = project_dir / relative_path
        if not target.exists() or not target.is_file():
            continue
        if _is_test_path(relative_path):
            test_paths.append(relative_path)
            continue
        if Path(relative_path).suffix == ".py":
            code_paths.append(relative_path)

    if code_paths and not test_paths:
        listed = ", ".join(sorted(code_paths))
        return [_advisory(f"code changes lacked test updates: {listed}.")]
    return []


def _resolve_quality_config(config: dict[str, Any] | None) -> dict[str, Any]:
    root = config if isinstance(config, dict) else {}

    return {
        "time_budget_seconds": _as_float(
            root.get("time_budget_seconds"),
            DEFAULT_TIME_BUDGET_SECONDS,
        ),
        "file_growth": _resolve_check_config(
            root.get("file_growth"),
            {"enabled": True, "threshold": DEFAULT_FILE_GROWTH_THRESHOLD},
        ),
        "duplicate_functions": _resolve_check_config(
            root.get("duplicate_functions"),
            {
                "enabled": True,
                "similarity_threshold": DEFAULT_DUPLICATE_SIMILARITY_THRESHOLD,
                "max_file_lines": DEFAULT_DUPLICATE_MAX_FILE_LINES,
            },
        ),
        "dead_imports": _resolve_check_config(root.get("dead_imports"), {"enabled": True}),
        "test_coverage": _resolve_check_config(root.get("test_coverage"), {"enabled": True}),
    }


def _resolve_check_config(raw: Any, defaults: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return dict(defaults)
    resolved = dict(defaults)
    resolved.update(raw)
    resolved["enabled"] = bool(resolved.get("enabled", True))
    return resolved


def _line_count_from_head(project_dir: Path, relative_path: str) -> tuple[int | None, str | None]:
    if not (project_dir / ".git").exists():
        return None, "git baseline unavailable because the project is not a git repository."
    try:
        process = subprocess.run(
            ["git", "show", f"HEAD:{relative_path}"],
            cwd=str(project_dir),
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError:
        return None, "git baseline unavailable because git is not on PATH."
    except subprocess.TimeoutExpired:
        return None, "git show timed out while reading the baseline."

    if process.returncode != 0:
        stderr = process.stderr.decode("utf-8", errors="replace").strip()
        stdout = process.stdout.decode("utf-8", errors="replace").strip()
        combined = stderr or stdout or "unknown git error"
        if _looks_like_new_file_error(combined):
            return 0, None
        return None, f"git show failed ({combined})."

    try:
        text = process.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None, "baseline file in HEAD is binary."
    return _count_lines(text), None


def _looks_like_new_file_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "exists on disk, but not in 'head'" in lowered
        or "does not exist in 'head'" in lowered
        or "path '" in lowered and "not in 'head'" in lowered
    )


def _read_text_file(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return None, "file is binary or not valid UTF-8"
    except OSError as exc:
        return None, str(exc)


def _count_lines(text: str) -> int:
    return len(text.splitlines())


def _function_bodies(tree: ast.AST, lines: list[str]) -> list[tuple[str, set[str]]]:
    functions: list[tuple[str, set[str]]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.body:
            continue
        start_line = getattr(node.body[0], "lineno", node.lineno)
        end_line = getattr(node.body[-1], "end_lineno", start_line)
        normalized_lines = {
            normalized
            for line in lines[start_line - 1:end_line]
            if (normalized := _normalize_source_line(line))
        }
        if normalized_lines:
            functions.append((node.name, normalized_lines))

    return functions


def _normalize_source_line(line: str) -> str:
    return " ".join(line.strip().split())


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _import_bindings(tree: ast.AST) -> list[tuple[str, str]]:
    bindings: list[tuple[str, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                binding_name = alias.asname or alias.name.split(".")[0]
                bindings.append((alias.asname or alias.name, binding_name))
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                binding_name = alias.asname or alias.name
                display_name = alias.asname or alias.name
                bindings.append((display_name, binding_name))

    return bindings


def _is_test_path(relative_path: str) -> bool:
    posix_path = Path(relative_path).as_posix()
    name = Path(relative_path).name
    stem = Path(relative_path).stem
    return (
        "/tests/" in f"/{posix_path}/"
        or "/test/" in f"/{posix_path}/"
        or name.startswith("test_")
        or stem.endswith("_test")
    )


def _advisory(message: str) -> str:
    return f"Advisory quality: {message}"


def _time_budget_message(budget_seconds: float) -> str:
    return f"skipped remaining quality checks after reaching the {budget_seconds:.1f}-second budget."


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed
