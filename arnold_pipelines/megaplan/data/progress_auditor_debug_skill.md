---
name: progress-auditor-debug
description: Interpret a Hetzner 6-hour progress-auditor report, decide what it surfaced correctly, find inefficiencies or weirdness it missed, and turn every miss into a deterministic gather reason plus regression test. Use with $megaplan-cloud when audit findings repeat as PASSIVE/STALE/INEFFICIENT, green checks hide repair churn, or the auditor seems blind to stale repair-data, meta-repair launch failures, wrapper drift, PR merge drift, or deterministic failure loops.
---

# progress-auditor-debug

A playbook for debugging the auditor that judges the repair system.

## The philosophy

The 6-hour progress auditor is not one thing. It is a **gather-then-judge
pipeline**:

1. `arnold-progress-auditor` deterministically discovers sessions and gathers
   evidence into report JSON.
2. It adds a `reasons[]` list for plans that look suspicious.
3. Only plans with reasons are dispatched to Codex/DeepSeek for judgement.
4. Plans with no reasons become `green_checks`.

That means the gather step is the ceiling on what the model can see. If the
bad fact is not in the evidence JSON, Codex cannot reliably notice it. If the
session never gets a reason, Codex never sees it at all.

So the reframe is strict:

> Never ask "why did the auditor miss this?" first. Ask "what deterministic
> gather signal should have made this impossible to miss?"

Your job is not to hand-fix the audited chain. Your job is to understand whether
the audit finding is live, stale, noisy, or incomplete; then fix the auditor's
evidence contract when the miss is structural. A prompt-only fix is acceptable
only when the bad fact was already explicit in the evidence JSON and the model
still drew the wrong conclusion.

## The cast

On the Hetzner box (`ssh root@159.69.51.216`, `docker exec megaplan-cloud-agent`):

| Layer | Who | Evidence |
| --- | --- | --- |
| status | `megaplan cloud status --all` | operator classification, should-run, tmux/process liveness |
| detect | `arnold-watchdog` | `/workspace/watchdog-report.json`, `/workspace/watchdog-reports/*.json`, `/workspace/watchdog.log` |
| L1 | repair loop | `/workspace/.megaplan/cloud-sessions/repair-data/*.repair-data.json`, attempts, repair progress |
| L2 | meta-repair | `/workspace/.megaplan/cloud-sessions/repair-data/meta/*.json`, `/workspace/.megaplan/meta-runs/*` |
| L3 | progress auditor | `/workspace/audit-reports/*-audit.{json,md}`, `/workspace/audit-report.log` |
| truth | chain and plan state | `<workspace>/.megaplan/plans/.chains/*.json`, plan `state.json`, `events.ndjson`, chain log |
| outside | external state | PR state, CI/build state, git state, installed wrapper mtimes |

Use the `$megaplan-cloud` skill for the box. Start with a real cloud YAML, for
example:

```bash
ssh root@159.69.51.216 \
  'docker exec megaplan-cloud-agent bash -lc "
    cd /workspace/superfixer-repair-custody/Arnold &&
    python -m arnold_pipelines.megaplan cloud status --all \
      --cloud-yaml cloud.tiered-repair-hardening.yaml
  "'
```

If that checkout is not present, find another real spec:

```bash
ssh root@159.69.51.216 \
  'docker exec megaplan-cloud-agent bash -lc "
    find /workspace -maxdepth 5 \( -name cloud.yaml -o -name \"cloud.*.yaml\" \) 2>/dev/null
  "'
```

## Quick triage

When an audit report feels wrong, do this before theorizing:

1. Read the newest `/workspace/audit-reports/<ts>-audit.json` and `.md`.
2. Read `/workspace/audit-report.log` to see report counts over time. Repeated
   findings across cycles are often the signal.
3. For each suspicious finding, record: `session`, `plan`, `reasons[]`,
   `deepseek_response` or `hypothesis`, `chain_state_summary.current`,
   `repair_data_summary`, `meta_repair_summary`, `stale_state_evidence`, and
   `source_refs`.
4. Deduplicate findings by `(session, reasons[])`. Fifteen plan findings with
   the same chain-log repeat are usually one underlying issue.
5. Cross-check watchdog status against chain truth. `watchdog-report.json`
   saying `awaiting_pr_merge` while chain-health says `pr_state=merged` and
   `chain_complete=true` is watchdog drift, not a live PR blocker.
6. Cross-check repair-data against chain truth. `repair-data` saying
   `outcome=running` after chain `last_state=done` is stale repair custody.
7. Cross-check meta records against run logs. A meta record with no verdict,
   no changes, no tests, and stderr like `Not inside a trusted directory` means
   meta-repair never really ran.
