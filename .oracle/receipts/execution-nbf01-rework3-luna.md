# Executor receipt — NBF-01 Batch 1 rework 3

Executor evidence only; this file is not an Oracle review and contains no
Oracle verdict.

## Receipt status

Attempt-3 was applied in strict serial order
`RW3-01 → RW3-02 → RW3-05 → RW3-03 → RW3-04 → RW3-06`.
The implementation is complete for the packet scope. Validation recorded 112
focused tests and 78 frozen legacy tests passing. The broader directory sweep
was attempted and stopped at collection because two unrelated modules are
missing. The candidate remains uncommitted and unstaged; Batch 2 was not
started.

## Candidate and evidence binding

- Candidate: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Branch: `megado-nbf-guard-0826`
- HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Source: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Frozen tasklist: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Attempt-3 packet: `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779`
- Attempt-3 triage receipt: `2d025f9614d5dcf3f4e00de881962f1152a8be222b7cb4868055cf5a47856f4b`
- Attempt-2 starting production diff: `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`
- Final tracked production diff SHA-256: `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`

## Exact validation command receipt

All commands ran with cwd
`/Users/peteromalley/Documents/Arnold-oracle-nbf`. Empty stdout/stderr has
SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

```text
ARGV: ["pytest", "-q", "tests/arnold_pipelines/megaplan/test_worker_disposition.py", "tests/arnold_pipelines/megaplan/test_scheduling_conditions.py", "tests/arnold_pipelines/megaplan/test_provider_route_projection.py", "tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py", "tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py", "tests/arnold_pipelines/megaplan/test_terminal_outcomes.py", "tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py", "tests/arnold_pipelines/megaplan/test_supervision_confirmation.py", "tests/arnold_pipelines/megaplan/test_incident_ledger.py"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT: 0
STDOUT: ........................................................................ [ 64%]\n........................................                                 [100%]\n112 passed in 16.34s\n
STDOUT SHA-256: 1e97d7ee82701355e83e954bf945cd5ed2655ed884f7369c19fb499e84f8f2e4
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

ARGV: ["pytest", "-q", "tests/arnold_pipelines/megaplan/test_incident_projection.py", "tests/arnold_pipelines/megaplan/test_incident_summaries.py", "tests/arnold_pipelines/megaplan/test_incident_bridge.py", "tests/arnold_pipelines/megaplan/test_phase_result_classify.py"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT: 0
STDOUT: ........................................................................ [ 92%]\n......                                                                   [100%]\n78 passed in 1.76s\n
STDOUT SHA-256: 47e12d6b3361c9722be15df538acf7f74a1edd503fcf3fd62440780abe3a2a14
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

ARGV: ["pytest", "-q", "tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py", "-k", "two_process or torn or crash or contention"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT: 0
STDOUT: .....                                                                    [100%]\n5 passed, 11 deselected in 1.98s\n
STDOUT SHA-256: 84fd46578d96dc146270b129a50526740ec854e77467875c0725b42b218b3e45
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

ARGV: ["pytest", "-q", "tests/arnold_pipelines/megaplan/test_provider_route_projection.py", "-k", "replay or receipt or keyed"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT: 0
STDOUT: .....                                                                    [100%]\n5 passed, 6 deselected in 0.36s\n
STDOUT SHA-256: dd0cc8f5ae146b4a403f7dab2a0b66f4aea8601afbb760e6ec799a38b9581c01
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

ARGV: ["pytest", "-q", "tests/arnold_pipelines/megaplan/test_supervision_confirmation.py", "-k", "cli or confirmation or incarnation or reopen"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT: 0
STDOUT: .......                                                                  [100%]\n7 passed in 0.39s\n
STDOUT SHA-256: 9c2bc789bf2cba75cc5ed822cd3fccab9cf3d7a226611daf566ceea5ed0c55b1
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

ARGV: ["python", "-m", "py_compile", "arnold_pipelines/megaplan/orchestration/phase_result.py", "arnold_pipelines/megaplan/orchestration/phase_result_classify.py", "arnold_pipelines/megaplan/incident/schema.py", "arnold_pipelines/megaplan/incident/ledger.py", "arnold_pipelines/megaplan/incident/disposition.py"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT: 0
STDOUT: (empty)
STDOUT SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

ARGV: ["git", "diff", "--check"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT: 0
STDOUT: (empty)
STDOUT SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

The broader sweep was:

```text
ARGV: ["pytest", "-q", "tests/arnold_pipelines/megaplan"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT: 2
STDOUT: collection errors in test_cli_check_validator.py and test_key_pool_codex.py; missing arnold.agent.costing.model_resource_capabilities and tools.environments.singularity; 2 errors in 5.37s\n
STDOUT SHA-256: 733a94e3d720a83113f4d94c7df880dde1698225649e63b3d076fa51cc771123
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

## Disposition CLI status matrix

All rows used cwd
`/Users/peteromalley/Documents/Arnold-oracle-nbf` and argv template
`["python", "-m", "arnold_pipelines.megaplan.incident.disposition", "record", "--ledger-root", CASE_ROOT, "--json-stdin"]`.

| Case | Exit | stdout / SHA-256 | stderr / SHA-256 |
|---|---:|---|---|
| malformed | 2 | empty / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `disposition schema error: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)\n` / `45c31321add927bbf9be3bd864a18e688dbaf59a4326c527bdb198b56258180a` |
| schema | 2 | empty / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `disposition schema error: WorkerDisposition missing fields: ['admission_receipt_id', 'cause_kind', 'confirmation_event_id', 'dispatch_family_id', 'disposition_id', 'elapsed_s', 'evidence', 'killer_identity', 'killer_kind', 'ladder_step', 'logical_dispatch_id', 'mode', 'observed_at', 'phase', 'plan_id', 'process_group_identity', 'schema_version', 'selected_spec', 'semantic_dispatch_fingerprint', 'signal', 'timeout_source', 'victim_pid', 'victim_process_start_identity', 'worker_identity']\n` / `2525d332bcb419a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee` |
| append failure | 3 | empty / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `ledger append failure: [Errno 21] Is a directory: '/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/rw3-cli-6iwnoowa/append3/.megaplan/incident-ledger/events.jsonl'\n` / `4f778281f315da56dc7fd54318341076ea01fa89c0e5bc554c055c4188d0da6c` |
| invalid location | 4 | empty / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `invalid ledger location: ledger root must be an existing directory\n` / `d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f` |
| confirmation missing | 5 | empty / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `required confirmation missing\n` / `ba1b085108f0badd069a4300fa67e4c3b5bc5e15b3ca539791b1df1fb55dfcd9` |
| confirmation expired | 5 | empty / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `required confirmation missing or not consumed\n` / `4a94dd274793bb078a14c1b046e8d3ff12648c4e6f2f378a41d158500b5f9b93` |
| first valid replay | 0 | `{"disposition_id":"cli-d","ledger_event_id":"cli-d","record_id":"cli-d"}\n` / `ca0439b771124a8d30d3a105ccf198a91654bd71341b841cd64f49a14e5f26d9` | empty / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| already-consumed replay | 5 | empty / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `disposition replay already consumed\n` / `7fe9e01d6cba7af6c48aff7b6a459cfc1116a9bfbc742574a8da501cc954e208` |

Case ledger roots were, in row order:
`/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/rw3-cli-6iwnoowa/{malformed,schema,append3,not-dir,missing,expired,replay,replay}`.

