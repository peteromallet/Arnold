# Iteration 002 — Changes

## What changed

Two additions to megaplan/prompts.py:

1. **Prep: `estimated_scope` field** — "How big is this change? (e.g., '1-line fix', 'new function needed'). Be honest."

2. **Execute: diagnose test failures** — "If tests fail, read the traceback carefully. Diagnose WHY — don't just retry."

Also: watch_scoring.py now defaults to Modal, has 3-attempt retry, error categorization, and stderr capture.

## Why it's general

Estimating scope helps any coding task — knowing "this needs a new function" vs "this is a 1-line fix" changes how you plan. Diagnosing test failures instead of blind retry is universally useful.

## Evidence

- scikit-learn-12973 (iter 001 fail → iter 002 pass): "grep all usages" found both call sites
- pytest-10051 (iter 001 fail → iter 002 pass): organically chose better approach with more prep context
- sympy-18199 (still fails): prep found 0 references in 310s — estimated_scope might help future iterations
- sphinx tasks: FAIL_TO_PASS tests actually fail — patches have real bugs, not just env issues
