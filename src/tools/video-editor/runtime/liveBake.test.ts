import { describe, expect, it } from 'vitest';
import type { TimelineSnapshot } from '@reigh/editor-sdk';
import type {
  LiveBakeSelection,
  LiveChannelDescriptor,
  LiveSample,
  LiveSource,
} from '@reigh/editor-sdk';
import type { ContributionIndex, ContributionIndexEntry } from '@/tools/video-editor/runtime/extensionSurface.ts';
import type {
  ClipKeyframe,
  DeterministicCapture,
} from '@/tools/video-editor/types/index.ts';
import {
  hashCaptureBody,
  validateDeterministicCapture,
} from '@/tools/video-editor/runtime/deterministicCapture.ts';
import { projectCompositionGraph, type CompositionGraphInput } from '@/tools/video-editor/runtime/composition/graphProjector.ts';
import {
  bakeLiveSource,
  convertAcceptedEventTablesToGraphPreviewOperations,
  convertAcceptedEventTablesWithConversionDetail,
  validateConversionPreviewReadiness,
  withAcceptedEventTableGraphPreview,
} from '@/tools/video-editor/runtime/liveBake';

const source: LiveSource = {
  id: 'src-live',
  kind: 'generated',
  status: 'active',
  diagnostics: [],
};

function sample(
  channelId: LiveChannelDescriptor,
  sequenceNumber: number,
  timestamp: number,
  data: Record<string, unknown> | Uint8Array = { value: sequenceNumber },
  metadata?: Record<string, unknown>,
): LiveSample {
  return {
    channelId,
    sequenceNumber,
    frame: {
      timestamp,
      data,
      format: data instanceof Uint8Array ? 'raw' : 'json',
      metadata,
    },
  };
}

type HostClipSummary = TimelineSnapshot['clips'][number] & {
  keyframes?: Record<string, ClipKeyframe[]>;
};

function keyframe(
  time: number,
  value: number | string | boolean,
  interpolation: ClipKeyframe['interpolation'] = 'linear',
): ClipKeyframe {
  return { time, value, interpolation };
}

function automationClip(overrides: Partial<HostClipSummary> = {}): HostClipSummary {
  return {
    id: 'clip-automation',
    track: 'V1',
    at: 0,
    clipType: 'automation',
    duration: 24,
    managed: false,
    automation: [{
      contributionId: 'glow',
      parameterPath: 'params.opacity',
      targetPath: 'opacity',
      keyframeCount: 1,
      enabled: true,
    }],
    keyframes: {
      opacity: [keyframe(0, 0.2)],
    },
    ...overrides,
  };
}

function timelineSnapshot(clips: HostClipSummary[]): TimelineSnapshot {
  return {
    projectId: 'project-1',
    baseVersion: 1,
    currentVersion: 1,
    extensionRequirements: [],
    clips,
    tracks: [],
    assetKeys: [],
    app: {},
    shaders: [],
  };
}

function indexEntry(
  scopedKey: string,
  overrides: Partial<ContributionIndexEntry> = {},
): ContributionIndexEntry {
  const [kind, extensionId, contributionId] = scopedKey.split(':');
  return {
    scopedKey,
    kind: kind!,
    extensionId: extensionId!,
    contributionId: contributionId!,
    status: overrides.status ?? 'active',
    packageState: overrides.packageState,
    diagnostics: overrides.diagnostics ?? [],
    duplicateOrdinal: overrides.duplicateOrdinal ?? 0,
    projectionEligible: overrides.projectionEligible ?? true,
    projection: overrides.projection ?? {
      duplicateOrdinal: overrides.duplicateOrdinal ?? 0,
      eligible: overrides.projectionEligible ?? true,
      projected: true,
      source: 'descriptor-array',
    },
    renderId: overrides.renderId,
    routeFit: overrides.routeFit,
    resolutionPolicy: overrides.resolutionPolicy,
  };
}

function contributionIndex(): ContributionIndex {
  return {
    'effect:com.example.effects:glow': [
      indexEntry('effect:com.example.effects:glow'),
    ],
  };
}

