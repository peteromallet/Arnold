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
# Each entry is  (relative_file, line_number, key).
# These are the *only* routing-owned state writes permitted in handlers.
# When a handler no longer needs a write, remove its entry — do not leave
# stale entries that would mask a regression.
_INVENTORIED_HANDLER_WRITES: set[tuple[str, int, str]] = {
    # _tiebreaker_impl.py
    ("arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py", 61, "current_state"),
    ("arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py", 132, "current_state"),
    ("arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py", 135, "current_state"),
    ("arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py", 139, "current_state"),
    # critique.py
    ("arnold_pipelines/megaplan/handlers/critique.py", 874, "current_state"),
    ("arnold_pipelines/megaplan/handlers/critique.py", 1215, "current_state"),
    ("arnold_pipelines/megaplan/handlers/critique.py", 1223, "current_state"),
    ("arnold_pipelines/megaplan/handlers/critique.py", 1237, "current_state"),
    ("arnold_pipelines/megaplan/handlers/critique.py", 1247, "current_state"),
    ("arnold_pipelines/megaplan/handlers/critique.py", 1264, "current_state"),
    ("arnold_pipelines/megaplan/handlers/critique.py", 1283, "current_state"),
    ("arnold_pipelines/megaplan/handlers/critique.py", 1285, "current_state"),
    ("arnold_pipelines/megaplan/handlers/critique.py", 1289, "current_state"),
    # execute.py
    ("arnold_pipelines/megaplan/handlers/execute.py", 260, "current_state"),
    ("arnold_pipelines/megaplan/handlers/execute.py", 318, "current_state"),
    # finalize.py
    ("arnold_pipelines/megaplan/handlers/finalize.py", 1507, "current_state"),
    ("arnold_pipelines/megaplan/handlers/finalize.py", 1753, "current_state"),
    # gate.py
    ("arnold_pipelines/megaplan/handlers/gate.py", 490, "current_state"),
    ("arnold_pipelines/megaplan/handlers/gate.py", 506, "current_state"),
    ("arnold_pipelines/megaplan/handlers/gate.py", 599, "current_state"),
    ("arnold_pipelines/megaplan/handlers/gate.py", 612, "current_state"),
    ("arnold_pipelines/megaplan/handlers/gate.py", 621, "current_state"),
    # override.py
    ("arnold_pipelines/megaplan/handlers/override.py", 674, "current_state"),
    ("arnold_pipelines/megaplan/handlers/override.py", 810, "current_state"),
    ("arnold_pipelines/megaplan/handlers/override.py", 921, "current_state"),
    ("arnold_pipelines/megaplan/handlers/override.py", 997, "current_state"),
    ("arnold_pipelines/megaplan/handlers/override.py", 1041, "current_state"),
    ("arnold_pipelines/megaplan/handlers/override.py", 1277, "current_state"),
    ("arnold_pipelines/megaplan/handlers/override.py", 1799, "current_state"),
    # plan.py
    ("arnold_pipelines/megaplan/handlers/plan.py", 241, "current_state"),
    ("arnold_pipelines/megaplan/handlers/plan.py", 276, "current_state"),
    # review.py
    ("arnold_pipelines/megaplan/handlers/review.py", 1127, "current_state"),
    ("arnold_pipelines/megaplan/handlers/review.py", 1194, "current_state"),
    # verifiability.py
    ("arnold_pipelines/megaplan/handlers/verifiability.py", 283, "current_state"),
}

# Tuple-unpack writes where one of the unpacked targets is a routing-owned key.
# These don't show up as simple `state["key"] =` AST nodes but the test still
# needs to allow them.
_INVENTORIED_UNPACK_WRITES: set[tuple[str, int, str]] = {
    ("arnold_pipelines/megaplan/handlers/critique.py", 1163, "current_state"),
    ("arnold_pipelines/megaplan/handlers/plan.py", 195, "current_state"),
}


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

        rel = str(source.relative_to(root.parent.parent))

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


# ── tests ──────────────────────────────────────────────────────────────────

class TestRoutingSourceInvariants:
    """Source-invariant scans for routing-shaped handler mutations."""

    def test_all_handler_routing_writes_are_inventoried(self) -> None:
        """Every handler write to a routing-owned state key must be in the inventory."""
        simple, unpack = _collect_routing_writes(
            HANDLERS_DIR, rel_prefix="arnold_pipelines/megaplan/handlers"
        )

        simple_set = set(simple)
        unpack_set = set(unpack)

        uninventoried_simple = simple_set - _INVENTORIED_HANDLER_WRITES
        uninventoried_unpack = unpack_set - _INVENTORIED_UNPACK_WRITES

        uninventoried: list[str] = []
        for rel, lineno, key in sorted(uninventoried_simple):
            uninventoried.append(
                f"  {rel}:{lineno}  state[\"{key}\"] = ... (new simple write)"
            )
        for rel, lineno, key in sorted(uninventoried_unpack):
            uninventoried.append(
                f"  {rel}:{lineno}  state[\"{key}\"] = ... (new unpack write)"
            )

        assert not uninventoried, (
            "New uninventoried routing-owned state writes detected. "
            "If these are audited compatibility bookkeeping, add them to "
            "_INVENTORIED_HANDLER_WRITES or _INVENTORIED_UNPACK_WRITES.\n"
            + "\n".join(uninventoried)
        )

    def test_no_stale_inventory_entries(self) -> None:
        """Every inventory entry must match an actual source write."""
        simple, unpack = _collect_routing_writes(
            HANDLERS_DIR, rel_prefix="arnold_pipelines/megaplan/handlers"
        )

        simple_set = set(simple)
        unpack_set = set(unpack)

        stale_simple = _INVENTORIED_HANDLER_WRITES - simple_set
        stale_unpack = _INVENTORIED_UNPACK_WRITES - unpack_set

        stale: list[str] = []
        for rel, lineno, key in sorted(stale_simple):
            stale.append(
                f"  {rel}:{lineno}  state[\"{key}\"] = ... (stale simple entry)"
            )
        for rel, lineno, key in sorted(stale_unpack):
            stale.append(
                f"  {rel}:{lineno}  state[\"{key}\"] = ... (stale unpack entry)"
            )

        assert not stale, (
            "Stale inventory entries found — the code no longer contains these writes. "
            "Remove them from _INVENTORIED_HANDLER_WRITES or _INVENTORIED_UNPACK_WRITES.\n"
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
            "megaplan",
            "Megaplan",
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
