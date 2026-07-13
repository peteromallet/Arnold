# Codex 5.6 Sol audit: autofixing and six-hour feedback

**Audit timestamp:** 2026-07-10T19:10:12Z  
**Scope:** automatic detection, diagnosis, L1 repair/superfixer, L2 meta-repair, watchdog supervision, and the L3 six-hour progress-auditor loop  
**Repository:** `/workspace/arnold` at `fbcfff10fa29c7ce8cab5489859e8db5411a8683` (`v0.20.0-4432-gfbcfff10f-dirty`)  
**Mode:** read-only architecture and evidence audit. No production code was changed. This report is the only file created by this audit.

## Executive assessment

Arnold has the right high-level shape: fast lifecycle detection feeds an immediate repair loop; an hourly watchdog supplies a durable backstop; L2 meta-repair can repair a defective L1; and a six-hour L3 audit reconciles broader evidence. The code also contains useful foundations: typed run-state classifications, conservative `UNKNOWN` outcomes, bounded repair attempts, active-claim locks, an append-only incident journal, heartbeat supervision, recurrence records, and extensive unit/contract coverage.

The implementation does not yet form one trustworthy closed loop. Five integration failures dominate the risk:

1. **The L3 auditor's current-target adapter calls `resolve_current_target()` with arguments that the implementation does not accept.** The exception is caught and converted to fallback evidence, so the audit continues while silently losing the canonical target. The corresponding test stub accepts arbitrary keyword arguments and therefore masks the defect.
2. **The final L3 report asserts `report_only` and `autofix_enabled: false` even after the wrapper conditionally dispatches an autofix agent.** The tests require this false summary. At the same time, mutation-related feature flags default on and the nominal master autonomy flag is not an effective global gate.
3. **Some immediate repair requests are written to `.megaplan/plans/repair-queue`, while the systemd path unit and watchdog scan `/workspace/.megaplan/repair-queue`.** In addition, the supervisor exits on the common repeated-same-error threshold before its queueing branch. These failures can therefore wait for a later watchdog inference instead of entering the advertised immediate path.
4. **Liveness is inconsistently treated as both non-success and verified recovery.** L1's current contract correctly excludes `live_with_fresh_activity` from success, but L2 accepts it as retrigger success and appends `verified_recovered`. All five locally recorded `verified_recovered` summaries use this liveness-only result. A running process is not proof that the original blocker cleared.
5. **There is no single enforced, read-coherent authority.** The custody design calls for one resolver and transition writer, but watchdog/status/chain paths still assemble and classify evidence differently; L1 can directly rewrite plan and chain state under a repair lock rather than the lifecycle transition authority. The result can be a plausible but internally inconsistent snapshot.

The first release should therefore be a containment release, not a larger autonomous repair release: make action reporting truthful, put all mutation behind an effective default-off gate, repair the L3 adapter and queue topology, and forbid liveness-only recovery. Then introduce versioned observation/attempt/verification contracts and one read-coherent resolver before enabling canonical enforcement. Delayed, independent verification at 5 minutes, 1 hour, and 6 hours should be the definition of a genuinely effective fix.

## Scope, evidence, and limitations

### Examined implementation

- Detection and workflow integration: `arnold_pipelines/megaplan/auto.py`, especially `_enqueue_lifecycle_failure_request`; `arnold_pipelines/megaplan/cloud/wrappers/arnold-supervise`.
- Queueing, dispatch, and recurrence: `arnold_pipelines/megaplan/cloud/repair_requests.py`, `repair_recurrence.py`, `repair_contract.py`, and `wrappers/arnold-repair-trigger`.
- L1 and watchdog: `wrappers/arnold-repair-loop`, `wrappers/arnold-watchdog`, `status_snapshot.py`, and the watchdog Python package.
- L2: `wrappers/arnold-meta-repair-loop`, `meta_repair.py`, and `incident_bridge.py`.
- L3: `wrappers/arnold-progress-auditor`, `six_hour_auditor.py`, progress-auditor tests, systemd service/timer definitions, and the external CI/engine evidence path.
- Authority and feature control: `current_target.py`, `run_state/{evidence,model,classifiers,resolver}.py`, both `cloud/feature_flags.py` and `feature_flags.py`, and the chain/status guard paths.
- Resident supervision: `cloud/systemd/megaplan-progress-audit.{service,timer}`, `megaplan-repair-trigger.{service,path}`, `megaplan-watchdog-ensure.{service,timer}`, `ensure-megaplan-watchdog`, and `cloud/templates/entrypoint.sh.tmpl`.

The three main shell wrappers are unusually large: approximately 7,305 lines for watchdog, 6,171 for L1 repair, and 4,462 for the progress auditor. This matters because state classification, policy, subprocess orchestration, and report construction are duplicated across shell/Python boundaries.

### Examined intended-design material

- `docs/ops/tiered-repair-and-audit-loop.md`
- `docs/ops/tiered-repair-data-contract.md`
- `docs/hetzner-watchdog-meta-loop.md`
- `.megaplan/initiatives/custody-control-plane/NORTHSTAR.md` and its M1-M4 briefs
- `.megaplan/initiatives/workflow-boundary-contracts/NORTHSTAR.md`
- `.megaplan/initiatives/progress-auditor-stage-metrics/NORTHSTAR.md`
- `.megaplan/initiatives/progress-auditor-stage-metrics/research/auditor_signal_swarm_synthesis_20260704.md`
- `.megaplan/audits/6hr-auditor-20way-subagent-review-20260703.md`
- `docs/arnold/watchdog-snapshot-staleness-fix.md`
- Superseded initiative material under `.megaplan/initiatives/tiered-repair-hardening`, `incident-control-plane`, and `superfixer-repair-custody`.

### Examined local operational evidence

- `.megaplan/incident-ledger/events.jsonl`, `incidents.json`, `problems.json`, and summary indexes.
- `.megaplan/cloud-chain-custody-control-plane.log`.
- `.megaplan/cloud-chain-progress-auditor-stage-metrics.log`.
- `.megaplan/watchdog-run-logs/`.
- Git history and current working-tree state.

### Verification performed

The following tests were run from `/tmp` with bytecode and pytest cache writes disabled, leaving the repository untouched:

