import {
  useRef,
  useState,
  useEffect,
  useCallback,
  type SyntheticEvent,
} from 'react';
import { GenerationRow } from '@/domains/generation/types';
import { useIsMobile, useIsTablet } from '@/shared/hooks/mobile';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { Button } from '@/shared/components/ui/button';
import { VariantSelector } from '@/shared/components/VariantSelector';
import {
  Scissors,
  RefreshCw,
  X,
  Sparkles
} from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn';
import { TooltipProvider } from '@/shared/components/ui/tooltip';
import { useQueryClient } from '@tanstack/react-query';
import { unifiedGenerationQueryKeys } from '@/shared/lib/queryKeys/unified';
import { getGenerationId } from '@/shared/lib/media/mediaTypeHelpers';
import { useVariants } from '@/shared/hooks/variants/useVariants';
import type { PortionSelection } from '@/shared/components/VideoPortionTimeline';
import { TrimControlsPanel } from '@/shared/components/VideoTrimEditor/components/TrimControlsPanel';
import { useVideoTrimming } from '@/shared/components/VideoTrimEditor/hooks/useVideoTrimming';
import { useTrimSave } from '@/shared/components/VideoTrimEditor/hooks/useTrimSave';
import { ModeSelector } from '@/domains/media-lightbox/components/ModeSelector';
import { VideoEnhanceForm } from '@/domains/media-lightbox/components/VideoEnhanceForm';
import { useVideoEnhance } from '@/domains/media-lightbox/hooks/useVideoEnhance';
import { DEFAULT_ENHANCE_SETTINGS } from '@/domains/media-lightbox/model/editSettingsTypes';
import type { VideoEnhanceSettings } from '@/domains/media-lightbox/model/editSettingsTypes';
import { VideoEditModeDisplay } from '@/domains/media-lightbox/components/VideoEditModeDisplay';
import { VideoTrimModeDisplay } from '@/domains/media-lightbox/components/VideoTrimModeDisplay';
import { MediaDisplayWithCanvas } from '@/domains/media-lightbox/components/MediaDisplayWithCanvas';
import {
  useReplaceMode,
  ReplacePanelContent,
} from './VideoReplaceMode';

// Default FPS for AI-generated videos
const DEFAULT_VIDEO_FPS = 16;

interface InlineEditVideoViewProps {
  media: GenerationRow;
  onClose: () => void;
  onVideoSaved?: (newVideoUrl: string) => Promise<void>;
  onNavigateToGeneration?: (generationId: string) => Promise<void>;
  initialSegments?: PortionSelection[];
  onSegmentsChange?: (segments: PortionSelection[]) => void;
}

