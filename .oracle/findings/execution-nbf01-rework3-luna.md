# Executor finding — NBF-01 Batch 1 rework 3

This is executor evidence, not an Oracle review or verdict.

## Result

The attempt-3 packet was implemented in the required serial order:

`RW3-01 → RW3-02 → RW3-05 → RW3-03 → RW3-04 → RW3-06`

The packet-scoped implementation and validation completed. The candidate is
left uncommitted and unstaged. Batch 2 was not started. No Oracle verdict was
issued.

## Immutable bindings

- Candidate: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Branch: `megado-nbf-guard-0826`
- Candidate HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Source: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- HEAD/source merge-base: `798c50619204010ed3f4297fbb57988fe9381924`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Attempt-3 packet SHA-256: `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779`
- Attempt-3 triage receipt SHA-256: `2d025f9614d5dcf3f4e00de881962f1152a8be222b7cb4868055cf5a47856f4b`
- Attempt-2 tracked-production starting identity: `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`

The working tree was already dirty. Existing user/orchestrator changes and
historical `.oracle` evidence were preserved; only the two evidence files named
by this packet were added under `.oracle`.

## Implemented packet scope

- `RW3-01`: typed worker identity and terminal-outcome invariants; controlled
  adapter acceptance marker is required before terminal append.
- `RW3-02`: authoritative, reason-specific changed-precondition producers;
  provider recovery is bound to a passed canonical probe and matching key.
- `RW3-05`: provider route-child reservation is keyed to the parent terminal,
  authorizing recovery event, lease, and single-use semantics; reservation
  projection no longer infers acceptance from a terminal.
- `RW3-03`: append/replay projection is keyed by provider failure key and
  preserves streak/terminal semantics; confirmation expiry cannot undo consume.
- `RW3-04`: disposition CLI maps malformed/schema/location/append/confirmation
  and already-consumed replay cases to the required statuses.
- `RW3-06`: packet behavioral regressions cover forged transitions, typed worker
  dispositions, concurrent distinct terminal IDs, receipt replay, confirmation
  binding, and legal OOM/unknown-death records.

Production files changed in scope:

- `arnold_pipelines/megaplan/incident/ledger.py`
- `arnold_pipelines/megaplan/incident/schema.py`
- `arnold_pipelines/megaplan/incident/disposition.py`
- `arnold_pipelines/megaplan/orchestration/phase_result.py`

Packet test files changed in scope:

- `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py`
- `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`
- `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`
- `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py`
- `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py`
- `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py`
- `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`
- `tests/arnold_pipelines/megaplan/test_worker_disposition.py`

`tests/arnold_pipelines/megaplan/test_incident_ledger.py` was included in the
frozen focused suite and was not modified.

## Production diff identity

The final tracked production diff, computed with:

```text
git diff origin/main -- arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py | shasum -a 256
```

has SHA-256:

`8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`

The additional production CLI file has git blob identity
`291c66ed2ac9b984e2c3d1f763bafcf7b86ca1c1` and SHA-256
`2a59e440d7bcae53700b7ea63fdd2d15b1b1705eeb6914d24ea4f37300ab505a`.

## Validation receipt

All commands below ran with cwd
`/Users/peteromalley/Documents/Arnold-oracle-nbf`. For every command, the
recorded hashes are over the complete stdout and stderr byte streams. The hash
of empty output is
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

### Frozen focused and legacy suites