- `tests/cloud/test_six_hour_auditor.py`, `test_repair_contract.py`, and `test_meta_repair.py`: **244 passed**.
- Current-target, dispatch, resolver-enforcement, repair-request, and recurrence tests: **147 passed**.
- `tests/cloud/test_progress_auditor.py`: **96 passed**.
- Focused repair-wrapper tests covering terminal-plan behavior, chain health, partial liveness, and resolver behavior: **5 passed**, 251 deselected.
- `bash -n` on the four principal wrappers: **passed**.

These results establish local syntax and the invariants the tests currently express. They do not establish end-to-end correctness: two material defects below are actively hidden by permissive stubs or asserted as desired behavior.

### Historical findings that triangulate this audit

- `.megaplan/audits/6hr-auditor-20way-subagent-review-20260703.md` records a 20-of-20 review in which the system was predominantly rated weak or partial. Its most consistent gaps were post-fix verification, persistent identity, operational telemetry, and freshness. The present code has added pieces in all four areas, but the liveness/closure contradiction and stale local projections show that they are not yet closed end to end.
- `.megaplan/initiatives/progress-auditor-stage-metrics/research/auditor_signal_swarm_synthesis_20260704.md` recommends separating deterministic gather/report from interpretation/action, stable coverage/data-quality fields, explicit dispatch reporting, and negative controls. The hard-coded dispatch summary and missing-to-green behavior are direct regressions against that advice.
- Initiative decisions refer to a real cloud audit at `/workspace/audit-reports/20260704T110403Z-audit.json` with 35 findings, zero green sessions, 17 ghost-running cases, and 18 green-with-churn cases. The artifact is not locally present, so these numbers are cited only as a historical claim in the decision material, not independently verified evidence.
- `.megaplan/watchdog-run-logs/` preserves older repeated same-error loops, import-shadowing failures, enum/contract mismatch, and engine-isolation problems. Those files date from June 14–15 and are not current cloud watchdog reports, but they support treating repeated-failure queueing and interface/schema drift as recurring failure classes.
- `docs/arnold/watchdog-snapshot-staleness-fix.md` documents a July 9 resident snapshot roughly 2.5 hours stale and the source-versus-installed-wrapper gap. The early-heartbeat and ensure-timer fixes are visible in the current tree; a current remote artifact is needed to prove deployment and sustained freshness.

### Limits and unknowns

No current production `/workspace/watchdog-report.json`, six-hour report, repair-data directory, or meta-run directory is present in this checkout. The historical cloud-audit artifact referenced by initiative material (`/workspace/audit-reports/20260704T110403Z-audit.json`) is also absent. Consequently:

- I cannot establish the flags active on the current Hetzner agentbox, the installed wrapper hashes, whether its timers are enabled, or whether recent repairs succeeded in production.
- I cannot distinguish a missing local artifact from an artifact retained only on the remote agentbox.
- The repository is detached and dirty, with concurrent local work in relevant wrappers. Findings describe the examined working tree; deployment equivalence is unknown.
- The custody-control-plane log ends before an evidenced completed rollout, so the North Star is treated as intended direction, not deployed truth.

These are evidence gaps, not grounds to infer healthy behavior.

## End-to-end system map

```text
Workflow / supervisor / human-gate failure
        |
        | write repair request (intended immediate path)
        v
Central repair queue ---- systemd .path ----+
        ^                                  |
        |                                  v
Hourly watchdog sweep ---> target resolver/classifier ---> blocker claim/lock
        |                                  |
        | heartbeat + status snapshot      | dispatch
        |                                  v
        |                          L1 arnold-repair-loop
        |                          - deterministic repairs
        |                          - source/dev-agent fixes
        |                          - install/relaunch
        |                          - bounded retries
        |                                  |
        |                    success?       | L1 itself defective/recurrent?
        |                       |           v
        |                       |     L2 meta-repair-loop
        |                       |     - diagnose/fix L1
        |                       |     - install repaired wrapper
        |                       |     - retrigger L1
        |                       +-----------+
        |                                   |
        |                          repair data + incident journal
        |                                   |
        +-------------------------- status / report projections
                                            |
Six-hour systemd timer ---------------------+
        |
        v
L3 progress auditor
- discover active/recent sessions
- gather plan/chain/events/repair/meta/watchdog/prior-audit evidence
- reconcile incident, recurrence, CI, and engine-tree state
- report findings
- optionally dispatch a bounded Codex/DeepSeek repair and commit/push
        |
        v
next watchdog/L3 observation should independently verify or reopen
```

The intended authority chain in `custody-control-plane/NORTHSTAR.md` is narrower than the implemented map:

```text
Evidence producers -> coherent ObservationEnvelope -> resolve_run_state
                                                    -> dispatch policy
Transition writers <- authorized action             -> event journal
Independent verifier <- post-action observation     -> verified/reopened
Derived projections and reports <- journal + observations (never authority)
```

Today, several arrows bypass that center: queues have different roots, status and dispatch paths do not consume identical snapshots, repair code directly edits lifecycle state, and report generation can contradict actions already taken.

## Intended design versus observed behavior

