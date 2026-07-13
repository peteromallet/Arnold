# Exceptionally rigorous end-to-end run tracking

## VibeComfy reconstruction and a general architecture for Megaplan, cloud, watchdog, repair, and resident delegated-agent runs

**Canonical initiative:** custody-control-plane

**Evidence cutoff:** 2026-07-10T23:31:34Z, with one later read confirming the repair retrigger changed the plan projection to finalized with no latest failure

**Scope:** local durable artifacts and local processes only. No remote shell was used. No repair runner was launched by this investigation.

**Operational recheck at 2026-07-10T23:38:34Z:** subagent-20260710-230902-16f838da remained live; subagent-20260710-231759-ed2f44a7 had become interrupted with return code 143. Plan state was finalized with no latest failure, while chain state still projected milestone zero as blocked. No process was signaled or otherwise changed by this investigation.

## Executive conclusion

The system records a great deal, but it does not yet record one coherent end-to-end story. It has several detailed local journals and snapshots whose identities, clocks, causal links, freshness rules, and custody semantics do not join reliably:

- plan state and plan events;
- chain state and the unstructured chain log;
- cloud session markers and chain-health projections;
- watchdog reports;
- repair-data and the newer incident ledger;
- resident messages, turns, delegated-agent manifests, logs, results, and completion-delivery state;
- Git, PR, CI, and provider-side facts.

VibeComfy demonstrates the practical consequence. At the same time, different surfaces could truthfully report all of the following: the plan was blocked, a repair was active, no Megaplan phase was active, a stale LLM call was in flight, the plan was progressing, the chain needed a human, a Discord notification was delivered, and a repair had achieved partial liveness. Each statement came from a different projection. There was no common causal chain proving which statement superseded which, who currently owned recovery, or whether the original condition had actually recovered.

The strongest findings are:

1. **Active repair already existed and one repair agent remained active at final recheck.** At the evidence cutoff, two resident delegated agents were live for the same VibeComfy corrective incident:
   - subagent-20260710-230902-16f838da, request vibecomfy-recovery-20260710;
   - subagent-20260710-231759-ed2f44a7, request vibecomfy-holistic-stall-20260710.

   A prior root-fix agent, subagent-20260710-215400-1dd0389e, had completed. The first live agent subsequently invoked the supported Megaplan execute recovery path. By 23:38:34Z the first remained live and the second had been interrupted. This investigation launched no duplicate repair.

2. **There is no shared repair lease or incident correlation in those manifests.** Both live manifests say running and point at the same workspace, but neither contains the VibeComfy session ID, plan ID, incident ID, blocker ID, repair-attempt ID, parent event, ownership lease, heartbeat, or supersession relationship. Different request IDs hide that they contend for the same logical incident.

3. **Observation can change the evidence used to infer liveness.** At 23:29:26Z, introspection read an authoritatively blocked plan with no active phase, but reported progressing because the last event was five seconds old. That recent event was a state-written event produced by observation/reconciliation itself. The same payload displayed a stale unmatched LLM start from 22:24:37Z, while doctor warned that the call had no heartbeat for more than an hour. An observer can therefore refresh the activity clock that the observer uses to classify the run.

4. **The plan event journal is voluminous but semantically sparse at the failure boundary.** In the sampled VibeComfy journal there were 630 events: 482 state-written events consuming about 15.6 MB, 37 LLM starts, 11 LLM ends, 34 phase starts, and 31 phase ends. There were no causal IDs, parent event IDs, run IDs, or attempt IDs. Phase-end events carried only the phase name, not outcome or error. Provider-capacity failures were recoverable only from full state snapshots, raw provider output, and chain-log prose.

5. **Capacity handling became a retry storm.** The state history recorded 26 Codex usage-limit errors between 22:15:34Z and 22:24:16Z. The chain retried roughly every 19–24 seconds, repeatedly logged that it was at the escalation ceiling, and continued to invoke the same unavailable provider instead of recording a typed capacity deferral with a next-eligible time. This consumed iteration budget and produced many unmatched call starts.

6. **Repair success was defined as liveness rather than verified recovery.** Legacy repair-data marked both attempts partial_liveness and completed the second repair record at 22:06:59Z. The original plan later blocked again on a different task, T16, at 22:33:53Z. The repair-data file remained keyed to the earlier T14 signature and did not become a new causal problem chain.

7. **The incident ledger exists but was not the end-to-end ledger.** The VibeComfy incident ledger contained only four repair-attempt events: attempted and partial_liveness for attempts one and two. It had no watchdog detection, dispatch, mechanical-launch failure, provider-capacity failure, install-sync, retrigger, verified-recovered, recurrence, delivery, or terminal event. All four parent-event lists were empty, evidence payloads were empty, and the declared next expected verification event never arrived.

8. **Delivery truth is split.** Normal resident delegated-agent manifests can store immutable Discord origin and completion-delivery attempts. The completed VibeComfy root-fix agent had neither because its synthetic request ID appended a suffix to the inbound resident message ID, preventing provenance recovery. Separately, the watchdog report said “needs-human Discord DM delivered” but held no delivery attempt ID, provider message ID, outbox record, or durable link to the incident. It is impossible to prove from one ledger what was delivered, to whom, for which causal state, and whether a later recovery invalidated the message.

9. **Current state is moving, but recovery was not yet proven terminal.** Around 23:29Z the plan was blocked on T16. Around 23:30Z an existing repair agent retriggered execute through supported tooling; a later read showed the plan projection at finalized with latest_failure cleared. The chain projection still represented milestone zero and previously blocked custody. That is evidence of active repair and renewed execution, not yet proof of chain completion, publication, delivery, or verified recovery.

The implementable answer is not another status label. It is one append-only causal event envelope, one target identity model, one exclusive renewable custody lease, content-addressed evidence, typed error and recovery decisions, and replayable projections that explicitly separate execution, liveness, custody, recovery, capacity, delivery, publication, and integrity.

## Why custody-control-plane is the canonical home

The closest initiative was found by rough-title and description search across canonical initiatives. custody-control-plane explicitly says it supersedes canonical-run-state-control-plane, incident-control-plane, superfixer-repair-custody, and tiered-repair-hardening. Its North Star already establishes the correct foundations:

- a pure resolve_run_state authority;
- read-coherent evidence collection;
- liveness is not success;
- mandatory verify_retrigger_success;
- drift must be emitted;
- dispatch must reject non-canonical inputs;
- an event-sourced incident ledger;
- audit of the resolver and repair system themselves.

