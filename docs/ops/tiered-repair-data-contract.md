# Tiered Repair Data Contract

## Executive Summary

The tiered repair system needs a shared evidence model, not more independent
sidecars. Each layer should be able to answer four questions without
reconstructing history from logs:

1. What is the current authoritative target?
2. What incident is being handled, and has this exact incident appeared before?
3. What action did a repair layer take?
4. What machine-checkable proof shows the target is complete, progressing, or
   genuinely waiting on a human?

The current implementation already records useful evidence in repair-data JSON,
repair-progress sidecars, watchdog reports, audit reports, plan state, chain
state, and event journals. The gaps are contract shape and ownership. The most
important changes are:

- centralize current-target resolution and record the resolver's decision in
  every artifact;
- split stable "current" files from immutable incident, attempt, escalation,
  meta-repair, and audit history;
- make verification evidence machine-checkable, with process liveness recorded
  only as partial proof;
- turn human escalation into a durable answer/resume ledger, not a deletable
  marker;
- require every repair actor to hold one shared session lock before mutating
  plan or chain state;
- redact failure context before it reaches prompts, Discord, reports, or
  persisted summaries.

Nested DeepSeek probes used for this design all completed successfully:

- DeepSeek Flash: existing persisted watchdog, repair, audit, escalation, plan,
  chain, and event data.
- DeepSeek Flash: stage-to-stage handoff data.
- DeepSeek Flash: retention, indexing, naming, and cross-reference strategy.
- DeepSeek Pro: adversarial critique.

This document is a data contract only. It does not require repair code changes
in this commit.

## Principles

### Current State Is Resolved, Not Guessed

Every stage must read a single current-target resolver output before acting. The
resolver enforces this precedence:

1. Current live child chain state.
2. Current active plan state.
3. Live worker or tmux/process evidence.
4. Fresh chain and plan events.
5. Current repair markers matching the current plan.
6. Older parent-chain markers.
7. Historical repair-progress sidecars.

Older artifacts are evidence, not authority. If an older parent marker conflicts
with a live child chain or current plan, stages must preserve the old artifact as
history but refuse to act on it.

### Current Files Are Mutable; Evidence Is Append-Only

Fast consumers need stable paths such as `<session>.repair-data.json` and
`watchdog-report.json`. Auditors and meta-repair need immutable proof. The
contract therefore keeps mutable current snapshots and adds immutable records
for incidents, attempts, escalation records, meta-repair runs, and audits.

Mutable files may be overwritten atomically. Append-only or immutable files may
only receive new records or resolution records. They must not be rewritten to
erase the original observation.

### Success Requires Independent Proof

"An agent launched" and "tmux stayed alive for 30 seconds" are not success.
Process liveness is only `verification.status = "partial_liveness"`.

Terminal success requires one of:

- the current target is complete;
- the current target advanced after repair;
- the current target has fresh activity after repair and no stronger proof is
  currently available;
- a true human blocker was classified, delivered, and recorded with a resumable
  response contract.

### State Mutation Requires One Shared Lock

Failure-triggered repair, hourly repair, meta-repair, and audit-initiated
cleanup must use one shared session/workspace lock before mutating `state.json`,
chain state, repair markers, or human escalation records. Stages may observe
without the lock. They may not clear stale state, answer gates, relaunch, or
delete markers without it.

### Human Escalation Is a Workflow, Not a Notification

Discord/webhook delivery is only transport. The durable artifact must record the
question, allowed responses, default answer, response channel/message, resume
command or handler, and final resolution. A human decision must remain
auditable even if the chain later advances and makes the question stale.

### Prompts and Reports Are Redacted Views

Failure context can contain secrets in stderr, command lines, logs, event
payloads, and workspace paths. Every prompt, Discord payload, Markdown report,
and summarized JSON field must pass through a redaction layer. Raw local logs can
remain on disk with restricted access, but contract artifacts should store
redacted excerpts by default.

## Stage-By-Stage Data Lifecycle

### 1. Failure-Triggered Repair

Purpose: enqueue immediate repair when a known bad state is observed, without
running long repair work inside state writers or event emitters.

Triggers:

- `latest_failure` recorded;
- plan enters `awaiting_human_verify`;
- expected worker exits;
- state is missing, invalid, or mismatched;
- stale marker conflict is detected;
- no-advance detection fires outside an active long-running step.

