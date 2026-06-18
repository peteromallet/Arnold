# M15: Hardening, Compatibility, Examples, Docs

## Outcome

Harden the extension platform enough to be usable by real developers: compatibility tests, examples, docs, migration notes, release checklist, and a clear line between supported V1 and future power features.

## Execution Posture

Docs are evidence, not aspiration. The final milestone should prove the implemented platform through compiled examples, compatibility gates, supported/deferred matrices, and migration notes; do not launder future promises as V1 behavior.

## Scope

IN:
- Add compatibility test suite for SDK public types and runtime behavior.
- Add example extensions covering UI surface, inspector, overlay, command, parser, effect, transition, clip type, agent tool, and live preview where available.
- Add developer docs and quickstart.
- Add diagnostics/debugging guide.
- Add migration guide from local source extension to installed pack.
- Add release checklist and supported/deferred feature matrix.
- Audit public exports to remove accidental internals.
- Run a contract-recheck pass across every prior milestone's Done Criteria before writing final docs/examples.
- Add an extension author contract guide that ties together contribution declaration, host services, patches/proposals, schemas, diagnostics, renderability, determinism, packaging, and trusted-local warnings.
- Add a frontend closure matrix mapping every public primitive to its required visible host affordance, empty/error/loading/disabled states, accessibility expectations, and at least one test or compiled example.

OUT:
- New platform primitives.
- Marketplace launch.
- Production sandboxing.
- Theme contributions.

## Locked Decisions

- Docs should be honest about unsupported export/cloud paths.
- Public SDK compatibility matters more than internal implementation aesthetics.
- Examples are part of the API contract.
- Every example that exercises a public SDK primitive must compile in CI; richer walkthrough variants may be docs-only if they are derived from tested examples.
- SDK versioning follows semver from the first public package boundary; pre-marketplace releases can be `0.x`, but documented public exports still require changelog/migration notes.
- Browser support follows the app's existing supported browser matrix; extension APIs that require browser-gated capabilities must declare support/fallback behavior.
- Hardening starts with a pre-flight verification matrix: every prior milestone Done Criteria is rechecked against current `main`; failures block release docs rather than being papered over.
- Example matrix includes one example per contribution kind plus cross-cutting and error-path examples. Error examples must prove diagnostics, not crashes.
- Compatibility suite includes type-level SDK compilation, headless provider integration tests, provider contract tests for InMemory/Astrid/Supabase where feasible, and public API regression checks.
- M15 verifies earlier compatibility/provider/test harnesses; it must not be the first milestone to introduce them.
- Public export audit walks transitive exported types from SDK entrypoints and flags leaks of internal provider/mutation/runtime types.
- Every documented API behavior must map to a compiled example and a CI test. Unsupported/deferred matrix rows must be backed by tests or automated absence checks.
- No public primitive is considered complete if it lacks frontend closure: a host-visible surface, diagnostic fallback, accessible empty/error state, and test coverage for the user path.
- Release checklist gates SDK version bumps; it is not a non-blocking markdown note.

## Constraints

- Documentation must match implemented behavior, not future promises.
- Examples must run against current repo without private setup.
- Public export audit should not break existing app imports.

## Done Criteria

- A developer can build a local extension from docs without reading editor internals.
- A developer can understand the trusted-local threat model and author contract before writing code.
- CI covers public SDK behavior and example compilation.
- Supported/deferred matrix is explicit.
- Release checklist captures export limitations, diagnostics, and compatibility rules.
- Public export audit confirms no accidental internal provider state is part of the SDK.
- Contract-recheck matrix passes or explicitly blocks release with documented unresolved gaps.
- Frontend closure matrix passes for surfaces introduced across the epic, including proposals, source maps/diffs, generation sessions, live sources, pending/concrete materials, process roundtrips, export planner, asset search/enrichment, recording passes, shader diagnostics, and extension manager dependency/settings migration flows.
- Frontend closure matrix includes screenshots or test snapshots for empty/loading/error/disabled states of the material browser/detail, generation session panel, steering/range bake, proposal diff/context preview, asset detail/enrichment/search, export configuration/dry-run/sidecar preview, recording surfaces, shader preview/materialize, and extension manager detail flows.

## Touchpoints

- SDK exports
- Example extension directory
- Docs
- Tests/CI
- Existing `.extension_plan.md`
