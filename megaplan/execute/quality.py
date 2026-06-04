"""Thin facade for the canonical execute quality module."""

import sys

from arnold.pipelines.megaplan.execute import quality as _canonical

sys.modules[__name__] = _canonical
