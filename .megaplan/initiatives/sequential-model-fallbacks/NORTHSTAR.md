---
type: anchor
anchor_type: north_star
slug: sequential-model-fallbacks
title: 'North Star: Unified Managed-Agent Profiles and Sequential Fallbacks'
created_at: '2026-07-04T02:08:44.561159+00:00'
updated_at: '2026-07-11'
---

# North Star: Unified Managed-Agent Profiles and Sequential Fallbacks

## End State

Megaplan workers, resident-launched agents, and every managed descendant use one versioned resolution and custody contract. A D1–D10 task specification resolves deterministically to a profile, ordered model chain, reasoning effort, tool/sandbox ceiling, and time/token/cost/attempt budgets; the same request produces the same resolution receipt in every dispatcher. Managed agents may launch bounded children only through the first-class launcher, with complete immutable root-task custody, ancestry and request provenance, inherited non-expanding authority, durable structured results, restart-safe accounting, and root-only user delivery.

Ordered model fallback remains an availability mechanism built on the existing `partnered-5` and fallback-chain machinery. All dispatchers use the same canonical failure classes. They advance only when policy permits and there is affirmative evidence that the failed attempt could not have mutated externally visible or repository state; ambiguity fails closed.

## Delivery Contract

Reach this end state through exactly two aggressive executable sprints in roughly two weeks total. Sprint 1 establishes the shared resolver/profile, fallback-safety, immutable custody/schema, and durable managed-launch/result foundations through concurrent workstreams and an explicit interface convergence gate. Sprint 2 concurrently completes tree authority/root budgets, cross-dispatcher integration and additive migration/resume, and adversarial conformance/rollout readiness before one deterministic final gate. The two-sprint chain preserves every invariant below; it does not serialize the former seven work packages inside either sprint.

## Resolution Invariants

1. **One resolver.** Megaplan execute/critique/fanout and resident root/child dispatch call the same pure D1–D10 resolver and consume the same versioned profile data. Adapter-specific routing tables are forbidden.
2. **Deterministic input.** Resolution is a pure function of the normalized task specification, D1–D10 difficulty, task kind/risk flags, requested profile or overrides, parent ceilings, root budget state, available profile revision, and explicit operator policy. Environment discovery may reject a route but may not silently rewrite it.
3. **D5 is the middle default.** Missing difficulty resolves to D5 with reason `default_d5`; explicit D5 stays D5. D5 selects the routine middle profile/model class and medium reasoning unless a documented risk rule raises it. It never rounds down, inherits a child's self-claimed reduction, or means “unknown.” Ambiguous/high-risk work may deterministically raise the effective route while retaining requested difficulty and reason evidence.
4. **Complete receipt.** Every resolution persists requested and effective difficulty, task kind/risk inputs, profile revision, selected profile, ordered model specs, reasoning, tools, sandbox, all ceilings/budgets, applied defaults/overrides, policy reasons, and a canonical receipt hash. Scalar callers receive the same primary route they receive today.
5. **Explicit overrides only narrow descendants.** A root operator may select an allowed route within configured system ceilings. Descendants cannot raise model class, reasoning, tools, sandbox permissions, wall time, tokens, cost, fanout, depth, or attempt allowance.

## Fallback Invariants

1. Native TOML arrays and the existing canonical compact JSON bridge remain the ordered-chain representation; existing scalar profile behavior is byte/route compatible at public and persisted boundaries.
2. One canonical retry classifier and decision record is used by Megaplan workers, fanout, resident roots, and managed children. Dispatcher-local string matching is forbidden.
3. Fallback covers only canonical availability/independent-provider operational classes allowed by policy. It never repairs quality, semantic, schema, test, evidence, gate, review, blocked, unsupported configuration, or malformed-output failures.
4. Provider-family independence, visited-spec history, root-scoped attempt budget, and remaining ceilings are checked before every attempt. A `(canonical spec, provider family, relevant policy revision)` already visited in the root tree cannot be retried through another ancestor or descendant.
5. **No post-mutation fallback.** A later model may be attempted only with affirmative pre-mutation evidence. Any output, accepted structured result, tool side effect, file/tree change, checkpoint, external send, unknown timeout outcome, or missing mutation evidence closes the fallback gate and records the fail-closed reason.
6. Exhaustion is terminal and explicit. No ambient fallback, arbitrary shell relaunch, or silent primary flattening may bypass the configured chain.

## Custody and Managed-Tree Invariants

