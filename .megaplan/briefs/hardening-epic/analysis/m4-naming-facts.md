# M4-Naming Forensic Log Extraction

**Plan:** `m4-naming-vocabulary-20260526-1359`
**Window:** 2026-05-26T13:59:00 – 2026-05-27T13:14:00 UTC
**Relevant files:** 17 of 46 manifest entries (2 excluded as unrelated `feat/batching-pl` sessions; 27 had zero m4 signals)
**Wall clock:** 2026-05-26T12:08:06 UTC – 2026-05-26T19:36:49 UTC (7h 28m active; ~5h idle gap 12:54→17:50 UTC)

---

## 1. REVISION LOOPS
**COUNT: 8 review rounds, each with 9 sub-checks = 72 total critique invocations. No execute→review→rework cycles observed — reviews were all pre-execution plan reviews.**

The 8 review sessions are the 12-line files at 14:48, 14:49, 14:51, 14:52, 14:53, 19:50, 20:06, 20:12. Each fires one turn that produces a `selections` array of 9 checks. No `ITERATE`/`REVISE`/`APPROVE`/`REJECT` verdicts appear in the selections — all `verdict` fields are `N/A`, meaning the review output is observational, not gating.

Evidence — `rollout-2026-05-26T14-48-49-...jsonl:9`:
```
{"selections":[
  {"check_id":"issue_hints","critic_model":"deepseek-v4-pro","why":"Needs a final cross-check..."},
  {"check_id":"correctness","critic_model":"gpt-5.5",...},
  {"check_id":"scope","critic_model":"deepseek-v4-pro",...},
  ...
]}
```

**Review rounds total:** 8 (all pre-execution; zero post-execution review loops)

---

## 2. CRITIQUE
**COUNT: 72 critique sub-invocations across 8 review rounds. Zero critique rounds produced zero-action results. Zero critique fallbacks/KeyErrors.**

Critic model distribution across the 72 checks:
- `deepseek-v4-pro`: 32 checks (44%)
- `deepseek-v4-flash`: 15 checks (21%)
- `claude-sonnet-4-6`: 14 checks (19%)
- `gpt-5.5`: 11 checks (15%)

Evidence — `rollout-2026-05-26T14-49-59-...jsonl:9` (claude-sonnet-4-6 dominant round):
```
{"check_id":"issue_hints","critic_model":"claude-sonnet-4-6",...}
{"check_id":"correctness","critic_model":"claude-sonnet-4-6",...}
{"check_id":"scope","critic_model":"claude-sonnet-4-6",...}
```

No `fallback`, `KeyError`, or `static` associated with critique path. All checks had valid `critic_model` assignments.

---

## 3. BLOCKERS / STALLS / RETRIES
**COUNT: ZERO retries, ZERO resume events, ZERO SIGKILL/timeouts.**

No grep matches for `retry`, `resume`, `SIGKILL`, `max_blocked`, or `heartbeat` in the 17 relevant files. The `blocked` matches (163 raw hits) are all from the Codex base instructions text ("never revert...", "if you hit a blocker") and `git status` output — not actual blocker events.

**Idle gap:** 2026-05-26T12:54:22 UTC → 2026-05-26T17:50:55 UTC = **4h 56min** between the last morning review (14:53 local) and first evening review (19:50 local). This appears to be a natural afternoon break, not a stall.

---

## 4. ERRORS
**COUNT: 17 non-zero exit codes. 2 distinct error signatures attributable to m4 work.**

**Distinct signatures:**

| # | Type | Example | File:Line |
|---|------|---------|-----------|
| A | Path miss (`rg: prompts/demos: No such file or directory`) | `rg: prompts: No such file or directory (os error 2)` | `14-08-06:14` |
| B | Missing test file (`sed: tests/test_prompts_shared.py: No such file`) | agent assumed file existed but didn't | `20-30-10:32` |
| C | Pytest test failures (6 tests failed in 21:29 file) | 4 unrelated (cloud preflight/config), 1 `critique_evaluator.json` schema ref, 1 `Critique output failed check validation` | `21-29-54:198` |
| D | `TypeError: _build_gate_carry() got an unexpected keyword argument 'recommendation'` | Directly caused by m4 gate_carry migration work — a verification script used the old API | `21-29-54:27,45` |

