# m3a-fail-loud-policy — Forensic Log Extraction

**Plan**: `m3a-make-failures-loud-census-20260525-1748`
**Manifest**: 20 files listed; **8 belong** to this milestone, **12 are unrelated** (m5a-taxonomy-deadcode-docs, m5b-structure-split-cli, m6s runs overlapping in the same time window).
**Total relevant lines**: 1,210 across 8 files (3 substantial sessions + 5 stub sessions).

---

## 1. REVISION LOOPS

**COUNT: 0**

All `reviewer_verdict` fields in task payloads are empty strings (`""`). No execute→review→rework cycle was recorded in these logs. No APPROVE, REJECT, ITERATE, or TIEBREAKER decisions appear.

Evidence — every `reviewer_verdict` is `""`:
```
19:02.jsonl (task T5): "reviewer_verdict": ""
19:14.jsonl (task T6): "reviewer_verdict": ""
19:36.jsonl (tasks T7/T8): "reviewer_verdict": ""
```
The 161 raw grep hits for "ITERATE|TIEBREAKER|REVISE|APPROVE|REJECT|blocked" were noise — all from base system instructions (which contain "APPROVE"/"REJECT") and task descriptions using "blocked" in prose, not actual review events.

---

## 2. CRITIQUE

**COUNT: 0 actual critique invocations**

The 17 grep hits for "critique" are all task descriptions referencing `critique.py` file sites (e.g., "including critique.py and chain.py warning sites called out by the gate") and debt watch items. Zero `critique_model` fields, zero `critique_evaluator` invocations, zero adaptive critique rounds.

4 hits for "adaptive critique" appear only in the skills instructions list (`contextminning-subagentmaxxing` skill description).

**No critique errors/fallbacks**: `grep -iE "fallback|KeyError|static"` returned 0 results in actual event payloads.

Evidence of what "critique" actually refers to:
```
19:02.jsonl (T3 description): "...ensure there is a concrete classification path for all hits
including critique.py and chain.py warning sites called out by the gate."
```

---

## 3. BLOCKERS / STALLS / RETRIES

**COUNT: 0 runtime blockers/retries. 5 stub sessions (possible harness stalls).**

The 103 raw grep hits for "blocked|stall|retry|timeout|heartbeat|resume" are from debt watch items and task descriptions in the batch payload, not runtime events.

**5 stub sessions** (files 20:00, 20:00b, 20:01, 20:01b, 20:02 — 14 lines each): Each has `session_meta`, `turn_context`, and event_msgs with the harness preamble ("You are already running inside the megaplan harness..."), but **zero function calls**. These sessions launched and immediately terminated without doing any work. Possible timeout, startup failure, or harness issue.

Evidence — stub session structure:
```
20:00-15.jsonl: session_meta → event_msg (harness preamble) → turn_context → 
  event_msg → ... → event_msg (14 lines, 0 function_calls)
20:02-21.jsonl: 18:02:21Z → 18:03:20Z (59 seconds, 0 function_calls)
```

No retry/resume events found in any event_msg payloads.

---

## 4. ERRORS

**COUNT: 1 Traceback, 2 test failures (later resolved)**

A single `Traceback` appears in the 19:02 session (T5 execution), from a pytest run showing:

1. `test_gate_logs_warning_when_flag_delta_emit_fails` — assertion error: expected `M3A_WARN_EMIT_FLAG_EVENT` in caplog, found `M3A_WARN_EMIT_ARTIFACT_WRITTEN` instead. The emit was patched at the wrong target.
   ```
   tests/test_gate.py:1405: AssertionError
   assert any("M3A_WARN_EMIT_FLAG_EVENT" in record.getMessage() ...)
   ```
2. `test_load_resilient_to_unreadable_existing_file` — uncaught `PermissionError` from monkeypatched `Path.read_text`; the `FaultRegistry.load` code didn't catch OSError (only `json.JSONDecodeError`).
   ```
   tests/test_pipeline_faults.py:142: PermissionError: denied
   ```

Both failures were resolved by Session 3 (T8): targeted tests passed (200 passed), full suite passed (2970 passed, 29 skipped, 0 failed).

The 98 "Error" and 76 "Exception" grep hits are from code/task descriptions, not runtime errors.

---

## 5. MODELS / TIER USED

**COUNT: GPT-5 (OpenAI provider), 3 turns, 0 premium/cheap split**

All 3 main sessions use `model_provider: "openai"` with no explicit `model` field set. Base instructions say "You are Codex, a coding agent based on GPT-5."

```
19:02 session_meta: provider=openai, model=NOT_SET
19:14 session_meta: provider=openai, model=NOT_SET
19:36 session_meta: provider=openai, model=NOT_SET
```

The 5 stub sessions also use `provider=openai`.

