/**
 * M1 Preview Truth — Drift Check Helpers
 *
 * Pure parsing and validation functions extracted from check-extension-drift.mjs
 * so they can be unit-tested with fixture files without touching the real
 * repository sources.
 *
 * Every function accepts explicit paths (or content strings) and returns
 * structured data — no process.exit, no global state, no side effects.
 */

import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';

// ---------------------------------------------------------------------------
// 0. Load bridged/reserved authority from the generated family maturity matrix
// ---------------------------------------------------------------------------

/**
 * Load bridged/reserved classification from the generated family maturity
 * JSON matrix.  This is the canonical source of truth for bridge/reserved
 * status — it derives from the TypeScript registry via the generator.
 *
 * @param {string} matrixPath - Path to config/extensions/family-maturity.json
 * @returns {{ bridged: Set<string>, reserved: Set<string>, milestoneMap: Record<string, string> }}
 */
export function loadFamilyMaturityMatrix(matrixPath) {
  /** @type {Set<string>} */
  const bridged = new Set();
  /** @type {Set<string>} */
  const reserved = new Set();
  /** @type {Record<string, string>} */
  const milestoneMap = {};

  if (!existsSync(matrixPath)) {
    return { bridged, reserved, milestoneMap };
  }

  /** @type {any[]} */
  let matrix;
  try {
    matrix = JSON.parse(readFileSync(matrixPath, 'utf8'));
  } catch {
    return { bridged, reserved, milestoneMap };
  }

  if (!Array.isArray(matrix)) {
    return { bridged, reserved, milestoneMap };
  }

  for (const row of matrix) {
    const kind = row.kind;
    if (!kind || typeof kind !== 'string') continue;

    const legacy = row.legacyCompatibility;
    const milestone = legacy?.milestone;
    if (milestone && typeof milestone === 'string') {
      milestoneMap[kind] = milestone;
    }

    if (legacy?.bridged === true) {
      bridged.add(kind);
    } else {
      reserved.add(kind);
    }
  }

  return { bridged, reserved, milestoneMap };
}

// ---------------------------------------------------------------------------
// 1. Parse SDK ContributionKind and bridged/reserved status
// ---------------------------------------------------------------------------

/**
 * Parse the ContributionKind type union from an SDK source string.
 * Looks for `export type ContributionKind = …` and extracts string literals.
 *
 * When `externalAuthority` is supplied (from the family maturity matrix),
 * bridged/reserved classification and milestoneMap come from the registry.
 * Otherwise the legacy regex-parsed milestone logic is used — this preserves
 * compatibility with old-shape fixtures that intentionally exercise the
 * legacy parsing path.
 *
 * @param {string} source - Raw TypeScript source of the SDK index file.
 * @param {{ bridged?: Set<string>, reserved?: Set<string>, milestoneMap?: Record<string, string> }} [externalAuthority]
 * @returns {{
 *   kinds: string[],
 *   bridged: Set<string>,
 *   reserved: Set<string>,
 *   milestoneMap: Record<string, string>
 * }}
 */
