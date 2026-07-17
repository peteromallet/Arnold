# F01–F17 current-epoch implementation and adoption audit

```yaml
artifact: f01-f17-current-epoch-adoption-audit
canonical_initiative: custody-control-plane
canonical_source: research/unified-authority-efficiency-prevention-20260714.md
source_snapshot: 2026-07-14T10:35:52Z
status_snapshot_generated_at: 2026-07-17T12:44:05.058821Z
watchdog_generated_at: 2026-07-17T12:21:30.603074Z
report_generated_at: 2026-07-17T13:20:08Z
evidence_mode: bounded-read-only-research
```

## Executive verdict

**[VERIFIED FACT]** All F01–F17 findings are represented in the Custody Control
Plane's M5–M11/M8A program or a dependency initiative. That is planning coverage,
not completion. No F row has the complete combination of accepted chain evidence,
observed use by the exact pinned runtime, live canary evidence, and legacy-path
retirement required by the canonical completion contract.

**[VERIFIED FACT]** The strongest reusable components are already present:
F06's append-safe projection writer (including advancing cursor artifacts in two
active plan directories), F07's task-feasibility compiler, source and
execution binding for F10/F17, repair request/custody primitives for F01/F15,
bounded compaction and receipt replay for part of F11, and reducer/shadow status
views for F05. Rebuilding these components would duplicate work. Their remaining
problem is boundary adoption, acceptance, version reconciliation, or runtime proof.

**[VERIFIED FACT]** F04, F09, F12, F13, and F14 remain below implementation
acceptance: the WBC attempt ledger is explicitly schema-only; `validation_jobs`
has no located execution consumer; review rework still bypasses the ordinary batch
splitter; no normalized `worker_budget_exhausted` plan circuit was located; and no
joined productive-versus-replayed cost ledger exists.

**[INFERENCE]** The prevention program should be treated as three dependency-ordered
adoption efforts, not seventeen greenfield builds: (1) exact authority/custody and
version identity, (2) wiring existing planner/executor controls, and (3) joined
telemetry plus runtime acceptance. F01/F15, F04/F06, F05/F16, and F10/F17 should
share acceptance workstreams while retaining their distinct owner invariants.

## Evidence semantics and scope

- **[VERIFIED FACT]** is supported by a durable repository artifact, git ancestry,
  test output, resident manifest/result, or timestamped bounded status evidence.
- **[INFERENCE]** is a synthesis from verified facts; it is not an execution or
  completion claim.
- **[UNKNOWN]** means the required telemetry or exact runtime evidence was not
  available. Unknown is never treated as zero, false, or complete.

Status words retain their canonical meanings: `planned`, `executing`, `reworking`,
`reviewing`, `integrated`, `paused`, `blocked`, and `mentioned`. An item can be
`integrated` as a component while its end-to-end recommendation remains `planned`
or `reworking`.

The evidence ladder used throughout is:

1. **planned** — a document, brief, schema, prompt, or initiative names the work;
2. **component present** — code and focused tests exist;
3. **landed** — git proves the component is contained in a named ref/revision;
4. **chain-accepted** — the owning chain's acceptance contract accepted it;
5. **runtime-observed** — the exact source/install/wrapper/process vector used it
   successfully in a canary or genuine run.

Nothing in levels 1–3 alone proves levels 4–5.

### Epoch boundary

**[VERIFIED FACT]** This report defines the current epoch as the interval beginning
at the canonical synthesis `source_snapshot`, `2026-07-14T10:35:52Z`, and ending at
the bounded status snapshot, `2026-07-17T12:44:05.058821Z`. This is more defensible
than silently using a calendar-day boundary because it begins when the unified
recommendation set became durable planning input. Post-snapshot commits and repair
runs are labeled post-snapshot and receive no runtime-adoption credit.

### Canonical and contributor evidence

- Canonical F01–F17 source: `research/unified-authority-efficiency-prevention-20260714.md`.
  **[VERIFIED FACT]** The launch checkout held an obsolete untracked copy
  (`sha256 0d2f5fa2…`) whose only substantive F01–F17 difference said the WBC merge
  was still in progress. The tracked `origin/main` copy (`sha256 df13266e…`) proves
  audited merge `24afce006b9ad20391ac7af10ef67ea0b1774f9f` landed the candidate;
  this report uses that tracked version.
- Prior delivery audit: `subagent-20260717-122309-58b75ec1`.
  **[VERIFIED FACT]** It proves the July 14 Discord summary was provider-accepted
  and received later direct replies. It does not prove read/notification telemetry,
  a full-report attachment, or implementation.
- Prior recommendation audit: `subagent-20260717-122327-52377ef7`.
  **[VERIFIED FACT]** It proves an eight-minute review completed and 131 selected
  component tests passed on then-clean source `b923802…`. It does not prove full
  conformance, controlled deployment, runtime use, M5A acceptance, or canaries.
