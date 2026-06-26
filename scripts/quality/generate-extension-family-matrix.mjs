#!/usr/bin/env node
/**
 * Generate `config/extensions/family-maturity.json` from the canonical
 * video family registry.
 *
 * This script imports `VIDEO_FAMILY_REGISTRY` through the `tsx` TypeScript
 * runtime, builds a deterministic JSON projection of every family, and
 * writes the output to `config/extensions/family-maturity.json`.
 *
 * Rows are sorted by `kind` string ascending.  The output contains no
 * timestamps or non-deterministic fields — identical registry data
 * always produces identical JSON.
 *
 * Usage:
 *   npx tsx scripts/quality/generate-extension-family-matrix.mjs
 */

import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');

const OUTPUT_DIR = resolve(repoRoot, 'config', 'extensions');
const OUTPUT_PATH = resolve(OUTPUT_DIR, 'family-maturity.json');

// ---------------------------------------------------------------------------
// Dynamic import of the TypeScript registry via tsx
// ---------------------------------------------------------------------------

/**
 * The tsx runtime resolves `@/` path aliases from tsconfig.json and
 * transpiles TypeScript on the fly.  This dynamic import is the only
 * bridge between the quality scripts (.mjs) and the SDK source (.ts).
 */
const registryModule = await import(
  '@/sdk/video/families/familyDefinitions.js'
);

const conformanceModule = await import(
  '@/sdk/core/families/conformance.js'
);

const { VIDEO_FAMILY_REGISTRY } = registryModule;
const { buildConformanceReport, isFullyConformant } = conformanceModule;

// ---------------------------------------------------------------------------
// Build the matrix
// ---------------------------------------------------------------------------

/**
 * Determine whether a family is bridged (i.e. has host runtime support).
 *
 * Families with execution maturity `runtime-bridged`, `host-integrated`,
 * or `public-supported` are bridged.  Families with execution maturity
 * `delegated` are also considered bridged for runtime-support drift checks
 * when they have a host placeholder adapter (descriptor projection is
 * stable), but they remain `delegated` in the SDK conformance view.
 */
const BRIDGED_EXECUTION_MATURITIES = new Set([
  'runtime-bridged',
  'host-integrated',
  'public-supported',
]);

/**
 * Build a single row for the family maturity matrix.
 * @param {import('@/sdk/core/families/maturity').FamilyDefinition} def
 * @returns {object}
 */
function buildRow(def) {
  const report = buildConformanceReport(def);
  const fullyConformant = isFullyConformant(def);
  const bridged =
    BRIDGED_EXECUTION_MATURITIES.has(def.executionMaturity) ||
    (def.executionMaturity === 'delegated' && def.hostAdapter !== null);

  // Build coverage flags — normalize undefined to null for clean JSON.
  const coverage = {};
  for (const key of Object.keys(def.requirements)) {
    const v = def.requirements[key];
    coverage[key] = v === undefined ? null : v;
  }

  return {
    kind: def.kind,
    label: def.label ?? def.kind,
    description: def.description ?? null,
    declarationMaturity: def.declarationMaturity,
    executionMaturity: def.executionMaturity,
    sdkModules: [...def.sdkModules],
    hostAdapter: def.hostAdapter,
    requiresTrustedCode: def.requiresTrustedCode,
    manifestSchemaDefinition: def.manifestSchemaDefinition,

    /** Requirement checklist as boolean flags (undefined → null). */
    coverage,

    /** Conformance snapshot. */
    conformance: {
      fullyConformant,
      gapCount: report.gaps.length,
      coherent: report.coherent,
      schemaCovered: report.schemaCovered,
      metRequirementCount: report.metRequirements.length,
      unmetRequirementCount: report.unmetRequirements.length,
      unassessedRequirementCount: report.unassessedRequirements.length,
    },

    /** Legacy compatibility metadata for milestone bridging. */
    legacyCompatibility: {
      milestone: def.legacyMilestone ?? null,
      bridged,
    },

    /** Optional host integration notes for human readers. */
    hostIntegrationNotes: def.hostIntegrationNotes ?? null,
  };
}

/**
 * Build the full family maturity matrix, sorted by kind ascending.
 * @returns {object[]}
 */
function buildMatrix() {
  // The registry is already sorted by kind, but sort again for determinism.
  const sorted = [...VIDEO_FAMILY_REGISTRY].sort((a, b) =>
    a.kind.localeCompare(b.kind),
  );

  return sorted.map(buildRow);
}

// ---------------------------------------------------------------------------
// Write output
// ---------------------------------------------------------------------------

const matrix = buildMatrix();

mkdirSync(OUTPUT_DIR, { recursive: true });

// Pretty-print with 2-space indent, trailing newline.
// No timestamp or non-deterministic fields.
writeFileSync(
  OUTPUT_PATH,
  JSON.stringify(matrix, null, 2) + '\n',
  'utf8',
);

console.log(
  `[generate-extension-family-matrix] Wrote ${matrix.length} families to ${OUTPUT_PATH}`,
);