export function parseSdkContributionKinds(source, externalAuthority) {
  const kindRe = /\|\s*'([a-zA-Z][a-zA-Z0-9]*)'/g;

  // Try the original ContributionKind type alias (legacy inline union).
  const kindBlockRe = /export type ContributionKind\s*=\s*([\s\S]*?);/;
  const kindBlock = source.match(kindBlockRe);

  /** @type {string[]} */
  const kinds = [];
  if (kindBlock) {
    for (const m of kindBlock[1].matchAll(kindRe)) {
      if (!kinds.includes(m[1])) kinds.push(m[1]);
    }
  }

  // If the above is a type alias (e.g. `= VideoContributionKind`), look for
  // the VideoContributionKind union in the same source or a combined contributionKinds.ts.
  if (kinds.length === 0) {
    const videoKindBlockRe = /export type VideoContributionKind\s*=\s*([\s\S]*?);/;
    const videoKindBlock = source.match(videoKindBlockRe);
    if (videoKindBlock) {
      for (const m of videoKindBlock[1].matchAll(kindRe)) {
        if (!kinds.includes(m[1])) kinds.push(m[1]);
      }
    }
  }

  // Also extract KNOWN_CONTRIBUTION_KINDS / VIDEO_CONTRIBUTION_KINDS array.
  const knownArrayRe = /export const (?:KNOWN_CONTRIBUTION_KINDS|VIDEO_CONTRIBUTION_KINDS)[\s\S]*?=\s*\[([\s\S]*?)\]\s*as const/;
  const knownArrayMatch = source.match(knownArrayRe);
  /** @type {string[]} */
  const knownArrayKinds = [];
  if (knownArrayMatch) {
    for (const m of knownArrayMatch[1].matchAll(kindRe)) {
      if (!knownArrayKinds.includes(m[1])) knownArrayKinds.push(m[1]);
    }
  }

  // If external authority is provided, use it for bridged/reserved/milestoneMap.
  if (externalAuthority) {
    // If regex parsing found 0 kinds, derive kinds from the external authority.
    /** @type {string[]} */
    let resolvedKinds = kinds;
    if (resolvedKinds.length === 0) {
      const matrixKinds = Object.keys(externalAuthority.milestoneMap || {});
      if (matrixKinds.length > 0) {
        resolvedKinds = matrixKinds.sort();
      }
    }

    /** @type {Set<string>} */
    const bridged = new Set(externalAuthority.bridged || []);
    /** @type {Set<string>} */
    const reserved = new Set(externalAuthority.reserved || []);

    // Only classify kinds that are in the external authority.
    // Kinds not in the authority default to reserved.
    for (const kind of resolvedKinds) {
      if (!bridged.has(kind) && !reserved.has(kind)) {
        reserved.add(kind);
      }
    }

    return {
      kinds: resolvedKinds,
      bridged,
      reserved,
      milestoneMap: { ...(externalAuthority.milestoneMap || {}) },
    };
  }

  // Legacy path: regex-parse CONTRIBUTION_KIND_MILESTONE and apply
  // hard-coded milestone-to-bridged logic.  Kept for old-shape fixture
  // compatibility — real drift checks pass externalAuthority instead.

  // Parse CONTRIBUTION_KIND_MILESTONE
  const milestoneRe = /export const CONTRIBUTION_KIND_MILESTONE[\s\S]*?=\s*\{([\s\S]*?)\};/;
  const milestoneMatch = source.match(milestoneRe);
  /** @type {Record<string, string>} */
  const milestoneMap = {};
  if (milestoneMatch) {
    const entryRe = /(\w+)\s*:\s*'([^']*)'/g;
    for (const m of milestoneMatch[1].matchAll(entryRe)) {
      milestoneMap[m[1]] = m[2];
    }
  }

  // Determine bridged vs reserved (mirrors contributionKindNotYetBridged logic)
  /** @type {Set<string>} */
  const bridged = new Set();
  /** @type {Set<string>} */
  const reserved = new Set();

  for (const kind of kinds) {
    const milestone = milestoneMap[kind];
    if (!milestone) {
      reserved.add(kind);
      continue;
    }

    if (milestone === 'M1' || milestone === 'M2') {
      bridged.add(kind);
      continue;
    }

    if (milestone === 'M4') {
      if (kind === 'command' || kind === 'keybinding' || kind === 'contextMenuItem') {
        bridged.add(kind);
      } else {
        reserved.add(kind);
      }
      continue;
    }

    if (milestone === 'M6') {
      if (kind === 'parser' || kind === 'metadataFacet' || kind === 'assetDetailSection') {
        bridged.add(kind);
      } else {
        reserved.add(kind);
      }
      continue;
    }

    if (milestone === 'M7' && kind === 'effect') {
      bridged.add(kind);
      continue;
    }

    if (milestone === 'M8' && kind === 'transition') {
      bridged.add(kind);
      continue;
    }

    if (milestone === 'M9' && (kind === 'clipType' || kind === 'automation')) {
      bridged.add(kind);
      continue;
    }

    if (milestone === 'M10' && (kind === 'agentTool' || kind === 'agent')) {
      bridged.add(kind);
      continue;
    }

    if (milestone === 'M13' && kind === 'shader') {
      bridged.add(kind);
      continue;
    }

    reserved.add(kind);
  }

  return { kinds, bridged, reserved, milestoneMap };
}

// ---------------------------------------------------------------------------
// 2. Parse schema enums and definitions
// ---------------------------------------------------------------------------

/**
 * Parse the JSON schema content and extract contribution-relevant enums and definitions.
 *
 * @param {string} schemaJson - Raw JSON schema string.
 * @returns {{
 *   kindEnum: string[],
 *   slotEnum: string[],
 *   definitions: Set<string>,
 *   placementConstraints: Record<string, {placement?: string[], slot?: boolean}>
 * }}
 */
