# HARD FAIL — T1.8 GEN-DEPLOY independent review pass 4

## Scope and position

**HARD FAIL.** Exact candidate
`26d240339e0911a0e7347fc7849c8e151ab92111` is not acceptable for
clean-lineage integration.

The pass-3 displaced-writer blocker is closed, including fresh-process replay
with an empty post-CAS process set. The pass-3 exact-generation repair also
rejects the original coherent vector/manifest substitution and changed
migration records. However, one independently reproduced critical-path variant
remains: a fully signed, digest-coherent rollback backup can carry a generation
for the wrong target. Execution activates it, advances the selector, and
durably resolves the deployment. Only the later independent verifier notices
the target mismatch. The acceptance brief explicitly requires wrong-target
state to fail closed before activation, so this false success is a **BLOCKER**.

This is a bounded local review. It is not a formal T1.8, release, deployment,
production-availability, or production-custody completion claim.

## Frozen identity and input hashes

```text
reviewed commit: 26d240339e0911a0e7347fc7849c8e151ab92111
reviewed tree:   b8e5e1bc50f04942d21d71458260d94594e11e69
parent:          148465a109ade4318e4cb9ae13a83645a4bf2934
repair report SHA-256:
  8b464ea770d0987d3c63a6fe09a2d4f16964e5b5750a65085bf5c532ea38db11
prior HARD FAIL report SHA-256:
  bff46dc2b888e989ae9099d6270f4a4dac0c37dbdaf80e1fd1eba43fdf9b887a
```

Identity command:

```text
$ git rev-parse HEAD HEAD^{tree} HEAD^
26d240339e0911a0e7347fc7849c8e151ab92111
b8e5e1bc50f04942d21d71458260d94594e11e69
148465a109ade4318e4cb9ae13a83645a4bf2934
```

`git status --porcelain=v1 --untracked-files=all` produced no output before
and after the review. `git diff --check 148465a... 26d2403...` also produced no
output. The repair diff is exactly seven files with 704 insertions and 69
deletions.

## BLOCKER — signed rollback activates a wrong-target generation

### Reproduction

The disposable probe used the real fixture, store, hermetic adapter, signed
accepted deployment, signed recovery decisions, recovery executor, and
independent verifier. It performed these exact semantic steps:

1. accept the original generation for `hermetic:control-plane`;
2. construct a second valid `GenerationVector` under a fresh in-root generation
   path, but set its signed `target_id` to `hermetic:wrong-target`;
3. construct canonical backup state selecting that generation and recompute the
   exact backup SHA-256, canonical state digest, generation digest, schema
   digest, and vector digest;
4. sign a rollback decision and recovery-resolution decision whose binding
   still targets `hermetic:control-plane` and whose result selects the
   wrong-target generation;
5. call `execute_recovery_resolution`; and
6. inspect the target/store state and call `verify_recovery_resolution`.

The command was an inline, self-deleting `TemporaryDirectory` probe:

```text
$ PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp .venv/bin/python - <<'PY'
# imported the real conftest authority fixture and test_repair_pass2 helpers;
# built wrong_generation = _forward_generation(authority, "wrong-target")
#     .model_copy(update={"target_id": "hermetic:wrong-target"});
# built canonical initial_hermetic_state() selecting wrong_generation;
# rewrote the disposable signed backup and recomputed all RecoveryPayload digests;
# signed matching rollback RecoveryDecision and RecoveryResolutionDecision;
# executed recovery, inspected adapter/store, and independently verified it.
PY
execute_returned= True
selector_activated= True 2
runtime_target_id= hermetic:wrong-target
store_resolved= RA-wrong-target-resolution
verification= False ('forward_fix_target_mismatch',)
```

The probe made no persistent write: all target/store/backup material lived in a
self-deleting temporary directory. The worktree remained clean.

### Root cause

