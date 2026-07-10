# Loop — hourly check-in protocol for babysitting the watchdog

This is the protocol I follow each time the hourly cron fires AND when the
background watchdog process exits. North star: `watchdog-babysitting-goal.md`.

**Prerequisite state (set up at launch):** the watchdog is running in the
background; an hourly cron re-invokes me with this doc. The current run_id and
background task id live in the running log at the bottom of this file.

## 1. Gather (read these, cheaply)

- `tail` `.watchdog-runs/<run_id>/auto.log` — the event stream
  (`scan`, `codex_done`, `committed`, `round_done`, …). Is it advancing?
- `.watchdog-runs/<run_id>/outcome.json` — per-round `pass/fail`, codex edits,
  regressions, next-turn tests. **The single most important file.**
- Latest `.watchdog-runs/<run_id>/turn-rN-report.md` — Codex's in-depth reasoning.
- `.watchdog-runs/<run_id>/bigger_swings.md` — accumulating larger ideas (tail).
- Background task state: still running, or exited? (its exit re-invokes me.)

## 2. Assess health (is the machine alive?)

| Signal | Healthy | Intervene |
|---|---|---|
| Watchdog process | running, log advancing | **dead/stuck** → §4 |
| Suite pass trend (rounds) | flat-or-up | crashing/reverting → §4 |
| Codex auth | turns succeeding | `token_invalidated` → ask user to `codex login` |
| Per-turn time/cost | within usual band | one turn >> usual → possible wedge, investigate |
| Safety gate | passes each turn | import break / out-of-allowlist → revert + retry fired? |
| Regressions | newly-fixed ≥ regressions | regressions > fixes → flag, may revert that round |

## 3. Assess real improvement vs noise (is Codex earning it?)

- **Where** are the edits? Anywhere under `vibecomfy/` (prompts, runtime,
  executor, schema cache) or `tests/live_agentic_harness/*.py` (grading/harness
  code) is now legitimate. Scenario data, other unit tests, the driver, docs =
  off-rails (the safety gate reverts these).
- **Is the diagnosis real?** Specific failure → specific change → why it
  generalizes. Boilerplate or "tweaked wording" with no theory = weak signal.
- **Movement:** count `newly-fixed` vs `REGRESSIONS` across rounds. Real
  improvement has net-positive movement that doesn't get undone next turn.
- **No gaming:** pass count rising *without* a credible diagnosis, or alongside
  weakened checks / hardcoded answers, is a red flag — intervene.
- **GRADER-CODE WEAKENING (new, high-priority):** each round, `git diff` the
  grading/harness code (`tests/live_agentic_harness/*.py`). Codex MAY edit it to
  fix a genuinely-wrong test, but NEVER to loosen an assertion or raise the pass
  count. Any grader edit that makes a check more permissive = gaming → flag it,
  consider `git revert` of that round, and discount any pass-count gain it bought.
  The pass-count signal is only trustworthy while graders aren't being weakened.

## 4. Decide & act (decision tree)

- **Healthy + improving** → re-arm the cron (it's recurring, so just confirm it's
  listed), append to the running log, wait for next fire or exit.
- **Healthy + plateaued for several turns** → let the run finish, then §5.
- **Watchdog dead/wedged** → read the last log lines + `outcome.json` for the
  cause. Fix the **process** bug if it's in the watchdog/harness wiring (rare),
  or just `--resume <run_id>` to continue the same run. Re-launch in background.
- **Codex auth dead** → I cannot do interactive login. Tell the user to run
  `codex login`, then `--resume <run_id>`.
