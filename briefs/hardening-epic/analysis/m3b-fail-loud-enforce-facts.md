# M3b-fail-loud-enforce — Forensic Log Facts

**Milestone:** `m3b-fail-loud-enforce`
**Plan:** `m3b-make-failures-loud-20260526-1223`
**Date:** 2026-05-26, ~1h07m wall-clock

## Log File Relevance
- **12 files** in manifest; **5 relevant** (grep for plan name returned hits), **7 unrelated** (0 hits)
- Relevant files (5 sessions, 1,174 total lines):
  - `rollout-...T12-52-17...` — 375 lines, 102 function calls
  - `rollout-...T13-05-22...` — 353 lines, 83 function calls
  - `rollout-...T13-42-11...` — 203 lines, 62 function calls
  - `rollout-...T13-50-31...` — 188 lines, 53 function calls
  - `rollout-...T13-57-44...` — 55 lines, 12 function calls

**Critical finding:** These are 5 **megaplan execute-batch sessions** (batches 2–6 of 7). Each session has exactly 1 user message (the megaplan batch prompt), 1 assistant message (final output), and N function_call/function_call_output pairs for tool use. The sessions are execute-only — no critique, review, or gate phases appear in these logs. The bulk of grep matches below are from **source/test code being read**, not from actual events occurring during the run.

---

## 1. REVISION LOOPS
**COUNT:** 137 grep matches across 5 files — but nearly all are from source code being read (e.g., `auto.py` inlined in logs containing `STATE_TIEBREAKER_PENDING`, `STATE_BLOCKED`, `DEFAULT_MAX_REVIEW_REWORK_CYCLES`, `EXTERNAL_RETRYABLE_PHASES`). No actual review verdicts were issued during these execute-only sessions. Each session produced 1 assistant response; no execute→review→rework cycle occurred in-capture.

**Evidence (source code reads, not events):**
- `rollout-...T12-52-17...:30` — `STATE_TIEBREAKER_PENDING`, `STATE_TIEBREAKER_READY`, `STATE_BLOCKED` (inlined from `auto.py` source)
- `rollout-...T12-52-17...:30` — `DEFAULT_MAX_REVIEW_REWORK_CYCLES = 3` (constant definition in auto.py being read)
- `rollout-...T12-52-17...:30` — `EXTERNAL_RETRYABLE_PHASES = frozenset({"plan","prep","critique","revise","gate","finalize","review"})`

**Rounds count:** 0 review rounds visible in these execute-only sessions.

---

## 2. CRITIQUE
**COUNT:** 62 grep matches — overwhelmingly from source code reads. No actual critique invocations occurred during these execute sessions.

**Evidence (source code reads):**
- `rollout-...T12-52-17...:55` — `STATE_CRITIQUED` (from `megaplan/_core/state.py` being read)
- `rollout-...T12-52-17...:55` — `_apply_legacy_state_migration` mapping `"evaluated"` → `STATE_CRITIQUED`
- `rollout-...T12-52-17...:6` — task descriptions mention critique in the plan text only

**Critique errors/fallbacks:** 18 matches for `fallback|KeyError|static` near "critique" — all from source code (e.g., `_warn_chain_fallback` in chain.py, `M3A_WARN_VENDOR_LOCK` fallback path). No actual critique error occurred.

---

## 3. BLOCKERS / STALLS / RETRIES
**COUNT:** 101 grep matches — nearly all from `auto.py` source code being read (contains `DEFAULT_STALL_THRESHOLD`, `DEFAULT_MAX_BLOCKED_RETRIES`, `_is_retryable_external_error`, etc.).

**Evidence (source code reads):**
- `rollout-...T12-52-17...:30` — `DEFAULT_STALL_THRESHOLD = 5`, `DEFAULT_MAX_BLOCKED_RETRIES = 1`, `DEFAULT_MAX_CONTEXT_RETRIES = 2`, `DEFAULT_MAX_EXTERNAL_RETRIES = 1`
- `rollout-...T12-52-17...:30` — `_is_retryable_external_error()` function definition (contains "blocked/resumable", "retry_after_s")
- `rollout-...T13-05-22...:47` — `recommended_action: "resume_or_recover"` (from test code fixture being read)

**Retries/resumes:** No actual retry or resume event detected in these 5 sessions. All 5 sessions ran start-to-finish without interruption.

---

## 4. ERRORS
**COUNT:** 154 grep matches — nearly all from source/test code being read (test assertions, exception classes, error handling in source). The most frequent signatures are from code reads:

| Signature | Matches | Source |
|-----------|---------|--------|
| `CliError` | ~227 | Inlined from source |
| `OSError` | ~29 | Inlined from source |
| `UnicodeDecodeError` | ~29 | Inlined from source |
| `JSONDecodeError` | ~17 | Inlined from source |
| `RuntimeError` | ~30 | Inlined from source |
| `ValueError` | ~15 | Inlined from source |

**Traceback count:** 4 total tracebacks across all 5 files (all in source code being read, not runtime tracebacks).

