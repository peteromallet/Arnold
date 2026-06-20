/**
 * Schema capability registry.
 *
 * Maps parameter schema types to host rendering capabilities so that
 * SchemaForm can decide which widget to render, whether to show a
 * diagnostic placeholder, and which validation paths to apply.
 *
 * - Supported types (string, number, boolean, select, color) map to
 *   native host widgets.
 * - Shader uniform types map to compact shader controls where they do
 *   not overlap legacy parameter widgets.
 * - Custom types (audio-binding) map to host-approved placeholder
 *   widgets during migration — they render real controls but are
 *   tracked as custom so future StandardSchema alignment is visible.
 * - Unsupported types emit structured diagnostics and render a
 *   diagnostic placeholder instead of disappearing or crashing.
 *
 * @module schemaCapabilityRegistry
 */

import type { ParameterDefinition, ParameterType } from '@/tools/video-editor/types';
import type { DiagnosticSeverity, ExtensionDiagnostic } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Widget type taxonomy
// ---------------------------------------------------------------------------

/**
 * Widget categories the host shell knows how to render natively.
 * Each maps to a concrete React component inside SchemaForm.
 */
export type SchemaWidgetType =
  | 'text'       // <input type="text"> / textarea
  | 'number'     // <NumberInput> — integer or float
  | 'slider'     // <Slider> — ranged number with min/max/step
  | 'boolean'    // <Switch> — toggle
  | 'select'     // <Select> — enumerated dropdown
  | 'color'      // <input type="color"> — hex color picker
  | 'vector'     // Compact numeric vector inputs
  | 'shader-number'; // Compact numeric shader uniform input

// ---------------------------------------------------------------------------
// Capability status
// ---------------------------------------------------------------------------

/** Resolution status for a schema parameter type. */
export type SchemaCapabilityStatus =
  | 'supported'     // Host has a native widget
  | 'custom'        // Host-approved custom/placeholder widget
  | 'unsupported';  // No widget — diagnostic placeholder fallback

// ---------------------------------------------------------------------------
// Capability entry
// ---------------------------------------------------------------------------

/** A single capability entry describing how to render and validate a parameter type. */
export interface SchemaCapabilityEntry {
  /** The parameter type this entry describes. */
  readonly type: string;
  /** Host widget category, if any (undefined for unsupported). */
  readonly widgetType?: SchemaWidgetType;
  /** Resolution status. */
  readonly status: SchemaCapabilityStatus;
  /** Human-readable label for diagnostics / accessibility. */
  readonly label: string;
  /** Diagnostic emitted when this type is unsupported (null for supported/custom). */
  readonly diagnostic: Readonly<ExtensionDiagnostic> | null;
  /** True if this is a host-approved custom/migration widget placeholder. */
  readonly isCustomPlaceholder: boolean;
}

// ---------------------------------------------------------------------------
// Validation path mapping
// ---------------------------------------------------------------------------

/**
 * Associates a parameter name (exact) or path glob with a validation
 * function.  SchemaForm evaluates validation paths in registration
 * order and stops at the first matching entry.
 */
export interface ValidationPathEntry {
  /** Exact parameter name or a simple glob like `param.*`. */
  readonly path: string;
  /**
   * Validate a parameter value against its definition.
   * Returns `null` if valid, or a human-readable error message.
   */
  readonly validate: (value: unknown, definition: ParameterDefinition) => string | null;
}

// ---------------------------------------------------------------------------
// Registry interface
// ---------------------------------------------------------------------------

export interface SchemaCapabilityRegistry {
  /** Resolve a schema type to its capability entry (never null). */
  resolve(type: string): SchemaCapabilityEntry;

  /** All registered entries (frozen snapshot). */
  readonly entries: ReadonlyMap<string, SchemaCapabilityEntry>;

  /** All registered validation paths (frozen snapshot). */
  readonly validationPaths: ReadonlyMap<string, ValidationPathEntry>;

  /** True if the type has a native host widget. */
  isSupported(type: string): boolean;

  /** True if the type has a host-approved custom placeholder widget. */
  isCustom(type: string): boolean;

  /** Get the diagnostic for a type, or null if supported. */
  getDiagnostic(type: string): ExtensionDiagnostic | null;

  /**
   * Register a custom widget placeholder for a migration type
   * (e.g. audio-binding).  Must not collide with a built-in type.
   */
  registerCustom(type: string, entry: SchemaCapabilityEntry): void;

  /**
   * Register a validation path.  Evaluated in registration order;
   * the first matching path wins.
   */
  registerValidation(path: string, entry: ValidationPathEntry): void;
}