1. A root run captures the complete root brief/task as immutable content-addressed bytes plus canonical metadata. Every descendant carries the same root reference and SHA-256 hash, its own immutable task reference/hash, and a parent reference. Previews, argv strings, mutable paths, and conversation windows are never custody authority.
2. Descendants are created only through the managed child-launch API/tool. Direct unmanaged subagent shell spawning is outside the contract and must be rejected or made incapable of claiming managed custody/results.
3. Every run has immutable root id, run id, parent id, ordered ancestry, depth, child ordinal, root attempt-budget id, and launch/request provenance. Discord-origin provenance is inherited unchanged and cannot be replaced by a child or mutable conversation cursor.
4. Children persist versioned structured results and artifact references to their parent/root ledger. Only the root may authorize a user-visible completion. Children never send Discord/user replies directly; the Discord corrective initiative owns the eventual outbox/delivery lifecycle.
5. Authority is intersection-only: child model/tool/sandbox/cost/time/token/attempt limits are the minimum of system, root, parent, profile, and explicit request ceilings. Missing or malformed custody/ceiling evidence fails launch.
6. Default tree bounds are depth **2** below the root, at most **4** direct children per parent, and at most **8** descendants per root. These are conservative configurable ceilings, enforced transactionally across concurrent launchers; configuration may lower them, and raising them requires an explicit root/operator policy change and evidence.
7. Attempts and spend are root scoped, not process scoped. Reservation/commit/release transitions survive crashes and prevent concurrent oversubscription. Cancellation and restart preserve consumed attempts and visited specs.

## Migration and Evidence Invariants

1. Introduce an additive managed-run/child-result schema revision with strict validation and canonical hashing. Existing `arnold-resident-agent-run-v1`, legacy scalar profile/state, and current Megaplan plan records remain dual-readable through an explicit backfill/cutover/rollback sequence.
2. V1 records may be projected into a conservative root-only tree but cannot be fabricated into complete brief custody or expanded privileges. Operations requiring missing proof fail closed or stay on the legacy path.
3. Observability exposes deterministic resolution receipts, ancestry, immutable content hashes, fallback attempts/classifications, mutation-gate evidence, budget reservations/consumption, limit denials, structured child-result state, and restart/resume transitions without storing secrets or full Discord content beyond existing policy.
4. Time, token, cost, attempt, depth, fanout, and descendant limits are machine-enforced and tested under concurrency, crash, replay, and resume—not merely prompt instructions.
5. Acceptance evidence proves scalar compatibility, all D1–D10 routes, D5 default/explicit/high-risk behavior, identical classification across dispatchers, no post-mutation fallback, complete brief hashes, immutable custody/provenance, root-only delivery, bounded trees and budgets, no privilege expansion, schema dual-read compatibility, and deterministic restart/resume.

## Ownership Boundary with Discord Corrective

This initiative owns generic profile resolution, fallback policy, immutable root/task references, managed ancestry/child launch, inherited ceilings, structured child results, and the rule that only a root can request user delivery.

`.megaplan/initiatives/discord-resident-delegation-delivery-corrective/` owns Discord ingress provenance creation, message lifecycle, acknowledgement/terminal outboxes, transport idempotency, attachment delivery, retries, and provider reconciliation. This initiative consumes its immutable provenance envelope and hands one root completion intent/result to its delivery contract; it does not redesign or duplicate the Discord ledger. Integration changes must be additive and coordinated at the provenance-envelope and root-completion interfaces.

## Explicit Non-Goals

- No parallel resident or Discord bot loop.
- No arbitrary unmanaged shell spawning presented as managed child launch.
- No child-to-user or child-to-Discord delivery.
- No fallback for quality repair or after possible mutation.
- No comma-delimited or ad hoc fallback syntax.
- No privilege, budget, or custody expansion during migration.
- No xhigh/max planning-depth requirement for this epic.
- No launch, resume, or cloud execution as part of shaping these assets.
- No production rollout before the operator configuration and canary gates are satisfied.

## Drift Signals

- Two dispatchers resolve the same task spec differently or classify the same failure differently.
- D5 is treated as unknown, low effort, or an implementation-specific default.
- A child sees a summary when the complete root-task hash/reference is required.
- A descendant changes request/Discord provenance, delivers to a user, or expands authority.
- A retry occurs without affirmative no-mutation evidence or outside the root attempt budget.
- Depth/fanout/descendant limits are prompt-only or process-local.
- V1 compatibility silently fabricates custody, drops fallback arrays, or broadens sandbox/tools.
