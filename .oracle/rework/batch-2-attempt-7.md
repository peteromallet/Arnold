# Batch 2 attempt 7 — converged Luna rework

Verdict: **REWORK REQUIRED** on the native/terminal roots; lifecycle is
accepted. Bound to attempt-6 brief SHA `e172c9b67fa1b55f2b164fb578ead173ff879151ca863bda96b07944d94cbd42` and the three Luna verdicts (native REWORK, lifecycle PASS, terminal REWORK). No additional Sol oracle was commissioned.

- Remove production caller route-liveness injection and use backend-owned
  authority at native and managed doors.
- Keep native proof family/catalog identities recomputed and update stale
  fixtures so stale proofs reach stale validation.
- Exercise actual native/OMP/managed doors with typed terminal categories and
  legacy compatibility where safe.
- Filter legacy ambiguous markers before ordered lifecycle reopen; retain them
  only as permanent-hold reconciliation evidence, and migrate stale fixtures
  to the canonical lifecycle prefix.

No frozen/status/execution-log/index changes, second WBC authority, or
Batch-3/provider/scheduler redesign.
