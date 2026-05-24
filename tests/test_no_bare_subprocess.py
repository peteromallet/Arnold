"""
AST-based guard test that walks megaplan/**/*.py and flags, outside
megaplan/runtime/process.py:

  (a) bare subprocess.Popen(...) calls
  (b) any call passing shell=True
  (c) bare os.killpg(...) calls

Each violation must be accounted for in the FROZEN deferral ledger.
The ledger is closed — no new entries may be added without deliberate
review.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Frozen deferral ledger — (relpath, reason) keyed by file path relative to
# the repository root.  Every file listed here has at least one violation
# that is intentionally deferred.  New entries are NOT permitted without
# explicit gate review; the test below enforces this by asserting that every
# violation found belongs to a file that appears in this dict.
# ---------------------------------------------------------------------------

FROZEN_LEDGER: dict[str, str] = {
    # ── anti-scoped / design-decision deferrals ──────────────────────────
    "megaplan/loop/engine.py": (
        "anti-scoped shell=True @ L254, commit 1ec7caab; "
        "_run_monitored_command uses shell=True + subprocess.Popen for "
        "the legacy observation loop — intentionally not migrated"
    ),
    "megaplan/agent/environments/patches.py": (
        "swerex RexCommand shell=True (T14 verdict); command strings "
        "may contain pipes/redirects/globs that require shell interpretation"
    ),
    "megaplan/agent/tools/process_registry.py": (
        "remote/PTY os.kill @ ~569 only — no local Popen handle exists; "
        "its os.killpg + spawn paths ARE already migrated"
    ),
    "megaplan/agent/tools/browser_tool.py": (
        "~1695 bare-PID daemon kill via os.kill (SD3) — daemon_pid is a "
        "raw int from a pidfile, no Popen handle; kill_group infeasible"
    ),
    # ── pending migration (in-scope but not yet landed) ──────────────────
    "megaplan/agent/tools/code_execution_tool.py": (
        "pending spawn migration @ L449 — preexec_fn=os.setsid; "
        "deferred from T5 scope, planned for later batch"
    ),
    # ── long-tail deferrals (not in current migration scope) ─────────────
    "megaplan/agent/tools/voice_mode.py": (
        "long-tail: voice playback subprocess.Popen, deferred migration"
    ),
    "megaplan/agent/tools/environments/docker.py": (
        "long-tail: Docker container subprocess management, deferred"
    ),
    "megaplan/agent/tools/environments/singularity.py": (
        "long-tail: Singularity container subprocess management, deferred"
    ),
    "megaplan/agent/tools/environments/ssh.py": (
        "long-tail: SSH remote subprocess management, deferred"
    ),
    "megaplan/agent/gateway/run.py": (
        "long-tail: gateway subprocess spawns, deferred"
    ),
    "megaplan/bakeoff/handlers.py": (
        "long-tail: bakeoff asyncio subprocess management, deferred"
    ),
    "megaplan/bakeoff/orchestrator.py": (
        "long-tail: bakeoff orchestration subprocesses, deferred"
    ),
    "megaplan/bakeoff/judge.py": (
        "long-tail: asyncio subprocess for judge agent calls, deferred"
    ),
    "megaplan/cloud/providers/base.py": (
        "long-tail: cloud provider subprocess execution, deferred"
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_test_file(path: Path) -> bool:
    """Return True if *path* is a test file and should be excluded."""
    name = path.name
    parts = path.parts
    # Standard pytest naming conventions
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    # Files inside a tests/ or test/ directory
    if "tests" in parts or "test" in parts:
        return True
    return False


def _relpath(path: Path, root: Path) -> str:
    """Return *path* relative to *root* using forward slashes."""
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_popen_call(node: ast.Call) -> bool:
    """Return True if *node* is a subprocess.Popen(...) call."""
    func = node.func
    if isinstance(func, ast.Attribute):
        if func.attr == "Popen":
            if isinstance(func.value, ast.Name) and func.value.id == "subprocess":
                return True
    return False


def _is_killpg_call(node: ast.Call) -> bool:
    """Return True if *node* is an os.killpg(...) call."""
    func = node.func
    if isinstance(func, ast.Attribute):
        if func.attr == "killpg":
            if isinstance(func.value, ast.Name) and func.value.id == "os":
                return True
    return False


def _has_shell_true(node: ast.Call) -> bool:
    """Return True if *node* has a keyword argument shell=True."""
    for kw in node.keywords:
        if kw.arg == "shell":
            # Python 3.8+ uses ast.Constant; older uses ast.NameConstant
            value = kw.value
            if isinstance(value, ast.Constant) and value.value is True:
                return True
            # Python < 3.8 compat
            if hasattr(ast, "NameConstant") and isinstance(value, ast.NameConstant):
                if value.value is True:
                    return True
    return False


class ViolationVisitor(ast.NodeVisitor):
    """Collect (line_number, description) tuples for each violation."""

    def __init__(self) -> None:
        self.violations: list[tuple[int, str]] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if _is_popen_call(node):
            self.violations.append((node.lineno, "subprocess.Popen(...) call"))
        if _is_killpg_call(node):
            self.violations.append((node.lineno, "os.killpg(...) call"))
        if _has_shell_true(node):
            self.violations.append((node.lineno, "call with shell=True"))
        self.generic_visit(node)


def _find_violations(filepath: Path) -> list[tuple[int, str]]:
    """Parse *filepath* and return a list of (line, description) violations."""
    try:
        source = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []
    visitor = ViolationVisitor()
    visitor.visit(tree)
    return visitor.violations


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_no_bare_subprocess_outside_runtime() -> None:
    """Walk megaplan/**/*.py and ensure every violation is in the frozen ledger."""
    repo_root = Path(__file__).resolve().parents[1]
    megaplan_dir = repo_root / "megaplan"
    runtime_module = megaplan_dir / "runtime" / "process.py"

    if not megaplan_dir.is_dir():
        pytest.skip("megaplan/ directory not found")

    # ── Collect all violations keyed by relpath ──────────────────────────
    violations_by_file: dict[str, list[tuple[int, str]]] = {}
    scanned = 0
    for py_file in sorted(megaplan_dir.rglob("*.py")):
        if py_file.resolve() == runtime_module.resolve():
            continue  # the blessed module
        if _is_test_file(py_file):
            continue
        scanned += 1
        rel = _relpath(py_file, repo_root)
        found = _find_violations(py_file)
        if found:
            violations_by_file[rel] = found

    assert scanned > 0, "no megaplan source files scanned — check path"

    # ── Check every violation is in the frozen ledger ────────────────────
    unledgered: dict[str, list[tuple[int, str]]] = {}
    for rel, violations in violations_by_file.items():
        if rel not in FROZEN_LEDGER:
            unledgered[rel] = violations

    if unledgered:
        msg_lines = [
            "UNLEDGERED subprocess violations found — the frozen deferral ledger",
            f"is closed.  Add entries to FROZEN_LEDGER in {__file__} ONLY after",
            "explicit gate review:\n",
        ]
        for rel, violations in sorted(unledgered.items()):
            msg_lines.append(f"  {rel}:")
            for lineno, desc in violations:
                msg_lines.append(f"    L{lineno}: {desc}")
        pytest.fail("\n".join(msg_lines))

    # ── Sanity: the ledger should not be empty ───────────────────────────
    assert len(FROZEN_LEDGER) > 0, "FROZEN_LEDGER is empty — expected known deferrals"

    # ── Report coverage (informational) ──────────────────────────────────
    ledgered_files = set(FROZEN_LEDGER) & set(violations_by_file)
    extra_ledger = set(FROZEN_LEDGER) - set(violations_by_file)
    print(f"\nScanned {scanned} megaplan source files.")
    print(f"Violations found in {len(violations_by_file)} files "
          f"({len(ledgered_files)} ledgered).")
    if extra_ledger:
        print(f"Ledger entries without current violations ({len(extra_ledger)}): "
              f"{sorted(extra_ledger)}")
