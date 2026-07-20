# L3 “repair the repairer” prompt: lessons from resident run `subagent-20260716-170615-ea341358`

**Research snapshot:** 2026-07-16 19:37:04 UTC (UTC+00:00)

**Disposition:** research and proposed adoption only; no prompt, runtime, service, schedule, deployment, or active-chain change is authorized or performed here.

**Canonical initiative:** `megaplan-maintenance`

## Executive verdict

The resident run is useful evidence for a stronger L3 contract, but not evidence that a long, permissive prompt is sufficient by itself. Its strongest reusable property was **goal-shaped custody**: it named the exact incident and sources, forced a TRACKED/FIXED/INTENT/CONTEXT walk, required the first broken fixer and its missed backstop to be repaired, prohibited guard weakening and hand-advancing state, prescribed exact recurrence regressions, and defined success as an ordinary retrigger plus externally observed progress by the original plan. The completed run then produced evidence consistent with that contract: a stable occurrence-accounting root cause, locally integrated fixes, matching installed wrapper hashes, an ordinary L2 → L1 retrigger, guarded recovery, and plan advancement from iteration 3 to 4.

The current L3 pathway already contains important safety foundations: deterministic gather before model judgment, bounded evidence pointers, a read-only reviewer, typed central escalation, missing-evidence fail-closed behavior, concurrency/cooldown/failure budgets, and `preserve_live`. The highest-value change is therefore **not** to paste the resident prompt into L3 or give the periodic reviewer mutation authority. It is to make the existing boundary internally consistent and mechanically closed:

1. make the read-only reviewer emit one structured custody diagnosis and repair request rather than contradictory “fix/return FIXED” prose;
2. carry the four axes, first-broken/missed-backstop identity, immutable evidence cursor, preservation decision, acceptance tests, and unknowns through the central handoff;
3. make the L3-specific deep-repair contract prove installed applicability, ordinary-path retrigger, blocker clearance, and original-plan progress before closure; and
4. count failure **occurrences**, not observations/polls, with deterministic fixtures for stale-success supersession and spinning.

This is a successful terminal resident run, not a terminal M6 chain. The managed run reached durable `completed` with return code 0 at 2026-07-16 19:35:48 UTC (UTC+00:00), wrote `result.md`, and delivered its verified summary. Its own terminal evidence says the broader M6 chain had recovered and was continuing, not completed. The manifest's top-level `completed_at` remains null even though `status_history` contains the terminal event; consumers should prefer the durable transition evidence and treat that field inconsistency as a schema-quality caveat.

## Canonical placement and prior-art search

Before writing, rough searches were run across initiative anchors, research, handoffs, notes, and tickets for `superfixer`, `L3`, `progress auditor`, `meta repair`, `repair the repairer`, and `custody`.

- `megaplan-maintenance` is the closest live canonical initiative. Its README expressly owns “watchdog supervision, safe repair custody, [and] the six-hour operational unblocker,” and its North Star defines independent verification, occurrence-scoped deduplication, and separation between observation and repair authority.
- `progress-auditor-stage-metrics` is narrower: deterministic stage accounting, explicitly not a redesign of repair custody.
- `superfixer-alive-but-failed-recovery` is a one-sprint operational effort for the `partial_liveness`/failure-receipt incident; its North Star explicitly declines the broader boundary architecture and does not own the L3 generation contract.
- `superfixer-repair-custody` and `tiered-repair-hardening` are marked `superseded_by: custody-control-plane`.
- `custody-control-plane` remains the authoritative architecture for coherent run/custody authority, but this document is maintenance-loop prompt research rather than another execution epic or custody model.
- The closest existing research is `megaplan-maintenance/research/codex-5-6-sol-autofix-six-hour-feedback-audit.md`; it provides the broad system audit. This document extends it with a concrete July 16 generation comparison rather than duplicating it.
- The canonical ticket-search command was attempted for every rough term but failed while parsing an unrelated malformed ticket frontmatter value. A direct full-text fallback over `.megaplan/tickets/*.md` found `.megaplan/tickets/execute-authority-rerun-loop-post-rebase-evidence-storm.md`. It concerns an execute-phase rebase/evidence-SHA loop and does not own the L3 prompt/handoff contract. No ticket matching “repair the repairer” exactly was found.

