# m0-characterization — forensic log extraction

**Plan:** `m0-characterization-gate-20260525-1545`
**Time window:** 2026-05-25T15:45–16:35 local (14:08–14:29 UTC actual)
**Relevant files:** 2 of 5 listed (file 4: `rollout-...16-08-04...jsonl`, file 5: `rollout-...16-18-32...jsonl`). Files 1–3 are unrelated sessions or contain only stray filename mentions.
**Total lines analyzed:** 623 (314 + 309) across the 2 relevant .jsonl files.

---

## 1. REVISION LOOPS

**COUNT:** 20 critique rounds, 20 gate rounds, 10 revise rounds observed across all pipeline runs in the logs. Each full pipeline cycle contains exactly 1 revise-rework loop (critique→gate→revise→critique→gate→finalize). No manual human-in-the-loop review verdicts (ITERATE/APPROVE/REJECT) appear as agent actions — these are all mock/harness pipeline runs driven by golden characterization tests.

**Evidence (F4):**
- `F4:17` — `[megaplan] Starting critique... [megaplan] Starting gate... [megaplan] Starting revise... [megaplan] Starting critique... [megaplan] Starting gate... [megaplan] Starting finalize...` (fresh run stderr)
- `F4:17` — `[megaplan] Starting execute... [megaplan] Starting review...` (same cycle continues)
- `F4:18` — Same cycle repeats for resume run: `prep → plan → critique → gate → revise → critique → gate → finalize → execute → review`

**Evidence (F5):**
- `F5:18–22` — 10 occurrences of the full pipeline phase sequence in test output, showing consistent critique→gate→revise→critique→gate pattern

**Round count detail:** The megaplan harness runs `prep → plan → critique → gate → revise → critique → gate → finalize → execute → review`. That is 2 critique rounds, 2 gate rounds, 1 revise round, 1 review round per pipeline invocation. The golden characterization tests exercised this ~10 times across sessions (5 fresh + 5 resume variants).

---

## 2. CRITIQUE

**COUNT:** 20 `[megaplan] Starting critique...` lines observed in captured stderr across both sessions. These are internal megaplan harness critique invocations during golden test generation — NOT separate Codex agent critique turns. No `critic_model`, `critique_evaluator`, or `adaptive critique` references found as agent actions in the Codex session logs.

**Evidence:**
- `F4:17` — `[megaplan] Starting critique... Expected duration: 1m-15m.` (appears twice per pipeline run)
- `F5:18` — Same pattern in resume golden test output

**Critique with no change / error / fallback:** NONE FOUND. All critique rounds produced `critique_v1.json` and `critique_v2.json` artifacts (confirmed by artifact filename lists in test output). No `KeyError` or `fallback` tied to critique phase specifically. No `static` flag found in critique context.

**Note:** The word "critique" also appears 3× in F4 and 22× in F5 as test file names (`tests/test_critique.py`, `tests/test_critique_evaluator.py`) in test runner output — these are pytest progress lines, not agent actions.

---

## 3. BLOCKERS / STALLS / RETRIES

**COUNT:** 0 runtime blocks, stalls, or retries. Both sessions ran start-to-finish without interruption.

**Evidence:**
- Zero `SIGKILL`, zero `timeout`, zero `heartbeat` matches in agent-control context
- `retry`/`resume` matches are from skill descriptions and test function names (e.g., `test_resume_after_finalize_matches_fixture`), not actual runtime retries
- `blocked` matches are exclusively from: skill descriptions (`cleanup-loose-branches`), document paths (`docs/ops/blocked-recovery.md`), and test code (`BlockedTask` import)
- `stall` appears 0 times in F4, found only in test docstrings in F5 (`stall_threshold=999` to disable stall guard)

---

## 4. ERRORS

**COUNT:** 52 total error-class matches across both files. After collapsing repeats and filtering test-code-only hits, **1 real runtime error** found.

**Distinct error signatures (entirely from test code/grep output, not agent failures):**
```
  42 StoreError      (production code raise statements, grep hits)
  41 ValueError      (production code only)
  22 FileNotFoundError
  20 KeyError
  13 AssertionError   (7 in test code, 6 in production)
   7 RuntimeError
   5 BaseException
   3 CliError
```

**ONLY real runtime failure:**
- `F4:104` — `FAILED tests/test_multi_store.py::test_multi_store_contract - AssertionError: missing epic/body error class mismatch: FileNotFoundError != KeyError`
  - This is a **test assertion failure** during the T3 (store contract) implementation, where `FileStore.load_body()` raises `FileNotFoundError` but `MultiStore` routing raises `KeyError` for missing epics. The agent detected this, diagnosed it as a genuine mismatch, and fixed it in a subsequent round. Not a confusion — this is the characterization test doing its job.

**Traceback:** 1 hit in F4 (line 35) — `TracebackType` in a Python `Protocol` definition (type annotation), not a stack trace. 0 real tracebacks.

**No agent-level crashes, exceptions, or fallback-to-static paths.**

---

## 5. MODELS / TIER USED

**COUNT:** Single model in both sessions: **gpt-5.4** (Codex). 2 session_meta records confirm this.

| Model | Turns (F4) | Turns (F5) |
|-------|-----------|-----------|
| gpt-5.4 | 1 turn (session) | 1 turn (session) |