// ---------------------------------------------------------------------------
// Built-in capability map
// ---------------------------------------------------------------------------

/** Severity used for unsupported-type diagnostics. */
const UNSUPPORTED_SEVERITY: DiagnosticSeverity = 'warning';

function unsupportedDiagnostic(type: string, message?: string, detail?: Record<string, unknown>): ExtensionDiagnostic {
  return Object.freeze({
    severity: UNSUPPORTED_SEVERITY,
    code: 'schema/unsupported-type',
    message: message ?? (`Schema type "${type}" is not supported by the host. `
      + 'The parameter will render as a diagnostic placeholder.'),
    detail: detail ?? { unsupportedType: type },
  });
}

function unsupportedTextureRefDiagnostic(): ExtensionDiagnostic {
  return Object.freeze({
    severity: UNSUPPORTED_SEVERITY,
    code: 'schema/texture-ref-unsupported',
    message: 'Shader textureRef uniforms are not editable in SchemaForm yet. '
      + 'Bind textures through the host shader texture picker.',
    detail: { unsupportedType: 'textureRef' },
  });
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isFiniteNumberVector(value: unknown, length: number): value is readonly number[] {
  return Array.isArray(value) && value.length === length && value.every(isFiniteNumber);
}

const BUILTIN_TYPE_KEYS = new Set<string>([
  'string',
  'number',
  'boolean',
  'select',
  'color',
  'audio-binding',
  'float',
  'int',
  'bool',
  'vec2',
  'vec3',
  'vec4',
  'enum',
  'textureRef',
  'frame',
  'time',
]);

const BUILTIN_CAPABILITIES: ReadonlyMap<string, SchemaCapabilityEntry> = new Map([
  ['string' as ParameterType, Object.freeze<SchemaCapabilityEntry>({
    type: 'string',
    widgetType: 'text',
    status: 'supported',
    label: 'String',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
  ['number' as ParameterType, Object.freeze<SchemaCapabilityEntry>({
    type: 'number',
    widgetType: 'slider',
    status: 'supported',
    label: 'Number',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
  ['boolean' as ParameterType, Object.freeze<SchemaCapabilityEntry>({
    type: 'boolean',
    widgetType: 'boolean',
    status: 'supported',
    label: 'Boolean',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
  ['select' as ParameterType, Object.freeze<SchemaCapabilityEntry>({
    type: 'select',
    widgetType: 'select',
    status: 'supported',
    label: 'Select',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
  ['color' as ParameterType, Object.freeze<SchemaCapabilityEntry>({
    type: 'color',
    widgetType: 'color',
    status: 'supported',
    label: 'Color',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
  // Audio-binding: host-approved custom placeholder during migration
  ['audio-binding' as ParameterType, Object.freeze<SchemaCapabilityEntry>({
    type: 'audio-binding',
    widgetType: undefined, // Custom widget, not a standard SchemaWidgetType
    status: 'custom',
    label: 'Audio Binding',
    diagnostic: null, // No diagnostic — it renders via its custom widget
    isCustomPlaceholder: true,
  })],
  ['float', Object.freeze<SchemaCapabilityEntry>({
    type: 'float',
    widgetType: 'shader-number',
    status: 'supported',
    label: 'Float',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
  ['int', Object.freeze<SchemaCapabilityEntry>({
    type: 'int',
    widgetType: 'shader-number',
    status: 'supported',
    label: 'Integer',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
  ['bool', Object.freeze<SchemaCapabilityEntry>({
    type: 'bool',
    widgetType: 'boolean',
    status: 'supported',
    label: 'Boolean',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
  ['vec2', Object.freeze<SchemaCapabilityEntry>({
    type: 'vec2',
    widgetType: 'vector',
    status: 'supported',
    label: 'Vector 2',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
  ['vec3', Object.freeze<SchemaCapabilityEntry>({
    type: 'vec3',
    widgetType: 'vector',
    status: 'supported',
    label: 'Vector 3',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
  ['vec4', Object.freeze<SchemaCapabilityEntry>({
    type: 'vec4',
    widgetType: 'vector',
    status: 'supported',
    label: 'Vector 4',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
  ['enum', Object.freeze<SchemaCapabilityEntry>({
    type: 'enum',
    widgetType: 'select',
    status: 'supported',
    label: 'Enum',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
  ['textureRef', Object.freeze<SchemaCapabilityEntry>({
    type: 'textureRef',
    widgetType: undefined,
    status: 'unsupported',
    label: 'Texture Reference',
    diagnostic: unsupportedTextureRefDiagnostic(),
    isCustomPlaceholder: false,
  })],
  ['frame', Object.freeze<SchemaCapabilityEntry>({
    type: 'frame',
    widgetType: 'shader-number',
    status: 'supported',
    label: 'Frame',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
  ['time', Object.freeze<SchemaCapabilityEntry>({
    type: 'time',
    widgetType: 'shader-number',
    status: 'supported',
    label: 'Time',
    diagnostic: null,
    isCustomPlaceholder: false,
  })],
]);

// ---------------------------------------------------------------------------
// Built-in validation paths
// ---------------------------------------------------------------------------

function buildValidationPaths(): ReadonlyMap<string, ValidationPathEntry> {
  const entries: Array<[string, ValidationPathEntry]> = [
    // Number: coerce to number, clamp to min/max
    ['*', {
      path: '*',
      validate(value: unknown, def: ParameterDefinition): string | null {
        if (def.type !== 'number') return null; // Only applies to number types
        if (value === undefined || value === null) return null; // Let defaults handle
        const n = Number(value);
        if (Number.isNaN(n)) {
          return `"${def.label}" must be a number.`;
        }
        if (def.min !== undefined && n < def.min) {
          return `"${def.label}" must be at least ${def.min}.`;
        }
        if (def.max !== undefined && n > def.max) {
          return `"${def.label}" must be at most ${def.max}.`;
        }
        return null;
      },
    }],
    // Shader scalar uniforms
    ['shader-scalar-path', {
      path: 'shader-scalar-path',
      validate(value: unknown, def: ParameterDefinition): string | null {
        const type = def.type as string;
        if (type !== 'float' && type !== 'int' && type !== 'frame' && type !== 'time') {
          return null;
        }
        if (value === undefined || value === null) return null;
        if (!isFiniteNumber(value)) {
          return `"${def.label}" must be a finite number.`;
        }
        if (type === 'int' && !Number.isInteger(value)) {
          return `"${def.label}" must be an integer.`;
        }
        if (def.min !== undefined && value < def.min) {
          return `"${def.label}" must be at least ${def.min}.`;
        }
        if (def.max !== undefined && value > def.max) {
          return `"${def.label}" must be at most ${def.max}.`;
        }
        return null;
      },
    }],
    // Shader vector uniforms
    ['shader-vector-path', {
      path: 'shader-vector-path',
      validate(value: unknown, def: ParameterDefinition): string | null {
        const vectorLengthByType: Record<string, number> = {
          vec2: 2,
          vec3: 3,
          vec4: 4,
        };
        const length = vectorLengthByType[def.type as string];
        if (!length) return null;
        if (value === undefined || value === null) return null;
        if (!isFiniteNumberVector(value, length)) {
          return `"${def.label}" must be a ${length}-number vector.`;
        }
        return null;
      },
    }],
    // Shader color uniforms use vec4 RGBA arrays; legacy parameter colors use hex strings.
    ['shader-color-vector-path', {
      path: 'shader-color-vector-path',
      validate(value: unknown, def: ParameterDefinition): string | null {
        if ((def.type as string) !== 'color' || !Array.isArray(value)) return null;
        if (!isFiniteNumberVector(value, 4)) {
          return `"${def.label}" must be a 4-number RGBA vector.`;
        }
        return null;
      },
    }],
    // Boolean: must be boolean-ish
    ['boolean-path', {
      path: 'boolean-path',
      validate(value: unknown, def: ParameterDefinition): string | null {
        if ((def.type as string) !== 'boolean' && (def.type as string) !== 'bool') return null;
        if (value === undefined || value === null) return null;
        if (typeof value !== 'boolean') {
          return `"${def.label}" must be true or false.`;
        }
        return null;
      },
    }],
    // Select: value must be in options
    ['select-path', {
      path: 'select-path',
      validate(value: unknown, def: ParameterDefinition): string | null {
        if ((def.type as string) !== 'select' && (def.type as string) !== 'enum') return null;
        if (value === undefined || value === null) return null;
        if (typeof value !== 'string') {
          return `"${def.label}" must be a string option value.`;
        }
        const validValues = new Set((def.options ?? []).map((o) => o.value));
        if (!validValues.has(value)) {
          return `"${value}" is not a valid option for "${def.label}".`;
        }
        return null;
      },
    }],
    // Color: must be a valid hex color
    ['color-path', {
      path: 'color-path',
      validate(value: unknown, def: ParameterDefinition): string | null {
        if ((def.type as string) !== 'color' || Array.isArray(value)) return null;
        if (value === undefined || value === null) return null;
        if (typeof value !== 'string') {
          return `"${def.label}" must be a hex color string.`;
        }
        if (!/^#[0-9a-fA-F]{3,8}$/.test(value)) {
          return `"${value}" is not a valid hex color.`;
        }
        return null;
      },
    }],
    // Audio-binding: must have source, min, max
    ['audio-binding-path', {
      path: 'audio-binding-path',
      validate(value: unknown, def: ParameterDefinition): string | null {
        if (def.type !== 'audio-binding') return null;
        if (value === undefined || value === null) return null;
        if (typeof value !== 'object' || value === null) {
          return `"${def.label}" must be an audio binding object.`;
        }
        const v = value as Record<string, unknown>;
        const validSources = ['bass', 'mid', 'treble', 'amplitude'];
        if (typeof v.source !== 'string' || !validSources.includes(v.source)) {
          return `"${def.label}" source must be one of: ${validSources.join(', ')}.`;
        }
        if (typeof v.min !== 'number') {
          return `"${def.label}" min must be a number.`;
        }
        if (typeof v.max !== 'number') {
          return `"${def.label}" max must be a number.`;
        }
        if (v.min > v.max) {
          return `"${def.label}" min must be <= max.`;
        }
        return null;
      },
    }],
  ];

  return new Map(entries) as ReadonlyMap<string, ValidationPathEntry>;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

/**
 * Create a schema capability registry.
 *
 * Returns a frozen registry pre-populated with the built-in capability
 * map (string, number, boolean, select, color + audio-binding custom
 * placeholder) and built-in validation paths.
 *
 * Callers may register additional custom types and validation paths
 * before the registry is consumed by SchemaForm.  Once a type or path
 * is registered it cannot be removed (only overridden via another
 * registerCustom / registerValidation call for the same key).
 *
 * @param ownerExtensionId Optional extension ID for diagnostic attribution.
 */
export function createSchemaCapabilityRegistry(
  ownerExtensionId?: string,
): SchemaCapabilityRegistry {
  // Clone the built-in map so callers can mutate their copy
  const entries = new Map<string, SchemaCapabilityEntry>(BUILTIN_CAPABILITIES);
  const validationPaths = new Map<string, ValidationPathEntry>(buildValidationPaths());

  function makeDiagnostic(type: string): ExtensionDiagnostic {
    const d = type === 'textureRef' ? unsupportedTextureRefDiagnostic() : unsupportedDiagnostic(type);
    if (ownerExtensionId) {
      return Object.freeze({ ...d, extensionId: ownerExtensionId });
    }
    return d;
  }

  const UNSUPPORTED_FALLBACK: SchemaCapabilityEntry = {
    type: '',
    widgetType: undefined,
    status: 'unsupported',
    label: 'Unknown',
    diagnostic: null, // Filled per-call
    isCustomPlaceholder: false,
  };

  const registry: SchemaCapabilityRegistry = {
    resolve(type: string): SchemaCapabilityEntry {
      const entry = entries.get(type);
      if (entry) {
        if (entry.status === 'unsupported' && entry.diagnostic) {
          return Object.freeze({
            ...entry,
            diagnostic: makeDiagnostic(type),
          });
        }
        return entry;
      }

      // Return an ephemeral unsupported entry with diagnostic
      return {
        ...UNSUPPORTED_FALLBACK,
        type,
        label: type,
        diagnostic: makeDiagnostic(type),
      };
    },

    get entries(): ReadonlyMap<string, SchemaCapabilityEntry> {
      return entries;
    },

    get validationPaths(): ReadonlyMap<string, ValidationPathEntry> {
      return validationPaths;
    },

    isSupported(type: string): boolean {
      return entries.get(type)?.status === 'supported';
    },

    isCustom(type: string): boolean {
      return entries.get(type)?.isCustomPlaceholder === true;
    },

    getDiagnostic(type: string): ExtensionDiagnostic | null {
      const entry = entries.get(type);
      if (entry) {
        if (entry.status === 'unsupported' && entry.diagnostic) {
          return makeDiagnostic(type);
        }
        return entry.diagnostic;
      }
      return makeDiagnostic(type);
    },

    registerCustom(type: string, entry: SchemaCapabilityEntry): void {
      if (BUILTIN_TYPE_KEYS.has(type)) {
        throw new Error(
          `Cannot register custom type "${type}": it is a built-in type. `
          + 'Built-in types cannot be overridden.',
        );
      }
      entries.set(type, Object.freeze({ ...entry, type }));
    },

    registerValidation(path: string, entry: ValidationPathEntry): void {
      validationPaths.set(path, { ...entry, path });
    },
  };

  return registry;
}
