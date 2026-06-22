"""Compatibility facade — delegates to arnold_pipelines.megaplan.routing.

M4: Megaplan planning decision literals and routing helpers have moved to
``arnold_pipelines.megaplan.routing``.  This module re-exports everything
from the canonical location so legacy importers (tests, scripts, downstream
packages) continue to work without changes.
"""

from arnold_pipelines.megaplan.routing import *  # noqa: F401, F403

# Re-export __all__ from the canonical location for IDEs and linters.
from arnold_pipelines.megaplan.routing import __all__ as __routing_all__  # noqa: F401

__all__ = list(__routing_all__)  # type: ignore[name-defined]
