---
type: decision
status: approved-planning-amendment
date: 2026-07-17
initiative: custody-control-plane
protected_through_index: 2
protected_current_plan: m6-exact-contract-and-20260716-1303
---

# F01–F17 upcoming-milestone amendment

## Decision

Adopt the current-epoch F01–F17 recommendations and ranked recommendations
R1–R3 as explicit acceptance obligations of the already-ordered pending
milestones M6A, M7, M8, M8A, M9, M10, and M11. Preserve their stable labels,
branches, intent, and serial dependencies. Do not insert a competing authority,
ledger, reducer, queue, provenance manifest, planner policy layer, or lifecycle.

This matrix is the unique recommendation-allocation index. Milestone briefs own
execution details; later milestones may verify a predecessor's output but do not
re-implement it. A row is not complete when a component merely exists or has
focused tests. Completion requires the named runtime wiring, exact-version
evidence, negative cases, and acceptance owner.

## Sources and custody boundary

- Raw current-epoch audit: commit
  `44441636f125ad490dd12adba8254462c15ea48f`, artifact
  `research/f01-f17-current-epoch-adoption-audit-20260717.md`.
- Current-run crosswalk: commit
  `b363d7d8ad9c02a04f369dd62074206fa1d6cf4d`, artifact
  `research/unified-authority-efficiency-prevention-20260714.md`.
- Required audited WBC merge evidence: byte-exact artifact from commit
  `2ac7271fb` at
  `.megaplan/initiatives/workflow-boundary-contracts/handoff/consolidation-20260714/wbc-merge-evidence.md`
  (blob `3c7ff724b837532c854576b2e9837aaa70ecf12f`). It is imported only because the
  authoritative chain already declares it as a launch prerequisite and the
  pinned target omitted it; no WBC contract, chain, manifest, or status changes.
- Related open ticket reviewed after initiative discovery:
  `.megaplan/tickets/01KTH21EXMWBHWBA62QC5Y8D3D-supervisor-stale-step-autonomous-recovery-policy.md`.
  Its surviving stale/dead-worker, bounded retry, lease, and terminal diagnostic
  cases are absorbed by F02/F11/F13/F15 below. Its obsolete touchpoint guesses
  are not implementation authority and it does not create another initiative.
- Authoritative live custody was re-read at `2026-07-17T13:58:13Z` from
  `/workspace/custody-control-plane-20260714/Arnold`. Chain
  `chain-1e998199f544.json` remained at index 2 with M5 and M5A done,
  `m6-exact-contract-and-20260716-1303` current, and `last_state: blocked`.
  The M6 plan remained `gated` with a failed finalize request at
  `2026-07-17T13:56:51Z`. Therefore M5, M5A, M6, and the finalized M6 plan
  artifacts are immutable; this amendment begins at M6A.
- Final verification re-read at `2026-07-17T14:08:58Z` still found index 2 and
  the same current plan. The plan projection had moved to `blocked` after
  another rejected finalize request at `2026-07-17T14:03:57Z`; the protected
  boundary did not move.

The canonical source imports the live North Star and protected milestone
definitions without semantic change. Their authoritative SHA-256 values are:

| Protected asset | SHA-256 |
| --- | --- |
| `NORTHSTAR.md` | `315ed6ba4db2323958448db2ec7aa81fa5ddbc140bc05823ec0de322e78c5f45` |
| M5 brief | `2e8f3f96fd360d6d5cab2a5c2ba5f8dde728d0ff576572f7296f6436cd2491b1` |
| M5A brief | `9a337ca44fd83e0e43bbb371232bcab5d414f20706cf676f15c63256b7f82ae6` |
| M6 brief | `3fea24d7120fb6dd97a0a876caff200bd9d2847d6fcae37dcb69a63b1b8ec66e` |

The live chain file's pre-amendment SHA-256 is
`e11fa65186ce7934c3ac2fd5b3b79a79ff0ed5a92f984de4b2d05e72e1b599fa`.
Only milestone entries after index 2 may differ in the amended canonical spec.
This commit does not edit live chain state, rebind the running plan, resume,
restart, deploy, promote, delete, or perform an external effect.