**Premium vs cheap split:** 100% premium (gpt-5.4). Zero DeepSeek/Kimi/Claude invocations as the primary agent. Mentions of `deepseek`, `claude`, `opus`, `sonnet`, `kimi` are all from skill descriptions, documentation, and test code — not actual model dispatches.

**Evidence:**
- `F4:1` — `"model_provider":"openai"` in session_meta
- `F4:16` — `"model":"gpt-5.4"` in turn_context
- `F5:14` — `"model":"gpt-5.4"` in turn_context

The megaplan harness itself (running inside the mock characterization tests) touched DeepSeek and Claude — visible in profile documentation replayed in F5 output — but those are harness-internal decisions, not Codex agent model choices.

---

## 6. TOKEN / COST SIGNALS

**COUNT:** 155 token-related lines in F4, 166 in F5. Token usage tracked per-turn via `token_count` events.

**Final cumulative totals:**

| Metric | F4 (session 1) | F5 (session 2) | Combined |
|--------|---------------|---------------|----------|
| input_tokens | 5,660,263 | 6,618,296 | 12,278,559 |
| cached_input_tokens | 5,493,760 | 6,487,936 | 11,981,696 |
| output_tokens | 14,365 | 20,016 | 34,381 |
| reasoning_output_tokens | 5,283 | 5,745 | 11,028 |
| **total_tokens** | **5,674,628** | **6,638,312** | **12,312,940** |

**Cache hit rate:** ~97.5% (11.98M cached out of 12.28M input). Nearly all input tokens were served from cache.

**Cost signals:** No `cost`, `usage`, or `prompt_tokens`/`completion_tokens` fields found in the log events. Only `token_count` events track token metrics. No USD cost totals recorded in these session logs.

**Note:** The high total token counts (~12.3M) are dominated by the massive base instructions + skills list (~75KB of text) replayed in full at session start for each session (visible in session_meta and developer message payloads). The actual agent work consumed minimal output tokens (~34K).

---

## 7. REPEATED CONTEXT / WASTE

**EVIDENCE FOUND — systemic but structured:** The base instructions block (Codex personality + frontend guidance + formatting rules + editing constraints) is ~75KB and appears verbatim in each session's `session_meta` payload. Similarly, the skills instructions list (~50+ skills with descriptions and paths) appears in each session's first `response_item` of type `message`. These are sent once per session — not re-sent per-turn.

- Skills list: 1 occurrence per session (confirmed: `skill-installer` appears exactly once per file)
- Base instructions: 1 occurrence per session (in `session_meta`)

**No evidence of:** The same large context block being re-sent mid-session. No re-reading of identical files within the same turn. No re-execution of completed work. The two sessions are sequential (F4 ends at 14:18:31, F5 starts at 14:18:32) — they represent a single execution split across two Codex sessions (likely due to context window compaction or the megaplan harness dispatching batch 4 as a fresh session).

---

## 8. CONFUSION

**NONE FOUND.** The agent executed linearly and correctly through T4 (golden pipeline characterization tests):

1. Surveyed existing pipeline test harness and resume flow patterns
2. Generated sample runs to inspect stable state fields
3. Implemented `tests/characterization/test_pipeline_golden.py` with `{{WORKDIR}}` normalization
4. Generated golden fixtures: `pipeline_fresh_run.json` (17,662 bytes) and `pipeline_resume_after_finalize.json` (22,698 bytes)
5. Ran full test suite — 2929 passed, 29 skipped (F4) then 2927 passed, 28 skipped (F5, after T3 fix)

**No wrong-file edits, no self-contradiction, no looping on the same action.** The agent's `update_plan` calls (F5) show clean progress: `in_progress → completed` for each sub-step.

The one apparent "error" (`FileNotFoundError != KeyError` in T3) was the characterization test correctly detecting a real inconsistency — the agent then fixed it, not a confusion.

---

## 9. WALL-CLOCK

| Session | Earliest | Latest | Duration |
|---------|----------|--------|----------|
| F4 | 2026-05-25T14:08:05.206Z | 2026-05-25T14:18:31.237Z | **10m 26s** |
| F5 | 2026-05-25T14:18:32.185Z | 2026-05-25T14:29:30.915Z | **10m 58s** |
| **Combined** | 14:08:05Z | 14:29:30Z | **21m 25s** |

**Gap between sessions:** ~1 second (F4 ends 14:18:31.237, F5 starts 14:18:32.185). Essentially continuous — no idle gaps, no overnight pauses. F5 appears to be a fresh session dispatch for the same batch (T4 execution), likely triggered by megaplan context compaction or session split.

**Note on time window mismatch:** The specified window was 15:45–16:35 local (CEST, UTC+2), but actual timestamps are 14:08–14:29 UTC = 16:08–16:29 CEST. The sessions fall within the specified window.

---

## RAW SUMMARY

- **Review rounds:** 20 critique + 20 gate + 10 revise + 9 review per pipeline harness (mock, automated, no human in loop)
- **Retries:** 0 — no stalls, timeouts, or resume events
- **Errors:** 1 real test failure (`FileNotFoundError != KeyError` mismatch), 0 agent crashes
- **Model split:** 100% gpt-5.4 (premium), 0% DeepSeek/Claude/Kimi as driving agent
- **Duration:** 21m 25s across 2 sequential sessions, 12.3M total tokens (97.5% cached)
