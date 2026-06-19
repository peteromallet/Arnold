/**
 * Tests for transition validation and repair utilities.
 * Covers T13: pure transition validation and repair.
 */
import { describe, expect, it } from 'vitest';
import {
  validateTransitionObject,
  validateClipTransition,
  repairClipTransition,
  generateTransitionDiagnostics,
  TransitionDiagnosticCodes,
  type TransitionValidationResult,
  type TransitionRepairPatch,
} from '@/tools/video-editor/transitions/validation.ts';
import { createTransitionSnapshot } from '@/tools/video-editor/transitions/catalog.ts';
import {
  createTransitionRegistry,
  type TransitionRegistryRecord,
  type TransitionRegistrySnapshot,
} from '@/tools/video-editor/transitions/registry/index.ts';
import type { ClipTransition, ParameterSchema } from '@/tools/video-editor/types/index.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRecord(
  transitionId: string,
  overrides?: Partial<TransitionRegistryRecord>,
): TransitionRegistryRecord {
  return {
    transitionId,
    contributionId: `test:${transitionId}`,
    renderer: () => ({ opacity: 1 }),
    provenance: 'built-in',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: [
        {
          route: 'preview',
          status: 'supported',
          determinism: 'deterministic',
        },
      ],
    },
    status: 'active',
    ...overrides,
  };
}

function makeRegistrySnapshot(
  records: TransitionRegistryRecord[],
): TransitionRegistrySnapshot {
  const registry = createTransitionRegistry();
  for (const record of records) {
    registry.register(record);
  }
  return createTransitionSnapshot(registry.getSnapshot());
}

