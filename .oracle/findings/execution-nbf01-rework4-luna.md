# NBF-01 rework 4 — Luna executor finding

## Evidence status

This is executor evidence for the frozen NBF-01 Batch 1 rework attempt 4. It
is not an Oracle review, does not issue `PASS_BATCH_1` or `ACCEPTED_ISSUES`,
and does not authorize Batch 2. The candidate remains uncommitted as required
by the leaf-execution contract.

RW4-01 was the hard gate. The typed reason-specific authoritative-source
reader now binds the producer and all serialized fields; coherent recomputed
forgery is rejected at decode, append, and consume, while a valid reader event
appends and consumes once. RW4-02 through RW4-05 then passed their packet
gates in strict serial order.

## Bound identities

| Item | Value |
|---|---|
| Branch | `megado-nbf-guard-0826` |
| Final HEAD before evidence artifacts | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| Source / merge-base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` / `798c50619204010ed3f4297fbb57988fe9381924` |
| Frozen tasklist SHA-256 | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| North Star SHA-256 | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| Attempt-4 packet SHA-256 | `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534` |
| Attempt-4 triage receipt SHA-256 | `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c` |
| Historical attempt-3 starting/reviewed production diff SHA-256 | `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8` |
| Final attempt-4 production diff SHA-256 | `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41` |

The exact identity command output is retained at
`/tmp/oracle-nbf01-rework4-luna/final_identity.txt` with SHA-256
`05797ea4e5dd3eb9d084e68e724b73dd0064efdba06cb1bf322e9e4750b3aebf`.
The historical attempt-3 digest is retained as historical input; it is not
claimed as the final digest.

## Owned production and test inventory

For each file, `git hash-object` is followed by the full-file SHA-256.

| File | git hash-object | SHA-256 |
|---|---|---|
| `arnold_pipelines/megaplan/incident/__init__.py` | `e9d4ecd617ae4e7eadf0c0450cba0a73d0720f1b` | `8a5afee7861ac777071f355e60627913b9a67a6178375ae141d57f983b75b923` |
| `arnold_pipelines/megaplan/incident/ledger.py` | `dab84bf37a52396b7b6de440e44c199d5bc342e0` | `da256e9d10763d1f5e76a13cacb95ae6d61a3ca6e95c42ae4d4f702e3c3061fe` |
| `arnold_pipelines/megaplan/incident/schema.py` | `f85ec2172ec1e36087e2927f796d8a61e72af97a` | `e32c111c077cced274162e51df1d3b0623b99a2933b390928f1356fe34402004` |
| `arnold_pipelines/megaplan/incident/disposition.py` | `74d640b20fe1b4c8edc58cbafd5d3d5756712ec3` | `8edad79ca55a3e999ab325158f7ce4f2c247b8f9698b4f2677b1c05d57512cf5` |
| `arnold_pipelines/megaplan/orchestration/phase_result.py` | `eb60256d6d4501dc97a37b90fe92191a611878ae` | `b3621d08c8c0367b65a3d3fbba2abee10d42d90a14896ebd1f9f83e65dfc0d28` |
| `arnold_pipelines/megaplan/orchestration/phase_result_classify.py` | `6f14c61e1b95609858dbb7b49a5bfa4b98de1cf5` | `a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641` |
| `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py` | `11813a7d986556b203497b2bad055eaa94aba550` | `ed21611737f05d74aecaa1f41b4a8af37baf59d488c467b232d77acf992b3cea` |
| `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py` | `c91963087ae35fce9f50ae322663825e4642bb59` | `118f174629869fb9aa4a7dbe6cfa127d317d71f2bfb90b10dcdbd353e7e837f8` |
| `tests/arnold_pipelines/megaplan/test_provider_route_projection.py` | `6de73b1e16d59ade8c22c5428dfdad5b660b072c` | `6d036f349fa14cf31f585996ca67033aeaa7b131b591958dcde1632cb656a949` |
| `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py` | `2d2ec909688040de467fb82f16e0676c1e69e8cd` | `8f2d756b8b7fd22b1f1c871829f593260e7a374c7b68e55a26c7870eb05f0a0e` |
| `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py` | `fc54999a025f23d89860facda94b260d1d7e5bb3` | `2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb` |
| `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py` | `30d6200fe4acd01cb2fd653364b949adaaa93e0a` | `73be8fb3f19e903f5b48680d200674e547aa4c4b111495e92b19ab7d1fe7a9d7` |
| `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py` | `1dcb901b9623e320642f4b96dae499e0c8e336a2` | `70d05156ff467c79f4ccc55446e7b5d692d1f4d362a8a21021230c22f0e80915` |
| `tests/arnold_pipelines/megaplan/test_worker_disposition.py` | `12e44bba5a1e9e99cb14886047eef240663244fb` | `0f9c412cd85b217a132b0e84b4e2f944bf4ba4b947f1dbbbc785116e0a876d06` |

The unchanged legacy `tests/arnold_pipelines/megaplan/test_incident_ledger.py`
was inspected and remained unmodified.

## Serial gate results

Every command ran with cwd
`/Users/peteromalley/Documents/Arnold-oracle-nbf`. Each `.meta` file records
the exact argv, cwd, exit status, complete stream paths, and stream hashes;
the referenced stream files are immutable isolated transcripts.

| Gate | Result | Metadata / stream SHA-256 (stdout, stderr) |
|---|---|---|
| RW4-01 exact coherent-forgery/reader gate | exit 0; 9 passed, 15 deselected | `rw401.meta`; `12892781cd69a69f7898391ccbf529aa47762cc0ad42d40b434ef5752e4dbc64`, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| RW4-02 exact four-door matrix | exit 0; 25 passed | `rw402.meta`; `f9bbeabdf0d465ce8619b915071c5298489c79da837a22fe040908499981ada0`, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| RW4-03 exact provider projection suite | exit 0; 18 passed | `rw403.meta`; `bcf90c38b8f06841524d35285acb47f7aed3489961bfce3db8a78803833308e3`, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| RW4-04 exact transaction proofs | exit 0; 6 passed, 11 deselected | `rw404tx.meta`; `aea89fb6eab893c383381e74852ea1b39ed8a317639d899da93a3b18a2a83e74`, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| RW4-04 exact provider replay/receipt proofs | exit 0; 6 passed, 12 deselected | `rw404provider.meta`; `cba62e819daecb2e25405e09697b04d0fca546d88c1d537c0704b2be0e02aec3`, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| RW4-05 exact confirmation/worker suite | exit 0; 28 passed | `rw405.meta`; `afdc3f3cdb3eff3741a8d949cd15a56f1e8ee6f87aa7289d036c9d6c2d755569`, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

## Stable-candidate validation

| Command | Exit/result | Metadata / stream SHA-256 (stdout, stderr) |
|---|---|---|
| Frozen focused suite: the eight new NBF modules plus `test_incident_ledger.py` | exit 0; 121 passed in 16.61s | `focused.meta`; `1f01445f45b658375e82f8d266eabe7313865719db122c33c2cb662c1ad28019`, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Frozen legacy suite: projection, summaries, bridge, phase-result classify | exit 0; 78 passed | `legacy.meta`; `db85410b01611725bec965e80009492342796bc42dc7b8ce17f65bafb28bd372`, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Packet-required RW4-05 confirmation-only suite | exit 0; 7 passed in 0.27s | `rw405_confirmation_only.meta`; `3b699c09a131f6fce9f8c5f77719de7f8be6f3d226bd0fbfbe7c408b1742ff02`, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Broad evidence sweep: `pytest -q tests/arnold_pipelines/megaplan` | exit 2; collection blocked | `broad.meta`; `8fb59a66f2a82c1b28b58912dce97aecc50c5511677ea3bd9a034b4081646c5c`, `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Required compile gate | exit 0 | `pycompile.meta`; both streams `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Required whitespace gate | exit 0 | `diffcheck.meta`; both streams `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

