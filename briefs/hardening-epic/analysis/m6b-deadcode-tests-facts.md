# M6b-deadcode-tests — Forensic Log Extraction

**Plan:** `m6b-dead-code-test-hygiene-20260528-0043`
**Time window:** 2026-05-27T22:43:32 → 2026-05-28T12:06:02 UTC
**Relevant files:** 5 of 20 manifest files (rest were unrelated Codex sessions in other repos)
**Total log lines:** 2,288 across 5 files (main session: 1,733 lines)

---

## 1. REVISION LOOPS

**COUNT:** 2 `revise`, 2 `tiebreaker` mentions in agent narrative. Zero explicit review→rework→re-review cycles observed in the Codex session logs.

The agent messages mentioning these terms are from the megaplan source code being merged (the `hardening-epic` merge), not from an active megaplan review loop:
- `F4:770` — "tiebreaker trigger" listed among failing test clusters during validation
- `F1:42` — Plan document mentions "tiebreaker" phases as part of megaplan pipeline source code

The Codex agent itself did not go through megaplan's plan→critique→revise→gate→execute pipeline. It worked directly on the hardening merge (resolving merge conflicts, running tests, fixing failures). No explicit "APPROVE"/"REJECT" verdicts or iterative rework commands found.

**Evidence:**
```
F4:770: "...Shannon idle timeout, tickets search/CLI, and tiebreaker trigger. I'm waiting for the complete failure report..."
F1:42: (plan document containing tiebreaker phase descriptions in megaplan source code)
```

---

## 2. CRITIQUE

**COUNT (agent messages):** 68 `critique`, 26 `critique_evaluator`, 16 `adaptive-critique`
**COUNT (all content):** 349 lines in F4, 29 in F3

Critique was the *subject* of work, not an active runtime service. The agent merged the `hardening-epic` branch which refactored `megaplan/handlers/critique.py` and the adaptive critique evaluator routing. The string `[megaplan] ADAPTIVE CRITIQUE FALLBACK` appears 6 times in F4 but only in `function_call_output` (source code being read/edited). No evidence it fired at runtime. No critique invocation produced action — critique was the code being changed, not a phase being run.

**Evidence:**
```
F4:97: (ADAPTIVE CRITIQUE FALLBACK handler in critique.py merge conflict)
F4:289: (merge conflict in critique.py with hardening-epic markers)
```

---

## 3. BLOCKERS / STALLS / RETRIES

**COUNT (agent messages):** 4 `blocked`, 4 `timeout`, 4 `retry`, 2 `idle`, 2 `resume`
**COUNT (all content):** 536 `timeout`, 231 `blocked`, 218 `resume` — nearly all in megaplan runtime policy source code

No SIGKILL, no resume-from-crash. The 2 retries were dependency installs (`ulid`, `python-dotenv` missing), not agent crashes.

**Evidence:**
```
F4:169: "blocked before collection by a missing local dependency: ModuleNotFoundError: No module named 'ulid'"
F4:227: "uv pip touched uv.lock, so I reverted that"
```

---

## 4. ERRORS

**COUNT (agent messages):** 8 `failed`, 6 `error`, 4 `except`
**COUNT (all content):** 655 `Error`, 444 `raise`, 159 `failed`, 159 `except`, 36 `Exception`, 14 `Traceback`

Most `Error` matches are in source code (`raise CliError`, `except ...Error`). Actual runtime errors were 2 missing dependencies and whitespace cleanup. Final suite: 3088 passed, 29 skipped (green).

**Evidence:**
```
F4:169: "ModuleNotFoundError: No module named 'ulid'"
F4: "3088 passed, 29 skipped"
```

---

## 5. MODELS / TIER USED

**Session model:** All 5 sessions: `"model_provider":"openai"` — GPT-5 via Codex CLI.

**Model mentions in source code (F4, the main session):**

| Model | Mentions | Tier |
|---|---|---|
| claude (various) | 674 | Premium |
| deepseek-v4-pro | 185 | Cheap |
| o3 / o4 | 339 | Premium |
| deepseek-code-quality | 68 | Cheap |
| claude-opus-4-7 | 53 | Premium |
| gpt-5.5 | 52 | Premium |
| claude-opus-4.6 | 42 | Premium |
| kimi | 53 | Cheap |

**Premium vs. Cheap split (source code mentions):** ~1,260 premium vs. ~306 cheap (~80%/20%). These reflect megaplan's model routing config, not the session's model.

**Actual agent model:** GPT-5 (OpenAI/Codex) for all turns.

---

## 6. TOKEN / COST SIGNALS

**Cumulative token totals (last token_count per session):**

| Session | Input | Cached Input | Output | Reasoning | Total |
|---|---|---|---|---|---|
| F3 (01-22-08) | 8,560,276 | 8,387,840 | 26,597 | 9,169 | 8,586,873 |
| F4 (11-49-07) | 39,117,543 | 38,100,736 | 75,870 | 20,254 | 39,193,413 |
| F5 (11-49-59) | 1,893,364 | 1,700,608 | 11,600 | 1,908 | 1,904,964 |
| **Grand total** | **~49.6M** | **~48.2M** | **~114K** | **~31K** | **~49.7M** |

