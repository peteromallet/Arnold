# Execute fan-out with conflict custody — North Star

Ship a bounded, observable Execute scheduler that can run independent tasks in
parallel without sharing mutable worktrees, silently overwriting changes, or
allowing an unresolved conflict to reach Finalize or acceptance.

The end state is deliberately conservative: safe disjoint work can fan out;
uncertain or overlapping work is serialized or held for an explicit resolver.
Every worker returns a versioned result and evidence, one reducer owns the
merge decision, and the plan remains blocked until the reducer has produced a
clean merge receipt and the acceptance gates pass.
