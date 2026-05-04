import { describe, expect, it } from 'vitest';
import { buildAssetDropEdit } from '@/tools/video-editor/hooks/useAssetManagement';
import {
  EXTERNAL_DROP_VISIBLE_VIDEO_FALLBACK_SECONDS,
  getDroppedGenerationDurationContract,
  getDuplicateGenerationDurationContract,
  getFinalVideoReplacementDurationContract,
} from '@/tools/video-editor/lib/timeline-asset-durations';
import {
  planDuplicateGenerationAssetRegistration,
  planFinalVideoGenerationAssetRegistration,
  planGenerationAssetRegistration,
} from '@/tools/video-editor/lib/timeline-asset-plans';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data';

const createTimelineData = (assetType: string, file: string): TimelineData => ({
  config: {
    output: { width: 1280, height: 720, fps: 30 },
    tracks: [{ id: 'V1', kind: 'visual' }],
    clips: [],
    registry: {
      assets: {
        asset1: { src: file, file, type: assetType, duration: 4 },
      },
    },
  },
  configVersion: 1,
  registry: {
    assets: {
      asset1: { src: file, file, type: assetType, duration: 4 },
    },
  },
  resolvedConfig: {
    output: { width: 1280, height: 720, fps: 30 },
    tracks: [{ id: 'V1', kind: 'visual' }],
    clips: [],
    registry: {
      asset1: { src: file, file, type: assetType, duration: 4 },
    },
  },
  rows: [{ id: 'V1', actions: [] }],
  meta: {},
  effects: {},
  assetMap: {},
  output: { width: 1280, height: 720, fps: 30 },
  tracks: [{ id: 'V1', kind: 'visual' }],
  clipOrder: { V1: [] },
  signature: 'sig',
  stableSignature: 'stable',
});

