# Codex Critique: Agent Process

## Summary

The overhaul targets the right failure: HotShotXL was not a discovery failure, it was a cognitive-contract failure. The agent saw good evidence, inferred "add some relevant ingredients," and the loop accepted landed edits as success. A research -> plan -> execute split will help only if the plan is a hard graph invariant, not another contextual packet.

## Stage-by-Stage View

Classify sees the user request, graph summary/map, and conversation context. It emits route/research hints, not a contract. Its prompt can be over-constrained: external named technologies should route to `adapt`, but there is also guidance not to name ecosystems not visible in the graph. For HotShotXL on an image graph, that can corrupt research before it starts.

Research sees a sanitized classifier query, not necessarily the raw request. It returns best-effort summary, selected precedent, precedent packet/slices, and graph inspection. This is still evidence. It may say HotShotXL maps to AnimateDiff/VHS, but does not force "motion model reaches sampler," "8-frame active path," or "video terminal consumes decoded frames."

Execute turn 0 sees full rendered Python, signatures, node index, research brief, scoped research notes, selected precedent context, and graph inspection. Later turns mainly see current render/diff/report plus compact research memory. The system prompt tells it to use selected precedent as grounding, but also says "apply the smallest evidence-supported edit," and `done()` means "commit landed edits." That framing rewards partial visible progress.

Finish/done sees batch diagnostics, landed op count, failed statements, and some revise-only eligibility. It rejects no-op and failed-statement cases. It does not reject successful but semantically incomplete adaptations.

## Prompt/Goal Problems

"Plan is authoritative unless it contradicts the user" is too soft. The execute agent needs a closed checklist: required roles, edges, terminals, values, and forbidden substitutions.

The plan must distinguish "node may be authored" from "node satisfies a required invariant." Workflow-provisional schemas are useful, but availability does not prove the node is on the active path.

The classifier contract should not only add `needs_precedent_plan`; it should remove contradictory route guidance. External named technology absent from the current graph is exactly when the classifier must preserve that name for research.

## Feedback Problems

Current feedback is mostly local syntax/authoring feedback: wrong fields, no-op, failed statements, read-only search, repeated discovery. That teaches the agent how to make statements land, not how to complete the workflow.

Plan-status feedback must be deterministic and repeated every execute turn, not only after rejected `done()`. The agent should see:

```text
missing: motion_model.model -> sampler.model
missing: active 8-frame latent/image path
missing: video terminal
```

Bounded done nudges are dangerous for semantic blockers. Syntax nudges can be bounded; critical plan conditions must remain candidate-blocking even if the batch budget is exhausted.

## Process Risks

A deterministic planner can be wrong. If it maps the wrong sampler, decoder, or terminal anchor, execute will obediently damage the graph. Plan construction needs confidence and explicit unresolved anchors.

Small/medium/full routing can under-route requests. "Generate 8 frames" sounds simple but implies latent batch semantics and output terminal changes. Trigger rules should privilege output-domain and active-path changes over apparent text simplicity.

Partial custom-node availability is a trap. If one planned node lands and another class is unavailable, the system can still leave a partial candidate unless plan evaluation runs before candidate/apply.

## Recommended Changes

1. Make `ExecutionPlan` the execute-stage authority. Treat research packets as unavailable to execute except through the compiled plan plus exact schema references.
2. Add mandatory `active_path_conditions`: source role, target role, required edge reachability, terminal role, and count evidence.
3. Run plan evaluation before accepting `done()`, before producing a candidate, and before apply eligibility.
4. Put compact plan status in every execute turn.
5. Fix classifier contradictions around external technologies. For absent named tech, route to precedent planning and preserve the name as research input.
6. Add negative tests where relevant classes are added but unconsumed. The pass condition must be graph reachability, not class presence or narrative.
