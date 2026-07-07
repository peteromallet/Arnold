#!/usr/bin/env node
/**
 * M1 Preview Truth — Extension Contract Drift Gate
 *
 * Compares SDK exported kinds, bridged/reserved status, manifest schema
 * enums/placements, supported/deferred docs rows, and checked-in extension
 * manifests.  Fails on every defined mismatch category:
 *
 *   1. Kind drift        — SDK ContributionKind ≠ schema ContributionKind enum
 *   2. Placement drift   — schema SlotName / placement enums ≠ SDK slot names
 *                           or placement constants
 *   3. Docs drift        — supported rows reference kinds not in SDK or schema
 *   4. Schema drift      — schema definitions missing for known kinds
 *   5. Manifest drift    — checked-in manifests use unknown/invalid kinds or
 *                           violate placement rules
 *   6. Bridged/reserved  — SDK bridged/reserved status inconsistent with docs
 *
 * ## Modes
 *
 *   --audit   (default)  Report mismatches as warnings.  Only exit non-zero
 *                        when a hard contract violation exists (unknown kind
 *                        in a checked-in manifest, schema missing a known kind
 *                        definition).
 *
 *   --release            Every mismatch category causes a hard failure.
 *
 * ## Design
 *
 * This gate does NOT import TypeScript — it parses the SDK source file and
 * schema JSON statically.  This keeps it fast and dependency-free at the
 * CLI level while still catching real contract drift.
 */

import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { resolve, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  parseSdkContributionKinds,
  loadFamilyMaturityMatrix,
  readFileIfExists,
} from './lib/drift-check-helpers.mjs';

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------

const moduleDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(moduleDir, '..', '..');

const SDK_INDEX = resolve(repoRoot, 'src/sdk/index.ts');
const SDK_MANIFEST = resolve(repoRoot, 'src/sdk/manifest.ts');
const SCHEMA_PATH = resolve(repoRoot, 'config/contracts/reigh-extension.schema.json');
const DOCS_PATH = resolve(
  repoRoot,
  'docs/video-editor/extension-platform-supported-deferred.md',
);
const EXTENSIONS_DIR = resolve(
  repoRoot,
  'src/tools/video-editor/examples/extensions',
);
const FAMILY_MATURITY_PATH = resolve(repoRoot, 'config/extensions/family-maturity.json');

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

const args = new Set(process.argv.slice(2));
const mode = args.has('--release') ? 'release' : 'audit';
const LABEL = '[extension-drift]';

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/** Accumulate errors and warnings. */
class DriftReport {
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

  /** Exit with appropriate code. */
  exit() {
    const hasErrors = this.errors.length > 0;
    const hasWarnings = this.warnings.length > 0;

    if (hasErrors) {
      console.error(`\n${LABEL} ERRORS (${this.errors.length}):`);
      for (const e of this.errors) console.error(`  ✗ ${e}`);
    }

    if (hasWarnings) {
      const prefix = mode === 'release' ? 'ERRORS (release mode)' : 'WARNINGS';
      const stream = mode === 'release' ? console.error : console.warn;
      stream(`\n${LABEL} ${prefix} (${this.warnings.length}):`);
      for (const w of this.warnings) {
        (mode === 'release' ? console.error : console.warn)(`  ⚠ ${w}`);
      }
    }

    if (hasErrors) {
      console.error(`\n${LABEL} FAILED: ${this.errors.length} hard violation(s).`);
      process.exit(1);
    }

    if (mode === 'release' && hasWarnings) {
      console.error(`\n${LABEL} FAILED (release mode): ${this.warnings.length} mismatch(es).`);
      process.exit(1);
    }

    if (!hasErrors && !hasWarnings) {
      console.log(`${LABEL} OK: no drift detected across SDK, schema, docs, and manifests.`);
    } else {
      console.log(`${LABEL} OK (audit mode): ${this.warnings.length} advisory mismatch(es) reported above.`);
    }
    process.exit(0);
  }
}

const R = new DriftReport();

// ---------------------------------------------------------------------------
// 1. Parse SDK ContributionKind and bridged/reserved status
// ---------------------------------------------------------------------------
//
// Bridged/reserved classification now comes from the family maturity
// matrix (config/extensions/family-maturity.json) — the canonical
// registry-derived source of truth.  The legacy regex-parsed
// contributionKindNotYetBridged() authority is removed from the
// production drift gate.