| Concern | Intended design | Observed in implementation/artifacts | Consequence |
|---|---|---|---|
| Detection latency | Lifecycle hooks dispatch immediately; watchdog is a one-hour durable fallback. | `_enqueue_lifecycle_failure_request` passes a plan directory to `repair_queue_dir`, producing `.megaplan/plans/repair-queue`; systemd/watchdog consume `/workspace/.megaplan/repair-queue`. `arnold-supervise` exits at its same-error threshold before the later `other_count` queue branch. | Common failures can miss the immediate queue and wait for inference by a later sweep. |
| State authority | One pure resolver owns current run state; projections are not authoritative. | `run_state.resolve_run_state` classifies a mapping assembled elsewhere. `current_target.resolve_current_target`, status snapshot, watchdog, trigger, and chain guards still have different assembly/classification paths. There is no snapshot token or read-coherence transaction. | Different consumers can correctly classify different moments/sources and disagree. |
| Mutation authority | Evidence producers observe, transition writers mutate, evaluators verify. | L1 functions such as `recover_blocked_after_dev_fix_if_possible` and `repair_clear_stale_state_if_needed` directly rewrite plan/chain state under a repair lock. One write path uses plain `Path.write_text`. | Repairs can manufacture a lifecycle transition without the normal writer lock/event semantics. |
| Recovery definition | Current custody design: liveness is not success; only verified terminal success closes custody. | L1 contract excludes liveness, but `meta_repair.verify_retrigger_success` accepts `LIVE_WITH_FRESH_ACTIVITY`; the incident bridge records `verified_recovered`. | A restarted but still-broken process can close the feedback loop. |
| Six-hour role | Deterministic gather/reconcile, audit the repair system, bounded or report-only action according to explicit policy. Current M4 says L3 is read-only. | The prompt both forbids modifying audited run state and later permits updating running workspace state. The wrapper can patch/commit/push, while the final report always says report-only. | Authority is ambiguous and reported mode is untrustworthy. |
| Feature safety | Shadow observation, then explicit enforcement/autonomy rollout. | Resolver observation defaults on, enforcement/autonomy off; repair trigger, meta repair, auditor autofix, meta commit, and audit commit default on. `autonomy_enabled()` is not a global gate. | Operators can believe autonomy is disabled while mutation paths remain active. |
| Six-hour metrics | Exact 14-stage, report-only measurements; missing data is unknown rather than zero. | The wrapper loads full event history, not an exact six-hour cutoff. Greedy phase pairing and repeated global unknown counts distort stages; several missing inputs yield green findings. | Reports can reward absence of evidence and cannot support trend/SLO claims. |
| Provenance | Durable causal chain from detection through fix, install, retrigger, and verification. | Incident emission is best-effort and silently dropped on error; watchdog bridge events require repair data/incident ID that often does not exist at first detection. Local journal has no watchdog detection/dispatch events. | The most important causal start of an incident is missing. |
| Aggregation | Journal is source; projections are fresh, digest-bound derivatives. | Local journal has 345 events while projections cover 338 and a different digest; indexes are older and omit the custody incident. | Consumers can read stale derived truth with no hard freshness failure. |

## Detailed findings

### 1. Detection and queueing do not reliably join the immediate repair path

`auto.py:_enqueue_lifecycle_failure_request` calls the queue API with `marker_dir=plan_dir`. `repair_requests.repair_queue_dir(marker_dir)` defines the queue as `marker_dir.parent / "repair-queue"`; for a normal plan this is `.megaplan/plans/repair-queue`. The resident path unit `cloud/systemd/megaplan-repair-trigger.path` watches `/workspace/.megaplan/repair-queue/requests`, and the watchdog derives that same central location from cloud-session markers. No consumer of the plan-level queue was found.

The supervisor has a second gap. In `wrappers/arnold-supervise`, `STREAK_MAX=5` exits on repeated identical failures before the later branch that queues a request after `OTHER_MAX` diverse errors. Historical logs under `.megaplan/watchdog-run-logs/` contain repeated five-iteration same-failure patterns, making this more than a theoretical ordering issue.

The hourly watchdog can still infer a stuck run, but that is recovery by a slower safety net, not the intended immediate path. Queue latency metrics will also look deceptively good if missed requests never enter the denominator.

### 2. L3 loses canonical current-target evidence through an interface mismatch

`wrappers/arnold-progress-auditor:_resolve_current_target_evidence` calls:

```python
resolve_current_target(session, marker_dir=..., repo_root=..., base_branch="main")
```

The actual `current_target.resolve_current_target` signature accepts `session`, `marker_dir`, optional `repair_data_dir`, and liveness callbacks; it has no `repo_root` or `base_branch`. The wrapper catches the resulting exception and returns fallback evidence. This turns an integration defect into an apparently successful audit with low-confidence/unknown targeting.

`tests/cloud/test_progress_auditor.py` writes a stub `def resolve_current_target(session, **kwargs)`, so its contract test accepts the bad call. This is a classic false-green seam: wrapper tests validate a hand-built substitute whose interface is broader than production.

### 3. L3 action reporting is factually wrong

The progress-auditor wrapper calculates `AUDIT_AUTOFIX_ENABLED_FLAG` and can invoke `dispatch_one`, whose prompt authorizes a danger-full-access agent, source changes, commits, and pushes. Later, the report assembler unconditionally emits:

```json
{
  "mode": "report_only",
  "autofix_enabled": false,
  "repair_dispatched": false,
  "model_dispatched": false
}
```

This is not just uncovered behavior: `TestStageMetrics.test_dispatch_summary_block_present` and `test_dispatch_summary_report_only_guard` explicitly require the hard-coded values. The command's exit status is also discarded with `|| true`; the report has no authoritative dispatch receipt, return code, duration, token/cost data, actual subagent/model identity, diff, or commit reference. Configuration alone is used to populate some model metadata, which does not prove the model ran.

This violates the core evidence rule that a report must describe actions that actually occurred. It also prevents an auditor from determining whether a later change was autonomous, operator-authored, or merely proposed.

### 4. Feature flags do not define a coherent authority boundary

`cloud/feature_flags.py` defaults resolver observation on and resolver enforcement/autonomy off, but repair-trigger, meta-repair, auditor-autofix, meta-commit, and audit-commit flags default on. The top-level `autonomy_enabled()` helper is not used as a master guard outside tests. Resolver enforcement currently gates only a narrow watchdog suppression path; other dispatch/mutation paths have their own decisions.

The operationally dangerous state is therefore possible: `autonomy_enabled == false` while an L3 agent patches and pushes. A safety control that does not dominate every mutating path is a label, not an authority boundary.

### 5. Liveness and success have contradictory meanings

`repair_contract.SUCCESS_OUTCOMES` contains `complete`, `progressed`, and `true_human_blocker`; it deliberately excludes `live_with_fresh_activity` and `partial_liveness`. L1's `verify_started_and_holding` observes session health twice over roughly 30 seconds, then writes `partial_liveness`. That is a reasonable provisional handoff signal, although wrapper log text sometimes calls it “verified recovery.”

`true_human_blocker` is itself an overloaded “success”: it can mean diagnosis and escalation worked, but it does not mean the run recovered. It should transition custody to `awaiting_human` with an owner/deadline, not enter the same success set as `complete` or `progressed`.

L2 reverses the contract. `meta_repair.verify_retrigger_success` accepts `LIVE_WITH_FRESH_ACTIVITY` or authoritative `COMPLETE`; `_META_REPAIR_ACCEPTED_SUCCESS_OUTCOMES` includes liveness. The meta wrapper then appends `verified_recovered`, whose bridge documentation says the fix chain completed and the outcome recovered. `tests/cloud/test_meta_repair.py:test_live_with_fresh_activity_is_accepted_success` codifies the contradiction.

