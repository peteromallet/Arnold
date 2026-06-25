#!/usr/bin/env node
/**
 * M1 Preview Truth — Extension Drift Gate Mismatch Coverage Tests
 *
 * Proves that the drift-check helpers detect intentional mismatches for:
 *   1. Kind drift        — SDK kind not in schema enum
 *   2. Placement drift   — schema placement ≠ expected values
 *   3. Schema def drift  — schema missing a definition for a known kind
 *   4. Manifest unknown  — checked-in manifest uses unknown kind
 *   5. Manifest placement— manifest violates placement rules
 *
 * Uses Node.js built-in test runner (node:test) and fixture files under
 * `scripts/quality/__fixtures__/`.
 */

import { describe, it } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  parseSdkContributionKinds,
  parseSchema,
  parseDocs,
  parseExtensionManifests,
  checkKindDrift,
  checkSchemaDefinitionDrift,
  checkPlacementDrift,
  parseSdkSlotNames,
  checkSlotNameDrift,
  runFullDriftCheck,
  readFileIfExists,
} from './lib/drift-check-helpers.mjs';

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const moduleDir = dirname(fileURLToPath(import.meta.url));
const fixturesDir = resolve(moduleDir, '__fixtures__');
const repoRoot = resolve(moduleDir, '..', '..');

function fixturePath(category, file) {
  return resolve(fixturesDir, category, file);
}

function extensionsDir(category) {
  return resolve(fixturesDir, category, 'extensions');
}

function readFixture(category, file) {
  const p = fixturePath(category, file);
  if (!existsSync(p)) throw new Error(`Fixture not found: ${p}`);
  return readFileSync(p, 'utf8');
}

function readRepoFile(relativePath) {
  const p = resolve(repoRoot, relativePath);
  if (!existsSync(p)) throw new Error(`Repo file not found: ${p}`);
  return readFileSync(p, 'utf8');
}

function extractStringUnion(source, typeName) {
  const block = source.match(new RegExp(`export type ${typeName}\\s*=\\s*([\\s\\S]*?);`));
  if (!block) return [];
  return [...block[1].matchAll(/'([^']+)'/g)].map((match) => match[1]);
}

function loadCurrentSchema() {
  return JSON.parse(readRepoFile('config/contracts/reigh-extension.schema.json'));
}

