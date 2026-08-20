# T1.5 canonical `simple_fixer` — repair pass 2 result

## Disposition

The seven blocker groups independently reproduced in pass 1 are repaired in the
bounded local source/evidence scope. All requested local finite validation is
green. This document is an implementation result, not a formal T1.5 completion
claim, owner acceptance, deployed-runtime acceptance, or evidence that the
incident/epic advanced.

No cloud/provider call, deploy, restart, production owner/socket interaction,
production state mutation, push, checklist edit, or git operation outside the
designated worktree was performed.

## Frozen input and output identity

- Worktree: `/private/tmp/arnold-critique-recovery-simple-fixer-20260802`
- Exact clean evidence head admitted: `4bfd5fb2cc0d174297260aee6da7cb9a347f6a6a`
- Evidence-head tree: `066c22a540ff9983380760088e2daa9113cbb539`
- Independent pass-1 HARD FAIL report SHA-256:
  `9c0a4ebc7afd39466dcb12241d72bf8b994ad1a936cf5b0205bdb39d66f0e1d6`
- Repair commit: `ea7fb2aacb6622a7e18ea4a579019ae271aa52ec`
- Repair tree: `5077ceff4e9ccd8958051acd999fb86172233f8f`
- Repair parent: `4bfd5fb2cc0d174297260aee6da7cb9a347f6a6a`
- Commit subject: `fix(recovery): close simple fixer authority blockers`
- Worktree after commit: clean; branch
  `critique-recovery-t1-5-simple-fixer-20260802`

## Bounded repairs

### B1 — owner authority, peer, and response binding

- Production uses only the fixed `/run/arnold/recovery-owner-v1.sock` endpoint.
  The socket path must be a root-owned Unix socket and the connected peer is
  authenticated with `SO_PEERCRED`/`getpeereid`; unsupported peer authentication
  fails closed.
- Requests bind protocol/schema, operation, exact occurrence, canonical payload,
  and request digest. Responses have an exact outer shape and bind the same
  operation, occurrence/request digest, owner revision/fence, inner result
  identity, result digest, and owner-derived response digest.
- Intake accepts only exact F01 identity. The owner resolves the pre-existing
  RA/Custody/WBC record and validates grant revision/fence, lease/epoch/fence,
  and GLEK. Caller `AuthorityEnvelope` data is rejected at CLI, adapter, and
  owner intake boundaries.
- The conformance owner is now visibly named
  `TestOnlyHermeticRecoveryOwner`, can only be constructed through `for_test()`
  with preinstalled typed owner records, and has no callback/effect object seam.
  Its bounded simulated effect is one row in its own SQLite owner store.

### B2 — canonical result reconciliation

- Terminal replay verifies canonical result, intent, and receipt bytes against
  occurrence, execution request digest, attempt, claim/epoch/fence, authority
  digest, owner-record digest/revision/fence, WBC GLEK, state, result digest, and
  the current owner record before returning bytes.
- Missing, deleted, corrupt, substituted, partial, or mismatched result,
  receipt, attempt, claim, occurrence, or owner record is typed
  `RESULT_RECONCILIATION_UNKNOWN`/owner UNKNOWN and never redispatched.
- The exact `FORGED-RESULT` single-column database probe is checked in. Separate
  hostile probes cover result deletion, receipt deletion/corruption, attempt
  substitution/authority mismatch/deletion, and owner-record deletion.
- Response-loss remains indeterminate and non-redispatchable.

### B3–B5 — ordinary execution seams retired at point of use

- `AUTOMATIC_RUN_KINDS` contains only `automatic_research_subagent`; all eight
  recovery kinds are rejected before mutation by reservation, public execution,
  deepest imported locked execution, and manifest validation.
- `repair_source_initiative` and its internal copy/overlay functions are hard
  tombstones before filesystem work.
- `repair_goal` mutators and direct module main, `repair_investigation` mutators
  and direct module main, and repair queue decision/dispatch/claim/internal store
  mutators are typed point-of-use tombstones.
- Seven legacy wrappers always emit a typed retirement record and exit 78 with
  zero mutation/agent-launch counters. The only immediate/reconciler delegates
  are the canonical installed owner entrypoints.
- Normal imported aliases, direct module execution, reservation, and the deepest
  managed executor have explicit no-side-effect regression probes.

### B6 — separate fix-the-fixer transaction and stable provenance dedupe

- Callers submit only an exact occurrence. Owner-preinstalled authorization is
  bound to that occurrence/fence, canonical implementation and backstop SHA-256
  digests, approved target generation, authority revision, and an independently
  signed verifier decision in the test owner model.
- Intent, result, verifier receipt, and authorization-consumption state are
  durable and exact-replayed. Forks, corruption, incomplete data, missing
  verification, or deletion of a consumed transaction remain typed UNKNOWN and
  cannot recreate a transaction. There is no ordinary fallback or agent launch.
- Provenance dedupe is stable occurrence + typed error code + subject. Free-form
  detail is projection-only; the exact two-detail probe produces one obligation
  and one quiet transition.

