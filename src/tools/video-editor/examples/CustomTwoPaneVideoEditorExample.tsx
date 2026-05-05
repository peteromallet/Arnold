import { memo, type CSSProperties, type ReactNode } from 'react';
import { cn } from '@/shared/components/ui/contracts/cn.ts';
import { PreviewPanel } from '@/tools/video-editor/components/PreviewPanel/PreviewPanel.tsx';
import { useVideoEditorPreviewSurface } from '@/tools/video-editor/components/PreviewPanel/useVideoEditorPreviewSurface.tsx';
import { PropertiesPanel } from '@/tools/video-editor/components/PropertiesPanel/PropertiesPanel.tsx';
import { VideoEditorAssetPanelSurface } from '@/tools/video-editor/components/PropertiesPanel/VideoEditorAssetPanelSurface.tsx';
import { TimelineEditor } from '@/tools/video-editor/components/TimelineEditor/TimelineEditor.tsx';
import { VideoEditorProvider, type VideoEditorProviderProps } from '@/tools/video-editor/contexts/VideoEditorProvider.tsx';
import {
  useTimelineChromeContext,
  useTimelineEditorData,
  useTimelinePlaybackContext,
} from '@/tools/video-editor/hooks/timelineStore.ts';
import { VIDEO_EDITOR_THEME_VARS } from '@/tools/video-editor/lib/themeTokens.ts';
import {
  useVideoEditorRenderContext,
  useVideoEditorSlotRenderers,
} from '@/tools/video-editor/runtime/useVideoEditorRenderContext.ts';
import type { VideoEditorRenderContext, VideoEditorSlotRenderer } from '@/tools/video-editor/runtime/extensionSurface.ts';

function resolveSlot(
  slotRenderer: VideoEditorSlotRenderer | undefined,
  context: VideoEditorRenderContext,
  fallback: ReactNode = null,
) {
  return slotRenderer ? slotRenderer(context) : fallback;
}

export interface CustomTwoPaneVideoEditorShellProps {
  className?: string;
  onOpenSequenceCreator?: () => void;
}

function CustomTwoPaneVideoEditorShellComponent({
  className,
  onOpenSequenceCreator,
}: CustomTwoPaneVideoEditorShellProps) {
  const renderContext = useVideoEditorRenderContext();
  const slotRenderers = useVideoEditorSlotRenderers();
  const previewSurface = useVideoEditorPreviewSurface();
  const editorData = useTimelineEditorData();
  const chrome = useTimelineChromeContext();
  const playback = useTimelinePlaybackContext();

  const header = resolveSlot(slotRenderers.header, renderContext, (
    <header className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-card/80 px-4 py-3">
      <div className="min-w-0">
        <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
          Custom two-pane shell
        </p>
        <h1 className="truncate text-lg font-semibold text-foreground">
          {renderContext.timelineName ?? 'Video editor'}
        </h1>
      </div>
      <div className="text-right text-xs text-muted-foreground">
        <p>{editorData.resolvedConfig?.output?.resolution ?? 'Unset resolution'}</p>
        <p>{editorData.selectedClipIds.size} selected</p>
      </div>
    </header>
  ));

  const toolbar = resolveSlot(slotRenderers.toolbar, renderContext, (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-card/60 px-4 py-2 text-sm text-muted-foreground">
      <span>Save status: {chrome.saveStatus}</span>
      <span>Time: {playback.formatTime(playback.currentTime)}</span>
    </div>
  ));

  const timelineFooter = resolveSlot(slotRenderers.timelineFooter, renderContext);
  const statusBar = resolveSlot(slotRenderers.statusBar, renderContext, (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-card/60 px-4 py-2 text-xs text-muted-foreground">
      <span>Preview-ready custom layout</span>
      <span>{editorData.resolvedConfig?.clips.length ?? 0} clips</span>
    </div>
  ));

  const leftPaneFallback = (
    <div className="flex min-h-0 flex-col gap-3">
      <PreviewPanel
        surface={previewSurface}
        panelClassName="min-h-[320px] flex-[1.15]"
        footer={(
          <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
            <span>{editorData.resolvedConfig?.output?.resolution ?? 'Unset resolution'}</span>
            <span>{playback.formatTime(playback.currentTime)}</span>
          </div>
        )}
      />
      <div className="min-h-[280px] flex-1 overflow-hidden rounded-2xl border border-border bg-card/80">
        <TimelineEditor onOpenSequenceCreator={onOpenSequenceCreator} />
      </div>
      {timelineFooter}
    </div>
  );

  const rightPaneFallback = (
    <div className="grid min-h-0 gap-3 xl:grid-rows-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
      <section className="min-h-0 overflow-auto rounded-2xl border border-border bg-card/70 p-3">
        {resolveSlot(
          slotRenderers.assetPanel,
          renderContext,
          <VideoEditorAssetPanelSurface includeBuiltIn />,
        )}
      </section>
      <section className="min-h-0 overflow-auto rounded-2xl border border-border bg-card/70 p-3">
        {resolveSlot(slotRenderers.inspectorPanel, renderContext, <PropertiesPanel />)}
      </section>
    </div>
  );

  return (
    <div
      className={cn('min-h-screen bg-background text-foreground', className)}
      style={VIDEO_EDITOR_THEME_VARS as CSSProperties}
      data-testid="custom-two-pane-shell"
    >
      <div className="mx-auto flex min-h-screen w-full max-w-[1600px] flex-col gap-3 p-4">
        {header}
        {toolbar}
        <div className="grid min-h-0 flex-1 gap-3 xl:grid-cols-[minmax(0,1.65fr)_minmax(320px,0.85fr)]">
          {resolveSlot(slotRenderers.leftPanel, renderContext, leftPaneFallback)}
          {resolveSlot(slotRenderers.rightPanel, renderContext, rightPaneFallback)}
        </div>
        {statusBar}
      </div>
      {resolveSlot(slotRenderers.dialogs, renderContext)}
    </div>
  );
}

export const CustomTwoPaneVideoEditorShell = memo(CustomTwoPaneVideoEditorShellComponent);

export interface CustomTwoPaneVideoEditorExampleProps
  extends Omit<VideoEditorProviderProps, 'children'> {
  className?: string;
  onOpenSequenceCreator?: () => void;
}

export function CustomTwoPaneVideoEditorExample({
  className,
  onOpenSequenceCreator,
  ...providerProps
}: CustomTwoPaneVideoEditorExampleProps) {
  return (
    <VideoEditorProvider {...providerProps}>
      <CustomTwoPaneVideoEditorShell
        className={className}
        onOpenSequenceCreator={onOpenSequenceCreator}
      />
    </VideoEditorProvider>
  );
}
