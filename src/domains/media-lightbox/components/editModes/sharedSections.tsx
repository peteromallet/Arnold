import React from 'react';
import { Button } from '@/shared/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { Textarea } from '@/shared/components/ui/textarea';
import { Switch } from '@/shared/components/ui/switch';
import { Label } from '@/shared/components/ui/primitives/label';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { XCircle, Layers, Plus } from 'lucide-react';
import { cn } from '@/shared/components/ui/contracts/cn';
import { ActiveLoRAsDisplay } from '@/domains/lora/components';
import type { LoraModel } from '@/domains/lora/types/lora';
import type { LoraManagerState } from '@/domains/lora/types/loraManager';
import type { EditAdvancedSettings as EditAdvancedSettingsType } from '../../hooks/useGenerationEditSettings';
import type { EditModePanelState } from '../../hooks/useEditModePanelState';
import { EditAdvancedSettings } from '../EditAdvancedSettings';
import { GenerateButton } from './GenerateButton';
import { getClosestOverlayContainer } from '@/shared/components/ui/overlay';

const REPOSITION_DEFAULT_PROMPT = 'match existing content';

function blurActiveElement() {
  if (document.activeElement instanceof HTMLElement) {
    document.activeElement.blur();
  }
}

function useSelectPortalContainer<T extends HTMLElement>() {
  const sectionRef = React.useRef<T | null>(null);
  const [container, setContainer] = React.useState<HTMLElement | null>(null);

  React.useLayoutEffect(() => {
    const nextContainer = getClosestOverlayContainer(sectionRef.current);
    setContainer(nextContainer ?? null);
  }, []);

  return { sectionRef, container };
}

export interface SharedEditPanelProps {
  state: EditModePanelState;
  isCloudMode?: boolean;
  editLoraManager?: LoraManagerState;
  availableLoras: LoraModel[];
  advancedSettings?: EditAdvancedSettingsType;
  setAdvancedSettings?: (updates: Partial<EditAdvancedSettingsType>) => void;
  isLocalGeneration?: boolean;
}

interface SectionLabelProps {
  isMobile: boolean;
  children: React.ReactNode;
}

export const SectionLabel: React.FC<SectionLabelProps> = ({ isMobile, children }) => (
  isMobile ? (
    <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
      {children}
    </div>
  ) : null
);

interface PromptSectionProps {
  state: EditModePanelState;
  mode: 'text' | 'inpaint' | 'annotate' | 'reposition';
}

export const PromptSection: React.FC<PromptSectionProps> = ({ state, mode }) => {
  const isRepositionMode = mode === 'reposition';
  const isUsingDefaultPrompt = isRepositionMode && !state.inpaintPrompt && !state.hasUserEditedPrompt;
  const displayPromptValue = isUsingDefaultPrompt ? REPOSITION_DEFAULT_PROMPT : state.inpaintPrompt;

  const placeholder =
    mode === 'text'
      ? (state.isMobile ? 'Describe changes...' : 'Describe the text-based edit to make...')
      : mode === 'annotate'
        ? (state.isMobile ? 'What to generate...' : 'Describe what to generate in the annotated regions...')
        : mode === 'reposition'
          ? ''
          : (state.isMobile ? 'What to generate...' : 'Describe what to generate in the masked area...');

  return (
    <div className={state.generationsSpacing}>
      <SectionLabel isMobile={state.isMobile}>Prompt</SectionLabel>
      <div className="flex items-center gap-2">
        {!state.isMobile && (
          <label className={`${state.labelSize} font-medium`}>
            Prompt{isRepositionMode ? ' (optional)' : ''}:
          </label>
        )}
        {isUsingDefaultPrompt && (
          <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] text-primary">
            Default
          </span>
        )}
      </div>
      <Textarea
        value={displayPromptValue}
        onChange={(e) => {
          state.setHasUserEditedPrompt(true);
          state.setInpaintPrompt(e.target.value);
        }}
        onBlur={() => {
          void state.flushTextFields();
        }}
        placeholder={placeholder}
        className={`w-full ${state.textareaMinHeight} ${state.textareaPadding} ${state.textareaTextSize} resize-none`}
        rows={state.textareaRows}
        clearable
        onClear={() => {
          state.setHasUserEditedPrompt(true);
          state.setInpaintPrompt('');
        }}
        voiceInput
        voiceContext="This is an image editing prompt. Describe what changes to make to the image - what to add, remove, or modify in the selected/masked area. Be specific about the visual result you want."
        onVoiceResult={(result) => {
          state.setHasUserEditedPrompt(true);
          state.setInpaintPrompt(result.prompt || result.transcription);
        }}
      />
    </div>
  );
};