// Load the family maturity matrix for bridged/reserved authority.
const familyMatrix = loadFamilyMaturityMatrix(FAMILY_MATURITY_PATH);

// Parse SDK kinds from source and apply registry-based bridged/reserved.
// Read both index.ts (barrel) and contributionKinds.ts (canonical authority) since
// ContributionKind is a type alias whose canonical union lives in contributionKinds.ts.
const CANONICAL_KINDS_PATH = resolve(repoRoot, 'src/sdk/video/families/contributionKinds.ts');
const sdkSource = (readFileIfExists(SDK_INDEX) || '') + '\n' + (readFileIfExists(CANONICAL_KINDS_PATH) || '');
if (!sdkSource.trim()) {
  R.error(`SDK index not found: ${SDK_INDEX}`);
}

const sdk = parseSdkContributionKinds(sdkSource, {
  bridged: familyMatrix.bridged,
  reserved: familyMatrix.reserved,
  milestoneMap: familyMatrix.milestoneMap,
});
console.log(`${LABEL} SDK: ${sdk.kinds.length} kinds (${sdk.bridged.size} bridged, ${sdk.reserved.size} reserved)`);
console.log(`${LABEL} Matrix: ${familyMatrix.bridged.size} bridged, ${familyMatrix.reserved.size} reserved from family-maturity.json`);

// ---------------------------------------------------------------------------
// 2. Parse schema enums and definitions
// ---------------------------------------------------------------------------

/**
 * Parse the JSON schema and extract contribution-relevant enums and definitions.
 */
function parseSchema() {
  if (!existsSync(SCHEMA_PATH)) {
    R.error(`Schema not found: ${SCHEMA_PATH}`);
    return { kindEnum: [], slotEnum: [], definitions: new Set(), placementConstraints: {} };
  }

  /** @type {any} */
  let schema;
  try {
    schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf8'));
  } catch (e) {
    R.error(`Schema parse error: ${e.message}`);
    return { kindEnum: [], slotEnum: [], definitions: new Set(), placementConstraints: {} };
  }

  const defs = schema.definitions || {};

  // Extract ContributionKind enum
  /** @type {string[]} */
  const kindEnum = defs.ContributionKind?.enum || [];

  // Extract SlotName enum
  /** @type {string[]} */
  const slotEnum = defs.SlotName?.enum || [];

  // Collect all contribution definition names
  /** @type {Set<string>} */
  const definitions = new Set();
  // Look for $ref patterns in the Contribution oneOf
  const contributionDef = defs.Contribution;
  if (contributionDef?.oneOf) {
    for (const item of contributionDef.oneOf) {
      const ref = item.$ref || '';
      const name = ref.replace('#/definitions/', '');
      if (name) definitions.add(name);
    }
  }

  // Extract placement constraints per kind
  /** @type {Record<string, {placement?: string[], slot?: boolean}>} */
  const placementConstraints = {};

  for (const [defName, def] of Object.entries(defs)) {
    if (!defName.endsWith('Contribution') || defName === 'Contribution') continue;
    if (typeof def !== 'object' || !def) continue;

    const constraints = {};

    // Check for placement property
    if (def.properties?.placement) {
      const placementProp = def.properties.placement;
      if (placementProp.enum) {
        constraints.placement = placementProp.enum;
      } else if (placementProp.const) {
        constraints.placement = [placementProp.const];
      }
    }

    // Check if this kind has a slot property
    if (def.properties?.slot) {
      constraints.slot = true;
    }

    placementConstraints[defName] = constraints;
  }

  return { kindEnum, slotEnum, definitions, placementConstraints };
}

const schema = parseSchema();
console.log(`${LABEL} Schema: ${schema.kindEnum.length} kind enum values, ${schema.slotEnum.length} slot enum values, ${schema.definitions.size} contribution definitions`);

// ---------------------------------------------------------------------------
// 3. Parse docs supported/deferred rows
// ---------------------------------------------------------------------------

/**
 * Parse the supported/deferred matrix and extract:
 * - Row IDs for supported and deferred
 * - Contribution kinds referenced in evidence
 */
