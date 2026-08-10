"""Review policy package — parallel review runner, check registry, mechanical pre-checks.

This __init__ re-exports every name historically imported from the
pre-refactor top-level modules (``megaplan.parallel_review``,
``megaplan.review_checks``, ``megaplan.review_mechanical``) so that any
callers using ``from arnold_pipelines.megaplan.review import X`` keep working.
The canonical import paths are now plugin-local:
``arnold_pipelines.megaplan.review.parallel``,
``arnold_pipelines.megaplan.review.checks``, and
``arnold_pipelines.megaplan.review.mechanical``.
"""

from arnold_pipelines.megaplan.review.parallel import run_parallel_review
from arnold_pipelines.megaplan.review.checks import (
    REVIEW_CHECKS,
    ReviewCheckSpec,
    build_check_category_map,
    build_empty_template,
    checks_for_robustness,
    get_check_by_id,
    get_check_ids,
    validate_review_checks,
)
from arnold_pipelines.megaplan.review.mechanical import run_pre_checks

__all__ = [
    # parallel
    "run_parallel_review",
    # checks
    "REVIEW_CHECKS",
    "ReviewCheckSpec",
    "build_check_category_map",
    "build_empty_template",
    "checks_for_robustness",
    "get_check_by_id",
    "get_check_ids",
    "validate_review_checks",
    # mechanical
    "run_pre_checks",
]
