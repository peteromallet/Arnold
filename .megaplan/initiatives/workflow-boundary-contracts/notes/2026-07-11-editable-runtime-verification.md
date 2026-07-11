# Editable auto-repair runtime verification — 2026-07-11

Session: `workflow-boundary-contracts-corrective-20260710`  
Plan: `c1-contract-reality-20260711-1433`

## Outcome

The live machine was split across three Arnold sources: the WBC target checkout at
`432760d13`, a detached dirty watchdog/resident source at `d3bac006c`, and the
installed editable mirror at stale detached `4291bf630`. Commit `cfe3b25ee`
was absent from all three effective sources. There was no second installed wheel,
but cwd/PYTHONPATH shadowing overrode the editable metadata.

The authoritative repair runtime is now the local, unpushed worktree
`/workspace/wbc-c1-root-corrective-20260711`. The system editable
`direct_url.json`, watchdog, repair loop, resident PYTHONPATH/cwd, and isolated
`python -P` probes all resolve there. Automatic source sync is disabled while
this local corrective branch is intentionally ahead of `origin/editible-install`.

## Code boundary

`cfe3b25ee` is primarily the secondary-recovery fix: typed quality failure
evidence, one bounded L1 attempt, shared request/claim/attempt custody, durable
accepted-unclaimed retries, typed human-only gates, unknown/broken-superfixer
separation, and stale-marker precedence.

Primary prevention also depends on its ancestors and forward ports:
`3ff595994`/`7aec506ad` prevent the repeated gate payload failure, revalidate
repair targets, preserve typed fallback reasons, route direct relaunch, and reject
false/self-observer/phase-stale liveness; `15d09c3c7`, `75b2fbd20`, and
`83ba03b4c` harden stale status/chain/cursor and relaunch precedence.
`41658c0a9` adds a fail-closed import/editable/revision provenance gate and a
real editable venv + `python -P` cwd-shadow integration test. `455b25920`
accepts a pinned Git worktree as valid source metadata without treating it as a
missing checkout.

## Verification

- 318 focused recovery/status/human-gate/liveness tests passed.
- 12 editable provenance/install tests passed, including the isolated venv
  subprocess and Git-worktree source test.
- Wrapper shell syntax and `git diff --check` passed.
- The broader historical wrapper sweep was stopped after 91 passes and 12 known
  branch-drift failures (obsolete wrapper-string and removed queue-helper
  expectations); it is not represented as globally green.
- The first live watchdog projection emitted `dispatch_l1_repair` for WBC.
  Because the accepted request lacked a canonical blocker ID, it remained visible
  and recorded bounded `claim_retry`; no `needs_human` marker or Discord
  notification was created. One canonical relaunch fallback ran and immediately
  preserved the blocked state; no duplicate WBC worker remained.

## Current state and residual risk

C1 remains milestone 0/in progress. Chain state says `blocked`; plan state says
`executed` with a stale dead review `active_step`, `manual_review` cursor,
and no typed `latest_failure`. The current artifact predates typed persistence,
so it correctly fails closed and is not retroactively relabeled as a human gate.
No force-proceed or gate bypass was used.

Equivalent future structured deterministic quality/import failures are prevented
where normalization/provenance can reject them early; if they still occur, they
are eligible for exactly one bounded L1 repair. Ambiguous legacy evidence,
missing canonical blocker identity, destructive actions, credentials/accounts,
approvals, policy/legal gates, and product decisions are not auto-mutated.
Unknown automation remains broken-superfixer/attention, not human-required.
