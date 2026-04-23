# Failure Catalog

Detailed root cause analysis for every failure across iterations 004-006. Used as the ground truth for phase comparison experiments.

## How to Read

Each entry has:
- **Task**: SWE-bench instance ID
- **Iteration**: which run it failed in
- **Failing phase**: where the root cause originated (not where it manifested)
- **What went wrong**: specific description
- **What the model should have done**: the correct action at that phase
- **Evidence**: file paths and line numbers
- **Keywords**: for automated checking in experiments

---

## Prep Failures (2)

### astropy-13398 (iter 006)
- **Failing phase**: Prep
- **What went wrong**: Prep didn't discover that adding a new module import to `builtin_frames/__init__.py` would cause a circular import in a clean Python environment. The import ordering constraint between `astropy.coordinates` and `builtin_frames` was not surfaced.
- **What the model should have done**: During prep research, trace the import chain: `__init__.py` imports `builtin_frames` which imports the new module which imports from `astropy.coordinates` — circular.
- **Evidence**: `test_output.txt` shows `ImportError: cannot import name 'itrs_observed_transforms' from partially initialized module`
- **Keywords**: circular import, import ordering, partially initialized module
- **Trace**: `results/auto-improve/iteration-006/worker-0/astropy__astropy-13398/*/traces/prep_v1.json`

### sympy-18199 (iter 005)
- **Failing phase**: Prep
- **What went wrong**: Prep didn't discover that `nthroot_mod` is called by `solveset.py` with composite moduli (p=8, p=74). The fix added an early return for `a % p == 0` after the `isprime` check, which is correct for prime p but changes control flow for callers that pass composite p before the NotImplementedError guard.
- **What the model should have done**: Grep for callers of `nthroot_mod`, find `solveset.py:1205`, check what values of `p` it passes.
- **Evidence**: `report.json` shows `test_solve_modular` and `test_residue` both fail
- **Keywords**: composite modulus, nthroot_mod, solveset, callers
- **Trace**: `results/auto-improve/iteration-005/worker-2/sympy__sympy-18199/*/traces/prep_v1.json`

---

## Plan Failures (4)

### django-15252 (iter 005)
- **Failing phase**: Plan
- **What went wrong**: Plan used `router.allow_migrate(self.connection.alias, 'migrations', model_name='migration')` instead of the more conventional `router.allow_migrate_model(self.connection.alias, self.Migration)`. Critique noted this twice but didn't flag it.
- **What the model should have done**: Check how other Django code calls router checks — `operations/base.py:121` uses `allow_migrate_model`.
- **Evidence**: Critique findings show the API mismatch noted but `flagged: false`
- **Keywords**: allow_migrate, allow_migrate_model, router, convention
- **Trace**: `results/auto-improve/iteration-005/worker-0/django__django-15252/*/traces/plan_v1.json`

### django-10973 (iter 006)
- **Failing phase**: Plan
- **What went wrong**: Refactored from `.pgpass` to `subprocess.run` with `PGPASSWORD` env var. Fix handles password case correctly but `test_nopass` (no password) fails — the refactored code doesn't handle the passwordless connection path.
- **What the model should have done**: Enumerate all test cases: with password, without password, with special chars, etc. The plan only considered the password case.
- **Evidence**: `report.json` shows 4/5 FAIL_TO_PASS pass, `test_nopass` fails
- **Keywords**: test_nopass, PGPASSWORD, subprocess.run, passwordless
- **Trace**: `results/auto-improve/iteration-006/worker-1/django__django-10973/*/traces/plan_v1.json`

### sympy-18698 (iter 004)
- **Failing phase**: Plan
- **What went wrong**: sqf_list merge logic uses `.gens` attribute to decide whether to merge factors with matching multiplicity. The logic is incomplete — doesn't handle all cases the SWE-bench tests check.
- **What the model should have done**: Test the merge logic with multiple examples from the issue, including multivariate cases.
- **Keywords**: sqf_list, merge factors, gens, multiplicity
- **Trace**: `results/auto-improve/iteration-004/worker-2/sympy__sympy-18698/*/traces/plan_v1.json`

