# M1: Neutral Outcome And Control Extraction

## Outcome

Generic run outcome and control carrier vocabulary no longer belongs to Megaplan. The lowest-risk proof is moving neutral outcome types while preserving old imports.

## Scope

In scope:

- Add `arnold/runtime/outcome.py` or `arnold/control/outcome.py` for neutral outcome vocabulary.
- Move or mirror `RunOutcome` and `RunResultMetadata` out of `arnold/pipelines/megaplan/run_outcome.py`.
- Keep `arnold/pipelines/megaplan/run_outcome.py` as a compatibility re-export plus Megaplan-specific adapters only.
- Split neutral control carriers from Megaplan bridge functions in `arnold/pipelines/megaplan/control_interface.py` where safe.
- Update internal imports gradually toward the neutral module.
- Add tests proving neutral outcome/control modules import no Megaplan code.

Out of scope:

- Changing run outcome semantics.
- Moving planning-state mappings into generic Arnold.
- Moving Git/PR/merge policy.

## Locked Decisions

- Neutral modules may define generic status/result carriers.
- Megaplan-specific state names, phase policy, and bridge functions stay in `arnold.pipelines.megaplan`.
- Old public imports must continue to work until a later shim-deletion milestone.

## Done Criteria

- Existing control/run outcome tests pass.
- New boundary tests prove neutral outcome/control modules are Megaplan-free.
- Old Megaplan import paths remain compatible.
- Internal code prefers the neutral import where it is clearly generic.
