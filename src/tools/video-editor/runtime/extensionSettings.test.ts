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
import {
  adaptManifestSettingsSchema,
  analyzeManifestSettingsSchema,
  detectUnsupportedShape,
  materializeSettingsDefaults,
  reconcileSettingsSnapshot,
} from './extensionSettings';
import type { ReconciliationResult } from './extensionSettings';
import type { StandardSchemaProperty } from '@/tools/video-editor/components/SchemaForm/SchemaForm';
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

  // --- Unsupported marker preservation (T1) ---

  it('preserves $ref marker through adaptation', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            ref: { $ref: '#/definitions/SomeType', title: 'Reference' },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);
    expect(result.schema).not.toBeNull();
    expect(result.schema!.properties.ref.$ref).toBe('#/definitions/SomeType');
    expect(result.schema!.properties.ref.type).toBeUndefined();
  });

  it('preserves oneOf marker through adaptation', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            val: { oneOf: [{ type: 'string' }, { type: 'number' }] },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);
    expect(result.schema).not.toBeNull();
    expect(result.schema!.properties.val.oneOf).toEqual([{ type: 'string' }, { type: 'number' }]);
  });

  it('preserves anyOf marker through adaptation', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            mixed: { anyOf: [{ type: 'string' }, { type: 'number' }] },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);
    expect(result.schema).not.toBeNull();
    expect(result.schema!.properties.mixed.anyOf).toEqual([{ type: 'string' }, { type: 'number' }]);
  });

  it('preserves allOf marker through adaptation', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            combined: { allOf: [{ minLength: 3 }, { maxLength: 10 }] },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);
    expect(result.schema).not.toBeNull();
    expect(result.schema!.properties.combined.allOf).toHaveLength(2);
  });

  it('preserves array/items markers through adaptation', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            tags: { type: 'array', items: { type: 'string' }, title: 'Tags' },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);
    expect(result.schema).not.toBeNull();
    expect(result.schema!.properties.tags.type).toBe('array');
    expect(result.schema!.properties.tags.items).toEqual({ type: 'string' });
  });

  it('preserves nested object properties marker through adaptation', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            config: {
              type: 'object',
              properties: { nested: { type: 'string' } },
            },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);
    expect(result.schema).not.toBeNull();
    expect(result.schema!.properties.config.type).toBe('object');
    expect(result.schema!.properties.config.properties).toEqual({ nested: { type: 'string' } });
  });

  it('preserves conditional (if/then/else) markers through adaptation', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            dynamic: {
              if: { type: 'string' },
              then: { type: 'number' },
              else: { type: 'boolean' },
            },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);
    expect(result.schema).not.toBeNull();
    expect(result.schema!.properties.dynamic.if).toEqual({ type: 'string' });
    expect(result.schema!.properties.dynamic.then).toEqual({ type: 'number' });
    expect(result.schema!.properties.dynamic.else).toEqual({ type: 'boolean' });
  });

  it('preserves unsupported markers alongside supported keywords on the same property', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            mixed: {
              type: 'array',
              title: 'Mixed Field',
              description: 'An array that should not be editable',
              items: { type: 'number' },
              default: [1, 2, 3],
            },
          },
        },
      },
    });

    const result = adaptManifestSettingsSchema(manifest);
    expect(result.schema).not.toBeNull();
    const prop = result.schema!.properties.mixed;
    expect(prop.type).toBe('array');
    expect(prop.title).toBe('Mixed Field');
    expect(prop.description).toBe('An array that should not be editable');
    expect(prop.default).toEqual([1, 2, 3]);
    expect(prop.items).toEqual({ type: 'number' });
  });
});

// ---------------------------------------------------------------------------
// detectUnsupportedShape (T1)
// ---------------------------------------------------------------------------

describe('detectUnsupportedShape', () => {
  function prop(overrides: Partial<StandardSchemaProperty> = {}): StandardSchemaProperty {
    return { type: 'string', ...overrides };
  }

  // Supported primitives
  it('returns null for string', () => {
    expect(detectUnsupportedShape(prop({ type: 'string' }))).toBeNull();
  });

  it('returns null for number', () => {
    expect(detectUnsupportedShape(prop({ type: 'number' }))).toBeNull();
  });

  it('returns null for boolean', () => {
    expect(detectUnsupportedShape(prop({ type: 'boolean' }))).toBeNull();
  });

  it('returns null for integer (mapped to number)', () => {
    expect(detectUnsupportedShape(prop({ type: 'number' }))).toBeNull();
  });

  it('returns null for property with constraints only', () => {
    expect(
      detectUnsupportedShape(
        prop({ type: 'string', minLength: 1, maxLength: 100, pattern: '^[a-z]+$' }),
      ),
    ).toBeNull();
  });

  // Arrays
  it('detects array via type', () => {
    expect(detectUnsupportedShape(prop({ type: 'array' }))).toBe('array');
  });

  it('detects array via items (no explicit type)', () => {
    expect(detectUnsupportedShape(prop({ items: { type: 'string' } }))).toBe('array');
  });

  // Nested objects
  it('detects nested-object via type', () => {
    expect(detectUnsupportedShape(prop({ type: 'object' }))).toBe('nested-object');
  });

  it('detects nested-object via properties (no explicit type)', () => {
    expect(
      detectUnsupportedShape(prop({ properties: { x: { type: 'string' } as any } })),
    ).toBe('nested-object');
  });

  // $ref
  it('detects $ref', () => {
    expect(detectUnsupportedShape(prop({ $ref: '#/definitions/X' }))).toBe('$ref');
  });

  // Combinators
  it('detects oneOf', () => {
    expect(detectUnsupportedShape(prop({ oneOf: [{ type: 'string' }] }))).toBe('oneOf');
  });

  it('detects anyOf', () => {
    expect(detectUnsupportedShape(prop({ anyOf: [{ type: 'string' }] }))).toBe('anyOf');
  });

  it('detects allOf', () => {
    expect(detectUnsupportedShape(prop({ allOf: [{ type: 'string' }] }))).toBe('allOf');
  });

  // Conditionals
  it('detects conditional via if', () => {
    expect(detectUnsupportedShape(prop({ if: { type: 'string' } }))).toBe('conditional');
  });

  it('detects conditional via then', () => {
    expect(detectUnsupportedShape(prop({ then: { type: 'number' } }))).toBe('conditional');
  });

  it('detects conditional via else', () => {
    expect(detectUnsupportedShape(prop({ else: { type: 'boolean' } }))).toBe('conditional');
  });

  it('detects conditional via if+then+else combo', () => {
    expect(
      detectUnsupportedShape(
        prop({
          if: { type: 'string' },
          then: { type: 'number' },
          else: { type: 'boolean' },
        }),
      ),
    ).toBe('conditional');
  });

  // Priority: first match wins
  it('returns array (first match) when property has both array and nested-object markers', () => {
    expect(
      detectUnsupportedShape(prop({ type: 'array', properties: { x: { type: 'string' } as any } })),
    ).toBe('array');
  });

  // Edge cases
  it('detects nested-object for property with type:\"object\" and no nested properties', () => {
    expect(detectUnsupportedShape(prop({ type: 'object' }))).toBe('nested-object');
  });

  it('detects nested-object for property with empty properties object', () => {
    expect(detectUnsupportedShape(prop({ properties: {} }))).toBe('nested-object');
  });

  it('detects conditional via else only (no if/then)', () => {
    expect(detectUnsupportedShape(prop({ else: { type: 'boolean' } }))).toBe('conditional');
  });

  it('returns null for property with no recognized markers', () => {
    // Property with only metadata fields, no type or shape markers
    expect(detectUnsupportedShape(prop({ title: 'Just a title', description: 'No type' }))).toBeNull();
  });

  it('returns null for property whose type is explicitly undefined', () => {
    expect(detectUnsupportedShape(prop({ type: undefined }))).toBeNull();
  });

  it('detects array via items even when type is explicitly something else', () => {
    // items presence takes priority (checked before type-based array detection at line 316 vs 318)
    // Actually line 316 checks type === 'array' OR items !== undefined
    expect(detectUnsupportedShape(prop({ type: 'string', items: { type: 'number' } }))).toBe('array');
  });
});

