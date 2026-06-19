/**
 * M10 T4: Focused tests for agentToolContracts.
 *
 * Covers:
 *  - validateAgentToolInputSchema: supported/unsupported StandardSchema subsets
 *  - validateToolResult: accepted grouped families, invalid one-off shapes
 *  - Diagnostic helpers: createToolResultDiagnostic, error/warning/info
 *  - Type guards: isToolResultFamily, isMutationProposalResult, isTimelineEditableResult
 *  - toolResultToTimelineProposalInput / toolResultToTimelineProposalInputs:
 *    conversion metadata preservation, base version, stale/version diagnostics
 *
 * @module agentToolContracts.test
 * @milestone M10
 */

import { describe, expect, it } from 'vitest';
import {
  validateAgentToolInputSchema,
  validateToolResult,
  createToolResultDiagnostic,
  errorDiagnostic,
  warningDiagnostic,
  infoDiagnostic,
  isToolResultFamily,
  isMutationProposalResult,
  isTimelineEditableResult,
  toolResultToTimelineProposalInput,
  toolResultToTimelineProposalInputs,
  SUPPORTED_TOOL_RESULT_FAMILIES,
} from '@/tools/video-editor/runtime/agentToolContracts';
import type {
  AgentToolInputSchema,
  ToolMutationProposalResult,
  ToolResultFamily,
  ToolResultDiagnostic,
  TimelinePatch,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTimelinePatch(overrides?: Partial<TimelinePatch>): TimelinePatch {
  return {
    version: 1,
    operations: [
      {
        op: 'clip.move',
        target: 'clip-1',
        payload: { trackId: 'track-a', time: 0 },
      },
    ],
    source: 'test',
    ...overrides,
  };
}

function makeMutationProposalResult(
  overrides?: Partial<ToolMutationProposalResult>,
): ToolMutationProposalResult {
  return {
    family: 'mutation/proposal',
    patches: [makeTimelinePatch()],
    rationale: 'Test proposal',
    ...overrides,
  };
}

/** Collect diagnostic codes from an array of diagnostics. */
function codes(diagnostics: ToolResultDiagnostic[]): string[] {
  return diagnostics.map((d) => d.code);
}

/** Collect diagnostic severities from an array of diagnostics. */
function severities(
  diagnostics: ToolResultDiagnostic[],
): ToolResultDiagnostic['severity'][] {
  return diagnostics.map((d) => d.severity);
}

/** Find first diagnostic matching a code. */
function findDiag(
  diagnostics: ToolResultDiagnostic[],
  code: string,
): ToolResultDiagnostic | undefined {
  return diagnostics.find((d) => d.code === code);
}

// ---------------------------------------------------------------------------
// validateAgentToolInputSchema — supported StandardSchema subsets
// ---------------------------------------------------------------------------

describe('validateAgentToolInputSchema — valid schemas', () => {
  it('accepts undefined (absent schema)', () => {
    const diags = validateAgentToolInputSchema(undefined);
    expect(diags).toEqual([]);
  });

  it('accepts null (absent schema)', () => {
    const diags = validateAgentToolInputSchema(null);
    expect(diags).toEqual([]);
  });

  it('accepts a minimal object schema', () => {
    const diags = validateAgentToolInputSchema({ type: 'object' });
    expect(diags).toEqual([]);
  });

  it('accepts a schema with title and description', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      title: 'My Tool',
      description: 'Does things',
    });
    expect(diags).toEqual([]);
  });

  it('accepts a schema with string properties', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        name: { type: 'string', title: 'Name' },
        count: { type: 'number', default: 0 },
        enabled: { type: 'boolean', default: false },
      },
      required: ['name'],
    });
    expect(diags).toEqual([]);
  });

  it('accepts a schema with enum properties on string type', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        mode: {
          type: 'string',
          enum: ['fast', 'balanced', 'quality'],
          default: 'balanced',
        },
      },
    });
    expect(diags).toEqual([]);
  });

  it('accepts a schema with nested object properties (depth 1)', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        config: {
          type: 'object',
          title: 'Configuration',
          properties: {
            debug: { type: 'boolean', default: false },
            threshold: { type: 'number', default: 0.5 },
          },
          required: ['threshold'],
        },
      },
    });
    expect(diags).toEqual([]);
  });

  it('accepts a schema with all valid property types', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        a: { type: 'string' },
        b: { type: 'number' },
        c: { type: 'boolean' },
        d: { type: 'object', properties: { x: { type: 'string' } } },
      },
    });
    expect(diags).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// validateAgentToolInputSchema — unsupported / invalid subsets
// ---------------------------------------------------------------------------

