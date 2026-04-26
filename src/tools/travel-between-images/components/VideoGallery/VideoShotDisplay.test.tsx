import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Shot } from '@/domains/generation/types';
import { VideoShotDisplay } from './VideoShotDisplay';

const mocks = vi.hoisted(() => ({
  shotControlsProps: null as null | Record<string, unknown>,
  updateShotName: vi.fn(),
  deleteShot: vi.fn(),
  duplicateShot: vi.fn(),
  toastError: vi.fn(),
  normalizeAndPresentError: vi.fn(),
  triggerRipple: vi.fn(),
}));

vi.mock('@/shared/hooks/shots', () => ({
  useUpdateShotName: () => ({ mutateAsync: mocks.updateShotName, isPending: false }),
  useDeleteShot: () => ({ mutateAsync: mocks.deleteShot, isPending: false }),
  useDuplicateShot: () => ({ mutateAsync: mocks.duplicateShot, isPending: false }),
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
});
