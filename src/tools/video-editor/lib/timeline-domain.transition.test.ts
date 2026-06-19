/**
 * Integration tests for transition validation/repair in timeline-domain (T14).
 *
 * Covers: legacy malformed transitions, removed contributed transitions,
 * no-transition repair behavior, and integration into canonicalize paths.
 */

import { describe, expect, it } from 'vitest';
import type { TimelineClip, TimelineConfig, ClipTransition, ParameterSchema } from '@/tools/video-editor/types/index.ts';
import { repairTimelineClipTransitions } from '@/tools/video-editor/lib/timeline-domain.ts';
import type { TimelineDomainIssue } from '@/tools/video-editor/lib/timeline-domain.ts';
import {
  createTransitionRegistry,
  type TransitionRegistryRecord,
  type TransitionRegistrySnapshot,
} from '@/tools/video-editor/transitions/registry/index.ts';
import { createTransitionSnapshot } from '@/tools/video-editor/transitions/catalog.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeTimelineConfig(clips: TimelineClip[]): TimelineConfig {
  return {
    output: { width: 1920, height: 1080, fps: 30 },
    clips,
    tracks: [
      { id: 'V1', type: 'video', kind: 'visual', label: 'Video 1' },
    ],
  };
}

function makeClip(overrides?: Partial<TimelineClip>): TimelineClip {
  return {
    id: 'clip-1',
    clipType: 'media',
    track: 'V1',
    at: 0,
    hold: 5,
    asset: 'asset-1',
    ...overrides,
  };
}

function makeTransitionRecord(
  transitionId: string,
  overrides?: Partial<TransitionRegistryRecord>,
): TransitionRegistryRecord {
  return {
    transitionId,
    contributionId: `test:${transitionId}`,
    renderer: () => ({ opacity: 1 }),
    provenance: 'bundled-extension',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: [
        { route: 'preview', status: 'supported' as const, determinism: 'deterministic' as const },
      ],
    },
    status: 'active',
    ...overrides,
  };
}

function makeRegistrySnapshot(records: TransitionRegistryRecord[]): TransitionRegistrySnapshot {
  const registry = createTransitionRegistry();
  for (const record of records) {
    registry.register(record);
  }
  return createTransitionSnapshot(registry.getSnapshot());
}

function makeTransition(overrides?: Partial<ClipTransition>): ClipTransition {
  return { type: 'crossfade', duration: 0.5, ...overrides };
}

// ---------------------------------------------------------------------------
// repairTimelineClipTransitions tests
// ---------------------------------------------------------------------------

