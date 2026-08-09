# Task sizing, dependency graph, and test budget investigation

Companion architecture: [Megaplan bounded parallel execution: evidence and architecture](parallel-execution-architecture-investigation-20260715.md)

## Scope and ownership boundary

This investigation owns planner/finalizer task shape, DAG feasibility, write-set
accuracy, per-task narrow-test budgets, harness validation separation, and the
telemetry needed to distinguish those costs. It does not implement compaction,
whole-task replay, attempt adoption, Run Authority, or WBC custody. Those
surfaces are referenced only to classify observed time and define the residual
checkpoint handoff that their owner can consume.

The matching initiative is `custody-control-plane`; its existing M8A brief
already assigns planner/compiler efficiency here and explicitly excludes Run
Authority schemas and compaction/replay ownership.

Evidence is frozen from:

- plan: `m5a-atomic-fail-closed-20260715-0149`;
- immutable finalized artifact:
  `finalize_snapshot.json`, SHA-256
  `1d048a7e5f3aa6b7548faa3345b029230550f248a855bfe44ca8dca1b65f6523`;
- target source binding: base
  `5e4f375737cacf2ca6d2977c12a767cd33f9ae6f`, observed target head
  `4be5d0b566d23c74f7e66254e72e51886010328a`;
- engine source recorded by the plan: `/workspace/arnold-custody-runtime`;
- the relevant finalizer prompt bytes are identical in that engine tree and the
  pinned resident tree, SHA-256
  `3dabbe7ae60cf147a1ac22e273dfc016f1126192145bf03eb250c37a8306d003`;
- execution event/tool evidence through T31, with the last inspected active-step
  heartbeat at `2026-07-15T11:14:42Z`;
- resident runtime pin supplied to the investigation:
  `89e74997dd807f20c659519bf4831beed3c2ab7d`.

The mutable target and engine checkouts continued running after the evidence
cutoff. No conclusion depends on later task completion.

## Result

### Confirmed causes of the 35-task/34-edge graph

1. **The approved plan was already serial-shaped.** `plan_v1.md` has 22 ordered
   steps and its final step explicitly says to run targeted tests and then the
   full suite. Gate approved that shape before a task DAG existed.
2. **Finalize guidance manufactured routing dependencies.** The prompt said:
   isolate complexity-7/8 tasks by chaining lighter tasks through them, and
   linearize independent fan-out with `depends_on` when it exceeded five. The
   runtime already splits ready frontiers into chunks of at most five, so these
   instructions converted routing preference into false correctness authority.
3. **No post-finalize feasibility gate existed.** The model-output schema and
   `_finalize_semantic_postcheck` validate presence, status, complexity range,
   and justification. They do not validate task duration, bounded objective,
   dependency meaning, graph width, critical path, write-set overlap, selector
   budget, or execution-phase feasibility.
4. **Gate cannot inspect what does not yet exist.** Critique asks whether a plan
   step fits a worker turn, but finalize runs after gate. Gate reported all
   critique dimensions clear and proceeded; no gate ran on the emitted DAG.
5. **The schema does not capture planning estimates or dependency evidence.**
   Complexity 1..10 selects a model tier; it is not a duration estimate and
   does not buy a longer turn. `depends_on` is only a string array. There is no
   `dependency_reasons`, `routing_group`, `estimated_minutes`, planned
   `write_set`, or task test budget.
6. **Planned write sets were absent.** All 35 immutable finalized tasks had
   empty `files_changed` and `commands_run`. After execution, 32 completed
   tasks had claimed 71 file touches over 50 unique files. Hot files were
   touched repeatedly (`chain/__init__.py` six tasks,
   `completion_contract.py` five, `acceptance_transaction.py` four,
   `completion_io.py` four). The finalizer therefore had no data with which to
   prove either independence or required ordering.
