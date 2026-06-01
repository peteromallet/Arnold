# M2a: Capability Operations, Run Envelope, And Stepwise Driver Contract

## Outcome

Design and land the neutral contracts that let Arnold dispatch plugin-owned operations without knowing Megaplan policy. This milestone freezes the operation carriers, runtime-owned run envelope, and stepwise/checkpointed driver seam before consumers migrate onto them.

## Scope

In:
- Define optional plugin operation registry/carriers for run phase, status/control projection, resume, override list/apply, and profile validation.
- Define runtime-owned run envelope fields required before plugin dispatch: plugin identity, manifest hash, envelope schema version, plugin state schema version, run id, artifact root, resume cursor, trust/quarantine state, and creation time.
- Define where neutral runtime settings live relative to the run envelope and operation requests. Per-run and per-stage wall timeout, idle timeout, heartbeat interval, poll cadence, deadline, cancellation, retry budget envelope, max workers, isolation, and cost caps must be Arnold carriers; Megaplan may supply defaults and policy interpretation for its phases.
- Define the stepwise/checkpointed execution driver seam: Arnold owns advance/checkpoint/resume/isolation mechanics; Megaplan owns phase policy and argument translation.
- Keep operation request/result types neutral: no Megaplan phase names, robustness levels, gate labels, override meanings, profile semantics, or artifact conventions.
- Document the contract well enough that M2b can migrate auto/resume/control/CLI consumers onto it.

Out:
- Do not rewire all consumers yet.
- Do not physically move the Megaplan plugin.
- Do not build a plugin VM, package manager, remote registry, or signing system.

## Locked Decisions

- Simple plugins do not implement operations; empty operations means `arnold run` uses the generic graph executor.
- Complex plugins implement only the operations they need.
- Run/phase/auto/resume/status/control behavior is not a method on the graph dataclass.
- Plugin-owned vocabularies remain opaque strings to Arnold.
- Every supported operation/runtime setting must have an effective value or an explicit unset/unsupported state. Defaults may come from Arnold, plugin defaults, profiles, pipeline/run config, or invocation overrides, but validation and dry-run output must be able to explain the final source.

## Required Outputs

- Exact module placement for operation carrier types.
- Exact module placement, precedence, and scoping rules for runtime settings: Arnold defaults < plugin defaults < profile settings < run/CLI overrides < intentionally supported env overrides; run defaults inherit into stages; stage settings override named stages; child-operation settings apply inside panels, fanouts, batches, and subpipelines where supported.
- Status/control operation shape: one operation or a small operation family, decided and documented as part of the carrier contract.
- The stepwise driver contract owns selection of in-process versus subprocess isolation mode. Concrete subprocess launch/supervision may land later, but the carrier declaring isolation choice lives in M2a.
- Which cross-cutting settings are in scope for M2a carriers versus later milestones: identity/discovery, model/profile routing, prompt/context, artifact/dataflow, control/resume, recovery/failure, resource/security, isolation/environment, observability/audit, and composition/subpipeline policy.
- Define the legacy-to-M2a resume migration contract: a persisted run without a runtime-owned envelope must be upgradable through an explicit tested path. The first migrated resume may handle manifest-hash mismatch; subsequent resumes use the new identity and hash.

## Constraints

- This is the keystone schema/interface milestone; keep the diff focused on contracts and the smallest proof harness.
- Do not leak Megaplan state or phase names into Arnold types.
- Keep the surface minimal; do not manufacture non-Megaplan override/status features just to prove the abstraction.

## Done Criteria

- Neutral operation carrier types exist and are documented.
- Runtime-owned run envelope type/schema exists and is documented.
- Runtime settings carriers are documented separately from opaque plugin state. Validation covers unknown stage keys, impossible timeout pairs, unsupported isolation modes, invalid worker caps, and settings declared for stages the pipeline does not expose.
- `--dry-run` output reports the effective value of every supported runtime setting and the source of that value.
- Settings categories are explicit: inheritable settings, globally aggregated/enforced settings, stage-local settings, and plugin-owned meanings are not conflated.
- Defaults and unsupported states are explicit; no operation carrier relies on hidden Megaplan-specific fallback behavior.
- Stepwise driver seam is documented and represented in code enough for M2b to consume.
- Simple graph execution still works without plugin operations.
- Boundary tests prove generic operation carriers do not import Megaplan policy or contain Megaplan literals.
- M2b has a clear migration checklist for auto, resume, control, CLI, and profile dispatch.

## Touchpoints

- `arnold/pipeline/`
- `arnold/runtime/`
- `megaplan/_pipeline/types.py`
- `megaplan/drivers/`
- `megaplan/auto.py`
- `megaplan/control_interface.py`
- `megaplan/_core/workflow.py`

## Anti-Scope

- Do not move stage implementations.
- Do not rename the package.
- Do not rework authoring API.
