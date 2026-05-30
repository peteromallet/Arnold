Superseded by `tests/characterization/auto_drive_corpus/` (M2.5). These four prototype fixtures remain for backwards reference only and are NOT the oracle.

# Corpus notes — M0 harness floor

## Shape

Four deterministic traces committed under `tests/fixtures/corpus/`:

| File                | status     | Key signal                           |
|---------------------|------------|--------------------------------------|
| happy.json          | done       | clean completion                     |
| execute_stall.json  | stalled    | stall metadata, iterations=7         |
| blocked_retry.json  | blocked    | blocked_retries_used=3               |
| escalate.json       | escalated  | tier_escalations_used=2, tier pin=2  |

## SD1 — recover shape

The brief's **recover** shape (blocked-retry-then-resume) is intentionally
covered by the **W5 substrate-swap self-test** rather than a dedicated
corpus trace.  A recover-shaped trace requires a two-phase state
transition (blocked → resume → done) that the dual-run rig handles in
its self-test cycle.  Adding a recover fixture here would create a
maintenance burden without increasing coverage beyond what W5 already
provides.

## Real-run capture

Capture of traces from a live driver run is **deferred to M1**
(accepted debt).  M0 is a harness floor — all traces here are
synthetically constructed via direct `DriverOutcome` instantiation.

## Determinism guarantee

Every trace is built by direct `DriverOutcome(...)` construction
with **no `Date.now`**, **no `random`**, and **no driver state-machine
replay**.  Serialization is via `DriverOutcome.to_json()`, which uses
`json.dumps(…, indent=2)` with insertion-ordered dicts.  The
regenerator test (`tests/test_corpus_gen.py`) rebuilds each outcome
identically and asserts **byte-equality** against the committed files.
