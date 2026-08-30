# Executor finding — NBF-01 Batch 1 rework 6

This is executor evidence for the single authorized task `RW6-01 — C02/C13
complete six-kind/four-door payload and typed-identity matrix`. It is not an
Oracle review or a batch decision.

## Outcome

The candidate already contained the RW6-01 implementation before this leaf
began. The existing test-only matrix repair is in
`tests/arnold_pipelines/megaplan/test_worker_disposition.py` and covers the
complete `DispatchOutcome.to_dict()` six-kind records through direct
construction, `from_dict`, `validate_nbf_event`, public
`append_terminal_outcome`, and public `append_disposition`, with exact
payload-family assertions. It also covers worker, observed-death, and
non-worker identity/version matrices and preserves legal positives.

The existing candidate also contains one minimal source correction in
`arnold_pipelines/megaplan/incident/schema.py`,
`ObservedProcessDeath.__post_init__`: victim identity evidence must be a
mapping before the existing non-empty check. A fabricated non-empty string no
longer crosses that typed-identity door. No source or test edit was needed in
this leaf; duplicating or restyling the already-present repair would widen the
authorized change without improving behavior.

## Identity and custody

- Model: `codex:gpt-5.6-luna`; reasoning: high.
- Candidate HEAD before and after: `922241d0bdb3e993c3b554cc69f19948adef7bc3`.
- Branch: `megado-nbf-guard-0826`.
- Source/merge-base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`.
- Attempt-6 packet SHA-256:
  `b776d6cc5b090fb4cbb278ec5fff265cb5cf92896c22c0fe0fed066713609b83`.
- Attempt-6 triage receipt SHA-256:
  `88a0c2b76663cf63a32129296a74a610d01a4bedf66aef04dbaec570979bbcc8`.
- Frozen tasklist SHA-256:
  `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`.
- Settled plan v8 SHA-256:
  `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`.
- North Star SHA-256:
  `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.
- Agent goal SHA-256:
  `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`.
- Custody SHA-256:
  `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`.
- Attempt-5 production baseline SHA-256:
  `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`.

The required pre-edit production-diff capture was already
`ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`, not the
attempt-5 baseline. This is evidence that the dirty candidate already included
the RW6-01 source correction; it was preserved, not overwritten. The final
production diff is the same digest. Preflight and final identity commands
recorded identical HEAD, branch, and merge-base values.

## Preserved behavior

Validation retained the one incident journal and sequence-sidecar lock, typed
worker dispositions, no-launch/unresolved distinction, legal OOM and unknown
death paths, non-worker lifecycle shutdown, matching success/ordinary/provider
terminals, keyed provider/recovery behavior, replay/consume-once,
confirmation-evidence equality, C03-C08/C12/C14 semantics, and legacy ledger
behavior. No `PhaseResult` transport expansion, C19-C21/C39 reopener, second
authority, scheduler/policy change, or later-batch file was introduced.

## Validation evidence

Fresh isolated evidence root:
`/tmp/oracle-nbf01-rework6-luna-final-0830/`.

Every record stores literal argv, cwd, UTC start/end, exit status, complete
stdout and stderr files, stream SHA-256 digests, and a structured transcript
digest. Empty streams use the full SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

| Exact command | Exit/result | stdout SHA-256 | stderr SHA-256 | transcript SHA-256 |
|---|---:|---|---|---|
| `python -m pytest -q tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py` | 0; 28 passed | `e1b901de52356d4a4f7fbe2acc082fdd083f764e68d041aa8d5094691793299e` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `24d00e0353fc84f7680fbd559965511f0ec1c0fe3c206c141ae64111bd82e643` |
| `python -m pytest -q tests/arnold_pipelines/megaplan/test_worker_disposition.py -k "incompatible_matrix or observed_and_non_worker"` | 0; 2 passed, 22 deselected | `c15e3b3f685b855afc4ed4a33d067ada47b85290c28b88cf9c3a680f06c7e5c0` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `1107909cc9db6c5f907fcaf0f27fb4782f47aea6d0d68e76dbcb2c8412e60992` |
| `python -m pytest -q tests/arnold_pipelines/megaplan/test_terminal_outcomes.py -k "append or disposition or worker"` | 0; 1 passed, 1 deselected | `cbef2dd0385da86eece360e3d0ee595e1117d4e9248047b20d4985e9a3ecff97` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `39bd8dd84b0e2504937f267887e9523e53a0d86ab10b161944b7e4caca9606e1` |
| `python -m pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_supervision_confirmation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_incident_ledger.py` | 0; 124 passed | `d9bfdba7a5c53164e2664c7c5b12d3d99f2d1464382416d3b56ae1ae81b7c6a7` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `41fd543d0971c1e1e8d79a66b0bd305e64db1ab8a161ce933c0033a6d0bab40f` |
| `python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger.py` | 0; 42 passed | `745040281d8d7f49095b94c095703a369a4b2acc63334f4f4cca7588618c5991` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `176a2ab4063933d9bcf564662687943de2bd6e9baec9a43e140cecd8abee421c` |
| `python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_projection.py tests/arnold_pipelines/megaplan/test_incident_summaries.py tests/arnold_pipelines/megaplan/test_incident_bridge.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py` | 0; 78 passed | `1beeac65683fcf647b3d859c3bc90c1fd986b6ed82e0a661b92ee6d13cce93af` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `a02134f5cb8d7a1343644f98d518c44c004229a9899b12da4b57ed44bc1d57e2` |
| `python -m py_compile arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/disposition.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `0faa6fb0774c58dce1d8de83941c9bb9a3f3ac12e7c7673ed7601b870c49eb41` |
| `git diff --check` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `d58abd51da854280e14b8d2ba86c422a79a6e319288069471788c10e03117be0` |

Complete records are in
`/tmp/oracle-nbf01-rework6-luna-final-0830/validation/command-manifest.ndjson`,
manifest SHA-256
`ca18c4ee9eb4b7c48ddb8a6f75e073ccad1518577667bd84b4b52738e58658eb`.
No broad `pytest -q tests/arnold_pipelines/megaplan` command was run. The
attempt-5 evidence remains the proof that the unmodified candidate's named
tests only asserted generic `ValueError`; this leaf did not mutate the tree to
reproduce that historical state.

## Final diff and inventory

Final exact identity/diff records are in
`/tmp/oracle-nbf01-rework6-luna-final-0830/final/command-manifest.ndjson`,
manifest SHA-256
`86eba8e5386bb7599ab55246b52d82eb5ef5555db307e6efba01b20383cdd187`.
The six-path production diff digest is
`ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`.

The inventory records are in
`/tmp/oracle-nbf01-rework6-luna-final-0830/inventory/command-manifest.ndjson`,
manifest SHA-256
`c10e450501f3cd9a5a30cd6749c28bfa1f339aba815f5eb4e4efa10ffa050362`.
All modified tracked files and owned untracked source/test files are listed in
the receipt. `tests/arnold_pipelines/megaplan/test_incident_ledger.py` is
unchanged versus `origin/main`: SHA-256
`83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`, git blob
`44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`; the recorded `git diff --exit-code`
also exited 0. The tracked diff-name transcript lists no later-batch source or
test file, and the owned untracked source/test set is limited to the existing
NBF modules.

## Explicit non-actions

No self-review, reviewer, nested harness, commit, stage, push, merge, rebase,
reset, clean, broad-suite rerun, Batch 2 action, or frozen/history/status/
goal/custody/tasklist/plan/North Star mutation occurred. No pass or acceptance
verdict is issued here.