### pytest-10356 (iter 005)
- **Failing phase**: Plan
- **What went wrong**: Deduplicates marks by `mark.name` only. When class C(A, B) has `@xfail("c")` and A has `@xfail("a")`, processing C first puts 'xfail' in `seen_names`, then A's and B's xfail marks get filtered out. Should dedup by full mark identity (name + args), not just name.
- **What the model should have done**: Think through what "duplicate" means for marks — same name with different args are NOT duplicates.
- **Keywords**: mark.name, dedup, MRO, xfail, seen_names
- **Trace**: `results/auto-improve/iteration-005/worker-1/pytest-dev__pytest-10356/*/traces/plan_v1.json`

---

## Critique Failures (5)

### sphinx-7462 (iter 004)
- **Failing phase**: Critique
- **What went wrong**: Critique didn't flag that the fix handles empty tuples but not single-element tuples (which need a trailing comma). The `if node.elts:` check distinguishes empty vs non-empty but tuples have 3 forms: empty, single, multi.
- **What the model should have done**: Flag: "the fix adds a conditional branch — check all cases: empty (), single (1,), multi (1,2,3)"
- **Evidence**: Critique `flagged: false` on correctness check
- **Keywords**: single-element tuple, trailing comma, node.elts
- **Trace**: `results/auto-improve/iteration-004/worker-0/sphinx-doc__sphinx-7462/*/traces/critique_v1.json`

### astropy-14365 (iter 004 + 006)
- **Failing phase**: Critique (partially) + Gate (iter 006)
- **What went wrong**: Critique flagged the correctness issue (NO data markers become case-insensitive) but in iter 006 the gate PROCEEDed past it despite significant flags. In iter 004, the gate correctly ITERATEd and the revised narrow regex fix still didn't cover data-level case insensitivity.
- **What the model should have done**: Critique should flag that lowercasing commands also lowercases data markers. Gate should not PROCEED past significant correctness flags.
- **Keywords**: re.IGNORECASE, NO, data marker, case-insensitive, QDP
- **Trace**: `results/auto-improve/iteration-006/worker-6/astropy__astropy-14365/*/traces/critique_v1.json`

### astropy-13977 (iter 004 + 006)
- **Failing phase**: Critique
- **What went wrong**: Narrow try/except scope was correct direction but didn't cover all edge cases with empty arrays and binary operations. 8/10 target tests still fail. Critique caught and fixed a different dedup bug but the fundamental scope issue remained.
- **What the model should have done**: Trace through ALL 10 test cases to verify the fix handles each one.
- **Keywords**: try/except scope, empty arrays, binary ufuncs, NotImplemented
- **Trace**: `results/auto-improve/iteration-004/worker-2/astropy__astropy-13977/*/traces/critique_v1.json`

### django-10097 (iter 006)
- **Failing phase**: Critique
- **What went wrong**: 0 critique flags on a regex change that doesn't cover all URL validation test cases. The regex `[^\s:@/]+` is close but misses edge cases the SWE-bench tests check.
- **What the model should have done**: Test the regex against multiple URL patterns, especially edge cases with encoded characters.
- **Keywords**: URLValidator, regex, user:pass, RFC 1738
- **Trace**: `results/auto-improve/iteration-006/worker-6/django__django-10097/*/traces/critique_v1.json`

### django-16631 (iter 005)
- **Failing phase**: Critique
- **What went wrong**: 3 critique iterations (5→3→0 flags), all cleared, but the final implementation still fails the injected test. The critique verified the architecture was correct but couldn't predict the exact test expectations.
- **What the model should have done**: Hard to say — the critique did extensive work. This may be a model capability limit.
- **Keywords**: SECRET_KEY_FALLBACKS, session auth, salted_hmac
- **Trace**: `results/auto-improve/iteration-005/worker-0/django__django-16631/*/traces/critique_v1.json`

---

## Gate Failures (2)

