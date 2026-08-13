---
name: babysitter
description: Status-trigger epic babysitter for blocked/errored cloud chains. The watchdog's MEGAPLAN_SUPERFIXER_ONLY status trigger renders this goal and launches ONE detached hermes:deepseek:deepseek-v4-flash managed agent whose prompt drives the whole recovery itself: deploy a bounded read-only swarm via skills/subagent-launcher/fan.py over the failure evidence -> hand the packed context to codex (codex:gpt-5.6-sol, high reasoning) for a proper solution proposal -> implement the narrowest source-level fix -> relaunch the chain (megaplan resume / chain start) -> prove movement (chain-*.json last_state leaves blocked, same failure_fingerprint does not recur). Use when a cloud chain is blocked/errored and the watchdog status trigger must recover it with the single-flash-prompt flow.
---

# Babysitter (status-trigger)

This skill is the goal protocol for the watchdog's status-trigger superfixer
dispatch (`MEGAPLAN_SUPERFIXER_ONLY=1`). It is DISTINCT from `fix-the-fixer`,
though both are single agents:

- `fix-the-fixer` is the single-agent meta-fixer: exactly one mutation owner,
  no fan-out, no subagents. Its renderer lives at
  `skills/fix-the-fixer/scripts/render_goal.py`.
- `babysitter` is the single-agent ORCHESTRATOR: ONE Flash agent
  (`hermes:deepseek:deepseek-v4-flash`) whose goal prompt drives the whole
  swarm -> codex -> implement -> relaunch -> prove flow. It deploys its own
  bounded read-only swarm over the failure evidence, consults codex for the
  solution, implements the narrowest source-level fix, relaunches the chain,
  and proves movement.

Never reuse the fix-the-fixer renderer for the status trigger — the babysitter
needs the full orchestration prompt, not the meta-fixer prompt.

## Render

```bash
python "<skill-dir>/scripts/render_babysitter_goal.py" \
  --target "<session>" --workspace "<ws>" --plan "<plan>" \
  --failure-json "<latest_failure.json>" --occurrence-digest "<digest>"
```

The renderer embeds the session/workspace/plan context plus the failure
evidence (`latest_failure`, `planner_repair`) and requires the five-step flow:
swarm -> codex -> implement -> relaunch -> prove.

## The prompt drives the flow

The status trigger renders this goal and launches ONE detached
`hermes:deepseek:deepseek-v4-flash` managed agent (the babysitter) with the
goal as its prompt. The babysitter is the orchestrator of the whole flow — it
must not hand the outcome to a separate orchestrator process, and it must not
collapse to an un-swarmed single pass:

1. **Swarm** — over the failure evidence, fan out one bounded read-only
   investigator per scoping question through `skills/subagent-launcher/fan.py`
   (`hermes:deepseek:deepseek-v4-flash` investigators).
2. **Codex** — hand the packed context (evidence pack, swarm index, every
   investigator report) to `codex:gpt-5.6-sol` (high reasoning) for a proper
   solution proposal.
3. **Implement** — apply the narrowest source-level fix in the approved
   editable runtime and verify it against the focused regression.
4. **Relaunch** — restart the chain via megaplan resume / chain start as the
   evidence requires; never `--fresh`.
5. **Prove** — from canonical state, `chain-*.json` `last_state` leaves
   blocked and the same `failure_fingerprint` does not recur. A PID, commit,
   self-report, or heartbeat is NOT proof.

The goal also carries the no-op guard (stand down when nothing is actually
blocked/failed) and the coordination guard (stand down when another fixer
already owns the occurrence), so a babysitter that finds nothing to do ends
cleanly instead of inventing work.