describe('validateAgentToolInputSchema — invalid schemas', () => {
  it('rejects non-object schemas', () => {
    const diags = validateAgentToolInputSchema('not-an-object');
    expect(diags).toHaveLength(1);
    expect(codes(diags)).toContain('agent-tool/invalid-input-schema');
    expect(severities(diags)).toContain('error');
  });

  it('rejects a schema with non-object type', () => {
    const diags = validateAgentToolInputSchema({ type: 'array' });
    expect(codes(diags)).toContain('agent-tool/invalid-schema-type');
    expect(severities(diags)).toContain('error');
  });

  it('warns on non-string schema title', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      title: 123 as unknown as string,
    });
    expect(codes(diags)).toContain('agent-tool/invalid-schema-title');
    expect(severities(diags)).toContain('warning');
  });

  it('warns on non-string schema description', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      description: true as unknown as string,
    });
    expect(codes(diags)).toContain('agent-tool/invalid-schema-description');
    expect(severities(diags)).toContain('warning');
  });

  it('rejects non-object properties field', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: 'bad' as unknown as Record<string, unknown>,
    });
    expect(codes(diags)).toContain('agent-tool/invalid-schema-properties');
    expect(severities(diags)).toContain('error');
  });

  it('rejects invalid property type', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        badProp: { type: 'invalid-type' as any },
      },
    });
    expect(codes(diags)).toContain('agent-tool/invalid-property-type');
    expect(severities(diags)).toContain('error');
  });

  it('rejects a non-object property value', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        badProp: 'not-an-object' as any,
      },
    });
    expect(codes(diags)).toContain('agent-tool/invalid-input-property');
  });

  it('rejects excessive nesting depth (> 2)', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        level1: {
          type: 'object',
          properties: {
            level2: {
              type: 'object',
              properties: {
                tooDeep: { type: 'string' },
              },
            },
          },
        },
      },
    });
    expect(codes(diags)).toContain('agent-tool/max-schema-depth-exceeded');
  });

  it('warns on enum on non-string type', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        count: {
          type: 'number',
          enum: [1, 2, 3] as unknown as string[],
        },
      },
    });
    expect(codes(diags)).toContain('agent-tool/enum-on-non-string');
    expect(severities(diags)).toContain('warning');
  });

  it('rejects enum with non-string values', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        mode: {
          type: 'string',
          enum: [1, 2, 3] as unknown as string[],
        },
      },
    });
    expect(codes(diags)).toContain('agent-tool/invalid-enum-values');
    expect(severities(diags)).toContain('error');
  });

  it('warns on default type mismatch (string schema, number default)', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        name: { type: 'string', default: 42 as unknown as string },
      },
    });
    const d = findDiag(diags, 'agent-tool/default-type-mismatch');
    expect(d).toBeDefined();
    expect(d!.severity).toBe('warning');
  });

  it('warns on default type mismatch (number schema, string default)', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        count: { type: 'number', default: 'zero' as unknown as number },
      },
    });
    const d = findDiag(diags, 'agent-tool/default-type-mismatch');
    expect(d).toBeDefined();
  });

  it('warns on default type mismatch (boolean schema, string default)', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        flag: { type: 'boolean', default: 'yes' as unknown as boolean },
      },
    });
    const d = findDiag(diags, 'agent-tool/default-type-mismatch');
    expect(d).toBeDefined();
  });

  it('rejects invalid required array (non-array)', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: { name: { type: 'string' } },
      required: 'name' as unknown as string[],
    });
    expect(codes(diags)).toContain('agent-tool/invalid-required-array');
  });

  it('rejects required items that are not strings', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: { name: { type: 'string' } },
      required: [123] as unknown as string[],
    });
    expect(codes(diags)).toContain('agent-tool/invalid-required-item');
  });

  it('warns on required field not in properties', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: { name: { type: 'string' } },
      required: ['missingField'],
    });
    expect(codes(diags)).toContain('agent-tool/required-field-not-in-properties');
  });

  it('warns on properties on non-object type', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        name: {
          type: 'string',
          properties: { sub: { type: 'string' } } as any,
        },
      },
    });
    expect(codes(diags)).toContain('agent-tool/properties-on-non-object');
  });

  it('warns on required on non-object type', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        name: {
          type: 'string',
          required: ['sub'] as any,
        },
      },
    });
    expect(codes(diags)).toContain('agent-tool/required-on-non-object');
  });

  it('warns on non-string property title/description', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        name: {
          type: 'string',
          title: 42 as unknown as string,
          description: true as unknown as string,
        },
      },
    });
    expect(codes(diags)).toContain('agent-tool/invalid-property-title');
    expect(codes(diags)).toContain('agent-tool/invalid-property-description');
  });

  it('rejects invalid nested properties (non-object)', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        config: {
          type: 'object',
          properties: 'bad' as any,
        },
      },
    });
    expect(codes(diags)).toContain('agent-tool/invalid-nested-properties');
  });

  it('rejects invalid nested required (non-string[])', () => {
    const diags = validateAgentToolInputSchema({
      type: 'object',
      properties: {
        config: {
          type: 'object',
          properties: { x: { type: 'string' } },
          required: 42 as any,
        },
      },
    });
    expect(codes(diags)).toContain('agent-tool/invalid-nested-required');
  });

  it('returns multiple diagnostics for a schema with many issues', () => {
    const diags = validateAgentToolInputSchema({
      type: 'array',
      properties: 'bad' as any,
      title: 123 as any,
      required: 'bad' as any,
    });
    // Should have at least: invalid-schema-type, invalid-schema-properties,
    // invalid-schema-title, invalid-required-array
    expect(diags.length).toBeGreaterThanOrEqual(3);
    expect(codes(diags)).toContain('agent-tool/invalid-schema-type');
  });
});

