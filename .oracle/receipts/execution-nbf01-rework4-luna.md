# Receipt — NBF-01 rework 4 Luna executor evidence

## Classification

This receipt records the implementation executor's evidence for the frozen
attempt-4 packet. It is not an Oracle review and contains no
`PASS_BATCH_1`/`ACCEPTED_ISSUES` verdict. No reviewer was commissioned. Batch 2
was not started.

## Bound source and artifacts

- Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Branch: `megado-nbf-guard-0826`
- HEAD at validation: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Source and merge-base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
  and `798c50619204010ed3f4297fbb57988fe9381924`
- Frozen tasklist SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Attempt-4 packet SHA-256:
  `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534`
- Attempt-4 triage receipt SHA-256:
  `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c`
- Historical attempt-3 starting/reviewed production diff SHA-256:
  `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`
- Final attempt-4 production diff SHA-256:
  `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`
- Finding `git hash-object`:
  `cd6a54789d8e0b2ba6a7a0759d873914bba57022`
- Finding full-file SHA-256:
  `b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1`

The complete owned-file inventory and all validation evidence are in the
companion finding. The exact identity transcript is
`/tmp/oracle-nbf01-rework4-luna/final_identity.txt`.

## Execution receipt

The six frozen tasks ran serially: RW4-01, RW4-02, RW4-03, RW4-04, RW4-05,
then RW4-06 evidence publication. RW4-01's hard condition passed: the
recomputed coherent forgery failed at decode, locked append, and locked
consume, and the valid typed authoritative-reader event appended and consumed
exactly once. The later task gates passed as recorded in the finding.

Stable-candidate outcomes:

- RW4-01: 9 passed, 15 deselected.
- RW4-02: 25 passed.
- RW4-03: 18 passed.
- RW4-04 transaction proofs: 6 passed, 11 deselected; provider replay/receipt
  proofs: 6 passed, 12 deselected.
- RW4-05: 28 passed.
- Packet-required confirmation-only command: 7 passed in 0.27s; exact
  transcript `rw405_confirmation_only.meta`, stdout SHA-256
  `3b699c09a131f6fce9f8c5f77719de7f8be6f3d226bd0fbfbe7c408b1742ff02`,
  empty stderr SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Frozen focused suite: 121 passed.
- Frozen legacy suite: 78 passed.
- Compile gate: exit 0.
- Whitespace gate: exit 0.
- Broad sweep: exit 2 during collection only because the pre-existing missing
  `arnold.agent.costing.model_resource_capabilities` and
  `tools.environments.singularity` modules recur. The complete output remains
  verbatim at `/tmp/oracle-nbf01-rework4-luna/broad.stdout` with the hashes in
  the finding; neither module was repaired or waived.

Independent CLI subprocess evidence covers status 0, malformed/schema-invalid
status 2, append/lock status 3, invalid-ledger status 4, and missing, expired,
and distinct already-consumed replay status 5. The status-0 process emitted
one JSON acknowledgment and did not signal. The eight complete JSON records
are in `/tmp/oracle-nbf01-rework4-luna/cli_status_*.json` and include exact
stdin, ledger roots, argv, streams, exits, and stream hashes.

## Evidence-seal addendum

A Luna executor-evidence sealing pass compared the attempt-4 packet's exact
gate-command list with the transcript inventory and verified every displayed
stream, CLI JSON, owned-file, identity, and production-diff SHA-256. All
pre-existing digests reproduced. The suspected status-4 value was verified,
not changed: stdout is empty with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
stderr SHA-256 is
`d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f`.

The audit identified only one transcript-coverage omission: the exact
single-module RW4-05 gate command had no standalone capture. It was rerun
exactly as
`pytest -q tests/arnold_pipelines/megaplan/test_supervision_confirmation.py`
from the repository cwd and recorded under the existing attempt-4 evidence
root. With that addition, every exact RW4-06 gate command has a dedicated
transcript. This sealing pass edited only this receipt and its companion
attempt-4 finding; it did not edit production/tests or create a review verdict.

## Stop state

Only the requested source/test edits and these two executor artifacts were
published by this leaf. No frozen or historical artifact was rewritten; no
staging, commit, push, merge, rebase, reset, cleanup, Oracle verdict, or Batch
2 action was performed. The sole unresolved validation issue is the
pre-existing out-of-scope broad-collection blocker described above.
