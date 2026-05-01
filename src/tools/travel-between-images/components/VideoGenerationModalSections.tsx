import React, { useMemo, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { getDisplayUrl } from '@/shared/lib/media/mediaUrl';
import { ExternalLinkTooltipButton } from '@/shared/components/ui/composed/ExternalLinkTooltipButton';
import { Skeleton } from '@/shared/components/ui/skeleton';
import { BatchSettingsForm } from '@/tools/travel-between-images/components/BatchSettingsForm';
import { MotionControl } from '@/tools/travel-between-images/components/MotionControl';
import { PanelSectionHeader } from '@/tools/travel-between-images/components/shared/PanelSectionHeader';
import { ShotImagesEditor } from '@/tools/travel-between-images/components/ShotImagesEditor';
import { FinalVideoSection } from '@/tools/travel-between-images/components/FinalVideoSection';
import { ImageManagerSkeleton } from '@/tools/travel-between-images/components/ShotEditor/ui/Skeleton';
import { DEFAULT_PHASE_CONFIG, coerceSelectedModel, getModelSpec, type SelectedModel, type VideoTravelSettings } from '@/tools/travel-between-images/settings';
import {
  useVideoTravelSettingsHandlers,
  useMotionSettings,
  useModelSettings,
  useSettingsSave,
} from '@/tools/travel-between-images/providers';
import { useModalImageHandlers } from './hooks/useModalImageHandlers';
import { useSegmentOutputsForShot } from '@/shared/hooks/segments/useSegmentOutputsForShot';
import { useProjectVideoCountsCache } from '@/shared/hooks/projects/useProjectVideoCountsCache';
import type { GenerationRow } from '@/domains/generation/types';
import type { ActiveLora, LoraModel } from '@/domains/lora/types/lora';
import type { TravelGuidanceMode } from '@/shared/lib/tasks/travelGuidance';
import type { Project } from '@/types/project';
import type { ShotImagesEditorProps } from '@/tools/travel-between-images/components/ShotImagesEditor/types';

interface PositionedImagePreview {
  id?: string;
  thumbUrl?: string | null;
  imageUrl?: string | null;
  location?: string | null;
}

interface VideoGenerationModalHeaderProps {
  shotName: string | undefined;
  onNavigateToShot: () => void;
}

export function VideoGenerationModalHeader({
  shotName,
  onNavigateToShot,
}: VideoGenerationModalHeaderProps): React.ReactElement {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xl font-light">
        Generate Video - <span className="preserve-case">{shotName || 'Unnamed Shot'}</span>
      </span>
      <ExternalLinkTooltipButton
        onClick={onNavigateToShot}
        tooltipLabel="Open Shot Editor"
      />
    </div>
  );
}

