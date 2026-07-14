# Superfixer custody recovery — 2026-07-13

## Outcome

The canonical session `workflow-boundary-contracts-corrective-20260710`
recovered without state fabrication or guard relaxation. Plan
`c1-contract-reality-20260711-1433` is `done`; the chain completed milestone
S1 and advanced to `s2-contract-foundation-and-20260713-1544`. The current
runner was refreshed through managed operator pause/resume and imports Arnold
runtime revision `cd3128fcd425761bbc927a84ac78d53c6d5640e1`.

## Causal chain

- The original C1 loop began with strict gate-schema rejection of the model's
  unsupported `north_star_actions`, then later stopped in review with a dead
  worker PID.
- Watchdog/L1 accepted request `7473fa422fea89a936d0be64f25468524f0d7d0e1c8632478f5dcfc6ec37860e`
  without a typed failure or blocker identity. Claiming returned no custody,
  so the request accumulated zero claims and zero request-linked attempts.
- L2 returned early on the manual-review path instead of treating missing L1
  custody as a broken fixer. L3 repeatedly detected the missing meta-repair
  path, but its report-only boundary wrote to a queue the resident dispatcher
  did not consume.
- Status counted advisory sidecar activity as liveness even though the active
  plan worker was dead. A separate resident completion delivery used excess
  conversation context during semantic verification, allowing an older
  completion to compete with a newer restart turn even though transport reply
  correlation remained exact.

The first failed fixer was L1 request identity/claim custody. The first layer
that should have caught it was L2 meta-repair; L3 observed the recurrence but
had no executable handoff.

## Permanent changes

The pushed `editible-install` history through `cd3128fcd4` now:

- requires typed blocker identity at the L1 effect boundary and records bounded
  unclaimed retries/alerts instead of silently succeeding;
- routes L1 custody failures to L2, including unhealthy-session paths that
  previously fell through to relaunch;
- turns actionable L3 findings into stable, deduplicated requests in the
  central repair queue while keeping report rendering non-mutating;
- carries canonical session, marker, queue, and run-kind identity into every
  managed chain launch, including operator resume;
- routes lifecycle phase failures to the dispatcher-owned queue rather than a
  nested plan-local queue;
- preserves legacy untyped requests as visible accepted/unclaimed evidence,
  but never makes them dispatchable;
- terminalizes requests whose plan target has advanced, while preferring an
  explicit target plan so genuine human-gate requests are preserved;
- repairs dead review custody, archives superseded phase results, fixes review
  cap finalization, and prevents sidecars from establishing runner liveness;
- makes the deployed auditor source win over caller CWD and uses the current
  target resolver's real `workspace_hint` contract;
- limits resident completion semantic verification to the correlated turn,
  preventing an older completion from absorbing a newer restart request.

## Validation and deployment

- Progress-auditor suite: `112 passed`.
- Focused custody/L3/liveness/runtime/dead-review/resident delivery suite:
  `19 passed, 633 deselected`.
- Lifecycle queue routing: `7 passed, 8 deselected`.
- Advanced-target and operator-resume custody regressions: green.
- Phase-result recovery regressions: `6 passed, 28 deselected`; review-cap
  finalization regressions: `10 passed, 31 deselected`.
- Installed watchdog and auditor wrappers matched source hashes; repair trigger
  was refreshed from the same pushed branch.
- Managed runtime provenance after the final refresh reported import root
  `.megaplan/runtime/editable-engine`, source/runtime revision `cd3128fcd4`,
  and `ok=true`.

## Recovery evidence

- Fresh canonical runner identities: PID `1854068` first recovered C1; managed
  refresh then launched PID `2009128` with the four canonical repair-routing
  environment fields present.
- C1 state is `done`, has no active step or latest failure, and chain state has
  `completed_count=1`, current plan S2.
- S2 emitted fresh heartbeat/events and a post-refresh typed lifecycle request
  `ca1d74042d462d0eca8679ccc2f58a072ffa70639ce8b9628e987a120cbbbbb9`
  into `/workspace/.megaplan/repair-queue` under the canonical chain session.
- Legacy request `7473fa...` received terminal decision `stale` at
  `2026-07-13T15:58:26Z` because its target advanced from C1 to S2.
- L3 retro audit `/workspace/audit-reports/20260713T155345Z-audit.json`
  classified C1 as `done`, the successor as genuinely `RUNNING`, emitted typed
  central-queue findings, and separately retained the paused Discord sibling
  as an unresolved operator-resume case.

## Remaining operational state

There is no genuine human gate on the recovered WBC session. S2 is live but is
currently retrying a real gate output defect (`north_star_actions` is required
by the active schema but absent from model output). Its typed request is now in
central custody and must not be confused with the recovered C1 incident.

The resident service restart completed with a healthy new process, but its
durable restart-delivery record still says `restart_failed` with zero delivery
attempts. That unresolved delivery record is retained as evidence rather than
rewritten to imply success.