describe('buildAssetDropEdit media kind validation', () => {
  it('rejects text assets instead of adding them as visual video clips', () => {
    const edit = buildAssetDropEdit({
      current: createTimelineData('text/plain', 'https://example.com/script.txt'),
      assetKey: 'asset1',
      trackId: 'V1',
      time: 0,
    });

    expect(edit).toBeNull();
  });

  it('allows normal video assets on visual tracks', () => {
    const edit = buildAssetDropEdit({
      current: createTimelineData('video/mp4', 'https://example.com/clip.mp4'),
      assetKey: 'asset1',
      trackId: 'V1',
      time: 2,
    });

    expect(edit?.rows[0]?.actions[0]).toMatchObject({
      start: 2,
      end: 6,
    });
    expect(edit?.metaUpdates[edit.clipId]).toMatchObject({
      asset: 'asset1',
      track: 'V1',
      clipType: 'media',
      from: 0,
      to: 4,
    });
  });

  it('uses the 5 second visible-span fallback when video duration is unresolved and no clip span override is provided', () => {
    const current = createTimelineData('video/mp4', 'https://example.com/missing-duration.mp4');
    delete current.registry.assets.asset1.duration;

    const edit = buildAssetDropEdit({
      current,
      assetKey: 'asset1',
      trackId: 'V1',
      time: 1,
    });

    expect(edit?.rows[0]?.actions[0]).toMatchObject({
      start: 1,
      end: 6,
    });
    expect(edit?.metaUpdates[edit.clipId]).toMatchObject({
      asset: 'asset1',
      to: 5,
    });
  });

  it('keeps clip span separate from unresolved video asset duration for external-drop style inserts', () => {
    const registrationPlan = planGenerationAssetRegistration({
      assetId: 'asset-drop',
      generationId: 'gen-video',
      variantType: 'video',
      imageUrl: 'https://example.com/final.mp4',
      thumbUrl: 'https://example.com/final-thumb.jpg',
      assetDurationSeconds: null,
      metadata: { content_type: 'video/mp4' },
    });
    expect(registrationPlan.ok).toBe(true);
    if (!registrationPlan.ok) {
      throw new Error('registration plan should succeed');
    }

    expect(registrationPlan.assetEntry.duration).toBeUndefined();

    const edit = buildAssetDropEdit({
      current: makeDropTestDataLikeTimeline(),
      assetKey: registrationPlan.assetId,
      assetEntry: registrationPlan.assetEntry,
      trackId: 'V1',
      time: 12,
      clipSpanSeconds: 5,
    });

    expect(edit?.rows[0]?.actions[0]).toMatchObject({
      start: 12,
      end: 17,
    });
    expect(edit?.metaUpdates[edit.clipId]).toMatchObject({
      asset: 'asset-drop',
      to: 5,
    });
  });

  it('preserves explicit asset duration for duplicate-generation style registrations', () => {
    const registrationPlan = planDuplicateGenerationAssetRegistration({
      assetId: 'asset-dup',
      generationId: 'gen-video',
      variantId: 'variant-video',
      variantType: 'video',
      imageUrl: 'https://example.com/source.mp4',
      thumbUrl: 'https://example.com/source-thumb.jpg',
      sourceAssetEntry: {
        file: 'https://example.com/source.mp4',
        type: 'video/mp4',
        duration: 8.25,
      },
    });

    expect(registrationPlan).toMatchObject({
      ok: true,
      assetId: 'asset-dup',
      assetEntry: {
        duration: 8.25,
        generationId: 'gen-video',
        variantId: 'variant-video',
      },
    });
  });

  it('keeps duplicate-generation duration separate from visible clip-span planning', () => {
    expect(getDuplicateGenerationDurationContract({
      file: 'https://example.com/source.mp4',
      type: 'video/mp4',
      duration: 8.25,
    })).toEqual({
      assetDurationSeconds: 8.25,
      clipSpanSeconds: null,
    });
  });

  it('keeps unresolved external-drop video duration out of the registry while preserving the five-second visible fallback', () => {
    expect(getDroppedGenerationDurationContract({
      generationId: 'gen-video',
      imageUrl: 'https://example.com/final.mp4',
      variantType: 'video',
      metadata: { content_type: 'video/mp4' },
    })).toEqual({
      assetDurationSeconds: null,
      clipSpanSeconds: EXTERNAL_DROP_VISIBLE_VIDEO_FALLBACK_SECONDS,
    });
  });

  it('keeps final-video replacement duration unresolved instead of falling back to a visible five-second clip', () => {
    expect(getFinalVideoReplacementDurationContract(null)).toEqual({
      assetDurationSeconds: null,
      clipSpanSeconds: null,
    });

    const registrationPlan = planFinalVideoGenerationAssetRegistration({
      assetId: 'asset-final',
      generationId: 'final-video-1',
      imageUrl: 'https://example.com/final.mp4',
      thumbUrl: 'https://example.com/final-thumb.jpg',
      assetDurationSeconds: null,
    });

    expect(registrationPlan.ok).toBe(true);
    if (!registrationPlan.ok) {
      throw new Error('final video registration plan should succeed');
    }

    expect(registrationPlan.assetEntry.duration).toBeUndefined();
    expect(registrationPlan.assetEntry.type).toBe('video/mp4');
    expect(registrationPlan.assetEntry.generationId).toBe('final-video-1');
  });

  it('keeps external-drop registrations explicit about their unresolved five-second fallback', () => {
    const registrationPlan = planGenerationAssetRegistration({
      assetId: 'asset-drop-fallback',
      generationId: 'gen-video-fallback',
      variantType: 'video',
      imageUrl: 'https://example.com/final.mp4',
      thumbUrl: 'https://example.com/final-thumb.jpg',
      assetDurationSeconds: null,
      metadata: { content_type: 'video/mp4' },
    });

    expect(registrationPlan.ok).toBe(true);
    if (!registrationPlan.ok) {
      throw new Error('external-drop registration plan should succeed');
    }

    expect(registrationPlan.assetEntry.duration).toBeUndefined();
    expect(getDroppedGenerationDurationContract({
      generationId: 'gen-video-fallback',
      imageUrl: 'https://example.com/final.mp4',
      variantType: 'video',
      metadata: { content_type: 'video/mp4' },
    }).clipSpanSeconds).toBe(EXTERNAL_DROP_VISIBLE_VIDEO_FALLBACK_SECONDS);
  });
});

function makeDropTestDataLikeTimeline(): TimelineData {
  return createTimelineData('video/mp4', 'https://example.com/fallback.mp4');
}
