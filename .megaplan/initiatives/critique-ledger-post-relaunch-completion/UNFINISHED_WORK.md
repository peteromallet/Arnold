# Unfinished-work custody ledger

This is the mandatory handoff from the bounded Critique Ledger v3 canary into
the post-relaunch completion epic. An item leaves this ledger only through an
independently accepted completion or an explicit supersession record that binds
the replacement evidence. A passing canary does not complete any item below.

Exact worktree/commit/tree/status/diff identities are in
`custody-manifest.json`. Stale or conflicting route documents and rejected
candidates are governed by `supersession-index.json`. These JSON files are the
machine-readable authority; the paths and counts below are operator guidance.

## Current handoff and action-oriented execution order

Critique Ledger is durably moving at the handoff observation: cloud session
`critique-ledger-accountability-v3-r5-20260803`, plan
`cl2-wbc-backed-ledger-20260803-1357`, product
`e5e9f2b1c1a7e7779121405fd4801768e1e8a4c2`, fresh `v3-r5` milestone
branches, isolated image
`sha256:2b6b18caeaf90ecdf6246f2c5eec5bcb9eccdb86435f66b0c3f98a5af0dce82d`
and runtime `82a5a012fa58f44cdc5e9e895f454d86d95b446d`. The selected
profile is OAuth-backed all-Codex because a direct DeepSeek key was absent.
Prep succeeded at `2026-08-03T14:04:08Z`; plan succeeded at `14:11:40Z`;
critique began at `14:11:49Z` and six `gpt-5.6-sol` high workers produced fresh
outputs through `14:15:21Z`. The tmux and chain process were alive at the bound
observation. This is real progress, not whole-chain completion. Observation is
degraded: two launches reused the same minute-resolution plan ID, `introspect`
rejects their merged journal, and outer chain status remains stale at
`initialized`. PR #325 is open at head
`a73b2760369aa99f28bb02d41003325369bed6fa`; CI run `30820387356`, job
`91708543510`, is red because two initiative documents are outside canonical
artifact directories. Do not report “no current failure” from a stale observer.

The resident is separately healthy: epoch `discord-enospc-20260803-r7`,
container
`a2c9a0d058af24ec38b05f2c8a1d2865c6120420faa4802d4cd9a740eaed9b1a`,
image
`sha256:78474208a513bfa03c51d6e04f3d31381ae07305b1c291db112098c05ba82c20`,
runtime `31d2e052104a57eb48e782dce8bdf678e6731caf`, receipt
`healthy/discord_ready`.

Execute the following as a task board. Items in the same wave may run in
parallel; a later wave waits for its named dependencies. `VERY HARD` marks
work expected to need adversarial design/recovery testing, not work that blocks
supervision of the live Critique run.

### P0 — immediate security and live custody

- [ ] **URGENT — rotate exposed resident credentials.** A diagnostic command
  accidentally printed the resident environment file in a tool transcript.
  Rotate every credential contained there, update the admitted secret source,
  prove the old values are rejected, and restart the resident once through its
  supported receipted path. Never copy any secret value into evidence or this
  epic. This can run in parallel with passive Critique supervision.
- [ ] Supervise r5 without redeploying it: retain periodic exact
  plan/tmux/process/worker/runtime observations, record every milestone
  transition, and intervene only on a new evidence-backed failure.
- [ ] Capture the final r5 completion or terminal-failure receipt and update the
  custody manifest. Dependency: live r5 reaches a terminal state.
- [ ] **P0 — reconcile live PR custody before any advance/success claim.** Keep
  the content of `annexes/wbc-integration.md` and `validation/m6-end-to-end.md`,
  move it to canonical initiative artifact locations, and prove the exact PR
  #325 head and required checks are green. Consume accepted r5 CL2 work in F0/F3;
  never create a duplicate implementation dispatch, branch, PR or publication.
- [ ] **P0 — record observation degradation without stopping healthy work.**
  Bind the plan ID, both journal prefixes, chain process, tmux, active workers,
  PR head and observer errors in the r5 terminal handoff. A projection failure
  is not a product failure; intervention still requires dead process/tmux,
  terminal plan failure, vanished workers with no output, or a real stall.

### P0 — invalidate and dependency-close the historical M11 acceptance

Commit `d10b0fef2b6dbc283639ca14adf6790153ebd2a6` was promoted as M11
completion while its own committed `evidence/ownership-decision-record.json`
had `blocker_count=4` and its `evidence/f01-f17-completion-index.json` kept all
seventeen scenarios provisional and action-off. The acceptance generator's
fixed evidence set consumed neither file. Preserve the commit as immutable
history, but its completion/promotion claim is invalid until dependency-closed
revalidation passes. Exact source hashes and the acceptance-consumption gap are
frozen in `evidence/m11-acceptance-dependency-gap-20260803.json`.

- [ ] **P0/F1 PREREQUISITE — append the invalidation.** Reuse the existing Run
  Authority append-only decision mechanism to supersede the old completion
  claim. Do not edit/delete the commit, rewrite the evidence files, create a new
  status store, or let a projection assert invalidation/acceptance.
- [ ] **VERY HARD — zero-blocker dependency closure.** Regenerate the ownership
  decision from exact current sources and require zero blockers plus accepted
  predecessor dependencies. Bind candidate HEAD/tree, source/runtime revision,
  acceptance/proof-map inputs and both formerly omitted evidence files by exact
  SHA-256. Any mismatch or missing dependency is typed NO-GO.
- [ ] **VERY HARD — replace provisional/action-off with real proof.** Every
  F01-F17 row must carry non-provisional controlled-live evidence or an exact
  independently justified inapplicable negative control. Shadow, synthetic,
  action-off, mocked status, process liveness and test success alone never
  substitute for a live authority/effect receipt.
- [ ] **VERY HARD — controlled canary plus negative controls.** Run one narrowly
  admitted live canary through existing Run Authority/Custody/WBC, prove the
  intended effect exactly once, and prove negative controls produce zero bypass,
  duplicate, unowned or stale-generation effects. An independent verifier
  rereads current owner records and exact source bytes.
- [ ] **F1 ACCEPTANCE GATE — publish the superseding completion proof.** A new
  content-addressed M11 revalidation manifest must consume the entire dependency
  closure, including both formerly omitted files. Only its green superseding
  Run Authority decision retires the invalidation and permits F1 acceptance.
- [ ] **AUTOMATION HOLD — fail closed until green.** Do not re-enable any legacy
  repair-loop, managed-child automatic repair, watchdog direct repair fallback
  or meta-repair loop before the exact revalidation manifest and superseding
  decision pass. Manual toggles and projection-only overrides are forbidden.

### P0.5 — later r5 CL2 failure: immediate repair versus deferred hardening

The previous live-handoff observation was superseded later on 2026-08-03. CL2
blocked in critique at `14:56:06Z`, and the accepted repair request then
recorded a phantom L1 launch at `15:43:11Z`: the claim owner PID is dead, the
claimed managed manifest never existed, the active claim was never transferred
to a managed process, and the repair goal remains active with that nonexistent
manifest as its owner. The exact read-only evidence is frozen in
`evidence/r5-cl2-repair-control-incident-20260803.json`. This is a repair
control-plane failure, not proof that a fixer ran slowly and not proof that the
Sol critic failed to do useful work.

