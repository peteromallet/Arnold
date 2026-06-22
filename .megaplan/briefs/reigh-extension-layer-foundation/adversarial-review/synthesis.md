# Extension Foundation Adversarial Review Synthesis

Date: 2026-06-22

## Runs

- Wave 1: 10 DeepSeek V4 Pro agents, 7 completed, 3 failed due to provider connection errors.
- Wave 2: 10 DeepSeek V4 Pro agents, 10 completed. Wave 2 reran the failed topics and cross-checked the highest-impact wave 1 claims.

Result artifacts:

- `wave1-briefs/`, `wave1-results/`
- `wave2-briefs/`, `wave2-results/`

## Accepted Findings

1. Proposal policy is the highest-risk fake-pass area.
   - The client currently sends `proposal_policy` only on the auto-continuation path, not the first invoke.
   - The edge function does not parse `proposal_policy`, does not pass `timelineMutationMode`, and does not return proposal data.
   - `create_shot` mutates directly and must be explicitly gated or documented as out of policy.
   - Proposal persistence/TTL is not implemented.

2. Provider persistence is aspirational today.
   - Capability flags exist, but `DataProvider` has no extension persistence methods and Supabase has no extension-state/settings/proposal schema.
   - The loader's synchronous repository contract is real; the accepted plan is a sync cache repository over async Supabase/IndexedDB stores, not making the loader async.
   - Provider capabilities must be earned by conformance tests.

3. Contract drift is real and blocks a trustworthy preview freeze.
   - `panels.placement` is required by TypeScript/docs/examples/runtime but rejected by `config/contracts/reigh-extension.schema.json`.
   - `slots.placement` also drifts between runtime and external schema.
   - M1 must add a drift gate before it can be marked done.

4. Lifecycle and diagnostics need concrete cleanup primitives.
   - Diagnostics store lacks `removeByExtensionId`.
   - `extension-render` diagnostics are reported by push and are not replaced or cleared by lifecycle.
   - Render boundary reset must be explicit on re-enable after crash.
   - Diagnostics need capacity bounds and scoped extension-authored reporter source.

5. Manager scope is right but terminology/state model needs tightening.
   - The manager must not imply install/update/marketplace features.
   - `installedPackages` wording is risky; UI should say loaded packages/package states.
   - `loaded: false` collapses disabled/invalid/incompatible/duplicate, so the manager needs an explicit status/reason model.

6. SchemaForm belongs in foundation, but V1 should stay primitive.
   - There is no reusable SchemaForm component today.
   - Ajv and settings default/override behavior already exist.
   - V1 should support primitive fields, required/defaults/common constraints, and accessible errors; arrays/refs/conditionals/custom widgets stay out.

7. Phase 4 readiness should be a gate, not implementation.
   - Do not implement asset/effects/transition/clip-type/agent-tool/live-data families in the foundation.
   - M5 should produce the render planner participation contract, trust/sandbox decision, and family promotion checklist.
   - Timeline overlay should move out of foundation unless separately re-justified.

## Rejected Or Overstated

- The claim that `set_params`, `set_theme`, and `set_theme_overrides` bypass proposal policy was rejected. They route through the existing command/proposal path when `timelineMutationMode` is correctly wired.
- The `create_task` bypass claim is overstated. It creates generation queue tasks, not timeline config mutations. It should be classified deliberately, not automatically treated as a timeline proposal blocker.
- Provider persistence should not force a fully async loader rewrite.
- Phase 4 creative families should not move into foundation.

## Plan Changes Applied

- M1 resolves `panels.placement` toward adding `placement: 'asset-panel'` to schema, with documented examples validated.
- M3 explicitly requires `proposal_policy` on initial invoke and response aggregation of proposal data.
- M3 adds `create_shot` to the proposal-policy audit and removes the overstated shortcut-only framing.
- M5 removes timeline overlay from foundation scope and tightens manager wording around loaded package states.
- The foundation plan gets a third synthesis section for this 20-agent adversarial review wave.

## Net Judgment

The foundation plan still makes sense. The review did not argue for a different architecture. It argues for stricter gates: proposal safety must be proven end to end, persistence must be backed by real repositories/schema/conformance tests, contract drift must fail CI, diagnostics/lifecycle cleanup must be first-class, and the manager/readiness gate must avoid implying a full extension ecosystem.
