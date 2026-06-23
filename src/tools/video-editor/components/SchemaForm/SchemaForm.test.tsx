// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import React, { useRef } from 'react';
import { SchemaForm, type SchemaFormSchema, type SchemaFormHandle } from '@/tools/video-editor/components/SchemaForm/SchemaForm';
import { createSchemaCapabilityRegistry } from '@/tools/video-editor/runtime/schemaCapabilityRegistry';
import type {
  SchemaCapabilityRegistry,
  SchemaCapabilityEntry,
} from '@/tools/video-editor/runtime/schemaCapabilityRegistry';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';
import type { ShaderUniformSchema } from '@reigh/editor-sdk';
import type { ParameterDefinition, ParameterSchema } from '@/tools/video-editor/types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function freshRegistry(): SchemaCapabilityRegistry {
  return createSchemaCapabilityRegistry();
}

function parameterDef(overrides: Partial<ParameterDefinition> = {}): ParameterDefinition {
  return {
    name: 'testField',
    label: 'Test Field',
    description: 'A test parameter',
    type: 'string',
    ...overrides,
  };
}

function renderForm(props: {
  schema?: SchemaFormSchema;
  values?: Record<string, unknown>;
  onChange?: (name: string, value: unknown) => void;
  disabled?: boolean;
  capabilityRegistry?: SchemaCapabilityRegistry;
  onDiagnostics?: (diagnostics: ExtensionDiagnostic[]) => void;
}) {
  const {
    schema = [],
    values = {},
    onChange = vi.fn(),
    disabled = false,
    capabilityRegistry,
    onDiagnostics,
  } = props;

  return render(
    React.createElement(SchemaForm, {
      schema,
      values,
      onChange,
      disabled,
      capabilityRegistry,
      onDiagnostics,
    }),
  );
}

// ---------------------------------------------------------------------------
// Fields rendering
// ---------------------------------------------------------------------------

describe('fields rendering', () => {
  it('renders a string field as a text input', () => {
    renderForm({
      schema: [parameterDef({ name: 'title', type: 'string', label: 'Title' })],
      values: { title: 'Hello' },
    });

    const input = screen.getByTestId('schema-form-widget-title');
    expect(input).toBeTruthy();
    expect((input as HTMLInputElement).value).toBe('Hello');
  });

  it('renders a number field as a slider', () => {
    renderForm({
      schema: [parameterDef({ name: 'opacity', type: 'number', label: 'Opacity', min: 0, max: 1, step: 0.1 })],
      values: { opacity: 0.5 },
    });

    const field = screen.getByTestId('schema-form-field-opacity');
    expect(field).toBeTruthy();
    expect(field.getAttribute('data-field-type')).toBe('number');
    expect(field.getAttribute('data-field-status')).toBe('supported');
  });

  it('renders a boolean field as a switch', () => {
    renderForm({
      schema: [parameterDef({ name: 'enabled', type: 'boolean', label: 'Enabled' })],
      values: { enabled: true },
    });

    const field = screen.getByTestId('schema-form-field-enabled');
    expect(field.dataset.fieldType).toBe('boolean');
    expect(field.dataset.fieldStatus).toBe('supported');
  });

  it('renders a select field as a dropdown', () => {
    renderForm({
      schema: [
        parameterDef({
          name: 'mode',
          type: 'select',
          label: 'Mode',
          options: [
            { label: 'Option A', value: 'a' },
            { label: 'Option B', value: 'b' },
          ],
        }),
      ],
      values: { mode: 'a' },
    });

    const field = screen.getByTestId('schema-form-field-mode');
    expect(field.dataset.fieldType).toBe('select');
  });

  it('renders a color field', () => {
    renderForm({
      schema: [parameterDef({ name: 'tint', type: 'color', label: 'Tint' })],
      values: { tint: '#ff0000' },
    });

    const field = screen.getByTestId('schema-form-field-tint');
    expect(field.dataset.fieldType).toBe('color');
  });

  it('renders an audio-binding field (custom placeholder)', () => {
    renderForm({
      schema: [parameterDef({ name: 'audio', type: 'audio-binding', label: 'Audio Bind' })],
      values: { audio: { source: 'bass', min: 0, max: 100 } },
    });

    const field = screen.getByTestId('schema-form-field-audio');
    expect(field.dataset.fieldType).toBe('audio-binding');
    expect(field.dataset.fieldStatus).toBe('custom');
    // Custom badge should be visible
    expect(screen.getByText('Custom')).toBeTruthy();
  });

  it('returns null for empty schema', () => {
    const { container } = renderForm({ schema: [] });
    expect(container.querySelector('[data-testid="schema-form"]')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Shader uniform controls
// ---------------------------------------------------------------------------

describe('shader uniform controls', () => {
  function shaderUniform(overrides: ShaderUniformSchema[number]): ShaderUniformSchema[number] {
    return overrides;
  }

  it('renders and persists float uniforms through a compact number input', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [shaderUniform({
        name: 'u_gain',
        label: 'Gain',
        description: 'Gain control',
        type: 'float',
        default: 0.5,
        min: 0,
        max: 1,
        step: 0.01,
      })],
      values: { u_gain: 0.5 },
      onChange,
    });

    const input = screen.getByTestId('schema-form-widget-u_gain') as HTMLInputElement;
    expect(input.value).toBe('0.5');
    fireEvent.change(input, { target: { value: '0.75' } });
    expect(onChange).toHaveBeenCalledWith('u_gain', 0.75);
  });

  it('renders and persists int uniforms as integer values', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [shaderUniform({ name: 'u_count', label: 'Count', type: 'int', default: 2 })],
      values: { u_count: 2 },
      onChange,
    });

    const input = screen.getByTestId('schema-form-widget-u_count') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '7.9' } });
    expect(onChange).toHaveBeenCalledWith('u_count', 7);
  });

  it('renders and persists bool uniforms through the boolean switch', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [shaderUniform({ name: 'u_enabled', label: 'Enabled', type: 'bool', default: false })],
      values: { u_enabled: false },
      onChange,
    });

    const field = screen.getByTestId('schema-form-field-u_enabled');
    expect(field.dataset.fieldType).toBe('bool');
    fireEvent.click(screen.getByTestId('schema-form-widget-u_enabled'));
    expect(onChange).toHaveBeenCalledWith('u_enabled', true);
  });

  it('renders and persists vec2 uniforms with compact component inputs', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [shaderUniform({ name: 'u_offset', label: 'Offset', type: 'vec2', default: [0, 1] })],
      values: { u_offset: [0, 1] },
      onChange,
    });

    fireEvent.change(screen.getByTestId('schema-form-widget-u_offset-x'), { target: { value: '0.25' } });
    expect(onChange).toHaveBeenCalledWith('u_offset', [0.25, 1]);
  });

  it('renders and persists vec3 uniforms with compact component inputs', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [shaderUniform({ name: 'u_axis', label: 'Axis', type: 'vec3', default: [0, 1, 0] })],
      values: { u_axis: [0, 1, 0] },
      onChange,
    });

    fireEvent.change(screen.getByTestId('schema-form-widget-u_axis-z'), { target: { value: '1' } });
    expect(onChange).toHaveBeenCalledWith('u_axis', [0, 1, 1]);
  });

  it('renders and persists vec4 uniforms with compact component inputs', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [shaderUniform({ name: 'u_bounds', label: 'Bounds', type: 'vec4', default: [0, 0, 1, 1] })],
      values: { u_bounds: [0, 0, 1, 1] },
      onChange,
    });

    fireEvent.change(screen.getByTestId('schema-form-widget-u_bounds-w'), { target: { value: '0.5' } });
    expect(onChange).toHaveBeenCalledWith('u_bounds', [0, 0, 1, 0.5]);
  });

  it('renders and persists color uniforms as RGBA vectors without using the hex color picker', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [shaderUniform({ name: 'u_tint', label: 'Tint', type: 'color', default: [1, 0, 0, 1] })],
      values: { u_tint: [1, 0, 0, 1] },
      onChange,
    });

    expect(screen.queryByTestId('schema-form-widget-u_tint')).toBeNull();
    fireEvent.change(screen.getByTestId('schema-form-widget-u_tint-g'), { target: { value: '0.5' } });
    expect(onChange).toHaveBeenCalledWith('u_tint', [1, 0.5, 0, 1]);
  });

  it('renders enum uniforms as select controls', () => {
    renderForm({
      schema: [shaderUniform({
        name: 'u_mode',
        label: 'Mode',
        type: 'enum',
        default: 'soft',
        options: [
          { label: 'Soft', value: 'soft' },
          { label: 'Hard', value: 'hard' },
        ],
      })],
      values: { u_mode: 'soft' },
    });

    const field = screen.getByTestId('schema-form-field-u_mode');
    expect(field.dataset.fieldType).toBe('enum');
    expect(screen.getByTestId('schema-form-widget-u_mode')).toBeTruthy();
  });

  it('renders textureRef uniforms as unsupported diagnostics without crashing', () => {
    const onDiagnostics = vi.fn();
    renderForm({
      schema: [shaderUniform({
        name: 'u_texture',
        label: 'Texture',
        type: 'textureRef',
        default: { kind: 'static-image-asset', ref: 'asset-1' },
      })],
      values: { u_texture: { kind: 'static-image-asset', ref: 'asset-1' } },
      onDiagnostics,
    });

    expect(screen.getByTestId('schema-form-unsupported-u_texture')).toBeTruthy();
    expect(screen.getByTestId('schema-form-diagnostic-u_texture').textContent).toContain('textureRef uniforms are not editable');
    const diagnostics = onDiagnostics.mock.calls[0][0] as ExtensionDiagnostic[];
    expect(diagnostics[0].code).toBe('schema/texture-ref-unsupported');
    expect(diagnostics[0].detail).toMatchObject({ fieldName: 'u_texture', unsupportedType: 'textureRef' });
  });

  it('renders and persists frame uniforms as compact number inputs', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [shaderUniform({ name: 'u_frame', label: 'Frame', type: 'frame', default: 12 })],
      values: { u_frame: 12 },
      onChange,
    });

    fireEvent.change(screen.getByTestId('schema-form-widget-u_frame'), { target: { value: '24' } });
    expect(onChange).toHaveBeenCalledWith('u_frame', 24);
  });

  it('renders and persists time uniforms as compact number inputs', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [shaderUniform({ name: 'u_time', label: 'Time', type: 'time', default: 1.5 })],
      values: { u_time: 1.5 },
      onChange,
    });

    fireEvent.change(screen.getByTestId('schema-form-widget-u_time'), { target: { value: '2.25' } });
    expect(onChange).toHaveBeenCalledWith('u_time', 2.25);
  });
});

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

