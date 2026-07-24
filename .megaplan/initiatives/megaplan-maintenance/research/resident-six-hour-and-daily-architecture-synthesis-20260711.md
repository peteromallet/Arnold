# Resident architecture synthesis: six-hour unblocker and daily auditor

Source: completed resident run `subagent-20260711-161224-0139c7b5`, durable result read from generated resident-run state on 2026-07-11. This file promotes its architecture conclusions into the canonical initiative without copying or changing runtime state.

## Adopted findings

- Use one event-sourced maintenance control plane with two products: operational recovery every roughly six hours and read-only systemic efficiency analysis every roughly 24 hours.
- Trust accepted Run Authority/WBC/transition/receipt evidence before mutable snapshots or status labels. Capture it in a coherent, versioned envelope; missing or torn evidence is unknown.
- Extend the existing incident ledger. Separate operational custody, verification, and analytical projections so a diagnosis cannot overwrite an active repair.
- Use occurrence-scoped dedupe, root-cause clustering, leases/fencing, append-only corrections, deterministic replay, and an independent verifier.
- Allow parallel observers/classifiers/investigators/analysts, while serializing repair claim/effects, transition writes, verification, and ticket/initiative authority.
- Keep the daily loop inert with respect to active repairs and chains. It may append a proposal but not repair, reroute, reprioritize, or reshape.

## WBC evidence incorporated

The resident analysis found repeated gate schema failures for an unexpected `north_star_actions` property from about 15:30–15:36 UTC, followed by adoption of a passing gate artifact around 15:43 and state/event advancement around 15:45. It also identified earlier finalize-output publication gaps of approximately 79, 84, and 176 minutes.

This supports a strict distinction: the operational loop opens or joins one occurrence only while accepted output and valid custody are absent, then verifies the blocker cleared; the daily loop clusters equivalent failures and publication dwell to recommend a root fix. Neither treats a transient live/no-process/status label as truth, and the daily loop does not restart or alter WBC.

## Validation evidence inherited, not rerun here

The resident task reported read-only inspection of maintenance, Run Authority, WBC, repair custody, watchdog/auditor, ledger, snapshot, and local WBC artifacts, plus 39 focused ledger/projection/six-hour tests passing. Those results are provenance for the analysis, not proof of this edited chain spec; current editorial validation is recorded separately in the launch-readiness handoff.

## Decisions intentionally left human

Baseline/SLO numbers, backend and retention, cost source/cohorts, lease durations, schedule timezone, ticket policy, safe-repair allowlist, promotion thresholds, and rollback/escalation ownership remain explicit gates.