This report extends that initiative rather than proposing a parallel control plane. The extension is that the authority must span ingress, resident delegation, cloud launch, plan and chain execution, repair, external effects, and terminal reply delivery, not only status and watchdog classification.

## Investigation method and safety boundary

The inspection followed the Megaplan observation hierarchy: introspect, trace, doctor, then direct durable-artifact inspection. Timestamp judgments were anchored to introspect.now_utc. Direct inspection covered:

- the VibeComfy plan state, events, execution trace, routing ledger, artifacts, step receipts, raw provider output, and chain log;
- the chain projection and Git state;
- cloud session, chain-health, repair-progress, repair-data, watchdog report, and archived incident events;
- resident delegated-agent manifests, processes, logs, results, completion-delivery fields, messages, turns, and conversation projections;
- local process and tmux metadata;
- the current tracking, liveness, incident, repair, and resident implementation.

No remote shell was used. No tmux session was attached, stopped, or modified. No signal was sent. No recovery or chain command was launched by this investigation. One important observer effect was nevertheless discovered: introspect/reconciliation appended state-written evidence and changed state/event modification times. That is a product defect, not an intentional repair action, and should be covered by the observer-purity acceptance test below.

## Worked reconstruction: VibeComfy

### Identity map

| Layer | Observed identity |
|---|---|
| Cloud session | vibecomfy-trust-corrective-2026-07 |
| Initiative/chain slug | vibecomfy-trust-correctness-2026-07 |
| Plan | corrective-verification-and-20260710-2028 |
| Chain projection | chain-61d2e7102328 |
| Incident | inc-vibecomfy-trust-corrective-2026-07 |
| Legacy blocker | blocker:v1:9f691… |
| PR | 140, open at the evidence cutoff |
| Earlier repair commits | 0e7636b and 9bc855e |
| Latest sampled execution commit | a9b2add |
| Completed root-fix agent | subagent-20260710-215400-1dd0389e |
| Live repair agents at cutoff | subagent-20260710-230902-16f838da and subagent-20260710-231759-ed2f44a7 |

These identities are not carried together on any one event or manifest. The table is a manual reconstruction.

### Timeline

| UTC | Reconstructed fact | Evidence and ambiguity |
|---|---|---|
| 20:28:19 | Cloud marker created for the corrective chain. | Marker records session, workspace, spec, launch recipe, and start time, but no current plan, runner lease, PID, heartbeat, correlation root, or marker revision. |
| 20:28:28–20:41:52 | Plan initialized and advanced through prep, plan, critique, gate, and finalize. | Plan events have ordered sequences and UTC timestamps. The five state transitions are explicit. |
| 20:41:52–21:11:52 | First execute ran batches 8–14 and ended blocked. | The detailed reason is in state history, execution artifacts, and logs. Phase-end itself says only execute. |
| 21:12:14 | Incident attempt one recorded. | Incident ledger starts with repair_attempt/attempted. There is no preceding detection or dispatch event and no parent. |
| 21:12–21:17 | Mechanical relaunch was reported failed:stopped; Kimi reported a live resumed chain; a development fix added ComfyUI sibling discovery and commit 0e7636b. | The later root-fix agent found a launcher race: the temporary tmux script was deleted before tmux opened it. Thus a valid launch could be classified stopped. Repair-data conflated this control-plane failure, target fix, and process liveness. |
| 21:17:31 | Attempt one recorded partial_liveness. | No verified-recovered event followed. The plan was still not durably through its acceptance condition. |
| 21:54:00–22:19:02 | A resident root-fix agent ran and completed. | Its result says it fixed the launcher race and VibeComfy E2E fallback. The manifest has hashes, paths, model, PIDs, and timestamps, but no incident or plan correlation and no completion delivery. |
| 21:56:14 | Incident attempt two recorded. | It reuses the T14 problem signature but recurrence remained false and attempt_number remained one. |
| 21:56–22:07 | Mechanical relaunch again said failed:stopped; Kimi observed a live process; development fix 9bc855e added a managed ComfyUI fallback. | Again the system classified liveness as partial recovery. repair-data completed at 22:06:59Z. |
| 22:04:55–22:15:43 | A resumed execute ran; T14 progressed. | Repair-data’s incident record stopped before later outcomes. |
| 22:15:34–22:24:16 | Twenty-six usage-limit errors occurred. | State history records each error. The chain log contains raw provider prose and the promised retry time. There is no provider.capacity_exhausted event, retry-after field, capacity lease, or deferred state. |
| 22:15:48–22:24:33 | Execute was restarted repeatedly, generally every 19–24 seconds. | Each start generated phase and LLM events; most capacity failures did not generate LLM-end or LLM-error events. Escalation-ceiling logging did not stop the loop. |
| 22:24:37–22:33:53 | A later execute call ran long enough to produce work and commit a9b2add, then the plan blocked on T16. | T16 reported real validation and artifact-sanitation failures. This was a new problem after T14, but no new incident or blocker lineage was opened. |
| 23:09:02 | Resident repair agent 16f838da started for VibeComfy recovery. | Live worker and Codex processes existed. Manifest status was running, but there was no lease or incident link. |
| 23:14:39–23:14:49 | Chain-health said stalled/blocked; watchdog said needs_human and claimed a Discord DM was delivered. | The watchdog also emitted drift showing canonical REPAIRING with queue_only versus legacy dispatch_l1_repair. It did not recognize the resident repair agent as custody that should suppress human classification. |
| 23:17:59 | A second resident repair agent ed2f44a7 started for the same incident. | No uniqueness constraint or shared target lease prevented duplicate ownership. |
| 23:29:26 | Introspect said plan blocked, no active phase, liveness progressing, and displayed an unmatched 22:24 LLM start. | Progressing was caused by a very recent event; doctor simultaneously warned of a stale unmatched call. Process discovery found one repair agent by matching the exact plan name in its command text but missed the other, whose prompt used a looser description. |
| 23:30:57 | The first live repair agent invoked supported execute recovery. | This was existing repair work, not work launched by this investigation. |
| after 23:31 | A read showed plan state finalized and latest_failure null. | This proves a transition/retrigger, not verified chain recovery. A terminal claim still requires chain advancement, clean custody, required validation, external publication truth, and delivery truth. |
| 23:35:55 | The second resident repair agent became interrupted with return code 143; the first remained live at 23:38:34. | The duplicate-custody interval ended operationally, but there is still no durable lease/transfer/supersession event explaining why or proving exclusive custody. |

### Fault tree

**Original correctness path**