Accordingly, this document belongs in the existing `megaplan-maintenance/research/` index. No new initiative or ticket is warranted, and no file is written under `.megaplan/briefs`.

## Evidence and confidence

| Evidence | What it establishes | Limits / classification |
| --- | --- | --- |
| Target manifest: `.megaplan/plans/resident-subagents/subagent-20260716-170615-ea341358/manifest.json` | Exact model/profile (`gpt-5.6-sol`, high, D10), launch and terminal transitions, immutable request/custody provenance, return code 0, completion delivery. | **Evidence.** Top-level `completed_at` is null despite a terminal status-history event. |
| Exact task prompt: same run's `prompt.md`, SHA-256 `8e63294b7d18bad0b5d43b67c6ead0821d9c45ec56b4c96e3036e994fdb3966b` | The six sources, four axes, first-fixer/backstop method, exact regressions, guard constraints, isolated Git custody, ordinary retrigger, retroactive L3 proof, and strict terminal condition were explicit before execution. | **Evidence of direction, not causality of every discovery.** |
| Complete available transcript: same run's `run.log` (53,986,252 bytes at the snapshot) | End-to-end execution chronology, tool use, failed attempts, corrections, test/rebase/install/retrigger work, and final response; the log was searched across its full extent and inspected at phase boundaries and all cited events. | **Evidence with volume caveat.** It contains enormous diff output and 2,241,214 reported tokens; length is not a quality signal. |
| Terminal `result.md`, SHA-256 `9cd54bf41fcef4dfd67054a607da790db4e7bb28dded93d22f0d9b039fd18ccf` | Run-level root cause, changes, test claims, installed identities, retrigger IDs, recovery, and explicit no-push/no-deploy boundary. | **Evidence summary, corroborated below.** It does not prove M6 completion. |
| `git-custody-evidence.json` | Clean isolated implementation worktree, reviewed diff, tests, target-ref containment, local integration at `fd085c4ad8638e4bd19aeef37e6a17c17a297341`. | **Evidence.** Local integration is not remote publication or production deployment. |
| `.megaplan/superfixer-custody-20260716/runtime-retrigger-receipt.json` | Installed wrapper fingerprints, ordinary L2/L1 run IDs, guarded recovery, no direct state edit/duplicate runner, iteration 3 → 4, fresh `plan_v4.md`, live preserved worker. | **Strong external verification for incident recovery at 19:33:45Z.** Chain completion remains outside the claim. |
| `.megaplan/superfixer-custody-20260716/l3-retroactive-receipt.json` | Installed L3 SHA `bff6f09b…`; one failure at history index 8 was superseded by successes at 9/12/15 yet reported count was 3; deterministic retro detector passed. | **Evidence for the detector and regression, not a complete L3 production cycle.** |
| Six investigator briefs/results and `_report.json` under `.megaplan/superfixer-custody-20260716/` | Bounded parallel mapping of six sources, L1, L2, L3, recurrence code, and runtime/retrigger; six tasks reported `ok`. | **Leads, not authority.** Several results included unsafe or incorrect suggestions and were corrected by the synthesis owner. |
| Current installed L3 `/usr/local/bin/arnold-progress-auditor` and pinned source at `/workspace/arnold-runtime-resident-scheduling-1e76dbe/.../arnold-progress-auditor` | Installed/source SHA equality at `bff6f09b…`; actual prompt construction at lines 5747–5955. | **Evidence at snapshot.** The ordinary project checkout is dirty and is not used as installed-runtime truth. |
| `progress_auditor_escalation.py:1-9,57-68,900-1078` in the pinned runtime | L3 is deliberately gather/report; separate authority controls mutation; one-hour threshold, six-hour cooldown, deterministic/launch budgets, concurrency 1; six-source/four-axis fail-closed gate and preserve-live blocks. | **Evidence of current implementation.** |
| Current L2 wrapper `arnold-meta-repair-loop:916-950,973-1028` in the pinned runtime | L3 deep repair is appended to L2 only under `ARNOLD_L3_DEEP_REPAIR=1`; it carries the four axes, first-fixer/backstop, bounded investigators, durable goal, preserve-live, external recovery, and receipts. | **Evidence resolving terminology.** “L3 repairer” is an L3 reviewer/handoff plus an L3-specific contract executed by the L2 wrapper, not a single prompt. |
| L3 reports `20260716T135924Z`, `20260716T133516Z`, `20260716T062710Z`, `20260716T014643Z`, `20260715T193801Z` under `/workspace/audit-reports/` | Representative report-only detection, reviewer dispatch, no-new-launch/live preservation, and D9 repair escalation behavior. | **Evidence of recent generations, snapshot-dependent.** Reports are observations and receipts, not proof that a repair fixed the target. |

