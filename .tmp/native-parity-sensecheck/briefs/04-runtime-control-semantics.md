# Lens 4 — runtime/control semantic trace

Working directory: `/Users/peteromalley/Documents/Arnold`. Strictly read-only. Do not modify files.

Trace behavior end to end from authored `workflow.pypeline` and imported native subworkflows/policies through parser/lowering/compiler, engine/runtime, handlers/components, CLI/auto-drive, and persisted run state. Focus on execution, retries/timeouts/model routing, execute DAG batching/fanout/fanin, critique/revise and review/rework caps, tiebreaker/replan, override/human gates, suspension/resume, and path-addressed checkpoints.

For each semantic, identify the actual decision-maker and state carrier. Find divergence, bypass, hidden semantic completion, double-route-brain behavior, non-path identity, restart-vs-resume behavior, or a native declaration ignored by runtime. Exercise targeted read-only tests/commands if useful, but do not alter tracked state. Current dirty checkout is the implementation under audit; compare seven sprint commits only where needed. Return a carrier trace table and ranked gaps with severity, confidence, consequence, smallest correction, and exact `path:line` evidence. Take a firm position.
