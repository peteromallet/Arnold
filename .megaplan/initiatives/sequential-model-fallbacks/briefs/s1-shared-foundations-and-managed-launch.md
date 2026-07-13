---
type: brief
slug: s1-shared-foundations-and-managed-launch
title: Shared Resolution, Fallback, Custody, and Managed-Launch Foundations
epic: sequential-model-fallbacks
created_at: '2026-07-11'
---

# Sprint 1 - Shared Foundations and Managed Launch

## Outcome and delivery contract

In days 1-6, establish the shared managed-agent substrate used by Megaplan workers, resident roots, and eligible descendants: one versioned D1-D10 resolver, one ordered fail-closed fallback kernel, complete immutable root/task custody with additive schemas, and a typed durable child-launch/result foundation. Preserve current scalar routes, `partnered-5` arrays, four-value `AgentMode` unpacking, and conservative resident-v1/legacy reads.

Overall plan difficulty is **5/5**; use **partnered-5/full/high @codex +prep**. The sprint owns several public and restart-sensitive contracts, but execution is deliberately parallel rather than a serial replay of former M1-M4.

## Parallel execution topology

Start all four tracks from the same golden-fixture baseline:

- **Track A - resolver/profile:** inventory Megaplan phase/tier/prep/execute/fanout and resident root/child routing; implement normalized `ManagedTaskSpec`, pure versioned `ResolvedManagedProfile`, D1-D10 table, D5 default/explicit/risk-promotion semantics, precedence, profile revisioning, narrowing-ready ceilings, and canonical resolution receipts.
- **Track B - fallback safety:** finish `FallbackSpecChain`, native TOML arrays, compact JSON string-boundary encoding, scalar decoding, policy rewrites, preflight/state/resume/fanout preservation, provider-family identity, canonical backend error taxonomy, root attempt/visited inputs, deterministic decisions, and affirmative `no_mutation` gating.
- **Track C - custody/schema:** implement content-addressed complete root/child task storage and hashes; immutable root/run/parent ids, ancestry, depth/ordinal, provenance and budget references; strict canonical serialization; managed-run and structured child-result schemas; atomic writes; conservative v1 projections and migration fixtures.
- **Track D - managed launch foundation:** concurrently inventory every resident, Megaplan fanout, repair, scheduler, VP-todo, CLI/tool, compatibility, and shell bypass; define the typed launch request, idempotency/fencing and result state machines, cancellation/recovery behavior, and managed-vs-unmanaged boundary. Integrate spawn/result handling after the shared Track A-C revisions freeze.

The only intra-sprint serialization is an early **contract convergence gate** that freezes canonical spec identity, schema/receipt revisions, immutable references, attempt/mutation enums, and launcher inputs. Tracks A-C otherwise proceed concurrently; Track D's inventory and state-machine tests do not wait for that gate, and only its final integration consumes the frozen interfaces.

## Locked contracts and scope

- Resolution is transport-neutral and pure. Inputs include normalized task specification, requested D1-D10 difficulty, kind/risk, named profile or explicit root override, inherited ceilings, root budget state, profile/catalog revision, and explicit operator policy. Environment discovery may reject but never silently reroute.
- D1-D10 accepts integers only; booleans, floats, and out-of-range values fail. Missing difficulty becomes D5 with `default_d5`; explicit D5 remains distinguishable. Routine D5 selects the middle route and medium reasoning; deterministic promotion preserves requested D5 and records its rule.
- Precedence is system ceiling -> root/operator policy -> inherited parent ceiling -> named profile revision -> task-kind/risk rule -> explicit narrowing override -> defaults. Production-required provider/catalog and numeric ceilings fail closed when absent.
- Receipts include requested/effective difficulty, task/risk inputs, profile/catalog revision, ordered models, reasoning, tools, sandbox, time/token/cost/attempt/tree ceilings, applied defaults/overrides/reasons, and canonical hash. Scalar consumers retain their current selected route and identity.
- Native arrays and canonical compact JSON bridging remain the ordered-chain representation. Arrays survive phase/tier/prep, cloud/chain, state/resume, preflight, fanout cloning, routing identity, receipts, and additive observability without flattening.
- One classifier covers worker, fanout, resident root, and managed child adapters. Fallback is only for policy-allowed availability or independent-provider operational failures; never for quality, semantic, schema, test, evidence, gate, review, blocked, unsupported-config, or malformed-output failures.
- Advancing requires affirmative pre-mutation evidence. Output bytes, accepted structured output, tool or filesystem/tree changes, checkpoints, external sends, timeout/kill ambiguity, or missing evidence fail closed. Explicit chains suppress ambient fallback. Execute/loop-execute may advance only through the same affirmative gate; otherwise return explicit unsafe/fail-closed evidence.
- Complete root and child task bytes are content addressed with SHA-256, media/encoding, length, schema, and immutable references. Previews, argv, mutable paths, filenames, and conversation windows are never custody authority.
- Every run carries immutable root id, run id, parent id, ordered ancestry, depth, child ordinal, root budget id, resolution/fallback references, and unchanged request/Discord provenance. The Discord corrective initiative owns creation and transport handling of that envelope.
- Structured child results contain terminal status, summary, typed outputs/artifacts/evidence, usage/cost/timing, fallback attempts/error class, and canonical hash. Prose/stdout is not result authority. Children target parent/root custody and cannot authorize user delivery.
- `ManagedChildLaunchRequest` accepts verified parent/root context, complete child task bytes/ref, D1-D10/kind, narrowing ceilings, idempotency key, and expected contract revisions. Reserve identity/budget and persist intent/fence before spawn; commit the child manifest and structured result durably; stale workers and duplicate launches/results converge.
- Resident roots and managed descendants use one launch service/tool. Supported Megaplan fanout and compatibility callers converge on it where applicable. Generic shell processes cannot claim managed ancestry, budgets, receipts, results, or delivery authority.