Local evidence shows the effect: all five `verified_recovered` journal records have summaries containing `live_with_fresh_activity`. None proves the triggering blocker disappeared, its phase completed, or a delayed observation remained healthy.

The vocabulary is also not closed. L1 writes outcomes including `deterministic_failure` and `recurring_retry_pending`, neither present in `repair_contract.ALL_OUTCOMES`. `validate_repair_data` accepts arbitrary outcome strings, and `is_terminal_outcome` treats every value other than `repairing` as terminal. Schema drift can therefore silently change control flow.

### 6. Canonical state resolution is not yet canonical or read-coherent

The new `run_state.resolve_run_state` is a valuable pure classifier with typed states and conservative conflict handling, but it classifies caller-provided evidence; it does not capture a coherent read of the marker, chain state, plan state, event tail, process state, repair data, and remote claims. `current_target.resolve_current_target` reads several of these sources and records fingerprints/mtimes, but there is no `captured_at`, version-before/version-after check, or retry on concurrent change.

Watchdog and repair-trigger invoke the canonical classifier in some paths. Status snapshot still has substantial bespoke `_classify_session` logic, and chain guards do not uniformly consume the same resolver result. `repair_contract.classify_repair_dispatch` prefers canonical input when supplied but retains legacy classification; the trigger supplies canonical state only under a narrower authoritative-source condition than watchdog. Resolver-observe/enforce flag meanings are thus consumer-dependent.

L1 further bypasses the intended boundary. `recover_blocked_after_dev_fix_if_possible` can set a plan to `finalized`, create a rerun cursor, clear `latest_failure`, and edit chain state directly. `repair_clear_stale_state_if_needed` can remove history, move phase results, and rewrite chain/plan state. These happen under a repair lock, not necessarily the lifecycle state-writer lock, and not through a single transition event API. A repair can therefore erase the evidence that an independent evaluator should use.

### 7. Deduplication suppresses legitimate future occurrences

Repair request IDs are deterministic over session, signature, and hint hash. The request file is write-once; once its decision becomes `dispatched`, the trigger excludes it. If the same blocker and hint recur later in the same session, enqueueing generates the same terminal ID and is coalesced forever. There is no occurrence epoch, cleared-at boundary, or post-verification reopen rule.

Meta-repair recursion protection similarly persists a session-lifetime record that allows at most one meta-repair. That is useful for preventing runaway recursion, but it also suppresses a distinct later L1 defect in a long-lived session. The recursion-guard dispatch path does not consistently create a durable `needs_human` record despite policy material describing that escalation.

Deduplication should collapse duplicate observations of one occurrence, not merge all future occurrences of the same signature.

### 8. Six-hour metrics are not reliably six-hour metrics

`arnold-progress-auditor` reads the entire event file. `_build_stage_metrics` counts lifetime events, attempts, and repetitions while the artifact is described as a six-hour report. Phase durations use greedy event pairing and only completed intervals; long-running censored phases disappear from duration distributions. A global unknown-phase count is copied into each stage, inflating stage-level unknowns. Conversely, a known active phase with no events can produce zeros that look measured rather than missing.

The pure `six_hour_auditor.audit_projection_input` also contains unsafe absence semantics. A probe with empty brief, evidence, and snapshot returned ten `OK` findings, including progress, watchdog, repair, install, live-process, current-target, evidence, and recurrence checks. `_is_stale(None)` is false, and several finding builders map missing records to OK. If callers omit `now`, the API can derive effective time from an incident's own latest timestamp, allowing old data to appear fresh relative to itself. The wrapper currently supplies real current time, but the public contract is unsafe.

Missing evidence must be `UNKNOWN`/`UNOBSERVED`, never green. Every rate needs an explicit numerator, denominator, window, source set, and missing count.

### 9. Local incident data is neither production-clean nor fresh

The tracked journal `.megaplan/incident-ledger/events.jsonl` contains 345 well-formed sequential records. That is structurally useful, but 337 records (97.7%) are demo/test/pytest-shaped by session name or `/tmp`/`/private/var` paths. Actor counts are 185 immediate, 153 meta, five repair-system, and two auditor; there are zero watchdog detection/dispatch records. Seven problem projections remain open; one is marked recurred after fix; no fix commits are recorded.

The newest embedded event timestamp is approximately 63.5 hours older than this audit. `incidents.json` and `problems.json` cover only 338 events and carry a source digest that no longer matches the 345-event journal. The summaries index is older still and omits the custody incident. These projections expose source metadata but readers do not hard-fail or rebuild on lag.

Pollution is facilitated by the incident bridge's fallback: if a payload lacks a workspace root, it can use the current working directory, which in tests is the repository. Production and test events do not have mandatory environment namespaces. Bridge writes are best-effort and broad exceptions are swallowed, so missing causality has no dead-letter counter. Watchdog incident events require an existing repair-data/incident ID; first detection occurs before L1 normally initializes those fields, explaining the absent initial detection edge.

### 10. Watchdog reports lack the contract needed for trustworthy aggregation

`arnold-watchdog:emit_report` writes its report directly rather than atomically and does not provide a schema version, report/tick ID, collector version or source commit, runtime/host/container/boot identity, observation window, payload hash, or source fingerprints. `sessions_seen` is set to `len(items)`, even though the item list can contain multiple actions for a session and non-session sync items. It is therefore not a unique-session count and need not match marker count, contradicting operator documentation.

Early heartbeat/snapshot emission and the one-minute `ensure-megaplan-watchdog` timer substantially improve liveness observability. But a fresh report proves the supervisor ticked, not that it covered all markers or read a coherent target set. Coverage and freshness must be separate dimensions.

### 11. L3 action scope is prompt-enforced and role design is stale

The L3 dispatcher can run Codex with broad filesystem authority and asks it to use an external subagent. Allowed paths, commit/push behavior, and prohibitions are prose in the prompt rather than mechanically enforced patch/path policies. The prompt first says never modify audited run/plan state, then a stale-state section says it may update running workspace state. Older tiered-repair material permits bounded fixes; the current custody M4 brief says L3 should be read-only.

