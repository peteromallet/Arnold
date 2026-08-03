# Critique Ledger post-relaunch completion epic

This epic begins only after the separately authorized live r5 Critique chain
has completed every CL2-CL5 milestone and published a content-addressed chain
completion manifest. The earlier finite-slice safe-canary lineage remains
immutable incident history; it is no longer this chain's executable launch
precondition.

It preserves the remainder of the 55-task recovery checklist, including deferred
platform-wide hardening, without making that generalization, product completion,
archival closeout, or 24h/72h/7d observation prerequisites for the bounded v3
finalize canary.

Canonical source:
`docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`.
The tracked copy is the complete 55-task source checklist, preserved as evidence
and work custody. Its original all-predecessors launch cut is not current launch
authority; the bounded zero-recovery cut and this epic's typed handoff are.

Sequencing audit:
`.megaplan/subagents/critique-ledger-recovery/SEQUENCING/relaunch-cutline-luna-audit.md`.
That audit is retained for task-by-task rationale but its conclusion that the
entire T1/T2/T3/T4/T5 portfolio blocks the finite canary is superseded. See
`supersession-index.json`.

Do not launch this chain until the live r5 predecessor has no active plan, all
CL2-CL5 milestones have accepted completion records, its current `chain.yaml`
hash matches the state, and its content-addressed completion manifest passes
the installed `chain_completed` precondition. F0 reconciles that handoff and
completes none of F1-F8 or F2A. Incident operators must follow
[`RUNBOOK.md`](RUNBOOK.md); generic cloud deploy/chain/supervision routes are
forbidden for this recovery.

## Current operational handoff — 2026-08-03

Critique Ledger is now running again on the cloud machine. This is a live
operational relaunch, not completion of this follow-up epic and not permission
to erase the failed-attempt history below.

- Session: `critique-ledger-accountability-v3-r5-20260803`.
- Current plan: `cl2-wbc-backed-ledger-20260803-1357`.
- Product source: `e5e9f2b1c1a7e7779121405fd4801768e1e8a4c2`, with fresh
  milestone branches under `megaplan/critique-ledger-accountability-v3-r5/`.
- Isolated collector image:
  `sha256:2b6b18caeaf90ecdf6246f2c5eec5bcb9eccdb86435f66b0c3f98a5af0dce82d`.
- Exact isolated runtime:
  `82a5a012fa58f44cdc5e9e895f454d86d95b446d`.
- The route is OAuth-backed all-Codex because no direct DeepSeek provider key
  was admitted. It must not claim that DeepSeek ran. The observed live worker
  is `gpt-5.6-luna` in prep.
- At the latest bound observation (`2026-08-03T14:15:48Z`), the chain tmux and
  chain process were alive. Prep completed at `14:04:08Z`, plan completed at
  `14:11:40Z`, and six `gpt-5.6-sol` high critique workers had produced fresh
  critique artifacts. This proves current progress, not milestone or whole-
  chain completion. Observation is degraded: the plan journal contains two
  launch incarnations under the same minute-resolution plan ID, `introspect`
  rejects the resulting non-monotonic sequence, and outer chain status remains
  stale at `initialized` while the plan is in critique.
- PR #325 is open at head
  `a73b2760369aa99f28bb02d41003325369bed6fa`. Its current CI run is red because
  two initiative documents were written outside canonical artifact
  subdirectories. The live critique/revision loop owns that repair; no success
  or milestone-advance claim may be made until the exact PR head is green.

### Later r5 CL2 repair-control incident

The live observation above is intentionally timestamped and was superseded
later the same day. At `2026-08-03T14:56:06Z`, CL2 stopped in critique after
three changing validation-error sets were incorrectly collapsed into one
deterministic signature. At `15:43:11Z`, repair request
`734816b31530e56a4835cc54c265e5712b247860a1de269b598ed93faf7b1d92`
then recorded `launched`/`dispatched`, but no managed repair process or manifest
was established: trigger PID `1310` is dead, the active claim has no managed
binding, the expected manifest is absent, and repair goal
`repair-goal-406167807af0ecce698017e5` remains active with that absent manifest
as owner. Exact evidence and the immediate/deferred ownership split are in
[`evidence/r5-cl2-repair-control-incident-20260803.json`](evidence/r5-cl2-repair-control-incident-20260803.json).

