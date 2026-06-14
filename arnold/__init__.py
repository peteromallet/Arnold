"""Arnold — neutral pipeline primitives extracted from Megaplan.

This package provides the pure-data, opinion-free type abstractions that
Megaplan's opinionated pipeline layer depends on.  No Megaplan-specific
logic, no CAS semantics, no gate recommendations — only the minimal shapes
that let Megaplan (and alternative runtimes) describe pipelines, stages,
steps, and state transitions.

Version is tracked here directly so that importing ``arnold`` never triggers
a ``megaplan`` import (the old ``from arnold.pipelines.megaplan import __version__`` created
a circular dependency after the rename).
"""

__version__ = "0.23.0"
