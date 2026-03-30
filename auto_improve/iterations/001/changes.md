# Iteration 001 — Changes

## What changed

Added step 7 to prep prompt in `megaplan/prompts.py`:

> Once you identify the function, parameter, or pattern that needs fixing, grep for ALL other usages of it in the codebase. If the same parameter is passed in 3 places, all 3 may need the fix. List every call site in relevant_code — do not stop at the first one.

## Why it's general

Any bug fix that involves a function parameter, API pattern, or code convention used in multiple locations requires knowing all the locations. This is how experienced developers work — "where else is this called?" The pipeline was finding one call site and stopping, producing patches that fixed 1 of N locations.

## Evidence

- scikit-learn-12973: Fixed `copy_X` in `lars_path()` call but missed identical usage in `_preprocess_data()` one line away
- sphinx-8035: Fixed the filter logic but missed the merge infrastructure that calls it from multiple `__init__` methods
- sympy-18199: Patched one edge case in `nthroot_mod` but the function is called from `solve` which needs composite moduli support
