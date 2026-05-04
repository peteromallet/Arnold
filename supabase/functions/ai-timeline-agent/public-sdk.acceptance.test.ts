import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  applySequenceDraftToTimeline,
  validateSequenceDraft,
} from '../../../src/tools/video-editor/sequence.ts';
import { createAgentWorkflowTimelineFixture } from '../../../src/tools/video-editor/testing.ts';
import { parseCommand, validateCommand } from './command-parser.ts';
import { executeCommand } from './tools/registry.ts';
import type { SupabaseAdmin, TimelineState } from './types.ts';

const { loadTimelineState, saveTimelineConfigVersioned } = vi.hoisted(() => ({
  loadTimelineState: vi.fn(),
  saveTimelineConfigVersioned: vi.fn(),
}));

vi.mock('./db.ts', () => ({
  loadTimelineState,
  saveTimelineConfigVersioned,
}));

vi.mock('@banodoco/timeline-ops', () => ({
  moveClip: (config: Record<string, any>, clipId: string, at: number) => {
    const nextConfig = structuredClone(config);
    const clipIndex = nextConfig.clips.findIndex((clip: { id: string }) => clip.id === clipId);
    if (clipIndex < 0) {
      return {
        changed: false,
        config,
        detail: { reason: 'not_found' },
      };
    }

    const previousAt = nextConfig.clips[clipIndex].at;
    nextConfig.clips[clipIndex] = {
      ...nextConfig.clips[clipIndex],
      at,
    };

    return {
      changed: true,
      config: nextConfig,
      detail: { previousAt },
    };
  },
  setClipParams: (config: Record<string, any>) => ({
    changed: false,
    config,
    detail: { reason: 'noop' },
  }),
  setClipProperty: (config: Record<string, any>) => ({
    changed: false,
    config,
    detail: { reason: 'noop' },
  }),
  setThemeOverrides: (config: Record<string, any>) => ({
    changed: false,
    config,
    detail: { reason: 'noop' },
  }),
  setTimelineTheme: (config: Record<string, any>) => ({
    changed: false,
    config,
    detail: { reason: 'noop' },
  }),
}));

function createSupabaseAdmin(): SupabaseAdmin {
  return {
    from: vi.fn(() => ({
      select: vi.fn(() => ({
        eq: vi.fn(),
        in: vi.fn(),
        or: vi.fn(),
        limit: vi.fn(),
        maybeSingle: vi.fn(),
      })),
      insert: vi.fn(),
      update: vi.fn(),
    })),
    rpc: vi.fn(() => ({
      maybeSingle: vi.fn(),
    })),
  } as unknown as SupabaseAdmin;
}

describe('ai-timeline-agent public SDK acceptance', () => {
  beforeEach(() => {
    loadTimelineState.mockReset();
    saveTimelineConfigVersioned.mockReset();
  });

  it('supports inspect, validate, dry-run, and apply against the shared public fixture without internal editor imports', async () => {
    const fixture = createAgentWorkflowTimelineFixture();
    const supabaseAdmin = createSupabaseAdmin();
    const state: TimelineState = {
      config: structuredClone(fixture.config),
      configVersion: fixture.configVersion,
      registry: structuredClone(fixture.registry),
      projectId: 'project-sdk-acceptance',
      shotNamesById: fixture.shotNamesById ?? {},
    };

    const inspectResult = await executeCommand('view', state, fixture.timelineId, supabaseAdmin);
    expect(inspectResult.result).toContain('Timeline summary:');
    expect(inspectResult.result).toContain('Shot groups:');
    expect(inspectResult.result).toContain('SDK Acceptance Shot');

    const validation = validateSequenceDraft({
      clipType: 'section-hook',
      hold: 3,
      params: {
        title: 'Agent acceptance draft',
      },
    });
    expect(validation.ok).toBe(true);
    if (!validation.ok) {
      return;
    }

    const dryRun = await applySequenceDraftToTimeline(
      state.config,
      state.registry,
      validation.draft,
      {
        at: 10.5,
        selectedTrackId: 'V1',
      },
    );
    expect(dryRun.ok).toBe(true);
    if (!dryRun.ok) {
      return;
    }

    const parsedMove = parseCommand(`move ${dryRun.clipId} 12.5`);
    expect(parsedMove.type).toBe('move');
    expect(validateCommand(parsedMove, dryRun.config, state.registry)).toBeNull();

    state.config = dryRun.config;
    saveTimelineConfigVersioned.mockResolvedValue(2);

    const applyResult = await executeCommand(
      `move ${dryRun.clipId} 12.5`,
      state,
      fixture.timelineId,
      supabaseAdmin,
    );

    expect(saveTimelineConfigVersioned).toHaveBeenCalledWith(
      supabaseAdmin,
      fixture.timelineId,
      1,
      expect.any(Object),
    );
    expect(loadTimelineState).not.toHaveBeenCalled();
    expect(applyResult.result).toContain(`Moved clip ${dryRun.clipId}`);
    expect(applyResult.config?.clips.find((clip) => clip.id === dryRun.clipId)).toMatchObject({
      id: dryRun.clipId,
      at: 12.5,
      track: 'V1',
      clipType: 'section-hook',
    });
    expect(state.configVersion).toBe(2);
  });
});
