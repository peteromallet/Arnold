Working directory: `/Users/peteromalley/Documents/megaplan`

Read the current workflow-manifest-runtime plan:
- `.megaplan/briefs/workflow-manifest-runtime/chain.yaml`
- `.megaplan/briefs/workflow-manifest-runtime/review-synthesis.md`
- all six `.megaplan/briefs/workflow-manifest-runtime/m*.md`

Wave 7 focus: semantic parity for agent/tool/model/effect dispatch.

Question: Does the plan preserve the meaning of model/tool calls, agent adapters, capabilities, budgets, idempotency, prompt builders, external effects, and callback recovery while moving execution behind neutral `arnold.execution` contracts?

Look for places where the neutral/product boundary could erase policy, weaken effect guarantees, or leave dynamic shims alive. Return:
- confidence score 0-100
- top capability/effect parity risks
- exact plan edits needed
- what should be contract-tested versus product-tested

Use judgement. Return under 900 words.