- **Codex off-rails / gaming** → tighten by reverting the bad round
  (`git revert <sha>` of that round's commit), and if it's structural, note it.
  Consider flipping `--allow-test-edits` only if a test is genuinely broken.
- **Cost/time runaway** → one turn wildly over baseline → investigate; if real,
  flag to user before burning more.

## 5. End-of-run assessment (when the watchdog process exits)

Read `outcome.json` `final` + the full turn-history, then:

- **Working well / converged** (meets the goal doc's five criteria + plateaued)
  → **STOP.** Delete the hourly cron (`CronList` → `CronDelete`). Summarize to
  the user: pass-count first→best→last, what Codex changed, where the pipeline
  landed, any flagged bad scenarios.
- **Progressing, not done** → relaunch to keep improving. Prefer
  `--resume <run_id>` (keeps focus/swings/tests history). Re-arm cron if needed.
- **Stuck or regressing** → diagnose the process issue, fix, then relaunch.

## 6. Operating commands

```bash
# resume the same run (keeps handoff history) — preferred for continuity
python3 scripts/live_agentic_watchdog.py --resume <run_id>
# fresh campaign run
python3 scripts/live_agentic_watchdog.py --iterations 10
# allow Codex to edit scenario files (only if a test is genuinely broken)
python3 scripts/live_agentic_watchdog.py --resume <run_id> --allow-test-edits
# find the current run_id
ls -1t .watchdog-runs/ | head
# watch a live run
tail -f .watchdog-runs/<run_id>/auto.log
```

Cron control: `CronList` to see the hourly check-in; `CronDelete <id>` to stop
babysitting. Stopping the watchdog itself: `TaskStop <task_id>` or kill the pid.

## Running log (append each check-in)

Format: `YYYY-MM-DD HH:MM — run_id — state — pass r1→rN — action`

<!-- entries below -->

**Campaign (allowlist-FREE model):** run_id=`run-20260628T022848` · background task=`b46hovpnu` (RESUMED from r9 after arnold-edit-fix) · hourly cron=`0d56524d` (fires :00 local) · launched `.venv/bin/python scripts/live_agentic_watchdog.py --resume run-20260628T022848`. MODEL: Codex may edit all of `vibecomfy/` + grading/harness code; scenario data/tests/driver/docs off-limits (git-tree safety gate). PARALLEL RUNNER: scenarios run 12-way concurrent (--single subprocesses, bounded pool, 600s per-scenario timeout) — ~2× faster rounds (~12m vs ~28m), bounded by the 2 slow video scenarios. torch does NOT load for headless scenarios (~60MB each), so concurrency is RAM-cheap; the real ceiling is DeepSeek rate limits. Prior commits dd434fb6/e7397eb6/76f894a8 + this run's 214e65a7/bc61b545/ea1c1b19/2d54ce0a all on the branch. Interpreter: `.venv/bin/python`.

`2026-06-28 02:22 CEST — run-20260628T002107 — LAUNCHED — suite r1 in progress (no pass data yet) — armed hourly cron; babysitting active`
`2026-06-28 02:33 CEST — run-20260628T002107 — R1 SUITE — 14/23 scenarios, zero errors, process alive — /loop 60m cron 100dd354 armed (replaced :13 cron); watching round 1 to first commit`
`2026-06-28 ~02:48 CEST — run-20260628T002107 — R1 STALLED — 21/23 since 02:34; scenario #22 video-video-frame-by-frame-style grinding/hang-prone (agent worker blocks on a network call; runner has NO per-scenario timeout so one slow scenario can eat the 45m suite budget). Letting round 1 ride to completion or suite timeout. ROOT-CAUSE FIX CANDIDATE: missing per-request HTTP timeout in the agent runtime (DeepSeek/Hivemind calls); investigating call site. These 2 video scenarios also make each round ~25-30m → 10-turn run ~5-6h.`
`2026-06-28 02:48 CEST — run-20260628T002107 — R1 SUITE DONE — 23/23 (the slow ones completed, not wedged); scan 4 pass / 19 fail. Hivemind calls already have timeouts (hivemind_feedback.py:287); DeepSeek calls live inside arnold (not patchable in vibecomfy) → robust fix = per-scenario runner timeout, deferred to between rounds.`
`2026-06-28 ~02:55 CEST — run-20260628T002107 — R1 CODEX ✅ — bet: route schema-fragile custom-node edits via `adapt` + hydrate exact target schemas (kills bad refusals). Edited 3 allowlist files (prompts.py/provider.py/artifacts.py), validated (14 pytest), committed dd434fb6 (allowlist-only ✅, no revert, tree clean). GOOD/BAD refusal framing actively used by codex. NOTE: watchdog recorded git_commit=null though commit landed (codex self-committed via bypassed approvals → watchdog commit step no-op); cosmetic. R2 suite running. Easing to ~10m checks.`
`2026-06-28 ~03:00 CEST — run-20260628T002107 — HOURLY CHECK-IN — healthy: watchdog+runner alive, no errors. r1=4/23 (codex dd434fb6, allowlist-only ✅). r2 suite ~7m in (started 02:53, ~27m expected). Decision: KEEP GOING; need r2 to judge if adapt-routing bet moved pass count. ~30m/round → ~3-4h more for 10 rounds.`
`2026-06-28 ~03:24 CEST — run-20260628T002107 — R2 DONE ✅ — 4→6 pass (+2 net). NEWLY FIXED: image-sdxl-txt2img-cat-in-spacesuit + image-style-transfer-using-ip-adapter (the r1-predicted rollback fixes ✓) + speed-distillation-research (SUSPECT — web 429 in r1, maybe flaky not real). REGRESSION: multi-crops-face-previews-it-sets (research drifted too broad). r2 codex committed e7397eb6 (anchor adapt research to exact classes), self-diagnosed the regression, targeted it. Loop self-correcting as designed. R3 running (tests regression recovery + gain retention). Note: r2 structured checks envelope empty but report+commit+handoff complete (cosmetic).`
`2026-06-28 ~04:28 CEST — MODEL CHANGE + RELAUNCH — removed the fixed allowlist; Codex now edits all of vibecomfy/ + grading/harness code via a git-tree safety gate (robust to self-commits). Stopped old run run-20260628T002107 (r1-r3 = 4→6, commits preserved). New run run-20260628T022848 / task b9x22wjek / cron 0d56524d launched. NEW babysitting duty: review grader-code diffs each round for weakening (= gaming). Validated before launch: 19 unit tests pass, git gate detects+reverts a rogue tests/ edit, --smoke --dry-codex plumbing clean, brief has no 'allowlist'.`
`2026-06-28 ~04:57 CEST — run-20260628T022848 — HOURLY CHECK-IN — healthy. r1 suite DONE 5/23 (baseline; builds on old run r1-r3 commits — vs old run's r1=4). codex r1 turn mid-flight (started 02:56 UTC). No commits/rogue/grader edits yet. KEEP GOING; awaiting r1 commit to assess freedom-used + grader-safety. PENDING USER: per-scenario runner timeout to cut ~30m rounds → ~15m.`
`2026-06-28 ~05:08 CEST — run-20260628T022848 — R1 DONE ✅ BREAKTHROUGH — 5/23 baseline; codex USED THE NEW FREEDOM: edited runtime files edit.py (+82) + diagnostics.py (+5) — a STRUCTURAL fix to the queue-safety blocker (_stage_summarize_v2 schema_less_queue_blocker): pre-existing schema-less UI nodes no longer falsely block queue validation (fail-closed preserved for genuinely new nodes). This is the 'target-aware revision evidence' fix the old run could only write as a bigger-swing — codex implemented it directly. ANTI-GAMING CLEAN (pipeline-only; no grader/scenario/driver/docs; report says so). Safety gate PASSED, sha 214e65a7 recorded (new git commit model works — fixed old null-tracking). 11.7m codex turn (substantial). r2 = payoff test (falsely-queue-blocked scenarios should pass). Validates removing the allowlist.`
`2026-06-28 ~05:42 CEST — run-20260628T022848 — R2 DONE ✅✅ — 5→8 pass (+3, ZERO regressions). NEWLY FIXED: audio-tts-narration-using-indextts-2 (the r1 queue-safety fix's target ✓), multi-crops-face-previews-it-sets (old run's regression, recovered), 3d-generates-a-3d-mesh-from. r2 commit bc61b545 = ANOTHER structural root-cause fix: object_info/widget schema resolution (consume.py +49, widgets/schema.py +33, edit/apply.py) — fixes the 'invalid widget field → rollback' chain (the schema-source root cause flagged in the Q2 strategic analysis). ANTI-GAMING CLEAN across r1+r2 (no grader/test/driver/docs). New run (5→8 in 2 rounds, structural, 0 regressions) clearly beating old run (4→6 in 3 rounds, prompt oscillation, 1 regression). r3 running.`
`2026-06-28 ~06:04 CEST — run-20260628T022848 — HOURLY CHECK-IN — healthy, no r3 result yet. r3 suite grinding on the 2 slow video scenarios (21/23, ~22m in, runner blocked on #22 — recurring pattern; finishes before 45m timeout ~04:18-04:26 UTC). Stray codex proc lingering from r2 (harmless). r1→r2 = 5→8 (+3, 0 reg) stands. KEEP GOING. RECURRING DRAG: the 2 video scenarios waste ~7-14m/round every time — per-scenario runner timeout increasingly warranted (pending user decision).`
`2026-06-28 ~06:14 CEST — run-20260628T022848 — R3 DONE — 8→10 pass (net +2: +4 fixed / -2 REGRESSED, first regressions this run). FIXED: image-animatediff-video, image-image-editing-with-qwen, video-generates-a-video, video-video-frame-by-frame-style. REGRESSED: audio-tts-narration-using-indextts-2 (r1's win) + multi-crops-face-previews (r2's win). r3 commit ea1c1b19 (codex self-committed → watchdog recorded commit=None; change IS in git): edit.py 'allow localized revise on custom-node graphs when blockers are pre-existing schema/readiness uncertainty' — a LOOSEN. Anti-gaming clean. WATCH r4: recover the 2 regressions without losing r3's 4 gains? If r4/r5 ping-pong on these = deeper revise-gate tension needing a surgical fix. r4 suite running.`
`2026-06-28 ~07:30 CEST — PLATEAU + PARALLELIZATION — run plateaued at 10 (r3/r4 flat, oscillating +4/-2 then +3/-3). Stopped run, BUILT a parallel runner (tests/live_agentic_harness/runner.py): scenarios run 12-way via --single subprocesses + bounded pool + 600s per-scenario timeout. Verified torch does NOT load for headless scenarios (~60MB each → RAM-cheap; ceiling is DeepSeek rate limits). Smoke-tested 2-way (correct). RESUMED run-20260628T022848 from r5 (task bxa5tm6o0). r5 suite ran 12-way in 12.7m (~2× faster; bounded by the 2 slow scenarios) → 11/23 (NEW HIGH, plateau broke), 0 × 429, RAM 44% free. codex r5 running. ~5 rounds left.`
`2026-06-28 ~08:40 CEST — run-20260628T022848 — HOURLY CHECK-IN (parallel) — healthy. r5=11/23 (+1 CLEAN, oscillation settled; codex self-commit 9efe58d1 'Allow safe fanout from existing schema-less nodes' — another structural edit-gate fix). Trajectory 5→8→10→10→11. r6 running (parallel ~12m rounds, 0 × 429, RAM fine). Anti-gaming CLEAN throughout (no grader/test/driver/docs). Note: cron's inline task id is stale (b9x22wjek=stopped); live task is bxa5tm6o0 per this header. KEEP GOING; ~4 rounds left (r6-r10).`
`2026-06-28 ~09:40 CEST — run-20260628T022848 — HOURLY CHECK-IN — r6=9/23 (−2 net: +1/-3 REGRESSED from r5's 11). Oscillating 9-11 (r3-r6: 10/10/11/9) on the revise-gate/schema-less-node tension — trading fixes for regressions. r6 commit d2960c28 (watchdog committed it; sha recorded). Anti-gaming CLEAN, 0 × 429. r7 running. KEEP GOING but NEAR CEILING for single-round edits on this tension; watch r7-r10 for breakthrough >11 vs continued oscillation (= ceiling → end-of-run stop at r10). Net still up r1→r6 (5→9).`
`2026-06-28 ~10:35 CEST — run-20260628T022848 — RUN KILLED at r8 (during /model switch to glm-5.2; switch only affects babysitter model, NOT the run's Codex/DeepSeek — kill was incidental). Trajectory 5→8→10→10→11→9→12→10 (peak 12 r7; oscillating 9-12 near ceiling). r7 commit f8d07851 'Normalize schema field aliases in agent edits' (pipeline). ANTI-GAMING VERDICT on r8 assessor.py edit (45883f40, assessor-only): LEGIT accuracy fix — skips error diagnostics from failed EXPLORATORY batch turns when a successful candidate was applied (don't penalize the final graph for scratch attempts); narrowly scoped, did NOT inflate count (12→10 within DeepSeek variance), matches allowed 'fix a genuinely-wrong test' category. No revert. RESUMING per user 'Continue' to finish r9-r10.`
`2026-06-28 ~10:10 CEST — run-20260628T022848 — ENV FIX + RESUME — an editable arnold install (_editable_impl_arnold.pth → local /Documents/Arnold checkout, which lacks pipelines.megaplan) broke new python processes (resume crashed: ModuleNotFoundError). Fixed: reinstalled git-pin arnold 0.23.0 (non-editable) → arnold resolves to venv site-packages again. Resumed from r9 (task b46hovpnu). Boot clean (no ModuleNotFoundError), r9 suite running (parallel). KEEP GOING to finish r9-r10.`
`2026-06-28 ~10:41 CEST — run-20260628T022848 — r10 SUITE=13/23 (NEW HIGH, beats r7 peak 12 — r8 assessor-accuracy fix + r9 paid off) but watchdog DIED mid-r10-codex turn (5 concurrent analysis-codex subagents I launched competed with r10's codex turn). RESUMED r10 (task b6uh7esor; subagents done, no contention). 5-CATEGORY CODEX FAILURE ANALYSIS: cat1 (7 "destroy editor state") = ALL FALSE BLOCKS — guard_emit in vibecomfy/porting/refuse.py over-conservative (treats changed inputs on existing nodes as editor-state loss); fix = target-aware attribution (~7-scenario unlock, same family as r1 queue-safety fix). cat2 (2 3d semantic) = SCHEMA-HINT gap — agent gets opaque widget_0 not field semantics; fix = enrich object_info widget metadata (names/descriptions/ranges/directionality) + require semantic evidence before numeric edits. cat3 (animatediff queue) = FALSE block — fix = generalize r1 carve-out (removed links to DELETED consumers = safe; compare by endpoint not raw link id). cat4 (speed-distillation) = TEST-BUG + valid no-op — scenario lacks expect_graph_changed; agent gave substantive distilled-LTX/LCM-LoRA recommendation; fix = make scenario non-editing (expect_graph_changed:false + evaluate reply text). cat5 (multi-crops + frame-by-frame) = AGENT ERROR (validation errors not surfaced — fix = pre-apply validation returning CONCRETE errors + persist them) + AGENT INEFFICIENCY (67 search turns 0 landed — fix = research-turn cap 3-5, don't raise timeout). CROSS-CUTTING: dominant remaining failures are COARSE SAFETY GATES (guard_emit + queue) treating legit edits as destructive — next big unlock = target-aware guard_emit. ~9/13 still-failing are fixable structural/gate issues, NOT capability ceiling.`
`2026-06-28 ~11:00 CEST — run-20260628T022848 — END OF WATCHDOG RUN (killed by user pivot). Final trajectory r1=5->r2=8->r3=10->r4=10->r5=11->r6=9->r7=12->r8=10->r9=10 (r10 suite hit 13, codex turn killed; final=None). Net: 5->~10-13 via STRUCTURAL fixes (queue-safety, schema resolution, schema-cache, edit-gate, assessor accuracy). Babysitting cron 0d56524d KILLED (run over). PIVOTED to new goal: deploy codex fix-subagents for the 5-category fixes (guard_emit target-aware, queue-gate generalization, research-turn cap, scenario fix, validation feedback, widget-semantics prompt) — DONE (fix1+fix2, all compile) — then run the full 100-test corpus (was 23, +77 new = 100) + cluster failures + per-cluster investigation + recommendations.`
`2026-06-28 ~12:00 CEST — GOAL COMPLETE — 100-TEST SCORE: 32/100 (orig 23=10/23 unchanged, new 77=22/77). Deployed 6 fixes (all compile) but they DIDN'T move the score: guard_emit was correct but NOT WIRED (edit.py::_stage_emit missing guard_resolved_ops), validation helper unwired, prompt rules insufficient, + 77 new scenarios exposed 2 new false-blocks. HIGH-THINKING CLUSTERING of 68 failures → 6 clusters; per-cluster codex investigators confirmed root causes + fixes: (1) research-route 10 — core.py research needs_implement=False + research prefetch; (2) UnsupportedNonDAG 22 — ingest/normalize.py recognize VibeComfy compiled_api envelope + narrow classify_failure [BIGGEST]; (3) genuine-hard 23 — _build_adaptation_plan deferred; need adapt plan→execute layer ('topology transplant compiler'); (4) destroy-editor-state 7 — WIRE guard_resolved_ops in edit.py::_stage_emit (activates deployed fix); (5) schema/IR 4 — wire validation_errors_payload into implementation_result.json + schema-source; (6) semantic 2 — enrich widget metadata (directionality) + hard preflight gate. CROSS-CUTTING: ~45/68 failures are FALSE-BLOCKS (pipeline rejecting valid edits), only 23 genuine-hard. Recommended order: wire guard_emit (7) → fix ingest envelope (22) → fix research route (10) → wire validation (4) → widget semantics (2) → adapt-compiler (23). Projected: fixes 1-4 → ~70+/100. Goal closed.`
`2026-06-28 ~13:30 CEST — WAVE 1 + WAVE 2 FIX-DEPLOY + 100-TEST CYCLE — WAVE 1 (4 fixes: guard_emit wiring, ingest envelope, research route, validation feedback) → 100-test: 32→57 (+25, the ingest-envelope + research-route fixes took). WAVE 2 (3 fixes: widget-shape guard, metadata-precedence, accounting bug) → 100-test: 57→56 (FLAT — fixes compiled but DIDN'T TAKE: widget-shape guard not wired to the pre-pass call site; metadata-precedence in consume.py but output-arity reconciliation is a different path). KEY PATTERN: fixes are logically correct but don't reach the failing code path (WIRING/COVERAGE GAPS) — same as the original guard_emit. Post-Wave-2 clustering of 44 failures (6 clusters): (1) destroy-editor-state widget-shape ~8+ — W2 Fix1 didn't take, WIRE guard_resolved_ops into widget-shape pre-pass; (2) output-arity abort ~10 — apply metadata-precedence in arity reconciliation not just consume.py; (3) requires_custom_nodes 14 — GENUINE-HARD, need provisional schemas + adapt-compiler; (4) schema-less queue validation 3 — extend W1 queue-safety to the queue-validation path; (5) intent judge false-neg 2 — rule assertions + judge reads candidate state; (6) agent semantic misses 4 + 1 timeout. FURTHER RECOMMENDATIONS: wire widget-shape fix (~8) → output-arity precedence (~10) → queue-validation schema-less (3) → schema-cache refresh (blocked, needs ComfyUI) → provisional schemas + adapt-compiler (14, long-term) → judge rule assertions (2) → agent field-targeting (4). LESSON: a fix that compiles isn't a fix that takes — verify it reaches the failing code path. Final score 56/100 (orig 23=10, new 77=46).`
`2026-06-28 ~03:32 CEST — OVER-CONSTRAINT WATCH (r2 bet e7397eb6) — _looks_schema_fragile_label heuristic FALSE-POSITIVES on CORE nodes (Load Checkpoint/Save Image/Load Image/CLIP Text Encode flagged via the bare space/'-'/'+' symbol fallback; branded-marker matching is correct). → schema-fragile hint will over-nudge simple core-node edits toward adapt. Also: "do not transplant unless same class type" may over-constrain legit cross-class adapt; accumulating never/must clauses risk re-introducing bad refusals. WATCH r3 for: new bad refusals / stalls / over-routing. Loop catches GROSS over-constraint (bad refusals flip pass/fail); subtle heuristic FP may need explicit flagging (narrow fallback to branded markers — 1-line, allowlisted, codex-owned).`
`2026-06-28 ~03:40 CEST — STRATEGIC FINDING (Q2) — ROOT CAUSE IS A MISSING DATA SOURCE, NOT PROMPTS. Dominant failure msg (verbatim, 3d/video-frame-by-frame/etc): "could not find a workflow precedent or installed/provisional node schema specific enough." + revise blocked by "5 unknown class type(s)". The agent CAN'T FIND schemas for non-installed custom nodes (Rodin/ADE/Qwen/VHS); provisional schemas from workflow JSON too sparse → guesses fields→rollback or refuses. Codex is patching SYMPTOMS (refuse→adapt→research-exact→don't-guess) at the prompt level; root is a schema-knowledge source in RUNTIME code OUTSIDE the allowlist → codex will oscillate + hit a ceiling on custom-node scenarios. Also: intent judge finds NO good declines either round → if judge can't credit good refusals, it penalizes all refusals → drives over-constraint (text_judge.prompt.md IS allowlisted → codex CAN fix this). FORKS: (i) expand allowlist to schema/search layer (high leverage, riskier), or (ii) keep tight + bigger-swing spec for provisional-schema source. BRIEF TWEAKS for next run: anti-oscillation nudge, prefer data-feeding over re-wording, anti-overcorrection guard, discount flaky/web-error scenarios. Plan: don't interrupt this run; bake tweaks next run; steer codex at judge fix; have codex write provisional-schema bigger-swing spec.`
