"""Step 14 (T17): Static negative checks for WBC ledger ownership boundaries.

This module enforces non-negotiable static invariants:

1. No second WBC store/API class — only one ``AttemptLedgerStore`` ABC and
   one ``SqliteAttemptLedgerStore`` implementation are permitted.
2. No Custody-owned attempt ledger — no custody module may define or own
   an attempt-ledger class.
3. No adapter path that swallows append failures — the
   ``LedgerStoreAdapter`` must propagate (not suppress) required-write
   persistence failures.
4. No adapter path that skips sequence gaps — the adapter must not contain
   logic that silently ignores gaps in the event sequence.
5. No production mutation import of ``ExecutionAttemptLedger`` that
   bypasses the store boundary — only approved WBC modules may import
   ``ExecutionAttemptLedger`` for construction/reconstruction; no
   non-store production module may import it for mutation.

Every assertion in this module is treated as a **blocking** ownership
boundary — a failure here means the WBC substrate contract has been
breached and must be remediated before any further M6A work proceeds.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import FrozenSet, List, Set, Tuple

import pytest

# ── Approved locations ──────────────────────────────────────────────────────

# These are the ONLY modules that may import ExecutionAttemptLedger.
# All other production imports are a bypass of the store boundary.
_APPROVED_EXECUTION_ATTEMPT_LEDGER_IMPORTERS: FrozenSet[str] = frozenset(
    {
        "arnold/workflow/__init__.py",          # re-exports schema types
        "arnold/workflow/attempt_ledger_store.py",  # the store itself
        "arnold/workflow/ledger_outbox.py",     # outbox ties to store
        "arnold/workflow/ledger_trace.py",      # trace evidence
        "arnold/adapters/ledger_store_adapter.py",  # official adapter
    }
)

# These are the ONLY classes that may act as WBC attempt-ledger stores.
_APPROVED_STORE_CLASSES: FrozenSet[str] = frozenset(
    {
        "AttemptLedgerStore",       # ABC in attempt_ledger_store.py
        "SqliteAttemptLedgerStore", # SQLite impl in attempt_ledger_store.py
    }
)

# Additional allowed store-related classes that are exceptions, not alternative stores.
_ALLOWED_STORE_RELATED_CLASSES: FrozenSet[str] = frozenset(
    {
        "AttemptLedgerError",
        "MonotonicSequenceError",
        "PostTerminalAppendError",
    }
)

# The file where the WBC store lives.
_STORE_MODULE_PATH: str = "arnold/workflow/attempt_ledger_store.py"

# Custody-owned packages — these must NOT define an attempt-ledger store.
_CUSTODY_PACKAGE_ROOTS: FrozenSet[str] = frozenset(
    {
        "arnold_pipelines/megaplan/cloud",
        "arnold_pipelines/megaplan/authority",
        "arnold_pipelines/megaplan/orchestration",
        "arnold_pipelines/megaplan/resident",
    }
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _project_root() -> Path:
    """Return the project root (two levels above this test file)."""
    return Path(__file__).resolve().parent.parent.parent.parent


def _production_py_files() -> List[Path]:
    """Return all production .py files under arnold/ (excluding tests)."""
    root = _project_root()
    src = root / "arnold"
    return sorted(p for p in src.rglob("*.py") if p.is_file())


def _find_class_definitions(
    file_path: Path,
) -> List[Tuple[str, ast.ClassDef]]:
    """Return (module_relpath, ClassDef) for every class defined in *file_path*."""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    rel = str(file_path.relative_to(_project_root()))
    return [
        (rel, node)
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    ]


def _find_imports_from(
    file_path: Path, module_name: str
) -> List[Tuple[str, str]]:
    """Return [(imported_name, alias_or_name)] for all imports from *module_name*."""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    rel = str(file_path.relative_to(_project_root()))
    results: List[Tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == module_name:
                for alias in node.names:
                    results.append((alias.name, alias.asname or alias.name))
    return results


def _find_try_except_in_function(
    file_path: Path, func_name: str
) -> List[ast.Try]:
    """Return all Try nodes within function *func_name* in *file_path*."""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    results: List[ast.Try] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                for child in ast.walk(node):
                    if isinstance(child, ast.Try):
                        results.append(child)
    return results


def _bare_except_handlers(try_node: ast.Try) -> List[ast.ExceptHandler]:
    """Return handlers from *try_node* that catch everything (bare except or
    except Exception)."""
    bare: List[ast.ExceptHandler] = []
    for handler in try_node.handlers:
        if handler.type is None:
            bare.append(handler)
        elif isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
            bare.append(handler)
    return bare


# ── Test: No second WBC store/API class ─────────────────────────────────────

def test_no_second_wbc_store_class() -> None:
    """Assert that only one ABC and one SQLite store implementation exist.

    No other class in the codebase may masquerade as an attempt-ledger
    store.  Schema-only definitions (``ExecutionAttemptLedger``) are fine;
    this check targets classes that implement store-like interfaces.
    """
    root = _project_root()
    store_file = root / _STORE_MODULE_PATH

    # Collect all class definitions in the store file.
    store_classes: Set[str] = set()
    for rel, node in _find_class_definitions(store_file):
        store_classes.add(node.name)

    # The store file must contain both approved store classes.
    missing = _APPROVED_STORE_CLASSES - store_classes
    assert not missing, (
        f"Store file {_STORE_MODULE_PATH} is missing expected classes: {missing}"
    )

    # Now scan ALL production files for any other class that looks like a
    # ledger store — i.e. class names containing 'LedgerStore' or
    # 'AttemptLedger' (excluding ExecutionAttemptLedger, which is a schema
    # definition, not a store).
    suspicious: List[Tuple[str, str]] = []
    for py_file in _production_py_files():
        rel = str(py_file.relative_to(root))
        for _, node in _find_class_definitions(py_file):
            name = node.name
            # Skip approved classes and allowed related classes.
            if name in _APPROVED_STORE_CLASSES:
                continue
            if name in _ALLOWED_STORE_RELATED_CLASSES:
                continue
            # ExecutionAttemptLedger is the schema class, not a store.
            if name == "ExecutionAttemptLedger":
                continue
            # LedgerStoreAdapter is the adapter, not a second store.
            if name == "LedgerStoreAdapter":
                continue
            # Check for names that suggest alternative store implementations.
            lowered = name.lower()
            if ("ledgerstore" in lowered or "attemptledgerstore" in lowered
                    or "ledger_store" in lowered or "attempt_ledger_store" in lowered):
                suspicious.append((rel, name))

    assert not suspicious, (
        f"Found suspicious store-like classes outside "
        f"{_STORE_MODULE_PATH}: {suspicious}"
    )


# ── Test: No Custody-owned attempt ledger ───────────────────────────────────

def test_no_custody_owned_attempt_ledger() -> None:
    """Assert that no custody-owned package defines an attempt-ledger class.

    Custody packages (cloud, authority, orchestration, resident) live in
    ``arnold_pipelines/megaplan/``. They must not define or claim ownership
    of any attempt-ledger storage class.
    """
    root = _project_root()
    violations: List[Tuple[str, str]] = []

    for custody_root_rel in _CUSTODY_PACKAGE_ROOTS:
        custody_dir = root / custody_root_rel
        if not custody_dir.is_dir():
            continue
        for py_file in sorted(custody_dir.rglob("*.py")):
            rel = str(py_file.relative_to(root))
            for _, node in _find_class_definitions(py_file):
                name = node.name
                lowered = name.lower()
                # Look for any class that claims to be a ledger or attempt
                # store in custody territory.
                if any(
                    token in lowered
                    for token in (
                        "attemptledger",
                        "ledgerstore",
                        "attempt_ledger",
                        "ledger_store",
                        "executionattemptledger",
                        "execution_attempt_ledger",
                    )
                ):
                    violations.append((rel, name))

    assert not violations, (
        f"Custody-owned modules must not define attempt-ledger classes. "
        f"Found: {violations}"
    )


# ── Test: No adapter path that swallows append failures ─────────────────────

def test_adapter_does_not_swallow_append_failures() -> None:
    """Assert that LedgerStoreAdapter does not suppress append failures.

    The adapter's ``_retry_on_transient_lock`` method and all ``append_*``
    methods must propagate non-transient errors immediately.  This test
    verifies that:

    * No ``except Exception: pass`` or bare ``except: pass`` exists in the
      append codepaths.
    * The ``_retry_on_transient_lock`` method re-raises non-transient errors.
    * No ``append_*`` method wraps the call in a broad try/except that
      could mask a persistence failure.
    """
    root = _project_root()
    adapter_path = root / "arnold/adapters/ledger_store_adapter.py"
    source = adapter_path.read_text(encoding="utf-8")

    # Check 1: No bare except with just 'pass' or 'return None' in the
    # append methods or _retry_on_transient_lock.
    # We scan the source for patterns like:
    #   except ...:
    #       pass
    #   except ...:
    #       return None
    # within functions related to append.
    tree = ast.parse(source)

    # Collect function names that are append-related.
    append_related_funcs = {
        "_retry_on_transient_lock",
        "append_event",
        "append_started",
        "append_completed",
        "append_failed",
        "append_cancelled",
    }

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in append_related_funcs:
                _check_no_swallowed_exceptions(node, node.name)

    # Check 2: Verify that _retry_on_transient_lock propagates
    # non-OperationalError exceptions.  We do this by scanning the
    # method body for an `except Exception` clause — if one exists, it
    # must re-raise, not pass/suppress/return.
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_retry_on_transient_lock":
            # The method must have a path that re-raises non-transient errors.
            # We check that the `except Exception` handler re-raises.
            for child in ast.walk(node):
                if isinstance(child, ast.Try):
                    for handler in child.handlers:
                        if handler.type is not None:
                            # Check if this is catching Exception broadly
                            if (isinstance(handler.type, ast.Name)
                                    and handler.type.id == "Exception"):
                                # Must re-raise, not suppress.
                                _assert_handler_re_raises(handler, "_retry_on_transient_lock")


def _check_no_swallowed_exceptions(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef, func_name: str
) -> None:
    """Walk *func_node* and assert no try/except silently swallows errors."""
    for child in ast.walk(func_node):
        if isinstance(child, ast.Try):
            for handler in child.handlers:
                # Bare except: pass is a swallow.
                if handler.type is None:
                    _assert_not_swallowing(handler, func_name)
                # except Exception: pass is a swallow.
                elif (isinstance(handler.type, ast.Name)
                      and handler.type.id == "Exception"):
                    _assert_not_swallowing(handler, func_name)


def _assert_not_swallowing(
    handler: ast.ExceptHandler, func_name: str
) -> None:
    """Assert the handler does not silently swallow the exception."""
    # If the handler body is just `pass` or `return None`, it's swallowing.
    stmts = handler.body
    if len(stmts) == 1:
        stmt = stmts[0]
        if isinstance(stmt, ast.Pass):
            # A bare pass is a swallow unless it's in a context that
            # doesn't matter (like signal handler cleanup in close()).
            # For append-related methods, ANY pass is suspect.
            raise AssertionError(
                f"Method '{func_name}' contains 'except: pass' which "
                f"swallows all exceptions. This is forbidden in append paths."
            )
        if isinstance(stmt, ast.Return) and (
            stmt.value is None
            or (isinstance(stmt.value, ast.Constant) and stmt.value.value is None)
        ):
            raise AssertionError(
                f"Method '{func_name}' contains 'except: return None' which "
                f"swallows required-write persistence failures."
            )


def _assert_handler_re_raises(
    handler: ast.ExceptHandler, func_name: str
) -> None:
    """Assert the handler body contains a raise statement."""
    has_raise = False
    for stmt in ast.walk(handler):
        if isinstance(stmt, ast.Raise):
            has_raise = True
            break
    # Also check for a bare raise in the direct body (not nested in if/for).
    for stmt in handler.body:
        if isinstance(stmt, ast.Raise):
            has_raise = True
            break
    if not has_raise:
        raise AssertionError(
            f"Method '{func_name}' has an 'except Exception' handler that "
            f"does not re-raise. This could swallow persistence failures."
        )


# ── Test: No adapter path that skips sequence gaps ──────────────────────────

def test_adapter_no_sequence_gap_skip() -> None:
    """Assert that the adapter does not silently skip sequence gaps.

    The adapter must not contain logic that detects a gap and then
    proceeds without raising or recording it.  We check for:

    * Comments or strings that suggest gap-skipping ("skip gap", "ignore gap").
    * A ``query_gaps`` method that returns gaps but then the caller
      proceeds without action — this is checked via source patterns.
    """
    root = _project_root()
    adapter_path = root / "arnold/adapters/ledger_store_adapter.py"
    source = adapter_path.read_text(encoding="utf-8")

    # Pattern: comments suggesting gap skipping
    gap_skip_patterns = [
        r"skip\s+gap",
        r"ignore\s+gap",
        r"bypass\s+gap",
        r"tolerate\s+gap",
        r"gap.*ok(ay)?",
        r"proceed.*gap",
        r"continue.*despite.*gap",
    ]

    lines = source.split("\n")
    for i, line in enumerate(lines, start=1):
        # Only check comment lines and docstrings
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"') or stripped.startswith("'"):
            for pattern in gap_skip_patterns:
                if re.search(pattern, stripped, re.IGNORECASE):
                    raise AssertionError(
                        f"adapter line {i} contains gap-skipping language: "
                        f"{stripped!r}"
                    )

    # Also verify the adapter delegates query_gaps to the store without
    # filtering or suppressing the result.
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "query_gaps":
            # The method should delegate directly — no filtering logic.
            # Walk the body and check there's no loop that conditionally
            # drops gaps.
            for child in ast.walk(node):
                if isinstance(child, ast.If):
                    # An if inside query_gaps could be filtering.  Allow
                    # simple guard clauses (is_closed checks, etc.) but
                    # flag anything that looks like gap filtering.
                    _check_no_gap_filtering(child, "query_gaps")


def _check_no_gap_filtering(if_node: ast.If, func_name: str) -> None:
    """Check that an If node in *func_name* is not filtering gaps."""
    # Check if the condition references 'gap' or 'skip'.
    for child in ast.walk(if_node.test):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if "gap" in child.value.lower():
                raise AssertionError(
                    f"'{func_name}' contains a conditional on gap-related "
                    f"string: {child.value!r}"
                )
        if isinstance(child, ast.Name) and "gap" in child.id.lower():
            raise AssertionError(
                f"'{func_name}' contains a conditional on '{child.id}' "
                f"which suggests gap filtering."
            )


# ── Test: No production mutation import bypassing the store ──────────────────

def test_no_execution_attempt_ledger_import_bypass() -> None:
    """Assert that ``ExecutionAttemptLedger`` is only imported by approved modules.

    The ``ExecutionAttemptLedger`` class is a WBC schema definition.  It
    may be imported by:

    * ``arnold/workflow/__init__.py`` — re-exports schema types.
    * ``arnold/workflow/attempt_ledger_store.py`` — the store itself.
    * ``arnold/workflow/ledger_outbox.py`` — outbox ties to store.
    * ``arnold/workflow/ledger_trace.py`` — trace evidence.
    * ``arnold/adapters/ledger_store_adapter.py`` — official adapter.

    Any other production import is a bypass of the store boundary and must
    be rejected.
    """
    root = _project_root()
    violations: List[Tuple[str, str]] = []

    for py_file in _production_py_files():
        rel = str(py_file.relative_to(root))
        if rel in _APPROVED_EXECUTION_ATTEMPT_LEDGER_IMPORTERS:
            continue
        # Check for direct import of ExecutionAttemptLedger
        imports = _find_imports_from(
            py_file, "arnold.workflow.execution_attempt_ledger"
        )
        for name, _ in imports:
            if name == "ExecutionAttemptLedger":
                violations.append((rel, f"direct import of {name}"))

        # Also check for import via arnold.workflow (re-export)
        wf_imports = _find_imports_from(py_file, "arnold.workflow")
        for name, _ in wf_imports:
            if name == "ExecutionAttemptLedger":
                violations.append(
                    (rel, f"import of {name} via arnold.workflow re-export")
                )

    assert not violations, (
        f"ExecutionAttemptLedger imported outside approved WBC modules. "
        f"These imports bypass the store boundary: {violations}"
    )


def test_no_non_store_production_mutation_of_execution_attempt_ledger() -> None:
    """Assert that non-store production code does not construct or mutate
    ``ExecutionAttemptLedger`` instances.

    Only the store (``attempt_ledger_store.py``), the adapter
    (``ledger_store_adapter.py``), and the schema definition module itself
    (``execution_attempt_ledger.py``) may construct
    ``ExecutionAttemptLedger`` instances.

    Other modules may reference the type for type annotations or
    read-only purposes, but must not call its constructor.
    """
    root = _project_root()
    allowed_constructors = {
        "arnold/workflow/execution_attempt_ledger.py",  # schema definition
        "arnold/workflow/attempt_ledger_store.py",      # store reads back
        "arnold/adapters/ledger_store_adapter.py",       # adapter delegates
    }

    violations: List[Tuple[str, int, str]] = []

    for py_file in _production_py_files():
        rel = str(py_file.relative_to(root))
        if rel in allowed_constructors:
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        lines = source.split("\n")
        for i, line in enumerate(lines, start=1):
            # Look for ExecutionAttemptLedger(  — constructor call
            if re.search(r"\bExecutionAttemptLedger\s*\(", line):
                # Allow if it's in a comment or string
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if stripped.startswith('"') or stripped.startswith("'"):
                    continue
                # Allow if the line is inside a docstring (multi-line check
                # is too complex for simple regex; just flag it).
                violations.append((rel, i, line.strip()))

    assert not violations, (
        f"Non-store production modules construct ExecutionAttemptLedger "
        f"instances, bypassing the store boundary: {violations}"
    )


# ── Additional boundary guard: no store bypass via private imports ──────────

def test_no_store_bypass_via_private_import() -> None:
    """Assert that no production module imports store internals directly.

    Modules outside the WBC boundary must go through the adapter or the
    public API surface.  Direct imports of ``SqliteAttemptLedgerStore``
    or ``AttemptLedgerStore`` outside approved locations are forbidden.
    """
    root = _project_root()
    approved_store_importers = {
        "arnold/workflow/attempt_ledger_store.py",      # itself
        "arnold/workflow/ledger_outbox.py",             # outbox
        "arnold/workflow/ledger_migrations.py",          # migrations
        "arnold/workflow/ledger_payload_store.py",       # payload store
        "arnold/adapters/ledger_store_adapter.py",        # adapter
        "arnold/workflow/__init__.py",                    # (doesn't import store)
    }

    violations: List[Tuple[str, str]] = []

    for py_file in _production_py_files():
        rel = str(py_file.relative_to(root))
        if rel in approved_store_importers:
            continue
        imports = _find_imports_from(
            py_file, "arnold.workflow.attempt_ledger_store"
        )
        for name, _ in imports:
            if name in ("AttemptLedgerStore", "SqliteAttemptLedgerStore"):
                violations.append((rel, name))

    assert not violations, (
        f"Production modules import store classes directly instead of "
        f"going through the adapter boundary: {violations}"
    )