This was not a slow fixer and should not be attributed simply to the Sol model:
all nine current per-check and producer-v2 critique payloads validate, while
aggregate recovery retained only the unhelpful sentinel `parallel`. The
immediate root branch is fixing the bounded live-unblock path. Nothing in that
branch counts as accepted, installed or deployed until integrated and proven
against this exact fixture. F1 retains the platform-wide truth firewall,
supported stale-claim/goal settlement, phase-bound repair authority,
current-error signature discipline, per-check reconstruction, canonical
observe-only full report and durable version-keyed status publication.

Today's relaunch also proved a separate cross-pipeline launch invariant was
missing: declared profile/vendor intent, fully resolved phase routing, uploaded
bytes and the process that actually ran were not one sealed object. The new
**F2A — VERY HARD (5/5)** milestone closes that gap after F1/F2 primitives and
before F3 ordinary product work. Its committed policy map refuses unexpected
all-Codex or any other substitution before spawn, binds execution only after
exact remote-byte readback, contains wrong-profile workers, rolls back and
relaunches once idempotently, and notifies only if bounded automatic repair
fails. The contract is pipeline-neutral and requires registry-closed tests for
every production Arnold pipeline and launcher; it is not a Critique/Megaplan-
only patch. See
[`provider-policy-execution-binding-contract.json`](provider-policy-execution-binding-contract.json)
and
[`briefs/f2a-launch-profile-artifact-drift-containment.md`](briefs/f2a-launch-profile-artifact-drift-containment.md).

Discord resident availability is separately restored. Recovery epoch
`discord-enospc-20260803-r7` created healthy container
`a2c9a0d058af24ec38b05f2c8a1d2865c6120420faa4802d4cd9a740eaed9b1a`
from image
`sha256:78474208a513bfa03c51d6e04f3d31381ae07305b1c291db112098c05ba82c20`
using immutable runtime `31d2e052104a57eb48e782dce8bdf678e6731caf`;
its receipt is healthy with reason `discord_ready`.

Machine-readable current custody is
[`current-operational-handoff.json`](current-operational-handoff.json); its
timestamped status is evidence, not a mutable live-status oracle.

The shortest safe operator route is therefore to supervise the live r5 chain,
leave its exact source/runtime/image tuple unchanged, and execute the ordered
follow-up backlog in [`UNFINISHED_WORK.md`](UNFINISHED_WORK.md). Do not redeploy
the live collector merely to consume a later runtime hardening commit. If the
live generation fails, use the fresh-generation procedure in
[`RUNBOOK.md`](RUNBOOK.md); never resume an ambiguous plan, branch or workspace.

One urgent security action is independent of chain progress: rotate every
resident credential present in the diagnostic environment file because a
diagnostic command accidentally printed that file in a tool transcript. No
secret value is retained in this epic.

## Operational-relaunch recut handoff — 2026-08-02

The supervised v3 canary is intentionally limited to the operational route
recorded in
`.megaplan/subagents/critique-ledger-recovery/INTEGRATION/minimal-operational-relaunch-map-sol.md`
(original SHA-256
`fd1a33ba58566aa126e170643f59a39bca13972e5919d0a338403b50c169312e`),
as corrected by the post-T1.5-failure route adjudication. The original
four-commit wording is superseded: T1.5 operational pass 3 is **rejected**, not
accepted, and a typed SSH lifecycle/capacity/durability preflight is now a
direct prelaunch dependency.

Corrected launch-route authority:
`.megaplan/initiatives/critique-ledger-post-relaunch-completion/finite-canary-operational-route.json`
(SHA-256 `189b289d4b5d556b1ab65c344220bd4e7fec2b2526a53227c1767912e1ff9a21`).
It consumes the earlier post-T1.5 shortest-route rationale only together with
the newer non-root privilege, mount, resource, effect and honest model-evidence
bindings. The rationale document alone has no launch authority.

