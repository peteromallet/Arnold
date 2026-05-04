import type { RefObject } from 'react';
import { forwardRef, memo, useEffect, useImperativeHandle, useMemo, useRef, useState } from 'react';
import { Pause, Play, SkipBack } from 'lucide-react';
import { Player, type PlayerRef } from '@remotion/player';
import { Button } from '@/shared/components/ui/button';
import { TimelineRenderer } from '@/tools/video-editor/compositions/TimelineRenderer';
import { useEffectDiagnostic, useRenderDiagnostic } from '@/tools/video-editor/hooks/usePerfDiagnostics';
import { getClipDurationInFrames, parseResolution, secondsToFrames } from '@/tools/video-editor/lib/config-utils';
import { VIDEO_EDITOR_THEME_VARS } from '@/tools/video-editor/lib/themeTokens';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';

export interface PreviewHandle {
  seek: (time: number) => void;
  play: () => void;
  pause: () => void;
  togglePlayPause: () => void;
  readonly isPlaying: boolean;
}

interface RemotionPreviewProps {
  config: ResolvedTimelineConfig;
  onTimeUpdate: (time: number) => void;
  playerContainerRef: RefObject<HTMLDivElement>;
  compact?: boolean;
  initialTime?: number;
}

const RemotionPreviewComponent = forwardRef<PreviewHandle, RemotionPreviewProps>(function RemotionPreview(
  { config, onTimeUpdate, playerContainerRef, compact = false, initialTime = 0 },
  ref,
) {
  const playerRef = useRef<PlayerRef>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  useRenderDiagnostic('RemotionPreview');
  const markEventsEffect = useEffectDiagnostic('remotionPreview:events');
  // Throttle config updates to the Player to avoid stutter during drag operations.
  // The timeline canvas shows immediate visual feedback; the Player catches up after 150ms idle.
  const [deferredConfig, setDeferredConfig] = useState(config);
  const deferTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingConfigRef = useRef<ResolvedTimelineConfig | null>(null);
  const flushDeferredConfig = (nextConfig: ResolvedTimelineConfig, delayMs: number) => {
    if (deferTimerRef.current) clearTimeout(deferTimerRef.current);
    if (delayMs <= 0) {
      setDeferredConfig(nextConfig);
      return;
    }
    deferTimerRef.current = setTimeout(() => setDeferredConfig(nextConfig), delayMs);
  };

  useEffect(() => {
    if (isPlaying) {
      pendingConfigRef.current = config;
      return;
    }

    const nextConfig = pendingConfigRef.current ?? config;
    const delayMs = pendingConfigRef.current ? 0 : 150;
    pendingConfigRef.current = null;
    flushDeferredConfig(nextConfig, delayMs);
    return () => {
      if (deferTimerRef.current) clearTimeout(deferTimerRef.current);
    };
  }, [config, isPlaying]);

  const inputProps = useMemo(() => ({ config: deferredConfig }), [deferredConfig]);
  const metadata = useMemo(() => {
    const fps = deferredConfig.output.fps;
    const { width, height } = parseResolution(deferredConfig.output.resolution);

    return {
      fps,
      durationInFrames: Math.max(
        1,
        ...deferredConfig.clips.map((clip) => secondsToFrames(clip.at, fps) + getClipDurationInFrames(clip, fps)),
      ),
      compositionWidth: Math.max(1, width),
      compositionHeight: Math.max(1, height),
    };
  }, [deferredConfig.clips, deferredConfig.output.fps, deferredConfig.output.resolution]);

  useEffect(() => {
    markEventsEffect();
    const player = playerRef.current;
    if (!player) {
      return;
    }

    const onFrameUpdate = (event: { detail: { frame: number } }) => {
      onTimeUpdate(event.detail.frame / metadata.fps);
    };
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);

    player.addEventListener('frameupdate', onFrameUpdate);
    player.addEventListener('play', onPlay);
    player.addEventListener('pause', onPause);

    return () => {
      player.removeEventListener('frameupdate', onFrameUpdate);
      player.removeEventListener('play', onPlay);
      player.removeEventListener('pause', onPause);
    };
  }, [markEventsEffect, metadata.fps, onTimeUpdate]);

  useImperativeHandle(ref, () => ({
    seek(time: number) {
      playerRef.current?.seekTo(Math.max(0, Math.round(time * metadata.fps)));
    },
    play() {
      playerRef.current?.play();
    },
    pause() {
      playerRef.current?.pause();
    },
    togglePlayPause() {
      playerRef.current?.toggle();
    },
    get isPlaying() {
      return playerRef.current?.isPlaying() ?? isPlaying;
    },
  }), [isPlaying, metadata.fps]);

  return (
    <div
      ref={playerContainerRef}
      className="relative flex h-full min-h-[220px] w-full items-center justify-center overflow-hidden rounded-xl bg-background"
      style={VIDEO_EDITOR_THEME_VARS}
    >
      <Player
        ref={playerRef}
        component={TimelineRenderer}
        inputProps={inputProps}
        durationInFrames={metadata.durationInFrames}
        fps={metadata.fps}
        compositionWidth={metadata.compositionWidth}
        compositionHeight={metadata.compositionHeight}
        initialFrame={Math.min(Math.max(0, Math.round(initialTime * metadata.fps)), Math.max(0, metadata.durationInFrames - 1))}
        controls={false}
        clickToPlay={false}
        doubleClickToFullscreen={false}
        spaceKeyToPlayOrPause={false}
        showVolumeControls={false}
        acknowledgeRemotionLicense
        bufferStateDelayInMilliseconds={1000}
        renderLoading={() => (
          <div
            style={{
              width: '100%',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'var(--video-editor-stage-bg)',
              color: 'var(--video-editor-stage-fg-subtle)',
              fontSize: 13,
              fontFamily: 'monospace',
            }}
          >
            Loading preview…
          </div>
        )}
        style={{ width: '100%', height: '100%' }}
      />
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 z-10 flex items-center justify-center gap-2 px-3 py-3"
        style={{ backgroundImage: 'linear-gradient(to top, var(--video-editor-stage-gradient-start), transparent)' }}
      >
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="pointer-events-auto h-8 w-8 rounded-full border-[color:var(--video-editor-stage-control-border)] bg-[var(--video-editor-stage-control-bg)] text-[color:var(--video-editor-stage-fg)] hover:bg-[var(--video-editor-stage-control-bg-hover)]"
          onClick={() => playerRef.current?.seekTo(0)}
          title="Jump to beginning"
        >
          <SkipBack className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="pointer-events-auto h-10 w-10 rounded-full border-[color:var(--video-editor-stage-control-border)] bg-[var(--video-editor-stage-control-bg)] text-[color:var(--video-editor-stage-fg)] hover:bg-[var(--video-editor-stage-control-bg-hover)]"
          onClick={() => playerRef.current?.toggle()}
          title={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 fill-current" />}
        </Button>
        {!compact && (
          <div className="pointer-events-none rounded-full bg-background/70 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            {config.output.resolution}
          </div>
        )}
      </div>
    </div>
  );
});

RemotionPreviewComponent.displayName = 'RemotionPreview';

export const RemotionPreview = memo(RemotionPreviewComponent);
