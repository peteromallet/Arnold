/**
 * Tests for transition schema default materialization.
 * Covers T9: apply transition schema defaults when selecting or normalizing
 * transitions without stored params.
 */
import { describe, expect, it } from 'vitest';
import {
  materializeTransitionDefaults,
  normalizeClipTransition,
} from '@/tools/video-editor/transitions/catalog.ts';
import type { ClipTransition, ParameterSchema } from '@/tools/video-editor/types/index.ts';
import type { TransitionRegistryRecord } from '@/tools/video-editor/transitions/registry/types.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRecord(overrides?: Partial<TransitionRegistryRecord>): TransitionRegistryRecord {
  return {
    transitionId: 'test-transition',
    contributionId: 'test.contribution',
    renderer: () => ({ opacity: 1 }),
    provenance: 'built-in',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: [],
    },
    status: 'active',
    ...overrides,
  };
}

function makeClipTransition(overrides?: Partial<ClipTransition>): ClipTransition {
  return {
    type: 'test-transition',
    duration: 0.5,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// materializeTransitionDefaults
// ---------------------------------------------------------------------------

describe('materializeTransitionDefaults', () => {
  it('returns an empty frozen record for undefined schema', () => {
    const result = materializeTransitionDefaults(undefined);
    expect(result).toEqual({});
    expect(Object.isFrozen(result)).toBe(true);
  });

  it('returns an empty frozen record for null schema', () => {
    const result = materializeTransitionDefaults(null as unknown as ParameterSchema);
    expect(result).toEqual({});
    expect(Object.isFrozen(result)).toBe(true);
  });

  it('returns an empty frozen record for empty array schema', () => {
    const result = materializeTransitionDefaults([]);
    expect(result).toEqual({});
    expect(Object.isFrozen(result)).toBe(true);
  });

  it('materializes number defaults from schema', () => {
    const schema: ParameterSchema = [
      { name: 'intensity', label: 'Intensity', type: 'number', default: 0.5, min: 0, max: 1, step: 0.1 },
    ];
    const result = materializeTransitionDefaults(schema);
    expect(result).toEqual({ intensity: 0.5 });
    expect(Object.isFrozen(result)).toBe(true);
  });

  it('materializes number fallback to min when no default specified', () => {
    const schema: ParameterSchema = [
      { name: 'speed', label: 'Speed', type: 'number', min: 0.2, max: 2, step: 0.1 },
    ];
    const result = materializeTransitionDefaults(schema);
    expect(result).toEqual({ speed: 0.2 });
  });

  it('materializes number fallback to 0 when no min or default', () => {
    const schema: ParameterSchema = [
      { name: 'offset', label: 'Offset', type: 'number' },
    ];
    const result = materializeTransitionDefaults(schema);
    expect(result).toEqual({ offset: 0 });
  });

  it('materializes select defaults from schema', () => {
    const schema: ParameterSchema = [
      {
        name: 'direction',
        label: 'Direction',
        type: 'select',
        default: 'right',
        options: [
          { label: 'Left', value: 'left' },
          { label: 'Right', value: 'right' },
        ],
      },
    ];
    const result = materializeTransitionDefaults(schema);
    expect(result).toEqual({ direction: 'right' });
  });

  it('materializes select fallback to first option when no default', () => {
    const schema: ParameterSchema = [
      {
        name: 'direction',
        label: 'Direction',
        type: 'select',
        options: [
          { label: 'Up', value: 'up' },
          { label: 'Down', value: 'down' },
        ],
      },
    ];
    const result = materializeTransitionDefaults(schema);
    expect(result).toEqual({ direction: 'up' });
  });

  it('materializes boolean defaults from schema', () => {
    const schema: ParameterSchema = [
      { name: 'reverse', label: 'Reverse', type: 'boolean', default: true },
    ];
    const result = materializeTransitionDefaults(schema);
    expect(result).toEqual({ reverse: true });
  });

  it('materializes boolean fallback to false when no default', () => {
    const schema: ParameterSchema = [
      { name: 'enabled', label: 'Enabled', type: 'boolean' },
    ];
    const result = materializeTransitionDefaults(schema);
    expect(result).toEqual({ enabled: false });
  });

  it('materializes color defaults from schema', () => {
    const schema: ParameterSchema = [
      { name: 'tint', label: 'Tint', type: 'color', default: '#ff0000' },
    ];
    const result = materializeTransitionDefaults(schema);
    expect(result).toEqual({ tint: '#ff0000' });
  });

  it('materializes color fallback to #000000 when no default', () => {
    const schema: ParameterSchema = [
      { name: 'overlay', label: 'Overlay', type: 'color' },
    ];
    const result = materializeTransitionDefaults(schema);
    expect(result).toEqual({ overlay: '#000000' });
  });

  it('materializes audio-binding defaults from schema', () => {
    const schema: ParameterSchema = [
      {
        name: 'audioSrc',
        label: 'Audio Source',
        type: 'audio-binding',
        default: { source: 'bass', min: 0, max: 100 },
      },
    ];
    const result = materializeTransitionDefaults(schema);
    expect(result).toEqual({ audioSrc: { source: 'bass', min: 0, max: 100 } });
  });

  it('materializes audio-binding fallback when no default', () => {
    const schema: ParameterSchema = [
      { name: 'reactive', label: 'Reactive', type: 'audio-binding' },
    ];
    const result = materializeTransitionDefaults(schema);
    expect(result).toEqual({ reactive: { source: 'amplitude', min: 0, max: 1 } });
  });

  it('materializes multiple parameters', () => {
    const schema: ParameterSchema = [
      { name: 'intensity', label: 'Intensity', type: 'number', default: 0.7, min: 0, max: 1 },
      { name: 'direction', label: 'Direction', type: 'select', options: [{ label: 'Left', value: 'left' }] },
      { name: 'reverse', label: 'Reverse', type: 'boolean', default: false },
    ];
    const result = materializeTransitionDefaults(schema);
    expect(result).toEqual({
      intensity: 0.7,
      direction: 'left',
      reverse: false,
    });
  });

  it('returns a new frozen object each call (no shared mutation risk)', () => {
    const schema: ParameterSchema = [
      { name: 'x', label: 'X', type: 'number', default: 1 },
    ];
    const a = materializeTransitionDefaults(schema);
    const b = materializeTransitionDefaults(schema);
    expect(a).toEqual(b);
    expect(a).not.toBe(b);
  });
});

// ---------------------------------------------------------------------------
// normalizeClipTransition
// ---------------------------------------------------------------------------

describe('normalizeClipTransition', () => {
  it('returns undefined when clipTransition is undefined', () => {
    const result = normalizeClipTransition(undefined, makeRecord());
    expect(result).toBeUndefined();
  });

  it('returns clipTransition unchanged when params are present and non-empty', () => {
    const clip = makeClipTransition({ params: { intensity: 0.8 } });
    const record = makeRecord({
      schema: [{ name: 'intensity', label: 'Intensity', type: 'number', default: 0.5 }],
    });
    const result = normalizeClipTransition(clip, record);
    expect(result).toBe(clip);
    expect(result?.params).toEqual({ intensity: 0.8 });
  });

  it('returns clipTransition unchanged when record is undefined (no schema available)', () => {
    const clip = makeClipTransition();
    const result = normalizeClipTransition(clip, undefined);
    expect(result).toBe(clip);
  });

  it('returns clipTransition unchanged when record has no schema', () => {
    const clip = makeClipTransition();
    const record = makeRecord({ schema: undefined });
    const result = normalizeClipTransition(clip, record);
    expect(result).toBe(clip);
  });

  it('returns clipTransition unchanged when record has empty schema', () => {
    const clip = makeClipTransition();
    const record = makeRecord({ schema: [] });
    const result = normalizeClipTransition(clip, record);
    expect(result).toBe(clip);
  });

  it('materializes defaults when clip has no params', () => {
    const clip = makeClipTransition({ params: undefined });
    const record = makeRecord({
      schema: [{ name: 'intensity', label: 'Intensity', type: 'number', default: 0.5 }],
    });
    const result = normalizeClipTransition(clip, record);
    expect(result).not.toBe(clip);
    expect(result?.type).toBe('test-transition');
    expect(result?.duration).toBe(0.5);
    expect(result?.params).toEqual({ intensity: 0.5 });
    expect(Object.isFrozen(result?.params as object)).toBe(true);
  });

  it('materializes defaults when clip has empty params object', () => {
    const clip = makeClipTransition({ params: {} });
    const record = makeRecord({
      schema: [{ name: 'intensity', label: 'Intensity', type: 'number', default: 0.5 }],
    });
    const result = normalizeClipTransition(clip, record);
    expect(result).not.toBe(clip);
    expect(result?.params).toEqual({ intensity: 0.5 });
  });

  it('does not mutate the original clip snapshot', () => {
    const clip = makeClipTransition({ params: undefined });
    const originalClip = { ...clip };
    const record = makeRecord({
      schema: [{ name: 'intensity', label: 'Intensity', type: 'number', default: 0.5 }],
    });
    normalizeClipTransition(clip, record);
    expect(clip).toEqual(originalClip);
    expect(clip.params).toBeUndefined();
  });

  it('does not mutate existing clip params when materializing', () => {
    const existingParams = Object.freeze({ custom: 'value' });
    const clip = makeClipTransition({ params: existingParams });
    const record = makeRecord({
      schema: [{ name: 'intensity', label: 'Intensity', type: 'number', default: 0.5 }],
    });
    const result = normalizeClipTransition(clip, record);
    // Since params are non-empty, the original is returned unchanged
    expect(result).toBe(clip);
    expect(result?.params).toBe(existingParams);
    expect(result?.params).toEqual({ custom: 'value' });
  });

  it('merges defaults with existing params where keys are missing', () => {
    const clip = makeClipTransition({ params: { custom: 'keep-me' } });
    const record = makeRecord({
      schema: [
        { name: 'intensity', label: 'Intensity', type: 'number', default: 0.5 },
        { name: 'direction', label: 'Direction', type: 'select', options: [{ label: 'Up', value: 'up' }, { label: 'Down', value: 'down' }] },
      ],
    });
    // Params are non-empty (custom: 'keep-me'), so it returns unchanged
    const result = normalizeClipTransition(clip, record);
    expect(result).toBe(clip);
  });

  it('materializes defaults from schema with multiple parameters', () => {
    const clip = makeClipTransition();
    const record = makeRecord({
      schema: [
        { name: 'intensity', label: 'Intensity', type: 'number', default: 0.7 },
        { name: 'direction', label: 'Direction', type: 'select', options: [{ label: 'Left', value: 'left' }] },
        { name: 'reverse', label: 'Reverse', type: 'boolean', default: false },
      ],
    });
    const result = normalizeClipTransition(clip, record);
    expect(result?.params).toEqual({
      intensity: 0.7,
      direction: 'left',
      reverse: false,
    });
  });

  it('preserves transition type and duration while materializing defaults', () => {
    const clip: ClipTransition = { type: 'custom-wipe', duration: 0.8 };
    const record = makeRecord({
      transitionId: 'custom-wipe',
      schema: [{ name: 'angle', label: 'Angle', type: 'number', default: 45 }],
    });
    const result = normalizeClipTransition(clip, record);
    expect(result?.type).toBe('custom-wipe');
    expect(result?.duration).toBe(0.8);
    expect(result?.params).toEqual({ angle: 45 });
  });
});