interface ModelAndLoraSectionProps {
  state: EditModePanelState;
  isCloudMode?: boolean;
  editLoraManager?: LoraManagerState;
  availableLoras: LoraModel[];
}

export const ModelAndLoraSection: React.FC<ModelAndLoraSectionProps> = ({
  state,
  isCloudMode,
  editLoraManager,
  availableLoras,
}) => {
  const { sectionRef, container } = useSelectPortalContainer<HTMLDivElement>();

  if (!editLoraManager && !state.setQwenEditModel) {
    return null;
  }

  const isKleinModel = state.qwenEditModel?.startsWith('flux-klein-');

  return (
    <div ref={sectionRef} className={state.generationsSpacing}>
      <SectionLabel isMobile={state.isMobile}>{isKleinModel ? 'Model' : 'Model & LoRAs'}</SectionLabel>
      <div className={cn('flex items-center gap-2', state.isMobile ? 'mb-1' : 'mb-2')}>
        {state.setQwenEditModel && (
          <Select
            value={state.qwenEditModel}
            onValueChange={(value) => {
              if (value) {
                state.setQwenEditModel(value);
              }
            }}
          >
            <SelectTrigger
              variant="retro"
              className={cn('w-[40%]', state.isMobile ? 'h-7 text-xs' : 'h-10')}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent container={container} variant="retro">
              <SelectItem variant="retro" value="qwen-edit">Qwen-Edit</SelectItem>
              <SelectItem variant="retro" value="qwen-edit-2509">Qwen-Edit-2509</SelectItem>
              <SelectItem variant="retro" value="qwen-edit-2511">Qwen-Edit-2511</SelectItem>
              {isCloudMode && (
                <>
                  <SelectItem variant="retro" value="flux-klein-4b">Klein 4B</SelectItem>
                  <SelectItem variant="retro" value="flux-klein-9b">Klein 9B</SelectItem>
                </>
              )}
            </SelectContent>
          </Select>
        )}
        {editLoraManager && !isKleinModel && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              blurActiveElement();
              editLoraManager.setIsLoraModalOpen(true);
            }}
            className={cn(
              'flex h-10 w-[40%] items-center justify-center gap-1 px-2 text-xs',
              state.isMobile && 'h-6 text-[10px]',
            )}
          >
            <Plus className={cn(state.isMobile ? 'h-2.5 w-2.5' : 'h-3 w-3')} />
            <span>LoRA</span>
          </Button>
        )}
      </div>

      {editLoraManager && !isKleinModel && editLoraManager.selectedLoras.length > 0 && (
        <ActiveLoRAsDisplay
          selectedLoras={editLoraManager.selectedLoras}
          onRemoveLora={editLoraManager.handleRemoveLora}
          onLoraStrengthChange={editLoraManager.handleLoraStrengthChange}
          isGenerating={state.isGeneratingInpaint || state.isCreatingMagicEditTasks}
          availableLoras={availableLoras}
          className={state.isMobile ? 'mt-1' : 'mt-2'}
        />
      )}
    </div>
  );
};

