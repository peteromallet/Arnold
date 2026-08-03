# F1 — Complete deferred owner, storage and recovery hardening

## Outcome

Close the owner/storage/recovery obligations intentionally scoped out of the
bounded Stage-A finalize canary before v3 receives ordinary execution or
publication authority.

## Scope

Complete `T0.3/platform-capacity-and-storage-hardening` after—not instead of—the
separately receipted `T0.3/scoped-prelaunch-capacity-reclaim`; platform adoption of T1.7 owner-local
transactional storage; the non-exercised but shipped T1.5 legacy recovery
retirement and honest disposition of all formerly hidden assertions; full T1.10
key rotation, reminder buckets and child GLEKs; remaining T1.8/T1.9 owner/store
generalization; and preparation of T4.6 without rewriting evidence.
Generalize the finite Codex UID/capability/resource boundary into a reusable
cross-pipeline worker profile and build a physically minimal image that omits
dormant recovery/notification code and credentials.
Close the zero-byte authority bootstrap deadlock found live on 2026-08-03:
durable local intent creation cannot be a prerequisite for reclaiming the first
writable block on that same full filesystem. The generalized solution requires
off-host monotonic operation consumption, a reboot-persistent provider fence,
an immutable preinstalled helper, `/run` same-boot staging, durable post-reclaim
sealing, ambiguity-safe reconciliation, and a supported strict receipt reader.
Also close the newly observed control-plane gaps: durable occurrence/state-
version notification dedupe; one provenance-safe bounded generalized fixer;
M7 projection-cursor reconciliation; event-incarnation/checkpoint repair and
cross-observer lifecycle convergence; resident read-only admission before its
source fence; stage-specific recovery diagnostics; a versioned receipt schema
that includes a separate `resident_image_id`; and hash-locked recovery-image
dependencies. Rotate every resident credential exposed when a diagnostic
command printed the environment file; retain no secret value in evidence.
Close the independent 11:42 Europe/Berlin `/whats-cooking` availability gap:
the Discord resident was offline after the production container exited on
ENOSPC, and restart attempts failed before Discord connect. The handler already
defers before status collection, so this is not acknowledgement ordering.
Attempt 14 began 27 minutes later without a Discord token or resident; no causal
link to the canary is established or may be claimed.
Close the major storage root cause confirmed after attempt 15. The preserved
production predecessor writable snapshot/container is approximately 389.927 GB,
with `/tmp` approximately 388.813 GB. Exactly 1,156,578 progress-auditor
recursion copies consumed 387,889,659,906 logical bytes as roughly 395,629-byte
`arnold-repair-loop.*` files. The installed-source trampoline preceded the
snapshot guard; the snapshot execed source; source saw an active-path mismatch
and created another snapshot; and the later cleanup trap was overwritten.
Post-run free space was 1,484,693,504 bytes, below the 1,611,661,312-byte hard
floor. This recursion drove ENOSPC and the resident crash and likely—but not
exclusively proven—contributed to attempt-15 code-host SIGTRAP/closed-stdout.

The notification/watchdog path independently re-emitted the same terminal
`manual_review` incident without durable incident-key dedupe; the progress
auditor did not send the repeated Discord messages. A separate diagnostic-fixer
launch failed provenance validation. The completed safe-reclaim receipt binds
predecessor container
`277d2e6dbc149e01b25881350238a7b0ff5de78cc27d8ef52c144dca7c35c5ab`,
1,156,578 deleted copies, 387,889,659,906 deleted logical bytes, zero remaining,
390,136,713,216 free bytes afterward, and preserved predecessor/workspace.

Attempt 16 subsequently passed the infrastructure recovery path: seven rc0
phases, complete dispatch integrity, null failure, reconciled stopped container
and sealed workspace. Its terminal state is product `product_gate_not_proceed`
after the bounded second `ITERATE`, so it is neither an infrastructure failure
nor a durable epic launch. The systemic tasks below remain required F1 work but
are `DEFERRED_POST_RELAUNCH_NONBLOCKING`; they must not be used to deny a
separately authorized relaunch or to rewrite attempt 16's exact classification.

## Locked decisions

- The eventual independently accepted and installed Stage-A route is preserved
  and regression-tested; bounded local components alone do not establish that
  route. This milestone generalizes rather than replaces accepted behavior.
- Every canonical owner fails closed on corrupt/missing state, has a current
  revision/fence/incarnation and preserves sticky indeterminacy.
