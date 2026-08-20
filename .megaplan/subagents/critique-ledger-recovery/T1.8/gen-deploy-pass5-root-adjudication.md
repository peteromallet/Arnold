# T1.8 pass-5 root adjudication — ACCEPT

Date: 2026-08-02

## Decision

Accept exact clean commit
`06d41e6b7148db4e5b464131762d63fd697db056`, tree
`a8a67b2e01b9129673afdc7931cb3ffdce03a2de`, for the bounded T1.8 Stage-A
release/rollback interface.

The independent pass-5 report's sole `HARD FAIL` was capitalization of the
descriptive subject supplied in the review prompt: the prompt said `bind...`
while Git stores `Bind...`. The authoritative identity fields were the exact
commit and tree, both of which match. The subject was descriptive, not an
additional cryptographic acceptance field. Rewriting it would necessarily
create a different commit and add no behavioral assurance.

## Evidence accepted

- Independent report:
  `gen-deploy-independent-review-pass5-sol-result.md`, SHA-256
  `373cd887376add06ceee25a466f04cbb6f3e58ba426be21171f4ed8d4c283b13`.
- Exact HEAD/tree/parent and clean worktree were verified.
- The pass-4 wrong-target rollback counterexample is closed before durable
  intent or effect on initial execution, same-process replay, response-loss
  reconciliation, and fresh-process replay.
- Hostile/preservation slice: 16 passed.
- Full release-authority source suite: 186 passed.
- Direct isolated wheel build/import proved changed runtime-module bytes match
  source and wrong-target checks fail closed. The pinned Hatchling 1.27 wheel
  setup could not fetch due DNS; this is an environmental limitation, not a
  product counterexample.

This adjudication accepts only the bounded local interface. It is not cloud
deploy authority or proof that v3 launched.
