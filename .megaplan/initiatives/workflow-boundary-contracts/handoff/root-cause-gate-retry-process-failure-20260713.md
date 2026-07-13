# Root-cause investigation: repeated gate retries and failed repair custody

Investigate the very deepest process failure that allowed the Workflow Boundary Contracts corrective chain, session `workflow-boundary-contracts-corrective-20260710`, plan `s2-contract-foundation-and-20260713-1544`, to run the gate roughly 39+ times without advancing.

This is an independent root-cause investigation, separate from the already-launched deployment/recovery operator. Diagnose; do not duplicate that operator's implementation unless a narrow change is essential to prove the root cause and does not conflict with live work.

Use the Superfixer chain-of-custody method. Establish, with durable evidence:

1. Why the gate model repeatedly emitted output missing required `north_star_actions`. Determine whether the schema, prompt, model adapter, structured-output validation, retry context, persistent session reuse, or stale artifact reuse is the initiating defect.
2. Why the retry controller treated the identical deterministic structural-audit failure as retryable dozens of times. Identify the exact retry policy/control-flow path, missing fingerprint/circuit breaker, and why attempts did not escalate after 2-3 identical failures.
3. Why watchdog/L1 repair detected a stall but could not obtain repair custody (`custody_missing`), including the exact identity/provenance/claim contract that failed.
4. Why L2/meta-repair and L3/progress-auditor did not convert that custody failure plus deterministic retry loop into an effective fixer repair. Identify the first failed fixer layer and the layer above that failed to catch it.
5. Why canonical status could simultaneously say `repairing`, show a live process/heartbeat, and yet have no effective repair or normal forward progress. Trace which projections conflate liveness, retry activity, repair dispatch, custody, and advancement.
6. Whether the 39 attempts were genuinely fresh model invocations, persistent-session retries, automated repair re-triggers, or a mixture. Produce an attempt timeline/fingerprint grouping, not anecdotes.
7. Hunt sibling failure paths: other structured-output phases and repair request types that can spin or report repairing without claimed custody.

Constraints:

- Do not run arbitrary remote shell commands. Work from local/on-box durable artifacts, constrained Megaplan status/log mechanisms, repository code, and tests.
- Do not stop or restart the live chain.
- Do not hand-advance or approve the gate.
- Do not weaken the gate schema or acceptance criteria.
- Preserve unrelated dirty work.
- Account for the separate deployment operator already running; avoid overlapping edits.

Deliver a concise but evidence-backed causal chain:

- initiating defect;
- retry-amplification defect;
- repair-custody defect;
- failed backstop defect;
- misleading-status defect;
- the earliest invariant that should have stopped the loop;
- recommended durable fixes and regression tests, ordered by layer;
- whether the currently running deployment operator's intended changes actually address the deepest cause or only symptoms.

Verify claims against source paths, state/events/log records, and targeted tests where safe. The final summary must clearly separate proven facts, strong inferences, and unknowns.
