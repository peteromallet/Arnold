# Epic Chaining Strategy

## Recommendation

Yes, conditionally: epic-chaining should be framed as **`megaplan chain`, one
level up**.

That analogy holds if the parent layer reuses the **same ordered-unit
contract** that `run_chain()` already uses for milestones:

- durable spec-path-keyed state
- one active unit at a time
- resume the active unit on restart
- append to `completed[]` only after authoritative completion
- advance the cursor only after that append
- honor `--one`
- map failure to `stop` / `skip` / `retry`

It stops being “chain one level up” if we flatten epics into milestone schema
or build a separate orchestration model with different state and advancement
rules.

## Concept Map

| `megaplan chain` today | Epic-chain parent | Maps cleanly? | Notes |
|---|---|---|---|
| `chain.yaml` `milestones[]` | meta-spec `epics[]` | Yes | Same shape: ordered units declared in YAML. The only change is the unit type. |
| one milestone run | one child epic run | Yes, with delegation | A milestone unit runs `_init_plan()` + `_drive_plan_with_blocked_execute_recovery()` inside `run_chain()`. An epic unit should instead call the existing child `megaplan chain start --spec <child>`. |
| `ChainState.current_milestone_index` | `current_epic_index` | Yes | Same cursor semantics as [`ChainState` in `spec.py`](/workspace/arnold/arnold_pipelines/megaplan/chain/spec.py:545). |
| `ChainState.current_plan_name` | `current_epic_id` / `current_spec_path` | Partial | Parent needs an “active unit” field, but the child epic keeps its own `current_plan_name` in the child `.chains/` state. |
| `ChainState.completed[]` | `completed[]` of child epics | Yes | Same append-on-authoritative-completion rule; the record payload changes from milestone facts to child-epic boundary facts. |
| milestone `done` then `idx += 1` | child epic `done` then `idx += 1` | Yes | Same advance rule used in the main milestone loop in [`run_chain()`](/workspace/arnold/arnold_pipelines/megaplan/chain/__init__.py:2422). |
| milestone PR / merge lifecycle | child epic PR / merge lifecycle | Mostly | The lifecycle already exists inside the child chain. The parent should observe child status, not own a second PR lifecycle. |
| `merge_policy` | child epic `merge_policy` | Semantic match, not a new parent field | In current chain, `merge_policy` decides whether the unit pauses at `awaiting_pr_merge` or auto-merges before advance. For epic-chaining, that remains the child epic’s concern. |
| `on_failure` / `on_escalate` with `stop_chain` / `skip_milestone` / `retry_milestone` | parent `on_failure` with `stop_epic_chain` / `skip_epic` / `retry_epic` | Yes | Same decision switch as `_handle_outcome()`; only the unit names change. |
| `--one` | single-epic step | Yes | Same pause-after-one-completed-unit behavior as [`run_chain(..., one=True)`](/workspace/arnold/arnold_pipelines/megaplan/chain/__init__.py:2956). |

## What The Current Chain Already Gives Us

The existing chain driver already defines the parent behavior we want:

- `ChainState` persists `current_milestone_index`, `current_plan_name`,
  `last_state`, `pr_number`, `pr_state`, `completed[]`, retry/bump state,
  workspace/session metadata, and `metadata`; see
  [`arnold_pipelines/megaplan/chain/spec.py`](/workspace/arnold/arnold_pipelines/megaplan/chain/spec.py:545).
- `_state_path_for()` writes deterministic digest-keyed state under
  `.megaplan/plans/.chains/<spec>-<digest>.json`; see
  [`spec.py`](/workspace/arnold/arnold_pipelines/megaplan/chain/spec.py:694).
- `run_chain()` loads state, resumes the active unit, skips already-completed
  units, appends to `completed[]`, advances `current_milestone_index`, and
  pauses on `--one`; see the main milestone loop in
  [`chain/__init__.py`](/workspace/arnold/arnold_pipelines/megaplan/chain/__init__.py:2422).
- `_handle_outcome()` already reduces terminal child status to
  `advance` / `stop` / `retry` / `skip`, with persisted retry counters and
  escalation policy; see
  [`chain/__init__.py`](/workspace/arnold/arnold_pipelines/megaplan/chain/__init__.py:2024).
- `docs/megaplan-epic.md` already defines an epic as an ordered list of
  sprint-sized megaplans driven by `megaplan chain`, with sticky state, PR
  lifecycle, and `--one`; see
  [`docs/megaplan-epic.md`](/workspace/arnold/docs/megaplan-epic.md:11).

