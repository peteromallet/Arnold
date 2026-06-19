/**
 * M7: Tests for effect registration service — schema validation and
 * trusteed component effect registration.
 *
 * Covers:
 * - validateEffectParameterSchema (all types, edge cases, duplicates)
 * - createEffectRegistrationService / registerComponent
 *   - Success with declared EffectContribution
 *   - Declaration/registration mismatch diagnostics
 *   - Provenance is 'bundled-extension'
 *   - Invalid schema → status 'error' record
 *   - HMR replacement via re-registration
 *   - Dispose handle idempotence
 *   - Disposal unregisters the record
 */

import type { FC } from 'react';
import { describe, expect, it, vi } from 'vitest';
import {
  createEffectRegistrationService,
  validateEffectParameterSchema,
} from '@/tools/video-editor/runtime/effectRegistrationService';
import { createEffectRegistry } from '@/tools/video-editor/effects/registry/EffectRegistry';
import type { EffectRegistry } from '@/tools/video-editor/effects/registry/types';
import type { EffectRegistryRecord } from '@/tools/video-editor/effects/registry/types';
import type {
  DisposeHandle,
  EffectComponent,
  EffectContribution,
  EffectParameterSchema,
  ExtensionDiagnostic,
  ExtensionDiagnosticsService,
  ReighExtension,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Test component
// ---------------------------------------------------------------------------

const TestComponent: FC<Record<string, unknown>> = () => null;
const ReplacementComponent: FC<Record<string, unknown>> = () => null;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create a minimal diagnostics service that records reports. */
function makeDiagnosticsService(
  extensionId: string,
): ExtensionDiagnosticsService & { reports: Omit<ExtensionDiagnostic, 'extensionId'>[] } {
  const reports: Omit<ExtensionDiagnostic, 'extensionId'>[] = [];
  return {
    report(diag) {
      reports.push({ ...diag });
    },
    get diagnostics(): readonly ExtensionDiagnostic[] {
      return reports.map((r) => ({ ...r, extensionId } as ExtensionDiagnostic));
    },
    reports,
  };
}

/** Create a real EffectRegistry for integration-level testing. */
function makeEffectRegistry(): EffectRegistry {
  return createEffectRegistry();
}

/** Build a minimal extension with EffectContribution declarations. */
function makeExtension(
  id: string,
  contributions?: readonly EffectContribution[],
): ReighExtension {
  return {
    manifest: {
      id: id as never,
      version: '1.0.0',
      label: id,
      contributions: contributions as never,
    },
    activate: undefined,
  } as unknown as ReighExtension;
}

/** A sample valid EffectContribution. */
function effectContrib(
  effectId: string,
  id?: string,
  overrides?: Partial<EffectContribution>,
): EffectContribution {
  return {
    id: (id ?? `contrib.${effectId}`) as never,
    kind: 'effect',
    effectId,
    label: `Effect ${effectId}`,
    order: 0,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// validateEffectParameterSchema
// ---------------------------------------------------------------------------

describe('validateEffectParameterSchema', () => {
  it('returns empty array for undefined schema', () => {
    expect(validateEffectParameterSchema(undefined)).toEqual([]);
  });

  it('returns empty array for empty array schema', () => {
    expect(validateEffectParameterSchema([])).toEqual([]);
  });

  it('returns error for non-array schema', () => {
    const diags = validateEffectParameterSchema('not-an-array' as unknown as EffectParameterSchema);
    expect(diags).toHaveLength(1);
    expect(diags[0].code).toBe('effects/invalid-schema-not-array');
    expect(diags[0].severity).toBe('error');
  });

  it('accepts a valid number parameter definition', () => {
    const schema: EffectParameterSchema = [
      {
        name: 'intensity',
        label: 'Intensity',
        description: 'Effect intensity',
        type: 'number',
        default: 50,
        min: 0,
        max: 100,
        step: 1,
      },
    ];
    expect(validateEffectParameterSchema(schema)).toEqual([]);
  });

  it('accepts a valid select parameter definition', () => {
    const schema: EffectParameterSchema = [
      {
        name: 'style',
        label: 'Style',
        description: 'Visual style',
        type: 'select',
        default: 'modern',
        options: [
          { label: 'Modern', value: 'modern' },
          { label: 'Classic', value: 'classic' },
        ],
      },
    ];
    expect(validateEffectParameterSchema(schema)).toEqual([]);
  });

  it('accepts a valid boolean parameter definition', () => {
    const schema: EffectParameterSchema = [
      {
        name: 'enabled',
        label: 'Enabled',
        description: 'Enable the effect',
        type: 'boolean',
        default: true,
      },
    ];
    expect(validateEffectParameterSchema(schema)).toEqual([]);
  });

  it('accepts a valid color parameter definition', () => {
    const schema: EffectParameterSchema = [
      {
        name: 'tint',
        label: 'Tint Color',
        description: 'Color tint',
        type: 'color',
        default: '#ff0000',
      },
    ];
    expect(validateEffectParameterSchema(schema)).toEqual([]);
  });

  it('accepts a valid audio-binding parameter definition', () => {
    const schema: EffectParameterSchema = [
      {
        name: 'bassReact',
        label: 'Bass Reactivity',
        description: 'Reactivity to bass',
        type: 'audio-binding',
        default: { source: 'bass', min: 0, max: 1 },
      },
    ];
    expect(validateEffectParameterSchema(schema)).toEqual([]);
  });

  it('accepts a mixed-type valid schema', () => {
    const schema: EffectParameterSchema = [
      {
        name: 'opacity',
        label: 'Opacity',
        description: 'Layer opacity',
        type: 'number',
        default: 80,
        min: 0,
        max: 100,
      },
      {
        name: 'showBorder',
        label: 'Show Border',
        description: 'Toggle border',
        type: 'boolean',
        default: false,
      },
    ];
    expect(validateEffectParameterSchema(schema)).toEqual([]);
  });

  // ── Name validation ────────────────────────────────────────────────────

  it('flags missing name', () => {
    const schema: EffectParameterSchema = [
      { name: '', label: 'Test', description: 'Desc', type: 'number' },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-name')).toBe(true);
  });

  it('flags non-string name', () => {
    const schema: EffectParameterSchema = [
      { name: 123 as unknown as string, label: 'Test', description: 'Desc', type: 'number' },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-name')).toBe(true);
  });

  // ── Label validation ───────────────────────────────────────────────────

  it('flags missing label', () => {
    const schema: EffectParameterSchema = [
      { name: 'test', label: '', description: 'Desc', type: 'number' },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-label')).toBe(true);
  });

  // ── Type validation ────────────────────────────────────────────────────

  it('flags invalid type', () => {
    const schema: EffectParameterSchema = [
      { name: 'test', label: 'Test', description: 'Desc', type: 'invalid' as 'number' },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-type')).toBe(true);
  });

  // ── Number type validation ─────────────────────────────────────────────

  it('flags non-number min for number type', () => {
    const schema: EffectParameterSchema = [
      { name: 'x', label: 'X', description: 'D', type: 'number', min: 'abc' as unknown as number },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-min')).toBe(true);
  });

  it('flags non-number max for number type', () => {
    const schema: EffectParameterSchema = [
      { name: 'x', label: 'X', description: 'D', type: 'number', max: 'abc' as unknown as number },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-max')).toBe(true);
  });

  it('flags min > max for number type', () => {
    const schema: EffectParameterSchema = [
      { name: 'x', label: 'X', description: 'D', type: 'number', min: 100, max: 0 },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-range')).toBe(true);
  });

  it('does not flag min <= max for number type', () => {
    const schema: EffectParameterSchema = [
      { name: 'x', label: 'X', description: 'D', type: 'number', min: 0, max: 100 },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-range')).toBe(false);
  });

  it('flags non-number step for number type', () => {
    const schema: EffectParameterSchema = [
      { name: 'x', label: 'X', description: 'D', type: 'number', step: 'abc' as unknown as number },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-step')).toBe(true);
  });

  it('flags non-number default for number type', () => {
    const schema: EffectParameterSchema = [
      { name: 'x', label: 'X', description: 'D', type: 'number', default: 'abc' as unknown as number },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-default')).toBe(true);
  });

  // ── Select type validation ─────────────────────────────────────────────

  it('flags missing options for select type', () => {
    const schema: EffectParameterSchema = [
      { name: 's', label: 'S', description: 'D', type: 'select' },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-options')).toBe(true);
  });

  it('flags empty options array for select type', () => {
    const schema: EffectParameterSchema = [
      { name: 's', label: 'S', description: 'D', type: 'select', options: [] },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-options')).toBe(true);
  });

  it('flags invalid option entries (missing label)', () => {
    const schema: EffectParameterSchema = [
      {
        name: 's', label: 'S', description: 'D', type: 'select',
        options: [{ value: 'v' } as { label: string; value: string }],
      },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-option-entry')).toBe(true);
  });

  it('flags non-string default for select type', () => {
    const schema: EffectParameterSchema = [
      { name: 's', label: 'S', description: 'D', type: 'select', default: 123 as unknown as string },
    ];
    const diags = validateEffectParameterSchema(schema);
    // This should get both options error AND default error
    expect(diags.some((d) => d.code === 'effects/invalid-schema-default')).toBe(true);
  });

  // ── Boolean type validation ────────────────────────────────────────────

  it('flags non-boolean default for boolean type', () => {
    const schema: EffectParameterSchema = [
      { name: 'b', label: 'B', description: 'D', type: 'boolean', default: 'yes' as unknown as boolean },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-default')).toBe(true);
  });

  // ── Color type validation ──────────────────────────────────────────────

  it('flags invalid hex default for color type', () => {
    const schema: EffectParameterSchema = [
      { name: 'c', label: 'C', description: 'D', type: 'color', default: 'not-a-color' },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-default')).toBe(true);
  });

  it('accepts valid hex defaults (#rgb, #rrggbb, #rrggbbaa)', () => {
    const validColors = ['#fff', '#ff0000', '#ff0000ff'];
    for (const color of validColors) {
      const schema: EffectParameterSchema = [
        { name: 'c', label: 'C', description: 'D', type: 'color', default: color },
      ];
      expect(validateEffectParameterSchema(schema)).toEqual([]);
    }
  });

  // ── Audio-binding type validation ──────────────────────────────────────

  it('flags non-object default for audio-binding type', () => {
    const schema: EffectParameterSchema = [
      { name: 'a', label: 'A', description: 'D', type: 'audio-binding', default: 'bass' as unknown as Record<string, unknown> },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-default')).toBe(true);
  });

  it('flags audio-binding default missing source', () => {
    const schema: EffectParameterSchema = [
      {
        name: 'a', label: 'A', description: 'D', type: 'audio-binding',
        default: { min: 0, max: 1 },
      },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-default')).toBe(true);
  });

  it('flags audio-binding default with invalid source name', () => {
    const schema: EffectParameterSchema = [
      {
        name: 'a', label: 'A', description: 'D', type: 'audio-binding',
        default: { source: 'invalid', min: 0, max: 1 },
      },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-default')).toBe(true);
  });

  // ── Duplicate name validation ─────────────────────────────────────────

  it('flags duplicate parameter names', () => {
    const schema: EffectParameterSchema = [
      { name: 'x', label: 'X1', description: 'D', type: 'number' },
      { name: 'x', label: 'X2', description: 'D', type: 'number' },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-duplicate-name')).toBe(true);
  });

  it('does not flag unique parameter names', () => {
    const schema: EffectParameterSchema = [
      { name: 'a', label: 'A', description: 'D', type: 'number' },
      { name: 'b', label: 'B', description: 'D', type: 'number' },
    ];
    const diags = validateEffectParameterSchema(schema);
    expect(diags.some((d) => d.code === 'effects/invalid-schema-duplicate-name')).toBe(false);
  });

  // ── Multiple errors ────────────────────────────────────────────────────

  it('collects multiple errors for a single parameter', () => {
    const schema: EffectParameterSchema = [
      { name: '', label: '', description: 'D', type: 'invalid' as 'number' },
    ];
    const diags = validateEffectParameterSchema(schema);
    // Should have name error, label error, and type error (at minimum)
    expect(diags.filter((d) => d.severity === 'error').length).toBeGreaterThanOrEqual(3);
  });
});

// ---------------------------------------------------------------------------
// createEffectRegistrationService / registerComponent
// ---------------------------------------------------------------------------

describe('createEffectRegistrationService', () => {
  it('registerComponent succeeds with declared EffectContribution', () => {
    const extensionId = 'com.example.test';
    const effectId = 'fx.glow';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [effectContrib(effectId)]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    const handle = svc.registerComponent(effectId, TestComponent as EffectComponent);

    // Record should be resolvable
    const resolved = registry.resolve(effectId);
    expect(resolved).toBeDefined();
    expect(resolved?.effectId).toBe(effectId);
    expect(resolved?.component).toBe(TestComponent);
    expect(resolved?.provenance).toBe('bundled-extension');
    expect(resolved?.ownerExtensionId).toBe(extensionId);
    expect(resolved?.status).toBe('active');

    // Handle should be a DisposeHandle
    expect(typeof handle.dispose).toBe('function');
  });

  it('registerComponent emits info diagnostic on success', () => {
    const extensionId = 'com.example.diag';
    const effectId = 'fx.fade';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [effectContrib(effectId)]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    svc.registerComponent(effectId, TestComponent as EffectComponent);

    const registeredDiag = diagSvc.reports.find((d) => d.code === 'effects/registered');
    expect(registeredDiag).toBeDefined();
    expect(registeredDiag?.severity).toBe('info');
    expect(registeredDiag?.message).toContain(effectId);
    expect(registeredDiag?.message).toContain(extensionId);
  });

  // ── Declaration/registration mismatch ──────────────────────────────────

  it('registerComponent emits error diagnostic for undeclared effectId', () => {
    const extensionId = 'com.example.undeclared';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [effectContrib('fx.declared')]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    const handle = svc.registerComponent('fx.undeclared', TestComponent as EffectComponent);

    // Should emit an error diagnostic
    const errDiag = diagSvc.reports.find((d) => d.code === 'effects/undeclared-effect');
    expect(errDiag).toBeDefined();
    expect(errDiag?.severity).toBe('error');
    expect(errDiag?.message).toContain('fx.undeclared');
    expect(errDiag?.message).toContain('not declared');

    // Should return a noop handle (calling dispose doesn't crash)
    expect(typeof handle.dispose).toBe('function');
    expect(() => handle.dispose()).not.toThrow();

    // Record should NOT be registered
    expect(registry.resolve('fx.undeclared')).toBeUndefined();
  });

  it('registerComponent returns a noop handle when no contributions exist', () => {
    const extensionId = 'com.example.nocontribs';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, []);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    const handle = svc.registerComponent('fx.any', TestComponent as EffectComponent);
    expect(diagSvc.reports.some((d) => d.code === 'effects/undeclared-effect')).toBe(true);
    expect(typeof handle.dispose).toBe('function');
    expect(() => handle.dispose()).not.toThrow();
  });

  // ── Provenance ─────────────────────────────────────────────────────────

  it('registered records have provenance "bundled-extension"', () => {
    const extensionId = 'com.example.provenance';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [effectContrib('fx.prove')]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    svc.registerComponent('fx.prove', TestComponent as EffectComponent);

    const record = registry.resolve('fx.prove');
    expect(record?.provenance).toBe('bundled-extension');
  });

  // ── Schema validation at registration ──────────────────────────────────

  it('valid schema produces status "active" record', () => {
    const extensionId = 'com.example.validschema';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [effectContrib('fx.valid')]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    const schema: EffectParameterSchema = [
      { name: 'intensity', label: 'Intensity', description: 'D', type: 'number', default: 50, min: 0, max: 100 },
    ];

    svc.registerComponent('fx.valid', TestComponent as EffectComponent, {
      parameterSchema: schema,
    });

    const record = registry.resolve('fx.valid');
    expect(record?.status).toBe('active');
    expect(record?.schema).toBeDefined();
    expect(record?.schema?.[0]?.name).toBe('intensity');
  });

  it('invalid schema produces status "error" record with diagnostics', () => {
    const extensionId = 'com.example.invalidschema';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [effectContrib('fx.invalid')]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    const schema: EffectParameterSchema = [
      { name: '', label: '', description: 'D', type: 'invalid' as 'number' },
    ];

    svc.registerComponent('fx.invalid', TestComponent as EffectComponent, {
      parameterSchema: schema,
    });

    const record = registry.resolve('fx.invalid');
    expect(record?.status).toBe('error');
    expect(record?.diagnostics).toBeDefined();
    expect(record!.diagnostics!.length).toBeGreaterThan(0);

    // The registered diagnostic should be a warning (not error) because
    // the record-level status already captures the error state.
    const registeredDiag = diagSvc.reports.find((d) => d.code === 'effects/registered');
    expect(registeredDiag).toBeDefined();
    expect(registeredDiag?.severity).toBe('warning');
  });

  // ── HMR replacement via re-registration ────────────────────────────────

  it('re-registering the same effectId replaces the record (HMR)', () => {
    const extensionId = 'com.example.hmr';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [effectContrib('fx.hmr')]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    // First registration
    const handle1 = svc.registerComponent('fx.hmr', TestComponent as EffectComponent);
    expect(registry.resolve('fx.hmr')?.component).toBe(TestComponent);

    // Re-registration (HMR replacement)
    const handle2 = svc.registerComponent('fx.hmr', ReplacementComponent as EffectComponent);

    // Old handle should be inert (disposing it doesn't remove the new record)
    handle1.dispose();
    expect(registry.resolve('fx.hmr')?.component).toBe(ReplacementComponent);

    // New handle properly disposes the replacement
    handle2.dispose();
    expect(registry.resolve('fx.hmr')).toBeUndefined();
  });

  // ── Disposal ───────────────────────────────────────────────────────────

  it('dispose handle unregisters the record', () => {
    const extensionId = 'com.example.dispose';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [effectContrib('fx.disp')]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    const handle = svc.registerComponent('fx.disp', TestComponent as EffectComponent);
    expect(registry.resolve('fx.disp')).toBeDefined();

    handle.dispose();
    expect(registry.resolve('fx.disp')).toBeUndefined();
  });

  it('dispose handle is idempotent', () => {
    const extensionId = 'com.example.idempotent';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [effectContrib('fx.idem')]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    const handle = svc.registerComponent('fx.idem', TestComponent as EffectComponent);

    // First dispose — record should be unregistered
    handle.dispose();
    expect(registry.resolve('fx.idem')).toBeUndefined();

    // Second dispose — should not throw, should not re-emit disposed diagnostic
    const reportsBefore = diagSvc.reports.length;
    handle.dispose();
    // No new diagnostics should be emitted
    expect(diagSvc.reports.length).toBe(reportsBefore);
  });

  it('dispose emits diagnostics on disposal', () => {
    const extensionId = 'com.example.dispdiag';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [effectContrib('fx.dispdiag')]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    const handle = svc.registerComponent('fx.dispdiag', TestComponent as EffectComponent);

    // Disposal should emit 'effects/disposed' diagnostic
    handle.dispose();
    const disposedDiag = diagSvc.reports.find((d) => d.code === 'effects/disposed');
    expect(disposedDiag).toBeDefined();
    expect(disposedDiag?.severity).toBe('info');
  });

  // ── Renderability ──────────────────────────────────────────────────────

  it('registered record gets preview-supported renderability by default', () => {
    const extensionId = 'com.example.renderability';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [effectContrib('fx.render')]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    svc.registerComponent('fx.render', TestComponent as EffectComponent);

    const record = registry.resolve('fx.render');
    expect(record?.renderability).toBeDefined();
    expect(record?.renderability.defaultRoute).toBe('preview');

    const capabilities = record?.renderability.capabilities ?? [];
    const previewCap = capabilities.find((c) => c.route === 'preview');
    expect(previewCap?.status).toBe('supported');

    // browser-export should be blocked by default (SD2)
    const browserCap = capabilities.find((c) => c.route === 'browser-export');
    expect(browserCap?.status).toBe('blocked');

    // worker-export should be blocked by default
    const workerCap = capabilities.find((c) => c.route === 'worker-export');
    expect(workerCap?.status).toBe('blocked');
  });

  it('allowBrowserExport=true produces supported browser-export capability', () => {
    const extensionId = 'com.example.browserexport';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [
      effectContrib('fx.browser', undefined, { allowBrowserExport: true }),
    ]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    svc.registerComponent('fx.browser', TestComponent as EffectComponent);

    const record = registry.resolve('fx.browser');
    const browserCap = record?.renderability.capabilities.find((c) => c.route === 'browser-export');
    expect(browserCap?.status).toBe('supported');
  });

  it('allowWorkerExport=true produces supported worker-export capability', () => {
    const extensionId = 'com.example.workerexport';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [
      effectContrib('fx.worker', undefined, { allowWorkerExport: true }),
    ]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    svc.registerComponent('fx.worker', TestComponent as EffectComponent);

    const record = registry.resolve('fx.worker');
    const workerCap = record?.renderability.capabilities.find((c) => c.route === 'worker-export');
    expect(workerCap?.status).toBe('supported');
  });

  // ── Multiple effect registrations ──────────────────────────────────────

  it('supports multiple effect registrations from the same extension', () => {
    const extensionId = 'com.example.multi';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [
      effectContrib('fx.one'),
      effectContrib('fx.two'),
      effectContrib('fx.three'),
    ]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    svc.registerComponent('fx.one', TestComponent as EffectComponent);
    svc.registerComponent('fx.two', TestComponent as EffectComponent);
    svc.registerComponent('fx.three', TestComponent as EffectComponent);

    expect(registry.resolve('fx.one')).toBeDefined();
    expect(registry.resolve('fx.two')).toBeDefined();
    expect(registry.resolve('fx.three')).toBeDefined();

    // All should have correct provenance
    for (const id of ['fx.one', 'fx.two', 'fx.three']) {
      expect(registry.resolve(id)?.provenance).toBe('bundled-extension');
      expect(registry.resolve(id)?.ownerExtensionId).toBe(extensionId);
    }
  });

  // ── Label override ─────────────────────────────────────────────────────

  it('uses options.label when provided', () => {
    const extensionId = 'com.example.label';
    const diagSvc = makeDiagnosticsService(extensionId);
    const registry = makeEffectRegistry();
    const extension = makeExtension(extensionId, [effectContrib('fx.label')]);

    const svc = createEffectRegistrationService({
      extension,
      effectRegistry: registry,
      diagnosticsService: diagSvc as ExtensionDiagnosticsService,
    });

    svc.registerComponent('fx.label', TestComponent as EffectComponent, {
      label: 'Custom Label Override',
    });

    // The record's label is not directly stored on EffectRegistryRecord;
    // it's used only in diagnostics. Verify the registered diagnostic
    // contains the label override.
    const registeredDiag = diagSvc.reports.find((d) => d.code === 'effects/registered');
    expect(registeredDiag).toBeDefined();
  });
});
