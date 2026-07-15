# Durable Resident Subagent Successor Queues

## Decision

Queued resident successors are part of the existing resident-managed run custody surface. A successor is committed as an `arnold-managed-agent-run-v2` manifest with an `arnold-resident-subagent-queue-v1` dependency block before it is eligible to launch. No parallel queue database or unbounded prompt handoff is introduced.

The supported trigger policy is `on_predecessor_success`. Eligibility requires durable predecessor terminal state `completed`, zero return code, compatible terminal outcome, and a present nonempty regular result file. PID, path existence alone, acknowledgement, or provider-session acceptance is not completion evidence.

Each successor:

- inherits the predecessor's normalized launch provenance, project directory, resolved work intent, query relationship, model route, and logical aggregation key;
- becomes the one `synthesis_delivery_owner`, while earlier runs become internal contributors and lose pending Discord delivery ownership;
- carries only three typed `arnold-resident-subagent-reference-v1` path references—manifest, result, and log—plus the bounded authored prompt and concise description;
- cannot change source message, Discord reply target, project/effect authorization, or aggregation custody;
- is cycle/depth checked at creation and again before launch.

## Terminal and recovery policy

- Predecessor success with a valid result launches the successor.
- Predecessor failure/interruption or missing/empty/invalid result terminalizes the successor as failed closed.
- Predecessor cancellation or supersession propagates the same control-terminal state.
- Successor launch failures use bounded exponential retry and then fail closed when the committed attempt budget is exhausted.
- Per-successor transition locks serialize concurrent observers. A manifest-bound execution lock prevents two supervisors from executing the same run. Startup, terminalization, and delivery sweeps all reconcile the same durable manifests, so precommitted work survives process restart.
- A newer queued synthesis owner supersedes older pending delivery owners; superseded queues cannot regain delivery authority.

## Bounded visibility

Resident hot context exposes at most eight queued rows. Each row contains run IDs, predecessor ID/status, dependency state, concise description, attempt counters, next retry time, and actionable attention. It omits predecessor artifact contents and full manifests/logs. The `agents/queued` context route and `resident inspect-subagent-queue` CLI provide bounded inspection.

## Raw evidence

Originating delegated-run artifacts:

- manifest: `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260715-200647-1a4ba0b5/manifest.json`
- streaming log: `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260715-200647-1a4ba0b5/run.log`
- delegated result: `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260715-200647-1a4ba0b5/result.md`
- git custody receipt: `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260715-200647-1a4ba0b5/git-custody-evidence.json`

Verification is recorded in the custody receipt. The focused executable evidence is `tests/resident/test_subagent_queue.py`; broader resident lifecycle coverage includes launch, provenance, aggregation/delivery, context-tree, and Discord adapter suites.

## Activation boundary

Source integration alone does not activate the running Discord resident. Loading this contract in production still requires the separately authorized resident restart/activation procedure; this decision does not authorize that restart.
