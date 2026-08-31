# Batch 3 NBF-04 — attempt 11 integration packet

## Binding and scope

This packet freezes the cumulative NBF-04 candidate at base checkpoint
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e` on
`reconcile/nbf-attempt4-2297`. It records attempt-10 and attempt-11 control-side
authority fixes on top of the prior cumulative candidate. Scope is NBF-04:
canonical signal/disposition ordering, typed confirmations, PID/start
incarnation safety, WBC cleanup custody, terminal reconciliation, and the
live Python inventory. NBF-05, provider resilience, status/execution-log
mutation, commit, push, merge, deployment, and epic launch remain excluded.

Frozen input identities:

* plan `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
* tasklist `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
* North Star `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
* agent goal `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
* custody `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
* execution brief `1e438fc088d9f95385ad0cd1b827a9aa6f701154d0b16a7bd904725120ffab6e`

## Attempt-10/11 fixes

Attempt 10 bound production `unresolved_launch` results to all seven receipt
fields (plan, phase, family, logical dispatch, admission receipt, semantic
fingerprint, and selected spec), while allowing genuinely absent worker/timing
proof. Production unresolved results now require one matching durable cleanup
handoff. Cleanup handoff and reconciliation handles are checked against the
registered PID and dynamic process-start identity before retention, polling,
reaping, or reconciliation.

Attempt 11 closed two authority gaps. A failed or mismatched later handle is
kept as a local candidate and cannot evict a previously validated retained
parent handle. A selected handoff is checked against the receiving adapter's
reservation, plan, phase, projection, family, logical dispatch, receipt,
fingerprint, selected spec, physical door, and execution-context identity
before custody is touched or any reconciliation event is written. A
cross-adapter handoff therefore returns typed unresolved custody with zero
writes. Regression coverage includes seven receipt-field mismatches, wrong
dead handles against live victims, lawful A custody surviving invalid B, and
both natural-death and permanent-hold cross-adapter attempts.

Prior confirmed blockers are closed: native timeout authorization and
record-before-signal TERM/KILL ordering; crash-after-KILL replay; already-dead
observation/terminal linkage; durable spawn cleanup handoff; pre-acceptance
custody holds; replay-idempotent permanent holds and natural death; wrapper
unwrapping and canonical handoff IDs; PID reuse and no-handle restart safety;
and unresolved-outcome propagation without accepted-result bypass.

## Validation evidence

The cumulative evidence record is **229 passing checks plus 11 attempt-11
checks**. The fresh focused controlled-launch run after attempt 11 is
**26 passed**; Python compilation and `git diff --check` also passed. The
focused run covered controlled/native timeout and replay, custody handoff and
reconciliation, seven cross-reservation context mismatches, wrong-dead-handle
false-death prevention, lawful custody retention, cross-adapter zero-write
rejection, WBC/managed signal contracts, ladder checks, inventory, and
no-bare-subprocess checks.

Known non-candidate baselines remain explicit: unrelated runtime-attestation
seed absence; the OMP fixture's `OMP_RESIDENT_OK` versus stale
`HERMES_RESIDENT_OK` assertion; and the old provider-timeout `124` expectation
versus the current cleanup-hold `75` contract. These are outside NBF-04
control-side scope.

## Canonical framed candidate identity

The exact sorted newline-terminated tracked+untracked source/test manifest has
25 paths and SHA-256
`c6cccbe732ce8b45f65779f95db4b246f0f85a433b0e304a9cb7912b971b9b5e`.
Quarantined Oracle artifacts and generated evidence are excluded.

The canonical aggregate NBF04-DIFF-V1 identity is
`b3945b43cc62136d463745c2c18e2066ee7b1ff8a4d2d81b3c41b4a2c6963f4b`.
The framing is produced by
`.oracle/scripts/nbf04_diff_v1.py` (script SHA-256
`967b9f41bd588ea1265b3eddf22e97b9ce1d8d37e3a5e49b20b23d6b2651a612`) with
the explicit newline manifest
`.oracle/scripts/nbf04-attempt-11.manifest` (manifest SHA-256
`c6cccbe732ce8b45f65779f95db4b246f0f85a433b0e304a9cb7912b971b9b5e`). Run
`python .oracle/scripts/nbf04_diff_v1.py --base
7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e --manifest
.oracle/scripts/nbf04-attempt-11.manifest`. The tool fixes Git
`core.quotepath=false`, empty external diff, disabled text conversion and
rename detection, uses tracked `git diff --binary --full-index` bytes and
`/dev/null` binary diffs for untracked paths, and fails closed on unexpected
absolute headers. Each frame contains path length, T/U status, diff length,
and raw diff bytes. Total framed raw diff bytes are 362278; the deterministic
JSON output SHA-256 is
`eb849a52235b2e1d63a7adf995738c5ce33c6271814fb8ecc28caae73a06b342`.

