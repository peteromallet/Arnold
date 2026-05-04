import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Shot } from '@/domains/generation/types';
import { getConfigSignature, getStableConfigSignature } from '@/tools/video-editor/lib/config-utils';
import { configToRows, type TimelineData } from '@/tools/video-editor/lib/timeline-data';
import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/types';
import { useVideoEditorLightboxNavigation } from './useVideoEditorLightboxNavigation';

function makeTimelineData(config: TimelineConfig, registry: AssetRegistry): TimelineData {
  const rowData = configToRows(config);
  const resolvedRegistry = Object.fromEntries(
    Object.entries(registry.assets).map(([assetKey, asset]) => [assetKey, {
      ...asset,
      src: asset.file.startsWith('http') ? asset.file : `https://example.com/${asset.file.replace(/^\/+/, '')}`,
    }]),
  );
  const resolvedConfig = {
    output: { ...config.output },
    tracks: (config.tracks ?? []).map((track) => ({ ...track })),
    clips: config.clips.map((clip) => ({
      ...clip,
      assetEntry: clip.asset ? resolvedRegistry[clip.asset] : undefined,
    })),
    registry: resolvedRegistry,
  };

  return {
    config,
    configVersion: 1,
    registry,
    resolvedConfig,
    rows: rowData.rows,
    meta: rowData.meta,
    effects: rowData.effects,
    assetMap: Object.fromEntries(Object.entries(registry.assets).map(([assetKey, asset]) => [assetKey, asset.file])),
    output: { ...config.output },
    tracks: (config.tracks ?? []).map((track) => ({ ...track })),
    clipOrder: rowData.clipOrder,
    signature: getConfigSignature(resolvedConfig),
    stableSignature: getStableConfigSignature(config, registry),
  };
}

describe('useVideoEditorLightboxNavigation', () => {
  const shots: Shot[] = [
    { id: 'shot-1', name: 'Intro' } as Shot,
    { id: 'shot-2', name: 'Outro' } as Shot,
  ];

  const registry: AssetRegistry = {
    assets: {
      'asset-1': { file: 'clip-1.mp4', type: 'video/mp4' },
      'asset-2': { file: 'clip-2.png', type: 'image/png' },
      'asset-3': { file: 'clip-3.mp4', type: 'video/mp4' },
      'asset-4': { file: 'clip-4.png', type: 'image/png' },
      'asset-audio': { file: 'clip-audio.mp4', type: 'video/mp4' },
    },
  };

  const data = makeTimelineData({
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [
      { id: 'V1', kind: 'visual', label: 'V1' },
      { id: 'V2', kind: 'visual', label: 'V2' },
      { id: 'A1', kind: 'audio', label: 'A1' },
    ],
    clips: [
      { id: 'clip-1', at: 0, track: 'V1', clipType: 'media', asset: 'asset-1', from: 0, to: 2 },
      { id: 'clip-2', at: 4, track: 'V1', clipType: 'media', asset: 'asset-2', from: 0, to: 2 },
      { id: 'clip-3', at: 8, track: 'V1', clipType: 'media', asset: 'asset-3', from: 0, to: 2 },
      { id: 'clip-text', at: 10, track: 'V1', clipType: 'text', hold: 2, text: { content: 'Inline text' } },
      { id: 'clip-effect', at: 12, track: 'V1', clipType: 'effect-layer', hold: 2, asset: 'asset-4' },
      { id: 'clip-4', at: 1, track: 'V2', clipType: 'media', asset: 'asset-2', from: 0, to: 2 },
      { id: 'clip-5', at: 3, track: 'V2', clipType: 'media', asset: 'asset-4', from: 0, to: 2 },
      { id: 'clip-6', at: 0, track: 'A1', clipType: 'media', asset: 'asset-audio', from: 0, to: 2 },
    ],
    pinnedShotGroups: [
      { shotId: 'shot-1', trackId: 'V1', clipIds: ['clip-1', 'clip-2'], mode: 'images' },
      { shotId: 'shot-2', trackId: 'V2', clipIds: ['clip-4'], mode: 'images' },
    ],
  }, registry);

  it('orders same-shot items first, then same-track, then other tracks, preserving the first asset occurrence', () => {
    const setLightboxAssetKey = vi.fn();
    const setLightboxClipId = vi.fn();

    const { result, rerender } = renderHook((props: { assetKey: string; clipId: string | null }) => useVideoEditorLightboxNavigation({
      lightboxAssetKey: props.assetKey,
      lightboxClipId: props.clipId,
      data,
      shots,
      setLightboxAssetKey,
      setLightboxClipId,
    }), {
      initialProps: {
        assetKey: 'asset-1',
        clipId: 'clip-1',
      },
    });

    expect(result.current.navigation).toEqual(expect.objectContaining({
      showNavigation: true,
      hasPrevious: false,
      hasNext: true,
    }));
    expect(result.current.indicator).toEqual({
      shotGroupLabel: 'Intro',
      shotGroupColor: expect.any(String),
      positionInGroup: { current: 1, total: 2 },
      positionInList: { current: 1, total: 4 },
    });

    act(() => result.current.navigation?.onNext?.());
    expect(setLightboxAssetKey).toHaveBeenNthCalledWith(1, 'asset-2');
    expect(setLightboxClipId).toHaveBeenNthCalledWith(1, 'clip-2');

    rerender({ assetKey: 'asset-2', clipId: 'clip-2' });
    act(() => result.current.navigation?.onNext?.());
    expect(setLightboxAssetKey).toHaveBeenNthCalledWith(2, 'asset-3');
    expect(setLightboxClipId).toHaveBeenNthCalledWith(2, 'clip-3');

    rerender({ assetKey: 'asset-3', clipId: 'clip-3' });
    act(() => result.current.navigation?.onNext?.());
    expect(setLightboxAssetKey).toHaveBeenNthCalledWith(3, 'asset-4');
    expect(setLightboxClipId).toHaveBeenNthCalledWith(3, 'clip-5');
  });

  it('uses the clicked clip id to resolve duplicate assets before deduplication', () => {
    const setLightboxAssetKey = vi.fn();
    const setLightboxClipId = vi.fn();

    const { result, rerender } = renderHook((props: { assetKey: string; clipId: string | null }) => useVideoEditorLightboxNavigation({
      lightboxAssetKey: props.assetKey,
      lightboxClipId: props.clipId,
      data,
      shots,
      setLightboxAssetKey,
      setLightboxClipId,
    }), {
      initialProps: {
        assetKey: 'asset-2',
        clipId: 'clip-4',
      },
    });

    expect(result.current.indicator?.positionInList).toEqual({ current: 1, total: 4 });
    expect(result.current.indicator?.shotGroupLabel).toBe('Outro');

    act(() => result.current.navigation?.onNext?.());
    expect(setLightboxAssetKey).toHaveBeenCalledWith('asset-4');
    expect(setLightboxClipId).toHaveBeenCalledWith('clip-5');

    rerender({ assetKey: 'asset-2', clipId: null });
    expect(result.current.indicator?.shotGroupLabel).toBe('Intro');
    expect(result.current.indicator?.positionInList).toEqual({ current: 2, total: 4 });
  });
});