That is why the right mental model is not “new orchestration concept.” It is
“same orchestration concept, different unit.”

## Maximal-Reuse Design

### Recommendation

Build a **thin parent `megaplan epic-chain` driver** that **reuses the chain
engine’s outer state/advance semantics** and delegates unit execution to the
existing child chain driver.

That is the smallest change that is still honestly “chain one level up.”

### Why not fully generalize `run_chain()`?

The outer loop generalizes cleanly. The unit body does not.

The current milestone body in `run_chain()` is tightly bound to milestone-plan
operations:

- `_refresh_base_branch()`
- `_checkout_milestone_branch()`
- `_init_plan()`
- `_drive_plan_with_blocked_execute_recovery()`
- `_commit_and_push_phase()`
- milestone completion guards and full-suite backstop handling

Those are the right behaviors **inside** a child epic. Re-parameterizing them
so the same function can drive both plans and child chains would be larger and
harder to reason about than a thin parent wrapper.

### Smallest-change implementation shape

The parent should mirror the current chain loop, but substitute “child epic”
for “milestone”:

1. Load `EpicChainSpec` and digest-keyed `EpicChainState`.
2. If `current_epic_index < 0`, initialize it to `0`.
3. If the active child epic is already in progress, re-enter
   `megaplan chain start --spec <child-spec>`.
4. Read the child chain’s durable state/status.
5. If the child is still running, blocked on PR merge, or blocked on human or
   quality input, return that parent state without advancing.
6. If the child is authoritatively complete, verify cross-epic handoff, append
   a completed record, bump `current_epic_index`, clear current-epic fields,
   and persist atomically.
7. If `--one` is set, stop after one completed child epic.

In code terms: reuse the **shape** of `ChainState`, `_state_path_for()`,
`load_*_state()`, `save_*_state()`, the `while idx < len(units)` loop, and the
`advance` / `stop` / `retry` / `skip` switch. Do **not** reimplement
milestone-level git/PR/plan orchestration at the parent layer.

If a later refactor is warranted, extract only the generic ordered-unit cursor
logic from `run_chain()` into shared helpers. Do not try to make the entire
milestone engine polymorphic in v1.

## Declaration Shape

The parent spec should look like chain spec one level up:

```yaml
base_branch: main
anchors:
  north_star: NORTHSTAR.md

epics:
  - id: python-shaped-workflow-authoring
    spec: .megaplan/briefs/python-shaped-workflow-authoring/chain.yaml

  - id: native-python-pipelines-completion
    spec: .megaplan/briefs/native-python-pipelines-completion/chain.yaml
    handoff_from_previous:
      require_merged_base: true
      artifacts:
        - path: docs/arnold/python-shaped-authoring-contract.md
          check: exists
        - path: arnold_pipelines/megaplan/workflows/planning.py
          check:
            kind: contains_text
            text: "WorkflowPolicy"

on_failure:
  abort: stop_epic_chain
```

Use a new meta-spec, not nested `milestones:`:

- current `MilestoneSpec` expects `idea`, not child `chain.yaml` references
- current milestone execution initializes and drives plans, not child chains
- child epics already have their own state files under `.chains/`

## Parent State

Use the same digest-keyed persistence pattern as chain state, but at the epic
grain:

```text
.megaplan/plans/.epic_chains/<spec-stem>-<digest>.json
```

The parent state should intentionally mirror `ChainState`:

```json
{
  "schema_version": 1,
  "current_epic_index": 1,
  "current_epic_id": "native-python-pipelines-completion",
  "current_spec_path": ".megaplan/briefs/native-python-pipelines-completion/chain.yaml",
  "last_state": "awaiting_pr_merge",
  "completed": [
    {
      "id": "python-shaped-workflow-authoring",
      "spec": ".megaplan/briefs/python-shaped-workflow-authoring/chain.yaml",
      "status": "done",
      "base_branch": "main",
      "pr_number": 456,
      "pr_state": "merged",
      "child_state_path": ".megaplan/plans/.chains/chain-<digest>.json",
      "handoff_verified": {
        "artifacts": [
          "docs/arnold/python-shaped-authoring-contract.md"
        ]
      }
    }
  ],
  "chain_session": "megaplan-epic-chain",
  "resolved_workspace": "/workspace/app",
  "metadata": {}
}
```

Two important differences from `ChainState` are intentional:

