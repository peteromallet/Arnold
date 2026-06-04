"""Compatibility facade — delegates to arnold.pipelines.megaplan.operations.

M4: The planning operation registry adapter has moved to
``arnold.pipelines.megaplan.operations``.  This module re-exports everything
from the canonical location so legacy importers continue to work.
"""

from arnold.pipelines.megaplan.operations import *  # noqa: F401, F403

# Re-export __all__ from the canonical location for IDEs and linters.
from arnold.pipelines.megaplan.operations import __all__ as __ops_all__  # noqa: F401

__all__ = list(__ops_all__)  # type: ignore[name-defined]
