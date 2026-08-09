# Execute queued Workflow Boundary Contracts follow-up with partnered-5

Act as the durable resident Megaplan operator for VP todo item `4a568ea1`. Execute this special request end to end, using the canonical `workflow-boundary-contracts` initiative and its `chain.yaml`.

Required profile correction: replace the todo/launch requirement `all-codex` with `partnered-5`. Preserve the task's existing conditions and intent otherwise, and verify the resulting chain spec and actual live run both use `partnered-5` before allowing execution.

Required gates before launch:

1. Confirm the canonical Run Authority epic is genuinely complete (3/3 milestones, completion evidence current, canonical PR merged).
2. Integrate the completed Run Authority result into the Workflow Boundary Contracts target working tree. Megaplan Maintenance is independent and must not be treated as a launch condition.
3. Install that exact Arnold checkout in editable mode in the actual execution environment and prove imports/runtime resolve to that checkout and revision, not a wheel, stale site-packages install, cached build, or another workspace. Treat any mismatch as a hard launch blocker.
4. Re-run the Run Authority manifest gate and launch-safety checks. Do not waive failures.
5. Detect and preserve any existing canonical Workflow Boundary Contracts run. Never start a duplicate chain.

If a prerequisite is not yet satisfied, keep durable custody of the request and wait through the resident special-request lifecycle until it becomes true; do not bypass it. Use Megaplan/cloud constrained operator interfaces and the initiative-specific cloud configuration. Do not use arbitrary remote shell commands. Do not babysit a normal healthy chain; its runner, watchdog, and bounded repair mechanisms own continued progress.

Once every gate passes, launch the canonical initiative chain with profile `partnered-5`, then own necessary bounded operator actions through genuine end-to-end completion. Respect human-only approval gates if encountered and report exactly what decision is required. Mark todo item `4a568ea1` complete only after the epic is genuinely complete and delivery evidence is current; mark it failed only for a real terminal failure, retaining a precise retry reason.

Report concise milestones and a final summary back through the immutable Discord reply provenance inherited from this launch. Include the resident run ID, canonical chain/session identity, gate evidence, final sprint count/state, PR outcome, todo disposition, and any delivery retry/failed/unknown state. Do not expose local filesystem paths in the Discord-facing summary.