Must read:

- cloud session marker;
- current-target resolver output;
- plan `state.json`;
- chain state;
- latest event cursors;
- worker/tmux liveness;
- repair lock state;
- existing open repair requests for the same target signature.

Must write:

- immutable repair request under
  `<marker_dir>/repair-requests/<request_id>.json`;
- append-only event in `<marker_dir>/repair-events.ndjson`;
- optional watchdog/current index entry noting `repair_request_queued`.

Must pass forward:

- `request_id`;
- `incident_id`;
- current target reference;
- trigger reason;
- dedupe signature;
- immutable snapshot references.

Success proof:

- request was durably written and either claimed by a repair worker or visible
  in the queue for the next watchdog tick.

Failure proof:

- request rejected because resolver says target is stale/superseded;
- request coalesced into existing in-flight repair;
- request could not be written.

### 2. One-Hour Repair

Purpose: the durable fixer of record for a session or plan.

Must read:

- repair request, when present;
- marker JSON;
- current-target resolver output;
- current plan state and chain state;
- event cursors and recent log excerpts;
- repair-progress snapshot;
- previous current repair snapshot;
- unresolved human escalation ledger entries;
- recurrence signature history;
- repair lock.

Must write:

- mutable current repair snapshot:
  `<marker_dir>/repair-data/<session>.repair-data.json`;
- immutable attempt record:
  `<marker_dir>/repair-data/attempts/<attempt_id>.json`;
- append-only repair event entries;
- updated repair-progress snapshot;
- repair summary Markdown companion;
- human escalation ledger entry if truly blocked;
- terminal outcome in the current repair snapshot.

Must pass forward:

- current repair snapshot path;
- attempt record paths;
- incident signature;
- verification status and proof;
- recurrence decision;
- human escalation record id, if any.

Terminal outcomes:

- `already_complete`;
- `progressed`;
- `live_with_fresh_activity`;
- `true_human_blocker`;
- `recurring_retry_pending`;
- `repair_timeout`;
- `repair_system_failed`;
- `superseded_target`;
- `failed_unclassified`.

Success proof:

- `verification.status` is one of `complete`, `progressed`,
  `live_with_fresh_activity`, or `true_human_blocker`.

Failure proof:

- wall-clock budget expired;
- required state could not be read;
- model/tool launch failed;
- repeated same signature without advancement;
- Discord/human escalation delivery failed for a true human blocker.

### 3. Meta-Repair

Purpose: fix the repair system, not hand-fix the epic.

Must read:

- terminal one-hour repair evidence;
- latest attempt records;
- repair-progress snapshot;
- recent watchdog reports;
- recent audit reports;
- escalation ledger;
- repair events;
- current source commit and recent commits;
- focused test history when available.

Must write:

- immutable meta-repair record:
  `<marker_dir>/repair-data/meta/<meta_repair_id>.json`;
- Markdown companion;
- source patch references, if any;
- tests run and results;
- retriggered one-hour repair command;
- post-retrigger repair verification result;
- append-only repair events.

Must pass forward:

- `meta_repair_id`;
- files changed;
- commits/PR refs;
- tests run;
- retriggered repair attempt id;
- proof that the ordinary repair loop now succeeds or that the remaining issue
  is genuinely human-only.

Success proof:

- a later one-hour repair attempt, running through the normal entrypoint,
  produces successful verification.

Failure proof:

- 90-minute budget expired;
- cannot launch required tools/models;
- patch too risky or untestable;
- remaining blocker classified as true human.

### 4. Six-Hour Audit

Purpose: summarize the last activity window, find patterns, and improve the
repair system when the fix is bounded and testable.

Must read:

- marker inventory;
- current-target index;
- repair-data current snapshots;
- immutable incident/attempt/meta records;
- repair events;
- watchdog current and archived reports;
- audit current and archived reports;
- escalation ledger;
- plan/chain state and events;
- persistent findings;
- recent source commits and PR/ticket refs.

Must write:

- immutable JSON audit:
  `/workspace/audit-reports/<ts>-audit.json`;
- Markdown companion:
  `/workspace/audit-reports/<ts>-audit.md`;
