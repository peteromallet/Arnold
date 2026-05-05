import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/types/index.ts';
import { createDefaultTimelineConfig } from '@/tools/video-editor/lib/defaults.ts';

export interface VideoEditorTestingTimelineFixture {
  timelineId: string;
  timelineName: string;
  configVersion: number;
  config: TimelineConfig;
  registry: AssetRegistry;
  shotNamesById?: Record<string, string>;
}

export const EMBED_DEMO_TIMELINE_ID = 'embed-demo';
export const EMBED_DEMO_TIMELINE_NAME = 'SDK Embed Demo';
export const EMBED_DEMO_ASSET_KEYS = ['demo-hero', 'demo-detail'] as const;

export const AGENT_WORKFLOW_TIMELINE_ID = 'agent-workflow';
export const AGENT_WORKFLOW_TIMELINE_NAME = 'SDK Agent Workflow';
export const AGENT_WORKFLOW_SHOT_ID = 'shot-sdk-acceptance';

const EMBED_DEMO_REGISTRY: AssetRegistry = {
  assets: {
    'demo-hero': {
      file: 'example-image1.jpg',
      src: '/example-image1.jpg',
      type: 'image/jpeg',
      duration: 4,
      generationId: 'gen-demo-hero',
    },
    'demo-detail': {
      file: 'example-image2.jpg',
      src: '/example-image2.jpg',
      type: 'image/jpeg',
      duration: 4,
      generationId: 'gen-demo-detail',
    },
  },
};

export function createEmbedDemoTimelineFixture(): VideoEditorTestingTimelineFixture {
  const base = createDefaultTimelineConfig();

  return {
    timelineId: EMBED_DEMO_TIMELINE_ID,
    timelineName: EMBED_DEMO_TIMELINE_NAME,
    configVersion: 1,
    registry: structuredClone(EMBED_DEMO_REGISTRY),
    config: {
      ...base,
      output: {
        ...base.output,
        file: 'embed-demo.mp4',
      },
      theme: '2rp',
      clips: [
        {
          id: 'clip-hero',
          track: 'V1',
          at: 0,
          clipType: 'media',
          hold: 4,
          asset: 'demo-hero',
        },
        {
          id: 'clip-title',
          track: 'V1',
          at: 4,
          clipType: 'text',
          hold: 2.5,
          text: {
            content: 'Public browser SDK demo',
          },
        },
        {
          id: 'clip-detail',
          track: 'V1',
          at: 6.5,
          clipType: 'media',
          hold: 4,
          asset: 'demo-detail',
        },
      ],
    },
  };
}

export function createAgentWorkflowTimelineFixture(): VideoEditorTestingTimelineFixture {
  const base = createEmbedDemoTimelineFixture();

  return {
    timelineId: AGENT_WORKFLOW_TIMELINE_ID,
    timelineName: AGENT_WORKFLOW_TIMELINE_NAME,
    configVersion: 1,
    registry: structuredClone(base.registry),
    shotNamesById: {
      [AGENT_WORKFLOW_SHOT_ID]: 'SDK Acceptance Shot',
    },
    config: {
      ...base.config,
      output: {
        ...base.config.output,
        file: 'agent-workflow.mp4',
      },
      pinnedShotGroups: [
        {
          shotId: AGENT_WORKFLOW_SHOT_ID,
          trackId: 'V1',
          clipIds: ['clip-hero', 'clip-detail'],
          mode: 'images',
        },
      ],
    },
  };
}
