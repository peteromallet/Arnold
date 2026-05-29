# Delta since brief — pipeline-unification-planning-as-pack

**Brief written:** 2026-05-23. **Delta cut:** 2026-05-28 (HEAD `c493f629`).
**Method:** read brief §10 work breakdown; `git show --stat` on the named commits; verified
current code state of every architectural surface the brief cites.

The post-brief work (hardening-epic + CLI/patterns/execute refactors) was **almost entirely
structural decomposition and hardening of the *legacy* path** — it did NOT advance the unification
itself. The dual-dispatch surface is still fully intact: `COMMAND_HANDLERS` lives (now in
`cli/__init__.py:1014`, dispatched `:1561`), `auto.py` still shells out via `_run_megaplan`
subprocess (`auto.py:238`), `InProcessHandlerStep` still carries its own routing table
(`inprocess_step.py:141 _label_for`, `:192 _gate_next_step`) and 3-key allowlist (`:86`), planning
is still `_BUILTIN_NAMES={"planning"}` (`registry.py:53`). No `HandlerContext`, no
`MEGAPLAN_UNIFIED_DISPATCH`, no `schema_version`, no `Realizer`, no `pipelines/planning/` dir.

But the refactors **moved the furniture the brief planned to move**, so the file-coordinates in the
brief are now largely stale, and a few items got *partially done as a byproduct*.

---

## Per-work-item classification

### Phase 0 — Scaffolding

| Item | Status | Evidence |
|---|---|---|
| Parity gate (`extract_decision_fields` diff, mock-override branch coverage) | **PARTIALLY DONE** | `tests/test_pipeline_parity.py` exists and dual-runs direct `handle_*` vs pipeline (`test_direct_and_pipeline_produce_identical_artifacts:162`), but it is a *single* happy-path test — **no `extract_decision_fields`, no `make_worker_sequence` overrides, no reprompt/downgrade/tiebreaker coverage**. Exactly the §7 caveat. Bulk of Phase 0's value (branch coverage + permanent CI armor) is UNTOUCHED. |
| Discovery-integrity guard (§8) | **UNTOUCHED** | no assertion that `planning` is discoverable/compiles; grep finds nothing. |
| `MEGAPLAN_UNIFIED_DISPATCH` toggle | **UNTOUCHED** | grep finds no toggle, no `dispatch_path` stamp. |

### Body 1 — Foundation

| Item | Status | Evidence |
|---|---|---|
| 1a state-write: handlers stop self-persisting, return full delta | **UNTOUCHED (and got *harder*)** | `save_state_merge_meta(` now at **37 call sites** (was 30 at brief time) across handlers + `execute/timeout.py` + `cli/resolutions.py` + `_core`. The refactors *added* writers. |
| 1a single shared emission hook (phase_result + receipt + history + events) | **PARTIALLY DONE** | `a59e5495` extracted `_emit_receipt` and `_write_gate_json` into `handlers/shared.py`, deduping receipt/gate-artifact emission across `critique/gate/override/review`. This is a *down-payment* on the §6-hazard-2 "single emission hook" — the helper now exists in one place — but it is invoked by handlers, not by a shared executor+CLI hook, and does not cover history/events uniformly. |
| 1a widen `inprocess_step` allowlist to full delta + `schema_version` stamp | **UNTOUCHED** | allowlist still the 3 keys (`inprocess_step.py:86`); no `schema_version` anywhere in state writes. |
| 1b `HandlerContext` + `args_to_hctx` adapter + `__all__` deprecation shims | **UNTOUCHED** | no `HandlerContext`/`args_to_hctx`. `bf7ce72e` instead *added more* `argparse.Namespace`-threaded fields (clarification escape hatch reads `args` in `override`/`plan`), deepening the config-bus debt HandlerContext was meant to kill. |

### Body 2 — Unification

| Item | Status | Evidence |
|---|---|---|
| Pack-ify planning → `pipelines/planning/` | **UNTOUCHED (but de-risked)** | no `pipelines/planning/` dir; `_BUILTIN_NAMES` unchanged. However `6ec0f27e` proved the *pattern* by pack-ifying creative/doc into `steps.py` + `prompts/__init__.py` (creative `steps.py:147 LOC`, doc `steps.py:125`), and shrank `_pipeline/planning.py` 233→122 LOC (now just `compile_planning_pipeline()`). The migration template the brief wanted now exists. |
| Retire `InProcessHandlerStep`; Steps as thin callers of new sig | **UNTOUCHED** | `InProcessHandlerStep` intact with own routing table + allowlist. |
| `prompts/__init__.py` bridge (make dead `prompt_key` live) | **PATTERN ESTABLISHED, planning UNTOUCHED** | `6ec0f27e` + `928e830b` built exactly this `register_pipeline_prompt` bridge for creative/doc and removed prompt shim files, migrating imports to canonical modules. Planning's prompt bridge still unwritten. |
| Export `run_planning()` / `mark_plan_executed()`; rewire `chain.py` off direct `current_state` write | **UNTOUCHED** | no `run_planning`/`mark_plan_executed`; three external writers still bypass. |
| Resume-migration shim (hazard 5) | **UNTOUCHED** | — |
| CLI rewire (phase subcommands → executor) | **UNTOUCHED** | `COMMAND_HANDLERS` still the dispatch (`cli/__init__.py:1561`); `653ee51c` *split* `cli.py` (5217 LOC) into `cli/` package but preserved the dispatch verbatim. |
| `auto.py` in-process rewrite | **UNTOUCHED (and got *bigger*)** | still subprocess (`_run_megaplan:238`); `bf7ce72e` + `6ec0f27e` *added* ~170 LOC to `auto.py` (clarification halt, status plumbing). Still zero direct `test_auto_drive.py`; `test_auto.py` grew but tests features, not the drive() exit-kind matrix. |

