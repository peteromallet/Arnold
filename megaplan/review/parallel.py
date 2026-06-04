"""Thin facade — canonical implementation is arnold.pipelines.megaplan.review.parallel.

This facade aliases the canonical module via sys.modules so that
monkeypatching ``megaplan.review.parallel._resolve_model`` (and other
module-level names) affects the canonical implementation directly.
"""
import sys
from arnold.pipelines.megaplan.review import parallel as _canonical

sys.modules[__name__] = _canonical
