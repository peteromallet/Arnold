# Evidence, provenance, and landed-versus-proposed audit

## Superseding rollout decision

The original evidence below records the proposal as it existed before the
user's coordinated-cutover decision. Current authority lives in the epic README,
North Star, five-milestone chain, briefs, WBC annex, and M6 validation gates.
Canary, prolonged shadow/report-only authority, broad mixed-version support, and
multi-boundary rollback are historical proposals, not current roadmap work.

## Canonical source and import custody

The scope anchor is
`../session-knowledge-compiler/briefs/domain-specific-critique-finding-ledger.md`, titled **Cumulative
Domain-Specific Critique Finding Ledger**. It was copied byte-for-byte from the
untracked canonical initiative material in `/workspace/arnold` into the clean
isolated worktree based on
`e5b7a2b29b074b407818c07bad795459f57ca321`. Source and imported SHA-256 are both
`889f0f7e67e395d1f9b7a45336ddabac4ec49f940d8874ddabf0a9e094f022bc`.
Only that source artifact was imported; the stale checkout's README and broader
Session Knowledge Compiler chain were not copied.

After the recorded target advanced, that isolated planning commit was replayed
without conflict onto a second clean worktree based on
`3c49e9ef7ecf747a959131d1c53d574207a798de`. The final durable commit and local
integration evidence therefore bind the newer recorded base; the earlier SHA is
retained only as exact import-chain provenance.

## Authoritative conversation evidence

Conversation `rconv_85a1c2bfd5f1` was searched through the resident scoped
conversation route with targeted queries including `cumulative finding ledger`
and `no additional findings`. Raw message records establish:

- `msg_742eb5f14076` at `2026-07-16T20:24:09.101839Z`: cumulative carry-forward,
  explicit dispositions/rationale/evidence/reopen conditions, separate ledger
  reconciliation versus novel discovery, and valid no-additional-findings.
- `msg_fb1babd8e3c3` at `2026-07-16T20:27:09.960616Z`: chooses evaluator-routed
  domain critics and requires WBC-aware implementation planning.
- `msg_a6fc1642ec09` at `2026-07-16T21:00:24.266035Z`: records the converged
  architecture, M6 validation stages, and missing WBC annex.
- `msg_45e16eba8e82` at `2026-07-16T21:03:59.250958Z` and
  `msg_3814a676278e` at `2026-07-16T21:05:36.384784Z`: correct scope to critique
  improvement specifically, not the parent compiler roadmap.

## Prior raw runs

- `subagent-20260716-202849-a282ad85` produced the 730-line source brief and
  result, but its manifest ended `failed` with return code 2 because the strict
  git-custody receipt was missing. Its prose is not completion proof; its raw
  log, manifest, exact file hash, and cited M6 artifacts are evidence inputs.
- Dependent run `subagent-20260716-202925-3e95d055` has `started_at: null`, no
  dispatch, no run log, and an empty result. It failed closed with `queued
  successor dependency failed closed`; therefore it supplied no WBC integration
  or implementation breakdown.

## Landed/current behavior

The recorded target contains WBC merge
`24afce006b9ad20391ac7af10ef67ea0b1774f9f` and completed WBC tip
`cbe69337d6f469fd7ae12f1fd0a51007d93b5d70` as ancestors. The landed tree
contains `arnold/workflow/execution_attempt_ledger.py`, payload policy,
boundary compatibility/conformance/evidence/templates, support/ownership
matrices, Megaplan boundary contracts/receipts, semantic health, fixtures, and
focused tests. The WBC merge evidence reports compile success, 259 bounded
regressions, and 1,799 focused WBC tests at integration time. Those historical
claims were checked against commit ancestry and current files; they are not a
claim that this critique-ledger feature is implemented.

Current critique runtime provides evaluator-selected lenses and skip reasons,
parallel producer outputs, canonical content-derived occurrence IDs,
per-iteration custody receipts with zero-loss checks, flag lifecycle, revision
metadata, gate signals/carry, and finalize resolution coverage. Later critic
templates carry only the immediately prior active check's findings/status.
`compute_recurring_critiques` intersects normalized concern strings from the two
adjacent critique artifacts. These are useful substrates, not a cumulative
semantic ledger.

## Proposed behavior and unknowns

Everything under this scoped epic—cumulative semantic identity, append-only
reconciliation/disposition events, full domain briefings, optional blind plus
mandatory history-aware passes, model-led semantic deduplication, honest gate
claims, and coordinated cutover/retirement—is proposed. CL1 must still decide the
exact stored-versus-projected disposition mapping, evaluator-versus-curator
split, stable semantic identity representation, privacy/retention class,
historical unknown behavior, and the replacement UX for exact-text recurrence.
No sprint may treat an open question as already landed.
