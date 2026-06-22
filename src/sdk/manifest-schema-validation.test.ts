/**
 * T5: Ajv-backed schema validation coverage for checked-in reigh-extension.json
 * manifests and proof that unknown/unsupported top-level collections are rejected
 * by the frozen manifest contract.
 *
 * This test:
 *   1. Loads the canonical schema from config/contracts/reigh-extension.schema.json
 *   2. Compiles it with Ajv
 *   3. Validates every checked-in reigh-extension.json manifest at the top-level
 *      property boundary (proving they conform to the frozen contract's root shape)
 *   4. Proves that manifests with arbitrary top-level 'effects', 'transitions',
 *      or 'agentTools' collections (as root properties) are rejected by the schema
 *   5. Verifies the schema's structural invariants (additionalProperties: false,
 *      required fields, ContributionKind enum, oneOf contribution variants)
 */

import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import Ajv from 'ajv';

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const REPO_ROOT = path.resolve(import.meta.dirname, '../..');
const SCHEMA_PATH = path.join(
  REPO_ROOT,
  'config',
  'contracts',
  'reigh-extension.schema.json',
);
const EXTENSIONS_DIR = path.join(
  REPO_ROOT,
  'src',
  'tools',
  'video-editor',
  'examples',
  'extensions',
);

// ---------------------------------------------------------------------------
// Load and compile schema
// ---------------------------------------------------------------------------

const schemaRaw = fs.readFileSync(SCHEMA_PATH, 'utf-8');
const schema = JSON.parse(schemaRaw) as Record<string, unknown>;

const ajv = new Ajv({ allErrors: true });
const validateFn = ajv.compile(schema);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface ManifestFile {
  /** Absolute path to the reigh-extension.json file. */
  filePath: string;
  /** Extension directory name for diagnostics. */
  extensionName: string;
  /** The inner manifest object (extracted from the {manifest:...} envelope). */
  manifest: Record<string, unknown>;
}

/**
 * Walk the extensions directory and collect every reigh-extension.json file,
 * extracting the inner manifest object.
 */
function collectExtensionManifests(): ManifestFile[] {
  const results: ManifestFile[] = [];

  if (!fs.existsSync(EXTENSIONS_DIR)) {
    return results;
  }

  for (const entry of fs.readdirSync(EXTENSIONS_DIR, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name.startsWith('.')) continue;

    const manifestPath = path.join(
      EXTENSIONS_DIR,
      entry.name,
      'reigh-extension.json',
    );

    if (!fs.existsSync(manifestPath)) continue;

    try {
      const raw = fs.readFileSync(manifestPath, 'utf-8');
      const envelope = JSON.parse(raw);

      // The checked-in manifests use a {"manifest": {...}} envelope.
      // Extract the inner manifest object that corresponds to the schema root.
      const inner =
        envelope && typeof envelope === 'object' && 'manifest' in envelope
          ? (envelope as { manifest: Record<string, unknown> }).manifest
          : envelope;

      if (inner && typeof inner === 'object' && !Array.isArray(inner)) {
        results.push({
          filePath: manifestPath,
          extensionName: entry.name,
          manifest: inner as Record<string, unknown>,
        });
      }
    } catch (err) {
      throw new Error(
        `Failed to parse manifest at ${manifestPath}: ${(err as Error).message}`,
      );
    }
  }

  return results;
}

// ---------------------------------------------------------------------------
// Valid manifest builder (matches schema's required fields)
// ---------------------------------------------------------------------------

