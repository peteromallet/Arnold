# Batch 3 combined NBF-04/NBF-05 candidate — attempt 1

## Freeze and scope

This packet freezes the shared dirty-tree candidate on branch
`reconcile/nbf-attempt4-2297`, built directly on base
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`. The candidate combines the
completed NBF-04 native custody/disposition work with the NBF-05 Python
authority, producer, and shell-supervision work present in the tree.

NBF-04 scope is canonical disposition/confirmation ordering, PID/start fencing,
WBC cleanup custody, terminal reconciliation, and worker/native signal paths.
NBF-05 scope is marker/bootstrap authority, non-worker signal revalidation,
record-before-signal locking, liveness/producer bindings, tmux socket/server/
owned-pane identity, and shell bridge fail-closed behavior. NBF-06, provider
resilience, deployment, commit/push/merge, main, and epic launch are excluded.

## Candidate manifest and framed identity

The explicit sorted newline-terminated manifest contains 40 source, test,
inventory, and generated-document paths:

`.oracle/scripts/nbf-batch3-attempt-1.manifest`

Manifest bytes: `2088`; manifest SHA-256:
`b28d54edca89ece81ba28d0bab7dae58350adbcbaca568176b66ca80ac12d622`.

The Oracle-only deterministic framing tool is
`.oracle/scripts/nbf_batch3_diff_v1.py`, SHA-256
`e2ec1d2f153c5990baeca60a9ee862fc8978f84d12fad4d447af1ac75454563a`.
Reproduce from repository root with:

```bash
python .oracle/scripts/nbf_batch3_diff_v1.py \
  --base 7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e \
  --manifest .oracle/scripts/nbf-batch3-attempt-1.manifest \
  --output .oracle/evidence/batch-3-attempt-1-framed-diff.json
```

The tool uses fixed Git config, no external diff/text conversion/renames,
tracked `--binary --full-index` diffs, `/dev/null` framing for untracked paths,
and fails closed on absolute headers. The output is
`.oracle/evidence/batch-3-attempt-1-framed-diff.json`, SHA-256
`85aa909c52d411a03f660ee301c70079e80ed0c925cf154c8dca3389649c275b`.
It records every per-path status, raw diff byte length, and raw diff SHA-256.
The manifest count is 40, total framed raw diff bytes are `663421`, and the
reproducible aggregate is:

`9cce8961eb5861aba1eb9948e9cb72580bd423de60ba2d9dfd3c7f3a32fec214`

## Implementation freeze

NBF-04 retains the single canonical signal/disposition/confirmation ledger,
typed TERM/KILL stages, record-before-signal ordering, dynamic PID/start
validation, crash/replay reconciliation, WBC custody handoff, and no-signal
failure paths.

NBF-05 adds an explicit marker/bootstrap resolver in
`incident/authority.py`. It validates marker self-digest, per-epic manifest and
expected runtime HEAD, manifest generation/runtime identity, boot/container and
supervisor incarnation, progress artifact digest, and worker reservation fields.
The CLI reloads these sources under the ledger lock before disposition/claim
and physical signal.

Real marker producers now refresh manifest/progress/supervisor bindings and,
when an exact tmux session is owned, publish socket fingerprint, server
PID/start, session ID, owned pane PID/start/ID/command, and all-pane digest.
Refresh removes stale tmux fields rather than carrying them forward. Resolver
and shell bridge reject partial or replaced bindings; ordinary non-tmux markers
remain valid. Late dead-target replay requires both the exact disposition and
matching `signal_claimed` event.

## Validation evidence

The requested focused gate was launched once as a quiescent combined run. It
reached `174 passed`, `9 failed`, and `187 errors` before completion. The
errors were predominantly pytest temporary-directory setup failures after the
machine again exhausted the filesystem while the test suite created numbered
temporary trees; representative errors were `FileNotFoundError` for vanished
pytest temp roots. The nine failures were downstream fixture/test failures in
that same exhausted-temp run, not a clean candidate verdict, and are not used
as acceptance evidence.

The relevant focused subsets had already passed independently: the authority,
replay, liveness, shell bridge, real tmux producer/resolver/replacement, and
NBF-04 ladder tests; the corrected shell bridge/source-contract pair was `2
passed`, and the earlier authority/liveness/watchdog gate was `51 passed`.
The inventory was regenerated from the candidate and then checked:

```text
fresh inventory: docs/nbf-signal-inventory.json
inventory_rc: 0
```

Python compilation of the touched authority/disposition/liveness/controlled
launch/custody modules passed. `bash -n` passed for all targeted heartbeat,
progress-auditor, runtime-lib, watchdog, and resident/watchdog systemd
wrappers. `git diff --check` passed.

## Explicit exclusions and residual risk

Excluded from this candidate framing are all `.oracle` packets, briefs,
receipts, findings, checkins, evidence directories, and the prior NBF-04
framing artifacts; they are review provenance, not source candidate content.
`evidence/m11-recovery-topology-surfaces.json` is likewise excluded as a
quarantined generated evidence artifact. The full repository suite was not
run. The combined run's filesystem exhaustion means this packet is a freeze
with recorded focused evidence, not a claim that every broad wrapper fixture
passed in that contaminated environment.

Known stale/non-candidate fixtures remain the unrelated runtime-attestation
seed expectation, OMP-vs-HERMES fake-output expectation, and old provider
timeout-124 expectation versus cleanup-hold-75. No NBF-06 work is required for
this internal gate.