- Current-epoch inventory: `subagent-20260717-124511-137a8f0c`.
- Existing-solutions audit: `subagent-20260717-124513-f7752f6b`.
- Skeptical evidence review: `subagent-20260717-124514-6f07e066`.
- Skeptical cross-auditor reconciliation: `subagent-20260717-131130-b63bdcca`.
- Synthesis and delivery owner: `subagent-20260717-124246-521d797a`.

## The preceding 15 recommendations crosswalk

**[VERIFIED FACT]** Outbound resident record `msg_0bb60e336996` (Discord message
`1527656312391860316`) was sent on July 17, 2026 at 12:40:47 UTC (UTC+00:00).
It is a compressed presentation of the canonical findings, not separate approval
or completion evidence.

| Summary item | User-visible recommendation | Canonical findings | Audit disposition |
| --- | --- | --- | --- |
| 1 | One authoritative run-state reducer | F05, with F16 consumer evidence | Keep; it is the consumer-facing expression of the authority program. |
| 2 | Immutable, exact repair/attempt scope | F01, F04 | Keep; share identity/storage prerequisites with F15. |
| 3 | Durable event-driven recovery | F02 | Keep; scans remain backstops, not the prompt path. |
| 4 | Adopt valid repairs through verify-only execution | F03 | Keep; existing prompt receipts are not sufficient repair receipts. |
| 5 | Append-only attempt history | F04 | Keep; WBC schema exists, operational store does not. |
| 6 | Finish append-safe projection work | F06 | Correct the old completion claim to “component merged and active cursor artifacts observed; full acceptance and exact-process provenance unproved.” |
| 7 | Reject infeasible serial DAGs | F07 | Adopt the existing compiler; do not redesign it. |
| 8 | Split oversized tasks and rework | F08, F12 | Keep as one operator recommendation with two separate enforcement points. |
| 9 | Move deterministic validation out of model calls | F09 | Keep; schema/prompt support is not executor wiring. |
| 10 | Bound launch and provider failures | F10, F11 | Keep at summary level; acceptance must separate source admission, provider, model, import, and compaction circuits. |
| 11 | Normalize repeated retry failures | F13 | Keep; no actual normalized plan circuit was found. |
| 12 | Authoritative efficiency telemetry | F14 | Keep; current values remain unknown without a joined ledger. |
| 13 | Transactional custody terminalization | F15 | Keep; share occurrence identity with F01, not ownership semantics. |
| 14 | Deterministic exact-evidence auditing | F16 | Keep; current exact IDs coexist with cross-session/projection counterevidence. |
| 15 | Source/install/runtime version equality | F17, with F10 admission | Keep and promote to the first adoption gate. |

## Current-epoch inventory

### Snapshot freshness

**[VERIFIED FACT]** The bounded status tree was generated at
`2026-07-17T12:44:05.058821Z`; watchdog evidence was generated at
`2026-07-17T12:21:30.603074Z`. At report generation those were approximately
36 and 59 minutes old. `stale_banner=null` does not make them current. The tree
reported nine total sessions: four nonterminal/attention sessions and five
completed sessions. The completed-session preview was empty, so older completion
details below are repository/status-history evidence, not a fresh live projection.

### All sessions visible to the bounded status inventory

| Initiative/session | Snapshot/status evidence | Canonical classification | Current-epoch relationship | Freshness/unknown warning |
| --- | --- | --- | --- | --- |
| `custody-control-plane-20260714` | `attention`; display/plan `done`; 20%; current `m5a-atomic-fail-closed-20260715-0149`; latest `12:20:50Z`; no live runner; chain completion absent | `reworking`; M5 `integrated` and accepted; M5A git-landed but rejected; successors `planned`/`blocked` | Controlling F01–F17 epic. M5 current-epoch reconciliation landed; M5A and M6 repair/reconciliation activity occurred. | Snapshot is stale. M5A `completion_verdict.json` has `accepted:false`; do not call it accepted or chain-integrated. |
| `critique-ledger-bigbang-20260716` | status `running`, display/plan `blocked`, 0%, current `cl1-contract-ownership-and-m6-20260716-2157`, latest `12:32:53Z`, no live phase/process | `blocked` and `reworking`; CL2–CL5 `planned` | Semantic critique occurrence/ledger lane for F04/F05/F15/F16. | Accepted repair request had zero claims/attempts at snapshot. Later repair activity is post-snapshot rework, not advancement proof. |
| `megaplan-maintenance` | `paused`, 25%, current `m1-containment-and-truthful-20260711-0021`, latest projection refresh `12:21:13Z` | `paused` | Adjacent F02/F05/F13–F16 owner; current-epoch fixes landed outside its paused chain. | Projection refresh is not execution. Explicit resume is required and was not authorized here. |
| `discord-resident-lifecycle-corrective-20260710` | `paused`, 31%, current `m2-transactional-inbound-20260711-0003`, latest projection refresh `12:21:00Z` | `paused` | Adjacent provenance/outbox/custody work for F01/F03/F15/F17. | No current work may be inferred from the refresh timestamp. |
| `extension-foundation-completion` | completed 1/1 before current epoch | `integrated`; completed before epoch | No current-epoch implementation; contextual platform prerequisite only. | Fresh completed-session projection unavailable. |
| extension composition-spine session | completed 13/13 before current epoch | `integrated`; completed before epoch | No current-epoch F01–F17 work. | Exact fresh session projection unavailable; name/status come from archived inventory. |
| `megaplan-native-parity-corrective` | completed 7/7; durable completion July 8 | `integrated`; completed before epoch | Supplies prior review-rework-cap design relevant to F12; no current-epoch runtime adoption. | July 17 activity was snapshot refresh only. |
| `repository-strategy-roadmap` | completed 5/5; latest substantive activity July 14 | `integrated`; completed in/at epoch boundary | Supplies the incident corpus for F07–F14, not prevention implementation. | Historical counterexample evidence; no live control use. |
| `runauthority-epic-cloud` | completed 3/3 before epoch | `integrated` component foundation; completion receipts later rejected/reconciled | Grants, accepted attempts/decisions, fences, CAS, quarantine; M5 reconciles it. | Nominal completion is not current universal-adoption proof. |

