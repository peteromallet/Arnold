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
import type { ExtensionManifest } from '@reigh/editor-sdk';
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

/**
 * Result of fully analysing a manifest settings schema.
 *
 * Extends {@link AdaptedSettingsSchema} with unsupported-field classification
 * and an editable-status flag so Manager/standalone consumers can decide
 * whether to render a read-only blocker or an interactive SchemaForm.
 */
export interface AnalyzedSettingsSchema extends AdaptedSettingsSchema {
  /**
   * Property names that use unsupported JSON Schema constructs
   * (`$ref`, combinators, arrays, nested objects, conditionals).
   * Empty when every adapted property is a flat supported primitive.
   */
  readonly unsupportedFields: readonly string[];
  /**
   * `true` when *every* adapted property is a supported flat primitive.
   * When `false` the settings surface must not offer editable controls
   * for this extension.
   */
  readonly editable: boolean;
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
    // Preserve unsupported-shape markers so SchemaForm's normalizeSchema /
    // detectUnsupportedShape (and analyzeManifestSettingsSchema) can classify
    // them without losing data.
    items: 'items' in raw ? raw.items : undefined,
    properties:
      raw.properties !== undefined && typeof raw.properties === 'object' && !Array.isArray(raw.properties)
        ? (raw.properties as Record<string, unknown>)
        : undefined,
    $ref: typeof raw.$ref === 'string' ? raw.$ref : undefined,
    oneOf: Array.isArray(raw.oneOf) ? raw.oneOf : undefined,
    anyOf: Array.isArray(raw.anyOf) ? raw.anyOf : undefined,
    allOf: Array.isArray(raw.allOf) ? raw.allOf : undefined,
    if: 'if' in raw ? raw.if : undefined,
    then: 'then' in raw ? raw.then : undefined,
    else: 'else' in raw ? raw.else : undefined,
  };
}

// ---------------------------------------------------------------------------
// Unsupported shape detection (shared with SchemaForm)
// ---------------------------------------------------------------------------

/**
 * Inspect a {@link StandardSchemaProperty} for unsupported JSON Schema shapes
 * (arrays, nested objects, `$ref`, `oneOf`, `anyOf`, `allOf`, conditionals).
 *
 * Mirrors the detection in SchemaForm's `detectUnsupportedShape` so that
 * non-React consumers (e.g. Manager reconciliation) can classify properties
 * without pulling in the component tree.
 *
 * @returns The shape key if unsupported, or `null` if the property is a
 * supported flat primitive or unknown type.
 */
export function detectUnsupportedShape(prop: StandardSchemaProperty): string | null {
  // Arrays
  if (prop.type === 'array' || prop.items !== undefined) {
    return 'array';
  }
  // Nested objects (type === 'object' with nested properties)
  if (prop.type === 'object' || (prop.properties !== undefined && typeof prop.properties === 'object')) {
    return 'nested-object';
  }
  // $ref
  if (prop.$ref !== undefined) {
    return '$ref';
  }
  // oneOf
  if (prop.oneOf !== undefined) {
    return 'oneOf';
  }
  // anyOf
  if (prop.anyOf !== undefined) {
    return 'anyOf';
  }
  // allOf
  if (prop.allOf !== undefined) {
    return 'allOf';
  }
  // Conditional schemas (if/then/else)
  if (prop.if !== undefined || prop.then !== undefined || prop.else !== undefined) {
    return 'conditional';
  }
  return null;
}

// ---------------------------------------------------------------------------
// Full analysis (adaptation + shape classification)
// ---------------------------------------------------------------------------

/**
 * Adapt *and* fully analyse the settings schema declared in an extension
 * manifest.
 *
 * In addition to the {@link AdaptedSettingsSchema} output, this function
 * classifies every adapted property as supported or unsupported and sets
 * {@link AnalyzedSettingsSchema.editable} to `false` when *any* property
 * uses a forbidden JSON Schema construct.
 *
 * Consumers that need to gate the editable surface (Manager, standalone
 * settings panel) should prefer this function over the raw
 * `adaptManifestSettingsSchema`.
 */
