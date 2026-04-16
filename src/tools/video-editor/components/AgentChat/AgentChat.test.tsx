// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AgentTurn } from '@/tools/video-editor/types/agent-session';
import { AgentChat } from './AgentChat';

const mocks = vi.hoisted(() => ({
  useAgentChatBridge: vi.fn(),
  useAgentSessions: vi.fn(),
  useCreateSession: vi.fn(),
  useAgentSession: vi.fn(),
  useSendMessage: vi.fn(),
  useCancelSession: vi.fn(),
  useGallerySelection: vi.fn(),
  useAgentVoice: vi.fn(),
  loadGenerationForLightbox: vi.fn(),
}));

vi.mock('@/shared/contexts/AgentChatContext', () => ({
  useAgentChatBridge: (...args: unknown[]) => mocks.useAgentChatBridge(...args),
}));

vi.mock('@/tools/video-editor/hooks/useAgentSession', () => ({
  useAgentSessions: (...args: unknown[]) => mocks.useAgentSessions(...args),
  useCreateSession: (...args: unknown[]) => mocks.useCreateSession(...args),
  useAgentSession: (...args: unknown[]) => mocks.useAgentSession(...args),
  useSendMessage: (...args: unknown[]) => mocks.useSendMessage(...args),
  useCancelSession: (...args: unknown[]) => mocks.useCancelSession(...args),
}));

vi.mock('@/shared/state/selectionStore', () => ({
  useGallerySelection: (...args: unknown[]) => mocks.useGallerySelection(...args),
}));

vi.mock('@/shared/contexts/PanesContext', () => ({
  usePanes: () => ({
    isTasksPaneLocked: false,
    tasksPaneWidth: 0,
    isGenerationsPaneLocked: false,
    isGenerationsPaneOpen: false,
    effectiveGenerationsPaneHeight: 0,
  }),
}));

vi.mock('@/tools/video-editor/hooks/useAgentVoice', () => ({
  useAgentVoice: (...args: unknown[]) => mocks.useAgentVoice(...args),
}));

vi.mock('@/tools/video-editor/lib/generation-utils', () => ({
  loadGenerationForLightbox: (...args: unknown[]) => mocks.loadGenerationForLightbox(...args),
}));

vi.mock('@/domains/media-lightbox/MediaLightbox', () => ({
  MediaLightbox: ({ media }: { media: { id: string } }) => <div data-testid="media-lightbox">{media.id}</div>,
}));

vi.mock('./AgentChatMessage', () => ({
  AgentChatMessage: ({ turn }: { turn: { content: string } }) => <div>{turn.content}</div>,
  AgentChatToolGroup: () => null,
  AgentChatAttachmentStrip: ({
    attachments,
    onRemoveAttachment,
    onRemoveShot,
  }: {
    attachments: Array<{ clipId: string; shotId?: string }>;
    onRemoveAttachment?: (attachment: { clipId: string; shotId?: string }) => void;
    onRemoveShot?: (shotId: string) => void;
  }) => (
    <div>
      {attachments.map((attachment) => (
        <button
          key={`remove-${attachment.clipId}`}
          type="button"
          onClick={() => onRemoveAttachment?.(attachment)}
        >
          {`remove-${attachment.clipId}`}
        </button>
      ))}
      {attachments
        .filter((attachment) => attachment.shotId)
        .map((attachment) => (
          <button
            key={`remove-shot-${attachment.shotId}`}
            type="button"
            onClick={() => onRemoveShot?.(attachment.shotId!)}
          >
            {`remove-shot-${attachment.shotId}`}
          </button>
        ))}
    </div>
  ),
}));

function iso(timestampMs: number) {
  return new Date(timestampMs).toISOString();
}

function createUserTurn(content: string, timestampMs: number): AgentTurn {
  return {
    role: 'user',
    content,
    timestamp: iso(timestampMs),
  };
}

function createTimelineClip(clipId: string) {
  return {
    clipId,
    assetKey: `asset-${clipId}`,
    url: `https://example.com/${clipId}.png`,
    mediaType: 'image' as const,
    isTimelineBacked: true,
  };
}

function createState() {
  return {
    timelineId: 'timeline-1' as string | null,
    timelineClips: [] as Array<ReturnType<typeof createTimelineClip>>,
    replaceSelectedTimelineClips: vi.fn(),
    sessionsData: [{ id: 'session-1', status: 'waiting_user' }],
    activeSessionData: {
      id: 'session-1',
      status: 'waiting_user',
      turns: [] as AgentTurn[],
    },
    createSession: {
      isPending: false,
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue({ id: 'session-2' }),
    },
    sendMessage: {
      mutateAsync: vi.fn().mockResolvedValue(undefined),
      isPending: false,
      localError: null as string | null,
    },
    cancelSession: {
      mutate: vi.fn(),
      isPending: false,
    },
    gallerySelection: {
      gallerySelectionMap: new Map(),
      selectedGalleryClips: [],
      deselectGalleryItems: vi.fn(),
      clearGallerySelection: vi.fn(),
    },
    voice: {
      startRecording: vi.fn(),
      stopRecording: vi.fn(),
      cancelRecording: vi.fn(),
      isRecording: false,
      isProcessing: false,
      remainingSeconds: 30,
    },
  };
}