function makeClipTransition(overrides?: Partial<ClipTransition>): ClipTransition {
  return {
    type: 'crossfade',
    duration: 0.5,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// validateTransitionObject
// ---------------------------------------------------------------------------

describe('validateTransitionObject', () => {
  it('flags null transition as invalid', () => {
    const result = validateTransitionObject(null);
    expect(result.isValid).toBe(false);
    expect(result.isResolvable).toBe(false);
    expect(result.resolvedType).toBeUndefined();
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.MISSING_TRANSITION_OBJECT,
    );
  });

  it('flags undefined transition as invalid', () => {
    const result = validateTransitionObject(undefined);
    expect(result.isValid).toBe(false);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.MISSING_TRANSITION_OBJECT,
    );
  });

  it('flags non-object values as invalid (string)', () => {
    const result = validateTransitionObject('crossfade');
    expect(result.isValid).toBe(false);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.INVALID_TYPE,
    );
  });

  it('flags non-object values as invalid (number)', () => {
    const result = validateTransitionObject(42);
    expect(result.isValid).toBe(false);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.INVALID_TYPE,
    );
  });

  it('flags arrays as invalid', () => {
    const result = validateTransitionObject([{ type: 'crossfade' }]);
    expect(result.isValid).toBe(false);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.INVALID_TYPE,
    );
  });

  it('flags object missing "type" field', () => {
    const result = validateTransitionObject({ duration: 0.5 });
    expect(result.isValid).toBe(false);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.MISSING_TYPE,
    );
    expect(result.diagnostics[0].detail?.keys).toEqual(['duration']);
  });

  it('flags object with null type', () => {
    const result = validateTransitionObject({ type: null, duration: 0.5 });
    expect(result.isValid).toBe(false);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.INVALID_TYPE,
    );
  });

  it('flags object with numeric type', () => {
    const result = validateTransitionObject({ type: 123, duration: 0.5 });
    expect(result.isValid).toBe(false);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.INVALID_TYPE,
    );
  });

  it('flags object with empty string type', () => {
    const result = validateTransitionObject({ type: '', duration: 0.5 });
    expect(result.isValid).toBe(false);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.INVALID_TYPE,
    );
  });

  it('flags object with whitespace-only type', () => {
    const result = validateTransitionObject({ type: '   ', duration: 0.5 });
    expect(result.isValid).toBe(false);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.INVALID_TYPE,
    );
  });

  it('accepts object with boolean type (treated as invalid string)', () => {
    const result = validateTransitionObject({ type: true, duration: 0.5 });
    expect(result.isValid).toBe(false);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.INVALID_TYPE,
    );
  });

  it('accepts valid transition object', () => {
    const result = validateTransitionObject({ type: 'crossfade', duration: 0.5 });
    expect(result.isValid).toBe(true);
    expect(result.isResolvable).toBe(true);
    expect(result.resolvedType).toBe('crossfade');
    expect(result.diagnostics[0].code).toBe(TransitionDiagnosticCodes.VALID);
  });

  it('accepts object with only type field (no duration)', () => {
    const result = validateTransitionObject({ type: 'wipe' });
    expect(result.isValid).toBe(true);
    expect(result.resolvedType).toBe('wipe');
  });

  it('preserves diagnostics as frozen', () => {
    const result = validateTransitionObject({ type: 'crossfade', duration: 0.5 });
    expect(Object.isFrozen(result.diagnostics)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// validateClipTransition
// ---------------------------------------------------------------------------

describe('validateClipTransition', () => {
  it('validates a built-in transition as resolvable and valid', () => {
    const result = validateClipTransition(makeClipTransition({ type: 'crossfade' }));
    expect(result.isValid).toBe(true);
    expect(result.isResolvable).toBe(true);
    expect(result.resolvedType).toBe('crossfade');
  });

  it('validates built-in wipe transition', () => {
    const result = validateClipTransition(makeClipTransition({ type: 'wipe' }));
    expect(result.isValid).toBe(true);
    expect(result.isResolvable).toBe(true);
  });

  it('validates built-in slide-push transition', () => {
    const result = validateClipTransition(makeClipTransition({ type: 'slide-push' }));
    expect(result.isValid).toBe(true);
  });

  it('validates built-in zoom-through transition', () => {
    const result = validateClipTransition(makeClipTransition({ type: 'zoom-through' }));
    expect(result.isValid).toBe(true);
  });

  it('flags unresolvable transition types', () => {
    const result = validateClipTransition(
      makeClipTransition({ type: 'nonexistent-transition' }),
    );
    expect(result.isValid).toBe(false);
    expect(result.isResolvable).toBe(false);
    expect(result.resolvedType).toBe('nonexistent-transition');
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.UNRESOLVED_TYPE,
    );
  });

  it('flags null/undefined transition via structural validation', () => {
    const result = validateClipTransition(null);
    expect(result.isValid).toBe(false);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.MISSING_TRANSITION_OBJECT,
    );
  });

  it('validates a contributed transition from registry', () => {
    const registry = makeRegistrySnapshot([
      makeRecord('custom-fx', { provenance: 'bundled-extension' }),
    ]);
    const result = validateClipTransition(
      makeClipTransition({ type: 'custom-fx' }),
      registry,
    );
    expect(result.isValid).toBe(true);
    expect(result.isResolvable).toBe(true);
    expect(result.resolvedType).toBe('custom-fx');
  });

  // -- Removed contributed transitions ---------------------------------------

  it('detects removed contributed transitions', () => {
    // A contributed transition that is NOT a built-in and NOT in the registry.
    // Uses a namespaced ID (containing ':') so the heuristic recognizes it
    // as an extension-contributed transition.
    const result = validateClipTransition(
      makeClipTransition({ type: 'my-ext:removed-fx' }),
    );
    expect(result.isValid).toBe(false);
    expect(result.isResolvable).toBe(false);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.REMOVED_CONTRIBUTED,
    );
    expect(result.diagnostics[0].message).toContain('no longer available');
  });

  it('detects removed contributed transition even with empty registry', () => {
    const emptyRegistry = createTransitionSnapshot();
    const result = validateClipTransition(
      makeClipTransition({ type: 'ext:uninstalled-transition' }),
      emptyRegistry,
    );
    expect(result.isValid).toBe(false);
    expect(result.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.REMOVED_CONTRIBUTED,
    );
  });

  // -- Missing params --------------------------------------------------------

  it('warns when transition has schema but no stored params', () => {
    const schema: ParameterSchema = [
      { name: 'intensity', label: 'Intensity', type: 'number', default: 0.5, min: 0, max: 1 },
    ];
    const registry = makeRegistrySnapshot([
      makeRecord('custom-wipe', { schema, provenance: 'bundled-extension' }),
    ]);

    const result = validateClipTransition(
      makeClipTransition({ type: 'custom-wipe', params: undefined }),
      registry,
    );

    // Should still be valid (renderer can use defaults) but warn about missing params
    expect(result.isValid).toBe(true);
    expect(result.diagnostics.some((d) => d.code === TransitionDiagnosticCodes.MISSING_PARAMS)).toBe(true);
  });

  it('warns when transition has schema but empty params object', () => {
    const schema: ParameterSchema = [
      { name: 'direction', label: 'Direction', type: 'select', options: [{ label: 'Left', value: 'left' }] },
    ];
    const registry = makeRegistrySnapshot([
      makeRecord('directional-wipe', { schema, provenance: 'bundled-extension' }),
    ]);

    const result = validateClipTransition(
      makeClipTransition({ type: 'directional-wipe', params: {} }),
      registry,
    );

    expect(result.isValid).toBe(true);
    expect(result.diagnostics.some((d) => d.code === TransitionDiagnosticCodes.MISSING_PARAMS)).toBe(true);
  });

  it('does NOT warn when transition has schema and non-empty params', () => {
    const schema: ParameterSchema = [
      { name: 'intensity', label: 'Intensity', type: 'number', default: 0.5 },
    ];
    const registry = makeRegistrySnapshot([
      makeRecord('param-transition', { schema, provenance: 'bundled-extension' }),
    ]);

    const result = validateClipTransition(
      makeClipTransition({ type: 'param-transition', params: { intensity: 0.8 } }),
      registry,
    );

    expect(result.isValid).toBe(true);
    expect(result.diagnostics.some((d) => d.code === TransitionDiagnosticCodes.MISSING_PARAMS)).toBe(false);
  });

  // -- Inactive records -----------------------------------------------------

  it('warns when record exists but is in error state', () => {
    const registry = makeRegistrySnapshot([
      makeRecord('broken-transition', {
        status: 'error',
        provenance: 'bundled-extension',
      }),
    ]);

    const result = validateClipTransition(
      makeClipTransition({ type: 'broken-transition' }),
      registry,
    );

    expect(result.isValid).toBe(true); // Still resolvable
    expect(result.diagnostics.some((d) => d.code === TransitionDiagnosticCodes.INACTIVE_RECORD)).toBe(true);
  });

  it('warns when record is inactive', () => {
    const registry = makeRegistrySnapshot([
      makeRecord('disabled-transition', {
        status: 'inactive',
        provenance: 'bundled-extension',
      }),
    ]);

    const result = validateClipTransition(
      makeClipTransition({ type: 'disabled-transition' }),
      registry,
    );

    expect(result.isValid).toBe(true);
    expect(result.diagnostics.some((d) => d.code === TransitionDiagnosticCodes.INACTIVE_RECORD)).toBe(true);
  });

  // -- Frozen diagnostics ----------------------------------------------------

  it('returns frozen diagnostics', () => {
    const result = validateClipTransition(makeClipTransition({ type: 'crossfade' }));
    expect(Object.isFrozen(result.diagnostics)).toBe(true);
  });

  it('returns frozen diagnostics for error cases', () => {
    const result = validateClipTransition(
      makeClipTransition({ type: 'nonexistent' }),
    );
    expect(Object.isFrozen(result.diagnostics)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// repairClipTransition
// ---------------------------------------------------------------------------

describe('repairClipTransition', () => {
  it('returns no-op for valid transitions', () => {
    const patch = repairClipTransition(makeClipTransition({ type: 'crossfade' }));
    expect(patch.action).toBe('no-op');
    expect(patch.transition).toEqual(makeClipTransition({ type: 'crossfade' }));
  });

  it('returns clear-transition for unresolvable types', () => {
    const patch = repairClipTransition(
      makeClipTransition({ type: 'nonexistent-transition' }),
    );
    expect(patch.action).toBe('clear-transition');
    expect(patch.transition).toBeNull();
    expect(patch.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.UNRESOLVED_TYPE,
    );
  });

  it('returns clear-transition for removed contributed transitions', () => {
    const patch = repairClipTransition(
      makeClipTransition({ type: 'ext:old-fx' }),
    );
    expect(patch.action).toBe('clear-transition');
    expect(patch.transition).toBeNull();
    expect(patch.diagnostics[0].code).toBe(
      TransitionDiagnosticCodes.REMOVED_CONTRIBUTED,
    );
  });

  it('returns clear-transition for null transition (explicit no-transition)', () => {
    const patch = repairClipTransition(null);
    expect(patch.action).toBe('clear-transition');
    expect(patch.transition).toBeNull();
  });

  it('returns clear-transition for malformed transition (missing type)', () => {
    // @ts-expect-error - intentionally malformed for testing
    const patch = repairClipTransition({ duration: 0.5 } as ClipTransition);
    expect(patch.action).toBe('clear-transition');
    expect(patch.transition).toBeNull();
    expect(patch.diagnostics[0].code).toBe(TransitionDiagnosticCodes.MISSING_TYPE);
  });

  it('returns clear-transition for empty-string type', () => {
    const patch = repairClipTransition(
      makeClipTransition({ type: '' }),
    );
    expect(patch.action).toBe('clear-transition');
    expect(patch.transition).toBeNull();
  });

  it('returns set-transition when params are missing but schema exists', () => {
    const schema: ParameterSchema = [
      { name: 'intensity', label: 'Intensity', type: 'number', default: 0.5 },
    ];
    const registry = makeRegistrySnapshot([
      makeRecord('schema-transition', { schema, provenance: 'bundled-extension' }),
    ]);

    const patch = repairClipTransition(
      makeClipTransition({ type: 'schema-transition', params: undefined }),
      registry,
    );

    expect(patch.action).toBe('set-transition');
    expect(patch.transition).not.toBeNull();
    expect(patch.transition?.type).toBe('schema-transition');
    expect(patch.transition?.params).toEqual({ intensity: 0.5 });
  });

  it('returns set-transition with materialized defaults for empty params', () => {
    const schema: ParameterSchema = [
      { name: 'speed', label: 'Speed', type: 'number', default: 1.0 },
      { name: 'direction', label: 'Direction', type: 'select', options: [{ label: 'Up', value: 'up' }] },
    ];
    const registry = makeRegistrySnapshot([
      makeRecord('multi-param-transition', { schema, provenance: 'bundled-extension' }),
    ]);

    const patch = repairClipTransition(
      makeClipTransition({ type: 'multi-param-transition', params: {} }),
      registry,
    );

    expect(patch.action).toBe('set-transition');
    expect(patch.transition?.params).toEqual({
      speed: 1.0,
      direction: 'up',
    });
  });

  it('returns no-op when params are already present (even with schema)', () => {
    const schema: ParameterSchema = [
      { name: 'intensity', label: 'Intensity', type: 'number', default: 0.5 },
    ];
    const registry = makeRegistrySnapshot([
      makeRecord('existing-params-transition', { schema, provenance: 'bundled-extension' }),
    ]);

    const patch = repairClipTransition(
      makeClipTransition({
        type: 'existing-params-transition',
        params: { intensity: 0.9 },
      }),
      registry,
    );

    expect(patch.action).toBe('no-op');
    expect(patch.transition?.params).toEqual({ intensity: 0.9 });
  });

  it('repair patch has frozen diagnostics', () => {
    const patch = repairClipTransition(
      makeClipTransition({ type: 'nonexistent' }),
    );
    expect(Object.isFrozen(patch.diagnostics)).toBe(true);
  });

  it('returns clear-transition with explicit null transition for malformed legacy objects', () => {
    // Simulate a legacy transition object that somehow got corrupted
    const corruptedTransition = { type: 42 as unknown as string, duration: 'bad' as unknown as number };
    const patch = repairClipTransition(corruptedTransition);
    expect(patch.action).toBe('clear-transition');
    expect(patch.transition).toBeNull();
  });

  it('handles undefined transition', () => {
    const patch = repairClipTransition(undefined);
    expect(patch.action).toBe('clear-transition');
    expect(patch.transition).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// generateTransitionDiagnostics
// ---------------------------------------------------------------------------

describe('generateTransitionDiagnostics', () => {
  it('returns diagnostics for valid transition', () => {
    const diags = generateTransitionDiagnostics(
      makeClipTransition({ type: 'crossfade' }),
    );
    expect(diags).toHaveLength(0);
  });

  it('returns diagnostics for unresolvable transition', () => {
    const diags = generateTransitionDiagnostics(
      makeClipTransition({ type: 'unknown-transition' }),
    );
    expect(diags).toHaveLength(1);
    expect(diags[0].code).toBe(TransitionDiagnosticCodes.UNRESOLVED_TYPE);
  });

  it('returns diagnostics for malformed transition', () => {
    const diags = generateTransitionDiagnostics(null);
    expect(diags).toHaveLength(1);
    expect(diags[0].code).toBe(TransitionDiagnosticCodes.MISSING_TRANSITION_OBJECT);
  });

  it('returns frozen diagnostics', () => {
    const diags = generateTransitionDiagnostics(
      makeClipTransition({ type: 'unknown' }),
    );
    expect(Object.isFrozen(diags)).toBe(true);
  });
});
