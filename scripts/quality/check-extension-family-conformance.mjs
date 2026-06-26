#!/usr/bin/env node
/**
 * Extension Family Conformance Gate
 *
 * Validates the registry/schema/generated-artifact contract for every
 * video contribution family.  In audit mode, violations are reported as
 * warnings; in release mode, every violation listed below causes a hard
 * failure.
 *
 * ## Checks (release-mode enforcement)
 *
 *   1. **Registry completeness** — every kind in the schema
 *      `ContributionKind` enum MUST have a corresponding entry in
 *      `VIDEO_FAMILY_REGISTRY`.
 *
 *   2. **Schema definition mapping** — every family's
 *      `manifestSchemaDefinition` MUST exist in the schema's
 *      `Contribution` `oneOf` definitions, and every schema definition
 *      in that oneOf MUST map back to a family.
 *
 *   3. **Stale generated JSON** — `config/extensions/family-maturity.json`
 *      MUST be byte-identical to the output the canonical generator would
 *      produce from the current registry.  Any drift is a hard failure.
 *
 *   4. **Unset maturity coordinates** — `declarationMaturity` and
 *      `executionMaturity` MUST be valid, known levels.  Families with
 *      unknown / missing values are rejected.
 *
 *   5. **Cross-axis coherence** — the declaration/execution maturity
 *      pair MUST pass `checkCrossAxisCoherence`; e.g. `runtime-bridged`
 *      requires at least `schema-backed`.
 *
 *   6. **Schema-backed/documented schema coverage** — any family whose
 *      `declarationMaturity` is `schema-backed` or `documented` MUST
 *      have its `manifestSchema` requirement met (`true`).
 *
 *   7. **Deterministic generated order** — `family-maturity.json` rows
 *      MUST be sorted by `kind` string ascending.
 *
 * ## Modes
 *
 *   --audit     (default)  Report all violations as warnings.  Only exit
 *                          non-zero when a structural error prevents the
 *                          gate from running (missing registry module,
 *                          corrupt schema, unreadable generated JSON).
 *
 *   --release              Every checklist violation is a hard error.
 *                          Use this in CI / `quality:check` pre-commit.
 *
 * ## Dependencies
 *
 *   Imports `VIDEO_FAMILY_REGISTRY` and conformance helpers through the
 *   `tsx` TypeScript runtime.  Reads the schema from disk directly.
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');

const SCHEMA_PATH = resolve(
  repoRoot,
  'config/contracts/reigh-extension.schema.json',
);
const MATURITY_JSON_PATH = resolve(
  repoRoot,
  'config/extensions/family-maturity.json',
);
const GENERATOR_PATH = resolve(
  repoRoot,
  'scripts/quality/generate-extension-family-matrix.mjs',
);

const LABEL = '[family-conformance]';

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

const args = new Set(process.argv.slice(2));

/** @type {'audit' | 'release'} */
let mode = 'audit';
if (args.has('--release')) {
  mode = 'release';
} else if (args.has('--audit')) {
  mode = 'audit';
}

const isRelease = mode === 'release';

// ---------------------------------------------------------------------------
// Report accumulator
// ---------------------------------------------------------------------------

class ConformanceReport {
  constructor() {
    /** @type {string[]} */
    this.errors = [];
    /** @type {string[]} */
    this.warnings = [];
  }

  /** Hard contract violation — always fails. */
  error(msg) {
    this.errors.push(msg);
  }

  /** Advisory mismatch — fails in release mode, warns in audit. */
  warn(msg) {
    this.warnings.push(msg);
  }