### Current-epoch plans and resident work

| Plan or run family | Status | Durable evidence | What it does and does not prove |
| --- | --- | --- | --- |
| Custody M5, `m5-run-authority-receipt-20260714-1428` | `integrated` and chain-accepted | Merge lineage through `5e4f375737c…` and accepted reconciliation evidence | Proves M5 reconciliation only; not M5A or F01–F17 completion. |
| Custody M5A, `m5a-atomic-fail-closed-20260715-0149` | plan `done`, git-landed, but `reworking`/rejected | `a5f92fadcfe…`; live `completion_verdict.json` has `accepted:false` and unsatisfied landed-diff, green-suite, and execution-acceptance obligations | Proves code/plan history; does not prove accepted milestone or successor authority. |
| Custody M6, `m6-exact-contract-and-20260716-1303` | `blocked`/`reworking` | At 12:55:57Z post-snapshot inspection it was blocked in critique before execution with an open replay-corpus/task-sizing finding | Shows active repair attention, not implementation or acceptance. |
| Custody M6A–M11 including M8A | `planned`; dependency-`blocked` | `chain.yaml`, briefs, coverage matrices | Complete planning coverage; no accepted runtime milestones. |
| Critique CL1 | `blocked`/`reworking` | Finding `CF-582FC3378CA325D81F45`; request `8324f152…`; 0/5 | Demonstrates the occurrence/custody problem is live. It does not prove Critique Ledger storage. |
| Critique CL2–CL5 | `planned` | Initiative landed at `17a7ce97f2f…`; initialization `59b4ae5c7e…` | CL2 cannot claim WBC-backed durability before an accepted operational WBC store exists. |
| Current resident fixers | `executing`/`reworking` at snapshot | `subagent-20260717-113550-f88b1c5f`, `subagent-20260717-113559-dd550210`; queued `113628-603a8e77` | Real repair work was launched. Neither chain recovery nor F-row acceptance was proved. |
| Current audit owner/contributors | `reviewing` | `124246-521d797a`, `124511-137a8f0c`, `124513-f7752f6b`, `124514-6f07e066`, reviewer continuation `131130-b63bdcca` | Produces research and durable curation only; authorizes no runtime mutation. |

## Checkout, install, and runtime topology

| Surface | Verified revision/state | Consequence |
| --- | --- | --- |
| Requested local target | `refs/heads/main` at `6a63c9e3405c…` at launch | It does not contain several cited solution commits, including F06. |
| Tracked remote | `origin/main` at `a5f92fadcfe…` during audit; merge base with local target `612b139971e…` | It contains F06 and M5A lineage but is not the authorized local target and was not pushed/merged here. |
| Task-declared pinned resident runtime | `868b6c21ccd5…` | Contains F06, F07, bounded compaction/replay, and numerous repair controls. This is ancestry evidence, not proof every live process imported them. |
| Live Discord resident restart receipt | process start July 17 11:19:26Z; receipt binds source `b92380231941…` | The live process does not equal the later task-declared pin or current checkout revision. |
| Resident source checkout observed during review | advanced clean/detached without resident restart: `868b6c21…` at `12:36:14Z`, `e1bce20d…` at `12:45:47Z`, then `6788980…` at `13:00:25Z` | Checkout HEAD cannot identify already imported modules; lazy-import identity is unknown without per-module receipts. |
| Editable package metadata | `arnold 0.23.0` pointed to `/workspace/arnold-critique-ledger-runtime-recovery-20260717`; that worktree and the mutable runtime checkout both reported `6788980…` at `13:17:09Z` | Present checkout alignment does not retroactively identify the long-running resident's loaded modules or align the project target/process receipt. |
| Custody M6 target | `ea2be1fe36c4…`, two dirty paths | F06 commits are not ancestors of this plan target. |

**[VERIFIED FACT]** This divergence is direct counterevidence to claiming universal
F10/F17 enforcement or runtime use of any component merely because it exists in
one checkout. At `2026-07-17T12:44:07Z`, bounded status also attached a Custody
relaunch command to the unrelated Progress Auditor D9 checkout. Exact-session
source isolation therefore remains unproved.

