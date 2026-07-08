---
superseded_by: custody-control-plane
---

# Megaplan Incident Control Plane Plan

Date: 2026-07-03

## Goal

Make autonomous megaplan recovery observable, self-healing, and easy for agents to operate.

The desired end state is that any agent can run one command against a session, plan, initiative, or incident and answer:

- what happened
- why it happened
- which actor noticed it
- what repair was attempted
- whether the repairer itself failed
- whether the repair-system fix was committed, installed, and retriggered
- whether the original work recovered
- whether this is a recurrence of a known problem
- where the underlying logs, sessions, commits, PRs, and watchdog records live

The core design is an append-only incident ledger plus a small agent-facing CLI. The ledger is the local/cloud source of truth. GitHub is a useful publication and review sink, but not the primary state store.

When local and cloud copies diverge, the active cloud workspace ledger wins for cloud-run incidents. Local copies are caches or development artifacts unless the incident explicitly says it is local-only. Derived indexes must be rebuildable from `events.jsonl`; if an index disagrees with the event log, agents should regenerate the index and record an integrity-repair event.

Core invariant: an incident is an event-sourced state machine. Actors never mutate incident state directly; they append events. Current state, active claims, problem indexes, human summaries, and GitHub updates are projections from the event stream.

## End State

Megaplan has a durable incident control plane made of:

- Append-only event log: `.megaplan/incident-ledger/events.jsonl`
- Derived problem index: `.megaplan/incident-ledger/problems.json`
- Derived incident index: `.megaplan/incident-ledger/incidents.json`
- Human summaries: `.megaplan/incident-ledger/summaries/*.md`
- CLI entrypoint: `incident ...` or an equivalent `megaplan incident ...`
- GitHub sync for important transitions and persistent issues
- Prompt instructions for watchdogs, immediate repairers, meta repairers, 6-hour auditors, chain runners, and subagents

Writes to `events.jsonl` must be append-only and atomic. The CLI/helper should acquire a short file lock before appending so concurrent watchdog, repairer, and auditor processes cannot interleave records.

The editable install branch should receive compact committed state and repair-system code changes. Raw huge transcripts and provider logs should remain referenced by path, hash, session id, or artifact id unless they are small and safe to commit.

## Agent UX

Agents should not need to know the filesystem layout by memory. They should use a small command vocabulary:

```bash
megaplan incident brief <session-or-incident>
megaplan incident list --active
megaplan incident claim <incident> --actor <actor> --expect <event-type>
megaplan incident dispatch <incident> --actor immediate_repair
megaplan incident dispatch <incident> --actor meta_repair --reason missed-deadline
megaplan incident dispatch <incident> --actor six_hour_auditor
megaplan incident start --session <id> --actor watchdog --type stalled_progress
megaplan incident event --incident <id> --actor immediate_repair --type repair_attempt --summary "..."
megaplan incident expect --incident <id> --next meta_repair.started --deadline-minutes 60
megaplan incident finish --incident <id> --outcome recovered --evidence <path-or-ref>
megaplan incident sync --push
```

The `brief` command is the load-bearing UX. It should return:

- current incident state
- next expected event and deadline
- missing evidence
- relevant watchdog reports
- immediate repair attempts
- meta-repair attempts
- 6-hour audit decisions
- running processes
- linked sessions and transcripts
- linked commits, branches, PRs, and install sync records
- stable problem ids and recurrence history
- concise recommendation for the next actor

Every fixer prompt should start by telling the agent to run or construct this incident brief before doing archaeology manually.

Agents that do not know which incident to work should run `megaplan incident list --active`. Before acting on a pending `next_expected_event`, an agent should write a claim event. `brief` must show active claims to prevent duplicate repairs. If the latest event has no `next_expected_event`, the incident is either recovered/closed or malformed; `brief` must say which.

The brief must not be only a bag of paths. It should validate evidence refs, flag broken or missing refs, and include a one-line summary for each important evidence item. If it lacks minimum evidence, it should say so explicitly and recommend a bounded discovery command such as `megaplan incident discover --session <id>`.

Claim lifecycle:

- `claim.created`: actor claims a specific expected transition.
- `claim.heartbeat`: long-running actor proves it is still active.
- `claim.released`: actor finishes or intentionally hands off.
- `claim.expired`: claim TTL passed without heartbeat or completion.
- `claim.overridden`: another actor takes over with evidence of missed deadline, dead process, or stale claim.

