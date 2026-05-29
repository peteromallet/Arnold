# M5d Pipeline God-Files — Raw Facts

**Plan:** `m5d-pipeline-god-file-20260527-2106`
**Time window (claimed):** 2026-05-27T21:06–23:07 CEST
**Actual span (all 18 relevant files):** 2026-05-27T19:06:26Z – 2026-05-28T20:46:19Z (~25.5h)
**Execution-only window (2 files):** 2026-05-27T20:29:56Z – 2026-05-27T20:55:49Z (~26 min)
**Files:** 18 relevant out of 24 listed (6 had zero m5d/godfile/patterns/phase_result hits)

---

## 1. REVISION LOOPS

**COUNT: 0 execute→review→rework cycles found in execution files. 13 hits for "revise/ITERATE/rework" in execution agent messages, all from the plan text being read/processed — not from actual revision rounds.**

The plan was created (21:06 session, 1 GPT-5.5 turn), critiqued by 13 subagent lenses (11 small + 2 additional 1-turn files), went through gate/review (54-turn file at 21:59 + 10-turn file at 22:37), then executed in 2 GPT-5.4 turns (22:29 + 22:47). No evidence of the executor being sent back to rework.

Evidence — plan text being processed during execution (not a rework directive):
```
rollout-...22-29-56...jsonl (via jq): "Split pattern joins and dynamic primitives: create
`megaplan/_pipeline/pattern_joins.py` for `majority_vote` and `weighted_vote`..."
rollout-...22-29-56...jsonl (via jq): "Split the static pattern surface: create
`megaplan/_pipeline/pattern_types.py` with `PromoteFn` and `JoinFn`..."
```

Plan itself declares planning-only intent:
```
rollout-...21-06-25...jsonl:6: "assumptions":["This task is planning-only; implementation
will be carried out by a later execution step using this plan."...]
```

---

## 2. CRITIQUE

**COUNT: 13 critique subagent dispatches (11 + 2). 9 lenses assigned across 5× deepseek-v4-flash and 4× deepseek-v4-pro. Evaluator: gpt-5. No errors or fallbacks observed.**

The critique evaluator (gpt-5) assigned lenses per the cheapest-capable-critic rule:
```
rollout-...21-10-09...jsonl:9: "selections":[
  {"check_id":"issue_hints","critic_model":"deepseek-v4-flash",...},
  {"check_id":"correctness","critic_model":"deepseek-v4-pro",...},
  {"check_id":"scope","critic_model":"deepseek-v4-pro",...},
  {"check_id":"all_locations","critic_model":"deepseek-v4-pro",...},
  {"check_id":"callers","critic_model":"deepseek-v4-pro",...},
  {"check_id":"conventions","critic_model":"deepseek-v4-flash",...},
  {"check_id":"verification","critic_model":"deepseek-v4-flash",...},
  {"check_id":"criteria_quality","critic_model":"deepseek-v4-flash",...},
  {"check_id":"prerequisite_ordering","critic_model":"deepseek-v4-flash",...}],
"skipped":[],"evaluator_model":"gpt-5"
```

Critic model roster in the prompt:
```
| Rank | Model | Cost hint |
| 1 | claude-opus-4-7 | $$$$ |
| 1 | gpt-5.5 | $$$$ |
| 2 | claude-sonnet-4-6 | $$$ |
| 3 | deepseek-v4-pro | $$ |
| 4 | deepseek-v4-flash | $ |
```

All 9 lenses fired (none skipped). Premium split: 0 premium (gpt-5/opus), 4 mid-tier (deepseek-v4-pro), 5 cheap (deepseek-v4-flash). No `KeyError`, `fallback`, or `static` errors in critique dispatch messages.

---

## 3. BLOCKERS / STALLS / RETRIES

**COUNT: 10 retry/resume hits in execution agent messages. All are boilerplate from the WRITE ACCESS CONTRACT — not actual retries.**

The phrase "retry with a different invocation" appears in the standard megaplan harness prompt injected into every subagent session:
```
rollout-...22-29-56...jsonl (via jq): "If a single shell command unexpectedly fails,
retry with a different invocation before concluding the environment is restricted."
```

No `timeout`, `SIGKILL`, `heartbeat`, `stall`, `max_blocked`, or `resume` events found in execution files. No actual retry events triggered.

---

## 4. ERRORS

**COUNT: 0 real runtime errors. All 796 raw grep hits for "Error/Exception/Traceback/failed" are Python source code being read/displayed — not execution failures.**

The "error" matches in function_call_output are from reading source files:
```
rollout-...22-29-56...jsonl (function_call_output): "except TypeError:"
rollout-...22-29-56...jsonl (function_call_output): "raise ValueError(...)"
rollout-...22-29-56...jsonl (function_call_output): "with pytest.raises(LookupError):"
```