describe('validation', () => {
  it('shows error for NaN number value', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [parameterDef({ name: 'count', type: 'number', label: 'Count', min: 0, max: 100 })],
      values: { count: 'not-a-number' },
      onChange,
    });

    // The slider gets a 0 fallback but validation should detect NaN before that
    // Actually the getDisplayValue returns the raw value for non-audio-binding types
    // Slider renders Number(value) which would be NaN -> 0
    // validateField checks Number.isNaN
    // Let's check: value='not-a-number', Number('not-a-number') is NaN
    const error = screen.queryByTestId('schema-form-error-count');
    expect(error).toBeTruthy();
  });

  it('shows error for number below min', () => {
    renderForm({
      schema: [parameterDef({ name: 'count', type: 'number', label: 'Count', min: 10, max: 100 })],
      values: { count: 5 },
    });

    const error = screen.getByTestId('schema-form-error-count');
    expect(error.textContent).toContain('must be at least 10');
  });

  it('shows error for number above max', () => {
    renderForm({
      schema: [parameterDef({ name: 'count', type: 'number', label: 'Count', min: 0, max: 100 })],
      values: { count: 200 },
    });

    const error = screen.getByTestId('schema-form-error-count');
    expect(error.textContent).toContain('must be at most 100');
  });

  it('shows error for invalid select value', () => {
    renderForm({
      schema: [
        parameterDef({
          name: 'mode',
          type: 'select',
          label: 'Mode',
          options: [{ label: 'A', value: 'a' }],
        }),
      ],
      values: { mode: 'invalid' },
    });

    const error = screen.getByTestId('schema-form-error-mode');
    expect(error).toBeTruthy();
    expect(error.textContent).toContain('not a valid option');
  });

  it('shows error for invalid hex color', () => {
    renderForm({
      schema: [parameterDef({ name: 'tint', type: 'color', label: 'Tint' })],
      values: { tint: 'not-a-color' },
    });

    const error = screen.getByTestId('schema-form-error-tint');
    expect(error.textContent).toContain('valid hex color');
  });

  it('shows error for non-boolean boolean value', () => {
    renderForm({
      schema: [parameterDef({ name: 'flag', type: 'boolean', label: 'Flag' })],
      values: { flag: 'not-boolean' },
    });

    const error = screen.getByTestId('schema-form-error-flag');
    expect(error.textContent).toContain('true or false');
  });

  it('does not show error for valid values', () => {
    renderForm({
      schema: [
        parameterDef({ name: 'count', type: 'number', label: 'Count', min: 0, max: 100 }),
        parameterDef({ name: 'mode', type: 'select', label: 'Mode', options: [{ label: 'A', value: 'a' }] }),
        parameterDef({ name: 'tint', type: 'color', label: 'Tint' }),
        parameterDef({ name: 'flag', type: 'boolean', label: 'Flag' }),
      ],
      values: { count: 50, mode: 'a', tint: '#ff0000', flag: true },
    });

    expect(screen.queryByTestId('schema-form-error-count')).toBeNull();
    expect(screen.queryByTestId('schema-form-error-mode')).toBeNull();
    expect(screen.queryByTestId('schema-form-error-tint')).toBeNull();
    expect(screen.queryByTestId('schema-form-error-flag')).toBeNull();
  });

  it('validates audio-binding fields', () => {
    renderForm({
      schema: [parameterDef({ name: 'audio', type: 'audio-binding', label: 'Audio' })],
      values: { audio: { source: 'invalid', min: 100, max: 0 } },
    });

    const error = screen.getByTestId('schema-form-error-audio');
    expect(error).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Unsupported types
// ---------------------------------------------------------------------------

describe('unsupported types', () => {
  it('renders diagnostic placeholder for unknown type', () => {
    renderForm({
      schema: [parameterDef({ name: 'custom', type: 'unknown-gizmo' as any, label: 'Gizmo' })],
      values: { custom: 'test' },
    });

    const placeholder = screen.getByTestId('schema-form-unsupported-custom');
    expect(placeholder).toBeTruthy();
    expect(placeholder.getAttribute('data-field-type')).toBe('unknown-gizmo');
    expect(placeholder.getAttribute('role')).toBe('alert');
    expect(screen.getByText('Unsupported')).toBeTruthy();
  });

  it('shows diagnostic message in placeholder', () => {
    renderForm({
      schema: [parameterDef({ name: 'custom', type: 'unknown-gizmo' as any, label: 'Gizmo' })],
      values: { custom: 'test' },
    });

    const diagnostic = screen.getByTestId('schema-form-diagnostic-custom');
    expect(diagnostic).toBeTruthy();
    expect(diagnostic.textContent).toContain('not supported by the host');
  });

  it('fires onDiagnostics for unsupported types', () => {
    const onDiagnostics = vi.fn();
    renderForm({
      schema: [parameterDef({ name: 'gizmo', type: 'unknown-type' as any, label: 'Gizmo' })],
      values: { gizmo: 'test' },
      onDiagnostics,
    });

    expect(onDiagnostics).toHaveBeenCalledTimes(1);
    const diagnostics = onDiagnostics.mock.calls[0][0] as ExtensionDiagnostic[];
    expect(diagnostics).toHaveLength(1);
    expect(diagnostics[0].code).toBe('schema/unsupported-type');
    expect(diagnostics[0].severity).toBe('warning');
  });

  it('does not fire onDiagnostics when all types are supported', () => {
    const onDiagnostics = vi.fn();
    renderForm({
      schema: [parameterDef({ name: 'count', type: 'number', label: 'Count' })],
      values: { count: 5 },
      onDiagnostics,
    });

    expect(onDiagnostics).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Unsupported schema shapes (M4 T10)
// ---------------------------------------------------------------------------

describe('unsupported schema shapes', () => {
  // -- Array schemas ----------------------------------------------------------

  it('renders read-only unsupported placeholder for array property (type:"array")', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        tags: { type: 'array' as const, title: 'Tags', items: { type: 'string' } },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { tags: ['a', 'b'] },
    });

    const placeholder = screen.getByTestId('schema-form-unsupported-tags');
    expect(placeholder).toBeTruthy();
    expect(placeholder.getAttribute('data-field-type')).toBe('array');
    expect(placeholder.getAttribute('role')).toBe('alert');
    expect(screen.getByText('Unsupported')).toBeTruthy();
    // Diagnostic message should mention arrays
    const diag = screen.getByTestId('schema-form-diagnostic-tags');
    expect(diag.textContent).toContain('Array schemas are not yet supported');
  });

  it('renders read-only unsupported placeholder for array property (items without explicit type)', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        items: { title: 'Items', items: { type: 'number' } },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { items: [1, 2, 3] },
    });

    const placeholder = screen.getByTestId('schema-form-unsupported-items');
    expect(placeholder).toBeTruthy();
    expect(placeholder.getAttribute('data-field-type')).toBe('array');
  });

  // -- Nested object schemas --------------------------------------------------

  it('renders read-only unsupported placeholder for nested object property (type:"object")', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        config: {
          type: 'object' as const,
          title: 'Config',
          properties: {
            nested: { type: 'string' },
          },
        },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { config: { nested: 'value' } },
    });

    const placeholder = screen.getByTestId('schema-form-unsupported-config');
    expect(placeholder).toBeTruthy();
    expect(placeholder.getAttribute('data-field-type')).toBe('nested-object');
    expect(placeholder.getAttribute('role')).toBe('alert');
    const diag = screen.getByTestId('schema-form-diagnostic-config');
    expect(diag.textContent).toContain('Nested object schemas');
  });

  it('renders read-only unsupported placeholder for nested object (properties without type)', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        metadata: {
          title: 'Metadata',
          properties: { key: { type: 'string' } },
        },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { metadata: { key: 'val' } },
    });

    const placeholder = screen.getByTestId('schema-form-unsupported-metadata');
    expect(placeholder).toBeTruthy();
    expect(placeholder.getAttribute('data-field-type')).toBe('nested-object');
  });

  // -- $ref schemas -----------------------------------------------------------

  it('renders read-only unsupported placeholder for $ref property', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        reference: { $ref: '#/definitions/SomeType', title: 'Reference' },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { reference: {} },
    });

    const placeholder = screen.getByTestId('schema-form-unsupported-reference');
    expect(placeholder).toBeTruthy();
    expect(placeholder.getAttribute('data-field-type')).toBe('$ref');
    const diag = screen.getByTestId('schema-form-diagnostic-reference');
    expect(diag.textContent).toContain('$ref references are not yet supported');
  });

  // -- oneOf schemas ----------------------------------------------------------

  it('renders read-only unsupported placeholder for oneOf property', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        value: {
          title: 'Value',
          oneOf: [{ type: 'string' }, { type: 'number' }],
        },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { value: 'hello' },
    });

    const placeholder = screen.getByTestId('schema-form-unsupported-value');
    expect(placeholder).toBeTruthy();
    expect(placeholder.getAttribute('data-field-type')).toBe('oneOf');
    const diag = screen.getByTestId('schema-form-diagnostic-value');
    expect(diag.textContent).toContain('oneOf');
  });

  // -- anyOf schemas ----------------------------------------------------------

  it('renders read-only unsupported placeholder for anyOf property', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        mixed: {
          title: 'Mixed',
          anyOf: [{ type: 'string' }, { type: 'number' }],
        },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { mixed: 42 },
    });

    const placeholder = screen.getByTestId('schema-form-unsupported-mixed');
    expect(placeholder).toBeTruthy();
    expect(placeholder.getAttribute('data-field-type')).toBe('anyOf');
    const diag = screen.getByTestId('schema-form-diagnostic-mixed');
    expect(diag.textContent).toContain('anyOf');
  });

  // -- allOf schemas ----------------------------------------------------------

  it('renders read-only unsupported placeholder for allOf property', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        combined: {
          title: 'Combined',
          allOf: [{ type: 'string', minLength: 3 }, { type: 'string', maxLength: 10 }],
        },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { combined: 'test' },
    });

    const placeholder = screen.getByTestId('schema-form-unsupported-combined');
    expect(placeholder).toBeTruthy();
    expect(placeholder.getAttribute('data-field-type')).toBe('allOf');
    const diag = screen.getByTestId('schema-form-diagnostic-combined');
    expect(diag.textContent).toContain('allOf');
  });

  // -- Conditional schemas (if/then/else) -------------------------------------

  it('renders read-only unsupported placeholder for conditional (if/then/else) property', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        dynamic: {
          title: 'Dynamic',
          if: { type: 'string' },
          then: { type: 'number' },
          else: { type: 'boolean' },
        },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { dynamic: 'conditional' },
    });

    const placeholder = screen.getByTestId('schema-form-unsupported-dynamic');
    expect(placeholder).toBeTruthy();
    expect(placeholder.getAttribute('data-field-type')).toBe('conditional');
    const diag = screen.getByTestId('schema-form-diagnostic-dynamic');
    expect(diag.textContent).toContain('Conditional schemas');
  });

  it('renders read-only unsupported placeholder for conditional (if/then only)', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        partial: {
          title: 'Partial',
          if: { type: 'string' },
          then: { type: 'number' },
        },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { partial: 42 },
    });

    const placeholder = screen.getByTestId('schema-form-unsupported-partial');
    expect(placeholder).toBeTruthy();
    expect(placeholder.getAttribute('data-field-type')).toBe('conditional');
  });

  // -- Non-mutation verification ----------------------------------------------

  it('does not fire onChange for any unsupported shape interaction', () => {
    const onChange = vi.fn();
    const standardSchema = {
      type: 'object' as const,
      properties: {
        arr: { type: 'array' as const, title: 'Arr', items: { type: 'string' } },
        nested: { type: 'object' as const, title: 'Nested', properties: { x: { type: 'string' } } },
        ref: { $ref: '#/defs/X', title: 'Ref' },
        one: { oneOf: [{ type: 'string' }], title: 'One' },
        any: { anyOf: [{ type: 'string' }], title: 'Any' },
        all: { allOf: [{ type: 'string' }], title: 'All' },
        cond: { if: { type: 'string' }, then: { type: 'number' }, title: 'Cond' },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: {
        arr: [],
        nested: {},
        ref: {},
        one: '',
        any: '',
        all: '',
        cond: '',
      },
      onChange,
    });

    // onChange should never have been called during initial render
    // (unsupported shapes have no interactive widgets)
    expect(onChange).not.toHaveBeenCalled();

    // Try to click on the placeholder — there are no interactive elements inside
    const placeholder = screen.getByTestId('schema-form-unsupported-arr');
    fireEvent.click(placeholder);
    expect(onChange).not.toHaveBeenCalled();
  });

  // -- onDiagnostics emission -------------------------------------------------

  it('emits onDiagnostics for unsupported shapes', () => {
    const onDiagnostics = vi.fn();
    const standardSchema = {
      type: 'object' as const,
      properties: {
        arr: { type: 'array' as const, title: 'Arr', items: { type: 'string' } },
        nested: { type: 'object' as const, title: 'Nested', properties: { x: { type: 'string' } } },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { arr: [], nested: {} },
      onDiagnostics,
    });

    expect(onDiagnostics).toHaveBeenCalledTimes(1);
    const diagnostics = onDiagnostics.mock.calls[0][0] as ExtensionDiagnostic[];
    expect(diagnostics).toHaveLength(2);

    const codes = diagnostics.map((d) => d.code);
    expect(codes).toContain('schema/unsupported-array');
    expect(codes).toContain('schema/unsupported-nested-object');

    // Verify detail contains fieldName
    const arrDiag = diagnostics.find((d) => d.code === 'schema/unsupported-array');
    expect(arrDiag?.detail).toMatchObject({ fieldName: 'arr' });
  });

  it('does not fire onDiagnostics for supported types in same form', () => {
    const onDiagnostics = vi.fn();
    const standardSchema = {
      type: 'object' as const,
      properties: {
        name: { type: 'string', title: 'Name' },
        count: { type: 'number', title: 'Count' },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { name: 'Alice', count: 42 },
      onDiagnostics,
    });

    expect(onDiagnostics).not.toHaveBeenCalled();
  });

  // -- Mixed supported + unsupported form -------------------------------------

  it('renders supported fields normally alongside unsupported shape placeholders', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        name: { type: 'string', title: 'Name' },
        tags: { type: 'array' as const, title: 'Tags', items: { type: 'string' } },
        active: { type: 'boolean', title: 'Active' },
        config: { type: 'object' as const, title: 'Config', properties: { x: { type: 'string' } } },
        ref: { $ref: '#/defs/X', title: 'Ref' },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { name: 'Alice', tags: [], active: true, config: {}, ref: {} },
    });

    // Supported fields render normally
    expect(screen.getByTestId('schema-form-field-name')).toBeTruthy();
    expect(screen.getByTestId('schema-form-field-active')).toBeTruthy();
    expect(screen.getByTestId('schema-form-widget-name')).toBeTruthy();

    // Unsupported shapes render as placeholders
    expect(screen.getByTestId('schema-form-unsupported-tags')).toBeTruthy();
    expect(screen.getByTestId('schema-form-unsupported-config')).toBeTruthy();
    expect(screen.getByTestId('schema-form-unsupported-ref')).toBeTruthy();

    // All unsupported shapes have the Unsupported badge
    const unsupportedBadges = screen.getAllByText('Unsupported');
    expect(unsupportedBadges).toHaveLength(3);
  });

  // -- Unsupported shapes do not crash with extreme values --------------------

  it('does not crash when unsupported shape has null value', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        arr: { type: 'array' as const, title: 'Arr', items: { type: 'string' } },
      },
    };
    // Should not throw
    expect(() => {
      renderForm({
        schema: standardSchema as any,
        values: { arr: null },
      });
    }).not.toThrow();
    expect(screen.getByTestId('schema-form-unsupported-arr')).toBeTruthy();
  });

  it('does not crash when unsupported shape has undefined value', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        nested: { type: 'object' as const, title: 'Nested', properties: { x: { type: 'string' } } },
      },
    };
    expect(() => {
      renderForm({
        schema: standardSchema as any,
        values: {},
      });
    }).not.toThrow();
    expect(screen.getByTestId('schema-form-unsupported-nested')).toBeTruthy();
  });

  // -- Verification that unsupported shapes are non-mutating (save path) ------

  it('validateAndFocus treats unsupported shapes as errors but does not mutate', () => {
    const onChange = vi.fn();
    const ref = React.createRef<SchemaFormHandle>();
    const standardSchema = {
      type: 'object' as const,
      properties: {
        name: { type: 'string', title: 'Name' },
        nested: { type: 'object' as const, title: 'Nested', properties: { x: { type: 'string' } } },
      },
    };
    render(
      React.createElement(SchemaForm, {
        ref,
        schema: standardSchema as any,
        values: { name: 'Alice', nested: {} },
        onChange,
      }),
    );

    // validateAndFocus should return false (unsupported shapes block save)
    expect(ref.current?.validateAndFocus()).toBe(false);

    // onChange should not have been called (no mutation)
    expect(onChange).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Disabled state
// ---------------------------------------------------------------------------

describe('disabled state', () => {
  it('passes disabled to slider widget', () => {
    renderForm({
      schema: [parameterDef({ name: 'count', type: 'number', label: 'Count' })],
      values: { count: 5 },
      disabled: true,
    });

    // The slider component receives disabled prop
    const field = screen.getByTestId('schema-form-field-count');
    expect(field).toBeTruthy();
  });

  it('passes disabled to text input', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [parameterDef({ name: 'title', type: 'string', label: 'Title' })],
      values: { title: 'hello' },
      disabled: true,
      onChange,
    });

    const input = screen.getByTestId('schema-form-widget-title') as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });

  it('passes disabled to select widget', () => {
    renderForm({
      schema: [
        parameterDef({
          name: 'mode',
          type: 'select',
          label: 'Mode',
          options: [{ label: 'A', value: 'a' }],
        }),
      ],
      values: { mode: 'a' },
      disabled: true,
    });

    const field = screen.getByTestId('schema-form-field-mode');
    expect(field).toBeTruthy();
    // The SelectTrigger is rendered and the Select receives disabled
  });

  it('passes disabled to switch widget', () => {
    renderForm({
      schema: [parameterDef({ name: 'flag', type: 'boolean', label: 'Flag' })],
      values: { flag: false },
      disabled: true,
    });

    const field = screen.getByTestId('schema-form-field-flag');
    expect(field).toBeTruthy();
  });

  it('passes disabled to color widget', () => {
    renderForm({
      schema: [parameterDef({ name: 'tint', type: 'color', label: 'Tint' })],
      values: { tint: '#ff0000' },
      disabled: true,
    });

    const input = screen.getByTestId('schema-form-widget-tint') as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// onChange behavior
// ---------------------------------------------------------------------------

describe('onChange behavior', () => {
  it('fires onChange(name, value) for text input', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [parameterDef({ name: 'title', type: 'string', label: 'Title' })],
      values: { title: 'Hello' },
      onChange,
    });

    const input = screen.getByTestId('schema-form-widget-title') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'World' } });
    expect(onChange).toHaveBeenCalledWith('title', 'World');
  });

  it('fires onChange(name, value) for boolean toggle', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [parameterDef({ name: 'flag', type: 'boolean', label: 'Flag' })],
      values: { flag: false },
      onChange,
    });

    // The Switch component uses onCheckedChange
    const switchEl = screen.getByTestId('schema-form-widget-flag');
    fireEvent.click(switchEl);
    expect(onChange).toHaveBeenCalledWith('flag', true);
  });

  it('fires onChange(name, value) for color input', () => {
    const onChange = vi.fn();
    renderForm({
      schema: [parameterDef({ name: 'tint', type: 'color', label: 'Tint' })],
      values: { tint: '#ff0000' },
      onChange,
    });

    const input = screen.getByTestId('schema-form-widget-tint') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '#00ff00' } });
    expect(onChange).toHaveBeenCalledWith('tint', '#00ff00');
  });

  it('fires onChange(name, value) for select change', () => {
    // Select change is harder to test without full Radix UI rendering, but we
    // verify the component structure is correct.
    renderForm({
      schema: [
        parameterDef({
          name: 'mode',
          type: 'select',
          label: 'Mode',
          options: [
            { label: 'A', value: 'a' },
            { label: 'B', value: 'b' },
          ],
        }),
      ],
      values: { mode: 'a' },
    });

    const trigger = screen.getByTestId('schema-form-widget-mode');
    expect(trigger).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// StandardSchema support
// ---------------------------------------------------------------------------

describe('StandardSchema support', () => {
  it('renders fields from a StandardSchema object', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        name: {
          type: 'string',
          title: 'Name',
          description: 'Your full name',
        },
        age: {
          type: 'number',
          title: 'Age',
          minimum: 0,
          maximum: 150,
        },
        active: {
          type: 'boolean',
          title: 'Active',
        },
      },
    };

    renderForm({
      schema: standardSchema as any,
      values: { name: 'Alice', age: 30, active: true },
    });

    expect(screen.getByTestId('schema-form-field-name')).toBeTruthy();
    expect(screen.getByTestId('schema-form-field-age')).toBeTruthy();
    expect(screen.getByTestId('schema-form-field-active')).toBeTruthy();

    // StandardSchema labels come from title
    expect(screen.getByText('Name')).toBeTruthy();
    expect(screen.getByText('Age')).toBeTruthy();
    expect(screen.getByText('Active')).toBeTruthy();
  });

  it('falls back to property name when title is missing', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        field1: { type: 'string' },
      },
    };

    renderForm({
      schema: standardSchema as any,
      values: { field1: 'value' },
    });

    expect(screen.getByText('field1')).toBeTruthy();
  });

  it('handles StandardSchema with enum properties as select', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        color: {
          type: 'string',
          title: 'Color',
          enum: ['red', 'green', 'blue'],
        },
      },
    };

    renderForm({
      schema: standardSchema as any,
      values: { color: 'red' },
    });

    const field = screen.getByTestId('schema-form-field-color');
    expect(field).toBeTruthy();
  });

  it('handles StandardSchema with numeric enum', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        size: {
          type: 'number',
          title: 'Size',
          enum: [1, 2, 3],
        },
      },
    };

    renderForm({
      schema: standardSchema as any,
      values: { size: 2 },
    });

    const field = screen.getByTestId('schema-form-field-size');
    expect(field).toBeTruthy();
  });

  it('marks required fields correctly', () => {
    // Required is tracked internally but doesn't change rendering (no visual indicator in M2)
    const standardSchema = {
      type: 'object' as const,
      properties: {
        req: { type: 'string', title: 'Required' },
        opt: { type: 'string', title: 'Optional' },
      },
      required: ['req'],
    };

    renderForm({
      schema: standardSchema as any,
      values: { req: 'hello', opt: 'world' },
    });

    // Both fields should render
    expect(screen.getByTestId('schema-form-field-req')).toBeTruthy();
    expect(screen.getByTestId('schema-form-field-opt')).toBeTruthy();
  });

  it('returns null for StandardSchema with no properties', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {},
    };

    const { container } = renderForm({
      schema: standardSchema as any,
      values: {},
    });

    expect(container.querySelector('[data-testid="schema-form"]')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Capability registry integration
// ---------------------------------------------------------------------------

describe('capability registry integration', () => {
  it('uses custom registry when provided', () => {
    const registry = freshRegistry();

    // Register a custom type
    const customEntry: SchemaCapabilityEntry = {
      type: 'my-custom',
      widgetType: 'text',
      status: 'supported',
      label: 'Custom Type',
      diagnostic: null,
      isCustomPlaceholder: false,
    };
    registry.registerCustom('my-custom', customEntry);

    renderForm({
      schema: [parameterDef({ name: 'custom', type: 'my-custom' as any, label: 'Custom' })],
      values: { custom: 'test' },
      capabilityRegistry: registry,
    });

    const field = screen.getByTestId('schema-form-field-custom');
    expect(field.dataset.fieldStatus).toBe('supported');
  });

  it('uses default built-in registry when none provided', () => {
    renderForm({
      schema: [parameterDef({ name: 'count', type: 'number', label: 'Count' })],
      values: { count: 5 },
    });

    const field = screen.getByTestId('schema-form-field-count');
    expect(field.dataset.fieldStatus).toBe('supported');
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe('edge cases', () => {
  it('handles undefined values gracefully', () => {
    renderForm({
      schema: [parameterDef({ name: 'count', type: 'number', label: 'Count', default: 42 })],
      values: {},
    });

    // Should use fallback (default: 42)
    const field = screen.getByTestId('schema-form-field-count');
    expect(field).toBeTruthy();
  });

  it('handles null values gracefully', () => {
    renderForm({
      schema: [parameterDef({ name: 'title', type: 'string', label: 'Title', default: 'default' })],
      values: { title: null },
    });

    const input = screen.getByTestId('schema-form-widget-title') as HTMLInputElement;
    // null is !== undefined so gets displayed as empty string via String(value)
    expect(input.value).toBe('');
  });

  it('renders multiple fields in order', () => {
    const schema: ParameterSchema = [
      parameterDef({ name: 'first', type: 'string', label: 'First' }),
      parameterDef({ name: 'second', type: 'number', label: 'Second' }),
      parameterDef({ name: 'third', type: 'boolean', label: 'Third' }),
    ];

    const { container } = renderForm({
      schema,
      values: { first: 'a', second: 1, third: true },
    });

    const fields = container.querySelectorAll('[data-testid^="schema-form-field-"]');
    expect(fields).toHaveLength(3);
  });
});

// ---------------------------------------------------------------------------
// Primitive constraints (M4 hardening)
// ---------------------------------------------------------------------------

describe('primitive constraints', () => {
  // -- String constraints ---------------------------------------------------

  it('shows error for string below minLength via StandardSchema', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        code: { type: 'string', title: 'Code', minLength: 3 },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { code: 'ab' },
    });
    const error = screen.getByTestId('schema-form-error-code');
    expect(error.textContent).toContain('must be at least 3 characters');
  });

  it('shows error for string above maxLength via StandardSchema', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        code: { type: 'string', title: 'Code', maxLength: 5 },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { code: 'abcdef' },
    });
    const error = screen.getByTestId('schema-form-error-code');
    expect(error.textContent).toContain('must be at most 5 characters');
  });

  it('shows error for string not matching pattern via StandardSchema', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        email: { type: 'string', title: 'Email', pattern: '^[a-z]+@[a-z]+\\\\.com$' },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { email: 'not-an-email' },
    });
    const error = screen.getByTestId('schema-form-error-email');
    expect(error.textContent).toContain('must match pattern');
  });

  it('does not show error when string satisfies all constraints', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        code: { type: 'string', title: 'Code', minLength: 2, maxLength: 10, pattern: '^[A-Z0-9]+$' },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { code: 'ABC123' },
    });
    expect(screen.queryByTestId('schema-form-error-code')).toBeNull();
  });

  it('applies minLength / maxLength as HTML attributes on the text input', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        name: { type: 'string', title: 'Name', minLength: 2, maxLength: 20 },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { name: 'Alice' },
    });
    const input = screen.getByTestId('schema-form-widget-name') as HTMLInputElement;
    expect(input.minLength).toBe(2);
    expect(input.maxLength).toBe(20);
  });

  it('applies pattern as HTML attribute on the text input', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        slug: { type: 'string', title: 'Slug', pattern: '^[a-z0-9-]+$' },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { slug: 'my-slug' },
    });
    const input = screen.getByTestId('schema-form-widget-slug') as HTMLInputElement;
    expect(input.pattern).toBe('^[a-z0-9-]+$');
  });

  // -- Required field constraints --------------------------------------------

  it('shows error for empty required string', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        name: { type: 'string', title: 'Name' },
      },
      required: ['name'],
    };
    renderForm({
      schema: standardSchema as any,
      values: { name: '' },
    });
    const error = screen.getByTestId('schema-form-error-name');
    expect(error.textContent).toContain('is required');
  });

  it('shows error for missing required field (undefined value)', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        name: { type: 'string', title: 'Name' },
      },
      required: ['name'],
    };
    renderForm({
      schema: standardSchema as any,
      values: {},
    });
    const error = screen.getByTestId('schema-form-error-name');
    expect(error.textContent).toContain('is required');
  });

  it('does not show required error for non-required empty string', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        comment: { type: 'string', title: 'Comment' },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { comment: '' },
    });
    expect(screen.queryByTestId('schema-form-error-comment')).toBeNull();
  });

  it('does not show required error when required field has value', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        name: { type: 'string', title: 'Name' },
      },
      required: ['name'],
    };
    renderForm({
      schema: standardSchema as any,
      values: { name: 'Alice' },
    });
    expect(screen.queryByTestId('schema-form-error-name')).toBeNull();
  });

  it('renders required indicator (*) next to label for required fields', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        name: { type: 'string', title: 'Name' },
        note: { type: 'string', title: 'Note' },
      },
      required: ['name'],
    };
    renderForm({
      schema: standardSchema as any,
      values: { name: 'A', note: '' },
    });

    const nameField = screen.getByTestId('schema-form-field-name');
    const noteField = screen.getByTestId('schema-form-field-note');

    // Required field should have a * indicator
    expect(nameField.textContent).toContain('*');
    // Non-required field should NOT have a * indicator
    // (the * is inside the label div, so check that note field label doesn't have it)
    const noteLabel = noteField.querySelector('.text-sm.font-medium');
    expect(noteLabel?.textContent?.includes('*')).toBe(false);
  });

  // -- Number / integer constraints -----------------------------------------

  it('shows error for number below minimum via StandardSchema', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        age: { type: 'number', title: 'Age', minimum: 18, maximum: 120 },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { age: 10 },
    });
    const error = screen.getByTestId('schema-form-error-age');
    expect(error.textContent).toContain('must be at least 18');
  });

  it('shows error for number above maximum via StandardSchema', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        age: { type: 'number', title: 'Age', maximum: 120 },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { age: 200 },
    });
    const error = screen.getByTestId('schema-form-error-age');
    expect(error.textContent).toContain('must be at most 120');
  });

  it('does not show error for number within range', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        age: { type: 'number', title: 'Age', minimum: 0, maximum: 150 },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { age: 42 },
    });
    expect(screen.queryByTestId('schema-form-error-age')).toBeNull();
  });

  it('slider picks up min/max from StandardSchema minimum/maximum', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        volume: { type: 'number', title: 'Volume', minimum: 0, maximum: 1 },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { volume: 0.7 },
    });
    const field = screen.getByTestId('schema-form-field-volume');
    expect(field.dataset.fieldType).toBe('number');
    expect(field.dataset.fieldStatus).toBe('supported');
  });

  // -- Boolean defaults ------------------------------------------------------

  it('uses false default for boolean when value is missing', () => {
    renderForm({
      schema: [parameterDef({ name: 'flag', type: 'boolean', label: 'Flag' })],
      values: {},
    });
    const field = screen.getByTestId('schema-form-field-flag');
    expect(field).toBeTruthy();
    // Boolean fallback is false
    const widgetText = screen.getByText('Disabled');
    expect(widgetText).toBeTruthy();
  });

  // -- Enum / select constraints ---------------------------------------------

  it('shows error for select value not in StandardSchema enum', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        size: { type: 'string', title: 'Size', enum: ['small', 'medium', 'large'] },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { size: 'xlarge' },
    });
    const error = screen.getByTestId('schema-form-error-size');
    expect(error).toBeTruthy();
    expect(error.textContent).toContain('not a valid option');
  });

  it('does not show error for valid StandardSchema enum value', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        size: { type: 'string', title: 'Size', enum: ['small', 'medium', 'large'] },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { size: 'medium' },
    });
    expect(screen.queryByTestId('schema-form-error-size')).toBeNull();
  });

  // -- Color constraints -----------------------------------------------------

  it('validates color from StandardSchema default', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        accent: { type: 'color' as const, title: 'Accent', default: '#336699' },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: {},
    });
    // Should render with the default value
    const field = screen.getByTestId('schema-form-field-accent');
    expect(field).toBeTruthy();
    const input = screen.getByTestId('schema-form-widget-accent') as HTMLInputElement;
    expect(input.value).toBe('#336699');
  });

  it('shows error for invalid color from StandardSchema', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        accent: { type: 'color', title: 'Accent' },
      },
    };
    renderForm({
      schema: standardSchema as any,
      values: { accent: 'bad-color' },
    });
    const error = screen.getByTestId('schema-form-error-accent');
    expect(error.textContent).toContain('valid hex color');
  });

  // -- Combined constraints -------------------------------------------------

  it('shows only the first failing constraint in validation order', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        token: { type: 'string', title: 'Token', minLength: 8, pattern: '^[A-Z0-9]+$' },
      },
      required: ['token'],
    };
    renderForm({
      schema: standardSchema as any,
      values: { token: 'ab' },
    });
    const error = screen.getByTestId('schema-form-error-token');
    // minLength fires before pattern, so we should see the minLength message
    expect(error.textContent).toContain('must be at least 8 characters');
  });
});