export function parseSchema(schemaJson) {
  /** @type {any} */
  let schema;
  try {
    schema = JSON.parse(schemaJson);
  } catch (e) {
    return { kindEnum: [], slotEnum: [], definitions: new Set(), placementConstraints: {} };
  }

  const defs = schema.definitions || {};

  /** @type {string[]} */
  const kindEnum = defs.ContributionKind?.enum || [];

  /** @type {string[]} */
  const slotEnum = defs.SlotName?.enum || [];

  /** @type {Set<string>} */
  const definitions = new Set();
  const contributionDef = defs.Contribution;
  if (contributionDef?.oneOf) {
    for (const item of contributionDef.oneOf) {
      const ref = item.$ref || '';
      const name = ref.replace('#/definitions/', '');
      if (name) definitions.add(name);
    }
  }

  /** @type {Record<string, {placement?: string[], slot?: boolean}>} */
  const placementConstraints = {};

  for (const [defName, def] of Object.entries(defs)) {
    if (!defName.endsWith('Contribution') || defName === 'Contribution') continue;
    if (typeof def !== 'object' || !def) continue;

    const constraints = {};

    if (def.properties?.placement) {
      const placementProp = def.properties.placement;
      if (placementProp.enum) {
        constraints.placement = placementProp.enum;
      } else if (placementProp.const) {
        constraints.placement = [placementProp.const];
      }
    }

    if (def.properties?.slot) {
      constraints.slot = true;
    }

    placementConstraints[defName] = constraints;
  }

  return { kindEnum, slotEnum, definitions, placementConstraints };
}

// ---------------------------------------------------------------------------
// 3. Parse docs supported/deferred rows
// ---------------------------------------------------------------------------

/**
 * Parse the supported/deferred matrix doc content.
 *
 * @param {string} content - Raw markdown content.
 * @param {string[]} knownKinds - List of known kind strings to scan for.
 * @returns {{
 *   supportedRows: string[],
 *   deferredRows: string[],
 *   referencedKinds: Set<string>
 * }}
 */
export function parseDocs(content, knownKinds) {
  /** @type {string[]} */
  const supportedRows = [];
  /** @type {string[]} */
  const deferredRows = [];
  /** @type {Set<string>} */
  const referencedKinds = new Set();

  const sRowRe = /\|\s*(S-\d+)\s*\|/g;
  for (const m of content.matchAll(sRowRe)) {
    supportedRows.push(m[1]);
  }

  const dRowRe = /\|\s*(D-\d+)\s*\|/g;
  for (const m of content.matchAll(dRowRe)) {
    deferredRows.push(m[1]);
  }

  for (const kind of knownKinds) {
    const escaped = kind.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`\\b${escaped}\\b`, 'i');
    if (re.test(content)) {
      referencedKinds.add(kind);
    }
  }

  return { supportedRows, deferredRows, referencedKinds };
}

// ---------------------------------------------------------------------------
// 4. Parse extension manifests from a directory
// ---------------------------------------------------------------------------

/**
 * Walk a directory and collect/validate extension manifests.
 *
 * @param {string} extensionsDir - Path to extensions directory.
 * @param {string[]} knownKinds - Known contribution kinds from SDK.
 * @returns {Array<{path: string, manifest: any, errors: string[], warnings: string[]}>}
 */
export function parseExtensionManifests(extensionsDir, knownKinds) {
  /** @type {Array<{path: string, manifest: any, errors: string[], warnings: string[]}>} */
  const manifests = [];

  if (!existsSync(extensionsDir)) {
    return manifests;
  }

  for (const entry of readdirSync(extensionsDir, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name.startsWith('.') || entry.name === '__tests__') continue;

    const manifestPath = resolve(extensionsDir, entry.name, 'reigh-extension.json');
    if (!existsSync(manifestPath)) continue;

    /** @type {any} */
    let raw;
    try {
      raw = JSON.parse(readFileSync(manifestPath, 'utf8'));
    } catch (e) {
      manifests.push({
        path: manifestPath,
        manifest: null,
        errors: [`Parse error: ${e.message}`],
        warnings: [],
      });
      continue;
    }

    const manifest = raw.manifest || raw;
    /** @type {string[]} */
    const errors = [];
    /** @type {string[]} */
    const warnings = [];

    validateManifestFields(manifest, errors);
    validateManifestContributions(manifest, knownKinds, errors, warnings);

    manifests.push({ path: manifestPath, manifest, errors, warnings });
  }

  return manifests;
}

/**
 * Validate top-level manifest fields.
 * @param {any} manifest
 * @param {string[]} errors
 */
function validateManifestFields(manifest, errors) {
  if (!manifest.id || typeof manifest.id !== 'string') {
    errors.push(`Missing or invalid 'id' field`);
  }
  if (!manifest.version || typeof manifest.version !== 'string') {
    errors.push(`Missing or invalid 'version' field`);
  }
  if (!manifest.label || typeof manifest.label !== 'string') {
    errors.push(`Missing or invalid 'label' field`);
  }
}