The immediate root-repair branch
`fix/watchdog-report-jsondecode-r5-20260803` is already addressing the bounded
live-unblock slice below. Its unmerged code and tests are **not** accepted,
installed, deployed, or F1 completion evidence. F1 consumes the integrated
result only after exact-r5 regression proof and owns the cross-pipeline,
installed-image, restart, response-loss and durability generalization. These
tasks refine existing F1 claims; they do not add or renumber the closed fifteen
deferred obligations.

- [ ] **IMMEDIATE ROOT — launched/dispatched truth firewall.** An attempt may
  say `launched` and a decision may say `dispatched` only after a real managed
  process exists, its immutable manifest validates, its PID is live, and the
  blocker claim is atomically bound to that exact run. A no-op, unchanged,
  exhausted, rejected or merely occurrence-recorded `simple_fixer` outcome is
  not a launch. Launch failure releases or settles custody and writes one typed
  terminal/retry record; it never fabricates its own trigger PID or a future
  manifest path. Immediate branch: implementation and focused tests in
  progress. F1 remainder: every shipped dispatcher, installed runtime and
  recovery layer proves the same invariant under crash/response loss.
- [ ] **IMMEDIATE ROOT — supported stale-claim/active-goal settlement.** Add one
  typed operator surface that resolves the exact request/blocker, verifies the
  recorded owner identity and dead PID plus absent managed binding/manifest,
  compare-and-swap releases or terminally seals the claim, and reconciles the
  active goal before the same accepted request is retried. It must never require
  deleting queue files, editing markers, synthesizing a manifest, or invoking a
  manual trigger that creates a second occurrence. Immediate branch: exact-r5
  settlement path in progress. F1 remainder: actor-neutral public CLI/API,
  restart/reboot races, PID reuse, delayed writes and installed-host proof.
- [ ] **IMMEDIATE ROOT — repair-phase gate cannot consume a stale result.** The
  live plan has `resume_cursor.phase=critique` while `phase_result.json` is the
  prior successful `revise` result. `recover-blocked` must validate the exact
  deterministic-failure fingerprint and 40-character repair commit at target
  HEAD regardless of an older phase result; a result whose phase/invocation
  does not match the cursor is historical evidence, never recovery authority.
  Immediate branch: handler/control-binding fix and regression in progress. F1
  remainder: installed compatibility and all phase/cursor combinations.
- [ ] **IMMEDIATE ROOT — current failure outranks stale prior failure.** The
  three observed validation messages were distinct, but auto recovery reused
  the first prior failure when computing every signature and falsely latched
  `deterministic_phase_failure`. Current phase stderr/output must outrank the
  captured prior failure; the prior message is fallback only when the current
  attempt emitted no diagnostics. Immediate branch: incident-shaped regression
  implemented locally (distinct errors do not latch; identical errors still
  latch at the bound), pending integration. F1 remainder: installed and
  cross-phase conformance.
- [ ] **IMMEDIATE ROOT — reconstruct and promote the parallel aggregate.** All
  nine current per-check and producer-v2 payloads validate, while aggregate
  recovery ignored them and persisted only raw sentinel `parallel`. Bind every
  child to one critique invocation/attempt, reconstruct the aggregate in stable
  requested-check order, validate and atomically promote it, and report exact
  failing child IDs, paths and digests when reconstruction is impossible.
  Immediate branch: reducer/promotion regression work exists, pending accepted
  integration. F1 remainder: provider matrix, crash/late-writer isolation,
  installed parity and bounded artifact retention.
- [ ] **VERY HARD — F1 shared inner/outer occurrence retry budget.** The
  Finalize repair consumed one inner recovery call, yet outer auto launched a
  third call because the two layers owned separate counters. Put initial phase,
  inner repair/replay and outer auto behind one durable CAS ledger keyed by
  run/incarnation/occurrence/state-version/phase/failure fingerprint. Permit one
  initial call plus one shared repair or replay, never one retry per layer. A
  valid repair artifact promotes without another model call. Restart, response
  loss, timeout, observers and concurrent claimants cannot replenish or
  multiply the budget. Contract:
  `finalize-output-artifact-handoff-shared-retry-contract.json`.
- [ ] **VERY HARD — F1 receipt-aware artifact archival and cleanup.** Never
  broad-glob, move or delete `critique_check_*` producer/raw artifacts: active
  `critique_custody_v1.json` and `critique_custody_v2.json` receipts name and
  hash those exact bytes. Derive and freeze an immutable exact-path/SHA-256
  keep-set only from validated active receipts; preflight every source and
  destination; copy into a content-addressed non-destructive
  archive; read back exact bytes; fsync an append-only archive manifest; then
  revalidate every active receipt against its original or manifest-bound
  archive path. Originals remain by default. Any later deletion is a separate
  owner-authorized transaction and ambiguity means no delete. Negative and
  mutation tests must prove a broad `critique_check_*` cleanup cannot orphan
  either receipt version, including late writers, path escape, collisions,
  missing manifest rows and hash changes. Contract:
  `artifact-archival-projection-cleanup-contract.json`.
- [ ] **HARD — F1 escalation sidecar root normalization and evidence
  migration.** During v2 escalation terminalization, a feature-gated disabled
  no-op was followed by one noncanonical nested write at
  `repair-data/escalations/escalations/escalations.jsonl`. The canonical
  `SUPERSEDED` event was then correctly appended as seq 635 at
  `repair-data/escalations/escalations.jsonl`, and consumers ignore the nested
  file. Replace raw/path-specialized roots with a typed `repair-data` root and
  one canonical builder; reject doubled segments before open and attest the
  resolved target. Quarantine/migrate the noncanonical record with exact byte,
  size and SHA-256 readback plus an append-only manifest. No hand deletion,
  consumer auto-discovery, canonical rewrite/renumber or duplicate terminal
  event. Test over-specific roots, doubled segments, traversal/symlink escape,
  restart and 200 polls. Contract:
  `escalation-sidecar-path-normalization-migration-contract.json`.
- [ ] **F1 authoritative failed-attempt projection cleanup.** Rebuild current
  attention only from canonical lifecycle, supersession and incarnation
  records. Exact r5 may be the one current subject; retired r2-r4 attempts stay
  queryable as immutable terminal history but never appear beside r5 as
  current attention. Missing or conflicting authority returns typed degraded
  ambiguity rather than choosing “latest.” Prove idempotence across restart and
  200 unchanged polls, zero duplicate-current rows, zero history loss, and zero
  repair/relaunch/delete/notification effects.
- [ ] **F1 — canonical observe-only full report and durable publication.** One
  read-only command must join plan/chain state, incarnation, live worker,
  repair request/decision/attempt, claim owner, goal, managed manifest and
  bounded logs into a content-addressed report without mutating, cancelling,
  reclaiming or relaunching anything. Discord `/whats-cooking` and operator
  status consume that same report. The interaction acknowledges immediately;
  a durable supervised job completes collection and publishes at most one
  version-keyed result, surviving client timeout/restart. A degraded source is
  explicit in the report, never converted to `no failure`, `stalled`, or a
  phantom agent. This remains post-relaunch F1 hardening except for any minimal
  report fields required to prove the immediate r5 repair.

### P1 — launch admission hardening (parallel implementation lanes)

