# Root cause: silent done-detection failures

Lens: **silent-failure / done-detection robustness.** Why do abnormal terminations
(zombie sessions, red suite, abandoned plan) produce *no signal*? All citations are
to live source, not the `done`-write path (covered separately).

The meta-irony: the hardening epic's thesis was "make failures LOUD." Every
done-detection seam below instead defaults to **trust + success**.

---

## 1. Zombie sessions — no "did this worker actually do work?" check

A worker is launched via `current_agent.run_conversation(...)` in
`workers/hermes.py:963`, then parsed by `parse_agent_output`. The *only*
abnormal-termination guard is for **literally empty output**:

`workers/hermes.py:994-1007` retries solely when
`exc.code == "worker_parse_error" and "0 chars" in exc.message`.

A zombie that ingested the payload, made **0 tool calls**, and emitted a
template-shaped JSON sails through. The "real content" check is field-shape only:

```python
# workers/hermes.py:493-497  (_has_real_content, non-critique/review branch)
return any(
    (isinstance(v, list) and v) or (isinstance(v, str) and v.strip())
    for k, v in payload.items()
)
```

One filler string passes. **Nothing inspects `len(messages)`, tool-call count, or
`files_changed`** to confirm the session did work. `tool_calls` is only consulted to
*recover* JSON (`hermes.py:530`), never to assert work happened.

The generic delegate path has the same hole: `delegate_tool.py:283-293` derives
`status="completed"` from `completed and summary` — it captures `api_calls`
(`:286`) and builds a `tool_trace` (`:297`) but **never asserts either is
non-empty**. A zombie returning a one-line summary is "completed."

The relaunch-5x came from `auto.py` redispatch (orphan/idle clears around
`auto.py:1396-1443`) firing repeatedly with **no zero-work circuit breaker** — each
relaunch looked like a fresh, legitimate dispatch.

## 2. Red suite — engine never verifies green; it trusts self-report

`finalize.py:495-525` runs the suite **once, to capture a baseline** of pre-existing
failures. Post-execute verification is merely *appended as a task for the executor
agent to self-run*: `finalize.py:335-345` ("re-run until all tests pass") and a
sense-check question `finalize.py:366`. These are prompts, not assertions.

Confirmed absent: `execute.py` has **no** `subprocess`/`pytest` call; `review.py`
has **none either** (grep returned nothing). `review` ingests the executor's
self-reported `commands_run`/verdicts. Execute's terminal outcome is just:

```python
# execute.py:278
outcome = response.get("_phase_outcome", "success")   # defaults to success
```

So execute finishing with a RED suite emits `exit_kind="success"` and nobody re-runs
the tests. There is **no engine-side green-suite assertion anywhere** between execute
finishing and the plan going done.

## 3. Abandonment — clean return == success, no phase-coverage assertion

`drive()` decides terminality purely from the `state` string:

```python
# auto.py:1363-1369
terminal_status = {STATE_DONE: "done", STATE_ABORTED: "aborted", ...}.get(state, state)
log(f"terminal state reached: {state}")
...
return _outcome(terminal_status, final_state=state, ...)   # auto.py:1388
```

There is **no assertion that all phases (plan→finalize→execute→review) actually
ran**. A plan that reaches a done-mapped state after only planning returns
`"done"`. The pipeline executor is the same: `executor.py:262-265` and `:303-304`
treat any `next == "halt"` / `edge.target == "halt"` as success and return — no
"were all expected stages visited?" check. `run_pipeline_with_policy` adds
stall/cost/max-iteration halts (`executor.py:343,370,372`) but still **no
completeness gate** on exit.

---

## Missing fail-loud checks (where each should go)

1. **Zero-work guard.** After `parse_agent_output`, in
   `workers/hermes.py` `_run_attempt` (~`:1010-1039`): for execute, reject when
   `messages` shows 0 assistant tool_calls AND `files_changed` empty. Mirror in
   `delegate_tool.py:288-293`: status "completed" must require `api_calls > 0` (or a
   non-empty `tool_trace`). Add a relaunch circuit breaker in `auto.py` redispatch
   (`:1396-1443`) that escalates after N consecutive zero-work sessions.

2. **Green-suite assertion.** A real engine-run gate after execute (in `review.py`
   or a post-`execute.py:278` step): re-run `baseline_test_command` and hard-fail /
   block if the failure set grew beyond `baseline_test_failures`. Today the only
   suite run is the baseline at `finalize.py:495`.

3. **Phase-coverage assertion.** Before `drive()` returns "done"
   (`auto.py:1363-1394`): assert every required phase emitted a `phase_result.json`
   with a terminal `exit_kind`; treat a done-state with missing phases as `failed`,
   not `done`. Same completeness check belongs at `executor.py:262`/`:303` halt
   returns.

**Meta-irony:** the epic built loud failure *everywhere except its own completion
edge.* Each of the three seams that decide "we're done" defaults to silent success —
exactly the failure class the epic existed to kill.
