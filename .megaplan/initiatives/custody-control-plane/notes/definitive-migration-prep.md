---
type: prep
date: 2026-07-11
classification: cross-cutting-migration-D5
---

# Post-WBC custody follow-up prep

## Sizing

The pending work is one roughly two-week Megaplan milestone. WBC already owns
the boundary declarations, durable attempt/effect history, payload policy, and
broad runtime conformance that the earlier M5-M10 draft proposed to build again.
The safe residual is narrower: converge the existing Megaplan cloud-chain
custody read and decision path on the completed WBC and Run Authority contracts.

The durable one-milestone chain is retained only to encode the WBC completion
dependency, content-addressed manifest requirement, and automatic follow-up
admission check. M1-M4 remain completed historical foundation and are not listed
as pending milestones. The former six-milestone continuation is superseded as
an executable plan; its exhaustive migration matrix remains research, not scope.

## Dial selection

Overall plan difficulty: 5/5; selected profile: `partnered-5`; because a wrong
authority mapping can pass local tests while enabling repair from stale,
contradictory, or version-mismatched evidence.

- Planning complexity: `full`, because the bounded cutover still crosses the
  resolver, cloud status/current-target, watchdog, repair dispatch, and verifier.
- Depth: `high`, because the planner must trace landed WBC/Run Authority contract
  versions and distinguish observation, authority, and compatibility paths.
- Vendor: `codex`.
- Prep: enabled and directed at the completed manifests, landed interfaces, and
  current call graph; this is integration discovery, not open-ended architecture.
- Recorded shorthand: `partnered-5/full/high @codex +prep`.
- No `xhigh` or `max` depth is requested.

## Fail-closed launch posture

Launch requires both a genuinely complete WBC chain with a current non-empty
completion manifest and a human-approved custody decision record. WBC currently
has no completion manifest in this checkout, so the dependency is intentionally
unsatisfied. `merge_policy: review`, manual clean-PR review, required validation,
`auto_approve: false`, clean-base enforcement, and stop-on-failure/escalation keep
execution and promotion from advancing unattended.

Production enforcement, mutating repair, provider/Git effects, and legacy
deletion remain separate post-run human gates. The milestone must finish with
those controls action-off.
