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
  and bind the exact handoff artifacts required by the supported artifact
  preconditions and strict F0 handoff-admission milestone. No normal-chain `done` state may be fabricated:
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
  atomically installed and file-plus-directory-fsynced. The transaction-
  independent global containment marker v2 has exactly
  `schema/profile/scope/active` and is published only after durable
  unit/job/session/process containment proof. Per-attempt intent and
  apply/verify/failure receipts bind exactly
  `transaction_id/transaction_digest/action`. A global-marker mismatch is a
  hard NO-GO; the same canonical marker is reusable by a fresh supported
  transaction only after containment is durably re-proved.
- [ ] All eight recovery units are absent or boundedly settled inactive and
  masked before any reclaim; failed units receive at most one bounded
  `reset-failed`, deactivating units have one shared deadline, recovery systemd
  jobs are observed and emitter/parser-bound, persistent masks are crash-safe
  before prune, and every failure is honestly split by authority boundary:
  pre-intent failure performs no mutation, fails closed and is captured through
  the supported caller's typed/error evidence path; every post-intent,
  partial or post-prune failure writes a durable O_EXCL host failure receipt
  and is reconcilable with no blind redispatch.
- [ ] One accepted built-image four-phase smoke, fresh inventory, bootstrap
  reclaim receipt, GO predeploy receipt, apply/verify fence receipts, finite
  run/conformance/completion receipt and terminal stop receipt bind the exact
  accepted finite-canary implementation commit/tree, manifest commit/tree and
  image. Candidate generation names never enter the gate ID; exact accepted
  identities live only in its evidence triple.
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
- [ ] F0 independently admits the exact finite-canary/stable-exit handoff and
  writes its content-addressed completion manifest. F0 is an evidence gate
  only: it completes none of F1-F8 and discharges zero deferred obligations.

## Failed prelaunch attempt history — immutable, not accepted

The machine-readable identities and remote copy dispositions are in
`custody-manifest.json#prelaunch_attempts`. Remote smoke evidence must be copied
byte-for-byte through the supported reader from the paths below. A null hash is
deliberately pending import; it is not permission to recreate a receipt.

- [ ] **B8 build** `c0e5e745d796d01deb962129f834978127f3adc0` /
  `0dc3d1e8c5d58ae5d09aa676148efadeb2f78ce8` failed because the minimal image
  lacked the `passwd` package providing `groupadd`/`useradd`.
- [ ] **B9 build** `cd120d8c585c078418583ba5142c966ac5554a12` /
  `025d719eb1318a2ff1f52673b79ef0014be7a1b2` installed `passwd` but the
  restricted runtime `PATH` omitted `/usr/sbin`.
- [ ] **B10 build attempt** `04178bf31748aa746a36e7e736c0ee38d441b666` /
  `7c67c7c63dc8d065a2f63663cba73e4566ed4c0e` completed the Dockerfile but
  final image unpack hit ENOSPC in the Claude CLI layer. A later rebuild of the
  same candidate succeeded after a separately authorized capacity reset; that
  does not erase this failure or constitute smoke/canary acceptance.
- [ ] Preserve B10 smoke at
  `/var/lib/arnold-zero-recovery/critique-ledger-b10-offline-smoke.json`: the
  harness used a local `sha256:` image ID as `FROM` and attempted an offline
  registry pull.
- [ ] Preserve B11 smoke at
  `/var/lib/arnold-zero-recovery/critique-ledger-b11-offline-smoke.json`:
  candidate `d610d1420a9851f2d3c0be27cf1cada5413b4f0f` / tree
  `1e9153d8ceda3834dc1f7b658322c7afbe16e05b` failed on missing `yaml`; its
  inspect evidence also exposed capability normalization and inherited-port
  drift.
- [ ] Preserve B12 and B13 at their corresponding
  `/var/lib/arnold-zero-recovery/critique-ledger-b12-offline-smoke.json` and
  `...b13-offline-smoke.json` paths. B12 (`cc5cd5b...` / `5494ba3...`) passed
  image/confinement checks but lost the init diagnostic; B13 (`63f8c0ae...` /
  `49afa570...`) retained a failed init phase receipt but still lacked bounded
  diagnostic tails. These are evidence-path failures as well as failed smokes.
- [ ] Preserve B14-B17 at the same immutable path pattern. B14
  (`38a7608f...` / `17f5cbcf...`) failed on missing `httpx`; B15
  (`4fbe51cd...` / `f7869b70...`) on absent `/dev/shm` under IPC isolation; B16
  (`05c874c8...` / `6f332c32...`) on permission creating phase-local
  `home/.codex`; and B17 (`dbb98ff2...` / `5115448b...`) on `fchmod(0600)`
  after premature UID transfer.
- [ ] Preserve B18-B20 at the same immutable path pattern. B18
  (`e1d26430...` / `75bd6a64...`) rejected untracked `.megaplan/worker_tmp`;
  B19 (`301abcae...` / `f743e9ec...`) rejected its streaming stdin tempfile;
  and B20 (`be3ca786...` / `602e5311...`) passed init but failed plan because
  `/usr/bin/env` could not resolve `python3` in the admitted model runtime PATH.