8. Inspect `green_checks`. A green check on a session with recent repair churn,
   stale repair-data, or repeated watchdog dispatch is a gather miss.
9. Decide whether the miss is:
   - **prompt miss**: evidence was explicit, model judged poorly;
   - **gather miss**: evidence was absent or no reason fired;
   - **custody miss**: evidence sources disagree and the auditor hid the disagreement.

## How to read an audit finding

Treat the Markdown report as an index, not proof. The JSON is the useful object.

Important fields:

- `reasons[]`: the deterministic signal that got this plan into `findings`.
- `stage_metrics`: top-level gather block keyed by the 14 lifecycle stages
  (`prep`, `plan`, `critique`, `gate`, `revise`, `finalize`, `execute`,
  `review`, `feedback`, `chain`, `repair`, `meta_repair`, `human_pr_ci`,
  `deployment_runtime`). Each stage always includes the same counters
  (`stalls`, `retries`, `repair_attempts`, `meta_repair_attempts`,
  `human_waits`, `ci_waits`, `handoff_gaps`, `no_op_loops`, `dead_workers`,
  `duration_seconds`, `unknowns`, `missing_evidence`) plus matching
  `*_evidence` arrays. Unmapped phases are never guessed; they land in
  `unknown_phase_count` and `unknown_phase_evidence`.
- `coverage`: deterministic summary of which stages have data (nonzero counters),
  which are all-zero, and which are `not_checked` (bucket missing). Helps operators
  quickly spot blind spots in the audit.
- `data_quality`: visibility into unknown phases, missing evidence, and data-source
  availability. Surfaces `not_checked` stages and warns when `stage_metrics` itself
  is absent from the report payload.
- `dispatch_summary`: always-present confirmation that this audit ran in report-only
  mode — no repair, model dispatch, meta-repair, git commit, or file edit occurred.
  Exists so operators and downstream tooling never need to guess whether the auditor
  took agentic action.
- `chain_state_summary.current`: the current chain state. This usually beats
  plan-local failure state.
- `active_step_stage`: conservative stage mapping derived from
  `active_step_phase`. Useful when the plan state has a recognizable phase name
  but no event-derived phase accounting yet.
- `active_event_phase`, `active_event_phase_stage`, `active_event_phase_kind`,
  `active_event_phase_ts`: recent event telemetry from `events.ndjson`. Treat
  these as the operator-facing live phase when `current_state=initialized` or
  another coarse lifecycle token hides active work.
- `chain_log.repetition_summary`: repeated stop/blocked signatures with line
  ranges.
- `stale_state_evidence`: whether the failure predates later success.
- `repair_data_summary`: repair outcome, iteration count, repeated signatures,
  and repair-data path.
- `meta_repair_summary`: whether meta-repair should dispatch, whether records
  or run logs exist, and whether they are launch failures.
- `source_refs`: paths to follow before trusting the model's prose.
- `green_checks`: sessions inspected and treated as non-suspicious. This is
  where missed issues hide.
- `root_cause_patterns`: cross-report aggregate hints. Helpful, but not a
  substitute for session-local ground truth.

Verdicts mean different things:

| Verdict | Meaning | What to verify |
| --- | --- | --- |
| `FIXED <sha>` | auditor claims it patched Arnold repair tooling | commit exists on `editible-install`, wrapper is installed, focused test passed, next cycle no longer repeats the same reason |
| `STALE` | evidence is historical or superseded | chain state/log shows later success; plan-local `latest_failure` is older than success |
| `INEFFICIENT` | progress exists but repair/watchdog/audit wasted cycles | repeated dispatch, stale repair-data, no-output meta runs, no circuit breaker |
| `PASSIVE` | no action recommended | prove this is not a completed-session shadow or green-masked churn |
| `ESCALATE` | human or operator action needed | unresolved `user_actions.md`, PR/CI/build state, or truly risky source fix |

## Recurring auditor failure shapes

Name the shape before fixing. It tells you whether to patch gather, prompt, or
the underlying repair system.

- **Completed-session drag.** A chain is `done`, watchdog says `complete`, but
  old plan directories keep producing findings because their chain log has
  historical `status_stopped` repeats. Fix by adding suppression or cleanup
  signals keyed to authoritative chain completion.
- **Repair-data ghost running.** `repair-data/index.json` or
  `<session>.repair-data.json` says `outcome=running`, but there is no
  `current_attempt_id`, no iterations, and watchdog/chain state says complete.
  This is stale custody, not live repair.
- **Artifact-exists-but-empty.** A repair or meta-repair record exists, but it
  contains no verdict, no diagnosis, no changes, no tests, or only launch
  failure text. Treat the artifact as negative evidence.