## F01–F17 recommendation and adoption matrix

| ID | Concise recommendation | Current-epoch status | Initiative / plan / commit / test / runtime evidence | Existing solution(s) | Actually used? | Adoption gap | Confidence | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F01 | Bind every repair to exact plan revision, task, attempt, failure signature, result hash, grant/fence, and immutable occurrence. | `reworking`; component present; not chain-accepted | **[FACT]** Custody M5/M5A/M6 and commits `0feaa9e…`, `bd7d9e0…`, `b4f0880…`, `817e46b…`, `b923802…`, `868b6c2…` address blocker/layer/same-lineage identity. Live Critique request `8324f152…` was accepted but unclaimed. A post-snapshot `13:01:56Z` queue sample found 136 requests: 13 with coarse blocker/fingerprint identity and 123 without it; none exposed the full revision/attempt/fence tuple. | `cloud/repair_requests.py` normalized signatures/blocker IDs; `repair_contract.py`; `repair_recurrence.py`; focused repair-request/trigger tests. | **Partial.** Exact IDs appear in live evidence, but the full canonical tuple and terminal adoption are absent on the sampled queue surface. | Existing fields are not one universally enforced occurrence key across enqueue, claim, execution, receipt, decision, and terminalization. Another private join is **[UNKNOWN]**. | High. | Reuse the repair schemas and implement one F01/F15 occurrence-terminalization conformance matrix at M6A/M7 boundaries. |
| F02 | Trigger deduplicated repair from durable block/process-exit events; retain scans only as reconciliation backstops; prove p95 under five minutes. | `reworking`; trigger component present; runtime outcome failed | **[FACT]** `cloud.supervise.enqueue_supervisor_repair_request`, watchdog/repair-trigger paths, `f038f49…`, `817e46b…`, and 153 gather/40 escalation-controller tests exist. Critique remained blocked with zero claim/attempt at snapshot. **[INFERENCE]** A biased post-snapshot join of 20 matched requests to their first attempts ranged 2–38,144s, median 2,003s, with 11/20 over five minutes. Six had multiple attempts; last-attempt intervals were longer. Neither is the canonical eligibility→accepted-repair SLO. | Existing enqueue hooks, repair request store, watchdog, repair-trigger wrapper, six-hour auditor. | **Partial.** Real automatic repair paths launched; neither active chain recovered. | Missing unmatched-request denominator and eligibility, claim, accepted-repair, unblock, duplicate/miss, and cohort-p95 evidence. | High on gap; medium on exploratory latency inference. | Instrument event→request→claim→terminal timestamps on the exact occurrence; shadow a genuine blocker and publish p50/p95/p99 plus miss/duplicate counts. |
| F03 | Accept a valid same-revision repair receipt via verify-only execution; force normal execution on code/test/contract/fence drift. | `planned`/`reworking`; precursor only | **[FACT]** `6057cdd…` binds quality repair to HEAD/target/validation; `blocker_recovery.py`, `handlers/override.py::_override_adopt_execution`, completed-task prompt projections, and `218f937…` replay bounds exist. `_override_adopt_execution` promotes already completed execution state; the repair validator authorizes phase replay, not verify-only repair adoption. | Same-lineage custody checks, code-repair receipt validation, adopt-execution authority receipt, completed-task projection. | **Reusable precursors only.** No named repair verify-only path exists; completed-task receipts omit grant, source/tree/test-set hashes, and fence identity. | No executor branch consumes a WBC-backed repair receipt and proves verify-only behavior/negative drift cases. | High. | Compose a narrow adapter over the existing validators/receipts after F01/WBC identity is accepted, then add positive and drift-negative canaries. |
| F04 | Make attempt/effect history append-only; mutable aliases become rebuildable projections only. | `planned`; Critique CL1 `blocked` | **[FACT]** WBC merge `24afce0…`; `arnold/workflow/execution_attempt_ledger.py` explicitly says schema-only/no I/O or runtime effects; support manifest describes the same. Critique Ledger proposes occurrences but has not cleared CL1. | WBC `ExecutionAttemptLedger` schema, repair-attempt sidecars, Critique occurrence design. | **No universal durable store.** Schemas and sidecars are used in limited contexts only. | Transactional persistence/query API, start-before-dispatch, terminal outcome, migration, producer adoption, and alias retirement are absent/unaccepted. | High. | Adopt the WBC schema in M6A's transactional store; gate Critique CL2 and all producer migration on accepted store/API proof. |
| F05 | Derive plan/chain/cloud/repair/operator status from one attempt-aware reducer and exact cursor vector. | `reworking`; reducer/shadow components present | **[FACT]** `arnold_pipelines/run_authority/reducer.py`, `authority/views.py`, `status_projection.py`, and status commits including `59f37d1…` exist. Snapshot simultaneously shows Custody plan `done`, chain `attention`/20%, no runner, and absent completion; Critique is `running`/`blocked` with no process. | Run Authority reducer/views; read-only status shadow; projection comparators. | **Partial/shadow.** Consumers still expose contradictory interpretations. | Shadow output has not replaced legacy authoritative readers; cursor agreement and cutover/rollback telemetry are missing. | High. | Freeze the source cursor vector, compare every consumer in shadow, and promote only after 100% agreement with explicit unknowns. |
| F06 | Replace whole-journal non-atomic heartbeat projection rewrites with incremental cursor-checked appends and atomic rebuilds. | component `integrated`; cursor-writing behavior observed; acceptance incomplete | **[FACT]** Commits `3221870c…`, `0a31d539…`, merge `8cbcd93…`; `tests/observability/test_events_projection.py`; ancestors of `origin/main`, `b923802…`, and `6788980…`, not local target or Custody M6. Cursor files advanced to sequence 2580 for Custody M6 and 2722 for Critique CL1, matching last projected events at `13:12:05Z` and `13:13:11Z`. The files do not record producer SHA. Tests cover small append/rebuild and atomic replace, not 10,000 events/concurrent readers. | `observability/events_projection.py` incremental cursor and atomic rebuild implementation. | **Behavior observed in active plans; exact producer provenance and full F06 acceptance unproved.** | Missing 10,000-heartbeat stress, monotonic concurrent-read proof, zero false stalls, bytes/time/rebuild telemetry, installed-SHA canary, rollback, and historical-reader retirement. | High. | Do not rebuild. Reconcile the exact target/runtime, run the specified stress/concurrency canary, then record consumer coverage and retirement evidence. |
| F07 | Reject unexplained serial DAGs; compute width, critical path, usable parallelism, routing groups, and turn feasibility. | component present/landed in pinned runtime; runtime adoption unproved | **[FACT]** `orchestration/task_feasibility.py`, dependency reasons/routing groups, commits `8122ff0…` and `b4bc639…`, focused tests. M5A's captured plan still had 35 tasks and 34 linear edges. | Existing v2 task-feasibility compiler is the strongest underused solution. | **Used in tests and some finalization paths; no captured replay/new-plan canary.** | Legacy/current plan admission and exact runtime coverage are not demonstrated; no Strategy/Transaction corpus report exists. | High. | Replay captured Strategy and Transaction plans through the existing compiler in report-only mode, then enforce on new v2 plans after false-positive review. |
| F08 | Split complexity 7–9 work into implementation/proof or grant evidence-backed larger budgets and residual checkpoints. | `reworking`; partial compiler/prompt control | **[FACT]** `b4bc639…` requires feasibility guidance/checkpoints; M5A evidence recorded tasks over the 15-minute target and T30 exhausting 90 iterations. | Task-feasibility complexity checks and planning prompts. | **Partial.** Residual checkpoint checks exist; split-vs-authorized-budget rule is not fully enforced. | No universal compiler rule joining complexity, split, budget authority, turn demand, and executor enforcement. | Medium-high. | Extend the existing feasibility result—not a new planner—to require split or signed budget authority, then replay known oversized fixtures. |
| F09 | Compile deterministic validation into reproducible harness jobs, never model-worker tasks. | `planned`/unwired; adjacent shadow harness present | **[FACT]** `finalize_contract.py` has `validation_jobs`; prompts assign harness ownership and generally emit `[]`; feasibility rejects some model validation tasks. `full_suite_backstop`, `suite_runner`, and `AcceptanceTransaction` are adjacent mechanical-suite substrate; Repository Strategy recorded a generic shadow backstop run with `status=failed`, `blocks=False`. No consumer of declared `validation_jobs` was located. | Existing `validation_jobs` schema plus adjacent suite runner/backstop/acceptance transaction. | **No F09 runtime use proved; only adjacent harness substrate exercised in shadow.** | Compiler→declared-job→harness wiring, environment/output/hash receipt, enforce-mode promotion, and zero-model-call acceptance fixture are missing. | High. | Wire the existing schema to the existing harness and replay T10/T12/T15-equivalent validation with an asserted model-call count of zero. |
| F10 | Validate exact source/ref/runtime binding once before dispatch; bound invalid-ref/startup retries and emit typed terminal reasons. | `reworking`; substantial guards present, not universal | **[FACT]** `chain/execution_binding.py`, `chain/source_admission.py`, content/source/runtime identities, and focused tests exist. Live topology diverged and a Custody relaunch targeted an unrelated checkout. | Chain execution binding and canonical source admission. | **Used at some launch/reconciliation boundaries; demonstrably not governing all relaunch/runtime paths.** | Missing one universal launcher gate, suggested-ref handling, bounded attempts, and mixed-boundary conformance. | High. | Adopt the current binding at every launcher/relaunch path, validate once, and prove invalid-ref termination without provider/model dispatch. |
| F11 | Separate and bound provider timeout, model resolution, import isolation, compaction, and replay circuits. | compaction/replay component `integrated` in pinned runtime; other subcontrols `planned`/`reworking` | **[FACT]** `218f937…`, `arnold/agent/context_compressor.py`, and tests preserve context on blank/failed summaries and bound replay. No joined live canary proves the combined recommendation. | Existing compressor, completed-receipt replay bounds, provider/model configuration checks. | **Partial.** Compaction/replay component used in tested lineage; provider/import/timeout circuits unproved. | Recommendation is over-bundled: each failure class needs a typed circuit, counters, attempt identity, and acceptance case. | High for compaction; medium for other path coverage. | Reuse existing circuit primitives, split acceptance by failure class, and require one typed terminal outcome per bounded circuit. |
| F12 | Apply the same maximum dispatch-wave size to review rework as normal execution. | `planned`; existing splitter bypassed | **[FACT]** `_core.io.split_oversized_batches` is used for normal batches. At revision `868b6c21…`, `execute/batch.py` still sets `batches_to_run = [review_rework_task_ids]`. Prior native-parity M7 design exists. | Ordinary batch splitter and prior review-rework-cap brief. | **No for review rework.** | Review path does not call the existing splitter; six-task regression and executor assertion are absent. | High. | Route review rework through the existing splitter, add the six-task→5+1 fixture, and reject oversized grants before launch. |
| F13 | After two equivalent normalized worker-budget failures, stop retrying and require split or explicit budget authority. | `planned`; adjacent circuits only | **[FACT]** Hinge/phase/repair recurrence circuits exist, but no normalized `worker_budget_exhausted` plan breaker was located in the pinned source. | Existing circuit/recurrence framework can be reused. | **No for the named plan circuit.** | Failure normalization, exact occurrence identity, collision tests, third-retry prevention, and split/budget transition are missing. | High. | Add the normalized reason to the existing circuit framework only after F01 identity is fixed; prove the third equivalent launch cannot occur. |
| F14 | Join queue, inference, tool, git, validation, retry, compaction, repair, tokens, cost, and accepted output to exact attempts; separate productive from replayed. | mostly `planned`; telemetry fragments `mentioned`/present | **[FACT]** Event kinds, cost projection, plan timings, incident ledgers, and WBC schema exist. No joined task/attempt/repair/accepted-output ledger or denominators were found. | Existing event stream, `observability/cost.py`, progress auditor metrics, WBC identity schema. | **Fragments used; authoritative joined classification no.** | Missing attempt join keys, accepted-output delta, productive/replayed rules, denominators, and explicit missing-data propagation. | High. | Extend the WBC/event identity fields and build a shadow join before dashboards or optimization claims; report missing as unknown. |
| F15 | Terminalize request/claim/attempt/decision/worker/repair atomically with one accepted actor and fenced overlap rejection. | `reworking`; strong precursors; live gap | **[FACT]** Atomic repair claims/attempts, `repair_contract` projections/events, Run Authority grants, and commits `c267920…`, `817e46b…`, `b923802…` exist. M5A's verdict is rejected; Critique had accepted-unclaimed repair and no attempt. A post-snapshot sample found 52 immutable dispatch-launch receipts whose constructor intentionally hardcodes `status=launched`; that surface cannot answer lifecycle terminalization. | Existing repair request store, custody events, grants/fences, M5A atomic-completion code. | **Partial.** Claims/dispatch are actively used; coherent terminal closure is not runtime-proved. | No accepted M6A/M7 occurrence/lease/epoch transaction, overlap canary, authoritative terminal join/rate, or universal boundary gate. Terminal outcomes elsewhere are **[UNKNOWN]**. | High. | Share F01's occurrence key, join launch receipts to authoritative terminal outbox records, and prove stale-fence/overlap rejection plus zero unresolved terminal chains. |
| F16 | Generate auditor findings from exact IDs, normalized deterministic reasons, and same-session joins; never heuristic basenames/prose. | `reworking`; analytic components used; isolation failed | **[FACT]** `six_hour_auditor.py`, progress-auditor controller/escalation, typed reasons, `f038f49…`, and exact IDs are visible. Cross-attached Custody relaunch source and current fixer work show false/stale joins remain. | Existing typed gather reasons, exact evidence references, progress-auditor controller. | **Yes for detection fragments; no for exact end-to-end isolation/effective repair.** | Historical recount, stale repair-data, same-basename/cross-session joins, precision/recall cohort, and consumer agreement remain unproved. | High. | Make gather reasons pure functions of exact occurrence/cursor/version, replay known false joins, and block any action when the join is ambiguous. |
| F17 | Require source, editable install, wrapper, configuration, worker, and live process to equal one recorded version vector at launch/promotion. | `reworking`; controls present; invariant currently violated | **[FACT]** Execution binding/runtime provenance and restart receipts exist. Resident PID `3884514` started at `11:19:26Z` from receipt `b923802…`; its `PYTHONPATH` checkout moved without restart through `868b6…`, `e1bce…`, and `6788980…`. At `13:17:09Z` the mutable runtime and editable-package worktree both reported `6788980…`, while project target remained dirty `6a63…`, `origin/main` `a5f92…`, and Custody target `ea2be…`. | Existing execution binding, runtime provenance, restart receipt, git-custody checks. | **Used selectively; not universal.** | No single time-scoped attested vector governs launch, loaded/lazy imports, relaunch, status publication, repair, and promotion. Loaded-module/wrapper/config/effect equality is **[UNKNOWN]**. | Very high. | Reconcile and freeze the exact vector first; fail closed at every launch/relaunch/promotion boundary and use immutable runtime directories plus per-process/import provenance. |

