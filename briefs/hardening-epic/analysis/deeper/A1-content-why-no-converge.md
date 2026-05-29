# A1 — Why the M2-store critique loop never converged (content forensics)

**Scope:** M2-store-abstraction critique loop, 9 iterations, hardening worktree, `originator==codex_exec`.
**Sources:** per-iteration codex sessions (one session = one critique round). Plan dir (`.megaplan/plans/m2-store-abstraction-20260525-2003/`) no longer on disk; logs are the only record.

## Round-by-round ledger

Extracted from each round's final `agent_message` (the `critique_output.json` payload: `flags[]`, `verified_flag_ids[]`, `disputed_flag_ids[]`).

| Round | NEW flags raised | Prior flags VERIFIED (closed) | Disputed | Still open after round |
|---|---|---|---|---|
| 1 | 001,002,003,004 | — | — | 001–004 |
| 2 | 005,006 | 001,003,004 | 0 | 002,005,006 |
| 3 | 007,008 | 002,005,006 | 0 | 007,008 |
| 4 | 009,010 | 007,008 | 0 | 009,010 |
| 5 | 011 | 009,010 | 0 | 011 |
| 6 | 012,013 | 011 | 0 | 012,013 |
| 7 | 014,015,016 | 012,013 | 0 | 014,015,016 |
| 8 | 017 | 014,015,016 | 0 | 017 |
| 9 | — | 017 | 0 | (clean) |

Session map: R1 `20-07-28`, R2 `20-16-06`, R3 `20-21-25`, R4 `20-28-22`, R5 `20-35-53`, R6 `20-42-42`, R7 `20-49-26`, R8 `20-57-28`, R9 `21-04-24`.

**Key structural fact:** every round closed exactly the flags the *previous* round opened, then opened a fresh batch. `disputed_flag_ids` is empty in all 9 rounds. Nothing was ever re-opened. The revise step genuinely fixed each flag — convergence-by-attrition only happened in R9 when the new-flag count finally hit zero.

## Flag lineage — two recursive concern-threads

The 17 flags are not 17 independent issues. They are two concerns peeling one layer per round:

**Thread A — "all plan-run `state.json` writers":**
- 001 "misses existing `_core.state` writers" → 005 "conflates loop state.json / `load_plan_from_dir` migration" → 007 "auto.py + chain.py writers not named" → 012 "`_core.state.touch_active_step` worker-liveness writer" → 016 "patch atomicity (lock/CAS) underspecified" → 017 "`bakeoff/merge.py::_rewrite_project_dir` copy-time writer."

**Thread B — "FileStore ticket / codebase identity parity vs DBStore":**
- 002 "FileStore ticket parity underspecified" → 006 "FileStore.root is metadata root not repo root" → 008 "null `codebase_id` frontmatter → DB-shaped Ticket" → 009 "FileStore can't persist `root_commit_sha`" → 010 "MultiStore DBStore casts in `tickets/core.py`" → 011 "missing `default_branch`" → 013 "`root_commit_sha=None` / `unknown/unknown` collision" → 014 "`is_cloud_store` gating conflict" → 015 "no-origin owner/name fallback."

(003 input-validation, 004 MultiStore routing — closed early, R2/R2.)

Each child flag is reachable only *after* the parent revision lands: e.g. 017 (`bakeoff/merge.py`) could only be flagged once R8's revision had already routed auto.py/chain.py/touch_active_step through the shared writer and the critic re-ran its `rg` sweep one module wider (R9 scope check: "Re-ran the state-writer search across … workers, loop, **and bakeoff/merge.py**").

## Classification of every post-R1 flag

| Flag | Class | Why |
|---|---|---|
| 005,006 | **(a) under-coverage** | adjacent writer/path R1 didn't enumerate |
| 007,008 | **(a) under-coverage** | auto.py/chain.py writers, null-codebase_id mapping — found by re-running grep wider |
| 009,010 | **(a) under-coverage** | `root_commit_sha`/MultiStore-cast surface R1–3 never inspected |
| 011 | **(a) under-coverage** | `default_branch` arg in same `upsert_codebase` call already in scope |
| 012 | **(a) under-coverage** | `touch_active_step` — another existing writer |
| 013 | **(b)+(a) revise-exposed** | R5's `_ensure_codebase` revision *introduced* the `root_commit_sha=None`/`unknown` fallback; R6 flagged the collision it created |
| 014 | **(a) under-coverage** | `is_cloud_store` gating was always there |
| 015 | **(a) under-coverage** | no-origin fallback path |
| 016 | **(a) under-coverage** | atomicity of the shared writer the plan was building |
| 017 | **(a) under-coverage** | last unswept module (`bakeoff/merge.py`) |

**No (c) re-litigation** (zero disputed, zero re-opened IDs). **No (d) lens rotation** as a *cause*: the same ~9 checks (`issue_hints, correctness, scope, all_locations, callers, conventions, verification, criteria_quality, prerequisite_ordering`) ran every round; new flags came overwhelmingly from `scope` / `all_locations` finding *one more code location*, not from a check that hadn't run. Only **013** is meaningfully (b).

## Verdict

1. **Did R1 under-cover? YES — decisively.** R1 raised only 4 flags and never enumerated the full writer set or the FileStore/DBStore parity surface. Its own check text admits it only "Validated JSON and confirmed 9 populated checks" as *evidence* — i.e. R1 spent its budget confirming the output was well-formed, not exhaustively sweeping callers. (Cf. the recurring log note that earlier "critique iterations … focused on test_init_plan.py and test_verifiability.py but missed test_gate.py" — a known sampling-coverage gap.) The plan touched a large multi-store surface (`_core.state`, `_pipeline`, `PlanRepository`, `auto.py`, `chain.py`, `loop`, `workers`, `bakeoff`, plus `Store/DBStore/FileStore/MultiStore` ticket+codebase methods) that one pass could not fully traverse.
2. **Did revise keep introducing problems?** Almost never — only **1 of 16** post-R1 flags (013) was revise-introduced. Not a moving target.
3. **Was the critic non-deterministic / re-litigating?** **No.** Zero disputes, zero re-opens; each round verified the prior fix cleanly.
4. **Dominant cause:** **iterative scope-crawl under-coverage.** Each round's `scope`/`all_locations` lens re-ran its `rg` sweep across one-more module and found the next adjacent writer or parity gap in two long dependency chains. Because the critic discovered the surface incrementally (and the loop had no "enumerate ALL writers up front" gate), convergence was rate-limited to ~1 peeled layer per round, producing monotonic FLAG accretion 001→017 over 9 rounds rather than a one-shot complete critique.