- [ ] **VERY HARD — F2A provider-policy/execution-binding seal.** After F1
  owner/recovery and F2 admission/model primitives, execute the dedicated
  `f2a-launch-profile-artifact-drift-containment` milestone before F3. Freeze
  the exact epic-level intended profile/provider/phase map; compare the fully
  resolved map before spawn and refuse unexpected all-Codex or any other
  substitution. Canonicalize/upload first, read back exact remote bytes, then
  persist the execution binding and spawn. Deterministically contain and kill
  wrong-profile workers by cgroup plus process-start identity, roll back to the
  last approved still-admissible map/binding, and relaunch once under a durable
  idempotency key. Notify only when bounded repair fails, is unsafe or exhausts.
  Registry-closed source/wheel/installed/cloud tests cover every production
  pipeline and launcher, not only Megaplan. Contract:
  `provider-policy-execution-binding-contract.json`.
- [ ] **VERY HARD — F2A cross-pipeline provider-schema dialect family.** Keep
  response enforcement independent of tool mode. Bind immutable canonical
  schema bytes, exact provider wire-schema bytes (or explicit null for local
  strict JSON), compiler version/source hash, provider/profile/model,
  runtime/image and real-canary receipt before the first provider call. Preserve
  dynamic `finalize`, `feedback` and `loop_plan` maps without semantic rewrite;
  unsupported provider keywords fall back to canonical local validation.
  Deterministic `provider_contract/schema_error` gets one phase invocation and
  at most one provider call, no generic/model fallback, one provenance-safe
  singleton fixer or fail-closed manual review, and exactly one commit/failure-
  bound post-repair retry. Process/host restart and response loss preserve the
  occurrence, claim, retry and notification budgets. Require a fresh installed
  cloud Codex canary plus registry-closed source/wheel/installed/cloud tests for
  every production pipeline, model phase, provider, profile, runtime and
  launcher. Historical M9 mutation fixtures and current r5 commits remain input
  evidence, never acceptance. The real canary must run after deployment at the
  exact final deployed/tested/receipted commit: `18b279f5ef...` or a descendant
  that proves `18b` ancestry. An earlier `b168edbca0...` canary is rejected.
  Contract:
  `provider-schema-dialect-family-contract.json`.
- [ ] **VERY HARD — F2A explicit phase-output artifact handoff.** The observed
  Sol repair wrote a valid 72,328-byte `finalize_output.json` (SHA-256 prefix
  `af6149be`, 28 tasks, 29 coverage rows, feasibility admitted), but Codex `-o`
  returned a 339-byte receipt and `local_strict` validated that receipt instead,
  rejecting required Finalize fields. Every registered phase/agent/executor
  must declare one output channel before dispatch. Bind and read back the exact
  artifact path/generation/size/full SHA-256/schema, classify `-o` as transport
  receipt only, and atomically promote the artifact once. Missing/stale/wrong-
  path/mutated artifacts fail typed with no receipt fallback. Capture the full
  SHA extending `af6149be` before acceptance and test source/wheel/installed/
  cloud plus restart/concurrency. Worker capture must use pre-handler
  `FINALIZE_MODEL_OUTPUT_SCHEMA`, not enriched product `finalize_capture.json`;
  prove handler-only enrichment and that template reset never erases a
  receipted candidate. Joint F1/F2A contract:
  `finalize-output-artifact-handoff-shared-retry-contract.json`.
- [ ] **HARD — F2A long inline prompt/path-probe safety.** Harden
  `_normalize_stdin_text` so probing a long, single-line inline prompt as a
  possible path catches `OSError`, including `ENAMETOOLONG`, and returns the
  original prompt byte-for-byte. Cover a real overlong OS path probe,
  monkeypatched `Path.is_file`, long Unicode, newline bypass and ordinary short
  prompt files. Once a real file is established, a read failure is a typed
  prompt-input error—not silently reinterpreted inline text.
- [ ] **HARD — F2A ephemeral Codex usage/cost provenance.** Locate each
  ephemeral call's exact rollout from its structured thread/session ID or a
  bounded invocation/time-window correlation under the bound `CODEX_HOME`, then
  bind rollout hash, observed model, token totals, pricing status and cost. If
  that evidence cannot be located/read, emit typed `usage_status=unavailable`
  plus search/session/rollout observations. A numeric compatibility `$0` is
  non-authoritative and must never silently mean zero usage or observed model.
  Concurrency, malformed/unreadable rollout and crash/restart tests prevent
  cross-binding or reuse of an ephemeral session.
- [ ] **HARD — provider credential admission.** Before dispatch, prove every
  selected provider credential and auth mechanism is available. A missing
  selected credential is typed no-spawn; it never silently authorizes an
  all-Codex, all-Claude or other replacement map. A different profile requires
  an explicit reviewed new policy version and digest.
- [ ] **HARD — fresh branch/spec lineage admission.** Require a never-reused
  generation workspace/session and milestone branches, full immutable source
  revisions, coherent spec/config lineage, and explicit supersession of stale
  plans before `--fresh` can mutate.
- [ ] **VERY HARD — missing/ambiguous chain-owner and no-seed hardening.** A
  missing, conflicting or ambiguous owner must fail before initialization;
  seedless and composed-chain paths need hostile composition tests proving no
  branch/plan can be inherited or attached to the wrong generation.
- [ ] Make clone/setup a synchronous completion contract: launch may not report
  success until checkout, credential seed, identity, `gh` auth and remote
  setup have either completed or emitted one typed terminal failure. Git tokens
  travel over stdin, never argv/logs/remotes; credential storage is owner-only;
  bot identity is fixed and nonsecret; Git transport auth and `gh` API auth are
  proved separately with push plus PR read/write smoke. Omit any prerequisite
  and initialization must fail. Repeat in a restarted fresh container.
- [ ] Eliminate duplicate launch-owned environment. One declarative owner sets
  runtime selectors; reject `.cloud-hot-env`, inherited `PYTHONPATH` or other
  late overrides that disagree with the pinned runtime.
- [ ] Enforce the read-only-runtime/writable-CWD invariant. Imported and
  editable runtime/source remain identical and non-writable while the worker's
  declared working tree is the sole writable product surface.
- [ ] **HARD — validate tracked symlink escape.** Admission must inspect tracked
  links without following them and reject any path that can escape the exact
  admitted source/workspace, with real Git fixtures and container tests.

### P2 — failure, notification and resident control planes

- [ ] **VERY HARD — durable notification occurrence/state-version dedupe.** A
  terminal incident owns one durable occurrence plus accepted state version;
  200 unchanged polls, process restart and host restart produce at most one
  provider effect. A genuine new version or recovery is a separate transition.
  Dependency: production occurrence owner/storage contract.
- [ ] **VERY HARD — provenance-safe generalized fixer.** On a recognized
  recoverable failure, create at most one mutation-authorized fixer with a
  durable delegation/launch receipt, exact prior failure/evidence paths and a
  bounded action budget. Missing provenance emits zero fixer and one terminal
  diagnostic—not a phantom agent or repeated escalation. Dependency: consumed
  grant/idempotency owner; may be built in parallel with notification dedupe.
