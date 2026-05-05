import { useEffect, useMemo, useState, type FC } from 'react';
import { Player } from '@remotion/player';
import { compileSequenceComponentAsync } from '@/tools/video-editor/sequences/compileSequenceComponent.tsx';
import type { ResolvedTimelineClip } from '@/tools/video-editor/types/index.ts';

const PREVIEW_FPS = 30;
const PREVIEW_WIDTH = 1280;
const PREVIEW_HEIGHT = 720;
const PREVIEW_DURATION_SECONDS = 4;

const PREVIEW_CLIP: ResolvedTimelineClip = {
  id: 'code-path-preview',
  clipType: 'code-path-preview',
  track: 'code-path-preview-track',
  at: 0,
  from: 0,
  to: PREVIEW_DURATION_SECONDS,
  asset: undefined,
} as unknown as ResolvedTimelineClip;

export interface CodePathPreviewProps {
  code: string;
  defaultsJson: object;
  fps?: number;
}

export function CodePathPreview({ code, defaultsJson, fps = PREVIEW_FPS }: CodePathPreviewProps) {
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

  const inputProps = useMemo(() => ({
    clip: PREVIEW_CLIP,
    params: defaultsJson ?? {},
    theme: undefined,
    fps,
  }), [defaultsJson, fps]);

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