This unresolved role boundary should be settled before enabling L3 mutation. A periodic evaluator that can alter the evidence it evaluates is especially vulnerable to self-confirming closure.

### 12. Deployment truth and regression risk are weakly evidenced

`docs/arnold/watchdog-snapshot-staleness-fix.md` records a real stale-resident-snapshot incident and a manual source-versus-installed-wrapper synchronization concern. Local current production artifacts are absent. The checkout is dirty and detached. Since July 1, the core watchdog/repair/auditor files have seen roughly 187 distinct commits (with overlapping per-file counts), indicating very high change velocity around stateful shell programs.

The broad test suite is a strength, but current seams show the limitation of source-fragment and stub-driven testing. The adapter mismatch passes because the stub is too permissive; the false dispatch summary passes because the test asserts it. There is no hermetic system test that creates one failure, observes central enqueue, executes trigger/L1/L2/L3, verifies install identity, and proves blocker clearance without mutating authoritative state out of band.

## Current strengths worth preserving

1. **Layered recovery model.** Immediate, hourly, meta-repair, and six-hour paths address different failure horizons and provide defense in depth.
2. **Conservative typed classifier.** `run_state/model.py` and `resolver.py` provide a good basis for explicit `UNKNOWN`, conflict, blocker, active, and terminal states.
3. **Bounded repair behavior.** Locks, claim files, iteration budgets, recursion guards, and breaker paths reduce uncontrolled loops.
4. **Repair evidence primitives.** Atomic repair-data writes, attempt history, recurrence state, install/retrigger fields, and the append-only sequenced journal are useful building blocks.
5. **Human-blocker modeling.** A true human gate is distinguished from mechanical failure and can be surfaced rather than endlessly retried.
6. **L1 success tightening.** The current repair contract correctly excludes partial liveness from its declared success set, even though L2 has not adopted the same rule.
7. **L3 evidence breadth.** The auditor gathers plan/chain/events, repair/meta artifacts, prior reports, incident projections, GitHub/CI, and engine-tree evidence, with recursion awareness.
8. **Resident observability.** Early heartbeat and status snapshots plus the watchdog ensure timer address silent tmux death and long stale-report windows.
9. **Extensive focused tests.** The suite is fast and covers many policy edge cases; it can support a controlled migration once integration seams use real contracts.
10. **Design convergence.** The custody and workflow-boundary North Stars explicitly recognize liveness-versus-success, projection authority, coherent reads, and evaluator/writer separation.

## Ranked failure modes

Rank uses impact first, then likelihood/detectability. `P0` can produce silent false completion or unauthorized/unreported mutation; `P1` materially delays or misdirects repair; `P2` degrades measurement or maintainability.

| Rank | Priority | Failure mode | Impact | Evidence/likelihood | Detectability today |
|---:|:---:|---|---|---|---|
| 1 | P0 | L3 current-target signature mismatch silently falls back | Auditor diagnoses/escalates against incomplete target evidence | Deterministic on current signatures | Low: exception is swallowed; tests mask it |
| 2 | P0 | L3 report claims report-only after possible autonomous dispatch | Audit provenance is false; changes cannot be attributed | Deterministic whenever autofix dispatch occurs | Very low: tests assert false summary |
| 3 | P0 | Liveness accepted as `verified_recovered` | Broken runs can be closed after mere process survival | Contract/test plus 5/5 local recovery records | Low without delayed blocker checks |
| 4 | P0 | Master autonomy off does not dominate mutating flags | Operator intent can be bypassed | Direct flag/control-flow inspection | Low unless action receipts exist |
| 5 | P1 | Immediate requests enter an unconsumed plan-level queue | Detection-to-repair latency expands toward watchdog interval | Deterministic path derivation | Low: missing requests absent from metrics |
| 6 | P1 | Repeated-same-error supervisor exits before queueing | Common crash loops miss immediate escalation | Control-flow inspection; historical repeated loops | Medium through later watchdog |
| 7 | P1 | Multiple non-coherent classifiers plus direct L1 state mutation | Conflicting state, false transition, lost failure evidence | Multiple live code paths | Low during concurrent transitions |
| 8 | P1 | Session/signature-lifetime dedupe suppresses recurrence | A real later incident is never dispatched | Deterministic ID/write-once behavior | Low: appears coalesced |
| 9 | P1 | Missing evidence becomes green and lifetime data becomes “six-hour” metrics | Self-confirming reports and invalid trend data | Reproducible pure-function probe and code inspection | Low to casual report readers |
| 10 | P1 | Incident journal is test-polluted; projections lag; emission can drop silently | Aggregates and causal incident histories are untrustworthy | 97.7% local pollution; 7-event lag | Medium if source metadata is manually checked |
| 11 | P2 | Watchdog report lacks schema/provenance/atomicity and misdefines sessions | Coverage/freshness cannot be audited reliably | Direct report builder inspection | Medium |
| 12 | P2 | Large shell monoliths and prompt-only L3 scope | Interface drift and unsafe changes recur | File size/change velocity and current defects | Medium after failures, low before |

## Ranked recommendation backlog

### Quick wins and containment