### Launch-time repository discovery

- Repository identity: `/workspace/arnold`, shared Git directory
  `/workspace/arnold/.git`; recorded writable target `refs/heads/main` at
  `b363d7d8ad9c02a04f369dd62074206fa1d6cf4d`.
- `/workspace/arnold` was a dirty launch checkout with extensive unrelated
  tracked and untracked work. It is evidence/source context only and is not the
  implementation checkout.
- The task-pinned resident runtime
  `/workspace/arnold-runtime-b92380231941-r2` was clean and detached at
  `6788980da951004b25686364b0d1a0426b024899`. It is runtime evidence, not the
  project mutation target.
- The authoritative live execution checkout
  `/workspace/custody-control-plane-20260714/Arnold` was on
  `megaplan/custody-control-plane/m6-authority-contract-and-residual-inventory`
  and dirty only in incident-ledger projections at discovery. Its live branch,
  plan state, and runtime artifacts are read-only for this amendment.
- Implementation uses isolated worktree
  `/workspace/arnold-custody-f01f17-chain-amendments-20260717` and feature branch
  `refs/heads/resident/custody-f01f17-chain-amendments-20260717`, initially
  based on the recorded `b363d7d…` target. Before local integration it must be
  rebased if and only if `main` advanced as a descendant of that launch base;
  movement off that lineage is the contract's approval gate.

## Dependency and recommendation allocation

The required sequence remains:

`M6 (protected) → M6A → M7 → M8 → M8A → M9 → M10 → M11`.

“Primary” owns implementation. “Adopter” wires the primary component into its
owned boundary. “Acceptance” supplies end-to-end/runtime proof and may block
retirement. These roles prevent silent omission without duplicating ownership.

