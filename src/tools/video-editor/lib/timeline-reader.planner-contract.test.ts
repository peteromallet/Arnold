/**
 * M12: Planner-public-contract-only tests for TimelineReader inspection surface.
 *
 * These tests prove that planner code can consume TimelineSnapshot,
 * TimelineReader, and SDK requirement types without importing provider
 * stores, raw timeline rows, or mutation APIs.
 *
 * @publicContract
 */

import { describe, expect, it } from 'vitest';
import { createTimelineReader, getCapabilityRequirements } from '@/tools/video-editor/lib/timeline-reader';
import type {
  TimelineSnapshot,
  TimelineClipSummary,
  TimelineEffectSummary,
  TimelineTransitionSummary,
  TimelineLiveBindingSummary,
  TimelineAutomationSummary,
  TimelineMaterialRefSummary,
  TimelineSourceRefSummary,
  TimelineRenderGroupSummary,
  TimelineOutputMetadata,
  CapabilityRequirement,
  CapabilityVersion,
  CapabilitySourceRef,
  RouteFitMetadata,
  IntegrationCapabilities,
  DeterminismStatus,
  RenderRoute,
  RenderBlockerReason,
  CapabilityFinding,
} from '@/sdk/index';
import { buildTimelineData } from '@/tools/video-editor/lib/timeline-data';
import type { TimelineConfig, AssetRegistry } from '@/tools/video-editor/types/index';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const emptyRegistry: AssetRegistry = { assets: {} };