// ---------------------------------------------------------------------------
// SUPPORTED_TOOL_RESULT_FAMILIES — constant
// ---------------------------------------------------------------------------

describe('SUPPORTED_TOOL_RESULT_FAMILIES', () => {
  it('contains exactly 7 families', () => {
    expect(SUPPORTED_TOOL_RESULT_FAMILIES).toHaveLength(7);
  });

  it('includes all expected families in order', () => {
    expect(SUPPORTED_TOOL_RESULT_FAMILIES).toEqual([
      'mutation/proposal',
      'generation/session',
      'material/artifact',
      'enrichment/search',
      'export',
      'process',
      'ui/summary',
    ]);
  });

  it('is a readonly const array (TS-level, not runtime-frozen)', () => {
    // `as const` provides TS-level readonly but does not Object.freeze at runtime.
    // The array reference is stable and the contract prohibits mutation at the type level.
    expect(Array.isArray(SUPPORTED_TOOL_RESULT_FAMILIES)).toBe(true);
    expect(SUPPORTED_TOOL_RESULT_FAMILIES).toHaveLength(7);
    // Verify the array contains the expected values in order
    expect([...SUPPORTED_TOOL_RESULT_FAMILIES].sort()).toEqual([
      'enrichment/search',
      'export',
      'generation/session',
      'material/artifact',
      'mutation/proposal',
      'process',
      'ui/summary',
    ]);
  });
});

// ---------------------------------------------------------------------------
// isToolResultFamily — type guard
// ---------------------------------------------------------------------------