Evidence — `rollout-2026-05-26T21-29-54-...jsonl:27`:
```
Traceback (most recent call last):
  File ".../tmp_verify_m4_vocabulary_compat.py", line 37, in <module>
  File ".../tmp_verify_m4_vocabulary_compat.py", line 18, in main
TypeError: _build_gate_carry() got an unexpected keyword argument 'recommendation'
```

Evidence — `rollout-2026-05-26T21-29-54-...jsonl:198` (test failures):
```
FAILED tests/test_workers.py::test_step_schema_filenames_reference_existing_schemas
  AssertionError: Step 'critique_evaluator' references non-existent schema 'critique_evaluator.json'
FAILED tests/test_handle_review_robustness.py::test_handle_review_light_branch_skips_prechecks...
  CliError: Critique output failed check validation: issue_hints, correctness, scope, ...
```

The `critique_evaluator.json` schema error is a pre-existing test failure (not caused by m4). The `TypeError` is a genuine m4-introduced bug: the gate_carry migration renamed the field but the verification script still used the old keyword.

---

## 5. MODELS / TIER USED
**COUNT: 17 sessions. 11 used gpt-5.5 (premium), 6 used gpt-5.4 (premium). Zero cheap-model sessions (no deepseek main agent, no kimi).**

**Main agent model per session:**

| Model | Sessions | Role |
|-------|----------|------|
| `gpt-5.5` | 11 | Planning (14:08), all 8 review rounds, 2 execution (20:07, 20:46) |
| `gpt-5.4` | 6 | Execution (20:23, 20:30, 20:39, 20:56, 21:22, 21:29) |

**Critic models (used within review rounds, NOT as main agents):**

| Model | Checks | Tier |
|-------|--------|------|
| `deepseek-v4-pro` | 32 | Cheap |
| `deepseek-v4-flash` | 15 | Cheap |
| `claude-sonnet-4-6` | 14 | Premium |
| `gpt-5.5` | 11 | Premium |

**Provider:** All 17 sessions via `model_provider: "openai"`.

**Premium/cheap split for main agent:** 17/0 premium — no cheap main-agent runs. Critics are 47 cheap / 25 premium.

Evidence — `turn_context` field from any session_meta:
```
"model":"gpt-5.5"
```

Evidence — review selections, e.g. `14-48-49:9`:
```
"critic_model":"deepseek-v4-pro"
```

---

## 6. TOKEN / COST SIGNALS
**COUNT: 376 turn-level token snapshots across 17 sessions. Cumulative max-input totals below (raw, not deduplicated across sessions).**

| Session | Max Input | Max Output | Max Reasoning |
|---------|-----------|------------|---------------|
| 14:08 (planning) | 564,809 | 8,559 | 2,905 |
| 14:48–14:53 (5 reviews) | ~64,700 each | ~2,800 each | ~515 each |
| 19:50 (review) | 64,638 | 2,839 | 430 |
| 20:06 (review) | 67,714 | 3,033 | 516 |
| 20:07 (exec) | 1,006,158 | 11,362 | 2,551 |
| 20:12 (review) | 43,220 | 4,149 | 516 |
| 20:23 (exec) | 615,284 | 4,792 | 926 |
| 20:30 (exec) | 5,447,719 | 10,874 | 2,367 |
| 20:39 (exec) | 2,599,807 | 7,428 | 1,188 |
| 20:46 (exec) | 4,505,944 | 13,871 | 2,490 |
| 20:56 (exec) | 5,944,221 | 12,391 | 3,816 |
| 21:22 (exec) | 3,304,848 | 6,935 | 1,537 |
| 21:29 (exec) | 3,393,818 | 6,650 | 967 |