- [ ] Preserve B21-B24 at the same immutable path pattern. B21
  (`29ee2bfd...` / `d78c2e2f...`) failed plan with EACCES because the smoke top
  checkout remained mode 0700; B22 (`4e2fca8a...` / `a38dbd6a...`) failed
  critique because required semantic checks were missing; B23 (`7c9256b2...` /
  `55161ca5...`) failed finalize because the offline fake omitted the
  `finalize_capture` schema; and B24 (`a172a7a7...` / `461672f9...`) passed
  init/plan/critique/gate but returned `planner_repair_required` at finalize,
  exposing a real product mismatch: the prompt/feasibility contract requires
  task-contract v2 while the capture schema forbids or omits its v2 fields.
- [ ] Preserve B25 at
  `/var/lib/arnold-zero-recovery/critique-ledger-b25-offline-smoke.json`.
  Candidate `117efa9e35307981b16379f9bc8204e5a5ec0695` / tree
  `13995f708ab68240dfd08fa41430735cb66985b0` finalized every phase, but the
  final verifier rejected the plan privilege receipt because it still required
  `/dev/shm` `root_nonwritable` while IPC-none correctly recorded
  `absent_ipc_none`. It is failed history, not acceptance authority.
- [ ] Copy B26 at
  `/var/lib/arnold-zero-recovery/critique-ledger-b26-offline-smoke.json`.
  Candidate `9a8edcf11a488b5dfb47e5c4ef7defb17e3ba6d2` / tree
  `1de51fd479e0bcffc8fb9f951cb27982ad9ee036` passed all five exact phases,
  exited zero, produced four privilege receipts, and has declared file SHA-256
  `cf0967638b2c84097ced4dfc113735bbd66db1a8925d00d7080bdf7242669487`,
  receipt digest `7a656459d4aace827e8b180eb025117b609262311641c15ce495ba87042cf64f`
  and verifier digest
  `99c4420ac9440d539753e0a261781f6fc8588f974fa7e2ed07ee86cb2106e373`.
  Its production image is
  `sha256:261642f73da83b4704b33b02b9b1c14f17c56d4cafb633c98cac4f938d6421ed`
  and derived image is
  `sha256:74d24afc0af67ff6ae5de7d40ece647067873168793936f6d5d58e1a4a8742a7`.
  Sol's independent review decision is **GO**. No review artifact is present in
  this checkout, so custody records the reviewer/decision without inventing
  path or hash bytes. B26 remains an accepted offline smoke only: it is not a
  live gate, canary, stable-exit proof, or F0 result.
- [ ] Import and reconcile the durable failure receipt for live transaction
  `404dd858567d48ffbe8cb7c27d85185a` from
  `/var/lib/arnold-zero-recovery/404dd858567d48ffbe8cb7c27d85185a.host-zero-recovery-fence-apply-failure.json`.
  The transaction failed closed at `verify_no_recovery_sessions` with
  `tmux_observation_unknown`; `marker_published` was false, all eight recovery
  units were inactive, masked and persistently masked, and no canary was
  created. Exact tmux observation: rc `1`, stderr
  `error connecting to /tmp/tmux-0/default (No such file or directory)`.
  Root cause was the narrow classifier treating an absent tmux socket as
  unknown, not evidence of an active recovery session.
- [ ] Preserve the A27 classifier repair at
  `185e8d97732ff25e5e5d6a00b6877b7a46f08129` / tree
  `a7c204b757fe0673516d1e9e22a1308b73b0d778` and B27 launch binding at
  `0a3fbb56e48c5de98a455224c444a522ff31bf07` / tree
  `beb5d68bfcbdd7b0867a139ec19885dbb260e57d`. The repair adds the narrow
  absent-socket classifier plus a fail-closed unknown regression; its recorded
  suite result is 169 passed and 1 skipped.
- [ ] Copy and obtain Sol's independent acceptance for B27 at
  `/var/lib/arnold-zero-recovery/critique-ledger-b27-offline-smoke.json`.
  B27 passed all five exact phases, exited zero and produced four privilege
  receipts. Its declared file SHA-256 is
  `77c39d4763641724aa3355210c3ccdcbb6deb8a8253b560d416a9f47d3f1e454`,
  receipt digest is
  `173288c2fcd0aa793f894a3a995de1512447b4e9bbf6744fc241d2227d505b9b`,
  verifier digest is
  `bae9f5e69d7d2eaf3106ac5652c77be2608fc7c643d708d5c24af74bf2b08184`,
  production image is
  `sha256:c5687c73d88307ab9d7847585aaa371d27fab1e1286283b6456dbbf0d269470d`,
  and derived image is
  `sha256:71ef320bd30fe70211e9885c6972994a5f61c9625cc24bba9aecc2874082fb6e`.
  Sol acceptance is pending, so B27 is not a live gate or F0 authority.
