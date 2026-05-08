// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Shot } from '@/domains/generation/types';
import { ShotsPanelContent } from './ShotsPanelContent';

const mocks = vi.hoisted(() => ({
  duplicateShot: vi.fn(),
  duplicateShotWithVideos: vi.fn(),
  withVideosPending: false,
  refetchShots: vi.fn(),
  normalizeAndPresentError: vi.fn(),
}));

vi.mock('@/shared/contexts/ShotsContext', () => ({
  useShots: () => ({
    shots: [
      {
        id: 'shot-1',
        name: 'Shot Alpha',
        images: [],
        settings: {},
        position: 1,
      } as Shot,
    ],
    isLoading: false,
    refetchShots: mocks.refetchShots,
  }),
}));

vi.mock('@/shared/contexts/ProjectContext', () => ({
  useProjectSelectionContext: () => ({ selectedProjectId: 'project-1' }),
}));

vi.mock('@/tools/travel-between-images/hooks/video/useShotFinalVideos', () => ({
  useShotFinalVideos: () => ({ finalVideoMap: new Map() }),
}));

vi.mock('@/shared/hooks/shots/useShotGenerationMutations', () => ({
  useAddImageToShot: () => ({ mutateAsync: vi.fn() }),
}));

vi.mock('@/shared/hooks/shots/useShotsCrud', () => ({
  useDuplicateShot: () => ({ mutateAsync: mocks.duplicateShot, isPending: false }),
  useDeleteShot: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock('@/shared/hooks/shots/useDuplicateShotWithVideos', () => ({
  useDuplicateShotWithVideos: () => ({
    mutateAsync: mocks.duplicateShotWithVideos,
    isPending: mocks.withVideosPending,
  }),
}));

vi.mock('@/shared/hooks/shots/useShotUpdates', () => ({
  useUpdateShotName: () => ({ mutateAsync: vi.fn() }),
}));

vi.mock('@/shared/hooks/shotCreation/useShotCreation', () => ({
  useShotCreation: () => ({ createShot: vi.fn() }),
}));

vi.mock('@/tools/travel-between-images/hooks/useHiddenShots', () => ({
  useHiddenShots: () => ({ hiddenIds: new Set<string>(), toggle: vi.fn() }),
}));

vi.mock('@/shared/lib/dnd/dragDrop', () => ({
  setShotDragData: vi.fn(),
  createDragPreview: vi.fn(),
  getGenerationDropData: vi.fn(),
  getMultiGenerationDropData: vi.fn(),
  isValidDropTarget: vi.fn(() => false),
}));

vi.mock('@/tools/travel-between-images/components/VideoGenerationModal', () => ({
  VideoGenerationModal: () => null,
}));

vi.mock('@/shared/lib/errorHandling/runtimeError', () => ({
  normalizeAndPresentError: (...args: unknown[]) => mocks.normalizeAndPresentError(...args),
}));

vi.mock('@/shared/dev/useRenderBudget', () => ({
  useRenderBudget: vi.fn(),
}));

describe('ShotsPanelContent Duplicate with videos', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.withVideosPending = false;
  });

  it('keeps normal duplicate image-only and exposes a separate Duplicate with videos affordance', () => {
    const parentClick = vi.fn();
    render(
      <div onClick={parentClick}>
        <ShotsPanelContent projectId="project-1" />
      </div>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Duplicate shot' }));
    fireEvent.click(screen.getByRole('button', { name: 'Duplicate with videos' }));

    expect(mocks.duplicateShot).toHaveBeenCalledWith({
      shotId: 'shot-1',
      projectId: 'project-1',
    });
    expect(mocks.duplicateShotWithVideos).toHaveBeenCalledWith({
      shotId: 'shot-1',
      projectId: 'project-1',
    });
    expect(screen.getByTitle('Duplicate with videos')).toBeInTheDocument();
    expect(parentClick).not.toHaveBeenCalled();
  });

  it('shows a distinct disabled pending state for Duplicate with videos', () => {
    mocks.withVideosPending = true;

    render(<ShotsPanelContent projectId="project-1" />);

    expect(screen.getByRole('button', { name: 'Duplicate with videos' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Duplicate shot' })).not.toBeDisabled();
  });
});
