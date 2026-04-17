import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import {
  VideoGenerationModalFormContent,
  VideoGenerationModalHeader,
  VideoGenerationModalLoadingContent,
} from './VideoGenerationModalSections';

const mocks = vi.hoisted(() => ({
  useVideoTravelSettingsHandlers: vi.fn(),
  handleGenerationTypeModeChange: vi.fn(),
  handlePhaseConfigChange: vi.fn(),
  handlePhasePresetRemove: vi.fn(),
  handlePhasePresetSelect: vi.fn(),
  batchSettingsForm: vi.fn(
    ({
      onBatchVideoPromptChange,
      onPhaseConfigChange,
      onPhasePresetSelect,
      onPhasePresetRemove,
    }: {
      onBatchVideoPromptChange: (value: string) => void;
      onPhaseConfigChange: (value: unknown) => void;
      onPhasePresetSelect: (id: string, config: unknown) => void;
      onPhasePresetRemove: () => void;
    }) => (
      <>
        <button data-testid="batch-settings-form" onClick={() => onBatchVideoPromptChange('updated prompt')}>
          batch
        </button>
        <button data-testid="batch-phase-config" onClick={() => onPhaseConfigChange({ num_phases: 2 })}>
          batch config
        </button>
        <button data-testid="batch-preset-select" onClick={() => onPhasePresetSelect('preset-a', { num_phases: 2 })}>
          batch preset
        </button>
        <button data-testid="batch-preset-remove" onClick={onPhasePresetRemove}>
          batch remove
        </button>
      </>
    ),
  ),
  motionControl: vi.fn(
    ({
      mode,
      presets,
      advanced,
    }: {
      mode: {
        onMotionModeChange: (mode: 'basic' | 'advanced') => void;
        onGenerationTypeModeChange: (mode: 'i2v' | 'vace') => void;
        guidanceKind?: string;
      };
      presets: {
        onPhasePresetSelect: (id: string, config: unknown) => void;
        onPhasePresetRemove: () => void;
      };
      advanced: {
        onPhaseConfigChange: (value: unknown) => void;
      };
    }) => (
      <>
        <button data-testid="motion-control" onClick={() => mode.onMotionModeChange('advanced')}>
          motion
        </button>
        <button data-testid="motion-generation-type" onClick={() => mode.onGenerationTypeModeChange('vace')}>
          motion type
        </button>
        <button data-testid="motion-preset-select" onClick={() => presets.onPhasePresetSelect('preset-b', { num_phases: 3 })}>
          motion preset
        </button>
        <button data-testid="motion-preset-remove" onClick={presets.onPhasePresetRemove}>
          motion remove
        </button>
        <button data-testid="motion-phase-config" onClick={() => advanced.onPhaseConfigChange({ num_phases: 3 })}>
          motion config
        </button>
      </>
    ),
  ),
}));

vi.mock('@/shared/lib/media/mediaUrl', () => ({
  getDisplayUrl: (src: string | null | undefined) => `display:${src ?? ''}`,
}));

vi.mock('@/shared/components/ui/tooltip', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button {...props}>{children}</button>
  ),
}));

vi.mock('@/shared/components/ui/skeleton', () => ({
  Skeleton: ({ className }: { className?: string }) => <div data-testid="skeleton" className={className} />,
}));

vi.mock('@/tools/travel-between-images/providers', () => ({
  useVideoTravelSettingsHandlers: (...args: unknown[]) => mocks.useVideoTravelSettingsHandlers(...args),
}));

vi.mock('@/tools/travel-between-images/components/BatchSettingsForm', () => ({
  BatchSettingsForm: (props: unknown) => mocks.batchSettingsForm(props),
}));

vi.mock('@/tools/travel-between-images/components/MotionControl', () => ({
  MotionControl: (props: unknown) => mocks.motionControl(props),
}));

vi.mock('@/shared/components/ImageGenerationForm/components', () => ({
  SectionHeader: ({ title }: { title: string }) => <h2>{title}</h2>,
}));

