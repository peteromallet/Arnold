# Unfinished-work custody ledger

This is the mandatory handoff from the bounded Critique Ledger v3 canary into
the post-relaunch completion epic. An item leaves this ledger only through an
independently accepted completion or an explicit supersession record that binds
the replacement evidence. A passing canary does not complete any item below.

Exact worktree/commit/tree/status/diff identities are in
`custody-manifest.json`. Stale or conflicting route documents and rejected
candidates are governed by `supersession-index.json`. These JSON files are the
machine-readable authority; the paths and counts below are operator guidance.

## Stable canary boundary

- [ ] The v3 handoff records exact deployed commit/tree/image/source identities.
- [ ] A real `.megaplan/initiatives/critique-ledger-safe-v3-canary/canary.yaml`,
  content-addressed conformance validator/traceability/proof map, successful
  independent conformance receipt, and typed `completion-receipt.json` exist
  and bind the exact handoff artifacts required by the follow-up
  `finite_canary_receipt` gate. No normal-chain `done` state may be fabricated:
  the accepted finite boundary is `finalized` before execute/review.
- [ ] The poisoned v2 generation is fenced and cannot resume or notify.
- [ ] Automatic fixer effects are `DISABLED_FAIL_CLOSED` unless an independently
  accepted production owner proves exact-once semantics.
- [ ] Notification provider effects are `DISABLED_FAIL_CLOSED` unless an
  independently accepted occurrence/version-keyed owner proves dedupe.
- [ ] Recovery/notification capabilities and credentials are unreachable from
  the finite runner; no recovery/notification workers, timers, residents,
  watchdogs, provider processes, or direct fallbacks are started. Dormant
  shared-package source in the finite image is not claimed absent and its
  physical removal remains F1 work. Denial is proved before mutation.
- [ ] The model sees only a fresh, never-reused canary child bind at
  `/workspace`. It cannot address the preserved parent or any sibling
  workspace. The creation receipt records the initially empty root-only child;
  any later group/traverse access required by the unprivileged model is an
  explicit identity transition, not a silent weakening. Deploy/run/stop
  receipts bind and verify the exact inode, owner/group/mode and mount.
- [ ] Every model/tool subprocess runs under a dedicated unprivileged UID with
  no-new-privileges and no effective capabilities. Source, `.git`, plan
  state/gate, runner, installed engine and root auth remain non-writable. Each
  phase receives fresh isolated Codex state and one precreated, same-inode
  output file; no model process or writable runtime state survives into the
  next phase.
- [ ] The model boundary has finite process, memory, per-file and aggregate
  scratch limits. Its only aggregate writable scratch is a size-bounded,
  noexec/nosuid/nodev phase-runtime tmpfs; `/tmp`, `/var/tmp`, `/dev/shm`, PATH
  entries and the host bind outside the exact output are non-writable. Partial
  setup failures reclaim or seal every UID-owned inode before any next phase.
- [ ] Any canary runner failure fences and stops without invoking T1.5/T1.10.
- [ ] The canary is stopped at its declared finite boundary; no background
  wrapper, timer, resident, or watchdog can continue mutating or messaging.
- [ ] Operational substrate is a separate typed collection, never inferred
  from the archival `items` collection. The accepted provider-v2 implementation
  is `CONSUMED_BOUNDED_SUBSTRATE`; the finite T1.9 launcher is
  `CONSUMED_ON_SUCCESS` only in a passing completion receipt that binds the
  exact successful run. Neither is emitted as deferred work.
- [ ] All fifteen F1/F2 obligations below are emitted unchanged as
  `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`. Omissions,
  additions, duplicates, phase drift, status drift, and disposition drift fail
  the T6.2 completion gate.
- [ ] All marker, fence, bootstrap and reconciliation authority lives in one
  fixed `root:root 0700`, symlink-free host control-state directory outside
  poisoned and canary workspaces. Every write is safe dirfd-relative/no-follow,
  atomically installed and file-plus-directory-fsynced; the active marker's
  exact transaction ID and digest match the applying transaction. A mismatch is
  a hard NO-GO.
- [ ] All eight recovery units are absent or boundedly settled inactive and
  masked before any reclaim; failed units receive at most one bounded
  `reset-failed`, deactivating units have one shared deadline, recovery systemd
  jobs are observed and emitter/parser-bound, persistent masks are crash-safe
  before prune, and every pre-intent or partial/post-prune failure has typed
  durable, reconcilable evidence with no blind redispatch.
- [ ] One accepted built-image four-phase smoke, fresh inventory, bootstrap
  reclaim receipt, GO predeploy receipt, apply/verify fence receipts, finite
  run/conformance/completion receipt and terminal stop receipt bind the exact
  accepted A7/B7 implementation commit/tree, manifest commit/tree and image.
  Until live acceptance these identities and receipts remain typed `PENDING`;
  no placeholder is success evidence.