- **Meta-repair launch abortion.** Meta records say `Codex meta-repair
  orchestrator returned no output`; run stderr says `Not inside a trusted
  directory`, `--skip-git-repo-check`, missing CLI, timeout, or input too large.
  This is infrastructure broken before diagnosis, not a failed diagnosis.
- **Cross-session pollution.** A trigger such as `partial_liveness_recurrence`
  or a chain-log repeat was computed from the wrong session's artifacts. Prove
  it by matching session ids in repair-data, sidecar events, and meta records.
- **Plan-shadow vs chain truth.** A plan `state.json` says `blocked`, but the
  chain has already replaced it, advanced, or completed. Chain truth wins.
- **Green hides churn.** The report lists a session in `green_checks` even
  though repair iterations, repeated dispatches, or chain-health no-advance
  counters moved recently. Add a churn score or explicit reason.
- **Signature loop without circuit breaker.** Same exception, same phase, same
  command, same failure class repeats 3+ times with no new evidence. The
  auditor should flag deterministic failure exhaustion, not let repair spend
  budget forever.
- **Watchdog status drift.** Watchdog says `awaiting_pr_merge`, `blocked`, or
  `repair_dispatched`, but chain-health or external PR state says merged,
  complete, or otherwise resolved.
- **Installed-wrapper drift.** Auditor reports `FIXED <sha>`, but
  `/usr/local/bin/arnold-progress-auditor` or `/usr/local/bin/arnold-watchdog`
  is older than `/workspace/arnold/arnold_pipelines/.../wrappers/<name>`.
  Editable-install sync alone does not prove the running wrapper changed.
- **Source checkout residue.** Watchdog reports `sync_dirty`; `/workspace/arnold`
  has local repair patches that may duplicate upstream commits or block clean
  sync. Inspect diff before trusting any new fix.
- **Human-action blind spot.** The auditor only reasons about unresolved actions
  in some states. A stopped/stalled chain can still have unresolved or resolved
  but unconsumed `user_actions.md` / `user_action_resolutions.json`.

## Deterministic gather reasons to expect

As of this playbook, the gather code explicitly reasons about:

- many `plan_v*.md` refreshes;
- repeated ITERATE or blocked gates;
- score regression;
- high active step attempt count;
- `latest_failure_kind` in `stalled`, `phase_failed`, `execution_blocked`;
- stale latest failure after later success;
- stale block replay;
- between-milestone cycling;
- chain `last_state` in `awaiting_human`, `pr_closed`, `missing_base_ref`, `blocked`;
- chain-log repeated signatures;
- repair-data iteration count;
- repeated repair failure signatures;
- missing meta-run evidence;
- failed meta-run launch/no-output evidence;
- unresolved user actions in plan mode or `awaiting_human`.

If your issue is not represented here, the fix is probably gather code plus a
test, not prose.

## Report-only safety contract

Gather/report changes are allowed to add evidence, accounting blocks, and new
`reasons[]`, but they do **not** silently change repair dispatch policy.

- `stage_metrics` is accounting for operators and downstream dashboards, not a
  hidden dispatch gate.
- Conservative mapping is mandatory: unknown or missing evidence stays visible
  as `unknown*` / `missing_evidence*`, never inferred from prose.
- When the auditor runs with autofix disabled, the brief must stay report-only:
  no file edits, no patches, no commits, and no changes to the audited
  workspace.
- If you add a new deterministic signal such as repair-data ghost-running or
  watchdog/chain disagreement, document it as a report reason first. Expanding
  dispatch behavior is a separate change and needs its own tests and operator
  review.

## Signals the gather should surface

Use these as candidate rules when L3 misses a class:

- `repair_data_ghost_running`: repair outcome `running`, no active attempt,
  no iterations, chain/watchdog terminal.
- `repair_index_watchdog_disagreement`: repair index says running, watchdog
  says complete.
- `watchdog_chain_health_disagreement`: watchdog status contradicts
  `<session>.chain-health*.json`, for example PR already merged.
- `completed_session_reaudited`: chain terminal and plan/events stale, but old
  plan still appears in findings.
- `green_with_recent_repair_churn`: green check with repair iterations,
  repair events, dispatches, or no-advance counters in the window.
- `meta_record_no_verdict`: meta record exists but lacks `FIXED`, `NO_FIX`,
  `ESCALATE`, diagnosis, changes, tests, or ordinary-repair retrigger.
- `meta_repair_launch_failure`: meta stderr contains trust-dir, missing CLI,
  timeout, input-size, or empty response failure.
