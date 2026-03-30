# Iteration 001 — Analysis

**Pass rate: 67%** (10/15 scorable). 3 infra errors with correct patches. 2 true errors (prep timeout, Modal sandbox).

## Passed (10)

- astropy__astropy-12907
- django__django-11099
- django__django-11179
- django__django-11603
- django__django-11749
- django__django-16139
- matplotlib__matplotlib-25311
- pallets__flask-5014
- psf__requests-2317
- pylint-dev__pylint-4970

## Failed (5)

- pytest-dev__pytest-10051 — **Phase:** plan | **Pattern:** wrong_approach | **Why:** Modified `reset()` instead of adding separate `clear()` method. Gold adds new method and rewires callers.
- scikit-learn__scikit-learn-12973 — **Phase:** execute | **Pattern:** under_scoped | **Why:** Fixed `lars_path` call but missed identical bug in `_preprocess_data` call one line away.
- scikit-learn__scikit-learn-13328 — **Phase:** execute | **Pattern:** wrong_approach | **Why:** Used `dtype=np.float64` (scalar) instead of `dtype=[np.float64, np.float32]` (list). Also patch contaminated with unrelated file deletions from dirty workspace.
- sphinx-doc__sphinx-8035 — **Phase:** plan | **Pattern:** under_scoped | **Why:** Core filter logic right but missed merge infrastructure (`merge_members_option()`, `__init__` rewiring) needed for tests.
- sympy__sympy-18199 — **Phase:** plan | **Pattern:** under_scoped | **Why:** Patched `a % p == 0` edge case but gold is 100-line overhaul adding composite moduli support.

## Infra Errors (3 — patches correct)

- matplotlib__matplotlib-23314 — Gold-identical patch. Docker image build fails on Apple Silicon.
- sphinx-doc__sphinx-7454 — Gold-identical patch. Scoring deferred/failed.
- sphinx-doc__sphinx-7889 — Functionally equivalent to gold. Scoring deferred/failed.

## True Errors (2)

- pydata__xarray-4094 — Prep phase timed out (1200s) on large codebase. Both attempts.
- sympy__sympy-20590 — Modal sandbox creation error during scoring.

## Failure Patterns

| Pattern | Count | Tasks |
|---------|-------|-------|
| `under_scoped` | 3 | scikit-learn-12973, sphinx-8035, sympy-18199 |
| `wrong_approach` | 2 | pytest-10051, scikit-learn-13328 |
| `infra_error` | 3 | matplotlib-23314, sphinx-7454, sphinx-7889 |

## Hypothesis

**Pattern:** under_scoped — the pipeline finds the right bug but doesn't discover all the code paths that need fixing.

**Change:** Strengthen the prep prompt to trace all callers/call sites of the buggy code before concluding. Currently prep finds one location and stops. It should grep for all usages of the function/parameter being fixed and report them, so the plan knows the full scope.

**Why it's general:** Any coding task that involves fixing a parameter, function, or pattern used in multiple locations benefits from knowing all the locations up front. This isn't eval-specific — it's how experienced developers work: "where else is this used?"
