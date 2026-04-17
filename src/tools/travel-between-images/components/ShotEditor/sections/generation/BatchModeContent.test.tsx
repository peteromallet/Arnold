import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BatchModeContent } from './BatchModeContent';

const batchSettingsFormSpy = vi.fn();
const motionControlSpy = vi.fn();
const generateVideoCtaSpy = vi.fn();
const joinClipsSettingsFormSpy = vi.fn();

const handleGenerateBatchMock = vi.fn();
const toggleGenerateModePreserveScrollMock = vi.fn();
const joinUpdateFieldMock = vi.fn();
const handleStructureVideoMotionStrengthChangeMock = vi.fn();
const handleUni3cEndPercentChangeMock = vi.fn();
const handleStructureTypeChangeFromMotionControlMock = vi.fn();

let simpleFilteredImagesMock: Array<{ id: string }> = [];
let structureVideoPathMock: string | null = null;
let structureVideoTypeMock: string = 'flow';
let structureVideoMotionStrengthMock = 1;
let structureVideoUni3cEndPercentMock = 0.5;
let stitchAfterGenerateMock = false;
let selectedModelMock: 'wan-2.2' | 'ltx-2.3' | 'ltx-2.3-fast' = 'wan-2.2';
const setSelectedModelMock = vi.fn();

vi.mock('@/shared/components/ui/collapsible', () => ({
  Collapsible: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CollapsibleTrigger: ({ children, ...props }: React.ComponentProps<'button'>) => (
    <button type="button" {...props}>
      {children}
    </button>
  ),
  CollapsibleContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/shared/components/ui/primitives/label', () => ({
  Label: ({ children, ...props }: React.ComponentProps<'label'>) => <label {...props}>{children}</label>,
}));

vi.mock('@/shared/components/ui/switch', () => ({
  Switch: ({ id, checked, onCheckedChange }: { id?: string; checked?: boolean; onCheckedChange?: (checked: boolean) => void }) => (
    <button data-testid={id || 'switch'} type="button" aria-pressed={checked} onClick={() => onCheckedChange?.(!checked)}>
      switch
    </button>
  ),
}));

vi.mock('@/shared/components/ui/slider', () => ({
  Slider: ({ value, onValueChange }: { value?: number | number[]; onValueChange?: (value: number[]) => void }) => (
    <button
      data-testid="slider"
      type="button"
      onClick={() => {
        const next = Array.isArray(value) ? value : [value ?? 0];
        onValueChange?.(next);
      }}
    >
      slider
    </button>
  ),
}));

vi.mock('@/shared/components/ImageGenerationForm/components', () => ({
  SectionHeader: ({ title }: { title: string }) => <div>{title}</div>,
}));

vi.mock('@/shared/contexts/AIInputModeContext', () => ({
  useAIInputMode: () => ({
    mode: 'text',
    setMode: vi.fn(),
    isLoading: false,
  }),
}));

vi.mock('../../../BatchSettingsForm', () => ({
  BatchSettingsForm: (props: unknown) => {
    batchSettingsFormSpy(props);
    return <div data-testid="batch-settings-form" />;
  },
}));

vi.mock('../../../MotionControl', () => ({
  MotionControl: (props: unknown) => {
    motionControlSpy(props);
    return <div data-testid="motion-control" />;
  },
}));

vi.mock('../../../GenerateVideoCTA', () => ({
  GenerateVideoCTA: (props: { onGenerate: () => void; middleContent?: React.ReactNode; bottomContent?: React.ReactNode }) => {
    generateVideoCtaSpy(props);
    return (
      <div data-testid="generate-video-cta">
        <button type="button" data-testid="generate-video-button" onClick={props.onGenerate}>
          Generate
        </button>
        {props.middleContent}
        {props.bottomContent}
      </div>
    );
  },
}));

vi.mock('@/shared/components/JoinClipsSettingsForm/JoinClipsSettingsForm', () => ({
  JoinClipsSettingsForm: (props: unknown) => {
    joinClipsSettingsFormSpy(props);
    return <div data-testid="join-clips-settings-form" />;
  },
  DEFAULT_JOIN_CLIPS_PHASE_CONFIG: {},
  BUILTIN_JOIN_CLIPS_DEFAULT_ID: 'builtin-default',
}));

