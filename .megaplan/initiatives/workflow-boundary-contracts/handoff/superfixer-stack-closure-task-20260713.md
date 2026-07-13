# Superfixer stack closure and C1 recovery

Use the `superfixer-debug` skill completely. This is an execution assignment, not a report-only diagnosis.

## Objective

Restore the complete watchdog -> L1 repair -> L2 meta-repair -> six-hour auditor chain of custody so deterministic actionable findings reliably acquire durable repair custody and launch the appropriate managed repair agent. Then re-trigger the original Workflow Boundary Contracts C1 incident and verify the real chain advances.

The six-hour auditor may remain report-only if that is the intended authority boundary. In that case, prove and repair the next authorized layer that must convert its findings into a typed request, claim, attempt, and terminal decision. Do not give a reporting projection mutation authority merely to make the symptom disappear.

## Existing work: coordinate, do not duplicate

Resident run `subagent-20260713-140203-ba91f563` is already the primary implementation/root-cause run for this incident. Inspect its durable manifest, log, current edits, and eventual result first. It has reportedly found broken request claiming, missing L2 escalation, incorrect auditor queue routing, and misleading running status.

Treat that run as active upstream work. Reuse and verify its changes, fill gaps, or take over only after its durable state proves it is terminal or unable to continue. Do not make competing edits to the same surfaces concurrently. Preserve unique work and clearly record coordination decisions.

## Ground truth

The canonical status snapshot generated at 2026-07-13T14:38:57.593854Z reports session `workflow-boundary-contracts-corrective-20260710` at 25% overall, current plan `c1-contract-reality-20260711-1433`, plan stage estimate 100% (`executed`), but with a stopped runner and stale dead review worker. Repair request `7473fa422fea89a936d0be64f25468524f0d7d0e1c8632478f5dcfc6ec37860e` was accepted with no typed blocker identity and received zero claims or attempts. Later audits detected the missing meta-repair path, but custody did not turn that evidence into execution.

Ground truth all relevant sources and ask TRACKED / FIXED / INTENT / CONTEXT at every layer. Identify both the first broken layer and the layer above that failed to catch it.

## Required work

1. Trace the full fixer stack and immutable custody records for the original C1 failure.
2. Establish why accepted requests can remain unclaimed, why L2 did not launch, how auditor findings are routed, and why status could claim activity without a live runner.
3. Fix the first broken layer and its missing backstop. Hunt sibling producers/consumers with the same defect.
4. Ensure actionable deterministic failures carry typed failure kind, stable blocker/root-cause identity, evidence cursor, retry budget, and durable request -> claim -> attempt -> decision history.
5. Ensure the six-hour path either launches an authorized managed repair agent or durably hands off to the authorized dispatcher that does. Add a regression proving the full path, not merely a unit-level classifier result.
6. Verify any resident-managed child launch inherits the immutable inbound delegation provenance. Never synthesize or replace Discord provenance. A malformed or ambiguous envelope must stop the launch.
7. Use managed child agents only for bounded independent work and only when they will not collide with the existing primary run. Classify every child with task kind and D1-D10 difficulty.
8. Run focused and appropriate broader tests. Deploy/refresh the actual live runtime through canonical safe mechanisms if code changes require it.
9. Re-trigger the original WBC C1 session through supported recovery controls. Do not hand-advance state, force-proceed, relax guards, or create a duplicate chain.
10. Verify fresh liveness and real advancement of the original chain. Add or update the six-hour auditor regression so this exact failure would be identified and routed correctly in the future.
11. Record a durable handoff under the canonical `workflow-boundary-contracts` initiative describing root cause, changes, tests, deployment evidence, recovery evidence, remaining risks, and any human gate.

## Constraints

- Do not use arbitrary remote shell commands or raw SSH. Use constrained Megaplan cloud/status/control mechanisms and the configured cloud YAML; use canonical on-box handling when already inside the target agentbox.
- Do not babysit. Durable agents, chain runners, watchdogs, and bounded repair own continued progress.
- Do not overwrite unrelated dirty work.
- Do not claim success until the live original chain has advanced or a genuine typed human gate is proven.
- If the existing primary run is still editing overlapping files, coordinate by waiting for its durable output or work on non-overlapping verification/design surfaces; do not race it.

## Completion contract

Success requires: the fixer defect and its missed backstop are repaired; managed launch/custody is proven end-to-end; focused and broader validation are recorded; the live runtime is using the fixed code; and the original C1 chain shows fresh, authoritative progress. If any element is not achieved, report a partial outcome with the exact remaining custody owner and next authorized action.
