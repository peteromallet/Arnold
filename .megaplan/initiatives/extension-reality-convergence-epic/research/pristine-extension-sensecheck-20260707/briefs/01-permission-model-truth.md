# Codex Sense-Check: Permission Model Truth

Repo: `/Users/peteromalley/Documents/reigh-workspace/reigh-app`

Run read-only. Do not edit files.

## Task

Investigate the current threat and best next move for the Reigh extension permission/trust model.

The criticism to evaluate:

> Manifests declare permissions that nothing enforces. Either enforce permissions at runtime through sandboxing/capability gating, or strip declarative theater and lean fully into the trusted-code model.

## What To Inspect

Prioritize current code over old docs:

- `src/sdk/index.ts`
- `config/contracts/reigh-extension.schema.json`
- `src/tools/video-editor/runtime/extensionManifest.ts`
- `src/tools/video-editor/runtime/extensionLoader.ts`
- `src/tools/video-editor/runtime/extensionSurface.ts`
- `src/tools/video-editor/runtime/extensionPackageManifest.ts`
- `src/tools/video-editor/components/ExtensionManager/**`
- `docs/extensions/compatibility.md`
- `docs/extensions/authoring.md`
- `docs/extensions/loading.md`
- `docs/extensions/phase4-readiness.md`
- `docs/video-editor/extension-platform-supported-deferred.md`
- `scripts/quality/**` relevant to extension claims
- checked-in example manifests under `src/tools/video-editor/examples/extensions/**/reigh-extension.json`

## Questions

1. What permission declarations exist today, and are any actually enforced?
2. Where could a user/developer reasonably infer false safety from manifest permissions?
3. Is real runtime enforcement/sandboxing feasible as a near-term foundation completion task, or should the pristine move be honesty-first docs/schema/UI?
4. What would a truly pristine permission/trust model look like for this codebase?
5. What is the smallest high-leverage plan to get there without overbuilding?

## Output

Markdown under 1800 words:

# Permission Model Truth
## Verdict
Say whether the criticism is valid and how severe the threat is.
## Current Code Reality
Concrete files and facts.
## Pristine End State
What the model should become.
## Recommended Work
Ranked actions, with "now" vs "later".
## Tests / Gates
Specific tests/scripts/docs checks needed.
## Biggest Trap
The tempting but wrong thing to do.