The supervised canary must run with automatic fixer effects and notification
provider effects disabled fail-closed unless a later independently accepted
candidate proves them. The installed canary execution surface must make those
paths unreachable: no recovery/notification capability or credential is passed
to the finite runner, and no recovery worker, timer, resident, watchdog, direct
fallback, or notification provider is started. The finite image may still
contain dormant shared-package source; physical package minimization is F1
follow-up work and is not claimed by the canary. Deny-before-mutation and
process/credential absence proofs remain prelaunch requirements. Runner failure
fences and stops; it never invokes T1.5 or T1.10. Direct observation by the recovery
operator is allowed;
absence of automatic repair is not evidence that recovery is complete. The
canary handoff must record the exact disabled-effect posture and must not claim
T1.5, T1.4 notification custody, or production-owner completion.

The complete inventory of preserved and unfinished work is
[`UNFINISHED_WORK.md`](UNFINISHED_WORK.md). No dirty worktree, rejected commit,
or deferred interface may be silently consumed by the canary or dropped by this
epic.

Machine-readable custody is frozen in [`custody-manifest.json`](custody-manifest.json),
including immutable B8-B25 failure history, B26's independent Sol GO, the
failed no-canary fence transaction, B27's terminal/reconciled failed live
canary, B28-B30's terminal/reconciled failed live retries, the full A31-B35
schema-access recovery lineage, B35 attempt 9's status-poll-induced terminal
stop, A36/B36's terminal publication NO-GO, immutable A37-B39 repair/launch lineage,
B38 attempt 12's terminal process-leak failure, the accepted reclaim-v2 and
bounded diagnostic-checkout retirement receipts, and B39 attempt 13's terminal,
safely stopped, not-accepted `ITERATE` result. A40 is closed: it authorized only
the bounded direct-PROCEED route or one ITERATE→revise→PROCEED route. The exact
attempt-14 candidate is implementation `a15e87adea1fa78e90008422f42bc79ae60dff13`
/ tree `63a75d9333e3fa69c9a039846595d3dd4d3cc4b3`, B44 manifest
`006895e8d66812dec5e85d26b32635af21ca21c7` / tree
`8d70cc79bc8f5a79a60be282bcc22122109c7f83`, and production image
`sha256:209a64de1f321b5ec49e8d6e6748187f790099a6fe8a68696352a5488bc7ffa6`.
Its outcome is immutable terminal failed/misclassified history: receipt digest
`59f0d1712bbd6f379d921f9662989a7a524b62e8509182041e08ba368e0abe0d`
(file SHA-256 `23f260ba72c0785401d4749132491beeac1bd2cf7c61cc386c7b29e980ecb3c0`)
records `init→plan→critique→gate→revise`, gate `ITERATE` at
`415fb3ffac618a196d2822f288d69d9457abd6f121615c1153e34fb7404e6545`,
and predispatch human halt `NSA-7`. The old runner reported generic failure,
partial dispatch integrity and ordinal 4; finalize never ran, and the container
is stopped with its workspace sealed. It has no F0 authority.