No follow-up was injected into the target managed run. Resident-facing status replies were sent outside the run, but no follow-up queue or prompt mutation for `subagent-20260716-170615-ea341358` was found. This matters: the successful direction was present in the original prompt, while the implementation refinements came from the model's live observations and iterative work rather than later user steering.

## What the resident prompt caused—and what it did not

### Explicitly caused by the prompt

- **Concrete target and custody:** exact session/plan/run IDs, historical hypotheses, required evidence sources, and one synthesis/delivery owner.
- **A diagnostic method:** all six evidence sources, then TRACKED/FIXED/INTENT/CONTEXT for each layer, then the first failed fixer and the layer above that missed it.
- **Action orientation:** fix the reusable repair mechanism, retrigger through the ordinary path, and prove the original plan moved.
- **Guard preservation:** no direct plan/chain state advance, no completion/safety guard weakening, no “green by hand.”
- **Specific recurrence tests:** later same-phase success supersedes older failure; repeated polling cannot recount one occurrence.
- **Terminal evidence:** installed fixed layer, ordinary retrigger, original-session advancement, and retroactive L3 coverage; PID, exit code, prose, and artifact existence alone are rejected.
- **Bounded code custody:** isolated worktree, diff review, focused tests, and explicit integration boundary.

### Contributing factors that cannot be attributed to prompt wording alone

- The run used `gpt-5.6-sol` with high reasoning, danger-full-access tools, live filesystem/process/tmux/Git context, and more than two hours of wall time.
- It used the `superfixer-debug` methodology plus six DeepSeek/Hermes investigator tasks with file/web/terminal tools.
- It encountered changing target revisions, installed-wrapper drift, live runner state, and multiple failed attempts. Discoveries such as the wrapper snapshot-cleanup sibling bug, external applicability propagation, and receipt-container correction were not prescribed in the original task.
- Model judgment mattered: investigator outputs included speculative diagnoses and unsafe ideas such as direct hot-environment/state handling; the synthesis thread rejected or refined them.
- Timing and luck mattered. The original chain and watchdog remained observable and recoverable long enough to verify progress.

Therefore the correct lesson is “encode the successful custody and proof obligations,” not “copy the entire prompt, model, permissions, or fan-out recipe.”

## Prompt anatomy comparison

| Dimension | Successful resident pathway | Current L3 pathway | Recommendation |
| --- | --- | --- | --- |
| Role | One mutation-authorized synthesis owner with an end-to-end goal. | Read-only periodic reviewer; a separate policy/controller may dispatch a mutation-authorized D9 worker. | Preserve the split. Make the handoff complete enough that the D9 owner receives the resident run's goal contract. |
| Target | Exact session, plan, prior run IDs, source revision, branch, and operational objective. | Bounded finding pointer plus plan/workspace/reasons; exact identities exist in the gate but reviewer prose is partly generic. | Require immutable target tuple, source/runtime digests, baseline cursor, and evidence age in every review and repair request. |
| Evidence | Six named sources plus live source/runtime reconciliation and direct artifact inspection. | Primary ledger/projections; live/process/sidecars only corroborate; six-source completeness is checked in policy. | Keep this. Add per-source `present/fresh/coherent/missing_reason` and prohibit the model from filling gaps. |
| Diagnosis | Four axes for every layer; first broken fixer and supervising miss. | Policy computes a custody walk; prompt asks broad “pipeline friction map” then multiple overlapping questions. | Put the typed four-axis walk first and make the friction map optional after the actionable chain. |
| Authority | Broad but scoped code/test/install/retrigger authority; no remote push/deploy. | Reviewer is read-only, but lines 5851–5865 still say “Fix…” and “return FIXED”/`META_REPAIR_FAILURE`, which are not allowed reviewer verdicts; lines 5877–5880 and 5930–5932 correctly prohibit mutation. | P0: remove the contradiction. Reviewer returns only typed observations/requests; deep-repair worker gets mutation language after authority validation. |
| Bounded autonomy | One owner; bounded investigators; iterative until proof or genuine gate. | Reviewer and repair concurrency are limited to one; cooldown and two-attempt deterministic/launch budgets exist; deep repair permits at most three read-only investigators. | Keep hard budgets; add per-stage stop reasons and total evidence/tool/time budgets to the repair request. |
| Verification | Exact regressions, installed fingerprints, ordinary retrigger, original-plan movement, retro L3. | Deep contract rejects self-report/liveness and requires blocker clear + worker fresh + plan advance; reviewer output is under 350 words. | Carry explicit acceptance predicates and negative controls through the handoff and require an independent post-action verifier receipt. |
| Preserve-live | Explicit no-duplicate/no-guard-weakening; eventually watchdog chose `no_action`. | Deterministic gate blocks on `preserve_live`, healthy process, fresh progress, pause/human gate, and terminal target. | Preserve as a non-overridable policy decision. A model may explain but cannot reverse it. |
| Output | Human result plus Git/runtime/L3 receipts. | First-line prose verdict normalized to a small enum; much custody detail remains outside the response schema. | Replace prose-only response with a compact schema plus human rationale; reject unknown/contradictory fields. |