export function InlineEditVideoView({
  media,
  onClose,
  initialSegments,
  onSegmentsChange,
}: InlineEditVideoViewProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const isMobile = useIsMobile();
  const isTablet = useIsTablet();
  // Use stacked layout for both mobile and tablet - video on top, settings below
  const useStackedLayout = isMobile || isTablet;
  const { selectedProjectId } = useProjectSelectionContext();
  const queryClient = useQueryClient();

  // Video edit sub-mode state: 'trim', 'replace', or 'enhance'
  const [videoEditSubMode, setVideoEditSubMode] = useState<'trim' | 'replace' | 'enhance'>('replace');
  const isReplaceModeActive = videoEditSubMode === 'replace';

  const generationId = getGenerationId(media);
  const {
    variants,
    activeVariant,
    isLoading: isLoadingVariants,
    setActiveVariantId,
    setPrimaryVariant,
    deleteVariant,
  } = useVariants({
    generationId,
    enabled: !!generationId,
  });

  useEffect(() => {
    if (variants.length === 0) {
      return;
    }

    const mediaParams = media.params as Record<string, unknown> | null | undefined;
    const mediaVariantId = typeof mediaParams?.variant_id === 'string'
      ? mediaParams.variant_id
      : null;
    const initialVariantId = [mediaVariantId, media.id].find((id): id is string => (
      typeof id === 'string' && variants.some(variant => variant.id === id)
    ));

    if (initialVariantId) {
      setActiveVariantId(initialVariantId);
    }
  }, [media.id, media.params, variants, setActiveVariantId]);

  const sourceVideoUrl = media.location || media.imageUrl || null;
  const sourceThumbnailUrl = media.thumbnail_url || media.thumbUrl;
  const videoUrl = activeVariant?.location || sourceVideoUrl;
  const thumbnailUrl = activeVariant?.thumbnail_url || sourceThumbnailUrl;
  const activeVariantId = activeVariant?.id || null;

  // --- Trim mode state ---
  const {
    trimState,
    setStartTrim,
    setEndTrim,
    resetTrim,
    setVideoDuration: setTrimVideoDuration,
    trimmedDuration,
    hasTrimChanges,
  } = useVideoTrimming();

  const {
    isSaving: isSavingTrim,
    saveProgress: trimSaveProgress,
    saveError: trimSaveError,
    saveSuccess: trimSaveSuccess,
    saveTrimmedVideo,
  } = useTrimSave({
    generationId: generationId ?? media.id,
    projectId: selectedProjectId,
    sourceVideoUrl: videoUrl ?? '',
    trimState,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: unifiedGenerationQueryKeys.projectPrefix(selectedProjectId) });
    },
  });

  const [videoDuration, setVideoDuration] = useState(0);
  const [videoFps, setVideoFps] = useState<number | null>(null);
  const [currentVideoTime, setCurrentVideoTime] = useState(0);

  const handleVideoDurationResolved = useCallback((duration: number) => {
    if (!Number.isFinite(duration) || duration <= 0) {
      return;
    }

    setVideoDuration(duration);
    setTrimVideoDuration(duration);
    setVideoFps(prev => prev ?? DEFAULT_VIDEO_FPS);
  }, [setTrimVideoDuration]);

  const handleEnhanceVideoLoadedMetadata = useCallback((event: SyntheticEvent<HTMLVideoElement>) => {
    handleVideoDurationResolved(event.currentTarget.duration);
  }, [handleVideoDurationResolved]);

  // --- Enhance mode state ---
  const [enhanceSettings, setEnhanceSettings] = useState<VideoEnhanceSettings>(DEFAULT_ENHANCE_SETTINGS);

  const videoEnhance = useVideoEnhance({
    projectId: selectedProjectId || undefined,
    videoUrl: videoUrl || undefined,
    generationId: generationId || undefined,
    activeVariantId,
    settings: enhanceSettings,
    updateSettings: (updates) => setEnhanceSettings(prev => ({ ...prev, ...updates })),
  });

  // --- Replace mode state (extracted to hook) ---
  const replaceState = useReplaceMode({
    media,
    videoUrl,
    videoDuration,
    videoFps,
    initialSegments,
    onSegmentsChange,
  });

  if (!media) return null;

  return (
    <TooltipProvider>
      <div className={cn(
        "w-full bg-background",
        useStackedLayout ? "flex flex-col" : "h-full flex flex-row"
      )}>
        {/* Left side: Video + Timeline (stacked vertically) */}
        <div className={cn(
          "flex flex-col min-h-0",
          useStackedLayout ? "w-full" : "flex-1 h-full"
        )}>
          {/* Video display area - uses same rendering components as MediaLightbox */}
          <div className={cn(
            "flex items-center justify-center relative overflow-hidden bg-zinc-900",
            useStackedLayout ? "w-full min-h-[38vh] touch-none z-10" : "flex-1 touch-none rounded-t-lg"
          )}>
            {isReplaceModeActive ? (
              <VideoEditModeDisplay
                videoRef={videoRef}
                videoUrl={videoUrl ?? ''}
                posterUrl={thumbnailUrl}
                videoDuration={videoDuration}
                onLoadedMetadata={handleVideoDurationResolved}
                selections={replaceState.selections}
                activeSelectionId={replaceState.activeSelectionId}
                onSelectionChange={replaceState.handleUpdateSelection}
                onSelectionClick={replaceState.setActiveSelectionId}
                onRemoveSelection={replaceState.handleRemoveSelection}
                onAddSelection={replaceState.handleAddSelection}
                fps={videoFps ?? DEFAULT_VIDEO_FPS}
              />
            ) : videoEditSubMode === 'trim' ? (
              <VideoTrimModeDisplay
                videoRef={videoRef}
                videoUrl={videoUrl ?? ''}
                posterUrl={thumbnailUrl}
                trimState={trimState}
                onLoadedMetadata={handleVideoDurationResolved}
                onTimeUpdate={setCurrentVideoTime}
                className="max-w-full max-h-full object-contain shadow-wes border border-border/20 rounded"
              />
            ) : (
              <MediaDisplayWithCanvas
                effectiveImageUrl={videoUrl ?? ''}
                thumbUrl={thumbnailUrl ?? undefined}
                isVideo={true}
                onVideoLoadedMetadata={handleEnhanceVideoLoadedMetadata}
                variant={useStackedLayout ? 'mobile-stacked' : 'desktop-side-panel'}
                containerClassName={useStackedLayout ? 'w-full h-full p-2' : 'w-full h-full p-4'}
                debugContext="InlineEditVideoView"
              />
            )}
          </div>
        </div>

        {/* Settings Panel */}
        <div className={cn(
          "bg-background overflow-y-auto flex flex-col",
          useStackedLayout ? "w-full border-t border-border" : "w-[40%] border-l border-border"
        )}>
          {/* Panel Header with Mode Selector and Close Button */}
          <div className={cn(
            "flex items-center justify-between border-b border-border bg-background flex-shrink-0",
            isMobile ? "px-3 py-2 gap-2" : "p-4 gap-3"
          )}>
            {/* Mode Selector */}
            <div className="flex-1">
              <ModeSelector
                items={[
                  {
                    id: 'trim',
                    label: 'Trim',
                    icon: <Scissors className="w-4 h-4" />,
                    onClick: () => setVideoEditSubMode('trim'),
                  },
                  {
                    id: 'replace',
                    label: 'Replace',
                    icon: <RefreshCw className="w-4 h-4" />,
                    onClick: () => setVideoEditSubMode('replace'),
                  },
                  {
                    id: 'enhance',
                    label: 'Enhance',
                    icon: <Sparkles className="w-4 h-4" />,
                    onClick: () => setVideoEditSubMode('enhance'),
                  },
                ]}
                activeId={videoEditSubMode}
              />
            </div>

            {/* Close Button */}
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onClose();
              }}
              className={cn("p-0 hover:bg-muted flex-shrink-0", isMobile ? "h-7 w-7" : "h-8 w-8")}
            >
              <X className={cn(isMobile ? "h-3.5 w-3.5" : "h-4 w-4")} />
            </Button>
          </div>

          {/* Panel Content - conditionally render based on mode */}
          <div className="flex-1 overflow-y-auto min-h-0">
            {videoEditSubMode === 'trim' && (
              <TrimControlsPanel
                trimState={trimState}
                onStartTrimChange={setStartTrim}
                onEndTrimChange={setEndTrim}
                onResetTrim={resetTrim}
                trimmedDuration={trimmedDuration}
                hasTrimChanges={hasTrimChanges}
                onSave={saveTrimmedVideo}
                isSaving={isSavingTrim}
                saveProgress={trimSaveProgress}
                saveError={trimSaveError}
                saveSuccess={trimSaveSuccess}
                onClose={onClose}
                variant={isMobile ? 'mobile' : 'desktop'}
                videoUrl={videoUrl || ''}
                currentTime={currentVideoTime}
                videoRef={videoRef}
                hideHeader
              />
            )}
            {isReplaceModeActive && (
              <ReplacePanelContent
                replaceState={replaceState}
                videoUrl={videoUrl}
                videoFps={videoFps}
                selectedProjectId={selectedProjectId}
              />
            )}
            {videoEditSubMode === 'enhance' && (
              <VideoEnhanceForm
                settings={videoEnhance.settings}
                onUpdateSetting={videoEnhance.updateSetting}
                onGenerate={videoEnhance.handleGenerate}
                isGenerating={videoEnhance.isGenerating}
                generateSuccess={videoEnhance.generateSuccess}
                canSubmit={videoEnhance.canSubmit}
                variant={isMobile ? 'mobile' : 'desktop'}
                videoUrl={videoUrl ?? undefined}
              />
            )}
          </div>
          <div className={cn(
            'border-t border-border bg-background/95 backdrop-blur-sm px-3 pt-3 pb-6',
            isMobile ? 'pb-8' : 'pb-6'
          )}>
            <VariantSelector
              variants={variants}
              activeVariantId={activeVariantId}
              onVariantSelect={setActiveVariantId}
              onMakePrimary={setPrimaryVariant}
              isLoading={isLoadingVariants}
              onDeleteVariant={deleteVariant}
            />
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
}