7. **The verification scrubber destroys objectives instead of extracting test
   work.** Model-authored descriptions that match the run-test heuristic are
   replaced wholesale with the generic “introduce no new failures” text. In
   this plan that erased the visible Step 7 and Step 9 implementation objectives
   in T8 and T11; executors reconstructed the intended work from surrounding
   context. T32 and T35 remained model-dispatched validation placeholders even
   though the harness claims to own authoritative validation.

### Exact graph and task-shape evidence

- 35 tasks, 34 dependency edges, one root (`T1`).
- Maximum topological width: 1.
- Critical path: all 35 tasks.
- Seriality: 100% by node count and by estimated topology (there are no
  duration estimates from which to compute a weighted alternative).
- Complexity sum: 200.
- Complexity distribution: 2 at 4, 14 at 5, 12 at 6, 6 at 7, 1 at 8.
- Seven tasks were complexity >=7: T2, T9, T15, T16, T17, T30, T32.
- Kind distribution: 26 code, 8 test, 1 audit.
- The prompt promised one roughly 15-minute turn per task. In the first-pass
  completed calls through T30, seven calls exceeded 15 minutes and four
  exceeded 30 minutes. Examples: T2 about 21.2 minutes, T9 about 37.6, T15
  about 26.8 after its failed attempt, T16 about 29.7, T17 about 41.6, T18
  about 35.1, and T30 about 31.7.

These are objective-sizing failures. A stronger model tier did not make them
fit the fixed turn contract.

## Was in-task test execution the material cause?

**No for task size and graph shape; partially yes for avoidable end-to-end
latency.**

### Implementation-task evidence

- The graph was finalized before any implementation tests ran, so tests cannot
  have caused the 35/34 topology.
- First-pass completed worker-call wall time through T30 was approximately
  6.97 hours. Worker-call spans combine model generation and all tool activity.
- T1 through T31 issued 147 pytest commands. 128 returned a parsable elapsed
  duration totaling 690.46 seconds (11.51 minutes); 19 did not expose elapsed
  time. This is measured command time, not an assumption.
- Known pytest time was therefore only about 2.7% of the 7.16 hours across all
  33 completed execute calls inspected, and an even smaller fraction of the
  full active window. Individual high-wall-time tasks often reported seconds
  of known pytest time: T2 1.80s, T9 8.44s plus four unmeasured invocations,
  T16 10.08s, T17 11.44s, T18 43.02s, and the successfully recognized T30
  replay 1.98s.
- The 147 invocations are still excessive: workers repeatedly widened from a
  focused check to hundreds of tests. They add churn and can expose unrelated
  failures, but the available timings do not support the claim that they
  dominated worker time.

### Harness and final-validation evidence

- Finalize selected 319 path selectors from plan metadata.
- The baseline ledger has one run, status `timeout`, and the finalized note
  says it hit the absolute 900-second ceiling while still producing output.
- The ledger leaves `started_at`, `finished_at`, `duration_seconds`,
  `exit_code`, and selector count null despite the timeout.
- The gate itself warned that the large import-graph suite had to be runnable.
- T32 and T35 are model tasks whose only visible objective is the generic
  no-new-failures contract. Those checks should be harness validation jobs,
  not LLM conversations.

Therefore broad tests materially increased finalize and late-validation wall
time and reliability risk, but did not cause the oversized implementation
objectives or the serial graph.

## Time classification

### Task shape

Confirmed by the immutable DAG and prompt: one objective often spanned a shared
contract, several consumers, compatibility behavior, and proof. Complexity was
used as a routing score without a duration field or split gate.

### Model plus general tool time

33 completed execute calls accounted for 25,763.43 seconds (7.16 hours) of
call wall time and 101,604,702 input plus 847,256 output tokens. The median
completed call was about 478.7 seconds. Current telemetry cannot split those
spans into model generation, repository reads/searches, edits, and non-test
commands.

### Test time

Known in-task pytest time was 690.46 seconds across 128 commands; 19 commands
lacked an elapsed value. Separately, the finalize baseline consumed its full
900-second ceiling. These populations must not be combined or treated as zero
when missing.

### Retry/replay/queue time

