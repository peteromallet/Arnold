# Luna review brief — Batch 3 combined NBF-04/NBF-05 attempt 2

Review `.oracle/rework/batch-3-attempt-2-combined-nbf04-nbf05.md` as a fresh,
read-only integration and authority review on branch
`reconcile/nbf-attempt4-2297`, based on
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`.

Bind the review to:

- packet SHA-256 `d0eeffa61c4e3cdebc3a449563eca02c87a4e68913e5ba12bd327bc899cae986`;
- classified 49-path manifest `.oracle/rework/batch-3-attempt-2.manifest.tsv`,
  SHA-256 `632acc64daf412220eafeb290f26431122b436a22a5b7aaf1c2a748ce27b2ec0`;
- framing script `.oracle/rework/nbf_batch3_attempt2_diff_v1.py`, SHA-256
  `fd03bfc92561dfe0a648cc79dd48187fddfeae65d8be905469d88a0cf9eadb43`;
- framed output `.oracle/evidence/batch-3-attempt-2-framed-diff.json`, SHA-256
  `85d3317efcedbd53bb864f90d93e3bce1c23e87903906af07dd8b81c19766317`;
- aggregate `8f732a1984fbcfd7b52aef05e5d33c2baec2802dc3fdb508ec0469694bf66046`;
- tasklist SHA-256
  `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73`.

Verify that the output reproduces twice, that the 49 entries are exactly the
current NBF04/NBF05 source/test/docs set, and that no source content changed
during framing.

## Review scope

Judge only NBF-04 and NBF-05. Trace every real Python and shell signal/death
path through one canonical ledger/disposition authority. Verify:

- record-before-signal ordering, distinct TERM/KILL identities, consumed
  PID/start-bound confirmations, replay and crash closure;
- WBC/native cleanup custody, pre-acceptance holds, natural death,
  permanent-hold replay, cross-adapter mismatch rejection, and no-signal
  failure paths;
- marker/bootstrap/manifest/runtime-head/progress/boot/container/supervisor
  source revalidation under the ledger lock;
- exact tmux socket/server/session/owned-pane identity, replacement rejection,
  typed acknowledgement, and non-tmux admissibility;
- shell bridge invocation of the canonical resolver, no ambient-context
  bypass, no second authority, and zero signal on missing or failed context;
- inventory discovery, classification, deterministic non-circular source
  digest, no-bare checks, and all wrapper syntax.

The accepted NBF-04 attempt-11 packet remains linked evidence at
`83f35cbc29f559d212fd1fc2bad8f8178fabd4d726bb30eafbc3c46a02c83071` with its
25-path manifest and `b3945b43...` aggregate. The supplied attempt-2 Python
evidence records 435/435 passed and the static/runtime evidence records the
compile, six-wrapper syntax, inventory, authority/tmux, and diff checks.

## Explicit exclusions

Do not count the contaminated `174 passed / 9 failed / 187 temporary-directory
errors` run. Exclude historical Batch 2 artifacts, NBF08 planning/rebind
artifacts, tasklist/status metadata, `evidence/m11-recovery-topology-surfaces.json`,
`babysitter-runs/`, and demo receipts. Do not evaluate NBF06 provider policy or
NBF08 implementation in this review.

Return `PASS` or `REWORK` with exact file:line evidence. Do not edit, commit,
push, merge, deploy, touch main, launch NBF06, or launch the epic.