Claims should include claimant id, expected transition, timestamp, TTL, and optional process id. Expired claims should not block work, but `brief` must warn about them.

Actor prompt envelope:

- incident id and current incident brief
- current expected transition and deadline
- actor role and allowed scope
- timebox and claim TTL
- minimum evidence to read and produce
- allowed writes and forbidden actions
- required final event
- verification signal for success
- stop condition and handoff target

Subagents receive a frozen brief. By default they cannot mutate the ledger or commit code; the caller records `subagent.completed` with the output as evidence. A subagent may commit or append events only when its prompt explicitly grants that authority.

`finish` is a convenience wrapper. It must emit canonical close or handoff events; it must not create a separate hidden state outside the ledger.

## Actor Quickstart

| Actor | First command | Claim? | Timebox | Allowed writes | Required final event | Next verifier |
| --- | --- | --- | --- | --- | --- | --- |
| Watchdog | `megaplan incident start` or `brief` | No | short detection pass | detection, expectation, process evidence | `watchdog.detection` | immediate repairer or chain runner |
| Chain runner | `megaplan incident list --active` | When dispatching | until expected deadline | lifecycle, dispatch, stale-state findings | dispatch or handoff event | dispatched actor |
| Immediate repairer | `megaplan incident brief <id>` | Yes | 15 min / 2 attempts without new evidence | repair attempt, verification, failure | `immediate_repair.verified_recovered` or `immediate_repair.repair_failed` | watchdog or meta repairer |
| Meta repairer | `megaplan incident brief <id>` | Yes | bounded by prompt | repair-system diagnosis, source fix, install handoff, retrigger | `meta_repair.repair_retriggered`, `verified_recovered`, or `meta_repair_failed` | immediate repairer or auditor |
| Install sync | `megaplan incident brief <id>` | Yes | 15 min default | install sync result and runtime evidence | `install_sync.install_sync_applied` or failure | meta repairer |
| 6-hour auditor | `megaplan incident brief <id>` | Yes | audit cycle | findings, problem updates, dispatches, summary sync | `six_hour_auditor.audit_complete` | next expected actor |
| GitHub sync | `megaplan incident brief <id>` | Usually no | short sync pass | redacted publication refs | `github_sync.github_sync` | brief projection |
| Human | `megaplan incident event --actor human` | Optional | none | manual observation or decision | explicit event/handoff | relevant actor |

## Event Model

Each event is one JSON object on one line.

Required fields:

- `schema_version`: event schema version, starting at `1`
- `event_id`: stable unique id
- `ts`: ISO timestamp
- `actor`: `watchdog`, `chain_runner`, `immediate_repair`, `meta_repair`, `six_hour_auditor`, `subagent`, `install_sync`, `github_sync`, `human`, or `system`
- `incident_id`: nullable when creating or discovering
- `session_id`: cloud/local session id when available
- `initiative`: initiative name when available
- `plan`: plan or milestone id when available
- `type`: typed transition
- `scope`: `project_code`, `repair_system`, `run_state`, `infrastructure`, `documentation`, or `unknown`
- `summary`: short human-readable text
- `evidence`: list of refs to logs, sessions, commits, PRs, files, command output, or artifacts
- `outcome`: `started`, `succeeded`, `failed`, `timed_out`, `verified`, `recovered`, `escalated`, or `unknown`
- `next_expected_event`: nullable typed transition
- `deadline_ts`: nullable timestamp
- `problem_id`: stable id when mapped to a known recurring problem
- `parent_event_ids`: causal parents that this event builds on
- `trigger_event_id`: event that caused this actor to run, when applicable
- `supersedes_event_id`: event corrected or superseded by this event, when applicable
- `attempt_id`: stable id for one immediate/meta repair attempt cycle, when applicable
- `links`: structured refs to sessions, plans, incidents, problems, attempts, commits, GitHub artifacts, install targets, and raw logs

Events are immutable. Corrections, redactions, and revised diagnoses are represented by new events that refer to the earlier event id. Agents must not edit or delete previous records except through an explicit redaction/integrity repair command that preserves an audit trail.

