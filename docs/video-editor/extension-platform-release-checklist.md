# Extension Platform — V1 Release Checklist

**Status:** Active (M15)
**Last updated:** 2026-06-20
**Scope:** Every evidence domain that must pass before a V1 extension-platform release can be cut.
**Consumer:** `scripts/quality/check-extension-release-checklist.mjs` (this file is the canonical data source).

---

## 1. Purpose

This checklist is the **single gate** that determines whether the extension platform is
ready for a V1 release. It aggregates evidence from every M15 quality gate and doc
artifact. Every row maps to a concrete file, test, or matrix entry.

**Release-blocking** rows (denoted `release-blocking`) cause `check-extension-release-checklist.mjs --release`
to exit non-zero. **Audit** rows cause the `--audit` mode (and `quality:check`) to report
warnings but not fail.

### 1.1 How to read this checklist

| Column | Meaning |
|---|---|
| **#** | Checklist item number. |
| **Domain** | Evidence domain (SDK, diagnostics, compatibility, docs, frontend, etc.). |
| **Check** | What must be true. |
| **Evidence** | Concrete artifact path(s) or gate reference. |
| **Release?** | `yes` = release-blocking; `no` = audit-only. |

---

## 2. Release Checklist

### 2.1 SDK Boundary & Public Exports

| # | Domain | Check | Evidence | Release? |
|---|---|---|---|---|
| 1 | SDK | `@reigh/editor-sdk` is the only public import path | `src/sdk/__tests__/sdk-boundary.test.ts`; `scripts/quality/check-sdk-public-exports.mjs` | yes |
| 2 | SDK | SDK boundary test passes without importing editor internals | `src/sdk/__tests__/sdk-boundary.test.ts`; `config/governance/sdk-public-export-allowlist.json` | yes |
| 3 | SDK | All SDK public exports are in the allowlist | `scripts/quality/check-sdk-public-exports.mjs`; `config/governance/sdk-public-export-allowlist.json` | yes |
| 4 | SDK | No internal re-exports leak through `@reigh/editor-sdk` | `config/governance/sdk-public-export-allowlist.json`; `src/sdk/index.ts` | yes |
| 5 | SDK | `src/sdk/index.ts` compiles under `tsc --noEmit` | `tsconfig.json`; `npm run typecheck:strict-probe` | yes |

### 2.2 Contract-Recheck Matrix

| # | Domain | Check | Evidence | Release? |
|---|---|---|---|---|
| 6 | Contract | Contract-recheck matrix is well-formed (no missing columns, bad vocab) | `docs/video-editor/extension-platform-contract-recheck.md`; `scripts/quality/check-extension-contract-recheck.mjs` | yes |
| 7 | Contract | Zero release-blocking rows in contract-recheck matrix | `docs/video-editor/extension-platform-contract-recheck.md`; `scripts/quality/check-extension-contract-recheck.mjs` | yes |
| 8 | Contract | Every supported row has non-empty evidence | `docs/video-editor/extension-platform-contract-recheck.md`; `scripts/quality/check-extension-contract-recheck.mjs` | yes |
| 9 | Contract | Every deferred/unsupported row has evidence or a release blocker | `docs/video-editor/extension-platform-contract-recheck.md`; `docs/video-editor/extension-platform-supported-deferred.md` | yes |

### 2.3 Supported / Deferred Matrix

| # | Domain | Check | Evidence | Release? |
|---|---|---|---|---|
| 10 | Deferred | Supported/deferred matrix parses cleanly | `docs/video-editor/extension-platform-supported-deferred.md` | yes |
| 11 | Deferred | Every deferred row has absence-check evidence or a blocker link | `docs/video-editor/extension-platform-supported-deferred.md`; `scripts/quality/check-extension-deferred-claims.mjs` | yes |
| 12 | Deferred | Risky deferred terms (marketplace, cloud loading, sandbox, CRDT, etc.) are covered | `scripts/quality/check-extension-deferred-claims.mjs` | yes |

### 2.4 Diagnostics

