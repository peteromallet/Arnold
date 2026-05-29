# Judgment — milestone m5c-eval-execute

**(a) Milestone verdict:** SUCCESS, but EXPENSIVE. A clean behavior-preserving split of `evaluation.py` + `execute/core.py` landed with self-healed mid-refactor friction and a substantive critique — but ~18.6M premium GPT-5 tokens for a mechanical refactor, plus an `adaptive_critique: true` flag that bought nothing, are the real waste.

**Config (chain.yaml):** vendor `codex`, profile `directed` (directed//high), robustness `full`, depth `high`, `adaptive_critique: true`. Coverage honest: the 6 sessions analyzed are the **orchestration layer** (critique + the premium driving agent's own execute turns running in-process on GPT-5.4/5.5). No separate DeepSeek worker logs exist in this set — and notably, none appear to have been spawned: the driving agent did the refactor itself.

## (b) Seven lenses

| # | Lens | Verdict | Single most concrete evidence |
|---|------|---------|------|
| 1 | Blockers / dead-ends | FINE | 0 stalls/timeouts/SIGKILL/resumes. Only friction: 2 `import megaplan` tracebacks in `6ab1-3068` from the agent's own in-progress `batch.py` extraction (partial circular import via `handlers/shared.py:13 → execute.batch`). Self-fixed in-session (line 104 edits batch.py to drop a stray `configured_timeout_seconds` param). [VERIFIED] |
| 2 | Excessive revision | FINE | 1 critique round, 0 execute→review→rework loops. 8 refactor-caused `test_execute.py` failures appeared transiently mid-split and were green by T16 verify. |
| 3 | Low-value critiques | MINOR | Critique session DID flag real issues (`_compute_execute_scope_drift` callers needed updating → plan step 8 revised; flagged `tests/test_execute.py` path). BUT it hit `jq: error … Cannot index array with string` reading its OWN `critique_output.json:164`, and the structured per-check output is all `flagged: false` boilerplate — the value lives only in prose. Tooling-fragile, costly (1.145M tokens). [VERIFIED] |
| 4 | Model-tier mismatch | SIGNIFICANT | Orchestration ran 6/6 premium GPT-5 (2× gpt-5.5, 4× gpt-5.4). This is a behavior-preserving move-code refactor with greppable seams — exactly what the brief calls "mechanical." The critique + verify turns (read template, run suite, report baseline failures) did not need gpt-5.5. [VERIFIED via per-session `"model"` fields] |
| 5 | Repeated/bloated context | MINOR | Full ~200KB plan (brief + debt registry + success criteria) re-embedded in every session's first user message. Mitigated to near-free by 89–98% cache hits (17.8M of 18.6M cached), but the uncached ~800K is still re-sent plan boilerplate. |
| 6 | Model confusion | FINE | No wrong-file edits or scope drift. The "switched to rg instead of fixing import" in facts is slightly off: agent both fixed batch.py AND switched to rg. Dispatch-adjacent guardrail symbols untouched. |
| 7 | Inefficiency / waste | SIGNIFICANT | ~18.6M tokens + 3h10m wall-clock for a two-file mechanical split. Dominated by premium-tier orchestration, not execute. The 78-min critique→T5 gap and 46-min T8→T11 gap are orchestration dead time. |

**Prior-finding cross-check:** adaptive-critique KeyError→static fallback did NOT reproduce here (0 KeyError, 0 fallback, critique completed). The `critique_evaluator` hits in exec sessions are the unrelated `test_step_schema_filenames_reference_existing_schemas` baseline failure (`critique_evaluator.json` missing from `SCHEMAS`), not runtime adaptive critique. max_blocked_retries, worktree-carry, 900s idle-cap, OpenRouter mis-routing, TIEBREAKER downgrade: none observed.

## (c) Top 3 improvements

**1. Premium model on mechanical refactor — [DRIVING] + [HARNESS]**
- *Problem:* All orchestration ran GPT-5.4/5.5 for a behavior-preserving file split with greppable seams.
- *Root cause:* `directed//high` + `depth: high` in chain.yaml pins the driving/critique/verify turns to the premium tier regardless of how mechanical the milestone is.
- *Fix:* [DRIVING] For pure relocation milestones use `directed//medium` or a cheaper driver; the brief itself labels this "mechanical." [HARNESS] Let robustness `full` keep its gate rigor while routing critique+verify turns (template read, suite run, baseline-diff report) to a cheap tier — split "orchestration tier" from "gate rigor" in the profile.

**2. `adaptive_critique: true` bought nothing but fragility — [HARNESS]**
- *Problem:* Flag set, yet only a single static 9-check critique ran, and it crashed `jq` on its own output file (`critique_output.json:164`, array-vs-dict mismatch).
- *Root cause:* On codex chains adaptive critique is effectively inert (consistent with the known epic-wide silent-static behavior), and the critique template the agent reads/writes has an array shape at line 164 that breaks naive `jq` indexing.
- *Fix:* [HARNESS] Either make `adaptive_critique` actually fire on codex vendor or stop emitting it into chain.yaml so it doesn't imply coverage it isn't delivering; and normalize `critique_output.json` so a flat `.checks[].findings` shape survives `jq` (or have the agent read it with `python -c json.load`, not `jq`).

**3. Mid-refactor circular-import friction is predictable — [HARNESS]**
- *Problem:* `import megaplan` failed twice while `batch.py` was half-extracted (the brief's own open question: "avoid a circular import with core").
- *Root cause:* `handlers/shared.py` imports from `execute.batch` at module load, so any partial extraction transiently breaks the whole package import.
- *Fix:* [HARNESS] Add a refactor-aware preflight/step-edit hint for "split god-file" milestones: extract into the new module first, wire the `__init__` re-export last, and run an import-smoke after each sub-step — turning a runtime traceback into a guided sequence.