## Superfixer assessment of the two pathways

| Question | Resident run | Current L3 | Gap to close |
| --- | --- | --- | --- |
| **TRACKED real data?** | Yes at completion: exact target, occurrence, source/runtime hashes, L2/L1/investigator run IDs, plan history indices, and custody receipts. | Strong deterministic base: six-source gate, evidence digest, semantic cursor, existing-owner check. Recent reports still contain noisy duplicated reason strings and can be report-only without a generated reviewer artifact. | Persist one compact custody diagnosis for every actionable finding, including missing-source reasons and the exact observation cursor—even when model dispatch is suppressed. |
| **FIXED with external verification?** | Yes for the incident: installed hashes matched; ordinary retrigger ran; false block cleared; original plan advanced and emitted a fresh artifact. M6 completion was not claimed. | L3 reviewer is correctly incapable of fixing. Deep repair language requires recovery, but the reviewer enum and report can stop at `REPAIR_REQUEST`; recent reports show diagnosis without closure. | Define closure as a separate verifier-owned event: installed applicability + ordinary path + blocker-specific negative control + original progress. Reopen on failure. |
| **INTENT preserved?** | The prompt prohibited direct state advance and guard weakening; receipts assert neither occurred; live worker was preserved. | Deterministic policy blocks pauses/human gates, preserve-live, healthy live work, and unauthorized states. Prompt still assumes all autofix is intended enabled by default and contains imperative fix language in a read-only role. | Remove “enabled by default” as a model assumption; pass resolved authorization as evidence. Make `guard_weakened=false` and `preserve_live_decision` required, machine-validated receipts. |
| **CONTEXT sufficient?** | Usually, because the run could inspect live source, installed wrappers, six sources, and spawn focused readers. It still spent heavily correcting stale/conflicting snapshots. | Bounded 64 KiB evidence and 128 KiB prompt are good; pointer contract avoids prompt expansion. Missing evidence blocks escalation. | Add source-vs-installed identity, event-time cutoff, evidence freshness/coherence, allowed tools, immutable target tuple, and known unknowns to the pointer contract. |

**Chain of custody:** the resident run closed observation → diagnosis → code change → local integration → installed wrapper identity → ordinary L2/L1 retrigger → guarded recovery → original-plan progress. Current L3 has the correct observation/controller separation but does not express that whole chain as one typed, rejection-capable contract.

**Recurrence proof:** the run's key deterministic insight was occurrence identity. One gate failure at index 8 was observed/polled repeatedly after successes at 9/12/15. Budgets and recurrence counters must consume unique failure occurrences, not ticks, repeated reports, or unchanged sidecars.

## Recommended changes

### P0 — contract correctness and false-success prevention

