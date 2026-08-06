"""Execute binding package — tier selection and validation helpers.

This package owns the 1..10 complexity scale, the rubric reference,
and the ``select_batch_tier`` entry point.  It is deliberately
separated from the main ``megaplan.execute`` namespace so that
planning-aware logic does not leak into the core execution engine.
"""