| Item | Primary / adopter / acceptance milestones | Prerequisites and first safe action | Deliverables and acceptance evidence | Version, custody, replay safeguard; component vs wiring |
| --- | --- | --- | --- | --- |
| F01 exact repair occurrence | M7 primary; M10 acceptance; M6A storage prerequisite | Consume accepted M6 identity inventory and M6A store. First generate the enqueue→claim→execute→receipt→decision→terminal field matrix in report-only mode. | One immutable occurrence key and joinable terminal chain; T7/T12 cross-binding rejection and every outcome terminal. | Bind exact revision, task, attempt, signature, result, grant/fence, lease/epoch. Existing repair IDs are components, not universal key wiring. |
| F02 durable event recovery | M6A fact storage; M8 producers; M10 primary/acceptance | Requires F01 and terminal eligibility semantics. First add event/request/claim/terminal timestamps without dispatch. | Deduplicated block/exit trigger, p50/p95/p99 with denominator, p95 <5m, miss/duplicate counts, six-hour missed-event recovery. | Delivery ambiguity stays pending; scans are reconciliation only. Existing hooks/watchdog are components, not accepted recovery. |
| F03 verify-only repair adoption | M6A receipts; M7 identity binding; M8A primary/acceptance | Requires F01/F04/F15 and accepted WBC API. First freeze a non-dispatch receipt schema and drift-negative fixtures. | Same-revision receipt skips replay; code/contract/tree/test/fence drift quarantines and selects normal execution. | Never infer trust from receipt labels. Existing adopt-execution and validators are precursors, not a wired repair consumer. |
| F04 append-only attempt/effect history | M6A primary; M8 adopter; M10 replay acceptance | Requires exact WBC version and migration/data policy. First retain every schema-only producer row as residual. | Durable reserve/start-before-dispatch, one terminal or indeterminate, byte-stable attempts, deterministic alias projections. | Mutable aliases never overwrite history. WBC schema existence is not operational storage or runtime adoption. |
| F05 one reducer/cursor vector | M9 primary; M11 acceptance/retirement | Requires F04 history and M8 producer coverage. First run same-input shadow comparisons from the generated reader registry. | 100% cursor/hash agreement; torn input is `UNKNOWN`/`INCOHERENT`; rollback and zero positive authority from projections. | No second reducer. Existing reducer/views are components while raw/legacy consumers remain wired. |
| F06 append-safe projection | M7 writer adoption; M9 rebuild/reader acceptance; M11 legacy retirement | Requires F04 source history and F17 vector. First inventory writer/reader/provenance; do not rebuild the existing implementation. | 10,000 heartbeats, sequences 0..9999, monotonic concurrent reads, atomic rebuild digest parity, bytes/time, zero false stalls. | Cursor mismatch rebuilds atomically over prior readable projection. Existing writer behavior is observed, not exact-runtime acceptance. |
| F07 DAG feasibility | M8A primary/acceptance | Requires captured corpus hashes and F17. First replay Transaction/Strategy inputs report-only through existing `task_feasibility.py`. | Width/critical path/seriality/routing/turn evidence; unexplained ≥8-task full seriality rejected for new canary plans. | Never rewrite protected/live plans. Existing compiler and focused tests are not governing-runtime proof. |
| F08 split complex work | M8A primary/acceptance | Requires F07, exact attempt identity, versioned budget grant. First replay complexity-7/8/9 fixtures. | Split implementation/proof or fail admission unless signed budget exists; checkpoints survive proof exhaustion. | No implicit budget widening or lost productive work. Prompt guidance is not executor enforcement. |
| F09 deterministic harness validation | M8A primary/acceptance | Requires F07 classification and reviewed non-mutating allowlist. First prove the existing `validation_jobs` producer/consumer edge is missing, then wire it. | Reproducible command/environment/output/hash receipts and zero model calls for deterministic fixtures. | Mutating/ambiguous checks remain explicit. Existing schema/suite runner are components, not connected execution. |
| F10 source/ref admission | M8A primary; M11 universal acceptance | Requires F17 vector and ancestry. First generate the zero-exemption launcher/relauncher registry and one-read validation contract. | Invalid ref stops before provider/model dispatch within bounded attempts with typed reason; every launcher shares the gate. | Dirty/divergent/mixed revisions fail closed. Existing binding/admission guards are selective, not universal. |
| F11 typed failure circuits | M8A primary/acceptance | Requires F01 identity and F17 provenance. First produce separate report-only matrices for provider, model, import, compaction, replay, and timeout. | Per-class counters and terminal outcomes; bounded timeout/failover/compaction/replay fixtures; no duplicate effect. | Do not merge unrelated counters. Existing compressor/replay bounds cover only part of runtime wiring. |
| F12 bounded review rework | M8A primary/acceptance | Requires finalized task identity and unchanged max wave. First add the six-task regression fixture. | Route review rework through existing splitter; observe 5+1; oversized grant rejected before worker launch with identical accepted output. | Preserve dependency/revision semantics. Normal-batch splitter existence does not wire review rework. |
| F13 normalized budget circuit | M8A primary/acceptance | Requires F01 and F08 transitions. First create report-only normalization/collision fixtures. | Two equivalent `worker_budget_exhausted` occurrences block a third launch; unrelated failures do not collide. | Preserve exact occurrence and checkpoints. Adjacent recurrence circuits are not the named plan breaker. |
| F14 productive/replayed telemetry | M8A emitters; M9 primary join; M11 promotion acceptance | Requires F01/F04 keys and work-class rules. First preserve unknown baselines and denominators. | Join queue/inference/tool/git/validation/retry/compaction/repair/tokens/cost/accepted output; reconcile totals or explicit unavailable reason. | Missing never becomes zero; productive review is not waste. Existing fragments are not an authoritative joined ledger. |
| F15 atomic custody terminalization | M7 primary; M10 acceptance | Requires F01 and M6A store. First generate writer/outbox/terminal conformance map. | One accepted actor; terminalize success/failure/cancel/supersede/timeout/escalate; stale-fence/cross-host overlap rejection; zero unresolved chains. | Ambiguity remains open and blocks effects. Claims/events/grants are precursors, not coherent runtime closure. |
| F16 deterministic exact-evidence audit | M9 primary; M10 recovery acceptance; M11 retirement | Requires F05 cursor and F01/F17. First replay same-basename/cross-session false joins report-only. | Pure reason functions over occurrence/cursor/version, exact IDs, once-only reasons, no action on ambiguity, recovery reporting. | Auditor never becomes authority. Existing typed reasons/controllers are fragments, not end-to-end isolation. |
| F17 time-scoped version vector | M8 propagation; M8A launcher use; M11 primary acceptance | Requires immutable runtime directories and M6 ownership record. First consume the attested mismatch inventory, never infer loaded code from checkout HEAD. | Source/install/wrapper/config/process/import equality at launch/relaunch/promotion; mixed-version and forced rollback canaries. | Mismatch stops action; historical adapters stay read-only. Existing provenance receipts are selective, not lifetime enforcement. |
| R1 enforce authority/custody/WBC/version foundation | M6A→M8 implementation; M10 effects; M11 acceptance | Requires protected M5/M5A/M6 evidence. First safe pending action is M6A prerequisite/hash validation and schema-only residual confirmation. | Complete boundary rows, exact vector, no accepted-unclaimed repair, one terminal actor, no same-cursor disagreement. | Compose F01/F04/F05/F10/F15/F16/F17; do not create new owners or claim components are wired. |
| R2 wire Megaplan efficiency controls | M8A sole primary; M11 acceptance | Requires R1 identities/storage/vector and captured corpora. First run the existing compiler/splitter/schema/circuit seams in one report-only suite. | Feasible DAG, zero-model validation, 5+1 rework, no third budget retry, drift-sensitive verify-only adoption. | Applies only to new canary plans until promoted; no new planner policy layer. |
| R3 runtime telemetry and canaries as completion authority | M9 primary telemetry; M10 recovery; M11 acceptance/retirement | Requires R1/R2, accepted WBC identities/storage, explicit missing semantics. First build the shadow join and projection stress with effects off. | <5m denominated recovery, 10k-heartbeat proof, 100% cursor agreement, classified work/cost, genuine recovery, no duplicate effect, rollback. | Commits/tests/PIDs/labels are not completion; no deletion before exact-runtime canaries. |

