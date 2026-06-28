# Epic Chaining Strategy

## Goal

Arnold already has a solid unit for one epic: `megaplan chain`, backed by
`ChainSpec`, `ChainState`, `run_chain()`, optional supervisor routing, and
cloud status/supervision. The missing layer is one level up: a durable,
resumable sequence of epics where each item in the sequence is itself a
`chain.yaml`.

This note recommends the smallest addition that gives first-class cross-epic
ordering, handoffs, resume, and supervision without flattening or rewriting the
existing chain model.

## What Exists Today

The current chain contract is already strong enough to reuse directly:

- `arnold_pipelines/megaplan/chain/spec.py`
  - `ChainSpec` carries `base_branch`, `milestones`, `on_failure`,
    `on_escalate`, `merge_policy`, `prerequisite_policy`,
    `validation_policy`, `review_policy`, and driver knobs.
  - `ChainState` persists `current_milestone_index`, `current_plan_name`,
    `last_state`, `pr_number`, `pr_state`, `completed[]`, retry counters,
    bump state, sync state, workspace/session metadata, and freeform
    `metadata`.
  - `_state_path_for()` writes deterministic digest-keyed state under
    `.megaplan/plans/.chains/<spec>-<digest>.json`.
- `arnold_pipelines/megaplan/chain/__init__.py`
  - `run_chain()` resumes by loading the same child state file, advances only
    after authoritative completion, and already handles mid-milestone resume,
    PR-merge waits, retries, and no-push local-base integration.
  - `build_chain_parser()` and `run_chain_cli()` define the current
    `chain start|status|verify|override` surface.
- `arnold_pipelines/megaplan/supervisor/chain_runner.py`
  - The flag-on path already treats a chain as an ordered node list and keeps a
    separate `SupervisorState` keyed by the spec path.
  - The supervisor owns the neutral ladder and child retries; the child chain
    is already the right unit of work for escalation.
- `arnold_pipelines/megaplan/chain/git_ops.py`
  - `_refresh_base_branch()` and `_checkout_milestone_branch()` already define
    the intended branching rule: fork from refreshed `origin/<base_branch>`
    when pushing, or from the local base branch in no-push mode.
- `arnold_pipelines/megaplan/chain/status.py` and
  `arnold_pipelines/megaplan/cloud/supervise.py`
  - chain status is already classifiable into `running`, `complete`,
    `awaiting_pr_merge`, `awaiting_human_verify`, `human_prerequisite`,
    `quality_gate`, and `stale_bookkeeping`.
  - cloud supervision is already mechanical-relaunch-first: it restarts only
    when the session is safely recoverable, advances after merged PRs, and
    refuses human/quality decisions.

`docs/megaplan-epic.md` also establishes the current product contract:

- an epic is an ordered list of sprint-sized milestones in one `chain.yaml`
- milestones depend on artifacts produced by earlier milestones
- state is sticky and resumable per spec path
- `base_branch` is the integration branch for the epic

That existing model should remain intact. Epic-chaining should compose it, not
replace it.

## The Unit And The Handoff

The right unit is one child epic, meaning one existing `chain.yaml` plus its
own child chain state and optional child supervisor state.

The right cross-epic handoff is a composite of three things:

1. `merged_base`
   - The primary handoff is the repository state that landed on the shared
     `base_branch`.
   - In push/PR mode, this means the merged result on `base_branch`.
   - In `--no-push` mode, this means the last local integration commit on the
     base branch, which child chains already record in `completed[]` as
     `local_commit_sha`.
2. `artifacts`
   - The next epic should be able to assert that specific repo artifacts exist
     in the merged base tree.
   - Keep v1 checks intentionally small:
     - `exists`
     - `contains_text`
   - Anything more semantic should stay inside a milestone or validation gate,
     not become a general-purpose cross-epic DSL.
3. `north_star`
   - Carry the top-level North Star forward as a program-level anchor.
   - The child epic may still declare its own `anchors.north_star`, but the
     meta-layer should have one shared anchor for the whole sequence.

Recommendation: define the cross-epic handoff as
`{base ref + explicit artifact assertions + inherited North Star}`. A git ref
alone is too implicit; artifact checks alone ignore the integration boundary.

## Declaration Shape

### Option A: Meta-chain spec plus thin `megaplan epic-chain` driver

Example:

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
  abort: stop_chain