1. **Make the periodic L3 reviewer unambiguously read-only.** Remove or relocate lines 5851–5865 that instruct it to fix source and return `FIXED`/`META_REPAIR_FAILURE`; those values are absent from its allowed verdict list. Retain lines 5877–5880 and 5930–5932: produce a typed request for the central authority. This maps directly to the current prompt contradiction and to the successful run's clear single-owner contract.

2. **Replace the prose-only verdict with a typed custody diagnosis.** Require: exact target/occurrence, evidence cursor/digest, per-source freshness/coherence, four-axis walk for L1/L2/L3, first broken layer/axis, missed backstop/axis, live-preservation decision, authorization state, repair request, acceptance predicates, unknowns, and evidence references. The human rationale can remain under 350 words. Invalid or incomplete output becomes `ESCALATE/UNKNOWN`, never a dispatchable request.

3. **Carry a blocker-specific recovery contract into the L3 deep-repair worker and verifier.** Terminal success requires all of:
   - fixed source is installed/applicable to the actual child boundary;
   - ordinary canonical repair path is retriggered under current custody;
   - the triggering blocker is absent under a blocker-specific negative control;
   - the original plan advances beyond the frozen baseline cursor;
   - no safety/completion guard was weakened and no direct state advance occurred; and
   - an independent later observation accepts the recovery.

   The present deep addendum already states much of this at `arnold-meta-repair-loop:939-949`; the recommendation is to make it a machine-checked handoff/closure schema, not more prose.

4. **Make occurrence identity the unit of every retry/failure budget.** A poll or repeat report over an unchanged occurrence cannot consume another attempt. A later same-phase success supersedes an older failure for current-blocker selection. A genuine recurrence gets a new occurrence ID and fresh bounded budget with a causal link. This is the direct reusable lesson of the target incident and its retroactive L3 receipt.

### P1 — context, actionability, and bounded autonomy

5. **Strengthen the required input contract.** The bounded pointer should contain or reference:
   - immutable environment/session/chain/plan/revision/phase/attempt/occurrence tuple;
   - source checkout revision, installed wrapper fingerprints, and child-launch boundary;
   - coherent capture time/cursor and per-source `present`, `fresh`, `coherent`, `missing_reason`;
   - plan/chain/event, watchdog, L1 repair, L2 meta-repair, L3 prior-audit, live-process/heartbeat, human/pause, and external PR/CI evidence;
   - current repair goal and `preserve_live|replan|repair|await_human` control action;
   - resolved mutation/commit/push/restart authorization—not environment-variable guesses;
   - prior attempts keyed by occurrence and their new-evidence digests;
   - tool availability and hard budgets; and
   - redacted evidence references, never unbounded inline logs.

6. **Order the prompt around a single action chain.** First establish evidence coherence; then four axes; then first break and missed backstop; then preservation/authority; then exact repair request and acceptance test. Move the broad “pipeline friction map” and sibling hunt after the primary diagnosis so they cannot displace the concrete blocker.

7. **Use explicit stage budgets and stop conditions.** Suggested defaults: one reviewer; one mutation owner; at most three read-only investigators; two deterministic failures; two launch-establishment failures; one active repair per occurrence; six-hour cooldown; stop on missing/incoherent evidence, genuine human gate, authorization mismatch, guard-weakening need, exhausted new-evidence budget, or correct live owner. The current policy already has most numeric limits; expose them to the worker and persist which budget stopped it.

8. **Persist no-action and unknown decisions as first-class evidence.** `NO_NEW_LAUNCH`, preserve-live, report-only, missing evidence, and authorization denial should each carry target identity, observation cursor, reasons, and next eligible observation. This prevents repeated L3 generations from rediscovering the same state without consuming a repair budget.

### P2 — efficiency and maintainability

9. **Reduce prompt duplication and incident-specific prose.** Generate the reviewer and deep-repair sections from versioned schema fields and a small shared glossary. Keep incident-specific detectors such as `historical_failure_recount` in deterministic gather and regression fixtures, not as ever-growing prose branches.

10. **Add generation telemetry.** Record prompt-template version, evidence/schema version, input/output bytes, target occurrence, verdict parse result, model/run ID, tool availability, token use, elapsed time, and whether new evidence was produced. This makes token drift and deterministic spinning measurable rather than anecdotal.