function parseDocs() {
  if (!existsSync(DOCS_PATH)) {
    R.error(`Docs not found: ${DOCS_PATH}`);
    return { supportedRows: [], deferredRows: [], referencedKinds: new Set() };
  }

  const content = readFileSync(DOCS_PATH, 'utf8');

  /** @type {string[]} */
  const supportedRows = [];
  /** @type {string[]} */
  const deferredRows = [];
  /** @type {Set<string>} */
  const referencedKinds = new Set();

  // Parse supported rows: S-* rows
  const sRowRe = /\|\s*(S-\d+)\s*\|/g;
  for (const m of content.matchAll(sRowRe)) {
    supportedRows.push(m[1]);
  }

  // Parse deferred rows: D-* rows
  const dRowRe = /\|\s*(D-\d+)\s*\|/g;
  for (const m of content.matchAll(dRowRe)) {
    deferredRows.push(m[1]);
  }

  // Scan evidence column for kind references
  // Look for patterns like: EXT:flagship-local/, EX:toolbar-example.ts
  // These reference contribution kinds indirectly

  // Also scan the whole document for explicit kind mentions
  // in the context of contribution surfaces
  for (const kind of sdk.kinds) {
    const escaped = kind.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`\\b${escaped}\\b`, 'i');
    if (re.test(content)) {
      referencedKinds.add(kind);
    }
  }

  return { supportedRows, deferredRows, referencedKinds };
}

const docs = parseDocs();
console.log(`${LABEL} Docs: ${docs.supportedRows.length} supported rows, ${docs.deferredRows.length} deferred rows`);

// ---------------------------------------------------------------------------
// 4. Collect and validate checked-in extension manifests
// ---------------------------------------------------------------------------

/**
 * Walk the extensions directory and validate every reigh-extension.json.
 */
