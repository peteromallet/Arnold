# Rework tasklist — batch-2 attempt 1 (from GateB2 P2)
1. [normal] wire.py _splice_provider header regex misses `providers: &anchor` / `providers: {`
   -> duplicate providers: key appended, user content silently dropped under last-wins.
   Fix: if header line carries anything besides an optional comment (anchor/flow token),
   fall back to yaml.safe_load -> update -> yaml.safe_dump full rewrite (documented
   byte-preservation loss for that rare shape) instead of splicing. Regression tests for both shapes.
Acceptance: new tests green; existing merge/idempotence tests unchanged-green.
