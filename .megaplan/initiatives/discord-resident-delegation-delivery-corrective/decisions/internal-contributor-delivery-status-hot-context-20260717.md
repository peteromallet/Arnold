# Internal Contributor Delivery Status and Hot Context

## Decision

`internal_contributor` describes aggregation only. It never proves a result is
non-deliverable. Resident manifests and projections use
`arnold-resident-delivery-status-v2` to separate:

- work: worker lifecycle and the explicit `worker_completed` terminal fact;
- delivery: independently resolved delivery policy and provider/outbox state;
- request: aggregation progress and the explicit `request_delivered` fact.

Launches record an outcome contract. Independently meaningful repair, deploy,
integration, activation, proof, coding, debugging, migration, or autonomous
execution defaults to independent terminal delivery even when its aggregation
role is `internal_contributor`. Intentional nondelivery requires a durable,
bounded override reason. Ordinary analytical fragments remain suppressible and
feed the single synthesis owner normally.

## Projection and migration

New manifests persist `execution_contract` and `lifecycle`. Existing v1
manifests remain readable: the resident deterministically projects missing
dimensions and labels them as migration projections. Historical completed
execution contributors whose delivery is `suppressed` or `superseded` are
attention, not silently reclassified as delivered.

Queued fan-in projections ignore embedded `predecessor_states` as authority.
They resolve every predecessor from its current durable manifest, retain a
stale-snapshot diagnostic, and calculate request delivery separately from work
completion. Deterministic attention codes cover:

- `completed_independent_result_suppressed`;
- `completed_result_hidden_by_predecessor`;
- `unrelated_execution_predecessors_all_success`;
- `delivery_owner_abnormally_waiting`;
- `failed_predecessor_hides_success`.

## Regression custody

The focused fixture seeds the observed failure shape: a useful repair
contributor is completed and suppressed; an unrelated sibling remains running;
an all-success synthesis owner waits on both; and its embedded predecessor
snapshot is stale. Assertions prove current manifests replace the stale state,
the hidden result reaches `context_root.attention`, `worker_completed` is true,
and `request_delivered` remains false. Companion cases cover analytical
suppression with normal synthesis, failed fan-in, abnormal owner wait, and an
explicit execution nondelivery override.

## Source custody

- recorded integration target: `refs/heads/main` at launch revision
  `44441636f125ad490dd12adba8254462c15ea48f`;
- separately pinned resident runtime/source checkout: detached
  `6788980da951004b25686364b0d1a0426b024899`, locally named by
  `fix/critique-ledger-runtime-recovery-20260717`;
- the two revisions have merge base
  `612b139971e1a65d2a40f9e387a5e8ff3e2ab960`; the pinned runtime checkout is
  not the integration target and is not updated by this local integration;
- implementation worktree:
  `/workspace/arnold-resident-delivery-status-20260717` on
  `feat/resident-delivery-status-hot-context-20260717`.

Exact verification commands and the final commit/integration revisions are
recorded in the delegated git-custody receipt for this request. No push,
deployment, or resident restart is part of this decision.

## Verification at implementation head

- `python -m py_compile arnold_pipelines/megaplan/resident/delivery_status.py arnold_pipelines/megaplan/resident/subagent.py arnold_pipelines/megaplan/resident/profile.py arnold_pipelines/megaplan/resident/context_tree.py tests/resident/test_delivery_status_hot_context.py` — passed.
- `pytest -q tests/resident/test_delivery_status_hot_context.py tests/resident/test_query_relationship_and_aggregation.py tests/resident/test_launch_subagent.py tests/resident/test_context_tree.py tests/resident/test_subagent_terminal_delivery_contract.py` — 73 passed.
- `pytest -q tests/resident/test_megaplan_initiatives.py::test_megaplan_resident_hot_context_includes_compact_initiative_index tests/resident/test_vp_todo_tools.py` — 17 passed.
- `git diff --check` — passed.

A wider seven-file run produced 105 passes and two failures in pre-existing
local epic-chain hot-context assertions. Running those exact two tests in a
temporary untouched worktree at launch base `44441636f125...` reproduced both
failures byte-for-byte (`KeyError: epic_chains` and `KeyError: active_chains`),
so they are recorded as launch-base failures, not regressions from this change.
