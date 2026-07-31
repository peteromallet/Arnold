# Post-M11 ticket reconciliation

Reconciled against consolidated source `6e60b31fbf`, the integrated M10/M11
lineage, post-M11 stabilization commits, and the finalized Milestone Gates,
Native Parity, Workflow Platformization, and Critique Ledger initiative
sources.

The rule used here is strict: implementation evidence can justify an
`addressed` status only when the ticket's full scoped acceptance is proved.
Partial code, unit coverage without the required archived/live replay, or a
successor epic that merely consumes the contract does not manufacture closure.
All successor links below are association-only unless explicitly stated.

| Ticket | Disposition | Actual owner / residual |
|---|---|---|
| `01KTH21DTP` stale hooks | Addressed | Integrated self-check, refresh, worktree resolution, tests |
| `01KTPVSH8` unresolved route | Addressed | Integrated fail-loud neutral-executor behavior and tests |
| `01KYSXVF1` malformed ticket discovery | Addressed | Integrated tolerant parser, isolation, and discovery tests |
| `01KYPNKB5` ready-wave full-suite | Addressed now | Terminal-frontier fix, focused regression, and archived production proof complete the narrow scope |
| `01KYV57FAP` opaque pytest node IDs | Open, immediate release blocker | The original whitespace/status-word repair landed, but the `1a10886218` exact run exposed inherited-test `nodeid <- source.py` provenance as a second accounting gap; parser fix and exact final full-inventory rerun remain |
| `01KYTANWK` graph-admission duplicate | Dismissed | Canonical scope remains in `01KYMTMKX` |
| `01KYMTM93` force-proceed custody | Open, immediate residual | Code is integrated; exact archived M11/WBC replay remains. Native S6 consumes it; Critique Ledger does not own it |
| `01KYMTMKX` graph admission | Open, immediate residual | Candidate admission/circuit breaker integrated; archived graphs, normalization, crash/CAS, semantic-hash, and status proof remain |
| `01KYMTN1T` timeout preservation | Open, immediate residual | Original call-site fixed; persistence, multi-batch, hash, and trace proof remain |
| `01KYMWFKQ` fixer custody containment | Open, immediate residual | Canonical custody, liveness, bounded projection, and handoff landed; exact singleton live replay remains |
| `01KYPNKC2` launch envelope | Open, immediate residual | Railway persistence, pinned sibling repair routes, and content-addressed container-boot source selection landed through `98056ca183`; canonical envelope/resident rotation/trusted-container/provider preflight and final live selector/canary proof remain |
| `01KYPNKD0` receipt repair | Open, immediate residual | CAS successor/no-body-replay landed; archived fixtures and hostile path/write semantics remain |
| `01KYPT8PS` nonterminal runner exit | Open, immediate residual | Dead-PID and handoff prerequisites landed; adoption/replacement of a pre-existing noncanonical runner remains |
| `01KYQ1CN4` canonical timeline | Open, split | Bounded checkpoint substrate landed; current product view is immediate/Native S6, later extraction may use Platformization without auto-closing |
| `01KYSBGRH` release consolidation | Open, release umbrella | Closes only after one pushed/deployed vector, validation/runtime/canary proof, cleanup evidence, and Native S1 handoff |
| `01KYT4ZMF` bounded replay/watchdog | Open, immediate residual | Compatibility implementation and 488 focused tests landed; production prebuild/canary, consumer audit, and watchdog re-enable remain |
| `01KYT5MGM` review/rework admission | Open, immediate residual | Typed reducer landed; final pre-dispatch CAS and exact review-v10 replay remain; Native S5 absorbs later |
| `01KYSS5QA` completion specs | Open, promoted/split | Native C1/C2/S2R/S5 implements it; Platformization extracts/certifies it; retired independent chain is not launchable |
| `01KTH21EX` stale-step recovery | Open, immediate residual | Several prerequisites landed; structured leases, bounded retry policy, schema terminality, and full golden/live proof remain |
| `01KTH21EC` compact monitor | Open, standalone | No conforming monitor CLI exists yet |
| `shannon-claude-2-1-169` | Open, standalone | Pane-based detector/self-defending interactive guard remains; no current epic honestly resolves it |

## Epic ownership conclusions

- **Native Parity** is an associated consumer for completion, finalization,
  review/rework, recovery-control, and projection fixtures. Pre-launch release
  residuals use `resolves_on_complete: false`.
- **Workflow Platformization** owns reusable extraction, authoring experience,
  public certification, and the unrelated second-consumer proof. It does not
  retroactively own current cloud launch, credential, fixer, or product-status
  defects.
- **Critique Ledger** owns cumulative semantic finding identity,
  reconciliation/dispositions, bounded briefings, and its cutover. None of the
  post-M11 task-graph, write-set, force-proceed, runner, or recovery-envelope
  tickets is honestly Critique-owned.
- The retired **Standardized Completion Specifications** initiative is a
  requirement index only. Its ticket is promoted into Native Parity and
  associated with Platformization; that archival chain must never be launched.

## Duplicate and closure policy

`01KYTANWK` remains the only confirmed recent duplicate and points to
`01KYMTMKX`. The narrow ready-wave symptom is now addressed rather than being
kept open by the broader release-validation umbrella. No other partial
implementation or successor relationship is treated as completion.

The release-discovery run at `1a10886218` reopened `01KYV57FAP`: shard 004
executed 852 passing tests, but the terminal parser admitted only 810 because
42 inherited conformance cases carried pytest's ` <- definition-source.py`
provenance suffix. This is an evidence-accounting defect, not a product-test
failure. Closure requires a frozen-inventory-aware parser fix plus a complete
exact rerun on the final release revision; focused tests alone do not restore
`addressed`.

## 2026-07-31 release-preflight addendum

The final image preflight found a concrete launch-envelope defect not visible
in the earlier code-only reconciliation: the generated container entrypoint
hard-coded heartbeat and watchdog wrapper execution to the mutable
`/workspace/arnold` checkout and gave the resident that checkout as its tmux
working directory. The live checkout is dirty and is not the selected
content-addressed runtime, so container replacement could revive recovery
authority from the wrong source.

Commit `98056ca183` makes all three boot services resolve and enter the same
quoted runtime source selected by `MEGAPLAN_RUNTIME_SRC`, falling back to
`CLOUD_WATCHDOG_ARNOLD_SRC` and only then `/workspace/arnold`. Rendering,
fallback, hard-coded-path negative, host-ensure compatibility, Bash syntax,
Ruff, compile, and diff checks passed. This is a landed subcase of
`01KYPNKC2`, not ticket closure: the final live selector rewrite, service
cutover, runtime provenance, ten-minute/three-cycle canary, resident rotation,
trusted-container, credential-channel, and provider-preflight evidence remain
required.
