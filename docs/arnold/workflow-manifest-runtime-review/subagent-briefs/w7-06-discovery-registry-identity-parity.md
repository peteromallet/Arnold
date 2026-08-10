Working directory: `/Users/peteromalley/Documents/megaplan`

Read the current workflow-manifest-runtime plan:
- `.megaplan/briefs/workflow-manifest-runtime/chain.yaml`
- `.megaplan/briefs/workflow-manifest-runtime/review-synthesis.md`
- all six `.megaplan/briefs/workflow-manifest-runtime/m*.md`

Wave 7 focus: semantic parity for discovery, registry, and identity.

Question: Does the plan make every surviving pipeline line up with one coherent identity model across package discovery manifests, pipeline ID registries, generated metadata, `build_pipeline()`, `WorkflowManifest.id/version/hash`, trust classes, tenant derivation, and installed-wheel discovery?

Look for split-brain identity, stale registries, trust bypass, or generated metadata that can disagree with the final manifest. Return:
- confidence score 0-100
- top identity/discovery risks
- exact plan edits needed
- required conformance tests

Use judgement. Return under 900 words.
