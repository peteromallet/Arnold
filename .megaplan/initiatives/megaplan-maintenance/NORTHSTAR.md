# Maintenance Control Plane North Star

Megaplan maintenance must restore forward progress safely and make systemic waste visible without becoming a second execution authority. The six-hour operational unblocker and 24-hour efficiency auditor consume the same append-only incident/maintenance ledger but serve different products: the unblocker may request bounded action through canonical repair custody and prove recovery; the daily auditor may analyze and recommend but never claim a repair or reshape an active chain.

## End-state invariants

- Run Authority remains authoritative for grants, accepted attempts, decisions, fences, and quarantine. Canonical transition/repair custody remains authoritative for plan and chain mutations.
- Neither loop directly edits plan/chain truth. Repair actors propose or claim through canonical custody; the lifecycle TransitionWriter is the only state writer.
- The six-hour loop owns operational detection-to-verification for a concrete occurrence. The daily loop owns read-only efficiency analysis across completed and censored histories.
- One append-only, versioned ledger preserves observation, finding, custody, action, verification, recurrence, and analytical events. Operational custody, verification, and efficiency-analysis projections advance independently.
- Every decision reads a coherent `ObservationEnvelope`: source identities and versions are captured together; torn, stale, cross-environment, or incomplete evidence yields typed `UNKNOWN`/`INCOHERENT`, never green or dispatchable state.
- Deduplication is occurrence-scoped. A verified recurrence creates a new occurrence with causal links and a fresh bounded budget; it is not suppressed forever by an old fingerprint.
- Claims and scheduled windows use renewable leases with monotonically increasing fencing tokens. Stale workers cannot install, retrigger, transition, verify, or materialize tickets.
- A repair actor cannot verify itself. Closure requires a later independent, blocker-specific negative control plus durable resumed-progress evidence.
- Event-time windows are half-open, watermarked, replayable, and correction-based. Late evidence appends a correction; it never rewrites history.
- Missing denominators, censored durations, unknowns, evidence coverage, classifier version, and content hashes are visible in every report.
- Production action remains default-off until explicit canary promotion gates are met; observation and report generation remain available when mutation is disabled.

## Authority and player model

Observers, envelope validators, per-run classifiers, read-only investigators, and independent daily cluster workers may fan out. One synthesizer deterministically merges their immutable outputs.

The following are serialized under canonical authority: one repair claim per occurrence; source/install/retrigger effects; TransitionWriter mutations; terminal verification; ticket materialization and initiative prioritization; and every human approval. Parallel workers may recommend these actions but cannot perform them without the relevant claim, lease, fence, policy gate, and receipt.

## Safe automatic boundary

The six-hour loop may automatically capture evidence, append findings, reconcile derived projections, enqueue or join one deduplicated repair request, reclaim an expired fenced claim, invoke an already-approved allowlisted retry/relaunch policy, and schedule independent verification. All mutation still requires both the master mutation gate and the path-specific gate.

The daily loop may append metrics, analytical classifications, recurrence clusters, and deduplicated ticket proposals. It cannot repair, reroute models, alter profiles or budgets, waive gates, edit an active brief/chain, or claim active custody.

Human approval is required for force-proceed or waiver, active-chain redesign, profile/budget changes, destructive Git/provider actions, protected-branch publication, real human gates, ambiguous blockers, new repair classes, ticket auto-materialization policy, and rollout promotion.

## Rollout destination

Ship contracts and reducers first, run both products in shadow/report-only mode, then canary only allowlisted six-hour repair requests with independent immediate/5m/1h/6h verification. Enable daily ticket proposals only after precision is measured; ticket materialization and all autonomy expansion remain explicit human gates. Rollback must disable action while preserving observation, ledger append, replay, and reporting.

## Anti-goals

- Do not infer recovery from commits, passing local tests, agent completion, PID/tmux health, fresh activity, or status labels alone.
- Do not let a daily diagnosis overwrite operational custody or quietly become an operator.
- Do not create a competing maintenance ledger, repair queue, transition writer, or initiative.
- Do not mutate paused/in-flight runtime state merely because these durable editorial assets changed.