### B7 — honest coverage and dynamic inventory

- All 28 module-wide skip declarations were removed. Every original test
  function/parametrization remains collected: exactly 741 historical case IDs.
  Each now exercises a subject-specific typed retirement/no-side-effect contract
  (queue, goal, investigation, source copy, exact wrapper, or canonical trigger)
  rather than skip/xfail/collection hiding.
- The static narrow JSON inventory was deleted. Runtime discovery now scans all
  shipped `arnold`, `arnold_pipelines`, and `scripts` files; Python modules and
  direct mains; package data; installed scripts; wrappers; systemd units;
  container/templates; and every discovered non-Megaplan pipeline root.
- Current dynamic result: 1,247 entries, comprising 1,067 Python modules,
  22 wrappers, 7 systemd surfaces, 9 container/template surfaces, 4 installed
  scripts, 137 package-data surfaces, and 1 script; zero violations. A hostile
  fixture proves new module/main/wrapper/systemd/container/installed-script
  bypasses are discovered.

## Finite validation on repair tree `5077ceff...`

### Focused owner, crash/concurrency, hostile, retirement, and dependency gate

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q \
  tests/cloud/test_simple_fixer.py \
  tests/cloud/test_simple_fixer_retirement.py \
  tests/cloud/test_progress_auditor.py \
  tests/cloud/test_repair_delegation.py \
  tests/cloud/test_wrapper_authority_bypass_gating.py \
  tests/m9/test_bypass_gating.py \
  tests/resident/test_fix_the_fixer_command.py \
  tests/test_managed_agent.py \
  tests/arnold_pipelines/megaplan/watchdog/test_repair_runner.py
112 passed in 11.00s
```

`tests/cloud/test_simple_fixer.py` contains the original 22 focused
concurrency/crash cases plus the new hostile probes and passed as part of this
112-test command. Its final standalone count is 32 cases.

### Restored historical retirement cases

```text
rg -l 'assert_historical_recovery_case_retired' tests/cloud/test_*.py |
  xargs python -m pytest -p no:cacheprovider -q
741 passed in 3.48s
```

### Full cloud suite, single-flight

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider tests/cloud -q
2151 passed in 45.76s
```

There were zero skips, xfails, or collection-hidden recovery modules.

### RA/Custody/WBC/dependency closure

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q \
  tests/custody/test_action_gate.py \
  tests/run_authority/test_dependency_closure.py \
  tests/m11/test_wbc_acceptance_semantics.py \
  tests/arnold_pipelines/megaplan/test_authority_dispatch_grants.py \
  tests/arnold_pipelines/megaplan/test_custody_contracts.py \
  tests/arnold_pipelines/megaplan/test_custody_lease_store.py \
  tests/arnold_pipelines/megaplan/test_current_epoch_custody.py \
  tests/arnold/workflow/test_native_wbc_adoption.py \
  tests/arnold/workflow/test_wbc_queries.py \
  tests/cloud/test_process_adapter_wbc.py \
  tests/cloud/test_dependency_manifest_repair.py
319 passed in 1.93s
```

### Installed wheel and materialized wrappers

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q \
  tests/installed_wheel \
  tests/arnold_pipelines/megaplan/test_wheel_smoke.py
9 passed in 71.78s
```

This includes built-wheel entrypoints, generic `arnold simple-fixer`, and wrappers
created by the installed `materialize_deploy_dir()`, all outside source imports.
Both immutable-help equivalence and fixed-owner absence (exit 69, no fallback)
are asserted.

One precursor packaging invocation exhausted the local volume because two old
generic smoke cases independently installed the entire runtime dependency graph.
It did not reach a product assertion. The smoke fixture was aligned with the
existing installed-wheel fixture: wheel-isolated install with `--no-deps` while
reusing the validation environment's pinned dependencies. Only that failed run's
exact disposable pytest directory was deleted. The final exact-tree run above is
green.

### Static, compile, shell, inventory, and diff checks

```text
focused ruff: All checks passed!
compileall: passed for arnold, arnold_pipelines, tests/cloud, tests/installed_wheel
AST parse: passed for all shipped Python modules
shell syntax: passed for every shell-shebang cloud wrapper
dynamic inventory: 1247 entries; 0 violations
historical collection: 741 tests collected
git diff --check: passed
recovery skip/xfail/collect-ignore scan: no matches
production callback seam scan: no __test_only_recovery_effect__ matches
```

## Limitations and required next authority

- This is local source and conformance evidence only. No accepted external
  production owner implementation or signed production response was available
  to validate.
- No deployed owner receipt, installed-release receipt, authorized production
  fix-the-fixer transaction, independently deployed verifier result, or real
  incident advancement receipt was created.
- A new independent Sol-high review must inspect commit
  `ea7fb2aacb6622a7e18ea4a579019ae271aa52ec`. Only after that review and later
  deployed owner receipts could a formal T1.5 claim be considered.
- Therefore this report intentionally makes no formal T1.5 claim.
