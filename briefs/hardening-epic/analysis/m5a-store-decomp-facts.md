# M5a Store Decomposition — Forensic Facts

**Milestone:** `m5a-store-decomp`  
**Plan:** `m5a-store-decomposition-20260527-1314`  
**Relevant log files:** 5 of 11 in manifest (6 unrelated sessions excluded)  
**Extraction method:** Python/jq over 835 JSONL records across 5 files

---

## 1. REVISION LOOPS

**COUNT: 3 review rounds, all `needs_rework`. No approve/accept verdict reached.**

The final session (`15-11-26`) was a dedicated review turn. Three sequential assistant messages each produced a review verdict:

- `rollout-...15-11-26...jsonl:10` — `review_verdict: "needs_rework"`, criteria: `"Review not yet performed."`
- `rollout-...15-11-26...jsonl:13` — `review_verdict: "needs_rework"`, criteria: `"Review is in progress."`
- `rollout-...15-11-26...jsonl:35-36` — `review_verdict: "needs_rework"`, full verdict with 10 task verdicts (T1–T9 pass, T10 fails)

Evidence (final review, line 36):
```
"review_verdict":"needs_rework"
"pre_check_flags":[{"id":"PRECHECK-DIFF_SIZE_SANITY","detail":"Diff size looks larger than expected: changed_lines=15150, expected≈10, ratio=1515.00, files=112, hunks=294.","severity":"significant"}]
```
Task verdict T10:
```
"T10: Needs rework. Focused store and golden checks pass, but full pytest still has 6 non-DB failures, so the must criterion is not satisfied."
```

No `APPROVE`/`REJECT`/`ITERATE` in assistant text. The earlier sessions (planning + 3 execution sessions) had no review cycles — they were plan→execute→execute→execute→review.

**Review rounds total: 1 review session with 3 progressive verdict updates, all `needs_rework`.**

---

## 2. CRITIQUE

**COUNT: 3 mentions of "critique," all in the final review session's agent message. No critique invocations, no critique model runs, no fallbacks, no errors.**

The word "critique" appears only in the final review verdict text:
```
rollout-...15-11-26...jsonl:35 [agent_message]: "...Store compatibility, schema aliasing, slice sizing, and critique flags are addressed."
rollout-...15-11-26...jsonl:36 [assistant]: "...Store compatibility, schema aliasing, slice sizing, and critique flags are addressed."
rollout-...15-11-26...jsonl:38 [task_complete]: "...Store compatibility, schema aliasing, slice sizing, and critique flags are addressed."
```

These are all the same text in three different event channels. "critique flags" refers to the review's own flag system, not a separate critique model invocation.

**Critique fallbacks/errors: NONE FOUND** — grep for `fallback|KeyError|static` in assistant+event text returned 0 matches.

---

## 3. BLOCKERS / STALLS / RETRIES

**COUNT: 0 actual blockers, stalls, or retries. Mentions are system-prompt boilerplate only.**

Two matches for `retry`, both in the user_message system prompt:
```
rollout-...13-14-02...jsonl:7 [user_message]: "...If a single shell command unexpectedly fails, retry with a different invocation before concluding..."
rollout-...15-11-26...jsonl:7 [user_message]: same boilerplate
```

No `blocked`, `stall`, `idle`, `timeout`, `SIGKILL`, `resume`, `max_blocked`, `heartbeat`, `no output` found in assistant or event text (beyond system prompt skill descriptions).

**5 task_started + 5 task_complete events — all 5 sessions completed without interruption.**

---

## 4. ERRORS

**COUNT: 0 error event_msgs. 3 error mentions in assistant text — all referencing pre-existing unrelated test failures.**

The assistant mentions test failures in execution summaries:

- `rollout-...14-31-29...jsonl:233`: `"...finished with 3023 passed, 28 skipped, 8 failed; those 8 failures match the unrelated cloud/config/review/worker..."` 
- `rollout-...14-03-38...jsonl:220`: `"...full pytest run ended with the same 8 unrelated failures already noted in prior batch context."`
- `rollout-...15-11-26...jsonl:36`: `"...full pytest still has 6 non-DB failures..."`

**Distinct error signatures: 1** — the cloud/config/review/worker test failures are pre-existing, not caused by this milestone. No `Traceback`, `Exception`, `raise`, or `failed` in tool-call outputs linked to the decomposition work.

---

## 5. MODELS / TIER USED

**COUNT: 5 turns, 2 models, all premium (GPT-5 family).**

| Model | Turns | Effort | Sessions |
|-------|-------|--------|----------|
| `gpt-5.5` | 2 | high (planning), low (review) | Session 1 (13-14-02), Session 5 (15-11-26) |
| `gpt-5.4` | 3 | medium (execution) | Sessions 2-4 (13-45-06, 14-03-38, 14-31-29) |