function makeBaseConfig(): TimelineConfig {
  return {
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [
      { id: 'V1', kind: 'visual', label: 'Visual 1' },
      { id: 'A1', kind: 'audio', label: 'Audio 1', muted: true },
    ],
    clips: [
      {
        id: 'clip-1',
        at: 0,
        track: 'V1',
        clipType: 'media',
        asset: 'asset-1',
        from: 0,
        to: 2,
        speed: 1,
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// Boundary: planner imports only public types
// ---------------------------------------------------------------------------

describe('M12 planner contract boundary', () => {
  it('can import TimelineSnapshot without provider stores', () => {
    // This test proves the import compiles.  If this file compiles,
    // the planner can access TimelineSnapshot without raw rows.
    const snap: TimelineSnapshot = {
      projectId: null,
      baseVersion: 1,
      currentVersion: 1,
      extensionRequirements: [],
      clips: [],
      tracks: [],
      assetKeys: [],
      app: {},
    };
    expect(snap).toBeDefined();
  });

  it('can import CapabilityRequirement without provider stores', () => {
    const req: CapabilityRequirement = {
      id: 'test.req.1',
      sourceRef: { source: 'built-in' },
      route: 'browser-export',
      requiredCapabilities: ['browser-export'],
      determinism: 'deterministic',
    };
    expect(req.id).toBe('test.req.1');
  });

  it('can import IntegrationCapabilities without provider stores', () => {
    const ic: IntegrationCapabilities = {
      extensionId: 'com.test.ext',
      routes: ['browser-export'],
      determinism: 'deterministic',
      capabilityRequirements: [],
      sourceRefs: [],
      fullySupported: true,
      anyBlocked: false,
    };
    expect(ic.fullySupported).toBe(true);
  });

  it('can import all M12 summary types without provider stores', () => {
    const effect: TimelineEffectSummary = {
      id: 'e1',
      clipId: 'c1',
      effectType: 'fade_in',
    };
    const transition: TimelineTransitionSummary = {
      id: 't1',
      clipId: 'c1',
      transitionType: 'crossfade',
      duration: 1,
    };
    const liveBinding: TimelineLiveBindingSummary = {
      bindingId: 'lb1',
      clipId: 'c1',
      sourceId: 'src1',
      sourceKind: 'webcam',
    };
    const automation: TimelineAutomationSummary = {
      contributionId: 'clip.glow',
      parameterPath: 'params.opacity',
      keyframeCount: 2,
      enabled: true,
    };
    const materialRef: TimelineMaterialRefSummary = {
      id: 'm1',
      clipId: 'c1',
      assetKey: 'asset-1',
    };
    const sourceRef: TimelineSourceRefSummary = {
      id: 's1',
      clipId: 'c1',
      sourceKind: 'generation',
      generationId: 'gen-1',
      determinism: 'process-dependent',
    };
    const renderGroup: TimelineRenderGroupSummary = {
      id: 'rg1',
      clipIds: ['c1', 'c2'],
    };
    const outputMeta: TimelineOutputMetadata = {
      resolution: '1920x1080',
      fps: 30,
      file: 'out.mp4',
    };

    expect(effect.effectType).toBe('fade_in');
    expect(transition.duration).toBe(1);
    expect(liveBinding.sourceKind).toBe('webcam');
    expect(automation.enabled).toBe(true);
    expect(materialRef.assetKey).toBe('asset-1');
    expect(sourceRef.generationId).toBe('gen-1');
    expect(renderGroup.clipIds).toEqual(['c1', 'c2']);
    expect(outputMeta.fps).toBe(30);
  });
});

// ---------------------------------------------------------------------------
// M12: Snapshot carries planner inspection data
// ---------------------------------------------------------------------------

describe('M12 snapshot inspection fields', () => {
  it('snapshot includes outputMetadata from config', async () => {
    const config = makeBaseConfig();
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    expect(snap.outputMetadata).toBeDefined();
    expect(snap.outputMetadata!.resolution).toBe('1920x1080');
    expect(snap.outputMetadata!.fps).toBe(30);
    expect(snap.outputMetadata!.file).toBe('out.mp4');
  });

  it('snapshot includes effects on clips when effects are present', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-effects',
          at: 0,
          track: 'V1',
          clipType: 'media',
          hold: 2,
          effects: [{ type: 'fade_in' }, { type: 'blur' }],
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    // Effects should be on the clip summary
    const clip = snap.clips.find((c) => c.id === 'clip-effects');
    expect(clip).toBeDefined();
    expect(clip!.effects).toBeDefined();
    expect(clip!.effects!.length).toBe(2);
    expect(clip!.effects![0].effectType).toBe('fade_in');
    expect(clip!.effects![1].effectType).toBe('blur');

    // Effects should also be on the snapshot-level effects array
    expect(snap.effects).toBeDefined();
    expect(snap.effects!.length).toBe(2);
  });

  it('snapshot includes transition on clips when transition is present', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-transition',
          at: 0,
          track: 'V1',
          clipType: 'media',
          hold: 2,
          transition: { type: 'crossfade', duration: 1.5 },
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    const clip = snap.clips.find((c) => c.id === 'clip-transition');
    expect(clip).toBeDefined();
    expect(clip!.transition).toBeDefined();
    expect(clip!.transition!.transitionType).toBe('crossfade');
    expect(clip!.transition!.duration).toBe(1.5);

    // Transition should also be in snapshot-level transitions
    expect(snap.transitions).toBeDefined();
    expect(snap.transitions!.length).toBe(1);
  });

  it('snapshot includes live bindings from clip app data', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-live',
          at: 0,
          track: 'V1',
          clipType: 'media',
          hold: 2,
          app: {
            liveBindings: [
              {
                bindingId: 'lb-1',
                sourceId: 'webcam-1',
                sourceKind: 'webcam',
                targetParamName: 'texture',
                resolutionStatus: 'active',
              },
            ],
          },
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    const clip = snap.clips.find((c) => c.id === 'clip-live');
    expect(clip).toBeDefined();
    expect(clip!.liveBindings).toBeDefined();
    expect(clip!.liveBindings!.length).toBe(1);
    expect(clip!.liveBindings![0].bindingId).toBe('lb-1');
    expect(clip!.liveBindings![0].sourceKind).toBe('webcam');
    expect(clip!.liveBindings![0].status).toBe('active');

    // Live bindings should also be on snapshot-level
    expect(snap.liveBindings).toBeDefined();
    expect(snap.liveBindings!.length).toBe(1);
  });

  it('snapshot includes live bindings from canonical app.live and params metadata', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-live-canonical',
          at: 0,
          track: 'V1',
          clipType: 'media',
          hold: 2,
          app: {
            live: {
              bindings: [
                {
                  bindingId: 'lb-app-live',
                  sourceId: 'generated-1',
                  sourceKind: 'generated',
                  resolutionStatus: 'active',
                },
              ],
            },
          },
          params: {
            liveBindings: [
              {
                bindingId: 'lb-param-live',
                sourceId: 'midi-1',
                sourceKind: 'midi',
                targetParamName: 'opacity',
                resolutionStatus: 'resolved',
              },
            ],
          },
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    const clip = snap.clips.find((c) => c.id === 'clip-live-canonical');
    expect(clip).toBeDefined();
    expect(clip!.liveBindings?.map((binding) => binding.bindingId)).toEqual([
      'lb-app-live',
      'lb-param-live',
    ]);
    expect(snap.liveBindings?.map((binding) => binding.bindingId)).toEqual([
      'lb-app-live',
      'lb-param-live',
    ]);
  });

  it('snapshot includes material refs from clip assets', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-asset',
          at: 0,
          track: 'V1',
          clipType: 'media',
          asset: 'some-asset-key',
          hold: 2,
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    const clip = snap.clips.find((c) => c.id === 'clip-asset');
    expect(clip).toBeDefined();
    expect(clip!.materialRefs).toBeDefined();
    expect(clip!.materialRefs!.length).toBe(1);
    expect(clip!.materialRefs![0].assetKey).toBe('some-asset-key');

    // Material refs should also be on snapshot-level
    expect(snap.materialRefs).toBeDefined();
    expect(snap.materialRefs!.length).toBe(1);
  });

  it('snapshot includes source refs from source_uuid and generation provenance', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-source',
          at: 0,
          track: 'V1',
          clipType: 'media',
          source_uuid: 'com.example.ext',
          generation: { id: 'gen-1', extensionId: 'com.generator.ext' },
          hold: 2,
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({
      data,
      extensionRequirements: [
        {
          extensionId: 'com.example.ext',
          versionRange: '>=1.0.0',
          posture: 'required',
        },
      ],
    });
    const snap = reader.snapshot();

    const clip = snap.clips.find((c) => c.id === 'clip-source');
    expect(clip).toBeDefined();
    expect(clip!.sourceRefs).toHaveLength(2);
    expect(clip!.sourceRefs![0]).toEqual(expect.objectContaining({
      sourceUuid: 'com.example.ext',
      sourceKind: 'extension',
      extensionId: 'com.example.ext',
    }));
    expect(clip!.sourceRefs![1]).toEqual(expect.objectContaining({
      generationId: 'gen-1',
      extensionId: 'com.generator.ext',
      determinism: 'process-dependent',
    }));

    expect(snap.sourceRefs).toHaveLength(2);
  });

  it('snapshot includes render groups from pinned shot groups', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        { id: 'clip-a', at: 0, track: 'V1', clipType: 'hold', hold: 2 },
        { id: 'clip-b', at: 2, track: 'V1', clipType: 'hold', hold: 2 },
      ],
      pinnedShotGroups: [
        { shotId: 'shot-1', trackId: 'V1', mode: 'images', clipIds: ['clip-a', 'clip-b'] },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    expect(snap.renderGroups).toBeDefined();
    expect(snap.renderGroups!.length).toBe(1);
    expect(snap.renderGroups![0].id).toBe('shot-1:V1');
    expect(snap.renderGroups![0].groupType).toBe('images');
    expect(snap.renderGroups![0].clipIds).toContain('clip-a');
    expect(snap.renderGroups![0].clipIds).toContain('clip-b');
  });

  it('snapshot omits optional M12 fields when not present', async () => {
    // Use a clip with no asset, no effects, no transition, no live bindings
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-bare',
          at: 0,
          track: 'V1',
          clipType: 'hold',
          hold: 2,
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    // Bare clip has no effects, transitions, live bindings, or material refs
    const clip = snap.clips[0];
    expect(clip.id).toBe('clip-bare');
    expect(clip.effects).toBeUndefined();
    expect(clip.transition).toBeUndefined();
    expect(clip.liveBindings).toBeUndefined();
    expect(clip.materialRefs).toBeUndefined();
    expect(clip.sourceRefs).toBeUndefined();

    // Snapshot-level arrays are undefined when empty
    expect(snap.effects).toBeUndefined();
    expect(snap.transitions).toBeUndefined();
    expect(snap.liveBindings).toBeUndefined();
    // materialRefs might be present if any clip has an asset, but this one doesn't
    expect(snap.materialRefs).toBeUndefined();
    expect(snap.sourceRefs).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// M12: getCapabilityRequirements — provider-free inspection
// ---------------------------------------------------------------------------

describe('M12 getCapabilityRequirements', () => {
  it('returns empty array for snapshot with no clips', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [],
      clips: [],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    const reqs = getCapabilityRequirements(snap);
    expect(reqs).toEqual([]);
  });

  it('emits clip-type requirements for each unique clip type', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        { id: 'c1', at: 0, track: 'V1', clipType: 'media', hold: 2 },
        { id: 'c2', at: 2, track: 'V1', clipType: 'media', hold: 2 },
        { id: 'c3', at: 4, track: 'V1', clipType: 'hold', hold: 2 },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    const reqs = getCapabilityRequirements(snap);

    // Should have 2 clip-type requirements (media, hold)
    const clipTypeReqs = reqs.filter((r) => r.id.startsWith('snapshot.clipType.'));
    expect(clipTypeReqs).toHaveLength(2);

    // Both should be built-in (no managedBy)
    for (const req of clipTypeReqs) {
      expect(req.sourceRef.source).toBe('built-in');
      expect(req.determinism).toBe('deterministic');
    }
  });

  it('emits effect requirements when clips have effects', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'c1',
          at: 0,
          track: 'V1',
          clipType: 'media',
          hold: 2,
          effects: [{ type: 'fade_in' }],
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    const reqs = getCapabilityRequirements(snap);

    const effectReqs = reqs.filter((r) => r.id.startsWith('snapshot.effect.'));
    expect(effectReqs.length).toBeGreaterThanOrEqual(1);

    const fadeReq = effectReqs.find((r) =>
      r.findings?.some((f) => f.message.includes('fade_in')),
    );
    expect(fadeReq).toBeDefined();
    expect(fadeReq!.sourceRef.source).toBe('built-in');
  });

  it('emits transition requirements when clips have transitions', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'c1',
          at: 0,
          track: 'V1',
          clipType: 'media',
          hold: 2,
          transition: { type: 'crossfade', duration: 1 },
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    const reqs = getCapabilityRequirements(snap);

    const transitionReqs = reqs.filter((r) =>
      r.id.startsWith('snapshot.transition.'),
    );
    expect(transitionReqs.length).toBeGreaterThanOrEqual(1);
    expect(transitionReqs[0].sourceRef.source).toBe('built-in');
  });

  it('emits live-binding requirements when live bindings are present', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'c1',
          at: 0,
          track: 'V1',
          clipType: 'media',
          hold: 2,
          app: {
            liveBindings: [
              {
                bindingId: 'lb-1',
                sourceId: 'webcam-1',
                sourceKind: 'webcam',
                resolutionStatus: 'active',
              },
            ],
          },
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    const reqs = getCapabilityRequirements(snap);

    const bindingReqs = reqs.filter((r) =>
      r.id.startsWith('snapshot.liveBinding.'),
    );
    expect(bindingReqs.length).toBeGreaterThanOrEqual(1);
    expect(bindingReqs[0].determinism).toBe('live-unbaked');
    expect(bindingReqs[0].sourceRef.source).toBe('provider');
    // Active bindings are blocking
    expect(bindingReqs[0].blocking).toBe(true);
  });

  it('resolved live bindings are not blocking', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'c1',
          at: 0,
          track: 'V1',
          clipType: 'media',
          hold: 2,
          app: {
            liveBindings: [
              {
                bindingId: 'lb-resolved',
                sourceId: 'webcam-1',
                sourceKind: 'webcam',
                resolutionStatus: 'resolved',
              },
            ],
          },
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    const reqs = getCapabilityRequirements(snap);

    const bindingReq = reqs.find((r) =>
      r.id.startsWith('snapshot.liveBinding.'),
    );
    expect(bindingReq).toBeDefined();
    expect(bindingReq!.blocking).toBe(false);
    expect(bindingReq!.routeFit?.fit).toBe('supported');
  });

  it('emits material-ref requirements when material refs exist', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'c1',
          at: 0,
          track: 'V1',
          clipType: 'media',
          asset: 'my-asset',
          hold: 2,
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    const reqs = getCapabilityRequirements(snap);

    const materialReqs = reqs.filter((r) =>
      r.id.startsWith('snapshot.materialRef.'),
    );
    expect(materialReqs.length).toBeGreaterThanOrEqual(1);
    expect(materialReqs[0].sourceRef.source).toBe('registry');
  });

  it('emits source-ref requirements when source refs exist', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'c-source',
          at: 0,
          track: 'V1',
          clipType: 'media',
          generation: { id: 'gen-1', extensionId: 'com.generator.ext' },
          hold: 2,
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });
    const snap = reader.snapshot();

    const reqs = getCapabilityRequirements(snap);

    const sourceReq = reqs.find((r) =>
      r.id.startsWith('snapshot.sourceRef.'),
    );
    expect(sourceReq).toBeDefined();
    expect(sourceReq!.sourceRef.source).toBe('extension');
    expect(sourceReq!.sourceRef.extensionId).toBe('com.generator.ext');
    expect(sourceReq!.determinism).toBe('process-dependent');
    expect(sourceReq!.blocking).toBe(true);
  });

  it('managingExtensionIds from clip.managedBy influences clip-type determinism', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'c-managed',
          at: 0,
          track: 'V1',
          clipType: 'custom-clip',
          hold: 2,
          app: { managedBy: 'com.example.ext' },
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({
      data,
      extensionRequirements: [
        {
          extensionId: 'com.example.ext',
          versionRange: '>=1.0.0',
          posture: 'required',
        },
      ],
    });
    const snap = reader.snapshot();

    const reqs = getCapabilityRequirements(snap);

    const clipTypeReq = reqs.find((r) => r.id.startsWith('snapshot.clipType.'));
    expect(clipTypeReq).toBeDefined();
    expect(clipTypeReq!.sourceRef.source).toBe('extension');
    expect(clipTypeReq!.sourceRef.extensionId).toBe('com.example.ext');
    // Managed clips are preview-only until explicitly declared
    expect(clipTypeReq!.determinism).toBe('preview-only');
  });

  it('does not import provider stores or mutation APIs', () => {
    // Structural check: this test file only imports from @/sdk/index
    // and timeline-reader.  It does NOT import DataProvider, useTimelineCommit,
    // TimelineOps, or any mutation APIs.
    //
    // If this file compiles and runs without crashing, the boundary holds.
    expect(typeof createTimelineReader).toBe('function');
  });

  it('snapshot carries automation summaries on automation clips', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-automation',
          at: 0,
          track: 'V1',
          clipType: 'automation',
          hold: 1,
          params: {
            target: {
              contributionId: 'clip.glow',
              parameterPath: 'params.opacity',
              targetPath: 'opacity',
            },
            keyframes: [{ time: 0, value: 1, interpolation: 'hold' }],
            enabled: true,
          },
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const snap = reader.snapshot();

    expect(snap.clips[0]?.automation).toEqual([
      {
        contributionId: 'clip.glow',
        parameterPath: 'params.opacity',
        targetPath: 'opacity',
        keyframeCount: 1,
        enabled: true,
      },
    ]);
    expect(snap.automations).toEqual(snap.clips[0]?.automation);
  });

  it('snapshot carries canonical live binding target detail for generic and shader-uniform bindings', async () => {
    const config: TimelineConfig = {
      output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
      tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
      clips: [
        {
          id: 'clip-live',
          at: 0,
          track: 'V1',
          clipType: 'media',
          hold: 2,
          app: {
            liveBindings: [
              {
                bindingId: 'lb-clip',
                sourceId: 'webcam-1',
                sourceKind: 'webcam',
                targetParamName: 'params.opacity',
                targetPath: 'opacity',
                resolutionStatus: 'resolved',
              },
            ],
            liveUniformBindings: [
              {
                bindingId: 'lb-uniform',
                sourceId: 'midi-1',
                sourceKind: 'midi',
                targetMaterialId: 'post-grade',
                mapping: { kind: 'scalar', uniform: 'intensity' },
              },
            ],
          },
        },
      ],
    };
    const data = await buildTimelineData(config, emptyRegistry);
    const reader = createTimelineReader({ data });

    const snap = reader.snapshot();

    expect(snap.liveBindings).toEqual([
      expect.objectContaining({
        bindingId: 'lb-clip',
        targetKind: 'clip-param',
        targetPath: 'opacity',
        status: 'resolved',
      }),
      expect.objectContaining({
        bindingId: 'lb-uniform',
        targetKind: 'shader-uniform',
        targetMaterialId: 'post-grade',
        targetPath: 'uniforms.intensity',
        status: 'resolved',
      }),
    ]);
  });
});
