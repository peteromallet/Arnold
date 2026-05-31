# Known gaps — M5b carried

## M5b: cheap-finalize profiles may dispatch tasks to a rater whose tier is lower than the dispatchee's adjudicated complexity tier

**Status:** Carried from M5b (F4 complexity-tiering → F5 task-DAG scheduler).  
**To be closed by:** M5-cal (the Calibration Ledger milestone).

**Gap description:**

When `handle_execute_one_batch` resolves the per-batch tier via `select_batch_tier` /
`compute_batch_complexity`, the tier map (`tier_models['execute']`) is sourced from
the planning profile's `tier_models`.  In a *cheap-finalize* profile (one that
declares a flat or ratio-limited tier map), it is possible for a batch whose
adjudicated complexity tier is *N* to be dispatched to a rater whose own tier is
*< N*.  This weakens the **rater ≥ dispatchee** invariant that the complexity
rubric assumes: a tier-3 batch routed to a tier-2 model may produce sub-standard
execution without the system detecting that the invariant was violated.

Once M5-cal lands, `tier_models` becomes a projection of the Calibration Ledger
and the invariant can be enforced at dispatch time by rejecting tier maps that
would violate it.  Until then, the gap is acknowledged and carried.
