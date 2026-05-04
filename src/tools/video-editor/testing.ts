/**
 * @publicContract
 * Test helpers for building fixture timelines against the supported SDK.
 */
export {
  DEFAULT_VIDEO_TRACKS,
  createDefaultTimelineConfig,
} from './lib/defaults.ts';
export {
  AGENT_WORKFLOW_SHOT_ID,
  AGENT_WORKFLOW_TIMELINE_ID,
  AGENT_WORKFLOW_TIMELINE_NAME,
  EMBED_DEMO_ASSET_KEYS,
  EMBED_DEMO_TIMELINE_ID,
  EMBED_DEMO_TIMELINE_NAME,
  createAgentWorkflowTimelineFixture,
  createEmbedDemoTimelineFixture,
} from './lib/fixtures.ts';

export type {
  VideoEditorTestingTimelineFixture,
} from './lib/fixtures.ts';