| # | Domain | Check | Evidence | Release? |
|---|---|---|---|---|
| 13 | Diagnostics | `ExtensionDiagnosticsService.report()` with stable codes, severity, source ranges | `src/sdk/index.ts`; `src/examples/code-panel-diagnostics-example.ts`; `docs/video-editor/extensions-debugging.md` | yes |
| 14 | Diagnostics | Diagnostic fallback links open `DiagnosticPanel` filtered to failing extension | `docs/video-editor/frontend-closure-matrix.md` § 6; `docs/video-editor/extensions-debugging.md` § 3 | yes |
| 15 | Diagnostics | Export guard diagnostics for missing/unsupported extensions | `src/tools/video-editor/runtime/renderability.ts`; `docs/video-editor/provider-compatibility-matrix.md` § 3.2 | yes |
| 16 | Diagnostics | Lifecycle teardown failures captured as diagnostics, never thrown | `docs/video-editor/extensions-trust-envelope.md` § 2 (Dispose row); S-017 | yes |

### 2.5 Compatibility

| # | Domain | Check | Evidence | Release? |
|---|---|---|---|---|
| 17 | Compatibility | Provider compatibility matrix is current and complete | `docs/video-editor/provider-compatibility-matrix.md` — all three providers (InMemory, Supabase, Astrid Bridge) | yes |
| 18 | Compatibility | InMemory provider: full M3 TimelinePatch + Proposal support | `docs/video-editor/provider-compatibility-matrix.md` § 3.3–3.8; `src/tools/video-editor/data/InMemoryDataProvider.test.ts` | yes |
| 19 | Compatibility | Supabase provider: full M3 support | `docs/video-editor/provider-compatibility-matrix.md` § 3.3–3.8; `src/tools/video-editor/data/SupabaseDataProvider.test.ts` | yes |
| 20 | Compatibility | Astrid Bridge provider: documented partial support with known limitations | `docs/video-editor/provider-compatibility-matrix.md` § 3.3 (Partial CAS enforcement noted) | yes |

### 2.6 Docs / Example Parity

| # | Domain | Check | Evidence | Release? |
|---|---|---|---|---|
| 21 | Docs | Every supported behavior in the supported/deferred matrix has a corresponding example | `docs/video-editor/extension-platform-supported-deferred.md` — EX:/EXT: refs; `src/examples/` (21 files) | yes |
| 22 | Docs | Pre-doc example readiness gate passes (all EX:/EXT: refs resolve) | `scripts/quality/check-extension-example-readiness.mjs`; `src/examples/` | yes |
| 23 | Docs | Extension quickstart compiles and matches current SDK API surface | `docs/video-editor/extensions-quickstart.md`; `src/sdk/index.ts` | yes |
| 24 | Docs | Extension author contract is traceable to the supported/deferred matrix | `docs/video-editor/extension-author-contract.md`; `docs/video-editor/extension-platform-supported-deferred.md` | yes |
| 25 | Docs | Extensions debugging guide references concrete diagnostic codes and lifecycle events | `docs/video-editor/extensions-debugging.md`; `docs/video-editor/extensions-trust-envelope.md` | yes |
| 26 | Docs | Migration guide (local → pack) honesty: no aspirational prose, every deferred item linked to a blocker or matrix row | `docs/video-editor/extensions-migration-local-to-pack.md`; `docs/video-editor/extension-platform-supported-deferred.md` | yes |
| 27 | Docs | Trust envelope documents capability visibility table and lifecycle boundaries | `docs/video-editor/extensions-trust-envelope.md`; S-016, S-017 | yes |

### 2.7 Frontend Closure

| # | Domain | Check | Evidence | Release? |
|---|---|---|---|---|
| 28 | Frontend | Frontend closure matrix is well-formed with all required columns | `docs/video-editor/frontend-closure-matrix.md`; `scripts/quality/check-frontend-closure-matrix.mjs` | yes |
| 29 | Frontend | Zero release-blocking primitives in frontend closure matrix | `docs/video-editor/frontend-closure-matrix.md`; `scripts/quality/check-frontend-closure-matrix.mjs` | yes |
| 30 | Frontend | Every supported primitive has evidence paths that resolve to existing files | `docs/video-editor/frontend-closure-matrix.md`; `scripts/quality/check-frontend-closure-matrix.mjs` | yes |
| 31 | Frontend | UI state coverage (empty / loading / error / disabled) documented for all supported primitives | `docs/video-editor/frontend-closure-matrix.md` — UI states column | yes |
| 32 | Frontend | Accessibility expectations documented for all supported primitives | `docs/video-editor/frontend-closure-matrix.md` — accessibility column; § 14 (cross-cutting a11y gaps) | yes |