Human-facing expected transitions should use `<actor>.<type>` format, for example `immediate_repair.repair_attempt`. JSON stores `actor` and `type` separately but may also include the formatted transition as a convenience.

Repair and diagnosis events should include a compact `decision` object:

- `question`
- `trigger_signal`
- `evidence_read`
- `reasoning_summary`
- `selected_action`
- `alternatives_considered`
- `rejected_reason`
- `confidence`
- `assumptions`

Action events should include structured `actions` when commands or patches are used:

- `kind`
- `command` or patch ref
- `cwd`
- `env_redacted`
- `exit_code`
- `duration_ms`
- `output_ref`
- `outcome`

New repair attempts must cite new evidence, changed code, changed state, or a changed hypothesis. Otherwise they are duplicate retries and should become a repair-system finding.

Evidence refs should prefer structured objects:

```json
{
  "kind": "agent_session",
  "path": "/workspace/.megaplan/sessions/...",
  "session_id": "...",
  "actor": "immediate_repair",
  "source_system": "codex",
  "captured_by": "immediate_repair",
  "captured_at": "2026-07-03T00:00:00Z",
  "sha256": "...",
  "byte_count": 12345,
  "redacted": true,
  "redaction_policy": "incident-ledger-v1",
  "availability": "local_path"
}
```

Other evidence kinds include `watchdog_report`, `repair_record`, `meta_repair_record`, `process_snapshot`, `git_commit`, `github_pr`, `github_issue`, `workflow_run`, `terminal_log`, `file_snapshot`, `diff`, and `artifact`.

Identity domains should not be collapsed into one string. Use `links` for distinct ids such as `provider_session_id`, `agent_run_id`, `terminal_session_id`, `chain_run_id`, `workspace_id`, Git commit SHA, GitHub PR/comment/workflow ids, install target id, and raw log path/hash.

If `brief` detects missing refs, schema failures, or index divergence, it should emit or recommend `system.integrity_repair`. Broken provenance should become queryable evidence, not only console text.

Minimum evidence expectations:

- `watchdog.detection`: watchdog report, report age, live process snapshot, and relevant terminal/log tail.
- `immediate_repair.repair_attempt`: diagnosis summary, attempted command or patch, result, and verification signal.
- `immediate_repair.repair_failed`: diagnosis summary, attempted commands with outcomes, blocking reason, and scope classification.
- `meta_repair.source_fix_committed`: commit SHA, branch, files changed, pushed status, and intended install target.
- `install_sync.install_sync_applied`: source commit SHA, target runtime id/path, sync command or mechanism, freshness timestamp, and runtime verification command.
- `verification` / `verified_recovered`: original failure condition, check command or signal, observed result, and whether the incident recurred after the fix.

## Event Types

Core event types:

- `detection`
- `diagnosis`
- `repair_attempt`
- `repair_failed`
- `meta_repair_started`
- `source_fix_committed`
- `install_sync_applied`
- `relaunch`
- `repair_retriggered`
- `verification`
- `verified_recovered`
- `meta_repair_failed`
- `persistent_issue`
- `human_escalation`
- `github_sync`
- `audit_complete`
- `secret_leak`
- `subagent_completed`
- `integrity_repair`

Repairers should distinguish:

- fixing the project under work
- fixing stale or contradictory run state
- fixing the repair machinery
- fixing infrastructure or credentials
- documenting a durable issue that needs a planned change

This distinction lives in `scope`.

Scope decision rules:

- Use `repair_system` for watchdog, immediate-repairer, meta-repairer, auditor, prompt, wrapper, routing, or tool-invocation defects.
- Use `project_code` for defects in the repository or product being built.
- Use `run_state` for stale, contradictory, or missing plan/chain/session state where the underlying code is not wrong.
- Use `infrastructure` for credentials, quota, provider, disk, network, GitHub, cloud host, or runtime-install failures.
- Use `documentation` for durable instructions, runbooks, or prompt context that are missing or misleading.

If multiple scopes apply, record the proximate failing scope and include secondary scopes in evidence. Repair-system failures should not be hidden as project-code failures.

## Trigger State Machine

Recovery should be driven by expected transitions, not by ad hoc retry loops.

Normal path:

1. `watchdog.detection`
2. `immediate_repair.repair_attempt`
3. `immediate_repair.verification`
4. `immediate_repair.verified_recovered`

