# M2-Store Forensic Facts

**Plan**: `m2-store-abstraction-20260525-2003`
**Label**: `m2-store`
**Relevant files**: 32 of 133 manifest files (31 with exact plan name, 1 additional with label)
**Total log size**: 16.7 MB across 32 JSONL session files

---

## 1. REVISION LOOPS

**COUNT**: 650 grep hits across 32 files. Evidence of **2 critique iterations** (iteration 1 + iteration 2), **1 tiebreaker phase**, and multiple plan revisions.

The plan went through: initial plan -> critique round 1 (4 flags: FLAG-M2-001 through FLAG-M2-004) -> revision to plan_v2 -> critique round 2 -> tiebreaker resolution.

```
rollout-2026-05-25T20-07-28-...jsonl:line ~6: "This is critique iteration 2. The template file includes prior findings with their status."
rollout-2026-05-25T20-16-06-...jsonl:line ~88: "Revise context (what changed since the last plan version): Unified diff between plan versions: --- plan_v1.md +++ plan_v2.md"
rollout-2026-05-25T20-07-28-...jsonl:line ~189: "critique_output.json" written with 9 checks, each with prior_findings and status fields ("addressed", "open", "n/a")
```

**Review rounds**: 2 critique rounds + 1 tiebreaker. The first round produced 4 flags; the second round verified 7 prior flags as addressed and raised 2 new flags (FLAG-M2-007, FLAG-M2-008). No evidence of execute->review->rework cycles (this milestone appears to be plan/critique only, not execution).

---

## 2. CRITIQUE

**COUNT**: 381 grep hits. 13 of 32 files directly reference `critique_output.json`.

**Critique invocations**: 2 full rounds (iteration 1 and iteration 2), each producing a critique_output.json file with 9 structured checks (issue_hints, correctness, scope, all_locations, callers, conventions, verification, criteria_quality, prerequisite_ordering).

```
rollout-2026-05-25T20-07-28-...jsonl:line ~6: "Your output template is at: .../critique_output.json. Read this file first — it contains 9 checks..."
rollout-2026-05-25T20-07-28-...jsonl:line ~189: First critique_output completed with FLAG-M2-001 through FLAG-M2-004
rollout-2026-05-25T20-16-06-...jsonl:line ~88: Second critique round verifying prior flags, producing FLAG-M2-007 + FLAG-M2-008
```

**Critique producing NO change**: NONE FOUND. Both rounds produced flagged findings.

**Critique errors/fallbacks**: NONE FOUND. No `KeyError` or `fallback` hits in critique-specific context. The word "fallback" appears 4 times in `resolution_merge_key` function bodies (not critique errors). "static" appears only in unrelated test code.

---

## 3. BLOCKERS / STALLS / RETRIES

**COUNT**: 614 grep hits. Key findings:

- **"blocked"**: Appears in executor recovery code (`_mark_blocked_execute_as_executed`, `_recover_blocked_execute_if_tasks_done`) — these are code patterns being read/analyzed, not actual stalls during this run.
- **"retry"**: Appears 12 times total across contexts like `retry_strategy`, `max_context_retries`, `max_external_retries`, `retry_count` — configuration parameters, not runtime retries.
- **"resume"**: Appears heavily in `ResumeCursor` class references and state machine code being analyzed. The word `resume` appears 351 times in response items.
- **"timeout"**: Appears in `DEFAULT_NON_EXECUTE_TIMEOUT_CAP_SECONDS` and `phase_stale_seconds` references.

```
rollout-2026-05-25T20-21-25-...jsonl:line ~78-79: "execute_result in {'success', 'blocked'}", "_mark_blocked_execute_as_executed"
rollout-2026-05-25T23-37-43-...jsonl: "max_review_rework_cycles", "max_context_retries", "max_external_retries" (configuration constants)
```

**Actual retries/resumes during this run**: NONE FOUND. No evidence of runtime retry events, SIGKILL, or heartbeat failures. These terms appear in code being read/analyzed, not in operational events.

---

## 4. ERRORS

**COUNT**: 731 grep hits. Collapsing repeats yields **35 distinct error signatures** across the 32 files.

Top error types (by occurrence):
| Error | Count |
|---|---|
| UnicodeDecodeError | 396 |
| OSError | 396 |
| StoreError | 355 |
| CliError | 323 |
| ValueError | 320 |
| JSONDecodeError | 270 |
| KeyError | 178 |
| FileNotFoundError | 166 |
| TypeError | 89 |
| RuntimeError | 77 |
| CalledProcessError | 76 |

```
rollout-2026-05-25T21-28-04-...jsonl: "OSError", "JSONDecodeError", "CliError" (27+ matches each)
rollout-2026-05-26T00-04-31-...jsonl: "CliError" (47 matches)
rollout-2026-05-26T00-15-05-...jsonl: "StoreError" (45 matches), "ValueError" (30 matches)
```

**Note**: Most hits are code being read/analyzed (test fixtures, exception handlers, recovery paths), not runtime crashes. High UnicodeDecodeError/OSError counts come from grep matching within base instruction blocks re-sent each session.

