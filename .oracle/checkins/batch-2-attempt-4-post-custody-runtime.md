# Batch-2 attempt-4 post-custody runtime review check-in

## Review boundary

Fresh independent read-only GPT-5.6 Luna/high review of the reconciled tree,
with runtime, physical-door, typed-identity, and persisted-lifecycle focus. No
source/test/frozen/status/history/custody/index edit was made. No commit, stage,
push, merge, Batch 3 action, launcher, delegation, nested model, or batch verdict
was issued.

The original attempt-4 review outputs are explicitly excluded. In particular,
no conclusion from the custody-drifted `819ce9da03694fb25d2c0b6613030e9aa8f1722e`
evolution, its changed goal/status, or the original runtime-review output was
used. The attempt-4 executor finding and receipt were hash-only custody
references and were not used as review evidence.

All captures are under:

`.oracle/evidence/batch-2-attempt-4-post-custody-runtime/`

The complete command records contain literal argv/body, cwd, UTC start/end,
exit code, separate stream byte counts, and stream SHA-256 values in
`command_manifest.json` (64 records; manifest SHA-256
`9df9a458ca3e0ad86ecce17e6368e3da098b502ae27e2be11b57511ab5be8d02`). Each command's
paired `.meta.json`, `.stdout`, and `.stderr` files are retained there.

## Identity and custody

