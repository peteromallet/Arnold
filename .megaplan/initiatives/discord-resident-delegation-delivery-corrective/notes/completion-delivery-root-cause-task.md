# Completion delivery root-cause and repair

Investigate the resident-managed subagent completion delivery failure to its deepest root cause. Recent completed Discord-origin runs have completion outboxes stuck pending with zero attempts, and historical failed deliveries also exist.

Required outcomes:

1. Trace the complete lifecycle from durable subagent completion through result materialization, outbox claim, terminal sweep, Discord provider send, retry, and persisted delivery state.
2. Establish why completed runs can remain pending with zero attempts. Check service/runtime wiring, sweep scheduling, process lifecycle, exceptions, transactional boundaries, idempotency, provenance/reply-target validation, and interactions with test-bot suppression and reset-notification changes.
3. Distinguish every recent pending and failed delivery by concrete cause. Do not claim delivery without provider message-ID evidence.
4. Implement the smallest robust repair, including regression tests for the exact failure modes and protection against duplicate replies.
5. Safely re-drive eligible pending/failed completion deliveries after the repair, preserving stable idempotency and exact Discord reply targets. Do not resend already-delivered results.
6. Verify end to end with focused tests and durable state evidence. If a resident restart is required, use only the canonical command `agentbox services restart agentbox-discord-resident`; note that it may interrupt the current Discord turn. Never use pkill, killall, cgroup-wide stops, or tmux cleanup.
7. Preserve all resident-managed agents and Megaplan/cloud chains. Do not launch, resume, pause, or modify chains.
8. Keep durable planning notes under this initiative only. Return a concise final summary with root cause, code changes, tests, redrive outcomes, unresolved delivery states, and evidence.

This is a high-risk, cross-cutting debugging/root-cause task (D9). Work autonomously until repaired and verified, stopping only for a genuine human approval gate.
