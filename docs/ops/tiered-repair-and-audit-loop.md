# Tiered Repair And Audit Loop

This note defines the target operating model for keeping long-running Megaplan
epic chains alive on the cloud machine. The core change is to stop treating the
hourly check as the first line of defense. Repairs should start as soon as a
failure is observed, and the slower loops should mostly supervise the repair
system itself.

## Goal

Every chain failure should converge to one of three outcomes without a human
polling the box:

- the correct current chain/plan is repaired and running again;
- the system proves the blocker genuinely needs human input and messages the
  user with the exact decision needed;
- the repair system fails, and a higher-level repair agent diagnoses and fixes
  the repair system rather than repeatedly poking the same broken epic.

Success is not "an agent was launched". Success is:

> The current live chain and plan were identified, the blocker was classified,
> a repair action was taken, and live state proves the chain is running again,
> advanced, or is genuinely waiting on a human.

## Precedence Order

### 1. Failure-Triggered Repair

Run repair immediately when a known bad state appears. This should use the same
core repair entrypoint as the hourly check, but without waiting for the next
hourly tick.

Trigger examples:

- worker process exits while the chain expects an active worker;
- plan enters `awaiting_human_verify`;
- chain state expects a current plan but no live worker exists;
- launch command exits before producing a worker;
- state files are missing, invalid, or inconsistent;
- stale repair markers disagree with the current plan;
- no-advance detection fires outside an active long-running worker step.

The failure-triggered repair should be narrow and current-state anchored. It
must resolve the active plan, active chain state, current worker, and relevant
sidecars before acting. It should not repair stale parent plans or superseded
sessions just because old markers remain on disk.

### 2. One-Hour Repair Loop

The one-hour loop remains the durable fixer of record. It should run even if
event-triggered repair exists, because event hooks can be missed and state can
drift between events.

The one-hour loop should:

- inspect every visible cloud chain/session;
- identify the current child plan rather than stale parent or previous-plan
  state;
- classify the blocker;
- resolve mechanical clarification gates when policy allows;
- relaunch or retry the correct worker;
- verify the relaunch produced a live worker or moved plan state forward;
- message Discord only for true human decisions;
- record what it saw, what it did, and what proof shows the result.

The one-hour repair agent gets a bounded 60-minute execution window. Inside that
window, its job is not merely to launch something. It must get the chain into a
verified live/progressing state, or produce a precise failure record explaining
why it could not.

### 3. Meta-Repair Escalation

If the one-hour repair agent cannot launch, cannot inspect state, times out, or
does not repair the chain within its 60-minute budget, escalate to a higher-level
meta-repair agent.

The meta-repair agent's job is to fix the repair system, not to hand-fix the
epic as a one-off.

It should:

- diagnose why the one-hour repair failed;
- run as a properly equipped Codex repair orchestrator when the failure needs
  source-level reasoning, with `danger-full-access` if it must launch nested
  DeepSeek/Hermes subagents;
- delegate broad file mapping, root-cause probes, independent reviews, and
  bounded fix investigations to DeepSeek subagents wherever practical, so the
  Codex orchestrator keeps its context focused on synthesis and decisions;
- inspect prompts, wrapper code, marker handling, stale state detection, launch
  commands, environment, model/tool availability, and Discord escalation paths;
- patch the repair tooling or prompts when the failure is systematic;
- manually retrigger the one-hour repair loop after each fix;
- verify that the one-hour repair loop itself successfully finds the problem and
  relaunches or advances the chain;
- repeat within a 90-minute budget until the repair loop succeeds or the
  remaining blocker is proven to require a human.

This layer exists to make the one-hour loop robust. If a meta-repair agent fixes
the epic directly but leaves the hourly repair loop blind, that is a failed
meta-repair.

### 4. Six-Hour Root-Cause Auditor

The six-hour loop is broader than observation, but it is not the emergency
responder. It should study the last window of activity, understand why failures
happened, and improve the system when the fix is obvious and safe.