**Grand totals (max per session, sum of 17 sessions):**
- Input: 27,881,449 tokens
- Output: 107,190 tokens
- Reasoning: 22,783 tokens

**No cost/usage fields found.** No `cost` or `usage` keys in any log event.

Token snapshots come from `event_msg` type `token_count` — e.g. `14-48-49:11`:
```
"total_token_usage":{"input_tokens":64717,"cached_input_tokens":2432,"output_tokens":2754,"reasoning_output_tokens":510}
```

---

## 7. REPEATED CONTEXT / WASTE
**NONE FOUND — no evidence of identical large blocks re-sent across turns.**

Review sessions (12-line files) each start fresh: session_meta + base_instructions + AGENTS.md + harness prompt + single turn. Identical base instructions are expected (Codex system prompt), not waste. Execution sessions accumulate context naturally via conversation turns. No grep evidence of the same large file content being re-read across multiple sessions.

The agent in 20:46 and 20:56 did invoke `contextminning-subagentmaxxing` (a context-hygiene skill), indicating awareness of context growth:
```
20:46: CMD: sed -n '1,220p' /Users/peteromalley/Documents/poms_skills/contextminning-subagentmaxxing/SKILL.md
```

---

## 8. CONFUSION
**Two minor instances found. No wrong-file edits, no looping on same action, no misreading of scope.**

1. **Wrong path assumption:** Agent ran `rg ... prompts` in `14-08-06:14` — `prompts/` directory didn't exist at that path (`rg: prompts: No such file or directory (os error 2)`). Agent corrected in subsequent command.

2. **Non-existent test file reference:** Agent ran `sed -n '1,220p' tests/test_prompts_shared.py` in `20-30-10:32` — file didn't exist. Agent adjusted and proceeded.

3. **Verification script used old API:** In `21-29-54:27`, agent ran a verification script (`tmp_verify_m4_vocabulary_compat.py`) that called `_build_gate_carry()` with the old `recommendation` kwarg, hitting `TypeError`. This is the agent writing a compat check that didn't account for the rename it had just performed — a consistency failure.

No evidence of: model contradicting itself, looping on the same action, editing wrong files, or misreading the milestone brief scope.

---

## 9. WALL-CLOCK
**Duration:** 2026-05-26T12:08:06 UTC → 2026-05-26T19:36:49 UTC = **7 hours 28 minutes**

**Timeline:**
- 12:08 UTC (14:08 local): Planning session starts
- 12:48–12:54 UTC (14:48–14:54 local): 5 rapid review rounds (~1 min each, ~56s duration per 14:48 file)
- **12:54–17:50 UTC (14:54–19:50 local): 4h 56min idle gap** (afternoon break)
- 17:50–18:12 UTC (19:50–20:12 local): 3 more review rounds
- 18:07–19:36 UTC (20:07–21:36 local): 8 execution sessions, including the main work

**No overnight gap** — all activity on 2026-05-26.

Evidence — earliest: `14-08-06:1` → `"timestamp":"2026-05-26T12:08:06.237Z"`  
Evidence — latest: `21-29-54:tail` → `"timestamp":"2026-05-26T19:36:49.796Z"`

---

## RAW SUMMARY

| Metric | Count |
|--------|-------|
| Review rounds | 8 (72 critique sub-checks) |
| Execute→review→rework cycles | 0 |
| Distinct error signatures (m4-attributable) | 2 (TypeError from gate_carry migration; path-miss self-corrected) |
| Test failures in final run | 6 (1 m4-related: `critique_evaluator.json` schema ref) |
| Main-agent model split | 11 gpt-5.5 / 6 gpt-5.4 (all premium; zero cheap) |
| Total input tokens (sum of session maxes) | 27.9M |
| Wall-clock duration | 7h 28m active + 4h 56m idle gap |
