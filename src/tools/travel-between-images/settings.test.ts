import { describe, it, expect } from 'vitest';
import { TOOL_IDS } from '@/shared/lib/tooling/toolIds';
import { DEFAULT_STEERABLE_MOTION_SETTINGS } from '@/shared/types/steerableMotion';
import {
  clampFrameCountToPolicy,
  coerceSelectedModel,
  getModelSpec,
  normalizeVideoTravelSettings,
  resolveSelectedModelFromModelName,
  videoTravelSettings,
} from './settings';

describe('videoTravelSettings', () => {
  it('targets the travel-between-images tool and shot scope', () => {
    expect(videoTravelSettings.id).toBe(TOOL_IDS.TRAVEL_BETWEEN_IMAGES);
    expect(videoTravelSettings.scope).toEqual(['shot']);
  });

  it('provides stable defaults for timeline generation flow', () => {
    expect(videoTravelSettings.defaults.generationMode).toBe('timeline');
    expect(videoTravelSettings.defaults.batchVideoFrames).toBe(61);
    expect(videoTravelSettings.defaults.batchVideoSteps).toBe(6);
    expect(videoTravelSettings.defaults.generationTypeMode).toBe('i2v');
    expect(videoTravelSettings.defaults.steerableMotionSettings).toEqual(DEFAULT_STEERABLE_MOTION_SETTINGS);
  });

  it('starts with clean content defaults for a new shot', () => {
    expect(videoTravelSettings.defaults.prompt).toBe('');
    expect(videoTravelSettings.defaults.negativePrompt).toBe('');
    expect(videoTravelSettings.defaults.pairConfigs).toEqual([]);
    expect(videoTravelSettings.defaults.shotImageIds).toEqual([]);
    expect(videoTravelSettings.defaults.loras).toEqual([]);
  });

  it('normalizes persisted settings into the canonical runtime shape', () => {
    const normalized = normalizeVideoTravelSettings({
      prompt: 'Travel prompt',
      batchVideoFrames: 49,
      steerableMotionSettings: { seed: 77 },
      pairConfigs: [
        { id: 'pair-1', prompt: 'pan', frames: 17, negativePrompt: 'blur', context: 4 },
        { prompt: 'missing-id' },
      ],
      shotImageIds: ['image-1', 2],
      loras: [
        { id: 'lora-1', name: 'Cinematic', path: '/tmp/cinematic', strength: 0.8 },
        { id: 'broken' },
      ],
      structure_video_path: 'https://example.com/guide.mp4',
      structure_video_motion_strength: 1.8,
      structure_video_type: 'flow',
    });

    expect(normalized.prompt).toBe('Travel prompt');
    expect(normalized.batchVideoFrames).toBe(49);
    expect(normalized.steerableMotionSettings.seed).toBe(77);
    expect(normalized.pairConfigs).toEqual([
      { id: 'pair-1', prompt: 'pan', frames: 17, negativePrompt: 'blur', context: 4 },
    ]);
    expect(normalized.shotImageIds).toEqual(['image-1']);
    expect(normalized.loras).toEqual([
      { id: 'lora-1', name: 'Cinematic', path: '/tmp/cinematic', strength: 0.8 },
    ]);
    expect(normalized.structureVideo).toEqual(expect.objectContaining({
      path: 'https://example.com/guide.mp4',
      motionStrength: 1.8,
      structureType: 'flow',
    }));
  });

  it('falls back to clean defaults for invalid persisted payloads', () => {
    const normalized = normalizeVideoTravelSettings('not-an-object');

    expect(normalized).toEqual(expect.objectContaining({
      prompt: '',
      generationMode: 'timeline',
      batchVideoFrames: 61,
      shotImageIds: [],
      loras: [],
    }));
  });

  it('coerces invalid runtime model values to wan-2.2', () => {
    expect(coerceSelectedModel('ltx-2.3')).toBe('ltx-2.3');
    expect(coerceSelectedModel('wan-2.1')).toBe('wan-2.2');
    expect(coerceSelectedModel({ model: 'ltx-2.3' })).toBe('wan-2.2');
  });

  it('maps worker model names back to the UI model selector ids', () => {
    expect(resolveSelectedModelFromModelName('wan_2_2_i2v_lightning_baseline_2_2_2')).toBe('wan-2.2');
    expect(resolveSelectedModelFromModelName('ltx2_22B')).toBe('ltx-2.3');
    expect(resolveSelectedModelFromModelName('ltx2_22B_distilled_1_1')).toBe('ltx-2.3-fast');
    expect(resolveSelectedModelFromModelName('ltx2_22B_distilled')).toBe('ltx-2.3-fast');
    expect(resolveSelectedModelFromModelName('unknown-model')).toBe('wan-2.2');
  });

  it('clamps frame counts to per-model continuation limits', () => {
    expect(clampFrameCountToPolicy(97, getModelSpec('ltx-2.3'), {
      smoothContinuations: true,
      requestedExecutionMode: 'i2v',
    })).toBe(97);

    // Values above the SC limit get clamped
    expect(clampFrameCountToPolicy(241, getModelSpec('ltx-2.3'), {
      smoothContinuations: true,
      requestedExecutionMode: 'i2v',
    })).toBe(217);

    expect(clampFrameCountToPolicy(81, getModelSpec('wan-2.2'), {
      smoothContinuations: true,
      requestedExecutionMode: 'vace',
    })).toBe(77);

    // WAN i2v (SVI) continuation clamps to 77
    expect(clampFrameCountToPolicy(81, getModelSpec('wan-2.2'), {
      smoothContinuations: true,
      requestedExecutionMode: 'i2v',
    })).toBe(77);

    expect(clampFrameCountToPolicy(97, getModelSpec('ltx-2.3'), {
      smoothContinuations: false,
      requestedExecutionMode: 'i2v',
    })).toBe(97);
  });
});