- Every still-shipped ordinary recovery mutation path is either owner-routed or
  hard-denied at point of use. No blanket skips, xfails or collection hiding.
- Notification key rotation and reminders cannot mint a second occurrence or
  re-send an unchanged decision.
- Caller-writable projections can never be the sole proof that an occurrence
  has not already consumed its one mutation attempt. The production
  effect-owner/WBC service holds a monotonic, occurrence-scoped consumed-grant
  or idempotency record outside those projections.
- Missing or rolled-back local attempt/claim/effect rows are not interpreted as
  fresh work. Reconciliation consults the external monotonic authority and
  returns typed UNKNOWN/indeterminate without redispatch when proof is absent.
- The production fixed-socket owner—not a caller or wrapper—issues the exact
  occurrence target/ref, accepted state version, quiet transition and due
  selection. Immediate/reconcile wrappers receive the exact occurrence ID.
- Phase OAuth and network egress are confined to the exact provider endpoint;
  no ambient credential, proxy secret or unrelated destination is reachable.
- Concurrent workers use distinct owner-issued identities/cgroups. A global
  shared-UID kill is not the generalized concurrency authority.
- Sealed phase rollouts/runtime receipts have explicit retention and garbage
  collection; cleanup cannot erase incident evidence or leak writable state.
- The privilege launcher has installed conformance for supported kernels and
  container runtimes, including capability, setpriv, tmp/proc/signal and
  resource-limit hostile matrices.
- A cache prune is not assumed replay-safe merely because its argv is
  idempotent-looking: a later replay can delete newly-created cache. Client loss
  or reboot after dispatch therefore consumes the operation and yields typed
  ambiguity until independently reconciled; it never authorizes redispatch.
- Resident recovery is bounded, receipted, and capacity-gated. Restart retries
  cannot create an unbounded loop or duplicate an outage alert.
- Resident recovery performs all read-only admission before changing source
  restart policy, binds separate exact source and resident image IDs, and
  reports the exact failing stage with rollback proof.
- A generalized fixer is real only after durable delegation provenance and
  launch receipt exist. Missing provenance emits no mutation and no repeat
  escalation.
- The installed-source trampoline checks the snapshot guard before exec. Every
  repair snapshot has bounded lifetime and non-overwritten `finally`/trap
  cleanup across success, failure, timeout, signal and cancellation.
- Repair loops are singleton per subject and enforce a durable attempt cap.
- Repair/resident paths have a disk budget and preserve reserved headroom; every
  model/tool phase trips fail-closed before dispatch below the threshold.
- Safe reclaim is bounded and receipted and proves historical and active
  workspaces byte-preserved. Resident recovery uses a dedicated surface with no
  general repair-loop, notification or canary-retry authority.
- Notification/watchdog delivery uses durable incident-key dedupe: exactly one
  terminal `manual_review` alert per incident across retries, with a separate
  recovery transition. Diagnostic-fixer provenance failure remains separate.
- Attempt 16's infrastructure-recovery PASS is immutable input evidence. F1
  neither converts its product ITERATE into PROCEED nor makes this broader
  systemic generalization a relaunch prerequisite.

## Open questions

- Which owners can adopt the neutral store directly and which require an
  adapter/migration with a reconciled saga?

## Constraints

No expansion of v3 execution/publication authority, cloud relaunch, marker edit,
or replacement of accepted owner evidence with projections.

Repair of the finite-canary trusted host control-state root, marker/receipt path
safety, fence emitter/parser parity, bounded unit settlement, crash-safe
persistent masks, partial-reclaim reconciliation and built-image smoke is T6.2
**PRELAUNCH** scope. None of it may be deferred to this F1 platform-hardening
milestone or satisfied by F1 evidence after launch.
The T6.2 global containment marker is transaction-independent
`schema/profile/scope/active` state published after durable containment proof;
per-attempt intent/apply/verify/failure evidence—not the marker—owns
`transaction_id/transaction_digest/action`. Pre-intent failures are no-mutation
caller-captured failures; post-intent failures retain durable O_EXCL host
receipts.

## Done criteria

- Storage reserve/capacity and crash/ENOSPC behavior are proven platform-wide.
- Installed-source/snapshot recursion regression tests prove the guard runs
  before trampoline exec and no cleanup trap is overwritten. Temp-file failure
  injection proves zero leaked `arnold-repair-loop.*` files after success,
  failure, timeout, signal and cancellation; concurrency proves singleton
  ownership and the durable attempt cap.