- [ ] **VERY HARD — F1 container-neutral liveness lease and observer
  convergence.** The live r5 runner in container `782c6da...` remained live,
  while resident `a2c9a0d...` used local tmux/ps/`os.kill` against a foreign PID
  namespace, falsely called the process dead, mishandled a fresh heartbeat,
  excluded the active attention row and left the watchdog stale/masked. Publish
  one owner-authenticated shared CAS liveness lease binding session, runner
  container/generation, PID/time namespaces, host boot, run/incarnation,
  process-start identity, lease/fence and monotonic authority freshness. A
  foreign process probe is unknown, never negative authority. Fresh-heartbeat/
  matched-process contradictions are typed degraded and cannot independently
  trigger recovery. Resident/runner restart, container replacement, stale/
  spoofed heartbeat, concurrent observers and 200-poll tests prove exactly one
  active projection and one recovery occurrence maximum. Keep the scoped old-
  wrapper missing `repair_delegation` module and preexisting checkpoint `0 <= 9`
  as separate input evidence; neither may mask the run nor serve as runner-death
  proof. Evidence:
  `evidence/r5-cross-container-liveness-observer-defect-20260803.json`.
- [ ] **HARD — reconcile M7 projection cursors.** Make fresh-generation resets
  either advance or explicitly fork projection history. A cursor mismatch must
  be repaired from canonical state or become one actionable incident; it must
  not repeat as a warning on every append. Replay the live exact-`18b` runtime-
  rebind fixture where the persisted chain-state projection cursor said 645
  records and the rebound canonical source said 630 while canonical state
  remained intact. Bind cursors to source store, epoch, incarnation, runtime,
  count and digests. A new epoch atomically supersedes/rebuilds; a same-epoch
  regression is typed degraded and mutates nothing. Crash/restart is idempotent,
  old history remains inspectable, 200 polls dedupe the incident, and neither a
  projection nor hand-edited cursor may authorize repair, relaunch, completion
  or publication. Evidence:
  `evidence/r5-m7-runtime-rebind-projection-cursor-mismatch-20260803.json`.
- [ ] **VERY HARD — event-incarnation/checkpoint and status convergence.** Two
  legitimate fresh launches in one minute reused the minute-resolution plan ID
  and collapsed into one invalid journal (`0..9` followed by `0..N`), while
  transaction IDs also collided. `megaplan introspect` aborts with
  `EventCheckpointError: non-monotonic event seq beyond checkpoint: 0 <= 9`.
  At the same observation, `megaplan trace` reads the journal and shows fresh
  30-second plan heartbeats, `megaplan status` reports `prepped/plan` with a
  healthy worker, while `megaplan chain status` still projects
  `last_state: initialized`. Make store incarnation part of every checkpoint
  and projection cursor; reset/fork atomically on incarnation change; make all
  supported observers return the same canonical lifecycle/active-phase tuple
  within a bounded lag. Replay the exact two-incarnation fixture and prove
  `introspect`, `trace`, `status`, `doctor`, cloud status and chain status never
  crash, silently skip binding checks or disagree past the declared lag. Add a
  per-session fresh-launch lease; reap the previous process tree before reset;
  give each launch and event an immutable incarnation ID; include incarnation
  in transaction identity; sequence strictly within an incarnation; rotate
  journal/checkpoint/projections atomically; and make rapid same-minute launches
  either distinct or one typed conflict. A degraded reader returns typed
  `OBSERVATION_DEGRADED` evidence and never infers `stalled` from its own fault.
- [ ] **HARD — repair M9 work-ledger transition emission.** `auto.py` currently
  passes `transition` both explicitly and inside metadata, producing
  `TypeError: emit_transition() got multiple values for keyword argument
  'transition'` after phases. Strip reserved fields before forwarding; prove
  every phase emits exactly one idempotent transition with no warning or hole.
- [ ] **HARD — resident pre-fence admission and diagnostics.** Before changing
  source restart policy, perform every read-only source/image/runtime/secret/
  capacity check. Emit the exact failed stage and rollback proof; never collapse
  `secret admission`, `runtime capture`, `image dependency`, `Discord ready`
  and `rollback` into one generic failure.
- [ ] Bump the resident receipt schema for `resident_image_id`, keep a defined
  reader/migration for v1, and validate separate exact source/resident images.
- [ ] Lock resident and recovery-image dependency versions with hashes; prove
  `discord.py`, YAML and all listener imports from the built immutable image,
  not an ephemeral container install.

### P3 — integration and release

- [ ] Join P1/P2 manifests, run cross-pipeline composition, response-loss,
  restart, replay, event-incarnation/checkpoint, observer-convergence, ENOSPC
  and installed-image tests, and independently review the result. Dependencies:
  all P1 and P2 items.
- [ ] Execute the ordinary F1/F2/F2A and CL2-CL5 milestone work below, deploy it,
  and complete the 24h/72h/7d observations. Parallelize only work explicitly
  separated by accepted manifests; effect-owner and release-authority work
  remains ordered.

## Preserved finite-canary history and deferred evidence

The checklist below remains historical/deferred custody. Its obsolete missing
safe-v3 completion and stable-exit receipt paths are not executable launch
preconditions for this recut follow-up chain and must never be fabricated.

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
  Sol acceptance remains unrecorded; the later failed live attempt does not
  retroactively satisfy that evidence gap or make B27 F0 authority.
- [ ] Import B27 live attempt 1's already-terminal/reconciled run receipt. Its
  declared SHA-256 is
  `710707648e66e37b2c57684faa135eb324f36b163796d45210763657ad6d4e17`
  and digest is
  `ac95bf39a39c946b73a56a08625d8d15e57f8673764365c0d4ad3354826085bd`;
  no receipt path was supplied locally. Status and terminal state were both
  `failed`. Dispatch integrity was `partial`: exactly one plan start dispatch
  used Codex `gpt-5.6-sol` high, and no terminal dispatch occurred because the
  finite-model boundary failed.
- [ ] Preserve B27's reported `plan_v1_raw` root-evidence excerpt:
  `finite model boundary failed: CliError:finite-model runtime contains a special or linked object | CliError:source object is not trusted-owner non-writable: .../.zero-recovery-plan-worker-output.json | CliError:plan artifact permissions are unsafe...`.
  The output itself remained empty, uid/gid 65532, mode 0600. Real Codex had
  created an AF_UNIX IPC socket under isolated `CODEX_HOME`, unlike the offline
  fake; the runtime validator rejected the socket before reclaiming output,
  which caused the two ownership/permission errors to cascade.
- [ ] Preserve B27's terminal containment evidence: container ID prefix
  `c6289bc3` stopped at exit 137 with OOM false and `reconciled_stop` true; the
  old workspace
  `/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-20260802` is
  sealed root:0700 and preserved; no loop started and no notification was sent.
- [ ] Preserve A28 at `4845a10a043f7d53ea235789d2603ad3869d212a` /
  tree `5b2b48a45617f5ddae20075240f061239c884ffb`. It admits only AF_UNIX socket
  filesystem objects after finite-UID process emptiness, counts them against
  the runtime bound, seals ownership/mode, still rejects symlinks, FIFOs,
  block/character devices and hardlinks, and improves exact error evidence.
  Its recorded suite result is 171 passed and 1 skipped.
