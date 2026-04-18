import React from 'react';
import { Button } from "@/shared/components/ui/button";
import { Slider } from "@/shared/components/ui/slider";
import { Textarea } from "@/shared/components/ui/textarea";
import { Label } from "@/shared/components/ui/primitives/label";
import { Switch } from "@/shared/components/ui/switch";
import { Info, Eraser, Check } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/components/ui/tooltip";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { CollapsibleSection } from "@/shared/components/ui/composed/collapsible-section";
import { ResponsiveInfoTip } from '@/shared/components/ui/composed/responsive-info-tip';
import { ModelToggle } from '@/shared/components/ui/composed/model-toggle';
import { useIsMobile } from '@/shared/hooks/mobile';
import { Project } from '@/types/project';
import type { ActiveLora } from '@/domains/lora/types/lora';
import type { LoraModel } from '@/domains/lora/types/lora';
import {
  PhaseConfig,
  DEFAULT_PHASE_CONFIG,
  MODEL_DEFAULTS,
  clampFrameCountToPolicy,
  getModelSpec,
  resolveGenerationPolicy,
  type SelectedModel,
  type ExecutionMode,
} from '../settings';
import { framesToSeconds } from '@/shared/lib/media/videoUtils';

interface BatchPromptControls {
  batchVideoPrompt: string;
  onBatchVideoPromptChange: (value: string) => void;
  negativePrompt: string;
  onNegativePromptChange: (value: string) => void;
  enhancePrompt: boolean;
  onEnhancePromptChange: (value: boolean) => void;
  textBeforePrompts?: string;
  onTextBeforePromptsChange?: (value: string) => void;
  textAfterPrompts?: string;
  onTextAfterPromptsChange?: (value: string) => void;
}

interface BatchTimingControls {
  batchVideoFrames: number;
  onBatchVideoFramesChange: (value: number) => void;
  batchVideoSteps: number;
  onBatchVideoStepsChange: (value: number) => void;
  amountOfMotion: number;
  onAmountOfMotionChange: (value: number) => void;
}

interface BatchDimensionControls {
  dimensionSource: 'project' | 'firstImage' | 'custom';
  onDimensionSourceChange: (source: 'project' | 'firstImage' | 'custom') => void;
  customWidth?: number;
  onCustomWidthChange: (v: number | undefined) => void;
  customHeight?: number;
  onCustomHeightChange: (v: number | undefined) => void;
}

interface BatchContextControls {
  projects: Project[];
  selectedProjectId: string | null;
  isTimelineMode?: boolean;
  selectedLoras?: ActiveLora[];
  availableLoras?: LoraModel[];
  imageCount?: number;
}

interface BatchModeControls {
  accelerated: boolean;
  onAcceleratedChange: (value: boolean) => void;
  showStepsNotification?: boolean;
  randomSeed: boolean;
  onRandomSeedChange: (value: boolean) => void;
  turboMode: boolean;
  onTurboModeChange: (value: boolean) => void;
  smoothContinuations?: boolean;
  onSmoothContinuationsChange?: (value: boolean) => void;
  advancedMode: boolean;
  generationTypeMode?: ExecutionMode;
  guidanceScale?: number;
  onGuidanceScaleChange?: (value: number) => void;
  ltxHdResolution?: boolean;
  onLtxHdResolutionChange?: (value: boolean) => void;
}

interface BatchPhaseControls {
  phaseConfig?: PhaseConfig;
  onPhaseConfigChange: (config: PhaseConfig) => void;
  selectedPhasePresetId?: string | null;
  onPhasePresetSelect?: (presetId: string, config: PhaseConfig) => void;
  onPhasePresetRemove?: () => void;
}

interface BatchBehaviorControls {
  onBlurSave?: () => void;
  onClearEnhancedPrompts?: () => Promise<void>;
  videoControlMode?: 'individual' | 'batch';
  readOnly?: boolean;
  selectedModel: SelectedModel;
  onSelectedModelChange?: (model: SelectedModel) => void;
}

type BatchSettingsFormProps =
  & BatchPromptControls
  & BatchTimingControls
  & BatchDimensionControls
  & BatchContextControls
  & BatchModeControls
  & BatchPhaseControls
  & BatchBehaviorControls;

