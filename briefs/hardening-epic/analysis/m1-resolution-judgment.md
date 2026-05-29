# Judgment — milestone m1-resolution

**Verdict: A clean, efficient orchestration run (0 retries, 0 rework cycles, 1 review pass) whose only real waste is paying premium GPT-5.x to drive trivially-gateable plan/review orchestration — the wrong-tier spend is structural, not a run accident.**

> Coverage note: the 3 Codex sessions for this milestone capture the ORCHESTRATION layer only (the gpt-5.x driver doing plan/review/gate turns). The actual code-edit EXECUTE phase was farmed to cheap DeepSeek worker subprocesses whose logs are NOT in this set. So "execute" findings below judge the driver's orchestration of execute, not the worker edits themselves.

## 7 lenses

| Lens | Verdict | Evidence |
|---|---|---|
| 1. Blockers / dead-ends | FINE | 0 stalls, 0 retries, 0 resume, 0 timeouts across all 3 sessions. Every `blocked`/`STATE_BLOCKED` hit is source/test text being read, not a runtime event. `max_blocked_retries=3` (chain.yaml:135) was never exercised. |
| 2. Excessive revision | FINE | 0 execute→review→rework cycles. Exactly 1 review turn, ending `approved`. No ITERATE/TIEBREAKER/REVISE outside schema text. |
| 3. Low-value critiques | FINE (N/A) | 0 critique invocations. `with_prep: true` but `adaptive_critique` is NOT set for m1 (chain.yaml:28-35) — so the known epic-wide "evaluator silently falls back to static (KeyError critique_evaluator)" bug could not have fired here. Contradicts/limits that prior finding for this milestone: no critique stage ran at all. |
| 4. Model-tier mismatch | **SIGNIFICANT** | All 3 orchestration turns ran premium GPT-5.x: exec drivers `gpt-5.4` (×2), review `gpt-5.5`. [VERIFIED] The review turn's job was a mechanical rubric check ("All must criteria pass") on a finished diff — gateable by a far cheaper model. Profile is `partnered//high +prep`, which buys premium across the board. |
| 5. Repeated/bloated context | MINOR | Review turn (17-47-02) received the ENTIRE plan + all 10 task descriptions + executor notes + sense-check + execution audit + git-diff summary (~200K chars) in one user prompt. Single occurrence, not resent — but a fat payload to feed a premium model for a yes/no rubric pass. |
| 6. Model confusion | MINOR | [VERIFIED] Review model emitted needs_rework verdicts BEFORE inspecting anything ("Review could not be completed because repository diff and source files were not inspected"; "Prior response was premature"), then self-corrected and inspected. Raw log shows `review_verdict\":\"needs_rework` ×4 and `\":\"approved` ×3 fragments + 3×"premature"/2×"not inspected". Cost ≈ wasted tokens before real work; no wrong-file edits. |
| 7. Inefficiency / waste | MINOR | ~46 min wall-clock, well-proportioned to a 10-task unification touching 8+ files. The ~15.5-min gap between exec turns is harness orchestration between batches, not model idle. Main waste is tier (lens 4) + premature-verdict tokens (lens 6), not loops. |

## Adversarial spot-checks
- **[VERIFIED] Tier:** `head -1` of exec sessions only carries `model_provider`; grepping the full files confirms `"model":"gpt-5.4"` in both exec sessions and `"model":"gpt-5.5"` in the review session. 100% premium, 0 cheap-model turns — real, not an extraction artifact.
- **[VERIFIED] Premature-review confusion:** grep of 17-47-02 confirms 4 escaped `review_verdict\":\"needs_rework` + `approved` final, plus 3×"premature", 4×"before inspect", 2×"not inspected". The facts file's "2 self-corrections before real review" is accurate; the underlying pattern (verdict emitted before tool calls) is genuine.

## TOP 3 IMPROVEMENTS

1. **Premium model on a mechanical review/gate turn → wasted premium spend.**
   - Root cause: the `partnered//high` profile assigns premium GPT-5.x to *every* orchestration role, including the final review, which here was a pure rubric check on a completed diff.
   - Fix [HARNESS]: split the review/gate role off the driver profile — route review to a cheaper rater (e.g. a deepseek/sonnet-tier rater) with the existing rubric prompt, and reserve premium for plan synthesis. Add a `review_model` override in the profile (profiles/ + the review dispatch in the orchestration layer) so `partnered//high` keeps premium planning but cheap reviewing. This is the real recurring cost lever, not execute.

2. **Review model emits a verdict before it inspects the diff → burned tokens + a fragile gate.**
   - Root cause: nothing forces the review prompt to require tool-call evidence before a verdict is structurally accepted; the model can (and did) emit `needs_rework` "before inspection" and only self-correct by luck.
   - Fix [HARNESS]: in `megaplan/prompts/critique_evaluator.py` / the review prompt, make the verdict schema reject a verdict that lacks an inspection-evidence field (must cite the diff/files actually read). Have the gate treat a verdict with no inspection trace as invalid and re-prompt rather than relying on the model self-noticing. Cheap insurance once review moves to a weaker model (improvement 1).

3. **~200K-char single-shot review payload re-narrates the whole plan to gate one diff.**
   - Root cause: the review turn is handed the full plan + all task notes + sense-check + execution audit, most of which is irrelevant to "does the diff satisfy the done-criteria."
   - Fix [DRIVING/HARNESS]: trim the review payload to the rubric/done-criteria + the diff + the canonical-contract doc this milestone emitted, not the entire planning history. Reduces the per-review token bill and sharpens the gate; matters more once review runs on a cheaper, smaller-context model.
