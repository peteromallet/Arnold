# Luna review brief — Batch 3 combined NBF-04/NBF-05 attempt 5

Perform a fresh independent read-only review of
`.oracle/rework/batch-3-attempt-5-combined-nbf04-nbf05.md` on branch
`reconcile/nbf-attempt4-2297`, against base/head
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`.

## Exact bindings

- packet SHA-256: `8481da7b8575d98ba4019e1620cfc72b1a9b6b2f26e93e942ce0cdf473e4e792`;
- manifest `.oracle/rework/batch-3-attempt-2.manifest.tsv`, SHA-256
  `632acc64daf412220eafeb290f26431122b436a22a5b7aaf1c2a748ce27b2ec0`;
- framing script `.oracle/rework/nbf_batch3_attempt5_diff_v1.py`, SHA-256
  `cfcf70916329ad9301ac70278389f49df9620363606281b715962b5536178cc0`;
- primary and rerun output SHA-256:
  `358bc185d04937b85ee1d886d2fb9e8bbd43b592b663ccf9a3f444c166ae14a3`;
- framed aggregate: `7f134a29fee76c1f68436798482dca46a301a380456c0793ce3b2b0ecf80c958`;
- tasklist SHA-256: `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73`;
- Python evidence SHA-256: `6ce40640ad901186936285da8861dcefd22d7de4f97985410de3ce726bc3930a`;
- static/runtime evidence SHA-256: `e56ab2c88a21189d05eab78e672462c7dde54b69586ebb744c483a6c1a4808d5`;
- inventory SHA-256: `e92b6c90c6adf7c6d5f05a8d10c888f4900b1a2395cf35ce55689323987568da`.

Verify the 49-path manifest is exact, both outputs are byte-identical, and
the source snapshot is stable before evaluating the packet narrative.

## Required semantic review

Judge NBF-04 and NBF-05 only. Trace every real Python and shell signal/death
path through the single canonical authority and inspect:

- record-before-signal, distinct TERM/KILL claims and confirmations, consumed
  two-scan evidence, PID/start fencing, replay and crash closure;
- native timeout/stall, WBC/spawn certification, cleanup handoff custody,
  pre-acceptance natural death/permanent hold, and no-signal failure paths;
- unresolved-launch receipt fields, cross-reservation rejection, retained
  handle validation, and zero-write mismatches;
- marker/bootstrap/manifest, runtime-head, progress, boot/container,
  supervisor-incarnation and one-lock final revalidation;
- canonical operator/fan ledger binding and locked pidfile/cmdline/group/start
  preflight;
- exact tmux socket/server/session/owned-pane proof and replacement rejection;
- explicit shell resolver authority with no ambient bypass or second ledger;
- action-aware inventory discovery, non-circular source digest, no-bare,
  compile, and all wrapper `bash -n` checks.

The attempt-4 packet is superseded. Sol's prior REWORK history must remain
visible as history, not be converted into acceptance evidence. Evaluate the
new generator/tests/artifact and action-aware inventory changes on their own;
no second Sol judgment was commissioned for this segment. The project Python
3.11 safepath PASS is valid evidence. The stripped Homebrew Python 3.14
optional-`fire` failure is outside the manifest and receives no candidate
pass/fail credit.

Exclude NBF-06, NBF-08 implementation, tasklist/status metadata, historical
Oracle evidence, M11 material, `babysitter-runs/`, demo receipts, and the
contaminated `174 passed / 9 failed / 187 temporary-directory errors` run.
Overlapping suite counts are not additive.

Return exactly `PASS` or `REWORK` with reproducible file:line evidence. Do
not edit, commit, push, merge, deploy, touch `main`, or launch the epic.
