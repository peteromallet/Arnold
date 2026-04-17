import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ShotSettingsEditor } from './index';

vi.mock('@/shared/hooks/shots', () => ({
  useUpdateShotImageOrder: () => ({ mutateAsync: vi.fn() }),
  useAddImageToShot: () => ({ mutateAsync: vi.fn(), mutateAsyncWithoutPosition: vi.fn() }),
  useRemoveImageFromShot: () => ({ mutateAsync: vi.fn() }),
}));

vi.mock('@/shared/hooks/shotCreation/useShotCreation', () => ({
  useShotCreation: () => ({ createShot: vi.fn() }),
}));

vi.mock('@/shared/hooks/mobile', () => ({
  useIsMobile: () => false,
  useDeviceInfo: () => ({ isPhone: false, mobileColumns: 3 }),
}));

vi.mock('@/shared/hooks/timeline/useTimelineCore', () => ({
  useTimelineCore: () => ({
    clearAllEnhancedPrompts: vi.fn(async () => {}),
    updatePairPromptsByIndex: vi.fn(async () => {}),
    refetch: vi.fn(async () => {}),
  }),
}));

vi.mock('@/shared/hooks/settings/useToolSettings', () => ({
  useToolSettings: () => ({
    settings: {},
    update: vi.fn(),
    isLoading: false,
  }),
}));

vi.mock('@/shared/state/selectionStore', () => ({
  useCurrentShot: () => ({ setCurrentShotId: vi.fn() }),
}));

vi.mock('@/shared/hooks/shots/useShotNavigation', () => ({
  useShotNavigation: () => ({ navigateToShot: vi.fn() }),
}));

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn(), setQueryData: vi.fn() }),
  useQuery: () => ({ data: null }),
}));

vi.mock('@/integrations/supabase/client', () => ({
  getSupabaseClient: () => ({
    from: () => ({
      select: () => ({ eq: () => ({ then: undefined }) }),
    }),
  }),
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProject: () => ({
    selectedProjectId: 'project-1',
    projects: [{ id: 'project-1', aspectRatio: '16:9' }],
  }),
  useProjectSelectionContext: () => ({
    selectedProjectId: 'project-1',
    project: { id: 'project-1', aspectRatio: '16:9' },
    setSelectedProjectId: vi.fn(),
  }),
  useProjectCrudContext: () => ({
    projects: [{ id: 'project-1', aspectRatio: '16:9' }],
    isLoadingProjects: false,
    fetchProjects: vi.fn(),
    addNewProject: vi.fn(),
    isCreatingProject: false,
    updateProject: vi.fn(),
    isUpdatingProject: false,
    deleteProject: vi.fn(),
    isDeletingProject: false,
  }),
  useProjectIdentityContext: () => ({ userId: null }),
}));

vi.mock('@/shared/contexts/IncomingTasksContext', () => ({
  useIncomingTasks: () => ({
    addIncomingTask: vi.fn().mockReturnValue('incoming-1'),
    removeIncomingTask: vi.fn(),
    resolveTaskIds: vi.fn(),
    cancelIncoming: vi.fn(),
    cancelAllIncoming: vi.fn(),
    wasCancelled: vi.fn(() => false),
    acknowledgeCancellation: vi.fn(),
    hasIncomingTasks: false,
    incomingTasks: [],
  }),
}));

vi.mock('@/shared/contexts/ShotsContext', () => ({
  useShots: () => ({
    shots: [{ id: 'shot-1', name: 'Shot 1', position: 0, images: [] }],
    isLoading: false,
    refetch: vi.fn(),
  }),
  useShotImages: () => ({
    images: [],
    isLoading: false,
  }),
}));

vi.mock('@/shared/hooks/segments', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/hooks/segments')>();
  return {
    ...actual,
    useSegmentOutputsForShot: () => ({
      segmentSlots: [],
      segments: [],
      selectedParent: null,
      parentGenerations: [],
      segmentProgress: {},
      isLoading: false,
    }),
  };
});

vi.mock('../../hooks/useDemoteOrphanedVariants', () => ({
  useDemoteOrphanedVariants: () => ({ demoteOrphanedVariants: vi.fn() }),
}));

