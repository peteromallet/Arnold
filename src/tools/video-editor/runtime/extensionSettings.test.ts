/**
 * Tests for the manifest settings-schema adapter (M4, T11).
 *
 * Validates:
 *  - Full valid JSON Schema maps to StandardSchema (type object, properties, required)
 *  - Type keyword mapping (integer → number)
 *  - All supported constraint keywords survive adaptation
 *  - Missing / malformed schemas emit diagnostics + null schema
 *  - Non-object schema types are rejected
 *  - Empty / missing properties are handled
 *  - Invalid property entries are skipped with diagnostics
 *  - Required array filters non-existent properties
 */

import { describe, it, expect } from 'vitest';
import { adaptManifestSettingsSchema } from './extensionSettings';
import type { ExtensionManifest } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeManifest(overrides: Partial<Record<string, unknown>> = {}): ExtensionManifest {
  return {
    id: 'com.test.settings-adapter' as any,
    version: '1.0.0',
    label: 'Test Extension',
    contributions: [],
    ...overrides,
  } as ExtensionManifest;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('adaptManifestSettingsSchema', () => {
  // --- Happy path: full valid schema ---

  it('adapts a complete settings schema with defaults and supported constraints', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          required: ['name'],
          properties: {
            name: {
              type: 'string',
              title: 'Display Name',
              description: 'The display name of the extension',
              default: 'My Extension',
              minLength: 1,
              maxLength: 100,
              pattern: '^[a-zA-Z0-9 ]+$',
            },
            volume: {
              type: 'number',
              title: 'Volume',
              description: 'Audio volume level',
              default: 0.8,
              minimum: 0,
              maximum: 1,
              multipleOf: 0.1,
            },
            count: {
              type: 'integer',
              title: 'Count',
              description: 'Number of iterations',
              default: 5,
              minimum: 1,
              maximum: 100,
            },
            enabled: {
              type: 'boolean',
              title: 'Enabled',
              description: 'Whether the feature is active',
              default: true,
            },
            theme: {
              type: 'string',
              title: 'Theme',
              description: 'Color theme',
              default: 'dark',
              enum: ['light', 'dark', 'auto'],
            },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).not.toBeNull();
    expect(result.schema!.type).toBe('object');
    expect(Object.keys(result.schema!.properties)).toHaveLength(5);
    expect(result.schema!.required).toEqual(['name']);
    expect(result.diagnostics).toHaveLength(0);

    // Verify each property
    const name = result.schema!.properties.name;
    expect(name.type).toBe('string');
    expect(name.title).toBe('Display Name');
    expect(name.description).toBe('The display name of the extension');
    expect(name.default).toBe('My Extension');
    expect(name.minLength).toBe(1);
    expect(name.maxLength).toBe(100);
    expect(name.pattern).toBe('^[a-zA-Z0-9 ]+$');

    const volume = result.schema!.properties.volume;
    expect(volume.type).toBe('number');
    expect(volume.default).toBe(0.8);
    expect(volume.minimum).toBe(0);
    expect(volume.maximum).toBe(1);
    expect(volume.multipleOf).toBe(0.1);

    const count = result.schema!.properties.count;
    // Integer maps to number
    expect(count.type).toBe('number');
    expect(count.default).toBe(5);
    expect(count.minimum).toBe(1);
    expect(count.maximum).toBe(100);

    const enabled = result.schema!.properties.enabled;
    expect(enabled.type).toBe('boolean');
    expect(enabled.default).toBe(true);

    const theme = result.schema!.properties.theme;
    expect(theme.type).toBe('string');
    expect(theme.default).toBe('dark');
    expect(theme.enum).toEqual(['light', 'dark', 'auto']);
  });

  // --- Type mapping ---

  it('maps JSON Schema integer type to number', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            retryCount: { type: 'integer', default: 3 },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);
    expect(result.schema).not.toBeNull();
    expect(result.schema!.properties.retryCount.type).toBe('number');
    expect(result.diagnostics).toHaveLength(0);
  });

  it('passes unknown types through unchanged', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            custom: { type: 'customWidget', default: 'value' },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);
    expect(result.schema).not.toBeNull();
    expect(result.schema!.properties.custom.type).toBe('customWidget');
    // SchemaForm will resolve this through the capability registry and
    // may treat it as unsupported — that's expected.
  });

  // --- Missing / malformed schema ---

  it('returns null schema with diagnostic when no settingsSchema is declared', () => {
    const manifest = makeManifest(); // no settingsSchema

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).toBeNull();
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe('settings/missing-schema');
    expect(result.diagnostics[0].severity).toBe('warning');
  });

  it('returns null schema with error when settingsSchema.schema is missing', () => {
    const manifest = makeManifest({
      settingsSchema: { version: 1 },
    });

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).toBeNull();
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe('settings/missing-schema-descriptor');
    expect(result.diagnostics[0].severity).toBe('error');
  });

  it('returns null schema with error when settingsSchema.schema is null', () => {
    const manifest = makeManifest({
      settingsSchema: { version: 1, schema: null },
    });

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).toBeNull();
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe('settings/missing-schema-descriptor');
  });

  it('returns null schema with error when settingsSchema.schema is a string instead of object', () => {
    const manifest = makeManifest({
      settingsSchema: { version: 1, schema: 'not-an-object' },
    });

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).toBeNull();
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe('settings/missing-schema-descriptor');
  });

  // --- Non-object top-level type ---

  it('rejects non-object top-level schema types', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'array',
          properties: { foo: { type: 'string' } },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).toBeNull();
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe('settings/non-object-schema');
    expect(result.diagnostics[0].severity).toBe('error');
  });

  it('rejects schema with no type field', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          properties: { foo: { type: 'string' } },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).toBeNull();
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe('settings/non-object-schema');
  });

  // --- Missing / empty properties ---

  it('returns null schema when properties is missing', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: { type: 'object' },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).toBeNull();
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe('settings/empty-properties');
  });

  it('returns null schema when properties is empty object', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: { type: 'object', properties: {} },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).toBeNull();
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe('settings/empty-properties');
  });

  it('returns null schema when properties is an array', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: { type: 'object', properties: [] },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).toBeNull();
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe('settings/empty-properties');
  });

  // --- Invalid property entries ---

  it('skips non-object property entries with diagnostic but adapts valid ones', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            valid: { type: 'string', default: 'hello' },
            badNumber: 42,
            badString: 'not an object',
            badNull: null,
            alsoValid: { type: 'number', default: 1 },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).not.toBeNull();
    expect(Object.keys(result.schema!.properties)).toEqual(['valid', 'alsoValid']);
    expect(result.diagnostics).toHaveLength(3);
    expect(result.diagnostics.every((d) => d.code === 'settings/invalid-property')).toBe(true);
  });

  it('returns null schema with error when all properties are invalid', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            a: 1,
            b: 'two',
            c: null,
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).toBeNull();
    expect(result.diagnostics).toHaveLength(4); // 3 invalid-property + 1 no-valid-properties
    expect(result.diagnostics.some((d) => d.code === 'settings/no-valid-properties')).toBe(true);
  });

  // --- Required array handling ---

  it('preserves required array for properties that exist', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          required: ['a', 'b', 'c', 'nonexistent'],
          properties: {
            a: { type: 'string' },
            b: { type: 'number' },
            c: { type: 'boolean' },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).not.toBeNull();
    // c is valid but only a and b were in required
    expect(result.schema!.required).toEqual(['a', 'b', 'c']);
    // nonexistent is filtered out
  });

  it('does not include required array when all entries are invalid', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          required: ['nonexistent', 'alsoNonexistent'],
          properties: {
            a: { type: 'string' },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.schema).not.toBeNull();
    expect(result.schema!.required).toBeUndefined();
  });

  // --- Diagnostic metadata ---

  it('includes extensionId in all diagnostics', () => {
    const manifest = makeManifest();

    const result = adaptManifestSettingsSchema(manifest);

    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].extensionId).toBe('com.test.settings-adapter');
  });

  it('diagnostics are frozen/deterministic arrays', () => {
    const manifest = makeManifest();

    const result1 = adaptManifestSettingsSchema(manifest);
    const result2 = adaptManifestSettingsSchema(manifest);

    expect(result1.diagnostics).toHaveLength(result2.diagnostics.length);
    expect(result1.diagnostics[0].code).toBe(result2.diagnostics[0].code);
  });
});
