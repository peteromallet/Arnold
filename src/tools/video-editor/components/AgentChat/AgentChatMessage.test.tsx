// @vitest-environment jsdom
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AgentChatAttachmentStrip, AgentChatMessage } from './AgentChatMessage';

describe('AgentChatMessage', () => {
  it('renders attachment summaries for gallery-style attachments that include generationId', () => {
    render(
      <AgentChatMessage
        turn={{
          role: 'assistant',
          content: 'I used your selected references.',
          attachments: [
            {
              clipId: 'gallery-gen-1',
              url: 'https://example.com/image.png',
              mediaType: 'image',
              generationId: 'gen-1',
            },
            {
              clipId: 'gallery-gen-2',
              url: 'https://example.com/video.mp4',
              mediaType: 'video',
              generationId: 'gen-2',
            },
          ],
          timestamp: '2026-04-04T12:00:00.000Z',
        }}
      />,
    );

    expect(screen.getByText('I used your selected references.')).toBeInTheDocument();
    expect(screen.getByLabelText('Attached image 1')).toBeInTheDocument();
    expect(screen.getByLabelText('Attached video 2')).toBeInTheDocument();
    expect(screen.getByText('1 image, 1 video attached')).toBeInTheDocument();
  });

  it('collapses extra attachment previews behind a count badge', () => {
    render(
      <AgentChatMessage
        turn={{
          role: 'user',
          content: 'Use these attachments.',
          attachments: [
            { clipId: 'clip-1', url: 'https://example.com/1.png', mediaType: 'image' },
            { clipId: 'clip-2', url: 'https://example.com/2.png', mediaType: 'image' },
            { clipId: 'clip-3', url: 'https://example.com/3.png', mediaType: 'image' },
            { clipId: 'clip-4', url: 'https://example.com/4.png', mediaType: 'image' },
            { clipId: 'clip-5', url: 'https://example.com/5.png', mediaType: 'image' },
          ],
          timestamp: '2026-04-04T12:00:00.000Z',
        }}
      />,
    );

    expect(screen.getAllByLabelText(/Attached image \d/)).toHaveLength(4);
    expect(screen.getByLabelText('1 more attachments')).toBeInTheDocument();
    expect(screen.getByText('+1')).toBeInTheDocument();
    expect(screen.getByText('5 images attached')).toBeInTheDocument();
  });

  it('renders shot-aware attachment summaries when a whole shot was attached', () => {
    render(
      <AgentChatMessage
        turn={{
          role: 'user',
          content: 'Use this shot and these extras.',
          attachments: [
            { clipId: 'shot-1-a', url: 'https://example.com/1.png', mediaType: 'image', shotId: 'shot-1', shotSelectionClipCount: 4 },
            { clipId: 'shot-1-b', url: 'https://example.com/2.png', mediaType: 'image', shotId: 'shot-1', shotSelectionClipCount: 4 },
            { clipId: 'shot-1-c', url: 'https://example.com/3.png', mediaType: 'image', shotId: 'shot-1', shotSelectionClipCount: 4 },
            { clipId: 'shot-1-d', url: 'https://example.com/4.png', mediaType: 'image', shotId: 'shot-1', shotSelectionClipCount: 4 },
            { clipId: 'clip-5', url: 'https://example.com/5.png', mediaType: 'image' },
            { clipId: 'clip-6', url: 'https://example.com/6.png', mediaType: 'image' },
          ],
          timestamp: '2026-04-04T12:00:00.000Z',
        }}
      />,
    );

    expect(screen.getByText('1 shot (4 images) and 2 more images attached')).toBeInTheDocument();
  });

  it('calls the attachment click handler for clickable previews', () => {
    const onAttachmentClick = vi.fn();

    render(
      <AgentChatMessage
        turn={{
          role: 'assistant',
          content: 'I used your selected references.',
          attachments: [
            {
              clipId: 'gallery-gen-1',
              url: 'https://example.com/image.png',
              mediaType: 'image',
              generationId: 'gen-1',
            },
          ],
          timestamp: '2026-04-04T12:00:00.000Z',
        }}
        onAttachmentClick={onAttachmentClick}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open attached image 1' }));

    expect(onAttachmentClick).toHaveBeenCalledWith({
      clipId: 'gallery-gen-1',
      url: 'https://example.com/image.png',
      mediaType: 'image',
      generationId: 'gen-1',
    });
  });

  it('renders full-shot selections inside a grouped bounding box', () => {
    render(
      <AgentChatAttachmentStrip
        attachments={[
          { clipId: 'shot-1-a', url: 'https://example.com/1.png', mediaType: 'image', shotId: 'shot-1', shotName: 'Hero Shot', shotSelectionClipCount: 2 },
          { clipId: 'shot-1-b', url: 'https://example.com/2.png', mediaType: 'image', shotId: 'shot-1', shotName: 'Hero Shot', shotSelectionClipCount: 2 },
          { clipId: 'clip-3', url: 'https://example.com/3.png', mediaType: 'image' },
        ]}
        isUser={false}
        maxPreviewCount={null}
      />,
    );

    expect(screen.getByLabelText('Hero Shot group')).toBeInTheDocument();
    expect(screen.getByText('Hero Shot (2)')).toBeInTheDocument();
    expect(screen.getAllByLabelText(/Attached image \d/)).toHaveLength(3);
  });

  it('calls remove handlers for individual items and whole shots', () => {
    const onRemoveAttachment = vi.fn();
    const onRemoveShot = vi.fn();

    render(
      <AgentChatAttachmentStrip
        attachments={[
          { clipId: 'shot-1-a', url: 'https://example.com/1.png', mediaType: 'image', shotId: 'shot-1', shotName: 'Hero Shot', shotSelectionClipCount: 2 },
          { clipId: 'shot-1-b', url: 'https://example.com/2.png', mediaType: 'image', shotId: 'shot-1', shotName: 'Hero Shot', shotSelectionClipCount: 2 },
          { clipId: 'clip-3', url: 'https://example.com/3.png', mediaType: 'image' },
        ]}
        isUser={false}
        onRemoveAttachment={onRemoveAttachment}
        onRemoveShot={onRemoveShot}
        maxPreviewCount={null}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Deselect Hero Shot' }));
    fireEvent.click(screen.getByRole('button', { name: 'Deselect attached image 2' }));

    expect(onRemoveShot).toHaveBeenCalledWith('shot-1');
    expect(onRemoveAttachment).toHaveBeenCalledWith({
      clipId: 'clip-3',
      url: 'https://example.com/3.png',
      mediaType: 'image',
    });
  });

  it('renders placeholder attachment chips as loading slots without media bindings or remove controls', () => {
    const onRemoveAttachment = vi.fn();

    render(
      <AgentChatAttachmentStrip
        attachments={[
          {
            clipId: 'pending-clip',
            url: '',
            mediaType: 'image',
            isPlaceholder: true,
          },
        ]}
        isUser={false}
        onRemoveAttachment={onRemoveAttachment}
        maxPreviewCount={null}
      />,
    );

    const loadingSlot = screen.getByLabelText('Attached image 1');

    expect(within(loadingSlot).getByText('Loading…')).toBeInTheDocument();
    expect(screen.getByLabelText('Loading attached image 1')).toBeInTheDocument();
    expect(loadingSlot.querySelector('img')).not.toBeInTheDocument();
    expect(loadingSlot.querySelector('video')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Deselect attached image 1' })).not.toBeInTheDocument();
  });

  it('renders non-placeholder attachment chips with media bindings and remove controls', () => {
    const onRemoveAttachment = vi.fn();

    render(
      <AgentChatAttachmentStrip
        attachments={[
          {
            clipId: 'real-clip',
            url: 'https://example.com/real.png',
            mediaType: 'image',
          },
        ]}
        isUser={false}
        onRemoveAttachment={onRemoveAttachment}
        maxPreviewCount={null}
      />,
    );

    const chip = screen.getByLabelText('Attached image 1');
    const image = chip.querySelector('img');

    expect(image).toBeInTheDocument();
    expect(image).toHaveAttribute('src', 'https://example.com/real.png');
    fireEvent.click(screen.getByRole('button', { name: 'Deselect attached image 1' }));
    expect(onRemoveAttachment).toHaveBeenCalledWith({
      clipId: 'real-clip',
      url: 'https://example.com/real.png',
      mediaType: 'image',
    });
  });

  it('reserves the same chip dimensions for placeholder and real attachment slots', () => {
    render(
      <AgentChatAttachmentStrip
        attachments={[
          {
            clipId: 'pending-clip',
            url: '',
            mediaType: 'image',
            isPlaceholder: true,
          },
          {
            clipId: 'real-clip',
            url: 'https://example.com/real.mp4',
            mediaType: 'video',
          },
        ]}
        isUser={false}
        maxPreviewCount={null}
      />,
    );

    const placeholderSurface = screen.getByLabelText('Attached image 1').parentElement;
    const realSurface = screen.getByLabelText('Attached video 2').parentElement;

    expect(placeholderSurface).toHaveClass('h-10', 'w-10');
    expect(realSurface).toHaveClass('h-10', 'w-10');
  });
});