function loadFamilyMatrixRows() {
  const rows = JSON.parse(readRepoFile('config/extensions/family-maturity.json'));
  assert.ok(Array.isArray(rows), 'family-maturity.json should be an array');
  return rows;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Drift Check Helpers — Mismatch Coverage', () => {

  // -----------------------------------------------------------------------
  // 1. Kind drift
  // -----------------------------------------------------------------------
  describe('Kind drift detection', () => {
    it('detects SDK kind not present in schema ContributionKind enum', () => {
      const sdkSource = readFixture('kind-drift', 'sdk.ts');
      const schemaJson = readFixture('kind-drift', 'schema.json');

      const sdk = parseSdkContributionKinds(sdkSource);
      const schema = parseSchema(schemaJson);

      // SDK has 'bogusKind', schema does not
      assert.ok(sdk.kinds.includes('bogusKind'), 'SDK should have bogusKind');
      assert.ok(!schema.kindEnum.includes('bogusKind'), 'Schema should NOT have bogusKind');

      const errors = checkKindDrift(sdk.kinds, schema.kindEnum);
      assert.ok(errors.length > 0, 'Should have kind drift errors');
      assert.ok(
        errors.some(e => e.includes('bogusKind') && e.includes('NOT in schema')),
        `Error should mention bogusKind missing from schema. Got: ${errors.join('; ')}`,
      );
    });

    it('detects schema enum value not present in SDK kinds', () => {
      // The kind-drift schema has 'dialog' and 'panel' but SDK has 'slot', 'dialog', 'panel', 'bogusKind'
      // So all schema kinds are in SDK. Let's test the opposite: schema has extra kind.
      // We'll construct this manually.
      const errors = checkKindDrift(
        ['slot', 'dialog'],           // SDK
        ['slot', 'dialog', 'extraKind'], // Schema has extra
      );
      assert.ok(errors.length > 0, 'Should detect schema extra kind');
      assert.ok(
        errors.some(e => e.includes('extraKind') && e.includes('NOT in SDK')),
        `Error should mention extraKind missing from SDK. Got: ${errors.join('; ')}`,
      );
    });
  });

  // -----------------------------------------------------------------------
  // 2. Placement drift
  // -----------------------------------------------------------------------
  describe('Placement drift detection', () => {
    it('detects when PanelContribution allows non-asset-panel placements', () => {
      const schemaJson = readFixture('placement-drift', 'schema.json');
      const schema = parseSchema(schemaJson);

      const panelConstraints = schema.placementConstraints['PanelContribution'];
      assert.ok(panelConstraints, 'Should have PanelContribution constraints');
      assert.ok(panelConstraints.placement, 'Should have placement values');
      assert.ok(!panelConstraints.placement.includes('asset-panel'),
        'Panel placement should NOT include asset-panel in this fixture');

      const { errors, warnings } = checkPlacementDrift(schema.placementConstraints);
      assert.ok(errors.length > 0, 'Should have placement drift errors');
      assert.ok(
        errors.some(e => e.includes('asset-panel')),
        `Error should mention asset-panel. Got: ${errors.join('; ')}`,
      );
    });

    it('warns when PanelContribution has more than one placement', () => {
      const { warnings } = checkPlacementDrift({
        PanelContribution: { placement: ['asset-panel', 'extra-placement'] },
      });
      assert.ok(warnings.length > 0, 'Should warn about extra placements');
      assert.ok(
        warnings.some(w => w.includes('PanelContribution') && w.includes('2 placements')),
        `Warning should mention multiple placements. Got: ${warnings.join('; ')}`,
      );
    });

    it('detects when InspectorSectionContribution is missing required placements', () => {
      const { errors } = checkPlacementDrift({
        InspectorSectionContribution: { placement: ['before-default'] },
      });
      assert.ok(errors.length > 0, 'Should error on missing after-default');
      assert.ok(
        errors.some(e => e.includes('InspectorSectionContribution')),
        `Error should mention InspectorSectionContribution. Got: ${errors.join('; ')}`,
      );
    });
  });

  // -----------------------------------------------------------------------
  // 3. Schema definition drift
  // -----------------------------------------------------------------------
  describe('Schema definition drift detection', () => {
    it('detects when a kind in the schema enum has no matching Contribution definition', () => {
      const schemaJson = readFixture('schema-definition-drift', 'schema.json');
      const schema = parseSchema(schemaJson);

      // Schema has 'panel' in the enum but no PanelContribution definition
      assert.ok(schema.kindEnum.includes('panel'), 'Schema enum should have panel');
      assert.ok(!schema.definitions.has('PanelContribution'),
        'Schema definitions should NOT have PanelContribution');

      const errors = checkSchemaDefinitionDrift(schema.kindEnum, schema.definitions);
      assert.ok(errors.length > 0, 'Should have schema definition drift errors');
      assert.ok(
        errors.some(e => e.includes('panel') && e.includes('PanelContribution')),
        `Error should mention panel/PanelContribution. Got: ${errors.join('; ')}`,
      );
    });
  });

  // -----------------------------------------------------------------------
  // 4. Manifest unknown kind
  // -----------------------------------------------------------------------
  describe('Manifest unknown-kind detection', () => {
    it('detects when a checked-in manifest uses an unknown contribution kind', () => {
      const sdkSource = readFixture('manifest-unknown-kind', 'sdk.ts');
      const sdk = parseSdkContributionKinds(sdkSource);

      const manifests = parseExtensionManifests(
        extensionsDir('manifest-unknown-kind'),
        sdk.kinds,
      );

      assert.ok(manifests.length > 0, 'Should have at least one manifest');

      const badManifest = manifests[0];
      assert.ok(badManifest.errors.length > 0, 'Manifest should have errors');
      assert.ok(
        badManifest.errors.some(e => e.includes('garbageKind') && e.includes('unknown kind')),
        `Error should mention garbageKind as unknown. Got: ${badManifest.errors.join('; ')}`,
      );
    });

    it('reports unknown kind as a hard error, not a warning', () => {
      const sdkSource = readFixture('manifest-unknown-kind', 'sdk.ts');
      const sdk = parseSdkContributionKinds(sdkSource);

      const manifests = parseExtensionManifests(
        extensionsDir('manifest-unknown-kind'),
        sdk.kinds,
      );

      const badManifest = manifests[0];
      assert.ok(badManifest.errors.length > 0, 'Unknown kind must be an error');
      // The unknown-kind error should be in errors, not warnings
      const hasUnknownKindError = badManifest.errors.some(
        e => e.includes('garbageKind') && e.includes('unknown kind'),
      );
      assert.ok(hasUnknownKindError, 'Unknown kind must be classified as error');
    });
  });

  // -----------------------------------------------------------------------
  // 5. Manifest placement mismatch
  // -----------------------------------------------------------------------
  describe('Manifest placement mismatch detection', () => {
    it('detects invalid panel placement in manifest', () => {
      const sdkSource = readFixture('manifest-placement-mismatch', 'sdk.ts');
      const sdk = parseSdkContributionKinds(sdkSource);

      const manifests = parseExtensionManifests(
        extensionsDir('manifest-placement-mismatch'),
        sdk.kinds,
      );

      assert.ok(manifests.length > 0, 'Should have at least one manifest');

      const badManifest = manifests[0];
      assert.ok(badManifest.errors.length > 0, 'Manifest should have placement errors');
      assert.ok(
        badManifest.errors.some(
          e => e.includes('panel') && e.includes('wrong-spot') && e.includes('invalid'),
        ),
        `Error should mention invalid panel placement. Got: ${badManifest.errors.join('; ')}`,
      );
    });

    it('detects invalid inspectorSection placement in manifest', () => {
      const sdkSource = readFixture('manifest-placement-mismatch', 'sdk.ts');
      const sdk = parseSdkContributionKinds(sdkSource);

      const manifests = parseExtensionManifests(
        extensionsDir('manifest-placement-mismatch'),
        sdk.kinds,
      );

      const badManifest = manifests[0];
      assert.ok(
        badManifest.errors.some(
          e => e.includes('inspectorSection') && e.includes('middle') && e.includes('invalid'),
        ),
        `Error should mention invalid inspectorSection placement. Got: ${badManifest.errors.join('; ')}`,
      );
    });
  });

  // -----------------------------------------------------------------------
  // 6. Full drift check integration
  // -----------------------------------------------------------------------
  describe('Full drift check integration', () => {
    it('runFullDriftCheck catches kind drift', () => {
      const result = runFullDriftCheck({
        sdkSource: readFixture('kind-drift', 'sdk.ts'),
        schemaJson: readFixture('kind-drift', 'schema.json'),
        docsContent: readFixture('kind-drift', 'docs.md'),
        extensionsDir: extensionsDir('kind-drift'),
      });

      assert.ok(result.allErrors.length > 0, 'Full check should catch kind drift errors');
      assert.ok(
        result.allErrors.some(e => e.includes('bogusKind')),
        `Should have bogusKind error. Errors: ${result.allErrors.join('; ')}`,
      );
    });

    it('runFullDriftCheck catches placement drift', () => {
      const result = runFullDriftCheck({
        sdkSource: readFixture('placement-drift', 'sdk.ts'),
        schemaJson: readFixture('placement-drift', 'schema.json'),
        docsContent: readFixture('placement-drift', 'docs.md'),
        extensionsDir: extensionsDir('placement-drift'),
      });

      assert.ok(result.allErrors.length > 0, 'Full check should catch placement drift errors');
      assert.ok(
        result.allErrors.some(e => e.includes('asset-panel') || e.includes('PanelContribution')),
        `Should have placement error. Errors: ${result.allErrors.join('; ')}`,
      );
    });

    it('runFullDriftCheck catches schema definition drift', () => {
      const result = runFullDriftCheck({
        sdkSource: readFixture('schema-definition-drift', 'sdk.ts'),
        schemaJson: readFixture('schema-definition-drift', 'schema.json'),
        docsContent: readFixture('schema-definition-drift', 'docs.md'),
        extensionsDir: extensionsDir('schema-definition-drift'),
      });

      assert.ok(result.allErrors.length > 0, 'Full check should catch schema def drift');
      assert.ok(
        result.allErrors.some(e => e.includes('PanelContribution')),
        `Should have PanelContribution error. Errors: ${result.allErrors.join('; ')}`,
      );
    });

    it('runFullDriftCheck catches manifest unknown kind', () => {
      const result = runFullDriftCheck({
        sdkSource: readFixture('manifest-unknown-kind', 'sdk.ts'),
        schemaJson: readFixture('manifest-unknown-kind', 'schema.json'),
        docsContent: readFixture('manifest-unknown-kind', 'docs.md'),
        extensionsDir: extensionsDir('manifest-unknown-kind'),
      });

      assert.ok(result.allErrors.length > 0, 'Full check should catch manifest unknown kind');
      assert.ok(
        result.allErrors.some(e => e.includes('garbageKind')),
        `Should have garbageKind error. Errors: ${result.allErrors.join('; ')}`,
      );
    });

    it('runFullDriftCheck catches manifest placement mismatch', () => {
      const result = runFullDriftCheck({
        sdkSource: readFixture('manifest-placement-mismatch', 'sdk.ts'),
        schemaJson: readFixture('manifest-placement-mismatch', 'schema.json'),
        docsContent: readFixture('manifest-placement-mismatch', 'docs.md'),
        extensionsDir: extensionsDir('manifest-placement-mismatch'),
      });

      assert.ok(result.allErrors.length > 0, 'Full check should catch manifest placement mismatch');
      assert.ok(
        result.allErrors.some(e => e.includes('wrong-spot') || e.includes('middle')),
        `Should have placement errors. Errors: ${result.allErrors.join('; ')}`,
      );
    });

    it('runFullDriftCheck passes when everything matches (clean fixture)', () => {
      // Construct a clean scenario where everything is consistent
      const cleanSdk = `export type ContributionKind = | 'slot' | 'dialog' | 'panel';
export type VideoEditorSlotName = | 'header' | 'toolbar';
export const KNOWN_CONTRIBUTION_KINDS: readonly any[] = ['slot','dialog','panel'] as const;
export const CONTRIBUTION_KIND_MILESTONE: Record<string,string|undefined> = {slot:'M1',dialog:'M1',panel:'M1'};
export function contributionKindNotYetBridged(k:any){return null;}`;

      const cleanSchema = JSON.stringify({
        definitions: {
          ContributionKind: { enum: ['slot', 'dialog', 'panel'] },
          SlotName: { enum: ['header', 'toolbar'] },
          Contribution: {
            oneOf: [
              { $ref: '#/definitions/SlotContribution' },
              { $ref: '#/definitions/DialogContribution' },
              { $ref: '#/definitions/PanelContribution' },
            ],
          },
          SlotContribution: {
            type: 'object',
            required: ['id', 'kind'],
            properties: { id: { type: 'string' }, kind: { const: 'slot' }, slot: { $ref: '#/definitions/SlotName' } },
          },
          DialogContribution: {
            type: 'object',
            required: ['id', 'kind'],
            properties: { id: { type: 'string' }, kind: { const: 'dialog' } },
          },
          PanelContribution: {
            type: 'object',
            required: ['id', 'kind'],
            properties: { id: { type: 'string' }, kind: { const: 'panel' }, placement: { enum: ['asset-panel'] } },
          },
        },
      });

      const cleanDocs = '# Docs\n| S-001 | slot stuff | **supported** | TEST:slot |\n';

      // Use an existing clean fixture dir
      const result = runFullDriftCheck({
        sdkSource: cleanSdk,
        schemaJson: cleanSchema,
        docsContent: cleanDocs,
        extensionsDir: extensionsDir('kind-drift'), // the manifest here only uses 'slot' which is valid
      });

      // 'kind-drift' fixtures dir has a valid manifest — but the SDK/schema we pass are clean.
      // The manifest from kind-drift uses 'slot' which is valid.
      // No drift errors expected from cross-validation.
      const driftErrors = result.allErrors.filter(
        e => e.includes('drift') || e.includes('NOT in schema') || e.includes('NOT in SDK'),
      );
      assert.strictEqual(driftErrors.length, 0,
        `Clean check should have no drift errors. Got: ${driftErrors.join('; ')}`,
      );
    });
  });

  // -----------------------------------------------------------------------
  // 7. Slot name drift (bonus coverage)
  // -----------------------------------------------------------------------
  describe('Slot name drift detection', () => {
    it('detects SDK slot name not in schema SlotName enum', () => {
      const sdkSlotNames = ['header', 'toolbar', 'mysterySlot'];
      const schemaSlotEnum = ['header', 'toolbar'];

      const warnings = checkSlotNameDrift(sdkSlotNames, schemaSlotEnum);
      assert.ok(warnings.length > 0, 'Should detect slot name drift');
      assert.ok(
        warnings.some(w => w.includes('mysterySlot')),
        `Should mention mysterySlot. Got: ${warnings.join('; ')}`,
      );
    });

    it('detects schema SlotName not in SDK slot names', () => {
      const sdkSlotNames = ['header'];
      const schemaSlotEnum = ['header', 'extraSlot'];

      const warnings = checkSlotNameDrift(sdkSlotNames, schemaSlotEnum);
      assert.ok(warnings.length > 0, 'Should detect reverse slot drift');
      assert.ok(
        warnings.some(w => w.includes('extraSlot')),
        `Should mention extraSlot. Got: ${warnings.join('; ')}`,
      );
    });

    it('reports no warnings when slots match', () => {
      const warnings = checkSlotNameDrift(
        ['header', 'toolbar'],
        ['header', 'toolbar'],
      );
      assert.strictEqual(warnings.length, 0, 'Matching slots should have no warnings');
    });
  });

  // -----------------------------------------------------------------------
  // 8. Real schema vocabulary drift guards
  // -----------------------------------------------------------------------
  describe('Current schema vocabulary drift guards', () => {
    const schema = loadCurrentSchema();
    const schemaDefs = schema.definitions || {};
    const renderingSource = readRepoFile('src/sdk/video/rendering/renderability.ts');
    const sdkIndexSource = readRepoFile('src/sdk/index.ts');

    it('keeps RenderRoute enum aligned to the SDK RenderRoute union', () => {
      const schemaEnum = schemaDefs.RenderRoute?.enum || [];
      const sdkUnion = extractStringUnion(renderingSource, 'RenderRoute');
      assert.deepStrictEqual(schemaEnum, sdkUnion);
    });

    it('keeps DeterminismStatus enum aligned to the SDK DeterminismStatus union', () => {
      const schemaEnum = schemaDefs.DeterminismStatus?.enum || [];
      const sdkUnion = extractStringUnion(renderingSource, 'DeterminismStatus');
      assert.deepStrictEqual(schemaEnum, sdkUnion);
    });

    it('keeps ContextMenuItemContribution.target aligned to the SDK TargetContext union', () => {
      const schemaEnum = schemaDefs.ContextMenuItemContribution?.properties?.target?.enum || [];
      const sdkUnion = extractStringUnion(sdkIndexSource, 'TargetContext');
      assert.deepStrictEqual(schemaEnum, sdkUnion);
    });

    it('keeps shader pass/source/fallback vocabulary aligned to SDK unions', () => {
      const passEnum = schemaDefs.ShaderContribution?.properties?.pass?.oneOf?.[0]?.enum || [];
      const sourceKinds = schemaDefs.ShaderContribution?.properties?.source?.oneOf?.map(
        (entry) => entry?.properties?.kind?.const,
      ) || [];
      const fallbackEnum = schemaDefs.ShaderContribution?.properties?.fallback?.enum || [];

      assert.deepStrictEqual(passEnum, extractStringUnion(sdkIndexSource, 'ShaderPassKind'));
      assert.deepStrictEqual(sourceKinds, ['inline', 'module']);
      assert.deepStrictEqual(fallbackEnum, extractStringUnion(sdkIndexSource, 'ShaderFallbackBehavior'));
    });

    it('keeps shader texture and uniform vocabulary aligned to SDK unions', () => {
      const uniformTypeEnum =
        schemaDefs.ShaderContribution?.properties?.uniforms?.items?.properties?.type?.enum || [];
      const textureSourceKindEnum =
        schemaDefs.ShaderContribution?.properties?.textures?.items?.properties?.sourceKind?.enum || [];
      const textureFilterEnum =
        schemaDefs.ShaderContribution?.properties?.textures?.items?.properties?.filter?.enum || [];
      const textureWrapEnum =
        schemaDefs.ShaderContribution?.properties?.textures?.items?.properties?.wrap?.enum || [];
      const passColorSpaceEnum =
        schemaDefs.ShaderContribution?.properties?.pass?.oneOf?.[1]?.properties?.colorSpace?.enum || [];

      assert.deepStrictEqual(uniformTypeEnum, extractStringUnion(sdkIndexSource, 'ShaderUniformType'));
      assert.deepStrictEqual(textureSourceKindEnum, extractStringUnion(sdkIndexSource, 'ShaderTextureSourceKind'));
      assert.deepStrictEqual(textureFilterEnum, extractStringUnion(sdkIndexSource, 'ShaderTextureFilter'));
      assert.deepStrictEqual(textureWrapEnum, extractStringUnion(sdkIndexSource, 'ShaderTextureWrap'));
      assert.deepStrictEqual(passColorSpaceEnum, extractStringUnion(sdkIndexSource, 'ShaderColorSpace'));
    });
  });

  // -----------------------------------------------------------------------
  // 9. Contribution schema ↔ family mapping guards
  // -----------------------------------------------------------------------
  describe('Current contribution schema-to-family mapping guards', () => {
    const schema = loadCurrentSchema();
    const matrixRows = loadFamilyMatrixRows();
    const schemaDefs = schema.definitions || {};
    const contributionRefs = (schemaDefs.Contribution?.oneOf || []).map((entry) =>
      String(entry?.$ref || '').replace('#/definitions/', ''),
    );

    const familyByKind = new Map(matrixRows.map((row) => [row.kind, row]));
    const familyBySchemaDefinition = new Map(
      matrixRows.map((row) => [row.manifestSchemaDefinition, row]),
    );

    // Known many-to-one or host-owned schema aliases are explicit here so future
    // additions do not silently bypass coverage.
    const explicitDefinitionKinds = new Map([
      ['AutomationContribution', 'automation'],
    ]);
    const explicitHostOnlyDefinitions = new Set([]);

    it('maps every contribution-like schema definition to a family or explicit host-only classification', () => {
      const unmapped = [];

      for (const defName of contributionRefs) {
        if (familyBySchemaDefinition.has(defName) || explicitHostOnlyDefinitions.has(defName)) {
          continue;
        }

        const explicitKind = explicitDefinitionKinds.get(defName);
        if (explicitKind) {
          assert.ok(
            familyByKind.has(explicitKind),
            `${defName} explicit kind '${explicitKind}' should exist in family matrix`,
          );
          continue;
        }

        const kindConst = schemaDefs[defName]?.properties?.kind?.const;
        if (typeof kindConst === 'string' && familyByKind.has(kindConst)) {
          continue;
        }

        unmapped.push(defName);
      }

      assert.deepStrictEqual(unmapped, []);
    });

    it('keeps every family definition anchored to declared contribution schema coverage', () => {
      const contributionRefSet = new Set(contributionRefs);
      const missing = [];

      for (const row of matrixRows) {
        const hasDeclaredDefinition = contributionRefSet.has(row.manifestSchemaDefinition);
        const hasExplicitAlias = [...explicitDefinitionKinds.entries()].some(
          ([defName, kind]) => kind === row.kind && contributionRefSet.has(defName),
        );

        if (!hasDeclaredDefinition && !hasExplicitAlias) {
          missing.push(`${row.kind}:${row.manifestSchemaDefinition}`);
        }
      }

      assert.deepStrictEqual(missing, []);
    });
  });
});