| Rank | Recommendation | Impact | Risk | Effort | Dependencies | Acceptance test |
|---:|---|:---:|:---:|:---:|---|---|
| 1 | **Make every action report factual.** Build `dispatch_summary` from a durable dispatch receipt containing actual flag evaluation, command start/end, return code, actor/model identity, changed paths, commit/push result, and error. Remove unconditional `report_only`. | Very high | Low | S | None | With autofix off, no repair/model subprocess runs and report says off. With a fake successful/failed dispatcher, report matches the receipt byte-for-byte; it can never say report-only after start. |
| 2 | **Introduce one effective mutation gate, default off.** `AUTONOMY_ENABLED && path_specific_flag` must guard repair-trigger mutation, L2 source/commit/install, and L3 patch/commit/push. Log evaluated inputs and reason. Observation remains available. | Very high | Medium | S-M | Action receipts | Exhaustive flag-matrix test proves master off prevents every write/agent/commit/push path while reports still run. |
| 3 | **Fix the L3 `resolve_current_target` call and use the real module in wrapper integration tests.** Prefer a typed adapter rather than adding ignored kwargs. | Very high | Low | S | None | Test imports production `current_target.py`; a realistic fixture produces an authoritative target. Signature drift fails loudly, not as `UNKNOWN`. |
| 4 | **Unify the repair queue root.** Queue API should require a workspace root/explicit queue root; reject plan directories. Move supervisor threshold enqueue before every terminal exit. Add a scanner for stranded legacy requests during migration. | High | Low | S | None | Lifecycle and human-gate fixtures write exactly the path unit's directory; a repeated identical failure queues once before exit; trigger consumes it within the path-unit test. |
| 5 | **Ban liveness-only verified recovery.** Rename it `provisional_liveness`; only original-blocker clearance or authoritative terminal completion may emit `verified_recovered`. Remove unknown outcomes or add them to a closed enum. | Very high | Medium | S-M | Verification contract can follow | Meta-repair test with healthy tmux + unchanged blocker remains open. The same fixture after blocker-clear evidence closes. Unknown outcome fails validation. |
| 6 | **Stop missing evidence from becoming OK.** Require an explicit observation and real current time for every freshness-sensitive finding. Use `UNKNOWN` with reason/source. | High | Low | S | None | Empty input produces zero green findings; omitted `now` raises validation error; each finding exposes evidence IDs or missing-source codes. |
| 7 | **Quarantine non-production incident data.** Add mandatory environment namespace and prohibit cwd fallback. Move/ignore fixture journals; rebuild current projections from the intended production journal. | High | Low-Medium | S-M | Contract versioning | Test events can never enter `environment=production`; projection source count/digest exactly match journal; stale projection is rejected. |
| 8 | **Make watchdog report writes atomic and fields honest.** Add schema/report ID, unique session/marker/action counts, generated time/window, collector source commit, runtime identity, source coverage, errors, and content hash. | Medium | Low | S | Observation schema | Duplicate items do not inflate `unique_sessions_seen`; interrupted write preserves prior valid report; schema validation runs in CI. |

### Architectural changes

| Rank | Recommendation | Impact | Risk | Effort | Dependencies | Acceptance test |
|---:|---|:---:|:---:|:---:|---|---|
| 9 | **Create a read-coherent observation service.** Capture all state sources with read-start/read-end versions, retry on mutation, and return one versioned `ObservationEnvelope`. Make watchdog, status, dispatch, chain guards, and L3 consume it. | Very high | Medium-High | L | Schema and shadow telemetry | A fault-injection writer mutates every source mid-read; resolver returns coherent snapshot or explicit `INCOHERENT`, never a mixed terminal/active result. Shadow drift is below an agreed threshold before enforcement. |
| 10 | **Make lifecycle TransitionWriter the only state mutator.** L1 proposes a transition with evidence; it does not directly edit plan/chain JSON. Emit immutable transition and repair events under the correct lock. | Very high | High | L | Coherent resolver, event contract | Filesystem audit/test denies direct state writes from repair actors. Every finalized/reopened transition has one event, actor, precondition observation, and idempotency key. |
| 11 | **Separate attempt, handoff, verification, and closure.** Add independent post-action observations at 5m/1h/6h; original repair actor cannot self-verify. Reopen automatically on blocker recurrence. | Very high | Medium | M-L | Observation and event contracts | Synthetic “process alive, blocker unchanged” never closes. A real fix stays clear at all checkpoints. Regression emits `reopened` linked to the prior attempt. |
| 12 | **Use occurrence-scoped idempotency.** Define `blocker_occurrence_id` from detection epoch/transition, while signature remains a grouping key. Dedupe only within an open occurrence; reset meta budget after verified closure or a new occurrence. | High | Medium | M | Event/verification model | Duplicate detections dispatch once; identical blocker after verified closure creates a new request and fresh meta budget; recurring metrics group both by signature. |
| 13 | **Rebuild L3 metrics as exact-window typed aggregations.** Filter by event time with skew policy, track censored phases, use explicit denominators/unknowns, and reconcile dispatch receipts. | High | Low-Medium | M | Clean event and observation contracts | Golden timeline tests cover boundary, late, duplicated, missing, censored, and out-of-order events. Six-hour totals equal only included event IDs. |
| 14 | **Make provenance durable and failure-visible.** Detection creates incident/occurrence ID before dispatch. Journal append failure goes to a dead-letter spool and increments an alerting counter; projections rebuild by seq/digest and reject lag. | High | Medium | M | Event schema | Simulated journal failure preserves action intent in dead letter; replay is idempotent; every verification traverses detection → attempt → install → retrigger → observation. |
| 15 | **Mechanically sandbox L3 scope.** Resolve whether L3 is read-only. Recommended: L3 files findings/tickets; L1/L2 execute changes. If mutation remains, use disposable worktree, path allowlist, diff budget, tests, signed receipt, canary install, and rollback—not prompt prose. | High | Medium-High | M-L | Mutation gate and receipts | Forbidden path modification aborts before commit; failed canary rolls back; evaluator cannot modify its input artifacts; report identifies every authorized path. |
| 16 | **Extract policy/report logic from shell into typed Python modules.** Keep wrappers as thin process launchers; share production adapters in tests. | Medium-High | Medium | L | Stabilized contracts | Shell contains no state classification/report assembly. Contract/integration tests run identical code used by all four tiers and fail on signature mismatch. |

`S` is days, `M` about one sprint, and `L` multiple coordinated sprints. Estimates assume no remote deployment surprises.

## Proposed data contracts

Use versioned JSON Schema with `additionalProperties: false` at authority boundaries, explicit extension maps where needed, RFC 3339 UTC timestamps, closed enums, and content hashes over canonical JSON. Store schemas under a dedicated operational-contract directory and validate both producers and consumers.

### `ObservationEnvelope.v1`

Required fields:

- Identity: `observation_id`, `environment`, `workspace_id`, `session_id`, `run_id`, `target_id`, optional `blocker_occurrence_id`.
- Capture: `captured_at`, `read_started_at`, `read_completed_at`, `window_start`, `window_end`.
- Collector provenance: package/version, source commit, wrapper hash, host/container/boot IDs, deployment/install ID.
- Per source: source kind, path/URI, status (`observed|missing|unreadable|invalid`), content hash, mtime, sequence/version before and after, observed timestamp, age, and parse/schema result.
- Coherence: `coherent|incoherent|partial`, retry count, changed sources, and bounded clock-skew estimate.
- Resolver result: typed state, confidence, reasons, conflicts, authoritative source set, and resolver version/policy hash.