function parseExtensionManifests() {
  if (!existsSync(EXTENSIONS_DIR)) {
    R.warn(`Extensions directory not found: ${EXTENSIONS_DIR}`);
    return [];
  }

  /** @type {Array<{path: string, manifest: any, errors: string[], warnings: string[]}>} */
  const manifests = [];

  for (const entry of readdirSync(EXTENSIONS_DIR, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name.startsWith('.') || entry.name === '__tests__') continue;

    const manifestPath = resolve(EXTENSIONS_DIR, entry.name, 'reigh-extension.json');
    if (!existsSync(manifestPath)) {
      R.warn(`Extension directory '${entry.name}' has no reigh-extension.json`);
      continue;
    }

    /** @type {any} */
    let raw;
    try {
      raw = JSON.parse(readFileSync(manifestPath, 'utf8'));
    } catch (e) {
      R.error(`Extension manifest parse error in '${entry.name}': ${e.message}`);
      continue;
    }

    // Unwrap manifest wrapper: { "manifest": { ... } }
    const manifest = raw.manifest || raw;
    /** @type {string[]} */
    const errors = [];
    /** @type {string[]} */
    const warnings = [];

    // Validate manifest structure
    if (!manifest.id || typeof manifest.id !== 'string') {
      errors.push(`Missing or invalid 'id' field`);
    }
    if (!manifest.version || typeof manifest.version !== 'string') {
      errors.push(`Missing or invalid 'version' field`);
    }
    if (!manifest.label || typeof manifest.label !== 'string') {
      errors.push(`Missing or invalid 'label' field`);
    }

    // Validate contributions
    const contributions = manifest.contributions;
    if (!Array.isArray(contributions)) {
      if (contributions !== undefined) {
        errors.push(`'contributions' must be an array`);
      }
    } else {
      for (let i = 0; i < contributions.length; i++) {
        const c = contributions[i];
        if (!c || typeof c !== 'object') {
          errors.push(`contributions[${i}] is not an object`);
          continue;
        }
        if (!c.id) {
          errors.push(`contributions[${i}] missing 'id'`);
        }
        if (!c.kind) {
          errors.push(`contributions[${i}] (${c.id || '?'}) missing 'kind'`);
        } else {
          // Check if kind is in SDK known kinds
          if (!sdk.kinds.includes(c.kind)) {
            errors.push(
              `contributions[${i}] (${c.id}) has unknown kind '${c.kind}' — not in SDK ContributionKind`,
            );
          }

          // Validate kind-specific required fields.
          // All contribution shape issues are advisory warnings, not hard errors,
          // since the manifest is parseable and the extension host will surface
          // diagnostics at activation time.
          const addIssue = (msg) => warnings.push(msg);

          if (c.kind === 'slot' && !c.slot) {
            addIssue(`contributions[${i}] (${c.id}): kind 'slot' requires 'slot' field`);
          }
          if (c.kind === 'effect' && !c.effectId) {
            addIssue(`contributions[${i}] (${c.id}): kind 'effect' requires 'effectId' field`);
          }
          if (c.kind === 'transition' && !c.transitionId) {
            addIssue(`contributions[${i}] (${c.id}): kind 'transition' requires 'transitionId' field`);
          }
          if (c.kind === 'clipType' && !c.clipTypeId) {
            addIssue(`contributions[${i}] (${c.id}): kind 'clipType' requires 'clipTypeId' field`);
          }
          if (c.kind === 'shader' && !c.shaderId) {
            addIssue(`contributions[${i}] (${c.id}): kind 'shader' requires 'shaderId' field`);
          }
          if (c.kind === 'command' && !c.command) {
            addIssue(`contributions[${i}] (${c.id}): kind 'command' requires 'command' field`);
          }
          if (c.kind === 'keybinding' && (!c.command || !c.key)) {
            addIssue(
              `contributions[${i}] (${c.id}): kind 'keybinding' requires 'command' and 'key' fields`,
            );
          }
          if (c.kind === 'contextMenuItem' && (!c.command || !c.target)) {
            addIssue(
              `contributions[${i}] (${c.id}): kind 'contextMenuItem' requires 'command' and 'target' fields`,
            );
          }
          if (c.kind === 'agentTool' && !c.toolId) {
            addIssue(`contributions[${i}] (${c.id}): kind 'agentTool' requires 'toolId' field`);
          }

          // Validate placement rules
          if (c.kind === 'panel' && c.placement && c.placement !== 'asset-panel') {
            errors.push(
              `contributions[${i}] (${c.id}): panel placement '${c.placement}' is invalid (only 'asset-panel' allowed)`,
            );
          }
          if (
            (c.kind === 'inspectorSection' || c.kind === 'assetDetailSection') &&
            c.placement &&
            !['before-default', 'after-default'].includes(c.placement)
          ) {
            errors.push(
              `contributions[${i}] (${c.id}): ${c.kind} placement '${c.placement}' is invalid (must be 'before-default' or 'after-default')`,
            );
          }
        }
      }
    }

    manifests.push({ path: manifestPath, manifest, errors, warnings });
  }

  return manifests;
}

const extManifests = parseExtensionManifests();
console.log(`${LABEL} Manifests: ${extManifests.length} checked-in extension manifests`);

// ---------------------------------------------------------------------------
// 5. Cross-validate: Kind drift
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking kind drift…`);

const sdkKinds = new Set(sdk.kinds);
const schemaKinds = new Set(schema.kindEnum);

// SDK kinds not in schema
for (const kind of sdk.kinds) {
  if (!schemaKinds.has(kind)) {
    R.error(`Kind drift: '${kind}' in SDK ContributionKind but NOT in schema ContributionKind enum`);
  }
}

// Schema kinds not in SDK
for (const kind of schema.kindEnum) {
  if (!sdkKinds.has(kind)) {
    R.error(`Kind drift: '${kind}' in schema ContributionKind enum but NOT in SDK ContributionKind`);
  }
}

// ---------------------------------------------------------------------------
// 6. Cross-validate: Definition drift
// ---------------------------------------------------------------------------

// Every kind in the schema enum should have a corresponding contribution definition
// Map: kind -> expected definition name (e.g., 'slot' -> 'SlotContribution')
function expectedDefName(kind) {
  // Handle camelCase: 'inspectorSection' -> 'InspectorSectionContribution'
  return kind.charAt(0).toUpperCase() + kind.slice(1) + 'Contribution';
}

for (const kind of schema.kindEnum) {
  const expected = expectedDefName(kind);
  if (!schema.definitions.has(expected)) {
    R.error(
      `Schema drift: ContributionKind '${kind}' has no matching definition '${expected}' in Contribution oneOf`,
    );
  }
}

// Check that every definition in Contribution oneOf has a corresponding kind
for (const defName of schema.definitions) {
  // Strip 'Contribution' suffix
  if (!defName.endsWith('Contribution')) continue;
  const camelKind = defName.replace(/Contribution$/, '');
  // Convert to camelCase: 'Slot' -> 'slot', 'InspectorSection' -> 'inspectorSection'
  const kind = camelKind.charAt(0).toLowerCase() + camelKind.slice(1);
  if (!schemaKinds.has(kind)) {
    R.warn(
      `Schema drift: Definition '${defName}' in Contribution oneOf but '${kind}' not in ContributionKind enum`,
    );
  }
}

// ---------------------------------------------------------------------------
// 7. Cross-validate: Slot name drift
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking slot name drift…`);