### 2.8 Structural Governance

| # | Domain | Check | Evidence | Release? |
|---|---|---|---|---|
| 33 | Governance | Contract surface map is current (`config/governance/contract-surface-map.json`) | `scripts/quality/check-contract-surface-map.mjs` | yes |
| 34 | Governance | Contract governance checks pass (`check-contract-governance.mjs`) | `scripts/quality/check-contract-governance.mjs` | yes |
| 35 | Governance | No SDK import violations in example files (`check-video-editor-sdk-imports.mjs`) | `scripts/quality/check-video-editor-sdk-imports.mjs` | yes |
| 36 | Governance | No core shim usage violations (`check-core-shim-usage.mjs`) | `scripts/quality/check-core-shim-usage.mjs` | yes |
| 37 | Governance | No shots shim usage violations (`check-shots-shim-usage.mjs --max 0`) | `scripts/quality/check-shots-shim-usage.mjs` | yes |

### 2.9 Test Infrastructure

| # | Domain | Check | Evidence | Release? |
|---|---|---|---|---|
| 38 | Tests | SDK boundary test suite passes | `npm run test:sdk-boundary` → `vitest run --config config/testing/vitest.boundary.config.ts` | yes |
| 39 | Tests | No smoke tests (`check:no-smoke-tests`) | `scripts/quality/check-no-smoke-tests.mjs` | yes |
| 40 | Tests | Lint passes with zero warnings | `npm run lint` → `eslint . --ext ts,tsx --max-warnings 0` | yes |
| 41 | Tests | Strict-islands typecheck passes | `npm run typecheck:strict-probe` | yes |

### 2.10 Release Gate Meta

| # | Domain | Check | Evidence | Release? |
|---|---|---|---|---|
| 42 | Meta | This checklist file is parseable by the release checklist gate | `scripts/quality/check-extension-release-checklist.mjs`; `docs/video-editor/extension-platform-release-checklist.md` | yes |
| 43 | Meta | `quality:check` aggregate passes (all audit-mode gates) | `npm run quality:check` | no |
| 44 | Meta | All M15 success criteria (plan_v1.meta.json) have been reviewed | `.megaplan/plans/m15-hardening-compatibility-20260620-1850/plan_v1.meta.json` | no |

---

## 3. Gate summary

| Gate | Mode | Package script |
|---|---|---|
| `check-extension-release-checklist.mjs` | `--audit` | `npm run check:release-checklist` |
| `check-extension-release-checklist.mjs` | `--release` | `npm run check:release-checklist:release` |
| Aggregate audit | (all audit gates) | `npm run quality:check` |

### 3.1 Release-blocking summary

All 43 checklist items marked `Release? = yes` (items 1–42) are **release-blocking**.
Items 43–44 are audit-only and do not block release.

A release can be cut when:
- `npm run check:release-checklist:release` exits 0 (all release-blocking items pass)
- `npm run check:contract-recheck:release` exits 0
- `npm run check:deferred-claims:release` exits 0
- `npm run check:sdk-public-exports:release` exits 0
- `npm run check:frontend-closure:release` exits 0
- `npm run check:extension-example-readiness:release` exits 0

---

## 4. Maintenance

When adding a new evidence domain or gate:
1. Add a row to § 2 with the appropriate `Release?` classification.
2. Update § 3 if a new package script is needed.
3. Run `node scripts/quality/check-extension-release-checklist.mjs --audit` to verify the row parses.
4. Run `node scripts/quality/check-extension-release-checklist.mjs --release` to confirm the gate still passes.

**Never** change a release-blocking row to audit-only without a documented deferral rationale
and a corresponding entry in the supported/deferred matrix.