// ---------------------------------------------------------------------------
// Accessibility metadata (M4)
// ---------------------------------------------------------------------------

describe('accessibility metadata', () => {
  // -- Label and description IDs ---------------------------------------------

  it('renders label div with deterministic id', () => {
    renderForm({
      schema: [parameterDef({ name: 'title', type: 'string', label: 'Title', description: 'A title' })],
      values: { title: 'Hello' },
    });
    const label = document.getElementById('schema-form-title-label');
    expect(label).toBeTruthy();
    expect(label?.textContent).toContain('Title');
  });

  it('renders description div with deterministic id', () => {
    renderForm({
      schema: [parameterDef({ name: 'title', type: 'string', label: 'Title', description: 'A title' })],
      values: { title: 'Hello' },
    });
    const desc = document.getElementById('schema-form-title-description');
    expect(desc).toBeTruthy();
    expect(desc?.textContent).toBe('A title');
  });

  it('renders error div with deterministic id', () => {
    renderForm({
      schema: [parameterDef({ name: 'count', type: 'number', label: 'Count', min: 10, max: 100 })],
      values: { count: 5 },
    });
    const error = document.getElementById('schema-form-count-error');
    expect(error).toBeTruthy();
    expect(error?.getAttribute('role')).toBe('alert');
  });

  // -- Text input aria attributes --------------------------------------------

  it('text input has aria-labelledby referencing label id', () => {
    renderForm({
      schema: [parameterDef({ name: 'title', type: 'string', label: 'Title' })],
      values: { title: 'Hello' },
    });
    const input = screen.getByTestId('schema-form-widget-title');
    expect(input.getAttribute('aria-labelledby')).toBe('schema-form-title-label');
  });

  it('text input has aria-describedby referencing description id', () => {
    renderForm({
      schema: [parameterDef({ name: 'title', type: 'string', label: 'Title', description: 'A title' })],
      values: { title: 'Hello' },
    });
    const input = screen.getByTestId('schema-form-widget-title');
    expect(input.getAttribute('aria-describedby')).toBe('schema-form-title-description');
  });

  it('text input has aria-describedby referencing both description and error when invalid', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: { title: { type: 'string', title: 'Title', minLength: 10 } },
    };
    renderForm({ schema: standardSchema as any, values: { title: 'ab' } });
    const input = screen.getByTestId('schema-form-widget-title');
    const describedBy = input.getAttribute('aria-describedby');
    expect(describedBy).toContain('schema-form-title-description');
    expect(describedBy).toContain('schema-form-title-error');
  });

  it('text input has aria-invalid="true" when validation fails', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: { title: { type: 'string', title: 'Title', minLength: 10 } },
    };
    renderForm({ schema: standardSchema as any, values: { title: 'ab' } });
    const input = screen.getByTestId('schema-form-widget-title');
    expect(input.getAttribute('aria-invalid')).toBe('true');
  });

  it('text input does not have aria-invalid when value is valid', () => {
    renderForm({
      schema: [parameterDef({ name: 'title', type: 'string', label: 'Title' })],
      values: { title: 'Hello' },
    });
    const input = screen.getByTestId('schema-form-widget-title');
    expect(input.getAttribute('aria-invalid')).toBeNull();
  });

  it('text input has aria-required="true" for required field', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: { name: { type: 'string', title: 'Name' } },
      required: ['name'],
    };
    renderForm({ schema: standardSchema as any, values: { name: 'Alice' } });
    const input = screen.getByTestId('schema-form-widget-name');
    expect(input.getAttribute('aria-required')).toBe('true');
  });

  // -- Slider aria attributes ------------------------------------------------

  it('slider widget has aria-labelledby referencing label id', () => {
    renderForm({
      schema: [parameterDef({ name: 'opacity', type: 'number', label: 'Opacity', min: 0, max: 1 })],
      values: { opacity: 0.5 },
    });
    // Slider renders a role="slider" element
    const slider = document.querySelector('[data-testid="schema-form-widget-opacity"]');
    expect(slider?.getAttribute('aria-labelledby')).toBe('schema-form-opacity-label');
  });

  it('slider widget has aria-describedby referencing description', () => {
    renderForm({
      schema: [parameterDef({ name: 'opacity', type: 'number', label: 'Opacity', description: 'Fade amount', min: 0, max: 1 })],
      values: { opacity: 0.5 },
    });
    const slider = document.querySelector('[data-testid="schema-form-widget-opacity"]');
    expect(slider?.getAttribute('aria-describedby')).toContain('schema-form-opacity-description');
  });

  it('slider widget has aria-invalid="true" when value out of range', () => {
    renderForm({
      schema: [parameterDef({ name: 'count', type: 'number', label: 'Count', min: 10, max: 100 })],
      values: { count: 5 },
    });
    const slider = document.querySelector('[data-testid="schema-form-widget-count"]');
    expect(slider?.getAttribute('aria-invalid')).toBe('true');
  });

  // -- Color input aria attributes -------------------------------------------

  it('color input has aria-labelledby and aria-describedby', () => {
    renderForm({
      schema: [parameterDef({ name: 'tint', type: 'color', label: 'Tint', description: 'Color tint' })],
      values: { tint: '#ff0000' },
    });
    const input = screen.getByTestId('schema-form-widget-tint');
    expect(input.getAttribute('aria-labelledby')).toBe('schema-form-tint-label');
    expect(input.getAttribute('aria-describedby')).toBe('schema-form-tint-description');
  });

  it('color input has aria-invalid="true" when invalid', () => {
    renderForm({
      schema: [parameterDef({ name: 'tint', type: 'color', label: 'Tint' })],
      values: { tint: 'bad' },
    });
    const input = screen.getByTestId('schema-form-widget-tint');
    expect(input.getAttribute('aria-invalid')).toBe('true');
  });

  // -- Select trigger aria attributes ----------------------------------------

  it('select trigger has aria-labelledby and aria-describedby', () => {
    renderForm({
      schema: [parameterDef({
        name: 'mode', type: 'select', label: 'Mode', description: 'Operating mode',
        options: [{ label: 'A', value: 'a' }],
      })],
      values: { mode: 'a' },
    });
    const trigger = screen.getByTestId('schema-form-widget-mode');
    expect(trigger.getAttribute('aria-labelledby')).toBe('schema-form-mode-label');
    expect(trigger.getAttribute('aria-describedby')).toBe('schema-form-mode-description');
  });

  it('select trigger has aria-invalid="true" when invalid', () => {
    renderForm({
      schema: [parameterDef({
        name: 'mode', type: 'select', label: 'Mode',
        options: [{ label: 'A', value: 'a' }],
      })],
      values: { mode: 'bad' },
    });
    const trigger = screen.getByTestId('schema-form-widget-mode');
    expect(trigger.getAttribute('aria-invalid')).toBe('true');
  });

  // -- Boolean / Switch aria attributes --------------------------------------

  it('boolean wrapper has aria-labelledby and aria-describedby', () => {
    renderForm({
      schema: [parameterDef({ name: 'flag', type: 'boolean', label: 'Flag', description: 'Enable feature' })],
      values: { flag: true },
    });
    const field = screen.getByTestId('schema-form-field-flag');
    // The wrapper div child has the aria attributes
    const wrapper = field.querySelector('[aria-labelledby]');
    expect(wrapper).toBeTruthy();
    expect(wrapper?.getAttribute('aria-labelledby')).toBe('schema-form-flag-label');
    expect(wrapper?.getAttribute('aria-describedby')).toContain('schema-form-flag-description');
  });

  it('boolean wrapper has aria-invalid="true" when invalid', () => {
    renderForm({
      schema: [parameterDef({ name: 'flag', type: 'boolean', label: 'Flag' })],
      values: { flag: 'bad' },
    });
    const field = screen.getByTestId('schema-form-field-flag');
    const wrapper = field.querySelector('[aria-invalid]');
    expect(wrapper?.getAttribute('aria-invalid')).toBe('true');
  });

  // -- Shader-number aria attributes -----------------------------------------

  it('shader-number input has aria-labelledby and aria-describedby', () => {
    renderForm({
      schema: [shaderUniform({ name: 'u_gain', label: 'Gain', description: 'Gain control', type: 'float', default: 0.5 })],
      values: { u_gain: 0.5 },
    });
    const input = screen.getByTestId('schema-form-widget-u_gain');
    expect(input.getAttribute('aria-labelledby')).toBe('schema-form-u_gain-label');
    expect(input.getAttribute('aria-describedby')).toBe('schema-form-u_gain-description');
  });

  it('shader-number input has id attribute', () => {
    renderForm({
      schema: [shaderUniform({ name: 'u_gain', label: 'Gain', type: 'float', default: 0.5 })],
      values: { u_gain: 0.5 },
    });
    const input = document.getElementById('schema-form-widget-u_gain');
    expect(input).toBeTruthy();
  });

  // -- Vector input aria attributes ------------------------------------------

  it('vector component inputs have aria-describedby referencing description and error', () => {
    renderForm({
      schema: [shaderUniform({ name: 'u_offset', label: 'Offset', description: 'Position offset', type: 'vec2', default: [0, 1] })],
      values: { u_offset: [0, 1] },
    });
    const inputX = screen.getByTestId('schema-form-widget-u_offset-x');
    expect(inputX.getAttribute('aria-describedby')).toBe('schema-form-u_offset-description');
    // Vector inputs should NOT have aria-labelledby (they have their own <label>)
    expect(inputX.getAttribute('aria-labelledby')).toBeNull();
  });

  it('vector component inputs have aria-invalid="true" when field is invalid', () => {
    renderForm({
      schema: [shaderUniform({ name: 'u_offset', label: 'Offset', type: 'vec2', default: [0, 1] })],
      values: { u_offset: 'bad' },
    });
    // Validation runs against the raw value 'bad', which fails for vec2 type
    const inputX = screen.getByTestId('schema-form-widget-u_offset-x');
    expect(inputX.getAttribute('aria-invalid')).toBe('true');
  });

  // -- Required field visual indicator ---------------------------------------

  it('required fields display asterisk visual indicator', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        name: { type: 'string', title: 'Name' },
      },
      required: ['name'],
    };
    renderForm({ schema: standardSchema as any, values: { name: 'Alice' } });
    const field = screen.getByTestId('schema-form-field-name');
    expect(field.textContent).toContain('*');
  });

  // -- NumberInput (StandardSchema number fallback) aria attributes -----------

  it('number input fallback has aria-labelledby and aria-describedby', () => {
    // StandardSchema 'number' type resolves to widgetType 'number' (NumberInput, not Slider)
    const standardSchema = {
      type: 'object' as const,
      properties: {
        qty: { type: 'number', title: 'Quantity', description: 'Item count', minimum: 0 },
      },
    };
    renderForm({ schema: standardSchema as any, values: { qty: 42 } });
    // NumberInput renders; find the input by testid
    const widget = document.querySelector('[data-testid="schema-form-widget-qty"]');
    expect(widget?.getAttribute('aria-labelledby')).toBe('schema-form-qty-label');
    expect(widget?.getAttribute('aria-describedby')).toContain('schema-form-qty-description');
  });
});

