# Judgment — m6a-surface-config

**Verdict:** ABANDONED-AFTER-PLAN — the captured run produced a clean plan, a clean 9-lens critique assignment, and an 18-task decomposition on premium gpt-5.5, then stopped: no Codex execute/review/gate session for plan id `m6a-surface-config-cleanup-20260527-2307` exists anywhere on disk, and no worktree/branch/commit landed. Within its narrow scope the orchestration was efficient and error-free; the milestone simply never ran to completion in this capture.

## The 7 lenses

| # | Lens | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Blockers / dead-ends | **FINE (within capture)** | 0 stalls/retries/resumes across the 3 turns; all 18 `exec_command` exited 0. But the *whole milestone* dead-ended after decompose — no downstream session ever picked it up [VERIFIED: only sessions referencing the plan id are F1/F2/F4 + one process-listing artifact in an unrelated vibecomfy chat]. |
| 2 | Excessive revision | **FINE** | 0 execute→review→rework cycles; all 18 tasks `status:pending`. No rework occurred (nor could it — execute never ran). |
| 3 | Low-value critiques | **MINOR** | Evaluator assigned all 9/9 lenses, 0 skipped, on a milestone of small independent mechanical edits (CLI flags, sentinel dedup). Full 9-lens fan-out on `directed/full` housekeeping is generous; but critics never returned, so no wasted critic spend was actually incurred — the cost was the gpt-5.5 evaluator turn (40K tokens). |
| 4 | Model-tier mismatch | **SIGNIFICANT** | Orchestration was 100% gpt-5.5 premium (3/3 turns) for plan + critique-routing + decompose of self-evidently mechanical work (delete a `default=` key, add `--work-dir`, rename a flag). The routing/decompose turns in particular did not need GPT-5.x. [VERIFIED: `grep "model"` = gpt-5.5 in all of F1/F2/F4.] |
| 5 | Repeated/bloated context | **MINOR** | ~30K-token GPT-5 base instructions re-sent identically in all 3 separate sessions (~90K total system overhead). Turn 1 cached 91% (75K/82K); Turns 2 & 4 cached only ~2.4K each — new sessions reloaded cold. |
| 6 | Model confusion | **FINE** | 0 wrong-file edits, 0 contradictions, 0 looping. The one "ERROR" grep hit was file-read content, not runtime [VERIFIED]. The only confusion is in the *analysis*, not the run (see below). |
| 7 | Inefficiency / waste | **SIGNIFICANT** | 174K tokens + ~18min wall-clock of premium planning produced ZERO landed diff — the milestone was abandoned post-decompose. Highest waste ratio possible: full premium plan, no shipped output. |

### Adversarial spot-check of prior findings
- **"adaptive critique silently fell back to static (KeyError critique_evaluator)"** — **CONTRADICTED for this milestone [VERIFIED].** F2's critique turn returned `evaluator_model:"gpt-5.5"` with 9 real lens→model assignments. The 25 `fallback` / 2 `static` grep hits in F2 are all *instruction/plan prose* ("the configured fallback critic", "a final static grep guard"), not a runtime fallback. No KeyError, no static-path entry. The known bug did not fire here.
- **Facts-file claim "critics ASSIGNED but not executed; only 3/15 files matched"** — **VERIFIED & explained.** Execute/critics are farmed to off-log DeepSeek workers (6× deepseek-v4-pro + 3× deepseek-v4-flash assigned). The manifest over-captured 4×: 12/15 files are unrelated (vibecomfy emitter + May-28 chains). The 84-match `21-59-55` session is a red herring — it is an unrelated vibecomfy operator chat with the megaplan skill *documentation* loaded (cwd=`.../vibecomfy`); the plan id appears once, inside a `ps` process listing. Its 425 "verdict"/582 "blocked" hits are skill-doc text, NOT m6a runtime.

## Top 3 improvements

1. **Abandoned milestone left no trace — silent drop. [HARNESS]**
   *Problem:* plan→critique→decompose completed, then nothing; no execute session, no worktree, no branch, no failure record. From logs alone you cannot tell "completed" from "silently dropped."
   *Root cause:* the chain driver emits no terminal state-transition event when a milestone stops between decompose and execute; `on_failure: stop_chain` / `max_blocked_retries:3` only guard *runtime* failures, not a decompose-then-exit. Combined with the off-log execute farm, a dropped milestone is invisible.
   *Fix:* have the chain write a `milestone_outcome` record (completed | failed | abandoned) to the epic state.json at every milestone boundary, and have `megaplan chain status` surface "decomposed but never executed" as a distinct non-green state. Without it, post-hoc audits like this cannot distinguish success from abandonment.

2. **Premium gpt-5.5 on mechanical orchestration. [DRIVING]**
   *Problem:* plan + critique-routing + decompose of trivially mechanical edits ran on gpt-5.5 (174K premium tokens).
   *Root cause:* `chain.yaml` m6a uses `vendor: codex` + `profile: directed/full` with no cheaper-tier override for orchestration; the driver runs all main-agent turns at the profile's premium model.
   *Fix:* for `directed` housekeeping milestones, pin critique-routing + decompose to a mid-tier model via `override set-model` in the chain spec (keep gpt-5.x only for the initial plan turn if at all). The critique *routing* decision especially does not need a frontier model.

3. **Critique fan-out + manifest over-capture inflate the audit. [HARNESS]**
   *Problem:* 9/9 lenses fired on small independent edits; the log manifest pulled in 12 unrelated files (4× over-capture), nearly producing a false "no execute / critique fell back" conclusion.
   *Root cause:* (a) no lens-budget scaling by milestone size/profile; (b) the manifest builder keys on coarse substrings (`m6a`, `surface-config`) and a time window, not the concrete plan id.
   *Fix:* (a) scale assigned lenses to task count / blast radius for `directed` work (cap at ~4–5 for pure housekeeping); (b) key manifest selection on the exact plan id (`m6a-surface-config-cleanup-20260527-2307`) so audits don't ingest sibling-chain noise.

*File written: .megaplan/briefs/hardening-epic/analysis/m6a-surface-config-judgment.md*
