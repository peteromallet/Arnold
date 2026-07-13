# M5 — Artifact Recovery, Retention, Migration, and Backward Compatibility

## Outcome

Make the unified request/artifact lifecycle self-healing across resident restarts and continuous sweeps, enforce reference-based retention and safe garbage collection, and provide a reversible migration/cutover that preserves existing message, voice/image, manifest, scheduler/todo, and Discord delivery behavior without split-brain authority.

## Scope

Incident addition: startup and continuous reconciliation must cover accepted messages lacking requested execution custody or terminal intent, requested executions not yet converted into launch custody, and failed/cancelled/timed-out turns lacking pending, claimed, delivered, or dead-letter terminal outbox custody. Abandoned-turn-only recovery is insufficient.

In scope: startup reconciliation before ingress readiness and continuous bounded workers for accepted messages, ingest intents/claims, quarantine parts, promoted orphan blobs, missing/corrupt refs/blobs, incomplete materializations, launch/declaration/selection state, expired execution/outbox leases, unknown multipart outcomes, partial batches, dead letters, and compatibility projections; indexed/fenced idempotent recovery transitions; scanner/source-expiry retry budgets; reference expiry classes, legal/incident holds, Discord deletion privacy tombstones, reachability across inbound/run/declaration/preview/outbox/dead-letter/hold/legacy refs, `gc_eligible_at`, grace, second reachability check, deletion tombstones, and backup/object-version deletion documentation; low-risk sandboxed preview derivatives only; optional oversize serving only after its private authorization/revocation/audit design passes review; additive discovery/import/backfill/dual projection for existing message attachment flags, voice/audio/transcription, image `BlobStore` records, current/prior `arnold-resident-agent-run-v1` manifests, declaration sidecars, mutable delivery fields/cursors, and historical text-only sends; feature flags, readiness, shadow/divergence detection, cutover/rollback; constrained operator status/actions for retry, reconcile, approve explicit reply fallback, extend retention/hold, and purge.

Exercise every normal and repair owner: resident startup/runtime, ingest and outbox workers, completion reaper, scheduled reconciliation, VP todo/sweep handlers, repair/supervisor paths, legacy manifest scans, compatibility readers/writers, and service bootstrap/day-2 readiness. No path may repair files silently or establish a second artifact/delivery authority.

Out of scope: destructive legacy deletion, unrelated chain/workspace cleanup, broad store replacement, unrestricted previews/archive extraction, public hosting, or final production rollout.

## Locked decisions

- Startup reconciliation precedes attachment-capable ingress readiness; bounded degraded readiness is explicit and cannot silently dispatch work whose artifacts are unresolved.
- Continuous recovery is indexed, bounded, idempotent, fence-aware, safe under concurrent workers, and expressed as audited ledger transitions—not shell/file edits.
- A live artifact reference/outbox item/hold/legacy projection cannot lose its bytes. Blob deletion requires expiry/hold checks, complete reachability, grace, and a second reachability pass.
- Default configurable starting TTLs follow the design: unfinished quarantine 24h; rejected/infected restricted quarantine 7d where policy permits; conversation refs 30d after terminal; previews 7d or parent expiry; attempt receipts 180d without content; dead-letter refs 30d after resolution; orphan CAS grace 7d.
- Migration is additive, versioned, observable, reversible, and preserves existing voice/image/text/manifests. CAS/artifact ledger becomes authority only through explicit flags and divergence gates.
- Discord deletion shortens/revokes the scoped inbound ref via a privacy tombstone without rewriting provenance, subject to lawful holds.
- Preview/render/extraction uses disposable unprivileged resource-limited isolation with no credentials/network. Initial preview scope excludes Office, HTML, SVG, archives, and executable content.
- Rollback disables new ingest/declaration/multipart effects while retaining ledger/CAS custody and restoring text/legacy serving authority; rollback never deletes artifacts.

## Open questions for the plan

- Which legacy combinations deterministically import versus become visible `unknown`/manual reconciliation, especially mutable delivery fields and partial voice/image blobs?
- What startup time/work budget and degraded-readiness semantics prevent bypass while keeping the service operable under a large backlog?
- What exact flag sequence covers metadata-only, quarantine shadow, trusted inbound, declaration shadow, multipart canary, new authority, and rollback without dual-authority writes?
- What established resident content/legal/backup policy should override the proposed TTL defaults, and how is backup deletion truth reported?
- Is a private oversize download service already available with conversation-scoped auth, short expiry, revocation, and audit, or must M5 retain visible `oversize_retained` failures only?

## Constraints

Preserve unrelated active chains/workspaces and dirty work. Never use arbitrary remote shell or destructive cleanup. Do not submit private files to public scanners, expose public/signed URLs outside their authorization scope, or claim deletion while backups/object versions remain. Recovery queries and work batches must be bounded; repeated failure degrades visibly with status/alerts rather than infinite retry or attachment-free dispatch.

## Done criteria and acceptance evidence

- Seeded matrix covers every request/artifact boundary: accepted-only, ingest requested/claimed/partial/quarantined/scanned/promoted/orphan/ref-created/materialization-failed, launch/declaration/selection partials, ack/text/artifact batches pending/sending/expired/unknown/partial/dead-letter, terminal refs, expired refs, holds, missing/corrupt blobs, and legacy projections.
- Repeated concurrent startup/continuous/scheduler/todo/repair/reaper sweeps converge without duplicate execution/download/capture/send, stale commits, terminal regression, lost bytes, or silent mutation. Startup readiness is blocked/degraded exactly as policy states.
- Reconciliation proves every accepted inbound reaches one durable outcome class within policy SLA: execution custody, blocking clarification, or terminal delivery/dead letter. It repairs or pages on `failed && message_sent=false` and accepted messages with neither custody nor terminal intent.
- Fake-clock retention tests cover quarantine, accepted refs, derivatives, attempts, dead letters, holds, privacy tombstones, orphan grace, second reachability, backup-age reporting, deletion failures/retry, and restoration digest verification.
- GC retains any blob reachable from inbound, run, declaration, preview, outbox, unknown attempt, dead letter, hold, backup policy, or legacy projection; deletion records a tombstone and never races a new ref.
- Current/prior message, voice/transcription, image/blob, run manifest, sidecar, delivery-field, scheduler/todo, and text-only fixtures remain readable and receive deterministic authority/projection outcomes.
- Feature-flag tests prove old-only, metadata/shadow ingest, dual projection, restricted trusted attachment use, declaration shadow, multipart canary, new authority, rollback, and split-brain/divergence alerts without deletion.
- One constrained status/action surface shows safe request lifecycle plus ingest/scan/materialization/declaration/batch/receipt/expiry state and records authorized retry/reconcile/fallback/retention/purge events.

## Touchpoints

Expected areas: resident startup/runtime/readiness, artifact/ingest/outbox/recovery workers, scheduler and VP todo/sweep, completion reaper/repair tools, store migrations and GC, config/service bootstrap/day-2, status/hot context/observability, legacy projections, preview/oversize policy, and recovery/migration tests.

## Anti-scope

Do not remove legacy compatibility, destructively backfill/delete runtime data, garbage-collect by age alone, silently repair manifests/files, enable unsafe previews/public links, touch unrelated sessions, or bypass canonical operator commands.