The six-hour auditor should:

- deploy subagents to inspect failures independently when the history is complex;
- use subagents to fix obvious, bounded tooling defects;
- dig into root causes rather than stopping at the immediate symptom;
- decide whether failures were epic-specific, repair-loop-specific,
  environment-specific, prompt-specific, state-model-specific, or policy-ordering
  problems;
- compare new failures against previous issues, tickets, audit reports,
  watchdog reports, and known repair-loop bugs;
- identify repeated patterns, such as stale parent state, superseded sessions,
  sidecar drift, model fallback mistakes, missing secrets, Discord delivery
  failures, or repair agents that launch but do not verify;
- commit and deploy narrow fixes when the issue is clear and tests can cover it;
- log deeper unresolved issues for follow-up when the fix is not obvious or too
  risky for an autonomous audit pass.

The six-hour loop should produce a useful audit artifact even when everything is
green. The artifact should say what it checked, which repair actions happened in
the window, whether those actions worked, what patterns are emerging, and which
older issues this resembles.

## Failure Handling Contract

Each repair attempt should leave enough structured evidence for the next layer:

- chain/session id;
- workspace path;
- current chain state file;
- current plan name;
- current plan state;
- active phase and worker pid, if any;
- latest failure or clarification gate;
- marker and sidecar files considered;
- repair action attempted;
- launch command used;
- verification command/result;
- whether Discord escalation was sent;
- whether the issue appears new, repeated, or related to a known prior issue.

Without this evidence, the meta-repair and six-hour audit loops will be forced
to reconstruct too much context and will drift toward symptom-chasing.

## Policy Ordering

When multiple signals conflict, prefer this ordering:

1. Current live child chain state.
2. Current active plan state.
3. Live worker/process evidence.
4. Fresh chain events.
5. Current repair markers matching the current plan.
6. Older parent-chain markers.
7. Historical repair-progress sidecars.

Older markers can inform diagnosis, but they should not override current child
chain state. A superseded parent session with a live child worker is not a
reason to relaunch the parent.

## Applying This To The Native Python Failure

The native Python chain exposed the exact failure mode this design is meant to
prevent:

- the live M3 plan paused at `awaiting_human_verify`;
- the repair layer was looking at stale parent/M1 repair state;
- the chain was not advanced because the repair system did not anchor itself to
  the live current plan;
- Discord did not answer because the resident bot lacked a live model
  credential path;
- the watchdog needed patches to ignore stale sidecars, skip superseded parents,
  and avoid no-advance false positives during active long-running worker steps.

Under this design:

- the M3 clarification gate would trigger immediate repair;
- the one-hour repair would answer policy-allowed mechanical questions, resume
  clarification, and verify a live worker;
- if the one-hour repair inspected stale M1 state, meta-repair would patch that
  bug and retrigger the one-hour repair until it succeeded;
- the six-hour auditor would connect the incident to prior stale-marker,
  parent/child-chain, Discord, and verification gaps, then either land bounded
  fixes or record a deeper systemic issue.

## Implementation Notes

This design implies these concrete implementation changes:

- expose a failure-event hook that calls the same repair entrypoint as the hourly
  loop;
- make the repair entrypoint self-verifying and current-plan anchored;
- give repair agents explicit 60-minute message/runtime budgets;
- add a meta-repair wrapper with a 90-minute budget, a hard requirement to
  retrigger and validate the one-hour repair loop, and explicit instructions for
  Codex to deploy DeepSeek subagents for as much mapping, diagnosis, and bounded
  repair work as possible;
- ensure Discord escalation is reserved for true human decisions and includes
  the exact question, current plan, and suggested default;
- make six-hour audit reports cross-reference prior tickets, reports, commits,
  and repair incidents;
- let the six-hour auditor dispatch subagents for deep diagnosis and obvious
  narrow fixes, while logging risky or ambiguous fixes for human review.
