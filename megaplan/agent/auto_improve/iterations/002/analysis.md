# Iteration 002 — Analysis

**Pass rate: 63%** (12/19 scorable). Up from 56% in iteration 001.

## Passed (12)

- astropy__astropy-12907
- django__django-11099
- django__django-11179
- django__django-11603
- django__django-11749
- django__django-16139
- matplotlib__matplotlib-25311
- pallets__flask-5014
- psf__requests-2317
- pylint-dev__pylint-4970 ← WAIT: this was scored False. Checking...
- pytest-dev__pytest-10051
- scikit-learn__scikit-learn-12973
- sympy__sympy-20590

## Failed (6)

- matplotlib__matplotlib-23314 — **Phase:** n/a | **Pattern:** infra_error | **Why:** Correct patch (gold-identical), FAIL_TO_PASS passes, but PASS_TO_PASS env regressions score it False
- pylint-dev__pylint-4970 — **Phase:** ? | **Pattern:** nondeterminism | **Why:** Passed iter 001, failed iter 002 with no relevant prompt changes
- scikit-learn__scikit-learn-13328 — **Phase:** execute | **Pattern:** wrong_approach | **Why:** Same as iter 001
- sphinx-doc__sphinx-7454 — **Phase:** execute | **Pattern:** wrong_approach | **Why:** Patch looks similar to gold but FAIL_TO_PASS test actually fails
- sphinx-doc__sphinx-7889 — **Phase:** execute | **Pattern:** wrong_approach | **Why:** Same — FAIL_TO_PASS test fails despite plausible patch
- sphinx-doc__sphinx-8035 — **Phase:** plan | **Pattern:** under_scoped | **Why:** Same as iter 001
- sympy__sympy-18199 — **Phase:** prep | **Pattern:** under_scoped | **Why:** Same narrow patch. Prep found 0 code references despite 310s of searching

## Errors (2)

- pydata__xarray-4094 — prep timeout (1200s) on both attempts
- scikit-learn__scikit-learn-13328 — still generating at time of scoring

## vs Iteration 001

| Task | 001 | 002 | |
|------|-----|-----|-|
| pytest-10051 | FAIL | **PASS** | improved — different approach |
| scikit-learn-12973 | FAIL | **PASS** | improved — found both call sites |
| sympy-20590 | ERROR | **PASS** | improved — was scoring infra |
| pylint-4970 | PASS | **FAIL** | regression — nondeterminism |

## Failure Patterns

| Pattern | Count | Tasks |
|---------|-------|-------|
| under_scoped | 2 | sphinx-8035, sympy-18199 |
| wrong_approach | 3 | scikit-learn-13328, sphinx-7454, sphinx-7889 |
| nondeterminism | 1 | pylint-4970 |
| infra_error | 1 | matplotlib-23314 |

## Hypothesis

**Pattern:** wrong_approach (3/7) is now the top pattern, overtaking under_scoped.

**Change:** The pipeline chooses a different approach than gold despite the issue hinting at the correct one. Prep should estimate the scope of the change, and execute should diagnose test failures from tracebacks instead of retrying blindly.

**Why it's general:** Any coding task benefits from knowing the change size up front and understanding test failures.
