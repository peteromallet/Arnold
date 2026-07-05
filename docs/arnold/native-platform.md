# Native Platform Production Posture

This page separates the production-covered platform contract from local-only
developer behavior for the M6 native platform. Product workflows, including
Megaplan, own routing, loop exits, execute/review decisions, model choices, and
domain policy. The platform owns durable execution, security mediation,
reconcile, leases, audit, and operator controls.

## Coverage Matrix

| Area | Production-covered behavior | Local-only behavior | Production bypass rule |
| --- | --- | --- | --- |
| Reconcile | Resume and expired-lease takeover run `arnold.pipeline.native.reconcile` before mutation; dirty unknown worktrees, in-progress git operations, and unproven idempotent effects block. | Unit tests may feed deterministic fake `ReconcileDecision` values instead of probing a real repo. | Do not continue a resumed or takeover run until reconcile returns `execute`, `continue_owned`, or `skip`. |
| Idempotency | Brokered side effects carry action IDs/effect refs and reconcile metadata so already-applied file, branch, and commit effects can be skipped rather than repeated. | Local fakes may model idempotency with in-memory refs. | Do not replay protected side effects from stale process memory alone. |
| Broker | Covered git and LLM-provider actions are evaluated through the security broker; broker mode fails closed when unreachable. | Unconfigured local runs may use fallback policy for development-only commands. | Do not set raw provider or git credentials in agent-visible production environments. |
| Packs | Shared packs are package resources and workflow inputs; product code decides which pack step runs. | Tests may use temporary package-like resource folders. | Do not replace pack loading with checkout-only paths in installed validation. |
| DB durability | Durable store rows, operation records, lease records, and audit refs are the production authority across process death. | File stores and temporary JSON state are acceptable for deterministic conformance. | Do not treat local memory as durable production state. |
| Leases | One project/worktree run holds a lease token, heartbeat, expiry, and terminal/quarantine state; expired takeover requires reconcile and resume trust. | Local tests use `FileProjectLeaseStore` and fixed clocks. | Do not mutate a leased worktree without a valid token or reconciled takeover decision. |
| Audit lookup | Provider and git effects expose sanitized audit refs that can be joined by run ID and step path. | Fakes may store audit refs in process for assertions. | Do not put secret values in audit refs, summaries, metadata, or command echoes. |
| Approval gates | Force pushes, branch deletes, PR merges, credential escalation, and declared destructive actions require broker approval or an explicit suspension/resume route. | Auto-approval is allowed only inside test fixtures with fake policy. | Do not bypass broker approval by invoking shell/git helpers directly. |
| Cancellation | Cancellation is a terminal platform outcome for a lease/run and must persist before workers stop mutating project state. | Local tests may simulate cancellation by transitioning the lease. | Do not continue execution after a persisted cancellation state. |
| Rollout | New platform behavior rolls through local conformance, installed-package conformance, canary, then operator-enabled production. | Developers may run focused suites against a checkout. | Do not promote canary-only or local-only paths as production-covered. |
| Rollback | Rollback disables new admission and drains or cancels leased runs before reverting code or config. | Local rollback may delete temporary state. | Do not roll back by deleting durable state or skipping audit retention. |

## Authority Boundaries

The platform substrate is deliberately not a second semantic owner. It may
enforce lease, reconcile, audit, broker, durability, cancellation, and approval
contracts. It must not decide Megaplan product routing, gate outcomes,
execute/review loop exits, prompt/model routing, or task satisfaction. Those
decisions remain in the product workflow source and handlers.

## Installed Package Rule

Production evidence must work from the installed package, not only from the
checkout. Tests that need source, docs, handlers, or fixtures should resolve
resources through `importlib.resources` when a package resource exists and use
checkout paths only for source-tree-only negative checks such as stale
`arnold/pipelines/megaplan` path guards.

## Design-Doc Reconciliation

Every deferred or out-of-scope design item from the native representation,
composition, and persistence handoff docs is classified here so platform
rollout does not turn an open design question into an implicit production
claim.

| Item | Final classification | Proof or owner |
| --- | --- | --- |
| Canonical Megaplan authored source must be `.pypeline`, not `workflow.py` semantics. | Delivered by composition. | `arnold_pipelines/megaplan/workflows/workflow.pypeline`; `workflow.py` is compatibility glue verified by installed-source reconciliation. |
| Stale dot-path references under `arnold/pipelines/megaplan`. | Delivered by completion and composition. | Source-path reconciliation keeps live paths under `arnold_pipelines/megaplan` and preserves stale-path negative checks. |
| Platform must not become a hidden owner of product routing, loop exits, model routing, execute/review decisions, or task satisfaction. | Delivered by platform. | Platform E2E and chain/PR conformance assert substrate metadata never owns those product decisions. |
| Durable suspension, approval, resume, and cancellation across process death. | Delivered by platform for local conformance; production rollout requires backend/operator setup. | `tests/arnold/conformance/test_platform_e2e.py`; operator prerequisite in `docs/arnold/operations.md`. |
| Credential broker coverage for protected git and provider proxy paths. | Delivered by platform where covered; intentionally deferred for uncovered provider classes. | `docs/arnold/security.md`; downstream owner: platform security for any provider not listed in broker coverage. |
| DBOS as the native persistence backend. | Rejected for M6. | `docs/arnold/native-persistence-backend-decision.md` rejects output-cache replay until Arnold has an explicit cached-output policy. |
| File backend as production durability proof. | Intentionally deferred. | File backend is local-only conformance; downstream owner: platform operations to provision Postgres before production admission. |
| Fleet-wide rollout beyond canary. | Intentionally deferred to operator decision. | Rollout checklist and decision record in `docs/arnold/operations.md`; sign-off is outside this automated harness. |
| Full final native-representation closeout report, YAML ledger, proof map, and manifest. | Deferred to later batch. | Owner: M6 final ledger tasks; this batch only updates docs and conformance tests. |

### Persistence-Backend Risk Classification

| Risk | Classification | Proof or owner |
| --- | --- | --- |
| Connection pool exhaustion under concurrent native runs. | Intentionally deferred production-scale risk. | Owner: platform operations; canary must set pool limits and monitor saturation before fleet rollout. |
| Large trace artifacts exceeding `jsonb` practical limits. | Intentionally deferred production-scale risk. | Owner: native persistence; proof required from compound-run trace-size telemetry before large-fleet enablement. |
| DBOS output cache leaking into replay semantics. | Rejected for M6. | DBOS remains disabled by the persistence decision record until cached replay becomes an explicit policy with conformance. |
| Persistence becoming hidden semantic owner. | Delivered by platform and composition. | Structural, source-path, anti-wrapper, and platform substrate tests prove persistence consumes canonical source decisions. |
| Sequence gaps in ordered events. | Delivered by persistence design. | Monotonic uniqueness, not gaplessness, is the production invariant in the persistence decision record. |

## Operator Decision Records

| Decision | M6 position | Production prerequisite |
| --- | --- | --- |
| DB backend | Raw Postgres is the production DB backend; file storage is local-only. | Apply migrations, configure backups, set pool limits, and prove restore/reconcile before admitting production runs. |
| Broker coverage | Protected git operations and covered provider proxy paths use broker-first enforcement. | Configure branch policy, broker secret store, provider proxy base URLs, and approval routing; uncovered provider classes stay out of production coverage. |
| Rollout mode | Canary first, then explicit operator enablement. | Local conformance, installed-wheel conformance, canary audit refs, cancellation proof, and signed rollout record. |