**All sessions:** provider=`openai`, base model hint=`GPT-5`. No DeepSeek, Kimi, Claude, o3, o4, Opus, Sonnet, or Haiku used. **100% premium tier.**

Evidence:
```
turn_context models: {'gpt-5.5': 2, 'gpt-5.4': 3}
session_meta model_provider: openai (all 5 sessions)
```

---

## 6. TOKEN / COST SIGNALS

**COUNT: 167 token_count events across 5 sessions. Cumulative totals (last event per session):**

| Session | Input Tokens | Cached Input | Output Tokens | Reasoning | Total Tokens |
|---------|-------------|-------------|---------------|-----------|-------------|
| Planning (13-14) | 543,424 | 430,464 | 8,360 | 2,056 | 551,784 |
| FileStore exec (13-45) | 5,677,011 | 5,199,360 | 23,149 | 10,624 | 5,700,160 |
| DBStore exec (14-03) | 5,271,594 | 4,413,952 | 29,410 | 8,418 | 5,301,004 |
| EpicSummary (14-31) | 3,906,443 | 3,805,312 | 7,632 | 1,798 | 3,914,075 |
| Review (15-11) | 226,128 | 146,048 | 4,459 | 1,052 | 230,587 |
| **TOTAL** | **15,624,600** | **13,995,136** | **73,010** | **23,948** | **15,697,610** |

**Cache hit rate: ~89.6%** (14.0M cached of 15.6M input). No explicit cost/dollar figures in logs.

Sample token event structure:
```
{"type":"token_count","info":{"total_token_usage":{"input_tokens":33632,"cached_input_tokens":2432,"output_tokens":657,"reasoning_output_tokens":295,"total_tokens":34289},"model_context_window":258400}}
```

---

## 7. REPEATED CONTEXT / WASTE

**Developer messages:** 3 unique hashes across 5 sessions (~23K chars each). Sessions 1+2 shared one hash; sessions 4+5 shared another; session 3 had a unique variant. Roughly 40% duplication of the ~23K system prompt.

**User messages grew monotonically** as context accumulated:
- Session 1 (planning): 11,117 chars
- Session 2 (FileStore): 48,569 chars  
- Session 3 (DBStore): 52,768 chars
- Session 4 (EpicSummary): 57,870 chars
- Session 5 (review): 155,703 chars

Each execution session re-sent the full milestone brief + accumulated plan/status context. The review session ballooned to 155K chars because it included the full prior execution outputs.

**Tool call pattern:** 146 `exec_command` + 81 `write_stdin` + 6 `apply_patch` calls. No evidence of redoing work — each session built linearly on the prior one (plan → FileStore decomp → DBStore decomp → EpicSummary collapse → review).

---

## 8. CONFUSION

**COUNT: 1 weak signal, no clear confusion events.**

The single match for confusion patterns is a file-reference mention of "revert" in the planning output:
```
rollout-...13-14-02...jsonl:93: "...epic CRUD, list/search, body, snapshots, revert..."
```
This is describing existing store method categories, not an agent correcting itself.

**No wrong-file edits, no self-contradiction, no action loops, no scope misreadings detected** in assistant messages or event logs.

---

## 9. WALL CLOCK

**Earliest timestamp:** `2026-05-27T11:14:02.611Z` (Session 1, planning)  
**Latest timestamp:** `2026-05-27T13:13:25.181Z` (Session 5, review)  
**Duration: 1 hour 59 minutes** (11:14 → 13:13 UTC)

Per-session spans (UTC):
| Session | Start | End | Duration |
|---------|-------|-----|----------|
| Planning | 11:14:02 | 11:18:52 | ~4m 50s |
| FileStore exec | 11:45:06 | 12:02:36 | ~17m 30s |
| DBStore exec | 12:03:38 | 12:23:17 | ~19m 39s |
| EpicSummary | 12:31:29 | 12:40:05 | ~8m 36s |
| Review | 13:11:26 | 13:13:25 | ~1m 59s |

**Gap between sessions 4 and 5:** ~31 minutes (12:40 → 13:11). No overnight gaps. All within the stated time window.

---

## RAW SUMMARY

- **Review rounds:** 1 review session, 3 progressive verdict updates, all `needs_rework` (T10 failing on 6 pre-existing test failures)
- **Retries/resumes:** 0
- **Errors attributable to milestone:** 0 (all test failures pre-existing cloud/config/review/worker)
- **Model split:** 100% GPT-5 premium (gpt-5.5 × 2 turns, gpt-5.4 × 3 turns); no cheap models used
- **Duration:** 1h 59m wall clock (11:14–13:13 UTC), ~15.7M tokens, 89.6% cache hit rate
