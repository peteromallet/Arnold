# North Star: Durable Session Knowledge Compiler

## Destination

Every managed execution and agent/subagent session automatically leaves behind
a durable, searchable, correction-friendly knowledge record. This includes
resident, workflow phase/step, implementation/review, retry/rework, nested,
repair, chain-transition, backend-neutral, and higher-workflow evidence. The
compiler operates at incremental and terminal boundaries, costs little enough
to run by default, and can fail asynchronously without changing, delaying, or
misreporting primary execution, acceptance, custody, result, or delivery.

The product is a knowledge compiler, not a lossy chat summary. Raw transcripts,
tool events, manifests, logs, commits, files, and test evidence remain primary.
Derived records make that evidence useful without replacing it.

## Load-bearing product invariants

1. **Evidence remains primary.** Every substantive derived claim links to the
   persisted source range and, where applicable, tool/file/commit/test evidence.
2. **Incremental work is durable and idempotent.** A successful checkpoint
   covers an immutable event/token range. Durable offsets advance atomically
   only after all required outputs validate and persist. Retries and duplicate
   triggers are harmless.
3. **Meaningful boundaries trigger compilation.** Compile after roughly
   100,000 newly persisted tokens and at terminal states including completed,
   failed, cancelled, and superseded. Idle compilation is an optional policy,
   disabled until its semantics and noise budget are proven.
4. **Compilation is harmlessly asynchronous.** Extraction or storage failure
   never changes the managed session's terminal state, blocks its delivery, or
   invents a success. Failure is visible, retryable, and does not advance the
   last-successful cursor.
5. **Outputs remain distinct.** Each checkpoint emits evidence-linked activity
   (what happened), reusable knowledge, paper-cut source observations, and
   improvement candidates. One output may link to another but must not collapse
   their different truth and lifecycle semantics.
6. **Claims say what kind of claim they are.** Records distinguish observed,
   performed, inferred, proposed, and unverified claims. A proposal never reads
   like a performed action; an inference never reads like direct evidence.
7. **History is append-only and correctable.** Immutable checkpoints coexist
   with rolling and terminal syntheses. Corrections supersede derived claims
   without rewriting source evidence or silently deleting prior versions.
8. **Promotion is cautious.** Session knowledge becomes project knowledge only
   through an explicit candidate/review path with repository, version, and
   commit applicability; contradiction detection; and stronger review for
   authoritative claims.
9. **Observations survive consolidation.** Repeated paper cuts may produce one
   deduplicated, prioritized backlog item, but every source observation and its
   evidence remains independently addressable.
10. **The normal UX is nearly invisible.** Automatic operation is the default.
    Agents additionally have lightweight `record-learning`, `record-friction`,
    `correct-summary`, `search-session-knowledge`, and `propose-promotion`
    surfaces that add intent without requiring manual bookkeeping.
11. **Lineage and time are explicit.** Stable workflow, epic/chain, milestone,
    plan, phase/step, attempt, and agent-run identities preserve parent and
    causal edges. Occurrence, persistence, capture, and ingestion times remain
    distinct; native source order and causality outrank wall-clock guesses.
12. **Authority stays outside.** Run Authority, WBC, workflow scheduling and
    acceptance, Custody, repair dispatch, and delivery retain their ownership.
    The compiler and its read-only reconciler may observe and derive but cannot
    grant, schedule, accept, retry, repair, transfer custody, or deliver. Logs
    and agent prose remain evidence rather than authority.

## Canonical derived records

- **Activity record:** goals, scope, actions actually performed, changed
  artifacts, commands/tests, results, failures, and unresolved work.
- **Reusable knowledge:** evidence-backed facts, decisions, techniques,
  constraints, and applicability that may help later work.
- **Paper-cut observation:** a source-preserving report of confusion, friction,
  workaround, reliability, performance/cost, discoverability, ambiguity, or a
  missing capability encountered in this session.
- **Improvement candidate:** a proposed change linked to one or more source
  observations, with impact, confidence, applicability, and status.

## Success measures

- Restart, duplicate-trigger, out-of-order, and partial-write tests demonstrate
  no skipped or double-counted source ranges.
- Terminal sessions always become eligible even below the token threshold.
- Compiler failures leave session completion/delivery unchanged and are
  observable and retryable.
- Every accepted derived claim resolves to durable evidence and a claim kind.
- Corrections, rolling/final synthesis, contradiction handling, and promotion
  preserve complete lineage.
- Backlog deduplication demonstrably preserves all source observations.
- End-to-end tests cover automatic and explicit agent UX across representative
  managed-session backends and a generated matrix covers every required
  producer, transition, execution role, and backend without silent omissions.
- Duplicate, concurrent, late, crash/restart, schema-evolution, and read-only
  reconciliation proofs rebuild equivalent projections from agent run through
  reviewed cross-epic knowledge without mutating source execution.

## Anti-scope

- Do not replace or compact away authoritative transcripts, tool events, logs,
  or manifests.
- Do not turn derived summaries into execution or run-authority state.
- Do not move scheduling, acceptance, custody, repair, reconciliation authority,
  or delivery into the compiler, or infer any of them from logs/PIDs/prose.
- Do not auto-promote authoritative project claims without review.
- Do not make compilation success a prerequisite for session completion or
  terminal reply delivery.
- Do not build a general document/RAG platform beyond the session and project
  knowledge needs defined here.