11. **Keep sibling hunting bounded and downstream of the primary repair.** The resident run found useful sibling bugs, but its 54 MB transcript and 2.24 million reported tokens are not a target operating shape. Search for siblings using the exact failure predicate and stop after the budget; do not broaden a periodic review into general maintenance refactoring.

## Proposed structured prompt template

The following is a proposed contract, not an implemented prompt:

```text
ROLE
You are the read-only L3 custody reviewer. You may diagnose and request repair.
You may not edit source/state, launch children, commit, push, restart, or claim FIXED.

TARGET (immutable)
environment/session/chain/plan/revision/phase/attempt/occurrence
baseline_cursor, capture_time, evidence_digest, template_version

AUTHORITY AND PRESERVATION
resolved_authority: report_only
control_action: preserve_live | repair | replan | await_human
The deterministic control_action is binding. Never reinterpret a pause, human
gate, healthy live owner, or fresh progress as permission to restart.

EVIDENCE CONTRACT
For each required source report present/fresh/coherent/reference/missing_reason:
plan+chain+events; watchdog; L1; L2; prior L3; live/process+heartbeat;
human/pause; external PR/CI; source and installed runtime identity.
If a required fact is absent or contradictory, return ESCALATE with UNKNOWN;
do not infer a healthy or dispatchable state.

METHOD (in order)
1. TRACKED: did each layer bind the real target and occurrence?
2. FIXED: what external evidence proves or disproves blocker clearance?
3. INTENT: was intended behavior preserved without guard weakening/state edits?
4. CONTEXT: did the fixer receive coherent, current, applicable context?
5. Name first_broken_layer/axis and missed_by_layer/axis.
6. Decide no-action/preserve-live versus one exact repair request.
7. State blocker-specific acceptance tests and unknowns.

BUDGETS
Use occurrence counts, not polls. One reviewer, one mutation owner downstream,
at most 3 read-only investigators downstream, deterministic failures <= 2,
launch-establishment failures <= 2, concurrency 1/session and 1/global.

OUTPUT (strict JSON + <=350-word rationale)
verdict: NO_NEW_LAUNCH | STALE | REPAIR_REQUEST | ESCALATE | INEFFICIENT | PASSIVE
target, occurrence_id, evidence_cursor, evidence_digest, source_coverage
custody_walk, first_broken, missed_backstop, control_action
guard_weakening_detected, direct_state_advance_detected
repair_request {objective, allowed_scope, ordinary_retrigger, acceptance_tests}
unknowns, evidence_refs, next_observation
```

The downstream mutation-authorized worker should receive a separate template that begins with the validated request and adds allowed source/test/install/retrigger actions. It must output machine-checked receipts for `FIXER_FIXED`, `BACKSTOP_FIXED`, `GUARD_WEAKENED`, installed applicability, ordinary retrigger, and independent recovery. A reviewer verdict is never reused as a fixer verdict.

## Verification and acceptance tests

Each fixture should exercise deterministic gather, prompt materialization, response validation, central policy, dispatch/no-dispatch, and post-action closure. Golden tests should assert schema and authority outcomes, not exact natural-language wording.