- Branch: `reconcile/nbf-attempt4-2297`.
- Reconciled HEAD: `2297fb330cdb375b4e5bd048f0d5c37d0e06db30`.
- Source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`.
- Candidate implementation: `5da26ec5be4d13559948fe4256a114ad7626482b`.
- Candidate parent/tree: `19deab5bb407273e7e82d40a66fc06d17af93ad4` /
  `e3d0376482154c4f95d2ec5809d630c4a0c32e69`.
- Raw candidate full source/test diff: 153829 bytes, SHA-256
  `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163`.
- Raw candidate production diff (`arnold_pipelines scripts`): 109379 bytes,
  SHA-256 `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32`.
  Both supplied digests were reproduced by
  `candidate_full_diff_raw` and `supplied_production_diff_raw`.
- The index was empty before and after: `post_index_empty` exit 0 with empty
  stdout/stderr SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Source/test porcelain status filtered to `arnold_pipelines`, `scripts`, and
  `tests` was byte-for-byte equal before and after (`pre_post_source_status_compare`,
  exit 0, stdout SHA-256
  `bca02e568bd08199da24f755737ef3721475bd7903585db5b50306ad82690c5e`). No
  untracked source/test path was present after the review.

The consumed artifact hash command (`consumed_artifact_hashes`) rehashed the
packet, tasklist, North Star, sealed manifest, execution brief, custody,
status, goal, policy receipt, and historical hash-only references. Its stdout
is 2008 bytes, SHA-256
`7efffd7e8bac08cce2e9acb9a27d88149f858d4d757abed4faf05c48f45ee8d4`. The
attempt-3 Sol receipt named in an earlier local list was absent; it was not
substituted. Rehashed values matching the immutable bindings include:

- tasklist `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`;
- North Star `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`;
- packet `888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078`;
- execution brief `aac0fc784e5ddf938682298309b94ad4d4f2f5356babb4210467cc440f5368d9`;
- sealed manifest `5238ec05d2f19e798c0fa3e8dc7fbe75876505393ef61411b22fa82a86211e5b`;
- goal `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`;
- status `9f4c6a0794a87d18aaac3e49109baa7ed792d86571483913625ebc1507e362af`;
- custody `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`;
- review-policy receipt `1e22ec54c1c1afb33e3d1faf81d2e49b8b540f6f62dbd7e0b264249716c4bccc`.

## North Star proof

`northstar_exact_match` reports 1515 bytes, `byte_equal: true`, and both the
canonical file and packet block SHA-256 as
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.

The session proof (`session_model_proof`, 2026-08-30T22:33:43.863788Z to
2026-08-30T22:33:43.942290Z UTC) records the declared model as GPT-5.6 Luna/high,
Python 3.11.11 at `/Users/peteromalley/.pyenv/versions/3.11.11/bin/python`,
PID 75483, and `nested_model_launched: false`, `delegation: false`.

## Runtime results

The four ordered criterion probes all passed their existing focused tests:

| Probe | Result | stdout SHA-256 | stderr SHA-256 |
|---|---:|---|---|
| R3-NATIVE focused | exit 0, 4 passed | `b4e6716fbd6745e8531d806d530757d7b2e907a881718c8369d92405a53c4ebc` | empty |
| R3-TERM focused | exit 0, 5 passed | `c45e78d927aa6cc86c3af7ffebe1bb506dc10d7ca7110009debbb589f0b63aac` | empty |
| R3-LIFE focused | exit 0, 5 passed | `dc73d5669fe02105037ac272969a74c0e92d8e4eda11ab9f36efd14f0fd1c648` | empty |
| R3-AUTH focused | exit 0, 5 passed | `31aea369e724e06e40899f30e41b4d08322eb801791b7267f074241d775f0735` | empty |

The full authority test module passed 14 tests (`probe_authority_all`, stdout
SHA-256 `60953c2aaedac1030962d6168ddcfe37af78715bcaf5720a16c5115cbd1d2e06`),
and the repository checker reported `ok: true` with empty diagnostics
(`probe_checker`, stdout SHA-256
`e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2`). The
independent raw-symbol scan also reported no matches (`probe_raw_symbol_scan`,
stdout SHA-256 `68a397053ea9fe0feaebad839a22f290595926ac9af71f2bff8003303da9f96c`).

The exact frozen NBF-02 suite passed 257 tests (`frozen_nbf02_nbf03_suite`,
exit 0, stdout SHA-256
`194ca0548fb95b8376a25371abd519ba22cf25dd4c4f0357b4c7d1ebc1a794a6`). The
exact frozen NBF-03 suite produced 60 passed and the four named babysitter
failures (`frozen_nbf03_suite`, exit 1, stdout SHA-256
`9b71f077fa49a000338e266f0b4e1bf4157922f0381f96d302d87ae63e3a22e6`):

1. `test_babysitter_routing_defaults_to_legacy_deepseek`;
2. `test_legacy_managed_spec_keeps_hermes_controller`;
3. `test_renderer_requires_single_flash_orchestrator_contract`;
4. `test_renderer_cli_mentions_single_flash_contract`.

A clean archive of checkpoint `19deab5bb407273e7e82d40a66fc06d17af93ad4` was
extracted under the unique evidence root. The same babysitter command produced
12 passed and exactly the same four failure identities (`clean_baseline_babysitter`,
exit 1, stdout SHA-256
`548b08a309ef3c66a20564ee7b4ea54d68fbc401ab0ecfee5b18de08fc94feb5`). The
parent-preservation proof passed with stdout SHA-256
`c9fac69c4c9132ffd842a50e733a8ab34b11666ba97a5d931d7bb0c57f5eced8`; the
three preserved file hashes were exactly `285af9a1ac4f2db640d4ca781f426e4c52f2af47203a5deff0f0db805a62f9eb`,
`ba75ceca1f1316864aef83d6f92a81fae2cd4e88c2da0168dac1391d817eb7fa`, and
`4e85a83fa889640abaea70046d73498a2ed407bccffc3434750c764df2c87153`, and the
renderer path was absent from both checkpoint and HEAD. These four failures are
therefore recorded as unchanged baseline behavior, not attributed to this
candidate.

Preserved roots remained green:

- RTB: 59 passed, stdout SHA-256 `242873d5a255859ec3171c3e3831b6eeabb443a11380f3f84ab2ced04cb83238`;
- CHILD: 53 passed, stdout SHA-256 `c5a22b3bada1858d74080777caea657d375787a599db22260e88d2a206889ea6`;
- OMP: 90 passed, stdout SHA-256 `954098f316015bd261566142cea85fdbae7609064276fc67ccf09aca9b6377b3`;
- SCHED: 74 passed, stdout SHA-256 `f9a2faeb34decf442cbb0e4b37a21d3f9e045af232f98ebc7147020e8f06dc35`.

All listed command stderr streams were zero bytes with SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## Direct runtime findings

### R3-NATIVE-001 — unknown native model ids receive positive proof

`workers/_impl.py:7349-7400` checks only broad Codex/Claude name predicates,
then returns a registry and `proof: {constructable: True}` without constructing
the selected backend/runtime/model. `worker_dispatch.py:699-718` accepts this
callback as authoritative; digest recomputation therefore authenticates the
self-described proof rather than proving construction.

- `probe_native_unknown_models` returned `accepted: true`, `constructable: true`
  for both `gpt-5.999-unknown` and `claude-not-a-catalog-model`; stdout SHA-256
  `d874035b32d07315be2570d811b126da64f685b99b19b4544f1251340bd7bd57`.
- `probe_native_production_unknown` supplied a valid mocked runtime seed and
  authoritative runtime binding, then exercised the production admission path.
  The unknown Codex model returned `WorkerAdmissionReceipt` and wrote one
  reservation instead of a typed refusal; stdout SHA-256
  `a8134f610e0681b47923305a2a42c0c9ccaeb3fb9ed1da65538f174e00012651`.

This is a concrete authority failure: exact digest/generation checks are
internally consistent but bind content produced by a classifier-shaped proof,
not a real live catalog/construction result.

### R3-TERM-002 — route/provider identity and conflicting terminal replay are lossy

`DispatchOutcome` in `orchestration/phase_result.py:118-142` has no provider or
route-liveness identity fields. `worker_dispatch.py:845-926` and the terminal
writer consequently serialize only the selected spec and omit the receipt's
provider/route proof identities. In the direct terminal run, the persisted
terminal payload reported `terminal_provider: null` and
`terminal_route_liveness_identity: null` (`probe_terminal_identity_and_replay`,
stdout SHA-256
`eb2813502593201a4f0fe4d3f73278d7e795fedaa1c1bcfd7e46c5d970489709`), while a
second terminal with identical context but `success_payload` changed from
`{"value":1}` to `{"value":2}` returned `replay_conflicting_payload: accepted`.
The idempotency comparison at `incident/ledger.py:802-818` does not compare the
operation payload.

The same probe's terminal payload key set and exact retained payload are in
its stdout capture. This is not a timing or test-fixture assertion; it is a
fresh locked-ledger append/replay exercise.

The managed physical door has a separate closure gap. `cloud/babysitter/launch.py:545-608`
constructs `WorkerAdmissionRequest` and calls `dispatch_with_admission`, but its
closure directly evaluates `ManagedCommandResult(run_managed_command(spec))`;
it accepts no WBC adapter, constructs none, and does not refuse on absent WBC.
The generic managed-door test is a synthetic `dispatch_with_admission` lambda,
not `_admit_managed_launch`, so the 5-test green result does not prove this
physical door. This is the same physical-door contract defect, not a separate
terminal category.

### R3-LIFE-003 — accepted-first persisted history is admitted

`incident/ledger.py:40-96` explicitly permits an `accepted` first marker for a
legacy fixture. The real append door therefore admits an illegal persisted
history: `probe_accepted_first_transition` created a reservation and appended
`accepted` without `not_started` or `entered`, returning
`accepted_first: ADMITTED`; stdout SHA-256
`4d2232074ed1ecaed30fa50ac669f24371849f25d47778db4f6be8f2a4178a37`.
This violates the frozen global transition matrix even though ordinary ordered
replay remains green.

### R3-AUTH-004 — configured-door checker misses contextual cases

The configured repository scan is green, but the checker has two direct gaps:

- `_AuthorityVisitor.visit_Call` at `scripts/check_worker_admission_authority.py:184-199`
  gates process/client/RPC/WBC diagnostics on an enclosing-name regex. In
  configured mode, a helper named `helper` containing `subprocess.Popen` yielded
  no diagnostic.
- `_is_absent_wbc_test` at `:292-315` does not classify `wbc_dispatch is False`
  or `False is wbc_dispatch` as absent-WBC delegation. Both forms yielded only
  `raw_final_launch_access`, not `absent_wbc_legacy_delegation`.

The precise configured-mode probe (`probe_checker_configured_gaps_precise`)
returned these results with stdout SHA-256
`97101a316205ae5aeb1767a2ce3c64079c9ea2b9e04ca9724cb7cb0a4758cc65`. The
repository's 14 passing checker tests cover the current fixture set but do not
cover these frozen adversarial forms.

## KISS/YAGNI and North Star alignment

The implementation retains one central admission/dispatch loop and the
preserved RTB, CHILD, OMP, and SCHED seams; no second scheduler, family lease,
T8 policy, speculative network probe, or second journal was observed. The
remaining defects are authority defects rather than a case for broadening the
scope: a classifier-shaped native proof, a managed physical-door WBC omission,
lossy terminal identity/replay, an illegal persisted predecessor exception, and
checker coverage gaps. They directly preserve the North Star anti-patterns of
assumed model health, incomplete death/route evidence, and judgment from
partial history.

No aggregate Batch-2 verdict is issued here.

## Evidence index

Key command metadata and streams:

- `session_model_proof`, `northstar_exact_match`, `consumed_artifact_hashes`;
- `candidate_full_diff_raw`, `supplied_production_diff_raw`,
  `candidate_changed_path_hashes`;
- `probe_native`, `probe_terminal`, `probe_lifecycle`,
  `probe_authority_focused`, `probe_authority_all`, `probe_checker`,
  `probe_raw_symbol_scan`;
- `frozen_nbf02_nbf03_suite`, `frozen_nbf03_suite`, `preserved_rtb`,
  `preserved_child`, `preserved_omp`, `preserved_sched`;
- `clean_checkpoint_extract`, `clean_baseline_babysitter`,
  `baseline_preservation_proof`;
- direct probes `probe_native_unknown_models`,
  `probe_native_production_unknown`, `probe_terminal_identity_and_replay`,
  `probe_accepted_first_transition`, and
  `probe_checker_configured_gaps_precise`.

Every item above has a matching metadata record and paired streams in the
unique capture root; `command_manifest.json` is the authoritative complete
index.