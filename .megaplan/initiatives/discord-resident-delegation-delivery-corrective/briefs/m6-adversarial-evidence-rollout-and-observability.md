# M6 — Adversarial Artifact Evidence, Observability, and Rollout

## Outcome

Close the lifecycle and attachment design with adversarial end-to-end proof across every normal, repair, scheduler, todo, recovery, and compatibility path; operational observability and constrained runbooks; and a canary-ready staged rollout whose request/artifact custody, security boundary, delivery, retry, retention, and rollback status can be trusted without fragmented file inspection.

## Scope

In scope: deterministic contract/storage/security/fault/restart/integration suite covering the entire canonical attachment acceptance matrix; concurrent duplicate and burst stress; process death at every database/filesystem/network boundary; hostile inbound URL/name/type/size/content/scanner/parser fixtures; cross-scope access and restricted-run isolation; explicit declaration/path/TOCTOU/fence/DLP cases; Discord multipart construction, packing, receipts, rate limits, unknown reconciliation, partial batches, oversize and deleted-target behavior; startup/continuous recovery, migration flags, legacy voice/image/manifest/text compatibility, privacy tombstones, retention/holds/GC/backup reporting; exact-origin acknowledgement/text/artifact E2E assertions through normal conversation, VibeComfy, Megaplan, AgentBox, repair/supervisor, scheduler, VP todo/sweep, completion reaper, restart replay, and legacy compatibility entry points; metrics/traces/status/alerts; threat model, operator runbook, feature gates, canary/soak/rollback and post-cutover verification. Fix defects revealed within initiative scope.

Out of scope: unrelated resident features, destructive legacy cleanup, broad performance tuning, arbitrary hostile-file enablement without the restricted runner, public hosting, or irreversible production actions.

## Locked decisions

- Evidence asserts persisted ledger/CAS/ref/outbox/receipt/retention state plus visible transport effects; no sleep, PID, final-prose, mutable cursor, or local-path guess is correctness evidence.
- Every launch/send/recovery entry point must converge on the same ledger, artifact broker, restricted run envelope, declaration adapter, and artifact-aware outbox. A bypass is a release blocker, not accepted compatibility.
- Rollout order is metadata-only → quarantine shadow → trusted-principal inbound → declaration shadow → restricted trusted multipart canary → broader enablement. Each gate has quantitative prerequisites and rollback.
- Canary requires healthy private scanners, storage headroom, restricted attachment execution or explicit trusted-principal/low-risk-type limits, retention jobs, dashboards/alerts, and operator recovery. Malware scanning alone never opens the gate.
- Rollback stops new attachment effects while retaining custody/evidence and compatible text delivery. No rollback or test deletes unrelated/legacy data.
- Operational views derive from the unified ledger and use non-secret bounded-cardinality fields. Unknown/partial/dead-letter/legacy/divergent states are explicit.
- Exactly-once Discord delivery is claimed only to the extent provider receipts/Gateway/nonce evidence supports; unresolved ambiguity remains visible.

## Open questions for the plan

- Which deterministic Discord/provider faults need extensions to existing fakes versus an isolated HTTP/Gateway harness?
- What canary principals/types, soak windows, storage/scanner/recovery thresholds, and page-vs-warn policies fit the existing traffic/risk envelope?
- Which restricted-run controls can be asserted mechanically in CI/deployment readiness, and which require an operator evidence artifact?
- Which broader suites are the proportional backstop for all touched resident, AgentBox, cloud-service, scheduler/todo, and storage surfaces?

## Constraints

Never emit message/file contents, signed URLs, tokens, full paths, filenames as labels, full digests, or uncontrolled IDs/MIME subtypes into metrics/logs. Use fake clocks and deterministic IDs. Preserve service availability, authorization, existing text/voice/image behavior, M1 completion, unrelated dirty work, and active cloud chains. Unverifiable provider/isolation/backup semantics must remain explicit gates or caveats.

## Done criteria and acceptance evidence

- Contract/CAS suite proves realm-scoped deduplication with distinct provenance/ACL refs; immutable origin/digest/scope; no ref-before-bytes; crash-safe quarantine/promotion/ref ordering; corruption/missing-byte detection; and reachability-safe GC across every reference class.
- Inbound suite proves authorization causes zero unauthorized fetches; hostile URL/redirect/size/name/MIME/polyglot/malware/scanner/archive/dimension/page/encryption/quota cases fail safely; every intent/stream/fsync/scan/promotion/ref/materialization kill point converges; expired sources and mixed/attachment-only bursts never become silent attachment-free runs.
- Run/declaration suite proves read-only request projections and cross-scope denial; common restricted launcher use by every named profile/path; immediate source-stable capture; traversal/symlink/special/hard-link/TOCTOU rejection; declaration idempotency/order; stale-fence denial; no secret leakage; no auto-selection from discovery/prose; and visible legacy-sidecar behavior.
- Outbox/provider suite proves exact multipart parts/metadata/reply/nonce, deterministic count+byte packing, immutable bytes, text-only compatibility, correct 4xx/429/5xx/pre-send/unknown handling, Gateway/history reconciliation, kill-after-accept recovery, no committed-batch resend, partial/dead-letter truth, receipt mismatch rejection, oversize policy, and no silent retarget.
- Recovery/migration/retention suite proves startup readiness, repeated concurrent sweep convergence, all normal/repair/scheduler/todo/reaper/legacy paths, feature-flag authority/rollback/divergence, deletion tombstones, holds, preview lineage, two-pass GC, backup caveats, and constrained audited operator actions.
- Metrics/traces/status expose request/turn/execution/artifact/declaration/group/batch/attempt/fence/provider IDs only where appropriate, safe outcome/MIME-family/byte/duration/policy fields, backlog/age/retry/unknown/partial/dead-letter/storage/GC gauges, and no forbidden data/cardinality. Alerts cover scanner outage, storage watermark, missing blobs, accepted-without-custody-or-terminal-intent, `failed && message_sent=false` without outbox custody, timeout-before-launch, unknown/partial age, dead letters, migration divergence, and GC/recovery lag.
- Rollout/runbook documents capability/readiness checks, flags, canary population, quantitative soak gates, operator retry/reconcile/fallback/hold/purge, privacy/retention, rollback preserving custody, and post-cutover proof. A dry-run/canary evidence artifact records exact commands/results where permitted.
- Focused and proportional broader suites pass, and final review maps executable evidence to every North Star invariant, supplied audit finding, canonical attachment-design acceptance case, and every normal/repair/scheduler/todo/compatibility route.

## Touchpoints

Expected areas: resident contract/fault/security/integration tests and Discord fakes; all M2–M5 implementation surfaces; normal/profile/repair/scheduler/todo/reaper/legacy callers; observability/status/hot-context and service readiness; operator docs/runbooks; migration/retention/rollout evidence.

## Anti-scope

Do not claim safety or exactly-once semantics beyond evidence, waive the restricted execution gate, hide unknown/partial outcomes, use flaky timing, auto-execute/unpack hostile content, perform destructive migration/GC, or alter unrelated cloud sessions/workspaces.
