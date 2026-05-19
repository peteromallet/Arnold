"""Structured object_info cache for per-class ComfyUI node schema lookups.

Built from a ComfyUI ``object_info`` JSON dump (e.g. a RunPod snapshot).
Provides deterministic per-pack cache files and a lazy consumer API.
"""

from vibecomfy.porting.object_info.consume import get_class, object_info_widget_order, output_names, list_classes
from vibecomfy.porting.object_info.serialize import (
    build_cache,
    CACHE_DIR,
    INDEX_PATH,
)

__all__ = [
    "get_class",
    "object_info_widget_order",
    "output_names",
    "list_classes",
    "build_cache",
    "CACHE_DIR",
    "INDEX_PATH",
]