export function analyzeManifestSettingsSchema(
  manifest: ExtensionManifest,
): AnalyzedSettingsSchema {
  const adapted = adaptManifestSettingsSchema(manifest);

  // No schema → nothing to classify
  if (!adapted.schema) {
    return {
      schema: null,
      diagnostics: adapted.diagnostics,
      unsupportedFields: [],
      editable: false,
    };
  }

  const unsupportedFields: string[] = [];
  for (const [name, prop] of Object.entries(adapted.schema.properties)) {
    if (detectUnsupportedShape(prop) !== null) {
      unsupportedFields.push(name);
    }
  }

  return {
    schema: adapted.schema,
    diagnostics: adapted.diagnostics,
    unsupportedFields,
    editable: unsupportedFields.length === 0,
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

// ---------------------------------------------------------------------------
// Default materialization
// ---------------------------------------------------------------------------

/**
 * Priority-ordered SchemaForm display fallbacks for supported primitive
 * types when no persisted value, manifest default, or schema property
 * `default` exists.
 *
 * These are purely display-side fillers — they are **not** persisted and
 * exist only to give the SchemaForm a coherent starting point for the
 * interactive widget.  The precedence is intentionally low:
 *
 * 1. Saved value (already set externally — not handled here)
 * 2. Manifest `settingsDefaults` entry
 * 3. Schema property `default`
 * 4. Display-only SchemaForm fallback ← this table
 */
const SCHEMAFORM_DISPLAY_FALLBACKS: ReadonlyMap<string, unknown> = new Map<string, unknown>([
  ['string', ''],
  ['number', 0],
  ['integer', 0],
  ['boolean', false],
  // enum → first enum value (handled per-field below)
]);

/**
 * Materialize the initial settings values for a set of supported top-level
 * fields by applying the following precedence:
 *
 *  1. Manifest `settingsDefaults` (highest)
 *  2. Schema property `default`
 *  3. Display-only SchemaForm type-based fallback (lowest)
 *
 * Only fields present in the adapted `schema.properties` are included in
 * the returned record.  Fields with unsupported shapes (`$ref`,
 * combinators, arrays, nested objects, conditionals) are **excluded**
 * from the result — the caller should never attempt to edit them via
 * SchemaForm.
 *
 * The function is intentionally decoupled from React; both Manager
 * reconciliation and the standalone settings panel can call it to produce
 * consistent base values before persisted overrides are applied.
 *
 * @param schema          A SchemaForm-compatible `StandardSchema` (adapted
 *                        from an extension manifest's settings schema).
 * @param settingsDefaults  The manifest `settingsDefaults` record, or
 *                        `undefined` when no defaults are declared.
 * @returns A record mapping every *supported* property name to its
 *          materialized default value.
 */
export function materializeSettingsDefaults(
  schema: StandardSchema,
  settingsDefaults: Record<string, unknown> | undefined,
): Record<string, unknown> {
  const result: Record<string, unknown> = {};

  for (const [name, prop] of Object.entries(schema.properties)) {
    // Skip unsupported shapes — they have no editable widget and cannot
    // carry a meaningful default.
    if (detectUnsupportedShape(prop) !== null) {
      continue;
    }

    // 1. Manifest settingsDefaults wins
    if (settingsDefaults && name in settingsDefaults) {
      result[name] = settingsDefaults[name];
      continue;
    }

    // 2. Schema property default
    if (prop.default !== undefined) {
      result[name] = prop.default;
      continue;
    }

    // 3. Display-only SchemaForm fallback (type-based)
    const propType = prop.type ?? 'string';

    if (prop.enum && prop.enum.length > 0) {
      // Enum: first enum value as display fallback (works for string and
      // number enums alike).
      result[name] = prop.enum[0];
    } else {
      result[name] = SCHEMAFORM_DISPLAY_FALLBACKS.get(propType) ?? '';
    }
  }

  return result;
}

// ---------------------------------------------------------------------------
// Settings reconciliation (T3)
// ---------------------------------------------------------------------------

/**
 * Reconciliation state classification for a settings snapshot.
 *
 * - `clean`: All values match the supported schema exactly; no repairs needed.
 * - `repaired`: Safe fixes applied (missing defaults filled, numeric-string
 *   coercion).
 * - `needs-review`: Legacy values preserved but cannot be safely reconciled
 *   without user confirmation (invalid enum, unconvertible type mismatch,
 *   unknown fields dropped, etc.).
 * - `blocked`: Cannot proceed — corrupt/non-object snapshot, unsupported
 *   schema constructs, or missing schema altogether.
 */
export type ReconciliationState = 'clean' | 'repaired' | 'needs-review' | 'blocked';

/** Result of reconciling a settings snapshot against a manifest schema. */
export interface ReconciliationResult {
  /** The overall reconciliation classification. */
  readonly state: ReconciliationState;
  /** The reconciled settings values (supported fields only). */
  readonly values: Record<string, unknown>;
  /** Diagnostics emitted during reconciliation. */
  readonly diagnostics: readonly ExtensionDiagnostic[];
  /** Fields present in the snapshot but absent from the schema (dropped). */
  readonly droppedUnknownFields: readonly string[];
}

/**
 * Reconstitute a saved {@link ExtensionSettingsSnapshot} (or raw values
 * record) against the extension manifest's declared settings schema.
 *
 * The function classifies the snapshot as `clean`, `repaired`,
 * `needs-review`, or `blocked` and produces a reconciled `values` record
 * that includes only supported, schema-declared fields with correct types.
 *
 * **Precedence for each supported field:**
 * 1. Saved snapshot value (when type-compatible with schema property).
 * 2. Coerced snapshot value (numeric string → number, number → integer).
 * 3. Materialized default via {@link materializeSettingsDefaults}.
 *
 * Unknown fields (present in the snapshot but absent from the schema) are
 * always dropped and reported in {@link ReconciliationResult.droppedUnknownFields}.
 *
 * @param manifest  The extension manifest whose settings schema to reconcile against.
 * @param snapshot  The saved snapshot (a {@link SettingsSnapshot} with a
 *                  `values` key, a raw values object, or `null`/`undefined`
 *                  for a fresh start).
 */
export function reconcileSettingsSnapshot({
  manifest,
  snapshot,
}: {
  manifest: ExtensionManifest;
  snapshot: unknown;
}): ReconciliationResult {
  const diagnostics: ExtensionDiagnostic[] = [];
  const extensionId = manifest.id as string;

  // 1. Analyze the manifest schema
  const analysis = analyzeManifestSettingsSchema(manifest);

  // Push schema-adapter diagnostics into the reconciliation result
  for (const d of analysis.diagnostics) {
    diagnostics.push(d);
  }

  // No usable schema → blocked
  if (!analysis.schema) {
    return {
      state: 'blocked',
      values: {},
      diagnostics,
      droppedUnknownFields: [],
    };
  }

  // Unsupported schema constructs → blocked
  if (!analysis.editable) {
    diagnostics.push(
      makeDiagnostic(
        'settings/unsupported-schema',
        `Extension "${extensionId}" uses unsupported schema constructs (fields: ${analysis.unsupportedFields.join(', ')}); settings are not editable.`,
        extensionId,
        'error',
      ),
    );
    return {
      state: 'blocked',
      values: {},
      diagnostics,
      droppedUnknownFields: [],
    };
  }

  const schema = analysis.schema;

  // 2. Extract raw values from snapshot
  const rawValues = extractSnapshotValues(snapshot);

  // Corrupt / non-object snapshot → blocked
  if (rawValues === null) {
    diagnostics.push(
      makeDiagnostic(
        'settings/corrupt-snapshot',
        `Extension "${extensionId}" settings snapshot is corrupt or not a valid object.`,
        extensionId,
        'error',
      ),
    );
    return {
      state: 'blocked',
      values: {},
      diagnostics,
      droppedUnknownFields: [],
    };
  }

  // 3. Build a map of raw property types from the manifest schema (before
  //    adaptation maps `integer` → `number`).  This lets `coerceValue`
  //    distinguish integer from number for truncation behaviour.
  const rawPropTypes = buildRawPropTypes(manifest);

  // 4. Materialize defaults as the base
  const defaults = materializeSettingsDefaults(
    schema,
    manifest.settingsDefaults as Record<string, unknown> | undefined,
  );

  // 5. Reconcile each supported field
  const values: Record<string, unknown> = {};
  let hasRepairs = false;
  let needsReview = false;

  for (const [name, prop] of Object.entries(schema.properties)) {
    // Only reconcile supported shapes
    if (detectUnsupportedShape(prop) !== null) {
      continue;
    }

    const savedValue = rawValues[name];
    const defaultValue = defaults[name];

    if (savedValue !== undefined) {
      // Field is present in the snapshot — validate/coerce
      const coercion = coerceValue(savedValue, prop, name, extensionId, rawPropTypes.get(name));

      if (coercion.action === 'use-as-is') {
        values[name] = savedValue;
      } else if (coercion.action === 'coerced') {
        values[name] = coercion.value;
        hasRepairs = true;
        if (coercion.diagnostic) {
          diagnostics.push(coercion.diagnostic);
        }
      } else if (coercion.action === 'needs-review') {
        // Preserve the original value but flag for review
        values[name] = savedValue;
        needsReview = true;
        if (coercion.diagnostic) {
          diagnostics.push(coercion.diagnostic);
        }
      } else {
        // Fallback to default (should not normally happen)
        values[name] = defaultValue;
        hasRepairs = true;
      }
    } else {
      // Field missing from snapshot — use default
      values[name] = defaultValue;
      hasRepairs = true;
    }
  }

  // 5. Detect unknown fields in the snapshot
  const schemaPropNames = new Set(Object.keys(schema.properties));
  const unknownFields: string[] = [];

  for (const key of Object.keys(rawValues)) {
    if (!schemaPropNames.has(key)) {
      unknownFields.push(key);
    }
  }

  // Unknown fields trigger needs-review (they are dropped from values)
  if (unknownFields.length > 0) {
    needsReview = true;
    for (const field of unknownFields) {
      diagnostics.push(
        makeDiagnostic(
          'settings/unknown-field',
          `Unknown field "${field}" found in settings snapshot for extension "${extensionId}"; it will be dropped on save.`,
          extensionId,
          'warning',
        ),
      );
    }
  }

  // 6. Check additionalProperties: false in the raw schema
  const rawSchema = manifest.settingsSchema?.schema;
  const hasStrictAdditionalProperties =
    rawSchema !== undefined &&
    typeof rawSchema === 'object' &&
    !Array.isArray(rawSchema) &&
    (rawSchema as Record<string, unknown>).additionalProperties === false;

  // 7. Determine final state
  //    When the schema has `additionalProperties: false`, dropping unknown
  //    fields is schema enforcement, not a user-review concern.  In that
  //    case the drop is treated as an automatic repair so the result is at
  //    least `repaired` (unless other review-level issues exist).
  if (unknownFields.length > 0 && hasStrictAdditionalProperties) {
    // Dropping unknown fields is an automatic repair action
    hasRepairs = true;
    // Only flag needs-review if there are other review-level issues
    const otherReviewIssues = checkForReviewIssues(values, rawValues, schema);
    needsReview = otherReviewIssues;
  }

  let state: ReconciliationState;
  if (needsReview) {
    state = 'needs-review';
  } else if (hasRepairs) {
    state = 'repaired';
  } else {
    state = 'clean';
  }

  return {
    state,
    values,
    diagnostics,
    droppedUnknownFields: unknownFields,
  };
}

// ---------------------------------------------------------------------------
// Reconciliation helpers
// ---------------------------------------------------------------------------

/**
 * Extract a plain values record from a snapshot.
 *
 * Handles:
 * - `null` / `undefined` → empty record (fresh start).
 * - Object with a `values` key containing a non-null non-array object →
 *   use `snapshot.values`.
 * - Plain object without `values` → use the object itself.
 * - Arrays, primitives, or objects with non-object `values` → `null` (corrupt).
 */
function extractSnapshotValues(
  snapshot: unknown,
): Record<string, unknown> | null {
  if (snapshot === null || snapshot === undefined) {
    return {};
  }

  if (typeof snapshot !== 'object' || Array.isArray(snapshot)) {
    return null; // Corrupt: not an object
  }

  const obj = snapshot as Record<string, unknown>;

  // If the snapshot has a `values` key, prefer that
  if ('values' in obj) {
    const v = obj.values;
    if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
      return v as Record<string, unknown>;
    }
    // values exists but is not a valid object → corrupt
    return null;
  }

  // Plain object — treat as raw values record
  return obj;
}

/** Outcome of coercing a single snapshot value against a schema property. */
interface ValueCoercion {
  action: 'use-as-is' | 'coerced' | 'needs-review' | 'fallback';
  value?: unknown;
  diagnostic?: ExtensionDiagnostic;
}

/**
 * Build a map of field name → raw JSON Schema type from the manifest.
 *
 * This preserves the original `integer` type before adaptation maps it to
 * `number`, so coercion can apply integer-specific rules (truncation).
 */
function buildRawPropTypes(manifest: ExtensionManifest): Map<string, string | undefined> {
  const map = new Map<string, string | undefined>();
  const rawSchema = manifest.settingsSchema?.schema;
  if (!rawSchema || typeof rawSchema !== 'object' || Array.isArray(rawSchema)) {
    return map;
  }
  const rawProps = (rawSchema as Record<string, unknown>).properties;
  if (!rawProps || typeof rawProps !== 'object' || Array.isArray(rawProps)) {
    return map;
  }
  for (const [name, rawProp] of Object.entries(rawProps as Record<string, unknown>)) {
    if (rawProp && typeof rawProp === 'object' && !Array.isArray(rawProp)) {
      const rp = rawProp as Record<string, unknown>;
      map.set(name, typeof rp.type === 'string' ? rp.type : undefined);
    }
  }
  return map;
}

/**
 * Coerce a saved value to match the expected schema property type.
 *
 * Safe repairs (→ `coerced`):
 * - Numeric string (e.g. `"42"`) for a `number` / `integer` field.
 *
 * Needs-review:
 * - Invalid enum value (not in the enum list).
 * - Type mismatch that cannot be safely coerced.
 *
 * @param rawType  The original JSON Schema type from the manifest (before
 *                 adaptation), or `undefined`.  Used to distinguish `integer`
 *                 from `number` for truncation behaviour.
 */
function coerceValue(
  value: unknown,
  prop: StandardSchemaProperty,
  fieldName: string,
  extensionId: string,
  rawType?: string,
): ValueCoercion {
  // Use raw type for the effective expected type (preserves integer/string
  // distinction that adaptation flattens).
  const effectiveType = rawType ?? prop.type;
  const expectedType = effectiveType;

  // ---- Enum validation ----
  if (prop.enum && prop.enum.length > 0) {
    const enumValues = prop.enum as unknown[];
    if (!enumValues.includes(value)) {
      return {
        action: 'needs-review',
        diagnostic: makeDiagnostic(
          'settings/invalid-enum',
          `Field "${fieldName}" value ${JSON.stringify(value)} is not one of the allowed enum values for extension "${extensionId}".`,
          extensionId,
          'warning',
        ),
      };
    }
    // Enum value is valid — use as-is (no type coercion for enums)
    return { action: 'use-as-is' };
  }

  // ---- No type declared — accept as-is ----
  if (!expectedType) {
    return { action: 'use-as-is' };
  }

  // ---- String field ----
  if (expectedType === 'string') {
    if (typeof value === 'string') return { action: 'use-as-is' };
    // Non-string value for a string field → needs-review
    return {
      action: 'needs-review',
      diagnostic: makeDiagnostic(
        'settings/type-mismatch',
        `Field "${fieldName}" expected type "string" but got ${typeof value} for extension "${extensionId}".`,
        extensionId,
        'warning',
      ),
    };
  }

  // ---- Number / integer field ----
  if (expectedType === 'number' || expectedType === 'integer') {
    if (typeof value === 'number') {
      // Check if it's a finite number
      if (!Number.isFinite(value)) {
        return {
          action: 'needs-review',
          diagnostic: makeDiagnostic(
            'settings/non-finite-number',
            `Field "${fieldName}" has non-finite value ${value} for extension "${extensionId}".`,
            extensionId,
            'warning',
          ),
        };
      }
      return { action: 'use-as-is' };
    }

    // Numeric string coercion
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (trimmed === '') {
        return {
          action: 'needs-review',
          diagnostic: makeDiagnostic(
            'settings/type-mismatch',
            `Field "${fieldName}" expected type "${expectedType}" but got empty string for extension "${extensionId}".`,
            extensionId,
            'warning',
          ),
        };
      }

      const parsed = Number(trimmed);
      if (!Number.isFinite(parsed)) {
        return {
          action: 'needs-review',
          diagnostic: makeDiagnostic(
            'settings/unparseable-number',
            `Field "${fieldName}" value "${trimmed}" could not be parsed as a number for extension "${extensionId}".`,
            extensionId,
            'warning',
          ),
        };
      }

      // Coerce to number (for integer type, truncate to integer)
      const coerced = expectedType === 'integer' ? Math.trunc(parsed) : parsed;
      return {
        action: 'coerced',
        value: coerced,
        diagnostic: makeDiagnostic(
          'settings/numeric-string-coerced',
          `Field "${fieldName}" numeric string "${trimmed}" coerced to ${coerced} for extension "${extensionId}".`,
          extensionId,
          'info',
        ),
      };
    }

    // Boolean → number coercion (true→1, false→0)
    if (typeof value === 'boolean') {
      const coerced = expectedType === 'integer' ? (value ? 1 : 0) : (value ? 1 : 0);
      return {
        action: 'coerced',
        value: coerced,
        diagnostic: makeDiagnostic(
          'settings/boolean-to-number',
          `Field "${fieldName}" boolean ${value} coerced to ${coerced} for extension "${extensionId}".`,
          extensionId,
          'info',
        ),
      };
    }

    // Other type mismatch
    return {
      action: 'needs-review',
      diagnostic: makeDiagnostic(
        'settings/type-mismatch',
        `Field "${fieldName}" expected type "${expectedType}" but got ${typeof value} for extension "${extensionId}".`,
        extensionId,
        'warning',
      ),
    };
  }

  // ---- Boolean field ----
  if (expectedType === 'boolean') {
    if (typeof value === 'boolean') return { action: 'use-as-is' };

    // String "true"/"false" coercion
    if (typeof value === 'string') {
      const lower = value.trim().toLowerCase();
      if (lower === 'true') {
        return {
          action: 'coerced',
          value: true,
          diagnostic: makeDiagnostic(
            'settings/string-to-boolean',
            `Field "${fieldName}" string "true" coerced to boolean true for extension "${extensionId}".`,
            extensionId,
            'info',
          ),
        };
      }
      if (lower === 'false') {
        return {
          action: 'coerced',
          value: false,
          diagnostic: makeDiagnostic(
            'settings/string-to-boolean',
            `Field "${fieldName}" string "false" coerced to boolean false for extension "${extensionId}".`,
            extensionId,
            'info',
          ),
        };
      }
    }

    // Number → boolean coercion (0→false, non-zero→true)
    if (typeof value === 'number') {
      const coerced = value !== 0;
      return {
        action: 'coerced',
        value: coerced,
        diagnostic: makeDiagnostic(
          'settings/number-to-boolean',
          `Field "${fieldName}" number ${value} coerced to boolean ${coerced} for extension "${extensionId}".`,
          extensionId,
          'info',
        ),
      };
    }

    return {
      action: 'needs-review',
      diagnostic: makeDiagnostic(
        'settings/type-mismatch',
        `Field "${fieldName}" expected type "boolean" but got ${typeof value} for extension "${extensionId}".`,
        extensionId,
        'warning',
      ),
    };
  }

  // ---- Unknown type — accept as-is ----
  return { action: 'use-as-is' };
}

