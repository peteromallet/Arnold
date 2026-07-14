"""Compatibility re-exports for historic ``arnold.pipelines.megaplan._pipeline.registry``."""

from arnold_pipelines.megaplan._pipeline.registry import *  # noqa: F401,F403

__all__ = [
    *[name for name in globals() if not name.startswith("__")],
]
