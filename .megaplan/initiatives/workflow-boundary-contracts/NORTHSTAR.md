# Workflow Boundary Contracts

## North Star

Every workflow boundary has one declared durable contract, and every producer,
transition gate, status view, repair loop, watchdog, and auditor reads from that
same contract.

A boundary is complete only when its declared durable effects are present,
coherent, and authorized.

Every supported workflow step and every one of its attempts also has an
ordered, durable kernel ledger history. Dispatch cannot begin until its start is
durable, and completion, failure, retry, suspension/resume, and cancellation
cannot be reported as settled until the corresponding ledger transition is
durable or an explicit persistence-failed/indeterminate condition is exposed.

## Why This Exists

The cloud prep incident exposed a process/state gap:

- prep work ran and wrote artifacts;
- `state.json` stayed `current_state=initialized`;
- history lacked prep success;
- `phase_result.json` was missing or stale;
- watchdog/status saw liveness and activity, not semantic progress failure.

The related cloud custody drift class exposed a second gap:

- a process can appear partially alive across watchdog, repair-loop, status, and
  auditor views;
- `active_step` may point at a dead worker PID;
- repair may restore execution as an unmanaged background process;
- status may classify the run as running from process evidence while no layer
  proves expected tmux/supervisor custody.

The immediate root bug was fixed in the prep/state merge path, but the broader
system still lacks a standard way to say:

> This boundary crossed a semantic line, but durable lifecycle evidence did not
> cross with it.

It also lacks a standard way to say:

> This cloud run is alive, but not under the expected custody contract.

This initiative merges three threads into one generalized boundary program:

- structured output / BoundaryTurn stage boundaries;
- TransitionWriter / transition-policy authority gates;
- semantic-health detection, repair triggers, status, and auditor evidence.

## End State

The system has a shared boundary vocabulary that covers Megaplan phases and
future workflow boundaries. It is deliberately split into three concepts:

- `BoundaryContract`: the declared durable effects expected at a boundary;
- `BoundaryReceipt` / `BoundaryEvidence`: what the producer or observer proved
  actually happened;
- `SemanticFinding`: a mismatch between the contract, evidence, authority, and
  current durable reality.

This split prevents `BoundaryContract` from becoming a god abstraction that
executes work, observes work, judges work, and repairs work.

The shared kernel also provides `ExecutionAttemptLedger`: an append-only record
of what each supported runtime actually attempted. It reuses Run Authority
grant/attempt/decision identities and references Maintenance transitions; it is
not a second authority kernel, lifecycle writer, queue, or workflow runtime.

Each attempt records immutable workflow/run/graph-revision, step/boundary,
invocation, attempt ordinal/id, parent/causal, runtime-adapter, code/config/
template-version, grant/decision, and actor/tool provenance. Events have an
idempotency key, per-attempt monotonic sequence, causal predecessor, durable
append position, and observed/occurred timestamps; clocks alone never establish
ordering. Required events cover started, completed, failed, retry scheduled,
suspended, resumed, and cancelled, plus external-effect intent/outcome and
persistence-failure/reconciliation where applicable.

Ledger events carry typed durable references for declared inputs, outputs and
results, verdicts, state deltas, artifacts, checkpoints/resume anchors, and
external effects. Small non-sensitive canonical payloads may be inline under a
versioned size/classification policy. Large or sensitive values must use a
durable object reference containing store identity/locator, content digest,
schema/media type, byte size, encryption/access scope, privacy class, retention
class, and availability state. A digest without retained retrievable bytes is
integrity evidence, not result preservation. Secrets are never ledger payloads.

Retention, redaction, and deletion are schema-governed. Ledger metadata and
causal tombstones remain audit-visible when policy permits payload expiry or
redaction; redaction records identify authority, scope, reason, and affected
references without leaking the removed value. Storage is tenant/workflow
scoped, encrypted, least-privilege, access-audited, and supports legal hold and
policy-driven disposal.

Attempt start is write-ahead and durable before user code or an external effect.
Internal state/result publication uses one transaction where the store permits,
or a durable outbox/prepare-commit protocol with deterministic reconciliation.
External effects use a durable pre-effect intent and idempotency/fencing key,
then a durable outcome or explicit unknown outcome. If start persistence fails,
dispatch fails closed. If terminal/result persistence fails, the runtime must
not report success: it exposes `persistence_failed` or `indeterminate`, retains
recoverable spool/outbox evidence where available, quarantines authority
advance, and reconciles explicitly. No ledger write is best-effort or silently
swallowed.

Contracts can declare:

- boundary identity and invocation identity;
- declared inputs;
- scratch outputs;
- canonical outputs;
- receipts;
- `phase_result`;
- expected state delta;
- expected history entry;
- transition decision, where authority increases;
- external effect refs;
- expected custody, for cloud/process boundaries;
- completion and in-progress witnesses;
- staleness policy;
- owner and repair domain.