vi.mock('../../ShotSettingsContext', () => ({
  useShotSettingsIdentity: () => ({
    projectId: 'project-1',
    selectedProjectId: 'project-1',
    projects: [{ id: 'project-1', name: 'Project 1' }],
  }),
  useShotSettingsMedia: () => ({
    simpleFilteredImages: simpleFilteredImagesMock,
    structureVideo: {
      structureVideoPath: structureVideoPathMock,
      structureVideoMotionStrength: structureVideoMotionStrengthMock,
      structureVideoType: structureVideoTypeMock,
      structureVideoUni3cEndPercent: structureVideoUni3cEndPercentMock,
    },
    structureVideoHandlers: {
      handleStructureVideoMotionStrengthChange: handleStructureVideoMotionStrengthChangeMock,
      handleUni3cEndPercentChange: handleUni3cEndPercentChangeMock,
      handleStructureTypeChangeFromMotionControl: handleStructureTypeChangeFromMotionControlMock,
    },
  }),
  useShotSettingsUi: () => ({
    state: { showStepsNotification: false },
    dimensions: {
      dimensionSource: 'project',
      onDimensionSourceChange: vi.fn(),
      customWidth: 1280,
      onCustomWidthChange: vi.fn(),
      customHeight: 720,
      onCustomHeightChange: vi.fn(),
    },
  }),
  useShotSettingsGeneration: () => ({
    loraManager: {
      selectedLoras: [],
      setIsLoraModalOpen: vi.fn(),
      handleRemoveLora: vi.fn(),
      handleLoraStrengthChange: vi.fn(),
      handleAddTriggerWord: vi.fn(),
      renderHeaderActions: vi.fn(),
    },
    availableLoras: [{ id: 'lora-1' }],
    generationMode: {
      accelerated: false,
      onAcceleratedChange: vi.fn(),
      randomSeed: null,
      onRandomSeedChange: vi.fn(),
      currentMotionSettings: {},
      isSteerableMotionEnqueuing: false,
      steerableMotionJustQueued: false,
      isGenerationDisabled: false,
      toggleGenerateModePreserveScroll: toggleGenerateModePreserveScrollMock,
    },
    generationHandlers: {
      handleBatchVideoPromptChangeWithClear: vi.fn(),
      handleStepsChange: vi.fn(),
      clearAllEnhancedPrompts: vi.fn(),
      handleGenerateBatch: handleGenerateBatchMock,
    },
    joinState: {
      joinSettings: {
        settings: {
          stitchAfterGenerate: stitchAfterGenerateMock,
          prompt: 'join prompt',
          negativePrompt: 'join negative',
          contextFrameCount: 8,
          gapFrameCount: 12,
          replaceMode: false,
          keepBridgingImages: true,
          enhancePrompt: false,
          motionMode: 'basic',
          phaseConfig: null,
          selectedPhasePresetId: null,
          randomSeed: null,
        },
        updateField: joinUpdateFieldMock,
        updateFields: vi.fn(),
      },
      joinValidationData: {
        shortestClipFrames: 24,
      },
      joinLoraManager: {
        selectedLoras: [],
      },
      handleRestoreJoinDefaults: vi.fn(),
    },
  }),
}));

