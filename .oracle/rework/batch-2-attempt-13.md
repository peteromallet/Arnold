# Batch 2 attempt 13 — final physical-door verification

Verdict: **REWORK REQUIRED**. Bound to the Batch 2 attempt-12 brief SHA
`9a8aea5662d8a3222248250b90cf3ab57b2bc6e07a58f256ca7165f4c502baee` and the
three independent reviews (native REWORK, OMP PASS with environment note,
managed PASS), including parallel writer results; no additional Sol oracle
was commissioned.

- Verify native typed terminals remain carried through the legacy tuple to
  handlers; unresolved outcomes carry both valid scheduling condition and
  dispatch outcome without failure accounting.
- Verify OMP disposition and unresolved append/link behavior without relaunch.
- Verify managed integer compatibility and canonical terminal observability.
- Run the three physical-door files and focused Batch2 chunks through
  `python -m pytest`, recording the `omp_rpc` collection blocker and baseline
  failures precisely.

No frozen/status/execution-log/index changes, commit, push, merge, deploy, or
scope expansion.