- append-only audit log line;
- optional finding records/tickets;
- optional bounded fix refs and verification.

Must pass forward:

- root-cause patterns;
- related prior incident refs;
- autonomous fix attempts;
- risky or deferred fixes;
- unresolved human decisions;
- repeated signatures and no-advance windows.

Success proof:

- report is written even when no suspicious plans are found.

Failure proof:

- report records why audit could not inspect or dispatch subagents.

### 5. Discord/Human Escalation

Purpose: create a durable, resumable human decision record.

Must read:

- current target;
- latest repair evidence;
- true-human-blocker classification;
- relevant proof and proposed default;
- existing unresolved escalation records for the same incident.

Must write:

- append-only escalation ledger entry:
  `<marker_dir>/repair-data/escalations.ndjson`;
- mutable current pointer:
  `<marker_dir>/repair-data/<session>.needs-human.json`;
- Discord/webhook delivery result;
- response/resolution record when answered or superseded.

Must pass forward:

- `escalation_id`;
- exact question;
- allowed responses;
- default response;
- response channel and message id when available;
- resume command or handler;
- current evidence paths;
- delivery status;
- resolution status.

Success proof:

- delivery is confirmed or explicitly unavailable, and the escalation remains
  resumable through the ledger.

Failure proof:

- delivery failed;
- no response route exists;
- human answer cannot be matched to a current escalation.

## Canonical Persisted Artifacts and Schemas

### Artifact Layout

```text
<marker_dir>/
  <session>.json
  <session>.repair-loop.lock/
  repair-requests/
    <request_id>.json
  repair-data/
    <session>.repair-data.json
    <session>.repair-summary.md
    <session>.needs-human.json
    index.json
    incidents/
      <incident_id>.json
    attempts/
      <attempt_id>.json
    meta/
      <meta_repair_id>.json
    escalations.ndjson
  repair-events.ndjson

/workspace/
  watchdog-report.json
  watchdog-reports/
    <ts>-watchdog-report.json
  audit-report.log
  audit-reports/
    <ts>-audit.json
    <ts>-audit.md
  repair-findings/
    persistent-problems.md
```

The existing paths remain compatible:

- `<marker_dir>/<session>.json`;
- `<marker_dir>/<session>.repair-progress.json`;
- `<marker_dir>/repair-data/<session>.repair-data.json`;
- `<marker_dir>/repair-data/<session>.needs-human.json`;
- `/workspace/watchdog-report.json`;
- `/workspace/audit-reports/<ts>-audit.{json,md}`;
- `/workspace/audit-report.log`;
- plan `state.json`;
- plan `events.ndjson`;
- chain state JSON;
- `awaiting_user.json`.

### Current Target Record

```json
{
  "schema_version": 1,
  "resolved_at": "2026-07-01T00:00:00+00:00",
  "target_id": "target-...",
  "session": "cloud-session",
  "workspace_path": "/workspace/project",
  "run_kind": "chain",
  "remote_spec": ".megaplan/initiatives/demo/briefs/demo.md",
  "current_plan_name": "m3-plan",
  "current_plan_state": "executing",
  "current_chain_state_path": "/workspace/project/.megaplan/plans/.chains/chain-demo.json",
  "current_plan_state_path": "/workspace/project/.megaplan/plans/m3-plan/state.json",
  "worker": {
    "tmux_session": "cloud-session",
    "pid": 12345,
    "alive": true,
    "command_fingerprint": "sha256:..."
  },
  "event_cursors": {
    "plan_events_path": "/workspace/project/.megaplan/plans/m3-plan/events.ndjson",
    "plan_last_seq": 42,
    "chain_log_mtime": "2026-07-01T00:00:00+00:00"
  },
  "policy_ordering_decision": {
    "authoritative_source": "live_child_chain_state",
    "ignored_artifacts": [
      {
        "path": "/workspace/.megaplan/cloud-sessions/old-parent.json",
        "reason": "superseded_parent"
      }
    ],
    "rationale": "Live child session owns workspace and current chain state."
  }
}
```

### Incident Record

Immutable once written.

