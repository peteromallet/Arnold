# Resident model timeout recovery — 2026-07-15

This note records a bounded corrective within the existing Discord Resident Delegation Delivery Corrective initiative. It does not create a separate initiative or authorize deployment/restart.

## Incident evidence

- Resident turn `turn_d7a5ac014199`, triggered by `msg_bb1e93d694a6`, ran from `2026-07-15T20:13:24.267795Z` to its failed terminal record at `2026-07-15T20:19:06.442214Z`.
- The pinned runner applied `MEGAPLAN_RESIDENT_MODEL_TIMEOUT_S=300` and recorded `AgentLoopError: codex exec timed out after 300s`, followed by generic failure message `msg_4130e57383af`.
- The durable Codex rollout `019f6769-bd3c-7d73-841c-94c54ff68de8` disproves a hung model. It continued making bounded repository/context-search tool calls through the deadline and emitted a complete 599-character answer at `2026-07-15T20:19:06.011Z`; the rollout completed at `2026-07-15T20:19:06.083Z`.
- The native invocation therefore completed roughly 36 seconds after the fixed deadline. `asyncio.wait_for` had already cancelled `communicate()` at the deadline and waited for that cancellation to settle; when control returned, the runner unconditionally took the timeout branch and discarded the now-valid output. The existing cleanup also targeted only the direct PID, a separate latent descendant-leak risk, but durable evidence does not establish that a descendant leak caused this incident. The request prompt was about 83 KiB and below the configured 700,000-character pre-dispatch cap; there is no evidence of prompt-limit starvation.
- Contributing inefficiency: the model issued repeated serial context searches, including invalid `--limit 50` attempts and multiple 20–30 second waits, before finding the canonical artifact.

## Corrective invariant

The Codex CLI runner gets exactly one bounded continuation of the same invocation after the initial timeout. It does not replay the prompt or any tools, so possible effects are not duplicated. A successful continuation records structured timeout-recovery diagnostics on the completed turn. If the grace window is exhausted, the entire isolated process group is terminated and the terminal warning/reply identifies the initial timeout, grace cap, elapsed time, output byte counts, and the fact that no invocation replay occurred.

The defaults cap one invocation at the configured model timeout plus one 60-second grace window. Operators may set `MEGAPLAN_RESIDENT_MODEL_TIMEOUT_RECOVERY_GRACE_S=0` to disable grace without removing process-group cleanup.

## Original lookup result

The closest canonical match is the initiative **Durable Session Knowledge Compiler** (`session-knowledge-compiler`). The conversation at `2026-07-13T20:21:49Z` requested structured per-subagent summarisation into durable session knowledge. The initiative's actual checkpoint is roughly every 100,000 newly persisted tokens plus terminal states; no initiative, ticket, document, or earlier conversation match was found for a 20,000-token threshold.