1. Execute reached T14 and could not find/provision the required ComfyUI environment.
2. Initial fixes addressed path discovery and then managed fallback provisioning.
3. Independent acceptance later exposed T16 gate-surface and artifact-sanitation failures.

**Recovery-control path**

1. The mechanical launcher removed a temporary script before tmux consumed it.
2. The launch could be valid while the wrapper returned failed:stopped.
3. Kimi then observed a live process and the repair outcome became partial_liveness.
4. No mandatory verification asserted that the original blocked task, plan, chain, tests, and external delivery had recovered.
5. The same legacy blocker signature remained current even when the actual blocker moved from T14 to T16.

**Provider-capacity path**

1. Codex returned a typed usage-limit response with a future retry time.
2. The response became generic internal_error history and unstructured log text.
3. The auto loop retried 26 times in about nine minutes.
4. Tier escalation could not change availability because the provider/vendor constraint was unchanged.
5. Missing LLM terminal events accumulated, degrading later in-flight inference.

**Custody path**

1. Watchdog/repair-data owned one view of repair.
2. Resident delegated agents were launched under unrelated request IDs with no incident lease.
3. Watchdog classified needs-human while a repair agent was already live.
4. A second repair agent launched because no compare-and-set lease guarded the target incident.
5. Process discovery used command-line substring matching, so exact prompt wording influenced liveness.

**Delivery path**

1. The originating Discord message had durable message and turn records.
2. The delegated root-fix request appended a suffix to the resident message ID.
3. Exact origin lookup therefore failed; the manifest had no Discord origin and no completion-delivery state.
4. Watchdog later claimed a needs-human DM was delivered, but only as report prose without a durable outbox receipt.

### What should the canonical status have been?

At 23:29Z a single label was insufficient. The correct multidimensional projection was approximately:

| Dimension | Correct projection |
|---|---|
| Execution | BLOCKED, T16 |
| Plan phase | none active |
| Liveness | no active Megaplan phase; resident repair workers live |
| Custody | CONFLICTED: two resident repair claims, no exclusive lease |
| Recovery | REPAIRING, original recovery not verified |
| Capacity | available again after an earlier capacity-exhausted interval |
| Chain | milestone 0 not complete; last projected state blocked |
| Publication | PR open; chain projection’s branch/head fields stale relative to local execution |
| Delivery | needs-human delivery claimed by watchdog; repair completion delivery absent/unproven |
| Integrity | projection drift present; observer effect and stale incident data detected |

This projection would have prevented both “progressing” optimism and “needs human” overstatement.

## What is logged today

### Plan state and plan event journal

The plan directory is the richest source. It records:

- state.json with current state, config, history, latest failure, resume cursor, model sessions, gate metadata, execution-environment metadata, and recovery notes;
- events.ndjson with ordered sequence, UTC timestamp, relative-init time, kind, phase, payload, store method, transaction ID, and sometimes workflow cursor;
- prep, plan, critique, gate, finalize, execute, review, and transition artifacts;
- step receipts;
- raw provider output;
- routing_ledger.jsonl and execution_trace.jsonl;
- approval and resume anchors;
- artifact hashes and cost history.

The declared EventKind vocabulary is broader than what appeared in this run. It includes lifecycle, subprocess, LLM, artifact, decision, cost, evaluation, diagnostic, and routing events. In the sampled journal only 12 kinds appeared.

Observed event counts at the evidence cutoff:

| Kind | Count | Important payload |
|---|---:|---|
| state_written | 482 | full state, effect, effect class, taint |
| llm_call_start | 37 | provider, model, prompt hash, null request ID |
| llm_call_end | 11 | model, request ID, token counts |
| phase_start | 34 | phase only |
| phase_end | 31 | phase only |
| cost_recorded | 11 | provider, model, request ID, cost |
| artifact_written | 9 | path, size |
| state_transition | 5 | from, to |
| tier_escalated | 4 | tiers/models/failure count |
| init | 3 | plan name |
| drift_detected | 2 | canonical versus legacy decision |
| anchor_captured | 1 | source path, hash, size |

What this does well:

- append ordering is explicit;
- timestamps are UTC and sequence numbers are monotonic per journal;
- North Star and many generated artifacts are hashed;
- cost, routing, and state history are durable;
- the state can often be reconstructed after a crash.

What it does not do:

- no event_id distinct from sequence;
- no correlation_id, causation_id, parent_event_id, run_id, phase-instance ID, task attempt ID, repair ID, or delivery ID;
- transaction_id is generated per emitted event and is not a shared transaction/call correlation key;
- LLM starts have null request IDs while ends have request IDs;
- phase-end has no outcome, error, retry decision, or artifact references;
- capacity errors do not produce LLM_CALL_ERROR or provider-capacity events;
- state-written dominates storage and activity calculations;
- full state snapshots are repeatedly embedded instead of checkpointed and content-addressed;
- read-side reconciliation can write events, contaminating liveness.

### Chain and cloud state

The cloud marker records:

- session, run kind, identity digest, workspace, remote spec, chain slug;
- start time;
- editable-source branch and sync status;
- a complete relaunch command.

The chain projection records:

- current milestone and plan;
- last state;
- completed milestones;
- target base;
- branch, PR, and push fields;
- sync and dirty flags;
- chain-spec path and hash;
- execution-environment paths and target commits;
- a point-in-time ground-truth reconciliation object.

The cloud chain log records exact commands, return codes, state-loop decisions, model escalation prose, raw provider errors, Git operations, and the final stop payload.

The chain-health projection records current plan, last state, event mtime/size, liveness, active-step and in-flight booleans, PR state, stuck ticks, and updated_at.

The gaps are consequential:

- marker has no renewable owner lease, PID, process start identity, heartbeat, or supersession;
- chain schema is version 0 and lacks updated_at and projection source version;
- chain branch_head/pr_head/last_pushed_commit can lag the actual local head;
- ground_truth_reconciliation is a stale embedded snapshot with no validity interval;
- chain log contains critical facts only as prose;
- relaunch command storage is oversized and risks retaining environment interpolation or sensitive command material;
- mtime and event size are treated as progress signals even when observers write.

### Watchdog and repair tracking

The watchdog report records its timestamp, marker/session counts, issue count, restarted sessions, needs-human sessions, feature switches, and per-session action/status/message.

Repair-progress records advancement snapshots, no-advance counts, recurrence windows, plan activity, Git/PR checks, and last dispatch.

Legacy repair-data is very detailed. It records:

