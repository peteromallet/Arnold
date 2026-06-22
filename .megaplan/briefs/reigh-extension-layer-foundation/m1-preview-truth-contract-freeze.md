# M1: Preview Truth And Contract Freeze

## Outcome

Make the current extension-author preview honest, stable, and hard to accidentally overstate. A clean checkout should prove that docs, manifest schema, contribution-family status, examples, public exports, and release gates agree about what is supported now.

## Scope

In:

- Regenerate and record validation for the intended commit.
- Freeze public exports from `src/tools/video-editor/extension.ts` in the contract registry.
- Fix the known `panels.placement` docs/schema contradiction by adding `placement: 'asset-panel'` to the contract schema to match TypeScript, runtime validation, docs, and examples.
- Fix the latent `slots.placement` runtime/schema drift or remove that field from the runtime contract.
- Add a compatibility drift gate that compares:
  - `src/tools/video-editor/runtime/contributionFamilies.ts`
  - `config/contracts/reigh-extension.schema.json`
  - `docs/extensions/compatibility.md`
  - public exports and examples
- Validate documented manifest examples against `config/contracts/reigh-extension.schema.json`.
- Add production-build extension smoke coverage so extension behavior is not only tested through dev harness routes.
- Add public-entrypoint extraction smoke proving the preview entrypoint is packagable without publishing `@reigh/editor-sdk`.
- Normalize authoring/loading/compatibility docs and trust language.

Out:

- Provider-backed persistence.
- Extension manager UI.
- Timeline proposal persistence or agent policy changes.
- Public creative contribution families.
- Actual `@reigh/editor-sdk` publishing.

## Locked Decisions

- Supported now: surfaces, commands, settings, loader/runtime diagnostics visibility, and command-backed proposals.
- Diagnostics remain loader/runtime-only until the scoped reporter exists.
- Effects, transitions, and clip types remain trusted-only.
- Agent tools, live data, render materials/capabilities, and keyframes remain deferred.
- Manifest permissions are declarative only; they are not runtime enforcement.
- Preview extension code is trusted and unsandboxed.

## Open Questions

- What is the smallest production-build smoke that covers real extension loading without depending on dev-only harness routes?
- Should trust/security docs be standalone or folded into authoring/compatibility docs?

## Constraints

- Do not loosen schema validation to make docs pass unless the runtime contract truly supports the field.
- Do not imply marketplace, sandboxing, permission enforcement, or code signing.
- Do not mark any new contribution family `supported`.
- Do not require Docker locally, but release posture must distinguish local partial validation from Docker-capable CI.

## Done Criteria

- `npm run test:extensions` passes from a clean checkout.
- `npm run build` passes.
- Docker-capable `make release-check` passes or docs explicitly mark the preview non-production.
- Production-build extension smoke passes.
- Documented manifest examples validate against `config/contracts/reigh-extension.schema.json`.
- Drift gate fails if docs/schema/runtime/export status disagree.
- Unknown/deferred contribution collections fail closed.
- Public-entrypoint extraction smoke passes.
- Docs state trusted-code/no-sandbox/no-runtime-permission-enforcement clearly.

## Touchpoints

- `src/tools/video-editor/extension.ts`
- `src/tools/video-editor/runtime/contributionFamilies.ts`
- `src/tools/video-editor/runtime/extensionManifest.ts`
- `config/contracts/registry.json`
- `config/contracts/reigh-extension.schema.json`
- `scripts/quality/check-video-editor-sdk-imports.mjs`
- new or existing drift-check script under `scripts/quality/*`
- `docs/extensions/authoring.md`
- `docs/extensions/loading.md`
- `docs/extensions/compatibility.md`
- `docs/extensions/validation/*`
- `examples/video-editor-extension/*`
- `package.json`
- `Makefile`
- `playwright.config.ts`
- `tests/e2e/video-editor-*.spec.ts`

## Required Tests

- Contract: public extension exports are frozen.
- Schema: documented manifest examples validate.
- Schema: examples using `panels[].placement: 'asset-panel'` validate against `config/contracts/reigh-extension.schema.json`.
- Schema negative: unsupported collections such as effects/transitions/agentTools fail closed.
- Drift gate: docs/schema/runtime mismatch fails.
- Production smoke: built app can load/resolve a known extension surface without relying only on `import.meta.env.DEV` harnesses.
- Import boundary: example extension imports only public entrypoints.