- [ ] Stable exit proves v2 stopped, preserved and persistently fenced; all
  recovery units absent or inactive+persistently masked; no relevant systemd
  job, tmux session or process; v3 `finalized` and stopped; and no notifier,
  fixer, resident, watchdog or timer remains.
- [ ] The follow-up authority files are updated with exact live identities,
  committed and pushed. One namespaced custody anchor, prelaunch and postcanary
  tags, and runnable integration ref preserve every accepted, rejected and
  dirty-snapshot identity; a fresh clone recomputes every hash and passes the
  same handoff checks.

## Exact deferred-obligation contract

Every row below also carries, in `custody-manifest.json`, an exact
`owner_milestone`, `INDEPENDENT_COMPLETION_MANIFEST_REQUIRED` gate,
`proof-map.json` evidence reference and same-ID required claim. Those fields are
part of the closed schema; prose or milestone completion without the exact
claim cannot discharge an obligation.

- [ ] `F1.platform_capacity_storage_hardening` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F1.physically_minimal_image` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F1.cross_pipeline_model_isolation` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F1.t1_5_monotonic_consumed_grant` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F1.production_recovery_owner` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F1.exact_occurrence_handoff` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F1.notification_occurrence_version_custody` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F1.t1_5_topology_retirement` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F1.t1_7_transactional_storage` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F1.t1_10_notification_policy` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F2.t1_1_universal_admission` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F2.t1_2_attempt_model_handling` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F2.provider_attested_model_identity` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F2.t1_3_transport_integration` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`
- [ ] `F2.t1_4_t1_6_release_closure` — `DEFERRED_POST_CANARY` / `NOT_CONSUMED_OPERATIONAL_CANARY`

## F1 — owner, storage and recovery root fixes

- [ ] Finish platform T0.3 beyond the bounded bootstrap: introduce an owner for
  reserved receipt/WAL capacity, quotas and high/low watermarks; prove ENOSPC,
  corruption and crash behavior; define safe lifecycle retention and broad
  Docker/storage reclaim. The prelaunch dangling-builder-cache reclaim and
  free-space floor are only a scoped bootstrap, not T0.3 completion.
- [ ] Produce a physically minimal production/canary image that omits dormant
  recovery/notification implementation and GLEKs, rather than relying only on
  execution-surface unreachability.
- [ ] Generalize the finite-canary model privilege boundary into a reusable
  cross-pipeline worker isolation profile, including per-provider UID/session
  lifecycle, resource budgets and policy receipts. The finite Codex boundary
  itself is prelaunch; multi-provider/platform adoption is follow-up work.

- [ ] Repair the rejected T1.5 candidate without discarding its valid HMAC
  receipt work. Coordinated deletion or rollback of `attempts`, `claims`, and
  `simulated_effects` must query an independently authoritative monotonic
  consumed-grant/idempotency record and return typed UNKNOWN/indeterminate with
  no second attempt or effect. Evidence:
  `.megaplan/subagents/critique-ledger-recovery/T1.5/t1-5-operational-pass3-independent-review-luna.md`
  (SHA-256
  `290fcd8b2132b5834c6e6fe961a2640329bfb133eb1acd618f82fed2b3d8d13a`).
- [ ] Implement and deploy the real fixed-socket production recovery owner; the
  current SQLite owner is explicitly test-only. The production owner must issue
  the occurrence target/ref, monotonic accepted state version, quiet transition,
  due-selection result, authenticated effect receipt, and exact-once consumed
  grant. The `F1.production_recovery_owner` claim also owns the remaining T1.8
  generation-owner and T1.9 production launch/store generalization; it does not
  reclassify the finite T1.9 launcher, which is consumed only by a passing
  canary receipt.
- [ ] Fix exact-occurrence handoff: immediate/reconcile wrappers must receive the
  owner-issued occurrence ID rather than calling owner operations with zero
  arguments. Preserve the retired four-line watchdog tombstone; do not revive
  diagnostic/Kimi/meta/fallback launchers. Evidence:
  `.megaplan/subagents/critique-ledger-recovery/T1.4/incident-stall-notify-exact-implementation-map-luna.md`
  (SHA-256
  `fd83c969cd8c2ffa45819aa5d23d098974bbd2aab2b37259f48f919beada1213`).
- [ ] Prove notification custody by occurrence ID plus accepted state version:
  restart and 200 unchanged polls produce one intent/effect maximum; missing
  provenance produces zero provider effects; same-occurrence reconciliation
  cannot mint a new notification key.
- [ ] Complete generic T1.5 topology and meaningful subject-specific retirement
  proofs for all 28 historical modules / 674 functions / 741 cases.