## Evidence-seal audit

This executor-evidence sealing pass is not the later independent review. It
made no production or test edit. It re-hashed every stream referenced by the
existing `.meta` files, recomputed the serialized stdout/stderr hashes in all
eight `cli_status_*.json` records, re-hashed every displayed owned-file
identity, and reproduced the final production diff, tasklist, North Star,
packet, triage receipt, and identity-transcript digests.

Every pre-existing displayed digest reproduced. In particular, status 4 has
truly empty stdout with the full SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
its stderr SHA-256 is
`d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f`.
No status-4 correction was required.

The packet's exact RW4-06 command inventory was compared to the captured
transcripts. One gap was found: the exact single-module command
`pytest -q tests/arnold_pipelines/megaplan/test_supervision_confirmation.py`
had only been covered inside `rw405.meta`, which is a two-module command. The
single-module command was therefore rerun and captured under the existing
evidence root as:

- `/tmp/oracle-nbf01-rework4-luna/rw405_confirmation_only.meta`
- `/tmp/oracle-nbf01-rework4-luna/rw405_confirmation_only.stdout`
- `/tmp/oracle-nbf01-rework4-luna/rw405_confirmation_only.stderr`

Its exact argv and cwd are in the metadata above; it exited 0 with
`7 passed in 0.27s`, stdout SHA-256
`3b699c09a131f6fce9f8c5f77719de7f8be6f3d226bd0fbfbe7c408b1742ff02`,
and empty stderr SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