- T15 began a call at `2026-07-15T04:56:56Z`; provider timeout/stall events
  culminated at `2026-07-15T05:15:01Z`, about 18.1 minutes later. Its next full
  worker call then ran about 26.8 minutes. No residual subobjective checkpoint
  distinguishes useful partial work from replay.
- T30's first worker call ran about 31.7 minutes and the required test file was
  committed at `2026-07-15T09:51:35Z`; the stale failure was recorded two
  seconds later. Recovery guidance at `2026-07-15T10:23:37Z` explicitly said to
  reuse that evidence, yet T30 was re-driven from `2026-07-15T10:27:06Z` until
  successful recognition at `2026-07-15T10:52:38Z`, about 25.5 minutes of
  replay/compaction/retry wall after a roughly 35.6-minute repair queue delay.
- Two of those repeated T30 call starts and one T15 call start have no matching
  `llm_call_end`. Error records are not linked to call transaction IDs. The
  exact compaction-versus-provider-versus-tool split is unavailable.

This section is evidence for the replay owner, not an implementation claim in
this investigation.

## Missing telemetry

The following must be represented as unavailable, never zero:

1. no planned or observed task duration estimate;
2. no command/test start/end spans joined to task, batch, attempt, and call ID;
3. Hermes message/tool timestamps collapse near the response-persistence time,
   many sessions leave `ended_at` null, and they cannot measure tool duration;
4. 19 of 147 observed pytest invocations had no parsable elapsed time;
5. baseline suite ledger timeout lacks start, finish, duration, exit code, and
   selector count;
6. execute history recorded a zero-duration error after hours of productive
   batch work, so history duration does not reconcile to call wall time;
7. routing ledger records model/tier and a completion timestamp but no task
   start, tool time, test time, or retry parent;
8. unmatched call starts and unlinked error events prevent exact retry and
   compaction attribution;
9. no token/cost attribution by task or accepted versus replayed outcome;
10. no immutable residual checkpoint with completed subobjectives, output
    hashes, remaining work, and validation state;
11. no dependency reason, planned output artifact, or planned write set;
12. no finalized graph metrics or exception record.

## Enforceable finalization contract

### Proposed initial thresholds

These are conservative canary thresholds, to be calibrated report-only over
the historical corpus before enforcement.

| Control | Warning | Hard block / required action |
|---|---:|---|
| Task estimated duration | >10 min | >15 min: split |
| Task primary objectives | >1 independently reviewable behavior | Multiple independent behaviors: split |
| Planned write set | >3 implementation paths | >5 paths: split or scoped exception |
| Complexity | >=7 | Require split review plus residual checkpoint contract; broad proof becomes harness validation |
| Narrow selectors per task | >2 | >3: move integration scope to harness |
| Narrow test wall budget | >90s | >120s: stop and defer to harness |
| Narrow test attempts | 2 | >2: typed `task_test_budget_exhausted` checkpoint |
| Ready batch estimated work | >12 min | >15 min: split the batch, not the DAG |
| Seriality for >=8 tasks | >75% | 100%: block unless every edge has an approved semantic exception |
| Seriality for >=12 tasks | >80% | >90%: split/replan |
| Critical-path duration | >60% of execute phase timeout | >80%: split/replan |
| Total dispatch estimate | >60% of execute phase timeout | >80%: split/replan |
| Task count | >24 | report only; block only through duration/graph controls |

`phase_timeout` means the configured execute-phase budget, not an assumed
provider timeout. The compiler must report both graph critical-path work and
the actual sequential dispatch estimate because today's executor dispatches
batches serially even when the DAG is wide.

### Versioned schema example