describe('isToolResultFamily', () => {
  it.each(SUPPORTED_TOOL_RESULT_FAMILIES)(
    'returns true for %s',
    (family: ToolResultFamily) => {
      expect(isToolResultFamily(family)).toBe(true);
    },
  );

  it('returns false for non-string values', () => {
    expect(isToolResultFamily(42)).toBe(false);
    expect(isToolResultFamily(null)).toBe(false);
    expect(isToolResultFamily(undefined)).toBe(false);
    expect(isToolResultFamily({})).toBe(false);
  });

  it('returns false for unknown family strings', () => {
    expect(isToolResultFamily('custom/unknown')).toBe(false);
    expect(isToolResultFamily('mutation')).toBe(false);
    expect(isToolResultFamily('')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// validateToolResult — accepted grouped families
// ---------------------------------------------------------------------------

describe('validateToolResult — accepted families', () => {
  it('accepts a valid mutation/proposal result', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: [makeTimelinePatch()],
    });
    expect(diags).toEqual([]);
  });

  it('accepts a mutation/proposal result with optional fields', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: [makeTimelinePatch()],
      rationale: 'Change tempo',
      affectedObjectIds: ['clip-1', 'clip-2'],
      sourceRefs: [
        { sourceId: 'src-1', outputId: 'out-1' },
        { sourceId: 'src-2', outputId: 'out-2' },
      ],
    });
    expect(diags).toEqual([]);
  });

  it('accepts a valid generation/session result', () => {
    const diags = validateToolResult({
      family: 'generation/session',
      session: { id: 'gen-1', cancel: () => {} },
    });
    expect(diags).toEqual([]);
  });

  it('accepts a valid material/artifact result', () => {
    const diags = validateToolResult({
      family: 'material/artifact',
      refs: [{ ref: 'asset-1', kind: 'asset', label: 'My Asset' }],
    });
    expect(diags).toEqual([]);
  });

  it('accepts a valid enrichment/search result with suggestions', () => {
    const diags = validateToolResult({
      family: 'enrichment/search',
      suggestions: { 'key-1': { mood: 'dark' } },
    });
    expect(diags).toEqual([]);
  });

  it('accepts a valid enrichment/search result with matches', () => {
    const diags = validateToolResult({
      family: 'enrichment/search',
      matches: [{ key: 'asset-1', score: 0.95 }],
    });
    expect(diags).toEqual([]);
  });

  it('accepts a valid export result', () => {
    const diags = validateToolResult({
      family: 'export',
      findings: [{ capability: 'h.265' }],
    });
    expect(diags).toEqual([]);
  });

  it('accepts a valid process result', () => {
    const diags = validateToolResult({
      family: 'process',
      diagnostics: [{ severity: 'info', code: 'agent-tool/ok', message: 'Done' }],
    });
    expect(diags).toEqual([]);
  });

  it('accepts a valid ui/summary result', () => {
    const diags = validateToolResult({
      family: 'ui/summary',
      summary: 'Analysis complete',
    });
    expect(diags).toEqual([]);
  });

  it('accepts a ui/summary result with detail', () => {
    const diags = validateToolResult({
      family: 'ui/summary',
      summary: 'Analysis complete',
      detail: { wordCount: 150 },
    });
    expect(diags).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// validateToolResult — invalid / one-off shapes
// ---------------------------------------------------------------------------

describe('validateToolResult — invalid shapes', () => {
  it('rejects a non-object result', () => {
    const diags = validateToolResult('not-an-object');
    expect(codes(diags)).toContain('agent-tool/tool-result-not-object');
  });

  it('rejects a null result', () => {
    const diags = validateToolResult(null);
    expect(codes(diags)).toContain('agent-tool/tool-result-not-object');
  });

  it('rejects result without family discriminator', () => {
    const diags = validateToolResult({ patches: [] });
    expect(codes(diags)).toContain('agent-tool/missing-result-family');
  });

  it('rejects result with unsupported family', () => {
    const diags = validateToolResult({
      family: 'custom/one-off',
      data: 'test',
    });
    expect(codes(diags)).toContain('agent-tool/unsupported-result-family');
  });

  it('rejects result with mis-cased family', () => {
    const diags = validateToolResult({
      family: 'Mutation/Proposal',
      patches: [makeTimelinePatch()],
    });
    expect(codes(diags)).toContain('agent-tool/unsupported-result-family');
  });

  // mutation/proposal family errors
  it('errors on mutation/proposal result without patches', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
    });
    expect(codes(diags)).toContain('agent-tool/mutation-missing-patches');
  });

  it('warns on mutation/proposal result with empty patches', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: [],
    });
    expect(codes(diags)).toContain('agent-tool/mutation-empty-patches');
  });

  it('errors on invalid patch item', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: ['not-a-patch'],
    });
    expect(codes(diags)).toContain('agent-tool/invalid-patch-item');
  });

  it('warns on patch without operations', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: [{ version: 1 }],
    });
    expect(codes(diags)).toContain('agent-tool/patch-missing-operations');
  });

  it('warns on invalid versionHint', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: [{ version: 1, operations: [], versionHint: 'v1' }],
    });
    expect(codes(diags)).toContain('agent-tool/invalid-version-hint');
  });

  it('warns on non-string rationale in mutation/proposal', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: [makeTimelinePatch()],
      rationale: 42,
    });
    expect(codes(diags)).toContain('agent-tool/invalid-rationale-type');
  });

  it('warns on non-array affectedObjectIds', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: [makeTimelinePatch()],
      affectedObjectIds: 'clip-1',
    });
    expect(codes(diags)).toContain('agent-tool/invalid-affected-ids');
  });

  it('warns on non-array sourceRefs', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: [makeTimelinePatch()],
      sourceRefs: 'bad',
    });
    expect(codes(diags)).toContain('agent-tool/invalid-source-refs');
  });

  // generation/session family errors
  it('errors on generation/session result without session', () => {
    const diags = validateToolResult({
      family: 'generation/session',
    });
    expect(codes(diags)).toContain('agent-tool/generation-missing-session');
  });

  it('errors on generation/session with session missing id', () => {
    const diags = validateToolResult({
      family: 'generation/session',
      session: {},
    });
    expect(codes(diags)).toContain('agent-tool/session-missing-id');
  });

  it('warns on generation/session missing cancel method', () => {
    const diags = validateToolResult({
      family: 'generation/session',
      session: { id: 'gen-1' },
    });
    expect(codes(diags)).toContain('agent-tool/session-missing-cancel');
  });

  // material/artifact family errors
  it('errors on material/artifact result without refs', () => {
    const diags = validateToolResult({
      family: 'material/artifact',
    });
    expect(codes(diags)).toContain('agent-tool/material-missing-refs');
  });

  it('warns on material/artifact result with empty refs', () => {
    const diags = validateToolResult({
      family: 'material/artifact',
      refs: [],
    });
    expect(codes(diags)).toContain('agent-tool/material-empty-refs');
  });

  // enrichment/search family warnings
  it('warns on enrichment/search with neither suggestions nor matches', () => {
    const diags = validateToolResult({
      family: 'enrichment/search',
    });
    expect(codes(diags)).toContain('agent-tool/enrichment-no-data');
  });

  // export family warnings
  it('warns on export with non-array findings', () => {
    const diags = validateToolResult({
      family: 'export',
      findings: 'bad',
    });
    expect(codes(diags)).toContain('agent-tool/invalid-findings-type');
  });

  // process family errors
  it('errors on process result without diagnostics', () => {
    const diags = validateToolResult({
      family: 'process',
    });
    expect(codes(diags)).toContain('agent-tool/process-missing-diagnostics');
  });

  it('errors on process result with empty diagnostics', () => {
    const diags = validateToolResult({
      family: 'process',
      diagnostics: [],
    });
    expect(codes(diags)).toContain('agent-tool/process-missing-diagnostics');
  });

  // ui/summary family errors
  it('errors on ui/summary result without summary', () => {
    const diags = validateToolResult({
      family: 'ui/summary',
    });
    expect(codes(diags)).toContain('agent-tool/summary-missing-text');
  });

  it('warns on ui/summary with non-object detail', () => {
    const diags = validateToolResult({
      family: 'ui/summary',
      summary: 'OK',
      detail: 'not-an-object',
    });
    expect(codes(diags)).toContain('agent-tool/invalid-detail-type');
  });
});