```json
{
  "schema_version": 1,
  "incident_id": "incident-cloud-session-20260701-a1b2c3d4",
  "created_at": "2026-07-01T00:00:00+00:00",
  "trigger": "latest_failure_recorded",
  "target": {"target_id": "target-..."},
  "problem_signature": {
    "failure_kind": "phase_failed",
    "current_state": "blocked",
    "phase_or_step": "execute",
    "milestone_or_plan": "m3-plan",
    "gate_recommendation": "ITERATE",
    "blocked_task_id": "task-123",
    "root_cause_hint_hash": "sha256:..."
  },
  "failure_snapshot": {
    "latest_failure": {},
    "plan_runtime_state": {},
    "chain_state_summary": {},
    "last_gate": {},
    "user_action_context": {},
    "execute_attempt_context": {},
    "raw_failure_signals": []
  },
  "source_refs": {
    "marker_path": "",
    "plan_state_path": "",
    "chain_state_path": "",
    "events_path": "",
    "repair_request_path": ""
  }
}
```

### Repair Request

Immutable request queue item. It can be marked claimed by appending a repair
event, not by rewriting the request.

```json
{
  "schema_version": 1,
  "request_id": "req-...",
  "created_at": "2026-07-01T00:00:00+00:00",
  "incident_id": "incident-...",
  "trigger": "awaiting_human_verify",
  "dedupe_key": "sha256:...",
  "target": {},
  "requested_action": "run_one_hour_repair",
  "status": "queued"
}
```

### Current Repair Snapshot

Mutable latest state at the existing stable path.

```json
{
  "schema_version": 1,
  "session": "cloud-session",
  "workspace": "/workspace/project",
  "spec": ".megaplan/initiatives/demo/briefs/demo.md",
  "run_kind": "chain",
  "plan_name": "m3-plan",
  "incident_id": "incident-...",
  "target": {},
  "repair_run_count": 2,
  "started_at": "2026-07-01T00:00:00+00:00",
  "deadline_at": "2026-07-01T01:00:00+00:00",
  "initial_facts": {},
  "attempt_ids": ["attempt-..."],
  "current_attempt_id": "attempt-...",
  "current_recurrence": {},
  "verification": {},
  "discord_escalation": {},
  "known_prior_issue_refs": [],
  "outcome": "repairing"
}
```

The current file may preserve legacy keys such as `attempts`, `iterations`,
`current_signature`, and `current_advancement_snapshot` until consumers migrate.

### Repair Attempt Record

Immutable attempt history.

```json
{
  "schema_version": 1,
  "attempt_id": "attempt-cloud-session-0003",
  "incident_id": "incident-...",
  "session": "cloud-session",
  "started_at": "2026-07-01T00:10:00+00:00",
  "ended_at": "2026-07-01T00:30:00+00:00",
  "budget": {
    "deadline_at": "2026-07-01T01:00:00+00:00",
    "remaining_secs_at_start": 3000,
    "remaining_secs_at_end": 1800
  },
  "target": {},
  "problem_signature": {},
  "pre_snapshot": {},
  "actions": [
    {
      "action_id": "action-1",
      "type": "dev_fix",
      "model": "gpt-5.4",
      "report_path": "",
      "claimed_result": "",
      "git_before": "",
      "git_after": "",
      "independent_check": {
        "changed_files": [],
        "nontrivial_change": false
      }
    },
    {
      "action_id": "action-2",
      "type": "mechanical_launch",
      "launch_command_fingerprint": "sha256:...",
      "raw_launch_command_path": "",
      "result": "started"
    }
  ],
  "post_snapshot": {},
  "verification": {},
  "recurrence": {},
  "outcome": "partial_liveness"
}
```

Raw launch commands may be stored by reference in a restricted local file. The
contract record should store a fingerprint and redacted summary.

### Verification Record

```json
{
  "schema_version": 1,
  "status": "progressed",
  "checked_at": "2026-07-01T00:20:00+00:00",
  "window_secs": 300,
  "pre": {
    "plan_state": "blocked",
    "plan_iteration": 4,
    "active_step_last_activity_at": "2026-07-01T00:00:00+00:00",
    "plan_event_seq": 42,
    "chain_completed_count": 2,
    "chain_milestone_index": 3,
    "git_head": "abc123"
  },
  "post": {
    "plan_state": "executing",
    "plan_iteration": 5,
    "active_step_last_activity_at": "2026-07-01T00:19:30+00:00",
    "plan_event_seq": 46,
    "chain_completed_count": 2,
    "chain_milestone_index": 3,
    "git_head": "abc123"
  },
  "proofs": [
    {
      "kind": "plan_event_seq_advanced",
      "before": 42,
      "after": 46
    },
    {
      "kind": "state_transition",
      "before": "blocked",
      "after": "executing"
    }
  ],
  "partial_liveness": {
    "tmux_alive": true,
    "worker_pid": 12345
  },
  "failure_reason": ""
}
```