function graphInput(clip: HostClipSummary): CompositionGraphInput {
  return {
    snapshot: timelineSnapshot([clip]),
    contributionIndex: contributionIndex(),
  };
}

async function acceptedEventTableSource() {
  const capture: DeterministicCapture = {
    captureId: 'capture-evt-001',
    profile: 'event',
    provenance: {
      capturedAt: '2026-07-04T00:00:00.000Z',
      producerExtensionId: 'ext.live',
    },
    contentHash: '',
    routeConstraints: ['preview'],
    determinism: 'deterministic',
    body: {
      profile: 'event',
      defaultCollisionPolicy: 'replace',
      events: [{
        eventId: 'evt-1',
        time: 12,
        targetPath: 'params.opacity',
        value: 0.8,
        interpolation: 'linear',
      }],
    },
  };
  capture.contentHash = await hashCaptureBody(capture.body);
  const validation = await validateDeterministicCapture(capture);
  if (!validation.valid || !validation.ref) {
    throw new Error('Expected deterministic capture validation to succeed.');
  }

  const channelId = 'src-live:control' as LiveChannelDescriptor;
  const bakeResult = bakeLiveSource({
    selection: {
      sourceId: source.id,
      targets: [{
        kind: 'deterministic-capture',
        ref: capture.captureId,
        params: {
          captureId: capture.captureId,
          profile: capture.profile,
          contentHash: capture.contentHash,
          provenanceHash: validation.ref.provenanceHash,
          routeConstraints: capture.routeConstraints,
          determinism: capture.determinism,
        },
      }],
    },
    source,
    bindingIds: ['binding-capture'],
    channels: [{
      metadata: { channelId, sourceId: source.id, kind: 'control' },
      samples: [sample(channelId, 0, 0, { value: 42 })],
    }],
  });

  return {
    capture,
    captureRef: validation.ref,
    replacement: bakeResult.replacements[0]!,
  };
}

