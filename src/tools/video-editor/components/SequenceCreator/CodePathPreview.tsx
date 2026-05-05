import { useEffect, useMemo, useState, type FC } from 'react';
import { Player } from '@remotion/player';
import { compileSequenceComponentAsync } from '@/tools/video-editor/sequences/compileSequenceComponent.tsx';
import type { ResolvedTimelineClip } from '@/tools/video-editor/types/index.ts';

const PREVIEW_FPS = 30;
const PREVIEW_WIDTH = 1280;
const PREVIEW_HEIGHT = 720;
const PREVIEW_DURATION_SECONDS = 4;

export interface CodePathPreviewAsset {
  key: string;
  url: string;
}

export interface CodePathPreviewProps {
  code: string;
  defaultsJson: object;
  fps?: number;
  /**
   * User-supplied assets attached/selected in the panel. Their URLs are
   * injected into the preview clip + params so the generated component
   * has actual image data to render against (matching the trusted-clip
   * pattern: params.images = [...urls], imageAssetKeys = [...keys],
   * clip.asset.src = first url).
   */
  allowedAssets?: readonly CodePathPreviewAsset[];
}

export function CodePathPreview({ code, defaultsJson, fps = PREVIEW_FPS, allowedAssets }: CodePathPreviewProps) {
  const [Component, setComponent] = useState<FC<unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setComponent(null);
    setError(null);
    compileSequenceComponentAsync(code)
      .then((compiled) => {
        if (cancelled) return;
        setComponent(() => compiled as unknown as FC<unknown>);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  const durationInFrames = Math.max(1, Math.round(PREVIEW_DURATION_SECONDS * fps));

  const inputProps = useMemo(() => {
    const urls = (allowedAssets ?? []).map((a) => a.url).filter(Boolean);
    const keys = (allowedAssets ?? []).map((a) => a.key).filter(Boolean);
    const baseParams = (defaultsJson ?? {}) as Record<string, unknown>;
    // Inject asset URLs/keys ONLY where the model didn't already provide a
    // non-empty default (don't clobber prompt-derived intent).
    const hasArray = (v: unknown) => Array.isArray(v) && v.length > 0;
    const params = {
      ...baseParams,
      ...(hasArray(baseParams.images) ? {} : { images: urls }),
      ...(hasArray(baseParams.imageAssetKeys) ? {} : { imageAssetKeys: keys }),
      ...(hasArray(baseParams.assetKeys) ? {} : { assetKeys: keys }),
      ...(hasArray(baseParams.assetUrls) ? {} : { assetUrls: urls }),
    };
    const previewClip: ResolvedTimelineClip = {
      id: 'code-path-preview',
      clipType: 'code-path-preview',
      track: 'code-path-preview-track',
      at: 0,
      from: 0,
      to: PREVIEW_DURATION_SECONDS,
      asset: urls[0] ? { src: urls[0], mediaType: 'image' } : undefined,
    } as unknown as ResolvedTimelineClip;
    return {
      clip: previewClip,
      params,
      theme: undefined,
      fps,
    };
  }, [allowedAssets, defaultsJson, fps]);

  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-destructive">
        Compile error: {error}
      </div>
    );
  }
  if (!Component) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground">
        Compiling preview…
      </div>
    );
  }

  return (
    <Player
      component={Component as unknown as FC<Record<string, unknown>>}
      inputProps={inputProps as unknown as Record<string, unknown>}
      durationInFrames={durationInFrames}
      compositionWidth={PREVIEW_WIDTH}
      compositionHeight={PREVIEW_HEIGHT}
      fps={fps}
      controls
      autoPlay
      loop
      style={{ width: '100%', height: '100%' }}
    />
  );
}
