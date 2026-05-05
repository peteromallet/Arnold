import { useMemo } from 'react';
import { ExternalLink, Plus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/shared/components/ui/button.tsx';
import { Slider } from '@/shared/components/ui/slider.tsx';
import { RemotionPreview } from '@/tools/video-editor/components/PreviewPanel/RemotionPreview.tsx';
import { getTimelineDurationInFrames } from '@/tools/video-editor/lib/config-utils.ts';
import { useRenderDiagnostic } from '@/tools/video-editor/hooks/usePerfDiagnostics.ts';
import {
  useTimelineChromeContext,
  useTimelineEditorData,
  useTimelinePlaybackContext,
} from '@/tools/video-editor/hooks/timelineStore.ts';

interface CompactPreviewCoreProps {
  timelineId?: string | null;
  onCreateTimeline?: () => void;
  onOpenEditor?: (timelineId: string | null | undefined) => void;
}

export function CompactPreviewCore({ timelineId, onCreateTimeline, onOpenEditor }: CompactPreviewCoreProps) {
  useRenderDiagnostic('CompactPreviewCore');
  const { resolvedConfig } = useTimelineEditorData();
  const { saveStatus } = useTimelineChromeContext();
  const { previewRef, playerContainerRef, currentTime, onPreviewTimeUpdate } = useTimelinePlaybackContext();

  const totalSeconds = useMemo(() => {
    if (!resolvedConfig) {
      return 1;
    }

    return getTimelineDurationInFrames(resolvedConfig, resolvedConfig.output.fps) / resolvedConfig.output.fps;
  }, [resolvedConfig]);

  if (!resolvedConfig || !timelineId) {
    return (
      <div className="flex h-full items-center justify-center bg-background">
        <div className="rounded-xl border border-dashed border-border bg-card/60 p-6 text-center">
          <div className="text-sm font-medium text-foreground">No active timeline</div>
          <div className="mt-1 text-xs text-muted-foreground">Create one in the full editor or open an existing timeline.</div>
          <div className="mt-4 flex justify-center gap-2">
            <Button type="button" size="sm" onClick={() => onCreateTimeline?.()}>
              <Plus className="mr-1 h-4 w-4" />
              Create timeline
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={() => onOpenEditor?.(timelineId)}>
              Open editor
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div>
          <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Editor pane</div>
          <div className="text-sm text-foreground">Timeline {timelineId.slice(0, 8)} · {saveStatus}</div>
        </div>
        <Button type="button" size="sm" variant="outline" className="gap-1" onClick={() => onOpenEditor?.(timelineId)}>
          <ExternalLink className="h-3.5 w-3.5" />
          Open in editor
        </Button>
      </div>
      <section role="region" aria-label="Preview panel" className="min-h-0 flex-1 p-3">
        <div className="h-full overflow-hidden rounded-xl border border-border">
          <RemotionPreview
            ref={previewRef}
            config={resolvedConfig}
            compact
            onTimeUpdate={onPreviewTimeUpdate}
            playerContainerRef={playerContainerRef}
          />
        </div>
      </section>
      <div className="border-t border-border px-3 py-3">
        <Slider
          value={[currentTime]}
          min={0}
          max={Math.max(1, totalSeconds)}
          step={0.05}
          onValueChange={(value) => previewRef.current?.seek(value)}
        />
      </div>
    </div>
  );
}

interface CompactPreviewProps {
  timelineId?: string | null;
  onCreateTimeline?: () => void;
}

export function CompactPreview({ timelineId, onCreateTimeline }: CompactPreviewProps) {
  useRenderDiagnostic('CompactPreview');
  const navigate = useNavigate();

  return (
    <CompactPreviewCore
      timelineId={timelineId}
      onCreateTimeline={onCreateTimeline}
      onOpenEditor={(nextTimelineId) => navigate(nextTimelineId ? `/tools/video-editor?timeline=${nextTimelineId}` : '/tools/video-editor')}
    />
  );
}