Invariant: a terminal or dispatchable state cannot be returned from an incoherent envelope without an explicit fail-closed override recorded as an event.

### `DetectionEvent.v1`

- `detection_id`, `incident_id`, `blocker_occurrence_id`, causal parents, detector identity/version.
- Signal code, severity, confidence, signature, first/last seen, observation ID.
- Positive evidence, negative controls checked, missing sources, deadline/expected-next-transition.
- Dedupe window and idempotency key.

Invariant: detection must be durably recorded before or atomically with dispatch intent.

### `RepairAttempt.v1`

- Attempt/request/incident/occurrence IDs and parent detection.
- Actor tier (`L1|L2|operator`), model/tool identities, prompt/policy hash, authority scope, budget.
- Precondition observation and exact blocker-before fingerprint.
- Structured actions, changed paths/diff hash, tests and results, commit, install/deployment identity, retrigger receipt.
- Exit classification from a closed enum: `no_action`, `attempt_failed`, `provisional_handoff`, `awaiting_human`, `awaiting_verification`, `verified_success`, `superseded`.
- Cost/duration/tokens and captured stdout/stderr artifact hashes with redaction status.

Invariant: `provisional_handoff` is never terminal success.

### `VerificationEvent.v1`

- Verification ID, attempt and occurrence IDs, verifier identity/version distinct from repair author, policy hash.
- Checkpoint (`immediate|5m|1h|6h|24h|7d`), post-observation ID.
- Original blocker status (`present|cleared|unknown`), expected transition status, negative controls, new blockers.
- Verdict (`provisional|verified|regressed|unknown`) and evidence IDs.

Invariant: `verified` requires original blocker cleared and no contradictory authoritative evidence. Liveness alone can only produce `provisional`.

### `AuditReport.v2`

- Report ID, exact window, generation time, previous report ID/hash, auditor version/policy/source commit/runtime identity.
- Source coverage by required entity, freshness and coherence, included event IDs or range/digest.
- Finding IDs with severity, confidence, evidence, missing evidence, owner, due/expected-next, and prior-finding link.
- Exact metrics with numerator, denominator, unknown count, filters, unit, and source IDs.
- Actual effective flags and complete dispatch receipts; `mode` derived from actions, never a constant.
- Projection source seq/digest and payload content hash.

### `IncidentEvent.v2`

- Mandatory environment namespace and runtime identity; no cwd-derived production root.
- Closed event type and actor enums, causal parents, observation/attempt/verification references, occurrence ID, idempotency key.
- Journal sequence assigned by the writer, schema validation result, and redaction/provenance metadata.

Projection invariant: `last_seq`, event count, and source digest must match the journal at read time, or the projection is `STALE` and cannot support a green finding.

## Metrics that answer whether the loop works

Every metric should carry its time window, numerator, denominator, unknown count, source coverage, environment, and policy version. Report distributions, not only averages.

### Detection and dispatch

- Time to detect: failure timestamp → first durable detection, p50/p95/p99.
- Queue latency: detection → request write → trigger claim → L1 start.
- Immediate-detection coverage: incidents first found by lifecycle/supervisor ÷ all incidents later found by watchdog. Include “unknown origin.”
- Orphan queue depth/age by queue root; stranded legacy requests; dispatch without detection.
- Duplicate rate within an occurrence and recurrence-suppression rate across occurrences.
- Detection precision: actionable mechanical failures, true human blockers, and false positives by signal.

### Diagnosis and repair

- Diagnosis coverage: attempts with blocker fingerprint, root-cause code, negative control, and precondition observation.
- Attempt success funnel: detected → claimed → actioned → installed → retriggered → provisional → verified at 5m/1h/6h.
- MTTR p50/p95 from first failure to verified clearance, not to process start.
- No-op repair rate, retry count, breaker rate, and human escalation rate/precision.
- Cost, tokens, wall time, changed lines, tests, and attempts per independently verified recovery.
- Install/retrigger completion and rollback rates; source hash versus installed wrapper hash.

### Effectiveness and false completion

- Original-blocker clearance rate and unknown-clearance rate.
- Liveness-only claim rate: closure/provisional records based only on process health; target is zero closures.
- Durable recovery at 5m, 1h, 6h, 24h, and 7d.
- Recurrence rate by signature/root cause and time-to-recurrence.
- False-completion rate: closure later contradicted by authoritative evidence, divided by closures with sufficient follow-up.
- Self-verification rate: verifier shares actor/process/observation with repair author; target zero for terminal closure.
- Reopen latency after regression.

### Authority and data quality

- Canonical-versus-legacy drift rate and confusion matrix by state.
- Incoherent/partial observation rate, read retries, source age, and `UNKNOWN` rate by missing source.
- Schema validation failure rate; unknown-enum rate; provenance completeness.
- Journal append/dead-letter/replay counts; projection lag in events and seconds; digest mismatch duration.
- Test/staging/production cross-namespace contamination count; target zero.
- Causal completeness: percentage of verified outcomes with detection → attempt → install → retrigger → independent verification.

### Watchdog and L3

- Watchdog tick duration p95/p99, tick gaps, restarts, report age, and write failures.
- Unique markers discovered, unique sessions classified, actions produced, exclusions with reason, and coverage percentage.
- L3 required-source coverage and fresh-source coverage per session.
- False-green count: green finding later shown to have absent/stale evidence.
- Dispatch/report reconciliation: started actions represented by receipts; target 100%.
- Finding actionability: findings with owner, next action, and deadline; recurrence and resolution latency.
- L3 agent/subagent invocation, duration, result, cost, change scope, canary and rollback rates.

## Pragmatic phased rollout

### Phase 0 — Contain false claims and hidden action (48–72 hours)

Ship only ranks 1–7 from the quick-win backlog:

1. Truthful dispatch receipts/report mode.
2. One master default-off mutation gate.
3. Real-signature L3 adapter fix.
4. Central queue and supervisor ordering fix.
5. Provisional liveness semantics and closed outcome enum.
6. Missing-evidence-as-unknown.
7. Production/test journal separation.

Acceptance gate:

- End-to-end fixture produces one immediate central request and one claim.
- Master gate off results in zero state/source/commit/push mutations across L1/L2/L3.
- L3 real-module integration resolves a target; injected signature mismatch fails the run visibly.
- A live-but-still-blocked fixture remains open through L1 and L2.
- Empty/stale evidence produces no green findings.
- Every started subprocess has a report receipt; no receipt can claim report-only.

