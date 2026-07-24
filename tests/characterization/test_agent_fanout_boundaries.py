from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PHASE_DIRS = (
    PROJECT_ROOT / "arnold" / "pipelines" / "megaplan" / "handlers",
    PROJECT_ROOT / "arnold" / "pipelines" / "megaplan" / "orchestration",
    PROJECT_ROOT / "arnold" / "pipelines" / "megaplan" / "review",
)

ALLOWED_RAW_FANOUT_MODULES = {
    Path("arnold/pipelines/megaplan/_core/hermes_fanout.py"),
    Path("arnold/pipelines/megaplan/_core/process_fanout.py"),
    Path("arnold/pipelines/megaplan/_core/worker_fanout.py"),
    Path("arnold/pipelines/megaplan/workers/hermes.py"),
    # Legacy compatibility shim for tests that still import _run_check.
    # The production run_parallel_critique path below this shim dispatches
    # through WorkerUnit/scatter_worker_units.
    Path("arnold/pipelines/megaplan/orchestration/parallel_critique.py"),
}

PROHIBITED_IMPORTS = {
    "concurrent.futures",
    "multiprocessing",
    "arnold_pipelines.megaplan.workers.hermes",
}

PROHIBITED_NAMES = {
    "ThreadPoolExecutor",
    "ProcessPoolExecutor",
    "scatter_gather_processes",
    "scatter_gather_checks",
    "AIAgent",
    "_import_hermes_runtime",
}


def _phase_modules() -> list[Path]:
    modules: list[Path] = []
    for directory in PHASE_DIRS:
        modules.extend(path for path in directory.glob("*.py") if path.name != "__init__.py")
    return sorted(modules)


def _raw_fanout_violations(path: Path, source: str) -> list[str]:
    rel = path.relative_to(PROJECT_ROOT)
    if rel in ALLOWED_RAW_FANOUT_MODULES:
        return []

    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in PROHIBITED_IMPORTS:
                    violations.append(f"{rel}: imports {alias.name}")
                if alias.name in PROHIBITED_NAMES:
                    violations.append(f"{rel}: imports {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in PROHIBITED_IMPORTS:
                violations.append(f"{rel}: imports from {module}")
            for alias in node.names:
                if alias.name in PROHIBITED_NAMES:
                    violations.append(f"{rel}: imports {alias.name} from {module}")
        elif isinstance(node, ast.Name) and node.id in PROHIBITED_NAMES:
            violations.append(f"{rel}: uses {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in PROHIBITED_NAMES:
            violations.append(f"{rel}: uses {node.attr}")
    return violations


def test_phase_modules_do_not_own_raw_agent_fanout() -> None:
    violations: list[str] = []
    for path in _phase_modules():
        violations.extend(_raw_fanout_violations(path, path.read_text()))

    assert violations == []


def test_boundary_guard_detects_prohibited_phase_level_import() -> None:
    source = "from concurrent.futures import ThreadPoolExecutor\nThreadPoolExecutor()\n"
    fake_path = PROJECT_ROOT / "arnold" / "pipelines" / "megaplan" / "orchestration" / "fake_phase.py"

    violations = _raw_fanout_violations(fake_path, source)

    assert any("ThreadPoolExecutor" in item for item in violations)
