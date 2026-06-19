/**
 * Schema capability registry.
 *
 * Maps parameter schema types to host rendering capabilities so that
 * SchemaForm can decide which widget to render, whether to show a
 * diagnostic placeholder, and which validation paths to apply.
 *
 * - Supported types (string, number, boolean, select, color) map to
 *   native host widgets.
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
  | 'color';     // <input type="color"> — hex color picker

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

function unsupportedDiagnostic(type: string): ExtensionDiagnostic {
  return Object.freeze({
    severity: UNSUPPORTED_SEVERITY,
    code: 'schema/unsupported-type',
    message: `Schema type "${type}" is not supported by the host. `
      + 'The parameter will render as a diagnostic placeholder.',
    detail: { unsupportedType: type },
  });
}

const BUILTIN_CAPABILITIES: ReadonlyMap<ParameterType, SchemaCapabilityEntry> = new Map([
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
    // Boolean: must be boolean-ish
    ['boolean-path', {
      path: 'boolean-path',
      validate(value: unknown, def: ParameterDefinition): string | null {
        if (def.type !== 'boolean') return null;
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
        if (def.type !== 'select') return null;
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
        if (def.type !== 'color') return null;
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
    const d = unsupportedDiagnostic(type);
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
      if (entry) return entry;

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
      if (entry) return entry.diagnostic;
      return makeDiagnostic(type);
    },

    registerCustom(type: string, entry: SchemaCapabilityEntry): void {
      if (BUILTIN_CAPABILITIES.has(type as ParameterType)) {
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