// ---------------------------------------------------------------------------
// validateToolResult — diagnostics array validation (cross-family)
// ---------------------------------------------------------------------------

describe('validateToolResult — diagnostics field validation', () => {
  it('warns on non-array diagnostics field', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: [makeTimelinePatch()],
      diagnostics: 'bad',
    });
    expect(codes(diags)).toContain('agent-tool/invalid-diagnostics-array');
  });

  it('warns on diagnostics containing non-object items', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: [makeTimelinePatch()],
      diagnostics: ['not-an-object'],
    });
    expect(codes(diags)).toContain('agent-tool/invalid-diagnostic-item');
  });

  it('warns on diagnostic missing severity', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: [makeTimelinePatch()],
      diagnostics: [{ code: 'agent-tool/x', message: 'msg' }],
    });
    expect(codes(diags)).toContain('agent-tool/diagnostic-missing-severity');
  });

  it('warns on diagnostic missing code', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: [makeTimelinePatch()],
      diagnostics: [{ severity: 'error', message: 'msg' }],
    });
    expect(codes(diags)).toContain('agent-tool/diagnostic-missing-code');
  });

  it('warns on diagnostic missing message', () => {
    const diags = validateToolResult({
      family: 'mutation/proposal',
      patches: [makeTimelinePatch()],
      diagnostics: [{ severity: 'error', code: 'agent-tool/x' }],
    });
    expect(codes(diags)).toContain('agent-tool/diagnostic-missing-message');
  });
});

// ---------------------------------------------------------------------------
// Diagnostic helpers
// ---------------------------------------------------------------------------

describe('createToolResultDiagnostic', () => {
  it('creates an error diagnostic with auto-prefix', () => {
    const d = createToolResultDiagnostic('error', 'bad-input', 'Bad input');
    expect(d.severity).toBe('error');
    expect(d.code).toBe('agent-tool/bad-input');
    expect(d.message).toBe('Bad input');
  });

  it('preserves existing agent-tool/ prefix', () => {
    const d = createToolResultDiagnostic(
      'warning',
      'agent-tool/already-prefixed',
      'Msg',
    );
    expect(d.code).toBe('agent-tool/already-prefixed');
  });

  it('attaches detail when provided', () => {
    const d = createToolResultDiagnostic('info', 'test', 'Msg', {
      key: 'value',
      num: 42,
    });
    expect((d as Record<string, unknown>).detail).toEqual({
      key: 'value',
      num: 42,
    });
  });

  it('does not attach detail when omitted', () => {
    const d = createToolResultDiagnostic('error', 'test', 'Msg');
    expect((d as Record<string, unknown>).detail).toBeUndefined();
  });
});

