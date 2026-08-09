# Luna explorer 4 — lease, launch, and liveness fencing

You are GPT-5.6 Luna, read-only, high reasoning. Do not edit files, launch
cloud commands, or use collaboration tools. Return under 1200 words.

Read `sol-p2-framing-result-20260804.md`, `sol-final-plan-20260804.md`, and
`luna-synthesis-20260804.md`. Known symptoms: managed lease acquisition was
swallowed; sidecars/tmux/markers made runs look alive; stale active-step PIDs
were reported; dispatch could publish progress without authoritative live
runner proof.

Audit lease acquisition/takeover, runner launch verification, PID/start-time
checks, heartbeat/marker code, supervisor, watchdog registry, and cloud status
observation. Trace exception handling and the exact fields currently used to
claim ownership or liveness.

Decide the smallest fenced lease protocol: lease ID/generation, process-start
identity, exact command/runtime/source/session/container, verification deadline,
renewal, expiry, and takeover. Provide fault-injection acceptance tests for
lease failure, marker-only, tmux-only, PID reuse, expired-but-live owner,
identity mismatch, and a valid launch. Identify which legacy cases must remain
human-gated.
