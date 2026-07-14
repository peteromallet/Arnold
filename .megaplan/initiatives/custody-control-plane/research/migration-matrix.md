---
type: research
date: 2026-07-11
schema: custody-control-plane-migration-matrix-v1
---

# Exhaustive authority migration matrix

Status vocabulary: `substrate` means the right primitive exists but coverage is
not proven; `legacy` means authority can still be inferred or written outside
the target; `prerequisite-WBC` is externally owned and must be consumed and
operationalized without changing ownership; `gate` requires human or
manifest evidence; `target` is the planned end state.

## Residual-scope rule

This matrix is a zero-exemption audit surface, not an instruction to duplicate
another initiative. M5 first establishes accepted current Run Authority
completion and retirement proof. At M6, that proof and WBC completion/support
manifests must be joined to every row. A WBC row is prerequisite-satisfied only
when exact implementation, static call-site, captured runtime trace, negative
bypass and relevant fault/migration evidence prove it—not because a support
manifest or schema suite declares it supported. Missing substrate goes to M6A;
missing producers go to M8; missing consumers go to M9. Ownership remains WBC
and never defaults to Custody.

The row-level WBC completion equation and named producer/consumer families are
maintained in `wbc-boundary-adoption-matrix.md`. M6 generates the machine-
readable inventory that joins both matrices.

The table's **Proof** column is the required shadow/conformance proof for that
surface. The following execution columns apply normatively to every row, rather
than being optional defaults:

| Required column | Per-row contract |
|---|---|
| Fail-closed behavior | If the row's exact contract/version, Run Authority grant/coordinator fence, Custody lease/custody epoch, coherent WBC evidence, owner, or listed proof is absent or contradictory, the reader returns `UNKNOWN`/`INCOHERENT`, emits drift, and performs zero authority-increasing transition, dispatch, retry, repair, completion, cancellation, delivery, publication, or deletion. A projection cannot fill a missing source record. |
| Rollback / mixed-version policy | Shadow before enforcement; old readers may consume only an explicit, expiring compatibility projection; old writers are rejected after cutover. Rollback disables promotion/effects and keeps append, reconciliation, and evidence intact—never restoring raw legacy authority or rewriting history. Row-specific stricter rules in milestone briefs and the decision record win. |
| Completion evidence | The listed proof artifact, exact source/runtime/contract hashes, migration owner sign-off, authoritative-history/replay evidence, zero legacy authority-reader/writer scan for the row, rollback result, and M11 proof-map entry. A generated completion manifest must hash the proof; status text or nominal milestone completion is insufficient. |

Thus each legacy path below is mapped to target contract, owner/milestone,
shadow/conformance proof, fail-closed behavior, deletion gate, mixed-version and
rollback policy, and completion evidence. No row may claim an exception by
omitting one of these inherited columns.

The July 14 authority/efficiency extension adds F01-F17 traceability in
`unified-authority-efficiency-prevention-20260714.md`. The rows below remain the
surface inventory; that document is the canonical root-cause/control/SLO/rollout
map; M6A is added for the WBC transactional substrate and M8A for adjacent
planner/executor controls.

