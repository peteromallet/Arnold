# M4: Supervisor Extraction

## Outcome

Cross-run orchestration primitives become generic Arnold supervisor concepts. Megaplan chain policy remains a domain adapter.

## Scope

In scope:

- Add `arnold.supervisor` for generic run node, dependency, lifecycle, ladder, checkpoint, and outcome carriers where they are truly generic.
- Move or mirror generic pieces from `arnold/pipelines/megaplan/supervisor/*`.
- Keep Megaplan chain YAML parsing, Git/PR lifecycle, profile/robustness policy, completion contract policy, and ticket linkage in Megaplan.
- Add adapters from Megaplan chain/supervisor objects to generic supervisor carriers.
- Add tests proving generic supervisor modules contain no profile/robustness/Git/PR hardcoding.

Out of scope:

- Moving chain spec format to Arnold.
- Changing chain failure semantics.
- Changing merge policy.

## Locked Decisions

- Generic supervisor owns dependency/lifecycle mechanics.
- Megaplan owns orchestration policy and repository workflow.

## Done Criteria

- Existing supervisor and chain runner tests pass.
- New `arnold.supervisor` tests pass.
- Chain behavior remains equivalent through the adapter.
- Generic supervisor boundary tests prevent Megaplan policy leakage.
