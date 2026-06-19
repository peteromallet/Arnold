/**
 * M10: Agent tool contract validation and conversion helpers.
 *
 * Runtime boundary between arbitrary tool output and host-owned proposal
 * creation. Validates input schemas and ToolResults, creates diagnostics,
 * and converts timeline-editing results to TimelineProposalInput records.
 *
 * This module is pure and side-effect-free. It does not interact with
 * ProposalRuntime, DataProvider, or any editor internals.
 *
 * @module agentToolContracts
 * @milestone M10
 */

import type {
  AgentToolInputSchema,
  AgentToolInputProperty,
  ToolResult,
  ToolResultFamily,
  ToolMutationProposalResult,
  ToolResultDiagnostic,
  TimelineProposalInput,
  TimelinePatch,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Locked set of valid ToolResultFamily discriminators. */
export const SUPPORTED_TOOL_RESULT_FAMILIES: readonly ToolResultFamily[] = [
  'mutation/proposal',
  'generation/session',
  'material/artifact',
  'enrichment/search',
  'export',
  'process',
  'ui/summary',
] as const;

/** Valid input schema property types. */
const VALID_PROPERTY_TYPES = new Set<string>(['string', 'number', 'boolean', 'object']);

/** Maximum nested object depth for input schemas. */
const MAX_SCHEMA_DEPTH = 2;

// ---------------------------------------------------------------------------
// Diagnostic helpers
// ---------------------------------------------------------------------------

/**
 * Create a structured ToolResultDiagnostic.
 *
 * The `code` is automatically prefixed with `agent-tool/` for consistency
 * with the {@link ToolResultDiagnostic.code} contract.
 */
export function createToolResultDiagnostic(
  severity: ToolResultDiagnostic['severity'],
  code: string,
  message: string,
  detail?: Record<string, unknown>,
): ToolResultDiagnostic {
  const diagnostic: ToolResultDiagnostic = {
    severity,
    code: code.startsWith('agent-tool/')
      ? (code as `agent-tool/${string}`)
      : (`agent-tool/${code}` as `agent-tool/${string}`),
    message,
  };
  if (detail !== undefined) {
    (diagnostic as unknown as Record<string, unknown>).detail = detail;
  }
  return diagnostic;
}

/**
 * Syntactic sugar: create an error-level diagnostic.
 */
export function errorDiagnostic(
  code: string,
  message: string,
  detail?: Record<string, unknown>,
): ToolResultDiagnostic {
  return createToolResultDiagnostic('error', code, message, detail);
}

/**
 * Syntactic sugar: create a warning-level diagnostic.
 */
export function warningDiagnostic(
  code: string,
  message: string,
  detail?: Record<string, unknown>,
): ToolResultDiagnostic {
  return createToolResultDiagnostic('warning', code, message, detail);
}

/**
 * Syntactic sugar: create an info-level diagnostic.
 */
export function infoDiagnostic(
  code: string,
  message: string,
  detail?: Record<string, unknown>,
): ToolResultDiagnostic {
  return createToolResultDiagnostic('info', code, message, detail);
}

// ---------------------------------------------------------------------------
// Family helpers
// ---------------------------------------------------------------------------

/**
 * Type guard: check whether a value is a known ToolResultFamily discriminator.
 */
export function isToolResultFamily(value: unknown): value is ToolResultFamily {
  return (
    typeof value === 'string' &&
    (SUPPORTED_TOOL_RESULT_FAMILIES as readonly string[]).includes(value)
  );
}

// ---------------------------------------------------------------------------
// Input schema validation
// ---------------------------------------------------------------------------

/**
 * Validate a property definition within an agent tool input schema.
 *
 * Recurses into nested object properties up to {@link MAX_SCHEMA_DEPTH}.
 * Returns diagnostics for invalid property shapes.
 */
function validateInputProperty(
  property: unknown,
  path: string,
  depth: number,
): ToolResultDiagnostic[] {
  const diagnostics: ToolResultDiagnostic[] = [];

  if (typeof property !== 'object' || property === null) {
    diagnostics.push(
      errorDiagnostic(
        'invalid-input-property',
        `Input property at "${path}" must be an object.`,
        { path },
      ),
    );
    return diagnostics;
  }

  const prop = property as Record<string, unknown>;

  // Validate 'type'
  if (typeof prop.type !== 'string' || !VALID_PROPERTY_TYPES.has(prop.type)) {
    diagnostics.push(
      errorDiagnostic(
        'invalid-property-type',
        `Input property at "${path}" has invalid or missing type. ` +
          `Expected one of: string, number, boolean, object.`,
        { path, received: String(prop.type) },
      ),
    );
    return diagnostics; // Cannot recurse without a valid type
  }

  // Validate 'title' if present
  if (prop.title !== undefined && typeof prop.title !== 'string') {
    diagnostics.push(
      warningDiagnostic(
        'invalid-property-title',
        `Input property at "${path}" has non-string title; ignoring.`,
        { path },
      ),
    );
  }

  // Validate 'description' if present
  if (prop.description !== undefined && typeof prop.description !== 'string') {
    diagnostics.push(
      warningDiagnostic(
        'invalid-property-description',
        `Input property at "${path}" has non-string description; ignoring.`,
        { path },
      ),
    );
  }

  // Validate 'enum' (only for string type)
  if (prop.enum !== undefined) {
    if (prop.type !== 'string') {
      diagnostics.push(
        warningDiagnostic(
          'enum-on-non-string',
          `Input property at "${path}" declares enum but type is "${prop.type}"; ` +
            `enum is only valid for type "string".`,
          { path, type: prop.type },
        ),
      );
    } else if (!Array.isArray(prop.enum) || !prop.enum.every((v) => typeof v === 'string')) {
      diagnostics.push(
        errorDiagnostic(
          'invalid-enum-values',
          `Input property at "${path}" has invalid enum values; expected string[].`,
          { path },
        ),
      );
    }
  }

  // Validate 'default' type consistency
  if (prop.default !== undefined) {
    const defaultType = typeof prop.default;
    const schemaType = prop.type as string;
    if (schemaType === 'string' && defaultType !== 'string') {
      diagnostics.push(
        warningDiagnostic(
          'default-type-mismatch',
          `Input property at "${path}" default value type "${defaultType}" ` +
            `does not match schema type "string".`,
          { path, defaultType, schemaType },
        ),
      );
    } else if (schemaType === 'number' && defaultType !== 'number') {
      diagnostics.push(
        warningDiagnostic(
          'default-type-mismatch',
          `Input property at "${path}" default value type "${defaultType}" ` +
            `does not match schema type "number".`,
          { path, defaultType, schemaType },
        ),
      );
    } else if (schemaType === 'boolean' && defaultType !== 'boolean') {
      diagnostics.push(
        warningDiagnostic(
          'default-type-mismatch',
          `Input property at "${path}" default value type "${defaultType}" ` +
            `does not match schema type "boolean".`,
          { path, defaultType, schemaType },
        ),
      );
    }
  }

  // Recurse into nested object properties
  if (prop.type === 'object') {
    if (depth >= MAX_SCHEMA_DEPTH) {
      diagnostics.push(
        errorDiagnostic(
          'max-schema-depth-exceeded',
          `Input property at "${path}" exceeds maximum nesting depth of ${MAX_SCHEMA_DEPTH}.`,
          { path, depth },
        ),
      );
      return diagnostics;
    }

    if (prop.properties !== undefined) {
      if (typeof prop.properties !== 'object' || prop.properties === null) {
        diagnostics.push(
          errorDiagnostic(
            'invalid-nested-properties',
            `Input property at "${path}" has non-object "properties" field.`,
            { path },
          ),
        );
      } else {
        const nestedProps = prop.properties as Record<string, unknown>;
        for (const key of Object.keys(nestedProps)) {
          diagnostics.push(
            ...validateInputProperty(nestedProps[key], `${path}.${key}`, depth + 1),
          );
        }
      }
    }

    // Validate nested 'required'
    if (prop.required !== undefined) {
      if (!Array.isArray(prop.required) || !prop.required.every((v) => typeof v === 'string')) {
        diagnostics.push(
          errorDiagnostic(
            'invalid-nested-required',
            `Input property at "${path}" has non-string[] "required" field.`,
            { path },
          ),
        );
      }
    }
  } else {
    // Non-object types should not have nested properties or required
    if (prop.properties !== undefined) {
      diagnostics.push(
        warningDiagnostic(
          'properties-on-non-object',
          `Input property at "${path}" declares "properties" but type is "${prop.type}"; ignoring.`,
          { path, type: prop.type },
        ),
      );
    }
    if (prop.required !== undefined) {
      diagnostics.push(
        warningDiagnostic(
          'required-on-non-object',
          `Input property at "${path}" declares "required" but type is "${prop.type}"; ignoring.`,
          { path, type: prop.type },
        ),
      );
    }
  }

  return diagnostics;
}

/**
 * Validate an agent tool input schema against the supported StandardSchema subset.
 *
 * Checks:
 * - Top-level type is 'object'
 * - Properties are valid {@link AgentToolInputProperty} shapes
 * - Required fields reference declared properties
 * - Nesting depth does not exceed {@link MAX_SCHEMA_DEPTH}
 * - Title and description are strings when present
 *
 * @returns Array of diagnostics (empty = valid).
 */
export function validateAgentToolInputSchema(
  schema: unknown,
): ToolResultDiagnostic[] {
  const diagnostics: ToolResultDiagnostic[] = [];

  if (schema === undefined || schema === null) {
    // Absent schema is valid (tools may have no inputs)
    return diagnostics;
  }

  if (typeof schema !== 'object') {
    diagnostics.push(
      errorDiagnostic(
        'invalid-input-schema',
        'Agent tool input schema must be an object or undefined.',
        { received: typeof schema },
      ),
    );
    return diagnostics;
  }

  const s = schema as Record<string, unknown>;

  // Validate top-level type
  if (s.type !== 'object') {
    diagnostics.push(
      errorDiagnostic(
        'invalid-schema-type',
        `Agent tool input schema type must be "object", received "${String(s.type)}".`,
        { received: String(s.type) },
      ),
    );
    // Continue validating other fields for richer diagnostics
  }

  // Validate title
  if (s.title !== undefined && typeof s.title !== 'string') {
    diagnostics.push(
      warningDiagnostic(
        'invalid-schema-title',
        'Input schema title must be a string.',
        { received: typeof s.title },
      ),
    );
  }

  // Validate description
  if (s.description !== undefined && typeof s.description !== 'string') {
    diagnostics.push(
      warningDiagnostic(
        'invalid-schema-description',
        'Input schema description must be a string.',
        { received: typeof s.description },
      ),
    );
  }

  // Validate properties
  const propertyNames: string[] = [];
  if (s.properties !== undefined) {
    if (typeof s.properties !== 'object' || s.properties === null) {
      diagnostics.push(
        errorDiagnostic(
          'invalid-schema-properties',
          'Input schema properties must be an object.',
          { received: typeof s.properties },
        ),
      );
    } else {
      const props = s.properties as Record<string, unknown>;
      for (const key of Object.keys(props)) {
        propertyNames.push(key);
        diagnostics.push(...validateInputProperty(props[key], key, 1));
      }
    }
  }

  // Validate required fields
  if (s.required !== undefined) {
    if (!Array.isArray(s.required)) {
      diagnostics.push(
        errorDiagnostic(
          'invalid-required-array',
          'Input schema "required" must be an array of property names.',
          { received: typeof s.required },
        ),
      );
    } else {
      const requiredArray = s.required as unknown[];
      for (let i = 0; i < requiredArray.length; i++) {
        const item = requiredArray[i];
        if (typeof item !== 'string') {
          diagnostics.push(
            errorDiagnostic(
              'invalid-required-item',
              `Input schema "required" contains non-string item at index ${i}.`,
              { index: i, received: typeof item },
            ),
          );
        } else if (!propertyNames.includes(item) && propertyNames.length > 0) {
          diagnostics.push(
            warningDiagnostic(
              'required-field-not-in-properties',
              `Required field "${item}" is not declared in properties.`,
              { field: item },
            ),
          );
        }
      }
    }
  }

  return diagnostics;
}

// ---------------------------------------------------------------------------
// ToolResult validation
// ---------------------------------------------------------------------------

/**
 * Validate that a value is a well-formed ToolResult.
 *
 * Checks the `family` discriminator and validates the payload shape
 * for each supported family. Family-specific payload validation is
 * best-effort (structural) — it does not validate semantic correctness
 * of patch operations, session IDs, or artifact refs.
 *
 * @returns Array of diagnostics (empty = valid).
 */
export function validateToolResult(result: unknown): ToolResultDiagnostic[] {
  const diagnostics: ToolResultDiagnostic[] = [];

  if (typeof result !== 'object' || result === null) {
    diagnostics.push(
      errorDiagnostic(
        'tool-result-not-object',
        'Tool result must be a non-null object.',
        { received: typeof result },
      ),
    );
    return diagnostics;
  }

  const r = result as Record<string, unknown>;

  // Validate family discriminator
  if (typeof r.family !== 'string') {
    diagnostics.push(
      errorDiagnostic(
        'missing-result-family',
        'Tool result is missing the required "family" discriminator.',
        { keys: Object.keys(r) },
      ),
    );
    return diagnostics;
  }

  if (!isToolResultFamily(r.family)) {
    diagnostics.push(
      errorDiagnostic(
        'unsupported-result-family',
        `Tool result family "${String(r.family)}" is not supported. ` +
          `Supported families: ${SUPPORTED_TOOL_RESULT_FAMILIES.join(', ')}.`,
        { received: r.family, supported: SUPPORTED_TOOL_RESULT_FAMILIES },
      ),
    );
    return diagnostics; // Cannot validate further without a known family
  }

  const family = r.family as ToolResultFamily;

  // Family-specific structural validation
  switch (family) {
    case 'mutation/proposal': {
      // Must have a patches array
      if (!Array.isArray(r.patches)) {
        diagnostics.push(
          errorDiagnostic(
            'mutation-missing-patches',
            'Mutation/proposal result must include a "patches" array.',
            { keys: Object.keys(r) },
          ),
        );
      } else if (r.patches.length === 0) {
        diagnostics.push(
          warningDiagnostic(
            'mutation-empty-patches',
            'Mutation/proposal result has an empty patches array.',
            {},
          ),
        );
      } else {
        // Best-effort: check that patches are objects with an 'operations' array
        for (let i = 0; i < r.patches.length; i++) {
          const patch = (r.patches as unknown[])[i];
          if (typeof patch !== 'object' || patch === null) {
            diagnostics.push(
              errorDiagnostic(
                'invalid-patch-item',
                `Patch at index ${i} is not an object.`,
                { index: i },
              ),
            );
          } else {
            const p = patch as Record<string, unknown>;
            if (!Array.isArray(p.operations)) {
              diagnostics.push(
                warningDiagnostic(
                  'patch-missing-operations',
                  `Patch at index ${i} has no "operations" array.`,
                  { index: i },
                ),
              );
            }
            if (p.versionHint !== undefined && typeof p.versionHint !== 'number') {
              diagnostics.push(
                warningDiagnostic(
                  'invalid-version-hint',
                  `Patch at index ${i} has non-number "versionHint".`,
                  { index: i },
                ),
              );
            }
          }
        }
      }

      // Validate rationale if present
      if (r.rationale !== undefined && typeof r.rationale !== 'string') {
        diagnostics.push(
          warningDiagnostic(
            'invalid-rationale-type',
            'Mutation/proposal result rationale must be a string.',
            {},
          ),
        );
      }

      // Validate affectedObjectIds if present
      if (r.affectedObjectIds !== undefined) {
        if (!Array.isArray(r.affectedObjectIds)) {
          diagnostics.push(
            warningDiagnostic(
              'invalid-affected-ids',
              'affectedObjectIds must be an array of strings.',
              {},
            ),
          );
        }
      }

      // Validate sourceRefs if present
      if (r.sourceRefs !== undefined) {
        if (!Array.isArray(r.sourceRefs)) {
          diagnostics.push(
            warningDiagnostic(
              'invalid-source-refs',
              'sourceRefs must be an array.',
              {},
            ),
          );
        }
      }
      break;
    }

    case 'generation/session': {
      // Must have a session
      if (typeof r.session !== 'object' || r.session === null) {
        diagnostics.push(
          errorDiagnostic(
            'generation-missing-session',
            'Generation/session result must include a "session" object.',
            { keys: Object.keys(r) },
          ),
        );
      } else {
        const session = r.session as Record<string, unknown>;
        if (typeof session.id !== 'string') {
          diagnostics.push(
            errorDiagnostic(
              'session-missing-id',
              'Session object must have a string "id".',
              {},
            ),
          );
        }
        if (typeof session.cancel !== 'function') {
          diagnostics.push(
            warningDiagnostic(
              'session-missing-cancel',
              'Session object should have a "cancel" method.',
              {},
            ),
          );
        }
      }
      // Rationale is optional
      if (r.rationale !== undefined && typeof r.rationale !== 'string') {
        diagnostics.push(
          warningDiagnostic(
            'invalid-rationale-type',
            'Generation/session result rationale must be a string.',
            {},
          ),
        );
      }
      break;
    }

    case 'material/artifact': {
      // Must have refs
      if (!Array.isArray(r.refs)) {
        diagnostics.push(
          errorDiagnostic(
            'material-missing-refs',
            'Material/artifact result must include a "refs" array.',
            { keys: Object.keys(r) },
          ),
        );
      } else if (r.refs.length === 0) {
        diagnostics.push(
          warningDiagnostic(
            'material-empty-refs',
            'Material/artifact result has an empty refs array.',
            {},
          ),
        );
      }
      if (r.rationale !== undefined && typeof r.rationale !== 'string') {
        diagnostics.push(
          warningDiagnostic(
            'invalid-rationale-type',
            'Material/artifact result rationale must be a string.',
            {},
          ),
        );
      }
      break;
    }

    case 'enrichment/search': {
      // At least one of suggestions or matches should be present
      const hasSuggestions =
        r.suggestions !== undefined && typeof r.suggestions === 'object' && r.suggestions !== null;
      const hasMatches = Array.isArray(r.matches) && r.matches.length > 0;
      if (!hasSuggestions && !hasMatches) {
        diagnostics.push(
          warningDiagnostic(
            'enrichment-no-data',
            'Enrichment/search result has neither suggestions nor matches.',
            {},
          ),
        );
      }
      if (r.suggestions !== undefined && typeof r.suggestions !== 'object') {
        diagnostics.push(
          warningDiagnostic(
            'invalid-suggestions-type',
            'Enrichment suggestions must be an object.',
            {},
          ),
        );
      }
      if (r.matches !== undefined && !Array.isArray(r.matches)) {
        diagnostics.push(
          warningDiagnostic(
            'invalid-matches-type',
            'Enrichment matches must be an array.',
            {},
          ),
        );
      }
      if (r.rationale !== undefined && typeof r.rationale !== 'string') {
        diagnostics.push(
          warningDiagnostic(
            'invalid-rationale-type',
            'Enrichment/search result rationale must be a string.',
            {},
          ),
        );
      }
      break;
    }

    case 'export': {
      // findings is optional; validate if present
      if (r.findings !== undefined && !Array.isArray(r.findings)) {
        diagnostics.push(
          warningDiagnostic(
            'invalid-findings-type',
            'Export findings must be an array.',
            {},
          ),
        );
      }
      if (r.rationale !== undefined && typeof r.rationale !== 'string') {
        diagnostics.push(
          warningDiagnostic(
            'invalid-rationale-type',
            'Export result rationale must be a string.',
            {},
          ),
        );
      }
      break;
    }

    case 'process': {
      // Must have diagnostics (always present before M12)
      if (!Array.isArray(r.diagnostics) || r.diagnostics.length === 0) {
        diagnostics.push(
          errorDiagnostic(
            'process-missing-diagnostics',
            'Process result must include a non-empty "diagnostics" array.',
            { keys: Object.keys(r) },
          ),
        );
      }
      break;
    }

    case 'ui/summary': {
      // Must have summary
      if (typeof r.summary !== 'string') {
        diagnostics.push(
          errorDiagnostic(
            'summary-missing-text',
            'UI/summary result must include a "summary" string.',
            { keys: Object.keys(r) },
          ),
        );
      }
      if (r.detail !== undefined && typeof r.detail !== 'object') {
        diagnostics.push(
          warningDiagnostic(
            'invalid-detail-type',
            'UI/summary detail must be an object.',
            {},
          ),
        );
      }
      break;
    }

    default: {
      // Exhaustiveness check — should never reach here
      diagnostics.push(
        errorDiagnostic(
          'unhandled-result-family',
          `Tool result family "${family}" is known but not validated.`,
          { family },
        ),
      );
      break;
    }
  }

  // Validate diagnostics array if present (cross-family)
  if (r.diagnostics !== undefined) {
    if (!Array.isArray(r.diagnostics)) {
      diagnostics.push(
        warningDiagnostic(
          'invalid-diagnostics-array',
          'Tool result "diagnostics" must be an array of ToolResultDiagnostic.',
          {},
        ),
      );
    } else {
      for (let i = 0; i < (r.diagnostics as unknown[]).length; i++) {
        const d = (r.diagnostics as unknown[])[i];
        if (typeof d !== 'object' || d === null) {
          diagnostics.push(
            warningDiagnostic(
              'invalid-diagnostic-item',
              `Diagnostic at index ${i} is not an object.`,
              { index: i },
            ),
          );
        } else {
          const diag = d as Record<string, unknown>;
          if (typeof diag.severity !== 'string') {
            diagnostics.push(
              warningDiagnostic(
                'diagnostic-missing-severity',
                `Diagnostic at index ${i} is missing "severity".`,
                { index: i },
              ),
            );
          }
          if (typeof diag.code !== 'string') {
            diagnostics.push(
              warningDiagnostic(
                'diagnostic-missing-code',
                `Diagnostic at index ${i} is missing "code".`,
                { index: i },
              ),
            );
          }
          if (typeof diag.message !== 'string') {
            diagnostics.push(
              warningDiagnostic(
                'diagnostic-missing-message',
                `Diagnostic at index ${i} is missing "message".`,
                { index: i },
              ),
            );
          }
        }
      }
    }
  }

  return diagnostics;
}

// ---------------------------------------------------------------------------
// ToolResult type guards
// ---------------------------------------------------------------------------

/**
 * Type guard: check whether a value is a `ToolMutationProposalResult`.
 *
 * Performs structural checks without validating patch semantics.
 */
export function isMutationProposalResult(
  result: unknown,
): result is ToolMutationProposalResult {
  if (typeof result !== 'object' || result === null) return false;
  const r = result as Record<string, unknown>;
  return (
    r.family === 'mutation/proposal' &&
    Array.isArray(r.patches)
  );
}

/**
 * Type guard: check whether a ToolResult family supports timeline editing
 * (i.e., can be converted to a TimelineProposalInput).
 */
export function isTimelineEditableResult(
  result: unknown,
): result is ToolMutationProposalResult {
  return isMutationProposalResult(result);
}

// ---------------------------------------------------------------------------
// Result-to-proposal conversion
// ---------------------------------------------------------------------------

/**
 * Convert a timeline-editing {@link ToolMutationProposalResult} to a
 * host-owned {@link TimelineProposalInput}.
 *
 * Preserves rationale, source/output refs (via affectedObjectIds),
 * and base version. Each patch in the result produces a separate
 * proposal — the caller should call this once per patch or combine
 * patches before calling.
 *
 * The `source` parameter identifies the tool that produced the result
 * (e.g. `"extensionId.toolId"`). It is stored in the proposal's `source` field.
 *
 * @param result - A validated mutation/proposal tool result.
 * @param baseVersion - The timeline version the result was computed against.
 * @param source - Human-readable source identifier for the proposal.
 * @returns A TimelineProposalInput ready for ProposalRuntime.create().
 * @throws If the result is not a mutation/proposal result or has no patches.
 */
export function toolResultToTimelineProposalInput(
  result: ToolMutationProposalResult,
  baseVersion: number,
  source: string,
): TimelineProposalInput {
  if (!isMutationProposalResult(result)) {
    throw new Error(
      'Cannot convert non-mutation/proposal result to TimelineProposalInput.',
    );
  }

  if (result.patches.length === 0) {
    throw new Error(
      'Cannot convert mutation/proposal result with empty patches array.',
    );
  }

  // Build rationale, incorporating tool diagnostics if present
  let rationale = result.rationale ?? `Proposed by agent tool: ${source}`;

  // Append affected object context to rationale if available
  if (result.affectedObjectIds && result.affectedObjectIds.length > 0) {
    const objectList = result.affectedObjectIds.slice(0, 5).join(', ');
    const suffix =
      result.affectedObjectIds.length > 5
        ? ` (and ${result.affectedObjectIds.length - 5} more)`
        : '';
    rationale += `\nAffected objects: ${objectList}${suffix}`;
  }

  // Append source ref context to rationale if available
  if (result.sourceRefs && result.sourceRefs.length > 0) {
    const refSummaries = result.sourceRefs
      .map((ref) => `${ref.sourceId} → ${ref.outputId}`)
      .join('; ');
    rationale += `\nSource→Output refs: ${refSummaries}`;
  }

  // Use the first patch. Callers with multiple patches should call
  // this function once per patch.
  const patch: TimelinePatch = result.patches[0];

  return {
    source,
    rationale,
    patch,
    baseVersion,
  };
}

/**
 * Convert a mutation/proposal result to multiple TimelineProposalInput records,
 * one per patch in the result.
 *
 * Each proposal gets the same baseVersion, source, and rationale context.
 * Source/output refs and affected object IDs are spread across all proposals.
 *
 * @param result - A validated mutation/proposal tool result.
 * @param baseVersion - The timeline version the result was computed against.
 * @param source - Human-readable source identifier for the proposal.
 * @returns Array of TimelineProposalInput records.
 * @throws If the result is not a mutation/proposal result or has no patches.
 */
export function toolResultToTimelineProposalInputs(
  result: ToolMutationProposalResult,
  baseVersion: number,
  source: string,
): TimelineProposalInput[] {
  if (!isMutationProposalResult(result)) {
    throw new Error(
      'Cannot convert non-mutation/proposal result to TimelineProposalInputs.',
    );
  }

  if (result.patches.length === 0) {
    throw new Error(
      'Cannot convert mutation/proposal result with empty patches array.',
    );
  }

  return result.patches.map((patch, index) => {
    const patchSource =
      result.patches.length > 1 ? `${source}#patch${index + 1}` : source;

    let rationale = result.rationale ?? `Proposed by agent tool: ${source}`;

    if (result.patches.length > 1) {
      rationale += ` (patch ${index + 1} of ${result.patches.length})`;
    }

    if (result.affectedObjectIds && result.affectedObjectIds.length > 0) {
      const objectList = result.affectedObjectIds.slice(0, 5).join(', ');
      const suffix =
        result.affectedObjectIds.length > 5
          ? ` (and ${result.affectedObjectIds.length - 5} more)`
          : '';
      rationale += `\nAffected objects: ${objectList}${suffix}`;
    }

    if (result.sourceRefs && result.sourceRefs.length > 0) {
      const refSummaries = result.sourceRefs
        .map((ref) => `${ref.sourceId} → ${ref.outputId}`)
        .join('; ');
      rationale += `\nSource→Output refs: ${refSummaries}`;
    }

    return {
      source: patchSource,
      rationale,
      patch,
      baseVersion,
    };
  });
}
