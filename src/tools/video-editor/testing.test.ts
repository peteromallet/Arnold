import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import {
  getStableConfigSignature,
  getTimelineDurationInFrames,
  resolveTimelineConfig,
} from '@/tools/video-editor';
import {
  InMemoryDataProvider,
  createLocalAssetResolver,
} from '@/tools/video-editor/browser-provider';
import {
  AGENT_WORKFLOW_SHOT_ID,
  EMBED_DEMO_ASSET_KEYS,
  EMBED_DEMO_TIMELINE_ID,
  EMBED_DEMO_TIMELINE_NAME,
  createAgentWorkflowTimelineFixture,
  createEmbedDemoTimelineFixture,
} from '@/tools/video-editor/testing';
import {
  applySequenceDraftToTimeline,
  validateSequenceDraft,
} from '@/tools/video-editor/sequence';

vi.mock('@banodoco/timeline-composition/registry.generated', () => ({
  THEME_PACKAGE_REGISTRY: {},
}));

vi.mock('@banodoco/timeline-composition/theme-api', () => ({
  ThemeProvider: ({ children }: { children: ReactNode }) => children,
  useTheme: () => ({}),
}));

describe('public testing fixtures', () => {
  it('loads the shared embed demo fixture through the public testing, browser, and core SDK entrypoints', async () => {
    const fixture = createEmbedDemoTimelineFixture();
    const resolver = createLocalAssetResolver({ assetRoot: 'https://cdn.example/assets' });
    const provider = new InMemoryDataProvider({
      timelines: {
        [fixture.timelineId]: fixture,
      },
      resolveAssetUrl: resolver.resolveAssetUrl,
    });

    const loaded = await provider.loadTimeline(fixture.timelineId);
    const registry = await provider.loadAssetRegistry(fixture.timelineId);
    const resolved = await resolveTimelineConfig(
      loaded.config,
      registry,
      (file) => resolver.resolveAssetUrl(file),
    );

    expect(fixture.timelineId).toBe(EMBED_DEMO_TIMELINE_ID);
    expect(fixture.timelineName).toBe(EMBED_DEMO_TIMELINE_NAME);
    expect(Object.keys(registry.assets)).toEqual([...EMBED_DEMO_ASSET_KEYS]);
    expect(loaded.config.clips).toHaveLength(3);
    expect(resolved.clips).toHaveLength(3);
    expect(getTimelineDurationInFrames(resolved, resolved.output.fps)).toBeGreaterThan(0);
    expect(getStableConfigSignature(loaded.config, registry)).toBeTypeOf('string');
  });

  it('creates a trusted sequence clip against the shared agent fixture without internal editor imports', async () => {
    const fixture = createAgentWorkflowTimelineFixture();
    const allowedAssetKeys = Object.keys(fixture.registry.assets);
    const validation = validateSequenceDraft({
      clipType: 'resource-card',
      hold: 3,
      params: {
        title: 'Fixture-backed resource card',
        previewAssetKeys: allowedAssetKeys,
      },
    }, { allowedAssetKeys });

    expect(validation.ok).toBe(true);
    if (!validation.ok) {
      return;
    }

    const result = await applySequenceDraftToTimeline(
      fixture.config,
      fixture.registry,
      validation.draft,
      {
        at: 10.5,
        selectedTrackId: 'V1',
      },
    );

    expect(result.ok).toBe(true);
    if (!result.ok) {
      return;
    }

    expect(fixture.config.pinnedShotGroups?.[0]?.shotId).toBe(AGENT_WORKFLOW_SHOT_ID);
    expect(result.config.clips.some((clip) => clip.id === result.clipId)).toBe(true);
    expect(result.config.clips.find((clip) => clip.id === result.clipId)).toMatchObject({
      track: 'V1',
      at: 10.5,
      clipType: 'resource-card',
      params: {
        title: 'Fixture-backed resource card',
        previewAssetKeys: allowedAssetKeys,
      },
    });
  });
});
