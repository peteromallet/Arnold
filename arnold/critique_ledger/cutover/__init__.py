"""Legacy-to-canonical cutover tooling package (CL5 Steps 11-20).

This package holds the net-new, side-effect-free cutover contract modules:

* :mod:`arnold.critique_ledger.cutover.config` — the frozen
  :class:`~arnold.critique_ledger.cutover.config.CutoverConfig` binding all
  required revisions and hashes, including the immutable North Star
  exact-runtime binding.
* :mod:`arnold.critique_ledger.cutover.drain_map` — the exhaustive
  drain-vs-indeterminate classification of every ``AttemptEventType``.

The later CL5 steps (quiesce, backup, restore, retirement, receipt, smoke,
completion) build their modules under this same package; the deferred
cutover orchestration entry point ``run_cutover`` (imported lazily by
``arnold_pipelines.megaplan.handlers.override``) is added in Phase 2+ and is
intentionally NOT defined here.
"""
