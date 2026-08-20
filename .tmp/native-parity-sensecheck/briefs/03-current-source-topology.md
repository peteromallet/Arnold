# Lens 3 — current source/topology authority

Working directory: `/Users/peteromalley/Documents/Arnold`. Strictly read-only. Do not modify files. Audit the current checkout, including relevant uncommitted changes as current state, but note where that differs from sprint commits.

Inspect `arnold_pipelines/megaplan/workflows/workflow.pypeline` and every native subworkflow/policy it imports. Trace referenced components, handlers, metadata, route tables, lowering/compiler/runtime and CLI/auto-drive surfaces enough to classify every major Megaplan semantic as:

1. visibly source-authoritative in authored native topology;
2. declared natively but semantically completed elsewhere;
3. hidden in a component/handler/runtime/metadata/route table/CLI/auto-drive;
4. duplicated or contradictory authority;
5. absent.

Cover prep/research, plan, critique/revise loop, gate, tiebreaker/replan, execute DAG batching/fanin, approval, review/rework/human verification, finalize/fallback, override/abort/adopt/recover, suspend/resume, checkpoints, policies/model/timeout/retry settings, and typed outcomes. Find source constructs that are decorative or not honored by lowering/runtime. Return a dense matrix plus ranked gaps, each with exact `path:line` evidence and consequence/smallest corrective action. Do not accept imports, milestone claims, or generated reports as proof of semantic authority.
