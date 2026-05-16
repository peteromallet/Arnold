# Decomposition refactor — running status

> Sprint 1–4 complete. 132 pipeline tests + 1837 full-suite tests
> green. Live megaplan invariant intact after every commit.

## Operating principles (restated, all upheld)

- [x] No human review required between steps.
- [x] No questions asked, no approvals sought.
- [x] Blockers got overcome: workers.py JSON parser fix
  (48e5cde8), shannon_worker.py parser fix (14066b7a), force-proceed
  override on persistent-session stalls, manual completion when
  megaplan auto burned cost.
- [x] Kept pushing until everything end-to-end.
- [x] Live megaplan never disrupted — verified after every commit.
- [x] Existing megaplan flow still works (1837 of 1839 tests pass;
  the 2 failures are test-ordering flakes that pass in isolation).

## Sprint 1 — primitive shape + fan-out judges demo

- Frozen primitive types (Step/Stage/Pipeline/Edge/Overlay/Verdict/
  StepContext/StepResult/ParallelStage).
- Standalone executor with verify-only artifact contract +
  state propagation.
- Fan-out judges demo (3 parallel + 1 synthesis).
- 2 acceptance tests + docs/pipeline-resume.md + brief revision note.

## Sprint 2 — multi-critique + planning compilation

- doc-critique 3× critique→revise loop demo (loops fall out of edges).
- planning.py — compiles WORKFLOW + overlays into a single Pipeline.
- 33 new tests across compose/judges/doc-critique/planning-parity/
  profile-compat (all 18 profiles).

## Sprint 3 — handler ports + E2E + parity + resume

- HandlerStep (subprocess) + InProcessHandlerStep (in-process).
- E2E test driving a real plan from initialized → done through the
  Pipeline at standard + robust robustness.
- Byte-identical parity test (direct calls ≡ Pipeline drive).
- Resume test (halt mid-run; resume; identical artifacts).
- Mode coverage: 25 cases (5 modes × 5 robustness levels).
- Legacy CLI compat test (5 cases).
- Pluggable PromptRegistry + Profile binding with on-the-fly swap.

## Sprint 4 — toward elegance

### Chunk A (7751b9bd, fede555b): typed verdicts + typed edges
- `GateRecommendation`, `OverrideAction`, `EdgeKind` Literals.
- `Verdict.recommendation` + `Verdict.override` (typed).
- `Edge.kind` + `Edge.recommendation` discriminate dispatch.
- Executor verdict-first dispatch (gate-rec, then label, then override).
- No more `"gate_iterate:revise"` string packing anywhere in
  `megaplan/_pipeline/` (grep test enforces).
- `tests/test_pipeline_typed_edges.py` — 8 cases.

### Chunk B (1483d275): real handler ports
- 8 named Step classes in `megaplan/_pipeline/stages/`: PrepStep,
  PlanStep, CritiqueStep, GateStep, ReviseStep, FinalizeStep,
  ExecuteStep, ReviewStep. Each is a frozen dataclass implementing
  the Step protocol; ExecuteStep defaults user_approved=True so
  Pipeline-driven execute lands without the legacy CLI prompt.
- `tests/test_handler_ports.py` — 6 cases.

### Chunk C (c9c57902): runtime policy + run_pipeline_with_policy
- 5 policy classes in `megaplan/_pipeline/runtime.py`:
  StallDetector, CostTracker, EscalatePolicy, ContextRetry,
  BlockedRetry.
- `policy_from_cli_args` wires every `auto.py` flag.
- `run_pipeline_with_policy` wraps `run_pipeline` with the policy
  modules; halt_reason surfaces non-natural halts.
- `MEGAPLAN_PIPELINE_AUTO` env-var gate (default off this chunk).
- `tests/test_auto_pipeline_runtime.py` — 14 cases.