function mockFromState(state: ReturnType<typeof createState>) {
  mocks.useAgentChatBridge.mockImplementation(() => ({
    timelineId: state.timelineId,
    timelineClips: state.timelineClips,
    replaceSelectedTimelineClips: state.replaceSelectedTimelineClips,
  }));
  mocks.useAgentSessions.mockImplementation(() => ({
    data: state.sessionsData,
    isLoading: false,
  }));
  mocks.useCreateSession.mockImplementation(() => state.createSession);
  mocks.useAgentSession.mockImplementation(() => ({
    data: state.activeSessionData,
    isLoading: false,
  }));
  mocks.useSendMessage.mockImplementation(() => state.sendMessage);
  mocks.useCancelSession.mockImplementation(() => state.cancelSession);
  mocks.useGallerySelection.mockImplementation(() => state.gallerySelection);
  mocks.useAgentVoice.mockImplementation(() => state.voice);
}

function renderAgentChat() {
  return render(
    <MemoryRouter initialEntries={['/tools/video-editor']}>
      <AgentChat />
    </MemoryRouter>,
  );
}

function rerenderAgentChat(rerender: ReturnType<typeof render>['rerender']) {
  rerender(
    <MemoryRouter initialEntries={['/tools/video-editor']}>
      <AgentChat />
    </MemoryRouter>,
  );
}

async function openChatAndGetInput() {
  fireEvent.click(screen.getByRole('button', { name: /timeline agent/i }));
  const textbox = await screen.findByRole('textbox');
  await waitFor(() => expect(textbox).not.toBeDisabled());
  return textbox;
}

async function queueMessage(textbox: HTMLElement, text: string) {
  fireEvent.change(textbox, { target: { value: text } });
  fireEvent.keyDown(textbox, { key: 'Enter' });
  await waitFor(() => expect((textbox as HTMLInputElement).value).toBe(''));
}

function getQueuedTexts() {
  return Array.from(document.querySelectorAll('.line-clamp-2')).map((node) => node.textContent);
}