If immediate repair fails or times out:

1. `immediate_repair.repair_failed`
2. `meta_repair.meta_repair_started`
3. `meta_repair.diagnosis`
4. `meta_repair.source_fix_committed` when the repairer itself needs a code or prompt fix
5. `install_sync.install_sync_applied`
6. `meta_repair.repair_retriggered` or `immediate_repair.repair_attempt`
7. `meta_repair.verification`
8. `immediate_repair.verified_recovered`

The default immediate-repair timebox is 15 minutes or two attempts without new evidence, whichever comes first. A watchdog or chain runner should dispatch meta repair when the deadline expires or the immediate repairer records `repair_failed`. The immediate/meta loop may retry only when a new event adds new evidence, code, prompt, install, or state information; repeating the same action is a repair-system failure.

If the incident is still unresolved at the 6-hour check:

1. `six_hour_auditor.diagnosis`
2. Audit broken expectations and stale records.
3. Audit project progress since the last check.
4. Audit immediate repairer behavior.
5. Audit meta-repair behavior.
6. Audit whether repair-system fixes were committed, installed, and retriggered.
7. Dispatch subagents for root-cause analysis and repair-system fixes when useful.
8. Write or update persistent `problem_id` records for recurring or unresolved issues.
9. Commit/sync compact ledger and summary updates.
10. Emit `six_hour_auditor.audit_complete` with outcome `recovered`, `escalated`, or `audit_cycle_complete`, and set the next expected event.

There should not be an unbounded retry count as the primary control. Time-bounded recovery should learn from each attempt by appending new evidence and comparing it with the previous attempts. Repeating the same repair without new evidence is itself a repair-system failure.

The 6-hour check is scheduled by setting `next_expected_event: six_hour_auditor.diagnosis` with `deadline_ts` at incident creation plus six hours. If an incident recovers before then, the expectation is cleared. If the auditor runs and the incident is still not resolved, it should either set a new six-hour deadline, hand off to immediate/meta repair with a concrete expected event, or record `human_escalation`.

## Actor Responsibilities

### Watchdog

- Detect stalled, contradictory, stale, or failed run states.
- Create or update an incident.
- Record live process evidence and watchdog report age.
- Set the next expected event to `immediate_repair.repair_attempt`.

### Chain Runner

- Record plan, milestone, and chain lifecycle transitions that affect incident interpretation.
- Attach current chain state, active milestone, worktree path, branch, PR, and process id when available.
- Dispatch immediate repair, meta repair, or the 6-hour auditor when a pending expected event expires.
- Avoid marking a plan as healthy solely from stale state; compare persisted state with live process evidence.

### Immediate Repairer

- Read the incident brief.
- Fix the concrete project/run-state issue if possible.
- Record every diagnosis, attempted command, and outcome.
- Verify recovery with the same signal the watchdog uses.
- If it cannot fix the issue, record a structured failure and set the next expected event to `meta_repair.meta_repair_started`.

### Meta Repairer

- Treat the immediate repairer as the patient.
- Read the incident brief and immediate repair evidence.
- Determine whether the failure was missing context, weak prompt, bad code, stale install, tool failure, quota/routing, or an actual project blocker.
- If it fixes the repair system, commit the change, install/sync it to the active cloud runtime, retrigger the immediate repairer, and verify that the original incident recovers.
- Record both the repair-system outcome and the original incident outcome.
- If it cannot fix the repair system, emit `meta_repair_failed` with evidence and set the next expected event to `six_hour_auditor.diagnosis` or `human_escalation`.

### 6-Hour Auditor

- Read the incident ledger before reading raw logs.
- Identify broken expected transitions.
- Identify stale reports, stale watchdog conclusions, and stale chain state.
- Compare current live processes with persisted state.
- Audit what happened in the last 6 hours across project work, immediate repair, meta repair, install sync, GitHub sync, and subagents.
- Reconcile broken expectations first; direct fixes are optional bounded interventions and should be recorded as ordinary repair or meta-repair transitions.
- Dispatch subagents for broad independent diagnosis and repair-system patches.
- Log persistent problems with stable ids when a class of issue recurs or cannot be fully fixed immediately.
- Emit at least one structured finding for each audited layer: project progress, immediate repair, meta repair, install sync, GitHub sync, and live process state.
- Review active or recently completed meta repairs before independently changing the repair system, and record contradictory evidence before overriding them.