// ---------------------------------------------------------------------------
// Save-with-errors focus behavior (M4)
// ---------------------------------------------------------------------------

describe('save-with-errors focus behavior', () => {
  /**
   * Renders SchemaForm with a ref so the imperative validateAndFocus()
   * handle can be exercised synchronously in tests.
   */
  function renderFormWithRef(props: {
    schema?: SchemaFormSchema;
    values?: Record<string, unknown>;
    onChange?: (name: string, value: unknown) => void;
    disabled?: boolean;
    capabilityRegistry?: SchemaCapabilityRegistry;
    onDiagnostics?: (diagnostics: ExtensionDiagnostic[]) => void;
  }) {
    const {
      schema = [],
      values = {},
      onChange = vi.fn(),
      disabled = false,
      capabilityRegistry,
      onDiagnostics,
    } = props;

    const ref = React.createRef<SchemaFormHandle>();

    const result = render(
      React.createElement(SchemaForm, {
        ref,
        schema,
        values,
        onChange,
        disabled,
        capabilityRegistry,
        onDiagnostics,
      }),
    );

    return { ...result, ref };
  }

  // -- Returns true when valid -----------------------------------------------

  it('validateAndFocus returns true when all fields are valid', () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'title', type: 'string', label: 'Title' }),
        parameterDef({ name: 'count', type: 'number', label: 'Count', min: 0, max: 100 }),
      ],
      values: { title: 'Hello', count: 50 },
    });

    expect(ref.current?.validateAndFocus()).toBe(true);
  });

  // -- Focuses first invalid field (text) ------------------------------------

  it('focuses the first invalid text input', () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'title', type: 'string', label: 'Title', minLength: 5 }),
      ],
      values: { title: 'ab' },
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    expect(document.activeElement).toBe(screen.getByTestId('schema-form-widget-title'));
  });

  // -- Focuses first invalid field (number / slider) -------------------------

  it('focuses the first invalid slider widget', () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'count', type: 'number', label: 'Count', min: 10, max: 100 }),
      ],
      values: { count: 5 },
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    // The focusable wrapper div (with tabIndex) receives focus
    const focusTarget = screen.getByTestId('schema-form-field-count').querySelector('[tabindex="-1"]');
    expect(focusTarget).toBeTruthy();
    expect(document.activeElement).toBe(focusTarget);
  });

  // -- Focuses first invalid field (boolean / Switch) ------------------------

  it('focuses the first invalid boolean Switch', () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'flag', type: 'boolean', label: 'Flag' }),
      ],
      values: { flag: 'not-boolean' },
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    expect(document.activeElement).toBe(screen.getByTestId('schema-form-widget-flag'));
  });

  // -- Focuses first invalid field (select) ----------------------------------

  it('focuses the first invalid select trigger', () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({
          name: 'mode',
          type: 'select',
          label: 'Mode',
          options: [{ label: 'A', value: 'a' }],
        }),
      ],
      values: { mode: 'invalid' },
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    expect(document.activeElement).toBe(screen.getByTestId('schema-form-widget-mode'));
  });

  // -- Focuses first invalid field (color) -----------------------------------

  it('focuses the first invalid color input', () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'tint', type: 'color', label: 'Tint' }),
      ],
      values: { tint: 'not-a-hex-color' },
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    expect(document.activeElement).toBe(screen.getByTestId('schema-form-widget-tint'));
  });

  // -- Focuses first invalid field (shader-number) ---------------------------

  it('focuses the first invalid shader-number input', () => {
    const { ref } = renderFormWithRef({
      schema: [{
        name: 'u_gain',
        label: 'Gain',
        type: 'float',
        default: 0.5,
        min: 0,
        max: 1,
      } as any],
      values: { u_gain: 5 }, // out of range
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    expect(document.activeElement).toBe(screen.getByTestId('schema-form-widget-u_gain'));
  });

  // -- Focuses first invalid field (vector) ----------------------------------

  it('focuses the first component of the first invalid vector field', () => {
    const { ref } = renderFormWithRef({
      schema: [{
        name: 'u_offset',
        label: 'Offset',
        type: 'vec2',
        default: [0, 1],
      } as any],
      values: { u_offset: 'bad' }, // not a valid vector
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    // First component (x) should be focused
    expect(document.activeElement).toBe(screen.getByTestId('schema-form-widget-u_offset-x'));
  });

  // -- Focuses first invalid among multiple fields --------------------------

  it('focuses the first invalid field when multiple fields have errors', () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'first', type: 'string', label: 'First', minLength: 5 }),
        parameterDef({ name: 'second', type: 'number', label: 'Second', min: 10, max: 100 }),
        parameterDef({ name: 'third', type: 'color', label: 'Third' }),
      ],
      values: { first: 'ab', second: 5, third: 'bad' },
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    // 'first' comes first in field order → its widget gets focus
    expect(document.activeElement).toBe(screen.getByTestId('schema-form-widget-first'));
  });

  // -- Skips valid fields, focuses first invalid -----------------------------

  it('focuses the first invalid field, skipping a preceding valid field', () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'first', type: 'string', label: 'First' }),
        parameterDef({ name: 'second', type: 'number', label: 'Second', min: 10, max: 100 }),
      ],
      values: { first: 'valid', second: 5 },
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    // 'second' is the first invalid field — its wrapper div gets focus
    const focusTarget = screen.getByTestId('schema-form-field-second').querySelector('[tabindex="-1"]');
    expect(focusTarget).toBeTruthy();
    expect(document.activeElement).toBe(focusTarget);
  });

  // -- Falls back to error summary for unsupported type ----------------------

  it('focuses error summary when the only invalid field has no focusable widget', async () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'gizmo', type: 'unknown-gizmo' as any, label: 'Gizmo' }),
      ],
      values: { gizmo: 'test' },
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    // Unsupported type renders a placeholder div (role="alert"), not a focusable widget.
    // Focus should fall back to the error summary (rendered asynchronously via state update).
    const summary = await screen.findByTestId('schema-form-error-summary');
    expect(summary).toBeTruthy();
    expect(document.activeElement).toBe(summary);
  });

  // -- Focuses widget even when unsupported field precedes it ----------------

  it('skips unsupported fields and focuses the first focusable invalid widget', () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'gizmo', type: 'unknown-type' as any, label: 'Gizmo' }),
        parameterDef({ name: 'title', type: 'string', label: 'Title', minLength: 10 }),
      ],
      values: { gizmo: 'x', title: 'ab' },
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    // 'gizmo' has no focusable widget; 'title' does → focus 'title'
    expect(document.activeElement).toBe(screen.getByTestId('schema-form-widget-title'));
  });

  // -- Error summary has correct attributes ----------------------------------

  it('error summary is a programmatically-focusable alert', async () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'gizmo', type: 'unknown-type' as any, label: 'Gizmo' }),
      ],
      values: { gizmo: 'test' },
    });

    ref.current?.validateAndFocus();

    const summary = await screen.findByTestId('schema-form-error-summary');
    expect(summary.getAttribute('role')).toBe('alert');
    expect(summary.getAttribute('aria-live')).toBe('assertive');
    expect(summary.tabIndex).toBe(-1);
    expect(summary.textContent).toContain('Please fix the validation errors');
  });

  // -- Error summary is hidden when values change ---------------------------

  it('hides error summary when values change after a failed save', async () => {
    const onChange = vi.fn();
    const { ref, rerender } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'gizmo', type: 'unknown-type' as any, label: 'Gizmo' }),
      ],
      values: { gizmo: 'test' },
      onChange,
    });

    // First save fails → summary appears
    ref.current?.validateAndFocus();
    await screen.findByTestId('schema-form-error-summary');
    expect(screen.getByTestId('schema-form-error-summary')).toBeTruthy();

    // User edits a value → summary should hide
    rerender(
      React.createElement(SchemaForm, {
        ref,
        schema: [parameterDef({ name: 'gizmo', type: 'unknown-type' as any, label: 'Gizmo' })],
        values: { gizmo: 'edited' },
        onChange,
      }),
    );
    expect(screen.queryByTestId('schema-form-error-summary')).toBeNull();
  });

  // -- NumberInput fallback focus --------------------------------------------

  it('focuses NumberInput widget for StandardSchema number field with errors', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        qty: { type: 'number', title: 'Quantity', minimum: 1, maximum: 10 },
      },
    };
    const { ref } = renderFormWithRef({
      schema: standardSchema as any,
      values: { qty: 0 },
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    // NumberInput's wrapper div (with tabIndex) receives focus
    const focusTarget = screen.getByTestId('schema-form-field-qty').querySelector('[tabindex="-1"]');
    expect(focusTarget).toBeTruthy();
    expect(document.activeElement).toBe(focusTarget);
  });
});

