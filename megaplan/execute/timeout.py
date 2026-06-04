"""Thin facade for the canonical execute timeout module."""

import sys

from arnold.pipelines.megaplan.execute import timeout as _canonical

sys.modules[__name__] = _canonical