| Consumer / surface | Current authority | Target authority | Milestone | Shadow / conformance proof | Deletion gate | Owner / initiative | Status |
|---|---|---|---|---|---|---|---|
| Run Authority M1-M3 completion receipts | all three `accepted: false`; stale/missing phase evidence, diff mismatches, structural failures | three fresh content-addressed accepted receipts | M5 | canonical receipt regeneration plus `chain verify` divergence count 0 | no downstream milestone before manual acceptance | runauthority-epic / custody M5 evidence repair | blocked evidence |
| Canonical `runauthority-epic` retirement | no initiative `.retired` marker; a duplicate-session tombstone exists but is not initiative retirement authority | metadata-only `.megaplan/initiatives/runauthority-epic/.retired` marker plus content-addressed retirement attestation | M5 | three accepted receipts, canonical divergence count 0, regenerated proof/manifest, exact chain-state identity, constrained duplicate-session lookup/tombstone, and canonical asset hashes | marker creation fails closed until every proof gate passes; never delete canonical audit evidence | runauthority-epic / custody M5; Resident supplies supporting session evidence | blocked evidence |
| Kernel `WorkflowManifest` identity | compiled manifest plus package identity | exact hash/version recorded on every attempt | M6/M8 | stale-version and missing-manifest tests | no implicit-latest lookup | Native Platform | substrate |
| Kernel NDJSON journal | append-only generic runtime events | WBC transactional execution-attempt store/API plus Run Authority-linked causal envelope | M6A/M8 | append/transaction/crash/replay/runtime-trace conformance | old journal adapter read-only; direct writer rejected | WBC / Run Authority; Custody adapter only | substrate gap |
| Native persistence checkpoint/cursor | checkpoint JSON including native `pc` | versioned evidence projection bound to accepted attempt | M8 | corrupt/stale/deleted cursor tests | bare `pc` banned outside schema | Native Platform; PC gate | legacy |
| Native trace hooks (`state/events/stages/artifacts/checkpoint`) | parallel trace files | projections/evidence refs from one history | M8/M11 | delete/rebuild and hash proof | zero authority readers | Native Platform | legacy |
| `.pypeline` and named subworkflows | intended topology authority | unchanged topology plus exact boundary evidence | M8 | native traceability/conformance | component/handler routes deleted | Native Parity | substrate, manifest absent |
| Component/handler route tables | callable compatibility topology | non-authoritative adapter or deletion | M8/M11 | negative execution-authority tests | zero runtime route reads | Native Parity | legacy |
| Graph/native-program projections | generated route/topology views | rebuildable source projection | M8/M11 | source-to-projection parity | no dynamic authority fallback | Native Parity | legacy |
| `RunAuthorityKernel` grants | grant/fence contracts | same records in joined causal history | M7 | grant/fence/quarantine tests | raw dispatch forbidden | runauthority-epic | substrate; landing gate |
| Accepted attempt/decision reducer | deterministic Run Authority view | pure source-backed acceptance projection; never a bearer grant or custody lease | M7/M8 | stale/off-scope result quarantine plus source reread | artifact labels or serialized view never accepted as action token | runauthority-epic | substrate |
| Runner/publication/human/recovery views | separate domain views | versioned projections from history/evidence | M9 | multidimensional fixture suite | aggregate optimistic status removed | runauthority-epic | substrate |
| Canonical run-state resolver | ordered raw evidence classifier | read-coherent reducer/evidence binding | M6/M9 | torn-read and parity tests | noncanonical dispatch rejected | custody-control-plane M1-M4 | substrate |
| Run-state classifiers | local precedence rules | pure policy over coherent versioned envelope | M9 | all July incident fixtures | duplicate classifiers deleted | custody-control-plane | substrate |
| `state.json` writer / merge-on-save | mutable plan truth plus append-only meta | compatibility projection writer after history append | M7 | crash between append/project edges | direct authoritative save fails | custody-control-plane | legacy |
| `state.json` readers | widespread phase/status/resume reads | signed projection or reducer query | M8/M9/M11 | generated reader inventory | zero authority-increasing reads | custody-control-plane | legacy |
| Plan `events.ndjson` | detailed but separate plan journal | migrated/imported causal event stream | M7 | ordering/parent/attempt replay | no activity authority from mtime | custody-control-plane | legacy/substrate |
| `phase_result.json` | stage terminal claim | evidence ref awaiting accepted decision | M8 | stale/partial terminal tests | labels cannot advance | WBC + custody | partial |
| receipts/routing/cost ledgers | separate append logs | evidence/effect events linked by attempt | M7/M8 | join completeness and replay | unlinked receipts diagnostic only | WBC / observability | partial |
| effect ledger/enforcement | local effect records | history intent/outcome/idempotency/reconcile | M7/M10 | crash matrix; provider reconcile | no sidecar retry | Native Platform / custody | partial |
| prep/plan/revise stages | handler/native stage state | exact-version attempt boundaries | M8 | start/terminal/stale-fence/CAS/reread tests | direct plan/chain mutation blocked | custody-control-plane | substrate |
| CLI override/user actions | append some resolution metadata and mutate state | authorized decision + transition append | M7/M8 | replay/idempotency/permission tests | raw override state edits fail | Megaplan | legacy |
| prep/plan/revise stages | handlers and state/artifact writes | exact-version attempt/boundary events | M8 | start/terminal/persistence faults | unledgered stage refused | WBC C2-C3 | in-flight-WBC |
| critique/gate/tiebreaker/reducer stages | handler results, verdict artifacts and mutable state | exact-version attempts plus accepted Run Authority decisions | M8 | split-verdict/retry/reducer/replay tests | checkpoint-only completion forbidden | WBC / Run Authority | partial |
| finalize/execute/review/feedback stages | artifacts, batch checkpoints, receipts and state | causal attempts/effects with post-transition reread | M8/M10 | partial batch, approval, rework and retry tests | artifact label never advances alone | WBC / Run Authority | partial |
| fallback chains/model seam | configured retry/fallback specs | history decision per attempt/fallback | M8/M10 | swallowed fallback tests | unsafe fallback fails visible | Megaplan runtime | legacy |
| worker/process fanout | PID/result files | parent/child attempts with leases | M8/M10 | dead/duplicate child tests | PID is corroboration only | Megaplan runtime | partial |
| human suspend/resume/approval | markers, cursor, CLI state | signed decision/effect history | M8 | stale approval/replay tests | no marker-only resume | WBC / Run Authority | partial |
| chain state writer/driver | `.chains/*.json`, logs, plan state | chain projection from accepted milestone events | M7/M8 | restart/advance replay | no raw terminal shortcut | custody / chain | legacy |
| chain advancement/guards | mixed plan/chain/PR status | authoritative reducer + post-reread | M9 | stale terminal/merged PR tests | raw guard branches removed | Run Authority / custody | partial |
| chain completion manifests | generated content-addressed proof | portfolio admission evidence only; never runtime action authority | M11 | manifest validator/hash mutation | no nominal done dependency or manifest-only action | Megaplan chain | substrate |
| PR merge/publication supervisor | PR/CI API plus state cursor | effect intent/outcome + publication view | M8/M10 | duplicate merge/reconcile tests | no PR label/status authority | Run Authority / Native Platform | partial |
| Git/provider effects | subprocess/API result | reconciled non-compensable effect record | M10 | ambiguous timeout/retry tests | blind replay forbidden | Native Platform | partial |
| CLI status/projection | raw state + compatibility formatter | rebuildable multidimensional view | M9 | parity/rebuild snapshots | no raw status fallback for actions | custody-control-plane | partial |
| introspect/trace/doctor | events, state, process probes | pure observer over history/evidence | M9 | observer-purity test | reads cannot refresh activity | custody-control-plane | partial |
| status projection module | mixed source presentation | signed/versioned projection | M9 | delete/rebuild hash | projection never authority | custody-control-plane | partial |
| cloud status snapshot/formatter | markers/state/watchdog/process best effort | view-only reducer snapshot | M9 | freshness/cursor/drift tests | no control read from snapshot | custody-control-plane | partial |
| cloud current-target selector | precedence across marker/live/state/chain | history target identity decision | M9 | deleted/stale selector tests | disagreement returns unknown | custody-control-plane | legacy |
| cloud session markers | launch/session projection | immutable launch evidence ref | M9 | stale/cross-environment tests | marker cannot prove active/complete | Megaplan Cloud | legacy |
| watchdog Python discovery | filesystem/state/mtime/process scan | coherent evidence collector only | M9 | unrelated-process false liveness | classifier consumes history view | custody-control-plane | partial |
| `arnold-watchdog` wrapper | duplicated shell selectors/classifiers | thin input/output adapter | M9/M11 | static no-authority scan | duplicated branches deleted | custody-control-plane | legacy |
| progress auditor/L3 | ledger plus snapshots and wrappers | read-only audit of reducer/custody | M9/M10 | lying-resolver/recursion tests | cannot mutate/claim custody | Maintenance / custody | partial |
| six-hour unblocker | observations + repair request path | history occurrence/custody consumer | M9/M10 | exact-window/fence tests | no independent transition writer | megaplan-maintenance | planned |
| daily efficiency auditor | read-only analytic projections | immutable history analytics | M9 | mutation-negative tests | no repair/ticket authority | megaplan-maintenance | planned |
| human-blocker markers/classifier | marker lifecycle plus raw facts | history decision projection | M9 | stale marker tests | marker cannot outrank reducer | custody-control-plane | partial |
| repair request queue | queue files/systemd trigger | history request/claim projection | M7/M10 | duplicate/idempotency tests | trigger only nudges canonical dispatcher | custody-control-plane | partial |
| repair locks/leases | blocker file locks, active claims, and repair projections | `CustodyTargetKey`/`RepairOccurrenceKey` plus renewable `CustodyLease` event stream and monotonic custody epoch joined to current Run Authority grant/fence | M7/M10 | expiry/renew/transfer/cross-host reclaim/stale-worker/PID-reuse tests | no effect without both current grant/fence and current lease/epoch; queue lock/projection never authority | custody-control-plane | partial |
| repair-data/repair contract | JSON custody buckets/attempts | compatibility projection from history | M7/M10/M11 | replay/sidecar drift | zero authority readers then delete | custody-control-plane | legacy |
| L1 repair loop | wrapper/queue/raw status decisions | fenced occurrence repair policy | M10 | fault matrix | only canonical claims act | custody-control-plane | partial |
| L2 meta-repair | meta records/retrigger verification | history attempt + independent verifier | M10 | nonzero/dead retrigger tests | cannot self-record FIXED | custody-control-plane | partial |
| L3/audit repair | gather/recommend/escalate | read-only audit events | M10 | recursion/false-FIXED tests | human escalation, no self-repair | custody-control-plane | partial |
| source/install/retrigger repair | commits/install hashes/process relaunch | distinct fenced effect events | M10 | wrong-install/retrigger failure | liveness never terminal success | custody-control-plane | partial |
| independent recovery verification | optional/delayed repair evidence | mandatory later negative control + progress | M10 | immediate/5m/1h/6h tests | only verifier closes | custody / Maintenance | planned |
| resident inbound message/turn | resident store and conversation cursor | immutable root custody provenance | M8 | burst/restart provenance tests | no inference from final text | Discord corrective / custody | partial |
| resident managed child launch | manifest/run PID/result | child attempt under parent/root custody | M8/M10 | duplicate launch/lineage tests | no unparented child for managed task | Discord corrective / custody | partial |
| resident completion outbox | per-child auto-delivery state | parent-owned aggregated delivery effect | M8/M10 | no-independent-child-delivery test | child outbox suppressed by contract | Discord corrective / custody | legacy |
| ordinary resident reply | DB message then Discord send then turn completion | durable intent/provider receipt effect outbox | M10 | crash before/after send/turn completion | no inbound replay early-return without outcome | Discord corrective / custody | legacy |
| scheduled notification | metadata and fire lifecycle split around send | same durable effect outbox and nonce receipt | M10 | swallowed-send and duplicate-reclaim tests | `already_persisted` cannot suppress unknown send | Resident / custody | legacy |
| resident scheduler/todo sweep | mutable hot context and run scan | history custody/read model | M9 | restart/duplicate todo tests | no cursor-derived authority | Resident / custody | partial |
| Discord status/follow-up | snapshot/local fallback prose | non-authoritative projection from history | M9 | degraded/unknown UX tests | fallback cannot dispatch | Resident / custody | partial |
| AgentBox guardian/reconcile | operation state/tmux/process views | target/custody reducer consumer | M9/M10 | dead/unrelated process tests | no operation status authority | AgentBox / custody | partial |
| cloud resident service/heartbeat | systemd/tmux/heartbeat freshness | runner lease and correlated heartbeat event | M9 | hung-live/dead-worker tests | service alive != run alive | AgentBox / custody | legacy |
| cloud provider/local/SSH adapters | process/API observations | evidence adapters plus effect outcomes | M9/M10 | cross-provider parity | no provider-local control truth | Megaplan Cloud | partial |
| cloud repair wrappers | generated shell with selectors/retries | thin calls to history APIs | M10/M11 | static/runtime bypass scan | delete embedded classifiers/writers | custody-control-plane | legacy |
| cloud/source initiative repair | source/branch/install state | fenced effects with SHA reread | M10 | stale install/post-mutation retry | no success before reread | custody-control-plane | partial |
| notification safety/delivery | separate safety and outbox projections | history effect + target receipt + supersession | M10 | ambiguous send/retry tests | no prose-only delivered claim | Discord corrective | partial |
| WBC declarations/attempt ledger | C1-C6-owned schemas; exact final merge commit pending; audited candidate ledger is schema-only | exact-version transactional boundary/evidence store/API joined to Run Authority and Custody IDs but granting neither capability nor lease | M6/M6A/M8/M11 | exact landed/runtime proof plus store, call-site set equality, runtime traces, fault/replay and bypass-negative suite | do not rename/duplicate; support manifest or receipts/projections alone never pass or act | workflow-boundary-contracts | blocked substrate/adoption |
| WBC payload/privacy/retention/encryption | schema validators and policy metadata; no audited stored-byte enforcement | tenant/access-enforced encrypted durable references, retention/legal hold/tombstone/deletion evidence and key/version audit | M6A/M9/M11 | cross-tenant, missing-key, retention/hold/tombstone/deletion tests against stored bytes | no protected payload defaulting to unencrypted; no unaudited delete | workflow-boundary-contracts | blocked substrate |
| WBC schema/data migration | no audited transactional WBC storage migration/backfill | checksummed, crash-resumable, idempotent, mixed-version migration with explicit unknown legacy records | M6A/M9/M10/M11 | every supported version, interruption/resume, corrupt/partial, duplicate backfill and rollback/forward-fix tests | never fabricate success or rewrite history | workflow-boundary-contracts | blocked substrate |
| WBC universal producer adoption | audited 35-contract matrix: 5 auto, 8 manual emission, 13 declared-only, 9 unknown | every declared and discovered boundary writes durable start, all required phase/effect evidence, and exactly one terminal/indeterminate through WBC API | M6/M8/M10/M11 | generated contract/call-site/runtime-trace set equality plus positive, negative and failure/replay cases | no evidence-only/best-effort/swallowed/`|| true` required write; zero legacy writers | workflow-boundary-contracts with named runtime owners | blocked adoption |
| WBC universal consumer adoption | no audited canonical query use in status/cloud/resident/repair/chain operational consumers | exact-version WBC query API across status, watchdog/repair/auditor, chain/publication, resident/cloud, retention/migration and trace | M9/M11 | generated consumer inventory and raw-state/prose/token/implicit-latest negative tests | no optimistic or fail-open fallback; historical adapters read-only with expiry | named consumer owners; WBC owns query semantics | blocked adoption |
| WBC semantic findings | WBC-owned durable findings mapped to repair | evidence/decision refs; no self-clear | M6/M8/M10 | WBC manifest plus finding-to-verification tests | no second repair/status authority | workflow-boundary-contracts | prerequisite-WBC |
| Native Parity Corrective | source/evidence alignment chain | topology owner, consumed by WBC/custody | M6/M8 | completion/traceability proof | no assumed completion | native parity | gate |
| Evidence-First Pipeline Semantics | historical contracts/partial work | lineage only, no parallel authority | M6/M11 | ownership map | no relaunch as control plane | portfolio | legacy |
| Canonical Run-State Control Plane | one-sprint resolver precursor | superseded by custody-control-plane | M6/M11 | initiative supersession check | no parallel launch | portfolio | retired |
| incident/superfixer/tiered initiatives | retired precursor scopes | custody-control-plane only | M6/M11 | retirement markers/session scan | remain merge/launch disabled | portfolio | retired |
| Megaplan Maintenance | shared ledger/repair/audit product plan | consumer of canonical history/custody | M9/M10 | contract compatibility suite | no second ledger/writer | megaplan-maintenance | adjacent |
| archived/historical runs | legacy files and schemas | read-only versioned adapters | M11 | old-run/new-reader corpus | never normalize by write | custody-control-plane | legacy |
| installed/editable/cloud runtime | potentially divergent source trees | identical pinned contract/runtime SHA | M11 | import/source SHA gate | no rollout on mismatch | deployment human gate | gate |
| compatibility aliases (`planning`, old paths) | callable legacy imports/routes | fail-closed read-only adapters | M11 | zero authority caller scan | delete after cross-version proof | cleanup/native parity | legacy |
| selectors/test selection/baselines | files/change metadata and defaults | selector receipt from canonical source/version | M8/M11 | deleted/stale selector tests | selector absence never broadens authority | Megaplan orchestration | partial |
| planner DAG dependencies/routing | `depends_on` also serializes routing; no reason/critical-path feasibility | semantic dependency reasons plus separate `routing_group`, seriality/width/turn feasibility report | M8A | captured Transaction/Strategy replay and historical false-positive corpus | reject infeasible/unexplained serial DAG before execute | planner/compiler | legacy |
| complexity/task proof budgets | uniform turn ceilings combine implementation and proof | complexity >=7 split/checkpoint or explicit authorized budget | M8A | T7/T12 and complexity-8/9 admission fixtures | typed blocker/checkpoint; no blind retry or discarded work | planner/compiler + executor | legacy |
| deterministic validation tasks | no-file checks dispatched to models | content-addressed harness validation job | M8A | Strategy T10/T12/T15-equivalent zero-model-call parity | ambiguous/mutating check stays explicit; never guessed mechanical | planner/compiler + executor | legacy |
| launcher ref/runtime preflight | invalid refs and divergent installs repeatedly retried | one bounded validation/suggestion plus source/install/runtime version receipt | M8A/M11 | invalid-ref/dirty-source fixture and installed-runtime canary | unresolved mismatch blocks launch | launcher/runtime packaging | legacy |
| provider/summary/import/compaction policy | repeated invalid route/timeouts, target/runtime import leak, unbounded compaction | pre-resolved model, isolated imports, timeout/failover/compaction circuit | M8A | empty-model/import/300s-timeout/repeat-compaction fixtures | visible terminal/escalation; no ambient fallback | executor | legacy |
| review rework fanout | review can exceed normal wave ceiling | rework compiled and granted under normal maximum scope | M8A | six-task fixture splits to configured ceiling | oversized grant rejected before launch | planner/compiler + executor | legacy |
| normalized executor failure circuit | task-specific strings hide repeated budget exhaustion | normalized class with exact attempt identity; circuit after two equivalents | M8A | T7+T12 fixture blocks third blind retry | open circuit requires split/budget authority | executor | legacy |
| repair receipt adoption | fixed work cannot become an accepted checkpoint | immutable receipt plus current verify-only Run Authority acceptance | M7/M8A | valid receipt avoids replay; revision/tree/test/fence mutations quarantine | mismatch executes normally; never implicit adoption | WBC + Run Authority + executor | legacy |
| work/token/cost classification | raw totals cannot separate legitimate work from replay/wait | joined task/batch/attempt ledger with productive/proof/review/replay/wait classes | M6/M8A/M9 | captured totals reconcile with unknown reasons and accepted-output denominator | missing denominator is unknown, never zero/waste | observability + Maintenance | planned |
| event-driven recovery trigger | hourly scan is primary discovery | deduplicated durable block/exit trigger, exact live signature/fence, six-hour reconciliation backstop | M10/M11 | lost/duplicate/out-of-order fixtures, p95 <5m canary, genuine blocked run | ambiguous delivery stays pending; no duplicate launch | repair custody + Run Authority + Maintenance backstop | legacy |
| PC adjacent work | program counter / Parity Corrective / control plane ambiguous | explicitly owned typed scope | M6 | `PC_SCOPE_DECISION` | M7 blocked on material overlap | human portfolio gate | gate |