Cache hit rate: ~97% (48.2M / 49.6M input tokens were cached).

`token_count` events: 417 total across all files. `cost_usd` field: 192 occurrences (source code references to `cost_usd` in WorkerResult payloads, not actual billing).

**Evidence:**
```
F3:last: "total_token_usage":{"input_tokens":8560276,"cached_input_tokens":8387840,"output_tokens":26597,"reasoning_output_tokens":9169,"total_tokens":8586873}
F4:last: "total_token_usage":{"input_tokens":39117543,"cached_input_tokens":38100736,"output_tokens":75870,"reasoning_output_tokens":20254,"total_tokens":39193413}
F5:last: "total_token_usage":{"input_tokens":1893364,"cached_input_tokens":1700608,"output_tokens":11600,"reasoning_output_tokens":1908,"total_tokens":1904964}
```

---

## 7. REPEATED CONTEXT / WASTE

**COUNT:** 172 `compact`, 428 `context_window`, 854 `token_usage` mentions — nearly all in source code (megaplan's own context/compaction handling), not agent compactions.

Actual compactions: ~39 mentions across all files (`compaction`/`compacted`). No evidence the same large file was re-sent many turns. The agent re-read files naturally as it iterated on merge conflicts, test failures, and validation.

No sign of the agent re-doing completed work. The work pattern was linear: merge conflicts → install deps → run tests → fix failures → run full suite → green.

**Evidence:**
```
F4: "Collection is now down to one missing optional agent dependency, fire. I'm installing that and rerunning"
F4: "The next missing dependency is python-dotenv, also part of the agent extra. I'm installing the remaining declared agent extra packages in one shot"
```

---

## 8. CONFUSION

**COUNT (agent messages):** 4 `Revert`, 2 `wrong`, 2 `revert`, 2 `accidentally`

No wrong-file edits, no model self-contradiction, no looping on the same action found.

Closest to confusion:
1. **F4:169** — Agent encountered `ModuleNotFoundError: No module named 'ulid'` and correctly identified it needed to check the project's dependency setup rather than installing ad-hoc into the wrong environment.
2. **F4:227** — `uv pip` accidentally touched `uv.lock`, agent reverted it. Intentional cleanup, not confusion.
3. **F4:1026** — Agent noted risk of accidentally deleting unrelated repos sharing `.megaplan-worktrees` parent folder. Correctly separated concerns.

**Evidence:**
```
F4:169: "ModuleNotFoundError: No module named 'ulid'. I'm checking the project's test runner/dependency setup rather than installing ad hoc into the wrong environment."
F4:227: "uv pip touched uv.lock, so I reverted that local test-environment churn."
F4:1026: "a bunch of directories under .megaplan-worktrees that are different repos sharing the parent cleanup folder. I'm separating those so we don't accidentally delete unrelated project work"
```

---

## 9. WALL CLOCK

| Session | Start | End | Duration |
|---|---|---|---|
| F1 (00-43-32) | 22:43:32 | 22:45:17 | 1m 45s |
| F2 (01-02-04) | 23:02:04 | 23:03:03 | 0m 59s |
| F3 (01-22-08) | 23:22:09 | 23:38:36 | 16m 27s |
| F4 (11-49-07) | 09:49:17 | 12:06:02 | 2h 16m 45s |
| F5 (11-49-59) | 09:50:00 | 11:07:38 | 1h 17m 38s |

**Earliest:** 2026-05-27T22:43:32Z
**Latest:** 2026-05-28T12:06:02Z
**Total span:** 13h 22m 30s
**Active work:** ~3h 54m (sum of session durations)

**Long idle gap:** 23:38 → 09:49 = **~10h 11m overnight gap** between evening execution session (F3) and morning working session (F4/F5).

**Task structure:** 14 tasks total (1 in F3, 9 in F4, 2 in F5, plus 2 plan/task-generation sessions F1/F2). 28 final_answer events. 14 user_messages across all sessions.

---

## RAW SUMMARY

- **Review rounds:** 0 (no megaplan critique/revise pipeline active; agent worked directly on merge)
- **Retries:** 2 (dependency installs), no crashes or resumes
- **Errors:** Minimal runtime (dep install gaps, whitespace cleanup); 3088 passed / 29 skipped final suite
- **Model split:** Agent = GPT-5 only; source code discussed 76% premium (claude/opus/gpt-5.5/o3/o4) vs 24% cheap (deepseek/kimi)
- **Duration:** 13h 22m span, ~3h 54m active, 10h 11m overnight idle
- **Tokens:** ~49.7M total (~97% cached), ~$0 cost in log (Codex Pro plan, no usage billing recorded)