export function VideoGenerationModalLoadingContent(): React.ReactElement {
  return (
    <div className="space-y-4 pb-4">
      <div className="flex flex-col lg:flex-row gap-6">
        <div className="lg:w-1/2">
          <div className="mb-4">
            <Skeleton className="h-6 w-20" />
          </div>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-[70px] w-full rounded-md" />
              </div>
              <div className="space-y-1.5">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-[70px] w-full rounded-md" />
              </div>
            </div>
            <Skeleton className="h-12 w-full rounded-lg" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-9 w-full rounded-md" />
              </div>
              <div className="space-y-1.5">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-9 w-full rounded-md" />
              </div>
            </div>
            <div className="space-y-1">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-5 w-full rounded-full" />
            </div>
          </div>
        </div>

        <div className="lg:w-1/2">
          <div className="mb-4">
            <Skeleton className="h-6 w-16" />
          </div>
          <div className="space-y-4">
            <Skeleton className="h-10 w-full rounded-md" />
            <div className="flex gap-2">
              <Skeleton className="h-8 w-16 rounded-full" />
              <Skeleton className="h-8 w-20 rounded-full" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface VideoGenerationModalFormContentProps {
  settings: VideoTravelSettings;
  updateField: <K extends keyof VideoTravelSettings>(key: K, value: VideoTravelSettings[K]) => void;
  projects: Project[];
  selectedProjectId: string | null;
  selectedLoras: ActiveLora[];
  availableLoras: LoraModel[] | undefined;
  accelerated: boolean;
  onAcceleratedChange: (value: boolean) => void;
  randomSeed: boolean;
  onRandomSeedChange: (value: boolean) => void;
  imageCount: number;
  hasStructureVideo: boolean;
  guidanceKind?: TravelGuidanceMode;
  validPresetId: string | undefined;
  status: 'idle' | 'loading' | 'ready' | 'saving' | 'error';
  onOpenLoraModal: () => void;
  onRemoveLora: (loraId: string) => void;
  onLoraStrengthChange: (loraId: string, strength: number) => void;
  onAddTriggerWord: (word: string) => void;
}

export function VideoGenerationModalFormContent({
  settings,
  updateField,
  projects,
  selectedProjectId,
  selectedLoras,
  availableLoras,
  accelerated,
  onAcceleratedChange,
  randomSeed,
  onRandomSeedChange,
  imageCount,
  hasStructureVideo,
  guidanceKind,
  validPresetId,
  status,
  onOpenLoraModal,
  onRemoveLora,
  onLoraStrengthChange,
  onAddTriggerWord,
}: VideoGenerationModalFormContentProps): React.ReactElement {
  const selectedModel = coerceSelectedModel(settings.selectedModel);
  const handlers = useVideoTravelSettingsHandlers();
  const {
    handleGenerationTypeModeChange,
    handlePhaseConfigChange,
    handlePhasePresetRemove,
    handlePhasePresetSelect,
  } = handlers;

  // Pull the handlers that BatchSettingsForm gates fields on. These live on the
  // VideoTravelSettingsProvider (which VideoGenerationModal wraps around this
  // component). Without them, BatchSettingsForm silently hides the model
  // toggle, smooth-continuations, guidance scale, and LTX HD resolution
  // controls — which is how this form drifted behind BatchModeContent.
  const motionSettings = useMotionSettings();
  const modelSettings = useModelSettings();
  const { onBlurSave } = useSettingsSave();

  const ltxSelected = getModelSpec(selectedModel).modelFamily === 'ltx';
  const handleSelectedModelChange = (nextModel: SelectedModel) => {
    if (nextModel === 'wan-2.2') {
      modelSettings.setSelectedModel('wan-2.2');
      return;
    }
    if (getModelSpec(nextModel).modelFamily !== 'ltx') {
      return;
    }
    modelSettings.setSelectedModel(ltxSelected ? nextModel : 'ltx-2.3-fast');
  };

  return (
    <div className="space-y-6 pb-4">
      <div className="flex flex-col lg:flex-row gap-6">
        <div className="lg:w-1/2">
          <PanelSectionHeader title="Settings" theme="orange" />
          <BatchSettingsForm
            selectedModel={selectedModel}
            onSelectedModelChange={handleSelectedModelChange}
            batchVideoPrompt={settings.prompt || ''}
            onBatchVideoPromptChange={(v) => updateField('prompt', v)}
            batchVideoFrames={settings.batchVideoFrames || 61}
            onBatchVideoFramesChange={(v) => updateField('batchVideoFrames', v)}
            batchVideoSteps={settings.batchVideoSteps || 6}
            onBatchVideoStepsChange={(v) => updateField('batchVideoSteps', v)}
            dimensionSource={settings.dimensionSource || 'firstImage'}
            onDimensionSourceChange={(v) => updateField('dimensionSource', v)}
            customWidth={settings.customWidth}
            onCustomWidthChange={(v) => updateField('customWidth', v)}
            customHeight={settings.customHeight}
            onCustomHeightChange={(v) => updateField('customHeight', v)}
            negativePrompt={settings.negativePrompt || ''}
            onNegativePromptChange={(v) => updateField('negativePrompt', v)}
            projects={projects}
            selectedProjectId={selectedProjectId}
            selectedLoras={selectedLoras}
            availableLoras={availableLoras}
            isTimelineMode={false}
            accelerated={accelerated}
            onAcceleratedChange={onAcceleratedChange}
            randomSeed={randomSeed}
            onRandomSeedChange={onRandomSeedChange}
            turboMode={settings.turboMode || false}
            onTurboModeChange={(v) => updateField('turboMode', v)}
            smoothContinuations={motionSettings.smoothContinuations}
            onSmoothContinuationsChange={motionSettings.setSmoothContinuations}
            guidanceScale={modelSettings.guidanceScale}
            onGuidanceScaleChange={modelSettings.setGuidanceScale}
            ltxHdResolution={modelSettings.ltxHdResolution}
            onLtxHdResolutionChange={modelSettings.setLtxHdResolution}
            amountOfMotion={settings.amountOfMotion || 50}
            onAmountOfMotionChange={(v) => updateField('amountOfMotion', v)}
            imageCount={imageCount}
            enhancePrompt={settings.enhancePrompt}
            onEnhancePromptChange={(v) => updateField('enhancePrompt', v)}
            advancedMode={(settings.motionMode || 'basic') === 'advanced'}
            generationTypeMode={settings.generationTypeMode || 'i2v'}
            phaseConfig={settings.phaseConfig || DEFAULT_PHASE_CONFIG}
            onPhaseConfigChange={handlePhaseConfigChange}
            selectedPhasePresetId={validPresetId}
            onPhasePresetSelect={handlePhasePresetSelect}
            onPhasePresetRemove={handlePhasePresetRemove}
            onBlurSave={onBlurSave}
            videoControlMode="batch"
            textBeforePrompts={settings.textBeforePrompts || ''}
            onTextBeforePromptsChange={(v) => updateField('textBeforePrompts', v)}
            textAfterPrompts={settings.textAfterPrompts || ''}
            onTextAfterPromptsChange={(v) => updateField('textAfterPrompts', v)}
          />
        </div>

        <div className="lg:w-1/2">
          <PanelSectionHeader title="Motion" theme="purple" />
          <MotionControl
            mode={{
              motionMode: (settings.motionMode || 'basic') as 'basic' | 'advanced',
              onMotionModeChange: (v) => {
                updateField('motionMode', v);
                updateField('advancedMode', v === 'advanced');
              },
              selectedModel,
              generationTypeMode: settings.generationTypeMode || 'i2v',
              onGenerationTypeModeChange: handleGenerationTypeModeChange,
              hasStructureVideo,
              guidanceKind,
            }}
            lora={{
              selectedLoras,
              availableLoras: availableLoras || [],
              onAddLoraClick: onOpenLoraModal,
              onRemoveLora,
              onLoraStrengthChange,
              onAddTriggerWord: (word) => onAddTriggerWord(word),
            }}
            presets={{
              selectedPhasePresetId: validPresetId,
              onPhasePresetSelect: handlePhasePresetSelect,
              onPhasePresetRemove: handlePhasePresetRemove,
              currentSettings: {},
            }}
            advanced={{
              phaseConfig: settings.phaseConfig || DEFAULT_PHASE_CONFIG,
              onPhaseConfigChange: handlePhaseConfigChange,
              onBlurSave,
              randomSeed,
              onRandomSeedChange,
            }}
            stateOverrides={{
              turboMode: settings.turboMode || false,
              settingsLoading: status !== 'ready' && status !== 'saving',
            }}
          />
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Collapsible Accordion Section
// =============================================================================

interface ModalAccordionSectionProps {
  title: string;
  defaultOpen?: boolean;
  summary: React.ReactNode;
  children: React.ReactNode;
}

export function ModalAccordionSection({ title, defaultOpen = false, summary, children }: ModalAccordionSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-zinc-700 rounded-lg overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between px-4 py-2.5 bg-zinc-800/50 hover:bg-zinc-800 transition-colors text-sm font-medium text-zinc-300"
        onClick={() => setIsOpen((prev) => !prev)}
      >
        <span>{title}</span>
        <ChevronDown className={`h-4 w-4 transition-transform duration-200 ${isOpen ? '' : '-rotate-90'}`} />
      </button>
      {isOpen ? (
        <div className="border-t border-zinc-700">{children}</div>
      ) : (
        <div className="px-4 py-3 border-t border-zinc-700/50">{summary}</div>
      )}
    </div>
  );
}

// =============================================================================
// Shot Images Section (real ShotImagesEditor in readOnly batch mode)
// =============================================================================

const noop = () => {};
const emptyMap = new Map<string, number>();

interface ModalShotImagesEditorProps {
  shotId: string;
  projectId: string;
  images: GenerationRow[];
  batchVideoFrames: number;
  projectAspectRatio?: string;
}

function ModalShotImagesEditor({ shotId, projectId, images, batchVideoFrames, projectAspectRatio }: ModalShotImagesEditorProps) {
  const [generationMode, setGenerationMode] = useState<'batch' | 'timeline'>('batch');
  const handlers = useModalImageHandlers(shotId, projectId, images, batchVideoFrames);

  const editorProps: ShotImagesEditorProps = useMemo(() => ({
    displayOptions: {
      isModeReady: true,
      isMobile: false,
      generationMode,
      onGenerationModeChange: setGenerationMode as (mode: 'batch' | 'timeline' | 'by-pair') => void,
      columns: 4 as const,
      skeleton: <ImageManagerSkeleton />,
      projectAspectRatio,
    },
    imageState: {
      selectedShotId: shotId,
      projectId,
      preloadedImages: images,
      batchVideoFrames,
      pendingPositions: emptyMap,
      unpositionedGenerationsCount: 0,
      fileInputKey: 0,
      isUploadingImage: handlers.isUploadingImage,
      uploadProgress: handlers.uploadProgress,
    },
    editActions: {
      onImageReorder: handlers.onImageReorder,
      onFramePositionsChange: noop,
      onFileDrop: handlers.onFileDrop,
      onGenerationDrop: handlers.onGenerationDrop,
      onBatchFileDrop: handlers.onBatchFileDrop,
      onBatchGenerationDrop: handlers.onBatchGenerationDrop,
      onPendingPositionApplied: noop,
      onImageDelete: handlers.onImageDelete,
      onBatchImageDelete: handlers.onBatchImageDelete,
      onImageDuplicate: handlers.onImageDuplicate,
      onOpenUnpositionedPane: noop,
      onImageUpload: handlers.onImageUpload,
    },
    shotWorkflow: {},
  }), [shotId, projectId, images, batchVideoFrames, projectAspectRatio, generationMode, handlers]);

  return <ShotImagesEditor {...editorProps} />;
}

function ShotImagesSummary({ images }: { images: PositionedImagePreview[] }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1">
        {images.slice(0, 8).map((img, idx) => (
          <img
            key={img.id || idx}
            src={getDisplayUrl(img.thumbUrl || img.imageUrl || img.location)}
            alt={`Image ${idx + 1}`}
            className="w-6 h-6 object-cover rounded border border-zinc-600"
          />
        ))}
        {images.length > 8 && (
          <span className="text-xs text-zinc-400 ml-1">+{images.length - 8}</span>
        )}
      </div>
      <span className="text-xs text-zinc-400">
        {images.length} image{images.length !== 1 ? 's' : ''} · Batch mode
      </span>
    </div>
  );
}

// =============================================================================
// Final Video collapsed summary
// =============================================================================

function FinalVideoSummary() {
  return (
    <span className="text-xs text-zinc-400">Click to view final video output</span>
  );
}

// =============================================================================
// Generation Settings collapsed summary
// =============================================================================

function GenerationSettingsSummary({ settings }: { settings: VideoTravelSettings }) {
  const model = coerceSelectedModel(settings.selectedModel);
  const frames = settings.batchVideoFrames || 61;
  const prompt = settings.prompt || '';
  const truncatedPrompt = prompt.length > 60 ? prompt.slice(0, 57) + '...' : prompt;

  return (
    <div className="flex items-center gap-3 text-xs text-zinc-400">
      <span className="font-medium text-zinc-300">{model}</span>
      <span className="text-zinc-600">·</span>
      <span>{frames} frames</span>
      {truncatedPrompt && (
        <>
          <span className="text-zinc-600">·</span>
          <span className="truncate max-w-[200px] italic">&ldquo;{truncatedPrompt}&rdquo;</span>
        </>
      )}
    </div>
  );
}

// =============================================================================
// Accordion Content (combines all three sections)
// =============================================================================

export interface VideoGenerationModalAccordionContentProps extends VideoGenerationModalFormContentProps {
  defaultTopOpen?: boolean;
  defaultFinalVideoOpen?: boolean;
  defaultBottomOpen?: boolean;
  shotId: string;
  projectId: string;
  positionedImages: PositionedImagePreview[];
  shotGenerations: GenerationRow[];
  effectiveAspectRatio?: string;
}

export function VideoGenerationModalAccordionContent({
  defaultTopOpen = false,
  defaultFinalVideoOpen = false,
  defaultBottomOpen = true,
  shotId,
  projectId,
  positionedImages,
  shotGenerations,
  effectiveAspectRatio,
  ...formProps
}: VideoGenerationModalAccordionContentProps) {
  const segmentOutputs = useSegmentOutputsForShot(shotId, projectId);
  const hasFinalVideo = segmentOutputs.parentGenerations.some((p) => Boolean(p.location));
  const { getFinalVideoCount } = useProjectVideoCountsCache(projectId || null);
  const cachedFinalVideoCount = getFinalVideoCount(shotId);
  const willHaveFinalVideo = cachedFinalVideoCount !== null && cachedFinalVideoCount > 0;
  const shouldRenderFinalVideoSection = hasFinalVideo || willHaveFinalVideo;
  const imageHandlers = useModalImageHandlers(shotId, projectId, shotGenerations, formProps.settings.batchVideoFrames || 61);

  return (
    <div className="space-y-4">
      {shouldRenderFinalVideoSection && (
        <ModalAccordionSection
          title="Final Video"
          defaultOpen={defaultFinalVideoOpen}
          summary={<FinalVideoSummary />}
        >
          <FinalVideoSection
            shotId={shotId}
            projectId={projectId}
            projectAspectRatio={effectiveAspectRatio}
            getFinalVideoCount={getFinalVideoCount}
            isParentLoading={segmentOutputs.isLoading}
            onDelete={imageHandlers.onDeleteFinalVideo}
          />
        </ModalAccordionSection>
      )}

      <ModalAccordionSection
        title="Shot Images"
        defaultOpen={defaultTopOpen}
        summary={<ShotImagesSummary images={positionedImages} />}
      >
        <ModalShotImagesEditor
          shotId={shotId}
          projectId={projectId}
          images={shotGenerations}
          batchVideoFrames={formProps.settings.batchVideoFrames || 61}
          projectAspectRatio={effectiveAspectRatio}
        />
      </ModalAccordionSection>

      <ModalAccordionSection
        title="Generation Settings"
        defaultOpen={defaultBottomOpen}
        summary={<GenerationSettingsSummary settings={formProps.settings} />}
      >
        <VideoGenerationModalFormContent {...formProps} />
      </ModalAccordionSection>
    </div>
  );
}