Allowed statuses:

- `complete`;
- `progressed`;
- `live_with_fresh_activity`;
- `true_human_blocker`;
- `partial_liveness`;
- `failed`;
- `not_checked`.

### Repair Progress Snapshot

Mutable compatibility sidecar. Existing recurrence fields remain valid:

```json
{
  "updated_at": "2026-07-01T00:00:00+00:00",
  "current": {},
  "last_dispatch_snapshot": {},
  "no_advance_dispatches": [],
  "no_advance_count": 0,
  "advancement_since_last_dispatch": false,
  "window_seconds": 21600,
  "min_dispatches": 3,
  "layer2_recurrence": false
}
```

### Human Escalation Ledger Entry

Append-only line in `escalations.ndjson`.

```json
{
  "schema_version": 1,
  "event_type": "escalation_opened",
  "escalation_id": "esc-...",
  "incident_id": "incident-...",
  "session": "cloud-session",
  "created_at": "2026-07-01T00:00:00+00:00",
  "target": {},
  "question": "Should the repair loop resume this clarification with default X?",
  "allowed_responses": ["approve_default", "choose_alternative", "stop"],
  "default_response": "approve_default",
  "evidence_refs": {
    "repair_data_path": "",
    "attempt_id": "",
    "audit_path": ""
  },
  "delivery": {
    "transport": "discord_dm",
    "status": "delivered",
    "message_id": "",
    "channel_id": "",
    "delivered_at": ""
  },
  "resume": {
    "handler": "megaplan_resume_human_gate",
    "command_redacted": "megaplan resume ...",
    "requires_confirmation": true
  }
}
```

Resolution entries use the same `escalation_id`:

```json
{
  "schema_version": 1,
  "event_type": "escalation_resolved",
  "escalation_id": "esc-...",
  "resolved_at": "2026-07-01T00:30:00+00:00",
  "resolution": "answered",
  "answer": "approve_default",
  "actor": "human",
  "resume_result": {
    "status": "accepted",
    "verification": {}
  }
}
```

The mutable `<session>.needs-human.json` is only a current pointer and summary:

```json
{
  "schema_version": 1,
  "session": "cloud-session",
  "incident_id": "incident-...",
  "escalation_id": "esc-...",
  "plan_name": "m3-plan",
  "summary": "awaiting human decision",
  "question": "...",
  "default_response": "approve_default",
  "repair_data_path": "",
  "discord_status": "delivered",
  "recorded_at": "2026-07-01T00:00:00+00:00"
}
```

Deleting the current pointer must never delete the ledger record.

### Meta-Repair Record

```json
{
  "schema_version": 1,
  "meta_repair_id": "meta-...",
  "incident_id": "incident-...",
  "trigger_attempt_id": "attempt-...",
  "started_at": "2026-07-01T00:00:00+00:00",
  "ended_at": "2026-07-01T01:30:00+00:00",
  "diagnosis": {
    "repair_system_failure_type": "verification_blind_spot",
    "root_cause": "",
    "not_epic_specific": true
  },
  "subagent_results": [
    {
      "model": "deepseek:deepseek-v4-flash",
      "brief": "state mapping",
      "result_path": "",
      "succeeded": true
    }
  ],
  "changes": [
    {
      "path": "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop",
      "summary": "..."
    }
  ],
  "tests": [
    {
      "command": "pytest tests/cloud/test_watchdog_wrappers.py -k verify",
      "status": "passed"
    }
  ],
  "retrigger": {
    "command_redacted": "arnold-repair-loop ...",
    "attempt_id": "attempt-..."
  },
  "post_retrigger_verification": {},
  "outcome": "repair_loop_fixed"
}
```

### Watchdog Report