**No other models were invoked.** The raw grep hits for deepseek, claude, opus, sonnet, haiku, kimi, o3, o4 (592 total) are all from:
- Skill descriptions (e.g., "subagent-launcher: Launch an external model as a subagent... DeepSeek / Kimi / Zhipu hermes subagent")
- Code and task descriptions naming model families
- Debt watch items referencing Claude

No actual model API calls to any model other than GPT-5 appear in these logs.

---

## 6. TOKEN / COST SIGNALS

**COUNT: 0 — not present in these logs**

The 575 raw grep hits for "tokens|cache|cost|usage" are all from base instructions and code prose, not structured accounting fields. No `prompt_tokens`, `completion_tokens`, `cost_usd`, or `usage` fields exist in any payload.

These log files are Codex session transcripts, not API accounting logs. Token/cost data was not captured.

---

## 7. REPEATED CONTEXT / WASTE

**COUNT: Full batch payload re-sent 8 times (3 main + 5 stub sessions)**

Each session receives the identical batch payload (~50KB+ of JSON) containing:
- All 9 task descriptions (T1–T9) with full executor_notes, complexity justifications, etc.
- 30+ debt watch items
- 5 sense checks
- Execution context (SD1-SD3 settled decisions)
- 13 watch_items
- Plan execution order rationale and inter-task guidance

The payload is re-sent verbatim each time. The 5 stub sessions received it and did zero work.

`execution_batch` mentions: 19:02=13, 19:14=15, 19:36=11, stubs=2 each. Total: 49 references for 4 completed tasks.

---

## 8. CONFUSION / WASTE SIGNALS

**COUNT: 1 persistent issue across sessions**

**Unused imports never cleaned up**: `megaplan/handlers/shared.py` accumulated unused imports (`BlockedTask, MOCK_ENV_VAR, configured_robustness, save_state, shutil, subprocess, sys`). This was flagged in Session 1 (T5), re-flagged in Session 2 (T6), and acknowledged but deferred in Session 3 (T8):
```
Session 3: "Advisory quality: megaplan/handlers/shared.py still carries the 
previously noted unused imports; T8 only added regression coverage and did not 
widen scope into cleanup."
```
25 total "unused imports" mentions across all files. The advisory was raised but never actioned.

**5 sessions launched but did nothing**: The harness launched 5 Codex sessions between 18:00:15Z and 18:02:21Z that all received the full batch prompt but executed zero function calls. These may indicate harness-level retry/stall behavior, but the logs contain no error or timeout signal — just silent session creation and immediate termination.

**No wrong-file edits or self-contradiction detected** in the logs. The model followed the task ordering (T5→T6→T7+T8) correctly.

---

## 9. WALL-CLOCK

**Earliest relevant timestamp**: `2026-05-25T17:02:59.493Z` (19:02 session)
**Latest relevant timestamp**: `2026-05-25T18:03:20.670Z` (20:02 stub session)
**Duration**: ~60 minutes (1 hour, 0 minutes, 21 seconds)

Per-session spans:
| Session | Task(s) | Start (UTC) | End (UTC) | Duration |
|---------|---------|-------------|-----------|----------|
| 19:02   | T5      | 17:02:59    | 17:14:31  | 11.5 min |
| 19:14   | T6      | 17:14:32    | 17:29:08  | 14.6 min |
| 19:36   | T7+T8   | 17:36:50    | 17:47:31  | 10.7 min |
| 20:00   | (stub)  | 18:00:15    | 18:00:27  | 12 sec   |
| 20:00b  | (stub)  | 18:00:50    | 18:01:03  | 13 sec   |
| 20:01   | (stub)  | 18:01:21    | 18:01:33  | 12 sec   |
| 20:01b  | (stub)  | 18:01:51    | 18:02:03  | 12 sec   |
| 20:02   | (stub)  | 18:02:21    | 18:03:20  | 59 sec   |

**Gap T6→T7+T8**: 7.7 min (harness overhead). **Gap T7+T8→stubs**: 12.7 min, then 5 stubs launched 30-35s apart. No overnight gaps.

Filename timestamps are CEST (UTC+2); JSON timestamps are UTC (17:02Z = 19:02 CEST).

---

## RAW SUMMARY

- **Review rounds**: 0 (no reviewer_verdict values)
- **Critique**: 0 invocations (all hits are task descriptions)
- **Retries/resumes**: 0 runtime; 5 stub sessions (zero work)
- **Errors**: 1 traceback, 2 test failures (resolved by T8)
- **Model**: GPT-5 only, 3 turns, 0 premium/cheap split
- **Tasks**: T5/T6/T7/T8 done (of 9); T9 never executed
- **Duration**: 60 min wall-clock; ~37 min actual work
- **Waste**: ~50KB batch context re-sent 8x; unused imports flagged 3x, never fixed
