# M3: Chain Policy And Cloud Effective Status

## Outcome

Add chain-level policy support and accurate cloud chain status. Operators should see effective state without manually comparing chain state, plan state, process liveness, logs, PR state, and checks.

## Scope

IN: parse `prerequisite_policy`, `validation_policy`, and `review_policy.clean_milestone_pr`; propagate policy into initialized plans; add runtime policy override command shape; define branch/PR synchronization status separately from review policy; report branch head, PR head, last pushed commit, dirty classification, and stale/clean sync state; extend cloud preflight for validation-environment capabilities; implement effective `cloud status --chain` payload merging chain, plan, heartbeat, runner, log, and PR information; add tests.

OUT: long-running supervisor loop and real provider/GitHub dependencies in tests.

## Locked Decisions

PR synchronization answers whether the milestone PR is up to date. PR policy answers whether to mark ready, pause, merge, or continue. Cloud status is read-only and should report stale bookkeeping separately from live state.

## Done Criteria

New policy fields parse; runtime policy can be set without editing YAML; status distinguishes PR sync state from PR policy state; effective status classifies running, awaiting PR merge, true human prerequisite, recoverable quality gate, and stale bookkeeping.
