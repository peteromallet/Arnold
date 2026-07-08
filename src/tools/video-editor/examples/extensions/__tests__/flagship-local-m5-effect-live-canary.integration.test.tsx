import { describe, expect, it } from 'vitest';
import { type TimelineSnapshot } from '@/sdk/index';
import { flagshipLocalExtension } from '@/tools/video-editor/examples/extensions/flagship-local';
import { buildTimelineData } from '@/tools/video-editor/lib/timeline-data.ts';
import { serializeTimelineConfigSnapshot } from '@/tools/video-editor/lib/timeline-domain.ts';
import { createTimelineReader } from '@/tools/video-editor/lib/timeline-reader.ts';
import type {
  ResolvedTimelineConfig,
  TimelineLiveBinding,
  TimelineLiveDeterministicRef,
} from '@/tools/video-editor/types/index.ts';
import { projectCompositionGraph } from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import {
  collectBuiltInKnownIds,
  collectExtensionDeclaredIds,
  scanExportConfig,
} from '@/tools/video-editor/runtime/exportGuard.ts';
import { normalizeExtensionRuntime } from '@/tools/video-editor/runtime/extensionSurface.ts';
import { createLiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
import {
  buildExportReadinessPlan,
  planRender,
} from '@/tools/video-editor/runtime/renderPlanner.ts';

const FLAGSHIP_EXTENSION_ID = 'com.reigh.examples.flagship-local';
const FLAGSHIP_GLOW_CONTRIBUTION_ID = 'flagship-effect-glow';
const FLAGSHIP_GLOW_EFFECT_ID = 'com.reigh.flagship.effect.glow';
const CLIP_ID = 'clip-flagship-glow-live';
const SOURCE_ID = 'source-flagship-glow-live';
const BINDING_ID = 'binding-flagship-glow-intensity';
const CAPTURE_REF_ID = 'capture-flagship-glow-intensity';
const EFFECT_REF_KEY = `effect:${FLAGSHIP_EXTENSION_ID}:${FLAGSHIP_GLOW_CONTRIBUTION_ID}`;
const EFFECT_NODE_ID = `contribution:${EFFECT_REF_KEY}`;
const emptyAssetRegistry = { assets: {} };

function makeBinding(
  overrides: Partial<TimelineLiveBinding> = {},
): TimelineLiveBinding {
  return {
    bindingId: BINDING_ID,
    sourceId: SOURCE_ID,
    sourceKind: 'generated',
    sourceStatus: 'active',
    targetEffectId: FLAGSHIP_GLOW_CONTRIBUTION_ID,
    targetParamName: 'params.intensity',
    targetPath: 'params.intensity',
    ownerExtensionId: FLAGSHIP_EXTENSION_ID,
    ...overrides,
  };
}

function makeConfig(binding: TimelineLiveBinding): ResolvedTimelineConfig {
  return {
    output: { resolution: '1280x720', fps: 30, file: 'flagship-glow-live.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [{
      id: CLIP_ID,
      track: 'V1',
      at: 0,
      hold: 60,
      clipType: 'media',
      effects: [{
        type: FLAGSHIP_GLOW_EFFECT_ID,
        managedBy: FLAGSHIP_EXTENSION_ID,
        params: {
          intensity: 0.35,
          color: '#ff6b6b',
          style: 'glow',
          animate: true,
        },
      }],
      params: {
        liveBindings: [binding],
      },
    }],
    registry: {},
  } as ResolvedTimelineConfig;
}

async function roundTripSnapshot(config: ResolvedTimelineConfig): Promise<TimelineSnapshot> {
  const serialized = serializeTimelineConfigSnapshot(config).config;
  const data = await buildTimelineData(serialized, emptyAssetRegistry);
  return createTimelineReader({ data }).snapshot();
}

