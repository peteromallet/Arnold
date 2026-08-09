---
type: brief
slug: m5-adoption-conformance
title: Repository Adoption and Conformance
epic: repository-strategy-roadmap
created_at: '2026-07-13T21:35:51.655386+00:00'
---

# Repository Adoption and Conformance

## Outcome

Adopt the finished contract in Arnold with a useful initial strategy, complete
documentation and conformance coverage, and prove the full ticket-to-roadmap-to-
epic lifecycle. The shipped result is understandable to humans, reliable for
automation, and contains no competing roadmap authority.

## Scope

### In scope

- Create Arnold's initial `.megaplan/STRATEGY.md` with stable direction and a
  deliberately small Now / Next / Later set of real ticket/epic references,
  chosen from current canonical artifacts without copying their status/bodies.
- Add author/operator documentation, a template, lifecycle examples, authority
  rules, projection rebuild instructions, and troubleshooting guidance.
- Update relevant Megaplan skill/help text so agents search initiatives before
  promotion and distinguish roadmap visibility from the full ticket backlog.
- Run end-to-end and adversarial conformance: direct Markdown edit, CLI edit,
  projection deletion/rebuild, ticket outside roadmap, ticket inclusion and
  horizon movement, promotion with retained history, epic completion link,
  malformed refs, stale display title, and mixed-version recovery.
- Add repository checks/CI lint that validate adopted strategy without requiring
  generated JSON to be committed unless a documented consumer needs it.
- Audit all new code/docs for a single authority line and remove temporary
  bridges no longer justified.

### Out of scope

- Curating every open Arnold ticket into the roadmap, changing existing epic
  execution order, or launching additional product epics.
- A global dashboard, web UI, or organization-wide strategy service.

## Locked Decisions

- Arnold adoption demonstrates the same contract intended for every repo; no
  Arnold-only hidden schema.
- The initial roadmap is selective and references only real ticket/epic IDs.
- Current status stays in ticket/initiative/run artifacts and is rendered by
  lookup, never copied into strategy.
- JSON remains rebuildable and disposable.

## Open Questions for This Sprint

- Select the smallest honest set of current Arnold roadmap references after
  checking artifact existence and avoiding claims about volatile execution
  status.
- Decide whether CI checks only Markdown/reference validity or also verifies a
  clean regenerated projection when that projection is committed.
- Identify and retire any compatibility bridge whose continued existence would
  create two ways to express the same authoritative relationship.

## Constraints

- Do not disturb unrelated dirty work or mutate active chain/run state.
- Documentation examples must use valid, non-secret identifiers and clearly
  distinguish illustrative from live references.
- Validation must be fast enough for ordinary pre-commit/CI use and produce
  actionable diagnostics.
- This sprint is sized to at most two weeks.

## Done Criteria

- Arnold has a validated, human-readable `.megaplan/STRATEGY.md` with no copied
  ticket/epic bodies or statuses and only resolvable `type + ref` identities.
- Deleting and rebuilding all generated strategy projections succeeds and does
  not alter Markdown or referenced artifacts.
- The documented ticket-to-epic lifecycle passes end-to-end with two retained
  identities and explicit supersedes/resolves evidence.
- Focused unit, contract, CLI, migration, and end-to-end suites pass; parser/help
  snapshots are current; lint/CI integration is proven.
- A final authority audit finds exactly one editable strategy source and no
  independently editable JSON or duplicated lifecycle state.
- User-facing docs explain stable direction, horizons, item types, optional
  roadmap inclusion, identity, promotion, validation, and recovery.

## Touchpoints

- `.megaplan/STRATEGY.md`, strategy docs/templates, relevant skill/help sources,
  CLI/contract tests, and CI/pre-commit checks.
- Existing tickets and initiatives only as referenced/read-only adoption inputs.

## Anti-Scope

- Do not claim active-chain status in stable strategy prose.
- Do not add every ticket to make the roadmap look complete.
- Do not introduce a checked-in JSON file unless a real consumer and rebuild
  contract justify it.
- Do not refactor unrelated resident, cloud, or run-authority systems.
