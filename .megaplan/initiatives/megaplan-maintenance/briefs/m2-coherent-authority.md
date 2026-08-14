# M2 — Coherent maintenance observations and authority joins

## Outcome

Freeze and implement the Maintenance-owned observation and join contracts over the accepted Run Authority, WBC, Custody, and Native Parity sources. Extend the existing append-only incident ledger for Maintenance events and immutable references; do not create an omnibus ledger, a second WBC/attempt ledger, a second completion kernel, or a transition writer. Adopt the joins in shadow/warn mode before any enforcement.

## Scope (about one sprint; no more than two weeks)

In scope: strict versioned `ObservationEnvelope` and Maintenance-owned `MaintenanceEvent`, `DetectionEvent`, `EfficiencyAnalysis`, and `AuditReport` contracts; immutable references/digests/cursors to owner records; source versions before/after reads; bounded tearing retry; `PARTIAL`/`UNKNOWN`/`INCOHERENT` states; environment/tenant/run/chain/plan/stage/model/profile/attempt identities; event-time window and watermark fields; operational occurrence versus root-cause cluster identity; append idempotency for the existing incident ledger; dead letters and replay of Maintenance events; projection sequence/digest freshness; and shadow consumers for watchdog/status/auditor/dispatch/chain guards. Read adapters must consume the exact M6A WBC `AttemptLedgerStore`/query API, M7 Custody lease/action-validator interfaces, Run Authority current-source view, M11 conformance evidence, and Native Parity C1/C2/S1/S2R manifests without copying their records.

Out of scope: enabling enforcement or autonomy; changing Run Authority decision semantics; implementing the M6A WBC attempt/effect store, outbox, payload policy, or migrations; implementing M7 controlled writers, leases, epochs, action validation, repair receipts, or TransitionWriter enforcement; implementing M8–M11 producer adoption, recovery/effect policy, or conformance retirement; implementing C1/C2 completion semantics or S1/S2R Native runtime primitives; six-hour repair policy; daily baselines; and any new ledger, authority store, completion engine, queue, validator, lease system, or transition writer.

## Locked decisions

- Evidence precedence is: Run Authority grants/attempts/accepted decisions/fences/quarantine; WBC/kernel attempt events when available; maintenance observations/transitions; plan events/receipts/artifact digests/accepted gate-finalize results; chain and repair-custody events; resident/cloud snapshots and heartbeats; mutable state/status projections last.
- The existing Maintenance incident ledger carries closed, versioned Maintenance events with identity, event/observation/window time, watermark/lateness, fingerprint/occurrence/cluster, confidence/classifier version, immutable evidence references, impact, custody/lease/fence references, causality/recurrence, and resolution-proof references. Owner-specific WBC, Custody, Run Authority, and Native histories remain canonical and are never copied into an omnibus ledger.
- At least three reducers advance independently: `operational_custody`, `verification`, and `efficiency_analysis`. A daily classification cannot overwrite active repair state.
- Incoherent or stale envelopes cannot produce terminal or dispatchable state.
- Signature groups recurrences; occurrence identity controls dedupe, leases, and bounded budgets.
- Run Authority remains the accepted-attempt/decision authority. Repair actors propose transitions; the canonical lifecycle `write_plan_state` seam and its TransitionWriter policy, together with repair custody, own mutation. M2 does not claim that `TransitionWriter` is the sole physical `state.json` writer until the M7 enforcement handoff proves that boundary.
- M6A–M11 and Native Parity C1/C2/S1/S2R contracts are consumed, not locally implemented. Package placement stays under `arnold_pipelines/megaplan`; neutral `arnold.*` seams are consumed one way and no generic package receives Megaplan policy.
- Unknown schema fields are rejected except explicit extension maps.

## Open questions / human gate

Before enforcement, approve the durable event-store backend and retention, production identity fields, maximum unexplained legacy/canonical drift, watermark lateness allowance, and ledger access/PII policy. Record the accepted M6A/M7/M10/M11 and C1/C2/S1/S2R handoff identities, including WBC store incarnation/restore/high-water coordinates.

## Done criteria and handoff

- Fault-injected reads return one coherent envelope or typed `INCOHERENT`, never mixed truth.
- Existing-ledger Maintenance append/replay is idempotent; projection lag/digest mismatch is explicit; failed append yields a replayable dead letter; no owner-specific ledger or authority record is duplicated.
- Same-occurrence events dedupe, while verified recurrence creates a causally linked new occurrence and budget.
- Direct plan/chain writes by maintenance actors fail authority tests and route to the M7 controlled-writer inventory; M2 records the bypass and consumer contract but does not implement a second writer or replace `write_plan_state`/TransitionWriter.
- Shadow comparison exposes denominators and no unexplained bucket; missing/cross-environment evidence cannot become green.
- Handoff to M3: frozen observation schemas, precedence table, owner-specific read adapters, projection APIs, compatibility adapters, replay fixtures, and proof that M3 can consume accepted M7/M10/M11/C1/C2 evidence without creating a custody or verification substrate.

## Parallelism and anti-scope

Envelope reads, validators, classifiers, and compatibility comparisons may run in parallel over immutable inputs. Ledger ordering per stream, custody claims, transitions, and projection commits are serialized/fenced. Do not create a second ledger or mutate any paused/in-flight plan or chain during migration.