```json
{
  "task_contract_version": 2,
  "tasks": [
    {
      "id": "T4",
      "objective": "Add content-addressed acceptance snapshot IO.",
      "description": "Implement snapshot storage and recovery helpers only.",
      "kind": "code",
      "complexity": 5,
      "complexity_justification": "Touches the immutable snapshot contract used by completion.",
      "estimated_minutes": 10,
      "depends_on": ["T1", "T2"],
      "dependency_reasons": {
        "T1": {
          "kind": "consumes_output",
          "reason": "Uses the versioned AcceptanceSnapshot model.",
          "required_output": "arnold_pipelines/megaplan/orchestration/acceptance_transaction.py:AcceptanceSnapshot"
        },
        "T2": {
          "kind": "consumes_output",
          "reason": "Persists through the CAS journal primitive.",
          "required_output": "arnold_pipelines/megaplan/_core/io.py:prepare_journal_transaction"
        }
      },
      "routing_group": "acceptance-core",
      "write_set": {
        "paths": [
          "arnold_pipelines/megaplan/orchestration/completion_io.py",
          "tests/arnold_pipelines/megaplan/test_completion_io.py"
        ],
        "complete": true
      },
      "narrow_tests": {
        "selectors": ["tests/arnold_pipelines/megaplan/test_completion_io.py"],
        "max_seconds": 120,
        "max_runs": 2
      },
      "checkpoint": {
        "required": true,
        "max_interval_seconds": 300,
        "records": ["completed_subobjectives", "remaining_subobjectives", "output_hashes", "test_state"]
      }
    }
  ],
  "validation_jobs": [
    {
      "id": "V1",
      "kind": "integration",
      "after_tasks": ["T4", "T7", "T12"],
      "selectors": ["tests/orchestration/test_completion_contract_atomic.py"],
      "max_seconds": 900,
      "model_calls": false
    },
    {
      "id": "V2",
      "kind": "full_suite",
      "after_tasks": ["T35"],
      "max_seconds": 1800,
      "model_calls": false,
      "run_once_per_tree_hash": true
    }
  ],
  "graph_report": {
    "task_count": 0,
    "edge_count": 0,
    "max_width": 0,
    "critical_path_task_ids": [],
    "critical_path_minutes": 0,
    "seriality": 0.0,
    "estimated_dispatch_minutes": 0,
    "exceptions": []
  }
}
```

`routing_group` may influence batching but grants no dependency authority.
Every dependency needs a reason and a concrete output. Every non-audit task
needs a complete planned write set or a typed `write_set_unknown` blocker.
Actual undeclared writes block merge unless attributed through an approved
write-set amendment.

## Finalize and post-finalize gates

1. Extend the model-output and runtime schemas with the fields above. Preserve
   v1 reads, but require v2 for new enforcement cohorts.
2. Add a pure `compile_task_feasibility(payload, config)` pass after model
   output and before baseline capture. It computes roots, edges, batches, width,
   weighted and unweighted critical paths, seriality, total estimated work,
   estimated sequential dispatch time, write overlap, and test budgets.
3. Reject duplicate/unknown/cyclic dependencies as today, plus missing reasons,
   reasons that say routing/order/model isolation, missing referenced outputs,
   and false ordering where neither output consumption nor write conflict is
   declared.
4. Validate write overlap bidirectionally: overlapping tasks require a true
   semantic edge or a single routing group; an edge justified only by overlap
   must state which write must precede which.
5. Remove integration/full-suite objectives from model tasks. Compile them into
   `validation_jobs` run by the harness with immutable command, environment,
   output, exit, duration, selector count, tree hash, and evidence hash.
6. Keep unit/focused feedback inside implementation and test-authoring tasks,
   under selector/run/time budgets. On exhaustion, checkpoint residual work and
   stop; do not loop or silently widen.
7. Route feasibility failures to revise with stable codes such as
   `task_objective_oversized`, `task_duration_exceeded`,
   `dependency_reason_missing`, `routing_dependency_forbidden`,
   `write_set_missing`, `write_overlap_unordered`, `serial_graph_unjustified`,
   `critical_path_infeasible`, and `task_test_budget_exceeded`.
8. Run the same compiler after any post-finalize mutation. A mutated task graph
   whose hash differs from the admitted graph cannot execute until recompiled.

### Residual checkpoint and escalation rules

