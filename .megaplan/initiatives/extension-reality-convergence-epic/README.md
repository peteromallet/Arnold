# Extension Reality Convergence Epic

This epic is the follow-up to extension-foundation completion. It turns the remaining architectural criticism into an ordered Megaplan chain.

The core pattern is convergence:

1. One honest trust model for extensions.
2. One authority path for migrated composition facts.
3. One readiness authority for export.
4. One evidence layer proving the claims from a clean checkout.

## Source Research

Primary synthesis:

- `.megaplan/initiatives/extension-reality-convergence-epic/research/pristine-extension-sensecheck-20260707/pristine-sensecheck-synthesis.md`

Supporting Codex subagent outputs:

- `.megaplan/initiatives/extension-reality-convergence-epic/research/pristine-extension-sensecheck-20260707/results/01-permission-model-truth.md`
- `.megaplan/initiatives/extension-reality-convergence-epic/research/pristine-extension-sensecheck-20260707/results/02-composition-spine-authority.md`
- `.megaplan/initiatives/extension-reality-convergence-epic/research/pristine-extension-sensecheck-20260707/results/03-export-readiness-convergence.md`

Related initiative:

- `.megaplan/initiatives/extension-foundation-completion/`
- `.megaplan/initiatives/reigh-extension-composition-spine-epic/`

## Launch Notes

Run this after the extension-foundation completion sprint has landed and the
finish branch has been merged into the local base. This setup uses
`base_branch: local/extension-foundation-completion`, which currently points at
`origin/main` plus `origin/extension-foundation-finish-20260707`.

This epic deliberately does not include real untrusted-extension sandboxing; it
makes the current trusted-extension model honest and then moves
composition/export authority to the surfaces that can be tested.

Suggested launch:

```bash
megaplan chain start --spec .megaplan/initiatives/extension-reality-convergence-epic/chain.yaml
```

For a cloud run, first push the merged local base under a remote branch and set
both this chain's `base_branch` and the initiative `cloud.yaml` repo branch to
that pushed branch. Do not use plain `main` unless `main` has absorbed the
finish branch.