## Existing solutions to adopt rather than rebuild

| Reuse target | Findings served | Adoption decision | Proof still required |
| --- | --- | --- | --- |
| `arnold_pipelines/run_authority/reducer.py` plus `authority/views.py` | F05, F16 | Promote through shadow agreement; do not write another status reducer. | Exact cursor equality, every consumer migrated, disagreement telemetry, rollback. |
| `cloud/repair_requests.py`, `repair_contract.py`, Run Authority grants/fences | F01, F02, F15 | Extend into one occurrence-terminalization transaction; do not create a parallel repair queue/ledger. | Full identity tuple, claim/attempt/decision closure, overlap/stale-fence canaries. |
| WBC `ExecutionAttemptLedger` schema | F04, F14, F15 | Adopt as the schema for M6A storage; do not mistake it for storage or create a competing attempt schema. | Durable transactional API, migrations, producer/consumer coverage, mixed-version behavior. |
| `observability/events_projection.py` | F06, F05 | Keep the merged implementation; finish stress/canary/reader retirement. | 10,000-heartbeat and concurrent-reader acceptance plus runtime provenance. |
| `orchestration/task_feasibility.py` | F07, F08, F09 | Use as the compiler enforcement point and extend its result; do not create a second planner policy layer. | Captured-corpus shadow replay, false-positive review, new-plan canary. |
| `finalize_contract.validation_jobs` | F09 | Wire it to the deterministic harness; do not invent a second validation declaration. | Real consumer, reproducible receipts, zero model calls. |
| `_core.io.split_oversized_batches` | F12 | Call it from review rework; do not implement another splitter. | Six-task regression, grant bound, 5+1 observed wave. |
| Existing hinge/phase/recurrence circuit framework | F11, F13 | Add typed normalized failure circuits after identity normalization; do not fork retry state. | Collision safety, exact two-strike semantics, third-launch rejection. |
| Execution binding and source admission | F10, F17 | Enforce on every launcher/relaunch/promotion path; do not build another provenance manifest. | Exact vector equality, mixed-version negative canary, process/import receipts. |
| Event stream and cost projection | F14 | Add exact attempt/accepted-output joins in shadow; do not replace telemetry wholesale. | Denominators, productive/replayed classification, missing-data semantics. |

