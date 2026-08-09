# Managed Execution Observation and Knowledge Lineage

Status: accepted initiative architecture; implementation not started

Date: 2026-07-16

## Provenance and reconciliation

This decision curates the still-valid substance of
[the resident architecture research](../research/epic-wide-managed-agent-capture-architecture-20260716.md),
preserved verbatim with source SHA-256
\`a5e9a541101e210889e03df4f2d574b1c30a3fc2884a663bdc548b7dd8510553\`.
That research is evidence from its recorded baselines, not a claim about the
current runtime. Implementation must repeat its seam inventory against the
target revision before selecting authoritative producers.

This decision extends the existing three-sprint Durable Session Knowledge
Compiler. It does not create another initiative, authority ledger, queue,
database, service, or derived-record family.

## Decision

Use one versioned, append-only \`KnowledgeObservationEnvelope\`, idempotent
producer adapters, correctable projections, and a read-only reconciler for all
managed execution evidence. The compiler derives knowledge from authoritative
records but never becomes execution authority.

The required lineage is:

\`\`\`text
workflow run
  -> epic/chain run
  -> sprint/milestone run
  -> plan run
  -> phase/step
  -> attempt
  -> agent run
\`\`\`

Levels that do not apply remain explicitly \`not_applicable\`; missing evidence
is \`unknown(reason)\`. No adapter may infer identity or success from names,
paths, a latest pointer, timestamps, process state, log text, or agent prose.
Higher-level workflows and portfolio orchestrators layer above Megaplan through
the same optional parent-workflow fields and causal edges rather than a
Megaplan-specific schema fork.

## Ownership boundary

- Run Authority owns grants, fences, execution decisions, quarantine, and
  supported attempt authority.
- Workflow Boundary Contracts own supported-runtime attempt/effect evidence
  and conformance.
- Custody owns action targets, occurrences, leases, epochs, transfer, and
  reconciliation authority.
- Megaplan and any higher-level workflow own scheduling, routing, task/rework
  policy, acceptance, and chain/milestone progression.
- Resident delivery and other delivery systems retain delivery custody.
- The compiler owns only append-only observations, compilation checkpoints,
  the four derived record families, synthesis, corrections, contradictions,
  retrieval views, and promotion candidates.

Authority, scheduling, acceptance, custody, and delivery references are inputs
to the compiler, never powers it can mint or exercise. Logs, projections,
mutable status, PIDs, transcripts, tool output, and agent/model prose remain
evidence. They are not authoritative merely because they are recent or fluent.

The compiler must consume, not compete with, the
[WBC execution-attempt ledger](../../workflow-boundary-contracts/decisions/2026-07-11-kernel-execution-attempt-ledger.md)
and the
[composed Run Authority/WBC/Custody contract](../../custody-control-plane/decisions/single-authoritative-runtime-history.md).
Where those contracts are not operationally adopted, adapters record declared
legacy source priority and explicit gaps; they do not create replacement
authority.

## Generalized observation contract

Every envelope has a schema version, observation ID and kind, adapter identity
and version, deterministic idempotency key, source reference, privacy metadata,
and causal/correction edges. Additive fields cover:

| Scope | Stable identity and rule |
| --- | --- |
| Workflow | workflow kind, stable workflow-run ID, workflow definition/revision digest, optional parent workflow run |
| Initiative/epic | canonical initiative identity and intended revision; optional portfolio/parent epic |
| Chain | immutable chain-binding digest plus explicit chain-run ID and optional chain session; binding identifies inputs, run ID distinguishes reruns |
| Sprint/milestone | label/index, brief digest, milestone-attempt ID/ordinal, predecessor acceptance refs |
| Plan | stable plan ID, plan/run revision, initialization or plan-attempt ID, source-binding digest |
| Phase/step | logical boundary ID, phase/step name, contract/template version, invocation ID |
| Attempt | stable attempt ID/ordinal and kind; retry, rework, supersession, and prior-attempt causal refs |
| Agent run | runtime/custodian kind, stable agent-run ID, root and direct-parent IDs, launch idempotency key, role, backend/model/route provenance |
| Task/goal | immutable task/goal identity and revision; changed objective means a new revision |
| Evidence | source store/stream, native position unit, exact half-open range or immutable event/sequence, locator, digest, schema/media type, availability, gaps, and typed artifact/commit/test/verdict refs |
| Outcome | lifecycle outcome, semantic verdict, claimed result, and separate acceptance state with exact authority decision refs |
| Authority/custody | actor/tool and work-intent provenance, evidence scope, grant/fence/attempt, target/occurrence/lease/epoch, policy, acceptance, and delivery refs |
| Causality | parent, caused-by, retry-of, rework-of, corrects, supersedes, contradicts, and compiler-checkpoint refs |

The envelope distinguishes:

- \`occurred_at\`: when the source says the event happened;
- \`persisted_at\`: when the source durably recorded it;
- \`observed_at\` or \`captured_at\`: when an adapter saw it;
- \`ingested_at\`: when the compiler accepted the observation;
- optional terminal and authority-decision times.

All stored times are UTC. Ordering follows a source-native position/sequence
and explicit causal links. Timestamps express occurrence and capture latency;
they never invent a total order across concurrent streams.

The small generic observation vocabulary includes source registration, launch
reservation, attempt start, evidence/artifact/checkpoint persistence, outcome,
verdict, acceptance, retry/rework/supersession, transition, correction,
contradiction, persistence gap, and reconciliation. Phase names and agent
roles are values, not new schemas.

## Required execution coverage

Adapters and the acceptance matrix must cover without silent omission:

- resident-managed roots, delegated agents, continuations, and all nested
  subagents;
- every Megaplan phase/step worker, including prep, plan, critique, gate,
  revise, finalize, implementation/execute, and review;
- repeated iterations, retries, fallbacks, rework, supersession, cancellation,
  and late terminal results as distinct attempts;
- neutral managed commands and automatic repair, meta-repair, watchdog, and
  progress-auditor lifecycle evidence when the producer is authoritative for
  that fact, with derived/best-effort rows explicitly labelled corroboration;
- plan, milestone, chain, child-epic, and higher-level workflow transitions,
  including acceptance and handoff receipts;
- Hermes, Codex, Claude, and future execution backends through backend-neutral
  identities plus versioned adapters.

The compiler's extraction route remains the exact bounded
\`hermes:deepseek:deepseek-v4-pro\` route through provider \`direct\`. That is a
knowledge-policy choice and is independent of the execution backend whose
evidence is being compiled. No source backend may be excluded merely because
it is not the extraction backend.

## Capture and reconciliation

Use three layers:

1. A generic Store-backed append substrate validates envelopes, applies
   idempotency, preserves source cursors and scopes, and builds disposable
   projections.
2. Thin producer adapters map authoritative native journals, Store events,
   typed phase/worker results, manifests, result artifacts, acceptance
   receipts, resident audits, and authoritative custody/repair records.
3. Initiative-owned knowledge policy applies threshold/terminal triggers, the
   four record schemas, bounded extraction, synthesis/correction/search,
   promotion, paper-cut consolidation, privacy, and budgets.

The primary seam is a lifecycle subscriber/outbox after source persistence.
Post-step hooks may reduce latency but only trigger work after durable evidence
exists. A scheduled reconciler is strictly read-only: it scans source cursors
and durable artifacts, appends missing observations or explicit gaps, and never
changes source runs, retries work, grants authority, accepts results, transfers
custody, or infers status from prose/PIDs.

No model/network call, broad transcript read, semantic search, or cross-epic
aggregation occurs synchronously on the primary execution/delivery path.

## Append-only knowledge projections

All projections are rebuildable views over immutable observations:

\`\`\`text
source evidence
  -> normalized observations
  -> per-agent-run checkpoints
  -> attempt and phase/step synthesis
  -> plan synthesis
  -> sprint/milestone synthesis
  -> epic/chain synthesis
  -> workflow synthesis
  -> reviewed cross-epic promotion candidate
  -> reusable project/cross-epic knowledge
\`\`\`

Each level preserves exact inputs, gaps, claim kinds, acceptance state,
applicability, compiler/adapter versions, and supersession lineage. Retries and
rework remain addressable even when a correctable active view selects one
accepted attempt. A failed attempt may contain accepted learning; a completed
agent may produce rejected claims. Lifecycle outcome and knowledge acceptance
are separate.

Corrections append edges and new versions. Contradictions preserve both sides
and any adjudication. Cross-epic outputs are candidates until repository,
revision, path/environment applicability, evidence access, contradiction
review, and authority-proportionate review permit promotion.

## Replay, concurrency, failure, and evolution

- Observation idempotency derives from source kind/stream, immutable source
  position or event/range, source digest, and adapter major version.
- Checkpoint idempotency includes ordered observation/range identities,
  trigger, policy/schema/compiler generation, and bounded-context digest.
- Source persistence precedes enqueue. Failed enqueue or compilation never
  alters primary outcome/delivery or advances the last-successful cursor.
- Duplicate launch contracts rejoin one run; changed contracts and retries
  create new attempts. Process IDs, names, and wall-clock proximity are never
  identity.
- Late and out-of-order events retain native order and causal parents. A late
  superseded result stays evidence and cannot become active without a new
  authority decision.
- Concurrency is partitioned by native source stream/attempt. Cross-stream
  synthesis waits for declared join/acceptance boundaries or records named
  gaps; missing children cannot disappear silently.
- Version envelopes and adapters independently. Add optional fields, preserve
  source refs and adapter versions, rebuild via explicit upcasters, and make a
  new major version for breaking identity changes. Never reinterpret history
  through an implicit latest schema.

## Privacy and bounded context

Derived authorization is the intersection of referenced evidence scopes.
Prefer references to copied payloads. Never expose secrets, credentials, sealed
stdin, raw environments, private provider session IDs, or unredacted prompts in
generic metadata, metrics, or logs. Apply source retention, encryption,
redaction, deletion, and legal-hold rules. Retained tombstones preserve
causality and invalidate affected active views without exposing deleted data.

Treat transcript, tool, log, and model content as untrusted data. Extraction is
limited to the exact new range, bounded prior accepted context, directly
relevant lineage context, explicit gaps, and enforced size/token/cost limits.
Never bulk-inject an epic or cross-epic corpus.

## Three-sprint integration

- M1 delivers the envelope, time/identity/authority model, Store append and
  cursor/idempotency contract, and initial workflow/phase and managed-agent
  adapter families together with the unchanged four-record checkpoint.
- M2 builds correctable run-to-workflow projections, scoped retrieval, all five
  controls, and reviewed project/cross-epic promotion on that same append-only
  lifecycle.
- M3 completes the producer/backend matrix, read-only reconciliation,
  paper-cut/ticket integration, compatibility, privacy/operational controls,
  and non-mutating proof.

This does not reopen the archived eleven-sprint plan.

## Non-mutating proving strategy

Use a content-addressed, redacted, access-controlled offline replay of the
existing \`custody-control-plane\` epic. It supplies real chain/milestone
transitions, phase work, managed repair agents, retries, acceptance receipts,
and authority/custody boundaries without resuming or mutating that chain.

Register legacy sources honestly, preserving \`unknown\` and explicit gaps.
Replay normal, duplicate, restart, concurrent, late, and out-of-order delivery
and require content-equivalent projections. Prove every required producer and
backend row against a real seam. Shadow and canary operation remain later
implementation/operational gates; broad enablement, deployment, restart, soak,
and historical full-corpus backfill are not part of this documentation change.

## Explicitly outside the compiler

Execution authorization, scheduling, task/rework decisions, acceptance,
custody, repair dispatch, delivery, automatic semantic adjudication,
self-approved promotion, and autonomous code changes remain outside. Also
excluded are a standalone event bus, sidecar database, remote compiler service,
vector/general-RAG platform, global ontology, mandatory idle compilation,
organization-wide ranking, deployment, restart, and broad enablement.

## Implementation unknowns to resolve in M1

M1 must re-inventory WBC transactional adoption, a universal chain-run identity,
nested-parent propagation, source-native token accounting, authoritative
acceptance records for every producer, and current higher-workflow seams.
Unknowns stay explicit and fail closed for derivation while primary execution
and delivery remain unaffected.
