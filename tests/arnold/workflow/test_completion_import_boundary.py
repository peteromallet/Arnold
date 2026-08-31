"""Import boundary and hash-determinism tests for the completion package.

This module verifies that:
1. ``arnold.workflow.completion`` and its submodules do not transitively import
   ``arnold_pipelines.megaplan`` or other forbidden product modules (neutral
   package invariant).
2. :func:`~arnold.workflow.completion.hashing.hash_canonical` matches the
   exact algorithm and output format of
   ``arnold_pipelines.megaplan.orchestration.acceptance_transaction._sha256_hex``
   for identical input (``sha256:`` prefix + 64 hex digits).
3. :func:`~arnold.workflow.completion.hashing.content_addressed_store_path`
   produces correct sharded paths.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from arnold.workflow.completion.hashing import (
    canonical_json,
    content_addressed_store_path,
    hash_canonical,
)

# ---------------------------------------------------------------------------
# Forbidden module prefixes (mirrors arnold.workflow.validation.FORBIDDEN_PRODUCT_IMPORTS)
# ---------------------------------------------------------------------------

FORBIDDEN_PREFIXES = (
    "arnold.pipelines.megaplan",
    # Reject the package root too: ``from arnold_pipelines import ...``
    # otherwise evades a check limited to its ``megaplan`` child.
    "arnold_pipelines",
    "arnold_pipelines.megaplan",
    "megaplan",
)

# ---------------------------------------------------------------------------
# Import boundary — transitive dependency check
# ---------------------------------------------------------------------------


def _is_forbidden_module(name: str) -> bool:
    return any(
        name == prefix or name.startswith(prefix + ".")
        for prefix in FORBIDDEN_PREFIXES
    )


def _literal_import_targets(tree: ast.AST) -> list[tuple[int, str]]:
    """Return every direct or literal dynamic import target in *tree*."""
    targets: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets.append((node.lineno, node.module))
        elif isinstance(node, ast.Call) and node.args:
            is_dynamic_import = (
                isinstance(node.func, ast.Name)
                and node.func.id == "__import__"
            ) or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
            )
            if (
                is_dynamic_import
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                targets.append((node.lineno, node.args[0].value))
    return targets


def test_completion_sources_do_not_import_forbidden_modules() -> None:
    """Source-level boundary check cannot be hidden by a preloaded package.

    This deliberately inspects every neutral completion module instead of
    looking at ``sys.modules`` after imports.  It therefore fails even when a
    forbidden import is added to ``__init__.py`` or a submodule already loaded
    during test collection.
    """
    package_dir = Path(__file__).parents[3] / "arnold" / "workflow" / "completion"
    violations: list[str] = []
    for source_file in sorted(package_dir.rglob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        for line, target in _literal_import_targets(tree):
            if _is_forbidden_module(target):
                violations.append(f"{source_file.relative_to(package_dir)}:{line}: {target}")

    assert not violations, "neutral completion import boundary violated:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# Hash format — sha256: prefix + 64 hex digits
# ---------------------------------------------------------------------------


def test_hash_canonical_format() -> None:
    """``hash_canonical`` output must start with ``sha256:`` and contain a hex digest."""
    digest = hash_canonical({"hello": "world"})
    assert digest.startswith("sha256:"), f"Missing sha256: prefix: {digest!r}"
    hex_part = digest[len("sha256:"):]
    assert len(hex_part) == 64, f"Expected 64 hex chars, got {len(hex_part)}: {hex_part!r}"
    int(hex_part, 16)  # raises ValueError if not valid hex


def test_hash_canonical_determinism() -> None:
    """Identical input must produce identical output across calls."""
    obj = {"z": 1, "a": [1, 2, 3], "nested": {"b": True, "c": None}}
    assert hash_canonical(obj) == hash_canonical(obj)


def test_hash_canonical_order_independence() -> None:
    """Canonical JSON sorts keys, so dict key insertion order must not affect the hash."""
    a = hash_canonical({"a": 1, "b": 2})
    b = hash_canonical({"b": 2, "a": 1})
    assert a == b, "Key ordering changed the hash"


# ---------------------------------------------------------------------------
# Hash equivalence — compare against acceptance_transaction algorithm
# ---------------------------------------------------------------------------


def test_hash_canonical_matches_acceptance_transaction() -> None:
    """``hash_canonical`` must produce the same output as ``acceptance_transaction``'s
    internal helpers for the same input (prefixed-to-prefixed comparison)."""
    from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
        _canonical_json_bytes,
        _sha256_hex,
    )

    test_objects = [
        {"hello": "world"},
        {"z": 1, "a": [1, 2, 3], "nested": {"b": True, "c": None}},
        {"empty": {}, "null": None, "bool": True},
        {"list": [1, 2, 3]},
        {},
    ]

    for obj in test_objects:
        expected_bytes = _canonical_json_bytes(obj)
        actual_bytes = canonical_json(obj)
        assert actual_bytes == expected_bytes, (
            f"canonical_json bytes differ for {obj!r}\n"
            f"  actual:   {actual_bytes!r}\n"
            f"  expected: {expected_bytes!r}"
        )

        expected_digest = _sha256_hex(expected_bytes)
        actual_digest = hash_canonical(obj)
        assert actual_digest == expected_digest, (
            f"hash_canonical differs for {obj!r}\n"
            f"  actual:   {actual_digest!r}\n"
            f"  expected: {expected_digest!r}"
        )


# ---------------------------------------------------------------------------
# content_addressed_store_path
# ---------------------------------------------------------------------------


def test_content_addressed_store_path() -> None:
    """Correct sharding and prefix stripping."""
    digest = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    path = content_addressed_store_path("/tmp/store", digest)
    assert path == Path("/tmp/store/e3/e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")


def test_content_addressed_store_path_rejects_bad_prefix() -> None:
    """Raises ValueError when digest does not start with ``sha256:``."""
    with pytest.raises(ValueError, match="sha256:"):
        content_addressed_store_path("/tmp", "md5:abc123")
