"""Orchestration helpers: evaluation, phase results, iteration pressure, etc.

This package groups orchestration-layer modules that the planning/execution
loop relies on. Submodules are imported lazily by their consumers; the
package ``__init__`` intentionally performs no eager imports to avoid
partial-import / circular-import drift when these helpers feed back into
``megaplan._core`` and ``megaplan.store``.
"""