- [ ] Run a fresh supported B27 live retry only after independent acceptance;
  do not reuse the failed transaction or infer authority from its safe unit
  state.
- [ ] Import and independently reconcile the failed-live and fresh-live receipt
  bytes; no missing receipt may be synthesized.
- [ ] Produce and independently accept the canary completion, stop and
  stable-exit proofs. These remain pending even after a successful offline
  smoke.
- [ ] Copy and reconcile every available B10-B27 receipt/evidence directory.
  No B8-B25 failed attempt is current acceptance authority; B26 is accepted
  offline history, B27 is the latest passing candidate pending Sol acceptance,
  and no missing receipt may be synthesized.

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

- [ ] **VERY HARD — zero-byte recovery authority.** Productize the emergency
  bootstrap exposed on 2026-08-03: when the authority filesystem has exactly
  zero writable bytes, the current safe route cannot create
  `/var/lib/arnold-zero-recovery` and therefore cannot reach its only admitted
  reclaim. Add an independently controlled off-host monotonic consumed-grant,
  a provider/reboot-persistent activation fence, an already-installed immutable
  helper, same-boot `/run` tmpfs stage receipts, immediate durable receipt
  migration, and reconciliation that never redispatches an ambiguous prune.
  Add a strict supported CLI reader for bootstrap/fence authority receipts so a
  lost client session never requires an internal provider command. Test client
  loss and reboot at every boundary, `/run` failure, concurrent BuildKit drift,
  partial persistent masking, insufficient reclaim, WBC rollback/corruption,
  and notification-provider zero-call assertions. This is owned by
  `F1.platform_capacity_storage_hardening`; it does not add or renumber a
  deferred obligation.
- [ ] Preserve and independently review the one-time live bootstrap evidence:
  the normal transaction `5ec3ee3ddb8948e3bccea8faeb41a051` failed
  `before_intent` with `prune_started=false` because creating the durable
  authority root returned `ENOSPC`. The separately committed operation intent
  at `evidence/zero-byte-bootstrap-operation-intent-20260803.json` permits at
  most one exact `docker builder prune -f` dispatch and makes ambiguity a
  terminal no-redispatch state. Replace this checkbox only with exact WBC,
  host receipt, capacity, containment and independent-review evidence.
- [ ] Preserve and independently review the subsequent capacity-reserve
  remediation at
  `evidence/capacity-reserve-remediation-intent-20260803.json`. Live evidence
  showed Docker build cache reclaim succeeded (3.83 GB to 0 B), while ext4
  still exposed 0 available bytes because 6,407,420 blocks (~26.2 GB) were
  reserved for root and only 938,990 blocks were free. The bounded remedy may
  purge only the 4,384,727,040-byte pip cache and reduce the reserve to 262,144
  blocks (1 GiB); workspace, deploy directory, npm cache, predecessor
  container, images and volumes remain preserved. Platform T0.3 must replace
  this emergency tuning with owned high/low watermarks and reserve policy.
  The first admitted cache command failed before mutation because host Python
  has no pip module; its failure receipt is preserved. The exact filesystem-
  native fallback is separately authorized at
  `evidence/capacity-reserve-remediation-fallback-intent-20260803.json` and may
  delete only descendants of the canonical pip-cache directory while
  preserving that directory inode.
- [ ] Preserve the three failed real image-build attempts (B8 missing account
  tooling, B9 restricted-PATH account-tool resolution, and B10 final-layer
  ENOSPC) and the exact failed-build reset authority at
  `evidence/failed-build-capacity-reset-intent-20260803.json`. The reset may
  prune only build cache, images referenced by no container, npm-cache
  descendants, and reduce root reserve from 1 GiB to 512 MiB. It must preserve
  the predecessor container and referenced image, workspace, deploy directory,
  volumes, trusted host receipts and archived unit definitions. Platform T0.3
  owns eliminating this repeated build/cache pressure permanently.
  The first reset intent failed before dispatch because it bound the provider's
  overall cache projection as the npm-subdirectory size. Its `dispatch=[]`
  receipt is preserved; the corrected exact observation/authority is
  `evidence/failed-build-capacity-reset-corrected-intent-20260803.json`.
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
- [ ] Align the canonical `FINALIZE_MODEL_OUTPUT_SCHEMA` required set with the
  persisted finalize schema; prompt, feasibility, capture and stored output
  must consume one exact task-contract-v2 contract.
- [ ] Prove non-empty `dependency_reasons` against the real provider output
  schema, not only the offline fake.
- [ ] Close the scratch-template `const2` mismatch without weakening the exact
  finite-worker mutation boundary.
- [ ] Preserve historical v1 read compatibility while keeping all new writes
  and validation on the canonical v2 contract.
- [ ] Qualify document and joke modes against the same finalize/capture schema
  rather than treating planning mode as universal proof. These five B26-era
  follow-ups remain under existing F2 release closure and do not add, renumber,
  or complete any deferred obligation.

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