### Subagents

- Receive a self-contained incident brief and exact output shape.
- Return conclusions, ranked risks, or patches.
- Record their output as evidence and, when trusted for repair-system fixes, commit/push or hand back an apply-ready patch as instructed by the caller.

### Install Sync

- Apply committed repair-system fixes to the active runtime used by cloud watchdogs, repairers, and auditors.
- Record `install_sync_applied` with commit SHA, runtime path/id, sync command, timestamp, and verification command.
- If sync fails or the runtime remains stale, record failure and set the next expected event to `meta_repair.meta_repair_started`.

### GitHub Sync

- Publish important transitions, not noisy raw logs.
- Create or update issues/PR comments for persistent problems.
- Link commits, PRs, and CI results back into the ledger.
- Prefer batched updates from the ledger over treating GitHub comments as the canonical state.
- Run redaction and size checks before committing or pushing ledger-derived files.
- Publish summarized projections and attach returned issue/PR/comment refs as evidence. It should not introduce independent workflow authority.

### Human

- Humans may append manual observations or decisions through `megaplan incident event --actor human ...`.
- Human events should be short, evidence-linked, and should not bypass the expected-transition model unless they explicitly record why.

## Git And Branch Policy

The local/cloud ledger is canonical. The editable install branch should receive:

- repair-system source changes
- prompt/wrapper changes
- compact incident indexes
- human-readable summaries
- stable persistent-problem records

Avoid committing:

- huge raw transcripts
- secrets
- provider payloads with sensitive metadata
- duplicate copies of logs already retained elsewhere

For each repair-system source fix, the ledger must record:

- commit SHA
- branch
- whether it was pushed
- whether it was installed into the active runtime
- how it was verified
- whether the original incident recurred after the fix

For a repair-system fix to count as shipped, the ledger must contain the full chain:

1. `source_fix_committed`
2. `install_sync_applied`
3. `repair_retriggered` or equivalent `relaunch`
4. `verified_recovered`

`source_fix_committed` without install and retrigger evidence is not shipped. `install_sync_applied` without original-condition verification is not proven.

## Recurrence And Problem Index

`problems.json` is derived from events and should be regenerable. Each problem record should include:

- `problem_id`
- `title`
- `scope`
- `normalized_signature`
- `first_seen_ts`
- `last_seen_ts`
- `occurrence_count`
- `linked_incident_ids`
- `fix_commits`
- `recurred_after_fix`
- `status`: `open`, `mitigated`, `fixed`, or `wont_fix`
- `owner_actor`
- `next_review_ts`

Problem ids should be stable across runs. A reasonable first rule is a hash of `scope + normalized_signature`, where the signature removes timestamps, process ids, attempt numbers, and transient paths. If the same signature appears after a claimed fix, set `recurred_after_fix: true` and make the next repair/audit treat it as a higher-priority repair-system issue.

Mutable-looking problem fields such as `status`, `owner_actor`, and `next_review_ts` must also be derived from events, for example `problem_status_changed`, `problem_owner_assigned`, and `problem_review_scheduled`. `problems.json` is never manually edited as truth.

## Redaction And Size Rules

Committed summaries and GitHub sync output must be small and redacted.

Hard gates:

- Event summaries must be under 2 KB.
- Committed ledger-derived files should normally be under 50 KB each; larger data should be rotated or summarized.
- Raw command output, environment dumps, provider payloads, and full transcripts should be referenced, not pasted.
- Summaries must not contain API keys, tokens, authorization headers, environment variable values, or unredacted provider payloads.

The append helper, brief generator, commit path, and GitHub sync path should reject or redact obvious secrets, including lines containing `Authorization:`, `X-API-Key:`, `OPENAI_API_KEY=`, `AWS_SECRET`, `ghp_`, `AKIA`, or long high-entropy token-like strings. If a secret is committed, record a `secret_leak` incident, rotate the credential, rewrite/remove the leaked content where appropriate, and meta-repair the guard that missed it.

## Brief Query Requirements

`megaplan incident brief` should be able to query and display:

