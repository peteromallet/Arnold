# M2 — Shared ledger, coherent evidence, and authority

## Outcome

Freeze and implement the common maintenance control-plane contracts: one append-only incident/maintenance ledger, coherent observation envelopes, separate projections, occurrence-scoped identity, and canonical transition/repair authority. Adopt them in shadow/warn mode before any enforcement.

## Scope (about one sprint; no more than two weeks)

In scope: strict versioned `ObservationEnvelope`, `MaintenanceEvent`, `DetectionEvent`, `RepairRequest/Attempt`, `VerificationEvent`, `EfficiencyAnalysis`, and `AuditReport` contracts; immutable evidence references and digests; source versions before/after reads; bounded tearing retry; `PARTIAL`/`INCOHERENT` states; environment/tenant/run/chain/plan/stage/model/profile/attempt identities; event-time window and watermark fields; operational occurrence versus root-cause cluster identity; append idempotency; dead letters and replay; projection sequence/digest freshness; shadow consumers for watchdog/status/dispatch/chain guards; TransitionWriter enforcement seams; direct-write inventory and tests.

Out of scope: enabling enforcement or autonomy; changing Run Authority decision semantics; six-hour repair policy; daily baselines; production store migration without an approved retention/backend decision.

## Locked decisions

- Evidence precedence is: Run Authority grants/attempts/accepted decisions/fences/quarantine; WBC/kernel attempt events when available; maintenance observations/transitions; plan events/receipts/artifact digests/accepted gate-finalize results; chain and repair-custody events; resident/cloud snapshots and heartbeats; mutable state/status projections last.
- One closed, versioned ledger event carries identity, event/observation/window time, watermark/lateness, fingerprint/occurrence/cluster, confidence/classifier version, immutable evidence, impact, custody/lease/fence, causality/recurrence, and resolution proof.
- At least three reducers advance independently: `operational_custody`, `verification`, and `efficiency_analysis`. A daily classification cannot overwrite active repair state.
- Incoherent or stale envelopes cannot produce terminal or dispatchable state.
- Signature groups recurrences; occurrence identity controls dedupe, leases, and bounded budgets.
- Run Authority remains the accepted-attempt/decision authority. Repair actors propose transitions; canonical TransitionWriter/repair custody owns mutation.
- Unknown schema fields are rejected except explicit extension maps.

## Open questions / human gate

Before enforcement, approve the durable event-store backend and retention, production identity fields, maximum unexplained legacy/canonical drift, watermark lateness allowance, and ledger access/PII policy. Shadow implementation does not require those answers to enable mutation.

## Done criteria and handoff

- Fault-injected reads return one coherent envelope or typed `INCOHERENT`, never mixed truth.
- Ledger append/replay is idempotent; projection lag/digest mismatch is explicit; failed append yields a replayable dead letter.
- Same-occurrence events dedupe, while verified recurrence creates a causally linked new occurrence and budget.
- Direct plan/chain writes by maintenance actors fail authority tests; every accepted transition has actor, immutable precondition envelope, idempotency key, fence, and event.
- Shadow comparison exposes denominators and no unexplained bucket; missing/cross-environment evidence cannot become green.
- Handoff to M3: frozen schemas, precedence table, projection APIs, compatibility adapters, replay fixtures, and authority tests.

## Parallelism and anti-scope

Envelope reads, validators, classifiers, and compatibility comparisons may run in parallel over immutable inputs. Ledger ordering per stream, custody claims, transitions, and projection commits are serialized/fenced. Do not create a second ledger or mutate any paused/in-flight plan or chain during migration.
