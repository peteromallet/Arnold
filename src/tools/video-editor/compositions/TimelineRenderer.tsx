import { AbsoluteFill, Sequence } from 'remotion';
import { Component, memo, useMemo, type FC, type ReactNode } from 'react';
import { getAudioTracks, getVisualTracks } from '@/tools/video-editor/lib/editor-utils.ts';
import { getClipDurationInFrames, getTimelineDurationInFrames, secondsToFrames } from '@/tools/video-editor/lib/config-utils.ts';
import { BUILTIN_CLIP_TYPES, type ParameterSchema, type ResolvedTimelineClip, type ResolvedTimelineConfig, type TrackDefinition } from '@/tools/video-editor/types/index.ts';
import { AudioTrack } from '@/tools/video-editor/compositions/AudioTrack.tsx';
import { AudioAnalysisProvider } from '@/tools/video-editor/compositions/AudioAnalysisProvider.tsx';
import { EffectLayerSequence } from '@/tools/video-editor/compositions/EffectLayerSequence.tsx';
import { TextClipSequence } from '@/tools/video-editor/compositions/TextClip.tsx';
import { VisualClipSequence } from '@/tools/video-editor/compositions/VisualClip.tsx';
import { UnknownClipPlaceholderSequence } from '@/tools/video-editor/compositions/UnknownClipPlaceholder.tsx';
import { resolveTimelineRenderTheme } from '@/tools/video-editor/compositions/installed-themes.ts';
import {
  getGeneratedRemotionModuleStatus,
  isGeneratedRemotionModuleClip,
} from '@/tools/video-editor/lib/generated-lanes.ts';
import { materializeResolvedSequenceConfig } from '@/tools/video-editor/sequences/materialize.ts';
import {
  ThemeProvider,
  useTheme,
  type RuntimeTheme,
  type Theme,
} from '@banodoco/timeline-composition/theme-api';
import {
  describeClipCapabilityWith,
  resolveSequenceClipEntry,
  SEQUENCE_COMPONENT_REGISTRY,
  type DynamicSequenceComponentEntry,
} from '@/tools/video-editor/sequences/registry.ts';
import { useSequenceComponentRegistrySnapshot } from '@/tools/video-editor/sequences/SequenceComponentRegistryContext.tsx';
import { useClipTypeRegistrySnapshot } from '@/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx';
import type { ClipRendererProps, ClipTypeRegistryRecord } from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import { applyAutomationOverrides, resolveAnimatedParams } from '@/tools/video-editor/keyframes/index.ts';

// Phase 4d (Sprint 5): EFFECT_REGISTRY dispatch.
//
// Mirrors `tools/remotion/src/HypeComposition.tsx:58-64` (lifted into
// `packages/timeline-composition/typescript/src/TimelineComposition.tsx`).
// Lookup chain for a clipType:
//
//   1. Reigh-native built-ins (effect-layer, text, media, hold) — same as
//      pre-Sprint-5 behavior.
//   2. THEME_PACKAGE_REGISTRY (codegenned from installed
//      @banodoco/timeline-theme-* packages) — render the theme component.
//   3. Sprint-3 loud placeholder — defensive fallback when the theme
//      package isn't installed OR the clipType is unknown.
const isBuiltinClipType = (value: string | undefined): boolean => {
  if (typeof value !== 'string') {
    return true; // legacy clips with no clipType default to media-equivalent dispatch
  }
  return (BUILTIN_CLIP_TYPES as readonly string[]).includes(value);
};

// Dynamic-aware sequence-component dispatch check. Built-in entries match
// SEQUENCE_COMPONENT_REGISTRY directly; DB-stored entries (clipType
// `custom:<name>`) match via the dynamic resolver. We accept any clipType
// that has a registry entry on either side and a browser-preview-capable
// capability descriptor.
const isSequenceComponentClipType = (
  value: string | undefined,
  dynamicEntries: readonly DynamicSequenceComponentEntry[],
): boolean => {
  if (typeof value !== 'string') return false;
  if (resolveSequenceClipEntry(value, dynamicEntries)) return true;
  return Object.prototype.hasOwnProperty.call(SEQUENCE_COMPONENT_REGISTRY, value);
};

const sortClipsByAt = (clips: ResolvedTimelineClip[]): ResolvedTimelineClip[] => {
  return [...clips].sort((left, right) => left.at - right.at);
};

type ThemeEffectSequenceProps = {
  clip: ResolvedTimelineClip;
  fps: number;
  theme: Theme;
  dynamicEntries: readonly DynamicSequenceComponentEntry[];
};