/**
 * Validate manifest contributions array.
 * @param {any} manifest
 * @param {string[]} knownKinds
 * @param {string[]} errors
 * @param {string[]} warnings
 */
function validateManifestContributions(manifest, knownKinds, errors, warnings) {
  const contributions = manifest.contributions;
  if (!Array.isArray(contributions)) {
    if (contributions !== undefined) {
      errors.push(`'contributions' must be an array`);
    }
    return;
  }

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
      if (!knownKinds.includes(c.kind)) {
        errors.push(
          `contributions[${i}] (${c.id}) has unknown kind '${c.kind}' — not in SDK ContributionKind`,
        );
      }

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

// ---------------------------------------------------------------------------
// 5. Cross-validation helpers (pure functions)
// ---------------------------------------------------------------------------

/**
 * Check kind drift between SDK kinds and schema kind enum.
 * @returns {string[]} drift errors
 */
export function checkKindDrift(sdkKinds, schemaKindEnum) {
  /** @type {string[]} */
  const errors = [];
  const sdkSet = new Set(sdkKinds);
  const schemaSet = new Set(schemaKindEnum);

  for (const kind of sdkKinds) {
    if (!schemaSet.has(kind)) {
      errors.push(`Kind drift: '${kind}' in SDK ContributionKind but NOT in schema ContributionKind enum`);
    }
  }
  for (const kind of schemaKindEnum) {
    if (!sdkSet.has(kind)) {
      errors.push(`Kind drift: '${kind}' in schema ContributionKind enum but NOT in SDK ContributionKind`);
    }
  }
  return errors;
}

/**
 * Check schema definition drift.
 * @returns {string[]} drift errors
 */
export function checkSchemaDefinitionDrift(schemaKindEnum, schemaDefinitions) {
  /** @type {string[]} */
  const errors = [];

  for (const kind of schemaKindEnum) {
    const expected = kind.charAt(0).toUpperCase() + kind.slice(1) + 'Contribution';
    if (!schemaDefinitions.has(expected)) {
      errors.push(
        `Schema drift: ContributionKind '${kind}' has no matching definition '${expected}' in Contribution oneOf`,
      );
    }
  }

  return errors;
}

/**
 * Check slot name drift between SDK slot names and schema slot enum.
 * @returns {string[]} drift warnings
 */
export function checkSlotNameDrift(sdkSlotNames, schemaSlotEnum) {
  /** @type {string[]} */
  const warnings = [];
  const sdkSet = new Set(sdkSlotNames);
  const schemaSet = new Set(schemaSlotEnum);

  for (const slot of sdkSlotNames) {
    if (!schemaSet.has(slot)) {
      warnings.push(`Slot name drift: '${slot}' in SDK VideoEditorSlotName but NOT in schema SlotName enum`);
    }
  }
  for (const slot of schemaSlotEnum) {
    if (!sdkSet.has(slot)) {
      warnings.push(`Slot name drift: '${slot}' in schema SlotName enum but NOT in SDK VideoEditorSlotName`);
    }
  }
  return warnings;
}

/**
 * Check placement drift between schema constraints and expected values.
 * @returns {{ errors: string[], warnings: string[] }}
 */
export function checkPlacementDrift(placementConstraints) {
  /** @type {string[]} */
  const errors = [];
  /** @type {string[]} */
  const warnings = [];

  // Panel placement: schema should only allow 'asset-panel'
  const panelDef = placementConstraints['PanelContribution'];
  if (panelDef?.placement) {
    const allowed = panelDef.placement;
    if (!allowed.includes('asset-panel')) {
      errors.push(`Placement drift: PanelContribution schema does not allow 'asset-panel' placement`);
    }
    if (allowed.length > 1) {
      warnings.push(
        `Placement drift: PanelContribution allows ${allowed.length} placements (${allowed.join(', ')}); expected only 'asset-panel'`,
      );
    }
  }

  // Inspector placement: 'before-default' or 'after-default'
  for (const defName of ['InspectorSectionContribution', 'AssetDetailSectionContribution']) {
    const def = placementConstraints[defName];
    if (def?.placement) {
      const allowed = def.placement;
      if (!allowed.includes('before-default') || !allowed.includes('after-default')) {
        errors.push(
          `Placement drift: ${defName} placement enum must include 'before-default' and 'after-default'`,
        );
      }
    }
  }

  return { errors, warnings };
}

/**
 * Check manifest drift — look for unknown kinds, placement violations, and
 * reserved-kind usage in the given manifest list.
 *
 * @returns {{ errors: string[], warnings: string[] }}
 */
export function checkManifestDrift(manifests, reservedKinds, repoRoot) {
  /** @type {string[]} */
  const errors = [];
  /** @type {string[]} */
  const warnings = [];

  for (const { path: manifestPath, errors: manifestErrors, warnings: manifestWarnings, manifest } of manifests) {
    const relPath = repoRoot ? manifestPath.replace(repoRoot + '/', '') : manifestPath;

    for (const err of manifestErrors) {
      errors.push(`Manifest validation: ${relPath}: ${err}`);
    }
    for (const w of manifestWarnings) {
      warnings.push(`Manifest validation: ${relPath}: ${w}`);
    }

    // Check reserved kinds in manifests
    if (manifest?.contributions && Array.isArray(manifest.contributions)) {
      for (const c of manifest.contributions) {
        if (c.kind && reservedKinds.has(c.kind)) {
          warnings.push(
            `Manifest drift: ${relPath} contains contribution '${c.id}' with reserved kind '${c.kind}'`,
          );
        }
      }
    }
  }

  return { errors, warnings };
}

/**
 * Parse SDK slot names from source.
 * @param {string} source
 * @returns {string[]}
 */
export function parseSdkSlotNames(source) {
  const slotBlockRe = /export type VideoEditorSlotName\s*=\s*([\s\S]*?);/;
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

/**
 * Read a file and return its content, or null if not found.
 * @param {string} path
 * @returns {string|null}
 */
export function readFileIfExists(path) {
  if (!existsSync(path)) return null;
  return readFileSync(path, 'utf8');
}

/**
 * Run a full drift check against arbitrary files and return structured results.
 *
 * When `familyMaturityPath` is provided, bridged/reserved classification
 * comes from the generated matrix instead of legacy regex-parsed milestone
 * logic.  This is the production path — the family maturity matrix is the
 * canonical source of truth.
 *
 * @param {object} opts
 * @param {string} opts.sdkSource - SDK index.ts content
 * @param {string} opts.schemaJson - Schema JSON content
 * @param {string} opts.docsContent - Docs markdown content
 * @param {string} opts.extensionsDir - Path to extensions directory
 * @param {string} [opts.repoRoot] - For relative path reporting
 * @param {string} [opts.familyMaturityPath] - Path to config/extensions/family-maturity.json
 * @returns {{
 *   sdk: ReturnType<typeof parseSdkContributionKinds>,
 *   schema: ReturnType<typeof parseSchema>,
 *   docs: ReturnType<typeof parseDocs>,
 *   manifests: ReturnType<typeof parseExtensionManifests>,
 *   allErrors: string[],
 *   allWarnings: string[]
 * }}
 */
export function runFullDriftCheck(opts) {
  const { sdkSource, schemaJson, docsContent, extensionsDir, repoRoot, familyMaturityPath } = opts;

  // Load registry-based authority when available.
  const externalAuthority = familyMaturityPath
    ? loadFamilyMaturityMatrix(familyMaturityPath)
    : undefined;

  const sdk = parseSdkContributionKinds(sdkSource, externalAuthority);
  const schema = parseSchema(schemaJson);
  const docs = parseDocs(docsContent, sdk.kinds);
  const manifests = parseExtensionManifests(extensionsDir, sdk.kinds);

  /** @type {string[]} */
  const allErrors = [];
  /** @type {string[]} */
  const allWarnings = [];

  // Kind drift
  allErrors.push(...checkKindDrift(sdk.kinds, schema.kindEnum));

  // Schema definition drift
  allErrors.push(...checkSchemaDefinitionDrift(schema.kindEnum, schema.definitions));

  // Slot name drift
  const sdkSlots = parseSdkSlotNames(sdkSource);
  allWarnings.push(...checkSlotNameDrift(sdkSlots, schema.slotEnum));

  // Placement drift
  const { errors: placementErrors, warnings: placementWarnings } = checkPlacementDrift(schema.placementConstraints);
  allErrors.push(...placementErrors);
  allWarnings.push(...placementWarnings);

  // Manifest drift
  const { errors: manifestErrors, warnings: manifestWarnings } = checkManifestDrift(
    manifests,
    sdk.reserved,
    repoRoot || '',
  );
  allErrors.push(...manifestErrors);
  allWarnings.push(...manifestWarnings);

  // Bridged/reserved status consistency (docs)
  for (const kind of sdk.bridged) {
    if (!docs.referencedKinds.has(kind)) {
      // Informational only — not a warning in audit mode
    }
  }

  return { sdk, schema, docs, manifests, allErrors, allWarnings };
}