Per-path status, diff-byte length, and full raw-diff SHA-256:

```text
arnold_pipelines/megaplan/auto.py|T|4798|a4e951cd864b00232ab5e9968dbeb087af12d660457124ab04db6430f7e82c2d
arnold_pipelines/megaplan/cloud/controlled_final_launch.py|T|52422|505f794f023db0554191a3646a81734603be757e7d42cbc9361486eabc859e85
arnold_pipelines/megaplan/cloud/operator_control.py|T|3406|aba77aa3589b8491c87b1e629ef225319b1622a3f23849601d41b39cf2110b05
arnold_pipelines/megaplan/cloud/worker_dispatch.py|T|1801|ff3bc1af384f4bee074ced6bc8330f106f1082db7e0c5948f7c1695e1ee39afc
arnold_pipelines/megaplan/custody/__init__.py|T|794|55b7f8aefc75943e5aaa5cc30ba55c4b4ed00fbec8f849a18cb22b0cfff605dd
arnold_pipelines/megaplan/custody/common_worker_dispatch.py|T|10714|5b9862657185751c868c021dce49d240e44396c8f36d2d241c30608d1d55874c
arnold_pipelines/megaplan/custody/wbc_runtime.py|T|4672|2b2328f8d088093e3ae6c665b02eef67d5a76669059bbe4abfccad3b4d244275
arnold_pipelines/megaplan/incident/disposition.py|T|54053|8a9e767b486c60f0c03db14feee8dd3a746d3489681cf039c22c440d9ccc6b22
arnold_pipelines/megaplan/incident/ledger.py|T|22594|4082916ef4f4fe3ed1bdb9ec4f838fe0d7a8d5637e1b93b748e7422aeb0f41f9
arnold_pipelines/megaplan/incident/schema.py|T|15582|2f0d1082ff9e76b5b5222d32e4eef9d14e27b8fa841317c6d35072538da646ba
arnold_pipelines/megaplan/managed_agent.py|T|18180|35e421038f7eb271a1c43ecc462b6088a6b3a22c21f5d5994d60623378ed5c34
arnold_pipelines/megaplan/resident/agent_loop.py|T|3684|a173605a7144517d2bb1c5f30097074f2cec51a6fd8c2c8d92e57d0f3ba74e60
arnold_pipelines/megaplan/resident/subagent.py|T|6889|cedc18684a2f9d0897e07895826718ae4e906eb2c13886df40a3d5909f977e4c
arnold_pipelines/megaplan/skills/subagent-launcher/fan.py|T|13154|c4f1b20296a5eca193f700a0aee2e18af262f4b09424f0f14364e367c99c077d
arnold_pipelines/megaplan/skills/subagent-launcher/fan_kill.py|T|4111|fb5f177286aa2cbac752f1fe02fca63f4cfe5d31eefa5c92fd37325aeffae92c
arnold_pipelines/megaplan/skills/subagent-launcher/fan_process.py|T|7233|9f07afd7c5f985221a48853d59c0c8be9876b677a01aeb408b146ff3d0293098
arnold_pipelines/megaplan/skills/subagent-launcher/launch_omp_agent.py|T|21978|f0b7ea4430489a24873f708892348c80c1631f22cf51a1c30244a1784743f26a
arnold_pipelines/megaplan/watchdog/worker_identity.py|T|1839|2cd779041eb0d0bf6de8b02a39cb62d822ea2bce1cbcbd76460527ab789e1094
arnold_pipelines/megaplan/workers/_impl.py|T|33334|7c50aed660c9019c3961a3b0da80815d932f5e2b3e04236d9cdbc0477254e932
tests/arnold_pipelines/megaplan/test_managed_signal_contract.py|U|12424|67890f29a628b26b2dcad3dd422c2155d63efb4ebc36d05a2ab89da77724b963
tests/arnold_pipelines/megaplan/test_nbf04_ladder.py|U|12179|b2bfe44d20299b432fa864acd0550c56481cb8e1837ff68ec1add22b612d8546
tests/arnold_pipelines/megaplan/test_python_signal_inventory.py|U|25403|80ce7da13cab9efeb1159503de9d053899ceb787aa8f032858bc1864fcd96fe9
tests/arnold_pipelines/megaplan/test_subagent_launcher_disposition.py|U|3234|4ee2ff8cb7f2cca3ed82773725c4d93485bc5d0ee866c59027016305156ecd27
tests/cloud/test_controlled_final_launch.py|T|26632|99463c6354f7849530bd33b5ae3c72c63e817743fff1efdba59631f317fffb7b
tests/test_no_bare_subprocess.py|T|1168|88867a641787b7c74c5d302aeab3b938e5703e79eb249b8dd09fc5853ae9cfba
```

This packet is intentionally uncommitted and ready for independent Luna
semantic review and the permitted final Sol oracle review. It does not
authorize merge, deployment, or epic launch.