---

## 5. MODELS / TIER USED

**COUNT**: 1,679 model-name grep hits across all files.

**Primary execution model**: All 32 sessions use `"model_provider":"openai"` with `"source":"exec"`. The `"model"` field shows:

- **gpt-5.5**: 30 sessions
- **gpt-5.4**: 2 sessions (`rollout-2026-05-25T22-37-41` and `rollout-2026-05-25T23-47-08`)

```
rollout-2026-05-25T20-07-28-...jsonl: "model_provider":"openai", "model":"gpt-5.5"
rollout-2026-05-25T22-37-41-...jsonl: "model":"gpt-5.4"
```

**Premium vs cheap split**: 100% premium (all GPT-5.x via OpenAI). Zero cheap-model sessions. Mentions of "deepseek", "kimi", "claude", "opus", "sonnet" in the logs are from:
- Skill descriptions in the base instruction block (e.g., "subagent-launcher: ... DeepSeek / Kimi / Zhipu hermes subagent")
- Config file references (`deepseek-pro.toml`, `claude.json`)
- No actual cheap-model inference occurred during this milestone.

---

## 6. TOKEN / COST SIGNALS

**COUNT**: 2,625 grep hits. 2,050 `token_count` events across 32 sessions. Each session has cumulative token tracking.

**Aggregate totals** (sum of final `token_count` per session, 64 data points from 32 sessions × 2 event types):
- **Total tokens**: ~89.3 million
- **Input tokens**: ~88.9 million
- **Output tokens**: ~339K
- **Cached input tokens**: ~84.9 million (**95.1% cache hit rate**)
- Model context window: 258,400 (consistent across all sessions)

```
rollout-2026-05-25T20-07-28-...jsonl (final token_count): total_tokens: 334,255 (single session)
rollout-2026-05-25T20-07-28-...jsonl (mid-session): total_tokens: 45,220 → 91,922 → 165,618 → 246,783 → 334,255
```

**Cost signals**: No explicit USD cost data found. Rate limit data shows `"plan_type":"pro"` with primary window usage at 12% and secondary at 58%. No rate-limit hits.

---

## 7. REPEATED CONTEXT / WASTE

**EVIDENCE FOUND**. Every one of the 32 session files begins with the identical massive base instruction block (~400K characters per session), containing:
- Full Codex personality/system prompt
- Complete skills list (~40+ skills with descriptions)
- Frontend guidance rules
- Editing constraints
- Formatting rules

This block is re-transmitted at every new `codex_exec` session. At 95.1% cache hit rate, provider-side caching absorbed most of this, but 32 sessions × ~400K chars = ~12.8 MB of repeated system instructions. No evidence of the agent re-doing completed work.

---

## 8. CONFUSION

Limited evidence in the plan/critique phase. Two observations:

1. **FLAG-M2-001 (scope miss)**: The initial plan missed `_core.state.save_state` and `save_state_merge_meta` as production state.json writers. The critique caught this: *"The plan only names executor, resume, run_cli initialization, and PlanRepository... grep shows additional production writers."* The revision fixed it but the second critique found the fix still incomplete (missed `auto.py` and `chain.py` writers).

2. **FLAG-M2-008 (schema mismatch)**: The plan assumed FileStore tickets could return DB-shaped Ticket models from local frontmatter, but existing local tickets set `codebase_id = None` while the Ticket schema requires `codebase_id: str`. The critique flagged this but it was not resolved — it remained as FLAG-M2-008 after round 2.

3. **Iteration counter ambiguity**: The critique template says "This is critique iteration 2" but also references prior findings as if from iteration 1. No evidence of the model misreading which iteration it was on.

---

## 9. WALL-CLOCK

**Earliest timestamp**: `2026-05-25T18:07:28.949Z` (2026-05-25 2:07 PM EDT)
**Latest timestamp**: `2026-05-26T10:23:09.317Z` (2026-05-26 6:23 AM EDT)

**Duration**: **16 hours 16 minutes** (wall clock), spanning 32 Codex sessions.

**Overnight gap**: NONE. Sessions ran continuously from 18:07 UTC May 25 to 10:23 UTC May 26 with no gap longer than ~9 minutes between sessions. The file at `rollout-2026-05-26T12-20-37` (manifest line 133, file timestamp 12:20 UTC / 8:20 AM EDT) contains the last relevant content at 10:23 UTC, suggesting the harness completed before noon.

---

## RAW SUMMARY

- **Rounds**: 2 critique iterations + 1 tiebreaker = 3 review rounds (plan/critique only, no execute phase)
- **Retries**: 0 runtime retries detected; retry config params mentioned but never triggered
- **Errors**: 35 distinct error type signatures found in analyzed code; 0 confirmed operational failures
- **Model split**: 30 sessions gpt-5.5 + 2 sessions gpt-5.4 = 100% GPT-5 premium tier (0% cheap)
- **Duration**: 16h16m across 32 Codex sessions, 89.3M total tokens, 95% cached
