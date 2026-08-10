# S6 - Override, Recovery, Auto-Drive, and Projection Adoption

## Objective

Make every override/recovery/configuration route and exact reentry edge authored
topology, then reduce auto-drive, CLI, status, watchdog, auditor, and projections
to non-authoritative consumers of the admitted M11 control/query APIs.

Make the `NP-GT-006` family in `../GOLDEN_TRACE_CONTRACT.md` green, including
`NP-GT-006A`, `NP-GT-006B`, and `NP-GT-006C`.

Before any S6 work, reconsume the exact C1/C2 manifests, S2R
kernel-enablement receipt, S5B completion-slice receipt, current
divergence-ledger hash, accepted M11 coordinates, and scoped
topology/obligation hashes. Missing, stale, unresolved-blocking,
cross-incarnation, or mismatched evidence blocks GO-3.

S6 closes GO-3 through the pre-merge/post-merge `conformance_gate`. Every
registry-side control-authority demotion, legacy-writer fence/delete, or
heterogeneous rollout operation must consume that exact accepted post-merge
receipt. A chain milestone state or later S7 result cannot authorize it.
The cutover runs only as the chain's declared S6 transition, emits one
immutable control-authority receipt, and must pass the separate post-transition
GO-3 verifier over the final writer/fence/consumer state before S6 completes.

## Product scope

- abort, force-proceed, replan, recover-blocked, resume-clarify,
  resume-tiebreaker, adopt-execution, cancel, terminal halt, publication, and
  delivery routes;
- model/vendor/profile/robustness configuration effects followed by explicit
  reentry at the current semantic phase;
- `add-note` and supported non-routing annotations as typed effect-only actions
  with exact target, current required authority/custody, durable WBC effect
  history, and an explicit `no_route_change` outcome;
- unknown-action denial;
- auto-drive scheduling/event consumption and liveness only.

## Required work

- Keep `workflows/control/` workflow-free unless a genuine independently
  hosted child topology is discovered and separately migrated. Override,
  reconfiguration, human-control, auto-drive, and compatibility operations are
  typed `.py` steps/effects/policies whose resulting route remains visible in
  the calling workflow (`plan_quality/gate.pype` or
  `delivery/cycle.pype`). No control step may invoke a step or workflow.
- Author each action as a closed typed decision with capability, exact semantic
  target/reentry, and terminal or loop effect.
- Implement model/vendor/profile/robustness changes through the S2R typed
  `reconfigure` transition: accepted schema-versioned delta, durable checkpoint,
  new policy/executable/product-contract binding, and exact named-cursor
  reentry. Ambient context or live flags cannot mutate control flow.
- Route authority-increasing actions through the existing M11 action/recovery
  boundary. Native Parity supplies semantic target/reentry; it does not create
  recovery policy, grants, leases, WBC queries, or reconciliation.
- Reduce auto-drive to consuming canonical events and requesting
  topology-declared actions. It may not derive product route, retry/cap policy,
  model choice, resume, completion, cancellation, publication, or delivery from
  state/status.
- Enforce an explicit scheduler allowlist. Given an immutable admitted typed
  action already selected by topology/accepted decision, auto-drive may choose
  only eligible worker/host, queue, and dispatch/wakeup time. It cannot create
  or reinterpret outcome, retry generation, escalation, cap/cost/stall,
  model/config change, resume, or terminal.
- Adopt M11 exact-version WBC queries and pure rebuildable projections for
  observation. Do not rewrite status/watchdog/auditor projection machinery.
- Make completion status, Markdown, causal explanations and fixer inputs pure
  projections from immutable bindings/verdicts/acceptance records. Delete,
  rebuild, forge, corrupt and cursor-diverge each projection; none may satisfy
  an obligation, choose a candidate, accept a decision, dispatch repair, or
  change effect/terminal truth.
- Prove every legacy independent completion writer and reader-to-authority path
  is deleted or structurally inert through reader/use-def reachability plus
  mutation. Compatibility readers may decode exact pinned legacy records as
  `legacy/unknown`; compatibility writers may not remain.
- Prove `LEGACY_ALIASES`, component override matrices, handler action
  dispatch, manifest route maps/defaults, `_core` product transitions, projected
  native programs, and CLI decision translation are absent or structurally
  inert, then delete/fence them only through the GO-3-consuming cutover path.
  Structurally inert means reader/use-def reachability proves no data or
  control path from the carrier to route selection, decision acceptance,
  admission, resume, retry, effect intent, terminalization, or an
  operator-facing action that can bypass current RA/Custody/WBC admission.
  Pair reachability with carrier mutation; writer-only inventory is
  insufficient.
- Add projection-forgery, stale-cursor, replay, and evidence-as-authority
  negative tests.
- Author one closed cancel/publish/deliver/terminal arbitration and CAS contract.
  It declares legal preconditions, mutual exclusion, preserved effect history,
  terminal precedence, and rejection outcomes; wall-clock order or projections
  cannot choose the winner.
- Keep the terminal-arbitration role, semantic key and accepting Run Authority
  identity stable and explicit. A future root-host adapter may translate the
  closed result only by consuming that same accepted identity; it cannot replace
  the arbiter or create a second root acceptance domain.