- Disk-budget tests prove reserved headroom, pre-model/tool capacity trip, and a
  bounded receipted reclaim that preserves every historical and active workspace.
- Resident-only recovery tests prove it cannot reach the general repair loop,
  notification sender, or finite-canary retry surface.
- Notification/watchdog tests prove durable incident-key dedupe emits exactly
  one terminal `manual_review` alert per incident across retries and a distinct
  recovery transition; no test attributes those messages to progress auditing.
- At exactly zero free bytes, client loss and reboot at every boundary prove one
  admitted reclaim dispatch maximum, zero legacy notification effects, durable
  post-reclaim sealing, and supported recovery of host authority evidence.
- Required owners use accepted transactional storage or an independently proven
  equivalent.
- Full recovery topology inventory has zero live unowned mutation path and the
  historical 741 assertions have explicit passing retirement/no-side-effect
  dispositions.
- Full notification rotation/reminder/child-key semantics pass source, wheel and
  installed-generation tests.
- The reusable cross-pipeline worker profile proves per-worker UID/cgroup
  isolation, zero model capabilities, strict env/credential/egress confinement,
  bounded resources, deterministic process cleanup, sealed evidence retention
  and portable installed-runtime conformance.
- The production/minimal canary image physically excludes deferred
  recovery/notification implementations and GLEKs; execution-surface denial
  alone is not accepted as physical minimization.
- Coordinated erasure and rollback after both ambiguity and completed success
  cannot mint a new attempt or effect, including after process and host restart.
- The deployed production owner passes peer authentication, monotonic
  consumed-grant, exact-occurrence wrapper, quiet-transition, due-selection and
  accepted-state-version hostile tests; the test-only SQLite owner is not used
  as deployment evidence.
- Restart and 200 unchanged polls emit at most one occurrence/version-keyed
  notification effect; missing provenance emits zero.
- An injected resident exit is detected and recovered through one bounded safe
  restart with receipts. ENOSPC blocks restart until a bounded reclaim and
  accepted capacity proof complete.
- Synthetic Discord interaction monitoring detects defer/response
  unavailability independently of status collection, and exactly one outage
  alert is emitted per outage epoch across restart retries, followed by a
  separate recovery transition.
- M7 projection history is reconciled or explicitly forked for a fresh
  generation; cursor mismatch cannot become an indefinitely repeated warning.
- The exact r5 two-incarnation event fixture (`0..9`, then `0..N`) is replayed.
  `introspect`, `trace`, plan status, doctor, cloud status and chain status all
  remain readable and converge on one lifecycle/active-phase tuple within a
  declared bounded lag; an incarnation change atomically rotates checkpoint
  and projection cursors instead of raising a non-monotonic-sequence error.
- A per-session fresh-launch lease prevents overlap. Reset cannot delete a plan
  until its previous process tree is terminated and reaped; two launches in one
  minute receive distinct plan/incarnation identities or one typed conflict.
  Events and transaction IDs include incarnation; sequence is strictly
  monotonic within it. Checkpoints bind plan, incarnation, sequence, byte
  offset and source digest. Historical incarnations remain inspectable.
- The canonical observer tuple is plan, incarnation, lifecycle, active phase,
  worker liveness and observation timestamp. All supported observers converge
  within 60 seconds. A broken checkpoint returns typed degraded evidence and
  never infers a product stall. The installed cloud regression proves one
  active runner, one current incarnation and zero repeated cursor warnings.
- Work-ledger emitters remove reserved fields from metadata before forwarding;
  each auto phase transition produces exactly one idempotent transition and no
  `multiple values for keyword argument 'transition'` warning.
- Resident receipt v2 migration and compatibility tests bind
  `resident_image_id`; built-image import tests use hash-locked dependencies.
- All resident credentials exposed in the diagnostic transcript are rotated,
  old values are rejected, and no evidence artifact contains a value.
- Independent completion manifest at
  `evidence/critique-ledger-recovery/T0.3/platform-capacity-and-storage-hardening/completion-manifest.json`
  binds exact commits, migrations and receipts. It cannot supersede or imply
  the prelaunch reclaim/GO receipt.

## Touchpoints

`arnold.storage`, recovery/simple-fixer topology, notification custody, release
and launch owners, capacity controls, installed wrappers and evidence for
T0.3's platform-hardening subtask, repair-loop temp creation/cleanup, model/tool
phase admission, resident-only recovery, T1.5/T1.7-T1.10/T4.6.

## Anti-scope

Do not run CL2 feature execution, publish a PR, deploy the product, or mark the
incident resolved.