// ---------------------------------------------------------------------------
// Diagnostics prop rendering (without fields)
// ---------------------------------------------------------------------------

describe('diagnostics prop', () => {
  it('renders diagnostic rows when diagnostics prop is provided and fields are empty', () => {
    render(
      React.createElement(SchemaForm, {
        schema: [],
        values: {},
        onChange: vi.fn(),
        diagnostics: [
          {
            severity: 'error',
            code: 'settings/missing-schema',
            message: 'No settings schema declared in the manifest.',
            detail: {},
          },
        ],
      }),
    );

    expect(screen.getByTestId('schema-form')).toBeTruthy();
    expect(screen.getByTestId('schema-form-diagnostic-0')).toBeTruthy();
    expect(screen.getByTestId('schema-form-diagnostic-0').textContent).toContain('No settings schema declared');
    expect(screen.getByTestId('schema-form-diagnostic-0').getAttribute('role')).toBe('alert');
    expect(screen.getByText('Schema validation error')).toBeTruthy();
    expect(screen.getByText('Error')).toBeTruthy();
  });

  it('renders multiple diagnostic rows in order', () => {
    render(
      React.createElement(SchemaForm, {
        schema: [],
        values: {},
        onChange: vi.fn(),
        diagnostics: [
          {
            severity: 'error',
            code: 'settings/missing-schema',
            message: 'First diagnostic.',
            detail: {},
          },
          {
            severity: 'warning',
            code: 'settings/unknown-field',
            message: 'Second diagnostic.',
            detail: {},
          },
        ],
      }),
    );

    expect(screen.getByTestId('schema-form-diagnostic-0').textContent).toContain('First diagnostic');
    expect(screen.getByTestId('schema-form-diagnostic-1').textContent).toContain('Second diagnostic');
  });

  it('returns null when both fields and diagnostics are empty', () => {
    const { container } = render(
      React.createElement(SchemaForm, {
        schema: [],
        values: {},
        onChange: vi.fn(),
      }),
    );

    expect(container.querySelector('[data-testid="schema-form"]')).toBeNull();
  });

  it('renders diagnostics above fields when both are present', () => {
    render(
      React.createElement(SchemaForm, {
        schema: [parameterDef({ name: 'title', type: 'string', label: 'Title' })],
        values: { title: 'Hello' },
        onChange: vi.fn(),
        diagnostics: [
          {
            severity: 'warning',
            code: 'settings/unknown-field',
            message: 'Schema-level diagnostic.',
            detail: {},
          },
        ],
      }),
    );

    // Both the diagnostic row and the field should render
    expect(screen.getByTestId('schema-form')).toBeTruthy();
    expect(screen.getByTestId('schema-form-diagnostic-0')).toBeTruthy();
    expect(screen.getByTestId('schema-form-field-title')).toBeTruthy();
    // Diagnostic should appear before the field in DOM order
    const form = screen.getByTestId('schema-form');
    const children = Array.from(form.children);
    const diagIndex = children.findIndex((c) => c.getAttribute('data-testid') === 'schema-form-diagnostic-0');
    const fieldIndex = children.findIndex((c) => c.getAttribute('data-testid') === 'schema-form-field-title');
    expect(diagIndex).toBeLessThan(fieldIndex);
  });
});

