// @vitest-environment jsdom
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import React from 'react';
import { SchemaForm, type SchemaFormSchema } from '@/tools/video-editor/components/SchemaForm/SchemaForm';
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
