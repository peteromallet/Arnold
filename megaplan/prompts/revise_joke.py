"""Re-export shim for relocated ``revise_joke`` prompt builder (T8).

Canonical module: ``megaplan.pipelines.creative.prompts.revise_joke``.
"""

from __future__ import annotations

from megaplan.pipelines.creative.prompts.revise_joke import *  # noqa: F401,F403
from megaplan.pipelines.creative.prompts.revise_joke import (  # noqa: F401
    _revise_joke_prompt,
)

__all__ = ["_revise_joke_prompt"]