- [ ] Copy and obtain Sol's independent acceptance for B28 at
  `/var/lib/arnold-zero-recovery/critique-ledger-b28-offline-smoke.json`.
  Launch `d7194ec75dd27c9dc549af603effbdc4f11371ab` / tree
  `0872e11712cb796cf0be2d65e7f4846bb54211d7` passed all five exact offline
  phases with four privilege receipts. File SHA-256 is
  `2fa22ddcaeb92bb005cf24dfd8392b2e1e72206f7290c964b52a63549ef253d0`,
  receipt digest is
  `3ec46ea9f0992d606da5f34c84d76a58c7c8650f51c79d9538d1682d78bf6d40`,
  verifier digest is
  `fa98493c808093164446284204a7ba433f18a2934137a2d98c5ecac462381d40`,
  production image is
  `sha256:c1dcccbd0381bb8d578c14b9a0edfcbb24eddf9d70c537f1063a9e065feba878`,
  and derived image is
  `sha256:5677ed0b6a888be55ce4aaf1cedbfc57d3037f1e55b6ca1e8e19067029f99476`.
  Sol acceptance remains unrecorded; its later terminal failed-live receipt
  does not retroactively satisfy the independent gate.
- [ ] Import B28 live attempt 2's already-terminal/reconciled receipt. Its
  declared file SHA-256 is
  `1f39fc0bc54958b127016b08a0778dece85f2900e30defbd40dfc39d6de00dad`
  and digest is
  `2f682fe966d45dfc71527284259cea98e34876d79ac49797603261f5aee102cf`;
  no local path was supplied. It made exactly one plan-start dispatch, then
  failed with terminal state `failed`. Exact reported primary raw evidence is
  `finite-model runtime contains a forbidden or linked object: /run/.../home/.codex/tmp/arg0/codex-arg0ZLod2y/codex-execve-wrapper mode=0o120000 nlink=1`.
  Real Codex created this temporary arg0 wrapper symlink, which the offline fake
  did not model, followed by the same two output ownership cascades.
- [ ] Preserve B28 containment: container
  `megaplan-cloud-agent-finite-canary-2`, ID prefix `84a022`, stopped exit 137,
  OOM false and `reconciled_stop` true. Attempt-2 workspace
  `/opt/megaplan-cloud/workspace/critique-ledger-safe-v3-canary-attempt-2-20260803`
  is sealed root:0700 and preserved.
- [ ] Preserve A29 at `dcebf3749a1b25d2c4aac23223e5bc99280dd432` /
  tree `b849184abf77d10491a40e252fa2587112ad72ab`. It accounts symlink target
  bytes without resolving the link, unlinks the link itself only after finite
  UID process emptiness, leaves the external target untouched, and continues
  to reject FIFOs, block/character devices and hardlinks. Its recorded suite
  result is 172 passed and 1 skipped.
- [ ] Copy and obtain Sol's independent acceptance for B29 at
  `/var/lib/arnold-zero-recovery/critique-ledger-b29-offline-smoke.json`.
  Launch `234dab1d37ff3dd9363f4e381cf0f4556d34d966` / tree
  `ab078643d37e74a4a6ff173dfd9904cfa3c2b3e0` passed all five exact phases
  with four privilege receipts. File SHA-256 is
  `2b32f71a5cf20bf3ef14774f47d3cd6aa0ed1bf2d836df6d1863478c6323e70b`,
  receipt digest is
  `3877c42171d7d7a96935631d6202dd2ccdf4a4943515d57f3e77b60fa6c6092b`,
  verifier digest is
  `f785eca5a73c1809ed7f8151e724082dc7da9e6f7b359137e2c2e99dfcca03f9`,
  production image is
  `sha256:ddec86ad159adc1c464a7373292ab3ee7bd0cb08555418167f619096d81ef64e`,
  and derived image is
  `sha256:231c9ff9bfdcd1a1b54b305ca8c74ab7df63067b4501e4c33923cb6a4bc319fe`.
  Sol acceptance remains unrecorded; its later failed live run does not satisfy
  the independent gate.
- [ ] Import B29 live attempt 3's already-terminal/reconciled receipt. Declared
  file SHA-256 is
  `81295354cb68fe743c952f64c332d4d34a883daed6cacc68062904ad7584cb11`
  and digest is
  `243d9ee2d979a296235983faa6058e94142e674b3c12045f1d44fd229e5df89c`;
  no local path was supplied. It progressed past socket/symlink classification
  but plan exited nonzero. Exact primary raw evidence is
  `finite model boundary failed: PermissionError:[Errno 13] Permission denied: '/run/.../home/.codex/tmp/arg0/codex-arg0O2caQy/codex-execve-wrapper'`.
  Reclaim attempted unlink while the parent remained model-owned mode 0700;
  trusted root intentionally lacks `DAC_OVERRIDE`.
- [ ] Preserve B29 containment: container
  `megaplan-cloud-agent-finite-canary-3`, ID prefix `940c`, stopped and
  reconciled with OOM false; the attempt-3 workspace is sealed.
- [ ] Preserve A30 at `c717f693dbff0c1775a3f4ee06d203a9996aa5ec` /
  tree `e3dbec62223898005e57bdf03a3e2f97d023c66d`. After finite-UID process
  emptiness proof, it takes trusted ownership/mode of a directory before
  recursing, while preserving the minimal capability set and continuing to
  omit `DAC_OVERRIDE`. Its recorded suite result is 172 passed and 1 skipped.
- [ ] Copy and obtain Sol's independent acceptance for B30 at
  `/var/lib/arnold-zero-recovery/critique-ledger-b30-offline-smoke.json`.
  Launch `0bc07ba280d8832e72b6859b20ddec38060954c6` / tree
  `da191a1a9261d1b8e37bce648a7549a82c6901fb` passed all five exact phases
  with four privilege receipts. File SHA-256 is
  `068100927d60dc3b5b9c8fba4f7f814ca0548dbb4ceb8a4aebe791fd8dfd2d95`,
  receipt digest is
  `9440f30306ef63895199aa70db7ba249c634780c3a241ac99ad096fa1767fed9`,
  verifier digest is
  `0a1378cb3cbe1040f76665ec0bae29591c23e768ce9dcb4bb14334190fe7e9d3`,
  production image is
  `sha256:375ccaca36c9727cffd9ce8dab6615bbb163a5f0f62f17b06784c8044e266f6f`,
  and derived image is
  `sha256:f3d8df941bb2bb6d35e23aa3e61c10b3f16de4bd53f4edeeb28161dc40833ccb`.
  Independent acceptance remains unrecorded; the later live failure does not
  retroactively satisfy it.
- [ ] Import B30 live attempt 4's stopped/reconciled receipt. Declared file
  SHA-256 is
  `c4aa925f98ffc5a41992f2347366e6d3175e089b6982708a0e6cac0a5b021080`
  and digest is
  `482910834d106e6ee4281cb930918d7f793d17b4a1140a63a9c1b796fcc662ee`;
  no local path was supplied. Its root failure was denial reading the schema
  while it remained root-owned mode 0600. No further terminal effect is
  claimed beyond the supplied stopped/reconciled state.
