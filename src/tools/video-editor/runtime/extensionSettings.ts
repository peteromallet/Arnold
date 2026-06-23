/**
 * Manifest settings-schema adapter (M4, Step 7).
 *
 * Converts an extension manifest's `settingsSchema` into a SchemaForm-compatible
 * `StandardSchema` (or emits diagnostics when the manifest schema is malformed).
 * The adapter handles:
 *
 *  - Top-level shape validation (`type: 'object'`, non-empty `properties`)
 *  - JSON Schema keyword mapping to {@link StandardSchemaProperty} fields
 *  - Diagnostic emission for missing / malformed settings schemas
 *  - Integration with the existing `SchemaForm` component's input contract
 *
 * This module is purely a data adapter; it does **not** manage persistence,
 * overrides, or the Ajv-backed atomic save (that lives in
 * `extensionSettingsService.ts`).
 */

import type { StandardSchema, StandardSchemaProperty } from '@/tools/video-editor/components/SchemaForm/SchemaForm';
import type { ExtensionManifest, ExtensionSettingsSchema } from '@reigh/editor-sdk';
import type { ExtensionDiagnostic } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Result type
// ---------------------------------------------------------------------------

/** Result of adapting a manifest settings schema for SchemaForm consumption. */
export interface AdaptedSettingsSchema {
  /**
   * The SchemaForm-compatible schema, or `null` when the manifest schema
   * could not be adapted (e.g. missing, malformed, or non-object).
   */
  readonly schema: StandardSchema | null;
  /**
   * Diagnostics emitted during adaptation.  Consumer should surface these
   * through the active diagnostic collection so extension authors see
   * problems with their declared settings schema.
   */
  readonly diagnostics: readonly ExtensionDiagnostic[];
}

// ---------------------------------------------------------------------------
// Diagnostic helpers
// ---------------------------------------------------------------------------

function makeDiagnostic(
  code: string,
  message: string,
  extensionId: string,
  severity: ExtensionDiagnostic['severity'] = 'warning',
): ExtensionDiagnostic {
  return {
    severity,
    code,
    message,
    extensionId,
    detail: { source: 'settings-schema-adapter' },
  };
}

// ---------------------------------------------------------------------------
// JSON Schema type → SchemaForm widget type mapping
// ---------------------------------------------------------------------------

/**
 * Map well-known JSON Schema `type` values to SchemaForm widget types.
 * Types not in this map pass through unchanged (SchemaForm's
 * `normalizeSchema` resolves them via the capability registry).
 *
 * The mapping is intentionally minimal — most SchemaForm widget types
 * (shader-specific vec2/vec3/vec4/bool/float/int/enum etc.) are not
 * expected in extension settings schemas, which use plain JSON Schema
 * types.  Types like `integer` are folded into `number` because
 * SchemaForm's V1 number path handles both.
 */
const JSON_SCHEMA_TYPE_MAP: ReadonlyMap<string, string> = new Map([
  ['integer', 'number'],
]);

function mapJsonSchemaType(rawType: string): string {
  return JSON_SCHEMA_TYPE_MAP.get(rawType) ?? rawType;
}

// ---------------------------------------------------------------------------
// Property adaptation
// ---------------------------------------------------------------------------

/**
 * Convert a single JSON Schema property descriptor into a
 * {@link StandardSchemaProperty} suitable for SchemaForm rendering.
 *
 * The adapter preserves all standard JSON Schema keywords that the
 * current {@link StandardSchemaProperty} interface accepts.
 */
function adaptProperty(raw: Record<string, unknown>): StandardSchemaProperty {
  return {
    type: typeof raw.type === 'string' ? mapJsonSchemaType(raw.type) : undefined,
    title: typeof raw.title === 'string' ? raw.title : undefined,
    description: typeof raw.description === 'string' ? raw.description : undefined,
    default: 'default' in raw ? raw.default : undefined,
    enum: Array.isArray(raw.enum) ? raw.enum : undefined,
    minimum: typeof raw.minimum === 'number' ? raw.minimum : undefined,
    maximum: typeof raw.maximum === 'number' ? raw.maximum : undefined,
    multipleOf: typeof raw.multipleOf === 'number' ? raw.multipleOf : undefined,
    minLength: typeof raw.minLength === 'number' ? raw.minLength : undefined,
    maxLength: typeof raw.maxLength === 'number' ? raw.maxLength : undefined,
    pattern: typeof raw.pattern === 'string' ? raw.pattern : undefined,
    // Unsupported shapes are detected downstream by SchemaForm's
    // normalizeSchema / detectUnsupportedShape; we pass through only
    // flat primitive keywords here.
  };
}