Rollback: keep observation/report generation on; disable all autonomous mutation through the one master gate.

### Phase 1 — Establish trustworthy evidence and authority (1–2 sprints)

- Introduce schemas and environment namespaces.
- Build `ObservationEnvelope` and shadow it beside existing resolver/classifiers.
- Add journal dead letter and automatic seq/digest projection rebuild.
- Add occurrence IDs and occurrence-scoped idempotency.
- Route state changes through TransitionWriter; initially warn/record direct-write violations.

Acceptance gate:

- Fault-injection reads never produce mixed snapshots without `INCOHERENT`.
- A seven-day shadow comparison reports canonical/legacy drift with explained denominators and no unclassified divergence above the agreed threshold.
- Production projections remain at zero event lag or explicitly fail stale.
- Test/staging events cannot appear in production aggregates.
- Every repair transition has an immutable precondition observation and event.

Rollback: continue producing envelopes/events without enforcing their decisions; legacy control remains available but all divergences are recorded.

### Phase 2 — Prove repair effectiveness (1–2 sprints)

- Split attempt, provisional handoff, independent verification, closure, and reopen.
- Add delayed checkpoints and blocker-specific negative controls.
- Record install identity, retrigger receipt, test evidence, cost, and diff scope.
- Use canary installs for wrapper changes and automated rollback.

Acceptance gate:

- Fault suite covers process-alive/blocker-present, stale terminal state, failed install, wrong installed hash, recurrence, and human blocker.
- Only blocker-cleared cases close; all regressions reopen and link to the original occurrence.
- No repair actor can write its own terminal verification.
- At least one controlled canary demonstrates install → retrigger → 5m/1h/6h verified recovery and one forced failure demonstrates rollback.

### Phase 3 — Rebuild the six-hour feedback product (1 sprint)

- Implement exact-window metrics and coverage/quality sections from typed events.
- Settle L3 as read-only evaluator (recommended); route its actionable findings into the normal repair/ticket authority.
- Add audit-the-auditor negative controls and external CI/engine evidence receipts.
- Replace stale docs and mark old contracts superseded at the relevant paragraphs, not only initiative front matter.

Acceptance gate:

- Golden timelines prove exact inclusion/exclusion at window boundaries, late/out-of-order handling, censored durations, and missing data.
- Recomputing a report from the same immutable inputs yields the same content hash.
- Every green finding has fresh evidence IDs and every unknown names the missing source.
- L3 cannot alter audited state or its input artifacts; findings dispatched elsewhere retain causal IDs.

### Phase 4 — Controlled enforcement and autonomy (progressive canary)

- Enable coherent resolver enforcement for one non-critical canary session, then 5%, 25%, and 100% after SLO gates.
- Separately canary L1 mutation; keep L2 source repair and any L3 mutation disabled until delayed verification data is credible.
- Review weekly false completion, recurrence, human-escalation precision, cost per verified recovery, and data-quality SLOs.

Promotion gate:

- Zero unexplained autonomous mutations and zero liveness-only closures.
- 100% action/receipt reconciliation.
- Projection lag and cross-environment contamination at zero.
- False-completion and 6h recurrence below agreed thresholds with sufficient follow-up coverage.
- Demonstrated kill switch and rollback in a game day.

## Specific test additions

1. **Queue topology system test:** lifecycle failure, human-gate failure, and repeated supervisor crash each write the same configured queue; path trigger claims exactly once.
2. **Real-adapter contract test:** wrapper subprocess imports production `current_target.resolve_current_target`, not a `**kwargs` stub.
3. **Action-truth matrix:** disabled, attempted, succeeded, failed, timed out, and partially changed dispatches produce exact receipts and modes.
4. **Liveness negative control:** tmux and PID healthy while failure marker/state unchanged; closure forbidden.
5. **Read-tearing test:** mutate chain/plan/events between reads and require retry or `INCOHERENT`.
6. **Transition authority test:** filesystem/monkeypatch guard fails any L1/L2 direct state write outside TransitionWriter.
7. **Occurrence test:** identical signature twice within one incident dedupes; identical signature after verified closure dispatches anew.
8. **Exact-window property tests:** generated timelines with clock skew, duplicates, out-of-order and missing events match a reference aggregator.
9. **Projection freshness test:** append event without rebuild; projection consumer rejects stale digest, then rebuild is deterministic.
10. **Namespace isolation test:** randomized test paths/payload omissions can never resolve to a production journal.
11. **Journal failure test:** disk/lock/schema failure produces alert and replayable dead letter rather than silent loss.
12. **Full custody fault matrix:** failure detected → L1 defective → L2 fixes L1 → install mismatch → corrected install → retrigger → delayed verification, with causal IDs checked at each edge.

## Documentation and ownership decisions required

Before implementation, owners should explicitly decide and record:

1. **Is L3 read-only?** The current custody M4 direction says yes; older docs and current wrapper allow mutations. This audit recommends read-only L3, with normal repair authority consuming its findings.
2. **What is the single source of runtime identity?** Repository HEAD, installed wrapper hash, package version, container image, and host boot all matter; reports need all of them.
3. **Who may close custody?** Recommended: only an independent verifier operating on a later coherent observation, never the repair actor or process-liveness probe.
4. **What is the production incident store and retention policy?** It must not be a cwd fallback or tracked fixture file.
5. **What SLOs justify autonomy promotion?** Thresholds need minimum follow-up coverage so low false-completion counts cannot be achieved by not observing outcomes.

## Bottom line

Arnold's repair architecture is promising but presently measures orchestration more reliably than recovery. The most dangerous defects are quiet: a canonical resolver that L3 cannot call, a report that can deny an action it performed, liveness relabeled as verified recovery, immediate requests written where no immediate consumer looks, and stale/test-polluted evidence that can still aggregate green.

Do not expand autonomous scope until Phase 0 makes control and reporting truthful. The decisive architectural move is then to make one coherent observation and one transition authority common to watchdog, L1, L2, L3, status, and chain guards. Success should mean that an independently observed original blocker stayed cleared—not that an agent ran, a commit existed, a tmux session lived, or the same component declared itself fixed.