describe('VideoGenerationModalSections', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useVideoTravelSettingsHandlers.mockReturnValue({
      handleGenerationTypeModeChange: mocks.handleGenerationTypeModeChange,
      handlePhaseConfigChange: mocks.handlePhaseConfigChange,
      handlePhasePresetRemove: mocks.handlePhasePresetRemove,
      handlePhasePresetSelect: mocks.handlePhasePresetSelect,
    });
  });

  it('renders header with shot name and navigate action', () => {
    const onNavigateToShot = vi.fn();
    render(
      <VideoGenerationModalHeader
        shotName="Shot A"
        onNavigateToShot={onNavigateToShot}
      />,
    );

    expect(screen.getByText(/Generate Video -/)).toHaveTextContent('Shot A');

    fireEvent.click(screen.getByRole('button'));
    expect(onNavigateToShot).toHaveBeenCalledTimes(1);
  });

  it('shows unnamed fallback when no shot name', () => {
    render(
      <VideoGenerationModalHeader
        shotName={undefined}
        onNavigateToShot={vi.fn()}
      />,
    );

    expect(screen.getByText(/Unnamed Shot/)).toBeInTheDocument();
  });

  it('renders loading skeleton layout', () => {
    render(<VideoGenerationModalLoadingContent />);
    expect(screen.getAllByTestId('skeleton').length).toBeGreaterThan(5);
  });

  it('wires form callbacks from settings and motion controls', () => {
    const updateField = vi.fn();
    render(
      <VideoGenerationModalFormContent
        settings={{
          prompt: 'start',
          motionMode: 'basic',
          phaseConfig: undefined,
        } as never}
        updateField={updateField as never}
        projects={[]}
        selectedProjectId={null}
        selectedLoras={[]}
        availableLoras={[]}
        accelerated={false}
        onAcceleratedChange={vi.fn()}
        randomSeed={false}
        onRandomSeedChange={vi.fn()}
        imageCount={2}
        hasStructureVideo={false}
        guidanceKind="flow"
        validPresetId={undefined}
        status="ready"
        onOpenLoraModal={vi.fn()}
        onRemoveLora={vi.fn()}
        onLoraStrengthChange={vi.fn()}
        onAddTriggerWord={vi.fn()}
      />,
    );

    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByText('Motion')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('batch-settings-form'));
    fireEvent.click(screen.getByTestId('motion-control'));
    fireEvent.click(screen.getByTestId('batch-phase-config'));
    fireEvent.click(screen.getByTestId('batch-preset-select'));
    fireEvent.click(screen.getByTestId('batch-preset-remove'));
    fireEvent.click(screen.getByTestId('motion-generation-type'));
    fireEvent.click(screen.getByTestId('motion-preset-select'));
    fireEvent.click(screen.getByTestId('motion-preset-remove'));
    fireEvent.click(screen.getByTestId('motion-phase-config'));

    expect(updateField).toHaveBeenCalledWith('prompt', 'updated prompt');
    expect(updateField).toHaveBeenCalledWith('motionMode', 'advanced');
    expect(updateField).toHaveBeenCalledWith('advancedMode', true);
    expect(mocks.handlePhaseConfigChange).toHaveBeenCalledTimes(2);
    expect(mocks.handlePhaseConfigChange).toHaveBeenCalledWith({ num_phases: 2 });
    expect(mocks.handlePhaseConfigChange).toHaveBeenCalledWith({ num_phases: 3 });
    expect(mocks.handlePhasePresetSelect).toHaveBeenCalledTimes(2);
    expect(mocks.handlePhasePresetSelect).toHaveBeenCalledWith('preset-a', { num_phases: 2 });
    expect(mocks.handlePhasePresetSelect).toHaveBeenCalledWith('preset-b', { num_phases: 3 });
    expect(mocks.handlePhasePresetRemove).toHaveBeenCalledTimes(2);
    expect(mocks.handleGenerationTypeModeChange).toHaveBeenCalledWith('vace');
    expect(mocks.motionControl).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: expect.objectContaining({
          guidanceKind: 'flow',
        }),
      }),
    );
  });
});
