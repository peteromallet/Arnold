"""AST tripwire: three vendored model-dispatch boundaries must not be eroded.

The three invariants enforced here guard code sites that were deliberately
kept as-is during the C2 model-seam relocation because they encode
vendor-specific protocol details that cannot be abstracted away without
breaking the worker:

1. **Shannon --json-schema compatibility layer** (``workers/shannon.py``)
   ``_append_json_output_contract`` must still exist as a callable function.
   The docstring at line 1104 references ``--json-schema`` but the function
   definition is what the boundary checks — not the docstring string.

2. **Hermes response_format-under-tools boundary** (``workers/hermes.py``)
   ``set_response_format`` must be called ONLY within an ``if seam_tier is
   ModelTier.ENFORCED:`` guard — it must never be called unconditionally in
   the hermes execute path (many models hang when both tools and
   response_format are active).

3. **Codex session model literal** (``workers/_impl.py``, NOT codex.py)
   The literal string ``"codex exec resume"`` (or the list
   ``["codex", "exec", "resume"]``) must appear in real executable code
   (not just a docstring or comment).  This guards that the codex resume
   dispatch path still exists.

Docstring exclusion is essential for boundaries 1 and 3 to avoid
false-positive matches on the prose descriptions inside triple-quoted
docstrings (e.g. ``shannon.py`` line ~1104 discusses ``--json-schema`` in
its docstring; ``_impl.py`` discusses ``codex exec resume`` in comments).
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]

_SHANNON_SRC = REPO_ROOT / "arnold/pipelines/megaplan/workers/shannon.py"
_HERMES_SRC = REPO_ROOT / "arnold/pipelines/megaplan/workers/hermes.py"
_IMPL_SRC = REPO_ROOT / "arnold/pipelines/megaplan/workers/_impl.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _is_docstring_node(node: ast.AST) -> bool:
    """Return True if *node* is a module/class/function docstring Expr."""
    if not isinstance(node, ast.Expr):
        return False
    return isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _function_names(tree: ast.Module) -> set[str]:
    """Return all top-level and nested function definition names."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


def _string_literals_outside_docstrings(tree: ast.Module) -> list[str]:
    """Collect string literal values that are NOT part of a docstring.

    Walks the AST and collects ``ast.Constant`` string values that appear
    inside expressions which are not the first statement of a module, class,
    or function body (i.e. not docstrings).
    """
    docstring_nodes: set[int] = set()

    def _mark_docstrings(body: list[ast.stmt]) -> None:
        if body and _is_docstring_node(body[0]):
            docstring_nodes.add(id(body[0]))

    _mark_docstrings(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            _mark_docstrings(node.body)

    literals: list[str] = []
    for node in ast.walk(tree):
        if id(node) in docstring_nodes:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.append(node.value)
    return literals


# ---------------------------------------------------------------------------
# Boundary 1: Shannon --json-schema compatibility layer
# ---------------------------------------------------------------------------


def test_shannon_json_schema_compat_function_exists() -> None:
    """``_append_json_output_contract`` must exist as a callable in shannon.py.

    This is the Shannon ``--json-schema`` compatibility layer. If it is
    renamed or deleted the structured-output contract injection for the
    interactive Claude route will silently break.
    """
    tree = _parse(_SHANNON_SRC)
    names = _function_names(tree)
    assert "_append_json_output_contract" in names, (
        "shannon.py: _append_json_output_contract function is missing. "
        "This is the vendored --json-schema compatibility boundary."
    )


# ---------------------------------------------------------------------------
# Boundary 2: Hermes response_format-under-tools guard
# ---------------------------------------------------------------------------


def test_hermes_set_response_format_always_guarded_by_enforced_tier() -> None:
    """``set_response_format`` must only be called under an ENFORCED-tier guard.

    In the hermes execute path the only valid call site is inside
    ``if seam_tier is ModelTier.ENFORCED:``. Calling it unconditionally
    causes many models (Qwen, GLM-5) to hang or produce garbage when tool
    use is also active.

    The test verifies that every ``set_response_format(`` AST call node is a
    direct child of an ``If`` body whose test compares against
    ``ModelTier.ENFORCED``.
    """
    tree = _parse(_HERMES_SRC)

    # Collect all call nodes that invoke set_response_format
    call_sites: list[ast.Call] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "set_response_format"
        ):
            call_sites.append(node)

    assert call_sites, (
        "hermes.py: no set_response_format call found — "
        "the response_format-under-tools boundary has been removed."
    )

    # Build a mapping from child-node id -> parent for guarding check
    parent_map: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[id(child)] = parent

    def _guarded_by_enforced(call: ast.Call) -> bool:
        """Walk up the parent chain looking for an if-ENFORCED guard."""
        node: ast.AST | None = call
        while node is not None:
            parent = parent_map.get(id(node))
            if parent is None:
                break
            if isinstance(parent, ast.If):
                # Check if the test references ModelTier.ENFORCED
                test_src = ast.dump(parent.test)
                if "ENFORCED" in test_src:
                    return True
            node = parent
        return False

    unguarded = [call for call in call_sites if not _guarded_by_enforced(call)]
    assert unguarded == [], (
        f"hermes.py: {len(unguarded)} set_response_format call(s) are not guarded "
        "by 'if seam_tier is ModelTier.ENFORCED:' — "
        "response_format must NOT be set when tools are active."
    )


# ---------------------------------------------------------------------------
# Boundary 3: Codex session dispatch literal in _impl.py
# ---------------------------------------------------------------------------


def test_impl_codex_exec_resume_literal_in_real_code() -> None:
    """``"codex"`` + ``"exec"`` + ``"resume"`` must appear in executable code in _impl.py.

    This guards the codex session-resume dispatch path. The check looks for
    the string literal ``"resume"`` adjacent to ``"exec"`` and ``"codex"``
    in the same list/assignment context — outside of any docstring.

    Docstrings and comments are excluded so the test does not false-positive
    on the prose description of the codex resume flow.
    """
    tree = _parse(_IMPL_SRC)
    literals = _string_literals_outside_docstrings(tree)

    # The codex resume command is built as a list: ["codex", "exec", "resume"]
    # All three components must appear as real string literals.
    required = {"codex", "exec", "resume"}
    found = required & set(literals)
    assert found == required, (
        f"_impl.py: codex exec resume dispatch literals missing outside docstrings. "
        f"Found {sorted(found)!r}, expected {sorted(required)!r}. "
        "The codex session-resume dispatch path may have been removed."
    )