- [ ] Preserve the exact schema-access lineage:
  A31/B31 `5ae02bb84b98d784cd230e69b633e89f77c95462` /
  `b0437d698a3806cfa2fed85a7e64cea99468aea5` granted model read-only schema
  access but B31 offline failed source identity; A32/B32
  `9a09b25a3f6596e641b6a88329ccb280a8957bb4` /
  `f1de9294ff19f842cdc82e3736335b5289cf2f4a` captured exact source-integrity
  diagnostics; A33/B33 `64afbf29cd381de63cdcfa07d5cb80dd44fc7acc` /
  `109fa8c2f35f3094c7c005a264a14d48390a8b08` proved 0600→0644 with unchanged
  content hash; and A34/B34 `eb057201716d4a161465669677d76fb636bddca0` /
  `c9b403d431f21174e0940433a17265a3978b9a78` passed happy-path grant/revoke but
  received independent **NO-GO** because failure cleanup was incomplete.
- [ ] Preserve A35/B35 total-cleanup lineage:
  `aa493800750e3547a78a4ef0bf00edc9ac4a9b50` / tree
  `d0ff36acc353fd95eccdb6162fcdfdde54f9abc7`, then
  `665851a8af14c895545a0b9f8d67251e0958f3c8` / tree
  `2d5e49eab5e5f27ab522accb37b97039ae1e3988`, with 177 passed and 1 skipped.
- [ ] Import B35's diagnostic pass: SHA-256
  `f68b132bfe918ed8028597f25a38330edf3c3d9e23ad924eb55d424a1307e2b8`.
  Only digest prefix `0a5d477d` was supplied; path and full digest remain
  unknown and must not be synthesized.
- [ ] Import and independently review B35's production acceptance smoke:
  SHA-256
  `901e677c85f7fd213f8e0129712f146024b36dc578225e3f86091e0f3fcae383`,
  supplied digest prefix `8668387b`, and supplied production-image prefix
  `sha256:fec327f1`. Path, full digest and full image identity remain unknown.
  The smoke passed and fresh predeploy observed GO with 1,343,115,264 free
  bytes, but independent acceptance remains pending.
- [ ] Import the outstanding failed-fence and B27-B30 live receipt bytes; no
  missing receipt may be synthesized. B27-B30 outcomes are already
  terminal/reconciled.
- [ ] Preserve B35 live attempt 9 as terminal/reconciled without inventing a
  run receipt. Container `megaplan-cloud-agent-finite-canary-9`, exact ID
  `acf086d75ef2ffd678117e09236819d3387298112b522dbc0e98ed2e4e7e2381`,
  stopped exit 137, OOM false, restart count 0. Its attempt-9 workspace is
  sealed root:0700; only transition-digest prefix `f513d54d` was supplied.
- [ ] Import attempt 9's phase evidence: init receipt SHA-256
  `bec8be741aee9444926843a251cd53027de80a5c5a9eac010219d4f841c85623`,
  plan-started SHA-256
  `de51ef7812468e8da192e2fed7e404647eec783d7f33e607a9e14a1858a347c2`,
  and dispatch-ledger SHA-256
  `f2d24e7bf3640145dcc15d70361ccb13469318acdec3b06e74b226b613f52bc7`.
  Output was empty and no run receipt exists.
- [ ] Preserve the definitive attempt-9 cause as an operator-status collision,
  not a model/runtime failure: process-adapter status began `06:30:25.420`,
  Docker stop sent SIGTERM at `06:30:26.882`, and the run exited 137 at
  `06:30:36.876`. Status cleanup unconditionally stopped and resealed the
  concurrently running canary.
- [ ] Preserve A36/B36 lineage and its terminal publication **NO-GO**: repair
  `b9a7a2d2eacca529568b625e35525762a961eda5` / tree
  `d9384fb3b9114e3d02dd4b5f66e191975819efa8` makes running status
  non-cancelling, reports `in_progress` and returns CLI success, with regression
  coverage; launch `a3288a6364fb51776f816577a5857bdebab8aa74` / tree
  `7ceb34a0a2cdd0973563d5f0c42eb4864ad85791` binds fresh attempt-10 workspace
  and `megaplan-cloud-agent-finite-canary-10` while preserving attempt 9. Its
  terminal result is not launch authority.
- [ ] Preserve A37/B37 exactly: repair
  `b8ffeb14ea408a2171ebcddc3bcda7b6188a36e5` / tree
  `dbc56fc906f4bb1976510156f464e681302534db` gates terminal publication on
  a sealed stop; launch `c4ac9e76e6665ef47c4f11f5e2f5b37bebb524bd` /
  tree `cd4ac3774fe9013751819d05bc12838b704755cd` is retained history, not current
  authority.
- [ ] Preserve A38/B38 exactly: repair
  `a965867e658193f4b3aba8fbdfa6517a653cb36b` / tree
  `f5860f777ece19caedb25426e263c169e0be324c` admits only safe capacity drift;
  launch `84e4ff29eaac7c96b2a6334c5f938015742f11af` / tree
  `e15c918e8fcb0bf4437cf534075a0c8258d725aa`. Import the exact B38 diagnostic
  and production receipt bytes currently identified only by file-SHA prefixes
  `4a9bae` and `26c217`, and the full production image currently identified by
  prefix `sha256:56402`; prefixes are not acceptance evidence.
- [ ] Preserve the accepted official reclaim-v2 result: transaction prefix
  `f0070`, 807,890,944 bytes before, 1,982,816,256 after, delta
  1,174,925,312, all eight recovery units masked, and no recovery job, tmux
  session or process. Import the exact transaction identity and receipt bytes.
- [ ] Preserve B38 live attempt 12 as terminal failed. Container prefix `cd07`
  used production-image prefix `sha256:56402`; the live owner exited 1, the
  stopped container exited 137 with OOM false and restart count 0, and the
  attempt-12 workspace is sealed root:0700 on the same inode. Run-receipt
  SHA/digest prefixes are `8dc24` / `d5d182`. The exact primary failure is
  `finite-model UID retained a process after provider return`; the later
  UID-65532 output-ownership error is downstream. Root cause is Docker
  `HostConfig.Init=null`, not an accepted provider result.
- [ ] Preserve A39/B39 exactly: repair
  `2159347ae291102dd5ec90d2aac736fc0d5a58e0` / tree
  `0b6d9b7961d03665b48b505a2738d7a3612334bb`; launch
  `11305b7c2c1891614b85322f8e0f3c766d2586d6` / tree
  `8adcb18fa955544a7a1da1777b6d9ffbb8d5b9a0`, with 187 passed / 1 skipped,
  fresh attempt-13 workspace and `megaplan-cloud-agent-finite-canary-13`.
  Diagnostic file SHA/digest are
  `c0949f6f2e40b0db1bbc6e3e251c1b701930ca2750a7cc9fcd87f4e64b4488d6` /
  `84667d967794d93dc753076350d6d34face8d755aee5251d5340629812ef4ed1`;
  verifier digest is known only by prefix `36c31861`. Production file
  SHA/digest are
  `087007324e255ebd42e82daf93781bf7032eb96bdee9643527984ce6240c6fc3` /
  `1e956fb442e06d7e0520a4f21de04a6eec246e42209e23fcd88ad0da2f72046d`;
  verifier and image are known only by prefixes `a1bf4eb8` and
  `sha256:d38b921f`. Prefixes must not be expanded or treated as full identity.