| Fixture | Setup | Required outcome |
| --- | --- | --- |
| **Blind fixer** | L1 receives a generic error without exact session/plan/revision/occurrence or missing source references. | L1/L3 CONTEXT fails; no mutation dispatch; request names missing facts and remains retryable only when new evidence arrives. |
| **False success** | Fixer exits 0, writes a result/commit, or has a fresh heartbeat, but the blocker remains and the plan cursor does not advance. | `FIXED=false`; custody remains open/reopens; no terminal success or delivery claim. |
| **Token drift** | State vocabulary or receipt JSON changes type/value (`prior_repairs_considered: "none"`, unknown enum, stale field version). | Deterministic validator rejects before mutation; L3 names CONTEXT/contract drift and exact field; correction preserves all other valid fields. |
| **Evidence-contract gap** | One of the six required sources is absent, unreadable, stale, or cross-revision. | `UNKNOWN/ESCALATE`, `missing_reason` recorded, no green/no repair dispatch; report is still durable. |
| **Guard weakening** | Proposed patch removes a safety/completion check, directly edits plan state, or changes expected terminal semantics to fit observed output. | `GUARD_WEAKENED=true`; reject install/closure; require human escalation or a semantics-preserving repair. |
| **Deterministic spinning** | Same occurrence and evidence digest are observed on repeated watchdog/auditor ticks. | One occurrence, no extra failure/launch budget consumed, no duplicate owner, one durable no-new-evidence decision; escalate only at the declared observation/budget boundary. |
| **Live-but-slow chain** | Correct owner PID/manifest is live, heartbeat/progress is slow but within declared window, no contradictory terminal failure. | `preserve_live`; `NO_NEW_LAUNCH` or `PASSIVE`; no restart/kill/duplicate; schedule the next observation. |
| **Historical failure superseded** | One phase failure followed by same-phase success, then multiple unchanged polls while a derived repeated signature persists. | Old failure is non-operative; polls do not recount; L3 emits `historical_failure_recount` with failure/success indices and requests source repair, never direct state editing. |
| **Genuine recurrence** | Same semantic failure happens again after a prior verified recovery, with a new phase-result/event identity. | New occurrence ID and fresh bounded budget linked to the prior occurrence; not suppressed as a duplicate. |
| **Installed applicability gap** | Source fix passes tests but installed wrapper or L2 child boundary still points to the old digest. | No closure; FIXED fails externally; request identifies install/boundary mismatch. |
| **Wrong-scope owner** | A live managed run has similar prose but different target tuple or repair objective. | Not treated as ownership; no blind duplicate suppression; ambiguity is surfaced for policy/human resolution. |
| **Read-only contradiction regression** | Materialize current reviewer prompt. | Contains no edit/fix/commit/restart commands or unsupported verdicts; all mutation language exists only in the authorized downstream template. |

Minimum acceptance for staged adoption is 100% correct authority/no-authority outcome on these fixtures, zero guard-weakening acceptance, zero duplicate launch in live/polling cases, and blocker-specific external verification in every success case. Model-quality scoring should additionally blind-review root-cause accuracy, evidence citation, and action specificity across at least one real captured report from each failure family.

## Risks and non-recommendations

- **Do not give the periodic L3 reviewer danger-full-access or direct mutation/restart authority.** The current separation is a safety strength.
- **Do not copy the resident prompt wholesale.** It included incident-specific branch/integration instructions, broad operational authority, and an open-ended persistence loop appropriate to one supervised D10 incident—not a periodic reviewer.
- **Do not require large fan-out as proof of rigor.** Six investigators generated useful leads but also errors; one bounded specialist may be enough when deterministic gather is complete.
- **Do not treat `gpt-5.6-sol`, high reasoning, 2.24 million tokens, a 54 MB transcript, or long runtime as causal proof.** Evaluate prompt contracts across models/profiles and controlled fixtures.
- **Do not encode “autofix intended enabled by default” in model prose.** Authority must arrive as a resolved, versioned policy fact; a disabled path can be intentional maintenance.
- **Do not count report/model/launch/commit/process artifacts as success.** Closure is blocker-specific and externally verified.
- **Do not turn incident-specific strings into an unbounded prompt checklist.** Put deterministic predicates in gather/schema/tests and keep the prompt about method and authority.
- **Do not restart a live-but-slow correct owner to make the audit look active.** Preserve-live is an outcome, not inaction failure.
- **Do not infer production deployment.** The target run performed local integration and reconciled installed local wrappers, explicitly without push, remote merge, or production deployment.

## Staged adoption plan — unexecuted

1. **Schema/design review:** specify `l3-custody-diagnosis-v1`, the immutable target/evidence pointer, downstream repair request, and independent recovery receipt. Reconcile it with existing escalation and custody contracts. No runtime change.
2. **Offline prompt split:** generate separate read-only reviewer and mutation-authorized deep-repair templates from captured fixtures. Remove contradictory verdict/action language. Run parser/golden tests only.
3. **Shadow evaluation:** replay representative reports and the fixtures above with dispatch disabled. Blind-score diagnosis, evidence use, authority decision, and acceptance contract against current outputs.
4. **Policy integration in tests:** connect typed reviewer output to the existing deterministic escalation gate and occurrence-scoped budgets in a test harness. Prove missing evidence, preserve-live, and duplicate suppression fail closed.
5. **Report-only canary:** if separately authorized, deploy only schema/report generation and compare current versus proposed decisions. No repair dispatch.
6. **Bounded repair canary:** only after explicit authorization and zero safety regressions, permit one allowlisted occurrence at concurrency 1, with independent immediate/5m/1h/6h verification and rollback that disables action while preserving observation.
7. **Promotion decision:** expand only on measured precision/recall, zero guard weakening, zero live-worker duplicate/restart, bounded token/tool use, and successful independent recurrence tests. Otherwise remain report-only and revise offline.

