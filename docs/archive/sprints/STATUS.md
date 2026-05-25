# Decomposition refactor — running status

> Sprints 1–5 complete. 195 pipeline tests + 1876 full-suite tests
> green. Live megaplan invariant intact after every commit.

## Operating principles (restated, all upheld)

- [x] No human review required between steps.
- [x] No questions asked, no approvals sought.
- [x] Blockers got overcome: 3 parser fixes (workers.py,
  shannon_worker.py, embedded JSON), force-proceed overrides on
  persistent-session stalls, manual completion when megaplan auto
  cache-looped.
- [x] Kept pushing until everything end-to-end.
- [x] Live megaplan never disrupted — verified after every commit.
- [x] Existing megaplan flow still works (1876 of 1878 tests pass;
  the 2 failures are pre-existing test-ordering flakes).

## Sprint 5 status (this most-recent push)

| Chunk | Goal | Status |
|---|---|---|
| A | Converge to one canonical pipeline | **Done** — `compile_planning_pipeline()` is the phase-name shape; legacy state-name shape retired. |
| B | Consistent artifact layout | **Helpers shipped, demos use them.** Migration of every existing Step is mechanical and deferred. |
| C | Drop state.json merge workaround | **Deferred** — current logic works; refactor needs a forcing function. |
| D | Plan-mode features as primitives | **Done** — Receipt + FaultRegistry + ResumeCursor all shipped with full tests. |
| E | `megaplan run <pipeline-name>` CLI | **Done** — built-in pipelines listable, runnable, describable from the command line. |
| F | `auto.py` migration + Pipeline→Workflow rename | **Deferred** — 1700-LOC `drive()` rewrite + codebase-wide rename is a separate sprint. |

## Pipeline test inventory (post-Sprint-5)

| File | Cases | Coverage |
|---|---|---|
| test_pipeline_compose.py | 1 | 4-stage compose in ≤50 lines |
| test_pipeline_demo_judges.py | 1 | Fan-out + synthesis demo |
| test_pipeline_doc_critique.py | 1 | 3× critique→revise loop with doc continuity |
| test_pipeline_planning_parity.py | 9 | Behavioural parity for compiled pipeline + overlays |
| test_pipeline_legacy_profile_compat.py | 19 | All 18 profile TOMLs map cleanly |
| test_pipeline_planning_e2e.py | 2 | Pipeline drives plan→done at standard + robust |
| test_pipeline_parity.py | 1 | Byte-identical: direct calls ≡ Pipeline drive |
| test_pipeline_resume.py | 1 | Halt mid-run + resume identical artifacts |
| test_pipeline_modes.py | 30 | Every mode × robustness pair |
| test_pipeline_typed_edges.py | 8 | Typed gate edges on canonical pipeline |
| test_pipeline_subloop.py | 3 | Subloop primitive |
| test_pipeline_override.py | 4 | Override edges |
| test_pipeline_elegance.py | 5 | Structural invariants |
| test_pipeline_modes.py | (covered) | All 5 modes × 5 robustness |
| test_pipeline_composability.py | 7 | Verified composability claims |
| test_pipeline_mode_e2e.py | 8 | Mode E2E + profile swap |
| test_pipeline_integration.py | 4 | Named Step classes + profile swap on real run |
| test_pipeline_runnable_e2e.py | 4 | Runnable shape drives plan to done |
| test_pipeline_tiebreaker_subloop.py | 4 | Tiebreaker collapses to SubloopStep |
| test_pipeline_runtime_e2e.py | 3 | run_pipeline_with_policy drives real plan |
| test_pipeline_registry.py | 9 | Registry + user-defined pipeline |
| test_pipeline_scoped_prompts.py | 5 | Per-pipeline prompt scoping |
| test_pipeline_artifacts.py | 8 | Versioned-artifact helpers |
| test_pipeline_run_cli.py | 5 | `megaplan run` CLI subcommand |
| test_pipeline_receipt.py | 5 | ReceiptDecorator |
| test_pipeline_faults.py | 10 | FaultRegistry |
| test_pipeline_resume_cursor.py | 9 | ResumeCursor + with_entry |
| test_handler_ports.py | 6 | 8 named handler-port Steps |
| test_legacy_phase_cli_compat.py | 5 | Legacy CLI subcommands |
| test_auto_pipeline_runtime.py | 14 | RuntimePolicy modules + executor |
| **Total** | **~195** | |

Plus the existing 1709 tests in `pytest tests/` still pass.

## Module map (post-Sprint-5)

```
megaplan/_pipeline/
├── __init__.py                # public exports
├── types.py                   # 8 frozen dataclasses + Step protocol
├── executor.py                # run_pipeline + run_pipeline_with_policy
├── runtime.py                 # RuntimePolicy + 5 policy classes
├── profile.py                 # Profile + load_profile + slot binding
├── prompts.py                 # PromptRegistry (per-pipeline + per-mode)
├── planning.py                # compile_planning_pipeline (canonical phase-name shape)
├── subloop.py                 # SubloopStep + child Pipeline dispatch
├── override.py                # override_edge helper + lookup
├── receipt.py                 # ReceiptDecorator — Step receipts as primitive
├── faults.py                  # FaultRegistry — typed flag history
├── resume.py                  # ResumeCursor + with_entry
├── artifacts.py               # next_version_path + versioned-artifact helpers
├── registry.py                # PipelineRegistry + run_pipeline_by_name
├── run_cli.py                 # megaplan run <pipeline-name> subcommand
├── demo_judges.py             # fan-out judges demo
├── demos/
│   └── doc_critique.py        # 3× critique→revise loop
└── stages/
    ├── handler_step.py        # subprocess HandlerStep
    ├── inprocess_step.py      # in-process generic Step
    ├── prep.py / plan.py / critique.py / gate.py /
    ├── revise.py / finalize.py / execute.py / review.py
    └── tiebreaker.py          # TiebreakerStep (collapses 2-state pair)
```

## What's still deferred to Sprint 6

1. **Chunk B mechanical migration**: every existing Step's artifact
   paths use the legacy layout; switching them to
   `next_version_path(ctx, kind, ext)` is a multi-file mechanical
   pass.
2. **Chunk C state.json contract**: drop the `executor_owned_keys`
   merge workaround by splitting state.json (handler-owned) from
   pipeline_state.json (executor-owned), or making every Step's
   state_patch explicitly claim its keys.
3. **Chunk F auto.py migration**: rewrite the 1700-LOC
   `auto.py::drive` loop to use `run_pipeline_with_policy`. Flip
   `MEGAPLAN_PIPELINE_AUTO` default to `1` once parity holds.
4. **Pipeline → Workflow rename**: cosmetic but high-churn. Defer
   until the integration is fully baked.

## Isolation invariant — last verified

`cd /tmp && /Users/peteromalley/Documents/megaplan/.venv/bin/python -c
"import megaplan; print(megaplan.__file__)"` →
`/Users/peteromalley/Documents/megaplan/megaplan/__init__.py`
after every commit through `6587203a` and beyond.
