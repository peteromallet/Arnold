# Debug and deploy the Workflow Boundary Contracts gate/superfixer repair

Investigate and, where verified safe, fix and deploy the root cause behind the Workflow Boundary Contracts corrective chain repeatedly failing S2 gate output validation with `missing_required at /north_star_actions`, while its automated fixer repeatedly retries without converging.

Target session: `workflow-boundary-contracts-corrective-20260710`.
Target plan: `s2-contract-foundation-and-20260713-1544`.

Use the constrained Megaplan cloud/operator interfaces and configured initiative/cloud metadata. Do not run arbitrary remote shell commands. Do not restart or duplicate the live chain merely to clear the symptom.

Apply the Superfixer debugging discipline:

1. Establish current ground truth and quantify the repeated signature.
2. Walk watchdog/detector, L1 repair, L2 meta-repair, and L3 progress-auditor custody. For each, determine TRACKED, FIXED, INTENT, and CONTEXT.
3. Identify the first failing fixer layer and why the layer above did not catch or stop the deterministic retry loop.
4. Determine why the gate worker repeatedly omits required `north_star_actions`: inspect the effective schema, prompt/template, output adapter/audit, model retry path, installed/editable runtime parity, and evidence passed to repair.
5. Hunt sibling instances of the same schema/prompt/token/custody failure.
6. Implement the narrow source fix plus regression tests. Do not weaken the schema or completion guard merely to accept malformed output.
7. Verify focused and relevant broader tests. Report unrelated failures distinctly.
8. If deployment prerequisites and tests are genuinely green, deploy through the canonical constrained deployment/runtime mechanism, re-trigger ordinary repair on the original session, and verify that the original S2 advances beyond the failing gate. Do not claim deployment if it was not performed.
9. Add or strengthen the deterministic retry circuit breaker and L3 detection if this failure could otherwise spin indefinitely.
10. Preserve unrelated dirty work and existing chains. Do not push/open PR/restart the Discord resident unless that is an explicitly required, safe, in-scope deployment step; if a human gate or unsafe ambiguity blocks deployment, stop and report the exact required approval.

Return a concise verified summary covering root cause, first broken fixer layer, missed backstop, files/tests changed, deployment state, original-chain recovery evidence, and any remaining blocker.