- incident, blocker, request, session, workspace, and plan fields;
- signatures and recurrence structures;
- attempts, dispatch times, mechanical and Kimi launch results;
- model choices, development fix SHAs, diagnosis, summaries, and validation commands;
- copied chain, plan, failure, log, resolver, and user-action context.

The newer incident ledger has a strong intended schema: event ID, timestamp, type, actor, scope, outcome, summary, incident/session/problem/attempt IDs, parent and trigger IDs, evidence, deadline, next expected event, decisions, actions, and links.

The observed implementation gap is large:

- repair-data was 3.46 MB and copied large mutable snapshots and log tails;
- it said partial_liveness and completed before later capacity and T16 failures;
- attempt_ids was empty even though attempts contained IDs 1 and 2;
- both recurrences said attempt_number one and detected false;
- the current signature’s blocked_task_id was T1 while its event signature named T14;
- no new problem identity was created for T16;
- incident events contained only four attempt markers, no causal parents, and empty evidence;
- declared next expected verification was never fulfilled;
- repair agents launched outside repair-data were invisible to its custody model.

### Resident delegation and delivery

Resident messages record:

- message ID, conversation ID, direction, idempotency key, sent time;
- transport message ID;
- burst relationship;
- voice/attachment metadata;
- bot turn link.

Resident turns record:

- triggering messages;
- start/completion and status;
- model/prompt versions;
- state-at-turn and full prompt snapshot;
- tool and reasoning results;
- final output and status message links.

Delegated-agent manifests record:

- schema, run kind, run ID, request ID, custodian;
- backend, model, reasoning effort, sandbox;
- project directory;
- supervisor/worker PIDs and start timestamps;
- task and prompt hashes;
- manifest, log, prompt, and result paths;
- persisted status, finish time, return code;
- when origin resolution succeeds, immutable Discord origin and completion-delivery attempts.

These are valuable foundations. The gaps are:

- no common correlation with initiative/chain/plan/phase/task/incident/repair;
- no heartbeat, lease expiry, process birth token, or last-progress cursor;
- status running can become stale if supervisor finalization fails;
- request ID is overloaded as both user idempotency key and origin lookup key;
- synthetic request IDs lose delivery provenance;
- no parent run or supersession link;
- no normalized terminal reason or error chain;
- no resource/capacity usage;
- no hashes for final log/result or code/environment outcome;
- turn snapshots repeatedly retain the full system prompt, tool catalog, and broad resident state, producing roughly quarter-megabyte records and widening the privacy/retention surface.

### External delivery and publication

Git commits, branch heads, PR number/state, and some CI facts appear across chain state, repair snapshots, logs, and resident state. Discord delivery appears either in delegated manifests when origin lookup works or as watchdog report prose.

There is no single effect ledger proving:

- which state transition authorized a commit/push/PR/update/message;
- the idempotency key used;
- provider attempt and response;
- whether the effect was retried;
- whether a later state superseded the message;
- whether the published commit is the commit verified by tests;
- whether completion delivery corresponds to verified completion rather than a worker’s final prose.

## Why diagnosis and failed auto-recovery escape clarity

### Competing authorities

Every reader has a plausible but partial model. Plan state, chain state, chain-health, repair-data, watchdog, incident ledger, resident manifests, and external state all have their own status vocabulary and freshness rules. The newest write is not necessarily the newest truth.

### Non-coherent reads

Readers gather process state, state.json, events, chain state, repair-data, and PR state at different moments. A process can start between reads; an atomic state rename can race an unlocked event append; a projection can be copied while half of its source set is old. No snapshot token proves all facts were observed together.

### Liveness is inferred from unrelated writes

Any recent event can make a plan progressing. State reconciliation and introspection can append events. Resident repair processes can be discovered by plan-name substring in their command line even when they are not active plan-phase workers. A stale start can be shown as in-flight even when active phase is null.

### Errors are prose, not chains

The original prerequisite failure, launcher race, provider capacity exhaustion, retry decision, new T16 correctness failure, and delivery gaps live in different files. There is no error object with cause, fingerprint, retryability, retry-after, impacted scope, and superseding event.

### Recovery decisions are implicit

The system records what was launched but not a complete decision record: evidence version, alternatives considered, policy version, retry budget, reason for same-provider retry, lease owner, next eligibility, and success predicate.

### Attempts do not have one identity

Attempt one in repair-data, a resident subagent run ID, a Megaplan execute attempt, an LLM request, a process, a Git commit, and a Discord reply all use unrelated IDs. Operators manually correlate by time and text.

### Terminality is claimed too early

partial_liveness and a live process are accepted as repair completion. Clearing latest_failure or reaching finalized is accepted as movement. Neither proves that the original condition passed, the chain advanced, the runtime contained the repair, external state matched, or the terminal response was delivered.

### Capacity is treated like correctness

Provider exhaustion consumes phase retries and iteration budget, produces error history, drives tier escalation, and can eventually look like manual review. Capacity should suspend execution until next eligibility without modifying correctness retry counters.

### Delivery is not causally coupled

An ack or final response can be stored independently of the state transition it describes. Synthetic request IDs can break origin recovery. Watchdog notification claims are not outbox receipts. A stale needs-human message can be sent after repair custody exists.

### Provenance ends at seams

North Star and plan artifacts are hashed, but the active engine checkout, editable-install commit, dirty diff, container image, profile, model route, repair source patch, target commit, test result, PR head, and delivered message are not joined into one immutable proof chain.

## Proposed tracking architecture

### 1. One canonical event envelope

Use one schema package across Megaplan, chain, cloud, watchdog, repair, resident, and delivery. Components may keep local journals, but every meaningful boundary event must use the same envelope and identity rules.