- Tasks estimated >=10 minutes or complexity >=7 must checkpoint at least every
  five minutes and after each independently verifiable subobjective.
- A checkpoint records task/attempt ID, admitted task hash, base/head/tree,
  completed subobjectives, remaining subobjectives, output paths and hashes,
  narrow-test state, and the next safe command. It never marks the task done.
- Resume dispatch receives only the admitted objective plus verified residual;
  it must not replay completed subobjectives. Invalid checkpoints are
  quarantined with an exact reason.
- At 80% of the task budget, force a residual checkpoint. At 100%, emit a typed
  blocker and return to split/revise. Do not increase complexity, model tier, or
  time budget automatically.
- Two equivalent `task_budget_exhausted` outcomes open a plan circuit before a
  third attempt. An authorized exception must be versioned, scoped to exact
  task/graph hashes, evidence-backed, owned, and expiring.
- Post-finalize write-set expansion beyond five paths, selector expansion beyond
  three, or an estimated-duration increase beyond 15 minutes forces a split.

## Focused change implemented

Project commit `0a1fc0a4cc` (`Constrain finalized task graphs and test scope`)
changes only finalization guidance and a new prompt regression test:

- forbids routing-only `depends_on` edges;
- preserves ready frontiers wider than five because the runtime already chunks
  batches;
- removes model-owned integration/full-suite final tasks;
- limits in-task testing to changed-behavior selectors, one normal run plus one
  diagnostic rerun, and a normal 120-second budget;
- changes the example consumer DAG from `T1 -> T2 -> T3` to independent
  consumers `T1 -> {T2,T3}`.

Verification:

```text
pytest -q tests/prompts/test_finalize_task_feasibility_prompt.py
1 passed in 0.18s

pytest -q tests/prompts/test_template_read_instruction.py \
  tests/prompts/test_finalize_task_feasibility_prompt.py
5 passed in 0.10s
```

No schema, handler, executor, checkpoint, retry, replay, compaction, cloud, or
resident file changed. The prompt commit is on the project `main` worktree,
which was 71 commits behind `origin/main` before this work and differs from the
pinned resident/runtime source. It was intentionally not published or deployed;
tree/revision reconciliation is required first.

## Concrete follow-up patch plan and tests

Implement against the reconciled pinned runtime in this order:

1. `finalize_contract.py` and `schemas/runtime.py`: add the v2 fields and
   validation-job schema.
2. New pure module `orchestration/task_feasibility.py`: deterministic compiler
   and stable diagnostic codes, with no execution or replay imports.
3. `handlers/finalize.py`: invoke compiler before baseline capture; persist
   `graph_report.json`; route blockers to revise; stop replacing entire task
   objectives in `_ensure_verification_task`.
4. Test selection: compile integration/full-suite work into harness jobs and
   persist complete timing/evidence spans.
5. Execute prompt/merge boundary: enforce declared write sets and narrow-test
   budgets; emit telemetry spans. Hand residual checkpoint consumption to the
   replay owner without changing replay here.

Required focused tests:

- golden 35/34 fixture rejects `serial_graph_unjustified`;
- 30/29 historical Transaction fixture rejects identically;
- wide independent graph remains wide and is chunked into <=5 without new
  edges;
- every edge lacks/has valid reason cases, including routing-only rejection;
- critical path and seriality metrics are content-hash deterministic;
- overlapping write sets require order/routing-group evidence;
- missing write sets fail v2 admission;
- >15-minute estimate and complexity-7 unsplit task fail;
- <=3 narrow selectors, <=120 seconds, <=2 attempts pass; each boundary+1
  fails with a stable code;
- integration/full-suite validation emits zero model calls;
- objective text containing a focused test command is preserved rather than
  replaced wholesale;
- post-finalize mutation invalidates graph hash and re-runs feasibility;
- telemetry reconciliation accounts for model, general tool, narrow test,
  harness validation, retry, replay, compaction, and queue time or records an
  `unavailable_reason`.
