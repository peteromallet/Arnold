"""Re-export shim for relocated ``execute_joke`` prompt builders (T8).

Canonical module: ``megaplan.pipelines.creative.prompts.execute_joke``.
"""

from __future__ import annotations

from megaplan.pipelines.creative.prompts.execute_joke import *  # noqa: F401,F403
from megaplan.pipelines.creative.prompts.execute_joke import (  # noqa: F401
    _execute_joke_batch_prompt,
    _execute_joke_prompt,
)

__all__ = [
    "_execute_joke_batch_prompt",
    "_execute_joke_prompt",
]