## Milestone execution amendments

Each pending brief contains its own first safe action, concrete output bundle,
acceptance evidence, and stop/rollback rules. The additional assignment is:

| Milestone | Owned rows | Required predecessor evidence | First safe action |
| --- | --- | --- | --- |
| M6A | F04 primary; F02/F03/F15 substrate; R1 foundation | Protected M6 accepted owner/vector/inventory handoff | Validate exact hashes and classify schema-only rows before selecting/characterizing storage with dispatch/effects off. |
| M7 | F01/F15 primary; F06 writer adoption; R1 custody gate | Accepted M6A store/API/migrations | Generate report-only writer, terminal, lease, and provenance maps before enabling any gate. |
| M8 | F02 producer and F04/F17 adoption; R1 universal boundaries | Accepted M7 double-fenced writer contract | Regenerate declared/static/runtime inventory at one vector; exercise the lowest-risk fake adopter first. |
| M8A | F03/F07–F13 primary; F14 emitters; R2 | Accepted M8 adopter proof and immutable corpus | Run report-only captured replay through existing components before wiring or enforcement. |
| M9 | F05/F14/F16 primary; F06 consumer proof; R3 telemetry | Accepted M8A exact-identity events | Delete/rebuild fixture projections and shadow-compare consumers with positive actions disabled. |
| M10 | F02/F15 acceptance; F01/F04/F16 recovery/effect proof; R1/R3 effects | Accepted M9 views and joined ledger | Run the action-off fault/replay matrix with fakes before any separately approved canary. |
| M11 | F05/F10/F17 and R1–R3 final acceptance/retirement | Complete M10 evidence bundle and exact runtime vector | Revalidate every manifest/inventory/hash from a clean pin before canary or deletion eligibility. |

No later brief may claim an assigned row complete by citing this decision. It
must produce the row's named deliverables and acceptance evidence against its
exact predecessor/runtime vector.