// ---------------------------------------------------------------------------
// analyzeManifestSettingsSchema (T1)
// ---------------------------------------------------------------------------

describe('analyzeManifestSettingsSchema', () => {
  it('returns editable=true with empty unsupportedFields for fully supported flat schema', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            name: { type: 'string', title: 'Name', default: 'Alice' },
            count: { type: 'number', title: 'Count', default: 1 },
            flag: { type: 'boolean', title: 'Flag', default: false },
            theme: {
              type: 'string',
              title: 'Theme',
              enum: ['light', 'dark'],
              default: 'light',
            },
          },
        },
      },
    });

    const result = analyzeManifestSettingsSchema(manifest);
    expect(result.schema).not.toBeNull();
    expect(result.editable).toBe(true);
    expect(result.unsupportedFields).toEqual([]);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('returns editable=false with unsupportedFields for $ref property', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            ref: { $ref: '#/definitions/X' },
          },
        },
      },
    });

    const result = analyzeManifestSettingsSchema(manifest);
    expect(result.schema).not.toBeNull();
    expect(result.editable).toBe(false);
    expect(result.unsupportedFields).toEqual(['ref']);
  });

  it('returns editable=false with unsupportedFields for oneOf property', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            val: { oneOf: [{ type: 'string' }, { type: 'number' }] },
          },
        },
      },
    });

    const result = analyzeManifestSettingsSchema(manifest);
    expect(result.editable).toBe(false);
    expect(result.unsupportedFields).toEqual(['val']);
  });

  it('returns editable=false with unsupportedFields for anyOf property', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            mixed: { anyOf: [{ type: 'string' }, { type: 'number' }] },
          },
        },
      },
    });

    const result = analyzeManifestSettingsSchema(manifest);
    expect(result.editable).toBe(false);
    expect(result.unsupportedFields).toEqual(['mixed']);
  });

  it('returns editable=false with unsupportedFields for allOf property', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            combined: { allOf: [{ minLength: 3 }, { maxLength: 10 }] },
          },
        },
      },
    });

    const result = analyzeManifestSettingsSchema(manifest);
    expect(result.editable).toBe(false);
    expect(result.unsupportedFields).toEqual(['combined']);
  });

  it('returns editable=false with unsupportedFields for array property', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            tags: { type: 'array', items: { type: 'string' } },
          },
        },
      },
    });

    const result = analyzeManifestSettingsSchema(manifest);
    expect(result.editable).toBe(false);
    expect(result.unsupportedFields).toEqual(['tags']);
  });

  it('returns editable=false with unsupportedFields for nested object property', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            config: { type: 'object', properties: { x: { type: 'string' } } },
          },
        },
      },
    });

    const result = analyzeManifestSettingsSchema(manifest);
    expect(result.editable).toBe(false);
    expect(result.unsupportedFields).toEqual(['config']);
  });

  it('returns editable=false with unsupportedFields for conditional property', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            dynamic: {
              if: { type: 'string' },
              then: { type: 'number' },
            },
          },
        },
      },
    });

    const result = analyzeManifestSettingsSchema(manifest);
    expect(result.editable).toBe(false);
    expect(result.unsupportedFields).toEqual(['dynamic']);
  });

  it('returns multiple unsupported fields in a mixed schema', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            count: { type: 'number' },
            tags: { type: 'array', items: { type: 'string' } },
            ref: { $ref: '#/defs/X' },
            flag: { type: 'boolean' },
          },
        },
      },
    });

    const result = analyzeManifestSettingsSchema(manifest);
    expect(result.editable).toBe(false);
    expect(result.unsupportedFields).toEqual(['tags', 'ref']);
  });

  it('returns editable=false and empty unsupportedFields when schema is null (no settingsSchema)', () => {
    const manifest = makeManifest();

    const result = analyzeManifestSettingsSchema(manifest);
    expect(result.schema).toBeNull();
    expect(result.editable).toBe(false);
    expect(result.unsupportedFields).toEqual([]);
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe('settings/missing-schema');
  });

  it('returns editable=false and empty unsupportedFields when schema is null (malformed)', () => {
    const manifest = makeManifest({
      settingsSchema: {
        version: 1,
        schema: { type: 'array', properties: {} },
      },
    });

    const result = analyzeManifestSettingsSchema(manifest);
    expect(result.schema).toBeNull();
    expect(result.editable).toBe(false);
    expect(result.unsupportedFields).toEqual([]);
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe('settings/non-object-schema');
  });
});

