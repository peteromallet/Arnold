"""Tiebreaker handler bridge — re-exports for the tiebreaker subpipeline.

M4: The tiebreaker run/decide pair used by ``TiebreakerStep`` and
``build_planning_steps()`` is re-exported here so stage implementations can
import from the plugin-local package.

Handler internals (prompt construction, state transitions, flag registry
interaction) are defined in ``megaplan.handlers.tiebreaker`` and deferred to:

* **M5a** — prompt templates and state representations move into the plugin.
* **M5b** — the tiebreaker orchestration policy (when to escalate vs iterate)
  moves into the plugin.

Until those milestones land, this bridge provides stable re-exports.

Handlers re-exported (2):
    handle_tiebreaker_run, handle_tiebreaker_decide
"""

from arnold.pipelines.megaplan.handlers._tiebreaker_impl import (  # noqa: F401 — re-export for stage consumption
    _build_tiebreaker_reprompt,
    handle_tiebreaker_run,
    handle_tiebreaker_decide,
)

__all__ = [
    "_build_tiebreaker_reprompt",
    "handle_tiebreaker_run",
    "handle_tiebreaker_decide",
]