// ---------------------------------------------------------------------------
// Top-level adaptation
// ---------------------------------------------------------------------------

/**
 * Adapt the settings schema declared in an extension manifest into the
 * {@link StandardSchema} shape expected by SchemaForm.
 *
 * @returns An {@link AdaptedSettingsSchema} with either a valid schema
 *          or `null` when the manifest schema is missing or malformed,
 *          plus diagnostics for each observable problem.
 */
export function adaptManifestSettingsSchema(
  manifest: ExtensionManifest,
): AdaptedSettingsSchema {
  const diagnostics: ExtensionDiagnostic[] = [];
  const extensionId = manifest.id as string;

  // 1. No settingsSchema declared
  if (!manifest.settingsSchema) {
    diagnostics.push(
      makeDiagnostic(
        'settings/missing-schema',
        `Extension "${extensionId}" does not declare a settingsSchema; settings UI will be unavailable.`,
        extensionId,
        'warning',
      ),
    );
    return { schema: null, diagnostics };
  }

  const raw = manifest.settingsSchema.schema;

  // 2. settingsSchema is present but schema descriptor is missing
  if (!raw || typeof raw !== 'object') {
    diagnostics.push(
      makeDiagnostic(
        'settings/missing-schema-descriptor',
        `Extension "${extensionId}" declares settingsSchema but its "schema" property is missing or not an object.`,
        extensionId,
        'error',
      ),
    );
    return { schema: null, diagnostics };
  }

  const schemaObj = raw as Record<string, unknown>;

  // 3. Validate top-level type
  if (schemaObj.type !== 'object') {
    diagnostics.push(
      makeDiagnostic(
        'settings/non-object-schema',
        `Extension "${extensionId}" settingsSchema.schema.type must be "object", got "${String(schemaObj.type)}".`,
        extensionId,
        'error',
      ),
    );
    return { schema: null, diagnostics };
  }

  // 4. Validate properties
  const rawProperties = schemaObj.properties;
  if (!rawProperties || typeof rawProperties !== 'object' || Array.isArray(rawProperties)) {
    diagnostics.push(
      makeDiagnostic(
        'settings/empty-properties',
        `Extension "${extensionId}" settingsSchema.schema.properties is missing, empty, or not an object.`,
        extensionId,
        'warning',
      ),
    );
    return { schema: null, diagnostics };
  }

  const props = rawProperties as Record<string, unknown>;
  const propKeys = Object.keys(props);

  if (propKeys.length === 0) {
    diagnostics.push(
      makeDiagnostic(
        'settings/empty-properties',
        `Extension "${extensionId}" settingsSchema.schema.properties is empty; no settings fields to render.`,
        extensionId,
        'warning',
      ),
    );
    return { schema: null, diagnostics };
  }

  // 5. Adapt each property
  const adaptedProperties: Record<string, StandardSchemaProperty> = {};
  for (const key of propKeys) {
    const rawProp = props[key];
    if (rawProp && typeof rawProp === 'object' && !Array.isArray(rawProp)) {
      adaptedProperties[key] = adaptProperty(rawProp as Record<string, unknown>);
    } else {
      // Non-object property value — skip and emit diagnostic
      diagnostics.push(
        makeDiagnostic(
          'settings/invalid-property',
          `Property "${key}" in extension "${extensionId}" settings schema is not a valid JSON Schema property definition; skipping.`,
          extensionId,
          'warning',
        ),
      );
    }
  }

  if (Object.keys(adaptedProperties).length === 0) {
    diagnostics.push(
      makeDiagnostic(
        'settings/no-valid-properties',
        `Extension "${extensionId}" settings schema has no valid property definitions after adaptation.`,
        extensionId,
        'error',
      ),
    );
    return { schema: null, diagnostics };
  }

  // 6. Extract required array
  const rawRequired = schemaObj.required;
  let required: string[] | undefined;
  if (Array.isArray(rawRequired)) {
    required = rawRequired.filter(
      (item): item is string => typeof item === 'string' && item in adaptedProperties,
    );
  }

  const schema: StandardSchema = {
    type: 'object',
    properties: adaptedProperties,
    ...(required && required.length > 0 ? { required } : {}),
  };

  return { schema, diagnostics };
}
