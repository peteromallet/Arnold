"""Thin facade for the canonical execute envelope module."""

import sys

from arnold.pipelines.megaplan.execute import _envelope as _canonical

sys.modules[__name__] = _canonical