- Prove `NP-GT-006A` cancel-before-publish, `NP-GT-006B`
  publish-outcome-before-cancel/pre-delivery, and `NP-GT-006C`
  delivery/done-before-late-cancel. Equivalent semantics to the durable golden
  contract are allowed only when explicitly authored and mutation-tested.
- Build a Native composed-history explanation and repair preflight solely from
  admitted M11 queries. It joins semantic occurrence/retry/reentry, exact
  accepted/consumed decision, current/historical fence and epoch, WBC
  attempt/effect ambiguity, pinned/current executable digests, and terminal
  arbitration. It lists only legal request-only repairs and failed
  preconditions; it never dispatches, authorizes, or chooses a route.
- Prove deletion/rebuild of the explanation/preflight is deterministic and
  behaviorally inert.
- Treat every repair-request field and projection-derived failed precondition as
  an untrusted hint. At acceptance M11 re-resolves canonical journals and
  current RA/Custody/WBC, reruns every precondition, and the action path invokes
  the shared validator again immediately before work. Add forged, stale, and
  internally inconsistent request mutations.
- Classify pre-work rejection from canonical facts. Actor-local stale worker/
  lease/epoch or placement failure may leave a still-valid unconsumed immutable
  decision eligible for M11-controlled reassignment. Semantic precondition,
  capability, executable/product/WBC drift or validity failure atomically
  invalidates it and requires a new request/decision. Consumed decisions and
  any decision after body/effect intent are never redispatched; scheduler code
  cannot choose the class.
- Derive every scoped CAS/arbitration site and participant transition family
  from lowered IR. Require exact equality with the versioned policy index and
  force every participant pair to the pre-CAS boundary in both release orders,
  preserving loser/rejected-late raw facts.
- Join every derived site to S2R's certified linearizable canonical
  store/service operation. Run two independent clients through the production
  adapter, force both orders and crash edges, and record adapter/store/schema
  provenance; application read/check/write or an in-process lock fails.
- Put each new control/arbitration ledger or registry in its admitted rollback
  boundary, or pass restore-then-replay before it becomes authoritative in S6.
  The receipt binds store incarnation/restore generation and raw-history
  high-water cursor.
- Remove S5B's delivery/control seam and prove no remaining control bridge can
  route, retry, resume, configure or terminalize.
- Append every completion comparison difference to C1's same stable-occurrence
  divergence ledger and bind its exact current hash in GO-3.
- Explicitly make `_core/workflow_data.py:WORKFLOW` and
  `_ROBUSTNESS_OVERRIDES` inert/hard-fenced or delete them. Mutate every
  supported robustness level and prove no runtime, auto, or CLI entry point
  reads those tables as route or live-policy authority.

## Semantic gate

- Source visibly owns every routing action and config-effect reentry edge.
- Force-proceed, abort, replan, recover, all resume forms, adoption, config
  change/reentry, add-note/annotation no-route-change, cancellation,
  publication, delivery, and unknown-action scenarios execute from lowered
  topology.
- Auto/CLI/runtime/component mutations cannot alter canonical product routes.
- Scheduler mutations for retry/escalation/cap/cost/stall/config/terminal and
  every `workflow_data.py` robustness mutation are inert or rejected.
- The closed arbitration/CAS source contract, not wall-clock/projection state,
  determines all `NP-GT-006A/B/C` outcomes.
- Root arbitration identity is unchanged by adapters, and production-store
  contention admits one winner at every derived site.

## Custody-adoption gate

- Each positive control action validates a current Run Authority grant/fence
  and exact Custody lease/epoch against its semantic target.
- Required WBC boundary evidence is exact-version and durable, but success
  receipts and projections cannot trigger or authorize an action.
- Projection deletion/rebuild is deterministic; forged, stale, internally
  consistent, or cursor-divergent projections remain observational only.
- Completion projections and legacy completion carriers are likewise inert,
  and the accepted S2R kernel remains the sole semantic evaluator/decoder
  authority.
- Mixed-version control/effect workers reject before action, and the composed
  explanation/preflight remains observation/request-only under every race.
- Stale or forged repair-request preconditions are recomputed from canonical
  stores and cannot be grandfathered into acceptance.
- Actor-local redispatch and semantic invalidation mutations follow their
  distinct declared dispositions; lowered arbitration sites have complete
  indexed forced-race coverage.

## Do not close if

- Auto-drive still interprets `next_step` or status to choose behavior.
- A compatibility projection or CLI handler can satisfy semantic evidence.
- Config changes apply without an authored effect and exact reentry edge.
- An add-note/annotation action can change route, omit exact target/fencing, or
  avoid durable WBC effect history.
- Cancel and done can both be accepted, delivery follows a winning cancel, or a
  late cancel rewrites terminal history.
- The Native incident view requires handler-local state, can issue a repair, or
  changes behavior when deleted/rebuilt.
- Auto-drive creates a retry/escalation or `workflow_data.py` changes a route,
  or a request-carried precondition is trusted without canonical revalidation.
- An application mutex/read-check-write emulates CAS, root hosting changes the
  accepting identity, or a control ledger reaches authority before restore proof.