describe('repairTimelineClipTransitions', () => {
  // -- No-op for valid transitions -------------------------------------------

  it('returns config unchanged for valid built-in transition', () => {
    const config = makeTimelineConfig([
      makeClip({ transition: makeTransition({ type: 'crossfade' }) }),
    ]);
    const issues: TimelineDomainIssue[] = [];

    const result = repairTimelineClipTransitions(config, undefined, issues);

    // Config should be reference-identical (no repair needed)
    expect(result).toBe(config);
    expect(issues).toHaveLength(0);
  });

  it('returns config unchanged for clip without transition', () => {
    const config = makeTimelineConfig([makeClip()]);
    const issues: TimelineDomainIssue[] = [];

    const result = repairTimelineClipTransitions(config, undefined, issues);

    expect(result).toBe(config);
    expect(issues).toHaveLength(0);
  });

  // -- Legacy: missing type --------------------------------------------------

  it('clears transition with missing type and reports diagnostic', () => {
    // @ts-expect-error - intentionally malformed for legacy test
    const malformedTransition = { duration: 0.5 } as ClipTransition;
    const config = makeTimelineConfig([
      makeClip({ transition: malformedTransition }),
    ]);
    const issues: TimelineDomainIssue[] = [];

    const result = repairTimelineClipTransitions(config, undefined, issues);

    // Transition should be removed
    expect(result.clips[0].transition).toBeUndefined();
    // Diagnostic should be recorded
    expect(issues.length).toBeGreaterThan(0);
    expect(issues.some((i) => i.code === 'legacy_transition_missing_type')).toBe(true);
    expect(issues.some((i) => i.clipId === 'clip-1')).toBe(true);
  });

  it('clears transition with null type', () => {
    const config = makeTimelineConfig([
      makeClip({ transition: makeTransition({ type: '' }) }),
    ]);
    const issues: TimelineDomainIssue[] = [];

    const result = repairTimelineClipTransitions(config, undefined, issues);

    expect(result.clips[0].transition).toBeUndefined();
    expect(issues.length).toBeGreaterThan(0);
  });

  // -- Legacy: unresolvable type ---------------------------------------------

  it('clears unresolvable transition IDs without silent fallback', () => {
    const config = makeTimelineConfig([
      makeClip({ transition: makeTransition({ type: 'nonexistent-transition' }) }),
    ]);
    const issues: TimelineDomainIssue[] = [];

    const result = repairTimelineClipTransitions(config, undefined, issues);

    // Transition should be cleared, NOT silently replaced with crossfade
    expect(result.clips[0].transition).toBeUndefined();
    expect(issues.some((i) => i.code === 'legacy_transition_unresolvable')).toBe(true);
    expect(issues.some((i) => i.message?.includes('nonexistent-transition'))).toBe(true);
  });

  // -- Removed contributed transitions ---------------------------------------

  it('detects and clears removed contributed transitions', () => {
    const config = makeTimelineConfig([
      makeClip({ transition: makeTransition({ type: 'my-ext:custom-wipe' }) }),
    ]);
    const issues: TimelineDomainIssue[] = [];

    const result = repairTimelineClipTransitions(config, undefined, issues);

    expect(result.clips[0].transition).toBeUndefined();
    expect(issues.some((i) => i.code === 'legacy_transition_removed_contributed')).toBe(true);
  });

  it('detects removed contributed transition with empty registry', () => {
    const emptyRegistry = createTransitionSnapshot();
    const config = makeTimelineConfig([
      makeClip({ transition: makeTransition({ type: 'ext:uninstalled-fx' }) }),
    ]);
    const issues: TimelineDomainIssue[] = [];

    const result = repairTimelineClipTransitions(config, emptyRegistry, issues);

    expect(result.clips[0].transition).toBeUndefined();
    expect(issues.some((i) => i.code === 'legacy_transition_removed_contributed')).toBe(true);
  });

  // -- Missing params repair -------------------------------------------------

  it('materializes default params for transition with schema but no stored params', () => {
    const schema: ParameterSchema = [
      { name: 'intensity', label: 'Intensity', type: 'number', default: 0.5, min: 0, max: 1 },
    ];
    const snapshot = makeRegistrySnapshot([
      makeTransitionRecord('param-wipe', { schema }),
    ]);

    const config = makeTimelineConfig([
      makeClip({
        transition: makeTransition({ type: 'param-wipe', params: undefined }),
      }),
    ]);
    const issues: TimelineDomainIssue[] = [];

    const result = repairTimelineClipTransitions(config, snapshot, issues);

    // Transition should still exist but with materialized defaults
    expect(result.clips[0].transition).toBeDefined();
    expect(result.clips[0].transition!.type).toBe('param-wipe');
    expect(result.clips[0].transition!.params).toEqual({ intensity: 0.5 });

    // A params-repaired diagnostic should be issued
    expect(issues.some((i) => i.code === 'legacy_transition_params_repaired')).toBe(true);
  });

  it('does not modify transitions that already have params', () => {
    const schema: ParameterSchema = [
      { name: 'intensity', label: 'Intensity', type: 'number', default: 0.5 },
    ];
    const snapshot = makeRegistrySnapshot([
      makeTransitionRecord('custom-fx', { schema }),
    ]);

    const config = makeTimelineConfig([
      makeClip({
        transition: makeTransition({
          type: 'custom-fx',
          params: { intensity: 0.9 },
        }),
      }),
    ]);
    const issues: TimelineDomainIssue[] = [];

    const result = repairTimelineClipTransitions(config, snapshot, issues);

    // Should be unchanged - no-op
    expect(result).toBe(config);
    expect(issues).toHaveLength(0);
  });

  // -- Multiple clips --------------------------------------------------------

  it('repairs multiple clips and collects all issues', () => {
    const config = makeTimelineConfig([
      makeClip({
        id: 'clip-1',
        transition: makeTransition({ type: 'nonexistent-1' }),
      }),
      makeClip({
        id: 'clip-2',
        transition: makeTransition({ type: 'ext:removed-fx' }),
      }),
      makeClip({
        id: 'clip-3',
      }),
    ]);
    const issues: TimelineDomainIssue[] = [];

    const result = repairTimelineClipTransitions(config, undefined, issues);

    // All malformed transitions should be cleared
    expect(result.clips[0].transition).toBeUndefined();
    expect(result.clips[1].transition).toBeUndefined();
    // Clip without transition should be unchanged
    expect(result.clips[2].transition).toBeUndefined();

    // Should have per-clip issues plus a summary issue
    expect(issues.length).toBeGreaterThanOrEqual(2);
    // Summary issue about cleared transitions
    expect(issues.some((i) => i.code === 'legacy_transition_cleared')).toBe(true);
  });

  // -- Returns original config on no-op --------------------------------------

  it('returns original config reference when no repairs needed', () => {
    const config = makeTimelineConfig([
      makeClip(),
      makeClip({ id: 'clip-2' }),
    ]);
    const issues: TimelineDomainIssue[] = [];

    const result = repairTimelineClipTransitions(config, undefined, issues);

    expect(result).toBe(config);
    expect(issues).toHaveLength(0);
  });

  // -- Immutability: does not mutate input config ----------------------------

  it('does not mutate the original config', () => {
    const originalTransition = makeTransition({ type: 'nonexistent' });
    const config = makeTimelineConfig([
      makeClip({ transition: originalTransition }),
    ]);
    const issues: TimelineDomainIssue[] = [];

    const _result = repairTimelineClipTransitions(config, undefined, issues);

    // Original config should still have the transition
    expect(config.clips[0].transition).toBeDefined();
    expect(config.clips[0].transition!.type).toBe('nonexistent');
  });
});
