# Judgment — milestone m5b-godfiles

**Verdict (one line):** A clean, near-textbook behavior-preserving refactor — the orchestration ran efficiently, but it was over-tiered (all GPT-5.4/5.5, no cheap model on mechanical file-moves) and showed minor self-confusion (orphan-code IndentationErrors + a duplicated patch) that a tighter edit-then-verify loop would have eliminated.

## The 7 lenses

| # | Lens | Verdict | Single most concrete evidence |
|---|------|---------|-------------------------------|
| 1 | Blockers / dead-ends | **FINE** | 0 runtime retries/stalls/blocked states; all 22 `patch_apply_end` events `"success":true`. `resume`/`heartbeat`/`timeout` hits are 100% system-prompt text, not runtime. |
| 2 | Excessive revision | **FINE** | 1 plan-level critique cycle, 0 execute-phase review rounds. No verdict re-flagging — clean single pass. |
| 3 | Low-value critiques | **FINE** | The 1 critique round earned its place: 3 actionable flags (FLAG-001 chain monkeypatch risk, FLAG-002 CLI setup gap, FLAG-003 chain helper omissions) that visibly shaped scope — `critique_output.json` patched, `"success":true`. [VERIFIED] |
| 4 | Model-tier mismatch | **SIGNIFICANT** | Orchestration ran 1×GPT-5.5 (critique) + 3×GPT-5.4 (batches), all `"model_provider":"openai"`. For a *behavior-preserving file-move* refactor, premium reasoning on the review/gate/driving turns is over-spec. [VERIFIED] |
| 5 | Repeated / bloated context | **MINOR** | 4 sessions each re-loaded full Codex base_instructions + ~40-skill catalog from scratch. Mitigated by 93.5% API cache hit (S3: 10.68M of 11.04M cached), so wasted *paid* tokens are small. |
| 6 | Model confusion | **MINOR** | 3 IndentationErrors from orphan-code cleanup (`skills.py:287`, `__init__.py:889`, the dict-entry one) + `_PROGRESS_PHASE_COMMANDS` patched into `cli/__init__.py` twice. All self-corrected. [VERIFIED — facts file under-counted: it said 1 IndentationError, raw logs show 3.] |
| 7 | Inefficiency / waste | **MINOR** | 1h 23m wall-clock, 21.7M tokens for a ~5-file split; reasonable. But two idle gaps (12m + 25m between S3→S4) and batches 4–6 absent from this log set — orchestration wall-clock loosely coupled to actual work. |

**Coverage note (honest framing):** these logs are the **orchestration layer only** — plan/critique/review/gate/driving turns (premium GPT-5.x). The EXECUTE phase was farmed to cheap DeepSeek workers whose logs are NOT here. "0 execute-phase review rounds" means none surfaced in the orchestration log, not that execute was skipped. The tier-mismatch verdict (#4) is therefore scoped to **orchestration spend**, which is the real question.

## Top 3 improvements

### 1. Premium orchestration on a mechanical refactor — drop the driver/review tier `[DRIVING]`
**Problem:** Every orchestration turn ran GPT-5.4/5.5. m5b is a pure re-export-only code-move with a per-split-commit checklist — the hardest reasoning is "did this symbol only move?", which is a grep, not a premium-model judgment.
**Root cause:** chain.yaml gives m5b `profile: directed` + `depth: high`, the same tier as genuinely hard milestones (m2-store at `premium/thorough`). No notion that "structural-move" milestones can drive on a cheaper orchestrator.
**Concrete fix:** Add a lighter orchestration profile for behavior-preserving move/rename milestones (m4, m5a, m5b, m5d) — keep premium only for the critique pass, drop the per-batch driving/review turns to a mid-tier model. Edit `.megaplan/briefs/hardening-epic/chain.yaml` m5b entry to `depth: medium` and verify the harness routes review/gate to a cheaper model for `directed` at medium depth.

### 2. Orphan-code IndentationErrors on every delete-a-function step `[HARNESS]`
**Problem:** Deleting a function repeatedly left orphaned dict entries / dangling blocks with broken indentation (3 IndentationErrors across S3), each needing a second cleanup patch — wasted turns and the duplicate `_PROGRESS_PHASE_COMMANDS` patch.
**Root cause:** The agent edits by line-region then `ast.parse()`-validates *after* the patch, so it discovers the orphan only post-hoc. No "delete the whole symbol + its registrations atomically" guidance for decomposition work.
**Concrete fix:** Add a decomposition-execute guardrail to the move/refactor prompt (the directed execute/revise prompt template): "when removing a function, remove all its registrations/dict entries in the same patch, then ast-validate before applying the next edit." `[HARNESS]` — fixes the prompt, not the run.

### 3. Confirm adaptive-critique actually ran (prior-finding extension) `[HARNESS]`
**Problem:** m5b has `adaptive_critique: true`, yet the critique session shows critique done **inline as GPT-5 with no separate `critic_model` field** — exactly the signature of the known epic-wide bug where the adaptive evaluator silently fell back to static (KeyError critique_evaluator) on every codex-chain milestone. No KeyError is visible *in S1 itself* (the fallback fires upstream), so this is consistent-but-not-proven here. **[FACTS-ONLY — extends prior finding, not independently reproved in m5b logs.]**
**Root cause:** Per the known finding: vendor-based routing key mismatch dropped the evaluator for codex chains.
**Concrete fix:** This should already be fixed per memory (vendor-based + routing key). Add a one-line assertion to the chain harness that, when `adaptive_critique: true`, the critique record carries a `critic_model`/evaluator marker — fail loud if it falls back, so silent static-fallback can never recur unobserved.

---
*Adversarial spot-checks: #4 tier (model fields, all sessions) [VERIFIED]; #6 confusion (3 IndentationErrors + 25× `_PROGRESS_PHASE_COMMANDS`) [VERIFIED]; #3 critique flags [VERIFIED]. Facts file was accurate except it under-counted IndentationErrors (1 reported, 3 actual).*
