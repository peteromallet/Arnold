# M7: Completion, GitHub, And Cleanup

Overall plan difficulty: 5/5; selected profile: partnered-5; because this milestone crosses operation state, GitHub, approvals, cleanup contracts, and destructive-action boundaries.

## Outcome

Track branch/PR/CI/completion state and expose cleanup/consolidation as an approval-gated AgentBox capability over Arnold reconcile contracts.

## Scope

In:

- add or use operation fields/resources for pushed branch, PR number/url, CI status, and cleanup state;
- finalize immediate completion DM format;
- validate GitHub auth before offering push/PR actions;
- implement or stub operation policy for draft PR creation/update;
- define Arnold reconcile finding/decision/final-state contract;
- productize cleanup-loose-branches as a remote-safe `agentbox cleanup survey` command/tool;
- route merge/delete/park through resident confirmation/approval mechanisms;
- record cleanup decisions as operation/audit events.

Out:

- enterprise PR dashboards;
- auto-merge by default;
- multi-user approvals;
- cleanup of unrelated repos without explicit survey and approval.

## Locked Decisions

- No direct push to main.
- Merge/delete/reset require explicit approval.
- cleanup-loose-branches is the consolidation policy source.
- AgentBox owns the cleanup command/tool implementation; Arnold owns only neutral reconcile findings, approvals, and final cleanup state.
- Orphaned worktrees/branches are surveyed, not silently deleted.
- Cleanup descriptors can be operation-kind-specific.

## Open Questions

- Whether draft PR creation is automatic per operation policy or offered in the completion DM for v0.
- Exact GitHub interface: CLI, connector, or existing chain git helpers.
- How much CI detail belongs in Discord vs logs.

## Constraints

- Destructive cleanup is never automatic.
- GitHub credential is validated before offering push/open PR.
- Approval replies must match a pending confirmation and the same authorized Discord user.
- Cleanup survey must classify land/delete/park with evidence.

## Done Criteria

- Completed operation DM includes summary, validation, branch/PR status, and next action.
- Cleanup survey reports land/delete/park recommendations.
- Merge/delete/reset require approval.
- Failed GitHub auth produces a fix command instead of a broken action.
- Tests cover parked branch, merged branch, dirty worktree, and orphaned worktree cases.

## Touchpoints

- `chain/git_ops.py`
- `supervisor/pr_merge.py`
- GitHub CLI or connector paths
- resident confirmations
- cleanup-loose-branches algorithm/productized command
- Arnold reconcile contract

## Anti-Scope

- No broad branch deletion.
- No auto-merge default.
- No web dashboard.
