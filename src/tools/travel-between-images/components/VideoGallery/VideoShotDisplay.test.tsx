import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Shot } from '@/domains/generation/types';
import { VideoShotDisplay } from './VideoShotDisplay';

const mocks = vi.hoisted(() => ({
  shotControlsProps: null as null | Record<string, unknown>,
  updateShotName: vi.fn(),
  deleteShot: vi.fn(),
  duplicateShot: vi.fn(),
  duplicateShotWithVideos: vi.fn(),
  toastError: vi.fn(),
  normalizeAndPresentError: vi.fn(),
  triggerRipple: vi.fn(),
}));

vi.mock('@/shared/hooks/shots', () => ({
  useUpdateShotName: () => ({ mutateAsync: mocks.updateShotName, isPending: false }),
  useDeleteShot: () => ({ mutateAsync: mocks.deleteShot, isPending: false }),
  useDuplicateShot: () => ({ mutateAsync: mocks.duplicateShot, isPending: false }),
  useDuplicateShotWithVideos: () => ({ mutateAsync: mocks.duplicateShotWithVideos, isPending: false }),
}));

vi.mock('@/shared/components/ui/runtime/sonner', () => ({
  toast: {
    error: (...args: unknown[]) => mocks.toastError(...args),
  },
}));

vi.mock('@/shared/lib/errorHandling/runtimeError', () => ({
  normalizeAndPresentError: (...args: unknown[]) => mocks.normalizeAndPresentError(...args),
}));

vi.mock('@/shared/hooks/interaction/useClickRipple', () => ({
  useClickRipple: () => ({
    triggerRipple: mocks.triggerRipple,
    rippleStyles: undefined,
    isRippleActive: false,
  }),
}));

vi.mock('@/shared/state/panesStore', () => ({
  usePanesStore: (selector: (state: { isGenerationsPaneLocked: boolean }) => unknown) => selector({
    isGenerationsPaneLocked: false,
  }),
}));

vi.mock('@/shared/hooks/mobile', () => ({
  useIsMobile: () => false,
}));

vi.mock('@/shared/state/selectionStore', () => ({
  useShotAdditionSelectionOptional: () => null,
}));

vi.mock('../hooks/useVideoShotDisplayState', () => ({
  useVideoShotDisplayState: () => ({
    isEditingName: false,
    editableName: 'Shot Alpha',
    isDeleteDialogOpen: false,
    isVideoModalOpen: false,
    showVideo: false,
    isFinalVideoLightboxOpen: false,
    skipConfirmationChecked: false,
    isSelectedForAddition: false,
    startNameEdit: vi.fn(),
    cancelNameEdit: vi.fn(),
    setEditableName: vi.fn(),
    finishNameEdit: vi.fn(),
    setDeleteDialogOpen: vi.fn(),
    setSkipConfirmationChecked: vi.fn(),
    setVideoModalOpen: vi.fn(),
    setShowVideo: vi.fn(),
    setFinalVideoLightboxOpen: vi.fn(),
    setSelectedForAddition: vi.fn(),
  }),
}));

vi.mock('./VideoShotDisplayParts', () => ({
  ShotMetadata: ({ displayName }: { displayName: string }) => (
    <div data-testid="shot-metadata">{displayName}</div>
  ),
  ShotControls: (props: Record<string, unknown>) => {
    mocks.shotControlsProps = props;
    return <div data-testid="shot-controls">{String(props.isHidden)}</div>;
  },
  ShotPreview: () => <div data-testid="shot-preview">preview</div>,
}));

vi.mock('../VideoGenerationModal', () => ({
  VideoGenerationModal: () => null,
}));

vi.mock('@/shared/components/modals/ImageGenerationModal', () => ({
  ImageGenerationModal: () => null,
}));

vi.mock('@/domains/media-lightbox/MediaLightbox', () => ({
  MediaLightbox: () => null,
}));

vi.mock('@/shared/components/ui/alert-dialog', () => ({
  AlertDialog: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  AlertDialogAction: ({ children }: { children: React.ReactNode }) => <button type="button">{children}</button>,
  AlertDialogCancel: ({ children }: { children: React.ReactNode }) => <button type="button">{children}</button>,
  AlertDialogContent: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  AlertDialogDescription: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogTitle: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/shared/components/ui/checkbox', () => ({
  Checkbox: () => null,
}));

describe('VideoShotDisplay', () => {
  beforeEach(() => {
    mocks.shotControlsProps = null;
    mocks.duplicateShot.mockReset();
    mocks.duplicateShotWithVideos.mockReset();
  });

  it('renders hidden styling and forwards hidden controls into ShotControls', () => {
    const shot = { id: 'shot-1', name: 'Shot Alpha', images: [], settings: {} } as Shot;
    const onToggleHidden = vi.fn();
    const { container } = render(
      <VideoShotDisplay
        shot={shot}
        onSelectShot={vi.fn()}
        currentProjectId="project-1"
        isHidden={true}
        onToggleHidden={onToggleHidden}
      />,
    );

    expect(container.firstElementChild).toHaveClass('opacity-50');
    expect(screen.getByText('Hidden')).toBeInTheDocument();
    expect(screen.getByTestId('shot-controls')).toHaveTextContent('true');
    expect(mocks.shotControlsProps).toEqual(
      expect.objectContaining({
        isHidden: true,
        onToggleHidden,
      }),
    );
  });

  it('keeps normal duplicate on the image-only mutation path', async () => {
    const callOrder: string[] = [];
    const onDuplicateShot = vi.fn(() => callOrder.push('callback'));
    mocks.duplicateShot.mockImplementation(async () => {
      callOrder.push('normal');
      return {};
    });

    const shot = { id: 'shot-1', name: 'Shot Alpha', images: [], settings: {} } as Shot;
    render(
      <VideoShotDisplay
        shot={shot}
        onSelectShot={vi.fn()}
        onDuplicateShot={onDuplicateShot}
        currentProjectId="project-1"
      />,
    );

    const controlsProps = mocks.shotControlsProps as {
      onDuplicate: (event?: React.MouseEvent) => Promise<void>;
    };

    await controlsProps.onDuplicate();

    expect(mocks.duplicateShot).toHaveBeenCalledWith({
      shotId: 'shot-1',
      projectId: 'project-1',
    });
    expect(mocks.duplicateShotWithVideos).not.toHaveBeenCalled();
    expect(callOrder).toEqual(['callback', 'normal']);
  });

  it('calls onDuplicateShot before Duplicate with videos and uses the new mutation args', async () => {
    const callOrder: string[] = [];
    const onDuplicateShot = vi.fn(() => callOrder.push('callback'));
    mocks.duplicateShotWithVideos.mockImplementation(async () => {
      callOrder.push('with-videos');
      return {};
    });

    const shot = { id: 'shot-1', name: 'Shot Alpha', images: [], settings: {} } as Shot;
    render(
      <VideoShotDisplay
        shot={shot}
        onSelectShot={vi.fn()}
        onDuplicateShot={onDuplicateShot}
        currentProjectId="project-1"
      />,
    );

    const controlsProps = mocks.shotControlsProps as {
      onDuplicateWithVideos: (event?: React.MouseEvent) => Promise<void>;
    };

    await controlsProps.onDuplicateWithVideos();

    expect(onDuplicateShot).toHaveBeenCalledTimes(1);
    expect(mocks.duplicateShot).not.toHaveBeenCalled();
    expect(mocks.duplicateShotWithVideos).toHaveBeenCalledWith({
      shotId: 'shot-1',
      projectId: 'project-1',
    });
    expect(callOrder).toEqual(['callback', 'with-videos']);
  });
});