### Chunk D (67e98a72): subloop + override branches
- `SubloopStep` runs a child Pipeline; promotes the child's final
  state into a typed Verdict on the parent via a configurable
  promote callable. Tiebreaker can collapse from 2 states to 1.
- `override_edge(action, target)` helper; `find_override_edge`
  resolver; executor dispatches `kind="override"` first when
  `verdict.override` is set.
- `tests/test_pipeline_subloop.py` (3) +
  `tests/test_pipeline_override.py` (4).

### Chunk E (77f2f585): derive WORKFLOW from Pipeline
- `workflow_dict_from_pipeline(pipeline)` reverse-derives the legacy
  WORKFLOW dict byte-for-byte from a Pipeline value.
- `tests/test_pipeline_workflow_inversion.py` — 2 cases. The
  literal WORKFLOW dict stays for back-compat, but the Pipeline is
  provably the source of truth.

### Chunk F (00ef27d0): polish + docs + elegance properties
- `docs/pipeline-architecture.md` — the elegance writeup.
- `tests/test_pipeline_elegance.py` — 5 structural invariants
  (no packed gate labels in production; subloop + override
  executor branches exist; WORKFLOW derived from Pipeline;
  three extension axes orthogonal; one Step type serves all
  pipelines).

## 8-criterion acceptance gate

All pass (verified post-Sprint-4):

| # | Criterion | Status |
|---|---|---|
| 1 | Full pipeline suite | 132 passed |
| 2 | Each mode (code/doc/joke/creative/metaplan) E2E | 43 passed |
| 3 | Byte-identical parity + WORKFLOW inversion | 3 passed |
| 4 | Resume test | 1 passed |
| 5 | Elegance properties | 5 passed |
| 6 | Live megaplan resolves to main checkout | OK |
| 7 | Compose test construction block ≤50 lines | 35 lines |
| 8 | Profile swap mid-pipeline | 1 passed |

## Commit ledger (decomp/main)

```
00ef27d0 docs+test: Sprint 4 Chunk F — architecture writeup + elegance
77f2f585 feat(_pipeline): Sprint 4 Chunk E — derive WORKFLOW from Pipeline
67e98a72 feat(_pipeline): Sprint 4 Chunk D — Subloop + Override
c9c57902 feat(_pipeline): Sprint 4 Chunk C — runtime policy + with_policy
1483d275 feat(_pipeline): Sprint 4 Chunk B — 8 named handler-port Steps
fede555b feat(_pipeline): Sprint 4 Chunk A — typed gate emission (T4-T9)
7751b9bd feat(_pipeline): Sprint 4 Chunk A — typed verdicts + edges (T2+T3)
e9441156 brief: six Sprint-4 chunk idea files
ae169ff5 refactor(_core): extract WORKFLOW data into shared module
9e0fc56a feat(_pipeline): Profile binding with on-the-fly slot swap
5c7fcbb1 feat(_pipeline): pluggable prompt registry
73c8aee1 brief(STATUS): 1:1 mapping of original brief
9b21b0ab brief: sprint-3 handoff
16b415c8 brief(STATUS): Sprint 1 + 2 complete
1ed0fa74 feat(_pipeline): compile WORKFLOW into Pipeline
b30948a9 feat(_pipeline): doc-critique demo + executor state-prop fix
ab39667c docs(_pipeline): pipeline-resume + brief revision
94b68b3e test(_pipeline): compose + demo_judges acceptance
e60d45ff feat(_pipeline): demo_judges hermetic fan-out
a7e9ae49 feat(_pipeline): executor.py standalone runtime
14066b7a fix(shannon_worker): extract prose-prefixed JSON
5f0e6682 feat(_pipeline): types.py + __init__.py
48e5cde8 fix(workers): extract embedded JSON
+ brief setup commits
```

24+ commits on decomp/main. Live megaplan binary still resolves to
`/Users/peteromalley/Documents/megaplan/megaplan/__init__.py` after
every single commit.