vi.mock('./ShotSettingsContext', () => ({
  ShotSettingsProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('./sections/HeaderSection', () => ({
  HeaderSection: () => <div data-testid="header-section">header</div>,
}));
vi.mock('./sections/TimelineSection', () => ({
  TimelineSection: () => <div data-testid="timeline-section">timeline</div>,
}));
vi.mock('./sections/ModalsSection', () => ({
  ModalsSection: () => <div data-testid="modals-section">modals</div>,
}));
vi.mock('./sections/GenerationSection', () => ({
  GenerationSection: () => <div data-testid="generation-section">generation</div>,
}));

vi.mock('../FinalVideoSection', () => ({
  FinalVideoSection: () => <div data-testid="final-video-section">final-video</div>,
}));

vi.mock('@/tools/travel-between-images/providers', () => ({
  usePromptSettings: () => ({
    prompt: '',
    setPrompt: vi.fn(),
    negativePrompt: '',
    setNegativePrompt: vi.fn(),
    enhancePrompt: false,
    setEnhancePrompt: vi.fn(),
    textBeforePrompts: '',
    setTextBeforePrompts: vi.fn(),
    textAfterPrompts: '',
    setTextAfterPrompts: vi.fn(),
  }),
  useMotionSettings: () => ({
    motionMode: 'basic',
    setMotionMode: vi.fn(),
    amountOfMotion: 50,
    setAmountOfMotion: vi.fn(),
    turboMode: false,
    setTurboMode: vi.fn(),
    smoothContinuations: false,
  }),
  useFrameSettings: () => ({
    batchVideoFrames: 61,
    setFrames: vi.fn(),
    batchVideoSteps: 6,
    setSteps: vi.fn(),
  }),
  usePhaseConfigSettings: () => ({
    generationTypeMode: 'i2v',
    setGenerationTypeMode: vi.fn(),
    phaseConfig: undefined,
    setPhaseConfig: vi.fn(),
    selectedPhasePresetId: null,
    selectPreset: vi.fn(),
    removePreset: vi.fn(),
    advancedMode: false,
  }),
  useGenerationModeSettings: () => ({
    generationMode: 'timeline',
    setGenerationMode: vi.fn(),
  }),
  useSteerableMotionSettings: () => ({
    steerableMotionSettings: { model_name: 'wan', negative_prompt: '', seed: 1, debug: false, show_input_images: false },
    setSteerableMotionSettings: vi.fn(),
  }),
  useLoraSettings: () => ({
    selectedLoras: [],
    setSelectedLoras: vi.fn(),
    availableLoras: [],
  }),
  useVideoTravelSettings: () => ({ isLoading: false }),
}));

vi.mock('./useShotEditorController', () => ({
  useShotEditorController: () => ({
    hasSelectedShot: true,
    layoutProps: {},
  }),
}));

vi.mock('./ShotEditorLayout', () => ({
  ShotEditorLayout: () => (
    <div>
      <div data-testid="header-section">header</div>
      <div data-testid="final-video-section">final-video</div>
      <div data-testid="timeline-section">timeline</div>
      <div data-testid="generation-section">generation</div>
      <div data-testid="modals-section">modals</div>
    </div>
  ),
}));

vi.mock('./state/useShotEditorState', () => ({
  useShotEditorState: () => ({
    state: {
      isEditingName: false,
      editingName: '',
      pendingFramePositions: new Map(),
      isModeReady: true,
      settingsError: null,
      isSettingsModalOpen: false,
      isUploadingImage: false,
      uploadProgress: 0,
      duplicatingImageId: null,
      duplicateSuccessImageId: null,
      showStepsNotification: false,
    },
    actions: {
      setSettingsModalOpen: vi.fn(),
      setShowStepsNotification: vi.fn(),
    },
  }),
}));

describe('ShotSettingsEditor', () => {
  it('renders the modular sections with a direct component test harness', () => {
    render(
      <ShotSettingsEditor
        selectedShotId="shot-1"
        projectId="project-1"
        onShotImagesUpdate={() => {}}
        onBack={() => {}}
      />,
    );

    expect(screen.getByTestId('header-section')).toBeInTheDocument();
    expect(screen.getByTestId('final-video-section')).toBeInTheDocument();
    expect(screen.getByTestId('timeline-section')).toBeInTheDocument();
    expect(screen.getByTestId('generation-section')).toBeInTheDocument();
    expect(screen.getByTestId('modals-section')).toBeInTheDocument();
  });

  it('renders section content text', () => {
    render(
      <ShotSettingsEditor
        selectedShotId="shot-1"
        projectId="project-1"
        onShotImagesUpdate={() => {}}
        onBack={() => {}}
      />,
    );

    expect(screen.getByText('header')).toBeInTheDocument();
    expect(screen.getByText('final-video')).toBeInTheDocument();
    expect(screen.getByText('timeline')).toBeInTheDocument();
    expect(screen.getByText('generation')).toBeInTheDocument();
    expect(screen.getByText('modals')).toBeInTheDocument();
  });

  it('accepts required props', () => {
    expect(ShotSettingsEditor).toBeDefined();
    // React.memo wraps the component — typeof is 'object', not 'function'
    expect(typeof ShotSettingsEditor).toBe('object');
    expect(ShotSettingsEditor).toHaveProperty('$$typeof');
  });

  it('renders all sections as children of the layout', () => {
    const { container } = render(
      <ShotSettingsEditor
        selectedShotId="shot-1"
        projectId="project-1"
        onShotImagesUpdate={() => {}}
        onBack={() => {}}
      />,
    );

    const headerSection = screen.getByTestId('header-section');
    const finalVideoSection = screen.getByTestId('final-video-section');
    const timelineSection = screen.getByTestId('timeline-section');
    const generationSection = screen.getByTestId('generation-section');
    const modalsSection = screen.getByTestId('modals-section');

    expect(headerSection.textContent).toBe('header');
    expect(finalVideoSection.textContent).toBe('final-video');
    expect(timelineSection.textContent).toBe('timeline');
    expect(generationSection.textContent).toBe('generation');
    expect(modalsSection.textContent).toBe('modals');
    expect(container.querySelector('[data-testid]')).not.toBeNull();
  });
});