Attempt 15 is terminal infrastructure-failure history: A15 implementation
`8932873ba1c81d398cf42fb9879605d14d50cbb4` / tree
`7fdcf11dba38354645290314443c1de3c8b33bbb`, B15 manifest
`4f021cb70f3202dd90d599f8d710b626ba27b16b` / tree
`3777df403e9ae06cba75cf6fb6ac3b804f808723`, image
`sha256:ea1e66940e7445649b083b8d7acc896080526011f9bfc4a9e21b475046e1814a`,
workspace `critique-ledger-safe-v3-canary-attempt-15-20260803`, and container
`megaplan-cloud-agent-finite-canary-15`. It settles one clean committed source
commit/tree across finalize, direct execute, batch execute and handoff; emits a
typed revise result with fresh invocation identity; classifies human-halt and
unresolved blockers as `product_revise_blocked`; and admits dispatch ordinal 4
only after a revise worker dispatch. Receipt digest
`59bc8d659ca8ec59baa9da9051fcd7320199e6ffea12a97d3b7018694b266331`
(file SHA-256 `10eb82a07ca0829b585c4316413b76851665ac9b90ef93e051f94626f91a182a`)
completed at `2026-08-03T11:00:12.627961Z` after
`init→plan→critique`. Plan returned successfully. The critique worker returned
output, but the in-turn Codex code-mode host repeatedly hit SIGTRAP/closed
stdout and could not inspect or update the template; the CLI returned 1 with
state `planned`. Gate, revise and finalize did not run. The receipt is
failed/failed/partial with null product outcome and dispatch-ledger SHA
`222abc464f60acf7b14689fcfef4ca8649a7746d80e3d09a600caf89988d7ded`.
The container stopped at 143 (OOM false, restart zero) and the workspace is
sealed. Attempt 15 itself has no F0 or retry authority; that was the terminal
lineage before fresh B16 attempt-16 authority was issued.

Attempt 16 is the validated terminal infrastructure-recovery proof. Its outer
status is `available`; the v3 run receipt is `passed` with terminal state and
product-outcome kind `product_gate_not_proceed`. Source B16 is commit
`fb5a394878bc900b189213a3de5dcc40169d8b7b` / tree
`a8f903a94e5029fa50c148df3289186dc4c39caf`. All seven phases
`init→plan→critique→gate→revise→critique→gate` returned zero, dispatch
integrity is complete and failure is null. Both gate attempts returned
`ITERATE`; product outcome recommendation is `ITERATE` at gate attempt 2, whose
gate SHA-256 is
`b8d6dcf366b04bde245890e1cb224c191f202101cb53dbb3fa59ca721c05d546`.
The receipt digest/file SHA-256 are
`3a9925dbfcc0c901905db0265b48c062f051b16bdbb31b9f873c5e086eac08c0` /
`1b4e1d013f444b3f3f2c3af1bb4938002e730f727a0be39834a2ca235fa592ba`;
state SHA-256 is
`4ef979066dfb3c822625de21ec52e95c7d25a42f185ea01970865d4b4116e525`.
Container
`0552d39f4589239cb0b8e10b68b12c8ebab3a0e2fde6284049e1e466f0896ba6`
is stopped at exit 143 (OOM false, restart zero), stop is reconciled and the
terminal workspace is sealed. This is not an infrastructure failure: the
infrastructure recovery proof passed. It is also not a product PROCEED,
finalized result or durable epic launch. Its remaining product actions and the
broader systemic hardening are owned by F2 and F1 respectively and do not block
a separately authorized relaunch.

## Historical v3 durable-relaunch precursor — contained, not accepted

The first v3 bootstrap correctly rejected the abbreviated initiative revision
`0bb0c0b74e` as `intended_initiative_revision_unpinned` before initialization.
That precursor defect is resolved: the source was repinned to the full revision
`0bb0c0b74e6b1913d39b51f33559b2f5127f1886`, and a fresh `cloud chain` retry
returned zero, was alive, advanced beyond init and initialized plan
`cl2-wbc-backed-ledger-20260803-1313`.

Those signals did **not** establish a durable relaunch. The stability read found
the editable root/revision bound to
`/workspace/runtime-candidates/arnold-a8e7ef6c345bbc1aceb19af67e7e25b1e05ad4e4`
at `a8e7ef6c345bbc1aceb19af67e7e25b1e05ad4e4`, while the actual import root and
source revision were still
`/workspace/runtime-candidates/arnold-c7bcb06af536acfe759c1b31a785afc19afe92d4`
at `c7bcb06af536acfe759c1b31a785afc19afe92d4`. The later cloud hot-environment
selector overrode the already verified pinned runtime source. The operator
therefore redeployed the same isolated collector to stop the untrusted run.
The initialized plan has no reuse or resume authority.

