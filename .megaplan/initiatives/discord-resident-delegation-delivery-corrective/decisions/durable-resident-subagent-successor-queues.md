# Durable Resident Subagent Successor Queues

## Decision

Queued resident successors are part of the existing resident-managed run custody surface. A successor is committed as an `arnold-managed-agent-run-v2` manifest with an `arnold-resident-subagent-queue-v1` dependency block before it is eligible to launch. No parallel queue database or unbounded prompt handoff is introduced.

The supported trigger policy is `on_predecessor_success`. A queue may declare either the legacy singular `predecessor_run_id` or the canonical ordered `predecessor_run_ids` set. Eligibility requires every distinct predecessor to have durable terminal state `completed`, zero return code, compatible terminal outcome, and a present nonempty regular result file. PID, path existence alone, acknowledgement, provider-session acceptance, or partial fan-in completion is not completion evidence.

The launch API retains `depends_on_run_id` for existing callers and adds `depends_on_run_ids` for fan-in (maximum eight). Supplying both fields, an empty plural list, duplicates, malformed IDs, missing runs, or inconsistent committed singular/plural fields is rejected deterministically. Declared order is durable: the first predecessor is the primary lineage/routing parent, and the first declared terminal violation determines failure/control-status propagation. All predecessors must share project, immutable launch provenance, resolved work intent, and—within a same-request fan-in—logical aggregation custody.

Each successor:

- inherits the predecessor set's normalized launch provenance, project directory, resolved work intent, query relationship, and logical aggregation key; the first declared predecessor supplies the compatible singular lineage/model-route fields;
- becomes the one `synthesis_delivery_owner`, while earlier runs become internal contributors and lose pending Discord delivery ownership;
- carries three typed `arnold-resident-subagent-reference-v1` path references per predecessor—manifest, result, and log—plus the bounded authored prompt and concise description;
- cannot change source message, Discord reply target, project/effect authorization, or aggregation custody;
- is cycle/depth checked at creation and again before launch.

## Terminal and recovery policy

- Every predecessor succeeding with a valid result launches the successor exactly once; any partial completion remains queued.
- Any predecessor failure/interruption or missing/empty/invalid result terminalizes the successor as failed closed.
- Any predecessor cancellation or supersession propagates the same control-terminal state.
- Successor launch failures use bounded exponential retry and then fail closed when the committed attempt budget is exhausted.
- Per-successor transition locks serialize concurrent observers. A manifest-bound execution lock prevents two supervisors from executing the same run. Startup, terminalization, and delivery sweeps all reconcile the same durable manifests, so precommitted work survives process restart.
- A newer queued synthesis owner supersedes older pending delivery owners; superseded queues cannot regain delivery authority.

## Bounded visibility

Resident hot context exposes at most eight queued rows. Each row contains the complete bounded predecessor ID set and per-predecessor status, result state, actionable attention, dependency state, concise description, attempt counters, and next retry time. It omits predecessor artifact contents and full manifests/logs. Manifests retain all typed predecessor references, and the `agents/queued` context route plus `resident inspect-subagent-queue` CLI provide bounded inspection.

## Raw evidence

Originating delegated-run artifacts:

- manifest: `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260715-200647-1a4ba0b5/manifest.json`
- streaming log: `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260715-200647-1a4ba0b5/run.log`
- delegated result: `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260715-200647-1a4ba0b5/result.md`
- git custody receipt: `/workspace/arnold/.megaplan/plans/resident-subagents/subagent-20260715-200647-1a4ba0b5/git-custody-evidence.json`

Verification is recorded in the custody receipt. The focused executable evidence is `tests/resident/test_subagent_queue.py`; broader resident lifecycle coverage includes launch, provenance, aggregation/delivery, context-tree, and Discord adapter suites.

## Activation boundary

Source integration alone does not activate the running Discord resident. Loading this contract in production still requires the separately authorized resident restart/activation procedure; this decision does not authorize that restart.