function bakeDeterministicCapture(): TimelineLiveDeterministicRef {
  const registry = createLiveDataRegistry({ emitLifecycleDiagnostics: false });
  const handle = registry.registerSource({ id: SOURCE_ID, kind: 'generated' });
  const channelId = registry.openChannel(SOURCE_ID, 'control', { label: 'Flagship Glow Intensity' });
  registry.pushSample(channelId, {
    timestamp: 0,
    format: 'json',
    data: { value: 0.82 },
  });

  const result = registry.bake({
    sourceId: SOURCE_ID,
    channelIds: [channelId],
    targets: [{
      kind: 'deterministic-capture',
      ref: CAPTURE_REF_ID,
      params: {
        captureId: CAPTURE_REF_ID,
        profile: 'event',
        contentHash: 'a'.repeat(64),
        provenanceHash: 'b'.repeat(64),
        routeConstraints: ['preview', 'browser-export'],
        determinism: 'deterministic',
      },
    }],
  });

  expect(result.success).toBe(true);
  expect(result.replacements).toHaveLength(1);
  expect(result.replacements[0]).toEqual(expect.objectContaining({
    capture: expect.objectContaining({
      captureId: CAPTURE_REF_ID,
      profile: 'event',
      routeConstraints: ['preview', 'browser-export'],
      determinism: 'deterministic',
    }),
    deterministicRef: expect.objectContaining({
      kind: 'deterministic-capture',
      ref: CAPTURE_REF_ID,
    }),
  }));

  handle.dispose();
  return result.replacements[0]!.deterministicRef;
}

describe('flagship-local M5 effect/live canary', () => {
  it('proves EX-02 effect consumes, effect-param binds-live, export block before bake, and clearance after bake', async () => {
    const runtime = normalizeExtensionRuntime([flagshipLocalExtension]);
    const builtIn = collectBuiltInKnownIds();
    const extensionIds = collectExtensionDeclaredIds(flagshipLocalExtension.manifest.contributions ?? []);

    const unbakedConfig = makeConfig(makeBinding());
    const unbakedSnapshot = await roundTripSnapshot(unbakedConfig);

    const blockedExport = scanExportConfig(unbakedConfig, builtIn, extensionIds);
    expect(blockedExport.diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: 'export/live-binding-unresolved',
        detail: expect.objectContaining({
          clipId: CLIP_ID,
          bindingId: BINDING_ID,
          sourceId: SOURCE_ID,
          resolutionStatus: 'active',
          path: `clips.${CLIP_ID}.params.liveBindings.0`,
        }),
      }),
    ]));

    const blockedPlanner = buildExportReadinessPlan({
      snapshot: unbakedSnapshot,
      extensionRuntime: runtime,
      guard: blockedExport,
    });
    expect(blockedPlanner.canBrowserExport).toBe(false);
    expect(blockedPlanner.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        route: 'browser-export',
        reason: 'live-unbaked',
      }),
    ]));

    const bakedRef = bakeDeterministicCapture();
    const bakedConfig = makeConfig(makeBinding({
      bake: {
        status: 'complete',
        deterministicRefs: [bakedRef],
      },
    }));
    const bakedSnapshot = await roundTripSnapshot(bakedConfig);
    const graph = projectCompositionGraph({
      snapshot: bakedSnapshot,
      contributionIndex: runtime.contributionIndex,
    });

    expect(graph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'consumes',
        sourceNodeId: `clip:${CLIP_ID}`,
        targetNodeId: EFFECT_NODE_ID,
        detail: expect.objectContaining({
          clipId: CLIP_ID,
          effectType: FLAGSHIP_GLOW_EFFECT_ID,
          consumedKind: 'effect',
          refKey: EFFECT_REF_KEY,
        }),
      }),
      expect.objectContaining({
        kind: 'binds-live',
        sourceNodeId: `clip:${CLIP_ID}`,
        targetNodeId: EFFECT_NODE_ID,
        detail: expect.objectContaining({
          bindingId: BINDING_ID,
          clipId: CLIP_ID,
          sourceId: SOURCE_ID,
          targetKind: 'effect-param',
          targetPath: 'intensity',
          targetEffectId: FLAGSHIP_GLOW_CONTRIBUTION_ID,
          refKey: EFFECT_REF_KEY,
        }),
      }),
    ]));

    const clearedExport = scanExportConfig(
      bakedConfig,
      builtIn,
      extensionIds,
      undefined,
      undefined,
      undefined,
      graph,
    );
    expect(clearedExport.diagnostics.filter((diagnostic) => diagnostic.code === 'export/live-binding-unresolved')).toEqual([]);

    const clearedPlanner = planRender({
      snapshot: bakedSnapshot,
      compositionGraph: graph,
      extensionRuntime: runtime,
    });
    expect(clearedPlanner.canBrowserExport).toBe(true);
    expect(clearedPlanner.blockers.filter((blocker) => blocker.reason === 'live-unbaked')).toEqual([]);
    expect(buildExportReadinessPlan({
      snapshot: bakedSnapshot,
      compositionGraph: graph,
      extensionRuntime: runtime,
      guard: clearedExport,
    }).canBrowserExport).toBe(true);
  });
});
