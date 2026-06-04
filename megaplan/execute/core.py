"""Thin facade for the canonical execute core module."""

import sys

from arnold.pipelines.megaplan.execute import core as _canonical

sys.modules[__name__] = _canonical