describe('AgentChat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
      configurable: true,
      value: vi.fn(),
    });

    mocks.loadGenerationForLightbox.mockResolvedValue({
      id: 'gen-1',
      generation_id: 'gen-1',
      location: 'https://example.com/shared.png',
      imageUrl: 'https://example.com/shared.png',
      thumbUrl: 'https://example.com/shared.png',
      type: 'image',
      primary_variant_id: null,
      name: 'Shared image',
    });
  });

  it('shows a no-timeline prompt and does not auto-create a session', async () => {
    const state = createState();
    state.timelineId = null;
    state.sessionsData = [];
    state.createSession = {
      isPending: false,
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
    };
    mockFromState(state);

    renderAgentChat();

    fireEvent.click(screen.getByRole('button', { name: /timeline agent/i }));

    expect(await screen.findByText('Create a timeline to start chatting.')).toBeInTheDocument();
    await waitFor(() => expect(state.createSession.mutate).not.toHaveBeenCalled());
  });

  it('auto-creates a session when the chat opens with a timeline available', async () => {
    const state = createState();
    state.sessionsData = [];
    state.createSession = {
      isPending: false,
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue({ id: 'session-2' }),
    };
    mockFromState(state);

    renderAgentChat();

    fireEvent.click(screen.getByRole('button', { name: /timeline agent/i }));

    await waitFor(() => expect(state.createSession.mutate).toHaveBeenCalledTimes(1));
  });

  it('opens the chat instead of starting recording when no timeline exists', async () => {
    const state = createState();
    state.timelineId = null;
    state.sessionsData = [];
    state.voice = {
      startRecording: vi.fn(),
      stopRecording: vi.fn(),
      cancelRecording: vi.fn(),
      isRecording: false,
      isProcessing: false,
      remainingSeconds: 30,
    };
    mockFromState(state);

    renderAgentChat();

    fireEvent.keyDown(window, {
      key: 'r',
      metaKey: true,
      shiftKey: true,
    });

    expect(state.voice.startRecording).not.toHaveBeenCalled();
    expect(await screen.findByText('Create a timeline to start chatting.')).toBeInTheDocument();
  });

  it('routes attachment removal through the bridge callback', async () => {
    const state = createState();
    state.timelineClips = [
      createTimelineClip('clip-1'),
      createTimelineClip('clip-2'),
    ];
    mockFromState(state);

    renderAgentChat();

    fireEvent.click(screen.getByRole('button', { name: /timeline agent/i }));
    fireEvent.click(screen.getByRole('button', { name: 'remove-clip-1' }));

    expect(state.replaceSelectedTimelineClips).toHaveBeenCalledWith([
      expect.objectContaining({ clipId: 'clip-2' }),
    ]);
  });

  it('allows typing while processing and queues without sending immediately', async () => {
    const state = createState();
    state.activeSessionData.status = 'processing';
    mockFromState(state);

    renderAgentChat();

    const textbox = await openChatAndGetInput();
    expect(textbox).not.toBeDisabled();

    await queueMessage(textbox, 'queued while processing');

    expect(state.sendMessage.mutateAsync).not.toHaveBeenCalled();
    expect(screen.getByText('queued while processing')).toBeInTheDocument();
  });

  it('auto-sends the queued head with attachments snapshotted at queue time', async () => {
    const state = createState();
    state.activeSessionData.status = 'processing';
    state.timelineClips = [createTimelineClip('clip-1')];
    mockFromState(state);

    const view = renderAgentChat();
    const textbox = await openChatAndGetInput();

    await queueMessage(textbox, 'send old attachment');
    expect(state.sendMessage.mutateAsync).not.toHaveBeenCalled();

    state.timelineClips = [createTimelineClip('clip-2')];
    state.activeSessionData.status = 'waiting_user';
    rerenderAgentChat(view.rerender);

    await waitFor(() => {
      expect(state.sendMessage.mutateAsync).toHaveBeenCalledWith({
        message: 'send old attachment',
        attachments: [
          expect.objectContaining({ clipId: 'clip-1' }),
        ],
      });
    });
  });

  it('does not clear optimistic state for duplicate text until a newer matching turn appears', async () => {
    const state = createState();
    const dateNowSpy = vi.spyOn(Date, 'now').mockReturnValue(10_000);
    state.activeSessionData.status = 'processing';
    state.activeSessionData.turns = [
      createUserTurn('same text', 9_000),
    ];
    mockFromState(state);

    const view = renderAgentChat();
    const textbox = await openChatAndGetInput();

    await queueMessage(textbox, 'same text');
    await queueMessage(textbox, 'same text');

    state.activeSessionData.status = 'waiting_user';
    rerenderAgentChat(view.rerender);

    await waitFor(() => expect(state.sendMessage.mutateAsync).toHaveBeenCalledTimes(1));

    state.activeSessionData.turns = [
      createUserTurn('same text', 9_000),
    ];
    rerenderAgentChat(view.rerender);

    await waitFor(() => expect(state.sendMessage.mutateAsync).toHaveBeenCalledTimes(1));

    state.activeSessionData.turns = [
      createUserTurn('same text', 9_000),
      createUserTurn('same text', 10_500),
    ];
    rerenderAgentChat(view.rerender);

    await waitFor(() => expect(state.sendMessage.mutateAsync).toHaveBeenCalledTimes(2));
    dateNowSpy.mockRestore();
  });

  it('keeps a failed head queued, shows an error, and only resumes draining after the failed head is removed', async () => {
    const state = createState();
    state.activeSessionData.status = 'processing';
    state.sendMessage.mutateAsync = vi.fn().mockImplementation(async ({ message }: { message: string }) => {
      if (message === 'first queued') {
        state.sendMessage.localError = 'Send failed';
        throw new Error('Send failed');
      }

      return undefined;
    });
    mockFromState(state);

    const view = renderAgentChat();
    const textbox = await openChatAndGetInput();

    await queueMessage(textbox, 'first queued');
    await queueMessage(textbox, 'second queued');

    state.activeSessionData.status = 'waiting_user';
    rerenderAgentChat(view.rerender);

    await waitFor(() => expect(state.sendMessage.mutateAsync).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText('Send failed')).toBeInTheDocument());
    expect(getQueuedTexts()).toEqual(['first queued', 'second queued']);

    fireEvent.click(screen.getAllByTitle('Remove queued message')[0]);

    await waitFor(() => {
      expect(state.sendMessage.mutateAsync).toHaveBeenNthCalledWith(2, {
        message: 'second queued',
        attachments: [],
      });
    });
  });

  it('reorders and deletes queued messages in the rendered stack', async () => {
    const state = createState();
    state.activeSessionData.status = 'processing';
    mockFromState(state);

    renderAgentChat();

    const textbox = await openChatAndGetInput();

    await queueMessage(textbox, 'first');
    await queueMessage(textbox, 'second');
    await queueMessage(textbox, 'third');

    expect(getQueuedTexts()).toEqual(['first', 'second', 'third']);

    fireEvent.click(screen.getAllByTitle('Move queued message down')[0]);
    expect(getQueuedTexts()).toEqual(['second', 'first', 'third']);

    fireEvent.click(screen.getAllByTitle('Remove queued message')[1]);
    expect(getQueuedTexts()).toEqual(['second', 'third']);
  });
});