### Body 3 — Platform generalisation

| Item | Status | Evidence |
|---|---|---|
| `capabilities` metadata + formalise `patterns.py` as capability library | **PARTIALLY DONE (formalisation only)** | `96b5e66b` split the `patterns.py` god-file (874→~30 LOC façade) into `pattern_topology.py` (`critique_revise_gate_loop`, `phase_zero_gate`, `panel_parallel`, `escalate_if`…), `pattern_dynamic.py` (`dynamic_fanout`, `panel_from_artifact`, consensus), `pattern_joins.py` (votes), `pattern_types.py`. This **delivers the §2.1 "formalise patterns.py as the capability library" goal structurally.** The declarative `capabilities=(...)` tuple key on packs is still UNTOUCHED. |
| Extract engine DAG-runner + `Realizer` interface; refactor execute/ → `CodeRealizer`; mode-agnostic finalize | **PARTIALLY DONE (mechanical split only)** | `6e69814c` split `execute/core.py` (1930→~big drop) into `aggregation.py`, `batch.py` (1529), `merge.py` — the universal-vs-code seam the brief drew in §5 is now **physically cut along nearly the same line**. BUT it is a façade refactor, not a `Realizer` protocol: no `class Realizer`, no `backend_id`, and **`is_prose_mode` branches still live (18 occurrences across `aggregation/batch/merge/timeout`)** — they merely *moved* out of `core.py` into the new modules. So the brief's "~200 LOC of is_prose_mode disappears" is NOT done; the branches were relocated, not eliminated. |
| Promotions (FaultRegistry, DeadlockResolver, intensity dial, receipt schema, versioned-artifact helper); demote 4-verdict taxonomy | **UNTOUCHED** | `faults.py` unchanged; verdict taxonomy still engine-level in `types.py`. |
| Re-home PR #43 as `CodeRealizer` vehicle | **UNTOUCHED** | no sign #43 landed. |

---

## NEW work the brief did NOT anticipate

1. **The whole CLI file moved.** `653ee51c` deleted `megaplan/cli.py` (5217 LOC) and created a
   `megaplan/cli/` package (`__init__.py`, `parser.py`, `feedback.py`, `resolutions.py`, `roots.py`,
   `setup.py`, `skills.py`, `status_view.py`). **Every `cli.py:NNNN` coordinate in the brief is dead**
   (dual-dispatch refs `cli.py:4454-4491/:5170`, the `auto_approve` injection, etc.). The
   `COMMAND_HANDLERS` table is now `cli/__init__.py:1014`, dispatch `:1561`. CLI-rewire (Body 2 step
   5) now targets a 1669-LOC `cli/__init__.py` + a clean `parser.py` seam — *easier* than the brief
   assumed, but all line refs must be re-derived.

2. **`patterns.py` and `execute/core.py` — the two biggest Body-3 refactor targets — were already
   split.** Body 3's "formalise patterns.py" is structurally done (`96b5e66b`); Body 3's "extract the
   DAG-runner from execute/" has its file boundaries pre-cut (`6e69814c`: `batch.py`/`merge.py`/
   `aggregation.py`). This **inverts the brief's sequencing claim** that Body 3 is independent
   long-tail: the mechanical decomposition is *done*, so the residual Body-3 work is now purely the
   *semantic* layer (Realizer protocol, killing the 18 relocated `is_prose_mode` branches, the
   capabilities tuple, promotions) — much smaller and cleaner than "~2–3 weeks of file-moving."

3. **The config-bus / state-write debt the brief targets got WORSE, not better.** `save_state_merge_meta`
   went 30→37 sites; `bf7ce72e` threaded *new* `args.`-read clarification logic through
   `override.py`/`plan.py`/`auto.py` and added a new `STATE_AWAITING_HUMAN` + `clarification` state key
   and a 9th override action `resume-clarify` (`override.py:848`). So Body 1 (state-write + HandlerContext)
   is now larger, AND the brief's "8 override actions" inventory (§3.2) is stale — there are **9**, and
   the new prep-clarification human-gate is a *second* human-gate surface (`STATE_AWAITING_HUMAN` +
   `awaiting_user.json`) the §6-hazard-5 resume analysis must now reconcile.

## Top-line: the plan must change because…
- **Phase 0 is the only thing partly built (parity gate skeleton + emission-helper dedup), and it's
  the happy-path stub the brief explicitly warned against** — the highest-value Phase-0 work (decision-
  field diff + branch coverage + discovery guard + toggle) is untouched. Start here, finish it properly.
- **Body 3's mechanical decomposition already happened** (patterns split, execute/core split) — re-scope
  Body 3 from "extract + refactor" down to "add Realizer protocol + delete the 18 *relocated*
  is_prose_mode branches + add capabilities tuple." It's now smaller and partly de-coupled.
- **Every file/line coordinate in the brief is stale** — `cli.py` is gone (now `cli/` package),
  `patterns.py`/`execute/core.py` are split, planning.py shrank to a 122-LOC compiler. Re-baseline all
  §11 evidence coordinates before sequencing. And the legacy-path debt the brief targets (state writes
  30→37, +1 override action, +1 human-gate state) grew, so Body 1 sizing is now *under*-stated.
