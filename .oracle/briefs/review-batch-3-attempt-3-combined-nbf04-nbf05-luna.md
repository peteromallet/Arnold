# Luna review brief — Batch 3 combined NBF-04/NBF-05 attempt 3

Review `.oracle/rework/batch-3-attempt-3-combined-nbf04-nbf05.md` read-only on
branch `reconcile/nbf-attempt4-2297`, based on
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`.

Bind the review to:

- packet SHA: `cdc710c44e256ad05cd487eeae487374fa476b03146b743da8e7f6a023cdc864`;
- manifest `.oracle/rework/batch-3-attempt-2.manifest.tsv`, SHA
  `632acc64daf412220eafeb290f26431122b436a22a5b7aaf1c2a748ce27b2ec0`;
- script `.oracle/rework/nbf_batch3_attempt3_diff_v1.py`, SHA
  `a0b9cb88e60310486e09d5096c115550d4e4e7b41a8626dcd4ac270f85913bbb`;
- framed output SHA
  `5aa29092a49e6d4920798db46c217c2d64a3a3bff1ca2a8d97f20e49e09c713a`;
- aggregate `f28e039c23b74b37b752ef4527ef1d8878953f21537ca9b23d1c2f1f21686991`;
- tasklist SHA
  `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73`.

Verify the exact 49-path manifest, deterministic two-run framing, source
stability, and the NBF04/NBF05 authority contract: record-before-signal,
distinct TERM/KILL claims and confirmations, replay/crash closure, WBC
custody, marker/bootstrap reload, one-lock final preflight, exact tmux
socket/server/session/pane binding, shell canonical resolver use, operator/fan
fail-closed behavior, and no ambient or second authority.

The post-fix wrong-process-handle checks must prove that both controlled
`signal_ladder` and `immediate_timeout` return typed unresolved before any
poll/signal when handle PID B is supplied for admitted child A. The admitted
child path must still deliver the authorized teardown. The optional `fire`
stripped-environment baseline failure is explicitly excluded; overlapping
suite counts are not additive.

Exclude NBF06, NBF08 implementation, historical Oracle/evidence outputs,
`babysitter-runs/`, demo receipts, and quarantined M11 material. Return PASS or
REWORK with exact file:line evidence. Do not edit, commit, push, merge,
deploy, touch main, or launch an epic.
