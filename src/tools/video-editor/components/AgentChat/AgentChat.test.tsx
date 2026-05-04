// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AgentTurn } from '@/tools/video-editor/types/agent-session';
import { AgentChatPanel } from './AgentChat';

const mocks = vi.hoisted(() => ({
  useAgentChatBridge: vi.fn(),
  useAgentChatActionsRegistry: vi.fn(),
  useVideoEditorRuntime: vi.fn(),
  useAgentSessions: vi.fn(),
  useCreateSession: vi.fn(),
  useAgentSession: vi.fn(),
  useSendMessage: vi.fn(),
  useCancelSession: vi.fn(),
  useCurrentAttachmentSet: vi.fn(),
  composerRemoveAttachment: vi.fn(),
  composerClearAttachments: vi.fn(),
  useAgentVoice: vi.fn(),
  loadGenerationForLightbox: vi.fn(),
  // Mutable so individual tests can flip isTasksPaneLocked to satisfy the
  // engagement gate that drives auto-create.
  panesState: { isTasksPaneLocked: false },
}));

vi.mock('@/shared/contexts/AgentChatContext', () => ({
  useAgentChatBridge: (...args: unknown[]) => mocks.useAgentChatBridge(...args),
  useAgentChatActionsRegistry: (...args: unknown[]) => mocks.useAgentChatActionsRegistry(...args),
}));

vi.mock('@/tools/video-editor/contexts/DataProviderContext', () => ({
  useVideoEditorRuntime: (...args: unknown[]) => mocks.useVideoEditorRuntime(...args),
}));

vi.mock('@/tools/video-editor/hooks/useAgentSession', () => ({
  useAgentSessions: (...args: unknown[]) => mocks.useAgentSessions(...args),
  useCreateSession: (...args: unknown[]) => mocks.useCreateSession(...args),
  useAgentSession: (...args: unknown[]) => mocks.useAgentSession(...args),
  useSendMessage: (...args: unknown[]) => mocks.useSendMessage(...args),
  useCancelSession: (...args: unknown[]) => mocks.useCancelSession(...args),
}));

vi.mock('@/shared/state/selectionStore', () => ({
  composerRemoveAttachment: (...args: unknown[]) => mocks.composerRemoveAttachment(...args),
  composerClearAttachments: (...args: unknown[]) => mocks.composerClearAttachments(...args),
}));

vi.mock('@/shared/state/currentAttachmentSet', () => ({
  useCurrentAttachmentSet: (...args: unknown[]) => mocks.useCurrentAttachmentSet(...args),
}));

vi.mock('@/shared/state/panesStore', () => ({
  // AgentChatPanel only reads isTasksPaneLocked now (used as an engagement signal).
  usePanesStore: (selector: (state: { isTasksPaneLocked: boolean }) => unknown) =>
    selector({ isTasksPaneLocked: mocks.panesState.isTasksPaneLocked }),
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
  mocks.useVideoEditorRuntime.mockImplementation(() => ({
    mediaLightbox: {
      loadGenerationForLightbox: mocks.loadGenerationForLightbox,
      Lightbox: ({ media }: { media: { id: string } }) => <div data-testid="media-lightbox">{media.id}</div>,
    },
  }));
  mocks.useAgentChatBridge.mockImplementation(() => ({
    timelineId: state.timelineId,
  }));
  mocks.useAgentChatActionsRegistry.mockImplementation(() => ({
    registerHandlers: vi.fn(),
    publishState: vi.fn(),
    unregister: vi.fn(),
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
  mocks.useCurrentAttachmentSet.mockImplementation(() => ({
    clips: state.timelineClips,
    summary: state.timelineClips.length > 0 ? `attaching ${state.timelineClips.length} image` : '',
  }));
  mocks.useAgentVoice.mockImplementation(() => state.voice);
}

function renderAgentChat() {
  return render(<AgentChatPanel />);
}

function rerenderAgentChat(rerender: ReturnType<typeof render>['rerender']) {
  rerender(<AgentChatPanel />);
}

async function getInput() {
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
    // Default: pane is locked so the engagement gate is satisfied and the
    // existing auto-create assertions still hold. Tests that need the unengaged
    // baseline flip this back to false.
    mocks.panesState.isTasksPaneLocked = true;
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

  it('shows a no-timeline prompt and does not auto-create a session even when engaged', async () => {
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

    expect(await screen.findByText('Create a timeline to start chatting.')).toBeInTheDocument();
    await waitFor(() => expect(state.createSession.mutate).not.toHaveBeenCalled());
  });

  it('auto-creates a session when the engagement gate fires (pane locked) with a timeline available', async () => {
    const state = createState();
    state.sessionsData = [];
    state.createSession = {
      isPending: false,
      mutate: vi.fn(),
      mutateAsync: vi.fn().mockResolvedValue({ id: 'session-2' }),
    };
    mockFromState(state);

    renderAgentChat();

    await waitFor(() => expect(state.createSession.mutate).toHaveBeenCalledTimes(1));
  });

  it('does not auto-create when unengaged (pane unlocked, no voice, no markEngaged)', async () => {
    mocks.panesState.isTasksPaneLocked = false;
    const state = createState();
    state.sessionsData = [];
    state.createSession = {
      isPending: false,
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
    };
    mockFromState(state);

    renderAgentChat();

    // Give the auto-create effect time to NOT fire.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(state.createSession.mutate).not.toHaveBeenCalled();
  });

  it('Cmd+Shift+R is a no-op when no timeline exists', async () => {
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
  });

  it('routes attachment removal through the composer intent', async () => {
    const state = createState();
    state.timelineClips = [
      createTimelineClip('clip-1'),
      createTimelineClip('clip-2'),
    ];
    mockFromState(state);

    renderAgentChat();

    fireEvent.click(screen.getByRole('button', { name: 'remove-clip-1' }));

    expect(mocks.composerRemoveAttachment).toHaveBeenCalledWith(expect.objectContaining({
      clipId: 'clip-1',
      url: 'https://example.com/clip-1.png',
      mediaType: 'image',
    }));
  });

  it('allows typing while processing and queues without sending immediately', async () => {
    const state = createState();
    state.activeSessionData.status = 'processing';
    mockFromState(state);

    renderAgentChat();

    const textbox = await getInput();
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
    const textbox = await getInput();

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
    const textbox = await getInput();

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
    const textbox = await getInput();

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

    const textbox = await getInput();

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