Durable relaunch now requires one fresh retry whose post-launch observation
proves all four runtime fields agree: `editable_root == import_root ==` the
configured pinned runtime root and `editable_revision == source_revision ==`
the configured pinned runtime revision. Exit zero, alive, advanced and plan
initialization remain necessary but are not independently sufficient. This is
an active T6.2 pre-F0 blocker; it does not change, discharge or pull forward the
fifteen deferred F1/F2 obligations.

That requirement was subsequently satisfied by the fresh r5 generation
recorded in **Current operational handoff** above. This precursor remains
immutable rejected history and its initialized plan remains non-resumable.

Post-run free space was 1,484,693,504 bytes, below the 1,611,661,312-byte hard
floor. Read-only inventory found the preserved production predecessor writable
snapshot/container at approximately 389.927 GB, with `/tmp` approximately
388.813 GB. Exactly 1,156,578 progress-auditor recursion copies consumed
387,889,659,906 logical bytes as roughly 395,629-byte
`arnold-repair-loop.*` files. The installed-source trampoline ran before the
snapshot guard; the snapshot execed source; source saw an active-path mismatch
and created another snapshot; and the later cleanup trap was overwritten. This
recursion drove ENOSPC and the resident crash and likely, but not exclusively,
contributed to attempt 15's code-host instability.

The repeated Discord messages have a different owner: the
notification/watchdog path re-emitted the same terminal `manual_review`
incident without durable incident-key dedupe. The progress auditor did not send
those messages. A separate diagnostic-fixer launch failed provenance
validation. Receipted reclaim from preserved predecessor container
`277d2e6dbc149e01b25881350238a7b0ff5de78cc27d8ef52c144dca7c35c5ab`
deleted all 1,156,578 recursion copies (387,889,659,906 logical bytes), left
zero, and restored 390,136,713,216 free bytes while preserving the predecessor
and workspace. Attempt 16 subsequently proved infrastructure recovery. The
remaining root, storage, resident, notification and recovery generalization is
deferred into the follow-up and does not block relaunch; any future execution
still requires fresh explicit authority. The five
historical operations still require receipt import and independent
reconciliation; the unrelated terminal checkout retirement does not discharge
them.
Conflicting or stale launch instructions are retired by
[`supersession-index.json`](supersession-index.json). Human prose never
overrides those typed dispositions.

An independent product-availability incident is also in custody. At 11:42
Europe/Berlin, `/whats-cooking` failed because the Discord resident was offline;
the production container had exited on ENOSPC and restart attempts failed before
Discord connection, so no resident event existed. The handler already defers
before status collection, ruling out acknowledgement ordering. Attempt 14 began
27 minutes later and has neither a Discord token nor a resident. No causal link
to the canary is established or claimed. F1 owns the resulting resident-liveness,
capacity-safe recovery, interaction-monitoring, and deduplicated-alert tasks.

F1 explicitly inherits:

- the T1.5 pass-3 deletion/rollback failure: coordinated erasure of all mutable
  attempt/claim/effect projections can mint a second attempt and effect;
- a production effect-owner/WBC monotonic consumed-grant/idempotency authority
  outside caller-writable SQLite, including authenticated reconciliation of
  missing local state and no redispatch after deletion or rollback;
- the production fixed-socket owner operations missing from the bounded model:
  owner-issued occurrence target/ref, quiet transition, due selection,
  `accepted_state_version`, and exact-occurrence wrapper handoff;
- generic T1.5 dynamic recovery-topology closure beyond the installed
  operational resident/fixer path;
- supervised resident liveness, ENOSPC-triggered bounded safe recovery,
  synthetic interaction availability monitoring, and exactly one deduplicated
  outage alert per outage epoch plus a separate recovery transition;
- restoration of meaningful subject-specific retirement/no-side-effect proofs
  for all 28 historical modules / 674 functions / 741 cases;
- platform T1.7 storage adoption and remaining T1.8/T1.9 owner/store
  generalization; and
- full T1.10 notification key rotation, reminder/chunk/child-key policy and
  auxiliary-writer retirement.