After that capture, every exact gate command required by RW4-06 has a dedicated
artifact:

| Packet command | Evidence |
|---|---|
| Frozen focused suite | `focused.meta` |
| Frozen legacy suite | `legacy.meta` |
| RW4-01 producer/forgery subset | `rw401.meta` |
| RW4-02 payload/identity matrix | `rw402.meta` |
| RW4-03 provider projection suite | `rw403.meta` |
| RW4-04 transaction subset | `rw404tx.meta` |
| RW4-04 provider replay/receipt subset | `rw404provider.meta` |
| RW4-05 confirmation-only suite | `rw405_confirmation_only.meta` |
| Direct CLI 0/2/3/4/5 matrix | eight `cli_status_*.json` transcripts |
| Full megaplan-directory sweep | `broad.meta` and complete `broad.stdout` / `broad.stderr` |
| Production-module compile gate | `pycompile.meta` |
| Whitespace gate | `diffcheck.meta` |

The two-module `rw405.meta` remains valid serial-stage regression evidence in
addition to the now-complete exact RW4-06 command inventory.

The broad sweep transcript is complete at
`/tmp/oracle-nbf01-rework4-luna/broad.stdout`; it was not summarized or
repaired. Its collection blocker is the pre-existing missing
`arnold.agent.costing.model_resource_capabilities` module in
`test_cli_check_validator.py` and missing `tools.environments.singularity` in
`test_key_pool_codex.py`. These are outside the frozen packet scope.

## Independent CLI evidence

The independent subprocess records are complete JSON transcripts. Each record
contains the exact argv, cwd, stdin, ledger root in argv, complete stdout and
stderr, exit status, and both stream SHA-256 values.

| Case | Exit | Transcript; stdout SHA-256; stderr SHA-256 |
|---|---:|---|
| status 0 valid acknowledgment | 0 | `cli_status_0.json`; `de85b9592423e61ef59c4a860ba75e55ed618dd8934da164df3f802f16b71e85`; `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| status 2 malformed JSON | 2 | `cli_status_2_malformed.json`; `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; `50749e033709ba1e535cb55375755634d1959d2b544b9d147b53f83ee9e40cce` |
| status 2 schema-invalid | 2 | `cli_status_2_schema.json`; `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; `2525d332bcb419a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee` |
| status 3 append/lock | 3 | `cli_status_3.json`; `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; `9c917cf1df7f9f9eb5f072885c632f0d3d9d89347e4e68684bfbeb672d2e1298` |
| status 4 invalid ledger | 4 | `cli_status_4.json`; `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; `d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f` |
| status 5 missing replay | 5 | `cli_status_5_missing.json`; `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; `ba1b085108f0badd069a4300fa67e4c3b5bc5e15b3ca539791b1df1fb55dfcd9` |
| status 5 expired replay | 5 | `cli_status_5_expired.json`; `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; `4a94dd274793bb078a14c1b046e8d3ff12648c4e6f2f378a41d158500b5f9b93` |
| status 5 distinct already-consumed replay | 5 | `cli_status_5_distinct_consumed.json`; `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; `2f3e796334ebb7f1319ec5a87170361442060a3f641644f8b41cf03a07a87655` |

The valid status-0 case emitted one JSON acknowledgment and did not signal.

## Preserved scope and unresolved issues

The implementation retains the single journal, sequence-sidecar lock, single
mutation door, receipt-bound launch markers, keyed replay/isolation, real
two-process reservation and terminal races, pre- and post-append crash/reopen
proofs, lease-bound recovery, full confirmation equality, and CLI regression
behavior required by the packet. Excluded work was not reopened.

There is no in-scope implementation blocker after RW4-05. The only failed
validation is the broad collection sweep's pre-existing missing-module blocker
listed above. The candidate is intentionally uncommitted and no Oracle or
Batch-2 conclusion is made.