The existing current report remains mutable at `/workspace/watchdog-report.json`
and should also archive immutable copies in `/workspace/watchdog-reports/`.

Required fields:

- `schema_version`;
- `timestamp_utc`;
- `marker_dir`;
- `markers_seen`;
- `sessions_seen`;
- `items`;
- `issues`;
- `repair_dispatches`;
- `stale_artifacts_ignored`;
- `report_archive_path`.

### Audit Report

The existing JSON/Markdown pair remains the human-facing audit artifact.

Required fields:

- `schema_version`;
- `timestamp_utc`;
- `window_hours`;
- `finding_count`;
- `findings`;
- `root_cause_patterns`;
- `related_prior_incidents`;
- `autonomous_fix_attempts`;
- `risky_or_deferred_fixes`;
- `green_checks`, even when no suspicious plans are found.

## Mutable vs Append-Only Data

Mutable current state:

- cloud session marker `<session>.json`;
- repair lock directory;
- current repair snapshot `<session>.repair-data.json`;
- current needs-human pointer `<session>.needs-human.json`;
- repair-progress snapshot `<session>.repair-progress.json`;
- repair-data `index.json`;
- `/workspace/watchdog-report.json`;
- plan `state.json`;
- chain state JSON;
- `awaiting_user.json`, until resumed.

Append-only or immutable evidence:

- `repair-events.ndjson`;
- repair request records;
- incident records;
- attempt records;
- escalation ledger entries;
- meta-repair records;
- archived watchdog reports;
- audit reports;
- audit log;
- plan `events.ndjson`;
- AgentBox run `events.ndjson`;
- repair summary Markdown snapshots;
- persistent findings entries.

Mutable files must be written atomically. Append-only ledgers must include
monotonic timestamps and stable ids. Where possible, append-only ledgers should
use the existing `events.ndjson` pattern with sequence numbers or idempotency
keys.

## Dedupe and Signature Strategy

### Identifiers

- `target_id`: hash of workspace, run kind, remote spec, current chain path,
  current plan path, and current plan name.
- `incident_id`: `incident-<session>-<yyyymmdd>-<signature_hash_8>`.
- `request_id`: hash of incident id, trigger, and request creation time.
- `attempt_id`: `attempt-<session>-<repair_run_count>-<attempt_counter>`.
- `escalation_id`: `esc-<incident_id>-<counter>`.
- `meta_repair_id`: `meta-<incident_id>-<yyyymmddhhmmss>`.

### Incident Signature

Reuse the existing controlled fields from `repair_recurrence.py`:

- `failure_kind`;
- `current_state`;
- `phase_or_step`;
- `milestone_or_plan`;
- `gate_recommendation`;
- `blocked_task_id`.

Add one bounded root-cause discriminator:

- `root_cause_hint_hash`: hash of a redacted, normalized excerpt from stderr,
  failure message, or machine-readable error code.

This avoids collapsing distinct failures that share the same phase and state,
while avoiding raw secret-bearing text in the signature.

### Request Dedupe

Repair request dedupe should avoid exact timestamps because repeated reports of
the same incident often differ by seconds. Use:

- `target_id`;
- normalized incident signature;
- trigger kind;
- state/event cursor;
- active step run id when present.

Requests with the same dedupe key are coalesced into one queued or in-flight
repair. Coalescing should append a repair event, not mutate the original request.

### Escalation Dedupe

One unresolved escalation may exist per `incident_id` and question hash. If a
new target supersedes the old one, append `escalation_resolved` with
`resolution = "superseded"`, preserve the question, and write a new escalation
only if the current target still needs a human.

### Audit Finding Dedupe

Audit findings dedupe by:

- incident signature;
- target lineage;
- audit window;
- prior finding refs.

The auditor should still report repeated unresolved incidents, but as
continuations linked to the same incident family rather than fresh unrelated
findings.

## Cross-Reference Strategy

Every artifact that summarizes another artifact should reference it by path and
stable id, not copy the entire artifact.

Required reference fields:

- `incident_id`;
- `target_id`;
- `request_id`, when applicable;
- `attempt_id`, when applicable;
- `escalation_id`, when applicable;
- `meta_repair_id`, when applicable;
- `source_refs` object with file paths;
- `commit_refs` for source changes;
- `pr_refs` or ticket refs when known;
- `prior_incident_refs`;
- `prior_audit_refs`;
- `prior_watchdog_report_refs`;
- `persistent_finding_refs`.

