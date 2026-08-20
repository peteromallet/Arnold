# HARD FAIL — T1.8 GEN-DEPLOY independent review pass 5

## Decision

**HARD FAIL** against the requested exact identity. The pass-4 wrong-target
rollback blocker is closed in the reviewed tree, but the supplied identity is
internally inconsistent: commit
`06d41e6b7148db4e5b464131762d63fd697db056` records subject
`Bind rollback recovery to authoritative target`, while the required exact
subject is `bind rollback recovery to authoritative target`.

This is the sole blocker. If the subject line in the review request was intended
as a case-insensitive description, the bounded source/behavior verdict is
**PASS**.

## Exact Git identity and cleanliness

```text
$ git rev-parse HEAD HEAD^{tree} HEAD^
06d41e6b7148db4e5b464131762d63fd697db056
a8a67b2e01b9129673afdc7931cb3ffdce03a2de
26d240339e0911a0e7347fc7849c8e151ab92111

$ git show -s --format='%s' HEAD
Bind rollback recovery to authoritative target

$ git status --porcelain=v2 --untracked-files=all
<no output>

$ git diff --check HEAD^ HEAD
<no output>
```

The status remained empty after review. The complete parent-to-candidate diff
was inspected: 8 files, 478 insertions, 36 deletions. No source or Git state was
edited.

## Pass-4 counterexample outcome

The repair binds the authoritative target in the signed recovery and resolution
contracts, performs a read-only parse of the exact signed backup before durable
intent, checks both the canonical backup state's `target_id` and every embedded
`GenerationVector.target_id`, persists the target claims in intent/receipt
lineage, and uses the authoritative target during reconciliation and independent
observation. A receipt cannot claim the authoritative target while restoring a
different target: `restored_target_id`, the recomputed backup bytes/vectors, the
signed target, and live observation must all agree.

A fresh inline, self-deleting hostile probe used an owner-signed,
digest-recomputed rollback whose canonical backup itself named
`hermetic:wrong-target` while the authoritative target remained
`hermetic:control-plane`. It exercised direct reconciliation, initial execution,
same-process replay, fresh-process replay, and independent verification:

```text
direct_reconcile=unknown
initial_same_process=recovery_target_mismatch,recovery_target_mismatch
fresh_process=recovery_target_mismatch exit=0
dispatch_counts={"resolve": 0, "write": 0}
durable_state_unchanged=True
verifier=False errors=recovery_event_lineage_missing
```

The committed complementary hostile case, with a right-target canonical state
embedding a digest-coherent wrong-target generation, also failed before intent
or effect. Its assertions cover unchanged selector, store, deployment, target
files, runtime/manifest dispatch, same-process replay, and spawned replay.

## Commands and results

Targeted hostile/preservation slice:

```text
$ PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp .venv/bin/pytest -q \
    -p no:cacheprovider \
    tests/arnold_pipelines/release_authority/test_repair_pass2.py::test_digest_coherent_wrong_target_rollback_is_zero_effect_fail_closed \
    tests/arnold_pipelines/release_authority/test_repair_pass2.py::test_compatible_rollback_materializes_exact_prior_generation \
    tests/arnold_pipelines/release_authority/test_repair_pass2.py::test_backup_restore_and_forward_fix_are_executable \
    tests/arnold_pipelines/release_authority/test_repair_regressions.py::test_recovery_effect_response_loss_reconciles_exact_signed_result \
    tests/arnold_pipelines/release_authority/test_repair_regressions.py::test_recovery_crash_boundaries_replay_idempotently \
    tests/arnold_pipelines/release_authority/test_repair_pass2.py::test_independent_recovery_observation_rejects_wrong_materialized_evidence
16 passed in 1.51s
```

This independently covered valid rollback, valid forward-fix, real response-loss
reconciliation, rollback/forward-fix crash replay, wrong materialized evidence,
and the wrong-target initial/same-process/fresh-process paths.

Complete focused source suite:

```text
$ PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp .venv/bin/pytest -q \
    -p no:cacheprovider tests/arnold_pipelines/release_authority
186 passed in 10.79s
```

The narrow pinned installed-wheel command selected
`test_minimum_and_locked_wheels_preserve_authority_bytes` and
`test_installed_wheel_cli_executes_accepted_active_forward_fix`; it could not
build because the sandbox could not fetch the absent cached
`hatchling==1.27.0`. All three expanded cases ended as setup errors before
candidate code ran. A self-deleting direct wheel
build with the locally installed Hatchling 1.29.0 then verified the four changed
runtime modules were byte-identical to source and executed an isolated wheel
import probe:

```text
wheel_build=PASS(hatchling-1.29-direct)
changed_bytes_exact=True
origin=.../arnold-0.23.0-py3-none-any.whl/arnold_pipelines/release_authority/executor.py
wrong_target_codes=recovery_target_mismatch,recovery_target_mismatch
valid_absent=absent,absent,absent
installed_probe_exit=0
```

Thus verifier, source, and shipped runtime-module semantics agree for the
bounded target check; the unavailable pinned build environment is recorded as
an environmental limitation, not a second blocker.

## Sole bounded blocker

The required exact subject and required exact commit cannot both be true. Git
commit `06d41e6b...` has uppercase `Bind`; changing it to lowercase necessarily
creates a different commit object. Acceptance requires the authority to correct
the requested subject spelling/case or provide the replacement exact commit
identity.