interface LegacyLoraSectionProps {
  state: EditModePanelState;
  hasManagedLoras: boolean;
}

export const LegacyLoraSection: React.FC<LegacyLoraSectionProps> = ({ state, hasManagedLoras }) => {
  const { sectionRef, container } = useSelectPortalContainer<HTMLDivElement>();

  if (hasManagedLoras || state.qwenEditModel?.startsWith('flux-klein-')) {
    return null;
  }

  return (
    <div ref={sectionRef}>
      <SectionLabel isMobile={state.isMobile}>Style LoRA</SectionLabel>
      <div className="flex items-center gap-2">
        {!state.isMobile && <label className="text-sm font-medium whitespace-nowrap">LoRA:</label>}
        <div className="flex flex-1 items-center gap-1">
          <Select value={state.loraMode} onValueChange={(value) => value && state.setLoraMode(value)}>
            <SelectTrigger variant="retro" className={cn('flex-1', state.isMobile ? 'h-7 text-xs' : 'h-10')}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent container={container} variant="retro">
              <SelectItem variant="retro" value="none">None</SelectItem>
              <SelectItem variant="retro" value="in-scene">InScene</SelectItem>
              <SelectItem variant="retro" value="next-scene">Next Scene</SelectItem>
              <SelectItem variant="retro" value="custom">Custom</SelectItem>
            </SelectContent>
          </Select>
          {state.loraMode !== 'none' && (
            <Button
              variant="ghost"
              size="sm"
              onClick={state.handleClearLora}
              className={cn('h-9 w-9 shrink-0 p-0 hover:bg-muted', state.isMobile && 'h-7 w-7')}
              title="Clear LoRA selection"
            >
              <XCircle className={cn('h-4 w-4 text-muted-foreground', state.isMobile && 'h-3 w-3')} />
            </Button>
          )}
        </div>
      </div>

      {state.loraMode === 'custom' && (
        <input
          type="text"
          value={state.customLoraUrl}
          onChange={(e) => state.setCustomLoraUrl(e.target.value)}
          onBlur={() => {
            void state.flushTextFields();
          }}
          placeholder="Enter a Hugging Face LoRA URL"
          className={cn(
            'preserve-case mt-1.5 w-full rounded-md border border-input bg-background',
            'focus:outline-none focus:ring-2 focus:ring-ring',
            state.isMobile ? 'px-2 py-1.5 text-base' : 'px-3 py-2 text-sm',
          )}
        />
      )}
    </div>
  );
};

interface AdvancedSettingsSectionProps {
  state: EditModePanelState;
  settings?: EditAdvancedSettingsType;
  onSettingsChange?: (updates: Partial<EditAdvancedSettingsType>) => void;
  isLocalGeneration?: boolean;
}

export const AdvancedSettingsSection: React.FC<AdvancedSettingsSectionProps> = ({
  state,
  settings,
  onSettingsChange,
  isLocalGeneration = false,
}) => {
  if (!settings || !onSettingsChange || state.isMobile || state.qwenEditModel?.startsWith('flux-klein-')) {
    return null;
  }

  return (
    <EditAdvancedSettings
      settings={settings}
      onSettingsChange={onSettingsChange}
      isLocalGeneration={isLocalGeneration}
    />
  );
};

interface GenerationOptionsSectionProps {
  state: EditModePanelState;
}

