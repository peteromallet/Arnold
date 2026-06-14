"""Characterization test for the patterns module import surface and node registry.

Asserts that every public name declared in ``megaplan._pipeline.patterns.__all__``
is (a) importable from the module, (b) present in ``_NODE_REGISTRY``, and (c) the
registry covers the full public surface with no gaps.
"""

from __future__ import annotations


def test_every_all_name_importable() -> None:
    """Every symbol in patterns.__all__ resolves via getattr on the module."""
    from arnold.pipelines.megaplan._pipeline import patterns

    missing: list[str] = []
    for name in patterns.__all__:
        try:
            getattr(patterns, name)
        except AttributeError:
            missing.append(name)

    assert not missing, (
        f"patterns.__all__ names not importable:\n  "
        + "\n  ".join(missing)
    )


def test_every_all_name_in_node_registry() -> None:
    """Every symbol in patterns.__all__ has a corresponding _NODE_REGISTRY entry."""
    from arnold.pipelines.megaplan._pipeline import patterns

    registry_keys = set(patterns._NODE_REGISTRY)
    missing = [n for n in patterns.__all__ if n not in registry_keys]

    assert not missing, (
        f"patterns.__all__ names not in _NODE_REGISTRY:\n  "
        + "\n  ".join(missing)
    )


def test_node_registry_covers_no_unexpected_entries() -> None:
    """set(__all__) - set(_NODE_REGISTRY) is empty (registry has no extra keys)."""
    from arnold.pipelines.megaplan._pipeline import patterns

    all_set = set(patterns.__all__)
    registry_set = set(patterns._NODE_REGISTRY)
    delta = all_set - registry_set

    assert not delta, (
        f"patterns.__all__ contains names not in _NODE_REGISTRY:\n  "
        + "\n  ".join(sorted(delta))
    )