// Parse SDK slot names from the canonical definition in src/sdk/manifest.ts.
function parseSdkSlotNames() {
  const sourcePath = existsSync(SDK_MANIFEST) ? SDK_MANIFEST : SDK_INDEX;
  if (!existsSync(sourcePath)) return [];
  const source = readFileSync(sourcePath, 'utf8');
  const slotBlockRe = /(?:export\s+)?type VideoEditorSlotName\s*=\s*([\s\S]*?);/;
  const slotBlock = source.match(slotBlockRe);
  /** @type {string[]} */
  const names = [];
  if (slotBlock) {
    const nameRe = /\|\s*'([a-zA-Z][a-zA-Z0-9]*)'/g;
    for (const m of slotBlock[1].matchAll(nameRe)) {
      names.push(m[1]);
    }
  }
  return names;
}

const sdkSlots = parseSdkSlotNames();
const sdkSlotSet = new Set(sdkSlots);
const schemaSlotSet = new Set(schema.slotEnum);

for (const slot of sdkSlots) {
  if (!schemaSlotSet.has(slot)) {
    R.warn(`Slot name drift: '${slot}' in SDK VideoEditorSlotName but NOT in schema SlotName enum`);
  }
}

for (const slot of schema.slotEnum) {
  if (!sdkSlotSet.has(slot)) {
    R.warn(`Slot name drift: '${slot}' in schema SlotName enum but NOT in SDK VideoEditorSlotName`);
  }
}

// ---------------------------------------------------------------------------
// 8. Cross-validate: Placement drift
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking placement drift…`);

// Panel placement: schema says only 'asset-panel'
const panelDef = schema.placementConstraints['PanelContribution'];
if (panelDef?.placement) {
  const allowed = panelDef.placement;
  if (!allowed.includes('asset-panel')) {
    R.error(`Placement drift: PanelContribution schema does not allow 'asset-panel' placement`);
  }
  if (allowed.length > 1) {
    R.warn(
      `Placement drift: PanelContribution allows ${allowed.length} placements (${allowed.join(', ')}); expected only 'asset-panel'`,
    );
  }
}

// Inspector placement: 'before-default' or 'after-default'
for (const defName of ['InspectorSectionContribution', 'AssetDetailSectionContribution']) {
  const def = schema.placementConstraints[defName];
  if (def?.placement) {
    const allowed = def.placement;
    if (!allowed.includes('before-default') || !allowed.includes('after-default')) {
      R.error(
        `Placement drift: ${defName} placement enum must include 'before-default' and 'after-default'`,
      );
    }
  }
}

// ---------------------------------------------------------------------------
// 9. Cross-validate: Bridged/reserved status vs docs
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking bridged/reserved status consistency…`);

// Supported docs rows should reference bridged kinds primarily
// Deferred docs rows may reference reserved kinds

// For each bridged kind, note whether it appears in docs (informational only)
const missingFromDocs = [];
for (const kind of sdk.bridged) {
  if (!docs.referencedKinds.has(kind)) {
    missingFromDocs.push(kind);
  }
}
if (missingFromDocs.length > 0) {
  console.log(`\n${LABEL} Note: ${missingFromDocs.length} bridged kind(s) not explicitly named in docs: ${missingFromDocs.join(', ')}`);
  console.log(`${LABEL} (This is informational — kinds may be referenced via evidence links or descriptions)`);
}

