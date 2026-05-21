"""Re-export shim for relocated ``critique_joke`` prompt builders (T8).

Canonical module: ``megaplan.pipelines.creative.prompts.critique_joke``.

CRITICAL: ``single_check_critique_joke_prompt`` is a non-underscore
public symbol consumed at ``megaplan/orchestration/parallel_critique.py:21``
and ``tests/test_joke_mode_smoke.py:14``. Star-imports do NOT carry
non-underscore symbols consistently across Python versions; the
explicit ``__all__`` below MUST enumerate it.
"""

from __future__ import annotations

from megaplan.pipelines.creative.prompts.critique_joke import *  # noqa: F401,F403
from megaplan.pipelines.creative.prompts.critique_joke import (  # noqa: F401
    _critique_joke_prompt,
    single_check_critique_joke_prompt,
)

__all__ = [
    "_critique_joke_prompt",
    "single_check_critique_joke_prompt",
]
