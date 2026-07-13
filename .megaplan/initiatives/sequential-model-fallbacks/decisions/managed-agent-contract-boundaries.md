# Managed-Agent Contract Decisions and Ownership Boundaries

Date: 2026-07-11  
Status: locked for epic planning

## Decisions

1. **Reuse this initiative.** The existing fallback design, `partnered-5` arrays, shared fallback primitives, resident D1–D10 routing, and durable resident manifest are partial layers of one managed dispatch contract. A parallel initiative would create competing routing and custody authority.
2. **One transport-neutral resolver.** Megaplan and resident adapters consume a shared pure D1–D10/profile resolver. Adapters may translate inputs/outputs but may not own routing tables or retry classification.
3. **D5 semantics.** Missing difficulty defaults to D5 with an explicit reason. Explicit D5 remains distinguishable. The base D5 route is the middle/routine model class with medium reasoning; deterministic high-risk/task-kind policy may promote the effective route without rewriting requested difficulty.
4. **Fallback semantics.** Ordered fallback extends the existing `partnered-5`/`FallbackSpecChain` machinery. One canonical classifier applies everywhere. Advancing requires affirmative no-mutation evidence; unknown is treated as possible mutation and fails closed.
5. **Complete immutable custody.** Root and child tasks are stored as complete content-addressed bytes with SHA-256 references. A preview, prompt window, argv value, filename, or mutable path is not a task reference.
6. **Managed launch only.** Resident roots and managed descendants launch children through one typed, idempotent, fenced API/tool. A generic shell-spawned process cannot claim managed ancestry, budget, result, or delivery authority.
7. **Root-only delivery.** Children persist structured results for their parent/root. Only the root may submit a user-completion intent. Transport delivery remains outside the child contract.
8. **Non-expanding inheritance.** Descendant authority is the intersection of system, root/operator, parent, profile, and requested ceilings. Missing evidence never widens a child.
9. **Root-scoped accounting.** Attempts, visited specs, time, tokens, cost, and tree counts are durable root-tree state with reservation/fencing semantics.
10. **Default bounds.** Depth is limited to two levels below root, direct fanout to four per parent, and total descendants to eight per root. These defaults balance useful decomposition (a root can delegate and a child can subdivide) against exponential spend/custody risk. They are configurable downward. Raising them is an explicit operator/root policy action recorded in the receipt, not a child override.
11. **Additive migration.** Introduce a new managed-run/result schema revision with v1 dual read, conservative projection, shadow comparison, backfill, cutover, and rollback. Never fabricate missing custody or delete legacy evidence during this epic.
12. **Two-sprint delivery.** Deliver the full contract in exactly two aggressive sprints over roughly two weeks. Sprint 1 runs resolver/profile, fallback safety, custody/schema, and launcher-foundation tracks concurrently, serializing only their interface convergence. Sprint 2 runs authority/budget enforcement, dispatcher migration/resume, and conformance/rollout tracks concurrently, then closes them through one deterministic traceability gate. The chain-level dependency is only Sprint 2 on Sprint 1; the former seven-milestone decomposition is superseded, not nested behind two labels.

## Discord coordination boundary

The `discord-resident-delegation-delivery-corrective` initiative owns:

- creation and durability of Discord ingress/request provenance;
- message lifecycle, acknowledgement and terminal outboxes;
- request/transport idempotency, provider receipts/reconciliation, retries, dead letters;
- inbound/outbound attachments and user-visible Discord delivery.

This initiative owns:

- generic D1–D10 profile resolution and ordered fallback;
- immutable root/child task references and ancestry;
- managed child launch, inherited ceilings, tree/root budgets, structured results;
- immutable consumption/propagation of request provenance;
- the rule and generic interface by which only a root submits one completion intent/result.

The integration must use a versioned compatibility seam. If the Discord initiative's current provenance or completion interface is insufficient, this epic may specify an additive field/interface requirement and coordinate it; it must not copy the Discord ledger or implement direct transport sends.

## Operator decisions intentionally deferred to deployment

- Exact provider/model catalog entries and aliases for each D1–D10 profile revision.
- Numeric default dollar, token, and wall-clock ceilings for each environment/root class.
- Whether any production root class may explicitly raise the structural defaults.
- Canary population and final cutover date.

The implementation must require, validate, version, and receipt these values. Safe development defaults may be supplied for tests, but production must not silently infer them.