## Overlaps, dependencies, and obsolete/duplicate edges

1. **F01 + F15: shared identity and transaction, distinct semantics.**
   **[INFERENCE]** F01 defines which repair occurrence is being acted upon; F15
   defines exclusive custody and coherent terminal closure. One acceptance matrix
   should exercise both, but identity must not absorb custody ownership.

2. **F04 + F06: source history versus projection mechanics.**
   **[INFERENCE]** F04 needs an operational append-only source of truth; F06 already
   supplies a safer projection writer. Completing F06 cannot substitute for the
   missing F04 store, and M6A should not rebuild F06.

3. **F05 + F16: reducer truth versus analytic evidence.**
   **[INFERENCE]** F05 owns coherent state projection; F16 owns deterministic
   findings over exact evidence. Auditor output must consume the reducer/cursor,
   never become a second status authority.

4. **F10 + F17: admission check versus lifetime provenance.**
   **[INFERENCE]** F10 validates the launch target and bounds retry; F17 preserves
   the version invariant through install, wrapper, worker, lazy imports, restart,
   repair, and promotion. They should share one vector and separate gates.

5. **F11 + F13: typed failure circuits.**
   **[INFERENCE]** F13 is the normalized budget-exhaustion specialization of F11's
   broader circuit family. Reuse the framework, but keep separate counters and
   collision tests so provider timeouts cannot trip a worker-budget decision.

