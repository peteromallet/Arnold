# M4 - Tree Graph, Trace, And Audit Skeleton

## Objective

Build the tree-shaped structural layer that tooling consumes: a static derived
composition graph, a tree-shaped run trace, stable path addressing, and a
minimal per-attempt audit skeleton. Runtime traces record what happened; the
derived graph records what the workflow contains. Both are needed.

## Files To Change And Instructions

- `arnold/pipeline/native/compiler.py`
  Emit or expose the static composition tree for workflows, including untaken
  branches, child workflow call sites, loop nodes, stable IDs, and declared
  interfaces. Prefer deriving this graph at workflow registration/decorator
  time when possible so static queries work before execution and do not require
  a runtime run.
- `arnold/pipeline/native/ir.py`
  Add static graph/query metadata if the existing IR cannot answer "what does
  this workflow contain" without executing it.
- `arnold/pipeline/native/trace.py`
  Emit tree-aware run trace events and durable trace artifacts. Preserve enough
  data to render a nested run and query any executed node by path.
- `arnold/pipeline/native/audit.py`
  Create the per-attempt audit skeleton layer or an equivalent module. Record
  at least `run_id`, `step_path`, `attempt`, `inputs_ref_or_summary`,
  `output_ref_or_summary`, `started_at`, `ended_at`, and `status`. Keep this
  logically separate from operational checkpoints even if the initial storage is
  file-backed.
- `arnold/pipeline/native/runtime.py`
  Carry the current run path through parent and child workflow execution and
  call the audit skeleton at the step boundary, including failures.
- `arnold/pipeline/native/checkpoint.py`
  Persist path metadata in native cursors without breaking existing native
  cursor classification.
- `tests/arnold/pipeline/native/`
  Add golden fixtures for nested traces, static graph queries, repeated child
  workflow call sites, loop iteration paths, failed attempts, and depth-3
  nesting.
- `tests/arnold/pipelines/megaplan/`
  Update Megaplan compositional trace expectations so the major subworkflows
  are visible as a tree and queryable as static structure.
  Static topology must also show the tiebreaker researcher/challenger
  subworkflow with `pick`, `escalate`, and `replan` decision routes; review
  `criteria_verdict`, every selected review-check child, reducer/fan-in, and
  infra-retry trace; and execute DAG/batch children rather than a single opaque
  execute node.

## Verifiable Completion Criterion

- Native tooling can answer "what does this workflow contain?" from the static
  derived graph without executing the workflow.
- Native traces represent executed nested workflows as a tree, not only as an
  ordered flat stage list.
- Every step-run can be addressed by a stable path such as
  `root/critique_loop[2]/revise`.
- The path format explicitly separates stable machine identity from human
  display labels, and the contract states whether a rename is breaking or
  produces a display-only change.
- Reusing the same child workflow in two places produces distinct path
  addresses.
- Failed step attempts are visible in the audit skeleton, not lost behind
  successful retries.
- Existing non-nested workflows still produce usable traces.
- The static topology snapshot includes untaken tiebreaker `replan`, review
  fanout/reducer, execute-batch, approval/deferred-human, and no-review routes.
- For runtime-list fanout, static topology shows the typed dynamic-map or DAG
  node, collection schema, mapper, reducer/fan-in, declared policy, and stable
  item path template. Runtime tree traces expand the concrete selected children
  for each run. Static topology is not required to enumerate runtime-selected
  items before execution.

## Native Representation Alignment

- Matrix rows owned or affected: Tiebreaker researcher/challenger path; Dependency-aware execute batches; Execute/review/rework loop; Review parallel checks/fan-in; Path-addressed checkpoints; Handler topology extraction/purity audit; Behavior parity with existing Megaplan.
- Expected status change: rows requiring rendered/static topology gain proof through static graph snapshots and tree traces.
- Proof artifacts: static derived graph snapshots with untaken branches, nested trace goldens, per-attempt audit skeletons, Megaplan compositional trace expectations, tiebreaker `replan` topology, review fanout/reducer topology, execute DAG topology, infra-retry trace, and failed-attempt audit tests.
- False-pass guard: runtime traces from only a happy path are insufficient;
  snapshots must show untaken branches, child workflows, loop nodes, stable IDs,
  declared interfaces, and dynamic-map templates. Runtime-expanded traces must
  show concrete dynamic-map children.
- Deferrals: kill/resume from nested paths is M5; broker content logs and DB audit storage are platform M2/M4.
- Canonical source paths/imports: graph and trace generation must resolve from the same canonical Megaplan source that package registration and CLI use.

## Risks And Blockers

- Changing trace shape can invalidate many tests; update tests deliberately
  rather than mass-renaming goldens.
- Path stability is a contract. Do not base it on incidental program counters
  alone if source edits would make normal traces unreadable.
- The audit skeleton is not the full broker content log. Prompt/completion,
  exact git commands, diff content, redaction, and retention belong to the
  platform follow-up epic.

## Dependencies

- Depends on M2 and M3.
