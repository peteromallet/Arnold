# North Star: Extension Foundation Completion

## End State

The Reigh video-editor extension foundation is genuinely complete and releasable from a clean checkout. The repository can prove, with source-controlled tests and quality gates, that the extension preview contract is honest; provider persistence is durable; proposal-mode agent mutations are visible and reviewable before application; diagnostics, lifecycle cleanup, and settings forms are host-owned and scoped; and the Extension Manager accurately reflects runtime package state without implying sandboxing, marketplace support, or future composition-spine capabilities.

## Success In One Sentence

From a clean cloud checkout, the extension foundation passes its release gates, production smoke, SDK boundary checks, proposal UI flow, manager enable/disable smoke, and docs consistency checks without hiding deferred work behind supported-language claims.

## Immutable Constraints

- Do not implement the composition-spine epic in this run.
- Do not add marketplace, install-from-URL, discovery, update, delete, dependency resolution, sandboxing, code signing, or runtime permission enforcement.
- Do not claim export/process/sidecar/composition support beyond what current code and tests prove.
- Do not weaken release gates to make them pass. Fix the product/code/docs mismatch or explicitly document a deferred requirement in the correct source-of-truth docs.
- Keep extension code trusted and unsandboxed unless a separate future epic changes the security model.
- Preserve existing editor behavior when no extension packages are supplied.
- Keep proposal application on the existing `TimelineOps.apply` / proposal runtime path; do not introduce a second mutation engine.
- Do not mutate raw timeline internals from extensions, agents, processes, or sidecars.

## Required Proof

- `npm run test:extensions` passes.
- SDK public export governance passes from a clean checkout.
- Extension production smoke is wired into runtime/app behavior and passes.
- SDK packagability is either fixed or explicitly deferred by a failing/non-release gate that no longer blocks this foundation claim.
- Proposal-mode agent output is imported into frontend proposal runtime, visible to the user, and accept/reject tested.
- Extension Manager enable/disable is covered by at least one browser-level or equivalent integrated smoke proving runtime re-resolution and contribution disappearance/reappearance without page refresh.
- Manager settings editing is either backed by the M4 `SchemaForm` path or explicitly documented and tested as a narrower intentional editor.
- Docs reconcile older supported/deferred matrices with the newer foundation state and keep composition-spine work clearly staged.

