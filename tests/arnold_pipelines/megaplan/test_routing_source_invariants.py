"""Source-invariant scans for routing-shaped handler state mutations.

These tests encode the SD1 settled decision: handler writes to routing-owned
state keys are inventoried as audited compatibility bookkeeping, not removed
wholesale.  A new uninventoried write to a routing-owned key must fail,
preventing hidden routing authority from creeping in without review.

The companion ``test_import_boundaries.py`` verifies that the native
pipeline modules never import Megaplan-specific product semantics.
"""

from __future__ import annotations

import ast
from pathlib import Path

# ── routing-owned state keys (mirrors validator._ROUTING_OWNED_STATE_KEYS) ──
_ROUTING_OWNED_STATE_KEYS = frozenset(
    {
        "__control_override__",
        "__override_route__",
        "branch",
        "branches",
        "current_state",
        "decision",
        "next_stage",
        "next_step",
        "override_action",
        "override_route",
        "route",
        "routes",
        "workflow_transition",
    }
)

REPO_ROOT = Path(__file__).parents[3]
HANDLERS_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "handlers"
NATIVE_DIR = REPO_ROOT / "arnold" / "pipeline" / "native"

# ── audited compatibility inventory ──────────────────────────────────────
# Each entry is  (relative_file, key, expected_count).
# These are the *only* routing-owned state writes permitted in handlers.
# When a handler no longer needs a write, remove its entry — do not leave
# stale entries that would mask a regression.
_INVENTORIED_HANDLER_WRITE_COUNTS: dict[tuple[str, str], int] = {
    # execute.py
    ("arnold_pipelines/megaplan/handlers/execute.py", "current_state"): 2,
    # finalize.py
    ("arnold_pipelines/megaplan/handlers/finalize.py", "current_state"): 2,
    # gate.py
    ("arnold_pipelines/megaplan/handlers/gate.py", "current_state"): 5,
    # override.py
    ("arnold_pipelines/megaplan/handlers/override.py", "current_state"): 7,
    # plan.py
    ("arnold_pipelines/megaplan/handlers/plan.py", "current_state"): 2,
    # review.py
    ("arnold_pipelines/megaplan/handlers/review.py", "current_state"): 2,
    # verifiability.py
    ("arnold_pipelines/megaplan/handlers/verifiability.py", "current_state"): 1,
}

# Tuple-unpack writes where one of the unpacked targets is a routing-owned key.
# These don't show up as simple `state["key"] =` AST nodes but the test still
# needs to allow them.
_INVENTORIED_UNPACK_WRITE_COUNTS: dict[tuple[str, str], int] = {}


# ── helpers ───────────────────────────────────────────────────────────────

def _collect_routing_writes(
    root: Path, *, rel_prefix: str
) -> tuple[list[tuple[str, int, str]], list[tuple[str, int, str]]]:
    """Scan *root* for ``state[<routing_key>] = ...`` patterns.

    Returns ``(simple_writes, unpack_writes)`` where each element is
    ``(relative_path, line_number, key)``.
    """
    simple: list[tuple[str, int, str]] = []
    unpack: list[tuple[str, int, str]] = []

    for source in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue

        rel = f"{rel_prefix}/{source.relative_to(root).as_posix()}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Detect tuple-unpack: state["iteration"], state["current_state"] = ...
                routing_targets = [
                    t for t in node.targets
                    if _is_routing_subscript(t)
                ]
                if len(routing_targets) > 1 or (
                    len(routing_targets) == 1 and len(node.targets) > 1
                ):
                    for t in routing_targets:
                        key = _subscript_key(t)
                        if key is not None:
                            unpack.append((rel, node.lineno, key))
                    continue

                for target in node.targets:
                    key = _routing_state_key(target)
                    if key is not None:
                        simple.append((rel, node.lineno, key))

            elif isinstance(node, ast.AugAssign):
                key = _routing_state_key(node.target)
                if key is not None:
                    simple.append((rel, node.lineno, key))

    return simple, unpack


def _routing_state_key(target: ast.expr) -> str | None:
    """Return the key name if *target* is ``state[<routing_key>]``."""
    if not isinstance(target, ast.Subscript):
        return None
    return _subscript_key(target)


def _is_routing_subscript(target: ast.expr) -> bool:
    """Check if *target* is ``state[<any_key>]`` (used for unpack detection)."""
    if not isinstance(target, ast.Subscript):
        return False
    if not isinstance(target.value, ast.Name):
        return False
    if target.value.id != "state":
        return False
    return isinstance(target.slice, ast.Constant) and isinstance(target.slice.value, str)


def _subscript_key(sub: ast.Subscript) -> str | None:
    """Extract key from ``state[<key>]`` if the key is a routing-owned key."""
    if not isinstance(sub.value, ast.Name) or sub.value.id != "state":
        return None
    if not isinstance(sub.slice, ast.Constant) or not isinstance(sub.slice.value, str):
        return None
    key = sub.slice.value
    if key in _ROUTING_OWNED_STATE_KEYS:
        return key
    return None


def _write_counts(
    writes: list[tuple[str, int, str]],
) -> dict[tuple[str, str], list[int]]:
    counts: dict[tuple[str, str], list[int]] = {}
    for rel, lineno, key in writes:
        counts.setdefault((rel, key), []).append(lineno)
    return counts


# ── tests ──────────────────────────────────────────────────────────────────