describe('liveBake planner', () => {
  it('fully bakes frame samples to deterministic asset replacement metadata', () => {
    const channelId = 'src-live:video' as LiveChannelDescriptor;
    const selection: LiveBakeSelection = {
      sourceId: source.id,
      channelIds: [channelId],
      targets: [{ kind: 'asset', ref: 'asset-live-frame' }],
    };

    const result = bakeLiveSource({
      selection,
      source,
      bindingIds: ['binding-frame'],
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'video' },
        samples: [
          sample(channelId, 0, 100, new Uint8Array([1, 2])),
          sample(channelId, 1, 200, new Uint8Array([3, 4])),
        ],
      }],
    });

    expect(result.success).toBe(true);
    expect(result.targets[0].outputRef).toBe('asset-live-frame');
    expect(result.replacements).toHaveLength(1);
    expect(result.replacements[0].bindingIds).toEqual(['binding-frame']);
    expect(result.replacements[0].deterministicRef).toMatchObject({
      kind: 'asset',
      ref: 'asset-live-frame',
      metadata: {
        liveBake: {
          sourceId: source.id,
          targetKind: 'asset',
          sampleCount: 2,
          firstTimestamp: 100,
          lastTimestamp: 200,
        },
      },
    });
    expect(result.replacements[0].input.inputHash).toMatch(/^fnv1a-[0-9a-f]{8}$/);
    expect(result.diagnostics.some((diagnostic) => diagnostic.code === 'live/bake-complete')).toBe(true);
  });

  it('bakes audio and controller channels to keyframe, automation, and sidecar refs', () => {
    const audioChannelId = 'src-live:audio' as LiveChannelDescriptor;
    const controlChannelId = 'src-live:control' as LiveChannelDescriptor;

    const result = bakeLiveSource({
      selection: {
        sourceId: source.id,
        targets: [
          { kind: 'keyframe', ref: 'clip-1:opacity' },
          { kind: 'automation', ref: 'automation-live-volume' },
          { kind: 'sidecar', ref: 'sidecar-live-analysis' },
        ],
      },
      source,
      channels: [
        {
          metadata: { channelId: audioChannelId, sourceId: source.id, kind: 'audio' },
          samples: [sample(audioChannelId, 0, 0, { rms: 0.1 }), sample(audioChannelId, 1, 16, { rms: 0.2 })],
        },
        {
          metadata: { channelId: controlChannelId, sourceId: source.id, kind: 'control' },
          samples: [sample(controlChannelId, 0, 0, { knob: 0.5 })],
        },
      ],
    });

    expect(result.success).toBe(true);
    expect(result.targets.map((target) => target.outputRef)).toEqual([
      'clip-1:opacity',
      'automation-live-volume',
      'sidecar-live-analysis',
    ]);
    expect(result.replacements.map((replacement) => replacement.deterministicRef.kind)).toEqual([
      'keyframe',
      'automation',
      'sidecar',
    ]);
    expect(result.replacements[0].input.sampleCount).toBe(3);
  });

  it('bakes material destinations to RenderMaterial replacement refs', () => {
    const channelId = 'src-live:video' as LiveChannelDescriptor;

    const result = bakeLiveSource({
      selection: {
        sourceId: source.id,
        targets: [{
          kind: 'render-material',
          ref: 'material-live-frame',
          params: { producerExtensionId: 'ext.live', producerVersion: '1.2.3' },
        }],
      },
      source,
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'video' },
        samples: [sample(channelId, 0, 0, new Uint8Array([7, 8, 9]))],
      }],
    });

    expect(result.success).toBe(true);
    expect(result.replacements[0].deterministicRef.kind).toBe('render-material');
    expect(result.replacements[0].renderMaterial).toMatchObject({
      id: 'material-live-frame',
      mediaKind: 'video',
      determinism: 'deterministic',
      replacementPolicy: 'replace-live-ref',
      producerExtensionId: 'ext.live',
      producerVersion: '1.2.3',
    });
    expect(result.replacements[0].renderMaterial?.locator.uri).toBe('live-bake://src-live/material-live-frame');
  });

  it('partially bakes by frame, time, sample-index range, and take ID', () => {
    const channelId = 'src-live:video' as LiveChannelDescriptor;

    const result = bakeLiveSource({
      selection: {
        sourceId: source.id,
        channelIds: [channelId],
        timeRange: [100, 300],
        frameRange: [10, 12],
        sampleRange: [1, 3],
        takeId: 'take-a',
        targets: [{ kind: 'asset', ref: 'asset-live-partial' }],
      },
      source,
      bindingIds: ['binding-partial'],
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'video' },
        samples: [
          sample(channelId, 0, 100, new Uint8Array([0]), { frameIndex: 10, takeId: 'take-a' }),
          sample(channelId, 1, 120, new Uint8Array([1]), { frameIndex: 11, takeId: 'take-a' }),
          sample(channelId, 2, 240, new Uint8Array([2]), { frameIndex: 12, takeId: 'take-a' }),
          sample(channelId, 3, 280, new Uint8Array([3]), { frameIndex: 13, takeId: 'take-a' }),
          sample(channelId, 4, 300, new Uint8Array([4]), { frameIndex: 12, takeId: 'take-b' }),
        ],
      }],
    });

    expect(result.success).toBe(true);
    expect(result.replacements).toHaveLength(1);
    expect(result.replacements[0].input).toMatchObject({
      sampleCount: 2,
      firstTimestamp: 120,
      lastTimestamp: 240,
      range: {
        start: 100,
        end: 300,
        startFrame: 10,
        endFrame: 12,
        startSample: 1,
        endSample: 3,
        takeId: 'take-a',
      },
    });
    expect(result.replacements[0].deterministicRef).toMatchObject({
      kind: 'asset',
      ref: 'asset-live-partial',
      range: {
        start: 100,
        end: 300,
        startFrame: 10,
        endFrame: 12,
        startSample: 1,
        endSample: 3,
        takeId: 'take-a',
      },
      metadata: {
        liveBake: {
          partial: true,
          sampleCount: 2,
        },
      },
    });
  });

  it('carries validated deterministic-capture ref and provenance metadata while avoiding RenderMaterialRef', () => {
    const channelId = 'src-live:control' as LiveChannelDescriptor;

    const result = bakeLiveSource({
      selection: {
        sourceId: source.id,
        targets: [{
          kind: 'deterministic-capture',
          ref: 'capture-evt-001',
          params: {
            captureId: 'capture-evt-001',
            profile: 'event',
            contentHash: 'a'.repeat(64),
            provenanceHash: 'b'.repeat(64),
            routeConstraints: ['preview', 'browser-export'],
            determinism: 'deterministic',
          },
        }],
      },
      source,
      bindingIds: ['binding-capture'],
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'control' },
        samples: [sample(channelId, 0, 0, { value: 42 })],
      }],
    });

    expect(result.success).toBe(true);
    expect(result.replacements).toHaveLength(1);
    const replacement = result.replacements[0];

    // Core replacement shape — capture ref is baked through.
    expect(replacement.bindingIds).toEqual(['binding-capture']);
    expect(replacement.outputRef).toBe('capture-evt-001');
    expect(replacement.deterministicRef.kind).toBe('deterministic-capture');
    expect(replacement.deterministicRef.ref).toBe('capture-evt-001');

    // No RenderMaterialRef for deterministic-capture targets.
    expect(replacement.renderMaterial).toBeUndefined();

    // Capture metadata is carried through.
    expect(replacement.capture).toBeDefined();
    expect(replacement.capture!.captureId).toBe('capture-evt-001');
    expect(replacement.capture!.profile).toBe('event');
    expect(replacement.capture!.contentHash).toBe('a'.repeat(64));
    expect(replacement.capture!.provenanceHash).toBe('b'.repeat(64));
    expect(replacement.capture!.routeConstraints).toEqual(['preview', 'browser-export']);
    expect(replacement.capture!.determinism).toBe('deterministic');

    // Deterministic ref metadata is enriched with capture provenance.
    const dcapMeta = replacement.deterministicRef.metadata?.deterministicCapture as Record<string, unknown> | undefined;
    expect(dcapMeta).toBeDefined();
    expect(dcapMeta?.captureId).toBe('capture-evt-001');
    expect(dcapMeta?.profile).toBe('event');
    expect(dcapMeta?.provenanceHash).toBe('b'.repeat(64));
    expect(dcapMeta?.determinism).toBe('deterministic');

    // Live bake metadata still present alongside capture metadata.
    const liveBakeMeta = replacement.deterministicRef.metadata?.liveBake as Record<string, unknown> | undefined;
    expect(liveBakeMeta).toBeDefined();
    expect(liveBakeMeta?.targetKind).toBe('deterministic-capture');
    expect(liveBakeMeta?.sourceId).toBe(source.id);
    expect(liveBakeMeta?.sampleCount).toBe(1);
  });

  it('omits capture metadata when deterministic-capture target params are incomplete', () => {
    const channelId = 'src-live:control' as LiveChannelDescriptor;

    const result = bakeLiveSource({
      selection: {
        sourceId: source.id,
        targets: [{
          kind: 'deterministic-capture',
          ref: 'capture-incomplete',
          params: {
            // Missing required fields: contentHash, provenanceHash, etc.
            captureId: 'capture-incomplete',
          },
        }],
      },
      source,
      channels: [{
        metadata: { channelId, sourceId: source.id, kind: 'control' },
        samples: [sample(channelId, 0, 0, { value: 1 })],
      }],
    });

    expect(result.success).toBe(true);
    expect(result.replacements).toHaveLength(1);

    // Capture metadata omitted because params are incomplete.
    expect(result.replacements[0].capture).toBeUndefined();
    expect(result.replacements[0].renderMaterial).toBeUndefined();

    // Deterministic ref still has the correct kind.
    expect(result.replacements[0].deterministicRef.kind).toBe('deterministic-capture');

    // No capture enrichment in metadata when capture is absent.
    expect(result.replacements[0].deterministicRef.metadata?.deterministicCapture).toBeUndefined();
  });

  it('bakes deterministic-capture alongside render-material without mixing capture into media refs', () => {
    const vidChannelId = 'src-live:video' as LiveChannelDescriptor;
    const ctrlChannelId = 'src-live:control' as LiveChannelDescriptor;

    const result = bakeLiveSource({
      selection: {
        sourceId: source.id,
        targets: [
          {
            kind: 'render-material',
            ref: 'material-live-frame',
            params: { producerExtensionId: 'ext.test' },
          },
          {
            kind: 'deterministic-capture',
            ref: 'capture-seed-001',
            params: {
              captureId: 'capture-seed-001',
              profile: 'seed',
              contentHash: 'c'.repeat(64),
              provenanceHash: 'd'.repeat(64),
              routeConstraints: ['preview'],
              determinism: 'deterministic',
            },
          },
        ],
      },
      source,
      channels: [
        {
          metadata: { channelId: vidChannelId, sourceId: source.id, kind: 'video' },
          samples: [sample(vidChannelId, 0, 100, new Uint8Array([1, 2, 3]))],
        },
        {
          metadata: { channelId: ctrlChannelId, sourceId: source.id, kind: 'control' },
          samples: [sample(ctrlChannelId, 0, 50, { seed: 12345 })],
        },
      ],
    });

    expect(result.success).toBe(true);
    expect(result.replacements).toHaveLength(2);

    const materialReplacement = result.replacements.find((r) => r.target.kind === 'render-material');
    const captureReplacement = result.replacements.find((r) => r.target.kind === 'deterministic-capture');

    // Render-material gets its material ref.
    expect(materialReplacement).toBeDefined();
    expect(materialReplacement!.renderMaterial).toBeDefined();
    expect(materialReplacement!.renderMaterial!.mediaKind).toBe('video');
    expect(materialReplacement!.capture).toBeUndefined();

    // Deterministic-capture carries metadata but no material ref.
    expect(captureReplacement).toBeDefined();
    expect(captureReplacement!.capture).toBeDefined();
    expect(captureReplacement!.capture!.profile).toBe('seed');
    expect(captureReplacement!.renderMaterial).toBeUndefined();
  });

  it('converts accepted event-table bake results into graph-owned keyframe preview operations', async () => {
    const accepted = await acceptedEventTableSource();

    const operations = convertAcceptedEventTablesToGraphPreviewOperations({
      sources: [accepted],
      timingResolver: {
        resolveEventTime(event) {
          return { ok: true, mappedTime: event.time };
        },
      },
      valueNormalizer: {
        normalizeEvent(event) {
          return {
            ok: true,
            normalized: {
              clipId: 'clip-automation',
              paramName: 'params.opacity',
              targetPath: event.targetPath,
              value: event.value,
              interpolation: event.interpolation,
            },
          };
        },
      },
    });

    expect(operations).toEqual([
      expect.objectContaining({
        kind: 'keyframe.add',
        clipId: 'clip-automation',
        paramName: 'params.opacity',
        keyframe: keyframe(12, 0.8),
        metadata: {
          captureRef: accepted.captureRef.captureId,
          eventId: 'evt-1',
          provenanceHash: accepted.captureRef.provenanceHash,
          collisionPolicy: 'replace',
          targetPath: 'params.opacity',
        },
      }),
    ]);
  });

  it('attaches accepted event-table preview to zero-arg CompositionGraph.preview without mutating the base graph', async () => {
    const accepted = await acceptedEventTableSource();
    const input = graphInput(automationClip());
    const sourceClip = input.snapshot.clips[0] as HostClipSummary;
    const baseGraph = projectCompositionGraph(input);

    const graphWithPreview = withAcceptedEventTableGraphPreview({
      graph: baseGraph,
      graphInput: input,
      sources: [accepted],
      timingResolver: {
        resolveEventTime(event) {
          return { ok: true, mappedTime: event.time };
        },
      },
      valueNormalizer: {
        normalizeEvent(event) {
          return {
            ok: true,
            normalized: {
              clipId: 'clip-automation',
              paramName: 'params.opacity',
              targetPath: event.targetPath,
              value: event.value,
              interpolation: event.interpolation,
            },
          };
        },
      },
    });

    const preview = graphWithPreview.preview?.();

    expect(baseGraph.preview).toBeUndefined();
    expect(graphWithPreview.preview).toBeDefined();
    expect(baseGraph.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'animates',
        detail: expect.objectContaining({
          targetPath: 'opacity',
          keyframeCount: 1,
        }),
      }),
    ]));
    expect(preview?.edges).toEqual(expect.arrayContaining([
      expect.objectContaining({
        kind: 'animates',
        detail: expect.objectContaining({
          targetPath: 'opacity',
          keyframeCount: 2,
        }),
      }),
    ]));
    expect(sourceClip.keyframes?.opacity).toEqual([keyframe(0, 0.2)]);
    expect(sourceClip.automation?.[0]?.keyframeCount).toBe(1);
  });

  it('exposes per-keyframe conversion preview detail with event id, target path, mapped time, value, interpolation, collision policy, capture ref, provenance hash, operation kind, and blocking diagnostics', async () => {
    const accepted = await acceptedEventTableSource();

    const result = convertAcceptedEventTablesWithConversionDetail({
      sources: [accepted],
      timingResolver: {
        resolveEventTime(event) {
          return { ok: true, mappedTime: event.time };
        },
      },
      valueNormalizer: {
        normalizeEvent(event) {
          return {
            ok: true,
            normalized: {
              clipId: 'clip-automation',
              paramName: 'params.opacity',
              targetPath: event.targetPath,
              value: event.value,
              interpolation: event.interpolation,
            },
          };
        },
      },
    });

    expect(result.operations).toHaveLength(1);
    expect(result.details).toHaveLength(1);
    expect(result.details[0]).toMatchObject({
      eventId: 'evt-1',
      targetPath: 'params.opacity',
      mappedTime: 12,
      normalizedValue: 0.8,
      interpolation: 'linear',
      collisionPolicy: 'replace',
      captureRef: accepted.captureRef.captureId,
      provenanceHash: accepted.captureRef.provenanceHash,
      operationKind: 'keyframe.add',
    });
    expect(result.details[0].diagnostics).toEqual([]);
  });

  it('fails readiness when non-empty conversions collapse to summary-only output (all blocked)', async () => {
    const accepted = await acceptedEventTableSource();

    // Cause all events to be blocked via a rejecting timing resolver.
    const result = convertAcceptedEventTablesWithConversionDetail({
      sources: [accepted],
      timingResolver: {
        resolveEventTime(event) {
          return {
            ok: false,
            diagnostic: {
              severity: 'error',
              code: 'test/reject-all',
              message: `Rejecting event ${event.eventId}.`,
              detail: { eventId: event.eventId },
            },
          };
        },
      },
      valueNormalizer: {
        normalizeEvent(event) {
          return {
            ok: true,
            normalized: {
              clipId: 'clip-automation',
              paramName: 'params.opacity',
              targetPath: event.targetPath,
              value: event.value,
              interpolation: event.interpolation,
            },
          };
        },
      },
    });

    // Non-empty details but zero operations = summary-only collapse.
    expect(result.details.length).toBeGreaterThan(0);
    expect(result.operations).toHaveLength(0);
    expect(result.details.every((d) => d.operationKind === 'blocked')).toBe(true);

    const readiness = validateConversionPreviewReadiness(result);
    expect(readiness.ready).toBe(false);
    expect(readiness.diagnostics).toHaveLength(1);
    expect(readiness.diagnostics[0].code).toBe('live-event/conversion-summary-only-collapse');
    expect(readiness.diagnostics[0].severity).toBe('error');
    expect(readiness.diagnostics[0].detail).toMatchObject({
      totalDetailCount: result.details.length,
      blockedCount: result.details.length,
    });
  });

  it('passes readiness check when conversion produces actionable operations', async () => {
    const accepted = await acceptedEventTableSource();

    const result = convertAcceptedEventTablesWithConversionDetail({
      sources: [accepted],
      timingResolver: {
        resolveEventTime(event) {
          return { ok: true, mappedTime: event.time };
        },
      },
      valueNormalizer: {
        normalizeEvent(event) {
          return {
            ok: true,
            normalized: {
              clipId: 'clip-automation',
              paramName: 'params.opacity',
              targetPath: event.targetPath,
              value: event.value,
              interpolation: event.interpolation,
            },
          };
        },
      },
    });

    expect(result.operations.length).toBeGreaterThan(0);

    const readiness = validateConversionPreviewReadiness(result);
    expect(readiness.ready).toBe(true);
    expect(readiness.diagnostics).toHaveLength(0);
  });

  it('passes readiness check for empty conversions (no sources processed)', () => {
    const result = convertAcceptedEventTablesWithConversionDetail({
      sources: [],
      timingResolver: {
        resolveEventTime() {
          return { ok: true, mappedTime: 0 };
        },
      },
      valueNormalizer: {
        normalizeEvent(event) {
          return {
            ok: true,
            normalized: {
              clipId: 'clip-1',
              paramName: 'params.x',
              targetPath: event.targetPath,
              value: event.value,
              interpolation: event.interpolation,
            },
          };
        },
      },
    });

    expect(result.details).toHaveLength(0);

    const readiness = validateConversionPreviewReadiness(result);
    expect(readiness.ready).toBe(true);
    expect(readiness.diagnostics).toHaveLength(0);
  });

  it('fails without replacements for empty, targetless, invalid, or unmatched range bakes', () => {
    const channelId = 'src-live:control' as LiveChannelDescriptor;

    const empty = bakeLiveSource({
      selection: { sourceId: source.id, targets: [{ kind: 'keyframe', ref: 'clip-1:x' }] },
      source,
      channels: [{ metadata: { channelId, sourceId: source.id, kind: 'control' }, samples: [] }],
    });
    expect(empty.success).toBe(false);
    expect(empty.replacements).toHaveLength(0);
    expect(empty.diagnostics.some((diagnostic) => diagnostic.code === 'live/bake-empty-selection')).toBe(true);

    const targetless = bakeLiveSource({
      selection: { sourceId: source.id, targets: [] },
      source,
      channels: [{ metadata: { channelId, sourceId: source.id, kind: 'control' }, samples: [sample(channelId, 0, 0)] }],
    });
    expect(targetless.success).toBe(false);
    expect(targetless.diagnostics.some((diagnostic) => diagnostic.code === 'live/bake-no-targets')).toBe(true);

    const invalidRange = bakeLiveSource({
      selection: {
        sourceId: source.id,
        sampleRange: [2, 1],
        targets: [{ kind: 'keyframe', ref: 'clip-1:x' }],
      },
      source,
      channels: [{ metadata: { channelId, sourceId: source.id, kind: 'control' }, samples: [sample(channelId, 0, 0)] }],
    });
    expect(invalidRange.success).toBe(false);
    expect(invalidRange.diagnostics.some((diagnostic) => diagnostic.code === 'live/bake-invalid-range')).toBe(true);

    const unmatchedRange = bakeLiveSource({
      selection: {
        sourceId: source.id,
        sampleRange: [5, 6],
        targets: [{ kind: 'keyframe', ref: 'clip-1:x' }],
      },
      source,
      channels: [{ metadata: { channelId, sourceId: source.id, kind: 'control' }, samples: [sample(channelId, 0, 0)] }],
    });
    expect(unmatchedRange.success).toBe(false);
    expect(unmatchedRange.diagnostics.some((diagnostic) => diagnostic.code === 'live/bake-empty-selection')).toBe(true);
  });
});
