# Judgment — milestone m0-characterization

**Verdict:** CLEAN, LOW-WASTE run — the characterization gate landed in ~21m on a single premium driver with one legitimate test-caught fix and zero stalls; the only real inefficiency is using a 100% premium GPT-5.4 driver to author deterministic, mechanical test scaffolding.

## Coverage note
The two relevant Codex logs (F4 = 16:08 session, F5 = 16:18 session) capture the **orchestration/driver layer only** — a single `gpt-5.4` Codex agent authoring the characterization suite via tool calls (76 function_calls, 4 patch_apply in F5). The `[megaplan] Starting prep/plan/critique/gate/revise…` strings are **captured subprocess stderr inside golden fixtures the agent was generating** ([VERIFIED] — they appear as one canned banner string with "Expected duration" labels inside `function_call_output`, not as real orchestration phases). No execute-worker (DeepSeek) logs are in this set, as expected; this milestone is test-authoring, so execute farming is minimal anyway.

## The 7 lenses

| # | Lens | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Blockers / dead-ends | **FINE** | 0 SIGKILL / timeout / heartbeat / resume events. ~1s gap between F4→F5 (14:18:31→14:18:32 UTC) — continuous, no idle. `max_blocked_retries=3` never exercised. |
| 2 | Excessive revision | **FINE** | The critique→gate→revise sequences are golden-fixture stderr, not real loops [VERIFIED]. One genuine rework: T3 store-contract assertion fix, well within 1–2. |
| 3 | Low-value critiques | **FINE (N/A in logs)** | No real critique-phase agent turns in these logs; this milestone's *own* critique ran but isn't captured here. No evidence of fired-on-noise critiques. |
| 4 | Model-tier mismatch | **SIGNIFICANT** | Driver = 100% `gpt-5.4` premium ([VERIFIED]: `"model":"gpt-5.4"`, `model_provider:openai` in both session_meta). The work is mechanical test scaffolding (import smoke, parser snapshot, golden fixtures, extend existing contract test) — `directed//high` over-specs the driver for deterministic boilerplate. |
| 5 | Repeated/bloated context | **MINOR** | 97.5% cache hit (11.98M cached / 12.28M input) — caching is working. But ~75KB base instructions + ~50-skill list replayed at each session start; the F4→F5 split paid that twice for one logical task. |
| 6 | Model confusion | **FINE** | No wrong-file edits, no contradictions, no looping. The lone `FileNotFoundError != KeyError` failure was the characterization test correctly catching a real store inconsistency, then fixed. |
| 7 | Inefficiency / waste | **MINOR** | 21m25s / 12.3M tokens (97.5% cached) for ~34K output tokens of real work. Wall-clock fine; the spend is dominated by cached context, not productive generation — proportionate but premium-priced. |

## Prior-finding cross-check
- **adaptive critique → static fallback:** chain.yaml shows m0 does NOT set `adaptive_critique: true` (added only from m3b onward), so the KeyError bug couldn't fire here. Consistent, not contradicted.
- **max_blocked_retries=1:** confirmed fixed in this chain.yaml (`max_blocked_retries: 3`); never triggered in m0.
- **worktree-carry, idle-cap, OpenRouter routing, TIEBREAKER downgrade:** none observed in these logs — clean run.

## Top 3 improvements

**1. Stop driving deterministic test-scaffolding milestones with a premium model. [DRIVING]**
- *Problem:* m0 is pure mechanical characterization (import smoke, `build_parser()` snapshot, golden JSON fixtures, extend an existing 454-loc contract test) yet ran on 100% `gpt-5.4`.
- *Root cause:* `chain.yaml:24` sets `profile: directed / depth: high` for a milestone whose hardest cognitive step was diagnosing one error-class mismatch.
- *Fix:* Downgrade m0's driver to a mid-tier profile (e.g. `directed//medium` or a cheaper vendor for the driver) in `briefs/hardening-epic/chain.yaml`. Reserve premium depth for the semantic-edit milestones (M1/M3*/M5*). The safety-net value comes from the *tests being green on main*, not from premium authorship.

**2. Avoid the F4→F5 session split that re-pays the ~75KB base+skills preamble. [HARNESS]**
- *Problem:* One logical T4 task ran as two back-to-back Codex sessions 1s apart, each re-sending the full base-instructions + skills payload (1 occurrence per session, confirmed).
- *Root cause:* Likely a context-compaction / batch-dispatch boundary that opened a fresh session mid-task instead of continuing.
- *Fix:* In the Codex session/batch dispatcher, prefer continuing the existing session across a batch boundary when the same milestone is still active, or compact-in-place; only fork a new session at a milestone boundary. Cheap win given preamble is the dominant token mass.

**3. Make the orchestration logs self-identifying so judges don't mistake fixture stderr for real phases. [HARNESS]**
- *Problem:* The strongest false-positive risk this pass faced was reading golden-fixture `[megaplan] Starting critique…` stderr as real revision loops.
- *Root cause:* Captured subprocess stderr is byte-identical to live orchestration banners.
- *Fix:* Tag live orchestration phase events with a structured marker (e.g. a `phase_event` record type or a run-id prefix) distinct from any string embedded in test fixtures, so downstream analysis/observability can separate the driver's own phases from captured child output.

---
*Adversarial spot-checks: model tier [VERIFIED] (`grep "model"` both sessions = gpt-5.4); revision-loop framing [VERIFIED] (banner strings live inside `function_call_output`, not real phases); token totals [VERIFIED] (match facts file exactly).*
