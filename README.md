# Reigh

AI-powered image and video generation studio. **For usage, go to [reigh.art](https://reigh.art/)** — this repo is for development only.

---

## Tech Stack

React + Vite + TypeScript · TailwindCSS + shadcn-ui · Supabase (Postgres, Auth, Storage, Edge Functions)

## Quick Start

**Prerequisites:** Node.js 18+, Docker, [Supabase CLI v1+](https://supabase.com/docs/guides/cli)

```bash
git clone https://github.com/peteromallet/reigh
cd reigh && npm install

cp .env .env.local            # or create .env manually
supabase start                # launches Postgres, Auth, Storage, Realtime
# copy the printed SUPABASE_URL, ANON_KEY & SERVICE_ROLE_KEY into .env
supabase db push              # applies migrations

npm run dev                   # Vite on http://localhost:2222
```

GPU task processing requires **[Reigh-Worker](https://github.com/banodoco/Reigh-Worker)** running separately. Worker and API orchestration is managed by **[Reigh-Worker-Orchestrator](https://github.com/banodoco/Reigh-Worker-Orchestrator)**.

## Governance Contracts

- Supabase runtime contract: [`docs/governance/contracts/supabase-runtime.md`](docs/governance/contracts/supabase-runtime.md)
- Error handling contract: [`docs/governance/contracts/error-handling.md`](docs/governance/contracts/error-handling.md)
- Compatibility shims and migration gates: [`docs/governance/contracts/compatibility-shims.md`](docs/governance/contracts/compatibility-shims.md)

### Contract Status Matrix

| Contract Surface | Canonical Path | Compatibility Status | Removal Target |
|---|---|---|---|
| Supabase runtime accessor | `src/integrations/supabase/client.ts` | Stable canonical | N/A |
| Runtime error normalization | `src/shared/lib/errorHandling/runtimeError.ts` (`normalizeAndPresentError`) | Deprecated aliases live in `src/shared/lib/errorHandling/handleError.ts` | 2026-06-30 |
| UI button entrypoint | `src/shared/components/ui/button.tsx` | Stable canonical for app imports | N/A |
| UI button primitive (base-only) | `src/shared/components/ui/contracts/button.tsx` | Canonical primitive contract behind `ui/button` | N/A |
| UI themed button wrapper | `src/shared/components/ui/theme/button.tsx` | App layer wrapper over base primitive | N/A |
| UI class merge primitive | `src/shared/components/ui/contracts/cn.ts` | Stable canonical | N/A |
| Video editor core SDK | `src/tools/video-editor/index.ts` | Stable edge-safe contract | N/A |
| Video editor browser helpers | `src/tools/video-editor/browser.ts` | Stable browser-only contract | N/A |
| Video editor browser provider | `src/tools/video-editor/browser-provider.ts` | Stable custom-shell browser contract | N/A |
| Video editor testing helpers | `src/tools/video-editor/testing.ts` | Stable testing contract | N/A |

Compatibility shims that remain for legacy imports:

- `src/shared/components/ui/primitives/cn.ts` -> re-export shim to `ui/contracts/cn.ts`

### Governance Test Gates

Run these in CI and before merging facade/contract changes:

- `npm run test:contracts`
- `npm run test:arch`
- `npm run quality:check`
- `npm run quality:extension-family-conformance`

### Gate-to-Surface Map

| Gate | Required Surface Coverage | Expected Assertion |
|---|---|---|
| `npm run test:contracts` | `src/sdk/index.ts`, `src/tools/video-editor/index.ts`, `src/tools/video-editor/browser.ts`, `src/tools/video-editor/testing.ts`, `src/shared/components/ui/contracts/cn.ts`, `src/shared/lib/errorHandling/runtimeError.ts`, `src/domains/generation/types/index.ts` | Public contract API shape and behavior stays stable |
| `npm run test:arch` | `scripts/quality/check-video-editor-sdk-imports.mjs`, `scripts/quality/check-sdk-no-barrel-imports.mjs`, `config/governance/video-editor-sdk-import-allowlist.json`, `src/shared/lib/errorHandling/runtimeError.ts`, `src/integrations/supabase/client.ts`, `docs/governance/contracts/compatibility-shims.md` | Contract and shim usage rules are enforced |
| `npm run quality:check` | `src/sdk/index.ts`, `src/tools/video-editor/index.ts`, `src/tools/video-editor/browser.ts`, `src/tools/video-editor/testing.ts`, `scripts/quality/check-video-editor-sdk-imports.mjs`, `scripts/quality/check-sdk-public-exports.mjs`, `scripts/quality/check-sdk-no-barrel-imports.mjs`, `config/governance/video-editor-sdk-import-allowlist.json`, `config/governance/sdk-public-export-allowlist.json`, `src/integrations/supabase/client.ts`, `src/shared/lib/errorHandling/runtimeError.ts`, `src/shared/components/ui/contracts/cn.ts` | Integrated lint/typecheck/governance checks pass for touched contract surfaces |
| `npm run quality:extension-family-conformance` | `src/sdk/video/families/familyDefinitions.ts`, `src/sdk/video/families/familyDefinitions.test.ts`, `src/sdk/video/families/conformanceGate.test.ts`, `src/sdk/core/families/maturity.ts`, `src/sdk/core/families/conformance.ts` | Family registry/schema/conformance contract stays aligned |

## Code Health

<img src="scorecard.png">

## Documentation

| Doc | Purpose |
|-----|---------|
| **[structure.md](structure.md)** | Architecture overview, directory map, links to all sub-docs |
| **[docs/code_quality_audit.md](docs/code_quality_audit.md)** | Quality standards, anti-patterns, metrics, known exceptions |
| **[docs/video-editor-sdk/](docs/video-editor-sdk/README.md)** | Supported public SDK guide, recipes, and standalone embed demo references |
| **[CLAUDE.md](CLAUDE.md)** | AI agent instructions — working rules, routing table, conventions (symlinked to `.cursorrules`) |
| **[docs/structure_detail/](docs/structure_detail/)** | 24 focused sub-docs covering every system (settings, data fetching, realtime, tasks, etc.) |
