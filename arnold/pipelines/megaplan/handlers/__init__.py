"""Handler bridge — re-exports Megaplan handler functions for stage consumption.

M4 places handler references under ``arnold/pipelines/megaplan/handlers/``
so that stage implementations can import handlers from the plugin-local
package rather than reaching into ``megaplan.handlers`` directly.

Each handler function is defined in ``megaplan.handlers`` and its internals
(prompts, state manipulation, profiles, control transitions) are deferred to
future milestones:

* **M5a** — prompt templates, state representations, and profile resolution
  move into the plugin.
* **M5b** — execute/review orchestration policy moves into the plugin.

Until those milestones land, these bridge modules provide stable re-exports
so stage files under ``arnold/pipelines/megaplan/stages/`` have a single,
plugin-local import surface.

Handlers re-exported (8):
    handle_prep, handle_plan, handle_critique, handle_gate, handle_revise,
    handle_finalize, handle_execute, handle_review
"""

from megaplan.handlers import (  # noqa: F401 — re-export for stage consumption
    handle_prep,
    handle_plan,
    handle_critique,
    handle_revise,
    handle_gate,
    handle_finalize,
    handle_execute,
    handle_review,
)

__all__ = [
    "handle_prep",
    "handle_plan",
    "handle_critique",
    "handle_revise",
    "handle_gate",
    "handle_finalize",
    "handle_execute",
    "handle_review",
]
