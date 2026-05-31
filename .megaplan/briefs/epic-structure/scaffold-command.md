# Epic Structure Scaffolding

## Outcome

Define and implement the default structure for megaplan epics, then provide a CLI scaffolder that creates that structure for new chain-driven epics.

The result should make it obvious where to put the chain spec, milestone briefs, the overall epic/vision document, generated plan artifacts, archive/status files, and the directory that houses the whole epic.

## Scope

In scope:

- Add a canonical "Recommended epic layout" section to `docs/megaplan-epic.md` and the generated `megaplan-epic` skill sources.
- Add a scaffolding command, preferably under the chain namespace: `megaplan chain init <slug>`.
- Make the default scaffold a committed design-record layout:

```text
docs/megaplan/epics/<slug>/
  EPIC.md
  chain.yaml
  m1-<name>.md
  m2-<name>.md
  status.md
  artifacts/
```

- Ensure `chain.yaml` references the generated milestone brief paths.
- Provide useful fill-in templates for `EPIC.md`, milestone briefs, and `status.md`.
- Add focused tests for the CLI scaffolder and generated file contents.
- Update any help text or skill docs that tell agents how to start a new epic.

Out of scope:

- Do not introduce a new persistent "epic object" just to run a chain.
- Do not rename or repurpose the existing `megaplan epic` data-admin namespace.
- Do not change chain execution state semantics.
- Do not automate archive/status updates unless it is already a small existing helper; file a follow-up ticket if needed.

## Locked Decisions

- Use `megaplan chain init`, not `megaplan epic create`. The `megaplan epic` namespace is already documented as data-admin tooling for editorial epic records, so new chain-orchestration scaffolding belongs under `megaplan chain`.
- The canonical default layout is `docs/megaplan/epics/<slug>/`.
- Treat this as a design-record layout intended to live in version control.
- Keep `.megaplan/plans/.chains/...` as harness state, separate from user-authored epic structure.
- Document an alternate operator/scratch layout only as a secondary pattern, not the default.
- `EPIC.md` is a human-facing overview, not a load-bearing harness input.
- The harness consumes `chain.yaml` and each milestone `idea:` path; everything else is convention for humans and agents.

## Open Questions

- What exact flags should `megaplan chain init` expose for initial milestone creation? A minimal version can accept `--milestone` repeatedly, or create one starter `m1-foundation.md` brief when no milestones are supplied.
- Should the scaffolder refuse to overwrite an existing epic directory by default? Prefer yes, with an explicit force flag only if the repo already has such patterns.
- Should generated `chain.yaml` use relative paths from the spec location or repo-root-relative paths? Prefer the convention already accepted by current chain loading; choose the least surprising option and cover it in tests.

## Constraints

- Preserve current chain execution behavior.
- Keep changes scoped to docs, CLI scaffolding, templates, and tests.
- Follow existing repo patterns for argparse command structure, YAML writing, path handling, and tests.
- Generated files should be deterministic and ASCII.
- Avoid creating nested cards or unrelated frontend changes; this is CLI/docs work only.

## Done Criteria

- `megaplan chain init <slug>` creates the default epic directory and files.
- Generated `chain.yaml` is valid YAML and points at the generated milestone brief files.
- `megaplan chain start --spec docs/megaplan/epics/<slug>/chain.yaml` can use the generated spec after the user fills the briefs.
- `docs/megaplan-epic.md` clearly explains default layout, optional `EPIC.md`, operator/scratch layout, and what is load-bearing.
- The Codex/Claude distributed skill text is updated consistently with docs.
- Tests cover successful scaffold creation, overwrite refusal, slug validation or normalization, and milestone path generation.

## Touchpoints

- `docs/megaplan-epic.md`
- `megaplan/data/epic_skill.md`
- `megaplan/data/_codex_skills/megaplan-epic/SKILL.md`
- `megaplan/cli.py`
- Chain command handling modules, if already split out
- Existing chain tests and CLI tests

## Anti-Scope

- Do not reorganize the whole CLI.
- Do not implement the broader `megaplan/` package structure cleanup ticket.
- Do not make this an epic unless implementation reveals the scope is much larger than expected.
- Do not add cloud-specific behavior in this sprint.

## Related Ticket

`01KS0MFGXA5JCM7Z91HZ0XEQJE` — `megaplan-epic skill doesn't prescribe a layout for epic artifacts (chain.yaml, briefs, vision doc)`
