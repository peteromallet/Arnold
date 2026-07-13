# S3: Megaplan Boundary Coverage And Cloud Custody

> Superseded as an executable milestone by C1-C6. Preserved as historical
> checklist material; see the 2026-07-10 corrective reshape decision.

## Outcome

Extend the boundary-contract system across Megaplan phases, reducers, chain
milestones, PR/CI transitions, repair records, and cloud custody. The system can
detect artifact/state/promotion divergence across core phases and distinguish
real cloud custody from vague process liveness.

This sprint collapses the detailed briefs:

- `m7-phase-coverage-and-reducer-boundaries.md`
- `m9-chain-pr-cloud-boundaries.md`

## Scope

IN:

- Add contracts or time-bounded migration exceptions for plan, revise, critique, critique
  evaluator, gate, execute, finalize, review, tiebreaker, feedback where
  present, child/reducer flows, and parent-state promotion.
- Represent reducer semantics: child outputs, aggregate canonical outputs,
  parent-state promotion point, side-effect evidence, blocked/retry records,
  and repair-domain separation.
- Add chain/PR/cloud contracts for milestone start/completion, PR ready/merged,
  chain complete, cloud repair dispatch, ordinary repair completion,
  meta-repair completion, and 6h auditor completion.
- Add cloud custody contracts for managed-running under expected
  tmux/supervisor/session custody, complete, unmanaged-running with warning,
  blocked relaunch failure, and escalated after repeated unchanged custody
  findings.
- Pin evidence for chain state, PR/CI refs, repair data, expected session/tmux
  identity, live process fingerprints, active-step worker liveness, relaunch
  commands, and failure reasons.
- Detect stale PR heads, stale repair-data, missing repair verdicts, stale
  active-step worker PIDs, unmanaged live processes, repair success without
  custody, and watchdog/status custody disagreement.
- Preserve all detailed acceptance criteria from the two source briefs as the
  sprint checklist.

OUT:

- Public workflow conformance enforcement.
- Replacing GitHub/CI providers.
- Solving external service unreliability generally.
- Repair-loop/status/auditor consumption changes beyond what is needed to
  produce the facts consumed by S4.

## Locked Decisions

- Child turns never advance parent state.
- Reducer promotion owns parent canonical artifacts and parent state effects.
- Execute is not atomic; it records side-effect evidence and resume anchors.
- Chain/cloud evidence cannot rely on branch names or clean worktrees alone.
- Process liveness alone is not cloud run custody.
- Repair completion is trusted only when it proves the original finding cleared
  or gives a structured no-fix/escalation verdict.

## Done Criteria

1. Every covered phase has a contract; no supported-surface exception survives
   C6 final acceptance.
2. Semantic-health tests cover at least one broken contract per phase family.
3. Reducer tests cover child output without reducer promotion and reducer
   promotion without required child evidence.
4. Chain milestone advancement has boundary contract evidence.
5. PR merge transition verifies merge commit contains expected tip where
   applicable.
6. Repair-loop and meta-repair records have structured verdict requirements.
7. Cloud run custody contracts distinguish managed-running, complete,
   unmanaged-running-with-warning, blocked relaunch failure, and escalated.
8. Tests cover stale PR head, stale repair-data, no-verdict repair artifacts,
   stale active-step worker PID, unmanaged live process, repair success without
   custody, and watchdog/status custody disagreement.

## Touchpoints

- plan/revise/gate/finalize handlers
- execute/review/tiebreaker orchestration
- BoundaryTurn reducer code
- semantic-health evaluator
- `arnold_pipelines/megaplan/chain/*`
- `arnold_pipelines/megaplan/cloud/*`
- GitHub/CI evidence helpers
- repair and meta-repair wrappers
- progress auditor
- existing phase, reducer, and chain completion guard tests