  exit() {
    const hasErrors = this.errors.length > 0;
    const hasWarnings = this.warnings.length > 0;

    if (hasErrors) {
      console.error(`\n${LABEL} ERRORS (${this.errors.length}):`);
      for (const e of this.errors) console.error(`  ✗ ${e}`);
    }

    if (hasWarnings) {
      const prefix = isRelease ? 'ERRORS (release mode)' : 'WARNINGS';
      const stream = isRelease ? console.error : console.warn;
      stream(`\n${LABEL} ${prefix} (${this.warnings.length}):`);
      for (const w of this.warnings) {
        (isRelease ? console.error : console.warn)(`  ⚠ ${w}`);
      }
    }

    if (hasErrors) {
      console.error(`\n${LABEL} FAILED: ${this.errors.length} hard violation(s).`);
      process.exit(1);
    }

    if (isRelease && hasWarnings) {
      console.error(`\n${LABEL} FAILED (release mode): ${this.warnings.length} violation(s).`);
      process.exit(1);
    }

    if (!hasErrors && !hasWarnings) {
      console.log(`${LABEL} OK: all families conform.`);
    } else {
      console.log(`${LABEL} OK (audit mode): ${this.warnings.length} advisory violation(s) reported above.`);
    }
    process.exit(0);
  }
}

const R = new ConformanceReport();

// ---------------------------------------------------------------------------
// Dynamic import of TypeScript registry via tsx
// ---------------------------------------------------------------------------

/** @type {import('@/sdk/video/families/familyDefinitions').FamilyDefinition[] | null} */
let registry = null;
/** @type {typeof import('@/sdk/core/families/conformance') | null} */
let conformance = null;

try {
  const registryModule = await import(
    '@/sdk/video/families/familyDefinitions.js'
  );
  registry = registryModule.VIDEO_FAMILY_REGISTRY;

  const conformanceModule = await import(
    '@/sdk/core/families/conformance.js'
  );
  conformance = conformanceModule;
} catch (err) {
  console.error(`${LABEL} FATAL: Cannot import registry or conformance modules.`);
  console.error(`${LABEL} ${err.message}`);
  console.error(`${LABEL} Ensure tsx is available and the TypeScript config resolves @/ paths.`);
  process.exit(2);
}

const { checkCrossAxisCoherence, buildConformanceReport, isFullyConformant } =
  conformance;

// ---------------------------------------------------------------------------
// Adapter registry import (optional — used for delegated-gap metadata checks)
// ---------------------------------------------------------------------------

/** @type {import('@/tools/video-editor/runtime/families/familyAdapterRegistry').FamilyAdapterRegistry | null} */
let adapterRegistry = null;

try {
  const adapterRegistryModule = await import(
    '@/tools/video-editor/runtime/families/familyAdapterRegistry.js'
  );
  adapterRegistry = adapterRegistryModule.VIDEO_EDITOR_FAMILY_ADAPTER_REGISTRY;
} catch (err) {
  console.warn(
    `${LABEL} Could not import video-editor adapter registry; delegated-gap and classification checks will be skipped.`,
  );
}

console.log(
  `${LABEL} Registry: ${registry.length} family definitions loaded.`,
);

// ---------------------------------------------------------------------------
// Load schema
// ---------------------------------------------------------------------------

/** @type {any} */
let schema;
try {
  schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf8'));
} catch (err) {
  console.error(`${LABEL} FATAL: Cannot parse schema: ${err.message}`);
  process.exit(2);
}

const defs = schema.definitions || {};

// Extract ContributionKind enum
/** @type {string[]} */
const schemaKindEnum = defs.ContributionKind?.enum || [];

// Extract Contribution oneOf definition names
/** @type {Set<string>} */
const schemaDefNames = new Set();
if (defs.Contribution?.oneOf) {
  for (const item of defs.Contribution.oneOf) {
    const ref = (item.$ref || '').replace('#/definitions/', '');
    if (ref) schemaDefNames.add(ref);
  }
}

console.log(
  `${LABEL} Schema: ${schemaKindEnum.length} kind enum values, ` +
    `${schemaDefNames.size} contribution definitions.`,
);

// ---------------------------------------------------------------------------
// Derived lookup maps from registry
// ---------------------------------------------------------------------------

/** @type {Map<string, import('@/sdk/core/families/maturity').FamilyDefinition>} */
const registryByKind = new Map();
for (const def of registry) {
  if (registryByKind.has(def.kind)) {
    R.error(`Duplicate family definition for kind '${def.kind}' in registry.`);
  }
  registryByKind.set(def.kind, def);
}

