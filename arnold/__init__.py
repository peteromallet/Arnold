"""Arnold — neutral pipeline primitives extracted from Megaplan.

This package provides the pure-data, opinion-free type abstractions that
Megaplan's opinionated pipeline layer depends on.  No Megaplan-specific
logic, no CAS semantics, no gate recommendations — only the minimal shapes
that let Megaplan (and alternative runtimes) describe pipelines, stages,
steps, and state transitions.

Version is inherited from the megaplan harness distribution so that the
whole monorepo moves in lockstep.
"""

from megaplan import __version__  # noqa: F401
