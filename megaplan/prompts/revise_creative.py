"""Re-export shim for relocated ``revise_creative`` prompt builder (T8).

Canonical module: ``megaplan.pipelines.creative.prompts.revise_creative``.

Intent policy marker: canonical implementation uses ``intent_brief_reference``.
"""

from __future__ import annotations

from megaplan.pipelines.creative.prompts.revise_creative import *  # noqa: F401,F403
from megaplan.pipelines.creative.prompts.revise_creative import (  # noqa: F401
    _revise_creative_prompt,
)

__all__ = ["_revise_creative_prompt"]