- `current_plan_name` does not belong in parent state; the child epic already
  owns that in its own `ChainState`.
- parent `pr_number` / `pr_state` are boundary observations about the active
  child epic, not a separate parent-owned PR workflow.

## Failure Semantics

The semantic mapping is clean:

- child epic `done` -> parent verifies handoff, appends to `completed[]`,
  advances
- child epic `awaiting_pr_merge` -> parent stays on the same child epic
- child epic `awaiting_human_verify`, `human_prerequisite`, or `quality_gate`
  -> parent blocks without auto-skipping
- child epic `stopped` or `blocked` -> parent applies its own
  `stop_epic_chain` / `skip_epic` / `retry_epic` policy

This should reuse the same decision model as `_handle_outcome()` rather than
inventing a second escalation ladder above the child chain. The child epic
already owns milestone retries, tier bumps, and escalation.

## Where The Analogy Genuinely Diverges

### 1. Units are chains, not plans

This is the real seam.

A milestone unit in `run_chain()` is a single plan lifecycle. A parent epic
unit is a full child `megaplan chain start`, with its own:

- `ChainSpec`
- `.megaplan/plans/.chains/<child>.json`
- `current_milestone_index`
- `current_plan_name`
- `completed[]`

So the parent should store only boundary facts, not duplicate child progress.

### 2. Merge policy stays at the child level

Current chain behavior is:

- if a milestone PR is not merged and `merge_policy == "review"`, the chain
  persists `last_state = awaiting_pr_merge` and waits
- if `merge_policy` allows auto-merge, the chain enables merge and advances
  only after merge is durable

That behavior already exists in the child chain loop in
[`chain/__init__.py`](/workspace/arnold/arnold_pipelines/megaplan/chain/__init__.py:2804).
The parent should observe the child’s status and wait; it should not invent a
second merge policy.

### 3. The base branch advances across epic boundaries

This is different in scope, but not in model.

Current chain git behavior already assumes downstream units build on the latest
integrated base:

- `_refresh_base_branch()` refreshes `origin/<base_branch>` before new unit
  work; see
  [`git_ops.py`](/workspace/arnold/arnold_pipelines/megaplan/chain/git_ops.py:35).
- `_checkout_milestone_branch(..., from_origin=True)` forks or rebases onto the
  refreshed `origin/<base_branch>` so later units see prior merged work; see
  [`git_ops.py`](/workspace/arnold/arnold_pipelines/megaplan/chain/git_ops.py:332).

That means the parent usually does **not** need to pass “branch from the
previous epic’s merged tip” explicitly. The normal child-chain contract already
does that, provided:

- all child epics use the same `base_branch`
- the parent validates that invariant

In `--no-push` mode, the parent should still record the child’s local
integration commit so the handoff is explicit, just as current chain state
records `local_commit_sha` in completed milestone entries.

### 4. One program North Star, narrower child North Stars

Current chain already supports an epic-level north-star anchor plus optional
milestone-level north stars via `_attach_chain_anchors_to_plan()`.

Epic-chaining should apply the same pattern one level up:

- the parent carries the program North Star across all child epics
- each child epic may still narrow that with its own `anchors.north_star`

### 5. Supervision is split-level

The parent session should be the top-level liveness object. The active child
epic should remain the detailed execution object.

That matches the current status and supervision model:

- `chain/status.py` classifies chain state into `running`, `complete`,
  `awaiting_pr_merge`, `awaiting_human_verify`, `human_prerequisite`,
  `quality_gate`, and `stale_bookkeeping`; see
  [`status.py`](/workspace/arnold/arnold_pipelines/megaplan/chain/status.py:169).
- the supervisor-backed chain runner already treats a chain as an ordered node
  list with its own durable `SupervisorState`; see
  [`supervisor/chain_runner.py`](/workspace/arnold/arnold_pipelines/megaplan/supervisor/chain_runner.py:89).

So the parent should supervise the meta-chain session, while the child chain
and child supervisor state remain the source of truth for the active epic.

## Bottom Line

The right v1 is:

- a new parent spec that lists child epics
- a new parent state file under `.epic_chains/`
- a thin parent driver whose loop and state semantics mirror `megaplan chain`
- delegation of actual unit execution to existing child `megaplan chain`
  runs

That is the smallest design that is honestly **“`megaplan chain`, one level
up”**. It maximizes reuse of the current chain model, keeps child epic state
authoritative, and only diverges where the unit itself changes from “plan” to
“chain.”
