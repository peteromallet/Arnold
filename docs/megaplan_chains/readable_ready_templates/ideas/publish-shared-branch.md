# Publish Shared Branch

Commit and push the accumulated chain work to the single shared branch.

## Branch Constraints

- Work only on `main`.
- Do not create, switch to, or push any other branch.
- Do not open milestone-specific PRs.
- Preserve unrelated pre-existing changes if they are clearly outside the chain's
  claimed work. If in doubt, report them rather than reverting them.

## Tasks

1. Inspect `git status --short` and separate chain-owned changes from unrelated
   pre-existing local changes.
2. Run the highest-signal validation that is feasible after Sprint 8.
3. Commit only chain-owned changes with a clear message such as:
   `megaplan: readable ready template cleanup chain`.
4. Push to `origin main`.
5. Report the pushed commit SHA and any validation gaps.

## Success Criteria

- Exactly one branch is pushed: `main`.
- No milestone branches are created.
- The final pushed commit includes the completed chain work.
- Validation results and any residual risk are recorded in the plan output.
