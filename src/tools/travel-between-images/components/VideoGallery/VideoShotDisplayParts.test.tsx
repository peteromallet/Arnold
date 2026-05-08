// @vitest-environment jsdom
import { fireEvent, render, screen, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import type { GenerationRow } from '@/domains/generation/types';
import {
  ShotControls,
  ShotMetadata,
  ShotPreview,
} from './VideoShotDisplayParts';

vi.mock('@/shared/components/ui/button', () => ({
  Button: ({
    children,
    type,
    ...props
  }: {
    children: ReactNode;
    type?: 'button' | 'submit' | 'reset';
    [key: string]: unknown;
  }) => (
    <button type={type ?? 'button'} {...props}>
      {children}
    </button>
  ),
}));

vi.mock('@/shared/components/ui/input', () => ({
  Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));

vi.mock('@/shared/components/ui/tooltip', () => ({
  TooltipProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  Tooltip: ({ children }: { children: ReactNode }) => <div data-tooltip="true">{children}</div>,
  TooltipTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/shared/components/media/HoverScrubVideo', () => ({
  HoverScrubVideo: ({ src }: { src: string }) => <div data-testid="hover-scrub-video" data-src={src} />,
}));

vi.mock('@/shared/lib/media/mediaUrl', () => ({
  getDisplayUrl: (url: string) => `display:${url}`,
}));

vi.mock('@/shared/components/ui/contracts/cn', () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' '),
}));

function createImage(id: string, url: string): GenerationRow {
  return {
    id,
    imageUrl: url,
    location: url,
    thumbUrl: url,
  } as GenerationRow;
}

function getTooltipButton(label: RegExp | string): HTMLButtonElement {
  const tooltipText = typeof label === 'string'
    ? screen.getByText(label)
    : screen.getByText(label);

  return within(tooltipText.closest('[data-tooltip="true"]') as HTMLElement).getByRole('button');
}