- `fixed_but_not_installed`: source wrapper newer than `/usr/local/bin` wrapper.
- `deterministic_failure_exhaustion`: same failure signature repeats 3+ times
  with no new approach or circuit breaker.
- `human_action_resolution_drift`: actions resolved on disk but executor or
  watchdog still reports a human block.
- `token_drift`: watchdog status token and repair-data/current-target token do
  not name the same state.

## Run it as a swarm

This work is fan-out-shaped. Keep the main thread for synthesis; dispatch
DeepSeek subagents with `fan.py` and terminal access, but make every brief
read-only unless you are in the fix phase.

Point every investigation brief at `$megaplan-cloud`, then at these paths:

- `/workspace/audit-reports/*-audit.json`
- `/workspace/audit-report.log`
- `/workspace/watchdog-report.json`
- `/workspace/watchdog-reports/*.json`
- `/workspace/.megaplan/cloud-sessions/*.json`
- `/workspace/.megaplan/cloud-sessions/*.chain-health*.json`
- `/workspace/.megaplan/cloud-sessions/repair-data/**`
- `/workspace/.megaplan/meta-runs/**`
- `<workspace>/.megaplan/plans/.chains/*.json`
- `<workspace>/.megaplan/plans/<plan>/state.json`
- `<workspace>/.megaplan/plans/<plan>/events.ndjson`
- `<workspace>/.megaplan/cloud-chain-<session>.log`
- `/workspace/arnold` git status and wrapper mtimes

Useful swarm lanes:

- **Current status and custody:** run cloud status, read watchdog report, report
  contradictions between status, chain-health, marker, repair-data, and chain
  state.
- **Latest audit reports:** classify recent findings by verdict, reason, and
  repeated session; identify which fields actually helped diagnosis.
- **Missed weirdness:** search for stale repair-data, green-with-churn, no-output
  meta runs, installed-wrapper drift, and deterministic loops not surfaced as
  findings.
- **Repair/meta evidence:** decide which repair and meta records are trustworthy
  and which are negative evidence.
- **Implementation versus cloud:** compare `arnold-progress-auditor` gather
  reasons and tests against real cloud artifacts.
- **Skill shape or fix plan:** synthesize the missing gather rules and propose
  the regression tests.

Require each subagent to return concrete remote paths and the one-sentence
operator consequence. Discard long narratives.

## Turn a miss into a fix

When L3 misses something, ask two questions in order:

1. **Was the bad fact explicit in the evidence JSON?**
   - If yes, tighten the prompt or verdict policy.
   - If no, patch the gather program.
2. **Would a deterministic reason have caused this session to enter `findings`
   instead of `green_checks`, or given Codex the missing fact?**
   - If yes, implement that reason and test it.
   - If no, the issue is probably outside the auditor's remit; write an operator
     ticket instead.

The normal fix path:

1. Add the deterministic signal to the gather block in
   `arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor`.
2. Include the signal in `reasons[]` and the relevant structured fields in the
   finding JSON.
3. Add a focused regression in `tests/cloud/test_progress_auditor.py` using the
   exact missed artifact shape.
4. Run `bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor`
   and `pytest tests/cloud/test_progress_auditor.py`.
5. Deploy to the box: sync `/workspace/arnold`, copy the wrapper to
   `/usr/local/bin/arnold-progress-auditor`, `chmod +x`, and restart or wait for
   the timer as appropriate.
6. Replay or synthesize the missed artifact set and prove the new reason appears.

A prompt-only change is not done unless the existing input already made the bad
fact impossible to miss.

## Close the loop

Before declaring the auditor fixed, answer these:

1. Did the original missed class now produce a deterministic `reasons[]` entry?
2. Did the regression test fail before the change and pass after it?
3. Did the fix reach the running wrapper, not just `/workspace/arnold`?
4. Did the next or replayed audit stop repeating the same stale finding?
5. Did any sibling artifact contract need the same treatment in watchdog,
   repair-loop, meta-repair, or status rendering?

Not done until the auditor would catch the same class next time without relying
on luck, stale prose, or a model guessing from weak hints.

## Anti-patterns

- Treating `PASSIVE` as proof. It is only a model verdict over the gathered
  evidence.
- Treating `green_checks` as proof. It may mean the gather did not know what to
  look for.
- Counting a meta record as success without reading the run log and verdict.
- Trusting `repair-data outcome=running` without active attempt evidence.
- Reopening completed sessions because old plan-local failures still exist.
- Fixing a chain workspace when the failure is stale repair custody.
- Shipping a `FIXED <sha>` without verifying `/usr/local/bin` wrapper freshness.
- Adding prompt instructions for a fact the gather never surfaces.
- Sampling one audit report and missing that the same reason has recurred for
  several cycles.
