"""Re-export shim for relocated ``execute_doc`` prompt builders (T5).

The canonical module now lives at
``megaplan.pipelines.doc.prompts.execute_doc``. This shim preserves the
historical ``megaplan.prompts.execute_doc`` import path used by the
legacy planning + mode-overlay ``--auto-start`` path and by the
``megaplan.prompts.__init__`` re-export aggregator.

The explicit ``__all__`` enumerates every public symbol the Step 1.4
grep inventory found — star-imports alone do not carry non-underscore
symbols consistently across Python versions.
"""

from __future__ import annotations

from megaplan.pipelines.doc.prompts.execute_doc import *  # noqa: F401,F403
from megaplan.pipelines.doc.prompts.execute_doc import (  # noqa: F401
    _execute_doc_batch_prompt,
    _execute_doc_prompt,
)

__all__ = [
    "_execute_doc_batch_prompt",
    "_execute_doc_prompt",
]
