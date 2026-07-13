---
type: research
date: 2026-07-11
schema: custody-control-plane-migration-matrix-v1
---

# Exhaustive authority migration matrix

Status vocabulary: `substrate` means the right primitive exists but coverage is
not proven; `legacy` means authority can still be inferred or written outside
the target; `in-flight-WBC` is externally owned and must be consumed unchanged;
`gate` requires human/manifest evidence; `target` is planned end state.

The table's **Proof** column is the required shadow/conformance proof for that
surface. The following execution columns apply normatively to every row, rather
than being optional defaults:

| Required column | Per-row contract |
|---|---|
| Fail-closed behavior | If the row's exact contract/version, fence, coherent evidence, owner, or listed proof is absent or contradictory, the reducer returns `UNKNOWN`/`INCOHERENT`, emits drift, and performs zero authority-increasing transition, dispatch, retry, repair, delivery, publication, or deletion. |
| Rollback / mixed-version policy | Shadow before enforcement; old readers may consume only an explicit, expiring compatibility projection; old writers are rejected after cutover. Rollback disables promotion/effects and keeps append, reconciliation, and evidence intact—never restoring raw legacy authority or rewriting history. Row-specific stricter rules in milestone briefs and the decision record win. |
| Completion evidence | The listed proof artifact, exact source/runtime/contract hashes, migration owner sign-off, authoritative-history/replay evidence, zero legacy authority-reader/writer scan for the row, rollback result, and M10 proof-map entry. A generated completion manifest must hash the proof; status text or nominal milestone completion is insufficient. |

Thus each legacy path below is mapped to target contract, owner/milestone,
shadow/conformance proof, fail-closed behavior, deletion gate, mixed-version and
rollback policy, and completion evidence. No row may claim an exception by
omitting one of these inherited columns.