- timeline by causal chain, not only timestamp order
- active and expired claims
- attempts grouped by `attempt_id`
- attempts grouped by `problem_id`
- repair-system shipped status
- install freshness and target runtime identity
- unresolved expectations and deadlines
- missing or stale evidence refs
- recurrence after claimed fix
- GitHub publication status
- raw-log refs with hash, size, retention class, and redaction status
- original failure signal and latest verification signal

## Load-Bearing Questions And Answers

1. Source of truth?
   Append-only incident ledger on the machine/cloud workspace. GitHub is a sync target, not canonical state.

2. Who writes to it?
   Watchdog, chain runner, immediate repairer, meta repairer, 6-hour auditor, subagents, install sync, GitHub sync, and humans.

3. What does an event mean?
   A typed transition with actor, scope, outcome, evidence, and next expected event.

4. How does an agent know what should happen next?
   Read `next_expected_event` and `deadline_ts` from the incident brief.

5. How do we detect that a fixer failed?
   Missing, late, contradictory, or failed expected event.

6. How do we distinguish project fixes from repair-system fixes?
   Use `scope`: `project_code`, `repair_system`, `run_state`, `infrastructure`, or `documentation`.

7. How do we distinguish immediate repair, meta repair, and 6-hour audit?
   Use `actor` plus event type. The actor names the layer; the type names the transition.

8. How do agents avoid log archaeology?
   Start from `megaplan incident brief`, which indexes the relevant logs, sessions, processes, commits, PRs, and summaries.

9. How do we know a repair-system fix shipped?
   Require the full chain `source_fix_committed -> install_sync_applied -> repair_retriggered/relaunch -> verified_recovered`.

10. How do we know it worked?
    Require `verified_recovered` against the original failure condition, not only a successful command.

11. What happens when immediate repair fails?
    It records a structured failure, explains why, attaches evidence, and expects `meta_repair.meta_repair_started`. A watchdog or chain runner dispatches meta repair when failure is recorded or the immediate-repair deadline expires.

12. What does meta repair do?
    It diagnoses and fixes the repairer or its context, installs the fix, retriggers immediate repair, and verifies the original incident. If the repairer is not the problem, it records that boundary and hands off to the appropriate actor.

13. What does the 6-hour auditor do?
    It audits broken expectations, stale data, recurrence, inefficient loops, immediate repair, meta repair, install sync, GitHub sync, and live project progress, then emits a structured completion/handoff event.

14. How do recurring issues get tracked?
    Stable `problem_id`, normalized signature, occurrence count, first/last seen, linked incidents, fix SHAs, status, and recurred-after-fix markers.

15. How do humans inspect this?
    Read committed summaries and indexes, or follow GitHub comments/issues/PR links that mirror important transitions.

16. How do agents interact with it?
    Use `megaplan incident list --active`, `brief`, `claim`, `start`, `event`, `expect`, `finish`, and `sync`.

17. How do we avoid noisy GitHub spam?
    Store detailed events locally and batch important transitions to GitHub.

18. How do we avoid leaking secrets or bloating git?
    Commit refs, hashes, summaries, and redacted excerpts instead of huge raw logs.

19. How do we prevent symptom-only fixes?
    Require scope, recurrence history, original-condition verification, and explicit repair-system vs project-code classification.

20. What is the success condition?
    One command can explain the incident timeline, cause, repair attempts, repairer failures, source fixes, install status, verification, recurrence, and next action.

## Open Implementation Questions

- Should the CLI be a new `megaplan incident` namespace or a standalone `incident` command?
- Which existing wrapper should own the first ledger append helper?
- What is the minimum event schema that can be shipped without blocking current cloud runs?
- How much of `events.jsonl` should be committed versus rotated into summaries?
- Which records need redaction before GitHub sync?
- Should broken expected transitions automatically open a persistent problem issue after N recurrences?

## First Implementation Slice

1. Add the event append helper and schema validation.
2. Add `megaplan incident brief` over existing watchdog, repair, meta-repair, process, git, and session evidence.
3. Patch watchdog, immediate repairer, meta repairer, and 6-hour auditor prompts to start from the incident brief and append events.
4. Add `source_fix_committed -> install_sync_applied -> retriggered -> verified_recovered` enforcement for meta repairer fixes.
5. Add committed compact summaries and problem index sync to the editable install branch.
6. Add tests for missing meta-repair evidence, stale watchdog reports, stale running repairs, install sync freshness, and recurring problem ids.