F2 explicitly inherits:

- the paused T1.1 universal admission repair and its remaining validation;
- the paused T1.2 typed critic-attempt implementation;
- provider/server-attested model identity. The finite canary may bind the exact
  requested argv and root-custodied Codex CLI `turn_context`, but must label it
  `codex_cli_turn_context`; it is not cryptographic proof of the backend model;
- integration/generalization of the independently accepted bounded Stage-A
  T1.3 authenticated raw target-bound transport component at
  `2f1500aea1d03fbf13df5c796b17bd03d17bb79c`; this is not T1.2 attempt/model
  completion, installed production authority, release authority, or cloud
  launch authority;
- generalized T1.4 graph repair and retry policy; and
- universal T1.6 effect-family migration plus the full release evidence matrix.

The operational candidate must record these as typed
`NOT_CONSUMED_OPERATIONAL_CANARY` exclusions with no capability or completion
claim. The T6.2 handoff must bind their exact deferred status and preserved
worktree/evidence locations so the epic cannot silently drop them.

## Capacity and isolation cut

T0.3 is intentionally split rather than silently waived:

- **Prelaunch bootstrap:** re-observe the stopped predecessor and exact runtime,
  fence every background path, reclaim only typed dangling builder cache, prove
  the receipt reserve/free-space floor, and create one fresh mode-0700 canary
  bind source. Mount only that child at `/workspace`; never expose the preserved
  parent or sibling workspaces to the model. The trusted runner remains root,
  but every model/tool subprocess runs as a dedicated unprivileged UID with
  no-new-privileges, no effective capabilities, fresh phase-local Codex state,
  root-owned non-writable source/engine/state, and only one precreated output
  inode writable. Bind the exact host source, access identity, privilege vector,
  and container destination into deploy/run/stop receipts.
- **F1 follow-up:** durable reserved-capacity ownership, quotas/watermarks,
  ENOSPC/corruption/crash behavior, lifecycle retention, broad Docker/storage
  reclamation, and physical minimal-image enforcement.

The bootstrap may not delete the stopped predecessor, historical workspace,
images, named volumes, or arbitrary cache. A capacity failure remains a hard
NO-GO and the predecessor remains stopped and recoverable.

## Prelaunch and stable-exit cut

The closed-schema `prelaunch_release_gates` in `custody-manifest.json` are
T6.2 prerequisites, not F1 work. They require an independently accepted exact
finite-canary candidate whose implementation/manifest identities live only in
the gate's accepted evidence; a fixed root-owned symlink-free host control-state
directory;
bounded all-eight-unit settlement and crash-safe fencing before reclaim;
durable failure/reconciliation evidence; the built-image four-phase smoke;
fresh live capacity/predeploy authority; a finalized-then-stopped finite canary;
and remotely anchored custody reconstructed from a fresh clone. Pending null
evidence is deliberately non-authoritative and keeps the route closed.

The global containment marker v2 is deliberately transaction-independent. It
contains exactly `schema/profile/scope/active` and is published only after
durable unit/job/session/process proof. The same canonical marker may support a
fresh retry only after that containment is durably re-proved. Transaction
identity belongs instead to each attempt's intent and apply/verify/failure
receipts, which bind `transaction_id/transaction_digest/action`. Before the
trusted directory opens and the intent persists, failure performs no mutation,
fails closed and is captured by the supported caller error path; after intent,
every partial or post-prune failure requires a durable O_EXCL host receipt.

The follow-up chain may start only after both the strict finite-canary receipt
and `stable-exit-receipt.json` exist. Stable exit means the exact v2 predecessor
is preserved, stopped and persistently fenced; the exact v3 successor reached
`finalized` and then stopped; no recovery/notifier/resident/watchdog/timer job,
session or process remains; the exact source/tree/image and live receipt set are
bound; and the updated follow-up authority is pushed under namespaced custody,
prelaunch/postcanary tags and a runnable integration ref with an independently
accepted fresh-clone reconstruction receipt.
