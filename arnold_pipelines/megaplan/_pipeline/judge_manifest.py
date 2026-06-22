"""Compatibility bridge for judge manifest primitives.

The canonical import-free implementation now lives in the neutral discovery
package; this module re-exports the same public surface so existing Megaplan
consumers keep working without import changes.
"""

from arnold.pipeline.discovery.judge_manifest import *  # noqa: F401,F403
from arnold.pipeline.discovery.judge_manifest import (  # noqa: F401
    JUDGE_KIND,
    JUDGE_MANIFEST_SCHEMA,
)