const registryKinds = new Set(registry.map((d) => d.kind));

// ---------------------------------------------------------------------------
// 1. Registry completeness — every schema kind must have a family definition
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking registry completeness…`);

for (const kind of schemaKindEnum) {
  if (!registryKinds.has(kind)) {
    R.warn(
      `Registry missing family definition for kind '${kind}' ` +
        `(present in schema ContributionKind enum).`,
    );
  }
}

// Also check: every registry kind should be in the schema enum
for (const kind of registryKinds) {
  if (!schemaKindEnum.includes(kind)) {
    R.warn(
      `Registry kind '${kind}' is not in schema ContributionKind enum.`,
    );
  }
}

// ---------------------------------------------------------------------------
// 2. Schema definition mapping
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking schema definition mapping…`);

/**
 * Convert a kind string to the expected schema definition name.
 * e.g. 'inspectorSection' → 'InspectorSectionContribution'
 */
function kindToDefName(kind) {
  return kind.charAt(0).toUpperCase() + kind.slice(1) + 'Contribution';
}

/**
 * Convert a schema definition name back to the expected kind.
 * e.g. 'InspectorSectionContribution' → 'inspectorSection'
 */
function defNameToKind(defName) {
  const camelKind = defName.replace(/Contribution$/, '');
  return camelKind.charAt(0).toLowerCase() + camelKind.slice(1);
}

// Every family's manifestSchemaDefinition must exist in the schema
for (const def of registry) {
  if (!schemaDefNames.has(def.manifestSchemaDefinition)) {
    R.warn(
      `Family '${def.kind}' references manifestSchemaDefinition ` +
        `'${def.manifestSchemaDefinition}', which is not in schema Contribution oneOf.`,
    );
  }
}

// Every schema definition in Contribution oneOf should have a family
for (const defName of schemaDefNames) {
  const expectedKind = defNameToKind(defName);
  if (!registryKinds.has(expectedKind)) {
    R.warn(
      `Schema definition '${defName}' in Contribution oneOf has no ` +
        `matching family in registry (expected kind '${expectedKind}').`,
    );
  }
}

// Every family's manifestSchemaDefinition should match the conventional name
for (const def of registry) {
  const expectedDefName = kindToDefName(def.kind);
  if (def.manifestSchemaDefinition !== expectedDefName) {
    R.warn(
      `Family '${def.kind}' manifestSchemaDefinition ` +
        `'${def.manifestSchemaDefinition}' does not match conventional name ` +
        `'${expectedDefName}'.`,
    );
  }
}

// ---------------------------------------------------------------------------
// 3. Unset maturity coordinates
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking maturity coordinates…`);

const VALID_DECLARATION_MATURITIES = new Set([
  'typed',
  'schema-backed',
  'documented',
]);

const VALID_EXECUTION_MATURITIES = new Set([
  'absent',
  'delegated',
  'runtime-bridged',
  'host-integrated',
  'public-supported',
]);

for (const def of registry) {
  if (!VALID_DECLARATION_MATURITIES.has(def.declarationMaturity)) {
    R.warn(
      `Family '${def.kind}' has unknown declarationMaturity ` +
        `'${def.declarationMaturity}'.`,
    );
  }

  if (!VALID_EXECUTION_MATURITIES.has(def.executionMaturity)) {
    R.warn(
      `Family '${def.kind}' has unknown executionMaturity ` +
        `'${def.executionMaturity}'.`,
    );
  }
}

// ---------------------------------------------------------------------------
// 4. Cross-axis coherence
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking cross-axis coherence…`);

for (const def of registry) {
  const coh = checkCrossAxisCoherence(
    def.declarationMaturity,
    def.executionMaturity,
  );
  if (!coh.coherent) {
    for (const violation of coh.violations) {
      R.warn(
        `Family '${def.kind}' coherence violation: ${violation}`,
      );
    }
  }
}

