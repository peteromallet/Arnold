Working directory: `/Users/peteromalley/Documents/megaplan`

Read the current workflow-manifest-runtime plan:
- `.megaplan/briefs/workflow-manifest-runtime/chain.yaml`
- `.megaplan/briefs/workflow-manifest-runtime/review-synthesis.md`
- all six `.megaplan/briefs/workflow-manifest-runtime/m*.md`

Wave 7 focus: semantic parity for generated/operator-facing artifacts.

Question: Does the plan guarantee that generated skills, composed rules, docs, projections, scaffolds, templates, package disposition data, and examples teach and enforce the same final manifest-backed behavior that the code implements?

Look for docs/skills that might remain syntactically updated but semantically old, especially around runtime state, CLI, package authoring, and pipeline IDs. Return:
- confidence score 0-100
- top generated-artifact risks
- exact plan edits needed
- freshness/provenance gates that should exist

Use judgement. Return under 900 words.
