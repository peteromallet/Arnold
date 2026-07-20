# Three-hour babysitter agent-awareness deployment receipt

All control-plane and evidence timestamps in this receipt are UTC.

## Schedule mutation

- Schedule: `sched_pinned_e894_epics_babysit_3h`
- Observed CAS revision before update: `7`
- Supported operation: `resident schedule update --if-revision 7`
- Returned revision: `8`
- Generation: `1` (unchanged; timing was not revised)
- State: `active`
- Prompt reference: `resident-schedule://sched_pinned_e894_epics_babysit_3h/prompt-v3`
- Prompt digest: `sha256:e4edf81f486293502cc461c7432233bddc8427aa3024e4a2fa3faed022a7cc3c`
- Definition updated at: `2026-07-20T19:49:47.039108Z`
- Definition receipt event hash: `sha256:883659d525fd7aeffc53d8726ced16d1ed285abbd6e18e66ac53acf9126a2f4c`
- Definition digest: `sha256:f14b0ba91c3e11b163aebe3b6399ddb5aca8e57e60e7f555bdf91a3528916c0e`
- Fresh read: enabled, fixed delay `PT3H`, next trigger
  `2026-07-20T21:26:52.164301Z`

The update preserved the immutable authorization grant and delivery route,
all three target sessions/workspaces/specs/markers, the existing model and
profile, the pinned-runtime/non-regression requirements, and the global
one-at-a-time controls (`overlap=forbid`, `max_active=1`, and the existing
concurrency key).

The scheduler consumes the current stored definition when materializing the
next fixed-delay occurrence. Because revision 8 remained active and the fresh
projection is enabled with a next trigger, no resident restart or service
relaunch was required.

## Policy verification

The embedded policy requires explicit session/chain/workspace plus
blocker/recovery-objective matching. It defines substantive evidence, excludes
PID/heartbeat/liveness-only evidence, uses a 6-hour freshness window, and
requires both a 12-hour no-substantive-progress bound and a verified better
route before time can contribute to replacement. Insufficient evidence maps to
`hold_uncertain_no_duplicate`, never cancellation.

A deterministic decision-table check passed these cases:

- active on-path Custody candidate -> `defer_to_agent`
- unrelated session/workspace/blocker candidate -> `unrelated`
- stale candidate without a verified better route ->
  `hold_uncertain_no_duplicate`
- terminal failed matching candidate -> `replace_agent`
- no candidate -> `repair_without_candidate`

Schedule schema/digest preview passed before CAS update. A fresh post-update
read verified the prompt linkage, Custody run linkage, active/enabled state,
revision, generation, timing, model/profile, authorization, and concurrency
controls.

## Custody candidate assessment

- Assessment time: `2026-07-20T19:50:56Z`
- Candidate: `subagent-20260720-193054-5b0373d2`
- Classification: `defer_to_agent`
- Match basis: its declared task explicitly binds
  `custody-control-plane-20260714`, the stopped Custody recovery, and the
  provider-timeout/fallback blocker. Its project/runtime root is the pinned
  e894 checkout and its isolated implementation worktree is linked by its
  durable artifacts.
- Fresh substantive evidence: commit
  `e5b2327734705f298cd2ee7c3d925706d135468b` at
  `2026-07-20T19:45:56Z`; focused and relevant regression evidence including
  `280 passed, 1 deselected`; git-custody receipt written at
  `2026-07-20T19:47:23.632251756Z`; recovery-gate evidence written at
  `2026-07-20T19:50:06.829817739Z`.
- Decision: no duplicate Custody repair, no cancellation, no takeover of its
  source changes, and no independent Custody resume.

The candidate's recovery evidence says the Custody runner remains stopped and
the fix is not active in the relaunch runtime because its own target-ref gate
is unresolved. This receipt therefore does not claim the Custody chain has
recovered.