export const BatchSettingsForm: React.FC<BatchSettingsFormProps> = ({
  batchVideoPrompt,
  onBatchVideoPromptChange,
  batchVideoFrames,
  onBatchVideoFramesChange,
  batchVideoSteps,
  onBatchVideoStepsChange,
  negativePrompt,
  onNegativePromptChange,
  isTimelineMode,
  turboMode,
  smoothContinuations = false,
  onSmoothContinuationsChange,
  guidanceScale,
  onGuidanceScaleChange,
  ltxHdResolution,
  onLtxHdResolutionChange,
  imageCount = 0,
  enhancePrompt,
  onEnhancePromptChange,
  advancedMode,
  generationTypeMode = 'i2v',
  phaseConfig = DEFAULT_PHASE_CONFIG,
  onBlurSave,
  onClearEnhancedPrompts,
  textBeforePrompts = '',
  onTextBeforePromptsChange,
  textAfterPrompts = '',
  onTextAfterPromptsChange,
  selectedModel = 'wan-2.2',
  onSelectedModelChange,
  readOnly = false,
}) => {
    // Mobile detection for touch-friendly tooltips
    const isMobile = useIsMobile();
    const spec = getModelSpec(selectedModel);
    const modelDefaults = MODEL_DEFAULTS[spec.id];
    const generationIntent = {
      smoothContinuations,
      requestedExecutionMode: generationTypeMode,
    };
    const policy = resolveGenerationPolicy(spec, generationIntent);
    const frameStep = modelDefaults.frameStep;
    const maxFrames = policy.continuation.enabled ? policy.continuation.maxOutputFrames : spec.maxFrames;
    const resolvedFrameCount = clampFrameCountToPolicy(batchVideoFrames, spec, generationIntent);
    const [stepMin, stepMax] = spec.stepRange;
    const canShowSmoothContinuations = Boolean(spec.continuationByExecutionMode[policy.travelMode]);

    // State for clear enhanced prompts success feedback
    const [clearSuccess, setClearSuccess] = React.useState(false);

    // Dev-only: warn when the model spec says a field should render but the
    // required handler prop wasn't passed. Without this, the field silently
    // disappears at the callsite — no error, no render — and the bug is hard
    // to spot. Warnings are stripped in production via import.meta.env.DEV.
    React.useEffect(() => {
      if (!import.meta.env.DEV) return;
      const missing: string[] = [];
      if (canShowSmoothContinuations && !onSmoothContinuationsChange) {
        missing.push(
          `[BatchSettingsForm] Model "${selectedModel}" supports smoothContinuations but no onSmoothContinuationsChange handler was passed — the Continue toggle will not render. Check the callsite.`
        );
      }
      if (spec.ui.guidanceScale && !onGuidanceScaleChange) {
        missing.push(
          `[BatchSettingsForm] Model "${selectedModel}" supports guidanceScale but no onGuidanceScaleChange handler was passed — the guidance scale slider will not render. Check the callsite.`
        );
      }
      if (spec.resolutionTier === 'hd' && !onLtxHdResolutionChange) {
        missing.push(
          `[BatchSettingsForm] Model "${selectedModel}" supports HD resolution but no onLtxHdResolutionChange handler was passed — the HD Resolution toggle will not render. Check the callsite.`
        );
      }
      for (const msg of missing) console.warn(msg);
    }, [
      selectedModel,
      canShowSmoothContinuations,
      spec.ui.guidanceScale,
      spec.resolutionTier,
      onSmoothContinuationsChange,
      onGuidanceScaleChange,
      onLtxHdResolutionChange,
    ]);

    // Validation: Check for phaseConfig inconsistencies and warn
    React.useEffect(() => {
      if (phaseConfig && advancedMode) {
        const phasesLength = phaseConfig.phases?.length || 0;
        const stepsLength = phaseConfig.steps_per_phase?.length || 0;
        const numPhases = phaseConfig.num_phases;
        
        if (import.meta.env.DEV && numPhases !== phasesLength || numPhases !== stepsLength) {
          console.error('[BatchSettingsForm] INCONSISTENT PHASE CONFIG:', {
            num_phases: numPhases,
            phases_array_length: phasesLength,
            steps_array_length: stepsLength,
            phases_data: phaseConfig.phases?.map(p => ({
              phase: p.phase,
              guidance_scale: p.guidance_scale,
              loras_count: p.loras?.length
            })),
            steps_per_phase: phaseConfig.steps_per_phase,
          });
        }
      }
    }, [phaseConfig, advancedMode]);

    return (
        <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Left Column: Prompts with text before/after when applicable */}
                <div className="space-y-4">
                  {/* Main Prompt */}
                  <div className="relative">
                    <Label htmlFor="batchVideoPrompt" className="text-sm font-light block mb-1.5">
                      {(isTimelineMode || enhancePrompt)
                        ? 'Base Prompt:'
                        : 'Prompt:'
                      }
                    </Label>
                    <ResponsiveInfoTip
                      isMobile={isMobile}
                      content={(
                        <p>
                          {enhancePrompt
                            ? 'This text will be appended after AI-generated individual prompts for each pair.'
                            : 'This prompt guides the style and transition for all video segments.'
                          }
                          <br />
                          Small changes can have a big impact.
                        </p>
                      )}
                    />
                    <Textarea
                      id="batchVideoPrompt"
                      value={batchVideoPrompt}
                      onChange={(e) => onBatchVideoPromptChange(e.target.value)}
                      onBlur={() => onBlurSave?.()}
                      placeholder="Enter a global prompt for all video segments... (e.g., cinematic transition)"
                      className="min-h-[120px]"
                      rows={5}
                      readOnly={readOnly}
                      clearable={!readOnly}
                      onClear={() => onBatchVideoPromptChange('')}
                      voiceInput={!readOnly}
                      voiceContext="This is a video generation prompt for AI video transitions between images. Describe the motion, transition style, or visual transformation you want. Focus on movement, camera motion, or how elements should animate."
                      onVoiceResult={(result) => {
                        onBatchVideoPromptChange(result.prompt || result.transcription);
                      }}
                    />
                  </div>
                  
                </div>
                
                {/* Right Column: Negative Prompt - same height as main prompt */}
                <div className="relative">
                  <Label htmlFor="negative_prompt" className="text-sm font-light block mb-1.5">
                    {isTimelineMode ? 'Default Negative Prompt:' : 'Negative prompt:'}
                  </Label>
                  {isMobile ? (
                    <Popover>
                      <PopoverTrigger asChild>
                        <button 
                          type="button" 
                          className="absolute top-0 right-0 text-muted-foreground hover:text-foreground transition-colors bg-transparent border-0 p-0"
                        >
                          <Info className="h-4 w-4" />
                          <span className="sr-only">Info</span>
                        </button>
                      </PopoverTrigger>
                      <PopoverContent className="w-64 text-sm" side="left" align="start">
                        <p>Specify what you want to avoid in the generated videos, like 'blurry' or 'distorted'.</p>
                      </PopoverContent>
                    </Popover>
                  ) : (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="absolute top-0 right-0 text-muted-foreground cursor-help hover:text-foreground transition-colors">
                          <Info className="h-4 w-4" />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Specify what you want to avoid in the generated videos, <br /> like 'blurry' or 'distorted'.</p>
                      </TooltipContent>
                    </Tooltip>
                  )}
                  <Textarea
                    id="negative_prompt"
                    value={negativePrompt}
                    onChange={(e) => onNegativePromptChange(e.target.value)}
                    onBlur={() => onBlurSave?.()}
                    placeholder="e.g., blurry, low quality"
                    className="min-h-[120px]"
                    rows={5}
                    readOnly={readOnly}
                    clearable={!readOnly}
                    onClear={() => onNegativePromptChange('')}
                    voiceInput={!readOnly}
                    voiceContext="This is a negative prompt - things to AVOID in the video generation. List unwanted qualities like 'blurry, distorted, low quality, shaky'. Keep it as a comma-separated list of terms to avoid."
                    onVoiceResult={(result) => {
                      onNegativePromptChange(result.prompt || result.transcription);
                    }}
                  />
                </div>
            </div>

            {/* Additional prompt settings */}
            <CollapsibleSection title="Additional prompt settings">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="textBeforePrompts" className="text-sm font-light block mb-1.5">
                    Before each prompt:
                  </Label>
                  <Textarea
                    id="textBeforePrompts"
                    value={textBeforePrompts}
                    onChange={(e) => onTextBeforePromptsChange?.(e.target.value)}
                    onBlur={() => onBlurSave?.()}
                    placeholder="Text to prepend to each prompt..."
                    className="min-h-[60px] resize-none"
                    rows={2}
                    readOnly={readOnly}
                    clearable={!readOnly}
                    onClear={() => onTextBeforePromptsChange?.('')}
                    voiceInput={!readOnly}
                    voiceContext="This is text that will be prepended to every video generation prompt. Keep it short - things like style prefixes or descriptions that apply to all video segments."
                    onVoiceResult={(result) => {
                      onTextBeforePromptsChange?.(result.prompt || result.transcription);
                    }}
                  />
                </div>

                <div>
                  <Label htmlFor="textAfterPrompts" className="text-sm font-light block mb-1.5">
                    After each prompt:
                  </Label>
                  <Textarea
                    id="textAfterPrompts"
                    value={textAfterPrompts}
                    onChange={(e) => onTextAfterPromptsChange?.(e.target.value)}
                    onBlur={() => onBlurSave?.()}
                    placeholder="Text to append to each prompt..."
                    className="min-h-[60px] resize-none"
                    rows={2}
                    readOnly={readOnly}
                    clearable={!readOnly}
                    onClear={() => onTextAfterPromptsChange?.('')}
                    voiceInput={!readOnly}
                    voiceContext="This is text that will be appended to every video generation prompt. Keep it short - things like quality suffixes or parameters that apply to all video segments."
                    onVoiceResult={(result) => {
                      onTextAfterPromptsChange?.(result.prompt || result.transcription);
                    }}
                  />
                </div>
              </div>
            </CollapsibleSection>

            {/* Toggle row: Model + Enhance + HD + Smooth Continuations */}
            <div className="flex flex-wrap gap-2">
              {onSelectedModelChange && (
                <div className="min-w-[110px] flex-1">
                  <ModelToggle
                    selectedModel={selectedModel}
                    onSelectedModelChange={onSelectedModelChange}
                  />
                </div>
              )}
              {!turboMode && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="group relative flex items-center gap-x-2 p-2 bg-muted/30 rounded-lg border flex-1 min-w-[110px]">
                      <Switch
                        id="enhance-prompt"
                        checked={enhancePrompt}
                        onCheckedChange={onEnhancePromptChange}
                      />
                      <Label htmlFor="enhance-prompt" className="text-xs cursor-pointer">
                        Enhance Prompts
                      </Label>
                      {onClearEnhancedPrompts && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className={`absolute right-1 h-6 w-6 p-0 ${clearSuccess
                            ? "text-green-500 hover:text-green-500"
                            : "text-muted-foreground hover:text-foreground"
                          }`}
                          onClick={(e) => {
                            e.stopPropagation();
                            setClearSuccess(true);
                            setTimeout(() => setClearSuccess(false), 2000);
                            onClearEnhancedPrompts();
                          }}
                        >
                          {clearSuccess ? (
                            <Check className="h-3.5 w-3.5" />
                          ) : (
                            <Eraser className="h-3.5 w-3.5" />
                          )}
                        </Button>
                      )}
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>AI generates individual prompts for each pair based on the images</p>
                  </TooltipContent>
                </Tooltip>
              )}

              {spec.resolutionTier === 'hd' && onLtxHdResolutionChange && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="flex items-center gap-x-2 p-2 bg-muted/30 rounded-lg border flex-1 min-w-[110px]">
                      <Switch
                        id="ltx-hd-toggle"
                        checked={ltxHdResolution || false}
                        onCheckedChange={onLtxHdResolutionChange}
                      />
                      <Label htmlFor="ltx-hd-toggle" className="text-xs cursor-pointer">
                        HD Resolution
                      </Label>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Generate at 720p+ instead of ~500p for better quality</p>
                  </TooltipContent>
                </Tooltip>
              )}

              {canShowSmoothContinuations && onSmoothContinuationsChange && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="flex items-center gap-x-2 p-2 bg-muted/30 rounded-lg border flex-1 min-w-[110px]">
                      <Switch
                        id="batch-smooth-continuations"
                        checked={smoothContinuations}
                        onCheckedChange={onSmoothContinuationsChange}
                      />
                      <Label htmlFor="batch-smooth-continuations" className="text-xs cursor-pointer">
                        Continue
                      </Label>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Smoother transitions between segments (max {policy.continuation.maxOutputFrames} frames)</p>
                  </TooltipContent>
                </Tooltip>
              )}
            </div>

            {/* Inference Steps + Distilled/Full (LTX) - just above Guidance Scale */}
            {spec.ui.inferenceSteps && (
              <div className="flex gap-3 items-end">
                {onSelectedModelChange && spec.modelFamily === 'ltx' && (
                  <div className="flex rounded-lg border border-border overflow-hidden self-stretch">
                    <button
                      type="button"
                      onClick={() => onSelectedModelChange('ltx-2.3-fast')}
                      className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                        spec.id === 'ltx-2.3-fast'
                          ? 'bg-muted text-foreground'
                          : 'bg-transparent text-muted-foreground hover:text-foreground hover:bg-muted/50'
                      }`}
                    >
                      Distilled
                    </button>
                    <button
                      type="button"
                      onClick={() => onSelectedModelChange('ltx-2.3')}
                      className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                        spec.id === 'ltx-2.3'
                          ? 'bg-muted text-foreground'
                          : 'bg-transparent text-muted-foreground hover:text-foreground hover:bg-muted/50'
                      }`}
                    >
                      Full
                    </button>
                  </div>
                )}
                <div className="flex-1">
                  <Label htmlFor="batchVideoSteps" className="text-sm font-light block mb-1">
                    Inference steps: {batchVideoSteps}
                  </Label>
                  <Slider
                    id="batchVideoSteps"
                    min={stepMin}
                    max={stepMax}
                    step={1}
                    value={batchVideoSteps}
                    onValueChange={onBatchVideoStepsChange}
                    disabled={readOnly}
                    className={readOnly ? 'opacity-50' : ''}
                  />
                </div>
              </div>
            )}

            {/* Guidance Scale */}
            {spec.ui.guidanceScale && guidanceScale !== undefined && onGuidanceScaleChange && (
              <div className="relative">
                <Label htmlFor="guidanceScale" className="text-sm font-light block mb-1">
                  Guidance scale: {guidanceScale.toFixed(1)}
                </Label>
                <Slider
                  id="guidanceScale"
                  min={1}
                  max={10}
                  step={0.1}
                  value={guidanceScale}
                  onValueChange={(value) => {
                    const v = Array.isArray(value) ? (value[0] ?? guidanceScale) : value;
                    onGuidanceScaleChange(Number(Number(v).toFixed(1)));
                  }}
                  disabled={readOnly}
                  className={readOnly ? 'opacity-50' : ''}
                />
              </div>
            )}
            
            {/* Turbo Mode Toggle - DISABLED - keeping code for potential future use
            {isCloudGenerationEnabled && !isTurboModeDisabled && (
              <div className="flex items-center gap-x-2 p-3 bg-muted/30 rounded-lg border">
                <Switch
                  id="turbo-mode"
                  checked={turboMode}
                  onCheckedChange={(checked) => {
                    onTurboModeChange(checked);
                    // Auto-set frames to 81 when turbo mode is enabled
                    if (checked && batchVideoFrames !== 81) {
                      onBatchVideoFramesChange(81);
                    }
                  }}
                />
                <div className="flex-1">
                  <Label htmlFor="turbo-mode" className="font-medium">
                    Turbo Mode
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Using fast WAN 2.2 model for quick results ({framesToSeconds(81)})
                  </p>
                </div>
              </div>
            )}
            */}
            
            {/* Frames per pair - hidden in Timeline mode since users set duration individually */}
            {!isTimelineMode && (
              <div className="relative">
                <Label htmlFor="batchVideoFrames" className="text-sm font-light block mb-1">
                  {imageCount === 1 ? 'Duration to generate' : 'Duration per pair'}: {framesToSeconds(resolvedFrameCount, modelDefaults.fps)} ({resolvedFrameCount} frames)
                </Label>
                <ResponsiveInfoTip
                  isMobile={isMobile}
                  content={(
                    <p>
                      Determines the duration of the video segment{imageCount === 1 ? '' : ' for each image'}.
                      <br />
                      More frames result in a longer segment.
                    </p>
                  )}
                />
                <Slider
                  id="batchVideoFrames"
                  min={9}
                  max={maxFrames}
                  step={frameStep}
                  value={resolvedFrameCount}
                  onValueChange={(value) => onBatchVideoFramesChange(clampFrameCountToPolicy(value, spec, generationIntent))}
                  disabled={turboMode}
                  className={turboMode ? 'opacity-50' : ''}
                />
              </div>
            )}


        </div>
    );
};