## Compatibility and migration foundation

Golden tests precede changes for scalar profile/phase/tier/prep/override routes, selected model/session/cache identity, persisted resume, preflight, fanout pack/unpack, and `AgentMode.__iter__`. Introduce additive managed-run/result schemas with strict v1/v2 readers and fixtures. Legacy `arnold-resident-agent-run-v1` and Megaplan state can project conservatively to a root-only/incomplete-custody view; missing bytes, ceilings, or provenance never get fabricated or widened. Full backfill, cutover, rollback, and split-authority removal are Sprint 2 work.

## Required handoff evidence

Produce coherent, versioned artifacts (exact placement may follow existing repository conventions):

- `docs/managed-agents/resolution-contract-v1.md` and machine-readable D1-D10/scalar golden fixtures;
- `docs/managed-agents/fallback-safety-contract-v1.md` and backend-neutral classification/mutation fixtures;
- `docs/managed-agents/custody-and-schema-v2.md`, checked schemas/models, v1/v2 fixtures, and migration matrix;
- `docs/managed-agents/child-launch-api-v1.md`, caller/bypass inventory, and launcher/result state-machine evidence.

Sprint 2 must consume the exact schema/fixture revisions and may not introduce dispatcher-specific substitutes.

## Acceptance evidence

- Identical normalized fixtures produce byte-stable resolver receipts across Megaplan and resident adapters for every D1-D10 value, missing/explicit/promoted D5, invalid inputs, overrides, and profile revisions.
- Existing scalar routes and public/persisted identities remain unchanged; `partnered-5` arrays round-trip through every named serialization and routing boundary; `AgentMode` still unpacks to four values.
- All adapters produce identical fallback class/decision/reason for retryable availability, independent/same provider families, exhaustion, attempt/visited denial, and non-retryable classes.
- Deterministic tests prove no fallback after each output/tool/file/checkpoint/result/send mutation signal or unknown timeout/restart state, and no ambient bypass of an explicit chain.
- Tamper tests reject truncated, substituted, reordered, or mutated root/child tasks, ancestry/provenance, and results. A depth-two fixture resolves the exact complete root bytes/hash without prompt or path authority.
- Launch replay converges on one logical child, stale workers cannot commit, structured results survive restart, unmanaged processes cannot claim managed status, and children cannot send/enqueue user or Discord completion.
- Focused resolver, fallback, profile/state/preflight, custody/schema, resident launcher, and compatibility suites pass with deterministic evidence rather than sleeps or live-provider dependence.

## Touchpoints

- `arnold_pipelines/megaplan/profiles/`, profile policy/tier/prep resolution, `_core` worker/fanout/dispatch, `fallback_chains.py`, state/preflight/cloud/chain/receipts/status
- resident profile/subagent/subagent-worker/provenance/config/runtime/scheduler/recovery surfaces
- Megaplan brief/task artifacts and a narrowly shared content-addressed custody/managed-run store
- managed-agent fixtures and compatibility tests

## Anti-scope and safety gates

Do not rename profiles, flatten fallback arrays, infer deployment spend limits, retry for quality, infer no mutation from process exit, fabricate legacy custody, parse results/delivery from prose, create a second resident launcher, grant shell processes managed status, or change Discord lifecycle/outbox/attachment/provider behavior. Do not launch or resume a chain or cloud run while authoring/executing this contract.