### astropy-14365 (iter 006)
- **Failing phase**: Gate
- **What went wrong**: Gate PROCEEDed with 2 significant open correctness flags and zero flag_resolutions. Handler enforcement wasn't active yet.
- **What the model should have done**: ITERATE — the significant flags describe a real correctness issue.
- **Evidence**: `gate_v1.json` shows `recommendation: PROCEED` with 2 significant flags
- **Keywords**: PROCEED, significant flags, unresolved, override
- **Trace**: `results/auto-improve/iteration-006/worker-6/astropy__astropy-14365/*/traces/gate_v1.json`

### django-15252 (iter 005)
- **Failing phase**: Gate (partially)
- **What went wrong**: Critique noted the wrong API (allow_migrate vs allow_migrate_model) as unflagged findings. Gate never saw them because unflagged findings were invisible to the gate at that time.
- **What the model should have done**: Gate should have seen the unflagged findings and promoted them. (Now fixed — gate sees all findings.)
- **Keywords**: unflagged findings, FYI, promote, allow_migrate
- **Trace**: `results/auto-improve/iteration-005/worker-0/django__django-15252/*/traces/gate_v1.json`

---

## Execute Failures (4)

### django-11885 (iter 004)
- **Failing phase**: Execute
- **What went wrong**: Executor modified test file count assertions despite "don't modify tests" constraint. Required test doesn't exist in repo.
- **What the model should have done**: Not modify test files. Report the constraint conflict.
- **Keywords**: test contamination, modified tests, constraint violation
- **Trace**: `results/auto-improve/iteration-004/worker-1/django__django-11885/*/traces/execute_v1.json`

### django-12325 (iter 004)
- **Failing phase**: Execute
- **What went wrong**: Required tests don't exist. Plan substituted different tests without proving equivalence. Gate warned but review approved.
- **What the model should have done**: Escalate — the required tests don't exist and constraints say don't create them.
- **Keywords**: substituted tests, test equivalence, missing tests
- **Trace**: `results/auto-improve/iteration-004/worker-2/django__django-12325/*/traces/execute_v1.json`

### django-12406 (iter 004)
- **Failing phase**: Execute
- **What went wrong**: Gate explicitly warned "skip test additions." Executor modified test files anyway. Also hit SWE-bench harness registration error.
- **What the model should have done**: Follow the gate's explicit instruction to skip test additions.
- **Keywords**: gate warning ignored, test additions, constraint violation
- **Trace**: `results/auto-improve/iteration-004/worker-1/django__django-12406/*/traces/execute_v1.json`

### astropy-14182 (iter 004)
- **Failing phase**: Execute
- **What went wrong**: C extensions couldn't build. Executor tested against installed astropy package instead of patched source. Tests "passed" in wrong environment.
- **What the model should have done**: Report the build failure, not fall back to testing installed package.
- **Keywords**: installed package fallback, C extensions, build failure, wrong env
- **Trace**: `results/auto-improve/iteration-004/worker-2/astropy__astropy-14182/*/traces/execute_v1.json`

---

## Environment / Scoring Failures (3)

### sphinx-8475 (iter 004)
- **Failing phase**: Scoring environment
- **What went wrong**: Docker missing `roman` package. ALL tests fail with `No module named 'roman'`. Code fix is correct (2-line TooManyRedirects catch).
- **Excludable**: YES — verified against upstream PR
- **Keywords**: roman, missing module, Docker env

### astropy-7606 (iter 006)
- **Failing phase**: Scoring environment
- **What went wrong**: Fix passes all 242 local tests but `test_compose_roundtrip[]` regresses in SWE-bench Docker. Parameterized test with empty args behaves differently.
- **Excludable**: INVESTIGATE — need to compare with gold patch behavior
- **Keywords**: test_compose_roundtrip, parameterized, regression

### django-11820 (iter 005)
- **Failing phase**: Plan (possibly)
- **What went wrong**: 2-line pk alias fix is correct for the reported issue. SWE-bench tests expect something additional. The fix resolves `pk` to the actual primary key field name but the injected test may check for additional behavior.
- **Keywords**: pk alias, ordering, __pk, FieldDoesNotExist
