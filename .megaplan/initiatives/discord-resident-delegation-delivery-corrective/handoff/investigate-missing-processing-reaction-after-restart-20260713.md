# Investigate missing processing reaction after resident restart

Diagnose why the Discord message replying to “Discord resident reset complete” did not receive the waiting/processing emoji immediately when processing began.

Context:
- This is a Discord-origin request with immutable launch provenance injected by the resident launcher.
- The canonical Discord resident was just restarted.
- The user expected the processing reaction as soon as their inbound message began processing.
- Existing checkout work reportedly includes a reaction lifecycle, but some changes may be uncommitted or not deployed.

Tasks:
1. Inspect the current resident Discord ingress and reaction lifecycle implementation, configuration, tests, installed/runtime code identity, and durable records for this exact inbound message.
2. Determine whether the reaction was never enqueued, enqueued but not delivered, removed too early, suppressed during startup/replay, or absent because the deployed resident does not contain the implementation.
3. Distinguish expected behavior from current actual behavior. The waiting reaction is expected to appear promptly after accepted processing unless a documented exception applies.
4. Do not restart services, send Discord messages/reactions, mutate cloud chains, or run arbitrary remote shell commands.
5. Provide a concise evidence-backed root cause and the smallest safe corrective action. Do not implement unless a tiny local diagnostic-only correction is essential; prefer diagnosis.

Return a concise final summary suitable for automatic reply to the originating Discord message.
