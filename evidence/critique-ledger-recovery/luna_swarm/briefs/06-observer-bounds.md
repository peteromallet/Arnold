# Luna audit 06 — bounded observer and notification behavior

Context: Read `evidence/critique-ledger-recovery/sol-broader-review-compact-brief-20260804.md` and Sol's verdict. Audit `/whats-cooking`, status snapshot generation, watchdog report parsing, stale/corrupt snapshot handling, notification deduplication, and timeout boundaries. Inspect resident/Discord observer code and tests. Do not edit. Return exact evidence, a bounded read-model design that never hides last-known state, and 3–6 acceptance tests covering timeout, corruption, stale data, and duplicate notifications. Under 900 words.
