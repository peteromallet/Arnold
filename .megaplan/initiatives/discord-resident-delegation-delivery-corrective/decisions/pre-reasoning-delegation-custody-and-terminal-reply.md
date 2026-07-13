# Decision: pre-reasoning delegation custody and terminal-reply invariant

## Incident

An explicit request to run a Superfixer subagent was accepted, but the general Codex routing turn timed out after 300 seconds before calling `launch_subagent`. The runtime marked the turn failed and re-raised; the Discord handler logged the exception. No terminal outbound intent was created, `message_sent` remained false, and abandoned-turn recovery did not cover the failed turn.

## Decision

1. Deterministically explicit execution/delegation requests are recorded as requested execution custody during durable acceptance, before general resident model reasoning.
2. The initial router receives a bounded purpose-specific envelope. Large cloud snapshots, initiative inventories, and unrelated history are fetched only after custody when needed.
3. Ambiguity produces a durable blocking-clarification intent.
4. Routing/model timeout, process failure, usage-limit failure, malformed output, and crash atomically record the turn transition and an idempotent terminal failure outbox intent before propagation or logging.
5. Recovery covers accepted messages, requested executions, abandoned turns, and failed/cancelled/timed-out turns. It reconciles any accepted message lacking execution custody, clarification, or terminal delivery/dead-letter custody.
6. Every accepted inbound reaches one durable outcome class: execution custody, blocking clarification, or terminal outbound delivery/dead letter. `failed && message_sent=false` without outbox custody is page-worthy corruption.

## Current-code evidence

- `resident/agent_loop.py` kills the Codex subprocess and raises `AgentLoopError` on model timeout.
- `resident/runtime.py` marks the turn `failed` and re-raises without creating outbound custody.
- `resident/discord.py` logs the propagated error, leaving the user without a failure response.
- Startup recovery covers abandoned turns, not this terminal failed-but-unreplied state.

## Milestone application

- M2: durable requested-execution custody and bounded routing inputs.
- M3: unique launch/replay from that custody.
- M4: terminal outbox creation for every resident failure class.
- M5: continuous/startup reconciliation of custody and delivery gaps.
- M6: timeout-before-launch proof and invariant alerts.

The active M2 runtime plan was finalized before this decision. It must be replanned or explicitly revised against the updated source brief before execution continues.