| Consumer / surface | Current authority | Target authority | Milestone | Shadow / conformance proof | Deletion gate | Owner / initiative | Status |
|---|---|---|---|---|---|---|---|
| Kernel `WorkflowManifest` identity | compiled manifest plus package identity | exact hash/version recorded on every attempt | M5/M7 | stale-version and missing-manifest tests | no implicit-latest lookup | Native Platform | substrate |
| Kernel NDJSON journal | append-only generic runtime events | shared causal history backend/envelope | M6 | append/CAS/replay conformance | old journal adapter read-only | custody-control-plane | substrate |
| Native persistence checkpoint/cursor | checkpoint JSON including native `pc` | versioned evidence projection bound to accepted attempt | M7 | corrupt/stale/deleted cursor tests | bare `pc` banned outside schema | Native Platform; PC gate | legacy |
| Native trace hooks (`state/events/stages/artifacts/checkpoint`) | parallel trace files | projections/evidence refs from one history | M7/M10 | delete/rebuild and hash proof | zero authority readers | Native Platform | legacy |
| `.pypeline` and named subworkflows | intended topology authority | unchanged topology plus exact boundary evidence | M7 | native traceability/conformance | component/handler routes deleted | Native Parity | substrate, manifest absent |
| Component/handler route tables | callable compatibility topology | non-authoritative adapter or deletion | M7/M10 | negative execution-authority tests | zero runtime route reads | Native Parity | legacy |
| Graph/native-program projections | generated route/topology views | rebuildable source projection | M7/M10 | source-to-projection parity | no dynamic authority fallback | Native Parity | legacy |
| `RunAuthorityKernel` grants | grant/fence contracts | same records in joined causal history | M6 | grant/fence/quarantine tests | raw dispatch forbidden | runauthority-epic | substrate; landing gate |
| Accepted attempt/decision reducer | deterministic Run Authority view | canonical acceptance facet | M6/M7 | stale/off-scope result quarantine | artifact labels never accepted | runauthority-epic | substrate |
| Runner/publication/human/recovery views | separate domain views | versioned projections from history/evidence | M8 | multidimensional fixture suite | aggregate optimistic status removed | runauthority-epic | substrate |
| Canonical run-state resolver | ordered raw evidence classifier | read-coherent reducer/evidence binding | M5/M8 | torn-read and parity tests | noncanonical dispatch rejected | custody-control-plane M1-M4 | substrate |
| Run-state classifiers | local precedence rules | pure policy over coherent versioned envelope | M8 | all July incident fixtures | duplicate classifiers deleted | custody-control-plane | substrate |
| `state.json` writer / merge-on-save | mutable plan truth plus append-only meta | compatibility projection writer after history append | M6 | crash between append/project edges | direct authoritative save fails | custody-control-plane | legacy |
| `state.json` readers | widespread phase/status/resume reads | signed projection or reducer query | M7/M8/M10 | generated reader inventory | zero authority-increasing reads | custody-control-plane | legacy |
| Plan `events.ndjson` | detailed but separate plan journal | migrated/imported causal event stream | M6 | ordering/parent/attempt replay | no activity authority from mtime | custody-control-plane | legacy/substrate |
| `phase_result.json` | stage terminal claim | evidence ref awaiting accepted decision | M7 | stale/partial terminal tests | labels cannot advance | WBC + custody | partial |
| receipts/routing/cost ledgers | separate append logs | evidence/effect events linked by attempt | M6/M7 | join completeness and replay | unlinked receipts diagnostic only | WBC / observability | partial |
| effect ledger/enforcement | local effect records | history intent/outcome/idempotency/reconcile | M6/M9 | crash matrix; provider reconcile | no sidecar retry | Native Platform / custody | partial |
| prep/plan/revise stages | handler/native stage state | exact-version attempt boundaries | M7 | start/terminal/stale-fence/CAS/reread tests | direct plan/chain mutation blocked | custody-control-plane | substrate |
| CLI override/user actions | append some resolution metadata and mutate state | authorized decision + transition append | M6/M7 | replay/idempotency/permission tests | raw override state edits fail | Megaplan | legacy |
| prep/plan/revise stages | handlers and state/artifact writes | exact-version attempt/boundary events | M7 | start/terminal/persistence faults | unledgered stage refused | WBC C2-C3 | in-flight-WBC |
| critique/gate/tiebreaker/reducer stages | handler results, verdict artifacts and mutable state | exact-version attempts plus accepted Run Authority decisions | M7 | split-verdict/retry/reducer/replay tests | checkpoint-only completion forbidden | WBC / Run Authority | partial |
| finalize/execute/review/feedback stages | artifacts, batch checkpoints, receipts and state | causal attempts/effects with post-transition reread | M7/M9 | partial batch, approval, rework and retry tests | artifact label never advances alone | WBC / Run Authority | partial |
| fallback chains/model seam | configured retry/fallback specs | history decision per attempt/fallback | M7/M9 | swallowed fallback tests | unsafe fallback fails visible | Megaplan runtime | legacy |
| worker/process fanout | PID/result files | parent/child attempts with leases | M7/M9 | dead/duplicate child tests | PID is corroboration only | Megaplan runtime | partial |
| human suspend/resume/approval | markers, cursor, CLI state | signed decision/effect history | M7 | stale approval/replay tests | no marker-only resume | WBC / Run Authority | partial |
| chain state writer/driver | `.chains/*.json`, logs, plan state | chain projection from accepted milestone events | M6/M7 | restart/advance replay | no raw terminal shortcut | custody / chain | legacy |
| chain advancement/guards | mixed plan/chain/PR status | authoritative reducer + post-reread | M8 | stale terminal/merged PR tests | raw guard branches removed | Run Authority / custody | partial |
| chain completion manifests | generated content-addressed proof | authoritative portfolio prerequisite evidence | M10 | manifest validator/hash mutation | no nominal done dependency | Megaplan chain | substrate |
| PR merge/publication supervisor | PR/CI API plus state cursor | effect intent/outcome + publication view | M7/M9 | duplicate merge/reconcile tests | no PR label/status authority | Run Authority / Native Platform | partial |
| Git/provider effects | subprocess/API result | reconciled non-compensable effect record | M9 | ambiguous timeout/retry tests | blind replay forbidden | Native Platform | partial |
| CLI status/projection | raw state + compatibility formatter | rebuildable multidimensional view | M8 | parity/rebuild snapshots | no raw status fallback for actions | custody-control-plane | partial |
| introspect/trace/doctor | events, state, process probes | pure observer over history/evidence | M8 | observer-purity test | reads cannot refresh activity | custody-control-plane | partial |
| status projection module | mixed source presentation | signed/versioned projection | M8 | delete/rebuild hash | projection never authority | custody-control-plane | partial |
| cloud status snapshot/formatter | markers/state/watchdog/process best effort | view-only reducer snapshot | M8 | freshness/cursor/drift tests | no control read from snapshot | custody-control-plane | partial |
| cloud current-target selector | precedence across marker/live/state/chain | history target identity decision | M8 | deleted/stale selector tests | disagreement returns unknown | custody-control-plane | legacy |
| cloud session markers | launch/session projection | immutable launch evidence ref | M8 | stale/cross-environment tests | marker cannot prove active/complete | Megaplan Cloud | legacy |
| watchdog Python discovery | filesystem/state/mtime/process scan | coherent evidence collector only | M8 | unrelated-process false liveness | classifier consumes history view | custody-control-plane | partial |
| `arnold-watchdog` wrapper | duplicated shell selectors/classifiers | thin input/output adapter | M8/M10 | static no-authority scan | duplicated branches deleted | custody-control-plane | legacy |
| progress auditor/L3 | ledger plus snapshots and wrappers | read-only audit of reducer/custody | M8/M9 | lying-resolver/recursion tests | cannot mutate/claim custody | Maintenance / custody | partial |
| six-hour unblocker | observations + repair request path | history occurrence/custody consumer | M8/M9 | exact-window/fence tests | no independent transition writer | megaplan-maintenance | planned |
| daily efficiency auditor | read-only analytic projections | immutable history analytics | M8 | mutation-negative tests | no repair/ticket authority | megaplan-maintenance | planned |
| human-blocker markers/classifier | marker lifecycle plus raw facts | history decision projection | M8 | stale marker tests | marker cannot outrank reducer | custody-control-plane | partial |
| repair request queue | queue files/systemd trigger | history request/claim projection | M6/M9 | duplicate/idempotency tests | trigger only nudges canonical dispatcher | custody-control-plane | partial |
| repair locks/leases | file locks and records | renewable fenced custody event | M6/M9 | expiry/reclaim/stale-worker tests | no effect without current fence | custody-control-plane | partial |
| repair-data/repair contract | JSON custody buckets/attempts | compatibility projection from history | M6/M9/M10 | replay/sidecar drift | zero authority readers then delete | custody-control-plane | legacy |
| L1 repair loop | wrapper/queue/raw status decisions | fenced occurrence repair policy | M9 | fault matrix | only canonical claims act | custody-control-plane | partial |
| L2 meta-repair | meta records/retrigger verification | history attempt + independent verifier | M9 | nonzero/dead retrigger tests | cannot self-record FIXED | custody-control-plane | partial |
| L3/audit repair | gather/recommend/escalate | read-only audit events | M9 | recursion/false-FIXED tests | human escalation, no self-repair | custody-control-plane | partial |
| source/install/retrigger repair | commits/install hashes/process relaunch | distinct fenced effect events | M9 | wrong-install/retrigger failure | liveness never terminal success | custody-control-plane | partial |
| independent recovery verification | optional/delayed repair evidence | mandatory later negative control + progress | M9 | immediate/5m/1h/6h tests | only verifier closes | custody / Maintenance | planned |
| resident inbound message/turn | resident store and conversation cursor | immutable root custody provenance | M7 | burst/restart provenance tests | no inference from final text | Discord corrective / custody | partial |
| resident managed child launch | manifest/run PID/result | child attempt under parent/root custody | M7/M9 | duplicate launch/lineage tests | no unparented child for managed task | Discord corrective / custody | partial |
| resident completion outbox | per-child auto-delivery state | parent-owned aggregated delivery effect | M7/M9 | no-independent-child-delivery test | child outbox suppressed by contract | Discord corrective / custody | legacy |
| ordinary resident reply | DB message then Discord send then turn completion | durable intent/provider receipt effect outbox | M9 | crash before/after send/turn completion | no inbound replay early-return without outcome | Discord corrective / custody | legacy |
| scheduled notification | metadata and fire lifecycle split around send | same durable effect outbox and nonce receipt | M9 | swallowed-send and duplicate-reclaim tests | `already_persisted` cannot suppress unknown send | Resident / custody | legacy |
| resident scheduler/todo sweep | mutable hot context and run scan | history custody/read model | M8 | restart/duplicate todo tests | no cursor-derived authority | Resident / custody | partial |
| Discord status/follow-up | snapshot/local fallback prose | non-authoritative projection from history | M8 | degraded/unknown UX tests | fallback cannot dispatch | Resident / custody | partial |
| AgentBox guardian/reconcile | operation state/tmux/process views | target/custody reducer consumer | M8/M9 | dead/unrelated process tests | no operation status authority | AgentBox / custody | partial |
| cloud resident service/heartbeat | systemd/tmux/heartbeat freshness | runner lease and correlated heartbeat event | M8 | hung-live/dead-worker tests | service alive != run alive | AgentBox / custody | legacy |
| cloud provider/local/SSH adapters | process/API observations | evidence adapters plus effect outcomes | M8/M9 | cross-provider parity | no provider-local control truth | Megaplan Cloud | partial |
| cloud repair wrappers | generated shell with selectors/retries | thin calls to history APIs | M9/M10 | static/runtime bypass scan | delete embedded classifiers/writers | custody-control-plane | legacy |
| cloud/source initiative repair | source/branch/install state | fenced effects with SHA reread | M9 | stale install/post-mutation retry | no success before reread | custody-control-plane | partial |
| notification safety/delivery | separate safety and outbox projections | history effect + target receipt + supersession | M9 | ambiguous send/retry tests | no prose-only delivered claim | Discord corrective | partial |
| WBC declarations/attempt ledger | in-flight C1-C6 contracts | exact-version boundary facet of history | M7/M10 | WBC manifest/support matrix | do not rename/duplicate; deletion waits | workflow-boundary-contracts | in-flight |
| WBC semantic findings | durable findings mapped to repair | evidence/decision refs; no self-clear | M7/M9 | finding-to-verification tests | no second repair/status authority | workflow-boundary-contracts | in-flight |
| Native Parity Corrective | source/evidence alignment chain | topology owner, consumed by WBC/custody | M5/M7 | completion/traceability proof | no assumed completion | native parity | gate |
| Evidence-First Pipeline Semantics | historical contracts/partial work | lineage only, no parallel authority | M5/M10 | ownership map | no relaunch as control plane | portfolio | legacy |
| Canonical Run-State Control Plane | one-sprint resolver precursor | superseded by custody-control-plane | M5/M10 | initiative supersession check | no parallel launch | portfolio | retired |
| incident/superfixer/tiered initiatives | retired precursor scopes | custody-control-plane only | M5/M10 | retirement markers/session scan | remain merge/launch disabled | portfolio | retired |
| Megaplan Maintenance | shared ledger/repair/audit product plan | consumer of canonical history/custody | M8/M9 | contract compatibility suite | no second ledger/writer | megaplan-maintenance | adjacent |
| archived/historical runs | legacy files and schemas | read-only versioned adapters | M10 | old-run/new-reader corpus | never normalize by write | custody-control-plane | legacy |
| installed/editable/cloud runtime | potentially divergent source trees | identical pinned contract/runtime SHA | M10 | import/source SHA gate | no rollout on mismatch | deployment human gate | gate |
| compatibility aliases (`planning`, old paths) | callable legacy imports/routes | fail-closed read-only adapters | M10 | zero authority caller scan | delete after cross-version proof | cleanup/native parity | legacy |
| selectors/test selection/baselines | files/change metadata and defaults | selector receipt from canonical source/version | M7/M10 | deleted/stale selector tests | selector absence never broadens authority | Megaplan orchestration | partial |
| PC adjacent work | program counter / Parity Corrective / control plane ambiguous | explicitly owned typed scope | M5 | `PC_SCOPE_DECISION` | M6 blocked on material overlap | human portfolio gate | gate |

## Adversarial acceptance catalog

M5 freezes fixtures; M6-M9 implement them; M10 runs the integrated matrix.

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