export const GenerationOptionsSection: React.FC<GenerationOptionsSectionProps> = ({ state }) => {
  if (!state.setCreateAsGeneration) {
    return null;
  }

  return (
    <div className={cn(
      'flex w-[80%] items-center gap-2 overflow-hidden rounded-md px-1 py-1.5',
      state.isMobile && 'bg-muted/30',
    )}>
      <SectionLabel isMobile={state.isMobile}>Options</SectionLabel>
      <div className={cn('flex min-w-0 items-center gap-2', state.isMobile ? 'flex-1' : 'flex-shrink')}>
        <label className={cn(
          'flex-shrink-0 whitespace-nowrap font-medium',
          state.isMobile ? 'text-[10px] text-muted-foreground' : 'text-sm',
        )}>
          {state.isMobile ? '#' : 'Generations:'}
        </label>
        <div className="flex min-w-0 flex-1 items-center gap-1.5">
          <input
            type="range"
            min={1}
            max={16}
            value={state.inpaintNumGenerations}
            onChange={(e) => state.setInpaintNumGenerations(parseInt(e.target.value))}
            className={cn(
              'h-2 w-full min-w-[60px] cursor-pointer appearance-none rounded-lg bg-muted accent-primary',
              state.isMobile ? 'h-1.5 flex-1' : 'max-w-[120px]',
            )}
          />
          <span className={cn(
            'w-5 flex-shrink-0 text-center font-medium text-foreground',
            state.isMobile ? 'w-4 text-xs' : 'text-sm',
          )}>
            {state.inpaintNumGenerations}
          </span>
        </div>
      </div>

      <div className="flex flex-shrink-0 items-center gap-1.5">
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex cursor-help items-center gap-1">
              <Layers className={cn(state.isMobile ? 'h-3 w-3' : 'h-4 w-4', 'text-muted-foreground')} />
              <Label
                htmlFor="create-as-variant"
                className={cn(
                  'cursor-pointer whitespace-nowrap font-medium',
                  state.isMobile ? 'text-[10px] text-muted-foreground' : 'text-sm',
                )}
              >
                Variant
              </Label>
            </div>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-[250px]">
            <p className="text-xs">
              <strong>On:</strong> Result appears as a variant of this image.
              <br />
              <strong>Off:</strong> Result appears as its own image in the gallery.
            </p>
          </TooltipContent>
        </Tooltip>
        <Switch
          id="create-as-variant"
          checked={!state.createAsGeneration}
          onCheckedChange={(checked) => state.setCreateAsGeneration(!checked)}
          className={cn(state.isMobile && 'scale-90')}
        />
      </div>
    </div>
  );
};

interface StandardEditPanelContentProps extends SharedEditPanelProps {
  mode: 'text' | 'inpaint' | 'annotate';
  handleUnifiedGenerate: () => void;
  handleGenerateAnnotatedEdit: () => void;
}

export const StandardEditPanelContent: React.FC<StandardEditPanelContentProps> = ({
  state,
  mode,
  isCloudMode,
  editLoraManager,
  availableLoras,
  advancedSettings,
  setAdvancedSettings,
  isLocalGeneration,
  handleUnifiedGenerate,
  handleGenerateAnnotatedEdit,
}) => (
  <>
    <PromptSection state={state} mode={mode} />
    <ModelAndLoraSection
      state={state}
      isCloudMode={isCloudMode}
      editLoraManager={editLoraManager}
      availableLoras={availableLoras}
    />
    <LegacyLoraSection state={state} hasManagedLoras={Boolean(editLoraManager)} />
    <AdvancedSettingsSection
      state={state}
      settings={advancedSettings}
      onSettingsChange={setAdvancedSettings}
      isLocalGeneration={isLocalGeneration}
    />
    <GenerationOptionsSection state={state} />
    <GenerateButton
      isMobile={state.isMobile}
      editMode={mode}
      handleUnifiedGenerate={handleUnifiedGenerate}
      handleGenerateAnnotatedEdit={handleGenerateAnnotatedEdit}
      brushStrokes={state.brushStrokes}
      inpaintPrompt={state.inpaintPrompt}
      isGeneratingInpaint={state.isGeneratingInpaint}
      inpaintGenerateSuccess={state.inpaintGenerateSuccess}
      isCreatingMagicEditTasks={state.isCreatingMagicEditTasks}
      magicEditTasksCreated={state.magicEditTasksCreated}
    />
  </>
);
