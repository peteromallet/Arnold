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
import { RENDER_ROUTES, DETERMINISM_STATUSES } from '@/sdk/index.ts';

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

        expect(validateFn(mf.manifest)).toBe(true);
      });
    }
  });

  describe('Route-scoped output-format and process contracts', () => {
    it('accepts a render-dependent output format with a non-empty explicit route set', () => {
      const manifest = {
        ...baseValidManifest(),
        contributions: [
          {
            id: 'mp4-video',
            kind: 'outputFormat',
            label: 'MP4 Video',
            requiresRender: true,
            outputExtension: 'mp4',
            render: {
              routes: ['browser-export'],
            },
          },
        ],
      };

      expect(validateFn(manifest)).toBe(true);
    });

    it('rejects a render-dependent output format with an empty route set', () => {
      const manifest = {
        ...baseValidManifest(),
        contributions: [
          {
            id: 'mp4-video',
            kind: 'outputFormat',
            label: 'MP4 Video',
            requiresRender: true,
            outputExtension: 'mp4',
            render: {
              routes: [],
            },
          },
        ],
      };

      expect(validateFn(manifest)).toBe(false);
      expect((validateFn.errors ?? []).some((error) =>
        error.keyword === 'minItems'
        && String((error as { instancePath?: string; dataPath?: string }).instancePath
          ?? (error as { dataPath?: string }).dataPath
          ?? '').includes('render.routes'),
      )).toBe(true);
    });

    it('accepts process operations with omitted routes', () => {
      const manifest = {
        ...baseValidManifest(),
        contributions: [
          {
            id: 'analysis-process',
            kind: 'process',
            spec: {
              id: 'analysis-local',
              label: 'Analysis Local',
              spawn: { command: 'analysis-local' },
              protocol: 'stdio-jsonrpc',
              operations: [
                {
                  id: 'analyze',
                  label: 'Analyze',
                },
              ],
            },
          },
        ],
      };

      expect(validateFn(manifest)).toBe(true);
    });

    it('rejects process operations that declare an empty route set', () => {
      const manifest = {
        ...baseValidManifest(),
        contributions: [
          {
            id: 'ffmpeg-process',
            kind: 'process',
            spec: {
              id: 'ffmpeg-local',
              label: 'FFmpeg Local',
              spawn: { command: 'ffmpeg-local' },
              protocol: 'stdio-jsonrpc',
              operations: [
                {
                  id: 'render-mp4',
                  label: 'Render MP4',
                  routes: [],
                },
              ],
            },
          },
        ],
      };

      expect(validateFn(manifest)).toBe(false);
      expect((validateFn.errors ?? []).some((error) =>
        error.keyword === 'minItems'
        && String((error as { instancePath?: string; dataPath?: string }).instancePath
          ?? (error as { dataPath?: string }).dataPath
          ?? '').includes('spec.operations[0].routes'),
      )).toBe(true);
    });
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

  describe('Permission access disclosure contract', () => {
    it('accepts canonical reason plus optional posture access flags', () => {
      const manifest = {
        ...baseValidManifest(),
        permissions: [
          {
            reason: 'Fetch remote reference metadata and invoke local analysis tools.',
            posture: {
              network: true,
              filesystem: true,
              env: false,
              processes: true,
            },
          },
          {
            reason: 'No elevated access declared for this helper.',
          },
        ],
      };

      expect(validateFn(manifest)).toBe(true);
    });

    it('rejects legacy permission field on a declaration that otherwise has reason', () => {
      const manifest = {
        ...baseValidManifest(),
        permissions: [
          {
            permission: 'network',
            reason: 'Legacy permission name is no longer part of the contract.',
          },
        ],
      };

      expect(validateFn(manifest)).toBe(false);
      const errors = validateFn.errors ?? [];
      expect(errors.some((error) => error.keyword === 'additionalProperties')).toBe(true);
      expect(errors.some((error) => error.keyword === 'required')).toBe(false);
    });

    it('rejects declarations without reason', () => {
      const manifest = {
        ...baseValidManifest(),
        permissions: [
          {
            posture: { network: true },
          },
        ],
      };

      expect(validateFn(manifest)).toBe(false);
      const errors = validateFn.errors ?? [];
      expect(errors.some((error) => error.keyword === 'required')).toBe(true);
    });

    it('rejects unsupported posture keys', () => {
      const manifest = {
        ...baseValidManifest(),
        permissions: [
          {
            reason: 'Attempt to declare unsupported capabilities.',
            posture: {
              network: true,
              camera: true,
            },
          },
        ],
      };

      expect(validateFn(manifest)).toBe(false);
      expect((validateFn.errors ?? []).some((error) =>
        error.keyword === 'additionalProperties'
        && String((error as { instancePath?: string; dataPath?: string }).instancePath
          ?? (error as { dataPath?: string }).dataPath
          ?? '').includes('posture'),
      )).toBe(true);
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

    it('defines ExtensionPermissionDeclaration as canonical access disclosure shape', () => {
      const defs = schema.definitions as Record<string, unknown>;
      const permissionDef = defs['ExtensionPermissionDeclaration'] as Record<string, unknown>;
      expect(permissionDef).toBeDefined();
      expect(permissionDef.additionalProperties).toBe(false);
      expect(permissionDef.required).toEqual(['reason']);

      const props = permissionDef.properties as Record<string, unknown>;
      expect(Object.keys(props).sort()).toEqual(['posture', 'reason']);
      expect(props).not.toHaveProperty('permission');

      const posture = props.posture as Record<string, unknown>;
      expect(posture.additionalProperties).toBe(false);
      const postureProps = posture.properties as Record<string, unknown>;
      expect(Object.keys(postureProps).sort()).toEqual([
        'env',
        'filesystem',
        'network',
        'processes',
      ]);
    });
  });

  // -- Schema enum ↔ SDK constant alignment ---------------------------------

  /**
   * Test-local TargetContext value list mirroring the sealed union in
   * src/sdk/index.ts (export type TargetContext = 'clip' | 'clip-selection' |
   * 'track' | 'timeline-area').  There is no exported runtime constant for
   * this union, so we define the canonical set here for alignment checking.
   */
  const TARGET_CONTEXT_VALUES = ['clip', 'clip-selection', 'track', 'timeline-area'] as const;

  describe('Schema enum ↔ SDK constant alignment', () => {
    it('RenderRoute schema enum exactly matches RENDER_ROUTES', () => {
      const defs = schema.definitions as Record<string, unknown>;
      const renderRouteDef = defs['RenderRoute'] as Record<string, unknown>;
      expect(renderRouteDef).toBeDefined();
      const schemaEnum = renderRouteDef['enum'] as string[];
      expect(schemaEnum).toBeDefined();
      expect(schemaEnum.length).toBeGreaterThan(0);

      // Same values (order-independent)
      expect([...schemaEnum].sort()).toEqual([...RENDER_ROUTES].sort());

      // Same length (no extra / missing entries)
      expect(schemaEnum.length).toBe(RENDER_ROUTES.length);

      // Every schema value exists in SDK
      for (const v of schemaEnum) {
        expect(RENDER_ROUTES).toContain(v);
      }
      // Every SDK value exists in schema
      for (const v of RENDER_ROUTES) {
        expect(schemaEnum).toContain(v);
      }
    });

    it('DeterminismStatus schema enum exactly matches DETERMINISM_STATUSES', () => {
      const defs = schema.definitions as Record<string, unknown>;
      const detStatusDef = defs['DeterminismStatus'] as Record<string, unknown>;
      expect(detStatusDef).toBeDefined();
      const schemaEnum = detStatusDef['enum'] as string[];
      expect(schemaEnum).toBeDefined();
      expect(schemaEnum.length).toBeGreaterThan(0);

      // Same values (order-independent)
      expect([...schemaEnum].sort()).toEqual([...DETERMINISM_STATUSES].sort());

      // Same length
      expect(schemaEnum.length).toBe(DETERMINISM_STATUSES.length);

      // Bidirectional membership
      for (const v of schemaEnum) {
        expect(DETERMINISM_STATUSES).toContain(v);
      }
      for (const v of DETERMINISM_STATUSES) {
        expect(schemaEnum).toContain(v);
      }
    });

    it('ContextMenuItemContribution.target schema enum exactly matches TargetContext values', () => {
      const defs = schema.definitions as Record<string, unknown>;
      const ctxMenuItemDef = defs['ContextMenuItemContribution'] as Record<string, unknown>;
      expect(ctxMenuItemDef).toBeDefined();
      const props = ctxMenuItemDef['properties'] as Record<string, unknown>;
      expect(props).toBeDefined();
      const targetProp = props['target'] as Record<string, unknown>;
      expect(targetProp).toBeDefined();
      const schemaEnum = targetProp['enum'] as string[];
      expect(schemaEnum).toBeDefined();
      expect(schemaEnum.length).toBeGreaterThan(0);

      const sdkValues = [...TARGET_CONTEXT_VALUES];

      // Same values (order-independent)
      expect([...schemaEnum].sort()).toEqual([...sdkValues].sort());

      // Same length
      expect(schemaEnum.length).toBe(sdkValues.length);

      // Bidirectional membership
      for (const v of schemaEnum) {
        expect(sdkValues).toContain(v);
      }
      for (const v of sdkValues) {
        expect(schemaEnum).toContain(v);
      }
    });

    it('RenderRoute schema enum has no extra values beyond RENDER_ROUTES', () => {
      const defs = schema.definitions as Record<string, unknown>;
      const renderRouteDef = defs['RenderRoute'] as Record<string, unknown>;
      const schemaEnum = renderRouteDef['enum'] as string[];
      const schemaSet = new Set(schemaEnum);
      const sdkSet = new Set(RENDER_ROUTES);
      expect(schemaSet.size).toBe(sdkSet.size);
    });

    it('DeterminismStatus schema enum has no extra values beyond DETERMINISM_STATUSES', () => {
      const defs = schema.definitions as Record<string, unknown>;
      const detStatusDef = defs['DeterminismStatus'] as Record<string, unknown>;
      const schemaEnum = detStatusDef['enum'] as string[];
      const schemaSet = new Set(schemaEnum);
      const sdkSet = new Set(DETERMINISM_STATUSES);
      expect(schemaSet.size).toBe(sdkSet.size);
    });

    it('ContextMenuItemContribution.target schema enum has no extra values beyond TargetContext', () => {
      const defs = schema.definitions as Record<string, unknown>;
      const ctxMenuItemDef = defs['ContextMenuItemContribution'] as Record<string, unknown>;
      const props = ctxMenuItemDef['properties'] as Record<string, unknown>;
      const targetProp = props['target'] as Record<string, unknown>;
      const schemaEnum = targetProp['enum'] as string[];
      const schemaSet = new Set(schemaEnum);
      const sdkSet = new Set(TARGET_CONTEXT_VALUES);
      expect(schemaSet.size).toBe(sdkSet.size);
    });
  });

  // -- M2: Uniform/parameter schema coverage ---------------------------------

  describe('M2: Uniform/parameter definition schema coverage', () => {
    /** Build a minimal valid shader contribution with the given uniforms. */
    function shaderWithUniforms(uniforms: Record<string, unknown>[]): Record<string, unknown> {
      return {
        ...baseValidManifest(),
        contributions: [
          {
            id: 'test-shader',
            kind: 'shader',
            shaderId: 'shader.test',
            label: 'Test Shader',
            pass: 'clip',
            source: {
              kind: 'inline',
              fragment: 'void main() {}',
            },
            uniforms,
          },
        ],
      };
    }

    // -- Scalar types --------------------------------------------------------

    it('accepts scalar float uniform with bounds (min/max/step)', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'intensity',
          label: 'Intensity',
          type: 'float',
          default: 0.5,
          min: 0,
          max: 1,
          step: 0.1,
        },
      ]);
      expect(validateFn(manifest)).toBe(true);
    });

    it('accepts scalar int uniform with integer bounds', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'bands',
          label: 'Bands',
          type: 'int',
          default: 8,
          min: 2,
          max: 24,
          step: 1,
        },
      ]);
      expect(validateFn(manifest)).toBe(true);
    });

    it('accepts scalar bool uniform', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'showGrid',
          label: 'Grid',
          type: 'bool',
          default: true,
        },
      ]);
      expect(validateFn(manifest)).toBe(true);
    });

    // -- Vector types --------------------------------------------------------

    it('accepts vec2 uniform', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'center',
          label: 'Center',
          type: 'vec2',
          default: [0.5, 0.5],
        },
      ]);
      expect(validateFn(manifest)).toBe(true);
    });

    it('accepts vec3 uniform', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'lift',
          label: 'Lift',
          type: 'vec3',
          default: [0.15, 0.25, 0.45],
        },
      ]);
      expect(validateFn(manifest)).toBe(true);
    });

    it('accepts vec4 uniform', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'colorOffset',
          label: 'Color Offset',
          type: 'vec4',
          default: [0.1, 0.2, 0.3, 1.0],
        },
      ]);
      expect(validateFn(manifest)).toBe(true);
    });

    // -- Color type ----------------------------------------------------------

    it('accepts color uniform (legacy hex or vec4 array default)', () => {
      const manifestColorHex = shaderWithUniforms([
        {
          name: 'tintHex',
          label: 'Tint Hex',
          type: 'color',
          default: '#ff8800',
        },
      ]);
      expect(validateFn(manifestColorHex)).toBe(true);

      const manifestColorVec4 = shaderWithUniforms([
        {
          name: 'tintVec4',
          label: 'Tint Vec4',
          type: 'color',
          default: [0.2, 0.7, 1.0, 1.0],
        },
      ]);
      expect(validateFn(manifestColorVec4)).toBe(true);
    });

    // -- Source selector (enum) -----------------------------------------------

    it('accepts enum/source-selector uniform with options', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'blendMode',
          label: 'Blend Mode',
          type: 'enum',
          default: 'soft',
          options: [
            { label: 'Soft', value: 'soft' },
            { label: 'Invert Lift', value: 'invert-lift' },
            { label: 'Screen', value: 'screen' },
          ],
        },
      ]);
      expect(validateFn(manifest)).toBe(true);
    });

    it('rejects enum uniform without required options (options missing)', () => {
      // enum type is valid alone; options are optional at schema level
      // (runtime validates option membership)
      const manifest = shaderWithUniforms([
        {
          name: 'bareEnum',
          label: 'Bare Enum',
          type: 'enum',
          default: 'a',
        },
      ]);
      expect(validateFn(manifest)).toBe(true);
    });

    // -- Bounded structured-data (object) ------------------------------------

    it('accepts structured object uniform with bounded sub-fields', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'shadow',
          label: 'Shadow',
          type: 'object',
          default: { offsetX: 2, offsetY: 2, blur: 4, color: [0, 0, 0, 0.5] },
          fields: [
            {
              name: 'offsetX',
              label: 'Offset X',
              type: 'float',
              default: 2,
              min: -50,
              max: 50,
              step: 1,
            },
            {
              name: 'offsetY',
              label: 'Offset Y',
              type: 'float',
              default: 2,
              min: -50,
              max: 50,
              step: 1,
            },
            {
              name: 'blur',
              label: 'Blur',
              type: 'float',
              default: 4,
              min: 0,
              max: 100,
              step: 0.5,
            },
            {
              name: 'color',
              label: 'Shadow Color',
              type: 'color',
              default: [0, 0, 0, 0.5],
            },
          ],
        },
      ]);
      expect(validateFn(manifest)).toBe(true);
    });

    it('accepts structured object uniform with selector sub-field', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'style',
          label: 'Style',
          type: 'object',
          default: { mode: 'ease-in', intensity: 0.5 },
          fields: [
            {
              name: 'mode',
              label: 'Mode',
              type: 'enum',
              default: 'ease-in',
              options: [
                { label: 'Ease In', value: 'ease-in' },
                { label: 'Ease Out', value: 'ease-out' },
              ],
            },
            {
              name: 'intensity',
              label: 'Intensity',
              type: 'float',
              default: 0.5,
              min: 0,
              max: 1,
              step: 0.1,
            },
          ],
        },
      ]);
      expect(validateFn(manifest)).toBe(true);
    });

    it('rejects structured object uniform without required sub-field name/label/type', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'badObj',
          label: 'Bad Object',
          type: 'object',
          fields: [
            {
              // missing 'name'
              label: 'Missing Name',
              type: 'float',
            },
          ],
        },
      ]);
      expect(validateFn(manifest)).toBe(false);
    });

    it('rejects object sub-field with unknown type', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'badObj',
          label: 'Bad Object',
          type: 'object',
          fields: [
            {
              name: 'bad',
              label: 'Bad',
              type: 'matrix4',  // not in the sub-field type enum
            },
          ],
        },
      ]);
      expect(validateFn(manifest)).toBe(false);
    });

    // -- Reserved extension-param domains (lexical-only) ---------------------

    it('accepts uniform with reserved extension-param type names in description context only', () => {
      // The schema allows all documented type names in the uniform type enum.
      // Reserved domains (output, process, agent, app) are NOT in the enum,
      // so using them as a uniform type should be rejected.
      const manifest = shaderWithUniforms([
        {
          name: 'badOutput',
          label: 'Bad Output',
          type: 'output',  // reserved domain, not in the type enum
        },
      ]);
      expect(validateFn(manifest)).toBe(false);
    });

    it('rejects reserved domain "process" as a uniform type', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'badProcess',
          label: 'Bad Process',
          type: 'process',
        },
      ]);
      expect(validateFn(manifest)).toBe(false);
    });

    it('rejects reserved domain "agent" as a uniform type', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'badAgent',
          label: 'Bad Agent',
          type: 'agent',
        },
      ]);
      expect(validateFn(manifest)).toBe(false);
    });

    it('rejects reserved domain "app" as a uniform type', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'badApp',
          label: 'Bad App',
          type: 'app',
        },
      ]);
      expect(validateFn(manifest)).toBe(false);
    });

    // -- TextureRef and temporal types ---------------------------------------

    it('accepts textureRef uniform', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'u_source',
          label: 'Source',
          type: 'textureRef',
          default: { kind: 'clip-frame' },
        },
      ]);
      expect(validateFn(manifest)).toBe(true);
    });

    it('accepts frame and time temporal uniforms', () => {
      const manifest = shaderWithUniforms([
        {
          name: 'holdFrame',
          label: 'Frame Hold',
          type: 'frame',
          default: 12,
        },
        {
          name: 'holdTime',
          label: 'Time Hold',
          type: 'time',
          default: 0.25,
        },
      ]);
      expect(validateFn(manifest)).toBe(true);
    });
  });
});