// ---------------------------------------------------------------------------
// materializeSettingsDefaults (T2)
// ---------------------------------------------------------------------------

describe('materializeSettingsDefaults', () => {
  function makeStandardSchema(
    properties: Record<string, StandardSchemaProperty>,
  ): import('@/tools/video-editor/components/SchemaForm/SchemaForm').StandardSchema {
    return { type: 'object', properties };
  }

  function sp(
    overrides: Partial<StandardSchemaProperty> = {},
  ): StandardSchemaProperty {
    return { type: 'string', ...overrides };
  }

  // ---- Precedence: manifest defaults > schema default > display fallback ----

  it('uses manifest settingsDefaults value when present (highest precedence)', () => {
    const schema = makeStandardSchema({
      name: sp({ type: 'string', title: 'Name', default: 'schema-default' }),
    });

    const result = materializeSettingsDefaults(schema, {
      name: 'manifest-default',
    });

    expect(result.name).toBe('manifest-default');
  });

  it('uses schema property default when manifest settingsDefaults does not have the key', () => {
    const schema = makeStandardSchema({
      name: sp({ type: 'string', title: 'Name', default: 'schema-default' }),
    });

    const result = materializeSettingsDefaults(schema, {});

    expect(result.name).toBe('schema-default');
  });

  it('uses schema property default when settingsDefaults is undefined', () => {
    const schema = makeStandardSchema({
      name: sp({ type: 'string', title: 'Name', default: 'schema-default' }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result.name).toBe('schema-default');
  });

  it('uses display-only SchemaForm fallback when nothing else is available', () => {
    const schema = makeStandardSchema({
      name: sp({ type: 'string', title: 'Name' }), // no default
    });

    const result = materializeSettingsDefaults(schema, undefined);

    // String fallback is ''
    expect(result.name).toBe('');
  });

  // ---- String defaults ----

  it('materializes empty string for string type with no default', () => {
    const schema = makeStandardSchema({
      title: sp({ type: 'string', title: 'Title' }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result.title).toBe('');
  });

  it('materializes explicit default for string type', () => {
    const schema = makeStandardSchema({
      title: sp({ type: 'string', title: 'Title', default: 'Hello World' }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result.title).toBe('Hello World');
  });

  it('manifest defaults override schema default for string', () => {
    const schema = makeStandardSchema({
      title: sp({ type: 'string', title: 'Title', default: 'schema-val' }),
    });

    const result = materializeSettingsDefaults(schema, { title: 'manifest-val' });

    expect(result.title).toBe('manifest-val');
  });

  // ---- Number defaults ----

  it('materializes 0 for number type with no default', () => {
    const schema = makeStandardSchema({
      count: sp({ type: 'number', title: 'Count' }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result.count).toBe(0);
  });

  it('materializes explicit default for number type', () => {
    const schema = makeStandardSchema({
      count: sp({ type: 'number', title: 'Count', default: 42 }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result.count).toBe(42);
  });

  it('manifest defaults override schema default for number', () => {
    const schema = makeStandardSchema({
      count: sp({ type: 'number', title: 'Count', default: 1 }),
    });

    const result = materializeSettingsDefaults(schema, { count: 100 });

    expect(result.count).toBe(100);
  });

  // ---- Integer defaults (mapped to number) ----

  it('materializes 0 for integer type (mapped to number) with no default', () => {
    const schema = makeStandardSchema({
      count: sp({ type: 'integer', title: 'Count' }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result.count).toBe(0);
  });

  it('materializes explicit default for integer type', () => {
    const schema = makeStandardSchema({
      count: sp({ type: 'integer', title: 'Count', default: 5 }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result.count).toBe(5);
  });

  // ---- Boolean defaults ----

  it('materializes false for boolean type with no default', () => {
    const schema = makeStandardSchema({
      flag: sp({ type: 'boolean', title: 'Flag' }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result.flag).toBe(false);
  });

  it('materializes explicit default for boolean type', () => {
    const schema = makeStandardSchema({
      flag: sp({ type: 'boolean', title: 'Flag', default: true }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result.flag).toBe(true);
  });

  it('manifest defaults override schema default for boolean', () => {
    const schema = makeStandardSchema({
      flag: sp({ type: 'boolean', title: 'Flag', default: false }),
    });

    const result = materializeSettingsDefaults(schema, { flag: true });

    expect(result.flag).toBe(true);
  });

  // ---- Enum defaults ----

  it('materializes first enum value for string enum with no default', () => {
    const schema = makeStandardSchema({
      theme: sp({ type: 'string', title: 'Theme', enum: ['light', 'dark', 'auto'] }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    // First enum value is the display fallback for enum types
    expect(result.theme).toBe('light');
  });

  it('materializes explicit default for enum type (overriding first enum value)', () => {
    const schema = makeStandardSchema({
      theme: sp({
        type: 'string',
        title: 'Theme',
        enum: ['light', 'dark', 'auto'],
        default: 'dark',
      }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result.theme).toBe('dark');
  });

  it('manifest defaults override both schema default and enum fallback for enum', () => {
    const schema = makeStandardSchema({
      theme: sp({
        type: 'string',
        title: 'Theme',
        enum: ['light', 'dark', 'auto'],
        default: 'dark',
      }),
    });

    const result = materializeSettingsDefaults(schema, { theme: 'auto' });

    expect(result.theme).toBe('auto');
  });

  it('materializes first numeric enum value for number enum with no default', () => {
    const schema = makeStandardSchema({
      size: sp({ type: 'number', title: 'Size', enum: [1, 2, 3] }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result.size).toBe(1);
  });

  // ---- Unsupported shapes are excluded ----

  it('excludes array properties from the result', () => {
    const schema = makeStandardSchema({
      name: sp({ type: 'string', title: 'Name' }),
      tags: sp({ type: 'array', title: 'Tags', items: { type: 'string' } }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result).toHaveProperty('name');
    expect(result).not.toHaveProperty('tags');
    expect(Object.keys(result)).toEqual(['name']);
  });

  it('excludes nested object properties from the result', () => {
    const schema = makeStandardSchema({
      name: sp({ type: 'string', title: 'Name' }),
      config: sp({
        type: 'object',
        title: 'Config',
        properties: { nested: { type: 'string' } },
      }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result).toHaveProperty('name');
    expect(result).not.toHaveProperty('config');
  });

  it('excludes $ref properties from the result', () => {
    const schema = makeStandardSchema({
      name: sp({ type: 'string', title: 'Name' }),
      ref: sp({ $ref: '#/definitions/X' }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result).toHaveProperty('name');
    expect(result).not.toHaveProperty('ref');
  });

  it('excludes oneOf/anyOf/allOf properties from the result', () => {
    const schema = makeStandardSchema({
      name: sp({ type: 'string', title: 'Name' }),
      one: sp({ oneOf: [{ type: 'string' }] }),
      any: sp({ anyOf: [{ type: 'number' }] }),
      all: sp({ allOf: [{ minLength: 3 }] }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result).toHaveProperty('name');
    expect(result).not.toHaveProperty('one');
    expect(result).not.toHaveProperty('any');
    expect(result).not.toHaveProperty('all');
  });

  it('excludes conditional (if/then/else) properties from the result', () => {
    const schema = makeStandardSchema({
      name: sp({ type: 'string', title: 'Name' }),
      dynamic: sp({
        if: { type: 'string' },
        then: { type: 'number' },
        else: { type: 'boolean' },
      }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result).toHaveProperty('name');
    expect(result).not.toHaveProperty('dynamic');
  });

  // ---- Mixed scenarios ----

  it('handles mixed precedence across multiple fields', () => {
    const schema = makeStandardSchema({
      // manifest default wins
      name: sp({ type: 'string', title: 'Name', default: 'schema-name' }),
      // schema default wins (not in manifest)
      count: sp({ type: 'number', title: 'Count', default: 42 }),
      // display fallback (no schema or manifest default)
      flag: sp({ type: 'boolean', title: 'Flag' }),
      // enum display fallback
      theme: sp({ type: 'string', title: 'Theme', enum: ['light', 'dark'] }),
      // unsupported — excluded
      tags: sp({ type: 'array', title: 'Tags', items: { type: 'string' } }),
    });

    const result = materializeSettingsDefaults(schema, {
      name: 'manifest-name',
    });

    expect(result).toEqual({
      name: 'manifest-name', // manifest override
      count: 42, // schema default
      flag: false, // display fallback
      theme: 'light', // enum fallback
      // tags excluded (unsupported shape)
    });
  });

  it('returns empty object for empty schema properties', () => {
    const schema = makeStandardSchema({});

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result).toEqual({});
  });

  it('returns empty object when all properties are unsupported shapes', () => {
    const schema = makeStandardSchema({
      arr: sp({ type: 'array', items: { type: 'string' } }),
      nested: sp({ type: 'object', properties: { x: { type: 'string' } } }),
      ref: sp({ $ref: '#/defs/X' }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result).toEqual({});
  });

  it('manifest defaults don\'t leak into unsupported shapes', () => {
    const schema = makeStandardSchema({
      tags: sp({ type: 'array', items: { type: 'string' } }),
    });

    const result = materializeSettingsDefaults(schema, { tags: ['a', 'b'] });

    // tags is unsupported and should be excluded even if manifest has it
    expect(result).not.toHaveProperty('tags');
    expect(result).toEqual({});
  });

  // ---- Zero / falsy defaults are preserved ----

  it('preserves explicit 0 as schema default (not confused with missing default)', () => {
    const schema = makeStandardSchema({
      count: sp({ type: 'number', title: 'Count', default: 0 }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    // Explicit 0 should be kept, not replaced by display fallback
    expect(result.count).toBe(0);
  });

  it('preserves explicit false as schema default', () => {
    const schema = makeStandardSchema({
      flag: sp({ type: 'boolean', title: 'Flag', default: false }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    // Explicit false should be kept, not replaced by display fallback
    expect(result.flag).toBe(false);
  });

  it('preserves explicit empty string as schema default', () => {
    const schema = makeStandardSchema({
      name: sp({ type: 'string', title: 'Name', default: '' }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    // Explicit '' should be kept, not replaced by display fallback
    expect(result.name).toBe('');
  });

  // ---- Unknown types get '' display fallback ----

  it('uses empty string fallback for unknown types', () => {
    const schema = makeStandardSchema({
      custom: sp({ type: 'customWidget', title: 'Custom' }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result.custom).toBe('');
  });

  it('uses empty string fallback when type is undefined', () => {
    const schema = makeStandardSchema({
      unknown: sp({ title: 'Unknown' }),
    });

    const result = materializeSettingsDefaults(schema, undefined);

    expect(result.unknown).toBe('');
  });
});

// ---------------------------------------------------------------------------
// reconcileSettingsSnapshot (T3)
// ---------------------------------------------------------------------------

describe('reconcileSettingsSnapshot', () => {
  // ---- Helpers ----

  function makeManifestWithSchema(
    properties: Record<string, unknown>,
    extras: Partial<Record<string, unknown>> = {},
  ): ExtensionManifest {
    return makeManifest({
      ...extras,
      settingsSchema: {
        version: 1,
        schema: {
          type: 'object',
          properties,
          ...extras,
        },
      },
    });
  }

  function snapshot(
    values: Record<string, unknown>,
    overrides: Partial<Record<string, unknown>> = {},
  ): Record<string, unknown> {
    return {
      extensionId: 'com.test.reconcile',
      schemaVersion: 1,
      lastWrittenAt: '2026-06-23T00:00:00Z',
      values,
      ...overrides,
    };
  }

  /** Shortcut for quick reconciliation assertions. */
  function rec(
    manifest: ExtensionManifest,
    snap: unknown,
  ): ReconciliationResult {
    return reconcileSettingsSnapshot({ manifest, snapshot: snap });
  }

  // ======================================================================
  // CLEAN
  // ======================================================================

  describe('clean', () => {
    it('classifies a perfectly matching snapshot as clean', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
        count: { type: 'number', title: 'Count' },
      });

      const result = rec(
        manifest,
        snapshot({ name: 'Alice', count: 42 }),
      );

      expect(result.state).toBe('clean');
      expect(result.values).toEqual({ name: 'Alice', count: 42 });
      expect(result.droppedUnknownFields).toEqual([]);
      // No repair or review diagnostics
      const codes = result.diagnostics.map((d) => d.code);
      expect(codes.filter((c) => c !== '')).toEqual([]);
    });

    it('classifies a snapshot with all defaults matching as clean (no repairs)', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name', default: 'default-name' },
        enabled: { type: 'boolean', title: 'Enabled', default: true },
      });

      const result = rec(
        manifest,
        snapshot({ name: 'default-name', enabled: true }),
      );

      // All values present and match — no missing fields → clean
      expect(result.state).toBe('clean');
      expect(result.values).toEqual({ name: 'default-name', enabled: true });
    });

    it('classifies clean with enum field matching an allowed value', () => {
      const manifest = makeManifestWithSchema({
        theme: { type: 'string', title: 'Theme', enum: ['light', 'dark'] },
      });

      const result = rec(
        manifest,
        snapshot({ theme: 'dark' }),
      );

      expect(result.state).toBe('clean');
      expect(result.values).toEqual({ theme: 'dark' });
    });

    it('classifies clean with integer field matching expected type', () => {
      const manifest = makeManifestWithSchema({
        retries: { type: 'integer', title: 'Retries' },
      });

      const result = rec(
        manifest,
        snapshot({ retries: 3 }),
      );

      expect(result.state).toBe('clean');
      expect(result.values).toEqual({ retries: 3 });
    });

    it('classifies clean with falsy values present (0, false, "")', () => {
      const manifest = makeManifestWithSchema({
        count: { type: 'number', title: 'Count' },
        flag: { type: 'boolean', title: 'Flag' },
        text: { type: 'string', title: 'Text' },
      });

      const result = rec(
        manifest,
        snapshot({ count: 0, flag: false, text: '' }),
      );

      expect(result.state).toBe('clean');
      expect(result.values).toEqual({ count: 0, flag: false, text: '' });
    });
  });

  // ======================================================================
  // REPAIRED
  // ======================================================================

  describe('repaired', () => {
    it('fills missing fields from defaults (repaired)', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name', default: 'fallback' },
        count: { type: 'number', title: 'Count', default: 10 },
      });

      // Snapshot has neither field
      const result = rec(manifest, snapshot({}));

      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ name: 'fallback', count: 10 });
    });

    it('fills missing fields from manifest settingsDefaults (repaired)', () => {
      const manifest = makeManifestWithSchema(
        {
          name: { type: 'string', title: 'Name' },
          count: { type: 'number', title: 'Count' },
        },
        { settingsDefaults: { name: 'manifest-name', count: 99 } },
      );

      const result = rec(manifest, snapshot({}));

      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ name: 'manifest-name', count: 99 });
    });

    it('coerces numeric string to number (repaired)', () => {
      const manifest = makeManifestWithSchema({
        count: { type: 'number', title: 'Count' },
      });

      const result = rec(
        manifest,
        snapshot({ count: '42' }),
      );

      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ count: 42 });
      expect(
        result.diagnostics.some((d) => d.code === 'settings/numeric-string-coerced'),
      ).toBe(true);
    });

    it('coerces numeric string to integer (repaired)', () => {
      const manifest = makeManifestWithSchema({
        retries: { type: 'integer', title: 'Retries' },
      });

      const result = rec(
        manifest,
        snapshot({ retries: '3' }),
      );

      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ retries: 3 });
      expect(
        result.diagnostics.some((d) => d.code === 'settings/numeric-string-coerced'),
      ).toBe(true);
    });

    it('coerces boolean to number (repaired)', () => {
      const manifest = makeManifestWithSchema({
        count: { type: 'number', title: 'Count' },
      });

      const result = rec(
        manifest,
        snapshot({ count: true }),
      );

      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ count: 1 });
    });

    it('coerces string "true"/"false" to boolean (repaired)', () => {
      const manifest = makeManifestWithSchema({
        flag: { type: 'boolean', title: 'Flag' },
      });

      const result = rec(
        manifest,
        snapshot({ flag: 'true' }),
      );

      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ flag: true });
    });

    it('coerces number to boolean (repaired)', () => {
      const manifest = makeManifestWithSchema({
        flag: { type: 'boolean', title: 'Flag' },
      });

      const r1 = rec(manifest, snapshot({ flag: 0 }));
      expect(r1.state).toBe('repaired');
      expect(r1.values.flag).toBe(false);

      const r2 = rec(manifest, snapshot({ flag: 1 }));
      expect(r2.state).toBe('repaired');
      expect(r2.values.flag).toBe(true);
    });

    it('null snapshot produces repaired with all defaults filled', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name', default: 'default-name' },
        count: { type: 'number', title: 'Count', default: 5 },
      });

      const result = rec(manifest, null);

      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ name: 'default-name', count: 5 });
    });

    it('undefined snapshot produces repaired with all defaults filled', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name', default: 'default-name' },
      });

      const result = rec(manifest, undefined);

      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ name: 'default-name' });
    });

    it('partial snapshot fills missing with defaults (repaired)', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name', default: 'fallback' },
        count: { type: 'number', title: 'Count', default: 0 },
        flag: { type: 'boolean', title: 'Flag', default: false },
      });

      // Only 'name' is present
      const result = rec(manifest, snapshot({ name: 'Alice' }));

      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ name: 'Alice', count: 0, flag: false });
    });

    it('classifies as repaired when only numeric string coercion is needed', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name', default: 'Bob' },
        count: { type: 'number', title: 'Count' },
      });

      // name present and correct, count needs coercion
      const result = rec(
        manifest,
        snapshot({ name: 'Bob', count: '100' }),
      );

      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ name: 'Bob', count: 100 });
    });

    it('coerces whitespace-padded numeric string', () => {
      const manifest = makeManifestWithSchema({
        count: { type: 'number', title: 'Count' },
      });

      const result = rec(manifest, snapshot({ count: '  42  ' }));

      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ count: 42 });
    });

    it('truncates float string to integer for integer fields', () => {
      const manifest = makeManifestWithSchema({
        retries: { type: 'integer', title: 'Retries' },
      });

      const result = rec(manifest, snapshot({ retries: '3.9' }));

      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ retries: 3 });
    });
  });

  // ======================================================================
  // NEEDS-REVIEW
  // ======================================================================

  describe('needs-review', () => {
    it('flags invalid enum value as needs-review (preserves original value)', () => {
      const manifest = makeManifestWithSchema({
        theme: { type: 'string', title: 'Theme', enum: ['light', 'dark'] },
      });

      const result = rec(
        manifest,
        snapshot({ theme: 'blue' }),
      );

      expect(result.state).toBe('needs-review');
      // Original value preserved
      expect(result.values).toEqual({ theme: 'blue' });
      expect(
        result.diagnostics.some((d) => d.code === 'settings/invalid-enum'),
      ).toBe(true);
    });

    it('flags unknown fields as needs-review with droppedUnknownFields', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
      });

      const result = rec(
        manifest,
        snapshot({ name: 'Alice', extraField: 'should-be-dropped' }),
      );

      expect(result.state).toBe('needs-review');
      // Unknown field dropped from values
      expect(result.values).toEqual({ name: 'Alice' });
      expect(result.droppedUnknownFields).toEqual(['extraField']);
      expect(
        result.diagnostics.some((d) => d.code === 'settings/unknown-field'),
      ).toBe(true);
    });

    it('flags multiple unknown fields', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
      });

      const result = rec(
        manifest,
        snapshot({ name: 'Alice', x: 1, y: 2, z: 3 }),
      );

      expect(result.state).toBe('needs-review');
      expect(result.droppedUnknownFields).toEqual(['x', 'y', 'z']);
      expect(result.values).toEqual({ name: 'Alice' });
      // One diagnostic per unknown field
      expect(
        result.diagnostics.filter((d) => d.code === 'settings/unknown-field'),
      ).toHaveLength(3);
    });

    it('flags type mismatch (string expected, number received) as needs-review', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
      });

      const result = rec(
        manifest,
        snapshot({ name: 42 }),
      );

      expect(result.state).toBe('needs-review');
      expect(result.values).toEqual({ name: 42 }); // preserved
      expect(
        result.diagnostics.some((d) => d.code === 'settings/type-mismatch'),
      ).toBe(true);
    });

    it('flags unparseable numeric string as needs-review', () => {
      const manifest = makeManifestWithSchema({
        count: { type: 'number', title: 'Count' },
      });

      const result = rec(
        manifest,
        snapshot({ count: 'not-a-number' }),
      );

      expect(result.state).toBe('needs-review');
      expect(result.values).toEqual({ count: 'not-a-number' }); // preserved
      expect(
        result.diagnostics.some((d) => d.code === 'settings/unparseable-number'),
      ).toBe(true);
    });

    it('flags empty string for number field as needs-review', () => {
      const manifest = makeManifestWithSchema({
        count: { type: 'number', title: 'Count' },
      });

      const result = rec(
        manifest,
        snapshot({ count: '' }),
      );

      expect(result.state).toBe('needs-review');
      expect(result.values).toEqual({ count: '' }); // preserved
    });

    it('flags non-finite number as needs-review', () => {
      const manifest = makeManifestWithSchema({
        count: { type: 'number', title: 'Count' },
      });

      const result = rec(
        manifest,
        snapshot({ count: Infinity }),
      );

      expect(result.state).toBe('needs-review');
      expect(result.values).toEqual({ count: Infinity }); // preserved
      expect(
        result.diagnostics.some((d) => d.code === 'settings/non-finite-number'),
      ).toBe(true);
    });

    it('flags object value for string field as needs-review', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
      });

      const result = rec(
        manifest,
        snapshot({ name: { nested: true } }),
      );

      expect(result.state).toBe('needs-review');
    });

    it('needs-review supersedes repaired when both occur', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name', default: 'default' },
        theme: { type: 'string', title: 'Theme', enum: ['light', 'dark'] },
      });

      // name is missing (would be repaired), theme is invalid enum (needs-review)
      const result = rec(
        manifest,
        snapshot({ theme: 'blue' }),
      );

      expect(result.state).toBe('needs-review');
      // name filled from default (repair), theme preserved (review)
      expect(result.values).toEqual({ name: 'default', theme: 'blue' });
    });
  });

  // ======================================================================
  // ADDITIONAL PROPERTIES: FALSE
  // ======================================================================

  describe('additionalProperties: false', () => {
    it('drops unknown fields but classifies as repaired (not needs-review) when additionalProperties is false', () => {
      const manifest = makeManifestWithSchema(
        {
          name: { type: 'string', title: 'Name', default: 'Alice' },
        },
        {
          additionalProperties: false,
        },
      );

      const result = rec(
        manifest,
        snapshot({ name: 'Alice', extra: 'should-drop' }),
      );

      // Schema explicitly forbids extra props → dropping them is enforcement,
      // not a review concern
      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ name: 'Alice' });
      expect(result.droppedUnknownFields).toEqual(['extra']);
      // Still warns about the drop
      expect(
        result.diagnostics.some((d) => d.code === 'settings/unknown-field'),
      ).toBe(true);
    });

    it('classifies as clean with additionalProperties: false and all values matching', () => {
      const manifest = makeManifestWithSchema(
        {
          name: { type: 'string', title: 'Name' },
        },
        {
          additionalProperties: false,
        },
      );

      const result = rec(
        manifest,
        snapshot({ name: 'Alice' }),
      );

      expect(result.state).toBe('clean');
      expect(result.droppedUnknownFields).toEqual([]);
    });

    it('still flags needs-review with additionalProperties: false when there are other review issues', () => {
      const manifest = makeManifestWithSchema(
        {
          theme: { type: 'string', title: 'Theme', enum: ['light', 'dark'] },
        },
        {
          additionalProperties: false,
        },
      );

      const result = rec(
        manifest,
        snapshot({ theme: 'blue', extra: 'unknown' }),
      );

      // Invalid enum still triggers needs-review
      expect(result.state).toBe('needs-review');
      expect(result.droppedUnknownFields).toEqual(['extra']);
    });
  });

  // ======================================================================
  // BLOCKED
  // ======================================================================

  describe('blocked', () => {
    it('blocks on corrupt non-object snapshot (string)', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
      });

      const result = rec(manifest, 'not-an-object');

      expect(result.state).toBe('blocked');
      expect(result.values).toEqual({});
      expect(
        result.diagnostics.some((d) => d.code === 'settings/corrupt-snapshot'),
      ).toBe(true);
    });

    it('blocks on corrupt non-object snapshot (array)', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
      });

      const result = rec(manifest, [1, 2, 3]);

      expect(result.state).toBe('blocked');
      expect(
        result.diagnostics.some((d) => d.code === 'settings/corrupt-snapshot'),
      ).toBe(true);
    });

    it('blocks on corrupt non-object snapshot (number)', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
      });

      const result = rec(manifest, 42);

      expect(result.state).toBe('blocked');
    });

    it('blocks on snapshot with non-object .values', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
      });

      // Snapshot has `values` but it's a string
      const result = rec(manifest, { values: 'not-an-object' });

      expect(result.state).toBe('blocked');
      expect(
        result.diagnostics.some((d) => d.code === 'settings/corrupt-snapshot'),
      ).toBe(true);
    });

    it('blocks on snapshot with null .values', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
      });

      const result = rec(manifest, { values: null });

      expect(result.state).toBe('blocked');
    });

    it('blocks on snapshot with array .values', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
      });

      const result = rec(manifest, { values: ['a', 'b'] });

      expect(result.state).toBe('blocked');
    });

    it('blocks when manifest has no settings schema', () => {
      const manifest = makeManifest(); // no settingsSchema

      const result = rec(manifest, snapshot({ name: 'test' }));

      expect(result.state).toBe('blocked');
      expect(result.diagnostics.some((d) => d.code === 'settings/missing-schema')).toBe(
        true,
      );
    });

    it('blocks on unsupported schema constructs ($ref)', () => {
      const manifest = makeManifestWithSchema({
        ref: { $ref: '#/definitions/X' },
      });

      const result = rec(manifest, snapshot({ ref: 'value' }));

      expect(result.state).toBe('blocked');
      expect(
        result.diagnostics.some((d) => d.code === 'settings/unsupported-schema'),
      ).toBe(true);
      expect(result.values).toEqual({});
    });

    it('blocks on unsupported schema constructs (array type)', () => {
      const manifest = makeManifestWithSchema({
        tags: { type: 'array', items: { type: 'string' } },
      });

      const result = rec(manifest, snapshot({ tags: ['a'] }));

      expect(result.state).toBe('blocked');
    });

    it('blocks on unsupported schema constructs (nested object)', () => {
      const manifest = makeManifestWithSchema({
        config: { type: 'object', properties: { x: { type: 'string' } } },
      });

      const result = rec(manifest, snapshot({ config: { x: 'y' } }));

      expect(result.state).toBe('blocked');
    });

    it('blocks on unsupported schema constructs (oneOf)', () => {
      const manifest = makeManifestWithSchema({
        val: { oneOf: [{ type: 'string' }, { type: 'number' }] },
      });

      const result = rec(manifest, snapshot({ val: 'test' }));

      expect(result.state).toBe('blocked');
    });

    it('blocks on unsupported schema constructs (anyOf)', () => {
      const manifest = makeManifestWithSchema({
        mixed: { anyOf: [{ type: 'string' }, { type: 'number' }] },
      });

      const result = rec(manifest, snapshot({ mixed: 1 }));

      expect(result.state).toBe('blocked');
    });

    it('blocks on unsupported schema constructs (allOf)', () => {
      const manifest = makeManifestWithSchema({
        combined: { allOf: [{ minLength: 3 }, { maxLength: 10 }] },
      });

      const result = rec(manifest, snapshot({ combined: 'test' }));

      expect(result.state).toBe('blocked');
    });

    it('blocks on unsupported schema constructs (conditional)', () => {
      const manifest = makeManifestWithSchema({
        dynamic: { if: { type: 'string' }, then: { type: 'number' } },
      });

      const result = rec(manifest, snapshot({ dynamic: 'hello' }));

      expect(result.state).toBe('blocked');
    });

    it('blocks on malformed manifest schema (non-object type)', () => {
      const manifest = makeManifest({
        settingsSchema: {
          version: 1,
          schema: { type: 'array', properties: {} },
        },
      });

      const result = rec(manifest, snapshot({}));

      expect(result.state).toBe('blocked');
      expect(
        result.diagnostics.some((d) => d.code === 'settings/non-object-schema'),
      ).toBe(true);
    });
  });

  // ======================================================================
  // EDGE CASES & SNAPSHOT EXTRACTION
  // ======================================================================

  describe('snapshot extraction', () => {
    it('extracts values from a full SettingsSnapshot-shaped object', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name', default: 'Alice' },
      });

      const result = rec(
        manifest,
        {
          extensionId: 'ext-id',
          schemaVersion: 1,
          lastWrittenAt: '2026-01-01T00:00:00Z',
          values: { name: 'Bob' },
        },
      );

      expect(result.state).toBe('clean');
      expect(result.values).toEqual({ name: 'Bob' });
      // Non-values keys are not treated as unknown fields
      expect(result.droppedUnknownFields).toEqual([]);
    });

    it('treats plain object without .values as raw values record', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name', default: 'Alice' },
      });

      // Plain object passed directly (legacy path)
      const result = rec(manifest, { name: 'Charlie' });

      expect(result.state).toBe('clean');
      expect(result.values).toEqual({ name: 'Charlie' });
    });
  });

  describe('mixed scenarios', () => {
    it('reports droppedUnknownFields cleanly without polluting values', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
        count: { type: 'number', title: 'Count' },
      });

      const result = rec(
        manifest,
        snapshot({ name: 'Alice', count: 10, extra1: 'x', extra2: 'y' }),
      );

      // Values only contain schema-declared fields
      expect(result.values).toEqual({ name: 'Alice', count: 10 });
      expect(result.droppedUnknownFields).toEqual(['extra1', 'extra2']);
      // Unknown metadata never pollutes values
      expect(result.values).not.toHaveProperty('extra1');
      expect(result.values).not.toHaveProperty('extra2');
    });

    it('handles a fully populated snapshot with no issues', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
        count: { type: 'number', title: 'Count' },
        flag: { type: 'boolean', title: 'Flag' },
        theme: { type: 'string', title: 'Theme', enum: ['light', 'dark'] },
      });

      const result = rec(
        manifest,
        snapshot({
          name: 'Alice',
          count: 42,
          flag: true,
          theme: 'dark',
        }),
      );

      expect(result.state).toBe('clean');
      expect(result.values).toEqual({
        name: 'Alice',
        count: 42,
        flag: true,
        theme: 'dark',
      });
      expect(result.droppedUnknownFields).toEqual([]);
    });

    it('preserves numeric zero correctly (not confused with missing)', () => {
      const manifest = makeManifestWithSchema({
        count: { type: 'number', title: 'Count', default: 10 },
      });

      // Zero is explicitly present — should not be replaced by default
      const result = rec(manifest, snapshot({ count: 0 }));

      expect(result.state).toBe('clean');
      expect(result.values).toEqual({ count: 0 });
    });

    it('preserves boolean false correctly (not confused with missing)', () => {
      const manifest = makeManifestWithSchema({
        flag: { type: 'boolean', title: 'Flag', default: true },
      });

      const result = rec(manifest, snapshot({ flag: false }));

      expect(result.state).toBe('clean');
      expect(result.values).toEqual({ flag: false });
    });

    it('preserves empty string correctly (not confused with missing)', () => {
      const manifest = makeManifestWithSchema({
        text: { type: 'string', title: 'Text', default: 'placeholder' },
      });

      const result = rec(manifest, snapshot({ text: '' }));

      expect(result.state).toBe('clean');
      expect(result.values).toEqual({ text: '' });
    });
  });

  // ======================================================================
  // RECONCILIATION EDGE CASES
  // ======================================================================

  describe('reconciliation edge cases', () => {
    it('handles snapshot with null values field gracefully', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name', default: 'fallback' },
      });

      const result = rec(manifest, { extensionId: 'x', schemaVersion: 1, values: null });

      expect(result.state).toBe('blocked');
      expect(result.values).toEqual({});
      expect(result.diagnostics.some((d) => d.code === 'settings/corrupt-snapshot')).toBe(true);
    });

    it('handles completely empty snapshot object (no values key, no data)', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name', default: 'fallback' },
        count: { type: 'number', title: 'Count', default: 10 },
      });

      // Empty object without .values — treated as raw values, all fields missing
      const result = rec(manifest, {});

      expect(result.state).toBe('repaired');
      expect(result.values).toEqual({ name: 'fallback', count: 10 });
    });

    it('preserves valid values while flagging only the problematic fields', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name' },
        count: { type: 'number', title: 'Count' },
        theme: { type: 'string', title: 'Theme', enum: ['light', 'dark'] },
      });

      const result = rec(manifest, snapshot({ name: 'Alice', count: 42, theme: 'blue' }));

      expect(result.state).toBe('needs-review');
      // Valid fields preserved, invalid enum preserved for review
      expect(result.values).toEqual({ name: 'Alice', count: 42, theme: 'blue' });
      // Only the enum field should have a review diagnostic
      const reviewCodes = result.diagnostics
        .filter((d) => d.code === 'settings/invalid-enum' || d.code === 'settings/type-mismatch');
      expect(reviewCodes).toHaveLength(1);
    });

    it('coerces and repairs numeric strings while flagging invalid enums (mixed state)', () => {
      const manifest = makeManifestWithSchema({
        name: { type: 'string', title: 'Name', default: 'default' },
        count: { type: 'number', title: 'Count' },
        theme: { type: 'string', title: 'Theme', enum: ['light', 'dark'] },
      });

      const result = rec(manifest, snapshot({ name: 'Bob', count: '50', theme: 'blue' }));

      // needs-review wins over repaired
      expect(result.state).toBe('needs-review');
      // count coerced, theme preserved for review
      expect(result.values).toEqual({ name: 'Bob', count: 50, theme: 'blue' });
    });

    it('reports both unknown fields and invalid enums in the same snapshot', () => {
      const manifest = makeManifestWithSchema({
        theme: { type: 'string', title: 'Theme', enum: ['light', 'dark'] },
      });

      const result = rec(manifest, snapshot({ theme: 'blue', extra1: 'x', extra2: 'y' }));

      expect(result.state).toBe('needs-review');
      expect(result.values).toEqual({ theme: 'blue' });
      expect(result.droppedUnknownFields).toEqual(['extra1', 'extra2']);
      expect(result.diagnostics.some((d) => d.code === 'settings/invalid-enum')).toBe(true);
      expect(result.diagnostics.filter((d) => d.code === 'settings/unknown-field')).toHaveLength(2);
    });
  });
});