describe('errorDiagnostic convenience', () => {
  it('creates an error-level diagnostic', () => {
    const d = errorDiagnostic('e1', 'Error message');
    expect(d.severity).toBe('error');
    expect(d.code).toBe('agent-tool/e1');
    expect(d.message).toBe('Error message');
  });

  it('includes detail', () => {
    const d = errorDiagnostic('e2', 'Msg', { a: 1 });
    expect((d as Record<string, unknown>).detail).toEqual({ a: 1 });
  });
});

describe('warningDiagnostic convenience', () => {
  it('creates a warning-level diagnostic', () => {
    const d = warningDiagnostic('w1', 'Warning message');
    expect(d.severity).toBe('warning');
    expect(d.code).toBe('agent-tool/w1');
  });
});

describe('infoDiagnostic convenience', () => {
  it('creates an info-level diagnostic', () => {
    const d = infoDiagnostic('i1', 'Info message');
    expect(d.severity).toBe('info');
    expect(d.code).toBe('agent-tool/i1');
  });
});

// ---------------------------------------------------------------------------
// isMutationProposalResult / isTimelineEditableResult — type guards
// ---------------------------------------------------------------------------

describe('isMutationProposalResult', () => {
  it('returns true for valid mutation/proposal result', () => {
    const result = makeMutationProposalResult();
    expect(isMutationProposalResult(result)).toBe(true);
  });

  it('returns false for non-object', () => {
    expect(isMutationProposalResult(null)).toBe(false);
    expect(isMutationProposalResult('string')).toBe(false);
  });

  it('returns false for wrong family', () => {
    expect(
      isMutationProposalResult({ family: 'process', diagnostics: [] }),
    ).toBe(false);
  });

  it('returns false for missing patches', () => {
    expect(
      isMutationProposalResult({ family: 'mutation/proposal' }),
    ).toBe(false);
  });

  it('returns true even with empty patches array', () => {
    expect(
      isMutationProposalResult({
        family: 'mutation/proposal',
        patches: [],
      }),
    ).toBe(true);
  });
});