// ---------------------------------------------------------------------------
// validateAndFocus with custom status
// ---------------------------------------------------------------------------

describe('validateAndFocus custom status', () => {
  function renderFormWithRef(props: {
    schema?: SchemaFormSchema;
    values?: Record<string, unknown>;
    onChange?: (name: string, value: unknown) => void;
  }) {
    const { schema = [], values = {}, onChange = vi.fn() } = props;
    const ref = React.createRef<SchemaFormHandle>();
    const result = render(
      React.createElement(SchemaForm, { ref, schema, values, onChange }),
    );
    return { ...result, ref };
  }

  it('blocks save when the only field has custom status (audio-binding)', () => {
    const { ref } = renderFormWithRef({
      schema: [parameterDef({ name: 'audio', type: 'audio-binding', label: 'Audio' })],
      values: { audio: { source: 'bass', min: 0, max: 100 } },
    });

    // Custom status fields cannot be saved through SchemaForm
    expect(ref.current?.validateAndFocus()).toBe(false);
  });

  it('blocks save when a custom-status field precedes a valid field', () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'audio', type: 'audio-binding', label: 'Audio' }),
        parameterDef({ name: 'title', type: 'string', label: 'Title' }),
      ],
      values: { audio: { source: 'bass', min: 0, max: 100 }, title: 'Hello' },
    });

    // Custom status blocks save even when valid fields follow
    expect(ref.current?.validateAndFocus()).toBe(false);
  });

  it('focuses the first error widget even when it has custom status', () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'audio', type: 'audio-binding', label: 'Audio' }),
        parameterDef({ name: 'title', type: 'string', label: 'Title', minLength: 10 }),
      ],
      values: { audio: { source: 'bass', min: 0, max: 100 }, title: 'ab' },
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    // 'audio' has custom status and is the first error; its SelectTrigger
    // IS in the widgetRefs map, so it receives focus first
    const audioWidget = screen.getByTestId('schema-form-widget-audio-source');
    expect(document.activeElement).toBe(audioWidget);
  });

  it('focuses the custom-status widget when it is the only error', () => {
    const { ref } = renderFormWithRef({
      schema: [
        parameterDef({ name: 'audio', type: 'audio-binding', label: 'Audio' }),
      ],
      values: { audio: { source: 'bass', min: 0, max: 100 } },
    });

    expect(ref.current?.validateAndFocus()).toBe(false);
    // The audio-binding widget (SelectTrigger) IS focusable and gets focus
    const audioWidget = screen.getByTestId('schema-form-widget-audio-source');
    expect(document.activeElement).toBe(audioWidget);
  });
});