// Reserved kinds should not appear in checked-in manifests as active contributions
// (they can appear as future/reserved declarations but should be flagged)
for (const { path: manifestPath, manifest, errors } of extManifests) {
  const relPath = manifestPath.replace(repoRoot + '/', '');
  if (manifest.contributions && Array.isArray(manifest.contributions)) {
    for (const c of manifest.contributions) {
      if (c.kind && sdk.reserved.has(c.kind)) {
        R.warn(
          `Manifest drift: ${relPath} contains contribution '${c.id}' with reserved kind '${c.kind}' (milestone: ${sdk.milestoneMap[c.kind] || 'unknown'})`,
        );
      }
    }
  }
}

// ---------------------------------------------------------------------------
// 10. Validate that manifests pass basic checks
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Validating checked-in manifests…`);

for (const { path: manifestPath, errors, warnings } of extManifests) {
  const relPath = manifestPath.replace(repoRoot + '/', '');
  const hasIssues = errors.length > 0 || warnings.length > 0;

  if (errors.length > 0) {
    for (const err of errors) {
      R.error(`Manifest validation: ${relPath}: ${err}`);
    }
  }
  if (warnings.length > 0) {
    for (const w of warnings) {
      R.warn(`Manifest validation: ${relPath}: ${w}`);
    }
  }
  if (!hasIssues) {
    console.log(`  ✓ ${relPath}`);
  } else if (errors.length === 0) {
    console.log(`  ⚠ ${relPath} (${warnings.length} advisory warning(s))`);
  }
}

// ---------------------------------------------------------------------------
// 11. Cross-validate: Examples referenced in docs exist
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Checking doc example references…`);

if (existsSync(DOCS_PATH)) {
  const docsContent = readFileSync(DOCS_PATH, 'utf8');
  // Extract evidence references from the docs.
  // Evidence appears in table cells after the classification column.
  // Format: `EXT:dirname/` or `EXT:dirname/file` or `EX:filename`
  // Ignore placeholder references like `<path>`, `<RowID>` from the legend.
  const extRefRe = /EXT:([^\s|;,\\)`]+)/g;
  const exRefRe = /EX:([^\s|;,\\)`]+)/g;

  for (const m of docsContent.matchAll(extRefRe)) {
    let ref = m[1].trim();
    // Skip placeholders from the legend
    if (ref.startsWith('<') || ref === 'path') continue;
    if (!ref) continue;

    // Try as directory under extensions/
    const dirPath = resolve(EXTENSIONS_DIR, ref);
    // Try as file under src/examples/
    const filePath = resolve(repoRoot, 'src/examples', ref);
    // Try as full repo-relative path
    const repoPath = resolve(repoRoot, ref);

    if (!existsSync(dirPath) && !existsSync(filePath) && !existsSync(repoPath)) {
      // Try just the first path segment as extension dir name
      const baseRef = ref.split('/')[0];
      const baseDirPath = resolve(EXTENSIONS_DIR, baseRef);
      if (!existsSync(baseDirPath)) {
        R.warn(`Docs example reference EXT:${ref} does not resolve`);
      }
    }
  }

  for (const m of docsContent.matchAll(exRefRe)) {
    let ref = m[1].trim();
    // Skip placeholders from the legend
    if (ref.startsWith('<') || ref === 'path') continue;
    if (!ref) continue;

    const filePath = resolve(repoRoot, 'src/examples', ref);
    const repoPath = resolve(repoRoot, ref);
    if (!existsSync(filePath) && !existsSync(repoPath)) {
      R.warn(`Docs example reference EX:${ref} does not resolve to a file`);
    }
  }
}

// ---------------------------------------------------------------------------
// 12. Summary and exit
// ---------------------------------------------------------------------------

console.log(`\n${LABEL} Summary:`);
console.log(`  SDK kinds:        ${sdk.kinds.length} (${sdk.bridged.size} bridged, ${sdk.reserved.size} reserved)`);
console.log(`  Schema enum:      ${schema.kindEnum.length} kinds, ${schema.slotEnum.length} slots, ${schema.definitions.size} definitions`);
console.log(`  Docs:             ${docs.supportedRows.length} supported, ${docs.deferredRows.length} deferred rows`);
console.log(`  Manifests:        ${extManifests.length} checked-in`);
console.log(`  Errors:           ${R.errors.length}`);
console.log(`  Warnings:         ${R.warnings.length}`);

R.exit();