describe('isTimelineEditableResult', () => {
  it('aliases isMutationProposalResult', () => {
    const result = makeMutationProposalResult();
    expect(isTimelineEditableResult(result)).toBe(true);
    expect(isTimelineEditableResult(null)).toBe(false);
    expect(
      isTimelineEditableResult({ family: 'ui/summary', summary: 'x' }),
    ).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// toolResultToTimelineProposalInput — conversion metadata
// ---------------------------------------------------------------------------

describe('toolResultToTimelineProposalInput', () => {
  it('converts a basic mutation result to a timeline proposal input', () => {
    const result = makeMutationProposalResult({
      rationale: 'Fix clip timing',
    });
    const input = toolResultToTimelineProposalInput(result, 5, 'ext1.tool1');
    expect(input.source).toBe('ext1.tool1');
    expect(input.baseVersion).toBe(5);
    expect(input.rationale).toBe('Fix clip timing');
    expect(input.patch).toBe(result.patches[0]);
  });

  it('preserves base version even when stale', () => {
    // Base version can be older than current — the host handles staleness
    const result = makeMutationProposalResult();
    const input = toolResultToTimelineProposalInput(result, 0, 'test.tool');
    expect(input.baseVersion).toBe(0);
  });

  it('preserves base version when version is very large', () => {
    const result = makeMutationProposalResult();
    const input = toolResultToTimelineProposalInput(
      result,
      Number.MAX_SAFE_INTEGER,
      'test.tool',
    );
    expect(input.baseVersion).toBe(Number.MAX_SAFE_INTEGER);
  });

  it('incorporates affectedObjectIds into rationale', () => {
    const result = makeMutationProposalResult({
      rationale: 'Adjust brightness',
      affectedObjectIds: ['clip-a', 'clip-b', 'clip-c'],
    });
    const input = toolResultToTimelineProposalInput(result, 1, 'ext.tool');
    expect(input.rationale).toContain('Adjust brightness');
    expect(input.rationale).toContain('Affected objects: clip-a, clip-b, clip-c');
  });

  it('truncates affectedObjectIds at 5 in rationale', () => {
    const result = makeMutationProposalResult({
      affectedObjectIds: ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
    });
    const input = toolResultToTimelineProposalInput(result, 1, 'ext.tool');
    expect(input.rationale).toContain('a, b, c, d, e');
    expect(input.rationale).toContain('and 2 more');
  });

  it('incorporates sourceRefs into rationale', () => {
    const result = makeMutationProposalResult({
      sourceRefs: [
        { sourceId: 'src-a', outputId: 'out-a' },
        { sourceId: 'src-b', outputId: 'out-b' },
      ],
    });
    const input = toolResultToTimelineProposalInput(result, 1, 'ext.tool');
    expect(input.rationale).toContain('src-a → out-a');
    expect(input.rationale).toContain('src-b → out-b');
    expect(input.rationale).toContain('Source→Output refs');
  });

  it('generates default rationale when none provided', () => {
    const result = makeMutationProposalResult();
    delete (result as Record<string, unknown>).rationale;
    const input = toolResultToTimelineProposalInput(result, 1, 'myExt.myTool');
    expect(input.rationale).toContain('Proposed by agent tool: myExt.myTool');
  });

  it('throws on non-mutation/proposal result', () => {
    expect(() =>
      toolResultToTimelineProposalInput(
        { family: 'process', diagnostics: [] } as any,
        1,
        'test',
      ),
    ).toThrow('Cannot convert non-mutation/proposal result');
  });

  it('throws on empty patches', () => {
    expect(() =>
      toolResultToTimelineProposalInput(
        { family: 'mutation/proposal', patches: [] } as any,
        1,
        'test',
      ),
    ).toThrow('empty patches');
  });

  it('uses the first patch from the result', () => {
    const patch0 = makeTimelinePatch({ version: 10 });
    const patch1 = makeTimelinePatch({ version: 20 });
    const result = makeMutationProposalResult({
      patches: [patch0, patch1],
    });
    const input = toolResultToTimelineProposalInput(result, 3, 'src');
    expect(input.patch).toBe(patch0);
  });

  it('includes both affectedObjectIds and sourceRefs in rationale', () => {
    const result = makeMutationProposalResult({
      rationale: 'Multi-context change',
      affectedObjectIds: ['clip-1'],
      sourceRefs: [{ sourceId: 's1', outputId: 'o1' }],
    });
    const input = toolResultToTimelineProposalInput(result, 1, 'ext.t');
    expect(input.rationale).toContain('Multi-context change');
    expect(input.rationale).toContain('Affected objects');
    expect(input.rationale).toContain('Source→Output refs');
  });

  it('carries patch operations through unchanged', () => {
    const patch = makeTimelinePatch({
      operations: [
        { op: 'clip.move', target: 'c1', payload: { trackId: 't1', time: 10 } },
        { op: 'clip.trim', target: 'c2', payload: { start: 0, end: 30 } },
      ],
    });
    const result = makeMutationProposalResult({ patches: [patch] });
    const input = toolResultToTimelineProposalInput(result, 7, 'ext.tool');
    expect(input.patch.operations).toHaveLength(2);
    expect(input.patch.operations[0].op).toBe('clip.move');
    expect(input.patch.operations[1].op).toBe('clip.trim');
  });
});

// ---------------------------------------------------------------------------
// toolResultToTimelineProposalInputs — multi-patch conversion
// ---------------------------------------------------------------------------

describe('toolResultToTimelineProposalInputs', () => {
  it('converts single-patch result to single-element array', () => {
    const result = makeMutationProposalResult();
    const inputs = toolResultToTimelineProposalInputs(result, 1, 'src');
    expect(inputs).toHaveLength(1);
    expect(inputs[0].source).toBe('src');
  });

  it('converts multi-patch result to multi-element array', () => {
    const patch0 = makeTimelinePatch({ version: 1 });
    const patch1 = makeTimelinePatch({ version: 2 });
    const result = makeMutationProposalResult({
      patches: [patch0, patch1],
    });
    const inputs = toolResultToTimelineProposalInputs(result, 3, 'ext.tool');
    expect(inputs).toHaveLength(2);
    expect(inputs[0].source).toBe('ext.tool#patch1');
    expect(inputs[1].source).toBe('ext.tool#patch2');
    expect(inputs[0].patch).toBe(patch0);
    expect(inputs[1].patch).toBe(patch1);
    expect(inputs[0].baseVersion).toBe(3);
    expect(inputs[1].baseVersion).toBe(3);
  });

  it('each patch proposal carries the same baseVersion', () => {
    const result = makeMutationProposalResult({
      patches: [makeTimelinePatch(), makeTimelinePatch()],
    });
    const inputs = toolResultToTimelineProposalInputs(result, 42, 's');
    expect(inputs).toHaveLength(2);
    expect(inputs[0].baseVersion).toBe(42);
    expect(inputs[1].baseVersion).toBe(42);
  });

  it('each rationale includes patch index for multi-patch results', () => {
    const result = makeMutationProposalResult({
      patches: [makeTimelinePatch(), makeTimelinePatch(), makeTimelinePatch()],
      rationale: 'Bulk update',
    });
    const inputs = toolResultToTimelineProposalInputs(result, 1, 's');
    expect(inputs[0].rationale).toContain('(patch 1 of 3)');
    expect(inputs[1].rationale).toContain('(patch 2 of 3)');
    expect(inputs[2].rationale).toContain('(patch 3 of 3)');
  });

  it('does not append patch index for single-patch results', () => {
    const result = makeMutationProposalResult({ patches: [makeTimelinePatch()] });
    const inputs = toolResultToTimelineProposalInputs(result, 1, 's');
    expect(inputs[0].rationale).not.toContain('(patch');
  });

  it('carries affectedObjectIds across all proposals', () => {
    const result = makeMutationProposalResult({
      patches: [makeTimelinePatch(), makeTimelinePatch()],
      affectedObjectIds: ['clip-x', 'clip-y'],
    });
    const inputs = toolResultToTimelineProposalInputs(result, 1, 's');
    expect(inputs).toHaveLength(2);
    expect(inputs[0].rationale).toContain('Affected objects');
    expect(inputs[1].rationale).toContain('Affected objects');
  });

  it('carries sourceRefs across all proposals', () => {
    const result = makeMutationProposalResult({
      patches: [makeTimelinePatch(), makeTimelinePatch()],
      sourceRefs: [{ sourceId: 'a', outputId: 'b' }],
    });
    const inputs = toolResultToTimelineProposalInputs(result, 1, 's');
    expect(inputs).toHaveLength(2);
    expect(inputs[0].rationale).toContain('Source→Output refs');
    expect(inputs[1].rationale).toContain('Source→Output refs');
  });

  it('throws on non-mutation/proposal result', () => {
    expect(() =>
      toolResultToTimelineProposalInputs(
        { family: 'export', findings: [] } as any,
        1,
        'test',
      ),
    ).toThrow('Cannot convert non-mutation/proposal result');
  });

  it('throws on empty patches', () => {
    expect(() =>
      toolResultToTimelineProposalInputs(
        { family: 'mutation/proposal', patches: [] } as any,
        1,
        'test',
      ),
    ).toThrow('empty patches');
  });
});

// ---------------------------------------------------------------------------
// Stale / base-version diagnostic inputs (edge cases for contract)
// ---------------------------------------------------------------------------

describe('toolResultToTimelineProposalInput — stale/base-version edges', () => {
  it('handles negative baseVersion without rejection (host validates)', () => {
    // The contract function doesn't validate version semantics;
    // it passes the value through. The host (ProposalRuntime) handles staleness.
    const result = makeMutationProposalResult();
    const input = toolResultToTimelineProposalInput(result, -1, 'test');
    expect(input.baseVersion).toBe(-1);
  });

  it('handles version 0 (initial state)', () => {
    const result = makeMutationProposalResult();
    const input = toolResultToTimelineProposalInput(result, 0, 'test');
    expect(input.baseVersion).toBe(0);
  });

  it('handles result with undefined rationale (uses default)', () => {
    const result = makeMutationProposalResult();
    delete (result as Record<string, unknown>).rationale;
    const input = toolResultToTimelineProposalInput(result, 7, 'agent.tool');
    expect(input.rationale).toBe('Proposed by agent tool: agent.tool');
  });

  it('handles result with empty affectedObjectIds array', () => {
    const result = makeMutationProposalResult({
      affectedObjectIds: [],
      rationale: 'No specific objects',
    });
    const input = toolResultToTimelineProposalInput(result, 1, 'test');
    // Empty array should not append affected objects line
    expect(input.rationale).not.toContain('Affected objects');
  });

  it('handles result with empty sourceRefs array', () => {
    const result = makeMutationProposalResult({
      sourceRefs: [],
      rationale: 'No refs',
    });
    const input = toolResultToTimelineProposalInput(result, 1, 'test');
    expect(input.rationale).not.toContain('Source→Output refs');
  });

  it('preserves source identifier exactly', () => {
    const result = makeMutationProposalResult();
    const input = toolResultToTimelineProposalInput(
      result,
      1,
      'com.example.ext.tool-1',
    );
    expect(input.source).toBe('com.example.ext.tool-1');
  });

  it('handles patch with source already set', () => {
    const patch = makeTimelinePatch({ source: 'original-source' });
    const result = makeMutationProposalResult({ patches: [patch] });
    const input = toolResultToTimelineProposalInput(result, 1, 'agent.source');
    // The proposal source is separate from the patch's source metadata
    expect(input.source).toBe('agent.source');
    expect(input.patch.source).toBe('original-source');
  });
});