on_escalate:
  abort: stop_chain
```

Properties:

- ordered list, just like `milestones:` today
- each item points at an existing child `chain.yaml`
- cross-epic handoff is declared where the consumer needs it
- child chain specs remain authoritative for milestone-level behavior

### Option B: Independent `megaplan chain start` launches plus convention/script

This is cheapest to prototype, but it is not a real orchestration surface.

- no first-class persisted answer to “epic 2 of 5”
- no top-level resume point across epic boundaries
- handoff checks live in ad hoc shell/script logic
- cloud/watchdog sees only whichever child chain happens to be active

This is acceptable as an operator habit, but weak as a product contract.

### Option C: One nested `chain.yaml` where milestones are epic specs

This is the wrong abstraction.

- current `MilestoneSpec` expects `idea`, not child chain specs
- milestone state and epic state are different grains
- nested PR/base-branch semantics become ambiguous
- child chain resume/state files either disappear or must be reimplemented
- supervisor ladder and chain status would need a second interpretation layer

This has the highest implementation cost and the least conceptual clarity.

### Recommendation

Recommend **Option A**: a **meta-chain spec** plus a **thin new
`megaplan epic-chain` driver**.

Why:

- It is the smallest addition that preserves real top-level state and resume.
- It reuses the existing child chain driver unchanged.
- It keeps child chain failure semantics, PR lifecycle, and supervision intact.
- It avoids flattening two different units of work into one schema.

## Cross-Epic State And Resume

Mirror the existing digest-keyed pattern.

Recommended state path:

```text
.megaplan/plans/.epic_chains/<spec-stem>-<digest>.json
```

Recommended `EpicChainState` shape:

```json
{
  "schema_version": 1,
  "current_epic_index": 1,
  "current_epic_id": "native-python-pipelines-completion",
  "current_spec_path": ".megaplan/briefs/native-python-pipelines-completion/chain.yaml",
  "last_state": "running",
  "completed": [
    {
      "id": "python-shaped-workflow-authoring",
      "spec": ".megaplan/briefs/python-shaped-workflow-authoring/chain.yaml",
      "status": "done",
      "base_branch": "main",
      "merged_commit": "abc123",
      "pr_number": 456,
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

Important design point: do **not** duplicate child chain progress inside the
meta-state. The child chain already has its own durable `ChainState`. The
meta-state should only store:

- which child epic is active
- which child epics are complete/skipped/stopped
- the boundary facts needed to advance to the next epic

Resume behavior:

- crash mid-epic:
  - reload `EpicChainState`
  - re-enter the same child `megaplan chain start --spec <child>`
  - child chain resumes from its own `ChainState`
- crash after child epic finished but before boundary commit:
  - on restart, read the child chain status
  - if the child already classifies as complete, re-run handoff verification
    and advance idempotently
- crash mid-boundary:
  - boundary advancement must be a single reconcile step:
    verify child completion, verify handoff, write completed entry, bump
    `current_epic_index`, fsync/atomic replace

This is exactly the same pattern the current chain driver uses around merged PR
advancement: observe durable child state, then reconcile and advance.

## Failure Semantics

The meta-layer should treat the child epic as authoritative for milestone-level
retries and escalations.

That means:

- child milestone failure is handled inside the child chain by its own
  `on_failure_policy`, retry counters, bump state, or supervisor ladder
- the epic-chain should react only to the child epic’s top-level status

Recommended mapping:

- child returns `done`
  - verify handoff, then advance
- child returns `awaiting_pr_merge`
  - epic-chain pauses at the boundary; same child epic remains active
- child returns `awaiting_human_verify`, `human_prerequisite`, or
  `quality_gate`
  - epic-chain is blocked; do not auto-skip
- child returns `stopped` or `blocked`
  - apply epic-chain `on_failure`

Recommended epic-chain policy surface:

- `stop_chain` default
- `retry_epic`
- `skip_epic`

Default should be conservative: **one epic failing halts the whole epic-chain**.

Why not add a second tier ladder at the meta-layer:

- the child chain already has laddered retry/escalation behavior
- supervisor-tier routing already moves escalation into the neutral ladder in
  `supervisor.chain_runner.run_chain()`
- a second automatic ladder above that would be hard to reason about and would
  blur whether the failure belongs to the child epic or the program plan

## Supervision

Recommendation: supervise the **epic-chain session** as the top-level unit, but
keep **per-epic child chain state** as the detailed source of truth.

That gives the right split:

- one top-level marker/session for liveness, restart, logs, and operator
  attachment
- one active child chain for milestone-level progress and existing status
  classification

How this fits the current cloud/watchdog model:

- `cloud_supervise_tick()` already does the right high-level thing:
  - mechanical relaunch first
  - advance only after durable facts say it is safe
  - refuse human prerequisite / quality gate / unmerged PR cases
- epic-chain should reuse that policy, but point it at:
  - the epic-chain session marker
  - the active child chain state referenced by `EpicChainState`

Operationally:

- dead epic-chain tmux session + resumable child state
  - restart the top-level session
  - top-level driver reloads meta-state
  - active child chain resumes from child state
- merged PR at child epic boundary
  - restart/wake the top-level session
  - top-level driver reconciles the completed child epic and advances
- human/manual-review boundary
  - do not auto-advance
  - surface the active child epic id and child plan name in the report
  - keep any existing manual-review or Discord escalation path at the child
    plan/epic level

This matches the recent direction in `docs/cloud.md`: slot-first, recoverable,
mechanical relaunch only when state says it is safe.

## Base Branch And Branch Lifecycle Across Epics

Recommendation: default to an **advancing base branch**, not a fixed base SHA.

That matches current child-chain behavior:

- milestones already fork from refreshed `origin/<base_branch>` when pushing
- milestones already integrate locally onto `base_branch` in `--no-push` mode
- downstream work is expected to build on the integrated output of earlier work

For epic-chaining, that means:

- epic N finishes by integrating onto `base_branch`
- epic N+1 starts from the same `base_branch` name, now at a newer commit
- the handoff commit from epic N becomes the minimum expected ancestor for
  epic N+1

Do **not** rewrite child chain specs at runtime in v1. Instead:

- the meta-spec may carry a top-level `base_branch`
- the driver validates that each child `chain.yaml` resolves to the same
  `base_branch`
- if a child epic intentionally diverges, treat that as an explicit special
  case, not the default program flow

`merge_policy` should remain a child-epic concern in v1:

- each child chain already knows whether it is `auto` or `review`
- the epic-chain driver should wait for authoritative completion and then move
  on
- no new top-level merge policy needs to be invented unless the product later
  wants a program-wide default/override

## Concrete Recommendation

Build a **thin `megaplan epic-chain` layer** with these rules:

1. New declaration shape
   - one YAML meta-spec listing ordered `epics:`
   - each epic points at an existing child `chain.yaml`
   - each epic after the first may declare `handoff_from_previous`
2. New persisted state
   - `.megaplan/plans/.epic_chains/<spec>-<digest>.json`
   - stores only the top-level cursor and boundary facts
   - child progress stays in existing child `ChainState`
3. New driver
   - `megaplan epic-chain start --spec ...`
   - `megaplan epic-chain status --spec ...`
   - internally calls the existing child chain driver/status surfaces
4. Failure semantics
   - child epic owns milestone retries/escalation
   - epic-chain default is `stop_chain`
   - optional `retry_epic` / `skip_epic`
5. Supervision
   - one top-level session/marker per epic-chain
   - existing chain/cloud/watchdog logic reused against the active child epic
   - mechanical relaunch-first stays unchanged
6. Base-branch policy
   - default sequential flow advances the shared `base_branch`
   - validate child specs; do not mutate them in v1

## What Already Exists Vs What Must Be Built

Already exists:

- child epic parsing, state, resume, and PR lifecycle
- child epic status classification
- child supervisor ladder
- cloud restart/advance/block policy

Must be built:

- `EpicChainSpec`
- `EpicChainState`
- `megaplan epic-chain start|status`
- handoff verification helper for `exists` / `contains_text`
- cloud/status adapter for the new top-level session type if first-class cloud
  launch/status is desired

Should not be built in v1:

- nested epic-as-milestone `chain.yaml`
- a second automatic escalation ladder above the child chain ladder
- runtime mutation of child `base_branch`
- a large cross-epic artifact validation language

## Bottom Line

The smallest principled design is: **one new meta-chain layer whose items are
existing child epics**.

That keeps the current `megaplan chain` contract intact, adds a durable answer
to “which epic are we on?”, makes handoffs explicit, and plugs naturally into
the existing supervision model without inventing a second orchestration system.
