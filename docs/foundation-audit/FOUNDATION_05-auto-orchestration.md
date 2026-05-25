First read `FOUNDATION_PREAMBLE.md` (shared context + output rules). Obey it.

## YOUR SUBSYSTEM: `auto.py` — the orchestration driver (the brief's most-undersized item)

The brief: `auto.py` is ~1846 LOC with ZERO direct tests; its subprocess boundary is ALSO the
isolation boundary (per-phase timeouts, stall/idle detection, context-exhaustion `--fresh` retry,
blocked-task retries, ESCALATE→force-proceed). Body 2 step 6 ports it in-process (~600 LOC). This
is the riskiest single item — characterize what's actually in there.

Investigate (cite path:line):
- Read `auto.py` thoroughly. Catalog every responsibility: phase selection (`megaplan status` →
  `next_step`/`valid_next`, ~158-183), the subprocess spawn/timeout/kill machinery (recent commits
  mention subprocess-group isolation + killing grandchildren — find that), stall/idle detection,
  context-exhaustion retry, blocked-task retry loops, ESCALATE policy, the auto_approve injection
  (~316-335), the success-synthesis fallback (~763-771), `DriverOutcome`/`--outcome-file`.
- What of this is genuinely coupled to the *subprocess* model (process isolation, signals, OS
  timeouts) and therefore CANNOT be trivially reimplemented in-process? This is the crux: which
  robustness properties are accidental gifts of "it's a separate process"?
- What hidden state does auto keep across iterations (in-memory vs re-read from disk each loop)?
- Interaction with `chain.py` (epics drive auto) and cloud (shells `megaplan` over SSH).

Key question: how much of auto.py's robustness is *load-bearing process isolation* that an
in-process port silently loses (crash containment, memory blowup, runaway worker kill, signal
handling)? Rank the responsibilities by port-difficulty. Name the isolation property most likely
to be lost in translation that the brief's "~600 LOC port" estimate ignores.
