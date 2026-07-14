"""Compatibility re-exports for historic ``_pipeline.executor`` imports."""

from arnold_pipelines.megaplan.runtime.executor import *  # noqa: F401,F403

__all__ = [
    *[name for name in globals() if not name.startswith("__")],
]
