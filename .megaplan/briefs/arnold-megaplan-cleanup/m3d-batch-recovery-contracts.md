# M3d: Batch Runtime And Recovery Classifier Contracts

## Outcome

Split generic batch/runtime mechanics and recovery classification seams from Megaplan's execution, review, retry, and escalation policy.

## Scope

In:
- Split generic batch execution mechanics from Megaplan execution policy.
- Identify reusable command/agent batch envelopes, timeout handling, aggregation hooks, and result carriers.
- Thread neutral runtime settings through drivers and batch envelopes where needed: wall timeout, idle timeout, deadline, cancellation, heartbeat interval, retry budget envelope, max workers, isolation, and cost caps.
- Define a neutral recovery classifier interface only where policy-free.
- Keep Megaplan retry/escalation defaults, blocked-task recovery, destructive confirmation, review coupling, evidence checks, and task complexity semantics in the plugin.

Out:
- Do not move execute/review/orchestration policy yet; that is M5b.
- Do not generalize Megaplan robustness or auto retry policy into Arnold.
- Do not build a universal workflow state machine.

## Locked Decisions

- Arnold owns batch mechanics only where they are policy-free.
- Megaplan owns execution policy meanings and recovery defaults.
- Recovery classifier must carry plugin-owned retry/escalation vocabularies as opaque values.
- Timeout supervision is generic mechanics, but timeout recovery meaning, retry escalation, blocked-task handling, and phase-specific thresholds remain Megaplan policy.
- Generic batch envelopes and recovery classifiers must not contain hidden Megaplan fallback behavior. If no plugin recovery policy is registered, report unset/unsupported rather than applying Megaplan defaults.

## Runtime Settings Discipline

Batch envelopes and recovery classifier inputs use neutral runtime settings. Each supported setting must have declaration, inheritance, override path, owner of meaning, effective value or explicit unset/unsupported state, validation, and dry-run source reporting.

## Required Outputs

- Which current `execute/`, `review/`, and `orchestration/` modules are truly reusable mechanics per M-1.
- Timeout-supervision placement across drivers and batch runtime, documented as a contract rather than left implicit.
- How `RecoveryPolicy.classify(error, context) -> RecoveryDecision` receives neutral runtime settings, carries plugin-owned retry/escalation vocabularies as opaque values, and reports unset/unsupported when no plugin policy is registered.

## Constraints

- Preserve execute policy details in later plugin move: destructive confirmation, review-mode approval, blocked lifecycle, retry-blocked-tasks, batch transitions, timeout checkpoint recovery, evidence attribution, and tier selection.
- Preserve review policy details in later plugin move.

## Done Criteria

- Generic batch runtime contract exists where justified by current code.
- Batch/driver timeout handling reads neutral runtime settings and reports neutral timeout/idle/deadline outcomes.
- Megaplan execute/review policy remains plugin-owned.
- Recovery classifier seam exists only where policy-free and tested.
- Future M5b has a clear map for moving execute/review/orchestration policy into the plugin.

## Touchpoints

- `megaplan/execute/`
- `megaplan/review/`
- `megaplan/orchestration/`
- `megaplan/drivers/`
- `arnold/runtime/`
- `arnold/pipeline/`

## Anti-Scope

- Do not change public authoring API.
- Do not move policy modules yet.