`RecoveryPayload` validates forward-fix migration lineage but has no rollback
target-identity constraint (`contracts.py:378-411`). In the rollback execution
branch, the restored vector is parsed and its generation digest is recomputed,
but `prior_generation.target_id` is never compared with
`resolution.binding.target_id` before manifest materialization and runtime
activation (`executor.py:1980-2011`).

The live observation primitive itself has the required comparison
(`executor.py:1474-1507`), but rollback reconciliation calls it with
`generation.target_id` loaded from the restored bytes rather than the signed
recovery binding target (`executor.py:2277-2305`). That self-comparison makes
the target receipt current and permits durable completion. The independent
verifier instead passes the authoritative resolution target
(`verifier.py:179-200`), so it detects the mismatch only after activation and
store resolution.

This is not a demand for interpreter-takeover resistance or mathematical
impossibility. All bytes and decisions were validly owner-signed and internally
coherent; the ordinary executor accepted the wrong subject. It is a reproduced
unsafe activation and false success under the incident standard.

## Pass-3 blocker closure results

### Exact generation, manifest, and migration evidence

The original coherent substituted-vector/manifest counterexample is closed.
`observe_installed_generation` independently parses the live vector and
canonical manifest, recomputes both digests, compares them to the signed digest,
checks target identity, and rebuilds the process attestation
(`executor.py:1429-1532`). The committed counterexample now fails verification
with `recovery_signed_observed_generation_digest_mismatch`
(`test_repair_pass2.py:345-472`).

Forward-fix requires an embedded signed `RecoveryMigrationArtifact` and rejects
a bare digest (`contracts.py:347-411`). Execution binds the exact restored
source-state digest, target generation, target state-vector digest, and full
execution record (`executor.py:2033-2064`). A fresh-process probe changed the
persisted execution record's `target_state_digest`; independent verification
returned false with `recovery_target_disagreement`, and replay returned
`recovery_effect_indeterminate` without reaching either runtime-start or
selector-CAS again.

These results do not cure the rollback wrong-target path above.

### Durable displaced-writer lineage

The second pass-3 blocker is closed in the bounded implementation:

- the signed resolution carries observed selector/revision, observed generation,
  and exact displaced writer IDs (`contracts.py:479-494`);
- first dispatch compares that complete tuple with live pre-effect state
  (`executor.py:1406-1427`);
- durable intent records both decision digests and the complete tuple before
  effect, and exact replay compares it (`store.py:1344-1410`);
- execution derives displaced/rejected writers only from the signed tuple and
  persists selector, runtime, rejected IDs, and receipt in one target-state
  replacement before the post-CAS crash hook (`executor.py:1935-1978,
  2069-2173`);
- reconciliation uses the persisted receipt and rejected IDs rather than the
  new runtime process set (`executor.py:2182-2212,2308-2338`); and
- independent verification rebinds intent/receipt to the signed tuple and
  rejects overlap between current and displaced writers
  (`verifier.py:135-219`).

The committed post-CAS fresh-process forward-fix regression passed. An
additional rollback-to-absent probe reproduced the explicitly requested empty
process case:

```text
empty-process fresh replay PASS; displaced=2 current=0 verified=True
missing target proof PASS; outcome=recovery_effect_indeterminate redispatch=0
```

It crashed at `after-recovery-selector-cas`, reopened a fresh store and adapter,
required an empty current process set, preserved both original writer IDs in the
byte-stable receipt/rejected set, forbade a second runtime/CAS dispatch, required
exact second replay, and independently verified the result. Removing the target
receipt after the crash produced indeterminate without redispatch.

## Finite local evidence

All pytest commands used `PYTHONDONTWRITEBYTECODE=1`, `TMPDIR=/private/tmp`, and
`-p no:cacheprovider`. Suites were run sequentially; the installed-wheel suite
was single-flight.

### Exact blocker slice