// ---------------------------------------------------------------------------
// 5. Schema coverage — schema-backed+ must have manifestSchema met
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking schema coverage…`);

const SCHEMA_BACKED_OR_HIGHER = new Set(['schema-backed', 'documented']);

for (const def of registry) {
  if (
    SCHEMA_BACKED_OR_HIGHER.has(def.declarationMaturity) &&
    def.requirements.manifestSchema !== true
  ) {
    R.warn(
      `Family '${def.kind}' has declarationMaturity '${def.declarationMaturity}' ` +
        `but manifestSchema requirement is not met (got: ${def.requirements.manifestSchema}).`,
    );
  }
}

// ---------------------------------------------------------------------------
// 6. Generated JSON freshness / staleness check
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking generated JSON freshness…`);

/**
 * Rebuild what the generator would produce from the current registry.
 * This mirrors the logic in `generate-extension-family-matrix.mjs` exactly
 * so we can byte-compare the output.
 */
function buildExpectedMatrix() {
  const { buildConformanceReport: bcR, isFullyConformant: iFC } = conformance;

  const BRIDGED_EXECUTION_MATURITIES = new Set([
    'runtime-bridged',
    'host-integrated',
    'public-supported',
  ]);

  function buildRow(def) {
    const report = bcR(def);
    const fullyConformant = iFC(def);
    const bridged = BRIDGED_EXECUTION_MATURITIES.has(def.executionMaturity);

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
      coverage,
      conformance: {
        fullyConformant,
        gapCount: report.gaps.length,
        coherent: report.coherent,
        schemaCovered: report.schemaCovered,
        metRequirementCount: report.metRequirements.length,
        unmetRequirementCount: report.unmetRequirements.length,
        unassessedRequirementCount: report.unassessedRequirements.length,
      },
      legacyCompatibility: {
        milestone: def.legacyMilestone ?? null,
        bridged,
      },
      hostIntegrationNotes: def.hostIntegrationNotes ?? null,
    };
  }

  const sorted = [...registry].sort((a, b) =>
    a.kind.localeCompare(b.kind),
  );

  return sorted.map(buildRow);
}

const expectedMatrix = buildExpectedMatrix();

/** @type {any[] | null} */
let onDiskMatrix = null;
let onDiskRaw = null;

try {
  onDiskRaw = readFileSync(MATURITY_JSON_PATH, 'utf8');
  onDiskMatrix = JSON.parse(onDiskRaw);
} catch (err) {
  if (!existsSync(MATURITY_JSON_PATH)) {
    R.warn(`Generated JSON not found at ${MATURITY_JSON_PATH}. Run the generator first.`);
  } else {
    R.warn(`Cannot parse generated JSON: ${err.message}`);
  }
}

