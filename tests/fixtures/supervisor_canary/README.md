Supervisor canary fixture for M5d.

This directory is a hermetic unit-test fixture. The tests use fake drivers and
fake pack runners only; they do not invoke live `megaplan auto` runs.

Fixture shape:
- `chain.yaml` defines two milestones (`alpha`, `beta`).
- `supervisor-canary.yaml` defines two milestones (`alpha`, `beta`).
- `beta` depends on `alpha`, so the supervisor must persist one dependency
  assertion.
- Unit tests induce one per-run failure on `beta` before the fake driver
  succeeds on retry.

Live release gate:

`MEGAPLAN_SUPERVISOR_TIER=1 megaplan chain start --spec tests/fixtures/supervisor_canary/supervisor-canary.yaml`

Treat that command as a release gate, not a unit test. It drives real plans and
is the throwaway canary the M5d brief calls for when validating the flag-on
supervisor path end to end.
