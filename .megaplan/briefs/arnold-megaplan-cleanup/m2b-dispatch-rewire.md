# M2b: Rewire Privileged Dispatch Onto Capability Operations

## Outcome

Remove hardcoded `planning` dispatch from auto, control/status, resume, override, profile validation, and Arnold CLI paths by routing them through the M2a operation/run-envelope seam.

## Scope

In:
- Migrate `megaplan/auto.py` away from `PipelineRegistry().get("planning")`.
- Migrate `megaplan/control_interface.py` away from default `binding="planning"` and privileged planning imports.
- Migrate `megaplan/cli/arnold.py` to discover operation support and override catalogs from the target plugin.
- Migrate `_core/workflow.py` resume routing to read the runtime-owned envelope before plugin dispatch.
- Ensure `read_valid_targets()` and similar control APIs do not silently default `binding="planning"`.
- Ensure legacy `planning` aliases route through explicit migration behavior, not generic defaults.
- Preserve phase arg behavior for resume of execute, including destructive confirmation, user-approved flag, and batch index.

Out:
- Do not physically move the plugin to `arnold/pipelines/megaplan/` unless the registry scans `arnold.pipelines`, `SKILL.md` and prompt/profile resources resolve there, pipeline-local profiles load there, and legacy `planning` aliases route through the runtime-owned envelope/migration path rather than generic defaults.
- Do not change Megaplan auto policy semantics.
- Do not generalize Megaplan retry/escalation behavior into Arnold.

## Locked Decisions

- Arnold may provide polling/driver/checkpoint helpers only where policy-free.
- Megaplan owns phase ordering, retry classification, escalation, stall policy, cost policy, and phase argument translation.
- Override action meanings remain plugin-owned.

## Required Outputs

- Physical-move disposition for this sprint: complete the move only if all explicit discovery/resource/profile/alias preconditions are proven; otherwise document the blocked preconditions and leave the move to M3a/M4.
- Exact compatibility behavior for existing persisted plans with manifest hash mismatch.

## Constraints

- Preserve auto liveness/orphan handling, stale phase-result behavior, review rework loops, override fallback, strict-note guardrails, resume rollback, and status projection.
- Do not silently accept missing plugin identity for new runs.
- Keep chain/cloud/bakeoff product behavior working or explicitly parked by tests.

## Done Criteria

- Auto resolves plugin run/phase operations by plugin identity, not `planning`.
- Control/status resolves plugin-provided control binding.
- CLI operation verbs dispatch only when the plugin advertises the operation.
- Override action lists come from plugin override catalog.
- Resume refuses missing identity for new runs and migrates captured legacy `planning` runs.
- The first migrated resume handles manifest-hash mismatch explicitly; subsequent resumes use the new identity and hash.
- Dispatch passes M2a runtime-settings carriers through neutrally and does not synthesize Megaplan-specific defaults.
- Parity smoke tests cover the operational behaviors listed in the M-1 parity gate list.

## Touchpoints

- `megaplan/auto.py`
- `megaplan/control_interface.py`
- `megaplan/cli/arnold.py`
- `megaplan/_core/workflow.py`
- `megaplan/_pipeline/registry.py`
- `tests/test_auto.py`
- `tests/test_control_interface.py`
- resume tests

## Anti-Scope

- Do not move prompts/stages/state.
- Do not rename the package.
- Do not add new product features.