const ThemePackageComponent: FC<{
  component: FC<{
    clip: ResolvedTimelineClip;
    params: unknown;
    theme: RuntimeTheme;
    fps: number;
  }>;
  clip: ResolvedTimelineClip;
  fps: number;
}> = ({ component: Component, clip, fps }) => {
  const theme = useTheme();
  return <Component clip={clip} params={clip.params} theme={theme} fps={fps} />;
};

const ThemeEffectSequence: FC<ThemeEffectSequenceProps> = ({ clip, fps, theme, dynamicEntries }) => {
  // Dynamic-aware lookup: prefer DB-stored components for `custom:` clipTypes;
  // fall back to the static SEQUENCE_COMPONENT_REGISTRY for built-ins.
  const dynamicEntry = resolveSequenceClipEntry(clip.clipType, dynamicEntries);
  const staticEntry = SEQUENCE_COMPONENT_REGISTRY[clip.clipType as keyof typeof SEQUENCE_COMPONENT_REGISTRY];
  const Component = (dynamicEntry?.component ?? staticEntry?.component) as
    | FC<{ clip: ResolvedTimelineClip; params: unknown; theme: RuntimeTheme; fps: number }>
    | undefined;
  // Defensive: if neither registry has the component, fall back to the loud
  // placeholder. This is the second layer of the SD-025 "loud placeholder"
  // safety net for clipTypes that *are* in the registry but somehow fail to
  // render.
  if (!Component) {
    return <UnknownClipPlaceholderSequence clip={clip} fps={fps} reason="unsupported" />;
  }
  const durationInFrames = getClipDurationInFrames(clip, fps);
  return (
    <Sequence
      key={clip.id}
      from={Math.round(clip.at * fps)}
      durationInFrames={durationInFrames}
    >
      <ThemeProvider value={theme}>
        <ThemePackageComponent component={Component} clip={clip} fps={fps} />
      </ThemeProvider>
    </Sequence>
  );
};

const GeneratedModulePlaceholderSequence: FC<{
  clip: ResolvedTimelineClip;
  fps: number;
}> = ({ clip, fps }) => {
  const moduleStatus = getGeneratedRemotionModuleStatus(clip);
  const durationInFrames = getClipDurationInFrames(clip, fps);
  const artifactId = moduleStatus.kind === 'valid_module' ? moduleStatus.artifactId : null;
  const reason = moduleStatus.kind === 'blocked_module' ? moduleStatus.reason : 'worker_only';
  return (
    <Sequence
      key={clip.id}
      from={Math.max(0, Math.round(clip.at * fps))}
      durationInFrames={durationInFrames}
    >
      <AbsoluteFill
        data-testid="generated-module-placeholder"
        data-clip-id={clip.id}
        data-artifact-id={artifactId ?? undefined}
        data-placeholder-reason={reason}
        style={{
          backgroundColor: '#111827',
          borderTop: '2px solid #38bdf8',
          borderBottom: '2px solid #38bdf8',
          color: '#e0f2fe',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '12px 24px',
          textAlign: 'center',
          fontFamily: 'ui-monospace, SFMono-Regular, "Roboto Mono", Menlo, Consolas, monospace',
          fontSize: 14,
          lineHeight: 1.4,
          letterSpacing: '0.04em',
        }}
      >
        <div
          style={{
            maxWidth: '80%',
            padding: '8px 16px',
            borderRadius: 4,
            background: 'rgba(0, 0, 0, 0.45)',
          }}
        >
          Generated Remotion module previews only in worker render infrastructure.
        </div>
      </AbsoluteFill>
    </Sequence>
  );
};

// ---------------------------------------------------------------------------
// M9 T10: Extension clip renderer dispatch
// ---------------------------------------------------------------------------

/** Parse width and height from a resolution string like "1920x1080". */
function parseResolution(resolution: string): { width: number; height: number } {
  const parts = resolution.split('x');
  const w = parseInt(parts[0] ?? '1920', 10);
  const h = parseInt(parts[1] ?? '1080', 10);
  return { width: Number.isFinite(w) ? w : 1920, height: Number.isFinite(h) ? h : 1080 };
}

/**
 * Convert InterpolatedParam array to a plain Record for ClipRendererProps.
 */
function interpolatedParamsToRecord(
  params: ReadonlyArray<{ name: string; value: number | string | boolean }>,
): Record<string, unknown> {
  const record: Record<string, unknown> = {};
  for (const p of params) {
    record[p.name] = p.value;
  }
  return record;
}

