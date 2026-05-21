"""Re-export shim for relocated ``prep_joke`` prompt builder (T8).

Canonical module: ``megaplan.pipelines.creative.prompts.prep_joke``.
"""

from __future__ import annotations

from megaplan.pipelines.creative.prompts.prep_joke import *  # noqa: F401,F403
from megaplan.pipelines.creative.prompts.prep_joke import (  # noqa: F401
    _prep_joke_prompt,
)

__all__ = ["_prep_joke_prompt"]