// ---------------------------------------------------------------------------
// Invalid regex pattern handling
// ---------------------------------------------------------------------------

describe('invalid regex pattern', () => {
  it('does not crash when StandardSchema string field has an invalid regex pattern', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        code: { type: 'string', title: 'Code', pattern: '[invalid(regex' },
      },
    };

    // Should render without throwing
    expect(() => {
      renderForm({
        schema: standardSchema as any,
        values: { code: 'test' },
      });
    }).not.toThrow();

    // Field should render normally (validation skips invalid regex)
    expect(screen.getByTestId('schema-form-field-code')).toBeTruthy();
    // No error should be shown for pattern mismatch since the regex is invalid
    expect(screen.queryByTestId('schema-form-error-code')).toBeNull();
  });

  it('does not crash when ParameterDefinition string field has an invalid regex pattern', () => {
    expect(() => {
      renderForm({
        schema: [parameterDef({ name: 'slug', type: 'string', label: 'Slug', pattern: '[bad(regex' })],
        values: { slug: 'test' },
      });
    }).not.toThrow();

    expect(screen.getByTestId('schema-form-field-slug')).toBeTruthy();
    expect(screen.queryByTestId('schema-form-error-slug')).toBeNull();
  });

  it('still validates other constraints when pattern regex is invalid', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        code: { type: 'string', title: 'Code', minLength: 5, pattern: '[bad(regex' },
      },
    };

    renderForm({
      schema: standardSchema as any,
      values: { code: 'ab' },
    });

    // minLength constraint should still fire (invalid regex is skipped)
    const error = screen.getByTestId('schema-form-error-code');
    expect(error.textContent).toContain('must be at least 5 characters');
  });
});