## Adversarial acceptance catalog

M5 repairs prerequisite evidence; M6 freezes fixtures/inventory; M6A builds the
WBC substrate; M7-M10 implement and adopt the composed contracts;
M11 runs the integrated matrix.

| Scenario | Required result |
|---|---|
| stale contract / deleted selector | reject before dispatch; name exact missing version/selector |
| torn evidence | bounded reread then `INCOHERENT`/`UNKNOWN`; zero action |
| unrelated process false liveness | process excluded by immutable run/attempt identity |
| dead worker | lease expires, attempt remains, recovery not claimed |
| duplicate dispatch | one accepted fenced attempt; duplicate is idempotent/rejected |
| swallowed fallback | visible terminal fallback failure; no silent primary result |
| post-mutation retry | reconcile/reread; new authority required before retry |
| observer/runner confusion | observer emits no activity and cannot look like runner |
| partial persistence | dead letter/pending reconciliation; never success |
| replay/restart | deterministic same projections and no repeated effects |
| cloud/resident divergence | drift emitted, action blocked until coherent |
| old-reader/new-writer | versioned compatibility projection with unknowns |
| new-reader/old-run | exact legacy adapter, read-only, no normalization write |
| stale fence/reclaimed custody | old worker effects rejected |
| self-verification | terminal closure rejected |
| projection deletion | full rebuild matches digest and ordering |