No `Traceback` (Python stack trace format) found in any agent message or tool output. The execution completed without runtime errors.

---

## 5. MODELS / TIER USED

**COUNT: 80 total turns across all 18 relevant files.**

| Model | Turns | Tier | Role |
|-------|-------|------|------|
| gpt-5.5 | 78 | Premium ($$$$) | Plan, critique dispatch, gate, review |
| gpt-5.4 | 2 | Premium ($$$) | Execution (both commits) |

Critique subagent models (from lens assignment, not turn_context):
- deepseek-v4-pro: 4 lenses (mid-tier, $$)
- deepseek-v4-flash: 5 lenses (cheap, $)

All sessions use `model_provider: "openai"` (from session_meta). No Claude, Opus, Sonnet, Haiku, Kimi, o3, or o4 sessions in this milestone — the hits from the raw grep were from the critic model roster text and CLAUDE.md references in the repo, not from actual agent sessions.

---

## 6. TOKEN / COST SIGNALS

**COUNT: 1,351 token_count events across all relevant files. Cumulative maximum: 3,848,535 total tokens.**

Final cumulative from the second execution file:
```
rollout-...22-47-30...jsonl (token_count):
  input_tokens: 3,837,562
  cached_input_tokens: 3,679,872  (95.9% cache rate)
  output_tokens: 10,973
  reasoning_output_tokens: 2,126
  total_tokens: 3,848,535
  model_context_window: 258,400
```

No cost dollar amounts found in logs. The 95.9% cache hit rate means the massive system prompt (~95K tokens) was amortized across turns. Rate limits: 8% of 5-hour window, 78% of weekly window used (pro plan).

---

## 7. REPEATED CONTEXT / WASTE

**COUNT: The megaplan harness prompt (~95K tokens) was included in every session_meta line 1 (all 18 files). Plan text re-sent 21 times (11 in the 22:29 file, 10 in the 22:47 file).**

The full plan (identical ~3K-word markdown) appears verbatim in both execution sessions and multiple critique dispatches. This is by design — the megaplan harness injects the complete plan into each execution step's prompt. No evidence of the agent re-reading files it had already read within a single turn.

The `re-done work` grep produced only false positives from system instructions (e.g., "do not restart from scratch", "resume" boilerplate).

---

## 8. CONFUSION

**COUNT: No execution confusion by the M5d executor itself. However, the PLAN contained two factual errors that were flagged by critique lenses:**

Evidence from critique feedback (DEBT findings) in execution context:
```
rollout-...22-47-30...jsonl (via jq): "factual error: plan step 7.2 says 'create
tests/test_gate.py because no dedicated gate test file exists' but tests/test_gate.py
exists as a 1303-line file with extensive gate tests."

rollout-...22-47-30...jsonl (via jq): "plan says 'tests/test_execute.py does not exist.
either create tests/test_execute.py...' but tests/test_execute.py exists as a 4004-line
file with 321 references to megaplan."
```

These are plan-quality issues (not execution confusion). The executor appears to have processed the critique and proceeded — the findings were about OTHER plans/milestones being cross-referenced, not about M5d's own files. No wrong-file edits, contradictions, or looping observed in the M5d execution.

---

## 9. WALL-CLOCK

**Earliest timestamp:** `2026-05-27T19:06:26.192Z` (rollout-...21-06-25..., the plan session)
**Latest timestamp:** `2026-05-28T20:46:19.332Z` (rollout-...22-37-53..., the 10-turn review phase)
**Duration:** ~25h 40min total

**Execution-only window** (2 execution files):
- File 1 (22:29): 2026-05-27T20:29:56Z – 2026-05-27T20:39:48Z (~10 min)
- File 2 (22:47): 2026-05-27T20:47:30Z – 2026-05-27T20:55:49Z (~8 min)
- Combined execution: ~26 minutes

**Overnight gap:** The gate/review file (21:59, 54 turns) extends to 2026-05-28T20:22 UTC, and the review file (22:37, 10 turns) extends to 2026-05-28T20:46 UTC. This means the pipeline spent ~23.5 hours in the review/gate phase across an overnight boundary, with execution completing in ~26 minutes the following evening.

---

## RAW SUMMARY

- **Rounds:** Plan → 9-lens critique (13 subagents) → gate → review → 2 execution turns. Zero rework cycles.
- **Retries:** 0 real retries. 10 false-positive hits from harness boilerplate.
- **Errors:** 0 runtime errors. All "Error/Exception" hits are Python source code in tool output.
- **Model split:** 78 GPT-5.5 (planning/review) + 2 GPT-5.4 (execution). Critique: 5× deepseek-v4-flash + 4× deepseek-v4-pro. 0 Claude/Opus/Kimi sessions.
- **Duration:** ~25.5h total (overnight review gap), ~26 min execution. 3.85M tokens at 95.9% cache rate.
