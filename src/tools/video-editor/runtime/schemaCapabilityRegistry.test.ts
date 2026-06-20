// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { createSchemaCapabilityRegistry } from '@/tools/video-editor/runtime/schemaCapabilityRegistry';
import type {
  SchemaCapabilityRegistry,
  SchemaCapabilityEntry,
  ValidationPathEntry,
} from '@/tools/video-editor/runtime/schemaCapabilityRegistry';
import type { ParameterDefinition } from '@/tools/video-editor/types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeDef(overrides: Partial<ParameterDefinition> = {}): ParameterDefinition {
  return {
    name: 'testParam',
    label: 'Test Param',
    description: 'A test parameter',
    type: 'string',
    ...overrides,
  };
}

function fresh(): SchemaCapabilityRegistry {
  return createSchemaCapabilityRegistry();
}

// ---------------------------------------------------------------------------
// Supported widgets
// ---------------------------------------------------------------------------

describe('supported widgets', () => {
  const supportedTypes = [
    { type: 'string', widgetType: 'text', label: 'String' },
    { type: 'number', widgetType: 'slider', label: 'Number' },
    { type: 'boolean', widgetType: 'boolean', label: 'Boolean' },
    { type: 'select', widgetType: 'select', label: 'Select' },
    { type: 'color', widgetType: 'color', label: 'Color' },
    { type: 'float', widgetType: 'shader-number', label: 'Float' },
    { type: 'int', widgetType: 'shader-number', label: 'Integer' },
    { type: 'bool', widgetType: 'boolean', label: 'Boolean' },
    { type: 'vec2', widgetType: 'vector', label: 'Vector 2' },
    { type: 'vec3', widgetType: 'vector', label: 'Vector 3' },
    { type: 'vec4', widgetType: 'vector', label: 'Vector 4' },
    { type: 'enum', widgetType: 'select', label: 'Enum' },
    { type: 'frame', widgetType: 'shader-number', label: 'Frame' },
    { type: 'time', widgetType: 'shader-number', label: 'Time' },
  ] as const;

  for (const { type, widgetType, label } of supportedTypes) {
    it(`resolves "${type}" as supported with widget "${widgetType}"`, () => {
      const reg = fresh();
      expect(reg.isSupported(type)).toBe(true);
      expect(reg.isCustom(type)).toBe(false);

      const entry = reg.resolve(type);
      expect(entry.status).toBe('supported');
      expect(entry.widgetType).toBe(widgetType);
      expect(entry.label).toBe(label);
      expect(entry.isCustomPlaceholder).toBe(false);
      expect(entry.diagnostic).toBeNull();
      expect(reg.getDiagnostic(type)).toBeNull();
    });
  }

  it('exposes supported built-in types in entries map', () => {
    const reg = fresh();
    expect(reg.entries.size).toBe(16); // supported controls + audio-binding + unsupported textureRef
    for (const { type } of supportedTypes) {
      expect(reg.entries.has(type)).toBe(true);
    }
  });

  it('resolves textureRef as a built-in unsupported diagnostic placeholder', () => {
    const reg = fresh();
    expect(reg.isSupported('textureRef')).toBe(false);
    expect(reg.isCustom('textureRef')).toBe(false);

    const entry = reg.resolve('textureRef');
    expect(entry.status).toBe('unsupported');
    expect(entry.label).toBe('Texture Reference');
    expect(entry.diagnostic?.code).toBe('schema/texture-ref-unsupported');
    expect(entry.diagnostic?.message).toContain('not editable');
    expect(reg.entries.has('textureRef')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Custom widget placeholders (audio-binding)
// ---------------------------------------------------------------------------

describe('custom widget placeholders', () => {
  it('resolves audio-binding as custom placeholder, not supported', () => {
    const reg = fresh();
    expect(reg.isSupported('audio-binding')).toBe(false);
    expect(reg.isCustom('audio-binding')).toBe(true);

    const entry = reg.resolve('audio-binding');
    expect(entry.status).toBe('custom');
    expect(entry.isCustomPlaceholder).toBe(true);
    expect(entry.widgetType).toBeUndefined(); // Not a standard widget type
    expect(entry.label).toBe('Audio Binding');
    expect(entry.diagnostic).toBeNull(); // Custom placeholders are not broken
  });

  it('audio-binding is listed in entries as custom', () => {
    const reg = fresh();
    expect(reg.entries.has('audio-binding')).toBe(true);
    const entry = reg.entries.get('audio-binding')!;
    expect(entry.status).toBe('custom');
    expect(entry.isCustomPlaceholder).toBe(true);
  });

  it('getDiagnostic returns null for audio-binding (it renders fine)', () => {
    const reg = fresh();
    expect(reg.getDiagnostic('audio-binding')).toBeNull();
  });

  it('registerCustom allows adding new custom types', () => {
    const reg = fresh();
    const customEntry: SchemaCapabilityEntry = {
      type: 'my-custom-type',
      widgetType: undefined,
      status: 'custom',
      label: 'My Custom',
      diagnostic: null,
      isCustomPlaceholder: true,
    };

    reg.registerCustom('my-custom-type', customEntry);

    expect(reg.isCustom('my-custom-type')).toBe(true);
    expect(reg.isSupported('my-custom-type')).toBe(false);
    expect(reg.entries.has('my-custom-type')).toBe(true);

    const resolved = reg.resolve('my-custom-type');
    expect(resolved.status).toBe('custom');
    expect(resolved.label).toBe('My Custom');
  });

  it('registerCustom throws when trying to override a built-in type', () => {
    const reg = fresh();
    expect(() =>
      reg.registerCustom('string', {
        type: 'string',
        widgetType: 'text',
        status: 'custom',
        label: 'String Override',
        diagnostic: null,
        isCustomPlaceholder: true,
      }),
    ).toThrow(/built-in type/);
  });
});

// ---------------------------------------------------------------------------
// Unsupported type diagnostics
// ---------------------------------------------------------------------------

describe('unsupported type diagnostics', () => {
  it('resolves unknown types as unsupported with a diagnostic', () => {
    const reg = fresh();
    expect(reg.isSupported('made-up-type')).toBe(false);
    expect(reg.isCustom('made-up-type')).toBe(false);

    const entry = reg.resolve('made-up-type');
    expect(entry.status).toBe('unsupported');
    expect(entry.widgetType).toBeUndefined();
    expect(entry.isCustomPlaceholder).toBe(false);
    expect(entry.diagnostic).not.toBeNull();
    expect(entry.diagnostic!.code).toBe('schema/unsupported-type');
    expect(entry.diagnostic!.severity).toBe('warning');
    expect(entry.diagnostic!.message).toContain('made-up-type');
    expect(entry.diagnostic!.detail).toEqual({ unsupportedType: 'made-up-type' });
  });

  it('getDiagnostic returns a valid diagnostic for unknown types', () => {
    const reg = fresh();
    const d = reg.getDiagnostic('nonexistent');
    expect(d).not.toBeNull();
    expect(d!.code).toBe('schema/unsupported-type');
    expect(d!.severity).toBe('warning');
    expect(d!.message).toContain('nonexistent');
  });

  it('unsupported types are NOT added to the entries map (they are ephemeral)', () => {
    const reg = fresh();
    reg.resolve('unknown');
    expect(reg.entries.has('unknown')).toBe(false);
  });

  it('unsupported diagnostic includes extensionId when owner is provided', () => {
    const reg = createSchemaCapabilityRegistry('my-extension');
    const entry = reg.resolve('bad-type');
    expect(entry.diagnostic!.extensionId).toBe('my-extension');
  });

  it('resolve returns a fresh unsupported entry each call for unknown types', () => {
    const reg = fresh();
    const a = reg.resolve('type-a');
    const b = reg.resolve('type-b');
    expect(a.type).toBe('type-a');
    expect(b.type).toBe('type-b');
    expect(a.diagnostic!.message).toContain('type-a');
    expect(b.diagnostic!.message).toContain('type-b');
  });

  it('resolve returns consistent label for unknown types', () => {
    const reg = fresh();
    const entry = reg.resolve('video-url');
    expect(entry.label).toBe('video-url');
    expect(entry.status).toBe('unsupported');
  });
});

// ---------------------------------------------------------------------------
// Validation path mapping
// ---------------------------------------------------------------------------

describe('validation path mapping', () => {
  it('built-in validation paths cover number, shader scalars, vectors, boolean, select, color, audio-binding', () => {
    const reg = fresh();
    const paths = [...reg.validationPaths.keys()];
    // At least the five type-specific paths should exist
    expect(paths.length).toBeGreaterThanOrEqual(8);
    expect(reg.validationPaths.has('*')).toBe(true);
    expect(reg.validationPaths.has('shader-scalar-path')).toBe(true);
    expect(reg.validationPaths.has('shader-vector-path')).toBe(true);
    expect(reg.validationPaths.has('shader-color-vector-path')).toBe(true);
    expect(reg.validationPaths.has('boolean-path')).toBe(true);
    expect(reg.validationPaths.has('select-path')).toBe(true);
    expect(reg.validationPaths.has('color-path')).toBe(true);
    expect(reg.validationPaths.has('audio-binding-path')).toBe(true);
  });

  it('number validation: returns error for NaN', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('*')!;
    expect(path).toBeDefined();
    const err = path.validate('not-a-number', makeDef({ type: 'number', label: 'Size' }));
    expect(err).toBe('"Size" must be a number.');
  });

  it('number validation: returns error if below min', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('*')!;
    const err = path.validate(-5, makeDef({ type: 'number', label: 'Size', min: 0, max: 100 }));
    expect(err).toBe('"Size" must be at least 0.');
  });

  it('number validation: returns error if above max', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('*')!;
    const err = path.validate(200, makeDef({ type: 'number', label: 'Size', min: 0, max: 100 }));
    expect(err).toBe('"Size" must be at most 100.');
  });

  it('number validation: returns null for valid value', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('*')!;
    expect(path.validate(50, makeDef({ type: 'number', label: 'Size', min: 0, max: 100 }))).toBeNull();
    expect(path.validate(undefined, makeDef({ type: 'number' }))).toBeNull();
    expect(path.validate(null, makeDef({ type: 'number' }))).toBeNull();
  });

  it('number validation: skips non-number types', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('*')!;
    // Should return null because def.type is 'string', not 'number'
    expect(path.validate('anything', makeDef({ type: 'string' }))).toBeNull();
  });

  it('boolean validation: returns error for non-boolean', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('boolean-path')!;
    const err = path.validate('yes', makeDef({ type: 'boolean', label: 'Enabled' }));
    expect(err).toBe('"Enabled" must be true or false.');
  });

  it('boolean validation: returns null for valid booleans', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('boolean-path')!;
    expect(path.validate(true, makeDef({ type: 'boolean' }))).toBeNull();
    expect(path.validate(false, makeDef({ type: 'boolean' }))).toBeNull();
    expect(path.validate(undefined, makeDef({ type: 'boolean' }))).toBeNull();
  });

  it('shader scalar validation covers float, int, frame, and time', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('shader-scalar-path')!;

    expect(path.validate(0.5, makeDef({ type: 'float' as const, label: 'Gain' }))).toBeNull();
    expect(path.validate(12, makeDef({ type: 'frame' as const, label: 'Frame' }))).toBeNull();
    expect(path.validate(1.25, makeDef({ type: 'time' as const, label: 'Time' }))).toBeNull();
    expect(path.validate(3.2, makeDef({ type: 'int' as const, label: 'Count' }))).toBe('"Count" must be an integer.');
    expect(path.validate(Number.NaN, makeDef({ type: 'float' as const, label: 'Gain' }))).toBe('"Gain" must be a finite number.');
  });

  it('shader vector validation covers vec2, vec3, vec4, and color vectors', () => {
    const reg = fresh();
    const vectorPath = reg.validationPaths.get('shader-vector-path')!;
    const colorPath = reg.validationPaths.get('shader-color-vector-path')!;

    expect(vectorPath.validate([1, 2], makeDef({ type: 'vec2' as const, label: 'Offset' }))).toBeNull();
    expect(vectorPath.validate([1, 2, 3], makeDef({ type: 'vec3' as const, label: 'Axis' }))).toBeNull();
    expect(vectorPath.validate([1, 2, 3, 4], makeDef({ type: 'vec4' as const, label: 'Bounds' }))).toBeNull();
    expect(vectorPath.validate([1, 2], makeDef({ type: 'vec3' as const, label: 'Axis' }))).toBe('"Axis" must be a 3-number vector.');
    expect(colorPath.validate([1, 0.5, 0, 1], makeDef({ type: 'color', label: 'Tint' }))).toBeNull();
    expect(colorPath.validate([1, 0.5, 0], makeDef({ type: 'color', label: 'Tint' }))).toBe('"Tint" must be a 4-number RGBA vector.');
  });

  it('select validation: returns error for invalid option', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('select-path')!;
    const err = path.validate('invalid', makeDef({
      type: 'select',
      label: 'Theme',
      options: [{ label: 'Dark', value: 'dark' }, { label: 'Light', value: 'light' }],
    }));
    expect(err).toBe('"invalid" is not a valid option for "Theme".');
  });

  it('select validation: returns null for valid option', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('select-path')!;
    expect(path.validate('dark', makeDef({
      type: 'select',
      options: [{ label: 'Dark', value: 'dark' }],
    }))).toBeNull();
  });

  it('select validation: returns error for non-string value', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('select-path')!;
    const err = path.validate(42, makeDef({ type: 'select', label: 'Count' }));
    expect(err).toBe('"Count" must be a string option value.');
  });

  it('color validation: returns error for invalid hex', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('color-path')!;
    expect(path.validate('blue', makeDef({ type: 'color', label: 'Tint' })))
      .toBe('"blue" is not a valid hex color.');
    expect(path.validate('rgb(1,2,3)', makeDef({ type: 'color', label: 'Tint' })))
      .toBe('"rgb(1,2,3)" is not a valid hex color.');
  });

  it('color validation: returns null for valid hex colors', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('color-path')!;
    expect(path.validate('#ff0000', makeDef({ type: 'color' }))).toBeNull();
    expect(path.validate('#FFF', makeDef({ type: 'color' }))).toBeNull();
    expect(path.validate('#12345678', makeDef({ type: 'color' }))).toBeNull();
  });

  it('color validation: returns error for non-string', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('color-path')!;
    expect(path.validate(0xff0000, makeDef({ type: 'color', label: 'Tint' })))
      .toBe('"Tint" must be a hex color string.');
  });

  it('audio-binding validation: returns error for invalid source', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('audio-binding-path')!;
    const err = path.validate(
      { source: 'noise', min: 0, max: 1 },
      makeDef({ type: 'audio-binding', label: 'Binding' }),
    );
    expect(err).toContain('source must be one of');
  });

  it('audio-binding validation: returns error for missing min', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('audio-binding-path')!;
    const err = path.validate(
      { source: 'bass', max: 1 },
      makeDef({ type: 'audio-binding', label: 'Binding' }),
    );
    expect(err).toBe('"Binding" min must be a number.');
  });

  it('audio-binding validation: returns error when min > max', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('audio-binding-path')!;
    const err = path.validate(
      { source: 'bass', min: 5, max: 1 },
      makeDef({ type: 'audio-binding', label: 'Binding' }),
    );
    expect(err).toBe('"Binding" min must be <= max.');
  });

  it('audio-binding validation: returns null for valid binding', () => {
    const reg = fresh();
    const path = reg.validationPaths.get('audio-binding-path')!;
    expect(path.validate(
      { source: 'treble', min: 2, max: 4 },
      makeDef({ type: 'audio-binding' }),
    )).toBeNull();
  });

  it('registerValidation adds a new validation path', () => {
    const reg = fresh();
    const custom: ValidationPathEntry = {
      path: 'custom-path',
      validate: (_v, _d) => 'custom error',
    };
    reg.registerValidation('custom-path', custom);
    expect(reg.validationPaths.has('custom-path')).toBe(true);
    expect(reg.validationPaths.get('custom-path')!.validate(null, makeDef())).toBe('custom error');
  });

  it('registerValidation can override an existing path', () => {
    const reg = fresh();
    const override: ValidationPathEntry = {
      path: 'color-path',
      validate: () => 'overridden',
    };
    reg.registerValidation('color-path', override);
    expect(reg.validationPaths.get('color-path')!.validate('anything', makeDef())).toBe('overridden');
  });

  it('validation paths are independent per registry instance', () => {
    const reg1 = fresh();
    const reg2 = fresh();

    reg1.registerValidation('only-in-reg1', {
      path: 'only-in-reg1',
      validate: () => 'reg1 error',
    });

    expect(reg1.validationPaths.has('only-in-reg1')).toBe(true);
    expect(reg2.validationPaths.has('only-in-reg1')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Registry isolation / owner identity
// ---------------------------------------------------------------------------

describe('registry isolation', () => {
  it('each createSchemaCapabilityRegistry() returns an independent registry', () => {
    const a = fresh();
    const b = fresh();

    a.registerCustom('a-only', {
      type: 'a-only',
      widgetType: undefined,
      status: 'custom',
      label: 'A Only',
      diagnostic: null,
      isCustomPlaceholder: true,
    });

    expect(a.isCustom('a-only')).toBe(true);
    expect(b.isCustom('a-only')).toBe(false);
  });

  it('ownerExtensionId is reflected in unsupported diagnostics', () => {
    const reg = createSchemaCapabilityRegistry('ext-abc');
    const diag = reg.getDiagnostic('unknown-type')!;
    expect(diag.extensionId).toBe('ext-abc');
  });

  it('ownerExtensionId is reflected in built-in unsupported textureRef diagnostics', () => {
    const reg = createSchemaCapabilityRegistry('ext-abc');
    const entry = reg.resolve('textureRef');
    expect(entry.diagnostic?.extensionId).toBe('ext-abc');
    expect(reg.getDiagnostic('textureRef')?.extensionId).toBe('ext-abc');
  });

  it('ownerExtensionId null yields diagnostics without extensionId', () => {
    const reg = fresh();
    const diag = reg.getDiagnostic('unknown-type')!;
    expect(diag.extensionId).toBeUndefined();
  });
});