Common boundary shapes should be reusable typed contract templates, not
bespoke one-off schemas per workflow. A template is a named required-field
profile over the generic boundary vocabulary, with optional extension fields
for domain-specific detail. The first standard templates should cover the
recurring workflow moves we already rely on: revision feedback, validation
results, artifact handoff/promotion, approval/waiver, external effects, and
execution custody.

Boundary producers emit receipts/evidence. Transition writers authorize
state/routing changes. Semantic health compares contracts, receipts, event
journals, warrants, state projections, and current durable reality. Repair,
cloud status, and the 6h auditor consume the same structured findings.

`state.json` is one projection of boundary reality, not the sole arbiter.

## Core Invariants

1. No boundary is considered complete from activity alone.
2. A model-filled template is never canonical until the harness validates and
   promotes it.
3. A canonical artifact without matching state/history/receipt/phase-result
   evidence is a semantic-health finding.
4. A state transition without required artifact/evidence/transition decision is
   a semantic-health finding.
5. Authority-increasing transitions require durable decisions with pinned
   evidence.
6. Child/reducer outputs never advance parent state directly.
7. The repair queue receives structured findings, not prompt-only hints.
8. Watchdog, repair-loop, status, and auditor must not maintain separate
   definitions of progress.
9. A cloud/process boundary is not healthy merely because some matching process
   exists; custody must be one of the explicitly accepted outcomes.
10. Producers write evidence; transition writers mutate lifecycle/routing;
    evaluators produce findings; repair attempts fixes; only evaluators clear
    findings.
11. Every attempt on a supported runtime has exactly one ordered ledger stream;
    retries are new linked attempts and resume preserves explicit lineage.
12. Hashes never substitute for retained result data or a durable retrievable
    reference governed by payload retention policy.
13. Ledger persistence failure is operator-, query-, status-, and audit-visible
    and prevents unsupported success/authority advance.
14. Supported consumers derive query, replay, audit, and conformance evidence
    from the same ledger; shadow compatibility data cannot claim conformance.

## Relationship To Existing Work

This initiative intentionally absorbs and aligns:

- `.megaplan/initiatives/legacy-loose-briefs/notes/structured-output-template-boundaries.md`
- `.megaplan/initiatives/boundary-turn-end-to-end`
- `.megaplan/initiatives/evidence-first-pipeline-semantics/briefs/m7-transition-validator-routing.md`
- cloud superfixer hardening from the prep-state incident.

It should not create a permanent parallel semantic-health registry. Early prep
checks may be bespoke as a bridge, but the long-term source of truth is the
boundary contract.

Run Authority is the sole initiative prerequisite. Megaplan Maintenance is an
independent adjacent architecture whose landed contracts are consumed when
present, not a WBC launch condition:

- Run Authority owns capability/dispatch grants, attempts, claims, decisions,
  quarantine, accepted execution authority, and sibling operational views.
- Megaplan Maintenance owns coherent observation envelopes, lifecycle mutation
  through `TransitionWriter`, mutation gates, repair/verification custody,
  truthful status semantics, and the deterministic six-hour feedback product.
- This initiative declares boundary expectations, records receipts/evidence,
  and derives semantic findings from those prerequisite-owned facts. It does not
  redefine their authority, lifecycle, queue, status, or custody contracts.

Compatibility JSON remains an observation, claim, or projection according to
Run Authority. A boundary contract may require or describe it during migration,
but may not promote it into authority.

## Execution Strategy

Launch only after the complete Run Authority chain is landed and proven by a
current completion manifest. Then:

1. Rebase on that completed authority baseline and reconcile declared boundaries with
   real producer outputs using read-only inventory and legacy/current fixtures.
2. Add durable findings and immediate verification through their existing
   observation, mutation-gate, repair-request, and verification contracts.
3. Add execution-custody and shared-consumer semantics through their canonical
   operational views; keep global rollout observe-only until parity is proven.
4. Cover chain, PR, repair, and auditor completion with pinned decision and
   observation evidence.
5. Generalize profiles/templates and adapt prerequisite-owned authority records
   without creating another transition writer.
6. Make the pinned `arnold.pipeline.native` runtime adapter mandatory, remove supported-surface
compatibility bypasses, and prove universal query/replay/audit/conformance.

The declared supported set is all `arnold.workflow` executions and the Megaplan
phase, reducer, chain/publication, cloud repair/verification, and auditor
adapters named by this initiative. Manual work wholly outside those runtimes,
third-party internal execution, and historical read-only data are out of scope;
external effects initiated by a supported attempt remain in scope. Temporary
C1-C5 migration exceptions require owner, reason, expiry/removal milestone, and
visible non-conformant status. C6 accepts none for a supported producer.

The first corrective milestone is the mutation gate. Its criteria are
machine-validated and fail closed: if current schemas, ownership, or fixtures
cannot be reconciled, the chain aborts with diagnostics rather than asking a
human to choose. Do not weaken guards, guess at stale paths, or let a boundary
evaluator become a new lifecycle owner.