function baseValidManifest(): Record<string, unknown> {
  return {
    id: 'com.example.valid',
    version: '1.0.0',
    label: 'Valid Test Manifest',
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('T5: Manifest schema validation (Ajv-backed)', () => {
  // -- Checked-in manifest top-level property validation --------------------

  describe('Checked-in reigh-extension.json manifests — root shape conformance', () => {
    const manifests = collectExtensionManifests();

    it('finds at least one checked-in manifest to validate', () => {
      expect(manifests.length).toBeGreaterThan(0);
    });

    for (const mf of manifests) {
      it(`"${mf.extensionName}": root manifest has required fields (id, version, label) and no forbidden top-level collections`, () => {
        // Verify required fields exist
        expect(typeof mf.manifest.id).toBe('string');
        expect(mf.manifest.id.length).toBeGreaterThan(0);
        expect(typeof mf.manifest.version).toBe('string');
        expect(mf.manifest.version.length).toBeGreaterThan(0);
        expect(typeof mf.manifest.label).toBe('string');
        expect(mf.manifest.label.trim().length).toBeGreaterThan(0);

        // Verify NO forbidden top-level collections exist
        const forbiddenTopLevel = ['effects', 'transitions', 'agentTools'];
        for (const forbidden of forbiddenTopLevel) {
          expect(mf.manifest).not.toHaveProperty(forbidden);
        }

        // Verify only known top-level properties are present
        const knownTopLevel = new Set([
          'id', 'version', 'label', 'description', 'apiVersion',
          'contributions', 'permissions', 'processes', 'migrations',
          'comments', 'dependsOn', 'renderability', 'settingsDefaults',
          'settingsSchema', 'messages', 'publisher', 'license', 'icon',
          'integrity', // allowed in installed mode
        ]);

        for (const key of Object.keys(mf.manifest)) {
          expect(knownTopLevel.has(key)).toBe(true);
        }
      });
    }
  });

  // -- Rejection of unknown top-level collections (schema-level) ------------

  describe('Schema rejects unknown top-level collections (Ajv proof)', () => {
    it('rejects top-level "effects" array property', () => {
      const manifest = {
        ...baseValidManifest(),
        effects: [{ id: 'fx1', name: 'Glow' }],
      };
      const valid = validateFn(manifest);
      expect(valid).toBe(false);
      const messages = (validateFn.errors ?? []).map((e) => e.message);
      expect(messages.some((m) =>
        m.includes('additional properties') ||
        m.includes('additionalProperties'),
      )).toBe(true);
    });

    it('rejects top-level "transitions" array property', () => {
      const manifest = {
        ...baseValidManifest(),
        transitions: [{ id: 'tr1', name: 'Wipe' }],
      };
      const valid = validateFn(manifest);
      expect(valid).toBe(false);
      const messages = (validateFn.errors ?? []).map((e) => e.message);
      expect(messages.some((m) =>
        m.includes('additional properties') ||
        m.includes('additionalProperties'),
      )).toBe(true);
    });

    it('rejects top-level "agentTools" array property', () => {
      const manifest = {
        ...baseValidManifest(),
        agentTools: [{ id: 'at1', name: 'Search' }],
      };
      const valid = validateFn(manifest);
      expect(valid).toBe(false);
      const messages = (validateFn.errors ?? []).map((e) => e.message);
      expect(messages.some((m) =>
        m.includes('additional properties') ||
        m.includes('additionalProperties'),
      )).toBe(true);
    });

    it('rejects top-level "plugins" array (completely unknown)', () => {
      const manifest = {
        ...baseValidManifest(),
        plugins: [{ name: 'BadPlugin' }],
      };
      const valid = validateFn(manifest);
      expect(valid).toBe(false);
      const messages = (validateFn.errors ?? []).map((e) => e.message);
      expect(messages.some((m) =>
        m.includes('additional properties') ||
        m.includes('additionalProperties'),
      )).toBe(true);
    });

    it('accepts a manifest WITHOUT any unknown top-level properties', () => {
      const manifest = {
        ...baseValidManifest(),
        description: 'A valid extension',
        apiVersion: 1,
        publisher: 'Test Corp',
        license: 'MIT',
        contributions: [],
      };
      const valid = validateFn(manifest);
      expect(valid).toBe(true);
    });

    it('rejects a manifest with known AND ONE unknown top-level property (effects)', () => {
      const manifest = {
        ...baseValidManifest(),
        description: 'Mostly valid',
        apiVersion: 1,
        publisher: 'Test Corp',
        license: 'MIT',
        contributions: [
          {
            id: 'c1',
            kind: 'command',
            command: 'test.cmd',
            label: 'Test',
          },
        ],
        effects: [{ id: 'bad-fx', name: 'Bad' }],
      };
      const valid = validateFn(manifest);
      expect(valid).toBe(false);
      const messages = (validateFn.errors ?? []).map((e) => e.message);
      expect(messages.some((m) =>
        m.includes('additional properties') ||
        m.includes('additionalProperties'),
      )).toBe(true);
    });

    it('rejects top-level "transitions" with known properties present', () => {
      const manifest = {
        ...baseValidManifest(),
        publisher: 'Test',
        license: 'MIT',
        contributions: [],
        transitions: [{ id: 't1', name: 'Crossfade' }],
      };
      const valid = validateFn(manifest);
      expect(valid).toBe(false);
    });

    it('rejects top-level "agentTools" with known properties present', () => {
      const manifest = {
        ...baseValidManifest(),
        publisher: 'Test',
        license: 'MIT',
        contributions: [],
        agentTools: [{ id: 'a1', name: 'Analyze' }],
      };
      const valid = validateFn(manifest);
      expect(valid).toBe(false);
    });
  });

  // -- Schema structural checks --------------------------------------------

  describe('Schema structural invariants', () => {
    it('has additionalProperties: false on the root object', () => {
      expect(schema.additionalProperties).toBe(false);
    });

    it('requires id, version, and label', () => {
      expect(Array.isArray(schema.required)).toBe(true);
      const required = schema.required as string[];
      expect(required).toContain('id');
      expect(required).toContain('version');
      expect(required).toContain('label');
    });

    it('defines ContributionKind enum with all known kinds', () => {
      const defs = schema.definitions as Record<string, unknown>;
      expect(defs).toBeDefined();
      const kindDef = defs['ContributionKind'] as Record<string, unknown>;
      expect(kindDef).toBeDefined();
      const kindEnum = kindDef['enum'] as string[];
      expect(Array.isArray(kindEnum)).toBe(true);
      expect(kindEnum).toContain('slot');
      expect(kindEnum).toContain('panel');
      expect(kindEnum).toContain('command');
      expect(kindEnum).toContain('effect');
      expect(kindEnum).toContain('transition');
      expect(kindEnum).toContain('agentTool');
      expect(kindEnum).toContain('shader');
      expect(kindEnum).toContain('clipType');
      expect(kindEnum).toContain('parser');
    });

    it('defines Contribution oneOf with all expected contribution variants', () => {
      const defs = schema.definitions as Record<string, unknown>;
      const contrib = defs['Contribution'] as Record<string, unknown>;
      const oneOf = contrib['oneOf'] as Array<{ $ref?: string }>;
      expect(Array.isArray(oneOf)).toBe(true);
      const refs = oneOf.map((o) => o.$ref ?? '');
      expect(refs.some((r) => r.includes('EffectContribution'))).toBe(true);
      expect(refs.some((r) => r.includes('TransitionContribution'))).toBe(true);
      expect(refs.some((r) => r.includes('AgentToolContribution'))).toBe(true);
      expect(refs.some((r) => r.includes('ShaderContribution'))).toBe(true);
    });

    it('defines allowed top-level properties matching the frozen contract', () => {
      const props = schema.properties as Record<string, unknown>;
      expect(props).toBeDefined();
      const allowedKeys = Object.keys(props);
      // Verify key properties are allowed
      expect(allowedKeys).toContain('id');
      expect(allowedKeys).toContain('contributions');
      expect(allowedKeys).toContain('permissions');
      expect(allowedKeys).toContain('processes');
      expect(allowedKeys).toContain('settingsSchema');
      expect(allowedKeys).toContain('messages');
      // Verify forbidden keys are NOT in allowed properties
      expect(allowedKeys).not.toContain('effects');
      expect(allowedKeys).not.toContain('transitions');
      expect(allowedKeys).not.toContain('agentTools');
    });
  });
});