~~~json
{
  "schema": "arnold.run-event.v1",
  "event_id": "01J...ULID",
  "event_type": "provider.capacity_exhausted",
  "occurred_at": "2026-07-10T22:15:34.091522Z",
  "observed_at": "2026-07-10T22:15:34.102004Z",
  "recorded_at": "2026-07-10T22:15:34.104881Z",
  "monotonic_ns": 918233004441,
  "boot_id": "host-boot-or-container-start-id",
  "source": {
    "component": "megaplan.execute",
    "instance_id": "worker-...",
    "version": "git-sha",
    "source_seq": 317
  },
  "identity": {
    "initiative_id": "vibecomfy-trust-correctness-2026-07",
    "chain_id": "chain-61d2e7102328",
    "milestone_id": "corrective-1-verification-and-trust",
    "plan_id": "corrective-verification-and-20260710-2028",
    "phase_instance_id": "phase-execute-...",
    "task_id": "T16",
    "agent_run_id": "subagent-...",
    "provider_request_id": "provider-...",
    "incident_id": "inc-...",
    "problem_id": "problem-...",
    "repair_attempt_id": "repair-...",
    "delivery_id": null
  },
  "correlation_id": "root-inbound-or-launch-id",
  "causation_id": "event-that-directly-caused-this-event",
  "parent_event_ids": ["event-for-lease", "event-for-error"],
  "idempotency_key": "stable-effect-key",
  "actor": {
    "kind": "service",
    "name": "megaplan-auto",
    "principal_hash": "non-secret-stable-hash"
  },
  "outcome": "deferred",
  "severity": "warning",
  "error": {
    "domain": "provider",
    "code": "capacity_exhausted",
    "class": "transient_capacity",
    "message_redacted": "Codex usage limit reached",
    "retryable": true,
    "retry_after": "2026-07-10T23:05:00Z",
    "fingerprint": "sha256:...",
    "cause_event_id": "..."
  },
  "decision": {
    "policy": "capacity-retry-v2",
    "policy_version": "sha256:...",
    "action": "suspend_until",
    "retry_budget_before": 2,
    "retry_budget_after": 2,
    "reason_code": "provider_retry_after_present"
  },
  "evidence_refs": [
    {
      "kind": "provider_raw",
      "uri": "blob:sha256:...",
      "sha256": "...",
      "redaction_class": "restricted"
    }
  ],
  "provenance": {
    "engine_commit": "...",
    "target_commit": "...",
    "config_hash": "...",
    "profile_hash": "...",
    "environment_digest": "..."
  }
}
~~~

Required timestamp semantics:

- occurred_at: when the source says the event happened;
- observed_at: when Arnold observed it;
- recorded_at: when append committed;
- monotonic_ns plus boot_id: duration ordering within one process lifetime;
- source_seq: monotonic sequence per source;
- ledger_seq: assigned by the append journal.

Never use filesystem mtime as a primary event time. Record clock skew and reject impossible causal ordering rather than silently sorting by whichever timestamp is convenient.

### 2. Stable identity hierarchy and correlation rules

Define a RunIdentity object once and pass it, never infer it from paths or command text.

The correlation root is:

- inbound request ID for resident/user-triggered work;
- launch request ID for unattended scheduled/cloud work;
- deterministic migration ID for legacy adoption.

Child identities are minted at boundaries:

correlation root → initiative → chain → milestone → plan → phase instance → task attempt → agent run → provider call → effect/delivery.

Incident and problem are orthogonal:

- incident_id groups the operator-visible episode;
- problem_id identifies a stable failure fingerprint;
- repair_attempt_id identifies one recovery decision and action set.

Rules:

- request_id remains an idempotency identity and is never modified to encode purpose;
- purpose belongs in operation_name or labels;
- every child stores parent_run_id and causation event;
- every external effect uses a stable idempotency key;
- aliases and legacy IDs are recorded in identity.aliases, not substituted for canonical IDs;
- no process is treated as relevant because its command line contains a plan name.

### 3. Exclusive renewable custody leases

Before launching or mutating a target, acquire a compare-and-set lease keyed by:

target = chain_id + plan_id + problem_id + operation class.

Lease fields:

- lease_id, owner_run_id, owner_component, acquired_at, expires_at;
- renewable heartbeat and last_progress_event_id;
- process birth identity: PID plus start time/boot ID, not PID alone;
- permitted actions and workspace;
- fencing token incremented on every new owner;
- predecessor/superseded lease;
- incident and repair-attempt links.

Every mutating write carries the fencing token. Stale owners are rejected. A second repair request gets custody_conflict_detected and joins as an observer or is queued; it does not launch.

Lease health and execution health remain separate. A live repair lease does not mean the plan is progressing, but it prevents watchdog from simultaneously declaring unowned needs-human or dispatching another repair.

### 4. Canonical event taxonomy

Use namespaced past-tense events. Events say what happened, not what a consumer should infer.

| Domain | Required events |
|---|---|
| Ingress/provenance | request.received, request.accepted, provenance.captured, request.deduplicated, burst.formed |
| Custody | custody.claimed, custody.renewed, custody.transferred, custody.released, custody.expired, custody.conflict_detected, custody.fenced |
| Run lifecycle | run.created, run.launched, run.started, run.heartbeat, run.suspended, run.resumed, run.cancelled, run.failed, run.completed_claimed, run.completed_verified |
| Chain/milestone | chain.started, milestone.selected, milestone.started, milestone.blocked, milestone.completed, chain.advanced, chain.completed |
| Plan/phase/task | plan.initialized, plan.transitioned, phase.started, phase.ended, phase.failed, task.started, task.progressed, task.blocked, task.completed, task.verification_failed |
| Process | process.spawned, process.heartbeat, process.exited, process.signaled, process.orphan_detected |
| Agent/provider | agent.dispatch_requested, agent.dispatch_accepted, agent.started, provider.call_started, provider.call_heartbeat, provider.call_succeeded, provider.call_failed, provider.capacity_exhausted |
| Retry/routing | retry.decided, retry.scheduled, retry.started, retry.exhausted, route.selected, route.escalated, route.degraded |
| Evidence/artifact | artifact.written, artifact.validated, artifact.invalidated, evidence.linked, snapshot.checkpointed |
| Recovery/incident | incident.opened, problem.classified, recovery.decided, repair.started, repair.action_failed, repair.retriggered, recovery.verification_started, recovery.verified, recovery.failed, problem.recurred, incident.closed |
| Integrity/drift | projection.drift_detected, provenance.mismatch, observer.mutation_detected, state_machine.broken, resolver.low_confidence |
| Source/install | source.patch_created, source.commit_created, engine.sync_started, engine.sync_succeeded, engine.sync_failed, runtime.activated |
| Publication | git.push_attempted, git.push_succeeded, pr.opened, pr.updated, ci.started, ci.failed, ci.succeeded, merge.completed |
| Delivery | delivery.enqueued, delivery.attempted, delivery.succeeded, delivery.failed, delivery.retry_scheduled, delivery.dead_lettered, delivery.superseded |
| Capacity/cost | capacity.blocked, capacity.available, budget.reserved, budget.consumed, budget.exhausted, cost.recorded |

State-written is not a liveness event. Full state snapshots become periodic content-addressed checkpoints. Normal state changes are small deltas tied to the causal event.

### 5. Typed error and causal chains

Every failure gets:

- error_id and fingerprint;
- domain: product, state-machine, infrastructure, provider, policy, delivery, publication, integrity;
- code and normalized class;
- retryable and human_required independently;
- original cause event;
- impacted target and blocked operation;
- first_seen, last_seen, occurrence count;
- retry-after or prerequisite;
- raw evidence reference, never an unbounded copy;
- superseded_by or resolved_by event.

A new failure condition such as T16 creates a new problem_id linked to the T14 incident as caused_after or uncovered_by. It must not silently overwrite T14 or continue under its blocker fingerprint.

Capacity errors are never correctness failures. They suspend eligibility and preserve correctness retry/iteration budgets.

### 6. Explicit retry and recovery decisions

For each retry or recovery, record:

- triggering error/event;
- coherent evidence snapshot token;
- canonical state and confidence;
- policy and version;
- allowed alternatives;
- chosen action and rejected alternatives;
- attempt number by problem and by action;
- retry/iteration/cost budgets before and after;
- backoff and next eligible timestamp;
- vendor/model constraints;
- lease/fencing token;
- exact success predicate and verification deadline.

The decision engine must distinguish:

- retry same call;
- wait for capacity;
- resume a checkpoint;
- replan;
- repair target code;
- repair control-plane code;
- sync/install a repair;
- retrigger original work;
- require a human;
- stop as broken/unknown.

partial_liveness is never terminal. The only successful recovery sequence is:

repair action succeeded → runtime activated → original work retriggered → original condition no longer present → expected forward transition observed → required tests/effects verified → recovery.verified.

### 7. Multidimensional health projection

resolve_run_state should return a read-coherent projection with source versions and freshness, but not collapse independent dimensions.

~~~text
execution:    INITIALIZED | RUNNING | BLOCKED | FAILED | COMPLETED
liveness:     ACTIVE | QUIET | STALLED | UNKNOWN
custody:      UNOWNED | OWNED | CONFLICTED | EXPIRED | FENCED
recovery:     NONE | QUEUED | REPAIRING | RETRIGGERED | VERIFYING | RECOVERED | FAILED
capacity:     AVAILABLE | THROTTLED | EXHAUSTED_UNTIL | UNKNOWN
delivery:     NOT_REQUIRED | PENDING | DELIVERED | RETRYING | DEAD_LETTER
publication:  LOCAL_ONLY | PUSHED | PR_OPEN | CI_FAILED | MERGED
integrity:    COHERENT | DRIFTED | TORN_READ | PROVENANCE_MISMATCH | UNKNOWN
~~~

The projection includes:

- as_of and snapshot_token;
- source version/hash for every input;
- stale_sources and contradictions;
- confidence with explicit reasons;
- canonical next actions allowed by the state machine;
- active owners/leases;
- terminality proof or missing proof;
- no side effects.

Introspect, status, watchdog, Discord, repair, chain guards, and auditors consume the same projection. They may format it differently but cannot reclassify it.

### 8. Read-coherent snapshots and observer purity

Implement a gather transaction:

1. read journal cursors and file/inode/version tokens;
2. read process leases and active-step state;
3. read plan, artifacts, chain, repair, delivery, and external receipts;
4. re-read all version tokens;
5. accept only if unchanged, otherwise retry boundedly and return TORN_READ.

Observation commands must be pure by default:

- introspect, trace, doctor, status, and dashboard queries append nothing to run journals;
- detected drift is returned as a diagnostic result;
- a separate reconciler may append projection.drift_detected with actor=reconciler and a snapshot token;
- observer processes are excluded from target liveness by explicit run identity, not name filtering.

### 9. Immutable provenance and evidence

Store large/raw artifacts once under a content-addressed blob store. Events hold hashes and redaction class.

Terminal provenance must join:

- initiative, North Star, brief, chain spec, and config hashes;
- engine source commit and active installed/runtime digest;
- target base, dirty-diff hash, produced commit, pushed commit, PR head, merge commit;
- container/image/environment digest and tool versions;
- profile, routing-policy, vendor/model, prompt-template, and output-schema hashes;
- agent manifest, prompt hash, result hash, and log hash;
- test command, test environment, result artifact hash, and exit status;
- delivery content hash, target provenance, idempotency key, provider receipt;
- all override and human approval events.

Use segment hash chaining or Merkle checkpoints so deletion or rewriting is detectable. Sign terminal manifests where a signing key is available. GitHub is a publication sink, not ledger authority.

### 10. Delivery as an outbox, not report prose

Acceptance of an inbound request, turn creation, provenance capture, and outbox enqueue must cross one crash-safe boundary.

Every outbound acknowledgement, status notice, needs-human notice, and terminal reply has:

- delivery_id and causal event;
- immutable exact reply target;
- content hash and supersession policy;
- idempotency key;
- attempt number, provider response, provider message ID;
- next retry and dead-letter reason;
- delivered_at and receipt hash.

A synthetic operation name must never alter request identity. If a repair was launched because of message msg_x, the manifest stores request_id=msg_x and operation_name=vibecomfy-root-superfixer.

Watchdog can request a delivery, but only the outbox can claim delivered. A recovery event can supersede an undelivered needs-human notice or enqueue a correction to an already delivered notice.

### 11. Storage, retention, and redaction

Apply redaction before append, not only at display:

- never persist credentials, auth headers, environment values, OAuth bundles, raw secret-bearing commands, or unredacted provider payloads;
- allowlist event fields and attach a redaction_class;
- tokenize user/Discord identifiers in operational events; retain exact routing only in the restricted delivery store;
- store prompts/transcripts separately from operational metadata;
- scan every append for secret patterns and reject/quarantine on match;
- record redaction actions and schema version.

Suggested default retention, configurable by deployment:

| Data | Hot | Cold/terminal |
|---|---:|---:|
| Canonical event metadata and terminal manifests | 90 days | 400 days or initiative lifetime |
| Delivery receipts and idempotency records | 90 days | 400 days |
| Incident summaries and provenance hashes | 400 days | initiative lifetime |
| Raw provider/tool logs | 14 days | 30 days encrypted if incident-pinned |
| Full prompts/transcripts | 14 days | 30 days only with explicit incident hold |
| Reconstructible projections | 7 days | none; regenerate |
| State checkpoints | latest 24 hourly | 30 daily plus terminal |
| Secret-quarantined material | no normal hot access | purge after security review |

Replace repeated full resident turn snapshots and repeated 50 KB state-written events with content-addressed prompt/catalog/config snapshots plus small references.

### 12. Dashboards and reports

Provide one operator surface with drill-down:

1. **Fleet view:** canonical dimensions, owner lease, age, last meaningful progress, next eligible action, capacity, cost, delivery, publication.
2. **Run timeline:** causal DAG grouped by chain/milestone/plan/phase/task/agent/provider/effect.
3. **Incident brief:** first failure, current problem, attempts, control-plane versus target fixes, activation proof, retrigger, verification, recurrence, missing expected events.
4. **Custody view:** all leases and conflicts, process birth identity, heartbeat, fencing token, supersession.
5. **Retry/capacity view:** attempts by error fingerprint, policy decisions, retry-after adherence, budget use, provider availability.
6. **Delivery/publication view:** outbox state, provider receipts, Git/PR/CI/merge lineage, commit verified versus commit delivered.
7. **Integrity view:** projection drift, stale sources, torn reads, observer mutation, provenance gaps, schema/engine-version skew.
8. **Storage/privacy view:** bytes by event/artifact class, retention holds, redaction failures, largest duplicated snapshots.

CLI/API:

- megaplan run status --canonical;
- megaplan run explain --at EVENT_OR_TIME;
- megaplan incident brief INCIDENT;
- megaplan custody list TARGET;
- megaplan ledger verify;
- megaplan projection rebuild --compare;
- megaplan delivery status DELIVERY.

Every report names as_of, snapshot token, confidence, stale sources, and evidence cutoff.

## Invariants

The following should be machine-enforced:

1. Exactly one unexpired mutating custody lease exists per target/problem/operation class.
2. Every mutating write carries the current fencing token.
3. Every event has event_id, identity, correlation_id, occurred/observed/recorded timestamps, source sequence, actor, schema, and provenance version.
4. Every child run has one parent or an explicit root reason.
5. Every phase/task/provider start reaches a typed terminal event or a synthetic timeout/abandon event tied to lease expiry.
6. Every error produces one explicit decision: retry, defer, repair, replan, human, or stop.
7. Every retry references its error and prior attempt and records policy, budget, and eligibility.
8. Capacity deferrals do not consume correctness retry or iteration budgets.
9. New error fingerprints create or link a new problem; they do not silently replace the current problem.
10. No liveness computation uses observer writes, unrelated process substrings, or raw mtime as primary evidence.
11. Read-only observation produces no durable run events.
12. Projections are rebuildable byte-for-byte or semantically equivalently from events plus referenced evidence.
13. Legacy projection disagreement emits drift and cannot silently win.
14. partial_liveness, process alive, latest_failure cleared, finalized, commit created, and PR open are never terminal recovery proof.
15. recovery.verified is the only successful incident-closing event and requires the original success predicate.
16. run.completed_verified requires required tests, provenance, publication policy, and delivery policy.
17. Every outbound effect is idempotent and has a durable receipt or dead letter.
18. Exact reply provenance is immutable after acceptance.
19. No secret-class value can enter normal event, report, or manifest storage.
20. Event hash-chain/Merkle verification passes before a terminal manifest is trusted.

## Alerts

### Page immediately

- custody conflict for a mutating target;
- fencing rejection from a stale repair/runner;
- recovery claimed without recovery.verified;
- terminal completion with provenance gap or hash-chain failure;
- delivery to a target different from immutable origin;
- secret detected in an event or artifact;
- projection says completed while live evidence says blocked/failed;
- chain/plan mutation from an unleased actor.

### High priority

- active repair lease plus needs-human classification;
- expected verification event misses deadline;
- new problem fingerprint appears under an old blocker without linkage;
- provider retry occurs before retry_after;
- more than two same-fingerprint retries without new evidence;
- phase start has no terminal after lease expiry;
- observer mutation detected;
- read-coherent snapshot cannot be obtained;
- repair fix committed but not activated/retriggered;
- delivered completion refers to a commit different from verified/published commit.

### Warning/trend

- state-written/checkpoint volume exceeds budget;
- raw log/transcript retention exceeds policy;
- resolver low confidence;
- clock skew exceeds threshold;
- projection lag exceeds one watchdog tick;
- cost trajectory exceeds plan envelope;
- delivery retry or dead letter;
- engine/tree/profile provenance differs across runner and repairer.

## Acceptance tests

### VibeComfy golden replay

Create a redacted fixture containing the relevant marker, state, events, chain state, repair attempts, incident events, resident manifests, watchdog report, and external receipts. Replaying it must:

1. classify the first T14 failure as a real implementation/prerequisite block;
2. open one incident and one T14 problem;
3. record the mechanical-launch race as repair.action_failed, not target failure;
4. keep Kimi’s live-process observation as liveness evidence only;
5. refuse recovery verification until T14 passes and the chain advances;
6. classify 26 usage responses as one capacity interval and schedule at most one eligible retry;
7. preserve correctness retry budgets during capacity suspension;
8. close or supersede all unmatched provider calls with typed capacity failures;
9. create a new linked problem for T16;
10. recognize the first resident repair lease and block/queue the second;
11. show execution BLOCKED, custody OWNED/CONFLICTED, and recovery REPAIRING without saying generic progressing or needs human;
12. require a delivery outbox receipt for any needs-human or completion notice;
13. reach RECOVERED only after retrigger, original predicate, chain advancement, provenance, and required external effects verify.

### Core contract tests

- **Observer purity:** hash all run artifacts, run introspect/trace/doctor/status repeatedly, and assert no hashes, mtimes, event counts, or state versions change.
- **Read coherence:** mutate state/events/chain concurrently and prove the resolver returns one coherent version or TORN_READ, never a mixed projection.
- **Lease race:** launch 100 concurrent repair claims; exactly one receives a fencing token.
- **Lease death:** kill owner after side effect but before receipt; replacement replays safely with the same idempotency key.
- **PID reuse:** a new process with the old PID but different birth identity cannot inherit custody.
- **Provider terminality:** crash/timeout/capacity/error paths all close provider.call_started.
- **Capacity policy:** retry-after is honored; no iteration budget is consumed; availability resumes once.
- **Retry storm breaker:** repeated identical failures without new evidence stop and escalate deterministically.
- **Error lineage:** a later different blocker opens a new problem linked to the earlier incident.
- **Recovery verification:** liveness, commit, install, retrigger, and original success predicate are separately required.
- **Projection replay:** delete every projection and rebuild equivalent status, incident, custody, cost, and delivery views.
- **Projection drift:** corrupt a projection and assert deterministic drift emission by the reconciler, not the reader.
- **Resident idempotency:** duplicate inbound and duplicate launch converge on one logical run/effect.
- **Origin preservation:** operation labels cannot alter request/reply identity.
- **Delivery crash matrix:** crash before enqueue, after enqueue, during send, after provider success, and before receipt persist; exactly one visible effect results.
- **Publication lineage:** tests on commit A cannot verify completion delivered for commit B.
- **Schema evolution:** old events replay under upcasters; unknown required fields fail closed.
- **Clock skew:** causal ordering remains correct with skewed wall clocks using source sequence and monotonic time.
- **Redaction:** seeded secrets across prompts, commands, provider payloads, Git URLs, and errors never enter normal storage.
- **Retention:** expired raw data is purged while terminal hashes, receipts, and replayability remain.
- **Tamper detection:** edit/delete/reorder an event or blob and ledger verification fails.
- **Scale:** one million small events and thousands of concurrent runs remain queryable without copying full state into every event.