- [ ] Complete T1.7 owner-local transactional storage, capacity, ENOSPC,
  corruption and crash recovery. Preserved worktree:
  `/private/tmp/arnold-critique-recovery-t1-7-storage-20260802` (79 pass / 1 fail
  at pause; dirty work is evidence, not accepted code).
- [ ] Complete T1.10 notification rotation, reminder/chunk/child-key policy and
  auxiliary-writer retirement.

## F2 — admission, model, effect and release closure

- [ ] Resume and complete T1.1 universal admission from
  `/private/tmp/arnold-critique-recovery-t1-1-admission-20260802` (19 current
  modified/untracked paths at the frozen custody snapshot; paused at 6 pass /
  1 fail). Do not infer acceptance from preservation.
- [ ] Resume and complete T1.2 typed attempt/model handling from its preserved
  partial lane at
  `/private/tmp/arnold-critique-recovery-contract-bundles-20260802`; bind exact
  route/model, semantic success, bounded response-loss retry, sticky UNKNOWN
  and installed parity.
- [ ] Add provider/server-attested backend-model identity (or an independently
  authoritative equivalent). Exact CLI argv plus a sealed Codex rollout
  `turn_context.model` is useful operational evidence but is same-UID
  client-generated evidence, not cryptographic provider attestation; never
  relabel it as `provider_observed`.
- [ ] Integrate and generalize the bounded Stage-A T1.3 transport component
  `2f1500aea1d03fbf13df5c796b17bd03d17bb79c` only through a clean descendant
  with conflict and package qualification. Its acceptance covers authenticated,
  raw target-bound transport only—not T1.2 attempt/model completion, installed
  production authority, release authority, or cloud launch authority.
- [ ] Complete generalized T1.4 graph repair/retry and T1.6 effect-family
  migration plus the full release evidence matrix.

## Preserved but non-authoritative artifacts

- Rejected oversized T1.5/B7 attempt:
  `/private/tmp/arnold-critique-recovery-simple-fixer-20260802`, commit
  `939c763ae492a72efdd74941d431045b0f0ea61d`, tree
  `c78890fd9998241f8767210b36036e63c17eda5a` (32-file implementation history,
  roughly 28k inserted test lines). Mine it for evidence only; never merge it
  wholesale or report it as completed work.
- Rejected bounded T1.5 pass-3 commit:
  `9642193a063d91a6be364f2d11a04b221eae30cf`, tree
  `27a3d61dff39a4c1a26a8a736dc85ce727c57b7c`. Preserve its authenticated
  receipt design, but it has no acceptance or deployment authority.
- Accepted T1.8 Stage-A release/rollback commit:
  `06d41e6b7148db4e5b464131762d63fd697db056`, tree
  `a8a67b2e01b9129673afdc7931cb3ffdce03a2de`. Its accepted scope is local
  Stage-A interface behavior; it is not cloud deploy authority.
- Locally integration-eligible run-authority containment candidate:
  `48e13e1bcbc6769aff753270331d52ac1c148125`, tree
  `550421e34c1e789e31d173fdf35fdd7fd55ce287`, at
  `/private/tmp/arnold-critique-recovery-ra-contain-20260802`. It is not T0.0
  completion or installed production authority until clean integration and an
  owner-issued production decision/revision/fence/receipt pass.
- Rejected T1.10 notification candidate:
  `0c3d662024bc0497ed3979991a20b3b48ecf19cd`, tree
  `d4c10e167be87e1655704d1beeaf92d6c4e46526`, at
  `/private/tmp/arnold-critique-recovery-notification-ux-20260802`. Evidence
  only; never wholesale integrate.
- T5.1 evidence-schema candidate:
  `7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd`, tree
  `27e7b22ef0d7f3faeaa6b7cbcd63aabb2872d7e9`, at
  `/private/tmp/arnold-critique-recovery-t5-1-20260802`. Four owner decisions
  remain; it has no T6.2 acceptance authority.
- Prepared T1.4/T1.10 lane
  `/private/tmp/arnold-critique-recovery-incident-stall-notify-20260802` is a
  clean no-edit base only, not implemented work.
- The original all-task launch-cut audit at
  `.megaplan/subagents/critique-ledger-recovery/SEQUENCING/relaunch-cutline-luna-audit.md`
  is retained as historical classification evidence. Its all-T1-through-T5
  prelaunch conclusion is superseded by the independently reviewed bounded
  zero-recovery route; it does not regain launch authority by being tracked.

## Epic completion rule

The follow-up epic is incomplete until every checkbox above has an accepted
manifest or explicit supersession record, the ordinary Critique Ledger work is
completed and deployed, incident evidence is closed without rewriting history,
and real 24h/72h/7d durability observations pass.