```text
$ .venv/bin/pytest -q -p no:cacheprovider \
  tests/arnold_pipelines/release_authority/test_repair_pass2.py::test_compatible_rollback_materializes_exact_prior_generation \
  'tests/arnold_pipelines/release_authority/test_repair_pass2.py::test_crash_at_each_restore_forward_fix_edge_replays[after-recovery-selector-cas]' \
  tests/arnold_pipelines/release_authority/test_repair_pass2.py::test_backup_restore_and_forward_fix_are_executable \
  tests/arnold_pipelines/release_authority/test_repair_pass2.py::test_independent_recovery_observation_rejects_wrong_materialized_evidence
8 passed in 1.08s
```

The count is eight because the wrong-materialized-evidence node expands to five
cases: manifest, schema, vector, runtime, and migration.

### Complete source and broad authority gates

```text
$ .venv/bin/pytest -q -p no:cacheprovider \
  tests/arnold_pipelines/release_authority
185 passed in 11.82s

$ .venv/bin/pytest -q -p no:cacheprovider \
  tests/characterization/test_import_surface.py \
  tests/test_pipeline_run_cli.py \
  tests/cloud/test_wrapper_authority_bypass_gating.py
84 passed in 3.78s
```

The 185-case suite covers ordinary exact idempotency/restart, recovery
response-loss and crash replay, 10 recovery restore/forward-fix crash cuts, 12
backup/state crash cuts, stale cached target evidence, signed migration
material, selector/fence races, writer rejection, protected ancestor and lock
replacement, custody tampering, and production fail-closed paths. The broad
suite preserves import, CLI, and wrapper bypass gates.

### Installed wheel/source/minimum/locked parity

```text
$ UV_CACHE_DIR=/Users/peteromalley/.cache/uv \
  PIP_CACHE_DIR=/Users/peteromalley/Library/Caches/pip \
  .venv/bin/pytest -q -p no:cacheprovider \
  tests/installed_wheel/test_release_authority_entrypoint.py
11 passed in 65.64s
```

This independently passed detached source/wheel byte parity, minimum Pydantic
2.11.0 versus locked Pydantic 2.12.5 parity, shipped schemas and entrypoint,
hermetic cutover, accepted-active forward-fix in both environments, protected
ancestor replacement in both environments, and controlled dependency-import
failure. No installed/source mismatch was reproduced.

## Acceptance summary

| Area | Result | Basis |
|---|---|---|
| Exact restored generation/manifest | **FAIL** | Original substitution is rejected, but a digest-coherent rollback generation for the wrong target activates and durably resolves. |
| Signed migration material | **PASS (bounded local model)** | Bare digest rejected; exact record required; changed record verifies false and replay is indeterminate without redispatch. |
| Pre-CAS displaced-writer lineage | **PASS** | Signed, journaled before effect, rebound on reconcile/replay, including fresh-process empty-runtime probe. |
| Exact idempotency and recovery crash cuts | **PASS** | Full 185-case suite plus focused fresh-process probes. |
| Selector fencing / old-writer rejection | **PASS** | Full suite and explicit lineage probes; no duplicate effect or unsafe retry reproduced. |
| Installed wheel/source/minimum/locked parity | **PASS** | 11/11 single-flight. |
| Production fail-closed behavior | **PASS (local claim only)** | Missing privileged adapters/observers and ordinary bypass paths remain closed in the local tests. |
| Prior release-authority guarantees | **PASS except blocker above** | 185 source + 84 broad tests green; candidate-specific wrong-target rollback remains blocking. |

## Nonblocking limitations and external evidence

- The shipped migration artifact models one bounded declarative operation and a
  signed `GenerationVector.state` digest; it is not evidence from a real
  production application-state migration. That production evidence remains
  unavailable locally.
- No cloud/provider API, credential, owner state, production generation,
  selector, process, marker, checklist, plan, or Git ref was touched.
- No privileged production executor/observer, descriptor/mount custody, real
  production cutover, owner custody receipt, or deployed old-writer rejection
  proof was exercised.
- Owner integration and deployed receipts remain separate. No formal T1.8 or
  release/deployment completion claim is made.

The wrong-target rollback false success must be repaired and independently
reviewed before clean-lineage integration. The external limitations above are
not elevated to blockers.