6. **Critique Ledger dependency.** **[VERIFIED FACT]** Critique Ledger owns semantic
   finding occurrences/dispositions, not general run authority. CL2's proposed
   WBC-backed persistence is dependency-blocked until M6A (or another explicitly
   accepted substrate) provides operational storage.

7. **Orphan recovery ticket.** **[VERIFIED FACT]** The open ticket “Supervisor
   stale-step autonomous recovery policy” overlaps F02/F11/F13/F15, has no linked
   epic, and names obsolete `arnold/pipelines/megaplan` touchpoints.
   **[INFERENCE]** Reconcile its surviving acceptance cases into Custody/Maintenance
   and then mark it superseded; do not launch a duplicate initiative.

## Telemetry and acceptance evidence still unknown

- **[UNKNOWN]** Real event-to-accepted-repair p50/p95/p99, eligibility denominator,
  missed-event rate, duplicate-launch rate, and genuine blocked-run recovery.
- **[UNKNOWN]** F06 bytes written, wall time, reader error rate, false stalls,
  rebuild frequency, and monotonic concurrent reads at 10,000 heartbeats.
- **[UNKNOWN]** Productive versus replayed time, calls, tokens, dollars, accepted
  output, and queue/tool/git/validation/compaction decomposition.
- **[UNKNOWN]** Exact compaction duration and useful work retained across timeout
  or compaction.
