"""Orchestration policy package — phase-result transport, progress emission,
evaluation, gate signals, completion contracts, iteration pressure,
recovery policy, and tiebreaker support.

Canonical home for orchestration policy modules moved from ``megaplan/orchestration/``
during M5b.  This package uses direct ``arnold_pipelines.megaplan.<domain>.*``
imports (SD2).  Old ``megaplan.orchestration.*`` paths are thin compatibility
facades that re-export from here.
"""

# Modules present (add as they land):
#   phase_result, phase_result_classify, recovery_policy, progress  (T4)
#   gate_checks, gate_signals, execution_evidence, rubber_stamp,
#   plan_structure, iteration_pressure, critique_status            (T5)
#   verifiability, feedback, parallel_critique, prep_research,
#   tiebreaker                                                    (T7)
