"""Thin facade for the canonical execute batch module."""

import sys

from arnold.pipelines.megaplan.execute import batch as _canonical

sys.modules[__name__] = _canonical