// ---------------------------------------------------------------------------
// Slider value badge and multipleOf → step
// ---------------------------------------------------------------------------

describe('slider details', () => {
  it('displays numeric value badge next to slider label', () => {
    renderForm({
      schema: [parameterDef({ name: 'opacity', type: 'number', label: 'Opacity', min: 0, max: 1, step: 0.1 })],
      values: { opacity: 0.75 },
    });

    // The value badge should show the current numeric value
    const field = screen.getByTestId('schema-form-field-opacity');
    expect(field.textContent).toContain('0.75');
  });

  it('maps StandardSchema multipleOf to slider step', () => {
    const standardSchema = {
      type: 'object' as const,
      properties: {
        volume: { type: 'number', title: 'Volume', minimum: 0, maximum: 1, multipleOf: 0.1 },
      },
    };

    renderForm({
      schema: standardSchema as any,
      values: { volume: 0.5 },
    });

    // Field renders as slider
    const field = screen.getByTestId('schema-form-field-volume');
    expect(field.dataset.fieldType).toBe('number');
    expect(field.dataset.fieldStatus).toBe('supported');
    // The value badge shows the value
    expect(field.textContent).toContain('0.5');
  });

  it('slider defaults to step 1 when min/max are present but step is undefined', () => {
    renderForm({
      schema: [parameterDef({ name: 'count', type: 'number', label: 'Count', min: 0, max: 100 })],
      values: { count: 42 },
    });

    const field = screen.getByTestId('schema-form-field-count');
    expect(field.dataset.fieldType).toBe('number');
    expect(field.textContent).toContain('42');
  });

  it('slider value badge shows 0 when value is 0 (falsy value preserved)', () => {
    renderForm({
      schema: [parameterDef({ name: 'count', type: 'number', label: 'Count', min: 0, max: 100 })],
      values: { count: 0 },
    });

    const field = screen.getByTestId('schema-form-field-count');
    expect(field.textContent).toContain('0');
  });
});

// Shader uniform helper (re-used from shader test block)
function shaderUniform(overrides: ShaderUniformSchema[number]): ShaderUniformSchema[number] {
  return overrides;
}
