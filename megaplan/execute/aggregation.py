"""Thin facade for the canonical execute aggregation module."""

import sys

from arnold.pipelines.megaplan.execute import aggregation as _canonical

sys.modules[__name__] = _canonical