The repair-data index should make lookups cheap:

```json
{
  "schema_version": 1,
  "updated_at": "2026-07-01T00:00:00+00:00",
  "sessions": {
    "cloud-session": {
      "current_repair_data_path": "",
      "latest_incident_id": "",
      "latest_attempt_id": "",
      "latest_outcome": "",
      "unresolved_escalation_ids": [],
      "signature_hashes": [],
      "target_id": ""
    }
  },
  "incidents": {
    "incident-...": {
      "session": "cloud-session",
      "signature_hash": "",
      "latest_attempt_id": "",
      "status": "open"
    }
  }
}
```

Current-target records should include `ignored_artifacts` so stale parent and
old plan confusion is visible in later audits.

## Human Escalation Data

Human escalation requires two artifacts:

1. Append-only escalation ledger for durability and audit.
2. Current needs-human pointer for watchdog compatibility and fast UI/Discord
   summaries.

The escalation must record:

- exact question;
- why a human is needed;
- why automation is not allowed to answer;
- suggested default;
- allowed responses;
- deadline or expected response window, if any;
- response channel/message id;
- evidence refs;
- resume handler or redacted command;
- delivery result;
- resolution result.

A Discord message must be answerable. If the resident bot cannot map a reply to
an escalation id, the message should say so and the escalation record should mark
`response_route = "unavailable"` so meta-repair and audit can diagnose the gap.

## Verification and Proof Data

Every repair action must capture a pre/post proof window. Required observed
signals:

- tmux/session liveness;
- worker pid and command fingerprint;
- plan state;
- plan iteration;
- active step phase/run id/last activity time;
- plan event path and last seq;
- chain state path;
- current plan name from chain;
- chain milestone index and completed count;
- chain log mtime or event cursor;
- git HEAD and branch state when relevant;
- unresolved human escalation state.

Verification status rules:

- `complete`: current target terminal state is complete/finalized/done.
- `progressed`: milestone index, completed count, plan iteration, plan state, or
  git HEAD advanced.
- `live_with_fresh_activity`: worker is alive and event seq, active step
  heartbeat, or chain log mtime advanced inside the proof window.
- `true_human_blocker`: blocker classification says human-only and escalation
  ledger has an open or delivered record.
- `partial_liveness`: process is alive but no stronger proof exists.
- `failed`: process died, state regressed, or no proof was collected.
- `not_checked`: verification could not run; this should be a repair failure
  unless another proof exists.

Dev-fix claims must be independently checked. At minimum, record git before/after
and whether the diff changed nontrivial files. A self-reported model summary must
not be used as success proof.

## Retention and Cleanup Policy

Retention should preserve evidence long enough for the six-hour auditor and a
few follow-up cycles without unbounded growth.

Recommended defaults:

- repair requests: delete after successful claim plus 24 hours of immutable
  event history;
- current repair snapshots: keep latest per session indefinitely while session
  exists;
- immutable repair attempts: keep 14 days or last 20 attempts per session,
  whichever is larger;
- incident records: keep 30 days, or longer if unresolved;
- escalation ledger: keep 90 days, or longer if unresolved;
- meta-repair records: keep 90 days;
- watchdog current report: overwrite each tick;
- archived watchdog reports: keep 14 days;
- audit reports: keep 30 days;
- audit log: rotate at 10 MB;
- persistent findings: roll up monthly into a summarized archive;
- raw logs: follow existing workspace retention, but summaries should store only
  redacted excerpts.

Cleanup must never delete:

- unresolved escalation ledger entries;
- unresolved incident records;
- the latest current repair snapshot for an active session;
- audit reports referenced by unresolved incidents.

Cleanup should append a cleanup event summarizing what was pruned.

## Migration Path From Current Sidecars and Reports

### Phase 1: Add Schema Fields Without Changing Behavior

- Add `schema_version` to current repair-data, needs-human, watchdog, and audit
  reports.
- Preserve existing `iterations`, `attempts`, `initial_facts`, and `outcome`
  keys.
- Add `target`, `incident_id`, `attempt_ids`, `verification`,
  `discord_escalation`, and `known_prior_issue_refs` as additive fields.