/**
 * Error boundary that catches renderer crashes and shows a loud placeholder.
 * Extension renderers are trusted local code but may throw at runtime
 * (e.g. division by zero, invalid state). The boundary preserves the
 * SD-025 guarantee that broken clips never silently vanish.
 */
class ExtensionRendererErrorBoundary extends Component<
  { fallback: ReactNode; children: ReactNode },
  { hasError: boolean }
> {
  constructor(props: { fallback: ReactNode; children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(): { hasError: boolean } {
    return { hasError: true };
  }
  override render(): ReactNode {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}

/** Props for the ExtensionClipSequence host-side wrapper. */
interface ExtensionClipSequenceProps {
  clip: ResolvedTimelineClip;
  fps: number;
  registryRecord: ClipTypeRegistryRecord;
  resolution: string;
  /** All timeline clips (needed for automation override resolution). */
  allClips: readonly ResolvedTimelineClip[];
}

/**
 * Wraps an extension-provided clip renderer in a Remotion <Sequence> with
 * host-interpolated keyframe params and automation overrides applied.
 *
 * The host computes interpolated parameter values via resolveAnimatedParams()
 * before passing them to the extension renderer, satisfying SD2 ("extension
 * renderers must not implement timeline interpolation").
 *
 * Automation overrides are then applied via applyAutomationOverrides(),
 * which scans automation clips for matching target contribution IDs and
 * overrides the extension clip's parameters at the current time (SD3 /
 * success criterion 9).
 *
 * If the renderer throws at runtime, the error boundary catches it and
 * displays a loud placeholder preserving the clip's duration and position.
 */
const ExtensionClipSequence: FC<ExtensionClipSequenceProps> = ({
  clip,
  fps,
  registryRecord,
  resolution,
  allClips,
}) => {
  const durationInFrames = getClipDurationInFrames(clip, fps);
  const from = Math.max(0, secondsToFrames(clip.at, fps));
  const { width, height } = parseResolution(resolution);

  // Compute host-interpolated params from keyframe data, then apply
  // automation overrides from automation clips targeting this extension clip.
  const interpolatedParams = useMemo(() => {
    const schema: ParameterSchema | undefined = registryRecord.schema as ParameterSchema | undefined;
    const keyframes = clip.keyframes ?? {};
    let baseParams: Record<string, unknown>;
    if (!schema || schema.length === 0) {
      // No schema → pass raw params (no interpolation needed)
      baseParams = (clip.params as Record<string, unknown>) ?? {};
    } else {
      const resolved = resolveAnimatedParams(keyframes, schema, clip.at);
      baseParams = interpolatedParamsToRecord(resolved);
    }

    // Apply automation overrides
    if (clip.clipType) {
      return applyAutomationOverrides(
        allClips,
        clip.clipType,
        baseParams,
        clip.at,
      );
    }
    return baseParams;
  }, [clip.at, clip.keyframes, clip.params, clip.clipType, registryRecord.schema, allClips]);

  const rendererProps: ClipRendererProps = {
    clipId: clip.id,
    clipTypeId: registryRecord.clipTypeId,
    time: clip.at,
    params: interpolatedParams,
    width,
    height,
  };

  // Extension renderers are stored as `Record<string, unknown> | Function`.
  // We cast to FC<ClipRendererProps> since the registry contract guarantees
  // a React component.
  const Renderer = registryRecord.renderer as FC<ClipRendererProps>;

  const placeholder = (
    <UnknownClipPlaceholderSequence
      clip={clip}
      fps={fps}
      reason="unsupported"
    />
  );

  return (
    <Sequence key={clip.id} from={from} durationInFrames={durationInFrames}>
      <ExtensionRendererErrorBoundary fallback={placeholder}>
        <Renderer {...rendererProps} />
      </ExtensionRendererErrorBoundary>
    </Sequence>
  );
};

interface VisualTrackProps {
  track: TrackDefinition;
  clips: ResolvedTimelineClip[];
  fps: number;
  theme: Theme;
  resolution: string;
  /** All timeline clips (needed for automation override resolution). */
  allClips: readonly ResolvedTimelineClip[];
}

// Lifted into a component so we can call useSequenceComponentRegistrySnapshot
// once per visual track. Keeps the dynamic-registry subscription out of the
// per-clip dispatch loop.
const VisualTrack: FC<VisualTrackProps> = ({ track, clips, fps, theme, resolution, allClips }) => {
  const { entries: dynamicEntries } = useSequenceComponentRegistrySnapshot();
  const clipTypeRegistry = useClipTypeRegistrySnapshot();
  const sortedClips = sortClipsByAt(clips);
  if (sortedClips.length === 0) {
    return null;
  }

  return (
    <AbsoluteFill
      key={track.id}
      style={{
        opacity: track.opacity ?? 1,
        mixBlendMode: track.blendMode && track.blendMode !== 'normal' ? track.blendMode : undefined,
      }}
    >
      {sortedClips.map((clip, index) => {
        // Dynamic-aware capability lookup (FLAG-001/002). DB-stored sequence
        // components surface workerRender:false through this path.
        const descriptor = describeClipCapabilityWith(clip, dynamicEntries);

        if (descriptor?.source === 'generated-module' || isGeneratedRemotionModuleClip(clip)) {
          return <GeneratedModulePlaceholderSequence key={clip.id} clip={clip} fps={fps} />;
        }

        if (clip.clipType === 'effect-layer') {
          return null;
        }

        if (clip.clipType === 'text') {
          return <TextClipSequence key={clip.id} clip={clip} track={track} fps={fps} />;
        }

        // EFFECT_REGISTRY dispatch (Sprint 5 / SD-026): if the clipType
        // is provided by an installed theme package OR a DB-stored
        // sequence component, render via the dynamic-aware registry entry.
        // Mirrors HypeComposition.tsx:58-64 with DB augmentation.
        if (isSequenceComponentClipType(clip.clipType, dynamicEntries)) {
          return (
            <ThemeEffectSequence
              key={clip.id}
              clip={clip}
              fps={fps}
              theme={theme}
              dynamicEntries={dynamicEntries}
            />
          );
        }

        // M9 T10: Extension clip renderer dispatch.
        // After built-ins and sequence components, before the loud
        // placeholder fallback. Looks up the clipTypeId in the
        // provider-scoped ClipTypeRegistry.
        // - Active record with a renderer → ExtensionClipSequence
        //   with host-interpolated params (SD2).
        // - Active record without a usable renderer → loud placeholder
        //   (missing renderer).
        // - Inactive / error record → loud placeholder.
        // - Not in registry → falls through to existing placeholder logic.
        // The error boundary inside ExtensionClipSequence catches
        // runtime renderer crashes and displays a placeholder too.
        if (clip.clipType) {
          const extensionRecord = clipTypeRegistry.get(clip.clipType);
          if (extensionRecord) {
            if (
              extensionRecord.status === 'active' &&
              typeof extensionRecord.renderer === 'function'
            ) {
              // Check renderability: if preview route is explicitly blocked,
              // show the placeholder instead of attempting render.
              const previewCap = extensionRecord.renderability.capabilities.find(
                (c) => c.route === 'preview',
              );
              if (previewCap && previewCap.status === 'blocked') {
                return (
                  <UnknownClipPlaceholderSequence
                    key={clip.id}
                    clip={clip}
                    fps={fps}
                    reason="unsupported"
                  />
                );
              }
              return (
                <ExtensionClipSequence
                  key={clip.id}
                  clip={clip}
                  fps={fps}
                  registryRecord={extensionRecord}
                  resolution={resolution}
                  allClips={allClips}
                />
              );
            }
            // Found in registry but not renderable: loud placeholder
            return (
              <UnknownClipPlaceholderSequence
                key={clip.id}
                clip={clip}
                fps={fps}
                reason="unsupported"
              />
            );
          }
        }

        if (descriptor?.capabilities.preview === 'placeholder') {
          return (
            <UnknownClipPlaceholderSequence
              key={clip.id}
              clip={clip}
              fps={fps}
              reason="unsupported"
            />
          );
        }

        // SD-025 (Sprint 3): loud placeholder for unknown clipTypes that
        // are NOT in BUILTIN_CLIP_TYPES and NOT in the theme registry —
        // theme package missing, typo, or future clipType not yet
        // supported. Surfaces as a labeled band rather than a silent
        // black void.
        if (!isBuiltinClipType(clip.clipType)) {
          return (
            <UnknownClipPlaceholderSequence
              key={clip.id}
              clip={clip}
              fps={fps}
              reason="unsupported"
            />
          );
        }

        const predecessor = index > 0 ? sortedClips[index - 1] : null;
        const hasPositionOverride = (
          clip.x !== undefined
          || clip.y !== undefined
          || clip.width !== undefined
          || clip.height !== undefined
          || clip.cropTop !== undefined
          || clip.cropBottom !== undefined
          || clip.cropLeft !== undefined
          || clip.cropRight !== undefined
        );
        if (hasPositionOverride) {
          return (
            <VisualClipSequence
              key={clip.id}
              clip={clip}
              track={track}
              fps={fps}
              predecessor={predecessor}
            />
          );
        }

        const effectiveScale = track.scale ?? 1;
        const needsScaleWrapper = effectiveScale !== 1;
        if (needsScaleWrapper) {
          return (
            <AbsoluteFill
              key={clip.id}
              style={{
                transform: `scale(${effectiveScale})`,
                transformOrigin: 'center center',
                overflow: 'hidden',
                isolation: 'isolate',
              }}
            >
              <VisualClipSequence
                clip={clip}
                track={track}
                fps={fps}
                predecessor={predecessor}
              />
            </AbsoluteFill>
          );
        }
        return (
          <VisualClipSequence
            key={clip.id}
            clip={clip}
            track={track}
            fps={fps}
            predecessor={predecessor}
          />
        );
      })}
    </AbsoluteFill>
  );
};

export const TimelineRenderer: FC<{ config: ResolvedTimelineConfig }> = memo(({ config }) => {
  const renderConfig = useMemo(() => materializeResolvedSequenceConfig(config), [config]);
  const fps = renderConfig.output.fps;
  const theme = useMemo(() => resolveTimelineRenderTheme(renderConfig), [renderConfig]);
  const visualTracks = useMemo(() => [...getVisualTracks(renderConfig)].reverse(), [renderConfig]);
  const audioTracks = useMemo(() => getAudioTracks(renderConfig), [renderConfig]);
  const totalDurationInFrames = useMemo(() => getTimelineDurationInFrames(renderConfig, fps), [renderConfig, fps]);
  const audioClips = useMemo(() => {
    const audioTrackIds = new Set(audioTracks.map((track) => track.id));
    return renderConfig.clips.filter((clip) => audioTrackIds.has(clip.track));
  }, [audioTracks, renderConfig.clips]);
  const clipsByTrack = useMemo(() => {
    return renderConfig.clips.reduce<{
      regular: Record<string, ResolvedTimelineClip[]>;
      effectLayers: Record<string, ResolvedTimelineClip[]>;
      all: Record<string, ResolvedTimelineClip[]>;
    }>((groups, clip) => {
      groups.all[clip.track] ??= [];
      groups.all[clip.track].push(clip);
      if (clip.clipType === 'automation') {
        // Automation clips are data-only and do not produce visual output.
        // They are only processed for override resolution.
      } else if (clip.clipType === 'effect-layer' && !isGeneratedRemotionModuleClip(clip)) {
        groups.effectLayers[clip.track] ??= [];
        groups.effectLayers[clip.track].push(clip);
      } else {
        groups.regular[clip.track] ??= [];
        groups.regular[clip.track].push(clip);
      }
      return groups;
    }, { regular: {}, effectLayers: {}, all: {} });
  }, [renderConfig]);

  const visualContent = useMemo(() => {
    const resolution = renderConfig.output.resolution;
    let accumulated: ReactNode = null;

    for (const track of visualTracks) {
      const trackClips = clipsByTrack.regular[track.id] ?? [];
      const trackContent: ReactNode = trackClips.length > 0
        ? <VisualTrack key={track.id} track={track} clips={trackClips} fps={fps} theme={theme} resolution={resolution} allClips={renderConfig.clips} />
        : null;
      let lowerTrackContent: ReactNode = accumulated;
      const effectLayers = sortClipsByAt(clipsByTrack.effectLayers[track.id] ?? []);

      if (lowerTrackContent && effectLayers.length > 0) {
        for (const effectLayer of effectLayers) {
          lowerTrackContent = (
            <EffectLayerSequence key={effectLayer.id} clip={effectLayer} fps={fps}>
              {lowerTrackContent}
            </EffectLayerSequence>
          );
        }
      }

      accumulated = lowerTrackContent && trackContent
        ? <>{lowerTrackContent}{trackContent}</>
        : (trackContent ?? lowerTrackContent);
    }

    return accumulated;
  }, [clipsByTrack.effectLayers, clipsByTrack.regular, fps, theme, visualTracks]);

  return (
    <AudioAnalysisProvider clips={audioClips} fps={fps} totalDurationInFrames={totalDurationInFrames}>
      <AbsoluteFill style={{ backgroundColor: 'black', overflow: 'hidden' }}>
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <AbsoluteFill style={{ position: 'relative', overflow: 'hidden' }}>{visualContent}</AbsoluteFill>
        </AbsoluteFill>
        {audioTracks.map((track) => (
          <AudioTrack
            key={track.id}
            track={track}
            clips={clipsByTrack.all[track.id] ?? []}
            fps={fps}
          />
        ))}
      </AbsoluteFill>
    </AudioAnalysisProvider>
  );
});