**Evidence (code reads, not runtime errors):**
- `rollout-...T12-52-17...:111` — `test_write_plan_state_rejects_corrupt_json_without_renaming_state` — `pytest.raises(CliError, match="M3B_HALT_CORRUPT_STATE_WRITE")` (test code reading)
- `rollout-...T12-52-17...:354` — `except json.JSONDecodeError as exc: raise CliError("corrupt_state_write", ...)` (source being read)
- `rollout-...T12-52-17...:354` — `except UnicodeDecodeError as exc: raise CliError("corrupt_state_write", ...)` (source being read)

**No runtime errors** were detected in the assistant's actual tool calls or responses.

---

## 5. MODELS / TIER USED
**COUNT (actual model field):** Only 10 `"model"` field matches total:
- `gpt-5.4` — 8 occurrences (primary model for all 5 sessions)
- `gpt-5.5` — 2 occurrences (appears in skill description text only: "Codex (GPT-5.5)")

**Premium vs cheap split:** All 5 sessions used GPT-5.4 (premium). No DeepSeek, Kimi, Claude, or o3/o4 models were used as the primary agent model in these sessions — those names appeared only in code reads and skill descriptions.

**Large grep false positives:** The initial broad grep returned 71× "o4", 64× "o3", 45× "Claude", 12× "Kimi" — all from inlined source code, test fixtures, and skill descriptions (e.g., `subagent-launcher` skill mentioning "DeepSeek / Kimi / Zhipu hermes subagent"). None were model invocations.

---

## 6. TOKEN / COST SIGNALS
**COUNT:** 641 grep matches for token/cost terms. 271 `token_count` events across all 5 sessions.

**Final cumulative token total (last file, last event):**
- Input tokens: 473,791 (cached: 389,888)
- Output tokens: 5,103
- Reasoning tokens: 741
- **Total: 478,894**
- Model context window: 258,400

**Per-session cumulative token growth:**
- Session 1 (batch 2): 6,693,627 → 113,310 (last event)
- Session 2 (batch 3): 6,972,007 → 122,096
- Session 3 (batch 4): 3,904,445 → 79,294
- Session 4 (batch 5): 2,793,239 → 60,154
- Session 5 (batch 6?): 478,894 → 88,214

Note: The first `total_tokens` value in sessions 1–4 appears to be cumulative across the entire chain run, while the second is per-session. Session 5 final: 478,894 total.

**Cost:** No `total_cost_usd` values found in token_count events. The `DriverOutcome` dataclass (inlined in source code) defines `total_cost_usd: float | None` but no actual cost data was emitted in these execute sessions.

---

## 7. REPEATED CONTEXT / WASTE
**NONE FOUND as a measurable pattern.** The system prompt (skills list + personality + formatting rules) is re-sent at the start of each of the 5 sessions — this is inherent to Codex's fresh-session-per-batch design. Each session's user prompt contains the batch task descriptions and completed-task context, which is necessary context. No evidence of the same large file being re-sent multiple times within a single session or the agent re-doing identical work across sessions.

---

## 8. CONFUSION
**NONE FOUND.** 11 grep matches for `wrong.file|mistake|contradict|apologize|...` but all are from inlined source/test code (e.g., test assertions, debt-watch items in batch prompts). No evidence of wrong-file edits, model self-contradiction, action looping, or scope misreading in the assistant's actual tool calls or responses.

---

## 9. WALL-CLOCK
**Duration:** 1 hour, 7 minutes, 20 seconds
- **Earliest:** `2026-05-26T10:52:17.133Z` (Session 1 start)
- **Latest:** `2026-05-26T11:59:37.709Z` (Session 5 end)

**Per-session spans:**
- Session 1 (batch 2): 10:52:17 → 11:05:21 (~13m)
- Session 2 (batch 3): 11:05:22 → 11:16:10 (~11m)
- Session 3 (batch 4): 11:42:11 → 11:50:30 (~8m)
- Session 4 (batch 5): 11:50:31 → 11:57:33 (~7m)
- Session 5 (batch 6?): 11:57:44 → 11:59:37 (~2m)

**Idle gaps between sessions:**
- 11:05:21 → 11:05:22: 1s (Session 1→2, near-instant)
- 11:16:10 → 11:42:11: **~26 minutes** (Session 2→3 gap)
- 11:50:30 → 11:50:31: 1s (Session 3→4, near-instant)
- 11:57:33 → 11:57:44: 11s (Session 4→5)

**Note:** The session timestamps in UTC (10:52–11:59) differ from the stated time window (12:23–13:59). The filenames use `T12-52-17` etc. but the internal `timestamp` fields show UTC (`T10:52:17`). This is a UTC-vs-local offset (~2h); the sessions are correctly identified.

---

## RAW SUMMARY
- **5 execute-batch sessions**, 312 total function calls, **0 review/critique/gate phases** in capture
- **0 retries, 0 resumes, 0 runtime errors** — all source/test code reads
- **478,894 total tokens** (final cumulative), ~89% cache hit rate (389,888 cached of 473,791 input)
- **Model: GPT-5.4 exclusively** (8 model-field matches); no cheap-tier models used
- **1h07m wall-clock** with one 26-minute idle gap between sessions 2→3
