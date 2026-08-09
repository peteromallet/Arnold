# Sol (gpt-5.6-sol) recovery recommendation for T0/T1 blocks — 2026-08-06

## T0 — re-pin baseline to d5848010
- Do NOT check out c116f38cc (ancestor); do NOT waive identity enforcement.
- d5848010 is the chain launch base, contains c116f38cc, includes later fixes.
- Apply via documented North Star review: change baseline in NORTHSTAR.md, produce a new plan revision + re-finalize (do not mutate plan_v5.md). Regenerated finalize.json must change T0 required HEAD -> d584..., T1 dependency_reasons.T0.required_output likewise, and source-identity checks.
- Record baseline tree 1faf7aa08100aada4838eaf312aac2af244f9dc8.
- Perform/commit the review on the governance/source branch, then recreate/reset the execution worktree to the reviewed baseline.

## T1 — executor isolation/stale environment
- Likely a stale/isolated worker command namespace whose Python did not see host site-packages. NOT a test defect, PATH spelling, or fixed by sys.executable rewrite.
- Minimal durable fix: run `python -c 'import pytest; print(pytest.__file__)'` in the executor sandbox before dispatch; if it fails, classify as infra failure, refresh/recreate executor env, don't charge the task's test budget. Pin the same pytest-bearing env used by validation into executor sessions. Add regression test.
- For this occurrence: retire the stale executor session and grant one replacement test invocation. No reinstall.

## Ordered recovery
1. Pause the chain supervisor.
2. Preserve the 6 dirty entries; park them (named stash incl. untracked).
3. North Star re-pin + regenerate/re-finalize with d5848010.
4. Prepare execution checkout at exactly d5848010; require empty git status.
5. Run T0; record commit d5848010695e28ddb9d9cbee8675d7ebe725caae, tree 1faf7aa08100aada4838eaf312aac2af244f9dc8.
6. Restore only the two T1 files into the worktree.
7. Fresh executor session; pytest import preflight; run the single narrow test (or adopt the passing VJ2 receipt if policy permits).
8. Mark T1 complete without reimplementing.
9. Recover plan to finalized/execute at the current frontier and resume batch execution.