- **[UNKNOWN]** Current runtime coverage for WBC's 35 producer rows. The audited
  baseline remains 5 auto-matched, 8 manual-emission, 13 declared-only, 9 unknown.
- **[UNKNOWN]** Cross-host lease overlap, stale-fence rejection, terminal-custody
  closure rate, and mixed-version canary results.
- **[VERIFIED FACT]** M5A's journal contains an unmatched historical
  `llm_call_start` while the plan is `done`; introspection also treated it as
  in-flight/stalled. Unmatched call state is therefore not reliable telemetry.

## Verification performed for this audit

- Bounded resident context/status/session/initiative/ticket/document searches were
  used; the complete cloud-status JSON was never loaded.
- Git ancestry was independently checked across local target `6a63c9e…`,
  `origin/main`, task pin `868b6c21…`, live process receipt `b923802…`, and the
  Custody M6 target.
- Existing component claims were spot-checked in source and support manifests.
- The skeptical reviewer independently ran 21 focused projection/feasibility
  tests successfully; the prior audit ran 131 selected component tests
  successfully. These are component tests, not runtime acceptance.
- The report itself requires a row for every F01–F17, a 15-item crosswalk, all
  bounded status sessions, evidence labels, exactly three terminal priorities,
  and clean git diff validation before integration.

## Ranked recommendations

1. **Adopt and enforce the existing authority, custody, WBC, and version-binding foundation at every active boundary.**
   - **Rationale:** F01/F04/F05/F10/F15/F16/F17 are the prerequisite truth and identity layer; the live version vector and unresolved M5A/CL1 custody states invalidate downstream completion claims.
   - **Prerequisites:** Select and reconcile the exact local/source/install/wrapper/process vector; preserve M5 acceptance; resolve M5A's rejected verdict without crediting successor work; agree the M6A WBC store and M7 custody ownership boundary.
   - **Concrete first move:** Generate M6's zero-exemption producer/consumer/boundary matrix from the existing execution binding and WBC schemas, with one version vector and one F01/F15 occurrence key, then run it in report-only mode against Custody and Critique.
   - **Success measure:** Exact vector equality at launch/relaunch/promotion; every boundary row has producer, consumer, acceptance, runtime trace, and owner; zero accepted-but-unclaimed repairs; no contradictory reducer projections at one cursor.
   - **Stop/defer:** Stop duplicate reducer/queue/attempt-ledger/provenance designs; defer M8A enforcement, CL2 persistence claims, legacy retirement, deploy, and restart until this gate is accepted.

2. **Wire the already-built Megaplan efficiency controls into the real compiler and executor.**
   - **Rationale:** F07 has substantial tested code, while F09/F12/F13 are mostly unwired paths; reuse can remove the known seriality, validation-call, oversized-rework, and blind-budget-retry failure modes faster than another architecture pass.
   - **Prerequisites:** Recommendation 1's exact attempts, receipts, fences, and runtime vector; captured Strategy/Transaction and six-task rework fixtures; report-only false-positive review.
   - **Concrete first move:** Replay the captured corpus through `task_feasibility.py`, wire `validation_jobs` to the harness, route review rework through `split_oversized_batches`, and add the normalized two-strike budget circuit in one shadow acceptance suite.
   - **Success measure:** No unexplained meaningful fully serial DAG; deterministic validation produces zero model calls; six rework tasks dispatch 5+1; no third equivalent budget launch; a same-revision valid repair is adopted verify-only while drift forces normal execution.
   - **Stop/defer:** Stop new planner/splitter/validation declarations; defer enforcement on existing live plans and automatic budget escalation until captured replay and collision tests pass.

3. **Make joined telemetry and runtime canaries—not commits or focused tests—the completion authority.**
   - **Rationale:** F02/F06/F14 and every promotion gate lack the real denominators, latency/cost joins, stress evidence, and exact-runtime observation needed to distinguish productive progress from replay, waiting, or false success.
   - **Prerequisites:** Recommendations 1–2, an exact version vector, accepted WBC identity/storage fields, and explicit missing-data semantics.
   - **Concrete first move:** Add exact attempt/repair/accepted-output IDs and stage timestamps to the existing WBC/event stream, then shadow two captured corpora plus one genuine eligible blocker and the 10,000-heartbeat projection workload.
   - **Success measure:** Event-to-repair p95 under five minutes with denominator and miss/duplicate rates; 100% cursor/hash agreement; monotonic concurrent reads and zero false stalls in the projection stress; productive/replayed time, tokens, and cost classified with unknowns explicit; one genuine blocked-run recovery and zero duplicate effects.
   - **Stop/defer:** Stop calling documents, commits, green focused tests, PIDs, or status labels “runtime complete”; defer deletion/retirement, broad rollout, and efficiency ROI claims until canary, mixed-version, rollback, and genuine-recovery evidence is durable.