/**
 * Check whether the reconciled values contain any review-level issues beyond
 * unknown fields.
 *
 * This is used to determine whether a snapshot with dropped unknown fields
 * should be classified as `needs-review` or `repaired` when the schema has
 * `additionalProperties: false`.
 */
function checkForReviewIssues(
  values: Record<string, unknown>,
  rawValues: Record<string, unknown>,
  schema: StandardSchema,
): boolean {
  for (const [name, prop] of Object.entries(schema.properties)) {
    if (detectUnsupportedShape(prop) !== null) continue;

    const savedValue = rawValues[name];
    if (savedValue === undefined) continue; // missing → not a review issue (it's repaired)

    // Check if the value would have been flagged for review
    if (prop.enum && prop.enum.length > 0) {
      if (!prop.enum.includes(savedValue as string | number)) {
        return true;
      }
      continue;
    }

    const expectedType = prop.type;
    if (!expectedType) continue;

    if (expectedType === 'string' && typeof savedValue !== 'string') {
      return true;
    }

    if ((expectedType === 'number' || expectedType === 'integer') && typeof savedValue !== 'number') {
      // Check if it's a coercible string or boolean
      if (typeof savedValue === 'string') {
        const trimmed = savedValue.trim();
        if (trimmed === '' || !Number.isFinite(Number(trimmed))) {
          return true;
        }
        // It's coercible → not a review issue
      } else if (typeof savedValue === 'boolean') {
        // Coercible → not a review issue
      } else {
        return true;
      }
    }

    if (expectedType === 'boolean' && typeof savedValue !== 'boolean') {
      if (typeof savedValue === 'string') {
        const lower = savedValue.trim().toLowerCase();
        if (lower !== 'true' && lower !== 'false') {
          return true;
        }
      } else if (typeof savedValue === 'number') {
        // Coercible (0→false, non-zero→true) → not a review issue
      } else {
        return true;
      }
    }
  }

  return false;
}