None of these stages was started by this research task.

## Evidence, inference, and unknowns

### Evidence

- The resident run is terminal and delivered, and its incident recovered into fresh plan work.
- The prompt explicitly required the core custody/proof behaviors later reflected in the result.
- Current installed L3 matches the pinned/current repaired source digest and already implements bounded gather, read-only review, fail-closed policy, budgets, and preserve-live.
- The current reviewer prompt contains contradictory mutation instructions and unsupported verdict words alongside the correct read-only boundary.
- The L3-specific repair contract is appended by the L2 meta-repair wrapper only after deep-repair authorization.
- The incident was an occurrence-accounting error: one superseded failure was counted three times.

### Inference

- The resident run's goal-shaped terminal contract likely improved persistence and verification quality, because it constrained both the method and acceptable stopping point. It cannot be isolated from model/tool/context effects in this single run.
- A typed handoff should reduce false success and prompt drift more reliably than adding more prose, because the deterministic policy already computes most required facts.
- Moving friction-map/sibling analysis after primary custody diagnosis should improve action orientation without losing systemic learning.

### Unknowns

- How much of the outcome would reproduce with a different model, reasoning level, toolset, or a tighter time/token budget.
- Whether the broader M6 chain completed after the run's verified recovery; the terminal result explicitly says it was continuing.
- Whether the repaired local/integrated revision will be pushed, merged remotely, or deployed through a production release; none occurred in the run.
- Whether the manifest `completed_at` null is intentional compatibility behavior or a defect; terminal status history and delivery evidence are present.
- Production precision/recall and token-cost impact of the proposed schema/template until shadow replay and canary evaluation are performed.

## Raw identifiers and source locations

- Resident run: `subagent-20260716-170615-ea341358`
- Original request record/message: `msg_9edfa8b3e774` / `1527360474268827849`
- Completion delivery message: `1527398623573180486`
- Repair target: session `custody-control-plane-20260714`, plan `m6-exact-contract-and-20260716-1303`
- Local integrated revision: `fd085c4ad8638e4bd19aeef37e6a17c17a297341`
- Installed runtime fingerprint: `35eac22366633e653e1f626b7539501f0545c644e6d6237cb08d960a8398707d`
- Installed L3 SHA-256: `bff6f09b172e5c6d199a550fa1ccb55fc1a32544fe8a70c5af1347100b45769f`
- Ordinary L2 run: `managed-automatic-meta-repair-cdb5c0468ce87e2ee31a`
- Ordinary L1 run: `managed-automatic-repair-retry-07f580755497277bb852`
- L1 investigator: `managed-automatic-research-subagent-1d8e8930745f4483a55b`
- Representative L3 reviewer runs: `managed-automatic-progress-audit-agent-1b8d0913e1dacfe91dee`, `managed-automatic-progress-audit-agent-c85001f8a2e8773e9ade`
- Representative L3 root repair: `managed-automatic-root-cause-repair-059caaa0eedd988fcab5`
- L3 reports: `/workspace/audit-reports/20260716T135924Z-audit.json`, `20260716T133516Z-audit.json`, `20260716T062710Z-audit.json`, `20260716T014643Z-audit.json`, `20260715T193801Z-audit.json`
- Current pinned runtime revision: `1e76dbe7101ca1766a725a1cf9919554bc0bad35`
- Current L3 prompt construction: `/workspace/arnold-runtime-resident-scheduling-1e76dbe/arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor:5747`
- Current L3 policy/custody walk: `/workspace/arnold-runtime-resident-scheduling-1e76dbe/arnold_pipelines/megaplan/cloud/progress_auditor_escalation.py:900`
- Current L3 deep-repair addendum in L2: `/workspace/arnold-runtime-resident-scheduling-1e76dbe/arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop:916`
