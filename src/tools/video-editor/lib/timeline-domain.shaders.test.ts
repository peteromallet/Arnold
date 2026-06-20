import { describe, expect, it } from 'vitest';
import {
  TIMELINE_POSTPROCESS_SHADER_APP_KEY,
  assignTimelineClipShader,
  assignTimelinePostprocessShader,
  getTimelineClipShader,
  getTimelinePostprocessShader,
  serializeTimelineConfigSnapshot,
  validateTimelineConfigSnapshot,
} from '@/tools/video-editor/lib/timeline-domain.ts';
import type {
  TimelineClip,
  TimelineClipShaderMetadata,
  TimelineConfig,
  TimelinePostprocessShaderMetadata,
} from '@/tools/video-editor/types/index.ts';

const clipShader: TimelineClipShaderMetadata = {
  scope: 'clip',
  extensionId: 'com.example.shader',
  contributionId: 'clip-glow-shader',
  shaderId: 'shader.clipGlow',
  uniforms: { intensity: 0.5 },
};

const otherClipShader: TimelineClipShaderMetadata = {
  scope: 'clip',
  extensionId: 'com.example.shader',
  contributionId: 'clip-edge-shader',
  shaderId: 'shader.clipEdge',
};

const postprocessShader: TimelinePostprocessShaderMetadata = {
  scope: 'postprocess',
  extensionId: 'com.example.shader',
  contributionId: 'post-grade-shader',
  shaderId: 'shader.postGrade',
  uniforms: { exposure: 0.1 },
};

const otherPostprocessShader: TimelinePostprocessShaderMetadata = {
  scope: 'postprocess',
  extensionId: 'com.example.shader',
  contributionId: 'post-vignette-shader',
  shaderId: 'shader.postVignette',
};

const makeClip = (overrides: Partial<TimelineClip> = {}): TimelineClip => ({
  id: 'clip-1',
  at: 0,
  track: 'V1',
  clipType: 'hold',
  hold: 2,
  ...overrides,
});

const makeConfig = (clip: TimelineClip = makeClip()): TimelineConfig => ({
  output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
  tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
  clips: [clip],
});

describe('timeline shader metadata domain helpers', () => {
  it('assigns and serializes one clip-local shader without disturbing existing clip app data', () => {
    const clip = makeClip({ app: { hostNote: 'keep-me' } });

    const assigned = assignTimelineClipShader(clip, clipShader);

    expect(assigned.ok).toBe(true);
    expect(getTimelineClipShader(assigned.ok ? assigned.value : clip)).toEqual(clipShader);
    expect((assigned.ok ? assigned.value : clip).app?.hostNote).toBe('keep-me');
    expect(serializeTimelineConfigSnapshot(makeConfig(assigned.ok ? assigned.value : clip)).config.clips[0].app?.shader)
      .toEqual(clipShader);
  });

  it('refuses a second clip-local shader in the same clip scope', () => {
    const clip = makeClip({ app: { shader: clipShader } });

    const assigned = assignTimelineClipShader(clip, otherClipShader);

    expect(assigned.ok).toBe(false);
    if (!assigned.ok) {
      expect(assigned.code).toBe('shader_scope_occupied');
      expect(assigned.scope).toBe('clip');
      expect(assigned.existing.shaderId).toBe('shader.clipGlow');
      expect(assigned.incoming.shaderId).toBe('shader.clipEdge');
      expect(assigned.message).toBe(
        'Cannot add shader "shader.clipEdge" to clip "clip-1" because shader "shader.clipGlow" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
      );
    }
    expect(getTimelineClipShader(clip)).toEqual(clipShader);
  });

  it('rejects stacked clip-local shader metadata during domain validation', () => {
    const config = makeConfig(makeClip({
      app: {
        shader: [clipShader, otherClipShader],
      } as never,
    }));

    const validation = validateTimelineConfigSnapshot(config);

    expect(validation.ok).toBe(false);
    expect(validation.issues).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: 'shader_scope_occupied',
        severity: 'error',
        clipId: 'clip-1',
        path: 'clips.clip-1.app.shader',
        message: 'Cannot add shader "shader.clipEdge" to clip "clip-1" because shader "shader.clipGlow" is already assigned. V1 supports one clip shader per clip. Remove the existing shader before assigning another.',
      }),
    ]));
  });

  it('assigns and serializes one postprocess shader in timeline app metadata', () => {
    const config = makeConfig();

    const assigned = assignTimelinePostprocessShader(config, postprocessShader);

    expect(assigned.ok).toBe(true);
    const value = assigned.ok ? assigned.value : config;
    expect(getTimelinePostprocessShader(value)).toEqual(postprocessShader);
    expect(serializeTimelineConfigSnapshot(value).config.app?.[TIMELINE_POSTPROCESS_SHADER_APP_KEY])
      .toEqual(postprocessShader);
  });

  it('refuses a second postprocess shader in the timeline scope', () => {
    const config = makeConfig();
    config.app = { [TIMELINE_POSTPROCESS_SHADER_APP_KEY]: postprocessShader };

    const assigned = assignTimelinePostprocessShader(config, otherPostprocessShader);

    expect(assigned.ok).toBe(false);
    if (!assigned.ok) {
      expect(assigned.code).toBe('shader_scope_occupied');
      expect(assigned.scope).toBe('postprocess');
      expect(assigned.existing.shaderId).toBe('shader.postGrade');
      expect(assigned.incoming.shaderId).toBe('shader.postVignette');
      expect(assigned.message).toBe(
        'Cannot add postprocess shader "shader.postVignette" because postprocess shader "shader.postGrade" is already assigned. V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.',
      );
    }
    expect(getTimelinePostprocessShader(config)).toEqual(postprocessShader);
  });

  it('rejects stacked postprocess shader metadata during domain validation', () => {
    const config = makeConfig();
    config.app = {
      [TIMELINE_POSTPROCESS_SHADER_APP_KEY]: [postprocessShader, otherPostprocessShader],
    } as never;

    const validation = validateTimelineConfigSnapshot(config);

    expect(validation.ok).toBe(false);
    expect(validation.issues).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: 'shader_scope_occupied',
        severity: 'error',
        path: 'app.shaderPostprocess',
        message: 'Cannot add postprocess shader "shader.postVignette" because postprocess shader "shader.postGrade" is already assigned. V1 supports one timeline postprocess shader. Remove the existing postprocess shader before assigning another.',
      }),
    ]));
  });
});