class TestRoutingSourceInvariants:
    """Source-invariant scans for routing-shaped handler mutations."""

    def test_all_handler_routing_writes_are_inventoried(self) -> None:
        """Every handler write to a routing-owned state key must be in the inventory."""
        simple, unpack = _collect_routing_writes(
            HANDLERS_DIR, rel_prefix="arnold_pipelines/megaplan/handlers"
        )

        simple_counts = _write_counts(simple)
        unpack_counts = _write_counts(unpack)

        uninventoried: list[str] = []
        for (rel, key), lines in sorted(simple_counts.items()):
            expected = _INVENTORIED_HANDLER_WRITE_COUNTS.get((rel, key), 0)
            if len(lines) > expected:
                uninventoried.append(
                    f"  {rel} state[\"{key}\"] count {len(lines)} > inventoried {expected}; lines={sorted(lines)}"
                )
        for (rel, key), lines in sorted(unpack_counts.items()):
            expected = _INVENTORIED_UNPACK_WRITE_COUNTS.get((rel, key), 0)
            if len(lines) > expected:
                uninventoried.append(
                    f"  {rel} state[\"{key}\"] unpack count {len(lines)} > inventoried {expected}; lines={sorted(lines)}"
                )

        assert not uninventoried, (
            "New uninventoried routing-owned state writes detected. "
            "If these are audited compatibility bookkeeping, add them to "
            "_INVENTORIED_HANDLER_WRITE_COUNTS or _INVENTORIED_UNPACK_WRITE_COUNTS.\n"
            + "\n".join(uninventoried)
        )

    def test_no_stale_inventory_entries(self) -> None:
        """Every inventory entry must match an actual source write."""
        simple, unpack = _collect_routing_writes(
            HANDLERS_DIR, rel_prefix="arnold_pipelines/megaplan/handlers"
        )

        simple_counts = _write_counts(simple)
        unpack_counts = _write_counts(unpack)

        stale: list[str] = []
        for (rel, key), expected in sorted(_INVENTORIED_HANDLER_WRITE_COUNTS.items()):
            actual = len(simple_counts.get((rel, key), []))
            if actual < expected:
                stale.append(
                    f"  {rel} state[\"{key}\"] count {actual} < inventoried {expected}; lines={sorted(simple_counts.get((rel, key), []))}"
                )
        for (rel, key), expected in sorted(_INVENTORIED_UNPACK_WRITE_COUNTS.items()):
            actual = len(unpack_counts.get((rel, key), []))
            if actual < expected:
                stale.append(
                    f"  {rel} state[\"{key}\"] unpack count {actual} < inventoried {expected}; lines={sorted(unpack_counts.get((rel, key), []))}"
                )

        assert not stale, (
            "Stale inventory entries found — the code no longer contains these writes. "
            "Remove them from _INVENTORIED_HANDLER_WRITE_COUNTS or _INVENTORIED_UNPACK_WRITE_COUNTS.\n"
            + "\n".join(stale)
        )

    def test_no_native_module_imports_megaplan_product_semantics(self) -> None:
        """Native pipeline modules must not import megaplan-specific packages."""
        banned_prefixes = (
            "arnold_pipelines.megaplan",
        )
        violations: dict[str, list[str]] = {}

        for source in sorted(NATIVE_DIR.rglob("*.py")):
            rel = str(source.relative_to(NATIVE_DIR.parent.parent))
            try:
                tree = ast.parse(source.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue

            bad: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "arnold_pipelines.megaplan" or alias.name.startswith(
                            "arnold_pipelines.megaplan."
                        ):
                            bad.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and (
                        node.module == "arnold_pipelines.megaplan"
                        or node.module.startswith("arnold_pipelines.megaplan.")
                    ):
                        bad.append(node.module)
            if bad:
                violations[rel] = bad

        assert violations == {}, (
            "Native pipeline modules import Megaplan-specific product semantics:\n"
            + "\n".join(
                f"  {rel}: {', '.join(mods)}" for rel, mods in sorted(violations.items())
            )
        )

    def test_no_native_module_embeds_megaplan_vocabulary(self) -> None:
        """Native pipeline modules must not embed Megaplan-specific DSL vocabulary.

        Checks for string literals that reference Megaplan product concepts
        (step names, route labels, artifact stages, etc.) that would couple
        the native validator to a specific product.
        """
        # These are Megaplan-specific DSL concepts that should not appear as
        # string literals in product-neutral native code.
        megaplan_vocabulary_patterns = (
            "arnold_pipelines.megaplan",
            "arnold.pipelines.megaplan",
            "megaplan/",
            ".megaplan/",
        )

        violations: dict[str, list[tuple[int, str]]] = {}

        for source in sorted(NATIVE_DIR.rglob("*.py")):
            rel = str(source.relative_to(NATIVE_DIR.parent.parent))
            try:
                tree = ast.parse(source.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue

            found: list[tuple[int, str]] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    for pattern in megaplan_vocabulary_patterns:
                        if pattern in node.value:
                            found.append((node.lineno, node.value[:120]))
                            break
            if found:
                violations[rel] = found

        # The compatibility.py in megaplan package may embed megaplan references
        # but native pipeline modules must stay product-neutral.
        assert violations == {}, (
            "Native pipeline modules contain Megaplan-specific vocabulary:\n"
            + "\n".join(
                f"  {rel}:{lineno}: {text}"
                for rel, items in sorted(violations.items())
                for lineno, text in items
            )
        )
