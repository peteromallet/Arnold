# C1 — Pipeline executor single-path validation

Validated against CURRENT code 2026-05-28 (brief dated 2026-05-23; line cites drifted).
Files read: `megaplan/_pipeline/executor.py`, `override.py`, `runtime.py`, `resume.py`,
`registry.py`, `run_cli.py`; cross-checked `megaplan/cli/__init__.py`, `megaplan/auto.py`.

Note on drift: brief's cites (`run_pipeline ~212`, `run_pipeline_with_policy ~308`,
`run_pipeline_by_name ~205`) are essentially still accurate — `run_pipeline` is at
executor.py:212, `run_pipeline_with_policy` at executor.py:308, `run_pipeline_by_name`
at registry.py:205. Cites did NOT meaningfully drift for the executor itself.

---

## Claim 1 — `run_pipeline_with_policy` DROPS the override-edge dispatch. **CONFIRMED.**

`run_pipeline` dispatch block (executor.py:273-305):

```python
from megaplan._pipeline.override import find_override_edge

edge = None
rec = None
if result.verdict is not None and result.verdict.override is not None:
    edge = find_override_edge(node.edges, result.verdict.override)
if edge is None and result.verdict is not None and result.verdict.recommendation is not None:
    rec = result.verdict.recommendation
    edge = next((e for e in node.edges if e.kind == "gate" and e.recommendation == rec), None)
if edge is None:
    edge = next((e for e in node.edges if e.kind == "normal" and e.label == result.next), None)
...
```

`run_pipeline_with_policy` dispatch block (executor.py:379-407):

```python
edge = None
rec = None
if result.verdict is not None and result.verdict.recommendation is not None:
    rec = result.verdict.recommendation
    edge = next((e for e in node.edges if e.kind == "gate" and e.recommendation == rec), None)
    # Apply escalate policy when the gate emits "escalate".
    if rec == "escalate" and edge is None:
        resolution = policy.escalate.resolve(node.name)
        if resolution == "force_proceed":
            edge = next((e for e in node.edges if e.kind == "gate" and e.recommendation == "proceed"), None)
if edge is None:
    edge = next((e for e in node.edges if e.kind == "normal" and e.label == result.next), None)
...
```

There is NO `import find_override_edge`, NO `verdict.override` check, and NO `kind=="override"`
match in the policy variant. A Step that returns `verdict.override` (the first-class override
edge mechanism — `override force-proceed/abort/replan/add-note`, see override.py:1-48) is silently
ignored: dispatch falls straight through to the `recommendation` then `normal`/`result.next`
branches. If none match, it raises `LookupError` (executor.py:400-404). So override edges are a
true F2 blocker for unifying on the policy path.

## Claim 2 — EscalatePolicy `"abort"` does no edge dispatch. **CONFIRMED.**

`EscalatePolicy.resolve` (runtime.py:92-101) returns the literal string `"abort"` for mode=abort
and `"force_proceed"` for mode=force-proceed. In the executor, ONLY `"force_proceed"` is consumed
(executor.py:388-394): `if resolution == "force_proceed": edge = ...proceed`. The return value
`"abort"` is never compared to anything — `resolution` is computed and then dropped on the abort
path. After the escalate block, control falls through to the `normal`/`result.next` fallback; if
no edge matches it raises `LookupError`, otherwise it follows whatever the gate's `result.next`
happened to be. There is no abort termination, no `halt_reason="aborted"`, no edge dispatch for
abort. Dead branch.

## Claim 3 — `ContextRetry` / `BlockedRetry` are DEAD CODE. **CONFIRMED.**

`ContextRetry` (runtime.py:104-122) and `BlockedRetry` (runtime.py:125-142) define `should_retry(...)`.
Neither `should_retry` is ever called anywhere in `megaplan/` (grep: only the class defs + the
`RuntimePolicy` field defaults at runtime.py:157-158 and `policy_from_cli_args` construction at
184-185). The executor (`run_pipeline_with_policy`) consults only `policy.stall`,
`policy.cost`, and `policy.escalate` (executor.py:368-394) — it never references
`policy.context_retry` or `policy.blocked_retry`. The `auto.py` hits for
`context_retry_count`/`blocked_retry_count` (auto.py:1099-2209) are the LEGACY loop's own local
integer counters, NOT the dataclass policies — they share a name but are unrelated code. So the
two classes are instantiated but their behavior is never dispatched: dead code.

## Claim 4 — NO per-stage `ResumeCursor` persistence in the executor. **CONFIRMED.**

`ResumeCursor` (resume.py:35-87) is fully implemented (load/save/with_payload) and its docstring
even shows the intended pattern `ResumeCursor(stage=node.name).save(plan_dir)` "After each stage"
(resume.py:16-17). But grep shows `ResumeCursor` is referenced ONLY inside resume.py — never
imported or called by executor.py, registry.py, run_cli.py, cli/__init__.py, or auto.py. Neither
`run_pipeline` nor `run_pipeline_with_policy` writes a resume cursor between stages. The only
resume mechanism the executor supports is the human-gate pause: `_pipeline_paused` →
`halt_reason="awaiting_user"` (executor.py:262-264, 374-377), and re-entry is driven externally
by `with_entry(pipeline, paused_stage)` in run_cli.py:313-314 / cli/__init__.py:922. There is no
mid-pipeline crash-resume cursor. Confirmed.