if (onDiskMatrix) {
  // Compare as normalized JSON strings to catch any drift
  const expectedRaw = JSON.stringify(expectedMatrix, null, 2) + '\n';

  if (onDiskRaw !== expectedRaw) {
    // Provide a more detailed message
    if (onDiskMatrix.length !== expectedMatrix.length) {
      R.warn(
        `Stale generated JSON: expected ${expectedMatrix.length} families, ` +
          `got ${onDiskMatrix.length}. Run the generator to refresh.`,
      );
    } else {
      // Find which rows differ
      for (let i = 0; i < expectedMatrix.length; i++) {
        const expRow = expectedMatrix[i];
        const diskRow = onDiskMatrix[i];
        const expJson = JSON.stringify(expRow);
        const diskJson = JSON.stringify(diskRow);
        if (expJson !== diskJson) {
          R.warn(
            `Stale generated JSON: row ${i} (kind '${expRow.kind}') differs ` +
              `from expected. Run the generator to refresh.`,
          );
          break; // One detailed message is enough
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// 7. Deterministic sort order in generated JSON
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking generated JSON sort order…`);

if (onDiskMatrix) {
  for (let i = 1; i < onDiskMatrix.length; i++) {
    const prev = onDiskMatrix[i - 1].kind;
    const curr = onDiskMatrix[i].kind;
    if (prev > curr) {
      R.warn(
        `Generated JSON sort violation: '${prev}' appears before '${curr}' ` +
          `(must be kind-ascending).`,
      );
    }
  }
}

// ---------------------------------------------------------------------------
// 8. Host adapter consistency and file existence (Step 28)
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking host adapter consistency…`);

const EXECUTION_EXPECTS_ADAPTER = new Set([
  'runtime-bridged',
  'host-integrated',
  'public-supported',
]);

/**
 * Resolve a hostAdapter path from the registry to an absolute file path.
 * @param {string} hostAdapter
 * @returns {string}
 */
function hostAdapterPath(hostAdapter) {
  return resolve(repoRoot, hostAdapter);
}

/**
 * Read the source of a host adapter file.
 * @param {string} hostAdapter
 * @returns {string}
 */
function readHostAdapterSource(hostAdapter) {
  return readFileSync(hostAdapterPath(hostAdapter), 'utf8');
}

for (const def of registry) {
  if (EXECUTION_EXPECTS_ADAPTER.has(def.executionMaturity)) {
    if (def.hostAdapter === null) {
      const msg =
        `Family '${def.kind}' has executionMaturity '${def.executionMaturity}' ` +
        `but hostAdapter is null.`;
      if (isRelease) {
        R.error(msg);
      } else {
        R.warn(msg);
      }
      continue;
    }

    if (!existsSync(hostAdapterPath(def.hostAdapter))) {
      const msg =
        `Family '${def.kind}' host adapter file does not exist: ${def.hostAdapter}`;
      if (isRelease) {
        R.error(msg);
      } else {
        R.warn(msg);
      }
      continue;
    }

    // runtime-bridged families must not use a placeholder adapter
    if (def.executionMaturity === 'runtime-bridged') {
      const source = readHostAdapterSource(def.hostAdapter);
      const isPlaceholder =
        source.includes("classification: 'placeholder'") ||
        source.includes('createPlaceholderAdapter');
      if (isPlaceholder) {
        R.error(
          `Family '${def.kind}' is runtime-bridged but its host adapter ` +
            `appears to be a placeholder (${def.hostAdapter}).`,
        );
      }
    }
  } else if (
    def.executionMaturity === 'absent' &&
    def.hostAdapter !== null
  ) {
    R.warn(
      `Family '${def.kind}' has executionMaturity 'absent' but hostAdapter is non-null.`,
    );
  }
}

// ---------------------------------------------------------------------------
// 9. Delegated gap metadata (Step 28)
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking delegated gap metadata…`);

if (adapterRegistry) {
  for (const def of registry) {
    if (def.executionMaturity !== 'delegated') continue;

    const adapter = adapterRegistry.get(def.kind);
    if (adapter === undefined) {
      R.warn(
        `Family '${def.kind}' is delegated but has no registered adapter in the runtime registry.`,
      );
      continue;
    }
    if (adapter === null) {
      // Known-unavailable delegated family (e.g. agent) — nothing to report.
      continue;
    }

    const meta = adapter.manifest?.metadata ?? {};
    const missing = [];
    if (!meta.owner) missing.push('owner');
    if (!meta.reason) missing.push('reason');
    if (!meta.expiration) missing.push('expiration');

    if (missing.length > 0) {
      R.warn(
        `Family '${def.kind}' delegated gap is missing metadata fields: ${missing.join(', ')}.`,
      );
    }
  }
} else {
  R.warn('Skipping delegated gap metadata checks — adapter registry unavailable.');
}

// ---------------------------------------------------------------------------
// 10. Inline projection check (Step 29)
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking for inline family projection in extensionSurface.ts…`);

const EXTENSION_SURFACE_PATH = resolve(
  repoRoot,
  'src/tools/video-editor/runtime/extensionSurface.ts',
);

if (existsSync(EXTENSION_SURFACE_PATH)) {
  const surfaceSource = readFileSync(EXTENSION_SURFACE_PATH, 'utf8');
  const inlineSwitch =
    /switch\s*\(\s*(contribution|contrib)\.kind\s*\)/.test(surfaceSource);

  if (inlineSwitch) {
    R.error(
      'extensionSurface.ts contains an inline switch on contribution.kind; ' +
        'family projection must live in adapter/projector modules.',
    );
  }
} else {
  R.warn('extensionSurface.ts not found; cannot check for inline projection.');
}

// ---------------------------------------------------------------------------
// 11. Projector forbidden-import check (Step 29)
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking projector imports…`);

const PROJECTORS_DIR = resolve(
  repoRoot,
  'src/tools/video-editor/runtime/families/projectors',
);

/** Forbidden import paths for projector modules. Type-only imports are allowed. */
const FORBIDDEN_PROJECTOR_IMPORTS = [
  'src/tools/video-editor/runtime/extensionSurface',
  'src/tools/video-editor/runtime/useTimelineState.types',
  'src/tools/video-editor/runtime/slices/',
  'src/tools/video-editor/runtime/store/',
  'src/tools/video-editor/state/',
];

/**
 * Detect whether a source line contains a value (non-type) import from one
 * of the forbidden paths.
 *
 * @param {string} line
 * @returns {string | null} the matched forbidden path, or null
 */
function detectForbiddenProjectorImport(line) {
  const trimmed = line.trim();
  if (!trimmed.startsWith('import') && !trimmed.startsWith('export')) {
    return null;
  }
  if (trimmed.startsWith('import type') || trimmed.startsWith('export type')) {
    return null;
  }
  const fromMatch = trimmed.match(/from\s+['"]([^'"]+)['"]/);
  if (!fromMatch) return null;
  const sourcePath = fromMatch[1];
  for (const forbidden of FORBIDDEN_PROJECTOR_IMPORTS) {
    if (sourcePath.includes(forbidden)) return forbidden;
  }
  return null;
}

if (existsSync(PROJECTORS_DIR)) {
  const projectorFiles = readdirSync(PROJECTORS_DIR).filter((name) =>
    name.endsWith('.ts'),
  );
  for (const file of projectorFiles) {
    const filePath = resolve(PROJECTORS_DIR, file);
    const source = readFileSync(filePath, 'utf8');
    const lines = source.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const forbidden = detectForbiddenProjectorImport(lines[i]);
      if (forbidden) {
        const msg =
          `Projector ${file} line ${i + 1} imports from forbidden path ` +
          `'${forbidden}' (value imports from extensionSurface, useTimelineState.types, ` +
          `or broad runtime slice modules are not allowed).`;
        R.error(msg);
      }
    }
  }
} else {
  R.warn('Projectors directory not found; skipping forbidden-import checks.');
}

// ---------------------------------------------------------------------------
// 12. Additional check: all requirement keys must be valid
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking requirement key validity…`);

const VALID_REQUIREMENT_KEYS = new Set([
  'manifestSchema',
  'normalizedDescriptor',
  'registrationApi',
  'lifecycleCleanup',
  'diagnostics',
  'hostCapabilityProjection',
  'uiIntegration',
  'persistencePosture',
  'examples',
  'tests',
]);

for (const def of registry) {
  for (const key of Object.keys(def.requirements)) {
    if (!VALID_REQUIREMENT_KEYS.has(key)) {
      R.warn(
        `Family '${def.kind}' has unknown requirement key '${key}'.`,
      );
    }
  }

  // Check that all expected keys are present
  for (const key of VALID_REQUIREMENT_KEYS) {
    if (!(key in def.requirements)) {
      R.warn(
        `Family '${def.kind}' is missing requirement key '${key}'.`,
      );
    }
  }
}

// ---------------------------------------------------------------------------
// Summary and exit
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Summary:`);
console.log(`  Registry families:  ${registry.length}`);
console.log(`  Schema kinds:        ${schemaKindEnum.length}`);
console.log(`  Schema definitions:  ${schemaDefNames.size}`);
console.log(`  Errors:              ${R.errors.length}`);
console.log(`  Warnings:            ${R.warnings.length}`);

R.exit();
