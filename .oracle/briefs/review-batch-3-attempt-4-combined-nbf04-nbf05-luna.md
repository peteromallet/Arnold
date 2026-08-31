# Luna review brief — Batch 3 combined NBF-04/NBF-05 attempt 4

Perform a fresh, independent, read-only semantic and authority review of
`.oracle/rework/batch-3-attempt-4-combined-nbf04-nbf05.md` on branch
`reconcile/nbf-attempt4-2297`, against base/head
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`.

## Exact review bindings

- packet SHA-256: `7581ba43f39c6632a76253ae3c55e39e9f0aaefed044b7e6c347818861a94a99`;
- manifest `.oracle/rework/batch-3-attempt-2.manifest.tsv`, SHA-256
  `632acc64daf412220eafeb290f26431122b436a22a5b7aaf1c2a748ce27b2ec0`;
- framing script `.oracle/rework/nbf_batch3_attempt4_diff_v1.py`, SHA-256
  `daecdd4508a04f28a491786034aa9f649105d090bb7bd775a8bd6daf28aa49bc`;
- primary output `.oracle/evidence/batch-3-attempt-4-framed-diff.json`, SHA-256
  `058377715f7360217bafe629daa6ed95b3dc78985821cdadcc3129c7672f4263`;
- rerun output SHA-256 `058377715f7360217bafe629daa6ed95b3dc78985821cdadcc3129c7672f4263`;
- framed aggregate: `a12004073f638fe16813ce532efd2a3c779a34372d74943c945a6cc982e4db9a`;
- tasklist SHA-256: `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73`;
- Python evidence SHA-256: `16f567743b7556419c580d764286133ed1ef84754a6bb6602e6db1f77df42b72`;
- static/runtime evidence SHA-256: `4fcfca894edcaf1ef8734b8f5ca71715c38d8f54b681eb83b23f29318a7d8715`;
- inventory SHA-256: `44331a169f8f8b4d5ae6141c5fe905cd79691e404bdaaa0fbe72c16c45525bf1`;
- inventory source-input SHA-256: `60d5d933e722d8f49905b534866e1a2bdb6d0c7766103f3176adacd7cd33a958`.

Verify the two framed outputs are byte-identical, the 49 manifest entries are
exactly the current NBF04/NBF05 candidate paths, and the source snapshot is
stable before accepting any packet narrative.

## Review scope

Judge every actual NBF-04/NBF-05 Python and shell signal/death path against the
single canonical authority.  In particular, inspect and probe as needed:

- record-before-signal, distinct TERM/KILL claim and confirmation identities,
  consumed two-scan evidence, PID/start fencing, replay and crash cut-points;
- native timeout/stall, WBC/spawn certification, cleanup handoff custody,
  pre-acceptance hold, natural death, permanent-hold replay, and no-signal
  failure paths;
- unresolved-launch seven-field receipt binding and cross-reservation
  rejection, including retained-handle integrity and zero-write mismatch;
- marker/bootstrap manifest, runtime-head, progress, boot/container, and
  supervisor-incarnation reload/revalidation under one ledger lock;
- operator/fan controls' canonical workspace ledger and final pidfile,
  cmdline/group/process-start preflight;
- exact tmux socket/server/session/owned-pane identity, replacement rejection,
  typed acknowledgement, and non-tmux behavior;
- shell resolver invocation, explicit per-target authority, no ambient bypass,
  no second authority, and fail-closed missing-context behavior;
- generated inventory completeness/non-circular source digest, no-bare checks,
  Python compilation, and all targeted wrapper `bash -n` checks.

The accepted NBF-04 attempt-11 packet remains linked evidence at
`83f35cbc29f559d212fd1fc2bad8f8178fabd4d726bb30eafbc3c46a02c83071` with
framed aggregate `b3945b43cc62136d463745c2c18e2066ee7b1ff8a4d2d81b3c41b4a2c6963f4b`.
The current packet records project Python 3.11 safepath 1/1 PASS.  The
stripped Homebrew Python 3.14 optional-`fire` failure is an excluded
interpreter baseline, not candidate pass/fail credit.

## Exclusions and output

Do not count the contaminated `174 passed / 9 failed / 187 temporary-directory
errors` run. Exclude historical Batch-2 artifacts, NBF08 planning/rebind
artifacts, tasklist/status metadata, `evidence/m11-recovery-topology-surfaces.json`,
`babysitter-runs/`, demo receipts, and NBF-06 provider policy.  Counts from
overlapping suites are not additive.

Return exactly `PASS` or `REWORK` with concrete file:line evidence and any
reproducible probe output. Do not edit files, commit, push, merge, deploy,
touch `main`, launch NBF-06, or launch the epic.