- [ ] Preserve B39 attempt 13's exact terminal safe-non-PROCEED outcome. Live
  receipt digest/file SHA are
  `72e4efaf37ea9b416cdada8e4447a30d2228d837b3029c9f163fee944bf85c11` /
  `ece98b8f99d4613dce1ec17888328a7cbc033df610d25e4855aec1b214c04b9b`.
  Real plan, critique and gate returned; gate recommendation was `ITERATE`,
  state remained `critiqued`, and eight blocking changes were recorded.
  Finalize did not run. The runner currently reports
  `unexpected_or_active_state` because state validation precedes gate
  recommendation classification; that diagnostic is not a live success gate.
  Container prefix `6cb81b` is stopped at exit 143, OOM false, after terminal
  reconciliation. The workspace is sealed root:0700 at inode 1317407 and no
  notification was sent. Its offline and independent evidence was observed at
  termination but not accepted; live is terminal-not-accepted and no
  stable-exit receipt was produced. These are immutable historical facts.
- [x] Preserve A40 as closed bounded-route authority, not a current decision:
  initial implementation `a3fe53b67564bbacd7e7d07eea737d675d4d8233` / tree
  `61205a4b2644548e0c7f3a3acb574fde0e90a611`, validator correction
  `cfab4da6877971f1517367387bd5584bb76a39e8` / tree
  `607e6a13b62e2d0b58f80bc6aeb5b4b6d5521282`, and only the exact direct
  PROCEED or one-revise ITERATE→PROCEED route. A40 cannot promote B39.
- [x] Preserve the exact attempt-14 candidate and immutable terminal result:
  implementation `a15e87adea1fa78e90008422f42bc79ae60dff13` / tree
  `63a75d9333e3fa69c9a039846595d3dd4d3cc4b3`, B44 manifest
  `006895e8d66812dec5e85d26b32635af21ca21c7` / tree
  `8d70cc79bc8f5a79a60be282bcc22122109c7f83`, production image
  `sha256:209a64de1f321b5ec49e8d6e6748187f790099a6fe8a68696352a5488bc7ffa6`,
  attempt-14 workspace/container, and all four manifest-file hashes. Receipt
  digest/file SHA are
  `59f0d1712bbd6f379d921f9662989a7a524b62e8509182041e08ba368e0abe0d` /
  `23f260ba72c0785401d4749132491beeac1bd2cf7c61cc386c7b29e980ecb3c0`.
  The exact prefix is `init→plan→critique→gate→revise`; gate `ITERATE` SHA is
  `415fb3ffac618a196d2822f288d69d9457abd6f121615c1153e34fb7404e6545`.
  Revise stopped predispatch on blocking `add_human_halt` action `NSA-7`; the
  old runner recorded ordinal 4 and misclassified the product terminal as
  generic failure with partial dispatch integrity. Finalize did not run. The
  container is stopped and workspace root:root:0700 is sealed. No F0 authority
  follows.
- [ ] Preserve diagnostic r1-r5 failures, r6 PASS, and the B44 production-smoke
  PASS exactly as recorded in `custody-manifest.json`. These smoke receipts are
  prelaunch evidence, not an invented live result.
- [ ] Complete `custody-v3-to-v4-semantic-migration` across the completion
  producer, finite-canary validator, distinct stable-exit validator, and
  fresh-clone reconstruction. Reject v3 with regression tests before launch.
- [x] Preserve exact A15/B15 attempt-15 terminal infrastructure-failure custody:
  implementation `8932873ba1c81d398cf42fb9879605d14d50cbb4` / tree
  `7fdcf11dba38354645290314443c1de3c8b33bbb`, manifest
  `4f021cb70f3202dd90d599f8d710b626ba27b16b` / tree
  `3777df403e9ae06cba75cf6fb6ac3b804f808723`, image
  `sha256:ea1e66940e7445649b083b8d7acc896080526011f9bfc4a9e21b475046e1814a`,
  exact attempt-15 workspace/container and four manifest-file hashes. Preserve
  its four root fixes: settled clean commit/tree input; fresh typed revise
  invocation; `product_revise_blocked` for human and unresolved blockers; and
  ordinal 4 only after revise dispatch. Receipt digest/file SHA are
  `59bc8d659ca8ec59baa9da9051fcd7320199e6ffea12a97d3b7018694b266331` /
  `10eb82a07ca0829b585c4316413b76851665ac9b90ef93e051f94626f91a182a`.
  It completed `2026-08-03T11:00:12.627961Z` after
  `init→plan→critique`: Sol plan returned success; Sol critique dispatch returned
  output, but the code-mode host repeatedly SIGTRAPed/closed stdout and could
  not inspect/update the template, so critique returned 1 with state `planned`.
  Gate/revise/finalize did not run. The receipt is failed/failed/partial, product
  outcome null, dispatch ledger
  `222abc464f60acf7b14689fcfef4ca8649a7746d80e3d09a600caf89988d7ded`.
  Container stopped at 143, OOM false, restart zero; workspace is sealed. It is
  not accepted and creates no F0, retry, or successor authority.
- [x] Preserve exact B16 attempt-16 terminal infrastructure-recovery custody.
  Outer status is `available`; receipt schema v3 and status `passed`; source
  commit/tree are `fb5a394878bc900b189213a3de5dcc40169d8b7b` /
  `a8f903a94e5029fa50c148df3289186dc4c39caf`. All phases
  `init→plan→critique→gate→revise→critique→gate` returned zero, dispatch
  integrity is complete and failure is null. Both gate attempts returned
  `ITERATE`; terminal state and outcome kind are `product_gate_not_proceed`,
  recommendation `ITERATE`, gate attempt 2. Receipt digest/file SHA are
  `3a9925dbfcc0c901905db0265b48c062f051b16bdbb31b9f873c5e086eac08c0` /
  `1b4e1d013f444b3f3f2c3af1bb4938002e730f727a0be39834a2ca235fa592ba`;
  state SHA is
  `4ef979066dfb3c822625de21ec52e95c7d25a42f185ea01970865d4b4116e525`;
  final gate SHA is
  `b8d6dcf366b04bde245890e1cb224c191f202101cb53dbb3fa59ca721c05d546`.
  Exact container
  `0552d39f4589239cb0b8e10b68b12c8ebab3a0e2fde6284049e1e466f0896ba6`
  is stopped at exit 143, OOM false, restart zero; stop is reconciled and the
  workspace sealed. Classify infrastructure recovery as PASSED, but never call
  this product PROCEED, finalized or a durable epic launch.
- [ ] Resolve both attempt-16 ITERATE gate result action sets before any later
  PROCEED claim. This product hardening belongs to F2 and is
  `DEFERRED_POST_RELAUNCH_NONBLOCKING`; it does not block separately authorized
  relaunch.
- [x] Resolve the v3 full-SHA bootstrap pin. The abbreviated initiative
  revision `0bb0c0b74e` was rejected before init as
  `intended_initiative_revision_unpinned`; the retry used full revision
  `0bb0c0b74e6b1913d39b51f33559b2f5127f1886` and `cloud chain` returned zero.
- [x] Preserve and contain the rejected v3 runtime-binding retry. It was alive,
  advanced beyond init and initialized `cl2-wbc-backed-ledger-20260803-1313`,
  but its execution binding split the editable root/revision
  (`/workspace/runtime-candidates/arnold-a8e7ef6c345bbc1aceb19af67e7e25b1e05ad4e4`,
  `a8e7ef6c345bbc1aceb19af67e7e25b1e05ad4e4`) from the actual import
  root/source revision
  (`/workspace/runtime-candidates/arnold-c7bcb06af536acfe759c1b31a785afc19afe92d4`,
  `c7bcb06af536acfe759c1b31a785afc19afe92d4`). The operator redeployed the
  same isolated collector to stop it. It is not a durable launch and the
  initialized plan must not be resumed or reused.