```text
ARGV: ["pytest", "-q", "tests/arnold_pipelines/megaplan/test_worker_disposition.py", "tests/arnold_pipelines/megaplan/test_scheduling_conditions.py", "tests/arnold_pipelines/megaplan/test_provider_route_projection.py", "tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py", "tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py", "tests/arnold_pipelines/megaplan/test_terminal_outcomes.py", "tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py", "tests/arnold_pipelines/megaplan/test_supervision_confirmation.py", "tests/arnold_pipelines/megaplan/test_incident_ledger.py"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT STATUS: 0
STDOUT:
........................................................................ [ 64%]
........................................                                 [100%]
112 passed in 16.34s
STDOUT SHA-256: 1e97d7ee82701355e83e954bf945cd5ed2655ed884f7369c19fb499e84f8f2e4
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

```text
ARGV: ["pytest", "-q", "tests/arnold_pipelines/megaplan/test_incident_projection.py", "tests/arnold_pipelines/megaplan/test_incident_summaries.py", "tests/arnold_pipelines/megaplan/test_incident_bridge.py", "tests/arnold_pipelines/megaplan/test_phase_result_classify.py"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT STATUS: 0
STDOUT:
........................................................................ [ 92%]
......                                                                   [100%]
78 passed in 1.76s
STDOUT SHA-256: 47e12d6b3361c9722be15df538acf7f74a1edd503fcf3fd62440780abe3a2a14
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

### Strong in-scope behavioral slices

```text
ARGV: ["pytest", "-q", "tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py", "-k", "two_process or torn or crash or contention"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT STATUS: 0
STDOUT:
.....                                                                    [100%]
5 passed, 11 deselected in 1.98s
STDOUT SHA-256: 84fd46578d96dc146270b129a50526740ec854e77467875c0725b42b218b3e45
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

```text
ARGV: ["pytest", "-q", "tests/arnold_pipelines/megaplan/test_provider_route_projection.py", "-k", "replay or receipt or keyed"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT STATUS: 0
STDOUT:
.....                                                                    [100%]
5 passed, 6 deselected in 0.36s
STDOUT SHA-256: dd0cc8f5ae146b4a403f7dab2a0b66f4aea8601afbb760e6ec799a38b9581c01
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

```text
ARGV: ["pytest", "-q", "tests/arnold_pipelines/megaplan/test_supervision_confirmation.py", "-k", "cli or confirmation or incarnation or reopen"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT STATUS: 0
STDOUT:
.......                                                                  [100%]
7 passed in 0.39s
STDOUT SHA-256: 9c2bc789bf2cba75cc5ed822cd3fccab9cf3d7a226611daf566ceea5ed0c55b1
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

```text
ARGV: ["python", "-m", "py_compile", "arnold_pipelines/megaplan/orchestration/phase_result.py", "arnold_pipelines/megaplan/orchestration/phase_result_classify.py", "arnold_pipelines/megaplan/incident/schema.py", "arnold_pipelines/megaplan/incident/ledger.py", "arnold_pipelines/megaplan/incident/disposition.py"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT STATUS: 0
STDOUT: (empty)
STDOUT SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

```text
ARGV: ["git", "diff", "--check"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT STATUS: 0
STDOUT: (empty)
STDOUT SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

### Full megaplan test-directory sweep

```text
ARGV: ["pytest", "-q", "tests/arnold_pipelines/megaplan"]
CWD: /Users/peteromalley/Documents/Arnold-oracle-nbf
EXIT STATUS: 2
STDOUT:
==================================== ERRORS ====================================
_ ERROR collecting tests/arnold_pipelines/megaplan/test_cli_check_validator.py _
ImportError while importing test module '/Users/peteromalley/Documents/Arnold-oracle-nbf/tests/arnold_pipelines/megaplan/test_cli_check_validator.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/arnold_pipelines/megaplan/test_cli_check_validator.py:21: in <module>
    from arnold.workflow.validator import (
arnold/workflow/validator.py:37: in <module>
    from arnold.agent.costing.model_resource_capabilities import prove_stage_required_capabilities
E   ModuleNotFoundError: No module named 'arnold.agent.costing.model_resource_capabilities'
___ ERROR collecting tests/arnold_pipelines/megaplan/test_key_pool_codex.py ____
ImportError while importing test module '/Users/peteromalley/Documents/Arnold-oracle-nbf/tests/arnold_pipelines/megaplan/test_key_pool_codex.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests/arnold_pipelines/megaplan/test_key_pool_codex.py:15: in <module>
    from arnold.agent.run_agent import AIAgent
arnold/agent/run_agent.py:71: in <module>
    from arnold.agent.tools.terminal_tool import cleanup_vm
arnold/agent/tools/terminal_tool.py:50: in <module>
    _SPEC.loader.exec_module(_MODULE)
arnold_pipelines/megaplan/agent/tools/terminal_tool.py:83: in <module>
    from tools.environments.singularity import _get_scratch_dir
E   ModuleNotFoundError: No module named 'tools.environments.singularity'
=========================== short test summary info ============================
ERROR tests/arnold_pipelines/megaplan/test_cli_check_validator.py
ERROR tests/arnold_pipelines/megaplan/test_key_pool_codex.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
2 errors in 5.37s
STDOUT SHA-256: 733a94e3d720a83113f4d94c7df880dde1698225649e63b3d076fa51cc771123
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

The sweep blocker is collection-only and comes from the two pre-existing
missing modules named above; the packet-focused and frozen legacy suites pass.

## Independent disposition CLI transcript

Each case used the exact argv below, with the case-specific ledger root shown
in the `--ledger-root` argument, and cwd
`/Users/peteromalley/Documents/Arnold-oracle-nbf`:

```text
ARGV template: ["python", "-m", "arnold_pipelines.megaplan.incident.disposition", "record", "--ledger-root", CASE_LEDGER_ROOT, "--json-stdin"]
```

`CASE_LEDGER_ROOT` values and complete streams:

```text
CASE 2-malformed
ARGV: ["python", "-m", "arnold_pipelines.megaplan.incident.disposition", "record", "--ledger-root", "/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/rw3-cli-6iwnoowa/malformed", "--json-stdin"]
EXIT STATUS: 2
STDOUT: (empty)
STDOUT SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
STDERR: disposition schema error: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)\n
STDERR SHA-256: 45c31321add927bbf9be3bd864a18e688dbaf59a4326c527bdb198b56258180a

CASE 2-schema
ARGV: ["python", "-m", "arnold_pipelines.megaplan.incident.disposition", "record", "--ledger-root", "/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/rw3-cli-6iwnoowa/schema", "--json-stdin"]
EXIT STATUS: 2
STDOUT: (empty)
STDOUT SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
STDERR: disposition schema error: WorkerDisposition missing fields: ['admission_receipt_id', 'cause_kind', 'confirmation_event_id', 'dispatch_family_id', 'disposition_id', 'elapsed_s', 'evidence', 'killer_identity', 'killer_kind', 'ladder_step', 'logical_dispatch_id', 'mode', 'observed_at', 'phase', 'plan_id', 'process_group_identity', 'schema_version', 'selected_spec', 'semantic_dispatch_fingerprint', 'signal', 'timeout_source', 'victim_pid', 'victim_process_start_identity', 'worker_identity']\n
STDERR SHA-256: 2525d332bcb419a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee

CASE 3
ARGV: ["python", "-m", "arnold_pipelines.megaplan.incident.disposition", "record", "--ledger-root", "/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/rw3-cli-6iwnoowa/append3", "--json-stdin"]
EXIT STATUS: 3
STDOUT: (empty)
STDOUT SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
STDERR: ledger append failure: [Errno 21] Is a directory: '/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/rw3-cli-6iwnoowa/append3/.megaplan/incident-ledger/events.jsonl'\n
STDERR SHA-256: 4f778281f315da56dc7fd54318341076ea01fa89c0e5bc554c055c4188d0da6c

CASE 4
ARGV: ["python", "-m", "arnold_pipelines.megaplan.incident.disposition", "record", "--ledger-root", "/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/rw3-cli-6iwnoowa/not-dir", "--json-stdin"]
EXIT STATUS: 4
STDOUT: (empty)
STDOUT SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
STDERR: invalid ledger location: ledger root must be an existing directory\n
STDERR SHA-256: d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f

CASE 5-missing
ARGV: ["python", "-m", "arnold_pipelines.megaplan.incident.disposition", "record", "--ledger-root", "/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/rw3-cli-6iwnoowa/missing", "--json-stdin"]
EXIT STATUS: 5
STDOUT: (empty)
STDOUT SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
STDERR: required confirmation missing\n
STDERR SHA-256: ba1b085108f0badd069a4300fa67e4c3b5bc5e15b3ca539791b1df1fb55dfcd9

CASE 5-expired
ARGV: ["python", "-m", "arnold_pipelines.megaplan.incident.disposition", "record", "--ledger-root", "/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/rw3-cli-6iwnoowa/expired", "--json-stdin"]
EXIT STATUS: 5
STDOUT: (empty)
STDOUT SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
STDERR: required confirmation missing or not consumed\n
STDERR SHA-256: 4a94dd274793bb078a14c1b046e8d3ff12648c4e6f2f378a41d158500b5f9b93

CASE 0-replay-first
ARGV: ["python", "-m", "arnold_pipelines.megaplan.incident.disposition", "record", "--ledger-root", "/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/rw3-cli-6iwnoowa/replay", "--json-stdin"]
EXIT STATUS: 0
STDOUT: {"disposition_id":"cli-d","ledger_event_id":"cli-d","record_id":"cli-d"}\n
STDOUT SHA-256: ca0439b771124a8d30d3a105ccf198a91654bd71341b841cd64f49a14e5f26d9
STDERR: (empty)
STDERR SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

CASE 5-replay-second
ARGV: ["python", "-m", "arnold_pipelines.megaplan.incident.disposition", "record", "--ledger-root", "/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/rw3-cli-6iwnoowa/replay", "--json-stdin"]
EXIT STATUS: 5
STDOUT: (empty)
STDOUT SHA-256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
STDERR: disposition replay already consumed\n
STDERR SHA-256: 7fe9e01d6cba7af6c48aff7b6a459cfc1116a9bfbc742574a8da501cc954e208
```

An independent status-0 run used ledger root
`/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/rw3-cli-status0-bj4sxuv9`
with the same argv and cwd: exit status `0`, stdout
`{"disposition_id":"cli-d","ledger_event_id":"cli-d","record_id":"cli-d"}\n`
with SHA-256
`ca0439b771124a8d30d3a105ccf198a91654bd71341b841cd64f49a14e5f26d9`, and
empty stderr with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## Historical custody preserved

The following prior identities were not rewritten:

- Start-gate mutation: `52→61`
- Unreproducible receipt: `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`
- Failed handoff: `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`
- Attempt-1 78/78 receipt: `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`
- Attempt-2 reviewed production diff: `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`