describe('VideoShotDisplayParts', () => {
  it('renders editable shot metadata and forwards save/cancel interactions', () => {
    const onEditableNameChange = vi.fn();
    const onSaveName = vi.fn();
    const onCancelEdit = vi.fn();

    render(
      <ShotMetadata
        displayName="Shot Alpha"
        isEditingName={true}
        editableName="Shot Alpha"
        onEditableNameChange={onEditableNameChange}
        onSaveName={onSaveName}
        onCancelEdit={onCancelEdit}
      />,
    );

    const input = screen.getByDisplayValue('Shot Alpha');
    fireEvent.change(input, { target: { value: 'Shot Beta' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    fireEvent.keyDown(input, { key: 'Escape' });

    expect(onEditableNameChange).toHaveBeenCalledWith('Shot Beta');
    expect(onSaveName).toHaveBeenCalledTimes(1);
    expect(onCancelEdit).toHaveBeenCalledTimes(1);
  });

  it('forwards control-button callbacks when the shot is actionable and disables them while saving', () => {
    const callbacks = {
      onVideoClick: vi.fn(),
      onEditName: vi.fn(),
      onDuplicate: vi.fn(),
      onDuplicateWithVideos: vi.fn(),
      onDelete: vi.fn(),
    };

    const { rerender } = render(
      <ShotControls
        isTempShot={false}
        displayImagesCount={2}
        isEditingName={false}
        dragHandleProps={{}}
        dragDisabledReason={undefined}
        duplicateIsPending={false}
        duplicateWithVideosIsPending={false}
        isHidden={true}
        {...callbacks}
      />,
    );

    fireEvent.click(getTooltipButton(/generate video/i));
    fireEvent.click(getTooltipButton(/edit shot name/i));
    fireEvent.click(getTooltipButton(/duplicate shot/i));
    fireEvent.click(getTooltipButton(/duplicate with videos/i));
    fireEvent.click(getTooltipButton(/delete shot/i));

    expect(callbacks.onVideoClick).toHaveBeenCalledTimes(1);
    expect(callbacks.onEditName).toHaveBeenCalledTimes(1);
    expect(callbacks.onDuplicate).toHaveBeenCalledTimes(1);
    expect(callbacks.onDuplicateWithVideos).toHaveBeenCalledTimes(1);
    expect(callbacks.onDelete).toHaveBeenCalledTimes(1);

    rerender(
      <ShotControls
        isTempShot={true}
        displayImagesCount={2}
        isEditingName={false}
        dragHandleProps={{}}
        dragDisabledReason="Locked"
        duplicateIsPending={false}
        duplicateWithVideosIsPending={false}
        isHidden={true}
        {...callbacks}
      />,
    );

    expect(screen.getAllByText('Saving...').length).toBeGreaterThan(0);
    screen.getAllByRole('button').forEach((button) => {
      expect(button).toBeDisabled();
    });
  });

  it('renders a hide toggle between duplicate and delete when hidden controls are provided', () => {
    const callbacks = {
      onVideoClick: vi.fn(),
      onEditName: vi.fn(),
      onDuplicate: vi.fn(),
      onDuplicateWithVideos: vi.fn(),
      onToggleHidden: vi.fn(),
      onDelete: vi.fn(),
    };
    const parentClick = vi.fn();

    const { rerender } = render(
      <div onClick={parentClick}>
        <ShotControls
          isTempShot={false}
          displayImagesCount={2}
          isEditingName={false}
          dragHandleProps={{}}
          dragDisabledReason={undefined}
          duplicateIsPending={false}
          duplicateWithVideosIsPending={false}
          isHidden={false}
          {...callbacks}
        />
      </div>,
    );

    fireEvent.click(getTooltipButton(/duplicate shot/i));
    fireEvent.click(screen.getByRole('button', { name: /hide shot/i }));

    expect(callbacks.onDuplicate).toHaveBeenCalledTimes(1);
    expect(callbacks.onToggleHidden).toHaveBeenCalledTimes(1);
    expect(screen.queryByLabelText(/delete shot/i)).not.toBeInTheDocument();
    expect(parentClick).not.toHaveBeenCalled();
    expect(screen.getByText('Hide shot')).toBeInTheDocument();

    rerender(
      <div onClick={parentClick}>
        <ShotControls
          isTempShot={false}
          displayImagesCount={2}
          isEditingName={false}
          dragHandleProps={{}}
          dragDisabledReason={undefined}
          duplicateIsPending={false}
          duplicateWithVideosIsPending={false}
          isHidden={true}
          {...callbacks}
        />
      </div>,
    );

    expect(screen.getByLabelText('Unhide shot')).toBeInTheDocument();
    expect(screen.getByText('Unhide shot')).toBeInTheDocument();

    fireEvent.click(getTooltipButton(/delete shot/i));
    expect(callbacks.onDelete).toHaveBeenCalledTimes(1);
  });

  it('keeps normal duplicate and Duplicate with videos as distinct accessible controls', () => {
    const callbacks = {
      onVideoClick: vi.fn(),
      onEditName: vi.fn(),
      onDuplicate: vi.fn(),
      onDuplicateWithVideos: vi.fn(),
      onDelete: vi.fn(),
    };

    const { rerender } = render(
      <ShotControls
        isTempShot={false}
        displayImagesCount={2}
        isEditingName={false}
        duplicateIsPending={false}
        duplicateWithVideosIsPending={false}
        isHidden={false}
        {...callbacks}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Duplicate shot' }));

    expect(callbacks.onDuplicate).toHaveBeenCalledTimes(1);
    expect(callbacks.onDuplicateWithVideos).not.toHaveBeenCalled();
    expect(screen.getByText('Duplicate shot')).toBeInTheDocument();
    expect(screen.getByText('Duplicate with videos')).toBeInTheDocument();

    callbacks.onDuplicate.mockClear();

    fireEvent.click(screen.getByRole('button', { name: 'Duplicate with videos' }));

    expect(callbacks.onDuplicate).not.toHaveBeenCalled();
    expect(callbacks.onDuplicateWithVideos).toHaveBeenCalledTimes(1);

    rerender(
      <ShotControls
        isTempShot={false}
        displayImagesCount={2}
        isEditingName={false}
        duplicateIsPending={true}
        duplicateWithVideosIsPending={false}
        isHidden={false}
        {...callbacks}
      />,
    );

    expect(screen.getByRole('button', { name: 'Duplicate with videos' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Duplicate shot' })).toBeDisabled();

    rerender(
      <ShotControls
        isTempShot={false}
        displayImagesCount={2}
        isEditingName={false}
        duplicateIsPending={false}
        duplicateWithVideosIsPending={true}
        isHidden={false}
        {...callbacks}
      />,
    );

    expect(screen.getByRole('button', { name: 'Duplicate with videos' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Duplicate shot' })).not.toBeDisabled();
  });

  it('renders the final-video preview and toggles back to shot images', () => {
    const onShowVideoChange = vi.fn();
    const onFinalVideoLightboxOpen = vi.fn();

    render(
      <ShotPreview
        displayImages={[createImage('img-1', '/one.png')]}
        pendingUploads={0}
        finalVideo={{ location: '/final.mp4', thumbnailUrl: '/thumb.jpg' } as never}
        showVideo={true}
        onShowVideoChange={onShowVideoChange}
        projectAspectRatio="16:9"
        dropLoadingState="idle"
        onFinalVideoLightboxOpen={onFinalVideoLightboxOpen}
        showMobileSelect={false}
        isSelectedForAddition={false}
        onSelectShotForAddition={vi.fn()}
      />,
    );

    expect(screen.getByTestId('hover-scrub-video')).toHaveAttribute('data-src', '/final.mp4');

    fireEvent.click(screen.getByTestId('hover-scrub-video').parentElement as HTMLElement);
    fireEvent.click(screen.getByRole('button', { name: /shot images/i }));

    expect(onFinalVideoLightboxOpen).toHaveBeenCalledTimes(1);
    expect(onShowVideoChange).toHaveBeenCalledWith(false);
  });

  it('shows collapsed images, expands them, and surfaces final-video and select actions in image mode', () => {
    const onShowVideoChange = vi.fn();
    const onSelectShotForAddition = vi.fn();

    render(
      <ShotPreview
        displayImages={[
          createImage('img-1', '/one.png'),
          createImage('img-2', '/two.png'),
          createImage('img-3', '/three.png'),
          createImage('img-4', '/four.png'),
        ]}
        pendingUploads={1}
        finalVideo={{ location: '/final.mp4', thumbnailUrl: '/thumb.jpg' } as never}
        showVideo={false}
        onShowVideoChange={onShowVideoChange}
        projectAspectRatio="1:1"
        dropLoadingState="loading"
        onFinalVideoLightboxOpen={vi.fn()}
        showMobileSelect={true}
        isSelectedForAddition={false}
        onSelectShotForAddition={onSelectShotForAddition}
      />,
    );

    expect(screen.getAllByRole('img')).toHaveLength(3);
    expect(screen.getByText('Show All (5)')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /show all \(5\)/i }));

    expect(screen.getAllByRole('img')).toHaveLength(4);
    expect(screen.getByRole('button', { name: /hide/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /final video/i }));
    fireEvent.click(screen.getByRole('button', { name: /select/i }));

    expect(onShowVideoChange).toHaveBeenCalledWith(true);
    expect(onSelectShotForAddition).toHaveBeenCalledTimes(1);
  });
});
