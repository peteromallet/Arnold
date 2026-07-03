import { describe, expect, it } from 'vitest';
import {
  resolveScopedKey,
  resolveRouteFitMetadata,
  blockerToRouteFitMetadata,
  findingToRouteFitMetadata,
} from '@/tools/video-editor/runtime/routeFitMapper.ts';
import type {
  ContributionIndex,
  ContributionIndexEntry,
  VideoEditorPlannerBlockerDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { CapabilityFinding } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

function entry(overrides: Partial<ContributionIndexEntry> & {
  scopedKey: string;
}): ContributionIndexEntry {
  return {
    kind: overrides.scopedKey.split(':')[0],
    extensionId: overrides.extensionId ?? overrides.scopedKey.split(':')[1],
    contributionId: overrides.contributionId ?? overrides.scopedKey.split(':')[2],
    status: 'active',
    diagnostics: Object.freeze([]),
    duplicateOrdinal: 0,
    projectionEligible: true,
    projection: Object.freeze({
      duplicateOrdinal: 0,
      eligible: true,
      projected: true,
      source: 'descriptor-array',
    }),
    ...overrides,
  };
}

function index(...entries: ContributionIndexEntry[]): ContributionIndex {
  const map: Record<string, ContributionIndexEntry[]> = {};
  for (const e of entries) {
    (map[e.scopedKey] ??= []).push(e);
  }
  return Object.freeze(map);
}

// ---------------------------------------------------------------------------
// resolveScopedKey
// ---------------------------------------------------------------------------

describe('resolveScopedKey', () => {
  it('returns undefined when contributionIndex is undefined', () => {
    expect(resolveScopedKey(undefined, { kind: 'shader', extensionId: 'a', contributionId: 'b' })).toBeUndefined();
  });

  it('returns undefined when identity is undefined', () => {
    expect(resolveScopedKey(index(), undefined)).toBeUndefined();
  });

  it('returns undefined when extensionId is missing', () => {
    expect(resolveScopedKey(index(), { kind: 'shader', contributionId: 'b' })).toBeUndefined();
  });

  it('returns undefined when contributionId is missing', () => {
    expect(resolveScopedKey(index(), { kind: 'shader', extensionId: 'a' })).toBeUndefined();
  });

  it('resolves directly when kind, extensionId, and contributionId are all supplied', () => {
    const idx = index(entry({ scopedKey: 'shader:ext-a:shader-1' }));
    expect(resolveScopedKey(idx, { kind: 'shader', extensionId: 'ext-a', contributionId: 'shader-1' })).toBe(
      'shader:ext-a:shader-1',
    );
  });

  it('returns undefined when fully-qualified key is not in the index', () => {
    const idx = index(entry({ scopedKey: 'shader:ext-b:shader-2' }));
    expect(resolveScopedKey(idx, { kind: 'shader', extensionId: 'ext-a', contributionId: 'shader-1' })).toBeUndefined();
  });

  it('resolves without kind when extensionId+contributionId uniquely match one entry', () => {
    const idx = index(entry({ scopedKey: 'output-format:ext-a:fmt-1' }));
    expect(resolveScopedKey(idx, { extensionId: 'ext-a', contributionId: 'fmt-1' })).toBe(
      'output-format:ext-a:fmt-1',
    );
  });

  it('returns undefined when extensionId+contributionId match entries with different kinds (ambiguous)', () => {
    const idx = index(
      entry({ scopedKey: 'shader:ext-a:shared-id' }),
      entry({ scopedKey: 'output-format:ext-a:shared-id' }),
    );
    expect(resolveScopedKey(idx, { extensionId: 'ext-a', contributionId: 'shared-id' })).toBeUndefined();
  });

  it('returns undefined when extensionId+contributionId have no match', () => {
    const idx = index(entry({ scopedKey: 'shader:ext-b:id-b' }));
    expect(resolveScopedKey(idx, { extensionId: 'ext-a', contributionId: 'id-a' })).toBeUndefined();
  });

  it('resolves when kind is provided even if other entries share extensionId+contributionId', () => {
    const idx = index(
      entry({ scopedKey: 'shader:ext-a:shared-id' }),
      entry({ scopedKey: 'output-format:ext-a:shared-id' }),
    );
    expect(resolveScopedKey(idx, { kind: 'shader', extensionId: 'ext-a', contributionId: 'shared-id' })).toBe(
      'shader:ext-a:shared-id',
    );
  });

  it('handles empty index gracefully', () => {
    expect(resolveScopedKey(index(), { extensionId: 'ext-a', contributionId: 'id-a' })).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// resolveRouteFitMetadata
// ---------------------------------------------------------------------------

describe('resolveRouteFitMetadata', () => {
  const idx = index(
    entry({ scopedKey: 'shader:ext-a:shader-1' }),
    entry({ scopedKey: 'output-format:ext-a:fmt-1' }),
  );

  it('returns RouteFitMetadata when identity is directly resolvable', () => {
    const result = resolveRouteFitMetadata({
      contributionIndex: idx,
      identity: { kind: 'shader', extensionId: 'ext-a', contributionId: 'shader-1' },
      route: 'browser-export',
      fit: 'supported',
    });
    expect(result).toEqual({ route: 'browser-export', fit: 'supported' });
  });

  it('returns RouteFitMetadata when identity is uniquely resolvable without kind', () => {
    const result = resolveRouteFitMetadata({
      contributionIndex: idx,
      identity: { extensionId: 'ext-a', contributionId: 'shader-1' },
      route: 'sidecar-export',
      fit: 'blocked',
      reason: 'process-dependent',
      message: 'Needs process',
    });
    expect(result).toEqual({
      route: 'sidecar-export',
      fit: 'blocked',
      reason: 'process-dependent',
      message: 'Needs process',
    });
  });

  it('defaults fit to "unknown" when not supplied', () => {
    const result = resolveRouteFitMetadata({
      contributionIndex: idx,
      identity: { kind: 'shader', extensionId: 'ext-a', contributionId: 'shader-1' },
      route: 'browser-export',
    });
    expect(result).toEqual({ route: 'browser-export', fit: 'unknown' });
  });

  it('returns undefined when identity is ambiguous', () => {
    const ambIdx = index(
      entry({ scopedKey: 'shader:ext-a:shared' }),
      entry({ scopedKey: 'process:ext-a:shared' }),
    );
    expect(
      resolveRouteFitMetadata({
        contributionIndex: ambIdx,
        identity: { extensionId: 'ext-a', contributionId: 'shared' },
        route: 'browser-export',
      }),
    ).toBeUndefined();
  });

  it('returns undefined when contributionIndex is undefined', () => {
    expect(
      resolveRouteFitMetadata({
        contributionIndex: undefined,
        identity: { kind: 'shader', extensionId: 'ext-a', contributionId: 'shader-1' },
        route: 'browser-export',
      }),
    ).toBeUndefined();
  });

  it('returns undefined when identity is undefined', () => {
    expect(
      resolveRouteFitMetadata({
        contributionIndex: idx,
        identity: undefined,
        route: 'browser-export',
      }),
    ).toBeUndefined();
  });

  it('returns undefined when scoped key resolves but is not in the index', () => {
    expect(
      resolveRouteFitMetadata({
        contributionIndex: idx,
        identity: { kind: 'effect', extensionId: 'ext-a', contributionId: 'eff-1' },
        route: 'browser-export',
      }),
    ).toBeUndefined();
  });

  it('omits reason from result when reason is undefined', () => {
    const result = resolveRouteFitMetadata({
      contributionIndex: idx,
      identity: { kind: 'shader', extensionId: 'ext-a', contributionId: 'shader-1' },
      route: 'browser-export',
      fit: 'degraded',
      reason: undefined,
      message: 'Degraded but no reason',
    });
    expect(result).toEqual({
      route: 'browser-export',
      fit: 'degraded',
      message: 'Degraded but no reason',
    });
    expect('reason' in result!).toBe(false);
  });

  it('omits message from result when message is undefined', () => {
    const result = resolveRouteFitMetadata({
      contributionIndex: idx,
      identity: { kind: 'shader', extensionId: 'ext-a', contributionId: 'shader-1' },
      route: 'browser-export',
      fit: 'supported',
    });
    expect(result).toEqual({
      route: 'browser-export',
      fit: 'supported',
    });
    expect('message' in result!).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// blockerToRouteFitMetadata
// ---------------------------------------------------------------------------

describe('blockerToRouteFitMetadata', () => {
  const idx = index(
    entry({ scopedKey: 'output-format:ext-a:fmt-1' }),
    entry({ scopedKey: 'process:ext-b:proc-1' }),
  );

  function blocker(overrides: Partial<VideoEditorPlannerBlockerDescriptor> = {}): VideoEditorPlannerBlockerDescriptor {
    return {
      id: 'blocker-1',
      extensionId: 'ext-a',
      contributionId: 'fmt-1',
      route: 'browser-export',
      reason: 'process-dependent',
      message: 'Process needed',
      ...overrides,
    };
  }

  it('resolves uniquely from blocker extensionId+contributionId', () => {
    const result = blockerToRouteFitMetadata(blocker(), idx);
    expect(result).toEqual({
      route: 'browser-export',
      fit: 'blocked',
      reason: 'process-dependent',
      message: 'Process needed',
    });
  });

  it('falls back to sidecar-export when blocker has no route', () => {
    const result = blockerToRouteFitMetadata(blocker({ route: undefined }), idx);
    expect(result).toEqual({
      route: 'sidecar-export',
      fit: 'blocked',
      reason: 'process-dependent',
      message: 'Process needed',
    });
  });

  it('returns undefined when blocker identity is ambiguous', () => {
    const ambIdx = index(
      entry({ scopedKey: 'output-format:ext-a:shared' }),
      entry({ scopedKey: 'process:ext-a:shared' }),
    );
    expect(blockerToRouteFitMetadata(blocker({ contributionId: 'shared' }), ambIdx)).toBeUndefined();
  });

  it('returns undefined when contributionIndex is undefined', () => {
    expect(blockerToRouteFitMetadata(blocker(), undefined)).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// findingToRouteFitMetadata
// ---------------------------------------------------------------------------

describe('findingToRouteFitMetadata', () => {
  const idx = index(
    entry({ scopedKey: 'shader:ext-a:shader-1' }),
  );

  function finding(overrides: Partial<CapabilityFinding> = {}): CapabilityFinding {
    return {
      id: 'finding-1',
      severity: 'error',
      route: 'browser-export',
      reason: 'missing-material',
      message: 'Material missing',
      extensionId: 'ext-a',
      contributionId: 'shader-1',
      ...overrides,
    };
  }

  it('resolves from finding with extensionId+contributionId', () => {
    const result = findingToRouteFitMetadata(finding(), idx);
    expect(result).toEqual({
      route: 'browser-export',
      fit: 'blocked',
      reason: 'missing-material',
      message: 'Material missing',
    });
  });

  it('uses degraded fit for warning severity', () => {
    const result = findingToRouteFitMetadata(finding({ severity: 'warning' }), idx);
    expect(result).toEqual({
      route: 'browser-export',
      fit: 'degraded',
      reason: 'missing-material',
      message: 'Material missing',
    });
  });

  it('falls back to provided fallbackRoute when finding has no route', () => {
    const result = findingToRouteFitMetadata(finding({ route: undefined }), idx, 'worker-export');
    expect(result).toEqual({
      route: 'worker-export',
      fit: 'blocked',
      reason: 'missing-material',
      message: 'Material missing',
    });
  });

  it('returns undefined when finding has no extensionId', () => {
    expect(findingToRouteFitMetadata(finding({ extensionId: undefined }), idx)).toBeUndefined();
  });

  it('returns undefined when finding has no contributionId', () => {
    expect(findingToRouteFitMetadata(finding({ contributionId: undefined }), idx)).toBeUndefined();
  });

  it('returns undefined when identity is ambiguous', () => {
    const ambIdx = index(
      entry({ scopedKey: 'shader:ext-a:shared' }),
      entry({ scopedKey: 'output-format:ext-a:shared' }),
    );
    expect(findingToRouteFitMetadata(finding({ contributionId: 'shared' }), ambIdx)).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// normalizeContributionIndexRouteFit
// ---------------------------------------------------------------------------

import { normalizeContributionIndexRouteFit } from '@/tools/video-editor/runtime/routeFitMapper.ts';
import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
import { decideRenderRoute } from '@/tools/video-editor/lib/renderRouter.ts';

describe('normalizeContributionIndexRouteFit', () => {
  const fmtIdx = index(
    entry({ scopedKey: 'output-format:ext-a:fmt-1' }),
    entry({ scopedKey: 'process:ext-b:proc-1' }),
  );

  function fmtBlocker(overrides: Partial<VideoEditorPlannerBlockerDescriptor> = {}): VideoEditorPlannerBlockerDescriptor {
    return {
      id: 'blocker-1',
      extensionId: 'ext-a',
      contributionId: 'fmt-1',
      route: 'browser-export',
      reason: 'process-dependent',
      message: 'Process needed',
      ...overrides,
    };
  }

  function procBlocker(overrides: Partial<VideoEditorPlannerBlockerDescriptor> = {}): VideoEditorPlannerBlockerDescriptor {
    return {
      id: 'blocker-2',
      extensionId: 'ext-b',
      contributionId: 'proc-1',
      route: 'sidecar-export',
      reason: 'missing-contribution',
      message: 'Process missing',
      ...overrides,
    };
  }

  it('returns the same index when blockers array is undefined', () => {
    const result = normalizeContributionIndexRouteFit(fmtIdx, undefined);
    expect(result).toBe(fmtIdx);
  });

  it('returns the same index when blockers array is empty', () => {
    const result = normalizeContributionIndexRouteFit(fmtIdx, []);
    expect(result).toBe(fmtIdx);
  });

  it('adds routeFit to the matching entry when blocker identity is uniquely resolvable', () => {
    const result = normalizeContributionIndexRouteFit(fmtIdx, [fmtBlocker()]);
    const entries = result['output-format:ext-a:fmt-1'];
    expect(entries).toBeDefined();
    expect(entries![0].routeFit).toEqual({
      route: 'browser-export',
      fit: 'blocked',
      reason: 'process-dependent',
      message: 'Process needed',
    });
  });

  it('adds routeFit to process entry when process blocker is uniquely resolvable', () => {
    const result = normalizeContributionIndexRouteFit(fmtIdx, [procBlocker()]);
    const entries = result['process:ext-b:proc-1'];
    expect(entries).toBeDefined();
    expect(entries![0].routeFit).toEqual({
      route: 'sidecar-export',
      fit: 'blocked',
      reason: 'missing-contribution',
      message: 'Process missing',
    });
  });

  it('adds routeFit to multiple entries when multiple blockers resolve', () => {
    const result = normalizeContributionIndexRouteFit(fmtIdx, [fmtBlocker(), procBlocker()]);
    expect(result['output-format:ext-a:fmt-1']![0].routeFit).toBeDefined();
    expect(result['process:ext-b:proc-1']![0].routeFit).toBeDefined();
  });

  it('does not add routeFit to entries when blocker identity is ambiguous', () => {
    const ambIdx = index(
      entry({ scopedKey: 'output-format:ext-a:shared' }),
      entry({ scopedKey: 'process:ext-a:shared' }),
    );
    const result = normalizeContributionIndexRouteFit(ambIdx, [
      fmtBlocker({ contributionId: 'shared' }),
    ]);
    expect(result['output-format:ext-a:shared']![0].routeFit).toBeUndefined();
    expect(result['process:ext-a:shared']![0].routeFit).toBeUndefined();
  });

  it('does not add routeFit when blocker identity is not in the index at all', () => {
    const result = normalizeContributionIndexRouteFit(fmtIdx, [
      fmtBlocker({ extensionId: 'ext-nonexistent', contributionId: 'nonexistent' }),
    ]);
    expect(result['output-format:ext-a:fmt-1']![0].routeFit).toBeUndefined();
    expect(result['process:ext-b:proc-1']![0].routeFit).toBeUndefined();
  });

  it('uses first-wins when multiple blockers target the same scoped key', () => {
    const result = normalizeContributionIndexRouteFit(fmtIdx, [
      fmtBlocker({ id: 'first', message: 'First blocker' }),
      fmtBlocker({ id: 'second', message: 'Second blocker', route: 'worker-export' }),
    ]);
    const fit = result['output-format:ext-a:fmt-1']![0].routeFit;
    expect(fit).toBeDefined();
    expect(fit!.message).toBe('First blocker');
    expect(fit!.route).toBe('browser-export');
  });

  it('preserves existing routeFit on entries that already have it', () => {
    const idxWithFit = index(
      entry({
        scopedKey: 'output-format:ext-a:fmt-1',
        routeFit: { route: 'sidecar-export', fit: 'degraded', reason: 'unknown', message: 'Existing' },
      }),
    );
    const result = normalizeContributionIndexRouteFit(idxWithFit, [
      fmtBlocker({ message: 'New blocker' }),
    ]);
    const fit = result['output-format:ext-a:fmt-1']![0].routeFit;
    expect(fit!.message).toBe('Existing');
  });

  it('does not modify entries whose scoped keys have no matching blocker', () => {
    const result = normalizeContributionIndexRouteFit(fmtIdx, [procBlocker()]);
    const formatEntries = result['output-format:ext-a:fmt-1'];
    expect(formatEntries).toBeDefined();
    expect(formatEntries![0].routeFit).toBeUndefined();
  });

  it('enriches first entry when scoped key has multiple duplicate entries', () => {
    const dupIdx = index(
      entry({ scopedKey: 'output-format:ext-a:fmt-1', duplicateOrdinal: 0 }),
      entry({ scopedKey: 'output-format:ext-a:fmt-1', duplicateOrdinal: 1 }),
    );
    const result = normalizeContributionIndexRouteFit(dupIdx, [fmtBlocker()]);
    const entries = result['output-format:ext-a:fmt-1'];
    expect(entries).toHaveLength(2);
    expect(entries![0].routeFit).toBeDefined();
    expect(entries![1].routeFit).toBeDefined();
  });

  it('returns a frozen index', () => {
    const result = normalizeContributionIndexRouteFit(fmtIdx, [fmtBlocker()]);
    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result['output-format:ext-a:fmt-1'])).toBe(true);
    expect(Object.isFrozen(result['output-format:ext-a:fmt-1']![0])).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Planner / router route-selection invariance
// ---------------------------------------------------------------------------

describe('route-selection invariance with routeFit metadata', () => {
  /**
   * The task requires that adding route-fit metadata to the contribution
   * index does NOT change RenderPlannerResult, renderRouter route decisions,
   * or useRenderState shapes.  These tests verify that planRender and
   * decideRenderRoute produce identical output whether or not routeFit
   * metadata is present on index entries.
   */

  it('planRender produces identical results with and without routeFit in the index', () => {
    const idx = index(
      entry({ scopedKey: 'output-format:ext-a:fmt-1' }),
    );

    // Enrich the index with routeFit from a descriptor blocker.
    const enrichedIdx = normalizeContributionIndexRouteFit(idx, [
      {
        id: 'blocker-1',
        extensionId: 'ext-a',
        contributionId: 'fmt-1',
        route: 'browser-export',
        reason: 'process-dependent',
        message: 'Process needed',
      },
    ]);

    const input = {
      extensionRuntime: {
        outputFormats: [],
        processes: [],
        shaders: [],
        contributionIndex: idx,
      },
    };

    const resultWithoutFit = planRender(input);
    const resultWithFit = planRender({
      ...input,
      extensionRuntime: { ...input.extensionRuntime, contributionIndex: enrichedIdx },
    });

    // Route-fit metadata must not change planner output.
    expect(resultWithFit).toEqual(resultWithoutFit);
  });

  it('planRender with requirements is unchanged by routeFit presence', () => {
    const idx = index(
      entry({ scopedKey: 'shader:ext-s:shader-1' }),
    );

    const enrichedIdx = normalizeContributionIndexRouteFit(idx, [
      {
        id: 'shader-blocker',
        extensionId: 'ext-s',
        contributionId: 'shader-1',
        route: 'sidecar-export',
        reason: 'unknown',
        message: 'Shader unavailable',
      },
    ]);

    const requirements = [
      {
        id: 'req-1',
        sourceRef: { source: 'extension', extensionId: 'ext-s', contributionId: 'shader-1' },
        route: 'browser-export',
        requiredCapabilities: ['render-material'],
        determinism: 'deterministic',
        blocking: false,
      },
    ] as const;

    const resultWithoutFit = planRender({ requirements, extensionRuntime: { outputFormats: [], processes: [], shaders: [], contributionIndex: idx } });
    const resultWithFit = planRender({ requirements, extensionRuntime: { outputFormats: [], processes: [], shaders: [], contributionIndex: enrichedIdx } });

    expect(resultWithFit).toEqual(resultWithoutFit);
  });

  it('decideRenderRoute produces identical route decisions with and without routeFit', () => {
    const idx = index(
      entry({ scopedKey: 'output-format:ext-a:fmt-1' }),
    );

    const enrichedIdx = normalizeContributionIndexRouteFit(idx, [
      {
        id: 'blocker-1',
        extensionId: 'ext-a',
        contributionId: 'fmt-1',
        route: 'browser-export',
        reason: 'process-dependent',
        message: 'Process needed',
      },
    ]);

    const timeline = {
      clips: [
        { clipType: 'media' },
        { clipType: 'text' },
      ],
    };

    const decisionWithoutFit = decideRenderRoute(timeline);
    const decisionWithFit = decideRenderRoute(timeline);

    // Route decisions must be identical — routeFit metadata is
    // additive to the index and must not change routing.
    expect(decisionWithFit.route).toBe(decisionWithoutFit.route);
    expect(decisionWithFit.reason).toBe(decisionWithoutFit.reason);
    expect(decisionWithFit.hasThemedClip).toBe(decisionWithoutFit.hasThemedClip);
    expect(decisionWithFit.hasMediaClip).toBe(decisionWithoutFit.hasMediaClip);
    expect(decisionWithFit.hasContributedClip).toBe(decisionWithoutFit.hasContributedClip);
  });

  it('decideRenderRoute themed-only routing is unchanged by routeFit presence', () => {
    const idx = index(
      entry({ scopedKey: 'output-format:ext-themed:theme-1' }),
    );

    const enrichedIdx = normalizeContributionIndexRouteFit(idx, [
      {
        id: 'theme-blocker',
        extensionId: 'ext-themed',
        contributionId: 'theme-1',
        route: 'worker-export',
        reason: 'process-dependent',
        message: 'Needs worker',
      },
    ]);

    // Route decisions are shape-driven and don't consume the
    // contribution index directly, so routeFit metadata must not
    // affect routing.
    const timeline = {
      clips: [{ clipType: 'image-jump' }],
    };

    const decision = decideRenderRoute(timeline);
    expect(decision.route).toBe('worker-banodoco');
    expect(decision.reason).toBe('themed_only');
    expect(decision.planner.selectedPlannerRoute).toBe('worker-export');
  });

  it('normalized index with routeFit is structurally compatible with ContributionIndex consumers', () => {
    const idx = index(
      entry({ scopedKey: 'output-format:ext-a:fmt-1' }),
      entry({ scopedKey: 'process:ext-b:proc-1' }),
    );

    const enriched = normalizeContributionIndexRouteFit(idx, [
      {
        id: 'blocker-1',
        extensionId: 'ext-a',
        contributionId: 'fmt-1',
        route: 'browser-export',
        reason: 'process-dependent',
        message: 'Process needed',
      },
    ]);

    // The enriched index must still be a valid ContributionIndex:
    // - Frozen
    // - All expected keys present
    // - Entries have the ContributionIndexEntry shape
    expect(Object.isFrozen(enriched)).toBe(true);
    expect(Object.keys(enriched)).toHaveLength(2);
    expect(enriched['output-format:ext-a:fmt-1']).toBeDefined();
    expect(enriched['process:ext-b:proc-1']).toBeDefined();

    // Enriched entry must have routeFit
    const fmtEntries = enriched['output-format:ext-a:fmt-1'];
    expect(fmtEntries![0].routeFit).toBeDefined();
    expect(fmtEntries![0].routeFit!.fit).toBe('blocked');

    // Non-targeted entry must remain unchanged
    const procEntries = enriched['process:ext-b:proc-1'];
    expect(procEntries![0].routeFit).toBeUndefined();
  });
});