- [x] **Pre-F0 launch blocker resolved — hot-environment runtime ordering and a
  fresh matched-runtime retry.** The post-launch stability observation must
  prove `editable_root == import_root == configured pinned runtime root` and
  `editable_revision == source_revision == configured pinned runtime revision`,
  as well as exit zero, session alive and advancement past init. This is a T6.2
  precursor and does not add, renumber, discharge or accelerate any deferred
  F1/F2 obligation. r5 proved all four runtime fields at immutable runtime
  `82a5a012fa58f44cdc5e9e895f454d86d95b446d`; the exact binding is retained in
  its chain execution metadata and current operational-handoff record.
- [x] Preserve the read-only storage root-cause inventory. Post-run free bytes
  1,484,693,504 are below hard floor 1,611,661,312 by 126,967,808 bytes. The
  preserved production predecessor writable snapshot/container is approximately
  389.927 GB; `/tmp` is approximately 388.813 GB and contains exactly 1,156,578
  progress-auditor recursion copies totaling 387,889,659,906 logical bytes as
  roughly 395,629-byte `arnold-repair-loop.*` files. The installed-source
  trampoline preceded the snapshot guard; the snapshot execed source; source
  saw an active-path mismatch and created another snapshot; and the later
  cleanup trap was overwritten. Record this recursion as the confirmed cause of
  disk exhaustion and resident crash and likely—not exclusively proven—cause of
  attempt-15 code-host instability.
- [x] Preserve the separate notification and reclaim evidence. The
  notification/watchdog path, not the progress auditor, re-emitted the same
  terminal `manual_review` incident without durable incident-key dedupe. A
  separate diagnostic-fixer launch failed provenance validation. Receipted safe
  reclaim from predecessor container
  `277d2e6dbc149e01b25881350238a7b0ff5de78cc27d8ef52c144dca7c35c5ab`
  deleted all 1,156,578 copies and 387,889,659,906 logical bytes, left zero,
  restored 390,136,713,216 free bytes, and preserved predecessor and workspace.
- [ ] Add bounded repair temp lifecycle (F1, nonblocking for relaunch).
  Acceptance: every temp file has a
  bounded lifetime; the installed-source trampoline checks the snapshot guard
  before exec; and non-overwritten `finally` cleanup covers success, failure,
  timeout, signal and cancellation.
- [ ] Add repair-loop singleton and durable attempt cap (F1, nonblocking for relaunch). Acceptance: one owner
  per subject and a durable cap prevent unbounded redispatch or temp creation.
- [ ] Add disk budget and reserved headroom (F1, nonblocking for relaunch). Acceptance: repair and resident
  paths preserve capacity above the hard floor.
- [ ] Add the pre-model/tool capacity trip (F1, nonblocking for relaunch). Acceptance: every phase fails closed
  before dispatch below the reserved threshold.
- [ ] Add receipted workspace-preserving safe reclaim (F1, nonblocking for relaunch). Acceptance: reclaim is
  bounded and proves every historical and active workspace byte-preserved.
- [ ] Add a resident-only recovery surface (F1, nonblocking for relaunch). Acceptance: resident recovery has
  no general repair-loop, notification, or canary-retry authority.
- [ ] Close the independent `/whats-cooking` availability incident in F1.
  At 11:42 Europe/Berlin the Discord resident was offline after the production
  container exited on ENOSPC; restarts failed before Discord connect and no
  resident event existed. The handler defers before status collection, so this
  is not acknowledgement ordering. Attempt 14 began 27 minutes later without a
  Discord token or resident; do not claim that the canary caused the outage.
- [ ] Add resident-liveness supervision. Acceptance: an injected resident exit
  is detected and recovered by one bounded safe restart with durable receipts.
- [ ] Add capacity-triggered safe recovery. Acceptance: ENOSPC blocks restart
  loops, performs bounded reclaim, and permits restart only after accepted
  capacity proof.
- [ ] Add interaction-availability monitoring. Acceptance: a synthetic Discord
  interaction detects defer/response unavailability independently of status
  collection.
- [ ] Add one deduplicated outage alert. Acceptance: exactly one alert per outage
  epoch across restart retries, plus a separate recovery transition.
- [ ] Preserve the bounded retirement of the temporary clean B38 diagnostic
  checkout: O_EXCL intent/receipt digest prefixes `2568` / `533399`, exact B38
  commit/tree, size 128,547,498 bytes, and free-space transition
  1,611,960,320 → 1,756,692,480 (delta 144,732,160). Receipts and evidence were
  retained. This terminal retirement does not reconcile any of the five older
  immutable operations.
- [ ] Reconcile B35's still-pending independent review and every unresolved
  historical operation. Neither B38's terminal checkout retirement nor B39's
  fresh retry erases attempt 9 or authorizes redispatch.
- [ ] Produce and independently accept the canary completion, stop and
  stable-exit proofs. These remain pending even after a successful offline
  smoke.
- [ ] Copy and reconcile every available B10-B44 and A15/B15 receipt/evidence directory.
  No B8-B25 failed attempt is current acceptance authority; B26 is accepted
  offline history, B27-B30 are terminal failed-live history, B31-B34 are
  diagnostic/rejected history, B35 is passing production-smoke history with
  terminal attempt-9 history, B38 has passing diagnostic/production smoke but
  terminal failed live attempt 12, B39 is terminal safely stopped non-PROCEED
  attempt-13 history, A40 is closed, B44 attempt 14 is immutable terminal
  failed/misclassified history, A15/B15 attempt 15 is terminal infrastructure
  failure, and B16 attempt 16 is terminal infrastructure-recovery PASSED with a
  bounded second-ITERATE product non-PROCEED outcome. Attempt 16 is neither an
  infrastructure failure nor a durable epic launch. Its F1/F2 follow-up tasks
  do not block relaunch; future execution still requires fresh authority.
  No missing receipt may be synthesized.

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
- [ ] Separate the Finalize model and product schema boundaries. Prompt,
  file-artifact capture, `local_strict` and handler input must consume exact
  pre-mutation `FINALIZE_MODEL_OUTPUT_SCHEMA`; `finalize_capture.json` is a
  post-handler enriched product shape and must never be the worker
  `capture_schema`. After model-output validation, the handler alone adds
  validation/execution/baseline/custody fields and validates the persisted
  product. Bind both schema hashes and the enrichment transform. A template
  reset never erases, truncates or reseeds a receipted candidate; reuse exact
  bytes or durably supersede to a new invocation path.
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

## F2A — cross-pipeline provider-policy and execution-binding containment

- [ ] Execute the dedicated F2A brief and produce its independent completion
  manifest before F3. F2A consumes F1/F2 primitives but adds or renumbers none
  of the fifteen deferred obligation IDs. Its proof must join the registry,
  intended/resolved phase maps, exact remote and loaded byte digests, runtime
  attestation, drift/repair ledger, notification effects and the all-pipeline
  source/wheel/installed/cloud hostile matrix.

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