- Treat missing fields as legacy version 0.

### Phase 2: Introduce Current-Target Resolver Output

- Generate current-target records inside watchdog and repair-loop collection.
- Record `policy_ordering_decision` and `ignored_artifacts`.
- Keep existing stale needs-human and sibling-session checks until the resolver
  fully replaces them.

### Phase 3: Add Immutable Attempt and Incident Records

- Continue writing `<session>.repair-data.json` for existing readers.
- Also write `incidents/<incident_id>.json` and `attempts/<attempt_id>.json`.
- Store only bounded, redacted context excerpts in immutable records.
- Put large raw context behind `source_refs`.

### Phase 4: Convert Needs-Human Marker to Ledger Plus Pointer

- Continue writing `<session>.needs-human.json`.
- Add `escalations.ndjson`.
- Change marker clearing into ledger resolution records.
- Allow watchdog to hide resolved/superseded pointers while keeping history.

### Phase 5: Add Verification Semantics

- Capture pre/post snapshots around mechanical and model-driven repairs.
- Change liveness-only success to `partial_liveness`.
- Use successful verification, not model claims, to set terminal outcomes.

### Phase 6: Add Meta-Repair Records and Audit Cross-Refs

- Write meta-repair records under `repair-data/meta/`.
- Teach auditor to read incident, attempt, escalation, and meta records.
- Populate related prior incidents, prior audit refs, and persistent findings.

## Tests and Validation Needed

Data contract validation:

- validate legacy repair-data as version 0;
- validate new current repair snapshot schema;
- validate immutable incident, attempt, escalation, meta-repair, watchdog, and
  audit records;
- reject missing ids, missing target, missing outcome, and unredacted secret
  patterns.

Current-target tests:

- live child chain beats stale parent marker;
- active current plan beats stale needs-human pointer;
- fresh events beat old repair-progress sidecar;
- sibling live session suppresses parent relaunch;
- resolver records ignored artifacts and rationale.

Repair request tests:

- duplicate failure events coalesce;
- timestamp drift does not fragment the same incident;
- distinct root-cause hints do not collapse into one incident;
- stale-parent request is rejected without repair action.

Verification tests:

- worker launches and stays alive briefly but no state/event progress occurs:
  outcome must not be `running` or success;
- event seq advances during long-running step: status is
  `live_with_fresh_activity`;
- milestone or completed count advances: status is `progressed`;
- true human blocker writes escalation ledger and pointer;
- verification failure triggers meta-repair eligible outcome.

Concurrency tests:

- failure-triggered and hourly repair race on the same session;
- only one actor obtains the shared repair lock;
- no state mutation occurs without the lock;
- losing actor appends a coalesced/busy event.

Human escalation tests:

- needs-human pointer can be cleared/resolved without deleting ledger history;
- Discord delivery status is persisted;
- human answer maps to escalation id and resume handler;
- superseded question gets resolution `superseded`.

Redaction tests:

- tokens in logs, stderr, command lines, environment-shaped strings, and event
  payloads are redacted before prompt/report/escalation storage;
- raw restricted file refs remain available for local debugging without being
  copied into LLM-visible summaries.

Audit tests:

- green audit writes JSON and Markdown;
- repeated incidents cross-reference prior audit and repair records;
- unbounded repair-data history is summarized through index and retention;
- autonomous fix report includes tests and post-retrigger verification.

## Open Questions Requiring Human Judgement

- Should Discord responses be free text, structured commands, reactions/buttons,
  or a strict command plus escalation id?
- What default verification window is acceptable for legitimately slow workers:
  5 minutes, 10 minutes, or stage-specific thresholds?
- May meta-repair commit and deploy autonomously, or should it stop at a patch
  plus tests for human approval?
- How long should unresolved human escalations remain visible in the operator
  surface after the chain supersedes them?
- Which paths are allowed to store raw unredacted local evidence, and what file
  permissions should they require?
- Should the root-cause hint hash include redacted stderr/message excerpts, or
  only structured error codes to reduce collision risk without carrying text?
- Should audit retention be longer than 30 days for cloud incidents that recur
  monthly?
- Should repair-system fixes require a negative control retry to distinguish a
  true repair from transient recovery?