## Prioritized rollout

This should amend the existing custody-control-plane milestones, not create a new initiative.

### P0: stop misleading and duplicate behavior

Implement immediately, behind conservative flags where necessary:

1. Make introspect, trace, doctor, and status provably read-only.
2. Exclude observer and resident processes from phase liveness unless their explicit RunIdentity says they own that phase.
3. Add typed provider.call_failed/provider.capacity_exhausted terminals and honor retry_after.
4. Separate capacity budget from correctness iteration/retry budget.
5. Add a compare-and-set repair lease and fencing token keyed by target/problem.
6. Require every resident repair launch to carry session, plan, incident, problem, and repair-attempt identities.
7. Preserve exact inbound request ID; move labels to operation_name.
8. Stop treating partial_liveness as completed repair; require verification pending.
9. Add a retry-storm breaker and alert after two identical no-new-evidence attempts.
10. Cap/remove full state copies from new events; checkpoint by hash.

Exit gate: the VibeComfy fixture cannot launch duplicate repair, cannot say progressing from an observer event, and cannot retry a capacity error 26 times.

### M1 extension: resolver, event envelope, coherent evidence, fixtures

Build on the existing M1 brief:

- canonical RunIdentity and event-envelope package;
- pure read-coherent resolver with multidimensional health;
- evidence refs and snapshot tokens;
- event adapters for legacy plan, chain, repair, incident, and resident data;
- VibeComfy golden replay plus all existing July fixtures;
- projection replay and observer-purity tests.

Exit gate: every fixture yields the expected multidimensional projection and names contradictions/stale sources.

### M2 extension: status, dispatch, resident, and delivery integration

Build on M2:

- status and all repair dispatches accept only canonical snapshots;
- resident launch requires canonical identity and lease;
- incident events include detection, decision, dispatch, action, and expected verification;
- durable delivery outbox replaces report-prose claims;
- drift is emitted by a reconciler with source snapshot token;
- legacy fields become projections and show stale status.

Exit gate: Discord, CLI, watchdog, and repair prompts show the same as_of state; synthetic labels cannot lose reply provenance.

### M3 extension: watchdog, chain guards, recovery proof, and capacity

Build on M3:

- watchdog and chain guards enforce fencing and canonical next actions;
- verify_retrigger_success becomes the only recovery-success writer;
- capacity suspension/resumption and retry budget semantics are enforced;
- activation provenance proves the fix reached the actual engine/target runtime;
- effect receipts join Git/PR/CI and delivery to the verified commit;
- stale owners and duplicate repairs are fenced.

Exit gate: a repair cannot close while original work remains blocked, and capacity cannot become manual-review correctness failure.

### M4 extension: audit, dashboards, retention, and tamper evidence

Build on M4:

- L3 reconciles event ledger, leases, resolver, projections, repair proof, engine freshness, PR/CI, and delivery;
- audit-the-auditor catches a lying resolver or false recovery;
- fleet/run/incident/custody/capacity/delivery/integrity dashboards;
- retention, legal/incident holds, append-time redaction, and secret scanning;
- hash-chained segments/Merkle checkpoints and terminal manifest verification;
- remove or freeze legacy repair-data and duplicated full turn/state snapshots after parity.

Exit gate: deleting projections and rebuilding produces the same operator truth; tampering and provenance gaps fail closed.

### Migration sequence

1. Dual-write canonical events while leaving current projections untouched.
2. Measure completeness and compare canonical versus legacy decisions.
3. Enforce observer purity and repair leases first because they prevent active harm.
4. Switch status/Discord to canonical projection in observe mode.
5. Switch repair dispatch and watchdog to enforcement mode.
6. Make incident/recovery and delivery terminality canonical.
7. Rebuild dashboards from the ledger.
8. Compact legacy data into content-addressed evidence, retain hashes, and retire write paths.
9. Remove legacy classifiers only after a full retention window with zero unexplained drift.

## Concrete VibeComfy closeout criteria

Do not call the current VibeComfy incident recovered until one canonical brief proves:

- exactly one valid custody lease or an orderly transfer history;
- the current target/problem identity, including the T14-to-T16 transition;
- no stale provider call considered active;
- capacity interval closed without hidden budget damage;
- the launcher/control-plane fix is committed, activated in the actual runtime, and linked to its repair event;
- the target fixes are committed and the workspace/dirty diff is fully accounted for;
- T16 and all required acceptance checks pass with sanitized artifacts;
- the chain advances beyond milestone zero or reaches its declared terminal policy;
- branch, pushed commit, PR head, CI, and merge state refer to the verified commit;
- any needs-human notice and final reply have durable outbox receipts and correct immutable origin;
- recovery.verified and, later, run.completed_verified are present;
- the incident ledger’s next expected events are all fulfilled or explicitly cancelled with reason.

Until then, the honest status is **repair active / recovery unverified**, even if a worker is live, state is finalized, latest_failure is null, or a commit exists.

## Final assessment

Megaplan already has many of the hard primitives: append-only journals, hashes, structured state, manifests, repair signatures, watchdog snapshots, an incident schema, idempotency keys, and delivery fields. The failure is architectural composition. The primitives are not joined by one identity system, one causal event envelope, one custody lease, one read-coherent resolver, and one terminal proof contract.

VibeComfy is therefore not merely an isolated stalled plan. It is a high-quality regression corpus for the custody-control-plane initiative. If the proposed P0 invariants and the VibeComfy golden replay are implemented first, the system will stop creating the most dangerous ambiguity—multiple active repairers, false liveness, retry storms, stale human escalation, and unverified repair completion—while the broader ledger, provenance, dashboards, retention, and audit layers roll out through the initiative’s existing M1–M4 plan.
