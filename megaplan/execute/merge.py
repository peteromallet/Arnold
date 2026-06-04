"""Thin facade for the canonical execute merge module."""

import sys

from arnold.pipelines.megaplan.execute import merge as _canonical

sys.modules[__name__] = _canonical
