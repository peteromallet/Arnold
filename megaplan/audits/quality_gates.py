"""Compatibility facade for the canonical quality-gates module."""

from arnold.pipelines.megaplan.audits.quality_gates import *  # noqa: F401,F403
from arnold.pipelines.megaplan.audits.quality_gates import (
    _check_dead_imports,
    _check_duplicate_functions,
    _check_file_growth,
    _check_test_coverage,
)