## Claim 5 — First-match edge dispatch can't disambiguate gate self-loops. **CONFIRMED (by design).**

Both dispatchers select edges with `next(... , None)` — first match wins — keyed on
`(kind, recommendation)` or `(kind, label)`. There is no per-iteration counter, attempt index, or
ResumeCursor payload feeding the selection. If a gate stage has two `kind="gate"` edges with the
SAME `recommendation` (e.g. an iterate self-loop edge and a distinct iterate edge), `next()` always
returns the first, so they cannot be disambiguated by iteration count. Combined with Claim 4 (no
cursor), the executor has no state to break the tie. Confirmed.

## Claim 6 — Production wiring + env gating. **CONFIRMED, with an important nuance.**

- `megaplan run <name>` (run_cli.py `cli_run`/`_run_pipeline`) imports and calls **bare
  `run_pipeline`** (run_cli.py:171, 335). NOT the policy variant.
- `megaplan` human-gate resume (cli/__init__.py:920-960) also calls **bare `run_pipeline`**.
- `run_pipeline_by_name` (registry.py:205-246) is the ONLY caller of `run_pipeline_with_policy`
  (registry.py:244), and only when a `policy=` kwarg is passed. But grep shows
  `run_pipeline_by_name` has **zero production callers** — it is invoked only by tests
  (`test_pipeline_registry.py`, `test_pipeline_scoped_prompts.py`).
- `policy_from_cli_args` / `RuntimePolicy` are referenced ONLY by tests
  (`test_pipeline_runtime_e2e.py`, `test_auto_pipeline_runtime.py`, etc.) — never by `auto.py` or
  any CLI handler.
- `megaplan auto` (`run_auto`, auto.py:2410) runs its OWN legacy phase loop (auto.py:309 `while True`
  + `current_state` machine). It does NOT import `_pipeline.executor`, `RuntimePolicy`, or
  `run_pipeline_with_policy` at all.
- The env flag exists: `pipeline_runtime_enabled()` reads `MEGAPLAN_PIPELINE_AUTO` (default "0",
  runtime.py:191-199). But grep shows `pipeline_runtime_enabled()` has **no callers** — the flag is
  never checked anywhere. The docstring claim "MEGAPLAN_PIPELINE_AUTO=1 flips the dispatch to
  run_pipeline_with_policy" (runtime.py:9-12) is **aspirational / STALE**: nothing reads it.

So: `run_pipeline_with_policy` is gated behind a flag that is never read AND behind an entry point
(`run_pipeline_by_name`) with no production callers. In production today the policy path is
**completely dead** — `megaplan auto` uses the legacy loop; `megaplan run` uses bare `run_pipeline`.

---

## ASSESSMENT — single-path readiness

The brief's "single execution path" is NOT close. There are TWO independent execution engines in
production: (1) the legacy `auto.py` state-machine loop (what `megaplan auto` actually runs), and
(2) the `_pipeline` executor's bare `run_pipeline` (what `megaplan run` runs). The policy variant
is a third, dead, partially-built engine. Unifying "every flow enters run_pipeline /
run_pipeline_with_policy" requires first porting `megaplan auto`'s entire phase machine onto the
pipeline executor — that work is essentially not started.

**Do NOT unify on `run_pipeline_with_policy` as-is.** It is strictly a SUBSET of `run_pipeline`'s
dispatch: it drops override edges (Claim 1) and adds only stall/cost/escalate observation plus a
half-wired escalate branch whose `"abort"` return is dead (Claim 2). Merging the two functions
first is the sound move: take `run_pipeline`'s full dispatch (override → gate → normal) as the
canonical block, and inject the policy hooks as optional `policy=None` parameters. That gives one
function with correct edge semantics AND optional runtime guards — eliminating the subset-drift
trap where the "advanced" path quietly loses override capability.

Realistic effort to a SAFE single path:
- **Merge the two executor functions** (override-complete dispatch + optional policy hooks): small,
  ~1 day, low risk — both bodies are nearly identical and well-tested.
- **Wire context/blocked retry** (Claim 3) into the merged dispatch: medium — the dead classes need
  a phase_result signal the pipeline Steps don't currently emit in a uniform shape.
- **Add per-stage ResumeCursor persistence** (Claim 4) + self-loop disambiguation (Claim 5):
  medium — needs a cursor write per stage and an attempt-indexed edge selector.
- **Port `auto.py`'s state machine onto the executor** (the actual "single path"): LARGE,
  multi-day — this is the real cost and the real risk. `auto.py` is ~2500 lines of recovery,
  blocked-retry, escalate, human-verify, and resume logic that the pipeline executor does not yet
  replicate.

**Real risk:** the policy path is dead and untested-in-production, so any flip to it (e.g. finally
reading `MEGAPLAN_PIPELINE_AUTO`) would expose users to the override-edge drop and the abort dead
branch on day one. The two engines have diverged silently; treat parity as unproven until `auto.py`
behaviors are characterized against the pipeline path.

**Unknown-unknown tripped over:** the brief frames `run_pipeline_with_policy` as the candidate
single path, but the genuinely production-critical engine is `auto.py`'s legacy loop — which lives
ENTIRELY outside `_pipeline/` and never touches the executor. The hard part of "single path" isn't
choosing between the two executor functions; it's that the most-used flow (`megaplan auto`) isn't
on the pipeline executor at all. Any unification estimate that ignores `auto.py` is off by an order
of magnitude.