vi.mock('@/tools/travel-between-images/providers', () => ({
  usePromptSettings: () => ({
    prompt: 'batch prompt',
    negativePrompt: 'batch negative',
    setNegativePrompt: vi.fn(),
    enhancePrompt: false,
    setEnhancePrompt: vi.fn(),
    textBeforePrompts: '',
    setTextBeforePrompts: vi.fn(),
    textAfterPrompts: '',
    setTextAfterPrompts: vi.fn(),
  }),
  useMotionSettings: () => ({
    motionMode: 'advanced',
    setMotionMode: vi.fn(),
    turboMode: false,
    setTurboMode: vi.fn(),
    smoothContinuations: false,
    setSmoothContinuations: vi.fn(),
    amountOfMotion: 0.6,
    setAmountOfMotion: vi.fn(),
  }),
  useFrameSettings: () => ({
    batchVideoFrames: 61,
    setFrames: vi.fn(),
    batchVideoSteps: 6,
  }),
  useModelSettings: () => ({
    selectedModel: selectedModelMock,
    guidanceScale: undefined,
    setSelectedModel: setSelectedModelMock,
    setGuidanceScale: vi.fn(),
  }),
  usePhaseConfigSettings: () => ({
    generationTypeMode: 'i2v',
    setGenerationTypeMode: vi.fn(),
    phaseConfig: {},
    setPhaseConfig: vi.fn(),
    selectedPhasePresetId: null,
    selectPreset: vi.fn(),
    removePreset: vi.fn(),
    restoreDefaults: vi.fn(),
  }),
  useGenerationModeSettings: () => ({
    generationMode: 'timeline',
    videoControlMode: 'default',
  }),
  useLoraSettings: () => ({
    availableLoras: [{ id: 'lora-ctx-1' }],
  }),
  useSettingsSave: () => ({
    onBlurSave: vi.fn(),
  }),
  useVideoTravelSettingsStatus: () => ({
    isLoading: false,
  }),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

function renderWithProviders(ui: React.ReactElement) {
  const Wrapper = createWrapper();
  return render(ui, { wrapper: Wrapper });
}

describe('BatchModeContent', () => {
  beforeEach(() => {
    batchSettingsFormSpy.mockClear();
    motionControlSpy.mockClear();
    generateVideoCtaSpy.mockClear();
    joinClipsSettingsFormSpy.mockClear();
    handleGenerateBatchMock.mockClear();
    toggleGenerateModePreserveScrollMock.mockClear();
    joinUpdateFieldMock.mockClear();
    handleStructureVideoMotionStrengthChangeMock.mockClear();
    handleUni3cEndPercentChangeMock.mockClear();
    handleStructureTypeChangeFromMotionControlMock.mockClear();
    setSelectedModelMock.mockClear();

    simpleFilteredImagesMock = [{ id: 'img-1' }, { id: 'img-2' }, { id: 'img-3' }];
    structureVideoPathMock = null;
    structureVideoTypeMock = 'flow';
    structureVideoMotionStrengthMock = 1;
    structureVideoUni3cEndPercentMock = 0.5;
    stitchAfterGenerateMock = false;
    selectedModelMock = 'wan-2.2';
  });

  it('passes derived values to child sections and generate CTA', () => {
    stitchAfterGenerateMock = true;

    renderWithProviders(<BatchModeContent swapButtonRef={{ current: null }} parentVariantName="Variant A" />);

    expect(screen.getByTestId('batch-settings-form')).toBeInTheDocument();
    expect(screen.getByTestId('motion-control')).toBeInTheDocument();
    expect(screen.getByTestId('generate-video-cta')).toBeInTheDocument();

    expect(batchSettingsFormSpy).toHaveBeenCalledWith(expect.objectContaining({ imageCount: 3 }));
    expect(generateVideoCtaSpy).toHaveBeenCalledWith(expect.objectContaining({ videoCount: 2, stitchEnabled: true, variantName: 'Variant A' }));
    expect(joinClipsSettingsFormSpy).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTestId('generate-video-button'));
    expect(handleGenerateBatchMock).toHaveBeenCalledWith('Variant A');
  });

  it('updates stitch setting and supports swap action when enough images exist', () => {
    renderWithProviders(<BatchModeContent swapButtonRef={{ current: null }} />);

    fireEvent.click(screen.getByTestId('stitch-after-generate'));
    expect(joinUpdateFieldMock).toHaveBeenCalledWith('stitchAfterGenerate', true);

    fireEvent.click(screen.getByText('Swap to Join Segments'));
    expect(toggleGenerateModePreserveScrollMock).toHaveBeenCalledWith('join');
  });

  it('renders camera guidance controls for structure video and routes slider changes', () => {
    structureVideoPathMock = '/tmp/structure.mp4';
    structureVideoTypeMock = 'uni3c';
    structureVideoMotionStrengthMock = 1.2;
    structureVideoUni3cEndPercentMock = 0.4;

    renderWithProviders(<BatchModeContent swapButtonRef={{ current: null }} />);

    expect(screen.getByText('Camera Guidance')).toBeInTheDocument();
    const sliders = screen.getAllByTestId('slider');
    expect(sliders).toHaveLength(2);

    fireEvent.click(sliders[0]);
    fireEvent.click(sliders[1]);

    expect(handleStructureVideoMotionStrengthChangeMock).toHaveBeenCalledWith(1.2);
    expect(handleUni3cEndPercentChangeMock).toHaveBeenCalledWith(0.4);
  });

  it('uses main model pills with LTX variant suboptions', () => {
    const { rerender } = renderWithProviders(<BatchModeContent swapButtonRef={{ current: null }} />);

    const initialBatchProps = batchSettingsFormSpy.mock.calls.at(-1)?.[0] as {
      selectedModel: string;
      onSelectedModelChange: (model: string) => void;
    };
    expect(initialBatchProps.selectedModel).toBe('wan-2.2');

    initialBatchProps.onSelectedModelChange('ltx-2.3-fast');
    expect(setSelectedModelMock).toHaveBeenCalledWith('ltx-2.3-fast');

    selectedModelMock = 'ltx-2.3-fast';
    rerender(<BatchModeContent swapButtonRef={{ current: null }} />);

    const ltxBatchProps = batchSettingsFormSpy.mock.calls.at(-1)?.[0] as {
      selectedModel: string;
      onSelectedModelChange: (model: string) => void;
    };
    expect(ltxBatchProps.selectedModel).toBe('ltx-2.3-fast');

    ltxBatchProps.onSelectedModelChange('ltx-2.3');
    expect(setSelectedModelMock).toHaveBeenCalledWith('ltx-2.3');
  });

  it('renders distilled LTX guidance modes and routes guidance mode changes', () => {
    structureVideoPathMock = '/tmp/structure.mp4';
    structureVideoTypeMock = 'video';
    selectedModelMock = 'ltx-2.3-fast';

    renderWithProviders(<BatchModeContent swapButtonRef={{ current: null }} />);

    expect(screen.getByRole('button', { name: 'Video' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pose' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Depth' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Canny' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Camera' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Pose' }));
    expect(handleStructureTypeChangeFromMotionControlMock).toHaveBeenCalledWith('pose');
  });
});
